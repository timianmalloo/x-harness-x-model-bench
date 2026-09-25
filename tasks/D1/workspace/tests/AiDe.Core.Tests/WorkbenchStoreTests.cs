using AiDe.Core.Workbench;

namespace AiDe.Core.Tests;

/// <summary>
/// ADR-0013 — the owned versioned envelope. The contract US-9 sets is that a layout which cannot be
/// honoured degrades to the default **and says what was lost**, preserving the original file —
/// never a broken window, never a silently dropped surface.
/// </summary>
public sealed class WorkbenchStoreTests : IDisposable
{
    private readonly string _dir =
        Path.Combine(Path.GetTempPath(), "aide-layout", Guid.NewGuid().ToString("N"));

    private string Path_ => Path.Combine(_dir, "layout.json");

    // DERIVED from the default layout, not typed. This list is "the surfaces this release ships",
    // which changes whenever one is added — and a hardcoded copy turns adding a surface into three
    // unrelated test failures that say nothing about persistence. It has already done so twice.
    private static readonly HashSet<string> AllSurfaces =
        [.. AiDe.Core.Workbench.Layout.Default().AllStacks()
            .SelectMany(stack => stack.Surfaces).Select(surface => surface.SurfaceId)];


    /// <summary>What the shell now passes: the shipped ids, plus every kind it can build.</summary>
    /// <remarks>
    /// The KINDS are derived too — from the surfaces the default layout declares, which is the same
    /// source the shell's factory is kept in step with. Typing them out is DC-021, and this file is
    /// where that class was first repaired.
    /// </remarks>
    private static readonly SurfaceAvailability Availability =
        new(AllSurfaces,
            Layout.Default().AllStacks().SelectMany(stack => stack.Surfaces)
                .Select(s => s.Kind).ToHashSet(StringComparer.Ordinal));

    [Fact]
    public void ASurfaceCreatedAtRuntimeSurvivesARestart()
    {
        // The reported shape, as an assertion. An agent terminal's id is minted when it is opened
        // (agent:claude#a1b2c3), so no list of shipped ids can contain it — and the restore dropped
        // it as "no longer available" on EVERY launch, announcing the loss of a pane the shell was
        // perfectly able to rebuild.
        var service = new LayoutService();
        var stack = service.Current.FindStackOf("terminal-1")!;
        service.Apply(new LayoutOperation.AddSurface(
            stack.Id, new Surface("agent:claude#a1b2c3", "terminal", "claude")));

        var store = new LayoutStore(Path_);
        store.Save(service.Current);

        var restored = store.Load(Availability);

        Assert.Null(restored.ErrorCode);
        Assert.Empty(restored.MissingSurfaces);
        Assert.Contains(restored.Layout.AllStacks().SelectMany(s => s.Surfaces),
            s => s.SurfaceId == "agent:claude#a1b2c3");
    }

    [Fact]
    public void ASurfaceOfAKindThisBuildNoLongerHas_IsStillDroppedAndReported()
    {
        // The other half, and the reason availability-by-kind is not just "accept everything". A
        // kind that was removed cannot be built, and restoring it would produce a pane rendering
        // nothing. The control must still fire, or widening availability quietly disabled it.
        var service = new LayoutService();
        var stack = service.Current.FindStackOf("terminal-1")!;
        service.Apply(new LayoutOperation.AddSurface(
            stack.Id, new Surface("legacy-1", "timeline", "Timeline")));

        var store = new LayoutStore(Path_);
        store.Save(service.Current);

        var restored = store.Load(Availability);

        Assert.Equal(LayoutErrorCodes.PartialRestore, restored.ErrorCode);
        Assert.Contains("Timeline", restored.MissingSurfaces);
        Assert.DoesNotContain(restored.Layout.AllStacks().SelectMany(s => s.Surfaces),
            s => s.SurfaceId == "legacy-1");
    }

    [Fact]
    public void Envelope_RoundTripsTheLayoutExactly()
    {
        var service = new LayoutService();
        service.Apply(new LayoutOperation.MoveSurface("domain",
            new DropTarget(service.Current.FindStackOf("sources")!.Id, DropKind.SplitBottom)));
        service.Apply(new LayoutOperation.MoveSurface("terminal-1", new DropTarget("", DropKind.Float)));
        var expected = service.Current.Shape();

        var store = new LayoutStore(Path_);
        store.Save(service.Current);
        var restored = store.Load(AllSurfaces);

        Assert.False(restored.WasDefaulted);
        Assert.Null(restored.ErrorCode);
        Assert.Equal(expected, restored.Layout.Shape());
    }

