using System.Collections.Immutable;
using AiDe.Core.Workbench;

namespace AiDe.Core.Tests.Workbench;

/// <summary>
/// F-1 (Rulings 83 and 88; SH-4.2): the native-drag reconcile reads the <b>model's</b> zones, not
/// only the rendered ones — a collapsed zone that still holds panes is absent from the view by
/// design, and the reconcile keeps what it holds instead of counting it lost and refusing the whole
/// drag. The surface-set guard stays: a drag that truly loses a surface is still refused.
/// </summary>
/// <remarks>
/// <para><b>The defect, measured before the fix (<c>docs/proof/coding-recut-left-dock.md</c>).</b>
/// <c>TryMapByPosition</c> pre-seeded Left, Center and Right with EMPTY surface lists and filled them
/// from the view's columns; a collapsed-holding side zone has no column, so its list stayed empty,
/// the guard saw its panes go missing and returned null — every drag reverted for as long as the
/// zone stayed collapsed, announced as <i>"a collapsed panel still holds panes"</i> (the operator's
/// finding 4). The Bottom was already kept (it was never pre-seeded), which is why Ruling 88's
/// default — Bottom collapsed, holding one terminal — was not the shape that refused; the Left and
/// Right were, and maximize-on-create (Ruling 47) collapsed both.</para>
/// <para><b>Red before green, per row (the record is <c>docs/proof/coding-recut-left-dock.md</c>):</b>
/// the Left and Right rows of the theory and the maximized fact REFUSED against the pre-seeding
/// code; the Bottom row was APPLIED BUT WRONG — <c>domain</c> landed in the Center (<i>Expected
/// Left, Actual Center</i>): the Bottom was never pre-seeded, so its panes were kept, and the
/// raw-count majority then let the Center (two owned, one moved) win the tie for the Left's column
/// (one owned). Ruling 88's premise that the default "would refuse every drag" was thus wrong for
/// the Bottom by refusal and right by mis-anchoring — a premise corrected, and a second cause found
/// on the same oracle.</para>
/// </remarks>
public sealed class ReconcileTests
{
    private static readonly Surface Explore = new("explore", "view", "Explore");
    private static readonly Surface Sources = new("sources", "view", "Sources");
    private static readonly Surface Graph = new("graph", "canvas", "Graph");
    private static readonly Surface Domain = new("domain", "view", "Domain");
    private static readonly Surface Terminal = new("terminal-1", "terminal", "Terminal — pwsh");

    /// <summary>Left [explore] · Center [graph, domain] · Right [provenance] · Bottom [terminal-1], every zone expanded.</summary>
    private static WorkbenchLayout FourZones() => new(
        ImmutableDictionary.CreateRange(new[]
        {
            KeyValuePair.Create(ZoneId.Left, new ZoneState(ZoneId.Left, new ZoneStack([Explore]), ZoneState.DefaultExtent, Collapsed: false)),
            KeyValuePair.Create(ZoneId.Right, new ZoneState(ZoneId.Right, new ZoneStack([Sources]), ZoneState.DefaultExtent, Collapsed: false)),
            KeyValuePair.Create(ZoneId.Bottom, new ZoneState(ZoneId.Bottom, new ZoneStack([Terminal]), 0.30, Collapsed: false)),
            KeyValuePair.Create(ZoneId.Center, new ZoneState(ZoneId.Center, new ZoneStack([Graph, Domain]), 1.0, Collapsed: false)),
        }),
        [], Maximized: null);

    private static Layout View(LayoutNode root) => new(root, [], ImmutableDictionary<string, StackState>.Empty);

