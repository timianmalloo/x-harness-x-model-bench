using System.Diagnostics;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace AiDe.Core.PromptCompilation;

/// <summary>What one open observed — emitted as <c>envelope-store.open</c> on the normal path (ADR-0034 rule 3; IO2).</summary>
/// <param name="Bytes">The file's length at open.</param>
/// <param name="Rows">Lines walked.</param>
/// <param name="Envelopes">Envelopes the fold could read.</param>
/// <param name="BrokenAt">The line the chain broke at, or null.</param>
/// <param name="WalkMs">How long the walk took — measured, the emitter D-D5's 10 MiB trigger reads.</param>
public sealed record EnvelopeStoreOpenReport(long Bytes, int Rows, int Envelopes, int? BrokenAt, long WalkMs);

/// <summary>
/// The compiled-envelope store: one append-only, exclusively written, sha-chained JSONL sidecar per
/// session — <c>&lt;workspace&gt;/.aide/sessions/&lt;id&gt;/envelope-events.jsonl</c> (ADR-0034).
/// </summary>
/// <remarks>
/// <para><b>Append and a reader, nothing else.</b> No update, delete or rewrite member exists, and a
/// reflection test asserts the surface by name. The file is opened <c>FileShare.None</c> for the
/// life of this object: a second writer, and a reader while a writer holds it, are refused visibly
/// (DM11 h) — which is also what makes <i>no <c>submitted</c> = abandoned</i> a stable read.</para>
///
/// <para><b>The walk at open is schema-agnostic and the fold is not.</b> Every line's
/// <c>(envelope_id, seq)</c> and raw bytes are read regardless of <c>schema</c> or <c>kind</c>, so a
/// rolled-back <c>/1</c> binary opening a file with <c>/2</c> rows still mints a unique, higher
/// <c>seq</c> and an unbroken chain; only the fold skips what it cannot read, and counts it. A chain
/// broken at line N refuses <see cref="Append"/> for the life of the open and leaves the bytes for
/// inspection — refuse, not rotate: a rotated file would be a second history nothing reads.</para>
///
/// <para><b>Patterns:</b> Event Store (the envelope is the fold), Hash Chain for corruption detection
/// — not tamper evidence (Security T1/T2), Projection (<see cref="Read"/>, the eval).</para>
/// </remarks>
public sealed class EnvelopeStore : IDisposable
{
    /// <summary>The row schema this writer writes and this reader folds.</summary>
    public const string Schema = "compiled-envelope/1";

    /// <summary>The sidecar's file name, a sibling of <c>session.json</c>.</summary>
    public const string FileName = "envelope-events.jsonl";

    private static readonly ActivitySource Signal = new(CompileSignal.SourceName);
    private static readonly UTF8Encoding Utf8 = new(encoderShouldEmitUTF8Identifier: false);
    private static readonly IReadOnlyList<string> Sources = [DecorationSources.Mechanical, DecorationSources.Derived, DecorationSources.Operator, DecorationSources.SessionDefault];

    private readonly Stream _stream;
    private readonly TimeProvider _time;
    private readonly Lock _gate = new();
    private readonly Dictionary<string, int> _lastSeq;
    private readonly HashSet<string> _opened;
    private readonly HashSet<string> _accepted;
    private readonly HashSet<string> _consumed;
    private readonly List<EnvelopeEvent> _readable;
    private readonly HashSet<string> _pastBreak;
    private int _rows;
    private int _skippedSchema;
    private int _skippedKind;
    private int _skippedTorn;
    private string? _lastLine;
    private bool _needsNewline;
    private bool _disposed;
    private string? _failed;

