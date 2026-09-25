using System.Diagnostics;
using AiDe.Core.Dispatch;
using AiDe.Core.Extraction;
using AiDe.Core.Health;
using AiDe.Core.Mcp;
using AiDe.Core.Projections;
using AiDe.Core.Store;
using AiDe.Core.Watcher;

namespace AiDe.Core;

/// <summary>
/// The in-process authority core (ADR-0009): the composition root the shell talks to in Phase 1 and
/// the same contract a separate daemon exposes over IPC from Phase 2, so the split is a deployment
/// substitution rather than a redesign.
/// </summary>
public sealed class WorkspaceCore : IDisposable
{
    private static readonly ActivitySource Activity = new("aide.workspace.command");

    private readonly IExtractor _extractor;
    private readonly IDisposable? _watcherStore;
    private long _generation;

    /// <param name="scoredEpisodes">
    /// The watcher's scored episodes, for the MCP <c>standing</c> tool (US-16). A CONSTRUCTOR
    /// parameter rather than a property set afterwards: <see cref="Mcp"/> is built in this
    /// constructor, so anything it needs must arrive with it — a value assigned after construction
    /// is not available to the object the constructor already made (DC-083).
    /// </param>
    private WorkspaceCore(
        string workspaceId, WorkspaceStore store, IExtractor extractor,
        HealthIncidentSidecar incidents, string rootPath,
        AiDe.Core.Presentation.IWatcherLeaderboardQuery? scoredEpisodes,
        IDisposable? watcherStore = null)
    {
        WorkspaceId = workspaceId;
        Store = store;
        _extractor = extractor;
        Incidents = incidents;
        RootPath = rootPath;
        Projections = new ProjectionService(store, rootPath);
        Dispatch = new DispatchService(store);
        Mcp = new McpToolGateway(Projections, workspaceId, scoredEpisodes);

        // Held so Dispose can close it. C1 opened this store and did not: every workspace open
        // leaked a SQLite connection and three file handles for the process lifetime, and the
        // privacy probe caught it by REFUSING to pass — it could not read watcher.db, watcher.db-wal
        // or watcher.db-shm to scan them, and reported "NOT COVERED" rather than a clean sweep over
        // files it never opened. A pass there would have been an absence over an empty set.
        _watcherStore = watcherStore;
    }

    public string WorkspaceId { get; }

    public string RootPath { get; }

    /// <summary>Where workspace-local state lives. The layout file sits beside the fact store (ADR-0013).</summary>
    public string DataDirectory { get; private set; } = string.Empty;

    public WorkspaceStore Store { get; }

    public ProjectionService Projections { get; }

    public DispatchService Dispatch { get; }

    public McpToolGateway Mcp { get; }

    public HealthIncidentSidecar Incidents { get; }

    /// <summary>
    /// Opens a workspace and runs recovery before serving anything. Sweeping first is deliberate: a
    /// caller must never be able to observe an unresolved attempt and read it as "never sent".
    /// </summary>
    public static WorkspaceCore Open(string workspaceId, string rootPath, string dataDirectory, IExtractor? extractor = null)
    {
        Directory.CreateDirectory(dataDirectory);
        var store = WorkspaceStore.Open(Path.Combine(dataDirectory, "workspace.db"));
        var incidents = new HealthIncidentSidecar(Path.Combine(dataDirectory, "health-incidents.jsonl"));

        // The watcher's store lives beside the workspace's, in the directory this method already
        // has. Opened here so the MCP `standing` tool has a real source at construction rather than
        // a null it degrades around — a tool wired only on the path that happens to have the value
        // is the shape that shipped an unreachable environment contract this morning (DC-084).
        //
        // A SECOND OPENER of watcher.db: the shell's WatcherHost holds the writer. SQLite permits
        // this and the tool only reads, but it is a runtime coupling rather than a compile-time one
        // and is recorded here because nothing else would say so.
        var watcher = SqliteWatcherObservationStore.Open(Path.Combine(dataDirectory, "watcher.db"));

        var core = new WorkspaceCore(
            workspaceId, store, extractor ?? new FixtureExtractor(), incidents, rootPath,
            new AiDe.Core.Presentation.WatcherLeaderboardQuery(watcher), watcher)
        {
            DataDirectory = dataDirectory,
        };

        // Seeded from the store, not from zero. The counter is in memory and the store is not, so a
        // workspace's second index after a restart re-used generation 1 and violated the desired-
        // generation primary key. The daemon opens the store fresh on every start, which made
        // "index, restart, index" fail every time — and nothing had ever indexed twice across a
        // reopen, so nothing had ever noticed.
        using (var reader = store.BeginRead())
        {
            core._generation = reader.HighestDesiredGeneration();
        }

        var swept = core.Dispatch.SweepPendingToUnknown();
        if (swept > 0)
        {
            incidents.Record("dispatch.delivery_unknown", "workspace",
                $"{swept} dispatch attempt(s) resolved to DeliveryUnknown after restart", DateTimeOffset.UtcNow);
        }

        return core;
    }

