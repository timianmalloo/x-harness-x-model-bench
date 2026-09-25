using AiDe.Core.Facts;
using AiDe.Core.Projections;

namespace AiDe.Core.Tests;

/// <summary>
/// The workspace as groups, for a graph too large to draw node by node.
/// </summary>
/// <remarks>
/// <para><b>The half of DC-035 that the bounded default left open.</b> Drawing 1,500 of 2,118
/// declared nodes and saying so is honest and is still a truncation. MEASURED on a real repository,
/// the overview is the shape instead: at depth 3, <c>Features.Fixtures</c> 117, <c>Features.Teams</c>
/// 117, <c>Features.Matches</c> 107, <c>Infrastructure.Data</c> 70 — in <b>55,758 bytes</b> against
/// 533,484 for the node graph.</para>
///
/// <para>These pin the four things a summary can quietly get wrong: losing the count that makes it
/// honest, laundering an inferred edge inside a bundle, hiding the user's code inside a group
/// coloured as a package, and drawing a link that is really a group talking to itself.</para>
/// </remarks>
public sealed class GraphOverviewTests
{
    private static EvidenceAssertion Say(string subject, string predicate, string obj,
        VerificationStatus status = VerificationStatus.Verified) =>
        new("scope", "rev-1", subject, predicate, obj, EvidenceOrigin.Static, status,
            new Provenance("test", null, "test", "1", DateTimeOffset.UnixEpoch));

    private static WorkspaceOverview Summarise(
        IEnumerable<EvidenceAssertion> assertions, OverviewQuery query) =>
        GraphOverview.Summarise(
            new GraphProjection([.. assertions], "rev-1").Compute(), query);

    [Fact]
    public void AGroupCarriesHowManyNodesItStandsFor()
    {
        // A dot standing for 240 types is only honest while the 240 is on it. That is the whole
        // difference between an overview and a smaller lie.
        var overview = Summarise(
        [
            Say("Shop.Orders.Order", "has_type", "class"),
            Say("Shop.Orders.Line", "has_type", "class"),
            Say("Shop.Billing.Invoice", "has_type", "class"),
        ], new OverviewQuery(Depth: 2));

        var orders = Assert.Single(overview.Clusters, c => c.Id == "Shop.Orders");
        Assert.Equal(2, orders.NodeCount);

        Assert.Equal(3, overview.TotalNodes);
    }

    [Fact]
    public void EdgesBetweenGroupsCarryHowManyTheyStandFor()
    {
        var overview = Summarise(
        [
            Say("Shop.Orders.Order", "has_type", "class"),
            Say("Shop.Orders.Line", "has_type", "class"),
            Say("Shop.Billing.Invoice", "has_type", "class"),
            Say("Shop.Orders.Order", "depends_on", "Shop.Billing.Invoice"),
            Say("Shop.Orders.Line", "depends_on", "Shop.Billing.Invoice"),
        ], new OverviewQuery(Depth: 2));

        var edge = Assert.Single(overview.Edges);
        Assert.Equal("Shop.Orders", edge.From);
        Assert.Equal("Shop.Billing", edge.To);
        Assert.Equal(2, edge.Weight);
    }

    [Fact]
    public void ABundleTakesTheStatusOfItsWEAKESTEdge()
    {
        // Drawing a bundle as Verified because most of its members were would launder the guesses
        // into facts — at a grain where the user can no longer see the members.
        var overview = Summarise(
        [
            Say("Shop.Orders.Order", "has_type", "class"),
            Say("Shop.Orders.Line", "has_type", "class"),
            Say("Shop.Billing.Invoice", "has_type", "class"),
            Say("Shop.Orders.Order", "depends_on", "Shop.Billing.Invoice"),
            Say("Shop.Orders.Line", "maps_to", "Shop.Billing.Invoice", VerificationStatus.Inferred),
        ], new OverviewQuery(Depth: 2));

        var edge = Assert.Single(overview.Edges);
        Assert.Equal(VerificationStatus.Inferred, edge.Status);
    }

