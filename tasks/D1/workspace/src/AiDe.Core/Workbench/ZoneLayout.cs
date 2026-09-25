using System.Collections.Immutable;

namespace AiDe.Core.Workbench;

/// <summary>
/// The four named, absolute regions of the workbench frame. Unlike the proportional split tree
/// (<see cref="Layout"/>), these are <b>stable containers</b>: the frame never restructures, so an
/// operation on a pane can only change the zone(s) that pane belongs to — never relocate or reorient
/// an unrelated pane (defect class DC-063). See <c>adr-0021-named-dock-zones</c>.
/// </summary>
public enum ZoneId
{
    /// <summary>Vertical tool stack on the left (explorers, parked panels). Collapses to a rail.</summary>
    Left,

    /// <summary>Vertical tool stack on the right. Collapses to a rail.</summary>
    Right,

    /// <summary>Horizontal tool stack along the bottom (terminals, diagnostics, output). Collapses to a rail.</summary>
    Bottom,

    /// <summary>The document / editor anchor. Always present; never collapses; may split into editor groups.</summary>
    Center,
}

/// <summary>
/// What a zone holds: either a single tab stack or, within the Center, a split into editor groups.
/// </summary>
/// <remarks>
/// The load-bearing rule is that a <see cref="ZoneSplit"/>'s children never leave the zone — a split
/// is <i>scoped to its zone</i>. That is what keeps the top-level frame from being a tree: there is
/// no operation that restructures the relationship <i>between</i> zones. A zone with no content is
/// represented by a null <see cref="ZoneState.Content"/> (a rail for a tool zone; a placeholder for
/// the Center), not by an empty stack — an empty <see cref="ZoneStack"/> is not constructible.
/// </remarks>
public abstract record ZoneContent
{
    /// <summary>Every surface this content holds, in tab/traversal order.</summary>
    public abstract IEnumerable<Surface> Surfaces();
}

/// <summary>A tab stack of one or more surfaces. The unit v1 tool zones are built from.</summary>
public sealed record ZoneStack : ZoneContent
{
    public ZoneStack(ImmutableList<Surface> surfaces, int activeIndex = 0)
    {
        if (surfaces.Count == 0)
        {
            throw new ArgumentException("a zone stack holds at least one surface", nameof(surfaces));
        }

        Tabs = surfaces;
        ActiveIndex = Math.Clamp(activeIndex, 0, surfaces.Count - 1);
    }

    public ImmutableList<Surface> Tabs { get; init; }

    public int ActiveIndex { get; init; }

    public Surface Active => Tabs[ActiveIndex];

    public override IEnumerable<Surface> Surfaces() => Tabs;
}

/// <summary>
/// A split into editor groups, scoped to its zone (Center only in v1). Its children are themselves
/// zone content, so a group can be a stack or a nested split — but always inside this zone.
/// </summary>
public sealed record ZoneSplit : ZoneContent
{
    public ZoneSplit(Orientation orientation, ImmutableList<ZoneContent> children, ImmutableList<double> weights)
    {
        if (children.Count < 2)
        {
            throw new ArgumentException("a zone split holds at least two children", nameof(children));
        }

        if (children.Count != weights.Count)
        {
            throw new ArgumentException("one weight per child", nameof(weights));
        }

        Orientation = orientation;
        Children = children;
        Weights = SplitNode.Normalize(weights);
    }

    public Orientation Orientation { get; init; }

    public ImmutableList<ZoneContent> Children { get; init; }

    public ImmutableList<double> Weights { get; init; }

    public override IEnumerable<Surface> Surfaces() => Children.SelectMany(c => c.Surfaces());
}

/// <summary>
/// One zone's state: what it holds, its cross-axis size relative to the Center, and whether it is
/// collapsed to a rail. The Center is never collapsed and its <see cref="Extent"/> is ignored (it
/// takes the remaining space).
/// </summary>
public sealed record ZoneState(ZoneId Id, ZoneContent? Content, double Extent, bool Collapsed)
{
    /// <summary>Default cross-axis extent for a tool zone, as a proportion of the frame.</summary>
    public const double DefaultExtent = 0.22;

    public bool IsEmpty => Content is null;

