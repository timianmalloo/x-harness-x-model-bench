using System.Text.Json;
using System.Text.Json.Serialization;
using AiDe.Core.Projections;
using AiDe.Core.Dispatch;
using AiDe.Core.Facts;
using AiDe.Core.Store;

namespace AiDe.Core.Ipc;

/// <summary>The four read projections, as they travel across the boundary.</summary>
/// <remarks>
/// Explicit request records rather than loose strings: the operation name and its arguments arrive
/// as one payload from a process we do not control, and a positional or free-form encoding would
/// have to be validated by hand at every call site.
/// </remarks>
public sealed record DescribeRequest(string NodeId, int MaxNeighbors);

/// <inheritdoc cref="DescribeRequest"/>
public sealed record ImpactRequest(string NodeId, int MaxNodes, int MaxEdges);

/// <inheritdoc cref="DescribeRequest"/>
public sealed record FindRequest(string Term, int MaxResults);

/// <summary>Ask for lines of workspace files containing a term.</summary>
public sealed record SearchContentRequest(string Term, int MaxMatches);

/// <summary>Ask for one caller's outgoing calls in order.</summary>
public sealed record InteractionRequest(string NodeId, int MaxMessages);

/// <summary>Asks for one page of every current assertion.</summary>
/// <param name="Cursor">Null for the first page; otherwise the previous page's NextCursor.</param>
public sealed record EvidenceRequest(string? Cursor, int MaxAssertions);

/// <summary>Asks for the workspace as groups rather than nodes.</summary>
public sealed record OverviewRequest(
    int Depth = 3,
    int MaxClusters = 60,
    IReadOnlyList<string>? Kinds = null,
    string? ScopeId = null,
    bool IncludeExternal = false);

/// <summary>Asks how one node reaches another.</summary>
public sealed record PathsRequest(
    string From,
    string To,
    int MaxPaths = 10,
    int MaxLength = 8,
    IReadOnlyList<string>? Kinds = null,
    string? ScopeId = null,
    bool IncludeExternal = true);

/// <summary>Asks for the graph — all of it, or the part the filters name.</summary>
public sealed record GraphRequest(
    int MaxNodes,
    IReadOnlyList<string>? Kinds = null,
    string? ScopeId = null,
    bool IncludeExternal = true,
    string? GroupId = null,
    bool ExcludeKnowledge = false);

/// <inheritdoc cref="DescribeRequest"/>
public sealed record KnowledgeRequest(string? Term, string? Type, int MaxResults);

/// <summary>One node, for the reader that selected it (ADR-0018 node-content-reader-contract).</summary>
public sealed record NodeContentRequest(string NodeId);

/// <summary>Phase 1 of a dispatch: make the attempt durable before any byte leaves the shell.</summary>
public sealed record DispatchBeginRequest(DispatchCommand Command);

/// <summary>Phase 2 of a dispatch: record the outcome the shell observed.</summary>
public sealed record DispatchFinalizeRequest(string DispatchKey, DispatchState State, string? ErrorCode);

/// <summary>Index every C# scope in the workspace.</summary>
/// <param name="Force">
/// Re-extract every scope even when its inputs are unchanged.
/// </param>
/// <remarks>
/// Additive with a default, so a client built before this field still decodes and still means "use
/// the cache" — which is the safe reading of an absent flag. It exists because an operator must
/// always be able to say "I do not believe the cache", and until it was reachable that sentence had
/// no button behind it.
/// </remarks>
public sealed record IndexSolutionRequest(string ArtifactRevision, bool Force = false);

/// <summary>Operations every daemon answers, whatever workspace it serves.</summary>
/// <remarks>
/// Separate from the projections because they are about the <i>daemon</i> rather than the
/// workspace's contents: a shell needs them to establish that it is talking to a live peer and which
/// epoch its commands will be judged against, before it has anything to ask.
/// </remarks>
public static class DaemonOperations
{
    public const string Ping = "ping";
    public const string Epoch = "epoch";

