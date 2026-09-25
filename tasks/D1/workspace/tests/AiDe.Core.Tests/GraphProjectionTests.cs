using AiDe.Core.Facts;
using AiDe.Core.Projections;

namespace AiDe.Core.Tests;

/// <summary>
/// The whole workspace as a graph.
/// </summary>
/// <remarks>
/// <para><b>Reported by the user.</b> TheTerrace rendered as <b>two nodes</b> against the same
/// repository's full graph in Obsidian. The cause was not extraction — the store held 12,100
/// assertions across 2,164 nodes — it was that the graph surface asked
/// <c>FindAsync("", 1)</c> for a single root and then drew that root's neighbours. It had never
/// shown a graph.</para>
///
/// <para>These pin the projection that replaced it, including the two judgements that decide whether
/// the picture is of the user's code or of the framework it happens to use.</para>
/// </remarks>
public sealed class GraphProjectionTests
{
    private static EvidenceAssertion Say(string subject, string predicate, string obj,
        VerificationStatus status = VerificationStatus.Verified) =>
        new("scope", "rev-1", subject, predicate, obj, EvidenceOrigin.Static, status,
            new Provenance("test", null, "test", "1", DateTimeOffset.UnixEpoch));

    [Fact]
    public void TheGraphIsEveryNodeAndEdge_NotOneNeighbourhood()
    {
        var graph = new GraphProjection(
        [
            Say("Shop.Order", "has_type", "class"),
            Say("Shop.Customer", "has_type", "class"),
            Say("Shop.Ledger", "has_type", "class"),
            Say("Shop.Order", "depends_on", "Shop.Customer"),
            Say("Shop.Ledger", "depends_on", "Shop.Order"),
        ], "rev-1").Compute();

        Assert.Equal(3, graph.Nodes.Count);
        Assert.Equal(2, graph.Edges.Count);
        Assert.Equal(0, graph.Omitted);
    }

    [Fact]
    public void AttributesDescribeANode_TheyAreNotEdges()
    {
        // Drawing `has_type` would put the string "class" in the graph as a thing other things point
        // at. The kind belongs ON the node, and the same rule the search already applies is applied
        // here from one definition.
        var graph = new GraphProjection(
        [
            Say("Shop.Order", "has_type", "class"),
            Say("Shop.Order", "declared_in", "Shop.dll"),
        ], "rev-1").Compute();

        var node = Assert.Single(graph.Nodes);
        Assert.Equal("class", node.Kind);
        Assert.Empty(graph.Edges);
    }

    [Fact]
    public void DisclosuresAreLiftedOutOfTheEdges()
    {
        // A `discloses` arrow to a node called "packages-not-restored" is noise on a canvas and a
        // warning in a caption.
        var graph = new GraphProjection(
        [
            Say("scope", "discloses", "packages-not-restored"),
            Say("Shop.Order", "has_type", "class"),
        ], "rev-1").Compute();

        Assert.Contains("packages-not-restored", graph.Disclosures);
        Assert.DoesNotContain(graph.Nodes, n => n.Id == "packages-not-restored");
    }

    [Fact]
    public void ANodeNothingDeclaresIsMarkedExternal()
    {
        // MEASURED: the six most-connected nodes of a real repository were string, int,
        // Task<TResult>, DateTimeOffset, IReadOnlyList<T> and Guid — 773 edges to `string` alone.
        // A graph whose centre is the BCL is not a picture of anybody's domain.
        var graph = new GraphProjection(
        [
            Say("Shop.Order", "has_type", "class"),
            Say("Shop.Order", "depends_on", "string"),
        ], "rev-1").Compute();

        var mine = Assert.Single(graph.Nodes, n => n.Id == "Shop.Order");
        Assert.False(mine.IsExternal);

        var framework = Assert.Single(graph.Nodes, n => n.Id == "string");
        Assert.True(framework.IsExternal);
        Assert.Equal("external", framework.Kind);
    }

    [Fact]
    public void WhenTheCapApplies_TheUsersOwnCodeIsKeptOverTheFramework()
    {
        // The judgement that matters at the cap. Ordering by raw degree kept `string` and dropped
        // the types the user actually wrote, because a framework primitive is referenced by
        // everything and declared by nothing.
        var assertions = new List<EvidenceAssertion> { Say("Shop.Order", "has_type", "class") };

        // One declared type with a single edge, against a framework type with fifty.
        for (var i = 0; i < 50; i++)
        {
            assertions.Add(Say($"Other{i}", "depends_on", "string"));
        }

        assertions.Add(Say("Shop.Order", "depends_on", "Shop.Customer"));
        assertions.Add(Say("Shop.Customer", "has_type", "class"));

        var graph = new GraphProjection(assertions, "rev-1").Compute(maxNodes: 2);

        Assert.All(graph.Nodes, n => Assert.False(n.IsExternal));
        Assert.True(graph.Omitted > 0);
    }

