using System.Text.Json;
using System.Text.Json.Nodes;
using AiDe.Core.AgentPlane;
using Xunit.Abstractions;

namespace AiDe.Core.Tests.AgentPlane;

/// <summary>
/// Each catalog engine, launched exactly as <see cref="EngineCatalog.ResolveLaunch"/> resolves it and
/// spawned exactly as <see cref="AcpEngineProcess.Start"/> spawns it, answers <c>initialize</c> with
/// <c>protocolVersion 1</c> — against the <b>real CLI</b> on this machine, never a stand-in.
/// </summary>
/// <remarks>
/// <para><b>Why the real peer.</b> Ruling 97: "no engine launches on an unobserved path". A fake
/// peer answering <c>protocolVersion 1</c> would prove the client's parser and nothing about the
/// launch line, the shim resolution, or the CLI. Where a CLI is not installed the test is
/// <b>skipped with the catalog's own refusal as the reason</b> — "not installed" said out loud, not
/// a green result over a peer that was never there.</para>
///
/// <para><b>What is deliberately not done.</b> No <c>session/new</c> (it would use a stored login or
/// refuse for want of one), no <c>session/prompt</c> (spend), no sign-in gesture. Each engine runs
/// with its home pointed at a scratch directory under <c>%TEMP%\aide-engine-spikes\</c> — the
/// isolation the spike used (<c>docs/spikes/engine-backends-2026-09-14.md</c>, "Method":
/// <c>COPILOT_HOME</c>, <c>CODEX_HOME</c>, <c>GROK_HOME</c>, and <c>HOME</c>+<c>USERPROFILE</c> for
/// gemini) — so nothing under the operator's <c>~/.copilot</c>, <c>~/.codex</c>, <c>~/.gemini</c> or
/// <c>~/.grok</c> is written or read. Whether a CLI reaches the network during <c>initialize</c> is
/// <b>not observed</b> here (no network instrument in the test); the spike's timings are the only
/// measurement.</para>
///
/// <para><b>What is recorded.</b> The launch line as spawned, the child's pid, the initialize
/// result and its latency are written to <c>observed-initialize.json</c> in the scratch directory
/// and echoed to the test output, so the proof pack copies an observation rather than a memory.</para>
/// </remarks>
[Trait("Platform", "Windows")]
public sealed class TheEnginesAnswerInitializeOnTheWireTests(ITestOutputHelper output)
{
    /// <summary>The spike's scratch prefix: every engine's per-test home and cwd live under it.</summary>
    private static readonly string ScratchRoot = Path.Combine(Path.GetTempPath(), "aide-engine-spikes", "aide-tests");

    /// <summary>
    /// The install root the catalog resolves an npm-delivered CLI from when PATH has none: the
    /// spike's per-engine scratch install (<c>npm install --prefix %TEMP%\aide-engine-spikes\&lt;engine&gt;</c>).
    /// </summary>
    internal static string SpikeInstallRoot(string engineId) => Path.Combine(Path.GetTempPath(), "aide-engine-spikes", engineId);

    /// <summary>
    /// copilot — <c>copilot --acp</c> (GitHub Copilot CLI 1.0.84-5 at spike time), the winget
    /// <c>copilot.exe</c> resolved from PATH. The spike's fresh-home run answered in 408 ms with
    /// <c>agentInfo.name "Copilot"</c> (<c>spikes/engine-backends/copilot/fresh-home/frames.jsonl</c>).
    /// </summary>
    [NativeCliFact("copilot")]
    public Task CopilotAnswersInitializeWithProtocolVersionOne()
        => ObserveInitializeAsync("copilot", home => new Dictionary<string, string> { ["COPILOT_HOME"] = home }, expectedAgentName: "Copilot");

