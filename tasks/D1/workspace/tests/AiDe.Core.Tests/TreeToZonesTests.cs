using System.Collections.Immutable;
using AiDe.Core.Workbench;

namespace AiDe.Core.Tests;

/// <summary>
/// The Expand-step migration: a legacy split-tree <see cref="Layout"/> converts to named zones losing
/// no surface, deterministically (AC-F9). Documents land in the Center; terminals/diagnostics in the
/// Bottom; explorers on the Left.
/// </summary>
public sealed class TreeToZonesTests
{
    [Fact]
    public void ConvertingTheDefaultTree_LosesNoSurface()
    {
        var tree = Layout.Default();
        var zones = TreeToZones.Convert(tree);

        var treeSurfaces = tree.AllStacks().SelectMany(s => s.Surfaces).Select(s => s.SurfaceId).OrderBy(x => x);
        var zoneSurfaces = zones.AllSurfaces().Select(s => s.SurfaceId).OrderBy(x => x);
        Assert.Equal(treeSurfaces, zoneSurfaces);
        zones.AssertInvariant();
    }

    [Fact]
    public void ConvertingTheDefaultTree_PlacesTheGraphInCenter_TerminalInBottom_ExplorersLeft()
    {
        var zones = TreeToZones.Convert(Layout.Default());

        // The graph document tabs stay grouped in the Center.
        Assert.Equal(ZoneId.Center, zones.FindZoneOf("graph"));
        Assert.Equal(ZoneId.Center, zones.FindZoneOf("domain"));   // same tree stack as the graph → stays together

        // The terminal goes to the Bottom.
        Assert.Equal(ZoneId.Bottom, zones.FindZoneOf("terminal-1"));

        // The workspace explorers go Left.
        Assert.Equal(ZoneId.Left, zones.FindZoneOf("explore"));
        Assert.Equal(ZoneId.Left, zones.FindZoneOf("joins"));
    }

    [Fact]
    public void Convert_IsDeterministic_SameTreeYieldsSameShape()
    {
        var a = TreeToZones.Convert(Layout.Default());
        var b = TreeToZones.Convert(Layout.Default());
        Assert.Equal(a.Shape(), b.Shape());
    }

    [Fact]
    public void Convert_CarriesFloatingStacksThrough()
    {
        var tree = Layout.Default() with
        {
            Floating = [new StackNode("float-1", [new Surface("popped", "terminal", "Popped")])],
        };

        var zones = TreeToZones.Convert(tree);

        Assert.Contains(zones.Floating, f => f.Surfaces.Any(s => s.SurfaceId == "popped"));
        Assert.Contains(zones.AllSurfaces(), s => s.SurfaceId == "popped");
    }

    [Fact]
    public void Convert_TreeWithNoDocuments_LeavesCenterEmpty()
    {
        // Two tool stacks, no canvas/document anywhere.
        var terminal = new StackNode("t", [new Surface("term", "terminal", "Term")]);
        var explorer = new StackNode("e", [new Surface("exp", "view", "Explore")]);
        var tree = new Layout(
            new SplitNode("r", Orientation.Vertical, [explorer, terminal], [0.6, 0.4]),
            [], ImmutableDictionary<string, StackState>.Empty);

        var zones = TreeToZones.Convert(tree);

        Assert.True(zones.Zone(ZoneId.Center).IsEmpty);   // placeholder, still present (AC-F3)
        Assert.Equal(ZoneId.Bottom, zones.FindZoneOf("term"));
        Assert.Equal(ZoneId.Left, zones.FindZoneOf("exp"));
    }
}
