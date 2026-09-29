using AiDe.Core.Workbench;

namespace AiDe.Core.Tests.Workbench;

/// <summary>
/// Coding's default as re-cut by Rulings 83 and 88 (SH-4.2, L1): Left = session documents, empty
/// until one opens, at the extent that holds the thread's 96ch measure · Center = the empty state ·
/// Bottom = one terminal, <b>collapsed</b> (the operator's <i>Bottom (1)</i>) · Right = empty.
/// </summary>
/// <remarks>
/// <b>Red before green:</b> the Bottom was not collapsed (Ruling 60's expanded terminal) and the
/// Left sat at the tool-zone default 0.22 — a 96ch column cannot fit a 22 % column at 1440 px
/// (<c>docs/proof/coding-recut-left-dock.md</c>). The extent's fit is measured on the composed
/// tree by the App's <c>CodingsLeftExtentTests</c>; this pins the model the composition reads.
/// </remarks>
public sealed class ZoneLayoutTests
{
    [Fact]
    public void CodingDefault_IsLeftEmpty_CenterEmpty_BottomOneTerminalCollapsed()
    {
        var layout = WorkbenchLayout.Default(PerspectiveSet.Coding);

        var left = layout.Zone(ZoneId.Left);
        Assert.Null(left.Content);
        Assert.False(left.Collapsed);   // empty, so it renders as its rail regardless — but never marked collapsed: a session opening there must not have to expand it

        // Ruling 83 condition 1: the Left is cut for the thread — 1.3 of the Center (DESIGN.md's
        // errata row; the mockup's `minmax(0,1.3fr) minmax(0,1fr)`), stated once as a named constant.
        Assert.Equal(WorkbenchLayout.CodingLeftExtent, left.Extent);
        Assert.Equal(1.3, left.Extent / (1 - left.Extent), 6);
        Assert.True(left.Extent > ZoneState.DefaultExtent, "the Left is a document zone here, not a tool rail; the tool default cannot hold 96ch");

        Assert.Null(layout.Zone(ZoneId.Center).Content);
        Assert.Null(layout.Zone(ZoneId.Right).Content);

        var bottom = layout.Zone(ZoneId.Bottom);
        var terminal = Assert.Single(bottom.Surfaces());
        Assert.Equal("terminal", terminal.Kind);
        Assert.True(bottom.Collapsed, "Ruling 88: Coding's default Bottom is collapsed — the terminal is one gesture away, not across the tree");

        // The projected frame: with the Left empty and the Bottom collapsed, the Center is the whole
        // tree until a session opens — the shape every fresh Coding host renders.
        Assert.Equal("Left:-|Right:-|Bottom:[terminal-1@0]/collapsed|Center:-|float:", layout.Shape());
        layout.AssertInvariant();
    }

    /// <summary>
    /// The extent survives the open: a session opening into the empty Left keeps the 1.3 cut
    /// (<c>OpenPane</c> floors an EMPTY tool zone at the tool default — a floor, never a ceiling),
    /// and the projected columns carry the ratio the mockup measured.
    /// </summary>
    [Fact]
    public void ASessionOpeningIntoTheEmptyLeft_KeepsThe1Point3Cut_InTheProjectedColumns()
    {
        var layout = WorkbenchLayout.Default(PerspectiveSet.Coding);
        var opened = ZoneLayoutService.OpenPane(layout, new Surface("session:s1", "session-document", "S1"), ZoneId.Left);
        Assert.True(opened.Applied);

        var columns = Assert.IsType<SplitNode>(ZonesToTree.ToTree(opened.Layout).Root);   // no Bottom row: it is collapsed
        Assert.Equal(Orientation.Horizontal, columns.Orientation);
        Assert.Equal(2, columns.Children.Count);
        Assert.Equal(ZonesToTree.LeftStackId, ((StackNode)columns.Children[0]).Id);
        Assert.Equal(1.3, columns.Weights[0] / columns.Weights[1], 6);
    }
}
