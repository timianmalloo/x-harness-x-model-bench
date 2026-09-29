using System.Net;

namespace AiDe.Core.Watcher;

/// <summary>
/// The in-process watcher host: it composes the observation store, the trusted registrar, the ingest
/// host, the injected coordination-contract ingest + its log pump, and (best-effort) the OTLP network
/// receiver into one running unit. Running it <b>in the same process as the read surfaces</b> is
/// deliberate: liveness compares monotonic ticks, which are process-relative, so hosting the ingest
/// beside the panes makes liveness exact - the cross-process caveat conn-2 recorded simply does not
/// arise here (a heartbeat and the liveness projection read one process's Stopwatch).
/// </summary>
/// <remarks>
/// <para>This is composition, not new behaviour (Solution-Selection Ladder rung 2): every part already
/// exists and is tested in isolation (slices 1, 2, 3). The host wires them and owns their lifetime.</para>
/// <para><b>Two ingest paths, one store.</b> The <b>coordination-contract log</b> (file-based, the
/// symbiotic path a non-AI-Forward session opts into by writing a register/heartbeat/session-end log
/// via <see cref="CoordContractWriter"/>) is drained by <see cref="PumpOnce"/> / <see cref="RunAsync"/>;
/// the <b>OTLP span</b> path (network) is drained by the same host when <see cref="TryStartOtlp"/>
/// started a receiver. Re-reading the whole coordination log directory is idempotent (registration is
/// keyed by external id), so a periodic pump never double-registers.</para>
/// </remarks>
public sealed class WatcherHost : IDisposable
{
    private readonly SqliteWatcherObservationStore _store;
    private readonly IngestHost _ingest;
    private readonly CoordContractLogPump _pump;
    private readonly LivenessProjection _liveness;
    private readonly string _coordLogDirectory;
    private readonly TimeProvider _time;
    private OtlpHttpReceiver? _receiver;
    private bool _disposed;

    private WatcherHost(
        SqliteWatcherObservationStore store, IngestHost ingest, CoordContractLogPump pump,
        LivenessProjection liveness, string coordLogDirectory, TimeProvider time)
    {
        _store = store;
        _ingest = ingest;
        _pump = pump;
        _liveness = liveness;
        _coordLogDirectory = coordLogDirectory;
        _time = time;
    }

    /// <summary>
    /// Opens the host: the SQLite watcher store at <c>&lt;dataDirectory&gt;/watcher.db</c>, and the
    /// coordination-contract log pump over <paramref name="coordLogDirectory"/>. The registrar and the
    /// liveness projection share one monotonic clock so liveness is consistent in-process.
    /// </summary>
    public static WatcherHost Open(
        string dataDirectory,
        string coordLogDirectory,
        TimeProvider? time = null,
        IMonotonicClock? clock = null,
        TimeSpan? staleAfter = null)
    {
        ArgumentException.ThrowIfNullOrEmpty(dataDirectory);
        ArgumentException.ThrowIfNullOrEmpty(coordLogDirectory);

        time ??= TimeProvider.System;
        clock ??= new SystemMonotonicClock();
        Directory.CreateDirectory(dataDirectory);
        Directory.CreateDirectory(coordLogDirectory);

        var store = SqliteWatcherObservationStore.Open(Path.Combine(dataDirectory, "watcher.db"));
        var registrar = new TrustedRegistrar(store, new CapabilityFactory(), clock);
        var ingest = new IngestHost(store, registrar, time);
        var injected = new InjectedContractIngest(ingest);
        var pump = new CoordContractLogPump(coordLogDirectory, injected);
        var liveness = new LivenessProjection(store, clock, staleAfter ?? TimeSpan.FromSeconds(30));

        return new WatcherHost(store, ingest, pump, liveness, coordLogDirectory, time);
    }

    /// <summary>The coordination-contract log directory a session opts in by writing to.</summary>
    public string CoordLogDirectory => _coordLogDirectory;

    /// <summary>
    /// A writer for the coordination log this host reads - a terminal/agent session in the same process
    /// registers and heartbeats through it, and the pump ingests it, so the session appears live (US-4).
    /// </summary>
    public SessionCoordinationEmitter CreateEmitter() =>
        new(new CoordContractWriter(_coordLogDirectory, _time));

    /// <summary>
    /// Imports the closed Work Episodes declared in a repo's AI-Forward audit log (the goal-state entries,
    /// AL5b) into the store, so real episodes exist to observe and score. Idempotent by episode id (a
    /// re-import of the same entry replaces its row, not duplicates it - <see cref="IWatcherObservationStore.RecordEpisode"/>
    /// is an upsert). Returns the number of episodes imported. A missing file imports nothing.
    /// </summary>
    public int ImportEpisodesFromAuditLog(string auditLogPath)
    {
        ArgumentException.ThrowIfNullOrEmpty(auditLogPath);
        var episodes = AuditLogEpisodeSource.ReadFile(auditLogPath);
        foreach (var episode in episodes)
        {
            _store.RecordEpisode(episode);
        }

        return episodes.Count;
    }

