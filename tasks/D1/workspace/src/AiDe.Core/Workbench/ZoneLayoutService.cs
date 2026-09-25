using System.Collections.Immutable;

namespace AiDe.Core.Workbench;

/// <summary>The outcome of a zone-layout operation, carrying the accessibility announcement (SC 4.1.3).</summary>
public sealed record ZoneLayoutResult(WorkbenchLayout Layout, bool Applied, string? RefusalCode, string Announcement);

/// <summary>
/// The zone-scoped layout operations. Every operation names a <see cref="ZoneId"/>, and its effect is
/// confined to that zone (and, for a move, the destination zone) — the other zones come through
/// reference-identical via <see cref="WorkbenchLayout.WithZone"/>. That confinement is the structural
/// remedy for DC-063: there is no operation that restructures the relationship between zones.
/// </summary>
/// <remarks>Pure functions over an immutable <see cref="WorkbenchLayout"/>; no shell/UI dependency.</remarks>
public static class ZoneLayoutService
{
    /// <summary>Moves a surface into <paramref name="target"/>, changing only its source and destination zones.</summary>
    public static ZoneLayoutResult MovePane(
        WorkbenchLayout layout, string surfaceId, ZoneId target, int? dropIndex = null)
    {
        var source = layout.FindZoneOf(surfaceId);
        if (source is null)
        {
            return new ZoneLayoutResult(layout, false, LayoutErrorCodes.SurfaceUnknown,
                $"Cannot move: surface '{surfaceId}' is not docked.");
        }

        var surface = layout.Zone(source.Value).Surfaces().First(s => s.SurfaceId == surfaceId);

        if (source == target)
        {
            // A move within the same zone is a reorder; keep it simple and re-seat as active.
            var same = layout.Zone(target);
            var reseated = AddSurface(RemoveSurface(same.Content, surfaceId), surface, dropIndex);
            var next0 = layout.WithZone(same with { Content = reseated });
            next0.AssertInvariant();
            return new ZoneLayoutResult(next0, true, null,
                $"Moved {surface.Title} within {ZoneName(target)}.");
        }

        var src = layout.Zone(source.Value);
        var dst = layout.Zone(target);

        var srcContent = RemoveSurface(src.Content, surfaceId);
        var dstContent = AddSurface(dst.Content, surface, dropIndex);

        var next = layout
            .WithZone(src with { Content = srcContent })
            .WithZone(dst with { Content = dstContent, Collapsed = false, Extent = UsableExtentFor(dst, target) });

        next.AssertInvariant();
        return new ZoneLayoutResult(next, true, null,
            $"Moved {surface.Title} to {ZoneName(target)}." +
            (srcContent is null ? $" {ZoneName(source.Value)} is now empty." : string.Empty));
    }

    /// <summary>Opens a new surface as the active tab of <paramref name="target"/> — destination-local.</summary>
    public static ZoneLayoutResult OpenPane(WorkbenchLayout layout, Surface surface, ZoneId target)
    {
        if (layout.AllSurfaces().Any(s => s.SurfaceId == surface.SurfaceId))
        {
            // Already open: activate it where it is rather than duplicating.
            return Activate(layout, surface.SurfaceId);
        }

        var dst = layout.Zone(target);
        var next = layout.WithZone(dst with
        {
            Content = AddSurface(dst.Content, surface, dropIndex: null),
            Collapsed = false,
            Extent = UsableExtentFor(dst, target),
        });
        next.AssertInvariant();
        return new ZoneLayoutResult(next, true, null, $"Opened {surface.Title} in {ZoneName(target)}.");
    }

    // A pane arriving into an EMPTY tool zone must land at a usable width, not whatever sliver a
    // previous resize/collapse left behind — the "created but hidden in the container till I widened
    // it" case (smoke 9-1 #4). Only empty tool zones are floored: a zone that already holds panes
    // keeps the width the user chose, and the Center sizes itself from the remainder.
    private static double UsableExtentFor(ZoneState dst, ZoneId target) =>
        dst.IsEmpty && target != ZoneId.Center
            ? Math.Max(dst.Extent, ZoneState.DefaultExtent)
            : dst.Extent;

