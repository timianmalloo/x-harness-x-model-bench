using System.Runtime.InteropServices;
using System.Runtime.Versioning;
using System.Text;
using AiDe.Core.Dispatch;
using AiDe.Core.Facts;
using AiDe.Core.Terminal;

namespace AiDe.Core.Tests;

/// <summary>
/// The D7 conformance suite: every behaviour <see cref="ITerminalSession"/> promises, asserted
/// against <b>every</b> implementation.
/// </summary>
/// <remarks>
/// <para><b>Why this is owed now and was not before.</b> Phase 1 had exactly one implementation, so
/// there was nothing for a fake to diverge from. Phase 2 has two, and the fixture is what every
/// dispatch test runs against — so without this suite, <c>DispatchTests</c> proves something about
/// <see cref="FixtureTerminalSession"/> rather than about the terminal seam. The Testing Strategy's
/// D7 directive fires exactly at the moment a second implementation appears.</para>
///
/// <para>The cases below are deliberately restricted to what the <i>contract</i> says. Crash
/// injection and generation forcing are fixture knobs, not contract behaviour, so they stay in
/// <c>DispatchTests</c>; asserting them here would make the suite unimplementable by the real
/// runtime and would quietly become a fixture-only suite wearing a conformance label.</para>
/// </remarks>
public abstract class TerminalSessionConformanceTests : IDisposable
{
    // Every case here can touch a real process, and a hung ConPTY read would otherwise stall the
    // whole run rather than fail one test. A per-test deadline turns a hang into a failure.
    private readonly CancellationTokenSource _deadline = new(TimeSpan.FromSeconds(60));

    /// <summary>The per-test deadline. Passed to every awaited call so nothing can hang the suite.</summary>
    protected CancellationToken Token => _deadline.Token;

    public void Dispose()
    {
        _deadline.Dispose();
        GC.SuppressFinalize(this);
    }

    /// <summary>Creates a live session that echoes what is written to it and then ends on demand.</summary>
    protected abstract Task<ITerminalSession> CreateAsync(string sessionId, long generation);

    /// <summary>Asks the session's process to end, however that implementation ends one.</summary>
    protected abstract Task RequestExitAsync(ITerminalSession session);

    [Fact]
    public async Task Identity_IsStableAndMatchesWhatItWasCreatedWith()
    {
        await using var session = await CreateAsync("session-conformance", generation: 7);

        Assert.Equal("session-conformance", session.SessionId);
        Assert.Equal(7, session.Generation);
        Assert.Equal(SessionProcessingClass.LocalOnly, session.ProcessingClass);

        // Read twice: an implementation that computes identity per call could return two answers,
        // and the dispatch fence binds a receipt to a single one.
        Assert.Equal(session.SessionId, session.SessionId);
        Assert.Equal(session.Generation, session.Generation);
    }

    [Fact]
    public async Task WriteAsync_WithTheLiveGeneration_IsAccepted()
    {
        await using var session = await CreateAsync("session-accept", generation: 3);

        var result = await session.WriteAsync(3, Bytes("echo hello\r"), Token);

        Assert.Equal(PtyWriteResult.Accepted, result);
    }

    [Fact]
    public async Task WriteAsync_WithAStaleGeneration_ReportsGenerationChangedAndWritesNothing()
    {
        await using var session = await CreateAsync("session-stale", generation: 3);

        var result = await session.WriteAsync(2, Bytes("echo nope\r"), Token);

        // The load-bearing half of the contract. A mismatch must NEVER retarget to the live
        // generation: a confirmed prompt landing in a session the user never approved is the failure
        // this fence exists to prevent.
        Assert.Equal(PtyWriteResult.GenerationChanged, result);
        Assert.Equal(3, session.Generation);
    }

    [Fact]
    public async Task WriteAsync_HonoursCancellation()
    {
        await using var session = await CreateAsync("session-cancel", generation: 1);
        using var cancelled = new CancellationTokenSource();
        await cancelled.CancelAsync();

        await Assert.ThrowsAnyAsync<OperationCanceledException>(
            () => session.WriteAsync(1, Bytes("echo cancelled\r"), cancelled.Token));
    }

    /// <summary>
    /// The channel itself: bytes the session produces are readable through <c>Output</c>.
    /// </summary>
    /// <remarks>
    /// Split from the child-output case below because these are two claims, not one. This proves the
    /// pipe, the read loop and the bounded channel — the parts this codebase owns. Conflating them
    /// meant a failure in either was reported as a failure in both, which is how a plumbing bug and
    /// an attachment bug become indistinguishable.
    /// </remarks>
    [Fact]
    public async Task Output_IsReadable_AndDeliversBytesTheSessionProduces()
    {
        await using var session = await CreateAsync("session-output", generation: 1);

        await session.WriteAsync(1, Bytes("echo conformance-marker\r"), Token);

        var total = await ReadAtLeastOneChunkAsync(session, TimeSpan.FromSeconds(20));

        Assert.True(total > 0, "no bytes at all arrived on the Output channel");
    }

