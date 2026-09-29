using System.Text.Json;
using AiDe.Core.Watcher;

namespace AiDe.Core.Tests.Watcher;

/// <summary>
/// An agent that registers its worktree as its repository is corrected, and told.
/// </summary>
/// <remarks>
/// <para><b>The defect.</b> <c>repo.path</c> is the grouping key in the fleet map, the registration
/// guard, the score segment AND the message board partition. AI-DE's own shell sends the repository
/// (it takes <c>--git-common-dir</c>'s parent), but an externally registering agent composes its own
/// attributes and nothing enforced that it does the same. An agent sending its worktree lands on a
/// board nobody is on — and every reply it makes to another session's thread is REFUSED as a
/// cross-repository thread, with an error message that is literally true and completely misleading
/// to an agent which knows it is in the same repository.</para>
///
/// <para><b>Correct, not reject</b>, because detecting a worktree-shaped path and correcting it are
/// the same filesystem read: a rejection could only fire where a correction would have succeeded,
/// and would be silent in the case that motivated it (a path this machine cannot see). Rejecting
/// also removes the agent from observation to protect a segmentation key, which is the opposite of
/// what the value is for.</para>
///
/// <para><b>But never silently</b>, which is what <see cref="RegistrationPublisher"/> is for. A
/// rewrite the registrant is not told about leaves it sending the wrong value forever, with the
/// correction depending permanently on our resolution staying right.</para>
/// </remarks>
public sealed class AWorktreeRegistrationIsCorrectedAndSaidSoTests
{
    private const double At = 1000;
    private const string Repository = @"C:\repos\app";
    private const string Worktree = @"C:\repos\app-feature";

    /// <summary>A locator that answers for one known worktree and "unknown" for everything else.</summary>
    private sealed class StubLocator(string worktree, string? repository) : IRepositoryLocator
    {
        public string? RepositoryFor(string checkoutPath)
            => string.Equals(
                new RepositoryIdentity(checkoutPath, "x").CanonicalPath,
                new RepositoryIdentity(worktree, "x").CanonicalPath,
                StringComparison.Ordinal)
                ? repository
                : null;
    }

    private static Dictionary<string, string?> Attrs(string repoPath, string terminal = "term-1") =>
        new(StringComparer.Ordinal)
        {
            [OtelAttributes.RepoPath] = repoPath,
            [OtelAttributes.RepoDisplay] = "app",
            [OtelAttributes.WorktreePath] = repoPath,
            [OtelAttributes.WorktreeBranch] = "feature",
            [OtelAttributes.TerminalId] = terminal,
            [OtelAttributes.AgentName] = "agent-ext",
            [OtelAttributes.ServiceName] = "claude-code",
        };

    private static IngestHost HostWith(IRepositoryLocator locator, InMemoryWatcherObservationStore store)
    {
        var n = 0;
        var registrar = new TrustedRegistrar(
            store, new SequentialCapabilityFactory(), new FakeMonotonicClock(), () => $"session-{++n}");

        return new IngestHost(
            store, registrar, new FixedTimeProvider(DateTimeOffset.UnixEpoch.AddSeconds(At)),
            locator: locator);
    }

    [Fact]
    public void AWorktreePathIsRegisteredAsItsRepository_AndTheWorktreeKeepsItsOwnPath()
    {
        var store = new InMemoryWatcherObservationStore();
        var host = HostWith(new StubLocator(Worktree, Repository), store);

        host.Register(new HarnessRegistration(Attrs(Worktree)));

        var session = Assert.Single(store.AllSessions());

        // The repository is corrected...
        Assert.Equal(
            new RepositoryIdentity(Repository, "app").CanonicalPath,
            session.Binding.Repository.CanonicalPath);

        // ...and so is the worktree's view of it, because they are one fact and a disagreement
        // between them is the aliasing this type exists to prevent.
        Assert.Equal(
            session.Binding.Repository.CanonicalPath,
            session.Binding.Worktree.Repository.CanonicalPath);

        // But the checkout keeps its OWN path. It is still where the session is; one repository,
        // several worktrees is the whole point.
        Assert.Equal(
            new RepositoryIdentity(Worktree, "x").CanonicalPath,
            new RepositoryIdentity(session.Binding.Worktree.Path, "x").CanonicalPath);
    }

    [Fact]
    public void TwoSessionsInDifferentWorktreesShareOneBoard()
    {
        // THE DEFECT THIS PREVENTS, stated as the behaviour rather than the field. Before the
        // correction these two sessions were on different board partitions, and a reply across them
        // was refused as a cross-repository thread.
        var store = new InMemoryWatcherObservationStore();
        var host = HostWith(new StubLocator(Worktree, Repository), store);

        host.Register(new HarnessRegistration(Attrs(Worktree, "term-1")));
        host.Register(new HarnessRegistration(Attrs(Repository, "term-2")));

        var keys = store.AllSessions()
            .Select(s => s.Binding.Repository.CanonicalPath)
            .Distinct(StringComparer.Ordinal)
            .ToList();

        Assert.Equal(2, store.AllSessions().Count);
        Assert.Single(keys);
    }

