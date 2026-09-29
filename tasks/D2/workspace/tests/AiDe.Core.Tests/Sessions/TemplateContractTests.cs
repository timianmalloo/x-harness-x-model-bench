using System.IO;
using System.Linq;
using AiDe.Core.Sessions;

namespace AiDe.Core.Tests.Sessions;

/// <summary>
/// FT clause 1 — <c>template-schema/1</c> is a pinned contract from birth.
/// </summary>
/// <remarks>
/// The clause fails if an unknown frontmatter field is REJECTED rather than preserved, so that is
/// asserted on a value the schema has never heard of, in both a scalar and a non-scalar shape.
/// </remarks>
public sealed class TemplateContractTests
{
    private const string Minimal = """
        ---
        id: sample
        version: 1
        intent: execute
        audience: conductor
        when_to_use: "A sample."
        why: "Because a schema needs a specimen."
        fields:
          - { name: goal, type: text, required: true }
        ---
        goal: {{goal}}
        """;

    [Fact]
    public void TheSchemaVersionIsPinned()
        => Assert.Equal("template-schema/1", TemplateContract.SchemaVersion);

    [Fact]
    public void AnUnknownFrontmatterFieldIsPreservedNotRejected()
    {
        var text = Minimal.Replace(
            "why: \"Because a schema needs a specimen.\"",
            "why: \"Because a schema needs a specimen.\"\nexperimental_flavour: pistachio",
            StringComparison.Ordinal);

        var result = TemplateLoader.Load(text);

        Assert.True(result.Loaded, string.Join("; ", result.Errors.Select(e => e.Message)));
        Assert.Equal("pistachio", result.Template!.UnknownFrontmatter["experimental_flavour"]);
    }

    [Fact]
    public void AnUnknownFrontmatterFieldOfNonScalarShapeIsAlsoPreserved()
    {
        var text = Minimal.Replace(
            "fields:",
            "future_matrix: { rows: 2, cols: 3 }\nfields:",
            StringComparison.Ordinal);

        var result = TemplateLoader.Load(text);

        Assert.True(result.Loaded, string.Join("; ", result.Errors.Select(e => e.Message)));
        var preserved = result.Template!.UnknownFrontmatter["future_matrix"];
        Assert.Contains("rows", preserved, StringComparison.Ordinal);
        Assert.Contains("cols", preserved, StringComparison.Ordinal);
    }

    [Fact]
    public void MinAndTierDefaultAreSchemaOneConstraintsNotPreservedUnknowns()
    {
        var text = Minimal
            .Replace("audience: conductor", "audience: conductor\ntier_default: T0", StringComparison.Ordinal)
            .Replace(
                "  - { name: goal, type: text, required: true }",
                "  - { name: goal, type: text, required: true }\n  - { name: options, type: list, required: true, min: 2 }",
                StringComparison.Ordinal)
            .Replace("goal: {{goal}}", "goal: {{goal}}\n{{#options}}- {{.}}{{/options}}", StringComparison.Ordinal);

        var result = TemplateLoader.Load(text);

        Assert.True(result.Loaded, string.Join("; ", result.Errors.Select(e => e.Message)));
        Assert.Equal("T0", result.Template!.TierDefault);
        Assert.Equal(2, result.Template.Fields.Single(f => f.Name == "options").Min);
        Assert.DoesNotContain("tier_default", result.Template.UnknownFrontmatter.Keys);
        Assert.DoesNotContain("min", result.Template.UnknownFrontmatter.Keys);
    }

    [Fact]
    public void TheRegistryDeclaresTheThreePinnedContractsAndWhereTheyLive()
    {
        var registry = RepoFiles.SourceFile("docs", "architecture", "pinned-contracts.md");

        Assert.Contains("template-schema/1", registry, StringComparison.Ordinal);
        Assert.Contains("weave/1", registry, StringComparison.Ordinal);
        Assert.Contains("loomkeeper/1", registry, StringComparison.Ordinal);
        Assert.Contains("docs/design/watcher-weave-score.md", registry, StringComparison.Ordinal);
        Assert.Contains("docs/design/watcher-coordination-contract.md", registry, StringComparison.Ordinal);
    }

    [Fact]
    public void TheRegistryAnswersTheMinAndTierDefaultQuestionWithoutAmbiguity()
    {
        var registry = RepoFiles.SourceFile("docs", "architecture", "pinned-contracts.md");

        Assert.Contains("`min`", registry, StringComparison.Ordinal);
        Assert.Contains("`tier_default`", registry, StringComparison.Ordinal);
        Assert.Contains("schema-1 constraint", registry, StringComparison.Ordinal);
    }

    [Fact]
    public void TheRegistryDoesNotMoveTheContractsThatAlreadyHaveHomes()
    {
        // Ruling 29: the registry LINKS to weave/1 and loomkeeper/1 where they already live. A
        // registry that copied their definitions would be a second place to change.
        Assert.True(File.Exists(Path.Combine(RepoFiles.Root(), "docs", "design", "watcher-weave-score.md")));
        Assert.True(File.Exists(Path.Combine(RepoFiles.Root(), "docs", "design", "watcher-coordination-contract.md")));
    }
}