    /// <summary>
    /// Extracts one scope and commits it as a complete snapshot. An incomplete extraction is recorded
    /// as a health incident and the previous snapshot stands — a failed refresh never empties the graph.
    /// </summary>
    /// <param name="rootPathOverride">
    /// What the extractor should read, when it is not the workspace root. A C# scope is one PROJECT
    /// built for one framework, so the request must carry that project's path — the workspace root
    /// names the repository, not the thing being extracted.
    /// </param>
    public async Task<ExtractionResult> RefreshScopeAsync(
        string scopeId, string artifactRevision, CancellationToken cancellationToken = default,
        string? rootPathOverride = null)
    {
        // A fact's identity includes the reader that produced it, so the revision is stamped with
        // the extractor generation before anything is compared or written. Stamping HERE rather than
        // at each call site is the point: the shell, the daemon's refresh op and a test all reach
        // this method, and the previous version let each of them ask a different question.
        artifactRevision = SourceRevision.Stamp(artifactRevision);

        using var activity = Activity.StartActivity("aide.ingestion.scope");
        activity?.SetTag("scope.id", scopeId);
        // The revision the CALLER named, plus the generation as its own axis. Putting the stamp in
        // the revision tag would make the same repository state look like a different revision on
        // every upgrade, and an operator grouping by revision would see churn that is not there.
        activity?.SetTag("artifact.revision", SourceRevision.Base(artifactRevision));
        activity?.SetTag("extractor.generation", ScopeFingerprints.ExtractorGeneration);

        // Re-extracting a revision the store already holds is a NO-OP, decided here rather than
        // absorbed by the database.
        //
        // The natural key deliberately rejects the same fact twice for one revision (P1-STORE-05),
        // and that is a control worth keeping — but "index again" is an ordinary thing for a user to
        // do, and before this it surfaced as a raw SQLite UNIQUE-constraint exception from the
        // middle of a run. Making the WRITE idempotent would have silenced the control; making the
        // CALLER idempotent leaves it strict and answers the user's actual question, which is
        // "is the graph current for this revision" — and it is.
        using (var probe = Store.BeginRead())
        {
            if (probe.LatestCommittedSnapshot(scopeId) is { AssertionCount: > 0 } snapshot
                && string.Equals(snapshot.ArtifactRevision, artifactRevision, StringComparison.Ordinal))
            {
                activity?.SetTag("scope.reused", true);
                return new ExtractionResult([], true, []);
            }
        }

        var generation = Interlocked.Increment(ref _generation);

        using (var writer = Store.BeginWrite())
        {
            writer.DesireScopeGeneration(scopeId, generation, artifactRevision);
            writer.Commit();
        }

        var result = await _extractor
            .ExtractAsync(
                new ExtractionRequest(
                    scopeId, rootPathOverride ?? RootPath, artifactRevision, generation,
                    WorkspaceModules(artifactRevision), WorkspaceDocuments(artifactRevision)),
                cancellationToken)
            .ConfigureAwait(false);

        if (!result.Complete)
        {
            // Explicit failed state, not silence: the operator's health view must show WHY the graph
            // is stale, and the last successful snapshot must remain the one that renders.
            foreach (var diagnostic in result.Diagnostics)
            {
                Incidents.Record("extraction.failed", scopeId,
                    $"{diagnostic.ErrorCode}: {diagnostic.ArtifactPathId} — {diagnostic.Message}", DateTimeOffset.UtcNow);
            }

            activity?.SetTag("outcome", "incomplete");
            return result;
        }

        // WHERE THE SCOPE LIVES, recorded as a fact.
        //
        // An assertion's provenance carries a path relative to its SCOPE — `main.bicep`,
        // `0001-modular-monolith.md` — and nothing recorded where the scope itself was. So a node
        // could not be resolved to a file at all: `declared_in` names the scope id, not a directory,
        // and deriving one from the id works for `knowledge:docs/adr` and fails for `bicep:main`,
        // which is a file stem. Guessing the rest would be a path resolved by pattern-matching, which
        // is how a reader ends up displaying the wrong file confidently.
        //
        // The core is what knows: it chose the path when it discovered the scope. One fact per scope,
        // relative to the workspace root so the store stays portable.
        var located = LocateScope(scopeId, rootPathOverride, artifactRevision) is { } where
            ? result.Assertions.Append(where).ToList()
            : result.Assertions;

        using (var writer = Store.BeginWrite())
        {
            writer.CommitSnapshot(scopeId, generation, artifactRevision, located, complete: true);

            // A subject is always a node. An OBJECT is a node only when the predicate is relational.
            // Found by indexing a real repository: api_version put "2020-02-02" in the graph and
            // resource_name_expression put "'${namePrefix}-acs'" there, so dates and unevaluated
            // strings became the things a user could navigate to. An attribute's value is a
            // property of its subject, not a peer of it.
            var nodeIds = result.Assertions
                .Select(a => a.Subject)
                .Concat(result.Assertions.Where(a => !AiDe.Core.Facts.EvidencePredicates.Attributes.Contains(a.Predicate)).Select(a => a.Object))
                .Distinct(StringComparer.Ordinal);

            // A node is KNOWLEDGE because a knowledge scope declared it — not because it has a type.
            //
            // This read `Any(a => a.Subject == nodeId && a.Predicate == "has_type")`, which was true
            // in Phase 1 when the fixture reader was the only producer of `has_type` and the only
            // reader of knowledge markdown. Six extractors later every declared C# class, table,
            // bicep resource and python module carries `has_type` too, so almost everything in the
            // graph was classified `knowledge` — and INV-0004 found it the way these are always
            // found, as a bicep resource reading "kind: knowledge" in the reader.
            //
            // DC-022 exactly: a predicate gained producers and a consumer kept its assumption about
            // who emits it. The scope id is the thing that actually knows.
            // The PRODUCER declares it. Scope ids were the first attempt and were nearly right —
            // but the fixture reader emits knowledge from a scope that is not named for it, so the
            // id cannot be the authority either. A fact can be.
            var knowledge = result.Assertions
                .Where(a => a.Predicate == "node_class" && a.Object == "knowledge")
                .Select(a => a.Subject)
                .ToHashSet(StringComparer.Ordinal);

            foreach (var nodeId in nodeIds)
            {
                writer.UpsertNode(nodeId, knowledge.Contains(nodeId) ? "knowledge" : "source", nodeId);
            }

            writer.Commit();
        }

        // What was COMMITTED, not what the extractor handed over. The two differ by the scope's own
        // location fact, and a caller that counts the return value is counting what is in the store —
        // which is what the index summary reports and what the evidence pages then page through.
        // Returning the extractor's set made the summary undercount by one per scope, caught by the
        // daemon's paging test comparing the summary against everything it could read back.
        activity?.SetTag("outcome", "committed");
        activity?.SetTag("assertion.count", located.Count);
        return result with { Assertions = [.. located] };
    }

