using System.Text.Json.Nodes;
using AiDe.Core.AgentPlane;
using AiDe.Core.Presentation.Sessions;
using AiDe.Core.Tests.AgentPlane;

namespace AiDe.Core.Tests.Sessions.Thread;

/// <summary>
/// <b>I1 (CV-5.3, Ruling 82).</b> The items projection over <c>Coalesce</c> rows — pure: a
/// <c>tool.call</c> and its <c>tool.result</c>s by id are one item carrying the last result's
/// status; a result with no call is an event row, never dropped; <c>acp.*</c> rows are events
/// (counted into <i>N events</i>), never items; order is preserved; and the five review turns plus
/// <c>b17</c> — the mockup's event model, at the event level — project to their goldens.
/// </summary>
/// <remarks>
/// <b>Red observed</b> against the pre-ruling projection (every row an event): the theory's first
/// row failed with <c>Expected: [Event, Reasoning, Tool(done), Prose, Event, Event] · Actual:
/// [Event ×7]</c>; the corpus facts failed on <c>Assert.Single</c> of a tool item.
/// </remarks>
public sealed class ConversationItemsTests
{
    private static readonly DateTimeOffset T0 = new(2026, 9, 12, 14, 1, 0, TimeSpan.Zero);

    // ── the event model, as the mapper emits it (the mockup's `msg · thought · call · result · acp · cond`), chunked as the wire chunks ──

    private static IEnumerable<EventLine> Msg(int s, string lane, string text) => Chunked(s, lane, Coalesce.MessageKind, text);

    private static IEnumerable<EventLine> Thought(int s, string lane, string text) => Chunked(s, lane, Coalesce.ThoughtKind, text);

    private static IEnumerable<EventLine> Chunked(int s, string lane, string kind, string text) =>
        text.Chunk(14).Select(c => new EventLine(T0.AddSeconds(s), lane, kind, new string(c), "run"));

    private static EventLine Call(int s, string lane, string id, string kind, string title, string input) =>
        new(T0.AddSeconds(s), lane, ConversationItems.CallKind, title, "run", new ToolFacts(id, kind, title, "pending", input, null));

    private static EventLine Result(int s, string lane, string id, string status, string output) =>
        new(T0.AddSeconds(s), lane, ConversationItems.ResultKind, status, "run", new ToolFacts(id, null, null, status, null, output));

    private static EventLine Acp(int s, string lane, string name) => new(T0.AddSeconds(s), lane, "acp.session.update." + name, "acp.session.update." + name, "run");

    private static EventLine Cond(int s, string kind, string text) => new(T0.AddSeconds(s), "conductor", kind, text, "run");

    /// <summary>The five review turns and b17, each with its golden — the item kinds in order, a tool item as <c>Tool(status)</c>; the usage rows are Console-only since Ruling 100 (b2's <c>acp.result</c> still folds).</summary>
    public static TheoryData<string, bool, string[]> Turns => new()
    {
        {
            "b1", false,
            ["Event", "Reasoning", "Tool(done)", "Prose", "Event"]
        },
        {
            "b2", false,
            ["Event", "Reasoning", "Tool(done)", "Tool(done)", "Prose", "Tool(done)", "Tool(failed)", "Tool(done)", "Prose", "Event", "Event"]
        },
        {
            "b3", false,
            ["Event", "Reasoning", "Tool(done)", "Tool(done)", "Prose", "Tool(done)", "Prose", "Event"]
        },
        {
            "b4", false,
            ["Event", "Reasoning", "Tool(done)", "Tool(done)", "Prose", "Event"]
        },
        {
            "b5", false,
            ["Event", "Reasoning", "Tool(done)", "Prose", "Tool(done)", "Prose", "Event"]
        },
        {
            "b17", false,
            ["Event", "Reasoning", "Tool(done)", "Tool(interrupted)", "Event", "Event"]
        },
        {
            "b6-running", true,
            ["Reasoning", "Tool(done)", "Tool(running)"]
        },
        {
            "b7-parallel", false,
            ["Tool(failed)", "Tool(done)"]
        },
    };

