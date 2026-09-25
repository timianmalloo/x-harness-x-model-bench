using System.Runtime.Versioning;
using System.Text;
using AiDe.Core.Dispatch;
using AiDe.Core.Facts;
using AiDe.Core.Ipc;
using AiDe.Core.Store;
using AiDe.Core.Terminal;

namespace AiDe.Core.TerminalHost;

/// <summary>
/// <b>ADR-0010 end to end, against a live session.</b>
/// </summary>
/// <remarks>
/// <para>A real daemon over a real pipe records the write-ahead attempt; a real ConPTY PowerShell
/// receives the prompt; the outcome is finalized; and the prompt is proven to have been
/// <i>acted on</i> rather than merely written.</para>
///
/// <para><b>The marker is the point.</b> A receipt saying <c>PtyWriteAccepted</c> proves bytes left
/// the process. It does not prove the session did anything with them — and a dispatch protocol whose
/// only evidence is its own receipt is a protocol agreeing with itself. So the prompt asks the shell
/// to emit a unique string, and this waits for that string to come back <i>out</i> of the terminal.
/// The marker appears twice (the shell echoes the line before running it), so the second occurrence
/// is what proves execution rather than echo.</para>
///
/// <para>Out of process because ConPTY needs a real console (<b>DC-014</b>), and the daemon is stood
/// up for real rather than mocked because a receipt that never crossed a boundary proves nothing
/// about the boundary.</para>
/// </remarks>
[SupportedOSPlatform("windows")]
internal static class DispatchProbe
{
    internal const int Ok = 0;
    internal const int SessionDidNotStart = 3;
    internal const int ReceiptNotAccepted = 5;
    internal const int WrittenButNotActedOn = 6;
    internal const int Threw = 7;

    /// <summary>Refused because readiness could not be established. The fix working, not a failure.</summary>
    internal const int RefusedNotReady = 8;

