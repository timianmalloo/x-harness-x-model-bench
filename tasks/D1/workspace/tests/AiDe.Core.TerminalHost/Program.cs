using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Runtime.Versioning;
using System.Text;
using AiDe.Core.Dispatch;
using AiDe.Core;
using AiDe.Core.Facts;
using AiDe.Core.Terminal;

namespace AiDe.Core.TerminalHost;

/// <summary>
/// Drives a real <see cref="ConPtyTerminalSession"/> end to end and reports the verdict by exit code.
/// </summary>
/// <remarks>
/// <para><b>Why this exists.</b> ConPTY only attaches a child to the pseudo console when the host
/// process owns a <b>real console</b>. A <c>dotnet test</c> host never does — its stdio is
/// redirected — so the round trip cannot be verified in-process no matter how correct the runtime
/// is. Measured 2026-08-26: identical code captures the child's stdout under <c>dotnet run</c> from
/// a terminal (90 bytes, marker present) and captures nothing under a console-less host.</para>
///
/// <para>The conformance suite launches this executable in a headless console (<c>CREATE_NO_WINDOW</c>
/// — a new console would be a Windows Terminal tab with an agent attached, DC-170) and asserts on
/// the exit code. That keeps the claim testable rather than downgrading it to a comment, which is
/// what a "known environment limitation" note would have been.</para>
///
/// <para>Exit codes are the contract: <b>0</b> the child's output was captured, <b>2</b> it was not,
/// <b>3</b> the session could not start. (<b>4</b>, "no console window", was retired with DC-014's
/// premise: the window was never the operative condition.)</para>
/// </remarks>
[SupportedOSPlatform("windows")]
internal static class Program
{
    private const string Marker = "conpty-host-marker";

    [DllImport("kernel32.dll")]
    private static extern IntPtr GetConsoleWindow();


