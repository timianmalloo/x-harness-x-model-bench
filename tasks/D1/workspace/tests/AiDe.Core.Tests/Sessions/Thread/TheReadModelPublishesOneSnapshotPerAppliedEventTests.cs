using AiDe.Core.Presentation.Sessions;

namespace AiDe.Core.Tests.Sessions.Thread;

/// <summary>
/// DS-1 <b>M4</b> (the D7 pairing row; R1 is CV-2's twin on the envelope projection) — the
/// run-channel read model raises <c>Changed</c> exactly once per applied event after catch-up, the
/// k-th snapshot's <c>Turns</c> is the fold of the first k events and its <c>Version</c> is k; a
/// snapshot before catch-up is not caught up; a pre-loaded fixture's first snapshot is. Plus
/// <b>M2</b>: absent usage reads <i>not recorded</i>, never 0, and the header's spend is the sum.
/// </summary>
public sealed class TheReadModelPublishesOneSnapshotPerAppliedEventTests
{
    private static readonly DateTimeOffset T0 = new(2026, 9, 12, 14, 0, 0, TimeSpan.Zero);

    private static IReadOnlyList<DecorationRow> Decorations =>
        [new("class", "free-form", "session-default", ""), new("tier", "T1", "rule", ""), new("lease", "src/**", "derived", ""), new("shape", "goal block", "projection", "")];

    private static EventLine Line(int i) => new(T0.AddSeconds(i), "claude-code", i % 3 == 0 ? Coalesce.MessageKind : "tool.call", $"line {i}", "run");

    [Fact]
    public void ApplyingNEventsAfterCatchUpRaisesExactlyNTimes_AndTheKthSnapshotIsTheFold()
    {
        var thread = new RunChannelSessionThread();
        var raised = new List<ThreadSnapshot>();
        thread.Changed += raised.Add;

        var ordinal = thread.Accept("Refactor the chain", Decorations, "bytes", T0);
        for (var i = 1; i <= 10; i++)
        {
            thread.Append(ordinal, Line(i), i == 5 ? new Spend(100, 10, 20, 1) : null);
        }

        thread.Conclude(ordinal, TurnState.Completed, T0.AddSeconds(30));

        // 1 accept + 10 lines + 1 conclude = 12 applied events → 12 raises, versions 1..12.
        Assert.Equal(12, raised.Count);
        Assert.Equal(Enumerable.Range(1, 12).Select(i => (long)i), raised.Select(s => s.Version));
        Assert.All(raised, s => Assert.True(s.IsCaughtUp));

        // The k-th snapshot is the fold of the first k events: after accept + k lines, k lines.
        for (var k = 1; k <= 10; k++)
        {
            Assert.Equal(k, raised[k].Turns[0].Events.Count);
            Assert.Equal(TurnState.Running, raised[k].Turns[0].State);
        }

        // Each snapshot is immutable: the first one still shows an empty turn after everything.
        Assert.Empty(raised[0].Turns[0].Events);

        var last = raised[^1].Turns[0];
        Assert.Equal(TurnState.Completed, last.State);
        Assert.Equal(10, last.Outcome!.EventCount);
        Assert.Equal(new Spend(100, 10, 20, 1), last.Outcome.Spend);
        Assert.Equal(TimeSpan.FromSeconds(30), last.Outcome.Duration);
        // The fold: every agent.msg line here is its own run (a tool.call sits between each pair), so
        // the rows are the events one to one, the message rows carrying their text and a count of 1.
        Assert.Equal(Coalesce.Rows(last.Events), last.Rows);
        Assert.Equal(["line 3", "line 6", "line 9"], last.Rows.Where(r => r.Kind == Coalesce.MessageKind).Select(r => r.Text));
        Assert.Same(raised[^1], thread.Current);
    }

    [Fact]
    public void ASnapshotBeforeCatchUpIsNotCaughtUp_AndCatchUpPublishesVersionZero()
    {
        var thread = new RunChannelSessionThread(caughtUp: false);
        var raised = new List<ThreadSnapshot>();
        thread.Changed += raised.Add;

        Assert.False(thread.Current.IsCaughtUp);

        var ordinal = thread.Accept("history", Decorations, "bytes", T0);
        thread.Conclude(ordinal, TurnState.Completed, T0.AddSeconds(5));

        Assert.All(raised, s => Assert.False(s.IsCaughtUp));
        Assert.All(raised, s => Assert.Equal(0, s.Version));

        thread.CatchUp();

        Assert.True(raised[^1].IsCaughtUp);
        Assert.Equal(0, raised[^1].Version);
        Assert.Single(raised[^1].Turns);

        var live = thread.Accept("live", Decorations, "bytes", T0.AddMinutes(1));
        Assert.Equal(2, live);
        Assert.Equal(1, raised[^1].Version);
    }

