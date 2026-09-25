using AiDe.Core.Watcher;

namespace AiDe.Core.Tests.Watcher;

/// <summary>
/// The operator question the Daydream design named: <i>is Daydream seeing anything?</i>
/// </summary>
/// <remarks>
/// <para>A system that proposes nothing looks identical to one that is not running, and after the
/// collaboration loop landed that stopped being hypothetical: the agent path is wired and feeds the
/// record nothing, because an unevidenced episode has nothing to key on. The surface said "No
/// patterns observed yet", which is true and reads as reassurance.</para>
///
/// <para>Every test below is about a DISTINCTION rather than a count — the counts were never the
/// hard part. Three different states produce an empty Daydream and only one of them is a gap.</para>
/// </remarks>
public sealed class DaydreamReachProbeTests : IDisposable
{
    private readonly string _root = Path.Combine(
        Path.GetTempPath(), "aide-reach-" + Guid.NewGuid().ToString("n")[..8]);

    private readonly InMemoryWatcherObservationStore _store = new();
    private readonly DaydreamRepositoryRecord _record;

    public DaydreamReachProbeTests()
    {
        Directory.CreateDirectory(_root);
        _record = DaydreamRepositoryRecord.For(_root);
    }

    public void Dispose()
    {
        try { Directory.Delete(_root, recursive: true); } catch (IOException) { /* best effort */ }
    }

    private static readonly DateTimeOffset At = DateTimeOffset.UnixEpoch.AddDays(1);

    private DaydreamReachProbe Probe(DaydreamRepositoryRecord? record = null) =>
        new(_store, record ?? _record);

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

    private void Score(params ScoredEpisode[] episodes)
    {
        foreach (var e in episodes)
        {
            _store.RecordScorecard(e);
        }
    }

    // -------------------------------------------------- the three silences, kept apart

    /// <summary>
    /// A repository nobody has scored in is not a repository with a gap.
    /// </summary>
    /// <remarks>
    /// The state every new workspace is in. Reporting it as an instrumentation gap would make the
    /// gap meaningless on the day it is real — a warning that fires for everyone warns no one.
    /// </remarks>
    [Fact]
    public void NothingScoredYetIsNotAFinding()
    {
        var reach = Probe().Probe();

        Assert.True(reach.NothingScoredYet);
        Assert.False(reach.Deaf);
        Assert.Null(reach.Finding);
    }

    /// <summary>Work that was assessed and went well is not a gap either.</summary>
    [Fact]
    public void EverythingCleanIsNotAFinding()
    {
        Score(Episode("ep-1", WeaveVerdict.Scored, floors: [], rubric: 4),
              Episode("ep-2", WeaveVerdict.Scored, floors: [], rubric: 4));

        var reach = Probe().Probe();

        Assert.Equal(2, reach.NothingWentWrong);
        Assert.False(reach.Deaf);
        Assert.Null(reach.Finding);
    }

    /// <summary>
    /// Nothing assessable IS the gap, and it says so in the operator's terms.
    /// </summary>
    /// <remarks>
    /// The live state after the collaboration loop landed. The finding has to name the cause —
    /// "an instrumentation gap rather than a quiet repository" — because the number alone is
    /// indistinguishable from the two states above.
    /// </remarks>
    [Fact]
    public void EverythingUnassessedIsTheFindingAndNamesItsCause()
    {
        Score(Episode("ep-1", WeaveVerdict.NotScored, floors: [], rubric: null),
              Episode("ep-2", WeaveVerdict.NotScored, floors: [], rubric: null));

        var reach = Probe().Probe();

        Assert.True(reach.Deaf);
        Assert.Equal(2, reach.NothingWasAssessed);
        Assert.Contains("instrumentation gap", reach.Finding);

        // The sentence must say what a reader cannot infer from the count: that Daydream CANNOT see
        // this work, not that it happened not to. "no patterns observed" is the reading being
        // displaced, so the finding must not be mistakable for it.
        Assert.Contains("cannot see this work", reach.Finding);
        Assert.DoesNotContain("no patterns", reach.Finding, StringComparison.OrdinalIgnoreCase);
    }

    /// <summary>One observable episode means Daydream is not deaf, however many are not.</summary>
    /// <remarks>
    /// Deafness is about capability, not proportion. A repository where Daydream works and most work
    /// is uninstrumented still has a reported shortfall — but it is a different, smaller statement,
    /// and calling it deafness would spend the word before it is needed.
    /// </remarks>
    [Fact]
    public void OneObservableEpisodeMeansNotDeafButStillReported()
    {
        var observable = Episode("ep-1");
        Score(observable, Episode("ep-2", WeaveVerdict.NotScored, floors: [], rubric: null));

        // Actually recorded, so `Missing` is zero and the shortfall is what remains to report. A
        // first draft of this test skipped the write and asserted the shortfall message; the probe
        // correctly reported the MISSING observation instead, which outranks it. The precedence was
        // right and the test was wrong.
        new DaydreamRecorder(_record, () => At).Observe(observable);

        var reach = Probe().Probe();

        Assert.False(reach.Deaf);
        Assert.Equal(1, reach.WouldRecord);
        Assert.Equal(0, reach.Missing);
        Assert.Contains("1 of 2 scored episode(s) carried nothing to assess", reach.Finding);
    }

    // ------------------------------------------------ measured against the record, not the writer

