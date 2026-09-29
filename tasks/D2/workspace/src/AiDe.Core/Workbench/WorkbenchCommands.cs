using System.Globalization;
using AiDe.Core.Terminal;

namespace AiDe.Core.Workbench;

/// <summary>
/// Where a command is offered: the rule that decides, per perspective, whether the menu and the
/// palette list it (Addendum C §B3 rule 2; ADR-0030).
/// </summary>
/// <remarks>
/// <b>What the command NEEDS, never which perspectives list it.</b> A perspective list on a
/// command row would be a second home for a fact the perspective rows and the kind rows already
/// hold (ADR-0030, alternatives). What a row can honestly state is its precondition — a docking
/// host to operate on, a graph canvas to focus, a surface kind the perspective must admit — and
/// <c>PerspectiveMenu</c> evaluates that against the active perspective's body and allow-list.
/// Adding a perspective needs no edit here; adding a command states its precondition once.
/// </remarks>
/// <param name="Kind">The precondition's shape.</param>
/// <param name="SurfaceKind">For <see cref="CommandScopeKind.Admits"/>: the surface kind the active perspective must admit.</param>
public sealed record CommandScope(CommandScopeKind Kind, string? SurfaceKind = null)
{
    /// <summary>Offered in every perspective: entry verbs, workspace verbs, the perspective radio, the status line.</summary>
    public static CommandScope Global { get; } = new(CommandScopeKind.Global);

    /// <summary>Offered iff the active body is a docking host: every layout operation.</summary>
    public static CommandScope DockHost { get; } = new(CommandScopeKind.DockHost);

    /// <summary>Offered iff the active perspective admits <paramref name="surfaceKind"/> — the command acts on such a surface.</summary>
    public static CommandScope Admits(string surfaceKind) => new(CommandScopeKind.Admits, surfaceKind);
}

public enum CommandScopeKind
{
    Global,
    DockHost,
    Admits,
}

/// <summary>
/// One keyboard-reachable command, as the command palette lists it.
/// </summary>
/// <remarks>
/// This catalog is the machine-checkable form of SC 2.5.7: every operation reachable by dragging
/// must have a keyboard equivalent. Because both the palette and the conformance test read the same
/// list, an operation added without a command fails the suite instead of shipping mouse-only.
/// </remarks>
/// <param name="Gesture">
/// The announced gesture string — data the uniqueness collector reads (US-C10 b2). <b>Announced is
/// not bound:</b> only the single strokes <c>KeyGestures.For</c> yields are bound, and the menu and
/// the palette show a keystroke only when one is bound (PS-M4). A <c>Ctrl+K, X</c> chord stays here
/// for the day a chord handler exists and is shown nowhere until then.
/// </param>
/// <param name="Menu">
/// Which top-level menu this command belongs under, with its access key — one of the six names the
/// design language fixes (PS-M1: File · Edit · View · Window · Prompt · Help).
/// </param>
/// <param name="Scope">
/// The precondition under which a perspective offers this command (§B3 rule 2). No default: a
/// command whose scope was defaulted would be offered where it cannot work, which is the menu
/// teaching the operator to distrust it.
/// </param>
/// <remarks>
/// <b>Placement is a Core decision.</b> Adding a command and putting it in a menu is one atomic
/// change — the menu builder derives its grouping from <paramref name="Menu"/> and <paramref name="Scope"/>,
/// so there is no second list in the App to keep in step (Ruling 55b).
/// </remarks>
public sealed record WorkbenchCommand(
    string Id,
    string Title,
    string Gesture,
    string OperationKind,
    string Hint,
    string Menu,
    CommandScope Scope);

