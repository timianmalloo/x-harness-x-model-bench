namespace AiDe.Core.Extraction;

/// <summary>What a knowledge artifact declares about itself in its frontmatter.</summary>
/// <param name="Id">The node's identity. Without one there is nothing to attach facts to.</param>
/// <param name="Type">Its declared kind — adr, spec, decision-note. Null when absent.</param>
/// <param name="Owner">Who answers for it. A person, so it stays workspace-local.</param>
/// <param name="ReviewBy">When it should next be re-read, if it says.</param>
/// <param name="Links">Typed edges to other knowledge, as <c>(to, rel)</c>.</param>
public sealed record KnowledgeRecord(
    string Id,
    string? Type,
    string? Owner,
    IReadOnlyList<(string To, string Rel)> Links,
    string? ReviewBy = null);

/// <summary>
/// Reading the YAML-ish frontmatter that makes a markdown file a node in the knowledge graph.
/// </summary>
/// <remarks>
/// <para><b>Shared because two readers need the same answer.</b> The fixture reader has parsed this
/// since Phase 1; the knowledge reader parses it on real repositories. Two copies of a format parser
/// is two things to drift, and the drift would show as a document that is a node in one view and not
/// in the other.</para>
///
/// <para><b>A subset reader, not a YAML parser.</b> The fields that carry graph structure — id, type,
/// owner, links — are read; everything else in the block is skipped. A YAML dependency would buy
/// anchors and flow mappings that this format does not use, and would make what the tool can see a
/// question about a package version.</para>
///
/// <para><c>simplify: line-oriented frontmatter reading rather than YAML; ceiling is id, type, owner
/// and inline `- { to: …, rel: … }` links; upgrade trigger = a consumer needs nested or multi-line
/// values, or the format grows beyond what one line can express.</c></para>
/// </remarks>
public static class KnowledgeFrontmatter
{
    /// <summary>
    /// The record a file declares, or null when it is not a knowledge artifact.
    /// </summary>
    /// <param name="missingId">
    /// Set when a file HAS frontmatter but no id — a real defect in the document, distinct from an
    /// ordinary markdown file that was never meant to be a node. Collapsing the two would either
    /// report every README as broken or hide a document that meant to join the graph and cannot.
    /// </param>
    public static KnowledgeRecord? Read(IReadOnlyList<string> lines, out bool missingId)
    {
        ArgumentNullException.ThrowIfNull(lines);

        missingId = false;

        if (lines.Count == 0 || lines[0].Trim() != "---") return null;

        string? id = null;
        string? type = null;
        string? owner = null;
        string? reviewBy = null;
        var links = new List<(string To, string Rel)>();

        for (var i = 1; i < lines.Count; i++)
        {
            var trimmed = lines[i].Trim();

            if (trimmed == "---") break;

            if (trimmed.StartsWith("id:", StringComparison.Ordinal))
            {
                id = Value(trimmed[3..]);
            }
            else if (trimmed.StartsWith("type:", StringComparison.Ordinal))
            {
                type = Value(trimmed[5..]);
            }
            else if (trimmed.StartsWith("owner:", StringComparison.Ordinal))
            {
                owner = Value(trimmed[6..]);
            }
            else if (trimmed.StartsWith("review-by:", StringComparison.Ordinal))
            {
                reviewBy = Value(trimmed[10..]);
            }
            else if (trimmed.StartsWith("- { to:", StringComparison.Ordinal))
            {
                // Up to the CLOSING BRACE, not TrimEnd. Real lines carry a trailing YAML comment —
                // `- { to: x, rel: implements }   # typed edges — registry in …` — and trimming from
                // the end leaves the comment attached to the relation, which reaches the graph as an
                // edge kind nobody has heard of. Measured: that exact string appeared as a relation.
                var close = trimmed.IndexOf('}', StringComparison.Ordinal);
                var body = (close < 0 ? trimmed[7..] : trimmed[7..close]).Trim();

                var segments = body.Split(',', StringSplitOptions.TrimEntries);
                var to = Value(segments[0]);

                var rel = segments.Length > 1 && segments[1].StartsWith("rel:", StringComparison.Ordinal)
                    ? Value(segments[1][4..])
                    : "relates-to";

                if (!IsPlaceholder(to) && !IsPlaceholder(rel)) links.Add((to, rel));
            }
        }

        // A placeholder is not an id, and a document that only demonstrates the format is not a node.
        //
        // `missingId` fires only when the frontmatter is GRAPH frontmatter — it carries a type, an
        // owner, links or a review date — and still has no id. YAML is a general format: this
        // repository's own INSTALL.md opens with `doc:`, `bundle_version:` and `changes:`, which is
        // a pack manifest and was never meant to be a node. Reporting it as a broken artifact is the
        // same mistake as reading prose into a schema, one field along.
        if (IsPlaceholder(id))
        {
            missingId = type is not null || owner is not null || reviewBy is not null || links.Count > 0;
            return null;
        }

        return new KnowledgeRecord(id, type, owner, links, IsPlaceholder(reviewBy) ? null : reviewBy);
    }

    private static string Value(string raw) => raw.Trim().Trim('"').Trim('\'').Trim();

    /// <summary>Whether a value is empty, or an angle-bracketed stand-in rather than a real name.</summary>
    /// <remarks>
    /// Template files carry <c>&lt;artifact-id&gt;</c> in exactly the position a real id occupies.
    /// Indexing them puts nodes in the graph that describe the SHAPE of a document rather than
    /// anything in the repository — and their placeholder links arrive as edges between things that
    /// do not exist.
    /// </remarks>
    private static bool IsPlaceholder(
        [System.Diagnostics.CodeAnalysis.NotNullWhen(false)] string? value) =>
        string.IsNullOrEmpty(value) || (value.StartsWith('<') && value.EndsWith('>'));
}