    public IEnumerable<Surface> Surfaces() => Content?.Surfaces() ?? [];
}

/// <summary>The arrangement to restore a maximized zone or pane back to.</summary>
public sealed record MaximizeMemo(ZoneId? Zone, string? SurfaceId, WorkbenchLayout Snapshot);

/// <summary>
/// The whole workbench arrangement as named zones: a fixed frame plus the floating stacks held
/// outside it. Replaces the proportional split tree (<see cref="Layout"/>).
/// </summary>
/// <remarks>
/// All four zones are <b>always present</b> in <see cref="Zones"/> — an empty zone has null content,
/// it is never removed. That is what makes "the Center is always there" and "moving a pane cannot
/// delete a zone" structural rather than rules to remember. Floating stacks live outside the frame,
/// unchanged from the tree model (only docked layout changes in ADR-0021).
/// </remarks>
public sealed record WorkbenchLayout(
    ImmutableDictionary<ZoneId, ZoneState> Zones,
    ImmutableList<StackNode> Floating,
    MaximizeMemo? Maximized)
{
    /// <summary>
    /// Coding's Left extent (Ruling 83 condition 1; DESIGN.md's errata row): the Left is <b>1.3 of
    /// the Center</b> — the mockup's <c>minmax(0,1.3fr) minmax(0,1fr)</c> — spelled as the zone's
    /// share of the columns row (1.3 ⁄ 2.3), which is what <see cref="ZoneState.Extent"/> is. A
    /// document zone, not a tool rail: the thread's 96ch measure plus its gutter must fit at the
    /// startup size, and the App's <c>CodingsLeftExtentTests</c> measures that on the composed tree.
    /// </summary>
    public const double CodingLeftExtent = 1.3 / 2.3;

    /// <summary>The default arrangement: graph document in the Center, a terminal in the Bottom.</summary>
    public static WorkbenchLayout Default()
    {
        var center = new ZoneStack(
        [
            new Surface("graph", "canvas", "Graph"),
            new Surface("domain", "view", "Domain"),
            new Surface("sessions", "sessions", "Sessions"),
            new Surface("board", "board", "Board"),
            new Surface("leaderboard", "leaderboard", "Leaderboard"),
            new Surface("ledger", "ledger", "Ledger"),
        ]);

        var left = new ZoneStack(
        [
            new Surface("explore", "view", "Explore"),
            new Surface("sources", "view", "Sources"),
            new Surface("contexts", "contexts", "Contexts"),
            new Surface("joins", "joins", "Joins"),
        ]);

        var bottom = new ZoneStack(
            [new Surface("terminal-1", "terminal", "Terminal — pwsh")]);

        var zones = ImmutableDictionary.CreateRange(new[]
        {
            KeyValuePair.Create(ZoneId.Left, new ZoneState(ZoneId.Left, left, ZoneState.DefaultExtent, Collapsed: false)),
            KeyValuePair.Create(ZoneId.Right, new ZoneState(ZoneId.Right, Content: null, ZoneState.DefaultExtent, Collapsed: false)),
            KeyValuePair.Create(ZoneId.Bottom, new ZoneState(ZoneId.Bottom, bottom, 0.30, Collapsed: false)),
            KeyValuePair.Create(ZoneId.Center, new ZoneState(ZoneId.Center, center, Extent: 1.0, Collapsed: false)),
        });

        return new WorkbenchLayout(zones, [], Maximized: null);
    }

    /// <summary>
    /// The per-perspective default (Addendum C §B4; Rulings 54/59/60/61/84) — each docking host's OWN
    /// table, never the combined seed <see cref="Default()"/> filtered down (the trap
    /// <c>ZoneBackedLayoutService</c> named: filtering one shared seed re-points "Domain" at the
    /// Evidence list and stacks Explore/Provenance/Contexts/Joins into one Left tab strip).
    /// </summary>
    /// <remarks>
    /// Coding, Architecture and Coordination have a docking host (<see cref="PerspectiveBody.DockHost"/>);
    /// Explore's full-window body has no zone layout and no caller ever asks this for it
    /// (<c>DockHost.Create</c> refuses a non-host perspective first) — so anything other than
    /// Architecture or Coordination falls back to Coding's table, which is the only other member of
    /// the closed set this method is ever actually asked for.
    /// </remarks>
    public static WorkbenchLayout Default(Perspective perspective)
    {
        ArgumentNullException.ThrowIfNull(perspective);

        return perspective.Id switch
        {
            "architecture" => ArchitectureDefault(),
            "coordination" => CoordinationDefault(),
            _ => CodingDefault(),
        };
    }

    /// <summary>
    /// Coding's default (Ruling 60 as re-cut by Rulings 83, 84 and 88; US-C6): <b>Left = session
    /// documents</b> — empty until one opens (an empty <see cref="ZoneStack"/> is not constructible,
    /// so the content is null and the zone renders as its rail), cut at <see cref="CodingLeftExtent"/>
    /// so the thread's 96ch measure fits at the startup size · <b>Center = the empty state</b> — the
    /// session's own copy, never a fleet-view tab strip beside a session (Ruling 55d) · <b>Bottom =
    /// one terminal, collapsed</b> (the operator's <i>Bottom (1)</i>; Ruling 88) · Right = empty.
    /// No Loomkeeper caption and no Explore/Domain/Provenance/Graph/Contexts/Joins caption anywhere
    /// in this host (US-C6's falsifier).
    /// </summary>
    /// <remarks>
    /// <para>The terminal is <b>one gesture away, not started</b>: a collapsed zone is absent from the
    /// projection, so its pane's content — and the shell process a terminal pane starts — is built
    /// when the rail is expanded, not at startup. Measured by the App's <c>CollapsedBottomTests</c>
    /// (no <c>terminal.start</c> until the expand); the alternative — a started shell behind a rail
    /// — costs a process for a pane the operator's five screenshots never showed open.</para>
    /// <para>A default that seeds a kind its own host refuses is a drop at construction, which
    /// <c>TheArchitectureAndCodingDefaults_SeedCleanly_WithNoDrops</c> pins as a defect; every kind
    /// here is Coding's.</para>
    /// </remarks>
    private static WorkbenchLayout CodingDefault()
    {
        var bottom = new ZoneStack([new Surface("terminal-1", "terminal", "Terminal — pwsh")]);

        var zones = ImmutableDictionary.CreateRange(new[]
        {
            KeyValuePair.Create(ZoneId.Left, new ZoneState(ZoneId.Left, Content: null, CodingLeftExtent, Collapsed: false)),
            KeyValuePair.Create(ZoneId.Right, new ZoneState(ZoneId.Right, Content: null, ZoneState.DefaultExtent, Collapsed: false)),
            KeyValuePair.Create(ZoneId.Bottom, new ZoneState(ZoneId.Bottom, bottom, 0.30, Collapsed: true)),
            // The Center holds no surface: the shell's empty copy answers "No session open" /
            // "The session is docked at the left", not a tab strip of Loomkeeper/graph panes.
            KeyValuePair.Create(ZoneId.Center, new ZoneState(ZoneId.Center, Content: null, Extent: 1.0, Collapsed: false)),
        });

        return new WorkbenchLayout(zones, [], Maximized: null);
    }

    /// <summary>
    /// Architecture's default (<b>Ruling 140</b>, amending Ruling 94 — the operator: <i>"the
    /// right-side-views for the architecture explorer need to be Graph and Tree, where tree is the
    /// more familiar dev view like in vs code"</i>): <b>Center = Graph (active), Tree</b> at extent
    /// 1.0 · <b>Left, Right and Bottom = empty, collapsed</b>.
    /// <para><b>Contexts and Domain leave the default and stay admitted</b> — one View-menu gesture
    /// away, their kinds still restorable, exactly as Evidence (<c>view</c>) did under Ruling 94.
    /// Absence from the default is the claim; absence from admission would be the envelope drop the
    /// ruling forbids. The <c>inspector</c> kind is retired from the product (Ruling 94).</para>
    /// <para>The Graph leaves Left with this amendment, so Ruling 94 condition (3)'s header-strip
    /// overflow finding becomes <b>moot rather than fixed</b>: the strip overflowed because the Graph
    /// sat in a 0.22-width zone, and it no longer does.</para>
    /// </summary>
    /// <remarks>
    /// <para>Left · Center · Bottom are the operator's saved slot (their
    /// <c>layout.architecture.zones.json</c>, read at the ruling: Left <c>canvas</c> at 0.22, Center
    /// <c>contexts</c> active then <c>classdiagram</c>, Bottom 0.22 collapsed). The file held the
    /// Right at 0.22 <i>not</i> collapsed; the ruling says collapsed, and the ruling wins.</para>
    /// <para><c>joins</c> is admitted to Architecture (Ruling 59) but left out of THIS default pending
    /// the attended real-content check Ruling 59's CONDITIONS require (a default tab that may render
    /// empty is the Explore-pane defect Ruling 55d already removed) — see
    /// <c>docs/proof/perspective-content.md</c>. It stays reachable from the derived View menu
    /// either way; re-add it here as a Center tab the moment the check finds real content.</para>
    /// </remarks>
    private static WorkbenchLayout ArchitectureDefault()
    {
        // Ruling 140 amends Ruling 94's layout line to the operator's own words: "the right-side-views
        // for the architecture explorer need to be Graph and Tree - where tree is the more familiar dev
        // view like in vs code". The operator's "right-side views" are THIS zone — the pane holding
        // Contexts | Domain in their screenshot — so the request is Center = [Graph, Tree], and the
        // Graph cannot also stay in Left: one Graph, one home. Contexts and Domain leave the default
        // and stay admitted through the View menu, exactly as Evidence does under 94; their kinds stay
        // restorable, so a saved slot carrying them still reconciles.
        //
        // Graph is first, so ZoneStack's ActiveIndex of 0 makes it active. `solution-tree` is the
        // Tree's registered kind (SurfaceContentFactory.cs:179, "Solution tree") — fetched, not
        // invented, per Ruling 140 (a).
        var center = new ZoneStack(
        [
            new Surface("graph", "canvas", "Graph"),
            new Surface("tree", "solution-tree", "Tree"),
        ]);

        var zones = ImmutableDictionary.CreateRange(new[]
        {
            // Left retires its Graph with it, which also makes Ruling 94 condition (3)'s header-strip
            // overflow finding MOOT rather than fixed: the strip overflowed because the Graph sat in a
            // 0.22-width zone, and it no longer does. Recorded as moot, not repaired.
            KeyValuePair.Create(ZoneId.Left, new ZoneState(ZoneId.Left, Content: null, ZoneState.DefaultExtent, Collapsed: true)),
            KeyValuePair.Create(ZoneId.Right, new ZoneState(ZoneId.Right, Content: null, ZoneState.DefaultExtent, Collapsed: true)),
            // (empty, collapsed) per §B4: Diagnostics is a Show entry, not a default.
            KeyValuePair.Create(ZoneId.Bottom, new ZoneState(ZoneId.Bottom, Content: null, ZoneState.DefaultExtent, Collapsed: true)),
            KeyValuePair.Create(ZoneId.Center, new ZoneState(ZoneId.Center, center, Extent: 1.0, Collapsed: false)),
        });

        return new WorkbenchLayout(zones, [], Maximized: null);
    }

    /// <summary>
    /// Architecture's Left extent (Ruling 94 condition 1): the value the operator's own saved slot
    /// holds — <c>0.22</c>, read from their <c>layout.architecture.zones.json</c> — which is also
    /// <see cref="ZoneState.DefaultExtent"/>. Named so the number is the operator's, not a coincidence.
    /// </summary>
    public const double ArchitectureLeftExtent = 0.22;

    /// <summary>
    /// Coordination's default (Ruling 84; §B4's third table — the Owner's arrangement, Inferred until
    /// the operator runs it): the watcher's Terminal sessions list alone in the Left (the master list;
    /// the switch lands here), Ledger · Leaderboard · Message board as three Center tabs — Ledger
    /// first, its rows are the widest — the Right empty, the Bottom empty and collapsed. Daydreams is
    /// admitted and reachable from the View menu, not in the default. Nothing on this bench takes
    /// typed input: no terminal, no session document, no prompt draft (none is admitted).
    /// </summary>
    private static WorkbenchLayout CoordinationDefault()
    {
        var left = new ZoneStack([new Surface("sessions", "sessions", "Terminal sessions")]);
        var center = new ZoneStack(
        [
            new Surface("ledger", "ledger", "Ledger"),
            new Surface("leaderboard", "leaderboard", "Leaderboard"),
            new Surface("board", "board", "Message board"),
        ]);

        var zones = ImmutableDictionary.CreateRange(new[]
        {
            KeyValuePair.Create(ZoneId.Left, new ZoneState(ZoneId.Left, left, ZoneState.DefaultExtent, Collapsed: false)),
            KeyValuePair.Create(ZoneId.Right, new ZoneState(ZoneId.Right, Content: null, ZoneState.DefaultExtent, Collapsed: false)),
            KeyValuePair.Create(ZoneId.Bottom, new ZoneState(ZoneId.Bottom, Content: null, ZoneState.DefaultExtent, Collapsed: true)),
            KeyValuePair.Create(ZoneId.Center, new ZoneState(ZoneId.Center, center, Extent: 1.0, Collapsed: false)),
        });

        return new WorkbenchLayout(zones, [], Maximized: null);
    }

    /// <summary>An empty frame — all four zones present, none with content. Used by the converter as a base.</summary>
    public static WorkbenchLayout Empty()
    {
        var zones = ImmutableDictionary.CreateRange(
            Enum.GetValues<ZoneId>().Select(id => KeyValuePair.Create(
                id, new ZoneState(id, Content: null,
                    id == ZoneId.Center ? 1.0 : ZoneState.DefaultExtent, Collapsed: false))));
        return new WorkbenchLayout(zones, [], Maximized: null);
    }

    public ZoneState Zone(ZoneId id) => Zones[id];

    public IEnumerable<Surface> AllSurfaces() =>
        Zones.Values.SelectMany(z => z.Surfaces()).Concat(Floating.SelectMany(s => s.Surfaces));

    /// <summary>The zone currently holding <paramref name="surfaceId"/>, or null if it is floating/absent.</summary>
    public ZoneId? FindZoneOf(string surfaceId) =>
        Zones.Values.FirstOrDefault(z => z.Surfaces().Any(s => s.SurfaceId == surfaceId))?.Id;

    /// <summary>Replaces one zone's state, leaving the other three byte-identical (the containment primitive).</summary>
    public WorkbenchLayout WithZone(ZoneState zone) =>
        this with { Zones = Zones.SetItem(zone.Id, zone) };

    /// <summary>
    /// The frame invariant, checked after every operation: the four zones exist, the Center is never
    /// collapsed, no surface appears twice, and no stack is empty.
    /// </summary>
    public void AssertInvariant()
    {
        foreach (var id in Enum.GetValues<ZoneId>())
        {
            if (!Zones.ContainsKey(id))
            {
                throw new InvalidOperationException($"zone '{id}' is missing — all four zones are always present");
            }
        }

        if (Zones[ZoneId.Center].Collapsed)
        {
            throw new InvalidOperationException("the Center zone is never collapsed");
        }

        var surfaceIds = AllSurfaces().Select(s => s.SurfaceId).ToList();
        if (surfaceIds.Count != surfaceIds.Distinct(StringComparer.Ordinal).Count())
        {
            throw new InvalidOperationException("a surface appears in more than one zone");
        }
    }

    /// <summary>
    /// Structural signature ignoring extents — the oracle for "which zone holds what, in what order".
    /// Two layouts with the same shape are the same arrangement of panes.
    /// </summary>
    public string Shape()
    {
        var zones = Enum.GetValues<ZoneId>()
            .Select(id => $"{id}:{ShapeOf(Zones[id].Content)}{(Zones[id].Collapsed ? "/collapsed" : "")}");
        return string.Join("|", zones) + "|float:" +
            string.Join(",", Floating.Select(f => "[" + string.Join("+", f.Surfaces.Select(s => s.SurfaceId)) + "]"));
    }

    private static string ShapeOf(ZoneContent? content) => content switch
    {
        null => "-",
        ZoneStack s => $"[{string.Join("+", s.Tabs.Select(t => t.SurfaceId))}@{s.ActiveIndex}]",
        ZoneSplit p => $"({p.Orientation}:{string.Join(",", p.Children.Select(ShapeOf))})",
        _ => "?",
    };
}
