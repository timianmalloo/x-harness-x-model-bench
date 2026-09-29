using System.Collections.Immutable;
using AiDe.Core.Workbench;

namespace AiDe.Core.Tests;

/// <summary>
/// The INV-0006 oracle, headless: <b>after any single reconcile, a surface that did not move in the
/// view must not change column in the next render.</b>
/// </summary>
/// <remarks>
/// <para>The measurement is <see cref="WorkbenchLayout.Shape()"/> projected through
/// <see cref="ZonesToTree.ToTree"/> — which column each surface is drawn in — because the defect is
/// invisible in the zone model alone: the reconcile reports success and loses no surface, it swaps the
/// zone <i>labels</i>, and the fixed Left | Center | Right render order then draws both columns on the
/// other side.</para>
/// <para>These are pure Core. What they cannot assert is that AvalonDock's drop produced the view tree
/// they feed in; that link needs a driven docking host (INV-0006 §9).</para>
/// </remarks>
public sealed class WorkbenchDragReconcileOracleTests
{
    // The operator's own session, 2026-09-11 05:59:20 PDT (INV-0006 §1). The model is what the log
    // recorded as live: the workspace-open restore at 05:52:58 plus the session document appended at
    // 05:55:02. No bottom zone — the restore dropped it.
    //
    // These four lists are RECORDED EVIDENCE, not a restatement of a product list, which is why each
    // carries the escape hatch. The surface set is whatever that workspace held on that day — a saved
    // per-workspace arrangement plus a session document opened mid-session — and deriving it from
    // Layout.Default() would substitute today's defaults for the operator's data, which is precisely
    // the input that does NOT reproduce the defect. If the shipped default surfaces change, this
    // fixture must not follow them.

    // fixture-derivation: ok — the operator's recorded zone-left at 05:59:20, not a product list.
    private static readonly string[] ModelLeft = ["graph", "explore", "sources", "contexts", "joins"];

    // fixture-derivation: ok — the operator's recorded zone-center at 05:59:20, not a product list.
    private static readonly string[] ModelCenter = ["domain", "sessions", "board", "leaderboard", "ledger", "session-document:2026-09-11"];

    // fixture-derivation: ok — the first column of screenshot 6, read off the screenshot.
    private static readonly string[] ViewFirstColumn = ["graph", "domain", "explore", "sessions", "board", "leaderboard", "ledger"];

    // fixture-derivation: ok — the second column of screenshot 6, read off the screenshot.
    private static readonly string[] ViewSecondColumn = ["session-document:2026-09-11", "sources", "contexts", "joins"];

    private static WorkbenchLayout OperatorModel() => Zones(ModelLeft, ModelCenter);

    // Screenshot 6, as the operator was looking at it: two columns, in this order.
    private static Layout OperatorScreenshot6View() => TwoColumns(ViewFirstColumn, ViewSecondColumn);

    /// <summary>
    /// The defect, measured on the operator's own data: the deferred regime. Nothing reconciles the
    /// view for 3m49s, so when a command finally does, the reconcile is handed a view that is EIGHT
    /// drags away from the model — and every one of the eleven surfaces is drawn on the other side.
    /// </summary>
    /// <remarks>
    /// This is a CHARACTERIZATION of what production does today, kept as the red witness for INV-0006.
    /// Its input is unreachable once every drag reconciles (see the next test), which is why the fix is
    /// the drag hook and not a change to the mapping heuristic.
    /// </remarks>
    [Fact]
    public void TheOperatorsDriftedView_ReconcilesSilently_AndSwapsBothColumnsWhole()
    {
        var svc = new ZoneBackedLayoutService(OperatorModel());
        var view = OperatorScreenshot6View();
        var onScreen = ColumnOfEachSurface(view);

        var applied = svc.ReconcileFromView(view);

        // It does not refuse, it does not warn, it loses no surface — and it moves everything.
        Assert.True(applied);
        var afterRender = ColumnOfEachSurface(ZonesToTree.ToTree(svc.Zones));
        var moved = onScreen.Keys.Where(id => onScreen[id] != afterRender[id]).ToList();

        Assert.Equal(11, onScreen.Count);
        Assert.Equal(11, moved.Count);
    }

