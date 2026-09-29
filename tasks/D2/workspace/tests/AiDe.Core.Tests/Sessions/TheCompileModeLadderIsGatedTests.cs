using System.Diagnostics;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json.Nodes;
using AiDe.Core.AgentPlane;
using AiDe.Core.PromptCompilation;
using AiDe.Core.Sessions;

namespace AiDe.Core.Tests.Sessions;

/// <summary>
/// ADR-0036 Gate 1 and US-D11 (b1, b2): the compile-mode ladder is held by an artifact the product
/// verifies, never a flag. <c>agentic-advisory</c> is selectable only when the pin-spike artifact
/// exists, its recorded triple equals the <b>installed</b> triple, and a recount of <c>tool_call</c>
/// frames over the frame log it names reads zero; <c>agentic</c> additionally needs Gate 2's
/// admission report (CV-4's reader), so it is refused here with the reason naming Gate 2.
/// </summary>
/// <remarks>
/// <para><b>A fixture install root, hashed the way the product hashes it.</b> The installed triple
/// is computed from bytes under a temp <c>node_modules</c> (raw bytes, <c>read_bytes()</c> —
/// ADR-0035's sha domain), and the artifact records those shas or deliberately not, so each refusal
/// is driven by the one fact it names. Presence alone is spoofable (Ruling 68) — the mismatch
/// cases are what make the gate a gate.</para>
/// </remarks>
public sealed class TheCompileModeLadderIsGatedTests : IDisposable
{
    private readonly string _root;
    private readonly string _install;
    private readonly string _proof;

    public TheCompileModeLadderIsGatedTests()
    {
        _root = Directory.CreateTempSubdirectory("aide-compile-gate-").FullName;
        _install = Path.Combine(_root, "install");
        _proof = Path.Combine(_root, "proof");
        Directory.CreateDirectory(_proof);

        Write(Path.Combine(_install, "node_modules", "@agentclientprotocol", "claude-agent-acp", "package.json"), """{"name":"@agentclientprotocol/claude-agent-acp","version":"0.75.1"}""");
        Write(Path.Combine(_install, "node_modules", "@agentclientprotocol", "claude-agent-acp", "dist", "acp-agent.js"), "// adapter bytes\n");
        Write(Path.Combine(_install, "node_modules", "@anthropic-ai", "claude-agent-sdk", "package.json"), """{"name":"@anthropic-ai/claude-agent-sdk","version":"0.3.257"}""");
        Write(Path.Combine(_install, "node_modules", "@anthropic-ai", CompilePin.CliPlatformPackage, CompilePin.CliFileName), "MZ fake cli bytes\n");
    }

    public void Dispose() => Directory.Delete(_root, recursive: true);

    private string ArtifactPath => Path.Combine(_proof, CompilePinArtifact.FileName);

    private string FrameLogPath => Path.Combine(_proof, CompilePinArtifact.FrameLogFileName);

