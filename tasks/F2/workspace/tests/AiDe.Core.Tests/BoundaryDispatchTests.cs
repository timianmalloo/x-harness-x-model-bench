using System.Runtime.Versioning;
using AiDe.Core.Dispatch;
using AiDe.Core.Facts;
using AiDe.Core.Ipc;
using AiDe.Core.Projections;
using AiDe.Core.Store;

namespace AiDe.Core.Tests;

/// <summary>
/// Prompt dispatch across the daemon boundary — ADR-0010's two-phase receipt, with the two phases
/// now in different processes.
/// </summary>
/// <remarks>
/// <para><b>The property that matters is agreement.</b> The same dispatch performed in process and
/// across the pipe must produce the same receipt, for the same reason the read surface is tested
/// that way: the split must not quietly change what the product records about a side effect the user
/// can see. So each case runs both ways against one store and compares.</para>
///
/// <para><b>The crash window is the real subject.</b> D1 put terminals in the shell and the store in
/// the daemon, so a dispatch now spans two processes: the shell can die between making the attempt
/// durable and reporting its outcome. That window is exactly what the write-ahead exists for, and
/// the test below simulates it by never calling finalize.</para>
/// </remarks>
[SupportedOSPlatform("windows")]
[Trait("Platform", "Windows")]
public sealed class BoundaryDispatchTests : IDisposable
{
    private readonly TestWorkspace _workspace = TestWorkspace.Create();
    private readonly string _pipeName = "aide-dispatch-" + Guid.NewGuid().ToString("N")[..12];

    private DispatchCommand Command(string body = "run the tests", string draft = "draft-1") =>
        new(
            WorkspaceId: "ws-1",
            WorkspaceEpoch: _workspace.Store.CoreEpoch,
            Caller: new CallerPrincipal("user-1", CallerKind.Shell),
            CommandId: Guid.NewGuid().ToString("N"),
            DraftId: draft,
            RevisionNo: 1,
            Body: body,
            SessionId: "session-1",
            SessionGeneration: 1);

    private async Task WithDaemon(Func<WorkspaceClient, Task> body)
    {
        var endpoint = new DaemonEndpoint(
            _pipeName, new CapabilityRegistry(), _ => _workspace.Store.CoreEpoch);

        DaemonOperations.Register(endpoint, () => _workspace.Store.CoreEpoch);
        WorkspaceOperations.Register(endpoint, new ProjectionService(_workspace.Store));
        WorkspaceOperations.RegisterDispatch(endpoint, new BoundaryDispatcher(_workspace.Store));

        var server = new IpcServer(
            _pipeName, endpoint, new IpcServerOptions(StartupGrace: TimeSpan.FromSeconds(45)));

        using var life = new CancellationTokenSource(TimeSpan.FromSeconds(60));
        var running = server.RunAsync(life.Token);

        try
        {
            await using var client = await WorkspaceClient.ConnectAsync(
                _pipeName, TimeSpan.FromSeconds(20), CancellationToken.None);
            await body(client);
        }
        finally
        {
            await life.CancelAsync();
            try { await running; } catch (OperationCanceledException) { }
        }
    }

    // ---- agreement ----------------------------------------------------------

    [Fact]
    public async Task ADispatchOverThePipe_ProducesTheSameReceiptAsInProcess()
    {
        var local = new BoundaryDispatcher(_workspace.Store);

        var inProcessCommand = Command(draft: "draft-in-process");
        var inProcess = await BoundaryDispatcher.BeginAndWriteAsync(
            inProcessCommand,
            new FixtureTerminalSession("session-1", 1),
            (c, ct) => Task.FromResult(local.Begin(c)),
            (key, state, code, ct) => Task.FromResult(local.Finalize(key, state, code)));

        DispatchReceipt? remote = null;
        var remoteCommand = Command(draft: "draft-remote");
        await WithDaemon(async client =>
        {
            remote = await BoundaryDispatcher.BeginAndWriteAsync(
                remoteCommand,
                new FixtureTerminalSession("session-1", 1),
                client.DispatchBeginAsync,
                client.DispatchFinalizeAsync);
        });

        Assert.NotNull(remote);
        Assert.Equal(DispatchState.PtyWriteAccepted, inProcess.State);
        Assert.Equal(inProcess.State, remote!.State);
        Assert.Equal(inProcess.ErrorCode, remote.ErrorCode);
        Assert.Equal(inProcess.SessionId, remote.SessionId);
        Assert.Equal(inProcess.SessionGeneration, remote.SessionGeneration);
    }

    // ---- idempotency --------------------------------------------------------

    [Fact]
    public async Task ARetriedDispatch_DoesNotWriteToTheTerminalTwice()
    {
        // The point of the whole pattern: across a boundary a lost reply is ordinary, so the same
        // command WILL be retried. A second prompt landing in a live agent session is the outcome
        // this prevents.
        var command = Command();
        var session = new FixtureTerminalSession("session-1", 1);

        await WithDaemon(async client =>
        {
            var first = await BoundaryDispatcher.BeginAndWriteAsync(
                command, session, client.DispatchBeginAsync, client.DispatchFinalizeAsync);
            var second = await BoundaryDispatcher.BeginAndWriteAsync(
                command, session, client.DispatchBeginAsync, client.DispatchFinalizeAsync);

            Assert.Equal(first.State, second.State);
            Assert.Equal(1, session.AcceptedWriteCount);
        });
    }

