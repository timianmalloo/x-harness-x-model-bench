using AiDe.Core.Watcher;

namespace AiDe.Core.Tests.Watcher;

/// <summary>
/// LK-ADV-01..N - the advisory calibration gates + gated fold (design-watcher-advisory-grader, slice 7).
/// The claims (spec rules 8-9, ADR-0019 advisory-evaluator-calibration): quadratic weighted kappa and stability decide qualification; an
/// advisory dimension enters points only when its evaluator version has qualified; and advisory never
/// overrides a deterministic Not Scored or Blocked result.
/// </summary>
public sealed class AdvisoryScoringTests
{
    private static readonly DateTimeOffset At = DateTimeOffset.UnixEpoch;
    private const string TaskClass = "refactor";

    // --- Quadratic Weighted Kappa -------------------------------------------------------------

    [Fact]
    public void Qwk_PerfectAgreement_IsOne()
        => Assert.Equal(1.0, QuadraticWeightedKappa.Compute([0, 1, 2, 3, 4], [0, 1, 2, 3, 4]), 6);

    [Fact]
    public void Qwk_MaximalReverseDisagreement_IsMinusOne()
        => Assert.Equal(-1.0, QuadraticWeightedKappa.Compute([0, 0, 4, 4], [4, 4, 0, 0]), 6);

    [Fact]
    public void Qwk_HighAgreementWithOneOffByOne_IsAboveTheFloor()
        => Assert.True(QuadraticWeightedKappa.Compute([0, 1, 2, 3, 4, 0, 1, 2, 3, 4], [1, 1, 2, 3, 4, 0, 1, 2, 3, 4]) >= 0.75);

    [Fact]
    public void Qwk_EmptyVectors_IsOne()
        => Assert.Equal(1.0, QuadraticWeightedKappa.Compute([], []));

    [Fact]
    public void Qwk_LengthMismatch_Throws()
        => Assert.Throws<ArgumentException>(() => QuadraticWeightedKappa.Compute([0, 1], [0]));

    // --- Stability ----------------------------------------------------------------------------

    [Fact]
    public void Stability_AllSame_Passes()
        => Assert.True(EvaluatorStability.Of([3, 3, 3, 3, 3]).Passes);

    [Fact]
    public void Stability_NineteenOfTwentyInBand_SpreadOne_Passes()
    {
        var repeats = Enumerable.Repeat(3, 19).Append(4).ToList(); // 95% in band, spread 1
        Assert.True(EvaluatorStability.Of(repeats).Passes);
    }

    [Fact]
    public void Stability_TooMuchDrift_Fails()
        => Assert.False(EvaluatorStability.Of([2, 3, 4, 3]).Passes); // spread 2

    [Fact]
    public void Stability_BelowNinetyFivePercentInBand_Fails()
    {
        var repeats = Enumerable.Repeat(3, 18).Concat([4, 4]).ToList(); // 90% in band
        Assert.False(EvaluatorStability.Of(repeats).Passes);
    }

    [Fact]
    public void Stability_Empty_Fails()
        => Assert.False(EvaluatorStability.Of([]).Passes);

    // --- Calibration verdict (all three gates) ------------------------------------------------

    [Fact]
    public void Qualify_AllGatesPass_IsQualified()
    {
        var verdict = AdvisoryCalibration.Qualify(
            stabilityRepeats: [4, 4, 4, 4, 4],
            evaluatorRatings: [4, 3, 2, 1, 0],
            humanRatings: [4, 3, 2, 1, 0],
            counterMetricsHeldNoWorse: true);

        Assert.True(verdict.Qualified);
        Assert.Empty(verdict.Reasons);
    }

    [Fact]
    public void Qualify_Unstable_IsRejectedWithReason()
    {
        var verdict = AdvisoryCalibration.Qualify([2, 3, 4], [4, 3, 2], [4, 3, 2], true);
        Assert.False(verdict.Qualified);
        Assert.Contains(verdict.Reasons, r => r.Contains("unstable", StringComparison.OrdinalIgnoreCase));
    }

    [Fact]
    public void Qualify_LowHumanAgreement_IsRejectedWithReason()
    {
        var verdict = AdvisoryCalibration.Qualify([3, 3, 3], [0, 0, 4, 4], [4, 4, 0, 0], true);
        Assert.False(verdict.Qualified);
        Assert.Contains(verdict.Reasons, r => r.Contains("QWK", StringComparison.OrdinalIgnoreCase));
    }

    [Fact]
    public void Qualify_CounterMetricsWorsened_IsRejectedAsGaming()
    {
        var verdict = AdvisoryCalibration.Qualify([4, 4, 4], [4, 4, 4], [4, 4, 4], counterMetricsHeldNoWorse: false);
        Assert.False(verdict.Qualified);
        Assert.Contains(verdict.Reasons, r => r.Contains("gaming", StringComparison.OrdinalIgnoreCase));
    }

