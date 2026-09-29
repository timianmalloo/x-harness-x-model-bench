using Microsoft.Data.Sqlite;

namespace AiDe.Core.Watcher;

/// <summary>
/// The durable <see cref="IWatcherObservationStore"/> on one SQLite file, reusing the ADR-0002 fact-store
/// idiom (WAL, append-only facts enforced by triggers, a single writer). It substitutes for
/// <see cref="InMemoryWatcherObservationStore"/> behind the same seam - the same contract, now persisted
/// across a restart. Spans are an append-only fact (dedup by content-addressed primary key); sessions,
/// heartbeats, and the ended flag are current-state cells (upsert), mirroring the in-memory maps.
///
/// simplify: one connection guarded by a lock. Ceiling: fine at the reference scale for the skeleton.
/// Upgrade trigger: read volume grows enough to want the WorkspaceStore read/write connection split.
/// </summary>
public sealed class SqliteWatcherObservationStore : IWatcherObservationStore, IDisposable
{
    private const int SchemaVersion = 7;

    private readonly SqliteConnection _connection;
    private readonly object _gate = new();
    private bool _disposed;

    private SqliteWatcherObservationStore(SqliteConnection connection, string databasePath)
    {
        _connection = connection;
        DatabasePath = databasePath;
    }

    /// <summary>The backing database file. Exposed so a test can open a raw connection against it.</summary>
    public string DatabasePath { get; }

    public static SqliteWatcherObservationStore Open(string databasePath)
    {
        ArgumentException.ThrowIfNullOrEmpty(databasePath);

        var connectionString = new SqliteConnectionStringBuilder
        {
            DataSource = databasePath,
            Mode = SqliteOpenMode.ReadWriteCreate,
            Pooling = false,
        }.ToString();

        var connection = new SqliteConnection(connectionString);
        connection.Open();
        Execute(connection, "PRAGMA journal_mode=WAL;");
        Execute(connection, "PRAGMA foreign_keys=ON;");
        // recursive_triggers=ON so an INSERT path cannot slip past the append-only triggers (ADR-0002 S4).
        Execute(connection, "PRAGMA recursive_triggers=ON;");
        EnsureSchema(connection);

        return new SqliteWatcherObservationStore(connection, databasePath);
    }

    /// <summary>
    /// Opens an EXISTING store read-only. Creates nothing and migrates nothing.
    /// </summary>
    /// <remarks>
    /// <para><b>For a reader that must hold no authority</b> — the MCP server, whose whole claim is
    /// that it can do nothing an agent writing JSONL by hand cannot. A write handle to the fact store
    /// would be exactly such an authority and would bypass every guarantee the ingest provides, so
    /// the mode is enforced here rather than trusted to a caller's discipline.</para>
    ///
    /// <para><b>ReadOnly, not ReadWrite-and-be-careful.</b> The distinction is enforced by SQLite
    /// rather than by convention, which is what makes "this process cannot write" a fact rather than
    /// a promise — and what a test can assert.</para>
    ///
    /// <para><b>No <c>EnsureSchema</c>.</b> A reader must never migrate: it would race the owning
    /// process, and a schema change is a decision the writer makes. A store older than this reader
    /// fails on the missing column, loudly, which is the honest outcome.</para>
    /// </remarks>
    /// <exception cref="FileNotFoundException">The store does not exist — an absence, not an empty store.</exception>
    public static SqliteWatcherObservationStore OpenReadOnly(string databasePath)
    {
        ArgumentException.ThrowIfNullOrEmpty(databasePath);

        if (!File.Exists(databasePath))
        {
            throw new FileNotFoundException(
                "The workspace store does not exist. Open the workspace in AI-DE first.", databasePath);
        }

        var connectionString = new SqliteConnectionStringBuilder
        {
            DataSource = databasePath,
            Mode = SqliteOpenMode.ReadOnly,
            Pooling = false,
        }.ToString();

        var connection = new SqliteConnection(connectionString);
        connection.Open();

        return new SqliteWatcherObservationStore(connection, databasePath);
    }

    public bool TryAppendSpan(ObservedSpan span)
    {
        ArgumentNullException.ThrowIfNull(span);
        lock (_gate)
        {
            // INSERT OR IGNORE: a primary-key conflict is a duplicate to ignore idempotently, and -
            // unlike INSERT OR REPLACE - it never fires the BEFORE UPDATE trigger, so append-only holds.
            var affected = ExecuteNonQuery(
                _connection,
                """
                INSERT OR IGNORE INTO observed_span_fact
                    (span_id, session_id, trace_id, source_span_id, operation_name, recorded_at)
                VALUES ($id, $session, $trace, $source, $op, $recorded);
                """,
                ("$id", span.SpanId),
                ("$session", span.SessionId),
                ("$trace", span.TraceId),
                ("$source", span.SourceSpanId),
                ("$op", span.OperationName),
                ("$recorded", span.RecordedAt.ToUniversalTime().ToString("O")));
            return affected > 0;
        }
    }

    public int SpanCount(string sessionId)
    {
        lock (_gate)
        {
            var count = ExecuteScalar(
                _connection,
                "SELECT count(*) FROM observed_span_fact WHERE session_id = $session;",
                ("$session", sessionId));
            return Convert.ToInt32(count);
        }
    }

    public int SpanCountInInterval(string sessionId, DateTimeOffset from, DateTimeOffset toInclusive)
    {
        lock (_gate)
        {
            // recorded_at is stored as ISO-8601 round-trip ("O") in UTC, which is fixed-width and
            // lexicographically ordered, so a string BETWEEN is a correct temporal range (endpoints inclusive).
            var count = ExecuteScalar(
                _connection,
                """
                SELECT count(*) FROM observed_span_fact
                WHERE session_id = $session AND recorded_at >= $from AND recorded_at <= $to;
                """,
                ("$session", sessionId),
                ("$from", from.ToUniversalTime().ToString("O")),
                ("$to", toInclusive.ToUniversalTime().ToString("O")));
            return Convert.ToInt32(count);
        }
    }

    public void UpsertHeartbeat(string sessionId, long monotonicTicks)
    {
        lock (_gate)
        {
            ExecuteNonQuery(
                _connection,
                """
                INSERT INTO session_heartbeat (session_id, monotonic_ticks) VALUES ($session, $ticks)
                ON CONFLICT(session_id) DO UPDATE SET monotonic_ticks = $ticks;
                """,
                ("$session", sessionId),
                ("$ticks", monotonicTicks));
        }
    }

    public long? LastHeartbeat(string sessionId)
    {
        lock (_gate)
        {
            var value = ExecuteScalar(
                _connection,
                "SELECT monotonic_ticks FROM session_heartbeat WHERE session_id = $session;",
                ("$session", sessionId));
            return value is null or DBNull ? null : Convert.ToInt64(value);
        }
    }