    /// <summary>
    /// codex — the adapter <c>@agentclientprotocol/codex-acp@1.10.0</c>, spawned as
    /// <c>node &lt;root&gt;/node_modules/@agentclientprotocol/codex-acp/dist/index.js</c> from the
    /// spike's scratch install (<c>%TEMP%\aide-engine-spikes\codex</c>, <c>--ignore-scripts</c>).
    /// The spike's fresh-home run answered in 834 ms with <c>agentInfo.name
    /// "@agentclientprotocol/codex-acp"</c> (<c>spikes/engine-backends/codex/frames.jsonl</c>); the
    /// adapter itself spawns <c>node &lt;@openai/codex/bin/codex.js&gt; app-server</c>, which is why
    /// the kill-on-close job matters here.
    /// </summary>
    [NativeCliFact("codex")]
    public Task CodexAnswersInitializeWithProtocolVersionOne()
        => ObserveInitializeAsync("codex", home => new Dictionary<string, string> { ["CODEX_HOME"] = home }, expectedAgentName: "@agentclientprotocol/codex-acp");

    /// <summary>
    /// gemini — <c>gemini --acp</c> (Gemini CLI 0.58.0 at spike time), resolved through npm's
    /// <c>gemini.cmd</c> to <c>node &lt;npm prefix&gt;/node_modules/@google/gemini-cli/bundle/gemini.js --acp</c>.
    /// The spike's fresh-home run answered in 1.1 s with <c>agentInfo.name "gemini-cli"</c>
    /// (<c>spikes/engine-backends/gemini/fresh-home/frames.jsonl</c>). Isolation is
    /// <c>HOME</c>+<c>USERPROFILE</c> on scratch, the spike's shape; the CLI writes
    /// <c>.gemini/</c> there. <c>GEMINI_API_KEY</c> is inherited as this machine has it — it is
    /// read at <c>session/new</c>, which is not sent.
    /// </summary>
    [NativeCliFact("gemini")]
    public Task GeminiAnswersInitializeWithProtocolVersionOne()
        => ObserveInitializeAsync("gemini", home => new Dictionary<string, string> { ["HOME"] = home, ["USERPROFILE"] = home }, expectedAgentName: "gemini-cli");

    /// <summary>
    /// grok — <c>grok agent stdio</c> (xAI Grok Build 1.0.30), not on this machine's PATH, so
    /// resolved from the spike's scratch install as
    /// <c>node &lt;root&gt;/node_modules/@xai-official/grok/bin/grok agent stdio</c>. The spike's
    /// fresh run answered in 2.8 s including the first-run bootstrap
    /// (<c>spikes/engine-backends/grok/frames.jsonl</c>); no <c>agentInfo</c>, the version rides
    /// <c>_meta.agentVersion</c>. <c>GROK_HOME</c> is a <b>stable</b> scratch home so the ~150 MB
    /// bootstrap (<c>bin/grok.exe</c> decompressed from the platform package) happens once per
    /// machine, never under <c>~/.grok</c>. <c>XAI_API_KEY</c> is inherited as this machine has it —
    /// it changes <c>authMethods</c> and is read at <c>session/new</c>, which is not sent.
    /// </summary>
    [NativeCliFact("grok")]
    public Task GrokAnswersInitializeWithProtocolVersionOne()
        => ObserveInitializeAsync(
            "grok",
            _ => new Dictionary<string, string> { ["GROK_HOME"] = Directory.CreateDirectory(Path.Combine(ScratchRoot, "grok-home")).FullName },
            expectedAgentName: null,
            assertIdentity: result => Assert.Equal("1.0.30", result["_meta"]!["agentVersion"]!.GetValue<string>()));

