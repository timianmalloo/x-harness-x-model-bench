using System.Text.Json.Nodes;
using AiDe.Core.PromptCompilation;
using AiDe.Core.Sessions;

namespace AiDe.Core.Tests.Sessions;

/// <summary>
/// Gate 2 (ADR-0036; CV-4): <c>agentic</c> is admitted only when every floor is recomputed from the
/// admission report's own <c>numerator</c>/<c>denominator</c> pairs — never a stored verdict, never
/// the sample judged as the holdout.
/// </summary>
public sealed class TheAdmissionGateRecomputesFromNumeratorDenominatorTests : IDisposable
{
    private readonly string _root = Directory.CreateTempSubdirectory("aide-admission-gate-").FullName;

    private string ReportPath => Path.Combine(_root, CompileAdmissionGate.FileName);

    public void Dispose() => Directory.Delete(_root, recursive: true);

    private static JsonArray IdsArray(int count, string prefix) =>
        new([.. Enumerable.Range(0, count).Select(i => JsonValue.Create($"{prefix}{i:0000}") as JsonNode)]);

    /// <summary>A passing report: 50 sample + 50 disjoint holdout, every floor comfortably inside its bound.</summary>
    private static JsonObject PassingReport(
        long schemaFailNum = 0, long schemaFailDen = 50,
        long appliedDeniedNum = 0, long appliedDeniedDen = 500,
        long toolCallsNum = 0, long toolCallsDen = 500,
        long degradedNum = 0, long degradedDen = 100,
        int holdoutN = 50,
        string sampleLastAt = "2026-09-13T18:00:00.000+00:00",
        string holdoutFirstAt = "2026-09-13T19:00:00.000+00:00")
    {
        static JsonObject Ratio(long num, long den) => new() { ["numerator"] = num, ["denominator"] = den };

        return new JsonObject
        {
            ["contract"] = CompileAdmissionGate.Contract,
            ["sample"] = new JsonObject { ["envelope_ids"] = IdsArray(50, "s-"), ["first_at"] = "2026-09-13T17:00:00.000+00:00", ["last_at"] = sampleLastAt, ["n"] = 50 },
            ["holdout"] = new JsonObject { ["envelope_ids"] = IdsArray(holdoutN, "h-"), ["first_at"] = holdoutFirstAt, ["last_at"] = "2026-09-13T20:00:00.000+00:00", ["n"] = holdoutN },
            ["invariants"] = new JsonObject
            {
                ["applied_denied"] = Ratio(appliedDeniedNum, appliedDeniedDen),
                ["tool_calls"] = Ratio(toolCallsNum, toolCallsDen),
            },
            ["metrics"] = new JsonObject
            {
                ["schema_fail"] = Ratio(schemaFailNum, schemaFailDen),
                ["degraded"] = Ratio(degradedNum, degradedDen),
            },
        };
    }

    private void Write(JsonObject report) => File.WriteAllText(ReportPath, report.ToJsonString());

    /// <summary>No report at all — Gate 2 refuses by name, exactly as CV-3 left it (US-D11 b2).</summary>
    [Fact]
    public void NoReportRefusesWithAdmissionOutstanding()
    {
        var refusal = CompileAdmissionGate.Evaluate(_root);

        Assert.NotNull(refusal);
        Assert.Equal(EnvelopeStoreErrorCodes.AdmissionReportOutstanding, refusal!.Code);
        Assert.Contains("Gate 2", refusal.Reason, StringComparison.Ordinal);
    }

    /// <summary>A report that is not JSON, or not the expected contract, is unreadable — not an admission.</summary>
    [Theory]
    [InlineData("{not json")]
    [InlineData("""{"contract": "some-other-contract/1"}""")]
    [InlineData("""{"contract": "compile-eval-admission/1"}""")]
    public void AnUnreadableReportRefuses(string text)
    {
        File.WriteAllText(ReportPath, text);

        var refusal = CompileAdmissionGate.Evaluate(_root);

        Assert.NotNull(refusal);
        Assert.Equal(EnvelopeStoreErrorCodes.AdmissionReportUnreadable, refusal!.Code);
    }

    /// <summary>Every floor holding, the split witness disjoint and ordered, and the holdout at exactly 50 — admits.</summary>
    [Fact]
    public void EveryFloorHoldingAdmits()
    {
        Write(PassingReport());

        Assert.Null(CompileAdmissionGate.Evaluate(_root));
    }

    /// <summary>Fewer than 50 holdout envelopes: the holdout is judged, never the sample — refused, never partially admitted.</summary>
    [Fact]
    public void AHoldoutBelow50Refuses()
    {
        Write(PassingReport(holdoutN: 49));

        var refusal = CompileAdmissionGate.Evaluate(_root);

        Assert.Equal(EnvelopeStoreErrorCodes.AdmissionSplitInvalid, refusal!.Code);
        Assert.Contains("50", refusal.Reason, StringComparison.Ordinal);
    }