    public void RecordSession(SessionRecord session)
    {
        ArgumentNullException.ThrowIfNull(session);
        var b = session.Binding;
        lock (_gate)
        {
            // Upsert the current session metadata, preserving heartbeat/ended which live in their own
            // tables - a dimension row, not an append-only fact.
            ExecuteNonQuery(
                _connection,
                """
                INSERT INTO agent_session_dim
                    (session_id, generation, repo_path, repo_display, worktree_branch, worktree_path,
                     terminal_id, agent_name, harness_name, harness_version, model_name, model_version, trust)
                VALUES ($id, $gen, $repoPath, $repoDisplay, $wtBranch, $wtPath,
                        $terminal, $agent, $hName, $hVer, $mName, $mVer, $trust)
                ON CONFLICT(session_id) DO UPDATE SET
                    generation = $gen, repo_path = $repoPath, repo_display = $repoDisplay,
                    worktree_branch = $wtBranch, worktree_path = $wtPath, terminal_id = $terminal,
                    agent_name = $agent, harness_name = $hName, harness_version = $hVer,
                    model_name = $mName, model_version = $mVer, trust = $trust;
                """,
                ("$id", session.SessionId),
                ("$gen", session.Generation.Value),
                ("$repoPath", b.Repository.CanonicalPath),
                ("$repoDisplay", b.Repository.DisplayName),
                ("$wtBranch", b.Worktree.Branch),
                ("$wtPath", b.Worktree.Path),
                ("$terminal", b.Terminal.TerminalId),
                ("$agent", b.Agent.AgentName),
                ("$hName", (object?)b.Harness?.Name ?? DBNull.Value),
                ("$hVer", (object?)b.Harness?.Version ?? DBNull.Value),
                ("$mName", (object?)b.Model?.Name ?? DBNull.Value),
                ("$mVer", (object?)b.Model?.Version ?? DBNull.Value),
                ("$trust", b.Trust.ToString()));
        }
    }

    public SessionRecord? FindSession(string sessionId)
    {
        lock (_gate)
        {
            using var command = _connection.CreateCommand();
            command.CommandText =
                """
                SELECT generation, repo_path, repo_display, worktree_branch, worktree_path, terminal_id,
                       agent_name, harness_name, harness_version, model_name, model_version, trust
                FROM agent_session_dim WHERE session_id = $session;
                """;
            command.Parameters.AddWithValue("$session", sessionId);
            using var reader = command.ExecuteReader();
            if (!reader.Read())
            {
                return null;
            }

            var repo = new RepositoryIdentity(reader.GetString(1), reader.GetString(2));
            var binding = new SessionBinding(
                repo,
                new WorktreeIdentity(repo, reader.GetString(3), reader.GetString(4)),
                new TerminalIdentity(reader.GetString(5)),
                new AgentIdentity(reader.GetString(6)),
                reader.IsDBNull(7) ? null : new HarnessIdentity(reader.GetString(7), reader.GetString(8)),
                reader.IsDBNull(9) ? null : new ModelIdentity(reader.GetString(9), reader.GetString(10)),
                Enum.Parse<TrustClassification>(reader.GetString(11)));
            return new SessionRecord(sessionId, new SessionGeneration(reader.GetInt64(0)), binding);
        }
    }

    public IReadOnlyList<SessionRecord> AllSessions()
    {
        lock (_gate)
        {
            using var command = _connection.CreateCommand();
            command.CommandText =
                """
                SELECT session_id, generation, repo_path, repo_display, worktree_branch, worktree_path,
                       terminal_id, agent_name, harness_name, harness_version, model_name, model_version, trust
                FROM agent_session_dim ORDER BY repo_display, worktree_branch, session_id;
                """;
            using var reader = command.ExecuteReader();
            var sessions = new List<SessionRecord>();
            while (reader.Read())
            {
                var repo = new RepositoryIdentity(reader.GetString(2), reader.GetString(3));
                var binding = new SessionBinding(
                    repo,
                    new WorktreeIdentity(repo, reader.GetString(4), reader.GetString(5)),
                    new TerminalIdentity(reader.GetString(6)),
                    new AgentIdentity(reader.GetString(7)),
                    reader.IsDBNull(8) ? null : new HarnessIdentity(reader.GetString(8), reader.GetString(9)),
                    reader.IsDBNull(10) ? null : new ModelIdentity(reader.GetString(10), reader.GetString(11)),
                    Enum.Parse<TrustClassification>(reader.GetString(12)));
                sessions.Add(new SessionRecord(reader.GetString(0), new SessionGeneration(reader.GetInt64(1)), binding));
            }

            return sessions;
        }
    }

    public void RecordEpisode(WorkEpisode episode)
    {
        ArgumentNullException.ThrowIfNull(episode);
        lock (_gate)
        {
            // Upsert a lifecycle dimension row (a reframe/close is an update of the current state, not
            // an append-only fact). Immutability of the goal/done is enforced by the service, not the row.
            ExecuteNonQuery(
                _connection,
                """
                INSERT INTO work_episode_dim
                    (episode_id, session_id, generation, goal, done_when, not_in_scope, opened_at, closed_at, outcome)
                VALUES ($id, $session, $gen, $goal, $done, $scope, $opened, $closed, $outcome)
                ON CONFLICT(episode_id) DO UPDATE SET
                    session_id = $session, generation = $gen, goal = $goal, done_when = $done,
                    not_in_scope = $scope, opened_at = $opened, closed_at = $closed, outcome = $outcome;
                """,
                ("$id", episode.EpisodeId),
                ("$session", episode.SessionId),
                ("$gen", episode.Generation.Value),
                ("$goal", episode.Goal.Statement),
                ("$done", episode.DoneWhen.Statement),
                ("$scope", (object?)episode.NotInScope ?? DBNull.Value),
                ("$opened", episode.OpenedAt.ToUniversalTime().ToString("O")),
                ("$closed", (object?)episode.ClosedAt?.ToUniversalTime().ToString("O") ?? DBNull.Value),
                ("$outcome", (object?)episode.Outcome?.ToString() ?? DBNull.Value));
        }
    }

    public WorkEpisode? FindEpisode(string episodeId)
    {
        lock (_gate)
        {
            using var command = _connection.CreateCommand();
            command.CommandText =
                """
                SELECT episode_id, session_id, generation, goal, done_when, not_in_scope, opened_at, closed_at, outcome
                FROM work_episode_dim WHERE episode_id = $id;
                """;
            command.Parameters.AddWithValue("$id", episodeId);
            using var reader = command.ExecuteReader();
            return reader.Read() ? ReadEpisode(reader) : null;
        }
    }

    public IReadOnlyList<WorkEpisode> EpisodesForSession(string sessionId)
    {
        lock (_gate)
        {
            using var command = _connection.CreateCommand();
            command.CommandText =
                """
                SELECT episode_id, session_id, generation, goal, done_when, not_in_scope, opened_at, closed_at, outcome
                FROM work_episode_dim WHERE session_id = $session ORDER BY generation;
                """;
            command.Parameters.AddWithValue("$session", sessionId);
            return ReadEpisodes(command);
        }
    }

    public IReadOnlyList<WorkEpisode> AllEpisodes()
    {
        lock (_gate)
        {
            using var command = _connection.CreateCommand();
            command.CommandText =
                """
                SELECT episode_id, session_id, generation, goal, done_when, not_in_scope, opened_at, closed_at, outcome
                FROM work_episode_dim ORDER BY session_id, generation;
                """;
            return ReadEpisodes(command);
        }
    }

    private static IReadOnlyList<WorkEpisode> ReadEpisodes(SqliteCommand command)
    {
        using var reader = command.ExecuteReader();
        var episodes = new List<WorkEpisode>();
        while (reader.Read())
        {
            episodes.Add(ReadEpisode(reader));
        }

        return episodes;
    }

