using System.Reflection;
using AiDe.Core.Workbench;

namespace AiDe.Core.Tests;

/// <summary>
/// SC 2.5.7 (Dragging Movements) made machine-checkable: every layout operation reachable by
/// dragging must have a keyboard equivalent. Photoshop and Premiere fail this criterion outright and
/// VS Code fails it inside floating windows; the point of these tests is that we cannot drift into
/// the same state silently.
/// </summary>
public sealed class WorkbenchCommandTests
{
    /// <summary>
    /// The conformance test. Reflects over the operation union so a NEW operation added without a
    /// keyboard command fails here rather than shipping mouse-only.
    /// </summary>
    [Fact]
    public void EveryLayoutOperation_HasAKeyboardCommand()
    {
        var operations = typeof(LayoutOperation).GetNestedTypes(BindingFlags.Public)
            .Where(t => t.IsSubclassOf(typeof(LayoutOperation)))
            .Select(t => t.Name)
            .ToHashSet(StringComparer.Ordinal);

        var covered = WorkbenchCommandCatalog.All
            .Select(c => c.OperationKind)
            .Where(k => !string.IsNullOrEmpty(k))
            .ToHashSet(StringComparer.Ordinal);

        var uncovered = operations.Except(covered).ToList();

        Assert.True(uncovered.Count == 0,
            "layout operations with no keyboard command (SC 2.5.7): " + string.Join(", ", uncovered));
    }

    [Fact]
    public void EveryCommand_HasATitleAGestureAndAHint()
    {
        foreach (var command in WorkbenchCommandCatalog.All)
        {
            Assert.False(string.IsNullOrWhiteSpace(command.Title), command.Id);
            Assert.False(string.IsNullOrWhiteSpace(command.Gesture), command.Id);
            // The hint is what the palette shows; a command the user cannot understand is not
            // meaningfully reachable.
            Assert.False(string.IsNullOrWhiteSpace(command.Hint), command.Id);
        }
    }

    [Fact]
    public void CommandIds_AreUnique()
    {
        var ids = WorkbenchCommandCatalog.All.Select(c => c.Id).ToList();
        Assert.Equal(ids.Count, ids.Distinct(StringComparer.Ordinal).Count());
    }

    [Theory]
    [InlineData("resize", "workbench.resizePane")]
    [InlineData("lock", "workbench.toggleLock")]
    [InlineData("float", "workbench.floatPane")]
    public void Search_FindsCommandsByTitleOrHint(string term, string expectedId)
    {
        var hits = WorkbenchCommandCatalog.Search(WorkbenchCommandCatalog.All, term).Select(c => c.Id).ToList();
        Assert.Contains(expectedId, hits);
    }

    [Fact]
    public void Search_WithNoTerm_ReturnsEverything()
    {
        Assert.Equal(WorkbenchCommandCatalog.All.Count, WorkbenchCommandCatalog.Search(WorkbenchCommandCatalog.All, "  ").Count());
    }

    // ── The Eclipse-pattern resize session ────────────────────────────────────────────────

    [Fact]
    public void Resize_Begin_AnnouncesWhichEdgeIsSelected()
    {
        var session = new KeyboardResizeSession(new LayoutService());

        var announcement = session.Begin("split-root", 0, "vertical divider");

        Assert.True(session.IsActive);
        // A keyboard user cannot see what a pointer user infers from the cursor, so the edge must be
        // named before the arrow keys do anything.
        Assert.Contains("vertical divider", announcement, StringComparison.Ordinal);
        Assert.Contains("Escape", announcement, StringComparison.Ordinal);
    }

    [Fact]
    public void Resize_Adjust_MovesTheDivider()
    {
        var service = new LayoutService();
        var session = new KeyboardResizeSession(service);
        var before = ((SplitNode)service.Current.Root).Weights[0];
        session.Begin("split-root", 0, "vertical divider");

        var result = session.Adjust(+1);

        Assert.True(result.Applied);
        Assert.True(((SplitNode)service.Current.Root).Weights[0] > before);
    }

    // Escape must return EXACTLY to the entry state — replaying inverse steps would drift.
    [Fact]
    public void Resize_Cancel_RestoresTheLayoutExactlyAsItWasOnEntry()
    {
        var service = new LayoutService();
        var session = new KeyboardResizeSession(service);
        var before = service.Current.Shape();

        session.Begin("split-root", 0, "vertical divider");
        session.Adjust(+1);
        session.Adjust(+1);
        session.Adjust(+1);
        Assert.NotEqual(before, service.Current.Shape());

        session.Cancel();

        Assert.Equal(before, service.Current.Shape());
        Assert.False(session.IsActive);
    }

    [Fact]
    public void Resize_Commit_KeepsTheChange()
    {
        var service = new LayoutService();
        var session = new KeyboardResizeSession(service);
        session.Begin("split-root", 0, "vertical divider");
        session.Adjust(+1);
        var adjusted = service.Current.Shape();

        session.Commit();

        Assert.Equal(adjusted, service.Current.Shape());
        Assert.False(session.IsActive);
    }

    // A refusal must not end the session: the user should be able to try the other direction.
    [Fact]
    public void Resize_AtMinimum_RefusesButKeepsTheSessionOpen()
    {
        var service = new LayoutService();
        var session = new KeyboardResizeSession(service) { Step = 0.5 };
        session.Begin("split-root", 0, "vertical divider");

        var result = session.Adjust(+1);

        Assert.False(result.Applied);
        Assert.Equal(LayoutErrorCodes.MinSize, result.RefusalCode);
        Assert.True(session.IsActive);
    }

    [Fact]
    public void Resize_AdjustWithoutBeginning_IsRefused()
    {
        var session = new KeyboardResizeSession(new LayoutService());

        var result = session.Adjust(+1);

        Assert.False(result.Applied);
    }

    [Fact]
    public void Restore_PutsBackAKnownLayout()
    {
        var service = new LayoutService();
        var original = service.Current;
        service.Apply(new LayoutOperation.ResizeSplit("split-root", 0, 0.1));
        Assert.NotEqual(original.Shape(), service.Current.Shape());

        service.Restore(original);

        Assert.Equal(original.Shape(), service.Current.Shape());
    }
}
