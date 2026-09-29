using AiDe.Core.Facts;

namespace AiDe.Core.Projections;

/// <summary>One group of nodes, drawn as a single thing.</summary>
/// <param name="Id">The grouping key — a namespace prefix, a directory, or a scope.</param>
/// <param name="NodeCount">How many nodes this stands for. The number that makes it honest.</param>
/// <param name="InternalEdges">Edges wholly inside the group, which the overview does not draw.</param>
/// <param name="IsExternal">True when nothing in the workspace declares anything in this group.</param>
public sealed record GraphCluster(
    string Id, string Label, int NodeCount, int InternalEdges, bool IsExternal);

/// <summary>A relationship between two groups, and how much of it there is.</summary>
/// <param name="Weight">Underlying edges this stands for — the thickness a renderer wants.</param>
/// <param name="Status">
/// The WEAKEST evidence among the edges aggregated here. A bundle drawn as Verified because most of
/// its members were would launder the inferred ones.
/// </param>
public sealed record ClusterEdge(
    string From, string To, int Weight, VerificationStatus Status);

/// <summary>The workspace at a distance, and what it stands for.</summary>
/// <param name="Depth">How many identifier segments were used to group.</param>
/// <param name="TotalNodes">Nodes summarised, so a caller can say "1,500 in 42 groups".</param>
/// <param name="OmittedClusters">Groups dropped because a cap applied.</param>
public sealed record WorkspaceOverview(
    IReadOnlyList<GraphCluster> Clusters,
    IReadOnlyList<ClusterEdge> Edges,
    int Depth,
    int TotalNodes,
    int TotalEdges,
    int OmittedClusters,
    IReadOnlyList<string> Disclosures,
    string SourceRevision);

/// <summary>How to summarise the workspace.</summary>
/// <param name="Depth">
/// Identifier segments to group by. 1 gives the coarsest picture (one group per top-level namespace
/// or directory) and each increment is one step of zoom.
///
/// <para><b>The default is 3, chosen from measurement across three repositories rather than from
/// taste.</b> Links between groups, by depth:</para>
/// <code>
/// TheTerrace                d1:  74 groups,  1 link    d2: 200,  6    d3: 200, 263
/// BioHacker                 d1:   9 groups,  0 links   d2:  48,  6    d3: 200, 323
/// meridian-finance-planner  d1:  89 groups,  6 links   d2: 156, 18    d3: 200,  93
/// </code>
/// <para>Depths 1 and 2 are almost linkless in ALL THREE, and for a reason that is arithmetic rather
/// than accidental: at a coarse grain nearly every edge is internal to a group, so it is counted and
/// not drawn. A picture of disconnected islands is correct and tells a reader nothing about
/// structure. Structure appears at 3. The first default shipped as 2 — the useless one — and only a
/// second and third repository made that visible as a pattern rather than a quirk.</para>
/// </param>
/// <param name="MaxClusters">
/// Groups returned before the rest are counted and dropped. MEASURED on a real repository: at depth
/// 3 this workspace has 689 groups, and returning 200 of them is a hairball at a coarser grain — the
/// exact failure the overview exists to prevent, and one this parameter's first default walked
/// straight into. Sixty is about what a person takes in at once; the groups kept are the largest of
/// the user's own code and the rest are counted.
/// </param>
/// <param name="Query">Which nodes to summarise — the same filter the graph surface takes.</param>
public sealed record OverviewQuery(
    int Depth = 3,
    int MaxClusters = 60,
    GraphQuery? Query = null);

/// <summary>
/// The workspace summarised into groups, for a graph too large to show node by node.
/// </summary>
/// <remarks>
/// <para><b>The half of DC-035 that was still open.</b> The bounded default fixed the transport
/// failure by drawing 1,500 of 2,118 declared nodes and saying so — which is honest, and is still a
/// truncation rather than an overview. A user looking at a repository wants to see its SHAPE first;
/// 1,500 dots is not a shape, and the 618 that were dropped are not the difference between
/// understanding it and not.</para>
///
/// <para><b>Grouping by identifier prefix, and why that is not a hack.</b> Every id in this graph is
/// already hierarchical because the languages are: a C# symbol is
/// <c>TheTerrace.Features.Competitions.Season</c>, a module is <c>src/app/models</c>. The first
/// <c>Depth</c> segments name the thing a developer would call "where that lives", and increasing
/// Depth is exactly the zoom control a level-of-detail view needs. No clustering algorithm is used,
/// deliberately: a community-detection result is unstable under small changes to the graph, so the
/// same repository would regroup between two indexes and the picture would move for reasons the user
/// cannot see.</para>
///
/// <para><b>What it must never do is hide the count.</b> A group drawn as one dot standing for 240
/// types is only honest while the 240 is on it — that is the whole difference between an overview and
/// a smaller lie.</para>
/// </remarks>
public static class GraphOverview
{
    /// <summary>Deepest grouping worth offering; past this a group is usually one node.</summary>
    public const int MaxDepth = 6;

