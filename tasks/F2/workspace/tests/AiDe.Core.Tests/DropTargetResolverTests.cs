using AiDe.Core.Workbench;

namespace AiDe.Core.Tests;

/// <summary>
/// The pointer half of SC 2.5.7. Until this existed, the equivalence test compared the keyboard path
/// against itself; now it compares two genuinely different input paths that converge on the same
/// <see cref="LayoutOperation"/>.
/// </summary>
public sealed class DropTargetResolverTests
{
    // A 400x300 pane at the origin with a 28px tab strip. Edge band = min(400,300)*0.25 = 75.
    private static readonly PaneHitBox Pane = new("stack-a", new LayoutRect(0, 0, 400, 300), 28);
    private static readonly IReadOnlyList<PaneHitBox> Panes = [Pane];

    private static DropTarget Resolve(double x, double y) =>
        DropTargetResolver.Resolve(Panes, new LayoutPoint(x, y))!;

    [Fact]
    public void EdgeBand_IsProportionalButBounded()
    {
        Assert.Equal(75, DropTargetResolver.EdgeBand(new LayoutRect(0, 0, 400, 300)));
        // A huge pane must not get an absurd split zone…
        Assert.Equal(DropTargetResolver.MaxEdgeBand, DropTargetResolver.EdgeBand(new LayoutRect(0, 0, 4000, 3000)));
        // …and a tiny one must still have a usable one.
        Assert.Equal(DropTargetResolver.MinEdgeBand, DropTargetResolver.EdgeBand(new LayoutRect(0, 0, 40, 30)));
    }

    [Theory]
    [InlineData(10, 150, DropKind.SplitLeft)]     // hard left
    [InlineData(390, 150, DropKind.SplitRight)]   // hard right
    [InlineData(200, 40, DropKind.SplitTop)]      // near top, below the tab strip
    [InlineData(200, 295, DropKind.SplitBottom)]  // near bottom
    [InlineData(200, 150, DropKind.JoinStack)]    // dead centre
    public void PointerPosition_ResolvesToTheExpectedDestination(double x, double y, DropKind expected)
    {
        Assert.Equal(expected, Resolve(x, y).Kind);
        Assert.Equal("stack-a", Resolve(x, y).TargetNodeId);
    }

    // The tab strip is the one region where intent is unambiguous, so it wins over edge arithmetic.
    [Theory]
    [InlineData(5, 5)]      // top-left corner, which would otherwise be SplitLeft
    [InlineData(200, 14)]   // mid strip
    [InlineData(395, 27)]   // bottom edge of the strip
    public void TabStrip_AlwaysMeansJoin_EvenInACorner(double x, double y)
    {
        Assert.Equal(DropKind.JoinStack, Resolve(x, y).Kind);
    }

    // "No pane here" is a real destination — it is how every exemplar creates a floating pane.
    [Fact]
    public void PointerOutsideEveryPane_ResolvesToFloat()
    {
        var target = DropTargetResolver.Resolve(Panes, new LayoutPoint(900, 900))!;

        Assert.Equal(DropKind.Float, target.Kind);
        Assert.Equal(string.Empty, target.TargetNodeId);
    }

    [Fact]
    public void ALockedLayout_OffersNoDestinationAtAll()
    {
        Assert.Null(DropTargetResolver.Resolve(Panes, new LayoutPoint(200, 150), isLocked: true));
        Assert.Null(DropTargetResolver.Resolve(Panes, new LayoutPoint(900, 900), isLocked: true));
    }

    [Fact]
    public void TheTopmostPaneUnderThePointer_Wins()
    {
        IReadOnlyList<PaneHitBox> stacked =
        [
            new("floating", new LayoutRect(100, 100, 200, 150), 28),
            new("behind", new LayoutRect(0, 0, 400, 300), 28),
        ];

        var target = DropTargetResolver.Resolve(stacked, new LayoutPoint(200, 200))!;

        Assert.Equal("floating", target.TargetNodeId);
    }