    [Fact]
    public async Task ARetriedFinalize_DoesNotOverwriteADeliveredOutcome()
    {
        var command = Command();

        await WithDaemon(async client =>
        {
            await BoundaryDispatcher.BeginAndWriteAsync(
                command, new FixtureTerminalSession("session-1", 1),
                client.DispatchBeginAsync, client.DispatchFinalizeAsync);

            // A finalize whose reply was lost, retried with a WORSE outcome. The delivered state
            // must win — otherwise a network hiccup rewrites history into a failure.
            var again = await client.DispatchFinalizeAsync(
                command.DispatchKey, DispatchState.Failed, DispatchErrorCodes.WriteFailed, CancellationToken.None);

            Assert.Equal(DispatchState.PtyWriteAccepted, again.State);
        });
    }

    // ---- the crash window ---------------------------------------------------

    [Fact]
    public async Task AShellThatDiesAfterBegin_LeavesPending_WhichRecoveryResolvesToDeliveryUnknown()
    {
        var command = Command();

        await WithDaemon(async client =>
        {
            // Begin, then "die": never finalize. This is the shell crashing with the daemon alive —
            // a window that did not exist before the process split.
            var began = await client.DispatchBeginAsync(command, CancellationToken.None);
            Assert.False(began.AlreadyAttempted);
            Assert.Equal(DispatchState.Pending, began.Receipt.State);
        });

        var swept = new DispatchService(_workspace.Store).SweepPendingToUnknown();
        Assert.Equal(1, swept);

        var receipt = new DispatchService(_workspace.Store).ReadReceipt(command.DispatchKey);
        Assert.NotNull(receipt);
        Assert.Equal(DispatchState.DeliveryUnknown, receipt!.State);

        // And the honest state must survive a retry: the user decides whether to resend, because
        // only they know whether the agent acted on it.
        await WithDaemon(async client =>
        {
            var again = await client.DispatchBeginAsync(command, CancellationToken.None);
            Assert.True(again.AlreadyAttempted);
            Assert.Equal(DispatchState.DeliveryUnknown, again.Receipt.State);
        });
    }

    // ---- the checks that must stay on the right side of the boundary --------

    [Fact]
    public async Task TheSessionBindingIsCheckedBeforeAnythingIsMadeDurable()
    {
        // The daemon cannot make this check — it has no session — so it belongs with the caller,
        // and it must happen BEFORE begin or a mismatched command leaves a durable attempt behind.
        var command = Command();

        await WithDaemon(async client =>
        {
            await Assert.ThrowsAsync<WorkspaceStoreException>(() =>
                BoundaryDispatcher.BeginAndWriteAsync(
                    command,
                    new FixtureTerminalSession("a-different-session", 1),
                    client.DispatchBeginAsync,
                    client.DispatchFinalizeAsync));
        });

        Assert.Null(new DispatchService(_workspace.Store).ReadReceipt(command.DispatchKey));
    }

    [Fact]
    public async Task AStaleEpochIsRefusedByTheDaemon_AndRecordsNoAttempt()
    {
        var command = Command() with { WorkspaceEpoch = _workspace.Store.CoreEpoch + 99 };

        await WithDaemon(async client =>
        {
            await Assert.ThrowsAnyAsync<Exception>(() =>
                client.DispatchBeginAsync(command, CancellationToken.None));
        });

        Assert.Null(new DispatchService(_workspace.Store).ReadReceipt(command.DispatchKey));
    }

    // ---- DC-020: the control, widened past the operations that needed it ----

    [Fact]
    public async Task ADomainRefusalFromAnyOperation_IsRefused_AndTheDaemonSurvivesToAnswerTheNext()
    {
        // The generalisation, not the instance. A refusal that throws is correct while the caller
        // shares its stack; behind a server it is a shared-fate event. Asserting that the NEXT
        // request still answers is the half that proves the daemon lived.
        var endpoint = new DaemonEndpoint(
            _pipeName, new CapabilityRegistry(), _ => _workspace.Store.CoreEpoch);

        DaemonOperations.Register(endpoint, () => _workspace.Store.CoreEpoch);
        WorkspaceOperations.Register(endpoint, new ProjectionService(_workspace.Store));
        WorkspaceOperations.RegisterDispatch(endpoint, new BoundaryDispatcher(_workspace.Store));

        var server = new IpcServer(
            _pipeName, endpoint, new IpcServerOptions(StartupGrace: TimeSpan.FromSeconds(45)));

        using var life = new CancellationTokenSource(TimeSpan.FromSeconds(60));
        var running = server.RunAsync(life.Token);

        try
        {
            await using var client = await WorkspaceClient.ConnectAsync(
                _pipeName, TimeSpan.FromSeconds(20), CancellationToken.None);

            var stale = Command() with { WorkspaceEpoch = _workspace.Store.CoreEpoch + 99 };
            await Assert.ThrowsAnyAsync<Exception>(() => client.DispatchBeginAsync(stale, CancellationToken.None));

            // The daemon must still be serving. Before the fix this hung or faulted, because the
            // refusal had escaped the listen loop.
            var epoch = await client.RefreshEpochAsync(CancellationToken.None);
            Assert.Equal(_workspace.Store.CoreEpoch, epoch);
        }
        finally
        {
            await life.CancelAsync();
            try { await running; } catch (OperationCanceledException) { }
        }
    }

    public void Dispose() => _workspace.Dispose();
}
