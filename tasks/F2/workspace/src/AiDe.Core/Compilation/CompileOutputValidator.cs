using System.Text.Json;
using System.Text.Json.Nodes;
using AiDe.Core.Presentation.Composer;

namespace AiDe.Core.PromptCompilation;

/// <summary>One derived decoration that passed the typed boundary (§A8.3's invariant, all five clauses).</summary>
public sealed record DerivedDecoration(string Name, string Value, double Confidence, IReadOnlyList<GroundedSpan> GroundedIn);

/// <summary>
/// What the boundary made of one model output: the decorations that passed, what it dropped by
/// reason, the <c>notes</c> if they passed the same scan, and the <c>called.outcome</c> the
/// output earns (<c>succeeded</c> · <c>succeeded_no_structure</c> · <c>malformed</c>).
/// </summary>
public sealed record ValidationResult(
    IReadOnlyList<DerivedDecoration> Applied,
    DroppedCounts Dropped,
    string? Notes,
    string Outcome,
    string? Reason);

/// <summary>
/// The non-determinism boundary (§A8.4; LOA 3.1 Deterministic Verifier): raw text → JSON → schema →
/// allow-list and open lines → type → mention scan (values and <c>notes</c>) → span resolution →
/// typed <see cref="DerivedDecoration"/>[]. Nothing downstream sees raw text.
/// </summary>
/// <remarks>
/// <para><b>C-Lease</b> (§A13.3 c): a value or <c>notes</c> carrying a mention token is refused —
/// not stripped — with <see cref="LeaseDerivation.HasMention"/>, the same regex <c>Patterns</c>
/// matches, so the scan and the derivation cannot drift. A refused proposal is never stored, so
/// <i>restore</i> cannot resurface it.</para>
///
/// <para><b>Every drop is counted on the reason it fell to</b>, in pipeline order — the first
/// failing clause names it — and the counts land on the <c>called</c> row (US-D5).</para>
/// </remarks>
public static class CompileOutputValidator
{
    private const string SourceTextInput = "source_text";

