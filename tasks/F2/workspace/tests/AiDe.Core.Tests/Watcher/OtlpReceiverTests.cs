using System.Net;
using System.Net.Sockets;
using System.Text;
using AiDe.Core.Watcher;

namespace AiDe.Core.Tests.Watcher;

/// <summary>
/// LK-OTLP-01..12 - the OTLP receiver (design-watcher-otlp-receiver). Deterministic units for the
/// stdlib parser, the token-&gt;capability handling, and the body cap; plus one real-loopback D4 test that
/// proves the HTTP leg end to end.
/// </summary>
public sealed class OtlpReceiverTests
{
    private static readonly DateTimeOffset At = DateTimeOffset.UnixEpoch;

    private static string OtlpJson(string sessionId, string source = "span-a",
        string? harness = "claude-code", string? model = "claude-opus-4-8", string name = "chat.completion")
    {
        var resourceAttrs = harness is null ? "" :
            $$"""{ "key": "service.name", "value": { "stringValue": "{{harness}}" } },""";
        var modelAttr = model is null ? "" :
            $$"""{ "key": "gen_ai.request.model", "value": { "stringValue": "{{model}}" } },""";
        return $$"""
        {
          "resourceSpans": [{
            "resource": { "attributes": [ {{resourceAttrs}} { "key": "service.version", "value": { "stringValue": "1.0.0" } } ] },
            "scopeSpans": [{ "spans": [{
              "traceId": "a6651377534188dcca9aa2f3db16f798",
              "spanId": "cca9aa2f3db16f79",
              "name": "{{name}}",
              "attributes": [ {{modelAttr}} { "key": "session.id", "value": { "stringValue": "{{sessionId}}" } },
                              { "key": "src", "value": { "stringValue": "{{source}}" } } ]
            }]}]
          }]
        }
        """;
    }

    // --- Parser (D1) --------------------------------------------------------------------------

    [Fact]
    public void Parse_ValidSpan_MergesResourceAndSpanAttributes()
    {
        var spans = OtlpJsonParser.Parse(OtlpJson("cc-7f3a"));

        var span = Assert.Single(spans);
        Assert.Equal("a6651377534188dcca9aa2f3db16f798", span.TraceId);
        Assert.Equal("cca9aa2f3db16f79", span.SpanId);
        Assert.Equal("chat.completion", span.OperationName);
        Assert.Equal("cc-7f3a", span.Attributes[OtelAttributes.SessionId]);
        Assert.Equal("claude-code", span.Attributes[OtelAttributes.ServiceName]);
        Assert.Equal("claude-opus-4-8", span.Attributes[OtelAttributes.GenAiModel]);
    }

    [Fact]
    public void Parse_MalformedJson_ReturnsEmpty()
    {
        Assert.Empty(OtlpJsonParser.Parse("{ not json"));
        Assert.Empty(OtlpJsonParser.Parse(""));
    }

    [Fact]
    public void Parse_NoResourceSpans_ReturnsEmpty()
    {
        Assert.Empty(OtlpJsonParser.Parse("{\"resourceSpans\":[]}"));
        Assert.Empty(OtlpJsonParser.Parse("{}"));
    }

    [Fact]
    public void Parse_MissingSessionId_StillParses_ButMapperRejectsLater()
    {
        var json = OtlpJson("ignored").Replace("session.id", "not.session");
        var span = Assert.Single(OtlpJsonParser.Parse(json));

        var ex = Assert.Throws<WatcherException>(() => OtelSpanMapper.MapSpan(span, At));
        Assert.Equal(WatcherErrorCodes.MalformedEvent, ex.Code);
    }

    // --- ReadCapped (D1) ----------------------------------------------------------------------

    [Fact]
    public void ReadCapped_UnderCap_ReturnsBody()
    {
        using var s = new MemoryStream(Encoding.UTF8.GetBytes("hello"));
        Assert.Equal("hello", OtlpHttpReceiver.ReadCapped(s, 5, 1024));
    }

    [Fact]
    public void ReadCapped_DeclaredLengthOverCap_ReturnsNull()
    {
        using var s = new MemoryStream(Encoding.UTF8.GetBytes("hello"));
        Assert.Null(OtlpHttpReceiver.ReadCapped(s, declaredLength: 5000, maxBytes: 8));
    }

    [Fact]
    public void ReadCapped_ActualBodyOverCap_ReturnsNull()
    {
        using var s = new MemoryStream(Encoding.UTF8.GetBytes(new string('x', 100)));
        // declaredLength unknown (-1, chunked): the read loop must still stop at the cap.
        Assert.Null(OtlpHttpReceiver.ReadCapped(s, declaredLength: -1, maxBytes: 8));
    }

    // --- HandleExport (D1, no network) --------------------------------------------------------

    private static (OtlpHttpReceiver receiver, IngestHost host, InMemoryWatcherObservationStore store, RegisteredSession session, string token)
        NewReceiver()
    {
        var store = new InMemoryWatcherObservationStore();
        var registrar = new TrustedRegistrar(store, new SequentialCapabilityFactory(), new FakeMonotonicClock(), () => "cc-1");
        var host = new IngestHost(store, registrar, new FixedTimeProvider(At));
        var session = host.Register(WatcherFixtures.HarnessRegistration());
        var tokens = new SessionTokenRegistry();
        const string token = "boot-token-1";
        tokens.Register(token, session.Capability);
        var receiver = new OtlpHttpReceiver(host, tokens, "http://127.0.0.1:0/"); // prefix unused by HandleExport
        return (receiver, host, store, session, token);
    }

