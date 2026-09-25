using System.Text;
using AiDe.Core.AgentPlane;
using AiDe.Core.Tests.Watcher;
using AiDe.Core.Watcher;

namespace AiDe.Core.Tests.AgentPlane;

/// <summary>
/// <c>GovernedLaneSource</c> (renamed from <c>GovernedSessionSource</c> by Ruling 15/A3) — spec
/// §6.1/§6.2 and R2. A governed lane's episode is opened by the
/// runtime at spawn, with attributes taken verbatim from the goal block, over the same live ingest
/// path every other episode uses.
/// </summary>
/// <remarks>
/// <para><b>No new seam.</b> The episode reaches the store through
/// <see cref="IngestHost.OpenEpisode"/> / <see cref="IngestHost.DeclareEpisodeArtifacts"/> /
/// <see cref="IngestHost.CloseEpisode"/>, capability-verified through <c>ITrustedRegistrar</c>,
/// exactly as <c>InjectedContractIngest</c> does for a declaring session. An <c>IEpisodeSource</c>
/// interface was declined by ruling until a third implementer exists; a second one is not evidence
/// of a shape.</para>
///
/// <para><b>Why byte-for-byte and not "equal".</b> The goal block is what the episode is later scored
/// against. A source that trimmed, normalized, collapsed whitespace or re-encoded would score the
/// agent against a goal it did not write, and every such transformation is invisible to a
/// case-insensitive or trimming comparison. So the assertion is over UTF-8 bytes, with a goal string
/// carrying accents, an em dash and a double space — the characters that a helpful normalizer eats.</para>
///
/// <para><b>The agent cannot forge these</b> (§6.1): the capability lives in the source, and the lane
/// never sees it.</para>
/// </remarks>
public sealed class GovernedLaneSourceTests
{
    private const double At = 1_700_000_000d;

    // Deliberately awkward: accents, an em dash, an internal double space, a trailing period.
    private const string GoalText = "Déplacer PaymentAggregate — et  ses handlers — vers Payments.Domain.";
    private const string DoneWhenText = "Payments.Domain builds; its tests green;  no references from Ordering.";
    private const string NotInScopeText = "IPaymentGateway contract edits (serial spine) — épine dorsale.";

    private static GoalBlock Block() => new(
        GoalText, DoneWhenText, NotInScopeText, Tier: "T1", FanOutCap: 0, Budget: new RunBudget(250, 600_000));

    private static LaneIdentity Lane() => new(
        LaneId: "lane-0001",
        AgentName: "payments-refactorer",
        RepositoryPath: "C:/repos/app",
        RepositoryDisplay: "app",
        WorktreeBranch: "agent/claude-code-lane-000",
        WorktreePath: "C:/repos/app-agent-claude-code-lane-000",
        Harness: "claude-code",
        Model: "sonnet");

    private static (GovernedLaneSource Source, InMemoryWatcherObservationStore Store, TimeProvider Time) New()
    {
        var store = new InMemoryWatcherObservationStore();
        var time = new FixedTimeProvider(DateTimeOffset.UnixEpoch.AddSeconds(At));
        var n = 0;
        var registrar = new TrustedRegistrar(store, new SequentialCapabilityFactory(), new FakeMonotonicClock(), () => $"session-{++n}");
        return (new GovernedLaneSource(new IngestHost(store, registrar, time)), store, time);
    }

    private static void AssertSameBytes(string expected, string? actual, string what)
        => Assert.Equal(Encoding.UTF8.GetBytes(expected), Encoding.UTF8.GetBytes(actual ?? $"<{what} was null>"));

    /// <summary>The clause: the opened episode's attributes are the goal block, byte for byte.</summary>
    [Fact]
    public void TheEpisodeOpensWithAttributesByteForByteEqualToTheGoalBlock()
    {
        var (source, store, _) = New();
        var block = Block();

        var session = source.Open(Lane(), block);

        // (1) the attribute map the source emits, keyed exactly as the coordination contract keys it
        AssertSameBytes(block.Goal!, session.OpenAttributes[CoordContract.EpisodeAttributes.Goal], "goal");
        AssertSameBytes(block.DoneWhen!, session.OpenAttributes[CoordContract.EpisodeAttributes.DoneWhen], "done_when");
        AssertSameBytes(block.NotInScope!, session.OpenAttributes[CoordContract.EpisodeAttributes.NotInScope], "not_in_scope");

        // (2) and what the store durably holds, which is what scoring later reads
        var episode = store.FindEpisode(session.EpisodeId)!;
        AssertSameBytes(block.Goal!, episode.Goal.Statement, "goal");
        AssertSameBytes(block.DoneWhen!, episode.DoneWhen.Statement, "done_when");
        AssertSameBytes(block.NotInScope!, episode.NotInScope, "not_in_scope");
    }

    /// <summary>Only the three episode attributes are emitted — tier, cap and budget belong to the spawn.</summary>
    [Fact]
    public void TheOpenAttributesAreExactlyTheThreeEpisodeKeys()
        => Assert.Equal(
            new[]
            {
                CoordContract.EpisodeAttributes.DoneWhen,
                CoordContract.EpisodeAttributes.Goal,
                CoordContract.EpisodeAttributes.NotInScope,
            },
            New().Source.Open(Lane(), Block()).OpenAttributes.Keys.Order(StringComparer.Ordinal));

