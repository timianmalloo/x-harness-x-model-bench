using System.Diagnostics;
using System.Runtime.Versioning;
using System.Threading.Channels;
using AiDe.Core.Dispatch;
using AiDe.Core.Facts;
using Microsoft.Win32.SafeHandles;

namespace AiDe.Core.Terminal;

/// <summary>What a caller must supply to start a real terminal session.</summary>
public sealed record TerminalSessionRequest(
    string SessionId,
    long Generation,
    string CommandLine,
    string? WorkingDirectory,
    int Columns,
    int Rows,
    SessionProcessingClass ProcessingClass,
    ShellIntegrationMode Integration = ShellIntegrationMode.None,
    string ShellPath = "powershell.exe",
    IReadOnlyDictionary<string, string>? Environment = null);

/// <summary>Whether the runtime installs its OSC shell integration into the session's shell.</summary>
/// <remarks>
/// Opt-in per session rather than always-on: <see cref="CommandLine"/> may be any executable, and
/// decorating an arbitrary command with PowerShell arguments would corrupt it.
/// </remarks>
public enum ShellIntegrationMode
{
    /// <summary>Launch the command line as given. The session uses the output heuristic.</summary>
    None,

    /// <summary>
    /// Run the command line as an AGENT hosted inside the user's login shell.
    /// </summary>
    /// <remarks>
    /// <para>Launching an agent directly was the defect behind "the agent sessions do not have my
    /// profile or my environment variables". The measurement found something sharper than a missing
    /// profile: an agent whose launcher is a <c>.cmd</c> shim — every npm-installed CLI — runs under
    /// <c>cmd.exe</c>, and cmd drops any environment variable past its limit. A 22,297-character
    /// PATH becomes an EMPTY PATH, and the agent cannot find node, git, or itself.</para>
    ///
    /// <para>Hosting it in the login shell gives it the profile, PATHEXT resolution for shims, and a
    /// shell that handles a long PATH — which together are what "works with my profile" means.</para>
    /// </remarks>
    PowerShellHostedAgent,

    /// <summary>
    /// Treat the command line as a PowerShell executable and launch it with this session's
    /// integration installed.
    /// </summary>
    PowerShell,
}

/// <summary>
/// The real terminal runtime: one ConPTY, one process, one owner loop (ADR-0005).
/// </summary>
/// <remarks>
/// <para><b>Input and output loops are separate</b>, which is a correctness requirement rather than
/// tidiness. ConPTY's pipes are finite: a process producing output faster than we read it blocks on
/// its own write, and if the same loop were responsible for both reading and writing, a large write
/// would deadlock against a full output pipe with neither side able to proceed.</para>
///
/// <para><b>Output is bounded and drops the oldest.</b> The architecture budgets 1 MiB/s of sustained
/// output; a reader that falls behind must not be able to grow the queue without limit. Dropping is
/// therefore a designed state — reported through <see cref="TerminalChunk.Truncated"/> and
/// <see cref="SessionActivity.OutputOverload"/> — because for a terminal, the *newest* output is the
/// interesting output and stalling the process to preserve scrollback would be the wrong trade.</para>
///
/// <para><b>Terminal bytes never leave this object except through <see cref="Output"/>.</b> They are
/// not logged, traced, or attached to telemetry, per the spec's privacy rule. The telemetry below
/// counts bytes; it never carries them.</para>
/// </remarks>
[SupportedOSPlatform("windows")]
public sealed class ConPtyTerminalSession : ITerminalSession
{
    /// <summary>Chunks buffered before the oldest is dropped.</summary>
    /// <remarks>
    /// simplify: a fixed chunk count rather than a byte budget; ceiling is roughly 512 x read-buffer
    /// (~2 MiB); upgrade trigger = P2-PERF shows a renderer starving or a memory ceiling breached
    /// under the 1 MiB/s case.
    /// </remarks>
    private const int OutputCapacity = 512;

    private const int ReadBufferSize = 4096;

    private static readonly ActivitySource Telemetry = new("aide.terminal.runtime");

    private readonly Channel<TerminalChunk> _output;
    private readonly TaskCompletionSource<SessionExit> _exit =
        new(TaskCreationOptions.RunContinuationsAsynchronously);

    private readonly SemaphoreSlim _writeGate = new(1, 1);
    private readonly CancellationTokenSource _shutdown = new();
    private readonly System.Threading.Lock _stateGate = new();

