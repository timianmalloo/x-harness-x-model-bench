using System.Threading.Channels;
using AiDe.Core.Dispatch;
using AiDe.Core.Facts;

namespace AiDe.Core.Tests;

/// <summary>
/// Thrown by <see cref="FixtureTerminalSession"/> to stand in for the process dying after the bytes
/// were accepted but before the outcome was recorded. <see cref="DispatchService"/> deliberately does
/// not catch it, so the attempt is left Pending exactly as a real crash would leave it.
/// </summary>
internal sealed class SimulatedProcessCrashException : Exception
{
    public SimulatedProcessCrashException()
        : base("simulated process death after the terminal accepted the bytes")
    {
    }
}

/// <summary>
/// The Phase-1 substitute for the terminal runtime (D7). Holds written bytes in memory only —
/// never on disk, never in a log — because a test double persisting prompt text would itself be a
/// privacy finding.
/// </summary>
/// <remarks>
/// <para><b>Phase-2 amendment.</b> The contract gained output, activity, exit and resize, so the
/// fixture gained them too — and gained them for real rather than as stubs. A double that throws
/// <c>NotImplementedException</c> for half the contract cannot satisfy the D7 conformance suite, and
/// a conformance suite the fake cannot pass is one that gets quietly narrowed until it does.</para>
///
/// <para>It <b>echoes</b> what is written, which is the smallest behaviour that makes the output
/// channel observably real: a test can write a marker and read it back. It is not a terminal
/// emulator and interprets nothing.</para>
/// </remarks>
internal sealed class FixtureTerminalSession : ITerminalSession
{
    private readonly List<byte[]> _writes = [];
    private readonly Channel<TerminalChunk> _output = Channel.CreateUnbounded<TerminalChunk>();

    private readonly TaskCompletionSource<SessionExit> _exit =
        new(TaskCreationOptions.RunContinuationsAsynchronously);

    private readonly System.Threading.Lock _gate = new();
    private bool _disposed;

    public FixtureTerminalSession(
        string sessionId,
        long generation,
        SessionProcessingClass processingClass = SessionProcessingClass.LocalOnly)
    {
        SessionId = sessionId;
        Generation = generation;
        ProcessingClass = processingClass;
    }

    public string SessionId { get; }

    public long Generation { get; private set; }

    public SessionProcessingClass ProcessingClass { get; }

    public ChannelReader<TerminalChunk> Output => _output.Reader;

    public SessionActivity Activity { get; private set; } = SessionActivity.Ready;

    /// <summary>Number of times bytes were actually accepted — the assertion that proves no re-send.</summary>
    public int AcceptedWriteCount => _writes.Count;

    public IReadOnlyList<byte[]> Writes => _writes;

    /// <summary>When true, the session accepts the bytes and then simulates the process dying.</summary>
    public bool CrashAfterAcceptingWrite { get; set; }

    /// <summary>When true, the next write reports a generation change (zero bytes written).</summary>
    public bool AdvanceGenerationBeforeNextWrite { get; set; }

    public bool FailNextWrite { get; set; }

    /// <summary>The dimensions of the last resize, so a test can prove the call reached the session.</summary>
    public (int Columns, int Rows)? LastResize { get; private set; }

    public Task<PtyWriteResult> WriteAsync(
        long expectedGeneration, ReadOnlyMemory<byte> bytes, CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();

        if (Activity == SessionActivity.Ended)
        {
            // A dead session that accepted bytes would hand back a truthful-looking receipt for a
            // delivery that cannot have happened (DC-004).
            return Task.FromResult(PtyWriteResult.Failed);
        }

        if (AdvanceGenerationBeforeNextWrite)
        {
            // The real runtime replaces the process and bumps the generation on its owner loop; the
            // compare below is the same atomic compare-with-write a ConPTY implementation must do.
            Generation++;
            AdvanceGenerationBeforeNextWrite = false;
        }

        if (expectedGeneration != Generation)
        {
            return Task.FromResult(PtyWriteResult.GenerationChanged);
        }

        if (FailNextWrite)
        {
            FailNextWrite = false;
            return Task.FromResult(PtyWriteResult.Failed);
        }

        _writes.Add(bytes.ToArray());
        _output.Writer.TryWrite(new TerminalChunk(bytes.ToArray(), Truncated: false));

        if (CrashAfterAcceptingWrite)
        {
            throw new SimulatedProcessCrashException();
        }

        return Task.FromResult(PtyWriteResult.Accepted);
    }

    public Task<SessionExit> WaitForExitAsync(CancellationToken cancellationToken) =>
        _exit.Task.WaitAsync(cancellationToken);

    public ValueTask ResizeAsync(int columns, int rows, CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        LastResize = (columns, rows);
        return ValueTask.CompletedTask;
    }

    /// <summary>Ends the fixture's notional process — the fake's equivalent of the shell exiting.</summary>
    public void EndProcess(int? exitCode, bool killed = false)
    {
        lock (_gate)
        {
            if (Activity == SessionActivity.Ended)
            {
                return;
            }

            Activity = SessionActivity.Ended;
        }

        // Complete the channel BEFORE the exit task. A reader woken by the exit and then draining
        // must find a completed channel rather than blocking forever on one more read.
        _output.Writer.TryComplete();
        _exit.TrySetResult(new SessionExit(exitCode, killed, DateTimeOffset.UtcNow));
    }

    public ValueTask DisposeAsync()
    {
        if (_disposed)
        {
            return ValueTask.CompletedTask;
        }

        _disposed = true;
        EndProcess(exitCode: null, killed: true);
        return ValueTask.CompletedTask;
    }
}
