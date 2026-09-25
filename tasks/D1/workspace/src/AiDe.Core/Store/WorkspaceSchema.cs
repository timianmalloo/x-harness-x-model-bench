namespace AiDe.Core.Store;

/// <summary>
/// Schema v1 for one workspace. Dimensions hold stable identities, facts are append-only, and
/// anything derived is a labelled rebuildable cache (the only tables without immutability triggers).
/// </summary>
internal static class WorkspaceSchema
{
    internal const int Version = 1;

    /// <summary>
    /// Fact tables. Each gets BEFORE UPDATE / BEFORE DELETE aborts. Kept as a list so the trigger
    /// set cannot drift from the table set — adding a fact table without its trigger is the defect
    /// this loop prevents.
    /// </summary>
    internal static readonly string[] FactTables =
    [
        "evidence_assertion_fact",
        "scope_generation_desired_fact",
        "scope_snapshot_committed_fact",
        "command_receipt_fact",
        "dispatch_attempt_fact",
        "dispatch_outcome_fact",
        "prompt_revision_fact",
    ];

    internal const string CreateSql = """
        CREATE TABLE schema_version (
            version     INTEGER NOT NULL PRIMARY KEY,
            applied_at  TEXT    NOT NULL
        );

        -- Single-row control table. ingress_seq is the total order for every fact: wall-clock is
        -- display metadata only, so clock skew can never reorder evidence.
        CREATE TABLE core_state (
            id          INTEGER NOT NULL PRIMARY KEY CHECK (id = 1),
            core_epoch  INTEGER NOT NULL,
            ingress_seq INTEGER NOT NULL
        );

        ---------------------------------------------------------------- dimensions
        CREATE TABLE workspace_dim (
            workspace_id   TEXT    NOT NULL,
            workspace_key  INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            root_path      TEXT    NOT NULL,   -- Type-2: a changed root rewrites past meaning
            display_name   TEXT    NOT NULL,   -- Type-1: cosmetic
            valid_from_seq INTEGER NOT NULL,
            valid_to_seq   INTEGER NULL
        );
        CREATE UNIQUE INDEX ux_workspace_current
            ON workspace_dim (workspace_id) WHERE valid_to_seq IS NULL;

        CREATE TABLE node_dim (
            node_id        TEXT    NOT NULL,
            node_key       INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            node_kind      TEXT    NOT NULL,   -- Type-2: source <-> knowledge changes interpretation
            display_label  TEXT    NOT NULL,   -- Type-1
            valid_from_seq INTEGER NOT NULL,
            valid_to_seq   INTEGER NULL
        );
        CREATE UNIQUE INDEX ux_node_current
            ON node_dim (node_id) WHERE valid_to_seq IS NULL;

        CREATE TABLE session_dim (
            session_id       TEXT    NOT NULL,
            session_key      INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            generation       INTEGER NOT NULL,  -- Type-2
            processing_class TEXT    NOT NULL,  -- Type-2: an egress decision must not be re-read
                                                --         under a newer class
            display_name     TEXT    NOT NULL,  -- Type-1
            valid_from_seq   INTEGER NOT NULL,
            valid_to_seq     INTEGER NULL
        );
        CREATE UNIQUE INDEX ux_session_current
            ON session_dim (session_id) WHERE valid_to_seq IS NULL;

        ---------------------------------------------------------------- facts (append-only)
        -- Grain: one request to extract one scope at one desired generation + artifact revision.
        CREATE TABLE scope_generation_desired_fact (
            scope_id          TEXT    NOT NULL,
            generation        INTEGER NOT NULL,
            artifact_revision TEXT    NOT NULL,
            requested_at      TEXT    NOT NULL,
            ingress_seq       INTEGER NOT NULL,
            PRIMARY KEY (scope_id, generation)
        );

        -- Grain: one commit of one complete snapshot for one scope generation.
        CREATE TABLE scope_snapshot_committed_fact (
            scope_id          TEXT    NOT NULL,
            generation        INTEGER NOT NULL,
            artifact_revision TEXT    NOT NULL,
            assertion_count   INTEGER NOT NULL,  -- semi-additive: NEVER summed across generations
            complete          INTEGER NOT NULL,
            committed_at      TEXT    NOT NULL,
            ingress_seq       INTEGER NOT NULL,
            PRIMARY KEY (scope_id, generation),
            FOREIGN KEY (scope_id, generation)
                REFERENCES scope_generation_desired_fact (scope_id, generation)
        );

        -- Grain: one assertion by one extractor about one normalized relation at one revision.
        CREATE TABLE evidence_assertion_fact (
            assertion_id      TEXT    NOT NULL PRIMARY KEY,
            scope_id          TEXT    NOT NULL,
            generation        INTEGER NOT NULL,
            artifact_revision TEXT    NOT NULL,
            subject           TEXT    NOT NULL,
            predicate         TEXT    NOT NULL,
            object            TEXT    NOT NULL,
            origin            TEXT    NOT NULL,
            status            TEXT    NOT NULL,
            artifact_path_id  TEXT    NOT NULL,
            source_location   TEXT    NULL,
            extractor_id      TEXT    NOT NULL,
            extractor_version TEXT    NOT NULL,
            observed_at       TEXT    NOT NULL,
            ingress_seq       INTEGER NOT NULL
        );
        CREATE UNIQUE INDEX ux_assertion_natural ON evidence_assertion_fact
            (scope_id, artifact_revision, subject, predicate, object, extractor_id);
        -- Bounded traversal indexes. The traversal column LEADS: a lookup is always "this node,
        -- in whichever scope/generation is current", so scope_id first would force a scan for the
        -- node predicate. P1-PERF-04 asserts these are the plans actually chosen.
        CREATE INDEX ix_assertion_subject   ON evidence_assertion_fact (subject, scope_id, generation);
        CREATE INDEX ix_assertion_object    ON evidence_assertion_fact (object, scope_id, generation);
        -- Serves the knowledge projection, which selects by predicate ('has_type', 'owned_by').
        CREATE INDEX ix_assertion_predicate ON evidence_assertion_fact (predicate, scope_id, generation);

        -- Grain: one COMPLETED mutating command for one idempotency key. Single grain because the
        -- effect and the receipt commit in one transaction; only dispatch needs two grains.
        CREATE TABLE command_receipt_fact (
            workspace_id     TEXT    NOT NULL,
            caller_principal TEXT    NOT NULL,
            command_type     TEXT    NOT NULL,
            command_id       TEXT    NOT NULL,
            outcome          TEXT    NOT NULL,
            error_code       TEXT    NULL,
            recorded_at      TEXT    NOT NULL,
            ingress_seq      INTEGER NOT NULL,
            PRIMARY KEY (workspace_id, caller_principal, command_type, command_id)
        );

        -- Grain: one ATTEMPT to deliver one prompt revision to one session generation.
        -- Written BEFORE the PTY write; this row is what makes at-most-once true across a crash.
        CREATE TABLE dispatch_attempt_fact (
            dispatch_key       TEXT    NOT NULL PRIMARY KEY,
            workspace_id       TEXT    NOT NULL,
            workspace_epoch    INTEGER NOT NULL,
            draft_id           TEXT    NOT NULL,
            revision_no        INTEGER NOT NULL,
            session_id         TEXT    NOT NULL,
            session_generation INTEGER NOT NULL,
            attempted_at       TEXT    NOT NULL,
            ingress_seq        INTEGER NOT NULL
        );

        -- Grain: one OUTCOME EVENT for one dispatch key. Append-only, so a late AgentAccepted
        -- appends rather than rewriting an immutable row.
        CREATE TABLE dispatch_outcome_fact (
            dispatch_key TEXT    NOT NULL,
            ingress_seq  INTEGER NOT NULL,
            state        TEXT    NOT NULL,
            error_code   TEXT    NULL,
            recorded_at  TEXT    NOT NULL,
            PRIMARY KEY (dispatch_key, ingress_seq),
            FOREIGN KEY (dispatch_key) REFERENCES dispatch_attempt_fact (dispatch_key)
        );

        CREATE TABLE prompt_revision_fact (
            draft_id    TEXT    NOT NULL,
            revision_no INTEGER NOT NULL,
            body        TEXT    NOT NULL,
            saved_at    TEXT    NOT NULL,
            ingress_seq INTEGER NOT NULL,
            PRIMARY KEY (draft_id, revision_no)
        );

        ---------------------------------------------------------------- rebuildable cache
        -- LABELLED CACHE, not a fact: mutable by design and provably equal to its derivation
        -- (see ClaimProjection rebuild-equality test). No immutability triggers here.
        CREATE TABLE claim_current_cache (
            subject         TEXT    NOT NULL,
            predicate       TEXT    NOT NULL,
            object          TEXT    NOT NULL,
            status          TEXT    NOT NULL,
            assertion_count INTEGER NOT NULL,
            source_revision TEXT    NOT NULL,
            PRIMARY KEY (subject, predicate, object)
        );
        """;

    /// <summary>
    /// Immutability triggers. Correction is a superseding fact, never an in-place edit.
    /// NOTE: these are only half the control — <c>PRAGMA recursive_triggers=ON</c> is required on
    /// every writer connection, because with the SQLite default OFF an <c>INSERT OR REPLACE</c>
    /// resolves its conflict with an internal delete that does NOT fire the BEFORE DELETE trigger
    /// and silently overwrites the row (spikes/sqlite-fact-store, case S4; S5 shows the pragma
    /// closes it). The single-writer core process is the real boundary; this is defense in depth.
    /// </summary>
    internal static string TriggerSql() =>
        string.Concat(FactTables.Select(t => $"""
            CREATE TRIGGER trg_{t}_no_update BEFORE UPDATE ON {t}
                BEGIN SELECT RAISE(ABORT, 'AIDE-STORE-IMMUTABLE-VIOLATION'); END;
            CREATE TRIGGER trg_{t}_no_delete BEFORE DELETE ON {t}
                BEGIN SELECT RAISE(ABORT, 'AIDE-STORE-IMMUTABLE-VIOLATION'); END;

            """));
}
