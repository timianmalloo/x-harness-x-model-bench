using AiDe.Core.Workbench;

namespace AiDe.Core.Tests;

/// <summary>
/// Architecture's default layout is the operator's stated one, asserted headlessly.
/// </summary>
/// <remarks>
/// <para><b>Ruling 140</b> amends Ruling 94 to the operator's own words — <i>"the right-side-views for
/// the architecture explorer need to be Graph and Tree - where tree is the more familiar dev view like
/// in vs code"</i> — so the default is <b>Center = [Graph (active), Tree]</b> with <b>Left empty and
/// collapsed</b>. Contexts and Domain leave the default and stay admitted through the View menu.</para>
///
/// <para><b>Why this file exists at all.</b> The ruling names "one change to <c>ZoneLayout.cs</c> plus
/// its default-layout test", and the default-layout tests are in <c>AiDe.App.Tests</c> — they need a
/// shown window and a desktop slot. So a ruling that fixes what the product opens with had <b>no
/// headless assertion guarding it</b>: the whole 168-test layout suite passed unchanged when the
/// default was rewritten underneath it. Nothing here needs a window — the default is a pure function
/// of a perspective id — so nothing justified the gap.</para>
///
/// <para>The tabs are asserted <b>in order</b>, because the order is the operator's instruction and not
/// an implementation detail: "Graph and Tree" puts the graph first, and first is active.</para>
/// </remarks>
public sealed class TheArchitectureDefaultIsGraphAndTreeTests
{
    private static ZoneStack CenterOf(WorkbenchLayout layout) =>
        Assert.IsType<ZoneStack>(layout.Zones[ZoneId.Center].Content);

    [Fact]
    public void CenterIsGraphThenTree_AndGraphIsActive()
    {
        var layout = WorkbenchLayout.Default(PerspectiveSet.Architecture);

        var center = CenterOf(layout);
        Assert.Equal(["graph", "tree"], center.Tabs.Select(s => s.SurfaceId));
        Assert.Equal("graph", center.Active.SurfaceId);
    }

    /// <summary>The Tree is a real registered kind, not a label — a saved slot must be able to restore it.</summary>
    [Fact]
    public void TheTreeTabNamesTheSolutionTreeKind()
    {
        var tree = CenterOf(WorkbenchLayout.Default(PerspectiveSet.Architecture))
            .Tabs.Single(s => s.SurfaceId == "tree");

        Assert.Equal("solution-tree", tree.Kind);
    }

    /// <summary>
    /// One Graph, one home: Left retires its copy with the amendment.
    /// </summary>
    /// <remarks>
    /// Ruling 140 refused the option that kept the Graph in two zones at once. It also records that
    /// Ruling 94 condition (3)'s header-strip overflow finding becomes <b>moot</b> here rather than
    /// fixed — the strip overflowed because the Graph sat in a 0.22-width zone, and it no longer does.
    /// </remarks>
    [Fact]
    public void LeftIsEmptyAndCollapsed_SoTheGraphHasExactlyOneHome()
    {
        var layout = WorkbenchLayout.Default(PerspectiveSet.Architecture);

        var left = layout.Zones[ZoneId.Left];
        Assert.Null(left.Content);
        Assert.True(left.Collapsed);

        var graphTabs = layout.Zones.Values
            .Select(z => z.Content)
            .OfType<ZoneStack>()
            .SelectMany(s => s.Tabs)
            .Count(s => s.SurfaceId == "graph");

        Assert.Equal(1, graphTabs);
    }

    /// <summary>
    /// Contexts and Domain leave the DEFAULT; their kinds stay restorable.
    /// </summary>
    /// <remarks>
    /// The distinction Ruling 140 turns on, and the one a careless reading of "leave the default"
    /// would break: a surface out of the default is one View-menu gesture away and a saved slot
    /// carrying it still reconciles. Dropping the kind would be an envelope drop, which the ruling
    /// forbids — so this asserts absence from the default and nothing stronger.
    /// </remarks>
    [Fact]
    public void ContextsAndDomainAreNotInTheDefault()
    {
        var defaulted = WorkbenchLayout.Default(PerspectiveSet.Architecture).Zones.Values
            .Select(z => z.Content)
            .OfType<ZoneStack>()
            .SelectMany(s => s.Tabs)
            .Select(s => s.SurfaceId)
            .ToList();

        Assert.DoesNotContain("contexts", defaulted);
        Assert.DoesNotContain("domain", defaulted);
    }
}
