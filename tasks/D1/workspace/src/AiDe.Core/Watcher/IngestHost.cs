using System.Threading.Channels;

namespace AiDe.Core.Watcher;

/// <summary>A harness event. Registration/heartbeat are handled synchronously; spans are queued.</summary>
public abstract record HarnessEvent;

/// <summary>An observed span plus the capability the emitting process presented for its session.</summary>
public sealed record HarnessSpanEvent(SessionCapability Capability, HarnessSpan Span) : HarnessEvent;

/// <summary>
/// The transport port. An OTLP network receiver (slice 1b) or an in-process source implements this and
/// feeds <see cref="IngestHost.Enqueue"/>. Defined here as the seam; the host itself is transport-neutral.
/// </summary>
public interface IHarnessEventSource
{
    IAsyncEnumerable<HarnessSpanEvent> ReadSpansAsync(CancellationToken ct);
}

/// <summary>
/// A snapshot of the ingest counters - the operator questions answerable without a debugger (IO1):
/// how many spans came in, were dropped under load, stored, deduped, rejected as forged, or quarantined.
/// </summary>
public sealed record IngestStats(
    long Enqueued, long Dropped, long Ingested, long Deduped, long Rejected, long Quarantined);

/// <summary>
/// Hosts the ingest path: synchronous registration/heartbeat, plus an async, bounded span stream drained
/// into <see cref="OtelSpanMapper"/> + <see cref="SpanIngest"/>. A span flood is absorbed by the bounded
/// queue (drop-oldest), a forged span is rejected, and a malformed one is quarantined - one bad event can
/// never kill the drain loop, and every disposition increments a visible counter (US-11 fail honestly).
///
/// Pattern: bounded producer/consumer (LOA Channel&lt;T&gt; backpressure) - the repo's
/// <c>Channel.CreateBounded</c> + <c>DropOldest</c> idiom (ConPtyTerminalSession).
/// </summary>
public sealed class IngestHost
{
    private readonly Channel<HarnessSpanEvent> _queue;
    private readonly SpanIngest _ingest;
    private readonly ITrustedRegistrar _registrar;
    private readonly IWatcherObservationStore _store;
    private readonly IWorkEpisodeService _episodes;
    private readonly IMessageBoard _board;
    private readonly IRepositoryLocator _locator;
    private readonly TimeProvider _time;

    /// <summary>Corrections awaiting delivery to the registrant, drained by the host that publishes them.</summary>
    private readonly System.Collections.Concurrent.ConcurrentQueue<RegistrationNotice> _notices = new();

    private long _enqueued;
    private long _dropped;
    private long _ingested;
    private long _deduped;
    private long _rejected;
    private long _quarantined;

    public IngestHost(
        IWatcherObservationStore store,
        ITrustedRegistrar registrar,
        TimeProvider time,
        int queueCapacity = 1024,
        IWorkEpisodeService? episodes = null,
        IMessageBoard? board = null,
        IRepositoryLocator? locator = null)
    {
        ArgumentNullException.ThrowIfNull(store);
        ArgumentNullException.ThrowIfNull(registrar);
        ArgumentNullException.ThrowIfNull(time);
        ArgumentOutOfRangeException.ThrowIfLessThan(queueCapacity, 1);

        _registrar = registrar;
        _time = time;
        _store = store;
        _ingest = new SpanIngest(store, registrar);
        // Composed from the same three dependencies rather than required from the caller: every
        // existing construction site would otherwise have to be edited to pass something it has no
        // opinion about. Injectable for tests that need a controlled episode id.
        _episodes = episodes ?? new WorkEpisodeService(store, registrar, time);
        _board = board ?? new MessageBoardService(store, registrar, time);

        // Defaulted rather than required for the same reason as the two above: no existing
        // construction site has an opinion about it. Injectable so the correction can be tested
        // without creating real git worktrees, and so a caller that cannot see the registrant's
        // filesystem can supply one that always answers "unknown" instead of misfiring.
        _locator = locator ?? new FileSystemRepositoryLocator();

        // DropOldest keeps the freshest spans under load; the itemDropped callback makes every drop a
        // visible coverage-gap signal rather than a silent loss.
        _queue = Channel.CreateBounded<HarnessSpanEvent>(
            new BoundedChannelOptions(queueCapacity)
            {
                FullMode = BoundedChannelFullMode.DropOldest,
                SingleReader = true,
            },
            itemDropped: _ => Interlocked.Increment(ref _dropped));
    }