    /// <summary>The sample and the holdout sharing an id would let the sample be judged as the holdout — refused.</summary>
    [Fact]
    public void AnOverlappingSplitRefuses()
    {
        var report = PassingReport();
        // Plant one shared id between sample and holdout.
        ((JsonArray)report["holdout"]!["envelope_ids"]!)[0] = JsonValue.Create("s-0000");
        Write(report);

        var refusal = CompileAdmissionGate.Evaluate(_root);

        Assert.Equal(EnvelopeStoreErrorCodes.AdmissionSplitInvalid, refusal!.Code);
        Assert.Contains("share", refusal.Reason, StringComparison.Ordinal);
    }

    /// <summary>The holdout preceding the sample inverts the split's ordering — refused.</summary>
    [Fact]
    public void AHoldoutThatPrecedesTheSampleRefuses()
    {
        Write(PassingReport(sampleLastAt: "2026-09-13T20:00:00.000+00:00", holdoutFirstAt: "2026-09-13T19:00:00.000+00:00"));

        var refusal = CompileAdmissionGate.Evaluate(_root);

        Assert.Equal(EnvelopeStoreErrorCodes.AdmissionSplitInvalid, refusal!.Code);
        Assert.Contains("precedes", refusal.Reason, StringComparison.Ordinal);
    }

    /// <summary>A schema-fail rate over §A14.4's 2 % floor refuses, recomputed from the numerator/denominator — never a written rate.</summary>
    [Fact]
    public void ASchemaFailRateOverTheFloorRefuses()
    {
        Write(PassingReport(schemaFailNum: 2, schemaFailDen: 50)); // 4 % > 2 %

        var refusal = CompileAdmissionGate.Evaluate(_root);

        Assert.Equal(EnvelopeStoreErrorCodes.AdmissionFloorSchemaFail, refusal!.Code);
        Assert.Contains("2/50", refusal.Reason, StringComparison.Ordinal);
    }

    /// <summary>The applied_denied invariant must be exactly zero over every called row — any non-zero numerator refuses.</summary>
    [Fact]
    public void AppliedDeniedNonZeroRefuses()
    {
        Write(PassingReport(appliedDeniedNum: 1, appliedDeniedDen: 500));

        var refusal = CompileAdmissionGate.Evaluate(_root);

        Assert.Equal(EnvelopeStoreErrorCodes.AdmissionFloorAppliedDenied, refusal!.Code);
        Assert.Contains("1/500", refusal.Reason, StringComparison.Ordinal);
    }

    /// <summary>tool_calls must be exactly zero over every called row (ADR-0035's pin premise) — non-zero refuses.</summary>
    [Fact]
    public void ToolCallsNonZeroRefuses()
    {
        Write(PassingReport(toolCallsNum: 3, toolCallsDen: 500));

        var refusal = CompileAdmissionGate.Evaluate(_root);

        Assert.Equal(EnvelopeStoreErrorCodes.AdmissionFloorToolCalls, refusal!.Code);
        Assert.Contains("3/500", refusal.Reason, StringComparison.Ordinal);
    }

    /// <summary>The degraded rate over Ruling 76's 5 % floor refuses.</summary>
    [Fact]
    public void ADegradedRateOverTheFloorRefuses()
    {
        Write(PassingReport(degradedNum: 6, degradedDen: 100)); // 6 % > 5 %

        var refusal = CompileAdmissionGate.Evaluate(_root);

        Assert.Equal(EnvelopeStoreErrorCodes.AdmissionFloorDegraded, refusal!.Code);
        Assert.Contains("6/100", refusal.Reason, StringComparison.Ordinal);
    }

    /// <summary>A zero-denominator rate is never assumed to pass — an unmeasurable floor refuses, not admits.</summary>
    [Fact]
    public void AZeroDenominatorNeverPasses()
    {
        Write(PassingReport(degradedNum: 0, degradedDen: 0));

        var refusal = CompileAdmissionGate.Evaluate(_root);

        Assert.Equal(EnvelopeStoreErrorCodes.AdmissionFloorDegraded, refusal!.Code);
    }

    /// <summary>
    /// The red the plan names by name: a planted <c>verdict: "admit"</c> (and <c>met</c>, <c>passed</c>)
    /// over otherwise-failing numerator/denominator pairs must still refuse — the reader never reads
    /// a verdict-shaped key, however it is spelled or where it is nested.
    /// </summary>
    [Fact]
    public void APlantedVerdictOverFailingFloorsIsIgnoredAndStillRefuses()
    {
        var report = PassingReport(schemaFailNum: 10, schemaFailDen: 50); // fails on its own
        report["verdict"] = "admit";
        report["met"] = true;
        report["metrics"]!["schema_fail"]!["passed"] = true;
        report["admitted"] = true;
        report["selectable"] = true;
        Write(report);

        var refusal = CompileAdmissionGate.Evaluate(_root);

        Assert.NotNull(refusal);
        Assert.Equal(EnvelopeStoreErrorCodes.AdmissionFloorSchemaFail, refusal!.Code);
    }

    /// <summary>
    /// Symmetrically: a planted verdict can never MANUFACTURE an admission either — with every real
    /// floor passing, the presence of extra verdict-shaped keys does not change the (correct) result.
    /// </summary>
    [Fact]
    public void APlantedVerdictOverPassingFloorsChangesNothing()
    {
        var report = PassingReport();
        report["verdict"] = "admit";
        report["met"] = true;
        Write(report);

        Assert.Null(CompileAdmissionGate.Evaluate(_root));
    }
}
