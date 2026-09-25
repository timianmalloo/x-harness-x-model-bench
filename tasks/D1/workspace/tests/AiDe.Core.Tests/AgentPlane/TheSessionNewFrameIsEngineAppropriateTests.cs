using System.Text.Json.Nodes;
using AiDe.Core.AgentPlane;

namespace AiDe.Core.Tests.AgentPlane;

/// <summary>
/// The <c>session/new</c> a lane sends is the one its engine accepts: the claude-code adapter's
/// <c>_meta.claudeCode.options</c> pin goes to the claude-code adapter and to nothing else.
/// </summary>
/// <remarks>
/// <para><b>Red-first.</b> Before the client knew its engine, a governed lane on copilot would have
/// sent <c>_meta.claudeCode.options.disallowedTools</c> to a peer that has no such slot — a pin that
/// pins nothing and looks, on the recorded frame, exactly like governance.</para>
///
/// <para><b>What each peer was observed to accept</b> is the frame the spike sent every one of them
/// — <c>{"cwd": …, "mcpServers": []}</c> and nothing else — and every one answered it: copilot,
/// codex, gemini and grok each returned a <c>sessionId</c> or an authentication error, never a
/// parameter error (<c>spikes/engine-backends/&lt;engine&gt;/**/frames.sent.jsonl</c>, 2026-09-14).
/// That frame, byte for byte, is what a non-claude engine gets.</para>
/// </remarks>
public sealed class TheSessionNewFrameIsEngineAppropriateTests
{
    private sealed record Harness(AcpLaneClient Client, AcpPeer Peer, PushTextReader Input, RecordingTextWriter Output, List<string> Diagnostics);

    private static Harness New(EngineRow? engine)
    {
        var input = new PushTextReader();
        var output = new RecordingTextWriter();
        var diagnostics = new List<string>();
        var peer = new AcpPeer(input, output, new AcpRunEventMapper("run-1", "lane-1"));
        return new Harness(new AcpLaneClient(peer, engine: engine, diagnostics: diagnostics.Add), peer, input, output, diagnostics);
    }

    private static readonly LaneSessionOptions GovernedPin = new(DisallowedTools: ["Bash"]) { ThinkingDisplay = LaneSessionOptions.ThinkingSummarized };

    /// <summary>
    /// A non-claude engine's <c>session/new</c> is the ACP-standard frame the spike observed it
    /// accept — <c>cwd</c> and an empty <c>mcpServers</c> — with no <c>_meta</c> at all, even when
    /// the caller hands over the governed lane's pin.
    /// </summary>
    [Theory]
    [InlineData("copilot")]
    [InlineData("codex")]
    [InlineData("gemini")]
    [InlineData("grok")]
    public async Task ANonClaudeEngineGetsTheAcpStandardFrameAndNoClaudeMeta(string engineId)
    {
        var absolute = Path.GetFullPath(Path.GetTempPath());
        var harness = New(EngineCatalog.Find(engineId));
        var run = harness.Peer.RunAsync();
        var session = harness.Client.NewSessionAsync(absolute, GovernedPin);

        harness.Input.Push("""{"jsonrpc":"2.0","id":1,"result":{"sessionId":"s-native"}}""" + "\n");
        Assert.Equal("s-native", await session);

        var expected = """{"jsonrpc":"2.0","id":1,"method":"session/new","params":{"cwd":"""
            + JsonValue.Create(absolute)!.ToJsonString()
            + ""","mcpServers":[]}}""";
        Assert.Equal(expected, Assert.Single(harness.Output.Lines).Line);
        Assert.DoesNotContain("claudeCode", harness.Client.SessionNewParameters!.ToJsonString(), StringComparison.Ordinal);

        // Not sent, and SAID: a pin that vanishes silently is the failure this test exists for.
        var reported = Assert.Single(harness.Diagnostics);
        Assert.Contains(engineId, reported, StringComparison.Ordinal);
        Assert.Contains("not sent", reported, StringComparison.Ordinal);

        harness.Input.EndOfStream();
        await run;
    }

    /// <summary>The claude-code adapter still gets its pin, unchanged, when the client is told its engine.</summary>
    [Fact]
    public async Task TheClaudeCodeAdapterStillGetsItsPin()
    {
        var absolute = Path.GetFullPath(Path.GetTempPath());
        var harness = New(EngineCatalog.Find("claude-code"));
        var run = harness.Peer.RunAsync();
        var session = harness.Client.NewSessionAsync(absolute, GovernedPin);

        harness.Input.Push("""{"jsonrpc":"2.0","id":1,"result":{"sessionId":"s-claude"}}""" + "\n");
        Assert.Equal("s-claude", await session);

        var parameters = JsonNode.Parse(Assert.Single(harness.Output.Lines).Line)!["params"]!.AsObject();
        var options = parameters["_meta"]!["claudeCode"]!["options"]!.AsObject();
        Assert.Equal(["Bash"], options["disallowedTools"]!.AsArray().Select(n => n!.GetValue<string>()));
        Assert.Empty(harness.Diagnostics);

        harness.Input.EndOfStream();
        await run;
    }

    /// <summary>
    /// A client told no engine behaves as every caller before the second launch path did: the
    /// options go to the wire as given. The frame is unchanged so the callers that predate the
    /// catalog's native rows are unchanged — and a host launching a native row passes its row.
    /// </summary>
    [Fact]
    public async Task AClientToldNoEngineSendsTheOptionsAsGiven()
    {
        var absolute = Path.GetFullPath(Path.GetTempPath());
        var harness = New(engine: null);
        var run = harness.Peer.RunAsync();
        var session = harness.Client.NewSessionAsync(absolute, GovernedPin);

        harness.Input.Push("""{"jsonrpc":"2.0","id":1,"result":{"sessionId":"s-0"}}""" + "\n");
        await session;

        Assert.Contains("claudeCode", Assert.Single(harness.Output.Lines).Line, StringComparison.Ordinal);
        Assert.Empty(harness.Diagnostics);

        harness.Input.EndOfStream();
        await run;
    }

    /// <summary>A non-claude engine with no options sends the same frame, and reports nothing — there was no pin to drop.</summary>
    [Fact]
    public async Task ANonClaudeEngineWithNoOptionsReportsNothing()
    {
        var absolute = Path.GetFullPath(Path.GetTempPath());
        var harness = New(EngineCatalog.Find("copilot"));
        var run = harness.Peer.RunAsync();
        var session = harness.Client.NewSessionAsync(absolute);

        harness.Input.Push("""{"jsonrpc":"2.0","id":1,"result":{"sessionId":"s-plain"}}""" + "\n");
        await session;

        Assert.DoesNotContain("_meta", Assert.Single(harness.Output.Lines).Line, StringComparison.Ordinal);
        Assert.Empty(harness.Diagnostics);

        harness.Input.EndOfStream();
        await run;
    }
}