    private static async Task<int> Main(string[] args)
    {
        var report = args.Length > 0 ? args[0] : null;
        var mode = args.Length > 1 ? args[1] : "capture";
        var log = new StringBuilder();

        // Fail loudly rather than quietly reporting "not captured": a missing console is the
        // caller's mistake, and reporting it as a product failure would be a false negative that
        // looks exactly like a real one.
        // Recorded, not required (X-2: DC-014's premise was DC-164's mechanism; the runtime's
        // channel works with no console window at all). A headless console is what CREATE_NO_WINDOW
        // gives this process, and it is what keeps Windows Terminal — the default terminal on the
        // reporting machine — from opening a tab for every launch and attaching an agent to it.
        log.AppendLine(GetConsoleWindow() == IntPtr.Zero ? "console window: none (headless)" : "console window: present");

        if (mode == "osc")
        {
            return await OscAsync(report, log);
        }

        if (mode == "integration")
        {
            return await IntegrationAsync(report, log);
        }

        if (mode == "privacy")
        {
            return await PrivacyAsync(report, log);
        }

        if (mode is "dispose-then-hold" or "child-exit-then-hold")
        {
            // INV-0010: the two in-life paths. A closed TAB disposes its session while the App
            // lives on; a shell the user ends with `exit` completes its session while the pane
            // lives on. Whether the `conhost.exe --headless` host is released on each is the
            // question this holds still long enough to measure.
            return await InLifePathAsync(report, log, childExits: mode == "child-exit-then-hold");
        }

        if (mode == "env-scrub")
        {
            // INV-0010 slice 0: what the runtime hands a child. Windows Terminal's own variables
            // must not reach it (each one that did cost a `node higgsfield-mcp` under WT's agent
            // host, measured 4/4 → 0/4); everything else must.
            return await EnvironmentScrubAsync(report, log);
        }

        if (mode is "exit-undisposed" or "kill-self")
        {
            // INV-0010: the App's exit path, reproduced. `WorkbenchShell.Dispose` disposes no
            // TerminalSurface, so closing the window ends the process with every session
            // UNDISPOSED — the kernel closes the job handle and the pseudo console handle, and
            // whether the `conhost.exe --headless` host follows is the question this measures.
            // `kill-self` is `taskkill /F` on the owning host: TerminateProcess on ourselves, no
            // user-mode cleanup at all.
            return await ExitPathAsync(report, log, kill: mode == "kill-self");
        }

        if (mode == "dispatch")
        {
            var code = await DispatchProbe.RunAsync(log);
            Write(report, log);
            return code;
        }

        if (mode == "observe-agent")
        {
            // An instrument, not a test. It prints what the agent actually draws, so a readiness
            // marker is written against measured output instead of a memory of what a CLI prints.
            var code = await ObserveProbe.RunAsync(
                log,
                commandLine: args.Length > 2 ? args[2] : "claude",
                workingDirectory: args.Length > 3 ? args[3] : Environment.CurrentDirectory,
                settleSeconds: args.Length > 4 && int.TryParse(args[4], out var settle) ? settle : 20,
                hosted: args.Length > 5 && string.Equals(args[5], "hosted", StringComparison.OrdinalIgnoreCase));

            Write(report, log);
            return code;
        }

        if (mode == "dispatch-agent")
        {
            // ADR-0010's stated residual: the live session so far has been a SHELL. This dispatches
            // into a real agent CLI, which buffers, streams, and takes seconds to answer — none of
            // which a shell exercises.
            var code = await DispatchProbe.RunAsync(
                log,
                commandLine: args.Length > 2 ? args[2] : "claude",
                prompt: "Reply with exactly {MARKER} and nothing else.",
                settleSeconds: 25,
                expectedOccurrences: 2,
                // A TRUSTED directory. Launched in the temp folder, Claude Code opens with a
                // "is this a project you trust?" confirmation and the dispatched prompt lands in
                // that dialog rather than a conversation — measured, and the reason this parameter
                // exists at all.
                workingDirectory: args.Length > 3 ? args[3] : Environment.CurrentDirectory);

            Write(report, log);
            return code;
        }

        ConPtyTerminalSession session;
        try
        {
            session = await ConPtyTerminalSession.StartAsync(
                new TerminalSessionRequest(
                    SessionId: "host-probe",
                    Generation: 1,
                    CommandLine: "cmd.exe",
                    WorkingDirectory: Path.GetTempPath(),
                    Columns: 80,
                    Rows: 25,
                    ProcessingClass: SessionProcessingClass.LocalOnly),
                CancellationToken.None);
        }
        catch (Exception ex)
        {
            log.AppendLine($"StartAsync threw {ex.GetType().Name}: {ex.Message}");
            Write(report, log);
            return 3;
        }

        await using (session)
        {
            var written = await session.WriteAsync(
                1, Encoding.UTF8.GetBytes($"echo {Marker}\r"), CancellationToken.None);
            log.AppendLine($"write result: {written}");

            var seen = new StringBuilder();
            using var deadline = new CancellationTokenSource(TimeSpan.FromSeconds(20));

            try
            {
                while (await session.Output.WaitToReadAsync(deadline.Token))
                {
                    while (session.Output.TryRead(out var chunk))
                    {
                        seen.Append(Encoding.UTF8.GetString(chunk.Bytes.Span));
                        if (seen.ToString().Contains(Marker, StringComparison.Ordinal))
                        {
                            log.AppendLine($"captured after {seen.Length} chars");
                            Write(report, log);
                            return 0;
                        }
                    }
                }

                log.AppendLine("output channel completed without the marker");
            }
            catch (OperationCanceledException)
            {
                log.AppendLine("timed out waiting for the marker");
            }

            log.AppendLine($"activity: {session.Activity}");
            log.AppendLine($"bytes seen: {seen.Length}");
            log.AppendLine("raw: " + seen.ToString().Replace("", "<ESC>"));
            Write(report, log);
            return 2;
        }
    }