    private static void Write(string path, string text)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        File.WriteAllText(path, text);
    }

    private static string Sha(string path) => Convert.ToHexStringLower(SHA256.HashData(File.ReadAllBytes(path)));

    /// <summary>An artifact recording the fixture install's own triple and the frame log it names.</summary>
    private void WriteArtifact(string? adapterSha = null, string? cliSha = null, string? frameLogSha = null, bool withFrameLog = true, string frameLog = "", string mode = "full", bool promptAnswered = true, JsonObject? sentMeta = null)
    {
        var installed = CompilePin.Installed(_install);
        if (withFrameLog)
        {
            File.WriteAllText(FrameLogPath, frameLog);
        }

        var artifact = new JsonObject
        {
            ["mode"] = mode,
            ["at"] = "2026-09-13T18:58:48Z",
            ["sent_meta_triple"] = sentMeta ?? (LaneSessionOptions.Compile with { Model = "claude-opus-5[1m]" }).ToMeta(),
            ["prompt_1"] = new JsonObject { ["text"] = "read", ["result"] = promptAnswered ? new JsonObject { ["stopReason"] = "end_turn" } : null },
            ["pin_triple"] = new JsonObject
            {
                ["adapter_package"] = "@agentclientprotocol/claude-agent-acp",
                ["adapter_version"] = "0.75.1",
                ["adapter_sha256"] = adapterSha ?? installed.AdapterSha256,
                ["sdk_package"] = "@anthropic-ai/claude-agent-sdk",
                ["sdk_version"] = "0.3.257",
                ["cli_executable_override"] = null,
                ["cli_sha256"] = cliSha ?? installed.CliSha256,
                ["cli_version_output"] = "2.1.257 (Claude Code)",
            },
            ["tool_call_frame_count"] = 0,
            ["tool_call_names"] = new JsonArray(),
            ["permission_request_count"] = 0,
            ["frame_log"] = new JsonObject
            {
                ["file"] = "recv.jsonl",
                ["sha256"] = frameLogSha ?? (withFrameLog ? Sha(FrameLogPath) : "0000"),
                ["frames"] = frameLog.Split('\n', StringSplitOptions.RemoveEmptyEntries).Length,
            },
        };
        File.WriteAllText(ArtifactPath, artifact.ToJsonString());
    }

    private const string CleanFrames =
        """{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":1}}""" + "\n"
        + """{"jsonrpc":"2.0","method":"session/update","params":{"sessionId":"s","update":{"sessionUpdate":"agent_message_chunk","content":{"type":"text","text":"none"}}}}""" + "\n";

    private const string ToolCallFrames = CleanFrames
        + """{"jsonrpc":"2.0","method":"session/update","params":{"sessionId":"s","update":{"sessionUpdate":"tool_call","toolCallId":"c1","title":"mcp__pd5-fixture__write_note","kind":"other"}}}""" + "\n";

    private CompileModeAvailability Evaluate() => CompileModeGate.Evaluate(_install, _proof);

    /// <summary>US-D11 b1: no artifact → neither agentic rung; the reason names the spike; <c>mechanical-only</c> always.</summary>
    [Fact]
    public void NoArtifactLeavesBothAgenticRungsUnselectableNamingTheSpike()
    {
        var availability = Evaluate();

        Assert.True(availability.IsSelectable(CompileModes.MechanicalOnly));
        Assert.False(availability.IsSelectable(CompileModes.AgenticAdvisory));
        Assert.False(availability.IsSelectable(CompileModes.Agentic));

        var refusal = availability.RefusalFor(CompileModes.AgenticAdvisory)!;
        Assert.Equal(EnvelopeStoreErrorCodes.PinArtifactMissing, refusal.Code);
        Assert.Contains("compile-pin-spike", refusal.Reason, StringComparison.Ordinal);
        Assert.Equal(EnvelopeStoreErrorCodes.PinArtifactMissing, availability.RefusalFor(CompileModes.Agentic)!.Code);
    }

    /// <summary>A spoofed artifact — present, its recorded adapter sha not the installed one — refuses both rungs with the triple mismatch.</summary>
    [Fact]
    public void AnArtifactWhoseAdapterShaIsNotTheInstalledOneRefusesBothRungs()
    {
        WriteArtifact(adapterSha: new string('a', 64), frameLog: CleanFrames);

        var availability = Evaluate();

        Assert.False(availability.IsSelectable(CompileModes.AgenticAdvisory));
        var refusal = availability.RefusalFor(CompileModes.AgenticAdvisory)!;
        Assert.Equal(EnvelopeStoreErrorCodes.PinTripleMismatch, refusal.Code);
        Assert.Contains("adapter", refusal.Reason, StringComparison.Ordinal);
        Assert.Equal(EnvelopeStoreErrorCodes.PinTripleMismatch, availability.RefusalFor(CompileModes.Agentic)!.Code);
    }

    /// <summary>The CLI binary is the enforcement point (ADR-0035 rule 2): its sha is part of the triple, and a bump under a stale artifact refuses.</summary>
    [Fact]
    public void AnArtifactWhoseCliShaIsNotTheInstalledOneRefusesBothRungs()
    {
        WriteArtifact(cliSha: new string('b', 64), frameLog: CleanFrames);

        var refusal = Evaluate().RefusalFor(CompileModes.AgenticAdvisory)!;

        Assert.Equal(EnvelopeStoreErrorCodes.PinTripleMismatch, refusal.Code);
        Assert.Contains("cli", refusal.Reason, StringComparison.OrdinalIgnoreCase);
    }

    /// <summary>The count is never trusted: a missing or sha-mismatched frame log is unverifiable, and unverifiable refuses.</summary>
    [Theory]
    [InlineData(false, null)]
    [InlineData(true, "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc")]
    public void AMissingOrShaMismatchedFrameLogRefusesBothRungs(bool withFrameLog, string? frameLogSha)
    {
        WriteArtifact(withFrameLog: withFrameLog, frameLogSha: frameLogSha, frameLog: CleanFrames);

        var refusal = Evaluate().RefusalFor(CompileModes.AgenticAdvisory)!;

        Assert.Equal(EnvelopeStoreErrorCodes.PinFrameLogUnverifiable, refusal.Code);
    }

    /// <summary>PD-5 run 2's shape: an aborted artifact (a zero count, a valid frame log) admits nothing; nor does a full run with a prompt that never answered.</summary>
    [Theory]
    [InlineData("aborted", true)]
    [InlineData("full", false)]
    public void ARunThatDidNotEndRefusesBothRungs(string mode, bool promptAnswered)
    {
        WriteArtifact(frameLog: CleanFrames, mode: mode, promptAnswered: promptAnswered);

        var refusal = Evaluate().RefusalFor(CompileModes.AgenticAdvisory)!;

        Assert.Equal(EnvelopeStoreErrorCodes.PinRunNotEnded, refusal.Code);
        Assert.Equal(EnvelopeStoreErrorCodes.PinRunNotEnded, Evaluate().RefusalFor(CompileModes.Agentic)!.Code);
    }

    /// <summary>An artifact that measured another pin than this build sends — run 1's 30-name pin without <c>mcp__*</c> or <c>strictMcpConfig</c> — refuses; the per-session model is not part of the identity.</summary>
    [Fact]
    public void AnArtifactThatMeasuredAnotherPinRefusesBothRungs()
    {
        WriteArtifact(frameLog: CleanFrames, sentMeta: new LaneSessionOptions(Tools: [], DisallowedTools: LaneSessionOptions.DeniedToolNames).ToMeta());

        var refusal = Evaluate().RefusalFor(CompileModes.AgenticAdvisory)!;

        Assert.Equal(EnvelopeStoreErrorCodes.PinIdentityMismatch, refusal.Code);
        Assert.Contains("mcp__*", refusal.Reason, StringComparison.Ordinal);
    }

    /// <summary>A recount ≠ 0 — a <c>tool_call</c> frame in the log the artifact claims was clean — refuses both rungs, naming the count.</summary>
    [Fact]
    public void ARecountThatIsNotZeroRefusesBothRungs()
    {
        WriteArtifact(frameLog: ToolCallFrames);

        var refusal = Evaluate().RefusalFor(CompileModes.AgenticAdvisory)!;

        Assert.Equal(EnvelopeStoreErrorCodes.PinRecountNotZero, refusal.Code);
        Assert.Contains("1 tool_call", refusal.Reason, StringComparison.Ordinal);
        Assert.Contains("mcp__pd5-fixture__write_note", refusal.Reason, StringComparison.Ordinal);
    }

    /// <summary>US-D11 b2: a matching artifact with a zero recount admits <c>agentic-advisory</c>; <c>agentic</c> waits on Gate 2, and the reason says so.</summary>
    [Fact]
    public void AMatchingArtifactWithAZeroRecountAdmitsAdvisoryAndNotAgentic()
    {
        WriteArtifact(frameLog: CleanFrames);

        var availability = Evaluate();

        Assert.True(availability.IsSelectable(CompileModes.MechanicalOnly));
        Assert.True(availability.IsSelectable(CompileModes.AgenticAdvisory));
        Assert.Null(availability.RefusalFor(CompileModes.AgenticAdvisory));
        Assert.False(availability.IsSelectable(CompileModes.Agentic));

        var refusal = availability.RefusalFor(CompileModes.Agentic)!;
        Assert.Equal(EnvelopeStoreErrorCodes.AdmissionReportOutstanding, refusal.Code);
        Assert.Contains("Gate 2", refusal.Reason, StringComparison.Ordinal);
        Assert.Equal(2, availability.Recount!.Frames);
        Assert.Equal(0, availability.Recount.ToolCalls);
    }

    /// <summary>The settings write goes through the gate: an unadmitted rung is refused with the gate's code and the file is not touched; an admitted one is written.</summary>
    [Fact]
    public void SetCompileModeRefusesAnUnadmittedRungAndWritesAnAdmittedOne()
    {
        var sessionId = SessionId.New();
        var store = new SessionConfigStore(_root, sessionId);
        store.Create("s", "w", [new AccountRef("anthropic", "max")], new AccountRef("anthropic", "max"), DateTimeOffset.UtcNow);

        var refused = Assert.Throws<EnvelopeStoreException>(
            () => store.SetCompileMode(CompileModes.AgenticAdvisory, Evaluate(), DateTimeOffset.UtcNow));
        Assert.Equal(EnvelopeStoreErrorCodes.PinArtifactMissing, refused.Code);
        Assert.Equal(CompileModes.MechanicalOnly, store.Load().CompileMode);

        WriteArtifact(frameLog: CleanFrames);
        var updated = store.SetCompileMode(CompileModes.AgenticAdvisory, Evaluate(), DateTimeOffset.UtcNow);

        Assert.Equal(CompileModes.AgenticAdvisory, updated.CompileMode);
        Assert.Equal(CompileModes.AgenticAdvisory, store.Load().CompileMode);
        Assert.Contains(store.ReadEvents(), e => e.Kind == SessionEventKinds.Config && e.Body["compileMode"]?.GetValue<string>() == CompileModes.AgenticAdvisory);

        var unknown = Assert.Throws<EnvelopeStoreException>(() => store.SetCompileMode("agentic-yolo", Evaluate(), DateTimeOffset.UtcNow));
        Assert.Equal(EnvelopeStoreErrorCodes.CompileModeUnknown, unknown.Code);
    }

    /// <summary>
    /// <c>SetCompileMode</c> defaults its trigger to <c>operator</c> (the settings sheet is the only
    /// caller today) and emits <c>compile.mode.changed{from, to, trigger}</c> exactly once for a real
    /// transition — never when the mode does not actually change (setting the same mode twice).
    /// </summary>
    [Fact]
    public void SetCompileModeDefaultsToOperatorAndEmitsOnlyOnARealTransition()
    {
        WriteArtifact(frameLog: CleanFrames);
        var store = new SessionConfigStore(_root, SessionId.New());
        store.Create("s", "w", [new AccountRef("anthropic", "max")], new AccountRef("anthropic", "max"), DateTimeOffset.UtcNow);

        using var capture = ModeChangedCapture.Open();

        store.SetCompileMode(CompileModes.AgenticAdvisory, Evaluate(), DateTimeOffset.UtcNow);
        var first = Assert.Single(capture.Activities);
        Assert.Equal(CompileModes.MechanicalOnly, first.GetTagItem("from"));
        Assert.Equal(CompileModes.AgenticAdvisory, first.GetTagItem("to"));
        Assert.Equal(CompileModeChangeTriggers.Operator, first.GetTagItem("trigger"));

        // Same mode again: no real transition, so no second event.
        store.SetCompileMode(CompileModes.AgenticAdvisory, Evaluate(), DateTimeOffset.UtcNow);
        Assert.Single(capture.Activities);
    }

    /// <summary>An explicit trigger (the gate/ring/drift path) is carried onto the emitted event, not silently rewritten to <c>operator</c>.</summary>
    [Fact]
    public void SetCompileModeCarriesAnExplicitTrigger()
    {
        WriteArtifact(frameLog: CleanFrames);
        var store = new SessionConfigStore(_root, SessionId.New());
        store.Create("s", "w", [new AccountRef("anthropic", "max")], new AccountRef("anthropic", "max"), DateTimeOffset.UtcNow);

        using var capture = ModeChangedCapture.Open();

        store.SetCompileMode(CompileModes.AgenticAdvisory, Evaluate(), DateTimeOffset.UtcNow, CompileModeChangeTriggers.Ring);

        var activity = Assert.Single(capture.Activities);
        Assert.Equal(CompileModeChangeTriggers.Ring, activity.GetTagItem("trigger"));
    }

    /// <summary>A trigger outside the closed four-word vocabulary is a programming error, not a domain refusal.</summary>
    [Fact]
    public void SetCompileModeRejectsAnUnknownTrigger()
    {
        WriteArtifact(frameLog: CleanFrames);
        var store = new SessionConfigStore(_root, SessionId.New());
        store.Create("s", "w", [new AccountRef("anthropic", "max")], new AccountRef("anthropic", "max"), DateTimeOffset.UtcNow);

        Assert.Throws<ArgumentOutOfRangeException>(
            () => store.SetCompileMode(CompileModes.AgenticAdvisory, Evaluate(), DateTimeOffset.UtcNow, "operator-ish"));
    }

    /// <summary>Listens for <c>compile.mode.changed</c> activities on the compile signal source.</summary>
    private sealed class ModeChangedCapture : IDisposable
    {
        private readonly ActivityListener _listener;
        private readonly List<Activity> _activities = [];

        private ModeChangedCapture()
        {
            _listener = new ActivityListener
            {
                ShouldListenTo = source => source.Name == CompileSignal.SourceName,
                Sample = (ref ActivityCreationOptions<ActivityContext> _) => ActivitySamplingResult.AllDataAndRecorded,
                ActivityStarted = activity =>
                {
                    if (activity.OperationName == CompileEventKinds.ModeChanged)
                    {
                        lock (_activities)
                        {
                            _activities.Add(activity);
                        }
                    }
                },
            };
            ActivitySource.AddActivityListener(_listener);
        }

        public IReadOnlyList<Activity> Activities
        {
            get
            {
                lock (_activities)
                {
                    return [.. _activities];
                }
            }
        }

        public static ModeChangedCapture Open() => new();

        public void Dispose() => _listener.Dispose();
    }

    /// <summary>
    /// The installed triple is read from the install root's own bytes: a one-byte change to
    /// <c>acp-agent.js</c> changes the adapter sha and nothing else; a missing CLI reads
    /// <i>not recorded</i>, never a plausible sha.
    /// </summary>
    [Fact]
    public void TheInstalledTripleIsHashedFromTheInstallRootsBytes()
    {
        var before = CompilePin.Installed(_install);
        File.AppendAllText(Path.Combine(_install, "node_modules", "@agentclientprotocol", "claude-agent-acp", "dist", "acp-agent.js"), "x");
        var after = CompilePin.Installed(_install);

        Assert.NotEqual(before.AdapterSha256, after.AdapterSha256);
        Assert.Equal(Sha(Path.Combine(_install, "node_modules", "@agentclientprotocol", "claude-agent-acp", "dist", "acp-agent.js")), after.AdapterSha256);
        Assert.Equal(before.CliSha256, after.CliSha256);
        Assert.Equal("0.75.1", after.AdapterVersion);
        Assert.Equal("0.3.257", after.SdkVersion);

        File.Delete(Path.Combine(_install, "node_modules", "@anthropic-ai", CompilePin.CliPlatformPackage, CompilePin.CliFileName));
        Assert.Equal(Envelope.NotRecorded, CompilePin.Installed(_install).CliSha256);
    }

    /// <summary>The recount reads <c>tool_call</c> and <c>tool_call_update</c> frames of any name; a torn line is skipped and counted, never a frame.</summary>
    [Fact]
    public void TheRecountReadsToolCallFramesOfAnyName()
    {
        var frames = ToolCallFrames
            + """{"jsonrpc":"2.0","method":"session/update","params":{"sessionId":"s","update":{"sessionUpdate":"tool_call_update","toolCallId":"c1","status":"completed"}}}""" + "\n"
            + "{not json\n";

        var recount = CompilePin.Recount(Encoding.UTF8.GetBytes(frames));

        Assert.Equal(2, recount.ToolCalls);
        Assert.Equal(["mcp__pd5-fixture__write_note"], recount.ToolNames);
        Assert.Equal(4, recount.Frames);
        Assert.Equal(1, recount.Torn);
    }

    /// <summary>
    /// The canonicalisation fixture (CV-4's red): the pin's sha is <b>raw file bytes, SHA-256, lowercase
    /// hex</b> — nothing else. <c>tools/compile-eval/ring.py</c>'s <c>--self-test</c> hashes the same
    /// bytes with Python's <c>hashlib.sha256(...).hexdigest()</c> and asserts the same constant, so a
    /// canonicalisation drift between the two languages (a BOM, a trailing newline, upper-casing) is
    /// caught on both sides rather than only where it happens to be exercised. The pack half (a
    /// craft-profile sha fixture) is a finding for <c>ai-forward</c>, recorded, not built here.
    /// </summary>
    [Fact]
    public void TheCanonicalisationFixtureMatchesRingPysHash()
    {
        var fixturePath = Path.Combine(_root, "canonicalisation-fixture.bin");
        File.WriteAllBytes(fixturePath, "the compile pin canonicalisation fixture (CV-4)\n"u8.ToArray());

        var sha = CompilePin.Sha256(fixturePath);

        Assert.Equal("59ca002ce13e199384243973f49f5cf3fb0d39c759f98fcbf79579f1e63c5488", sha);
    }
}
