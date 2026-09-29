using System.Text.Json.Nodes;

namespace AiDe.Core.AgentPlane;

/// <summary>
/// Reads the adapter's <c>_auth/status_update</c> extension frame.
/// </summary>
/// <remarks>
/// <b>An <c>_</c>-prefixed extension, so absence is ordinary.</b> The frame may simply not arrive,
/// and <c>null</c> is what that means. <see cref="SpawnContract"/> refuses on it rather than
/// assuming a subscription — an environment API key outranks the stored subscription inside the
/// adapter and bills silently, so "not recorded" is the one answer that must never be optimistic.
/// </remarks>
public static class AcpAuthStatus
{
    /// <summary>The wire method, as observed. Vendor-prefixed, and therefore not in schema v1.</summary>
    public const string Method = "_auth/status_update";

    /// <summary>Reads one status update's params, or <c>null</c> when it carries no status.</summary>
    public static ObservedAuthStatus? From(JsonObject? parameters)
    {
        if (parameters?["authStatus"] is not JsonObject status)
        {
            return null;
        }

        var kind = AcpJson.Text(status["kind"]);
        return kind is null
            ? null
            : new ObservedAuthStatus(kind, AcpJson.Text((status["account"] as JsonObject)?["plan"]), AcpJson.Text(status["label"]));
    }
}

/// <summary>
/// What this client tells the agent it can do for it.
/// </summary>
/// <remarks>
/// <b>Declared honestly, which is the whole point.</b> A client that advertises
/// <c>fs.writeTextFile</c> and then answers <c>-32601</c> has told the agent a lie it will plan
/// around. Phase 1 implements none of the client-side capabilities, and the adapter's own tools
/// cover the same ground — the captured corpus shows a file write arriving as a <c>tool_call</c>
/// with <c>kind:"edit"</c> plus a permission request, not as <c>fs/write_text_file</c>.
/// </remarks>
/// <param name="ReadTextFile">Whether the agent may ask this client to read a file.</param>
/// <param name="WriteTextFile">Whether the agent may ask this client to write one.</param>
/// <param name="Terminal">Whether the agent may ask this client to host a terminal.</param>
public sealed record AcpClientCapabilities(bool ReadTextFile, bool WriteTextFile, bool Terminal)
{
    /// <summary>What Phase 1 actually implements: none of them.</summary>
    public static readonly AcpClientCapabilities PhaseOne = new(false, false, false);

    /// <summary>The <c>clientCapabilities</c> object, in the shape the adapter reads.</summary>
    public JsonObject ToJson() => new()
    {
        ["fs"] = new JsonObject
        {
            ["readTextFile"] = ReadTextFile,
            ["writeTextFile"] = WriteTextFile,
        },
        ["terminal"] = Terminal,
    };
}

/// <summary>
/// The tools argument of <c>session/new</c> — what the lane's model may hold — sent through the
/// adapter's extension slot <c>_meta.claudeCode.options</c>.
/// </summary>
/// <remarks>
/// <para><b>A lane is not toolless by default.</b> With no <c>_meta</c> the adapter hands the SDK
/// the <c>claude_code</c> preset and resolves permissions from the user's, the repository's and the
/// local settings (adapter 0.75.1, <c>acp-agent.js:5883-5884</c>, <c>:5962</c>), so the lease
/// bounds the file writes the seams observe and nothing bounds the tools. This record is the one
/// place the host says otherwise (Ruling 71; <c>docs/notes/lane-pin-spike.md</c>).</para>
///
/// <para><b>Exactly the two members the adapter spreads into the SDK options</b>
/// (<c>:6007-6008</c>), and nothing else — the whole <c>_meta.claudeCode.options</c> object is
/// spread into the SDK's options (<c>:5964</c>), so a wider record would be a wider reach. An
/// absent record and an empty one both send the frame every prior run sent.</para>
/// </remarks>
/// <param name="Tools">
/// The base tool set: <c>null</c> leaves the adapter's preset in place; an empty list disables
/// every built-in tool (Addendum D's compile session).
/// </param>
/// <param name="DisallowedTools">
/// Tool names removed from the model's context even where the settings would allow them;
/// <c>null</c> sends none. The governed lane sends <c>["Bash"]</c>.
/// </param>
public sealed record LaneSessionOptions(IReadOnlyList<string>? Tools = null, IReadOnlyList<string>? DisallowedTools = null)
{
    /// <summary>
    /// <c>strictMcpConfig: true</c> — the SDK uses only the servers the frame's <c>mcpServers</c>
    /// names and ignores the repository's <c>.mcp.json</c>, user settings and plugins
    /// (<c>sdk.d.ts:2110</c>, forwarded as <c>--strict-mcp-config</c>). <b>Admitted by
    /// measurement</b> (ADR-0035 rule 2): PD-5's second run showed the CLI spawning the fixture
    /// repository's <c>.mcp.json</c> server as the operator at <c>session/new</c>, before any prompt,
    /// with <c>tools: []</c> and <c>mcp__*</c> on the frame — <c>mcp__*</c> denies at the name; this
    /// closes the spawn (the Security &amp; Identity Architect's blocker at CV-3's gate). <c>null</c>
    /// sends nothing; a lane keeps its servers.
    /// </summary>
    public bool? StrictMcpConfig { get; init; }

