using AiDe.Core.AgentPlane;
using AiDe.Core.Tests.Watcher;
using AiDe.Core.Watcher;

namespace AiDe.Core.Tests.AgentPlane;

/// <summary>
/// Spec R2's third bullet (line 362) and §5.3 Stage 0: a T0-tier run reaches dispatch with
/// <b>zero council lanes and zero plan artifacts</b>.
/// </summary>
/// <remarks>
/// <para><b>Triage decides on what the block declares, and only that.</b> §5.3 phrases the skip as
/// "a T0/T1 run (no fan-out, no loop, no gate)". The goal block (§14.3) carries six fields and none
/// of them is a loop or a gate — read from <see cref="GoalBlockFields.All"/>, not assumed — so the
/// two inputs that exist are the <b>tier</b> and the <b>fan-out cap</b>. A triage that guessed at a
/// loop would be inventing a value; the day the block gains a field for one, <see cref="RunTriage"/>
/// is the rule that must change.</para>
///
/// <para><b>Why the counts are measured and not implied.</b> "Zero council lanes" is easy to satisfy
/// vacuously in a phase with no conductor. So the run is actually dispatched — authorized, worktree
/// identity and all — and the counts are read from the <b>store</b>: how many sessions were
/// registered, and how many artifacts were declared. A conductor that later spawned a reviewer lane
/// on the skip path would register a second session and this goes red.</para>
/// </remarks>
public sealed class ATierZeroRunSkipsPlanAndCouncilTests
{
    private static GoalBlock Block(string tier, int fanOutCap = 0) => new(
        "Rename PaymentId to PaymentIdentifier across Payments.Domain",
        "the solution builds and the Payments tests are green",
        "any change to the wire contract",
        tier,
        fanOutCap,
        new RunBudget(40, 60_000));

    private static LaneIdentity Lane() => new(
        LaneId: "lane-t0",
        AgentName: "renamer",
        RepositoryPath: "C:/repos/app",
        RepositoryDisplay: "app",
        WorktreeBranch: "agent/claude-code-lane-t0",
        WorktreePath: "C:/repos/app-agent-claude-code-lane-t0",
        Harness: "claude-code",
        Model: "sonnet");

    private static ProviderRegistry Registry()
        => new([new ProviderRow("anthropic", ProviderAuth.Subscription, [new ProviderAccount("max-personal", AccountHealth.Ready)])]);

    /// <summary>THE CLAUSE: a T0 run dispatches, and the store shows one lane and no plan artifact.</summary>
    [Fact]
    public void ATierZeroRunReachesDispatchWithNoCouncilLaneAndNoPlanArtifact()
    {
        var block = Block("T0");

        var triage = RunTriage.For(block);
        Assert.True(triage.SkipsPlanAndCouncil, triage.Reason);
        Assert.DoesNotContain(RunStage.Plan, triage.Stages);
        Assert.DoesNotContain(RunStage.Council, triage.Stages);
        Assert.Contains(RunStage.Dispatch, triage.Stages);

        // …and it really dispatches: authorized on the real spawn path, opened on the real ingest path.
        var spawn = SpawnContract.Authorize(
            new SpawnRequest(block, "claude-code", "sonnet", "max-personal", new ObservedAuthStatus("account", "max", "Claude Max")),
            Registry());
        Assert.NotNull(spawn.Goal);
        Assert.Equal("T0", spawn.Goal.Tier);

        var store = new InMemoryWatcherObservationStore();
        var registrar = new TrustedRegistrar(
            store, new SequentialCapabilityFactory(), new FakeMonotonicClock(), () => "session-1");
        var session = new GovernedLaneSource(new IngestHost(store, registrar, TimeProvider.System))
            .Open(Lane(), spawn.Goal);

        // Zero council lanes: the work lane is the only session anything registered.
        Assert.Single(store.AllSessions());

        // Zero plan artifacts: nothing was declared, by this lane or any other.
        Assert.Empty(store.DeclaredArtifactsFor(session.EpisodeId));
        Assert.Single(store.AllEpisodes());
    }

    /// <summary>
    /// The negative control: a T2 run does <b>not</b> skip.
    /// </summary>
    /// <remarks>
    /// Without it, "always skip" passes the clause above while removing the gate entirely — the same
    /// failure shape as a lease that seams on every edit.
    /// </remarks>
    [Fact]
    public void ATierTwoRunDoesNotSkipPlanAndCouncil()
    {
        var triage = RunTriage.For(Block("T2"));

        Assert.False(triage.SkipsPlanAndCouncil);
        Assert.Contains(RunStage.Plan, triage.Stages);
        Assert.Contains(RunStage.Council, triage.Stages);
        Assert.Contains(RunStage.Dispatch, triage.Stages);
    }

    /// <summary>A T0 block that declares fan-out is not a Stage-0 skip either — §5.3 says "no fan-out".</summary>
    [Fact]
    public void ATierZeroRunThatFansOutDoesNotSkip()
    {
        var triage = RunTriage.For(Block("T0", fanOutCap: 2));

        Assert.False(triage.SkipsPlanAndCouncil);
        Assert.Contains("fan", triage.Reason, StringComparison.OrdinalIgnoreCase);
    }
}
