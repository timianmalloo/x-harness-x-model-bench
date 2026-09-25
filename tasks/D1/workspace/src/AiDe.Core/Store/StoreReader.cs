using System.Globalization;
using AiDe.Core.Extraction;
using AiDe.Core.Facts;
using Microsoft.Data.Sqlite;

namespace AiDe.Core.Store;

/// <summary>
/// A snapshot read. The connection is pinned <c>query_only=1</c>, so this path cannot write even by
/// accident (spike S6).
/// </summary>
public sealed class StoreReader : IDisposable
{
    private readonly SqliteConnection _connection;

    internal StoreReader(SqliteConnection connection) => _connection = connection;

    /// <summary>The latest committed generation for a scope, or null if nothing complete exists yet.</summary>
    public (long Generation, string ArtifactRevision, int AssertionCount)? LatestCommittedSnapshot(string scopeId)
    {
        using var command = Command("""
            SELECT generation, artifact_revision, assertion_count
            FROM scope_snapshot_committed_fact
            WHERE scope_id = $scope AND complete = 1
            ORDER BY generation DESC LIMIT 1;
            """, ("$scope", scopeId));
        using var reader = command.ExecuteReader();
        return reader.Read() ? (reader.GetInt64(0), reader.GetString(1), reader.GetInt32(2)) : null;
    }

    /// <summary>
    /// Current evidence for a scope: assertions of the latest COMPLETE snapshot only. A partial or
    /// superseded snapshot never contributes, so the graph cannot silently mix generations.
    /// </summary>
    public IReadOnlyList<StoredAssertion> CurrentAssertions(string scopeId)
    {
        var latest = LatestCommittedSnapshot(scopeId);
        if (latest is null)
        {
            return [];
        }

        using var command = Command("""
            SELECT assertion_id, scope_id, artifact_revision, subject, predicate, object, origin, status,
                   artifact_path_id, source_location, extractor_id, extractor_version, observed_at
            FROM evidence_assertion_fact
            WHERE scope_id = $scope AND generation = $gen
            ORDER BY subject, predicate, object;
            """, ("$scope", scopeId), ("$gen", latest.Value.Generation));
        return ReadAssertions(command);
    }

    /// <summary>
    /// The "current generation" filter every bounded read composes with: one row per scope, so the
    /// join stays tiny while the traversal predicate drives the index.
    /// </summary>
    private const string LatestCte = """
        WITH latest AS (
            SELECT scope_id, max(generation) AS generation
            FROM scope_snapshot_committed_fact WHERE complete = 1 GROUP BY scope_id
        )
        """;

    private const string AssertionColumns = """
        a.assertion_id, a.scope_id, a.artifact_revision, a.subject, a.predicate, a.object,
        a.origin, a.status, a.artifact_path_id, a.source_location, a.extractor_id,
        a.extractor_version, a.observed_at
        """;

    /// <summary>Assertions where the node is the subject OR the object, bounded in SQL.</summary>
    /// <remarks>
    /// Deliberately a UNION ALL of two single-column lookups rather than one <c>OR</c> predicate:
    /// SQLite will not use two different indexes to satisfy one OR, so the OR form degrades into
    /// the full scan this method exists to avoid (measured, P1-PERF 2026-08-26).
    /// </remarks>
    public IReadOnlyList<StoredAssertion> AssertionsTouching(string nodeId, int limit)
    {
        using var command = Command($"""
            {LatestCte}
            SELECT * FROM (
                SELECT {AssertionColumns} FROM evidence_assertion_fact a
                JOIN latest l ON l.scope_id = a.scope_id AND l.generation = a.generation
                WHERE a.subject = $node
                UNION ALL
                SELECT {AssertionColumns} FROM evidence_assertion_fact a
                JOIN latest l ON l.scope_id = a.scope_id AND l.generation = a.generation
                WHERE a.object = $node AND a.subject <> $node
            )
            -- IDENTITY FIRST, then what this node points at, then what points at it.
            --
            -- This was `ORDER BY subject, predicate, object` — alphabetical, which is deterministic
            -- and says nothing about importance. A node with more facts than the cap therefore lost
            -- its own type and owner to its own links, and lost them in alphabetical order, so WHICH
            -- facts survived depended on how the node happened to be named. MEASURED: 12 of 877
            -- knowledge documents were already over this ceiling before anything was added to them.
            --
            -- The bands are coarse on purpose. Identity is a handful of facts that answer "what is
            -- this"; everything else competes behind it, still alphabetically, so the result stays
            -- deterministic and the omission count still means what it says.
            ORDER BY
                CASE
                    WHEN subject = $node AND predicate IN ({AiDe.Core.Facts.EvidencePredicates.IdentitySqlList}) THEN 0
                    WHEN subject = $node THEN 1
                    ELSE 2
                END,
                subject, predicate, object
            LIMIT $limit;
            """, ("$node", nodeId), ("$limit", limit));
        return ReadAssertions(command);
    }