    private static IReadOnlyList<EventLine> Events(string turn) => turn switch
    {
        "b1" =>
        [
            Cond(12, "run.accepted", "Block b1 accepted, tier T0, 0 lanes"),
            .. Thought(13, "conductor", "The workspace has two layout stores; name each one's invariant from its migration code."),
            Call(14, "conductor", "b1t1", "search", "Grep \"class .*LayoutStore\"", "pattern: class .*LayoutStore"),
            Result(14, "conductor", "b1t1", "completed", "2 matches: LayoutStore.cs:18, ZoneLayoutStore.cs:14"),
            .. Msg(15, "conductor", "Two stores.\n\n- `LayoutStore` — tree schema, v4.\n- `ZoneLayoutStore` — zone schema, v1."),
            Acp(18, "conductor", "usage_update"),
            Cond(18, "run.completed", "answered (1,860 tokens)"),
        ],
        "b2" =>
        [
            Cond(3, "run.accepted", "Block b2 accepted, tier T1, 1 lane"),
            .. Thought(4, "claude-code", "A newer schema must be refused before any step runs."),
            Call(7, "claude-code", "b2t1", "read", "Read LayoutStore.cs", "file_path: src/AiDe.Core/Workbench/LayoutStore.cs"),
            Result(7, "claude-code", "b2t1", "completed", "412 lines"),
            Call(8, "claude-code", "b2t2", "search", "Grep \"Migrations.Step\"", "pattern: Migrations\\.Step"),
            Result(8, "claude-code", "b2t2", "completed", "3 matches"),
            .. Msg(14, "claude-code", "`Load` steps the chain before it compares versions. I'll compare first."),
            Call(20, "claude-code", "b2t6", "edit", "Edit LayoutStoreTests.cs", "file_path: tests/AiDe.App.Tests/LayoutStoreTests.cs"),
            Result(20, "claude-code", "b2t6", "completed", "1 hunk, 14 lines"),
            Call(31, "claude-code", "b2t7", "execute", "dotnet test tests/AiDe.App.Tests --filter LayoutStore", "command: dotnet test"),
            Result(58, "claude-code", "b2t7", "failed", "Failed! 13 passed, 1 failed"),
            Call(65, "claude-code", "b2t8", "edit", "Edit LayoutStore.cs", "file_path: src/AiDe.Core/Workbench/LayoutStore.cs"),
            Result(65, "claude-code", "b2t8", "completed", "1 hunk, 9 lines"),
            .. Msg(224, "claude-code", "Done.\n\n| What | Result |\n|---|---|\n| Red first | failed on the old order |\n| Green | 14 passed |"),
            Acp(254, "claude-code", "usage_update"),
            Acp(254, "claude-code", "usage_update"),
            Acp(255, "claude-code", "result"),
            Cond(255, "run.completed", "completed: 3 edits, 12,400 tokens"),
        ],
        "b3" =>
        [
            Cond(2, "run.accepted", "Block b3 accepted, tier T1, 1 lane"),
            .. Thought(3, "claude-code", "A green theory beside a failing shell measures something the shell does not construct."),
            Call(5, "claude-code", "b3t1", "read", "Read ContrastFloorTests.cs", "file_path: tests/AiDe.App.Tests/ContrastFloorTests.cs"),
            Result(5, "claude-code", "b3t1", "completed", "188 lines"),
            Call(20, "claude-code", "b3t2", "search", "Grep \"ThemeBrushes\"", "pattern: ThemeBrushes"),
            Result(20, "claude-code", "b3t2", "completed", "0 matches under src/"),
            .. Msg(40, "claude-code", "Root cause: the theory exercises `ThemeBrushes`, which the product does not construct."),
            Call(100, "claude-code", "b3t3", "edit", "Edit ShellContrastCensusTests.cs", "file_path: tests/AiDe.App.Tests/ShellContrastCensusTests.cs"),
            Result(100, "claude-code", "b3t3", "completed", "1 hunk, 22 lines"),
            .. Msg(185, "claude-code", "The census now walks the composed tree — the shell's number, reproduced."),
            Acp(187, "claude-code", "usage_update"),
            Cond(187, "run.completed", "completed: 1 edit, 9,900 tokens"),
        ],
        "b4" =>
        [
            Cond(10, "run.accepted", "Block b4 accepted, tier T2, 2 lanes"),
            .. Thought(11, "claude-code", "Two seams: the tab strip template and the three menu brushes."),
            Call(12, "claude-code", "b4t1", "read", "Read DockRoundedTabs.xaml", "file_path: src/AiDe.App/Workbench/DockRoundedTabs.xaml"),
            Result(12, "claude-code", "b4t1", "completed", "240 lines"),
            Call(30, "claude-code", "b4t2", "edit", "Edit DockRoundedTabs.xaml", "file_path: src/AiDe.App/Workbench/DockRoundedTabs.xaml"),
            Result(30, "claude-code", "b4t2", "completed", "2 hunks, 18 lines"),
            .. Msg(700, "claude-code", "Both seams landed: the selected-inactive tab pairs text on surface with the 2px muted edge."),
            Cond(700, "run.completed", "completed: 5 edits, 31,200 tokens"),
        ],
        "b5" =>
        [
            Cond(2, "run.accepted", "Block b5 accepted, tier T1, 1 lane"),
            .. Thought(3, "claude-code", "Three changes with their shas, two open items; the proof pack names each claim's oracle."),
            Call(5, "claude-code", "b5t1", "edit", "Write docs/proof/pp-0142.md", "file_path: docs/proof/pp-0142.md"),
            Result(5, "claude-code", "b5t1", "completed", "1 file, 61 lines"),
            .. Msg(40, "claude-code", "## Open\n\n1. the density question\n2. the split's home — see [the review](docs/reviews/r.md)"),
            Call(50, "claude-code", "b5t2", "read", "Read docs/proof/pp-0142.md", "file_path: docs/proof/pp-0142.md"),
            Result(50, "claude-code", "b5t2", "completed", "61 lines"),
            .. Msg(60, "claude-code", "Wrote docs/proof/pp-0142.md — three changes with their shas, two open items (§7)."),
            Acp(62, "claude-code", "usage_update"),
            Cond(62, "run.completed", "completed: 1 edit, 4,100 tokens"),
        ],
        "b17" =>
        [
            Cond(1, "run.accepted", "Block b17 accepted, tier T1, 1 lane"),
            .. Thought(2, "claude-code", "The lease refuses docs/audit/; write the proof under docs/proof/ instead."),
            Call(3, "claude-code", "b17t1", "read", "Read docs/proof/pp-0141.md", "file_path: docs/proof/pp-0141.md"),
            Result(3, "claude-code", "b17t1", "completed", "40 lines"),
            Call(9, "claude-code", "b17t2", "edit", "Edit docs/audit/audit-log.jsonl", "file_path: docs/audit/audit-log.jsonl"),
            new EventLine(T0.AddSeconds(12), "claude-code", "stderr", "b17 line 12: exit 1 — the lease refused docs/audit/", "run"),
            Cond(12, "run.completed", "lane exited 1"),
        ],
        "b7-parallel" =>
        [
            // Two calls open at once, the results interleaved: by id, never by position — the one
            // input on which the two attachments differ while both ids are known.
            Call(1, "claude-code", "a", "read", "Read a.cs", "file_path: a.cs"),
            Call(2, "claude-code", "b", "read", "Read b.cs", "file_path: b.cs"),
            Result(3, "claude-code", "b", "completed", "b: 12 lines"),
            Result(4, "claude-code", "a", "failed", "a: not found"),
        ],
        "b6-running" =>
        [
            .. Thought(2, "claude-code", "Read the proof pack before the change."),
            Call(3, "claude-code", "b6t1", "read", "Read docs/proof/pp-0141.md", "file_path: docs/proof/pp-0141.md"),
            Result(3, "claude-code", "b6t1", "completed", "40 lines"),
            Call(9, "claude-code", "b6t2", "execute", "dotnet test", "command: dotnet test"),
            Result(10, "claude-code", "b6t2", "in_progress", ""),
        ],
        _ => throw new ArgumentOutOfRangeException(nameof(turn)),
    };