    private EnvelopeStore(Stream stream, string path, string sessionId, TimeProvider time, Walk walk, Stopwatch clock)
    {
        _stream = stream;
        _time = time;
        Path = path;
        SessionId = sessionId;
        _lastSeq = walk.LastSeq;
        _opened = walk.Opened;
        _accepted = walk.Accepted;
        _consumed = walk.Consumed;
        _readable = walk.Readable;
        _pastBreak = walk.PastBreak;
        _rows = walk.Rows;
        _skippedSchema = walk.SkippedSchema;
        _skippedKind = walk.SkippedKind;
        _skippedTorn = walk.SkippedTorn;
        _lastLine = walk.LastLine;
        _needsNewline = walk.NeedsNewline;
        BrokenAt = walk.BrokenAt;

        // walk_ms covers the walk AND the first fold: what the open cost, measured where it is paid.
        var envelopes = FoldNow().Envelopes.Count;
        OpenReport = new EnvelopeStoreOpenReport(walk.Bytes, walk.Rows, envelopes, walk.BrokenAt, clock.ElapsedMilliseconds);
    }

    /// <summary>The file this store holds exclusively.</summary>
    public string Path { get; }

    /// <summary>The session id — the directory segment, which every <c>opened</c> row must match.</summary>
    public string SessionId { get; }

    /// <summary>The line the chain broke at, or null; when set, <see cref="Append"/> is refused for the life of this open.</summary>
    public int? BrokenAt { get; }

    /// <summary>What the open measured (bytes, rows, envelopes, broken_at, walk_ms).</summary>
    public EnvelopeStoreOpenReport OpenReport { get; }

    /// <summary>
    /// Opens the session's store exclusively, walking the whole chain first (off the caller's UI
    /// thread is the caller's job; the walk is measured either way).
    /// </summary>
    /// <param name="sessionDirectory">The session's directory; its last segment is the session id. Never created here.</param>
    /// <param name="time">The clock rows are stamped from.</param>
    /// <exception cref="EnvelopeStoreException">
    /// <see cref="EnvelopeStoreErrorCodes.NoSessionDirectory"/>; <see cref="EnvelopeStoreErrorCodes.HeldByAnotherWriter"/>.
    /// </exception>
    public static EnvelopeStore Open(string sessionDirectory, TimeProvider? time = null) => OpenWith(sessionDirectory, null, time);

    /// <summary>
    /// The fault seam for the append-failure tests (ADR-0034 rule 3's "an Append that throws after
    /// open"): <paramref name="wrap"/> decorates the exclusive file stream — a test wraps it in one
    /// that throws mid-write. Internal: the product opens through <see cref="Open"/> only.
    /// </summary>
    internal static EnvelopeStore OpenWith(string sessionDirectory, Func<Stream, Stream>? wrap, TimeProvider? time = null)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(sessionDirectory);

        var directory = System.IO.Path.GetFullPath(sessionDirectory).TrimEnd(System.IO.Path.DirectorySeparatorChar, System.IO.Path.AltDirectorySeparatorChar);
        if (!Directory.Exists(directory))
        {
            throw new EnvelopeStoreException(
                EnvelopeStoreErrorCodes.NoSessionDirectory,
                $"no session directory at '{directory}'; the store never creates the Session aggregate's directory, so compile history is not recorded until the session exists");
        }

        var sessionId = System.IO.Path.GetFileName(directory);
        var path = System.IO.Path.Combine(directory, FileName);

        using var activity = Signal.StartActivity("envelope-store.open");
        var clock = Stopwatch.StartNew();

        FileStream stream;
        try
        {
            stream = new FileStream(path, FileMode.OpenOrCreate, FileAccess.ReadWrite, FileShare.None);
        }
        catch (IOException error)
        {
            throw Held(path, error);
        }
        catch (UnauthorizedAccessException error)
        {
            throw Held(path, error);
        }

