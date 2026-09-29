using System.Text.Json;
using System.Text.Json.Nodes;

namespace AiDe.Core.AgentPlane;

/// <summary>
/// The <b>one</b> mapper from ACP wire frames to <see cref="RunEvent"/>. Pattern: Anti-Corruption
/// Layer — the single seam that keeps adapter vocabulary out of the plane.
/// </summary>
/// <remarks>
/// <para><b>One source, one mapper.</b> Spec §7.2 describes one envelope over four sources; Phase 1
/// has ACP and nothing else. A second mapper appearing before a second source does is the defined
/// failure of this node — the envelope would then be a shape two writers agree on by luck rather
/// than a contract one writer owns.</para>
///
/// <para><b>Recognition is a table, not a handler per kind.</b> Five wire shapes have a Phase-1
/// producer and are projected onto v1 kinds; everything else is namespaced <c>acp.*</c> and carried
/// whole under <c>Ext</c>. Adding a kind is adding a row, and an adapter release that invents one
/// needs no change at all — §7.2's "consumers ignore unknown kinds", implemented rather than
/// restated.</para>
///
/// <para><b>Nothing is dropped, ever.</b> A recognized frame's payload moves to <c>body</c> and the
/// remaining envelope stays in <c>Ext</c>; an unrecognized frame goes to <c>Ext</c> entire. Either
/// way every field of the original frame is present exactly once, which is what the captured-corpus
/// round-trip proves over every frame in the corpus (enumerated from disk, never counted here — DC-184).</para>
///
/// <para><b>Identity, ordering and time come from the plane.</b> ACP frames carry no run id, no
/// sequence and no timestamp. <c>Seq</c> is assigned here and <c>Ts</c> is stamped at receipt —
/// the same discipline as <c>OtelSpanMapper</c>'s <c>recordedAt</c>, for the same reason: a value
/// taken from the wire would be a claim, not a measurement.</para>
/// </remarks>
public sealed class AcpRunEventMapper
{
    /// <summary><c>session/update</c> discriminators with a Phase-1 producer, mapped to v1 kinds.</summary>
    private static readonly Dictionary<string, string> RecognizedSessionUpdates = new(StringComparer.Ordinal)
    {
        ["agent_message_chunk"] = "agent.msg",
        ["agent_thought_chunk"] = "agent.thought",   // Ruling 82; the shape Verified from frames/thought.jsonl (CV-5.3)
        ["tool_call"] = "tool.call",
        ["tool_call_update"] = "tool.result",
    };

    /// <summary>Top-level methods with a Phase-1 producer, mapped to v1 kinds.</summary>
    private static readonly Dictionary<string, string> RecognizedMethods = new(StringComparer.Ordinal)
    {
        ["session/request_permission"] = "permission.request",
    };

    private long seq;

    /// <param name="runId">The governed run every event from this lane belongs to.</param>
    /// <param name="agentId">The lane's agent identity.</param>
    public AcpRunEventMapper(string runId, string agentId)
    {
        RunId = runId;
        AgentId = agentId;
    }

    /// <summary>The run every mapped event is stamped with.</summary>
    public string RunId { get; }

    /// <summary>The agent every mapped event is stamped with.</summary>
    public string AgentId { get; }

    /// <summary>
    /// Maps one newline-delimited ACP frame. <paramref name="receivedAt"/> is stamped by the reader,
    /// never read from the frame.
    /// </summary>
    /// <exception cref="AgentPlaneException">
    /// <see cref="AgentPlaneErrorCodes.MalformedFrame"/> when the line is not a JSON object, so it
    /// carries no event at all. Refused rather than swallowed: a line the reader cannot understand
    /// is a contract break, and silently returning nothing would make it invisible.
    /// </exception>
    public RunEvent Map(string frameLine, DateTimeOffset receivedAt)
    {
        var frame = Parse(frameLine);
        var ordinal = Interlocked.Increment(ref seq);

        var method = AcpJson.Text(frame["method"]);
        var parameters = frame["params"] as JsonObject;
        var update = parameters?["update"] as JsonObject;
        var sessionUpdate = update is null ? null : AcpJson.Text(update["sessionUpdate"]);

        var cost = CostOf(frame["result"] as JsonObject);

        string kind;
        var body = new JsonObject();

        if (method == "session/update" && sessionUpdate is not null)
        {
            if (RecognizedSessionUpdates.TryGetValue(sessionUpdate, out var recognized))
            {
                kind = recognized;
                body = Lift(parameters!, "update");
            }
            else
            {
                kind = "acp.session.update." + sessionUpdate;
            }
        }
        else if (method is not null)
        {
            if (RecognizedMethods.TryGetValue(method, out var recognized) && parameters is not null)
            {
                kind = recognized;
                body = Lift(frame, "params");
            }
            else
            {
                kind = "acp." + method.Replace('/', '.');
            }
        }
        else
        {
            // A response, or something that is neither. The frame is carried whole: correlating a
            // response to its request is state the client owns, not something a stateless mapping
            // can invent from one line.
            kind = frame["error"] is not null ? "acp.error"
                : frame["result"] is not null ? "acp.result"
                : "acp.frame";
        }

        return new RunEvent(
            RunId,
            AgentId,
            ParentAgentId: null,
            ordinal,
            receivedAt,
            kind,
            cost,
            body,
            frame);
    }

    /// <summary>
    /// Detaches <paramref name="key"/> from <paramref name="owner"/> and returns it as the body.
    /// Cloned before removal so the node is unambiguously unparented, whatever a future
    /// <c>JsonObject.Remove</c> does about detaching.
    /// </summary>
    private static JsonObject Lift(JsonObject owner, string key)
    {
        var payload = ((JsonObject)owner[key]!).DeepClone().AsObject();
        owner.Remove(key);
        return payload;
    }

    private static JsonObject Parse(string frameLine)
    {
        JsonNode? node;
        try
        {
            node = JsonNode.Parse(frameLine);
        }
        catch (JsonException error)
        {
            throw new AgentPlaneException(
                AgentPlaneErrorCodes.MalformedFrame,
                "ACP frame is not valid JSON: " + error.Message);
        }

        return node as JsonObject
            ?? throw new AgentPlaneException(
                AgentPlaneErrorCodes.MalformedFrame,
                "ACP frame is valid JSON but not an object, so it carries no event");
    }

    /// <summary>
    /// Reads the cost the wire states, and only that. Absent usage yields <c>null</c>, never a zero
    /// — "not recorded" and "cost nothing" are different facts (IO12).
    /// </summary>
    private static RunEventCost? CostOf(JsonObject? result)
    {
        if (result?["usage"] is not JsonObject usage)
        {
            return null;
        }

        // Requests is 1 because this frame IS one completed engine request. Counting turns is the
        // client's job once it correlates ids; a mapper that guessed higher would be inventing.
        return new RunEventCost(
            Number(usage["inputTokens"]),
            Number(usage["outputTokens"]),
            Number(usage["cachedReadTokens"]),
            Requests: 1);
    }

    private static long Number(JsonNode? node)
        => node is JsonValue value && value.TryGetValue<long>(out var number) ? number : 0;
}