    /// <summary>The result of indexing a whole repository's C# scopes.</summary>
    /// <param name="Failed">Scopes that did not complete — each already has a health incident.</param>
    /// <param name="ScopesReused">
    /// Scopes whose inputs had not changed, so nothing was re-read. Reported separately from
    /// <paramref name="ScopesIndexed"/> because a skip presented as work is the difference between
    /// "it looked and found nothing" and "it did not look".
    /// </param>
    public sealed record IndexResult(
        int ScopesFound,
        int ScopesIndexed,
        int Assertions,
        IReadOnlyList<string> Failed,
        IReadOnlyList<string> Disclosures,
        string? Contexts = null,
        int ScopesReused = 0);

    /// <summary>
    /// Retires a departed scope's evidence by committing an EMPTY snapshot over it.
    /// </summary>
    /// <remarks>
    /// <para><b>Superseded, never deleted.</b> The store is append-only and every projection reads
    /// the latest generation per scope, so an empty snapshot at a higher generation retires the
    /// evidence while the history that produced it stays readable. Deleting the rows would destroy
    /// the record of what the graph once said, which is the thing an audit trail is for.</para>
    ///
    /// <para><b>The graph was drawing deleted code.</b> Removing a project left its symbols, edges
    /// and crossings in every projection indefinitely: nothing re-extracted a scope that no longer
    /// existed, so nothing ever replaced its snapshot. The departure was noticed before this; now it
    /// is acted on.</para>
    ///
    /// <para>A failure here is recorded and swallowed. One scope that cannot be retired must not
    /// cost the caller the rest of an index run, and the stale evidence it leaves is exactly the
    /// state that already existed.</para>
    /// </remarks>
    /// <summary>
    /// Where a scope's files are, relative to the workspace root, as one assertion.
    /// </summary>
    /// <remarks>
    /// <para>The BASE the scope's provenance paths hang off — a project's directory, a template's
    /// directory, a documentation folder — mirroring how <see cref="ScopeFingerprints.Compute"/>
    /// decides the same thing, because a scope pointed at a file means that file's directory and a
    /// scope pointed at a directory means itself.</para>
    ///
    /// <para>Relative, and never above the root: a stored absolute path would leak one machine's
    /// layout into a store meant to be portable, and an escaping one would let a later reader resolve
    /// outside the workspace it belongs to.</para>
    /// </remarks>
    private Facts.EvidenceAssertion? LocateScope(string scopeId, string? scopePath, string artifactRevision)
    {
        if (string.IsNullOrWhiteSpace(scopePath)) return null;

        try
        {
            var basePath = File.Exists(scopePath) ? Path.GetDirectoryName(scopePath) : scopePath;

            if (string.IsNullOrEmpty(basePath)) return null;

            var relative = Path.GetRelativePath(RootPath, basePath)
                .Replace(Path.DirectorySeparatorChar, '/');

            if (relative.StartsWith("..", StringComparison.Ordinal) || Path.IsPathRooted(relative))
            {
                return null;
            }

            return new Facts.EvidenceAssertion(
                scopeId, artifactRevision, scopeId, "declared_at", relative == "." ? string.Empty : relative,
                Facts.EvidenceOrigin.Static, Facts.VerificationStatus.Verified,
                new Facts.Provenance(relative, null, "workspace-core", "1", DateTimeOffset.UtcNow));
        }
        catch (Exception ex) when (ex is ArgumentException or PathTooLongException)
        {
            // A scope whose location cannot be expressed is a scope whose content cannot be read.
            // That is a reader saying "no content", not an indexing failure.
            return null;
        }
    }

