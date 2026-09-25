using System.Collections.Immutable;
using System.Diagnostics;

namespace AiDe.Core.Workbench;

/// <summary>
/// An <see cref="ILayoutService"/> whose real state is a <see cref="WorkbenchLayout"/> of named zones,
/// projected to a fixed-shape <see cref="Layout"/> tree for the existing adapter/persistence to render
/// (ADR-0021). Every tree-shaped operation is translated to a zone-scoped one, so an operation on one
/// pane changes only the zone(s) it names — the frame cannot "flip" (defect class DC-063). This is the
/// Strangler that lets the layout logic become zone-based without touching the adapter, controller,
/// persistence or shell wiring, all of which speak <see cref="ILayoutService"/>.
/// </summary>
public sealed class ZoneBackedLayoutService : ILayoutService
{
    private static readonly ActivitySource Activity = new("aide.workbench.operation");
    private int _floatSeq;

    private WorkbenchLayout _zones;
    private Layout? _projection;

    public ZoneBackedLayoutService(WorkbenchLayout? initial = null)
        : this(SurfaceAdmission.Unrestricted, initial)
    {
    }

    /// <summary>
    /// A host's service: <paramref name="admission"/> is the perspective's allow-list and
    /// one-instance rule, enforced at open, restore and reset (ADR-0031 rule 3). The initial
    /// arrangement — <paramref name="initial"/>, else the default — is filtered by the same rule, so
    /// the host never starts holding a kind it would refuse.
    /// </summary>
    public ZoneBackedLayoutService(SurfaceAdmission admission, WorkbenchLayout? initial = null)
    {
        Admission = admission ?? throw new ArgumentNullException(nameof(admission));
        var filtered = Admission.Filter(initial ?? SeedDefault(Admission));
        _zones = filtered.Layout;
        DefaultDropped = initial is null ? filtered.Dropped : [];
    }

    /// <summary>
    /// The seed a host with no explicit initial arrangement starts from: a real (non-Unrestricted)
    /// admission gets ITS perspective's own §B4 table (<see cref="WorkbenchLayout.Default(Perspective)"/>,
    /// SH-3); the bare/test <see cref="SurfaceAdmission.Unrestricted"/> keeps the legacy combined seed
    /// so every existing bare-service construction is unchanged.
    /// </summary>
    private static WorkbenchLayout SeedDefault(SurfaceAdmission admission) =>
        admission.IsUnrestricted ? WorkbenchLayout.Default() : WorkbenchLayout.Default(admission.Perspective);

    /// <summary>
    /// What the seed default dropped to satisfy this host's invariant — non-empty only while the
    /// one <see cref="WorkbenchLayout.Default"/> seeds a kind or a duplicate a perspective refuses
    /// (today: Architecture drops the second <c>view</c>). The shell records it; a construction that
    /// dropped something is on record, never silent.
    /// </summary>
    public IReadOnlyList<DroppedSurface> DefaultDropped { get; }

    /// <summary>The allow-list this host enforces; <see cref="SurfaceAdmission.Unrestricted"/> for a bare service.</summary>
    public SurfaceAdmission Admission { get; }

    /// <summary>The zone model — the real source of truth behind the projected tree.</summary>
    public WorkbenchLayout Zones => _zones;

    /// <summary>
    /// The arrangement this host starts from and resets to: the default, holding only admitted
    /// kinds and at most one of each one-instance kind.
    /// </summary>
    /// <remarks>
    /// SH-3: seeded from THIS host's own §B4 table (<see cref="SeedDefault"/>), not the old combined
    /// seed filtered down — the source of the "Domain wired to the Evidence list" and "Explore/
    /// Provenance/Contexts/Joins stacked as sibling tabs" defects a shared, generic seed produced.
    /// Still run through <see cref="SurfaceAdmission.Filter"/>: defensive, and what applies the
    /// one-instance rule for a caller that mutates the seed before this runs.
    /// </remarks>
    public WorkbenchLayout DefaultLayout() => Admission.Filter(SeedDefault(Admission)).Layout;