    /// <summary>Maps and registers a session synchronously, returning its capability (LK-0004/LK-0002).</summary>
    /// <remarks>
    /// <para><b>A registration claiming a worktree as its repository is corrected here</b>, before
    /// the registrar sees it, so every downstream consumer of <c>repo.path</c> — the fleet map, the
    /// message board partition, the score segment — agrees from the first moment the session exists.
    /// Correcting later would leave a window in which the session is on the wrong board.</para>
    ///
    /// <para>The correction is queued rather than acted on, because telling the registrant is
    /// somebody else's job: this class has no filesystem to write to and no idea where the agent is
    /// listening. See <see cref="DrainRegistrationNotices"/>.</para>
    /// </remarks>
    public RegisteredSession Register(HarnessRegistration registration)
    {
        var correction = RepositoryCorrection.Apply(OtelSpanMapper.MapRegistration(registration), _locator);

        // ADOPT an existing session for this terminal rather than minting a second one.
        //
        // MEASURED 2026-09-03: 21 register lines in a coordination log had produced 3,232 sessions
        // from 6 terminals. The pump re-reads the WHOLE log every tick, which is idempotent against
        // the adapter's in-memory external-id map — but that map dies with the process while the log
        // does not, so every application start replayed all 21 registers and minted 21 brand-new
        // sessions. Durable input, in-memory dedup: the duplication is once per restart, forever.
        //
        // The fix uses machinery that already existed and had no caller: RegisterNextGeneration
        // reuses the session id and bumps the generation, which is exactly what a restart IS. The
        // generation counter now means something — how many times the product restarted around this
        // terminal — where before it was pinned at 1 because a freshly minted GUID never matched.
        var existing = FindSessionForTerminal(correction.Binding.Terminal.TerminalId);
        var session = existing is null
            ? _registrar.Register(correction.Binding)
            : _registrar.RegisterNextGeneration(existing.SessionId, correction.Binding);

        if (correction.Corrected)
        {
            _notices.Enqueue(new RegistrationNotice(
                session.SessionId, correction.RepositorySent!, correction.RepositoryUsed!, correction.Reason!));
        }

        return session;
    }

    /// <summary>
    /// Takes the registration corrections that have not yet been delivered, emptying the queue.
    /// </summary>
    /// <remarks>
    /// <para><b>Drained, not read.</b> A notice is delivered once; leaving it queued would rewrite
    /// the same file every tick forever, and a re-appearing correction reads as a recurring problem
    /// rather than a single one that was already handled.</para>
    ///
    /// <para><b>Queued rather than published inline</b> because a registration arrives on the ingest
    /// path, where a filesystem write would put an agent's disk in the way of the pump every other
    /// session depends on. The delay is one tick, which is well inside the constraint that matters:
    /// the notice must be readable BEFORE the agent's first episode, not before its next instruction.</para>
    /// </remarks>
    public IReadOnlyList<RegistrationNotice> DrainRegistrationNotices()
    {
        var drained = new List<RegistrationNotice>();
        while (_notices.TryDequeue(out var notice))
        {
            drained.Add(notice);
        }

        return drained;
    }

    /// <summary>
    /// The session already recorded for this terminal, or <c>null</c> when it is genuinely new.
    /// </summary>
    /// <remarks>
    /// <para>Keyed on the TERMINAL id rather than the external session id, because that is the value
    /// the store durably holds — and the two are the same thing on every path that registers today,
    /// so matching on the stored one costs nothing and survives a caller that stops passing the
    /// other.</para>
    ///
    /// <para>A linear scan, deliberately. It runs once per register — not per tick — and after this
    /// fix the session count stops growing, so the set it scans is small by construction. An index
    /// would be optimising the symptom of the bug this method removes.</para>
    /// </remarks>
    private SessionRecord? FindSessionForTerminal(string terminalId)
    {
        if (string.IsNullOrEmpty(terminalId))
        {
            return null;
        }

        // The LAST match: with historical duplicates already in a store, adopting the most recent one
        // continues the newest history rather than resurrecting the oldest.
        return _store.AllSessions()
            .LastOrDefault(s => string.Equals(
                s.Binding.Terminal.TerminalId, terminalId, StringComparison.Ordinal));
    }

