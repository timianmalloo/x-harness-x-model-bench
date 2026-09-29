using AiDe.Core;
using AiDe.Core.Extraction;
using AiDe.Core.Projections;

namespace AiDe.Core.Tests;

/// <summary>
/// The reader gets the one node's content it asked for — from inside the workspace, bounded, and
/// honest when there is nothing to give.
/// </summary>
/// <remarks>
/// <para>ADR-0018 node-content-reader-contract. The graph carries no content on purpose: paying for 1,500 nodes to serve the one
/// a user selected is what overflowed the frame (INV-0003). So content is a separate, on-demand
/// query — and because it is the only operation on this seam that touches a FILE, the interesting
/// tests are about what it refuses rather than what it returns.</para>
/// </remarks>
public sealed class NodeContentTests : IDisposable
{
    private readonly string _root = Path.Combine(
        Path.GetTempPath(), "aide-content", Guid.NewGuid().ToString("N"));

    public NodeContentTests()
    {
        Directory.CreateDirectory(Path.Combine(_root, "src"));
        Directory.CreateDirectory(Path.Combine(_root, "docs"));
    }

    public void Dispose()
    {
        try { Directory.Delete(_root, recursive: true); } catch (IOException) { }
    }

    private async Task<WorkspaceCore> IndexedAsync()
    {
        File.WriteAllText(Path.Combine(_root, "src", "Shop.csproj"), """
            <Project Sdk="Microsoft.NET.Sdk">
              <PropertyGroup><TargetFramework>net10.0</TargetFramework></PropertyGroup>
            </Project>
            """);

        File.WriteAllText(Path.Combine(_root, "src", "Order.cs"), """
            namespace Shop;

            public class Order
            {
                public int Id { get; set; }
            }
            """);

        File.WriteAllText(Path.Combine(_root, "docs", "adr-1.md"), """
            ---
            id: adr-1
            type: adr
            owner: "@someone"
            ---

            # A decision

            The body of the decision.
            """);

        var core = WorkspaceCore.Open(
            "ws", _root, Path.Combine(_root, ".data"), WorkspaceExtractors.Default());

        await core.IndexCSharpAsync("rev-1");
        return core;
    }

    [Fact]
    public async Task ACodeNodeComesBackAsCodeWithItsLanguage()
    {
        using var core = await IndexedAsync();

        var content = core.Projections.NodeContent("Shop.Order");

        Assert.Equal(NodeContentKind.Code, content.RenderKind);
        Assert.Equal("csharp", content.Language);
        Assert.Contains("public class Order", content.Content, StringComparison.Ordinal);
        Assert.Null(content.Shortfall);
    }

    [Fact]
    public async Task ADocumentComesBackAsText()
    {
        // The scope that knows where documents live is a different one, with a different base path.
        // A resolver that worked only for the scope it was written against would pass on code and
        // fail here — which is the whole reason the location is recorded per scope.
        using var core = await IndexedAsync();

        var content = core.Projections.NodeContent("adr-1");

        Assert.Equal(NodeContentKind.Text, content.RenderKind);
        Assert.Equal("markdown", content.Language);
        Assert.Contains("The body of the decision.", content.Content, StringComparison.Ordinal);
    }

    [Fact]
    public async Task ANodeIdThatIsAPathEscapeGetsNothing()
    {
        // A node id arrives from a client. This one is not a node at all — it is an attempt to make
        // the resolver walk out of the workspace. The answer must be the same "no content" a genuine
        // unknown node gets: telling an untrusted caller WHICH way it failed describes the filesystem
        // to whoever asked.
        using var core = await IndexedAsync();

        var content = core.Projections.NodeContent("../../../../Windows/System32/drivers/etc/hosts");

        Assert.Equal(NodeContentKind.None, content.RenderKind);
        Assert.Empty(content.Content);
    }

    [Fact]
    public async Task AnUnknownNodeSaysSoRatherThanFailing()
    {
        using var core = await IndexedAsync();

        var content = core.Projections.NodeContent("Shop.NoSuchType");

        Assert.Equal(NodeContentKind.None, content.RenderKind);
        Assert.Empty(content.Content);
        Assert.NotNull(content.Shortfall);
    }

