using System.Text.RegularExpressions;

namespace AiDe.Core.Presentation.Sessions;

/// <summary>One inline span of the prose: plain, code, bold, italic, or a link — which is its text followed by its URL, never a control.</summary>
public enum ProseInlineKind
{
    Text,
    Code,
    Bold,
    Italic,
    Link,
}

/// <summary>A span of inline text; <paramref name="Url"/> is set for a link only.</summary>
public sealed record ProseInline(ProseInlineKind Kind, string Text, string? Url = null);

/// <summary>One block of the prose (Ruling 82's markdown subset, CV-5.3's design-slice answer).</summary>
public abstract record ProseBlock
{
    /// <summary><c>#</c> · <c>##</c> · <c>###</c> — one size, the weight carries the level.</summary>
    public sealed record Heading(int Level, IReadOnlyList<ProseInline> Inlines) : ProseBlock;

    public sealed record Paragraph(IReadOnlyList<ProseInline> Inlines) : ProseBlock;

    /// <summary><c>- </c> / <c>* </c> items, or <c>1. </c> items when <paramref name="Ordered"/>.</summary>
    public sealed record ListBlock(bool Ordered, IReadOnlyList<IReadOnlyList<ProseInline>> Items) : ProseBlock;

    /// <summary>A fenced block, verbatim, the fence's language tag dropped.</summary>
    public sealed record Code(string Text) : ProseBlock;

    /// <summary>A pipe table: the header row, then the body rows (the <c>|---|</c> separator is structure, never a row).</summary>
    public sealed record Table(IReadOnlyList<IReadOnlyList<ProseInline>> Header, IReadOnlyList<IReadOnlyList<IReadOnlyList<ProseInline>>> Rows) : ProseBlock;
}

/// <summary>
/// The markdown subset the reply renders — headings, paragraphs, lists, fenced code, pipe tables;
/// inline code, bold, italic and inert links — parsed once here, pure, so the goldens are text in
/// and blocks out, and the WPF renderer maps blocks to elements and nothing else. Anything outside
/// the subset stays literal text: the reader sees the source, never a dropped line (Ruling 82: the
/// operator's screenshot showed the source because nothing rendered it; a subset that silently ate
/// what it did not understand would be the opposite defect). Fenced code is in the subset for the
/// same reason: without the fence rule the other rules corrupt code — a <c># comment</c> becomes a
/// heading, <c>- x</c> a bullet, <c>| a |</c> a table.
/// </summary>
/// <remarks>
/// <c>simplify:</c> a hand-built subset (five block kinds, four inline kinds; no nested lists,
/// block quotes, images or HTML) over native WPF inlines rather than a new dependency — ceiling:
/// this subset, no sixth block kind; upgrade trigger: ADR-0025's Markdig.Wpf landing for the code
/// viewer, at which point this parser is deleted and <c>ProseMarkdownTests</c>' goldens become the
/// replacement's acceptance, so the thread and the viewer never render markdown two ways.
/// </remarks>
public static partial class ProseMarkdown
{
    [GeneratedRegex(@"`([^`]+)`|\*\*([^*]+)\*\*|\*([^*\s][^*]*)\*|\[([^\]]+)\]\(([^)\s]+)\)")]
    private static partial Regex InlinePattern();

    [GeneratedRegex(@"^(#{1,3})\s+(.*)$")]
    private static partial Regex HeadingPattern();

    [GeneratedRegex(@"^\d+\.\s+")]
    private static partial Regex OrderedPattern();

