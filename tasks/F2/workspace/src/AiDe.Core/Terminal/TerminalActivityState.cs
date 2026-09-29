using AiDe.Core.Dispatch;

namespace AiDe.Core.Terminal;

/// <summary>
/// Decides which of the session's competing signals owns <see cref="SessionActivity"/>.
/// </summary>
/// <remarks>
/// <para>There are three signals and they routinely disagree. <b>Output arriving</b> is a coarse
/// heuristic — bytes appeared, so something is presumably working. <b>An authenticated OSC claim</b>
/// is the shell itself reporting what it is doing. <b>Overload</b> is our own resource state.</para>
///
/// <para>The heuristic and OSC conflict directly: a shell that finishes a command prints its prompt,
/// and that prompt is output, so the heuristic would immediately flip the session out of the
/// <c>Ready</c> the shell just announced. Whichever signal is applied last wins, which would make the
/// coarser one authoritative by accident. So the <b>first authenticated claim makes OSC
/// authoritative</b> for the rest of the session, and the heuristic retires — it exists to serve
/// sessions with no shell integration, and a session that has produced one nonced claim has it.</para>
///
/// <para>Overload outranks both, because neither the shell nor a byte count can tell us we have
/// stopped dropping output — only we know that. <see cref="SessionActivity.Ended"/> outranks
/// everything: a dead process is not <c>Ready</c>, whatever the last bytes in the pipe claimed, and
/// output outliving the process that wrote it is ordinary rather than exotic.</para>
///
/// <para>Not thread-safe by design: the ConPTY session already serialises state under its own lock,
/// and a second lock inside here would be a redundant one to reason about.</para>
/// </remarks>
public sealed class TerminalActivityState
{
    private SessionActivity _current = SessionActivity.Starting;

    /// <summary>The state the session should report right now.</summary>
    public SessionActivity Current => _current;

    /// <summary>
    /// Has an authenticated OSC claim arrived? Once true the output heuristic no longer applies.
    /// </summary>
    public bool OscAuthoritative { get; private set; }

    /// <summary>Output arrived. The fallback signal, for sessions with no shell integration.</summary>
    public void OnOutput()
    {
        if (OscAuthoritative || _current is SessionActivity.Ended or SessionActivity.OutputOverload)
        {
            return;
        }

        _current = SessionActivity.Busy;
    }

    /// <summary>An OSC claim that carried the session nonce. Advisory, never agent acceptance.</summary>
    public void OnOscClaim(SessionActivity claimed)
    {
        if (_current == SessionActivity.Ended)
        {
            return;
        }

        // Authoritative even if the claim changes nothing: what matters is that integration is
        // present, which is what retires the heuristic.
        OscAuthoritative = true;
        _current = claimed;
    }

    /// <summary>Output is being dropped to stay inside the buffer budget.</summary>
    public void OnOverload()
    {
        if (_current == SessionActivity.Ended)
        {
            return;
        }

        _current = SessionActivity.OutputOverload;
    }

    /// <summary>The process ended. Final.</summary>
    public void OnEnded() => _current = SessionActivity.Ended;
}