    /// <summary>
    /// The child process's own stdout reaches us — i.e. it is really attached to this session.
    /// </summary>
    /// <remarks>
    /// The fixture satisfies this by echoing; the real runtime satisfies it only if the pseudo
    /// console actually captured the child. Kept separate from the channel test above precisely so
    /// that "our plumbing works" and "the child is attached" cannot be mistaken for one another.
    /// </remarks>
    [Fact]
    public virtual async Task Output_DeliversTheChildProcessesOwnOutput()
    {
        await using var session = await CreateAsync("session-child-output", generation: 1);

        await session.WriteAsync(1, Bytes("echo conformance-marker\r"), Token);

        var seen = await ReadUntilAsync(session, "conformance-marker", TimeSpan.FromSeconds(20));

        Assert.Contains("conformance-marker", seen, StringComparison.Ordinal);
    }

    [Fact]
    public async Task Activity_StartsAtStartingOrReady_AndReachesEndedAfterExit()
    {
        await using var session = await CreateAsync("session-activity", generation: 1);

        Assert.True(
            session.Activity is SessionActivity.Starting or SessionActivity.Ready or SessionActivity.Busy,
            $"a live session reported {session.Activity}");

        await RequestExitAsync(session);
        await session.WaitForExitAsync(Token);

        Assert.Equal(SessionActivity.Ended, session.Activity);
    }

    [Fact]
    public async Task WaitForExitAsync_CompletesAfterExit_AndReturnsTheSameResultToEveryCaller()
    {
        await using var session = await CreateAsync("session-exit", generation: 1);
        await RequestExitAsync(session);

        var first = await session.WaitForExitAsync(Token);
        var second = await session.WaitForExitAsync(Token);

        // Two callers observing different exits would let two parts of the shell disagree about
        // whether a session ended, which is worse than neither knowing.
        Assert.Equal(first.ExitCode, second.ExitCode);
        Assert.Equal(first.Killed, second.Killed);
        Assert.Equal(first.At, second.At);
    }

    [Fact]
    public async Task WriteAsync_AfterExit_Fails_RatherThanSilentlySucceeding()
    {
        await using var session = await CreateAsync("session-write-after-exit", generation: 1);
        await RequestExitAsync(session);
        await session.WaitForExitAsync(Token);

        var result = await session.WriteAsync(1, Bytes("echo gone\r"), Token);

        // Accepting bytes into a dead process would produce a truthful-looking receipt for a delivery
        // that cannot have happened — precisely the class DC-004 exists for.
        Assert.NotEqual(PtyWriteResult.Accepted, result);
    }

    [Fact]
    public async Task Output_CompletesAfterExit_SoAReaderIsNotLeftHanging()
    {
        await using var session = await CreateAsync("session-output-complete", generation: 1);
        await RequestExitAsync(session);
        await session.WaitForExitAsync(Token);

        using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(20));
        try
        {
            while (await session.Output.WaitToReadAsync(timeout.Token))
            {
                while (session.Output.TryRead(out _))
                {
                }
            }
        }
        catch (OperationCanceledException)
        {
            Assert.Fail("the output channel never completed after the session ended");
        }
    }

    [Fact]
    public async Task ResizeAsync_IsAcceptedAndDoesNotChangeTheGeneration()
    {
        await using var session = await CreateAsync("session-resize", generation: 5);

        await session.ResizeAsync(120, 40, Token);

        // A resize that bumped the generation would invalidate every in-flight dispatch receipt for
        // a window being dragged wider, which no user would connect to the failure they see.
        Assert.Equal(5, session.Generation);
    }

    [Fact]
    public async Task DisposeAsync_IsIdempotent()
    {
        var session = await CreateAsync("session-dispose", generation: 1);

        await session.DisposeAsync();
        await session.DisposeAsync();
    }

    private static ReadOnlyMemory<byte> Bytes(string text) => Encoding.UTF8.GetBytes(text);

    /// <summary>Total bytes seen on the channel until it goes quiet or time runs out.</summary>
    private static async Task<int> ReadAtLeastOneChunkAsync(ITerminalSession session, TimeSpan limit)
    {
        var total = 0;
        using var timeout = new CancellationTokenSource(limit);
        try
        {
            while (await session.Output.WaitToReadAsync(timeout.Token))
            {
                while (session.Output.TryRead(out var chunk))
                {
                    total += chunk.Bytes.Length;
                    if (total > 0)
                    {
                        return total;
                    }
                }
            }
        }
        catch (OperationCanceledException)
        {
        }

        return total;
    }

    /// <summary>Drains output until the marker appears or time runs out, returning what was seen.</summary>
    private static async Task<string> ReadUntilAsync(
        ITerminalSession session, string marker, TimeSpan limit)
    {
        var builder = new StringBuilder();
        using var timeout = new CancellationTokenSource(limit);

        try
        {
            while (await session.Output.WaitToReadAsync(timeout.Token))
            {
                while (session.Output.TryRead(out var chunk))
                {
                    builder.Append(Encoding.UTF8.GetString(chunk.Bytes.Span));
                    if (builder.ToString().Contains(marker, StringComparison.Ordinal))
                    {
                        return builder.ToString();
                    }
                }
            }
        }
        catch (OperationCanceledException)
        {
        }

        return builder.ToString();
    }
}

