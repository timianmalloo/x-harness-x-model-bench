using AiDe.Core.Presentation;
using AiDe.Core.Watcher;

namespace AiDe.Core.Tests.Watcher;

/// <summary>
/// LK-FLEET-01..N - the cross-repository fleet aggregator (design-watcher-message-board, slice 6). The
/// claim (spec US-3 item 3): the repo-&gt;session map is built across &gt;=2 sources, grouped by the
/// session's own repository identity, in a deterministic order.
/// </summary>
public sealed class FleetAggregatorTests
{
    private static readonly FleetAggregator Aggregator = new();

    private sealed class FakeSessionsQuery(params WatcherSessionSnapshot[] sessions) : IWatcherSessionsQuery
    {
        public IReadOnlyList<WatcherSessionSnapshot> GetSessions() => sessions;
    }

    private static WatcherSessionSnapshot Snapshot(string id, string repoPath, string repoDisplay)
    {
        var repo = new RepositoryIdentity(repoPath, repoDisplay);
        var binding = new SessionBinding(
            repo,
            new WorktreeIdentity(repo, "main", repoPath),
            new TerminalIdentity("t1"),
            new AgentIdentity("agent-1"),
            null, null, TrustClassification.Asserted);
        return new WatcherSessionSnapshot(id, binding, LivenessState.Alive, 0);
    }

    [Fact]
    public void Aggregate_TwoReposAcrossTwoSources_GroupsByRepository()
    {
        var alpha = new FakeSessionsQuery(Snapshot("s-a", "C:/repos/alpha", "alpha"));
        var beta = new FakeSessionsQuery(Snapshot("s-b", "C:/repos/beta", "beta"));

        var fleet = Aggregator.Aggregate(alpha, beta);

        Assert.Equal(2, fleet.RepositoryCount);
        Assert.Equal(2, fleet.SessionCount);
        Assert.Collection(fleet.Repositories,
            r => Assert.Equal("alpha", r.Repository.DisplayName),
            r => Assert.Equal("beta", r.Repository.DisplayName));
    }

    [Fact]
    public void Aggregate_SameRepoAcrossSources_MergesIntoOneRepositoryWithBothSessions()
    {
        var one = new FakeSessionsQuery(Snapshot("s-1", "C:/repos/shared", "shared"));
        var two = new FakeSessionsQuery(Snapshot("s-2", "C:/repos/shared", "shared"));

        var fleet = Aggregator.Aggregate(one, two);

        var repo = Assert.Single(fleet.Repositories);
        Assert.Equal("shared", repo.Repository.DisplayName);
        Assert.Equal(2, repo.Sessions.Count);
    }

    [Fact]
    public void Aggregate_NoSources_IsEmpty()
    {
        var fleet = Aggregator.Aggregate();

        Assert.Equal(0, fleet.RepositoryCount);
        Assert.Equal(0, fleet.SessionCount);
        Assert.Empty(fleet.Repositories);
    }

    [Fact]
    public void Aggregate_OrdersRepositoriesByDisplay_AndSessionsById()
    {
        var source = new FakeSessionsQuery(
            Snapshot("s-z", "C:/repos/zulu", "zulu"),
            Snapshot("s-a", "C:/repos/alpha", "alpha"),
            Snapshot("s-b", "C:/repos/alpha", "alpha"));

        var fleet = Aggregator.Aggregate(source);

        Assert.Equal("alpha", fleet.Repositories[0].Repository.DisplayName);
        Assert.Equal("zulu", fleet.Repositories[1].Repository.DisplayName);
        Assert.Collection(fleet.Repositories[0].Sessions,
            s => Assert.Equal("s-a", s.SessionId),
            s => Assert.Equal("s-b", s.SessionId));
    }

    [Fact]
    public void Aggregate_OverRealStores_BuildsTheRepoSessionMap()
    {
        var (queryA, _) = RealRepo("C:/repos/alpha", "alpha", "sa");
        var (queryB, _) = RealRepo("C:/repos/beta", "beta", "sb");

        var fleet = Aggregator.Aggregate(queryA, queryB);

        Assert.Equal(2, fleet.RepositoryCount);
        Assert.Equal(2, fleet.SessionCount);
    }

    private static (WatcherSessionsQuery query, InMemoryWatcherObservationStore store) RealRepo(
        string repoPath, string repoDisplay, string sessionId)
    {
        var store = new InMemoryWatcherObservationStore();
        var clock = new FakeMonotonicClock();
        var registrar = new TrustedRegistrar(store, new SequentialCapabilityFactory(), clock, () => sessionId);
        var repo = new RepositoryIdentity(repoPath, repoDisplay);
        registrar.Register(new SessionBinding(
            repo, new WorktreeIdentity(repo, "main", repoPath),
            new TerminalIdentity("t1"), new AgentIdentity("agent-1"), null, null, TrustClassification.Asserted));
        var liveness = new LivenessProjection(store, clock, TimeSpan.FromSeconds(30));
        return (new WatcherSessionsQuery(store, liveness), store);
    }
}
