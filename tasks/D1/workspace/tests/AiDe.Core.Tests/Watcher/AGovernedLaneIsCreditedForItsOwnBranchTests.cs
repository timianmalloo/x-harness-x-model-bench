using System.Diagnostics;
using AiDe.Core.AgentPlane;
using AiDe.Core.Watcher;

namespace AiDe.Core.Tests.Watcher;

/// <summary>
/// DC-115: a governed lane running in a LINKED WORKTREE is credited for the Proof Pack it committed
/// on its own branch.
/// </summary>
/// <remarks>
/// <para><b>The false measurement this closes.</b> <c>EvidenceFor</c> verified a declared path
/// against <c>SessionBinding.Repository.CanonicalPath</c> — an identity, normalised so that every
/// worktree of one repository groups into one cohort. Handing that value to <c>File.Exists</c> reads
/// the <i>parent checkout's working tree</i>, which is on another branch and does not contain the
/// lane's evidence. Every layer answered correctly and the composed statement — <c>Not Scored — no
/// minimum verification path</c> — was false: the path existed, was committed, and was named.</para>
///
/// <para><b>Why real git and not a fabricated pointer file.</b> The claim under test is a fact about
/// what git puts on disk: a linked worktree has its own working tree, checked out on its own branch,
/// with a <c>.git</c> FILE pointing back at the repository. A stand-in would test this test's
/// author's belief about git — the failure mode DC-115 itself is an instance of.</para>
///
/// <para><b>Both routes to the defect are covered</b>, because they are different and the register
/// only measured one. A lane provisioned by spec §6.4 registers <c>repo.path</c> as the PARENT
/// (<c>LaneIdentity.RepositoryPath</c> says so in its own doc comment), so
/// <c>RepositoryCorrection</c> never fires and the defect arrives with no correction involved. An
/// agent that registers its worktree as its repository is corrected to the parent and lands in the
/// same place. Fixing only the corrected route would have left the shape the product actually
/// provisions still broken.</para>
/// </remarks>
public sealed class AGovernedLaneIsCreditedForItsOwnBranchTests : IDisposable
{
    private const double At = 1_700_000_000d;
    private const string ProofPack = "docs/proof/lane.md";

    private readonly string _repository = NewDirectory();
    private readonly string _lane;

    public AGovernedLaneIsCreditedForItsOwnBranchTests()
    {
        _lane = _repository + "-lane";

        Git(_repository, "init", "-q", "-b", "main");
        Git(_repository, "config", "user.email", "test@example.invalid");
        Git(_repository, "config", "user.name", "test");
        File.WriteAllText(Path.Combine(_repository, "a.txt"), "a");
        Git(_repository, "add", "-A");
        Git(_repository, "commit", "-q", "-m", "init");
        Git(_repository, "worktree", "add", "-q", "-b", "lane", _lane);

        // The evidence, committed on the lane's own branch — the ordering the Proof Pack convention
        // requires, and the ordering that makes the parent checkout's tree not contain it.
        var pack = Path.Combine(_lane, "docs", "proof", "lane.md");
        Directory.CreateDirectory(Path.GetDirectoryName(pack)!);
        File.WriteAllText(pack, "proof");
        Git(_lane, "add", "-A");
        Git(_lane, "commit", "-q", "-m", "proof");
    }

    public void Dispose()
    {
        Delete(_lane);
        Delete(_repository);
    }

    /// <summary>
    /// The shape spec §6.4 provisions: repository = the parent checkout, worktree = the lane's tree.
    /// </summary>
    [Fact]
    public void ALaneProvisionedByTheSpecIsCreditedForEvidenceOnItsBranch()
    {
        GivenTheEvidenceIsOnlyOnTheLanesBranch();

        var (source, store, time) = Circuit();
        var session = source.Open(Lane(repositoryPath: _repository, worktreePath: _lane), Block());

        session.DeclareArtifacts([ProofPack]);
        session.Close(EpisodeOutcome.Completed);

        Assert.Equal(1, ClosedEpisodeScoring.Run(store, time, taskClass: "refactor"));
        AssertCredited(store, session.EpisodeId);
    }

