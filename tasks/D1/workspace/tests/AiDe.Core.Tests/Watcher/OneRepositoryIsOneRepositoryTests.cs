using AiDe.Core.Presentation;
using AiDe.Core.Watcher;

namespace AiDe.Core.Tests.Watcher;

/// <summary>
/// Two spellings of one repository path are one repository, not two.
/// </summary>
/// <remarks>
/// <para><b>US-3's second acceptance clause:</b> <i>"Given a worktree path aliases an already watched
/// repository, When it is added, Then it appears as a Worktree under that Repository, not as a
/// duplicate Repository."</i></para>
///
/// <para><b>The defect.</b> <c>RepositoryIdentity.CanonicalPath</c> is a plain string that nothing
/// canonicalises — the name asserts an invariant no code enforces — and <c>FleetAggregator</c> groups
/// by it with <c>StringComparer.Ordinal</c>. On Windows that splits one repository into several: paths
/// are case-insensitive, git reports forward slashes where .NET reports backslashes, and a trailing
/// separator is not distinguishable from its absence.</para>
///
/// <para><b>It has already been hit once, at one producer.</b> The design session found the
/// slash-direction case in session identity this morning and normalised it there — <i>"RepoPath is
/// what groups sessions, so two spellings of one repo would have presented as two repos"</i>. That
/// fixed the producer it was found in. The grouping key itself was left ordinal, so any other route
/// into the store — a different producer, an older row, a manual registration — still splits.</para>
///
/// <para><b>Fixing the type rather than the aggregator</b> is deliberate: the same field is the
/// grouping key in <c>FleetAggregator</c>, the persisted column in the store, the registration guard
/// in <c>TrustedRegistrar</c> and the lookup key in the coordination contract. A comparison fixed in
/// one consumer leaves the other three disagreeing about whether two sessions are in the same
/// repository.</para>
/// </remarks>
public sealed class OneRepositoryIsOneRepositoryTests
{
    private sealed class Sessions(params WatcherSessionSnapshot[] snapshots) : IWatcherSessionsQuery
    {
        public IReadOnlyList<WatcherSessionSnapshot> GetSessions() => snapshots;
    }

    /// <summary>Uses the shared fixture so the binding's shape is not restated here (DC-021).</summary>
    private static WatcherSessionSnapshot Session(string sessionId, string repoPath, string worktree)
    {
        var binding = WatcherFixtures.Binding(repoPath: repoPath, terminal: $"term-{sessionId}");
        var repo = binding.Repository;

        return new WatcherSessionSnapshot(
            sessionId,
            binding with { Worktree = new WorktreeIdentity(repo, "main", worktree) },
            LivenessState.Alive, 0);
    }

    private static FleetView Aggregate(params WatcherSessionSnapshot[] snapshots) =>
        new FleetAggregator().Aggregate([new Sessions(snapshots)]);

    // Platform=Windows: asserts a case-INsensitive filesystem; on Linux case correctly does split a repository
    [Trait("Platform", "Windows")]
    [Fact]
    public void SlashDirectionDoesNotSplitARepository()
    {
        // git answers with forward slashes and .NET with backslashes. Both name one repository.
        var fleet = Aggregate(
            Session("s1", @"C:\Projects\ai-de", @"C:\Projects\ai-de"),
            Session("s2", "C:/Projects/ai-de", "C:/Projects/ai-de-worktree"));

        Assert.Single(fleet.Repositories);
    }

    // Platform=Windows: asserts a case-INsensitive filesystem; on Linux case correctly does split a repository
    [Trait("Platform", "Windows")]
    [Fact]
    public void CaseDoesNotSplitARepository()
    {
        // Windows paths are case-insensitive. Ordinal grouping makes one repository into two.
        var fleet = Aggregate(
            Session("s1", @"C:\Projects\ai-de", @"C:\Projects\ai-de"),
            Session("s2", @"c:\projects\AI-DE", @"c:\projects\AI-DE-worktree"));

        Assert.Single(fleet.Repositories);
    }

    [Fact]
    public void ATrailingSeparatorDoesNotSplitARepository()
    {
        var fleet = Aggregate(
            Session("s1", @"C:\Projects\ai-de", @"C:\Projects\ai-de"),
            Session("s2", @"C:\Projects\ai-de\", @"C:\Projects\ai-de-worktree"));

        Assert.Single(fleet.Repositories);
    }

    [Fact]
    public void GenuinelyDifferentRepositoriesStayApart()
    {
        // The DC-016 guard, and it is not hypothetical: canonicalising too hard — lowercasing a
        // whole path on a case-sensitive filesystem, or trimming to the folder name — would merge
        // repositories that only share a display name, which is the case CanonicalPath exists for.
        var fleet = Aggregate(
            Session("s1", @"C:\Projects\ai-de", @"C:\Projects\ai-de"),
            Session("s2", @"C:\Other\ai-de", @"C:\Other\ai-de"));

        Assert.Equal(2, fleet.Repositories.Count);
    }

    [Fact]
    public void AnAliasedWorktreeAppearsUnderTheRepositoryItAliases()
    {
        // US-3's clause stated directly: the second spelling is a WORKTREE of the first repository,
        // not a repository of its own.
        var fleet = Aggregate(
            Session("s1", @"C:\Projects\ai-de", @"C:\Projects\ai-de"),
            Session("s2", "C:/Projects/ai-de", "C:/Projects/ai-de-feature"));

        var repository = Assert.Single(fleet.Repositories);

        // Two distinct worktrees under the one repository, rather than two repositories.
        Assert.Equal(2, repository.Sessions.Select(s => s.Binding.Worktree.Path).Distinct().Count());
    }
}