    /// <summary>
    /// Drives OSC 133 through a real pseudo console, forged first and authenticated second.
    /// </summary>
    /// <remarks>
    /// <para><b>The question this answers is not "does the parser work".</b> That is settled by unit
    /// tests. It is whether an OSC sequence written by a child process <i>survives the round trip at
    /// all</i> — ConPTY is not a pipe, it is a terminal emulator that parses the child's output and
    /// re-emits its own VT stream, and a sequence it does not recognise could reasonably be dropped
    /// on the floor. If it were, every unit test above would still pass and the feature would be
    /// inert in production. That is a claim only a real console can settle.</para>
    ///
    /// <para>Forged is tried <b>first, deliberately</b>. An unauthenticated claim arrives while the
    /// session is still using the output heuristic, which is the state a real session is in when a
    /// hostile child would try it — and running it second, after a genuine claim had made OSC
    /// authoritative, would test an easier case than the real one.</para>
    ///
    /// <para>Exit codes: <b>0</b> both correct, <b>3</b> could not start, <b>5</b> the forged claim
    /// was honoured, <b>6</b> the authenticated claim was not honoured, <b>7</b> timed out.</para>
    /// </remarks>
    private static async Task<int> OscAsync(string? report, StringBuilder log)
    {
        ConPtyTerminalSession session;
        try
        {
            session = await ConPtyTerminalSession.StartAsync(
                new TerminalSessionRequest(
                    SessionId: "osc-probe",
                    Generation: 1,
                    // PowerShell rather than cmd because it can emit a raw ESC in one legible line.
                    CommandLine: "powershell.exe -NoProfile -NoLogo",
                    WorkingDirectory: Path.GetTempPath(),
                    Columns: 80,
                    Rows: 25,
                    ProcessingClass: SessionProcessingClass.LocalOnly),
                CancellationToken.None);
        }
        catch (Exception ex)
        {
            log.AppendLine($"StartAsync threw {ex.GetType().Name}: {ex.Message}");
            Write(report, log);
            return 3;
        }

        await using (session)
        {
            var nonce = session.ShellIntegrationNonce;
            log.AppendLine($"nonce length: {nonce.Length}");

            // --- 1. forged: no nonce, sent while the heuristic is still in charge -------------
            await SendAsync(session, "[Console]::Write([char]27+']133;D;0'+[char]27+'\\'); 'FORGED-DONE'");

            if (!await WaitForAsync(session, "FORGED-DONE", log))
            {
                Write(report, log);
                return 7;
            }

            var afterForged = session.Activity;
            log.AppendLine($"activity after the forged claim: {afterForged}");

            if (afterForged == SessionActivity.Ready)
            {
                log.AppendLine("FAIL: an unauthenticated OSC 133;D was honoured");
                Write(report, log);
                return 5;
            }

            // --- 2. authenticated -------------------------------------------------------------
            await SendAsync(
                session, $"[Console]::Write([char]27+']133;D;0;nonce={nonce}'+[char]27+'\\'); 'REAL-DONE'");

            if (!await WaitForAsync(session, "REAL-DONE", log))
            {
                Write(report, log);
                return 7;
            }

            var afterReal = session.Activity;
            log.AppendLine($"activity after the authenticated claim: {afterReal}");

            if (afterReal != SessionActivity.Ready)
            {
                log.AppendLine(
                    "FAIL: an authenticated OSC 133;D did not reach the parser. Either ConPTY does "
                    + "not pass OSC through, or the read loop is not feeding it.");
                Write(report, log);
                return 6;
            }

            log.AppendLine("both cases correct");
            Write(report, log);
            return 0;
        }
    }


