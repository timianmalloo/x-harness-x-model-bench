using System.Text.Json.Nodes;
using AiDe.Core.AgentPlane;

namespace AiDe.Core.Presentation.Sessions;

/// <summary>
/// One line of the merged Console stream, carrying the lane it came from (R16 b1's "lane rail":
/// attribution is a property of the row, never a guess made at render time).
/// </summary>
/// <param name="Ordinal">The producing lane's own <see cref="RunEvent.Seq"/> — see the model's remarks.</param>
/// <param name="LaneId">Which lane produced it.</param>
/// <param name="LaneName">That lane's display name, resolved once at append.</param>
/// <param name="Kind">The <see cref="RunEvent.Kind"/>, verbatim.</param>
/// <param name="Text">What to show. Never null; an event with no text reads as its kind.</param>
public sealed record ConsoleRow(long Ordinal, string LaneId, string LaneName, string Kind, string Text);

/// <summary>One lane on the rail: who it is, how much it has said, and whether it is shown.</summary>
public sealed record ConsoleRail(string LaneId, string LaneName, int Rows, bool Visible);

/// <summary>
/// One node of the filter tree: a lane, or one event kind within a lane. Excluding a node hides
/// every row beneath it.
/// </summary>
/// <param name="LaneId">The lane this node belongs to.</param>
/// <param name="Kind">Null for the lane node itself; an event kind for a child.</param>
/// <param name="Label">What the tree shows.</param>
/// <param name="Rows">How many rows sit under it.</param>
/// <param name="Visible">Whether it is currently included.</param>
public sealed record ConsoleFilterNode(string LaneId, string? Kind, string Label, int Rows, bool Visible);

/// <summary>
/// The merged Console stream across every lane of one session (R16 b1) — rows, the lane rail, and
/// the filter tree over them.
/// </summary>
/// <remarks>
/// <para><b>The ordinal is the lane's own sequence, not a counter this type invents.</b>
/// <see cref="AcpRunEventMapper"/> assigns <see cref="RunEvent.Seq"/> at receipt, so a gap in what
/// the console holds is a gap in what the console <i>received</i> — which is exactly the question
/// the retain-never-rebuild clause asks. A second monotonic counter here would renumber whatever
/// arrived and make every rebuild look contiguous (DM7: two definitions of one quantity).</para>
///
/// <para><b>Filtering hides rows; it never drops them.</b> <see cref="Rows"/> is the record and
/// <see cref="VisibleRows"/> is the view, so excluding a lane cannot silently destroy history and
/// <see cref="OrdinalGaps"/> keeps answering about what arrived rather than about what is on
/// screen.</para>
/// </remarks>
public sealed class ConsoleStreamModel
{
    private readonly List<ConsoleRow> _rows = [];
    private readonly Dictionary<string, string> _laneNames = new(StringComparer.Ordinal);
    private readonly List<string> _laneOrder = [];
    private readonly HashSet<string> _hiddenLanes = new(StringComparer.Ordinal);
    private readonly HashSet<(string Lane, string Kind)> _hiddenKinds = [];

    /// <summary>
    /// Guards every read and write. <b>A merged stream is written by more than one lane by
    /// definition</b> — that is what "merged" means — and each lane drains its own queue on its own
    /// thread.
    /// </summary>
    /// <remarks>
    /// <para><b>The evidence for the two halves of this is not equal, and the weaker half is
    /// labelled rather than rounded up.</b></para>
    ///
    /// <para><b>Snapshot reads: verified, deterministically.</b> <see cref="Rows"/> used to hand
    /// back the live list, so a consumer enumerating it while a lane appended threw — and
    /// <c>ConsoleSurface.Render</c> is exactly such a <c>foreach</c>. That needs no interleaving to
    /// reproduce, because a <see cref="List{T}"/> enumerator checks its version on every step:
    /// <c>AReaderIsNeverEnumeratingAListALaneCanStillAppendTo</c> was observed red <b>10 of 10</b>
    /// runs against the pre-fix shape, with <c>InvalidOperationException: Collection was
    /// modified</c>, and green 10 of 10 after.</para>
    ///
    /// <para><b>Torn concurrent writes: NOT RECORDED.</b> That two <c>Add</c> calls cannot
    /// interleave destructively is <i>not</i> proven here and is not claimed to be.
    /// <c>ConcurrentLanesNeverLoseARow</c> is a <b>measurement</b>: without the lock it failed 10 of
    /// 10 runs (one observed loss, 983 of 1000 rows) and with it passed 10 of 10 — a rate, not a
    /// certainty, and a lock verified by an intermittent no longer appearing is absence of evidence.
    /// <b>What would confirm it:</b> an injectable rendezvous inside this locked region, or a
    /// runtime that enumerates thread interleavings. The first would mean shipping a seam that
    /// exists only for its own test, so it was refused; the second does not exist here.</para>
    /// </remarks>
    private readonly Lock _gate = new();

