using System.Text;
using System.Text.Json.Nodes;

namespace AiDe.Core.PromptCompilation;

/// <summary>One constitution document, by identity and hash only — never its body (§A12.3).</summary>
public sealed record ConstitutionRef(string Id, string Sha);

/// <summary>
/// What the compile prompt is assembled from (§A8.3): the source text, the mechanical facts the
/// model may not contradict (as display), the open lines, the profile body, the history window's
/// admissible classes and the constitution by reference. Never an account label, never an
/// attachment body, never lane output.
/// </summary>
/// <param name="SourceText">The operator's text, fenced by the assembler.</param>
/// <param name="MechanicalFacts">The current shape, tier, lease patterns, task class, template and profile — as text the model reads and may not change.</param>
/// <param name="OpenLines">The structure lines the model is asked for.</param>
/// <param name="ProfileBody">The family craft profile's body, or null for <c>none</c>.</param>
/// <param name="HistoryEntries">The admissible classes of the window's envelopes, one entry per envelope, or empty.</param>
/// <param name="Constitution">The manifest's <c>{id, sha}</c> pairs.</param>
public sealed record CompilePromptInputs(
    string SourceText,
    IReadOnlyDictionary<string, string> MechanicalFacts,
    IReadOnlyList<string> OpenLines,
    string? ProfileBody,
    IReadOnlyList<string> HistoryEntries,
    IReadOnlyList<ConstitutionRef> Constitution);

/// <summary>
/// Assembles the <c>compile-prompt/1</c> text from host-embedded bytes and typed inputs, and
/// computes the two hashes the <c>called</c> row records: <see cref="PromptSha"/> over the
/// template's bytes and <see cref="InputsSha"/> over the canonical inputs (§A8.4).
/// </summary>
public static class CompilePromptAssembler
{
    /// <summary>sha256 over the host header and template bytes — a wording edit to the prompt changes it, a workspace file never does.</summary>
    public static string PromptSha { get; } = EnvelopeHash.Sha256Hex(CompileContract.TemplateBytes);

    private static readonly System.Text.RegularExpressions.Regex Slot = new(@"\{\{([a-z_]+)\}\}", System.Text.RegularExpressions.RegexOptions.Compiled | System.Text.RegularExpressions.RegexOptions.CultureInvariant);

    /// <summary>The prompt, first bytes the host header.</summary>
    public static string Assemble(CompilePromptInputs inputs)
    {
        ArgumentNullException.ThrowIfNull(inputs);

        var facts = new StringBuilder();
        foreach (var (key, value) in inputs.MechanicalFacts.OrderBy(f => f.Key, StringComparer.Ordinal))
        {
            facts.Append("- ").Append(key).Append(": ").Append(value).Append('\n');
        }

        // ONE PASS over the template's slots: a value is never re-scanned for slots, so a source text
        // (or a history entry, or the profile) that spells `{{constitution}}` is text, not a slot.
        var slots = new Dictionary<string, string>(StringComparer.Ordinal)
        {
            ["source_text"] = Fence(inputs.SourceText),
            ["mechanical_facts"] = facts.Length == 0 ? "(none)" : facts.ToString().TrimEnd('\n'),
            ["open_lines"] = inputs.OpenLines.Count == 0 ? "(none — every line is supplied; do not propose any)" : string.Join(", ", inputs.OpenLines),
            ["family_profile"] = inputs.ProfileBody ?? "(none)",
            ["history_window"] = inputs.HistoryEntries.Count == 0 ? "(none)" : string.Join("\n\n", inputs.HistoryEntries.Select(Fence)),
            ["constitution"] = inputs.Constitution.Count == 0
                ? "(none)"
                : "Already in your context; do not request them.\n" + string.Join("\n", inputs.Constitution.Select(c => $"- {c.Id} sha256:{c.Sha}")),
        };
        var body = Slot.Replace(CompileContract.Template, m => slots.TryGetValue(m.Groups[1].Value, out var value) ? value : m.Value);

        return CompileContract.HostHeader + "\n" + body;
    }

    /// <summary>
    /// <c>sha256(canonical(source_text ‖ the mechanical facts sorted by name ‖ open lines ‖ profile
    /// {family, version, sha} ‖ history ids ‖ contract_version ‖ prompt_sha))</c> — the same inputs
    /// yield the same sha, so a re-prepare can reuse stored decorations and only a changed input
    /// re-calls (§A8.4).
    /// </summary>
    public static string InputsSha(
        string sourceText,
        IReadOnlyDictionary<string, string> mechanicalFacts,
        IReadOnlyList<string> openLines,
        JsonNode? familyProfile,
        IReadOnlyList<string> historyIds)
    {
        ArgumentNullException.ThrowIfNull(sourceText);
        ArgumentNullException.ThrowIfNull(mechanicalFacts);
        ArgumentNullException.ThrowIfNull(openLines);
        ArgumentNullException.ThrowIfNull(historyIds);

        var domain = new JsonArray
        {
            sourceText,
            new JsonObject(mechanicalFacts.OrderBy(f => f.Key, StringComparer.Ordinal).Select(f => KeyValuePair.Create(f.Key, (JsonNode?)JsonValue.Create(f.Value)))),
            new JsonArray([.. openLines.Select(l => JsonValue.Create(l))]),
            familyProfile?.DeepClone(),
            new JsonArray([.. historyIds.Select(h => JsonValue.Create(h))]),
            CompileContract.Version,
            PromptSha,
        };
        return EnvelopeHash.Sha256Hex(domain.ToJsonString());
    }

    /// <summary>A fence widened past the longest backtick run inside, so the content cannot end it early.</summary>
    private static string Fence(string text)
    {
        var longest = 2;
        var run = 0;
        foreach (var c in text)
        {
            run = c == '`' ? run + 1 : 0;
            longest = Math.Max(longest, run);
        }

        var fence = new string('`', longest + 1);
        return fence + "text\n" + (text.EndsWith('\n') ? text : text + "\n") + fence;
    }
}
