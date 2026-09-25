using AiDe.Core.Watcher;

namespace AiDe.Core.Tests.Watcher;

/// <summary>
/// D5 — the one call site that turns a scored episode into a Daydream observation.
/// </summary>
/// <remarks>
/// <para>The whole vertical folds from what this writes, so its refusals matter more than its
/// writes: a clean episode must not become a pattern, and an unavailable record must not report a
/// write it did not make.</para>
///
/// <para><b>OBSERVED RED — mutation replay, 2026-09-02</b> (DC-099: a test that has only ever been
/// green is not evidence). Making the observation id non-deterministic reddens
/// <c>ReObservingOneEpisodeProducesTheSameId</c> alone; making <c>Append</c> report success with
/// nowhere to write reddens <c>AnUnavailableRecordIsReportedAsNoWrite</c> and the record's own.</para>
///
/// <para><b>And four tests here are load-bearing on the scorer, not merely adjacent to it.</b> The
/// concurrent session's mutation sweep found that making an unevidenced episode trip a floor reddens
/// <c>ACleanEpisodeIsNotObservedAtAll</c>, <c>AnUnassessedEpisodeIsDistinguishedFromACleanOne</c> and
/// <c>TheRealEvidenceFreeEpisodeReportsAsUnassessed</c> here. <see cref="DaydreamObservationOutcome"/>'s
/// whole distinction rests on the scorer refusing to fabricate a floor it did not observe — a
/// coupling neither session would have described that way before measuring it.</para>
/// </remarks>
public sealed class DaydreamRecorderTests : IDisposable
{
    private readonly string _root = Path.Combine(
        Path.GetTempPath(), "aide-recorder-" + Guid.NewGuid().ToString("n")[..8]);

    private readonly DaydreamRepositoryRecord _record;

    public DaydreamRecorderTests()
    {
        Directory.CreateDirectory(_root);
        _record = DaydreamRepositoryRecord.For(_root);
    }

    public void Dispose()
    {
        try { Directory.Delete(_root, recursive: true); } catch (IOException) { /* best effort */ }
    }

    private static readonly DateTimeOffset At = DateTimeOffset.UnixEpoch.AddDays(1);

    private DaydreamRecorder Recorder(DaydreamRepositoryRecord? record = null) =>
        new(record ?? _record, () => At);

    private static ScoredEpisode Episode(
        string id,
        WeaveVerdict verdict = WeaveVerdict.Blocked,
        FloorDomain[]? floors = null,
        int? rubric = 1)
    {
        var assessments = rubric is null
            ? (IReadOnlyList<DimensionAssessment>)[]
            : [new DimensionAssessment(
                ScoreDimension.OutcomeIntegrity, 30, rubric, 0, AssessmentPosture.Deterministic, "…")];

        return new ScoredEpisode(
            id, "claude-code", "opus", "operator-1",
            new ScoreSegment(TestWorkspaces.Repo, "implement", ScoreSchema.Weave1Version),
            new Scorecard(
                id, ScoreSchema.Weave1Version, verdict, assessments,
                floors ?? [FloorDomain.Correctness], Coverage: null, "…", At));
    }

    // ------------------------------------------------------------------- writes

    [Fact]
    public void AScoredEpisodeBecomesAnObservationInTheRepository()
    {
        Assert.Equal(DaydreamObservationOutcome.Recorded, Recorder().Observe(Episode("ep-1")));

        var observation = Assert.Single(_record.Read().Observations);
        Assert.Equal("ep-1", observation.EpisodeId);
        Assert.Equal(At, observation.ObservedAt);
        Assert.Equal("Correctness", observation.Signature.Floors);
        Assert.Equal("OutcomeIntegrity:1", observation.Signature.Shortfalls);
    }

    /// <summary>
    /// A clean episode is not a pattern.
    /// </summary>
    /// <remarks>
    /// US-9's rule, enforced at the writer rather than only at the fold: a record full of "work went
    /// well" is true, recurrent, and useless as a lesson — and it would push genuine patterns below
    /// any threshold that counted rows.
    /// </remarks>
    [Fact]
    public void ACleanEpisodeIsNotObservedAtAll()
    {
        Assert.Equal(
            DaydreamObservationOutcome.NothingWentWrong,
            Recorder().Observe(Episode("ep-1", WeaveVerdict.Scored, floors: [], rubric: 4)));

        Assert.Empty(_record.Read().Observations);
    }