    /// <summary>Records a heartbeat after verifying the capability (LK-0001).</summary>
    public void Heartbeat(string sessionId, SessionCapability capability)
        => _registrar.Heartbeat(sessionId, capability);

    /// <summary>
    /// Records a harness and/or model learned after registration, capability-verified.
    /// </summary>
    /// <remarks>
    /// The reason this exists at all: AI-DE registers a terminal before knowing what runs inside it,
    /// and the model is knowable only by the agent. Without a post-registration path the model can
    /// never be recorded for any AI-DE-launched session, because a repeat <c>register</c> discards
    /// its attributes rather than merging them (observed).
    /// </remarks>
    public void UpdateHarnessAndModel(
        string sessionId, SessionCapability capability, HarnessIdentity? harness, ModelIdentity? model)
        => _registrar.UpdateHarnessAndModel(sessionId, capability, harness, model);

    /// <summary>
    /// Opens a Work Episode for a verified session (US-6). Capability-gated like every other
    /// post-registration write.
    /// </summary>
    /// <remarks>
    /// The reason this exists on the host: before it, <see cref="AuditLogEpisodeSource"/> was the
    /// only producer of episodes, so an episode existed only where the AI-Forward pack had written
    /// an audit entry. Any harness can now declare one over the coordination log, which is what the
    /// leaderboard's cross-harness comparison and the specified Daydream both depend on.
    /// </remarks>
    public WorkEpisode OpenEpisode(
        string sessionId, SessionCapability capability, Goal goal, DoneCondition doneWhen, string? notInScope = null)
        => _episodes.Open(sessionId, capability, goal, doneWhen, notInScope);

    /// <summary>Reframes an open episode: the current one closes Superseded and a new generation opens.</summary>
    public WorkEpisode ReframeEpisode(
        string episodeId, SessionCapability capability, Goal goal, DoneCondition doneWhen, string? notInScope = null)
        => _episodes.Reframe(episodeId, capability, goal, doneWhen, notInScope);

    /// <summary>Closes an episode with its declared outcome. The declaration is not a quality judgement.</summary>
    public WorkEpisode CloseEpisode(string episodeId, SessionCapability capability, EpisodeOutcome outcome)
        => _episodes.Close(episodeId, capability, outcome);

    /// <summary>
    /// Records the evidence paths an agent named for an episode — as declared, never as verified.
    /// </summary>
    /// <remarks>
    /// <para><b>A separate verb from <see cref="CloseEpisode"/> on purpose.</b> Closing declares an
    /// outcome; this declares where to look. Folding them into one call would make the episode's
    /// close depend on the evidence write, and the close is the thing that must not be lost.</para>
    ///
    /// <para><b>Capability-verified like every other write.</b> An unregistered session cannot
    /// declare evidence for an episode, for the same reason it cannot open one: registration is
    /// where trust is decided, and evidence attributed to a session that was never admitted is
    /// evidence with no one behind it.</para>
    ///
    /// <para><b>Nothing here inspects the paths.</b> An absolute path, one that escapes the
    /// repository, and one that does not exist are all recorded exactly as sent. Verification is a
    /// separate answer derived at scoring time, and merging the two would destroy the only evidence
    /// that separates an agent that lied from a file that moved.</para>
    /// </remarks>
    /// <returns>How many paths were recorded. Zero when none were declared — not a failure.</returns>
    public int DeclareEpisodeArtifacts(
        string episodeId, SessionCapability capability, IReadOnlyList<string> paths)
    {
        ArgumentException.ThrowIfNullOrEmpty(episodeId);
        ArgumentNullException.ThrowIfNull(capability);
        ArgumentNullException.ThrowIfNull(paths);

        return _episodes.DeclareArtifacts(episodeId, capability, paths);
    }