public static class WorkbenchCommandCatalog
{
    /// <summary>
    /// The commands, grouped by menu in menu order — which is the order the menu and the palette
    /// offer them. Gestures follow Windows/Fluent conventions and deliberately avoid the
    /// Alt+&lt;letter&gt; menu-mnemonic space.
    /// </summary>
    /// <remarks>
    /// <b>Not here: the "New/Show &lt;Title&gt;" openers for surface kinds.</b> Those are derived
    /// from the App's kind rows and their allow-lists (ADR-0030 rule 3) — a row per kind carrying
    /// both a Core command and an App kind would be two rows that must agree, which is the defect
    /// Ruling 22 removed for kinds. <c>terminal.new</c> and <c>session.new</c> stay: they are entry
    /// verbs (US-C11), offered in File in every perspective and routed to Coding.
    /// </remarks>
    public static IReadOnlyList<WorkbenchCommand> All { get; } =
    [
        // ── File: the entry verbs first, then the workspace verbs ─────────────────────────────

        // The front door (R13 b1). Ctrl+N rather than a Ctrl+K chord: this opens the product's
        // primary object and Addendum A names the gesture. A session cannot exist unbound, so with
        // no workspace open the chooser interposes before the sheet — that happens in the flow, not
        // in this row. Leads the File menu: a session is the object the product is about.
        new("session.new", "New session…", "Ctrl+N",
            string.Empty,
            "Opens the New Session sheet, pre-bound to the open workspace. With none open, the "
            + "workspace chooser comes first, and cancelling it creates nothing.",
            Menu: "_File", Scope: CommandScope.Global),

        // A plain shell terminal — the common case. Distinct from "New agent terminal" so a user who
        // wants a shell is not handed the first agent on PATH (and a tab mislabelled with its name).
        // An ENTRY VERB (US-C11): in File in every perspective, and the terminal kind's only opener —
        // the derived "New <Title>" rule skips the kind because this row is its door.
        new("terminal.new", "New terminal", "Ctrl+K, T",
            nameof(LayoutOperation.AddSurface),
            "Opens a plain shell terminal beside the others. Never launches an agent.",
            Menu: "_File", Scope: CommandScope.Global),

        // One command per launchable harness, DERIVED from the readiness profiles rather than listed
        // here. Adding a harness is then a profile, not an edit in three files — and there is no
        // second list to keep in step by memory, which is the failure this repository has hit
        // repeatedly. The menu derives from the same set, so catalog and menu cannot disagree about
        // which harnesses exist.
        //
        // This REPLACES `terminal.newAgent`, which opened whichever agent happened to be first on
        // PATH. That command could not say which harness it had started, and a session's harness
        // cannot be added afterwards: a second coordination register for a known session DISCARDS
        // its attributes rather than merging them (observed —
        // CoordinationContractTests.Apply_DuplicateRegister_DiscardsTheSecondAttributes_ItDoesNotMerge).
        // So the harness must be known at launch, which is exactly what choosing the entry supplies.
        ..AgentReadinessProfiles.BuiltIn.All
            .Where(profile => profile.Launchable)
            .OrderBy(profile => profile.DisplayName, StringComparer.Ordinal)
            .Select(profile => new WorkbenchCommand(
                profile.CommandId,
                $"New {profile.DisplayName} session",
                profile.Gesture!,
                // AddSurface's keyboard equivalent (SC 2.5.7). Declared rather than left empty: the
                // conformance test reflects over the operation union, and it caught this immediately.
                nameof(LayoutOperation.AddSurface),
                $"Opens a terminal running {profile.DisplayName}. Prompts can be dispatched to it once "
                + "it reaches its prompt, and the session registers with its harness named.",
                Menu: "_File", Scope: CommandScope.Global)),

        // Without this the daemon path was reachable only by setting an environment variable before
        // launch, which made indexing untestable by anyone who did not already know that.
        new("workspace.open", "Open a repository as a workspace…", "Ctrl+K, O",
            string.Empty,
            "Choose a folder. Its daemon is started if it is not already running, and its evidence becomes queryable.",
            Menu: "_File", Scope: CommandScope.Global),

        new("workspace.indexSolution", "Index C# projects in this workspace", "Ctrl+K, I",
            string.Empty,
            "Finds every C# project and indexes one scope per target framework. Reports what was not analysed.",
            Menu: "_File", Scope: CommandScope.Global),

        // Unchanged scopes are reused, which is almost always what the user wants and occasionally
        // is not. An operator must always be able to say "I do not believe the cache", and until
        // this existed that sentence had an API parameter behind it and no way to reach it.
        new("workspace.reindexAll", "Re-index everything (ignore the cache)", "Ctrl+K, Shift+I",
            string.Empty,
            "Re-reads every scope even when its files have not changed. Slower, and the answer when the graph disagrees with the code.",
            Menu: "_File", Scope: CommandScope.Global),

        // Not a layout command. Re-indexing is a WRITE that crosses the daemon boundary, and it
        // needs a keyboard-reachable trigger for the same reason every layout operation does: an
        // action available only by some other route is an action a keyboard-first operator does
        // not have.
        new("workspace.refresh", "Re-index this workspace", "Ctrl+K, Ctrl+I",
            OperationKind: "",   // ingestion, not a tree mutation
            "Asks the daemon to re-read the repository. The current evidence keeps rendering until "
            + "a complete snapshot replaces it.",
            Menu: "_File", Scope: CommandScope.Global),

        // ── Edit: operations on the focused pane (a host only) ────────────────────────────────

        new("workbench.moveSurface", "Move pane…", "Ctrl+K, M",
            nameof(LayoutOperation.MoveSurface),
            "Choose a destination with the arrow keys. Enter places it, Escape cancels.",
            Menu: "_Edit", Scope: CommandScope.DockHost),

        new("workbench.resizePane", "Resize pane…", "Ctrl+K, R",
            nameof(LayoutOperation.ResizeSplit),
            "Select an edge, then adjust it with the arrow keys. Enter commits, Escape cancels.",
            Menu: "_Edit", Scope: CommandScope.DockHost),

        // ── View: the perspective radio, then what the body offers ────────────────────────────

        // One command per perspective, DERIVED from the closed Perspective set (ADR-0030 rule 1), so
        // the catalog cannot list a perspective the set lacks. Each carries its bound single-stroke
        // gesture (US-C10; Ctrl+1/2/3 — D1's decision). The View menu renders these as a radio group
        // with the active one checked; the rail runs the same ids (AR5).
        //
        // This REPLACES `shell.toggleExplorer`: a toggle has no meaning over three destinations, and
        // activating the active perspective is a no-op (US-C1).
        ..PerspectiveSet.All.Select(perspective => new WorkbenchCommand(
            perspective.CommandId,
            $"{perspective.Title} perspective",
            perspective.Gesture,
            OperationKind: "",   // a shell view mode, not a tree mutation
            perspective.Description,
            Menu: "_View", Scope: CommandScope.Global)),

        new("workbench.nextSurface", "Next tab in pane", "Ctrl+PageDown",
            nameof(LayoutOperation.ActivateSurface),
            "Moves to the next surface in the focused pane.",
            Menu: "_View", Scope: CommandScope.DockHost),

        new("workbench.previousSurface", "Previous tab in pane", "Ctrl+PageUp",
            nameof(LayoutOperation.ActivateSurface),
            "Moves to the previous surface in the focused pane.",
            Menu: "_View", Scope: CommandScope.DockHost),

        new("workbench.reorderSurface", "Move tab left/right", "Ctrl+Shift+PageUp/PageDown",
            nameof(LayoutOperation.ReorderSurface),
            "Reorders the surface within its pane.",
            Menu: "_View", Scope: CommandScope.DockHost),

        // Not a layout operation, so it carries no OperationKind: SC 2.5.7's conformance test asks
        // that every DRAGGABLE operation has a keyboard path, and focusing the canvas is not one.
        // It is here because WPF traversal cannot reach the canvas at all (spike S4), so without an
        // explicit command the graph is unreachable from the keyboard entirely. Offered where a
        // DOCKED canvas can be — the seam it focuses is bound to the workbench's canvas surface, so
        // in Explore (whose graph has its own Tab cycle with the reader, DC-039) the row would
        // answer "not ready" and is absent (PS-M3).
        //
        // Ctrl+K, Shift+G: the unshifted G was announced for this AND for "New GitHub Copilot
        // session" (US-C10 b2's fourth collision); the harness row keeps its letter.
        new("workbench.focusCanvas", "Focus graph canvas", "Ctrl+K, Shift+G",
            string.Empty,
            "Moves focus into the graph. Tab off either end or press Escape to come back.",
            Menu: "_View", Scope: CommandScope.Admits("canvas")),

        // The operator's recourse against a score they disagree with (US rule 12). Append-only: it
        // records a dispute as evidence for review; it never changes the score. Keyboard-reachable for
        // the same reason every other write is - an action available only by some other route is one a
        // keyboard-first operator does not have. A Loomkeeper action: offered where the leaderboard is.
        new("watcher.raiseDispute", "Raise score dispute on the latest scored episode", "Ctrl+K, Ctrl+U",
            OperationKind: "",   // an append to the dispute log, not a tree mutation
            "Records an append-only operator dispute against the most recently scored episode. The score "
            + "is never changed - the dispute is evidence for later review.",
            Menu: "_View", Scope: CommandScope.Admits("leaderboard")),

        // A status message has no natural end, and the longest one is usually the last one. This is
        // how a reader puts it away; what it said is still in the diagnostics.
        new("workbench.clearStatus", "Clear the status message", "Ctrl+K, Ctrl+C",
            nameof(LayoutOperation.ResetToDefault),
            "Empties the status line. What it said is still available under Diagnostics.",
            Menu: "_View", Scope: CommandScope.Global),

        // The registry leg of DC-068's seam request (DS-1 P4, SC8): the session document's own
        // header → thread → composer → split cycle, reachable from the palette and the menu, not
        // only from F6 landing inside the document itself — which stays the fallback so a document
        // with no capture surface still has the key (DC-072). Not a layout operation, so it carries
        // no OperationKind: nothing here mutates the zone tree.
        new("session.cycleRegion", "Cycle session region", "F6",
            string.Empty,
            "Moves focus to the open session's next region: header, thread, composer, then the Console when it is open.",
            Menu: "_View", Scope: CommandScope.Admits("session-document")),

        new("session.cycleRegionBack", "Cycle session region backward", "Shift+F6",
            string.Empty,
            "Moves focus to the open session's previous region.",
            Menu: "_View", Scope: CommandScope.Admits("session-document")),

        // The session's Console as a document (Ruling 89): the `console` kind's only door — the
        // session header's toggle, this row in View and the palette all run it. Offered where a
        // session document can be, since it needs one focused. A second run focuses the one open
        // console; the tab's close is the way back. A layout operation (it adds a surface).
        new("session.console", "Session console", "Ctrl+K, Ctrl+L",
            nameof(LayoutOperation.AddSurface),
            "Opens the focused session's Console — every wire frame, one row per message — as a "
            + "document in the Center zone, or focuses it when it is already open.",
            Menu: "_View", Scope: CommandScope.Admits("session-document")),

        // ── Window: the arrangement (a host only) ─────────────────────────────────────────────

        new("workbench.floatPane", "Float pane", "Ctrl+K, F",
            nameof(LayoutOperation.SetStackState),
            "Detaches the pane into its own window.",
            Menu: "_Window", Scope: CommandScope.DockHost),

        new("workbench.collapsePane", "Collapse pane", "Ctrl+K, C",
            nameof(LayoutOperation.SetStackState),
            "Hides the pane; its surfaces stay reachable by name.",
            Menu: "_Window", Scope: CommandScope.DockHost),

        new("workbench.maximizePane", "Maximize pane", "Ctrl+K, Z",
            nameof(LayoutOperation.SetStackState),
            "Restoring returns the previous arrangement.",
            Menu: "_Window", Scope: CommandScope.DockHost),

        new("workbench.closeSurface", "Close surface", "Ctrl+W",
            nameof(LayoutOperation.CloseSurface),
            "Closes the focused surface.",
            Menu: "_Window", Scope: CommandScope.DockHost),

        new("workbench.toggleLock", "Lock/unlock layout", "Ctrl+K, L",
            OperationKind: "",   // a mode, not a tree mutation
            "Freezes the arrangement so a stray drag cannot change it.",
            Menu: "_Window", Scope: CommandScope.DockHost),

        new("workbench.resetLayout", "Reset workbench layout", "Ctrl+K, Ctrl+R",
            nameof(LayoutOperation.ResetToDefault),
            "Returns to the default arrangement.",
            Menu: "_Window", Scope: CommandScope.DockHost),

        // ── Prompt: dispatching to a terminal (where a terminal can be) ───────────────────────

        // The receipt, not the send, is what this command exists to surface — a prompt reaching an
        // agent session cannot be taken back. Offered where a terminal is admitted; the "New Prompt
        // draft" entry beside it is derived from the prompt kind's row.
        new("workbench.dispatchPrompt", "Dispatch prompt to terminal…", "Ctrl+K, P",
            string.Empty,
            "Type a prompt and press Enter. The recorded delivery receipt is announced, including when delivery is unknown.",
            Menu: "_Prompt", Scope: CommandScope.Admits("terminal")),

        // ── Help ──────────────────────────────────────────────────────────────────────────────

        // Read-only on purpose. Upgrade and rollback are choreographed against a store a running
        // binary may not be able to read halfway through, so the shell REPORTS the state and names
        // what a rollback would do; the act itself stays with the Bootstrap. Captioned "Diagnostics
        // report" so it does not collide with the diagnostics SURFACE's "Show Diagnostics" (§B3 rule 1).
        new("workspace.diagnostics", "Diagnostics report", "Ctrl+K, D",
            string.Empty,
            "Reports the daemon version, whether a rollback is possible, open health incidents, and the registered MCP tools.",
            Menu: "_Help", Scope: CommandScope.Global),
    ];