    private static WorkEpisode ReadEpisode(SqliteDataReader reader) => new(
        reader.GetString(0),
        reader.GetString(1),
        new EpisodeGeneration(reader.GetInt64(2)),
        new Goal(reader.GetString(3)),
        new DoneCondition(reader.GetString(4)),
        reader.IsDBNull(5) ? null : reader.GetString(5),
        DateTimeOffset.Parse(reader.GetString(6), null, System.Globalization.DateTimeStyles.RoundtripKind),
        reader.IsDBNull(7) ? null : DateTimeOffset.Parse(reader.GetString(7), null, System.Globalization.DateTimeStyles.RoundtripKind),
        reader.IsDBNull(8) ? null : Enum.Parse<EpisodeOutcome>(reader.GetString(8)));

    public void AppendDeclaredArtifact(DeclaredEpisodeArtifact artifact)
    {
        ArgumentNullException.ThrowIfNull(artifact);
        lock (_gate)
        {
            // OR IGNORE on (episode, path, sequence): a redelivered contract line is a no-op rather
            // than a duplicate claim. The coordination log is re-read from the start on every pump,
            // so idempotent ingest is the norm here and not a defensive extra.
            ExecuteNonQuery(
                _connection,
                """
                INSERT OR IGNORE INTO declared_artifact_fact (episode_id, path, declared_at, sequence)
                VALUES ($episode, $path, $declared, $sequence);
                """,
                null,
                ("$episode", artifact.EpisodeId),
                ("$path", artifact.Path),
                ("$declared", artifact.DeclaredAt.ToString("O")),
                ("$sequence", artifact.Sequence));
        }
    }

    public IReadOnlyList<DeclaredEpisodeArtifact> DeclaredArtifactsFor(string episodeId)
    {
        ArgumentException.ThrowIfNullOrEmpty(episodeId);
        lock (_gate)
        {
            var rows = new List<DeclaredEpisodeArtifact>();
            using var command = _connection.CreateCommand();
            command.CommandText =
                """
                SELECT episode_id, path, declared_at, sequence
                FROM declared_artifact_fact
                WHERE episode_id = $episode
                ORDER BY sequence, path;
                """;
            command.Parameters.AddWithValue("$episode", episodeId);
            using var reader = command.ExecuteReader();
            while (reader.Read())
            {
                rows.Add(new DeclaredEpisodeArtifact(
                    reader.GetString(0),
                    reader.GetString(1),
                    DateTimeOffset.Parse(reader.GetString(2), System.Globalization.CultureInfo.InvariantCulture),
                    reader.GetInt64(3)));
            }

            return rows;
        }
    }

    public void AppendDaydreamObservation(DaydreamObservation observation)
    {
        ArgumentNullException.ThrowIfNull(observation);
        lock (_gate)
        {
            ExecuteNonQuery(
                _connection,
                """
                INSERT INTO daydream_observation_fact
                    (observation_id, task_class, schema_version, verdict, floors, shortfalls,
                     episode_id, observed_at)
                VALUES ($id, $task, $schema, $verdict, $floors, $shortfalls, $episode, $observed);
                """,
                null,
                ("$id", observation.ObservationId),
                ("$task", observation.Signature.TaskClass),
                ("$schema", observation.Signature.SchemaVersion),
                ("$verdict", observation.Signature.Verdict.ToString()),
                ("$floors", observation.Signature.Floors),
                ("$shortfalls", observation.Signature.Shortfalls),
                ("$episode", observation.EpisodeId),
                ("$observed", observation.ObservedAt.ToString("O")));
        }
    }

    public IReadOnlyList<DaydreamObservation> AllDaydreamObservations()
    {
        lock (_gate)
        {
            var rows = new List<DaydreamObservation>();
            using var command = _connection.CreateCommand();
            command.CommandText =
                """
                SELECT observation_id, task_class, schema_version, verdict, floors, shortfalls,
                       episode_id, observed_at
                FROM daydream_observation_fact
                ORDER BY observed_at, observation_id;
                """;
            using var reader = command.ExecuteReader();
            while (reader.Read())
            {
                rows.Add(new DaydreamObservation(
                    reader.GetString(0),
                    new DaydreamSignature(
                        reader.GetString(1),
                        reader.GetString(2),
                        Enum.Parse<WeaveVerdict>(reader.GetString(3)),
                        reader.GetString(4),
                        reader.GetString(5)),
                    reader.GetString(6),
                    DateTimeOffset.Parse(reader.GetString(7), System.Globalization.CultureInfo.InvariantCulture)));
            }

            return rows;
        }
    }

    public void AppendDaydreamEvent(DaydreamEvent daydreamEvent)
    {
        ArgumentNullException.ThrowIfNull(daydreamEvent);
        lock (_gate)
        {
            ExecuteNonQuery(
                _connection,
                """
                INSERT INTO daydream_event_fact
                    (event_id, task_class, schema_version, verdict, floors, shortfalls,
                     kind, actor, detail, outcome, at, sequence)
                VALUES ($id, $task, $schema, $verdict, $floors, $shortfalls,
                        $kind, $actor, $detail, $outcome, $at, $seq);
                """,
                null,
                ("$id", daydreamEvent.EventId),
                ("$task", daydreamEvent.Signature.TaskClass),
                ("$schema", daydreamEvent.Signature.SchemaVersion),
                ("$verdict", daydreamEvent.Signature.Verdict.ToString()),
                ("$floors", daydreamEvent.Signature.Floors),
                ("$shortfalls", daydreamEvent.Signature.Shortfalls),
                ("$kind", daydreamEvent.Kind.ToString()),
                ("$actor", daydreamEvent.Actor),
                ("$detail", (object?)daydreamEvent.Detail ?? DBNull.Value),
                ("$outcome", (object?)daydreamEvent.Outcome?.ToString() ?? DBNull.Value),
                ("$at", daydreamEvent.At.ToString("O")),
                ("$seq", daydreamEvent.Sequence));
        }
    }

    public IReadOnlyList<DaydreamEvent> AllDaydreamEvents()
    {
        lock (_gate)
        {
            var rows = new List<DaydreamEvent>();
            using var command = _connection.CreateCommand();
            command.CommandText =
                """
                SELECT event_id, task_class, schema_version, verdict, floors, shortfalls,
                       kind, actor, detail, outcome, at, sequence
                FROM daydream_event_fact
                ORDER BY sequence, event_id;
                """;
            using var reader = command.ExecuteReader();
            while (reader.Read())
            {
                rows.Add(new DaydreamEvent(
                    reader.GetString(0),
                    new DaydreamSignature(
                        reader.GetString(1), reader.GetString(2),
                        Enum.Parse<WeaveVerdict>(reader.GetString(3)),
                        reader.GetString(4), reader.GetString(5)),
                    Enum.Parse<DaydreamEventKind>(reader.GetString(6)),
                    reader.GetString(7),
                    reader.IsDBNull(8) ? null : reader.GetString(8),
                    reader.IsDBNull(9) ? null : Enum.Parse<DisconfirmingOutcome>(reader.GetString(9)),
                    DateTimeOffset.Parse(reader.GetString(10), System.Globalization.CultureInfo.InvariantCulture),
                    reader.GetInt64(11)));
            }

            return rows;
        }
    }