    [Fact]
    public void Load_WithNoFile_StartsFromTheDefaultWithoutComplaining()
    {
        var result = new LayoutStore(Path_).Load(AllSurfaces);

        Assert.True(result.WasDefaulted);
        Assert.Null(result.ErrorCode);
        result.Layout.AssertInvariant();
    }

    // The degradation contract. Fails RED against a store that throws or returns a broken tree.
    [Fact]
    public void Load_Unreadable_FallsBackToDefaultAndPreservesTheOriginalFile()
    {
        Directory.CreateDirectory(_dir);
        File.WriteAllText(Path_, "{ this is not json");
        var store = new LayoutStore(Path_);

        var result = store.Load(AllSurfaces);

        Assert.True(result.WasDefaulted);
        Assert.Equal(LayoutErrorCodes.Unreadable, result.ErrorCode);
        Assert.Contains("kept", result.Announcement, StringComparison.OrdinalIgnoreCase);
        // The user's file is evidence of their intent — it must survive.
        Assert.True(File.Exists(store.BackupPath));
        result.Layout.AssertInvariant();
    }

    [Fact]
    public void Load_FromANewerSchema_DegradesRatherThanGuessing()
    {
        Directory.CreateDirectory(_dir);
        var store = new LayoutStore(Path_);
        store.Save(Layout.Default());
        // Read from the constant, not typed. A test that hardcodes the current version silently
        // stops testing anything the release after it — the same shape as DC-021, one field wide.
        File.WriteAllText(Path_, File.ReadAllText(Path_)
            .Replace($"\"schemaVersion\": {LayoutStore.CurrentSchemaVersion}", "\"schemaVersion\": 99",
                StringComparison.Ordinal));

        var result = store.Load(AllSurfaces);

        Assert.True(result.WasDefaulted);
        Assert.Equal(LayoutErrorCodes.VersionUnsupported, result.ErrorCode);
        Assert.Contains("newer version", result.Announcement, StringComparison.OrdinalIgnoreCase);
    }

    // Partial restore must name what it lost, not say "some panes were unavailable".
    [Fact]
    public void Load_WithAMissingSurface_NamesItAndStillProducesAValidLayout()
    {
        var store = new LayoutStore(Path_);
        store.Save(Layout.Default());

        // Everything except the terminal, derived rather than listed: the point of the case is the
        // ONE surface that is gone, and spelling out the others makes it a case about all of them.
        var result = store.Load(new HashSet<string>(
            AllSurfaces.Where(id => id != "terminal-1"), StringComparer.Ordinal));

        Assert.Equal(LayoutErrorCodes.PartialRestore, result.ErrorCode);
        Assert.Contains("Terminal — pwsh", result.MissingSurfaces);
        Assert.Contains("Terminal — pwsh", result.Announcement, StringComparison.Ordinal);
        Assert.DoesNotContain(result.Layout.AllStacks().SelectMany(s => s.Surfaces),
            s => s.SurfaceId == "terminal-1");
        result.Layout.AssertInvariant();
    }

    [Fact]
    public void Load_WithAFloatingPaneOnADisconnectedDisplay_ReportsTheRehoming()
    {
        var service = new LayoutService();
        service.Apply(new LayoutOperation.MoveSurface("sources", new DropTarget("", DropKind.Float)));
        var store = new LayoutStore(Path_);
        store.Save(service.Current);

        var result = store.Load(AllSurfaces, displayIsConnected: _ => false);

        Assert.Equal(LayoutErrorCodes.PartialRestore, result.ErrorCode);
        Assert.Contains("Sources", result.RehomedFloating);
        Assert.Contains("not connected", result.Announcement, StringComparison.OrdinalIgnoreCase);
    }

    // A malformed-but-parseable tree must not be adopted: validate before trusting.
    [Fact]
    public void Load_WithAStructurallyInvalidTree_Degrades()
    {
        Directory.CreateDirectory(_dir);
        File.WriteAllText(Path_, """
            { "schemaVersion": 1, "appVersion": "0.3.0", "savedAt": "2026-08-26T00:00:00+00:00",
              "payload": { "Root": { "Id": "s", "Kind": "stack", "ActiveIndex": 0,
              "State": "Docked", "Surfaces": [] }, "Floating": [] } }
            """);

        var result = new LayoutStore(Path_).Load(AllSurfaces);

        Assert.True(result.WasDefaulted);
        Assert.Equal(LayoutErrorCodes.Unreadable, result.ErrorCode);
    }

    public void Dispose()
    {
        try { Directory.Delete(_dir, recursive: true); } catch (IOException) { }
    }
}
