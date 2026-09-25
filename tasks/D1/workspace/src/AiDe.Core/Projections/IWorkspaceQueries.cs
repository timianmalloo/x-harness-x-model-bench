namespace AiDe.Core.Projections;

/// <summary>
/// The workspace's read surface, however it is reached.
/// </summary>
/// <remarks>
/// <para><b>This seam exists so the shell does not know whether the core is in this process.</b>
/// ADR-0009 keeps both hosting modes supported — in-process first, then a separate daemon — and a
/// UI written against one of them is a UI that has to be rewritten to get the other. The whole
/// difference between the two is which implementation is handed in.</para>
///
/// <para><b>Asynchronous because the remote case is the real one.</b> A synchronous seam would force
/// every remote call to block a thread, and on a UI thread that is a frozen window for the length of
/// a pipe round trip. The in-process adapter completes immediately, which costs it nothing.</para>
///
/// <para><b>The result types are the core's own.</b> A parallel set of "view" types would be a second
/// definition of every result to keep in step, and the first divergence would show up as a field
/// present one way and missing the other.</para>
/// </remarks>
public interface IWorkspaceQueries
{
    Task<DescribeResult> DescribeAsync(string nodeId, int maxNeighbors, CancellationToken cancellationToken);

    Task<ImpactResult> ImpactAsync(string nodeId, int maxNodes, int maxEdges, CancellationToken cancellationToken);

    Task<FindResult> FindAsync(string term, int maxResults, CancellationToken cancellationToken);

    /// <summary>
    /// Lines in the workspace's own files that contain a term.
    /// </summary>
    /// <remarks>
    /// The App must not read workspace files: two authorities on what a file contains disagree the
    /// first time one resolves a path differently (DC-022), and file access belongs on the side of
    /// the boundary that can confine it to the workspace. Same rule that put NodeContentAsync here,
    /// applied to the corpus rather than to one node.
    /// </remarks>
    Task<ContentSearchResult> SearchContentAsync(string term, int maxMatches, CancellationToken cancellationToken);

    /// <summary>
    /// One caller's outgoing calls, in the order they are written — a UML sequence diagram's feed.
    /// </summary>
    /// <remarks>
    /// Not <c>calls</c>: those edges are deduplicated to one per pair, which is right for a graph
    /// and destroys an interaction, because a repeated call collapses and the message is lost.
    /// Type-level — the caller and callee are types and the member is the message name.
    /// </remarks>
    Task<InteractionResult> InteractionAsync(string nodeId, int maxMessages, CancellationToken cancellationToken);

    Task<KnowledgeResult> KnowledgeAsync(string? term, string? type, int maxResults, CancellationToken cancellationToken);

    /// <summary>
    /// The content behind one node — source, prose, or nothing, as the authority sees it.
    /// </summary>
    /// <remarks>
    /// ADR-0018 node-content-reader-contract. Fetched for the ONE node a reader selected, because the graph deliberately carries
    /// no content: paying for 1,500 nodes to serve one is what overflowed the frame (INV-0003). The
    /// client does not read files — two authorities on what a node contains would disagree the first
    /// time one resolved a path differently (DC-022), and file access belongs on the side of the
    /// boundary that can confine it to the workspace.
    /// </remarks>
    Task<NodeContent> NodeContentAsync(string nodeId, CancellationToken cancellationToken);

    /// <summary>
    /// One page of every current assertion.
    /// </summary>
    /// <remarks>
    /// The question the evidence panes are actually asking. They were rebuilding this set node by
    /// node through <c>Describe</c>, which bounds neighbours at 50 and lost two join edges of 124
    /// doing it — and which asks the store for a graph walk when what is wanted is a table scan.
    /// </remarks>
    Task<EvidencePage> EvidenceAsync(string? cursor, int maxAssertions, CancellationToken cancellationToken);

    /// <summary>
    /// The workspace as a graph — all of it, or the part the query names.
    /// </summary>
    /// <remarks>
    /// <para>Distinct from <see cref="DescribeAsync"/>, which answers "what is around THIS node".
    /// The graph surface asked the neighbourhood question and rendered two nodes of two thousand.</para>
    ///
    /// <para>The query carries the filter because filtering has to happen before the CAP. A caller
    /// that fetches everything and then keeps the classes has already let the cap rank and trim a
    /// graph it did not want, and nothing in the result would say so.</para>
    /// </remarks>
    Task<WorkspaceGraph> GraphAsync(GraphQuery query, CancellationToken cancellationToken);