    /// <summary>
    /// Replaces the whole zone arrangement (persistence restore), dropping what this host does not
    /// admit and reporting each drop (ADR-0032 rule 2). Zero surfaces left → the default is applied
    /// and the report says so; the host is never four empty zones.
    /// </summary>
    public ZoneRestoreReport RestoreZones(WorkbenchLayout zones)
    {
        ArgumentNullException.ThrowIfNull(zones);

        var filtered = Admission.Filter(zones);
        var defaulted = !Admission.IsUnrestricted && !filtered.Layout.AllSurfaces().Any();
        Set(defaulted ? DefaultLayout() : filtered.Layout);
        return new ZoneRestoreReport(filtered.Dropped, defaulted);
    }

    public Layout Current => _projection ??= ZonesToTree.ToTree(_zones);

    public bool IsLocked { get; set; }

    public void Restore(Layout layout)
    {
        ArgumentNullException.ThrowIfNull(layout);

        // Two callers reach here through one ILayoutService.Restore:
        //  (1) the native-drag reconcile passes a FIXED-FRAME tree — map it by POSITION so a tab
        //      dragged into another zone's pane follows the drag (not reclassified by kind);
        //  (2) persistence/migration passes an arbitrary or legacy tree — position mapping returns
        //      null and we fall back to kind-based conversion (AC-F9). A reconcile shape we cannot
        //      map confidently also returns null, and the fallback keeps the surfaces without a flip.
        Set(Admission.Filter(TryMapByPosition(layout, _zones) ?? TreeToZones.Convert(layout)).Layout);
    }

    /// <summary>
    /// Reconciles a native drag from the VIEW's fixed-frame tree by POSITION only. Returns true when it
    /// mapped confidently and applied; returns <b>false without touching the model</b> when it cannot —
    /// so an unmappable drag reverts (the dragged pane snaps back) rather than falling through to the
    /// kind-based conversion, which re-seats <i>every</i> stack and moved a bystander zone on a single
    /// drag ("I moved joins and contexts moved too", smoke 9-2 #3). Kind conversion belongs only to the
    /// persistence/migration path (<see cref="Restore"/>), never to a live drag.
    /// </summary>
    public bool ReconcileFromView(Layout layout)
    {
        ArgumentNullException.ThrowIfNull(layout);

        var mapped = TryMapByPosition(layout, _zones);
        if (mapped is null)
        {
            return false; // not confident — leave the model as it is; the next Render reverts the drag
        }

        Set(mapped);
        return true;
    }

