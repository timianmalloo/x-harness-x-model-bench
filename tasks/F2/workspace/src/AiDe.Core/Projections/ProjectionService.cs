using System.Diagnostics;
using System.Text;
using AiDe.Core.Facts;
using AiDe.Core.Store;

namespace AiDe.Core.Projections;

public static class ProjectionErrorCodes
{
    public const string LimitExceeded = "AIDE-MCP-LIMIT-EXCEEDED";
    public const string NodeUnknown = "AIDE-PROJECTION-NODE-UNKNOWN";

    // INV-0014 P4. One code per non-located NodeContent outcome, emitted on the span beside
    // `content.outcome`. Search-key stability is the whole point: these are what an operator greps
    // for when a language's files stop being readable — which is how DC-229 should have surfaced.

    /// <summary>No assertion names a source artifact for the node at all.</summary>
    public const string ContentNoDeclaration = "AIDE-PROJECTION-CONTENT-NO-DECLARATION";

    /// <summary>A recorded artifact path that does not name a file inside the workspace.</summary>
    public const string ContentUnresolvable = "AIDE-PROJECTION-CONTENT-UNRESOLVABLE";

    /// <summary>The file is there and could not be opened.</summary>
    public const string ContentUnreadable = "AIDE-PROJECTION-CONTENT-UNREADABLE";

    /// <summary>A real file whose extension this reader does not render inline.</summary>
    public const string ContentNotRendered = "AIDE-PROJECTION-CONTENT-NOT-RENDERED";
}

/// <summary>
/// What a bounded result actually returned, and what it left out. Every projection carries this:
/// a truncated result that does not publish its omission is indistinguishable from a complete one,
/// which is how a "bounded" tool silently becomes an unbounded context assembler.
/// </summary>
public sealed record ResultBounds(
    int MaxNodes,
    int MaxEdges,
    int MaxBytes,
    int ReturnedNodes,
    int OmittedNodes,
    int ReturnedEdges,
    int OmittedEdges,
    bool ByteCapped,
    /// <summary>
    /// <b>Always null. No projection returning <see cref="ResultBounds"/> pages.</b>
    /// </summary>
    /// <remarks>
    /// Kept because the wire shape is published, and removing a field is a breaking change for a
    /// field nobody reads. Said out loud because a caller could reasonably loop on it and never get
    /// past the first page, with nothing failing. The one projection that DOES page —
    /// <see cref="ProjectionService.Evidence"/> — returns <see cref="EvidencePage"/> and its own
    /// cursor, which is populated and tested.
    /// </remarks>
    string? NextCursor);

public sealed record EdgeView(
    string Subject,
    string Predicate,
    string Object,
    VerificationStatus Status,
    EvidenceOrigin Origin,
    string ArtifactRevision,
    Provenance Provenance);

public sealed record NodeView(string NodeId, string NodeKind, string DisplayLabel);

/// <param name="NeighborKinds">
/// Each neighbouring node's own <c>has_type</c>, keyed by node id.
/// </param>
/// <param name="KnowledgeIds">
/// Which of the described node and its neighbours the workspace classifies as knowledge.
/// </param>
/// <remarks>
/// <para><b>INV-0004.</b> The canvas hardcoded <c>"source"</c> as every neighbour's kind because the
/// describe result did not carry one — so a drill-down showed a table, a bicep resource and a class
/// as the same thing, and the filter could not tell them apart. The kind is a property of the
/// NEIGHBOUR, and only the projection can read it; a renderer inventing a default is a renderer
/// stating a fact it does not have.</para>
///
/// <para><b><c>KnowledgeIds</c> closes the same shape one field over.</b> The view model carried a
/// written-down gap — <c>IsKnowledge</c> defaulted to <c>false</c> on every drill-down neighbour
/// because a kind is not a node class, so the view "genuinely cannot tell knowledge from source".
/// <c>false</c> under-counted rather than mislabelled, which is the safer direction and still a
/// renderer answering a question it had no data for. It matters more now that the graph reports
/// <c>NotInView</c>: the default view is a map of the code, and a knowledge node the budget could
/// never draw is reached by drill-down instead — so the drill-down has to know what it is
/// holding.</para>
/// </remarks>
public sealed record DescribeResult(
    NodeView Node,
    IReadOnlyList<EdgeView> Neighbors,
    ResultBounds Bounds,
    string SourceRevision,
    IReadOnlyDictionary<string, string>? NeighborKinds = null,
    IReadOnlyList<string>? Members = null,
    int MembersDeclared = 0,
    IReadOnlyCollection<string>? KnowledgeIds = null);

public sealed record ImpactResult(
    string RootNodeId,
    IReadOnlyList<NodeView> Nodes,
    IReadOnlyList<EdgeView> Edges,
    ResultBounds Bounds,
    string SourceRevision);

/// <summary>One search hit, and why it is one.</summary>
/// <param name="MatchedOn">
/// Whether the node's own identity contained the term, or one of its attribute values did.
/// </param>
/// <param name="Evidence">
/// <c>predicate = value</c> for an attribute match, truncated; null for an identity match, where the
/// id is already the evidence. A result whose relevance is invisible reads as a wrong result:
/// searching <c>addEventListener</c> and being shown a class called <c>Element</c> is correct, and
/// looks like a defect until the row says why.
/// </param>
/// <remarks>
/// The two fields are ADDED rather than replacing anything, and both are optional to read. A client
/// that ignores them behaves exactly as before — which is what makes this a widening of the contract
/// and not a break of it.
/// </remarks>
public sealed record FindMatch(
    string NodeId,
    string NodeKind,
    string DisplayLabel,
    AuthorshipOrigin Authorship,
    Store.NodeMatchKind MatchedOn = Store.NodeMatchKind.Identity,
    string? Evidence = null);

public sealed record FindResult(IReadOnlyList<FindMatch> Matches, ResultBounds Bounds, string SourceRevision);

/// <summary>One page of current evidence, and where to continue.</summary>
/// <param name="NextCursor">Null when this page is the last. Opaque to the caller, by design.</param>
public sealed record EvidencePage(
    IReadOnlyList<Facts.EvidenceAssertion> Assertions,
    string? NextCursor,
    string SourceRevision);

/// <summary>
/// The paging cursor: the last row's ordering tuple, encoded.
/// </summary>
/// <remarks>
/// Base64 of the three ordered fields, so it survives a JSON round trip and a caller cannot
/// construct one by hand and expect it to mean something. Ordering by the same tuple the cursor
/// carries is what makes a page boundary unable to skip or repeat a row.
/// </remarks>
internal static class EvidenceCursor
{
    private const char Separator = '';

    internal static string Format(string subject, string predicate, string obj, string scopeId) =>
        Convert.ToBase64String(System.Text.Encoding.UTF8.GetBytes(
            string.Join(Separator, subject, predicate, obj, scopeId)));

    internal static (string Subject, string Predicate, string Object, string ScopeId)? Parse(string? cursor)
    {
        if (string.IsNullOrWhiteSpace(cursor)) return null;

        try
        {
            var parts = System.Text.Encoding.UTF8
                .GetString(Convert.FromBase64String(cursor))
                .Split(Separator);

            // A malformed cursor restarts from the beginning rather than throwing. The caller gets
            // rows it has already seen, which is wasteful and correct; the alternative is a failed
            // read for a value the caller was never supposed to inspect.
            return parts.Length == 4 ? (parts[0], parts[1], parts[2], parts[3]) : null;
        }
        catch (FormatException)
        {
            return null;
        }
    }
}

/// <summary>
/// Who authored a record. Carried on every read result so a consuming agent can tell a repository
/// fact from something another agent wrote — without it, an agent-authored note is laundered back
/// out as workspace knowledge.
/// </summary>
public enum AuthorshipOrigin
{
    RepositoryArtifact,
    Human,
    Agent,
}

public sealed record KnowledgeQuery(string? Term, string? Type, int MaxResults);

public sealed record KnowledgeNodeView(
    string NodeId,
    string Type,
    string? Owner,
    IReadOnlyList<EdgeView> Links,
    IReadOnlyList<EdgeView> Backlinks,
    string? SourceLocation,
    IReadOnlyList<string> HealthFindings);

public sealed record KnowledgeResult(
    IReadOnlyList<KnowledgeNodeView> Nodes,
    ResultBounds Bounds,
    string SourceRevision);

/// <summary>
/// Bounded, self-describing projections over the current fact set.
/// </summary>
/// <remarks>
/// Pattern: CQRS / Materialized Read Model. Every result is rebuildable from facts and every one is
/// capped on nodes, edges AND bytes — the byte cap matters because node labels come from repository
/// content, so a count-only cap still admits an unbounded payload.
/// </remarks>
public sealed class ProjectionService(WorkspaceStore store, string? workspaceRoot = null)
{
    private static readonly ActivitySource Activity = new("aide.projection.query");

