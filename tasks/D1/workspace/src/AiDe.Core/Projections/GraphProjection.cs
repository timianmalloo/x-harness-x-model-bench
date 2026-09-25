using AiDe.Core.Facts;

namespace AiDe.Core.Projections;

/// <summary>One node of the whole graph, with how connected it is.</summary>
/// <param name="Degree">
/// Edges touching this node. Carried because the surface has to choose what to draw, and choosing
/// without it means choosing alphabetically — which is how a graph of two thousand nodes gets
/// rendered as whichever two happened to sort first.
/// </param>
/// <param name="IsExternal">
/// True when nothing in this workspace DECLARES the node — a framework or package type that is only
/// ever pointed at.
/// </param>
/// <remarks>
/// <b>Without this the graph is mostly not the user's code.</b> Measured on a real repository: the
/// six most-connected nodes were <c>string</c>, <c>int</c>, <c>Task&lt;TResult&gt;</c>,
/// <c>DateTimeOffset</c>, <c>IReadOnlyList&lt;T&gt;</c> and <c>Guid</c> — 773 edges to
/// <c>string</c> alone. Ranking by raw degree therefore puts the BCL at the centre of a picture of
/// somebody's domain, and capping by raw degree drops their code to keep it.
/// </remarks>
/// <param name="IsKnowledge">
/// Whether the producer declared this node as knowledge rather than source.
/// </param>
/// <remarks>
/// <b>Reported by the user: the Knowledge chip read 0 on a repository holding 2,343 knowledge
/// nodes.</b> The graph carried each node's fine <c>Kind</c> — and on that repository the knowledge
/// kinds are <c>spec</c> and <c>knowledge-epl-fan-platform</c>, which is a name that repository
/// invented. A chip matching a fixed list of type names cannot work across repositories, and
/// widening the list only moves the problem to the next repository (DC-033).
///
/// The coarse class is a DECLARED dimension — the producer says it (<c>node_class</c>) — so a filter
/// can ask the question directly instead of recognising spellings.
/// </remarks>
public sealed record GraphNode(
    string Id, string Label, string Kind, int Degree, bool IsExternal, bool IsKnowledge = false);

/// <summary>One relationship, with the status of the evidence behind it.</summary>
public sealed record GraphEdge(string From, string To, string Predicate, VerificationStatus Status);

/// <summary>
/// Which part of the graph to build.
/// </summary>
/// <param name="MaxNodes">The cap. What it drops is counted and reported, never silent.</param>
/// <param name="Kinds">
/// Keep only nodes of these kinds (the values <c>has_type</c> carries — <c>class</c>,
/// <c>python-module</c>, <c>table</c>). Null or empty means every kind.
/// </param>
/// <param name="ScopeId">Keep only nodes this scope declares. Null means every scope.</param>
/// <param name="GroupId">
/// Keep only the nodes inside one overview group — the drill-down from a cluster to its contents.
/// </param>
/// <param name="IncludeExternal">
/// Whether to keep nodes nothing in the workspace declares — framework and package types.
/// </param>
/// <remarks>
/// <para><b>Why filtering belongs HERE and not at the caller.</b> A tool that wants the domain model
/// would otherwise fetch 2,813 nodes across a pipe and discard nine tenths of them, and — worse —
/// the CAP would have already chosen which nodes to send, by a ranking computed over a graph the
/// caller did not want. Filtering after a cap gives you the wrong 5,000 nodes trimmed to the right
/// kind, and nothing in the result says so.</para>
///
/// <para>So the filter runs BEFORE the cap, degree is computed over what survives it, and "most
/// connected" means most connected <em>in the graph that was asked for</em>.</para>
///
/// <para><b>The group filter takes no depth, on purpose.</b> A group id already states its own depth
/// — <c>TheTerrace.Features</c> is two segments and <c>src/app</c> is two — so the depth is read back
/// out of the id rather than passed alongside it. A separate parameter would let a caller ask for
/// <c>TheTerrace.Features</c> at depth 3 and receive nothing, with no error and no way to tell that
/// from an empty group.</para>
/// </remarks>
/// <param name="ExcludeEdges">
/// Edge predicates to leave out entirely. Null keeps every kind.
/// </param>
/// <remarks>
/// <para><b>Why excluding rather than selecting.</b> MEASURED on TheTerrace: the canvas's own default
/// spends <b>702,425 of 852,680 bytes on edges</b> — 82% — and two predicates are 74% of them
/// (<c>depends_on</c> 2,155, <c>calls</c> 1,272). Edges, not nodes, are what fills the frame, so the
/// only lever that buys a bigger picture is dropping a kind.</para>
///
/// <para>An <i>include</i> list would be a caller restating the extractors' vocabulary, and would go
/// stale silently the first time a reader emitted a predicate nobody had added to it — the shape this
/// codebase has paid for repeatedly (DC-042, DC-022). Excluding means a new predicate appears in
/// every view by default, which is the safe direction: a caller sees something unexpected rather than
/// silently missing something.</para>
///
/// <para>Applied BEFORE the cap, like every other filter here. An excluded edge frees its bytes for
/// nodes rather than being trimmed after the ranking has already been paid for (DC-035).</para>
/// </remarks>
/// <param name="ExcludeKnowledge">
/// Drop every node the producer declared knowledge (<c>node_class = knowledge</c>) rather than
/// source (Ruling 53; US-C8): Architecture's canvas asks for code, data and architecture/
/// infrastructure — never the knowledge/spec corpus Explore already reads.
/// </param>
/// <remarks>
/// <para><b>Excluding one declared flag, not an allow-list of "code/data/architecture" kind
/// spellings.</b> An allow-list would restate the extractors' <c>has_type</c> vocabulary here and go
/// stale the first time a reader emitted a spelling nobody had added to it — the exact DC-033 trap
/// this file already names for the Knowledge chip ("the knowledge kinds are <c>spec</c> and
/// <c>knowledge-epl-fan-platform</c>… widening the list only moves the problem to the next
/// repository"). <see cref="AiDe.Core.Projections.GraphNode.IsKnowledge"/> is a DECLARED dimension
/// the producer already carries for exactly this reason, so excluding by it is safe across
/// repositories the way an include-list of kind spellings is not.</para>
///
/// <para>Every non-knowledge node — code, data and architecture/infrastructure alike — passes this
/// filter, which is what makes "exclude knowledge" the same result as "keep code, data and
/// architecture" without Core ever learning that three-way taxonomy (a UI-layer concept the
/// remarks on <see cref="WorkspaceGraph.DeclaredByKind"/> already keep out of Core).</para>
/// </remarks>
public sealed record GraphQuery(
    int MaxNodes = GraphProjection.DefaultMaxNodes,
    IReadOnlyList<string>? Kinds = null,
    string? ScopeId = null,
    bool IncludeExternal = true,
    string? GroupId = null,
    IReadOnlyList<string>? ExcludeEdges = null,
    bool ExcludeKnowledge = false);

