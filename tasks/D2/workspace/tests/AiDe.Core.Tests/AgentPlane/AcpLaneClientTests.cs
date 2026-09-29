using System.Text.Json.Nodes;
using AiDe.Core.AgentPlane;

namespace AiDe.Core.Tests.AgentPlane;

/// <summary>
/// The ACP semantics layered on the peer: the handshake, the session, and the permission answer.
/// </summary>
/// <remarks>
/// <para><b>Why the echoed protocol version is asserted rather than read.</b> Schema v2 alpha is in
/// flight and the adapters publish near-daily (spike residual risk 5). Sending
/// <c>protocolVersion: 1</c> and not checking what came back is how a client keeps speaking v1 to a
/// peer that answered v2 — every frame parses, and the meanings have moved.</para>
///
/// <para><b>Why the relative <c>cwd</c> is refused locally.</b> The adapter answers
/// <c>-32602 "`cwd` must be an absolute path"</c>, which is a fine error to receive and a poor one
/// to depend on: it arrives after a session was attempted, names no caller, and would change with
/// the adapter. Refusing before the wire keeps the reason attached to the call that made it.</para>
/// </remarks>
public sealed class AcpLaneClientTests
{
    private sealed record Harness(AcpLaneClient Client, AcpPeer Peer, PushTextReader Input, RecordingTextWriter Output);

    private static Harness New(AcpClientCapabilities? capabilities = null, Func<JsonObject, string>? permission = null)
    {
        var input = new PushTextReader();
        var output = new RecordingTextWriter();
        var peer = new AcpPeer(input, output, new AcpRunEventMapper("run-1", "lane-1"));
        return new Harness(new AcpLaneClient(peer, capabilities, permission), peer, input, output);
    }

    private static JsonObject Parse(string line) => JsonNode.Parse(line)!.AsObject();

    /// <summary><c>initialize</c> pins version 1 and declares exactly the capabilities it implements.</summary>
    [Fact]
    public async Task InitializePinsProtocolVersionOneAndDeclaresOnlyTheCapabilitiesItImplements()
    {
        var harness = New();
        var run = harness.Peer.RunAsync();
        var initialize = harness.Client.InitializeAsync();

        harness.Input.Push("""{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":1,"authMethods":[]}}""" + "\n");
        await initialize;

        var sent = Parse(harness.Output.Lines[0].Line);
        Assert.Equal("initialize", sent["method"]!.GetValue<string>());
        Assert.Equal(AcpLaneClient.ProtocolVersion, sent["params"]!["protocolVersion"]!.GetValue<int>());

        var fs = sent["params"]!["clientCapabilities"]!["fs"]!;
        Assert.False(fs["readTextFile"]!.GetValue<bool>());
        Assert.False(fs["writeTextFile"]!.GetValue<bool>());
        Assert.False(sent["params"]!["clientCapabilities"]!["terminal"]!.GetValue<bool>());

        harness.Input.EndOfStream();
        await run;
    }

    /// <summary>A different echoed version is refused, naming both values.</summary>
    [Fact]
    public async Task AnEchoedProtocolVersionThatIsNotOneIsRefused()
    {
        var harness = New();
        var run = harness.Peer.RunAsync();
        var initialize = harness.Client.InitializeAsync();

        harness.Input.Push("""{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":2}}""" + "\n");

        var error = await Assert.ThrowsAsync<AgentPlaneException>(async () => await initialize);
        Assert.Equal(AgentPlaneErrorCodes.ProtocolVersionMismatch, error.Code);
        Assert.Contains("1", error.Message, StringComparison.Ordinal);
        Assert.Contains("2", error.Message, StringComparison.Ordinal);

        harness.Input.EndOfStream();
        await run;
    }

    /// <summary>An absent echoed version is "not recorded", which is refused — never read as agreement.</summary>
    [Fact]
    public async Task AnAbsentEchoedProtocolVersionIsRefusedRatherThanAssumedToAgree()
    {
        var harness = New();
        var run = harness.Peer.RunAsync();
        var initialize = harness.Client.InitializeAsync();

        harness.Input.Push("""{"jsonrpc":"2.0","id":1,"result":{"authMethods":[]}}""" + "\n");

        var error = await Assert.ThrowsAsync<AgentPlaneException>(async () => await initialize);
        Assert.Equal(AgentPlaneErrorCodes.ProtocolVersionMismatch, error.Code);
        Assert.Contains("not recorded", error.Message, StringComparison.Ordinal);

        harness.Input.EndOfStream();
        await run;
    }

    /// <summary>A relative <c>cwd</c> never reaches the wire.</summary>
    [Fact]
    public async Task ARelativeSessionCwdIsRefusedBeforeAnythingIsSent()
    {
        var harness = New();

        var error = await Assert.ThrowsAsync<AgentPlaneException>(
            () => harness.Client.NewSessionAsync("spikes/acp-subscription-lane"));

        Assert.Equal(AgentPlaneErrorCodes.SessionCwdNotAbsolute, error.Code);
        Assert.Contains("spikes/acp-subscription-lane", error.Message, StringComparison.Ordinal);
        Assert.Empty(harness.Output.Lines);
    }

