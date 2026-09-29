namespace AiDe.Core.Workbench;

/// <summary>Why a focus transition ended the way it did.</summary>
public enum CanvasFocusOutcome
{
    /// <summary>Focus is now inside the canvas.</summary>
    Entered,

    /// <summary>Focus returned to the element that held it before entry.</summary>
    Restored,

    /// <summary>Focus left the canvas in a direction, for WPF traversal to continue.</summary>
    Moved,

    /// <summary>The transition did not happen, and the user was told why.</summary>
    Refused,
}

/// <summary>Which way focus left the canvas.</summary>
public enum CanvasFocusDirection
{
    /// <summary>Tab off the last focusable element.</summary>
    Forward,

    /// <summary>Shift+Tab off the first focusable element.</summary>
    Backward,

    /// <summary>Esc — return to whatever held focus before entry.</summary>
    Restore,
}

/// <summary>The result of one focus transition, including the text the user hears on a refusal.</summary>
public sealed record CanvasFocusResult(CanvasFocusOutcome Outcome, string Announcement)
{
    public bool Succeeded => Outcome != CanvasFocusOutcome.Refused;
}

/// <summary>
/// The canvas, as the focus router needs to see it. Implemented over the WPF <c>HwndHost</c>.
/// </summary>
/// <remarks>
/// This is a seam rather than a direct dependency because the mechanism is Win32 and the policy is
/// not: what should happen when the canvas is not ready, or is hidden behind the snapshot swap, is
/// decidable without a window — and a rule that can only be tested with a real WebView2 running is a
/// rule that stops being tested.
/// </remarks>
public interface ICanvasFocusTarget
{
    /// <summary>Whether the canvas has a created window handle yet.</summary>
    bool IsReady { get; }

    /// <summary>
    /// Whether the snapshot swap is currently showing a still frame in place of the live canvas
    /// (ADR-0015). While it is, the canvas is hidden and cannot take focus.
    /// </summary>
    bool IsObscured { get; }

    /// <summary>
    /// Calls <c>SetFocus</c> on the canvas handle and <b>reads back <c>GetFocus</c></b>, returning
    /// whether focus actually landed on the handle or a descendant.
    /// </summary>
    /// <remarks>
    /// The read-back is the whole point. <c>SetFocus</c> returns the <i>previously</i> focused
    /// window, whose null case is ambiguous between "failed" and "nothing had focus" — so its return
    /// value cannot distinguish success from failure (spike S4).
    /// </remarks>
    bool TryFocus();
}

/// <summary>The host's WPF focus, as the router needs to see it.</summary>
public interface IHostFocusScope
{
    /// <summary>An opaque token for whatever currently holds WPF focus, or null if nothing does.</summary>
    object? Current { get; }

    /// <summary>Puts WPF focus back on <paramref name="target"/>. False when it no longer accepts focus.</summary>
    bool Restore(object target);

    /// <summary>Moves WPF focus past the canvas in <paramref name="direction"/>.</summary>
    bool MoveNext(CanvasFocusDirection direction);
}

/// <summary>
/// Routes focus across the canvas boundary in <b>both</b> directions, explicitly.
/// </summary>
/// <remarks>
/// <para>Neither crossing happens by WPF traversal, because traversal does not work here: spike S4
/// measured <c>Focus()</c> refused and Tab never landing on the canvas in <i>both</i> hosting modes,
/// so this is a property of hosting a browser rather than of the mode ADR-0015 chose.</para>
///
/// <para><b>Every refusal is announced.</b> A focus command that silently does nothing is
/// indistinguishable from a broken key (defect class <b>DC-011</b>), and this command has two
/// ordinary reasons to refuse — a canvas that has not been created yet, and one hidden behind the
/// snapshot swap.</para>
/// </remarks>
public sealed class CanvasFocusRouter(ICanvasFocusTarget canvas, IHostFocusScope host)
{
    private readonly ICanvasFocusTarget _canvas = canvas ?? throw new ArgumentNullException(nameof(canvas));
    private readonly IHostFocusScope _host = host ?? throw new ArgumentNullException(nameof(host));

