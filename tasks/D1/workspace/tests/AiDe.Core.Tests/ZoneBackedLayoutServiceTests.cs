using System.Collections.Immutable;
using AiDe.Core.Workbench;

namespace AiDe.Core.Tests;

/// <summary>
/// The Strangler service: an <see cref="ILayoutService"/> backed by the zone model. Tree-shaped
/// operations translate to zone-scoped ones, and the projected <see cref="ILayoutService.Current"/>
/// tree is always the fixed frame — so a close or an add cannot relocate an unrelated pane (DC-063).
/// </summary>
public sealed class ZoneBackedLayoutServiceTests
{
    private static ILayoutService Service() => new ZoneBackedLayoutService();

    [Fact]
    public void Current_IsTheFixedFrame_WithDeterministicZoneStackIds()
    {
        var ids = Service().Current.AllStacks().Select(s => s.Id).ToHashSet();
        Assert.Contains(ZonesToTree.CenterStackId, ids);
        Assert.Contains(ZonesToTree.LeftStackId, ids);
        Assert.Contains(ZonesToTree.BottomStackId, ids);
    }

    [Fact]
    public void AddSurface_ToAZone_AppearsThere_AndLeavesOtherZonesStackContentsUnchanged()
    {
        var svc = Service();
        var leftBefore = StackSurfaces(svc, ZonesToTree.LeftStackId);
        var centerBefore = StackSurfaces(svc, ZonesToTree.CenterStackId);

        var result = svc.Apply(new LayoutOperation.AddSurface(
            ZonesToTree.BottomStackId, new Surface("diag", "diagnostics", "Diagnostics")));
        Assert.True(result.Applied);

        Assert.Contains("diag", StackSurfaces(svc, ZonesToTree.BottomStackId));
        Assert.Equal(leftBefore, StackSurfaces(svc, ZonesToTree.LeftStackId));      // no flip
        Assert.Equal(centerBefore, StackSurfaces(svc, ZonesToTree.CenterStackId));  // no flip
    }

    [Fact]
    public void CloseSurface_RemovesItWithoutRelocatingOtherZones()
    {
        var svc = Service();
        var bottomBefore = StackSurfaces(svc, ZonesToTree.BottomStackId);
        var leftBefore = StackSurfaces(svc, ZonesToTree.LeftStackId);

        // Close a Center document.
        var result = svc.Apply(new LayoutOperation.CloseSurface("domain"));
        Assert.True(result.Applied);

        Assert.DoesNotContain("domain", svc.Current.AllStacks().SelectMany(s => s.Surfaces).Select(s => s.SurfaceId));
        Assert.Equal(bottomBefore, StackSurfaces(svc, ZonesToTree.BottomStackId));  // the terminal did not move
        Assert.Equal(leftBefore, StackSurfaces(svc, ZonesToTree.LeftStackId));      // explorers did not move
    }

    [Fact]
    public void MoveSurface_JoiningAZoneStack_MovesItToThatZoneOnly()
    {
        var svc = Service();
        var target = new DropTarget(ZonesToTree.LeftStackId, DropKind.JoinStack);

        var result = svc.Apply(new LayoutOperation.MoveSurface("terminal-1", target));
        Assert.True(result.Applied);

        Assert.Contains("terminal-1", StackSurfaces(svc, ZonesToTree.LeftStackId));
        // Bottom is now empty of the terminal — and because it becomes empty it is omitted from the frame.
        Assert.DoesNotContain(ZonesToTree.BottomStackId, svc.Current.AllStacks().Select(s => s.Id));
    }

