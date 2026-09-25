using AiDe.Core.Watcher;

namespace AiDe.Core.Tests.Watcher;

/// <summary>
/// D5 — the Daydream record the product maintains IN the repository it is about.
/// </summary>
/// <remarks>
/// <para>The owner's decision (<c>note-20260902-two-decisions-the-loop-waits-on</c>): "day dreaming
/// is specific to a repo and should be maintained in the repo … i.e the product should write to the
/// repo". The per-workspace SQLite store gave the rows the wrong lifetime — they outlived the
/// repository they were about, and a clone on another machine started with nothing.</para>
///
/// <para>The tests below are about the properties that make a committed, hand-inspectable,
/// union-merged file trustworthy: round-trip, per-record provenance, order independence, and the
/// difference between a line that is missing and one that could not be read.</para>
///
/// <para><b>OBSERVED RED — mutation replay, 2026-09-02.</b> Every test here was written in the same
/// edit as the code it covers, so none had ever been shown capable of failing. A test that has only
/// been green is not evidence (DC-099). Each row below is a mutation applied to the production code,
/// with the tests that went red against a baseline of 87 green:</para>
///
/// <list type="table">
///   <item><description>enum written as an ordinal → <c>EnumsAreWrittenAsNames…</c>, <c>AnEventRoundTrips…</c>, <c>AnUnknownOutcome…</c></description></item>
///   <item><description>events not sorted by sequence → <c>EventsAreOrderedBySequenceNotByLinePosition</c>, alone</description></item>
///   <item><description>unknown outcome silently defaulted → <c>AnUnknownOutcomeIsUnreadableRatherThanTreatedAsAbsent</c>, alone</description></item>
///   <item><description>unreadable lines not counted → <c>AnUnreadableLineIsSkippedAndCounted</c> + <c>AnUnknownOutcome…</c></description></item>
///   <item><description>index rewritten on every append → <c>AnExistingIndexIsNeverRewritten</c>, alone</description></item>
///   <item><description>provenance marker misspelled → <c>EveryWrittenLineCarries…</c>, <c>TheIndexUsesTheSameMarkerSpelling…</c></description></item>
///   <item><description>append reports success with nowhere to write → <c>WritingToAnUnavailableRecord…</c> + the recorder's</description></item>
/// </list>
///
/// <para>Zero uncovered. The couplings are real rather than accidental: counting no unreadable lines
/// also reddens the unknown-outcome test, because that test asserts the count — which is the two
/// controls sharing one claim, not one of them being redundant.</para>
/// </remarks>
public sealed class DaydreamRepositoryRecordTests : IDisposable
{
    private readonly string _root = Path.Combine(
        Path.GetTempPath(), "aide-daydream-" + Guid.NewGuid().ToString("n")[..8]);

    private static readonly DaydreamSignature Pattern = new(
        "implement", ScoreSchema.Weave1Version, WeaveVerdict.Blocked, "Correctness", "OutcomeIntegrity:1");

    public DaydreamRepositoryRecordTests() => Directory.CreateDirectory(_root);

    public void Dispose()
    {
        try { Directory.Delete(_root, recursive: true); } catch (IOException) { /* best effort */ }
    }

    private DaydreamRepositoryRecord Record() => DaydreamRepositoryRecord.For(_root);

    private string LogPath(string name) => Path.Combine(_root, "docs", "daydream", name);

    private static DaydreamObservation Observation(string id, string episode, int minute = 0) =>
        new(id, Pattern, episode, DateTimeOffset.UnixEpoch.AddMinutes(minute));

    // ------------------------------------------------------------------ absence

    /// <summary>
    /// A workspace with no repository has nowhere to write, and says so.
    /// </summary>
    /// <remarks>
    /// The alternative — reporting an empty record — would let a surface tell the user this
    /// repository has observed nothing, about a repository it never opened (DC-025).
    /// </remarks>
    [Fact]
    public void NoRepositoryIsAStatedAbsenceRatherThanAnEmptyRecord()
    {
        var record = DaydreamRepositoryRecord.For(null);

        Assert.False(record.Available);
        Assert.Contains("No repository is open", record.Unavailable);
        Assert.Null(record.Directory);
        Assert.Equal(DaydreamRecordRead.Empty, record.Read());
    }

    /// <summary>A root that does not exist is a different absence, and names itself differently.</summary>
    [Fact]
    public void AMissingRepositoryFolderNamesItsOwnCause()
    {
        var record = DaydreamRepositoryRecord.For(Path.Combine(_root, "nope"));

        Assert.False(record.Available);
        Assert.Contains("not found", record.Unavailable);
    }

    /// <summary>An unavailable record refuses the write instead of failing silently.</summary>
    /// <remarks>
    /// <c>false</c>, not an exception and not <c>true</c>. A writer that returned success with
    /// nowhere to write would produce a Daydream that reports observations it never kept.
    /// </remarks>
    [Fact]
    public void WritingToAnUnavailableRecordReportsThatItDidNotWrite()
    {
        Assert.False(DaydreamRepositoryRecord.Absent.Append(Observation("obs-1", "ep-1")));
    }