    private void RetractScope(string scopeId, string artifactRevision)
    {
        try
        {
            var generation = Interlocked.Increment(ref _generation);

            using var writer = Store.BeginWrite();
            writer.DesireScopeGeneration(scopeId, generation, artifactRevision);
            writer.CommitSnapshot(scopeId, generation, artifactRevision, [], complete: true);
            writer.Commit();
        }
        catch (Store.WorkspaceStoreException ex)
        {
            Incidents.Record("extraction.retraction_failed", scopeId,
                $"the departed scope's evidence could not be retired: {ex.ErrorCode}", DateTimeOffset.UtcNow);
        }
    }

    /// <summary>
    /// Whether the store still holds a committed snapshot for a scope we are about to skip — one
    /// with evidence in it, stamped with a revision that is a revision.
    /// </summary>
    /// <remarks>
    /// <para>The fingerprint says the INPUTS have not changed; it says nothing about whether the
    /// output survived. A store rebuilt, compacted or replaced under an unchanged working tree would
    /// otherwise leave the scope skipped forever and its evidence permanently missing.</para>
    ///
    /// <para><b>Nor about what the output is stamped with (Ruling 98).</b> Ruling 85 moved the shell
    /// off the fixture literal at the writer; a store the OLD writer had already written still carries
    /// <see cref="SourceRevision.RetiredFixtureLiteral"/> on every snapshot, and a guard that reuses
    /// on the fingerprint alone never opens the snapshot's revision — so the fix could not reach the
    /// operator's workspace, which kept printing <i>rev rev-1</i> on a build that no longer attached
    /// it. The base is compared (<see cref="SourceRevision.Base"/>: the stored value carries the
    /// extractor generation); a match re-extracts the scope once under the caller's revision, after
    /// which the snapshot is reusable like any other.</para>
    /// </remarks>
    private static bool Reusable(Store.StoreReader reader, string scopeId)
    {
        using (reader)
        {
            return reader.LatestCommittedSnapshot(scopeId) is { AssertionCount: > 0 } snapshot
                && !string.Equals(
                    SourceRevision.Base(snapshot.ArtifactRevision),
                    SourceRevision.RetiredFixtureLiteral,
                    StringComparison.Ordinal);
        }
    }

