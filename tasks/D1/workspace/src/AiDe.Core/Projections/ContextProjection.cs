using AiDe.Core.Extraction;

namespace AiDe.Core.Projections;

/// <summary>One context as the domain view draws it.</summary>
/// <param name="Crossings">
/// Edges leaving this context for another. The number that matters in a context map — a context with
/// no crossings is isolated, and one with hundreds is not bounded.
/// </param>
public sealed record ContextView(
    string Name,
    string? Description,
    int Symbols,
    int InternalEdges,
    int Crossings);

/// <summary>One symbol-level edge that crosses a context boundary.</summary>
public sealed record CrossingMember(string Subject, string Predicate, string Object);

/// <summary>One relationship between contexts, and how much traffic it carries.</summary>
/// <param name="Weight">Every edge counted, including any beyond <paramref name="Members"/>.</param>
/// <param name="Members">
/// The edges themselves, capped.
/// </param>
/// <remarks>
/// <b>A count is not evidence.</b> "Editorial → Football, 47 edges" is a number the user cannot
/// check, act on, or disagree with; the 47 edges are the thing they came for, and until the count
/// can be opened it is an assertion about their code that they have to take on trust. Capped
/// because a crossing can run to thousands and a pane that renders all of them is a pane that
/// stops responding — <see cref="Weight"/> stays the true total, so the cap never becomes a
/// quieter wrong number.
/// </remarks>
public sealed record ContextEdge(
    string From,
    string To,
    int Weight,
    IReadOnlyList<CrossingMember> Members)
{
    public const int MemberCap = 200;

    /// <summary>
    /// The share of listed members one object must reach before the crossing is called dominated.
    /// </summary>
    /// <remarks>
    /// Half. Not tuned — chosen because "most of this crossing is one thing" is the claim being
    /// made, and a majority is what that sentence means. A lower bar would flag ordinary coupling
    /// to a widely-used type; a higher one would have missed nothing real yet and is not worth the
    /// extra digit of false precision.
    /// </remarks>
    public const double DominanceShare = 0.5;

    /// <summary>How many edges exist beyond the ones listed.</summary>
    public int Undisclosed => Math.Max(0, Weight - Members.Count);

    /// <summary>
    /// The single object most of this crossing points at, or null when no one object dominates.
    /// </summary>
    /// <remarks>
    /// <para><b>Found by eye once, so now it is computed.</b> On a real repository 57 of the 72
    /// Football-to-Operations edges were one class — <c>AppDbContext</c> — which made a boundary
    /// that mostly holds look like one that never did. Nothing in the tool said so; a human read a
    /// list. A signal a person has to notice is a signal that gets noticed once.</para>
    ///
    /// <para>Computed over the LISTED members, so a capped crossing reports the share of what it
    /// actually examined rather than extrapolating to the full weight. <see cref="Undisclosed"/>
    /// stays beside it, because a majority of 200 out of 4,000 is a different statement.</para>
    /// </remarks>
    public CrossingMember? DominantTarget =>
        Members.Count == 0
            ? null
            : Members
                .GroupBy(m => m.Object, StringComparer.Ordinal)
                .Where(g => g.Count() > Members.Count * DominanceShare)
                .OrderByDescending(g => g.Count())
                .Select(g => g.First())
                .FirstOrDefault();

    /// <summary>How many listed members point at <see cref="DominantTarget"/>.</summary>
    public int DominantCount =>
        DominantTarget is { } target
            ? Members.Count(m => string.Equals(m.Object, target.Object, StringComparison.Ordinal))
            : 0;
}

/// <summary>Symbols outside every context, gathered by the namespace they live in.</summary>
/// <remarks>
/// <b>A percentage is not a task.</b> "68% covered" tells the user a number and gives them nowhere
/// to start; six namespaces ranked by size tells them which declaration to write next. The grouping
/// is presentation only — nothing here assigns a symbol to a context, because a symbol placed in
/// "the nearest" context is inference dressed as a declaration, which is exactly what ADR-0016
/// rejected folder convention for.
/// </remarks>
public sealed record UncoveredGroup(string Namespace, int Symbols, IReadOnlyList<string> Examples);

/// <summary>The domain view: contexts, what connects them, and what belongs to none.</summary>
/// <param name="IsDeclared">
/// Whether a context map exists at all.
/// </param>
/// <remarks>
/// <b>Absence is not coverage.</b> Measured on a second repository, which has no
/// <c>bounded-contexts.yaml</c>: the pane reported zero uncovered symbols and said "every declared
/// symbol belongs to a context", which is the sentence a fully-mapped codebase produces. Nothing was
/// wrong with the arithmetic — no map means no uncovered list — and that is exactly why it needed a
/// separate field rather than a cleverer count.
/// </remarks>
public sealed record ContextMapView(
    IReadOnlyList<ContextView> Contexts,
    IReadOnlyList<ContextEdge> Edges,
    int UncoveredSymbols,
    IReadOnlyList<string> Problems,
    IReadOnlyList<UncoveredGroup> UncoveredGroups,
    bool IsDeclared = true)
{
    public bool IsValid => Problems.Count == 0;
}

