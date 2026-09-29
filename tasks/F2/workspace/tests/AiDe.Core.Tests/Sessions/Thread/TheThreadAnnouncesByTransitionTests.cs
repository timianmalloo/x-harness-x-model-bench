using AiDe.Core.Presentation.Sessions;

namespace AiDe.Core.Tests.Sessions.Thread;

/// <summary>
/// DS-1 <b>A1</b> — <c>ThreadAnnouncementPolicy.Next</c> emits each transition once, nothing before
/// catch-up, nothing for history, two outcomes in one snapshot as two, and both legs of a
/// <i>running → waiting → running</i> that arrive before one render. Pure: no window.
/// </summary>
/// <remarks>
/// <b>Red observed</b>: with the catch-up rule's first line removed (a policy that remembers a
/// not-caught-up snapshot), the forty-replays row emitted 5 and the pre-loaded-fixture row 6
/// (recorded in <c>docs/proof/composer-as-conversation.md</c>).
/// </remarks>
public sealed class TheThreadAnnouncesByTransitionTests
{
    private static readonly DateTimeOffset T0 = new(2026, 9, 12, 14, 0, 0, TimeSpan.Zero);

    private static TurnView Turn(
        int ordinal, TurnState state, int? exitCode = null, string? requestId = null, Spend? spend = null, string shape = "goal block")
    {
        var terminal = TurnView.IsTerminal(state);
        return new TurnView(
            ordinal, $"env-{ordinal}", $"words of b{ordinal}",
            [new("class", "free-form", "session-default", ""), new("tier", "T1", "rule", ""), new("shape", shape, "projection", "")],
            state,
            terminal ? new OutcomeView("claude-code", exitCode, 1, spend, TimeSpan.FromSeconds(252), 12) : null,
            state == TurnState.Waiting ? new WaitingRequest(requestId ?? "r1", "permission", "claude-code asks to write outside the declared scope.", [TurnActionKind.Deny, TurnActionKind.AllowOnce]) : null,
            [], "bytes", T0);
    }

    private static ThreadSnapshot Snapshot(long version, bool caughtUp, params TurnView[] turns) => new(turns, version, caughtUp);

    private static TurnView Running(int ordinal, params EventLine[] events) =>
        new(ordinal, $"env-{ordinal}", $"words of b{ordinal}",
            [new("class", "free-form", "session-default", ""), new("tier", "T1", "rule", ""), new("shape", "goal block", "projection", "")],
            TurnState.Running, null, null, events, "bytes", T0);

    private static EventLine Line(int second, string kind, string text) => new(T0.AddSeconds(second), "claude-code", kind, text, "run");

    /// <summary>SC9 (Ruling 81): a chunk arriving, a message folding, a tool call between messages — none is a transition; the policy reads the state, never the rows.</summary>
    [Fact]
    public void ChunksArrivingAndFolding_AreNeverAnnounced()
    {
        var policy = new ThreadAnnouncementPolicy();
        Assert.Empty(policy.Next(Snapshot(0, true, Turn(1, TurnState.Completed))));
        var accepted = policy.Next(Snapshot(1, true, Turn(1, TurnState.Completed), Running(2)));
        Assert.NotEmpty(accepted);

        var announced = 0;
        announced += policy.Next(Snapshot(2, true, Turn(1, TurnState.Completed), Running(2, Line(0, Coalesce.MessageKind, "mer")))).Count;
        announced += policy.Next(Snapshot(3, true, Turn(1, TurnState.Completed), Running(2, Line(0, Coalesce.MessageKind, "mer"), Line(0, Coalesce.MessageKind, "ges are")))).Count;
        announced += policy.Next(Snapshot(4, true, Turn(1, TurnState.Completed), Running(2, Line(0, Coalesce.MessageKind, "mer"), Line(0, Coalesce.MessageKind, "ges are"), Line(1, "tool.call", "read docs/tracker.md")))).Count;
        announced += policy.Next(Snapshot(5, true, Turn(1, TurnState.Completed), Running(2, Line(0, Coalesce.MessageKind, "mer"), Line(0, Coalesce.MessageKind, "ges are"), Line(1, "tool.call", "read docs/tracker.md"), Line(2, Coalesce.MessageKind, "three")))).Count;

        Assert.Equal(0, announced);
    }