    [Fact]
    public void ActivateSurface_SelectsTheTab_WithoutMovingAnything()
    {
        var svc = Service();
        var surfacesBefore = svc.Current.AllStacks()
            .SelectMany(s => s.Surfaces).Select(s => s.SurfaceId).OrderBy(x => x).ToList();

        var result = svc.Apply(new LayoutOperation.ActivateSurface("joins"));
        Assert.True(result.Applied);

        var surfacesAfter = svc.Current.AllStacks()
            .SelectMany(s => s.Surfaces).Select(s => s.SurfaceId).OrderBy(x => x).ToList();
        Assert.Equal(surfacesBefore, surfacesAfter); // same surfaces in the same zones; only the active tab changed
    }

    [Fact]
    public void Locked_RefusesEverythingExceptActivate()
    {
        var svc = Service();
        svc.IsLocked = true;

        Assert.False(svc.Apply(new LayoutOperation.CloseSurface("graph")).Applied);
        Assert.True(svc.Apply(new LayoutOperation.ActivateSurface("graph")).Applied);
    }

    [Fact]
    public void Restore_FromATree_RebuildsTheZones()
    {
        var svc = Service();
        svc.Apply(new LayoutOperation.AddSurface(ZonesToTree.RightStackId, new Surface("outline", "view", "Outline")));
        var saved = svc.Current;

        var fresh = Service();
        fresh.Restore(saved);

        Assert.Equal("outline", fresh.Current.AllStacks()
            .SelectMany(s => s.Surfaces).Select(s => s.SurfaceId).FirstOrDefault(x => x == "outline"));
    }

    [Fact]
    public void ResetToDefault_ReturnsTheDefaultFrame()
    {
        var svc = Service();
        svc.Apply(new LayoutOperation.CloseSurface("graph"));
        var result = svc.Apply(new LayoutOperation.ResetToDefault());
        Assert.True(result.Applied);
        Assert.Contains("graph", svc.Current.AllStacks().SelectMany(s => s.Surfaces).Select(s => s.SurfaceId));
    }

    [Fact]
    public void Restore_AfterANativeDragBetweenZones_FollowsTheDropByPosition_NotByKind()
    {
        var svc = new ZoneBackedLayoutService(WorkbenchLayout.Default());
        var tree = svc.Current; // Vertical[ Horizontal[zone-left, zone-center], zone-bottom ]

        var left = tree.AllStacks().Single(s => s.Id == ZonesToTree.LeftStackId);
        var center = tree.AllStacks().Single(s => s.Id == ZonesToTree.CenterStackId);
        var bottom = tree.AllStacks().Single(s => s.Id == ZonesToTree.BottomStackId);
        var domain = center.Surfaces.Single(s => s.SurfaceId == "domain"); // a Center document (kind "view")

        // Simulate the user dragging "domain" out of the Center pane into the Bottom pane.
        var center2 = new StackNode("c", center.Surfaces.Remove(domain));
        var bottom2 = new StackNode("b", bottom.Surfaces.Add(domain));
        var post = new Layout(
            new SplitNode("root", Orientation.Vertical,
                [new SplitNode("cols", Orientation.Horizontal, [left, center2], [0.3, 0.7]), bottom2],
                [0.7, 0.3]),
            [], ImmutableDictionary<string, StackState>.Empty);

        svc.Restore(post);

        // Position wins: "domain" is now in the Bottom zone — a kind-based reconcile would have snapped
        // it back to the Center (its "view" kind).
        Assert.Equal(ZoneId.Bottom, svc.Zones.FindZoneOf("domain"));
        Assert.Equal(ZoneId.Center, svc.Zones.FindZoneOf("graph")); // untouched Center doc stayed
    }

