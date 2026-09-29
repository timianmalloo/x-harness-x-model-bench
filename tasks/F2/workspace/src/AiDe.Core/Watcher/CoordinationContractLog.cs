using System.Text;
using System.Text.Json;

namespace AiDe.Core.Watcher;

/// <summary>
/// Writes injected-contract events for one or more non-AI-Forward sessions to a coord-core-shaped
/// append log (spike S4): one file per session (<c>&lt;dir&gt;/&lt;session&gt;.jsonl</c>), one JSON object
/// per line, <c>seq</c> auto-assigned, an atomic single-write append, and the <b>LOG-A</b> guard - a
/// leading newline when the file did not already end in one, so a fused line is impossible to express.
/// This is the session-side half of the contract; <see cref="InjectedContractIngest"/> is the ingest half.
/// </summary>
public sealed class CoordContractWriter
{
    private readonly string _logDir;
    private readonly TimeProvider _time;

    public CoordContractWriter(string logDir, TimeProvider? time = null)
    {
        ArgumentException.ThrowIfNullOrEmpty(logDir);
        _logDir = logDir;
        _time = time ?? TimeProvider.System;
    }

    /// <summary>Writes a registration with the same <see cref="OtelAttributes"/> keys as the OTLP path.</summary>
    public void WriteRegister(string externalSessionId, IReadOnlyDictionary<string, string?> attributes)
    {
        ArgumentNullException.ThrowIfNull(attributes);
        Append(externalSessionId, "register", attributes);
    }

    public void WriteHeartbeat(string externalSessionId) => Append(externalSessionId, "heartbeat", null);

    public void WriteSessionEnd(string externalSessionId) => Append(externalSessionId, "session-end", null);

    /// <summary>
    /// Writes one contract line of any kind — the same line an agent writes by hand.
    /// </summary>
    /// <remarks>
    /// <para><b>Here rather than in the MCP server, because the line format must have exactly one
    /// definition.</b> The server's whole claim is that it is a translation of the contract rather
    /// than a parallel API (<c>design-mcp-enlightened-path</c>), and a second place that knows how a
    /// contract line is spelled would make that claim untestable — the two paths could then differ
    /// in precisely the way the equivalence gate exists to catch.</para>
    ///
    /// <para><b>It validates nothing.</b> Every kind's refusals belong to
    /// <c>InjectedContractIngest</c>, with counters, and re-deciding any of them here would be a
    /// second set of rules free to drift from the first. Callers report what the ingest will do;
    /// this writes what the caller said.</para>
    /// </remarks>
    public void Write(string kind, string externalSessionId, IReadOnlyDictionary<string, string?> attributes)
    {
        ArgumentException.ThrowIfNullOrEmpty(kind);
        ArgumentNullException.ThrowIfNull(attributes);
        Append(externalSessionId, kind, attributes);
    }

    /// <summary>
    /// Writes one <c>board-post</c> line — the same line an agent writes by hand.
    /// </summary>
    /// <remarks>
    /// Its own method rather than a <see cref="Write"/> call at each site because the absent-vs-null
    /// content rule below is a property of the board's wire shape, and a rule enforced at the call
    /// sites is a rule the next call site will not know about. It validates nothing else, for the
    /// reason <see cref="Write"/> gives.
    /// </remarks>
    public void WriteBoardPost(
        string externalSessionId, string kind, string? content, string? parentMessageId = null)
    {
        ArgumentException.ThrowIfNullOrEmpty(kind);

        var attributes = new Dictionary<string, string?>(StringComparer.Ordinal)
        {
            [CoordContract.BoardAttributes.Kind] = kind,
            [CoordContract.BoardAttributes.Content] = content,
        };

        // Absent, not null: an acknowledgement legitimately carries no content, and a null-valued key
        // is a different wire fact from a missing one — the ingest reads present-but-blank as
        // malformed, which is the distinction that makes a lost value visible.
        if (content is null)
        {
            attributes.Remove(CoordContract.BoardAttributes.Content);
        }

        if (!string.IsNullOrEmpty(parentMessageId))
        {
            attributes[CoordContract.BoardAttributes.Parent] = parentMessageId;
        }

        Append(externalSessionId, "board-post", attributes);
    }

    /// <summary>
    /// A filesystem-safe, deterministic file name for one external session id.
    /// </summary>
    /// <remarks>
    /// <para><b>The session id was used verbatim, and on Windows that silently created an alternate
    /// data stream.</b> An agent pane's id is <c>agent:claude#fb96e3</c>; <c>Path.Combine(dir,
    /// "agent:claude#fb96e3.jsonl")</c> is not a file called <c>agent:claude#fb96e3.jsonl</c> — NTFS
    /// reads it as the file <c>agent</c> with the stream <c>claude#fb96e3.jsonl</c>. The write
    /// succeeds. The bytes are there. And <c>Directory.EnumerateFiles(dir, "*.jsonl")</c> — which is
    /// how the pump finds logs — cannot see a stream, so <b>no agent session was ever
    /// registered</b>.</para>
    ///
    /// <para><b>Observed:</b> one zero-byte file named <c>agent</c> holding seven streams and 41 KB
    /// of coordination events, against <c>terminal-1.jsonl</c> as a real 442 KB file. Plain
    /// terminals worked; every agent pane was invisible. Nothing failed, nothing was logged, and the
    /// data was not even lost — just unreachable by every reader, backup and sync that lists files.
    /// </para>
    ///
    /// <para><b>The hash is not decoration.</b> Replacing invalid characters alone maps
    /// <c>agent:claude</c> and <c>agent-claude</c> onto one file, which would interleave two
    /// sessions' events into a single stream and fold them into one identity. The suffix is derived
    /// from the original id, so distinct sessions stay distinct and the same session always resolves
    /// to the same file.</para>
    ///
    /// <para>The name need not be reversible: every record carries its own <c>session</c> field, and
    /// the pump reads that rather than the file name.</para>
    ///
    /// <para><b>An id that is already safe is left exactly alone</b>, digest and all. Renaming
    /// <c>terminal-1.jsonl</c> would orphan every log already on disk and change the file name for
    /// the case that was never broken — the existing suite caught the first version of this doing
    /// precisely that. Only a name the filesystem would have mangled is rewritten, so the two forms
    /// cannot collide: a rewritten name always carries the digest suffix, and an untouched one
    /// contained no invalid character to have been rewritten from.</para>
    /// </remarks>
    internal static string FileNameFor(string session)
    {
        var invalid = Path.GetInvalidFileNameChars();
        var safe = new char[session.Length];
        var mangled = false;
        for (var i = 0; i < session.Length; i++)
        {
            if (Array.IndexOf(invalid, session[i]) >= 0)
            {
                safe[i] = '-';
                mangled = true;
            }
            else
            {
                safe[i] = session[i];
            }
        }

        if (!mangled)
        {
            return session + ".jsonl";
        }

        var digest = System.Security.Cryptography.SHA256.HashData(
            System.Text.Encoding.UTF8.GetBytes(session));

        return new string(safe) + "-" + Convert.ToHexString(digest.AsSpan(0, 4)).ToLowerInvariant() + ".jsonl";
    }