    /// <summary>
    /// Maps a fixed-frame tree back to zones — by the view's pane IDENTITY where it survives, by
    /// content majority where it does not, by position for a column the drag split off — using the
    /// current model to keep what the view cannot show. Returns null for any shape that is not the
    /// expected frame — the caller then falls back to kind-based conversion. This is what makes a
    /// native tab drag between zones follow the drop instead of snapping back to the surface's kind-zone.
    /// </summary>
    /// <remarks>
    /// <para><b>The model's zones, not only the rendered ones (F-1; Rulings 83/88).</b> A collapsed
    /// tool zone that still holds panes is not in the view — by design, it is a rail. The mapping
    /// used to pre-seed Left, Center and Right as EMPTY and fill them from the view's columns, so a
    /// collapsed-holding side zone came out empty, the surface-set guard saw its panes go missing
    /// and refused the whole drag — <i>"a collapsed panel still holds panes"</i> — for as long as
    /// the zone stayed collapsed; maximize-on-create collapsed two of them, so every drag after a
    /// New Session reverted (the operator's finding 4). A zone the view cannot show keeps what the
    /// model holds; a column the operator dropped on its side joins it and expands it. The guard is
    /// unchanged: a surface the view lost is still a refusal.</para>
    /// <para><b>Identity first.</b> The adapter names each rendered pane with its zone's stack id and
    /// reads that name back (<c>ILayoutPaneSerializable.Id</c>), so a pane that survived the drag says
    /// which zone it is. Content majority — the anchor rule before this — mis-anchored a tie: a Left
    /// of one surface and a Center of two after one moved into the Left both counted one in the
    /// Left's column, the Center won the tie by rule, and the drag moved the SESSION to the Center
    /// (DC-063's bystander class). Majority remains the fallback for a tree with no pane names.</para>
    /// <para><b>The placeholder is the Center.</b> The view's Center pane shows
    /// <see cref="ZonesToTree.WelcomePlaceholder"/> while the model's Center is empty, and a document
    /// dropped INTO that pane sits beside it. The placeholder is view-only: it identifies the Center's
    /// column and is filtered out of every assignment, never entering the model.</para>
    /// </remarks>
    internal static WorkbenchLayout? TryMapByPosition(Layout tree, WorkbenchLayout current)
    {
        static bool IsPlaceholder(Surface s) => string.Equals(s.SurfaceId, ZonesToTree.WelcomePlaceholder.SurfaceId, StringComparison.Ordinal);

        // Split the root into the columns row and (optionally) the bottom zone. A vertical root is
        // the frame's own shape — columns over the Bottom — whether the Bottom was rendered or a drop
        // on the bottom edge just made the row (the Bottom collapsed and holding: the drop joins it,
        // below). Any other vertical shape is not our frame: reading it as one column would hand
        // every Center tab to whichever zone claimed the column first (the WPF lens's finding).
        LayoutNode columns = tree.Root;
        LayoutNode? bottom = null;
        if (tree.Root is SplitNode { Orientation: Orientation.Vertical } vertical)
        {
            if (vertical.Children.Count != 2 || vertical.Children[1] is SplitNode { Orientation: Orientation.Vertical })
            {
                return null;
            }

            columns = vertical.Children[0];
            bottom = vertical.Children[1];
        }

        // The columns row holds the side and center zones. A native drag can INSERT a column (a new
        // side pane) or REORDER them, so a column's zone is never its raw index: index-based mapping
        // ("first is Left, last is Right") scatters a real zone the moment a dragged pane reads first
        // or last (smoke 9-1 #10).
        var colChildren = columns is SplitNode { Orientation: Orientation.Horizontal } split
            ? split.Children.ToList()
            : [columns];

        var anchorZone = new Dictionary<int, ZoneId>();
        var claimed = new HashSet<ZoneId>();

        void Claim(int column, ZoneId zone)
        {
            anchorZone[column] = zone;
            claimed.Add(zone);
        }

        // 1. Identity: a column holding a pane the adapter named for a zone IS that zone; a column
        //    holding the Center's placeholder is the Center.
        for (var i = 0; i < colChildren.Count; i++)
        {
            var named = StackIdsUnder(colChildren[i]).Select(ZonesToTree.ZoneOfStackId).FirstOrDefault(z => z is not null && z != ZoneId.Bottom);
            if (named is { } byName && !claimed.Contains(byName))
            {
                Claim(i, byName);
            }
            else if (!claimed.Contains(ZoneId.Center) && SurfacesUnder(colChildren[i]).Any(IsPlaceholder))
            {
                Claim(i, ZoneId.Center);
            }
        }

        // 2. Majority, for a zone no pane names (a tree with no pane names, or a pane AvalonDock
        //    re-created): the unclaimed column holding the largest SHARE of the zone's prior
        //    surfaces — a share, not a count, so a small zone is not out-voted by a large one that
        //    lost a tab into it. Greedy over every (zone, column) pair by descending share.
        var candidates = new List<(double Share, ZoneId Zone, int Column)>();
        foreach (var zone in new[] { ZoneId.Left, ZoneId.Center, ZoneId.Right })
        {
            if (claimed.Contains(zone))
            {
                continue;
            }

            var owned = current.Zone(zone).Surfaces().Select(s => s.SurfaceId).ToHashSet(StringComparer.Ordinal);
            if (owned.Count == 0)
            {
                continue;
            }

            for (var i = 0; i < colChildren.Count; i++)
            {
                if (anchorZone.ContainsKey(i))
                {
                    continue;
                }

                var count = SurfacesUnder(colChildren[i]).Count(s => owned.Contains(s.SurfaceId));
                if (count > 0)
                {
                    candidates.Add(((double)count / owned.Count, zone, i));
                }
            }
        }

        foreach (var (_, zone, column) in candidates.OrderByDescending(c => c.Share).ThenBy(c => c.Column))
        {
            if (!claimed.Contains(zone) && !anchorZone.ContainsKey(column))
            {
                Claim(column, zone);
            }
        }

        // 3. The Center is mandatory. Unnamed and owning nothing to anchor by — the Coding default
        //    before any session opens (Ruling 55d/60) — the one column no side zone claims IS the
        //    Center, by elimination; still refuse when that leaves more than one candidate, never
        //    guess. Every column claimed by a side zone and no Center column: the Center is empty.
        var unclaimed = Enumerable.Range(0, colChildren.Count).Where(i => !anchorZone.ContainsKey(i)).ToList();
        if (!claimed.Contains(ZoneId.Center))
        {
            if (unclaimed.Count == 1)
            {
                Claim(unclaimed[0], ZoneId.Center);
                unclaimed.Clear();
            }
            else if (unclaimed.Count > 1)
            {
                return null; // no column carries the Center's content — not our frame; let the caller revert
            }
        }

        var centerIndex = anchorZone.Where(kv => kv.Value == ZoneId.Center).Select(kv => kv.Key).DefaultIfEmpty(-1).First();
        if (centerIndex < 0 && unclaimed.Count > 0)
        {
            return null; // a split-off column with no Center to be beside — ambiguous; revert
        }

        var assigned = new Dictionary<ZoneId, List<Surface>>();

        // The view's ACTIVE surface per zone, so the model catches up to the tab the user is looking
        // at rather than resetting every reconciled stack to its first tab (INV-0006's class: a
        // reconcile that rebuilt the stack with ActiveIndex 0 moved the active tab on the next
        // render — SH-1's seam note, measured by SH-2's create-failure test).
        var activeIn = new Dictionary<ZoneId, string>();

        for (var i = 0; i < colChildren.Count; i++)
        {
            var target = anchorZone.TryGetValue(i, out var z)
                ? z
                // A dragged column with no anchor joins the side it now sits on relative to the Center:
                // a drop to the right lands in the Right zone even when it was empty, a drop to the left
                // lands in Left — never merged into the Center or swapped to the wrong side.
                : i < centerIndex ? ZoneId.Left : ZoneId.Right;
            if (!assigned.TryGetValue(target, out var list))
            {
                assigned[target] = list = [];
            }

            list.AddRange(SurfacesUnder(colChildren[i]).Where(s => !IsPlaceholder(s)));
            if (!activeIn.ContainsKey(target) && ActiveUnder(colChildren[i]) is { } active && !string.Equals(active, ZonesToTree.WelcomePlaceholder.SurfaceId, StringComparison.Ordinal))
            {
                activeIn[target] = active;
            }
        }

        if (bottom is not null)
        {
            var below = SurfacesUnder(bottom).Where(s => !IsPlaceholder(s)).ToList();
            if (below.Count == 0)
            {
                return null; // a bottom row holding nothing but the placeholder is not our frame
            }

            assigned[ZoneId.Bottom] = below;
            if (ActiveUnder(bottom) is { } activeBottom)
            {
                activeIn[ZoneId.Bottom] = activeBottom;
            }
        }

        // Build the result from the current model (so extents are preserved), replacing each zone's
        // content with what the view assigned it. A zone the view could not show — collapsed, still
        // holding — keeps the model's content; a rendered zone the view no longer shows is empty.
        var result = current;
        foreach (var id in Enum.GetValues<ZoneId>())
        {
            var zone = result.Zone(id);
            var hidden = zone.Collapsed && !zone.IsEmpty;
            var arrived = assigned.TryGetValue(id, out var surfaces) ? surfaces : [];

            if (hidden && arrived.Count == 0)
            {
                continue; // the rail keeps its panes
            }

            if (id == ZoneId.Bottom && bottom is null && !hidden)
            {
                continue; // an empty Bottom that was not rendered has nothing to catch up to
            }

            var tabs = hidden
                ? [.. zone.Surfaces(), .. arrived]   // a drop on a rail's side joins it — and shows it
                : arrived;
            var activeIndex = activeIn.TryGetValue(id, out var activeId)
                ? Math.Max(0, tabs.FindIndex(s => string.Equals(s.SurfaceId, activeId, StringComparison.Ordinal)))
                : 0;
            ZoneContent? content = tabs.Count == 0 ? null : new ZoneStack([.. tabs], activeIndex);
            result = result.WithZone(zone with { Content = content, Collapsed = zone.Collapsed && !hidden });
        }

        // The strong guard: a reconcile that lost, duplicated or invented a surface is corrupt — refuse
        // and let the caller fall back rather than render a dropped pane.
        var before = current.AllSurfaces().Select(s => s.SurfaceId).ToHashSet(StringComparer.Ordinal);
        var after = result.AllSurfaces().Select(s => s.SurfaceId).ToList();
        if (after.Count != before.Count || !after.ToHashSet(StringComparer.Ordinal).SetEquals(before))
        {
            return null;
        }

        result.AssertInvariant();
        return result;
    }

