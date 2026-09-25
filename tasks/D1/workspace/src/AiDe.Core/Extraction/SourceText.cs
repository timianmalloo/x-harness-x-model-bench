using System.Text;

namespace AiDe.Core.Extraction;

/// <summary>
/// Removing the parts of a file that are commentary, before a line-oriented reader believes them.
/// </summary>
/// <remarks>
/// <para><b>Four readers were caught inventing on the same day.</b> A shared control fed each
/// extractor a corpus with no declarations and plenty of text SHAPED like declarations, and the SQL,
/// TypeScript and Python readers all reported things that existed only inside comments:
/// <c>table:Ghost</c> from <c>-- CREATE TABLE Ghost</c>, a class from
/// <c>/* export class Removed {} */</c>, a class from inside a docstring.</para>
///
/// <para><b>Commented-out code is the worst possible input for a line-oriented reader</b>, because it
/// is real syntax — it was code, which is why it is shaped exactly like code. Every repository is
/// full of it. A fact read out of a comment is not a gap, it is a confident claim about something
/// that does not exist, and it arrives labelled Verified.</para>
///
/// <para><c>simplify: character-scan comment removal rather than a lexer per language; ceiling is
/// line comments, block comments and quoted strings; upgrade trigger = a reader needs to know what
/// was inside a string as opposed to merely skipping it.</c></para>
/// </remarks>
public static class SourceText
{
    /// <summary>
    /// The text with C-style comments blanked out, keeping every line and column.
    /// </summary>
    /// <remarks>
    /// Replaced with spaces rather than deleted so that line numbers, and therefore provenance, stay
    /// true. A reader that reports the wrong line is a reader nobody can follow back to the source.
    /// </remarks>
    /// <param name="blankStrings">
    /// Whether the CONTENTS of string literals are blanked too. A C-family reader wants them kept —
    /// a SQL statement lives inside one. A DDL reader wants them gone: <c>PRINT 'about to create
    /// table X'</c> names no table, and dynamic SQL is DDL this reader cannot evaluate, so it reads
    /// neither and discloses the count instead.
    /// </param>
    /// <param name="singleQuotedStringsOnly">
    /// Whether only <c>'…'</c> delimits a string. In SQL <c>"…"</c> is a quoted IDENTIFIER — a table
    /// or column name — so blanking it deletes the very thing a schema reader is looking for.
    /// Blanking `"main"."Thing"` cost this reader a test, which is the cheapest possible way to find
    /// out that the two languages disagree about a quote character.
    /// </param>
    public static string WithoutCComments(
        string text,
        bool doubleDashLineComments = false,
        bool blankStrings = false,
        bool singleQuotedStringsOnly = false)
    {
        ArgumentNullException.ThrowIfNull(text);

        var result = new StringBuilder(text.Length);
        var i = 0;

        while (i < text.Length)
        {
            var c = text[i];

            if (c == '\'' || (c == '"' && !singleQuotedStringsOnly))
            {
                var quote = c;
                result.Append(c);
                i++;

                while (i < text.Length)
                {
                    // SQL escapes a quote by doubling it; C-family languages use a backslash. Both
                    // are handled so a string ends where the language says it ends.
                    if (text[i] == '\\' && i + 1 < text.Length)
                    {
                        result.Append(blankStrings ? "  " : text.Substring(i, 2));
                        i += 2;
                        continue;
                    }

                    var closing = text[i] == quote;
                    var keep = !blankStrings || closing || text[i] == '\n';

                    result.Append(keep ? text[i] : ' ');

                    if (closing)
                    {
                        i++;
                        break;
                    }

                    i++;
                }

                continue;
            }

            if (c == '/' && i + 1 < text.Length && text[i + 1] == '/')
            {
                i = Blank(text, result, i, EndOfLine(text, i));
                continue;
            }

            if (doubleDashLineComments && c == '-' && i + 1 < text.Length && text[i + 1] == '-')
            {
                i = Blank(text, result, i, EndOfLine(text, i));
                continue;
            }

            if (c == '/' && i + 1 < text.Length && text[i + 1] == '*')
            {
                var close = text.IndexOf("*/", i + 2, StringComparison.Ordinal);
                i = Blank(text, result, i, close < 0 ? text.Length : close + 2);
                continue;
            }

            result.Append(c);
            i++;
        }

        return result.ToString();
    }

    /// <summary>
    /// The text with <c>#</c> comments and triple-quoted blocks blanked out.
    /// </summary>
    /// <remarks>
    /// A docstring is the Python case that matters: it holds example code at column zero, which is
    /// precisely what the declaration reader looks for.
    /// </remarks>
    public static string WithoutPythonComments(string text)
    {
        ArgumentNullException.ThrowIfNull(text);

        var result = new StringBuilder(text.Length);
        var i = 0;

        while (i < text.Length)
        {
            if (Triple(text, i) is { } fence)
            {
                var close = text.IndexOf(fence, i + 3, StringComparison.Ordinal);
                i = Blank(text, result, i, close < 0 ? text.Length : close + 3);
                continue;
            }

            if (text[i] == '#')
            {
                i = Blank(text, result, i, EndOfLine(text, i));
                continue;
            }

            result.Append(text[i]);
            i++;
        }

        return result.ToString();
    }

    private static string? Triple(string text, int i) =>
        i + 2 < text.Length && (text[i] == '"' || text[i] == '\'') && text[i + 1] == text[i] && text[i + 2] == text[i]
            ? text.Substring(i, 3)
            : null;

    private static int EndOfLine(string text, int from)
    {
        var end = text.IndexOf('\n', from);
        return end < 0 ? text.Length : end;
    }

    /// <summary>Replaces a span with spaces, keeping newlines so line numbers survive.</summary>
    private static int Blank(string text, StringBuilder result, int from, int to)
    {
        for (var i = from; i < to && i < text.Length; i++)
        {
            result.Append(text[i] == '\n' ? '\n' : ' ');
        }

        return to;
    }
}
