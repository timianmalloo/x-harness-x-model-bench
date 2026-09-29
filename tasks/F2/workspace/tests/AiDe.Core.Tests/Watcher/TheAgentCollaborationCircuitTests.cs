using System.Text.Json;
using AiDe.Core.Watcher;

namespace AiDe.Core.Tests.Watcher;

/// <summary>
/// The whole agent loop as ONE chain, end to end.
/// </summary>
/// <remarks>
/// <para><b>Why this exists.</b> Every link in the collaboration loop is tested at its own seam and
/// passes. Three capabilities were nonetheless found that nothing could reach —
/// <c>MessageBoardService</c>, <c>StandingComposer</c>, <c>McpToolGateway</c> — because a seam test
/// asks "does this component work" and never "can anything get here from there". A chain of correct
/// components is not a working chain, and the only thing that distinguishes them is a test that
/// walks the whole thing.</para>
///
/// <para><b>What is proven here:</b> an agent registers through the contract log, receives a
/// capability, declares an episode, closes it, <b>is scored</b>, and <b>receives a standing</b> — all
/// through the channel an agent actually has, with no shell and no UI.</para>
///
/// <para><b>Where the chain used to end.</b> A closed episode was never scored. Scoring had exactly
/// one producer, <c>WatcherHost.ImportAndScoreEpisodesFromAuditLog</c>, which reads AI-DE's own audit
/// log — and an audit-imported episode takes its <c>SessionId</c> from the log's <c>session</c>
/// field, while <see cref="TrustedRegistrar"/> mints a fresh id for a registered agent. The two
/// identifier spaces never met, so an agent that registered and declared work produced a closed
/// episode, no scorecard, and therefore no standing, forever.</para>
///
/// <para><b>Two tests here pinned that absence and were written to fail the day it closed. They
/// did.</b> <see cref="ClosedEpisodeScoring"/> now runs on the watcher tick, and they are rewritten
/// to assert the standing rather than deleted — which is what the previous version of this remark
/// instructed whoever closed the gap to do.</para>
///
/// <para><b>Replayed against the defects they claim to catch (DC-099).</b> Mutating the product and
/// running all 1,557 Core tests: dropping the already-scored guard reddens
/// <c>ScoringTheSameClosedEpisodeTwiceScoresItOnce</c> alone; dropping the closed-state guard
/// reddens <c>AnOpenEpisodeIsNotScored</c> alone; passing a null workspace reddens
/// <c>ACompletedAgentEpisodeIsScored_AndTheVerdictIsHonestlyNotScored</c> and
/// <c>AndTheStandingReachesTheAgent_SayingWhyItHasNoRank</c>; suppressing
/// <c>ScoreSegment.IncomparableReason</c> reddens the standing test alone. Each fails for the branch
/// it is about and would not catch a regression it does not cover, which is the property worth
/// having and the one that cannot be got by reasoning.</para>
///
/// <para><b>Not replayed:</b> <c>AnAgentRegistersDeclaresAndClosesWorkThroughTheContractAlone</c>,
/// which predates this work.</para>
///
/// <para><b>What the agent receives is Not Scored, and that is the honest answer.</b> A
/// contract-declared episode carries no Proof Pack, so there is no verification path to observe, and
/// the conservative defaults produce a verdict of Not Scored <i>with its reason</i>. That is not a
/// low score and must never become one: a low score is a claim about the agent, and nothing observed
/// here is evidence for one.</para>
/// </remarks>
public sealed class TheAgentCollaborationCircuitTests
{
    private const double At = 1000;
    private const string Repo = "C:/repos/app";

    private static Dictionary<string, string?> RegisterAttrs() => new(StringComparer.Ordinal)
    {
        [OtelAttributes.RepoPath] = Repo,
        [OtelAttributes.RepoDisplay] = "app",
        [OtelAttributes.WorktreePath] = Repo,
        [OtelAttributes.WorktreeBranch] = "main",
        [OtelAttributes.TerminalId] = "term-1",
        [OtelAttributes.AgentName] = "agent-ext",
        [OtelAttributes.ServiceName] = "claude-code",
    };

    private static Dictionary<string, string?> EpisodeAttrs() => new(StringComparer.Ordinal)
    {
        [CoordContract.EpisodeAttributes.Goal] = "close the collaboration loop",
        [CoordContract.EpisodeAttributes.DoneWhen] = "an agent receives a standing",
    };

    private static (InjectedContractIngest Adapter, InMemoryWatcherObservationStore Store) Circuit()
    {
        var store = new InMemoryWatcherObservationStore();
        var n = 0;
        var registrar = new TrustedRegistrar(
            store, new SequentialCapabilityFactory(), new FakeMonotonicClock(), () => $"session-{++n}");
        var host = new IngestHost(store, registrar, new FixedTimeProvider(DateTimeOffset.UnixEpoch.AddSeconds(At)));

        return (new InjectedContractIngest(host), store);
    }

    private static void CloseOneEpisode(InjectedContractIngest adapter)
    {
        adapter.Apply(new ContractRegister("ext-1", RegisterAttrs(), At, 1));
        adapter.Apply(new ContractEpisodeOpen("ext-1", EpisodeAttrs(), At + 1, 2));
        adapter.Apply(new ContractEpisodeClose(
            "ext-1",
            new Dictionary<string, string?>(StringComparer.Ordinal)
            {
                [CoordContract.EpisodeAttributes.Outcome] = "completed",
            },
            At + 2, 3));
    }

