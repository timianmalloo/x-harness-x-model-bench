using AiDe.Core.Workbench;

namespace AiDe.Core.Tests;

/// <summary>
/// <c>P2-FOCUS-01</c>, <c>-02</c> and <c>-04</c> — the host half of the canvas focus contract.
/// </summary>
/// <remarks>
/// <para><b>What these prove and what they do not.</b> The canvas is the one surface WPF's focus
/// system cannot reach, and the contract has two halves: the host's policy (when may focus enter,
/// what is recorded, what is announced on refusal) and the page's boundary handlers (trapping Tab at
/// each end and posting <c>focus.leave</c>). These tests prove the <b>host</b> half against the
/// <see cref="ICanvasFocusTarget"/> seam.</para>
///
/// <para><b><c>P2-FOCUS-03</c> is not here and is still owed.</b> The keyboard-trap test needs a real
/// window, a real WebView2 runtime and the canvas page's own handlers — none of which exist yet, as
/// the graph canvas surface is unbuilt. It is recorded as owed rather than approximated here,
/// because a keyboard-trap test that runs against a fake cannot fail for the reason it exists
/// (<b>DC-016</b>: a control that cannot fire in the environment that verifies it).</para>
/// </remarks>
public sealed class CanvasFocusRouterTests
{
    private sealed class FakeCanvas : ICanvasFocusTarget
    {
        public bool IsReady { get; set; } = true;
        public bool IsObscured { get; set; }

        /// <summary>Whether the read-back would report focus actually landed.</summary>
        public bool FocusLands { get; set; } = true;

        public int FocusAttempts { get; private set; }

        public bool TryFocus()
        {
            FocusAttempts++;
            return FocusLands;
        }
    }

    private sealed class FakeHost : IHostFocusScope
    {
        public object? Current { get; set; } = "search-box";
        public object? Restored { get; private set; }
        public CanvasFocusDirection? Moved { get; private set; }

        /// <summary>Set when the pre-entry element no longer accepts focus (its pane was closed).</summary>
        public bool RestoreFails { get; set; }

        public bool MoveSucceeds { get; set; } = true;

        public bool Restore(object target)
        {
            if (RestoreFails) return false;
            Restored = target;
            Current = target;
            return true;
        }

        public bool MoveNext(CanvasFocusDirection direction)
        {
            if (!MoveSucceeds) return false;
            Moved = direction;
            return true;
        }
    }

    private static (CanvasFocusRouter Router, FakeCanvas Canvas, FakeHost Host) Build()
    {
        var canvas = new FakeCanvas();
        var host = new FakeHost();
        return (new CanvasFocusRouter(canvas, host), canvas, host);
    }

    // ---- P2-FOCUS-01 --------------------------------------------------------

    [Fact]
    public void FocusCanvas_EntersOnlyWhenTheReadBackConfirmsItLanded()
    {
        var (router, canvas, _) = Build();

        var result = router.Enter();

        Assert.Equal(CanvasFocusOutcome.Entered, result.Outcome);
        Assert.True(router.IsInsideCanvas);
        Assert.Equal(1, canvas.FocusAttempts);
    }

    [Fact]
    public void FocusCanvas_RefusesWhenSetFocusDidNotLand()
    {
        // The case SetFocus's own return value cannot distinguish: it hands back the PREVIOUSLY
        // focused window, and null is ambiguous between "failed" and "nothing had focus". Only the
        // GetFocus read-back separates them, so the router must believe the read-back and not the call.
        var (router, canvas, _) = Build();
        canvas.FocusLands = false;

        var result = router.Enter();

        Assert.Equal(CanvasFocusOutcome.Refused, result.Outcome);
        Assert.False(router.IsInsideCanvas);
        Assert.Equal("The graph canvas is not ready.", result.Announcement);
    }

    [Fact]
    public void FocusCanvas_RefusesAndAnnouncesWhenTheCanvasHasNoHandleYet()
    {
        var (router, canvas, _) = Build();
        canvas.IsReady = false;

        var result = router.Enter();

        Assert.Equal(CanvasFocusOutcome.Refused, result.Outcome);
        Assert.Equal(0, canvas.FocusAttempts);
        Assert.NotEmpty(result.Announcement);
    }

