using AiDe.Core.Facts;
using Microsoft.Data.Sqlite;

namespace AiDe.Core.Store;

/// <summary>
/// The single writer's unit of work. Every append allocates the next ingress sequence, which is the
/// total order for all facts — wall-clock never orders anything.
/// </summary>
/// <remarks>
/// Pattern: Unit of Work. The writer deliberately exposes no general SQL surface and never uses
/// INSERT OR REPLACE / UPSERT on a fact table: REPLACE is the documented bypass of the immutability
/// triggers (spike S4), so forbidding it in the writer API is the control, and the pragma is the net.
/// </remarks>
public sealed class StoreWriter : IDisposable
{
    private readonly SqliteConnection _connection;
    private readonly SemaphoreSlim _gate;
    private readonly SqliteTransaction _transaction;
    private bool _completed;

    internal StoreWriter(SqliteConnection connection, SemaphoreSlim gate)
    {
        _connection = connection;
        _gate = gate;
        _transaction = connection.BeginTransaction();
    }

    /// <summary>Allocates the next total-order position. Monotonic within the workspace.</summary>
    public long NextIngressSequence()
    {
        WorkspaceStore.Execute(_connection, "UPDATE core_state SET ingress_seq = ingress_seq + 1 WHERE id = 1;", _transaction);
        return Convert.ToInt64(WorkspaceStore.ExecuteScalar(
            _connection, "SELECT ingress_seq FROM core_state WHERE id = 1;", _transaction));
    }

    public void DesireScopeGeneration(string scopeId, long generation, string artifactRevision)
    {
        var seq = NextIngressSequence();
        Exec("""
            INSERT INTO scope_generation_desired_fact
                (scope_id, generation, artifact_revision, requested_at, ingress_seq)
            VALUES ($scope, $gen, $rev, $at, $seq);
            """,
            ("$scope", scopeId), ("$gen", generation), ("$rev", artifactRevision),
            ("$at", WorkspaceStore.Iso(DateTimeOffset.UtcNow)), ("$seq", seq));
    }

    /// <summary>The latest desired (generation, revision) pair for a scope, or null if none.</summary>
    public (long Generation, string ArtifactRevision)? ReadDesired(string scopeId)
    {
        using var command = _connection.CreateCommand();
        command.Transaction = _transaction;
        command.CommandText = """
            SELECT generation, artifact_revision FROM scope_generation_desired_fact
            WHERE scope_id = $scope ORDER BY generation DESC LIMIT 1;
            """;
        command.Parameters.AddWithValue("$scope", scopeId);
        using var reader = command.ExecuteReader();
        return reader.Read() ? (reader.GetInt64(0), reader.GetString(1)) : null;
    }