    private static string Golden(ConversationItem item) => item switch
    {
        ConversationItem.Prose => "Prose",
        ConversationItem.Reasoning => "Reasoning",
        ConversationItem.Tool tool => "Tool(" + ConversationItems.StatusWord(tool.Status) + ")",
        ConversationItem.Event => "Event",
        _ => throw new ArgumentOutOfRangeException(nameof(item)),
    };

    /// <summary>The five turns and b17 project to their goldens; every row of the fold is either one item's row or attached to a tool item, in order — nothing dropped, nothing invented.</summary>
    [Theory]
    [MemberData(nameof(Turns))]
    public void ItemsOverTheFold_AreProseReasoningToolAndOutcome_InEventOrder(string turn, bool live, string[] golden)
    {
        var rows = Coalesce.Rows(Events(turn));
        var items = ConversationItems.Of(rows, live);

        Assert.Equal(golden, items.Select(Golden).ToArray());

        // Every row but a bookkeeping row appears exactly once: as an item's row, or attached to the
        // tool item it belongs to (a partition of the folded rows — ordered by the rows' own order,
        // since a parallel call's results legitimately interleave with the next call's row). The
        // bookkeeping rows (Ruling 100) stay in `rows` for the Console and are the only ones absent.
        var folded = rows.Where(r => !ConversationItems.BookkeepingKinds.Contains(r.Kind)).ToList();
        var covered = items.SelectMany(i => i is ConversationItem.Tool t ? t.Results.Prepend(t.Row) : new[] { i.Row }).ToList();
        Assert.Equal(folded.Count, covered.Count);
        Assert.Equal(folded, covered.OrderBy(r => rows.ToList().IndexOf(r)));
        Assert.Equal(items.Select(i => i.Row), items.Select(i => i.Row).OrderBy(r => rows.ToList().IndexOf(r)));   // the items keep the rows' order

        // Each tool item holds exactly the results that carry its id.
        Assert.All(items.OfType<ConversationItem.Tool>(), t => Assert.All(t.Results, r => Assert.Equal(t.Row.Tool!.CallId, r.Tool!.CallId)));

        // acp.* rows are events, never items — except the two bookkeeping kinds, which are neither
        // (Ruling 100); every event row is a non-conversation kind.
        Assert.All(items.OfType<ConversationItem.Event>(), e => Assert.NotEqual(Coalesce.MessageKind, e.Row.Kind));
        Assert.All(rows.Where(r => r.Kind.StartsWith("acp.", StringComparison.Ordinal) && !ConversationItems.BookkeepingKinds.Contains(r.Kind)), r => Assert.Contains(items, i => i is ConversationItem.Event e && ReferenceEquals(e.Row, r)));
        Assert.All(rows.Where(r => ConversationItems.BookkeepingKinds.Contains(r.Kind)), r => Assert.DoesNotContain(items, i => ReferenceEquals(i.Row, r)));
    }