    [Fact]
    public void APreloadedFixturesFirstSnapshotIsCaughtUpAtVersionZero()
    {
        var turns = Enumerable.Range(1, 5).Select(i => new TurnView(
            i, $"env-{i}", $"words {i}", Decorations, TurnState.Completed,
            new OutcomeView("claude-code", null, 1, new Spend(1000, 0, 240, 1), TimeSpan.FromSeconds(60), 3),
            null, [], "bytes", T0.AddMinutes(i))).ToList();

        var thread = RunChannelSessionThread.Preloaded(turns);

        Assert.True(thread.Current.IsCaughtUp);
        Assert.Equal(0, thread.Current.Version);
        Assert.Equal(5, thread.Current.Turns.Count);
        Assert.Equal(new Spend(1000, 0, 240, 1), thread.Current.Turns[2].Outcome!.Spend);
        Assert.Equal(TimeSpan.FromSeconds(60), thread.Current.Turns[2].Outcome!.Duration);

        var raised = 0;
        thread.Changed += _ => raised++;
        thread.Accept("b6", Decorations, "bytes", T0.AddMinutes(6));
        Assert.Equal(1, raised);
        Assert.Equal(1, thread.Current.Version);
    }

    [Fact]
    public void ATerminalStateNeverMovesAgain()
    {
        var thread = new RunChannelSessionThread();
        var ordinal = thread.Accept("x", Decorations, "bytes", T0);
        thread.Conclude(ordinal, TurnState.Stopped, T0.AddSeconds(1));

        Assert.Throws<InvalidOperationException>(() => thread.Conclude(ordinal, TurnState.Completed, T0.AddSeconds(2)));
        Assert.Throws<InvalidOperationException>(() => thread.Wait(ordinal, new WaitingRequest("r", "permission", "?", [TurnActionKind.Deny])));
        Assert.Throws<ArgumentOutOfRangeException>(() => thread.Conclude(ordinal, TurnState.Running, T0));
    }

    [Fact]
    public void TheInvariantsHold_WaitingIffWaitingState_OutcomeIffTerminal()
    {
        Assert.Throws<ArgumentException>(() => new TurnView(1, "e", "s", [], TurnState.Waiting, null, null, [], "b", T0));
        Assert.Throws<ArgumentException>(() => new TurnView(1, "e", "s", [], TurnState.Running, new OutcomeView("l", null, null, null, null, 0), null, [], "b", T0));
        Assert.Throws<ArgumentException>(() => new TurnView(1, "e", "s", [], TurnState.Completed, null, null, [], "b", T0));
        Assert.Throws<ArgumentException>(() => new TurnView(1, "e", "s", [], TurnState.NotRecorded, new OutcomeView("l", null, null, null, null, 0), null, [], "b", T0));
    }

    /// <summary>M2: absent usage reads <i>not recorded</i>, never 0; the header sums what was measured and names what was not.</summary>
    [Fact]
    public void AbsentUsageReadsNotRecordedNeverZero_AndTheHeaderSpendIsTheSum()
    {
        var measured = new TurnView(1, "e", "s", Decorations, TurnState.Completed, new OutcomeView("claude-code", null, 3, new Spend(10_000, 1_840, 2_400, 3), TimeSpan.FromSeconds(252), 142), null, [], "b", T0);
        var unmeasured = new TurnView(2, "e", "s", Decorations, TurnState.Completed, new OutcomeView("claude-code", null, null, null, null, 4), null, [], "b", T0);
        var notRecorded = new TurnView(3, "e", "s", Decorations, TurnState.NotRecorded, null, null, [], "b", T0);

        Assert.Equal("tokens not recorded", TurnCopy.SpendText(null));
        Assert.DoesNotContain("0 tokens", string.Join(" ", TurnCopy.Counts(unmeasured)), StringComparison.Ordinal);
        Assert.Equal(["edits not recorded", "tokens not recorded", "4 events"], TurnCopy.Counts(unmeasured));
        Assert.Equal(["3 edits", "12,400 tokens", "4 min 12 s", "142 events"], TurnCopy.Counts(measured));

        Assert.Equal("12,400 tokens this session (1 not recorded) · bounded by your subscription", TurnCopy.SessionSpend([measured, unmeasured, notRecorded], null));
        Assert.Equal("12,400 of 40,000 · cap enforced", TurnCopy.SessionSpend([measured, unmeasured], 40_000));
        Assert.Equal("spend not recorded · bounded by your subscription", TurnCopy.SessionSpend([unmeasured], null));

        Assert.Equal("outcome not recorded", TurnCopy.OutcomeWord(notRecorded));
        Assert.Equal("completed", TurnCopy.OutcomeWord(unmeasured));
    }

    [Fact]
    public void TheNameIsTheOrdinalAndTheFirst120CharactersWithAnEllipsisWhenTruncated()
    {
        var words = string.Join(" ", Enumerable.Range(0, 40).Select(i => "word" + i));
        var turn = new TurnView(17, "e", words, Decorations, TurnState.Failed, new OutcomeView("claude-code", 1, 0, null, null, 12), null, [], "b", T0);

        var name = TurnCopy.Name(turn);

        Assert.StartsWith("b17, ", name, StringComparison.Ordinal);
        Assert.EndsWith("…", name, StringComparison.Ordinal);
        Assert.True(name.Length <= "b17, ".Length + TurnCopy.NameWords + 1);
        Assert.Equal("b2, short", TurnCopy.Name(new TurnView(2, "e", "short", Decorations, TurnState.Running, null, null, [], "b", T0)));
        Assert.Equal("lane exited 1", TurnCopy.OutcomeWord(turn));
        Assert.Equal("The lane exited 1 after 0 edits. Send the same turn again as a new turn, or open the log.", TurnCopy.ReasonSentence(turn));
        Assert.Equal("class free-form · tier T1 · lease src/** · goal block", TurnCopy.DecorationLine(Decorations));
    }
}
