using AiDe.Core.Presentation.Sessions;

namespace AiDe.Core.Tests.Sessions.Thread;

/// <summary>
/// <b>Ruling 95 (Wait) — the read model's half.</b> A queued turn is one turn of the append-only
/// stream: it takes the next ordinal, carries exactly the bytes that will be sent, starts only by
/// <see cref="RunChannelSessionThread.Start"/> (the drain, or <i>Send now</i>), ends only by
/// cancellation, and there is exactly one. The snapshot derives who it waits behind and whether it
/// waits on the operator — never a member.
/// </summary>
/// <remarks>
/// <b>Red observed</b>: against the base (<c>c831113e</c>) this file does not compile —
/// <c>CS0117: 'TurnState' does not contain a definition for 'Queued'</c> (and <c>Cancelled</c>,
/// <c>Enqueue</c>, <c>Start</c>, <c>Queued</c>, <c>QueuedAwaitsYou</c>) — the model had no queue at
/// all, which is what Ruling 77(b) froze out of Phase 1.
/// </remarks>
public sealed class TheQueuedTurnIsOneTurnOfTheStreamTests
{
    private static readonly DateTimeOffset T0 = new(2026, 9, 14, 18, 0, 0, TimeSpan.Zero);

    private static IReadOnlyList<DecorationRow> Decorations =>
        [new("class", "free-form", "session-default", ""), new("tier", "T0", "rule", ""), new("shape", "message", "projection", "")];

    private static RunChannelSessionThread WithB1Running()
    {
        var thread = new RunChannelSessionThread();
        thread.Accept("b1's words", Decorations, "b1 bytes", T0);
        return thread;
    }

    [Fact]
    public void AQueuedTurn_TakesTheNextOrdinal_CarriesItsBytes_AndIsNeitherInFlightNorTerminal()
    {
        var thread = WithB1Running();
        var b2 = thread.Enqueue("b2's words", Decorations, "b2 bytes", T0.AddSeconds(5), "env-2", new Spend(100, 0, 20, 1));

        Assert.Equal(2, b2);
        var snapshot = thread.Current;
        var queued = Assert.Single(snapshot.Turns, t => t.State == TurnState.Queued);
        Assert.Equal("b2 bytes", queued.SentBytes);
        Assert.Equal("env-2", queued.EnvelopeId);
        Assert.Null(queued.Outcome);
        Assert.Null(queued.Waiting);
        Assert.False(TurnView.IsTerminal(queued.State));

        // Derived, never a member: the queued turn, who it waits behind, and that it is not waiting on you.
        Assert.Same(queued, snapshot.Queued);
        Assert.Equal(1, snapshot.InFlight!.Ordinal);
        Assert.Equal(1, snapshot.QueuedBehind!.Ordinal);
        Assert.False(snapshot.QueuedAwaitsYou);
        Assert.Equal("b2 queued — sends after b1", TurnCopy.QueuedSentence(snapshot));
        Assert.Equal("queued", TurnCopy.OutcomeWord(queued));
    }

    [Fact]
    public void ExactlyOneQueuedTurn_ASecondEnqueueIsRefusedNamingTheFirst()
    {
        var thread = WithB1Running();
        thread.Enqueue("b2", Decorations, "b2 bytes", T0.AddSeconds(5));

        var refusal = Assert.Throws<InvalidOperationException>(() => thread.Enqueue("b3", Decorations, "b3 bytes", T0.AddSeconds(6)));
        Assert.StartsWith("turn b2 is queued; cancel it or wait", refusal.Message, StringComparison.Ordinal);
        Assert.Equal(2, thread.Current.Turns.Count);
    }

