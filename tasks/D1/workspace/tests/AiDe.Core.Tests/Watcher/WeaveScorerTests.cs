using AiDe.Core.Watcher;

namespace AiDe.Core.Tests.Watcher;

/// <summary>
/// LK-WEAVE-01..N - the deterministic Weave (design-watcher-weave-score, slice 5). The claims: a closed
/// episode is scored on the four deterministic dimensions (observed weight 70); the two advisory ones are
/// excluded, not faked; a hard floor trips Blocked and suppresses the headline; a missing
/// goal/done/verification path is Not Scored; a Partial headline never rescales to 0-100; and Coverage is
/// separate from points. This is where done_when becomes measured (Focus + Outcome).
/// </summary>
public sealed class WeaveScorerTests
{
    private static readonly DateTimeOffset At = DateTimeOffset.UnixEpoch;
    private static readonly WeaveScorer Scorer = new();
    private static readonly TimeProvider Time = new FixedTimeProvider(At);

    private static WorkEpisode ClosedEpisode(
        string goal = "wire the receiver", string done = "a span ingests and the suite is green",
        EpisodeOutcome outcome = EpisodeOutcome.Completed, bool closed = true)
        => new("ep-1", "s1", new EpisodeGeneration(1), new Goal(goal), new DoneCondition(done), null,
            At, closed ? At.AddMinutes(5) : null, closed ? outcome : null);

    private static DeterministicEpisodeSignals Clean(
        bool hasVerificationPath = true,
        bool? acceptanceMet = true,
        bool verificationExecuted = true,
        bool regression = false,
        FloorDomain[]? blockers = null,
        int actionsAfterDone = 0,
        bool premature = false,
        int reqGuidance = 3, int satGuidance = 3,
        int reqCoord = 2, int obsCoord = 2,
        bool coverageCalibrated = true, int reqSignals = 10, int obsSignals = 9)
        => new(hasVerificationPath, acceptanceMet, verificationExecuted, regression,
            new HashSet<FloorDomain>(blockers ?? []), actionsAfterDone, premature,
            reqGuidance, satGuidance, reqCoord, obsCoord, coverageCalibrated, reqSignals, obsSignals);

    private static DimensionAssessment Of(Scorecard card, ScoreDimension dim)
        => card.Assessments.Single(a => a.Dimension == dim);

    // --- the clean deterministic case ---------------------------------------------------------

    [Fact]
    public void Clean_ClosedEpisode_IsPartial_WithObservedWeight70()
    {
        var card = Scorer.Score(ClosedEpisode(), Clean(), Time);

        Assert.Equal(WeaveVerdict.Partial, card.Verdict);
        Assert.Equal("Partial: 70 / 70 observed", card.Headline); // matches the spec's "58 / 70 observed" shape
        Assert.Empty(card.TrippedFloors);
        Assert.Equal(30, Of(card, ScoreDimension.OutcomeIntegrity).EarnedPoints);
        Assert.Equal(15, Of(card, ScoreDimension.FocusAndTermination).EarnedPoints);
        Assert.Equal(15, Of(card, ScoreDimension.GuidanceAdherence).EarnedPoints);
        Assert.Equal(10, Of(card, ScoreDimension.CoordinationAndLearning).EarnedPoints);
    }

    [Fact]
    public void AdvisoryDimensions_AreExcluded_NotFakedZero()
    {
        var card = Scorer.Score(ClosedEpisode(), Clean(), Time);

        foreach (var dim in new[] { ScoreDimension.EvidenceDiscipline, ScoreDimension.SolutionEconomy })
        {
            var a = Of(card, dim);
            Assert.Equal(AssessmentPosture.Advisory, a.Posture);
            Assert.Null(a.EarnedPoints); // excluded, never 0
            Assert.Null(a.Rubric0to4);
        }
    }

    [Fact]
    public void Partial_HeadlineDenominatorIsObservedWeight_NotRescaledTo100()
    {
        var card = Scorer.Score(ClosedEpisode(), Clean(), Time);

        Assert.Contains("/ 70 observed", card.Headline, StringComparison.Ordinal);
        Assert.DoesNotContain("/ 100", card.Headline, StringComparison.Ordinal);
    }

    // --- Not Scored gate (rule 5) -------------------------------------------------------------

