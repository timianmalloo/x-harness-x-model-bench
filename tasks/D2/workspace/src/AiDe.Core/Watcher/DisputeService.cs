namespace AiDe.Core.Watcher;

/// <summary>
/// The operator-facing entry point for raising a dispute (US-16 / rule 12). It mints the dispute id and
/// timestamp and appends the <see cref="ScoreDispute"/> fact - the append-only, never-overwrites
/// guarantee lives in the store (conn-4). This is the API a UI command binds to; it exists so a caller
/// never hand-builds a dispute id or reaches past the store's append-only contract.
/// </summary>
public sealed class DisputeService(IWatcherObservationStore store, TimeProvider time, Func<string>? newDisputeId = null)
{
    private readonly IWatcherObservationStore _store = store ?? throw new ArgumentNullException(nameof(store));
    private readonly TimeProvider _time = time ?? throw new ArgumentNullException(nameof(time));
    private readonly Func<string> _newDisputeId = newDisputeId ?? (() => Guid.NewGuid().ToString("n"));

    /// <summary>
    /// Raises a dispute against a scored episode with the operator's reason, optionally targeting one
    /// dimension (null = the whole score). Appends the fact and returns it. The reason is required - a
    /// dispute with no stated reason is not an audit trail (US-16).
    /// </summary>
    public ScoreDispute RaiseDispute(string episodeId, string operatorId, string reason, ScoreDimension? dimension = null)
    {
        ArgumentException.ThrowIfNullOrEmpty(episodeId);
        ArgumentException.ThrowIfNullOrEmpty(operatorId);
        ArgumentException.ThrowIfNullOrWhiteSpace(reason);

        var dispute = new ScoreDispute(
            _newDisputeId(), episodeId, operatorId, dimension, reason.Trim(), _time.GetUtcNow());
        _store.AppendScoreDispute(dispute);
        return dispute;
    }
}

/// <summary>
/// The cloud-judge scaffold: an <see cref="IAdvisoryEvaluator"/> that delegates the actual 0-4 rubric to
/// an injected model call. A real integration supplies the delegate (a call to a provider, grounded on
/// the quarantined evidence, returning a rubric), and this evaluator is placed <b>inside</b> an
/// <see cref="EgressGuardedAdvisoryEvaluator"/> so the network call only happens after the ADR-0024 credential-backed-grading-egress
/// egress opt-in and credential check pass. It exists so the seam is concrete and testable without a
/// provider: the deterministic parts (guarding, folding, calibration) are proven around it, and the one
/// undetermined piece - the model call - is a single injected function.
/// </summary>
/// <remarks>
/// The delegate returns only a rubric (0-4); the evaluator clamps it and wraps it with the version and a
/// rationale. It never egresses by itself - egress is the guard's job. A production call would validate
/// the model's structured output (LOA A1-A3) before returning the rubric.
/// </remarks>
public sealed class DelegatingAdvisoryEvaluator(
    string evaluatorVersion, Func<ScoreDimension, WorkEpisode, string, int> judge) : IAdvisoryEvaluator
{
    private readonly Func<ScoreDimension, WorkEpisode, string, int> _judge = judge ?? throw new ArgumentNullException(nameof(judge));

    public string EvaluatorVersion { get; } =
        !string.IsNullOrEmpty(evaluatorVersion) ? evaluatorVersion : throw new ArgumentException("An evaluator version is required.", nameof(evaluatorVersion));

    public AdvisoryAssessment Evaluate(ScoreDimension dimension, WorkEpisode episode, string evidence)
    {
        ArgumentNullException.ThrowIfNull(episode);
        ArgumentNullException.ThrowIfNull(evidence);

        var rubric = Math.Clamp(_judge(dimension, episode, evidence), 0, 4);
        return new AdvisoryAssessment(
            dimension, rubric, $"model judgement ({EvaluatorVersion})", EvidencePointer: "model:evidence", EvaluatorVersion);
    }
}
