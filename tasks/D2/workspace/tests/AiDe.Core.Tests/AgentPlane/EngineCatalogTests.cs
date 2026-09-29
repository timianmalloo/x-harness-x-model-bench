using AiDe.Core.AgentPlane;

namespace AiDe.Core.Tests.AgentPlane;

/// <summary>
/// Engines are <b>data, not code paths</b> (spec §4.1) — and exactly two launch paths exist: an
/// adapter package under <c>node</c>, and a native CLI resolved from PATH without a shell.
/// </summary>
/// <remarks>
/// <para><b>Why the refusals are the important half.</b> Every mode the catalog does not launch —
/// <c>Observed</c>, <c>Deferred</c> — and every row whose launch has not been observed on a real
/// install is refused by name. The deferral is <i>enforced rather than remembered</i>: a refusal
/// goes red the moment someone half-implements a path, which is the model the programme's other
/// deferrals imitate.</para>
///
/// <para><b>The alarm fired, on purpose.</b> <c>ANonAdapterModeIsRefusedWithANamedReason</c> was
/// the catalog's <c>simplify:</c> trigger: "adapter launch only; upgrade trigger = first native-ACP
/// (copilot) spawn". The engine-backends spike of 2026-09-14 observed <c>copilot --acp</c> answer
/// <c>initialize</c> with <c>protocolVersion 1</c> (<c>spikes/engine-backends/copilot/fresh-home/frames.jsonl</c>),
/// so the test was re-pointed rather than deleted or renamed: the refusal it guards now names the
/// two non-adapter modes that still have no launch path, under the name the frozen F5 exit-evidence
/// record cites.</para>
///
/// <para><b>The pins come from the spike, not from memory.</b> Every launch line asserted below is
/// one the spike record (<c>docs/spikes/engine-backends-2026-09-14.md</c>, "Catalog consequences")
/// observed on this machine; a row whose line was never observed has no test that resolves it.</para>
/// </remarks>
public sealed class EngineCatalogTests
{
    private const string InstallRoot = @"C:\repo\spikes\acp-subscription-lane";

    /// <summary>
    /// The rows load as data, with the pinned packages and declared ACP modes.
    /// </summary>
    /// <remarks>
    /// fixture-derivation: ok — these literals are the pinned catalog facts from
    /// docs/notes/conductor-spec-errata-policy.md, spec §14.2 and the engine-backends spike. Pinning
    /// them is the case's whole purpose: a version that drifts without a recorded re-pin is the
    /// drift this catches.
    /// </remarks>
    [Fact]
    public void TheEngineRowsLoadWithTheirPinnedPackagesAndObservedLaunches()
    {
        Assert.Equal(5, EngineCatalog.Rows.Count);

        var claude = EngineCatalog.Find("claude-code");
        Assert.Equal("anthropic", claude.Provider);
        Assert.Equal(AcpMode.Adapter, claude.Acp);
        Assert.Equal("@agentclientprotocol/claude-agent-acp", claude.AdapterPackage);
        Assert.Equal("0.75.1", claude.AdapterVersion);
        Assert.Null(claude.Native);

        var codex = EngineCatalog.Find("codex");
        Assert.Equal("openai", codex.Provider);
        Assert.Equal(AcpMode.Adapter, codex.Acp);
        Assert.Equal("@agentclientprotocol/codex-acp", codex.AdapterPackage);
        Assert.Equal("1.10.0", codex.AdapterVersion);
        Assert.Equal("dist/index.js", codex.AdapterEntryModule);

        var copilot = EngineCatalog.Find("copilot");
        Assert.Equal("github", copilot.Provider);
        Assert.Equal(AcpMode.Native, copilot.Acp);
        Assert.Null(copilot.AdapterPackage);
        var native = Assert.IsType<NativeCommand>(copilot.Native);
        Assert.Equal("copilot", native.Command);
        Assert.Equal(["--acp"], native.Arguments);
        Assert.Equal("COPILOT_GH_HOST", native.HostVariable);

        var gemini = EngineCatalog.Find("gemini");
        Assert.Equal("google", gemini.Provider);
        Assert.Equal(AcpMode.Native, gemini.Acp);
        var geminiNative = Assert.IsType<NativeCommand>(gemini.Native);
        Assert.Equal("gemini", geminiNative.Command);
        Assert.Equal(["--acp"], geminiNative.Arguments);
        Assert.Equal("@google/gemini-cli", geminiNative.NpmPackage);
        Assert.Equal("bundle/gemini.js", geminiNative.NpmEntryModule);
        Assert.Null(geminiNative.HostVariable);

        var grok = EngineCatalog.Find("grok");
        Assert.Equal("xai", grok.Provider);
        Assert.Equal(AcpMode.Native, grok.Acp);
        var grokNative = Assert.IsType<NativeCommand>(grok.Native);
        Assert.Equal("grok", grokNative.Command);
        Assert.Equal(["agent", "stdio"], grokNative.Arguments);
        Assert.Equal("@xai-official/grok", grokNative.NpmPackage);
        Assert.Equal("bin/grok", grokNative.NpmEntryModule);
        Assert.Null(grokNative.HostVariable);
    }

