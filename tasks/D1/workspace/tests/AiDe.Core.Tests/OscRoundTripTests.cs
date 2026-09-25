using System.Runtime.Versioning;

namespace AiDe.Core.Tests;

/// <summary>
/// `P2-TERM-06` end to end: OSC 133 driven through a <b>real</b> pseudo console by a real child.
/// </summary>
/// <remarks>
/// <para><b>What this proves that the unit tests cannot.</b> <see cref="OscParserTests"/> settles
/// what the parser does with bytes it is handed, and <see cref="TerminalActivityStateTests"/> settles
/// which signal wins. Neither can answer the question the whole feature rests on: <b>does an OSC
/// sequence written by a child process reach us at all?</b> ConPTY is not a pipe. It is a terminal
/// emulator that parses the child's output and re-emits its own VT stream, and a sequence it does
/// not itself act on could reasonably be swallowed on the way through. If it were, every unit test
/// above would still pass and shell integration would be silently inert in production — the exact
/// shape of a green suite proving something about a fake (<b>DC-002</b>).</para>
///
/// <para>It runs out of process for the reason recorded in <b>DC-014</b>: ConPTY only attaches a
/// child when the host owns a real console, and a <c>dotnet test</c> host never does.</para>
///
/// <para>Both halves matter. The <b>forged</b> claim is sent first, while the session is still using
/// the output heuristic, because that is the state a real session is in when a hostile child tries
/// it — testing it after a genuine claim had already made OSC authoritative would be an easier case
/// than the real one.</para>
/// </remarks>
[SupportedOSPlatform("windows")]
[Trait("Platform", "Windows")]
public sealed class OscRoundTripTests
{
    [Fact]
    public async Task AnAuthenticatedOsc133_DrivesActivity_AndAForgedOneDoesNot()
    {
        var helper = TerminalHostLauncher.LocateHelper();
        var report = Path.Combine(Path.GetTempPath(), $"aide-osc-host-{Guid.NewGuid():N}.log");

        try
        {
            var exitCode = await TerminalHostLauncher.RunInNewConsoleAsync(
                helper, report, TimeSpan.FromSeconds(90), mode: "osc");
            var detail = File.Exists(report) ? File.ReadAllText(report) : "(no report written)";

            Assert.True(exitCode != 3, $"the session could not start.\n{detail}");
            Assert.True(
                exitCode != 5,
                "an OSC 133;D carrying NO nonce was honoured. Any process that can print can now "
                + $"report itself idle while it keeps running.\n{detail}");
            Assert.True(
                exitCode != 6,
                "an OSC 133;D carrying the session nonce did NOT reach the parser. Either ConPTY "
                + "does not pass OSC through to the output pipe, or the read loop is not feeding "
                + $"the parser — shell integration is inert either way.\n{detail}");
            Assert.True(exitCode != 7, $"the probe timed out.\n{detail}");
            Assert.Equal(0, exitCode);

            // Exit code 0 is not enough on its own. An earlier revision of this test passed in
            // 200 ms because the mode argument silently never reached the helper, so it ran the
            // OTHER probe — which also succeeds and also returns 0. Asserting on the report makes
            // the test name and the work it did impossible to separate (DC-012).
            Assert.Contains("activity after the forged claim: Busy", detail, StringComparison.Ordinal);
            Assert.Contains("activity after the authenticated claim: Ready", detail, StringComparison.Ordinal);
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
