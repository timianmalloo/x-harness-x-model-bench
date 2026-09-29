using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace AiDe.Core.PromptCompilation;

/// <summary>
/// The pin triple as <b>installed</b> on this machine (ADR-0035 rule 2): the adapter's version
/// and <c>dist/acp-agent.js</c> sha, the SDK's version, and the sha of the CLI binary the SDK
/// vendors — the binary that enforces the pin. Every sha is over raw bytes; an element that cannot
/// be read is <see cref="Envelope.NotRecorded"/>, never a plausible value.
/// </summary>
public sealed record InstalledPinTriple(
    string AdapterVersion,
    string AdapterSha256,
    string SdkVersion,
    string CliPath,
    string CliSha256);

/// <summary>What the recorded artifact says the triple was when the spike ran.</summary>
public sealed record RecordedPinTriple(string AdapterVersion, string AdapterSha256, string SdkVersion, string CliSha256);

/// <summary>A recount of <c>tool_call</c> / <c>tool_call_update</c> frames over a frame log — computed, never read from the artifact.</summary>
/// <param name="Frames">Lines that parsed as frames.</param>
/// <param name="ToolCalls">Frames whose <c>sessionUpdate</c> is a tool call or its update, of any name.</param>
/// <param name="ToolNames">Every tool name seen, distinct, ordered.</param>
/// <param name="Torn">Lines that did not parse — skipped and counted.</param>
public sealed record FrameRecount(int Frames, int ToolCalls, IReadOnlyList<string> ToolNames, int Torn);

/// <summary>
/// The gate-1 artifact as read: <c>compile-pin-spike.json</c>'s recorded triple and the frame log
/// it names (ADR-0036 Gate 1).
/// </summary>
/// <param name="Path">Where it was read from.</param>
/// <param name="Triple">The recorded triple.</param>
/// <param name="FrameLogSha256">The sha the artifact claims for its frame log, or null when it names none.</param>
/// <param name="RecordedToolCalls">The count the artifact claims — reported beside the recount, never trusted.</param>
/// <param name="Mode">The run's <c>mode</c> — <c>full</c> is the only admitting value.</param>
/// <param name="PromptsUnanswered">How many <c>prompt_N</c> entries carry no result — a prompt the run never finished.</param>
/// <param name="SentMeta">The <c>_meta</c> the run sent on <c>session/new</c>, as recorded, or null.</param>
public sealed record CompilePinArtifact(string Path, RecordedPinTriple Triple, string? FrameLogSha256, int? RecordedToolCalls, string? Mode, int PromptsUnanswered, JsonObject? SentMeta)
{
    /// <summary>The artifact's file name — the same name the Proof Pack's citation copy carries under <c>docs/proof/</c>.</summary>
    public const string FileName = "compile-pin-spike.json";

    /// <summary>The frame log's file name, beside the artifact (ADR-0036: machine-level, never a checkout's).</summary>
    public const string FrameLogFileName = "compile-pin-spike.frames.jsonl";

    /// <summary>
    /// Where the product reads the gate artifacts: <c>~/.aide/proof/</c>, beside
    /// <c>~/.aide/providers.json</c> — the pin is about <i>this machine's</i> installed adapter,
    /// SDK and CLI, not about which workspace is open (ADR-0036's path-resolution rule). A
    /// checkout-level copy would make the gate satisfiable by cloning a repository.
    /// </summary>
    public static string DefaultDirectory => System.IO.Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), ".aide", "proof");

    /// <summary>Reads the artifact, or null when the file is absent. A malformed file reads as absent with its reason in <paramref name="problem"/>.</summary>
    public static CompilePinArtifact? Read(string path, out string? problem)
    {
        problem = null;
        if (!File.Exists(path))
        {
            return null;
        }

        JsonObject? root;
        try
        {
            root = JsonNode.Parse(File.ReadAllText(path)) as JsonObject;
        }
        catch (JsonException error)
        {
            problem = "the artifact is not JSON: " + error.Message;
            return null;
        }

        if (root?["pin_triple"] is not JsonObject triple)
        {
            problem = "the artifact carries no pin_triple";
            return null;
        }

        static string Text(JsonNode? node) => node is JsonValue v && v.TryGetValue<string>(out var s) && !string.IsNullOrWhiteSpace(s) ? s : Envelope.NotRecorded;

        var unanswered = root.Where(m => m.Key.StartsWith("prompt_", StringComparison.Ordinal))
            .Count(m => m.Value is not JsonObject prompt || prompt["result"] is null);

        return new CompilePinArtifact(
            path,
            new RecordedPinTriple(Text(triple["adapter_version"]), Text(triple["adapter_sha256"]), Text(triple["sdk_version"]), Text(triple["cli_sha256"])),
            root["frame_log"] is JsonObject log && log["sha256"] is JsonValue sha && sha.TryGetValue<string>(out var text) ? text : null,
            root["tool_call_frame_count"] is JsonValue count && count.TryGetValue<int>(out var n) ? n : null,
            root["mode"] is JsonValue mode && mode.TryGetValue<string>(out var modeText) ? modeText : null,
            unanswered,
            root["sent_meta_triple"] as JsonObject);
    }
}

/// <summary>
/// The pin as a check: the installed triple from the adapter install root, the recount over a
/// frame log, and the comparison with the recorded artifact — one reader for the settings model
/// (Gate 1) and the compile host (verified per call, ADR-0035 rule 1).
/// </summary>
public static class CompilePin
{
    /// <summary>The adapter package whose entry module the catalog names.</summary>
    public const string AdapterPackage = "@agentclientprotocol/claude-agent-acp";

    /// <summary>The SDK package the adapter runs on.</summary>
    public const string SdkPackage = "@anthropic-ai/claude-agent-sdk";

