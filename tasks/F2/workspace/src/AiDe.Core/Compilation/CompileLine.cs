using System.Globalization;

namespace AiDe.Core.PromptCompilation;

/// <summary>
/// The compile line's strings (spec Addendum D §A10.2's table, §A11, E4/E5): one per
/// <c>called.outcome</c>, the tenth for a reuse, and the skipped call's — a function of the fold,
/// read by Prepare and the STA state test alike, stored nowhere.
/// </summary>
/// <remarks>
/// <b>Absent under <c>mechanical-only</c> with nothing supplied</b> (E5): <c>mode: mechanical-only</c>
/// is provenance on <c>opened</c>, never a compile-line string; the line exists only when a call
/// was made, reused, or skipped because the structure was already supplied.
/// </remarks>
public static class CompileLine
{
    /// <summary>The line for a fold: null when absent.</summary>
    /// <param name="envelope">The fold.</param>
    /// <param name="structureSource">Who filled the structure when the call was skipped: <c>operator</c> · <c>template</c>; empty when no line is supplied.</param>
    /// <param name="historyTurns">How many prior turns the compile read (the history window's ids).</param>
    /// <param name="tierRationale">The projection's rationale for a succeeded line.</param>
    public static string? For(Envelope envelope, string structureSource = "", int historyTurns = 0, string tierRationale = "")
    {
        ArgumentNullException.ThrowIfNull(envelope);

        var call = envelope.LastCall;
        if (call is null)
        {
            return structureSource switch
            {
                DecorationSources.Operator => "structure supplied by you",
                PreCompile.TemplateWriter => "structure supplied by template",
                _ => null,
            };
        }

        return ForOutcome(call.Outcome, call.Reason, call.ModelObserved, call.ToolCalls, call.PermissionRequests,
            envelope.Current(DecorationNames.FamilyProfile)?.Value?["family"]?.GetValue<string>() ?? Envelope.NotRecorded,
            historyTurns, tierRationale);
    }

    /// <summary>The string for one outcome — the table, parameterised on <c>reason</c> (§A11's STA test walks it).</summary>
    public static string ForOutcome(string outcome, string? reason, string modelObserved, int toolCalls, int permissionRequests, string family, int historyTurns, string tierRationale)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(outcome);

        return outcome switch
        {
            CallOutcomes.Succeeded => $"Compiled on {modelObserved} · {family} · read {historyTurns.ToString(CultureInfo.InvariantCulture)} turn{(historyTurns == 1 ? string.Empty : "s")} · {tierRationale}",
            CallOutcomes.SucceededNoStructure => "no goal block proposed; sends as a message",
            CallOutcomes.Suspect => $"suspect — the model made {(toolCalls + permissionRequests).ToString(CultureInfo.InvariantCulture)} tool call{(toolCalls + permissionRequests == 1 ? string.Empty : "s")} / permission request{(toolCalls + permissionRequests == 1 ? string.Empty : "s")} — read the lines before you send",
            CallOutcomes.Reused => $"Compiled on {modelObserved} · {family} · reused, no new request",
            CallOutcomes.Unavailable or CallOutcomes.Refused or CallOutcomes.TimedOut or CallOutcomes.Malformed or CallOutcomes.Cancelled
                => $"compiled mechanically — {reason ?? outcome}",
            _ => $"compiled mechanically — {outcome}",
        };
    }

    /// <summary>Every outcome the table names, in §A10.2 order — the STA test's rows.</summary>
    public static readonly IReadOnlyList<string> Outcomes =
    [
        CallOutcomes.Unavailable, CallOutcomes.Refused, CallOutcomes.TimedOut, CallOutcomes.Malformed, CallOutcomes.Suspect,
        CallOutcomes.Cancelled, CallOutcomes.SucceededNoStructure, CallOutcomes.Succeeded, CallOutcomes.Reused,
    ];
}