    private readonly SafeFileHandle _inputWrite;
    private readonly SafeFileHandle _outputRead;
    private readonly FileStream _toProcess;
    private readonly FileStream _fromProcess;

    private IntPtr _console;
    private IntPtr _process;
    private IntPtr _thread;
    private IntPtr _job;

    private readonly TerminalActivityState _state = new();
    private readonly OscParser _osc;
    private readonly List<OscEvent> _oscEvents = [];
    private readonly long _startedAt = Stopwatch.GetTimestamp();

    private bool _truncatedSinceLastChunk;
    private bool _disposed;

    private ConPtyTerminalSession(
        TerminalSessionRequest request,
        string nonce,
        IntPtr console,
        IntPtr job,
        ConPtyInterop.ProcessInformation process,
        SafeFileHandle inputWrite,
        SafeFileHandle outputRead)
    {
        SessionId = request.SessionId;
        Generation = request.Generation;
        ProcessingClass = request.ProcessingClass;

        // Generated here rather than accepted from the caller: a nonce a caller can choose is one a
        // caller can reuse across sessions, and a value shared between two sessions authenticates
        // claims made by the wrong child.
        ShellIntegrationNonce = nonce;
        HasReadinessEvidence = false;
        _osc = new OscParser(nonce);

        _console = console;
        _job = job;
        _process = process.hProcess;
        _thread = process.hThread;
        _inputWrite = inputWrite;
        _outputRead = outputRead;

        _toProcess = new FileStream(inputWrite, FileAccess.Write, bufferSize: 1, isAsync: false);
        _fromProcess = new FileStream(outputRead, FileAccess.Read, bufferSize: ReadBufferSize, isAsync: false);

        _output = Channel.CreateBounded<TerminalChunk>(new BoundedChannelOptions(OutputCapacity)
        {
            FullMode = BoundedChannelFullMode.DropOldest,
            SingleWriter = true,
        });
    }

    public string SessionId { get; }

    public long Generation { get; private set; }

    public SessionProcessingClass ProcessingClass { get; }

    /// <summary>
    /// The secret this session's injected shell integration must echo back in its OSC 133 sequences
    /// for them to be believed.
    /// </summary>
    /// <remarks>
    /// Public because the integration script has to be given it; per-session and in-memory because a
    /// nonce that outlived the session would authenticate a later child's claims. It is not a
    /// credential for anything else — the worst a leak buys is the ability to lie about activity.
    /// </remarks>
    public string ShellIntegrationNonce { get; }

    /// <summary>
    /// Whether anything AUTHENTICATES this session's claim about its own state.
    /// </summary>
    /// <remarks>
    /// True only with shell integration: OSC 133 signed with the session nonce is what makes
    /// <see cref="SessionActivity.Ready"/> a claim rather than an inference. Without it, activity is
    /// derived from output timing — and a quiet agent mid-thought looks exactly like an idle one,
    /// which is how a prompt ends up in a confirmation dialog.
    /// </remarks>
    public bool HasReadinessEvidence { get; private set; }

    public ChannelReader<TerminalChunk> Output => _output.Reader;

    public SessionActivity Activity
    {
        get
        {
            lock (_stateGate)
            {
                return _state.Current;
            }
        }
    }

