using AiDe.Core.Watcher;

namespace AiDe.Core.Tests.Watcher;

/// <summary>
/// LK-HOST-01..10 - the ingest host (design-watcher-ingest-host). The claims: a span flood is absorbed
/// by the bounded queue and counted (not OOM), a forged span is rejected, a malformed one is quarantined
/// without killing the drain, and every disposition shows up in a visible counter (US-11).
/// </summary>
public sealed class IngestHostTests
{
    private static readonly DateTimeOffset At = DateTimeOffset.UnixEpoch;

    private static (IngestHost host, InMemoryWatcherObservationStore store, RegisteredSession session)
        NewHost(int capacity = 1024)
    {
        var store = new InMemoryWatcherObservationStore();
        var registrar = new TrustedRegistrar(store, new SequentialCapabilityFactory(), new FakeMonotonicClock(), () => "session-1");
        var host = new IngestHost(store, registrar, new FixedTimeProvider(At), capacity);
        var session = host.Register(WatcherFixtures.HarnessRegistration());
        return (host, store, session);
    }

    private static HarnessSpanEvent SpanEvent(SessionCapability cap, string sessionId, string source = "span-a")
        => new(cap, new HarnessSpan("trace-1", source, "chat.completion",
            new Dictionary<string, string?>(StringComparer.Ordinal) { [OtelAttributes.SessionId] = sessionId }));

    [Fact]
    public void Register_ReturnsAVerifiableCapability()
    {
        var (_, store, session) = NewHost();

        Assert.NotNull(store.FindSession(session.SessionId));
        Assert.Equal(1, session.Generation.Value);
    }

    [Fact]
    public void EnqueueDrain_ValidSpan_IngestedAndCounted()
    {
        var (host, store, session) = NewHost();

        host.Enqueue(SpanEvent(session.Capability, session.SessionId));
        var processed = host.DrainAvailable();

        Assert.Equal(1, processed);
        Assert.Equal(1, host.Stats.Ingested);
        Assert.Equal(1, store.SpanCount(session.SessionId));
    }

    [Fact]
    public void EnqueueDrain_DuplicateSpan_IsDeduped()
    {
        var (host, store, session) = NewHost();

        host.Enqueue(SpanEvent(session.Capability, session.SessionId));
        host.Enqueue(SpanEvent(session.Capability, session.SessionId)); // same source -> same content id
        host.DrainAvailable();

        Assert.Equal(1, host.Stats.Ingested);
        Assert.Equal(1, host.Stats.Deduped);
        Assert.Equal(1, store.SpanCount(session.SessionId));
    }

    [Fact]
    public void EnqueueDrain_ForgedCapability_Rejected_AndNotStored()
    {
        var (host, store, session) = NewHost();

        host.Enqueue(SpanEvent(WatcherFixtures.ForgedCapability(), session.SessionId));
        host.DrainAvailable();

        Assert.Equal(1, host.Stats.Rejected);
        Assert.Equal(0, host.Stats.Ingested);
        Assert.Equal(0, store.SpanCount(session.SessionId));
    }

    [Fact]
    public void EnqueueDrain_MalformedSpan_IsQuarantined_AndTheLoopSurvives()
    {
        var (host, store, session) = NewHost();
        // A span with no session.id attribute is unmappable (LK-0004).
        var malformed = new HarnessSpanEvent(session.Capability,
            new HarnessSpan("trace-x", "span-x", "op", new Dictionary<string, string?>(StringComparer.Ordinal)));

        host.Enqueue(malformed);
        host.Enqueue(SpanEvent(session.Capability, session.SessionId)); // a good span after the bad one
        host.DrainAvailable();

        Assert.Equal(1, host.Stats.Quarantined);
        Assert.Equal(1, host.Stats.Ingested);   // the loop survived and processed the good span
        Assert.Equal(1, store.SpanCount(session.SessionId));
    }

    [Fact]
    public void Enqueue_FloodPastCapacity_DropsOldest_AndCountsEveryDrop()
    {
        var (host, store, session) = NewHost(capacity: 4);

        // 10 distinct spans into a capacity-4 queue with DropOldest, drained only at the end.
        for (var i = 0; i < 10; i++)
        {
            host.Enqueue(SpanEvent(session.Capability, session.SessionId, source: $"span-{i}"));
        }

        Assert.Equal(10, host.Stats.Enqueued);
        Assert.Equal(6, host.Stats.Dropped);   // 10 - capacity 4

        host.DrainAvailable();

        Assert.Equal(4, host.Stats.Ingested);
        Assert.Equal(4, store.SpanCount(session.SessionId));
        // The counters reconcile: everything in is accounted for.
        var s = host.Stats;
        Assert.Equal(s.Enqueued, s.Ingested + s.Deduped + s.Rejected + s.Dropped + s.Quarantined);
    }

    [Fact]
    public void Heartbeat_BadCapability_Throws()
    {
        var (host, _, session) = NewHost();

        var ex = Assert.Throws<WatcherException>(() => host.Heartbeat(session.SessionId, WatcherFixtures.ForgedCapability()));

        Assert.Equal(WatcherErrorCodes.ForgeryRejected, ex.Code);
    }

    [Fact]
    public void Host_ComposesRegisterHeartbeatIngest_ThroughRealStore()
    {
        var store = new InMemoryWatcherObservationStore();
        var clock = new FakeMonotonicClock();
        var registrar = new TrustedRegistrar(store, new SequentialCapabilityFactory(), clock, () => "session-1");
        var host = new IngestHost(store, registrar, new FixedTimeProvider(At));
        var liveness = new LivenessProjection(store, clock, TimeSpan.FromSeconds(30));

        var session = host.Register(WatcherFixtures.HarnessRegistration(
            harnessName: "Claude Code", modelName: "Opus 4.8"));
        host.Heartbeat(session.SessionId, session.Capability);
        host.Enqueue(SpanEvent(session.Capability, session.SessionId));
        host.DrainAvailable();

        Assert.Equal(LivenessState.Alive, liveness.Evaluate(session.SessionId));
        Assert.Equal(1, store.SpanCount(session.SessionId));
        Assert.Equal("Opus 4.8", store.FindSession(session.SessionId)!.Binding.Model!.Name);
    }

    [Fact]
    public async Task Enqueue_Concurrent_CountsReconcile()
    {
        var (host, _, session) = NewHost(capacity: 4096);

        // 200 distinct spans enqueued concurrently, then drained once.
        var tasks = Enumerable.Range(0, 200).Select(i => Task.Run(
            () => host.Enqueue(SpanEvent(session.Capability, session.SessionId, source: $"s-{i}"))));
        await Task.WhenAll(tasks);
        host.DrainAvailable();

        var s = host.Stats;
        Assert.Equal(200, s.Enqueued);
        Assert.Equal(s.Enqueued, s.Ingested + s.Deduped + s.Rejected + s.Dropped + s.Quarantined);
    }
}
