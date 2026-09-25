using System.Runtime.Versioning;

namespace AiDe.Core.Tests;

/// <summary>
/// <c>ADR-0010</c> against a <b>live session</b> — the condition the Phase-2 exit review left open.
/// </summary>
/// <remarks>
/// <para><b>Why the existing dispatch tests were not enough.</b> <c>BoundaryDispatchTests</c> proves
/// the protocol: agreement between hosting modes, idempotency, the crash window, the checks that must
/// stay on their own side of the boundary. Every one of them writes to a <i>fixture</i> session. So
/// they prove the receipt is consistent with itself, and say nothing about whether a prompt that was
/// "accepted" ever reached a process that could act on it.</para>
///
/// <para><b>This closes that.</b> A real daemon over a real named pipe records the write-ahead
/// attempt; a real ConPTY PowerShell receives the prompt; and the prompt asks the shell to emit a
/// unique marker, which must come back <i>out</i> of the terminal before the test passes. A receipt
/// alone would be the protocol agreeing with itself.</para>
///
/// <para>Out of process because ConPTY needs a real console (<b>DC-014</b>), and its absence must
/// FAIL rather than skip (<b>DC-012</b>).</para>
/// </remarks>
[SupportedOSPlatform("windows")]
[Trait("Platform", "Windows")]
public sealed class DispatchLiveSessionTests
{
    [Fact]
    public async Task APromptDispatchedAcrossTheDaemon_ReachesALiveSessionAndIsExecuted()
    {
        var helper = TerminalHostLauncher.LocateHelper();
        var report = Path.Combine(Path.GetTempPath(), $"aide-dispatch-{Guid.NewGuid():N}.log");

        try
        {
            var exitCode = await TerminalHostLauncher.RunInNewConsoleAsync(
                helper, report, TimeSpan.FromMinutes(4), "dispatch");

            var log = File.Exists(report) ? await File.ReadAllTextAsync(report) : "(no report written)";

            // 6 is the interesting failure: the daemon recorded an accepted write and the session
            // never produced the marker — a prompt written into a void, which is precisely the
            // outcome a receipt on its own cannot distinguish from success.
            Assert.True(exitCode == 0, $"dispatch probe exited {exitCode}.\n{log}");

            Assert.Contains("PtyWriteAccepted", log, StringComparison.Ordinal);
            Assert.Contains("marker acted on: True", log, StringComparison.Ordinal);
        }
        finally
        {
            if (File.Exists(report)) File.Delete(report);
        }
    }
}