    public void AppendBoardMessage(BoardMessage message)
    {
        ArgumentNullException.ThrowIfNull(message);
        lock (_gate)
        {
            ExecuteNonQuery(
                _connection,
                """
                INSERT INTO board_message_fact
                    (message_id, repository_key, kind, author_session_id, author_trust, parent_message_id,
                     content, quarantined, injection_flagged, tombstoned, recorded_at, seq)
                VALUES ($id, $repo, $kind, $author, $trust, $parent, $content, $quar, $inj, $tomb, $recorded, $seq);
                """,
                ("$id", message.MessageId),
                ("$repo", message.RepositoryKey),
                ("$kind", message.Kind.ToString()),
                ("$author", message.AuthorSessionId),
                ("$trust", message.AuthorTrust.ToString()),
                ("$parent", (object?)message.ParentMessageId ?? DBNull.Value),
                ("$content", (object?)message.Content ?? DBNull.Value),
                ("$quar", message.Quarantined ? 1 : 0),
                ("$inj", message.InjectionFlagged ? 1 : 0),
                ("$tomb", message.Tombstoned ? 1 : 0),
                ("$recorded", message.RecordedAt.ToUniversalTime().ToString("O")),
                ("$seq", message.Seq));
        }
    }

    public IReadOnlyList<BoardMessage> BoardMessages(string repositoryKey)
    {
        lock (_gate)
        {
            using var command = _connection.CreateCommand();
            command.CommandText = BoardSelect + " WHERE repository_key = $repo ORDER BY seq;";
            command.Parameters.AddWithValue("$repo", repositoryKey);
            using var reader = command.ExecuteReader();
            var messages = new List<BoardMessage>();
            while (reader.Read())
            {
                messages.Add(ReadBoardMessage(reader));
            }

            return messages;
        }
    }

    public IReadOnlyList<BoardMessage> AllBoardMessages()
    {
        lock (_gate)
        {
            using var command = _connection.CreateCommand();
            command.CommandText = BoardSelect + " ORDER BY repository_key, seq;";
            using var reader = command.ExecuteReader();
            var messages = new List<BoardMessage>();
            while (reader.Read())
            {
                messages.Add(ReadBoardMessage(reader));
            }

            return messages;
        }
    }

    public BoardMessage? FindBoardMessage(string messageId)
    {
        lock (_gate)
        {
            using var command = _connection.CreateCommand();
            command.CommandText = BoardSelect + " WHERE message_id = $id;";
            command.Parameters.AddWithValue("$id", messageId);
            using var reader = command.ExecuteReader();
            return reader.Read() ? ReadBoardMessage(reader) : null;
        }
    }

    public void RedactBoardMessage(string messageId)
    {
        lock (_gate)
        {
            // The one allowed content mutation: null the payload, keep the envelope as a tombstone.
            ExecuteNonQuery(
                _connection,
                "UPDATE board_message_fact SET content = NULL, tombstoned = 1 WHERE message_id = $id;",
                ("$id", messageId));
        }
    }

    private const string BoardSelect =
        """
        SELECT message_id, repository_key, kind, author_session_id, author_trust, parent_message_id,
               content, quarantined, injection_flagged, tombstoned, recorded_at, seq
        FROM board_message_fact
        """;

    private static BoardMessage ReadBoardMessage(SqliteDataReader reader) => new(
        reader.GetString(0),
        reader.GetString(1),
        Enum.Parse<BoardMessageKind>(reader.GetString(2)),
        reader.GetString(3),
        Enum.Parse<TrustClassification>(reader.GetString(4)),
        reader.IsDBNull(5) ? null : reader.GetString(5),
        reader.IsDBNull(6) ? null : reader.GetString(6),
        reader.GetInt64(7) != 0,
        reader.GetInt64(8) != 0,
        reader.GetInt64(9) != 0,
        DateTimeOffset.Parse(reader.GetString(10), null, System.Globalization.DateTimeStyles.RoundtripKind),
        (int)reader.GetInt64(11));

    public void MarkEnded(string sessionId)
    {
        lock (_gate)
        {
            ExecuteNonQuery(
                _connection,
                "INSERT OR IGNORE INTO session_ended (session_id) VALUES ($session);",
                ("$session", sessionId));
        }
    }

    public void ClearEnded(string sessionId)
    {
        lock (_gate)
        {
            ExecuteNonQuery(
                _connection,
                "DELETE FROM session_ended WHERE session_id = $session;",
                ("$session", sessionId));
        }
    }

    public bool IsEnded(string sessionId)
    {
        lock (_gate)
        {
            var value = ExecuteScalar(
                _connection,
                "SELECT EXISTS(SELECT 1 FROM session_ended WHERE session_id = $session);",
                ("$session", sessionId));
            return Convert.ToInt64(value) != 0;
        }
    }

    public void RecordScorecard(ScoredEpisode scored)
    {
        ArgumentNullException.ThrowIfNull(scored);
        var card = scored.Scorecard;
        lock (_gate)
        {
            // One transaction: upsert the parent cell, then replace all child rows. Delete-then-insert
            // the children so a recompute never leaves a stale dimension or floor behind (DM7 cache
            // refresh). NOT append-only: a derived value is replaced, not historised.
            using var tx = _connection.BeginTransaction();

            ExecuteNonQuery(
                _connection,
                """
                INSERT INTO scored_episode_cell
                    (episode_id, harness, model, operator_id, task_class, schema_version,
                     verdict, headline, coverage_observed, coverage_required, evaluated_at, workspace)
                VALUES ($id, $harness, $model, $op, $task, $schema, $verdict, $headline, $covObs, $covReq, $at, $ws)
                ON CONFLICT(episode_id) DO UPDATE SET
                    harness = $harness, model = $model, operator_id = $op, task_class = $task,
                    schema_version = $schema, verdict = $verdict, headline = $headline,
                    coverage_observed = $covObs, coverage_required = $covReq, evaluated_at = $at,
                    workspace = $ws;
                """,
                tx,
                ("$id", scored.EpisodeId),
                ("$harness", scored.Harness),
                ("$model", scored.Model),
                ("$op", scored.OperatorId),
                ("$task", scored.TaskClass),
                ("$schema", scored.SchemaVersion),
                ("$verdict", card.Verdict.ToString()),
                ("$headline", card.Headline),
                ("$covObs", card.Coverage is { } c1 ? c1.Observed : (object?)null),
                ("$covReq", card.Coverage is { } c2 ? c2.Required : (object?)null),
                ("$at", card.EvaluatedAt.ToUniversalTime().ToString("O")),
                ("$ws", scored.Segment.Workspace?.Value));

            ExecuteNonQuery(_connection, "DELETE FROM score_dimension_cell WHERE episode_id = $id;", tx, ("$id", scored.EpisodeId));
            ExecuteNonQuery(_connection, "DELETE FROM score_tripped_floor_cell WHERE episode_id = $id;", tx, ("$id", scored.EpisodeId));

            foreach (var a in card.Assessments)
            {
                ExecuteNonQuery(
                    _connection,
                    """
                    INSERT INTO score_dimension_cell
                        (episode_id, dimension, weight, rubric, earned_points, posture, rationale)
                    VALUES ($id, $dim, $weight, $rubric, $earned, $posture, $rationale);
                    """,
                    tx,
                    ("$id", scored.EpisodeId),
                    ("$dim", a.Dimension.ToString()),
                    ("$weight", a.Weight),
                    ("$rubric", a.Rubric0to4 is { } r ? r : (object?)null),
                    ("$earned", a.EarnedPoints is { } e ? e : (object?)null),
                    ("$posture", a.Posture.ToString()),
                    ("$rationale", a.Rationale));
            }

            foreach (var floor in card.TrippedFloors)
            {
                ExecuteNonQuery(
                    _connection,
                    "INSERT OR IGNORE INTO score_tripped_floor_cell (episode_id, floor) VALUES ($id, $floor);",
                    tx,
                    ("$id", scored.EpisodeId),
                    ("$floor", floor.ToString()));
            }

            tx.Commit();
        }
    }

