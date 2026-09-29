using System.Globalization;
using System.Text;
using System.Text.Json;

namespace AiDe.Core.Watcher;

/// <summary>
/// What one read of the repository's Daydream record found — including what it could not read.
/// </summary>
/// <remarks>
/// <see cref="UnreadableLines"/> is reported rather than swallowed, following the audit log's own
/// verifier ("0 unreadable lines"). A line this version cannot parse is far more likely to be a
/// newer writer's than a corruption, and silently dropping it would render a partial record as a
/// complete one — an absence shown as a result (DC-025).
/// </remarks>
public sealed record DaydreamRecordRead(
    IReadOnlyList<DaydreamObservation> Observations,
    IReadOnlyList<DaydreamEvent> Events,
    int UnreadableLines)
{
    public static DaydreamRecordRead Empty { get; } = new([], [], 0);
}

/// <summary>
/// The repository's Daydream record: two append-only logs the product maintains, in the repository
/// being worked on.
/// </summary>
/// <remarks>
/// <para><b>Why the repository and not the product's store.</b> A lesson about <i>this</i>
/// repository belongs <i>with</i> that repository, for the same reason <c>defect-classes.md</c> is
/// committed rather than kept in a tool's private directory: it survives a machine change, it
/// travels with a clone, and it is reviewable in a pull request. The per-workspace SQLite store
/// gave the rows the wrong lifetime — they outlived the repository they were about.
/// (<c>design-watcher-daydream-dream-seam</c> §4a; the owner's decision in
/// <c>note-20260902-two-decisions-the-loop-waits-on</c>.)</para>
///
/// <para><b>Provenance is per-record, not per-file.</b> Every line carries
/// <c>"generated-by":"ai-de/daydream"</c>. These logs merge by <i>content union</i> across sessions
/// and worktrees (<c>tools/merge-append-only-log.py</c>, the DC-026 control), and a header line
/// would be merged, duplicated, or lost — while a field on each record survives every one of those.
/// The field's presence means the product wrote it; its absence means an agent or a human did.</para>
///
/// <para><b>Enums are written as names.</b> An ordinal in a committed file is unreadable to the
/// human it is committed for, and reordering an enum would silently rewrite the meaning of every
/// historical line.</para>
///
/// <para><b>Absence is stated.</b> A workspace with no repository has nowhere to write, and says so
/// rather than presenting an empty Daydream — the same rule <see cref="DreamCorpusReader"/> keeps
/// for an absent pack.</para>
/// </remarks>
public sealed class DaydreamRepositoryRecord
{
    /// <summary>The provenance marker, one literal spelling in every format (see the design §4b).</summary>
    public const string GeneratedBy = "ai-de/daydream";

    private const string ProvenanceField = "generated-by";

    private readonly Lock _write = new();

    private DaydreamRepositoryRecord(string? root, string? unavailable)
    {
        Root = root;
        Unavailable = unavailable;
    }

    /// <summary>The repository root, or <c>null</c> when there is none.</summary>
    public string? Root { get; }

    /// <summary>
    /// Why the record is unavailable, or <c>null</c> when it is readable and writable.
    /// </summary>
    /// <remarks>
    /// A sentence for a person, naming only what was actually checked. It never speculates about a
    /// cause this class did not look at (DC-087).
    /// </remarks>
    public string? Unavailable { get; }

    /// <summary>True when the record can be read and written.</summary>
    public bool Available => Unavailable is null;

    /// <summary>The directory the record lives in, or <c>null</c> when unavailable.</summary>
    public string? Directory => Root is null ? null : Path.Combine(Root, "docs", "daydream");

    /// <summary>Opens the record for a repository root, or reports why it cannot be opened.</summary>
    /// <remarks>
    /// The root is not created and not probed for a <c>.git</c> directory: the caller decides what a
    /// repository is, and this class only needs somewhere that exists to write into.
    /// </remarks>
    public static DaydreamRepositoryRecord For(string? repositoryRoot)
    {
        if (string.IsNullOrWhiteSpace(repositoryRoot))
        {
            return new DaydreamRepositoryRecord(
                null, "No repository is open, so nothing is recorded.");
        }

        if (!System.IO.Directory.Exists(repositoryRoot))
        {
            return new DaydreamRepositoryRecord(
                null, "The repository folder was not found, so nothing is recorded.");
        }

        return new DaydreamRepositoryRecord(Path.GetFullPath(repositoryRoot), null);
    }

    /// <summary>The record for a workspace with no repository — an absence, stated.</summary>
    public static DaydreamRepositoryRecord Absent { get; } = For(null);

    // ------------------------------------------------------------------ write

