namespace AiDe.Core.Workbench;

/// <summary>What fills the body region while a perspective is active (Addendum C §A6).</summary>
public enum PerspectiveBody
{
    /// <summary>A docking host of surfaces the perspective's allow-list admits.</summary>
    DockHost,

    /// <summary>One full-window surface; the perspective admits no docked kind.</summary>
    FullWindow,
}

/// <summary>
/// One perspective — the use case the whole tool is in (Addendum C, Ruling 50). A row of data,
/// never a class with behaviour: the shell projects it, the rail lists it, the catalog derives its
/// command from it.
/// </summary>
/// <param name="Id">The stable id (<c>coding</c> · <c>explore</c> · <c>architecture</c> · <c>coordination</c>); what the switch event and the layout slot name.</param>
/// <param name="Title">The word the rail, the menu and the window title show.</param>
/// <param name="Order">1-based position in the rail and the digit of the bound gesture (<c>Ctrl+1/2/3/4</c>, D1's decision).</param>
/// <param name="Body">Whether the body is a docking host or one full-window surface.</param>
/// <param name="CommandId">The catalog command that activates it — derived into <see cref="WorkbenchCommandCatalog.All"/> from this row.</param>
/// <param name="Description">What the perspective is for, as the palette's hint says it.</param>
/// <param name="Landing">
/// Where focus lands after a switch to this perspective (spec §C5; DESIGN.md's landing row): the
/// zone whose active tab takes focus — Architecture lands on its Center (Graph), Coordination on
/// its Left (Terminal sessions, the master list), Coding on its Left (the session document, Ruling
/// 83). Null for a body with another rule — Explore's reader. A zone the arrangement has emptied or
/// collapsed falls back to the Center's active tab (the empty copy when the Center is empty), then
/// the body's active surface. Stated on the row because the view's own notion of "active" after a
/// body is first parented is whichever pane control realized last (measured, SH-4.1), which is not
/// a landing anyone chose.
/// </param>
public sealed record Perspective(
    string Id,
    string Title,
    int Order,
    PerspectiveBody Body,
    string CommandId,
    string Description,
    ZoneId? Landing = null)
{
    /// <summary>The bound single-stroke gesture, spelled from the row (US-C10; <c>Ctrl+</c> the rail digit).</summary>
    public string Gesture => $"Ctrl+{Order}";
}

/// <summary>
/// The closed Perspective set (ADR-0030, amended by Ruling 84): four rows in rail order, and the
/// order a kind-open the active perspective does not admit is routed in. Pure data; constructible
/// in any test.
/// </summary>
/// <remarks>
/// <b>Why a static row set and not an enum.</b> An enum in the App beside the presenter was the
/// shape before this (<c>ShellViewMode</c>, two values). The perspective commands must be catalog
/// rows in Core, derived from the set — or the catalog carries a hand-listed copy that a new
/// perspective would silently miss. Rows in Core let the catalog, the rail, the menu radio, the
/// palette and the routed open all read ONE definition — Ruling 84's fourth row (Coordination) was
/// exactly that: one row here, and every derived surface followed. <b>Tests</b> is a reserved name
/// with no row (Ruling 54): adding it is adding a row here, and every derived surface follows.
/// </remarks>
public static class PerspectiveSet
{
    public static Perspective Coding { get; } = new(
        "coding", "Coding", 1, PerspectiveBody.DockHost, "perspective.coding",
        "Agentic coding: the session documents, terminals and prompt drafts. The perspective the tool starts in.",
        Landing: ZoneId.Left);

    public static Perspective Explore { get; } = new(
        "explore", "Explore", 2, PerspectiveBody.FullWindow, "perspective.explore",
        "Knowledge exploration: the full-window graph and reader. The other perspectives are retained, never rebuilt.");

    public static Perspective Architecture { get; } = new(
        "architecture", "Architecture", 3, PerspectiveBody.DockHost, "perspective.architecture",
        "Code and architecture understanding: the evidence, class, sequence, context and join views.",
        Landing: ZoneId.Center);

    /// <summary>
    /// Host C (Ruling 84; the operator's UC5 — observe the fleet): the Loomkeeper watcher's bench.
    /// A docking host like Coding and Architecture, never a full-window composite (ADR-0031's
    /// rejected alternative); the five Loomkeeper kinds are admitted here and nowhere else.
    /// </summary>
    public static Perspective Coordination { get; } = new(
        "coordination", "Coordination", 4, PerspectiveBody.DockHost, "perspective.coordination",
        "Fleet observation: the Loomkeeper watcher's terminal sessions, ledger, leaderboard, message board and daydreams. Read in parallel; no composer on this bench.",
        Landing: ZoneId.Left);

    /// <summary>The rows, in rail order: Coding · Explore · Architecture · Coordination.</summary>
    public static IReadOnlyList<Perspective> All { get; } = [Coding, Explore, Architecture, Coordination];

    /// <summary>The perspective the shell starts in (US-C1).</summary>
    public static Perspective Initial => Coding;

    /// <summary>
    /// Where a kind-open the active perspective does not admit is routed (US-C3): the first of these
    /// that admits the kind. Architecture before Coding because the requester is always a reading
    /// surface, so the reading host wins a shared kind — "View source" from Explore opens in
    /// Architecture, not Coding (<c>note-addendum-c-inadmissible-kind-routing</c>). Coordination
    /// last: it shares no kind with either (Ruling 84 re-homed the five as a set), so its position
    /// is unobservable until a kind is shared — appended, so the two existing positions are
    /// unchanged. It is a routing target so the drop report can name it and a Loomkeeper open from
    /// another host can land there.
    /// </summary>
    public static IReadOnlyList<Perspective> RoutingOrder { get; } = [Architecture, Coding, Coordination];

    /// <summary>The row whose command has this id, or null — the one lookup the controller needs.</summary>
    public static Perspective? ByCommandId(string commandId) =>
        All.FirstOrDefault(p => string.Equals(p.CommandId, commandId, StringComparison.Ordinal));
}