    [Fact]
    public void FortyReplayedSnapshotsAndTheFirstCaughtUpOneEmitNothing()
    {
        var policy = new ThreadAnnouncementPolicy();
        var history = Enumerable.Range(1, 5).Select(i => Turn(i, TurnState.Completed, spend: new Spend(10_000, 0, 2_400, 3))).ToArray();

        var emitted = 0;
        for (var i = 0; i < 40; i++)
        {
            emitted += policy.Next(Snapshot(0, caughtUp: false, history.Take(i % 5 + 1).ToArray())).Count;
        }

        emitted += policy.Next(Snapshot(0, caughtUp: true, history)).Count;

        Assert.Equal(0, emitted);
    }

    [Fact]
    public void APreloadedFixtureCaughtUpFromConstructionAnnouncesOnlyTheLiveTransition()
    {
        var policy = new ThreadAnnouncementPolicy();
        var history = Enumerable.Range(1, 5).Select(i => Turn(i, TurnState.Completed)).ToArray();

        Assert.Empty(policy.Next(Snapshot(0, true, history)));

        var running = history.Append(Turn(6, TurnState.Running)).ToArray();
        var accepted = policy.Next(Snapshot(1, true, running));
        Assert.Single(accepted);
        Assert.Equal("Turn b6 accepted as a goal block, tier T1, class free-form.", accepted[0].Text);
        Assert.Equal(Urgency.Status, accepted[0].Urgency);
        Assert.Equal(AnnouncementKind.ItemAdded, accepted[0].Kind);

        var completed = history.Append(Turn(6, TurnState.Completed, spend: new Spend(10_000, 1_840, 2_400, 3))).ToArray();
        var done = policy.Next(Snapshot(2, true, completed));
        Assert.Single(done);
        Assert.Equal("Turn b6 completed: 1 edit, 12,400 tokens, 4 minutes 12 seconds.", done[0].Text);
        Assert.Equal(AnnouncementKind.Completed, done[0].Kind);
        Assert.Equal("running→completed", done[0].Transition);
        Assert.Equal(6, done[0].Ordinal);
    }

    [Fact]
    public void TheSameSnapshotTwiceAFoldToggleAndAScrollProduceNoTransition()
    {
        var policy = new ThreadAnnouncementPolicy();
        var one = Turn(1, TurnState.Running);
        policy.Next(Snapshot(0, true, one));

        // A re-render of the same state (a fold toggle, a scroll, a caret move) is the same snapshot again.
        Assert.Empty(policy.Next(Snapshot(1, true, one)));
        Assert.Empty(policy.Next(Snapshot(2, true, one)));
    }

    [Fact]
    public void ALaneExitIsAssertiveAndOnce_AStopIsAStatus_NotRecordedIsAStatus()
    {
        var policy = new ThreadAnnouncementPolicy();
        policy.Next(Snapshot(0, true, Turn(1, TurnState.Running), Turn(2, TurnState.Running)));

        var exited = policy.Next(Snapshot(1, true, Turn(1, TurnState.Failed, exitCode: 1), Turn(2, TurnState.Running)));
        Assert.Single(exited);
        Assert.Equal(Urgency.Assertive, exited[0].Urgency);
        Assert.Equal(AnnouncementKind.Aborted, exited[0].Kind);
        Assert.Equal("Turn b1: the lane exited 1 after 1 edit. Send the same turn again as a new turn, or open the log.", exited[0].Text);

        var stopped = policy.Next(Snapshot(2, true, Turn(1, TurnState.Failed, exitCode: 1), Turn(2, TurnState.Stopped, spend: new Spend(3_000, 0, 900, 2))));
        Assert.Single(stopped);
        Assert.Equal(Urgency.Status, stopped[0].Urgency);
        Assert.Equal("Turn b2 stopped by you after 1 edit; 3,900 tokens. Send the same turn again as a new turn, or open the log.", stopped[0].Text);

        // Once by transition: the same terminal states again say nothing.
        Assert.Empty(policy.Next(Snapshot(3, true, Turn(1, TurnState.Failed, exitCode: 1), Turn(2, TurnState.Stopped, spend: new Spend(3_000, 0, 900, 2)))));

        var notRecorded = policy.Next(Snapshot(4, true, Turn(1, TurnState.Failed, exitCode: 1), Turn(2, TurnState.Stopped, spend: new Spend(3_000, 0, 900, 2)), Turn(3, TurnState.NotRecorded)));
        Assert.Single(notRecorded);
        Assert.Equal("Turn b3: outcome not recorded.", notRecorded[0].Text);
        Assert.Equal(AnnouncementKind.Other, notRecorded[0].Kind);
    }

