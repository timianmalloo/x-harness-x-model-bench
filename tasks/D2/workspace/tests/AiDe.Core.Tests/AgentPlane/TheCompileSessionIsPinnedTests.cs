using System.Text.Json.Nodes;
using AiDe.Core.AgentPlane;

namespace AiDe.Core.Tests.AgentPlane;

/// <summary>
/// ADR-0035 rule 2 and PD-5's finding 1: the compile session's pin, as it goes down the wire.
/// </summary>
/// <remarks>
/// <para><b>The exact key set, not the pinned keys.</b> Every widening vector lives in the same
/// <c>_meta.claudeCode.options</c> object the adapter spreads whole into the SDK
/// (<c>acp-agent.js:5964</c>): <c>settingSources</c>, <c>systemPrompt</c>, <c>env</c>,
/// <c>extraArgs</c>, <c>mcpServers</c>, <c>settings</c>. A test that asserted only the pinned keys
/// would stay green while a later passthrough filled one of those.</para>
///
/// <para><b>And <c>mcp__*</c>, because PD-5 measured the gap.</b> With <c>tools: []</c> and
/// <c>mcpServers: []</c> the CLI still loaded the fixture repository's <c>.mcp.json</c> server and
/// offered <c>mcp__pd5-fixture__write_note</c> to the model (docs/proof/compile-pin-spike.md,
/// finding 1). The CLI's own deny matcher reads <c>mcp__*</c> as "every MCP server's tools"
/// (claude.exe 2.1.257, the <c>isServerLevelDisallowed</c> parse: a <c>serverName</c> of <c>*</c>
/// sets the all-servers flag) — Verified in the binary's strings, measured on the wire by the
/// spike's second run.</para>
/// </remarks>
public sealed class TheCompileSessionIsPinnedTests
{
    private sealed record Harness(AcpLaneClient Client, AcpPeer Peer, PushTextReader Input, RecordingTextWriter Output);

    private static Harness New()
    {
        var input = new PushTextReader();
        var output = new RecordingTextWriter();
        var peer = new AcpPeer(input, output, new AcpRunEventMapper("run-c", "compile-1"));
        return new Harness(new AcpLaneClient(peer), peer, input, output);
    }

    /// <summary>
    /// The compile pin's <c>session/new</c> carries exactly <c>{cwd, mcpServers: [], _meta}</c>,
    /// <c>_meta</c> exactly <c>{claudeCode: {options}}</c>, <c>options</c> exactly
    /// <c>{tools: [], disallowedTools}</c>, and the disallowed set is every denied tool name plus
    /// <c>mcp__*</c> — nothing else on the frame.
    /// </summary>
    [Fact]
    public async Task TheCompileFrameCarriesExactlyTheCwdEmptyMcpServersAndThePinTriple()
    {
        var absolute = Path.GetFullPath(Path.GetTempPath());
        var harness = New();
        var run = harness.Peer.RunAsync();
        var session = harness.Client.NewSessionAsync(absolute, LaneSessionOptions.Compile);

        harness.Input.Push("""{"jsonrpc":"2.0","id":1,"result":{"sessionId":"s-compile"}}""" + "\n");
        Assert.Equal("s-compile", await session);

        var frame = JsonNode.Parse(Assert.Single(harness.Output.Lines).Line)!.AsObject();
        Assert.Equal("session/new", frame["method"]!.GetValue<string>());
        var parameters = frame["params"]!.AsObject();

        Assert.Equal(["cwd", "mcpServers", "_meta"], parameters.Select(m => m.Key));
        Assert.Equal(absolute, parameters["cwd"]!.GetValue<string>());
        Assert.Empty(parameters["mcpServers"]!.AsArray());

        var meta = parameters["_meta"]!.AsObject();
        Assert.Equal(["claudeCode"], meta.Select(m => m.Key));
        var claudeCode = meta["claudeCode"]!.AsObject();
        Assert.Equal(["options"], claudeCode.Select(m => m.Key));
        var options = claudeCode["options"]!.AsObject();
        Assert.Equal(["tools", "disallowedTools", "strictMcpConfig"], options.Select(m => m.Key));

        Assert.Empty(options["tools"]!.AsArray());
        Assert.True(options["strictMcpConfig"]!.GetValue<bool>());

        var disallowed = options["disallowedTools"]!.AsArray().Select(n => n!.GetValue<string>()).ToList();
        Assert.Equal(disallowed.Count, disallowed.Distinct(StringComparer.Ordinal).Count());
        Assert.Equal(
            LaneSessionOptions.DeniedToolNames.Append(LaneSessionOptions.EveryMcpServerTool).ToHashSet(StringComparer.Ordinal),
            disallowed.ToHashSet(StringComparer.Ordinal));
        Assert.Contains("mcp__*", disallowed);

        harness.Input.EndOfStream();
        await run;
    }