    /// <summary>Registers them against a live epoch source.</summary>
    public static void Register(DaemonEndpoint endpoint, Func<long> epoch)
    {
        ArgumentNullException.ThrowIfNull(endpoint);
        ArgumentNullException.ThrowIfNull(epoch);

        endpoint.Register(Ping, (_, _) => IpcResponse.Success("pong", WorkspaceOperations.Wire));

        // Read at call time, not captured once: the epoch advances when the core is replaced, and a
        // snapshot taken at registration would hand every later caller a fence value that has since
        // stopped being true.
        endpoint.Register(Epoch, (_, _) => IpcResponse.Success(epoch(), WorkspaceOperations.Wire));
    }
}

/// <summary>
/// Puts the core's read surface behind the daemon endpoint.
/// </summary>
/// <remarks>
/// <para><b>This is what the process split was for.</b> Until now the boundary existed and almost
/// nothing crossed it: the daemon answered <c>ping</c> while the shell called the core in-process,
/// so the trust boundary was real and unused. Every day that persists, new code is written against
/// the in-process path and has to be moved later.</para>
///
/// <para><b>Read projections only, and that is the whole surface today.</b> Dispatch — writing to a
/// terminal, staging a prompt — carries the two-phase receipt semantics of ADR-0010, and moving it
/// across is a separate piece of work with its own failure modes. Naming that here is better than
/// registering a handler that half-implements it.</para>
///
/// <para><b>The projections are already bounded</b> (<see cref="ProjectionService"/> clamps every
/// limit and reports what it omitted), which is what makes them safe to expose to a caller who
/// chooses the numbers. Nothing here re-validates: doing so would create a second definition of the
/// bound, and two definitions of one quantity is a defect signature.</para>
/// </remarks>
public static class WorkspaceOperations
{
    public const string Describe = "describe";
    public const string Impact = "impact";
    public const string Find = "find";

    /// <summary>Lines in the workspace's own files that contain a term.</summary>
    /// <remarks>
    /// Separate from <see cref="Find"/> because it answers a different question and costs a
    /// different amount: Find reads the store, this opens files. A client should be able to offer
    /// the cheap one on every keystroke and the expensive one on demand.
    /// </remarks>
    public const string SearchContent = "search-content";

    /// <summary>One caller's outgoing calls, in call order — a sequence diagram's feed.</summary>
    public const string Interaction = "interaction";
    public const string Knowledge = "knowledge";

    /// <summary>One node's content, on demand (ADR-0018 node-content-reader-contract).</summary>
    public const string NodeContent = "nodeContent";
    public const string Evidence = "evidence";
    public const string Graph = "graph";

    public const string Paths = "paths";

    public const string Overview = "overview";

    /// <summary>Census join of disk-now folders and indexed file-artifacts (ADR-0038).</summary>
    public const string SolutionTree = "solution-tree";

    /// <summary>D-1 entry-point listing (unclassified until classifier exists).</summary>
    public const string EntryPoints = "entry-points";
    public const string DispatchBegin = "dispatch.begin";
    public const string DispatchFinalize = "dispatch.finalize";
    public const string IndexSolution = "index.solution";

    /// <summary>
    /// How every payload on this boundary is encoded.
    /// </summary>
    /// <remarks>
    /// <b>Enums travel as strings.</b> By number, adding a member in the middle of an enum silently
    /// renumbers the ones after it — and with a dual-major handshake designed so an old shell may
    /// meet a new daemon, that is a wire break with no error and no symptom except wrong answers.
    /// A name costs a few bytes and cannot be renumbered.
    /// </remarks>
    public static JsonSerializerOptions Wire { get; } = new(JsonSerializerDefaults.Web)
    {
        Converters = { new JsonStringEnumConverter() },
    };

