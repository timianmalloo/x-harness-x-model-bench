using System.Runtime.Versioning;

namespace AiDe.Core.Tests;

/// <summary>
/// The shell integration driving a real PowerShell through its whole state loop.
/// </summary>
/// <remarks>
/// <para><b>Everything that decides whether this feature exists is invisible until PowerShell runs
/// the script.</b> Whether PSReadLine is loaded at all under <c>-NoProfile</c> inside a pseudo
/// console; whether the <c>Enter</c> handler fires there; whether overriding <c>prompt</c> takes
/// effect when the host has already captured one; whether <c>-EncodedCommand</c> survives the
/// ConPTY launch path. <see cref="ShellIntegrationTests"/> can only assert on the text of a string —
/// this is the test that runs it.</para>
///
/// <para><b>The Busy half is the one that would rot silently.</b> Reaching <c>Ready</c> at a prompt
/// proves the D/A/B path. Reaching <c>Busy</c> during a command proves <c>C</c>, and <c>C</c> is the
/// mark whose absence is invisible at exactly the moment someone would look: the prompt still says
/// <c>Ready</c>, correctly, and the session then keeps saying it for the entire duration of every
/// command. That is a confident wrong answer, and worse than the heuristic the integration
/// displaced.</para>
///
/// <para>Out of process for the reason in <b>DC-014</b>: ConPTY attaches a child only when the host
/// owns a real console, and a <c>dotnet test</c> host never does.</para>
/// </remarks>
[SupportedOSPlatform("windows")]
[Trait("Platform", "Windows")]
public sealed class ShellIntegrationRoundTripTests
{
    [Fact]
    public async Task TheIntegration_DrivesReadyAtThePrompt_AndBusyWhileACommandRuns()
    {
        var helper = TerminalHostLauncher.LocateHelper();
        var report = Path.Combine(Path.GetTempPath(), $"aide-integration-{Guid.NewGuid():N}.log");

        try
        {
            var exitCode = await TerminalHostLauncher.RunInNewConsoleAsync(
                helper, report, TimeSpan.FromSeconds(120), mode: "integration");
            var detail = File.Exists(report) ? File.ReadAllText(report) : "(no report written)";

            Assert.True(exitCode != 3, $"the session could not start.\n{detail}");
            Assert.True(
                exitCode != 8,
                "the session never reported Ready at a prompt. Either the integration did not "
                + "install — the script returns without hooking anything when PSReadLine is absent, "
                + "so this is its expected shape on a shell that cannot host it — or its marks are "
                + $"not being authenticated.\n{detail}");
            Assert.True(
                exitCode != 9,
                "the session never reported Busy while a command ran. The C mark is not firing, so "
                + "every command now runs with the session claiming to be idle — and because an "
                + "authenticated claim retires the fallback heuristic, this is worse than having no "
                + $"integration at all.\n{detail}");
            Assert.True(
                exitCode != 10,
                $"the session never returned to Ready after the command finished.\n{detail}");
            Assert.Equal(0, exitCode);

            // Asserted on the work, not the status code (DC-015): several probes share this
            // executable and every one of them exits 0 on success.
            Assert.Contains("Ready at the prompt", detail, StringComparison.Ordinal);
            Assert.Contains("Busy while the command ran", detail, StringComparison.Ordinal);
            Assert.Contains("Ready again after the command", detail, StringComparison.Ordinal);
        }
        finally
        {
            try
            {
                File.Delete(report);
            }
            catch (IOException)
            {
            }
        }
    }
}