    /// <summary>An incomplete goal block never opens an episode — R2's "no block, no spawn", mechanized.</summary>
    [Fact]
    public void AnIncompleteGoalBlockOpensNothing()
    {
        var (source, store, _) = New();

        var error = Assert.Throws<AgentPlaneException>(
            () => source.Open(Lane(), Block() with { Budget = null }));

        Assert.Equal(AgentPlaneErrorCodes.GoalBlockIncomplete, error.Code);
        Assert.Contains(GoalBlockFields.BudgetKey, error.Message, StringComparison.Ordinal);
        Assert.Empty(store.AllEpisodes());
        Assert.Empty(store.AllSessions());
    }

    /// <summary>
    /// A session is REGISTERED, which is what makes the episode sweepable.
    /// </summary>
    /// <remarks>
    /// <c>ClosedEpisodeScoring</c> skips an episode whose session it cannot find — deliberately, so
    /// the audit-import and registered-session producers stay disjoint. An episode source that opened
    /// episodes without registering would therefore produce work that scores nowhere, silently and
    /// forever. This is the assertion that says the governed door is a door.
    /// </remarks>
    [Fact]
    public void TheRegisteredSessionMakesTheClosedEpisodeSweepable()
    {
        var (source, store, time) = New();

        var session = source.Open(Lane(), Block());
        Assert.NotNull(store.FindSession(session.SessionId));

        session.Close(EpisodeOutcome.Completed);

        Assert.Equal(1, ClosedEpisodeScoring.Run(store, time, taskClass: "refactor"));
        var scored = store.FindScoredEpisode(session.EpisodeId)!;
        Assert.Equal("refactor", scored.TaskClass);
        Assert.Equal("claude-code", scored.Harness);
        Assert.Equal("sonnet", scored.Model);
    }

    /// <summary>Declared evidence reaches the store as declared — verbatim, never verified here.</summary>
    [Fact]
    public void DeclaredArtifactsReachTheStore()
    {
        var (source, store, _) = New();
        var session = source.Open(Lane(), Block());

        Assert.Equal(2, session.DeclareArtifacts(["docs/proof/pp-0001.md", "docs/proof/pp-0002.md"]));

        Assert.Equal(
            new[] { "docs/proof/pp-0001.md", "docs/proof/pp-0002.md" },
            store.DeclaredArtifactsFor(session.EpisodeId).Select(a => a.Path).Order(StringComparer.Ordinal));
    }

    // ---- Clause 7: engine-kill teardown (spec R1, line 353) ----

    /// <summary>
    /// Killing the engine closes the episode <c>Blocked</c> and PARKS a dirty worktree.
    /// </summary>
    /// <remarks>
    /// Both halves are failure modes with teeth. An episode left open scores nowhere and looks like a
    /// lane still working; a deleted dirty tree destroys the only copy of whatever the lane had
    /// written when it died — which, for a lane that died, is the only evidence of what went wrong.
    /// </remarks>
    [Fact]
    public void AKilledEngineClosesTheEpisodeBlockedAndParksADirtyWorktree()
    {
        var (source, store, _) = New();
        var runner = new NoOpRunner();
        var provisioner = new WorktreeProvisioner(runner);
        var tree = new ProvisionedWorktree("C:/repos/app", "agent/claude-code-lane-000", "C:/repos/app-agent-claude-code-lane-000", true);
        var lane = new GovernedLane(source.Open(Lane(), Block()), provisioner, tree);

        var teardown = lane.EngineKilled(new WorktreeState(HasUncommittedChanges: true, HasUnpushedWork: true));

        Assert.Equal(EpisodeOutcome.Blocked, teardown.Outcome);
        Assert.Equal(WorktreeDispositionKind.Parked, teardown.Worktree!.Kind);
        Assert.DoesNotContain(runner.Calls, c => c.Contains("remove", StringComparison.Ordinal));

        var episode = Assert.Single(store.AllEpisodes());
        Assert.Equal(EpisodeState.Closed, episode.State);
        Assert.Equal(EpisodeOutcome.Blocked, episode.Outcome);
    }

    /// <summary>A killed engine parks even a CLEAN tree: a kill is not an abandonment anyone declared.</summary>
    [Fact]
    public void AKilledEngineParksEvenACleanWorktree()
    {
        var (source, _, _) = New();
        var provisioner = new WorktreeProvisioner(new NoOpRunner());
        var tree = new ProvisionedWorktree("C:/repos/app", "agent/claude-code-lane-000", "C:/repos/app-agent-claude-code-lane-000", true);
        var lane = new GovernedLane(source.Open(Lane(), Block()), provisioner, tree);

        var teardown = lane.EngineKilled(new WorktreeState(false, false));

        Assert.Equal(WorktreeDispositionKind.Parked, teardown.Worktree!.Kind);
    }

    /// <summary>A lane with no provisioned tree still closes its episode — the teardown is not tree-conditional.</summary>
    [Fact]
    public void AKilledEngineWithNoWorktreeStillClosesTheEpisode()
    {
        var (source, store, _) = New();
        var lane = new GovernedLane(source.Open(Lane(), Block()), new WorktreeProvisioner(new NoOpRunner()), worktree: null);

        var teardown = lane.EngineKilled(new WorktreeState(false, false));

        Assert.Equal(EpisodeOutcome.Blocked, teardown.Outcome);
        Assert.Null(teardown.Worktree);
        Assert.Equal(EpisodeOutcome.Blocked, Assert.Single(store.AllEpisodes()).Outcome);
    }

    /// <summary>A runner that succeeds at everything and records what it was asked to do.</summary>
    private sealed class NoOpRunner : IProcessRunner
    {
        public List<string> Calls { get; } = [];

        public ProcessResult Run(string fileName, IReadOnlyList<string> arguments, string workingDirectory)
        {
            Calls.Add(fileName + " " + string.Join(' ', arguments));
            return new ProcessResult(0, string.Empty, string.Empty);
        }
    }
}
