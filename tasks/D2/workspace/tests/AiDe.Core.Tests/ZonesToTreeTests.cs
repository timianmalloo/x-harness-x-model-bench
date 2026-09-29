using AiDe.Core.Workbench;

namespace AiDe.Core.Tests;

/// <summary>
/// The zones → fixed-shape-tree projection that lets the existing AvalonDock adapter render zones
/// unchanged (ADR-0021 Strangler step). The projected frame is always the same shape, which is what
/// makes rendering it unable to "flip".
/// </summary>
public sealed class ZonesToTreeTests
{
    [Fact]
    public void Default_ProjectsToAFixedFrame_WithDeterministicZoneIds()
    {
        var tree = ZonesToTree.ToTree(WorkbenchLayout.Default());

        var stackIds = tree.AllStacks().Select(s => s.Id).ToHashSet();
        Assert.Contains(ZonesToTree.CenterStackId, stackIds);
        Assert.Contains(ZonesToTree.LeftStackId, stackIds);   // Default populates Left + Bottom + Center
        Assert.Contains(ZonesToTree.BottomStackId, stackIds);
        tree.AssertInvariant();
    }

    [Fact]
    public void RoundTrip_TreeToZones_Of_ZonesToTree_PreservesWhichZoneHoldsWhat()
    {
        var zones = WorkbenchLayout.Default();
        var back = TreeToZones.Convert(ZonesToTree.ToTree(zones));

        Assert.Equal(zones.FindZoneOf("graph"), back.FindZoneOf("graph"));
        Assert.Equal(zones.FindZoneOf("terminal-1"), back.FindZoneOf("terminal-1"));
        Assert.Equal(zones.FindZoneOf("explore"), back.FindZoneOf("explore"));
    }

    [Fact]
    public void CollapsedToolZone_IsOmittedFromTheTree_ButRetainedInTheModel()
    {
        var zones = ZoneLayoutService.CollapseZone(WorkbenchLayout.Default(), ZoneId.Left).Layout;
        var tree = ZonesToTree.ToTree(zones);

        Assert.DoesNotContain(ZonesToTree.LeftStackId, tree.AllStacks().Select(s => s.Id));
        Assert.False(zones.Zone(ZoneId.Left).IsEmpty); // content retained in the zone model
    }

    [Fact]
    public void EmptyCenter_StillRenders_ViaTheWelcomePlaceholder()
    {
        var zones = WorkbenchLayout.Default();
        foreach (var id in zones.Zone(ZoneId.Center).Surfaces().Select(s => s.SurfaceId).ToList())
        {
            zones = ZoneLayoutService.ClosePane(zones, id).Layout;
        }

        var tree = ZonesToTree.ToTree(zones);
        var center = tree.AllStacks().Single(s => s.Id == ZonesToTree.CenterStackId);
        Assert.Equal("welcome", center.Surfaces[0].SurfaceId);
    }

    [Fact]
    public void OnlyCenterPopulated_ProjectsWithoutASplit()
    {
        // A layout with just the Center should not build a degenerate one-child split.
        var zones = WorkbenchLayout.Empty();
        zones = zones.WithZone(zones.Zone(ZoneId.Center) with
        {
            Content = new ZoneStack([new Surface("doc", "canvas", "Doc")]),
        });

        var tree = ZonesToTree.ToTree(zones);
        Assert.IsType<StackNode>(tree.Root);
        Assert.Equal(ZonesToTree.CenterStackId, tree.Root.Id);
    }

    [Fact]
    public void ZoneOfStackId_MapsProjectedIdsBackToZones()
    {
        Assert.Equal(ZoneId.Left, ZonesToTree.ZoneOfStackId(ZonesToTree.LeftStackId));
        Assert.Equal(ZoneId.Center, ZonesToTree.ZoneOfStackId(ZonesToTree.CenterStackId));
        Assert.Null(ZonesToTree.ZoneOfStackId("something-else"));
    }
}
