using AiDe.Core.Workbench;

namespace AiDe.Core.Tests;

/// <summary>
/// ADR-0012's "layout round-trip across an app upgrade" spike, made permanent.
///
/// ADR-0013 put layouts in a versioned envelope specifically so an upgrade would have a migration
/// hook. The version FIELD existed from day one; the HOOK did not — an older file was read as-is,
/// so the first release that renamed a surface would silently drop it from every saved layout.
/// These tests pin the hook.
/// </summary>
public sealed class LayoutUpgradeTests : IDisposable
{
    private readonly string _dir =
        Path.Combine(Path.GetTempPath(), "aide-upgrade", Guid.NewGuid().ToString("N"));

    private string Path_ => Path.Combine(_dir, "layout.json");

    /// <summary>
    /// The rename that used to sit in the shipped chain as a worked example.
    /// </summary>
    /// <remarks>
    /// It documents a rename the product never performed. It lives here now, because a placeholder
    /// in the SHIPPED chain made the mechanism look exercised while doing nothing — and the first
    /// real release that added a surface reached existing users only if they knew to reset their
    /// layout. The hypothetical belongs in the test that asserts it; the chain ships what happened.
    /// </remarks>
    private static readonly IReadOnlyList<LayoutMigration> RenameChain =
        [new(1, dto => LayoutMigrations.RenameSurface(dto, "terminal-1", "terminal.session.1"))];

    /// <summary>The surface set a LATER release ships, after renaming the terminal surface.</summary>
    // DERIVED from the default layout, with the v1→v2 rename applied — not typed. A hardcoded copy
    // turns "a release added a surface" into unrelated persistence failures that say nothing about
    // migration, which it has now done three times. Same rule as WorkbenchStoreTests.
    private static readonly HashSet<string> V2Surfaces =
        [.. Layout.Default().AllStacks().SelectMany(stack => stack.Surfaces)
            .Select(surface => surface.SurfaceId == "terminal-1" ? "terminal.session.1" : surface.SurfaceId)];

    /// <summary>The surfaces this release ships, at the current schema version.</summary>
    private static readonly HashSet<string> CurrentSurfaces =
        [.. Layout.Default().AllStacks().SelectMany(stack => stack.Surfaces)
            .Select(surface => surface.SurfaceId)];

    /// <summary>A layout as the release that called the terminal surface "terminal-1" saved it.</summary>
    private void WriteV1Layout() => WriteFileAtSchema1(Layout.Default());

    /// <summary>Writes a layout and stamps the envelope back to schema 1.</summary>
    /// <remarks>
    /// Save always writes the CURRENT version, so a genuinely older file cannot be produced by the
    /// shipped writer. Rewriting the field is the honest stand-in: everything else about the file is
    /// exactly what version 1 wrote, because version 1 wrote this payload shape.
    /// </remarks>
    private void WriteFileAtSchema1(Layout layout)
    {
        new LayoutStore(Path_, appVersion: "0.3.0").Save(layout);
        File.WriteAllText(Path_, File.ReadAllText(Path_)
            .Replace($"\"schemaVersion\": {LayoutStore.CurrentSchemaVersion}", "\"schemaVersion\": 1", StringComparison.Ordinal));
    }

    [Fact]
    public void TheShippedChain_CoversEveryVersionGap()
    {
        // Each step is tested; nothing asserted that the STEPS JOIN UP. A version bumped without a
        // migration beside it degrades every older layout to the default with
        // AIDE-LAYOUT-VERSION-UNSUPPORTED — correct behaviour, and a silent loss of everyone's
        // arrangement on upgrade day. This is the only assertion that fails the moment that happens.
        var steps = LayoutMigrations.Default.Select(m => m.FromVersion).ToHashSet();

        for (var version = 1; version < LayoutStore.CurrentSchemaVersion; version++)
        {
            Assert.True(steps.Contains(version),
                $"no migration from schema {version}; a layout at that version cannot reach " +
                $"{LayoutStore.CurrentSchemaVersion} and would be reset to the default.");
        }
    }

    [Fact]
    public void ALayoutFromTheOldestSchema_ArrivesValidAtTheCurrentOne()
    {
        // The whole path a real user takes, rather than one step of it. Every earlier test pins a
        // single hop with an assumed version; this one runs the SHIPPED chain at the SHIPPED
        // version, which is the only combination anybody actually upgrades through.
        WriteFileAtSchema1(Layout.Default());

        var result = new LayoutStore(Path_, appVersion: "0.4.0").Load(CurrentSurfaces);

        Assert.False(result.WasDefaulted);
        Assert.Null(result.ErrorCode);
        Assert.Empty(result.MissingSurfaces);
        result.Layout.AssertInvariant();

        // Every surface this release ships is present after the climb — derived, so adding one and
        // forgetting its migration fails here rather than on a user's machine.
        var restored = result.Layout.AllStacks().SelectMany(stack => stack.Surfaces)
            .Select(surface => surface.SurfaceId).ToHashSet(StringComparer.Ordinal);

        Assert.Equal(CurrentSurfaces.OrderBy(id => id, StringComparer.Ordinal),
            restored.OrderBy(id => id, StringComparer.Ordinal));

        Assert.Contains($"\"schemaVersion\": {LayoutStore.CurrentSchemaVersion}",
            File.ReadAllText(Path_), StringComparison.Ordinal);
    }