    [Fact]
    public void Start_MovesQueuedToRunning_AndTheDurationCountsFromTheSend_NeverFromTheQueue()
    {
        var thread = WithB1Running();
        var b2 = thread.Enqueue("b2", Decorations, "b2 bytes", T0.AddSeconds(5));
        thread.Conclude(1, TurnState.Completed, T0.AddSeconds(30));

        thread.Start(b2, T0.AddSeconds(30));
        Assert.Equal(TurnState.Running, thread.Current.Turns[1].State);
        Assert.Null(thread.Current.Queued);
        Assert.Equal(2, thread.Current.InFlight!.Ordinal);

        thread.Conclude(b2, TurnState.Answered, T0.AddSeconds(33));
        Assert.Equal(TimeSpan.FromSeconds(3), thread.Current.Turns[1].Outcome!.Duration);

        // Only a queued turn starts.
        Assert.Throws<InvalidOperationException>(() => thread.Start(b2, T0.AddSeconds(40)));
        Assert.Throws<InvalidOperationException>(() => thread.Start(1, T0.AddSeconds(40)));
    }

    [Fact]
    public void AQueuedTurnEndsOnlyByCancellation_AndARunningTurnIsNeverCancelled()
    {
        var thread = WithB1Running();
        var b2 = thread.Enqueue("b2", Decorations, "b2 bytes", T0.AddSeconds(5));

        // A queued turn cannot complete, stop or fail — it never ran.
        Assert.Throws<InvalidOperationException>(() => thread.Conclude(b2, TurnState.Completed, T0.AddSeconds(6)));
        Assert.Throws<InvalidOperationException>(() => thread.Conclude(b2, TurnState.Stopped, T0.AddSeconds(6)));
        // A running turn is stopped or failed, never "cancelled" (two words, two facts).
        Assert.Throws<InvalidOperationException>(() => thread.Conclude(1, TurnState.Cancelled, T0.AddSeconds(6)));
        // A queued turn has no run to wait on or resume.
        Assert.Throws<InvalidOperationException>(() => thread.Wait(b2, new WaitingRequest("r", "permission", "?", [TurnActionKind.Deny])));
        Assert.Throws<InvalidOperationException>(() => thread.Resume(b2));

        thread.Conclude(b2, TurnState.Cancelled, T0.AddSeconds(7));
        var cancelled = thread.Current.Turns[1];
        Assert.Equal(TurnState.Cancelled, cancelled.State);
        Assert.True(TurnView.IsTerminal(cancelled.State));
        Assert.NotNull(cancelled.Outcome);
        Assert.Equal("cancelled by you", TurnCopy.OutcomeWord(cancelled));
        Assert.Equal(["never sent"], TurnCopy.Counts(cancelled));
        Assert.Equal("Cancelled before it was sent; its words went back to the editor.", TurnCopy.ReasonSentence(cancelled));

        // The stream is append-only: the row stays, the next turn is b3, and a new Wait may queue again.
        Assert.Null(thread.Current.Queued);
        Assert.Equal(3, thread.Enqueue("b3", Decorations, "b3 bytes", T0.AddSeconds(8)));
        Assert.Equal(1, thread.Current.QueuedBehind!.Ordinal);
    }

    [Theory]
    [InlineData(TurnState.Stopped)]
    [InlineData(TurnState.Failed)]
    public void AfterAStopOrAFailure_TheQueuedTurnWaitsOnYou(TurnState ending)
    {
        var thread = WithB1Running();
        thread.Enqueue("b2", Decorations, "b2 bytes", T0.AddSeconds(5));
        thread.Conclude(1, ending, T0.AddSeconds(10), exitCode: ending == TurnState.Failed ? 1 : null, edits: 0);

        var snapshot = thread.Current;
        Assert.Null(snapshot.InFlight);
        Assert.Equal(1, snapshot.QueuedBehind!.Ordinal);
        Assert.True(snapshot.QueuedAwaitsYou);
        Assert.Equal(
            ending == TurnState.Failed
                ? "b1 lane exited 1; b2 is waiting — Send it or cancel it"
                : "b1 stopped by you; b2 is waiting — Send it or cancel it",
            TurnCopy.QueuedSentence(snapshot));
    }

