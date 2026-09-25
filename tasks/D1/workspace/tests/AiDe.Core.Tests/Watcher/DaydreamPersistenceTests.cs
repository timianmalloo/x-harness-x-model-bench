using AiDe.Core.Watcher;
using Microsoft.Data.Sqlite;

namespace AiDe.Core.Tests.Watcher;

/// <summary>
/// D2 — Daydream observations survive a restart, and an existing database gains the table.
/// </summary>
/// <remarks>
/// <para><b>What P0 found.</b> <c>EnsureSchema</c> returned early whenever
/// <c>watcher_schema_version</c> existed, so <c>SchemaSql</c> only ever ran against a <b>fresh</b>
/// database. There was no migration path at all. Adding a table would have given it to new
/// workspaces and to no existing one, and the failure would have surfaced as "no such table" at the
/// first read — in whichever workspace had been open longest, which is the one with the most
/// history to observe.</para>
///
/// <para>Found by reading the method rather than trusting that a table named
/// <c>watcher_schema_version</c> implied a version was being checked. It stored one and compared
/// nothing.</para>
///
/// <para><b>THESE TABLES ARE NO LONGER THE DAYDREAM RECORD.</b> The owner's decision on 2026-09-02
/// put the record in the repository (<c>docs/daydream/*.jsonl</c>, see
/// <c>DaydreamRepositoryRecordTests</c> and <c>design-watcher-daydream-dream-seam</c> §4a), and
/// nothing reads <c>daydream_observation_fact</c> or <c>daydream_event_fact</c> any more — two
/// definitions of one quantity is a defect signature (DM7), so there is deliberately no parallel
/// copy.</para>
///
/// <para><b>Why the tests stay.</b> Schema version 3 shipped, so an installed store may already be
/// at it; rolling the version back would make a user's database newer than the code that reads it.
/// The migration must therefore remain correct on upgrade, and these tests are what keeps it so.
/// They prove the MIGRATION PATH, which is still live — not that the tables are authoritative,
/// which they are not. Written here so the next reader does not conclude from a tested schema that
/// the store is the record.</para>
/// </remarks>
public sealed class DaydreamPersistenceTests : IDisposable
{
    private readonly string _dir = Path.Combine(
        Path.GetTempPath(), "aide-daydream-" + Guid.NewGuid().ToString("n")[..8]);

    private string DbPath => Path.Combine(_dir, "watcher.db");

    public DaydreamPersistenceTests() => Directory.CreateDirectory(_dir);

    public void Dispose()
    {
        SqliteConnection.ClearAllPools();
        try { Directory.Delete(_dir, recursive: true); } catch (IOException) { /* best effort */ }
    }

    private static DaydreamObservation Observation(string id, string episodeId, int minute = 0) => new(
        id,
        new DaydreamSignature("implement", ScoreSchema.Weave1Version, WeaveVerdict.Blocked,
            "Correctness", "OutcomeIntegrity:1"),
        episodeId,
        DateTimeOffset.UnixEpoch.AddMinutes(minute));

    [Fact]
    public void AnObservationSurvivesAReopen()
    {
        using (var store = SqliteWatcherObservationStore.Open(DbPath))
        {
            store.AppendDaydreamObservation(Observation("obs-1", "ep-1"));
        }

        using var reopened = SqliteWatcherObservationStore.Open(DbPath);
        var observation = Assert.Single(reopened.AllDaydreamObservations());

        Assert.Equal("obs-1", observation.ObservationId);
        Assert.Equal("ep-1", observation.EpisodeId);
        Assert.Equal(WeaveVerdict.Blocked, observation.Signature.Verdict);
        Assert.Equal("Correctness", observation.Signature.Floors);
        Assert.Equal("OutcomeIntegrity:1", observation.Signature.Shortfalls);
        Assert.Equal(DateTimeOffset.UnixEpoch, observation.ObservedAt);
    }

    /// <summary>
    /// Two observations of one episode are two rows.
    /// </summary>
    /// <remarks>
    /// The store must not deduplicate. Deduplication is the recurrence fold's job on <b>read</b>, and
    /// doing it here would destroy the evidence that the fold needs to do it — a re-observation would
    /// be indistinguishable from never having happened, and "how many times" would have two
    /// definitions in two places.
    /// </remarks>
    [Fact]
    public void TheStoreKeepsBothObservationsOfOneEpisode()
    {
        using var store = SqliteWatcherObservationStore.Open(DbPath);

        store.AppendDaydreamObservation(Observation("obs-1", "ep-1"));
        store.AppendDaydreamObservation(Observation("obs-2", "ep-1", minute: 5));

        Assert.Equal(2, store.AllDaydreamObservations().Count);

        // …and the fold still reports one occurrence, which is the point of keeping both.
        Assert.Empty(new RecurrenceDetector().Recurring(store.AllDaydreamObservations()));
    }

