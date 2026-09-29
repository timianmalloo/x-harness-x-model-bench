using System.Diagnostics;
using System.Text.Json.Nodes;

namespace AiDe.Core.AgentPlane;

/// <summary>
/// First use (Rulings 104 and 105 (2)): what the New Session sheet's <b>Configure…</b> runs, as
/// rules and processes with no view attached — prerequisite checks before any network, the adapter
/// root rule, the pinned adapter install the product runs on the operator's gesture, and the
/// <c>providers.json</c> writer. Engine-native only; no embedded browser; no credential handled.
/// </summary>
/// <remarks>
/// <para><b>Package and version come from <see cref="EngineCatalog"/> only</b> (Ruling 104 (1)(c),
/// frozen) — never from the file, never from input. The install line is
/// <c>npm install --prefix &lt;root&gt; --ignore-scripts &lt;package&gt;@&lt;version&gt;</c>; the
/// spike (<c>docs/spikes/engine-backends-2026-09-14.md</c> §6) observed that claude-code and codex
/// declare no lifecycle scripts, so the flag skips nothing there and stands as the named residual
/// supply-chain control (condition 5).</para>
///
/// <para><b>Copy is copied, not recalled</b> (condition 6): every install instruction on
/// <see cref="Prerequisite"/> is quoted from the spike record with its citation, and the known-good
/// version named is the one observed there (node v24.18.0; claude 2.1.268), never a modeled floor.</para>
///
/// <para><b>Every measurement degrades to "not recorded"</b>: a timed-out install reports no exit
/// code and no guessed state; "installed" is decided by <see cref="EngineCatalog.ResolveLaunch"/>'s
/// composed entry module being on disk, never by npm's exit code alone.</para>
/// </remarks>
public static class FirstUse
{
    /// <summary>The product default for the adapter root beneath a home directory: <c>~/.aide/adapters</c> (Ruling 104 (2)).</summary>
    public static string DefaultAdapterRoot(string homeDirectory)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(homeDirectory);
        return Path.Combine(homeDirectory, ".aide", "adapters");
    }

    /// <summary>The provider file beneath a home directory: <c>~/.aide/providers.json</c>.</summary>
    public static string ProviderFilePath(string homeDirectory)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(homeDirectory);
        return Path.Combine(homeDirectory, ".aide", ProviderConfiguration.FileName);
    }

    // ------------------------------------------------------------------ (a) prerequisites

    /// <summary>The tools claude-code's first use needs on PATH, in the order the rows render (Ruling 104 (1)(a)).</summary>
    public static readonly IReadOnlyList<string> ClaudeCodeTools = ["node", "npm", "claude"];

    /// <summary>
    /// The install instruction for a missing tool — <b>copied from the observed upstream source at
    /// spike time and cited</b> (Ruling 104 condition 6; <c>docs/spikes/engine-backends-2026-09-14.md</c> §6).
    /// </summary>
    /// <param name="Tool">The tool.</param>
    /// <param name="Instruction">The exact command or URL, verbatim from the source.</param>
    /// <param name="KnownGood">The version observed working on the spike machine — shown, never the newest.</param>
    /// <param name="Citation">Where the text was read, and when.</param>
    public sealed record InstallInstruction(string Tool, string Instruction, string KnownGood, string Citation);

    /// <summary>The instructions, by tool. <c>npm</c> ships with node, so its instruction is node's.</summary>
    public static IReadOnlyDictionary<string, InstallInstruction> InstallInstructions { get; } =
        new Dictionary<string, InstallInstruction>(StringComparer.Ordinal)
        {
            ["node"] = new(
                "node",
                "winget install OpenJS.NodeJS.LTS  (or the installer at https://nodejs.org/en/download)",
                "v24.18.0",
                "docs/spikes/engine-backends-2026-09-14.md §6 \"Missing node\" — winget show --id OpenJS.NodeJS.LTS, read 2026-09-14; https://nodejs.org/en/download"),
            ["npm"] = new(
                "npm",
                "winget install OpenJS.NodeJS.LTS  (npm ships with Node.js)",
                "12.0.2",
                "docs/spikes/engine-backends-2026-09-14.md — machine baseline, npm --version, 2026-09-14"),
            ["claude"] = new(
                "claude",
                "Windows PowerShell: irm https://claude.ai/install.ps1 | iex  ·  WinGet: winget install Anthropic.ClaudeCode  ·  npm: npm install -g @anthropic-ai/claude-code",
                "2.1.268 (Claude Code)",
                "docs/spikes/engine-backends-2026-09-14.md §6 \"Missing claude\" — https://code.claude.com/docs/en/setup, read 2026-09-14"),
        };

    /// <summary>One prerequisite row: the tool, where it resolved on PATH, its version, and — when missing — the cited instruction.</summary>
    /// <param name="Tool">The tool.</param>
    /// <param name="ResolvedPath">The executable PATH resolved, or null when not on PATH.</param>
    /// <param name="Version">What <c>--version</c> printed, or null (not on PATH, or it did not answer — the reason is on <see cref="Result"/>).</param>
    /// <param name="Instruction">The cited install instruction when the tool is missing; null when present.</param>
    public sealed record Prerequisite(string Tool, string? ResolvedPath, string? Version, InstallInstruction? Instruction)
    {
        /// <summary>Whether the tool is on PATH and answered its version.</summary>
        public bool Satisfied => ResolvedPath is not null && Version is not null;

        /// <summary>The result line the row shows.</summary>
        public string Result => ResolvedPath is null
            ? $"{Tool}: not on PATH. Install: {Instruction?.Instruction} — known-good {Instruction?.KnownGood} ({Instruction?.Citation})"
            : Version is null
                ? $"{Tool}: on PATH at {ResolvedPath}; --version did not answer (not recorded)"
                : $"{Tool}: {Version} at {ResolvedPath}";
    }

    /// <summary>
    /// Checks the prerequisites, <b>before any network</b>: each tool on PATH and its <c>--version</c>.
    /// </summary>
    /// <param name="tools">The tools, in row order.</param>
    /// <param name="path">The PATH to search — the process's by default; a test passes its own.</param>
    /// <param name="version">Runs <c>&lt;tool&gt; --version</c> and returns the first line, or null; the default runs the real process.</param>
    public static IReadOnlyList<Prerequisite> CheckPrerequisites(
        IReadOnlyList<string> tools, string? path = null, Func<string, string?>? version = null)
    {
        ArgumentNullException.ThrowIfNull(tools);
        version ??= ReadVersion;

        var rows = new List<Prerequisite>();
        foreach (var tool in tools)
        {
            var resolved = Which(tool, path);
            InstallInstructions.TryGetValue(tool, out var instruction);
            rows.Add(new Prerequisite(
                tool,
                resolved,
                resolved is null ? null : version(resolved),
                resolved is null ? instruction : null));
        }

        return rows;
    }

    /// <summary>Resolves a tool on PATH the way the shell would (PATHEXT on Windows), or null.</summary>
    public static string? Which(string tool, string? path = null)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(tool);
        path ??= Environment.GetEnvironmentVariable("PATH") ?? string.Empty;

        var extensions = OperatingSystem.IsWindows()
            ? (Environment.GetEnvironmentVariable("PATHEXT") ?? ".COM;.EXE;.BAT;.CMD").Split(';', StringSplitOptions.RemoveEmptyEntries)
            : [string.Empty];

        // On Windows the bare name is tried only when the tool already carries an extension: npm
        // ships an extensionless POSIX script beside npm.cmd, and CreateProcess cannot run it —
        // observed by the fresh-machine oracle ("not a valid application for this OS platform").
        var candidates = OperatingSystem.IsWindows() && !Path.HasExtension(tool) ? extensions : extensions.Prepend(string.Empty);
        foreach (var directory in path.Split(Path.PathSeparator, StringSplitOptions.RemoveEmptyEntries))
        {
            foreach (var extension in candidates)
            {
                var candidate = Path.Combine(directory.Trim('"'), tool + extension);
                if (File.Exists(candidate))
                {
                    return candidate;
                }
            }
        }

        return null;
    }

    /// <summary>Runs <c>&lt;tool&gt; --version</c> with a 15 s bound; the first non-blank line, or null.</summary>
    public static string? ReadVersion(string resolvedPath)
    {
        try
        {
            using var process = StartHidden(resolvedPath, ["--version"], workingDirectory: null, environment: null);
            var output = process.StandardOutput.ReadToEndAsync();
            var error = process.StandardError.ReadToEndAsync();
            if (!process.WaitForExit(15_000))
            {
                try { process.Kill(entireProcessTree: true); } catch (InvalidOperationException) { }
                return null;
            }

            var first = (output.Result + Environment.NewLine + error.Result)
                .Split('\n').Select(l => l.Trim()).FirstOrDefault(l => l.Length > 0);
            return process.ExitCode == 0 ? first : null;
        }
        catch (Exception error) when (error is IOException or InvalidOperationException or System.ComponentModel.Win32Exception)
        {
            return null;
        }
    }

    // ------------------------------------------------------------------ per-provider copy

    /// <summary>
    /// What the operator must do for a provider, as the spike observed it — <b>copied, cited, never
    /// recalled</b> (<c>docs/spikes/engine-backends-2026-09-14.md</c>, the "What the operator must do
    /// (attended)" row of each engine section). The install step runs inside the product only for
    /// adapter engines (<see cref="AcpMode.Adapter"/>); a native CLI's install command is shown as copy.
    /// </summary>
    /// <param name="ProviderId">The provider.</param>
    /// <param name="EngineId">The catalog engine that authenticates against it.</param>
    /// <param name="Install">The install step: the product runs it for an adapter engine; copy for a native CLI.</param>
    /// <param name="SignIn">The sign-in step, engine-native.</param>
    /// <param name="Citation">Where the copy was read.</param>
    /// <param name="Confidence">Verified (observed on the wire) or Inferred (a doc page said it), as the spike labelled it.</param>
    public sealed record ProviderSteps(string ProviderId, string EngineId, string Install, string SignIn, string Citation, string Confidence);

    /// <summary>The steps for every catalog provider; a provider the spike did not observe reads "not recorded".</summary>
    public static ProviderSteps StepsFor(string providerId)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(providerId);
        var engine = EngineCatalog.Rows.FirstOrDefault(r => string.Equals(r.Provider, providerId, StringComparison.Ordinal))?.Id ?? "not recorded";
        const string spike = "docs/spikes/engine-backends-2026-09-14.md";
        return providerId switch
        {
            "anthropic" => new(providerId, engine,
                "The product runs: npm install --prefix <root> --ignore-scripts @agentclientprotocol/claude-agent-acp@0.75.1 (package and version from EngineCatalog).",
                "Run `claude` and follow the browser prompts (a Pro, Max, Team, Enterprise, or Console account; ANTHROPIC_API_KEY prompts once to approve the key instead).",
                spike + " §6; https://code.claude.com/docs/en/setup, read 2026-09-14", "Verified (install, initialize); Inferred (sign-in copy: docs page)"),
            "openai" => new(providerId, engine,
                "Nothing to install beyond the adapter (the product's Configure… runs the pinned npm install: @agentclientprotocol/codex-acp@1.10.0, which bundles @openai/codex).",
                "Either ChatGPT — the ACP client sends authenticate {methodId:\"chat-gpt\"} (opens a browser) — or install the CLI once and run `codex login` so ~/.codex/auth.json exists — or set OPENAI_API_KEY (or CODEX_API_KEY) in the environment the product launches with.",
                spike + " §2 \"What the operator must do (attended)\"", "Verified"),
            "github" => new(providerId, engine,
                "winget install GitHub.Copilot  (or: npm install -g @github/copilot). Prerequisites: an active GitHub Copilot subscription; on Windows, PowerShell v6 or higher.",
                "`copilot login` (github.com / Enterprise Cloud) or `copilot login --host https://<tenant>.ghe.com` (data-residency tenants); a headless box: `copilot login --device-code`. The product then launches `copilot --acp` (never --no-auto-login).",
                spike + " §1 \"What the operator / colleague must do (attended)\"; https://docs.github.com/en/copilot/how-tos/set-up/install-copilot-cli", "Verified (handshake, login help); Inferred (install page)"),
            "google" => new(providerId, engine,
                "npm install -g @google/gemini-cli",
                "Set GEMINI_API_KEY (from https://aistudio.google.com/apikey) in the environment the product launches with — the only path observed to open a session on this CLI today. A personal \"Sign in with Google\" no longer opens a session; an enterprise Code Assist licence is untested.",
                spike + " §3 \"What the operator must do (attended)\"", "Verified (API-key path); Inferred (README install line)"),
            "xai" => new(providerId, engine,
                "irm https://x.ai/cli/install.ps1 | iex  (Windows PowerShell); or the adapter-style install of @xai-official/grok@1.0.30 — the engines lane owns grok's launch.",
                "Either set XAI_API_KEY in the launch environment, or run `grok login` once (browser).",
                spike + " §4 \"What the operator must do (attended)\"", "Verified (handshake); Inferred (installer line: docs)"),
            _ => new(providerId, engine, "not recorded", "not recorded", "no spike record names this provider", "Not recorded"),
        };
    }

    // ------------------------------------------------------------------ (b) the adapter root

    /// <summary>
    /// Why a chosen adapter root is refused, or null when it is acceptable (Ruling 104 (1)(b)): a
    /// path inside a git checkout is refused with the reason — this machine's spike path
    /// (<c>C:/Projects/ai-de/spikes/acp-subscription-lane</c>) is the defect class (condition 7).
    /// </summary>
    public static string? AdapterRootRefusal(string root)
    {
        if (string.IsNullOrWhiteSpace(root))
        {
            return "the adapter root is blank";
        }

        string full;
        try
        {
            full = Path.GetFullPath(root);
        }
        catch (Exception error) when (error is ArgumentException or NotSupportedException or PathTooLongException)
        {
            return "the adapter root is not a path: " + error.Message;
        }

        for (var directory = new DirectoryInfo(full); directory is not null; directory = directory.Parent)
        {
            var git = Path.Combine(directory.FullName, ".git");
            if (Directory.Exists(git) || File.Exists(git))
            {
                return $"{full} is inside the git checkout at {directory.FullName}; an adapter install "
                    + "belongs under ~/.aide/adapters, never in a repository";
            }
        }

        return null;
    }

    // ------------------------------------------------------------------ (c) the install

    /// <summary>What the install produced.</summary>
    /// <param name="CommandLine">The exact line that ran.</param>
    /// <param name="ExitCode">npm's exit code, or null — not recorded (timed out, or npm did not start).</param>
    /// <param name="Duration">Wall time, or null when npm did not start.</param>
    /// <param name="ResolvedEntry">The <c>&lt;root&gt;/node_modules/&lt;package&gt;/&lt;entry&gt;</c> <see cref="EngineCatalog.ResolveLaunch"/> looks for.</param>
    /// <param name="Installed">Whether that entry is on disk — the one fact that means "installed".</param>
    /// <param name="Outcome">The result line.</param>
    public sealed record InstallResult(
        string CommandLine, int? ExitCode, TimeSpan? Duration, string? ResolvedEntry, bool Installed, string Outcome);

    /// <summary>
    /// Runs <c>npm install --prefix &lt;root&gt; --ignore-scripts --no-audit --no-fund &lt;package&gt;@&lt;version&gt;</c>
    /// for an adapter engine, on the operator's gesture — never at start, never elevated — with
    /// stdout/stderr streamed to <paramref name="log"/> line by line and the exit code read.
    /// </summary>
    /// <param name="engineId">A catalog adapter engine; the package and version are the row's.</param>
    /// <param name="root">The adapter root (already past <see cref="AdapterRootRefusal"/>).</param>
    /// <param name="log">Where each output line goes, as it arrives.</param>
    /// <param name="timeout">The bound; on expiry the result reads "not recorded", never a guessed state.</param>
    /// <param name="environment">Extra environment for npm — a test points <c>npm_config_registry</c> at a local registry; the product passes none.</param>
    /// <param name="npmPath">The npm to run; resolved on PATH when null.</param>
    /// <param name="cancellationToken">The operator's cancel.</param>
    public static async Task<InstallResult> InstallAdapterAsync(
        string engineId,
        string root,
        Action<string> log,
        TimeSpan timeout,
        IReadOnlyDictionary<string, string>? environment = null,
        string? npmPath = null,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(root);
        ArgumentNullException.ThrowIfNull(log);

        var row = EngineCatalog.Find(engineId);
        if (row.Acp != AcpMode.Adapter || row.AdapterPackage is null || row.AdapterVersion is null)
        {
            return new InstallResult(string.Empty, null, null, null, false,
                $"engine '{row.Id}' is not an adapter engine with a pinned package; nothing to install");
        }

        if (AdapterRootRefusal(root) is { } refused)
        {
            return new InstallResult(string.Empty, null, null, null, false, refused);
        }

        // PACKAGE AND VERSION FROM THE CATALOG ONLY (Ruling 104 (1)(c)).
        var spec = $"{row.AdapterPackage}@{row.AdapterVersion}";
        string[] arguments = ["install", "--prefix", root, "--ignore-scripts", "--no-audit", "--no-fund", spec];
        var npm = npmPath ?? Which("npm");
        var commandLine = (npm ?? "npm") + " " + string.Join(' ', arguments);
        log(commandLine);

        if (npm is null)
        {
            return new InstallResult(commandLine, null, null, null, false, "npm is not on PATH; nothing ran");
        }

        Directory.CreateDirectory(root);
        var stopwatch = Stopwatch.StartNew();
        int? exitCode;
        try
        {
            using var process = StartHidden(npm, arguments, root, environment);
            var stdout = PumpAsync(process.StandardOutput, log);
            var stderr = PumpAsync(process.StandardError, log);
            using var bound = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
            bound.CancelAfter(timeout);
            try
            {
                await process.WaitForExitAsync(bound.Token).ConfigureAwait(false);
                await Task.WhenAll(stdout, stderr).ConfigureAwait(false);
                exitCode = process.ExitCode;
            }
            catch (OperationCanceledException)
            {
                try { process.Kill(entireProcessTree: true); } catch (InvalidOperationException) { }
                exitCode = null;
            }
        }
        catch (Exception error) when (error is IOException or InvalidOperationException or System.ComponentModel.Win32Exception)
        {
            log("npm did not start: " + error.Message);
            return new InstallResult(commandLine, null, null, null, false, "npm did not start: " + error.Message);
        }

        stopwatch.Stop();

        // "INSTALLED" IS THE CATALOG'S OWN READING (EngineCatalog.InstallRefusal — the sheet takes the
        // same one; DC-223), never npm's exit code alone.
        var entry = EngineCatalog.ResolveLaunch(row.Id, root).Arguments[0];
        var installed = EngineCatalog.InstallRefusal(row.Id, root) is null;
        var outcome = exitCode is null
            ? $"exit code not recorded (bound {timeout.TotalSeconds:0} s exceeded after {stopwatch.Elapsed.TotalSeconds:0.0} s); "
              + (installed ? $"{entry} is on disk" : $"{entry} is not on disk")
            : $"npm exited {exitCode} in {stopwatch.Elapsed.TotalSeconds:0.0} s; "
              + (installed ? $"installed: {entry}" : $"not installed: {entry} is not on disk");
        log(outcome);
        return new InstallResult(commandLine, exitCode, stopwatch.Elapsed, entry, installed, outcome);
    }

    // ------------------------------------------------------------------ (e) the provider file

    /// <summary>
    /// Writes <c>providers.json</c> for one provider and one account (Ruling 104 (1)(e)): the auth
    /// per the erratum, the label the operator typed, <c>health</c> as observed — <c>ready</c> after
    /// a returned sign-in, <c>needs-login</c> otherwise (no new value) — and
    /// <c>engines.&lt;id&gt;.model</c> from the given default. <c>adapterInstallRoot</c> is written
    /// only when <paramref name="adapterInstallRoot"/> is not the default beside the file (Ruling 104 (2)).
    /// </summary>
    /// <returns>The file as it reads back through <see cref="ProviderConfiguration.Read"/> — a round trip, not a hope.</returns>
    public static ProviderConfiguration WriteProviderFile(
        string path,
        string providerId,
        ProviderAuth auth,
        string accountLabel,
        AccountHealth health,
        string engineId,
        string model,
        string? adapterInstallRoot = null)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(path);
        ArgumentException.ThrowIfNullOrWhiteSpace(providerId);
        ArgumentException.ThrowIfNullOrWhiteSpace(accountLabel);
        ArgumentException.ThrowIfNullOrWhiteSpace(engineId);
        ArgumentException.ThrowIfNullOrWhiteSpace(model);
        EngineCatalog.Find(engineId);

        var file = new JsonObject();
        var defaultRoot = ProviderConfiguration.DefaultAdapterInstallRoot(path);
        if (adapterInstallRoot is not null
            && !string.Equals(Path.GetFullPath(adapterInstallRoot).TrimEnd(Path.DirectorySeparatorChar), defaultRoot.TrimEnd(Path.DirectorySeparatorChar), StringComparison.OrdinalIgnoreCase))
        {
            file["adapterInstallRoot"] = Path.GetFullPath(adapterInstallRoot).Replace('\\', '/');
        }

        file["providers"] = new JsonObject
        {
            [providerId] = new JsonObject
            {
                ["auth"] = auth == ProviderAuth.Subscription ? "subscription" : "api-key",
                ["accounts"] = new JsonArray(new JsonObject
                {
                    ["label"] = accountLabel,
                    ["health"] = health switch
                    {
                        AccountHealth.Ready => "ready",
                        AccountHealth.QuotaDegraded => "quota-degraded",
                        _ => "needs-login",
                    },
                }),
            },
        };
        file["engines"] = new JsonObject { [engineId] = new JsonObject { ["model"] = model } };

        Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(path))!);
        File.WriteAllText(path, file.ToJsonString(new System.Text.Json.JsonSerializerOptions { WriteIndented = true }));
        return ProviderConfiguration.Read(path);
    }

    // ------------------------------------------------------------------ processes

    private static Process StartHidden(string fileName, IReadOnlyList<string> arguments, string? workingDirectory, IReadOnlyDictionary<string, string>? environment)
    {
        var info = new ProcessStartInfo
        {
            FileName = fileName,
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            RedirectStandardInput = false,
            CreateNoWindow = true,
            WorkingDirectory = workingDirectory ?? string.Empty,
        };
        foreach (var argument in arguments)
        {
            info.ArgumentList.Add(argument);
        }

        if (environment is not null)
        {
            foreach (var (key, value) in environment)
            {
                info.Environment[key] = value;
            }
        }

        return Process.Start(info) ?? throw new InvalidOperationException($"{fileName} did not start");
    }

    private static async Task PumpAsync(StreamReader reader, Action<string> log)
    {
        while (await reader.ReadLineAsync().ConfigureAwait(false) is { } line)
        {
            log(line);
        }
    }
}
