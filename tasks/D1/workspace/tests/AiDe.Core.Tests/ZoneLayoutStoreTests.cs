using AiDe.Core.Workbench;

namespace AiDe.Core.Tests;

/// <summary>
/// Zone-faithful persistence (ADR-0021 dz-persist): saving and restoring a WorkbenchLayout preserves
/// what the projected tree cannot — collapsed-zone content, per-zone extent, and exact placement —
/// while dropping surfaces the app can no longer provide.
/// </summary>
public sealed class ZoneLayoutStoreTests : IDisposable
{
    private readonly string _dir = Path.Combine(Path.GetTempPath(), "aide-zone-store-" + Guid.NewGuid().ToString("N"));

    private string Path_ => System.IO.Path.Combine(_dir, "zones.json");

    private static IReadOnlySet<string> All => new HashSet<string>(StringComparer.Ordinal);

    private static IReadOnlySet<string> Kinds(params string[] kinds) => new HashSet<string>(kinds, StringComparer.Ordinal);

    [Fact]
    public void SaveThenLoad_PreservesCollapsedState_Extents_AndExactPlacement()
    {
        // Arrange: a non-default arrangement — Right populated, Left collapsed, a custom Bottom extent.
        var layout = WorkbenchLayout.Default();
        layout = ZoneLayoutService.OpenPane(layout, new Surface("outline", "view", "Outline"), ZoneId.Right).Layout;
        layout = ZoneLayoutService.CollapseZone(layout, ZoneId.Left).Layout;
        layout = ZoneLayoutService.ResizeZone(layout, ZoneId.Bottom, 0.45).Layout;

        var store = new ZoneLayoutStore(Path_);
        store.Save(layout);

        // All kinds restorable so nothing is filtered.
        var restored = store.Read(All, Kinds("view", "canvas", "terminal", "sessions", "board", "leaderboard", "contexts", "joins")).Layout;

        Assert.NotNull(restored);
        Assert.True(restored!.Zone(ZoneId.Left).Collapsed);                 // collapsed state preserved
        Assert.False(restored.Zone(ZoneId.Left).IsEmpty);                   // collapsed content retained
        Assert.Equal(ZoneId.Right, restored.FindZoneOf("outline"));         // exact placement preserved
        Assert.Equal(0.45, restored.Zone(ZoneId.Bottom).Extent, precision: 6); // extent preserved
        Assert.Equal(ZoneId.Bottom, restored.FindZoneOf("terminal-1"));
    }

    [Fact]
    public void Load_DropsSurfacesTheAppCanNoLongerProvide()
    {
        var layout = ZoneLayoutService.OpenPane(
            WorkbenchLayout.Default(), new Surface("agent-terminal-xyz", "terminal", "Agent"), ZoneId.Bottom).Layout;
        new ZoneLayoutStore(Path_).Save(layout);

        // "terminal" kind is NOT restorable and the id is not available → the agent terminal is dropped;
        // everything else (view/canvas/etc.) is restorable by kind.
        var restored = new ZoneLayoutStore(Path_).Read(All, Kinds("view", "canvas", "sessions", "board", "leaderboard", "contexts", "joins")).Layout;

        Assert.NotNull(restored);
        Assert.DoesNotContain(restored!.AllSurfaces(), s => s.SurfaceId == "agent-terminal-xyz");
        Assert.DoesNotContain(restored.AllSurfaces(), s => s.SurfaceId == "terminal-1"); // terminal kind not restorable
        Assert.Contains(restored.AllSurfaces(), s => s.SurfaceId == "graph");            // canvas kind restorable
    }

    [Fact]
    public void Load_WithNoFile_ReturnsNull_SoTheCallerKeepsItsCurrentLayout()
    {
        Assert.Null(new ZoneLayoutStore(Path_).Read(All, Kinds("view")).Layout);
    }

    [Fact]
    public void Load_OfACorruptFile_ReturnsNull_WithoutThrowing()
    {
        Directory.CreateDirectory(_dir);
        File.WriteAllText(Path_, "{ this is not valid json");
        Assert.Null(new ZoneLayoutStore(Path_).Read(All, Kinds("view")).Layout);
    }

    [Fact]
    public void RestoreZones_OnTheService_ReplacesTheArrangement()
    {
        var svc = new ZoneBackedLayoutService();
        var saved = ZoneLayoutService.OpenPane(WorkbenchLayout.Default(), new Surface("outline", "view", "Outline"), ZoneId.Right).Layout;

        svc.RestoreZones(saved);

        Assert.Equal(ZoneId.Right, svc.Zones.FindZoneOf("outline"));
        Assert.Contains(ZonesToTree.RightStackId, svc.Current.AllStacks().Select(s => s.Id)); // reflected in the projection
    }

    // ── ADR-0032 rule 4 / test 7: refusal is reported, never silent ────────────────────────

    // Read distinguishes the three refusals Load folds into one null — no file, a newer schema, a
    // corrupt file (unreadable JSON, or a duplicated surface id the invariant refuses) — so the
    // caller can say WHY nothing was applied. A null with no reason fails.
    [Fact]
    public void Read_WithNoFile_ReportsNoFile_AndNoLayout()
    {
        var read = new ZoneLayoutStore(Path_).Read(All, Kinds("view"));

        Assert.Null(read.Layout);
        Assert.Equal(ZoneLoadRefusal.NoFile, read.Refusal);
    }

