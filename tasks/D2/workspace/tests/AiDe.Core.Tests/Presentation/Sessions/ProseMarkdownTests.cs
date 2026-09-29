using AiDe.Core.Presentation.Sessions;

namespace AiDe.Core.Tests.Sessions.Thread;

/// <summary>
/// The markdown subset (CV-5.3's design-slice answer; Ruling 82): headings · paragraphs · lists ·
/// fenced code · pipe tables; inline code · bold · italic · inert links — as goldens over text the
/// lane writes, including the operator's screenshot-3 shapes (<c>## Gaps I noticed</c>,
/// <c>| What | Result |</c>, <c>|---|---|</c>) and Ruling 87's <c>—</c> / <c>§</c>. What is outside
/// the subset stays literal text, never dropped.
/// </summary>
/// <remarks><b>Red observed</b> against a parser that returns the text as one paragraph: the first golden failed on <c>Heading</c> vs <c>Paragraph</c>.</remarks>
public sealed class ProseMarkdownTests
{
    private static ProseInline T(string text) => new(ProseInlineKind.Text, text);

    [Fact]
    public void TheScreenshot3Shapes_ParseToHeadingParagraphTableAndList()
    {
        var blocks = ProseMarkdown.Parse(
            "## Gaps I noticed\n\nTwo stores — see §4.\n\n| What | Result |\n|---|---|\n| Red first | `Failed` on the old order |\n| Green | **14 passed** |\n\n- `LayoutStore` — tree schema\n- `ZoneLayoutStore`\n\n1. first\n2. second");

        Assert.Equal(5, blocks.Count);
        var heading = Assert.IsType<ProseBlock.Heading>(blocks[0]);
        Assert.Equal(2, heading.Level);
        Assert.Equal([T("Gaps I noticed")], heading.Inlines);

        var paragraph = Assert.IsType<ProseBlock.Paragraph>(blocks[1]);
        Assert.Equal([T("Two stores — see §4.")], paragraph.Inlines);

        var table = Assert.IsType<ProseBlock.Table>(blocks[2]);
        Assert.Equal([[T("What")], [T("Result")]], table.Header);
        Assert.Equal(2, table.Rows.Count);
        Assert.Equal([T("Red first")], table.Rows[0][0]);
        Assert.Equal([new ProseInline(ProseInlineKind.Code, "Failed"), T(" on the old order")], table.Rows[0][1]);
        Assert.Equal([new ProseInline(ProseInlineKind.Bold, "14 passed")], table.Rows[1][1]);

        var bullets = Assert.IsType<ProseBlock.ListBlock>(blocks[3]);
        Assert.False(bullets.Ordered);
        Assert.Equal(2, bullets.Items.Count);
        Assert.Equal([new ProseInline(ProseInlineKind.Code, "LayoutStore"), T(" — tree schema")], bullets.Items[0]);

        var numbered = Assert.IsType<ProseBlock.ListBlock>(blocks[4]);
        Assert.True(numbered.Ordered);
        Assert.Equal([[T("first")], [T("second")]], numbered.Items);
    }

    [Fact]
    public void AFencedBlock_IsVerbatim_AndAnUnterminatedFence_RunsToTheEnd()
    {
        var blocks = ProseMarkdown.Parse("Before\n```csharp\nvar x = **not bold**;\n# not a heading\n```\nAfter\n```\ntail");

        Assert.Equal(4, blocks.Count);
        Assert.Equal("var x = **not bold**;\n# not a heading", Assert.IsType<ProseBlock.Code>(blocks[1]).Text);
        Assert.Equal([T("After")], Assert.IsType<ProseBlock.Paragraph>(blocks[2]).Inlines);
        Assert.Equal("tail", Assert.IsType<ProseBlock.Code>(blocks[3]).Text);
    }

    [Fact]
    public void ALink_IsItsTextWithItsUrl_AndEmphasisNestsNowhere()
    {
        var spans = ProseMarkdown.Inlines("see [the review](docs/reviews/r.md) and *this* or **that** `code`");

        Assert.Equal(
            [
                T("see "),
                new ProseInline(ProseInlineKind.Link, "the review", "docs/reviews/r.md"),
                T(" and "),
                new ProseInline(ProseInlineKind.Italic, "this"),
                T(" or "),
                new ProseInline(ProseInlineKind.Bold, "that"),
                T(" "),
                new ProseInline(ProseInlineKind.Code, "code"),
            ],
            spans);
    }

    /// <summary>Outside the subset is literal: a blockquote marker, a lone asterisk, an underscore, a horizontal rule — the reader sees the source, nothing vanishes.</summary>
    [Theory]
    [InlineData("> a quote", "> a quote")]
    [InlineData("a * b * c", "a * b * c")]
    [InlineData("snake_case_name", "snake_case_name")]
    [InlineData("---", "---")]
    [InlineData("2 * 3 = 6 and 4*5", "2 * 3 = 6 and 4*5")]
    public void WhatIsOutsideTheSubset_StaysLiteral(string text, string expected)
    {
        var paragraph = Assert.IsType<ProseBlock.Paragraph>(Assert.Single(ProseMarkdown.Parse(text)));
        Assert.Equal(expected, string.Concat(paragraph.Inlines.Select(i => i.Text)));
    }

    [Fact]
    public void ParagraphLinesJoin_BlankLinesSeparate_AndEmptyTextIsNoBlock()
    {
        Assert.Empty(ProseMarkdown.Parse(string.Empty));
        Assert.Empty(ProseMarkdown.Parse("\n\n"));

        var blocks = ProseMarkdown.Parse("one\ntwo\n\nthree\r\nfour");
        Assert.Equal(2, blocks.Count);
        Assert.Equal([T("one two")], Assert.IsType<ProseBlock.Paragraph>(blocks[0]).Inlines);
        Assert.Equal([T("three four")], Assert.IsType<ProseBlock.Paragraph>(blocks[1]).Inlines);
    }

