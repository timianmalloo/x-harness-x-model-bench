using System.Text.Json.Nodes;
using AiDe.Core.AgentPlane;

namespace AiDe.Core.Presentation.Sessions;

/// <summary>
/// What one <c>tool.call</c> / <c>tool.result</c> frame <b>states</b> about a tool call — read once
/// from the wire at the one writer of a turn's lines (Ruling 82: each <c>tool.call</c> with its
/// <c>tool.result</c>s, attached by id, is one item). Every field but the id is null when the frame
/// did not carry it — <i>not stated</i>, never a default — because the adapter spreads one call
/// over several updates: the call arrives as <c>title: "Terminal"</c>, <c>status: "pending"</c>,
/// the real title and the input on a later <c>tool_call_update</c>, the status and the output on
/// the last (<c>frames/read.jsonl:9–14</c>). The fold over the call and its results is
/// <see cref="ConversationItems"/>'s.
/// </summary>
/// <param name="CallId">The wire's <c>toolCallId</c> — the join key.</param>
/// <param name="Kind">The wire's <c>kind</c>: <c>read</c> · <c>edit</c> · <c>execute</c> · <c>search</c> … — rendered as a word (1.1.1).</param>
/// <param name="Title">The wire's <c>title</c>.</param>
/// <param name="Status">The wire's <c>status</c>: <c>pending</c> · <c>in_progress</c> · <c>completed</c> · <c>failed</c>.</param>
/// <param name="Input">The wire's <c>rawInput</c>, one <c>key: value</c> line per field.</param>
/// <param name="Output">The wire's <c>rawOutput</c> when it is text, else the frame's <c>content[]</c> text joined.</param>
public sealed record ToolFacts(string CallId, string? Kind, string? Title, string? Status, string? Input, string? Output)
{
    /// <summary>The facts a mapped event states, or null when it is not a tool frame (no <c>toolCallId</c>).</summary>
    public static ToolFacts? Of(RunEvent evt)
    {
        ArgumentNullException.ThrowIfNull(evt);

        if (evt.Kind is not (ConversationItems.CallKind or ConversationItems.ResultKind) || Text(evt.Body["toolCallId"]) is not { } id)
        {
            return null;
        }

        return new ToolFacts(
            id,
            Text(evt.Body["kind"]),
            Text(evt.Body["title"]),
            Text(evt.Body["status"]),
            InputOf(evt.Body["rawInput"]),
            Text(evt.Body["rawOutput"]) ?? ContentText(evt.Body["content"]));
    }

    private static string? Text(JsonNode? node) =>
        node is JsonValue value && value.TryGetValue<string>(out var text) ? text : null;

    /// <summary><c>command: git status --short</c> — one line per field (the mockup's input shape); a non-string value as its JSON; null when the frame states no input (<c>rawInput</c> is an object in every frame of the corpus).</summary>
    private static string? InputOf(JsonNode? node) =>
        node is JsonObject { Count: > 0 } input
            ? string.Join('\n', input.Select(pair => pair.Key + ": " + (Text(pair.Value) ?? pair.Value?.ToJsonString() ?? "null")))
            : null;

    /// <summary>The text of every <c>content[]</c> block that carries one, joined; null when none does.</summary>
    private static string? ContentText(JsonNode? node)
    {
        var texts = ContentTexts(node).ToList();
        return texts.Count > 0 ? string.Join('\n', texts) : null;
    }

    /// <summary>
    /// The text of each <c>content[]</c> item that carries one — <c>{type: "content", content: {type:
    /// "text", text}}</c>, the corpus's one text shape — in order; a <c>diff</c> or <c>terminal</c>
    /// item yields nothing. The ONE reader of the array's text: the tool item's output joins them
    /// and the Console row's body summarises them (DM7).
    /// </summary>
    internal static IEnumerable<string> ContentTexts(JsonNode? node) =>
        (node as JsonArray)?.Select(item => Text(item?["content"]?["text"])).Where(text => text is not null).Select(text => text!) ?? [];
}
