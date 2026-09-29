using System.Collections.Generic;
using System.Linq;
using System.Text;
using AiDe.Core.Sessions;

namespace AiDe.Core.Tests.Sessions;

/// <summary>
/// FT clause 3 — same template version + values produces byte-identical prompt text.
/// </summary>
/// <remarks>
/// <para><b>Bytes, not strings.</b> The clause says byte-identical, and a string comparison would
/// pass over a line-ending or encoding difference that a consumer writing the text to a file would
/// see. The assertion is on UTF-8 bytes.</para>
///
/// <para><b>The values arrive in a different order each time.</b> Compiling one dictionary twice
/// proves almost nothing: the interesting non-determinism is a renderer that walks the VALUES rather
/// than the template, and that only shows when insertion order differs.</para>
/// </remarks>
public sealed class TemplateCompileIsDeterministicTests
{
    private static PromptTemplate Sample()
    {
        var result = TemplateLoader.Load("""
            ---
            id: sample
            version: 1
            intent: decision
            audience: owner
            when_to_use: "A sample."
            why: "Because determinism needs a specimen."
            fields:
              - { name: question, type: text, required: true }
              - { name: options, type: list, required: true, min: 2 }
              - { name: evidence, type: mentions, required: false }
            ---
            Question: {{question}}
            Options:
            {{#options}}- {{.}}{{/options}}
            Evidence: {{evidence}}
            """);

        Assert.True(result.Loaded, string.Join("; ", result.Errors.Select(e => e.Message)));
        return result.Template!;
    }

    [Fact]
    public void TwoCompilesOfOneInputAreByteIdentical()
    {
        var template = Sample();

        var forward = new Dictionary<string, IReadOnlyList<string>>(StringComparer.Ordinal)
        {
            ["question"] = ["Ship it?"],
            ["options"] = ["ship", "hold"],
            ["evidence"] = ["docs/plans/conductor-front-door.md"],
        };

        var reversed = new Dictionary<string, IReadOnlyList<string>>(StringComparer.Ordinal)
        {
            ["evidence"] = ["docs/plans/conductor-front-door.md"],
            ["options"] = ["ship", "hold"],
            ["question"] = ["Ship it?"],
        };

        var first = Encoding.UTF8.GetBytes(TemplateCompiler.Compile(template, forward));
        var second = Encoding.UTF8.GetBytes(TemplateCompiler.Compile(template, reversed));
        var third = Encoding.UTF8.GetBytes(TemplateCompiler.Compile(template, forward));

        Assert.Equal(first, second);
        Assert.Equal(first, third);
    }

    [Fact]
    public void EveryBuiltInCompilesToTheSameBytesTwice()
    {
        foreach (var entry in TemplateCatalog.BuiltIn().Entries)
        {
            var template = entry.Template!;
            var values = template.Fields.ToDictionary(
                f => f.Name,
                f => (IReadOnlyList<string>)[$"value for {f.Name}"],
                StringComparer.Ordinal);

            var reversed = new Dictionary<string, IReadOnlyList<string>>(StringComparer.Ordinal);
            foreach (var pair in values.Reverse())
            {
                reversed[pair.Key] = pair.Value;
            }

            Assert.Equal(
                Encoding.UTF8.GetBytes(TemplateCompiler.Compile(template, values)),
                Encoding.UTF8.GetBytes(TemplateCompiler.Compile(template, reversed)));
        }
    }

    [Fact]
    public void ListSectionsRenderInTheOrderTheValuesWereGiven()
    {
        var text = TemplateCompiler.Compile(Sample(), new Dictionary<string, IReadOnlyList<string>>(StringComparer.Ordinal)
        {
            ["question"] = ["Ship it?"],
            ["options"] = ["ship", "hold", "split"],
        });

        Assert.Contains("- ship\n- hold\n- split", text, StringComparison.Ordinal);
    }

    [Fact]
    public void AnUnfilledFieldRendersEmptyRatherThanLeavingItsSlot()
    {
        // Required-ness is the form engine's gate (F4). The compiler's job is to be total: a slot
        // that survived into the output would be a prompt containing template syntax.
        var text = TemplateCompiler.Compile(Sample(), new Dictionary<string, IReadOnlyList<string>>(StringComparer.Ordinal));

        Assert.DoesNotContain("{{", text, StringComparison.Ordinal);
        Assert.DoesNotContain("}}", text, StringComparison.Ordinal);
    }

    [Fact]
    public void TheRulingRequestBuiltInCompilesToB31sShape()
    {
        var template = TemplateCatalog.BuiltIn().Find("ruling-request")!.Template!;

        var text = TemplateCompiler.Compile(template, new Dictionary<string, IReadOnlyList<string>>(StringComparer.Ordinal)
        {
            ["question"] = ["Do we ship FT now?"],
            ["options"] = ["ship now, carry the picker gap", "hold for F4"],
            ["recommendation"] = ["ship now"],
            ["evidence"] = ["docs/notes/addendum-b-ratification.md"],
        });

        Assert.Equal(
            """
            A ruling is requested. Authority: your decision counts as the user's (CT20).
            Question: Do we ship FT now?
            Options and costs:
            - ship now, carry the picker gap
            - hold for F4
            Recommendation and reasoning: ship now
            Evidence: docs/notes/addendum-b-ratification.md
            Record your ruling with rationale; it will be filed as a decision note and audit entry.

            """.ReplaceLineEndings("\n"),
            text);
    }

    [Fact]
    public void CompiledTextUsesLineFeedsWhateverTheSourceFileUsed()
    {
        var crlf = """
            ---
            id: sample
            version: 1
            intent: execute
            audience: conductor
            when_to_use: "A sample."
            why: "Because line endings travel."
            fields:
              - { name: goal, type: text, required: true }
            ---
            goal: {{goal}}
            """.ReplaceLineEndings("\r\n");

        var result = TemplateLoader.Load(crlf);
        Assert.True(result.Loaded, string.Join("; ", result.Errors.Select(e => e.Message)));

        var text = TemplateCompiler.Compile(
            result.Template!,
            new Dictionary<string, IReadOnlyList<string>>(StringComparer.Ordinal) { ["goal"] = ["land FT"] });

        Assert.DoesNotContain('\r', text);
        Assert.Equal("goal: land FT\n", text);
    }
}
