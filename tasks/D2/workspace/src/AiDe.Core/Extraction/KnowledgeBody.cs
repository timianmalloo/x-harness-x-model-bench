using System.Text.RegularExpressions;

namespace AiDe.Core.Extraction;

/// <summary>One markdown hyperlink written in a document's prose, and the line it is on.</summary>
/// <param name="Target">The href exactly as written, minus any fragment or query.</param>
/// <param name="Line">1-based line in the file, for provenance.</param>
internal readonly record struct BodyLink(string Target, int Line);

/// <summary>What a knowledge document's BODY contains, as far as this reader looks.</summary>
/// <param name="MarkdownLinks">Inline <c>[text](path.md)</c> links, outside fenced code.</param>
/// <param name="Headings">ATX headings — COUNTED for the disclosure, not extracted. See remarks.</param>
/// <param name="InlineCodeSpans">Backticked spans — COUNTED for the disclosure, not extracted.</param>
/// <param name="DeclaresItselfAGlossary">The document says it is a glossary, by type or by name.</param>
internal sealed record KnowledgeBodySurvey(
    IReadOnlyList<BodyLink> MarkdownLinks,
    int Headings,
    int InlineCodeSpans,
    bool DeclaresItselfAGlossary);

/// <summary>
/// Reading the PROSE of a knowledge document, as opposed to the frontmatter that declares it.
/// </summary>
/// <remarks>
/// <para><b>2,359 documents were in the graph carrying nothing but their own metadata.</b> The
/// product's premise is that <em>docs hold intent, code holds reality, and the expensive defects
/// live in the gap</em> — and the half that holds intent was represented by its id, its owner and
/// its review date. This reads the one thing in a body that is a DECLARATION rather than a
/// resemblance: a markdown hyperlink whose target is another document in the same scope.</para>
///
/// <para><b>Three other candidates were measured and deliberately left unread.</b> Each is counted
/// and disclosed by <see cref="KnowledgeExtractor"/> rather than silently skipped, because a
/// boundary is only honest when it carries a number (DC-050):</para>
/// <list type="bullet">
///   <item><b>Headings</b> — 4,471 across 375 of 877 documents on TheTerrace. Not extracted, and the
///   reason is measured rather than aesthetic. A heading is a PROPERTY of its document, so it would
///   be an attribute; attribute objects are excluded from the graph by
///   <c>EvidencePredicates.Attributes</c>, so the text would not be drawn. <b>Half of this reason
///   expired on 2026-08-31:</b> it also said attribute objects were excluded from node search by
///   construction, and <c>StoreReader.SearchNodes</c> now matches them and returns the OWNING node,
///   so heading text WOULD be findable. The decision does not change — the two reasons below are
///   the ones carrying it — but the argument as written is no longer true, and a decision resting
///   on a premise nobody rechecked is the gap between docs and code this product exists to find. The full body is ALREADY served whole by
///   <c>ProjectionService.NodeContent</c> (256 KB ceiling), so nothing would become visible that is
///   not visible now. And it measurably breaks the surface it was meant to enrich: simulated on the
///   real store, <c>adr-0015-erasure-ledger-durable-model</c> returns all 19 of its facts from
///   <c>Describe</c> today, and with 40 headings per scope it returns 44 headings and loses
///   <c>has_type</c>, <c>node_class</c>, <c>owned_by</c>, <c>refines</c> and <c>review_by</c>
///   entirely — <c>has_heading</c> sorts before all of them under the reader's
///   <c>ORDER BY subject, predicate, object LIMIT 50</c>. That is DC-035 in a new place.</item>
///
///   <item><b>Glossary terms</b> — 81 across 2 documents on TheTerrace and 253 across 14 in this
///   repository, written in THREE incompatible shapes (bullet <c>- **T** — …</c>, table row
///   <c>| **T** | … |</c>, and bare paragraph <c>**T** — …</c>). The bare shape is indistinguishable
///   from ordinary bold-led prose: the same pattern matches 506 lines in 114 NON-glossary documents
///   on TheTerrace. Same attribute arithmetic as headings, on the document type where it bites
///   hardest — <c>knowledge-epl-glossary</c> loses 14 of its 17 <c>uses-term</c> backlinks in the
///   same simulation.</item>
///
///   <item><b>Code and document references in backticks</b> — ruled out by measurement, twice over.
///   Of 26,924 inline code spans in TheTerrace's documents, <b>zero</b> exactly match a C# node id:
///   node ids are fully qualified (<c>TheTerrace.Infrastructure.Data.AppDbContext</c>) and prose
///   writes the short name, so an exact-match reader is a control that could never fire (DC-016) and
///   the only way to make it produce anything is the suffix matching the user ruled out. Matching
///   against KNOWLEDGE ids does fire — 372 mentions, 156 new pairs — and is wrong often enough to
///   reject: in this repository <c>`architecture`</c> names an MCP tool and a document type in 4 of
///   its 5 occurrences, not the document whose id is <c>architecture</c>. A name collides (DC-022),
///   and the only cure on offer was a length-or-hyphen threshold tuned to the one failure observed.
///   </item>
/// </list>
///
/// <para><c>simplify: line-oriented markdown recognition rather than a CommonMark parser; ceiling is
/// inline links, ATX headings and backtick spans outside fenced code; upgrade trigger = a consumer
/// needs reference-style links, HTML anchors, or anything whose meaning depends on block nesting.
/// Measured on both corpora: 0 reference-definitions, 0 percent-encoded targets, 0 root-absolute
/// targets, 0 links inside fences and 0 inside inline code, out of 353 prose .md links.</c></para>
/// </remarks>
internal static class KnowledgeBody
{
    // Inline links only. `[text](target)`, with an optional title the target must not swallow.
    // The target stops at whitespace or `)`, which is what CommonMark's non-angle-bracket form
    // permits and what all 353 links measured on the two corpora actually use.
    private static readonly Regex InlineLink = new(
        @"\[[^\]\n]*\]\(\s*([^)\s]+?)(?:\s+""[^""]*"")?\s*\)", RegexOptions.Compiled);