/// <summary>The whole graph, and what it left out.</summary>
/// <param name="Omitted">Nodes present in the evidence and not returned, because a cap applied.</param>
/// <param name="Disclosures">What the extraction said it could not see, lifted out of the edges.</param>
/// <param name="DeclaredByKind">
/// Every node kind the workspace declares, and how many there are — drawn or not.
/// </param>
/// <remarks>
/// <para><b>Why totals need their own field when the node total does not.</b> The overall total is
/// recoverable as <c>Nodes.Count + Omitted</c>, so a surface can already say "1,500 of 2,992". A
/// per-category total cannot be recovered that way: the omitted nodes are gone, and with them any
/// way to know what they were.</para>
///
/// <para><b>And it is not a detail.</b> MEASURED on a real workspace: 878 knowledge nodes, median
/// relation degree <b>0</b>, against a median of 4 for everything else — so under a
/// most-connected-first cap roughly 620 of them are never candidates for a slot. The surface
/// reported "Knowledge 257" with no denominator, which is true about what was drawn and reads as a
/// statement about what exists.</para>
///
/// <para><b>By KIND, not by the surface's categories.</b> Code / Data / Infra / Specs / Knowledge is
/// the canvas's taxonomy, and Core teaching itself that taxonomy would put a UI decision in the
/// projection — where it would then be wrong for every other consumer. Kinds are what Core knows;
/// the surface already has a <c>categoryOf</c> and can run it over these totals to get its own
/// denominators. MEASURED: 29 kinds, ~636 bytes.</para>
///
/// <para><b>The knowledge flag travels with each kind, rather than kind alone.</b> Measured on a
/// real workspace, no kind appears both as knowledge and as source — so kind alone WOULD work
/// today. That is a property of one corpus, not a guarantee, and a total that is silently wrong in
/// a repository where a kind is used both ways would be indistinguishable from a correct one.</para>
/// </remarks>
public sealed record WorkspaceGraph(
    IReadOnlyList<GraphNode> Nodes,
    IReadOnlyList<GraphEdge> Edges,
    int Omitted,
    IReadOnlyList<string> Disclosures,
    string SourceRevision,
    IReadOnlyList<GraphKindTotal>? DeclaredByKind = null);

/// <summary>How many nodes of one kind the workspace declares, drawn or not.</summary>
/// <param name="IsKnowledge">
/// Carried per kind rather than assumed from it: measured on a real workspace no kind is used both
/// ways, and that is one corpus rather than a rule.
/// </param>
public sealed record GraphKindTotal(string Kind, bool IsKnowledge, int Declared);

