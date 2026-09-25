using System.IO;
using System.Linq;
using AiDe.Core.Sessions;

namespace AiDe.Core.Tests.Sessions;

/// <summary>
/// FT clause 5 — the frontmatter parser is an installed YAML dependency scoped to the template
/// loader, not a third hand-rolled subset reader, and it does not let the document choose a type.
/// </summary>
/// <remarks>
/// The cases below are the exact constructs B3.1 uses and the two existing subset readers name as
/// their upgrade trigger: a multi-line plain scalar, and flow mappings inside a block sequence.
/// </remarks>
public sealed class TemplateFrontmatterParserTests
{
    [Fact]
    public void AMultiLinePlainScalarIsReadAsOneFoldedValue()
    {
        var result = TemplateLoader.Load("""
            ---
            id: ruling-request
            version: 1
            intent: decision
            audience: owner
            when_to_use: "A judgment call is blocking progress and the options are known."
            why: "Rulings that can be answered in one pass need options, costs, and a
                  recommendation up front; a prose request makes the Owner reconstruct
                  the decision before making it."
            fields:
              - { name: question, type: text, required: true }
            ---
            Question: {{question}}
            """);

        Assert.True(result.Loaded, string.Join("; ", result.Errors.Select(e => e.Message)));
        Assert.Equal(
            "Rulings that can be answered in one pass need options, costs, and a recommendation up "
            + "front; a prose request makes the Owner reconstruct the decision before making it.",
            result.Template!.Why);
    }

    [Fact]
    public void FlowMappingsInsideFieldsAreReadIncludingWrappedOnes()
    {
        var result = TemplateLoader.Load("""
            ---
            id: ruling-request
            version: 1
            intent: decision
            audience: owner
            tier_default: T0
            when_to_use: "A judgment call is blocking progress and the options are known."
            why: "Options first."
            fields:
              - { name: question,        type: text,    required: true,
                  hint: "One decidable question. If two, file two." }
              - { name: options,         type: list,    required: true, min: 2,
                  hint: "Each with cost/consequence. Include do-nothing when honest." }
              - { name: evidence,        type: mentions, required: false }
            ---
            Question: {{question}}
            {{#options}}- {{.}}{{/options}}
            Evidence: {{evidence}}
            """);

        Assert.True(result.Loaded, string.Join("; ", result.Errors.Select(e => e.Message)));

        var fields = result.Template!.Fields;
        Assert.Equal(["question", "options", "evidence"], fields.Select(f => f.Name));
        Assert.Equal(TemplateFieldType.Text, fields[0].Type);
        Assert.Equal("One decidable question. If two, file two.", fields[0].Hint);
        Assert.Equal(TemplateFieldType.List, fields[1].Type);
        Assert.Equal(2, fields[1].Min);
        Assert.Equal(TemplateFieldType.Mentions, fields[2].Type);
        Assert.False(fields[2].Required);
    }

    [Fact]
    public void AQuotedColonAndAnInlineCommentSurvive()
    {
        var result = TemplateLoader.Load("""
            ---
            id: sample            # a trailing comment
            version: 1
            intent: execute
            audience: conductor
            when_to_use: "Ratio: 2:1, and it matters."
            why: "Because a subset reader splits on the first colon."
            fields:
              - { name: goal, type: text, required: true }
            ---
            goal: {{goal}}
            """);

        Assert.True(result.Loaded, string.Join("; ", result.Errors.Select(e => e.Message)));
        Assert.Equal("sample", result.Template!.Id);
        Assert.Equal("Ratio: 2:1, and it matters.", result.Template.WhenToUse);
    }

    [Fact]
    public void AnExplicitYamlTagIsRefusedRatherThanResolved()
    {
        // "Deserialize into the schema type only — no tag-driven type resolution." The refusal is
        // structural: after this scan no node carries a tag, so nothing downstream CAN be driven by
        // one, whatever a future serializer setting does.
        var result = TemplateLoader.Load("""
            ---
            id: sample
            version: 1
            intent: execute
            audience: conductor
            when_to_use: !!str "A sample."
            why: "Because a document must not choose a type."
            fields:
              - { name: goal, type: text, required: true }
            ---
            goal: {{goal}}
            """);

        Assert.False(result.Loaded);
        Assert.Contains(result.Errors, e => e.Code == TemplateErrorCodes.ExplicitYamlTag);
    }

    [Fact]
    public void AnApplicationSpecificTagIsRefusedToo()
    {
        var result = TemplateLoader.Load("""
            ---
            id: sample
            version: 1
            intent: execute
            audience: conductor
            when_to_use: "A sample."
            why: "Because a document must not name a CLR type."
            fields: !AiDe.Core.Sessions.TemplateField
              - { name: goal, type: text, required: true }
            ---
            goal: {{goal}}
            """);

        Assert.False(result.Loaded);
        Assert.Contains(result.Errors, e => e.Code == TemplateErrorCodes.ExplicitYamlTag);
    }

    [Fact]
    public void MalformedYamlIsAnErrorNotAnException()
    {
        var result = TemplateLoader.Load("""
            ---
            id: sample
            fields:
              - { name: goal, type: text
            ---
            goal: {{goal}}
            """);

        Assert.False(result.Loaded);
        Assert.Contains(result.Errors, e => e.Code == TemplateErrorCodes.MalformedFrontmatter);
    }

    [Fact]
    public void AFileWithNoFrontmatterAtAllIsAnError()
    {
        var result = TemplateLoader.Load("just a markdown file\n");

        Assert.False(result.Loaded);
        Assert.Contains(result.Errors, e => e.Code == TemplateErrorCodes.MissingFrontmatter);
    }

    [Fact]
    public void ThereIsExactlyOneFrontmatterEntryPointUnderSessions()
    {
        // A third hand-rolled subset reader is refused (Ruling 35). This is the cheap mechanical
        // version of that refusal: one reader in the slice, and it names the dependency.
        var sessions = Path.Combine(RepoFiles.Root(), "src", "AiDe.Core", "Sessions");
        var readers = Directory
            .GetFiles(sessions, "*Frontmatter*.cs", SearchOption.AllDirectories)
            .Select(Path.GetFileName)
            .ToList();

        var only = Assert.Single(readers);
        Assert.Equal("TemplateFrontmatterReader.cs", only);
        Assert.Contains("YamlDotNet", File.ReadAllText(Path.Combine(sessions, only!)), StringComparison.Ordinal);
    }

    [Fact]
    public void TheDependencyIsScopedToTheTemplateLoader()
    {
        var offenders = Directory
            .GetFiles(Path.Combine(RepoFiles.Root(), "src"), "*.cs", SearchOption.AllDirectories)
            .Where(f => File.ReadAllText(f).Contains("YamlDotNet", StringComparison.Ordinal))
            .Select(Path.GetFileName)
            .ToList();

        Assert.Equal(["TemplateFrontmatterReader.cs"], offenders);
    }
}