    private async Task ObserveInitializeAsync(
        string engineId,
        Func<string, IReadOnlyDictionary<string, string>> isolation,
        string? expectedAgentName,
        Action<JsonObject>? assertIdentity = null)
    {
        var scratch = Path.Combine(ScratchRoot, engineId + "-" + Guid.NewGuid().ToString("n")[..8]);
        var home = Path.Combine(scratch, "home");
        var cwd = Path.Combine(scratch, "cwd");
        Directory.CreateDirectory(home);
        Directory.CreateDirectory(cwd);

        var row = EngineCatalog.Find(engineId);
        var launch = EngineCatalog.ResolveLaunch(engineId, SpikeInstallRoot(engineId));
        var diagnostics = new List<string>();
        var started = System.Diagnostics.Stopwatch.StartNew();

        using var engine = AcpEngineProcess.Start(launch, cwd, diagnostics.Add, environment: isolation(home));
        var peer = new AcpPeer(engine.Output, engine.Input, new AcpRunEventMapper("run-wire", "lane-" + engineId), diagnostics: diagnostics.Add);
        var client = new AcpLaneClient(peer, engine: row, diagnostics: diagnostics.Add);

        using var deadline = new CancellationTokenSource(TimeSpan.FromSeconds(90));
        var pump = peer.RunAsync(deadline.Token);

        JsonObject result;
        try
        {
            result = await client.InitializeAsync(deadline.Token);
        }
        finally
        {
            // The order matters: end the child, then the pump sees end-of-stream and completes.
            engine.Dispose();
            try
            {
                await pump.WaitAsync(TimeSpan.FromSeconds(10));
            }
            catch (Exception error) when (error is OperationCanceledException or IOException or TimeoutException)
            {
                diagnostics.Add("pump: " + error.GetType().Name);
            }
        }

        var latency = started.Elapsed;
        var observation = new JsonObject
        {
            ["engine"] = engineId,
            ["launch"] = new JsonObject { ["fileName"] = launch.FileName, ["arguments"] = new JsonArray([.. launch.Arguments.Select(a => JsonValue.Create(a))]) },
            ["pid"] = engine.ProcessId,
            ["initialize"] = result.DeepClone(),
            ["initializeLatencyMs"] = (long)latency.TotalMilliseconds,
            ["diagnostics"] = new JsonArray([.. diagnostics.Select(d => JsonValue.Create(d))]),
            ["observedAt"] = DateTimeOffset.UtcNow.ToString("O"),
        };
        var record = Path.Combine(scratch, "observed-initialize.json");
        File.WriteAllText(record, observation.ToJsonString(new JsonSerializerOptions { WriteIndented = true }));
        output.WriteLine(record);
        output.WriteLine(observation.ToJsonString());

        Assert.Equal(1, result["protocolVersion"]!.GetValue<int>());
        if (expectedAgentName is not null)
        {
            Assert.Equal(expectedAgentName, result["agentInfo"]!["name"]!.GetValue<string>());
        }

        assertIdentity?.Invoke(result);

        Assert.True(engine.HasExited, $"engine process {engine.ProcessId} outlived the test");
    }

    /// <summary>
    /// A fact that runs only where the catalog can resolve the engine's launch on this machine and
    /// the file it resolves to exists; elsewhere it is skipped with the catalog's own refusal — the
    /// install instruction — as the reason. An adapter or npm script needs <c>node</c> on PATH too.
    /// </summary>
    private sealed class NativeCliFactAttribute : FactAttribute
    {
        public NativeCliFactAttribute(string engineId)
        {
            EngineLaunch launch;
            try
            {
                launch = EngineCatalog.ResolveLaunch(engineId, SpikeInstallRoot(engineId));
            }
            catch (AgentPlaneException error) when (error.Code == AgentPlaneErrorCodes.EngineNotOnPath)
            {
                Skip = $"{engineId} is not installed on this machine: {error.Message}";
                return;
            }

            if (launch.FileName != "node")
            {
                return;
            }

            if (NativeCommandLocator.FromEnvironment().FindExecutable("node") is null)
            {
                Skip = $"{engineId} runs under node, and node is not on PATH";
            }
            else if (!File.Exists(launch.Arguments[0]))
            {
                var row = EngineCatalog.Find(engineId);
                Skip = $"{engineId} is not installed on this machine: '{launch.Arguments[0]}' does not exist "
                    + $"(npm install --prefix {SpikeInstallRoot(engineId)} --ignore-scripts {row.AdapterPackage ?? row.Native?.NpmPackage}@{row.AdapterVersion ?? "<version>"})";
            }
        }
    }
}