    private void Append(string session, string kind, IReadOnlyDictionary<string, string?>? attributes)
    {
        ArgumentException.ThrowIfNullOrEmpty(session);
        Directory.CreateDirectory(_logDir);
        var file = Path.Combine(_logDir, FileNameFor(session));

        var payload = new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["kind"] = kind,
            ["contract"] = CoordContract.Version,
            ["session"] = session,
            ["at"] = _time.GetUtcNow().ToUnixTimeMilliseconds() / 1000.0,
            ["seq"] = NextSeq(file),
        };
        if (attributes is not null)
        {
            payload["attrs"] = attributes.ToDictionary(kv => kv.Key, kv => kv.Value, StringComparer.Ordinal);
        }

        var line = JsonSerializer.Serialize(payload);
        // LOG-A: prepend a newline when the file does not already end in one, so a record left
        // unterminated by a crash or a hand edit cannot fuse with this one (control ladder rung 1).
        var text = (NeedsLeadingNewline(file) ? "\n" : "") + line + "\n";
        var bytes = Encoding.UTF8.GetBytes(text);

        // One Write under FileMode.Append (O_APPEND) is atomic: a concurrent writer cannot interleave
        // a partial line (mirrors the coord-core writer, spike S3/S4).
        using var stream = new FileStream(file, FileMode.Append, FileAccess.Write, FileShare.Read);
        stream.Write(bytes, 0, bytes.Length);
    }

    private static bool NeedsLeadingNewline(string file)
    {
        if (!File.Exists(file))
        {
            return false;
        }

        using var stream = new FileStream(file, FileMode.Open, FileAccess.Read, FileShare.ReadWrite);
        if (stream.Length == 0)
        {
            return false;
        }

        stream.Seek(-1, SeekOrigin.End);
        var last = stream.ReadByte();
        return last is not ('\n' or '\r');
    }

    private static int NextSeq(string file)
    {
        if (!File.Exists(file))
        {
            return 1;
        }

        var count = 0;
        foreach (var line in File.ReadLines(file))
        {
            if (line.Trim().Length > 0)
            {
                count++;
            }
        }

        return count + 1;
    }
}

/// <summary>Reads a coord-core append log directory into ordered contract events (stdlib, tolerant).</summary>
public static class CoordContractLog
{
    /// <summary>
    /// Reads every <c>*.jsonl</c> in <paramref name="logDir"/> and parses them into one ordered event
    /// stream (<see cref="CoordContractParser"/> sorts by <c>(at, session, seq)</c>). A missing directory
    /// yields an empty list; a malformed line in any file is skipped and counted by the parser.
    /// </summary>
    public static IReadOnlyList<CoordContractEvent> ReadDirectory(string logDir)
    {
        ArgumentException.ThrowIfNullOrEmpty(logDir);
        if (!Directory.Exists(logDir))
        {
            return [];
        }

        var builder = new StringBuilder();
        foreach (var file in Directory.EnumerateFiles(logDir, "*.jsonl").OrderBy(f => f, StringComparer.Ordinal))
        {
            builder.Append(File.ReadAllText(file));
            builder.Append('\n'); // guarantee a separator between files (defence in depth for LOG-A)
        }

        return CoordContractParser.Parse(builder.ToString());
    }
}

/// <summary>
/// Reads a contract log directory and applies it to an <see cref="InjectedContractIngest"/>. Re-running
/// is safe: the adapter is idempotent (a duplicate register is ignored, a heartbeat merely refreshes
/// liveness), so a whole-directory re-read never double-registers - which is why a naive "read it all"
/// pump is correct here without tracking file offsets.
/// </summary>
public sealed class CoordContractLogPump(string logDir, InjectedContractIngest ingest)
{
    private readonly string _logDir = !string.IsNullOrEmpty(logDir) ? logDir : throw new ArgumentException("logDir is required", nameof(logDir));
    private readonly InjectedContractIngest _ingest = ingest ?? throw new ArgumentNullException(nameof(ingest));

    /// <summary>Reads the log directory once and applies every event; returns the count applied.</summary>
    public int PumpOnce()
    {
        var events = CoordContractLog.ReadDirectory(_logDir);
        _ingest.ApplyAll(events);
        return events.Count;
    }
}
