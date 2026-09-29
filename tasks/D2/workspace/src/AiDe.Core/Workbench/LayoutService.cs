using System.Collections.Immutable;
using System.Diagnostics;
using System.Globalization;

namespace AiDe.Core.Workbench;

public static class LayoutErrorCodes
{
    public const string MinSize = "AIDE-LAYOUT-MIN-SIZE";
    public const string Locked = "AIDE-LAYOUT-LOCKED";
    public const string InvalidTarget = "AIDE-LAYOUT-INVALID-TARGET";
    public const string SurfaceUnknown = "AIDE-LAYOUT-SURFACE-UNKNOWN";
    public const string Unreadable = "AIDE-LAYOUT-UNREADABLE";
    public const string VersionUnsupported = "AIDE-LAYOUT-VERSION-UNSUPPORTED";
    public const string PartialRestore = "AIDE-LAYOUT-PARTIAL-RESTORE";
}

/// <summary>
/// One arrangement change. **Both the pointer and the keyboard produce these** — that is what makes
/// "the keyboard path and the drag path produce the same result" (SC 2.5.7) a testable property
/// rather than a hope.
/// </summary>
public abstract record LayoutOperation
{
    public sealed record MoveSurface(string SurfaceId, DropTarget Target) : LayoutOperation;

    public sealed record ResizeSplit(string SplitId, int EdgeIndex, double Delta) : LayoutOperation;

    public sealed record SetStackState(string StackId, StackState State) : LayoutOperation;

    public sealed record ActivateSurface(string SurfaceId) : LayoutOperation;

    public sealed record ReorderSurface(string StackId, int From, int To) : LayoutOperation;

    public sealed record CloseSurface(string SurfaceId) : LayoutOperation;

    /// <summary>Adds a new surface as a tab in an existing stack.</summary>
    /// <remarks>
    /// Into a STACK rather than a new pane: a second terminal is another tab beside the first, not a
    /// second region competing for the same space. The caller names the stack so the choice of where
    /// stays with whoever knows why.
    /// </remarks>
    public sealed record AddSurface(string StackId, Surface Surface) : LayoutOperation;

    public sealed record ResetToDefault : LayoutOperation;
}

/// <summary>
/// The outcome of an <see cref="ILayoutService.Apply"/>. Carries the announcement, so an operation
/// that mutates the layout without telling assistive technology is not expressible (SC 4.1.3).
/// </summary>
public sealed record LayoutResult(Layout Layout, bool Applied, string? RefusalCode, string Announcement);

public interface ILayoutService
{
    Layout Current { get; }

    bool IsLocked { get; set; }

    LayoutResult Apply(LayoutOperation operation);

    /// <summary>
    /// Puts back a previously observed layout. Used to cancel an in-flight interaction — a keyboard
    /// resize abandoned with Escape must return exactly to where it started, and replaying inverse
    /// operations would accumulate rounding error instead.
    /// </summary>
    void Restore(Layout layout);
}

/// <summary>
/// The single mutation path for the workbench arrangement.
/// </summary>
/// <remarks>
/// Pattern: Command + immutable aggregate. Every gesture — pointer drag, keyboard command, palette
/// entry — is funnelled through <see cref="Apply"/>, which validates, applies, re-checks the tiling
/// invariant and produces the announcement. Refusals are values, not exceptions: hitting a minimum
/// size is an ordinary outcome the UI reports, not an error path.
/// </remarks>
public sealed class LayoutService(Layout? initial = null) : ILayoutService
{
    private static readonly ActivitySource Activity = new("aide.workbench.operation");
    private int _idCounter;

    public Layout Current { get; private set; } = initial ?? Layout.Default();

    public bool IsLocked { get; set; }

    public void Restore(Layout layout)
    {
        layout.AssertInvariant();
        Current = layout;
    }