    // ------------------------------------------------------------- round trip

    [Fact]
    public void AnObservationRoundTripsThroughTheRepository()
    {
        Assert.True(Record().Append(Observation("obs-1", "ep-1", minute: 7)));

        var read = Record().Read();

        var observation = Assert.Single(read.Observations);
        Assert.Equal("obs-1", observation.ObservationId);
        Assert.Equal("ep-1", observation.EpisodeId);
        Assert.Equal(DateTimeOffset.UnixEpoch.AddMinutes(7), observation.ObservedAt);
        Assert.Equal(Pattern, observation.Signature);
        Assert.Equal(0, read.UnreadableLines);
    }

    [Fact]
    public void AnEventRoundTripsWithItsOutcomeAndSequence()
    {
        var written = new DaydreamEvent(
            "evt-1", Pattern, DaydreamEventKind.CheckCompleted, "operator",
            "check: reran the failing gate", DisconfirmingOutcome.Survived,
            DateTimeOffset.UnixEpoch.AddHours(3), Sequence: 42);

        Assert.True(Record().Append(written));

        var read = Assert.Single(Record().Read().Events);
        Assert.Equal(written, read);
    }

    /// <summary>An event with no detail and no outcome round-trips as null, not as empty text.</summary>
    /// <remarks>
    /// The fold reads <c>Outcome</c> to decide whether a check has run at all. An absent outcome
    /// arriving back as a value would turn a candidate awaiting its check into one that has had it.
    /// </remarks>
    [Fact]
    public void AnEventWithoutDetailOrOutcomeKeepsBothAsAbsent()
    {
        Record().Append(new DaydreamEvent(
            "evt-1", Pattern, DaydreamEventKind.Proposed, "watcher",
            Detail: null, Outcome: null, DateTimeOffset.UnixEpoch, Sequence: 1));

        var read = Assert.Single(Record().Read().Events);
        Assert.Null(read.Detail);
        Assert.Null(read.Outcome);
    }

    // ------------------------------------------------------------ provenance

    /// <summary>
    /// Every line carries its own provenance.
    /// </summary>
    /// <remarks>
    /// Per-record rather than a file header, because these logs merge by CONTENT UNION across
    /// worktrees (<c>tools/merge-append-only-log.py</c>, the DC-026 control). A header would be
    /// merged, duplicated, or lost; a field on each record survives all three.
    /// </remarks>
    [Fact]
    public void EveryWrittenLineCarriesTheProvenanceMarker()
    {
        var record = Record();
        record.Append(Observation("obs-1", "ep-1"));
        record.Append(Observation("obs-2", "ep-2"));
        record.Append(new DaydreamEvent(
            "evt-1", Pattern, DaydreamEventKind.Proposed, "watcher", null, null,
            DateTimeOffset.UnixEpoch, 1));

        var lines = File.ReadAllLines(LogPath("observations.jsonl"))
            .Concat(File.ReadAllLines(LogPath("events.jsonl")))
            .Where(l => l.Trim().Length > 0)
            .ToList();

        Assert.Equal(3, lines.Count);
        Assert.All(lines, l => Assert.Contains("\"generated-by\":\"ai-de/daydream\"", l));
    }

    /// <summary>
    /// The marker is spelled exactly one way, in every format.
    /// </summary>
    /// <remarks>
    /// Agreed with the concurrent session and recorded in the design §4b. The point of one spelling
    /// is that <c>grep -r "generated-by"</c> finds every product-written artifact in every format —
    /// which is the enforcement gate's first draft. A second spelling defeats it silently.
    /// </remarks>
    [Fact]
    public void TheIndexUsesTheSameMarkerSpellingAsTheLogLines()
    {
        Record().Append(Observation("obs-1", "ep-1"));

        var index = File.ReadAllText(Path.Combine(_root, "docs", "daydream", "index.md"));

        Assert.Contains("generated-by: ai-de/daydream", index);
        Assert.Contains("do not hand-edit", index, StringComparison.OrdinalIgnoreCase);
    }

    /// <summary>
    /// The index is written once and never rewritten.
    /// </summary>
    /// <remarks>
    /// It is the human-facing file in a product-owned folder, and a human may add to it. Rewriting
    /// it on every append would be the product overwriting an agent's or a person's edit — the exact
    /// failure the provenance rule exists to prevent, committed by the rule's own first instance.
    /// </remarks>
    [Fact]
    public void AnExistingIndexIsNeverRewritten()
    {
        var record = Record();
        record.Append(Observation("obs-1", "ep-1"));

        var path = Path.Combine(_root, "docs", "daydream", "index.md");
        File.AppendAllText(path, "\nA human added this line.\n");

        record.Append(Observation("obs-2", "ep-2"));

        Assert.Contains("A human added this line.", File.ReadAllText(path));
    }

    // -------------------------------------------------------- hand-edit safety

