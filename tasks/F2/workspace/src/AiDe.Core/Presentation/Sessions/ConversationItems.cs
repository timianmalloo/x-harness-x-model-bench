namespace AiDe.Core.Presentation.Sessions;

/// <summary>The status word of a tool item (DESIGN.md, the tool item row): <i>running · done · failed · interrupted</i>.</summary>
public enum ToolStatus
{
    /// <summary>No terminal status yet on a live turn — the ring.</summary>
    Running,

    /// <summary>The last result said <c>completed</c>.</summary>
    Done,

    /// <summary>The last result said <c>failed</c>.</summary>
    Failed,

    /// <summary>No terminal status on a turn that is no longer live: the lane ended before the tool answered — static, muted, never a ring.</summary>
    Interrupted,
}

/// <summary>
/// One item of a turn's conversation (Ruling 82), in event order: prose, reasoning, a tool call with
/// its results, or an event — a non-conversation row (<c>acp.*</c> less the two bookkeeping kinds
/// of Ruling 100, the conductor's lines, stderr, a result whose call is not in this turn) that
/// counts into <i>N events</i> and is never dropped from the Console.
/// </summary>
/// <param name="Row">The <see cref="Coalesce"/> row the item renders — the message, the thought, the call, or the event.</param>
public abstract record ConversationItem(TurnRow Row)
{
    /// <summary>An <c>agent.msg</c> row: the lane's prose, rendered as the markdown subset with no link activation.</summary>
    public sealed record Prose(TurnRow Row) : ConversationItem(Row);

    /// <summary>An <c>agent.thought</c> row: reasoning — collapsed, muted, plain text, never announced (SC9).</summary>
    public sealed record Reasoning(TurnRow Row) : ConversationItem(Row);

    /// <summary>
    /// A <c>tool.call</c> row with its <c>tool.result</c> rows attached by id: <i>kind · title ·
    /// status</i>, the detail on demand. The facets are the fold over what the call and each result
    /// stated (<see cref="ToolFacts"/>): the last stated value wins, the outputs join.
    /// </summary>
    /// <param name="Row">The call.</param>
    /// <param name="Results">Its results, in event order — empty when none arrived.</param>
    /// <param name="Live">Whether the turn is running or waiting: a call with no terminal status is then <i>running</i>, else <i>interrupted</i>.</param>
    public sealed record Tool(TurnRow Row, IReadOnlyList<TurnRow> Results, bool Live) : ConversationItem(Row)
    {
        private IEnumerable<ToolFacts> Frames => Results.Select(r => r.Tool).Prepend(Row.Tool).Where(f => f is not null)!;

        /// <summary>The last result's status: <c>completed</c> → done, <c>failed</c> → failed, else running on a live turn and interrupted otherwise.</summary>
        public ToolStatus Status => Frames.Select(f => f.Status).LastOrDefault(s => s is not null) switch
        {
            "completed" => ToolStatus.Done,
            "failed" => ToolStatus.Failed,
            _ => Live ? ToolStatus.Running : ToolStatus.Interrupted,
        };

        /// <summary>The last stated kind, as a word; empty when no frame stated one.</summary>
        public string Kind => Frames.Select(f => f.Kind).LastOrDefault(k => k is not null) ?? string.Empty;

        /// <summary>The last stated title, else the call row's text.</summary>
        public string Title => Frames.Select(f => f.Title).LastOrDefault(t => t is not null) ?? Row.Text;

        /// <summary>The last stated input; empty when none.</summary>
        public string Input => Frames.Select(f => f.Input).LastOrDefault(i => i is not null) ?? string.Empty;

        /// <summary>The results' outputs joined; empty when none.</summary>
        public string Output => string.Join('\n', Results.Select(r => r.Tool?.Output).Where(o => o is not null));
    }

    /// <summary>A non-conversation row: folded into <i>N events</i>, rendered as an event line, never as an item.</summary>
    public sealed record Event(TurnRow Row) : ConversationItem(Row);
}

/// <summary>
/// The ONE projection from <c>Coalesce(turn.Events)</c> to the conversation's items (Ruling 82) —
/// pure, read by the thread's reply side; the Console split reads the rows beneath it (DM7: one
/// derivation, two readers). There is no grouping rule: each <c>tool.call</c> is one item (the
/// review's §7, the Simplifier's veto on D3's run-of-four grouping).
/// </summary>
public static class ConversationItems
{
    /// <summary>The mapper's <c>tool_call</c>.</summary>
    public const string CallKind = "tool.call";

    /// <summary>The mapper's <c>tool_call_update</c>.</summary>
    public const string ResultKind = "tool.result";

    /// <summary>
    /// The bookkeeping kinds (Ruling 100, the Owner's extension of Ruling 82): <c>usage_update</c>
    /// and <c>available_commands_update</c> as the mapper spells them — <c>acp.session.update.</c>
    /// plus the wire discriminator (<c>frames/read.jsonl:5–8</c>). They stay Console rows and feed
    /// Spend (Ruling 78); they are never items of the conversation and never count in the thread's
    /// <i>N events</i> fold — a fold reading <i>14 events</i> over four usage rows misleads about
    /// what the agent did. A named list of two, never a pattern: <c>acp.result</c> and the rest of
    /// <c>acp.*</c> still fold.
    /// </summary>
    public static readonly IReadOnlyList<string> BookkeepingKinds =
    [
        "acp.session.update.usage_update",
        "acp.session.update.available_commands_update",
    ];

    /// <summary>The items of a turn's rows, in the rows' order. <paramref name="live"/>: the turn is running or waiting, so a call with no terminal status is <i>running</i>, not <i>interrupted</i>.</summary>
    public static IReadOnlyList<ConversationItem> Of(IReadOnlyList<TurnRow> rows, bool live)
    {
        ArgumentNullException.ThrowIfNull(rows);

        // A result belongs to the call with its id that PRECEDES it; a result with no such call is an
        // event row (never dropped, never a call's by position — attribution is a property of the row).
        var calls = new Dictionary<string, List<TurnRow>>(StringComparer.Ordinal);
        var items = new List<ConversationItem>(rows.Count);
        foreach (var row in rows)
        {
            switch (row.Kind)
            {
                case Coalesce.MessageKind:
                    items.Add(new ConversationItem.Prose(row));
                    break;
                case Coalesce.ThoughtKind:
                    items.Add(new ConversationItem.Reasoning(row));
                    break;
                case CallKind:
                    var results = new List<TurnRow>();
                    if (row.Tool is { } call)
                    {
                        calls[call.CallId] = results;   // the item's list, filled as its results arrive below
                    }

                    items.Add(new ConversationItem.Tool(row, results, live));
                    break;
                case ResultKind when row.Tool is { } result && calls.TryGetValue(result.CallId, out var attached):
                    attached.Add(row);
                    break;
                case var kind when BookkeepingKinds.Contains(kind, StringComparer.Ordinal):
                    break;   // Console-only (Ruling 100): the row stays in Rows for the split and for Spend; the fold never sees it
                default:
                    items.Add(new ConversationItem.Event(row));
                    break;
            }
        }

        return items;
    }

    /// <summary>The status word: <i>running · done · failed · interrupted</i> — the member's name, lower-cased (the goldens pin the four words).</summary>
    public static string StatusWord(ToolStatus status) => status.ToString().ToLowerInvariant();
}