    /// <summary>Every row that ever arrived, in receipt order.</summary>
    public IReadOnlyList<ConsoleRow> Rows
    {
        get
        {
            lock (_gate)
            {
                return [.. _rows];
            }
        }
    }

    /// <summary>The rows the filter currently includes.</summary>
    public IReadOnlyList<ConsoleRow> VisibleRows
    {
        get
        {
            lock (_gate)
            {
                return [.. _rows.Where(
                    r => !_hiddenLanes.Contains(r.LaneId) && !_hiddenKinds.Contains((r.LaneId, r.Kind)))];
            }
        }
    }

    /// <summary>Raised after any append or filter change, so a view can re-read.</summary>
    public event Action? Changed;

    /// <summary>The lane rail, in first-seen order.</summary>
    public IReadOnlyList<ConsoleRail> Rail
    {
        get
        {
            lock (_gate)
            {
                return
                [
                    .. _laneOrder.Select(id => new ConsoleRail(
                        id,
                        _laneNames[id],
                        _rows.Count(r => string.Equals(r.LaneId, id, StringComparison.Ordinal)),
                        !_hiddenLanes.Contains(id))),
                ];
            }
        }
    }

    /// <summary>The filter tree: one node per lane, one child per kind that lane has produced.</summary>
    public IReadOnlyList<ConsoleFilterNode> FilterTree
    {
        get
        {
            lock (_gate)
            {
                return FilterTreeUnsafe();
            }
        }
    }

    /// <summary>Builds the tree. The caller holds <see cref="_gate"/>.</summary>
    private List<ConsoleFilterNode> FilterTreeUnsafe()
    {
        var nodes = new List<ConsoleFilterNode>();

        foreach (var lane in _laneOrder)
        {
            var laneRows = _rows.Where(r => string.Equals(r.LaneId, lane, StringComparison.Ordinal)).ToList();
            nodes.Add(new ConsoleFilterNode(
                lane, null, _laneNames[lane], laneRows.Count, !_hiddenLanes.Contains(lane)));

            foreach (var kind in laneRows.Select(r => r.Kind).Distinct(StringComparer.Ordinal).Order(StringComparer.Ordinal))
            {
                nodes.Add(new ConsoleFilterNode(
                    lane,
                    kind,
                    kind,
                    laneRows.Count(r => string.Equals(r.Kind, kind, StringComparison.Ordinal)),
                    !_hiddenLanes.Contains(lane) && !_hiddenKinds.Contains((lane, kind))));
            }
        }

        return nodes;
    }

    /// <summary>Appends one lane event to the merged stream.</summary>
    public void Append(string laneId, string laneName, RunEvent evt)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(laneId);
        ArgumentNullException.ThrowIfNull(evt);

        lock (_gate)
        {
            if (!_laneNames.ContainsKey(laneId))
            {
                _laneNames[laneId] = string.IsNullOrWhiteSpace(laneName) ? laneId : laneName;
                _laneOrder.Add(laneId);
            }

            _rows.Add(new ConsoleRow(evt.Seq, laneId, _laneNames[laneId], evt.Kind, TextOf(evt)));
        }