    /// <summary>
    /// The expected observation reaching the record is what closes the loop.
    /// </summary>
    /// <remarks>
    /// The probe classifies the STORE and compares against the FILE. Two sources, neither of them
    /// the writer reporting on itself — which is the shape <c>FreshnessProber</c> was built to
    /// escape after a staleness metric measured against the daemon's own last event and let a dead
    /// watcher read as perfectly fresh.
    /// </remarks>
    [Fact]
    public void AnObservationThatReachedTheRecordIsNotMissing()
    {
        var episode = Episode("ep-1");
        Score(episode);
        new DaydreamRecorder(_record, () => At).Observe(episode);

        var reach = Probe().Probe();

        Assert.Equal(1, reach.WouldRecord);
        Assert.Equal(1, reach.ObservationsInRecord);
        Assert.Equal(0, reach.Missing);
        Assert.Null(reach.Finding);
    }

    /// <summary>
    /// A pattern the classification expected and the record does not hold is reported as missing.
    /// </summary>
    /// <remarks>
    /// The write silently failing is the failure a self-referential counter cannot see: the recorder
    /// would have returned <c>RecordUnavailable</c> to a caller that discards it, and every later
    /// read would show a record that is simply smaller than the truth.
    /// </remarks>
    [Fact]
    public void AnExpectedObservationAbsentFromTheRecordIsReportedMissing()
    {
        Score(Episode("ep-1"), Episode("ep-2"));

        var reach = Probe().Probe();

        Assert.Equal(2, reach.WouldRecord);
        Assert.Equal(0, reach.ObservationsInRecord);
        Assert.Equal(2, reach.Missing);
        Assert.Contains("missing from the record", reach.Finding);
    }

    /// <summary>
    /// A re-observed episode is one observation, so a duplicate cannot mask a shortfall.
    /// </summary>
    /// <remarks>
    /// Counting rows rather than distinct episodes would let a union merge across two worktrees
    /// manufacture a surplus and hide a genuine missing observation behind it — the record growing
    /// while the truth shrinks.
    /// </remarks>
    [Fact]
    public void ADuplicatedObservationDoesNotMaskAMissingOne()
    {
        var first = Episode("ep-1");
        Score(first, Episode("ep-2"));

        var recorder = new DaydreamRecorder(_record, () => At);
        recorder.Observe(first);
        recorder.Observe(first);

        var reach = Probe().Probe();

        Assert.Equal(1, reach.ObservationsInRecord);
        Assert.Equal(1, reach.Missing);
    }

    /// <summary>
    /// A record holding more than this store can account for is a count, not a fault.
    /// </summary>
    /// <remarks>
    /// <para><b>Found by mutation, and it was UNCOVERED.</b> Removing the <c>Math.Max(0, …)</c> from
    /// <c>Missing</c> reddened nothing, which said the negative case had never been considered.</para>
    ///
    /// <para>It is not an impossible state — it is the <i>normal</i> one for a fresh clone. The
    /// Daydream record is committed and travels with the repository; the scorecards live in a
    /// per-workspace store that starts empty. So a clone opens with a full record and no scored
    /// episodes behind it, and clamping that to zero folded a real state into "fine", which is the
    /// mistake this probe exists to correct.</para>
    ///
    /// <para>It stays a count and never a finding, because it fires for every clone and a warning
    /// that fires for everyone warns no one.</para>
    /// </remarks>
    [Fact]
    public void ARecordFromAnotherStoreIsCountedAndNotReportedAsAFault()
    {
        // A clone's shape: the record has an observation, the store has never scored anything.
        _record.Append(new DaydreamObservation(
            "obs-1",
            new DaydreamSignature("implement", ScoreSchema.Weave1Version, WeaveVerdict.Blocked, "Correctness", ""),
            "ep-elsewhere",
            At));

        var reach = Probe().Probe();

        Assert.Equal(1, reach.ObservationsInRecord);
        Assert.Equal(0, reach.WouldRecord);
        Assert.Equal(0, reach.Missing);
        Assert.Equal(1, reach.Unaccounted);
        Assert.Null(reach.Finding);
    }

    /// <summary>
    /// No repository outranks every other finding, and says so in its own words.
    /// </summary>
    /// <remarks>
    /// Reporting "2 patterns missing from the record" when there is no record to be missing from
    /// would send a reader looking for a write failure instead of a workspace.
    /// </remarks>
    [Fact]
    public void AnUnavailableRecordIsReportedAheadOfAnythingElse()
    {
        Score(Episode("ep-1"));

        var reach = Probe(DaydreamRepositoryRecord.Absent).Probe();

        Assert.Contains("No repository is open", reach.Finding);
        Assert.DoesNotContain("missing from the record", reach.Finding);
    }

    // ------------------------------------------------------------- one definition, not two

    /// <summary>
    /// The probe and the recorder agree on every episode, because they share the judgement.
    /// </summary>
    /// <remarks>
    /// The property that matters most and the one a count-based test would not check. If
    /// <c>DeclineReason</c> were re-implemented here the two would drift, and a probe that disagrees
    /// with the writer reports the wrong silence — which is worse than no probe, because it is
    /// believed.
    /// </remarks>
    [Fact]
    public void TheProbeAgreesWithTheRecorderOnEveryEpisode()
    {
        ScoredEpisode[] episodes =
        [
            Episode("ep-1"),
            Episode("ep-2", WeaveVerdict.Scored, floors: [], rubric: 4),
            Episode("ep-3", WeaveVerdict.NotScored, floors: [], rubric: null),
            Episode("ep-4", WeaveVerdict.Blocked, floors: [FloorDomain.Security], rubric: 0),
        ];
        Score(episodes);

        var recorder = new DaydreamRecorder(_record, () => At);
        var recorded = episodes.Count(e => recorder.Observe(e) == DaydreamObservationOutcome.Recorded);

        var reach = Probe().Probe();

        Assert.Equal(recorded, reach.WouldRecord);
        Assert.Equal(recorded, reach.ObservationsInRecord);
        Assert.Equal(0, reach.Missing);
    }
}