    public ScoredEpisode? FindScoredEpisode(string episodeId)
    {
        lock (_gate)
        {
            using var command = _connection.CreateCommand();
            command.CommandText = ScoredEpisodeSelect + " WHERE episode_id = $id;";
            command.Parameters.AddWithValue("$id", episodeId);
            var episodes = ReadScoredEpisodes(command);
            return episodes.Count == 0 ? null : episodes[0];
        }
    }

    public IReadOnlyList<ScoredEpisode> AllScoredEpisodes()
    {
        lock (_gate)
        {
            using var command = _connection.CreateCommand();
            command.CommandText = ScoredEpisodeSelect + ";";
            return ReadScoredEpisodes(command);
        }
    }

    public bool RecordEpisodeMode(string episodeId, string mode)
    {
        ArgumentException.ThrowIfNullOrEmpty(episodeId);
        ArgumentException.ThrowIfNullOrWhiteSpace(mode);

        lock (_gate)
        {
            // An UPDATE, not an upsert. A mode without a scorecard would be a cohort label on a cell
            // that does not exist, and the caller learns nothing was stamped rather than believing it
            // was. RecordScorecard's own column list omits `mode`, so a re-score preserves whatever
            // was stamped here instead of clearing it.
            using var command = _connection.CreateCommand();
            command.CommandText = "UPDATE scored_episode_cell SET mode = $mode WHERE episode_id = $id;";
            command.Parameters.AddWithValue("$mode", mode);
            command.Parameters.AddWithValue("$id", episodeId);
            return command.ExecuteNonQuery() == 1;
        }
    }

    public string? FindEpisodeMode(string episodeId)
    {
        lock (_gate)
        {
            using var command = _connection.CreateCommand();
            command.CommandText = "SELECT mode FROM scored_episode_cell WHERE episode_id = $id;";
            command.Parameters.AddWithValue("$id", episodeId);
            var value = command.ExecuteScalar();
            return value is null or DBNull ? null : (string)value;
        }
    }

    public bool RecordEpisodeTaskClassSource(string episodeId, string source)
    {
        ArgumentException.ThrowIfNullOrEmpty(episodeId);
        ArgumentException.ThrowIfNullOrWhiteSpace(source);
        lock (_gate)
        {
            // An UPDATE, not an upsert, exactly as `mode`: a provenance without a scorecard would be a
            // cohort label on a cell that does not exist. RecordScorecard's column list omits
            // `task_class_source`, so a re-score preserves whatever was stamped. IDEMPOTENT, never a
            // silent rewrite: a same-value re-stamp succeeds, a different value is refused (false) —
            // the caller says so (`compile.degraded{task-class-source-restamped}`) rather than
            // overwriting provenance (DM-F).
            using var command = _connection.CreateCommand();
            command.CommandText = "UPDATE scored_episode_cell SET task_class_source = $source WHERE episode_id = $id AND (task_class_source IS NULL OR task_class_source = $source);";
            command.Parameters.AddWithValue("$source", source);
            command.Parameters.AddWithValue("$id", episodeId);
            return command.ExecuteNonQuery() == 1;
        }
    }

    public string? FindEpisodeTaskClassSource(string episodeId)
    {
        lock (_gate)
        {
            using var command = _connection.CreateCommand();
            command.CommandText = "SELECT task_class_source FROM scored_episode_cell WHERE episode_id = $id;";
            command.Parameters.AddWithValue("$id", episodeId);
            var value = command.ExecuteScalar();
            return value is null or DBNull ? null : (string)value;
        }
    }

    private const string ScoredEpisodeSelect =
        """
        SELECT episode_id, harness, model, operator_id, task_class, schema_version,
               verdict, headline, coverage_observed, coverage_required, evaluated_at, workspace,
               task_class_source
        FROM scored_episode_cell
        """;

    private IReadOnlyList<ScoredEpisode> ReadScoredEpisodes(SqliteCommand command)
    {
        var rows = new List<(string Id, string? Harness, string? Model, string Op, string Task, string Schema,
            WeaveVerdict Verdict, string Headline, EvidenceCoverage? Coverage, DateTimeOffset At, string? Workspace, string? TaskClassSource)>();

        using (var reader = command.ExecuteReader())
        {
            while (reader.Read())
            {
                EvidenceCoverage? coverage = reader.IsDBNull(8) || reader.IsDBNull(9)
                    ? null
                    : new EvidenceCoverage(reader.GetInt32(8), reader.GetInt32(9));
                rows.Add((
                    reader.GetString(0),
                    reader.IsDBNull(1) ? null : reader.GetString(1),
                    reader.IsDBNull(2) ? null : reader.GetString(2),
                    reader.GetString(3),
                    reader.GetString(4),
                    reader.GetString(5),
                    Enum.Parse<WeaveVerdict>(reader.GetString(6)),
                    reader.GetString(7),
                    coverage,
                    DateTimeOffset.Parse(reader.GetString(10), null, System.Globalization.DateTimeStyles.RoundtripKind),
                    // NULL for a row written before segmentation existed. Read back as an absent
                    // workspace, never as a path - a backfill here would be a guess (DM: a backfill
                    // never guesses), and the row is excluded from cells rather than mis-compared.
                    reader.IsDBNull(11) ? null : reader.GetString(11),

                    // NULL for a row written before v7, or never stamped: "not recorded", never a guess.
                    reader.IsDBNull(12) ? null : reader.GetString(12)));
            }
        }

        var result = new List<ScoredEpisode>(rows.Count);
        foreach (var row in rows)
        {
            var assessments = ReadDimensions(row.Id);
            var floors = ReadTrippedFloors(row.Id);
            var card = new Scorecard(row.Id, row.Schema, row.Verdict, assessments, floors, row.Coverage, row.Headline, row.At);
            result.Add(new ScoredEpisode(
                row.Id, row.Harness, row.Model, row.Op,
                new ScoreSegment(WorkspaceKey.From(row.Workspace), row.Task, row.Schema), card)
            {
                TaskClassSource = row.TaskClassSource,
            });
        }

        return result;
    }

    private IReadOnlyList<DimensionAssessment> ReadDimensions(string episodeId)
    {
        using var command = _connection.CreateCommand();
        command.CommandText =
            "SELECT dimension, weight, rubric, earned_points, posture, rationale FROM score_dimension_cell WHERE episode_id = $id;";
        command.Parameters.AddWithValue("$id", episodeId);
        using var reader = command.ExecuteReader();
        var list = new List<DimensionAssessment>();
        while (reader.Read())
        {
            list.Add(new DimensionAssessment(
                Enum.Parse<ScoreDimension>(reader.GetString(0)),
                reader.GetInt32(1),
                reader.IsDBNull(2) ? null : reader.GetInt32(2),
                reader.IsDBNull(3) ? null : reader.GetDouble(3),
                Enum.Parse<AssessmentPosture>(reader.GetString(4)),
                reader.GetString(5)));
        }

        return list;
    }

    private IReadOnlyList<FloorDomain> ReadTrippedFloors(string episodeId)
    {
        using var command = _connection.CreateCommand();
        command.CommandText = "SELECT floor FROM score_tripped_floor_cell WHERE episode_id = $id;";
        command.Parameters.AddWithValue("$id", episodeId);
        using var reader = command.ExecuteReader();
        var list = new List<FloorDomain>();
        while (reader.Read())
        {
            list.Add(Enum.Parse<FloorDomain>(reader.GetString(0)));
        }

        return list;
    }

