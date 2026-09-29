using AiDe.Core;
using AiDe.Core.Extraction;
using AiDe.Core.Facts;
using AiDe.Core.Projections;

namespace AiDe.Core.Tests;

/// <summary>
/// A caller can ask for the graph without an edge kind, and gets a bigger picture for it.
/// </summary>
/// <remarks>
/// <para><b>Edges are what fills the frame, not nodes.</b> MEASURED on TheTerrace: the canvas default
/// spends <b>702,425 of 852,680 bytes on edges</b> — 82% — and two predicates are 74% of them
/// (`depends_on` 2,155, `calls` 1,272). Every extractor added since has made this worse, and the
/// payload budget is now the binding constraint on the whole product rather than a property of any
/// one reader.</para>
///
/// <para><b>What it buys, measured:</b> asking for 5,000 nodes today returns 2,243 with 749 omitted
/// and 68,857 bytes of headroom. The same request without `calls` and `depends_on` returns
/// <b>2,992 — the entire workspace, nothing omitted</b> — in 602,364 bytes.</para>
/// </remarks>
public sealed class GraphEdgeKindFilterTests : IDisposable
{
    private readonly string _dir = Path.Combine(
        Path.GetTempPath(), "aide-edgefilter", Guid.NewGuid().ToString("N"));

    public GraphEdgeKindFilterTests() => Directory.CreateDirectory(_dir);

    public void Dispose()
    {
        try { Directory.Delete(_dir, recursive: true); } catch (IOException) { }
    }

    /// <summary>Types that both depend on and call each other, so the two kinds can be told apart.</summary>
    private WorkspaceCore Filled(int types)
    {
        var core = WorkspaceCore.Open("ws", _dir, Path.Combine(_dir, "data"), new FixtureExtractor());
        var provenance = new Provenance("src/x.cs", "1:1", "test", "1", DateTimeOffset.UtcNow);
        var assertions = new List<EvidenceAssertion>();

        void Fact(string subject, string predicate, string obj) =>
            assertions.Add(new EvidenceAssertion(
                "csharp:shop", "rev-1", subject, predicate, obj,
                EvidenceOrigin.Static, VerificationStatus.Verified, provenance));

        for (var i = 0; i < types; i++)
        {
            Fact($"Shop.Type{i:D4}", "has_type", "class");
            Fact($"Shop.Type{i:D4}", "declared_in", "csharp:shop");
        }

        // Every type calls and depends on the next one, so both kinds cover the same node pairs and
        // removing one cannot be mistaken for removing the other.
        for (var i = 0; i < types - 1; i++)
        {
            Fact($"Shop.Type{i:D4}", "calls", $"Shop.Type{i + 1:D4}");
            Fact($"Shop.Type{i:D4}", "depends_on", $"Shop.Type{i + 1:D4}");
        }

        // One relationship of a third kind, so "excluded everything" is distinguishable from
        // "excluded the two named".
        Fact("Shop.Type0000", "implements", "Shop.Type0001");

        using var writer = core.Store.BeginWrite();
        writer.DesireScopeGeneration("csharp:shop", 1, "rev-1");
        writer.CommitSnapshot("csharp:shop", 1, "rev-1", assertions, complete: true);
        writer.Commit();

        return core;
    }

    [Fact]
    public void ExcludingAKindRemovesThoseEdgesAndNoOthers()
    {
        using var core = Filled(types: 40);

        var all = core.Projections.Graph(new GraphQuery(500));
        var without = core.Projections.Graph(new GraphQuery(500, ExcludeEdges: ["calls"]));

        Assert.Contains(all.Edges, e => e.Predicate == "calls");
        Assert.DoesNotContain(without.Edges, e => e.Predicate == "calls");

        // Everything else survives untouched — an exclusion that quietly took a neighbour with it
        // would be a filter nobody could reason about.
        Assert.Equal(
            all.Edges.Count(e => e.Predicate == "depends_on"),
            without.Edges.Count(e => e.Predicate == "depends_on"));

        Assert.Equal(
            all.Edges.Count(e => e.Predicate == "implements"),
            without.Edges.Count(e => e.Predicate == "implements"));
    }

    [Fact]
    public void ATypeDeclaredHereSurvivesLosingTheOnlyEdgeKindThatTouchedIt()
    {
        // The trap in the implementation: skipping an assertion also stops it MENTIONING its ends.
        // A node this workspace declares must still be drawn — its own `has_type` mentions it — or
        // excluding an edge kind would silently delete types from the picture.
        using var core = Filled(types: 40);

        var without = core.Projections.Graph(
            new GraphQuery(500, ExcludeEdges: ["calls", "depends_on", "implements"]));

        Assert.Equal(40, without.Nodes.Count);
        Assert.Empty(without.Edges);
    }

    [Fact]
    public void ExclusionHappensBeforeTheCapSoMoreNodesFit()
    {
        // The whole point. A filter applied after the cap returns the wrong slice trimmed to the
        // right shape (DC-035); applied before, the bytes an excluded edge would have cost are spent
        // on nodes instead.
        using var core = Filled(types: 4_000);

        var all = core.Projections.Graph(new GraphQuery(GraphProjection.DefaultMaxNodes));
        var without = core.Projections.Graph(
            new GraphQuery(GraphProjection.DefaultMaxNodes, ExcludeEdges: ["calls", "depends_on"]));

        Assert.True(without.Nodes.Count > all.Nodes.Count,
            $"excluding two edge kinds returned {without.Nodes.Count} nodes and keeping them "
            + $"returned {all.Nodes.Count} — the exclusion bought nothing");

        Assert.True(without.Omitted < all.Omitted);
    }

    [Fact]
    public void ExcludingNothingIsExactlyTodaysGraph()
    {
        // The default must not move. Every existing caller passes no exclusion.
        using var core = Filled(types: 40);

        var implicitAll = core.Projections.Graph(new GraphQuery(500));
        var explicitNone = core.Projections.Graph(new GraphQuery(500, ExcludeEdges: []));

        Assert.Equal(implicitAll.Nodes.Count, explicitNone.Nodes.Count);
        Assert.Equal(implicitAll.Edges.Count, explicitNone.Edges.Count);
    }

    [Fact]
    public void AnExcludedNameThatNobodyEmitsChangesNothing()
    {
        // Excluding is the safe direction precisely because of this: a stale or misspelled name is
        // inert. An INCLUDE list would have made the same mistake silently hide everything else —
        // which is why this takes exclusions and not selections.
        using var core = Filled(types: 40);

        var all = core.Projections.Graph(new GraphQuery(500));
        var nonsense = core.Projections.Graph(new GraphQuery(500, ExcludeEdges: ["no_such_predicate"]));

        Assert.Equal(all.Edges.Count, nonsense.Edges.Count);
        Assert.Equal(all.Nodes.Count, nonsense.Nodes.Count);
    }

    [Fact]
    public void AnAttributeCannotBeExcludedIntoDisappearing()
    {
        // Attributes are not edges, so naming one is inert rather than destructive. `has_type` is
        // what makes a node DECLARED — if excluding it dropped nodes, a caller could erase the graph
        // with a plausible-looking argument.
        using var core = Filled(types: 40);

        var without = core.Projections.Graph(new GraphQuery(500, ExcludeEdges: ["has_type"]));

        Assert.Equal(40, without.Nodes.Count);
    }
}