    /// <summary>
    /// Discovers every C# scope under the workspace root and refreshes each one.
    /// </summary>
    /// <remarks>
    /// <para><b>Per scope, not per repository.</b> Each project/framework pair gets its own budget,
    /// its own generation and its own snapshot, so one project that fails to load quarantines itself
    /// and leaves every other project's evidence standing (<c>P2-EXT-02</c>).</para>
    ///
    /// <para><b>The per-scope budget is enforced here.</b> A 60-second cap per scope, from the
    /// design — applied with a linked token so a caller cancelling the whole index still stops
    /// everything, while one slow project cannot consume the entire run.</para>
    /// </remarks>
    /// <param name="force">
    /// Re-extract every scope even when its inputs are unchanged. The escape hatch for "I do not
    /// believe the cache", which is a thing an operator must always be able to say.
    /// </param>
    public async Task<IndexResult> IndexCSharpAsync(
        string artifactRevision, CancellationToken cancellationToken = default,
        TimeSpan? perScopeBudget = null, bool force = false)
    {
        // Stamped once here so every revision this method compares or writes — the per-scope
        // refresh, a retraction, the stale-scope disclosure — is the same string.
        artifactRevision = SourceRevision.Stamp(artifactRevision);

        var scopes = CSharpScopeDiscovery.DiscoverAll(RootPath);
        var budget = perScopeBudget ?? TimeSpan.FromSeconds(60);

        // Unchanged scopes are not re-read. The fingerprint covers each scope's input files and the
        // extractor generation, so upgrading the product invalidates everything rather than leaving
        // a graph built by two extractor versions with nothing saying which.
        var fingerprints = ScopeFingerprints.Load(DataDirectory);
        var reused = 0;

        // The SET of scopes is part of the workspace's shape, and it changes without any individual
        // scope changing. Reconciling here drops the memory of scopes that have gone, so their
        // absence is noticed rather than silently reused forever.
        var departed = fingerprints.Known
            .Where(id => !scopes.Any(s => string.Equals(s.ScopeId, id, StringComparison.Ordinal)))
            .ToList();

        fingerprints.Reconcile(scopes.Select(s => s.ScopeId));

        foreach (var gone in departed)
        {
            Incidents.Record("extraction.scope_departed", gone,
                "the scope was indexed before and no longer exists in the workspace", DateTimeOffset.UtcNow);

            RetractScope(gone, artifactRevision);
        }

        var indexed = 0;
        var assertions = 0;
        var failed = new List<string>();
        var disclosures = new HashSet<string>(StringComparer.Ordinal);

        foreach (var scope in scopes)
        {
            cancellationToken.ThrowIfCancellationRequested();

            var fingerprint = ScopeFingerprints.Compute(RootPath, scope);

            if (!force && fingerprints.IsUnchanged(scope.ScopeId, fingerprint)
                && Store.BeginRead() is var probe && Reusable(probe, scope.ScopeId))
            {
                // Counted as REUSED, not indexed. "7 of 7 indexed" would be a true sentence about a
                // run that read nothing, and the question after a surprising graph is always
                // "did it actually look?".
                reused++;
                continue;
            }

            using var perScope = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
            perScope.CancelAfter(budget);

            ExtractionResult result;
            try
            {
                result = await RefreshScopeAsync(
                    scope.ScopeId, artifactRevision, perScope.Token, scope.ProjectPath).ConfigureAwait(false);
            }
            catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
            {
                // The scope's own budget expired. Quarantine it and keep going: the alternative is
                // one unloadable project costing the user every other project's evidence.
                Incidents.Record("extraction.timeout", scope.ScopeId,
                    $"scope exceeded its {budget.TotalSeconds:F0}s budget", DateTimeOffset.UtcNow);
                failed.Add(scope.ScopeId);
                continue;
            }

            if (!result.Complete)
            {
                failed.Add(scope.ScopeId);

                // The last good snapshot deliberately keeps rendering (see RefreshScopeAsync), which
                // is right — a failed extraction must not blank the graph. But what renders is now
                // OLD, and until this nothing said so: the panes drew a stale scope exactly like a
                // current one, and only the incident sidecar knew. Retracting instead would obey
                // this loop and contradict that decision, so the answer is to state it.
                using var staleReader = Store.BeginRead();
                if (staleReader.LatestCommittedSnapshot(scope.ScopeId) is { } stale
                    && !string.Equals(stale.ArtifactRevision, artifactRevision, StringComparison.Ordinal))
                {
                    disclosures.Add(
                        $"stale-scope ({scope.ScopeId} still shows evidence from {stale.ArtifactRevision})");
                }

                continue;
            }

            indexed++;
            assertions += result.Assertions.Count;
            fingerprints.Record(scope.ScopeId, fingerprint);

            foreach (var disclosure in result.Assertions
                .Where(a => a.Predicate == CSharpExtractor.DisclosurePredicate)
                .Select(a => a.Object))
            {
                disclosures.Add(disclosure);
            }
        }

        // The context map is validated against what was ACTUALLY extracted, at the end of the run —
        // validating it against nothing would only check the file's shape, which is the half that
        // never goes stale.
        var contextSummary = ValidateContexts();
        fingerprints.Save();

        // Source this build cannot read is DISCLOSED, not omitted. Measured on a repository of 63
        // Python and 40 TypeScript files: it produced zero scopes, zero assertions and an empty
        // disclosure list, which is indistinguishable from an empty directory. "Nothing here" and
        // "nothing I can read" must not render identically.
        foreach (var language in UnanalysedLanguages.Survey(RootPath))
        {
            disclosures.Add(language);
        }

        return new IndexResult(
            scopes.Count, indexed, assertions,
            failed, [.. disclosures.Order(StringComparer.Ordinal)], contextSummary, reused);
    }