    /// <summary>Every adapter row pins both a package and a version — an unpinned adapter is drift.</summary>
    [Fact]
    public void EveryAdapterRowPinsBothAPackageAndAVersion()
    {
        foreach (var row in EngineCatalog.Rows.Where(r => r.Acp == AcpMode.Adapter))
        {
            Assert.False(string.IsNullOrWhiteSpace(row.AdapterPackage), row.Id + " pins no package");
            Assert.False(string.IsNullOrWhiteSpace(row.AdapterVersion), row.Id + " pins no version");
            Assert.Null(row.Native);
        }
    }

    /// <summary>
    /// Every native row carries its command, its ACP arguments and the install instruction the
    /// spike copied — the three things a refusal has to be able to say.
    /// </summary>
    [Fact]
    public void EveryNativeRowCarriesACommandArgumentsAndAnInstallInstruction()
    {
        foreach (var row in EngineCatalog.Rows.Where(r => r.Acp == AcpMode.Native))
        {
            var native = Assert.IsType<NativeCommand>(row.Native);
            Assert.False(string.IsNullOrWhiteSpace(native.Command), row.Id + " names no command");
            Assert.NotEmpty(native.Arguments);
            Assert.False(string.IsNullOrWhiteSpace(native.InstallInstruction), row.Id + " carries no install instruction");
            Assert.Null(row.AdapterPackage);
            Assert.Null(row.AdapterEntryModule);
        }
    }

    /// <summary>The adapter launch path: an adapter engine whose entry module was observed.</summary>
    [Fact]
    public void TheAdapterLaunchPathResolvesForClaudeCode()
    {
        var launch = EngineCatalog.ResolveLaunch("claude-code", InstallRoot);

        Assert.Equal("node", launch.FileName);
        var module = Assert.Single(launch.Arguments);
        Assert.Equal(
            Path.Combine(InstallRoot, "node_modules", "@agentclientprotocol", "claude-agent-acp", "dist", "index.js"),
            module);
    }

    /// <summary>
    /// Ruling 97 condition 1, codex: the adapter path resolves the entry module the spike observed —
    /// <c>dist/index.js</c> of <c>@agentclientprotocol/codex-acp@1.10.0</c>, spawned as
    /// <c>node &lt;root&gt;/node_modules/@agentclientprotocol/codex-acp/dist/index.js</c>
    /// (<c>spikes/engine-backends/codex/frames.jsonl</c>).
    /// </summary>
    /// <remarks>
    /// <b>Red-first.</b> Before the entry was recorded this threw
    /// <c>AdapterEntryModuleNotRecorded</c> — the refusal that enforced the codex deferral until a
    /// real install was observed, and which <see cref="AnAdapterWithNoObservedEntryModuleIsRefusedRatherThanGuessed"/>
    /// still exercises on a synthetic row.
    /// </remarks>
    [Fact]
    public void TheAdapterLaunchPathResolvesForCodexWithTheObservedEntryModule()
    {
        var launch = EngineCatalog.ResolveLaunch("codex", InstallRoot);

        Assert.Equal("node", launch.FileName);
        var module = Assert.Single(launch.Arguments);
        Assert.Equal(
            Path.Combine(InstallRoot, "node_modules", "@agentclientprotocol", "codex-acp", "dist", "index.js"),
            module);
    }