    [Fact]
    public async Task AFileTooLargeForTheFrameIsTruncatedAndSaysWhatWasLeft()
    {
        // The bound that keeps this operation from becoming the defect the graph already had: a
        // response sized by repository content, with nothing saying it was cut.
        var big = string.Join("\n", Enumerable.Range(0, 40_000).Select(i => $"// padding line {i}"));

        File.WriteAllText(Path.Combine(_root, "src", "Huge.cs"),
            "namespace Shop;\n\npublic class Huge\n{\n}\n" + big);

        using var core = await IndexedAsync();

        var content = core.Projections.NodeContent("Shop.Huge");

        Assert.Equal(NodeContentKind.Code, content.RenderKind);
        Assert.True(
            System.Text.Encoding.UTF8.GetByteCount(content.Content) <= ProjectionService.MaxContentBytes,
            $"the content is {System.Text.Encoding.UTF8.GetByteCount(content.Content):N0} bytes and the "
            + $"bound is {ProjectionService.MaxContentBytes:N0}");

        Assert.NotNull(content.Shortfall);
        Assert.Contains("open the source", content.Shortfall, StringComparison.Ordinal);
    }

    [Fact]
    public async Task AHeavilyReferencedTypeStillFindsItsOwnSource()
    {
        // DC-035, fourth instance — made while fixing the third. The resolver filtered a CAPPED
        // neighbour list for the fact carrying a path, so a node with more edges than the cap never
        // found its own declaration. MEASURED on the real workspace: the most connected type
        // (`AppDbContext`, 244 edges) reported "no recorded source" while every small type worked —
        // the failure sorted by popularity, which is the worst way for one to sort.
        //
        // The referencing types are named to sort BEFORE the hub, because `AssertionsTouching`
        // orders by subject: on the real workspace the hub was `TheTerrace.Infrastructure.Data.
        // AppDbContext` and its callers were `TheTerrace.Features.*`, so fifty rows of callers filled
        // the window before the hub's own declaration was reached. A fixture whose references sorted
        // after the hub passed against the un-fixed code, which would have made this decorative.
        var references = string.Join(
            Environment.NewLine,
            Enumerable.Range(0, ProjectionService.MaxNeighborsCeiling + 20)
                .Select(i => $"public class Aaa{i:D3} : ZzzHub {{ }}"));

        File.WriteAllText(Path.Combine(_root, "src", "Hub.cs"), """
            namespace Shop;

            public class ZzzHub
            {
                public int Id { get; set; }
            }


            """ + references);

        using var core = await IndexedAsync();

        // The fixture proves it can reproduce before it asserts anything. A hub with fewer touching
        // facts than the cap cannot exercise this at all, and a test that cannot fail is worse than
        // no test (DC-016) — this one silently could not, twice, while being edited to try.
        using (var reader = core.Store.BeginRead())
        {
            var touching = reader.CountAssertionsTouching("Shop.ZzzHub");

            Assert.True(touching > ProjectionService.MaxNeighborsCeiling,
                $"the hub has {touching} touching assertion(s) and the cap is "
                + $"{ProjectionService.MaxNeighborsCeiling} — this fixture cannot reproduce the defect");

            // The window no longer hides the declaration, and that is a SECOND fix rather than this
            // one becoming unnecessary. `AssertionsTouching` used to order alphabetically, so a hub
            // whose callers sorted before it lost its own `has_type`; it now returns identity facts
            // first. Two independent guards hold this up: the dedicated `DeclaringAssertion` query,
            // which does not depend on ordering luck, and the ordering itself.
            //
            // The precondition kept here is the one that still discriminates: the hub genuinely has
            // more touching facts than the cap, so a reader that pages through them can still get
            // this wrong.
            var window = reader.AssertionsTouching("Shop.ZzzHub", ProjectionService.MaxNeighborsCeiling);

            Assert.Equal(ProjectionService.MaxNeighborsCeiling, window.Count);
        }

        var content = core.Projections.NodeContent("Shop.ZzzHub");

        Assert.Equal(NodeContentKind.Code, content.RenderKind);
        Assert.Contains("public class ZzzHub", content.Content, StringComparison.Ordinal);
    }

    [Fact]
    public async Task TheContentQueryIsReachableOverTheSeamTheReaderUses()
    {
        // DC-042: a capability complete, tested, and never routed. The reader talks to
        // IWorkspaceQueries, so that is where this has to answer — not merely on the projection.
        using var core = await IndexedAsync();

        IWorkspaceQueries queries = new LocalWorkspaceQueries(core.Projections);
        var content = await queries.NodeContentAsync("Shop.Order", CancellationToken.None);

        Assert.Equal(NodeContentKind.Code, content.RenderKind);
        Assert.Contains("class Order", content.Content, StringComparison.Ordinal);
    }
}