    /// <summary>
    /// Posts to a repository's Message Board on behalf of a verified session (US-4).
    /// </summary>
    /// <remarks>
    /// The reason these exist on the host: <see cref="MessageBoardService"/> had <b>no callers
    /// anywhere in the product</b>. It was implemented, tested and rendered as a pane, and nothing
    /// could write to it — a read surface over an empty store. An agent asked to post to the board
    /// searched the repository for how, found nothing, and the pane went on saying "No board posts
    /// yet". These are the ingest half of that path.
    /// </remarks>
    public BoardMessage PostToBoard(
        string repositoryKey, string sessionId, SessionCapability capability, BoardMessageKind kind, string content)
        => _board.Post(repositoryKey, sessionId, capability, kind, content);

    /// <summary>Replies to an existing message. The service refuses an orphan.</summary>
    public BoardMessage ReplyOnBoard(
        string repositoryKey, string sessionId, SessionCapability capability, string parentMessageId, string content)
        => _board.Reply(repositoryKey, sessionId, capability, parentMessageId, content);

    /// <summary>Acknowledges an existing message. Carries no content by design.</summary>
    public BoardMessage AcknowledgeOnBoard(
        string repositoryKey, string sessionId, SessionCapability capability, string parentMessageId)
        => _board.Acknowledge(repositoryKey, sessionId, capability, parentMessageId);

    /// <summary>
    /// Marks a session ended (its terminal closed / it reported session-end). Liveness then reads Ended
    /// rather than lingering Alive/Stale. Called by the coordination ingest on a session-end event; the
    /// registrar's re-registration path clears the ended mark for a fresh generation.
    /// </summary>
    public void EndSession(string sessionId) => _store.MarkEnded(sessionId);

    /// <summary>
    /// Enqueues a span event. Never blocks: under load the bounded queue drops its oldest item (counted),
    /// so a flood degrades to a coverage gap rather than unbounded growth.
    /// </summary>
    public void Enqueue(HarnessSpanEvent spanEvent)
    {
        ArgumentNullException.ThrowIfNull(spanEvent);
        // With DropOldest, TryWrite always accepts the new item; a displaced older item fires itemDropped.
        _queue.Writer.TryWrite(spanEvent);
        Interlocked.Increment(ref _enqueued);
    }

    /// <summary>
    /// Processes every span currently queued and returns the count. Deterministic (no waiting), so tests
    /// drain exactly what they enqueued.
    /// </summary>
    public int DrainAvailable()
    {
        var processed = 0;
        while (_queue.Reader.TryRead(out var spanEvent))
        {
            Process(spanEvent);
            processed++;
        }

        return processed;
    }

    /// <summary>The production loop: wait for spans, then drain, until cancelled.</summary>
    public async Task RunAsync(CancellationToken ct)
    {
        while (await _queue.Reader.WaitToReadAsync(ct).ConfigureAwait(false))
        {
            DrainAvailable();
        }
    }

    /// <summary>A point-in-time snapshot of the counters.</summary>
    public IngestStats Stats => new(
        Interlocked.Read(ref _enqueued),
        Interlocked.Read(ref _dropped),
        Interlocked.Read(ref _ingested),
        Interlocked.Read(ref _deduped),
        Interlocked.Read(ref _rejected),
        Interlocked.Read(ref _quarantined));

    private void Process(HarnessSpanEvent spanEvent)
    {
        ObservedSpan observed;
        try
        {
            observed = OtelSpanMapper.MapSpan(spanEvent.Span, _time.GetUtcNow());
        }
        catch (WatcherException ex) when (ex.Code == WatcherErrorCodes.MalformedEvent)
        {
            // A malformed span is dropped and counted; the loop must survive it (US-11).
            Interlocked.Increment(ref _quarantined);
            return;
        }

        switch (_ingest.Ingest(observed.SessionId, spanEvent.Capability, observed))
        {
            case IngestOutcome.Accepted:
                Interlocked.Increment(ref _ingested);
                break;
            case IngestOutcome.DuplicateIgnored:
                Interlocked.Increment(ref _deduped);
                break;
            case IngestOutcome.Rejected:
                Interlocked.Increment(ref _rejected);
                break;
        }
    }
}