    /// <summary>
    /// What held WPF focus immediately before entry, so <c>Esc</c> has somewhere to return to.
    /// Without this, leaving the canvas dumps the user at the start of the tab order.
    /// </summary>
    private object? _preEntryFocus;

    /// <summary>Whether focus is currently believed to be inside the canvas.</summary>
    public bool IsInsideCanvas { get; private set; }

    /// <summary>The pre-entry focus target, exposed so a test can assert it was recorded.</summary>
    public object? PreEntryFocus => _preEntryFocus;

    /// <summary>`workbench.focusCanvas` — WPF to canvas.</summary>
    public CanvasFocusResult Enter()
    {
        // Order matters: obscured is checked BEFORE ready, because the snapshot swap is a normal
        // transient state with a specific explanation, while "not ready" is the generic one. Telling
        // a user mid-drag that the canvas "is not ready" would be true and useless.
        if (_canvas.IsObscured)
        {
            return new CanvasFocusResult(
                CanvasFocusOutcome.Refused,
                "The graph canvas cannot take focus while the layout is being dragged.");
        }

        if (!_canvas.IsReady)
        {
            return new CanvasFocusResult(
                CanvasFocusOutcome.Refused,
                "The graph canvas is not ready.");
        }

        // Recorded BEFORE the transition: once focus has moved, what held it is gone.
        var previous = _host.Current;

        if (!_canvas.TryFocus())
        {
            return new CanvasFocusResult(
                CanvasFocusOutcome.Refused,
                "The graph canvas is not ready.");
        }

        _preEntryFocus = previous;
        IsInsideCanvas = true;
        return new CanvasFocusResult(CanvasFocusOutcome.Entered, "Graph canvas focused.");
    }

    /// <summary>
    /// A <c>focus.leave</c> message from the canvas page — canvas to WPF.
    /// </summary>
    /// <remarks>
    /// The page traps Tab on its last focusable element and Shift+Tab on its first, and posts here.
    /// <b>These handlers are the only way out</b>, so a page that forgets them is a keyboard trap —
    /// which is why this is a contract on the page and not a nicety.
    /// <para>Acting on this message moves focus and grants nothing, so a message forged by page
    /// content rather than the boundary handler has no privileged effect.</para>
    /// </remarks>
    public CanvasFocusResult Leave(CanvasFocusDirection direction)
    {
        if (!IsInsideCanvas)
        {
            // Not an error: the page can post this after focus has already moved for another reason.
            return new CanvasFocusResult(CanvasFocusOutcome.Refused, "Focus is not in the graph canvas.");
        }

        if (direction == CanvasFocusDirection.Restore)
        {
            IsInsideCanvas = false;
            if (_preEntryFocus is not null && _host.Restore(_preEntryFocus))
            {
                var restored = _preEntryFocus;
                _preEntryFocus = null;
                return new CanvasFocusResult(CanvasFocusOutcome.Restored, "Focus returned from the graph canvas.");
            }

            // The pre-entry element is gone — a pane it lived in was closed while the canvas held
            // focus. Falling forward is better than leaving focus nowhere.
            _preEntryFocus = null;
            return _host.MoveNext(CanvasFocusDirection.Forward)
                ? new CanvasFocusResult(CanvasFocusOutcome.Moved, "Focus left the graph canvas.")
                : new CanvasFocusResult(CanvasFocusOutcome.Refused, "Focus could not leave the graph canvas.");
        }

        IsInsideCanvas = false;
        _preEntryFocus = null;
        return _host.MoveNext(direction)
            ? new CanvasFocusResult(CanvasFocusOutcome.Moved, "Focus left the graph canvas.")
            : new CanvasFocusResult(CanvasFocusOutcome.Refused, "Focus could not leave the graph canvas.");
    }
}