    /// <summary>
    /// With one zone collapsed and still holding its pane, <c>domain</c> dragged out of the Center
    /// into a RENDERED zone is applied; the collapsed zone keeps its pane and stays collapsed.
    /// </summary>
    [Theory]
    [InlineData(ZoneId.Bottom, ZoneId.Left)]    // Ruling 88's default shape: the terminal collapsed below; the drop joins the Left
    [InlineData(ZoneId.Left, ZoneId.Bottom)]    // the Left collapsed-holding — the shape that refused (finding 4)
    [InlineData(ZoneId.Right, ZoneId.Left)]
    public void ADragWhileAZoneIsCollapsedHoldingPanes_IsApplied(ZoneId collapsed, ZoneId dropInto)
    {
        var svc = new ZoneBackedLayoutService(ZoneLayoutService.CollapseZone(FourZones(), collapsed).Layout);
        var held = svc.Zones.Zone(collapsed).Surfaces().Select(s => s.SurfaceId).ToList();
        Assert.NotEmpty(held);

        // The view after the drag: every RENDERED zone's column, the collapsed one absent, domain in its new pane.
        var post = View(DomainDraggedInto(svc.Zones, dropInto));

        var applied = svc.ReconcileFromView(post);

        Assert.True(applied, "the reconcile refused a drag because a collapsed zone still held panes (finding 4)");
        Assert.Equal(dropInto, svc.Zones.FindZoneOf("domain"));
        Assert.Equal(ZoneId.Center, svc.Zones.FindZoneOf("graph"));                    // the bystander stays
        Assert.Equal(held, svc.Zones.Zone(collapsed).Surfaces().Select(s => s.SurfaceId));   // the held pane is kept …
        Assert.True(svc.Zones.Zone(collapsed).Collapsed);                                 // … and the zone stays as the operator left it
        svc.Zones.AssertInvariant();
    }

    /// <summary>
    /// A drop on the SIDE of a collapsed-holding zone — a column the view shows where the collapsed
    /// zone would be — joins that zone and expands it, so the operator's drop is on screen rather than
    /// swallowed by a rail.
    /// </summary>
    [Fact]
    public void ADropBesideACollapsedHoldingZone_JoinsItAndExpandsIt()
    {
        var svc = new ZoneBackedLayoutService(ZoneLayoutService.CollapseZone(FourZones(), ZoneId.Right).Layout);

        // Columns: Left [explore] · Center [graph] · a new column to the right holding domain; the bottom row rendered.
        var post = View(new SplitNode("root", Orientation.Vertical,
            [
                new SplitNode("cols", Orientation.Horizontal,
                    [
                        new StackNode(ZonesToTree.LeftStackId, [Explore]),
                        new StackNode(ZonesToTree.CenterStackId, [Graph]),
                        new StackNode("dragged", [Domain]),
                    ],
                    [0.2, 0.6, 0.2]),
                new StackNode(ZonesToTree.BottomStackId, [Terminal]),
            ],
            [0.7, 0.3]));

        Assert.True(svc.ReconcileFromView(post));
        Assert.Equal(["sources", "domain"], svc.Zones.Zone(ZoneId.Right).Surfaces().Select(s => s.SurfaceId));
        Assert.False(svc.Zones.Zone(ZoneId.Right).Collapsed);
        Assert.Equal("domain", ((ZoneStack)svc.Zones.Zone(ZoneId.Right).Content!).Active.SurfaceId);   // the view's active tab wins
    }