    // ---- P2-FOCUS-02 --------------------------------------------------------

    [Fact]
    public void PreEntryFocusIsRecorded_AndEscapeReturnsToExactlyThatElement()
    {
        var (router, _, host) = Build();
        host.Current = "provenance-list";

        router.Enter();
        Assert.Equal("provenance-list", router.PreEntryFocus);

        var result = router.Leave(CanvasFocusDirection.Restore);

        Assert.Equal(CanvasFocusOutcome.Restored, result.Outcome);
        Assert.Equal("provenance-list", host.Restored);
        Assert.False(router.IsInsideCanvas);
    }

    [Fact]
    public void EscapeFallsForward_WhenThePreEntryElementIsGone()
    {
        // A pane closed while the canvas held focus. Leaving focus nowhere is the one outcome that
        // must not happen, so falling forward beats refusing.
        var (router, _, host) = Build();
        router.Enter();
        host.RestoreFails = true;

        var result = router.Leave(CanvasFocusDirection.Restore);

        Assert.Equal(CanvasFocusOutcome.Moved, result.Outcome);
        Assert.Equal(CanvasFocusDirection.Forward, host.Moved);
        Assert.False(router.IsInsideCanvas);
    }

    [Fact]
    public void PreEntryFocusIsNotRetained_AfterItHasBeenUsed()
    {
        // Otherwise a second Esc, from a later entry that recorded nothing, would send focus to a
        // stale element the user has since navigated away from.
        var (router, _, host) = Build();
        host.Current = "first";
        router.Enter();
        router.Leave(CanvasFocusDirection.Restore);

        Assert.Null(router.PreEntryFocus);
    }

    [Theory]
    [InlineData(CanvasFocusDirection.Forward)]
    [InlineData(CanvasFocusDirection.Backward)]
    public void LeavingByTab_MovesHostFocusInTheSameDirection(CanvasFocusDirection direction)
    {
        var (router, _, host) = Build();
        router.Enter();

        var result = router.Leave(direction);

        Assert.Equal(CanvasFocusOutcome.Moved, result.Outcome);
        Assert.Equal(direction, host.Moved);
    }

    [Fact]
    public void LeaveIsIgnored_WhenFocusWasNeverInTheCanvas()
    {
        var (router, _, host) = Build();

        var result = router.Leave(CanvasFocusDirection.Forward);

        Assert.Equal(CanvasFocusOutcome.Refused, result.Outcome);
        Assert.Null(host.Moved);
    }

    // ---- P2-FOCUS-04 --------------------------------------------------------

    [Fact]
    public void FocusCanvas_IsRefusedAndAnnouncedWhileTheSnapshotSwapIsShowing()
    {
        var (router, canvas, _) = Build();
        canvas.IsObscured = true;

        var result = router.Enter();

        Assert.Equal(CanvasFocusOutcome.Refused, result.Outcome);
        Assert.False(router.IsInsideCanvas);

        // Never silently ignored (DC-011): a focus command that does nothing is indistinguishable
        // from a broken key.
        Assert.NotEmpty(result.Announcement);

        // And it must not be attempted — the canvas is hidden behind a still frame.
        Assert.Equal(0, canvas.FocusAttempts);
    }

    [Fact]
    public void TheObscuredRefusal_SaysWhy_RatherThanReportingNotReady()
    {
        // Both refusals are announced, but they are different situations and the generic one is
        // useless mid-drag. Asserting they DIFFER is what stops the specific message rotting away
        // into the general one.
        var (obscuredRouter, obscuredCanvas, _) = Build();
        obscuredCanvas.IsObscured = true;

        var (notReadyRouter, notReadyCanvas, _) = Build();
        notReadyCanvas.IsReady = false;

        var obscured = obscuredRouter.Enter().Announcement;
        var notReady = notReadyRouter.Enter().Announcement;

        Assert.NotEqual(obscured, notReady);
    }

    [Fact]
    public void ObscuredIsCheckedBeforeReady_SoADragNeverReportsNotReady()
    {
        var (router, canvas, _) = Build();
        canvas.IsObscured = true;
        canvas.IsReady = false;

        var result = router.Enter();

        Assert.DoesNotContain("not ready", result.Announcement, StringComparison.OrdinalIgnoreCase);
    }
}
