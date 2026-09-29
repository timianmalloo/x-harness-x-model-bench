using AiDe.Core.Presentation.Composer;
using AiDe.Core.Sessions;

namespace AiDe.Core.Tests.Composer;

/// <summary>
/// The picker card shows <c>when_to_use</c> as headline and <c>why</c> as detail, a failed template
/// is a <b>disabled card carrying its error</b> rather than a silent drop, and an override is badged.
/// </summary>
public sealed class TheTemplatePickerShowsWhenToUseAndWhyTests
{
    private sealed class InMemorySource(string sourceId, params (string Origin, string Text)[] documents)
        : ITemplateSource
    {
        public string SourceId => sourceId;

        public IReadOnlyList<TemplateDocument> Read() =>
            [.. documents.Select(d => new TemplateDocument(d.Origin, d.Text))];
    }

    private static string Document(string id, string whenToUse, string why) =>
        $"""
        ---
        id: {id}
        version: 1
        intent: an intent
        audience: an audience
        when_to_use: {whenToUse}
        why: {why}
        fields:
          - name: title
            type: text
            required: true
        ---
        # TITLE_SLOT

        """.Replace("TITLE_SLOT", "{{title}}", StringComparison.Ordinal);

    [Fact]
    public void TheHeadlineIsWhenToUseAndTheDetailIsWhyVerbatim()
    {
        var catalog = TemplateCatalog.Load(
        [
            new InMemorySource(
                TemplateSources.Workspace,
                ("a.md", Document("launch", "Starting a new slice from a ratified spec", "It forces the goal block to be written before any code"))),
        ]);

        var row = Assert.Single(ComposerTemplatePicker.Rows(catalog));

        Assert.Equal("launch", row.Id);
        Assert.Equal("Starting a new slice from a ratified spec", row.Headline);
        Assert.Equal("It forces the goal block to be written before any code", row.Detail);
        Assert.True(row.IsEnabled);
        Assert.False(row.IsOverride);
        Assert.Equal(string.Empty, row.OverrideBadge);
    }

    [Fact]
    public void ATemplateThatFailedLoadIsADisabledCardCarryingItsErrorRatherThanASilentDrop()
    {
        var broken = """
            ---
            id: broken
            version: 1
            intent: an intent
            audience: an audience
            why: it has no when_to_use, which is load-blocking
            ---
            # body

            """;

        var catalog = TemplateCatalog.Load([new InMemorySource(TemplateSources.Workspace, ("b.md", broken))]);
        var row = Assert.Single(ComposerTemplatePicker.Rows(catalog));

        Assert.False(row.IsEnabled);
        Assert.Contains("broken", row.Headline, StringComparison.Ordinal);
        Assert.Contains("did not load", row.Headline, StringComparison.Ordinal);
        Assert.Contains(TemplateErrorCodes.MissingWhenToUse, row.Detail, StringComparison.Ordinal);
    }

    [Fact]
    public void AnOverrideIsVisiblyBadgedAndNamesWhatItShadows()
    {
        var catalog = TemplateCatalog.Load(
        [
            new InMemorySource(TemplateSources.BuiltIn, ("builtin.md", Document("launch", "the built-in headline", "the built-in detail"))),
            new InMemorySource(TemplateSources.Workspace, ("ws.md", Document("launch", "the workspace headline", "the workspace detail"))),
        ]);

        var row = Assert.Single(ComposerTemplatePicker.Rows(catalog));

        Assert.Equal("the workspace headline", row.Headline);
        Assert.True(row.IsOverride);
        Assert.Contains(TemplateSources.BuiltIn, row.OverrideBadge, StringComparison.Ordinal);
    }

    [Fact]
    public void TheTwelveBuiltInsAllRenderACardWithBothLines()
    {
        var rows = ComposerTemplatePicker.Rows(TemplateCatalog.BuiltIn());

        Assert.Equal(12, rows.Count);
        Assert.All(rows, row =>
        {
            Assert.True(row.IsEnabled, $"the built-in '{row.Id}' did not load");
            Assert.False(string.IsNullOrWhiteSpace(row.Headline));
            Assert.False(string.IsNullOrWhiteSpace(row.Detail));
        });
    }

    [Fact]
    public void ChoosingACardRendersItAsAValidatedFormWhoseFieldsCarryTheRuling33Widgets()
    {
        var catalog = TemplateCatalog.BuiltIn();
        var chosen = catalog.Entries.First(e => e.IsEnabled);

        var draft = new ComposerDraft();
        draft.UseTemplate(chosen.Id);

        // Required fields block the send until they are filled, and every declared field maps onto
        // the fixed widget inventory rather than onto an editor per field.
        var required = chosen.Template!.Fields.Where(f => f.Required).ToList();
        var errors = ComposerFormEngine.Validate(draft, chosen.Template);

        Assert.Equal(required.Count, errors.Count);
        Assert.All(chosen.Template.Fields, field =>
            Assert.Contains(
                ComposerFieldWidgets.ForTemplateField(field),
                new[]
                {
                    ComposerFieldWidget.Text, ComposerFieldWidget.List, ComposerFieldWidget.Mentions,
                }));
    }
}
