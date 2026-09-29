using AiDe.Core.Dispatch;
using AiDe.Core.Terminal;

namespace AiDe.Core.Tests;

/// <summary>
/// The rules that decide which of several competing signals owns <see cref="SessionActivity"/>.
/// </summary>
/// <remarks>
/// <para>Before shell integration existed, the runtime had exactly one signal — "bytes arrived, so
/// the process must be working" — and <see cref="SessionActivity.Ready"/> was a declared state that
/// nothing ever produced. Adding OSC gives a second, better signal, and the interesting question is
/// no longer how to read either one but which wins when they disagree.</para>
///
/// <para>They disagree constantly. A shell that has finished a command prints its prompt, which is
/// output, which the heuristic reads as "busy" — so a session with working integration would flip
/// straight back out of the <c>Ready</c> the shell just told us about. That is why the first
/// authenticated claim makes OSC <b>authoritative</b> for the rest of the session: not as an
/// optimisation, but because otherwise the two signals fight and the coarser one wins the last
/// word.</para>
///
/// <para>These rules live apart from the ConPTY session so they can be tested without a pseudo
/// console — the read loop that applies them needs a real console and a real child process
/// (<b>DC-014</b>), which is far too much apparatus for asserting a state transition.</para>
/// </remarks>
public sealed class TerminalActivityStateTests
{
    [Fact]
    public void ANewSession_IsStarting()
    {
        Assert.Equal(SessionActivity.Starting, new TerminalActivityState().Current);
    }

    // ---- the heuristic, for sessions with no shell integration -------------

    [Fact]
    public void WithNoOscClaim_OutputMeansBusy()
    {
        var state = new TerminalActivityState();

        state.OnOutput();

        Assert.Equal(SessionActivity.Busy, state.Current);
        Assert.False(state.OscAuthoritative);
    }

    [Fact]
    public void WithNoOscClaim_OverloadReplacesBusy()
    {
        var state = new TerminalActivityState();
        state.OnOutput();

        state.OnOverload();

        Assert.Equal(SessionActivity.OutputOverload, state.Current);
    }

    [Fact]
    public void WithNoOscClaim_OutputDoesNotClearAnOverload()
    {
        // Overload is a resource condition, and more output is the thing that caused it. Letting the
        // next chunk clear it would make the state flicker exactly when it matters most.
        var state = new TerminalActivityState();
        state.OnOverload();

        state.OnOutput();

        Assert.Equal(SessionActivity.OutputOverload, state.Current);
    }

    // ---- an authenticated claim takes over ---------------------------------

    [Fact]
    public void AnOscClaim_MakesOscAuthoritative()
    {
        var state = new TerminalActivityState();

        state.OnOscClaim(SessionActivity.Ready);

        Assert.Equal(SessionActivity.Ready, state.Current);
        Assert.True(state.OscAuthoritative);
    }

    [Fact]
    public void OnceAuthoritative_OutputNoLongerForcesBusy()
    {
        // This is the whole point: the shell prints its prompt after telling us it is done, and that
        // prompt must not undo what it just said.
        var state = new TerminalActivityState();
        state.OnOscClaim(SessionActivity.Ready);

        state.OnOutput();

        Assert.Equal(SessionActivity.Ready, state.Current);
    }

    [Fact]
    public void OnceAuthoritative_AClaimOfBusyIsStillHonoured()
    {
        var state = new TerminalActivityState();
        state.OnOscClaim(SessionActivity.Ready);

        state.OnOscClaim(SessionActivity.Busy);

        Assert.Equal(SessionActivity.Busy, state.Current);
    }

    [Fact]
    public void AnOscClaim_ClearsAnOverload()
    {
        // Unlike raw output, an authenticated claim is the shell saying the flood is over.
        var state = new TerminalActivityState();
        state.OnOverload();

        state.OnOscClaim(SessionActivity.Ready);

        Assert.Equal(SessionActivity.Ready, state.Current);
    }

    [Fact]
    public void OverloadStillApplies_AfterOscBecameAuthoritative()
    {
        // Integration tells us what the shell believes; it cannot tell us we stopped dropping bytes.
        var state = new TerminalActivityState();
        state.OnOscClaim(SessionActivity.Ready);

        state.OnOverload();

        Assert.Equal(SessionActivity.OutputOverload, state.Current);
    }

    // ---- Ended is final ----------------------------------------------------

    [Fact]
    public void Ended_IsTerminal_AgainstOutput()
    {
        var state = new TerminalActivityState();
        state.OnEnded();

        state.OnOutput();

        Assert.Equal(SessionActivity.Ended, state.Current);
    }

    [Fact]
    public void Ended_IsTerminal_AgainstAnOscClaim()
    {
        // A dead process cannot be Ready, whatever the last bytes in the pipe claimed. Buffered
        // output outliving the process is ordinary, so this ordering is reached in normal use.
        var state = new TerminalActivityState();
        state.OnEnded();

        state.OnOscClaim(SessionActivity.Ready);

        Assert.Equal(SessionActivity.Ended, state.Current);
    }

    [Fact]
    public void Ended_IsTerminal_AgainstOverload()
    {
        var state = new TerminalActivityState();
        state.OnEnded();

        state.OnOverload();

        Assert.Equal(SessionActivity.Ended, state.Current);
    }
}