    /// <summary>Closes a surface, changing only its own zone. The Center never disappears (becomes empty).</summary>
    public static ZoneLayoutResult ClosePane(WorkbenchLayout layout, string surfaceId)
    {
        var zoneId = layout.FindZoneOf(surfaceId);
        if (zoneId is null)
        {
            return new ZoneLayoutResult(layout, false, LayoutErrorCodes.SurfaceUnknown,
                $"Cannot close: surface '{surfaceId}' is not docked.");
        }

        var zone = layout.Zone(zoneId.Value);
        var surface = zone.Surfaces().First(s => s.SurfaceId == surfaceId);
        var next = layout.WithZone(zone with { Content = RemoveSurface(zone.Content, surfaceId) });
        next.AssertInvariant();
        return new ZoneLayoutResult(next, true, null, $"Closed {surface.Title}.");
    }

    /// <summary>Activates a surface's tab in whichever zone holds it.</summary>
    public static ZoneLayoutResult Activate(WorkbenchLayout layout, string surfaceId)
    {
        var zoneId = layout.FindZoneOf(surfaceId);
        if (zoneId is null)
        {
            return new ZoneLayoutResult(layout, false, LayoutErrorCodes.SurfaceUnknown,
                $"Cannot activate: surface '{surfaceId}' is not docked.");
        }

        var zone = layout.Zone(zoneId.Value);
        var next = layout.WithZone(zone with
        {
            Content = SetActive(zone.Content, surfaceId),
            Collapsed = false,
        });
        return new ZoneLayoutResult(next, true, null, string.Empty);
    }

    /// <summary>Collapses a tool zone to its rail; its panes are retained (AC-F4). The Center refuses.</summary>
    public static ZoneLayoutResult CollapseZone(WorkbenchLayout layout, ZoneId zoneId)
    {
        if (zoneId == ZoneId.Center)
        {
            return new ZoneLayoutResult(layout, false, LayoutErrorCodes.InvalidTarget,
                "The Center zone cannot be collapsed.");
        }

        var zone = layout.Zone(zoneId);
        if (zone.Collapsed)
        {
            return new ZoneLayoutResult(layout, false, null, $"{ZoneName(zoneId)} is already collapsed.");
        }

        var next = layout.WithZone(zone with { Collapsed = true });
        return new ZoneLayoutResult(next, true, null, $"Collapsed {ZoneName(zoneId)}.");
    }

    /// <summary>Re-expands a collapsed tool zone, restoring the same panes and active tab.</summary>
    public static ZoneLayoutResult ExpandZone(WorkbenchLayout layout, ZoneId zoneId)
    {
        var zone = layout.Zone(zoneId);
        if (!zone.Collapsed)
        {
            return new ZoneLayoutResult(layout, false, null, $"{ZoneName(zoneId)} is already expanded.");
        }

        var next = layout.WithZone(zone with { Collapsed = false });
        return new ZoneLayoutResult(next, true, null, $"Expanded {ZoneName(zoneId)}.");
    }

    /// <summary>Resizes a tool zone. Only that zone changes size; the Center absorbs the difference (AC-F6).</summary>
    public static ZoneLayoutResult ResizeZone(WorkbenchLayout layout, ZoneId zoneId, double extent)
    {
        if (zoneId == ZoneId.Center)
        {
            return new ZoneLayoutResult(layout, false, LayoutErrorCodes.InvalidTarget,
                "The Center zone sizes itself from the remaining space.");
        }

        var clamped = Math.Clamp(extent, 0.08, 0.6);
        var zone = layout.Zone(zoneId);
        var next = layout.WithZone(zone with { Extent = clamped });
        return new ZoneLayoutResult(next, true, null, $"Resized {ZoneName(zoneId)}.");
    }

    /// <summary>Maximizes a zone (others collapse to rails), snapshotting the arrangement for an exact restore.</summary>
    public static ZoneLayoutResult Maximize(WorkbenchLayout layout, ZoneId zoneId)
    {
        if (layout.Maximized is not null)
        {
            return new ZoneLayoutResult(layout, false, LayoutErrorCodes.InvalidTarget,
                "Something is already maximized; restore it first.");
        }

        var memo = new MaximizeMemo(zoneId, null, layout);
        var zones = layout.Zones;
        foreach (var id in Enum.GetValues<ZoneId>())
        {
            if (id != zoneId && id != ZoneId.Center)
            {
                zones = zones.SetItem(id, zones[id] with { Collapsed = true });
            }
        }

        // Maximizing a tool zone collapses the Center's neighbours; maximizing the Center collapses
        // all tool zones. Either way Restore returns the exact snapshot (AC-F5).
        var next = layout with { Zones = zones, Maximized = memo };
        return new ZoneLayoutResult(next, true, null, $"Maximized {ZoneName(zoneId)}.");
    }

