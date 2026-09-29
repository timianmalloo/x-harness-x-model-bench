using System.Diagnostics;
using AiDe.Core.AgentPlane;

namespace AiDe.Core.Tests.AgentPlane;

/// <summary>
/// Ruling 104 condition 2 — the fresh-machine oracle: with HOME/USERPROFILE pointed at an empty
/// temp dir, (a)–(e) run end to end with <c>npm</c> pointed at a <b>local one-package registry</b>
/// (a Node http server on 127.0.0.1 serving a packument and a tarball packed from the stand-in
/// fixture; no live network), and the assertion is that <see cref="EngineCatalog.ResolveLaunch"/>
/// succeeds against the produced root and <see cref="ProviderConfiguration.ReadIfPresent"/>
/// round-trips the written file.
/// </summary>
/// <remarks>
/// <para><b>Mechanism, observed before it was built</b> (scratchpad spike, 2026-09-14): a pre-packed
/// tarball alone does not work — <c>npm install &lt;tgz&gt;</c> still resolves dependencies at the
/// registry — so the registry is the thing pointed at, and the stand-in package has none. The real
/// adapter is never downloaded here; the pinned <i>name and version</i> are the catalog's, so the
/// install line the product runs is exactly the one under test.</para>
///
/// <para>Runs only where <c>node</c> and <c>npm</c> are on PATH (the spike's machine baseline);
/// elsewhere it is skipped with the reason, never silently green.</para>
/// </remarks>
public sealed class TheFreshMachineOracleTests : IDisposable
{
    private readonly string _home = Directory.CreateTempSubdirectory("aide-fresh-machine-").FullName;

    public void Dispose()
    {
        try { Directory.Delete(_home, recursive: true); } catch (IOException) { }
    }