    [Fact]
    public void AnEdgeWhoseOtherEndWasDroppedIsDroppedWithIt()
    {
        // A half-edge into nothing looks like a node the layout failed to place, which is worse than
        // an omission the caption accounts for.
        var graph = new GraphProjection(
        [
            Say("Shop.Order", "has_type", "class"),
            Say("Shop.Order", "depends_on", "string"),
        ], "rev-1").Compute(maxNodes: 1);

        Assert.Single(graph.Nodes);
        Assert.Empty(graph.Edges);
        Assert.Equal(1, graph.Omitted);
    }

    [Fact]
    public void ANodeCarriesTheCLASSItsProducerDeclared()
    {
        // Reported by the user: the Knowledge chip read 0 on a repository holding 2,343 knowledge
        // nodes. The graph carried each node's fine Kind, and that repository's knowledge kinds are
        // `spec` and `knowledge-epl-fan-platform` — a name it invented. A filter matching a fixed
        // list of type names cannot work across repositories, and widening the list only moves the
        // problem to the next one. The coarse class is DECLARED, so a filter can ask directly.
        var graph = new GraphProjection(
        [
            Say("adr-1", "has_type", "adr"),
            Say("adr-1", "node_class", "knowledge"),
            Say("Shop.Order", "has_type", "class"),
        ], "rev-1").Compute();

        Assert.True(Assert.Single(graph.Nodes, n => n.Id == "adr-1").IsKnowledge);
        Assert.False(Assert.Single(graph.Nodes, n => n.Id == "Shop.Order").IsKnowledge);
    }

    [Fact]
    public void AnInventedKnowledgeTypeIsStillKnowledge()
    {
        // The whole point: `knowledge-epl-fan-platform` is a type this product has never heard of,
        // and the class still answers correctly because the producer said so.
        var graph = new GraphProjection(
        [
            Say("kb-fans", "has_type", "knowledge-epl-fan-platform"),
            Say("kb-fans", "node_class", "knowledge"),
        ], "rev-1").Compute();

        Assert.True(Assert.Single(graph.Nodes).IsKnowledge);
    }

    // ---- the filtered subgraph ---------------------------------------------

    [Fact]
    public void AKindFilterKeepsOnlyThatKind_AndDropsTheEdgesThatLeaveIt()
    {
        var graph = new GraphProjection(
        [
            Say("Shop.Order", "has_type", "class"),
            Say("Shop.IRepo", "has_type", "interface"),
            Say("Shop.Order", "depends_on", "Shop.IRepo"),
        ], "rev-1").Compute(new GraphQuery(Kinds: ["class"]));

        var node = Assert.Single(graph.Nodes);
        Assert.Equal("Shop.Order", node.Id);

        // The edge led out of the requested graph, so it is not drawn into a node that is not there.
        Assert.Empty(graph.Edges);
    }

    [Fact]
    public void ExcludeKnowledge_DropsDeclaredKnowledgeNodes_ButKeepsEverythingElse()
    {
        // Ruling 53/US-C8: Architecture's canvas asks for code, data and architecture — never the
        // knowledge/spec corpus. Excluding by the DECLARED node_class flag, exactly like
        // ANodeCarriesTheCLASSItsProducerDeclared above — never an allow-list of "code/data/
        // architecture" has_type spellings, which would go stale the first repository that used a
        // spelling nobody had added (DC-033, the same trap this file already pins for the Knowledge
        // chip).
        var graph = new GraphProjection(
        [
            Say("Shop.Order", "has_type", "class"),
            Say("adr-1", "has_type", "adr"),
            Say("adr-1", "node_class", "knowledge"),
            Say("adr-1", "depends_on", "Shop.Order"),
        ], "rev-1").Compute(new GraphQuery(ExcludeKnowledge: true));

        var node = Assert.Single(graph.Nodes);
        Assert.Equal("Shop.Order", node.Id);
        Assert.Empty(graph.Edges);   // the knowledge endpoint is gone, so its edge cannot be drawn
    }

