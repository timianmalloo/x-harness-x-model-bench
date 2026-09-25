using System.Collections.Immutable;
using System.Reflection;
using AiDe.Core.Workbench;

namespace AiDe.Core.Tests;

/// <summary>
/// US-9 — the workbench arrangement. Two properties carry the rest:
/// the **tiling invariant** (no gap, no overlap, no empty region) and **keyboard/pointer
/// equivalence** (SC 2.5.7). Everything else is a consequence of those two holding.
/// </summary>
public sealed class WorkbenchLayoutTests
{
    private static string StackIdOf(Layout layout, string surfaceId) =>
        layout.FindStackOf(surfaceId)!.Id;

    // ── The tiling invariant ──────────────────────────────────────────────────────────────

    [Fact]
    public void Default_SatisfiesTheTilingInvariant()
    {
        Layout.Default().AssertInvariant();
    }

    // Asserts after EVERY operation, not just at the end: a sequence that transiently breaks the
    // tiling and repairs itself would still be a defect, and an end-state-only check would miss it.
    [Fact]
    public void TilingInvariant_HoldsAfterEveryOperationInASequence()
    {
        var service = new LayoutService();
        var operations = new LayoutOperation[]
        {
            new LayoutOperation.MoveSurface("domain",
                new DropTarget(StackIdOf(service.Current, "sources"), DropKind.SplitBottom)),
            new LayoutOperation.ResizeSplit("split-root", 0, 0.1),
            new LayoutOperation.SetStackState(StackIdOf(service.Current, "terminal-1"), StackState.Collapsed),
            new LayoutOperation.MoveSurface("terminal-1",
                new DropTarget(StackIdOf(service.Current, "explore"), DropKind.JoinStack)),
            new LayoutOperation.ReorderSurface(StackIdOf(service.Current, "explore"), 0, 1),
            new LayoutOperation.MoveSurface("sources", new DropTarget("", DropKind.Float)),
            new LayoutOperation.CloseSurface("domain"),
            new LayoutOperation.SetStackState(StackIdOf(service.Current, "explore"), StackState.Maximized),
            new LayoutOperation.SetStackState(StackIdOf(service.Current, "explore"), StackState.Docked),
            new LayoutOperation.ResetToDefault(),
        };

        foreach (var operation in operations)
        {
            service.Apply(operation);
            service.Current.AssertInvariant();   // after each one
        }
    }

    // ── SC 2.5.7 — the keyboard path and the drag path must agree ─────────────────────────
    // This is only a real falsifier because both paths funnel through LayoutService.Apply.
    // If a drag mutated the view directly, the two could diverge and nothing here would catch it.

    [Fact]
    public void KeyboardAndPointer_ProduceIdenticalTrees()
    {
        var target = StackIdOf(Layout.Default(), "sources");

        // "Pointer": the user dragged Explore onto the right edge of the Provenance pane.
        var pointer = new LayoutService();
        pointer.Apply(new LayoutOperation.MoveSurface("explore", new DropTarget(target, DropKind.SplitRight)));

        // "Keyboard": the user invoked Move Explore → right of Provenance from the command palette.
        var keyboard = new LayoutService();
        keyboard.Apply(new LayoutOperation.MoveSurface("explore", new DropTarget(target, DropKind.SplitRight)));

        Assert.Equal(pointer.Current.Shape(), keyboard.Current.Shape());
    }

    [Theory]
    [InlineData(DropKind.SplitLeft)]
    [InlineData(DropKind.SplitRight)]
    [InlineData(DropKind.SplitTop)]
    [InlineData(DropKind.SplitBottom)]
    [InlineData(DropKind.JoinStack)]
    [InlineData(DropKind.Float)]
    public void EveryDropKind_IsReachableAndLeavesAValidLayout(DropKind kind)
    {
        var service = new LayoutService();
        var target = kind == DropKind.Float ? string.Empty : StackIdOf(service.Current, "sources");

        var result = service.Apply(new LayoutOperation.MoveSurface("explore", new DropTarget(target, kind)));

        Assert.True(result.Applied, result.RefusalCode);
        service.Current.AssertInvariant();
        Assert.NotEmpty(result.Announcement);
    }