    public LayoutResult Apply(LayoutOperation operation)
    {
        using var activity = Activity.StartActivity("aide.workbench.operation");
        activity?.SetTag("operation.kind", operation.GetType().Name);

        if (IsLocked && operation is not LayoutOperation.ActivateSurface)
        {
            return Refuse(LayoutErrorCodes.Locked, "Layout is locked. Unlock to rearrange panes.", activity);
        }

        LayoutResult result;
        try
        {
            result = operation switch
            {
                LayoutOperation.MoveSurface op => MoveSurface(op),
                LayoutOperation.ResizeSplit op => ResizeSplit(op),
                LayoutOperation.SetStackState op => SetStackState(op),
                LayoutOperation.ActivateSurface op => ActivateSurface(op),
                LayoutOperation.ReorderSurface op => ReorderSurface(op),
                LayoutOperation.CloseSurface op => CloseSurface(op),
                LayoutOperation.AddSurface op => AddSurface(op),
                LayoutOperation.ResetToDefault => new LayoutResult(
                    Layout.Default(), true, null, "Workbench layout reset to the default."),
                _ => Refuse(LayoutErrorCodes.InvalidTarget, "Unsupported layout operation.", activity),
            };
        }
        catch (InvalidOperationException ex)
        {
            // A refused operation must never leave a half-applied tree behind.
            return Refuse(LayoutErrorCodes.InvalidTarget, ex.Message, activity);
        }

        if (result.Applied)
        {
            result.Layout.AssertInvariant();
            Current = result.Layout;
        }

        activity?.SetTag("outcome", result.Applied ? "applied" : "refused");
        activity?.SetTag("error.code", result.RefusalCode);
        return result;
    }

    private LayoutResult Refuse(string code, string announcement, Activity? activity)
    {
        activity?.SetTag("outcome", "refused");
        activity?.SetTag("error.code", code);
        return new LayoutResult(Current, false, code, announcement);
    }

    private string NextId(string prefix) =>
        string.Create(CultureInfo.InvariantCulture, $"{prefix}-{++_idCounter}");

    // ── operations ────────────────────────────────────────────────────────────────────────

    private LayoutResult MoveSurface(LayoutOperation.MoveSurface op)
    {
        var source = Current.FindStackOf(op.SurfaceId);
        if (source is null)
        {
            return new LayoutResult(Current, false, LayoutErrorCodes.SurfaceUnknown,
                $"No surface “{op.SurfaceId}”.");
        }

        var surface = source.Surfaces.First(s => s.SurfaceId == op.SurfaceId);

        // Detach first, so a move into the surface's own stack is a no-op rather than a duplicate.
        var detached = Detach(Current, op.SurfaceId);
        if (detached is null)
        {
            return new LayoutResult(Current, false, LayoutErrorCodes.InvalidTarget,
                "That move would empty the workbench.");
        }

        if (op.Target.Kind == DropKind.Float)
        {
            var floated = new StackNode(NextId("stack"), [surface], 0, StackState.Floating);
            var next = detached with { Floating = detached.Floating.Add(floated) };
            return new LayoutResult(next, true, null, $"{surface.Title} is now floating.");
        }

        var target = detached.Walk().FirstOrDefault(n => n.Id == op.Target.TargetNodeId)
            ?? detached.Floating.FirstOrDefault(n => n.Id == op.Target.TargetNodeId);
        if (target is null)
        {
            return new LayoutResult(Current, false, LayoutErrorCodes.InvalidTarget,
                "That destination is no longer available.");
        }

        if (op.Target.Kind == DropKind.JoinStack)
        {
            if (target is not StackNode stack)
            {
                return new LayoutResult(Current, false, LayoutErrorCodes.InvalidTarget,
                    "A surface can only join a pane.");
            }

            var joined = stack with
            {
                Surfaces = stack.Surfaces.Add(surface),
                ActiveIndex = stack.Surfaces.Count,
            };
            var next = Replace(detached, stack.Id, joined);
            return new LayoutResult(next, true, null,
                $"{surface.Title} moved into {stack.Surfaces[0].Title}.");
        }

        var newStack = new StackNode(NextId("stack"), [surface]);
        var orientation = op.Target.Kind is DropKind.SplitLeft or DropKind.SplitRight
            ? Orientation.Horizontal
            : Orientation.Vertical;
        var before = op.Target.Kind is DropKind.SplitLeft or DropKind.SplitTop;

        // INSERT AS A SIBLING when the target already sits in a split of the same orientation.
        //
        // Wrapping unconditionally is what made a drop look like a reorder: dropping to the right of
        // the right-hand pane of [Left, Right] produced [Left, [Right, New]] — the pane went where
        // the user asked in the tree and somewhere else on screen, and the new nested split reset
        // its weights to 50/50 so the unrelated panes moved too.
        var parent = ParentOf(detached.Root, target.Id);
        Layout replaced;

        if (parent is SplitNode host && host.Orientation == orientation)
        {
            var index = host.Children.FindIndex(c => c.Id == target.Id);
            var at = before ? index : index + 1;

            // The new pane takes half of the TARGET's width, not an equal share of the whole split.
            // Taking an equal share would move every other divider on the row, which is the "why did
            // everything else move" half of the same defect.
            var weights = host.Weights.ToBuilder();
            var half = weights[index] / 2;
            weights[index] = half;
            weights.Insert(at, half);

            var grown = host with
            {
                Children = host.Children.Insert(at, newStack),
                Weights = SplitNode.Normalize(weights.ToImmutable()),
            };

            replaced = Replace(detached, host.Id, grown);
        }
        else
        {
            // Different orientation, or the target is the root: a new split is the only way to
            // express the arrangement.
            ImmutableList<LayoutNode> children = before ? [newStack, target] : [target, newStack];
            var split = new SplitNode(NextId("split"), orientation, children, [0.5, 0.5]);
            replaced = Replace(detached, target.Id, split);
        }

        var where = op.Target.Kind.ToString().Replace("Split", string.Empty).ToLowerInvariant();
        return new LayoutResult(replaced, true, null, $"{surface.Title} moved to the {where}.");
    }

