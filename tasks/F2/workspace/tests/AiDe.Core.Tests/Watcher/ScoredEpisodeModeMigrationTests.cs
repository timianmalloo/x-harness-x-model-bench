using AiDe.Core.Watcher;
using Microsoft.Data.Sqlite;

namespace AiDe.Core.Tests.Watcher;

/// <summary>
/// The <c>mode</c> cohort column: an expand-only migration of <c>scored_episode_cell</c>, proven
/// against a hand-written PRE-MIGRATION (v5) database.
/// </summary>
/// <remarks>
/// <para><b>Why a fixture database and not a fresh one.</b> A migration tested only against a
/// database the same code just created proves the DDL parses. The failure worth catching is the one
/// that only an <i>existing</i> database can show: a rewritten row, a lost score, a column added
/// with a default that quietly invents history. So the v5 shape below is written by hand — it is the
/// oracle, not a snapshot of the thing under test.</para>
///
/// <para><b>Why NULL is the right value for a legacy row, and a backfill is not.</b> <c>mode</c>
/// records which door an episode came through. A row written before the column existed came through
/// a door nobody recorded. Inferring "observed" from the absence of a session record would be a
/// guess dressed as data — and it would be wrong for exactly the rows a cohort comparison cares
/// about, because it would put every unrecorded episode into one confident bucket. NULL means "not
/// recorded", which is true.</para>
///
/// <para><b>Why <c>mode</c> is not a <see cref="ScoreSegment"/> member.</b> The partition is
/// (workspace, task class, schema version) and a comparison never crosses it. Making mode a fourth
/// axis would split the same work into two cells — the exact thing R4 forbids — so it lives beside
/// the segment as an attribute of the cell, never inside the key.</para>
/// </remarks>
public sealed class ScoredEpisodeModeMigrationTests : IDisposable
{
    private readonly string _dir = Path.Combine(
        Path.GetTempPath(), "aide-mode-migration-" + Guid.NewGuid().ToString("n")[..8]);

    private string DbPath => Path.Combine(_dir, "watcher.db");

    public ScoredEpisodeModeMigrationTests() => Directory.CreateDirectory(_dir);

    public void Dispose()
    {
        SqliteConnection.ClearAllPools();
        try
        {
            Directory.Delete(_dir, recursive: true);
        }
        catch (IOException)
        {
            // A temp file still held open is not a test failure.
        }

        GC.SuppressFinalize(this);
    }

    /// <summary>
    /// The v5 shape of every table this test reads, written by hand from the schema as it shipped —
    /// <c>scored_episode_cell</c> ends at <c>workspace</c>, and there is no <c>mode</c>.
    /// </summary>
    private const string V5Schema =
        """
        CREATE TABLE watcher_schema_version (
            version    INTEGER NOT NULL PRIMARY KEY,
            applied_at TEXT    NOT NULL
        );
        CREATE TABLE scored_episode_cell (
            episode_id        TEXT    NOT NULL PRIMARY KEY,
            harness           TEXT    NULL,
            model             TEXT    NULL,
            operator_id       TEXT    NOT NULL,
            task_class        TEXT    NOT NULL,
            schema_version    TEXT    NOT NULL,
            verdict           TEXT    NOT NULL,
            headline          TEXT    NOT NULL,
            coverage_observed INTEGER NULL,
            coverage_required INTEGER NULL,
            evaluated_at      TEXT    NOT NULL,
            workspace         TEXT    NULL
        );
        CREATE INDEX ix_scored_episode_task ON scored_episode_cell (task_class, schema_version);
        CREATE TABLE score_dimension_cell (
            episode_id    TEXT    NOT NULL,
            dimension     TEXT    NOT NULL,
            weight        INTEGER NOT NULL,
            rubric        INTEGER NULL,
            earned_points REAL    NULL,
            posture       TEXT    NOT NULL,
            rationale     TEXT    NOT NULL,
            PRIMARY KEY (episode_id, dimension)
        );
        CREATE TABLE score_tripped_floor_cell (
            episode_id TEXT NOT NULL,
            floor      TEXT NOT NULL,
            PRIMARY KEY (episode_id, floor)
        );
        CREATE TABLE declared_artifact_fact (
            episode_id   TEXT    NOT NULL,
            path         TEXT    NOT NULL,
            declared_at  TEXT    NOT NULL,
            sequence     INTEGER NOT NULL,
            PRIMARY KEY (episode_id, path, sequence)
        );
        """;