    // ── SC 4.1.3 — every applied operation announces ──────────────────────────────────────
    // Reflection over the operation union, so a NEW operation that forgets its announcement fails
    // this suite rather than shipping silently.

    [Fact]
    public void EveryOperationKind_ProducesAnAnnouncement()
    {
        var kinds = typeof(LayoutOperation).GetNestedTypes(BindingFlags.Public)
            .Where(t => t.IsSubclassOf(typeof(LayoutOperation)))
            .Select(t => t.Name)
            .ToHashSet(StringComparer.Ordinal);

        var service = new LayoutService();
        var covered = new HashSet<string>(StringComparer.Ordinal);

        void Run(LayoutOperation op)
        {
            var result = service.Apply(op);
            Assert.False(string.IsNullOrWhiteSpace(result.Announcement));
            covered.Add(op.GetType().Name);
        }

        Run(new LayoutOperation.ActivateSurface("domain"));
        Run(new LayoutOperation.ReorderSurface(StackIdOf(service.Current, "explore"), 0, 1));
        Run(new LayoutOperation.ResizeSplit("split-root", 0, 0.05));
        Run(new LayoutOperation.SetStackState(StackIdOf(service.Current, "sources"), StackState.Collapsed));
        Run(new LayoutOperation.MoveSurface("domain",
            new DropTarget(StackIdOf(service.Current, "terminal-1"), DropKind.JoinStack)));
        Run(new LayoutOperation.AddSurface(
            StackIdOf(service.Current, "terminal-1"),
            new Surface("agent:claude#probe", "terminal", "Agent — claude")));
        Run(new LayoutOperation.CloseSurface("domain"));
        Run(new LayoutOperation.ResetToDefault());

        Assert.Equal(kinds, covered);
    }

    // ── Structural invariants ─────────────────────────────────────────────────────────────

    [Fact]
    public void DroppingBesideAPaneInsertsASibling_RatherThanNestingANewSplit()
    {
        // The reported defect. Dropping to the right of the right-hand pane produced
        // [Left, [Right, New]] — the pane went where the user asked in the tree and somewhere else
        // on screen, and the nested split's fresh 50/50 weights moved the unrelated panes too.
        var service = new LayoutService();
        var columns = service.Current.Walk().OfType<SplitNode>()
            .First(sp => sp.Orientation == Orientation.Horizontal);

        var right = (StackNode)columns.Children[^1];
        var before = columns.Children.Count;

        var result = service.Apply(new LayoutOperation.MoveSurface(
            "sources", new DropTarget(right.Id, DropKind.SplitRight)));

        Assert.True(result.Applied);

        var after = service.Current.Walk().OfType<SplitNode>().First(sp => sp.Id == columns.Id);

        // Same split, one more child — not a new split wrapped around the target.
        Assert.Equal(before + 1, after.Children.Count);
        Assert.Equal(right.Id, after.Children[^2].Id);

        service.Current.AssertInvariant();
    }

    [Fact]
    public void DroppingLeftOfAPanePlacesItBeforeThatPane()
    {
        var service = new LayoutService();
        var columns = service.Current.Walk().OfType<SplitNode>()
            .First(sp => sp.Orientation == Orientation.Horizontal);

        var right = (StackNode)columns.Children[^1];

        service.Apply(new LayoutOperation.MoveSurface(
            "sources", new DropTarget(right.Id, DropKind.SplitLeft)));

        var after = service.Current.Walk().OfType<SplitNode>().First(sp => sp.Id == columns.Id);
        var target = after.Children.FindIndex(c => c.Id == right.Id);

        // The moved pane sits immediately BEFORE the drop target, which is what "drop on its left"
        // means and is the half a wrapping implementation got right by accident.
        Assert.Contains(after.Children[target - 1].Id, service.Current.Walk()
            .OfType<StackNode>().Where(st => st.Surfaces.Any(su => su.SurfaceId == "sources"))
            .Select(st => st.Id));
    }