    /// <summary>
    /// The model the session runs on, host-authored from the binding (<c>providers.json</c>):
    /// without it the CLI's own resolution — user settings, the repository's <c>settings.json</c>,
    /// <c>ANTHROPIC_MODEL</c> — picks what bills, and a third of <c>AuthorizeBinding</c>'s triple is a
    /// label. <c>null</c> sends nothing (today's lanes).
    /// </summary>
    public string? Model { get; init; }

    /// <summary>
    /// <c>thinking: { type: "adaptive", display: … }</c> — whether the model's reasoning is streamed
    /// as text (<c>"summarized"</c>) or as signature-only blocks (<c>"omitted"</c>, the default of
    /// recent models). The adapter forwards a thought chunk only when its text is non-empty
    /// (<c>acp-agent.js:7742-7745</c>), so a lane that does not ask never yields an
    /// <c>agent.thought</c> row (Ruling 82). <c>null</c> sends nothing. The SDK's two values only
    /// (<c>sdk.d.ts:8448-8451</c>).
    /// </summary>
    public string? ThinkingDisplay { get; init; }

    /// <summary>The value a lane sends to show its reasoning in the thread.</summary>
    public const string ThinkingSummarized = "summarized";

    /// <summary>
    /// The CLI's glob for every MCP server's tools — <c>mcp__*</c>. Read in the CLI binary's own
    /// deny parser (claude.exe 2.1.257: a parsed <c>serverName</c> of <c>*</c> with no tool name
    /// sets the all-servers flag its <c>isServerLevelDisallowed</c> reads), and its effect measured
    /// on the wire by PD-5's second run (docs/proof/compile-pin-spike.md).
    /// </summary>
    public const string EveryMcpServerTool = "mcp__*";

    /// <summary>
    /// Every tool that writes the tree or a durable file, executes code, a shell or a process,
    /// delegates to an agent, sends a local file anywhere, or cannot be read — Ruling 73's set,
    /// <b>one constant</b> (ADR-0035 rule 2: hand-listing the names twice rots on the next SDK tool).
    /// </summary>
    /// <remarks>
    /// <b>Read, not recalled.</b> Two sources, both installed under
    /// <c>spikes/acp-subscription-lane/node_modules/</c>: the SDK's schema union
    /// (<c>@anthropic-ai/claude-agent-sdk</c> 0.3.257 <c>sdk-tools.d.ts:11-56</c>) and the shipped
    /// CLI's own tool-name table (<c>claude-agent-sdk-win32-x64/claude.exe</c>, 183 names).
    /// Every name in either is classified in <c>docs/proof/read-only-turn.md</c>; asserted as a
    /// set equality against a literal in <c>TheGovernedLaneHasNoShellTests</c>; an SDK or adapter
    /// bump re-reads both sources.
    /// </remarks>
    public static readonly IReadOnlyList<string> DeniedToolNames =
    [
        // The tree and durable files.
        "Write", "Edit", "MultiEdit", "NotebookEdit", "EnterWorktree", "ExitWorktree", "CronCreate", "CronDelete",

        // Code, shells and processes.
        "Bash", "PowerShell", "REPL", "Monitor", "Tmux", "LSP", "self_hosted_runner_spawn_local",

        // Delegation to another agent, local or remote.
        "Agent", "Task", "Workflow", "RemoteTrigger", "self_hosted_runner_requeue_session",

        // A local file sent or saved by a side door, or a consequential remote write.
        "Artifact", "Projects", "SendFile", "SendUserFile",

        // Opaque — fail-closed.
        "ClaudeDesign", "Snip", "WebBrowser", "SubscribePR", "DesignSync", "ConnectGitHub",
    ];

