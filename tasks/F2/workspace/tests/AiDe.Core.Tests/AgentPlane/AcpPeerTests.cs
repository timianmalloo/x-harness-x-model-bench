using System.Text.Json.Nodes;
using AiDe.Core.AgentPlane;

namespace AiDe.Core.Tests.AgentPlane;

/// <summary>
/// The bidirectional ACP peer: newline-delimited JSON over a child process's stdio, with the agent
/// calling <i>us</i> as often as we call it.
/// </summary>
/// <remarks>
/// <para><b>What <c>probe-write.js</c> did not solve.</b> The working 36-line probe correlated
/// replies by <c>m.id === 1 | 2 | 3</c> — three hard-coded integers for three known requests. That
/// cannot survive a fourth request, a concurrent one, or a string id, and — the failure that
/// actually bites — it cannot tell an inbound <i>request</i> from a reply to an outbound one. The
/// design under test replaces it with two rules: a frame carrying <c>method</c> is inbound, and a
/// frame carrying an <c>id</c> <b>key</b> (never a truthy value) is a request that must be answered.
/// </para>
///
/// <para><b>Inherited from <c>src/AiDe.Mcp/Program.cs</c>, deliberately:</b> stdout is the protocol
/// and diagnostics go to stderr; one bad message never kills the loop; an unknown method is
/// <i>answered</i>, not ignored — silence looks like a hung peer and the other side cannot tell the
/// two apart.</para>
/// </remarks>
public sealed class AcpPeerTests
{
    private const string AgentMessageFrame =
        """{"jsonrpc":"2.0","method":"session/update","params":{"update":{"sessionUpdate":"agent_message_chunk"}}}""";

    private sealed record Harness(
        AcpPeer Peer, PushTextReader Input, RecordingTextWriter Output, List<string> Diagnostics);

    private static Harness New(AcpPeerOptions? options = null)
    {
        var input = new PushTextReader();
        AcpPeer? peer = null;
        var output = new RecordingTextWriter(() => peer!.Events.Published);
        var diagnostics = new List<string>();
        peer = new AcpPeer(
            input,
            output,
            new AcpRunEventMapper("run-1", "lane-1"),
            options: options,
            diagnostics: diagnostics.Add);
        return new Harness(peer, input, output, diagnostics);
    }

    /// <summary>Feeds every line, closes the stream, and waits for the loop to finish.</summary>
    private static async Task Replay(Harness harness, params string[] lines)
    {
        var run = harness.Peer.RunAsync();
        foreach (var line in lines)
        {
            harness.Input.Push(line + "\n");
        }

        harness.Input.EndOfStream();
        await run;
    }

    private static JsonObject Parse(string line) => JsonNode.Parse(line)!.AsObject();

    // ---------------------------------------------------------------- clause 2: id 0 is an id

    /// <summary>
    /// <b><c>id: 0</c> is a valid inbound request id</b>, and the corpus contains one.
    /// </summary>
    /// <remarks>
    /// <c>frames/write.jsonl:12</c> is a real <c>session/request_permission</c> carrying
    /// <c>"id":0</c>. A correlation table keyed on truthiness — <c>if (id)</c>, <c>id != 0</c>, a
    /// <c>long</c> defaulting to zero for "absent" — reads that frame as a notification, never
    /// answers it, and the agent waits forever on a permission prompt that was in fact delivered.
    /// The bug is invisible in every other frame in the corpus, because every other id is non-zero.
    /// </remarks>
    [Fact]
    public async Task AnInboundRequestWithIdZeroIsAnsweredRatherThanReadAsANotification()
    {
        var permission = AcpCorpus.Lines("write.jsonl")
            .First(l => l.Contains("\"method\":\"session/request_permission\"", StringComparison.Ordinal));
        Assert.Contains("\"id\":0", permission, StringComparison.Ordinal);

        var harness = New();
        harness.Peer.InboundHandler = (_, _) => new JsonObject { ["outcome"] = "rejected" };
        await Replay(harness, permission);

        var answer = Assert.Single(harness.Output.Lines);
        var frame = Parse(answer.Line);
        Assert.Equal(0, frame["id"]!.GetValue<int>());
        Assert.NotNull(frame["result"]);
        Assert.Equal(1, harness.Peer.Counters.InboundRequestsAnswered);
        Assert.Equal(0, harness.Peer.Counters.Notifications);
    }