    /// <summary>Total assertions touching a node, so a bounded read can report what it omitted.</summary>
    public int CountAssertionsTouching(string nodeId)
    {
        using var command = Command($"""
            {LatestCte}
            SELECT
              (SELECT count(*) FROM evidence_assertion_fact a
                 JOIN latest l ON l.scope_id = a.scope_id AND l.generation = a.generation
                 WHERE a.subject = $node)
            + (SELECT count(*) FROM evidence_assertion_fact a
                 JOIN latest l ON l.scope_id = a.scope_id AND l.generation = a.generation
                 WHERE a.object = $node AND a.subject <> $node);
            """, ("$node", nodeId));
        return Convert.ToInt32(command.ExecuteScalar());
    }

    /// <summary>Outgoing edges only — one traversal step of a bounded impact walk.</summary>
    public IReadOnlyList<StoredAssertion> OutgoingAssertions(string nodeId, int limit)
    {
        using var command = Command($"""
            {LatestCte}
            SELECT {AssertionColumns} FROM evidence_assertion_fact a
            JOIN latest l ON l.scope_id = a.scope_id AND l.generation = a.generation
            WHERE a.subject = $node
            ORDER BY a.object
            LIMIT $limit;
            """, ("$node", nodeId), ("$limit", limit));
        return ReadAssertions(command);
    }

    /// <summary>Assertions with a given predicate — the knowledge projection's entry point.</summary>
    /// <summary>
    /// The assertion that says where a node was DECLARED — its scope and its path within it.
    /// </summary>
    /// <remarks>
    /// <para>Asked of the store rather than picked out of a neighbour list, because a neighbour list
    /// is capped. The content reader first filtered <c>AssertionsTouching(id, 50)</c> for the fact
    /// carrying a path, and on a node with 244 edges that fact was not among the first 50 — so the
    /// most connected types in a real workspace reported "no recorded source" while the least
    /// connected ones worked. DC-035, in code written the same day the class was recorded twice.</para>
    ///
    /// <para>Ordered so a declaration wins over a mention: <c>has_type</c> and <c>declared_in</c> are
    /// what a producer emits ABOUT a thing it declared, and their provenance is that thing's own
    /// file. Any other assertion's path is where it was REFERRED to.</para>
    /// </remarks>
    public StoredAssertion? DeclaringAssertion(string nodeId)
    {
        using var command = Command($"""
            {LatestCte}
            SELECT {AssertionColumns} FROM evidence_assertion_fact a
            JOIN latest l ON l.scope_id = a.scope_id AND l.generation = a.generation
            WHERE a.subject = $node AND a.artifact_path_id <> ''
            ORDER BY CASE a.predicate WHEN 'has_type' THEN 0 WHEN 'declared_in' THEN 1 ELSE 2 END,
                     a.artifact_path_id
            LIMIT 1;
            """, ("$node", nodeId));

        return ReadAssertions(command).FirstOrDefault();
    }

    /// <summary>
    /// One caller's outgoing calls, in the order they are written.
    /// </summary>
    /// <remarks>
    /// <para>The interaction, as opposed to the relationship. <c>calls</c> is deduplicated to one
    /// row per <c>(caller, callee)</c> pair — right for a graph, where the same relationship written
    /// seven times is one arrow, and wrong for a sequence diagram, where <c>A→B, A→C, A→B</c> must
    /// stay three messages. A diagram that silently drops a repeat is confidently incomplete.</para>
    ///
    /// <para><b>Ordered by source position, because that is the only order there is.</b> No ordinal
    /// column was added: every assertion already carries <c>source_location</c> as <c>line:col</c>,
    /// and a call sequence has exactly one correct order — the order it is written in. Sorted
    /// numerically rather than as text, or line 10 would come before line 9.</para>
    /// </remarks>
    public IReadOnlyList<(string Callee, string Member, string Location)> OutgoingCallsInOrder(
        string caller, int limit)
    {
        using var command = Command($"""
            {LatestCte}
            SELECT a.object, a.source_location FROM evidence_assertion_fact a
            JOIN latest l ON l.scope_id = a.scope_id AND l.generation = a.generation
            WHERE a.subject = $caller AND a.predicate = 'calls_at'
            ORDER BY
              CAST(SUBSTR(a.source_location, 1, INSTR(a.source_location, ':') - 1) AS INTEGER),
              CAST(SUBSTR(a.source_location, INSTR(a.source_location, ':') + 1) AS INTEGER),
              a.object
            LIMIT $limit;
            """, ("$caller", caller), ("$limit", limit));

        using var reader = command.ExecuteReader();
        var calls = new List<(string, string, string)>();

        while (reader.Read())
        {
            var value = reader.GetString(0);
            var location = reader.IsDBNull(1) ? string.Empty : reader.GetString(1);

            // `Type#Member`. `#` cannot occur in a C# display string, so the split is total — but a
            // value without one is returned whole as the callee rather than silently dropped: a fact
            // this reader cannot parse is a fact somebody else wrote, and losing it quietly is how a
            // diagram ends up missing a message nobody can account for.
            // `Type#Member@line:col`. The position is in the value because the store's natural key
            // would otherwise fold two identical call sites into one fact (P1-STORE-05) — and an
            // interaction is precisely a record of things that happened more than once.
            var at = value.LastIndexOf('@');
            var body = at < 0 ? value : value[..at];

            var hash = body.LastIndexOf('#');

            calls.Add(hash < 0
                ? (body, string.Empty, location)
                : (body[..hash], body[(hash + 1)..], location));
        }

        return calls;
    }

