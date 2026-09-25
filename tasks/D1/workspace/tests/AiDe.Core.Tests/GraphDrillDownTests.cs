using AiDe.Core.Facts;
using AiDe.Core.Projections;

namespace AiDe.Core.Tests;

/// <summary>
/// Clicking a group returns exactly the nodes that group said it stood for.
/// </summary>
/// <remarks>
/// <para><b>This is the property that makes the overview trustworthy.</b> A cluster drawn as "117"
/// is a claim, and the only way to check it is to open it. If drilling in returns 114, the overview
/// was not a summary — it was a different answer at a different grain, and a user who noticed would
/// be right to stop believing both. The round trip is asserted here rather than assumed because the
/// two paths compute group membership in different places.</para>
///
/// <para>They compute it from ONE definition — <see cref="GraphOverview.GroupFor"/> — which is why
/// the round trip holds. Two definitions of "which group is this in" is DC-022's shape, and the
/// divergence would look like a rendering bug rather than a projection one.</para>
/// </remarks>
public sealed class GraphDrillDownTests
{
    private static EvidenceAssertion Say(string subject, string predicate, string obj) =>
        new("scope", "rev-1", subject, predicate, obj, EvidenceOrigin.Static, VerificationStatus.Verified,
            new Provenance("test", null, "test", "1", DateTimeOffset.UnixEpoch));

    private static readonly EvidenceAssertion[] Workspace =
    [
        Say("Shop.Orders.Order", "has_type", "class"),
        Say("Shop.Orders.Line", "has_type", "class"),
        Say("Shop.Orders.Basket", "has_type", "class"),
        Say("Shop.Billing.Invoice", "has_type", "class"),
        Say("Shop.Billing.Receipt", "has_type", "class"),
        Say("Web.Pages.Checkout", "has_type", "class"),
        Say("Shop.Orders.Order", "depends_on", "Shop.Billing.Invoice"),
        Say("Shop.Orders.Line", "depends_on", "Shop.Orders.Order"),
        Say("Web.Pages.Checkout", "depends_on", "Shop.Orders.Basket"),
    ];

    [Fact]
    public void EveryGroupsCountIsExactlyWhatDrillingIntoItReturns()
    {
        // THE ROUND TRIP. Asserted for every group, not a sampled one, because the interesting
        // failure is the group whose naming rule differs — and that is never the group a test author
        // would pick by hand.
        var projection = new GraphProjection(Workspace, "rev-1");
        var overview = GraphOverview.Summarise(projection.Compute(), new OverviewQuery(Depth: 2));

        Assert.NotEmpty(overview.Clusters);

        foreach (var cluster in overview.Clusters)
        {
            var inside = projection.Compute(new GraphQuery(GroupId: cluster.Id));

            Assert.Equal(cluster.NodeCount, inside.Nodes.Count);
        }
    }

    [Fact]
    public void DrillingInReturnsTheNodesThemselves()
    {
        var inside = new GraphProjection(Workspace, "rev-1")
            .Compute(new GraphQuery(GroupId: "Shop.Orders"));

        Assert.Equal(3, inside.Nodes.Count);
        Assert.All(inside.Nodes, n => Assert.StartsWith("Shop.Orders.", n.Id, StringComparison.Ordinal));
    }

    [Fact]
    public void AnEdgeLeavingTheGroupIsNotDrawnIntoNothing()
    {
        // Shop.Orders.Order depends on Shop.Billing.Invoice, which is outside the group. Drawing that
        // edge would put a line into a node the view does not contain — the half-edge problem the
        // whole-graph cap already had to solve.
        var inside = new GraphProjection(Workspace, "rev-1")
            .Compute(new GraphQuery(GroupId: "Shop.Orders"));

        Assert.All(inside.Edges, e =>
        {
            Assert.Contains(inside.Nodes, n => n.Id == e.From);
            Assert.Contains(inside.Nodes, n => n.Id == e.To);
        });

        // The one edge wholly inside the group survives.
        var edge = Assert.Single(inside.Edges);
        Assert.Equal("Shop.Orders.Line", edge.From);
        Assert.Equal("Shop.Orders.Order", edge.To);
    }

    [Fact]
    public void TheGroupsInternalEdgeCountMatchesWhatDrillingInDraws()
    {
        // The overview promises "N edges wholly inside"; opening the group must show N.
        var projection = new GraphProjection(Workspace, "rev-1");
        var overview = GraphOverview.Summarise(projection.Compute(), new OverviewQuery(Depth: 2));

        foreach (var cluster in overview.Clusters)
        {
            var inside = projection.Compute(new GraphQuery(GroupId: cluster.Id));

            Assert.Equal(cluster.InternalEdges, inside.Edges.Count);
        }
    }

    [Fact]
    public void AGroupThatDoesNotExistIsEmptyRatherThanEverything()
    {
        // The dangerous failure mode: a filter that silently does not apply returns the whole graph,
        // which looks like a working drill-down into a very large group.
        var inside = new GraphProjection(Workspace, "rev-1")
            .Compute(new GraphQuery(GroupId: "Nothing.Here"));

        Assert.Empty(inside.Nodes);
    }

    [Fact]
    public void TheDepthComesFromTheGroupIdSoACallerCannotMismatchIt()
    {
        // A separate depth parameter would let a caller ask for Shop.Orders at depth 3 and receive
        // nothing, indistinguishable from an empty group.
        var projection = new GraphProjection(Workspace, "rev-1");

        Assert.Equal(3, projection.Compute(new GraphQuery(GroupId: "Shop.Orders")).Nodes.Count);
        Assert.Equal(5, projection.Compute(new GraphQuery(GroupId: "Shop")).Nodes.Count);
    }

    [Fact]
    public void DrillDownComposesWithTheOtherFilters()
    {
        var assertions = new List<EvidenceAssertion>(Workspace)
        {
            Say("Shop.Orders.IRepo", "has_type", "interface"),
        };

        var inside = new GraphProjection(assertions, "rev-1")
            .Compute(new GraphQuery(GroupId: "Shop.Orders", Kinds: ["interface"]));

        var node = Assert.Single(inside.Nodes);
        Assert.Equal("Shop.Orders.IRepo", node.Id);
    }
}
