using System.Threading.Channels;
using AiDe.Core.Dispatch;
using AiDe.Core.Facts;
using AiDe.Core.Store;

namespace AiDe.Core.Tests;

/// <summary>
/// P1-DISPATCH-01..04 — the crash window the Distributed Systems hard veto was raised on.
///
/// The claim under test is not "we call the terminal" but "at-most-once is TRUE across a process
/// death": a crash between the terminal accepting bytes and the outcome being recorded must resolve
/// to DeliveryUnknown, and a conformant retry must never re-send.
/// </summary>
public sealed class DispatchTests
{
    private static DispatchCommand Command(TestWorkspace workspace, string commandId = "cmd-1", long generation = 1)
        => new(
            WorkspaceId: "ws-1",
            WorkspaceEpoch: workspace.Store.CoreEpoch,
            Caller: new CallerPrincipal("shell-owner", CallerKind.Shell),
            CommandId: commandId,
            DraftId: "draft-1",
            RevisionNo: 1,
            Body: "Please review the Order aggregate.",
            SessionId: "session-1",
            SessionGeneration: generation);

    // P1-DISPATCH-01 — the happy path, and the honesty of what it proves.
    [Fact]
    public async Task Dispatch_WhenTerminalAccepts_RecordsPtyWriteAcceptedOnly()
    {
        using var workspace = TestWorkspace.Create();
        var service = new DispatchService(workspace.Store);
        var session = new FixtureTerminalSession("session-1", generation: 1);

        var receipt = await service.DispatchAsync(Command(workspace), session);

        Assert.Equal(DispatchState.PtyWriteAccepted, receipt.State);
        Assert.Equal(1, session.AcceptedWriteCount);
        // PtyWriteAccepted is terminal-byte acceptance, never agent acceptance (ADR-0007).
        Assert.NotEqual(DispatchState.DeliveryUnknown, receipt.State);
    }

    // P1-DISPATCH-02 — THE veto case.
    // Fails RED against a service that records the receipt only after the write: the crash leaves no
    // attempt row at all, ReadReceipt returns null, and the sweep has nothing to resolve.
    [Fact]
    public async Task Dispatch_CrashAfterWriteBeforeOutcome_ResolvesToDeliveryUnknownNotMissing()
    {
        using var workspace = TestWorkspace.Create();
        var command = Command(workspace);

        var session = new FixtureTerminalSession("session-1", generation: 1) { CrashAfterAcceptingWrite = true };
        var service = new DispatchService(workspace.Store);

        await Assert.ThrowsAsync<SimulatedProcessCrashException>(
            () => service.DispatchAsync(command, session));

        // The bytes really did reach the terminal, and the process died before recording that.
        Assert.Equal(1, session.AcceptedWriteCount);

        // Restart: recovery — not an in-memory field — must resolve the attempt.
        workspace.Reopen();
        var recovered = new DispatchService(workspace.Store);
        var swept = recovered.SweepPendingToUnknown();

        Assert.Equal(1, swept);
        var receipt = recovered.ReadReceipt(command.DispatchKey);
        Assert.NotNull(receipt);
        Assert.Equal(DispatchState.DeliveryUnknown, receipt.State);
    }

    // P1-DISPATCH-02 continued: the consequence that matters — a retry must not duplicate the prompt.
    [Fact]
    public async Task Retry_AfterUnknownDelivery_ReturnsTheReceiptAndNeverResends()
    {
        using var workspace = TestWorkspace.Create();
        var command = Command(workspace);
        var session = new FixtureTerminalSession("session-1", generation: 1) { CrashAfterAcceptingWrite = true };

        await Assert.ThrowsAsync<SimulatedProcessCrashException>(
            () => new DispatchService(workspace.Store).DispatchAsync(command, session));

        workspace.Reopen();
        var recovered = new DispatchService(workspace.Store);
        recovered.SweepPendingToUnknown();

        // A protocol-conformant client retries the same command id.
        session.CrashAfterAcceptingWrite = false;
        var retried = await recovered.DispatchAsync(
            command with { WorkspaceEpoch = workspace.Store.CoreEpoch }, session);

        Assert.Equal(DispatchState.DeliveryUnknown, retried.State);
        Assert.Equal(1, session.AcceptedWriteCount);   // still ONE — no duplicate prompt
    }

    // P1-DISPATCH-03 — crash between the attempt and the write. Honest: we cannot know, so Unknown.
    [Fact]
    public async Task Dispatch_CrashAfterAttemptBeforeWrite_AlsoResolvesToDeliveryUnknown()
    {
        using var workspace = TestWorkspace.Create();
        var command = Command(workspace);

        // A session that dies before accepting anything: no bytes written, attempt already durable.
        var session = new ThrowingBeforeWriteSession("session-1", 1);
        await Assert.ThrowsAsync<SimulatedProcessCrashException>(
            () => new DispatchService(workspace.Store).DispatchAsync(command, session));

        workspace.Reopen();
        var recovered = new DispatchService(workspace.Store);
        recovered.SweepPendingToUnknown();

        var receipt = recovered.ReadReceipt(command.DispatchKey);
        Assert.NotNull(receipt);
        // We know the bytes did NOT land, but the design refuses to guess from the outside:
        // an unresolved attempt is Unknown, and a human decides. Never an automatic resend.
        Assert.Equal(DispatchState.DeliveryUnknown, receipt.State);
    }

