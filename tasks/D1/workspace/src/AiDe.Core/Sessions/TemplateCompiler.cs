using System.Text;

namespace AiDe.Core.Sessions;

/// <summary>
/// Projects a template plus values to prompt text — deterministically (R18).
/// </summary>
/// <remarks>
/// <para><b>Same template version + values → byte-identical text.</b> Three things make that a
/// property rather than a hope: the renderer walks the TEMPLATE's declared fields, never the caller's
/// dictionary, so insertion and hash order cannot reach the output; the body arrives normalised to
/// line feeds with exactly one at the end; and nothing here reads a clock, a culture, a random source
/// or the environment.</para>
///
/// <para><b>Total, not validating.</b> A field with no value renders empty. Required-ness is the form
/// engine's gate (F4) and blocking send is its job; a compiler that left <c>{{goal}}</c> in the
/// output would put template syntax in a prompt, which is worse than a blank.</para>
/// </remarks>
public static class TemplateCompiler
{
    /// <summary>Compiles <paramref name="template"/> against <paramref name="values"/>.</summary>
    /// <param name="template">The template, as loaded.</param>
    /// <param name="values">
    /// Values by field name. A text field takes the first value; a list or mentions field takes them
    /// all, in the order given — the caller's order IS the content, unlike its key order.
    /// </param>
    public static string Compile(PromptTemplate template, IReadOnlyDictionary<string, IReadOnlyList<string>> values)
    {
        ArgumentNullException.ThrowIfNull(template);
        ArgumentNullException.ThrowIfNull(values);

        var text = template.Body;

        // Sections first: a section's inner text may itself contain a scalar slot, and expanding the
        // scalars first would fill the pattern instead of each repetition.
        foreach (var field in template.Fields)
        {
            text = ExpandSections(text, field.Name, Items(values, field.Name));
        }

        foreach (var field in template.Fields)
        {
            text = text.Replace(
                "{{" + field.Name + "}}",
                string.Join('\n', Items(values, field.Name)),
                StringComparison.Ordinal);
        }

        return text;
    }

    private static IReadOnlyList<string> Items(IReadOnlyDictionary<string, IReadOnlyList<string>> values, string name)
        => values.TryGetValue(name, out var items) ? items : [];

    /// <summary>Expands every <c>{{#name}}…{{/name}}</c> block, once per item, joined by line feeds.</summary>
    private static string ExpandSections(string text, string name, IReadOnlyList<string> items)
    {
        var open = "{{#" + name + "}}";
        var close = "{{/" + name + "}}";

        var result = new StringBuilder();
        var cursor = 0;

        while (true)
        {
            var start = text.IndexOf(open, cursor, StringComparison.Ordinal);
            if (start < 0)
            {
                result.Append(text, cursor, text.Length - cursor);
                return result.ToString();
            }

            var innerStart = start + open.Length;
            var end = text.IndexOf(close, innerStart, StringComparison.Ordinal);
            if (end < 0)
            {
                // An unclosed section is a load error; reaching here means the body was never
                // validated, and leaving the text alone is the honest answer.
                result.Append(text, cursor, text.Length - cursor);
                return result.ToString();
            }

            var inner = text[innerStart..end];
            result.Append(text, cursor, start - cursor);
            result.AppendJoin('\n', items.Select(item => inner.Replace("{{.}}", item, StringComparison.Ordinal)));
            cursor = end + close.Length;
        }
    }
}