    [Fact]
    public void NoGoal_IsNotScored()
    {
        var card = Scorer.Score(ClosedEpisode(goal: "   "), Clean(), Time);
        Assert.Equal(WeaveVerdict.NotScored, card.Verdict);
        Assert.Contains("no goal", card.Headline, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public void NoDoneCondition_IsNotScored()
    {
        var card = Scorer.Score(ClosedEpisode(done: ""), Clean(), Time);
        Assert.Equal(WeaveVerdict.NotScored, card.Verdict);
        Assert.Contains("done condition", card.Headline, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public void NoVerificationPath_IsNotScored()
    {
        var card = Scorer.Score(ClosedEpisode(), Clean(hasVerificationPath: false), Time);
        Assert.Equal(WeaveVerdict.NotScored, card.Verdict);
        Assert.Contains("verification path", card.Headline, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public void OpenEpisode_IsNotScored()
    {
        var card = Scorer.Score(ClosedEpisode(closed: false), Clean(), Time);
        Assert.Equal(WeaveVerdict.NotScored, card.Verdict);
        Assert.Contains("not closed", card.Headline, StringComparison.OrdinalIgnoreCase);
    }

    // --- hard floors (rules 6-7) --------------------------------------------------------------

    [Theory]
    [InlineData(FloorDomain.Security)]
    [InlineData(FloorDomain.Privacy)]
    [InlineData(FloorDomain.DataIntegrity)]
    [InlineData(FloorDomain.EvaluatorIntegrity)]
    [InlineData(FloorDomain.Correctness)]
    public void AnUnresolvedFloorBlocker_TripsBlocked_AndSuppressesTheHeadline(FloorDomain domain)
    {
        var card = Scorer.Score(ClosedEpisode(), Clean(blockers: [domain]), Time);

        Assert.Equal(WeaveVerdict.Blocked, card.Verdict);
        Assert.Contains(domain, card.TrippedFloors);
        Assert.Contains("Blocked", card.Headline, StringComparison.Ordinal);
        Assert.DoesNotContain("observed", card.Headline, StringComparison.Ordinal); // numeric suppressed
    }

    [Fact]
    public void AcceptanceNotMet_TripsCorrectnessFloor()
    {
        var card = Scorer.Score(ClosedEpisode(), Clean(acceptanceMet: false), Time);
        Assert.Equal(WeaveVerdict.Blocked, card.Verdict);
        Assert.Contains(FloorDomain.Correctness, card.TrippedFloors);
    }

    [Fact]
    public void Regression_TripsCorrectnessFloor()
    {
        var card = Scorer.Score(ClosedEpisode(), Clean(regression: true), Time);
        Assert.Equal(WeaveVerdict.Blocked, card.Verdict);
        Assert.Contains(FloorDomain.Correctness, card.TrippedFloors);
    }

    [Fact]
    public void RequiredVerificationNotExecuted_TripsCorrectnessFloor()
    {
        var card = Scorer.Score(ClosedEpisode(), Clean(verificationExecuted: false), Time);
        Assert.Equal(WeaveVerdict.Blocked, card.Verdict);
        Assert.Contains(FloorDomain.Correctness, card.TrippedFloors);
    }

    [Fact]
    public void UnknownAcceptance_DoesNotTripCorrectness_ButOutcomeIsNotRecorded()
    {
        // null acceptance is unknown, not failed - it must not trip the floor; the Outcome dimension
        // is honestly Not Recorded, and the observed weight drops by Outcome's 30.
        var card = Scorer.Score(ClosedEpisode(), Clean(acceptanceMet: null), Time);

        Assert.Equal(WeaveVerdict.Partial, card.Verdict);
        Assert.Empty(card.TrippedFloors);
        Assert.Equal(AssessmentPosture.NotRecorded, Of(card, ScoreDimension.OutcomeIntegrity).Posture);
        Assert.Contains("/ 40 observed", card.Headline, StringComparison.Ordinal); // 70 - 30
    }

    // --- dimension rubrics (done_when made measurable) ----------------------------------------

    [Fact]
    public void Outcome_NotCompleted_StepsDownTheRubric()
    {
        var card = Scorer.Score(ClosedEpisode(outcome: EpisodeOutcome.Abandoned), Clean(), Time);
        Assert.Equal(2, Of(card, ScoreDimension.OutcomeIntegrity).Rubric0to4); // 4 - 2 (not completed)
    }

    [Fact]
    public void Focus_WorkAfterDoneCondition_ReducesTheRubric_TheDriftPenalty()
    {
        var card = Scorer.Score(ClosedEpisode(), Clean(actionsAfterDone: 3), Time);
        Assert.Equal(2, Of(card, ScoreDimension.FocusAndTermination).Rubric0to4); // 4 - 2 drift (PACK-O)
    }

    [Fact]
    public void Focus_PrematureCompletion_ReducesTheRubric_TheUnderValidationPenalty()
    {
        var card = Scorer.Score(ClosedEpisode(), Clean(premature: true), Time);
        Assert.Equal(2, Of(card, ScoreDimension.FocusAndTermination).Rubric0to4);
    }

    [Fact]
    public void Guidance_IsProportionalToSatisfiedOverRequired()
    {
        var card = Scorer.Score(ClosedEpisode(), Clean(reqGuidance: 4, satGuidance: 2), Time);
        Assert.Equal(2, Of(card, ScoreDimension.GuidanceAdherence).Rubric0to4); // round(4 * 2/4)
    }

    [Fact]
    public void Guidance_NoTriggersRequired_IsNotRecorded()
    {
        var card = Scorer.Score(ClosedEpisode(), Clean(reqGuidance: 0, satGuidance: 0), Time);
        Assert.Equal(AssessmentPosture.NotRecorded, Of(card, ScoreDimension.GuidanceAdherence).Posture);
        Assert.Contains("/ 55 observed", card.Headline, StringComparison.Ordinal); // 70 - 15
    }

    [Fact]
    public void Coordination_NoSignalsRequired_IsNotRecorded()
    {
        var card = Scorer.Score(ClosedEpisode(), Clean(reqCoord: 0, obsCoord: 0), Time);
        Assert.Equal(AssessmentPosture.NotRecorded, Of(card, ScoreDimension.CoordinationAndLearning).Posture);
    }

    // --- Evidence Coverage (rules 3-4) --------------------------------------------------------

    [Fact]
    public void Coverage_Uncalibrated_IsNotRecorded()
    {
        var card = Scorer.Score(ClosedEpisode(), Clean(coverageCalibrated: false), Time);
        Assert.Null(card.Coverage); // Not Recorded, never 100% and never 0
    }

    [Fact]
    public void Coverage_Calibrated_IsObservedOverRequired_SeparateFromPoints()
    {
        var card = Scorer.Score(ClosedEpisode(), Clean(coverageCalibrated: true, reqSignals: 10, obsSignals: 7), Time);
        Assert.Equal(new EvidenceCoverage(7, 10), card.Coverage);
        Assert.Contains("70 / 70 observed", card.Headline, StringComparison.Ordinal); // coverage did not change points
    }

    // --- contract + composition ---------------------------------------------------------------

    [Fact]
    public void SchemaVersion_IsPinned() // A6: a bump is a deliberate, gated change
        => Assert.Equal("weave/1", ScoreSchema.Weave1.Version);

    [Fact]
    public void Schema_TotalWeightIs100_WithSeventyDeterministic()
    {
        Assert.Equal(100, ScoreSchema.Weave1.TotalWeight);
        Assert.Equal(70, ScoreSchema.Weave1.Dimensions.Where(d => d.Posture == AssessmentPosture.Deterministic).Sum(d => d.Weight));
    }

    [Fact]
    public void Composition_ScoresARealClosedEpisode_FromTheService()
    {
        var store = new InMemoryWatcherObservationStore();
        var clock = new FakeMonotonicClock();
        var registrar = new TrustedRegistrar(store, new SequentialCapabilityFactory(), clock, () => "s1");
        var svc = new WorkEpisodeService(store, registrar, new FixedTimeProvider(At), () => "ep-real");
        var session = registrar.Register(WatcherFixtures.Binding());

        var opened = svc.Open(session.SessionId, session.Capability, new Goal("do X"), new DoneCondition("X done"));
        var closed = svc.Close(opened.EpisodeId, session.Capability, EpisodeOutcome.Completed);

        var card = Scorer.Score(closed, Clean(), Time);

        Assert.Equal("ep-real", card.EpisodeId);
        Assert.Equal(WeaveVerdict.Partial, card.Verdict);
        Assert.Equal("Partial: 70 / 70 observed", card.Headline);
    }
}
