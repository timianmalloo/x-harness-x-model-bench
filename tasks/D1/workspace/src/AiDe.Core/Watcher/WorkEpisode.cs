namespace AiDe.Core.Watcher;

/// <summary>A session-authored objective. Immutable; a change starts a new episode (spec line 211).</summary>
public sealed record Goal(string Statement);

/// <summary>
/// The done-condition - the <b>terminal condition</b> against which the episode's outcome is judged
/// (the AI-Forward <c>done_when</c>: "point at a result and say whether it is met", CT19). Immutable.
/// </summary>
public sealed record DoneCondition(string Statement);

/// <summary>An episode's ordinal within its session's sequential episode chain (1, 2, 3 …).</summary>
public readonly record struct EpisodeGeneration(long Value);

/// <summary>
/// The DECLARED lifecycle terminal state of an episode - not a quality score. Whether a
/// <see cref="Completed"/> claim is <i>honest</i> (the goal was actually met vs. drifted past the
/// done-condition) is the Weave's Outcome-integrity dimension (slice 5), deliberately not decided here.
/// </summary>
public enum EpisodeOutcome { Completed, Abandoned, Superseded, Blocked }

/// <summary>Whether an episode is still open or has closed (derived from <see cref="WorkEpisode.ClosedAt"/>).</summary>
public enum EpisodeState { Active, Closed }

/// <summary>
/// One Work Episode: one immutable goal + done-condition over one bounded interval of one session
/// (spec US-6, lines 201-234). The <b>unit scoring attaches to</b>. It mirrors the AI-Forward CT19
/// goal-state triple (Goal / DoneWhen / NotInScope) so it is the durable, scoreable projection of a
/// turn's goal-state, not a parallel structure.
/// </summary>
public sealed record WorkEpisode(
    string EpisodeId,
    string SessionId,
    EpisodeGeneration Generation,
    Goal Goal,
    DoneCondition DoneWhen,
    string? NotInScope,
    DateTimeOffset OpenedAt,
    DateTimeOffset? ClosedAt,
    EpisodeOutcome? Outcome)
{
    /// <summary>Active until closed; Closed carries the interval end and the declared outcome.</summary>
    public EpisodeState State => ClosedAt is null ? EpisodeState.Active : EpisodeState.Closed;
}

/// <summary>
/// The Work Episode lifecycle. Only the authenticated session may open, reframe, or close <i>its</i>
/// episodes - every call presents the session capability and is verified (LK-0001 forgery on mismatch,
/// ADR-0020 trusted-registrar-harness-model-identity). Times use the wall-clock <see cref="TimeProvider"/> - the same base as span
/// <c>RecordedAt</c> - because an episode binds <i>recorded</i> activity, not a <i>live</i> condition.
/// </summary>
public interface IWorkEpisodeService
{
    WorkEpisode Open(string sessionId, SessionCapability capability, Goal goal, DoneCondition doneWhen, string? notInScope = null);

    /// <summary>Changing the goal starts a NEW episode: the current one is closed <c>Superseded</c> and a new generation opens.</summary>
    WorkEpisode Reframe(string episodeId, SessionCapability capability, Goal goal, DoneCondition doneWhen, string? notInScope = null);

    WorkEpisode Close(string episodeId, SessionCapability capability, EpisodeOutcome outcome);

    /// <summary>
    /// Records the evidence paths an agent named for an episode — as declared, never as verified.
    /// </summary>
    /// <remarks>
    /// Lives here rather than on the ingest host because capability verification does, and the same
    /// rule applies: an unregistered session cannot declare evidence, for the reason it cannot open
    /// an episode. Evidence attributed to a session that was never admitted has no one behind it.
    /// </remarks>
    /// <returns>How many paths were recorded. Zero when none were declared — not a failure.</returns>
    int DeclareArtifacts(string episodeId, SessionCapability capability, IReadOnlyList<string> paths);
}

/// <summary>The default in-process episode service. See <see cref="IWorkEpisodeService"/>.</summary>
public sealed class WorkEpisodeService : IWorkEpisodeService
{
    private readonly IWatcherObservationStore _store;
    private readonly ITrustedRegistrar _registrar;
    private readonly TimeProvider _time;
    private readonly Func<string> _newEpisodeId;
    private readonly object _gate = new();

    public WorkEpisodeService(
        IWatcherObservationStore store,
        ITrustedRegistrar registrar,
        TimeProvider time,
        Func<string>? newEpisodeId = null)
    {
        ArgumentNullException.ThrowIfNull(store);
        ArgumentNullException.ThrowIfNull(registrar);
        ArgumentNullException.ThrowIfNull(time);
        _store = store;
        _registrar = registrar;
        _time = time;
        _newEpisodeId = newEpisodeId ?? (() => Guid.NewGuid().ToString("n"));
    }

    public WorkEpisode Open(string sessionId, SessionCapability capability, Goal goal, DoneCondition doneWhen, string? notInScope = null)
    {
        ArgumentException.ThrowIfNullOrEmpty(sessionId);
        RequireCapability(sessionId, capability);
        Validate(goal, doneWhen);

        lock (_gate)
        {
            var episode = new WorkEpisode(
                _newEpisodeId(), sessionId, new EpisodeGeneration(NextGeneration(sessionId)),
                goal, doneWhen, NullIfBlank(notInScope),
                _time.GetUtcNow(), ClosedAt: null, Outcome: null);
            _store.RecordEpisode(episode);
            return episode;
        }
    }

