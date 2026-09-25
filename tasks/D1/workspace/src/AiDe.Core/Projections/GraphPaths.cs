using AiDe.Core.Facts;

namespace AiDe.Core.Projections;

/// <summary>Which route through the graph to look for.</summary>
/// <param name="MaxPaths">How many routes to return. What is dropped is reported, never silent.</param>
/// <param name="MaxLength">The longest route worth returning, in edges.</param>
/// <param name="Query">Which graph to search — the same filter the graph surface takes.</param>
public sealed record PathQuery(
    string From,
    string To,
    int MaxPaths = 10,
    int MaxLength = 8,
    GraphQuery? Query = null);

/// <summary>One route, as the edges that make it up.</summary>
public sealed record GraphPath(IReadOnlyList<GraphEdge> Edges)
{
    /// <summary>The weakest evidence anywhere on the route.</summary>
    /// <remarks>
    /// A chain is only as good as its worst link: one Inferred edge in a run of Verified ones makes
    /// the whole claim inferred, and presenting the route without saying so would launder a guess
    /// into a fact. <see cref="VerificationStatus"/> is ordered strongest-first, so the weakest is
    /// the maximum.
    /// </remarks>
    public VerificationStatus Status =>
        Edges.Count == 0 ? VerificationStatus.Verified : Edges.Max(e => e.Status);
}

/// <summary>The routes found, and what the search could not tell you.</summary>
/// <param name="Truncated">More routes of the same length existed than were returned.</param>
/// <param name="Reason">Why there are no paths, when there are none.</param>
public sealed record PathResult(
    IReadOnlyList<GraphPath> Paths,
    bool Truncated,
    string? Reason,
    string SourceRevision);

/// <summary>
/// How one node reaches another.
/// </summary>
/// <remarks>
/// <para><b>The question impact analysis is actually asking.</b> "What does this touch" is answered
/// by a neighbourhood; "how does the scheduler end up writing to the fixtures table" is a route, and
/// until now nothing could answer it. A user who can see two nodes and an edge count still cannot
/// tell whether a change here reaches there, or through what.</para>
///
/// <para><b>Shortest routes only, and it says so.</b> Enumerating every path between two nodes in a
/// graph of 8,602 edges is exponential and would not be read if it succeeded. This returns the
/// SHORTEST routes — all of them at that length, up to the cap — because the shortest route is the
/// one a reader can hold, and a longer one that avoids it is a different question ("is there another
/// way") that should be asked deliberately rather than answered by accident.</para>
///
/// <para><b>Directed, because dependency is directed.</b> <c>A depends_on B</c> does not mean B
/// depends on A, and a route that walks an edge backwards would answer "these are related" while
/// looking like "a change here reaches there".</para>
/// </remarks>
public static class GraphPaths
{
    /// <summary>The shortest routes from one node to another, within the graph the query names.</summary>
    public static PathResult Find(WorkspaceGraph graph, PathQuery query)
    {
        ArgumentNullException.ThrowIfNull(graph);
        ArgumentNullException.ThrowIfNull(query);

        if (string.Equals(query.From, query.To, StringComparison.Ordinal))
        {
            return new PathResult([new GraphPath([])], false, null, graph.SourceRevision);
        }

        var present = graph.Nodes.Select(n => n.Id).ToHashSet(StringComparer.Ordinal);

        // A missing endpoint is a DIFFERENT answer from "no route exists", and collapsing the two
        // would tell a user their code is unconnected when it was simply filtered out or misspelled.
        if (!present.Contains(query.From))
        {
            return new PathResult([], false, $"'{query.From}' is not in this graph", graph.SourceRevision);
        }

        if (!present.Contains(query.To))
        {
            return new PathResult([], false, $"'{query.To}' is not in this graph", graph.SourceRevision);
        }

        var outgoing = new Dictionary<string, List<GraphEdge>>(StringComparer.Ordinal);

        foreach (var edge in graph.Edges)
        {
            if (!outgoing.TryGetValue(edge.From, out var list))
            {
                outgoing[edge.From] = list = [];
            }

            list.Add(edge);
        }

        // Breadth-first, keeping EVERY predecessor at the depth a node was first reached. That is
        // what makes "all the shortest routes" possible without enumerating longer ones: a node
        // reached again at the same depth adds a route, and one reached later adds nothing.
        var depth = new Dictionary<string, int>(StringComparer.Ordinal) { [query.From] = 0 };
        var arrivals = new Dictionary<string, List<GraphEdge>>(StringComparer.Ordinal);
        var frontier = new Queue<string>();
        frontier.Enqueue(query.From);

        var found = -1;

        while (frontier.Count > 0)
        {
            var current = frontier.Dequeue();
            var next = depth[current] + 1;

            if (next > query.MaxLength) continue;
            if (found >= 0 && next > found) continue;

            if (!outgoing.TryGetValue(current, out var edges)) continue;

            foreach (var edge in edges)
            {
                if (depth.TryGetValue(edge.To, out var seen))
                {
                    // Same depth by another route: a second shortest path, not a revisit.
                    if (seen == next) Arrivals(arrivals, edge.To).Add(edge);
                    continue;
                }

                depth[edge.To] = next;
                Arrivals(arrivals, edge.To).Add(edge);

                if (string.Equals(edge.To, query.To, StringComparison.Ordinal))
                {
                    found = next;
                    continue;
                }

                frontier.Enqueue(edge.To);
            }
        }

        if (found < 0)
        {
            return new PathResult(
                [], false,
                $"no route within {query.MaxLength} edge(s)", graph.SourceRevision);
        }

        var paths = new List<GraphPath>();
        Rebuild(query.To, [], arrivals, depth, query, paths);

        var truncated = paths.Count > query.MaxPaths;

        return new PathResult(
            [.. paths.Take(query.MaxPaths)], truncated, null, graph.SourceRevision);
    }

    private static List<GraphEdge> Arrivals(
        Dictionary<string, List<GraphEdge>> arrivals, string node)
    {
        if (!arrivals.TryGetValue(node, out var list))
        {
            arrivals[node] = list = [];
        }

        return list;
    }

    /// <summary>Walks the arrival edges backwards, emitting each distinct shortest route.</summary>
    /// <remarks>
    /// Stops as soon as one more than the cap has been built: the caller only needs to know that
    /// MORE existed, and building the rest of an exponential set to count them would be the
    /// expensive half of the problem this method exists to avoid.
    /// </remarks>
    private static void Rebuild(
        string node,
        List<GraphEdge> suffix,
        Dictionary<string, List<GraphEdge>> arrivals,
        Dictionary<string, int> depth,
        PathQuery query,
        List<GraphPath> into)
    {
        if (into.Count > query.MaxPaths) return;

        if (string.Equals(node, query.From, StringComparison.Ordinal))
        {
            into.Add(new GraphPath([.. suffix]));
            return;
        }

        if (!arrivals.TryGetValue(node, out var incoming)) return;

        foreach (var edge in incoming)
        {
            // Only edges that arrive from the previous level are on a shortest route.
            if (!depth.TryGetValue(edge.From, out var from) || from + 1 != depth[node]) continue;

            suffix.Insert(0, edge);
            Rebuild(edge.From, suffix, arrivals, depth, query, into);
            suffix.RemoveAt(0);

            if (into.Count > query.MaxPaths) return;
        }
    }
}
