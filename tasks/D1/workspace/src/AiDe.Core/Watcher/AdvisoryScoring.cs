namespace AiDe.Core.Watcher;

/// <summary>
/// Quadratic Weighted Kappa - the human-agreement gate (spec rule 9b, ADR-0019 advisory-evaluator-calibration). Measures agreement
/// between two 0..K-1 rating vectors, correcting for chance and penalising disagreement by the squared
/// band distance. 1 is perfect agreement; 0 is chance; negative is worse than chance.
/// </summary>
public static class QuadraticWeightedKappa
{
    public const double Floor = 0.75;

    public static double Compute(IReadOnlyList<int> a, IReadOnlyList<int> b, int categories = 5)
    {
        ArgumentNullException.ThrowIfNull(a);
        ArgumentNullException.ThrowIfNull(b);
        if (a.Count != b.Count)
        {
            throw new ArgumentException("The two rating vectors must be the same length.");
        }

        if (a.Count == 0 || categories < 2)
        {
            return 1.0; // nothing to disagree about
        }

        var n = a.Count;
        var k = categories - 1; // max band distance
        var observed = new double[categories, categories];
        var rowTotals = new double[categories];
        var colTotals = new double[categories];

        for (var m = 0; m < n; m++)
        {
            var i = Math.Clamp(a[m], 0, k);
            var j = Math.Clamp(b[m], 0, k);
            observed[i, j] += 1;
            rowTotals[i] += 1;
            colTotals[j] += 1;
        }

        double numerator = 0, denominator = 0;
        for (var i = 0; i < categories; i++)
        {
            for (var j = 0; j < categories; j++)
            {
                var weight = (double)((i - j) * (i - j)) / (k * k);
                var expected = rowTotals[i] * colTotals[j] / n;
                numerator += weight * observed[i, j];
                denominator += weight * expected;
            }
        }

        // No expected disagreement (a marginal is degenerate) means the ratings agree perfectly.
        return denominator == 0 ? 1.0 : 1.0 - numerator / denominator;
    }
}

/// <summary>
/// Evaluator stability over repeated runs of the same item - the reproducibility gate (spec rule 9a):
/// the ratings must stay in the same discrete 0-4 band at least 95% of the time and never differ by
/// more than one band.
/// </summary>
public sealed record EvaluatorStability(double ModalBandFraction, int Spread)
{
    public bool Passes => ModalBandFraction >= 0.95 && Spread <= 1;

    public static EvaluatorStability Of(IReadOnlyList<int> repeats)
    {
        ArgumentNullException.ThrowIfNull(repeats);
        if (repeats.Count == 0)
        {
            return new EvaluatorStability(0, int.MaxValue); // no evidence of stability
        }

        var modal = repeats.GroupBy(r => r).Max(g => g.Count());
        return new EvaluatorStability((double)modal / repeats.Count, repeats.Max() - repeats.Min());
    }
}

/// <summary>The outcome of the ADR-0019 advisory-evaluator-calibration calibration gates for one advisory evaluator version.</summary>
public sealed record CalibrationVerdict(bool Qualified, IReadOnlyList<string> Reasons);

/// <summary>
/// The advisory-evaluator calibration gates (spec rules 9, 14; ADR-0019 advisory-evaluator-calibration). An evaluator version qualifies
/// to contribute score points only when ALL hold: (a) it is stable across repeats; (b) its agreement
/// with human labels reaches QWK &gt;= 0.75; and (c) the anti-Goodhart counter-metrics (held-out outcome
/// integrity, regression rate, rework, dispute overturns) did not worsen - otherwise it is rejected as
/// score gaming or miscalibration.
/// </summary>
public static class AdvisoryCalibration
{
    public static CalibrationVerdict Qualify(
        IReadOnlyList<int> stabilityRepeats,
        IReadOnlyList<int> evaluatorRatings,
        IReadOnlyList<int> humanRatings,
        bool counterMetricsHeldNoWorse)
    {
        var reasons = new List<string>();

        var stability = EvaluatorStability.Of(stabilityRepeats);
        if (!stability.Passes)
        {
            reasons.Add($"unstable: {stability.ModalBandFraction:P0} in-band, spread {stability.Spread} (needs >=95%, <=1)");
        }

        var kappa = QuadraticWeightedKappa.Compute(evaluatorRatings, humanRatings);
        if (kappa < QuadraticWeightedKappa.Floor)
        {
            reasons.Add($"low human agreement: QWK {kappa:0.00} (needs >= {QuadraticWeightedKappa.Floor:0.00})");
        }

        if (!counterMetricsHeldNoWorse)
        {
            reasons.Add("rejected as score gaming / miscalibration: held-out counter-metrics worsened");
        }

        return new CalibrationVerdict(reasons.Count == 0, reasons);
    }
}

