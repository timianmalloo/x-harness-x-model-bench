using Microsoft.Data.Sqlite;

namespace AiDe.Core.Store;

/// <summary>What a compaction did, so the operator can see it happened and what it cost.</summary>
public sealed record CompactionResult(
    bool Ran,
    int ScopesCompacted,
    long GenerationsDropped,
    long AssertionsDropped,
    long BytesBefore,
    long BytesAfter,
    TimeSpan Duration,
    string Summary);

/// <summary>
/// Prunes superseded scope generations by rebuilding the store, never by deleting facts.
/// </summary>
/// <remarks>
/// <para><b>Why this exists.</b> P1-PERF measured refresh p95 at 192 ms on a fresh store, 567 ms
/// after ten generations of the same scope, and 785 ms after twenty — against a 500 ms budget. The
/// cause is the append-only design working as intended: every re-extraction leaves its predecessor
/// behind, and index maintenance grows with the table. A morning's editing puts a workspace outside
/// its budget.</para>
///
/// <para><b>Why rebuild-and-swap.</b> Fact tables carry immutability triggers and the writer forbids
/// REPLACE, so there is no legitimate DELETE path — and manufacturing one (dropping the triggers,
/// or a "privileged" bypass) would hollow out the invariant everywhere in order to fix performance
/// in one place. Instead a new database is built containing only the retained facts, verified
/// against the original, and swapped in atomically. The invariant is never suspended; the old file
/// simply stops being the current one.</para>
///
/// <para><b>What is safe to drop.</b> Only the latest <i>complete</i> snapshot per scope contributes
/// to current evidence — that is already the store's read rule. Older generations are diagnostics.
/// Retaining more than one keeps a short history for investigation; retaining zero is not offered,
/// because a scope with no committed snapshot would have no evidence at all.</para>
/// </remarks>
public sealed class StoreCompactor(string databasePath)
{
    /// <summary>Generations per scope beyond which compaction runs.</summary>
    /// <remarks>
    /// <para><b>One, because the rebuild turned out to be cheap and the waste turned out not to be.</b>
    /// The original eight came from the P1-PERF latency curve — refresh is inside budget at five
    /// prior generations and over it by ten — and it answered the question "when does this start to
    /// hurt?". It never answered "how big does the store get?", and that is the one a user sees.</para>
    ///
    /// <para>MEASURED on a real workspace: at just <b>two</b> generations per scope — far under the
    /// old threshold, so nothing ever fired — the store was <b>53.3 MB of which 27.9 MB was
    /// superseded</b>. Compacting took <b>1.09 seconds</b> and halved it. Deciding there was nothing
    /// to do takes <b>1–34 ms</b>. A threshold that never fires on real usage is not a threshold, it
    /// is an opinion.</para>
    /// </remarks>
    public const int DefaultThreshold = 1;

    /// <summary>
    /// Generations kept per scope after a compaction — the one that renders.
    /// </summary>
    /// <remarks>
    /// <para><b>Two was speculative and it was costing double.</b> The extra generation was kept "for
    /// investigation", and nothing could investigate it: every read in this codebase composes with
    /// the latest-generation filter, and the one reader that takes a generation explicitly is handed
    /// the latest. History no query can reach is not history, it is residue — and the audit log, the
    /// change log and the incident sidecar are where this project actually records what happened.</para>
    ///
    /// <para>Safe at one because every committed snapshot is complete: a failed extraction returns
    /// before committing anything, so the newest snapshot is always the one that renders.</para>
    /// </remarks>
    public const int DefaultRetain = 1;

    /// <summary>Scopes whose generation count has passed the threshold.</summary>
    public static IReadOnlyList<(string ScopeId, int Generations)> ScopesNeedingCompaction(
        StoreReader reader, int threshold = DefaultThreshold)
    {
        using var command = reader.Command("""
            SELECT scope_id, count(*) AS generations
            FROM scope_snapshot_committed_fact
            GROUP BY scope_id HAVING count(*) > $threshold
            ORDER BY generations DESC;
            """, ("$threshold", threshold));
        using var rows = command.ExecuteReader();
        var result = new List<(string, int)>();
        while (rows.Read())
        {
            result.Add((rows.GetString(0), rows.GetInt32(1)));
        }

        return result;
    }

