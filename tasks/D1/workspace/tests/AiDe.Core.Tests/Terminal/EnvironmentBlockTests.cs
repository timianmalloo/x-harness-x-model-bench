using System.Runtime.Versioning;
using AiDe.Core.Terminal;

namespace AiDe.Core.Tests.Terminal;

/// <summary>
/// The environment a terminal hands its child — the contract in
/// <c>docs/design/ux-agent-session-registration.md</c> §3.
/// </summary>
/// <remarks>
/// <para><b>These assert that there is NO total-size limit, which is the opposite of what an earlier
/// version asserted.</b> That version refused past 32,647 characters, from a bisection that had
/// measured <c>PATH</c> length and been written into the code as a block size — two different
/// quantities, one named with the other's units.</para>
///
/// <para><b>Re-measured through the hop that matters.</b> A <b>60,000-character non-PATH variable
/// passes a PowerShell-hosted launch intact</b>; a <b>33,000-character PATH breaks it</b>. So the
/// limit is on <c>PATH</c> — PowerShell resolves the command it was given through <c>PATH</c>, and
/// an oversized one stops it finding anything — and not on the block at all.</para>
///
/// <para><b>Why the guard was removed rather than corrected.</b> It would have refused launches that
/// work. A check that fires on correct behaviour gets switched off, and takes the real check with
/// it. Oversized <c>PATH</c> is already reported by <c>EnvironmentHealth</c> at a threshold far
/// below the one that breaks PowerShell, so the hazard that does exist is already covered.</para>
/// </remarks>
[SupportedOSPlatform("windows")]
[Trait("Platform", "Windows")]
public sealed class EnvironmentBlockTests
{
    [Fact]
    public void NoExtras_AndNoWindowsTerminalVariables_MeansInherit_SoTheCommonPathIsUnchanged()
    {
        using var _ = new WithoutWindowsTerminalVariables();

        Assert.Null(ConPtyInterop.BuildEnvironmentBlock(null));
        Assert.Null(ConPtyInterop.BuildEnvironmentBlock(new Dictionary<string, string>()));
    }

    /// <summary>
    /// Windows Terminal's own variables never reach a ConPTY child (INV-0010, slice 0).
    /// </summary>
    /// <remarks>
    /// <para><b>Measured, 2026-09-12, this machine.</b> Four product-shaped ConPTY sessions whose
    /// parent inherited <c>WT_SESSION</c>/<c>WT_PROFILE_ID</c> from the Windows Terminal tab this
    /// harness runs in caused <b>four</b> <c>node higgsfield-mcp</c> servers (+ four console hosts)
    /// to be born under Windows Terminal's agent host (<c>wta.exe → copilot.exe</c>) within 40 s —
    /// one per session, kept for Windows Terminal's lifetime; the same four with <c>WT_*</c> removed
    /// caused <b>zero</b>. That pool (111 → 291 in a day) was the "foreign" population of five
    /// straggler reports: foreign by parent, ours by cause.</para>
    /// <para>So the block is built whenever the parent carries a <c>WT_</c> variable, even with
    /// nothing extra to add, and carries none of them; everything else passes through unchanged
    /// (INV-0001: the user's environment reaches the shell — only <c>WT_*</c> leaves).</para>
    /// </remarks>
    [Fact]
    public void AParentInsideWindowsTerminal_HandsItsChildNoWT_Variable_AndEverythingElse()
    {
        const string control = "AIDE_BLOCK_TEST_PASSTHROUGH";
        Environment.SetEnvironmentVariable("WT_SESSION", "6238a91b-f02c-4aca-86ee-08e02378260a");
        Environment.SetEnvironmentVariable("WT_PROFILE_ID", "{61c54bbd-c2c6-5271-96e7-009a87ff44bf}");
        Environment.SetEnvironmentVariable("wt_probe_lowercase", "also-scrubbed");
        Environment.SetEnvironmentVariable(control, "kept");
        try
        {
            var block = ConPtyInterop.BuildEnvironmentBlock(null);

            Assert.NotNull(block);
            var entries = new string(block!).Split('\0', StringSplitOptions.RemoveEmptyEntries);

            Assert.DoesNotContain(entries, e => e.StartsWith("WT_", StringComparison.OrdinalIgnoreCase));
            Assert.Contains($"{control}=kept", entries);
            Assert.Contains(entries, e => e.StartsWith("PATH=", StringComparison.OrdinalIgnoreCase));

            // With extras too: the scrub and the contract compose.
            var withExtras = ConPtyInterop.BuildEnvironmentBlock(new Dictionary<string, string> { ["AIDE_SESSION"] = "s" });
            var withExtrasEntries = new string(withExtras!).Split('\0', StringSplitOptions.RemoveEmptyEntries);
            Assert.DoesNotContain(withExtrasEntries, e => e.StartsWith("WT_", StringComparison.OrdinalIgnoreCase));
            Assert.Contains("AIDE_SESSION=s", withExtrasEntries);
        }
        finally
        {
            Environment.SetEnvironmentVariable("WT_SESSION", null);
            Environment.SetEnvironmentVariable("WT_PROFILE_ID", null);
            Environment.SetEnvironmentVariable("wt_probe_lowercase", null);
            Environment.SetEnvironmentVariable(control, null);
        }
    }

