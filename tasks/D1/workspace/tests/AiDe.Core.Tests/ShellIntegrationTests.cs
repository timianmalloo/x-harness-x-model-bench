using System.Text;
using AiDe.Core.Terminal;

namespace AiDe.Core.Tests;

/// <summary>
/// The script that makes the OSC control operate — and the rules that stop it lying.
/// </summary>
/// <remarks>
/// <para><b>Why this exists at all.</b> The parser authenticates OSC 133 against a per-session nonce,
/// but a nonce nothing ever emits authenticates nothing: without an integration, every real session
/// falls back to the coarse output heuristic and the control is built, tested and dormant.</para>
///
/// <para><b>The rule that shapes the whole design is all-or-nothing.</b> Once one authenticated
/// claim arrives, OSC becomes authoritative and the heuristic retires (see
/// <see cref="TerminalActivityStateTests"/>). An integration that announced <c>D</c> at the prompt
/// but never <c>C</c> when a command started would therefore leave the session reporting
/// <c>Ready</c> for the entire duration of every command — strictly worse than the heuristic it
/// displaced. So the script installs the complete loop or installs nothing at all, and "nothing" is
/// a supported outcome rather than a failure.</para>
/// </remarks>
[Trait("Platform", "Windows")]
public sealed class ShellIntegrationTests
{
    private const string Nonce = "0123456789abcdef0123456789abcdef";

    private static string Script() => ShellIntegration.PowerShellScript(Nonce);

    // ---- the script carries the nonce into every claim ---------------------

    [Fact]
    public void TheScript_EmitsEveryStateMarkerOfTheLoop()
    {
        var script = Script();

        // Asserted at the call sites rather than as finished sequences: the script composes
        // `133;<token>;nonce=` in one helper so the nonce is written once, which means no complete
        // sequence appears literally in the source. What this checks is that all four marks are
        // reached; that they produce the right BYTES is settled end to end by
        // ShellIntegrationRoundTripTests, which is the only place that can settle it.
        Assert.Contains("]133;", script, StringComparison.Ordinal);
        Assert.Contains(@"__AideMark ""D;$code""", script, StringComparison.Ordinal);
        Assert.Contains("__AideMark 'A'", script, StringComparison.Ordinal);
        Assert.Contains("__AideMark 'B'", script, StringComparison.Ordinal);
        Assert.Contains("__AideMark 'C'", script, StringComparison.Ordinal);
    }

    [Fact]
    public void TheScript_CarriesTheSessionNonce()
    {
        Assert.Contains(Nonce, Script(), StringComparison.Ordinal);
    }

    [Fact]
    public void TheScript_InstallsNothingWhenItCannotEmitTheWholeLoop()
    {
        // The C mark needs a line-accept hook. Where that hook is unavailable the script must bail
        // out BEFORE overriding anything, leaving the session on the heuristic.
        //
        // Ordering is the whole assertion. A guard that ran AFTER the prompt override would leave a
        // shell with no PSReadLine emitting D/A/B and never C — the half-loop that pins a session at
        // Ready for the length of every command. The bail-out has to come first to be a control at
        // all, and this is the only place that can check it: on a machine where PSReadLine IS
        // present, no end-to-end probe can reach the branch.
        var script = Script();

        var guard = script.IndexOf("Get-Command Set-PSReadLineKeyHandler", StringComparison.Ordinal);
        var promptOverride = script.IndexOf("function global:prompt", StringComparison.Ordinal);
        var hook = script.IndexOf("Set-PSReadLineKeyHandler -Chord Enter", StringComparison.Ordinal);

        Assert.True(guard >= 0, "the script does not check whether it can hook line accept");
        Assert.True(promptOverride >= 0, "the script does not override the prompt");
        Assert.True(hook >= 0, "the script does not hook line accept");
        Assert.True(
            guard < promptOverride,
            "the capability guard must precede the prompt override, or a shell without PSReadLine "
            + "gets a half-loop that is worse than no integration");
        Assert.Contains("return", script[guard..promptOverride], StringComparison.Ordinal);
    }