    /// <summary>
    /// The compile session's pin (ADR-0035 rule 2; Addendum D §A13.4 C1): <c>tools: []</c> as the
    /// primary pin (every built-in tool off — the SDK's <c>[]</c> = disable all,
    /// <c>sdk.d.ts:1497-1505</c>), and <c>disallowedTools</c> naming every denied tool as braces
    /// <b>plus <see cref="EveryMcpServerTool"/></b>: PD-5's first run measured that <c>tools: []</c>
    /// and <c>mcpServers: []</c> leave a repository <c>.mcp.json</c> server's tools reachable — the
    /// CLI loads the file at <c>session/new</c> and offers its tools to the model (finding 1).
    /// </summary>
    public static readonly LaneSessionOptions Compile = new(Tools: [], DisallowedTools: [.. DeniedToolNames, EveryMcpServerTool]) { StrictMcpConfig = true };

    /// <summary>The compile pin bound to the session's model — <see cref="Compile"/> with <c>model</c> from the binding, never from a page or the model's own text.</summary>
    public static LaneSessionOptions CompileOn(string model)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(model);
        return Compile with { Model = model };
    }

    /// <summary>
    /// The <c>_meta</c> object for <c>session/new</c>, or <c>null</c> when there is nothing to say —
    /// so an absent record and an empty one both leave the frame exactly as it was.
    /// </summary>
    /// <exception cref="ArgumentException">A blank tool name: it looks like a pin and pins nothing.</exception>
    internal JsonObject? ToMeta()
    {
        if (Tools is null && DisallowedTools is null && StrictMcpConfig is null && Model is null && ThinkingDisplay is null)
        {
            return null;
        }

        var options = new JsonObject();

        if (Tools is not null)
        {
            options["tools"] = Names(Tools);
        }

        if (DisallowedTools is not null)
        {
            options["disallowedTools"] = Names(DisallowedTools);
        }

        if (StrictMcpConfig is { } strict)
        {
            options["strictMcpConfig"] = strict;
        }

        if (Model is not null)
        {
            ArgumentException.ThrowIfNullOrWhiteSpace(Model);
            options["model"] = Model;
        }

        if (ThinkingDisplay is not null)
        {
            if (ThinkingDisplay is not (ThinkingSummarized or "omitted"))
            {
                throw new ArgumentException($"thinking.display must be \"summarized\" or \"omitted\" (the SDK's ThinkingAdaptive), not '{ThinkingDisplay}'.");
            }

            options["thinking"] = new JsonObject { ["type"] = "adaptive", ["display"] = ThinkingDisplay };
        }

        return new JsonObject { ["claudeCode"] = new JsonObject { ["options"] = options } };
    }

    private static JsonArray Names(IReadOnlyList<string> names)
    {
        var array = new JsonArray();

        foreach (var name in names)
        {
            ArgumentException.ThrowIfNullOrWhiteSpace(name);
            array.Add(name);
        }

        return array;
    }
}

/// <summary>
/// ACP semantics over the peer: the handshake, the session, the prompt, and the permission answer.
/// </summary>
/// <remarks>
/// <para><b>Separate from <see cref="AcpPeer"/> on purpose.</b> The peer owns framing, correlation
/// and failure; this owns what the messages mean. The split is what lets every framing failure mode
/// be tested without a handshake, and every handshake rule be tested without a process.</para>
///
/// <para><b>The permission answer defaults to reject.</b> That is the spike probe's behaviour and it
/// is the right default for an unattended lane: a client that silently allows every edit has removed
/// the governance the plane exists to provide. The choice is a delegate because it is a policy the
/// caller owns, not a constant.</para>
/// </remarks>
public sealed class AcpLaneClient
{
    /// <summary>
    /// The ACP schema revision this client speaks, pinned and <b>asserted on the way back</b>.
    /// </summary>
    /// <remarks>
    /// Schema v2 alpha is in flight and the adapters publish near-daily. Sending a version and not
    /// checking the echo is how a client goes on speaking v1 to a peer that answered v2: every frame
    /// still parses, and the meanings have moved underneath it.
    /// </remarks>
    public const int ProtocolVersion = 1;

    private readonly AcpPeer _peer;
    private readonly AcpClientCapabilities _capabilities;
    private readonly Func<JsonObject, string> _choosePermission;
    private readonly EngineRow? _engine;
    private readonly Action<string> _diagnostics;