    // Determinism at a corner: a resolver that flickers between two destinations is worse than one
    // that picks a fixed side.
    [Fact]
    public void ACornerResolvesDeterministically()
    {
        var first = Resolve(40, 40);
        for (var i = 0; i < 25; i++)
        {
            Assert.Equal(first, Resolve(40, 40));
        }
    }

    // ── The preview cannot disagree with the drop ─────────────────────────────────────────

    [Theory]
    [InlineData(DropKind.SplitLeft, 0, 0, 200, 300)]
    [InlineData(DropKind.SplitRight, 200, 0, 200, 300)]
    [InlineData(DropKind.SplitTop, 0, 0, 400, 150)]
    [InlineData(DropKind.SplitBottom, 0, 150, 400, 150)]
    [InlineData(DropKind.JoinStack, 0, 0, 400, 300)]
    public void Preview_MatchesTheDestinationItWillApply(
        DropKind kind, double x, double y, double w, double h)
    {
        var preview = DropTargetResolver.PreviewFor(Pane, new DropTarget("stack-a", kind));

        Assert.Equal(new LayoutRect(x, y, w, h), preview);
    }

    [Fact]
    public void EveryDropKind_HasADescription()
    {
        foreach (var kind in Enum.GetValues<DropKind>())
        {
            var text = DropTargetResolver.Describe(new DropTarget("stack-a", kind), "Sources");
            Assert.False(string.IsNullOrWhiteSpace(text));
            Assert.StartsWith("Destination:", text, StringComparison.Ordinal);
        }
    }

    // ── SC 2.5.7, now with BOTH paths real ────────────────────────────────────────────────

    /// <summary>
    /// A pointer drop and a keyboard command that name the same destination must produce the same
    /// tree. Previously this compared one path against itself; now the pointer side is resolved
    /// from real geometry, so the two inputs are genuinely different.
    /// </summary>
    [Theory]
    [InlineData(10, 150)]     // drop on the left edge
    [InlineData(390, 150)]    // right edge
    [InlineData(200, 295)]    // bottom edge
    [InlineData(200, 150)]    // centre → join
    public void PointerDropAndKeyboardCommand_ProduceIdenticalTrees(double x, double y)
    {
        // Pointer path: geometry → DropTarget → operation.
        var pointerService = new LayoutService();
        var stackId = pointerService.Current.FindStackOf("sources")!.Id;
        var panes = new[] { new PaneHitBox(stackId, new LayoutRect(0, 0, 400, 300), 28) };
        var resolved = DropTargetResolver.Resolve(panes, new LayoutPoint(x, y))!;
        pointerService.Apply(new LayoutOperation.MoveSurface("explore", resolved));

        // Keyboard path: the user names the same destination directly.
        var keyboardService = new LayoutService();
        keyboardService.Apply(new LayoutOperation.MoveSurface("explore",
            new DropTarget(stackId, resolved.Kind)));

        Assert.Equal(pointerService.Current.Shape(), keyboardService.Current.Shape());
    }

    [Fact]
    public void AResolvedDrop_AlwaysProducesAValidLayout()
    {
        foreach (var (x, y) in new[] { (10.0, 150.0), (390.0, 150.0), (200.0, 40.0), (200.0, 295.0), (200.0, 150.0) })
        {
            var service = new LayoutService();
            var stackId = service.Current.FindStackOf("sources")!.Id;
            var panes = new[] { new PaneHitBox(stackId, new LayoutRect(0, 0, 400, 300), 28) };

            var target = DropTargetResolver.Resolve(panes, new LayoutPoint(x, y))!;
            var result = service.Apply(new LayoutOperation.MoveSurface("explore", target));

            Assert.True(result.Applied, $"({x},{y}) → {target.Kind}: {result.RefusalCode}");
            service.Current.AssertInvariant();
        }
    }
}
