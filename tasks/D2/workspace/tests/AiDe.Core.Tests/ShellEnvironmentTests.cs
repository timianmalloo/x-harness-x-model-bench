using AiDe.Core.Terminal;

namespace AiDe.Core.Tests;

/// <summary>
/// The terminal must behave like the user's own terminal.
/// </summary>
/// <remarks>
/// <para><b>Reported as a defect, not found by a test.</b> The shell was launched with
/// <c>-NoProfile</c> for determinism, which meant the user's profile never ran — and a profile is
/// where PATH additions, aliases and tool shims live. Tools the user had installed were simply not
/// on PATH inside the product's terminal, so the terminal could not be worked in.</para>
///
/// <para><b>The determinism concern is met by ORDER instead.</b> The profile runs first, then the
/// integration script, which captures whatever <c>prompt</c> it finds and wraps it — so a profile
/// cannot redefine the prompt after us, because it has already run.</para>
/// </remarks>
public sealed class ShellEnvironmentTests
{
    private const string Nonce = "0123456789abcdef0123456789abcdef";

    [Fact]
    public void TheShellIsLaunchedWithTheUsersProfile()
    {
        // The control. -NoProfile is a one-word change that silently removes the user's tooling from
        // their own terminal, and nothing else in the suite would notice.
        var commandLine = ShellIntegration.PowerShellCommandLine("powershell.exe", Nonce);

        Assert.DoesNotContain("-NoProfile", commandLine, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("-noni", commandLine, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public void TheSessionStaysInteractiveAndKeepsItsIntegration()
    {
        var commandLine = ShellIntegration.PowerShellCommandLine("powershell.exe", Nonce);

        // -NoExit keeps the shell alive after the integration script; without it the terminal would
        // start, install the integration and immediately exit.
        Assert.Contains("-NoExit", commandLine, StringComparison.Ordinal);
        Assert.Contains("-EncodedCommand", commandLine, StringComparison.Ordinal);
    }

    [Fact]
    public void TheIntegrationWrapsAnExistingPrompt_RatherThanReplacingIt()
    {
        // This is what makes loading the profile safe: the user's prompt survives, and ours marks
        // around it. Replacing it would trade one broken terminal for another.
        var script = ShellIntegration.PowerShellScript(Nonce);

        Assert.Contains("$global:__AidePrompt = $function:prompt", script, StringComparison.Ordinal);
    }

    [Fact]
    public void TheNonceTravelsInTheScript_SoStateClaimsRemainAuthenticated()
    {
        // Loading the profile must not weaken the OSC 133 control: an unauthenticated claim from
        // anything else in the terminal is still not believed.
        var script = ShellIntegration.PowerShellScript(Nonce);

        Assert.Contains(Nonce, script, StringComparison.Ordinal);
    }
}