    /// <param name="peer">The transport. This client installs itself as its inbound handler.</param>
    /// <param name="capabilities">What to declare. Defaults to <see cref="AcpClientCapabilities.PhaseOne"/>.</param>
    /// <param name="choosePermission">
    /// Picks an <c>optionId</c> from a permission request's params. Defaults to the reject option.
    /// </param>
    /// <param name="engine">
    /// The catalog row this peer is, when the caller knows it. It decides whether
    /// <see cref="LaneSessionOptions"/> reach the wire: the <c>_meta.claudeCode.options</c> slot is
    /// the claude-code adapter's (<see cref="EngineRow.ReadsClaudeCodeMeta"/>), and every other
    /// engine gets the ACP-standard <c>session/new</c> the spike observed it accept. <c>null</c> —
    /// every caller that predates the catalog's native rows — sends the options as given.
    /// </param>
    /// <param name="diagnostics">Where a pin that was <b>not</b> sent is named. Defaults to stderr.</param>
    public AcpLaneClient(
        AcpPeer peer,
        AcpClientCapabilities? capabilities = null,
        Func<JsonObject, string>? choosePermission = null,
        EngineRow? engine = null,
        Action<string>? diagnostics = null)
    {
        ArgumentNullException.ThrowIfNull(peer);

        _peer = peer;
        _capabilities = capabilities ?? AcpClientCapabilities.PhaseOne;
        _choosePermission = choosePermission ?? RejectOption;
        _engine = engine;
        _diagnostics = diagnostics ?? Console.Error.WriteLine;
        _peer.InboundHandler = Handle;
    }

    /// <summary>
    /// Performs the handshake and returns its result, having checked the echoed version.
    /// </summary>
    /// <exception cref="AgentPlaneException">
    /// <see cref="AgentPlaneErrorCodes.ProtocolVersionMismatch"/> when the peer echoed a different
    /// version, or none at all.
    /// </exception>
    public async Task<JsonObject> InitializeAsync(CancellationToken cancellationToken = default)
    {
        var result = await _peer.RequestAsync(
            "initialize",
            new JsonObject
            {
                ["protocolVersion"] = ProtocolVersion,
                ["clientCapabilities"] = _capabilities.ToJson(),
            },
            cancellationToken: cancellationToken);

        var echoed = (result["protocolVersion"] as JsonValue)?.TryGetValue<int>(out var version) == true
            ? version
            : (int?)null;

        if (echoed != ProtocolVersion)
        {
            throw new AgentPlaneException(
                AgentPlaneErrorCodes.ProtocolVersionMismatch,
                $"this client speaks ACP protocolVersion {ProtocolVersion}; the engine echoed "
                + $"{(echoed is { } value ? value.ToString(System.Globalization.CultureInfo.InvariantCulture) : "not recorded")}. "
                + "Every frame would still parse and the meanings would have moved, so the session is refused");
        }

        return result;
    }

    /// <summary>
    /// The params of the <c>session/new</c> this client sent — the object the peer serialized onto
    /// the wire, <c>_meta</c> included — or <c>null</c> until it has sent one.
    /// </summary>
    /// <remarks>
    /// The outbound mirror of <see cref="AcpPeer.ObservedAuth"/>: kept so the host can record the
    /// frame it opened the lane with (Ruling 71 (a)) as what was sent, never as a re-computation of
    /// what should have been.
    /// </remarks>
    public JsonObject? SessionNewParameters { get; private set; }