    /// <summary>
    /// How one node reaches another.
    /// </summary>
    /// <remarks>
    /// Distinct from <see cref="ImpactAsync"/>, which answers "what does changing this touch". This
    /// answers "through WHAT does it touch it" — the route, which is the part a reviewer needs and
    /// the part a neighbourhood cannot show.
    /// </remarks>
    Task<PathResult> PathsAsync(PathQuery query, CancellationToken cancellationToken);

    /// <summary>
    /// The workspace as groups rather than nodes.
    /// </summary>
    /// <remarks>
    /// The entry point for a repository too large to draw node by node. <see cref="GraphAsync"/>
    /// bounded the payload by truncating and saying so, which is honest and is still a truncation;
    /// this answers "what shape is this repository" instead of "here are 1,500 of its 2,118 dots".
    /// </remarks>
    Task<WorkspaceOverview> OverviewAsync(OverviewQuery query, CancellationToken cancellationToken);

    /// <summary>
    /// The workspace as a census join: folders Core observed on disk, plus indexed file-artifacts.
    /// </summary>
    /// <remarks>
    /// Distinct from <see cref="OverviewAsync"/> (identifier-prefix clusters) and
    /// <see cref="GraphAsync"/> (graph nodes with no path). Census is daemon-side so the App never
    /// walks the workspace (DC-022). Query carries two integer caps only; a named drop-set is not
    /// on this seam.
    /// </remarks>
    Task<SolutionTreeResult> SolutionTreeAsync(SolutionTreeQuery query, CancellationToken cancellationToken);

    /// <summary>
    /// Indexed entry-point candidates (API/UX/CLI/unclassified). UV-0 lists <c>has_type</c> nodes as unclassified.
    /// </summary>
    Task<EntryPointsResult> EntryPointsAsync(EntryPointsQuery query, CancellationToken cancellationToken);
}

/// <summary>The read surface answered by a <see cref="ProjectionService"/> in this process.</summary>
/// <remarks>
/// Completed tasks rather than <c>Task.Run</c>: the projections are synchronous and fast, and moving
/// them to a thread pool thread would add a context switch and a scheduling hop to hide latency that
/// is not there.
/// </remarks>
public sealed class LocalWorkspaceQueries(ProjectionService projections) : IWorkspaceQueries
{
    public Task<DescribeResult> DescribeAsync(
        string nodeId, int maxNeighbors, CancellationToken cancellationToken) =>
        Task.FromResult(projections.Describe(nodeId, maxNeighbors));

    public Task<ImpactResult> ImpactAsync(
        string nodeId, int maxNodes, int maxEdges, CancellationToken cancellationToken) =>
        Task.FromResult(projections.Impact(nodeId, maxNodes, maxEdges));

    public Task<FindResult> FindAsync(
        string term, int maxResults, CancellationToken cancellationToken) =>
        Task.FromResult(projections.Find(term, maxResults));

    public Task<ContentSearchResult> SearchContentAsync(
        string term, int maxMatches, CancellationToken cancellationToken) =>
        Task.FromResult(projections.SearchContent(term, maxMatches));

    public Task<InteractionResult> InteractionAsync(
        string nodeId, int maxMessages, CancellationToken cancellationToken) =>
        Task.FromResult(projections.Interaction(nodeId, maxMessages));

    public Task<KnowledgeResult> KnowledgeAsync(
        string? term, string? type, int maxResults, CancellationToken cancellationToken) =>
        Task.FromResult(projections.Knowledge(new KnowledgeQuery(term, type, maxResults)));

    public Task<NodeContent> NodeContentAsync(string nodeId, CancellationToken cancellationToken) =>
        Task.FromResult(projections.NodeContent(nodeId));

    public Task<EvidencePage> EvidenceAsync(
        string? cursor, int maxAssertions, CancellationToken cancellationToken) =>
        Task.FromResult(projections.Evidence(cursor, maxAssertions));

    public Task<WorkspaceGraph> GraphAsync(GraphQuery query, CancellationToken cancellationToken) =>
        Task.FromResult(projections.Graph(query));

    public Task<PathResult> PathsAsync(PathQuery query, CancellationToken cancellationToken) =>
        Task.FromResult(projections.Paths(query));

    public Task<WorkspaceOverview> OverviewAsync(OverviewQuery query, CancellationToken cancellationToken) =>
        Task.FromResult(projections.Overview(query));

    public Task<SolutionTreeResult> SolutionTreeAsync(
        SolutionTreeQuery query, CancellationToken cancellationToken) =>
        Task.FromResult(projections.SolutionTree(query, cancellationToken));

    public Task<EntryPointsResult> EntryPointsAsync(
        EntryPointsQuery query, CancellationToken cancellationToken) =>
        Task.FromResult(projections.EntryPoints(query, cancellationToken));
}