    /// <summary>
    /// Ruling 97 condition 1, copilot: the native path resolves <c>copilot --acp</c> — the spike's
    /// observed launch line — to the executable on PATH, and never adds <c>--no-auto-login</c>.
    /// </summary>
    /// <remarks>
    /// <para><b>Red-first.</b> Before the Native path existed this threw
    /// <c>LaunchPathNotImplemented</c>, which was the alarm the catalog's <c>simplify:</c> comment
    /// named.</para>
    /// <para><b>Why <c>--no-auto-login</c> is asserted absent.</b> The spike measured it: with this
    /// machine's stored login and the flag, <c>session/new</c> was still refused
    /// <c>-32000 Authentication required</c>; without it, <c>session/new</c> succeeded — the flag
    /// suppresses the stored credential, not only a prompt
    /// (<c>spikes/engine-backends/copilot/existing-login/</c> vs <c>existing-login-autologin/</c>).</para>
    /// </remarks>
    [Fact]
    public void TheNativeLaunchPathResolvesCopilotToTheExecutableOnPath()
    {
        using var path = new FakePath();
        var exe = path.AddExecutable("copilot");

        var launch = EngineCatalog.ResolveLaunch("copilot", InstallRoot, path.Locator);

        Assert.Equal(exe, launch.FileName);
        Assert.Equal(["--acp"], launch.Arguments);
        Assert.DoesNotContain("--no-auto-login", launch.Arguments);
    }

    /// <summary>
    /// A direct executable wins over an npm <c>.cmd</c> shim wherever each sits on PATH: this
    /// machine carries both a winget <c>copilot.exe</c> and an older npm <c>copilot.cmd</c>
    /// (measured with <c>where copilot</c>, 2026-09-14), and only the executable's launch was observed.
    /// </summary>
    [Fact]
    [Trait("Platform", "Windows")]   // Ruling 117: a Windows scenario by its own doc comment; the Linux truth is TheLocatorTellsShimFromExecutableOnlyByWindowsSuffixTests
    public void ADirectExecutableWinsOverAnNpmShimEarlierOnPath()
    {
        using var path = new FakePath();
        path.AddNpmShim("copilot", "@github/copilot", "npm-loader.js");
        var exe = path.AddExecutable("copilot");

        var launch = EngineCatalog.ResolveLaunch("copilot", InstallRoot, path.Locator);

        Assert.Equal(exe, launch.FileName);
    }

    /// <summary>
    /// A native CLI that is not on PATH is refused, and the refusal carries the install instruction
    /// the spike copied from upstream — the operator's next action, not a Win32 message.
    /// </summary>
    [Fact]
    public void ANativeCommandThatIsNotOnPathIsRefusedWithItsInstallInstruction()
    {
        using var path = new FakePath();

        var error = Assert.Throws<AgentPlaneException>(
            () => EngineCatalog.ResolveLaunch("copilot", InstallRoot, path.Locator));

        Assert.Equal(AgentPlaneErrorCodes.EngineNotOnPath, error.Code);
        Assert.Contains("copilot", error.Message, StringComparison.Ordinal);
        Assert.Contains("winget install GitHub.Copilot", error.Message, StringComparison.Ordinal);
    }

    /// <summary>
    /// An npm <c>.cmd</c> shim for a CLI whose npm launch was never observed is refused rather than
    /// run through a shell: copilot's npm package exists, and only the winget executable's launch is
    /// in the spike record.
    /// </summary>
    [Fact]
    [Trait("Platform", "Windows")]   // Ruling 117: a Windows scenario by its own doc comment; the Linux truth is TheLocatorTellsShimFromExecutableOnlyByWindowsSuffixTests
    public void AnNpmShimForACliWithNoObservedNpmLaunchIsRefusedRatherThanRunThroughAShell()
    {
        using var path = new FakePath();
        path.AddNpmShim("copilot", "@github/copilot", "npm-loader.js");

        var error = Assert.Throws<AgentPlaneException>(
            () => EngineCatalog.ResolveLaunch("copilot", InstallRoot, path.Locator));

        Assert.Equal(AgentPlaneErrorCodes.EngineNotOnPath, error.Code);
        Assert.Contains("copilot", error.Message, StringComparison.Ordinal);
        Assert.Contains("shell", error.Message, StringComparison.OrdinalIgnoreCase);
    }

