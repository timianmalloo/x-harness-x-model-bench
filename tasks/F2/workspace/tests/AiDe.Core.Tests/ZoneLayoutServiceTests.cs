using System.Collections.Immutable;
using AiDe.Core.Workbench;

namespace AiDe.Core.Tests;

/// <summary>
/// The zone-scoped layout operations (ADR-0021). The headline property is <b>containment</b>: an
/// operation on one pane changes only the zone(s) that pane belongs to — the structural remedy for
/// defect class DC-063, where the split tree relocated unrelated panes on a single-child collapse.
/// </summary>
public sealed class ZoneLayoutServiceTests
{
    private static Surface S(string id, string kind = "view") => new(id, kind, id);

    /// <summary>All four zones populated, so a move has genuine bystanders to leave untouched.</summary>
    private static WorkbenchLayout FullyPopulated()
    {
        var layout = WorkbenchLayout.Default();                       // Left, Bottom, Center populated; Right empty
        layout = ZoneLayoutService.OpenPane(layout, S("outline", "view"), ZoneId.Right).Layout;
        layout.AssertInvariant();
        return layout;
    }

    // ---- AC-F1: containment on move (the DC-063 control) ---------------------

    [Fact]
    public void MovePane_ChangesOnlySourceAndDestination_OtherZonesReferenceIdentical()
    {
        var before = FullyPopulated();

        // Move a terminal from the Bottom zone to the Right zone.
        var result = ZoneLayoutService.MovePane(before, "terminal-1", ZoneId.Right);
        Assert.True(result.Applied);
        var after = result.Layout;

        // The moved surface left the source and joined the destination...
        Assert.Equal(ZoneId.Right, after.FindZoneOf("terminal-1"));
        Assert.DoesNotContain(after.Zone(ZoneId.Bottom).Surfaces(), s => s.SurfaceId == "terminal-1");

        // ...and every OTHER zone is byte-identical — not merely equal, the same instance (containment).
        Assert.Same(before.Zone(ZoneId.Left), after.Zone(ZoneId.Left));
        Assert.Same(before.Zone(ZoneId.Center), after.Zone(ZoneId.Center));
    }

    [Fact]
    public void MovePane_DoesNotReorientOrRelocateOtherZones()
    {
        var before = FullyPopulated();
        var beforeCenterShape = ShapeOfZone(before, ZoneId.Center);
        var beforeLeftShape = ShapeOfZone(before, ZoneId.Left);

        var after = ZoneLayoutService.MovePane(before, "outline", ZoneId.Bottom).Layout;

        // Center and Left neither moved, reordered, nor changed contents (AC-F2).
        Assert.Equal(beforeCenterShape, ShapeOfZone(after, ZoneId.Center));
        Assert.Equal(beforeLeftShape, ShapeOfZone(after, ZoneId.Left));
    }

    // ---- AC-F3: the Center never disappears --------------------------------

    [Fact]
    public void ClosingTheLastCenterSurface_LeavesAnEmptyCenter_NotAMissingZone()
    {
        var layout = WorkbenchLayout.Default();
        foreach (var id in layout.Zone(ZoneId.Center).Surfaces().Select(s => s.SurfaceId).ToList())
        {
            layout = ZoneLayoutService.ClosePane(layout, id).Layout;
        }

        // The zone still exists; it is simply empty (placeholder), and it is not collapsed.
        Assert.True(layout.Zones.ContainsKey(ZoneId.Center));
        Assert.True(layout.Zone(ZoneId.Center).IsEmpty);
        Assert.False(layout.Zone(ZoneId.Center).Collapsed);
        layout.AssertInvariant();
    }

    [Fact]
    public void TheCenter_CannotBeCollapsed()
    {
        var result = ZoneLayoutService.CollapseZone(WorkbenchLayout.Default(), ZoneId.Center);
        Assert.False(result.Applied);
        Assert.Equal(LayoutErrorCodes.InvalidTarget, result.RefusalCode);
    }

    // ---- AC-F4: tool zones collapse reversibly -----------------------------

    [Fact]
    public void CollapseThenExpand_RestoresTheSamePanesAndActiveTab()
    {
        var before = FullyPopulated();
        before = ZoneLayoutService.Activate(before, "joins").Layout; // make a non-default tab active in Left
        var leftShapeBefore = ShapeOfZone(before, ZoneId.Left);

        var collapsed = ZoneLayoutService.CollapseZone(before, ZoneId.Left).Layout;
        Assert.True(collapsed.Zone(ZoneId.Left).Collapsed);
        Assert.False(collapsed.Zone(ZoneId.Left).IsEmpty); // panes retained while collapsed

        var expanded = ZoneLayoutService.ExpandZone(collapsed, ZoneId.Left).Layout;
        Assert.False(expanded.Zone(ZoneId.Left).Collapsed);
        Assert.Equal(leftShapeBefore, ShapeOfZone(expanded, ZoneId.Left)); // same panes, same active tab
    }

    // ---- AC-F5: maximize is reversible -------------------------------------