    /// <summary>Creates the pseudo console, starts the process inside a kill-on-close job, and pumps.</summary>
    public static Task<ConPtyTerminalSession> StartAsync(
        TerminalSessionRequest request, CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        ArgumentException.ThrowIfNullOrWhiteSpace(request.CommandLine);
        ArgumentOutOfRangeException.ThrowIfLessThan(request.Columns, 1);
        ArgumentOutOfRangeException.ThrowIfLessThan(request.Rows, 1);

        // Generated here rather than in the constructor because the integration script has to
        // carry it and the script is part of the command line — the nonce must therefore exist
        // before the process does.
        var nonce = OscParser.NewNonce();

        var commandLine = request.Integration switch
        {
            ShellIntegrationMode.PowerShell => ShellIntegration.PowerShellCommandLine(request.CommandLine, nonce),
            ShellIntegrationMode.PowerShellHostedAgent =>
                ShellIntegration.AgentCommandLine(request.ShellPath, request.CommandLine, nonce),
            _ => request.CommandLine,
        };

        using var span = Telemetry.StartActivity("terminal.start");
        span?.SetTag("session.id", request.SessionId);
        span?.SetTag("session.generation", request.Generation);
        span?.SetTag("session.processing_class", request.ProcessingClass.ToString());

        // Two pipes, four handles. The pseudo console takes the ends it reads from and writes to;
        // we keep the other two. The console's own ends are closed immediately after creation —
        // holding them would keep the output pipe alive after the process ends and the read loop
        // would never see EOF, so the session would never report an exit.
        if (!ConPtyInterop.CreatePipe(out var inputRead, out var inputWrite, IntPtr.Zero, 0))
        {
            throw new IOException("could not create the ConPTY input pipe");
        }

        if (!ConPtyInterop.CreatePipe(out var outputRead, out var outputWrite, IntPtr.Zero, 0))
        {
            inputRead.Dispose();
            inputWrite.Dispose();
            throw new IOException("could not create the ConPTY output pipe");
        }

        var size = new ConPtyInterop.Coord { X = (short)request.Columns, Y = (short)request.Rows };
        ConPtyInterop.ThrowIfFailed(
            ConPtyInterop.CreatePseudoConsole(size, inputRead, outputWrite, 0, out var console),
            "CreatePseudoConsole");

        inputRead.Dispose();
        outputWrite.Dispose();

        var job = ConPtyInterop.CreateKillOnCloseJob();

        ConPtyInterop.ProcessInformation process = default;
        var started = false;
        try
        {
            process = ConPtyInterop.StartAttachedProcess(
                console, commandLine, request.WorkingDirectory, request.Environment);
            started = true;

            // THE ASSIGN IS CHECKED, and the window before it is ACCEPTED AND UNMEASURED.
            //
            // The child is created running and joins the job a moment later; anything it spawns
            // inside that window is outside the job permanently. Nobody has measured that window.
            // This comment used to call it "real but small" — "small" was a belief written in the
            // voice of a result, and there is no number behind it.
            //
            // It also declined CREATE_SUSPENDED-then-assign-then-resume for the wrong reason:
            // "the process never starts if the assign throws" is not a failure mode, it is the
            // refusal `docs/ai-forward-pack/scripts/bounded_process.py:224-226` already ships as
            // CORRECT — "the gated wrapper cannot launch the requested command until Job Object
            // containment succeeds, closing the child-start-before-assignment race".
            //
            // Neither is the end state. `PROC_THREAD_ATTRIBUTE_JOB_LIST` assigns the job AT
            // CREATION — "a pointer to a list of job handles to be assigned to the child process",
            // Windows 10 and Server 2016 and newer (Microsoft Learn, UpdateProcThreadAttribute) —
            // which removes the window and the resume together, and StartAttachedProcess already
            // builds the proc-thread attribute list it would extend. Recorded as a next step.
            ConPtyInterop.AssignProcessToJob(job, process.hProcess);
        }
        catch
        {
            if (started)
            {
                // Started, and NOT contained. Ending it here is the same choice bounded_process.py
                // makes: a caller that asked for a contained shell gets an exception, never an
                // uncontained one it has no way to notice.
                ConPtyInterop.TerminateProcess(process.hProcess, 1);
                ConPtyInterop.CloseHandle(process.hThread);
                ConPtyInterop.CloseHandle(process.hProcess);
            }

            ConPtyInterop.ClosePseudoConsole(console);
            ConPtyInterop.CloseHandle(job);
            inputWrite.Dispose();
            outputRead.Dispose();

            // The start above was counted before anything could throw (the ledger counts the
            // attempt). A start with no stop reads as a held host, so the failed construction
            // closes its own pair here — otherwise `starts − stops` drifts by one per failure and
            // the invariant the census reads is wrong in the direction that hides a leak.
            EmitStop(request.SessionId, request.Generation, exitCode: null, killed: false, reason: "start-failed", durationMs: null);
            throw;
        }

        var session = new ConPtyTerminalSession(
            request, nonce, console, job, process, inputWrite, outputRead);

        // Set from the REQUEST, not from later observation: a session either launched with shell
        // integration or it did not, and inferring it afterwards from whether an OSC ever arrived
        // would make "no integration" and "integration that has not spoken yet" the same state.
        // The HOSTED AGENT mode installs the integration but must NOT claim readiness evidence from
        // it. The nonce reports when the SHELL is at its prompt, and for a hosted agent that means
        // the agent has EXITED — the precise opposite of ready. Agent readiness stays with the
        // marker watcher, which is weaker evidence and named as such (ADR-0007).
        session.HasReadinessEvidence = request.Integration == ShellIntegrationMode.PowerShell;
        session.StartPumping();
        return Task.FromResult(session);
    }

