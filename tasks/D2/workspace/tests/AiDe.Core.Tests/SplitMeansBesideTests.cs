using AiDe.Core.Workbench;

namespace AiDe.Core.Tests;

/// <summary>
/// A drop lands in the zone it was dropped on, whatever gesture made it.
/// </summary>
/// <remarks>
/// <para><b>Two defects, and the second was in the fix for the first.</b> Originally
/// <c>ZoneBackedLayoutService.Move</c> ignored the drop's <c>Kind</c> entirely except for
/// <c>Float</c>, so a "split beside the graph" placement tabbed the document on top of the graph.
/// The fix remapped split kinds to a neighbouring zone — which made the reported case right and
/// every sibling case wrong: a user dragging a pane onto the LEFT zone with a split gesture had it
/// sent to the centre, as the last tab, announced as <i>"Moved Graph within the center."</i> A drop
/// that reports success and names a destination nobody asked for.</para>
///
/// <para><b>The error was one of kind, not coverage.</b> A placement-policy translation was put in a
/// user-gesture handler. "Beside the graph" is a thing one caller wants; "where I dropped it" is
/// what a drop means. The beside rule now lives with the caller that wants it —
/// <c>WorkbenchShell.OpenReferenceDocument</c> adds a reference document straight into the
/// neighbouring zone — and is asserted there.</para>
///
/// <para><b>Every zone is exercised, not the one the report named.</b> The sibling cases were missed
/// because a fix's test set is drawn from the defect report, and a report names one case. That is
/// the fifth instance of the shape in a day, four of them inside something just built.</para>
/// </remarks>
public sealed class SplitMeansBesideTests
{
    /// <summary>
    /// Every docking gesture, READ FROM THE ENUM rather than listed.
    /// </summary>
    /// <remarks>
    /// A hand-written list is the defect this file records, one level up: it covers the kinds
    /// somebody thought of on the day. Reflecting the enum means a kind added tomorrow is swept
    /// without anyone remembering this file exists — the sweep cannot go stale because there is no
    /// second list to keep in step. <c>Float</c> is excluded because it leaves the docked tree
    /// entirely, so "which zone did it land in" has no answer for it; that is a different contract,
    /// asserted elsewhere.
    /// </remarks>
    private static IEnumerable<DropKind> EveryDockingKind() =>
        Enum.GetValues<DropKind>().Where(k => k != DropKind.Float);

    /// <summary>Every zone's stack id, likewise derived from <see cref="ZoneId"/>.</summary>
    private static IEnumerable<string> EveryZoneStack() =>
        Enum.GetValues<ZoneId>().Select(StackIdOf);

    private static string StackIdOf(ZoneId zone) => zone switch
    {
        ZoneId.Left => ZonesToTree.LeftStackId,
        ZoneId.Right => ZonesToTree.RightStackId,
        ZoneId.Bottom => ZonesToTree.BottomStackId,
        ZoneId.Center => ZonesToTree.CenterStackId,
        _ => throw new ArgumentOutOfRangeException(
            nameof(zone), zone,
            "a zone was added and this sweep has no stack id for it — that is the finding, not a "
            + "test-maintenance chore: the mover's behaviour on the new zone is unasserted"),
    };

    private static string? StackOf(ZoneBackedLayoutService service, string surfaceId) =>
        service.Current.AllStacks().FirstOrDefault(s => s.Surfaces.Any(x => x.SurfaceId == surfaceId))?.Id;

    private static ZoneBackedLayoutService Seeded(out string graphStack)
    {
        var service = new ZoneBackedLayoutService();

        var stack = service.Current.AllStacks().FirstOrDefault(s => s.Surfaces.Any(x => x.Kind == "canvas"));
        Assert.NotNull(stack);

        graphStack = stack!.Id;
        return service;
    }

    [Fact]
    public void EveryDropKindLandsInTheZoneItTargeted()
    {
        // THE DEFECT, swept across every combination rather than the one that was reported. Measured
        // before the fix: every split onto a side zone resolved to the centre; only JoinStack
        // honoured its target.
        var wrong = new List<string>();

        foreach (var target in EveryZoneStack())
        {
            foreach (var kind in EveryDockingKind())
            {
                var service = Seeded(out var graphStack);
                var doc = new Surface($"doc-{target}-{kind}", "codeviewer", "Source");

                service.Apply(new LayoutOperation.AddSurface(graphStack, doc));
                service.Apply(new LayoutOperation.MoveSurface(doc.SurfaceId, new DropTarget(target, kind)));

                var landed = StackOf(service, doc.SurfaceId);

                if (landed != target) wrong.Add($"{kind} onto {target} landed in {landed}");
            }
        }

        Assert.True(wrong.Count == 0,
            "these drops did not land where they were dropped: " + string.Join("; ", wrong));
    }

    [Fact]
    public void TheAnnouncementNamesTheZoneTheUserChose()
    {
        // The confidently-wrong half. The move succeeded and said "within the center" for a drop on
        // the LEFT — a screen-reader user was told it worked and told the wrong place. The honest
        // data existed; what reached the user was a statement about somewhere else.
        var service = Seeded(out var graphStack);
        var doc = new Surface("doc-announce", "codeviewer", "Source");

        service.Apply(new LayoutOperation.AddSurface(graphStack, doc));

        var result = service.Apply(new LayoutOperation.MoveSurface(
            doc.SurfaceId, new DropTarget(ZonesToTree.LeftStackId, DropKind.SplitLeft)));

        Assert.True(result.Applied);
        Assert.DoesNotContain("center", result.Announcement, StringComparison.OrdinalIgnoreCase);
        Assert.Contains("left", result.Announcement, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public void TheSurfaceIsNeverLost()
    {
        // The invariant the original fallback protected. A placement rule that could drop a pane on
        // the floor would be a worse defect than either of the two this file records.
        foreach (var target in EveryZoneStack())
        {
            foreach (var kind in EveryDockingKind())
            {
                var service = Seeded(out var graphStack);
                var doc = new Surface($"keep-{target}-{kind}", "codeviewer", "Source");

                service.Apply(new LayoutOperation.AddSurface(graphStack, doc));
                service.Apply(new LayoutOperation.MoveSurface(doc.SurfaceId, new DropTarget(target, kind)));

                Assert.NotNull(StackOf(service, doc.SurfaceId));
            }
        }
    }

    [Fact]
    public void AnUnknownTargetStillLandsSomewhere()
    {
        // The documented fallback, kept and now asserted: an id no zone claims resolves to the
        // Center rather than losing the surface.
        var service = Seeded(out var graphStack);
        var doc = new Surface("doc-unknown", "codeviewer", "Source");

        service.Apply(new LayoutOperation.AddSurface(graphStack, doc));
        service.Apply(new LayoutOperation.MoveSurface(
            doc.SurfaceId, new DropTarget("not-a-zone", DropKind.SplitRight)));

        Assert.Equal(ZonesToTree.CenterStackId, StackOf(service, doc.SurfaceId));
    }
}
