using AiDe.Core.Projections;

namespace AiDe.Core.Tests;

/// <summary>
/// The declared totals count what the workspace HAS, not what the graph drew.
/// </summary>
/// <remarks>
/// <para><b>Why this exists.</b> The canvas chip read "Knowledge 257" against a workspace holding
/// 878 knowledge nodes. It was not lying about what was drawn — the graph keeps the 1,500
/// most-connected of 2,992, and MEASURED on that workspace knowledge has median relation degree
/// <b>0</b> against 4 for everything else, so roughly 620 knowledge nodes are never candidates for a
/// slot. A count that is a lower bound and one that is exact must be distinguishable, and no surface
/// could make that distinction because the denominator did not cross the wire.</para>
///
/// <para><b>The trap this guards.</b> A total computed over the KEPT nodes would equal the drawn
/// count, the ratio would always read "n of n", and every assertion about it would pass — a
/// denominator that cannot disagree with its numerator is not a denominator. So the fixture forces
/// the cap to bite and requires the two numbers to differ.</para>
/// </remarks>
public sealed class DeclaredTotalsAreDenominatorsTests
{
    /// <summary>A workspace with more nodes than the cap will draw, and a low-degree tail.</summary>
    private static TestWorkspace Seeded(int hubs, int orphanDocs)
    {
        var ws = TestWorkspace.Create();
        var facts = new List<Facts.EvidenceAssertion>();

        // Well-connected code: each hub depends on the next, so every one has degree >= 1.
        for (var i = 0; i < hubs; i++)
        {
            facts.Add(TestWorkspace.Assertion($"code.Hub{i}", "has_type", "class"));
            facts.Add(TestWorkspace.Assertion($"code.Hub{i}", "depends_on", $"code.Hub{(i + 1) % hubs}"));
        }

        // Documents that link to nothing — the shape the real workspace has, and the reason they
        // lose every tie for a slot under a most-connected-first cap.
        for (var i = 0; i < orphanDocs; i++)
        {
            facts.Add(TestWorkspace.Assertion($"docs.Note{i}", "has_type", "design"));
            facts.Add(TestWorkspace.Assertion($"docs.Note{i}", "node_class", "knowledge"));
        }

        ws.CommitSnapshot("fixture", 1, "rev-1", [.. facts]);
        return ws;
    }

    private static WorkspaceGraph Graph(TestWorkspace ws, int maxNodes) =>
        new ProjectionService(ws.Store).Graph(new GraphQuery(maxNodes));

    private static int DeclaredKnowledge(WorkspaceGraph g) =>
        g.DeclaredByKind?.Where(t => t.IsKnowledge).Sum(t => t.Declared) ?? 0;

    [Fact]
    public void TheKnowledgeTotalCountsNodesTheGraphNeverDrew()
    {
        // The whole point, and the assertion that fails if the total is computed over kept nodes.
        using var ws = Seeded(hubs: 40, orphanDocs: 60);

        var graph = Graph(ws, maxNodes: 45);

        var drawn = graph.Nodes.Count(n => n.IsKnowledge);

        Assert.Equal(60, DeclaredKnowledge(graph));
        Assert.True(drawn < 60,
            $"the cap did not bite — {drawn} knowledge nodes were drawn of 60, so this test cannot "
            + "tell a real denominator from a count of what was kept");
    }

    [Fact]
    public void TheTotalsAreByKindAndNotByTheCanvassCategories()
    {
        // Core does not know Code/Data/Infra/Specs/Knowledge — that taxonomy is the surface's, and
        // teaching it to the projection would make it wrong for every other consumer.
        using var ws = Seeded(hubs: 10, orphanDocs: 10);

        var kinds = Graph(ws, maxNodes: 100).DeclaredByKind!.Select(t => t.Kind).ToList();

        Assert.Contains("class", kinds);
        Assert.Contains("design", kinds);
        Assert.DoesNotContain("knowledge", kinds);   // a category, not a kind
        Assert.DoesNotContain("code", kinds);
    }

    [Fact]
    public void TheKnowledgeFlagTravelsWithEachKind()
    {
        // Measured on a real workspace, no kind is used both ways — which is one corpus, not a rule.
        // Carrying the flag means a repository that uses a kind both ways is counted correctly
        // rather than plausibly.
        using var ws = Seeded(hubs: 5, orphanDocs: 5);

        var totals = Graph(ws, maxNodes: 100).DeclaredByKind!;

        Assert.Contains(totals, t => t is { Kind: "design", IsKnowledge: true });
        Assert.Contains(totals, t => t is { Kind: "class", IsKnowledge: false });
    }

    [Fact]
    public void EveryDrawnNodeIsCountedInSomeTotal()
    {
        // A denominator smaller than its numerator is worse than none: it would render "257 of 100"
        // and make the surface look broken rather than the data look bounded.
        using var ws = Seeded(hubs: 30, orphanDocs: 30);

        var graph = Graph(ws, maxNodes: 20);
        var declared = graph.DeclaredByKind!.Sum(t => t.Declared);

        Assert.True(declared >= graph.Nodes.Count,
            $"declared total {declared} is smaller than the {graph.Nodes.Count} nodes drawn");
    }

    [Fact]
    public void AnUncappedGraphStillReportsTotals()
    {
        // When nothing was dropped the ratio reads "n of n", which is how a surface knows the count
        // is EXACT. Omitting totals in that case would leave it unable to tell exact from bounded —
        // the same defect from the other direction.
        using var ws = Seeded(hubs: 5, orphanDocs: 5);

        var graph = Graph(ws, maxNodes: 500);

        Assert.Equal(0, graph.Omitted);
        Assert.Equal(5, DeclaredKnowledge(graph));
        Assert.Equal(5, graph.Nodes.Count(n => n.IsKnowledge));
    }
}