    public async Task<PtyWriteResult> WriteAsync(
        long expectedGeneration, ReadOnlyMemory<byte> bytes, CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();

        // A write to a disposed session is a FAILED delivery, not an exception. Letting
        // ObjectDisposedException escape would hand the caller a crash where the contract promises a
        // result — and the write-ahead dispatch above it turns an unexpected throw into a Pending
        // attempt that the recovery sweep must later resolve as DeliveryUnknown. That is a truthful
        // "we cannot know" standing in for a knowable "it definitely did not land".
        lock (_stateGate)
        {
            if (_disposed)
            {
                return PtyWriteResult.Failed;
            }
        }

        // The gate is what makes "compare the generation and write" one indivisible step. Checking
        // outside it would leave a window in which the process is replaced between the check and the
        // write, and a confirmed prompt would land in a session the user never approved.
        try
        {
            await _writeGate.WaitAsync(cancellationToken).ConfigureAwait(false);
        }
        catch (ObjectDisposedException)
        {
            // Disposed between the check above and this wait. Same answer, for the same reason.
            return PtyWriteResult.Failed;
        }

        try
        {
            if (Activity == SessionActivity.Ended)
            {
                return PtyWriteResult.Failed;
            }

            if (expectedGeneration != Generation)
            {
                return PtyWriteResult.GenerationChanged;
            }

            await _toProcess.WriteAsync(bytes, cancellationToken).ConfigureAwait(false);
            await _toProcess.FlushAsync(cancellationToken).ConfigureAwait(false);

            // Byte COUNT only. The bytes themselves are a prompt and never reach telemetry.
            using var span = Telemetry.StartActivity("terminal.write");
            span?.SetTag("session.id", SessionId);
            span?.SetTag("write.bytes", bytes.Length);
            return PtyWriteResult.Accepted;
        }
        catch (OperationCanceledException)
        {
            throw;
        }
        catch (IOException)
        {
            // The pipe is gone: the process died between the generation check and the write. That is
            // a failed delivery, not an unknown one — nothing was accepted.
            return PtyWriteResult.Failed;
        }
        catch (ObjectDisposedException)
        {
            return PtyWriteResult.Failed;
        }
        finally
        {
            try
            {
                _writeGate.Release();
            }
            catch (ObjectDisposedException)
            {
                // Disposed while this write was in flight. Nothing to release, and throwing from a
                // finally would replace whatever result the write actually produced.
            }
        }
    }

    public Task<SessionExit> WaitForExitAsync(CancellationToken cancellationToken) =>
        _exit.Task.WaitAsync(cancellationToken);

    public ValueTask ResizeAsync(int columns, int rows, CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        ArgumentOutOfRangeException.ThrowIfLessThan(columns, 1);
        ArgumentOutOfRangeException.ThrowIfLessThan(rows, 1);

        lock (_stateGate)
        {
            if (_state.Current == SessionActivity.Ended || _console == IntPtr.Zero)
            {
                return ValueTask.CompletedTask;
            }

            // Deliberately does NOT touch Generation: a resize is the same process at a different
            // size, and bumping it would invalidate every in-flight receipt for a window drag.
            ConPtyInterop.ResizePseudoConsole(
                _console, new ConPtyInterop.Coord { X = (short)columns, Y = (short)rows });
        }

        return ValueTask.CompletedTask;
    }

    private void StartPumping()
    {
        // A dedicated long-running thread rather than a pooled task: this loop blocks on a synchronous
        // pipe read for the life of the session, and parking a thread-pool thread there starves the
        // pool for exactly as long as the terminal is open.
        var reader = new Thread(ReadLoop)
        {
            IsBackground = true,
            Name = $"conpty-read-{SessionId}",
        };
        reader.Start();

        _ = Task.Run(WatchForExitAsync);
    }