    [Fact]
    public void TwoOutcomesInOneSnapshotAreTwoAnnouncementsInOrdinalOrder()
    {
        var policy = new ThreadAnnouncementPolicy();
        policy.Next(Snapshot(0, true, Turn(1, TurnState.Running), Turn(2, TurnState.Running)));

        var both = policy.Next(Snapshot(1, true, Turn(1, TurnState.Completed), Turn(2, TurnState.Answered)));

        Assert.Equal(2, both.Count);
        Assert.Equal(1, both[0].Ordinal);
        Assert.Equal(2, both[1].Ordinal);
        Assert.All(both, a => Assert.Equal(Urgency.Status, a.Urgency));
    }

    [Fact]
    public void TwoSnapshotsBeforeOneRenderYieldBothLegs_WaitingIsAssertiveOncePerRequestId()
    {
        var policy = new ThreadAnnouncementPolicy();
        policy.Next(Snapshot(0, true, Turn(5, TurnState.Running)));

        var waiting = policy.Next(Snapshot(1, true, Turn(5, TurnState.Waiting, requestId: "r1")));
        Assert.Single(waiting);
        Assert.Equal(Urgency.Assertive, waiting[0].Urgency);
        Assert.Equal(AnnouncementKind.Other, waiting[0].Kind);
        Assert.Equal("Turn b5 is waiting for you: claude-code asks to write outside the declared scope. Deny or allow once.", waiting[0].Text);

        // The same request id again: nothing. A new one: one more, for it.
        Assert.Empty(policy.Next(Snapshot(2, true, Turn(5, TurnState.Waiting, requestId: "r1"))));
        Assert.Single(policy.Next(Snapshot(3, true, Turn(5, TurnState.Waiting, requestId: "r2"))));

        var continues = policy.Next(Snapshot(4, true, Turn(5, TurnState.Running)));
        Assert.Single(continues);
        Assert.Equal("Turn b5 continues.", continues[0].Text);
        Assert.Equal(Urgency.Status, continues[0].Urgency);
    }

    [Fact]
    public void ANewOrdinalAlreadyTerminalAnnouncesItsOutcomeOnce()
    {
        var policy = new ThreadAnnouncementPolicy();
        policy.Next(Snapshot(0, true));

        var joined = policy.Next(Snapshot(1, true, Turn(1, TurnState.Answered, spend: new Spend(1_000, 0, 860, 1))));

        Assert.Single(joined);
        Assert.Equal("Turn b1 answered: 1 edit, 1,860 tokens, 4 minutes 12 seconds.", joined[0].Text);
    }

    [Fact]
    public void AVersionGapIsReportedAndTheNetTransitionIsStillAnnounced()
    {
        var policy = new ThreadAnnouncementPolicy();
        policy.Next(Snapshot(0, true, Turn(1, TurnState.Running)));

        var emitted = policy.Next(Snapshot(5, true, Turn(1, TurnState.Completed)));

        Assert.Single(emitted);
        Assert.Equal((1L, 5L), policy.LastVersionGap);

        policy.Next(Snapshot(6, true, Turn(1, TurnState.Completed)));
        Assert.Null(policy.LastVersionGap);
    }

    [Fact]
    public void AFirstCallThatEmitsWouldAnnounceHistory_TheRuleForbidsIt()
    {
        var policy = new ThreadAnnouncementPolicy();
        var forty = Enumerable.Range(1, 40).Select(i => Turn(i, i == 17 ? TurnState.Failed : TurnState.Completed, exitCode: i == 17 ? 1 : null)).ToArray();

        Assert.Empty(policy.Next(Snapshot(0, true, forty)));
    }

