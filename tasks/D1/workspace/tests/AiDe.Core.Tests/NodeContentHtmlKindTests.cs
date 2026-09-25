using AiDe.Core.Projections;

namespace AiDe.Core.Tests;

/// <summary>
/// <b>Ruling 93 — <c>Html</c> is a render kind the authority names.</b> The Explorer reader
/// renders an HTML node in a sandbox and everything else by its kind, so the one producer of the
/// kind (<c>ProjectionService.KindOf</c>, DM7: derive once, never twice) must say <c>Html</c> for
/// <c>.html</c> and <c>.htm</c> — a client that inferred it from the language tag would be a
/// second definition of one quantity.
/// </summary>
public sealed class NodeContentHtmlKindTests
{
    [Theory]
    [InlineData("docs/index.html")]
    [InlineData("docs/INDEX.HTML")]
    [InlineData("site/page.htm")]
    public void AnHtmlArtifactIsTheHtmlKind_WithTheHtmlLanguageTag(string path)
    {
        Assert.Equal(NodeContentKind.Html, ProjectionService.KindOf(path));
        Assert.Equal("html", ProjectionService.LanguageOf(path));
    }

    [Theory]
    [InlineData("src/Page.razor", NodeContentKind.Code, "html")]
    [InlineData("src/Order.cs", NodeContentKind.Code, "csharp")]
    [InlineData("docs/adr-1.md", NodeContentKind.Text, "markdown")]
    [InlineData("docs/notes.txt", NodeContentKind.Text, null)]
    [InlineData("assets/logo.png", NodeContentKind.None, null)]
    public void EveryOtherKindIsUnchanged(string path, NodeContentKind kind, string? language)
    {
        Assert.Equal(kind, ProjectionService.KindOf(path));
        Assert.Equal(language, ProjectionService.LanguageOf(path));
    }
}