    public const int MaxNeighborsCeiling = 50;
    // A type's declared members are capped by the extractor at 40; 80 gives headroom for that plus the
    // members_truncated marker without letting a pathological node return an unbounded compartment.
    public const int MaxMembersRead = 80;
    public const int MaxEdgesCeiling = 500;
    public const int MaxNodesCeiling = 200;
    public const int MaxResultBytes = 64 * 1024;

    /// <summary>
    /// The most a single response may serialise to.
    /// </summary>
    /// <remarks>
    /// <para><b>Derived from the transport, with headroom.</b> One IPC frame carries 1,048,576 bytes
    /// (<c>IpcFraming.MaxFrameBytes</c>); this leaves a quarter of it spare for the response envelope
    /// and for the difference between an estimate and the truth. A projection that fills the frame
    /// exactly is one repository away from INV-0003.</para>
    ///
    /// <para><b>Why a byte budget and not a bigger count ceiling.</b> Every ceiling in this class
    /// counts ITEMS and the transport limit is in BYTES, and node labels, subjects and paths all come
    /// from repository content — so a count-only cap admits an unbounded payload. That is not a
    /// hypothetical: MEASURED on a real repository, an evidence page of 2,000 assertions serialises
    /// to <b>1,004,397 bytes</b>, which is 95.8% of the frame and fifteen times the
    /// <see cref="MaxResultBytes"/> its own documentation claimed it stayed "comfortably inside".</para>
    ///
    /// <para><b>Why the headroom is the size it is.</b> A response is its payload plus an envelope,
    /// and from IPC version 3 that is all it is: the payload is carried as JSON rather than as a
    /// string holding JSON text, so nothing is escaped twice. Through version 2 it was, at a measured
    /// <b>1.56–1.57x</b> — which is how a 727,244-byte graph inside a 768 KiB budget reached
    /// 1,137,104 bytes on the wire and was refused (DC-047). The budget had been checked on the inner
    /// bytes and enforced on the outer ones, and its tests counted the inner bytes too, so the guard
    /// and its proof were wrong together.</para>
    ///
    /// <para>128 KiB below the frame, which is the envelope with room to spare.
    /// <c>ThePayloadIsNotEncodedTwice</c> holds up the premise this rests on — that payload and frame
    /// are within a few percent — and <c>TheBudgetCannotDriftPastWhatAFrameHolds</c> holds up the
    /// arithmetic. Neither is optional: this number is only safe while both pass.</para>
    /// </remarks>
    public const int MaxResponseBytes = 896 * 1024;

    /// <summary>The transport's own limit, restated here only so the budget can be checked against it.</summary>
    public const int FrameBytes = Ipc.IpcFraming.MaxFrameBytes;

    /// <summary>
    /// What a shrunk graph must fit inside — the frame, less real headroom.
    /// </summary>
    /// <remarks>
    /// Shrinking stops at the FIRST size that fits, so a target equal to the frame leaves whatever
    /// margin the last step happened to produce. MEASURED with no headroom: 1,044,916 bytes against
    /// a 1,048,576 frame — 3,660 bytes, which is one longer type name away from failing. A limit met
    /// exactly is not a limit respected.
    /// </remarks>
    public const int MaxFramedGraphBytes = FrameBytes - (64 * 1024);

    /// <summary>
    /// What one assertion costs in JSON beyond its own text.
    /// </summary>
    /// <remarks>
    /// MEASURED, not estimated: a 2,000-assertion page whose subjects, predicates, objects and paths
    /// total 238,002 bytes serialises to 1,004,397 — <b>383 bytes per row</b> of field names,
    /// timestamps, enum spellings and punctuation. Rounded up for headroom, because a guard that
    /// under-counts is a guard that lets the frame overflow.
    /// </remarks>
    public const int AssertionOverheadBytes = 448;

    /// <summary>
    /// How many times a graph may be shrunk before it must already fit.
    /// </summary>
    /// <remarks>
    /// Each round takes at least a third off, so twelve rounds reduce five thousand nodes to fewer
    /// than five — far past any real graph. It is a cost bound, not the thing that makes the loop
    /// terminate; the guaranteed reduction does that.
    /// </remarks>
    public const int MaxShrinkAttempts = 12;

    /// <summary>
    /// How many times a shrunk graph may probe upward for the size it overshot.
    /// </summary>
    /// <remarks>
    /// Each probe halves the remaining gap. MEASURED on the calibrated fixture: none returns 868
    /// nodes where 1,281 fit, two returns 1,193, four returns 1,274, and six returns 1,274 again —
    /// by then <see cref="MinRecoveryGap"/> stops it. Four is where the curve flattens, and every
    /// probe is a full recompute of the graph, which is the expensive half.
    /// </remarks>
    public const int MaxRecoveryProbes = 4;

    /// <summary>
    /// Below this, the nodes still recoverable are not worth a recompute to find.
    /// </summary>
    /// <remarks>
    /// It is also the precision of the monotonicity this class offers: a larger request can return
    /// up to this many fewer nodes than a smaller one, because recovery approximates the largest
    /// fitting size rather than finding it. Exact monotonicity needs the node ORDERING computed once
    /// and candidate sizes evaluated against it — the ordering is identical for every size, so today
    /// each probe redoes work that does not change. That is the upgrade, and it is not free.
    /// </remarks>
    public const int MinRecoveryGap = 50;

    /// <summary>
    /// The ceiling on a SEARCH, which is a different question from a neighbour list.
    /// </summary>
    /// <remarks>
    /// <para><b>Find used to borrow <see cref="MaxNeighborsCeiling"/>, and 50 is the wrong number
    /// for it by two orders of magnitude.</b> The workbench asks for 20,000 matches to build the
    /// context and join panes; it received 50. Those panes were computing crossing counts, join
    /// counts and coverage from roughly three percent of a real workspace, and presenting the result
    /// as the answer — while a spike reading the store directly showed the whole picture and
    /// disagreed with the product for days.</para>
    ///
    /// <para>A search returns identity columns only — id, kind, label — so the payload per row is
    /// small and bounded, which is why this ceiling can be large where the neighbour one cannot.
    /// <see cref="MaxResultBytes"/> still applies underneath.</para>
    /// </remarks>
    public const int MaxSearchResultsCeiling = 20_000;

    /// <summary>
    /// Routes returned before the answer is truncated.
    /// </summary>
    /// <remarks>
    /// A reader comparing routes is choosing between them, and nobody chooses between two hundred.
    /// The cap is small on purpose and the truncation is reported.
    /// </remarks>
    /// <summary>
    /// Groups returned before the rest are counted and dropped.
    /// </summary>
    /// <remarks>
    /// An overview a person can read has tens of groups, not thousands; past a few hundred it is a
    /// hairball again at a coarser grain, which is the failure it exists to prevent.
    /// </remarks>
    public const int MaxClustersCeiling = 500;

    public const int MaxPathsCeiling = 100;

    /// <summary>
    /// The longest route worth returning, in edges.
    /// </summary>
    /// <remarks>
    /// Beyond about a dozen hops "A reaches B" stops being a fact about the design and becomes a
    /// fact about the graph being connected — in a codebase almost everything reaches almost
    /// everything if you allow enough steps.
    /// </remarks>
    public const int MaxPathLengthCeiling = 12;

    /// <summary>
    /// Assertions per evidence page.
    /// </summary>
    /// <remarks>
    /// <para><b>A COUNT ceiling, and it does not bound the payload.</b> This used to say the page was
    /// "sized so it stays comfortably inside <see cref="MaxResultBytes"/> once serialised". MEASURED:
    /// 2,000 assertions serialise to 1,004,397 bytes, which is fifteen times that constant and 95.8%
    /// of an IPC frame. The sentence was written, believed, and never checked.</para>
    ///
    /// <para>What actually bounds the page is <see cref="MaxResponseBytes"/>, applied row by row in
    /// <see cref="Evidence"/>; this count is the coarser of the two limits and usually is not the one
    /// that fires. An assertion carries its provenance, so it is far heavier per row than a search
    /// match — which is the reason a count could never have been the bound.</para>
    /// </remarks>
    public const int MaxEvidencePageCeiling = 2_000;