    /// <summary>
    /// The D2 property over a seeded walk, as it holds: for any snapshot sequence <i>S</i> and any
    /// subsequence <i>S'</i> of it, the ordinals <i>S'</i> announces are a subset of the ordinals
    /// <i>S</i> announces (a subsequence hides intermediate states, so its per-ordinal transitions
    /// are the net of the whole's — the design's stronger "subsequence of emissions" claim is false
    /// by construction for a net transition and is not asserted), and an ordinal has ≥ 1 emission
    /// iff its endpoint tuples differ. The seed is printed on failure.
    /// </summary>
    [Theory]
    [InlineData(1)]
    [InlineData(7)]
    [InlineData(42)]
    [InlineData(2026)]
    public void TheOrdinalsASubsequenceAnnouncesAreASubsetOfTheWholes_AndAnOrdinalSpeaksIffItsEndpointsDiffer(int seed)
    {
        var random = new Random(seed);
        var sequence = Walk(random, steps: 60);

        var whole = Emit(sequence).Select(a => (a.Ordinal, a.Transition)).ToList();
        var keep = sequence.Select((s, i) => i == 0 || i == sequence.Count - 1 || random.Next(3) != 0).ToList();
        var sub = sequence.Where((s, i) => keep[i]).ToList();
        var subEmissions = Emit(sub).Select(a => (a.Ordinal, a.Transition)).ToList();

        // A subsequence hides intermediate states, so its per-ordinal transitions are the net of
        // the whole's — every ordinal the subsequence announces, the whole announces too.
        Assert.True(
            subEmissions.Select(e => e.Ordinal).Distinct().All(o => whole.Any(w => w.Ordinal == o)),
            $"seed {seed}: the subsequence announced an ordinal the whole did not");

        var first = sequence[0];
        var last = sequence[^1];
        foreach (var turn in last.Turns)
        {
            var before = first.Turns.FirstOrDefault(t => t.Ordinal == turn.Ordinal);
            var differs = before is null || before.State != turn.State || before.Waiting?.RequestId != turn.Waiting?.RequestId;
            var announced = whole.Any(w => w.Ordinal == turn.Ordinal);
            Assert.True(differs == announced, $"seed {seed}: ordinal {turn.Ordinal} differs={differs} announced={announced}");
        }
    }

    private static List<Announcement> Emit(IReadOnlyList<ThreadSnapshot> snapshots)
    {
        var policy = new ThreadAnnouncementPolicy();
        var all = new List<Announcement>();
        foreach (var snapshot in snapshots)
        {
            all.AddRange(policy.Next(snapshot));
        }

        return all;
    }

    /// <summary>The state machine: ordinals dense and append-only, terminal states absorbing, request ids fresh.</summary>
    private static List<ThreadSnapshot> Walk(Random random, int steps)
    {
        var turns = new List<TurnView>();
        var snapshots = new List<ThreadSnapshot> { new([], 0, true) };
        var requests = 0;

        for (var step = 1; step <= steps; step++)
        {
            var open = turns.Where(t => !TurnView.IsTerminal(t.State)).ToList();
            if (open.Count == 0 || random.Next(4) == 0)
            {
                turns.Add(Turn(turns.Count + 1, TurnState.Running));
            }
            else
            {
                var pick = open[random.Next(open.Count)];
                var next = random.Next(6) switch
                {
                    0 => Turn(pick.Ordinal, TurnState.Waiting, requestId: "r" + (++requests)),
                    1 => Turn(pick.Ordinal, TurnState.Running),
                    2 => Turn(pick.Ordinal, TurnState.Completed),
                    3 => Turn(pick.Ordinal, TurnState.Failed, exitCode: 1),
                    4 => Turn(pick.Ordinal, TurnState.Stopped),
                    _ => pick,
                };
                turns[turns.IndexOf(pick)] = next;
            }

            snapshots.Add(new ThreadSnapshot([.. turns], step, true));
        }

        return snapshots;
    }
}