    /// <summary>
    /// Ruling 47's shape, the operator's finding 4 exactly: the session document maximized in the
    /// Center (Left and Bottom collapsed, both holding), then dragged toward the left dock. The view
    /// shows the session's column beside the Center's placeholder; the reconcile applies it — the
    /// session joins the Left, which expands — rather than refusing on the collapsed zones.
    /// </summary>
    [Fact]
    public void ADragWhileAStackIsMaximized_IsAppliedOrRefusedWithTheTrueCause()
    {
        var session = new Surface("session:s1", "session-document", "S1");
        var sessions = new Surface("sessions", "sessions", "Terminal sessions");
        var zones = ImmutableDictionary.CreateRange(new[]
        {
            KeyValuePair.Create(ZoneId.Left, new ZoneState(ZoneId.Left, new ZoneStack([sessions]), ZoneState.DefaultExtent, Collapsed: false)),
            KeyValuePair.Create(ZoneId.Right, new ZoneState(ZoneId.Right, (ZoneContent?)null, ZoneState.DefaultExtent, Collapsed: false)),
            KeyValuePair.Create(ZoneId.Bottom, new ZoneState(ZoneId.Bottom, new ZoneStack([Terminal]), 0.30, Collapsed: false)),
            KeyValuePair.Create(ZoneId.Center, new ZoneState(ZoneId.Center, new ZoneStack([session]), 1.0, Collapsed: false)),
        });
        var maximized = ZoneLayoutService.Maximize(new WorkbenchLayout(zones, [], Maximized: null), ZoneId.Center);
        Assert.True(maximized.Applied);
        var svc = new ZoneBackedLayoutService(maximized.Layout);
        Assert.True(svc.Zones.Zone(ZoneId.Left).Collapsed && svc.Zones.Zone(ZoneId.Bottom).Collapsed);

        // The drag: the session dropped to the LEFT of the Center. The Center pane is then empty and
        // shows the synthetic placeholder — which is what identifies it as the Center.
        var post = View(new SplitNode("cols", Orientation.Horizontal,
            [
                new StackNode("dragged", [session]),
                new StackNode(ZonesToTree.CenterStackId, [ZonesToTree.WelcomePlaceholder]),
            ],
            [0.5, 0.5]));

        var applied = svc.ReconcileFromView(post);

        Assert.True(applied, "the drag of a maximized document toward the left dock was refused — the reconcile is still blind to the collapsed zones' panes");
        Assert.Equal(["sessions", "session:s1"], svc.Zones.Zone(ZoneId.Left).Surfaces().Select(s => s.SurfaceId));
        Assert.False(svc.Zones.Zone(ZoneId.Left).Collapsed);
        Assert.Null(svc.Zones.Zone(ZoneId.Center).Content);
        Assert.Equal(["terminal-1"], svc.Zones.Zone(ZoneId.Bottom).Surfaces().Select(s => s.SurfaceId));
        Assert.True(svc.Zones.Zone(ZoneId.Bottom).Collapsed);
        svc.Zones.AssertInvariant();
    }

    /// <summary>
    /// O-2's gesture (Ruling 88 condition 1), both halves, in the Coding re-cut: the session dragged
    /// from the Left into the EMPTY Center — the view's Center pane then holds the placeholder and
    /// the session side by side — and back to the left of it. Both apply; the placeholder never
    /// enters the model; the Bottom's collapsed terminal is untouched throughout.
    /// </summary>
    /// <remarks>
    /// <b>Red before green, on a second cause:</b> the Center's anchor was found by majority over the
    /// model's Center surfaces, and an empty Center owns none — the placeholder is view-only — so
    /// the column holding it was claimed by nobody and the drag was refused as "not our frame"
    /// (SH-3's elimination fallback needs one unclaimed column, and the session's column had been
    /// claimed by the Left). The placeholder IS the Center pane, by construction.
    /// </remarks>
    [Fact]
    public void TheSessionDraggedIntoTheEmptyCenterAndBack_IsAppliedBothWays_AndThePlaceholderNeverEntersTheModel()
    {
        var session = new Surface("session:s1", "session-document", "S1");
        var opened = ZoneLayoutService.OpenPane(WorkbenchLayout.Default(PerspectiveSet.Coding), session, ZoneId.Left).Layout;
        var svc = new ZoneBackedLayoutService(opened);
        Assert.True(svc.Zones.Zone(ZoneId.Bottom).Collapsed);

        // Into the Center: the Left pane is emptied and dropped by the adapter; the Center pane
        // shows the placeholder with the session beside it (the placeholder is a real LayoutDocument
        // in the view until the next render).
        var intoCenter = View(new StackNode(ZonesToTree.CenterStackId, [ZonesToTree.WelcomePlaceholder, session], 1));
        Assert.True(svc.ReconcileFromView(intoCenter), "the drag into the empty Center was refused");
        Assert.Equal(ZoneId.Center, svc.Zones.FindZoneOf(session.SurfaceId));
        Assert.Null(svc.Zones.Zone(ZoneId.Left).Content);
        Assert.DoesNotContain(svc.Zones.AllSurfaces(), s => s.SurfaceId == ZonesToTree.WelcomePlaceholder.SurfaceId);
        Assert.Equal(["terminal-1"], svc.Zones.Zone(ZoneId.Bottom).Surfaces().Select(s => s.SurfaceId));
        Assert.True(svc.Zones.Zone(ZoneId.Bottom).Collapsed);

        // And back: a new column to the left of the Center pane, which now shows only the placeholder.
        var back = View(new SplitNode("cols", Orientation.Horizontal,
            [new StackNode("dragged", [session]), new StackNode(ZonesToTree.CenterStackId, [ZonesToTree.WelcomePlaceholder])],
            [0.55, 0.45]));
        Assert.True(svc.ReconcileFromView(back), "the drag back to the left dock was refused");
        Assert.Equal(ZoneId.Left, svc.Zones.FindZoneOf(session.SurfaceId));
        Assert.Null(svc.Zones.Zone(ZoneId.Center).Content);
        Assert.False(svc.Zones.Zone(ZoneId.Left).Collapsed);
        Assert.DoesNotContain(svc.Zones.AllSurfaces(), s => s.SurfaceId == ZonesToTree.WelcomePlaceholder.SurfaceId);
        Assert.True(svc.Zones.Zone(ZoneId.Bottom).Collapsed);
        svc.Zones.AssertInvariant();
    }