    [Fact]
    public void ASurfaceAddedByThisRelease_ReachesALayoutSavedBeforeIt()
    {
        // The defect this migration exists for. Adding a pane to Layout.Default reaches only people
        // with no saved layout — which is nobody who has used the product. Everyone who has ever
        // arranged their workbench got the feature only if they knew to reset it.
        var before = Layout.Default();
        var withoutJoins = LayoutService.Detach(before, "joins")!;
        WriteFileAtSchema1(withoutJoins);

        var result = new LayoutStore(Path_, appVersion: "0.4.0").Load(CurrentSurfaces);

        Assert.False(result.WasDefaulted);
        Assert.Null(result.ErrorCode);
        Assert.Contains(result.Layout.AllStacks().SelectMany(stack => stack.Surfaces),
            surface => surface.SurfaceId == "joins");

        // Beside its anchor, not wherever the tree happened to allow it.
        Assert.Contains(result.Layout.FindStackOf("joins")!.Surfaces, s => s.SurfaceId == "contexts");
    }

    [Fact]
    public void APaneTheUserClosedIsNotReopenedUnderANewName()
    {
        // If the anchor is gone, the user has said something about that area of the workbench.
        // Re-opening it as a different pane is not an upgrade.
        var stripped = LayoutService.Detach(LayoutService.Detach(Layout.Default(), "joins")!, "contexts")!;
        WriteFileAtSchema1(stripped);

        var result = new LayoutStore(Path_, appVersion: "0.4.0").Load(CurrentSurfaces);

        Assert.DoesNotContain(result.Layout.AllStacks().SelectMany(stack => stack.Surfaces),
            surface => surface.SurfaceId == "joins");
    }

    [Fact]
    public void TheMigrationIsSafeToReRun()
    {
        // Rewritten on read so it is not re-migrated every launch — but a step that duplicated the
        // surface if it ever ran twice would violate the layout's own uniqueness invariant, which
        // fails as a corrupt file rather than as a duplicate tab.
        var start = new LayoutDto(LayoutStore.ToDto(LayoutService.Detach(Layout.Default(), "joins")!.Root), []);
        var once = LayoutMigrations.AddSurfaceBeside(start, "contexts", new SurfaceDto("joins", "joins", "Joins"));

        var twice = LayoutMigrations.AddSurfaceBeside(once, "contexts", new SurfaceDto("joins", "joins", "Joins"));

        var layout = new Layout(LayoutStore.FromDto(twice.Root), [],
            System.Collections.Immutable.ImmutableDictionary<string, StackState>.Empty);

        layout.AssertInvariant();
        Assert.Single(layout.AllStacks().SelectMany(s => s.Surfaces), s => s.SurfaceId == "joins");
    }

    [Fact]
    public void TheV2ToV3Migration_AddsBoardAndLeaderboardBesideSessions()
    {
        // A layout arranged before Loomkeeper shipped has Sessions but not Board/Leaderboard. The
        // shipped v2→v3 step must add both beside Sessions, or the watcher UX is invisible to the
        // operators who arranged their workbench first (the same visibility lesson as Joins).
        var withoutWatcherPanes = LayoutService.Detach(
            LayoutService.Detach(Layout.Default(), "board")!, "leaderboard")!;
        var start = new LayoutDto(LayoutStore.ToDto(withoutWatcherPanes.Root), []);
        Assert.DoesNotContain(start.Root.Surfaces ?? [], s => s.SurfaceId == "board");

        var step = LayoutMigrations.Default.Single(m => m.FromVersion == 2);
        var migrated = new Layout(LayoutStore.FromDto(step.Apply(start).Root), [],
            System.Collections.Immutable.ImmutableDictionary<string, StackState>.Empty);

        var surfaces = migrated.AllStacks().SelectMany(s => s.Surfaces).ToList();
        // Both are present, exactly once, in the same stack as sessions.
        var sessionsStack = migrated.AllStacks().Single(s => s.Surfaces.Any(x => x.SurfaceId == "sessions"));
        Assert.Contains(sessionsStack.Surfaces, s => s.SurfaceId == "board");
        Assert.Contains(sessionsStack.Surfaces, s => s.SurfaceId == "leaderboard");
        Assert.Single(surfaces, s => s.SurfaceId == "board");
        Assert.Single(surfaces, s => s.SurfaceId == "leaderboard");
        migrated.AssertInvariant();
    }