/// <summary>
/// Records which advisory evaluator versions have qualified to contribute points, per
/// <c>(evaluatorVersion, taskClass, schemaVersion)</c> - because a change to any of the evaluator,
/// task class, or schema requires re-qualification (spec rules 10/13).
/// </summary>
public sealed class CalibrationRegistry
{
    private readonly HashSet<string> _qualified = new(StringComparer.Ordinal);
    private readonly object _gate = new();

    public void Qualify(string evaluatorVersion, string taskClass, string schemaVersion)
    {
        lock (_gate)
        {
            _qualified.Add(Key(evaluatorVersion, taskClass, schemaVersion));
        }
    }

    public bool IsQualified(string evaluatorVersion, string taskClass, string schemaVersion)
    {
        lock (_gate)
        {
            return _qualified.Contains(Key(evaluatorVersion, taskClass, schemaVersion));
        }
    }

    private static string Key(string evaluatorVersion, string taskClass, string schemaVersion)
        => $"{evaluatorVersion}\u001F{taskClass}\u001F{schemaVersion}";
}

/// <summary>One advisory (model-judge) assessment of a dimension. Carries its evaluator version and evidence.</summary>
public sealed record AdvisoryAssessment(
    ScoreDimension Dimension, int Rubric0to4, string Rationale, string EvidencePointer, string EvaluatorVersion);

/// <summary>
/// The model-judge seam (spec rule 8). A real implementation grounds on quarantined evidence and runs a
/// local model behind the credential/egress policy (ADR-0024 credential-backed-grading-egress, Phase 4/5); slice 7 depends only on the
/// interface, so the deterministic gate + fold are fully testable without a model.
/// </summary>
public interface IAdvisoryEvaluator
{
    string EvaluatorVersion { get; }

    AdvisoryAssessment Evaluate(ScoreDimension dimension, WorkEpisode episode, string evidence);
}

/// <summary>
/// Folds calibrated advisory assessments into a deterministic Weave scorecard (spec rule 9). An advisory
/// dimension earns points ONLY when its <c>(evaluatorVersion, taskClass, schemaVersion)</c> has qualified
/// in the registry; otherwise it stays excluded, exactly as the deterministic scorer left it. Advisory
/// never overrides a deterministic result: a Not Scored or Blocked base card is returned unchanged (a
/// tripped floor stands; an advisory judgment can never raise a deterministic failed dimension - rule 8).
/// </summary>
public sealed class AdvisoryWeaveScorer(WeaveScorer? baseScorer = null)
{
    private readonly WeaveScorer _base = baseScorer ?? new WeaveScorer();

    public Scorecard Score(
        WorkEpisode episode,
        DeterministicEpisodeSignals signals,
        IReadOnlyList<AdvisoryAssessment> advisory,
        CalibrationRegistry registry,
        string taskClass,
        TimeProvider time)
    {
        ArgumentNullException.ThrowIfNull(advisory);
        ArgumentNullException.ThrowIfNull(registry);

        var baseCard = _base.Score(episode, signals, time);

        // Advisory never overrides gating or floors (rule 8): a Not Scored or Blocked card stands.
        if (baseCard.Verdict is WeaveVerdict.NotScored or WeaveVerdict.Blocked || advisory.Count == 0)
        {
            return baseCard;
        }

        var byDimension = advisory
            .GroupBy(a => a.Dimension)
            .ToDictionary(g => g.Key, g => g.First());

        var updated = baseCard.Assessments.Select(assessment =>
        {
            if (assessment.Posture == AssessmentPosture.Advisory
                && byDimension.TryGetValue(assessment.Dimension, out var adv)
                && registry.IsQualified(adv.EvaluatorVersion, taskClass, baseCard.SchemaVersion))
            {
                var rubric = Math.Clamp(adv.Rubric0to4, 0, 4);
                return assessment with
                {
                    Rubric0to4 = rubric,
                    EarnedPoints = rubric / 4.0 * assessment.Weight,
                    Rationale = $"advisory (calibrated {adv.EvaluatorVersion}): {adv.Rationale}",
                };
            }

            return assessment; // unqualified advisory stays excluded (rule 9)
        }).ToList();

        return WeaveScorer.ComposeScoredCard(
            episode.EpisodeId, baseCard.SchemaVersion, updated, baseCard.Coverage, baseCard.EvaluatedAt, ScoreSchema.Weave1.TotalWeight);
    }
}