    /// <summary>
    /// The typed argument has exactly five members, each admitted by a named finding — the two
    /// the adapter spreads as tools (Ruling 71), <c>strictMcpConfig</c> (PD-5 run 2: the
    /// repository's <c>.mcp.json</c> server spawned as the operator under <c>tools: []</c> +
    /// <c>mcp__*</c>), <c>model</c> (the binding's third element, otherwise the CLI's own
    /// resolution picks what bills) and <c>thinking.display</c> (CV-5.3, Ruling 82: recent models
    /// default to <c>"omitted"</c> and the adapter forwards no thought chunk — the thread's
    /// Thinking line needs the lane to ask) — and a sixth is a wider reach. The compile pin is the
    /// named static, not an ad-hoc list, and it does not ask for thinking (its pin identity,
    /// <c>CE-0023</c>, is unchanged); a lane's record sends nothing new.
    /// </summary>
    [Fact]
    public void TheRecordHasExactlyFiveMembersAndTheCompilePinIsANamedStatic()
    {
        var members = typeof(LaneSessionOptions).GetProperties().Select(p => p.Name).Order(StringComparer.Ordinal).ToList();
        Assert.Equal(["DisallowedTools", "Model", "StrictMcpConfig", "ThinkingDisplay", "Tools"], members);
        Assert.Null(LaneSessionOptions.Compile.ThinkingDisplay);

        Assert.Null(new LaneSessionOptions(DisallowedTools: ["Bash"]).StrictMcpConfig);
        Assert.Null(new LaneSessionOptions(DisallowedTools: ["Bash"]).Model);
        Assert.True(LaneSessionOptions.Compile.StrictMcpConfig);
        Assert.Null(LaneSessionOptions.Compile.Model);
        Assert.Equal("claude-sonnet-5", LaneSessionOptions.CompileOn("claude-sonnet-5").Model);
        Assert.NotNull(LaneSessionOptions.Compile.Tools);
        Assert.Empty(LaneSessionOptions.Compile.Tools!);
        Assert.Equal("mcp__*", LaneSessionOptions.EveryMcpServerTool);
        // 30, not the "26" docs/proof/compile-pin-spike.md and run-spike.js's comment cite — the
        // literal was counted here, red-first (a finding for the Proof Pack; the set is the record).
        Assert.Equal(30, LaneSessionOptions.DeniedToolNames.Count);
        Assert.Equal(30, LaneSessionOptions.DeniedToolNames.Distinct(StringComparer.Ordinal).Count());
    }

    /// <summary>
    /// ADR-0035 rule 2: the pin is enforced by the CLI binary the SDK ships, and
    /// <c>CLAUDE_CODE_EXECUTABLE</c> would swap that binary (<c>acp-agent.js</c>:
    /// <c>pathToClaudeCodeExecutable: process.env.CLAUDE_CODE_EXECUTABLE ?? claudeCliPath()</c>).
    /// The engine's child never inherits it — every lane's and every compile's.
    /// </summary>
    [Theory]
    [InlineData("CLAUDE_CODE_EXECUTABLE")]
    [InlineData("NODE_OPTIONS")]
    [InlineData("NODE_PATH")]
    public void TheChildEnvironmentNeverCarriesAnInjectingVariableAndItsRemovalIsReported(string name)
    {
        Assert.Contains(name, AcpEngineProcess.StrippedEnvironmentVariables);
        var previous = Environment.GetEnvironmentVariable(name);
        Environment.SetEnvironmentVariable(name, name == "CLAUDE_CODE_EXECUTABLE" ? @"C:\somewhere\else\claude.exe" : "--require evil.js");
        var report = new List<string>();
        try
        {
            var info = AcpEngineProcess.StartInfoFor(new EngineLaunch("node", ["x.js"]), Path.GetTempPath(), report: report.Add);

            Assert.False(info.Environment.ContainsKey(name));
            Assert.True(info.Environment.ContainsKey("PATH") || info.Environment.ContainsKey("Path"));
            Assert.Contains(report, line => line.Contains(name, StringComparison.Ordinal) && line.Contains("removed", StringComparison.Ordinal));
        }
        finally
        {
            Environment.SetEnvironmentVariable(name, previous);
        }
    }

    /// <summary>A host-set variable reaches the child; a stripped name can never be set through the same door.</summary>
    [Fact]
    public void AHostSetVariableReachesTheChildAndAStrippedNameCannotBeSet()
    {
        var info = AcpEngineProcess.StartInfoFor(new EngineLaunch("node", ["x.js"]), Path.GetTempPath(), new Dictionary<string, string> { [AcpEngineProcess.MaxOutputTokensVariable] = "4096" });
        Assert.Equal("4096", info.Environment[AcpEngineProcess.MaxOutputTokensVariable]);

        Assert.Throws<ArgumentException>(() => AcpEngineProcess.StartInfoFor(new EngineLaunch("node", ["x.js"]), Path.GetTempPath(), new Dictionary<string, string> { ["NODE_OPTIONS"] = "x" }));
    }
}