    public DescribeResult Describe(string nodeId, int maxNeighbors)
    {
        using var activity = Activity.StartActivity("aide.projection.query");
        activity?.SetTag("projection", "describe");

        var limit = Clamp(maxNeighbors, 1, MaxNeighborsCeiling);
        using var reader = store.BeginRead();

        // The bound is applied in SQL, not after materializing the corpus: a bounded read must cost
        // what its result costs, not what the graph costs (P1-PERF-02).
        var touching = reader.AssertionsTouching(nodeId, limit);
        var total = reader.CountAssertionsTouching(nodeId);

        var (kept, byteCapped) = TakeWithinByteBudget(touching, limit);
        var edges = kept.Select(ToEdge).ToList();
        var revision = touching.Count > 0 ? touching[0].ArtifactRevision : reader.CurrentSourceRevision();

        var bounds = new ResultBounds(
            MaxNodes: 1, MaxEdges: limit, MaxBytes: MaxResultBytes,
            ReturnedNodes: 1, OmittedNodes: 0,
            ReturnedEdges: edges.Count, OmittedEdges: Math.Max(0, total - edges.Count),
            ByteCapped: byteCapped, NextCursor: null);

        activity?.SetTag("returned.edges", edges.Count);
        activity?.SetTag("omitted.edges", bounds.OmittedEdges);

        // The kinds of the nodes on the other end. Read here because the projection is the only
        // thing that can: the canvas has ids and nothing else.
        var kinds = edges
            .SelectMany(e => new[] { e.Subject, e.Object })
            .Where(id => !string.Equals(id, nodeId, StringComparison.Ordinal))
            .Distinct(StringComparer.Ordinal)
            .ToDictionary(id => id, id => NodeOf(reader, id).NodeKind, StringComparer.Ordinal);

        // The type's OWN members (has_member) — the class-diagram compartment (ADR-0026 class-diagram-architecture Phase 2). Read
        // directly by subject so the neighbour cap cannot starve them; `members_truncated` carries the
        // real declared count when the extractor capped the listing. Empty for a non-type node.
        var ownRows = reader.OutgoingAssertions(nodeId, MaxMembersRead);
        var members = ownRows.Where(a => a.Predicate == "has_member").Select(a => a.Object).ToList();
        var declared = members.Count;
        var truncated = ownRows.FirstOrDefault(a => a.Predicate == "members_truncated");
        if (truncated is not null
            && int.TryParse(truncated.Object, System.Globalization.CultureInfo.InvariantCulture, out var d))
        {
            declared = d;
        }

        // The described node AND its neighbours, in one bounded read. Asking per-node would make the
        // cost of a drill-down a function of its neighbour count in round trips rather than in rows.
        var knowledge = reader.ReadKnowledgeIds([nodeId, .. kinds.Keys]);

        return new DescribeResult(
            NodeOf(reader, nodeId), edges, bounds, revision, kinds, members, declared, knowledge);
    }

    /// <summary>
    /// Bounded dependent-neighbourhood walk. Breadth-first with an explicit frontier cap, so the
    /// traversal cannot fan out into the whole graph — the caller always learns what was omitted.
    /// </summary>
    public ImpactResult Impact(string nodeId, int maxNodes, int maxEdges)
    {
        using var activity = Activity.StartActivity("aide.projection.query");
        activity?.SetTag("projection", "impact");

        var nodeLimit = Clamp(maxNodes, 1, MaxNodesCeiling);
        var edgeLimit = Clamp(maxEdges, 1, MaxEdgesCeiling);

        using var reader = store.BeginRead();

        var visited = new HashSet<string>(StringComparer.Ordinal) { nodeId };
        var order = new List<string> { nodeId };
        var edges = new List<StoredAssertion>();
        var queue = new Queue<string>();
        queue.Enqueue(nodeId);
        var omittedNodes = 0;
        var omittedEdges = 0;

        while (queue.Count > 0)
        {
            var current = queue.Dequeue();

            // One indexed lookup per frontier node, bounded by the remaining edge budget. The walk
            // therefore costs what it visits — previously it grouped the entire corpus up front,
            // so a 3-node neighbourhood paid for all 50,000 edges (P1-PERF-03).
            var remaining = edgeLimit - edges.Count + 1;
            var outgoing = reader.OutgoingAssertions(current, Math.Max(1, remaining));
            if (outgoing.Count == 0)
            {
                continue;
            }

            foreach (var assertion in outgoing)
            {
                if (edges.Count >= edgeLimit)
                {
                    omittedEdges++;
                    continue;
                }

                if (!visited.Contains(assertion.Object))
                {
                    if (order.Count >= nodeLimit)
                    {
                        omittedNodes++;
                        continue;
                    }

                    visited.Add(assertion.Object);
                    order.Add(assertion.Object);
                    queue.Enqueue(assertion.Object);
                }

                edges.Add(assertion);
            }
        }

        var (kept, byteCapped) = TakeWithinByteBudget(edges, edges.Count);
        omittedEdges += edges.Count - kept.Count;

        var bounds = new ResultBounds(
            nodeLimit, edgeLimit, MaxResultBytes,
            order.Count, omittedNodes, kept.Count, omittedEdges, byteCapped, null);

        var revision = edges.Count > 0 ? edges[0].ArtifactRevision : reader.CurrentSourceRevision();
        activity?.SetTag("returned.nodes", order.Count);

        return new ImpactResult(
            nodeId,
            order.Select(id => NodeOf(reader, id)).ToList(),
            kept.Select(ToEdge).ToList(),
            bounds,
            revision);
    }

    /// <summary>
    /// One page of every current assertion, for a caller that wants the whole set.
    /// </summary>
    /// <remarks>
    /// <para>The panes want all of it and were rebuilding it node by node through
    /// <see cref="Describe"/>, which bounds neighbours at 50 and dropped two join edges of 124 doing
    /// so. This asks the question they were actually asking.</para>
    ///
    /// <para><b>Bounded by BYTES as well as by count, and the byte bound is the one that matters.</b>
    /// This method's documentation used to claim a page "can cross a pipe without breaching the
    /// result-byte cap". It could not: MEASURED on a real repository, a 2,000-assertion page is
    /// <b>1,004,397 bytes</b> against a 1,048,576-byte frame — 95.8% full, and over the frame
    /// entirely on a repository with slightly longer type names. The claim was written, believed and
    /// never checked, which is the same shape as INV-0003 one method along.</para>
    ///
    /// <para>Truncating a page early is LOSSLESS here, and that is why the fix belongs at this level:
    /// the cursor continues from the last row actually returned, so a byte-bounded page costs one
    /// extra round trip and never drops a row.</para>
    /// </remarks>
    public EvidencePage Evidence(string? cursor, int maxAssertions)
    {
        using var activity = Activity.StartActivity("aide.projection.query");
        activity?.SetTag("projection", "evidence");

        var limit = Clamp(maxAssertions, 1, MaxEvidencePageCeiling);
        using var reader = store.BeginRead();

        var after = EvidenceCursor.Parse(cursor);
        var rows = reader.CurrentAssertionPage(after, limit);

        // The BYTE bound, applied before the count bound can pretend to be one.
        var kept = new List<StoredAssertion>(rows.Count);
        var bytes = 0;
        var truncatedByBytes = false;

        foreach (var row in rows)
        {
            var size = Encoding.UTF8.GetByteCount(row.Subject)
                + Encoding.UTF8.GetByteCount(row.Predicate)
                + Encoding.UTF8.GetByteCount(row.Object)
                + Encoding.UTF8.GetByteCount(row.ScopeId)
                + Encoding.UTF8.GetByteCount(row.ArtifactRevision)
                + Encoding.UTF8.GetByteCount(row.Provenance.ArtifactPathId)
                + AssertionOverheadBytes;

            // At least one row always goes back. A page that returns nothing because its first row
            // is enormous is a caller that can never make progress, which is worse than one frame
            // that is slightly over.
            if (kept.Count > 0 && bytes + size > MaxResponseBytes)
            {
                truncatedByBytes = true;
                break;
            }

            bytes += size;
            kept.Add(row);
        }

        activity?.SetTag("returned.assertions", kept.Count);
        activity?.SetTag("returned.bytes", bytes);
        activity?.SetTag("truncated.by_bytes", truncatedByBytes);

        // A page that came back full MIGHT have more behind it; one that came back short cannot —
        // UNLESS the byte bound cut it short, in which case there is certainly more and the cursor
        // must say so or the caller stops early believing it has everything.
        var next = truncatedByBytes || rows.Count == limit
            ? EvidenceCursor.Format(kept[^1].Subject, kept[^1].Predicate, kept[^1].Object, kept[^1].ScopeId)
            : null;

        return new EvidencePage(
            [.. kept.Select(r => new EvidenceAssertion(
                r.ScopeId, r.ArtifactRevision, r.Subject, r.Predicate, r.Object,
                r.Origin, r.Status, r.Provenance))],
            next,
            reader.CurrentSourceRevision());
    }

    /// <summary>
    /// The whole workspace as a graph.
    /// </summary>
    /// <remarks>
    /// The question the graph surface was never asking. It requested one node and that node's
    /// neighbours, so a workspace of 12,100 assertions rendered as two nodes — reported against the
    /// same repository viewed in Obsidian.
    /// </remarks>
    public WorkspaceGraph Graph(int maxNodes) => Graph(new GraphQuery(maxNodes));