    /// <summary>Every stack id under <paramref name="node"/> — the pane names the adapter wrote at render.</summary>
    private static IEnumerable<string> StackIdsUnder(LayoutNode node) => node switch
    {
        StackNode s => [s.Id],
        SplitNode p => p.Children.SelectMany(StackIdsUnder),
        _ => [],
    };

    /// <summary>The active surface of the first stack under <paramref name="node"/> — the tab the view shows — or null.</summary>
    private static string? ActiveUnder(LayoutNode node) => node switch
    {
        StackNode s => s.Surfaces.Count > 0 ? s.Active.SurfaceId : null,
        SplitNode p => p.Children.Select(ActiveUnder).FirstOrDefault(a => a is not null),
        _ => null,
    };

    private static IReadOnlyList<Surface> SurfacesUnder(LayoutNode node)
    {
        var surfaces = new List<Surface>();
        Walk(node);
        return surfaces;

        void Walk(LayoutNode n)
        {
            switch (n)
            {
                case StackNode s:
                    surfaces.AddRange(s.Surfaces);
                    break;
                case SplitNode p:
                    foreach (var child in p.Children)
                    {
                        Walk(child);
                    }

                    break;
            }
        }
    }

    public LayoutResult Apply(LayoutOperation operation)
    {
        using var activity = Activity.StartActivity("aide.workbench.operation");
        activity?.SetTag("operation.kind", operation.GetType().Name);
        activity?.SetTag("layout.model", "zones");

        if (IsLocked && operation is not LayoutOperation.ActivateSurface)
        {
            return Refuse(LayoutErrorCodes.Locked, "Layout is locked. Unlock to rearrange panes.");
        }

        // The allow-list, at open (ADR-0031 rule 3; US-C3 b1): a surface of a kind this perspective
        // does not admit never enters the host, whatever path asked, and the refusal names where it
        // belongs so the caller can route it (ADR-0030 Resolve) or say so.
        if (operation is LayoutOperation.AddSurface add)
        {
            if (!Admission.Admits(add.Surface.Kind))
            {
                var home = Admission.AdmittedBy(add.Surface.Kind);
                return Refuse(SurfaceAdmission.RefusalCode, home is null
                    ? $"{add.Surface.Title} cannot open in {Admission.Perspective.Title}: no perspective admits a '{add.Surface.Kind}' surface."
                    : $"{add.Surface.Title} cannot open in {Admission.Perspective.Title}; it belongs to {home.Title}.");
            }

            // The one-instance rule, at open (the same invariant restore enforces — ADR-0032 rule 2):
            // a second surface of a one-instance kind is refused with the first named, never added.
            if (Admission.IsOneInstance(add.Surface.Kind)
                && _zones.AllSurfaces().FirstOrDefault(s => string.Equals(s.Kind, add.Surface.Kind, StringComparison.Ordinal)) is { } existing
                && !string.Equals(existing.SurfaceId, add.Surface.SurfaceId, StringComparison.Ordinal))
            {
                return Refuse(SurfaceAdmission.OneInstanceCode,
                    $"{add.Surface.Title} is already open ({existing.Title}); {Admission.Perspective.Title} holds one.");
            }
        }

        ZoneLayoutResult zoneResult;
        try
        {
            zoneResult = operation switch
            {
                LayoutOperation.MoveSurface op => Move(op),
                LayoutOperation.AddSurface op => ZoneLayoutService.OpenPane(_zones, op.Surface, ZoneFor(op.StackId)),
                LayoutOperation.CloseSurface op => ZoneLayoutService.ClosePane(_zones, op.SurfaceId),
                LayoutOperation.ActivateSurface op => ZoneLayoutService.Activate(_zones, op.SurfaceId),
                LayoutOperation.ReorderSurface op => Reorder(op),
                LayoutOperation.ResizeSplit op => Resize(op),
                LayoutOperation.SetStackState op => SetState(op),
                LayoutOperation.ResetToDefault => new ZoneLayoutResult(
                    DefaultLayout(), true, null, "Workbench layout reset to the default."),
                _ => new ZoneLayoutResult(_zones, false, LayoutErrorCodes.InvalidTarget, "Unsupported layout operation."),
            };
        }
        catch (InvalidOperationException ex)
        {
            return Refuse(LayoutErrorCodes.InvalidTarget, ex.Message);
        }

        if (zoneResult.Applied)
        {
            Set(zoneResult.Layout);
        }

        activity?.SetTag("outcome", zoneResult.Applied ? "applied" : "refused");
        activity?.SetTag("error.code", zoneResult.RefusalCode);
        return new LayoutResult(Current, zoneResult.Applied, zoneResult.RefusalCode, zoneResult.Announcement);
    }