    /// <summary>
    /// Ruling 97 condition 1, gemini: <c>gemini --acp</c> resolves through npm's <c>.cmd</c> shim to
    /// the script beside it — <c>node &lt;npm prefix&gt;/node_modules/@google/gemini-cli/bundle/gemini.js --acp</c>,
    /// the line the spike spawned (<c>spikes/engine-backends/gemini/fresh-home/frames.jsonl</c>) —
    /// and never <c>--experimental-acp</c>, which <c>gemini --help</c> marks deprecated.
    /// </summary>
    /// <remarks>
    /// <b>Red-first.</b> Before the row existed this threw <c>UnknownEngine</c>. Measured on this
    /// machine: <c>where gemini</c> finds <c>%APPDATA%\npm\gemini.cmd</c> and no <c>gemini.exe</c>,
    /// so this is the pass every gemini launch on Windows takes.
    /// </remarks>
    [Fact]
    [Trait("Platform", "Windows")]   // Ruling 117: a Windows scenario by its own doc comment; the Linux truth is TheLocatorTellsShimFromExecutableOnlyByWindowsSuffixTests
    public void TheNativeLaunchPathResolvesGeminiThroughTheNpmShimToItsScript()
    {
        using var path = new FakePath();
        var script = path.AddNpmShim("gemini", "@google/gemini-cli", "bundle/gemini.js");

        var launch = EngineCatalog.ResolveLaunch("gemini", InstallRoot, path.Locator);

        Assert.Equal("node", launch.FileName);
        Assert.Equal([script, "--acp"], launch.Arguments);
        Assert.DoesNotContain("--experimental-acp", launch.Arguments);
    }

    /// <summary>
    /// An npm shim whose script is not beside it is refused by name, not handed to <c>node</c> to
    /// fail with "Cannot find module" after the lane has started.
    /// </summary>
    [Fact]
    [Trait("Platform", "Windows")]   // Ruling 117: a Windows scenario by its own doc comment; the Linux truth is TheLocatorTellsShimFromExecutableOnlyByWindowsSuffixTests
    public void AnNpmShimWithoutItsScriptIsRefusedRatherThanHandedToNode()
    {
        using var path = new FakePath();
        var script = path.AddNpmShim("gemini", "@google/gemini-cli", "bundle/gemini.js");
        File.Delete(script);

        var error = Assert.Throws<AgentPlaneException>(
            () => EngineCatalog.ResolveLaunch("gemini", InstallRoot, path.Locator));

        Assert.Equal(AgentPlaneErrorCodes.EngineNotOnPath, error.Code);
        Assert.Contains(script, error.Message, StringComparison.Ordinal);
        Assert.Contains("npm install -g @google/gemini-cli", error.Message, StringComparison.Ordinal);
    }

    /// <summary>
    /// An npm-delivered CLI that PATH lacks is resolved from the product's own install root — the
    /// place Ruling 104's <c>npm install --prefix &lt;root&gt;</c> puts it — and refused, naming the
    /// root, when it is not there either.
    /// </summary>
    [Fact]
    public void AnNpmDeliveredCliAbsentFromPathResolvesFromTheInstallRootOrIsRefusedNamingIt()
    {
        using var path = new FakePath();
        using var installRoot = new FakePath();
        var script = installRoot.AddNpmShim("gemini", "@google/gemini-cli", "bundle/gemini.js");

        var launch = EngineCatalog.ResolveLaunch("gemini", installRoot.Entries.Single(), path.Locator);
        Assert.Equal("node", launch.FileName);
        Assert.Equal([script, "--acp"], launch.Arguments);

        var error = Assert.Throws<AgentPlaneException>(
            () => EngineCatalog.ResolveLaunch("gemini", InstallRoot, path.Locator));
        Assert.Equal(AgentPlaneErrorCodes.EngineNotOnPath, error.Code);
        Assert.Contains(InstallRoot, error.Message, StringComparison.Ordinal);
        Assert.Contains("@google/gemini-cli", error.Message, StringComparison.Ordinal);
    }