    private LayoutResult AddSurface(LayoutOperation.AddSurface op)
    {
        if (Current.Walk().FirstOrDefault(n => n.Id == op.StackId) is not StackNode stack)
        {
            return new LayoutResult(Current, false, LayoutErrorCodes.InvalidTarget, "No such pane.");
        }

        if (stack.Surfaces.Any(s => s.SurfaceId == op.Surface.SurfaceId))
        {
            // Already there. Activated rather than duplicated: asking twice for the same surface is
            // a user expecting to be taken to it, not to get a second one.
            return ActivateSurface(new LayoutOperation.ActivateSurface(op.Surface.SurfaceId));
        }

        var grown = stack with
        {
            Surfaces = stack.Surfaces.Add(op.Surface),
            ActiveIndex = stack.Surfaces.Count,
        };

        return new LayoutResult(
            Replace(Current, stack.Id, grown), true, null, $"{op.Surface.Title} opened.");
    }

    private LayoutResult ResizeSplit(LayoutOperation.ResizeSplit op)
    {
        if (Current.Walk().FirstOrDefault(n => n.Id == op.SplitId) is not SplitNode split)
        {
            return new LayoutResult(Current, false, LayoutErrorCodes.InvalidTarget, "No such divider.");
        }

        if (op.EdgeIndex < 0 || op.EdgeIndex >= split.Children.Count - 1)
        {
            return new LayoutResult(Current, false, LayoutErrorCodes.InvalidTarget, "No such divider.");
        }

        var weights = split.Weights.ToBuilder();
        var a = weights[op.EdgeIndex] + op.Delta;
        var b = weights[op.EdgeIndex + 1] - op.Delta;

        // A minimum expressed as a weight floor: refuse rather than clamp, so the user is told the
        // move did not happen instead of silently getting a different result than they asked for.
        const double MinWeight = 0.08;
        if (a < MinWeight || b < MinWeight)
        {
            return new LayoutResult(Current, false, LayoutErrorCodes.MinSize, "Minimum size reached.");
        }

        weights[op.EdgeIndex] = a;
        weights[op.EdgeIndex + 1] = b;
        var next = Replace(Current, split.Id, split with { Weights = SplitNode.Normalize(weights.ToImmutable()) });
        return new LayoutResult(next, true, null,
            string.Create(CultureInfo.InvariantCulture, $"Divider moved. {a * 100:F0} percent."));
    }