    /// <summary>
    /// The distinct files the graph knows about, each with a node that is declared in it.
    /// </summary>
    /// <remarks>
    /// <para>The corpus a content search may read. It is the set of files the EXTRACTORS chose to
    /// index, not the directory tree: walking the tree would open <c>node_modules</c>, <c>bin</c>
    /// and every generated bundle the readers already decided to skip, and would return hits in
    /// files the graph cannot navigate to — a result nobody can act on.</para>
    ///
    /// <para>One representative node per file, chosen the same way <see cref="DeclaringAssertion"/>
    /// chooses one: a declaration before a reference, then lowest id for determinism. A file holds
    /// many nodes and the hit needs somewhere to go, not everywhere it could go.</para>
    /// </remarks>
    public IReadOnlyList<(string NodeId, string ScopeId, string ArtifactPath)> FilesToSearch(int limit) =>
        ReadFilesToSearch(limit);

    /// <summary>
    /// Same grain as <see cref="FilesToSearch(int)"/> with no silent LIMIT — the tree projection
    /// ranks and omits, and a store cap would drop files without <c>OmittedByCap</c>.
    /// </summary>
    public IReadOnlyList<(string NodeId, string ScopeId, string ArtifactPath)> FilesToSearch() =>
        ReadFilesToSearch(limit: null);

    private IReadOnlyList<(string NodeId, string ScopeId, string ArtifactPath)> ReadFilesToSearch(int? limit)
    {
        var sql = $"""
            {LatestCte}
            SELECT a.scope_id, a.artifact_path_id, MIN(a.subject) AS node
            FROM evidence_assertion_fact a
            JOIN latest l ON l.scope_id = a.scope_id AND l.generation = a.generation
            WHERE a.artifact_path_id <> '' AND a.predicate IN ('has_type', 'declared_in')
            GROUP BY a.scope_id, a.artifact_path_id
            ORDER BY a.scope_id, a.artifact_path_id
            """;
        using var command = limit is { } cap
            ? Command(sql + "\nLIMIT $limit;", ("$limit", cap))
            : Command(sql + ";");

        using var reader = command.ExecuteReader();
        var files = new List<(string, string, string)>();

        while (reader.Read())
        {
            files.Add((reader.GetString(2), reader.GetString(0), reader.GetString(1)));
        }

        return files;
    }

    /// <summary>
    /// Where a scope's files live, relative to the workspace root, or null when it never said.
    /// </summary>
    /// <remarks>
    /// Written by the core when it indexes a scope, because the core is what chose the path. An
    /// empty string is a real answer — the scope IS the workspace root — and is distinct from null,
    /// which means nothing recorded it and no content can be resolved.
    /// </remarks>
    public string? ScopeLocation(string scopeId)
    {
        using var command = Command($"""
            {LatestCte}
            SELECT a.object FROM evidence_assertion_fact a
            JOIN latest l ON l.scope_id = a.scope_id AND l.generation = a.generation
            WHERE a.subject = $scope AND a.predicate = 'declared_at'
            LIMIT 1;
            """, ("$scope", scopeId));

        return command.ExecuteScalar() as string;
    }

    /// <summary>Every latest-generation <c>declared_at</c>, so coverage can join without a second walk.</summary>
    public IReadOnlyList<(string ScopeId, string DeclaredAt)> AllScopeLocations()
    {
        using var command = Command($"""
            {LatestCte}
            SELECT a.subject, a.object FROM evidence_assertion_fact a
            JOIN latest l ON l.scope_id = a.scope_id AND l.generation = a.generation
            WHERE a.predicate = 'declared_at';
            """);

        using var reader = command.ExecuteReader();
        var locations = new List<(string, string)>();
        while (reader.Read())
        {
            locations.Add((reader.GetString(0), reader.GetString(1)));
        }

        return locations;
    }

