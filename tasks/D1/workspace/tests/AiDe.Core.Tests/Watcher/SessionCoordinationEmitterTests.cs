using AiDe.Core.Watcher;

namespace AiDe.Core.Tests.Watcher;

/// <summary>
/// LK-EMITTER-01..09 - the auto-emitting session wrapper (conn-8). The claims: an identity maps to the
/// register attributes (omitting an absent harness/model, US-13); and end to end, a session that
/// registers + heartbeats through the emitter appears live in the watcher store after the host pumps,
/// re-registering is idempotent, HeartbeatAll keeps sessions alive, and End marks the session ended.
/// </summary>
public sealed class SessionCoordinationEmitterTests
{
    private static readonly DateTimeOffset At = DateTimeOffset.UnixEpoch;

    private sealed class TempDir : IDisposable
    {
        public string Path { get; } = System.IO.Path.Combine(
            System.IO.Path.GetTempPath(), $"aide-emitter-{Guid.NewGuid():N}");

        public TempDir() => Directory.CreateDirectory(Path);

        public void Dispose()
        {
            try { Directory.Delete(Path, recursive: true); }
            catch (IOException) { /* transient handle on Windows */ }
        }
    }

    private static SessionCoordinationIdentity Identity(string terminal = "term-1", string? harness = "claude-code", string? model = "opus-4-8")
        => new("C:/repos/healthwatch", "healthwatch", "main", "C:/repos/healthwatch", terminal, "agent-1", harness, "1.0.0", model, "2026-08");

    // ---- identity -> attributes ---------------------------------------------------------------------

    [Fact]
    public void ToAttributes_MapsTheIdentity()
    {
        var attrs = Identity().ToAttributes();

        Assert.Equal("C:/repos/healthwatch", attrs[OtelAttributes.RepoPath]);
        Assert.Equal("healthwatch", attrs[OtelAttributes.RepoDisplay]);
        Assert.Equal("term-1", attrs[OtelAttributes.TerminalId]);
        Assert.Equal("claude-code", attrs[OtelAttributes.ServiceName]);
        Assert.Equal("opus-4-8", attrs[OtelAttributes.GenAiModel]);
    }

    [Fact]
    public void ToAttributes_OmitsAbsentHarnessAndModel()
    {
        var attrs = Identity(harness: null, model: null).ToAttributes();

        Assert.False(attrs.ContainsKey(OtelAttributes.ServiceName));
        Assert.False(attrs.ContainsKey(OtelAttributes.GenAiModel));
        Assert.True(attrs.ContainsKey(OtelAttributes.AgentName)); // required attrs still present
    }

    // ---- end to end through the host ----------------------------------------------------------------

    [Fact]
    public void Register_ThenPump_SessionAppearsLiveInTheStore()
    {
        using var data = new TempDir();
        using var coord = new TempDir();
        using var host = WatcherHost.Open(data.Path, coord.Path, new FixedTimeProvider(At), new FakeMonotonicClock());
        var emitter = host.CreateEmitter();

        emitter.Register("ext-term-1", Identity());
        emitter.Heartbeat("ext-term-1");
        host.PumpOnce();

        var session = Assert.Single(host.Store.AllSessions());
        Assert.Equal("healthwatch", session.Binding.Repository.DisplayName);
        Assert.Equal("claude-code", session.Binding.Harness?.Name);
        Assert.Equal(LivenessState.Alive, host.Liveness.Evaluate(session.SessionId));
    }

    [Fact]
    public void CreateEmitter_UsesTheHostsCoordDirectory()
    {
        using var data = new TempDir();
        using var coord = new TempDir();
        using var host = WatcherHost.Open(data.Path, coord.Path, new FixedTimeProvider(At), new FakeMonotonicClock());

        Assert.Equal(coord.Path, host.CoordLogDirectory);
    }