    /// <summary>
    /// A Center tab dragged into the Left beside the session: the Left keeps its column and the
    /// session stays put. <b>Red before green:</b> the anchor was a raw count, so a Left of one
    /// surface tied a Center of two after one moved, the Center won the tie by rule and claimed the
    /// Left's column — the drag moved the SESSION to the Center (DC-063's class, the bystander).
    /// </summary>
    [Fact]
    public void ACenterTabDraggedBesideTheSession_LeavesTheSessionInTheLeft()
    {
        var session = new Surface("session:s1", "session-document", "S1");
        var viewer = new Surface("codeviewer#1", "codeviewer", "Router.cs");
        var layout = ZoneLayoutService.OpenPane(WorkbenchLayout.Default(PerspectiveSet.Coding), session, ZoneId.Left).Layout;
        layout = ZoneLayoutService.OpenPane(layout, viewer, ZoneId.Center).Layout;
        var svc = new ZoneBackedLayoutService(layout);

        var post = View(new SplitNode("cols", Orientation.Horizontal,
            [new StackNode(ZonesToTree.LeftStackId, [session, viewer], 1), new StackNode(ZonesToTree.CenterStackId, [ZonesToTree.WelcomePlaceholder])],
            [0.55, 0.45]));

        Assert.True(svc.ReconcileFromView(post));
        Assert.Equal(["session:s1", "codeviewer#1"], svc.Zones.Zone(ZoneId.Left).Surfaces().Select(s => s.SurfaceId));
        Assert.Null(svc.Zones.Zone(ZoneId.Center).Content);
    }

    /// <summary>
    /// A drop on the BOTTOM edge while the Bottom is collapsed and holding (Coding's default): the
    /// view's root becomes a vertical split with the dropped pane below the columns. The drop joins
    /// the Bottom and expands it — never a one-column reading of the whole tree that hands every
    /// Center tab to the Left (the WPF lens's finding on SH-4.2; DC-063's bystander class).
    /// </summary>
    [Fact]
    public void ADropOnTheBottomEdge_WhileTheBottomIsCollapsedHolding_JoinsTheBottomAndExpandsIt()
    {
        var session = new Surface("session:s1", "session-document", "S1");
        var viewer = new Surface("codeviewer#1", "codeviewer", "Router.cs");
        var layout = ZoneLayoutService.OpenPane(WorkbenchLayout.Default(PerspectiveSet.Coding), session, ZoneId.Left).Layout;
        layout = ZoneLayoutService.OpenPane(layout, viewer, ZoneId.Center).Layout;
        var svc = new ZoneBackedLayoutService(layout);
        Assert.True(svc.Zones.Zone(ZoneId.Bottom).Collapsed);

        var post = View(new SplitNode("root", Orientation.Vertical,
            [
                new SplitNode("cols", Orientation.Horizontal,
                    [new StackNode(ZonesToTree.LeftStackId, [session]), new StackNode(ZonesToTree.CenterStackId, [ZonesToTree.WelcomePlaceholder])],
                    [0.55, 0.45]),
                new StackNode("dropped", [viewer]),
            ],
            [0.7, 0.3]));

        Assert.True(svc.ReconcileFromView(post), "the bottom-edge drop was refused");
        Assert.Equal(["session:s1"], svc.Zones.Zone(ZoneId.Left).Surfaces().Select(s => s.SurfaceId));
        Assert.Null(svc.Zones.Zone(ZoneId.Center).Content);
        Assert.Equal(["terminal-1", "codeviewer#1"], svc.Zones.Zone(ZoneId.Bottom).Surfaces().Select(s => s.SurfaceId));
        Assert.False(svc.Zones.Zone(ZoneId.Bottom).Collapsed);
    }