    public void AppendScoreDispute(ScoreDispute dispute)
    {
        ArgumentNullException.ThrowIfNull(dispute);
        lock (_gate)
        {
            // INSERT OR IGNORE: a redelivered dispute id is a no-op, and - unlike INSERT OR REPLACE -
            // it never fires the BEFORE UPDATE trigger, so append-only holds (rule 12).
            ExecuteNonQuery(
                _connection,
                """
                INSERT OR IGNORE INTO score_dispute_fact
                    (dispute_id, episode_id, operator_id, disputed_dimension, reason, raised_at)
                VALUES ($id, $episode, $op, $dim, $reason, $raised);
                """,
                ("$id", dispute.DisputeId),
                ("$episode", dispute.EpisodeId),
                ("$op", dispute.OperatorId),
                ("$dim", dispute.DisputedDimension?.ToString()),
                ("$reason", dispute.Reason),
                ("$raised", dispute.RaisedAt.ToUniversalTime().ToString("O")));
        }
    }

    public IReadOnlyList<ScoreDispute> DisputesForEpisode(string episodeId)
    {
        lock (_gate)
        {
            using var command = _connection.CreateCommand();
            command.CommandText = DisputeSelect + " WHERE episode_id = $episode ORDER BY raised_at;";
            command.Parameters.AddWithValue("$episode", episodeId);
            return ReadDisputes(command);
        }
    }

    public IReadOnlyList<ScoreDispute> AllDisputes()
    {
        lock (_gate)
        {
            using var command = _connection.CreateCommand();
            command.CommandText = DisputeSelect + " ORDER BY raised_at;";
            return ReadDisputes(command);
        }
    }

    private const string DisputeSelect =
        "SELECT dispute_id, episode_id, operator_id, disputed_dimension, reason, raised_at FROM score_dispute_fact";

    private static IReadOnlyList<ScoreDispute> ReadDisputes(SqliteCommand command)
    {
        using var reader = command.ExecuteReader();
        var list = new List<ScoreDispute>();
        while (reader.Read())
        {
            list.Add(new ScoreDispute(
                reader.GetString(0),
                reader.GetString(1),
                reader.GetString(2),
                reader.IsDBNull(3) ? null : Enum.Parse<ScoreDimension>(reader.GetString(3)),
                reader.GetString(4),
                DateTimeOffset.Parse(reader.GetString(5), null, System.Globalization.DateTimeStyles.RoundtripKind)));
        }

        return list;
    }

    public void Dispose()
    {
        if (_disposed)
        {
            return;
        }

        _disposed = true;
        _connection.Dispose();
        SqliteConnection.ClearAllPools();
    }

    /// <summary>
    /// Creates the schema on a new database, and applies pending additive migrations to an existing
    /// one.
    /// </summary>
    /// <remarks>
    /// <para><b>The migration half did not exist.</b> This method returned early whenever
    /// <c>watcher_schema_version</c> was present, so <see cref="SchemaSql"/> only ever ran against a
    /// FRESH database. Adding a table to it would have given that table to new workspaces and to no
    /// existing one — and the failure would have surfaced as "no such table" at the first read, in
    /// whichever workspace had been opened longest. Found in D2's P0 by reading the method rather
    /// than trusting that a versioned schema implied a version check.</para>
    ///
    /// <para><b>Expand only.</b> Every migration here creates something that did not exist; none
    /// rewrites or drops. So there is no backfill to get wrong and nothing to roll back.</para>
    ///
    /// <para><b>And idempotent, which this comment claimed before it was true.</b> The DDL uses
    /// <c>IF NOT EXISTS</c> and a column add is guarded by <see cref="ColumnExists"/> (SQLite
    /// has no conditional ADD COLUMN), so a database that already holds part of a later shape — a shortcut
    /// during a repair, an interrupted run, a hand edit — heals instead of refusing to open. The
    /// first version said "re-running is safe" while a re-run would have thrown; a test rewinding a
    /// version without dropping everything that came after it is what found the gap between the
    /// sentence and the code.</para>
    /// </remarks>
    private static void EnsureSchema(SqliteConnection connection)
    {
        var exists = Convert.ToInt64(ExecuteScalar(
            connection,
            "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='watcher_schema_version';")) > 0;

        if (!exists)
        {
            using var create = connection.BeginTransaction();
            ExecuteNonQuery(connection, SchemaSql, create);
            RecordVersion(connection, create, SchemaVersion);
            create.Commit();
            return;
        }

        var current = Convert.ToInt64(ExecuteScalar(
            connection, "SELECT max(version) FROM watcher_schema_version;") ?? 0L);
        if (current >= SchemaVersion)
        {
            return;
        }

        using var tx = connection.BeginTransaction();
        foreach (var (version, ddl, addsColumn) in Migrations.Where(m => m.Version > current).OrderBy(m => m.Version))
        {
            // SQLite has no "ADD COLUMN IF NOT EXISTS", so the guard is explicit rather than in the
            // DDL. Without it the idempotency this method claims would be false for exactly one
            // migration shape, and the claim is load-bearing: a database that already holds part of
            // a later shape must heal rather than refuse to open.
            if (addsColumn is { } add && !ColumnExists(connection, tx, add.Table, add.Column))
            {
                ExecuteNonQuery(connection, $"ALTER TABLE {add.Table} ADD COLUMN {add.Column} {add.Declaration};", tx);
            }

            if (!string.IsNullOrWhiteSpace(ddl))
            {
                ExecuteNonQuery(connection, ddl, tx);
            }

            RecordVersion(connection, tx, version);
        }

        tx.Commit();
    }

    /// <summary>Whether a column is already present, so an ADD COLUMN can be skipped rather than throw.</summary>
    private static bool ColumnExists(SqliteConnection connection, SqliteTransaction tx, string table, string column)
    {
        using var command = connection.CreateCommand();
        command.Transaction = tx;
        command.CommandText = $"SELECT count(*) FROM pragma_table_info('{table}') WHERE name = $c;";
        command.Parameters.AddWithValue("$c", column);
        return Convert.ToInt64(command.ExecuteScalar() ?? 0L) > 0;
    }

    private static void RecordVersion(SqliteConnection connection, SqliteTransaction tx, int version)
        => ExecuteNonQuery(
            connection,
            "INSERT INTO watcher_schema_version (version, applied_at) VALUES ($v, $t);",
            tx,
            ("$v", version),
            ("$t", DateTimeOffset.UtcNow.ToString("O")));