    [Fact]
    public void Restore_OfAnUnmappableTree_FallsBackToConversion_WithoutLosingSurfaces()
    {
        var svc = new ZoneBackedLayoutService(WorkbenchLayout.Default());

        // A shape the position mapper will not recognise for the current 2-column occupancy: 3 columns.
        var a = new StackNode("a", [new Surface("x", "view", "X")]);
        var b = new StackNode("b", [new Surface("y", "canvas", "Y")]);
        var c = new StackNode("c", [new Surface("z", "view", "Z")]);
        var weird = new Layout(
            new SplitNode("cols", Orientation.Horizontal, [a, b, c], [0.33, 0.34, 0.33]),
            [], ImmutableDictionary<string, StackState>.Empty);

        svc.Restore(weird);

        // Falls back to kind-based conversion; every surface survives and lands in a deterministic zone.
        var all = svc.Current.AllStacks().SelectMany(s => s.Surfaces).Select(s => s.SurfaceId).ToHashSet();
        Assert.Contains("x", all);
        Assert.Contains("y", all);
        Assert.Contains("z", all);
        Assert.Equal(ZoneId.Center, svc.Zones.FindZoneOf("y")); // canvas → Center by kind
    }

    [Fact]
    public void Restore_AfterASideDropCreatingAnExtraRightColumn_LandsInTheRightZone_NotTheCenter()
    {
        var svc = new ZoneBackedLayoutService(WorkbenchLayout.Default());
        var tree = svc.Current;

        var left = tree.AllStacks().Single(s => s.Id == ZonesToTree.LeftStackId);
        var center = tree.AllStacks().Single(s => s.Id == ZonesToTree.CenterStackId);
        var bottom = tree.AllStacks().Single(s => s.Id == ZonesToTree.BottomStackId);
        var sessions = center.Surfaces.Single(s => s.SurfaceId == "sessions");

        // A native side-drop split "sessions" out into its own extra column on the RIGHT.
        var center2 = new StackNode("c", center.Surfaces.Remove(sessions));
        var extra = new StackNode("extra", [sessions]);
        var post = new Layout(
            new SplitNode("root", Orientation.Vertical,
                [new SplitNode("cols", Orientation.Horizontal, [left, center2, extra], [0.25, 0.5, 0.25]), bottom],
                [0.7, 0.3]),
            [], ImmutableDictionary<string, StackState>.Empty);

        svc.Restore(post);

        // Content-anchored: the extra column sits right of the Center, so it lands in the Right zone —
        // not merged into the Center as the old index-based mapper did.
        Assert.Equal(ZoneId.Right, svc.Zones.FindZoneOf("sessions"));
        Assert.Equal(ZoneId.Left, svc.Zones.FindZoneOf("explore"));  // Left untouched
        Assert.Equal(ZoneId.Center, svc.Zones.FindZoneOf("graph"));  // Center kept its documents
    }

    [Fact]
    public void Restore_WhenTheDraggedColumnReadsLeftmost_KeepsTheExplorersInLeft_NoScatter()
    {
        // The reported bug: a pane dropped near the right landed in the Left zone AND pushed the Left
        // explorers into the Center — because the old mapper called column[0] "Left" by raw index. With
        // anchor identification the explorers keep the Left identity no matter the dragged column's position.
        var svc = new ZoneBackedLayoutService(WorkbenchLayout.Default());
        var prompt = new Surface("prompt-1", "prompt", "Prompt");
        svc.Apply(new LayoutOperation.AddSurface(ZonesToTree.BottomStackId, prompt)); // prompt starts in the Bottom

        var tree = svc.Current;
        var left = tree.AllStacks().Single(s => s.Id == ZonesToTree.LeftStackId);
        var center = tree.AllStacks().Single(s => s.Id == ZonesToTree.CenterStackId);
        var bottom = tree.AllStacks().Single(s => s.Id == ZonesToTree.BottomStackId);

        // AvalonDock placed the dragged prompt column FIRST (leftmost), ahead of the real Left column;
        // the prompt left the Bottom.
        var promptCol = new StackNode("p", [prompt]);
        var bottom2 = new StackNode("b", bottom.Surfaces.RemoveAll(s => s.SurfaceId == "prompt-1"));
        var post = new Layout(
            new SplitNode("root", Orientation.Vertical,
                [new SplitNode("cols", Orientation.Horizontal, [promptCol, left, center], [0.2, 0.2, 0.6]), bottom2],
                [0.7, 0.3]),
            [], ImmutableDictionary<string, StackState>.Empty);

        svc.Restore(post);

        // The explorers stayed in Left (no scatter into Center); the prompt joined the Left side.
        Assert.Equal(ZoneId.Left, svc.Zones.FindZoneOf("explore"));
        Assert.Equal(ZoneId.Left, svc.Zones.FindZoneOf("joins"));
        Assert.Equal(ZoneId.Center, svc.Zones.FindZoneOf("graph")); // Center kept its documents
        Assert.Equal(ZoneId.Left, svc.Zones.FindZoneOf("prompt-1"));
    }