    /// <summary>
    /// Commits a complete snapshot and its assertions in ONE transaction, but only when the worker's
    /// (generation, revision) pair still equals the durable desired pair. A late or stale worker is
    /// rejected here rather than being allowed to remove newer evidence.
    /// </summary>
    public void CommitSnapshot(
        string scopeId, long generation, string artifactRevision,
        IReadOnlyList<EvidenceAssertion> assertions, bool complete)
    {
        var desired = ReadDesired(scopeId)
            ?? throw new WorkspaceStoreException(StoreErrorCodes.ScopeGenerationStale,
                $"scope '{scopeId}' has no desired generation");

        if (desired.Generation != generation || desired.ArtifactRevision != artifactRevision)
        {
            throw new WorkspaceStoreException(StoreErrorCodes.ScopeGenerationStale,
                $"scope '{scopeId}' generation {generation}/{artifactRevision} is not the desired " +
                $"{desired.Generation}/{desired.ArtifactRevision}");
        }

        foreach (var assertion in assertions)
        {
            var seq = NextIngressSequence();
            Exec("""
                INSERT INTO evidence_assertion_fact
                    (assertion_id, scope_id, generation, artifact_revision, subject, predicate, object,
                     origin, status, artifact_path_id, source_location, extractor_id, extractor_version,
                     observed_at, ingress_seq)
                VALUES ($id, $scope, $gen, $rev, $s, $p, $o, $origin, $status, $path, $loc, $ex, $exv, $obs, $seq);
                """,
                ("$id", assertion.AssertionId), ("$scope", assertion.ScopeId), ("$gen", generation),
                ("$rev", assertion.ArtifactRevision), ("$s", assertion.Subject),
                ("$p", assertion.Predicate), ("$o", assertion.Object),
                ("$origin", assertion.Origin.ToString()), ("$status", assertion.Status.ToString()),
                ("$path", assertion.Provenance.ArtifactPathId), ("$loc", assertion.Provenance.SourceLocation),
                ("$ex", assertion.Provenance.ExtractorId), ("$exv", assertion.Provenance.ExtractorVersion),
                ("$obs", WorkspaceStore.Iso(assertion.Provenance.ObservedAt)), ("$seq", seq));
        }

        var commitSeq = NextIngressSequence();
        Exec("""
            INSERT INTO scope_snapshot_committed_fact
                (scope_id, generation, artifact_revision, assertion_count, complete, committed_at, ingress_seq)
            VALUES ($scope, $gen, $rev, $count, $complete, $at, $seq);
            """,
            ("$scope", scopeId), ("$gen", generation), ("$rev", artifactRevision),
            ("$count", assertions.Count), ("$complete", complete ? 1 : 0),
            ("$at", WorkspaceStore.Iso(DateTimeOffset.UtcNow)), ("$seq", commitSeq));
    }

    /// <summary>Records a completed command. Its uniqueness is what makes a retry return the original outcome.</summary>
    public void RecordCommandReceipt(
        string workspaceId, CallerPrincipal caller, string commandType, string commandId,
        string outcome, string? errorCode)
    {
        var seq = NextIngressSequence();
        Exec("""
            INSERT INTO command_receipt_fact
                (workspace_id, caller_principal, command_type, command_id, outcome, error_code, recorded_at, ingress_seq)
            VALUES ($ws, $caller, $type, $id, $outcome, $err, $at, $seq);
            """,
            ("$ws", workspaceId), ("$caller", caller.Id), ("$type", commandType), ("$id", commandId),
            ("$outcome", outcome), ("$err", errorCode),
            ("$at", WorkspaceStore.Iso(DateTimeOffset.UtcNow)), ("$seq", seq));
    }

    /// <summary>The write-ahead half of ADR-0010: durable BEFORE any byte leaves the process.</summary>
    public void RecordDispatchAttempt(
        string dispatchKey, string workspaceId, long workspaceEpoch, string draftId, int revisionNo,
        string sessionId, long sessionGeneration)
    {
        var seq = NextIngressSequence();
        Exec("""
            INSERT INTO dispatch_attempt_fact
                (dispatch_key, workspace_id, workspace_epoch, draft_id, revision_no,
                 session_id, session_generation, attempted_at, ingress_seq)
            VALUES ($key, $ws, $epoch, $draft, $rev, $session, $gen, $at, $seq);
            """,
            ("$key", dispatchKey), ("$ws", workspaceId), ("$epoch", workspaceEpoch),
            ("$draft", draftId), ("$rev", revisionNo), ("$session", sessionId), ("$gen", sessionGeneration),
            ("$at", WorkspaceStore.Iso(DateTimeOffset.UtcNow)), ("$seq", seq));
    }

    /// <summary>Appends an outcome event. Never rewrites a prior row — a late acceptance appends.</summary>
    public void RecordDispatchOutcome(string dispatchKey, DispatchState state, string? errorCode)
    {
        var seq = NextIngressSequence();
        Exec("""
            INSERT INTO dispatch_outcome_fact (dispatch_key, ingress_seq, state, error_code, recorded_at)
            VALUES ($key, $seq, $state, $err, $at);
            """,
            ("$key", dispatchKey), ("$seq", seq), ("$state", state.ToString()),
            ("$err", errorCode), ("$at", WorkspaceStore.Iso(DateTimeOffset.UtcNow)));
    }

