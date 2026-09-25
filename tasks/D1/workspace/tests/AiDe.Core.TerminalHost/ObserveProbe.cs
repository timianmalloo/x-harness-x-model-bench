using AiDe.Core.Dispatch;
using AiDe.Core.Facts;
using System.Text;
using AiDe.Core.Terminal;

namespace AiDe.Core.TerminalHost;

/// <summary>
/// Launches an agent CLI and prints what it actually puts on the screen.
/// </summary>
/// <remarks>
/// <para><b>Written because a readiness marker was being tuned by inference.</b> The built-in
/// patterns are a guess at what an agent's prompt looks like, and a guess that does not match
/// refuses that agent forever — silently, because an unmatched pattern and a busy agent are the
/// same observation. There was no way to see the difference without this.</para>
///
/// <para>It asserts nothing and cannot fail. It is an instrument: it prints the tail with control
/// characters made visible, and reports whether each configured marker matched THAT tail — so the
/// pattern is written against measured output rather than against a memory of what a CLI prints.</para>
/// </remarks>
[System.Runtime.Versioning.SupportedOSPlatform("windows")]
internal static class ObserveProbe
{
    internal static async Task<int> RunAsync(
        StringBuilder log,
        string commandLine,
        string workingDirectory,
        int settleSeconds,
        bool hosted = false)
    {
        log.AppendLine($"observing  : {commandLine}");
        log.AppendLine($"cwd        : {workingDirectory}");
        log.AppendLine($"settle     : {settleSeconds}s");
        log.AppendLine($"hosted     : {hosted}");

        // The PARENT's own environment, printed before the child starts. Without this the question
        // "was the environment lost at the parent or between parent and child" cannot be answered,
        // and every hypothesis about the child is unfalsifiable.
        var parentPath = Environment.GetEnvironmentVariable("PATH") ?? string.Empty;
        log.AppendLine($"parent PATH: {parentPath.Length} chars, " +
                       $"{parentPath.Split(';', StringSplitOptions.RemoveEmptyEntries).Length} entries");
        log.AppendLine($"parent has System32: " +
                       parentPath.Contains("System32", StringComparison.OrdinalIgnoreCase));
        log.AppendLine($"parent env vars: {Environment.GetEnvironmentVariables().Count}");
        log.AppendLine();

        ITerminalSession session;
        try
        {
            session = await ConPtyTerminalSession.StartAsync(
                new TerminalSessionRequest(
                    SessionId: "observe-1",
                    Generation: 1,
                    CommandLine: commandLine,
                    WorkingDirectory: workingDirectory,
                    Columns: 120,
                    Rows: 30,
                    ProcessingClass: SessionProcessingClass.LocalOnly,
                    // `hosted` runs the command inside the user's login shell, which is what the
                    // product now does for an agent. Both paths are available here so the before
                    // and the after are measured by the same instrument.
                    Integration: hosted
                        ? ShellIntegrationMode.PowerShellHostedAgent
                        : ShellIntegrationMode.None),
                CancellationToken.None);
        }
        catch (Exception ex)
        {
            log.AppendLine($"StartAsync threw {ex.GetType().Name}: {ex.Message}");
            return 3;
        }

        var captured = new StringBuilder();

        await using (session)
        {
            using var draining = new CancellationTokenSource(TimeSpan.FromSeconds(settleSeconds));

            try
            {
                while (await session.Output.WaitToReadAsync(draining.Token))
                {
                    while (session.Output.TryRead(out var chunk))
                    {
                        captured.Append(Encoding.UTF8.GetString(chunk.Bytes.Span));
                    }
                }
            }
            catch (OperationCanceledException)
            {
                // Settling is the point. An agent that is still drawing when the window closes has
                // told us what we came for.
            }
        }

        var text = captured.ToString();
        var tail = text.Length <= 1200 ? text : text[^1200..];

        log.AppendLine($"captured   : {text.Length} char(s)");
        log.AppendLine();
        log.AppendLine("── tail, escaped ─────────────────────────────────────────────────────────────");
        log.AppendLine(Escape(tail));
        log.AppendLine("──────────────────────────────────────────────────────────────────────────────");
        log.AppendLine();

        // Fed through a real watcher, not a fresh Regex, so what is reported here is exactly what
        // dispatch would decide. A probe that evaluated the pattern its own way could report a match
        // the product does not see.
        foreach (var profile in AgentReadinessProfiles.BuiltIn.All)
        {
            var watcher = new AgentReadinessWatcher(profile.Pattern);
            watcher.Observe(text);
            log.AppendLine($"marker '{profile.Agent}' ({profile.Pattern}) → {(watcher.IsReady ? "READY" : "no match")}");
        }

        return 0;
    }

    /// <summary>
    /// Makes control characters visible.
    /// </summary>
    /// <remarks>
    /// An agent's screen is mostly escape sequences, and a raw dump is unreadable in a way that
    /// hides exactly the whitespace a tail-anchored pattern turns on.
    /// </remarks>
    private static string Escape(string text)
    {
        var builder = new StringBuilder(text.Length + 64);

        foreach (var c in text)
        {
            _ = c switch
            {
                '' => builder.Append("<ESC>"),
                '\r' => builder.Append("<CR>"),
                '\n' => builder.Append("<LF>").Append('\n'),
                '\t' => builder.Append("<TAB>"),
                '\a' => builder.Append("<BEL>"),
                _ => char.IsControl(c) ? builder.Append($"<{(int)c:X2}>") : builder.Append(c),
            };
        }

        return builder.ToString();
    }
}