    /// <summary>
    /// The ids currently classified as knowledge.
    /// </summary>
    /// <remarks>
    /// <c>node_kind</c> is the dimension that separates knowledge from source — the one thing that
    /// knows, now that <c>has_type</c> is emitted by six extractors and says nothing about which
    /// half of the graph a node belongs to (INV-0004).
    /// </remarks>
    /// <summary>
    /// The knowledge nodes a query asks for, with their declared type, and how many matched in all.
    /// </summary>
    /// <remarks>
    /// <para><b>The term and the type are applied HERE, not to the result.</b> The caller used to
    /// take 200 knowledge ids in id order and then filter them by term in memory, so a search only
    /// ever saw the alphabetically first 200 of 1,255 — and a document whose id sorted later was
    /// reported as not existing. That is DC-035 for the third time in this file: a bounded read
    /// whose filter is applied to the RESULT of the read rather than expressed in it.</para>
    ///
    /// <para>The total is counted over the same filtered set, so a caller can say what it left out
    /// instead of presenting a truncation as an answer.</para>
    /// </remarks>
    public (IReadOnlyList<(string NodeId, string Type)> Rows, int TotalMatched) KnowledgeNodes(
        string? term, string? type, int limit)
    {
        using var command = Command($"""
            {LatestCte}
            SELECT n.node_id, a.object AS declared_type
            FROM node_dim n
            JOIN evidence_assertion_fact a ON a.subject = n.node_id AND a.predicate = 'has_type'
            JOIN latest l ON l.scope_id = a.scope_id AND l.generation = a.generation
            WHERE n.node_kind = 'knowledge' AND n.valid_to_seq IS NULL
              AND ($term IS NULL OR n.node_id LIKE $pattern)
              AND ($type IS NULL OR a.object = $type COLLATE NOCASE)
            GROUP BY n.node_id
            ORDER BY n.node_id;
            """,
            ("$term", term), ("$pattern", term is null ? null : $"%{term}%"), ("$type", type));

        using var reader = command.ExecuteReader();
        var all = new List<(string, string)>();

        while (reader.Read())
        {
            all.Add((reader.GetString(0), reader.GetString(1)));
        }

        return (all.Count > limit ? all[..limit] : all, all.Count);
    }

    /// <summary>
    /// Latest-generation source <c>has_type</c> nodes (not knowledge). D-1 UV-0 listing input.
    /// Unbounded in SQL; the projection applies the listing cap so omitted count is honest.
    /// </summary>
    public IReadOnlyList<(string NodeId, string TypeKind)> SourceHasTypeNodes()
    {
        using var command = Command($"""
            {LatestCte}
            SELECT a.subject, a.object AS declared_type
            FROM evidence_assertion_fact a
            JOIN latest l ON l.scope_id = a.scope_id AND l.generation = a.generation
            LEFT JOIN node_dim n ON n.node_id = a.subject AND n.valid_to_seq IS NULL
            WHERE a.predicate = 'has_type'
              AND (n.node_kind IS NULL OR n.node_kind <> 'knowledge')
            GROUP BY a.subject
            ORDER BY a.subject;
            """);
        using var reader = command.ExecuteReader();
        var all = new List<(string, string)>();
        while (reader.Read())
        {
            all.Add((reader.GetString(0), reader.GetString(1)));
        }

        return all;
    }

    /// <summary>
    /// Latest-generation <c>has_member</c> facts. Listing display only — not Core observation ids (r5).
    /// </summary>
    public IReadOnlyList<(string TypeNodeId, string Member)> SourceHasMembers()
    {
        using var command = Command($"""
            {LatestCte}
            SELECT a.subject, a.object
            FROM evidence_assertion_fact a
            JOIN latest l ON l.scope_id = a.scope_id AND l.generation = a.generation
            WHERE a.predicate = 'has_member'
            GROUP BY a.subject, a.object
            ORDER BY a.subject, a.object;
            """);
        using var reader = command.ExecuteReader();
        var all = new List<(string, string)>();
        while (reader.Read())
        {
            all.Add((reader.GetString(0), reader.GetString(1)));
        }

        return all;
    }

