using System.Runtime.Versioning;
using System.Text.Json;
using AiDe.Core.Projections;
using AiDe.Core.Dispatch;
using AiDe.Core.Facts;

namespace AiDe.Core.Ipc;

/// <summary>
/// Raised when the daemon refuses a request, carrying the boundary's stable code.
/// </summary>
/// <remarks>
/// An exception rather than a nullable result because these are not outcomes a caller chooses
/// between — a stale epoch, a revoked capability and an unsupported version are all "this request
/// did not happen, and you must decide what to do about it". The code is on the exception so a
/// caller can decide without parsing prose.
/// </remarks>
public sealed class IpcRequestException(string code, string reason)
    : Exception($"{code}: {reason}")
{
    public string Code { get; } = code;
}

/// <summary>
/// The core's read surface, over the boundary, in the same shapes the in-process caller uses.
/// </summary>
/// <remarks>
/// <para><b>The result types are the core's own</b> — <see cref="DescribeResult"/> and its
/// siblings — rather than a parallel set of wire types. A second definition of one result is two
/// things to keep in step, and the first divergence would appear as a field that is present in
/// process and missing across the pipe.</para>
///
/// <para><b>The epoch is carried, not assumed.</b> Every request states which epoch it was authored
/// against, and the daemon rejects a mismatch. That is the fence that stops a command reasoning
/// about state that has since been replaced, and a client that quietly resent the daemon's current
/// epoch would defeat it while appearing to work.</para>
/// </remarks>
[SupportedOSPlatform("windows")]
public sealed class WorkspaceClient : IWorkspaceQueries, IWorkspaceCommands, IWorkspaceDispatch, IAsyncDisposable
{
    private readonly IpcClient _client;
    private readonly string _workspaceId;
    private long _epoch;

    private WorkspaceClient(IpcClient client, string workspaceId, long epoch)
    {
        _client = client;
        _workspaceId = workspaceId;
        _epoch = epoch;
    }

    /// <summary>The epoch this client is bound to.</summary>
    public long Epoch => _epoch;

    /// <summary>Connects, handshakes, and returns a client ready to query.</summary>
    /// <remarks>
    /// The epoch comes from the handshake rather than from the caller: the daemon owns the store and
    /// is the only party that knows it. A caller-supplied epoch would be a guess, and the fence
    /// exists precisely to catch guesses.
    /// </remarks>
    public static async Task<WorkspaceClient> ConnectAsync(
        string pipeName, TimeSpan timeout, CancellationToken cancellationToken)
    {
        var client = await IpcClient.ConnectAsync(pipeName, timeout, cancellationToken).ConfigureAwait(false);

        try
        {
            // Epoch 0 on the handshake because the handshake is the ONE exchange not judged
            // against the fence — a shell that has never spoken to this daemon has no way to know
            // the epoch, so it learns it here and states it on everything after.
            var opened = await client.OpenWorkspaceAsync(pipeName, 0, cancellationToken).ConfigureAwait(false);
            Throw(opened);

            return new WorkspaceClient(client, pipeName, client.Epoch);
        }
        catch
        {
            await client.DisposeAsync().ConfigureAwait(false);
            throw;
        }
    }

    public Task<DescribeResult> DescribeAsync(
        string nodeId, int maxNeighbors, CancellationToken cancellationToken) =>
        QueryAsync<DescribeResult>(
            WorkspaceOperations.Describe, new DescribeRequest(nodeId, maxNeighbors), cancellationToken);

    public Task<ImpactResult> ImpactAsync(
        string nodeId, int maxNodes, int maxEdges, CancellationToken cancellationToken) =>
        QueryAsync<ImpactResult>(
            WorkspaceOperations.Impact, new ImpactRequest(nodeId, maxNodes, maxEdges), cancellationToken);

    /// <summary>Phase 1 of a dispatch, answered by the daemon that owns the store.</summary>
    public Task<DispatchBeginResult> DispatchBeginAsync(
        DispatchCommand command, CancellationToken cancellationToken) =>
        QueryAsync<DispatchBeginResult>(
            WorkspaceOperations.DispatchBegin, new DispatchBeginRequest(command), cancellationToken);