    /// <summary>Removes every <c>WT_*</c> variable from this process for the scope, and restores it after.</summary>
    private sealed class WithoutWindowsTerminalVariables : IDisposable
    {
        private readonly Dictionary<string, string?> _saved = new(StringComparer.OrdinalIgnoreCase);

        public WithoutWindowsTerminalVariables()
        {
            foreach (System.Collections.DictionaryEntry e in Environment.GetEnvironmentVariables())
            {
                var name = e.Key?.ToString();
                if (name is not null && name.StartsWith("WT_", StringComparison.OrdinalIgnoreCase))
                {
                    _saved[name] = e.Value?.ToString();
                    Environment.SetEnvironmentVariable(name, null);
                }
            }
        }

        public void Dispose()
        {
            foreach (var (name, value) in _saved)
            {
                Environment.SetEnvironmentVariable(name, value);
            }
        }
    }

    [Fact]
    public void TheBlockCarriesTheExtras_AndIsDoubleNullTerminated()
    {
        var block = ConPtyInterop.BuildEnvironmentBlock(
            new Dictionary<string, string> { ["AIDE_SESSION"] = "surface-1" });

        Assert.NotNull(block);
        var text = new string(block!);

        Assert.Contains("AIDE_SESSION=surface-1\0", text, StringComparison.Ordinal);
        Assert.EndsWith("\0\0", text, StringComparison.Ordinal);
    }

    [Fact]
    public void TheExtrasOverrideTheInheritedValue_RatherThanAppearingTwice()
    {
        const string name = "AIDE_BLOCK_TEST_OVERRIDE";
        Environment.SetEnvironmentVariable(name, "inherited");
        try
        {
            var block = ConPtyInterop.BuildEnvironmentBlock(
                new Dictionary<string, string> { [name] = "supplied" });

            var text = new string(block!);
            Assert.Contains($"{name}=supplied\0", text, StringComparison.Ordinal);
            Assert.DoesNotContain($"{name}=inherited\0", text, StringComparison.Ordinal);
        }
        finally
        {
            Environment.SetEnvironmentVariable(name, null);
        }
    }

    /// <summary>
    /// A large addition still builds, because the limit is not on the block.
    /// </summary>
    /// <remarks>
    /// The test this replaces asserted a refusal at 32,647. Keeping the inverted assertion is the
    /// point: it fails if a size guard is ever reintroduced without a measurement behind it.
    /// </remarks>
    [Fact]
    public void ALargeAdditionStillBuilds_BecauseTheLimitIsNotOnTheBlock()
    {
        var block = ConPtyInterop.BuildEnvironmentBlock(
            new Dictionary<string, string> { ["AIDE_BLOCK_TEST_BIG"] = new('x', 40_000) });

        Assert.NotNull(block);
        Assert.True(block!.Length > 40_000, "the large value was not carried");
    }

    /// <summary>
    /// The contract's own variables are negligible, which is why they are safe to add.
    /// </summary>
    /// <remarks>
    /// §3's rule "keep every value short" survives the correction with a different justification: it
    /// is no longer defence against a block limit, it is what keeps the addition irrelevant to any
    /// limit anyone later discovers. A serialised payload here would deserve a fresh measurement.
    /// </remarks>
    [Fact]
    public void TheContractsOwnVariablesAreSmall_WhichIsWhyTheyAreSafe()
    {
        var contract = new Dictionary<string, string>
        {
            ["AIDE_SESSION"] = "agent:claude#a1b2c3",
            ["AIDE_TERMINAL_ID"] = "agent:claude#a1b2c3",
            ["AIDE_HARNESS"] = "claude-code",
            ["AIDE_AGENT"] = "claude",
            ["AIDE_CONTRACT_VERSION"] = "loomkeeper/1",
        };

        var added = contract.Sum(kv => kv.Key.Length + kv.Value.Length + 2);
        Assert.True(added < 512, $"the contract adds {added} chars; it is meant to be negligible");
    }
}