    /// <summary>The graph the query asks for — filtered before the cap applies.</summary>
    public WorkspaceGraph Graph(GraphQuery query)
    {
        using var activity = Activity.StartActivity("aide.projection.query");
        activity?.SetTag("projection", "graph");

        using var reader = store.BeginRead();

        var assertions = reader.AllCurrentAssertions()
            .Select(a => new EvidenceAssertion(
                a.ScopeId, a.ArtifactRevision, a.Subject, a.Predicate, a.Object,
                a.Origin, a.Status, a.Provenance))
            .ToList();

        var projection = new GraphProjection(assertions, reader.CurrentSourceRevision());
        var graph = projection.Compute(
            query with { MaxNodes = Clamp(query.MaxNodes, 1, GraphProjection.DefaultMaxNodes) });

        // The graph at its own COUNT ceiling still overflows the frame — MEASURED, 1,522,915 bytes
        // for 5,000 permitted nodes on a real repository. The canvas asks for a bounded default now,
        // but the operation is still reachable, and an operation that can never succeed is a defect
        // whoever calls it. Shrink to fit and let Omitted say so, rather than build a response the
        // transport will refuse.
        // Shrink until it FITS, and check that it did.
        //
        // The previous version applied ONE proportional correction and returned whatever came back.
        // That assumes bytes fall in proportion to node count, and they do not: nodes are kept in
        // degree order, so the ones that survive a cut are the most connected ones, and the edges
        // they carry dominate the payload. Cutting 15% of the nodes can cut 2% of the bytes.
        //
        // MEASURED on a real workspace: the response reached 1,176,341 bytes against a 1,048,576
        // frame, and the only thing the user saw was "The graph could not be loaded" on opening the
        // workspace — a shrink that had run, reported success by returning, and not worked.
        var weight = FramedCost(graph);
        var attempts = 0;

        // The smallest node count KNOWN not to fit, so the recovery below has something to aim at.
        var tooMany = int.MaxValue;

        while (weight > MaxFramedGraphBytes && graph.Nodes.Count > 1 && attempts < MaxShrinkAttempts)
        {
            tooMany = graph.Nodes.Count;

            var proportional = (int)(graph.Nodes.Count * (MaxFramedGraphBytes / (double)weight) * 0.85);

            // A third off every round at minimum, so this terminates even on a graph whose bytes
            // barely move when its node count does. Without it the loop ends only at the attempt
            // cap — and the cap firing would mean returning a response the transport refuses, which
            // is a circuit breaker used as a termination argument (GO12).
            var next = Math.Clamp(proportional, 1, graph.Nodes.Count * 2 / 3);

            graph = projection.Compute(query with { MaxNodes = next });
            weight = FramedCost(graph);
            attempts++;
        }

        // Take back what the shrink overshot.
        //
        // Every round above cuts by AT LEAST a third, which is what makes it terminate — and it means
        // the first size that fits can be far below the largest that would have. MEASURED before this:
        // asking for 5,000 nodes returned 706 while asking for 1,500 returned 1,000, so a caller who
        // asked for MORE was served LESS. That is not a shortfall in fidelity, it is a surface whose
        // answer depends on a number in a way nobody could predict or explain.
        //
        // Two probes at the midpoint of (fits, does-not-fit) recover most of it for a bounded cost.
        // Only ever accepted when the probe fits, so this can widen the answer and never break it.
        var recoveries = 0;

        while (attempts > 0 && recoveries < MaxRecoveryProbes
            && tooMany - graph.Nodes.Count > MinRecoveryGap)
        {
            var midpoint = graph.Nodes.Count + ((tooMany - graph.Nodes.Count) / 2);
            var candidate = projection.Compute(query with { MaxNodes = midpoint });
            var candidateWeight = FramedCost(candidate);

            if (candidateWeight <= MaxFramedGraphBytes)
            {
                graph = candidate;
                weight = candidateWeight;
            }
            else
            {
                tooMany = candidate.Nodes.Count;
            }

            recoveries++;
        }

        activity?.SetTag("shrunk.attempts", attempts);
        activity?.SetTag("recovery.probes", recoveries);
        activity?.SetTag("returned.bytes", weight);

        activity?.SetTag("returned.nodes", graph.Nodes.Count);
        activity?.SetTag("returned.edges", graph.Edges.Count);
        activity?.SetTag("omitted.nodes", graph.Omitted);

        return graph;
    }

    /// <summary>
    /// Census join of disk-now folders and latest-generation file-artifacts.
    /// </summary>
    public SolutionTreeResult SolutionTree(SolutionTreeQuery query) =>
        SolutionTree(query, omitRelativePaths: null, censusChildren: null, CancellationToken.None);

    /// <summary>D-1 UV-0 listing. Classification pending; all rows unclassified. No Open Sequence.</summary>
    public EntryPointsResult EntryPoints(EntryPointsQuery query) =>
        EntryPoints(query, CancellationToken.None);

    public EntryPointsResult EntryPoints(EntryPointsQuery query, CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(query);
        using var activity = Activity.StartActivity("aide.projection.query");
        activity?.SetTag("projection", "entry-points");
        cancellationToken.ThrowIfCancellationRequested();
        try
        {
            using var reader = store.BeginRead();
            var candidates = reader.SourceHasTypeNodes();
            var members = reader.SourceHasMembers();
            // Clamp, not trust: the listing floors at 1 and ceils at nothing, so an unclamped
            // MaxRows hands the frame budget to the caller. Every other operation here clamps.
            var result = EntryPointsListing.FromHasType(
                candidates,
                Clamp(query.MaxRows, 1, EntryPointsProjection.MaxRowsCeiling),
                reader.CurrentSourceRevision(),
                members);
            activity?.SetTag("returned.rows", result.Rows.Count);
            activity?.SetTag("omitted.by_cap", result.OmittedByCap);
            activity?.SetTag("outcome", "ok");
            return result;
        }
        catch (OperationCanceledException)
        {
            activity?.SetTag("outcome", "canceled");
            throw;
        }
    }


    public SolutionTreeResult SolutionTree(SolutionTreeQuery query, CancellationToken cancellationToken) =>
        SolutionTree(query, omitRelativePaths: null, censusChildren: null, cancellationToken);

    internal SolutionTreeResult SolutionTree(
        SolutionTreeQuery query,
        IEnumerable<string>? omitRelativePaths,
        Func<string, IEnumerable<string>>? censusChildren = null,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(query);

        using var activity = Activity.StartActivity("aide.projection.query");
        activity?.SetTag("projection", "solution-tree");
        var shrinkAttempts = 0;

        try
        {
            using var reader = store.BeginRead();
            var files = new List<SolutionTreeProjection.JoinedFile>();
            var joinDisclosures = new List<SolutionTreeDisclosure>();

            foreach (var (nodeId, scopeId, artifactPath) in reader.FilesToSearch())
            {
                if (SolutionTreeProjection.IsPythonOrTypeScriptScope(scopeId)) continue;

                var candidate = CandidateWithinWorkspace(reader, scopeId, artifactPath);
                if (candidate is not null && File.Exists(candidate) && workspaceRoot is not null)
                {
                    var relative = SolutionTreeProjection.NormalizeRelative(
                        Path.GetRelativePath(Path.GetFullPath(workspaceRoot), candidate));
                    files.Add(new SolutionTreeProjection.JoinedFile(
                        relative, nodeId, reader.ReadNodeKind(nodeId)));
                    continue;
                }

                if (candidate is not null && Directory.Exists(candidate)) continue;

                if (IsHostileArtifactPath(artifactPath) || IsFilenameOnly(artifactPath))
                {
                    joinDisclosures.Add(SolutionTreeProjection.Disclosure(
                        SolutionTreeShortfallCause.UnresolvablePath,
                        SolutionTreeProjection.NotRecordedCopy,
                        artifactPath));
                }
            }

            var scopes = reader.AllScopeLocations()
                .Select(s => new SolutionTreeProjection.ScopeDeclaredAt(
                    s.ScopeId, SolutionTreeProjection.NormalizeRelative(s.DeclaredAt)))
                .ToList();

            var projection = new SolutionTreeProjection(omitRelativePaths, censusChildren);
            var computed = projection.Compute(
                workspaceRoot, query, files, scopes, joinDisclosures,
                reader.CurrentSourceRevision(), cancellationToken);

            var result = ShrinkTree(projection, computed, ref shrinkAttempts);

            TagSolutionTree(activity, result, shrinkAttempts);
            activity?.SetTag("outcome", "ok");
            return result;
        }
        catch (OperationCanceledException)
        {
            activity?.SetTag("outcome", "canceled");
            throw;
        }
    }

    private SolutionTreeResult ShrinkTree(
        SolutionTreeProjection projection, SolutionTreeResult computed, ref int attempts)
    {
        SolutionTreeResult Pack(IReadOnlyList<SolutionTreeNode> nodes, int omitted) =>
            new(
                nodes,
                computed.SkipListedDirectoriesOmitted,
                omitted,
                SolutionTreeProjection.FinalizeDisclosures(computed.Disclosures.ToList(), omitted),
                computed.SourceRevision);

        if (FramedCost(Pack(computed.Nodes, computed.OmittedByCap)) <= MaxFramedGraphBytes)
        {
            return computed;
        }

        var counter = 0;
        var shrunk = projection.ShrinkRankedPrefix(
            computed.Nodes,
            computed.OmittedByCap,
            (nodes, omitted, _) =>
            {
                counter++;
                return Pack(nodes, omitted);
            },
            FramedCost,
            MaxFramedGraphBytes);

        attempts = counter;
        var omitted = computed.OmittedByCap + (computed.Nodes.Count - shrunk.Count);
        return Pack(shrunk, omitted);
    }