    /// <summary>Registers the read projections on <paramref name="endpoint"/>.</summary>
    public static void Register(DaemonEndpoint endpoint, ProjectionService projections)
    {
        ArgumentNullException.ThrowIfNull(endpoint);
        ArgumentNullException.ThrowIfNull(projections);

        // Every operation goes through Refusable, including the reads. None of the projections
        // throws a domain refusal TODAY — the point is that if one is added that does, it is
        // refused rather than taking the daemon down for every attached shell (DC-020). A control
        // that covers only the operations that happened to need it is not a control for the shape.
        endpoint.Register(Overview, (request, _) =>
            Refusable(() => Handle<OverviewRequest>(request, body => projections.Overview(
                new OverviewQuery(
                    body.Depth, body.MaxClusters,
                    new GraphQuery(
                        GraphProjection.DefaultMaxNodes, body.Kinds, body.ScopeId, body.IncludeExternal))))));

        endpoint.Register(Paths, (request, _) =>
            Refusable(() => Handle<PathsRequest>(request, body => projections.Paths(
                new PathQuery(
                    body.From, body.To, body.MaxPaths, body.MaxLength,
                    new GraphQuery(
                        GraphProjection.DefaultMaxNodes, body.Kinds, body.ScopeId, body.IncludeExternal))))));

        endpoint.Register(Graph, (request, _) =>
            Refusable(() => Handle<GraphRequest>(request, body => projections.Graph(
                new GraphQuery(
                    body.MaxNodes, body.Kinds, body.ScopeId, body.IncludeExternal, body.GroupId,
                    ExcludeKnowledge: body.ExcludeKnowledge)))));

        // Reads a FILE, unlike every other operation here — which is exactly why it is on this side
        // of the boundary. The projection confines the path to the workspace root; a client that did
        // its own reading would answer to nothing (ADR-0018 node-content-reader-contract).
        endpoint.Register(NodeContent, (request, _) =>
            Refusable(() => Handle<NodeContentRequest>(request,
                body => projections.NodeContent(body.NodeId))));

        endpoint.Register(Evidence, (request, _) =>
            Refusable(() => Handle<EvidenceRequest>(request,
                body => projections.Evidence(body.Cursor, body.MaxAssertions))));

        endpoint.Register(Describe, (request, _) =>
            Refusable(() => Handle<DescribeRequest>(request, body => projections.Describe(body.NodeId, body.MaxNeighbors))));

        endpoint.Register(Impact, (request, _) =>
            Refusable(() => Handle<ImpactRequest>(request, body => projections.Impact(body.NodeId, body.MaxNodes, body.MaxEdges))));

        endpoint.Register(Find, (request, _) =>
            Refusable(() => Handle<FindRequest>(request, body => projections.Find(body.Term, body.MaxResults))));

        endpoint.Register(SearchContent, (request, _) =>
            Refusable(() => Handle<SearchContentRequest>(request, body =>
                projections.SearchContent(body.Term, body.MaxMatches))));

        endpoint.Register(Interaction, (request, _) =>
            Refusable(() => Handle<InteractionRequest>(request, body =>
                projections.Interaction(body.NodeId, body.MaxMessages))));

        endpoint.Register(Knowledge, (request, _) =>
            Refusable(() => Handle<KnowledgeRequest>(request, body =>
                projections.Knowledge(new KnowledgeQuery(body.Term, body.Type, body.MaxResults)))));

        endpoint.Register(SolutionTree, (request, _) =>
            Refusable(() => Handle<SolutionTreeQuery>(request, body =>
                projections.SolutionTree(body))));

        endpoint.Register(EntryPoints, (request, _) =>
            Refusable(() => Handle<EntryPointsQuery>(request, body =>
                projections.EntryPoints(body))));
    }

