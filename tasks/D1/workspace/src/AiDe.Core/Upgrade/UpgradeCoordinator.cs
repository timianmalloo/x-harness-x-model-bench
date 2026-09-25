using System.Diagnostics;

namespace AiDe.Core.Upgrade;

/// <summary>Copies the store aside so a migration can be undone.</summary>
/// <remarks>
/// <b>Copied, never moved.</b> Renaming the store into place as a snapshot would leave a window in
/// which no store exists at all — which is the one state a crash must never find, and the exact
/// instant this whole mechanism is defending.
/// </remarks>
public static class StoreSnapshot
{
    /// <summary>Copies <paramref name="storePath"/> into <paramref name="directory"/>.</summary>
    public static string Capture(string storePath, string directory)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(storePath);
        ArgumentException.ThrowIfNullOrWhiteSpace(directory);

        Directory.CreateDirectory(directory);

        var snapshot = Path.Combine(
            directory, $"{Path.GetFileNameWithoutExtension(storePath)}.pre-migration.db");

        File.Copy(storePath, snapshot, overwrite: true);
        return snapshot;
    }

    /// <summary>Puts a snapshot back.</summary>
    public static void Restore(string snapshotPath, string storePath) =>
        File.Copy(snapshotPath, storePath, overwrite: true);
}

/// <summary>What an upgrade attempt did.</summary>
public sealed record UpgradeResult(
    bool Upgraded,
    string SnapshotPath,
    HealthGateResult? Gate,
    string? Failure);

/// <summary>What a startup recovery found.</summary>
public sealed record RecoveryResult(bool Recovered, string? Failure);

/// <summary>
/// The upgrade choreography: snapshot, migrate, gate, and either keep it or put it back.
/// </summary>
/// <remarks>
/// <para><b>The ordering is the design.</b> An upgrade that fails halfway is worse than one that
/// never started: a store migrated to a schema the running binary cannot read is a workspace nobody
/// can open, with the user's evidence inside it. So the snapshot is taken before anything changes,
/// the journal is written before the migration runs, and the point of no return — deleting the
/// snapshot — comes only after the gate has passed.</para>
///
/// <para><b>Rollback is not "do not migrate".</b> It is "undo a migration that already happened",
/// which is why a snapshot exists at all rather than a decision to proceed.</para>
///
/// <para><b>Recovery is a separate entry point</b> (<see cref="RecoverIfIncomplete"/>) because the
/// case it handles is the one where this class never got to finish. Nothing in the failure path can
/// be relied on to run at the moment of a power loss, so the next start reads the journal and
/// completes the sentence.</para>
/// </remarks>
public sealed class UpgradeCoordinator(string storePath, string workDirectory)
{
    private static readonly ActivitySource Telemetry = new("aide.upgrade.gate");

    private static string JournalPathFor(string workDirectory) =>
        Path.Combine(workDirectory, "migration.journal");

    /// <summary>Runs one migration behind its gate.</summary>
    public UpgradeResult Run(
        string migrationId,
        int fromSchema,
        int toSchema,
        Action migrate,
        Func<HealthGateResult> gate)
    {
        ArgumentNullException.ThrowIfNull(migrate);
        ArgumentNullException.ThrowIfNull(gate);

        using var span = Telemetry.StartActivity("upgrade.run");
        span?.SetTag("migration.id", migrationId);
        span?.SetTag("schema.from", fromSchema);
        span?.SetTag("schema.to", toSchema);

        var journal = new MigrationJournal(JournalPathFor(workDirectory));

        // Snapshot first, journal second, migrate third. A journal written after the migration would
        // describe work already done, and a crash between them would leave a changed store nobody
        // knows to undo.
        var snapshot = StoreSnapshot.Capture(storePath, workDirectory);
        journal.Begin(migrationId, fromSchema, toSchema, snapshot);

        try
        {
            migrate();
        }
        catch (Exception ex)
        {
            // Any exception, deliberately: a migration is arbitrary code over the user's evidence,
            // and the set of ways it can fail is not knowable from here. Narrowing this would let
            // an unanticipated type leave a half-migrated store behind.
            Rollback(journal, snapshot, span, ex.Message);
            return new UpgradeResult(false, snapshot, null, ex.Message);
        }

        var result = gate();
        span?.SetTag("gate.duration_ms", result.Duration.TotalMilliseconds);
        span?.SetTag("gate.passed", result.Passed);

        if (!result.Passed)
        {
            var failed = result.Checks.LastOrDefault(c => !c.Passed);
            Rollback(journal, snapshot, span, failed?.Name ?? "gate");
            return new UpgradeResult(false, snapshot, result, failed?.Detail);
        }

        journal.Complete();

        // The point of no return, and it is last. Deleting the snapshot earlier would save a copy
        // and cost the ability to undo.
        Delete(snapshot);

        return new UpgradeResult(true, snapshot, result, null);
    }

    /// <summary>
    /// Undoes a migration that was interrupted before it could finish.
    /// </summary>
    /// <remarks>
    /// Called at startup, before the store is opened. A journal in
    /// <see cref="MigrationState.Started"/> means a process died between "about to migrate" and
    /// "migrated and verified" — so the store may be anything, and the only thing known to be good
    /// is the snapshot.
    /// </remarks>
    public static RecoveryResult RecoverIfIncomplete(string storePath, string workDirectory)
    {
        var journal = new MigrationJournal(JournalPathFor(workDirectory));
        var record = journal.Read();

        if (record is null || record.State != MigrationState.Started)
        {
            // Completed and RolledBack are both terminal. Restoring over a completed migration would
            // undo a successful upgrade on every subsequent start — a rollback loop that presents as
            // the product refusing to stay upgraded.
            return new RecoveryResult(false, null);
        }

        using var span = Telemetry.StartActivity("upgrade.recover");
        span?.SetTag("migration.id", record.MigrationId);

        if (!File.Exists(record.SnapshotPath))
        {
            // Reported, never guessed at. Without the snapshot there is nothing to restore, and a
            // silent "recovered" would hand the product a half-migrated store it then treats as
            // healthy.
            var failure =
                $"migration '{record.MigrationId}' was interrupted and its snapshot is missing "
                + $"({record.SnapshotPath}); the store cannot be restored automatically";
            span?.SetStatus(ActivityStatusCode.Error, failure);
            return new RecoveryResult(false, failure);
        }

        StoreSnapshot.Restore(record.SnapshotPath, storePath);
        journal.RolledBack();
        Delete(record.SnapshotPath);

        return new RecoveryResult(true, null);
    }

    /// <summary>Puts the pre-migration store back and records that we did.</summary>
    /// <remarks>
    /// An instance method using <c>storePath</c> directly. An earlier revision derived the store's
    /// location from the snapshot's filename, which worked only because the fixture happened to put
    /// the store inside the work directory — the two are independent by design, and a workspace
    /// whose store lives elsewhere would have had its snapshot restored to a path that is not the
    /// store.
    /// </remarks>
    private void Rollback(MigrationJournal journal, string snapshot, Activity? span, string reason)
    {
        span?.SetTag("upgrade.rolled_back", true);
        span?.SetTag("upgrade.reason", reason);

        StoreSnapshot.Restore(snapshot, storePath);
        journal.RolledBack();
        Delete(snapshot);
    }

    private static void Delete(string path)
    {
        try
        {
            File.Delete(path);
        }
        catch (IOException)
        {
            // A snapshot that cannot be deleted is disk to reclaim later, not a failed upgrade.
        }
    }
}
