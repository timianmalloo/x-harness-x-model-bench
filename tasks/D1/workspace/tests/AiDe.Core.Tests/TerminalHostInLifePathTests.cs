using System.Runtime.Versioning;
using AiDe.Tests.Shared;
using Xunit.Abstractions;

namespace AiDe.Core.Tests;

/// <summary>
/// While its owner lives, is a session's <c>conhost.exe --headless</c> released when the session is
/// disposed, and when the session's child exits on its own? (INV-0010)
/// </summary>
/// <remarks>
/// <para><b>The two paths the exit-path facts cannot see.</b> Closing a terminal TAB disposes its
/// session while the App keeps running (<c>WorkbenchAdapter.Render</c> →
/// <c>TerminalSurface.Dispose</c> → <c>DisposeAsync</c>, fire-and-forget). Typing <c>exit</c> ends
/// the shell while the pane keeps running: until INV-0010's fix, <c>WatchForExitAsync</c>
/// completed the session and closed nothing — not the pseudo console, not the job — so the host
/// lived on under the App (measured 1 → 1); it now releases both with the child (1 → 0). An
/// operator with the App open all day would otherwise accumulate one host per ended pane, under
/// <c>AiDe.App.exe</c> in Task Manager until the App closed.</para>
///
/// <para>Same discipline as <see cref="TerminalHostExitPathTests"/>: the key is shown to see ≥ 1
/// host, then the count is taken three seconds after the state is reached, with the owner alive.
/// The assertions state the behaviour the runtime's own contract implies — one ConPTY, one
/// process, one owner loop (ADR-0005): a host with no process and no loop has no owner.</para>
/// </remarks>
[SupportedOSPlatform("windows")]
[Trait("Platform", "Windows")]
public sealed class TerminalHostInLifePathTests(ITestOutputHelper output)
{
    private static readonly TimeSpan SettleAfterState = TimeSpan.FromSeconds(3);

    [Fact]
    public Task ADisposedSession_ReleasesItsHeadlessHostWhileTheOwnerLives() =>
        MeasureAsync("dispose-then-hold", "disposed=");

    [Fact]
    public Task ASessionWhoseChildExited_ReleasesItsHeadlessHostWhileTheOwnerLives() =>
        MeasureAsync("child-exit-then-hold", "child-exited=");

    private async Task MeasureAsync(string mode, string stateMarker)
    {
        var helper = TerminalHostLauncher.LocateHelper();
        var report = Path.Combine(Path.GetTempPath(), $"aide-in-life-{mode}-{Guid.NewGuid():N}.log");

        var liveCount = -1;
        var afterCount = -1;
        var afterRows = "";

        try
        {
            var launch = TerminalHostLauncher.RunInNewConsoleAsync(helper, report, TimeSpan.FromSeconds(60), mode);

            var ownerPid = await ReadMarkerAsync(report, "pid=", TimeSpan.FromSeconds(20));
            var pid = int.Parse(ownerPid);

            // The dispose path holds the session two seconds first; the child-exit path's child
            // lives seven seconds (DC-157: a child gone in 50 ms is gone before one CIM read).
            var live = await ConsoleHostCensus.WaitForHeadlessHostAsync(pid, TimeSpan.FromSeconds(5));
            liveCount = live.HeadlessHostsOwnedBy(pid).Count;
            output.WriteLine($"[{mode}] owner {pid} live; headless hosts it owns: {liveCount} {ConsoleHostCensus.Describe(live.HeadlessHostsOwnedBy(pid))}");

            var reached = await ReadMarkerAsync(report, stateMarker, TimeSpan.FromSeconds(30));
            output.WriteLine($"[{mode}] state reached: {stateMarker}{reached}");
            if (mode == "child-exit-then-hold")
            {
                // The child's OWN exit, not a kill: the helper's child ends with `exit 3`.
                Assert.Contains("code=3", reached);
            }

            await Task.Delay(SettleAfterState);
            var after = ConsoleHostCensus.Take();
            Assert.True(after.Readable, "the process table could not be read");
            var survivors = after.HeadlessHostsOwnedBy(pid);
            afterCount = survivors.Count;
            afterRows = ConsoleHostCensus.Describe(survivors);
            output.WriteLine($"[{mode}] +{SettleAfterState.TotalSeconds}s, owner still alive; headless hosts it owns: {afterCount} {afterRows}");
            output.WriteLine($"[{mode}] owner's children then: {ConsoleHostCensus.Describe(after.ChildrenOf(pid))}");

            var exit = await launch;
            output.WriteLine($"[{mode}] helper exit code {exit}");
        }
        finally
        {
            try { File.Delete(report); } catch (IOException) { }
        }

        Assert.True(liveCount >= 1,
            $"the helper's session should have owned a conhost.exe --headless while it started; saw {liveCount}");
        Assert.True(afterCount == 0,
            $"{afterCount} headless console host(s) still owned by the live owner {SettleAfterState.TotalSeconds}s after '{mode}': {afterRows}");
    }

    private static async Task<string> ReadMarkerAsync(string report, string marker, TimeSpan limit)
    {
        var stop = DateTimeOffset.UtcNow + limit;
        while (DateTimeOffset.UtcNow < stop)
        {
            if (File.Exists(report))
            {
                string text;
                try { text = await File.ReadAllTextAsync(report); }
                catch (IOException) { text = ""; }

                var line = text.Split('\n').FirstOrDefault(l => l.StartsWith(marker, StringComparison.Ordinal));
                if (line is not null)
                {
                    return line[marker.Length..].Trim();
                }
            }

            await Task.Delay(200);
        }

        throw new Xunit.Sdk.XunitException($"the helper never wrote '{marker}' to its report");
    }
}
