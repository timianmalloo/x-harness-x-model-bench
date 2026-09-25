using System.Diagnostics;
using System.Text.Json.Nodes;
using AiDe.Core.AgentPlane;
using AiDe.Core.PromptCompilation;
using AiDe.Core.Sessions;

namespace AiDe.Core.Tests.Compilation;

/// <summary>
/// §A10.2's table and §A11's tenth string, table-driven: one string per <c>called.outcome</c>, in
/// voice, parameterised on <c>reason</c>; the line is <b>absent</b> under <c>mechanical-only</c> with
/// nothing supplied (E5) and names who supplied the structure when the call was skipped.
/// </summary>
public sealed class TheCompileLineHasTenStringsTests
{
    private static Envelope With(Called? call)
    {
        var rows = new List<EnvelopeEvent>
        {
            new Opened("e1", "text", "s", "claude-code", CompileModes.Agentic, null, PreCompile.ConstantsFor("1")),
            new Decorated("e1", DecorationNames.FamilyProfile, new JsonObject { ["family"] = "anthropic", ["version"] = null, ["sha"] = null }, DecorationSources.Mechanical),
        };
        if (call is not null)
        {
            rows.Add(call);
        }

        return Envelope.Pending(rows);
    }

    private static Called Call(string outcome, string? reason = null, int toolCalls = 0, int permissions = 0) => new(
        "e1", "claude-code", "claude-sonnet-5", "claude-opus-5[1m]", 812, null, outcome, reason,
        "inputs", "prompt", CompileContract.Version, permissions, toolCalls, DroppedCounts.None);

    public static TheoryData<string, string?, string> Rows => new()
    {
        { CallOutcomes.Unavailable, "needs-login", "compiled mechanically — needs-login" },
        { CallOutcomes.Refused, "AP-0011 not a subscription", "compiled mechanically — AP-0011 not a subscription" },
        { CallOutcomes.TimedOut, "compile bound 60000 ms exceeded at prompt", "compiled mechanically — compile bound 60000 ms exceeded at prompt" },
        { CallOutcomes.Malformed, "parse: the output is not one JSON object", "compiled mechanically — parse: the output is not one JSON object" },
        { CallOutcomes.Cancelled, "cancelled — draft edited", "compiled mechanically — cancelled — draft edited" },
        { CallOutcomes.SucceededNoStructure, null, "no goal block proposed; sends as a message" },
        { CallOutcomes.Succeeded, null, "Compiled on claude-opus-5[1m] · anthropic · read 0 turns · goal block filled by the model, one lease" },
        { CallOutcomes.Reused, "reused_from:e0#7", "Compiled on claude-opus-5[1m] · anthropic · reused, no new request" },
    };

    [Theory]
    [MemberData(nameof(Rows))]
    public void EachOutcomeHasItsStringInVoice(string outcome, string? reason, string expected)
    {
        var line = CompileLine.For(With(Call(outcome, reason)), tierRationale: "goal block filled by the model, one lease");

        Assert.Equal(expected, line);
    }

    [Theory]
    [InlineData(1, 0, "suspect — the model made 1 tool call / permission request — read the lines before you send")]
    [InlineData(2, 1, "suspect — the model made 3 tool calls / permission requests — read the lines before you send")]
    public void ASuspectLineNamesTheCount(int toolCalls, int permissions, string expected)
    {
        Assert.Equal(expected, CompileLine.For(With(Call(CallOutcomes.Suspect, "the model made tool calls", toolCalls, permissions))));
    }

    [Fact]
    public void TheTableCoversEveryOutcomeOnce()
    {
        string[] every = [CallOutcomes.Succeeded, CallOutcomes.SucceededNoStructure, CallOutcomes.Suspect, CallOutcomes.Unavailable, CallOutcomes.Refused, CallOutcomes.TimedOut, CallOutcomes.Malformed, CallOutcomes.Cancelled, CallOutcomes.Reused];

        Assert.Equal(every.ToHashSet(StringComparer.Ordinal), CompileLine.Outcomes.ToHashSet(StringComparer.Ordinal));
        Assert.Equal(9, CompileLine.Outcomes.Distinct(StringComparer.Ordinal).Count());
        Assert.Contains(CallOutcomes.Reused, CallOutcomes.Agentic);
    }

    /// <summary>E5: absent with no call and nothing supplied; the skipped call names who supplied the structure.</summary>
    [Theory]
    [InlineData("", null)]
    [InlineData(DecorationSources.Operator, "structure supplied by you")]
    [InlineData(PreCompile.TemplateWriter, "structure supplied by template")]
    public void WithNoCallTheLineIsAbsentOrNamesTheSupplier(string structureSource, string? expected)
    {
        Assert.Equal(expected, CompileLine.For(With(null), structureSource));
    }

    /// <summary><c>compile.stage{stage, duration_ms, outcome}</c> is emitted on the normal path and carries the three tags (US-D10).</summary>
    [Fact]
    public void TheStageRowCarriesStageDurationAndOutcome()
    {
        var seen = new List<Activity>();
        using var listener = new ActivityListener
        {
            ShouldListenTo = s => s.Name == CompileSignal.SourceName,
            Sample = (ref ActivityCreationOptions<ActivityContext> _) => ActivitySamplingResult.AllDataAndRecorded,
            ActivityStopped = seen.Add,
        };
        ActivitySource.AddActivityListener(listener);

        CompileSignal.Stage("compile", 812, CallOutcomes.Succeeded);

        var stage = Assert.Single(seen, a => a.OperationName == CompileEventKinds.Stage);
        Assert.Equal("compile", stage.GetTagItem("stage"));
        Assert.Equal(812L, stage.GetTagItem("duration_ms"));
        Assert.Equal(CallOutcomes.Succeeded, stage.GetTagItem("outcome"));
    }
}