    [Fact]
    public void Restore_DraggingABottomPaneToANewRightColumn_LandsInTheRightZone()
    {
        // The exact report: a prompt draft created in the Bottom, dragged up to the top-right, must land
        // in the Right zone — not the Center (old index mapper) and not the Left (the scatter bug).
        var svc = new ZoneBackedLayoutService(WorkbenchLayout.Default());
        var prompt = new Surface("prompt-1", "prompt", "Prompt");
        svc.Apply(new LayoutOperation.AddSurface(ZonesToTree.BottomStackId, prompt));

        var tree = svc.Current;
        var left = tree.AllStacks().Single(s => s.Id == ZonesToTree.LeftStackId);
        var center = tree.AllStacks().Single(s => s.Id == ZonesToTree.CenterStackId);
        var bottom = tree.AllStacks().Single(s => s.Id == ZonesToTree.BottomStackId);

        // Dropped as a new RIGHTMOST column; removed from the Bottom.
        var promptCol = new StackNode("p", [prompt]);
        var bottom2 = new StackNode("b", bottom.Surfaces.RemoveAll(s => s.SurfaceId == "prompt-1"));
        var post = new Layout(
            new SplitNode("root", Orientation.Vertical,
                [new SplitNode("cols", Orientation.Horizontal, [left, center, promptCol], [0.2, 0.6, 0.2]), bottom2],
                [0.7, 0.3]),
            [], ImmutableDictionary<string, StackState>.Empty);

        svc.Restore(post);

        Assert.Equal(ZoneId.Right, svc.Zones.FindZoneOf("prompt-1")); // where the user dropped it
        Assert.Equal(ZoneId.Left, svc.Zones.FindZoneOf("explore"));   // explorers untouched
        Assert.Equal(ZoneId.Center, svc.Zones.FindZoneOf("graph"));   // Center untouched
    }

    [Fact]
    public void ReconcileFromView_WhenPositionMappingFails_LeavesTheModelUnchanged_NoScatter()
    {
        var svc = new ZoneBackedLayoutService(WorkbenchLayout.Default());
        var before = svc.Zones.Shape();

        // An unmappable shape (surfaces the model does not know). Restore would kind-convert and could
        // move a bystander zone; ReconcileFromView must instead leave the model exactly as it was.
        var a = new StackNode("a", [new Surface("x", "view", "X")]);
        var b = new StackNode("b", [new Surface("y", "canvas", "Y")]);
        var weird = new Layout(
            new SplitNode("cols", Orientation.Horizontal, [a, b], [0.5, 0.5]),
            [], ImmutableDictionary<string, StackState>.Empty);

        var applied = svc.ReconcileFromView(weird);

        Assert.False(applied);
        Assert.Equal(before, svc.Zones.Shape()); // every bystander zone is exactly where it was — no scatter
    }

