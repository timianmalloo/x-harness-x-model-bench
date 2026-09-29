using AiDe.Core.Watcher;

namespace AiDe.Core.Tests.Watcher;

/// <summary>
/// LK-ADV-EVAL-01..14 - the local advisory evaluator and the egress/credential guard (conn-3, ADR-0024 credential-backed-grading-egress).
/// The claims: the local heuristic scores the two advisory dimensions deterministically from a quarantined
/// evidence token list with a conservative (never optimistic) default for absent tokens, needs no egress
/// or credential, and refuses a deterministic dimension (rule 8); and the guard enforces default-deny
/// egress (LK-0003) THEN a present credential (LK-0002) before an egressing evaluator can run, never
/// calling the inner evaluator when either check fails.
/// </summary>
public sealed class AdvisoryEvaluatorsTests
{
    private static readonly DateTimeOffset At = DateTimeOffset.UnixEpoch;

    private static WorkEpisode Episode() => new(
        "ep-1", "s1", new EpisodeGeneration(1), new Goal("do X"), new DoneCondition("X done"),
        null, At, At.AddMinutes(5), EpisodeOutcome.Completed);

    // ---- LocalHeuristicAdvisoryEvaluator ------------------------------------------------------------

    [Fact]
    public void Local_EvidenceDiscipline_FullEvidence_ScoresTop()
    {
        var e = new LocalHeuristicAdvisoryEvaluator();

        var a = e.Evaluate(ScoreDimension.EvidenceDiscipline, Episode(), "verification=executed; coverage=9/10");

        Assert.Equal(ScoreDimension.EvidenceDiscipline, a.Dimension);
        Assert.Equal(4, a.Rubric0to4);       // 2 (verification) + 2 (coverage >= 0.9)
        Assert.Equal("local-heuristic/1", a.EvaluatorVersion);
    }

    [Fact]
    public void Local_EvidenceDiscipline_NoVerification_LowCoverage_ScoresZero()
    {
        var e = new LocalHeuristicAdvisoryEvaluator();

        var a = e.Evaluate(ScoreDimension.EvidenceDiscipline, Episode(), "verification=none; coverage=1/10");

        Assert.Equal(0, a.Rubric0to4);
    }

    [Fact]
    public void Local_EvidenceDiscipline_PartialCoverage_ScoresBetween()
    {
        var e = new LocalHeuristicAdvisoryEvaluator();

        var a = e.Evaluate(ScoreDimension.EvidenceDiscipline, Episode(), "verification=executed; coverage=6/10");

        Assert.Equal(3, a.Rubric0to4);       // 2 + 1 (coverage >= 0.5)
    }

    [Fact]
    public void Local_AbsentTokens_ScoreConservatively_NotOptimistically()
    {
        var e = new LocalHeuristicAdvisoryEvaluator();

        // An empty evidence string must not be read as "all good": a missing signal lowers, never raises.
        var evidence = e.Evaluate(ScoreDimension.EvidenceDiscipline, Episode(), "");
        var economy = e.Evaluate(ScoreDimension.SolutionEconomy, Episode(), "");

        Assert.Equal(0, evidence.Rubric0to4);
        // Economy: absent actions_after_done => 0 band => 2; absent premature => not premature => +1;
        // absent reuse => 0. So a bare episode is "no evidence of waste" = 3, but never the full 4.
        Assert.Equal(3, economy.Rubric0to4);
        Assert.True(economy.Rubric0to4 < 4);
    }

    [Fact]
    public void Local_SolutionEconomy_LeanRun_ScoresTop()
    {
        var e = new LocalHeuristicAdvisoryEvaluator();

        var a = e.Evaluate(ScoreDimension.SolutionEconomy, Episode(),
            "actions_after_done=0; premature=false; reuse=high");

        Assert.Equal(4, a.Rubric0to4);       // 2 + 1 + 1
    }

    [Fact]
    public void Local_SolutionEconomy_WastefulAndPremature_ScoresLow()
    {
        var e = new LocalHeuristicAdvisoryEvaluator();

        var a = e.Evaluate(ScoreDimension.SolutionEconomy, Episode(),
            "actions_after_done=9; premature=true; reuse=none");

        Assert.Equal(0, a.Rubric0to4);
    }