    // P1-DISPATCH-04 — the TOCTOU the Security review found: generation must be fenced AT the write.
    [Fact]
    public async Task Dispatch_WhenGenerationChangesBeforeTheWrite_IsRejectedAndWritesNoBytes()
    {
        using var workspace = TestWorkspace.Create();
        var service = new DispatchService(workspace.Store);
        var session = new FixtureTerminalSession("session-1", generation: 1)
        {
            AdvanceGenerationBeforeNextWrite = true,
        };

        var receipt = await service.DispatchAsync(Command(workspace, generation: 1), session);

        Assert.Equal(DispatchState.Rejected, receipt.State);
        Assert.Equal(DispatchErrorCodes.GenerationChanged, receipt.ErrorCode);
        Assert.Equal(0, session.AcceptedWriteCount);   // never retargeted to the new generation
    }

    [Fact]
    public async Task Dispatch_WithStaleEpoch_IsRejectedBeforeAnyAttemptIsRecorded()
    {
        using var workspace = TestWorkspace.Create();
        var service = new DispatchService(workspace.Store);
        var session = new FixtureTerminalSession("session-1", generation: 1);
        var stale = Command(workspace) with { WorkspaceEpoch = workspace.Store.CoreEpoch - 1 };

        var ex = await Assert.ThrowsAsync<WorkspaceStoreException>(
            () => service.DispatchAsync(stale, session));

        Assert.Equal(DispatchErrorCodes.EpochStale, ex.ErrorCode);
        Assert.Null(service.ReadReceipt(stale.DispatchKey));   // nothing was attempted
        Assert.Equal(0, session.AcceptedWriteCount);
    }

    // The dispatch key must be a deterministic function of the command id: two idempotency
    // namespaces would let a retry miss the receipt it was meant to find.
    [Fact]
    public void DispatchKey_IsDerivedDeterministicallyFromTheCommandId()
    {
        using var workspace = TestWorkspace.Create();

        var first = Command(workspace, "cmd-42");
        var second = Command(workspace, "cmd-42");
        var different = Command(workspace, "cmd-43");

        Assert.Equal(first.DispatchKey, second.DispatchKey);
        Assert.NotEqual(first.DispatchKey, different.DispatchKey);
    }

    [Fact]
    public async Task Sweep_WithNoPendingAttempts_IsANoOp()
    {
        using var workspace = TestWorkspace.Create();
        var service = new DispatchService(workspace.Store);
        await service.DispatchAsync(Command(workspace), new FixtureTerminalSession("session-1", 1));

        Assert.Equal(0, service.SweepPendingToUnknown());
    }

    /// <summary>
    /// A session that dies before it can accept anything — the crash-before-PTY-write case.
    /// </summary>
    /// <remarks>
    /// Deliberately NOT a <see cref="FixtureTerminalSession"/> with a flag: this one must fail
    /// *before* the write, and the fixture's crash knob fires after the bytes are accepted. They are
    /// different points either side of the durable receipt, which is the whole distinction the
    /// write-ahead protocol turns on.
    ///
    /// The members beyond <c>WriteAsync</c> exist only to satisfy the contract; this double never
    /// reaches them, so they are inert rather than implemented. It is exempt from the D7 conformance
    /// suite for that reason — it models one failure instant, not a terminal.
    /// </remarks>
    private sealed class ThrowingBeforeWriteSession(string sessionId, long generation) : ITerminalSession
    {
        private readonly Channel<TerminalChunk> _output = Channel.CreateUnbounded<TerminalChunk>();

        public string SessionId { get; } = sessionId;

        public long Generation { get; } = generation;

        public SessionProcessingClass ProcessingClass => SessionProcessingClass.LocalOnly;

        public ChannelReader<TerminalChunk> Output => _output.Reader;

        public SessionActivity Activity => SessionActivity.Ready;

        public Task<PtyWriteResult> WriteAsync(
            long expectedGeneration, ReadOnlyMemory<byte> bytes, CancellationToken cancellationToken)
            => throw new SimulatedProcessCrashException();

        public Task<SessionExit> WaitForExitAsync(CancellationToken cancellationToken) =>
            Task.FromResult(new SessionExit(ExitCode: null, Killed: true, DateTimeOffset.UtcNow));

        public ValueTask ResizeAsync(int columns, int rows, CancellationToken cancellationToken) =>
            ValueTask.CompletedTask;

        public ValueTask DisposeAsync()
        {
            _output.Writer.TryComplete();
            return ValueTask.CompletedTask;
        }
    }
}
