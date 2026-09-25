using System.Collections.Immutable;

namespace AiDe.Core.Workbench;

public enum Orientation { Horizontal, Vertical }

/// <summary>How a stack is currently presented. Only <see cref="Floating"/> may overlap.</summary>
public enum StackState { Docked, Floating, Collapsed, Maximized, Hidden }

/// <summary>One thing the user works in. Its identity and state are independent of where it is docked.</summary>
public sealed record Surface(string SurfaceId, string Kind, string Title);

public abstract record LayoutNode(string Id);

/// <summary>
/// Divides its region among 2..n children by weights that always sum to 1.
/// </summary>
/// <remarks>
/// A split with fewer than two children is not representable: the operations collapse it into its
/// remaining child. That is what makes "no empty region" structural rather than a rule someone has
/// to remember.
/// </remarks>
public sealed record SplitNode : LayoutNode
{
    public SplitNode(string id, Orientation orientation,
        ImmutableList<LayoutNode> children, ImmutableList<double> weights)
        : base(id)
    {
        if (children.Count < 2)
        {
            throw new ArgumentException("a split holds at least two children", nameof(children));
        }

        if (children.Count != weights.Count)
        {
            throw new ArgumentException("one weight per child", nameof(weights));
        }

        Orientation = orientation;
        Children = children;
        Weights = Normalize(weights);
    }

    public Orientation Orientation { get; init; }

    public ImmutableList<LayoutNode> Children { get; init; }

    public ImmutableList<double> Weights { get; init; }

    internal static ImmutableList<double> Normalize(ImmutableList<double> weights)
    {
        var total = weights.Sum();
        return total <= 0
            ? [.. Enumerable.Repeat(1.0 / weights.Count, weights.Count)]
            : [.. weights.Select(w => w / total)];
    }
}

/// <summary>
/// A leaf region holding 1..n surfaces navigated by tabs.
/// </summary>
/// <remarks>
/// A stack with zero surfaces is not constructible. Removing the last surface destroys the stack
/// instead of emptying it — an empty region can never persist because it can never exist.
/// </remarks>
public sealed record StackNode : LayoutNode
{
    public const double DefaultMinimum = 120;

    public StackNode(string id, ImmutableList<Surface> surfaces, int activeIndex = 0,
        StackState state = StackState.Docked,
        double minWidth = DefaultMinimum, double minHeight = DefaultMinimum,
        LayoutRect? floatingBounds = null)
        : base(id)
    {
        FloatingBounds = floatingBounds;
        if (surfaces.Count == 0)
        {
            throw new ArgumentException("a stack holds at least one surface", nameof(surfaces));
        }

        Surfaces = surfaces;
        ActiveIndex = Math.Clamp(activeIndex, 0, surfaces.Count - 1);
        State = state;
        MinWidth = minWidth;
        MinHeight = minHeight;
    }

    public ImmutableList<Surface> Surfaces { get; init; }

    public int ActiveIndex { get; init; }

    public StackState State { get; init; }

    public double MinWidth { get; init; }

    public double MinHeight { get; init; }

    /// <summary>
    /// Where a floating pane sits, in virtual-screen coordinates. Null while docked.
    /// </summary>
    /// <remarks>
    /// Stored because US-9 requires a floating pane to return to the display it was on. Without it
    /// the off-screen guard has nothing to test and a restored floating pane would land wherever the
    /// shell happened to put it.
    /// </remarks>
    public LayoutRect? FloatingBounds { get; init; }

    public Surface Active => Surfaces[ActiveIndex];
}

/// <summary>Where a move will land. Computed and shown to the user *before* the move commits.</summary>
public enum DropKind { SplitLeft, SplitRight, SplitTop, SplitBottom, JoinStack, Float }

public sealed record DropTarget(string TargetNodeId, DropKind Kind);