    // ATX headings only. Setext (`Title\n=====`) is not counted; it does not appear in either
    // corpus and the count feeds a disclosure, where an undercount is a smaller lie than a parser.
    private static readonly Regex AtxHeading = new(@"^\s{0,3}#{1,6}\s", RegexOptions.Compiled);

    private static readonly Regex InlineCode = new(@"`[^`\n]+`", RegexOptions.Compiled);

    /// <summary>Everything after the closing frontmatter delimiter, surveyed.</summary>
    /// <param name="lines">The whole file, frontmatter included.</param>
    /// <param name="fileName">The file's own name, for the glossary self-declaration.</param>
    /// <param name="declaredType">The <c>type:</c> the frontmatter declares, if any.</param>
    public static KnowledgeBodySurvey Survey(
        IReadOnlyList<string> lines, string fileName, string? declaredType)
    {
        ArgumentNullException.ThrowIfNull(lines);

        var links = new List<BodyLink>();
        var headings = 0;
        var codeSpans = 0;
        var inFence = false;

        for (var i = BodyStart(lines); i < lines.Count; i++)
        {
            var line = lines[i];

            // A fence opens or closes. Everything between is a code sample: a link inside one is an
            // EXAMPLE of a link, and reading it would put an edge in the graph for a document that
            // is showing you what markdown looks like. Measured zero times on either corpus, which
            // is exactly why it is pinned by a fixture rather than trusted to the corpus (DC-016).
            if (IsFence(line))
            {
                inFence = !inFence;
                continue;
            }

            if (inFence) continue;

            if (AtxHeading.IsMatch(line)) headings++;

            // Inline code is BLANKED rather than skipped, so a link written inside backticks is not
            // read while the line's other links still are. Same reason the C# and Python readers
            // blank comments instead of dropping the line: the line numbers stay true.
            var text = InlineCode.Replace(line, m =>
            {
                codeSpans++;
                return new string(' ', m.Length);
            });

            foreach (Match match in InlineLink.Matches(text))
            {
                var target = match.Groups[1].Value;

                // A fragment or query is navigation WITHIN a target, not part of its identity.
                var cut = target.IndexOfAny(['#', '?']);
                if (cut >= 0) target = target[..cut];

                if (target.Length == 0) continue;

                links.Add(new BodyLink(target, i + 1));
            }
        }

        return new KnowledgeBodySurvey(links, headings, codeSpans, IsGlossary(fileName, declaredType));
    }

    /// <summary>
    /// Whether the document says it is a glossary — by its declared type, or by its file name.
    /// </summary>
    /// <remarks>
    /// Both, because both are used: TheTerrace's two glossaries carry <c>type: glossary</c>, and
    /// this repository's fourteen are <c>type: knowledge</c> in a file called <c>glossary.md</c>.
    /// A reader that only knew one of them would report the other repository as having none.
    /// </remarks>
    private static bool IsGlossary(string fileName, string? declaredType) =>
        string.Equals(declaredType, "glossary", StringComparison.OrdinalIgnoreCase)
        || Path.GetFileNameWithoutExtension(fileName)
            .StartsWith("glossary", StringComparison.OrdinalIgnoreCase);

    /// <summary>The first line after the frontmatter block, or 0 when there is no block.</summary>
    /// <remarks>
    /// The frontmatter is skipped rather than surveyed because it is not prose. MEASURED across both
    /// corpora: 15 frontmatter lines open with <c>#</c> — <c>`# ---- Prior revisions ----`</c> in the
    /// pack's INSTALL.md, <c>`# Syntax palette ...`</c> in DESIGN.md — and every one of them would be
    /// counted as a heading by a survey that started at line 0.
    ///
    /// The no-frontmatter guard on the first line is for TOTALITY only and cannot fire through
    /// <see cref="KnowledgeExtractor"/>: nothing is surveyed unless
    /// <see cref="KnowledgeFrontmatter.Read"/> already returned a record, which it only does for a
    /// file opening with <c>---</c>. Proved by mutation rather than assumed — removing it kills no
    /// test, and it is kept as a total function's guard rather than claimed as a control (DC-016).
    /// </remarks>
    private static int BodyStart(IReadOnlyList<string> lines)
    {
        if (lines.Count == 0 || lines[0].Trim() != "---") return 0;

        for (var i = 1; i < lines.Count; i++)
        {
            if (lines[i].Trim() == "---") return i + 1;
        }

        // An unterminated block is all frontmatter and no body. Returning 0 instead would read the
        // whole YAML as prose, and `- { to: x, rel: y }` lines would be surveyed as text.
        return lines.Count;
    }

    /// <summary>A fenced code block's delimiter — three or more backticks or tildes.</summary>
    private static bool IsFence(string line)
    {
        var trimmed = line.TrimStart();

        return trimmed.StartsWith("```", StringComparison.Ordinal)
            || trimmed.StartsWith("~~~", StringComparison.Ordinal);
    }
}