    public IReadOnlySet<string> KnowledgeNodeIds(int limit)
    {
        using var command = Command(
            "SELECT node_id FROM node_dim WHERE node_kind = 'knowledge' AND valid_to_seq IS NULL "
            + "ORDER BY node_id LIMIT $limit;",
            ("$limit", limit));

        var ids = new HashSet<string>(StringComparer.Ordinal);

        using var reader = command.ExecuteReader();
        while (reader.Read()) ids.Add(reader.GetString(0));

        return ids;
    }

    public IReadOnlyList<StoredAssertion> AssertionsWithPredicate(string predicate, int limit)
    {
        using var command = Command($"""
            {LatestCte}
            SELECT {AssertionColumns} FROM evidence_assertion_fact a
            JOIN latest l ON l.scope_id = a.scope_id AND l.generation = a.generation
            WHERE a.predicate = $predicate
            ORDER BY a.subject
            LIMIT $limit;
            """, ("$predicate", predicate), ("$limit", limit));
        return ReadAssertions(command);
    }

    /// <summary>
    /// Node identities matching a substring, with the total matched so omissions are reportable.
    /// </summary>
    /// <remarks>
    /// A leading-wildcard LIKE cannot use an index, so this selects only the identity columns: it
    /// scans a covering index rather than hydrating every row's provenance, which is what made the
    /// naive version cost a full-corpus materialization.
    /// </remarks>
    /// <summary>
    /// Subjects this workspace's own artifacts DECLARE — the things it owns.
    /// </summary>
    /// <remarks>
    /// Distinct from every node in the graph, which also contains external package types a
    /// repository merely depends on. Any denominator that counts those is measuring the wrong
    /// population — bounded-context coverage above all, because nobody can assign
    /// <c>Azure.Storage.Blobs.BlobClient</c> to a context in their own codebase.
    /// </remarks>
    public IReadOnlyList<string> ReadDeclaredSubjects()
    {
        using var command = Command($"""
            {LatestCte}
            SELECT DISTINCT a.subject FROM evidence_assertion_fact a
            JOIN latest l ON l.scope_id = a.scope_id AND l.generation = a.generation
            WHERE a.predicate = 'declared_in'
            ORDER BY a.subject;
            """);

        using var reader = command.ExecuteReader();
        var subjects = new List<string>();
        while (reader.Read()) subjects.Add(reader.GetString(0));
        return subjects;
    }

    /// <summary>
    /// Nodes whose identity contains the term, and nodes one of whose ATTRIBUTE VALUES does.
    /// </summary>
    /// <remarks>
    /// <para>Identity-only search cannot answer the question a person actually asks. Searching
    /// <c>addEventListener</c> found ONE node by id and could not find the class that HAS that
    /// member; searching a Bicep resource's deployed name found the name and not the resource.
    /// MEASURED across TheTerrace: matching attribute values adds 1–14 nodes per term that identity
    /// search cannot reach at all, and they are the ones a person meant.</para>
    ///
    /// <para><b>An attribute match returns the node that OWNS the attribute, never the value.</b>
    /// That is why the original query excluded attribute objects: a value is not a node, and putting
    /// <c>api_version = 2023-01-01</c> in a result list as though it were a thing you can navigate
    /// to is how dates ended up in the graph. The exclusion was right about the object and wrong
    /// about the subject — the owner is a real node, and it is the answer.</para>
    ///
    /// <para>Each row carries WHY it matched and the matched text, because a result whose relevance
    /// is invisible reads as a wrong result. The evidence is truncated in SQL rather than after, so
    /// a long value never crosses the boundary just to be trimmed on the far side.</para>
    /// </remarks>
    public (IReadOnlyList<NodeSearchHit> Matches, int TotalMatched) SearchNodes(string term, int limit)
    {
        using var command = Command($"""
            {LatestCte}
            SELECT id, MIN(kind) AS kind, MIN(evidence) AS evidence FROM (
                SELECT a.subject AS id, 0 AS kind, '' AS evidence
                FROM evidence_assertion_fact a
                JOIN latest l ON l.scope_id = a.scope_id AND l.generation = a.generation
                WHERE a.subject LIKE $pattern
                UNION ALL
                SELECT a.object AS id, 0 AS kind, '' AS evidence
                FROM evidence_assertion_fact a
                JOIN latest l ON l.scope_id = a.scope_id AND l.generation = a.generation
                WHERE a.object LIKE $pattern
                  -- An attribute's object is a VALUE, not a node. Without this, api_version puts
                  -- dates in the graph and resource_name_expression puts unevaluated strings there.
                  AND a.predicate NOT IN ({AiDe.Core.Facts.EvidencePredicates.SqlList})
                UNION ALL
                -- The owner of a matching attribute value. Same rows the clause above refuses to
                -- treat as nodes, read the other way round: the SUBJECT is a node, and it is what
                -- the person was looking for.
                SELECT a.subject AS id, 1 AS kind,
                       a.predicate || ' = ' || SUBSTR(a.object, 1, $evidence) AS evidence
                FROM evidence_assertion_fact a
                JOIN latest l ON l.scope_id = a.scope_id AND l.generation = a.generation
                WHERE a.object LIKE $pattern
                  AND a.predicate IN ({AiDe.Core.Facts.EvidencePredicates.SqlList})
            )
            GROUP BY id
            ORDER BY kind, id;
            """, ("$pattern", $"%{term}%"), ("$evidence", MaxEvidenceCharacters));

        using var reader = command.ExecuteReader();
        var all = new List<NodeSearchHit>();

        while (reader.Read())
        {
            // MIN(kind) means identity wins over attribute when a node matched both ways — the
            // stronger reason, and the one that needs no explaining in the UI.
            var identity = reader.GetInt64(1) == 0;

            all.Add(new NodeSearchHit(
                reader.GetString(0),
                identity ? NodeMatchKind.Identity : NodeMatchKind.Attribute,
                identity ? null : reader.GetString(2)));
        }

        return (all.Count > limit ? all[..limit] : all, all.Count);
    }