    /// <summary>
    /// Runs a real PowerShell under the real shell integration and checks the full state loop.
    /// </summary>
    /// <remarks>
    /// <para><b>This is the only test that can fail for the reasons that matter.</b> The script is a
    /// string until PowerShell runs it: whether PSReadLine is even loaded under
    /// <c>-NoProfile</c> inside a pseudo console, whether the <c>Enter</c> handler fires, whether
    /// overriding <c>prompt</c> works when the host has already captured one — none of that is
    /// visible to a unit test, and all of it decides whether the feature exists.</para>
    ///
    /// <para><b>Both phases are checked, and the second is the one that would rot.</b> Reaching
    /// <c>Ready</c> at a prompt proves the D/A/B path. Reaching <c>Busy</c> while a command runs
    /// proves <c>C</c> — and if only that one broke, the session would sit at <c>Ready</c> through
    /// every command while looking perfectly healthy at the prompt.</para>
    ///
    /// <para>Exit codes: <b>0</b> the whole loop, <b>3</b> could not start, <b>8</b> never became
    /// Ready at the prompt, <b>9</b> never became Busy during a command, <b>10</b> never returned to
    /// Ready afterwards.</para>
    /// </remarks>
    /// <summary>
    /// Starts the product-shaped session (PowerShell, integration installed), publishes this
    /// process's pid, holds the session long enough for the caller to see its console host, then
    /// ends the PROCESS without disposing the session.
    /// </summary>
    /// <remarks>
    /// The report is the handshake: the caller polls it for <c>pid=</c>, takes its live census while
    /// the hold lasts, then waits for exit and counts again. Nothing here is a verdict — the exit
    /// code is 0 on the undisposed path and whatever TerminateProcess leaves on the killed one; the
    /// measurement is the caller's.
    /// </remarks>
    /// <summary>
    /// Starts a session, reaches the in-life state under test — disposed, or its child exited —
    /// publishes the moment, then holds the PROCESS alive so the caller can count what the state
    /// left behind.
    /// </summary>
    private static async Task<int> InLifePathAsync(string? report, StringBuilder log, bool childExits)
    {
        ConPtyTerminalSession session;
        try
        {
            session = await ConPtyTerminalSession.StartAsync(
                new TerminalSessionRequest(
                    SessionId: childExits ? "in-life-child-exit" : "in-life-dispose",
                    Generation: 1,

                    // A child that LIVES long enough to be counted, then exits on its own. The
                    // first shape of this was `cmd.exe /c exit 0`, and the caller's live census
                    // still saw a host — only because the un-fixed runtime kept the host after
                    // the exit (INV-0010, path 5). Once the host follows the child, a child gone
                    // in 50 ms is gone before one CIM read completes, and the fact fails on its
                    // positive clause ("the key can see a host") rather than proving anything.
                    // Seven seconds of ping is longer than the caller's 5 s polling window; the
                    // non-zero code shows the exit is the child's own, not a kill.
                    CommandLine: childExits ? "cmd.exe /c \"ping -n 8 127.0.0.1 >nul & exit 3\"" : "powershell.exe",
                    WorkingDirectory: Path.GetTempPath(),
                    Columns: 80,
                    Rows: 25,
                    ProcessingClass: SessionProcessingClass.LocalOnly,
                    Integration: childExits ? ShellIntegrationMode.None : ShellIntegrationMode.PowerShell),
                CancellationToken.None);
        }
        catch (Exception ex)
        {
            log.AppendLine($"StartAsync threw {ex.GetType().Name}: {ex.Message}");
            Write(report, log);
            return 3;
        }

        using var draining = new CancellationTokenSource(TimeSpan.FromSeconds(30));
        _ = Task.Run(async () =>
        {
            try
            {
                while (await session.Output.WaitToReadAsync(draining.Token))
                {
                    while (session.Output.TryRead(out _))
                    {
                    }
                }
            }
            catch (OperationCanceledException)
            {
            }
        });

        log.AppendLine($"pid={Environment.ProcessId}");
        Write(report, log);

        if (childExits)
        {
            using var exitDeadline = new CancellationTokenSource(TimeSpan.FromSeconds(20));
            var exit = await session.WaitForExitAsync(exitDeadline.Token);
            log.AppendLine($"child-exited={DateTimeOffset.UtcNow:O} code={exit.ExitCode}");
        }
        else
        {
            await Task.Delay(TimeSpan.FromSeconds(2));
            await session.DisposeAsync();
            log.AppendLine($"disposed={DateTimeOffset.UtcNow:O}");
        }

        Write(report, log);

        // The caller's census window, with this process — the App's stand-in — still alive.
        await Task.Delay(TimeSpan.FromSeconds(6));

        if (childExits)
        {
            await session.DisposeAsync();
        }

        return 0;
    }

