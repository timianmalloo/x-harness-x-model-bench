using AiDe.Core.Watcher;

namespace AiDe.Core.Tests.Watcher;

/// <summary>
/// LK-SCORESVC-01..10 - the evidence composer + scoring service (conn-6). The claims: the composer maps
/// deterministic signals to the local evaluator's token vocabulary (omitting unobserved tokens so they
/// default conservatively, NG1); the service scores the four deterministic dimensions and persists the
/// ScoredEpisode so it reaches the Leaderboard; and the two advisory dimensions fold ONLY when the
/// evaluator's (version, taskClass, schemaVersion) is qualified in the registry (ADR-0019 advisory-evaluator-calibration, rule 8).
/// </summary>
public sealed class ScoringServiceTests
{
    private static readonly DateTimeOffset At = DateTimeOffset.UnixEpoch;
    private static readonly TimeProvider Clock = new FixedTimeProvider(At);

    private static WorkEpisode Episode(string id = "ep-1") => new(
        id, "s1", new EpisodeGeneration(1), new Goal("do X"), new DoneCondition("X done"),
        null, At, At.AddMinutes(5), EpisodeOutcome.Completed);

    // Clean signals: verification executed, coverage 9/10, no actions after done, not premature.
    private static DeterministicEpisodeSignals CleanSignals() => new(
        true, true, true, false, new HashSet<FloorDomain>(), 0, false, 3, 3, 2, 2, true, 10, 9);

    // ---- EvidenceComposer ---------------------------------------------------------------------------

    [Fact]
    public void EvidenceComposer_MapsCleanSignals_ToTokens()
    {
        var tokens = EvidenceComposer.Compose(CleanSignals());

        Assert.Contains("verification=executed", tokens);
        Assert.Contains("coverage=9/10", tokens);
        Assert.Contains("actions_after_done=0", tokens);
        Assert.Contains("premature=false", tokens);
    }

    [Fact]
    public void EvidenceComposer_NotExecuted_Premature_MapsConservatively()
    {
        var signals = CleanSignals() with { RequiredVerificationExecuted = false, PrematureCompletion = true, ActionsAfterDoneCondition = 5 };

        var tokens = EvidenceComposer.Compose(signals);

        Assert.Contains("verification=none", tokens);
        Assert.Contains("premature=true", tokens);
        Assert.Contains("actions_after_done=5", tokens);
    }

    [Fact]
    public void EvidenceComposer_RoundTripsThroughTheLocalEvaluator()
    {
        // The composed tokens must be exactly what the local heuristic reads: clean signals -> top evidence.
        var tokens = EvidenceComposer.Compose(CleanSignals());
        var a = new LocalHeuristicAdvisoryEvaluator().Evaluate(ScoreDimension.EvidenceDiscipline, Episode(), tokens);

        Assert.Equal(4, a.Rubric0to4); // verification executed (2) + coverage >= 0.9 (2)
    }

    // ---- ScoringService -----------------------------------------------------------------------------

    [Fact]
    public void ScoreAndRecord_NoEvaluator_PersistsDeterministicScorecard_AdvisoryExcluded()
    {
        var store = new InMemoryWatcherObservationStore();
        var svc = new ScoringService(store, Clock);

        var scored = svc.ScoreAndRecord(Episode(), CleanSignals(), "op1", "refactor", TestWorkspaces.Repo, "Claude Code", "Opus 4.8");

        Assert.Single(store.AllScoredEpisodes());
        Assert.Equal(WeaveVerdict.Partial, scored.Scorecard.Verdict);
        // The two advisory dimensions stay excluded (no evaluator supplied).
        var evidence = scored.Scorecard.Assessments.Single(x => x.Dimension == ScoreDimension.EvidenceDiscipline);
        Assert.Equal(AssessmentPosture.Advisory, evidence.Posture);
        Assert.Null(evidence.EarnedPoints);
    }