    /// <summary>A frame with no <c>id</c> key is a notification and MUST NOT be answered.</summary>
    [Fact]
    public async Task ANotificationIsNotAnswered()
    {
        var harness = New();
        harness.Peer.InboundHandler = (_, _) => new JsonObject();
        await Replay(harness, AgentMessageFrame);

        Assert.Empty(harness.Output.Lines);
        Assert.Equal(1, harness.Peer.Counters.Notifications);
    }

    /// <summary>An unknown inbound method is answered <c>-32601</c>, never ignored.</summary>
    [Fact]
    public async Task AnUnknownInboundMethodIsAnsweredNotIgnored()
    {
        var harness = New();
        await Replay(harness, """{"jsonrpc":"2.0","id":7,"method":"terminal/create","params":{}}""");

        var answer = Assert.Single(harness.Output.Lines);
        var frame = Parse(answer.Line);
        Assert.Equal(-32601, frame["error"]!["code"]!.GetValue<int>());
        Assert.Contains("terminal/create", frame["error"]!["message"]!.GetValue<string>(), StringComparison.Ordinal);
        Assert.Equal(1, harness.Peer.Counters.UnknownMethodsAnswered);
    }

    // ---------------------------------------------------------------- correlation, both directions

    /// <summary>An outbound request is correlated to its reply by id, not by call order.</summary>
    [Fact]
    public async Task AReplyIsCorrelatedToItsOutboundRequestById()
    {
        var harness = New();
        var run = harness.Peer.RunAsync();

        var first = harness.Peer.RequestAsync("initialize", new JsonObject { ["protocolVersion"] = 1 });
        var second = harness.Peer.RequestAsync("session/new", new JsonObject { ["cwd"] = "/tmp/x" });

        // Answered out of order on purpose: arrival order is not the correlation.
        harness.Input.Push("""{"jsonrpc":"2.0","id":2,"result":{"sessionId":"s-2"}}""" + "\n");
        harness.Input.Push("""{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":1}}""" + "\n");

        Assert.Equal("s-2", (await second)["sessionId"]!.GetValue<string>());
        Assert.Equal(1, (await first)["protocolVersion"]!.GetValue<int>());

        harness.Input.EndOfStream();
        await run;
    }

    /// <summary>A reply the peer never asked for is counted and survived, not crashed on.</summary>
    [Fact]
    public async Task AReplyToAnIdNobodySentIsCountedAndTheLoopSurvives()
    {
        var harness = New();
        await Replay(
            harness,
            """{"jsonrpc":"2.0","id":99,"result":{}}""",
            AgentMessageFrame);

        Assert.Equal(1, harness.Peer.Counters.UnmatchedResponses);
        Assert.Equal(2, harness.Peer.Counters.FramesRead);
    }

    /// <summary>A JSON-RPC error reply becomes a named refusal, not a null result.</summary>
    [Fact]
    public async Task AnErrorReplyBecomesANamedRefusalCarryingTheWireCode()
    {
        var harness = New();
        var run = harness.Peer.RunAsync();
        var request = harness.Peer.RequestAsync("session/new", new JsonObject { ["cwd"] = "relative" });

        harness.Input.Push(
            """{"jsonrpc":"2.0","id":1,"error":{"code":-32602,"message":"Invalid params: cwd must be an absolute path"}}"""
            + "\n");

        var error = await Assert.ThrowsAsync<AgentPlaneException>(async () => await request);
        Assert.Equal(AgentPlaneErrorCodes.EngineReturnedError, error.Code);
        Assert.Contains("-32602", error.Message, StringComparison.Ordinal);
        Assert.Contains("absolute path", error.Message, StringComparison.Ordinal);

        harness.Input.EndOfStream();
        await run;
    }