    // ── operation translation ──────────────────────────────────────────────────────────────

    private ZoneLayoutResult Move(LayoutOperation.MoveSurface op)
    {
        if (op.Target.Kind == DropKind.Float)
        {
            return Float(op.SurfaceId);
        }

        // A DROP LANDS WHERE IT WAS DROPPED, whatever gesture made it.
        //
        // A zone layout cannot split WITHIN a zone — that is what zones are — so every non-float
        // drop resolves to the zone it targeted, and the split kinds differ from JoinStack only in
        // the gesture, not the destination.
        //
        // This briefly remapped the split kinds to a neighbouring zone, to make a
        // "split beside the graph" placement land beside the graph rather than on it. That was a
        // PLACEMENT POLICY translation put in a USER GESTURE handler, and it did what such a thing
        // always does: a user dragging a pane onto the left zone with a split gesture had it sent
        // to the centre, announced as "moved within the center" — a drop that reports success and
        // names a destination nobody asked for. Measured across every kind and zone by the design
        // session; only JoinStack honoured its target.
        //
        // The "beside" rule belongs to the caller that wants it, and lives there:
        // `WorkbenchShell.OpenReferenceDocument` adds a reference document straight into the
        // neighbouring zone. A policy that needs a different destination should ask for that
        // destination, not rely on the mover to reinterpret the one it gave.
        //
        // Unknown ids still fall back to the Center so a move is never silently lost.
        var zone = ZonesToTree.ZoneOfStackId(op.Target.TargetNodeId) ?? ZoneId.Center;

        return ZoneLayoutService.MovePane(_zones, op.SurfaceId, zone);
    }