    /// <summary>Appends one observation. A no-op when the record is unavailable.</summary>
    public bool Append(DaydreamObservation observation)
    {
        ArgumentNullException.ThrowIfNull(observation);
        return AppendLine("observations.jsonl", WriteObservation(observation));
    }

    /// <summary>Appends one candidate event. A no-op when the record is unavailable.</summary>
    public bool Append(DaydreamEvent candidateEvent)
    {
        ArgumentNullException.ThrowIfNull(candidateEvent);
        return AppendLine("events.jsonl", WriteEvent(candidateEvent));
    }

    private bool AppendLine(string fileName, string line)
    {
        if (Directory is null)
        {
            return false;
        }

        lock (_write)
        {
            try
            {
                System.IO.Directory.CreateDirectory(Directory);
                EnsureIndex();
                File.AppendAllText(Path.Combine(Directory, fileName), line + "\n", Encoding.UTF8);
                return true;
            }
            catch (Exception ex) when (ex is IOException or UnauthorizedAccessException)
            {
                // A record that could not be written is not a record that says nothing happened.
                // The caller gets false; nothing here invents success.
                return false;
            }
        }
    }

    /// <summary>
    /// Writes the human-facing artifact beside the logs, once.
    /// </summary>
    /// <remarks>
    /// It exists so the record is a node in the docs graph and so a person opening the folder is
    /// told, in the file itself, that the product maintains it. Written only when absent: rewriting
    /// it on every append would overwrite a human's additions to a file whose whole point is being
    /// read by one.
    /// </remarks>
    private void EnsureIndex()
    {
        var path = Path.Combine(Directory!, "index.md");
        if (File.Exists(path))
        {
            return;
        }

        File.WriteAllText(path, $"""
            ---
            id: index-daydream-record
            title: "Daydream — this repository's observed patterns"
            type: index
            status: active
            owner: "ai-de/daydream"
            {ProvenanceField}: {GeneratedBy}
            tags: [daydream, loomkeeper, generated]
            links: []
            summary: >-
              The Daydream record for this repository: patterns AI-DE observed across closed Work
              Episodes, and the candidate lessons they became. Maintained by the product.
            ---

            # Daydream

            **Generated by `{GeneratedBy}` — do not hand-edit.** The product appends to the two logs
            beside this file and will not read your changes back. A correction belongs in the tool
            that wrote it.

            | File | One line is |
            |---|---|
            | `observations.jsonl` | one observed occurrence of one pattern in one Work Episode |
            | `events.jsonl` | one thing that happened to a candidate lesson |

            Both are **append-only** and merge by content union. Every line carries
            `"{ProvenanceField}": "{GeneratedBy}"`, which is how a tool tells the product's writes
            from an agent's.

            Nothing here is promoted. A pattern is a proposal until a human decides otherwise.

            """.ReplaceLineEndings("\n"), Encoding.UTF8);
    }

    private static string WriteObservation(DaydreamObservation o)
    {
        var buffer = new MemoryStream();
        using (var w = new Utf8JsonWriter(buffer))
        {
            w.WriteStartObject();
            w.WriteString(ProvenanceField, GeneratedBy);
            w.WriteString("kind", "observation");
            w.WriteString("id", o.ObservationId);
            w.WriteString("episode", o.EpisodeId);
            w.WriteString("observedAt", o.ObservedAt.ToString("O", CultureInfo.InvariantCulture));
            WriteSignature(w, o.Signature);
            w.WriteEndObject();
        }

        return Encoding.UTF8.GetString(buffer.ToArray());
    }

    private static string WriteEvent(DaydreamEvent e)
    {
        var buffer = new MemoryStream();
        using (var w = new Utf8JsonWriter(buffer))
        {
            w.WriteStartObject();
            w.WriteString(ProvenanceField, GeneratedBy);
            w.WriteString("kind", "event");
            w.WriteString("id", e.EventId);
            w.WriteNumber("seq", e.Sequence);
            w.WriteString("at", e.At.ToString("O", CultureInfo.InvariantCulture));
            w.WriteString("eventKind", e.Kind.ToString());
            w.WriteString("actor", e.Actor);

            if (e.Detail is not null)
            {
                w.WriteString("detail", e.Detail);
            }

            if (e.Outcome is not null)
            {
                w.WriteString("outcome", e.Outcome.Value.ToString());
            }

            WriteSignature(w, e.Signature);
            w.WriteEndObject();
        }

        return Encoding.UTF8.GetString(buffer.ToArray());
    }

    // Flat, and repeated on every line. A reader of one line sees the whole signature without a
    // join, which is what makes this file reviewable in a pull request rather than merely parseable.
    private static void WriteSignature(Utf8JsonWriter w, DaydreamSignature s)
    {
        w.WriteString("taskClass", s.TaskClass);
        w.WriteString("schemaVersion", s.SchemaVersion);
        w.WriteString("verdict", s.Verdict.ToString());
        w.WriteString("floors", s.Floors);
        w.WriteString("shortfalls", s.Shortfalls);
    }

