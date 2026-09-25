using System.Globalization;

namespace AiDe.Core.Watcher;

/// <summary>The six Weave dimensions (spec §"Weave Score"). Four carry deterministic signals; two are advisory.</summary>
public enum ScoreDimension
{
    OutcomeIntegrity,
    FocusAndTermination,
    EvidenceDiscipline,
    GuidanceAdherence,
    SolutionEconomy,
    CoordinationAndLearning,
}

/// <summary>The canonical hard floors (spec rule 6). A trip in any of these produces a Blocked verdict.</summary>
public enum FloorDomain { Correctness, Security, Privacy, DataIntegrity, EvaluatorIntegrity }

/// <summary>How a dimension was assessed. An advisory or un-signalled dimension is NotRecorded, never a fake 0.</summary>
public enum AssessmentPosture { Deterministic, Advisory, NotRecorded }

/// <summary>The honest verdict of a Scorecard.</summary>
public enum WeaveVerdict { Scored, Partial, Blocked, NotScored }

/// <summary>One dimension's weight and posture within a versioned score schema.</summary>
public sealed record DimensionWeight(ScoreDimension Dimension, int Weight, AssessmentPosture Posture);

/// <summary>
/// A versioned score schema (spec rule 1/13; A6 - a change is a gated contract change). <c>weave/1</c>
/// pins the four deterministic dimensions (Outcome 30 · Focus 15 · Guidance 15 · Coordination 10 =
/// observed weight 70) and the two advisory ones (Evidence 15 · Economy 15 = 30), which are excluded
/// from points until the grader passes its calibration gates (ADR-0019 advisory-evaluator-calibration, slice 7).
/// </summary>
public sealed class ScoreSchema
{
    public const string Weave1Version = "weave/1";

    private ScoreSchema(string version, IReadOnlyList<DimensionWeight> dimensions)
    {
        Version = version;
        Dimensions = dimensions;
    }

    public string Version { get; }

    public IReadOnlyList<DimensionWeight> Dimensions { get; }

    public int TotalWeight => Dimensions.Sum(d => d.Weight);

    public static ScoreSchema Weave1 { get; } = new(Weave1Version,
    [
        new DimensionWeight(ScoreDimension.OutcomeIntegrity, 30, AssessmentPosture.Deterministic),
        new DimensionWeight(ScoreDimension.FocusAndTermination, 15, AssessmentPosture.Deterministic),
        new DimensionWeight(ScoreDimension.GuidanceAdherence, 15, AssessmentPosture.Deterministic),
        new DimensionWeight(ScoreDimension.CoordinationAndLearning, 10, AssessmentPosture.Deterministic),
        new DimensionWeight(ScoreDimension.EvidenceDiscipline, 15, AssessmentPosture.Advisory),
        new DimensionWeight(ScoreDimension.SolutionEconomy, 15, AssessmentPosture.Advisory),
    ]);
}

/// <summary>One dimension's assessment. <see cref="EarnedPoints"/> is null unless the dimension was scored.</summary>
public sealed record DimensionAssessment(
    ScoreDimension Dimension, int Weight, int? Rubric0to4, double? EarnedPoints, AssessmentPosture Posture, string Rationale);

/// <summary>Evidence Coverage - observed required signals / required signals (spec rule 3). Not a multiplier.</summary>
public sealed record EvidenceCoverage(int Observed, int Required);

/// <summary>
/// The deterministic evidence gathered about a closed episode - the scorer's pure input. Populating this
/// from the store / coordination log / verification ingest is the wiring follow-on; the engine is pure.
/// </summary>
public sealed record DeterministicEpisodeSignals(
    bool HasVerificationPath,
    bool? AcceptanceCriteriaMet,
    bool RequiredVerificationExecuted,
    bool RegressionPresent,
    IReadOnlySet<FloorDomain> UnresolvedFloorBlockers,
    int ActionsAfterDoneCondition,
    bool PrematureCompletion,
    int RequiredGuidanceTriggers,
    int SatisfiedGuidanceTriggers,
    int RequiredCoordinationSignals,
    int ObservedCoordinationSignals,
    bool CoverageCalibrated,
    int RequiredSignalTotal,
    int ObservedSignalTotal);

