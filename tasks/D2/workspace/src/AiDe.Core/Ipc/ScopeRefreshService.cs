using System.Collections.Concurrent;
using System.Diagnostics;
using System.Text.Json;

namespace AiDe.Core.Ipc;

/// <summary>Where a scope refresh has got to.</summary>
public enum ScopeRefreshState
{
    /// <summary>Extraction is under way. Nothing has been committed yet.</summary>
    Running,

    /// <summary>A complete snapshot was committed.</summary>
    Completed,

    /// <summary>Extraction did not complete. The previous snapshot still renders.</summary>
    Failed,
}

/// <summary>What a caller learns about a refresh.</summary>
/// <remarks>
/// <see cref="Failure"/> is populated on <see cref="ScopeRefreshState.Failed"/> and states why. A
/// refresh that failed silently would leave the last good snapshot rendering with nothing to say it
/// is now stale — which is the "clean empty success over rotting evidence" this product exists to
/// avoid.
/// </remarks>
/// <param name="QueuedMilliseconds">
/// How long the refresh waited before it began. Separate from <paramref name="DurationMilliseconds"/>
/// because they have different remedies: waiting is a concurrency problem, running is a cost problem,
/// and a single "how long did it take" hides which one a user is feeling.
/// </param>
/// <param name="DurationMilliseconds">How long the refresh itself took, once it started.</param>
public sealed record ScopeRefreshStatus(
    string CommandId,
    string ScopeId,
    ScopeRefreshState State,
    int AssertionCount,
    string? Failure,
    long QueuedMilliseconds = 0,
    long DurationMilliseconds = 0);

/// <summary>
/// What every refresh so far has cost, and how often they happen.
/// </summary>
/// <param name="Completed">Refreshes that finished.</param>
/// <param name="Failed">Refreshes that did not.</param>
/// <param name="P50Milliseconds">The median refresh. What a user feels most of the time.</param>
/// <param name="P95Milliseconds">The slow tail. What a user complains about.</param>
/// <param name="MaxMilliseconds">The worst one seen.</param>
/// <param name="FirstAt">When the first refresh was observed, or null if none has been.</param>
/// <param name="LastAt">When the most recent one was observed.</param>
/// <remarks>
/// <para><b>This exists to answer a question a design decision is blocked on.</b>
/// <c>docs/notes/note-20260830-sub-scope-incrementality.md</c> weighs four ways to make re-indexing
/// incremental below the scope, and refuses to pick one, because the thing that decides it has never
/// been measured: whether re-indexing is an occasional on-demand cost or something a user waits on
/// constantly. Optimising a 1.2s operation that runs when asked is a different proposition from
/// optimising one that runs on every save.</para>
///
/// <para><b>No rate is computed here.</b> "Refreshes per hour" from two samples is a number with no
/// error bar that will be quoted as if it had one. The raw facts — how many, first, last — let a
/// reader compute it when there is enough of it to mean something, and notice when there is not.</para>
/// </remarks>
public sealed record RefreshMetrics(
    int Completed,
    int Failed,
    long P50Milliseconds,
    long P95Milliseconds,
    long MaxMilliseconds,
    DateTimeOffset? FirstAt,
    DateTimeOffset? LastAt);

/// <summary>Asking the daemon what refreshing has cost so far.</summary>
public sealed record RefreshMetricsRequest();

/// <summary>Asking the daemon to re-index a scope.</summary>
public sealed record RefreshRequest(string ScopeId, string ArtifactRevision);

/// <summary>Asking how a previously started refresh is doing.</summary>
public sealed record RefreshStatusRequest(string CommandId);

/// <summary>
/// Re-indexing a scope, across the boundary.
/// </summary>
/// <remarks>
/// <para><b>Started and polled, never awaited on the wire.</b> A scope has a 60-second budget and
/// the IPC lane serves one request at a time per connection — so a refresh that answered only when
/// it finished would hold that connection for a minute, and the daemon's response-write timeout
/// would abandon it long before. The control lane carries <i>commands</i>; a command that starts
/// long work returns as soon as the work is started.</para>
///
/// <para><b>The command id is the idempotency key</b>, exactly as the architecture's command
/// protocol specifies. Re-sending the same id returns the same job rather than starting a second
/// extraction — which matters most in the case it exists for: a client that did not see the reply
/// and retried. Two extractions of one scope would both bump the generation and the loser's work
/// would be discarded, having cost a full budget.</para>
///
/// <para><b>Nothing here re-implements ingestion.</b> The generation fence, the incomplete-result
/// handling and the snapshot commit all stay in <see cref="WorkspaceCore"/>; this decides only what
/// crossing the boundary means.</para>
/// </remarks>
public sealed class ScopeRefreshService
{
    private static readonly ActivitySource Telemetry = new("aide.ipc.command");