/// <summary>D7 against the Phase-1 fixture — the double every dispatch test still runs on.</summary>
[Trait("Platform", "Windows")]
public sealed class FixtureTerminalSessionConformanceTests : TerminalSessionConformanceTests
{
    protected override Task<ITerminalSession> CreateAsync(string sessionId, long generation) =>
        Task.FromResult<ITerminalSession>(new FixtureTerminalSession(sessionId, generation));

    protected override Task RequestExitAsync(ITerminalSession session)
    {
        ((FixtureTerminalSession)session).EndProcess(exitCode: 0);
        return Task.CompletedTask;
    }
}

/// <summary>D7 against the real ConPTY runtime, over a live <c>cmd.exe</c>.</summary>
/// <remarks>
/// No platform guard. ConPTY is a Windows API, the product is Windows-only by spec, the shell is
/// <c>net10.0-windows</c> and CI runs <c>windows-latest</c> — so a conditional skip would be
/// machinery guarding a case that cannot arise, and a skip is exactly how a conformance suite
/// quietly stops running (DC-012).
/// </remarks>
[SupportedOSPlatform("windows")]
[Trait("Platform", "Windows")]
public sealed class ConPtyTerminalSessionConformanceTests : TerminalSessionConformanceTests
{
    protected override async Task<ITerminalSession> CreateAsync(string sessionId, long generation)
    {
        var session = await ConPtyTerminalSession.StartAsync(
            new TerminalSessionRequest(
                SessionId: sessionId,
                Generation: generation,
                CommandLine: "cmd.exe",
                WorkingDirectory: Path.GetTempPath(),
                Columns: 80,
                Rows: 25,
                ProcessingClass: SessionProcessingClass.LocalOnly),
            Token);

        return session;
    }

    /// <summary>
    /// Ends the session, preferring the polite path and falling back to the kill path.
    /// </summary>
    /// <remarks>
    /// <para>Writing <c>exit</c> only works if the child is reading the pseudo console's input — and
    /// on a console-less host it is not attached at all (DC-014), so it never sees the bytes and
    /// never leaves. Waiting on that produced four cases that hung to their 60-second deadline and,
    /// before this, <b>passed by luck</b> when the child happened to die for unrelated reasons. A
    /// test that green-lights on timing is worse than one that fails.</para>
    ///
    /// <para>So this asks politely, then kills. The cases built on it — exit completes, every caller
    /// sees the same result, activity reaches Ended, writes fail afterwards, the channel completes —
    /// are all true of a killed process, so nothing is weakened by ending it that way. The
    /// <i>natural</i> exit path is covered where it can actually work: the out-of-process helper,
    /// whose child exits on its own.</para>
    /// </remarks>
    protected override async Task RequestExitAsync(ITerminalSession session)
    {
        await session.WriteAsync(session.Generation, Encoding.UTF8.GetBytes("exit\r"), Token);

        var exited = await Task.WhenAny(
            session.WaitForExitAsync(Token), Task.Delay(TimeSpan.FromSeconds(2), Token));

        if (exited is not Task<SessionExit>)
        {
            // DisposeAsync closes the pseudo console, terminates the child if it is still running,
            // and completes the exit. It is idempotent, so the test's own `await using` is unharmed.
            await session.DisposeAsync();
        }
    }

    /// <summary>
    /// Runs the child-output round trip OUT OF PROCESS, in a host that owns a real console.
    /// </summary>
    /// <remarks>
    /// <para><b>Measured 2026-08-26.</b> ConPTY attaches a child to the pseudo console only when the
    /// launching process owns a <b>real console</b>. Identical code captures the child's stdout under
    /// <c>dotnet run</c> from a terminal — 90 bytes, marker present, in both handle-closing orders —
    /// and captures nothing under a console-less host. A <c>dotnet test</c> host is always
    /// console-less because its stdio is redirected, so this case cannot pass in-process however
    /// correct the runtime is.</para>
    ///
    /// <para>The alternative was to downgrade the claim to a comment. That would leave the runtime's
    /// central promise — that a terminal's output reaches the application — asserted nowhere, which
    /// is exactly the shape of DC-002: a Verified label resting on evidence nobody can re-run.</para>
    /// </remarks>
    public override async Task Output_DeliversTheChildProcessesOwnOutput()
    {
        var helper = TerminalHostLauncher.LocateHelper();
        var report = Path.Combine(Path.GetTempPath(), $"aide-conpty-host-{Guid.NewGuid():N}.log");

        try
        {
            var exitCode = await TerminalHostLauncher.RunInNewConsoleAsync(helper, report, TimeSpan.FromSeconds(45));
            var detail = File.Exists(report) ? File.ReadAllText(report) : "(no report written)";

            Assert.True(exitCode != 3, $"the session could not start.\n{detail}");
            Assert.True(
                exitCode == 0,
                $"the child's output never reached the Output channel (exit {exitCode}).\n{detail}");
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
