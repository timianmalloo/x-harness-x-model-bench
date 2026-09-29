namespace AiDe.Core.Presentation.Sessions;

/// <summary>
/// One row of a turn's conversation at the message grain (Ruling 81): a message or a thought folded
/// from its wire chunks, or one event of any other kind.
/// </summary>
/// <param name="At">The first chunk's receipt time.</param>
/// <param name="Lane">The lane that produced every chunk of the row.</param>
/// <param name="Kind">The event kind, verbatim — <c>agent.msg</c>, <c>agent.thought</c>, <c>tool.call</c> …</param>
/// <param name="Text">The chunks' text joined in order; an unfolded event's own text.</param>
/// <param name="Chunks">How many wire chunks fold into this row; null for a kind that is one row per event.</param>
/// <param name="Tool">The tool frame's stated facts, carried from the one event of a <c>tool.call</c> / <c>tool.result</c> row; null otherwise.</param>
public sealed record TurnRow(DateTimeOffset At, string Lane, string Kind, string Text, int? Chunks, ToolFacts? Tool = null);

/// <summary>
/// <c>Coalesce(turn.Events)</c> — the ONE pure fold from a turn's event lines to its rows, read by
/// the thread's reply side and by the Console split (Ruling 81; DM7: one derivation, two readers).
/// </summary>
public static class Coalesce
{
    /// <summary>The mapper's <c>agent_message_chunk</c>: assistant prose, folded per message.</summary>
    public const string MessageKind = "agent.msg";

    /// <summary>The mapper's <c>agent_thought_chunk</c> (Ruling 82, CV-5.3): reasoning, folded per thought — its own run, never merged with prose.</summary>
    public const string ThoughtKind = "agent.thought";

    /// <summary>The rows of a turn's events, in order. Pure: the same events give the same rows.</summary>
    /// <remarks>
    /// A run is a maximal stretch of one folding kind from ONE lane — a row carries one lane, so a
    /// second lane's chunk starts a new row rather than being attributed to the first (R16 b1:
    /// attribution is a property of the row, never a guess). Any non-folding event, and any change
    /// of kind, ends the run (Ruling 81 condition 2: the boundary is the interleaving).
    /// </remarks>
    public static IReadOnlyList<TurnRow> Rows(IReadOnlyList<EventLine> events)
    {
        ArgumentNullException.ThrowIfNull(events);

        var rows = new List<TurnRow>(events.Count);
        for (var start = 0; start < events.Count;)
        {
            var first = events[start];
            var folds = Folds(first.Kind);
            var end = start + 1;
            if (folds)
            {
                while (end < events.Count && Continues(first, events[end]))
                {
                    end++;
                }
            }

            var text = end - start == 1 ? first.Text : string.Concat(events.Skip(start).Take(end - start).Select(e => e.Text));
            rows.Add(new TurnRow(first.At, first.Lane, first.Kind, text, folds ? end - start : null, folds ? null : first.Tool));
            start = end;
        }

        return rows;
    }

    /// <summary>Whether a kind arrives in wire chunks and folds to one row per run.</summary>
    private static bool Folds(string kind) =>
        string.Equals(kind, MessageKind, StringComparison.Ordinal) || string.Equals(kind, ThoughtKind, StringComparison.Ordinal);

    /// <summary>The same folding kind from the same lane continues the run (<paramref name="run"/>'s kind folds by construction).</summary>
    private static bool Continues(EventLine run, EventLine line) =>
        string.Equals(line.Kind, run.Kind, StringComparison.Ordinal)
        && string.Equals(line.Lane, run.Lane, StringComparison.Ordinal);
}