    // ---------------------------------------------------------------- clause 4: subprocess failures

    /// <summary>
    /// <b>Child crash mid-session.</b> Every outstanding request is failed with a named reason
    /// rather than left pending — a peer waiting on a process that has gone is the worst of both.
    /// </summary>
    [Fact]
    public async Task WhenTheChildDiesMidSessionEveryPendingRequestFailsWithANamedReason()
    {
        var harness = New();
        var run = harness.Peer.RunAsync();
        var request = harness.Peer.RequestAsync("session/prompt", new JsonObject());

        harness.Input.EndOfStream();
        await run;

        var error = await Assert.ThrowsAsync<AgentPlaneException>(async () => await request);
        Assert.Equal(AgentPlaneErrorCodes.EngineStreamEnded, error.Code);
        Assert.Contains("session/prompt", error.Message, StringComparison.Ordinal);
    }

    /// <summary><b>Partial line.</b> A tail with no newline is not a frame; it is counted and named.</summary>
    [Fact]
    public async Task AnUnterminatedTailIsNeverParsedAsAFrame()
    {
        const string tail = """{"jsonrpc":"2.0","method":"ses""";
        var harness = New();
        var run = harness.Peer.RunAsync();
        harness.Input.Push(AgentMessageFrame + "\n");
        harness.Input.Push("""{"jsonrpc":"2.0","method":"ses""");
        harness.Input.EndOfStream();
        await run;

        Assert.Equal(1, harness.Peer.Counters.FramesRead);
        Assert.Equal(0, harness.Peer.Counters.MalformedFrames);
        Assert.Equal(tail.Length, harness.Peer.Counters.UnterminatedTailChars);
        Assert.Contains(harness.Diagnostics, d => d.Contains("unterminated", StringComparison.Ordinal));
    }

    /// <summary>A frame split across chunk boundaries is still one frame.</summary>
    [Fact]
    public async Task AFrameSplitAcrossChunksIsReassembled()
    {
        var harness = New();
        var run = harness.Peer.RunAsync();
        harness.Input.Push(AgentMessageFrame[..40]);
        harness.Input.Push(AgentMessageFrame[40..] + "\n");
        harness.Input.EndOfStream();
        await run;

        Assert.Equal(1, harness.Peer.Counters.FramesRead);
        Assert.Equal(0, harness.Peer.Counters.MalformedFrames);
    }

    /// <summary>
    /// <b>Over-long line.</b> Past the cap the frame is refused, counted, and the splitter
    /// resynchronizes at the next newline — so the frame <i>after</i> the offender still arrives.
    /// </summary>
    [Fact]
    public async Task AnOverLongLineIsRefusedAndTheSplitterResynchronizes()
    {
        // The cap sits above an ordinary frame and below the offender, so the case separates the
        // two rather than refusing both.
        const int cap = 200;
        Assert.True(AgentMessageFrame.Length < cap, "the ordinary frame must fit under the cap");

        var harness = New(new AcpPeerOptions { MaxFrameChars = cap });
        await Replay(
            harness,
            "{\"pad\":\"" + new string('x', 400) + "\"}",
            AgentMessageFrame);

        Assert.Equal(1, harness.Peer.Counters.OverLongFrames);
        Assert.Equal(1, harness.Peer.Counters.FramesRead);
        Assert.Contains(harness.Diagnostics, d => d.Contains("200", StringComparison.Ordinal));
    }

    /// <summary><b>One bad message never kills the loop</b> — inherited from the MCP server.</summary>
    [Fact]
    public async Task AMalformedFrameIsCountedAndTheLoopKeepsReading()
    {
        var harness = New();
        await Replay(
            harness,
            "{not json",
            "[1,2,3]",
            AgentMessageFrame);

        Assert.Equal(2, harness.Peer.Counters.MalformedFrames);
        Assert.Equal(1, harness.Peer.Counters.FramesRead);
        Assert.Equal(1, harness.Peer.Events.Published);
    }

