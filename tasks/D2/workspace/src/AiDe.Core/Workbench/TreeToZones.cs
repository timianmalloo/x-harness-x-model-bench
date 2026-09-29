using System.Collections.Immutable;

namespace AiDe.Core.Workbench;

/// <summary>
/// Converts a legacy proportional split-tree <see cref="Layout"/> into a <see cref="WorkbenchLayout"/>
/// of named zones. The Expand step of the ADR-0021 migration: existing saved <c>layout.json</c> trees
/// are read through this so no surface is lost and every surface lands in a deterministic zone (AC-F9).
/// </summary>
/// <remarks>
/// Pure and deterministic — the same tree always yields the same zones, which is what lets a golden
/// <c>layout.json</c> fixture pin the conversion. Each tree stack is classified <i>as a unit</i> so its
/// tab grouping survives the move (the graph's document tabs stay together in the Center rather than
/// scattering). Stacks that map to the same zone are concatenated. Floating stacks carry over unchanged.
/// </remarks>
public static class TreeToZones
{
    // Kind → role. A stack is placed by the strongest role any of its surfaces carries.
    private static readonly HashSet<string> CenterKinds = new(StringComparer.OrdinalIgnoreCase)
    {
        "canvas", "code", "diagram", "classdiagram", "class-diagram", "erm", "sequence",
        "prompt", "document", "editor",
    };

    private static readonly HashSet<string> BottomKinds = new(StringComparer.OrdinalIgnoreCase)
    {
        "terminal", "diagnostics", "output", "log", "logs", "tests",
    };

    /// <summary>Converts a tree layout to zones, losing no surface.</summary>
    public static WorkbenchLayout Convert(Layout tree)
    {
        ArgumentNullException.ThrowIfNull(tree);

        // Accumulate surfaces per zone in tree order (which is left-to-right, top-to-bottom), so the
        // conversion is stable and the concatenation order is the reading order.
        var byZone = new Dictionary<ZoneId, List<Surface>>
        {
            [ZoneId.Left] = [], [ZoneId.Right] = [], [ZoneId.Bottom] = [], [ZoneId.Center] = [],
        };

        foreach (var stack in tree.Walk().OfType<StackNode>())
        {
            var zone = ClassifyStack(stack);
            byZone[zone].AddRange(stack.Surfaces);
        }

        var layout = WorkbenchLayout.Empty();
        foreach (var (zone, surfaces) in byZone)
        {
            if (surfaces.Count == 0)
            {
                continue; // leave the zone empty (null content) — rail for a tool zone, placeholder for Center
            }

            var state = layout.Zone(zone) with { Content = new ZoneStack([.. surfaces]) };
            layout = layout.WithZone(state);
        }

        layout = layout with { Floating = tree.Floating };
        layout.AssertInvariant();
        return layout;
    }

    /// <summary>Which zone a tree stack maps to, by the strongest role among its surfaces.</summary>
    internal static ZoneId ClassifyStack(StackNode stack)
    {
        // Center wins first: a stack holding the graph or any document is the document anchor.
        if (stack.Surfaces.Any(s => CenterKinds.Contains(s.Kind)))
        {
            return ZoneId.Center;
        }

        // Then tool panels that belong along the bottom.
        if (stack.Surfaces.Any(s => BottomKinds.Contains(s.Kind)))
        {
            return ZoneId.Bottom;
        }

        // Everything else is an explorer / tool stack on the left.
        return ZoneId.Left;
    }
}
