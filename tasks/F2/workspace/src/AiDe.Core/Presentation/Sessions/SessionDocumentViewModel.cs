using AiDe.Core.AgentPlane;

namespace AiDe.Core.Presentation.Sessions;

/// <summary>
/// One session document's state, with no view attached: which canvas mode is active, whether the
/// canvas is split, where the two splitters sit, the merged stream, and the permission surface.
/// </summary>
/// <remarks>
/// <para><b>Console is the default on session open (R16 b1).</b> The default is the catalog's first
/// row rather than a constant repeated here — two definitions of "which mode opens" is the defect
/// signature DM7 names, and the failure it produces is invisible: the document opens on Terminal
/// and everything still renders.</para>
///
/// <para><b>Dispatch is the event cycle.</b> One call is one event: the count rises, the row lands
/// in the stream, and a <c>permission.request</c> raises the permission surface — all before the
/// caller can dequeue the next event. That ordering is what R16 b3 asserts, on the recorded
/// ordinals rather than on a clock (DC-107).</para>
/// </remarks>
public sealed class SessionDocumentViewModel
{
    /// <summary>The run-event kind a lane asks for permission with — <c>AcpRunEventMapper</c>'s row.</summary>
    public const string PermissionRequestKind = "permission.request";

    private readonly List<string> _availableModes;

    /// <summary>Serialises one event cycle — see <see cref="Dispatch"/>.</summary>
    private readonly Lock _dispatchGate = new();

    /// <param name="sessionId">The session this document renders.</param>
    /// <param name="title">Its display name.</param>
    /// <param name="workspaceRoot">The workspace it is bound to. A session cannot exist unbound (R13).</param>
    /// <param name="preset">The paired-zone preset it opens in.</param>
    /// <param name="availableModes">
    /// The canvas mode ids on offer, <b>in catalog order</b>: the first is the mode a session opens
    /// on, which R16 b1 requires to be Console.
    /// </param>
    /// <remarks>
    /// <b><paramref name="availableModes"/> is required, and that is what keeps this type in
    /// Presentation.</b> It used to default from <c>CanvasModeCatalog</c>, whose rows carry a
    /// <c>Func&lt;…, FrameworkElement&gt;</c> — a WPF type — so the default was the one line binding
    /// a view model to a view. The App passes the catalog's ids; nothing here knows what a mode
    /// renders.
    /// </remarks>
    public SessionDocumentViewModel(
        string sessionId,
        string title,
        string workspaceRoot,
        IReadOnlyList<string> availableModes,
        SessionZonePreset? preset = null)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(sessionId);
        ArgumentException.ThrowIfNullOrWhiteSpace(workspaceRoot);
        ArgumentNullException.ThrowIfNull(availableModes);

        SessionId = sessionId;
        Title = string.IsNullOrWhiteSpace(title) ? sessionId : title;
        WorkspaceRoot = workspaceRoot;
        Preset = preset ?? SessionZonePreset.PairedZone;

        _availableModes = [.. availableModes];

        if (_availableModes.Count == 0)
        {
            throw new ArgumentException(
                "a session document with no canvas mode has nothing to render; Console and Terminal "
                + "are the Phase-1 rows",
                nameof(availableModes));
        }