    /// <summary>Phase 2 of a dispatch. Idempotent: a retried finalize returns the existing receipt.</summary>
    public Task<DispatchReceipt> DispatchFinalizeAsync(
        string dispatchKey, DispatchState state, string? errorCode, CancellationToken cancellationToken) =>
        QueryAsync<DispatchReceipt>(
            WorkspaceOperations.DispatchFinalize,
            new DispatchFinalizeRequest(dispatchKey, state, errorCode), cancellationToken);

    /// <summary>What re-indexing has cost in this daemon so far.</summary>
    /// <remarks>
    /// The measurement the sub-scope-incrementality decision is blocked on: whether a re-index is an
    /// occasional cost a user asks for, or something they wait on constantly.
    /// </remarks>
    public Task<RefreshMetrics> RefreshMetricsAsync(CancellationToken cancellationToken) =>
        QueryAsync<RefreshMetrics>(
            ScopeRefreshService.Operations.RefreshMetrics, new RefreshMetricsRequest(), cancellationToken);

    public Task<WorkspaceOverview> OverviewAsync(OverviewQuery query, CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(query);

        var graph = query.Query ?? new GraphQuery(IncludeExternal: false);

        return QueryAsync<WorkspaceOverview>(
            WorkspaceOperations.Overview,
            new OverviewRequest(
                query.Depth, query.MaxClusters, graph.Kinds, graph.ScopeId, graph.IncludeExternal),
            cancellationToken);
    }

    public Task<PathResult> PathsAsync(PathQuery query, CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(query);

        var graph = query.Query ?? new GraphQuery();

        return QueryAsync<PathResult>(
            WorkspaceOperations.Paths,
            new PathsRequest(
                query.From, query.To, query.MaxPaths, query.MaxLength,
                graph.Kinds, graph.ScopeId, graph.IncludeExternal),
            cancellationToken);
    }

    public Task<WorkspaceGraph> GraphAsync(GraphQuery query, CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(query);

        return QueryAsync<WorkspaceGraph>(
            WorkspaceOperations.Graph,
            new GraphRequest(
                query.MaxNodes, query.Kinds, query.ScopeId, query.IncludeExternal, query.GroupId,
                query.ExcludeKnowledge),
            cancellationToken);
    }

    public Task<EvidencePage> EvidenceAsync(
        string? cursor, int maxAssertions, CancellationToken cancellationToken) =>
        QueryAsync<EvidencePage>(
            WorkspaceOperations.Evidence, new EvidenceRequest(cursor, maxAssertions), cancellationToken);

    public Task<FindResult> FindAsync(string term, int maxResults, CancellationToken cancellationToken) =>
        QueryAsync<FindResult>(
            WorkspaceOperations.Find, new FindRequest(term, maxResults), cancellationToken);

    public Task<ContentSearchResult> SearchContentAsync(
        string term, int maxMatches, CancellationToken cancellationToken) =>
        QueryAsync<ContentSearchResult>(
            WorkspaceOperations.SearchContent,
            new SearchContentRequest(term, maxMatches), cancellationToken);

    public Task<InteractionResult> InteractionAsync(
        string nodeId, int maxMessages, CancellationToken cancellationToken) =>
        QueryAsync<InteractionResult>(
            WorkspaceOperations.Interaction,
            new InteractionRequest(nodeId, maxMessages), cancellationToken);

    public Task<KnowledgeResult> KnowledgeAsync(
        string? term, string? type, int maxResults, CancellationToken cancellationToken) =>
        QueryAsync<KnowledgeResult>(
            WorkspaceOperations.Knowledge, new KnowledgeRequest(term, type, maxResults), cancellationToken);

    public Task<NodeContent> NodeContentAsync(string nodeId, CancellationToken cancellationToken) =>
        QueryAsync<NodeContent>(
            WorkspaceOperations.NodeContent, new NodeContentRequest(nodeId), cancellationToken);