    /// <summary>
    /// The same eight drags, each reconciled as it completes — the regime the drag hook puts every
    /// reconcile into. The oracle holds at every step: only the dragged surface changes column.
    /// </summary>
    [Fact]
    public void TheSameDragsReconciledAsTheyHappen_MoveNothingButTheDraggedSurface()
    {
        var svc = new ZoneBackedLayoutService(OperatorModel());

        // The drift, decomposed into the single-surface moves it is made of: five Center documents
        // pulled into the first column, then three explorers pushed out into the second.
        var drags = new (string Surface, int ToColumn, int AtIndex)[]
        {
            ("domain", 0, 1), ("sessions", 0, 3), ("board", 0, 4),
            ("leaderboard", 0, 5), ("ledger", 0, 6),
            ("sources", 1, 1), ("contexts", 1, 2), ("joins", 1, 3),
        };

        foreach (var (surface, toColumn, atIndex) in drags)
        {
            var before = ZonesToTree.ToTree(svc.Zones);
            var beforeColumns = ColumnOfEachSurface(before);

            var dragged = MoveOneSurface(before, surface, toColumn, atIndex);
            Assert.True(svc.ReconcileFromView(dragged), $"the reconcile refused the drag of {surface}");

            var afterColumns = ColumnOfEachSurface(ZonesToTree.ToTree(svc.Zones));
            var bystandersMoved = beforeColumns.Keys
                .Where(id => id != surface && beforeColumns[id] != afterColumns[id])
                .OrderBy(id => id, StringComparer.Ordinal)
                .ToList();

            Assert.True(bystandersMoved.Count == 0,
                $"dragging {surface} moved {bystandersMoved.Count} bystander(s): "
                + string.Join(", ", bystandersMoved));
            Assert.Equal(toColumn, afterColumns[surface]);
        }

        // And it arrives at exactly the arrangement the operator was looking at in screenshot 6.
        Assert.Equal(
            ColumnOfEachSurface(OperatorScreenshot6View()),
            ColumnOfEachSurface(ZonesToTree.ToTree(svc.Zones)));
    }

    /// <summary>Moves one surface to another column at a given index — one native tab drag.</summary>
    private static Layout MoveOneSurface(Layout tree, string surfaceId, int toColumn, int atIndex)
    {
        var columns = tree.Root is SplitNode { Orientation: Orientation.Horizontal } split
            ? split.Children.Select(c => Under(c).ToList()).ToList()
            : [Under(tree.Root).ToList()];

        var moved = columns.SelectMany(c => c).Single(s => s.SurfaceId == surfaceId);
        foreach (var column in columns) { column.Remove(moved); }
        columns[toColumn].Insert(Math.Clamp(atIndex, 0, columns[toColumn].Count), moved);

        var stacks = columns.Select((c, i) => (LayoutNode)new StackNode($"col{i}", [.. c])).ToList();
        return new Layout(
            stacks.Count == 1
                ? stacks[0]
                : new SplitNode("cols", Orientation.Horizontal, [.. stacks], [.. stacks.Select(_ => 1.0)]),
            [], ImmutableDictionary<string, StackState>.Empty);
    }

    // ── fixtures ───────────────────────────────────────────────────────────────────────────

    private static WorkbenchLayout Zones(string[] left, string[] center)
    {
        var zones = ImmutableDictionary.CreateRange(new[]
        {
            KeyValuePair.Create(ZoneId.Left, new ZoneState(ZoneId.Left, Stack(left), ZoneState.DefaultExtent, Collapsed: false)),
            KeyValuePair.Create(ZoneId.Right, new ZoneState(ZoneId.Right, null, ZoneState.DefaultExtent, Collapsed: false)),
            KeyValuePair.Create(ZoneId.Bottom, new ZoneState(ZoneId.Bottom, null, 0.30, Collapsed: false)),
            KeyValuePair.Create(ZoneId.Center, new ZoneState(ZoneId.Center, Stack(center), 1.0, Collapsed: false)),
        });
        var layout = new WorkbenchLayout(zones, [], null);
        layout.AssertInvariant();
        return layout;
    }

    private static ZoneStack? Stack(string[] ids) =>
        ids.Length == 0 ? null : new ZoneStack([.. ids.Select(SurfaceOf)]);

    private static Surface SurfaceOf(string id) => new(id, KindOf(id), id);

    private static string KindOf(string id) => id switch
    {
        "graph" => "canvas",
        "sources" => "view",
        _ when id.StartsWith("session-document:", StringComparison.Ordinal) => "session-document",
        _ => "view",
    };

    private static Layout TwoColumns(string[] first, string[] second) => new(
        new SplitNode("cols", Orientation.Horizontal,
            [new StackNode("a", [.. first.Select(SurfaceOf)]), new StackNode("b", [.. second.Select(SurfaceOf)])],
            [0.5, 0.5]),
        [], ImmutableDictionary<string, StackState>.Empty);

    /// <summary>Which column index each surface is drawn in — the thing the user sees.</summary>
    private static Dictionary<string, int> ColumnOfEachSurface(Layout tree)
    {
        var columns = tree.Root is SplitNode { Orientation: Orientation.Horizontal } split
            ? split.Children.ToList()
            : [tree.Root];

        var map = new Dictionary<string, int>(StringComparer.Ordinal);
        for (var i = 0; i < columns.Count; i++)
        {
            foreach (var surface in Under(columns[i]))
            {
                map[surface.SurfaceId] = i;
            }
        }

        return map;
    }

    private static IEnumerable<Surface> Under(LayoutNode node) => node switch
    {
        StackNode s => s.Surfaces,
        SplitNode p => p.Children.SelectMany(Under),
        _ => [],
    };
}