    /// <summary>
    /// DC-115's measured shape verbatim: the lane registers its WORKTREE as its repository,
    /// <c>RepositoryCorrection</c> rebinds it to the parent, and the evidence must still count.
    /// </summary>
    [Fact]
    public void ACorrectedWorktreeRegistrationIsCreditedForEvidenceOnItsBranch()
    {
        GivenTheEvidenceIsOnlyOnTheLanesBranch();

        var (source, store, time) = Circuit();
        var session = source.Open(Lane(repositoryPath: _lane, worktreePath: _lane), Block());

        // The correction fired — otherwise this test is the one above under another name.
        Assert.Equal(
            new RepositoryIdentity(_repository, "x").CanonicalPath,
            store.FindSession(session.SessionId)!.Binding.Repository.CanonicalPath);

        session.DeclareArtifacts([ProofPack]);
        session.Close(EpisodeOutcome.Completed);

        Assert.Equal(1, ClosedEpisodeScoring.Run(store, time, taskClass: "refactor"));
        AssertCredited(store, session.EpisodeId);
    }

    /// <summary>
    /// The containment boundary, unchanged: a real Proof Pack in a NEIGHBOURING directory is not
    /// this session's evidence, however it is spelled.
    /// </summary>
    [Fact]
    public void EvidenceOutsideBothCheckoutsIsStillRefused()
    {
        var outside = NewDirectory();

        try
        {
            var pack = Path.Combine(outside, "docs", "proof", "lane.md");
            Directory.CreateDirectory(Path.GetDirectoryName(pack)!);
            File.WriteAllText(pack, "someone else's evidence");

            var (source, store, time) = Circuit();
            var session = source.Open(Lane(repositoryPath: _repository, worktreePath: _lane), Block());

            session.DeclareArtifacts([pack]);
            session.Close(EpisodeOutcome.Completed);

            ClosedEpisodeScoring.Run(store, time, taskClass: "refactor");

            Assert.Equal(WeaveVerdict.NotScored, store.FindScoredEpisode(session.EpisodeId)!.Scorecard.Verdict);
        }
        finally
        {
            Delete(outside);
        }
    }

    /// <summary>
    /// Widening the search is not an escape hatch: a CLAIMED worktree that is not a checkout of the
    /// bound repository is never read, even when the declared path resolves to a real file inside it.
    /// </summary>
    /// <remarks>
    /// <c>worktree.path</c> is composed by the registrant, like every other registration attribute.
    /// Admitting it on the claim alone would let a session keep an honest <c>repo.path</c> — so its
    /// board partition and leaderboard cohort look right — while pointing evidence verification at
    /// any directory on the machine. The claim is checked against the filesystem, by the same
    /// <c>.git</c>-pointer read <c>RepositoryCorrection</c> already uses, so the second checkout is
    /// OBSERVED to belong to the repository rather than asserted to.
    /// </remarks>
    [Fact]
    public void AClaimedWorktreeThatIsNotACheckoutOfThisRepositoryIsNeverSearched()
    {
        var impostor = NewDirectory();

        try
        {
            var pack = Path.Combine(impostor, "docs", "proof", "lane.md");
            Directory.CreateDirectory(Path.GetDirectoryName(pack)!);
            File.WriteAllText(pack, "not this repository's evidence");

            var (source, store, time) = Circuit();

            // An honest repository, and a worktree claim pointing somewhere else entirely.
            var session = source.Open(Lane(repositoryPath: _repository, worktreePath: impostor), Block());

            session.DeclareArtifacts([ProofPack]);
            session.Close(EpisodeOutcome.Completed);

            ClosedEpisodeScoring.Run(store, time, taskClass: "refactor");

            Assert.Equal(WeaveVerdict.NotScored, store.FindScoredEpisode(session.EpisodeId)!.Scorecard.Verdict);
        }
        finally
        {
            Delete(impostor);
        }
    }

