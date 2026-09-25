namespace AiDe.Core.Watcher;

/// <summary>
/// Computes a session's liveness from its heartbeats and the monotonic clock - a derived view, never
/// stored (ADR-0001, DM7). Because it uses monotonic elapsed duration, a wall-clock change cannot flip
/// a session's state (spec US-2).
/// </summary>
public sealed class LivenessProjection
{
    private readonly IWatcherObservationStore _store;
    private readonly IMonotonicClock _clock;
    private readonly double _staleAfterSeconds;

    public LivenessProjection(IWatcherObservationStore store, IMonotonicClock clock, TimeSpan staleAfter)
    {
        if (staleAfter <= TimeSpan.Zero)
        {
            throw new ArgumentOutOfRangeException(nameof(staleAfter), "The stale threshold must be positive.");
        }

        _store = store;
        _clock = clock;
        _staleAfterSeconds = staleAfter.TotalSeconds;
    }

    /// <summary>
    /// Ended if the session was ended or has no heartbeat (an unknown or never-alive session collapses
    /// to Ended per the spec); otherwise Alive within the stale threshold, else Stale.
    /// </summary>
    public LivenessState Evaluate(string sessionId)
    {
        if (_store.IsEnded(sessionId))
        {
            return LivenessState.Ended;
        }

        var last = _store.LastHeartbeat(sessionId);
        if (last is null)
        {
            return LivenessState.Ended;
        }

        var elapsedSeconds = (double)(_clock.Ticks - last.Value) / _clock.TicksPerSecond;
        return elapsedSeconds <= _staleAfterSeconds ? LivenessState.Alive : LivenessState.Stale;
    }
}
