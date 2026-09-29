using System.Runtime.Versioning;

namespace AiDe.Core.Tests;

/// <summary>
/// A ConPTY child gets the user's environment minus Windows Terminal's own variables (INV-0010,
/// slice 0) — proven through a real pseudo console, not the block builder alone.
/// </summary>
/// <remarks>
/// <para><b>The cause of the "foreign" population.</b> This harness runs inside a Windows Terminal
/// tab, so every process it spawns inherits <c>WT_SESSION</c> and <c>WT_PROFILE_ID</c>. Windows
/// Terminal's agent host (<c>wta.exe → copilot.exe --acp --stdio</c>) treats each such ConPTY
/// session as one of its own and attaches an agent session to it, which loads the global MCP
/// config and spawns one <c>node higgsfield-mcp</c> + one console host — kept for Windows Terminal's
/// lifetime. Measured on 2026-09-12: 4 product-shaped sessions with <c>WT_*</c> → 4 births in 40 s;
/// the same 4 without → 0. Five straggler reports counted that pool as someone else's.</para>
///
/// <para>The helper sets <c>WT_*</c> and a control variable in its own environment, starts
/// <c>cmd.exe /c set</c> through the runtime, and reports by exit code what the child printed:
/// 0 when no <c>WT_</c> line arrived and the control did. Red on the un-fixed runtime (exit 2).</para>
/// </remarks>
[SupportedOSPlatform("windows")]
[Trait("Platform", "Windows")]
public sealed class TerminalChildEnvironmentTests
{
    [Fact]
    public async Task AConPtyChild_ReceivesNoWindowsTerminalVariable_AndTheRestOfTheEnvironment()
    {
        var helper = TerminalHostLauncher.LocateHelper();
        var report = Path.Combine(Path.GetTempPath(), $"aide-env-scrub-{Guid.NewGuid():N}.log");

        int exit;
        string detail;
        try
        {
            exit = await TerminalHostLauncher.RunInNewConsoleAsync(helper, report, TimeSpan.FromSeconds(60), "env-scrub");
            detail = File.Exists(report) ? await File.ReadAllTextAsync(report) : "(no report)";
        }
        finally
        {
            try { File.Delete(report); } catch (IOException) { }
        }

        Assert.True(exit == 0, $"the child's environment was not the scrubbed one (exit {exit}):\n{detail}");
    }
}
