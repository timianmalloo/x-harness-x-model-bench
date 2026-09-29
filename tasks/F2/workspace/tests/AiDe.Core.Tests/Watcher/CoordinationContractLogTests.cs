using AiDe.Core.Watcher;

namespace AiDe.Core.Tests.Watcher;

/// <summary>
/// LK-COORDLOG-01..N - the session-side contract writer + log reader/pump (design-watcher-coordination-contract
/// residual, slice 2). D4 real-filesystem tests: the writer produces the coord-core append shape (atomic
/// append, LOG-A leading newline, incrementing seq) and the reader/pump feeds the same adapter, so a
/// non-AI-Forward session registers and heartbeats end to end through real files.
/// </summary>
public sealed class CoordinationContractLogTests
{
    private static readonly DateTimeOffset At = DateTimeOffset.UnixEpoch;

    private sealed class TempDir : IDisposable
    {
        public string Path { get; } = System.IO.Path.Combine(
            System.IO.Path.GetTempPath(), $"aide-coordlog-{Guid.NewGuid():N}");

        public TempDir() => Directory.CreateDirectory(Path);

        public void Dispose()
        {
            try { Directory.Delete(Path, recursive: true); }
            catch (IOException) { /* a transient handle on Windows; the temp dir is reclaimed anyway */ }
        }
    }

    private static IReadOnlyDictionary<string, string?> RegisterAttrs(string? harness = "claude-code", string? model = "opus-4-8")
        => WatcherFixtures.HarnessRegistration(harnessName: harness, modelName: model).Attributes;

    private static (InjectedContractIngest adapter, InMemoryWatcherObservationStore store, LivenessProjection liveness)
        NewAdapter()
    {
        var store = new InMemoryWatcherObservationStore();
        var clock = new FakeMonotonicClock();
        var registrar = new TrustedRegistrar(store, new SequentialCapabilityFactory(), clock, () => "s1");
        var host = new IngestHost(store, registrar, new FixedTimeProvider(At));
        var liveness = new LivenessProjection(store, clock, TimeSpan.FromSeconds(30));
        return (new InjectedContractIngest(host), store, liveness);
    }

    [Fact]
    public void Writer_WritesRegister_ReaderParsesItBack()
    {
        using var temp = new TempDir();
        var writer = new CoordContractWriter(temp.Path, new FixedTimeProvider(At));

        writer.WriteRegister("ext-1", RegisterAttrs());

        var events = CoordContractLog.ReadDirectory(temp.Path);
        var register = Assert.IsType<ContractRegister>(Assert.Single(events));
        Assert.Equal("ext-1", register.ExternalSessionId);
        Assert.Equal("claude-code", register.Attributes[OtelAttributes.ServiceName]);
    }

    [Fact]
    public void WriterAndPump_RegisterThenHeartbeat_SessionIsAliveInTheStore()
    {
        using var temp = new TempDir();
        var writer = new CoordContractWriter(temp.Path, new FixedTimeProvider(At));
        writer.WriteRegister("ext-1", RegisterAttrs());
        writer.WriteHeartbeat("ext-1");

        var (adapter, store, liveness) = NewAdapter();
        var applied = new CoordContractLogPump(temp.Path, adapter).PumpOnce();

        Assert.Equal(2, applied);
        Assert.Equal(1, adapter.Stats.Registered);
        Assert.Equal(1, adapter.Stats.Heartbeats);
        Assert.NotNull(store.FindSession("s1"));
        Assert.Equal(LivenessState.Alive, liveness.Evaluate("s1"));
    }

    [Fact]
    public void Writer_KeepsEachRecordOnItsOwnLine_EvenAfterAnUnterminatedFile_LOGA()
    {
        using var temp = new TempDir();
        var writer = new CoordContractWriter(temp.Path, new FixedTimeProvider(At));
        writer.WriteRegister("ext-1", RegisterAttrs());

        // Simulate a crash / hand edit that left the file without its trailing newline.
        var file = System.IO.Path.Combine(temp.Path, "ext-1.jsonl");
        var raw = File.ReadAllText(file).TrimEnd('\n', '\r');
        File.WriteAllText(file, raw);

        writer.WriteHeartbeat("ext-1"); // must emit a LEADING newline so it does not fuse

        var events = CoordContractLog.ReadDirectory(temp.Path);
        Assert.Equal(2, events.Count); // both records readable; nothing fused into a malformed line
        Assert.IsType<ContractRegister>(events[0]);
        Assert.IsType<ContractHeartbeat>(events[1]);
    }

    [Fact]
    public void Writer_AssignsIncrementingSeq()
    {
        using var temp = new TempDir();
        var writer = new CoordContractWriter(temp.Path, new FixedTimeProvider(At));

        writer.WriteRegister("ext-1", RegisterAttrs());
        writer.WriteHeartbeat("ext-1");

        var events = CoordContractLog.ReadDirectory(temp.Path);
        Assert.Equal(1, events[0].Seq);
        Assert.Equal(2, events[1].Seq);
    }

    [Fact]
    public void ReadDirectory_MissingDirectory_ReturnsEmpty()
    {
        var missing = System.IO.Path.Combine(System.IO.Path.GetTempPath(), $"aide-coordlog-missing-{Guid.NewGuid():N}");
        Assert.Empty(CoordContractLog.ReadDirectory(missing));
    }

    [Fact]
    public void Pump_ReRun_IsIdempotent_NoDoubleRegister()
    {
        using var temp = new TempDir();
        var writer = new CoordContractWriter(temp.Path, new FixedTimeProvider(At));
        writer.WriteRegister("ext-1", RegisterAttrs());

        var (adapter, _, _) = NewAdapter();
        var pump = new CoordContractLogPump(temp.Path, adapter);
        pump.PumpOnce();
        pump.PumpOnce(); // re-reading the whole log must not register a second time

        Assert.Equal(1, adapter.Stats.Registered);
        Assert.Equal(1, adapter.Stats.DuplicateRegister);
    }

    [Fact]
    public void Writer_TwoSessions_WriteSeparateFiles_BothRead()
    {
        using var temp = new TempDir();
        var writer = new CoordContractWriter(temp.Path, new FixedTimeProvider(At));

        writer.WriteRegister("ext-a", RegisterAttrs());
        writer.WriteRegister("ext-b", RegisterAttrs());

        Assert.Equal(2, Directory.GetFiles(temp.Path, "*.jsonl").Length);
        var events = CoordContractLog.ReadDirectory(temp.Path);
        Assert.Equal(2, events.Count);
        Assert.All(events, e => Assert.IsType<ContractRegister>(e));
    }
}