    public WorkEpisode Reframe(string episodeId, SessionCapability capability, Goal goal, DoneCondition doneWhen, string? notInScope = null)
    {
        ArgumentException.ThrowIfNullOrEmpty(episodeId);
        Validate(goal, doneWhen);

        lock (_gate)
        {
            var current = RequireActive(episodeId);
            RequireCapability(current.SessionId, capability);

            // Immutability: the goal is never mutated. Close the current episode Superseded, then open
            // a new generation with the new goal - "changing the goal starts a new episode" (spec 211).
            _store.RecordEpisode(current with { ClosedAt = _time.GetUtcNow(), Outcome = EpisodeOutcome.Superseded });

            var next = new WorkEpisode(
                _newEpisodeId(), current.SessionId, new EpisodeGeneration(NextGeneration(current.SessionId)),
                goal, doneWhen, NullIfBlank(notInScope),
                _time.GetUtcNow(), ClosedAt: null, Outcome: null);
            _store.RecordEpisode(next);
            return next;
        }
    }

    public WorkEpisode Close(string episodeId, SessionCapability capability, EpisodeOutcome outcome)
    {
        ArgumentException.ThrowIfNullOrEmpty(episodeId);

        lock (_gate)
        {
            var current = RequireActive(episodeId);
            RequireCapability(current.SessionId, capability);

            var closed = current with { ClosedAt = _time.GetUtcNow(), Outcome = outcome };
            _store.RecordEpisode(closed);
            return closed;
        }
    }

    private long NextGeneration(string sessionId) => _store.EpisodesForSession(sessionId).Count + 1;

    /// <summary>
    /// Records declared evidence paths against an episode.
    /// </summary>
    /// <remarks>
    /// <para><b>Against the episode, open or closed.</b> Unlike every other verb here this does not
    /// call <c>RequireActive</c>: the declaration arrives on the close line, and the contract
    /// adapter records it before closing, so requiring an OPEN episode would work today and break
    /// the moment anyone reordered those two calls. It requires the episode to EXIST, which is the
    /// property actually needed.</para>
    ///
    /// <para><b>Nothing here inspects a path.</b> Absolute, escaping the repository, non-existent —
    /// all recorded exactly as sent. Verification is a separate answer derived at scoring time, and
    /// merging the two destroys the only evidence separating an agent that lied from a file that
    /// moved.</para>
    /// </remarks>
    public int DeclareArtifacts(string episodeId, SessionCapability capability, IReadOnlyList<string> paths)
    {
        ArgumentException.ThrowIfNullOrEmpty(episodeId);
        ArgumentNullException.ThrowIfNull(paths);

        if (paths.Count == 0)
        {
            return 0;
        }

        lock (_gate)
        {
            var episode = _store.FindEpisode(episodeId)
                ?? throw new WatcherException(
                    WatcherErrorCodes.InvalidBinding, $"No work episode '{episodeId}' exists.");

            // Verified before ANY row is written, so a refusal writes nothing rather than a prefix.
            RequireCapability(episode.SessionId, capability);

            var at = _time.GetUtcNow();
            for (var i = 0; i < paths.Count; i++)
            {
                _store.AppendDeclaredArtifact(new DeclaredEpisodeArtifact(episodeId, paths[i], at, i));
            }

            return paths.Count;
        }
    }

    private WorkEpisode RequireActive(string episodeId)
    {
        var episode = _store.FindEpisode(episodeId)
            ?? throw new WatcherException(WatcherErrorCodes.InvalidBinding, $"No work episode '{episodeId}' exists.");
        if (episode.State == EpisodeState.Closed)
        {
            throw new WatcherException(WatcherErrorCodes.InvalidBinding, $"Work episode '{episodeId}' is already closed.");
        }

        return episode;
    }

    private void RequireCapability(string sessionId, SessionCapability capability)
    {
        ArgumentNullException.ThrowIfNull(capability);
        if (!_registrar.Verify(sessionId, capability))
        {
            throw new WatcherException(
                WatcherErrorCodes.ForgeryRejected,
                "The presented session capability did not match the session's current capability.");
        }
    }

    private static void Validate(Goal goal, DoneCondition doneWhen)
    {
        ArgumentNullException.ThrowIfNull(goal);
        ArgumentNullException.ThrowIfNull(doneWhen);
        if (string.IsNullOrWhiteSpace(goal.Statement) || string.IsNullOrWhiteSpace(doneWhen.Statement))
        {
            throw new WatcherException(
                WatcherErrorCodes.InvalidBinding,
                "A work episode requires a non-empty goal and done-condition.");
        }
    }

    private static string? NullIfBlank(string? value) => string.IsNullOrWhiteSpace(value) ? null : value;
}

/// <summary>
/// The deterministic read projection over episodes (ADR-0001; DM7 derive-don't-store). It computes an
/// episode's state and the observable activity bound to its interval - spans whose <c>RecordedAt</c>
/// falls in <c>[OpenedAt, ClosedAt ?? now]</c> - never a stored tally.
/// </summary>
public sealed class EpisodeProjection(IWatcherObservationStore store, TimeProvider time)
{
    private readonly IWatcherObservationStore _store = store ?? throw new ArgumentNullException(nameof(store));
    private readonly TimeProvider _time = time ?? throw new ArgumentNullException(nameof(time));

    /// <summary>The spans observed inside the episode's interval (an open episode uses <c>now</c> as the end).</summary>
    public int ObservedSpanCount(WorkEpisode episode)
    {
        ArgumentNullException.ThrowIfNull(episode);
        return _store.SpanCountInInterval(episode.SessionId, episode.OpenedAt, episode.ClosedAt ?? _time.GetUtcNow());
    }

    /// <summary>The session's episodes in generation order (its sequential episode chain).</summary>
    public IReadOnlyList<WorkEpisode> ForSession(string sessionId) => _store.EpisodesForSession(sessionId);
}