    private static void TagSolutionTree(Activity? activity, SolutionTreeResult result, int shrinkAttempts)
    {
        if (activity is null) return;

        var folders = 0;
        var files = 0;
        var indexed = 0;
        var unindexed = 0;
        foreach (var node in result.Nodes)
        {
            if (node.Kind == SolutionTreeNodeKind.FileArtifact) { files++; continue; }
            folders++;
            if (node.Coverage == CensusFolderCoverage.IndexedParent) indexed++;
            else if (node.Coverage == CensusFolderCoverage.Unindexed) unindexed++;
        }

        activity.SetTag("returned.census_folders", folders);
        activity.SetTag("returned.file_artifacts", files);
        activity.SetTag("returned.indexed_parent", indexed);
        activity.SetTag("returned.unindexed", unindexed);
        activity.SetTag("skip.omitted", result.SkipListedDirectoriesOmitted);
        activity.SetTag("omitted.by_cap", result.OmittedByCap);
        activity.SetTag("returned.bytes", FramedCost(result));
        activity.SetTag("shrunk.attempts", shrinkAttempts);

        if (result.Disclosures.Count > 0)
        {
            var causes = string.Join(',', result.Disclosures
                .Select(d => d.Cause.ToString())
                .Distinct()
                .Order(StringComparer.Ordinal));
            activity.SetTag("shortfall.causes", causes);
        }
    }

    private static bool IsFilenameOnly(string artifactPath)
    {
        var n = SolutionTreeProjection.NormalizeRelative(artifactPath);
        return n.Length > 0 && n.IndexOf('/') < 0;
    }

    private static bool IsHostileArtifactPath(string artifactPath)
    {
        var n = artifactPath.Replace('\\', '/');
        return n.Contains("..", StringComparison.Ordinal) || Path.IsPathRooted(artifactPath);
    }

    /// <summary>
    /// True when a row's artifact path could not name a file under its scope at all — as opposed to
    /// naming one that is not there.
    /// </summary>
    /// <remarks>
    /// <para><b>DC-229.</b> Both language extractors wrote the SCOPE id into this field, and a scope
    /// id is a kind and a colon: <c>csharp:PROJECT:TFM</c>, <c>python:DIR</c>,
    /// <c>typescript:DIR</c> (<see cref="Extraction.ScopeDescriptor"/>,
    /// <see cref="SolutionTreeProjection.IsPythonOrTypeScriptScope"/>). A scope-relative artifact
    /// path carries no colon, and on Windows it could not: the colon is the volume and
    /// alternate-stream separator, so such a value resolves to an ADS name or throws, depending on
    /// the spelling. Asking the question here rather than letting the path parser decide is what
    /// puts the class in ONE bucket on every platform.</para>
    ///
    /// <para><b>Only ever asked about a skip.</b> Resolution is attempted first and wins; this only
    /// says which kind of failure a failure was, so a POSIX file legitimately spelled with a colon
    /// is still searched.</para>
    /// </remarks>
    private static bool IsUnusableArtifactPath(string artifactPath) =>
        string.IsNullOrWhiteSpace(artifactPath)
        || artifactPath.Contains(':', StringComparison.Ordinal);

    /// <summary>
    /// The workspace at a distance: groups rather than nodes, for a graph too large to draw.
    /// </summary>
    /// <remarks>
    /// Built over the same <see cref="Graph"/> projection the canvas uses, so an overview can never
    /// summarise a node the detailed view would not show. Two answers to one question is the defect
    /// signature this codebase has already paid for.
    /// </remarks>
    public WorkspaceOverview Overview(OverviewQuery query)
    {
        ArgumentNullException.ThrowIfNull(query);

        using var activity = Activity.StartActivity("aide.projection.query");
        activity?.SetTag("projection", "overview");

        // The node graph underneath is asked for at the PROJECTION ceiling rather than the canvas
        // default: an overview summarises, so it should summarise as much as it can see, and the
        // result is groups whose count is bounded regardless.
        var graph = Graph(query.Query ?? new GraphQuery(GraphProjection.DefaultMaxNodes, IncludeExternal: false));

        var overview = GraphOverview.Summarise(graph, query with
        {
            MaxClusters = Clamp(query.MaxClusters, 1, MaxClustersCeiling),
        });

        activity?.SetTag("returned.clusters", overview.Clusters.Count);
        activity?.SetTag("returned.cluster_edges", overview.Edges.Count);
        activity?.SetTag("omitted.clusters", overview.OmittedClusters);

        return overview;
    }

    /// <summary>How one node reaches another, within the graph the query names.</summary>
    /// <remarks>
    /// Built over the same projection the graph surface uses, so a route can never contain an edge
    /// the picture does not show — two answers to one question is the defect signature this
    /// codebase has already paid for once.
    /// </remarks>
    public PathResult Paths(PathQuery query)
    {
        ArgumentNullException.ThrowIfNull(query);

        using var activity = Activity.StartActivity("aide.projection.query");
        activity?.SetTag("projection", "paths");

        var graph = Graph(query.Query ?? new GraphQuery());

        var result = GraphPaths.Find(graph, query with
        {
            MaxPaths = Clamp(query.MaxPaths, 1, MaxPathsCeiling),
            MaxLength = Clamp(query.MaxLength, 1, MaxPathLengthCeiling),
        });

        activity?.SetTag("returned.paths", result.Paths.Count);
        activity?.SetTag("truncated", result.Truncated);

        return result;
    }

    public FindResult Find(string term, int maxResults)
    {
        using var activity = Activity.StartActivity("aide.projection.query");
        activity?.SetTag("projection", "find");

        var limit = Clamp(maxResults, 1, MaxSearchResultsCeiling);
        using var reader = store.BeginRead();

        // Identity columns only: a leading-wildcard LIKE cannot use an index, so the cheapest
        // correct shape is to scan a covering index instead of hydrating every row's provenance.
        var (candidates, totalMatched) = reader.SearchNodes(term, limit);

        // The byte bound, ENFORCED rather than merely declared. This built the whole match list and
        // then reported `MaxBytes: 65,536` beside it — MEASURED at 461,750 bytes returned on a real
        // repository, and the ceiling permits 20,000 results where this repository happened to have
        // 2,764. A caller reading the bounds was told a limit that could not fire (DC-016), and a
        // repository with more matches would have overflowed the frame exactly like INV-0003.
        var matches = new List<FindMatch>();
        var bytes = 0;
        var byteCapped = false;

        foreach (var hit in candidates)
        {
            var node = NodeOf(reader, hit.NodeId);

            var match = new FindMatch(node.NodeId, node.NodeKind, node.DisplayLabel,
                // Phase 1 has no agent-authored records yet; stating the origin explicitly now
                // means the field exists on the wire before agents can write, rather than being
                // retrofitted after the laundering path is already open.
                AuthorshipOrigin.RepositoryArtifact,
                hit.Kind,
                hit.Evidence);

            // The evidence is counted. A budget that ignores a field it just added is a budget
            // that no longer describes the response — the exact shape that let a 1.18 MB payload
            // through a 1 MiB frame while reporting itself inside the limit.
            var size = Encoding.UTF8.GetByteCount(match.NodeId)
                + Encoding.UTF8.GetByteCount(match.NodeKind)
                + Encoding.UTF8.GetByteCount(match.DisplayLabel)
                + (match.Evidence is null ? 0 : Encoding.UTF8.GetByteCount(match.Evidence))
                + AssertionOverheadBytes;

            // At least one result always comes back, for the same reason the evidence page keeps
            // one row: a search that returns nothing because its first hit is long is worse than a
            // response slightly over an internal budget.
            if (matches.Count > 0 && bytes + size > MaxResponseBytes)
            {
                byteCapped = true;
                break;
            }

            bytes += size;
            matches.Add(match);
        }

        activity?.SetTag("returned.bytes", bytes);
        activity?.SetTag("byte.capped", byteCapped);

        var bounds = new ResultBounds(
            limit, 0, MaxResponseBytes, matches.Count, Math.Max(0, totalMatched - matches.Count),
            0, 0, byteCapped, null);

        return new FindResult(matches, bounds, reader.CurrentSourceRevision());
    }

