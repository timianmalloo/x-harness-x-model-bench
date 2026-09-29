using AiDe.Core.Presentation;

namespace AiDe.Core.Watcher;

/// <summary>One repository's sessions in the fleet map.</summary>
public sealed record RepositorySessions(RepositoryIdentity Repository, IReadOnlyList<WatcherSessionSnapshot> Sessions);

/// <summary>The cross-repository fleet: the <c>repository -&gt; sessions</c> map (spec item 3, US-3).</summary>
public sealed record FleetView(IReadOnlyList<RepositorySessions> Repositories)
{
    public int RepositoryCount => Repositories.Count;

    public int SessionCount => Repositories.Sum(r => r.Sessions.Count);
}

/// <summary>
/// Builds the cross-repository fleet map from one or more session sources - each store/daemon is per
/// workspace, so a fleet view is an aggregation over &gt;=2 sources, grouped by the session's own
/// repository identity (its canonical path). Deterministic order: repositories by display name then
/// canonical path, sessions by id. Pure - it reads the slice-3 session read model, adds no store.
/// </summary>
public sealed class FleetAggregator
{
    public FleetView Aggregate(IEnumerable<IWatcherSessionsQuery> sources)
    {
        ArgumentNullException.ThrowIfNull(sources);

        var byRepo = new Dictionary<string, (RepositoryIdentity Repo, List<WatcherSessionSnapshot> Sessions)>(StringComparer.Ordinal);
        foreach (var source in sources)
        {
            foreach (var snapshot in source.GetSessions())
            {
                var repo = snapshot.Binding.Repository;
                if (!byRepo.TryGetValue(repo.CanonicalPath, out var entry))
                {
                    entry = (repo, new List<WatcherSessionSnapshot>());
                    byRepo[repo.CanonicalPath] = entry;
                }

                entry.Sessions.Add(snapshot);
            }
        }

        var repositories = byRepo.Values
            .OrderBy(e => e.Repo.DisplayName, StringComparer.Ordinal)
            .ThenBy(e => e.Repo.CanonicalPath, StringComparer.Ordinal)
            .Select(e => new RepositorySessions(
                e.Repo,
                [.. e.Sessions.OrderBy(s => s.SessionId, StringComparer.Ordinal)]))
            .ToList();

        return new FleetView(repositories);
    }

    public FleetView Aggregate(params IWatcherSessionsQuery[] sources)
        => Aggregate((IEnumerable<IWatcherSessionsQuery>)sources);
}