    /// <summary>How much of a matched attribute value comes back as evidence.</summary>
    /// <remarks>
    /// Enough to recognise why a row is here, not enough to be content. A summary or a long
    /// expression would otherwise put unbounded text on a response whose budget is already the
    /// binding constraint on this product (INV-0003).
    /// </remarks>
    private const int MaxEvidenceCharacters = 120;

    /// <summary>
    /// The highest generation any scope has ever been asked for, or 0 for an empty store.
    /// </summary>
    /// <remarks>
    /// The in-memory counter starts at zero on every open, so without this a workspace's SECOND
    /// index after a restart re-uses generation 1 and violates the desired-generation primary key.
    /// The daemon opens the store fresh every time it starts, which made "index, restart, index"
    /// a guaranteed failure — found by a test that indexed twice across a reopen, which nothing had
    /// done before.
    /// </remarks>
    public long HighestDesiredGeneration()
    {
        using var command = Command("SELECT COALESCE(MAX(generation), 0) FROM scope_generation_desired_fact;");
        var value = command.ExecuteScalar();
        return value is null or DBNull ? 0 : Convert.ToInt64(value, CultureInfo.InvariantCulture);
    }

    /// <summary>The source revision currently rendered, for a result's provenance header.</summary>
    public string CurrentSourceRevision()
    {
        using var command = Command("""
            SELECT artifact_revision FROM scope_snapshot_committed_fact
            WHERE complete = 1 ORDER BY generation DESC, scope_id LIMIT 1;
            """);
        // Base, not stamped. What is stored carries the extractor generation that produced it
        // (SourceRevision); what a person is shown is the revision they named.
        return SourceRevision.Base(command.ExecuteScalar() as string ?? "none");
    }

    /// <summary>
    /// All current assertions across every scope that has a complete snapshot.
    /// </summary>
    /// <remarks>
    /// A deliberate full read, used only where the whole set IS the answer — the claim-cache rebuild.
    /// Bounded reads must never call this: at 50,000 edges it costs roughly 350 ms of materialization
    /// no matter how small the caller's result is (measured, P1-PERF 2026-08-26).
    /// </remarks>
    /// <summary>
    /// A page of the current assertions, ordered stably, starting after <paramref name="after"/>.
    /// </summary>
    /// <remarks>
    /// <para><b>Paged because the caller is across a pipe.</b> The panes want every current
    /// assertion — 12,085 of them on one real repository — and they were reconstructing that set one
    /// node at a time through <c>Describe</c>, which is bounded at 50 neighbours per node and lost
    /// two join edges out of 124 doing it. A single unbounded response would blow the result-byte
    /// cap instead, so the answer is neither: pages, with a cursor.</para>
    ///
    /// <para>The cursor is the last row's <c>(subject, predicate, object)</c> — the same tuple the
    /// ORDER BY uses, so a page boundary cannot skip or repeat a row. An id-based cursor would order
    /// by something the query does not, which is how paging quietly loses records.</para>
    /// </remarks>
    public IReadOnlyList<StoredAssertion> CurrentAssertionPage(
        (string Subject, string Predicate, string Object, string ScopeId)? after, int limit)
    {
        var sql = """
            SELECT a.assertion_id, a.scope_id, a.artifact_revision, a.subject, a.predicate, a.object,
                   a.origin, a.status, a.artifact_path_id, a.source_location, a.extractor_id,
                   a.extractor_version, a.observed_at
            FROM evidence_assertion_fact a
            JOIN (
                SELECT scope_id, max(generation) AS generation
                FROM scope_snapshot_committed_fact WHERE complete = 1 GROUP BY scope_id
            ) latest ON latest.scope_id = a.scope_id AND latest.generation = a.generation
            """;

        // SCOPE is part of the ordering and the cursor. (subject, predicate, object) is NOT unique:
        // two scopes can assert the same triple — measured on a real repository, where the page
        // boundary landed on such a tie and one assertion of 2,158 was skipped. A cursor over a
        // non-unique ordering loses exactly the rows that tie, silently.
        sql += after is null
            ? " ORDER BY a.subject, a.predicate, a.object, a.scope_id LIMIT $limit;"
            : """
               WHERE (a.subject, a.predicate, a.object, a.scope_id) > ($s, $p, $o, $scope)
               ORDER BY a.subject, a.predicate, a.object, a.scope_id LIMIT $limit;
              """;

        using var command = after is null
            ? Command(sql, ("$limit", limit))
            : Command(sql, ("$s", after.Value.Subject), ("$p", after.Value.Predicate),
                      ("$o", after.Value.Object), ("$scope", after.Value.ScopeId), ("$limit", limit));

        return ReadAssertions(command);
    }