    /// <summary>An absolute <c>cwd</c> is sent verbatim, and the session id comes back.</summary>
    [Fact]
    public async Task AnAbsoluteSessionCwdIsSentVerbatimAndTheSessionIdIsReturned()
    {
        var absolute = Path.GetFullPath(Path.GetTempPath());
        var harness = New();
        var run = harness.Peer.RunAsync();
        var session = harness.Client.NewSessionAsync(absolute);

        harness.Input.Push("""{"jsonrpc":"2.0","id":1,"result":{"sessionId":"s-77"}}""" + "\n");

        Assert.Equal("s-77", await session);
        var sent = Parse(harness.Output.Lines[0].Line);
        Assert.Equal("session/new", sent["method"]!.GetValue<string>());
        Assert.Equal(absolute, sent["params"]!["cwd"]!.GetValue<string>());

        harness.Input.EndOfStream();
        await run;
    }

    /// <summary>
    /// With no session options the frame is <b>byte for byte</b> the one every prior run sent —
    /// <c>cwd</c> and an empty <c>mcpServers</c>, no <c>_meta</c> — whether the record is absent or
    /// empty. Pinned as an exact string, so the pin below cannot widen the null path by accident.
    /// </summary>
    [Theory]
    [InlineData(false)]
    [InlineData(true)]
    public async Task WithoutSessionOptionsTheSessionNewFrameIsByteForByteTheOneEveryPriorRunSent(bool emptyRecord)
    {
        var absolute = Path.GetFullPath(Path.GetTempPath());
        var harness = New();
        var run = harness.Peer.RunAsync();
        var session = emptyRecord
            ? harness.Client.NewSessionAsync(absolute, new LaneSessionOptions())
            : harness.Client.NewSessionAsync(absolute);

        harness.Input.Push("""{"jsonrpc":"2.0","id":1,"result":{"sessionId":"s-1"}}""" + "\n");
        await session;

        var expected = """{"jsonrpc":"2.0","id":1,"method":"session/new","params":{"cwd":"""
            + JsonValue.Create(absolute)!.ToJsonString()
            + ""","mcpServers":[]}}""";
        Assert.Equal(expected, Assert.Single(harness.Output.Lines).Line);

        harness.Input.EndOfStream();
        await run;
    }

    /// <summary>
    /// Ruling 71: the governed lane pins its shell off through the adapter's extension slot —
    /// <c>_meta.claudeCode.options.disallowedTools: ["Bash"]</c> (adapter 0.75.1,
    /// <c>acp-agent.js:5859-5860</c>, <c>:6007</c>) — on the <b>worktree</b> overload, which is the
    /// governed caller's. The rest of the frame is unchanged, and <c>tools</c> is not sent.
    /// </summary>
    [Fact]
    public async Task TheGovernedLanePinsBashOffThroughTheAdaptersMetaSlot()
    {
        var absolute = Path.GetFullPath(Path.GetTempPath());
        var tree = new ProvisionedWorktree(absolute, "agent/claude-code/lane-0001", absolute, CoordInstalled: false);
        var harness = New();
        var run = harness.Peer.RunAsync();
        var session = harness.Client.NewSessionAsync(tree, new LaneSessionOptions(DisallowedTools: ["Bash"]));

        harness.Input.Push("""{"jsonrpc":"2.0","id":1,"result":{"sessionId":"s-2"}}""" + "\n");
        Assert.Equal("s-2", await session);

        var parameters = Parse(Assert.Single(harness.Output.Lines).Line)["params"]!.AsObject();
        Assert.Equal(absolute, parameters["cwd"]!.GetValue<string>());
        Assert.Empty(parameters["mcpServers"]!.AsArray());

        var meta = Assert.IsType<JsonObject>(parameters["_meta"]);
        var options = meta["claudeCode"]!["options"]!.AsObject();
        Assert.Equal(["Bash"], options["disallowedTools"]!.AsArray().Select(n => n!.GetValue<string>()));
        Assert.False(options.ContainsKey("tools"));
        Assert.Equal(["cwd", "mcpServers", "_meta"], parameters.Select(m => m.Key));

        // What the client says it sent IS what went down the wire — the host records the former.
        Assert.Equal(parameters.ToJsonString(), harness.Client.SessionNewParameters?.ToJsonString());

        harness.Input.EndOfStream();
        await run;
    }