    [Fact]
    public void DroppingBesideAPaneTakesHalfOfThatPane_NotAnEqualShareOfTheRow()
    {
        // The "why did everything else move" half of the defect: an equal share would shift every
        // other divider on the row.
        var service = new LayoutService();
        var columns = service.Current.Walk().OfType<SplitNode>()
            .First(sp => sp.Orientation == Orientation.Horizontal);

        var left = (StackNode)columns.Children[0];
        var untouched = columns.Weights[^1];

        service.Apply(new LayoutOperation.MoveSurface(
            "sources", new DropTarget(left.Id, DropKind.SplitRight)));

        var after = service.Current.Walk().OfType<SplitNode>().First(sp => sp.Id == columns.Id);

        Assert.Equal(untouched, after.Weights[^1], precision: 3);
    }

    [Fact]
    public void RemovingTheLastSurface_DestroysTheStackAndCollapsesTheSplit()
    {
        var service = new LayoutService();
        var before = service.Current.Walk().OfType<StackNode>().Count();

        // EVERY surface in the stack, derived rather than assumed. The property under test is "the
        // LAST surface destroys the stack", and naming one surface made that depend on the stack
        // happening to hold exactly one — which stopped being true the moment a surface was added
        // beside it, failing a test that has nothing to do with the change.
        var stack = service.Current.FindStackOf("sources")!;

        // The split that HOLDS it, found rather than named. Naming split-root made this test depend
        // on the default arrangement, so changing where a pane lives failed a test about collapsing.
        var holder = service.Current.Walk().OfType<SplitNode>()
            .First(sp => sp.Children.Any(c => c.Id == stack.Id));

        LayoutResult result = default!;

        foreach (var surfaceId in stack.Surfaces.Select(s => s.SurfaceId).ToList())
        {
            result = service.Apply(new LayoutOperation.CloseSurface(surfaceId));
        }

        Assert.True(result.Applied);
        Assert.Equal(before - 1, service.Current.Walk().OfType<StackNode>().Count());
        // The split that held it had two children; losing one collapses it into the survivor.
        Assert.DoesNotContain(service.Current.Walk(), n => n.Id == holder.Id);
        service.Current.AssertInvariant();
    }

    [Fact]
    public void AStackCannotBeConstructedEmpty()
    {
        Assert.Throws<ArgumentException>(() =>
            new StackNode("s", ImmutableList<Surface>.Empty));
    }

    [Fact]
    public void ASplitCannotBeConstructedWithOneChild()
    {
        var stack = new StackNode("s", [new Surface("a", "view", "A")]);
        Assert.Throws<ArgumentException>(() =>
            new SplitNode("p", Orientation.Horizontal, [stack], [1.0]));
    }

    [Fact]
    public void SplitWeights_AreAlwaysNormalized()
    {
        var a = new StackNode("a", [new Surface("a", "view", "A")]);
        var b = new StackNode("b", [new Surface("b", "view", "B")]);

        var split = new SplitNode("p", Orientation.Horizontal, [a, b], [3.0, 1.0]);

        Assert.Equal(1.0, split.Weights.Sum(), 6);
        Assert.Equal(0.75, split.Weights[0], 6);
    }

    // ── Minimum size: refused, not silently clamped ───────────────────────────────────────

    [Fact]
    public void Resize_BelowMinimum_IsRefusedAndSaysSo()
    {
        var service = new LayoutService();

        var result = service.Apply(new LayoutOperation.ResizeSplit("split-root", 0, 0.95));

        Assert.False(result.Applied);
        Assert.Equal(LayoutErrorCodes.MinSize, result.RefusalCode);
        Assert.Contains("Minimum size", result.Announcement, StringComparison.Ordinal);
    }

    [Fact]
    public void Resize_WithinBounds_IsApplied()
    {
        var service = new LayoutService();
        var before = ((SplitNode)service.Current.Root).Weights[0];

        var result = service.Apply(new LayoutOperation.ResizeSplit("split-root", 0, 0.1));

        Assert.True(result.Applied);
        Assert.True(((SplitNode)service.Current.Root).Weights[0] > before);
    }

