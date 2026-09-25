using AiDe.Core.Presentation;
using AiDe.Core.Watcher;

namespace AiDe.Core.Tests.Watcher;

/// <summary>
/// LK-DISPUTESVC-01..12 - the raise-dispute API, the per-session Disputed state, the Sessions Disputed
/// badge, and the cloud-judge scaffold (conn-7). The claims: RaiseDispute mints the id + timestamp and
/// appends the fact (requiring a reason); a session is Disputed iff any of its episodes carries a dispute
/// (DM7); the Sessions row and query surface that; and the DelegatingAdvisoryEvaluator delegates the
/// rubric to an injected model call, composing behind the ADR-0024 credential-backed-grading-egress egress guard.
/// </summary>
public sealed class DisputeServiceTests
{
    private static readonly DateTimeOffset At = DateTimeOffset.UnixEpoch;
    private static readonly TimeProvider Clock = new FixedTimeProvider(At);

    private static WorkEpisode Episode(string id, string session) => new(
        id, session, new EpisodeGeneration(1), new Goal("g"), new DoneCondition("d"), null, At, At.AddMinutes(1), EpisodeOutcome.Completed);

    // ---- DisputeService.RaiseDispute ----------------------------------------------------------------

    [Fact]
    public void RaiseDispute_AppendsTheFact_WithGeneratedIdAndTimestamp()
    {
        var store = new InMemoryWatcherObservationStore();
        var svc = new DisputeService(store, Clock, () => "d-1");

        var dispute = svc.RaiseDispute("ep-1", "op1", "the coverage claim is not evidenced");

        Assert.Equal("d-1", dispute.DisputeId);
        Assert.Equal(At, dispute.RaisedAt);
        Assert.Null(dispute.DisputedDimension);
        Assert.Single(store.DisputesForEpisode("ep-1"));
    }

    [Fact]
    public void RaiseDispute_CanTargetOneDimension()
    {
        var store = new InMemoryWatcherObservationStore();
        var svc = new DisputeService(store, Clock, () => "d-1");

        var dispute = svc.RaiseDispute("ep-1", "op1", "economy is wrong", ScoreDimension.SolutionEconomy);

        Assert.Equal(ScoreDimension.SolutionEconomy, dispute.DisputedDimension);
    }

    [Theory]
    [InlineData("")]
    [InlineData("   ")]
    public void RaiseDispute_RequiresANonBlankReason(string reason)
    {
        var svc = new DisputeService(new InMemoryWatcherObservationStore(), Clock);

        Assert.ThrowsAny<ArgumentException>(() => svc.RaiseDispute("ep-1", "op1", reason));
    }

    [Fact]
    public void RaiseDispute_TrimsTheReason()
    {
        var store = new InMemoryWatcherObservationStore();
        var svc = new DisputeService(store, Clock, () => "d-1");

        var dispute = svc.RaiseDispute("ep-1", "op1", "  padded reason  ");

        Assert.Equal("padded reason", dispute.Reason);
    }

    // ---- Per-session Disputed state -----------------------------------------------------------------

    [Fact]
    public void IsSessionDisputed_TrueWhenOneOfItsEpisodesIsDisputed()
    {
        var store = new InMemoryWatcherObservationStore();
        store.RecordEpisode(Episode("ep-1", "s1"));
        store.RecordEpisode(Episode("ep-2", "s2"));
        new DisputeService(store, Clock, () => "d-1").RaiseDispute("ep-1", "op1", "wrong");
        var projection = new DisputeProjection(store);

        Assert.True(projection.IsSessionDisputed("s1"));
        Assert.False(projection.IsSessionDisputed("s2"));
    }

    // ---- Sessions row badge + query -----------------------------------------------------------------

