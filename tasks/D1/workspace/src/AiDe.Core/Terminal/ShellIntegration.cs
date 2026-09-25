using System.Text;

namespace AiDe.Core.Terminal;

/// <summary>
/// Builds the shell-side half of the OSC contract: the script that reports session state, signed
/// with the session nonce.
/// </summary>
/// <remarks>
/// <para><b>Why the product ships this rather than asking users to install it.</b> The nonce is
/// generated per session and lives only in memory, so no script a user commits to their profile can
/// ever carry it. The integration has to be composed at session start, by us, from that session's
/// own secret — which is also what makes the control meaningful: the script is the one thing in the
/// world that knows the nonce, so a claim carrying it came from the shell we started.</para>
///
/// <para><b>All of the loop, or none of it.</b> The parser makes OSC authoritative on the first
/// authenticated claim, retiring the output heuristic. An integration that marked the prompt
/// (<c>D</c>, <c>A</c>, <c>B</c>) but not command start (<c>C</c>) would therefore pin the session at
/// <c>Ready</c> for the whole duration of every command — a confident wrong answer, and strictly
/// worse than the coarse signal it replaced. So the script checks it can hook line-accept
/// <b>before</b> it overrides anything, and returns without installing if it cannot. A session with
/// no integration is a supported outcome; a session with half of one is not.</para>
///
/// <para><b>Scope.</b> PowerShell only. It is the shell the product launches by default and the one
/// with a supported line-accept hook. <c>cmd.exe</c> has no equivalent — its prompt is a string, not
/// a function, and there is nowhere to run code when a command starts — so a cmd session keeps the
/// heuristic rather than getting a half-loop.</para>
/// </remarks>
public static class ShellIntegration
{
    /// <summary>
    /// The integration script for one session.
    /// </summary>
    /// <param name="nonce">
    /// This session's <see cref="OscParser"/> nonce. Must be plain lowercase hex.
    /// </param>
    /// <exception cref="ArgumentException">The nonce is not plain hex.</exception>
    public static string PowerShellScript(string nonce)
    {
        RequireHex(nonce);

        // Single-quoted PowerShell literals throughout: they interpolate nothing, so even if the hex
        // guard above were somehow bypassed there is no expansion for a payload to ride.
        return $$"""
            # AI-DE shell integration. Reports session state as OSC 133, signed with this session's
            # nonce so a claim from anything else in the terminal is not believed.

            $global:__AideNonce = '{{nonce}}'

            # Install only if the whole loop can be reported. Marking the prompt without marking
            # command start would leave the session claiming Ready for the length of every command,
            # because an authenticated claim retires the host's fallback heuristic.
            if (-not (Get-Command Set-PSReadLineKeyHandler -ErrorAction SilentlyContinue)) {
                Remove-Variable -Name __AideNonce -Scope Global -ErrorAction SilentlyContinue
                return
            }

            function global:__AideMark([string] $body) {
                # Written straight to the console rather than the pipeline: this is terminal
                # signalling, not output, and must never land in a variable or a redirect.
                [Console]::Write("$([char]27)]133;$body;nonce=$global:__AideNonce$([char]27)\")
            }

            $global:__AidePrompt = $function:prompt

            function global:prompt {
                # Captured on the first line: both reflect the command that just finished, and any
                # statement here would overwrite them.
                $ok = $?
                $native = $global:LASTEXITCODE

                $code = if ($null -ne $native) { $native } elseif ($ok) { 0 } else { 1 }

                # D carries the finished command's exit code; A says a prompt is being drawn.
                # For STATE they are currently redundant — both mean Ready, and deleting either one
                # changes no session's reported activity. D is kept because the exit code is the
                # only place a command's success is reported at all, and dropping the standard
                # marker to save a write would have to be undone the moment anything consumes it.
                __AideMark "D;$code"
                __AideMark 'A'

                # The user's own prompt is preserved. Replacing it would silently reformat every
                # terminal the product opens.
                $text = if ($null -ne $global:__AidePrompt) { & $global:__AidePrompt } else { "PS $($ExecutionContext.SessionState.Path.CurrentLocation)> " }

                __AideMark 'B'

                # Restored so the next prompt reports the user's command, not our bookkeeping.
                $global:LASTEXITCODE = $native
                return $text
            }

            Set-PSReadLineKeyHandler -Chord Enter -BriefDescription 'AideAcceptLine' -LongDescription 'Marks command start for AI-DE, then accepts the line.' -ScriptBlock {
                # AcceptLine first: it ends PSReadLine's own rendering, so our write cannot land in
                # the middle of a repaint. The command itself does not start until this handler
                # returns, so C still precedes every byte of its output.
                [Microsoft.PowerShell.PSConsoleReadLine]::AcceptLine()
                __AideMark 'C'
            }
            """;
    }

    /// <summary>
    /// A command line that launches <paramref name="executablePath"/> with the integration
    /// installed and the shell left interactive.
    /// </summary>
    /// <remarks>
    /// The script travels as <c>-EncodedCommand</c> (UTF-16LE base64) rather than as text. Passing
    /// it literally would put its quotes, semicolons and <c>$</c> through two parsers — the Win32
    /// command line and PowerShell's own — and the first apostrophe in a user's prompt would break
    /// it. Base64 has no metacharacters, so there is nothing to escape and nothing to get wrong.
    /// </remarks>
    public static string PowerShellCommandLine(string executablePath, string nonce)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(executablePath);