    /// <summary>
    /// Enum values are written as NAMES.
    /// </summary>
    /// <remarks>
    /// An ordinal in a committed file is unreadable to the human it is committed for, and reordering
    /// an enum would silently rewrite the meaning of every historical line — the file would still
    /// parse, and every past record would mean something else.
    /// </remarks>
    [Fact]
    public void EnumsAreWrittenAsNamesSoAReorderCannotRewriteHistory()
    {
        Record().Append(new DaydreamEvent(
            "evt-1", Pattern, DaydreamEventKind.CheckCompleted, "operator", null,
            DisconfirmingOutcome.Refuted, DateTimeOffset.UnixEpoch, 1));

        var line = File.ReadAllLines(LogPath("events.jsonl"))[0];

        Assert.Contains("\"eventKind\":\"CheckCompleted\"", line);
        Assert.Contains("\"outcome\":\"Refuted\"", line);
        Assert.Contains("\"verdict\":\"Blocked\"", line);
    }

    /// <summary>A malformed line is skipped and COUNTED, never silently dropped.</summary>
    /// <remarks>
    /// Following the audit log's own verifier ("0 unreadable lines"). Dropping it silently would
    /// render a partial record as a complete one, and the surface would report a smaller number as
    /// if it were the whole truth (DC-025).
    /// </remarks>
    [Fact]
    public void AnUnreadableLineIsSkippedAndCounted()
    {
        Record().Append(Observation("obs-1", "ep-1"));
        File.AppendAllText(LogPath("observations.jsonl"), "not json at all\n{ broken\n");

        var read = Record().Read();

        Assert.Single(read.Observations);
        Assert.Equal(2, read.UnreadableLines);
    }

    /// <summary>
    /// An outcome this version does not recognise makes the line unreadable, not outcome-less.
    /// </summary>
    /// <remarks>
    /// The dangerous direction. Reading a future <c>Refuted</c>-like outcome as "no outcome" would
    /// turn a refuted candidate back into an open one — a promotion block quietly lifted by an
    /// upgrade in the other direction.
    /// </remarks>
    [Fact]
    public void AnUnknownOutcomeIsUnreadableRatherThanTreatedAsAbsent()
    {
        Record().Append(new DaydreamEvent(
            "evt-1", Pattern, DaydreamEventKind.CheckCompleted, "operator", null,
            DisconfirmingOutcome.Survived, DateTimeOffset.UnixEpoch, 1));

        var path = LogPath("events.jsonl");
        File.WriteAllText(path, File.ReadAllText(path).Replace("\"Survived\"", "\"Inconclusive\""));

        var read = Record().Read();

        Assert.Empty(read.Events);
        Assert.Equal(1, read.UnreadableLines);
    }

    // ------------------------------------------------------------ merge safety

    /// <summary>
    /// Events fold in sequence order however the lines ended up ordered in the file.
    /// </summary>
    /// <remarks>
    /// A union merge across two worktrees produces a file in neither writer's order. A fold that
    /// depended on line order would give two clones two different candidate states from one
    /// committed record — the disagreement being invisible because both files are valid.
    /// </remarks>
    [Fact]
    public void EventsAreOrderedBySequenceNotByLinePosition()
    {
        var record = Record();
        record.Append(new DaydreamEvent("evt-3", Pattern, DaydreamEventKind.Promoted, "a", null, null, DateTimeOffset.UnixEpoch, 3));
        record.Append(new DaydreamEvent("evt-1", Pattern, DaydreamEventKind.Proposed, "a", null, null, DateTimeOffset.UnixEpoch, 1));
        record.Append(new DaydreamEvent("evt-2", Pattern, DaydreamEventKind.EvidenceAttached, "a", null, null, DateTimeOffset.UnixEpoch, 2));

        Assert.Equal(
            ["evt-1", "evt-2", "evt-3"],
            Record().Read().Events.Select(e => e.EventId));
    }

    /// <summary>A duplicated line is not a second occurrence.</summary>
    /// <remarks>
    /// A union merge can legitimately produce the same observation twice — two worktrees both
    /// observed the same episode. The fold deduplicates by episode, so recurrence cannot be
    /// manufactured by a merge, which is the cheapest possible route to a confident wrong lesson.
    /// </remarks>
    [Fact]
    public void ADuplicatedObservationDoesNotManufactureRecurrence()
    {
        var record = Record();
        record.Append(Observation("obs-1", "ep-1"));
        record.Append(Observation("obs-2", "ep-1", minute: 5));

        var read = record.Read();

        Assert.Equal(2, read.Observations.Count);
        Assert.Empty(new RecurrenceDetector().Recurring(read.Observations));
    }

    /// <summary>Reading a repository that has never been daydreamed in is empty, not an error.</summary>
    [Fact]
    public void AnUntouchedRepositoryReadsEmptyRatherThanFailing()
    {
        var read = Record().Read();

        Assert.Empty(read.Observations);
        Assert.Empty(read.Events);
        Assert.Equal(0, read.UnreadableLines);
    }
}