    [Theory]
    [InlineData(ScoreDimension.OutcomeIntegrity)]
    [InlineData(ScoreDimension.FocusAndTermination)]
    [InlineData(ScoreDimension.GuidanceAdherence)]
    [InlineData(ScoreDimension.CoordinationAndLearning)]
    public void Local_ADeterministicDimension_IsRefused(ScoreDimension dimension)
    {
        var e = new LocalHeuristicAdvisoryEvaluator();

        var ex = Assert.Throws<WatcherException>(() => e.Evaluate(dimension, Episode(), "coverage=9/10"));

        Assert.Equal(WatcherErrorCodes.InvalidBinding, ex.Code);
    }

    [Fact]
    public void Local_IsDeterministic_StabilityTriviallyPasses()
    {
        var e = new LocalHeuristicAdvisoryEvaluator();
        const string evidence = "verification=executed; coverage=8/10";

        // Twenty repeats produce the identical band - the ADR-0019 advisory-evaluator-calibration stability gate's happy path.
        var bands = Enumerable.Range(0, 20)
            .Select(_ => e.Evaluate(ScoreDimension.EvidenceDiscipline, Episode(), evidence).Rubric0to4)
            .ToArray();
        var stability = EvaluatorStability.Of(bands);

        Assert.True(stability.Passes);
        Assert.All(bands, b => Assert.Equal(bands[0], b));
    }

    // ---- EgressGuardedAdvisoryEvaluator -------------------------------------------------------------

    private sealed class SpyEvaluator : IAdvisoryEvaluator
    {
        public bool WasCalled { get; private set; }

        public string EvaluatorVersion => "cloud-judge/1";

        public AdvisoryAssessment Evaluate(ScoreDimension dimension, WorkEpisode episode, string evidence)
        {
            WasCalled = true;
            return new AdvisoryAssessment(dimension, 4, "cloud says great", "cloud:ptr", EvaluatorVersion);
        }
    }

    private sealed class PresentCredential : IAdvisoryCredentialSource
    {
        public bool HasCredential => true;
    }

    [Fact]
    public void Guard_EgressBlocked_IsDenied_AndInnerNeverRuns()
    {
        var spy = new SpyEvaluator();
        var guard = new EgressGuardedAdvisoryEvaluator(spy, new EgressGate(), "advisory/cloud", new PresentCredential());

        var ex = Assert.Throws<WatcherException>(() =>
            guard.Evaluate(ScoreDimension.EvidenceDiscipline, Episode(), "coverage=9/10"));

        Assert.Equal(WatcherErrorCodes.EgressDenied, ex.Code);   // LK-0003, default-deny
        Assert.False(spy.WasCalled);                              // the model call never happened
    }

    [Fact]
    public void Guard_EgressAllowed_ButNoCredential_IsInvalidBinding_AndInnerNeverRuns()
    {
        var spy = new SpyEvaluator();
        var gate = new EgressGate();
        gate.OptIn("advisory/cloud");
        var guard = new EgressGuardedAdvisoryEvaluator(spy, gate, "advisory/cloud", new NoCredential());

        var ex = Assert.Throws<WatcherException>(() =>
            guard.Evaluate(ScoreDimension.EvidenceDiscipline, Episode(), "coverage=9/10"));

        Assert.Equal(WatcherErrorCodes.InvalidBinding, ex.Code);  // LK-0002, no credential
        Assert.False(spy.WasCalled);
    }

    [Fact]
    public void Guard_EgressAllowed_WithCredential_DelegatesToInner()
    {
        var spy = new SpyEvaluator();
        var gate = new EgressGate();
        gate.OptIn("advisory/cloud");
        var guard = new EgressGuardedAdvisoryEvaluator(spy, gate, "advisory/cloud", new PresentCredential());

        var a = guard.Evaluate(ScoreDimension.EvidenceDiscipline, Episode(), "coverage=9/10");

        Assert.True(spy.WasCalled);
        Assert.Equal("cloud says great", a.Rationale);
        Assert.Equal("cloud-judge/1", guard.EvaluatorVersion);   // version delegates to the inner
    }

    [Fact]
    public void Guard_RevokedPath_ReturnsToDenied()
    {
        var spy = new SpyEvaluator();
        var gate = new EgressGate();
        gate.OptIn("advisory/cloud");
        gate.Revoke("advisory/cloud");
        var guard = new EgressGuardedAdvisoryEvaluator(spy, gate, "advisory/cloud", new PresentCredential());

        var ex = Assert.Throws<WatcherException>(() =>
            guard.Evaluate(ScoreDimension.EvidenceDiscipline, Episode(), "coverage=9/10"));

        Assert.Equal(WatcherErrorCodes.EgressDenied, ex.Code);
        Assert.False(spy.WasCalled);
    }
}