    /// <summary>
    /// Opens a session rooted at <paramref name="cwd"/>, which <b>must be absolute</b>, holding the
    /// tools <paramref name="options"/> names — or, with none, whatever the adapter's preset allows.
    /// </summary>
    /// <exception cref="AgentPlaneException">
    /// <see cref="AgentPlaneErrorCodes.SessionCwdNotAbsolute"/> — refused before the wire, so the
    /// reason stays attached to the caller rather than arriving later as a <c>-32602</c>.
    /// </exception>
    public async Task<string> NewSessionAsync(
        string cwd,
        LaneSessionOptions? options = null,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(cwd);

        if (!Path.IsPathRooted(cwd))
        {
            throw new AgentPlaneException(
                AgentPlaneErrorCodes.SessionCwdNotAbsolute,
                $"session cwd '{cwd}' is relative; ACP requires an absolute path and answers a relative one "
                + "with -32602. It is refused here so the error names the caller rather than the transport");
        }

        var parameters = new JsonObject { ["cwd"] = cwd, ["mcpServers"] = new JsonArray() };

        // Ruling 71: the tools pin rides the adapter's extension slot, and only when there is one to
        // send — the frame every prior run sent stays byte-identical otherwise.
        if (options?.ToMeta() is { } meta)
        {
            if (_engine is null || _engine.ReadsClaudeCodeMeta)
            {
                parameters["_meta"] = meta;
            }
            else
            {
                // The slot is the claude-code adapter's. Every other engine was observed accepting
                // exactly {cwd, mcpServers: []} (spikes/engine-backends/<engine>/**/frames.sent.jsonl),
                // and nothing observed says one reads _meta.claudeCode — so it is not sent, and
                // SAID: a pin that vanished silently would read as governance on the recorded frame.
                _diagnostics(
                    $"session/new: engine '{_engine.Id}' has no claudeCode extension slot; the lane's tools pin was "
                    + "not sent, and the frame is the ACP-standard one the spike observed this engine accept — "
                    + "the lane's governance on this engine is the permission policy alone");
            }
        }

        SessionNewParameters = parameters;
        var result = await _peer.RequestAsync("session/new", parameters, cancellationToken: cancellationToken);

        return (result["sessionId"] as JsonValue)?.TryGetValue<string>(out var sessionId) == true
            ? sessionId
            : throw new AgentPlaneException(
                AgentPlaneErrorCodes.EngineReturnedError,
                "the engine answered session/new without a sessionId, so there is no session to drive");
    }

    /// <summary>
    /// Opens the lane's session rooted in its <b>provisioned worktree</b> — spec R1 bullet 1.
    /// </summary>
    /// <remarks>
    /// <b>The composition lives in the signature.</b> Each half was already true and neither implied
    /// the other: this client refused a relative <c>cwd</c> (true of any absolute path, including the
    /// primary checkout), and the provisioner really cut a tree (true whether or not the lane ever
    /// ran there). A caller holding a <see cref="ProvisionedWorktree"/> passes the tree, not a
    /// string, so a governed lane cannot be rooted anywhere else by picking the wrong path.
    /// </remarks>
    public Task<string> NewSessionAsync(
        ProvisionedWorktree worktree,
        LaneSessionOptions? options = null,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(worktree);
        return NewSessionAsync(worktree.Path, options, cancellationToken);
    }

    /// <summary>
    /// Sends one prompt and waits for the turn to end, under the prompt bound rather than the
    /// handshake one.
    /// </summary>
    public Task<JsonObject> PromptAsync(string sessionId, string text, CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(sessionId);
        ArgumentException.ThrowIfNullOrWhiteSpace(text);

        return _peer.RequestAsync(
            "session/prompt",
            new JsonObject
            {
                ["sessionId"] = sessionId,
                ["prompt"] = new JsonArray(new JsonObject { ["type"] = "text", ["text"] = text }),
            },
            AcpPeerOptions.DefaultPromptTimeout,
            cancellationToken);
    }

    /// <summary>
    /// Answers what this client implements, and <c>null</c> — which the peer turns into
    /// <c>-32601</c> — for everything it does not.
    /// </summary>
    private JsonNode? Handle(string method, JsonObject? parameters)
        => method == "session/request_permission" && parameters is not null
            ? new JsonObject
            {
                ["outcome"] = new JsonObject
                {
                    ["outcome"] = "selected",
                    ["optionId"] = _choosePermission(parameters),
                },
            }
            : null;

    /// <summary>
    /// Picks the reject option, by its declared <c>kind</c> rather than by its id.
    /// </summary>
    /// <remarks>
    /// The corpus shows <c>options</c> as <c>allow_once</c> / <c>allow_always</c> /
    /// <c>reject_once</c>, with ids that are the adapter's own strings. Matching on <c>kind</c>
    /// survives an adapter that renames an id; falling back to the last option keeps the answer
    /// well-formed if it ever renames the kinds instead, and the convention in every observed set is
    /// that refusal is last.
    /// </remarks>
    private static string RejectOption(JsonObject parameters)
    {
        var options = parameters["options"] as JsonArray ?? [];
        string? last = null;

        foreach (var option in options.OfType<JsonObject>())
        {
            var id = (option["optionId"] as JsonValue)?.TryGetValue<string>(out var text) == true ? text : null;
            if (id is null)
            {
                continue;
            }

            last = id;
            if ((option["kind"] as JsonValue)?.TryGetValue<string>(out var kind) == true
                && kind.StartsWith("reject", StringComparison.Ordinal))
            {
                return id;
            }
        }

        return last ?? "reject";
    }
}
