using AiDe.Core.Watcher;
using Microsoft.Data.Sqlite;

namespace AiDe.Core.Tests.Watcher;

/// <summary>
/// The <c>task_class_source</c> cohort attribute (ADR-0033 rule 4; ADR-0028's amendment pointer):
/// an expand-only column on <c>scored_episode_cell</c>, v6 → v7, beside <c>mode</c> and never
/// inside <c>ScoreSegment</c> — proven against a hand-written PRE-MIGRATION (v6) database, with a
/// tested rollback (a v6-shaped reader over the v7 file), a legacy row that reads NULL, the stamp
/// that lands only on a scored cell, and the leaderboard's reader that tells a chosen
/// <c>free-form</c> from a defaulted one.
/// </summary>
/// <remarks>
/// <b>The plan row said v5 → v6.</b> The store was at v6 already (the <c>mode</c> column, ADR-0028)
/// when this slice opened, so the column is v7 — recorded, not silently renumbered.
/// </remarks>
public sealed class TaskClassSourceCohortColumnTests : IDisposable
{
    private readonly string _dir = Path.Combine(Path.GetTempPath(), "aide-tcs-migration-" + Guid.NewGuid().ToString("n")[..8]);

    private string DbPath => Path.Combine(_dir, "watcher.db");

    public TaskClassSourceCohortColumnTests() => Directory.CreateDirectory(_dir);

    public void Dispose()
    {
        SqliteConnection.ClearAllPools();
        try { Directory.Delete(_dir, recursive: true); } catch (IOException) { }
        GC.SuppressFinalize(this);
    }

    /// <summary>The v6 shape, by hand: <c>scored_episode_cell</c> ends at <c>mode</c>; there is no <c>task_class_source</c>.</summary>
    private const string V6Schema =
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
            workspace         TEXT    NULL,
            mode              TEXT    NULL
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

    /// <summary>The v6 reader's column list — what a rolled-back binary selects; every one must survive.</summary>
    private const string V6Columns =
        "episode_id, harness, model, operator_id, task_class, schema_version, verdict, headline, "
        + "coverage_observed, coverage_required, evaluated_at, workspace, mode";

    private string WritePreMigrationFixture()
    {
        using var connection = new SqliteConnection(new SqliteConnectionStringBuilder { DataSource = DbPath, Mode = SqliteOpenMode.ReadWriteCreate, Pooling = false }.ToString());
        connection.Open();
        Execute(connection, V6Schema);
        for (var version = 1; version <= 6; version++)
        {
            Execute(connection, $"INSERT INTO watcher_schema_version (version, applied_at) VALUES ({version}, '2026-01-0{version}T00:00:00.0000000+00:00');");
        }

        Execute(
            connection,
            """
            INSERT INTO scored_episode_cell VALUES
                ('ep-legacy-1', 'claude-code', 'sonnet', 'op-a', 'free-form', 'weave/1', 'Scored', 'Scored 62/100', 3, 4, '2026-02-01T10:00:00.0000000+00:00', 'C:/repos/app', 'governed'),
                ('ep-legacy-2', NULL, NULL, 'op-b', 'refactor', 'weave/1', 'NotScored', 'Not scored', NULL, NULL, '2026-02-02T10:00:00.0000000+00:00', NULL, NULL);
            INSERT INTO score_dimension_cell VALUES ('ep-legacy-1', 'EvidenceDiscipline', 20, 3, 15.0, 'Advisory', 'declared and verified');
            """);
        return Dump(connection, V6Columns);
    }

    private static string Dump(SqliteConnection connection, string columns)
    {
        using var command = connection.CreateCommand();
        command.CommandText = $"SELECT {columns} FROM scored_episode_cell ORDER BY episode_id;";
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
        using var connection = new SqliteConnection(new SqliteConnectionStringBuilder { DataSource = path, Mode = SqliteOpenMode.ReadOnly, Pooling = false }.ToString());
        connection.Open();
        return read(connection);
    }

    private static object? Scalar(SqliteConnection connection, string sql)
    {
        using var command = connection.CreateCommand();
        command.CommandText = sql;
        return command.ExecuteScalar();
    }

    [Fact]
    public void LegacyRowsReadNullAfterTheMigrationAndTheirV6ColumnsAreByteIdentical()
    {
        var before = WritePreMigrationFixture();

        using (var store = SqliteWatcherObservationStore.Open(DbPath))
        {
            Assert.Null(store.FindEpisodeTaskClassSource("ep-legacy-1"));
            Assert.Null(store.FindEpisodeTaskClassSource("ep-legacy-2"));
            Assert.Equal("governed", store.FindEpisodeMode("ep-legacy-1"));   // the neighbour column is untouched
        }

        SqliteConnection.ClearAllPools();
        Assert.Equal(before, Read(DbPath, c => Dump(c, V6Columns)));
        Assert.Equal(7L, Read(DbPath, c => Convert.ToInt64(Scalar(c, "SELECT max(version) FROM watcher_schema_version;"))));
    }

    /// <summary>The column is nullable, has no default that invents history, and is declared LAST so a fresh database matches a migrated one.</summary>
    [Fact]
    public void TheColumnIsAddedNullableWithoutADefaultAndLast()
    {
        WritePreMigrationFixture();
        using (SqliteWatcherObservationStore.Open(DbPath)) { }
        SqliteConnection.ClearAllPools();

        var (notNull, defaultValue, position, count) = Read(DbPath, connection =>
        {
            using var command = connection.CreateCommand();
            command.CommandText = "SELECT \"notnull\", dflt_value, cid, (SELECT count(*) FROM pragma_table_info('scored_episode_cell')) FROM pragma_table_info('scored_episode_cell') WHERE name = 'task_class_source';";
            using var reader = command.ExecuteReader();
            Assert.True(reader.Read(), "the column exists after the migration");
            return (reader.GetInt64(0), reader.IsDBNull(1) ? null : reader.GetString(1), reader.GetInt64(2), reader.GetInt64(3));
        });

        Assert.Equal(0L, notNull);
        Assert.Null(defaultValue);
        Assert.Equal(count - 1, position);
    }