    private void ReadLoop()
    {
        var buffer = new byte[ReadBufferSize];

        try
        {
            // TO EOF, UNCONDITIONALLY — not until the session ends. `ClosePseudoConsole` waits for
            // the host to exit, and the host cannot exit while its output pipe is full; a loop that
            // stopped reading when the session completed would leave the closer (the exit watcher's
            // pool thread, or the UI thread on dispose) waiting on a pipe nobody drains, with the
            // host alive after `terminal.stop` said otherwise. So the loop reads until the host is
            // gone (EOF), the pipe breaks, or the stream is disposed under it; chunks that arrive
            // after the channel completed are read and dropped.
            while (true)
            {
                var read = _fromProcess.Read(buffer, 0, buffer.Length);
                if (read <= 0)
                {
                    break; // EOF: the console's write end is closed, so the host is gone.
                }

                // Read for state BEFORE the chunk is published. The output channel drops the oldest
                // entry under load, so a parser fed from the reader's side would lose exactly the
                // sequences emitted during a flood — the moment activity state matters most.
                _oscEvents.Clear();
                var claimed = _osc.Consume(buffer.AsSpan(0, read), _oscEvents);

                lock (_stateGate)
                {
                    if (claimed is not null)
                    {
                        _state.OnOscClaim(claimed.Value);
                    }
                    else
                    {
                        _state.OnOutput();
                    }
                }

                RecordOscEvents();

                var chunk = new TerminalChunk(buffer.AsSpan(0, read).ToArray(), _truncatedSinceLastChunk);
                _truncatedSinceLastChunk = false;

                if (!_output.Writer.TryWrite(chunk))
                {
                    // DropOldest means TryWrite effectively always succeeds; a refusal here means the
                    // channel completed under us. Keep draining (see above) — just stop publishing.
                    continue;
                }

                // The reader is behind if the channel is at capacity, so the NEXT chunk carries the
                // truncation marker — that is where a renderer draws its gap.
                if (_output.Reader.Count >= OutputCapacity)
                {
                    _truncatedSinceLastChunk = true;
                    lock (_stateGate)
                    {
                        _state.OnOverload();
                    }
                }
            }
        }
        catch (IOException)
        {
            // The pipe broke: the same condition as EOF, reported differently.
        }
        catch (ObjectDisposedException)
        {
        }
        finally
        {
            _output.Writer.TryComplete();
        }
    }

    /// <summary>
    /// Emits a span for any OSC sequence that was refused, so a rejected control is visible rather
    /// than silent.
    /// </summary>
    /// <remarks>
    /// <para>Honoured sequences are deliberately not recorded: they are the normal case and would be
    /// pure volume. A <i>refusal</i> is the interesting event — a burst of
    /// <see cref="OscDisposition.RefusedUnauthenticated"/> means something in the session is emitting
    /// state claims it cannot authenticate, which is either broken integration or a child trying it
    /// on, and both are worth being able to see.</para>
    ///
    /// <para><b>Kind and disposition only.</b> Both are values from our own closed enums, so no byte
    /// the child chose can reach telemetry through here — which is the rule for the whole terminal
    /// path, restated at the one place that writes to a span from inside the read loop.</para>
    /// </remarks>
    private void RecordOscEvents()
    {
        foreach (var osc in _oscEvents)
        {
            if (osc.Disposition is OscDisposition.Honoured or OscDisposition.Ignored)
            {
                continue;
            }

            using var span = Telemetry.StartActivity("terminal.osc.refused");
            span?.SetTag("session.id", SessionId);
            span?.SetTag("osc.kind", osc.Kind.ToString());
            span?.SetTag("osc.disposition", osc.Disposition.ToString());
        }
    }

    private async Task WatchForExitAsync()
    {
        try
        {
            // Poll rather than wait on the handle: a WaitHandle wrapper over a process handle we own
            // raw would need its own SafeHandle lifetime, and the resolution that matters here is
            // "before a human notices", not milliseconds. The token is taken ONCE: reading
            // `_shutdown.Token` after DisposeAsync disposed the source throws ObjectDisposedException,
            // which the catch below does not cover.
            var token = _shutdown.Token;
            while (!token.IsCancellationRequested)
            {
                if (ConPtyInterop.GetExitCodeProcess(_process, out var code)
                    && code != ConPtyInterop.STILL_ACTIVE)
                {
                    Complete(new SessionExit(code, Killed: false, DateTimeOffset.UtcNow));

                    // RELEASED WITH THE CHILD, NOT WITH THE OWNER (DC-156). The pseudo console
                    // and the job were acquired for this process; its exit made both dead weight,
                    // and until INV-0010 nothing revisited them — one client-less
                    // `conhost.exe --headless` per ended pane for the App's lifetime, measured
                    // 1 -> 1 three seconds after `cmd.exe /c exit 0` with the owner alive. Closing
                    // the console ends the host and gives the read loop its EOF; closing the job's
                    // last handle ends anything the shell left behind in it. The process and
                    // thread handles stay for DisposeAsync, which still reads the exit code.
                    ReleaseHost();
                    return;
                }

                await Task.Delay(50, token).ConfigureAwait(false);
            }
        }
        catch (OperationCanceledException)
        {
        }
    }