    /// <summary>
    /// Ruling 97 condition 1, grok: <c>grok agent stdio</c> resolves to the executable on PATH when
    /// xAI's installer put one there, and otherwise — as on this machine, where <c>where grok</c>
    /// finds nothing — to the npm package under the install root, spawned as
    /// <c>node &lt;root&gt;/node_modules/@xai-official/grok/bin/grok agent stdio</c>, the line the
    /// spike observed (<c>spikes/engine-backends/grok/frames.jsonl</c>).
    /// </summary>
    /// <remarks>
    /// <b>Red-first.</b> Before the row existed both halves threw <c>UnknownEngine</c>. The npm shim
    /// pass is the same as gemini's and is not repeated here.
    /// </remarks>
    [Fact]
    public void TheNativeLaunchPathResolvesGrokFromPathOrFromTheInstallRoot()
    {
        using var path = new FakePath();
        var exe = path.AddExecutable("grok");
        var onPath = EngineCatalog.ResolveLaunch("grok", InstallRoot, path.Locator);
        Assert.Equal(exe, onPath.FileName);
        Assert.Equal(["agent", "stdio"], onPath.Arguments);

        using var emptyPath = new FakePath();
        using var installRoot = new FakePath();
        var script = installRoot.AddNpmShim("grok", "@xai-official/grok", "bin/grok");
        var fromRoot = EngineCatalog.ResolveLaunch("grok", installRoot.Entries.Single(), emptyPath.Locator);
        Assert.Equal("node", fromRoot.FileName);
        Assert.Equal([script, "agent", "stdio"], fromRoot.Arguments);
    }

    /// <summary>
    /// The two non-adapter modes with no launch path — <c>Observed</c>, <c>Deferred</c> — are still
    /// refused by name. The alarm the catalog's <c>simplify:</c> comment named has fired (copilot is
    /// Native and launches), so this is the <b>re-pointed</b> test: no catalog row carries either
    /// mode today, and the refusal is exercised on a synthetic row so it cannot rot into an untested
    /// branch.
    /// </summary>
    /// <remarks>
    /// <b>The name is kept on purpose.</b> The F5 exit-evidence record
    /// (<c>spikes/conductor-front-door-exit-run/exit-evidence.json</c>, clause 8) and its verifier —
    /// frozen at <c>1374401d</c> by its own clause 0 (Ruling 103) — cite this test by name as the
    /// proof that only <c>claude-code</c> was exercised at F5; a rename would make a frozen record
    /// point at nothing. What it guards moved from "every non-adapter mode" to "the two non-adapter
    /// modes that still have no path", which is the same clause read after Ruling 97 (iii).
    /// </remarks>
    [Theory]
    [InlineData(AcpMode.Observed)]
    [InlineData(AcpMode.Deferred)]
    public void ANonAdapterModeIsRefusedWithANamedReason(AcpMode mode)
    {
        var row = new EngineRow("someday", "someone", mode, null, null, null);

        var error = Assert.Throws<AgentPlaneException>(
            () => EngineCatalog.ResolveLaunch(row, InstallRoot, NativeCommandLocator.FromEnvironment()));

        Assert.Equal(AgentPlaneErrorCodes.LaunchPathNotImplemented, error.Code);
        Assert.Contains("someday", error.Message, StringComparison.Ordinal);
        Assert.Contains(mode.ToString(), error.Message, StringComparison.OrdinalIgnoreCase);
    }