    private LayoutResult SetStackState(LayoutOperation.SetStackState op)
    {
        var stack = Current.AllStacks().FirstOrDefault(s => s.Id == op.StackId);
        if (stack is null)
        {
            return new LayoutResult(Current, false, LayoutErrorCodes.InvalidTarget, "No such pane.");
        }

        // Maximize records exactly which stacks IT changed, so restoring undoes what maximizing did
        // and never what the user did. Eclipse gets this right and it is the subtle half of the
        // feature: a pane the user deliberately collapsed must still be collapsed afterwards.
        if (op.State == StackState.Maximized)
        {
            var memo = ImmutableDictionary.CreateBuilder<string, StackState>(StringComparer.Ordinal);
            var next = Current;
            foreach (var other in Current.Walk().OfType<StackNode>().Where(s => s.Id != stack.Id))
            {
                if (other.State == StackState.Docked)
                {
                    memo[other.Id] = other.State;
                    next = Replace(next, other.Id, other with { State = StackState.Hidden });
                }
            }

            next = Replace(next, stack.Id, stack with { State = StackState.Maximized });
            return new LayoutResult(next with { MaximizeMemo = memo.ToImmutable() }, true, null,
                $"{stack.Active.Title} maximized.");
        }

        if (stack.State == StackState.Maximized && op.State == StackState.Docked)
        {
            var next = Replace(Current, stack.Id, stack with { State = StackState.Docked });
            foreach (var (id, previous) in Current.MaximizeMemo)
            {
                if (next.Walk().OfType<StackNode>().FirstOrDefault(s => s.Id == id) is { } restored)
                {
                    next = Replace(next, id, restored with { State = previous });
                }
            }

            return new LayoutResult(next with { MaximizeMemo = ImmutableDictionary<string, StackState>.Empty },
                true, null, $"{stack.Active.Title} restored.");
        }

        var updated = Replace(Current, stack.Id, stack with { State = op.State });
        var verb = op.State switch
        {
            StackState.Collapsed => "collapsed. Its surfaces remain available by name",
            StackState.Hidden => "hidden",
            StackState.Floating => "floating",
            _ => "docked",
        };
        return new LayoutResult(updated, true, null, $"{stack.Active.Title} {verb}.");
    }

    private LayoutResult ActivateSurface(LayoutOperation.ActivateSurface op)
    {
        var stack = Current.FindStackOf(op.SurfaceId);
        if (stack is null)
        {
            return new LayoutResult(Current, false, LayoutErrorCodes.SurfaceUnknown, "No such surface.");
        }

        var index = stack.Surfaces.FindIndex(s => s.SurfaceId == op.SurfaceId);
        var next = Replace(Current, stack.Id, stack with { ActiveIndex = index });
        return new LayoutResult(next, true, null, $"{stack.Surfaces[index].Title} selected.");
    }

    private LayoutResult ReorderSurface(LayoutOperation.ReorderSurface op)
    {
        if (Current.AllStacks().FirstOrDefault(s => s.Id == op.StackId) is not { } stack)
        {
            return new LayoutResult(Current, false, LayoutErrorCodes.InvalidTarget, "No such pane.");
        }

        if (op.From < 0 || op.From >= stack.Surfaces.Count || op.To < 0 || op.To >= stack.Surfaces.Count)
        {
            return new LayoutResult(Current, false, LayoutErrorCodes.InvalidTarget, "No such tab.");
        }

        var moved = stack.Surfaces[op.From];
        var surfaces = stack.Surfaces.RemoveAt(op.From).Insert(op.To, moved);
        var next = Replace(Current, stack.Id, stack with { Surfaces = surfaces, ActiveIndex = op.To });
        return new LayoutResult(next, true, null, $"{moved.Title} moved to position {op.To + 1}.");
    }