/// <summary>
/// The whole arrangement: a docked tree plus the floating stacks held outside it.
/// </summary>
/// <remarks>
/// Floating stacks live outside the tree deliberately. A tree of proportional splits structurally
/// cannot express an overlap — which is exactly the tiling invariant — so anything permitted to
/// overlap must not be in it.
/// </remarks>
public sealed record Layout(
    LayoutNode Root,
    ImmutableList<StackNode> Floating,
    ImmutableDictionary<string, StackState> MaximizeMemo)
{
    public static Layout Default()
    {
        // Console at the bottom across the full width; workspace on the left; graph and domain on
        // the right. The console spans both columns because a terminal is used WITH whatever is
        // above it, not beside one column of it.
        var workspace = new StackNode("stack-workspace",
            [
                new Surface("explore", "view", "Explore"),
                new Surface("sources", "view", "Sources"),
                new Surface("contexts", "contexts", "Contexts"),
                new Surface("joins", "joins", "Joins"),
            ]);

        var graph = new StackNode("stack-graph",
            [
                new Surface("graph", "canvas", "Graph"),
                new Surface("domain", "view", "Domain"),
                new Surface("sessions", "sessions", "Sessions"),
                new Surface("board", "board", "Board"),
                new Surface("leaderboard", "leaderboard", "Leaderboard"),
                new Surface("ledger", "ledger", "Ledger"),
            ]);

        var terminal = new StackNode("stack-terminal",
            [new Surface("terminal-1", "terminal", "Terminal — pwsh")]);

        var columns = new SplitNode("split-columns", Orientation.Horizontal,
            [workspace, graph], [0.38, 0.62]);

        var root = new SplitNode("split-root", Orientation.Vertical,
            [columns, terminal], [0.68, 0.32]);

        return new Layout(root, [], ImmutableDictionary<string, StackState>.Empty);
    }

    public IEnumerable<LayoutNode> Walk() => Walk(Root);

    private static IEnumerable<LayoutNode> Walk(LayoutNode node)
    {
        yield return node;
        if (node is SplitNode split)
        {
            foreach (var child in split.Children)
            {
                foreach (var descendant in Walk(child))
                {
                    yield return descendant;
                }
            }
        }
    }

    /// <summary>Every stack, docked or floating.</summary>
    public IEnumerable<StackNode> AllStacks() => Walk().OfType<StackNode>().Concat(Floating);

    public StackNode? FindStackOf(string surfaceId) =>
        AllStacks().FirstOrDefault(s => s.Surfaces.Any(f => f.SurfaceId == surfaceId));

    /// <summary>
    /// The tiling invariant, checked after every operation rather than asserted once in prose:
    /// no empty stack, no under-filled split, weights summing to one, and unique ids.
    /// </summary>
    public void AssertInvariant()
    {
        var ids = new HashSet<string>(StringComparer.Ordinal);
        foreach (var node in Walk().Concat(Floating.Cast<LayoutNode>()))
        {
            if (!ids.Add(node.Id))
            {
                throw new InvalidOperationException($"duplicate node id '{node.Id}'");
            }

            switch (node)
            {
                case StackNode { Surfaces.Count: 0 }:
                    throw new InvalidOperationException($"stack '{node.Id}' has no surfaces");
                case SplitNode split when split.Children.Count < 2:
                    throw new InvalidOperationException($"split '{node.Id}' has {split.Children.Count} children");
                case SplitNode split when Math.Abs(split.Weights.Sum() - 1.0) > 1e-6:
                    throw new InvalidOperationException(
                        $"split '{node.Id}' weights sum to {split.Weights.Sum():F6}, not 1");
                default:
                    break;
            }
        }

        var surfaceIds = AllStacks().SelectMany(s => s.Surfaces).Select(s => s.SurfaceId).ToList();
        if (surfaceIds.Count != surfaceIds.Distinct(StringComparer.Ordinal).Count())
        {
            throw new InvalidOperationException("a surface appears in more than one stack");
        }
    }

    /// <summary>Structural equality ignoring generated ids — the oracle for keyboard/pointer equivalence.</summary>
    public string Shape() => Shape(Root) + "|float:" + string.Join(",", Floating.Select(Shape));

    private static string Shape(LayoutNode node) => node switch
    {
        StackNode s => $"[{string.Join("+", s.Surfaces.Select(f => f.SurfaceId))}@{s.ActiveIndex}:{s.State}]",
        SplitNode p => $"({p.Orientation}:" +
            string.Join(",", p.Children.Select((c, i) => $"{Shape(c)}#{p.Weights[i]:F3}")) + ")",
        _ => "?",
    };
}