    public void SavePromptRevision(string draftId, int revisionNo, string body)
    {
        var seq = NextIngressSequence();
        Exec("""
            INSERT INTO prompt_revision_fact (draft_id, revision_no, body, saved_at, ingress_seq)
            VALUES ($draft, $rev, $body, $at, $seq);
            """,
            ("$draft", draftId), ("$rev", revisionNo), ("$body", body),
            ("$at", WorkspaceStore.Iso(DateTimeOffset.UtcNow)), ("$seq", seq));
    }

    public void UpsertSession(string sessionId, long generation, SessionProcessingClass processingClass, string displayName)
    {
        var seq = NextIngressSequence();
        // Dimension, not a fact: a generation/class change closes the old version and opens a new one
        // (Type-2), so an egress decision is never re-read under a newer class.
        Exec("UPDATE session_dim SET valid_to_seq = $seq WHERE session_id = $id AND valid_to_seq IS NULL;",
            ("$seq", seq), ("$id", sessionId));
        Exec("""
            INSERT INTO session_dim (session_id, generation, processing_class, display_name, valid_from_seq, valid_to_seq)
            VALUES ($id, $gen, $class, $name, $seq, NULL);
            """,
            ("$id", sessionId), ("$gen", generation), ("$class", processingClass.ToString()),
            ("$name", displayName), ("$seq", seq));
    }

    /// <summary>
    /// Records a node's kind and label, closing the previous row when either changes.
    /// </summary>
    /// <remarks>
    /// <para><b>Unchanged is a NO-OP, deliberately.</b> This is a Type-2 dimension: every call used
    /// to close the current row and open a new one, so re-indexing a workspace rewrote the history
    /// of every node that had not changed. History whose every row is an artefact of re-running the
    /// indexer cannot answer the question it exists for — "when did this change?" — because the
    /// answer is always "just now".</para>
    ///
    /// <para>It also removed a flip-flop: while a node's kind was computed per scope, a node
    /// declared by one scope and referenced by another alternated between rows on every index.</para>
    /// </remarks>
    public void UpsertNode(string nodeId, string nodeKind, string displayLabel)
    {
        // One scalar rather than a reader: both fields are compared as a pair, so the cheapest
        // question is simply whether the CURRENT row already says exactly this.
        var unchanged = WorkspaceStore.ExecuteScalar(
            _connection,
            "SELECT 1 FROM node_dim WHERE node_id = $id AND valid_to_seq IS NULL "
            + "AND node_kind = $kind AND display_label = $label;",
            _transaction,
            ("$id", nodeId), ("$kind", nodeKind), ("$label", displayLabel));

        if (unchanged is not null) return;

        var seq = NextIngressSequence();
        Exec("UPDATE node_dim SET valid_to_seq = $seq WHERE node_id = $id AND valid_to_seq IS NULL;",
            ("$seq", seq), ("$id", nodeId));
        Exec("""
            INSERT INTO node_dim (node_id, node_kind, display_label, valid_from_seq, valid_to_seq)
            VALUES ($id, $kind, $label, $seq, NULL);
            """,
            ("$id", nodeId), ("$kind", nodeKind), ("$label", displayLabel), ("$seq", seq));
    }

    public void Commit()
    {
        _transaction.Commit();
        _completed = true;
    }

    /// <summary>Raw SQL on the real writer connection — test-only, so the pragma control can be proven where it lives.</summary>
    internal void ExecuteRawInternal(string sql) => Exec(sql);

    private void Exec(string sql, params (string Name, object? Value)[] parameters)
    {
        try
        {
            WorkspaceStore.Execute(_connection, sql, _transaction, parameters);
        }
        catch (SqliteException ex) when (ex.Message.Contains(StoreErrorCodes.ImmutableViolation, StringComparison.Ordinal))
        {
            throw new WorkspaceStoreException(StoreErrorCodes.ImmutableViolation,
                "facts are append-only; correction is a superseding fact", ex);
        }
    }

    public void Dispose()
    {
        if (!_completed)
        {
            _transaction.Rollback();
        }

        _transaction.Dispose();
        _gate.Release();
    }
}