    /// <summary>
    /// Imports the workspace's declared-goal episodes (ep-capture) AND auto-scores each one (conn-10).
    /// Derives its <see cref="DeterministicEpisodeSignals"/> from the observable audit evidence (a committed
    /// Proof Pack, plus any explicit telemetry <see cref="AuditSignals"/> the turn recorded - t3) and records
    /// the Weave. When <paramref name="evaluator"/> and <paramref name="registry"/> are supplied the two
    /// ADVISORY dimensions are folded too, but only if the evaluator has qualified in the registry (ADR-0019 advisory-evaluator-calibration):
    /// the safe default (both null) records the deterministic Weave only. The local heuristic evaluator is
    /// on-device (no egress); the cloud judge additionally needs an operator egress opt-in + credentials
    /// (t4). Idempotent (episode + scorecard upsert); operatorId is the session id (never a human identity);
    /// a missing file imports nothing.
    /// </summary>
    public int ImportAndScoreEpisodesFromAuditLog(
        string auditLogPath,
        WorkspaceKey? workspace,
        string taskClass = "audit-import",
        IAdvisoryEvaluator? evaluator = null,
        CalibrationRegistry? registry = null,
        DaydreamRecorder? daydream = null)
    {
        ArgumentException.ThrowIfNullOrEmpty(auditLogPath);
        ArgumentException.ThrowIfNullOrEmpty(taskClass);

        var imported = AuditLogEpisodeSource.ReadFileWithEvidence(auditLogPath);
        var scoring = new ScoringService(_store, _time, daydream);
        foreach (var (episode, evidence) in imported)
        {
            _store.RecordEpisode(episode);
            var signals = DeterministicSignalsDeriver.Derive(episode, evidence, _store);
            scoring.ScoreAndRecord(
                episode, signals, operatorId: episode.SessionId, taskClass: taskClass,
                workspace: workspace, evaluator: evaluator, registry: registry);
        }

        return imported.Count;
    }

    /// <summary>
    /// Scores every closed episode of a registered session that has no scorecard yet, and returns how
    /// many were newly scored (US-16's missing link). Delegates to <see cref="ClosedEpisodeScoring"/>,
    /// which is where the reasoning lives.
    /// </summary>
    public int ScoreClosedEpisodes(
        string taskClass = ScoreSegment.Unclassified,
        IAdvisoryEvaluator? evaluator = null,
        CalibrationRegistry? registry = null,
        DaydreamRecorder? daydream = null)
        => ClosedEpisodeScoring.Run(_store, _time, taskClass, evaluator, registry, daydream);

    /// <summary>The observation store, for the read surfaces (the app builds its queries from this).</summary>
    public IWatcherObservationStore Store => _store;

    /// <summary>The liveness projection sharing the host's monotonic clock (exact in-process).</summary>
    public LivenessProjection Liveness => _liveness;

    /// <summary>The ingest host, exposed so an in-process source can enqueue spans directly.</summary>
    public IngestHost Ingest => _ingest;

    /// <summary>A snapshot of the ingest counters (IO1 - answerable without a debugger).</summary>
    public IngestStats Stats => _ingest.Stats;

    /// <summary>
    /// Pumps the coordination-contract log once and drains any queued spans; returns the number of
    /// coordination events applied. Idempotent across calls (register is keyed by external id).
    /// </summary>
    public int PumpOnce()
    {
        var applied = _pump.PumpOnce();
        _ingest.DrainAvailable();
        return applied;
    }

    /// <summary>
    /// The background loop: pump + drain every <paramref name="interval"/> until cancelled. A transient
    /// read failure (a log file mid-write) is absorbed and retried next tick - one bad read never kills
    /// the loop (US-11 fail honestly), and the store degrades to "no new events", never a wrong number.
    /// </summary>
    public async Task RunAsync(TimeSpan interval, CancellationToken ct)
    {
        while (!ct.IsCancellationRequested)
        {
            try
            {
                PumpOnce();
            }
            catch (Exception ex) when (ex is IOException or UnauthorizedAccessException)
            {
                // A log file being appended to concurrently, or a transient permission blip: skip this
                // tick and try again. The next pump re-reads the whole directory, so nothing is lost.
            }

            try
            {
                await Task.Delay(interval, ct).ConfigureAwait(false);
            }
            catch (OperationCanceledException)
            {
                break;
            }
        }
    }

    /// <summary>
    /// Best-effort start of the OTLP HTTP receiver on a loopback prefix (the network span path). Returns
    /// false and leaves the host fully functional (coordination path only) when the prefix cannot bind -
    /// on Windows an <c>HttpListener</c> prefix may need a URL ACL, and a watcher that refused to run
    /// without the network path would be worse than one that ran the file path and reported the gap.
    /// </summary>
    public bool TryStartOtlp(string loopbackPrefix, ISessionTokenResolver tokens, CancellationToken ct)
    {
        ArgumentException.ThrowIfNullOrEmpty(loopbackPrefix);
        ArgumentNullException.ThrowIfNull(tokens);

        try
        {
            _receiver = new OtlpHttpReceiver(_ingest, tokens, loopbackPrefix);
            _ = _receiver.RunAsync(ct);
            return true;
        }
        catch (Exception ex) when (ex is HttpListenerException or ObjectDisposedException or PlatformNotSupportedException)
        {
            _receiver?.Dispose();
            _receiver = null;
            return false;
        }
    }

    public void Dispose()
    {
        if (_disposed)
        {
            return;
        }

        _disposed = true;
        _receiver?.Dispose();
        _store.Dispose();
    }
}