/// <summary>
/// The whole workspace as a graph, rather than one node and its neighbours.
/// </summary>
/// <remarks>
/// <para><b>The graph surface had never shown the graph.</b> It asked for one node
/// (<c>FindAsync("", 1)</c>) and then that node's neighbours, so a workspace of 12,100 assertions and
/// 2,164 nodes rendered as <b>two</b> — the alphabetically first symbol and its single neighbour.
/// Reported by the user, comparing it against the same repository in Obsidian.</para>
///
/// <para><b>Attributes are not edges.</b> <c>has_type</c>, <c>declared_in</c>, <c>api_version</c> and
/// the rest describe a node; drawing them puts the string "class" in the graph as a thing that other
/// things point at. The same rule the search already applies, applied here — one definition, in
/// <see cref="EvidencePredicates.Attributes"/>, used by both.</para>
///
/// <para><b>Bounded by DEGREE, not by name.</b> When a cap applies, the nodes kept are the ones the
/// graph is actually about: an alphabetical cut of a two-thousand-node graph is arbitrary, and looks
/// exactly like a complete small graph. What was dropped is counted, so a partial view can say so.</para>
/// </remarks>
public sealed class GraphProjection(IReadOnlyList<EvidenceAssertion> assertions, string sourceRevision)
{
    /// <summary>
    /// Nodes returned before the cap applies.
    /// </summary>
    /// <remarks>
    /// Large enough that no repository measured so far reaches it, so the common case is the WHOLE
    /// graph. A cap exists because a surface that receives ten million nodes stops responding, and a
    /// pane that stops responding tells the user nothing at all.
    /// </remarks>
    public const int DefaultMaxNodes = 5_000;

    public WorkspaceGraph Compute(int maxNodes = DefaultMaxNodes) =>
        Compute(new GraphQuery(maxNodes));

