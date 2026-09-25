using Microsoft.Data.Sqlite;

namespace AiDe.Core.Store;

/// <summary>Stable error codes this layer can raise. Never a bare exception message.</summary>
public static class StoreErrorCodes
{
    public const string ImmutableViolation = "AIDE-STORE-IMMUTABLE-VIOLATION";
    public const string ScopeGenerationStale = "AIDE-SCOPE-GENERATION-STALE";
    public const string EpochStale = "AIDE-AUTH-EPOCH-STALE";
}

/// <summary>A store-layer failure carrying a stable, greppable code.</summary>
public sealed class WorkspaceStoreException(string errorCode, string message, Exception? inner = null)
    : Exception(message, inner)
{
    public string ErrorCode { get; } = errorCode;
}

/// <summary>
/// One workspace, one SQLite file. Owns the single writer, the core epoch, and the total fact order.
/// </summary>
/// <remarks>
/// Pattern: Repository + Unit of Work (narrow). SQLite has no nested transactions
/// (spikes/sqlite-fact-store S8), so one write transaction per aggregate operation is the contract,
/// enforced by the writer semaphore rather than an ambient transaction scope.
/// </remarks>
public sealed class WorkspaceStore : IDisposable
{
    private readonly string _connectionString;
    private readonly SqliteConnection _writeConnection;
    private readonly SemaphoreSlim _writerGate = new(1, 1);
    private bool _disposed;

    private WorkspaceStore(string connectionString, SqliteConnection writeConnection, long coreEpoch)
    {
        _connectionString = connectionString;
        _writeConnection = writeConnection;
        CoreEpoch = coreEpoch;
    }

    /// <summary>
    /// Monotonic, store-persisted, incremented inside the open transaction. Never random and never
    /// clock-derived, so "stale" is decidable and an old epoch value cannot recur (ABA).
    /// </summary>
    public long CoreEpoch { get; }

    public static WorkspaceStore Open(string databasePath)
    {
        var connectionString = new SqliteConnectionStringBuilder
        {
            DataSource = databasePath,
            Mode = SqliteOpenMode.ReadWriteCreate,
            Pooling = false,
        }.ToString();

        var connection = new SqliteConnection(connectionString);
        connection.Open();
        ConfigureWriterConnection(connection);

        var created = EnsureSchema(connection);
        var epoch = BumpEpoch(connection, created);

        return new WorkspaceStore(connectionString, connection, epoch);
    }

    /// <summary>
    /// Writer pragmas. <c>recursive_triggers=ON</c> is load-bearing, not hygiene: without it
    /// INSERT OR REPLACE bypasses the immutability triggers entirely (spike S4).
    /// </summary>
    private static void ConfigureWriterConnection(SqliteConnection connection)
    {
        Execute(connection, "PRAGMA journal_mode=WAL;");
        Execute(connection, "PRAGMA foreign_keys=ON;");
        Execute(connection, "PRAGMA recursive_triggers=ON;");
    }

    private static bool EnsureSchema(SqliteConnection connection)
    {
        var exists = Convert.ToInt64(ExecuteScalar(connection,
            "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='schema_version';")) > 0;
        if (exists)
        {
            return false;
        }

        using var tx = connection.BeginTransaction();
        Execute(connection, WorkspaceSchema.CreateSql, tx);
        Execute(connection, WorkspaceSchema.TriggerSql(), tx);
        Execute(connection,
            "INSERT INTO schema_version (version, applied_at) VALUES ($v, $t);", tx,
            ("$v", WorkspaceSchema.Version), ("$t", Iso(DateTimeOffset.UtcNow)));
        Execute(connection, "INSERT INTO core_state (id, core_epoch, ingress_seq) VALUES (1, 0, 0);", tx);
        tx.Commit();
        return true;
    }

    private static long BumpEpoch(SqliteConnection connection, bool freshlyCreated)
    {
        _ = freshlyCreated;
        using var tx = connection.BeginTransaction();
        Execute(connection, "UPDATE core_state SET core_epoch = core_epoch + 1 WHERE id = 1;", tx);
        var epoch = Convert.ToInt64(ExecuteScalar(connection, "SELECT core_epoch FROM core_state WHERE id = 1;", tx));
        tx.Commit();
        return epoch;
    }

    /// <summary>
    /// Acquire the single writer. Blocks until the previous writer completes — the control path
    /// waits rather than erroring, which is the right shape for one local operator.
    /// </summary>
    public StoreWriter BeginWrite()
    {
        ObjectDisposedException.ThrowIf(_disposed, this);
        _writerGate.Wait();
        try
        {
            return new StoreWriter(_writeConnection, _writerGate);
        }
        catch
        {
            _writerGate.Release();
            throw;
        }
    }

    /// <summary>
    /// A read connection pinned to <c>query_only=1</c>, so a read path physically cannot write
    /// (spike S6) — reads never queue behind the writer.
    /// </summary>
    public StoreReader BeginRead()
    {
        ObjectDisposedException.ThrowIf(_disposed, this);
        var connection = new SqliteConnection(_connectionString);
        connection.Open();
        Execute(connection, "PRAGMA foreign_keys=ON;");
        Execute(connection, "PRAGMA query_only=1;");
        return new StoreReader(connection);
    }

    public void Dispose()
    {
        if (_disposed)
        {
            return;
        }

        _disposed = true;
        _writeConnection.Dispose();
        _writerGate.Dispose();
        SqliteConnection.ClearAllPools();
    }

    internal static string Iso(DateTimeOffset value) => value.ToUniversalTime().ToString("O");

    internal static void Execute(
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

    internal static object? ExecuteScalar(
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

        return command.ExecuteScalar();
    }
}