    /// <summary>
    /// US-4: knowledge navigation. Same facts, filtered to knowledge-kind subjects, with backlinks
    /// and the health findings the spec requires when source/owner/links are missing.
    /// </summary>
    public KnowledgeResult Knowledge(KnowledgeQuery query)
    {
        using var activity = Activity.StartActivity("aide.projection.query");
        activity?.SetTag("projection", "knowledge");

        var limit = Clamp(query.MaxResults, 1, MaxNeighborsCeiling);
        using var reader = store.BeginRead();

        // EVERY filter in the query, and the total counted over the same filtered set.
        //
        // This has now been the same defect three times. First it read the first 200 `has_type`
        // assertions and filtered THOSE to knowledge, so the 200 were C# types in alphabetical order
        // and the filter left nothing — 0 items on a workspace holding 468 knowledge nodes. Then the
        // knowledge read was pushed into the query but capped at 200 ids while the TERM was still
        // matched in memory afterwards, so a search saw only the alphabetically first 200 of 1,255
        // and a document whose id sorted later was reported as not existing.
        //
        // A cap applied before a filter returns the wrong slice trimmed to the right shape, and
        // nothing in the result says so (DC-035). Moving one filter into the query and leaving the
        // next one outside it moves the defect rather than removing it.
        var (rows, totalMatched) = reader.KnowledgeNodes(query.Term, query.Type, limit);

        var nodes = new List<KnowledgeNodeView>();
        foreach (var (id, declaredType) in rows)
        {
            var touching = reader.AssertionsTouching(id, MaxEdgesCeiling);
            var owner = touching.FirstOrDefault(a => a.Subject == id && a.Predicate == "owned_by");
            // `review_by` and `declared_in` describe the document; they are not links to other
            // knowledge, and drawing them as such puts a date in the graph as a thing to navigate to.
            var links = touching.Where(a => a.Subject == id
                && a.Predicate is not ("has_type" or "owned_by" or "review_by" or "declared_in" or "node_class")).ToList();

            var backlinks = touching.Where(a => a.Object == id
                && a.Predicate is not ("has_type" or "owned_by" or "review_by" or "declared_in" or "node_class")).ToList();

            // Missing evidence is surfaced as a health finding rather than rendered as a clean node —
            // the spec's "absence of evidence stays explicit".
            var findings = new List<string>();
            if (owner is null)
            {
                findings.Add("owner not recorded");
            }

            if (declaredType == "unknown")
            {
                findings.Add("type not recorded");
            }

            if (links.Count == 0 && backlinks.Count == 0)
            {
                findings.Add("orphan: no inbound or outbound links");
            }

            // The type assertion carries the provenance, so it is read from the neighbours already
            // in hand rather than by a second query per node.
            var typeAssertion = touching.FirstOrDefault(a => a.Subject == id && a.Predicate == "has_type");

            if (typeAssertion?.Provenance.SourceLocation is null)
            {
                findings.Add("source location not recorded");
            }

            // A review date that has passed is the one health finding that arrives on its own: the
            // document has not changed, the calendar has. Read from the frontmatter the pack already
            // writes, so a stale artifact says so rather than waiting to be noticed.
            var reviewBy = touching.FirstOrDefault(a => a.Subject == id && a.Predicate == "review_by");

            if (reviewBy is not null
                && DateOnly.TryParse(reviewBy.Object, System.Globalization.CultureInfo.InvariantCulture, out var due)
                && due < DateOnly.FromDateTime(DateTime.UtcNow))
            {
                findings.Add($"review overdue since {due:yyyy-MM-dd}");
            }

            nodes.Add(new KnowledgeNodeView(
                id, declaredType, owner?.Object,
                links.Select(ToEdge).ToList(), backlinks.Select(ToEdge).ToList(),
                typeAssertion?.Provenance.SourceLocation, findings));
        }

        // Omitted is counted against everything that MATCHED, not against everything that was read.
        // The two were the same only while the filter ran after the cap.
        var bounds = new ResultBounds(
            limit, MaxEdgesCeiling, MaxResultBytes, nodes.Count, totalMatched - nodes.Count,
            nodes.Sum(n => n.Links.Count + n.Backlinks.Count), 0, false, null);

        return new KnowledgeResult(nodes, bounds, reader.CurrentSourceRevision());
    }

    /// <summary>
    /// The content behind one node, for a reader that already has the node.
    /// </summary>
    /// <remarks>
    /// <para><b>On demand, for the one node asked for.</b> The graph carries no content by design —
    /// fattening 1,500 nodes to serve the one a user selected is what overflowed the frame in the
    /// first place (INV-0003, ADR-0018 node-content-reader-contract).</para>
    ///
    /// <para><b>Confined to the workspace.</b> The path is rebuilt from the scope's recorded location
    /// plus the assertion's own provenance, then checked to be under the root before anything is
    /// opened. A node id arrives from a client, and a client asking is not a reason to read a file.</para>
    ///
    /// <para><b>Bounded, and honest when it truncates.</b> Oversized content returns its first bytes
    /// and a shortfall saying what was left — never an oversized frame, never a silent half-file.</para>
    /// </remarks>
    /// <summary>
    /// Lines in the workspace's own files that contain a term.
    /// </summary>
    /// <remarks>
    /// <para><b>Why this is Core's and not the client's.</b> The App must not read workspace files:
    /// two authorities on what a file contains disagree the first time one resolves a path
    /// differently (DC-022), and file access belongs on the side of the boundary that can confine it
    /// to the workspace. This is the same rule that put <c>NodeContent</c> here, applied to the
    /// corpus instead of to one node.</para>
    ///
    /// <para><b>It searches files the STORE knows about, not the directory tree.</b> Walking the
    /// tree would read <c>node_modules</c>, <c>bin</c>, and every generated bundle the extractors
    /// already decided not to index — and would return hits in files the graph cannot navigate to,
    /// which is a result a person cannot act on. Every hit names the node that owns the file.</para>
    ///
    /// <para><b>Every bound is enforced, not declared.</b> Files, matches, bytes and per-file size
    /// all cap, and the result says when a cap fired. A limit that cannot fire is the defect it was
    /// written to prevent (DC-016), and a budget that is reported but not applied is how a 1.18 MB
    /// payload crossed a 1 MiB frame (INV-0003).</para>
    /// </remarks>
    /// <summary>
    /// One caller's outgoing calls, in call order — the feed for a UML sequence diagram.
    /// </summary>
    /// <remarks>
    /// <para><b>Why this is not <c>calls</c>.</b> The <c>calls</c> edges are deduplicated to one row
    /// per <c>(caller, callee)</c> pair, which is correct for a graph and destroys an interaction:
    /// <c>A→B, A→C, A→B</c> collapses to two messages and the repeat is gone. <c>calls_at</c> keeps
    /// every site. MEASURED on TheTerrace: 2,024 sites against 1,492 deduplicated edges, so keeping
    /// them costs about a third more rows on one predicate and nothing at all on the graph payload —
    /// <c>calls_at</c> is an attribute and is never drawn.</para>
    ///
    /// <para><b>Type-level, and it says so.</b> The caller and callee are types; the member is the
    /// message name. A sequence diagram of one METHOD's activation needs method-level callers, which
    /// the C# reader does not emit — so this draws "what this type calls, in order", which is a real
    /// interaction and not the one a lifeline-per-method diagram would show. Better to hand over a
    /// true smaller thing than a plausible larger one.</para>
    /// </remarks>
    public InteractionResult Interaction(string nodeId, int maxMessages)
    {
        ArgumentException.ThrowIfNullOrEmpty(nodeId);

        using var activity = Activity.StartActivity("aide.projection.query");
        activity?.SetTag("projection", "interaction");

        var limit = Clamp(maxMessages, 1, MaxInteractionMessages);
        using var reader = store.BeginRead();

        // One more than asked for, so "is there another" is answered by looking rather than guessing.
        var found = reader.OutgoingCallsInOrder(nodeId, limit + 1);
        var truncated = found.Count > limit;

        var messages = new List<InteractionMessage>();
        var bytes = 0;
        var byteCapped = false;

        foreach (var (callee, member, location) in found.Take(limit))
        {
            var message = new InteractionMessage(
                messages.Count + 1, nodeId, callee, member, location);

            var size = Encoding.UTF8.GetByteCount(message.From)
                + Encoding.UTF8.GetByteCount(message.To)
                + Encoding.UTF8.GetByteCount(message.Member)
                + Encoding.UTF8.GetByteCount(message.Location)
                + AssertionOverheadBytes;

            if (messages.Count > 0 && bytes + size > MaxResponseBytes)
            {
                byteCapped = true;
                break;
            }

            messages.Add(message);
            bytes += size;
        }

        return new InteractionResult(
            nodeId, messages, truncated || byteCapped,
            new ResultBounds(
                MaxNodes: limit, MaxEdges: 0, MaxBytes: MaxResponseBytes,
                ReturnedNodes: messages.Count,
                OmittedNodes: Math.Max(0, found.Count - messages.Count),
                ReturnedEdges: 0, OmittedEdges: 0,
                ByteCapped: byteCapped, NextCursor: null),
            reader.CurrentSourceRevision());
    }

    /// <summary>The most messages one interaction will return.</summary>
    /// <remarks>
    /// A lifeline with 500 messages on it is not a diagram anybody reads. MEASURED on TheTerrace,
    /// the busiest single caller has 46 outgoing call sites, so this bounds the pathological case
    /// without truncating any real one.
    /// </remarks>
    public const int MaxInteractionMessages = 200;