    public IReadOnlyList<StoredAssertion> AllCurrentAssertions()
    {
        using var command = Command("""
            SELECT a.assertion_id, a.scope_id, a.artifact_revision, a.subject, a.predicate, a.object,
                   a.origin, a.status, a.artifact_path_id, a.source_location, a.extractor_id,
                   a.extractor_version, a.observed_at
            FROM evidence_assertion_fact a
            JOIN (
                SELECT scope_id, max(generation) AS generation
                FROM scope_snapshot_committed_fact WHERE complete = 1 GROUP BY scope_id
            ) latest ON latest.scope_id = a.scope_id AND latest.generation = a.generation
            ORDER BY a.subject, a.predicate, a.object;
            """);
        return ReadAssertions(command);
    }

    /// <summary>Folds a dispatch key's attempt + outcome events into one displayed receipt.</summary>
    public DispatchReceipt? ReadDispatchReceipt(string dispatchKey)
    {
        using var command = Command("""
            SELECT a.dispatch_key, a.session_id, a.session_generation, a.attempted_at,
                   (SELECT state      FROM dispatch_outcome_fact o WHERE o.dispatch_key = a.dispatch_key
                     ORDER BY o.ingress_seq DESC LIMIT 1),
                   (SELECT error_code FROM dispatch_outcome_fact o WHERE o.dispatch_key = a.dispatch_key
                     ORDER BY o.ingress_seq DESC LIMIT 1)
            FROM dispatch_attempt_fact a WHERE a.dispatch_key = $key;
            """, ("$key", dispatchKey));
        using var reader = command.ExecuteReader();
        if (!reader.Read())
        {
            return null;
        }

        // No outcome event yet => the attempt is still Pending. Recovery resolves it, never a caller.
        var state = reader.IsDBNull(4)
            ? DispatchState.Pending
            : Enum.Parse<DispatchState>(reader.GetString(4));

        return new DispatchReceipt(
            reader.GetString(0), state, reader.GetString(1), reader.GetInt64(2),
            reader.IsDBNull(5) ? null : reader.GetString(5),
            DateTimeOffset.Parse(reader.GetString(3)));
    }

    /// <summary>Dispatch keys with an attempt but no outcome — what recovery must resolve.</summary>
    public IReadOnlyList<string> PendingDispatchKeys()
    {
        using var command = Command("""
            SELECT a.dispatch_key FROM dispatch_attempt_fact a
            WHERE NOT EXISTS (SELECT 1 FROM dispatch_outcome_fact o WHERE o.dispatch_key = a.dispatch_key)
            ORDER BY a.ingress_seq;
            """);
        using var reader = command.ExecuteReader();
        var keys = new List<string>();
        while (reader.Read())
        {
            keys.Add(reader.GetString(0));
        }

        return keys;
    }

    public string? ReadCommandOutcome(string workspaceId, CallerPrincipal caller, string commandType, string commandId)
    {
        using var command = Command("""
            SELECT outcome FROM command_receipt_fact
            WHERE workspace_id = $ws AND caller_principal = $caller
              AND command_type = $type AND command_id = $id;
            """,
            ("$ws", workspaceId), ("$caller", caller.Id), ("$type", commandType), ("$id", commandId));
        return command.ExecuteScalar() as string;
    }