    [Fact]
    public void Read_OfANewerSchema_RefusesWithTheReason_AndLeavesTheFile()
    {
        Directory.CreateDirectory(_dir);
        var newer = "{\"schemaVersion\":2,\"appVersion\":\"9.9.9\",\"savedUtc\":\"2026-09-12T00:00:00+00:00\",\"layout\":{\"zones\":[],\"floating\":[]}}";
        File.WriteAllText(Path_, newer);

        var read = new ZoneLayoutStore(Path_).Read(All, Kinds("view"));

        Assert.Null(read.Layout);
        Assert.Equal(ZoneLoadRefusal.NewerSchema, read.Refusal);
        Assert.Equal(newer, File.ReadAllText(Path_));   // never partially applied, never rewritten by a read
    }

    [Fact]
    public void Read_OfACorruptFile_RefusesWithTheReason()
    {
        Directory.CreateDirectory(_dir);
        File.WriteAllText(Path_, "{ this is not valid json");

        var read = new ZoneLayoutStore(Path_).Read(All, Kinds("view"));

        Assert.Null(read.Layout);
        Assert.Equal(ZoneLoadRefusal.Corrupt, read.Refusal);
    }

    [Fact]
    public void Read_OfAFileWithADuplicateSurfaceId_RefusesTheWholeFileAsCorrupt()
    {
        // ADR-0032 test 3's recorded boundary: a duplicated surface id is refused whole by the
        // invariant, and Read says so rather than returning a bare null.
        Directory.CreateDirectory(_dir);
        var store = new ZoneLayoutStore(Path_);
        var layout = WorkbenchLayout.Default();
        store.Save(layout);
        var text = File.ReadAllText(Path_).Replace("\"surfaceId\": \"terminal-1\"", "\"surfaceId\": \"graph\"", StringComparison.Ordinal);
        File.WriteAllText(Path_, text);

        var read = store.Read(All, Kinds("canvas", "terminal", "view", "contexts", "joins", "sessions", "board", "leaderboard", "ledger"));

        Assert.Null(read.Layout);
        Assert.Equal(ZoneLoadRefusal.Corrupt, read.Refusal);
    }

    [Fact]
    public void Read_OfAGoodFile_ReturnsTheLayout_AndNoRefusal()
    {
        var store = new ZoneLayoutStore(Path_);
        store.Save(WorkbenchLayout.Default());

        var read = store.Read(All, Kinds("terminal"));

        Assert.NotNull(read.Layout);
        Assert.Equal(ZoneLoadRefusal.None, read.Refusal);
    }

    // ── ADR-0032 rule 3: atomic replace with a backup, from the BCL ────────────────────────

    // The destination is never overwritten until the new file is complete: a save writes a temp
    // file beside it and replaces. A stale temp file from an interrupted save neither corrupts the
    // read nor survives the next save.
    [Fact]
    public void Save_WritesThroughATempFile_AndAStaleTempFileNeitherBreaksTheReadNorSurvives()
    {
        var store = new ZoneLayoutStore(Path_);
        store.Save(WorkbenchLayout.Default());
        var before = File.ReadAllText(Path_);

        File.WriteAllText(store.TempPath, "{ interrupted mid-write");   // a save that died after the temp write

        Assert.Equal(ZoneLoadRefusal.None, store.Read(All, Kinds("terminal")).Refusal);
        Assert.Equal(before, File.ReadAllText(Path_));                   // the destination was left intact

        store.Save(WorkbenchLayout.Default());
        Assert.False(File.Exists(store.TempPath));
    }

    // When a backup is due, the SAME call that replaces the original preserves it: the backup holds
    // the original's bytes, byte for byte.
    [Fact]
    public void Save_WithABackupPath_PreservesTheOriginalBytesInTheBackup()
    {
        var store = new ZoneLayoutStore(Path_);
        store.Save(WorkbenchLayout.Default());
        var original = File.ReadAllBytes(Path_);
        var backup = Path_ + ".pre-perspectives.bak";

        var second = ZoneLayoutService.OpenPane(WorkbenchLayout.Default(), new Surface("outline", "view", "Outline"), ZoneId.Right).Layout;
        store.Save(second, backupPath: backup);

        Assert.Equal(original, File.ReadAllBytes(backup));
        Assert.NotEqual(original, File.ReadAllBytes(Path_));
        Assert.Contains("\"outline\"", File.ReadAllText(Path_), StringComparison.Ordinal);
    }

    // With the backup target unwritable, the replace fails BEFORE the original is touched — the
    // destination keeps its bytes and the failure surfaces to the caller, who reports it. This is
    // the fail-safe half the tree store's best-effort backup lacks (ADR-0032 rule 3).
    [Fact]
    public void Save_WithAnUnwritableBackupTarget_LeavesTheOriginalUnchanged_AndThrows()
    {
        var store = new ZoneLayoutStore(Path_);
        store.Save(WorkbenchLayout.Default());
        var original = File.ReadAllBytes(Path_);
        var backup = Path_ + ".pre-perspectives.bak";
        Directory.CreateDirectory(backup);   // a directory where the backup file must go: unwritable as a file

        var second = ZoneLayoutService.OpenPane(WorkbenchLayout.Default(), new Surface("outline", "view", "Outline"), ZoneId.Right).Layout;

        Assert.ThrowsAny<IOException>(() => store.Save(second, backupPath: backup));
        Assert.Equal(original, File.ReadAllBytes(Path_));
        Assert.False(File.Exists(store.TempPath));
    }

    public void Dispose()
    {
        try { if (Directory.Exists(_dir)) { Directory.Delete(_dir, recursive: true); } }
        catch (IOException) { }
    }
}