    /// <summary>
    /// Starts a session under a parent that carries <c>WT_*</c> and a control variable, has the
    /// child print its environment, and reports what arrived. Exit <b>0</b>: no <c>WT_</c> line and
    /// the control present; <b>2</b>: a <c>WT_</c> line arrived, or the control did not; <b>3</b>:
    /// could not start; <b>5</b>: the child's output never completed.
    /// </summary>
    private static async Task<int> EnvironmentScrubAsync(string? report, StringBuilder log)
    {
        const string control = "AIDE_ENV_PROBE";

        // The parent's state is SET here rather than assumed from the launcher: the fact is about
        // what the runtime strips, and a parent that happened to carry no WT_* would make "no WT_
        // line" true for a reason that is not the runtime's.
        Environment.SetEnvironmentVariable("WT_SESSION", "probe-6238a91b-f02c-4aca-86ee-08e02378260a");
        Environment.SetEnvironmentVariable("WT_PROFILE_ID", "{probe-61c54bbd-c2c6-5271-96e7-009a87ff44bf}");
        Environment.SetEnvironmentVariable(control, "kept");

        ConPtyTerminalSession session;
        try
        {
            session = await ConPtyTerminalSession.StartAsync(
                new TerminalSessionRequest(
                    SessionId: "env-scrub",
                    Generation: 1,
                    CommandLine: "cmd.exe /c set",
                    WorkingDirectory: Path.GetTempPath(),
                    Columns: 200,
                    Rows: 50,
                    ProcessingClass: SessionProcessingClass.LocalOnly),
                CancellationToken.None);
        }
        catch (Exception ex)
        {
            log.AppendLine($"StartAsync threw {ex.GetType().Name}: {ex.Message}");
            Write(report, log);
            return 3;
        }

        var seen = new StringBuilder();
        await using (session)
        {
            using var deadline = new CancellationTokenSource(TimeSpan.FromSeconds(20));
            try
            {
                while (await session.Output.WaitToReadAsync(deadline.Token))
                {
                    while (session.Output.TryRead(out var chunk))
                    {
                        seen.Append(Encoding.UTF8.GetString(chunk.Bytes.Span));
                    }
                }
            }
            catch (OperationCanceledException)
            {
                log.AppendLine("timed out waiting for the child's environment listing");
                Write(report, log);
                return 5;
            }
        }

        // `set` prints NAME=value per line; the pty wraps at the column width, so a name is read
        // from a line start only. The pty's own VT sequences (CSI and OSC) are stripped first.
        var plain = System.Text.RegularExpressions.Regex.Replace(
            seen.ToString(), "\u001b\\[[0-9;?]*[A-Za-z]|\u001b\\][^\u0007]*\u0007", "");
        var lines = plain.Split('\n')
            .Select(l => l.Trim('\r', ' '))
            .ToList();
        var wt = lines.Where(l => l.StartsWith("WT_", StringComparison.OrdinalIgnoreCase)).ToList();
        var kept = lines.Any(l => l.StartsWith(control + "=kept", StringComparison.Ordinal));

        log.AppendLine($"lines={lines.Count} wt-lines={wt.Count} control-present={kept}");
        foreach (var l in wt) { log.AppendLine("  WT line: " + l); }
        Write(report, log);
        return wt.Count == 0 && kept ? 0 : 2;
    }

    private static async Task<int> ExitPathAsync(string? report, StringBuilder log, bool kill)
    {
        ConPtyTerminalSession session;
        try
        {
            session = await ConPtyTerminalSession.StartAsync(
                new TerminalSessionRequest(
                    SessionId: kill ? "exit-path-kill" : "exit-path-undisposed",
                    Generation: 1,
                    CommandLine: "powershell.exe",
                    WorkingDirectory: Path.GetTempPath(),
                    Columns: 80,
                    Rows: 25,
                    ProcessingClass: SessionProcessingClass.LocalOnly,
                    Integration: ShellIntegrationMode.PowerShell),
                CancellationToken.None);
        }
        catch (Exception ex)
        {
            log.AppendLine($"StartAsync threw {ex.GetType().Name}: {ex.Message}");
            Write(report, log);
            return 3;
        }

        // Deliberately NOT `await using`: the session must still be live when the process ends.
        using var draining = new CancellationTokenSource(TimeSpan.FromSeconds(20));
        var drain = Task.Run(async () =>
        {
            try
            {
                while (await session.Output.WaitToReadAsync(draining.Token))
                {
                    while (session.Output.TryRead(out _))
                    {
                    }
                }
            }
            catch (OperationCanceledException)
            {
            }
        });

        log.AppendLine($"pid={Environment.ProcessId}");
        log.AppendLine($"held-from={DateTimeOffset.UtcNow:O}");
        Write(report, log);

        // The caller's census window. Six seconds is generous for one CIM enumeration.
        await Task.Delay(TimeSpan.FromSeconds(6));

        if (kill)
        {
            Process.GetCurrentProcess().Kill();
        }

        Environment.Exit(0);
        return 0; // unreachable
    }