    public ContentSearchResult SearchContent(string term, int maxMatches)
    {
        using var activity = Activity.StartActivity("aide.projection.query");
        activity?.SetTag("projection", "content-search");

        var limit = Clamp(maxMatches, 1, MaxContentMatches);
        using var reader = store.BeginRead();

        var matches = new List<ContentMatch>();
        var searched = 0;
        var bytes = 0;
        var truncated = false;

        // INV-0014 P4: the skip count, by reason. A bare integer cannot be read as a defect signal —
        // DC-229 made every TypeScript and Python file in the corpus unresolvable, and the only trace
        // was a larger number in the same place a big `node_modules` would put one. The total is the
        // SUM of these, computed once below, so the buckets and the reply can never disagree.
        var skippedNoArtifactPath = 0;
        var skippedUnresolvedPath = 0;
        var skippedUnreadable = 0;
        var skippedTooLarge = 0;

        // An empty term would match every line of every file. Refused rather than served: the
        // cheapest wrong answer here is the most expensive one to produce.
        if (!string.IsNullOrWhiteSpace(term))
        {
            foreach (var (nodeId, scopeId, artifactPath) in reader.FilesToSearch(MaxContentFiles))
            {
                if (truncated) break;

                var resolved = ResolveWithinWorkspace(reader, scopeId, artifactPath);

                if (resolved is null)
                {
                    // Classified only AFTER resolution failed, never before it: a path that resolves
                    // is searched whatever it is spelled like, so the bucket decides which kind of
                    // skip this was and changes no answer.
                    if (IsUnusableArtifactPath(artifactPath)) skippedNoArtifactPath++;
                    else skippedUnresolvedPath++;

                    continue;
                }

                long length;

                try
                {
                    length = new FileInfo(resolved).Length;
                }
                catch (Exception ex) when (ex is IOException or UnauthorizedAccessException)
                {
                    skippedUnreadable++;
                    continue;
                }

                if (length > MaxContentBytes)
                {
                    // The same ceiling NodeContent uses. A file too large to serve whole is too
                    // large to scan on a query a person is waiting on. Its own bucket, because a
                    // corpus of big generated files and a corpus nobody can open are different
                    // problems with different repairs.
                    skippedTooLarge++;
                    continue;
                }

                string text;

                try
                {
                    text = ReadBounded(resolved, out _);
                }
                catch (Exception ex) when (ex is IOException or UnauthorizedAccessException)
                {
                    skippedUnreadable++;
                    continue;
                }

                searched++;

                var line = 0;

                foreach (var raw in text.Split('\n'))
                {
                    line++;

                    if (raw.IndexOf(term, StringComparison.OrdinalIgnoreCase) < 0) continue;

                    var snippet = raw.Trim('\r', ' ', '\t');

                    if (snippet.Length > MaxContentLineCharacters)
                    {
                        snippet = snippet[..MaxContentLineCharacters];
                    }

                    var match = new ContentMatch(nodeId, artifactPath, line, snippet);

                    var size = Encoding.UTF8.GetByteCount(match.NodeId)
                        + Encoding.UTF8.GetByteCount(match.RelativePath)
                        + Encoding.UTF8.GetByteCount(match.Text)
                        + AssertionOverheadBytes;

                    if (matches.Count > 0 && (bytes + size > MaxResponseBytes || matches.Count >= limit))
                    {
                        truncated = true;
                        break;
                    }

                    matches.Add(match);
                    bytes += size;
                }
            }
        }

        var skipped =
            skippedNoArtifactPath + skippedUnresolvedPath + skippedUnreadable + skippedTooLarge;

        // Emitted on every search, zeros included: a measured zero says the search looked and found
        // none, an absent tag says nothing was recorded. Collapsing those two is how a reason code
        // becomes a plausible wrong number. Counts only — a span that named the files would put
        // repository content into telemetry (P2-PRIV-02), and the reply is opaque for the same
        // reason (see ResolveWithinWorkspace).
        activity?.SetTag("search.skipped.no_artifact_path", skippedNoArtifactPath);
        activity?.SetTag("search.skipped.unresolved_path", skippedUnresolvedPath);
        activity?.SetTag("search.skipped.unreadable", skippedUnreadable);
        activity?.SetTag("search.skipped.too_large", skippedTooLarge);

        return new ContentSearchResult(
            matches, searched, skipped, truncated,
            new ResultBounds(
                MaxNodes: limit, MaxEdges: 0, MaxBytes: MaxResponseBytes,
                ReturnedNodes: matches.Count, OmittedNodes: 0,
                ReturnedEdges: 0, OmittedEdges: 0,
                ByteCapped: truncated, NextCursor: null),
            reader.CurrentSourceRevision());
    }

    /// <summary>The most files one content search will open.</summary>
    /// <remarks>
    /// A person is waiting on this. TheTerrace has 1,178 indexed artifacts; reading all of them on
    /// every keystroke is not a search box, it is a build step.
    /// </remarks>
    public const int MaxContentFiles = 600;

    /// <summary>The most matches one content search will return.</summary>
    public const int MaxContentMatches = 200;

    /// <summary>How much of a matching line comes back.</summary>
    private const int MaxContentLineCharacters = 200;

    public NodeContent NodeContent(string nodeId)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(nodeId);

        using var activity = Activity.StartActivity("aide.projection.query");
        activity?.SetTag("projection", "node-content");

        // INV-0014 P4: every return below goes through this, so an outcome cannot be added without
        // a tag and the span can never claim `located` by omission. `error.code` is passed null on
        // the one outcome that is not an error — SetTag with a null value REMOVES the tag, so a
        // reader sees "not recorded" rather than an empty code that looks like one.
        NodeContent Recorded(string outcome, string? errorCode, NodeContent content)
        {
            activity?.SetTag("content.outcome", outcome);
            activity?.SetTag("error.code", errorCode);
            return content;
        }

        using var reader = store.BeginRead();

        // The node's own facts carry both halves of its address: the scope it belongs to, and the
        // path relative to that scope. Asked of the store directly — the first version filtered a
        // CAPPED neighbour list for it, so a node with 244 edges never found its own declaration and
        // the most connected types in the workspace reported "no recorded source" (DC-035).
        var declaring = reader.DeclaringAssertion(nodeId);

        if (declaring is null)
        {
            return Recorded(
                NodeContentOutcome.NoDeclaration,
                ProjectionErrorCodes.ContentNoDeclaration,
                new NodeContent(
                    nodeId, NodeContentKind.None, null, string.Empty, "this node has no recorded source"));
        }

        var resolved = ResolveWithinWorkspace(reader, declaring.ScopeId, declaring.Provenance.ArtifactPathId);

        if (resolved is null)
        {
            return Recorded(
                NodeContentOutcome.Unresolvable,
                ProjectionErrorCodes.ContentUnresolvable,
                new NodeContent(
                    nodeId, NodeContentKind.None, null, string.Empty,
                    $"the source for this node could not be located ({declaring.Provenance.ArtifactPathId})"));
        }

        var kind = KindOf(resolved);

        if (kind == NodeContentKind.None)
        {
            return Recorded(
                NodeContentOutcome.NotRendered,
                ProjectionErrorCodes.ContentNotRendered,
                new NodeContent(
                    nodeId, kind, null, string.Empty, $"{Path.GetExtension(resolved)} is not rendered inline"));
        }