    /// <summary>The tested rollback: a v6 binary's reader (its column list) reads the v7 file whole, and never truncates it.</summary>
    [Fact]
    public void AV6ShapedReaderReadsTheV7FileWhole()
    {
        WritePreMigrationFixture();
        using (var store = SqliteWatcherObservationStore.Open(DbPath))
        {
            Assert.True(store.RecordEpisodeTaskClassSource("ep-legacy-1", "operator"));
        }

        SqliteConnection.ClearAllPools();
        var rows = Read(DbPath, c => Dump(c, V6Columns));
        Assert.Contains("ep-legacy-1", rows, StringComparison.Ordinal);
        Assert.Contains("ep-legacy-2", rows, StringComparison.Ordinal);
        Assert.Equal("operator", Read(DbPath, c => (string?)Scalar(c, "SELECT task_class_source FROM scored_episode_cell WHERE episode_id = 'ep-legacy-1';")));
    }

    /// <summary>The stamp lands only on a scored cell (an UPDATE, never an upsert), reads back, and a re-score keeps it.</summary>
    [Fact]
    public void TheStampLandsOnlyOnAScoredCellAndSurvivesARescore()
    {
        WritePreMigrationFixture();
        using var store = SqliteWatcherObservationStore.Open(DbPath);

        Assert.False(store.RecordEpisodeTaskClassSource("ep-never-scored", "session-default"));
        Assert.Null(store.FindEpisodeTaskClassSource("ep-never-scored"));

        Assert.True(store.RecordEpisodeTaskClassSource("ep-legacy-1", "session-default"));
        Assert.Equal("session-default", store.FindEpisodeTaskClassSource("ep-legacy-1"));

        // A re-score replaces the cell's derived values and keeps the cohort stamp, exactly as `mode` is kept.
        var scored = store.FindScoredEpisode("ep-legacy-1")!;
        store.RecordScorecard(scored);
        Assert.Equal("session-default", store.FindEpisodeTaskClassSource("ep-legacy-1"));
        Assert.Equal("session-default", store.FindScoredEpisode("ep-legacy-1")!.TaskClassSource);

        Assert.Throws<ArgumentException>(() => store.RecordEpisodeTaskClassSource("ep-legacy-1", " "));

        // Idempotent, never a silent rewrite: the same value again succeeds; a different value is refused and the first stands.
        Assert.True(store.RecordEpisodeTaskClassSource("ep-legacy-1", "session-default"));
        Assert.False(store.RecordEpisodeTaskClassSource("ep-legacy-1", "operator"));
        Assert.Equal("session-default", store.FindEpisodeTaskClassSource("ep-legacy-1"));
    }

    /// <summary>The in-memory store mirrors the SQL store: a stamp needs a scored cell; the read returns null for "not recorded".</summary>
    [Fact]
    public void TheInMemoryStoreMirrorsTheSqlStore()
    {
        var store = new InMemoryWatcherObservationStore();
        Assert.False(store.RecordEpisodeTaskClassSource("ep-1", "operator"));
        Assert.Null(store.FindEpisodeTaskClassSource("ep-1"));

        var segment = new ScoreSegment(WorkspaceKey.From("C:/repos/app"), TaskClasses.FreeForm, "weave/1");
        store.RecordScorecard(Episode("ep-1", "op-a", segment));
        Assert.True(store.RecordEpisodeTaskClassSource("ep-1", "operator"));
        Assert.True(store.RecordEpisodeTaskClassSource("ep-1", "operator"));
        Assert.False(store.RecordEpisodeTaskClassSource("ep-1", "session-default"));
        Assert.Equal("operator", store.FindScoredEpisode("ep-1")!.TaskClassSource);
    }

    /// <summary>The compute reader: a leaderboard cell counts the episodes whose class was the session's default, and "not recorded" counts as neither.</summary>
    [Fact]
    public void TheLeaderboardCellTellsADefaultedClassFromAChosenOne()
    {
        var segment = new ScoreSegment(WorkspaceKey.From("C:/repos/app"), TaskClasses.FreeForm, "weave/1");
        var episodes = Enumerable.Range(0, 6).Select(i => Episode($"ep-{i}", i % 2 == 0 ? "op-a" : "op-b", segment) with
        {
            TaskClassSource = i switch { 0 or 1 => "session-default", 2 or 3 => "operator", _ => null },
        }).ToList();

        var board = new LeaderboardComposer().Compose(episodes, segment, cohortMinimum: 2);
        var cell = board.Cell(LeaderboardFacet.HarnessModel, "claude-code / sonnet")!;

        Assert.Equal(6, cell.Cohort);
        Assert.Equal(2, cell.DefaultedClass);
        Assert.Equal(2, cell.ChosenClass);
        Assert.True(cell.Comparable);   // free-form is a comparable class (Ruling 72)
    }

    private static ScoredEpisode Episode(string id, string op, ScoreSegment segment) =>
        new(id, "claude-code", "sonnet", op, segment,
            new Scorecard(id, "weave/1", WeaveVerdict.Scored, [], [], new EvidenceCoverage(1, 1), "Scored", DateTimeOffset.UnixEpoch));
}
