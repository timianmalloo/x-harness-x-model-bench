using System.Runtime.Versioning;
using AiDe.Tests.Shared;
using Xunit.Abstractions;

namespace AiDe.Core.Tests;

/// <summary>
/// Does a <c>conhost.exe --headless</c> host survive the process that created it? (INV-0010)
/// </summary>
/// <remarks>
/// <para><b>The two exit paths the product actually has.</b> <c>WorkbenchShell.Dispose</c> — the
/// window's <c>Closed</c> handler — disposes session documents, persistence and the watcher, and
/// no <c>TerminalSurface</c>. So closing the App is <i>process exit with every terminal session
/// undisposed</i>: the kernel closes the session's kill-on-close job handle and its pseudo-console
/// handle, and nothing in our code runs. The second path is <c>taskkill /F</c> on the owner — a
/// hung test host, a crashed shell — which is the same handle-closing with even less ceremony.</para>
///
/// <para><b>Measured, not reasoned.</b> Whether the console host follows its owner on those paths
/// was asserted in comments ("the job object guarantees the child dies") and never counted. Each
/// fact here first proves the key can see a host (≥ 1 while the helper holds its session — a
/// count that cannot return non-zero would make the later zero worthless, DC-131 recurrence 2),
/// then counts again five seconds after the owner is gone. The count is the oracle; the number
/// is recorded in the test output either way.</para>
///
/// <para>The count runs <b>before the launcher releases its job</b>: the helper's hosts are inside
/// that job, and a count taken after release would credit the launcher's containment to the
/// product.</para>
/// </remarks>
[SupportedOSPlatform("windows")]
[Trait("Platform", "Windows")]
public sealed class TerminalHostExitPathTests(ITestOutputHelper output)
{
    private static readonly TimeSpan SettleAfterExit = TimeSpan.FromSeconds(5);

    [Fact]
    public Task AnOwnerThatExitsWithoutDisposing_LeavesNoHeadlessHostFiveSecondsLater() =>
        MeasureAsync("exit-undisposed");

    [Fact]
    public Task AnOwnerThatIsKilled_LeavesNoHeadlessHostFiveSecondsLater() =>
        MeasureAsync("kill-self");

    private async Task MeasureAsync(string mode)
    {
        var helper = TerminalHostLauncher.LocateHelper();
        var report = Path.Combine(Path.GetTempPath(), $"aide-exit-path-{mode}-{Guid.NewGuid():N}.log");

        var liveCount = -1;
        var afterCount = -1;
        var afterRows = "";

        try
        {
            // The helper publishes its pid, holds the session six seconds, then ends the process.
            // The launcher waits for exit; the hook below counts before the job is released.
            var launch = TerminalHostLauncher.RunInNewConsoleAsync(
                helper, report, TimeSpan.FromSeconds(60), mode,
                afterExit: async ownerPid =>
                {
                    await Task.Delay(SettleAfterExit);
                    var after = ConsoleHostCensus.Take();
                    Assert.True(after.Readable, "the process table could not be read after exit");
                    var survivors = after.HeadlessHostsOwnedBy(ownerPid);
                    afterCount = survivors.Count;
                    afterRows = ConsoleHostCensus.Describe(survivors);
                    output.WriteLine($"[{mode}] owner {ownerPid} gone; +{SettleAfterExit.TotalSeconds}s headless hosts still recording it as parent: {afterCount} {afterRows}");
                });

            // Meanwhile, while the helper holds its session: the oracle must see the host.
            var ownerPid = await ReadPidAsync(report, TimeSpan.FromSeconds(20));
            var live = await ConsoleHostCensus.WaitForHeadlessHostAsync(ownerPid, TimeSpan.FromSeconds(5));
            Assert.True(live.Readable, "the process table could not be read while the helper ran");
            liveCount = live.HeadlessHostsOwnedBy(ownerPid).Count;
            output.WriteLine($"[{mode}] owner {ownerPid} live; headless hosts it owns: {liveCount} {ConsoleHostCensus.Describe(live.HeadlessHostsOwnedBy(ownerPid))}");
            output.WriteLine($"[{mode}] owner's children while live: {ConsoleHostCensus.Describe(live.ChildrenOf(ownerPid))}");

            var exit = await launch;
            output.WriteLine($"[{mode}] helper exit code {exit}");
        }
        finally
        {
            try { File.Delete(report); } catch (IOException) { }
        }

        // THE KEY CAN SEE A HOST. Without this the zero below is the zero of an instrument that
        // cannot count.
        Assert.True(liveCount >= 1,
            $"the helper's session should have owned a conhost.exe --headless while it ran; saw {liveCount}");

        // THE MEASUREMENT. Today's answer is unknown; whatever it is, it is now a number.
        Assert.True(afterCount == 0,
            $"{afterCount} headless console host(s) still alive {SettleAfterExit.TotalSeconds}s after their owner ended by '{mode}': {afterRows}");
    }

    private static async Task<int> ReadPidAsync(string report, TimeSpan limit)
    {
        var stop = DateTimeOffset.UtcNow + limit;
        while (DateTimeOffset.UtcNow < stop)
        {
            if (File.Exists(report))
            {
                string text;
                try { text = await File.ReadAllTextAsync(report); }
                catch (IOException) { text = ""; }

                var line = text.Split('\n').FirstOrDefault(l => l.StartsWith("pid=", StringComparison.Ordinal));
                if (line is not null && int.TryParse(line["pid=".Length..].Trim(), out var pid))
                {
                    return pid;
                }
            }

            await Task.Delay(200);
        }

        throw new Xunit.Sdk.XunitException("the helper never published its pid; it did not start its session");
    }
}