    /// <summary>An unavailable record reports that it did not write, rather than throwing or lying.</summary>
    [Fact]
    public void AnUnavailableRecordIsReportedAsNoWrite()
    {
        Assert.Equal(
            DaydreamObservationOutcome.RecordUnavailable,
            Recorder(DaydreamRepositoryRecord.Absent).Observe(Episode("ep-1")));
    }

    // ------------------------------------------- nothing observed is not nothing wrong

    /// <summary>
    /// An episode nobody assessed does not report as a clean one.
    /// </summary>
    /// <remarks>
    /// Both produce an empty signature and both write nothing, so a boolean return collapsed them —
    /// and they are opposites. "Assessed, nothing fell short" is the system working; "no dimension
    /// carried a rubric" is the system seeing nothing. Rendered alike, a permanently quiet Daydream
    /// reads as a healthy repository (DC-025).
    /// </remarks>
    [Fact]
    public void AnUnassessedEpisodeIsDistinguishedFromACleanOne()
    {
        Assert.Equal(
            DaydreamObservationOutcome.NothingWasAssessed,
            Recorder().Observe(Episode("ep-1", WeaveVerdict.NotScored, floors: [], rubric: null)));

        Assert.Equal(
            DaydreamObservationOutcome.NothingWentWrong,
            Recorder().Observe(Episode("ep-2", WeaveVerdict.Scored, floors: [], rubric: 4)));
    }

    /// <summary>
    /// The discriminator asks the rubrics, not the verdict — in both crossed states.
    /// </summary>
    /// <remarks>
    /// <para><b>Found by mutation, and it was UNCOVERED.</b> Swapping the discriminator for
    /// <c>Verdict != NotScored</c> passed all 87 Daydream tests on 2026-09-02. The comment claimed
    /// the rubric form was stronger "whatever its verdict says"; nothing tested the claim.</para>
    ///
    /// <para><b>Why it was uncovered, which is the honest part.</b> <c>WeaveScorer</c> returns
    /// <c>NotScored</c> with an <b>empty</b> assessment list, so today the two questions have the
    /// same answer for everything it emits. No test built from scorer output could separate them.
    /// Both cards below are therefore constructed by hand and are states the scorer does not
    /// currently produce — this pins the discriminator's own contract, not the scorer's behaviour,
    /// and says so rather than implying the states are reachable.</para>
    ///
    /// <para><b>What it protects.</b> If the scorer ever emits <c>NotScored</c> carrying rubrics, or
    /// <c>Scored</c> carrying none, a verdict-based discriminator inverts silently — reporting an
    /// assessed episode as unobserved, or an unobserved one as clean, which is the DC-025 this enum
    /// exists to prevent, reintroduced from the other side of the boundary.</para>
    /// </remarks>
    [Fact]
    public void TheDiscriminatorAsksTheRubricsNotTheVerdict()
    {
        // NotScored, but a dimension WAS assessed: something was looked at, so this is not "nothing
        // was assessed" however the verdict reads.
        Assert.Equal(
            DaydreamObservationOutcome.NothingWentWrong,
            Recorder().Observe(Episode("ep-1", WeaveVerdict.NotScored, floors: [], rubric: 3)));

        // Scored, but nothing carried a rubric: no shortfall was possible, so the signature could
        // never have keyed on this episode — whatever the verdict claims.
        Assert.Equal(
            DaydreamObservationOutcome.NothingWasAssessed,
            Recorder().Observe(Episode("ep-2", WeaveVerdict.Scored, floors: [], rubric: null)));
    }