        var encoded = Convert.ToBase64String(Encoding.Unicode.GetBytes(PowerShellScript(nonce)));

        // THE PROFILE IS LOADED. It was suppressed for determinism, and that was the wrong trade for
        // a developer tool: a profile is where PATH additions, aliases and tool shims live, so
        // -NoProfile produced a terminal in which the user's own tools were not on PATH. A terminal
        // that does not behave like the user's terminal is not a terminal they can work in.
        //
        // The determinism concern is met by ORDER rather than by suppression. The profile runs
        // first, then this -EncodedCommand, and the script captures whatever prompt it finds and
        // wraps it — so the user keeps their prompt and the integration still marks the whole loop.
        // A profile that fails or prints a banner is cosmetic; a profile that redefines prompt
        // cannot win, because it has already run by the time this installs.
        return $"\"{executablePath}\" -NoLogo -NoExit -EncodedCommand {encoded}";
    }

    /// <summary>
    /// A command line that runs <paramref name="agent"/> INSIDE the user's login shell.
    /// </summary>
    /// <remarks>
    /// <para><b>An agent used to be launched directly, and that was the defect.</b> Reported as
    /// "the agent sessions do not have my profile or my environment variables", and the measurement
    /// found something sharper than a missing profile: a child that is a <c>.cmd</c> or <c>.bat</c>
    /// shim — which is what every npm-installed CLI is — starts through <c>cmd.exe</c>, and
    /// <b>cmd drops any environment variable past its own limit</b>. This machine's PATH is 22,297
    /// characters, so a cmd-hosted agent starts with an <b>empty PATH</b> and cannot find node, git
    /// or anything else. Measured: a cmd child through this ConPTY reported
    /// <c>PATH=[]</c> while PowerShell started from the same inherited block reported all 22,297
    /// characters and resolved <c>claude</c>.</para>
    ///
    /// <para><b>So the agent runs where the user's own commands run.</b> The login shell loads the
    /// profile — the aliases, functions and variables the request was actually about — resolves
    /// PATHEXT so a <c>.cmd</c> or <c>.ps1</c> shim works, and handles a long PATH correctly
    /// because it is not cmd. The agent becomes exactly what typing its name in their terminal
    /// does, which is the only definition of "works with my profile" that holds up.</para>
    ///
    /// <para>The agent's name is passed as a single-quoted PowerShell string with internal quotes
    /// doubled, and invoked with <c>&amp;</c>. A name is not a command line here: quoting it means a
    /// path with a space runs, and a name with an apostrophe cannot end the string early.</para>
    /// </remarks>
    public static string AgentCommandLine(string shellPath, string agent, string nonce)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(shellPath);
        ArgumentException.ThrowIfNullOrWhiteSpace(agent);

        var quoted = "'" + agent.Replace("'", "''", StringComparison.Ordinal) + "'";

        // THE INTEGRATION RUNS IN ITS OWN SCOPE, and that is the whole point of the `& { }`.
        //
        // The integration script gives up with a bare `return` when it cannot install the full
        // report loop. At the top level of an -EncodedCommand script that `return` ends the SCRIPT,
        // so an agent invocation appended after it never ran — and -NoExit then left a working
        // PowerShell prompt, which looks exactly like a terminal that was asked for.
        //
        // OBSERVED, in the product: PowerShell inside this ConPTY prints "PowerShell detected that
        // you might be using a screen reader and has disabled PSReadLine for compatibility
        // purposes", so `Set-PSReadLineKeyHandler` is genuinely absent and the guard fires EVERY
        // TIME. Opening a Claude Code session produced a plain shell at the workspace root while the
        // status bar said "Claude Code session opened".
        //
        // The same test run from an ordinary console finds PSReadLine present and the bug invisible,
        // which is why this needs the scope rather than a fixed guard: the integration is allowed to
        // decline, and declining must never be able to cancel the agent.
        var script =
            "& {" + Environment.NewLine
            + PowerShellScript(nonce) + Environment.NewLine
            + "}" + Environment.NewLine
            + "& " + quoted;
        var encoded = Convert.ToBase64String(Encoding.Unicode.GetBytes(script));

        return $"\"{shellPath}\" -NoLogo -NoExit -EncodedCommand {encoded}";
    }

    /// <summary>
    /// Refuses anything that is not plain hex.
    /// </summary>
    /// <remarks>
    /// The nonce is interpolated into a script. Every value our own generator produces is hex, so a
    /// non-hex value means a caller invented one — and refusing beats escaping, because an escaping
    /// routine is a standing claim about PowerShell's quoting rules that has to remain true for as
    /// long as the product ships.
    /// </remarks>
    private static void RequireHex(string nonce)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(nonce);

        foreach (var c in nonce)
        {
            if (!char.IsAsciiHexDigit(c))
            {
                throw new ArgumentException(
                    "the session nonce must be plain hex; it is interpolated into a script and is "
                    + "refused rather than escaped.",
                    nameof(nonce));
            }
        }
    }
}
