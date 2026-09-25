using AiDe.Core.Presentation;
using AiDe.Core.Watcher;

namespace AiDe.Core.Tests.Watcher;

/// <summary>
/// LK-HOST-01..08 - the in-process watcher host (conn-5). It composes the store, registrar, ingest host,
/// injected coordination-contract ingest + log pump, and (best-effort) the OTLP receiver into one running
/// unit. The claims: a coordination-contract log registers a session into the shared store through the
/// host (the file-based smoke-test ingest); re-pumping is idempotent; liveness is exact because the host's
/// registrar and liveness projection share one monotonic clock (in-process); an enqueued span is drained
/// by PumpOnce; and the shared store feeds the same read queries the WPF surfaces use (E11).
/// </summary>
public sealed class WatcherHostTests
{
    private static readonly DateTimeOffset At = DateTimeOffset.UnixEpoch;

    private sealed class TempDir : IDisposable
    {
        public string Path { get; } = System.IO.Path.Combine(
            System.IO.Path.GetTempPath(), $"aide-host-{Guid.NewGuid():N}");

        public TempDir() => Directory.CreateDirectory(Path);

        public void Dispose()
        {
            try { Directory.Delete(Path, recursive: true); }
            catch (IOException) { /* transient handle on Windows; reclaimed anyway */ }
        }
    }

    private static IReadOnlyDictionary<string, string?> RegisterAttrs()
        => WatcherFixtures.HarnessRegistration(harnessName: "claude-code", modelName: "opus-4-8").Attributes;

    [Fact]
    public void PumpOnce_RegistersACoordinationSession_IntoTheSharedStore()
    {
        using var data = new TempDir();
        using var coord = new TempDir();
        var writer = new CoordContractWriter(coord.Path, new FixedTimeProvider(At));
        writer.WriteRegister("ext-1", RegisterAttrs());
        writer.WriteHeartbeat("ext-1");

        using var host = WatcherHost.Open(data.Path, coord.Path, new FixedTimeProvider(At), new FakeMonotonicClock());
        var applied = host.PumpOnce();

        Assert.Equal(2, applied);                                  // register + heartbeat
        var session = Assert.Single(host.Store.AllSessions());
        Assert.Equal("claude-code", session.Binding.Harness?.Name);
    }

    [Fact]
    public void PumpOnce_IsIdempotent_ReReadDoesNotDoubleRegister()
    {
        using var data = new TempDir();
        using var coord = new TempDir();
        new CoordContractWriter(coord.Path, new FixedTimeProvider(At)).WriteRegister("ext-1", RegisterAttrs());

        using var host = WatcherHost.Open(data.Path, coord.Path, new FixedTimeProvider(At), new FakeMonotonicClock());
        host.PumpOnce();
        host.PumpOnce(); // re-reading the whole directory must not register a second session

        Assert.Single(host.Store.AllSessions());
    }

    [Fact]
    public void Liveness_IsExact_InProcess_SharedMonotonicClock()
    {
        using var data = new TempDir();
        using var coord = new TempDir();
        var writer = new CoordContractWriter(coord.Path, new FixedTimeProvider(At));
        writer.WriteRegister("ext-1", RegisterAttrs());
        writer.WriteHeartbeat("ext-1");

        // A fake clock the host's registrar AND liveness projection both read - so the heartbeat tick and
        // the "now" tick agree, which is the whole point of hosting the ingest in-process.
        var clock = new FakeMonotonicClock();
        using var host = WatcherHost.Open(data.Path, coord.Path, new FixedTimeProvider(At), clock, TimeSpan.FromSeconds(30));
        host.PumpOnce();

        var session = Assert.Single(host.Store.AllSessions());
        Assert.Equal(LivenessState.Alive, host.Liveness.Evaluate(session.SessionId));
    }

    [Fact]
    public void SharedStore_FeedsTheSessionsReadQuery_TheSurfacesUse()
    {
        // E11: the same store the host writes is read THROUGH the query the WPF Sessions pane folds.
        using var data = new TempDir();
        using var coord = new TempDir();
        var writer = new CoordContractWriter(coord.Path, new FixedTimeProvider(At));
        writer.WriteRegister("ext-1", RegisterAttrs());
        writer.WriteHeartbeat("ext-1");

        using var host = WatcherHost.Open(data.Path, coord.Path, new FixedTimeProvider(At), new FakeMonotonicClock());
        host.PumpOnce();

        var pane = new WatcherSessionsPaneViewModel(new WatcherSessionsQuery(host.Store, host.Liveness));
        pane.Load();

        Assert.Equal(PaneState.Ready, pane.State);
        Assert.Single(pane.Rows);
        Assert.Equal("claude-code", pane.Rows[0].Harness);
    }

    [Fact]
    public void Ingest_EnqueuedSpan_IsDrainedByPumpOnce()
    {
        using var data = new TempDir();
        using var coord = new TempDir();
        using var host = WatcherHost.Open(data.Path, coord.Path, new FixedTimeProvider(At), new FakeMonotonicClock());

        var session = host.Ingest.Register(WatcherFixtures.HarnessRegistration());
        host.Ingest.Enqueue(new HarnessSpanEvent(session.Capability, new HarnessSpan(
            "trace-1", "span-a", "chat.completion",
            new Dictionary<string, string?>(StringComparer.Ordinal) { [OtelAttributes.SessionId] = session.SessionId })));

        host.PumpOnce(); // pumps coord (nothing) AND drains the queued span

        Assert.Equal(1, host.Store.SpanCount(session.SessionId));
        Assert.Equal(1, host.Stats.Ingested);
    }

    [Fact]
    public void PumpOnce_EmptyCoordDirectory_IsZero_NoThrow()
    {
        using var data = new TempDir();
        using var coord = new TempDir();
        using var host = WatcherHost.Open(data.Path, coord.Path, new FixedTimeProvider(At), new FakeMonotonicClock());

        Assert.Equal(0, host.PumpOnce());
        Assert.Empty(host.Store.AllSessions());
    }

    [Fact]
    public void Open_CreatesTheDataAndCoordDirectories_IfMissing()
    {
        var baseDir = System.IO.Path.Combine(System.IO.Path.GetTempPath(), $"aide-host-mk-{Guid.NewGuid():N}");
        var data = System.IO.Path.Combine(baseDir, "data");
        var coord = System.IO.Path.Combine(baseDir, "coord");
        try
        {
            using var host = WatcherHost.Open(data, coord, new FixedTimeProvider(At), new FakeMonotonicClock());

            Assert.True(Directory.Exists(data));
            Assert.True(Directory.Exists(coord));
        }
        finally
        {
            try { Directory.Delete(baseDir, recursive: true); } catch (IOException) { }
        }
    }
}