    /// <summary>Summarise a graph that has already been projected and filtered.</summary>
    public static WorkspaceOverview Summarise(WorkspaceGraph graph, OverviewQuery query)
    {
        ArgumentNullException.ThrowIfNull(graph);
        ArgumentNullException.ThrowIfNull(query);

        var depth = Math.Clamp(query.Depth, 1, MaxDepth);

        var groupOf = new Dictionary<string, string>(StringComparer.Ordinal);
        var counts = new Dictionary<string, int>(StringComparer.Ordinal);
        var internalEdges = new Dictionary<string, int>(StringComparer.Ordinal);
        var external = new Dictionary<string, bool>(StringComparer.Ordinal);

        foreach (var node in graph.Nodes)
        {
            var group = GroupFor(node.Id, depth);
            groupOf[node.Id] = group;
            counts[group] = counts.GetValueOrDefault(group) + 1;

            // A group is external only when EVERY node in it is. One declared type makes the group
            // part of this workspace, and colouring it as a package would hide the user's own code
            // inside something they think they can ignore.
            external[group] = external.GetValueOrDefault(group, true) && node.IsExternal;
        }

        var between = new Dictionary<(string From, string To), (int Weight, VerificationStatus Status)>();

        foreach (var edge in graph.Edges)
        {
            if (!groupOf.TryGetValue(edge.From, out var from) || !groupOf.TryGetValue(edge.To, out var to))
            {
                continue;
            }

            if (string.Equals(from, to, StringComparison.Ordinal))
            {
                // Counted, not drawn. A self-loop on every group is noise, but "240 types that only
                // talk to each other" and "240 types wired to everything" are different pictures.
                internalEdges[from] = internalEdges.GetValueOrDefault(from) + 1;
                continue;
            }

            var key = (from, to);

            if (between.TryGetValue(key, out var existing))
            {
                // VerificationStatus is ordered strongest-first, so Max is the WEAKEST.
                between[key] = (existing.Weight + 1, (VerificationStatus)Math.Max(
                    (int)existing.Status, (int)edge.Status));
            }
            else
            {
                between[key] = (1, edge.Status);
            }
        }

        // Ordered the same way the node graph is: this workspace's own code first, then by size.
        // A cap that kept the biggest package group and dropped the user's smallest namespace would
        // repeat the mistake IsExternal was added to fix.
        var ordered = counts
            .OrderByDescending(kv => !external[kv.Key])
            .ThenByDescending(kv => kv.Value)
            .ThenBy(kv => kv.Key, StringComparer.Ordinal)
            .ToList();

        var kept = ordered.Take(Math.Max(1, query.MaxClusters)).ToList();
        var visible = kept.Select(kv => kv.Key).ToHashSet(StringComparer.Ordinal);

        return new WorkspaceOverview(
            [.. kept.Select(kv => new GraphCluster(
                kv.Key, Label(kv.Key), kv.Value,
                internalEdges.GetValueOrDefault(kv.Key), external[kv.Key]))],
            [.. between
                .Where(e => visible.Contains(e.Key.From) && visible.Contains(e.Key.To))
                .Select(e => new ClusterEdge(e.Key.From, e.Key.To, e.Value.Weight, e.Value.Status))
                .OrderByDescending(e => e.Weight)
                .ThenBy(e => e.From, StringComparer.Ordinal)
                .ThenBy(e => e.To, StringComparer.Ordinal)],
            depth,
            graph.Nodes.Count,
            graph.Edges.Count,
            Math.Max(0, ordered.Count - kept.Count),
            graph.Disclosures,
            graph.SourceRevision);
    }

    /// <summary>
    /// The group an id belongs to at a given depth.
    /// </summary>
    /// <remarks>
    /// <para><b>Public because a renderer needs the SAME answer.</b> A canvas colouring detail nodes
    /// by group, or drawing a node inside its cluster, has to agree with the overview about which
    /// group a node is in. Two definitions of one grouping is the shape of DC-022 — a predicate with
    /// two producers — and the divergence would show as a node drawn in the wrong cluster, which
    /// looks like a layout bug and is not one.</para>
    ///
    /// <para>Both separators are handled because both are real: C# symbols are dotted, modules are paths,
    /// and a scope-prefixed id like <c>bicep:main#siteName</c> has neither. An id with fewer segments
    /// than the depth IS its own group — grouping it under a shorter prefix that no other node shares
    /// would invent a container the repository does not have.</para>
    /// </remarks>
    public static string GroupFor(string id, int depth)
    {
        // A scope-qualified id names its container already; splitting past the marker would group
        // every scope's `main` together.
        var marker = id.IndexOf('#', StringComparison.Ordinal);
        if (marker > 0) return id[..marker];

        var separator = id.Contains('/', StringComparison.Ordinal) ? '/' : '.';
        var segments = id.Split(separator);

        return segments.Length <= depth ? id : string.Join(separator, segments.Take(depth));
    }

    private static string Label(string group)
    {
        var separator = group.Contains('/', StringComparison.Ordinal) ? '/' : '.';
        var segments = group.Split(separator);

        // The last two segments read as a place ("Features.Competitions") where the last alone is
        // ambiguous across a repository and the whole thing is too long to render on a dot.
        return segments.Length <= 2 ? group : string.Join(separator, segments.TakeLast(2));
    }
}
