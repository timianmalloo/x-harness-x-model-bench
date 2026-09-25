using AiDe.Core.Facts;
using AiDe.Core.Presentation;
using AiDe.Core.Projections;

namespace AiDe.Core.Tests;

/// <summary>
/// What the canvas draws, decided in Core where it can be tested without a browser.
/// </summary>
/// <remarks>
/// The interesting cases are the ones where the graph is <b>incomplete</b>. A canvas that renders
/// twelve nodes when the projection bounded the answer at twelve, or that omits package types
/// because nothing restored them, looks exactly like a small honest graph — so the omissions have to
/// travel with the data rather than being left for the user to infer.
/// </remarks>
public sealed class CanvasGraphViewModelTests
{
    private sealed class StubQueries : IWorkspaceQueries
    {
        public DescribeResult? Describe { get; set; }
        public List<FindMatch> Matches { get; } = [];
        public Exception? Throw { get; set; }
        public string? LastDescribedNode { get; private set; }

        public Task<DescribeResult> DescribeAsync(string nodeId, int maxNeighbors, CancellationToken ct)
        {
            if (Throw is not null) throw Throw;
            LastDescribedNode = nodeId;
            return Task.FromResult(Describe ?? Empty(nodeId));
        }

        public Task<FindResult> FindAsync(string term, int maxResults, CancellationToken ct)
        {
            if (Throw is not null) throw Throw;
            return Task.FromResult(new FindResult(Matches, Bounds(0), "rev-1"));
        }

        public Task<ImpactResult> ImpactAsync(string nodeId, int maxNodes, int maxEdges, CancellationToken ct) =>
            Task.FromResult(new ImpactResult(nodeId, [], [], Bounds(0), "rev-1"));

        public Task<ContentSearchResult> SearchContentAsync(string term, int maxMatches, CancellationToken ct) =>
            Task.FromResult(new ContentSearchResult([], 0, 0, false, Bounds(0), "rev-1"));

        public Task<InteractionResult> InteractionAsync(string nodeId, int maxMessages, CancellationToken ct) =>
            Task.FromResult(new InteractionResult(nodeId, [], false, Bounds(0), "rev-1"));

        public Task<KnowledgeResult> KnowledgeAsync(string? term, string? type, int maxResults, CancellationToken ct) =>
            Task.FromResult(new KnowledgeResult([], Bounds(0), "rev-1"));

        public Task<NodeContent> NodeContentAsync(string nodeId, CancellationToken ct) =>
            Task.FromResult(new NodeContent(nodeId, NodeContentKind.None, null, string.Empty, "stub"));

        private static DescribeResult Empty(string nodeId) =>
            new(new NodeView(nodeId, "source", nodeId), [], Bounds(0), "rev-1");

        internal static ResultBounds Bounds(int omittedEdges) =>
            new(100, 100, 100_000, 1, 0, 0, omittedEdges, false, null);

        public Task<EvidencePage> EvidenceAsync(string? cursor, int maxAssertions, CancellationToken ct) =>
            Task.FromResult(new EvidencePage([], null, "rev-1"));


        public WorkspaceGraph Graph { get; set; } = new([], [], 0, [], "rev-1");

        public Task<PathResult> PathsAsync(PathQuery query, CancellationToken ct) =>
            Task.FromResult(new PathResult([], false, null, "rev-1"));

        public Task<WorkspaceOverview> OverviewAsync(OverviewQuery query, CancellationToken ct) =>
            throw new NotSupportedException();

        public Task<SolutionTreeResult> SolutionTreeAsync(SolutionTreeQuery query, CancellationToken ct) =>
            throw new NotSupportedException();

        public Task<EntryPointsResult> EntryPointsAsync(EntryPointsQuery query, CancellationToken ct) =>
            throw new NotSupportedException();

        /// <summary>Every <see cref="GraphQuery"/> this stub has received, in order — the recording
        /// half of US-C8's oracle ("a recording FakeWorkspaceQueries sees the kind filter … on every
        /// GraphQuery it receives").</summary>
        public List<GraphQuery> ReceivedQueries { get; } = [];

        public Task<WorkspaceGraph> GraphAsync(GraphQuery query, CancellationToken ct)
        {
            ReceivedQueries.Add(query);
            return Throw is not null ? Task.FromException<WorkspaceGraph>(Throw) : Task.FromResult(Graph);
        }
    }