    public WorkspaceGraph Compute(GraphQuery query)
    {
        ArgumentNullException.ThrowIfNull(query);

        var disclosures = new List<string>();

        var excluded = query.ExcludeEdges is { Count: > 0 }
            ? query.ExcludeEdges.ToHashSet(StringComparer.Ordinal)
            : null;

        // Declared HERE: something in this workspace says what it is or where it lives. Everything
        // else is a name this code refers to and does not contain.
        var declared = assertions
            .Where(a => a.Predicate is "has_type" or "declared_in")
            .Select(a => a.Subject)
            .ToHashSet(StringComparer.Ordinal);

        var kinds = new Dictionary<string, string>(StringComparer.Ordinal);
        var knowledge = new HashSet<string>(StringComparer.Ordinal);
        var declaredIn = new Dictionary<string, string>(StringComparer.Ordinal);
        var mentioned = new HashSet<string>(StringComparer.Ordinal);
        var candidateEdges = new List<GraphEdge>();

        foreach (var assertion in assertions)
        {
            if (assertion.Predicate == "discloses")
            {
                disclosures.Add(assertion.Object);
                continue;
            }

            // An edge kind the caller does not want costs nothing: not an edge, and not a reason to
            // draw the node at its far end. A node this workspace DECLARES still survives, because
            // its own `has_type` mentions it — so excluding `calls` hides call relationships without
            // hiding the types that make them.
            if (excluded is not null && excluded.Contains(assertion.Predicate))
            {
                continue;
            }

            // Where a scope's files live is metadata ABOUT a scope, and a scope is not a node here —
            // every other fact naming one does so through an attribute, so scopes have never been
            // drawn. Letting this one through would put 67 directory-shaped nodes in TheTerrace's
            // graph, which is a surface change nobody asked for while adding a content reader.
            if (assertion.Predicate == "declared_at")
            {
                continue;
            }

            // An attribute describes its subject. `has_type` gives the node its kind; the others are
            // recorded as facts and are not relationships between two things.
            if (EvidencePredicates.Attributes.Contains(assertion.Predicate))
            {
                if (assertion.Predicate == "has_type")
                {
                    kinds[assertion.Subject] = assertion.Object;
                }
                else if (assertion.Predicate == "node_class" && assertion.Object == "knowledge")
                {
                    knowledge.Add(assertion.Subject);
                }
                else if (assertion.Predicate == "declared_in")
                {
                    declaredIn[assertion.Subject] = assertion.Object;
                }

                mentioned.Add(assertion.Subject);
                continue;
            }

            mentioned.Add(assertion.Subject);
            mentioned.Add(assertion.Object);

            candidateEdges.Add(new GraphEdge(
                assertion.Subject, assertion.Object, assertion.Predicate, assertion.Status));
        }

        // The FILTER, applied before the cap. Filtering afterwards would rank and trim the whole
        // graph and only then discard, so the caller would receive the wrong nodes of the right kind.
        var wanted = query.Kinds is { Count: > 0 }
            ? query.Kinds.ToHashSet(StringComparer.OrdinalIgnoreCase)
            : null;

        var included = mentioned
            .Where(id => query.IncludeExternal || declared.Contains(id))
            .Where(id => wanted is null || wanted.Contains(kinds.GetValueOrDefault(id, "external")))
            .Where(id => !query.ExcludeKnowledge || !knowledge.Contains(id))
            .Where(id => query.ScopeId is null
                || string.Equals(declaredIn.GetValueOrDefault(id), query.ScopeId, StringComparison.Ordinal))
            .Where(id => query.GroupId is null || InGroup(id, query.GroupId))
            .ToHashSet(StringComparer.Ordinal);

        // Degree is counted over the SURVIVING edges, so "most connected" means most connected in
        // the graph that was asked for rather than in one the caller filtered away.
        var edges = candidateEdges
            .Where(e => included.Contains(e.From) && included.Contains(e.To))
            .ToList();

        var degree = included.ToDictionary(id => id, _ => 0, StringComparer.Ordinal);

        foreach (var edge in edges)
        {
            degree[edge.From]++;
            degree[edge.To]++;
        }

        // DECLARED first, then by degree. A node this workspace declares is part of the thing being
        // looked at; a node it only points at is context. Ordering by degree alone put `string` at
        // the top and dropped the user's own types at the cap.
        var ordered = degree
            .OrderByDescending(kv => declared.Contains(kv.Key))
            .ThenByDescending(kv => kv.Value)
            .ThenBy(kv => kv.Key, StringComparer.Ordinal)
            .ToList();

        var nodes = ordered.Take(query.MaxNodes).ToList();
        var kept = nodes.Select(kv => kv.Key).ToHashSet(StringComparer.Ordinal);
        var omitted = Math.Max(0, ordered.Count - kept.Count);

        // An edge whose other end was dropped is dropped with it. Drawing a half-edge into nothing
        // is worse than omitting it: it looks like a node the layout failed to place.
        var visible = edges
            .Where(e => kept.Contains(e.From) && kept.Contains(e.To))
            .ToList();

        return new WorkspaceGraph(
            [.. nodes.Select(kv => new GraphNode(
                kv.Key, Label(kv.Key), kinds.GetValueOrDefault(kv.Key, "external"), kv.Value,
                IsExternal: !declared.Contains(kv.Key),
                IsKnowledge: knowledge.Contains(kv.Key)))],
            visible,
            omitted,
            // Folded by class, not deduplicated. 39 knowledge scopes each disclose their own
            // heading count, so `Distinct` merges nothing and the caller receives 108 lines for 28
            // classes — measured on a real workspace, where it filled the window and buried the one
            // finding that mattered.
            [.. AiDe.Core.Facts.DisclosureSummary.Fold(disclosures)],
            sourceRevision,
            // Counted over every node the walk SAW, not the ones that survived the cap — the whole
            // point is to be the denominator the drawn count is a numerator of.
            DeclaredByKind: [.. declared
                .GroupBy(id => (Kind: kinds.GetValueOrDefault(id, "external"), Knowledge: knowledge.Contains(id)))
                .Select(g => new GraphKindTotal(g.Key.Kind, g.Key.Knowledge, g.Count()))
                .OrderByDescending(t => t.Declared)
                .ThenBy(t => t.Kind, StringComparer.Ordinal)]);
    }

    /// <summary>
    /// Whether a node belongs to the overview group with this id.
    /// </summary>
    /// <remarks>
    /// The depth comes from the GROUP's own shape, so a drill-down cannot ask the wrong question:
    /// grouping <paramref name="id"/> to the same number of segments the group id has must produce
    /// the group id itself. Delegating to <see cref="GraphOverview.GroupFor"/> keeps one definition
    /// of "which group is this in" — two would put a node in a cluster the overview does not have.
    /// </remarks>
    private static bool InGroup(string id, string groupId)
    {
        var separator = groupId.Contains('/', StringComparison.Ordinal) ? '/' : '.';
        var depth = groupId.Contains('#', StringComparison.Ordinal)
            ? 1
            : groupId.Split(separator).Length;

        return string.Equals(GraphOverview.GroupFor(id, depth), groupId, StringComparison.Ordinal);
    }

    /// <summary>
    /// The short name a reader recognises, keeping the scope prefix where there is one.
    /// </summary>
    /// <remarks>
    /// A fully-qualified name is unreadable at graph scale and a bare last segment is ambiguous, so
    /// this keeps <c>bicep:main#siteName</c> whole and shortens a dotted symbol to its last part.
    /// </remarks>
    private static string Label(string id)
    {
        if (id.Contains(':', StringComparison.Ordinal)) return id;

        var cut = id.LastIndexOf('.');
        return cut > 0 && cut < id.Length - 1 ? id[(cut + 1)..] : id;
    }
}
