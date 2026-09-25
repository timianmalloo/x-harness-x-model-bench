using System.Text.Json.Nodes;
using AiDe.Core.AgentPlane;

namespace AiDe.Core.Tests.AgentPlane;

/// <summary>
/// A lane that asks for summarized thinking sends it through the adapter's <c>_meta</c> slot as the
/// SDK's <c>ThinkingAdaptive</c> shape; a lane that does not ask sends nothing new.
/// </summary>
/// <remarks>
/// <para><b>Red-first (CV-5.3's routed finding, 2026-09-13).</b> Recent models default
/// <c>thinking.display</c> to <c>"omitted"</c>: the adapter receives signature-only thinking blocks
/// with empty text and forwards no <c>agent_thought_chunk</c> at all (adapter 0.75.1
/// <c>acp-agent.js:7742-7745</c>, Verified). The product's <c>agent.thought</c> row (Ruling 82)
/// therefore never fires from a lane that does not ask. The SDK's option is
/// <c>thinking: { type: 'adaptive', display: 'summarized' | 'omitted' }</c> (<c>sdk.d.ts:8448-8451</c>,
/// Verified); CV-5.3's probe captured 19 thought frames by sending exactly that.</para>
/// <para>The compile session (<see cref="LaneSessionOptions.Compile"/>) does not ask: its output is a
/// decoration, reasoning display would cost tokens for nothing to render, and its pin identity
/// (<c>CE-0023</c>) compares the record's <c>_meta</c> — adding a member there would re-open gate 1.</para>
/// </remarks>
public sealed class AcpLaneClientThinkingDisplayTests
{
    [Fact]
    public void ALaneThatAsksForSummarizedThinking_SendsTheSdkShape()
    {
        var options = new LaneSessionOptions(DisallowedTools: ["Bash"]) { ThinkingDisplay = "summarized" };

        var meta = options.ToMeta();

        var thinking = Assert.IsType<JsonObject>(meta!["claudeCode"]!["options"]!["thinking"]);
        Assert.Equal("adaptive", thinking["type"]!.GetValue<string>());
        Assert.Equal("summarized", thinking["display"]!.GetValue<string>());
        Assert.Equal(["disallowedTools", "thinking"], meta["claudeCode"]!["options"]!.AsObject().Select(m => m.Key));
    }

    [Fact]
    public void ALaneThatDoesNotAsk_SendsNoThinkingMember()
    {
        var meta = new LaneSessionOptions(DisallowedTools: ["Bash"]).ToMeta();

        Assert.False(meta!["claudeCode"]!["options"]!.AsObject().ContainsKey("thinking"));
    }

    [Fact]
    public void TheCompileSessionDoesNotAsk()
    {
        Assert.Null(LaneSessionOptions.Compile.ThinkingDisplay);
        Assert.False(LaneSessionOptions.Compile.ToMeta()!["claudeCode"]!["options"]!.AsObject().ContainsKey("thinking"));
    }

    [Theory]
    [InlineData("")]
    [InlineData("verbose")]
    public void OnlyTheSdksTwoValuesAreAccepted(string display)
    {
        var options = new LaneSessionOptions(DisallowedTools: ["Bash"]) { ThinkingDisplay = display };

        Assert.Throws<ArgumentException>(() => options.ToMeta());
    }
}