    /// <summary>The columns a legacy row already had; every one must survive the migration unchanged.</summary>
    private const string LegacyColumns =
        "episode_id, harness, model, operator_id, task_class, schema_version, verdict, headline, "
        + "coverage_observed, coverage_required, evaluated_at, workspace";

    /// <summary>Writes the pre-migration database and returns its rows as they stood.</summary>
    private string WritePreMigrationFixture()
    {
        using var connection = new SqliteConnection(
            new SqliteConnectionStringBuilder { DataSource = DbPath, Mode = SqliteOpenMode.ReadWriteCreate, Pooling = false }.ToString());
        connection.Open();
        Execute(connection, V5Schema);

        for (var version = 1; version <= 5; version++)
        {
            Execute(connection, $"INSERT INTO watcher_schema_version (version, applied_at) VALUES ({version}, '2026-01-0{version}T00:00:00.0000000+00:00');");
        }

        Execute(
            connection,
            """
            INSERT INTO scored_episode_cell VALUES
                ('ep-legacy-1', 'copilot', 'gpt-5', 'session-a', 'audit-import', 'weave/1', 'Scored',
                 'Scored 62/100', 3, 4, '2026-02-01T10:00:00.0000000+00:00', 'C:/repos/app'),
                ('ep-legacy-2', NULL, NULL, 'session-b', 'audit-import', 'weave/1', 'NotScored',
                 'Not scored: no verification path', NULL, NULL, '2026-02-02T10:00:00.0000000+00:00', NULL);
            INSERT INTO score_dimension_cell VALUES
                ('ep-legacy-1', 'EvidenceDiscipline', 20, 3, 15.0, 'Advisory', 'declared and verified'),
                ('ep-legacy-1', 'SolutionEconomy', 15, 2, 7.5, 'Advisory', 'one rung skipped');
            INSERT INTO score_tripped_floor_cell VALUES ('ep-legacy-1', 'Correctness');
            """);

        return Dump(connection);
    }

    /// <summary>Every legacy column of every row, in a stable order — the byte-identical oracle.</summary>
    private static string Dump(SqliteConnection connection)
    {
        using var command = connection.CreateCommand();
        command.CommandText = $"SELECT {LegacyColumns} FROM scored_episode_cell ORDER BY episode_id;";
        using var reader = command.ExecuteReader();

        var rows = new List<string>();
        while (reader.Read())
        {
            var fields = new List<string>();
            for (var i = 0; i < reader.FieldCount; i++)
            {
                fields.Add(reader.IsDBNull(i) ? "<null>" : reader.GetValue(i).ToString() ?? "<null>");
            }

            rows.Add(string.Join('\u001f', fields));
        }

        return string.Join('\n', rows);
    }

    private static void Execute(SqliteConnection connection, string sql)
    {
        using var command = connection.CreateCommand();
        command.CommandText = sql;
        command.ExecuteNonQuery();
    }

    private static T Read<T>(string path, Func<SqliteConnection, T> read)
    {
        using var connection = new SqliteConnection(
            new SqliteConnectionStringBuilder { DataSource = path, Mode = SqliteOpenMode.ReadOnly, Pooling = false }.ToString());
        connection.Open();
        return read(connection);
    }

    /// <summary>The clause: legacy rows read NULL, and nothing else about them moved.</summary>
    [Fact]
    public void LegacyRowsReadNullAfterTheMigrationAndTheirScoresAreByteIdentical()
    {
        var before = WritePreMigrationFixture();

        using (var store = SqliteWatcherObservationStore.Open(DbPath))
        {
            Assert.Null(store.FindEpisodeMode("ep-legacy-1"));
            Assert.Null(store.FindEpisodeMode("ep-legacy-2"));
        }

        var after = Read(DbPath, Dump);
        Assert.Equal(before, after);
        Assert.Equal(2, Read(DbPath, c => Convert.ToInt64(Scalar(c, "SELECT count(*) FROM scored_episode_cell;"))));
    }

