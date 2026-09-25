using AiDe.Core.Facts;
using AiDe.Core.Projections;

namespace AiDe.Core.Tests;

/// <summary>
/// How one node reaches another.
/// </summary>
/// <remarks>
/// "What does this touch" is answered by a neighbourhood; "through WHAT does it touch it" is a
/// route, and nothing could answer it. These pin the four things a route can get quietly wrong:
/// walking an edge backwards, laundering an inferred link inside a verified chain, reporting a
/// missing node as an absent route, and looping forever.
/// </remarks>
public sealed class GraphPathsTests
{
    private static EvidenceAssertion Say(string subject, string predicate, string obj,
        VerificationStatus status = VerificationStatus.Verified) =>
        new("scope", "rev-1", subject, predicate, obj, EvidenceOrigin.Static, status,
            new Provenance("test", null, "test", "1", DateTimeOffset.UnixEpoch));

    private static WorkspaceGraph Graph(params EvidenceAssertion[] assertions) =>
        new GraphProjection(assertions, "rev-1").Compute();

    [Fact]
    public void ARouteIsTheEdgesBetweenTwoNodes()
    {
        var graph = Graph(
            Say("A", "has_type", "class"),
            Say("B", "has_type", "class"),
            Say("C", "has_type", "class"),
            Say("A", "depends_on", "B"),
            Say("B", "depends_on", "C"));

        var result = GraphPaths.Find(graph, new PathQuery("A", "C"));

        var path = Assert.Single(result.Paths);
        Assert.Equal(2, path.Edges.Count);
        Assert.Equal("A", path.Edges[0].From);
        Assert.Equal("C", path.Edges[1].To);
        Assert.Null(result.Reason);
    }

    [Fact]
    public void AnEdgeIsNotWalkedBackwards()
    {
        // `A depends_on B` does not mean B depends on A. A route that walks the edge backwards
        // answers "these are related" while looking like "a change here reaches there".
        var graph = Graph(
            Say("A", "has_type", "class"),
            Say("B", "has_type", "class"),
            Say("A", "depends_on", "B"));

        var forward = GraphPaths.Find(graph, new PathQuery("A", "B"));
        Assert.Single(forward.Paths);

        var backward = GraphPaths.Find(graph, new PathQuery("B", "A"));
        Assert.Empty(backward.Paths);
        Assert.NotNull(backward.Reason);
    }

    [Fact]
    public void ARouteIsOnlyAsStrongAsItsWeakestEdge()
    {
        // One inferred link in a run of verified ones makes the whole claim inferred. Presenting the
        // route without saying so would launder a guess into a fact.
        var graph = Graph(
            Say("A", "has_type", "class"),
            Say("B", "has_type", "class"),
            Say("C", "has_type", "class"),
            Say("A", "depends_on", "B"),
            Say("B", "maps_to", "C", VerificationStatus.Inferred));

        var path = Assert.Single(GraphPaths.Find(graph, new PathQuery("A", "C")).Paths);

        Assert.Equal(VerificationStatus.Inferred, path.Status);
    }

    [Fact]
    public void AMissingEndpointIsNotTheSameAnswerAsNoRoute()
    {
        // Collapsing the two tells a user their code is unconnected when it was filtered out or
        // misspelled.
        var graph = Graph(
            Say("A", "has_type", "class"),
            Say("B", "has_type", "class"));

        var absent = GraphPaths.Find(graph, new PathQuery("A", "Nowhere"));
        Assert.Empty(absent.Paths);
        Assert.Contains("not in this graph", absent.Reason);

        var disconnected = GraphPaths.Find(graph, new PathQuery("A", "B"));
        Assert.Empty(disconnected.Paths);
        Assert.Contains("no route", disconnected.Reason);
    }

    [Fact]
    public void ACycleTerminates()
    {
        var graph = Graph(
            Say("A", "has_type", "class"),
            Say("B", "has_type", "class"),
            Say("A", "depends_on", "B"),
            Say("B", "depends_on", "A"));

        var result = GraphPaths.Find(graph, new PathQuery("A", "B"));

        var path = Assert.Single(result.Paths);
        Assert.Single(path.Edges);
    }

    [Fact]
    public void EveryShortestRouteIsReturned_AndLongerOnesAreNot()
    {
        // Two ways round of equal length are both answers. A third, longer way is a different
        // question — "is there another route" — and answering it by accident buries the short ones.
        var graph = Graph(
            Say("A", "has_type", "class"),
            Say("B", "has_type", "class"),
            Say("C", "has_type", "class"),
            Say("D", "has_type", "class"),
            Say("Long", "has_type", "class"),
            Say("A", "depends_on", "B"),
            Say("A", "depends_on", "C"),
            Say("B", "depends_on", "D"),
            Say("C", "depends_on", "D"),
            Say("A", "depends_on", "Long"),
            Say("Long", "depends_on", "B"));

        var result = GraphPaths.Find(graph, new PathQuery("A", "D"));

        Assert.Equal(2, result.Paths.Count);
        Assert.All(result.Paths, p => Assert.Equal(2, p.Edges.Count));
    }

    [Fact]
    public void ALengthLimitIsReportedRatherThanReturningNothingQuietly()
    {
        var graph = Graph(
            Say("A", "has_type", "class"),
            Say("B", "has_type", "class"),
            Say("C", "has_type", "class"),
            Say("A", "depends_on", "B"),
            Say("B", "depends_on", "C"));

        var result = GraphPaths.Find(graph, new PathQuery("A", "C", MaxLength: 1));

        Assert.Empty(result.Paths);
        Assert.Contains("within 1 edge", result.Reason);
    }

    [Fact]
    public void MoreRoutesThanAskedForAreReportedAsTruncated()
    {
        // Silence here would read as "these are all of them", which is the absence-rendered-as-
        // success shape this codebase has a defect class for.
        var assertions = new List<EvidenceAssertion>
        {
            Say("A", "has_type", "class"),
            Say("Z", "has_type", "class"),
        };

        for (var i = 0; i < 6; i++)
        {
            assertions.Add(Say($"Mid{i}", "has_type", "class"));
            assertions.Add(Say("A", "depends_on", $"Mid{i}"));
            assertions.Add(Say($"Mid{i}", "depends_on", "Z"));
        }

        var graph = new GraphProjection(assertions, "rev-1").Compute();

        var result = GraphPaths.Find(graph, new PathQuery("A", "Z", MaxPaths: 2));

        Assert.Equal(2, result.Paths.Count);
        Assert.True(result.Truncated);
    }

    [Fact]
    public void ANodeReachesItselfWithoutTravelling()
    {
        var graph = Graph(Say("A", "has_type", "class"));

        var path = Assert.Single(GraphPaths.Find(graph, new PathQuery("A", "A")).Paths);

        Assert.Empty(path.Edges);
        Assert.Equal(VerificationStatus.Verified, path.Status);
    }
}
