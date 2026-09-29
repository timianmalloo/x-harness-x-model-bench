using System.Text.Json;
using System.Text.Json.Nodes;

namespace AiDe.Core.Sessions;

/// <summary>
/// Gate 2 (ADR-0036): reads <c>compile-eval-admission.json</c> — <c>tools/compile-eval/score.py</c>'s
/// report over 50 scored + 50 holdout real envelopes — and recomputes every floor from the report's
/// own <c>numerator</c>/<c>denominator</c> pairs. <c>agentic</c> is refused unless every floor holds.
/// </summary>
/// <remarks>
/// <para><b>A verdict field is never read, even if present.</b> The report contract
/// (<c>score.py</c>'s <c>check_contract</c>) already refuses to let one be written, but this reader
/// does not rely on that upstream promise: it never inspects a <c>met</c> / <c>verdict</c> / <c>passed</c>
/// / <c>admitted</c> / <c>selectable</c> key at all — the admit/refuse decision is arithmetic over
/// <c>numerator</c> and <c>denominator</c>, nothing else (DM7: derive, don't store — a verdict is
/// never stored, and this reader never trusts one that was).</para>
///
/// <para><b>The floor set this reader evaluates</b> (the plan row's naming of "every A14.4 floor"
/// for this reader — the fuller metric set (acceptance, missed, emptied, span resolution,
/// shape-flip) is §A14.4's quality bar for the harness, not a selectability gate here — YAGNI/
/// smallest-correct per the Solution-Selection Ladder, recorded as a scope decision, not an
/// omission): the split witness (the holdout is 50, disjoint from the sample, and does not precede
/// it — "the holdout of 50 judged, never the sample"), <c>schema_fail ≤ 2 %</c> over the holdout,
/// <c>applied_denied = 0</c> and <c>tool_calls = 0</c> as invariants over every <c>called</c> row,
/// and the degraded-rate floor at Ruling 76's <c>X = 5 %</c> over every model call.</para>
///
/// <para><b>A metric this reader cannot verify is never assumed to pass.</b> A missing or
/// non-numeric numerator/denominator, or a zero denominator where a rate is asked for, refuses —
/// an unmeasurable floor is not a met floor (IO: "degrades to not recorded, never a plausible
/// number" read as a gate: it degrades to refused, never to admitted).</para>
/// </remarks>
public static class CompileAdmissionGate
{
    /// <summary>The artifact's file name, machine-level beside <see cref="CompilePinArtifact"/> (ADR-0036's path-resolution rule).</summary>
    public const string FileName = "compile-eval-admission.json";

    /// <summary>The contract <c>score.py</c> writes.</summary>
    public const string Contract = "compile-eval-admission/1";

    /// <summary>The holdout's required size — N is revised only upward (ADR-0036).</summary>
    public const int RequiredHoldout = 50;

    /// <summary>§A14.4's <c>schema_fail</c> floor.</summary>
    public const double SchemaFailFloor = 0.02;

    /// <summary>Ruling 76's degraded-rate floor (the stricter reading; X's one home is this table, never <c>opened.constants</c>).</summary>
    public const double DegradedFloor = 0.05;