    /// <summary>Loads and validates the declared bounded contexts against the extracted symbols.</summary>
    private string? ValidateContexts()
    {
        var path = Path.Combine(RootPath, BoundedContextReader.DefaultRelativePath);
        if (!File.Exists(path)) return null;

        // Coverage is over what the repository DECLARES, not over every node in the graph.
        // The first run reported "52% of 2,086 symbols" with a denominator that included
        // AngleSharp.Dom.IElement and Azure.Storage.Blobs.BlobClient — external types nobody can
        // put in a bounded context. A percentage with the wrong denominator is a confident wrong
        // number, and coverage is exactly the figure someone would quote.
        List<string> symbols;
        List<string> tables;
        using (var reader = Store.BeginRead())
        {
            var declared = reader.ReadDeclaredSubjects();
            symbols = [.. declared.Where(id => !id.StartsWith("table:", StringComparison.Ordinal))];
            tables = [.. declared.Where(id => id.StartsWith("table:", StringComparison.Ordinal))
                .Select(id => id["table:".Length..])];
        }

        return BoundedContextReader.Load(path, symbols, tables).Describe();
    }

    /// <summary>
    /// Raises a health incident for any scope whose generation count has passed the compaction
    /// threshold.
    /// </summary>
    /// <remarks>
    /// P1-PERF measured refresh going over budget at roughly ten generations of the same scope. The
    /// growth is the append-only design working as intended, so the operator is told rather than the
    /// slowdown being absorbed silently — a workspace that has quietly become slow is the shape of
    /// problem people stop reporting and start working around.
    ///
    /// This reports; it does not compact. Compaction replaces the database file, so it belongs to a
    /// deliberate maintenance moment, not to a background timer that could fire mid-session.
    /// </remarks>
    public IReadOnlyList<(string ScopeId, int Generations)> CheckCompactionNeeded(
        int threshold = StoreCompactor.DefaultThreshold)
    {
        using var reader = Store.BeginRead();
        var needing = StoreCompactor.ScopesNeedingCompaction(reader, threshold);

        foreach (var (scopeId, generations) in needing)
        {
            Incidents.Record("store.compaction_due", scopeId,
                $"scope has {generations} committed generations; refresh slows measurably past "
                + $"{threshold}. Compaction reclaims the space without losing current evidence.",
                DateTimeOffset.UtcNow);
        }

        return needing;
    }