    private static async Task<int> IntegrationAsync(string? report, StringBuilder log)
    {
        ConPtyTerminalSession session;
        try
        {
            session = await ConPtyTerminalSession.StartAsync(
                new TerminalSessionRequest(
                    SessionId: "integration-probe",
                    Generation: 1,
                    CommandLine: "powershell.exe",
                    WorkingDirectory: Path.GetTempPath(),
                    Columns: 80,
                    Rows: 25,
                    ProcessingClass: SessionProcessingClass.LocalOnly,
                    Integration: ShellIntegrationMode.PowerShell),
                CancellationToken.None);
        }
        catch (Exception ex)
        {
            log.AppendLine($"StartAsync threw {ex.GetType().Name}: {ex.Message}");
            Write(report, log);
            return 3;
        }

        await using (session)
        {
            // Drained continuously in the background: the output channel drops the oldest entry
            // when it fills, and a probe that only reads between steps would stall the very session
            // it is measuring.
            using var draining = new CancellationTokenSource(TimeSpan.FromSeconds(80));
            var drain = Task.Run(async () =>
            {
                try
                {
                    while (await session.Output.WaitToReadAsync(draining.Token))
                    {
                        while (session.Output.TryRead(out _))
                        {
                        }
                    }
                }
                catch (OperationCanceledException)
                {
                }
            });

            if (!await WaitForActivityAsync(session, SessionActivity.Ready, TimeSpan.FromSeconds(30)))
            {
                log.AppendLine($"never reached Ready at the prompt; activity is {session.Activity}");
                log.AppendLine(
                    "Either the integration did not install (PSReadLine absent, so the script "
                    + "returns without hooking anything) or its marks are not being believed.");
                Write(report, log);
                return 8;
            }

            log.AppendLine("Ready at the prompt: the D/A/B path is authenticated and believed");

            await SendAsync(session, "Start-Sleep -Seconds 4; 'CMD-DONE'");

            if (!await WaitForActivityAsync(session, SessionActivity.Busy, TimeSpan.FromSeconds(15)))
            {
                log.AppendLine($"never reached Busy while a command ran; activity is {session.Activity}");
                log.AppendLine(
                    "The C mark is missing, so the session would report Ready for the whole "
                    + "duration of every command.");
                Write(report, log);
                return 9;
            }

            log.AppendLine("Busy while the command ran: the C mark fires on line accept");

            if (!await WaitForActivityAsync(session, SessionActivity.Ready, TimeSpan.FromSeconds(30)))
            {
                log.AppendLine($"never returned to Ready after the command; activity is {session.Activity}");
                Write(report, log);
                return 10;
            }

            log.AppendLine("Ready again after the command: the loop closes");
            log.AppendLine("integration loop complete");

            draining.Cancel();
            await drain;

            Write(report, log);
            return 0;
        }
    }

    /// <summary>Polls until the session reports <paramref name="wanted"/>, or the deadline passes.</summary>
    /// <remarks>
    /// Polled rather than awaited because activity is a state, not an event — the contract exposes
    /// no change notification, and inventing one for a probe would be testing something the product
    /// does not have.
    /// </remarks>
    private static async Task<bool> WaitForActivityAsync(
        ConPtyTerminalSession session, SessionActivity wanted, TimeSpan limit)
    {
        var deadline = DateTimeOffset.UtcNow + limit;

        while (DateTimeOffset.UtcNow < deadline)
        {
            if (session.Activity == wanted)
            {
                return true;
            }

            await Task.Delay(50);
        }

        return false;
    }