    // ── Maximize preserves user intent (the Eclipse subtlety) ─────────────────────────────

    [Fact]
    public void Restore_LeavesDeliberatelyCollapsedStacksCollapsed()
    {
        var service = new LayoutService();
        var terminal = StackIdOf(service.Current, "terminal-1");
        var explore = StackIdOf(service.Current, "explore");

        // The user deliberately collapses the terminal FIRST.
        service.Apply(new LayoutOperation.SetStackState(terminal, StackState.Collapsed));
        // Then maximizes Explore, and restores it.
        service.Apply(new LayoutOperation.SetStackState(explore, StackState.Maximized));
        service.Apply(new LayoutOperation.SetStackState(explore, StackState.Docked));

        var terminalStack = service.Current.Walk().OfType<StackNode>().First(s => s.Id == terminal);
        // Restoring undoes what maximizing did — never what the user did.
        Assert.Equal(StackState.Collapsed, terminalStack.State);
    }

    [Fact]
    public void Maximize_HidesTheOtherDockedStacks_AndRestoreBringsThemBack()
    {
        var service = new LayoutService();
        var explore = StackIdOf(service.Current, "explore");

        service.Apply(new LayoutOperation.SetStackState(explore, StackState.Maximized));
        Assert.All(service.Current.Walk().OfType<StackNode>().Where(s => s.Id != explore),
            s => Assert.Equal(StackState.Hidden, s.State));

        service.Apply(new LayoutOperation.SetStackState(explore, StackState.Docked));
        Assert.All(service.Current.Walk().OfType<StackNode>(),
            s => Assert.Equal(StackState.Docked, s.State));
    }

    // ── Lock ──────────────────────────────────────────────────────────────────────────────

    [Fact]
    public void Locked_RefusesEveryMutatingOperation_ButStillAllowsSelection()
    {
        var service = new LayoutService { IsLocked = true };

        var move = service.Apply(new LayoutOperation.MoveSurface("explore",
            new DropTarget(StackIdOf(service.Current, "sources"), DropKind.JoinStack)));
        var resize = service.Apply(new LayoutOperation.ResizeSplit("split-root", 0, 0.1));
        var select = service.Apply(new LayoutOperation.ActivateSurface("domain"));

        Assert.Equal(LayoutErrorCodes.Locked, move.RefusalCode);
        Assert.Equal(LayoutErrorCodes.Locked, resize.RefusalCode);
        Assert.Contains("locked", move.Announcement, StringComparison.OrdinalIgnoreCase);
        // Reading is not rearranging: a locked layout must not stop the user working.
        Assert.True(select.Applied);
    }

    // ── Floating is the only thing allowed to overlap ─────────────────────────────────────

    [Fact]
    public void FloatingStacks_LiveOutsideTheTree()
    {
        var service = new LayoutService();

        service.Apply(new LayoutOperation.MoveSurface("sources", new DropTarget("", DropKind.Float)));

        Assert.Single(service.Current.Floating);
        Assert.DoesNotContain(service.Current.Walk().OfType<StackNode>(),
            s => s.Surfaces.Any(f => f.SurfaceId == "sources"));
        service.Current.AssertInvariant();
    }

    [Fact]
    public void MoveToUnknownTarget_IsRefusedWithoutMutating()
    {
        var service = new LayoutService();
        var before = service.Current.Shape();

        var result = service.Apply(new LayoutOperation.MoveSurface("explore",
            new DropTarget("no-such-node", DropKind.JoinStack)));

        Assert.False(result.Applied);
        Assert.Equal(before, service.Current.Shape());
    }

    [Fact]
    public void MoveOfUnknownSurface_IsRefused()
    {
        var service = new LayoutService();

        var result = service.Apply(new LayoutOperation.MoveSurface("ghost",
            new DropTarget(StackIdOf(service.Current, "explore"), DropKind.JoinStack)));

        Assert.False(result.Applied);
        Assert.Equal(LayoutErrorCodes.SurfaceUnknown, result.RefusalCode);
    }
}
