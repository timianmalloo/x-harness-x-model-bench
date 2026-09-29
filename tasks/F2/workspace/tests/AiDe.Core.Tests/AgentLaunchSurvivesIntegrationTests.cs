using System.Diagnostics;
using AiDe.Core.Terminal;

namespace AiDe.Core.Tests;

/// <summary>
/// The agent starts whether or not the shell integration can install itself.
/// </summary>
/// <remarks>
/// <para><b>The defect, from a screenshot of the running product.</b> Opening a "Claude Code" session
/// produced a plain PowerShell prompt at the workspace root, with the status bar reporting
/// <i>"Claude Code session opened."</i> The terminal itself said why:</para>
/// <code>
/// Warning: PowerShell detected that you might be using a screen reader and has
/// disabled PSReadLine for compatibility purposes.
/// </code>
///
/// <para><b>So the guard fires every time inside the product.</b> The integration script declines to
/// install when <c>Set-PSReadLineKeyHandler</c> is unavailable — correctly, because a half-installed
/// report loop would claim Ready for the length of every command. It declined with a bare
/// <c>return</c>, and at the top level of an <c>-EncodedCommand</c> script that ends the SCRIPT. The
/// agent invocation was appended after it, so it never ran, and <c>-NoExit</c> left a working shell:
/// a terminal that looks exactly like the one that was asked for.</para>
///
/// <para><b>Why this needs a real process.</b> The same check run from an ordinary console finds
/// PSReadLine present and the bug invisible — a hypothesis about this exact line was raised and
/// wrongly dismissed on that evidence hours before the screenshot arrived. The condition is
/// reproduced here by emptying <c>PSModulePath</c> in the child, which stops module auto-loading the
/// way the host's screen-reader detection does.</para>
///
/// <para><b>The agent stands in as <c>whoami</c></b> — same code path, prints something checkable,
/// and starts no billable session.</para>
/// </remarks>
[Trait("Platform", "Windows")]
public sealed class AgentLaunchSurvivesIntegrationTests
{
    private static readonly TimeSpan Timeout = TimeSpan.FromSeconds(90);

    /// <summary>Runs the generated agent command line and returns what the child printed.</summary>
    /// <param name="psModulePath">
    /// The child's <c>PSModulePath</c>. Empty suppresses module auto-loading, which is how the
    /// PSReadLine-absent case is reproduced without needing the host's screen-reader detection.
    /// </param>
    private static string Run(string psModulePath)
    {
        var commandLine = ShellIntegration
            .AgentCommandLine("powershell.exe", "whoami", "abc123")
            // -NoExit would leave the child at a prompt forever. Removing it is the only difference
            // from what the product launches.
            .Replace("-NoExit ", string.Empty, StringComparison.Ordinal);

        var encoded = commandLine[(commandLine.IndexOf("-EncodedCommand ", StringComparison.Ordinal)
            + "-EncodedCommand ".Length)..];

        var start = new ProcessStartInfo("powershell.exe", $"-NoLogo -EncodedCommand {encoded}")
        {
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
        };

        start.Environment["PSModulePath"] = psModulePath;

        using var process = Process.Start(start);
        Assert.NotNull(process);

        var output = process!.StandardOutput.ReadToEnd();
        Assert.True(process.WaitForExit((int)Timeout.TotalMilliseconds),
            "the probe shell did not exit; the generated command line is waiting for input");

        return output;
    }

    private static bool AgentRan(string output) =>
        output.Contains(Environment.UserName, StringComparison.OrdinalIgnoreCase);

    [Fact]
    public void TheAgentRunsWhenTheIntegrationCannotInstall()
    {
        // THE DEFECT. Measured against the shipped binary before the fix: agent ran = False here and
        // True below, which is the whole bug — invisible in every environment where PSReadLine loads,
        // and certain in the one the product actually uses.
        var output = Run(psModulePath: string.Empty);

        Assert.True(AgentRan(output),
            "the shell integration declined to install and took the agent invocation with it, so the "
            + "session is a plain shell while the product reports an agent session opened. The "
            + "integration must be able to decline without cancelling the launch.");
    }

    [Fact]
    public void TheAgentStillRunsWhenTheIntegrationDoesInstall()
    {
        // The other half, so a "fix" that simply stopped running the integration would fail here.
        var output = Run(psModulePath: Environment.GetEnvironmentVariable("PSModulePath") ?? string.Empty);

        Assert.True(AgentRan(output),
            "the agent did not run in the ordinary case, so the launch is broken for every session "
            + "rather than only the ones where the integration declines");
    }

    [Fact]
    public void TheIntegrationIsStillAttemptedRatherThanSkipped()
    {
        // The DC-016 guard on both tests above: dropping the integration entirely would make them
        // pass while removing the OSC-133 reporting that readiness, dispatch and the prompt-target
        // list all depend on. The nonce appearing in the script is the evidence it is still there.
        var commandLine = ShellIntegration.AgentCommandLine("powershell.exe", "whoami", "abc123");

        var encoded = commandLine[(commandLine.IndexOf("-EncodedCommand ", StringComparison.Ordinal)
            + "-EncodedCommand ".Length)..];

        var script = System.Text.Encoding.Unicode.GetString(Convert.FromBase64String(encoded));

        Assert.Contains("abc123", script, StringComparison.Ordinal);
        Assert.Contains("& 'whoami'", script, StringComparison.Ordinal);
    }
}