    // --- gated fold into the Weave ------------------------------------------------------------

    private static WorkEpisode ClosedEpisode()
        => new("ep-1", "s1", new EpisodeGeneration(1), new Goal("do X"), new DoneCondition("X done"), null,
            At, At.AddMinutes(5), EpisodeOutcome.Completed);

    private static DeterministicEpisodeSignals Clean(FloorDomain[]? blockers = null, bool hasVerification = true)
        => new(hasVerification, true, true, false, new HashSet<FloorDomain>(blockers ?? []),
            0, false, 3, 3, 2, 2, true, 10, 9);

    private static AdvisoryAssessment Adv(ScoreDimension dim, int rubric, string version = "grader/1")
        => new(dim, rubric, "well-reasoned", "ep-1#evidence", version);

    private static CalibrationRegistry Registry(bool qualifyGrader)
    {
        var registry = new CalibrationRegistry();
        if (qualifyGrader)
        {
            registry.Qualify("grader/1", TaskClass, ScoreSchema.Weave1.Version);
        }

        return registry;
    }

    [Fact]
    public void Fold_QualifiedAdvisory_AddsPoints_AndCanReachFullyScored()
    {
        var scorer = new AdvisoryWeaveScorer();
        var advisory = new[] { Adv(ScoreDimension.EvidenceDiscipline, 4), Adv(ScoreDimension.SolutionEconomy, 4) };

        var card = scorer.Score(ClosedEpisode(), Clean(), advisory, Registry(qualifyGrader: true), TaskClass, new FixedTimeProvider(At));

        Assert.Equal(WeaveVerdict.Scored, card.Verdict);
        Assert.Equal("100 / 100", card.Headline); // 70 deterministic + 15 + 15 advisory
    }

    [Fact]
    public void Fold_UnqualifiedAdvisory_StaysExcluded()
    {
        var scorer = new AdvisoryWeaveScorer();
        var advisory = new[] { Adv(ScoreDimension.EvidenceDiscipline, 4), Adv(ScoreDimension.SolutionEconomy, 4) };

        var card = scorer.Score(ClosedEpisode(), Clean(), advisory, Registry(qualifyGrader: false), TaskClass, new FixedTimeProvider(At));

        Assert.Equal(WeaveVerdict.Partial, card.Verdict);
        Assert.Equal("Partial: 70 / 70 observed", card.Headline); // advisory excluded (rule 9)
    }

    [Fact]
    public void Fold_OneQualifiedOneNot_AddsOnlyTheQualifiedDimension()
    {
        var scorer = new AdvisoryWeaveScorer();
        // Only Evidence discipline's evaluator qualifies; Solution economy uses a different, unqualified version.
        var advisory = new[] { Adv(ScoreDimension.EvidenceDiscipline, 4, "grader/1"), Adv(ScoreDimension.SolutionEconomy, 4, "grader/2") };

        var card = scorer.Score(ClosedEpisode(), Clean(), advisory, Registry(qualifyGrader: true), TaskClass, new FixedTimeProvider(At));

        Assert.Equal(WeaveVerdict.Partial, card.Verdict);
        Assert.Equal("Partial: 85 / 85 observed", card.Headline); // 70 + 15 (Evidence only)
    }

    [Fact]
    public void Fold_BlockedBase_IsReturnedUnchanged_AdvisoryNeverOverridesAFloor()
    {
        var scorer = new AdvisoryWeaveScorer();
        var advisory = new[] { Adv(ScoreDimension.EvidenceDiscipline, 4), Adv(ScoreDimension.SolutionEconomy, 4) };

        var card = scorer.Score(ClosedEpisode(), Clean(blockers: [FloorDomain.Security]), advisory,
            Registry(qualifyGrader: true), TaskClass, new FixedTimeProvider(At));

        Assert.Equal(WeaveVerdict.Blocked, card.Verdict); // rule 8: advisory cannot lift a floor
        Assert.Contains(FloorDomain.Security, card.TrippedFloors);
    }

    [Fact]
    public void Fold_NotScoredBase_IsReturnedUnchanged()
    {
        var scorer = new AdvisoryWeaveScorer();
        var advisory = new[] { Adv(ScoreDimension.EvidenceDiscipline, 4) };

        var card = scorer.Score(ClosedEpisode(), Clean(hasVerification: false), advisory,
            Registry(qualifyGrader: true), TaskClass, new FixedTimeProvider(At));

        Assert.Equal(WeaveVerdict.NotScored, card.Verdict);
    }
}