    [Fact]
    public void ARepositoryRootIsLeftAlone_AndNoNoticeIsRaised()
    {
        var store = new InMemoryWatcherObservationStore();
        var host = HostWith(new StubLocator(Worktree, Repository), store);

        host.Register(new HarnessRegistration(Attrs(Repository)));

        var session = Assert.Single(store.AllSessions());
        Assert.Equal(new RepositoryIdentity(Repository, "app").CanonicalPath, session.Binding.Repository.CanonicalPath);

        // Nothing was changed, so there is nothing to tell anyone. A notice here would be the
        // product announcing that it left something alone.
        Assert.Empty(host.DrainRegistrationNotices());
    }

    [Fact]
    public void AnUnresolvablePathIsLeftAlone_RatherThanGuessed()
    {
        // The case that ruled out rejection: this machine cannot see the registrant's filesystem, so
        // the locator answers "unknown". Leaving the claim intact is the honest move — a guess here
        // would be the split reintroduced silently, and a rejection would remove the agent from
        // observation for a fact nobody established.
        var store = new InMemoryWatcherObservationStore();
        var host = HostWith(new StubLocator(Worktree, repository: null), store);

        // The worktree path is made DIFFERENT from the claimed repository, deliberately. The first
        // version of this test used the same value for both (the Attrs helper sets them equal), so a
        // fallback of "guess the worktree path" produced the identical answer and the test passed
        // while the guess ran. Mutation replay found it: removing the null guard reddened nothing.
        var attrs = Attrs(Worktree);
        attrs[OtelAttributes.WorktreePath] = @"C:epospp-somewhere-else";

        host.Register(new HarnessRegistration(attrs));

        var session = Assert.Single(store.AllSessions());
        Assert.Equal(new RepositoryIdentity(Worktree, "x").CanonicalPath, session.Binding.Repository.CanonicalPath);
        Assert.Empty(host.DrainRegistrationNotices());
    }

    [Fact]
    public void TheAgentIsToldWhatChanged_AndWhy()
    {
        var store = new InMemoryWatcherObservationStore();
        var host = HostWith(new StubLocator(Worktree, Repository), store);

        host.Register(new HarnessRegistration(Attrs(Worktree)));

        var notice = Assert.Single(host.DrainRegistrationNotices());
        var coord = NewDirectory();

        try
        {
            var published = RegistrationPublisher.Publish(coord, notice);
            var document = JsonDocument.Parse(File.ReadAllText(published)).RootElement;

            // BOTH values, because "we used X" without "you sent Y" does not tell the registrant it
            // has anything to change.
            Assert.Equal(
                new RepositoryIdentity(Worktree, "x").CanonicalPath,
                document.GetProperty("repositorySent").GetString());
            Assert.Equal(
                new RepositoryIdentity(Repository, "x").CanonicalPath,
                document.GetProperty("repositoryUsed").GetString());

            var reason = document.GetProperty("reason").GetString();
            Assert.False(string.IsNullOrWhiteSpace(reason));
            Assert.Contains("linked worktree", reason, StringComparison.Ordinal);

            // The product says it wrote this, so an agent or a human in that directory can tell what
            // they may maintain — provenance, not permission.
            Assert.Equal(
                RegistrationPublisher.GeneratedBy,
                document.GetProperty(RegistrationPublisher.GeneratedByField).GetString());
        }
        finally
        {
            Directory.Delete(coord, recursive: true);
        }
    }

    [Fact]
    public void TheNoticeIsDeliveredOnce()
    {
        // Queued notices are drained, not read. A notice that reappeared every tick would rewrite the
        // same file forever and read as a recurring problem rather than one already handled.
        var store = new InMemoryWatcherObservationStore();
        var host = HostWith(new StubLocator(Worktree, Repository), store);

        host.Register(new HarnessRegistration(Attrs(Worktree)));

        Assert.Single(host.DrainRegistrationNotices());
        Assert.Empty(host.DrainRegistrationNotices());
    }

    [Fact]
    public void TheContractPumpCannotSeeTheNotice()
    {
        // THE COLLISION, asserted rather than trusted. CoordinationContractLog.ReadDirectory
        // enumerates *.jsonl with no SearchOption, so a notice written as .jsonl in the root would be
        // parsed every tick and counted MALFORMED — the feature working while the ingest counters
        // filled with corruption that was not corruption. Both properties are checked because either
        // one alone would hide it today and neither is guaranteed by the other.
        var coord = NewDirectory();

        try
        {
            var published = RegistrationPublisher.Publish(
                coord, new RegistrationNotice("session-1", Worktree, Repository, "because"));

            Assert.Empty(Directory.EnumerateFiles(coord, "*.jsonl"));
            Assert.DoesNotContain(".jsonl", Path.GetFileName(published), StringComparison.Ordinal);
            Assert.NotEqual(coord, Path.GetDirectoryName(published));
        }
        finally
        {
            Directory.Delete(coord, recursive: true);
        }
    }

    private static string NewDirectory()
    {
        var path = Path.Combine(Path.GetTempPath(), "aide-reg-" + Guid.NewGuid().ToString("N")[..8]);
        Directory.CreateDirectory(path);
        return path;
    }
}