        // Outside the lock: a subscriber marshals to the UI thread, and holding a lock across that
        // hand-off is how a render and an append deadlock against each other.
        Changed?.Invoke();
    }

    /// <summary>Includes or excludes a whole lane.</summary>
    public void SetLaneVisible(string laneId, bool visible)
    {
        lock (_gate)
        {
            if (visible)
            {
                _hiddenLanes.Remove(laneId);
            }
            else
            {
                _hiddenLanes.Add(laneId);
            }
        }

        Changed?.Invoke();
    }

    /// <summary>Includes or excludes one event kind within one lane.</summary>
    public void SetKindVisible(string laneId, string kind, bool visible)
    {
        lock (_gate)
        {
            if (visible)
            {
                _hiddenKinds.Remove((laneId, kind));
            }
            else
            {
                _hiddenKinds.Add((laneId, kind));
            }
        }

        Changed?.Invoke();
    }

    /// <summary>
    /// Ordinals this lane never delivered, from 1 up to the highest it did — the positive oracle for
    /// "no event was lost".
    /// </summary>
    /// <remarks>
    /// Empty is the only passing answer. A console that was rebuilt starts its history at whatever
    /// arrived after the rebuild, so every ordinal before that reads here as missing — which is the
    /// difference <c>Assert.Same</c> cannot see.
    /// </remarks>
    public IReadOnlyList<long> OrdinalGaps(string laneId)
    {
        HashSet<long> seen;

        lock (_gate)
        {
            seen = [.. _rows
                .Where(r => string.Equals(r.LaneId, laneId, StringComparison.Ordinal))
                .Select(r => r.Ordinal)];
        }

        if (seen.Count == 0)
        {
            return [];
        }

        var highest = seen.Max();
        return [.. Enumerable.Range(1, (int)highest).Select(i => (long)i).Where(o => !seen.Contains(o))];
    }

    /// <summary>
    /// What a row shows: the event's own text when it carries one, else its kind. Public so the
    /// session thread's fold (CV-1) reads the same definition of a line's text — one derivation,
    /// two readers (DM7).
    /// </summary>
    /// <remarks>
    /// <b>The two shapes are the mapper's, read rather than guessed.</b> An <c>agent.msg</c> body is
    /// the lifted <c>update</c>, whose text sits at <c>content.text</c>; a <c>permission.request</c>
    /// body is the lifted <c>params</c>, whose text sits at <c>title</c>. Falling back to the kind is
    /// deliberate: a row with no text field reads as an event with nothing in it rather than as one
    /// this projection did not recognise, and the kind is always true. <b>A text field that IS
    /// present is the text, whitespace included</b>: a wire chunk of two newlines is the paragraph
    /// break between two chunks of one thought (<c>frames/thought.jsonl:27</c>), and a blank-means-absent
    /// reading folded the literal kind into the reasoning (DC-187 (CV-5-3 a)).
    /// <para><b>A tool result never reads its kind (Ruling 101).</b> A <c>tool_call_update</c> with
    /// no <c>title</c> carries its text in <c>content[]</c> — ACP's <c>ToolCallContent</c> items,
    /// <c>{type: "content", content: {type: "text", text}}</c> beside <c>diff</c> and <c>terminal</c>
    /// items (<c>frames/write.jsonl:13</c>, <c>:11</c>) — or, for the adapter's Bash results, in a
    /// <c>rawOutput</c> string with no array at all (<c>frames/read.jsonl:14</c>); one update carries
    /// nothing but <c>_meta</c> (<c>read.jsonl:13</c>). The row reads the first text line and the
    /// total text bytes, <i>no text content (n items: types)</i> when no item carries text, and the
    /// zero-item form when nothing does — because <c>tool.result   tool.result</c> is a row saying
    /// nothing in the shape of a value (IO: never a plausible wrong number).</para>
    /// </remarks>
    public static string TextOf(RunEvent evt) =>
        Text(evt.Body)
        ?? (evt.Body["content"] is JsonObject content ? Text(content) : null)
        ?? (evt.Body["content"] is JsonArray items ? ToolContentText(items) : null)
        ?? (evt.Kind == ConversationItems.ResultKind ? ToolResultText(evt.Body) : null)
        ?? evt.Kind;

    /// <summary>The first text item's first line and the items' total text bytes; the no-text form over the items' types when none carries text.</summary>
    private static string ToolContentText(JsonArray items)
    {
        var texts = ToolFacts.ContentTexts(items).ToList();
        if (texts.Count > 0)
        {
            return FirstLineAndBytes(texts[0], texts.Sum(System.Text.Encoding.UTF8.GetByteCount));
        }

        var types = items.Select(item => TextValue(item?["content"]?["type"]) ?? TextValue(item?["type"]) ?? "unknown");
        return NoTextContent(items.Count, string.Join(", ", types));
    }

    /// <summary>A result with no content array: its <c>rawOutput</c> string in the same form, else the zero-item form — the kind is never the body.</summary>
    private static string ToolResultText(JsonObject body) =>
        TextValue(body["rawOutput"]) is { } raw ? FirstLineAndBytes(raw, System.Text.Encoding.UTF8.GetByteCount(raw)) : NoTextContent(0, null);

    private static string FirstLineAndBytes(string text, int bytes)
    {
        var newline = text.IndexOf('\n', StringComparison.Ordinal);
        var firstLine = (newline < 0 ? text : text[..newline]).TrimEnd('\r');
        return string.Create(System.Globalization.CultureInfo.InvariantCulture, $"{firstLine} · {bytes} bytes");
    }

    private static string NoTextContent(int count, string? types) =>
        string.Create(System.Globalization.CultureInfo.InvariantCulture, $"no text content ({count} {(count == 1 ? "item" : "items")}{(string.IsNullOrEmpty(types) ? string.Empty : ": " + types)})");

    private static string? TextValue(JsonNode? node) =>
        node is JsonValue value && value.TryGetValue<string>(out var text) ? text : null;

    private static string? Text(JsonObject body)
    {
        foreach (var field in (string[])["text", "message", "title"])
        {
            if (body.TryGetPropertyValue(field, out var node) && node is JsonValue value
                && value.TryGetValue<string>(out var text))
            {
                return text;
            }
        }

        return null;
    }
}
