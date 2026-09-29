using AiDe.Core.Projections;

namespace AiDe.Testing;

/// <summary>
/// A read surface that refuses everything, so a test can implement only what it exercises.
/// </summary>
/// <remarks>
/// <para><b>Written after the fourth round of identical churn, not in anticipation of it.</b> Every
/// method added to <see cref="IWorkspaceQueries"/> — <c>EvidenceAsync</c>, <c>GraphAsync</c>,
/// <c>PathsAsync</c>, <c>OverviewAsync</c> — broke four hand-written stubs across two test projects,
/// each needing the same one-line addition. That is a measured recurrence rather than a predicted
/// one, which is what makes the abstraction earned here and speculative before.</para>
///
/// <para><b>Shared as LINKED SOURCE, not as a project.</b> Two test projects need it and a whole
/// assembly for forty lines is more machinery than the problem. The link is visible in both
/// <c>.csproj</c> files, which is the trade: slightly surprising to find the same file compiled
/// twice, against a project nobody would otherwise have.</para>
///
/// <para><b>It throws rather than returning empty.</b> A stub that quietly answers a question the
/// test did not intend to ask turns a wrong call site into a passing test — the shape of every
/// "clean empty success" defect in this codebase. A test that reaches an unimplemented member should
/// fail loudly and name the member.</para>
/// </remarks>
public abstract class FakeWorkspaceQueries : IWorkspaceQueries
{
    public virtual Task<DescribeResult> DescribeAsync(
        string nodeId, int maxNeighbors, CancellationToken cancellationToken) => Refuse<DescribeResult>();

    public virtual Task<ImpactResult> ImpactAsync(
        string nodeId, int maxNodes, int maxEdges, CancellationToken cancellationToken) => Refuse<ImpactResult>();

    public virtual Task<FindResult> FindAsync(
        string term, int maxResults, CancellationToken cancellationToken) => Refuse<FindResult>();

    public virtual Task<ContentSearchResult> SearchContentAsync(
        string term, int maxMatches, CancellationToken cancellationToken) => Refuse<ContentSearchResult>();

    public virtual Task<InteractionResult> InteractionAsync(
        string nodeId, int maxMessages, CancellationToken cancellationToken) =>
        Refuse<InteractionResult>();

    public virtual Task<KnowledgeResult> KnowledgeAsync(
        string? term, string? type, int maxResults, CancellationToken cancellationToken) => Refuse<KnowledgeResult>();

    public virtual Task<NodeContent> NodeContentAsync(string nodeId, CancellationToken cancellationToken) =>
        Refuse<NodeContent>();

    public virtual Task<EvidencePage> EvidenceAsync(
        string? cursor, int maxAssertions, CancellationToken cancellationToken) => Refuse<EvidencePage>();

    public virtual Task<WorkspaceGraph> GraphAsync(
        GraphQuery query, CancellationToken cancellationToken) => Refuse<WorkspaceGraph>();

    public virtual Task<PathResult> PathsAsync(
        PathQuery query, CancellationToken cancellationToken) => Refuse<PathResult>();

    public virtual Task<WorkspaceOverview> OverviewAsync(
        OverviewQuery query, CancellationToken cancellationToken) => Refuse<WorkspaceOverview>();

    public virtual Task<SolutionTreeResult> SolutionTreeAsync(
        SolutionTreeQuery query, CancellationToken cancellationToken) => Refuse<SolutionTreeResult>();

    public virtual Task<EntryPointsResult> EntryPointsAsync(
        EntryPointsQuery query, CancellationToken cancellationToken) => Refuse<EntryPointsResult>();

    private static Task<T> Refuse<T>([System.Runtime.CompilerServices.CallerMemberName] string member = "") =>
        throw new NotSupportedException(
            $"this test's double does not implement {member} — it was not expected to be called");
}
