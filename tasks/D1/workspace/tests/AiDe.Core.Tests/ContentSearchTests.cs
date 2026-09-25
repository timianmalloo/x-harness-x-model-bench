using AiDe.Core;
using AiDe.Core.Extraction;
using AiDe.Core.Projections;

namespace AiDe.Core.Tests;

/// <summary>
/// Searching the text of the workspace's own files, from the side of the boundary that can confine it.
/// </summary>
/// <remarks>
/// <para><b>Why Core owns this.</b> Design asked for content/keyword search (§4i) and said a corpus
/// file search is Core's to expose. It is: the App must not read workspace files, because two
/// authorities on what a file contains disagree the first time one resolves a path differently
/// (DC-022), and file access belongs where it can be confined to the workspace. Same rule that put
/// <c>NodeContentAsync</c> in Core, applied to the corpus instead of to one node.</para>
///
/// <para><b>Why it searches the STORE's files rather than the tree.</b> Walking the directory tree
/// would open <c>node_modules</c>, <c>bin</c> and every generated bundle the extractors already
/// decided to skip — and would return hits in files the graph cannot navigate to, which is a result
/// nobody can act on. Every hit names the node that owns the file.</para>
///
/// <para>These index a real workspace rather than hand-writing assertions, for the same reason
/// <c>NodeContentTests</c> does: the thing under test is a path resolved from a scope's recorded
/// location, and a fixture that fabricates that location would prove the resolver against a shape
/// no extractor produces.</para>
/// </remarks>
public sealed class ContentSearchTests : IDisposable
{
    private readonly string _root = Path.Combine(
        Path.GetTempPath(), "aide-content-search", Guid.NewGuid().ToString("N"));

    public ContentSearchTests()
    {
        Directory.CreateDirectory(Path.Combine(_root, "src"));
    }

    public void Dispose()
    {
        try { Directory.Delete(_root, recursive: true); } catch (IOException) { }
    }

    private async Task<WorkspaceCore> IndexedAsync(string orderBody = "public int Id { get; set; }")
    {
        File.WriteAllText(Path.Combine(_root, "src", "Shop.csproj"), """
            <Project Sdk="Microsoft.NET.Sdk">
              <PropertyGroup><TargetFramework>net10.0</TargetFramework></PropertyGroup>
            </Project>
            """);

        File.WriteAllText(Path.Combine(_root, "src", "Order.cs"), $$"""
            namespace Shop;

            public class Order
            {
                {{orderBody}}
            }
            """);

        var core = WorkspaceCore.Open(
            "ws", _root, Path.Combine(_root, ".data"), WorkspaceExtractors.Default());

        await core.IndexCSharpAsync("rev-1");
        return core;
    }

    [Fact]
    public async Task AMatchingLineComesBackWithItsFileAndLineNumber()
    {
        using var core = await IndexedAsync("public int Id { get; set; } // the marker is here");

        var match = Assert.Single(core.Projections.SearchContent("marker", 50).Matches);

        Assert.Contains("marker", match.Text, StringComparison.Ordinal);
        Assert.Contains("Order.cs", match.RelativePath, StringComparison.Ordinal);
        Assert.True(match.Line > 0, "a hit with no line number cannot be navigated to");
    }

    [Fact]
    public async Task AHitNamesTheNodeThatOwnsTheFile()
    {
        // A bare path the client would have to resolve itself is not a result it can navigate to,
        // and resolving it client-side is the second file authority DC-022 forbids.
        using var core = await IndexedAsync("public int Id { get; set; } // the marker is here");

        var match = Assert.Single(core.Projections.SearchContent("marker", 50).Matches);

        Assert.Contains("Order", match.NodeId, StringComparison.Ordinal);
    }

    [Fact]
    public async Task TheSearchIsCaseInsensitive()
    {
        // A person searching for a symbol does not know how it was capitalised in prose.
        using var core = await IndexedAsync("public int Id { get; set; } // The MARKER is here");

        Assert.NotEmpty(core.Projections.SearchContent("marker", 50).Matches);
    }

    [Fact]
    public async Task AnEmptyTermFindsNothingRatherThanEverything()
    {
        // The cheapest wrong answer here is the most expensive one to produce: an empty term
        // matches every line of every file in the workspace.
        using var core = await IndexedAsync();

        var result = core.Projections.SearchContent("   ", 50);

        Assert.Empty(result.Matches);
        Assert.Equal(0, result.FilesSearched);
    }

    [Fact]
    public async Task AFileTheStoreDoesNotKnowAboutIsNotSearched()
    {
        // The corpus is what the extractors chose to index. A hit in an unindexed file is a result
        // the graph cannot navigate to, and reading node_modules is how a search box becomes a
        // build step.
        using var core = await IndexedAsync();

        var modules = Path.Combine(_root, "node_modules", "pkg");
        Directory.CreateDirectory(modules);
        File.WriteAllText(Path.Combine(modules, "index.js"), "// the marker is here\n");

        Assert.Empty(core.Projections.SearchContent("marker", 50).Matches);
    }

    [Fact]
    public async Task TheMatchCapIsEnforcedAndSaidOutLoud()
    {
        // A declared limit that cannot fire is the defect it was written to prevent (DC-016).
        var many = string.Join("\n    ", Enumerable.Range(0, 60).Select(i => $"// marker {i}"));
        using var core = await IndexedAsync("public int Id { get; set; }\n    " + many);

        var result = core.Projections.SearchContent("marker", 5);

        Assert.Equal(5, result.Matches.Count);
        Assert.True(result.Truncated, "the cap fired and the result did not say so");
    }

    [Fact]
    public async Task ALongLineIsBoundedRatherThanReturnedWhole()
    {
        // A minified file is one line and megabytes long. Returning it whole would put the payload
        // straight through the frame INV-0003 was about.
        using var core = await IndexedAsync(
            "public int Id { get; set; } // " + new string('x', 50_000) + " marker");

        var match = Assert.Single(core.Projections.SearchContent("marker", 50).Matches);

        Assert.True(match.Text.Length <= 200,
            $"a single matching line carried {match.Text.Length} characters onto the response");
    }

    [Fact]
    public async Task TheResultSaysHowMuchOfTheCorpusItRead()
    {
        // A search that silently skipped half the corpus and said nothing would be a coverage claim
        // nobody could check (DC-025). The counts are how a caller knows what the answer is worth.
        using var core = await IndexedAsync("public int Id { get; set; } // the marker is here");

        var result = core.Projections.SearchContent("marker", 50);

        Assert.True(result.FilesSearched > 0,
            "the search reported reading no files while returning a hit from one");
    }

    [Fact]
    public async Task NothingIsFoundForATermNoFileContains()
    {
        // A widened search that matches too much is worse than one that matches too little: the
        // first is indistinguishable from a broken filter.
        using var core = await IndexedAsync();

        Assert.Empty(core.Projections.SearchContent("nothing-in-this-workspace", 50).Matches);
    }
}