    [Fact]
    public void SessionRow_Disputed_ShowsTheBadge_NoColourAlone()
    {
        var binding = WatcherFixtures.Binding(repoPath: "C:/repos/ai-de", agent: "agent-1");
        var row = WatcherSessionRow.From(new WatcherSessionSnapshot("s1", binding, LivenessState.Alive, 3, Disputed: true));

        Assert.True(row.Disputed);
        Assert.Contains(WatcherSessionRow.DisputedText, row.DisplayLabel);
        Assert.Contains("disputed score", row.AccessibleName);
    }

    [Fact]
    public void SessionRow_NotDisputed_OmitsTheBadge()
    {
        var binding = WatcherFixtures.Binding(repoPath: "C:/repos/ai-de", agent: "agent-1");
        var row = WatcherSessionRow.From(new WatcherSessionSnapshot("s1", binding, LivenessState.Alive, 3));

        Assert.False(row.Disputed);
        Assert.DoesNotContain(WatcherSessionRow.DisputedText, row.DisplayLabel);
    }

    [Fact]
    public void WatcherSessionsQuery_MarksASessionDisputed_WhenOneOfItsEpisodesIs()
    {
        var store = new InMemoryWatcherObservationStore();
        var binding = WatcherFixtures.Binding(repoPath: "C:/repos/ai-de", agent: "agent-1");
        store.RecordSession(new SessionRecord("s1", new SessionGeneration(1), binding));
        store.RecordEpisode(Episode("ep-1", "s1"));
        new DisputeService(store, Clock, () => "d-1").RaiseDispute("ep-1", "op1", "contested");

        var liveness = new LivenessProjection(store, new FakeMonotonicClock(), TimeSpan.FromSeconds(30));
        var snapshot = Assert.Single(new WatcherSessionsQuery(store, liveness).GetSessions());

        Assert.True(snapshot.Disputed);
    }

    // ---- DelegatingAdvisoryEvaluator (cloud-judge scaffold) -----------------------------------------

    [Fact]
    public void DelegatingEvaluator_DelegatesTheRubric_AndClampsIt()
    {
        var evaluator = new DelegatingAdvisoryEvaluator("cloud/1", (_, _, _) => 9); // out of range

        var a = evaluator.Evaluate(ScoreDimension.EvidenceDiscipline, Episode("ep-1", "s1"), "coverage=9/10");

        Assert.Equal(4, a.Rubric0to4);          // clamped to 0..4
        Assert.Equal("cloud/1", a.EvaluatorVersion);
    }

    [Fact]
    public void DelegatingEvaluator_BehindTheEgressGuard_DoesNotJudgeUntilOptedInAndCredentialed()
    {
        var judged = false;
        var inner = new DelegatingAdvisoryEvaluator("cloud/1", (_, _, _) => { judged = true; return 4; });
        var gate = new EgressGate();
        var guard = new EgressGuardedAdvisoryEvaluator(inner, gate, "advisory/cloud", new NoCredential());

        // Blocked: the model call never happens.
        Assert.Throws<WatcherException>(() => guard.Evaluate(ScoreDimension.EvidenceDiscipline, Episode("ep-1", "s1"), "e"));
        Assert.False(judged);
    }

    [Fact]
    public void DelegatingEvaluator_BehindTheEgressGuard_JudgesOnceOptedInAndCredentialed()
    {
        var judged = false;
        var inner = new DelegatingAdvisoryEvaluator("cloud/1", (_, _, _) => { judged = true; return 3; });
        var gate = new EgressGate();
        gate.OptIn("advisory/cloud");
        var guard = new EgressGuardedAdvisoryEvaluator(inner, gate, "advisory/cloud", new PresentCredentialForDispute());

        var a = guard.Evaluate(ScoreDimension.EvidenceDiscipline, Episode("ep-1", "s1"), "e");

        Assert.True(judged);
        Assert.Equal(3, a.Rubric0to4);
    }

    private sealed class PresentCredentialForDispute : IAdvisoryCredentialSource
    {
        public bool HasCredential => true;
    }
}