/// <summary>One evaluation of one closed episode under one schema version at one evaluation time (spec line 236).</summary>
public sealed record Scorecard(
    string EpisodeId,
    string SchemaVersion,
    WeaveVerdict Verdict,
    IReadOnlyList<DimensionAssessment> Assessments,
    IReadOnlyList<FloorDomain> TrippedFloors,
    EvidenceCoverage? Coverage,
    string Headline,
    DateTimeOffset EvaluatedAt);

/// <summary>
/// The deterministic Weave scorer. Pure, model-free: it turns a closed Work Episode's deterministic
/// evidence into an honest <see cref="Scorecard"/> - per-dimension 0-4 normalized to weight, the tripped
/// hard floors, Evidence Coverage, and a verdict. Advisory dimensions are declared-and-excluded, never
/// stubbed with fake numbers; a tripped floor suppresses the numeric headline; a missing
/// goal/done/verification path is Not Scored; a Partial headline never rescales to 0-100 (spec rules 1-9).
///
/// This is where <c>done_when</c> becomes measured: Focus-and-termination counts work after the done
/// condition, and Outcome-integrity checks the honest completion claim - the PACK-O drift / under-
/// validation faces (the AI-Forward goal-state work).
/// </summary>
public sealed class WeaveScorer
{
    public Scorecard Score(WorkEpisode episode, DeterministicEpisodeSignals signals, TimeProvider time)
        => Score(episode, signals, ScoreSchema.Weave1, time);

    public Scorecard Score(WorkEpisode episode, DeterministicEpisodeSignals signals, ScoreSchema schema, TimeProvider time)
    {
        ArgumentNullException.ThrowIfNull(episode);
        ArgumentNullException.ThrowIfNull(signals);
        ArgumentNullException.ThrowIfNull(schema);
        ArgumentNullException.ThrowIfNull(time);

        var at = time.GetUtcNow();

        // 1. Not Scored gate (rule 5): no goal, no done-condition, not closed, or no verification path.
        var notScored = NotScoredReason(episode, signals);
        if (notScored is not null)
        {
            return new Scorecard(episode.EpisodeId, schema.Version, WeaveVerdict.NotScored, [], [], null, $"Not Scored — {notScored}", at);
        }

        var assessments = schema.Dimensions.Select(d => Assess(d, episode, signals)).ToList();
        var coverage = signals.CoverageCalibrated
            ? new EvidenceCoverage(signals.ObservedSignalTotal, signals.RequiredSignalTotal)
            : null; // rule 3: uncalibrated -> Not Recorded, never 100% and never 0.

        // 2. Hard floors (rules 6-7): any trip -> Blocked, numeric headline suppressed.
        var tripped = TrippedFloors(signals);
        if (tripped.Count > 0)
        {
            return new Scorecard(episode.EpisodeId, schema.Version, WeaveVerdict.Blocked, assessments, tripped, coverage,
                "Blocked — a hard floor tripped; the numeric headline is suppressed.", at);
        }

        // 6. Verdict + headline (rule 2): no rescale to 0-100 when partial.
        return ComposeScoredCard(episode.EpisodeId, schema.Version, assessments, coverage, at, schema.TotalWeight);
    }

    /// <summary>
    /// Composes the verdict + headline from the (possibly advisory-folded) assessments. Shared by the
    /// deterministic scorer and the advisory fold so the no-rescale headline rule (rule 2) lives once.
    /// Assumes gating and floors were already resolved (this path is only reached for a scoreable card).
    /// </summary>
    internal static Scorecard ComposeScoredCard(
        string episodeId, string schemaVersion, IReadOnlyList<DimensionAssessment> assessments,
        EvidenceCoverage? coverage, DateTimeOffset at, int totalWeight)
    {
        var scored = assessments.Where(a => a.EarnedPoints is not null).ToList();
        var earned = scored.Sum(a => a.EarnedPoints!.Value);
        var observedWeight = scored.Sum(a => a.Weight);
        var allScored = scored.Count == assessments.Count;

        var (verdict, headline) = allScored
            ? (WeaveVerdict.Scored, $"{Format(earned)} / {totalWeight}")
            : (WeaveVerdict.Partial, $"Partial: {Format(earned)} / {observedWeight} observed");

        return new Scorecard(episodeId, schemaVersion, verdict, assessments, [], coverage, headline, at);
    }

    private static string? NotScoredReason(WorkEpisode episode, DeterministicEpisodeSignals signals)
    {
        if (string.IsNullOrWhiteSpace(episode.Goal.Statement))
        {
            return "no goal";
        }

        if (string.IsNullOrWhiteSpace(episode.DoneWhen.Statement))
        {
            return "no done condition";
        }

        if (episode.State != EpisodeState.Closed)
        {
            return "the episode is not closed";
        }

        return signals.HasVerificationPath ? null : "no minimum verification path";
    }