    /// <summary>Restores the arrangement captured at the last <see cref="Maximize"/> — exactly (AC-F5).</summary>
    public static ZoneLayoutResult Restore(WorkbenchLayout layout)
    {
        if (layout.Maximized is null)
        {
            return new ZoneLayoutResult(layout, false, null, "Nothing is maximized.");
        }

        return new ZoneLayoutResult(layout.Maximized.Snapshot, true, null, "Restored the layout.");
    }

    // ---- content helpers (add / remove / activate, scoped to one zone) ------------------------

    /// <summary>Removes a surface from zone content, returning null when the content becomes empty.</summary>
    internal static ZoneContent? RemoveSurface(ZoneContent? content, string surfaceId) => content switch
    {
        null => null,
        ZoneStack s => s.Tabs.All(t => t.SurfaceId == surfaceId)
            ? null
            : RebuildStack(s, s.Tabs.RemoveAll(t => t.SurfaceId == surfaceId), s.Active.SurfaceId),
        ZoneSplit p => CollapseSplit(
            p.Children
                .Select(c => RemoveSurface(c, surfaceId))
                .Where(c => c is not null)
                .Cast<ZoneContent>()
                .ToImmutableList(),
            p.Orientation),
        _ => content,
    };

    /// <summary>Adds a surface to zone content as the new active tab, creating a stack if the zone was empty.</summary>
    internal static ZoneContent AddSurface(ZoneContent? content, Surface surface, int? dropIndex) => content switch
    {
        null => new ZoneStack([surface]),
        ZoneStack s => InsertIntoStack(s, surface, dropIndex),
        // Into a split (Center editor groups): append to the last group so the frame stays scoped
        // to the zone. Editor-group focus is future work; the last group is a stable default.
        ZoneSplit p => p with
        {
            Children = p.Children.SetItem(p.Children.Count - 1,
                AddSurface(p.Children[^1], surface, dropIndex)),
        },
        _ => content,
    };

    private static ZoneContent SetActive(ZoneContent? content, string surfaceId) => content switch
    {
        ZoneStack s when s.Tabs.Any(t => t.SurfaceId == surfaceId) =>
            s with { ActiveIndex = s.Tabs.FindIndex(t => t.SurfaceId == surfaceId) },
        ZoneSplit p => p with
        {
            Children = p.Children.Select(c => SetActive(c, surfaceId)).ToImmutableList(),
        },
        _ => content ?? throw new InvalidOperationException("no content to activate in"),
    };

    private static ZoneStack InsertIntoStack(ZoneStack stack, Surface surface, int? dropIndex)
    {
        var at = Math.Clamp(dropIndex ?? stack.Tabs.Count, 0, stack.Tabs.Count);
        var tabs = stack.Tabs.Insert(at, surface);
        return new ZoneStack(tabs, activeIndex: tabs.FindIndex(t => t.SurfaceId == surface.SurfaceId));
    }

    private static ZoneStack RebuildStack(ZoneStack original, ImmutableList<Surface> tabs, string preferActive)
    {
        var idx = tabs.FindIndex(t => t.SurfaceId == preferActive);
        return new ZoneStack(tabs, activeIndex: idx >= 0 ? idx : Math.Min(original.ActiveIndex, tabs.Count - 1));
    }

    private static ZoneContent? CollapseSplit(ImmutableList<ZoneContent> children, Orientation orientation) =>
        children.Count switch
        {
            0 => null,
            1 => children[0], // a split with one child is scoped and internal — collapsing it stays inside the zone
            _ => new ZoneSplit(orientation, children,
                [.. Enumerable.Repeat(1.0 / children.Count, children.Count)]),
        };

    internal static string ZoneName(ZoneId id) => id switch
    {
        ZoneId.Left => "the left zone",
        ZoneId.Right => "the right zone",
        ZoneId.Bottom => "the bottom zone",
        ZoneId.Center => "the center",
        _ => id.ToString(),
    };
}