    [Fact]
    public void AnAgentRegistersDeclaresAndClosesWorkThroughTheContractAlone()
    {
        // The whole inbound half, driven the way an agent drives it: lines into the contract log.
        // No shell, no UI, no MCP — those are the paths an agent does NOT have.
        var (adapter, store) = Circuit();

        adapter.Apply(new ContractRegister("ext-1", RegisterAttrs(), At, 1));

        var session = Assert.Single(store.AllSessions());

        adapter.Apply(new ContractEpisodeOpen("ext-1", EpisodeAttrs(), At + 1, 2));

        var episode = Assert.Single(store.EpisodesForSession(session.SessionId));
        Assert.Equal(EpisodeState.Active, episode.State);

        adapter.Apply(new ContractEpisodeClose(
            "ext-1",
            new Dictionary<string, string?>(StringComparer.Ordinal)
            {
                [CoordContract.EpisodeAttributes.Outcome] = "completed",
            },
            At + 2, 3));

        var closed = Assert.Single(store.EpisodesForSession(session.SessionId));
        Assert.Equal(EpisodeState.Closed, closed.State);
    }

    [Fact]
    public void ACompletedAgentEpisodeIsScored_AndTheVerdictIsHonestlyNotScored()
    {
        // THE LINK THAT WAS MISSING. This assertion was Assert.Empty(store.AllScoredEpisodes()),
        // pinning the break; it is now the proof that the break closed.
        var (adapter, store) = Circuit();
        CloseOneEpisode(adapter);

        var newlyScored = ClosedEpisodeScoring.Run(store, TimeProvider.System);

        Assert.Equal(1, newlyScored);
        var scored = Assert.Single(store.AllScoredEpisodes());

        // Not Scored, because nothing observed amounts to evidence of outcome — never a low score,
        // which would be a claim about the agent rather than about the evidence.
        Assert.Equal(WeaveVerdict.NotScored, scored.Scorecard.Verdict);
        Assert.NotEmpty(scored.Scorecard.Headline);

        // Keyed to the REPOSITORY the session was bound to, which is what makes the score mean
        // anything: how an agent works is partly a product of that repository's directives.
        Assert.Equal(WorkspaceKey.From(Repo), scored.Segment.Workspace);

        // And not comparable, because the contract carries no task class. Scored and delivered, but
        // ranked nowhere — rather than pooled into a cohort that does not exist.
        Assert.Equal(ScoreSegment.Unclassified, scored.Segment.TaskClass);
        Assert.False(scored.Segment.IsComparable);
    }

    [Fact]
    public void ScoringTheSameClosedEpisodeTwiceScoresItOnce()
    {
        // The pass runs on every watcher tick, so idempotence is not a nicety: a second scoring would
        // replace the card, and a re-scored episode that became its own predecessor would report a
        // trend against itself.
        var (adapter, store) = Circuit();
        CloseOneEpisode(adapter);

        Assert.Equal(1, ClosedEpisodeScoring.Run(store, TimeProvider.System));
        Assert.Equal(0, ClosedEpisodeScoring.Run(store, TimeProvider.System));
        Assert.Single(store.AllScoredEpisodes());
    }

    [Fact]
    public void AnOpenEpisodeIsNotScored()
    {
        // Closing is the declaration that the work is done. Scoring an open episode would judge work
        // that is still happening.
        var (adapter, store) = Circuit();

        adapter.Apply(new ContractRegister("ext-1", RegisterAttrs(), At, 1));
        adapter.Apply(new ContractEpisodeOpen("ext-1", EpisodeAttrs(), At + 1, 2));

        Assert.Equal(0, ClosedEpisodeScoring.Run(store, TimeProvider.System));
        Assert.Empty(store.AllScoredEpisodes());
    }

    [Fact]
    public void AndTheStandingReachesTheAgent_SayingWhyItHasNoRank()
    {
        // THE LAST LINK. This asserted Assert.Null(published) — no standing, because there was no
        // score. There is a score now, so there is a standing, and the agent can read it from the
        // directory it was handed as AIDE_CONTRACT_LOG.
        var (adapter, store) = Circuit();
        CloseOneEpisode(adapter);
        ClosedEpisodeScoring.Run(store, TimeProvider.System);

        var session = Assert.Single(store.AllSessions());
        var scored = store.AllScoredEpisodes();
        var episode = Assert.Single(store.EpisodesForSession(session.SessionId));

        var directory = Path.Combine(Path.GetTempPath(), "aide-circuit-" + Guid.NewGuid().ToString("N")[..8]);
        Directory.CreateDirectory(directory);

        try
        {
            var published = StandingPublisher.Publish(directory, session.SessionId, scored, episode.EpisodeId);

            Assert.NotNull(published);
            Assert.True(File.Exists(published), "nothing was written at " + published);

            var standing = JsonDocument.Parse(File.ReadAllText(published!)).RootElement;

            Assert.Equal(episode.EpisodeId, standing.GetProperty("episodeId").GetString());
            Assert.False(standing.GetProperty("rankComparable").GetBoolean());

            // The reason travels with the absence. "No rank" alone is an empty state naming nothing,
            // and the two causes want opposite responses from the agent: an undeclared task class it
            // can fix, an unresolvable repository it cannot.
            var reason = standing.GetProperty("notComparableReason").GetString();
            Assert.False(string.IsNullOrWhiteSpace(reason));
            Assert.Contains("kind of work", reason, StringComparison.Ordinal);

            // And the product says it wrote this, so an agent or a human editing the directory can
            // tell what it may maintain — provenance, not permission.
            Assert.Equal(
                StandingPublisher.GeneratedBy,
                standing.GetProperty(StandingPublisher.GeneratedByField).GetString());
        }
        finally
        {
            Directory.Delete(directory, recursive: true);
        }
    }
}