    /// <summary>
    /// And the real evidence-free path, scored by the real scorer, is the unassessed one.
    /// </summary>
    /// <remarks>
    /// <para>MEASURED on 2026-09-02, after a prediction that went the other way. I argued that a
    /// Not-Scored episode would still carry a tripped floor and so would be observed — and that
    /// Daydream would drown in one useless recurring pattern. It produces
    /// <c>verdict=NotScored floors=[] rubrics=[]</c>: no assessments at all. A floor is an
    /// <i>observed</i> failure, so nothing can trip when nothing is observed.</para>
    ///
    /// <para>Built through <c>DeterministicSignalsDeriver</c> and <c>WeaveScorer</c> rather than
    /// from a hand-made <c>Scorecard</c>, because the claim is about what the real scorer emits. A
    /// fixture asserting my belief about its output would have passed while being wrong, which is
    /// how the prediction survived being written down in the first place.</para>
    /// </remarks>
    [Fact]
    public void TheRealEvidenceFreeEpisodeReportsAsUnassessed()
    {
        var closed = DateTimeOffset.UnixEpoch.AddDays(1);
        var episode = new WorkEpisode(
            "ep-1", "sess-1", new EpisodeGeneration(1), new Goal("Ship it"),
            new DoneCondition("tests green"), null, DateTimeOffset.UnixEpoch, closed,
            EpisodeOutcome.Completed);

        var card = new WeaveScorer().Score(
            episode,
            DeterministicSignalsDeriver.Derive(
                episode, new EpisodeEvidence(HasProofPack: false), new InMemoryWatcherObservationStore()),
            new FixedTimeProvider(closed));

        Assert.Equal(WeaveVerdict.NotScored, card.Verdict);
        Assert.Empty(card.TrippedFloors);

        var scored = new ScoredEpisode(
            "ep-1", "claude-code", "opus", "op-1",
            new ScoreSegment(TestWorkspaces.Repo, "implement", ScoreSchema.Weave1Version), card);

        Assert.True(DaydreamSignature.For(scored).IsUnremarkable);
        Assert.Equal(DaydreamObservationOutcome.NothingWasAssessed, Recorder().Observe(scored));
        Assert.Empty(_record.Read().Observations);
    }

    // ------------------------------------------------------------- determinism

    /// <summary>
    /// Re-scoring one episode produces the same observation id.
    /// </summary>
    /// <remarks>
    /// So a content union across two worktrees collapses a genuine duplicate rather than keeping two
    /// rows that mean one thing. The id is not relied on for uniqueness — the fold deduplicates by
    /// episode — but a random id would make every merge grow the record.
    /// </remarks>
    [Fact]
    public void ReObservingOneEpisodeProducesTheSameId()
    {
        var recorder = Recorder();
        recorder.Observe(Episode("ep-1"));
        recorder.Observe(Episode("ep-1"));

        var ids = _record.Read().Observations.Select(o => o.ObservationId).Distinct().ToList();

        Assert.Single(ids);
    }

    /// <summary>Two episodes with the same shortfall are one pattern with two occurrences.</summary>
    [Fact]
    public void TwoEpisodesWithOneSignatureBecomeARecurrence()
    {
        var recorder = Recorder();
        recorder.Observe(Episode("ep-1"));
        recorder.Observe(Episode("ep-2"));

        var recurrence = Assert.Single(new RecurrenceDetector().Recurring(_record.Read().Observations));

        Assert.Equal(2, recurrence.DistinctEpisodes);
    }

    /// <summary>
    /// A different shortfall is a different pattern, however similar the episodes look.
    /// </summary>
    /// <remarks>
    /// The signature is what makes two things "the same", and merging on the episode's other
    /// properties would produce one class general enough to prevent nothing.
    /// </remarks>
    [Fact]
    public void ADifferentShortfallIsADifferentPattern()
    {
        var recorder = Recorder();
        recorder.Observe(Episode("ep-1", rubric: 1));
        recorder.Observe(Episode("ep-2", rubric: 0));

        Assert.Equal(2, _record.Read().Observations.Select(o => o.Signature).Distinct().Count());
        Assert.Empty(new RecurrenceDetector().Recurring(_record.Read().Observations));
    }

    /// <summary>
    /// The observation survives the round trip through the committed file, not just in memory.
    /// </summary>
    /// <remarks>
    /// Read through a SECOND record over the same folder, because the point of the decision is that
    /// a different process — a later session, another clone — reads what this one wrote.
    /// </remarks>
    [Fact]
    public void AnotherReaderOverTheSameRepositorySeesIt()
    {
        Recorder().Observe(Episode("ep-1"));

        var elsewhere = DaydreamRepositoryRecord.For(_root).Read();

        Assert.Single(elsewhere.Observations);
        Assert.Equal(0, elsewhere.UnreadableLines);
    }
}