/// <summary>
/// Groups the graph by declared bounded context (ADR-0016).
/// </summary>
/// <remarks>
/// <para><b>This is what makes the joins legible.</b> A <c>maps_to</c> edge inside one context is
/// unremarkable; the same edge crossing two contexts is a coupling someone chose, and until the
/// contexts are drawn there is no way to tell those apart.</para>
///
/// <para><b>Uncovered symbols are counted, never assigned.</b> Placing a symbol in "the nearest"
/// context would be inference dressed as a declaration — the exact thing ADR-0016 rejected folder
/// convention for.</para>
/// </remarks>
public sealed class ContextProjection(BoundedContextMap map, IReadOnlyList<Facts.EvidenceAssertion> assertions)
{
    public ContextMapView Compute()
    {
        if (!map.IsValid)
        {
            // An invalid map draws NOTHING. A partially-applied context map is a diagram that is
            // wrong in a way nobody can see, which is worse than an absent one.
            return new ContextMapView([], [], map.TotalSymbols,
                [.. map.Problems.Select(p => p.Message)], [], map.IsDeclared);
        }

        var relational = assertions
            .Where(a => !Facts.EvidencePredicates.Attributes.Contains(a.Predicate))
            .ToList();

        // Owners are resolved for subjects AND objects of relational edges. Resolving only subjects
        // left every node that appears solely as a target — which is most of them — outside every
        // context, so a crossing between two contexts was silently counted as no crossing at all.
        var owner = new Dictionary<string, string>(StringComparer.Ordinal);
        foreach (var node in assertions.Select(a => a.Subject)
            .Concat(relational.Select(a => a.Object))
            .Distinct(StringComparer.Ordinal))
        {
            var context = map.Contexts.FirstOrDefault(c => c.Includes.Any(p => BoundedContextReader.Matches(p, node)));
            if (context is not null) owner[node] = context.Name;
        }

        var internalEdges = new Dictionary<string, int>(StringComparer.Ordinal);
        var crossings = new Dictionary<(string From, string To), int>();
        var members = new Dictionary<(string From, string To), List<CrossingMember>>();

        foreach (var edge in relational)
        {
            if (!owner.TryGetValue(edge.Subject, out var from)) continue;
            if (!owner.TryGetValue(edge.Object, out var to)) continue;

            if (string.Equals(from, to, StringComparison.Ordinal))
            {
                internalEdges[from] = internalEdges.GetValueOrDefault(from) + 1;
                continue;
            }

            // Direction is kept. "Editorial reads Football" and "Football reads Editorial" are
            // different statements about who depends on whom, and a context map that collapsed them
            // would hide the one thing it exists to show.
            crossings[(from, to)] = crossings.GetValueOrDefault((from, to)) + 1;

            var bucket = members.TryGetValue((from, to), out var existing)
                ? existing
                : members[(from, to)] = [];

            if (bucket.Count < ContextEdge.MemberCap)
            {
                bucket.Add(new CrossingMember(edge.Subject, edge.Predicate, edge.Object));
            }
        }

        var views = map.Contexts.Select(c =>
        {
            var symbols = owner.Count(kv => string.Equals(kv.Value, c.Name, StringComparison.Ordinal));
            var outward = crossings.Where(kv => kv.Key.From == c.Name).Sum(kv => kv.Value);
            var inward = crossings.Where(kv => kv.Key.To == c.Name).Sum(kv => kv.Value);

            return new ContextView(
                c.Name, c.Description, symbols, internalEdges.GetValueOrDefault(c.Name), outward + inward);
        }).ToList();

        var edges = crossings
            .Select(kv => new ContextEdge(kv.Key.From, kv.Key.To, kv.Value,
                members.TryGetValue(kv.Key, out var m) ? m : []))
            .OrderByDescending(e => e.Weight)
            .ToList();

        return new ContextMapView(
            views, edges, map.Uncovered.Count, [], GroupUncovered(map.Uncovered), map.IsDeclared);
    }

    /// <summary>
    /// Ranks the uncovered symbols by the namespace they sit in, largest first.
    /// </summary>
    /// <remarks>
    /// The namespace is the symbol's own text, split at the last dot — not a guess at which context
    /// it belongs to. A symbol with no dot is grouped under "(no namespace)" rather than dropped:
    /// silently omitting the ones that do not fit the shape is how a coverage report starts
    /// disagreeing with the coverage number beside it.
    /// </remarks>
    internal static IReadOnlyList<UncoveredGroup> GroupUncovered(IReadOnlyList<string> uncovered) =>
        [.. uncovered
            .GroupBy(NamespaceOf, StringComparer.Ordinal)
            .Select(g => new UncoveredGroup(
                g.Key,
                g.Count(),
                [.. g.Order(StringComparer.Ordinal).Take(5)]))
            .OrderByDescending(g => g.Symbols)
            .ThenBy(g => g.Namespace, StringComparer.Ordinal)];

    private static string NamespaceOf(string symbol)
    {
        var cut = symbol.LastIndexOf('.');
        return cut > 0 ? symbol[..cut] : "(no namespace)";
    }
}
