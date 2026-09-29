using System.Runtime.Versioning;

namespace AiDe.Core.Tests;

/// <summary>
/// `P2-PRIV-01` — terminal output reaches the screen and nowhere else.
/// </summary>
/// <remarks>
/// <para><b>The spec makes terminal output the strictest data in the product:</b> "display only in
/// the live terminal… never automatically indexed, attached to prompts, or copied into audit or
/// telemetry". Credentials, tokens and customer data all pass through a terminal, so the guarantee
/// is not a policy but a property of the construction — bounded, in-memory, ephemeral.</para>
///
/// <para><b>It is an absence, so it is seeded rather than reasoned about.</b> Reading the code and
/// concluding nothing writes output to the store is an inference; printing a unique string and then
/// searching every span attribute and every file the workspace wrote is a measurement.</para>
///
/// <para><b>Two ways this test could lie, and what stops each.</b> If the seed never reached the
/// terminal, every absence would hold trivially — so the probe requires it to arrive first. If a
/// file could not be read, the scan would silently skip it — so an unreadable file fails the run.
/// The first version did exactly that: SQLite held the database open and the store, the most
/// important file in the check, was never scanned while the probe reported success.</para>
///
/// <para>Out of process because a real ConPTY child needs a real console (<b>DC-014</b>), and a real
/// child is the point — a fixture session would only prove the fixture keeps secrets.</para>
/// </remarks>
[SupportedOSPlatform("windows")]
[Trait("Platform", "Windows")]
public sealed class TerminalPrivacyTests
{
    [Fact]
    public async Task ASecretPrintedByATerminal_ReachesNoSpanAttributeAndNoWorkspaceFile()
    {
        var helper = TerminalHostLauncher.LocateHelper();
        var report = Path.Combine(Path.GetTempPath(), $"aide-privacy-{Guid.NewGuid():N}.log");

        try
        {
            var exitCode = await TerminalHostLauncher.RunInNewConsoleAsync(
                helper, report, TimeSpan.FromSeconds(120), mode: "privacy");
            var detail = File.Exists(report) ? File.ReadAllText(report) : "(no report written)";

            Assert.True(exitCode != 3, $"the probe could not start.\n{detail}");
            Assert.True(
                exitCode != 8,
                "the seeded secret never reached the terminal's output channel, so every absence "
                + $"this test asserts would have been vacuous.\n{detail}");
            Assert.True(
                exitCode != 9,
                "a workspace file could not be read, so the scan did not cover what it claims to. "
                + $"A pass here would be an absence over a set nobody looked at.\n{detail}");
            Assert.True(
                exitCode != 6,
                $"terminal output reached a span attribute. Telemetry must carry counts, never bytes.\n{detail}");
            Assert.True(
                exitCode != 7,
                "terminal output reached a file in the workspace. Output must never cross into the "
                + $"store, the audit trail or the health sidecar.\n{detail}");
            Assert.Equal(0, exitCode);

            // On the work, not the status code (DC-015): several probes share this executable and
            // every one of them exits 0 on success.
            Assert.Contains("reached the terminal's output channel", detail, StringComparison.Ordinal);
            Assert.Contains("reached no span attribute and no workspace file", detail, StringComparison.Ordinal);

            // And that the scan actually covered every file it found.
            Assert.DoesNotContain("NOT COVERED", detail, StringComparison.Ordinal);
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