    /// <summary>The rows of <paramref name="commands"/> whose title or hint contains <paramref name="term"/>; all of them for a blank term.</summary>
    public static IEnumerable<WorkbenchCommand> Search(IEnumerable<WorkbenchCommand> commands, string term) =>
        string.IsNullOrWhiteSpace(term)
            ? commands
            : commands.Where(c =>
                c.Title.Contains(term, StringComparison.OrdinalIgnoreCase)
                || c.Hint.Contains(term, StringComparison.OrdinalIgnoreCase));
}

/// <summary>
/// The keyboard resize interaction, modelled after Eclipse's `Alt+-` → Size → arrows — the only
/// keyboard resize proven in any of the four exemplars.
/// </summary>
/// <remarks>
/// It is a small explicit state machine rather than a stream of resize operations because the user
/// must be able to **see which edge is selected** before moving it, and to **cancel back to where
/// they started**. Adjustments are applied live so the effect is visible, and Cancel restores the
/// layout captured on entry.
/// </remarks>
public sealed class KeyboardResizeSession(ILayoutService service)
{
    private Layout? _entryLayout;

    public bool IsActive { get; private set; }

    public string? SplitId { get; private set; }

    public int EdgeIndex { get; private set; }

    /// <summary>The step per arrow press, as a share of the split. Matches the mockup's declared increments.</summary>
    public double Step { get; init; } = 0.02;

