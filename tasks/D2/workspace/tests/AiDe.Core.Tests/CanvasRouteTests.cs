using AiDe.Testing;
using AiDe.Core.Facts;
using AiDe.Core.Presentation;
using AiDe.Core.Projections;

namespace AiDe.Core.Tests;

/// <summary>
/// The route, as the canvas would draw it.
/// </summary>
/// <remarks>
/// A route is a SUBGRAPH, so it comes back as the graph the canvas already draws — the design
/// session binds what it already binds and only the caption changes. These pin the caption, because
/// the caption is the part that can quietly mislead: a route rendered without its weakest link looks
/// like a fact about the code when one inferred edge makes the whole claim inferred.
/// </remarks>
public sealed class CanvasRouteTests
{
    private sealed class StubQueries(PathResult result) : FakeWorkspaceQueries
    {
        public PathQuery? Asked { get; private set; }

        public override Task<PathResult> PathsAsync(PathQuery query, CancellationToken ct)
        {
            Asked = query;
            return Task.FromResult(result);
        }






    }

    private static GraphEdge Edge(string from, string to, VerificationStatus status) =>
        new(from, to, "depends_on", status);

    [Fact]
    public async Task ARouteComesBackAsTheGraphTheCanvasAlreadyDraws()
    {
        var queries = new StubQueries(new PathResult(
            [new GraphPath([
                Edge("Shop.Order", "Shop.Ledger", VerificationStatus.Verified),
                Edge("Shop.Ledger", "Shop.Audit", VerificationStatus.Verified),
            ])],
            Truncated: false, Reason: null, SourceRevision: "rev-1"));

        var graph = await new CanvasGraphViewModel(queries)
            .RouteAsync("Shop.Order", "Shop.Audit");

        Assert.Equal(3, graph.Nodes.Count);
        Assert.Equal(2, graph.Edges.Count);

        // The endpoints are marked so the renderer can anchor them.
        Assert.True(graph.Nodes.Single(n => n.Id == "Shop.Order").IsRoot);
        Assert.True(graph.Nodes.Single(n => n.Id == "Shop.Audit").IsRoot);
        Assert.False(graph.Nodes.Single(n => n.Id == "Shop.Ledger").IsRoot);

        Assert.Contains("1 route", graph.Message);
        Assert.Contains("2 edges", graph.Message);
        Assert.Contains("every edge is verified", graph.Message);
    }

    [Fact]
    public async Task TheCaptionNamesTheWeakestLink()
    {
        var queries = new StubQueries(new PathResult(
            [new GraphPath([
                Edge("A", "B", VerificationStatus.Verified),
                Edge("B", "C", VerificationStatus.Inferred),
            ])],
            Truncated: false, Reason: null, SourceRevision: "rev-1"));

        var graph = await new CanvasGraphViewModel(queries).RouteAsync("A", "C");

        Assert.Contains("weakest link is Inferred", graph.Message);
    }

    [Fact]
    public async Task TwoRoutesSharingAnEdgeDrawItOnce()
    {
        // Drawing it twice renders a thicker line that means nothing.
        var queries = new StubQueries(new PathResult(
            [
                new GraphPath([Edge("A", "M", VerificationStatus.Verified), Edge("M", "Z", VerificationStatus.Verified)]),
                new GraphPath([Edge("A", "N", VerificationStatus.Verified), Edge("N", "Z", VerificationStatus.Verified)]),
            ],
            Truncated: true, Reason: null, SourceRevision: "rev-1"));

        var graph = await new CanvasGraphViewModel(queries).RouteAsync("A", "Z");

        Assert.Equal(4, graph.Edges.Count);
        Assert.Equal(4, graph.Nodes.Count);
        Assert.Contains("2 routes", graph.Message);
        Assert.Contains("More routes", graph.Message);
    }

    [Fact]
    public async Task TheProjectionsReasonSurvivesToTheCaption()
    {
        // "not in this graph" and "no route within 8 edges" send a user to different places, so the
        // reason is passed through rather than replaced with a house style (DC-011).
        var queries = new StubQueries(new PathResult(
            [], Truncated: false, Reason: "'Shop.Ghost' is not in this graph", SourceRevision: "rev-1"));

        var graph = await new CanvasGraphViewModel(queries).RouteAsync("Shop.Order", "Shop.Ghost");

        Assert.Empty(graph.Nodes);
        Assert.Contains("is not in this graph", graph.Message);
    }

    [Fact]
    public async Task WithNoWorkspaceItSaysSoRatherThanDrawingNothing()
    {
        var graph = await new CanvasGraphViewModel(null).RouteAsync("A", "B");

        Assert.Empty(graph.Nodes);
        Assert.Equal("No workspace is open.", graph.Message);
    }

    [Fact]
    public async Task AnIncompleteRequestIsNotSentToTheStore()
    {
        var queries = new StubQueries(new PathResult([], false, null, "rev-1"));

        var graph = await new CanvasGraphViewModel(queries).RouteAsync("A", "   ");

        Assert.Null(queries.Asked);
        Assert.Equal("Pick a start and an end.", graph.Message);
    }
}