        try
        {
            var length = new FileInfo(resolved).Length;
            var text = ReadBounded(resolved, out var truncated);

            return Recorded(
                NodeContentOutcome.Located,
                null,
                new NodeContent(
                    nodeId, kind, LanguageOf(resolved), text,
                    truncated
                        ? $"first {MaxContentBytes / 1024} KB of {length / 1024} KB — open the source for the rest"
                        : null));
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException)
        {
            // A file that cannot be read is a reader saying so, not a failed query: the node, its
            // metadata and its edges are still worth rendering.
            return Recorded(
                NodeContentOutcome.Unreadable,
                ProjectionErrorCodes.ContentUnreadable,
                new NodeContent(
                    nodeId, NodeContentKind.None, null, string.Empty,
                    $"the source could not be read: {ex.Message}"));
        }
    }

    /// <summary>How much of one artifact travels. Well inside the frame, with the rest named.</summary>
    public const int MaxContentBytes = 256 * 1024;

    /// <summary>
    /// The absolute path of an artifact, or null when it cannot be placed INSIDE the workspace.
    /// </summary>
    /// <remarks>
    /// Null covers every failure the same way on purpose — no recorded scope location, a path that
    /// escapes the root, a file that is not there. A reader needs to know it has no content; which of
    /// those it was is an operator question, and answering it in the reply would describe the
    /// filesystem to whoever asked.
    /// </remarks>
    internal string? ResolveWithinWorkspace(Store.StoreReader reader, string scopeId, string artifactPath)
    {
        var candidate = CandidateWithinWorkspace(reader, scopeId, artifactPath);
        return candidate is not null && File.Exists(candidate) ? candidate : null;
    }

    internal string? CandidateWithinWorkspace(Store.StoreReader reader, string scopeId, string artifactPath)
    {
        if (string.IsNullOrWhiteSpace(workspaceRoot)) return null;

        var location = reader.ScopeLocation(scopeId);

        if (location is null) return null;

        try
        {
            var root = Path.GetFullPath(workspaceRoot);
            var candidate = Path.GetFullPath(Path.Combine(root, location, artifactPath));

            // Compared as a path, not as a string: `C:\repo-other` starts with `C:\repo` and is not
            // inside it.
            var rooted = root.EndsWith(Path.DirectorySeparatorChar)
                ? root
                : root + Path.DirectorySeparatorChar;

            // The platform's own case rule, not a hardcoded fold. On POSIX a scope location of
            // `..` plus an artifact path spelled with the workspace's name in another case lands
            // OUTSIDE the workspace, and folding admits it - the separator-terminated prefix test
            // above defeated by the comparison beside it. See PathComparison.
            return candidate.StartsWith(rooted, PathComparison.ForThisFileSystem)
                ? candidate
                : null;
        }
        catch (Exception ex) when (ex is ArgumentException or PathTooLongException or NotSupportedException)
        {
            return null;
        }
    }

    private static string ReadBounded(string path, out bool truncated)
    {
        using var stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite);

        var length = (int)Math.Min(stream.Length, MaxContentBytes);
        truncated = stream.Length > MaxContentBytes;

        var buffer = new byte[length];
        stream.ReadExactly(buffer, 0, length);

        return Encoding.UTF8.GetString(buffer);
    }

    /// <summary>What a file is, by extension — the authority's call, so the reader does not guess.</summary>
    internal static NodeContentKind KindOf(string path) => Path.GetExtension(path).ToLowerInvariant() switch
    {
        ".cs" or ".ts" or ".tsx" or ".js" or ".jsx" or ".py" or ".sql" or ".bicep"
            or ".json" or ".yml" or ".yaml" or ".xml" or ".csproj" or ".props" or ".targets"
            or ".ps1" or ".sh" or ".razor" or ".css" => NodeContentKind.Code,
        ".md" or ".markdown" or ".txt" or ".log" => NodeContentKind.Text,
        // A document to render, not source to highlight (Ruling 93). The reader's sandbox is
        // the consumer; the code viewer still highlights it as html.
        ".html" or ".htm" => NodeContentKind.Html,
        _ => NodeContentKind.None,
    };

    internal static string? LanguageOf(string path) => Path.GetExtension(path).ToLowerInvariant() switch
    {
        ".cs" => "csharp",
        ".ts" or ".tsx" => "typescript",
        ".js" or ".jsx" => "javascript",
        ".py" => "python",
        ".sql" => "sql",
        ".bicep" => "bicep",
        ".json" => "json",
        ".yml" or ".yaml" => "yaml",
        ".xml" or ".csproj" or ".props" or ".targets" => "xml",
        ".ps1" => "powershell",
        ".sh" => "shell",
        ".razor" or ".html" or ".htm" => "html",
        ".css" => "css",
        ".md" or ".markdown" => "markdown",
        _ => null,
    };

    /// <summary>
    /// Rebuilds the labelled claim cache from facts. Public because the equality test needs to prove
    /// the stored cache equals this derivation — a cache with no such test is a second source of truth.
    /// </summary>
    public IReadOnlyList<(string Subject, string Predicate, string Object, string Status, int Count, string Revision)>
        DeriveClaimCurrent()
    {
        using var reader = store.BeginRead();
        return reader.AllCurrentAssertions()
            .GroupBy(a => (a.Subject, a.Predicate, a.Object))
            .Select(g => (
                g.Key.Subject, g.Key.Predicate, g.Key.Object,
                // The weakest status wins: a relation is only as established as its least certain
                // supporting assertion. Promoting on the strongest would manufacture confidence.
                Status: g.Max(a => a.Status).ToString(),
                Count: g.Count(),
                Revision: g.First().ArtifactRevision))
            .OrderBy(r => r.Subject, StringComparer.Ordinal)
            .ThenBy(r => r.Predicate, StringComparer.Ordinal)
            .ThenBy(r => r.Object, StringComparer.Ordinal)
            .ToList();
    }

    private static NodeView NodeOf(StoreReader reader, string nodeId)
        => new(nodeId, reader.ReadNodeKind(nodeId) ?? "unknown", reader.ReadNodeLabel(nodeId) ?? nodeId);

    private static EdgeView ToEdge(StoredAssertion a)
        => new(a.Subject, a.Predicate, a.Object, a.Status, a.Origin, a.ArtifactRevision, a.Provenance);

    /// <summary>
    /// Applies the count cap and then the byte budget. Labels come from repository content, so a
    /// count-only cap still admits a multi-megabyte payload built from adversarially long names.
    /// </summary>
    private static (List<StoredAssertion> Kept, bool ByteCapped) TakeWithinByteBudget(
        IReadOnlyList<StoredAssertion> source, int countLimit)
    {
        var kept = new List<StoredAssertion>();
        var bytes = 0;
        var capped = false;

        foreach (var assertion in source.Take(countLimit))
        {
            var size = Encoding.UTF8.GetByteCount(assertion.Subject)
                + Encoding.UTF8.GetByteCount(assertion.Predicate)
                + Encoding.UTF8.GetByteCount(assertion.Object)
                + Encoding.UTF8.GetByteCount(assertion.Provenance.ArtifactPathId);

            if (bytes + size > MaxResultBytes)
            {
                capped = true;
                break;
            }

            bytes += size;
            kept.Add(assertion);
        }

        return (kept, capped);
    }

    /// <summary>
    /// What a graph will cost on the wire, near enough to decide whether it fits.
    /// </summary>
    /// <remarks>
    /// The same shape as the assertion estimate and for the same reason: ids and labels come from
    /// repository content, so counting nodes tells you nothing about bytes. Deliberately an estimate
    /// rather than a serialisation — serialising to find out whether to serialise costs what it
    /// saves, and the budget already carries a quarter-frame of headroom for the difference.
    /// </remarks>
    private static readonly System.Text.Json.JsonSerializerOptions Wire =
        new(System.Text.Json.JsonSerializerDefaults.Web);

    /// <summary>
    /// What a graph costs ON THE WIRE, framed exactly as the transport frames it.
    /// </summary>
    /// <remarks>
    /// <para>The graph is one object, so — unlike a row-wise bound — it can simply be measured, and
    /// the thing measured is the thing the transport counts: the payload serialised, escaped, and
    /// wrapped in the envelope. <see cref="Weigh"/> counts the payload only, which is the estimate
    /// that let a 727,244-byte graph reach 1,137,104 bytes on the wire and be refused.</para>
    ///
    /// <para>Serialising twice is not free, so it is only paid where it could matter: a graph under a
    /// third of a frame cannot reach it at any inflation observed (1.57x), and returns the estimate,
    /// which is under budget by the same arithmetic.</para>
    /// </remarks>
    private static int FramedCost(WorkspaceGraph graph)
    {
        var estimate = Weigh(graph);

        if (estimate * 3 <= FrameBytes) return estimate;

        return Encoding.UTF8.GetByteCount(System.Text.Json.JsonSerializer.Serialize(
            Ipc.IpcResponse.Success(graph, Wire), Wire));
    }

    private static int FramedCost(SolutionTreeResult tree)
    {
        var estimate = Weigh(tree);

        if (estimate * 3 <= FrameBytes) return estimate;

        return Encoding.UTF8.GetByteCount(System.Text.Json.JsonSerializer.Serialize(
            Ipc.IpcResponse.Success(tree, Wire), Wire));
    }

    private static int Weigh(SolutionTreeResult tree)
    {
        var bytes = 128;
        foreach (var node in tree.Nodes)
        {
            bytes += Encoding.UTF8.GetByteCount(node.Path)
                + Encoding.UTF8.GetByteCount(node.NodeId ?? "")
                + Encoding.UTF8.GetByteCount(node.NodeKind ?? "")
                + 96;
        }

        foreach (var disclosure in tree.Disclosures)
        {
            bytes += Encoding.UTF8.GetByteCount(disclosure.Message)
                + Encoding.UTF8.GetByteCount(disclosure.Path ?? "")
                + 48;
        }

        return bytes;
    }

    private static int Weigh(WorkspaceGraph graph)
    {
        var bytes = 0;

        foreach (var node in graph.Nodes)
        {
            bytes += Encoding.UTF8.GetByteCount(node.Id)
                + Encoding.UTF8.GetByteCount(node.Label)
                + Encoding.UTF8.GetByteCount(node.Kind)
                + 64;
        }

        foreach (var edge in graph.Edges)
        {
            bytes += Encoding.UTF8.GetByteCount(edge.From)
                + Encoding.UTF8.GetByteCount(edge.To)
                + Encoding.UTF8.GetByteCount(edge.Predicate)
                + 64;
        }

        return bytes;
    }

    private static int Clamp(int requested, int min, int max) => Math.Max(min, Math.Min(requested, max));
}