    private ZoneLayoutResult Float(string surfaceId)
    {
        var zoneId = _zones.FindZoneOf(surfaceId);
        if (zoneId is null)
        {
            return new ZoneLayoutResult(_zones, false, LayoutErrorCodes.SurfaceUnknown, $"No surface “{surfaceId}”.");
        }

        var surface = _zones.Zone(zoneId.Value).Surfaces().First(s => s.SurfaceId == surfaceId);
        var removed = ZoneLayoutService.ClosePane(_zones, surfaceId).Layout;
        var floated = removed with
        {
            Floating = removed.Floating.Add(
                new StackNode($"float-{++_floatSeq}", [surface], 0, StackState.Floating)),
        };
        return new ZoneLayoutResult(floated, true, null, $"{surface.Title} is now floating.");
    }

    private ZoneLayoutResult Reorder(LayoutOperation.ReorderSurface op)
    {
        var zoneId = ZonesToTree.ZoneOfStackId(op.StackId);
        if (zoneId is null || _zones.Zone(zoneId.Value).Content is not ZoneStack stack)
        {
            return new ZoneLayoutResult(_zones, false, LayoutErrorCodes.InvalidTarget, "Cannot reorder that pane.");
        }

        var from = Math.Clamp(op.From, 0, stack.Tabs.Count - 1);
        var to = Math.Clamp(op.To, 0, stack.Tabs.Count - 1);
        if (from == to)
        {
            return new ZoneLayoutResult(_zones, false, null, string.Empty);
        }

        var moved = stack.Tabs[from];
        var tabs = stack.Tabs.RemoveAt(from).Insert(to, moved);
        var next = _zones.WithZone(_zones.Zone(zoneId.Value) with
        {
            Content = new ZoneStack(tabs, tabs.IndexOf(moved)),
        });
        return new ZoneLayoutResult(next, true, null, $"Reordered {moved.Title}.");
    }