    [Fact]
    public void HandleExport_ValidToken_EnqueuesAndIngests()
    {
        var (receiver, host, store, session, token) = NewReceiver();

        receiver.HandleExport(token, OtlpJson(session.SessionId));
        host.DrainAvailable();

        Assert.Equal(1, receiver.Stats.Received);
        Assert.Equal(1, store.SpanCount(session.SessionId));
    }

    [Fact]
    public void HandleExport_UnknownToken_IsUnauthenticated_AndEnqueuesNothing()
    {
        var (receiver, host, store, session, _) = NewReceiver();

        receiver.HandleExport("not-a-real-token", OtlpJson(session.SessionId));
        host.DrainAvailable();

        Assert.Equal(1, receiver.Stats.Unauthenticated);
        Assert.Equal(0, receiver.Stats.Received);
        Assert.Equal(0, store.SpanCount(session.SessionId));
    }

    [Fact]
    public void HandleExport_NullToken_IsUnauthenticated()
    {
        var (receiver, _, _, session, _) = NewReceiver();

        receiver.HandleExport(null, OtlpJson(session.SessionId));

        Assert.Equal(1, receiver.Stats.Unauthenticated);
    }

    [Fact]
    public void HandleExport_ValidTokenButMalformedBody_EnqueuesNothing()
    {
        var (receiver, host, store, session, token) = NewReceiver();

        receiver.HandleExport(token, "{ not json");
        host.DrainAvailable();

        Assert.Equal(0, receiver.Stats.Received);
        Assert.Equal(0, store.SpanCount(session.SessionId));
    }

    // --- D4 integration: a real loopback POST proves the HTTP leg ------------------------------

    [Fact]
    public async Task RealLoopbackPost_ValidToken_IngestsSpanEndToEnd()
    {
        var store = new InMemoryWatcherObservationStore();
        var registrar = new TrustedRegistrar(store, new SequentialCapabilityFactory(), new FakeMonotonicClock(), () => "cc-1");
        var host = new IngestHost(store, registrar, new FixedTimeProvider(At));
        var session = host.Register(WatcherFixtures.HarnessRegistration());
        var tokens = new SessionTokenRegistry();
        const string token = "boot-token-1";
        tokens.Register(token, session.Capability);

        var port = FreeLoopbackPort();
        var prefix = $"http://127.0.0.1:{port}/";
        using var receiver = new OtlpHttpReceiver(host, tokens, prefix);
        using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(15));
        // A bind failure (a CI box needing a urlacl) surfaces loudly here, never as a false pass.
        var run = receiver.RunAsync(cts.Token);

        using (var client = new HttpClient())
        {
            using var content = new StringContent(OtlpJson(session.SessionId), Encoding.UTF8, "application/json");
            content.Headers.Add("x-loomkeeper-session-token", token);
            using var response = await client.PostAsync($"{prefix}v1/traces", content, cts.Token);
            Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        }

        host.DrainAvailable();
        Assert.Equal(1, receiver.Stats.Received);
        Assert.Equal(1, store.SpanCount(session.SessionId));

        await cts.CancelAsync();
        try { await run; } catch (OperationCanceledException) { }
    }

    [Fact]
    public async Task RealLoopbackPost_UnknownToken_IsDroppedEndToEnd()
    {
        var store = new InMemoryWatcherObservationStore();
        var registrar = new TrustedRegistrar(store, new SequentialCapabilityFactory(), new FakeMonotonicClock(), () => "cc-1");
        var host = new IngestHost(store, registrar, new FixedTimeProvider(At));
        var session = host.Register(WatcherFixtures.HarnessRegistration());
        var tokens = new SessionTokenRegistry(); // deliberately empty: no token registered

        var port = FreeLoopbackPort();
        var prefix = $"http://127.0.0.1:{port}/";
        using var receiver = new OtlpHttpReceiver(host, tokens, prefix);
        using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(15));
        var run = receiver.RunAsync(cts.Token);

        using (var client = new HttpClient())
        {
            using var content = new StringContent(OtlpJson(session.SessionId), Encoding.UTF8, "application/json");
            content.Headers.Add("x-loomkeeper-session-token", "forged-token");
            using var response = await client.PostAsync($"{prefix}v1/traces", content, cts.Token);
            Assert.Equal(HttpStatusCode.OK, response.StatusCode); // OTLP is answered 200 even when dropped
        }

        host.DrainAvailable();
        Assert.Equal(1, receiver.Stats.Unauthenticated);
        Assert.Equal(0, store.SpanCount(session.SessionId));

        await cts.CancelAsync();
        try { await run; } catch (OperationCanceledException) { }
    }

    private static int FreeLoopbackPort()
    {
        using var probe = new TcpListener(IPAddress.Loopback, 0);
        probe.Start();
        var port = ((IPEndPoint)probe.LocalEndpoint).Port;
        probe.Stop();
        return port;
    }
}
