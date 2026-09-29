using AiDe.Core.Watcher;

namespace AiDe.Core.Tests.Watcher;

/// <summary>
/// LK-SKELETON-01 — the walking skeleton proven through its real composition seam: register an agent
/// session, observe a span, heartbeat, and read liveness, all through the real in-memory store, then
/// let time pass and confirm the honest transition to Stale. This is the end-to-end path the Phase-1
/// slice exists to prove (architecture §10).
/// </summary>
public sealed class WatcherCompositionTests
{
    [Fact]
    public void RegisterObserveHeartbeatEvaluate_ComposesEndToEnd()
    {
        // Arrange the real Phase-1 core: store, registrar, ingest, liveness, egress gate.
        var store = new InMemoryWatcherObservationStore();
        var clock = new FakeMonotonicClock();
        var registrar = new TrustedRegistrar(store, new SequentialCapabilityFactory(), clock, () => "session-1");
        var ingest = new SpanIngest(store, registrar);
        var liveness = new LivenessProjection(store, clock, TimeSpan.FromSeconds(30));
        var egress = new EgressGate();

        // Register a Claude Code / Opus 4.8 session.
        var session = registrar.Register(WatcherFixtures.Binding(
            harness: new HarnessIdentity("Claude Code", "1.0"),
            model: new ModelIdentity("Opus 4.8", "2026-08")));

        // Observe one operation, then a redelivery of the same operation.
        var span = new ObservedSpan(session.SessionId, "trace-1", "span-1", "Edit file", DateTimeOffset.UnixEpoch);
        Assert.Equal(IngestOutcome.Accepted, ingest.Ingest(session.SessionId, session.Capability, span));
        Assert.Equal(IngestOutcome.DuplicateIgnored,
            ingest.Ingest(session.SessionId, session.Capability,
                new ObservedSpan(session.SessionId, "trace-1", "span-1", "Edit file", DateTimeOffset.UnixEpoch)));

        // Heartbeat keeps it Alive; the harness/model attribution is carried; nothing egresses.
        registrar.Heartbeat(session.SessionId, session.Capability);
        Assert.Equal(LivenessState.Alive, liveness.Evaluate(session.SessionId));
        Assert.Equal("Opus 4.8", session.Binding.Model!.Name);
        Assert.Equal(1, store.SpanCount(session.SessionId));
        Assert.Equal(EgressDecision.Blocked, egress.Decide("hosted-grader"));

        // Time passes beyond the stale threshold without a heartbeat: honest transition to Stale.
        clock.Advance(TimeSpan.FromSeconds(31));
        Assert.Equal(LivenessState.Stale, liveness.Evaluate(session.SessionId));
    }
}
