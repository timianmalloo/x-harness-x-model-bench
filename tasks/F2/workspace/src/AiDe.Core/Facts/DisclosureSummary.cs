using System.Globalization;
using System.Text.RegularExpressions;

namespace AiDe.Core.Facts;

/// <summary>
/// Folds per-scope disclosures into one line per class, with the counts added up.
/// </summary>
/// <remarks>
/// <para><b>Every disclosure was right and the list was unusable.</b> A disclosure is emitted per
/// scope, conditional, and carrying its own count — which is the rule this codebase arrived at after
/// several defects, and it is correct. Nobody said what happens when 39 knowledge scopes each emit
/// the same two. MEASURED on TheTerrace after a real index: <b>178 disclosure strings, 108 distinct,
/// for 28 actual classes</b> — <c>knowledge-headings-not-analysed</c> alone appeared 39 times, each
/// with a different number, so <c>Distinct()</c> could not merge any of them.</para>
///
/// <para>The result filled the user's window: roughly sixty lines of near-identical text, with the
/// one finding that mattered — 109 prose links naming a file that is not there — buried in the
/// middle of it. <b>A boundary stated 39 times is noise, and noise is where a real signal goes to
/// hide.</b> That is this codebase's own lesson about disclosures, arrived at from the other
/// direction: it has spent a lot of effort making sure they fire, and none on what a reader does
/// with sixty of them.</para>
///
/// <para><b>The counts are summed, not the lines deduplicated.</b> "914 headings in one scope" and
/// "4,471 headings across the workspace" are different facts, and only the second answers "how much
/// of this repository is unread". The explanatory half of the sentence is kept from the first
/// occurrence, because every scope emits the same template.</para>
/// </remarks>
public static class DisclosureSummary
{
    /// <summary>The leading count inside a disclosure's parenthetical, if it has one.</summary>
    /// <remarks>
    /// Anchored to the start of the parenthetical rather than the first number anywhere: the
    /// explanations contain numbers of their own (<c>"914 heading(s) in 59 document(s)"</c>) and
    /// summing the wrong one would produce a total that is confidently meaningless.
    /// </remarks>
    private static readonly Regex LeadingCount = new(
        @"^\((?<count>\d[\d,]*)", RegexOptions.Compiled);

    /// <summary>One line per disclosure class, counts summed across every scope that raised it.</summary>
    public static IReadOnlyList<string> Fold(IEnumerable<string> disclosures)
    {
        ArgumentNullException.ThrowIfNull(disclosures);

        var byClass = new Dictionary<string, (long Total, bool Counted, string First, int Lines)>(
            StringComparer.Ordinal);

        foreach (var disclosure in disclosures)
        {
            var split = disclosure.IndexOf(" (", StringComparison.Ordinal);
            var name = split < 0 ? disclosure : disclosure[..split];
            var detail = split < 0 ? string.Empty : disclosure[(split + 1)..];

            var match = LeadingCount.Match(detail);

            var count = match.Success
                && long.TryParse(
                    match.Groups["count"].Value, NumberStyles.AllowThousands, CultureInfo.InvariantCulture,
                    out var parsed)
                    ? parsed
                    : 0L;

            if (byClass.TryGetValue(name, out var seen))
            {
                byClass[name] = (seen.Total + count, seen.Counted || match.Success, seen.First, seen.Lines + 1);
            }
            else
            {
                byClass[name] = (count, match.Success, detail, 1);
            }
        }

        return
        [
            .. byClass
                .OrderBy(e => e.Key, StringComparer.Ordinal)
                .Select(e => Render(e.Key, e.Value.Total, e.Value.Counted, e.Value.First, e.Value.Lines))
        ];
    }

    /// <summary>
    /// The count a folded disclosure carries, or zero when it names no number.
    /// </summary>
    /// <remarks>
    /// Exposed so a caller choosing WHICH disclosure to show does not re-parse the sentence this
    /// class just built — two readers of one format is how the two halves of a rule drift apart.
    /// </remarks>
    public static long CountIn(string folded)
    {
        ArgumentNullException.ThrowIfNull(folded);

        var open = folded.IndexOf(" (", StringComparison.Ordinal);

        if (open < 0) return 0;

        var match = LeadingCount.Match(folded[(open + 1)..]);

        return match.Success
            && long.TryParse(
                match.Groups["count"].Value, NumberStyles.AllowThousands, CultureInfo.InvariantCulture,
                out var parsed)
                ? parsed
                : 0;
    }

    private static readonly char[] Digits = ['0','1','2','3','4','5','6','7','8','9'];

    private static string Render(string name, long total, bool counted, string first, int lines)
    {
        if (!counted) return name;

        // ONE scope: its own sentence is exactly true, so it is kept whole.
        if (lines == 1) return $"{name} {first}";

        // SEVERAL scopes: the leading count becomes the workspace total, and everything from the
        // NEXT number onwards is cut away.
        //
        // Those later numbers are that one scope's, and folding leaves them beside a total they no
        // longer describe: `knowledge-headings-not-analysed` rendered as "4,471 heading(s) in 10
        // document(s)" — a true total next to one scope's document count, which is a worse answer
        // than either alone because it reads as though somebody counted both. A stale number inside
        // a corrected one is the shape this register calls out repeatedly.
        var body = LeadingCount.Replace(
            first, total.ToString("N0", CultureInfo.InvariantCulture), 1);

        var nextNumber = body.IndexOfAny(Digits, total.ToString("N0", CultureInfo.InvariantCulture).Length);
        if (nextNumber >= 0) body = body[..nextNumber];

        return $"{name} ({TrimDanglingWord(body)}, across {lines} scope(s))";
    }

    /// <summary>
    /// Words the cut can leave hanging, when the sentence continued into a second number.
    /// </summary>
    /// <remarks>
    /// Cutting "914 heading(s) in 59 document(s)" at the second number leaves "914 heading(s) in",
    /// and a dangling preposition reads like truncation damage rather than a decision. Trimmed to
    /// "4,471 heading(s), across 39 scope(s)", which is a whole sentence about the workspace.
    /// </remarks>
    private static readonly string[] Dangling =
        ["in", "across", "of", "and", "for", "on", "with", "to", "from", "that", "which"];

    private static string TrimDanglingWord(string text)
    {
        var trimmed = text.TrimEnd(')', ' ', ',', ';', '.').TrimEnd();

        var lastSpace = trimmed.LastIndexOf(' ');

        if (lastSpace > 0
            && Dangling.Contains(trimmed[(lastSpace + 1)..], StringComparer.OrdinalIgnoreCase))
        {
            trimmed = trimmed[..lastSpace].TrimEnd(',', ' ');
        }

        return trimmed;
    }
}