    /// <summary>
    /// Registers the two durable phases of prompt dispatch (ADR-0010) on <paramref name="endpoint"/>.
    /// </summary>
    /// <remarks>
    /// Separate from the projection registration because these are the first WRITES on the read
    /// endpoint, and because a daemon can legitimately serve projections without them.
    /// </remarks>
    public static void RegisterDispatch(DaemonEndpoint endpoint, BoundaryDispatcher dispatcher)
    {
        ArgumentNullException.ThrowIfNull(endpoint);
        ArgumentNullException.ThrowIfNull(dispatcher);

        endpoint.Register(DispatchBegin, (request, _) =>
            Refusable(() => Handle<DispatchBeginRequest>(request, body => dispatcher.Begin(body.Command))));

        endpoint.Register(DispatchFinalize, (request, _) =>
            Refusable(() => Handle<DispatchFinalizeRequest>(request, body =>
                dispatcher.Finalize(body.DispatchKey, body.State, body.ErrorCode))));
    }

    /// <summary>
    /// Turns a domain refusal into a stable error response instead of letting it escape.
    /// </summary>
    /// <remarks>
    /// <para><b>Found by a test, and it was worse than it looked.</b> A stale-epoch dispatch threw a
    /// <see cref="WorkspaceStoreException"/> out of the handler, past <see cref="Handle{TRequest}"/>
    /// — which deliberately guards only decoding — and out of the server's listen loop. One client
    /// holding a stale epoch would have taken the daemon down for <i>every</i> shell attached to the
    /// workspace.</para>
    ///
    /// <para><b>Why the distinction matters and is not a widening of the catch.</b> `Handle`'s rule
    /// stands: a projection that throws is a defect in us and must not be swallowed. But a stale
    /// epoch is not a defect — it is the expected answer when the core was replaced under a caller,
    /// and the design requires it to come back as a stable denial code. Only
    /// <see cref="WorkspaceStoreException"/> is mapped, because it is the type that carries one;
    /// everything else still escapes.</para>
    /// </remarks>
    /// <summary>Registers the workspace-wide C# index on <paramref name="endpoint"/>.</summary>
    public static void RegisterIndex(DaemonEndpoint endpoint, Func<string, bool, CancellationToken, Task<IndexSummary>> index)
    {
        ArgumentNullException.ThrowIfNull(endpoint);
        ArgumentNullException.ThrowIfNull(index);

        endpoint.Register(IndexSolution, (request, _) =>
            Refusable(() => Handle<IndexSolutionRequest>(request, body =>
                // Awaited here because the control lane serves one request at a time per connection
                // and the per-scope budget already bounds the total. If indexing ever outgrows that,
                // it becomes started-and-polled like scope refresh rather than a longer timeout.
                index(body.ArtifactRevision, body.Force, CancellationToken.None).GetAwaiter().GetResult())));
    }

    private static IpcResponse Refusable(Func<IpcResponse> operation)
    {
        try
        {
            return operation();
        }
        catch (WorkspaceStoreException ex)
        {
            return IpcResponse.Error(ex.ErrorCode, ex.Message);
        }
    }

    /// <summary>Decodes a payload, runs the projection, and encodes the result.</summary>
    /// <remarks>
    /// <para><b>A malformed payload is a rejection, not a crash.</b> The bytes come from another
    /// process; an unhandled <see cref="JsonException"/> here would take down a daemon serving every
    /// other shell attached to the workspace.</para>
    ///
    /// <para><b>What is NOT caught is as deliberate as what is.</b> Only decoding is guarded. A
    /// projection that throws is a defect in us, and swallowing it into a generic error would turn a
    /// bug into a shrug — the daemon would keep answering, wrongly, and nothing would say so.</para>
    /// </remarks>
    private static IpcResponse Handle<TRequest>(IpcRequest request, Func<TRequest, object> project)
    {
        TRequest? body;

        try
        {
            body = IpcPayload.Read<TRequest>(request.Payload, Wire);
        }
        catch (JsonException)
        {
            return IpcResponse.Error(
                IpcErrorCodes.MalformedEnvelope, $"the payload for '{request.Operation}' was not valid JSON");
        }

        if (body is null)
        {
            return IpcResponse.Error(
                IpcErrorCodes.MalformedEnvelope, $"'{request.Operation}' requires a payload");
        }

        return IpcResponse.Success(project(body), Wire);
    }
}