    /// <summary>Validates one raw model output against the open lines and the source text it must cite.</summary>
    /// <param name="rawText">The model's text, verbatim.</param>
    /// <param name="sourceText">The <c>opened.source_text</c> spans resolve into (UTF-16 indices).</param>
    /// <param name="openLines">The structure lines the prompt named as open — a proposal for any other line is dropped.</param>
    public static ValidationResult Validate(string rawText, string sourceText, IReadOnlyList<string> openLines)
    {
        ArgumentNullException.ThrowIfNull(rawText);
        ArgumentNullException.ThrowIfNull(sourceText);
        ArgumentNullException.ThrowIfNull(openLines);

        // 1. JSON.
        JsonObject? root;
        try
        {
            root = JsonNode.Parse(ExtractObject(rawText)) as JsonObject;
        }
        catch (JsonException)
        {
            root = null;
        }

        if (root is null)
        {
            return Malformed("parse: the output is not one JSON object");
        }

        // 2. Schema: the contract name and a decorations array.
        if (root["contract"] is not JsonValue contract || !contract.TryGetValue(out string? contractName)
            || !string.Equals(contractName, CompileContract.OutputContract, StringComparison.Ordinal))
        {
            return Malformed($"schema: contract is not {CompileContract.OutputContract}");
        }

        if (root["decorations"] is not JsonArray decorations)
        {
            return Malformed("schema: decorations is not an array");
        }

        var unknown = 0;
        var alreadySupplied = 0;
        var ungrounded = 0;
        var mentionBearing = 0;
        var typeFail = 0;
        var applied = new List<DerivedDecoration>();
        var seen = new HashSet<string>(StringComparer.Ordinal);

        foreach (var node in decorations)
        {
            if (node is not JsonObject proposal)
            {
                typeFail++;
                continue;
            }

            // 3. The allow-list (case-sensitive) — a `lease`, a `Lease`, a `tier`, any unknown name.
            var name = proposal["name"] is JsonValue n && n.TryGetValue(out string? nameText) ? nameText : null;
            if (name is null || !CompileContract.AllowList.Contains(name, StringComparer.Ordinal))
            {
                unknown++;
                continue;
            }

            // 3b. Only the open lines; a line already filled, or proposed twice, is dropped.
            if (!openLines.Contains(name, StringComparer.Ordinal) || !seen.Add(name))
            {
                alreadySupplied++;
                continue;
            }

            // 4. Type: a string, bounded, no control characters; confidence in [0, 1].
            if (proposal["value"] is not JsonValue v || !v.TryGetValue(out string? value)
                || value.Length == 0 || value.Length > CompileContract.MaxValueChars || CarriesAControlCharacter(value))
            {
                typeFail++;
                continue;
            }

            if (proposal["confidence"] is not JsonValue c || !c.TryGetValue(out double confidence) || double.IsNaN(confidence) || confidence < 0 || confidence > 1)
            {
                typeFail++;
                continue;
            }

            // 5. C-Lease: no mention token anywhere in the value.
            if (LeaseDerivation.HasMention(value))
            {
                mentionBearing++;
                continue;
            }

            // 6. Span resolution: ≥ 1 span into source_text that resolves.
            var spans = ReadSpans(proposal["grounded_in"]);
            if (!spans.Any(s => string.Equals(s.Input, SourceTextInput, StringComparison.Ordinal) && s.Start >= 0 && s.End <= sourceText.Length && s.Start < s.End))
            {
                ungrounded++;
                continue;
            }

            applied.Add(new DerivedDecoration(name, value, confidence, spans));
        }

        // Notes: shown as provenance, never applied; the same scan, or dropped.
        string? notes = null;
        if (root["notes"] is JsonValue notesValue && notesValue.TryGetValue(out string? notesText)
            && notesText.Length > 0 && notesText.Length <= CompileContract.MaxNotesChars
            && !CarriesAControlCharacter(notesText)
            && !LeaseDerivation.HasMention(notesText))
        {
            notes = notesText;
        }

        var dropped = new DroppedCounts(unknown, alreadySupplied, ungrounded, mentionBearing, typeFail);
        if (applied.Count == 0)
        {
            return decorations.Count == 0
                ? new ValidationResult([], dropped, notes, CallOutcomes.SucceededNoStructure, "no goal block proposed; sends as a message")
                : new ValidationResult([], dropped, notes, CallOutcomes.Malformed, "all proposals dropped");
        }

        return new ValidationResult(applied, dropped, notes, CallOutcomes.Succeeded, null);
    }

    private static ValidationResult Malformed(string reason) =>
        new([], DroppedCounts.None, null, CallOutcomes.Malformed, reason);

    /// <summary>
    /// §A8.3: no control characters — every <c>char.IsControl</c> (a line break included: a structure
    /// line is one line, and a break would forge a second rendered line), and the format (Cf) set —
    /// bidi overrides and zero-width joiners — which display-spoof what the operator reads in Prepare.
    /// </summary>
    private static bool CarriesAControlCharacter(string text) =>
        text.Any(c => char.IsControl(c) || char.GetUnicodeCategory(c) == System.Globalization.UnicodeCategory.Format);

    /// <summary>The one JSON object in the text: the model may wrap it in a fence or prose; nothing else is read.</summary>
    private static string ExtractObject(string rawText)
    {
        var start = rawText.IndexOf('{');
        var end = rawText.LastIndexOf('}');
        return start >= 0 && end > start ? rawText[start..(end + 1)] : rawText;
    }

    private static IReadOnlyList<GroundedSpan> ReadSpans(JsonNode? node)
    {
        if (node is not JsonArray spans)
        {
            return [];
        }

        var result = new List<GroundedSpan>();
        foreach (var span in spans.OfType<JsonObject>())
        {
            var input = span["input"] is JsonValue i && i.TryGetValue(out string? inputText) ? inputText : null;
            if (input is null || span["span"] is not JsonArray { Count: 2 } pair
                || pair[0] is not JsonValue a || !a.TryGetValue(out int start)
                || pair[1] is not JsonValue b || !b.TryGetValue(out int end))
            {
                continue;
            }

            result.Add(new GroundedSpan(input, start, end));
        }

        return result;
    }
}