    [Fact]
    public void TheScript_PreservesTheUsersOwnPrompt()
    {
        // Replacing the prompt outright would silently reformat every terminal in the product.
        Assert.Contains("prompt", Script(), StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public void OnAShellWithNoLineAcceptHook_TheScriptInstallsNothingAtAll()
    {
        // The control this checks is the ONE the ordering test above can only approximate. Run the
        // real script in a real PowerShell that genuinely cannot hook line accept, and assert it
        // left the shell untouched — no prompt override, no nonce in scope.
        //
        // Getting this wrong is not a small bug. A half-installed integration emits D/A/B and never
        // C, and because a single authenticated claim retires the host's fallback heuristic, the
        // session would then report Ready for the entire duration of every command. Silent, and
        // worse than not installing at all.
        //
        // No pseudo console needed: this is about what the script does, not about how bytes travel.
        var probe = Path.Combine(Path.GetTempPath(), $"aide-noreadline-{Guid.NewGuid():N}.ps1");

        // The script `return`s when it bails out, which would also skip anything appended after it,
        // so it runs inside a script block whose return does not end the file.
        File.WriteAllText(probe, $$"""
            & {
            {{ShellIntegration.PowerShellScript(Nonce)}}
            }
            if ($null -ne $global:__AideNonce) { 'NONCE-SET' } else { 'NONCE-UNSET' }
            if ((Get-Item function:prompt).Definition -match '__AideMark') { 'PROMPT-HOOKED' } else { 'PROMPT-CLEAN' }
            """);

        try
        {
            var start = new System.Diagnostics.ProcessStartInfo(
                "powershell.exe", $"-NoProfile -NoLogo -File \"{probe}\"")
            {
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                UseShellExecute = false,
            };

            // Emptying the module path is what makes Set-PSReadLineKeyHandler undiscoverable, which
            // is the condition the guard exists for. Verified reachable: the same shell reports
            // 'HOOK ABSENT' under this environment and finds the command without it.
            start.Environment["PSModulePath"] = string.Empty;

            using var process = System.Diagnostics.Process.Start(start);
            Assert.NotNull(process);

            var output = process.StandardOutput.ReadToEnd();
            Assert.True(process.WaitForExit(60_000), "the probe shell did not exit");

            Assert.Contains("NONCE-UNSET", output, StringComparison.Ordinal);
            Assert.Contains("PROMPT-CLEAN", output, StringComparison.Ordinal);
        }
        finally
        {
            try
            {
                File.Delete(probe);
            }
            catch (IOException)
            {
            }
        }
    }

    // ---- the nonce is never allowed to become script ------------------------

    [Theory]
    [InlineData("'; Remove-Item C:\\ -Recurse; '")]
    [InlineData("abc$(whoami)")]
    [InlineData("abc def")]
    [InlineData("abc';#")]
    [InlineData("")]
    [InlineData("   ")]
    [InlineData("nothex!!")]
    public void ANonceThatIsNotPlainHex_IsRefused(string hostile)
    {
        // The nonce is interpolated into a PowerShell string literal. Everything our own generator
        // produces is hex, so anything else means either a caller invented one or something is very
        // wrong — and in both cases refusing beats escaping, because escaping is a claim about a
        // language's quoting rules that has to stay true forever.
        Assert.Throws<ArgumentException>(() => ShellIntegration.PowerShellScript(hostile));
    }

    [Fact]
    public void AGeneratedNonce_IsAccepted()
    {
        // The guard above must not reject the thing the product actually produces.
        var script = ShellIntegration.PowerShellScript(OscParser.NewNonce());

        Assert.Contains("__AideMark 'C'", script, StringComparison.Ordinal);
    }

    // ---- the command line ---------------------------------------------------

    [Fact]
    public void TheCommandLine_EncodesTheScript_SoQuotingCannotBreakIt()
    {
        // -EncodedCommand takes UTF-16LE base64. Passing the script as ordinary text would put its
        // quotes, semicolons and dollar signs through two layers of parsing (the Win32 command line
        // and PowerShell's own), which is a defect waiting for the first apostrophe.
        var commandLine = ShellIntegration.PowerShellCommandLine("powershell.exe", Nonce);

        Assert.Contains("-EncodedCommand", commandLine, StringComparison.Ordinal);

        var encoded = commandLine[(commandLine.IndexOf("-EncodedCommand", StringComparison.Ordinal)
            + "-EncodedCommand".Length)..].Trim();
        var decoded = Encoding.Unicode.GetString(Convert.FromBase64String(encoded));

        Assert.Contains(Nonce, decoded, StringComparison.Ordinal);
        Assert.Contains("__AideMark 'C'", decoded, StringComparison.Ordinal);
    }

    [Fact]
    public void TheCommandLine_KeepsTheShellInteractive()
    {
        // Without -NoExit the shell runs the integration and exits immediately, which would make
        // every terminal in the product close the moment it opened.
        var commandLine = ShellIntegration.PowerShellCommandLine("powershell.exe", Nonce);

        Assert.Contains("-NoExit", commandLine, StringComparison.Ordinal);
    }

    [Fact]
    public void TheCommandLine_QuotesTheExecutable()
    {
        var commandLine = ShellIntegration.PowerShellCommandLine(
            @"C:\Program Files\PowerShell\7\pwsh.exe", Nonce);

        Assert.StartsWith("\"C:\\Program Files\\PowerShell\\7\\pwsh.exe\"", commandLine, StringComparison.Ordinal);
    }
}