    [Fact]
    public void AnEdgeInsideAGroupIsCountedRatherThanDrawn()
    {
        // A self-loop on every group is noise. But "240 types that only talk to each other" and
        // "240 types wired to everything" are different pictures, so it is not simply discarded.
        var overview = Summarise(
        [
            Say("Shop.Orders.Order", "has_type", "class"),
            Say("Shop.Orders.Line", "has_type", "class"),
            Say("Shop.Orders.Order", "depends_on", "Shop.Orders.Line"),
        ], new OverviewQuery(Depth: 2));

        var orders = Assert.Single(overview.Clusters);
        Assert.Equal(1, orders.InternalEdges);
        Assert.Empty(overview.Edges);
    }

    [Fact]
    public void AGroupIsExternalOnlyWhenEVERYNodeInItIs()
    {
        // One declared type makes the group part of this workspace. Colouring it as a package would
        // hide the user's own code inside something they think they can ignore.
        var overview = Summarise(
        [
            Say("Shop.Orders.Order", "has_type", "class"),
            Say("Shop.Orders.Order", "depends_on", "Shop.Orders.NotDeclared"),
            Say("Vendor.Thing.A", "has_type", "class"),
            Say("Vendor.Thing.A", "depends_on", "Nuget.Package.Type"),
        ], new OverviewQuery(Depth: 2));

        Assert.False(Assert.Single(overview.Clusters, c => c.Id == "Shop.Orders").IsExternal);
        Assert.True(Assert.Single(overview.Clusters, c => c.Id == "Nuget.Package").IsExternal);
    }

    [Fact]
    public void DepthIsTheZoomControl()
    {
        var assertions = new[]
        {
            Say("Shop.Orders.Order", "has_type", "class"),
            Say("Shop.Billing.Invoice", "has_type", "class"),
        };

        Assert.Single(Summarise(assertions, new OverviewQuery(Depth: 1)).Clusters);
        Assert.Equal(2, Summarise(assertions, new OverviewQuery(Depth: 2)).Clusters.Count);
    }

    [Fact]
    public void WhenTheCapAppliesTheUsersOwnCodeIsKeptAndTheRestIsCounted()
    {
        var assertions = new List<EvidenceAssertion> { Say("Shop.Mine.Type", "has_type", "class") };

        for (var i = 0; i < 40; i++)
        {
            assertions.Add(Say("Shop.Mine.Type", "depends_on", $"Vendor{i}.Package.Thing"));
        }

        var overview = Summarise(assertions, new OverviewQuery(Depth: 2, MaxClusters: 3));

        Assert.Contains(overview.Clusters, c => c.Id == "Shop.Mine");
        Assert.True(overview.OmittedClusters > 0);
    }

    [Theory]
    // A dotted symbol groups on dots, a module path on slashes.
    [InlineData("TheTerrace.Features.Competitions.Season", 2, "TheTerrace.Features")]
    [InlineData("src/app/models/order", 2, "src/app")]
    // An id with fewer segments than the depth IS its own group — grouping it under a shorter prefix
    // no other node shares would invent a container the repository does not have.
    [InlineData("Order", 2, "Order")]
    // A scope-qualified id already names its container; splitting past the marker would put every
    // scope's `main` in one group.
    [InlineData("bicep:main#siteName", 2, "bicep:main")]
    public void AGroupingKeyFollowsTheIdsOwnHierarchy(string id, int depth, string expected) =>
        Assert.Equal(expected, GraphOverview.GroupFor(id, depth));

    [Fact]
    public void DisclosuresSurviveTheSummary()
    {
        // A summary that dropped the caveats would be a clean-looking picture of a partial index —
        // the exact "clean empty success over rotting evidence" this product exists to avoid.
        var overview = Summarise(
        [
            Say("scope", "discloses", "packages-not-restored"),
            Say("Shop.Orders.Order", "has_type", "class"),
        ], new OverviewQuery(Depth: 2));

        Assert.Contains("packages-not-restored", overview.Disclosures);
    }
}