    [Fact]
    public void Register_IsIdempotent_OneSessionAfterPump()
    {
        using var data = new TempDir();
        using var coord = new TempDir();
        using var host = WatcherHost.Open(data.Path, coord.Path, new FixedTimeProvider(At), new FakeMonotonicClock());
        var emitter = host.CreateEmitter();

        emitter.Register("ext-1", Identity());
        emitter.Register("ext-1", Identity()); // same id again - must not re-register
        host.PumpOnce();

        Assert.Equal(1, emitter.LiveCount);
        Assert.Single(host.Store.AllSessions());
    }

    [Fact]
    public void HeartbeatAll_KeepsEveryLiveSessionAlive()
    {
        using var data = new TempDir();
        using var coord = new TempDir();
        using var host = WatcherHost.Open(data.Path, coord.Path, new FixedTimeProvider(At), new FakeMonotonicClock());
        var emitter = host.CreateEmitter();
        emitter.Register("ext-a", Identity(terminal: "term-a"));
        emitter.Register("ext-b", Identity(terminal: "term-b"));

        emitter.HeartbeatAll();
        host.PumpOnce();

        Assert.Equal(2, host.Store.AllSessions().Count);
        Assert.All(host.Store.AllSessions(), s => Assert.Equal(LivenessState.Alive, host.Liveness.Evaluate(s.SessionId)));
    }

    [Fact]
    public void End_WritesSessionEnd_AndStopsTracking()
    {
        using var data = new TempDir();
        using var coord = new TempDir();
        using var host = WatcherHost.Open(data.Path, coord.Path, new FixedTimeProvider(At), new FakeMonotonicClock());
        var emitter = host.CreateEmitter();
        emitter.Register("ext-1", Identity());
        host.PumpOnce();
        var sessionId = host.Store.AllSessions()[0].SessionId;

        emitter.End("ext-1");
        host.PumpOnce();

        Assert.Equal(0, emitter.LiveCount);
        Assert.Equal(LivenessState.Ended, host.Liveness.Evaluate(sessionId));
    }

    [Fact]
    public void Heartbeat_ForAnUnknownSession_IsANoOp()
    {
        using var data = new TempDir();
        using var coord = new TempDir();
        using var host = WatcherHost.Open(data.Path, coord.Path, new FixedTimeProvider(At), new FakeMonotonicClock());
        var emitter = host.CreateEmitter();

        emitter.Heartbeat("never-registered"); // must not throw, must not create anything
        host.PumpOnce();

        Assert.Empty(host.Store.AllSessions());
    }

    // ---- reconcile (conn-8 shell driver) ------------------------------------------------------------

    [Fact]
    public void Reconcile_Registers_Heartbeats_AndEnds_FromASnapshot()
    {
        using var data = new TempDir();
        using var coord = new TempDir();
        using var host = WatcherHost.Open(data.Path, coord.Path, new FixedTimeProvider(At), new FakeMonotonicClock());
        var emitter = host.CreateEmitter();

        // First snapshot: two terminals exist -> both register.
        emitter.Reconcile(new HashSet<string> { "term-a", "term-b" }, t => Identity(t));
        host.PumpOnce();
        Assert.Equal(2, emitter.LiveCount);
        Assert.Equal(2, host.Store.AllSessions().Count);
        Assert.All(host.Store.AllSessions(), s => Assert.Equal(LivenessState.Alive, host.Liveness.Evaluate(s.SessionId)));

        // Second snapshot: term-b is gone (pane closed) -> it ends; term-a stays (heartbeated), no new session.
        emitter.Reconcile(new HashSet<string> { "term-a" }, t => Identity(t));
        host.PumpOnce();
        Assert.Equal(1, emitter.LiveCount);
        Assert.Equal(2, host.Store.AllSessions().Count); // append-only: still two rows, one now Ended
        var states = host.Store.AllSessions().Select(s => host.Liveness.Evaluate(s.SessionId)).ToList();
        Assert.Equal(1, states.Count(x => x == LivenessState.Alive));
        Assert.Equal(1, states.Count(x => x == LivenessState.Ended));
    }
}
