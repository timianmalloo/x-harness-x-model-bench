using AiDe.Core.Upgrade;

namespace AiDe.Core.Tests;

/// <summary>
/// `P2-UPGRADE-01..03` — the path to a new daemon, and back.
/// </summary>
/// <remarks>
/// <para><b>The asymmetry that shapes all of this: an upgrade that fails halfway is worse than one
/// that never started.</b> A store migrated to a schema the running binary cannot read is a
/// workspace nobody can open, and the user's evidence is inside it. So every step is ordered so that
/// the point of no return comes last, and the journal exists so a process that dies before reaching
/// it leaves enough behind for the next start to finish the sentence.</para>
///
/// <para><b>The health gate is the fast subset only.</b> Full restore/replay equality is
/// asynchronous verification: P1-PERF measured a 50k-edge replay against a 15-minute RTO while the
/// gate has a 60-second budget. Putting the slow check inside the fast gate is the contradiction the
/// council review caught in the v1 architecture, and it must not return here — so the budget is
/// enforced rather than documented.</para>
/// </remarks>
public sealed class UpgradeTests : IDisposable
{
    private readonly string _root = Path.Combine(
        Path.GetTempPath(), "aide-upgrade", Guid.NewGuid().ToString("N"));

    public UpgradeTests() => Directory.CreateDirectory(_root);

    private string StorePath
    {
        get
        {
            var path = Path.Combine(_root, "workspace.db");
            if (!File.Exists(path))
            {
                File.WriteAllText(path, "ORIGINAL STORE");
            }

            return path;
        }
    }

    private string JournalPath => Path.Combine(_root, "migration.journal");

    // ---- the journal, which is what makes a crash recoverable ----------------

    [Fact]
    public void ANewJournal_HasNothingToRecover()
    {
        Assert.Null(new MigrationJournal(JournalPath).Read());
    }

    [Fact]
    public void ABegunMigration_IsReadableAfterAProcessRestart()
    {
        // "After a restart" is the whole point: an in-memory flag would be gone precisely when it is
        // needed. A second MigrationJournal over the same path IS the next process.
        new MigrationJournal(JournalPath).Begin("mig-1", 3, 4, "snapshot.db");

        var recovered = new MigrationJournal(JournalPath).Read();

        Assert.NotNull(recovered);
        Assert.Equal("mig-1", recovered!.MigrationId);
        Assert.Equal(3, recovered.FromSchema);
        Assert.Equal(4, recovered.ToSchema);
        Assert.Equal(MigrationState.Started, recovered.State);
    }

    [Fact]
    public void ACompletedMigration_IsRecordedAsCompleted()
    {
        var journal = new MigrationJournal(JournalPath);
        journal.Begin("mig-1", 3, 4, "snapshot.db");

        journal.Complete();

        Assert.Equal(MigrationState.Completed, new MigrationJournal(JournalPath).Read()!.State);
    }

    [Fact]
    public void AJournalWrittenTwice_KeepsOnlyTheLatestState()
    {
        // The journal answers one question — "is a migration in flight?" — and an append-only file
        // would make that question a parse rather than a read.
        var journal = new MigrationJournal(JournalPath);
        journal.Begin("mig-1", 3, 4, "snapshot.db");
        journal.Complete();
        journal.Begin("mig-2", 4, 5, "snapshot-2.db");

        var current = new MigrationJournal(JournalPath).Read();

        Assert.Equal("mig-2", current!.MigrationId);
        Assert.Equal(MigrationState.Started, current.State);
    }

    [Fact]
    public void ATornJournal_ReadsAsNothingInFlight_RatherThanThrowing()
    {
        // A journal is written by a process that can be killed at any instant. If a half-written
        // file threw on read, the recovery path — the one thing that must work after a crash —
        // would be the thing that crashed.
        File.WriteAllText(JournalPath, "{\"migrationId\": \"mig-1\", \"fromSch");

        var thrown = Record.Exception(() => new MigrationJournal(JournalPath).Read());

        Assert.Null(thrown);
        Assert.Null(new MigrationJournal(JournalPath).Read());
    }