    /// <summary>The path compaction operates on. Compaction requires the store to be closed.</summary>
    public string DatabasePath => Path.Combine(DataDirectory, "workspace.db");

    /// <summary>
    /// Closes what this object opened — both stores.
    /// </summary>
    /// <remarks>
    /// The watcher store is disposed here because <c>Open</c> created it. Whoever opens a handle
    /// owns closing it, and the alternative — taking the store as a constructor parameter so the
    /// caller owns its lifetime — would move that ownership rather than remove it.
    /// </remarks>
    public void Dispose()
    {
        Store.Dispose();
        _watcherStore?.Dispose();
    }
    private readonly System.Threading.Lock _modulesGate = new();
    private string? _modulesRevision;
    private IReadOnlySet<string>? _modules;

    /// <summary>
    /// Every module id in the workspace, so an import that leaves its scope can be resolved.
    /// </summary>
    /// <remarks>
    /// <para><b>Read from the FILESYSTEM, not from the store.</b> Resolving against what has already
    /// been extracted would make an edge depend on the order the scopes happened to run in — the
    /// trap the Python extractor already avoids within a scope by collecting modules before reading
    /// any of them. The same rule, one level up.</para>
    ///
    /// <para>Computed once per revision and cached, because indexing a repository with thirty scopes
    /// would otherwise walk the whole tree thirty times. The revision is the key: a new revision is
    /// exactly the event that can add or remove a file.</para>
    /// </remarks>
    private IReadOnlySet<string> WorkspaceModules(string artifactRevision)
    {
        lock (_modulesGate)
        {
            if (_modules is not null && _modulesRevision == artifactRevision) return _modules;

            var modules = new HashSet<string>(StringComparer.Ordinal);

            if (Directory.Exists(RootPath))
            {
                foreach (var file in ModuleFiles(RootPath))
                {
                    var relative = Path.GetRelativePath(RootPath, file);
                    var withoutExtension = relative[..^Path.GetExtension(relative).Length];

                    modules.Add(withoutExtension
                        .Replace(Path.DirectorySeparatorChar, '/')
                        .Replace(Path.AltDirectorySeparatorChar, '/'));
                }
            }

            _modules = modules;
            _modulesRevision = artifactRevision;
            return modules;
        }
    }

