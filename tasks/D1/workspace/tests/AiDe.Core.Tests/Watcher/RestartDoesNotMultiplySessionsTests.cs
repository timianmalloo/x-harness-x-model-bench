using AiDe.Core.Watcher;

namespace AiDe.Core.Tests.Watcher;

/// <summary>
/// A restart adopts the terminal's session; it does not mint a second one.
/// </summary>
/// <remarks>
/// <para><b>MEASURED 2026-09-03, in a real store.</b> A coordination log holding <b>21</b> register
/// lines had produced <b>3,232</b> sessions from <b>6</b> terminals — one terminal alone accounted
/// for 922. The Sessions surface showed "3012 session(s) · 3 alive", and every phantom was a
/// leaderboard cohort member.</para>
///
/// <para><b>The mechanism: durable input, in-memory dedup.</b> <c>CoordContractLogPump.PumpOnce</c>
/// re-reads the WHOLE log every tick, which is idempotent against the adapter's
/// <c>_byExternalId</c> map — but that map dies with the process while the log does not. So every
/// application start replayed all 21 registers, and <c>TrustedRegistrar.Register</c> minted a fresh
/// GUID for each. Duplication once per restart, forever, and nothing failed.</para>
///
/// <para><b>What made it invisible.</b> Every existing test registers through ONE adapter, where the
/// in-memory map works perfectly. The bug lives entirely in the seam between two process lifetimes,
/// which no single-adapter test can reach — so the suite was green while the store grew without
/// bound. That is why this test builds a second adapter over the SAME store rather than asserting
/// harder against one.</para>
/// </remarks>
public sealed class RestartDoesNotMultiplySessionsTests
{
    private const double At = 1_700_000_000d;

    private static Dictionary<string, string?> RegisterAttrs(string terminalId) => new(StringComparer.Ordinal)
    {
        [OtelAttributes.RepoPath] = "C:/repos/app",
        [OtelAttributes.RepoDisplay] = "app",
        [OtelAttributes.WorktreeBranch] = "main",
        [OtelAttributes.WorktreePath] = "C:/repos/app",
        [OtelAttributes.TerminalId] = terminalId,
        [OtelAttributes.AgentName] = "claude-code",
    };

    /// <summary>A fresh adapter over an existing store — exactly what an application restart is.</summary>
    private static InjectedContractIngest NewAdapterOver(InMemoryWatcherObservationStore store)
    {
        var n = 0;
        var registrar = new TrustedRegistrar(
            store, new SequentialCapabilityFactory(), new FakeMonotonicClock(),
            () => $"minted-{++n}-{Guid.NewGuid().ToString("n")[..6]}");
        return new InjectedContractIngest(
            new IngestHost(store, registrar, new FixedTimeProvider(DateTimeOffset.UnixEpoch.AddSeconds(At))));
    }

    /// <summary>
    /// Ten restarts replaying one register line produce ONE session, not ten.
    /// </summary>
    /// <remarks>
    /// The number is deliberately larger than two: with two, an off-by-one fix that adopted only the
    /// first repeat would pass. Ten makes "adopts every time" the only shape that works.
    /// </remarks>
    [Fact]
    public void ReplayingOneRegisterAcrossTenRestartsYieldsOneSession()
    {
        var store = new InMemoryWatcherObservationStore();
        var line = new ContractRegister("term-1", RegisterAttrs("term-1"), At, 1);

        for (var restart = 0; restart < 10; restart++)
        {
            NewAdapterOver(store).Apply(line);
        }

        var session = Assert.Single(store.AllSessions());
        Assert.Equal("term-1", session.Binding.Terminal.TerminalId);
    }

    /// <summary>
    /// And the restarts are visible as generations, rather than being silently discarded.
    /// </summary>
    /// <remarks>
    /// Adoption must not erase the fact that the product restarted — that is the difference between
    /// deduplicating and forgetting. <c>RegisterNextGeneration</c> existed for exactly this and had
    /// no caller, so the counter sat at 1 forever while the session count grew instead.
    /// </remarks>
    [Fact]
    public void EachRestartIsANewGenerationOfTheSameSession()
    {
        var store = new InMemoryWatcherObservationStore();
        var line = new ContractRegister("term-1", RegisterAttrs("term-1"), At, 1);

        NewAdapterOver(store).Apply(line);
        var first = store.AllSessions().Single().Generation.Value;

        NewAdapterOver(store).Apply(line);
        NewAdapterOver(store).Apply(line);

        var session = Assert.Single(store.AllSessions());
        Assert.Equal(1, first);
        Assert.Equal(3, session.Generation.Value);
    }

    /// <summary>Two different terminals stay two sessions — adoption must not collapse them.</summary>
    /// <remarks>
    /// The other direction, and the one a too-eager fix breaks: a dedup keyed on something coarser
    /// than the terminal (the repository, say) would report one session for a workspace with three
    /// agents in it, which is the same defect pointed the other way.
    /// </remarks>
    [Fact]
    public void DifferentTerminalsRemainDifferentSessions()
    {
        var store = new InMemoryWatcherObservationStore();
        var adapter = NewAdapterOver(store);

        adapter.Apply(new ContractRegister("term-1", RegisterAttrs("term-1"), At, 1));
        adapter.Apply(new ContractRegister("term-2", RegisterAttrs("term-2"), At + 1, 2));

        Assert.Equal(2, store.AllSessions().Count);
    }

    /// <summary>
    /// Within one run the in-memory map still short-circuits, so a re-read is not even a generation.
    /// </summary>
    /// <remarks>
    /// The pump re-reads the whole log every tick, so this is the common path by far. Reaching the
    /// store for it would bump the generation on every tick and replace 3,232 sessions with one
    /// session at generation 3,232 — the same number wearing a different hat.
    /// </remarks>
    [Fact]
    public void AReReadWithinOneRunDoesNotBumpTheGeneration()
    {
        var store = new InMemoryWatcherObservationStore();
        var adapter = NewAdapterOver(store);
        var line = new ContractRegister("term-1", RegisterAttrs("term-1"), At, 1);

        adapter.Apply(line);
        adapter.Apply(line);
        adapter.Apply(line);

        var session = Assert.Single(store.AllSessions());
        Assert.Equal(1, session.Generation.Value);
        Assert.Equal(2, adapter.Stats.DuplicateRegister);
    }
}
