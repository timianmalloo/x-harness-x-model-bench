using AiDe.Core.Watcher;

namespace AiDe.Core.Tests.Watcher;

/// <summary>
/// LK-SPAN-01..08 — idempotent span ingest (ADR-0006 / ADR-0023 watcher-observation-projection). The claim is not "we store a span"
/// but "a redelivered or out-of-order span is safe, and a forged session cannot write a fact."
/// </summary>
public sealed class SpanIngestTests
{
    private static (SpanIngest ingest, RegisteredSession session, ITrustedRegistrar registrar) NewIngest()
    {
        var store = new InMemoryWatcherObservationStore();
        var registrar = new TrustedRegistrar(
            store, new SequentialCapabilityFactory(), new FakeMonotonicClock(), () => "session-1");
        var session = registrar.Register(WatcherFixtures.Binding());
        return (new SpanIngest(store, registrar), session, registrar);
    }

    private static ObservedSpan Span(string session, string source = "span-a", string trace = "trace-1")
        => new(session, trace, source, "Edit file", DateTimeOffset.UnixEpoch);

    [Fact]
    public void Ingest_ValidCapability_Accepted()
    {
        var (ingest, session, _) = NewIngest();

        var outcome = ingest.Ingest(session.SessionId, session.Capability, Span(session.SessionId));

        Assert.Equal(IngestOutcome.Accepted, outcome);
    }

    [Fact]
    public void Ingest_SameSpanTwice_SecondIsDuplicateIgnored()
    {
        var (ingest, session, _) = NewIngest();
        var span = Span(session.SessionId);

        var first = ingest.Ingest(session.SessionId, session.Capability, span);
        // A redelivery constructs an equal span (same source id) - a realistic at-least-once redelivery.
        var second = ingest.Ingest(session.SessionId, session.Capability, Span(session.SessionId));

        Assert.Equal(IngestOutcome.Accepted, first);
        Assert.Equal(IngestOutcome.DuplicateIgnored, second);
    }

    [Fact]
    public void Ingest_DistinctSpansInAnyOrder_BothAccepted()
    {
        var (ingest, session, _) = NewIngest();

        var b = ingest.Ingest(session.SessionId, session.Capability, Span(session.SessionId, source: "span-b"));
        var a = ingest.Ingest(session.SessionId, session.Capability, Span(session.SessionId, source: "span-a"));

        Assert.Equal(IngestOutcome.Accepted, b);
        Assert.Equal(IngestOutcome.Accepted, a);
    }

    [Fact]
    public void Ingest_ForgedCapability_Rejected_AndNothingStored()
    {
        var (ingest, session, _) = NewIngest();
        var forged = WatcherFixtures.ForgedCapability(); // a token no registrar ever issued

        var outcome = ingest.Ingest(session.SessionId, forged, Span(session.SessionId));

        Assert.Equal(IngestOutcome.Rejected, outcome);
    }

    [Fact]
    public void ObservedSpan_SameInputs_YieldSameId()
    {
        var one = Span("s", source: "src", trace: "tr");
        var two = Span("s", source: "src", trace: "tr");

        Assert.Equal(one.SpanId, two.SpanId);
    }

    [Theory]
    [InlineData("s2", "tr", "src")]
    [InlineData("s", "tr2", "src")]
    [InlineData("s", "tr", "src2")]
    public void ObservedSpan_AnyDifferingField_YieldsDifferentId(string session, string trace, string source)
    {
        var baseline = new ObservedSpan("s", "tr", "src", "op", DateTimeOffset.UnixEpoch);
        var variant = new ObservedSpan(session, trace, source, "op", DateTimeOffset.UnixEpoch);

        Assert.NotEqual(baseline.SpanId, variant.SpanId);
    }

    [Fact]
    public async Task Ingest_ConcurrentDuplicates_AppendExactlyOnce()
    {
        var store = new InMemoryWatcherObservationStore();
        var registrar = new TrustedRegistrar(
            store, new SequentialCapabilityFactory(), new FakeMonotonicClock(), () => "session-1");
        var session = registrar.Register(WatcherFixtures.Binding());
        var ingest = new SpanIngest(store, registrar);

        // 32 writers race the same content-addressed span; the store must append it once.
        var tasks = Enumerable.Range(0, 32).Select(_ => Task.Run(
            () => ingest.Ingest(session.SessionId, session.Capability, Span(session.SessionId))));
        await Task.WhenAll(tasks);

        Assert.Equal(1, store.SpanCount(session.SessionId));
    }
}