    /// <summary>
    /// Additive DDL to bring an existing database up to <see cref="SchemaVersion"/>.
    /// </summary>
    /// <remarks>
    /// Each entry must also appear in <see cref="SchemaSql"/>, so a fresh database and a migrated
    /// one end up identical. <c>DaydreamPersistenceTests.AFreshDatabaseAndAMigratedOneHaveTheSameSchema</c>
    /// asserts exactly that by comparing <c>sqlite_master</c>, because two definitions of one schema
    /// is the shape that drifts. (This previously named a class that has never existed - a comment
    /// asserting a control by a name nothing resolves is the prose form of an unenforced invariant.)
    /// </remarks>
    private static readonly (int Version, string Ddl, (string Table, string Column, string Declaration)? AddsColumn)[] Migrations =
    [
        (2, """
            CREATE TABLE IF NOT EXISTS daydream_observation_fact (
                observation_id  TEXT NOT NULL PRIMARY KEY,
                task_class      TEXT NOT NULL,
                schema_version  TEXT NOT NULL,
                verdict         TEXT NOT NULL,
                floors          TEXT NOT NULL,
                shortfalls      TEXT NOT NULL,
                episode_id      TEXT NOT NULL,
                observed_at     TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS ix_daydream_observation_episode ON daydream_observation_fact (episode_id);
            """, null),
        (3, """
            CREATE TABLE IF NOT EXISTS daydream_event_fact (
                event_id        TEXT    NOT NULL PRIMARY KEY,
                task_class      TEXT    NOT NULL,
                schema_version  TEXT    NOT NULL,
                verdict         TEXT    NOT NULL,
                floors          TEXT    NOT NULL,
                shortfalls      TEXT    NOT NULL,
                kind            TEXT    NOT NULL,
                actor           TEXT    NOT NULL,
                detail          TEXT    NULL,
                outcome         TEXT    NULL,
                at              TEXT    NOT NULL,
                sequence        INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS ix_daydream_event_sequence ON daydream_event_fact (sequence);
            """, null),

        // v4: the score segment gains its workspace. Expand-only and nullable - existing rows keep a
        // NULL workspace and read back as an absent one, because the repository a past score was
        // earned in is not recoverable from the row and inventing it would be a backfill that guessed.
        (4, "", ("scored_episode_cell", "workspace", "TEXT NULL")),

        // v5: the evidence channel. Until this, ClosedEpisodeScoring passed HasProofPack as the
        // literal false — an absence asserted without looking, and with nowhere to look. This is
        // where an agent's declared path lands. DECLARED, never verified: the row is what was said,
        // and whether it is true is a separate answer the scoring side derives, because merging the
        // two loses the only evidence that separates a lying agent from a file that moved.
        (5, """
            CREATE TABLE IF NOT EXISTS declared_artifact_fact (
                episode_id   TEXT    NOT NULL,
                path         TEXT    NOT NULL,
                declared_at  TEXT    NOT NULL,
                sequence     INTEGER NOT NULL,
                PRIMARY KEY (episode_id, path, sequence)
            );
            CREATE INDEX IF NOT EXISTS ix_declared_artifact_episode ON declared_artifact_fact (episode_id);
            """, null),

        // v6: the scored cell gains its lane MODE - governed (an ACP lane the plane drove) or
        // observed (a CLI lane the watcher watched). Expand-only and nullable, following v4's shape
        // exactly. A row written before this column existed came through a door nobody recorded, so
        // it reads NULL, meaning "not recorded". There is deliberately NO backfill: inferring
        // "observed" from the absence of a session record would put every unrecorded episode into
        // one confident bucket, and a cohort comparison would then be comparing a guess.
        //
        // MODE IS NOT A PARTITION AXIS. The partition is ScoreSegment(Workspace, TaskClass,
        // SchemaVersion) and a comparison never crosses it; a fourth axis here would split the same
        // work into two cells, which is exactly what R4 forbids. It is an attribute OF the cell.
        (6, "", ("scored_episode_cell", "mode", "TEXT NULL")),

        // v7: the scored cell gains the PROVENANCE of its task class - session-default (the session's
        // declared default, Ruling 72) or operator (chosen for that prompt, Ruling 70). Expand-only
        // and nullable, following v4 and v6 exactly: a row written before this column existed
        // reads NULL, "not recorded", never backfilled. Like mode it is an attribute OF the cell,
        // never a partition axis (ADR-0028's amendment): a defaulted free-form and a chosen free-form
        // rank in one cell, and the board can tell them apart.
        (7, "", ("scored_episode_cell", "task_class_source", "TEXT NULL")),
    ];