    // INV-0006's class, SH-1's seam note, measured by SH-2's create-failure control: a reconcile
    // used to rebuild every stack with ActiveIndex 0, so the tab the user was looking at moved on
    // the next render. The view's active tab per zone is carried into the model.
    [Fact]
    public void ReconcileFromView_KeepsTheViewsActiveTabInEveryZone()
    {
        var svc = new ZoneBackedLayoutService(WorkbenchLayout.Default());
        svc.Apply(new LayoutOperation.ActivateSurface("board"));   // Center's fourth tab is active in the model
        var tree = svc.Current;
        var left = tree.AllStacks().Single(s => s.Id == ZonesToTree.LeftStackId);
        var center = tree.AllStacks().Single(s => s.Id == ZonesToTree.CenterStackId);
        var bottom = tree.AllStacks().Single(s => s.Id == ZonesToTree.BottomStackId);

        // The view shows Left's third tab and Center's "board"; the tree the adapter reads carries both.
        var leftView = new StackNode(left.Id, left.Surfaces, activeIndex: 2);
        var centerView = new StackNode(center.Id, center.Surfaces, activeIndex: center.Surfaces.IndexOf(center.Surfaces.Single(x => x.SurfaceId == "board")));
        var post = new Layout(
            new SplitNode("root", Orientation.Vertical,
                [new SplitNode("cols", Orientation.Horizontal, [leftView, centerView], [0.3, 0.7]), bottom],
                [0.7, 0.3]),
            [], ImmutableDictionary<string, StackState>.Empty);

        Assert.True(svc.ReconcileFromView(post));

        Assert.Equal("contexts", ((ZoneStack)svc.Zones.Zone(ZoneId.Left).Content!).Active.SurfaceId);
        Assert.Equal("board", ((ZoneStack)svc.Zones.Zone(ZoneId.Center).Content!).Active.SurfaceId);
    }

    [Fact]
    public void ReconcileFromView_WhenPositionMappingSucceeds_Applies()
    {
        var svc = new ZoneBackedLayoutService(WorkbenchLayout.Default());
        var tree = svc.Current;
        var left = tree.AllStacks().Single(s => s.Id == ZonesToTree.LeftStackId);
        var center = tree.AllStacks().Single(s => s.Id == ZonesToTree.CenterStackId);
        var bottom = tree.AllStacks().Single(s => s.Id == ZonesToTree.BottomStackId);
        var domain = center.Surfaces.Single(s => s.SurfaceId == "domain");

        var center2 = new StackNode("c", center.Surfaces.Remove(domain));
        var bottom2 = new StackNode("b", bottom.Surfaces.Add(domain));
        var post = new Layout(
            new SplitNode("root", Orientation.Vertical,
                [new SplitNode("cols", Orientation.Horizontal, [left, center2], [0.3, 0.7]), bottom2],
                [0.7, 0.3]),
            [], ImmutableDictionary<string, StackState>.Empty);

        var applied = svc.ReconcileFromView(post);

        Assert.True(applied);
        Assert.Equal(ZoneId.Bottom, svc.Zones.FindZoneOf("domain"));
        Assert.Equal(ZoneId.Left, svc.Zones.FindZoneOf("explore")); // bystander untouched
    }

    /// <summary>
    /// INV-0006 F3 as re-pointed by F-1 (Rulings 83/88; SH-4.2): a collapsed tool zone that still
    /// HOLDS panes is absent from the view by design, and the reconcile keeps what it holds — the
    /// drag is applied; the collapsed zone keeps its panes and stays collapsed. Before F-1 this
    /// test pinned the opposite (the refusal, then the only honest outcome of a mapping that
    /// pre-seeded the zone empty); <c>Workbench/ReconcileTests</c> carries the red record.
    /// </summary>
    [Fact]
    public void ReconcileFromView_WithACollapsedZoneStillHoldingPanes_AppliesTheDrag_AndKeepsTheRailsPanes()
    {
        var collapsed = ZoneLayoutService.CollapseZone(WorkbenchLayout.Default(), ZoneId.Left).Layout;
        var svc = new ZoneBackedLayoutService(collapsed);
        var held = svc.Zones.Zone(ZoneId.Left).Surfaces().Select(s => s.SurfaceId).ToList();

        var applied = svc.ReconcileFromView(DomainDraggedIntoTheBottom(svc.Current, withLeftColumn: false));

        Assert.True(applied);
        Assert.Equal(ZoneId.Bottom, svc.Zones.FindZoneOf("domain"));
        Assert.Equal(held, svc.Zones.Zone(ZoneId.Left).Surfaces().Select(s => s.SurfaceId));
        Assert.True(svc.Zones.Zone(ZoneId.Left).Collapsed);
    }