    [Fact]
    public void ExcludeKnowledge_Unset_DrawsKnowledgeNodesToo()
    {
        var graph = new GraphProjection(
        [
            Say("Shop.Order", "has_type", "class"),
            Say("adr-1", "has_type", "adr"),
            Say("adr-1", "node_class", "knowledge"),
        ], "rev-1").Compute(new GraphQuery());

        Assert.Equal(2, graph.Nodes.Count);
    }

    [Fact]
    public void ExcludingExternalsLeavesOnlyWhatTheWorkspaceDeclares()
    {
        var graph = new GraphProjection(
        [
            Say("Shop.Order", "has_type", "class"),
            Say("Shop.Order", "depends_on", "string"),
        ], "rev-1").Compute(new GraphQuery(IncludeExternal: false));

        Assert.Single(graph.Nodes);
        Assert.All(graph.Nodes, n => Assert.False(n.IsExternal));
    }

    [Fact]
    public void AScopeFilterKeepsOnlyWhatThatScopeDeclares()
    {
        var graph = new GraphProjection(
        [
            Say("Shop.Order", "has_type", "class"),
            Say("Shop.Order", "declared_in", "csharp:Shop:net10.0"),
            Say("Web.Page", "has_type", "class"),
            Say("Web.Page", "declared_in", "csharp:Web:net10.0"),
        ], "rev-1").Compute(new GraphQuery(ScopeId: "csharp:Shop:net10.0"));

        var node = Assert.Single(graph.Nodes);
        Assert.Equal("Shop.Order", node.Id);
    }

    [Fact]
    public void DegreeIsCountedOverTheFilteredGraph_NotTheWholeOne()
    {
        // The judgement that makes the filter worth having. `string` is referenced by everything, so
        // ranking by whole-graph degree would order the user's own types by how much framework they
        // touch — and at a cap, keep the wrong ones. Filter first, THEN rank.
        var assertions = new List<EvidenceAssertion>
        {
            Say("Shop.Hub", "has_type", "class"),
            Say("Shop.Leaf", "has_type", "class"),
            Say("Shop.Other", "has_type", "class"),

            // Leaf touches a lot of framework; Hub is connected to its own code.
            Say("Shop.Leaf", "depends_on", "string"),
            Say("Shop.Leaf", "depends_on", "int"),
            Say("Shop.Leaf", "depends_on", "Guid"),
            Say("Shop.Hub", "depends_on", "Shop.Leaf"),
            Say("Shop.Hub", "depends_on", "Shop.Other"),
        };

        // Three framework edges plus the one from Hub.
        var whole = new GraphProjection(assertions, "rev-1").Compute();
        Assert.Equal(4, whole.Nodes.Single(n => n.Id == "Shop.Leaf").Degree);

        var mine = new GraphProjection(assertions, "rev-1")
            .Compute(new GraphQuery(IncludeExternal: false));

        // Leaf's three framework edges are gone; only the one to Hub remains.
        Assert.Equal(1, mine.Nodes.Single(n => n.Id == "Shop.Leaf").Degree);
        Assert.Equal("Shop.Hub", mine.Nodes[0].Id);
    }

    [Fact]
    public void TheCapAppliesAfterTheFilter_SoTheCallerGetsTheRightNodesTrimmed()
    {
        // Filtering AFTER a cap would rank and trim the whole graph and only then discard, so a
        // caller asking for two classes could receive none — and nothing in the result would say so.
        var assertions = new List<EvidenceAssertion>
        {
            Say("Shop.Order", "has_type", "class"),
            Say("Shop.Customer", "has_type", "class"),
        };

        // Fifty framework nodes that would otherwise fill any small cap.
        for (var i = 0; i < 50; i++)
        {
            assertions.Add(Say($"Shop.Order", "depends_on", $"Framework{i}"));
        }

        var graph = new GraphProjection(assertions, "rev-1")
            .Compute(new GraphQuery(MaxNodes: 2, IncludeExternal: false));

        Assert.Equal(2, graph.Nodes.Count);
        Assert.All(graph.Nodes, n => Assert.False(n.IsExternal));
        Assert.Equal(0, graph.Omitted);
    }

    [Fact]
    public void AnEdgeKeepsTheStatusOfTheEvidenceBehindIt()
    {
        // A convention-derived edge drawn identically to a compiler-resolved one is the whole
        // confidence problem in one picture.
        var graph = new GraphProjection(
        [
            Say("Shop.Order", "has_type", "class"),
            Say("Shop.Order", "maps_to", "table:Order", VerificationStatus.Inferred),
        ], "rev-1").Compute();

        var edge = Assert.Single(graph.Edges);
        Assert.Equal(VerificationStatus.Inferred, edge.Status);
    }
}
