namespace AiDe.Core.Workbench;

/// <summary>A rectangle in window coordinates. Deliberately not <c>System.Windows.Rect</c> — this
/// layer stays free of WPF so the drop logic is testable headlessly and survives a shell change.</summary>
public readonly record struct LayoutRect(double X, double Y, double Width, double Height)
{
    public double Right => X + Width;

    public double Bottom => Y + Height;

    public bool Contains(LayoutPoint p) => p.X >= X && p.X <= Right && p.Y >= Y && p.Y <= Bottom;
}

public readonly record struct LayoutPoint(double X, double Y);

/// <summary>A pane as the resolver sees it: its id, its bounds, and where its tab strip is.</summary>
public readonly record struct PaneHitBox(string StackId, LayoutRect Bounds, double TabStripHeight);

/// <summary>
/// Turns a pointer position into the <see cref="DropTarget"/> a drop would use.
/// </summary>
/// <remarks>
/// This is the other half of SC 2.5.7. The keyboard already produces a <see cref="DropTarget"/>;
/// this makes the pointer produce one too, so both paths converge on the same
/// <see cref="LayoutOperation"/> and the equivalence test compares two real paths rather than one
/// path against itself.
///
/// It is also what makes "show the destination before release" honest: the preview and the commit
/// call **this same function**, so they cannot disagree. A preview computed one way and a drop
/// applied another is the classic source of "it docked somewhere else than the highlight showed".
/// </remarks>
public static class DropTargetResolver
{
    /// <summary>Share of the pane's smaller dimension treated as an edge band.</summary>
    public const double EdgeFraction = 0.25;

    /// <summary>Upper bound on the edge band, so a huge pane does not get an absurd split zone.</summary>
    public const double MaxEdgeBand = 80;

    /// <summary>Lower bound, so a tiny pane still has a usable split zone.</summary>
    public const double MinEdgeBand = 16;

    /// <summary>
    /// Resolves the destination for a pointer at <paramref name="pointer"/>.
    /// </summary>
    /// <param name="panes">Candidate panes, in hit-test order (topmost first).</param>
    /// <param name="pointer">Pointer position in the same coordinate space as the pane bounds.</param>
    /// <param name="isLocked">When the layout is locked, no destination is offered at all.</param>
    /// <returns>
    /// The destination, or <see langword="null"/> when the layout is locked. A pointer outside every
    /// pane resolves to <see cref="DropKind.Float"/> — dragging a surface out of the window is how
    /// every exemplar creates a floating pane, so "no pane here" is a real destination, not a miss.
    /// </returns>
    public static DropTarget? Resolve(IReadOnlyList<PaneHitBox> panes, LayoutPoint pointer, bool isLocked = false)
    {
        if (isLocked)
        {
            return null;
        }

        foreach (var pane in panes)
        {
            if (!pane.Bounds.Contains(pointer))
            {
                continue;
            }

            // The tab strip means "join this stack, as a tab" — it is the one region where the
            // user's intent is unambiguous, so it wins before any edge-band arithmetic.
            if (pane.TabStripHeight > 0 && pointer.Y <= pane.Bounds.Y + pane.TabStripHeight)
            {
                return new DropTarget(pane.StackId, DropKind.JoinStack);
            }

            var band = EdgeBand(pane.Bounds);
            var fromLeft = pointer.X - pane.Bounds.X;
            var fromRight = pane.Bounds.Right - pointer.X;
            var fromTop = pointer.Y - pane.Bounds.Y;
            var fromBottom = pane.Bounds.Bottom - pointer.Y;
            var nearest = Math.Min(Math.Min(fromLeft, fromRight), Math.Min(fromTop, fromBottom));

            if (nearest > band)
            {
                return new DropTarget(pane.StackId, DropKind.JoinStack);
            }

            // Ties resolve in a fixed order so the same position always yields the same answer —
            // a resolver that flickers between two destinations at a corner is worse than one that
            // picks a slightly arbitrary side.
            if (nearest == fromLeft)
            {
                return new DropTarget(pane.StackId, DropKind.SplitLeft);
            }

            if (nearest == fromRight)
            {
                return new DropTarget(pane.StackId, DropKind.SplitRight);
            }

            return nearest == fromTop
                ? new DropTarget(pane.StackId, DropKind.SplitTop)
                : new DropTarget(pane.StackId, DropKind.SplitBottom);
        }

        return new DropTarget(string.Empty, DropKind.Float);
    }

    /// <summary>
    /// The rectangle to highlight for a destination — what the user sees before releasing.
    /// </summary>
    /// <remarks>
    /// Derived from the same target the drop will apply, so the highlight cannot promise one
    /// destination while the drop performs another.
    /// </remarks>
    public static LayoutRect PreviewFor(PaneHitBox pane, DropTarget target) => target.Kind switch
    {
        DropKind.SplitLeft => pane.Bounds with { Width = pane.Bounds.Width / 2 },
        DropKind.SplitRight => pane.Bounds with
        {
            X = pane.Bounds.X + (pane.Bounds.Width / 2),
            Width = pane.Bounds.Width / 2,
        },
        DropKind.SplitTop => pane.Bounds with { Height = pane.Bounds.Height / 2 },
        DropKind.SplitBottom => pane.Bounds with
        {
            Y = pane.Bounds.Y + (pane.Bounds.Height / 2),
            Height = pane.Bounds.Height / 2,
        },
        // Joining highlights the whole pane: the surface becomes one of its tabs, not a region of it.
        _ => pane.Bounds,
    };

    /// <summary>The text announced while a keyboard move hovers this destination.</summary>
    public static string Describe(DropTarget target, string paneTitle) => target.Kind switch
    {
        DropKind.SplitLeft => $"Destination: split, left of {paneTitle}.",
        DropKind.SplitRight => $"Destination: split, right of {paneTitle}.",
        DropKind.SplitTop => $"Destination: split, above {paneTitle}.",
        DropKind.SplitBottom => $"Destination: split, below {paneTitle}.",
        DropKind.JoinStack => $"Destination: join {paneTitle} as a tab.",
        _ => "Destination: float in a new window.",
    };

    internal static double EdgeBand(LayoutRect bounds) =>
        Math.Clamp(Math.Min(bounds.Width, bounds.Height) * EdgeFraction, MinEdgeBand, MaxEdgeBand);
}