    /// <summary>A call and its results by id are one item with the last stated kind, title, input, the joined output and the last result's status.</summary>
    [Fact]
    public void ACallAndItsResultsById_AreOneItem_WithTheLastResultsStatus()
    {
        var rows = Coalesce.Rows(
        [
            new EventLine(T0, "claude-code", ConversationItems.CallKind, "Terminal", "run", new ToolFacts("t1", "execute", "Terminal", "pending", null, null)),
            new EventLine(T0.AddSeconds(1), "claude-code", ConversationItems.ResultKind, "tool.result", "run", new ToolFacts("t1", "execute", "git status --short", null, "command: git status --short", null)),
            new EventLine(T0.AddSeconds(2), "claude-code", ConversationItems.ResultKind, "tool.result", "run", new ToolFacts("t1", null, null, "in_progress", null, "Show short git status")),
            new EventLine(T0.AddSeconds(3), "claude-code", ConversationItems.ResultKind, "tool.result", "run", new ToolFacts("t1", null, null, "completed", null, "(Bash completed with no output)")),
        ]);

        var item = Assert.IsType<ConversationItem.Tool>(Assert.Single(ConversationItems.Of(rows, live: false)));
        Assert.Equal(ToolStatus.Done, item.Status);
        Assert.Equal("execute", item.Kind);
        Assert.Equal("git status --short", item.Title);
        Assert.Equal("command: git status --short", item.Input);
        Assert.Equal("Show short git status\n(Bash completed with no output)", item.Output);
        Assert.Equal(3, item.Results.Count);

        // A failed last result → failed; a pending last result → running on a live turn, interrupted otherwise.
        var failed = Coalesce.Rows(new[] { rows[0], new TurnRow(T0, "claude-code", ConversationItems.ResultKind, "r", null, new ToolFacts("t1", null, null, "failed", null, "boom")) }.Select(r => new EventLine(r.At, r.Lane, r.Kind, r.Text, "run", r.Tool)).ToList());
        Assert.Equal(ToolStatus.Failed, Assert.IsType<ConversationItem.Tool>(Assert.Single(ConversationItems.Of(failed, live: false))).Status);
        var pending = Coalesce.Rows([new EventLine(T0, "claude-code", ConversationItems.CallKind, "Terminal", "run", new ToolFacts("t2", "execute", "Terminal", "pending", null, null))]);
        Assert.Equal(ToolStatus.Running, Assert.IsType<ConversationItem.Tool>(Assert.Single(ConversationItems.Of(pending, live: true))).Status);
        Assert.Equal(ToolStatus.Interrupted, Assert.IsType<ConversationItem.Tool>(Assert.Single(ConversationItems.Of(pending, live: false))).Status);
    }