    [Fact]
    public void ScoreAndRecord_QualifiedEvaluator_FoldsAdvisory()
    {
        var store = new InMemoryWatcherObservationStore();
        var svc = new ScoringService(store, Clock);
        var evaluator = new LocalHeuristicAdvisoryEvaluator();
        var registry = new CalibrationRegistry();
        registry.Qualify(evaluator.EvaluatorVersion, "refactor", "weave/1");

        var scored = svc.ScoreAndRecord(Episode(), CleanSignals(), "op1", "refactor", TestWorkspaces.Repo, "Claude Code", "Opus 4.8", evaluator, registry);

        var evidence = scored.Scorecard.Assessments.Single(x => x.Dimension == ScoreDimension.EvidenceDiscipline);
        Assert.NotNull(evidence.EarnedPoints);                          // folded in (points earned)
        Assert.Contains("calibrated", evidence.Rationale, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public void ScoreAndRecord_UnqualifiedEvaluator_LeavesAdvisoryExcluded()
    {
        var store = new InMemoryWatcherObservationStore();
        var svc = new ScoringService(store, Clock);
        var evaluator = new LocalHeuristicAdvisoryEvaluator();
        var registry = new CalibrationRegistry(); // nothing qualified

        var scored = svc.ScoreAndRecord(Episode(), CleanSignals(), "op1", "refactor", TestWorkspaces.Repo, "H", "M", evaluator, registry);

        var evidence = scored.Scorecard.Assessments.Single(x => x.Dimension == ScoreDimension.EvidenceDiscipline);
        Assert.Equal(AssessmentPosture.Advisory, evidence.Posture);      // not qualified -> excluded
        Assert.Null(evidence.EarnedPoints);                             // no points folded in
    }

    [Fact]
    public void ScoreAndRecord_CarriesTheClassification()
    {
        var store = new InMemoryWatcherObservationStore();
        var svc = new ScoringService(store, Clock);

        var scored = svc.ScoreAndRecord(Episode(), CleanSignals(), "op7", "bugfix", TestWorkspaces.Repo, "Codex", "GPT");

        Assert.Equal("op7", scored.OperatorId);
        Assert.Equal("bugfix", scored.TaskClass);
        Assert.Equal("Codex", scored.Harness);
        Assert.Equal("GPT", scored.Model);
    }

    [Fact]
    public void ScoreAndRecord_PersistsEpisodes_ThatFeedTheLeaderboard()
    {
        // conn-1 + conn-6 end to end: scored episodes reach the Leaderboard composer the surface uses.
        var store = new InMemoryWatcherObservationStore();
        var svc = new ScoringService(store, Clock);
        for (var i = 0; i < 5; i++)
        {
            svc.ScoreAndRecord(Episode($"ep-{i}"), CleanSignals(), i % 2 == 0 ? "op1" : "op2", "refactor", TestWorkspaces.Repo, "Claude Code", "Opus 4.8");
        }

        var board = new LeaderboardComposer().Compose(store.AllScoredEpisodes(), new ScoreSegment(TestWorkspaces.Repo, "refactor", "weave/1"));

        var cell = board.Cell(LeaderboardFacet.HarnessModel, "Claude Code / Opus 4.8");
        Assert.NotNull(cell);
        Assert.Equal(5, cell!.Cohort);
        Assert.True(cell.Comparable);
    }

    [Fact]
    public void ScoreAndRecord_Recompute_ReplacesTheCard()
    {
        var store = new InMemoryWatcherObservationStore();
        var svc = new ScoringService(store, Clock);
        svc.ScoreAndRecord(Episode(), CleanSignals(), "op1", "refactor", TestWorkspaces.Repo);

        // Re-score the same episode with a floor tripped -> the persisted card is replaced (a cache refresh).
        var blocked = CleanSignals() with { UnresolvedFloorBlockers = new HashSet<FloorDomain> { FloorDomain.Correctness } };
        var second = svc.ScoreAndRecord(Episode(), blocked, "op1", "refactor", TestWorkspaces.Repo);

        Assert.Single(store.AllScoredEpisodes());
        Assert.Equal(WeaveVerdict.Blocked, second.Scorecard.Verdict);
        Assert.Equal(WeaveVerdict.Blocked, store.FindScoredEpisode("ep-1")!.Scorecard.Verdict);
    }
}