    private LayoutResult CloseSurface(LayoutOperation.CloseSurface op)
    {
        var stack = Current.FindStackOf(op.SurfaceId);
        if (stack is null)
        {
            return new LayoutResult(Current, false, LayoutErrorCodes.SurfaceUnknown, "No such surface.");
        }

        var title = stack.Surfaces.First(s => s.SurfaceId == op.SurfaceId).Title;
        var next = Detach(Current, op.SurfaceId);
        return next is null
            ? new LayoutResult(Current, false, LayoutErrorCodes.InvalidTarget,
                "The last pane cannot be closed.")
            : new LayoutResult(next, true, null, $"{title} closed.");
    }

    // ── tree surgery ──────────────────────────────────────────────────────────────────────

    /// <summary>
    /// Removes a surface, destroying its stack when it was the last one and collapsing the parent
    /// split when that leaves a single child. Returns null when the workbench would be emptied.
    /// </summary>
    internal static Layout? Detach(Layout layout, string surfaceId)
    {
        var stack = layout.FindStackOf(surfaceId);
        if (stack is null)
        {
            return layout;
        }

        if (stack.Surfaces.Count > 1)
        {
            var index = stack.Surfaces.FindIndex(s => s.SurfaceId == surfaceId);
            var trimmed = stack with
            {
                Surfaces = stack.Surfaces.RemoveAt(index),
                ActiveIndex = Math.Max(0, Math.Min(stack.ActiveIndex, stack.Surfaces.Count - 2)),
            };
            return layout.Floating.Any(f => f.Id == stack.Id)
                ? layout with { Floating = layout.Floating.Replace(stack, trimmed) }
                : Replace(layout, stack.Id, trimmed);
        }

        // Last surface in the stack: the stack itself goes.
        if (layout.Floating.Any(f => f.Id == stack.Id))
        {
            return layout with { Floating = layout.Floating.RemoveAll(f => f.Id == stack.Id) };
        }

        var pruned = Remove(layout.Root, stack.Id);
        return pruned is null ? null : layout with { Root = pruned };
    }

    private static LayoutNode? Remove(LayoutNode node, string id)
    {
        if (node.Id == id)
        {
            return null;
        }

        if (node is not SplitNode split)
        {
            return node;
        }

        var children = ImmutableList.CreateBuilder<LayoutNode>();
        var weights = ImmutableList.CreateBuilder<double>();
        for (var i = 0; i < split.Children.Count; i++)
        {
            var kept = Remove(split.Children[i], id);
            if (kept is not null)
            {
                children.Add(kept);
                weights.Add(split.Weights[i]);
            }
        }

        return children.Count switch
        {
            0 => null,
            // A split with one child is not a split — collapse it into the child so no empty
            // region and no degenerate node can persist.
            1 => children[0],
            _ => split with { Children = children.ToImmutable(), Weights = SplitNode.Normalize(weights.ToImmutable()) },
        };
    }

    internal static Layout Replace(Layout layout, string id, LayoutNode replacement)
    {
        if (layout.Floating.FirstOrDefault(f => f.Id == id) is { } floating && replacement is StackNode s)
        {
            return layout with { Floating = layout.Floating.Replace(floating, s) };
        }

        return layout with { Root = Replace(layout.Root, id, replacement) };
    }

    /// <summary>The split that directly contains <paramref name="id"/>, or null for the root.</summary>
    /// <remarks>
    /// Needed because a drop beside a pane must know whether a suitable split already exists. Walking
    /// for it each time rather than storing parent links: the tree is immutable and small, and a
    /// stored parent is a second thing that can disagree with the structure.
    /// </remarks>
    private static SplitNode? ParentOf(LayoutNode node, string id)
    {
        if (node is not SplitNode split) return null;
        if (split.Children.Any(c => c.Id == id)) return split;

        foreach (var child in split.Children)
        {
            var found = ParentOf(child, id);
            if (found is not null) return found;
        }

        return null;
    }

    private static LayoutNode Replace(LayoutNode node, string id, LayoutNode replacement)
    {
        if (node.Id == id)
        {
            return replacement;
        }

        return node is SplitNode split
            ? split with { Children = [.. split.Children.Select(c => Replace(c, id, replacement))] }
            : node;
    }
}