    [Fact]
    public void MaximizeThenRestore_RestoresTheExactArrangement()
    {
        var before = FullyPopulated();
        var shapeBefore = before.Shape();

        var maxed = ZoneLayoutService.Maximize(before, ZoneId.Center).Layout;
        Assert.NotNull(maxed.Maximized);
        Assert.True(maxed.Zone(ZoneId.Left).Collapsed);   // neighbours hidden while maximized

        var restored = ZoneLayoutService.Restore(maxed).Layout;
        Assert.Null(restored.Maximized);
        Assert.Equal(shapeBefore, restored.Shape());       // exact restore
    }

    // ---- AC-F6: resize is local --------------------------------------------

    [Fact]
    public void ResizeZone_ChangesOnlyThatZone()
    {
        var before = FullyPopulated();
        var after = ZoneLayoutService.ResizeZone(before, ZoneId.Left, 0.4).Layout;

        Assert.Equal(0.4, after.Zone(ZoneId.Left).Extent, precision: 6);
        Assert.Same(before.Zone(ZoneId.Right), after.Zone(ZoneId.Right));
        Assert.Same(before.Zone(ZoneId.Bottom), after.Zone(ZoneId.Bottom));
    }

    // ---- AC-F7: open is destination-local ----------------------------------

    [Fact]
    public void OpenPane_AddsToTargetZoneOnly_AsTheActiveTab()
    {
        var before = FullyPopulated();
        var result = ZoneLayoutService.OpenPane(before, S("diag", "diagnostics"), ZoneId.Bottom);
        var after = result.Layout;

        Assert.Equal(ZoneId.Bottom, after.FindZoneOf("diag"));
        Assert.Equal("diag", ((ZoneStack)after.Zone(ZoneId.Bottom).Content!).Active.SurfaceId);
        Assert.Same(before.Zone(ZoneId.Left), after.Zone(ZoneId.Left));
        Assert.Same(before.Zone(ZoneId.Center), after.Zone(ZoneId.Center));
        Assert.Same(before.Zone(ZoneId.Right), after.Zone(ZoneId.Right));
    }

    // ---- #4: a pane arriving into an empty tool zone lands at a usable width ----

    [Fact]
    public void OpenPane_IntoAShrunkEmptyZone_FloorsWidthToUsable()
    {
        // Right starts empty; a prior resize shrank it to the 8% minimum.
        var layout = ZoneLayoutService.ResizeZone(WorkbenchLayout.Default(), ZoneId.Right, 0.08).Layout;
        Assert.True(layout.Zone(ZoneId.Right).IsEmpty);
        Assert.Equal(0.08, layout.Zone(ZoneId.Right).Extent, precision: 6);

        var after = ZoneLayoutService.OpenPane(layout, S("src", "codeviewer"), ZoneId.Right).Layout;

        Assert.Equal(ZoneId.Right, after.FindZoneOf("src"));
        Assert.Equal(ZoneState.DefaultExtent, after.Zone(ZoneId.Right).Extent, precision: 6); // floored, not a sliver
    }

    [Fact]
    public void OpenPane_IntoAPopulatedZone_KeepsTheUserChosenWidth()
    {
        var layout = ZoneLayoutService.OpenPane(WorkbenchLayout.Default(), S("a", "codeviewer"), ZoneId.Right).Layout;
        layout = ZoneLayoutService.ResizeZone(layout, ZoneId.Right, 0.5).Layout; // user widens deliberately

        var after = ZoneLayoutService.OpenPane(layout, S("b", "codeviewer"), ZoneId.Right).Layout;

        Assert.Equal(0.5, after.Zone(ZoneId.Right).Extent, precision: 6); // not reset — the zone already had content
    }

    [Fact]
    public void MovePane_IntoAShrunkEmptyZone_FloorsWidthToUsable()
    {
        var layout = ZoneLayoutService.ResizeZone(WorkbenchLayout.Default(), ZoneId.Right, 0.08).Layout;
        Assert.True(layout.Zone(ZoneId.Right).IsEmpty);

        var after = ZoneLayoutService.MovePane(layout, "terminal-1", ZoneId.Right).Layout;

        Assert.Equal(ZoneId.Right, after.FindZoneOf("terminal-1"));
        Assert.Equal(ZoneState.DefaultExtent, after.Zone(ZoneId.Right).Extent, precision: 6);
    }

    [Fact]
    public void MovePane_UnknownSurface_IsRefused()
    {
        var result = ZoneLayoutService.MovePane(WorkbenchLayout.Default(), "nope", ZoneId.Right);
        Assert.False(result.Applied);
        Assert.Equal(LayoutErrorCodes.SurfaceUnknown, result.RefusalCode);
    }

    private static string ShapeOfZone(WorkbenchLayout layout, ZoneId id)
    {
        var z = layout.Zone(id);
        var content = z.Content switch
        {
            null => "-",
            ZoneStack s => string.Join("+", s.Tabs.Select(t => t.SurfaceId)) + "@" + s.ActiveIndex,
            _ => "split",
        };
        return $"{content}/{z.Collapsed}";
    }
}