    /// <summary>
    /// The premise of every assertion above, asserted rather than assumed: the evidence is in the
    /// lane's tree and NOT in the parent checkout's.
    /// </summary>
    private void GivenTheEvidenceIsOnlyOnTheLanesBranch()
    {
        Assert.True(
            File.Exists(Path.Combine(_lane, "docs", "proof", "lane.md")),
            "the lane's own tree does not hold the Proof Pack; this test would prove nothing");

        Assert.False(
            File.Exists(Path.Combine(_repository, "docs", "proof", "lane.md")),
            "the parent checkout holds the Proof Pack, so the defect cannot be reproduced here");

        Assert.True(
            File.Exists(Path.Combine(_lane, ".git")),
            "git did not write a .git pointer FILE in the lane's tree");
    }

    private static void AssertCredited(InMemoryWatcherObservationStore store, string episodeId)
    {
        var scored = store.FindScoredEpisode(episodeId)!;

        Assert.False(
            scored.Scorecard.Verdict is WeaveVerdict.NotScored,
            $"a committed Proof Pack on the lane's own branch was not credited: \"{scored.Scorecard.Headline}\"");
    }

    private static GoalBlock Block() => new(
        "Give DC-115 a control.",
        "A lane in a linked worktree is credited for evidence on its own branch.",
        "Scoring weights.",
        Tier: "T2",
        FanOutCap: 0,
        Budget: new RunBudget(100, 600_000));

    private static LaneIdentity Lane(string repositoryPath, string worktreePath) => new(
        LaneId: "lane-dc115",
        AgentName: "conductor-lane",
        RepositoryPath: repositoryPath,
        RepositoryDisplay: "app",
        WorktreeBranch: "lane",
        WorktreePath: worktreePath,
        Harness: "claude-code",
        Model: "opus");

    private static (GovernedLaneSource Source, InMemoryWatcherObservationStore Store, TimeProvider Time) Circuit()
    {
        var store = new InMemoryWatcherObservationStore();
        var time = new FixedTimeProvider(DateTimeOffset.UnixEpoch.AddSeconds(At));
        var n = 0;
        var registrar = new TrustedRegistrar(
            store, new SequentialCapabilityFactory(), new FakeMonotonicClock(), () => $"session-{++n}");

        // The REAL locator: the correction and the evidence search must agree with git, not with a
        // double that agrees with them.
        return (new GovernedLaneSource(new IngestHost(store, registrar, time)), store, time);
    }

    private static string NewDirectory()
    {
        var path = Path.Combine(Path.GetTempPath(), "aide-dc115-" + Guid.NewGuid().ToString("N")[..8]);
        Directory.CreateDirectory(path);
        return path;
    }

    private static void Delete(string path)
    {
        try
        {
            if (!Directory.Exists(path))
            {
                return;
            }

            // git marks objects read-only; a plain recursive delete refuses on Windows.
            foreach (var file in Directory.EnumerateFiles(path, "*", SearchOption.AllDirectories))
            {
                File.SetAttributes(file, FileAttributes.Normal);
            }

            Directory.Delete(path, recursive: true);
        }
        catch (IOException)
        {
            // A leaked temp directory is not worth failing a passing assertion over.
        }
        catch (UnauthorizedAccessException)
        {
        }
    }

    private static void Git(string workingDirectory, params string[] arguments)
    {
        var info = new ProcessStartInfo("git")
        {
            WorkingDirectory = workingDirectory,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
        };

        foreach (var argument in arguments)
        {
            info.ArgumentList.Add(argument);
        }

        using var process = Process.Start(info)
            ?? throw new InvalidOperationException("git could not be started; this test needs a real repository.");

        process.WaitForExit(30_000);

        if (process.ExitCode != 0)
        {
            throw new InvalidOperationException(
                $"git {string.Join(' ', arguments)} failed ({process.ExitCode}): {process.StandardError.ReadToEnd()}");
        }
    }
}
