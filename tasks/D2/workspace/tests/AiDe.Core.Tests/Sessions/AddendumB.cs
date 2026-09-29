using System.Collections.Generic;
using System.Linq;
using System.Text.RegularExpressions;

namespace AiDe.Core.Tests.Sessions;

/// <summary>One row of Addendum B §B4's catalog table, read from the committed spec.</summary>
internal sealed record B4Row(string Id, string Intent, string Audience, string CoreFields, string WhenToUse, string Why);

/// <summary>
/// Reads §B4 out of the spec HTML so the transcription is CHECKED rather than restated (Ruling 30).
/// </summary>
/// <remarks>
/// <para><b>An independent second implementation, on purpose.</b> The twelve files were produced by a
/// one-off script that read the same table; this parser is written separately in another language,
/// so a transcription mistake has to be made twice, identically, to survive.</para>
///
/// <para><b>The mechanical rules are stated here because they are the transcription contract:</b>
/// a core-fields cell splits on <c>,</c> and on <c>+</c>; each item slugs to lowercase with every
/// non-alphanumeric run collapsed to <c>_</c>; and <c>goal-block</c>'s why drops the trailing
/// parenthetical that begins at <see cref="DroppedWhyMarker"/> (Ruling 30 deviation i).</para>
/// </remarks>
internal static class AddendumB
{
    internal const string DroppedWhyMarker = " (Addendum A's";

    internal static IReadOnlyList<B4Row> CatalogRows()
    {
        var html = RepoFiles.AddendumBHtml();
        var b4 = html.Split("<h2><span class=\"n\">B4</span>")[1].Split("</table>")[0];

        var rows = new List<B4Row>();
        foreach (Match row in Regex.Matches(b4, "<tr>(.*?)</tr>", RegexOptions.Singleline))
        {
            var cells = Regex.Matches(row.Groups[1].Value, "<t[dh]>(.*?)</t[dh]>", RegexOptions.Singleline)
                .Select(c => Regex.Replace(c.Groups[1].Value, "<[^>]+>", string.Empty).Trim())
                .ToList();

            if (cells.Count != 5 || cells[0] == "Template")
            {
                continue;
            }

            var parts = cells[1].Split('·');
            rows.Add(new B4Row(cells[0], parts[0].Trim(), parts[1].Trim(), cells[2], cells[3], cells[4]));
        }

        return rows;
    }

    /// <summary>The row's why as it must appear in the template — B4's cell, minus deviation i's drop.</summary>
    internal static string WhyForTemplate(B4Row row)
    {
        var cut = row.Why.IndexOf(DroppedWhyMarker, StringComparison.Ordinal);
        return cut < 0 ? row.Why : row.Why[..cut].TrimEnd();
    }

    /// <summary>What deviation i dropped, or null when the row dropped nothing.</summary>
    internal static string? DroppedFromWhy(B4Row row)
    {
        var cut = row.Why.IndexOf(DroppedWhyMarker, StringComparison.Ordinal);
        return cut < 0 ? null : row.Why[cut..].Trim();
    }

    internal static IReadOnlyList<string> FieldNames(B4Row row)
        => row.CoreFields
            .Split(',')
            .SelectMany(part => part.Split('+'))
            .Select(item => item.Trim())
            .Where(item => item.Length > 0)
            .Select(Slug)
            .ToList();

    internal static string Slug(string item)
        => Regex.Replace(item.ToLowerInvariant(), "[^a-z0-9]+", "_").Trim('_');

    /// <summary>Theory data: the twelve rows, one per case, so a failure names the row it is about.</summary>
    internal static TheoryData<string> Ids()
    {
        var data = new TheoryData<string>();
        foreach (var row in CatalogRows())
        {
            data.Add(row.Id);
        }

        return data;
    }

    internal static B4Row Row(string id) => CatalogRows().Single(r => r.Id == id);
}