    [Fact]
    public void TheV3ToV4Migration_AddsLedgerBesideLeaderboard()
    {
        // A layout arranged before the Ledger shipped has Board/Leaderboard but not Ledger. The
        // v3→v4 step must add it beside Leaderboard, or the Ledger is invisible to the operators who
        // arranged their workbench first (the same visibility lesson as Board/Leaderboard/Joins).
        var withoutLedger = LayoutService.Detach(Layout.Default(), "ledger")!;
        var start = new LayoutDto(LayoutStore.ToDto(withoutLedger.Root), []);
        Assert.DoesNotContain(start.Root.Surfaces ?? [], s => s.SurfaceId == "ledger");

        var step = LayoutMigrations.Default.Single(m => m.FromVersion == 3);
        var migrated = new Layout(LayoutStore.FromDto(step.Apply(start).Root), [],
            System.Collections.Immutable.ImmutableDictionary<string, StackState>.Empty);

        var surfaces = migrated.AllStacks().SelectMany(s => s.Surfaces).ToList();
        var leaderboardStack = migrated.AllStacks().Single(s => s.Surfaces.Any(x => x.SurfaceId == "leaderboard"));
        Assert.Contains(leaderboardStack.Surfaces, s => s.SurfaceId == "ledger");
        Assert.Single(surfaces, s => s.SurfaceId == "ledger");
        migrated.AssertInvariant();
    }

    // The upgrade path: an old file, a new app, and a surface that was renamed between them.
    [Fact]
    public void AnOlderLayout_IsMigratedRatherThanSilentlyLosingRenamedSurfaces()
    {
        WriteV1Layout();

        // assumedCurrentVersion: 2 simulates the LATER build — the file is v1, the app is v2, and
        // the gap between them is what the migration chain exists to cross.
        var store = new LayoutStore(Path_, appVersion: "0.4.0", migrations: RenameChain);
        var result = store.Load(V2Surfaces, assumedCurrentVersion: 2);

        Assert.False(result.WasDefaulted);
        // The pane must survive the rename. Dropping it would silently delete part of an
        // arrangement the user built.
        Assert.Empty(result.MissingSurfaces);
        Assert.Contains(result.Layout.AllStacks().SelectMany(s => s.Surfaces),
            s => s.SurfaceId == "terminal.session.1");
        result.Layout.AssertInvariant();
    }

    [Fact]
    public void AMigratedLayout_IsRewrittenAtTheCurrentSchemaVersion()
    {
        WriteV1Layout();
        var store = new LayoutStore(Path_, appVersion: "0.4.0", migrations: RenameChain);

        store.Load(V2Surfaces, assumedCurrentVersion: 2);

        // Rewritten on read, so the migration is paid once rather than on every launch.
        Assert.Contains($"\"schemaVersion\": {LayoutStore.CurrentSchemaVersion}",
            File.ReadAllText(Path_), StringComparison.Ordinal);
    }

    [Fact]
    public void ALayoutAlreadyAtTheCurrentVersion_IsNotMigrated()
    {
        var store = new LayoutStore(Path_, appVersion: "0.4.0", migrations: RenameChain);
        store.Save(Layout.Default());
        var before = File.GetLastWriteTimeUtc(Path_);

        var result = store.Load(CurrentSurfaces);

        Assert.False(result.WasDefaulted);
        Assert.Null(result.ErrorCode);
        Assert.Equal(before, File.GetLastWriteTimeUtc(Path_));
    }

    // An old file with no migration available must degrade honestly, not be read as if current.
    [Fact]
    public void AnOlderLayout_WithNoMigrationPath_DegradesRatherThanGuessing()
    {
        WriteV1Layout();

        // A store that knows about a v3 schema but has no way to get there from v1.
        var store = new LayoutStore(Path_, appVersion: "0.9.0", migrations: []);
        var result = store.Load(V2Surfaces, assumedCurrentVersion: 3);

        Assert.True(result.WasDefaulted);
        Assert.Equal(LayoutErrorCodes.VersionUnsupported, result.ErrorCode);
        Assert.Contains("could not be upgraded", result.Announcement, StringComparison.OrdinalIgnoreCase);
        Assert.True(File.Exists(store.BackupPath));
    }

    [Fact]
    public void MigrationsRun_InOrder_AcrossMultipleVersions()
    {
        var applied = new List<int>();
        var migrations = new LayoutMigration[]
        {
            new(1, dto => { applied.Add(1); return dto; }),
            new(2, dto => { applied.Add(2); return dto; }),
        };

        WriteV1Layout();
        var store = new LayoutStore(Path_, appVersion: "0.5.0", migrations: migrations);
        store.Load(CurrentSurfaces, assumedCurrentVersion: 3);

        Assert.Equal([1, 2], applied);
    }

    public void Dispose()
    {
        try { Directory.Delete(_dir, recursive: true); } catch (IOException) { }
    }
}