    /// <summary>
    /// A native row that names no command is a row somebody half-filled: refused, not defaulted to
    /// the engine id.
    /// </summary>
    [Fact]
    public void ANativeRowWithNoCommandIsRefused()
    {
        var row = new EngineRow("halfway", "someone", AcpMode.Native, null, null, null);

        var error = Assert.Throws<AgentPlaneException>(
            () => EngineCatalog.ResolveLaunch(row, InstallRoot, NativeCommandLocator.FromEnvironment()));

        Assert.Equal(AgentPlaneErrorCodes.LaunchPathNotImplemented, error.Code);
        Assert.Contains("halfway", error.Message, StringComparison.Ordinal);
    }

    /// <summary>
    /// An adapter engine whose entry module has never been observed is refused too — the catalog
    /// does not guess a path it has not seen.
    /// </summary>
    /// <remarks>
    /// <c>codex</c> declared this refusal until its entry module was observed
    /// (<c>docs/spikes/engine-backends-2026-09-14.md</c> §2); the refusal itself stays, exercised on
    /// a synthetic row so that recording an entry cannot silently retire the branch.
    /// </remarks>
    [Fact]
    public void AnAdapterWithNoObservedEntryModuleIsRefusedRatherThanGuessed()
    {
        var row = new EngineRow("unseen", "someone", AcpMode.Adapter, "@example/unseen-acp", "0.0.1", null);

        var error = Assert.Throws<AgentPlaneException>(
            () => EngineCatalog.ResolveLaunch(row, InstallRoot, NativeCommandLocator.FromEnvironment()));

        Assert.Equal(AgentPlaneErrorCodes.AdapterEntryModuleNotRecorded, error.Code);
        Assert.Contains("unseen", error.Message, StringComparison.Ordinal);
    }

    /// <summary>An unknown engine id is refused, never defaulted, and the reason lists what is known.</summary>
    [Theory]
    [InlineData("grok-build")]
    [InlineData("antigravity")]
    [InlineData("Claude-Code")]
    [InlineData("")]
    public void AnUnknownEngineIdIsRefusedNeverDefaulted(string engineId)
    {
        var resolve = Assert.Throws<AgentPlaneException>(
            () => EngineCatalog.ResolveLaunch(engineId, InstallRoot));
        Assert.Equal(AgentPlaneErrorCodes.UnknownEngine, resolve.Code);
        Assert.Contains("claude-code", resolve.Message, StringComparison.Ordinal);

        var find = Assert.Throws<AgentPlaneException>(() => EngineCatalog.Find(engineId));
        Assert.Equal(AgentPlaneErrorCodes.UnknownEngine, find.Code);
    }

    // ---------------------------------------------------------------------------------------
    // The enterprise host rides on the ACCOUNT (Ruling 97 condition 3; Ruling 105 (1)) and reaches
    // the child as the variable the CLI's own help names.
    // ---------------------------------------------------------------------------------------

    /// <summary>
    /// A copilot account carrying <c>host</c> launches with <c>COPILOT_GH_HOST</c> set to it —
    /// the variable <c>copilot help environment</c> names as "used only by Copilot CLI for
    /// authentication and API requests, overriding GH_HOST when set"
    /// (<c>spikes/engine-backends/copilot/copilot-help-environment.txt:51</c>).
    /// </summary>
    [Fact]
    public void ACopilotAccountWithAHostLaunchesWithCopilotGhHost()
    {
        var account = new ProviderAccount("work", AccountHealth.Ready, Host: "mycompany.ghe.com");

        var environment = EngineCatalog.LaunchEnvironment(EngineCatalog.Find("copilot"), account);

        var pair = Assert.Single(environment);
        Assert.Equal("COPILOT_GH_HOST", pair.Key);
        Assert.Equal("mycompany.ghe.com", pair.Value);
    }

    /// <summary>An account with no host sets nothing: the CLI's default (github.com) is the CLI's.</summary>
    [Fact]
    public void AnAccountWithoutAHostSetsNoVariable()
    {
        var account = new ProviderAccount("personal", AccountHealth.Ready);

        Assert.Empty(EngineCatalog.LaunchEnvironment(EngineCatalog.Find("copilot"), account));
        Assert.Empty(EngineCatalog.LaunchEnvironment(EngineCatalog.Find("claude-code"), account));
    }