    // ------------------------------------------------------------------- read

    /// <summary>Reads the whole record. An unavailable record reads as empty, never as an error.</summary>
    public DaydreamRecordRead Read()
    {
        if (Directory is null)
        {
            return DaydreamRecordRead.Empty;
        }

        var observations = new List<DaydreamObservation>();
        var events = new List<DaydreamEvent>();
        var unreadable = 0;

        foreach (var line in Lines("observations.jsonl", ref unreadable))
        {
            if (TryReadObservation(line, out var observation))
            {
                observations.Add(observation);
            }
            else
            {
                unreadable++;
            }
        }

        foreach (var line in Lines("events.jsonl", ref unreadable))
        {
            if (TryReadEvent(line, out var candidateEvent))
            {
                events.Add(candidateEvent);
            }
            else
            {
                unreadable++;
            }
        }

        // Ordered by the recorded sequence, so a fold over a union-merged file is deterministic
        // regardless of the order two worktrees' lines ended up in.
        events.Sort((a, b) => a.Sequence.CompareTo(b.Sequence));
        return new DaydreamRecordRead(observations, events, unreadable);
    }

    private List<string> Lines(string fileName, ref int unreadable)
    {
        var path = Path.Combine(Directory!, fileName);
        try
        {
            return File.Exists(path)
                ? [.. File.ReadAllLines(path).Where(l => l.Trim().Length > 0)]
                : [];
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException)
        {
            // Unreadable is not absent. Counting it keeps the caller's report honest: a file that
            // could not be opened must not render identically to one that does not exist.
            unreadable++;
            return [];
        }
    }

    private static bool TryReadObservation(string line, out DaydreamObservation observation)
    {
        observation = null!;
        try
        {
            using var doc = JsonDocument.Parse(line);
            var root = doc.RootElement;
            if (Text(root, "kind") != "observation"
                || !TryReadSignature(root, out var signature)
                || Text(root, "id") is not { Length: > 0 } id
                || Text(root, "episode") is not { Length: > 0 } episode
                || !DateTimeOffset.TryParse(
                    Text(root, "observedAt"), CultureInfo.InvariantCulture,
                    DateTimeStyles.RoundtripKind, out var at))
            {
                return false;
            }

            observation = new DaydreamObservation(id, signature, episode, at);
            return true;
        }
        catch (JsonException)
        {
            return false;
        }
    }

    private static bool TryReadEvent(string line, out DaydreamEvent candidateEvent)
    {
        candidateEvent = null!;
        try
        {
            using var doc = JsonDocument.Parse(line);
            var root = doc.RootElement;
            if (Text(root, "kind") != "event"
                || !TryReadSignature(root, out var signature)
                || Text(root, "id") is not { Length: > 0 } id
                || !Enum.TryParse<DaydreamEventKind>(Text(root, "eventKind"), out var kind)
                || !DateTimeOffset.TryParse(
                    Text(root, "at"), CultureInfo.InvariantCulture,
                    DateTimeStyles.RoundtripKind, out var at))
            {
                return false;
            }

            DisconfirmingOutcome? outcome = null;
            if (Text(root, "outcome") is { Length: > 0 } outcomeText)
            {
                if (!Enum.TryParse<DisconfirmingOutcome>(outcomeText, out var parsed))
                {
                    // An outcome this version does not know is not "no outcome": dropping it would
                    // turn a refuted candidate back into an open one.
                    return false;
                }

                outcome = parsed;
            }

            var sequence = root.TryGetProperty("seq", out var seq) && seq.TryGetInt64(out var value)
                ? value
                : 0L;

            candidateEvent = new DaydreamEvent(
                id, signature, kind, Text(root, "actor") ?? string.Empty,
                Text(root, "detail"), outcome, at, sequence);
            return true;
        }
        catch (JsonException)
        {
            return false;
        }
    }

    private static bool TryReadSignature(JsonElement root, out DaydreamSignature signature)
    {
        signature = null!;
        if (!Enum.TryParse<WeaveVerdict>(Text(root, "verdict"), out var verdict))
        {
            return false;
        }

        signature = new DaydreamSignature(
            Text(root, "taskClass") ?? string.Empty,
            Text(root, "schemaVersion") ?? string.Empty,
            verdict,
            Text(root, "floors") ?? string.Empty,
            Text(root, "shortfalls") ?? string.Empty);
        return true;
    }

    private static string? Text(JsonElement root, string name) =>
        root.TryGetProperty(name, out var value) && value.ValueKind == JsonValueKind.String
            ? value.GetString()
            : null;
}