    [Fact]
    public async Task AJournalBeingRewritten_IsNeverObservedHalfWritten()
    {
        // The journal is replaced by writing a temporary file and renaming it, and this is the only
        // way that choice is observable: a rename is atomic, so a reader sees the old record or the
        // new one. Writing in place truncates first, leaving a window in which a reader — the
        // recovery path, after a crash — sees an empty or partial file and concludes nothing was in
        // flight.
        //
        // Mutation proved this needed a test: switching to an in-place write failed nothing.
        // Probabilistic by nature, so the loop is long enough that the window is hit if it exists.
        var journal = new MigrationJournal(JournalPath);
        journal.Begin("mig-0", 1, 2, "snapshot.db");

        var torn = 0;
        using var stop = new CancellationTokenSource(TimeSpan.FromSeconds(3));

        var writer = Task.Run(() =>
        {
            var n = 0;
            while (!stop.IsCancellationRequested)
            {
                journal.Begin($"mig-{n++}", 1, 2, "snapshot.db");
            }
        });

        while (!stop.IsCancellationRequested)
        {
            if (new MigrationJournal(JournalPath).Read() is null)
            {
                Interlocked.Increment(ref torn);
                break;
            }
        }

        await writer.WaitAsync(TimeSpan.FromSeconds(10));

        Assert.Equal(0, torn);
    }

    // ---- snapshot and restore ------------------------------------------------

    [Fact]
    public void ASnapshot_CapturesTheStoreBeforeAnythingChanges()
    {
        var snapshot = StoreSnapshot.Capture(StorePath, _root);

        File.WriteAllText(StorePath, "MIGRATED STORE");
        StoreSnapshot.Restore(snapshot, StorePath);

        Assert.Equal("ORIGINAL STORE", File.ReadAllText(StorePath));
    }

    [Fact]
    public void ASnapshot_IsNotTheStoreItself()
    {
        // Snapshotting by renaming would leave a window with no store at all, which is the one state
        // a crash must never find.
        var snapshot = StoreSnapshot.Capture(StorePath, _root);

        Assert.True(File.Exists(StorePath), "the store was moved rather than copied");
        Assert.True(File.Exists(snapshot));
        Assert.NotEqual(Path.GetFullPath(StorePath), Path.GetFullPath(snapshot));
    }

    // ---- the health gate -----------------------------------------------------

    [Fact]
    public void AGate_PassesWhenEveryCheckPasses()
    {
        var result = new HealthGate(TimeSpan.FromSeconds(60)).Run(
        [
            new("schema", () => HealthCheck.Pass("schema", "v4")),
            new("integrity", () => HealthCheck.Pass("integrity", "sampled 100 rows")),
        ]);

        Assert.True(result.Passed);
        Assert.Equal(2, result.Checks.Count);
    }

    [Fact]
    public void AGate_StopsAtTheFirstFailure()
    {
        // Later checks assume earlier ones held. Running them anyway produces a cascade of failures
        // whose first entry is the only real one, and the report becomes something to sift.
        var ran = 0;

        var result = new HealthGate(TimeSpan.FromSeconds(60)).Run(
        [
            new("schema", () => HealthCheck.Fail("schema", "expected v4, found v3")),
            new("integrity", () => { ran++; return HealthCheck.Pass("integrity", ""); }),
        ]);

        Assert.False(result.Passed);
        Assert.Equal(0, ran);
        Assert.Equal("schema", result.Checks[^1].Name);
    }

    [Fact]
    public void AGate_FailsWhenItRunsOutOfBudget()
    {
        // The budget is the control that keeps the slow check out of the fast gate. A gate that
        // merely documented its budget would pass a replay that took fifteen minutes, which is the
        // contradiction the v1 architecture review caught.
        var result = new HealthGate(TimeSpan.FromMilliseconds(150)).Run(
        [
            new("slow", () => { Thread.Sleep(400); return HealthCheck.Pass("slow", ""); }),
            new("never-reached", () => HealthCheck.Pass("never-reached", "")),
        ]);

        Assert.False(result.Passed);
        Assert.Contains(result.Checks, c => c.Name == "budget" && !c.Passed);
        Assert.DoesNotContain(result.Checks, c => c.Name == "never-reached");
    }

    [Fact]
    public void AGate_ReportsWhatItActuallyRan()
    {
        // A gate's green result is evidence the gate passed, not that its contents passed — unless
        // it says what it ran. Naming the checks is what makes the difference inspectable.
        var result = new HealthGate(TimeSpan.FromSeconds(60)).Run(
        [
            new("schema", () => HealthCheck.Pass("schema", "v4")),
        ]);

        Assert.Equal(["schema"], result.Checks.Select(c => c.Name));
        Assert.True(result.Duration >= TimeSpan.Zero);
    }