    /// <summary>The column exists, is nullable, and is declared in migration order (after workspace, before v7's task_class_source) so a fresh database matches a migrated one.</summary>
    [Fact]
    public void TheModeColumnIsAddedNullableAndLast()
    {
        WritePreMigrationFixture();
        using (SqliteWatcherObservationStore.Open(DbPath))
        {
        }

        var (notNull, defaultValue, position, count) = Read(DbPath, connection =>
        {
            using var command = connection.CreateCommand();
            command.CommandText = "SELECT \"notnull\", ifnull(dflt_value, '<none>'), cid, (SELECT count(*) FROM pragma_table_info('scored_episode_cell')) FROM pragma_table_info('scored_episode_cell') WHERE name = 'mode';";
            using var reader = command.ExecuteReader();
            Assert.True(reader.Read(), "scored_episode_cell has no 'mode' column after migration");
            return (reader.GetInt64(0), reader.GetString(1), reader.GetInt64(2), reader.GetInt64(3));
        });

        Assert.Equal(0, notNull);
        Assert.Equal("<none>", defaultValue);

        // Second-to-last since v7 appended `task_class_source` after it (CV-2; ADR-0028's amendment):
        // every expand-only column is declared after the one before it, so a fresh database and a
        // migrated one still agree — the property the position asserts.
        Assert.Equal(count - 2, position);
    }

    /// <summary>
    /// A fresh database and a migrated one have the same schema text — the property the v4 column was
    /// declared last to preserve, now asserted for v6 as well.
    /// </summary>
    [Fact]
    public void AFreshDatabaseAndAMigratedOneAgreeOnScoredEpisodeCell()
    {
        WritePreMigrationFixture();
        using (SqliteWatcherObservationStore.Open(DbPath))
        {
        }

        var freshPath = Path.Combine(_dir, "fresh.db");
        using (SqliteWatcherObservationStore.Open(freshPath))
        {
        }

        static string Sql(SqliteConnection c) =>
            (string)Scalar(c, "SELECT sql FROM sqlite_master WHERE type='table' AND name='scored_episode_cell';")!;

        Assert.Equal(
            Read(freshPath, c => string.Join(',', ColumnNames(c))),
            Read(DbPath, c => string.Join(',', ColumnNames(c))));
        Assert.Contains("mode", Read(freshPath, Sql), StringComparison.Ordinal);
    }

    /// <summary>A recorded mode survives a re-score: <c>RecordScorecard</c> does not clear the cohort.</summary>
    [Fact]
    public void ARecordedModeIsReadBackAndSurvivesARescore()
    {
        WritePreMigrationFixture();
        using var store = SqliteWatcherObservationStore.Open(DbPath);

        store.RecordEpisodeMode("ep-legacy-1", "governed");
        Assert.Equal("governed", store.FindEpisodeMode("ep-legacy-1"));

        var scored = store.FindScoredEpisode("ep-legacy-1")!;
        store.RecordScorecard(scored);

        Assert.Equal("governed", store.FindEpisodeMode("ep-legacy-1"));
        Assert.Null(store.FindEpisodeMode("ep-legacy-2"));
    }

    /// <summary>Stamping a mode on an episode that has no scorecard changes nothing and says so.</summary>
    [Fact]
    public void StampingAModeOnAnUnscoredEpisodeRecordsNothing()
    {
        WritePreMigrationFixture();
        using var store = SqliteWatcherObservationStore.Open(DbPath);

        Assert.False(store.RecordEpisodeMode("ep-never-scored", "governed"));
        Assert.Null(store.FindEpisodeMode("ep-never-scored"));
    }

    /// <summary>
    /// <c>mode</c> is not a partition axis. The negative check does not stand alone — the positive
    /// one-cell-two-cohorts proof is N5's — but a fourth segment member would be caught here first.
    /// </summary>
    [Fact]
    public void ModeIsNotAScoreSegmentMember()
        => Assert.Equal(
            new[] { "SchemaVersion", "TaskClass", "Workspace" },
            typeof(ScoreSegment).GetConstructors()[0].GetParameters().Select(p => p.Name).Order(StringComparer.Ordinal));

    private static object? Scalar(SqliteConnection connection, string sql)
    {
        using var command = connection.CreateCommand();
        command.CommandText = sql;
        return command.ExecuteScalar();
    }

    private static IReadOnlyList<string> ColumnNames(SqliteConnection connection)
    {
        using var command = connection.CreateCommand();
        command.CommandText = "SELECT name FROM pragma_table_info('scored_episode_cell') ORDER BY cid;";
        using var reader = command.ExecuteReader();
        var names = new List<string>();
        while (reader.Read())
        {
            names.Add(reader.GetString(0));
        }

        return names;
    }
}