    /// <summary>The read order is deterministic, so a replay produces the same sequence.</summary>
    [Fact]
    public void ObservationsReadBackInADeterministicOrder()
    {
        using var store = SqliteWatcherObservationStore.Open(DbPath);

        store.AppendDaydreamObservation(Observation("obs-c", "ep-3", minute: 2));
        store.AppendDaydreamObservation(Observation("obs-a", "ep-1", minute: 0));
        store.AppendDaydreamObservation(Observation("obs-b", "ep-2", minute: 1));

        Assert.Equal(
            ["obs-a", "obs-b", "obs-c"],
            store.AllDaydreamObservations().Select(o => o.ObservationId));
    }

    /// <summary>
    /// A database created before this table existed gains it on open.
    /// </summary>
    /// <remarks>
    /// The regression this whole slice nearly shipped. A v1 database is simulated exactly as one
    /// occurs in the wild — the table dropped and the version rewound — because a test that builds
    /// its "old" database by a different route proves the migration handles a shape nobody has.
    /// </remarks>
    [Fact]
    public void AnExistingDatabaseGainsTheTableOnOpen()
    {
        using (var fresh = SqliteWatcherObservationStore.Open(DbPath))
        {
            // A v1 store: no daydream table, version 1 recorded.
            using var connection = new SqliteConnection(
                new SqliteConnectionStringBuilder { DataSource = DbPath, Pooling = false }.ToString());
            connection.Open();
            using var command = connection.CreateCommand();
            command.CommandText =
                """
                DROP INDEX IF EXISTS ix_daydream_observation_episode;
                DROP TABLE IF EXISTS daydream_observation_fact;
                DELETE FROM watcher_schema_version;
                INSERT INTO watcher_schema_version (version, applied_at) VALUES (1, '2026-01-01T00:00:00Z');
                """;
            command.ExecuteNonQuery();
        }

        SqliteConnection.ClearAllPools();

        using var migrated = SqliteWatcherObservationStore.Open(DbPath);
        migrated.AppendDaydreamObservation(Observation("obs-1", "ep-1"));

        Assert.Single(migrated.AllDaydreamObservations());
    }

    /// <summary>
    /// Re-opening an already-migrated database applies nothing.
    /// </summary>
    /// <remarks>
    /// A migration that re-ran would throw on the second open ("table already exists"), which would
    /// turn every restart after the first into a failure to open the workspace at all.
    /// </remarks>
    [Fact]
    public void ReopeningAMigratedDatabaseIsANoOp()
    {
        using (var first = SqliteWatcherObservationStore.Open(DbPath))
        {
            first.AppendDaydreamObservation(Observation("obs-1", "ep-1"));
        }

        SqliteConnection.ClearAllPools();

        using var second = SqliteWatcherObservationStore.Open(DbPath);
        using var third = SqliteWatcherObservationStore.Open(DbPath);

        Assert.Single(third.AllDaydreamObservations());
    }

    /// <summary>
    /// A fresh database and a migrated one end up with the same schema.
    /// </summary>
    /// <remarks>
    /// The DDL exists twice — in <c>SchemaSql</c> for a new database and in <c>Migrations</c> for an
    /// existing one — which is two definitions of one schema, the shape that drifts. This compares
    /// them rather than trusting that whoever adds the next table remembers both. It is the same
    /// derived-view discipline the docs index gets, applied to a schema.
    /// </remarks>
    [Fact]
    public void AFreshDatabaseAndAMigratedOneHaveTheSameSchema()
    {
        var migratedPath = Path.Combine(_dir, "migrated.db");

        using (var seed = SqliteWatcherObservationStore.Open(migratedPath))
        {
            using var connection = new SqliteConnection(
                new SqliteConnectionStringBuilder { DataSource = migratedPath, Pooling = false }.ToString());
            connection.Open();
            using var command = connection.CreateCommand();
            command.CommandText =
                """
                DROP INDEX IF EXISTS ix_daydream_observation_episode;
                DROP TABLE IF EXISTS daydream_observation_fact;
                DELETE FROM watcher_schema_version;
                INSERT INTO watcher_schema_version (version, applied_at) VALUES (1, '2026-01-01T00:00:00Z');
                """;
            command.ExecuteNonQuery();
        }

        SqliteConnection.ClearAllPools();

        using (var _ = SqliteWatcherObservationStore.Open(migratedPath)) { }
        using (var _ = SqliteWatcherObservationStore.Open(DbPath)) { }

        SqliteConnection.ClearAllPools();

        Assert.Equal(SchemaOf(DbPath), SchemaOf(migratedPath));
    }

    private static IReadOnlyList<string> SchemaOf(string path)
    {
        using var connection = new SqliteConnection(
            new SqliteConnectionStringBuilder { DataSource = path, Pooling = false }.ToString());
        connection.Open();
        using var command = connection.CreateCommand();
        command.CommandText =
            """
            SELECT type || ' ' || name || ' ' || coalesce(sql, '')
            FROM sqlite_master
            WHERE name NOT LIKE 'sqlite_%'
            ORDER BY type, name;
            """;

        var rows = new List<string>();
        using var reader = command.ExecuteReader();
        while (reader.Read())
        {
            // Whitespace differs between the inline schema and the migration DDL; the shape does not.
            rows.Add(string.Join(' ', reader.GetString(0).Split(
                [' ', '\t', '\r', '\n'], StringSplitOptions.RemoveEmptyEntries)));
        }

        return rows;
    }
}