    /// <summary>
    /// `P2-PRIV-01` — a secret printed by a terminal must reach the screen and nowhere else.
    /// </summary>
    /// <remarks>
    /// <para><b>Terminal output is the highest-volume personal and work data in the product.</b>
    /// Credentials, tokens and customer data all pass through a terminal, and the design's answer is
    /// that it is ephemeral by construction: a bounded in-memory ring, never written to the store,
    /// logs, metrics or traces. That is an <i>absence</i>, and the only honest way to assert an
    /// absence is to seed something unique and go looking for it.</para>
    ///
    /// <para><b>The non-vacuity check is the important half.</b> An absence over an empty set is
    /// free — if the secret never reached the terminal at all, every assertion below passes while
    /// proving nothing. So this first requires the seed to arrive on the output channel, and only
    /// then requires it to be nowhere else.</para>
    ///
    /// <para>It runs here because a real ConPTY child needs a real console (<b>DC-014</b>), and a
    /// real child is the point: a fixture session would only prove that the fixture keeps secrets.</para>
    ///
    /// <para>Exit codes: <b>0</b> the seed reached the screen and nothing else, <b>3</b> could not
    /// start, <b>6</b> it reached a span attribute, <b>7</b> it reached a file in the workspace,
    /// <b>8</b> it never reached the terminal, so every assertion would have been vacuous, <b>9</b>
    /// a workspace file could not be read, so the check did not cover what it claims to.</para>
    /// </remarks>
    private static async Task<int> PrivacyAsync(string? report, StringBuilder log)
    {
        // Generated per run, so a stale artifact from a previous run can neither cause a pass nor a
        // failure, and unique enough that a match cannot be coincidence.
        var seed = "AIDE-PRIV-" + Guid.NewGuid().ToString("N");

        var captured = new List<Activity>();
        using var listener = new ActivityListener
        {
            // Every source, not a prefix. A listener scoped to a naming convention cannot see a
            // source that broke it, which is exactly how a privacy net develops a hole.
            ShouldListenTo = _ => true,
            Sample = (ref ActivityCreationOptions<ActivityContext> _) => ActivitySamplingResult.AllDataAndRecorded,
            ActivityStopped = activity => { lock (captured) { captured.Add(activity); } },
        };
        ActivitySource.AddActivityListener(listener);

        var workspaceRoot = Path.Combine(Path.GetTempPath(), $"aide-priv-root-{Guid.NewGuid():N}");
        var dataDirectory = Path.Combine(Path.GetTempPath(), $"aide-priv-data-{Guid.NewGuid():N}");
        Directory.CreateDirectory(workspaceRoot);

        ConPtyTerminalSession session;
        WorkspaceCore core;

        try
        {
            // A REAL workspace beside the terminal, so "output never crosses into the store" is
            // asserted against a store that exists and has been written to, not an empty directory.
            core = WorkspaceCore.Open("priv", workspaceRoot, dataDirectory);
            await core.RefreshScopeAsync("fixture", "rev-1");

            session = await ConPtyTerminalSession.StartAsync(
                new TerminalSessionRequest(
                    SessionId: "privacy-probe",
                    Generation: 1,
                    // The seed is in the COMMAND LINE as well as printed later. The privacy
                    // analysis says a session's command line "may contain paths or arguments" and
                    // is excluded from telemetry — a separate claim from output, and one nothing
                    // tested until a mutation added a command-line tag and no test failed.
                    CommandLine: $"cmd.exe /c echo {seed} && echo {seed}",
                    WorkingDirectory: Path.GetTempPath(),
                    Columns: 80,
                    Rows: 25,
                    ProcessingClass: SessionProcessingClass.LocalOnly),
                CancellationToken.None);
        }
        catch (Exception ex)
        {
            log.AppendLine($"could not start: {ex.GetType().Name}: {ex.Message}");
            Write(report, log);
            return 3;
        }

        await using (session)
        {
            // ONE occurrence, and the reason is the whole diagnosis of a flake that reddened CI
            // twice while passing locally every time (INV-0005).
            //
            // Nothing is typed here — the child prints the seed itself — so there is no keystroke
            // echo to skip, and the second occurrence was never evidence of anything the first did
            // not already prove. Meanwhile ConPtyTerminalSession's output channel is
            // BoundedChannelFullMode.DropOldest, which is right for a live terminal and means the
            // EARLIEST chunks are discarded under load. `cmd /c echo && echo` exits in
            // milliseconds, so on a loaded runner the first echo can be dropped before anything
            // drains — and the probe then waited for a second occurrence that could never arrive,
            // reporting "output completed before the marker appeared".
            //
            // The terminal is behaving correctly; the probe was assuming lossless delivery over a
            // channel that is deliberately lossy. One occurrence is all this test needs: it only
            // has to prove the seed reached the output channel before asserting it appears nowhere
            // else.
            var reached = await WaitForAsync(session, seed, log, occurrences: 1);

            if (!reached)
            {
                log.AppendLine("the seed never reached the output channel; every absence below would be vacuous");
                Write(report, log);
                return 8;
            }

            log.AppendLine("the seed reached the terminal's output channel, as it must");

            var spanLeaks = new List<string>();

            lock (captured)
            {
                foreach (var activity in captured)
                {
                    foreach (var tag in activity.Tags)
                    {
                        if ((tag.Value ?? string.Empty).Contains(seed, StringComparison.Ordinal))
                        {
                            spanLeaks.Add($"{activity.OperationName}/{tag.Key}");
                        }
                    }
                }

                log.AppendLine($"spans captured: {captured.Count}");
            }

            if (spanLeaks.Count > 0)
            {
                log.AppendLine("LEAKED into span attributes: " + string.Join(", ", spanLeaks));
                Write(report, log);
                return 6;
            }

            // CLOSED BEFORE SCANNING. SQLite holds the database open, and the first run of this
            // probe reported it could not read workspace.db — so the most important file in the
            // check was not being covered at all. The honest report exposed it; leaving the core
            // open would have left a passing test that skipped the store.
            core.Dispose();

            // Every file the workspace wrote: the store, the audit trail, the health sidecar.
            var fileLeaks = new List<string>();
            var unreadable = new List<string>();
            var scanned = 0;

            foreach (var file in Directory.EnumerateFiles(dataDirectory, "*", SearchOption.AllDirectories))
            {
                try
                {
                    scanned++;
                    if (File.ReadAllText(file).Contains(seed, StringComparison.Ordinal))
                    {
                        fileLeaks.Add(Path.GetFileName(file));
                    }
                }
                catch (IOException)
                {
                    // A FAILURE, not a note. A file this run could not read is a file the check did
                    // not cover, and a pass that skipped the store would be exactly the kind of
                    // absence-over-an-empty-set this whole probe exists to avoid.
                    unreadable.Add(Path.GetFileName(file));
                }
            }

            log.AppendLine($"workspace files scanned: {scanned - unreadable.Count} of {scanned}");

            if (unreadable.Count > 0)
            {
                log.AppendLine("NOT COVERED — these files could not be read: " + string.Join(", ", unreadable));
                Write(report, log);
                return 9;
            }

            if (fileLeaks.Count > 0)
            {
                log.AppendLine("LEAKED into workspace files: " + string.Join(", ", fileLeaks));
                Write(report, log);
                return 7;
            }

            log.AppendLine("the seed reached no span attribute and no workspace file");
            Write(report, log);
            return 0;
        }
    }

