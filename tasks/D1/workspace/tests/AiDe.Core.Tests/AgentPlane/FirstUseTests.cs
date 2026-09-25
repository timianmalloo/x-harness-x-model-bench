using AiDe.Core.AgentPlane;

namespace AiDe.Core.Tests.AgentPlane;

/// <summary>
/// Ruling 104 (1)(a)–(e) for claude-code, as rules with no view and no network: prerequisite rows
/// before anything else, the adapter-root rule (a path inside a git checkout is refused — this
/// machine's spike path is the defect class, condition 7), the install's package/version come from
/// the catalog only, the result line names the resolved entry module, a timed-out install reads
/// "not recorded", and the provider file writer round-trips through the reader.
/// </summary>
public sealed class FirstUseTests : IDisposable
{
    private readonly string _root = Directory.CreateTempSubdirectory("aide-first-use-").FullName;

    public void Dispose()
    {
        try { Directory.Delete(_root, recursive: true); } catch (IOException) { }
    }

    /// <summary>(a): a missing tool's row carries the exact instruction copied from the spike, with its citation and the observed known-good version — never a modeled floor.</summary>
    [Fact]
    public void AMissingToolsRowCarriesTheCitedInstructionAndTheObservedKnownGood()
    {
        var empty = Path.Combine(_root, "empty-path");
        Directory.CreateDirectory(empty);

        var rows = FirstUse.CheckPrerequisites(FirstUse.ClaudeCodeTools, path: empty, version: _ => "never called");

        Assert.Equal(["node", "npm", "claude"], rows.Select(r => r.Tool));
        Assert.All(rows, r => Assert.False(r.Satisfied));

        var node = rows[0];
        Assert.Contains("winget install OpenJS.NodeJS.LTS", node.Result, StringComparison.Ordinal);
        Assert.Contains("v24.18.0", node.Result, StringComparison.Ordinal);
        Assert.Contains("docs/spikes/engine-backends-2026-09-14.md", node.Result, StringComparison.Ordinal);

        var claude = rows[2];
        Assert.Contains("irm https://claude.ai/install.ps1 | iex", claude.Result, StringComparison.Ordinal);
        Assert.Contains("2.1.268 (Claude Code)", claude.Result, StringComparison.Ordinal);
        Assert.Contains("https://code.claude.com/docs/en/setup", claude.Result, StringComparison.Ordinal);
    }

    /// <summary>(a): a present tool's row names where it resolved and what --version said; a version that did not answer is "not recorded".</summary>
    [Fact]
    public void APresentToolsRowNamesItsPathAndVersion()
    {
        var bin = Path.Combine(_root, "bin");
        Directory.CreateDirectory(bin);
        File.WriteAllText(Path.Combine(bin, OperatingSystem.IsWindows() ? "node.cmd" : "node"), "@echo v0.0.0-standin");

        var rows = FirstUse.CheckPrerequisites(["node"], path: bin, version: _ => "v0.0.0-standin");
        var node = Assert.Single(rows);
        Assert.True(node.Satisfied);
        Assert.Equal("v0.0.0-standin", node.Version);
        Assert.Contains(bin, node.ResolvedPath!, StringComparison.Ordinal);
        Assert.Null(node.Instruction);

        var silent = Assert.Single(FirstUse.CheckPrerequisites(["node"], path: bin, version: _ => null));
        Assert.False(silent.Satisfied);
        Assert.Contains("not recorded", silent.Result, StringComparison.Ordinal);
    }

    /// <summary>
    /// Found by the fresh-machine oracle: node ships an extensionless POSIX `npm` script beside `npm.cmd`,
    /// and a resolver that tries the bare name first hands CreateProcess a file it cannot run ("not a
    /// valid application for this OS platform"). On Windows the bare name never wins for an
    /// extensionless tool.
    /// </summary>
    [Fact]
    public void OnWindowsThePathResolverPrefersPathextOverAnExtensionlessScript()
    {
        var bin = Path.Combine(_root, "bin");
        Directory.CreateDirectory(bin);
        File.WriteAllText(Path.Combine(bin, "npm"), "#!/bin/sh\necho posix\n");
        File.WriteAllText(Path.Combine(bin, "npm.cmd"), "@echo cmd");

        var resolved = FirstUse.Which("npm", bin);

        Assert.Equal(OperatingSystem.IsWindows() ? Path.Combine(bin, "npm.cmd") : Path.Combine(bin, "npm"), resolved, StringComparer.OrdinalIgnoreCase);   // PATHEXT spells .CMD
    }

    /// <summary>(b), condition 7: a root inside a git checkout is refused with the reason; the product default is not.</summary>
    [Fact]
    public void ARootInsideAGitCheckoutIsRefusedWithTheReason()
    {
        var checkout = Path.Combine(_root, "repo");
        Directory.CreateDirectory(Path.Combine(checkout, ".git"));
        var inside = Path.Combine(checkout, "spikes", "acp-subscription-lane");

        var refusal = FirstUse.AdapterRootRefusal(inside);
        Assert.NotNull(refusal);
        Assert.Contains("inside the git checkout at", refusal, StringComparison.Ordinal);
        Assert.Contains(checkout, refusal, StringComparison.OrdinalIgnoreCase);

        Assert.Null(FirstUse.AdapterRootRefusal(FirstUse.DefaultAdapterRoot(Path.Combine(_root, "home"))));
        Assert.NotNull(FirstUse.AdapterRootRefusal(" "));

        // Condition 7 names this machine's current value; the rule is proven above on a fixture, and
        // here against the literal whenever that checkout exists (it does not on a fresh machine).
        const string thisMachinesValue = "C:/Projects/ai-de/spikes/acp-subscription-lane";
        if (Directory.Exists(Path.Combine("C:/Projects/ai-de", ".git")))
        {
            Assert.Contains("inside the git checkout at", FirstUse.AdapterRootRefusal(thisMachinesValue), StringComparison.Ordinal);
        }
    }

