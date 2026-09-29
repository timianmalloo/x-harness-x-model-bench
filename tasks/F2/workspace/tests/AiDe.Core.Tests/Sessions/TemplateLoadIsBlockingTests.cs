using System.Collections.Generic;
using System.Linq;
using AiDe.Core.Sessions;

namespace AiDe.Core.Tests.Sessions;

/// <summary>
/// FT clause 2 — <c>when_to_use</c> and <c>why</c> are load-blocking, and a template that fails load
/// surfaces as a DISABLED entry carrying its error rather than disappearing.
/// </summary>
/// <remarks>
/// The catalog <i>view</i> that renders a disabled entry is Phase 3 (R22). What has to be true now is
/// that the model carries the error at all — a silent drop cannot be added back by a view later.
/// </remarks>
public sealed class TemplateLoadIsBlockingTests
{
    private const string WithWhenAndWhy = """
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
    public void ATemplateWithNoWhenToUseFailsLoad()
    {
        var result = TemplateLoader.Load(
            WithWhenAndWhy.Replace("when_to_use: \"A sample.\"\n", string.Empty, StringComparison.Ordinal));

        Assert.False(result.Loaded);
        Assert.Contains(result.Errors, e => e.Code == TemplateErrorCodes.MissingWhenToUse);
    }

    [Fact]
    public void ATemplateWithABlankWhenToUseFailsLoad()
    {
        var result = TemplateLoader.Load(
            WithWhenAndWhy.Replace("when_to_use: \"A sample.\"", "when_to_use: \"   \"", StringComparison.Ordinal));

        Assert.False(result.Loaded);
        Assert.Contains(result.Errors, e => e.Code == TemplateErrorCodes.MissingWhenToUse);
    }

    [Fact]
    public void ATemplateWithNoWhyFailsLoad()
    {
        var result = TemplateLoader.Load(
            WithWhenAndWhy.Replace("why: \"Because a schema needs a specimen.\"\n", string.Empty, StringComparison.Ordinal));

        Assert.False(result.Loaded);
        Assert.Contains(result.Errors, e => e.Code == TemplateErrorCodes.MissingWhy);
    }

    [Fact]
    public void AFailedTemplateSurfacesAsADisabledEntryCarryingItsError()
    {
        var broken = WithWhenAndWhy.Replace("when_to_use: \"A sample.\"\n", string.Empty, StringComparison.Ordinal);
        var catalog = TemplateCatalog.Load(
            [new FakeTemplateSource(TemplateSources.Workspace, ("broken.template.md", broken))]);

        var entry = catalog.Find("sample");

        Assert.NotNull(entry);
        Assert.False(entry!.IsEnabled);
        Assert.Null(entry.Template);
        Assert.Contains(entry.Errors, e => e.Code == TemplateErrorCodes.MissingWhenToUse);
        Assert.Equal("broken.template.md", entry.Origin);
    }

    [Fact]
    public void ATemplateWithNoIdSurfacesUnderItsOrigin()
    {
        // With no id there is nothing to key on, so the origin becomes the identity. Dropping it
        // would be exactly the silent disappearance this clause forbids.
        var broken = WithWhenAndWhy.Replace("id: sample\n", string.Empty, StringComparison.Ordinal);
        var catalog = TemplateCatalog.Load(
            [new FakeTemplateSource(TemplateSources.Workspace, ("nameless.template.md", broken))]);

        var entry = Assert.Single(catalog.Entries);
        Assert.False(entry.IsEnabled);
        Assert.Contains(entry.Errors, e => e.Code == TemplateErrorCodes.MissingId);
        Assert.Equal("nameless.template.md", entry.Origin);
    }

    [Fact]
    public void ABodySlotNamingNoFieldFailsLoad()
    {
        var result = TemplateLoader.Load(
            WithWhenAndWhy.Replace("goal: {{goal}}", "goal: {{goal}} and {{ghost}}", StringComparison.Ordinal));

        Assert.False(result.Loaded);
        Assert.Contains(result.Errors, e => e.Code == TemplateErrorCodes.UnresolvedSlot);
    }

    [Fact]
    public void AnUnknownFieldTypeFailsLoad()
    {
        var result = TemplateLoader.Load(
            WithWhenAndWhy.Replace("type: text", "type: hologram", StringComparison.Ordinal));

        Assert.False(result.Loaded);
        Assert.Contains(result.Errors, e => e.Code == TemplateErrorCodes.UnknownFieldType);
    }

    [Fact]
    public void AnIdCollisionWithinOneSourceFailsLoad()
    {
        var catalog = TemplateCatalog.Load([
            new FakeTemplateSource(
                TemplateSources.Workspace,
                ("a.template.md", WithWhenAndWhy),
                ("b.template.md", WithWhenAndWhy))
        ]);

        var entry = Assert.Single(catalog.Entries);
        Assert.False(entry.IsEnabled);
        Assert.Contains(entry.Errors, e => e.Code == TemplateErrorCodes.DuplicateIdInSource);
    }

    [Fact]
    public void EveryBuiltInTemplateLoadsCleanly()
    {
        var catalog = TemplateCatalog.BuiltIn();

        Assert.All(
            catalog.Entries,
            entry => Assert.True(
                entry.IsEnabled,
                $"{entry.Id}: {string.Join("; ", entry.Errors.Select(e => e.Message))}"));
    }
}

/// <summary>A source built from strings, so a catalog case needs no directory on disk.</summary>
internal sealed class FakeTemplateSource(string sourceId, params (string Origin, string Text)[] documents)
    : ITemplateSource
{
    public string SourceId { get; } = sourceId;

    public IReadOnlyList<TemplateDocument> Read()
        => documents.Select(d => new TemplateDocument(d.Origin, d.Text)).ToList();
}