    public (long Generation, SessionProcessingClass ProcessingClass)? ReadSession(string sessionId)
    {
        using var command = Command("""
            SELECT generation, processing_class FROM session_dim
            WHERE session_id = $id AND valid_to_seq IS NULL;
            """, ("$id", sessionId));
        using var reader = command.ExecuteReader();
        return reader.Read()
            ? (reader.GetInt64(0), Enum.Parse<SessionProcessingClass>(reader.GetString(1)))
            : null;
    }

    public string? ReadNodeKind(string nodeId)
        => Command("SELECT node_kind FROM node_dim WHERE node_id = $id AND valid_to_seq IS NULL;", ("$id", nodeId))
            .ExecuteScalar() as string;

    public string? ReadNodeLabel(string nodeId)
        => Command("SELECT display_label FROM node_dim WHERE node_id = $id AND valid_to_seq IS NULL;", ("$id", nodeId))
            .ExecuteScalar() as string;

    /// <summary>
    /// Which of <paramref name="nodeIds"/> the workspace classifies as knowledge.
    /// </summary>
    /// <remarks>
    /// <para>Reads the same <c>node_class = knowledge</c> fact <c>GraphProjection</c> reads, rather
    /// than deciding again from the kind. Two authorities on what counts as knowledge is the shape
    /// of INV-0004 — where a hardcoded default rendered a table, a bicep resource and a class all as
    /// "source" — and two definitions of one quantity is a defect signature in its own right.</para>
    ///
    /// <para>Bounded by the caller's id list, so it costs what the result costs rather than what the
    /// graph costs (P1-PERF-02); an empty input reads nothing at all.</para>
    /// </remarks>
    public IReadOnlyCollection<string> ReadKnowledgeIds(IReadOnlyCollection<string> nodeIds)
    {
        if (nodeIds.Count == 0) return [];

        var names = nodeIds.Select((_, i) => $"$n{i}").ToList();
        var parameters = nodeIds
            .Select((id, i) => ($"$n{i}", (object?)id))
            .ToArray();

        using var command = Command($"""
            {LatestCte}
            SELECT DISTINCT a.subject FROM evidence_assertion_fact a
            JOIN latest l ON l.scope_id = a.scope_id AND l.generation = a.generation
            WHERE a.predicate = 'node_class' AND a.object = 'knowledge'
              AND a.subject IN ({string.Join(", ", names)});
            """, parameters);

        var found = new HashSet<string>(StringComparer.Ordinal);
        using var rows = command.ExecuteReader();
        while (rows.Read()) found.Add(rows.GetString(0));

        return found;
    }

    /// <summary>Reads the labelled cache. Provably equal to its derivation — see the rebuild test.</summary>
    public IReadOnlyList<(string Subject, string Predicate, string Object, string Status, int Count, string Revision)>
        ReadClaimCache()
    {
        using var command = Command("""
            SELECT subject, predicate, object, status, assertion_count, source_revision
            FROM claim_current_cache ORDER BY subject, predicate, object;
            """);
        using var reader = command.ExecuteReader();
        var rows = new List<(string, string, string, string, int, string)>();
        while (reader.Read())
        {
            rows.Add((reader.GetString(0), reader.GetString(1), reader.GetString(2),
                reader.GetString(3), reader.GetInt32(4), reader.GetString(5)));
        }

        return rows;
    }

    internal SqliteCommand Command(string sql, params (string Name, object? Value)[] parameters)
    {
        var command = _connection.CreateCommand();
        command.CommandText = sql;
        foreach (var (name, value) in parameters)
        {
            command.Parameters.AddWithValue(name, value ?? DBNull.Value);
        }

        return command;
    }

    private static IReadOnlyList<StoredAssertion> ReadAssertions(SqliteCommand command)
    {
        using var reader = command.ExecuteReader();
        var results = new List<StoredAssertion>();
        while (reader.Read())
        {
            results.Add(new StoredAssertion(
                reader.GetString(0), reader.GetString(1), SourceRevision.Base(reader.GetString(2)),
                reader.GetString(3), reader.GetString(4), reader.GetString(5),
                Enum.Parse<EvidenceOrigin>(reader.GetString(6)),
                Enum.Parse<VerificationStatus>(reader.GetString(7)),
                new Provenance(
                    reader.GetString(8), reader.IsDBNull(9) ? null : reader.GetString(9),
                    reader.GetString(10), reader.GetString(11),
                    DateTimeOffset.Parse(reader.GetString(12)))));
        }

        return results;
    }

    public void Dispose() => _connection.Dispose();
}

/// <summary>An assertion as stored, carrying its computed identity back out.</summary>
public sealed record StoredAssertion(
    string AssertionId,
    string ScopeId,
    string ArtifactRevision,
    string Subject,
    string Predicate,
    string Object,
    EvidenceOrigin Origin,
    VerificationStatus Status,
    Provenance Provenance);
