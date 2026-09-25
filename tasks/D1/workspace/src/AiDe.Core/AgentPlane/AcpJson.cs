using System.Text.Json.Nodes;

namespace AiDe.Core.AgentPlane;

/// <summary>
/// The plane's one reader for a string off a JSON node.
/// </summary>
/// <remarks>
/// <b>One reader, because three could disagree.</b> The lane client, the run-event mapper and the
/// seam ledger each carried an identical private copy, so any change to what a non-string node
/// means would have had to land in three places to be true — and would have been quietly true in
/// only some of them. Call sites qualify it (<c>AcpJson.Text</c>) rather than importing it, so the
/// shared reader is visible at the point of use.
/// </remarks>
internal static class AcpJson
{
    /// <summary>The node's string value, or <c>null</c> when it is absent or is not a string.</summary>
    internal static string? Text(JsonNode? node)
        => node is JsonValue value && value.TryGetValue<string>(out var text) ? text : null;
}