    /// <summary>A vertical root of any other shape — three rows, or a row that is not the columns — is not our frame and is refused, never read as one column.</summary>
    [Fact]
    public void AVerticalRootThatIsNotColumnsOverBottom_IsRefused()
    {
        var session = new Surface("session:s1", "session-document", "S1");
        var viewer = new Surface("codeviewer#1", "codeviewer", "Router.cs");
        var layout = ZoneLayoutService.OpenPane(WorkbenchLayout.Default(PerspectiveSet.Coding), session, ZoneId.Left).Layout;
        layout = ZoneLayoutService.OpenPane(layout, viewer, ZoneId.Center).Layout;
        var svc = new ZoneBackedLayoutService(layout);
        var before = svc.Zones.Shape();

        var post = View(new SplitNode("root", Orientation.Vertical,
            [new StackNode("a", [session]), new StackNode("b", [viewer]), new StackNode("c", [ZonesToTree.WelcomePlaceholder])],
            [0.4, 0.3, 0.3]));

        Assert.False(svc.ReconcileFromView(post));
        Assert.Equal(before, svc.Zones.Shape());
    }

    /// <summary>
    /// The guard's honesty, kept: a view that truly LOST a surface — the collapsed zone's pane is
    /// missing from the model-side count because the view shows it nowhere and the model no longer
    /// holds it either — is still refused, never patched over.
    /// </summary>
    [Fact]
    public void AViewThatLosesARenderedSurface_IsStillRefused()
    {
        var svc = new ZoneBackedLayoutService(ZoneLayoutService.CollapseZone(FourZones(), ZoneId.Bottom).Layout);
        var before = svc.Zones.Shape();

        // graph vanished from the Center column and appears nowhere.
        var post = View(new SplitNode("cols", Orientation.Horizontal,
            [
                new StackNode(ZonesToTree.LeftStackId, [Explore]),
                new StackNode(ZonesToTree.CenterStackId, [Domain]),
                new StackNode(ZonesToTree.RightStackId, [Sources]),
            ],
            [0.2, 0.6, 0.2]));

        Assert.False(svc.ReconcileFromView(post));
        Assert.Equal(before, svc.Zones.Shape());
    }

    /// <summary>The view after <c>domain</c> is dragged from the Center into <paramref name="into"/>: every rendered zone's column, in frame order.</summary>
    private static LayoutNode DomainDraggedInto(WorkbenchLayout current, ZoneId into)
    {
        StackNode? Column(ZoneId zone, string stackId)
        {
            var state = current.Zone(zone);
            if (state.Collapsed || state.IsEmpty)
            {
                return null;
            }

            var tabs = state.Surfaces().Where(s => s.SurfaceId != "domain").ToList();
            if (zone == into)
            {
                tabs.Add(Domain);
            }

            return new StackNode(stackId, [.. tabs], tabs.Count - 1);
        }

        var columns = new[]
            {
                Column(ZoneId.Left, ZonesToTree.LeftStackId),
                Column(ZoneId.Center, ZonesToTree.CenterStackId),
                Column(ZoneId.Right, ZonesToTree.RightStackId),
            }
            .Where(c => c is not null)
            .Cast<LayoutNode>()
            .ToList();
        LayoutNode row = columns.Count == 1
            ? columns[0]
            : new SplitNode("cols", Orientation.Horizontal, [.. columns], [.. columns.Select(_ => 1.0 / columns.Count)]);

        var bottom = Column(ZoneId.Bottom, ZonesToTree.BottomStackId);
        return bottom is null
            ? row
            : new SplitNode("root", Orientation.Vertical, [row, bottom], [0.7, 0.3]);
    }
}
