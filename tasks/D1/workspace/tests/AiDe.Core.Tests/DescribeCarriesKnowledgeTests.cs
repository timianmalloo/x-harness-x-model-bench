using AiDe.Core.Presentation;
using AiDe.Core.Projections;

namespace AiDe.Core.Tests;

/// <summary>
/// A drill-down knows whether what it is holding is knowledge.
/// </summary>
/// <remarks>
/// <para><b>Why this path carries the weight now.</b> The default graph is a map of the code: nodes
/// are ordered declared-first then by degree, and knowledge has a measured median relation degree of
/// <b>0</b>, so most of a workspace's 878 knowledge nodes can never win a slot under the cap. That is
/// the right default — reserving slots would draw hundreds of disconnected dots and evict connected
/// code — but it makes drill-down, not the budget, the way a knowledge node is reached. The graph
/// says <c>NotInView</c>; describe is where the user goes next.</para>
///
/// <para><b>The gap this closes was written down and left open.</b> <c>CanvasGraphViewModel</c>
/// carried a comment saying <c>IsKnowledge</c> was not set on drill-down neighbours because a kind is
/// not a node class, so the view "genuinely cannot tell knowledge from source", and that <c>false</c>
/// under-counted rather than mislabelled. Under-counting is the safer direction and still a renderer
/// answering a question it had no data for — INV-0004 one field over.</para>
///
/// <para><b>One authority, not two.</b> The flag is read from the same <c>node_class = knowledge</c>
/// fact the graph projection reads. Deriving it a second time from the kind would put two
/// definitions of one quantity in the codebase, which is a defect signature on its own.</para>
/// </remarks>
public sealed class DescribeCarriesKnowledgeTests
{
    /// <summary>A doc that links to nothing, and code that links to code — the real shape.</summary>
    private static TestWorkspace Seeded()
    {
        var ws = TestWorkspace.Create();

        ws.CommitSnapshot("fixture", 1, "rev-1", [
            TestWorkspace.Assertion("code.Widget", "has_type", "class"),
            TestWorkspace.Assertion("code.Widget", "depends_on", "code.Gadget"),
            TestWorkspace.Assertion("code.Gadget", "has_type", "class"),

            // A knowledge node WITH an edge, so it can be reached as a neighbour at all.
            TestWorkspace.Assertion("docs.Adr", "has_type", "decision"),
            TestWorkspace.Assertion("docs.Adr", "node_class", "knowledge"),
            TestWorkspace.Assertion("docs.Adr", "documents", "code.Widget"),

            // And one with NO edges — the median case, and the one only drill-down can reach.
            TestWorkspace.Assertion("docs.Orphan", "has_type", "design"),
            TestWorkspace.Assertion("docs.Orphan", "node_class", "knowledge"),
        ]);

        return ws;
    }

    private static DescribeResult Describe(TestWorkspace ws, string id) =>
        new ProjectionService(ws.Store).Describe(id, 50);

    [Fact]
    public void TheDescribedNodeReportsThatItIsKnowledge()
    {
        // The ROOT, which a neighbours-only fix would have missed — and the root is precisely what a
        // NotInView search hit drills into.
        using var ws = Seeded();

        Assert.Contains("docs.Adr", Describe(ws, "docs.Adr").KnowledgeIds!);
    }

    [Fact]
    public void ACodeNodeIsNotReportedAsKnowledge()
    {
        // The DC-016 guard on the assertion above: a KnowledgeIds that contained everything would
        // satisfy the first test while telling the user nothing.
        using var ws = Seeded();

        var result = Describe(ws, "code.Widget");

        Assert.DoesNotContain("code.Widget", result.KnowledgeIds!);
        Assert.DoesNotContain("code.Gadget", result.KnowledgeIds!);
    }

    [Fact]
    public void AKnowledgeNeighbourIsReportedFromTheCodeSide()
    {
        // Drilling into code must classify its knowledge neighbours correctly, or the filter is
        // being told something false about what it is looking at.
        using var ws = Seeded();

        Assert.Contains("docs.Adr", Describe(ws, "code.Widget").KnowledgeIds!);
    }

    /// <summary>Hands the view model a REAL describe result, not a hand-built one.</summary>
    /// <remarks>
    /// A stub returning a literal <c>DescribeResult</c> would assert that the view model copies a
    /// field, which is true of a field that was never populated. Driving the real projection means
    /// the store, the projection and the view model all have to agree, and DC-074 lives at exactly
    /// that seam.
    /// </remarks>
    private sealed class RealDescribe(DescribeResult result) : AiDe.Testing.FakeWorkspaceQueries
    {
        public override Task<DescribeResult> DescribeAsync(
            string nodeId, int maxNeighbors, CancellationToken cancellationToken)
            => Task.FromResult(result);
    }

    [Fact]
    public async Task TheFlagReachesTheCanvasNodeAndNotJustTheProjection()
    {
        // The surface half. A field can be correct in the projection and dropped at the client
        // boundary — that is DC-074, and it is how IsKnowledge failed the first time.
        using var ws = Seeded();

        var vm = new CanvasGraphViewModel(new RealDescribe(Describe(ws, "docs.Adr")));
        var graph = await vm.LoadAsync("docs.Adr");

        var root = graph.Nodes.Single(n => n.Id == "docs.Adr");
        var neighbour = graph.Nodes.Single(n => n.Id == "code.Widget");

        Assert.True(root.IsKnowledge, "the described knowledge node did not reach the canvas as knowledge");
        Assert.False(neighbour.IsKnowledge, "a code neighbour was marked as knowledge");
    }

    [Fact]
    public void AnEdgelessKnowledgeNodeIsStillDescribable()
    {
        // The median knowledge node has degree 0 and can never be drawn under the budget. If
        // describe could not answer for it, the NotInView message would point nowhere and the
        // "map of the code" default would be a silent loss rather than a stated bound.
        using var ws = Seeded();

        var result = Describe(ws, "docs.Orphan");

        Assert.Contains("docs.Orphan", result.KnowledgeIds!);

        // "Edgeless" means no relation to ANOTHER NODE. The result still carries the node's own
        // attribute facts (`has_type`, `node_class`) as rows — correct, and what makes it
        // describable at all. Asserting Empty was the test being wrong about the data.
        //
        // Named nodes rather than a `NeighborKinds` lookup, because that dictionary is keyed by
        // every edge endpoint including attribute VALUES ("design", "knowledge"), so it would not
        // have distinguished the two cases either.
        string[] realNodes = ["code.Widget", "code.Gadget", "docs.Adr"];

        Assert.DoesNotContain(result.Neighbors, e => realNodes.Contains(e.Object) || realNodes.Contains(e.Subject));
    }
}