    /// <summary>Evaluates Gate 2 against <c>&lt;proofDirectory&gt;/compile-eval-admission.json</c>. Null admits; otherwise the refusal, with a stable <c>CE-</c> code.</summary>
    public static CompileModeRefusal? Evaluate(string proofDirectory)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(proofDirectory);
        return EvaluateReport(Path.Combine(proofDirectory, FileName));
    }

    /// <summary>Evaluates Gate 2 against the report at <paramref name="reportPath"/> directly (tests; a fixed report path).</summary>
    public static CompileModeRefusal? EvaluateReport(string reportPath)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(reportPath);

        if (!File.Exists(reportPath))
        {
            return new CompileModeRefusal(
                PromptCompilation.EnvelopeStoreErrorCodes.AdmissionReportOutstanding,
                $"Gate 2 is outstanding: no admission report ({FileName}) over 50 scored and 50 holdout envelopes has been read at {reportPath}; agentic-advisory builds that corpus");
        }

        JsonObject? report;
        try
        {
            report = JsonNode.Parse(File.ReadAllText(reportPath)) as JsonObject;
        }
        catch (JsonException error)
        {
            return Unreadable(reportPath, $"the report is not JSON: {error.Message}");
        }

        if (report is null)
        {
            return Unreadable(reportPath, "the report is not a JSON object");
        }

        var contract = report["contract"] as JsonValue;
        if (contract is null || !contract.TryGetValue<string>(out var contractText) || !string.Equals(contractText, Contract, StringComparison.Ordinal))
        {
            return Unreadable(reportPath, $"the report's contract is {(report["contract"]?.ToJsonString() ?? "absent")}, not {Contract}");
        }

        if (report["sample"] is not JsonObject || report["holdout"] is not JsonObject || report["invariants"] is not JsonObject || report["metrics"] is not JsonObject)
        {
            return Unreadable(reportPath, "the report is missing sample, holdout, invariants, or metrics — not the compile-eval-admission/1 shape");
        }

        var split = Split(report);
        if (!split.Ok)
        {
            return new CompileModeRefusal(
                PromptCompilation.EnvelopeStoreErrorCodes.AdmissionSplitInvalid,
                $"Gate 2's split witness fails: {split.Reason} — the holdout of {RequiredHoldout} is judged, never the sample");
        }

        if (RateFloorRefusal(report, "metrics", "schema_fail", SchemaFailFloor, PromptCompilation.EnvelopeStoreErrorCodes.AdmissionFloorSchemaFail, "schema_fail") is { } schemaFailRefusal)
        {
            return schemaFailRefusal;
        }

        if (InvariantRefusal(report, "invariants", "applied_denied", PromptCompilation.EnvelopeStoreErrorCodes.AdmissionFloorAppliedDenied, "applied_denied", "a derived row named outside the allow-list reached the store") is { } appliedDeniedRefusal)
        {
            return appliedDeniedRefusal;
        }

        if (InvariantRefusal(report, "invariants", "tool_calls", PromptCompilation.EnvelopeStoreErrorCodes.AdmissionFloorToolCalls, "tool_calls", "the pin's premise (ADR-0035) does not hold over this corpus") is { } toolCallsRefusal)
        {
            return toolCallsRefusal;
        }

        if (RateFloorRefusal(report, "metrics", "degraded", DegradedFloor, PromptCompilation.EnvelopeStoreErrorCodes.AdmissionFloorDegraded, "degraded (Ruling 76)") is { } degradedRefusal)
        {
            return degradedRefusal;
        }

        return null;
    }

    private static CompileModeRefusal Unreadable(string path, string reason) =>
        new(PromptCompilation.EnvelopeStoreErrorCodes.AdmissionReportUnreadable, $"the admission report at {path} could not be read: {reason}");

    /// <summary>A rate floor over <c>section.metric = {numerator, denominator}</c>: unreadable or unmeasurable never passes.</summary>
    private static CompileModeRefusal? RateFloorRefusal(JsonObject report, string section, string metric, double floor, string code, string label)
    {
        var ratio = Ratio(report, section, metric);
        if (ratio is null)
        {
            return new CompileModeRefusal(code, $"Gate 2's {label} floor is not met: {section}.{metric} is unreadable (floor ≤ {floor:P0})");
        }

        if (!Holds(ratio.Value, floor, out var reason))
        {
            return new CompileModeRefusal(code, $"Gate 2's {label} floor is not met: {reason} (floor ≤ {floor:P0})");
        }

        return null;
    }

    /// <summary>An invariant (a numerator that must be exactly zero) over <c>section.metric</c>: unreadable never passes.</summary>
    private static CompileModeRefusal? InvariantRefusal(JsonObject report, string section, string metric, string code, string label, string nonZeroReason)
    {
        var ratio = Ratio(report, section, metric);
        if (ratio is null)
        {
            return new CompileModeRefusal(code, $"Gate 2's {label} invariant is unreadable");
        }

        if (ratio.Value.Numerator != 0)
        {
            return new CompileModeRefusal(code, $"Gate 2's {label} invariant is not zero: {ratio.Value.Numerator}/{ratio.Value.Denominator} — {nonZeroReason}");
        }

        return null;
    }

    /// <summary>A <c>{numerator, denominator}</c> pair — never a verdict, never trusted beyond arithmetic.</summary>
    private readonly record struct RatioPair(long Numerator, long Denominator);

    private static RatioPair? Ratio(JsonObject report, string section, string metric)
    {
        if (report[section] is not JsonObject sectionNode || sectionNode[metric] is not JsonObject metricNode)
        {
            return null;
        }

        if (metricNode["numerator"] is JsonValue n && n.TryGetValue<long>(out var num)
            && metricNode["denominator"] is JsonValue d && d.TryGetValue<long>(out var den))
        {
            return new RatioPair(num, den);
        }

        return null;
    }

    /// <summary>A rate floor: an unmeasurable (zero-denominator) rate never holds — absence is never admitted.</summary>
    private static bool Holds(RatioPair ratio, double floor, out string? reason)
    {
        if (ratio.Denominator <= 0)
        {
            reason = $"{ratio.Numerator}/{ratio.Denominator} — no measured rows to compute the rate over";
            return false;
        }

        var rate = (double)ratio.Numerator / ratio.Denominator;
        if (rate > floor)
        {
            reason = $"{ratio.Numerator}/{ratio.Denominator} = {rate:P1} > {floor:P0}";
            return false;
        }

        reason = null;
        return true;
    }

    private readonly record struct SplitCheck(bool Ok, string? Reason);

    /// <summary>
    /// Recomputes the split witness from the report's own <c>sample</c>/<c>holdout</c> arrays — the
    /// holdout must carry ≥ 50 ids, disjoint from the sample's, and not precede it. Recomputed here,
    /// never trusted from a summary field the report might otherwise have carried.
    /// </summary>
    private static SplitCheck Split(JsonObject report)
    {
        if (report["sample"] is not JsonObject sample || report["holdout"] is not JsonObject holdout)
        {
            return new SplitCheck(false, "the report carries no sample/holdout witness");
        }

        var sampleIds = Ids(sample);
        var holdoutIds = Ids(holdout);
        var holdoutN = holdout["n"] is JsonValue hn && hn.TryGetValue<long>(out var n) ? n : holdoutIds.Count;

        if (holdoutN < RequiredHoldout || holdoutIds.Count < RequiredHoldout)
        {
            return new SplitCheck(false, $"holdout.n = {holdoutN} < {RequiredHoldout}");
        }

        var overlap = sampleIds.Intersect(holdoutIds, StringComparer.Ordinal).ToList();
        if (overlap.Count > 0)
        {
            return new SplitCheck(false, $"the sample and the holdout share {overlap.Count} envelope id(s) — the sample would be judged as the holdout");
        }

        var sampleLastAt = At(sample, "last_at");
        var holdoutFirstAt = At(holdout, "first_at");
        if (sampleLastAt is { } lastAt && holdoutFirstAt is { } firstAt && firstAt < lastAt)
        {
            return new SplitCheck(false, "holdout.first_at precedes sample.last_at");
        }

        return new SplitCheck(true, null);
    }

    private static HashSet<string> Ids(JsonObject witness)
    {
        var ids = new HashSet<string>(StringComparer.Ordinal);
        if (witness["envelope_ids"] is JsonArray array)
        {
            foreach (var value in array.OfType<JsonValue>())
            {
                if (value.TryGetValue<string>(out var id))
                {
                    ids.Add(id);
                }
            }
        }

        return ids;
    }

    private static DateTimeOffset? At(JsonObject witness, string field) =>
        witness[field] is JsonValue v && v.TryGetValue<string>(out var text) && DateTimeOffset.TryParse(text, out var parsed) ? parsed : null;
}