    private void Complete(SessionExit exit)
    {
        lock (_stateGate)
        {
            if (_state.Current == SessionActivity.Ended)
            {
                return;
            }

            _state.OnEnded();
        }

        // The other half of `terminal.start`, on the same source, ONCE per session: both end paths
        // funnel through this guarded transition, so a child exit followed by the tab's dispose is
        // one stop, and `starts - stops` (TerminalHostingLedger) is the number of hosts still held.
        // Emitted before the channel completes — the attempt, not the success, the idiom the
        // ledger records (INV-0010).
        EmitStop(
            SessionId, Generation, exit.ExitCode, exit.Killed,
            reason: exit.Killed ? "killed" : "child-exited",
            durationMs: Stopwatch.GetElapsedTime(_startedAt).TotalMilliseconds);

        // Complete the channel first so a reader woken by the exit and then draining finds a
        // completed channel rather than blocking forever on one more read.
        _output.Writer.TryComplete();
        _exit.TrySetResult(exit);
    }

    /// <summary>
    /// Opens the <c>terminal.stop</c> activity. Tags are the session's identity and how it ended;
    /// an exit code the runtime does not know is absent, never 0 (a killed session has none).
    /// </summary>
    private static void EmitStop(
        string sessionId, long generation, int? exitCode, bool killed, string reason, double? durationMs)
    {
        using var span = Telemetry.StartActivity("terminal.stop");
        span?.SetTag("session.id", sessionId);
        span?.SetTag("session.generation", generation);
        span?.SetTag("session.killed", killed);
        span?.SetTag("session.exit_code", exitCode);
        span?.SetTag("session.end_reason", reason);
        span?.SetTag("session.duration_ms", durationMs);
    }

    /// <summary>
    /// Closes the pseudo console and the job, whichever of the two this session still holds.
    /// Idempotent, and safe against the other end path: each handle is taken under the state gate
    /// exactly once, so the exit watcher and <see cref="DisposeAsync"/> cannot both close it.
    /// </summary>
    private void ReleaseHost()
    {
        var console = Take(ref _console);
        if (console != IntPtr.Zero)
        {
            ConPtyInterop.ClosePseudoConsole(console);
        }

        var job = Take(ref _job);
        if (job != IntPtr.Zero)
        {
            ConPtyInterop.CloseHandle(job);
        }
    }

    /// <summary>Takes a handle out of its field under the state gate, leaving zero behind.</summary>
    private IntPtr Take(ref IntPtr handle)
    {
        lock (_stateGate)
        {
            var taken = handle;
            handle = IntPtr.Zero;
            return taken;
        }
    }

    public async ValueTask DisposeAsync()
    {
        lock (_stateGate)
        {
            if (_disposed)
            {
                return;
            }

            _disposed = true;
        }

        await _shutdown.CancelAsync().ConfigureAwait(false);

        // Closing the console's handle is what tells the attached process its terminal is gone, so
        // it is the polite way out and must come before the kill. Taken under the gate: a session
        // whose child already exited released it in WatchForExitAsync, and this finds zero.
        var console = Take(ref _console);
        if (console != IntPtr.Zero)
        {
            ConPtyInterop.ClosePseudoConsole(console);
        }

        if (_process != IntPtr.Zero)
        {
            if (ConPtyInterop.GetExitCodeProcess(_process, out var code)
                && code == ConPtyInterop.STILL_ACTIVE)
            {
                ConPtyInterop.TerminateProcess(_process, 1);
            }
        }

        Complete(new SessionExit(ExitCode: null, Killed: true, DateTimeOffset.UtcNow));

        try
        {
            _toProcess.Dispose();
            _fromProcess.Dispose();
        }
        catch (IOException)
        {
        }

        _inputWrite.Dispose();
        _outputRead.Dispose();

        if (_thread != IntPtr.Zero)
        {
            ConPtyInterop.CloseHandle(_thread);
            _thread = IntPtr.Zero;
        }

        if (_process != IntPtr.Zero)
        {
            ConPtyInterop.CloseHandle(_process);
            _process = IntPtr.Zero;
        }

        // Last: closing the job's final handle is what kills anything the shell left behind, so it
        // must outlive every other cleanup step. Zero here when the child's exit already closed it.
        var job = Take(ref _job);
        if (job != IntPtr.Zero)
        {
            ConPtyInterop.CloseHandle(job);
        }

        _shutdown.Dispose();
        _writeGate.Dispose();
    }
}
