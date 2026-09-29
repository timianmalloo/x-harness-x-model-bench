namespace AiDe.Core.Watcher;

/// <summary>
/// Composes a closed episode's <see cref="DeterministicEpisodeSignals"/> into the quarantined evidence
/// token string the <see cref="LocalHeuristicAdvisoryEvaluator"/> grounds on (the
/// <c>key=value; key=value</c> vocabulary). It maps only the signals we actually capture; a dimension the
/// local heuristic looks for but we do not observe (e.g. <c>reuse</c>) is simply omitted, so the
/// evaluator scores it conservatively rather than optimistically (NG1). Deterministic and pure.
/// </summary>
public static class EvidenceComposer
{
    public static string Compose(DeterministicEpisodeSignals signals)
    {
        ArgumentNullException.ThrowIfNull(signals);

        // Only observed signals are emitted. coverage is observed/required; an unobserved token is left
        // out entirely so the evaluator's conservative default applies.
        var verification = signals.RequiredVerificationExecuted ? "executed" : "none";
        var premature = signals.PrematureCompletion ? "true" : "false";
        return string.Join("; ",
            $"verification={verification}",
            $"coverage={signals.ObservedSignalTotal}/{signals.RequiredSignalTotal}",
            $"actions_after_done={signals.ActionsAfterDoneCondition}",
            $"premature={premature}");
    }
}

/// <summary>
/// Turns a closed Work Episode + its deterministic signals into a persisted <see cref="ScoredEpisode"/>,
/// so a scored episode appears on the Leaderboard/Standing surfaces (US-14/US-16). It scores the four
/// deterministic dimensions always, and folds the two advisory dimensions ONLY when the supplied
/// evaluator's <c>(version, taskClass, schemaVersion)</c> has qualified in the calibration registry
/// (ADR-0019 advisory-evaluator-calibration, rule 8) - otherwise they stay excluded exactly as the deterministic scorer left them.
/// </summary>
/// <remarks>
/// <para>Advisory evaluation grounds on <see cref="EvidenceComposer"/>'s token string. Where no evaluator
/// is supplied (the safe default), only the deterministic Weave is recorded - which is enough to populate
/// the Leaderboard. The classification (harness/model/operator/taskClass) is supplied by the caller: it
/// comes from the session binding + the episode, which this pure service does not re-derive.</para>
/// <para>It never overrides a floor or a Not Scored verdict - that guarantee lives in
/// <see cref="AdvisoryWeaveScorer"/> (rule 8) and is exercised here end to end.</para>
/// </remarks>
/// <param name="daydream">
/// Optional. When supplied, every recorded scorecard is offered to the repository's Daydream record.
/// Here rather than at the two producers because this is the ONE place a scored episode comes into
/// existence, and a rule spelled at two call sites is a rule that drifts apart. The recorder decides
/// for itself whether an episode is worth recording, and writes nothing when it is not.
/// </param>
public sealed class ScoringService(
    IWatcherObservationStore store, TimeProvider time, DaydreamRecorder? daydream = null)
{
    private readonly IWatcherObservationStore _store = store ?? throw new ArgumentNullException(nameof(store));
    private readonly TimeProvider _time = time ?? throw new ArgumentNullException(nameof(time));
    private readonly DaydreamRecorder? _daydream = daydream;
    private readonly AdvisoryWeaveScorer _advisoryScorer = new();

    /// <summary>The two advisory dimensions the local evaluator may judge (rule 8 owns the rest).</summary>
    private static readonly ScoreDimension[] AdvisoryDimensions =
        [ScoreDimension.EvidenceDiscipline, ScoreDimension.SolutionEconomy];

    /// <summary>
    /// Scores the episode and persists the result. When <paramref name="evaluator"/> and
    /// <paramref name="registry"/> are supplied, the advisory dimensions are evaluated from the composed
    /// evidence and folded only if qualified; otherwise only the deterministic Weave is recorded.
    /// </summary>
    /// <param name="workspace">
    /// The repository the work happened in, or <c>null</c> when it could not be resolved. Required
    /// rather than defaulted so every caller decides: a default here would silently record every
    /// score into the unknown cohort, which reads as a working leaderboard with no rows.
    /// </param>
    public ScoredEpisode ScoreAndRecord(
        WorkEpisode episode,
        DeterministicEpisodeSignals signals,
        string operatorId,
        string taskClass,
        WorkspaceKey? workspace,
        string? harness = null,
        string? model = null,
        IAdvisoryEvaluator? evaluator = null,
        CalibrationRegistry? registry = null)
    {
        ArgumentNullException.ThrowIfNull(episode);
        ArgumentNullException.ThrowIfNull(signals);
        ArgumentException.ThrowIfNullOrEmpty(operatorId);
        ArgumentException.ThrowIfNullOrEmpty(taskClass);

        Scorecard card;
        if (evaluator is not null && registry is not null)
        {
            var evidence = EvidenceComposer.Compose(signals);
            var advisory = AdvisoryDimensions
                .Select(d => evaluator.Evaluate(d, episode, evidence))
                .ToList();
            card = _advisoryScorer.Score(episode, signals, advisory, registry, taskClass, _time);
        }
        else
        {
            card = new WeaveScorer().Score(episode, signals, _time);
        }

        // The segment is composed here rather than accepted: the schema version belongs to the card
        // the scorer just produced, and a caller-supplied one would be a second definition of it.
        var scored = new ScoredEpisode(
            episode.EpisodeId, harness, model, operatorId,
            new ScoreSegment(workspace, taskClass, card.SchemaVersion), card);
        _store.RecordScorecard(scored);

        // After the scorecard is stored, never before: an observation whose evidence the store does
        // not yet hold is a pattern a reader cannot follow back. Offered, not forced - the recorder
        // declines a clean episode, and an agent's Not-Scored episode is currently one of those
        // (nothing was observed, so no floor tripped and no rubric fell short).
        _daydream?.Observe(scored);

        return scored;
    }
}