    /// <summary>Finished jobs kept for collection by a client that has not asked yet.</summary>
    /// <remarks>
    /// Bounded, because job records are keyed by a caller-chosen id and an unbounded map is a memory
    /// leak any client can drive. Oldest completed jobs are dropped first: a status nobody collected
    /// within this many refreshes is one nobody is waiting for.
    /// simplify: a flat cap with oldest-first eviction rather than a time-based expiry; ceiling 256
    /// retained jobs; upgrade trigger = a client legitimately polls for a result later than that.
    /// </remarks>
    private const int RetainedJobs = 256;

    /// <summary>
    /// Durations kept for the percentile summary.
    /// </summary>
    /// <remarks>
    /// Bounded, because a daemon that runs for a week must not accumulate a sample per refresh
    /// forever. The oldest are dropped, so the summary describes recent behaviour — which is the
    /// behaviour anybody is asking about.
    /// </remarks>
    private const int RetainedSamples = 512;

    private readonly ConcurrentDictionary<string, ScopeRefreshStatus> _jobs = new(StringComparer.Ordinal);
    private readonly System.Threading.Lock _samplesGate = new();
    private readonly Queue<long> _samples = new();
    private int _completed;
    private int _failed;
    private DateTimeOffset? _firstAt;
    private DateTimeOffset? _lastAt;
    private readonly ConcurrentQueue<string> _order = new();
    private readonly Func<string, string, CancellationToken, Task<int>> _refresh;

    /// <param name="refresh">
    /// Runs the extraction and returns the assertion count. Injected rather than taking a
    /// <see cref="WorkspaceCore"/> so the boundary's behaviour — idempotency, retention, what a
    /// failure looks like — is testable without standing up a store and an extractor.
    /// </param>
    public ScopeRefreshService(Func<string, string, CancellationToken, Task<int>> refresh) =>
        _refresh = refresh ?? throw new ArgumentNullException(nameof(refresh));

    /// <summary>Jobs currently held, running or finished.</summary>
    public int TrackedJobs => _jobs.Count;

    /// <summary>Starts a refresh, or returns the job this command id already started.</summary>
    public ScopeRefreshStatus Start(string commandId, string scopeId, string artifactRevision)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(commandId);
        ArgumentException.ThrowIfNullOrWhiteSpace(scopeId);

        // A fast path, not the control. Deleting it changes nothing observable, because the TryAdd
        // below refuses a duplicate anyway and returns the same job — which is where deduplication
        // actually happens. Kept because it avoids allocating a status for the common retry, and
        // labelled so nobody mistakes it for the guard (DC-016: know which of your checks can fire).
        if (_jobs.TryGetValue(commandId, out var existing))
        {
            return existing;
        }

        var started = new ScopeRefreshStatus(commandId, scopeId, ScopeRefreshState.Running, 0, null);

        if (!_jobs.TryAdd(commandId, started))
        {
            // Lost a race with an identical retry. The winner's job is the answer — starting a
            // second extraction here is the exact duplication the idempotency key prevents.
            return _jobs[commandId];
        }

        _order.Enqueue(commandId);
        Evict();

