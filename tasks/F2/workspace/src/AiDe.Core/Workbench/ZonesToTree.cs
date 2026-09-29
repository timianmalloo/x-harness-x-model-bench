using System.Collections.Immutable;

namespace AiDe.Core.Workbench;

/// <summary>
/// Projects a <see cref="WorkbenchLayout"/> of named zones into a <b>fixed-shape</b> legacy
/// <see cref="Layout"/> tree, so the existing AvalonDock adapter, persistence and controller render
/// zones without change (the Strangler-Fig step of ADR-0021). The projected tree is always the same
/// frame — <c>Vertical[ Horizontal[left, center, right], bottom ]</c> — so rendering it can never
/// "flip": closing or opening a pane changes only which surfaces a zone's pane holds, never the frame.
/// </summary>
/// <remarks>
/// Node ids are deterministic per zone (<c>zone-left</c>, <c>zone-center</c>, …) so the projection is
/// stable across renders. Collapsed tool zones are omitted from the tree (their content is retained in
/// the zone model — the rail visual is a later phase). An empty Center still renders, via a synthetic
/// welcome placeholder, because the Center is never absent (AC-F3).
/// </remarks>
public static class ZonesToTree
{
    public const string CenterStackId = "zone-center";
    public const string LeftStackId = "zone-left";
    public const string RightStackId = "zone-right";
    public const string BottomStackId = "zone-bottom";
    public const string ColumnsSplitId = "frame-cols";
    public const string RootSplitId = "frame-root";

    /// <summary>The surface shown when the Center has no documents (kept out of the zone model itself).</summary>
    public static readonly Surface WelcomePlaceholder = new("welcome", "welcome", "Welcome");

    /// <summary>Builds the fixed-shape tree for the current zones.</summary>
    public static Layout ToTree(WorkbenchLayout zones)
    {
        ArgumentNullException.ThrowIfNull(zones);

        var left = VisibleStack(zones, ZoneId.Left, LeftStackId);
        var right = VisibleStack(zones, ZoneId.Right, RightStackId);
        var bottom = VisibleStack(zones, ZoneId.Bottom, BottomStackId);
        var center = CenterStack(zones);

        // The columns row: left | center | right, omitting collapsed/empty tool columns.
        var columnParts = new List<(LayoutNode Node, double Weight)>();
        if (left is not null)
        {
            columnParts.Add((left, zones.Zone(ZoneId.Left).Extent));
        }

        columnParts.Add((center, CenterColumnWeight(zones)));

        if (right is not null)
        {
            columnParts.Add((right, zones.Zone(ZoneId.Right).Extent));
        }

        LayoutNode columns = columnParts.Count == 1
            ? columnParts[0].Node
            : new SplitNode(ColumnsSplitId, Orientation.Horizontal,
                [.. columnParts.Select(p => p.Node)],
                [.. columnParts.Select(p => p.Weight)]);

        // The root: columns over the bottom zone, omitting the bottom when collapsed/empty.
        LayoutNode root = bottom is null
            ? columns
            : new SplitNode(RootSplitId, Orientation.Vertical,
                [columns, bottom],
                [1.0 - zones.Zone(ZoneId.Bottom).Extent, zones.Zone(ZoneId.Bottom).Extent]);

        var layout = new Layout(root, zones.Floating, ImmutableDictionary<string, StackState>.Empty);
        layout.AssertInvariant();
        return layout;
    }

    /// <summary>The projected stack id a zone renders as — the inverse of <see cref="ZoneOfStackId"/>; what an open names to land in a zone.</summary>
    public static string StackIdOf(ZoneId zone) => zone switch
    {
        ZoneId.Left => LeftStackId,
        ZoneId.Right => RightStackId,
        ZoneId.Bottom => BottomStackId,
        _ => CenterStackId,
    };

    /// <summary>Which zone a projected stack id belongs to, or null for an unknown id.</summary>
    public static ZoneId? ZoneOfStackId(string stackId) => stackId switch
    {
        LeftStackId => ZoneId.Left,
        RightStackId => ZoneId.Right,
        BottomStackId => ZoneId.Bottom,
        CenterStackId => ZoneId.Center,
        _ => null,
    };

    private static StackNode? VisibleStack(WorkbenchLayout zones, ZoneId id, string stackId)
    {
        var zone = zones.Zone(id);
        if (zone.Collapsed || zone.IsEmpty)
        {
            return null; // collapsed/empty tool zones are not rendered as panes (content retained in the model)
        }

        return StackFromContent(zone.Content!, stackId);
    }

    private static StackNode CenterStack(WorkbenchLayout zones)
    {
        var center = zones.Zone(ZoneId.Center);
        return center.IsEmpty
            ? new StackNode(CenterStackId, [WelcomePlaceholder])
            : StackFromContent(center.Content!, CenterStackId);
    }

    /// <summary>Flattens zone content to a single stack in tab order (v1 renders a zone as one tab strip).</summary>
    private static StackNode StackFromContent(ZoneContent content, string stackId)
    {
        var surfaces = content.Surfaces().ToImmutableList();
        var active = content is ZoneStack s ? s.ActiveIndex : 0;
        return new StackNode(stackId, surfaces, Math.Clamp(active, 0, surfaces.Count - 1));
    }

    private static double CenterColumnWeight(WorkbenchLayout zones)
    {
        var used = 0.0;
        if (!zones.Zone(ZoneId.Left).Collapsed && !zones.Zone(ZoneId.Left).IsEmpty)
        {
            used += zones.Zone(ZoneId.Left).Extent;
        }

        if (!zones.Zone(ZoneId.Right).Collapsed && !zones.Zone(ZoneId.Right).IsEmpty)
        {
            used += zones.Zone(ZoneId.Right).Extent;
        }

        return Math.Max(0.2, 1.0 - used); // the Center always keeps a meaningful share
    }
}