    private ZoneLayoutResult Resize(LayoutOperation.ResizeSplit op)
    {
        // Map a split-edge resize to a zone extent nudge. The bottom row and the side columns are the
        // only resizable boundaries; the Center absorbs the remainder (AC-F6).
        var zone = op.SplitId switch
        {
            ZonesToTree.RootSplitId => ZoneId.Bottom,
            ZonesToTree.ColumnsSplitId => op.EdgeIndex == 0 && ColumnsStartWithLeft() ? ZoneId.Left : ZoneId.Right,
            _ => (ZoneId?)null,
        };

        if (zone is null)
        {
            return new ZoneLayoutResult(_zones, false, LayoutErrorCodes.InvalidTarget, "That edge cannot be resized.");
        }

        // Bottom grows when the top-of-bottom edge moves up (negative delta); a side grows on a positive delta.
        var current = _zones.Zone(zone.Value).Extent;
        var next = zone == ZoneId.Bottom ? current - op.Delta : current + op.Delta;
        return ZoneLayoutService.ResizeZone(_zones, zone.Value, next);
    }

    private ZoneLayoutResult SetState(LayoutOperation.SetStackState op)
    {
        var zoneId = ZonesToTree.ZoneOfStackId(op.StackId);
        if (zoneId is null)
        {
            return new ZoneLayoutResult(_zones, false, LayoutErrorCodes.InvalidTarget, "Unknown pane.");
        }

        return op.State switch
        {
            StackState.Collapsed or StackState.Hidden => ZoneLayoutService.CollapseZone(_zones, zoneId.Value),
            StackState.Docked => ZoneLayoutService.ExpandZone(_zones, zoneId.Value),
            StackState.Maximized => ZoneLayoutService.Maximize(_zones, zoneId.Value),
            StackState.Floating => Float(_zones.Zone(zoneId.Value).Surfaces().FirstOrDefault()?.SurfaceId ?? string.Empty),
            _ => new ZoneLayoutResult(_zones, false, LayoutErrorCodes.InvalidTarget, "Unsupported state."),
        };
    }

    private bool ColumnsStartWithLeft() =>
        !_zones.Zone(ZoneId.Left).Collapsed && !_zones.Zone(ZoneId.Left).IsEmpty;

    private static ZoneId ZoneFor(string stackId) => ZonesToTree.ZoneOfStackId(stackId) ?? ZoneId.Center;

    private void Set(WorkbenchLayout zones)
    {
        zones.AssertInvariant();
        _zones = zones;
        _projection = null; // invalidate the cached tree projection
    }

    private LayoutResult Refuse(string code, string announcement) =>
        new(Current, false, code, announcement);
}

/// <summary>What a zone restore did to the arrangement it was given: every drop, and whether the default was applied because nothing admissible was left.</summary>
public sealed record ZoneRestoreReport(IReadOnlyList<DroppedSurface> Dropped, bool DefaultApplied);