    /// <summary>
    /// <b>Hung child.</b> A request that is never answered fails at the stated timeout instead of
    /// holding the lane open forever.
    /// </summary>
    [Fact]
    public async Task AHungChildFailsTheRequestAtTheStatedTimeout()
    {
        var harness = New();
        var run = harness.Peer.RunAsync();

        var request = harness.Peer.RequestAsync(
            "session/new", new JsonObject(), timeout: TimeSpan.FromMilliseconds(1));

        var error = await Assert.ThrowsAsync<AgentPlaneException>(async () => await request);
        Assert.Equal(AgentPlaneErrorCodes.EngineRequestTimedOut, error.Code);
        Assert.Contains("session/new", error.Message, StringComparison.Ordinal);

        harness.Input.EndOfStream();
        await run;
    }

    /// <summary>The production bounds are stated values, not numbers buried in a call site.</summary>
    [Fact]
    public void TheProductionTimeoutsAndFrameCapAreStatedValues()
    {
        Assert.Equal(TimeSpan.FromSeconds(60), AcpPeerOptions.DefaultRequestTimeout);
        Assert.Equal(TimeSpan.FromMinutes(15), AcpPeerOptions.DefaultPromptTimeout);
        Assert.Equal(4 * 1024 * 1024, AcpPeerOptions.DefaultMaxFrameChars);
        Assert.Equal(1024, AcpPeerOptions.DefaultEventQueueCapacity);
    }

    // ---------------------------------------------------------------- clause 5: the ordinal

    /// <summary>
    /// <b>The required deterministic ordinal.</b> The normalized run event for a tool call is
    /// observable <i>before</i> the peer's response to the next inbound request carrying the same
    /// call id.
    /// </summary>
    /// <remarks>
    /// <para>This is Ruling 11's assertion, and it is deliberately not a stopwatch. A literal
    /// <c>elapsed &lt; 250 ms</c> makes the runner part of the verdict (DC-107); an ordinal is true
    /// or false on any hardware, and it is the property that actually matters — a surface that
    /// renders the permission prompt before the tool call that caused it is wrong however fast it
    /// was.</para>
    ///
    /// <para>The mechanism under test is that the read loop <b>normalizes and publishes before it
    /// dispatches</b>. Move the publish after the response write and this inverts.</para>
    /// </remarks>
    [Fact]
    public async Task TheRunEventIsObservableBeforeTheResponseToTheNextRequestForTheSameCallId()
    {
        var received = AcpCorpus.Lines("write.jsonl");
        var permission = received.First(l => l.Contains("\"session/request_permission\"", StringComparison.Ordinal));
        var callId = Parse(permission)["params"]!["toolCall"]!["toolCallId"]!.GetValue<string>();
        var upTo = received.TakeWhile(l => l != permission).Append(permission).ToArray();

        var harness = New(new AcpPeerOptions { EventQueueCapacity = 512 });
        harness.Peer.InboundHandler = (_, _) => new JsonObject
        {
            ["outcome"] = new JsonObject { ["outcome"] = "selected", ["optionId"] = "reject" },
        };
        await Replay(harness, upTo);

        var answer = Assert.Single(harness.Output.Lines);
        Assert.Equal(0, Parse(answer.Line)["id"]!.GetValue<int>());

        var events = Drain(harness.Peer);
        var toolCall = events.First(e => e.Event.Kind == "tool.call" && Mentions(e, callId));
        var permissionEvent = events.First(e => e.Event.Kind == "permission.request" && Mentions(e, callId));

        // Snapshot = how many events had been published at the instant the response was written.
        Assert.True(
            answer.Snapshot >= toolCall.Event.Seq,
            $"the tool.call event for {callId} was seq {toolCall.Event.Seq}, but only {answer.Snapshot} events "
            + "had been published when the response went out — the ordinal is inverted");
        Assert.True(
            answer.Snapshot >= permissionEvent.Event.Seq,
            $"the permission.request event for {callId} was seq {permissionEvent.Event.Seq}, but only "
            + $"{answer.Snapshot} events had been published when the response went out");
    }