        // The queue clock starts HERE, not inside RunAsync: the wait this measures is the gap
        // between accepting the work and beginning it, which is invisible from inside the work.
        _ = RunAsync(commandId, scopeId, artifactRevision, System.Diagnostics.Stopwatch.GetTimestamp());
        return started;
    }

    /// <summary>How a refresh is doing, or <c>null</c> if this daemon has no record of it.</summary>
    /// <remarks>
    /// Null rather than a synthesised "unknown" state: a job this daemon never started, or one it
    /// has since evicted, are both "I cannot tell you", and inventing a status would let a caller
    /// wait for a result that is never coming.
    /// </remarks>
    public ScopeRefreshStatus? Status(string commandId) =>
        _jobs.TryGetValue(commandId, out var status) ? status : null;

    /// <summary>What refreshing has cost so far, on the normal path with no flag to remember.</summary>
    public RefreshMetrics Metrics()
    {
        lock (_samplesGate)
        {
            var ordered = _samples.Order().ToList();

            return new RefreshMetrics(
                _completed, _failed,
                Percentile(ordered, 0.50),
                Percentile(ordered, 0.95),
                ordered.Count == 0 ? 0 : ordered[^1],
                _firstAt, _lastAt);
        }
    }

    /// <summary>
    /// The value at a percentile, or zero when nothing has been measured.
    /// </summary>
    /// <remarks>
    /// Nearest-rank, on a list that is already sorted. Zero for "no samples" rather than a
    /// plausible-looking interpolation of nothing — every measurement path here degrades to "not
    /// recorded", never to a number somebody might believe.
    /// </remarks>
    private static long Percentile(IReadOnlyList<long> sorted, double fraction)
    {
        if (sorted.Count == 0) return 0;

        var rank = (int)Math.Ceiling(fraction * sorted.Count) - 1;
        return sorted[Math.Clamp(rank, 0, sorted.Count - 1)];
    }

    private void Record(long durationMs, bool succeeded, DateTimeOffset at)
    {
        lock (_samplesGate)
        {
            if (succeeded) _completed++; else _failed++;

            _samples.Enqueue(durationMs);
            while (_samples.Count > RetainedSamples) _samples.Dequeue();

            _firstAt ??= at;
            _lastAt = at;
        }
    }

    private async Task RunAsync(
        string commandId, string scopeId, string artifactRevision, long queuedAtTicks)
    {
        using var span = Telemetry.StartActivity("ipc.scope_refresh");
        span?.SetTag("scope.id", scopeId);
        span?.SetTag("command.id", commandId);

        var queuedMs = Elapsed(queuedAtTicks);
        var startedAtTicks = System.Diagnostics.Stopwatch.GetTimestamp();

        span?.SetTag("refresh.queued_ms", queuedMs);

        try
        {
            var count = await _refresh(scopeId, artifactRevision, CancellationToken.None)
                .ConfigureAwait(false);

            var durationMs = Elapsed(startedAtTicks);

            _jobs[commandId] = new ScopeRefreshStatus(
                commandId, scopeId, ScopeRefreshState.Completed, count, null, queuedMs, durationMs);

            span?.SetTag("assertion.count", count);
            span?.SetTag("refresh.duration_ms", durationMs);

            Record(durationMs, succeeded: true, DateTimeOffset.UtcNow);
        }
        catch (Exception ex)
        {
            // Any exception, and it is recorded rather than rethrown: this runs detached from the
            // request that started it, so an escaping exception would take down the daemon on behalf
            // of a caller who is no longer listening. The failure belongs in the status the caller
            // WILL ask for.
            var durationMs = Elapsed(startedAtTicks);

            _jobs[commandId] = new ScopeRefreshStatus(
                commandId, scopeId, ScopeRefreshState.Failed, 0, ex.Message, queuedMs, durationMs);

            span?.SetStatus(ActivityStatusCode.Error, ex.Message);
            span?.SetTag("refresh.duration_ms", durationMs);

            // A FAILED refresh is timed too. A run that takes twenty seconds and then throws is the
            // one an operator most wants to see, and excluding failures from the summary is how a
            // percentile ends up describing only the easy cases.
            Record(durationMs, succeeded: false, DateTimeOffset.UtcNow);
        }
    }

    private static long Elapsed(long sinceTicks) =>
        (System.Diagnostics.Stopwatch.GetTimestamp() - sinceTicks)
        * 1000 / System.Diagnostics.Stopwatch.Frequency;

    private void Evict()
    {
        while (_jobs.Count > RetainedJobs && _order.TryDequeue(out var oldest))
        {
            // A running job is never evicted: its status is the only record that it is happening,
            // and dropping it would report an in-flight extraction as one this daemon never heard of.
            if (_jobs.TryGetValue(oldest, out var status) && status.State == ScopeRefreshState.Running)
            {
                _order.Enqueue(oldest);
                return;
            }

            _jobs.TryRemove(oldest, out _);
        }
    }

    /// <summary>Registers refresh and its status query on the endpoint.</summary>
    public void Register(DaemonEndpoint endpoint)
    {
        ArgumentNullException.ThrowIfNull(endpoint);

        endpoint.Register(Operations.Refresh, (request, _) =>
        {
            var body = Decode<RefreshRequest>(request);
            return body is null
                ? IpcResponse.Error(IpcErrorCodes.MalformedEnvelope, "refresh requires a scope and a revision")
                : IpcResponse.Success(
                    Start(request.CommandId, body.ScopeId, body.ArtifactRevision),
                    WorkspaceOperations.Wire);
        });

        endpoint.Register(Operations.RefreshStatus, (request, _) =>
        {
            var body = Decode<RefreshStatusRequest>(request);
            if (body is null)
            {
                return IpcResponse.Error(IpcErrorCodes.MalformedEnvelope, "a command id is required");
            }

            var status = Status(body.CommandId);
            return status is null
                ? IpcResponse.Error(
                    IpcErrorCodes.CommandUnknown,
                    $"this daemon has no record of command '{body.CommandId}'")
                : IpcResponse.Success(status, WorkspaceOperations.Wire);
        });

        // No request body and no failure mode: an operator asking "what has re-indexing cost"
        // should never be told it depends on what they enable first.
        endpoint.Register(Operations.RefreshMetrics, (_, _) =>
            IpcResponse.Success(Metrics(), WorkspaceOperations.Wire));
    }

    private static T? Decode<T>(IpcRequest request)
    {
        try
        {
            return IpcPayload.Read<T>(request.Payload, WorkspaceOperations.Wire);
        }
        catch (JsonException)
        {
            return default;
        }
    }

    /// <summary>The operation names, so both ends spell them the same way.</summary>
    public static class Operations
    {
        public const string Refresh = "refresh";
        public const string RefreshStatus = "refresh.status";

        public const string RefreshMetrics = "refresh.metrics";
    }
}