    /// <summary>A result whose call is not in the turn is an event row — counted, never dropped, never attached by position to an unrelated call.</summary>
    [Fact]
    public void AResultWithNoCall_IsAnEventRow_NeverDropped()
    {
        var rows = Coalesce.Rows(
        [
            new EventLine(T0, "claude-code", ConversationItems.ResultKind, "tool.result", "run", new ToolFacts("orphan", null, null, "completed", null, "late")),
            new EventLine(T0.AddSeconds(1), "claude-code", ConversationItems.CallKind, "Read x", "run", new ToolFacts("t1", "read", "Read x", "pending", null, null)),
            new EventLine(T0.AddSeconds(2), "claude-code", ConversationItems.ResultKind, "tool.result", "run", new ToolFacts("other", null, null, "completed", null, "not t1's")),
            new EventLine(T0.AddSeconds(3), "claude-code", ConversationItems.ResultKind, "b7 line 3: read docs/proof/pp-0141.md", "run"),
        ]);

        var items = ConversationItems.Of(rows, live: false);

        Assert.Equal(["Event", "Tool(interrupted)", "Event", "Event"], items.Select(Golden).ToArray());
        Assert.Empty(((ConversationItem.Tool)items[1]).Results);
    }

    /// <summary>The captured read run through the real mapper: one tool item (<i>execute · git status --short · done</i>) over its four updates, prose, and the rest as events.</summary>
    [Fact]
    public void TheCapturedReadRun_ProjectsToOneToolItem_AndItsProse()
    {
        var items = ConversationItems.Of(Coalesce.Rows(Lines("read.jsonl")), live: false);

        var tool = Assert.Single(items.OfType<ConversationItem.Tool>());
        Assert.Equal("execute", tool.Kind);
        Assert.Equal("git status --short", tool.Title);
        Assert.Equal(ToolStatus.Done, tool.Status);
        Assert.Equal("command: git status --short\ndescription: Show short git status", tool.Input);
        Assert.Contains("(Bash completed with no output)", tool.Output, StringComparison.Ordinal);
        Assert.Equal(4, tool.Results.Count);   // read.jsonl:10, 11, 13, 14 — counted, not guessed
        Assert.NotEmpty(items.OfType<ConversationItem.Prose>());
        Assert.DoesNotContain(items, i => i is ConversationItem.Event e && e.Row.Kind == ConversationItems.ResultKind);
    }