    /// <summary>A table's separator row is structure in every spelling — never a body row.</summary>
    [Theory]
    [InlineData("| a | b |\n|---|---|\n| 1 | 2 |")]
    [InlineData("| a | b |\n| --- | --- |\n| 1 | 2 |")]
    [InlineData("| a | b |\n|:---:|---:|\n| 1 | 2 |")]
    public void ATableSeparator_IsStructure_InEverySpelling(string text)
    {
        var table = Assert.IsType<ProseBlock.Table>(Assert.Single(ProseMarkdown.Parse(text)));
        Assert.Equal([[T("a")], [T("b")]], table.Header);
        Assert.Equal([[[T("1")], [T("2")]]], table.Rows);
    }

    /// <summary>
    /// D2, over generated documents (seeded — D0): a document assembled from the subset's grammar
    /// parses to exactly the blocks it was assembled from, and the plain text of every block is the
    /// text it was given — nothing of the lane's answer is dropped, re-ordered or invented, over
    /// 200 documents per seed of 1–8 blocks each. A parser that drops a list item, a table row or a
    /// code line, or that swallows a heading into the paragraph before it, fails here.
    /// </summary>
    [Theory]
    [InlineData(1)]
    [InlineData(7)]
    [InlineData(42)]
    [InlineData(1981)]
    public void OverGeneratedDocuments_TheBlocksAndTheirTextRoundTrip(int seed)
    {
        var random = new Random(seed);
        string[] words = ["alpha", "beta", "gamma", "delta", "§4", "—", "x1", "store", "layout", "refused"];
        string Words(int n) => string.Join(' ', Enumerable.Range(0, n).Select(_ => words[random.Next(words.Length)]));

        for (var document = 0; document < 200; document++)
        {
            var source = new List<string>();
            var expected = new List<(string Kind, IReadOnlyList<string> Texts)>();
            var blocks = random.Next(1, 9);
            for (var b = 0; b < blocks; b++)
            {
                switch (random.Next(5))
                {
                    case 0:
                        var level = random.Next(1, 4);
                        var heading = Words(random.Next(1, 5));
                        source.Add(new string('#', level) + " " + heading);
                        expected.Add(("Heading" + level, [heading]));
                        break;
                    case 1:
                        var lines = Enumerable.Range(0, random.Next(1, 4)).Select(_ => Words(random.Next(1, 7))).ToList();
                        source.Add(string.Join('\n', lines));
                        expected.Add(("Paragraph", [string.Join(' ', lines)]));
                        break;
                    case 2:
                        var ordered = random.Next(2) == 0;
                        var items = Enumerable.Range(0, random.Next(1, 5)).Select(_ => Words(random.Next(1, 5))).ToList();
                        source.Add(string.Join('\n', items.Select((item, i) => (ordered ? (i + 1) + ". " : "- ") + item)));
                        expected.Add((ordered ? "Ordered" : "Bulleted", items));
                        break;
                    case 3:
                        var code = Enumerable.Range(0, random.Next(1, 4)).Select(_ => "# " + Words(random.Next(1, 4))).ToList();
                        source.Add("```\n" + string.Join('\n', code) + "\n```");
                        expected.Add(("Code", [string.Join('\n', code)]));
                        break;
                    default:
                        var columns = random.Next(1, 4);
                        var rows = random.Next(1, 4);
                        var cells = Enumerable.Range(0, rows + 1).Select(_ => Enumerable.Range(0, columns).Select(_ => Words(random.Next(1, 3))).ToList()).ToList();
                        source.Add(string.Join('\n', [$"| {string.Join(" | ", cells[0])} |", "|" + string.Concat(Enumerable.Repeat("---|", columns)), .. cells.Skip(1).Select(r => $"| {string.Join(" | ", r)} |")]));
                        expected.Add(("Table", [.. cells.SelectMany(r => r)]));
                        break;
                }
            }

            var parsed = ProseMarkdown.Parse(string.Join("\n\n", source));
            static string Flat(string kind, IEnumerable<string> texts) => kind + ": " + string.Join(" | ", texts);
            Assert.Equal(expected.Select(e => Flat(e.Kind, e.Texts)), parsed.Select(block => Flat(Kind(block), Texts(block))));
        }
    }

    private static string Kind(ProseBlock block) => block switch
    {
        ProseBlock.Heading h => "Heading" + h.Level,
        ProseBlock.Paragraph => "Paragraph",
        ProseBlock.ListBlock l => l.Ordered ? "Ordered" : "Bulleted",
        ProseBlock.Code => "Code",
        ProseBlock.Table => "Table",
        _ => throw new ArgumentOutOfRangeException(nameof(block)),
    };

    /// <summary>The plain text of a block: one string per heading / paragraph / list item / table cell, the code verbatim.</summary>
    private static IEnumerable<string> Texts(ProseBlock block) => block switch
    {
        ProseBlock.Heading h => [string.Concat(h.Inlines.Select(i => i.Text))],
        ProseBlock.Paragraph p => [string.Concat(p.Inlines.Select(i => i.Text))],
        ProseBlock.ListBlock l => l.Items.Select(item => string.Concat(item.Select(i => i.Text))),
        ProseBlock.Code c => [c.Text],
        ProseBlock.Table t => t.Header.Concat(t.Rows.SelectMany(r => r)).Select(cell => string.Concat(cell.Select(i => i.Text))),
        _ => [],
    };
}