    /// <summary>
    /// Ruling 73's pin is the second use of the same argument: a read-only lane sends its whole
    /// disallowed set — every name, in the order given, none dropped or re-spelled — on the plain
    /// <c>cwd</c> overload (there is no worktree to root it in), with <c>tools</c> absent and the
    /// frame's key set unchanged.
    /// </summary>
    /// <remarks>
    /// <b>A control, green before and after CV-0:</b> the client needed no change for the read-only
    /// lane — the set is the host's (<c>GovernedRunHost.ReadOnlyLaneSession</c>, asserted in
    /// <c>TheGovernedLaneHasNoShellTests</c>); what this proves is that a set of any size reaches the
    /// wire as itself.
    /// </remarks>
    [Fact]
    public async Task AReadOnlyLaneSendsItsWholeDisallowedSetOnTheCwdOverload()
    {
        var absolute = Path.GetFullPath(Path.GetTempPath());
        string[] disallowed = ["Write", "Edit", "MultiEdit", "NotebookEdit", "Bash", "REPL", "Agent"];
        var harness = New();
        var run = harness.Peer.RunAsync();
        var session = harness.Client.NewSessionAsync(absolute, new LaneSessionOptions(DisallowedTools: disallowed));

        harness.Input.Push("""{"jsonrpc":"2.0","id":1,"result":{"sessionId":"s-4"}}""" + "\n");
        Assert.Equal("s-4", await session);

        var parameters = Parse(Assert.Single(harness.Output.Lines).Line)["params"]!.AsObject();
        var options = parameters["_meta"]!["claudeCode"]!["options"]!.AsObject();

        Assert.Equal(disallowed, options["disallowedTools"]!.AsArray().Select(n => n!.GetValue<string>()));
        Assert.False(options.ContainsKey("tools"));
        Assert.Equal(["cwd", "mcpServers", "_meta"], parameters.Select(m => m.Key));
        Assert.Empty(parameters["mcpServers"]!.AsArray());
        Assert.Equal(absolute, parameters["cwd"]!.GetValue<string>());

        harness.Input.EndOfStream();
        await run;
    }

    /// <summary>
    /// The other member — Addendum D's C1 sends <c>tools: []</c> to disable every built-in tool. An
    /// empty list is sent as an empty array, not dropped as "nothing to say".
    /// </summary>
    [Fact]
    public async Task AnEmptyToolsListReachesTheMetaSlotAsAnEmptyArray()
    {
        var absolute = Path.GetFullPath(Path.GetTempPath());
        var harness = New();
        var run = harness.Peer.RunAsync();
        var session = harness.Client.NewSessionAsync(absolute, new LaneSessionOptions(Tools: []));

        harness.Input.Push("""{"jsonrpc":"2.0","id":1,"result":{"sessionId":"s-3"}}""" + "\n");
        await session;

        var options = Parse(harness.Output.Lines[0].Line)["params"]!["_meta"]!["claudeCode"]!["options"]!.AsObject();
        Assert.Empty(options["tools"]!.AsArray());
        Assert.False(options.ContainsKey("disallowedTools"));

        harness.Input.EndOfStream();
        await run;
    }

    /// <summary>A blank tool name looks like a pin and pins nothing; it is refused before the wire.</summary>
    [Theory]
    [InlineData("")]
    [InlineData(" ")]
    public async Task ABlankToolNameIsRefusedBeforeAnythingIsSent(string name)
    {
        var harness = New();

        await Assert.ThrowsAsync<ArgumentException>(
            () => harness.Client.NewSessionAsync(Path.GetTempPath(), new LaneSessionOptions(DisallowedTools: [name])));

        Assert.Empty(harness.Output.Lines);
    }

    /// <summary>
    /// The default permission answer is the <b>reject</b> option — fail closed, exactly as the spike
    /// probe did, because an unattended lane that silently accepts every edit is not governed.
    /// </summary>
    [Fact]
    public async Task ThePermissionRequestIsAnsweredWithTheRejectOptionByDefault()
    {
        var permission = AcpCorpus.Lines("write.jsonl")
            .First(l => l.Contains("\"session/request_permission\"", StringComparison.Ordinal));

        var harness = New();
        var run = harness.Peer.RunAsync();
        harness.Input.Push(permission + "\n");
        harness.Input.EndOfStream();
        await run;

        var answer = Parse(Assert.Single(harness.Output.Lines).Line);
        Assert.Equal(0, answer["id"]!.GetValue<int>());
        Assert.Equal("selected", answer["result"]!["outcome"]!["outcome"]!.GetValue<string>());
        Assert.Equal("reject", answer["result"]!["outcome"]!["optionId"]!.GetValue<string>());
    }

    /// <summary>The policy is a decision the caller owns, not a constant baked into the client.</summary>
    [Fact]
    public async Task TheCallerCanChooseADifferentPermissionOption()
    {
        var permission = AcpCorpus.Lines("write.jsonl")
            .First(l => l.Contains("\"session/request_permission\"", StringComparison.Ordinal));

        var harness = New(permission: _ => "allow-once");
        var run = harness.Peer.RunAsync();
        harness.Input.Push(permission + "\n");
        harness.Input.EndOfStream();
        await run;

        var answer = Parse(Assert.Single(harness.Output.Lines).Line);
        Assert.Equal("allow-once", answer["result"]!["outcome"]!["optionId"]!.GetValue<string>());
    }

    /// <summary>
    /// A client that declares a capability it cannot serve is lying on the wire, so the declared set
    /// is data the caller supplies and the default is the honest one.
    /// </summary>
    [Fact]
    public void TheDefaultDeclaredCapabilitiesAreTheOnesPhaseOneActuallyImplements()
    {
        var declared = AcpClientCapabilities.PhaseOne;

        Assert.False(declared.ReadTextFile);
        Assert.False(declared.WriteTextFile);
        Assert.False(declared.Terminal);
    }
}