    /// <summary>Enters resize mode on an edge and announces which edge is selected.</summary>
    public string Begin(string splitId, int edgeIndex, string edgeLabel)
    {
        _entryLayout = service.Current;
        IsActive = true;
        SplitId = splitId;
        EdgeIndex = edgeIndex;
        return $"Resize: {edgeLabel}. Arrow keys adjust. Enter commits, Escape cancels.";
    }

    /// <summary>Applies one arrow press. A refusal (minimum size) keeps the session open.</summary>
    public LayoutResult Adjust(int direction)
    {
        if (!IsActive || SplitId is null)
        {
            return new LayoutResult(service.Current, false, LayoutErrorCodes.InvalidTarget,
                "Not resizing.");
        }

        return service.Apply(new LayoutOperation.ResizeSplit(SplitId, EdgeIndex, Step * direction));
    }

    public string Commit()
    {
        IsActive = false;
        _entryLayout = null;
        SplitId = null;
        return "Resize committed.";
    }

    /// <summary>Abandons the resize and puts the layout back exactly as it was on entry.</summary>
    public string Cancel()
    {
        if (_entryLayout is not null)
        {
            service.Restore(_entryLayout);
        }

        IsActive = false;
        _entryLayout = null;
        SplitId = null;
        return "Resize cancelled.";
    }

    public string Describe() => IsActive
        ? string.Create(CultureInfo.InvariantCulture, $"Resizing edge {EdgeIndex + 1} of {SplitId}")
        : "Not resizing.";
}
