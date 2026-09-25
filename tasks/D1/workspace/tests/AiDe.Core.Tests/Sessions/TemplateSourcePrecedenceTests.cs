using System.Collections.Generic;
using System.IO;
using System.Linq;
using AiDe.Core.Sessions;

namespace AiDe.Core.Tests.Sessions;

/// <summary>
/// FT clause 4 — Phase 1 ships built-in + workspace only, the full precedence order is fixed in the
/// contract now, an override is badged in the model, and sources are an ordered descriptor list that
/// pack and personal can join without editing the loader.
/// </summary>
public sealed class TemplateSourcePrecedenceTests
{
    private const string Sample = """
        ---
        id: goal-block
        version: 1
        intent: execute
        audience: conductor
        when_to_use: "The workspace copy."
        why: "Because a workspace may disagree with the shipped catalog."
        fields:
          - { name: goal, type: text, required: true }
        ---
        goal: {{goal}}
        """;

    [Fact]
    public void ThePrecedenceOrderIsFixedInTheContract()
    {
        // fixture-derivation: ok — this IS the contract's own order, pinned so that registering pack
        // and personal later is data rather than a renegotiation (Ruling 26 cut i).
        Assert.Equal(
            ["personal", "workspace", "pack", "built-in"],
            TemplateSources.PrecedenceOrder);

        Assert.True(TemplateSources.RankOf(TemplateSources.Personal) < TemplateSources.RankOf(TemplateSources.Workspace));
        Assert.True(TemplateSources.RankOf(TemplateSources.Workspace) < TemplateSources.RankOf(TemplateSources.Pack));
        Assert.True(TemplateSources.RankOf(TemplateSources.Pack) < TemplateSources.RankOf(TemplateSources.BuiltIn));
    }

    [Fact]
    public void PhaseOneRegistersBuiltInAndWorkspaceOnly()
    {
        var sources = TemplateSources.Phase1("C:/workspace");

        Assert.Equal([TemplateSources.Workspace, TemplateSources.BuiltIn], sources.Select(s => s.SourceId));
    }

    [Fact]
    public void AWorkspaceTemplateShadowsABuiltInOfTheSameId()
    {
        var catalog = TemplateCatalog.Load([
            new FakeTemplateSource(TemplateSources.Workspace, ("goal-block.template.md", Sample)),
            new BuiltInTemplateSource(),
        ]);

        var entry = catalog.Find("goal-block");

        Assert.NotNull(entry);
        Assert.Equal(TemplateSources.Workspace, entry!.SourceId);
        Assert.Equal("The workspace copy.", entry.Template!.WhenToUse);
    }

    [Fact]
    public void AnOverrideIsBadgedInTheModel()
    {
        var catalog = TemplateCatalog.Load([
            new FakeTemplateSource(TemplateSources.Workspace, ("goal-block.template.md", Sample)),
            new BuiltInTemplateSource(),
        ]);

        var entry = catalog.Find("goal-block")!;

        Assert.True(entry.IsOverride);
        Assert.Equal([TemplateSources.BuiltIn], entry.ShadowedSourceIds);
    }

    [Fact]
    public void ATemplateNoOneOverridesIsNotBadged()
    {
        var entry = TemplateCatalog.BuiltIn().Find("goal-block")!;

        Assert.False(entry.IsOverride);
        Assert.Empty(entry.ShadowedSourceIds);
    }

    [Fact]
    public void RegisteringPackAndPersonalIsDataNotALoaderChange()
    {
        // The loader is handed descriptors and sorts them by the fixed table. Nothing here calls a
        // new API: pack and personal join by being constructed, which is the whole point of the
        // order being pinned in Phase 1 (Ruling 32).
        var catalog = TemplateCatalog.Load([
            new BuiltInTemplateSource(),
            new FakeTemplateSource(TemplateSources.Pack, ("goal-block.template.md", Sample.Replace("The workspace copy.", "The pack copy.", StringComparison.Ordinal))),
            new FakeTemplateSource(TemplateSources.Personal, ("goal-block.template.md", Sample.Replace("The workspace copy.", "The personal copy.", StringComparison.Ordinal))),
            new FakeTemplateSource(TemplateSources.Workspace, ("goal-block.template.md", Sample)),
        ]);

        var entry = catalog.Find("goal-block")!;

        Assert.Equal(TemplateSources.Personal, entry.SourceId);
        Assert.Equal("The personal copy.", entry.Template!.WhenToUse);
        Assert.Equal(
            [TemplateSources.Workspace, TemplateSources.Pack, TemplateSources.BuiltIn],
            entry.ShadowedSourceIds);
    }

    [Fact]
    public void SourcesAreConsultedInPrecedenceOrderWhateverOrderTheyWereRegisteredIn()
    {
        var declared = TemplateCatalog.Load([
            new BuiltInTemplateSource(),
            new FakeTemplateSource(TemplateSources.Workspace, ("goal-block.template.md", Sample)),
        ]);

        Assert.Equal(TemplateSources.Workspace, declared.Find("goal-block")!.SourceId);
    }

    [Fact]
    public void AnOverridingTemplateThatFailsLoadStillWinsAndCarriesItsError()
    {
        // Falling back to the built-in would hide a broken workspace file behind a catalog that
        // looks healthy — the silent drop of clause 2, wearing a different hat.
        var broken = Sample.Replace("when_to_use: \"The workspace copy.\"\n", string.Empty, StringComparison.Ordinal);

        var catalog = TemplateCatalog.Load([
            new FakeTemplateSource(TemplateSources.Workspace, ("goal-block.template.md", broken)),
            new BuiltInTemplateSource(),
        ]);

        var entry = catalog.Find("goal-block")!;

        Assert.Equal(TemplateSources.Workspace, entry.SourceId);
        Assert.False(entry.IsEnabled);
        Assert.True(entry.IsOverride);
        Assert.Contains(entry.Errors, e => e.Code == TemplateErrorCodes.MissingWhenToUse);
    }

    [Fact]
    public void TheWorkspaceSourceReadsTheAideTemplatesSubtree()
    {
        var root = Path.Combine(Path.GetTempPath(), "aide-templates-" + Guid.NewGuid().ToString("N"));
        try
        {
            var dir = Path.Combine(root, ".aide", "templates");
            Directory.CreateDirectory(dir);
            File.WriteAllText(Path.Combine(dir, "goal-block.template.md"), Sample);

            var catalog = TemplateCatalog.Load([new WorkspaceTemplateSource(root), new BuiltInTemplateSource()]);

            Assert.Equal("The workspace copy.", catalog.Find("goal-block")!.Template!.WhenToUse);
        }
        finally
        {
            if (Directory.Exists(root))
            {
                Directory.Delete(root, recursive: true);
            }
        }
    }

    [Fact]
    public void AWorkspaceWithNoTemplatesDirectoryIsEmptyRatherThanAFailure()
    {
        var root = Path.Combine(Path.GetTempPath(), "aide-templates-" + Guid.NewGuid().ToString("N"));

        Assert.Empty(new WorkspaceTemplateSource(root).Read());
    }
}