    // ---- P2-UPGRADE-01: the happy path repoints ------------------------------

    [Fact]
    public void AnUpgradeThatPassesItsGate_KeepsTheMigratedStoreAndClearsTheJournal()
    {
        var coordinator = new UpgradeCoordinator(StorePath, _root);

        var result = coordinator.Run(
            "mig-1", fromSchema: 3, toSchema: 4,
            migrate: () => File.WriteAllText(StorePath, "MIGRATED STORE"),
            gate: () => new HealthGate(TimeSpan.FromSeconds(60)).Run(
                [new("schema", () => HealthCheck.Pass("schema", "v4"))]));

        Assert.True(result.Upgraded);
        Assert.Equal("MIGRATED STORE", File.ReadAllText(StorePath));
        Assert.Equal(MigrationState.Completed, new MigrationJournal(JournalPath).Read()!.State);
    }

    [Fact]
    public void AfterASuccessfulUpgrade_TheSnapshotIsNotLeftBehind()
    {
        // A store-sized file per upgrade, kept forever, is a disk leak with a plausible excuse.
        var coordinator = new UpgradeCoordinator(StorePath, _root);

        var result = coordinator.Run(
            "mig-1", 3, 4,
            migrate: () => File.WriteAllText(StorePath, "MIGRATED STORE"),
            gate: () => new HealthGate(TimeSpan.FromSeconds(60)).Run([]));

        Assert.True(result.Upgraded);
        Assert.False(File.Exists(result.SnapshotPath), "the pre-migration snapshot was left on disk");
    }

    // ---- P2-UPGRADE-02: a failed gate rolls back -----------------------------

    [Fact]
    public void AnUpgradeWhoseGateFails_RestoresThePreMigrationStore()
    {
        // The migration ran and changed the file. Rollback is not "do not migrate" — it is "undo a
        // migration that already happened", which is why the snapshot is taken first.
        var coordinator = new UpgradeCoordinator(StorePath, _root);

        var result = coordinator.Run(
            "mig-1", 3, 4,
            migrate: () => File.WriteAllText(StorePath, "MIGRATED STORE"),
            gate: () => new HealthGate(TimeSpan.FromSeconds(60)).Run(
                [new("schema", () => HealthCheck.Fail("schema", "expected v4, found v3"))]));

        Assert.False(result.Upgraded);
        Assert.Equal("ORIGINAL STORE", File.ReadAllText(StorePath));
        Assert.Equal(MigrationState.RolledBack, new MigrationJournal(JournalPath).Read()!.State);
    }

    [Fact]
    public void AFailedUpgrade_ReportsWhichCheckFailed()
    {
        // "The upgrade failed" is not actionable. Which gate check failed, and what it saw, is.
        var coordinator = new UpgradeCoordinator(StorePath, _root);

        var result = coordinator.Run(
            "mig-1", 3, 4,
            migrate: () => File.WriteAllText(StorePath, "MIGRATED STORE"),
            gate: () => new HealthGate(TimeSpan.FromSeconds(60)).Run(
                [new("integrity", () => HealthCheck.Fail("integrity", "3 orphaned rows"))]));

        Assert.False(result.Upgraded);
        Assert.Contains(result.Gate!.Checks, c => c.Name == "integrity" && !c.Passed);
        Assert.Contains("orphaned", result.Gate.Checks[^1].Detail, StringComparison.Ordinal);
    }

    [Fact]
    public void AMigrationThatThrows_RollsBackRatherThanLeavingAHalfMigratedStore()
    {
        // A migration that dies partway is the case the snapshot exists for. Leaving the store as
        // the exception found it would be the "unopenable workspace" outcome.
        var coordinator = new UpgradeCoordinator(StorePath, _root);

        var result = coordinator.Run(
            "mig-1", 3, 4,
            migrate: () =>
            {
                File.WriteAllText(StorePath, "HALF MIGRATED");
                throw new InvalidOperationException("migration step 2 failed");
            },
            gate: () => new HealthGate(TimeSpan.FromSeconds(60)).Run([]));

        Assert.False(result.Upgraded);
        Assert.Equal("ORIGINAL STORE", File.ReadAllText(StorePath));
        Assert.Contains("migration step 2 failed", result.Failure!, StringComparison.Ordinal);
    }