    private static IReadOnlyList<FloorDomain> TrippedFloors(DeterministicEpisodeSignals signals)
    {
        var tripped = new SortedSet<FloorDomain>(signals.UnresolvedFloorBlockers);

        // Correctness also trips on a failed acceptance criterion, a regression, or unrun required
        // verification (rule 6). A null (unknown) acceptance does NOT trip - unknown is not failed.
        if (signals.AcceptanceCriteriaMet == false || signals.RegressionPresent || !signals.RequiredVerificationExecuted)
        {
            tripped.Add(FloorDomain.Correctness);
        }

        return [.. tripped];
    }

    private static DimensionAssessment Assess(DimensionWeight entry, WorkEpisode episode, DeterministicEpisodeSignals signals)
    {
        if (entry.Posture == AssessmentPosture.Advisory)
        {
            return NotScoredDimension(entry, AssessmentPosture.Advisory,
                "advisory — excluded from points until the grader passes calibration (ADR-0019 advisory-evaluator-calibration, slice 7)");
        }

        return entry.Dimension switch
        {
            ScoreDimension.OutcomeIntegrity => Outcome(entry, episode, signals),
            ScoreDimension.FocusAndTermination => Focus(entry, signals),
            ScoreDimension.GuidanceAdherence => Proportional(entry, signals.SatisfiedGuidanceTriggers, signals.RequiredGuidanceTriggers, "guidance triggers"),
            ScoreDimension.CoordinationAndLearning => Proportional(entry, signals.ObservedCoordinationSignals, signals.RequiredCoordinationSignals, "coordination signals"),
            _ => NotScoredDimension(entry, AssessmentPosture.NotRecorded, "no deterministic signal in this schema"),
        };
    }

    private static DimensionAssessment Outcome(DimensionWeight entry, WorkEpisode episode, DeterministicEpisodeSignals signals)
    {
        if (signals.AcceptanceCriteriaMet is null)
        {
            return NotScoredDimension(entry, AssessmentPosture.NotRecorded, "acceptance criteria not recorded");
        }

        var rubric = 4;
        if (episode.Outcome != EpisodeOutcome.Completed)
        {
            rubric -= 2; // an Abandoned/Blocked/Superseded close is not a met outcome
        }

        if (signals.AcceptanceCriteriaMet == false)
        {
            rubric -= 2;
        }

        if (signals.RegressionPresent)
        {
            rubric -= 1;
        }

        if (!signals.RequiredVerificationExecuted)
        {
            rubric -= 1;
        }

        return Scored(entry, Clamp(rubric), "outcome from declared close + acceptance + regression + verification");
    }

    private static DimensionAssessment Focus(DimensionWeight entry, DeterministicEpisodeSignals signals)
    {
        var rubric = 4;
        if (signals.ActionsAfterDoneCondition > 0)
        {
            rubric -= 2; // work continued past the done condition (PACK-O drift)
        }

        if (signals.PrematureCompletion)
        {
            rubric -= 2; // closed as done while acceptance was not met (PACK-O under-validation)
        }

        return Scored(entry, Clamp(rubric), "focus from work-after-done and premature-completion counts");
    }

    private static DimensionAssessment Proportional(DimensionWeight entry, int satisfied, int required, string what)
    {
        if (required <= 0)
        {
            return NotScoredDimension(entry, AssessmentPosture.NotRecorded, $"no {what} required for this episode");
        }

        var rubric = Clamp((int)Math.Round(4.0 * satisfied / required, MidpointRounding.AwayFromZero));
        return Scored(entry, rubric, $"{satisfied}/{required} {what} satisfied");
    }

    private static DimensionAssessment Scored(DimensionWeight entry, int rubric, string rationale)
        => new(entry.Dimension, entry.Weight, rubric, rubric / 4.0 * entry.Weight, AssessmentPosture.Deterministic, rationale);

    private static DimensionAssessment NotScoredDimension(DimensionWeight entry, AssessmentPosture posture, string rationale)
        => new(entry.Dimension, entry.Weight, null, null, posture, rationale);

    private static int Clamp(int rubric) => Math.Clamp(rubric, 0, 4);

    private static string Format(double points) => points.ToString("0.#", CultureInfo.InvariantCulture);
}