    /// <summary>
    /// Runs the probe against <paramref name="commandLine"/>.
    /// </summary>
    /// <param name="commandLine">
    /// The process to dispatch into. PowerShell is the portable case the suite runs; an agent CLI is
    /// the case that closes ADR-0010's stated residual, and it lives in a spike because a CI box has
    /// no agent installed and a test that skipped would report green while proving nothing.
    /// </param>
    /// <param name="prompt">
    /// What to send. It must produce the marker in the session's OUTPUT — a receipt alone cannot
    /// tell a delivered prompt from one written into a void.
    /// </param>
    /// <param name="settleSeconds">
    /// How long to let the process reach its input state. A shell needs a moment; an agent CLI needs
    /// considerably longer, and a prompt sent before it is listening is simply dropped.
    /// </param>
    internal static async Task<int> RunAsync(
        StringBuilder log,
        string commandLine = "powershell.exe",
        string? prompt = null,
        int settleSeconds = 8,
        int expectedOccurrences = 2,
        string? workingDirectory = null)
    {
        var marker = "AIDEDISPATCH" + Guid.NewGuid().ToString("N")[..12].ToUpperInvariant();
        var dataDirectory = Path.Combine(
            Path.GetTempPath(), "aide-dispatch-probe", Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(dataDirectory);

        var pipeName = "aide-dispatch-probe-" + Guid.NewGuid().ToString("N")[..12];

        try
        {
            using var store = WorkspaceStore.Open(Path.Combine(dataDirectory, "workspace.db"));

            var endpoint = new DaemonEndpoint(pipeName, new CapabilityRegistry(), _ => store.CoreEpoch);
            DaemonOperations.Register(endpoint, () => store.CoreEpoch);
            WorkspaceOperations.RegisterDispatch(endpoint, new BoundaryDispatcher(store));

            var server = new IpcServer(
                pipeName, endpoint, new IpcServerOptions(StartupGrace: TimeSpan.FromSeconds(60)));

            using var life = new CancellationTokenSource(TimeSpan.FromSeconds(150));
            var running = server.RunAsync(life.Token);

            ConPtyTerminalSession session;
            try
            {
                session = await ConPtyTerminalSession.StartAsync(
                    new TerminalSessionRequest(
                        SessionId: "dispatch-probe",
                        Generation: 1,
                        CommandLine: commandLine,
                        WorkingDirectory: workingDirectory ?? Path.GetTempPath(),
                        Columns: 120,
                        Rows: 30,
                        ProcessingClass: SessionProcessingClass.LocalOnly,
                        Integration: commandLine.Contains("powershell", StringComparison.OrdinalIgnoreCase)
                            ? ShellIntegrationMode.PowerShell
                            : ShellIntegrationMode.None),
                    CancellationToken.None);
            }
            catch (Exception ex)
            {
                log.AppendLine($"StartAsync threw {ex.GetType().Name}: {ex.Message}");
                return SessionDidNotStart;
            }

            await using (session)
            {
                var seen = new TaskCompletionSource<bool>(TaskCreationOptions.RunContinuationsAsynchronously);
                using var draining = new CancellationTokenSource(TimeSpan.FromSeconds(120));

                var captured = new StringBuilder();

                // An agent session gets a readiness watcher; a shell reports through OSC 133.
                // Through the profiles, so the probe judges readiness exactly as the product does.
                // A probe evaluating the pattern its own way can report a state the shell never sees.
                var watcher = AgentReadinessProfiles.BuiltIn.WatcherFor(
                    Path.GetFileNameWithoutExtension(commandLine));
                var drain = Task.Run(async () =>
                {
                    var buffer = captured;
                    try
                    {
                        while (await session.Output.WaitToReadAsync(draining.Token))
                        {
                            while (session.Output.TryRead(out var chunk))
                            {
                                var text = Encoding.UTF8.GetString(chunk.Bytes.Span);
                                buffer.Append(text);
                                watcher?.Observe(text);
                                if (Occurrences(buffer.ToString(), marker) >= expectedOccurrences)
                                {
                                    seen.TrySetResult(true);
                                }
                            }
                        }
                    }
                    catch (OperationCanceledException)
                    {
                    }
                });

                // Let the shell reach its first prompt before writing to it. A prompt delivered into
                // a shell that is still starting is dropped, and would look like a protocol failure.
                await Task.Delay(TimeSpan.FromSeconds(settleSeconds));

                await using var client = await WorkspaceClient.ConnectAsync(
                    pipeName, TimeSpan.FromSeconds(30), CancellationToken.None);

                var body = "Write-Output " + Quote(marker) + "\r\n";

                var command = new DispatchCommand(
                    WorkspaceId: "probe",
                    WorkspaceEpoch: await client.EpochAsync(CancellationToken.None),
                    Caller: new CallerPrincipal("probe", CallerKind.Shell),
                    CommandId: Guid.NewGuid().ToString("N"),
                    DraftId: "draft-probe",
                    RevisionNo: 1,
                    Body: body,
                    SessionId: session.SessionId,
                    SessionGeneration: session.Generation);

                // READINESS FIRST. This is what the trust-gate finding produced: an agent that has
                // not reached its prompt is refused rather than written into, and the refusal leaves
                // no durable attempt behind.
                var readiness = watcher is null
                    ? SessionReadiness.Ready
                    : watcher.IsReady ? SessionReadiness.Ready : SessionReadiness.Unknown;

                log.AppendLine($"readiness      : {readiness}" +
                               (watcher is null ? " (shell integration)" : " (observed pattern)"));

                if (readiness != SessionReadiness.Ready)
                {
                    log.AppendLine("REFUSED before the write-ahead: " + SessionReadinessPolicy.Explain(readiness));
                    log.AppendLine("This is the fix working. The prompt was NOT written into whatever the");
                    log.AppendLine("agent is currently showing, and no durable attempt was recorded.");

                    var tailNow = captured.ToString();
                    log.AppendLine("---- last 900 bytes of session output ----");
                    log.AppendLine(tailNow.Length > 900 ? tailNow[^900..] : tailNow);
                    log.AppendLine("---- end ----");

                    await draining.CancelAsync();
                    await life.CancelAsync();
                    return RefusedNotReady;
                }

                var receipt = await BoundaryDispatcher.BeginAndWriteAsync(
                    command, session, client.DispatchBeginAsync, client.DispatchFinalizeAsync,
                    CancellationToken.None, readiness);

                log.AppendLine($"receipt state  : {receipt.State}");
                log.AppendLine($"receipt error  : {receipt.ErrorCode ?? "(none)"}");

                if (receipt.State != DispatchState.PtyWriteAccepted)
                {
                    log.AppendLine("the daemon did not record an accepted write");
                    await life.CancelAsync();
                    return ReceiptNotAccepted;
                }

                var acted = await Task.WhenAny(seen.Task, Task.Delay(TimeSpan.FromSeconds(60))) == seen.Task;

                await draining.CancelAsync();
                try { await drain; } catch (OperationCanceledException) { }
                await life.CancelAsync();
                try { await running; } catch (OperationCanceledException) { }

                log.AppendLine($"marker acted on: {acted}");

                if (!acted)
                {
                    log.AppendLine("the receipt says the write was accepted, but the session never produced");
                    log.AppendLine("the marker — the prompt was written and NOT acted on.");

                    // The tail of what the session DID say. Without it this failure is
                    // indistinguishable between "the process never started", "it was not ready" and
                    // "it needs a different submit convention" — three different fixes.
                    var tail = captured.ToString();
                    tail = tail.Length > 1600 ? tail[^1600..] : tail;
                    log.AppendLine("---- last 1600 bytes of session output ----");
                    log.AppendLine(tail);
                    log.AppendLine("---- end ----");
                    return WrittenButNotActedOn;
                }

                log.AppendLine("dispatch crossed a real daemon, reached a live session, was EXECUTED,");
                log.AppendLine("and the durable receipt agrees with what the session actually did.");
                return Ok;
            }
        }
        catch (Exception ex)
        {
            log.AppendLine($"dispatch probe threw {ex.GetType().Name}: {ex.Message}");
            return Threw;
        }
        finally
        {
            Microsoft.Data.Sqlite.SqliteConnection.ClearAllPools();
            try { Directory.Delete(dataDirectory, recursive: true); } catch (IOException) { }
        }
    }

    /// <summary>A single-quoted PowerShell literal, built without embedding a quote in C# source.</summary>
    private static string Quote(string value) => (char)39 + value + (char)39;

    private static int Occurrences(string text, string value)
    {
        var count = 0;
        for (var i = text.IndexOf(value, StringComparison.Ordinal); i >= 0;
             i = text.IndexOf(value, i + value.Length, StringComparison.Ordinal))
        {
            count++;
        }

        return count;
    }
}