    [Fact]
    public void RollbackWorks_WhenTheStoreLivesOutsideTheWorkDirectory()
    {
        // The store and the upgrade's scratch space are independent by design. An earlier revision
        // derived the store's location from the snapshot's filename and passed only because this
        // fixture happened to put them in the same folder — restoring to a path that is not the
        // store is a rollback that silently does nothing.
        var storeDirectory = Path.Combine(_root, "store");
        var workDirectory = Path.Combine(_root, "upgrade-work");
        Directory.CreateDirectory(storeDirectory);

        var store = Path.Combine(storeDirectory, "workspace.db");
        File.WriteAllText(store, "ORIGINAL STORE");

        var result = new UpgradeCoordinator(store, workDirectory).Run(
            "mig-1", 3, 4,
            migrate: () => File.WriteAllText(store, "MIGRATED STORE"),
            gate: () => new HealthGate(TimeSpan.FromSeconds(60)).Run(
                [new("schema", () => HealthCheck.Fail("schema", "wrong version"))]));

        Assert.False(result.Upgraded);
        Assert.Equal("ORIGINAL STORE", File.ReadAllText(store));
    }

    // ---- P2-UPGRADE-03: power loss mid-migration -----------------------------

    [Fact]
    public void AnIncompleteMigrationFoundAtStartup_IsRolledBackAutomatically()
    {
        // The power-loss case. Nothing gets to run cleanup at the moment of failure, so recovery has
        // to be something the NEXT start does from what is on disk.
        var snapshot = StoreSnapshot.Capture(StorePath, _root);
        new MigrationJournal(JournalPath).Begin("mig-1", 3, 4, snapshot);
        File.WriteAllText(StorePath, "HALF MIGRATED");

        var recovery = UpgradeCoordinator.RecoverIfIncomplete(StorePath, _root);

        Assert.True(recovery.Recovered);
        Assert.Equal("ORIGINAL STORE", File.ReadAllText(StorePath));
        Assert.Equal(MigrationState.RolledBack, new MigrationJournal(JournalPath).Read()!.State);
    }

    [Fact]
    public void ACompletedMigrationFoundAtStartup_IsLeftAlone()
    {
        // Restoring here would undo a successful upgrade on every subsequent start — a rollback loop
        // that looks like the product refusing to stay upgraded.
        var snapshot = StoreSnapshot.Capture(StorePath, _root);
        var journal = new MigrationJournal(JournalPath);
        journal.Begin("mig-1", 3, 4, snapshot);
        File.WriteAllText(StorePath, "MIGRATED STORE");
        journal.Complete();

        var recovery = UpgradeCoordinator.RecoverIfIncomplete(StorePath, _root);

        Assert.False(recovery.Recovered);
        Assert.Equal("MIGRATED STORE", File.ReadAllText(StorePath));
    }

    [Fact]
    public void NoJournalAtStartup_IsTheOrdinaryCase()
    {
        var recovery = UpgradeCoordinator.RecoverIfIncomplete(StorePath, _root);

        Assert.False(recovery.Recovered);
        Assert.Equal("ORIGINAL STORE", File.ReadAllText(StorePath));
    }

    [Fact]
    public void AnIncompleteMigrationWhoseSnapshotIsGone_IsReportedRatherThanGuessedAt()
    {
        // Without the snapshot there is nothing to restore. Reporting beats pretending: a silent
        // "recovered" here would leave a half-migrated store the product then treats as healthy.
        new MigrationJournal(JournalPath).Begin("mig-1", 3, 4, Path.Combine(_root, "missing.db"));
        File.WriteAllText(StorePath, "HALF MIGRATED");

        var recovery = UpgradeCoordinator.RecoverIfIncomplete(StorePath, _root);

        Assert.False(recovery.Recovered);
        Assert.NotNull(recovery.Failure);
        Assert.Contains("snapshot", recovery.Failure!, StringComparison.OrdinalIgnoreCase);
    }

    public void Dispose()
    {
        try
        {
            Directory.Delete(_root, recursive: true);
        }
        catch (IOException)
        {
        }
    }
}