    /// <summary>The adapter file whose sha is pinned — the file that forwards <c>tools</c> and launches the CLI.</summary>
    public const string AdapterAgentFile = "acp-agent.js";

    /// <summary>
    /// The platform package the SDK vendors its CLI in — <c>@anthropic-ai/claude-agent-sdk-&lt;platform&gt;-&lt;arch&gt;</c>
    /// (PD-5's second finding: not the machine's global <c>claude</c>).
    /// </summary>
    public static string CliPlatformPackage { get; } = "claude-agent-sdk-" + Platform() + "-" + Arch();

    /// <summary>The CLI binary's file name on this platform.</summary>
    public static string CliFileName { get; } = OperatingSystem.IsWindows() ? "claude.exe" : "claude";

    /// <summary>Reads the installed triple from the adapter install root's own bytes.</summary>
    public static InstalledPinTriple Installed(string adapterInstallRoot)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(adapterInstallRoot);

        var modules = Path.Combine(adapterInstallRoot, "node_modules");
        var adapterDirectory = Path.Combine(modules, "@agentclientprotocol", "claude-agent-acp");
        var cliPath = Path.Combine(modules, "@anthropic-ai", CliPlatformPackage, CliFileName);

        return new InstalledPinTriple(
            Version(Path.Combine(adapterDirectory, "package.json")),
            Sha256(Path.Combine(adapterDirectory, "dist", AdapterAgentFile)),
            Version(Path.Combine(modules, "@anthropic-ai", "claude-agent-sdk", "package.json")),
            cliPath,
            Sha256(cliPath));
    }

    /// <summary>
    /// Compares the installed triple with the recorded one: null when every element matches, else
    /// the elements that differ, named — the reason the settings model and the compile host show.
    /// </summary>
    public static string? Mismatch(InstalledPinTriple installed, RecordedPinTriple recorded)
    {
        ArgumentNullException.ThrowIfNull(installed);
        ArgumentNullException.ThrowIfNull(recorded);

        var differences = new List<string>();
        if (!string.Equals(installed.AdapterSha256, recorded.AdapterSha256, StringComparison.Ordinal))
        {
            differences.Add($"adapter {AdapterAgentFile} sha installed {Short(installed.AdapterSha256)} ≠ recorded {Short(recorded.AdapterSha256)}");
        }

        if (!string.Equals(installed.AdapterVersion, recorded.AdapterVersion, StringComparison.Ordinal))
        {
            differences.Add($"adapter version installed {installed.AdapterVersion} ≠ recorded {recorded.AdapterVersion}");
        }

        if (!string.Equals(installed.SdkVersion, recorded.SdkVersion, StringComparison.Ordinal))
        {
            differences.Add($"sdk version installed {installed.SdkVersion} ≠ recorded {recorded.SdkVersion}");
        }

        if (!string.Equals(installed.CliSha256, recorded.CliSha256, StringComparison.Ordinal))
        {
            differences.Add($"cli binary sha installed {Short(installed.CliSha256)} ≠ recorded {Short(recorded.CliSha256)}");
        }

        return differences.Count == 0 ? null : string.Join("; ", differences);
    }

    /// <summary>Recounts tool-call frames over a frame log's raw bytes (LLM-free; ADR-0036 Gate 1).</summary>
    public static FrameRecount Recount(ReadOnlySpan<byte> frameLog)
    {
        var frames = 0;
        var toolCalls = 0;
        var torn = 0;
        var names = new SortedSet<string>(StringComparer.Ordinal);

        foreach (var line in Encoding.UTF8.GetString(frameLog).Split('\n'))
        {
            var trimmed = line.TrimEnd('\r');
            if (trimmed.Length == 0)
            {
                continue;
            }

            JsonObject? frame;
            try
            {
                frame = JsonNode.Parse(trimmed) as JsonObject;
            }
            catch (JsonException)
            {
                frame = null;
            }

            if (frame is null)
            {
                torn++;
                continue;
            }

            frames++;
            if (frame["params"]?["update"] is JsonObject update
                && update["sessionUpdate"] is JsonValue kind && kind.TryGetValue<string>(out var text)
                && text is "tool_call" or "tool_call_update")
            {
                toolCalls++;
                var name = (update["_meta"]?["claudeCode"]?["toolName"] as JsonValue)?.GetValue<string>()
                    ?? (update["title"] as JsonValue)?.GetValue<string>();
                if (name is not null)
                {
                    names.Add(name);
                }
            }
        }

        return new FrameRecount(frames, toolCalls, [.. names], torn);
    }

    /// <summary>sha256 over the file's raw bytes, lowercase hex; <see cref="Envelope.NotRecorded"/> when the file cannot be read.</summary>
    public static string Sha256(string path)
    {
        try
        {
            return Convert.ToHexStringLower(SHA256.HashData(File.ReadAllBytes(path)));
        }
        catch (Exception error) when (error is IOException or UnauthorizedAccessException)
        {
            return Envelope.NotRecorded;
        }
    }

    private static string Version(string packageJson)
    {
        try
        {
            return (JsonNode.Parse(File.ReadAllText(packageJson))?["version"] as JsonValue)?.GetValue<string>() ?? Envelope.NotRecorded;
        }
        catch (Exception error) when (error is IOException or UnauthorizedAccessException or JsonException)
        {
            return Envelope.NotRecorded;
        }
    }

    private static string Short(string sha) => sha.Length > 12 ? sha[..12] + "…" : sha;

    private static string Platform() => OperatingSystem.IsWindows() ? "win32" : OperatingSystem.IsMacOS() ? "darwin" : "linux";

    private static string Arch() => RuntimeInformation.ProcessArchitecture switch
    {
        Architecture.Arm64 => "arm64",
        _ => "x64",
    };
}