    /// <summary>
    /// The other half, which is what makes "expand it and move the pane again" an honest thing to
    /// announce rather than a guess: the SAME drag is applied once the zone is expanded.
    /// </summary>
    [Fact]
    public void ReconcileFromView_WithNoZoneCollapsed_AppliesTheSameDrag()
    {
        var svc = new ZoneBackedLayoutService(WorkbenchLayout.Default());

        var applied = svc.ReconcileFromView(DomainDraggedIntoTheBottom(svc.Current, withLeftColumn: true));

        Assert.True(applied);
        Assert.Equal(ZoneId.Bottom, svc.Zones.FindZoneOf("domain"));
        Assert.Equal(ZoneId.Left, svc.Zones.FindZoneOf("explore"));   // bystander untouched
    }

    /// <summary>
    /// SH-3: Coding's default before any session opens (Ruling 55d/60) leaves Center with NO model
    /// surfaces at all — only <see cref="ZonesToTree.WelcomePlaceholder"/>, which is view-only and
    /// never in the model — so <c>AnchorFor(Center)</c>'s majority-membership test can never match
    /// it. Center is mandatory, so the one column neither Left nor Right claims IS Center, by
    /// elimination. Without this, every native drag in a fresh Coding host silently reverted.
    /// </summary>
    [Fact]
    public void ReconcileFromView_WithAModelEmptyCenter_StillAnchorsCenterByElimination()
    {
        var sessions = new Surface("sessions", "sessions", "Terminal sessions");
        var terminal = new Surface("terminal-1", "terminal", "Terminal — pwsh");

        var zones = ImmutableDictionary.CreateRange(new[]
        {
            KeyValuePair.Create(ZoneId.Left, new ZoneState(ZoneId.Left, new ZoneStack([sessions]), ZoneState.DefaultExtent, Collapsed: false)),
            KeyValuePair.Create(ZoneId.Right, new ZoneState(ZoneId.Right, (ZoneContent?)null, ZoneState.DefaultExtent, Collapsed: false)),
            KeyValuePair.Create(ZoneId.Bottom, new ZoneState(ZoneId.Bottom, new ZoneStack([terminal]), 0.30, Collapsed: false)),
            KeyValuePair.Create(ZoneId.Center, new ZoneState(ZoneId.Center, (ZoneContent?)null, 1.0, Collapsed: false)),
        });
        var svc = new ZoneBackedLayoutService(new WorkbenchLayout(zones, [], Maximized: null));

        // The view: "sessions" dragged out of Left into Bottom, beside "terminal-1". Left's column
        // is then empty and absent from the rendered tree (the adapter's own fix for that shape);
        // Center's column holds only the synthetic Welcome placeholder.
        var centerColumn = new StackNode(ZonesToTree.CenterStackId, [ZonesToTree.WelcomePlaceholder]);
        var bottomAfter = new StackNode(ZonesToTree.BottomStackId, [terminal, sessions]);
        var post = new Layout(
            new SplitNode("root", Orientation.Vertical, [centerColumn, bottomAfter], [0.7, 0.3]),
            [], ImmutableDictionary<string, StackState>.Empty);

        var applied = svc.ReconcileFromView(post);

        Assert.True(applied);
        Assert.Equal(ZoneId.Bottom, svc.Zones.FindZoneOf("sessions"));
        Assert.Null(svc.Zones.Zone(ZoneId.Left).Content);
    }

