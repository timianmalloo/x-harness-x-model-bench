using AiDe.Core.Presentation.Sessions;

// The folder is Presentation/Sessions (the oracle's path); the namespace is the thread tests' (DC-172).
namespace AiDe.Core.Tests.Sessions.Thread;

/// <summary>
/// <b>C3</b> (Ruling 81; CV-5.2). The run-channel read model's <see cref="TurnView"/> carries the
/// fold — <c>Rows == Coalesce(Events)</c> — and no reply blob: the <c>StringBuilder</c> that
/// concatenated <c>agent.msg</c> text into a second store of the same events is gone, and so is the
/// <c>Reply</c> the thread rendered from it (Ruling 82: <i>two projections of the same events</i>).
/// </summary>
public sealed class RunChannelSessionThreadTests
{
    private static readonly DateTimeOffset T0 = new(2026, 9, 13, 16, 29, 56, TimeSpan.Zero);

    private static IReadOnlyList<DecorationRow> Decorations =>
        [new("class", "free-form", "session-default", ""), new("tier", "T1", "rule", ""), new("shape", "goal block", "projection", "")];

    private static EventLine Line(int second, string kind, string text) =>
        new(T0.AddSeconds(second), "claude-code", kind, text, "run");

    [Fact]
    public void TheTurnView_CarriesTheFold_NotAReplyBlob()
    {
        var thread = new RunChannelSessionThread();
        var ordinal = thread.Accept("Which merges are missing?", Decorations, "bytes", T0);

        thread.Append(ordinal, Line(0, Coalesce.MessageKind, "mer"));
        thread.Append(ordinal, Line(0, Coalesce.MessageKind, "ges are"));
        thread.Append(ordinal, Line(1, Coalesce.MessageKind, " missing from the tracker and"));
        thread.Append(ordinal, Line(2, "tool.call", "read docs/tracker.md"));
        thread.Append(ordinal, Line(3, Coalesce.MessageKind, "three "));
        thread.Append(ordinal, Line(3, Coalesce.MessageKind, "of them are yours."));
        thread.Conclude(ordinal, TurnState.Completed, T0.AddSeconds(4));

        var turn = Assert.Single(thread.Current.Turns);

        // The fold, and nothing beside it: every snapshot's rows are Coalesce of its events.
        Assert.Equal(Coalesce.Rows(turn.Events), turn.Rows);
        Assert.Equal(6, turn.Events.Count);
        Assert.Equal(3, turn.Rows.Count);
        Assert.Equal(["merges are missing from the tracker and", "read docs/tracker.md", "three of them are yours."], turn.Rows.Select(r => r.Text));
        Assert.Equal([3, null, 2], turn.Rows.Select(r => r.Chunks));

        // A second store of the text fails: the view carries no Reply — the text lives in Events
        // and is read through Rows (every snapshot's Rows == Coalesce(Events), below). The
        // accumulator's absence is proven by behaviour, not by scanning private structure (D1).
        Assert.Null(typeof(TurnView).GetProperty("Reply"));
    }

    /// <summary>Every published snapshot's rows are the fold of its own events — a chunk arriving re-folds the live message in place.</summary>
    [Fact]
    public void EachSnapshot_RowsAreCoalesceOfItsOwnEvents()
    {
        var thread = new RunChannelSessionThread();
        var raised = new List<ThreadSnapshot>();
        thread.Changed += raised.Add;
        var ordinal = thread.Accept("words", Decorations, "bytes", T0);

        thread.Append(ordinal, Line(0, Coalesce.MessageKind, "a"));
        thread.Append(ordinal, Line(0, Coalesce.MessageKind, "b"));
        thread.Append(ordinal, Line(1, "acp.result", "acp.result"));
        thread.Append(ordinal, Line(2, Coalesce.MessageKind, "c"));

        Assert.All(raised, s => Assert.Equal(Coalesce.Rows(s.Turns[0].Events), s.Turns[0].Rows));
        Assert.Equal([0, 1, 1, 2, 3], raised.Select(s => s.Turns[0].Rows.Count));
        Assert.Equal("ab", raised[2].Turns[0].Rows[0].Text);
        Assert.Equal(2, raised[2].Turns[0].Rows[0].Chunks);
    }

    /// <summary>A pre-loaded view's rows survive the round trip through the fold's private turn: what goes in is what comes out.</summary>
    [Fact]
    public void APreloadedTurn_KeepsItsRows()
    {
        var events = new[] { Line(0, Coalesce.MessageKind, "x"), Line(0, Coalesce.MessageKind, "y"), Line(1, "tool.result", "ok") };
        var view = new TurnView(1, "env", "words", Decorations, TurnState.Completed,
            new OutcomeView("claude-code", null, 0, null, TimeSpan.FromSeconds(1), 3), null, events, "bytes", T0);

        var thread = RunChannelSessionThread.Preloaded([view]);

        Assert.Equal(view.Rows, thread.Current.Turns[0].Rows);
        Assert.Equal(["xy", "ok"], thread.Current.Turns[0].Rows.Select(r => r.Text));
    }
}