        try
        {
            var bytes = new byte[stream.Length];
            stream.ReadExactly(bytes);
            var walk = WalkAll(bytes);
            var store = new EnvelopeStore(wrap is null ? stream : wrap(stream), path, sessionId, time ?? TimeProvider.System, walk, clock);

            activity?.SetTag("bytes", walk.Bytes);
            activity?.SetTag("rows", walk.Rows);
            activity?.SetTag("envelopes", store.OpenReport.Envelopes);
            activity?.SetTag("broken_at", walk.BrokenAt);
            activity?.SetTag("walk_ms", store.OpenReport.WalkMs);
            return store;
        }
        catch
        {
            stream.Dispose();
            throw;
        }
    }

    /// <summary>
    /// The reader for purge, export and the eval: folds a file that no writer holds — refused
    /// visibly otherwise, never a partial fold.
    /// </summary>
    public static EnvelopeFold ReadFile(string path)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(path);
        if (!File.Exists(path))
        {
            return new EnvelopeFold([], 0, 0, 0, 0, null);
        }

        byte[] bytes;
        try
        {
            // FileShare.Read: two readers (purge's plan, a fold) may read at once; a writer's
            // FileShare.None still refuses a reader, and an open reader refuses a writer — visibly.
            using var stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read);
            bytes = new byte[stream.Length];
            stream.ReadExactly(bytes);
        }
        catch (IOException error)
        {
            throw Held(path, error);
        }
        catch (UnauthorizedAccessException error)
        {
            throw Held(path, error);
        }

        var walk = WalkAll(bytes);
        return Fold(walk.Readable, walk.Rows, walk.SkippedSchema, walk.SkippedKind, walk.SkippedTorn, walk.BrokenAt, walk.PastBreak);
    }

    /// <summary>
    /// Appends one event: assigns <c>seq</c> (one greater than that envelope's last) and
    /// <c>prev_sha</c> (over the raw previous line, any schema), stamps <c>at</c>, and refuses
    /// anything that would break the aggregate's one invariant.
    /// </summary>
    /// <returns>The event as written — with its <c>seq</c> and <c>at</c>.</returns>
    /// <exception cref="EnvelopeStoreException">One of the <see cref="EnvelopeStoreErrorCodes"/>; the file is unchanged on every refusal.</exception>
    public EnvelopeEvent Append(EnvelopeEvent evt)
    {
        ArgumentNullException.ThrowIfNull(evt);
        ObjectDisposedException.ThrowIf(_disposed, this);

        lock (_gate)
        {
            if (BrokenAt is { } broken)
            {
                throw new EnvelopeStoreException(
                    EnvelopeStoreErrorCodes.StoreBroken,
                    $"compile history is broken at line {broken}; purge it to start again (aide session purge {SessionId}) — nothing is appended past a break");
            }

            // LATCHED AFTER A FAILED WRITE: bytes may have partially landed, so the tail is unknown
            // — a later append would glue its row to the partial prefix into one torn line whose key
            // nothing folds, and the next open would re-mint that seq (two rows, one key). The store
            // refuses every append for the life of this open; a reopen walks the real tail.
            if (_failed is { } failed)
            {
                throw new EnvelopeStoreException(EnvelopeStoreErrorCodes.AppendFailed, $"an earlier append to '{Path}' failed ({failed}); nothing is appended until the store is reopened");
            }

            Validate(evt);

            var last = _lastSeq.GetValueOrDefault(evt.EnvelopeId);
            var stamped = evt with { Seq = last + 1, At = _time.GetUtcNow() };
            var prevSha = _lastLine is null ? string.Empty : EnvelopeHash.Sha256Hex(_lastLine);
            var line = EnvelopeRowCodec.Write(stamped, Schema, prevSha);

            try
            {
                _stream.Seek(0, SeekOrigin.End);
                if (_needsNewline)
                {
                    _stream.Write("\n"u8);
                }

                _stream.Write(Utf8.GetBytes(line));
                _stream.Write("\n"u8);
                if (_stream is FileStream file)
                {
                    file.Flush(flushToDisk: true);   // the row is durable before the append returns
                }
                else
                {
                    _stream.Flush();
                }
            }
            catch (IOException error)
            {
                _failed = error.Message;
                throw new EnvelopeStoreException(EnvelopeStoreErrorCodes.AppendFailed, $"the append to '{Path}' failed: {error.Message}", error);
            }

            _needsNewline = false;
            _lastLine = line;
            _lastSeq[evt.EnvelopeId] = stamped.Seq;
            _rows++;
            _readable.Add(stamped);
            switch (stamped)
            {
                case Opened:
                    _opened.Add(stamped.EnvelopeId);
                    break;
                case Submitted { Accepted: true }:
                    _accepted.Add(stamped.EnvelopeId);
                    break;
                case Consumed:
                    _consumed.Add(stamped.EnvelopeId);
                    break;
            }

            return stamped;
        }
    }

    /// <summary>The fold over every row this open has read or written (DM11 g's defensive fold).</summary>
    public EnvelopeFold Read()
    {
        lock (_gate)
        {
            return FoldNow();
        }
    }

    /// <summary>Releases the exclusive handle. A second open succeeds afterwards.</summary>
    public void Dispose()
    {
        if (_disposed)
        {
            return;
        }

        _disposed = true;
        _stream.Dispose();
    }

    private EnvelopeFold FoldNow() => Fold(_readable, _rows, _skippedSchema, _skippedKind, _skippedTorn, BrokenAt, _pastBreak);

    private void Validate(EnvelopeEvent evt)
    {
        var last = _lastSeq.GetValueOrDefault(evt.EnvelopeId);
        if (evt.Seq != 0 && evt.Seq != last + 1)
        {
            throw new EnvelopeStoreException(
                EnvelopeStoreErrorCodes.SeqNotIncreasing,
                $"envelope '{evt.EnvelopeId}' is at seq {last}; a supplied seq of {evt.Seq} is not its next — the writer assigns seq, a caller may only confirm it");
        }

        if (evt is Opened opened)
        {
            if (!string.Equals(opened.SessionId, SessionId, StringComparison.Ordinal))
            {
                throw new EnvelopeStoreException(
                    EnvelopeStoreErrorCodes.SessionIdMismatch,
                    $"the opened row names session '{opened.SessionId}' but this store is '{SessionId}'; the session id has two homes and the containment cascade assumes they agree");
            }

            if (_opened.Contains(evt.EnvelopeId) || last > 0)
            {
                throw new EnvelopeStoreException(EnvelopeStoreErrorCodes.NotOpened, $"envelope '{evt.EnvelopeId}' is already opened; an envelope opens once");
            }

            return;
        }

        if (!_opened.Contains(evt.EnvelopeId))
        {
            throw new EnvelopeStoreException(EnvelopeStoreErrorCodes.NotOpened, $"envelope '{evt.EnvelopeId}' has no opened row; nothing decorates, submits or consumes an envelope that was never opened");
        }

        switch (evt)
        {
            case Decorated d:
                ValidateDecoration(d);
                break;

            case Submitted { Accepted: true } when _accepted.Contains(evt.EnvelopeId):
                throw new EnvelopeStoreException(EnvelopeStoreErrorCodes.SubmittedTwice, $"envelope '{evt.EnvelopeId}' already has an accepted submitted; a send is confirmed once");

            case Consumed when _consumed.Contains(evt.EnvelopeId):
                throw new EnvelopeStoreException(EnvelopeStoreErrorCodes.ConsumedTwice, $"envelope '{evt.EnvelopeId}' already has a consumed row; exactly one per envelope");
        }
    }

    private void ValidateDecoration(Decorated d)
    {
        if (_accepted.Contains(d.EnvelopeId))
        {
            throw new EnvelopeStoreException(EnvelopeStoreErrorCodes.DecoratedAfterSubmitted, $"envelope '{d.EnvelopeId}' has an accepted submitted; no decorated event follows it");
        }

        if (!Sources.Contains(d.Source, StringComparer.Ordinal))
        {
            throw new EnvelopeStoreException(EnvelopeStoreErrorCodes.DecorationNameRefused, $"decoration '{d.Name}' carries source '{d.Source}', which is not one of {string.Join(", ", Sources)}");
        }

        if (string.Equals(d.Name, "lease", StringComparison.OrdinalIgnoreCase))
        {
            throw new EnvelopeStoreException(EnvelopeStoreErrorCodes.DecorationNameRefused, "no decoration is named lease: the lease is a projection of the source text and has one home (DM-A)");
        }

        // A SETTING, A REF OR A PROJECTION HAS ONE WRITER — the mechanical pre-compile. An operator
        // row (US-D1) or a derived row (the model, C5) named like one is refused, whatever the validator
        // upstream admitted: Current() reads by name and would otherwise take the model's ceilings.
        if (!string.Equals(d.Source, DecorationSources.Mechanical, StringComparison.Ordinal)
            && DecorationNames.NeverOperator.Contains(d.Name, StringComparer.Ordinal))
        {
            throw new EnvelopeStoreException(EnvelopeStoreErrorCodes.DecorationNameRefused, $"'{d.Name}' is a setting, a ref or a projection with one mechanical writer, never a {d.Source} decoration (US-D1: one home)");
        }

        if (string.Equals(d.Name, DecorationNames.Tier, StringComparison.Ordinal)
            && !Presentation.Composer.ComposerCompiler.IsTier(d.ValueAsString))
        {
            throw new EnvelopeStoreException(EnvelopeStoreErrorCodes.TierRefused, $"a tier row's value is one of T0, T1, T2; '{d.ValueAsString ?? d.Value?.ToJsonString() ?? "null"}' is refused and the prior row stands");
        }

        if (string.Equals(d.Name, DecorationNames.Attachments, StringComparison.Ordinal) && !IsByReferenceOnly(d.Value))
        {
            throw new EnvelopeStoreException(EnvelopeStoreErrorCodes.AttachmentBodyRefused, "an attachment value carries more than its reference; bodies are never persisted — exactly path, sha256, bytes and outside_workspace, each a scalar (§A13.5)");
        }
    }

    /// <summary>The attachment refs' shape, as an allow-list (not a deny-list a nested or re-cased body slips past): an array of objects whose members are exactly the four scalars.</summary>
    private static readonly IReadOnlyList<string> AttachmentMembers = ["path", "sha256", "bytes", "outside_workspace"];

    private static bool IsByReferenceOnly(JsonNode? value) =>
        value is JsonArray refs && refs.All(r =>
            r is JsonObject o
            && o.Count == AttachmentMembers.Count
            && AttachmentMembers.All(m => o.ContainsKey(m) && o[m] is JsonValue));

    private static EnvelopeStoreException Held(string path, Exception error) => new(
        EnvelopeStoreErrorCodes.HeldByAnotherWriter,
        $"another AI-DE has this session's compile history open ({path}); close it to write or read here",
        error);

    private static EnvelopeFold Fold(
        List<EnvelopeEvent> readable, int rows, int skippedSchema, int skippedKind, int skippedTorn, int? brokenAt, HashSet<string> pastBreak)
    {
        var events = brokenAt is null ? readable : readable.Where(e => !pastBreak.Contains(e.EnvelopeId));
        return new EnvelopeFold(Envelope.Fold(events), rows, skippedSchema, skippedKind, skippedTorn, brokenAt);
    }

    // ── the walk ──

    private sealed class Walk
    {
        public Dictionary<string, int> LastSeq { get; } = new(StringComparer.Ordinal);
        public HashSet<string> Opened { get; } = new(StringComparer.Ordinal);
        public HashSet<string> Accepted { get; } = new(StringComparer.Ordinal);
        public HashSet<string> Consumed { get; } = new(StringComparer.Ordinal);
        public List<EnvelopeEvent> Readable { get; } = [];
        public HashSet<string> PastBreak { get; } = new(StringComparer.Ordinal);
        public long Bytes { get; set; }
        public int Rows { get; set; }
        public int SkippedSchema { get; set; }
        public int SkippedKind { get; set; }
        public int SkippedTorn { get; set; }
        public int? BrokenAt { get; set; }
        public string? LastLine { get; set; }
        public bool NeedsNewline { get; set; }
    }

    /// <summary>
    /// Reads every line's key and raw bytes regardless of schema or kind, verifies the chain, and
    /// parses what the <c>/1</c> reader knows. Lines before the break fold; every key counts.
    /// </summary>
    private static Walk WalkAll(byte[] content)
    {
        var walk = new Walk { Bytes = content.Length };
        if (content.Length == 0)
        {
            return walk;
        }

        var text = Utf8.GetString(content);
        walk.NeedsNewline = text[^1] != '\n';
        var lines = (walk.NeedsNewline ? text : text[..^1]).Split('\n');
        walk.Rows = lines.Length;

        string? previous = null;
        var readableBeforeBreak = new List<(int Line, EnvelopeEvent Event)>();

        for (var i = 0; i < lines.Length; i++)
        {
            var lineNumber = i + 1;
            var raw = lines[i];
            var parsed = TryParse(raw);

            if (parsed is null)
            {
                walk.SkippedTorn++;
            }
            else
            {
                // THE CHAIN, before anything is trusted: the previous raw line's hash must be what
                // this line claims. The first line claims nothing.
                if (walk.BrokenAt is null)
                {
                    var claimed = parsed["prev_sha"] is JsonValue p && p.TryGetValue(out string? sha) ? sha : null;
                    var expected = previous is null ? string.Empty : EnvelopeHash.Sha256Hex(previous);
                    if (!string.Equals(claimed, expected, StringComparison.Ordinal))
                    {
                        walk.BrokenAt = Math.Max(1, lineNumber - 1);
                    }
                }

                if (EnvelopeRowCodec.TryReadKey(parsed, out var envelopeId, out var seq))
                {
                    walk.LastSeq[envelopeId] = Math.Max(walk.LastSeq.GetValueOrDefault(envelopeId), seq);
                    if (walk.BrokenAt is { } broken && lineNumber >= broken)
                    {
                        walk.PastBreak.Add(envelopeId);
                    }
                }

                var schema = parsed["schema"] is JsonValue s && s.TryGetValue(out string? schemaText) ? schemaText : null;
                if (!string.Equals(schema, Schema, StringComparison.Ordinal))
                {
                    walk.SkippedSchema++;
                }
                else if (EnvelopeRowCodec.TryRead(parsed) is { } evt)
                {
                    readableBeforeBreak.Add((lineNumber, evt));
                }
                else
                {
                    walk.SkippedKind++;
                }
            }

            previous = raw;
        }

        walk.LastLine = previous;

        foreach (var (lineNumber, evt) in readableBeforeBreak)
        {
            if (walk.BrokenAt is { } broken && lineNumber >= broken)
            {
                // Past the break: the key counted (above); the row never folds and never seeds the
                // envelope's accepted/consumed state — a writer must not think an unreadable envelope
                // is open for decoration.
                continue;
            }

            walk.Readable.Add(evt);
            switch (evt)
            {
                case Opened:
                    walk.Opened.Add(evt.EnvelopeId);
                    break;
                case Submitted { Accepted: true }:
                    walk.Accepted.Add(evt.EnvelopeId);
                    break;
                case Consumed:
                    walk.Consumed.Add(evt.EnvelopeId);
                    break;
            }
        }

        return walk;
    }

    private static JsonObject? TryParse(string raw)
    {
        if (raw.Length == 0 || raw[0] != '{')
        {
            return null;
        }

        try
        {
            return JsonNode.Parse(raw) as JsonObject;
        }
        catch (JsonException)
        {
            return null;
        }
    }
}