    /// <summary>The blocks of <paramref name="text"/>, in order. Empty text yields no blocks.</summary>
    public static IReadOnlyList<ProseBlock> Parse(string text)
    {
        ArgumentNullException.ThrowIfNull(text);

        var lines = text.ReplaceLineEndings("\n").Split('\n');
        var blocks = new List<ProseBlock>();
        for (var i = 0; i < lines.Length;)
        {
            var line = lines[i];
            if (line.StartsWith("```", StringComparison.Ordinal))
            {
                var end = Array.FindIndex(lines, i + 1, l => l.StartsWith("```", StringComparison.Ordinal));
                var stop = end < 0 ? lines.Length : end;
                blocks.Add(new ProseBlock.Code(string.Join('\n', lines, i + 1, stop - (i + 1))));
                i = stop + 1;
            }
            else if (HeadingPattern().Match(line) is { Success: true } heading)
            {
                blocks.Add(new ProseBlock.Heading(heading.Groups[1].Length, Inlines(heading.Groups[2].Value)));
                i++;
            }
            else if (line.StartsWith('|'))
            {
                var rows = Take(lines, ref i, l => l.StartsWith('|')).Select(Cells).ToList();
                blocks.Add(new ProseBlock.Table(rows[0], [.. rows.Skip(1).Where(r => !r.All(c => c.Count == 1 && c[0].Text.Trim('-', ':', ' ').Length == 0))]));
            }
            else if (IsBullet(line))
            {
                blocks.Add(new ProseBlock.ListBlock(false, [.. Take(lines, ref i, IsBullet).Select(l => Inlines(l[2..]))]));
            }
            else if (OrderedPattern().IsMatch(line))
            {
                blocks.Add(new ProseBlock.ListBlock(true, [.. Take(lines, ref i, OrderedPattern().IsMatch).Select(l => Inlines(OrderedPattern().Replace(l, string.Empty, 1)))]));
            }
            else if (line.Trim().Length == 0)
            {
                i++;
            }
            else
            {
                blocks.Add(new ProseBlock.Paragraph(Inlines(string.Join(' ', Take(lines, ref i, IsParagraphLine)))));
            }
        }

        return blocks;
    }

    private static bool IsBullet(string line) => line.StartsWith("- ", StringComparison.Ordinal) || line.StartsWith("* ", StringComparison.Ordinal);

    private static bool IsParagraphLine(string line) =>
        line.Trim().Length > 0 && !line.StartsWith("```", StringComparison.Ordinal) && !HeadingPattern().IsMatch(line)
        && !line.StartsWith('|') && !IsBullet(line) && !OrderedPattern().IsMatch(line);

    /// <summary>The run of lines from <paramref name="i"/> that satisfy <paramref name="take"/>; advances <paramref name="i"/> past them.</summary>
    private static List<string> Take(string[] lines, ref int i, Func<string, bool> take)
    {
        var run = new List<string>();
        while (i < lines.Length && take(lines[i]))
        {
            run.Add(lines[i++]);
        }

        return run;
    }

    private static IReadOnlyList<IReadOnlyList<ProseInline>> Cells(string row) =>
        [.. row.Trim().Trim('|').Split('|').Select(c => Inlines(c.Trim()))];

    /// <summary>The inline spans of one line: the pattern's matches with the plain text between them.</summary>
    public static IReadOnlyList<ProseInline> Inlines(string line)
    {
        ArgumentNullException.ThrowIfNull(line);

        var spans = new List<ProseInline>();
        var at = 0;
        foreach (Match m in InlinePattern().Matches(line))
        {
            if (m.Index > at)
            {
                spans.Add(new ProseInline(ProseInlineKind.Text, line[at..m.Index]));
            }

            spans.Add(
                m.Groups[1].Success ? new ProseInline(ProseInlineKind.Code, m.Groups[1].Value)
                : m.Groups[2].Success ? new ProseInline(ProseInlineKind.Bold, m.Groups[2].Value)
                : m.Groups[3].Success ? new ProseInline(ProseInlineKind.Italic, m.Groups[3].Value)
                : new ProseInline(ProseInlineKind.Link, m.Groups[4].Value, m.Groups[5].Value));
            at = m.Index + m.Length;
        }

        if (at < line.Length)
        {
            spans.Add(new ProseInline(ProseInlineKind.Text, line[at..]));
        }

        return spans;
    }
}