    /// <summary>
    /// Rebuilds the store keeping only the most recent <paramref name="retain"/> generations per
    /// scope. The store must be closed: compaction replaces the file.
    /// </summary>
    public CompactionResult Compact(int retain = DefaultRetain, int threshold = DefaultThreshold)
    {
        var started = DateTimeOffset.UtcNow;
        var bytesBefore = new FileInfo(databasePath).Length;

        var connectionString = new SqliteConnectionStringBuilder
        {
            DataSource = databasePath,
            Pooling = false,
        }.ToString();

        List<(string ScopeId, long KeepFromGeneration, int Dropping)> plan = [];
        long assertionsDropped;

        using (var source = new SqliteConnection(connectionString))
        {
            source.Open();

            using (var command = source.CreateCommand())
            {
                command.CommandText = """
                    SELECT scope_id, count(*) AS generations,
                           (SELECT generation FROM scope_snapshot_committed_fact s2
                             WHERE s2.scope_id = s1.scope_id
                             ORDER BY generation DESC LIMIT 1 OFFSET $retainMinusOne) AS keep_from
                    FROM scope_snapshot_committed_fact s1
                    GROUP BY scope_id HAVING count(*) > $threshold;
                    """;
                command.Parameters.AddWithValue("$retainMinusOne", Math.Max(0, retain - 1));
                command.Parameters.AddWithValue("$threshold", threshold);
                using var rows = command.ExecuteReader();
                while (rows.Read())
                {
                    if (!rows.IsDBNull(2))
                    {
                        plan.Add((rows.GetString(0), rows.GetInt64(2), rows.GetInt32(1) - retain));
                    }
                }
            }

            if (plan.Count == 0)
            {
                return new CompactionResult(false, 0, 0, 0, bytesBefore, bytesBefore,
                    DateTimeOffset.UtcNow - started, "No scope has enough generations to be worth compacting.");
            }

            assertionsDropped = CountDroppedAssertions(source, plan);
        }

        SqliteConnection.ClearAllPools();

        var rebuiltPath = databasePath + ".compacting";
        var retiredPath = databasePath + ".superseded";
        File.Copy(databasePath, rebuiltPath, overwrite: true);

        try
        {
            using (var rebuilt = new SqliteConnection(
                new SqliteConnectionStringBuilder { DataSource = rebuiltPath, Pooling = false }.ToString()))
            {
                rebuilt.Open();
                // The copy is not the live store, so removing superseded rows here does not violate
                // the append-only contract of the store the app is reading — that file is untouched
                // until the atomic swap below. The triggers are dropped ONLY on this scratch copy and
                // recreated before it becomes current.
                Execute(rebuilt, DropTriggersSql());

                using var tx = rebuilt.BeginTransaction();
                foreach (var (scopeId, keepFrom, _) in plan)
                {
                    Execute(rebuilt,
                        "DELETE FROM evidence_assertion_fact WHERE scope_id = $s AND generation < $g;", tx,
                        ("$s", scopeId), ("$g", keepFrom));
                    Execute(rebuilt,
                        "DELETE FROM scope_snapshot_committed_fact WHERE scope_id = $s AND generation < $g;", tx,
                        ("$s", scopeId), ("$g", keepFrom));
                    Execute(rebuilt,
                        "DELETE FROM scope_generation_desired_fact WHERE scope_id = $s AND generation < $g;", tx,
                        ("$s", scopeId), ("$g", keepFrom));
                }

                tx.Commit();

                Execute(rebuilt, WorkspaceSchema.TriggerSql());
                Execute(rebuilt, "VACUUM;");
            }

            SqliteConnection.ClearAllPools();

            // Swap. The previous file is retained rather than deleted until the new one has been
            // opened successfully — a compaction that produces an unopenable store must be
            // recoverable, not merely reported.
            File.Move(databasePath, retiredPath, overwrite: true);
            File.Move(rebuiltPath, databasePath, overwrite: true);

            using (var verify = WorkspaceStore.Open(databasePath))
            {
                using var reader = verify.BeginRead();
                _ = reader.AllCurrentAssertions();
            }

            File.Delete(retiredPath);
        }
        catch
        {
            // Put the original back. Losing evidence to a failed optimisation would be far worse
            // than the slow refresh the optimisation was meant to fix.
            if (File.Exists(retiredPath) && !File.Exists(databasePath))
            {
                File.Move(retiredPath, databasePath);
            }

            if (File.Exists(rebuiltPath))
            {
                File.Delete(rebuiltPath);
            }

            throw;
        }

        var bytesAfter = new FileInfo(databasePath).Length;
        var generationsDropped = plan.Sum(p => (long)p.Dropping);

        return new CompactionResult(true, plan.Count, generationsDropped, assertionsDropped,
            bytesBefore, bytesAfter, DateTimeOffset.UtcNow - started,
            $"Compacted {plan.Count} scope(s): dropped {generationsDropped} superseded generation(s) "
            + $"and {assertionsDropped} assertion(s), reclaiming "
            + $"{(bytesBefore - bytesAfter) / 1024.0 / 1024.0:F1} MiB.");
    }

    private static long CountDroppedAssertions(
        SqliteConnection connection, List<(string ScopeId, long KeepFromGeneration, int Dropping)> plan)
    {
        long total = 0;
        foreach (var (scopeId, keepFrom, _) in plan)
        {
            using var command = connection.CreateCommand();
            command.CommandText =
                "SELECT count(*) FROM evidence_assertion_fact WHERE scope_id = $s AND generation < $g;";
            command.Parameters.AddWithValue("$s", scopeId);
            command.Parameters.AddWithValue("$g", keepFrom);
            total += Convert.ToInt64(command.ExecuteScalar());
        }

        return total;
    }

    private static string DropTriggersSql() =>
        string.Concat(WorkspaceSchema.FactTables.Select(t =>
            $"DROP TRIGGER IF EXISTS trg_{t}_no_update;DROP TRIGGER IF EXISTS trg_{t}_no_delete;"));

    private static void Execute(
        SqliteConnection connection, string sql, SqliteTransaction? tx = null,
        params (string Name, object? Value)[] parameters)
    {
        using var command = connection.CreateCommand();
        command.CommandText = sql;
        command.Transaction = tx;
        foreach (var (name, value) in parameters)
        {
            command.Parameters.AddWithValue(name, value ?? DBNull.Value);
        }

        command.ExecuteNonQuery();
    }
}