    /// <summary>
    /// The safe half of the elimination fallback above, named in its own comment ("still refuses,
    /// never guesses, when more than one [candidate] does") and pinned here rather than left
    /// asserted only in prose: when Center's own anchor search comes back empty AND more than one
    /// column is left unclaimed by Left/Right, the reconcile refuses — it never guesses which
    /// leftover column is Center.
    /// </summary>
    [Fact]
    public void ReconcileFromView_WithTwoUnanchorableColumns_RefusesRatherThanGuesses()
    {
        var left = new Surface("left-surface", "view", "L");
        var right = new Surface("right-surface", "view", "R");
        var bottomSurface = new Surface("terminal-1", "terminal", "Terminal");

        var zones = ImmutableDictionary.CreateRange(new[]
        {
            KeyValuePair.Create(ZoneId.Left, new ZoneState(ZoneId.Left, new ZoneStack([left]), ZoneState.DefaultExtent, Collapsed: false)),
            KeyValuePair.Create(ZoneId.Right, new ZoneState(ZoneId.Right, new ZoneStack([right]), ZoneState.DefaultExtent, Collapsed: false)),
            KeyValuePair.Create(ZoneId.Bottom, new ZoneState(ZoneId.Bottom, new ZoneStack([bottomSurface]), 0.30, Collapsed: false)),
            KeyValuePair.Create(ZoneId.Center, new ZoneState(ZoneId.Center, (ZoneContent?)null, 1.0, Collapsed: false)),
        });
        var svc = new ZoneBackedLayoutService(new WorkbenchLayout(zones, [], Maximized: null));
        var before = svc.Zones.Shape();

        // A view where NEITHER Left's nor Right's surface appears in either column — two columns,
        // both holding surfaces this model owns nowhere. Center's search already comes back empty
        // (Content is null above), so this leaves two unclaimed columns: ambiguous by construction.
        var col0 = new StackNode("col0", [new Surface("mystery-1", "view", "M1")]);
        var col1 = new StackNode("col1", [new Surface("mystery-2", "view", "M2")]);
        var post = new Layout(
            new SplitNode("root", Orientation.Vertical,
                [
                    new SplitNode("cols", Orientation.Horizontal, [col0, col1], [0.5, 0.5]),
                    new StackNode(ZonesToTree.BottomStackId, [bottomSurface]),
                ],
                [0.7, 0.3]),
            [], ImmutableDictionary<string, StackState>.Empty);

        var applied = svc.ReconcileFromView(post);

        Assert.False(applied);
        Assert.Equal(before, svc.Zones.Shape());   // untouched — no guess was made
    }

    private static Layout DomainDraggedIntoTheBottom(Layout rendered, bool withLeftColumn)
    {
        var center = rendered.AllStacks().Single(s => s.Id == ZonesToTree.CenterStackId);
        var bottom = rendered.AllStacks().Single(s => s.Id == ZonesToTree.BottomStackId);
        var domain = center.Surfaces.Single(s => s.SurfaceId == "domain");

        LayoutNode columns = new StackNode("c", center.Surfaces.Remove(domain));
        if (withLeftColumn)
        {
            var left = rendered.AllStacks().Single(s => s.Id == ZonesToTree.LeftStackId);
            columns = new SplitNode("cols", Orientation.Horizontal, [left, columns], [0.3, 0.7]);
        }

        return new Layout(
            new SplitNode("root", Orientation.Vertical,
                [columns, new StackNode("b", bottom.Surfaces.Add(domain))],
                [0.7, 0.3]),
            [], ImmutableDictionary<string, StackState>.Empty);
    }

    private static IReadOnlyList<string> StackSurfaces(ILayoutService svc, string stackId) =>
        svc.Current.AllStacks().FirstOrDefault(s => s.Id == stackId)?.Surfaces.Select(s => s.SurfaceId).ToList()
        ?? new List<string>();
}