    /// <summary>The captured thought run: one reasoning item, its text the joined 19 chunks with the paragraph break intact, then the prose; the usage and auth frames are events.</summary>
    [Fact]
    public void TheCapturedThoughtRun_ProjectsToReasoningThenProse()
    {
        var items = ConversationItems.Of(Coalesce.Rows(Lines("thought.jsonl")), live: false);

        var reasoning = Assert.Single(items.OfType<ConversationItem.Reasoning>());
        Assert.Equal(19, reasoning.Row.Chunks);
        Assert.StartsWith("This is a straightforward logic puzzle", reasoning.Row.Text, StringComparison.Ordinal);
        Assert.Contains("\n\n", reasoning.Row.Text, StringComparison.Ordinal);
        Assert.DoesNotContain("agent.thought", reasoning.Row.Text, StringComparison.Ordinal);

        var prose = Assert.Single(items.OfType<ConversationItem.Prose>());
        Assert.True(items.ToList().IndexOf(reasoning) < items.ToList().IndexOf(prose), "the reasoning precedes the answer");
        Assert.All(items.OfType<ConversationItem.Event>(), e => Assert.StartsWith("acp.", e.Row.Kind, StringComparison.Ordinal));
    }

    /// <summary>
    /// <b>Ruling 100 (R-3).</b> <c>usage_update</c> and <c>available_commands_update</c> are
    /// bookkeeping: Console rows, Spend's feed — never items of the conversation, never counted in
    /// the thread's <i>N events</i> fold. Over the captured read run through the real mapper: both
    /// kinds are present in the rows (the positive control — the corpus has them), the constant
    /// carries the strings the mapper emits, no event item carries either, and the fold's count is
    /// the non-conversation rows less the bookkeeping rows. Every row of <c>Coalesce</c> is still
    /// there for the Console (M1).
    /// </summary>
    /// <remarks><b>Red observed</b>: <c>Expected: 0 · Actual: 8</c> event items of the two kinds (6 usage, 2 available-commands).</remarks>
    [Fact]
    public void TheBookkeepingKinds_AreNeverItems_AndTheFoldCountsTheRest()
    {
        var rows = Coalesce.Rows(Lines("read.jsonl"));
        var items = ConversationItems.Of(rows, live: false);

        Assert.Equal(["acp.session.update.usage_update", "acp.session.update.available_commands_update"], ConversationItems.BookkeepingKinds);
        Assert.Equal(6, rows.Count(r => r.Kind == "acp.session.update.usage_update"));               // read.jsonl:8, 12, 15, 19, 20, 21
        Assert.Equal(2, rows.Count(r => r.Kind == "acp.session.update.available_commands_update"));  // read.jsonl:5, 6
        var bookkeeping = rows.Count(r => ConversationItems.BookkeepingKinds.Contains(r.Kind));
        Assert.True(bookkeeping > 0, "the corpus carries no bookkeeping row; this fact measures nothing");

        Assert.Equal(0, items.OfType<ConversationItem.Event>().Count(e => ConversationItems.BookkeepingKinds.Contains(e.Row.Kind)));

        // The fold's count: every non-conversation row that is not bookkeeping.
        var nonConversation = rows.Count(r => r.Kind is not (Coalesce.MessageKind or Coalesce.ThoughtKind or ConversationItems.CallKind or ConversationItems.ResultKind));
        Assert.Equal(nonConversation - bookkeeping, items.OfType<ConversationItem.Event>().Count());
        Assert.True(items.OfType<ConversationItem.Event>().Any(), "no event survives the fold; the count is vacuous");
    }

    /// <summary>The corpus as the product's sink writes it: the mapper's event, the console model's text, the tool facts (the one writer's line).</summary>
    private static IReadOnlyList<EventLine> Lines(string file)
    {
        var mapper = new AcpRunEventMapper("run", "claude-code");
        return AcpCorpus.Lines(file)
            .Select(raw => mapper.Map(raw, T0))
            .Select(evt => new EventLine(evt.Ts, "claude-code", evt.Kind, ConsoleStreamModel.TextOf(evt), "run", ToolFacts.Of(evt)))
            .ToList();
    }
}