    private string? _documentsRevision;
    private WorkspaceKnowledge? _documents;

    /// <summary>
    /// Every markdown file in the workspace and the node id it declares, so a prose link that leaves
    /// its scope's directory can be resolved.
    /// </summary>
    /// <remarks>
    /// <para><b>The same shape as <see cref="WorkspaceModules"/>, for a sharper reason.</b>
    /// Knowledge scopes NEST — <c>docs</c> and <c>docs/adr</c> are both scopes — and the reader now
    /// emits facts for its own directory only, so every document belongs to exactly one scope and
    /// nothing wider is left to resolve a link that crosses a directory. Measured before the change:
    /// making the walk narrow without this cost 30 of 42 prose-link edges (DC-051).</para>
    ///
    /// <para>Read from the FILESYSTEM rather than the store, and cached per revision, for the two
    /// reasons stated above <see cref="WorkspaceModules"/>: an edge must not depend on the order the
    /// scopes ran in, and thirty-nine knowledge scopes must not walk the tree thirty-nine times.
    /// MEASURED on TheTerrace: one survey of 1,087 markdown files, and the whole index went from
    /// 7.1s to 5.5s because the duplicated reading it replaces was the larger cost.</para>
    /// </remarks>
    private WorkspaceKnowledge WorkspaceDocuments(string artifactRevision)
    {
        lock (_modulesGate)
        {
            if (_documents is not null && _documentsRevision == artifactRevision) return _documents;

            _documents = KnowledgeExtractor.Survey(RootPath);
            _documentsRevision = artifactRevision;
            return _documents;
        }
    }

    /// <summary>Python, TypeScript and JavaScript files anywhere in the workspace.</summary>
    private static IEnumerable<string> ModuleFiles(string root)
    {
        // The union of what the two module-shaped extractors read, and the same vendored-tree
        // exclusions they use. A node_modules walk would dwarf the repository it sits in.
        var extensions = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        {
            ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
        };

        var skip = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        {
            "node_modules", "dist", "build", "out", ".next", "coverage", ".git",
            "__pycache__", ".venv", "venv", ".tox", "bin", "obj",
        };

        var pending = new Stack<string>();
        pending.Push(root);

        while (pending.Count > 0)
        {
            var current = pending.Pop();

            string[] files;
            try { files = Directory.GetFiles(current); }
            catch (Exception ex) when (ex is IOException or UnauthorizedAccessException) { continue; }

            foreach (var file in files)
            {
                // A declaration file re-states types defined elsewhere, so it is not a module a
                // reader navigates to — the same exclusion the TypeScript extractor makes.
                if (file.EndsWith(".d.ts", StringComparison.OrdinalIgnoreCase)) continue;

                if (extensions.Contains(Path.GetExtension(file))) yield return file;
            }

            IEnumerable<string> children;
            try { children = Directory.EnumerateDirectories(current); }
            catch (Exception ex) when (ex is IOException or UnauthorizedAccessException) { continue; }

            foreach (var child in children)
            {
                if (!skip.Contains(Path.GetFileName(child))) pending.Push(child);
            }
        }
    }

}