    /// <summary>
    /// A host on an account whose engine has no host variable is refused, not dropped: a launch that
    /// silently ignored it would sign in to the wrong tenant and look like success.
    /// </summary>
    [Fact]
    public void AHostOnAnEngineWithNoHostVariableIsRefusedRatherThanDropped()
    {
        var account = new ProviderAccount("work", AccountHealth.Ready, Host: "mycompany.ghe.com");

        var error = Assert.Throws<AgentPlaneException>(
            () => EngineCatalog.LaunchEnvironment(EngineCatalog.Find("claude-code"), account));

        Assert.Equal(AgentPlaneErrorCodes.LaunchPathNotImplemented, error.Code);
        Assert.Contains("claude-code", error.Message, StringComparison.Ordinal);
        Assert.Contains("mycompany.ghe.com", error.Message, StringComparison.Ordinal);
    }

    /// <summary>
    /// A PATH made of temp directories, so the locator's rules are asserted without this machine's
    /// PATH deciding the answer. Windows shapes on Windows (<c>.exe</c>, npm's <c>.cmd</c>), POSIX
    /// shapes elsewhere (an executable file, npm's extensionless sh shim).
    /// </summary>
    internal sealed class FakePath : IDisposable
    {
        private readonly string _root = Path.Combine(Path.GetTempPath(), "aide-fake-path-" + Guid.NewGuid().ToString("n")[..8]);
        private readonly List<string> _entries = [];

        public NativeCommandLocator Locator => new(_entries, OperatingSystem.IsWindows());

        /// <summary>The directories on this PATH, in order — each is also an npm prefix when a shim was added to it.</summary>
        public IReadOnlyList<string> Entries => _entries;

        /// <summary>A directory on PATH holding <c>&lt;command&gt;.exe</c> (or an executable file off Windows).</summary>
        public string AddExecutable(string command)
        {
            var dir = NewEntry();
            var file = Path.Combine(dir, OperatingSystem.IsWindows() ? command + ".exe" : command);
            File.WriteAllText(file, "not run");
            MarkExecutable(file);
            return file;
        }

        /// <summary>
        /// A directory on PATH holding npm's shim for <paramref name="command"/> beside a
        /// <c>node_modules/&lt;package&gt;/&lt;entry&gt;</c> — the shape <c>npm install -g</c> leaves
        /// (read from this machine's <c>%APPDATA%\npm\gemini.cmd</c>, 2026-09-14).
        /// </summary>
        public string AddNpmShim(string command, string package, string entry)
        {
            var dir = NewEntry();
            var script = Path.Combine([dir, "node_modules", .. package.Split('/'), .. entry.Split('/')]);
            Directory.CreateDirectory(Path.GetDirectoryName(script)!);
            File.WriteAllText(script, "// not run");

            var shim = Path.Combine(dir, OperatingSystem.IsWindows() ? command + ".cmd" : command);
            File.WriteAllText(shim, OperatingSystem.IsWindows()
                ? $"@ECHO off\r\n\"node\" \"%~dp0\\node_modules\\{package.Replace('/', '\\')}\\{entry.Replace('/', '\\')}\" %*\r\n"
                : $"#!/bin/sh\nexec node \"$(dirname \"$0\")/node_modules/{package}/{entry}\" \"$@\"\n");
            MarkExecutable(shim);
            return script;
        }

        private static void MarkExecutable(string file)
        {
            if (!OperatingSystem.IsWindows())
            {
                File.SetUnixFileMode(file, UnixFileMode.UserRead | UnixFileMode.UserWrite | UnixFileMode.UserExecute);
            }
        }

        private string NewEntry()
        {
            var dir = Path.Combine(_root, "entry-" + _entries.Count);
            Directory.CreateDirectory(dir);
            _entries.Add(dir);
            return dir;
        }

        public void Dispose()
        {
            try
            {
                Directory.Delete(_root, recursive: true);
            }
            catch (IOException)
            {
                // A temp tree that outlives the test is untidy, not a wrong answer.
            }
        }
    }
}