    /// <summary>(c): the install line is built from the catalog only, names the resolved entry, and a bound that expires reads "not recorded".</summary>
    [Fact]
    public async Task ATimedOutInstallReportsNotRecorded_AndTheLineComesFromTheCatalog()
    {
        var bin = Path.Combine(_root, "bin");
        Directory.CreateDirectory(bin);
        // A stand-in npm that never exits within the bound.
        var npm = Path.Combine(bin, OperatingSystem.IsWindows() ? "npm.cmd" : "npm");
        File.WriteAllText(npm, OperatingSystem.IsWindows() ? "@echo installing\r\n@ping -n 30 127.0.0.1 > nul\r\n" : "#!/bin/sh\necho installing\nsleep 30\n");
        if (!OperatingSystem.IsWindows())
        {
            File.SetUnixFileMode(npm, UnixFileMode.UserRead | UnixFileMode.UserWrite | UnixFileMode.UserExecute);
        }

        var log = new List<string>();
        var root = Path.Combine(_root, "adapters");
        var result = await FirstUse.InstallAdapterAsync("claude-code", root, log.Add, TimeSpan.FromSeconds(2), npmPath: npm);

        var row = EngineCatalog.Find("claude-code");
        Assert.Contains($"{row.AdapterPackage}@{row.AdapterVersion}", result.CommandLine, StringComparison.Ordinal);
        Assert.Contains("--ignore-scripts", result.CommandLine, StringComparison.Ordinal);
        Assert.Contains($"--prefix {root}", result.CommandLine, StringComparison.Ordinal);
        Assert.Null(result.ExitCode);
        Assert.False(result.Installed);
        Assert.Contains("not recorded", result.Outcome, StringComparison.Ordinal);
        Assert.Equal(EngineCatalog.ResolveLaunch("claude-code", root).Arguments[0], result.ResolvedEntry);
        Assert.Contains("installing", log);
    }

    /// <summary>(c): a non-adapter engine, and a root inside a checkout, refuse before anything runs.</summary>
    [Fact]
    public async Task TheInstallRefusesANonAdapterEngineAndACheckoutRoot()
    {
        var log = new List<string>();
        var native = await FirstUse.InstallAdapterAsync("copilot", Path.Combine(_root, "adapters"), log.Add, TimeSpan.FromSeconds(1), npmPath: "never-run");
        Assert.False(native.Installed);
        Assert.Contains("not an adapter engine", native.Outcome, StringComparison.Ordinal);

        Directory.CreateDirectory(Path.Combine(_root, "repo", ".git"));
        var checkout = await FirstUse.InstallAdapterAsync("claude-code", Path.Combine(_root, "repo", "adapters"), log.Add, TimeSpan.FromSeconds(1), npmPath: "never-run");
        Assert.False(checkout.Installed);
        Assert.Contains("inside the git checkout", checkout.Outcome, StringComparison.Ordinal);
        Assert.Empty(log);
    }

    /// <summary>(e): the written file round-trips through the reader; needs-login is the health for a skipped sign-in; the default root is not written; an override is.</summary>
    [Fact]
    public void TheWrittenProviderFileRoundTrips_AndTheDefaultRootIsNotWritten()
    {
        var home = Path.Combine(_root, "home");
        var path = FirstUse.ProviderFilePath(home);

        var read = FirstUse.WriteProviderFile(path, "anthropic", ProviderAuth.Subscription, "max", AccountHealth.NeedsLogin, "claude-code", "claude-sonnet-5");

        Assert.Equal(FirstUse.DefaultAdapterRoot(home), read.AdapterInstallRoot);
        Assert.True(read.AdapterInstallRootIsDefault);
        Assert.DoesNotContain("adapterInstallRoot", File.ReadAllText(path), StringComparison.Ordinal);
        var account = Assert.Single(read.Registry.Find("anthropic").Accounts);
        Assert.Equal("max", account.Label);
        Assert.Equal(AccountHealth.NeedsLogin, account.Health);
        Assert.Equal("claude-sonnet-5", read.ModelFor("claude-code"));
        Assert.Equal(("anthropic", "max"), read.FallbackDefaultAccount("claude-code"));

        var overridden = FirstUse.WriteProviderFile(path, "anthropic", ProviderAuth.Subscription, "max", AccountHealth.Ready, "claude-code", "claude-sonnet-5", Path.Combine(_root, "elsewhere"));
        Assert.False(overridden.AdapterInstallRootIsDefault);
        Assert.Contains("adapterInstallRoot", File.ReadAllText(path), StringComparison.Ordinal);
        Assert.Equal(AccountHealth.Ready, overridden.Registry.Find("anthropic").Accounts[0].Health);
    }
}