    private static EdgeView Edge(string subject, string predicate, string obj) =>
        new(subject, predicate, obj, VerificationStatus.Verified, EvidenceOrigin.Static, "rev-1",
            new Provenance("Orders.cs", "1:1", "csharp-extractor", "1.0.0", DateTimeOffset.UtcNow));

    [Fact]
    public async Task WithNoWorkspace_ItSaysSo_RatherThanRenderingAnEmptyGraph()
    {
        var graph = await new CanvasGraphViewModel(null).LoadAsync();

        Assert.Empty(graph.Nodes);
        Assert.Contains("No workspace", graph.Message, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public async Task WithNothingIndexed_ItNamesTheCommandThatWouldFixIt()
    {
        // Three different empty states exist and they need three different next actions. "Nothing
        // indexed" is the one the user can act on immediately.
        var graph = await new CanvasGraphViewModel(new StubQueries()).LoadAsync();

        Assert.Empty(graph.Nodes);
        Assert.Contains("Index C# projects", graph.Message, StringComparison.Ordinal);
    }

    [Fact]
    public async Task ItRendersTheNeighbourhoodOfACHOSENNode()
    {
        var queries = new StubQueries();
        queries.Matches.Add(new FindMatch("Shop.Order", "source", "Order", AuthorshipOrigin.RepositoryArtifact));
        queries.Describe = new DescribeResult(
            new NodeView("Shop.Order", "source", "Order"),
            [Edge("Shop.Order", "depends_on", "Shop.Customer"), Edge("Shop.Ledger", "depends_on", "Shop.Order")],
            StubQueries.Bounds(0), "rev-1");

        // A ROOT is now required for the neighbourhood view. Without one this returns the whole
        // graph, which is what the surface should have been showing all along — it asked for one
        // node and drew two of two thousand.
        var graph = await new CanvasGraphViewModel(queries).LoadAsync("Shop.Order");

        Assert.Equal("Shop.Order", graph.RootId);
        Assert.Equal(3, graph.Nodes.Count);
        Assert.Contains(graph.Nodes, n => n.Id == "Shop.Customer");

        // The edge that points AT the root counts too — a graph that only followed outgoing edges
        // would hide every caller.
        Assert.Contains(graph.Nodes, n => n.Id == "Shop.Ledger");
        Assert.Single(graph.Nodes, n => n.IsRoot);
    }

    [Fact]
    public async Task WithNoRootItLoadsTheWHOLEGraph()
    {
        // The reported defect, as an assertion. It asked FindAsync for ONE node and drew that node's
        // neighbours, so a workspace of 2,164 nodes rendered as two — the alphabetically first
        // symbol and its single neighbour. A root is a drill-down; the default is the graph.
        var queries = new StubQueries
        {
            Graph = new WorkspaceGraph(
                [
                    new GraphNode("Shop.Order", "Order", "class", 2, IsExternal: false),
                    new GraphNode("Shop.Customer", "Customer", "class", 1, IsExternal: false),
                    new GraphNode("string", "string", "external", 1, IsExternal: true),
                ],
                [
                    new GraphEdge("Shop.Order", "Shop.Customer", "depends_on", VerificationStatus.Verified),
                    new GraphEdge("Shop.Order", "string", "depends_on", VerificationStatus.Verified),
                ],
                Omitted: 5,
                ["packages-not-restored"],
                "rev-1"),
        };

        var graph = await new CanvasGraphViewModel(queries).LoadAsync();

        Assert.Equal(3, graph.Nodes.Count);
        Assert.Equal(2, graph.Edges.Count);
        Assert.Null(graph.RootId);

        // A bounded graph must not read as a complete small one.
        Assert.Equal(5, graph.Omitted);
        Assert.Contains("not drawn", graph.Message!, StringComparison.OrdinalIgnoreCase);
        Assert.Contains("packages-not-restored", graph.Disclosures);
    }

    [Fact]
    public async Task WholeGraph_CarriesTheIsKnowledgeFlag_SoTheChipDoesNotSpellTheKind()
    {
        // INV knowledge-chip-reads-zero-again / DC-042: the App categorised the Knowledge chip by
        // spelling the fine `kind` and dropped the authoritative IsKnowledge flag here. A knowledge
        // document whose kind is "spec" (or a repo-invented kind) must still reach the client AS
        // knowledge — the flag, not the spelling, is the answer.
        var queries = new StubQueries
        {
            Graph = new WorkspaceGraph(
                [
                    new GraphNode("Shop.Order", "Order", "class", 2, IsExternal: false),
                    new GraphNode("docs/spec.md", "spec.md", "spec", 1, IsExternal: false, IsKnowledge: true),
                ],
                [
                    new GraphEdge("Shop.Order", "docs/spec.md", "documents", VerificationStatus.Verified),
                ],
                Omitted: 0,
                [],
                "rev-1"),
        };

        var graph = await new CanvasGraphViewModel(queries).LoadAsync();

        var knowledge = graph.Nodes.Single(n => n.Id == "docs/spec.md");
        Assert.True(knowledge.IsKnowledge, "the knowledge node must carry IsKnowledge to the client");
        var code = graph.Nodes.Single(n => n.Id == "Shop.Order");
        Assert.False(code.IsKnowledge, "a code node must not be flagged knowledge");
    }

    [Fact]
    public async Task DisclosuresAreLiftedOutOfTheGraph_AndReportedSeparately()
    {
        // They arrive as ordinary facts because that is how the extractor records them, but a
        // "discloses" arrow to a node called "packages-not-restored" is noise on a canvas.
        var queries = new StubQueries();
        queries.Matches.Add(new FindMatch("scope:csharp:A:net10.0", "source", "scope", AuthorshipOrigin.RepositoryArtifact));
        queries.Describe = new DescribeResult(
            new NodeView("scope:csharp:A:net10.0", "source", "scope"),
            [
                Edge("scope:csharp:A:net10.0", "discloses", "packages-not-restored"),
                Edge("scope:csharp:A:net10.0", "discloses", "generated-code-not-analysed"),
            ],
            StubQueries.Bounds(0), "rev-1");

        var graph = await new CanvasGraphViewModel(queries).LoadAsync("scope:csharp:A:net10.0");

        Assert.Empty(graph.Edges);
        Assert.Equal(["generated-code-not-analysed", "packages-not-restored"], graph.Disclosures);
        Assert.DoesNotContain(graph.Nodes, n => n.Id == "packages-not-restored");
    }

    [Fact]
    public async Task ATruncatedResultCarriesItsOmittedCount()
    {
        var queries = new StubQueries();
        queries.Matches.Add(new FindMatch("Shop.Order", "source", "Order", AuthorshipOrigin.RepositoryArtifact));
        queries.Describe = new DescribeResult(
            new NodeView("Shop.Order", "source", "Order"),
            [Edge("Shop.Order", "depends_on", "Shop.Customer")],
            StubQueries.Bounds(omittedEdges: 37), "rev-1");

        var graph = await new CanvasGraphViewModel(queries).LoadAsync("Shop.Order");

        // Without this a bounded graph is indistinguishable from a small one.
        Assert.Equal(37, graph.Omitted);
    }

    [Fact]
    public async Task ANodeWithNoRelationshipsSaysThat_RatherThanRenderingBlank()
    {
        var queries = new StubQueries();
        queries.Matches.Add(new FindMatch("Shop.Loner", "source", "Loner", AuthorshipOrigin.RepositoryArtifact));

        var graph = await new CanvasGraphViewModel(queries).LoadAsync("Shop.Loner");

        Assert.Single(graph.Nodes);
        Assert.Contains("no recorded relationships", graph.Message, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public async Task AFailingWorkspaceReportsTheFailure_AndDoesNotThrowIntoTheShell()
    {
        // The canvas is one pane; a workspace that cannot answer must not take the shell down, and
        // an empty graph would read as "there is nothing here".
        var queries = new StubQueries { Throw = new InvalidOperationException("pipe closed") };

        var graph = await new CanvasGraphViewModel(queries).LoadAsync("Shop.Order");

        Assert.Empty(graph.Nodes);
        Assert.Contains("could not be loaded", graph.Message, StringComparison.OrdinalIgnoreCase);
        Assert.Contains("pipe closed", graph.Message, StringComparison.Ordinal);
    }

    [Fact]
    public async Task AnExplicitRootIsUsedWithoutSearching()
    {
        var queries = new StubQueries();
        queries.Matches.Add(new FindMatch("Shop.NotThisOne", "source", "x", AuthorshipOrigin.RepositoryArtifact));

        await new CanvasGraphViewModel(queries).LoadAsync("Shop.Chosen");

        Assert.Equal("Shop.Chosen", queries.LastDescribedNode);
    }

    [Fact]
    public async Task GroupAsync_LoadsAGroupsMembers_RootedOnTheGroupSoBackStaysLive()
    {
        // Drilling from a semantic-zoom super-node to the nodes it stands for. The projection filters
        // by GraphQuery.GroupId; here the stub returns the members, and the view is ROOTED on the group
        // id so the canvas keeps Back/Overview enabled rather than stranding the reader inside it.
        var queries = new StubQueries
        {
            Graph = new WorkspaceGraph(
                [
                    new GraphNode("Shop.Order", "Order", "class", 1, IsExternal: false),
                    new GraphNode("Shop.Customer", "Customer", "class", 1, IsExternal: false),
                ],
                [new GraphEdge("Shop.Order", "Shop.Customer", "depends_on", VerificationStatus.Verified)],
                Omitted: 0,
                [],
                "rev-1"),
        };

        var graph = await new CanvasGraphViewModel(queries).GroupAsync("Shop");

        Assert.Equal(2, graph.Nodes.Count);
        Assert.Equal("Shop", graph.RootId);
        Assert.Contains("member(s) of Shop", graph.Message);
    }

    [Fact]
    public async Task GroupAsync_WithNoGroupId_FallsBackToTheWholeGraph()
    {
        var queries = new StubQueries
        {
            Graph = new WorkspaceGraph(
                [new GraphNode("Shop.Order", "Order", "class", 1, IsExternal: false)],
                [],
                Omitted: 0,
                [],
                "rev-1"),
        };

        var graph = await new CanvasGraphViewModel(queries).GroupAsync("  ");

        // The whole-graph fallback is rooted on null, not on a group.
        Assert.Null(graph.RootId);
        Assert.Single(graph.Nodes);
    }

    /// <summary>
    /// US-C8's oracle: "a recording FakeWorkspaceQueries sees the kind filter code · data ·
    /// architecture on every GraphQuery it receives (headless), and no second graph store exists"
    /// (Ruling 53). Excluding knowledge — a declared flag, never an allow-list of kind spellings
    /// (see <see cref="GraphQuery.ExcludeKnowledge"/>) — IS "code, data and architecture": every
    /// node that is not knowledge already falls in one of those three.
    /// </summary>
    [Fact]
    public async Task WithExcludeKnowledgeSet_EveryGraphQueryIssued_CarriesTheFilter()
    {
        var queries = new StubQueries
        {
            Graph = new WorkspaceGraph(
                [new GraphNode("Shop.Order", "Order", "class", 1, IsExternal: false)], [], 0, [], "rev-1"),
        };
        var vm = new CanvasGraphViewModel(queries) { ExcludeKnowledge = true };

        await vm.LoadAsync();               // WholeGraphAsync's GraphQuery
        await vm.GroupAsync("Shop");         // GroupAsync's GraphQuery

        Assert.Equal(2, queries.ReceivedQueries.Count);
        Assert.All(queries.ReceivedQueries, q => Assert.True(q.ExcludeKnowledge));

        // No second store: one IWorkspaceQueries, one GraphQuery shape — a parameter, not a new type.
        Assert.IsType<GraphQuery>(queries.ReceivedQueries[0]);
    }

    [Fact]
    public async Task WithExcludeKnowledgeUnset_TheDefaultDrawsEveryKind()
    {
        // The Explorer's own canvas instance (CreateExplorerGraph) never sets this — Explore reads
        // every kind, knowledge included (Ruling 53: Explore is unchanged).
        var queries = new StubQueries
        {
            Graph = new WorkspaceGraph(
                [new GraphNode("Shop.Order", "Order", "class", 1, IsExternal: false)], [], 0, [], "rev-1"),
        };

        await new CanvasGraphViewModel(queries).LoadAsync();

        Assert.False(Assert.Single(queries.ReceivedQueries).ExcludeKnowledge);
    }
}
