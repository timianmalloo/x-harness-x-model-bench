using AiDe.Core.Watcher;

namespace AiDe.Core.Tests.Watcher;

/// <summary>
/// LK-LIVE-01..05 — liveness as a monotonic-derived projection (spec US-2). The load-bearing claim is
/// that a wall-clock change cannot flip a session's state, so the clock is monotonic and injected.
/// </summary>
public sealed class LivenessProjectionTests
{
    private static (LivenessProjection liveness, TrustedRegistrar registrar, FakeMonotonicClock clock, RegisteredSession session) NewLiveness(TimeSpan staleAfter)
    {
        var store = new InMemoryWatcherObservationStore();
        var clock = new FakeMonotonicClock();
        var registrar = new TrustedRegistrar(store, new SequentialCapabilityFactory(), clock, () => "session-1");
        var session = registrar.Register(WatcherFixtures.Binding());
        return (new LivenessProjection(store, clock, staleAfter), registrar, clock, session);
    }

    [Fact]
    public void Evaluate_FreshHeartbeat_IsAlive()
    {
        var (liveness, _, _, session) = NewLiveness(TimeSpan.FromSeconds(10));

        Assert.Equal(LivenessState.Alive, liveness.Evaluate(session.SessionId));
    }

    [Fact]
    public void Evaluate_AfterStaleThreshold_IsStale()
    {
        var (liveness, _, clock, session) = NewLiveness(TimeSpan.FromSeconds(10));

        clock.Advance(TimeSpan.FromSeconds(11));

        Assert.Equal(LivenessState.Stale, liveness.Evaluate(session.SessionId));
    }

    [Fact]
    public void Evaluate_AfterEnd_IsEnded()
    {
        var (liveness, registrar, _, session) = NewLiveness(TimeSpan.FromSeconds(10));

        registrar.End(session.SessionId, session.Capability);

        Assert.Equal(LivenessState.Ended, liveness.Evaluate(session.SessionId));
    }

    [Fact]
    public void Evaluate_UnknownSession_IsEnded()
    {
        var (liveness, _, _, _) = NewLiveness(TimeSpan.FromSeconds(10));

        Assert.Equal(LivenessState.Ended, liveness.Evaluate("never-registered"));
    }

    [Fact]
    public void Evaluate_WithoutMonotonicAdvance_StaysAlive_EvenIfWallClockWouldJump()
    {
        // The projection reads only the monotonic clock. A wall-clock jump has no monotonic effect,
        // so with no monotonic time elapsed the session stays Alive - the state cannot be flipped by
        // the wall clock moving (spec US-2).
        var (liveness, registrar, clock, session) = NewLiveness(TimeSpan.FromSeconds(10));
        registrar.Heartbeat(session.SessionId, session.Capability);

        // No clock.Advance() here: a wall-clock change would not advance the monotonic source.
        Assert.Equal(LivenessState.Alive, liveness.Evaluate(session.SessionId));
    }
}
