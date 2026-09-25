using AiDe.Core.Watcher;
using Microsoft.Data.Sqlite;

namespace AiDe.Core.Tests.Watcher;

/// <summary>
/// LK-SQLITE-01..10 — the durable observation store on a real SQLite file (D4: integration against the
/// real engine, not a substitute - only the real engine exhibits the trigger/pragma semantics). Proves
/// the same <see cref="IWatcherObservationStore"/> contract the in-memory store passes, plus persistence
/// across a reopen and the append-only invariant (DM11).
/// </summary>
public sealed class SqliteWatcherObservationStoreTests
{
    private static string NewDbPath()
    {
        var dir = Path.Combine(Path.GetTempPath(), "aide-tests", "watcher", Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(dir);
        return Path.Combine(dir, "watcher.db");
    }

    private static ObservedSpan Span(string session = "session-1", string source = "span-a", string trace = "trace-1")
        => new(session, trace, source, "Edit file", DateTimeOffset.UnixEpoch);

    [Fact]
    public void TryAppendSpan_NewSpan_PersistsAndCounts()
    {
        using var store = SqliteWatcherObservationStore.Open(NewDbPath());

        Assert.True(store.TryAppendSpan(Span()));

        Assert.Equal(1, store.SpanCount("session-1"));
    }

    [Fact]
    public void TryAppendSpan_DuplicateId_IsIgnoredIdempotently()
    {
        using var store = SqliteWatcherObservationStore.Open(NewDbPath());
        store.TryAppendSpan(Span());

        var second = store.TryAppendSpan(Span()); // same content-addressed id

        Assert.False(second);
        Assert.Equal(1, store.SpanCount("session-1"));
    }

    [Fact]
    public void Spans_PersistAcrossReopen()
    {
        var path = NewDbPath();
        using (var store = SqliteWatcherObservationStore.Open(path))
        {
            store.TryAppendSpan(Span(source: "span-a"));
            store.TryAppendSpan(Span(source: "span-b"));
        }

        // Reopen the same file: a real restart, not a lucky in-memory field.
        using var reopened = SqliteWatcherObservationStore.Open(path);
        Assert.Equal(2, reopened.SpanCount("session-1"));
    }

    [Fact]
    public void ObservedSpanFact_IsAppendOnly_UpdateIsRejected()
    {
        var path = NewDbPath();
        using var store = SqliteWatcherObservationStore.Open(path);
        store.TryAppendSpan(Span());

        using var raw = new SqliteConnection(
            new SqliteConnectionStringBuilder { DataSource = path, Mode = SqliteOpenMode.ReadWrite, Pooling = false }.ToString());
        raw.Open();
        using var update = raw.CreateCommand();
        update.CommandText = "UPDATE observed_span_fact SET operation_name = 'tampered';";

        var ex = Assert.Throws<SqliteException>(() => update.ExecuteNonQuery());
        Assert.Contains("append-only", ex.Message, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public void ObservedSpanFact_IsAppendOnly_DeleteIsRejected()
    {
        var path = NewDbPath();
        using var store = SqliteWatcherObservationStore.Open(path);
        store.TryAppendSpan(Span());

        using var raw = new SqliteConnection(
            new SqliteConnectionStringBuilder { DataSource = path, Mode = SqliteOpenMode.ReadWrite, Pooling = false }.ToString());
        raw.Open();
        using var delete = raw.CreateCommand();
        delete.CommandText = "DELETE FROM observed_span_fact;";

        var ex = Assert.Throws<SqliteException>(() => delete.ExecuteNonQuery());
        Assert.Contains("append-only", ex.Message, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public void Heartbeat_UpsertsAndReadsLatest_NullWhenNone()
    {
        using var store = SqliteWatcherObservationStore.Open(NewDbPath());

        Assert.Null(store.LastHeartbeat("session-1"));

        store.UpsertHeartbeat("session-1", 100);
        store.UpsertHeartbeat("session-1", 250);

        Assert.Equal(250, store.LastHeartbeat("session-1"));
    }

    [Fact]
    public void RecordSession_RoundTrips_IncludingNullHarnessAndModel()
    {
        using var store = SqliteWatcherObservationStore.Open(NewDbPath());
        var binding = WatcherFixtures.Binding(harness: null, model: null);
        store.RecordSession(new SessionRecord("session-1", new SessionGeneration(3), binding));

        var found = store.FindSession("session-1");

        Assert.NotNull(found);
        Assert.Equal(3, found!.Generation.Value);
        Assert.Null(found.Binding.Harness);
        Assert.Null(found.Binding.Model);
        Assert.Equal(binding.Agent.AgentName, found.Binding.Agent.AgentName);
    }

    [Fact]
    public void RecordSession_RoundTrips_HarnessModelAndTrust()
    {
        using var store = SqliteWatcherObservationStore.Open(NewDbPath());
        var binding = WatcherFixtures.Binding(
            harness: new HarnessIdentity("Claude Code", "1.0"),
            model: new ModelIdentity("Opus 4.8", "2026-08"),
            trust: TrustClassification.Asserted);
        store.RecordSession(new SessionRecord("session-1", new SessionGeneration(1), binding));

        var found = store.FindSession("session-1");

        Assert.Equal("Claude Code", found!.Binding.Harness!.Name);
        Assert.Equal("Opus 4.8", found.Binding.Model!.Name);
        Assert.Equal(TrustClassification.Asserted, found.Binding.Trust);
    }

    [Fact]
    public void FindSession_Unknown_ReturnsNull()
    {
        using var store = SqliteWatcherObservationStore.Open(NewDbPath());

        Assert.Null(store.FindSession("never-recorded"));
    }

    [Fact]
    public void Ended_MarkClearAndQuery()
    {
        using var store = SqliteWatcherObservationStore.Open(NewDbPath());

        Assert.False(store.IsEnded("session-1"));

        store.MarkEnded("session-1");
        Assert.True(store.IsEnded("session-1"));

        store.ClearEnded("session-1");
        Assert.False(store.IsEnded("session-1"));
    }

    [Fact]
    public void FullCore_ComposesOverSqlite_AndSurvivesReopen()
    {
        // The same registrar/ingest/liveness core, now over the durable store, and proven to persist.
        var path = NewDbPath();
        string sessionId;
        using (var store = SqliteWatcherObservationStore.Open(path))
        {
            var clock = new FakeMonotonicClock();
            var registrar = new TrustedRegistrar(store, new SequentialCapabilityFactory(), clock, () => "session-1");
            var ingest = new SpanIngest(store, registrar);
            var session = registrar.Register(WatcherFixtures.Binding(
                harness: new HarnessIdentity("Claude Code", "1.0"), model: new ModelIdentity("Opus 4.8", "2026-08")));
            sessionId = session.SessionId;

            Assert.Equal(IngestOutcome.Accepted, ingest.Ingest(sessionId, session.Capability, Span(sessionId)));
            Assert.Equal(IngestOutcome.DuplicateIgnored, ingest.Ingest(sessionId, session.Capability, Span(sessionId)));
        }

        using var reopened = SqliteWatcherObservationStore.Open(path);
        Assert.Equal(1, reopened.SpanCount(sessionId));
        var recovered = reopened.FindSession(sessionId);
        Assert.Equal("Opus 4.8", recovered!.Binding.Model!.Name);
    }
}