        ActiveModeId = _availableModes[0];
        CanvasSplitWeight = 0.5;
    }

    /// <summary>The session's id.</summary>
    public string SessionId { get; }

    /// <summary>Its display name.</summary>
    public string Title { get; }

    /// <summary>The workspace this session is bound to.</summary>
    public string WorkspaceRoot { get; }

    /// <summary>The paired-zone preset, carrying the composer/canvas splitter position.</summary>
    public SessionZonePreset Preset { get; private set; }

    /// <summary>The canvas modes on offer, in catalog order.</summary>
    public IReadOnlyList<string> AvailableModes => _availableModes;

    /// <summary>The mode showing in the primary half of the canvas.</summary>
    public string ActiveModeId { get; private set; }

    /// <summary>The mode showing beside it, or null when the canvas is not split.</summary>
    public string? SplitModeId { get; private set; }

    /// <summary>Whether the canvas shows two modes side by side (R16 b2, Ruling 21).</summary>
    public bool IsSplit => SplitModeId is not null;

    /// <summary>The primary mode's share of the canvas split.</summary>
    public double CanvasSplitWeight { get; private set; }

    /// <summary>
    /// Whether the composer's compiled-prompt disclosure is open — the document's state, not one
    /// composer instance's (Ruling 96): collapsed at rest (Ruling 57), and once the operator opens
    /// it, open for this document across turns and a reopen.
    /// </summary>
    public bool CompiledPromptOpen { get; private set; }

    /// <summary>The merged stream every lane of this session writes into.</summary>
    public ConsoleStreamModel Console { get; } = new();

    /// <summary>Where a lane's permission request becomes visible.</summary>
    public SessionPermissionSurface Permission { get; } = new();

    /// <summary>How many events this document has dispatched. The ordinal R16 b3 is asserted on.</summary>
    public long Dispatched { get; private set; }

    /// <summary>Raised after the mode, split or splitter position changes.</summary>
    public event Action? LayoutChanged;

    /// <summary>Makes <paramref name="modeId"/> the primary mode. A mode not on offer is refused.</summary>
    public void SetActiveMode(string modeId)
    {
        RefuseUnknownMode(modeId);

        if (string.Equals(modeId, ActiveModeId, StringComparison.Ordinal))
        {
            return;
        }

        // Swapping into the half the split already holds keeps both halves live rather than
        // dropping one: a mode switch on a split canvas is a swap, not a collapse.
        if (string.Equals(modeId, SplitModeId, StringComparison.Ordinal))
        {
            SplitModeId = ActiveModeId;
        }

        ActiveModeId = modeId;
        LayoutChanged?.Invoke();
    }

    /// <summary>Splits the canvas so <paramref name="modeId"/> renders beside the active mode.</summary>
    public void Split(string modeId)
    {
        RefuseUnknownMode(modeId);

        if (string.Equals(modeId, ActiveModeId, StringComparison.Ordinal))
        {
            throw new ArgumentException(
                "a canvas cannot be split against the mode already active — the second half would "
                + "render the same content twice and read as two lanes",
                nameof(modeId));
        }

        SplitModeId = modeId;
        LayoutChanged?.Invoke();
    }

    /// <summary>Closes the split, leaving the active mode alone in the canvas.</summary>
    public void Unsplit()
    {
        if (SplitModeId is null)
        {
            return;
        }

        SplitModeId = null;
        LayoutChanged?.Invoke();
    }

    /// <summary>Moves the canvas splitter. Clamped so neither half can vanish.</summary>
    public void SetCanvasSplitWeight(double weight)
    {
        CanvasSplitWeight = Math.Clamp(
            weight, SessionZonePreset.MinimumWeight, 1.0 - SessionZonePreset.MinimumWeight);
        LayoutChanged?.Invoke();
    }

    /// <summary>Moves the composer/canvas splitter. Clamped the same way.</summary>
    public void SetComposerWeight(double weight)
    {
        Preset = Preset.WithComposerWeight(weight);
        LayoutChanged?.Invoke();
    }

    /// <summary>Records the compiled-prompt disclosure's state (Ruling 96) — the surface calls this on the operator's toggle, and reads it when it binds a composer.</summary>
    public void SetCompiledPromptOpen(bool open) => CompiledPromptOpen = open;

    /// <summary>
    /// Dispatches one lane event: it lands in the merged stream, and a permission request surfaces
    /// before the caller can dequeue the next one.
    /// </summary>
    /// <param name="laneId">The lane that produced it.</param>
    /// <param name="laneName">That lane's display name, for the rail.</param>
    /// <param name="evt">The normalized event.</param>
    public void Dispatch(string laneId, string laneName, RunEvent evt)
    {
        ArgumentNullException.ThrowIfNull(evt);

        // One lock around the whole cycle, because more than one lane dispatches into one document
        // and each drains on its own thread. Without it the count and the permission ordinal are
        // read and written by two threads at once, and R16 b3's claim — "raised at THIS dispatch
        // count" — would be a race rather than an assertion.
        lock (_dispatchGate)
        {
            Dispatched++;
            Console.Append(laneId, laneName, evt);

        // REGARDLESS OF THE ACTIVE MODE (R16 b3), and this line is the whole clause.
        //
        // Written red-first against a version that raised only while Console was active: the Console
        // case passed and the Terminal case failed with "no permission surfaced in terminal mode".
        // That is the real defect shape — the overlay appearing when you happen to switch back — and
        // it is invisible to anyone testing in the default mode.
            if (string.Equals(evt.Kind, PermissionRequestKind, StringComparison.Ordinal))
            {
                Permission.Raise(evt, Dispatched);
            }
        }
    }

    /// <summary>This document's restorable state.</summary>
    public SessionDocumentEnvelope Envelope() => new(
        SessionDocumentStore.CurrentSchemaVersion,
        ActiveModeId,
        SplitModeId,
        CanvasSplitWeight,
        Preset.ComposerWeight,
        CompiledPromptOpen);

    /// <summary>
    /// Restores a saved envelope. A mode the build no longer offers is dropped rather than
    /// resurrected, exactly as <c>ZoneLayoutStore</c> drops a surface kind the app cannot provide.
    /// </summary>
    public void Restore(SessionDocumentEnvelope envelope)
    {
        ArgumentNullException.ThrowIfNull(envelope);

        if (_availableModes.Contains(envelope.ActiveModeId, StringComparer.Ordinal))
        {
            ActiveModeId = envelope.ActiveModeId;
        }

        SplitModeId = envelope.SplitModeId is { } split
            && _availableModes.Contains(split, StringComparer.Ordinal)
            && !string.Equals(split, ActiveModeId, StringComparison.Ordinal)
                ? split
                : null;

        CanvasSplitWeight = Math.Clamp(
            envelope.CanvasSplitWeight, SessionZonePreset.MinimumWeight, 1.0 - SessionZonePreset.MinimumWeight);
        Preset = Preset.WithComposerWeight(envelope.ComposerWeight);
        CompiledPromptOpen = envelope.CompiledPromptOpen;
        LayoutChanged?.Invoke();
    }

    private void RefuseUnknownMode(string modeId)
    {
        if (!_availableModes.Contains(modeId, StringComparer.Ordinal))
        {
            throw new ArgumentException(
                $"'{modeId}' is not a canvas mode this document offers; on offer: "
                + string.Join(", ", _availableModes),
                nameof(modeId));
        }
    }
}
