using System.Diagnostics;
using System.Runtime.Versioning;
using AiDe.Core.AgentPlane;
using AiDe.Core.Facts;
using AiDe.Core.Terminal;

namespace AiDe.Core.Tests;

/// <summary>
/// A terminal session that ends says so on the same source it announced itself on (INV-0010).
/// </summary>
/// <remarks>
/// <para><b>The instrumentation gap this pins.</b> <c>ConPtyTerminalSession.StartAsync</c> opens
/// <c>terminal.start</c> on <c>aide.terminal.runtime</c>; nothing opens a stop. The operator's log
/// carries 4,115 <c>terminal.start</c> lines for one day and zero ends, so a leaked host — a start
/// with no end — is exactly the shape the log cannot show. A ledger that counts starts alone can
/// say a terminal was hosted; it cannot say one is still hosted.</para>
///
/// <para><b>Red first.</b> Written against a runtime with no <c>terminal.stop</c>; the fact fails
/// until the session emits one at the top of its end path — the attempt, not the success, on the
/// idiom <see cref="TerminalHostingLedger"/> already records.</para>
/// </remarks>
[SupportedOSPlatform("windows")]
[Trait("Platform", "Windows")]
public sealed class TerminalStopEventTests
{
    private const string StopActivity = "terminal.stop";

    [Fact]
    public async Task ADisposedSession_EmitsTerminalStopWithItsSessionId()
    {
        var stops = new List<Activity>();
        using var listener = new ActivityListener
        {
            ShouldListenTo = source => source.Name == TerminalHostingLedger.TerminalActivitySource,
            Sample = (ref ActivityCreationOptions<ActivityContext> _) => ActivitySamplingResult.AllDataAndRecorded,
            ActivityStarted = activity =>
            {
                if (activity.OperationName == StopActivity)
                {
                    lock (stops) { stops.Add(activity); }
                }
            },
        };
        ActivitySource.AddActivityListener(listener);

        using var deadline = new CancellationTokenSource(TimeSpan.FromSeconds(60));
        var session = await ConPtyTerminalSession.StartAsync(
            new TerminalSessionRequest(
                SessionId: "stop-event-disposed",
                Generation: 1,
                CommandLine: "cmd.exe",
                WorkingDirectory: Path.GetTempPath(),
                Columns: 80,
                Rows: 25,
                ProcessingClass: SessionProcessingClass.LocalOnly),
            deadline.Token);

        await session.DisposeAsync();

        Activity stop;
        lock (stops)
        {
            stop = Assert.Single(stops);
        }

        Assert.Equal("stop-event-disposed", stop.GetTagItem("session.id"));

        // How it ended is the attribute an operator sorts by: a kill is ours, an exit is the
        // child's. Disposal of a live shell is a kill.
        Assert.Equal(true, stop.GetTagItem("session.killed"));
    }

    /// <summary>
    /// A construction that fails after its start was counted closes its own pair: one stop,
    /// <c>start-failed</c>, no exit code — or <i>starts − stops</i> drifts by one per failure in
    /// the direction that reads as a held host.
    /// </summary>
    [Fact]
    public async Task AStartThatFails_EmitsOneTerminalStop_SoThePairIsClosed()
    {
        var stops = new List<Activity>();
        using var listener = new ActivityListener
        {
            ShouldListenTo = source => source.Name == TerminalHostingLedger.TerminalActivitySource,
            Sample = (ref ActivityCreationOptions<ActivityContext> _) => ActivitySamplingResult.AllDataAndRecorded,
            ActivityStarted = activity =>
            {
                if (activity.OperationName == StopActivity)
                {
                    lock (stops) { stops.Add(activity); }
                }
            },
        };
        ActivitySource.AddActivityListener(listener);
        using var ledger = TerminalHostingLedger.Open();

        await Assert.ThrowsAnyAsync<Exception>(() => ConPtyTerminalSession.StartAsync(
            new TerminalSessionRequest(
                SessionId: "stop-event-start-failed",
                Generation: 1,
                CommandLine: $"aide-no-such-shell-{Guid.NewGuid():N}.exe",
                WorkingDirectory: Path.GetTempPath(),
                Columns: 80,
                Rows: 25,
                ProcessingClass: SessionProcessingClass.LocalOnly),
            CancellationToken.None));

        Activity stop;
        lock (stops)
        {
            stop = Assert.Single(stops);
        }

        Assert.Equal("stop-event-start-failed", stop.GetTagItem("session.id"));
        Assert.Equal("start-failed", stop.GetTagItem("session.end_reason"));
        Assert.Null(stop.GetTagItem("session.exit_code"));
        Assert.Equal(1, ledger.Constructions);
        Assert.Equal(1, ledger.Completions);
    }

    [Fact]
    public async Task ASessionWhoseChildExits_EmitsTerminalStopWithTheExitCode()
    {
        var stops = new List<Activity>();
        using var listener = new ActivityListener
        {
            ShouldListenTo = source => source.Name == TerminalHostingLedger.TerminalActivitySource,
            Sample = (ref ActivityCreationOptions<ActivityContext> _) => ActivitySamplingResult.AllDataAndRecorded,
            ActivityStarted = activity =>
            {
                if (activity.OperationName == StopActivity)
                {
                    lock (stops) { stops.Add(activity); }
                }
            },
        };
        ActivitySource.AddActivityListener(listener);

        using var deadline = new CancellationTokenSource(TimeSpan.FromSeconds(60));
        var session = await ConPtyTerminalSession.StartAsync(
            new TerminalSessionRequest(
                SessionId: "stop-event-exited",
                Generation: 1,
                CommandLine: "cmd.exe /c exit 7",
                WorkingDirectory: Path.GetTempPath(),
                Columns: 80,
                Rows: 25,
                ProcessingClass: SessionProcessingClass.LocalOnly),
            deadline.Token);

        await using (session)
        {
            var exit = await session.WaitForExitAsync(deadline.Token);
            Assert.False(exit.Killed);
        }

        Activity stop;
        lock (stops)
        {
            stop = Assert.Single(stops);
        }

        Assert.Equal("stop-event-exited", stop.GetTagItem("session.id"));
        Assert.Equal(false, stop.GetTagItem("session.killed"));
        Assert.Equal(7, stop.GetTagItem("session.exit_code"));
    }
}
