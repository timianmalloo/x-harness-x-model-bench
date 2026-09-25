using System.Text.Json;
using System.Text.Json.Nodes;
using AiDe.Core.AgentPlane;
using AiDe.Core.Sessions;

namespace AiDe.Core.Tests.Sessions;

/// <summary>
/// F0 clause 4 (docs/plans/conductor-front-door.md): <c>session.open</c> and <c>session.config</c>
/// ride <see cref="RunEvent"/>'s open <c>Kind</c> string. <c>RunEvent</c>'s own remarks state the
/// rule ("evolution is additive only; consumers ignore unknown kinds") — this proves it rather than
/// re-asserting it, and proves it for a kind nobody has invented yet, not just the two named here.
/// Fails if: the envelope's schema changes to accommodate this.
/// </summary>
public sealed class SessionEventEnvelopeTests
{
    [Theory]
    [InlineData(SessionEventKinds.Open)]
    [InlineData(SessionEventKinds.Config)]
    [InlineData("session.something-nobody-has-invented-yet")]
    public void RunEvent_SurvivesRoundTripWithASessionKind_NoSchemaChangeNeeded(string kind)
    {
        var original = new RunEvent(
            RunId: "run-1",
            AgentId: "agent-1",
            ParentAgentId: null,
            Seq: 1,
            Ts: DateTimeOffset.UtcNow,
            Kind: kind,
            Cost: null,
            Body: new JsonObject { ["enabledBackends"] = new JsonArray("claude-code") },
            Ext: new JsonObject());

        var json = JsonSerializer.Serialize(original);
        var roundTripped = JsonSerializer.Deserialize<RunEvent>(json);

        Assert.NotNull(roundTripped);
        Assert.Equal(original.RunId, roundTripped!.RunId);
        Assert.Equal(original.AgentId, roundTripped.AgentId);
        Assert.Equal(original.Seq, roundTripped.Seq);
        Assert.Equal(original.Kind, roundTripped.Kind);
        Assert.True(
            JsonNode.DeepEquals(original.Body, roundTripped.Body),
            "Body must survive verbatim for an unrecognized/new kind — that is the whole point of the open string.");
    }
}