    private const string SchemaSql =
        """
        CREATE TABLE watcher_schema_version (
            version    INTEGER NOT NULL PRIMARY KEY,
            applied_at TEXT    NOT NULL
        );

        -- Append-only observation fact. The content-addressed span_id is the primary key, so a
        -- redelivered span is a no-op INSERT OR IGNORE. Grain: one observed operation, once.
        CREATE TABLE observed_span_fact (
            span_id        TEXT NOT NULL PRIMARY KEY,
            session_id     TEXT NOT NULL,
            trace_id       TEXT NOT NULL,
            source_span_id TEXT NOT NULL,
            operation_name TEXT NOT NULL,
            recorded_at    TEXT NOT NULL
        );
        CREATE INDEX ix_observed_span_session ON observed_span_fact (session_id);

        -- Append-only enforcement (DM11): a fact cannot be updated or deleted in place.
        CREATE TRIGGER observed_span_fact_no_update BEFORE UPDATE ON observed_span_fact
        BEGIN SELECT RAISE(ABORT, 'observed_span_fact is append-only'); END;
        CREATE TRIGGER observed_span_fact_no_delete BEFORE DELETE ON observed_span_fact
        BEGIN SELECT RAISE(ABORT, 'observed_span_fact is append-only'); END;

        -- Current-state session metadata (a dimension; harness/model nullable => Not Recorded).
        CREATE TABLE agent_session_dim (
            session_id      TEXT    NOT NULL PRIMARY KEY,
            generation      INTEGER NOT NULL,
            repo_path       TEXT    NOT NULL,
            repo_display    TEXT    NOT NULL,
            worktree_branch TEXT    NOT NULL,
            worktree_path   TEXT    NOT NULL,
            terminal_id     TEXT    NOT NULL,
            agent_name      TEXT    NOT NULL,
            harness_name    TEXT    NULL,
            harness_version TEXT    NULL,
            model_name      TEXT    NULL,
            model_version   TEXT    NULL,
            trust           TEXT    NOT NULL
        );

        -- Latest heartbeat per session (monotonic ticks). Liveness is derived from this, never stored.
        CREATE TABLE session_heartbeat (
            session_id      TEXT    NOT NULL PRIMARY KEY,
            monotonic_ticks INTEGER NOT NULL
        );

        -- The ended flag. Presence means ended; ClearEnded removes it for a fresh generation.
        CREATE TABLE session_ended (
            session_id TEXT NOT NULL PRIMARY KEY
        );

        -- Current-state Work Episode metadata (a lifecycle dimension; slice 4). One row is one episode:
        -- one immutable (goal, done_when, session, generation) over one interval [opened_at, closed_at?].
        -- A reframe closes the current row Superseded and inserts a new row at the next generation.
        CREATE TABLE work_episode_dim (
            episode_id   TEXT    NOT NULL PRIMARY KEY,
            session_id   TEXT    NOT NULL,
            generation   INTEGER NOT NULL,
            goal         TEXT    NOT NULL,
            done_when    TEXT    NOT NULL,
            not_in_scope TEXT    NULL,
            opened_at    TEXT    NOT NULL,
            closed_at    TEXT    NULL,
            outcome      TEXT    NULL
        );
        CREATE INDEX ix_work_episode_session ON work_episode_dim (session_id);

        -- Append-only per-repository Message Board (slice 6). The envelope, order, and thread
        -- references are append-only; only a policy redaction may null the content payload and set
        -- tombstoned, leaving the immutable envelope (spec line 210). Repository-scoped by key.
        CREATE TABLE board_message_fact (
            message_id        TEXT    NOT NULL PRIMARY KEY,
            repository_key    TEXT    NOT NULL,
            kind              TEXT    NOT NULL,
            author_session_id TEXT    NOT NULL,
            author_trust      TEXT    NOT NULL,
            parent_message_id TEXT    NULL,
            content           TEXT    NULL,
            quarantined       INTEGER NOT NULL,
            injection_flagged INTEGER NOT NULL,
            tombstoned        INTEGER NOT NULL,
            recorded_at       TEXT    NOT NULL,
            seq               INTEGER NOT NULL
        );
        CREATE INDEX ix_board_message_repo ON board_message_fact (repository_key);

        -- Materialized scored-episode cache (DM7): a derived value stored so the leaderboard/standing
        -- surfaces read without recomputing. Current-state cell - a recompute UPSERTs and replaces the
        -- child rows; NOT an append-only fact, so it carries no append-only trigger. Rebuildable from
        -- (work_episode_dim + signals) via WeaveScorer; round-trip and rebuildability are tested.
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
            -- The REPOSITORY the work happened in, not the checkout (see WorkspaceKey). NULL for a
            -- row written before v4; such a row is excluded from leaderboard cells rather than
            -- backfilled with a path nobody observed. Declared LAST so a fresh database and one
            -- migrated by ALTER TABLE ADD COLUMN produce the same sqlite_master text.
            workspace         TEXT    NULL,
            -- The LANE MODE this episode came through: 'governed' (an ACP lane) or 'observed' (a CLI
            -- lane). NULL for a row written before v6, meaning "not recorded" - never backfilled.
            -- A cohort attribute, deliberately absent from ScoreSegment. Declared after workspace for
            -- the same reason: a fresh database and one migrated by ALTER TABLE ADD COLUMN must
            -- produce the same sqlite_master text.
            mode              TEXT    NULL,
            -- The PROVENANCE of the task class (v7): 'session-default' or 'operator'. NULL for a
            -- row written before v7 or never stamped - "not recorded", never backfilled. A cohort
            -- attribute beside mode, never inside ScoreSegment. A COPY, deliberately: the source of
            -- truth is the envelope's Current(task_class).source, joined on consumed.episode_id; the
            -- envelope is purgeable work data and scores are not, so after a purge this column is the
            -- provenance's only home (ADR-0033 rule 4, the Simplifier's finding under the D&P condition).
            -- Rebuildable by that join while the envelope exists. Declared LAST, as above.
            task_class_source TEXT    NULL
        );
        CREATE INDEX ix_scored_episode_task ON scored_episode_cell (task_class, schema_version);

        -- Per-dimension child cells, composed back into the Scorecard on read.
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

        -- Tripped-floor child cells.
        CREATE TABLE score_tripped_floor_cell (
            episode_id TEXT NOT NULL,
            floor      TEXT NOT NULL,
            PRIMARY KEY (episode_id, floor)
        );

        -- Append-only operator dispute of a scored episode (US-16 / rule 12): raising a dispute never
        -- overwrites the Scorecard. The Disputed state is DERIVED from the presence of these rows
        -- (DM7), never a stored flag on the score. disputed_dimension NULL means the whole score.
        CREATE TABLE score_dispute_fact (
            dispute_id        TEXT NOT NULL PRIMARY KEY,
            episode_id        TEXT NOT NULL,
            operator_id       TEXT NOT NULL,
            disputed_dimension TEXT NULL,
            reason            TEXT NOT NULL,
            raised_at         TEXT NOT NULL
        );
        CREATE INDEX ix_score_dispute_episode ON score_dispute_fact (episode_id);

        -- Daydream observations (US-9): one occurrence of one pattern in one episode at one time.
        -- A _fact, not a _dim: an observation is never edited, and a re-observation is a NEW row.
        -- The recurrence count is derived on read (DM7) and never stored, so there is exactly one
        -- definition of "how many times". No PRIMARY KEY on episode_id for the same reason - two
        -- rows for one episode must both survive, and the fold deduplicates.
        CREATE TABLE daydream_observation_fact (
            observation_id  TEXT NOT NULL PRIMARY KEY,
            task_class      TEXT NOT NULL,
            schema_version  TEXT NOT NULL,
            verdict         TEXT NOT NULL,
            floors          TEXT NOT NULL,
            shortfalls      TEXT NOT NULL,
            episode_id      TEXT NOT NULL,
            observed_at     TEXT NOT NULL
        );
        CREATE INDEX ix_daydream_observation_episode ON daydream_observation_fact (episode_id);

        -- A candidate's decision history (US-9). The STATE is folded from these and never stored,
        -- so "who promoted this, and when" is answerable rather than lost to an overwrite.
        CREATE TABLE daydream_event_fact (
            event_id        TEXT    NOT NULL PRIMARY KEY,
            task_class      TEXT    NOT NULL,
            schema_version  TEXT    NOT NULL,
            verdict         TEXT    NOT NULL,
            floors          TEXT    NOT NULL,
            shortfalls      TEXT    NOT NULL,
            kind            TEXT    NOT NULL,
            actor           TEXT    NOT NULL,
            detail          TEXT    NULL,
            outcome         TEXT    NULL,
            at              TEXT    NOT NULL,
            sequence        INTEGER NOT NULL
        );
        CREATE INDEX ix_daydream_event_sequence ON daydream_event_fact (sequence);

        -- The evidence channel (v5). Grain: one path one agent named for one episode at one
        -- declaration time. DECLARED, never verified — whether the path exists, sits under
        -- docs/proof/ and is inside the session's repository is a separate answer derived at
        -- scoring time, and the two must not share a column or nobody can afterwards tell an
        -- agent that lied from a file that moved.
        CREATE TABLE declared_artifact_fact (
            episode_id   TEXT    NOT NULL,
            path         TEXT    NOT NULL,
            declared_at  TEXT    NOT NULL,
            sequence     INTEGER NOT NULL,
            PRIMARY KEY (episode_id, path, sequence)
        );
        CREATE INDEX ix_declared_artifact_episode ON declared_artifact_fact (episode_id);

        CREATE TRIGGER score_dispute_fact_no_update BEFORE UPDATE ON score_dispute_fact
        BEGIN SELECT RAISE(ABORT, 'score_dispute_fact is append-only'); END;
        CREATE TRIGGER score_dispute_fact_no_delete BEFORE DELETE ON score_dispute_fact
        BEGIN SELECT RAISE(ABORT, 'score_dispute_fact is append-only'); END;
        """;

    private static void Execute(SqliteConnection connection, string sql)
        => ExecuteNonQuery(connection, sql);

    private static int ExecuteNonQuery(
        SqliteConnection connection, string sql, params (string Name, object? Value)[] parameters)
        => ExecuteNonQuery(connection, sql, null, parameters);

    private static int ExecuteNonQuery(
        SqliteConnection connection, string sql, SqliteTransaction? tx,
        params (string Name, object? Value)[] parameters)
    {
        using var command = connection.CreateCommand();
        command.CommandText = sql;
        command.Transaction = tx;
        foreach (var (name, value) in parameters)
        {
            command.Parameters.AddWithValue(name, value ?? DBNull.Value);
        }

        return command.ExecuteNonQuery();
    }

    private static object? ExecuteScalar(
        SqliteConnection connection, string sql, params (string Name, object? Value)[] parameters)
    {
        using var command = connection.CreateCommand();
        command.CommandText = sql;
        foreach (var (name, value) in parameters)
        {
            command.Parameters.AddWithValue(name, value ?? DBNull.Value);
        }

        return command.ExecuteScalar();
    }
}