    [NodeAndNpmFact]
    public async Task AFreshMachineConfiguresClaudeCodeEndToEnd_AgainstALocalRegistry()
    {
        var node = FirstUse.Which("node")!;
        var npm = FirstUse.Which("npm")!;
        var fixtures = Path.Combine(AppContext.BaseDirectory, "fixtures", "first-use");
        var row = EngineCatalog.Find("claude-code");

        // The stand-in, packed once into the temp home — npm pack needs no network.
        var packed = Path.Combine(_home, "packed");
        Directory.CreateDirectory(packed);
        var tarball = await PackAsync(npm, Path.Combine(fixtures, "standin-adapter"), packed);

        // The local registry, on an ephemeral port; killed at the end whatever happens.
        using var registry = Process.Start(new ProcessStartInfo(node)
        {
            ArgumentList = { Path.Combine(fixtures, "local-registry.js"), row.AdapterPackage!, row.AdapterVersion!, tarball, "0" },
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true,
        })!;
        try
        {
            var listening = await registry.StandardOutput.ReadLineAsync().WaitAsync(TimeSpan.FromSeconds(15));
            Assert.StartsWith("listening ", listening, StringComparison.Ordinal);
            var port = listening!["listening ".Length..].Trim();

            // The fresh machine: an empty home, and npm isolated from the operator's own config and cache.
            var environment = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
            {
                ["HOME"] = _home,
                ["USERPROFILE"] = _home,
                ["npm_config_registry"] = $"http://127.0.0.1:{port}",
                ["npm_config_cache"] = Path.Combine(_home, "npm-cache"),
                ["npm_config_userconfig"] = Path.Combine(_home, ".npmrc"),
            };

            // (a) prerequisites — before any network; claude may be absent on a build machine, and its row then carries the cited instruction.
            var prerequisites = FirstUse.CheckPrerequisites(FirstUse.ClaudeCodeTools);
            Assert.True(prerequisites[0].Satisfied, prerequisites[0].Result);
            Assert.True(prerequisites[1].Satisfied, prerequisites[1].Result);
            Assert.True(prerequisites[2].Satisfied || prerequisites[2].Result.Contains("https://code.claude.com/docs/en/setup", StringComparison.Ordinal), prerequisites[2].Result);

            // (b) the default root under the fresh home — accepted.
            var root = FirstUse.DefaultAdapterRoot(_home);
            Assert.Null(FirstUse.AdapterRootRefusal(root));

            // (c) the install, run by the product's own function with the catalog's pin, against the local registry.
            var log = new List<string>();
            var install = await FirstUse.InstallAdapterAsync("claude-code", root, log.Add, TimeSpan.FromSeconds(90), environment, npm);
            Assert.True(install.Installed, install.Outcome + Environment.NewLine + string.Join(Environment.NewLine, log));
            Assert.Equal(0, install.ExitCode);
            Assert.Contains("--ignore-scripts", install.CommandLine, StringComparison.Ordinal);
            Assert.Contains($"{row.AdapterPackage}@{row.AdapterVersion}", install.CommandLine, StringComparison.Ordinal);

            // (d) sign-in skipped ⇒ (e) writes needs-login; the default root is not written.
            var path = FirstUse.ProviderFilePath(_home);
            FirstUse.WriteProviderFile(path, "anthropic", ProviderAuth.Subscription, "max", AccountHealth.NeedsLogin, "claude-code", "claude-sonnet-5", root);

            // THE ASSERTION (condition 2): ResolveLaunch succeeds against the produced root, ReadIfPresent round-trips.
            var read = ProviderConfiguration.ReadIfPresent(path);
            Assert.NotNull(read);
            Assert.True(read!.AdapterInstallRootIsDefault);
            Assert.Equal(root, read.AdapterInstallRoot);
            var launch = EngineCatalog.ResolveLaunch("claude-code", read.AdapterInstallRoot);
            Assert.True(File.Exists(launch.Arguments[0]), launch.Arguments[0]);
            Assert.Equal(install.ResolvedEntry, launch.Arguments[0]);
            Assert.Equal(AccountHealth.NeedsLogin, Assert.Single(read.Registry.Find("anthropic").Accounts).Health);
            Assert.Equal("claude-sonnet-5", read.ModelFor("claude-code"));
            Assert.Null(read.Bind("anthropic", "max", out var refusal));   // needs-login binds nothing — the sheet's row reads "needs sign-in"
            Assert.Equal("accountLabel", refusal!.Field);

            // Nothing left the fresh home: the adapter, the cache and the file are all beneath it.
            Assert.StartsWith(_home, launch.Arguments[0], StringComparison.OrdinalIgnoreCase);
        }
        finally
        {
            try { registry.Kill(entireProcessTree: true); } catch (InvalidOperationException) { }
        }
    }

    private static async Task<string> PackAsync(string npm, string package, string destination)
    {
        using var pack = Process.Start(new ProcessStartInfo(npm)
        {
            ArgumentList = { "pack", "--silent", "--pack-destination", destination },
            WorkingDirectory = package,
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true,
        })!;
        var output = await pack.StandardOutput.ReadToEndAsync();
        var error = await pack.StandardError.ReadToEndAsync();
        await pack.WaitForExitAsync().WaitAsync(TimeSpan.FromSeconds(60));
        Assert.True(pack.ExitCode == 0, "npm pack failed: " + error);
        var name = output.Split('\n').Select(l => l.Trim()).Last(l => l.EndsWith(".tgz", StringComparison.Ordinal));
        return Path.Combine(destination, name);
    }

    /// <summary>A fact that runs only where node and npm are on PATH; elsewhere it is skipped with the reason.</summary>
    private sealed class NodeAndNpmFactAttribute : FactAttribute
    {
        public NodeAndNpmFactAttribute()
        {
            if (FirstUse.Which("node") is null || FirstUse.Which("npm") is null)
            {
                Skip = "node and npm are not both on PATH; the fresh-machine oracle needs the spike's baseline (node v24.18.0, npm 12.0.2)";
            }
        }
    }
}