    private static async Task SendAsync(ConPtyTerminalSession session, string line) =>
        await session.WriteAsync(1, Encoding.UTF8.GetBytes(line + "\r"), CancellationToken.None);

    /// <summary>Drains output until <paramref name="marker"/> appears, or the deadline passes.</summary>
    /// <remarks>
    /// The marker is printed by the same command that emitted the sequence, so seeing it proves the
    /// read loop has already consumed the sequence — the two cannot be reordered, because they leave
    /// the child in that order down one pipe.
    /// </remarks>
    private static async Task<bool> WaitForAsync(
        ConPtyTerminalSession session, string marker, StringBuilder log, int occurrences = 2)
    {
        var seen = new StringBuilder();
        using var deadline = new CancellationTokenSource(TimeSpan.FromSeconds(25));

        try
        {
            while (await session.Output.WaitToReadAsync(deadline.Token))
            {
                while (session.Output.TryRead(out var chunk))
                {
                    seen.Append(Encoding.UTF8.GetString(chunk.Bytes.Span));

                    // Where the marker is TYPED, the terminal echoes our keystrokes back, so the
                    // first occurrence is our own input and only the second proves the child ran.
                    // Where the child prints it unprompted there is no echo, and demanding two is
                    // asking a deliberately lossy channel not to lose — see the privacy probe.
                    var text = seen.ToString();
                    var found = 0;
                    for (var at = text.IndexOf(marker, StringComparison.Ordinal);
                         at >= 0;
                         at = text.IndexOf(marker, at + 1, StringComparison.Ordinal))
                    {
                        if (++found >= occurrences)
                        {
                            return true;
                        }
                    }
                }
            }

            log.AppendLine($"output completed before '{marker}' appeared");
            return false;
        }
        catch (OperationCanceledException)
        {
            log.AppendLine($"timed out waiting for '{marker}'");
            log.AppendLine("raw: " + seen.ToString().Replace("", "<ESC>"));
            return false;
        }
    }

    /// <summary>
    /// Writes the log where the caller can read it.
    /// </summary>
    /// <remarks>
    /// A new console closes when this process exits, taking its own stdout with it, so the detail
    /// has to leave through a file. Without it a failing run reports only an exit code, and "2"
    /// tells nobody why.
    /// </remarks>
    private static void Write(string? path, StringBuilder log)
    {
        if (string.IsNullOrWhiteSpace(path))
        {
            return;
        }

        try
        {
            File.WriteAllText(path, log.ToString());
        }
        catch (IOException)
        {
        }
        catch (UnauthorizedAccessException)
        {
        }
    }
}