    public Task<SolutionTreeResult> SolutionTreeAsync(
        SolutionTreeQuery query, CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(query);
        return QueryAsync<SolutionTreeResult>(
            WorkspaceOperations.SolutionTree, query, cancellationToken);
    }

    public Task<EntryPointsResult> EntryPointsAsync(
        EntryPointsQuery query, CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(query);
        return QueryAsync<EntryPointsResult>(
            WorkspaceOperations.EntryPoints, query, cancellationToken);
    }

    /// <summary>
    /// Asks the daemon to re-index a scope, and waits for it to finish.
    /// </summary>
    /// <remarks>
    /// <para><b>Start-then-poll, because the wire cannot hold a 60-second operation.</b> The lane
    /// serves one request at a time per connection, so a refresh that answered only on completion
    /// would occupy that connection for the whole budget — and the daemon's response-write timeout
    /// would abandon it first.</para>
    ///
    /// <para><b>One command id for the whole exchange.</b> It is the idempotency key: if the start
    /// reply is lost and the caller retries, the daemon returns the job it already has rather than
    /// extracting the scope twice.</para>
    /// </remarks>
    public async Task<ScopeRefreshStatus> RefreshScopeAsync(
        string scopeId, string artifactRevision, CancellationToken cancellationToken)
    {
        var commandId = Guid.NewGuid().ToString("N");

        var status = await QueryAsync<ScopeRefreshStatus>(
            ScopeRefreshService.Operations.Refresh,
            new RefreshRequest(scopeId, artifactRevision),
            cancellationToken,
            commandId).ConfigureAwait(false);

        while (status.State == ScopeRefreshState.Running)
        {
            cancellationToken.ThrowIfCancellationRequested();
            await Task.Delay(TimeSpan.FromMilliseconds(150), cancellationToken).ConfigureAwait(false);

            status = await QueryAsync<ScopeRefreshStatus>(
                ScopeRefreshService.Operations.RefreshStatus,
                new RefreshStatusRequest(commandId),
                cancellationToken).ConfigureAwait(false);
        }

        return status;
    }

    /// <summary>Re-reads the daemon's epoch, for a caller recovering from a stale-epoch rejection.</summary>
    /// <inheritdoc />
    public Task<IndexSummary> IndexSolutionAsync(
        string artifactRevision, CancellationToken cancellationToken, bool force = false) =>
        QueryAsync<IndexSummary>(
            WorkspaceOperations.IndexSolution, new IndexSolutionRequest(artifactRevision, force), cancellationToken);

    /// <inheritdoc />
    public Task<long> EpochAsync(CancellationToken cancellationToken) => RefreshEpochAsync(cancellationToken);

    public async Task<long> RefreshEpochAsync(CancellationToken cancellationToken)
    {
        var response = await _client
            .InvokeAsync(DaemonOperations.Epoch, Guid.NewGuid().ToString("N"), _workspaceId, _epoch, null, cancellationToken)
            .ConfigureAwait(false);

        Throw(response);
        _epoch = IpcPayload.Read<long>(response.Payload, WorkspaceOperations.Wire);
        return _epoch;
    }

    private async Task<TResult> QueryAsync<TResult>(
        string operation, object payload, CancellationToken cancellationToken, string? commandId = null)
    {
        var response = await _client.InvokeAsync(
            operation,
            commandId ?? Guid.NewGuid().ToString("N"),
            _workspaceId,
            _epoch,
            IpcPayload.From(payload, WorkspaceOperations.Wire),
            cancellationToken).ConfigureAwait(false);

        Throw(response);

        return IpcPayload.Read<TResult>(response.Payload, WorkspaceOperations.Wire)
            ?? throw new IpcRequestException(
                IpcErrorCodes.MalformedEnvelope, $"the daemon returned no result for '{operation}'");
    }

    private static void Throw(IpcResponse response)
    {
        if (!response.Ok)
        {
            throw new IpcRequestException(response.ErrorCode!, response.Reason!);
        }
    }

    public ValueTask DisposeAsync() => _client.DisposeAsync();
}