    /// <summary>The latency measurement exists and is a number.</summary>
    [Fact]
    public async Task EveryPublishedEventCarriesANormalizationLatencyThatIsANumber()
    {
        var harness = New();
        await Replay(harness, AgentMessageFrame);

        var observed = Assert.Single(Drain(harness.Peer));
        Assert.NotNull(observed.ReceivedAt);
        Assert.NotNull(observed.NormalizationLatency);
        Assert.EndsWith(" ms", observed.DescribeLatency(), StringComparison.Ordinal);
    }

    /// <summary>
    /// With the receipt timestamp removed the measurement reads <b>"not recorded", never 0</b> (IO12).
    /// </summary>
    [Fact]
    public void WithNoReceiptTimestampTheLatencyReadsNotRecordedRatherThanZero()
    {
        var evt = new RunEvent("run-1", "lane-1", null, 1, DateTimeOffset.UnixEpoch, "acp.frame", null, [], []);

        var observed = ObservedRunEvent.From(evt, receivedAt: null, normalizedAt: DateTimeOffset.UnixEpoch);

        Assert.Null(observed.NormalizationLatency);
        Assert.Equal(ObservedRunEvent.NotRecorded, observed.DescribeLatency());
        Assert.NotEqual("0 ms", observed.DescribeLatency());
    }

    // ---------------------------------------------------------------- the real corpus

    /// <summary>
    /// Every received frame in the corpus goes through the peer: nothing malformed, nothing dropped,
    /// one run event each.
    /// </summary>
    /// <remarks>
    /// The oracle is the wire, not the author. These are the bytes
    /// <c>claude-agent-acp@0.75.1</c> actually wrote (<c>frames/PROVENANCE.md</c>), so a framing
    /// assumption the adapter does not share fails here rather than in a live run.
    /// </remarks>
    [Theory]
    [InlineData("read.jsonl", 22)]
    [InlineData("write.jsonl", 59)]
    public async Task EveryReceivedFrameInTheCorpusBecomesExactlyOneRunEvent(string fileName, int expected)
    {
        var harness = New(new AcpPeerOptions { EventQueueCapacity = 512 });
        harness.Peer.InboundHandler = (_, _) => new JsonObject { ["outcome"] = "rejected" };
        await Replay(harness, [.. AcpCorpus.Lines(fileName)]);

        Assert.Equal(expected, harness.Peer.Counters.FramesRead);
        Assert.Equal(expected, harness.Peer.Events.Published);
        Assert.Equal(0, harness.Peer.Counters.MalformedFrames);
        Assert.Equal(0, harness.Peer.Counters.OverLongFrames);
        Assert.Equal(0, harness.Peer.Events.Dropped);
    }

    /// <summary>
    /// The <c>_auth/status_update</c> extension frame is observed as it goes past, so the ToS gate
    /// has a measurement rather than a configuration reading.
    /// </summary>
    [Fact]
    public async Task TheAuthStatusExtensionFrameIsObservedFromTheWire()
    {
        var auth = AcpCorpus.Lines("read.jsonl")
            .First(l => l.Contains("_auth/status_update", StringComparison.Ordinal));

        var harness = New();
        Assert.Null(harness.Peer.ObservedAuth);
        await Replay(harness, auth);

        var observed = harness.Peer.ObservedAuth;
        Assert.NotNull(observed);
        Assert.Equal(ObservedAuthStatus.AccountKind, observed.Kind);
        Assert.True(observed.IsSubscription);
        Assert.Equal("Claude Max", observed.Label);
    }

    private static bool Mentions(ObservedRunEvent observed, string callId)
        => observed.Event.Body.ToJsonString().Contains(callId, StringComparison.Ordinal)
            || observed.Event.Ext.ToJsonString().Contains(callId, StringComparison.Ordinal);

    private static List<ObservedRunEvent> Drain(AcpPeer peer)
    {
        var events = new List<ObservedRunEvent>();
        while (peer.Events.Reader.TryRead(out var observed))
        {
            events.Add(observed);
        }

        return events;
    }
}