    [Theory]
    [InlineData(TurnState.Completed)]
    [InlineData(TurnState.Answered)]
    public void AfterCompletedOrAnswered_TheQueuedTurnNeverReadsAsWaitingOnYou(TurnState ending)
    {
        // The instant between b1's conclusion and the drain's Start: derived from the turns, so the
        // row never flashes "Send now" for a turn the drain is about to send.
        var thread = WithB1Running();
        thread.Enqueue("b2", Decorations, "b2 bytes", T0.AddSeconds(5));
        thread.Conclude(1, ending, T0.AddSeconds(10));

        Assert.Null(thread.Current.InFlight);
        Assert.NotNull(thread.Current.Queued);
        Assert.False(thread.Current.QueuedAwaitsYou);
        Assert.Equal("b2 queued — sends after b1", TurnCopy.QueuedSentence(thread.Current));
    }

    [Fact]
    public void TheQueuedTurnsCompileSpend_IsSeededOnItsOwnTurn_NeverOnTheOneInFlight()
    {
        // Ruling 78 / Ruling 95 condition 4: the compile's called.cost is the queued turn's spend.
        var thread = WithB1Running();
        var b2 = thread.Enqueue("b2", Decorations, "b2 bytes", T0.AddSeconds(5), compileSpend: new Spend(100, 0, 20, 1));
        thread.Conclude(1, TurnState.Answered, T0.AddSeconds(10));
        Assert.Null(thread.Current.Turns[0].Outcome!.Spend);

        thread.Start(b2, T0.AddSeconds(10));
        thread.Append(b2, new EventLine(T0.AddSeconds(11), "claude-code", "acp.result", "ok", "run"), new Spend(4, 54_542, 182, 1));
        thread.Conclude(b2, TurnState.Answered, T0.AddSeconds(12));

        var spend = thread.Current.Turns[1].Outcome!.Spend;
        Assert.NotNull(spend);
        Assert.Equal(new Spend(104, 54_542, 202, 2), spend);
        Assert.Contains("306 tokens", TurnCopy.Counts(thread.Current.Turns[1]));
    }

    [Fact]
    public void ThePolicy_AnnouncesQueued_ThenAcceptedAtTheDrain_AndCancelledAsAborted()
    {
        var policy = new ThreadAnnouncementPolicy();
        var thread = WithB1Running();
        var announced = new List<Announcement>();
        thread.Changed += snapshot => announced.AddRange(policy.Next(snapshot));
        _ = policy.Next(thread.Current);

        var b2 = thread.Enqueue("b2", Decorations, "b2 bytes", T0.AddSeconds(5));
        var queued = Assert.Single(announced);
        Assert.Equal("Turn b2 queued; it sends after the turn in flight.", queued.Text);
        Assert.Equal(AnnouncementKind.ItemAdded, queued.Kind);
        Assert.Equal("new→queued", queued.Transition);

        announced.Clear();
        thread.Conclude(1, TurnState.Completed, T0.AddSeconds(10));
        thread.Start(b2, T0.AddSeconds(10));
        var accepted = announced.Last();
        Assert.Equal("Turn b2 accepted as a message, tier T0, class free-form.", accepted.Text);
        Assert.Equal("queued→running", accepted.Transition);

        announced.Clear();
        var b3 = thread.Enqueue("b3", Decorations, "b3 bytes", T0.AddSeconds(11));
        announced.Clear();
        thread.Conclude(b3, TurnState.Cancelled, T0.AddSeconds(12));
        var cancelled = Assert.Single(announced);
        Assert.Equal("Turn b3 cancelled before it was sent; its words went back to the editor.", cancelled.Text);
        Assert.Equal(AnnouncementKind.Aborted, cancelled.Kind);
        Assert.Equal("queued→cancelled", cancelled.Transition);

        Assert.Equal("Cancel", ThreadAnnouncementPolicy.ActionWord(TurnActionKind.Cancel));
        Assert.Equal("Send now", ThreadAnnouncementPolicy.ActionWord(TurnActionKind.SendNow));
    }
}
