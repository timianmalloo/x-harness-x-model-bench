using AiDe.Core.Presentation;
using AiDe.Core.Watcher;

namespace AiDe.Core.Tests.Watcher;

/// <summary>
/// LK-SESS-01..N - the Sessions surface read model (design-watcher-sessions-surface, slice 3). The
/// claims: the pane renders observed sessions honestly (Not Recorded for an unproven harness/model),
/// carries a no-colour-alone liveness badge, never strands on Loading and never renders an unreadable
/// store as a blank success (DC-011), and the query folds the store + liveness into snapshots.
/// </summary>
public sealed class WatcherSessionsPaneViewModelTests
{
    private static readonly DateTimeOffset At = DateTimeOffset.UnixEpoch;

    private sealed class FakeSessionsQuery(params WatcherSessionSnapshot[] sessions) : IWatcherSessionsQuery
    {
        public IReadOnlyList<WatcherSessionSnapshot> GetSessions() => sessions;
    }

    private sealed class ThrowingSessionsQuery : IWatcherSessionsQuery
    {
        public IReadOnlyList<WatcherSessionSnapshot> GetSessions() =>
            throw new InvalidOperationException("the observation store could not be read");
    }

    private static WatcherSessionSnapshot Snapshot(
        string id = "s1", string repo = "ai-de", string branch = "main", string agent = "agent-1",
        HarnessIdentity? harness = null, ModelIdentity? model = null,
        TrustClassification trust = TrustClassification.Verified,
        LivenessState liveness = LivenessState.Alive, int spans = 0)
    {
        var binding = WatcherFixtures.Binding(
            repoPath: $"C:/repos/{repo}", agent: agent, harness: harness, model: model, trust: trust);
        binding = binding with { Repository = new RepositoryIdentity($"C:/repos/{repo}", repo) };
        binding = binding with { Worktree = new WorktreeIdentity(binding.Repository, branch, $"C:/repos/{repo}") };
        return new WatcherSessionSnapshot(id, binding, liveness, spans);
    }

    [Fact]
    public void Load_NullQuery_IsEmpty_AndSaysWhatIsUnavailable()
    {
        var pane = new WatcherSessionsPaneViewModel(query: null);

        pane.Load();

        Assert.Equal(PaneState.Empty, pane.State);
        Assert.Empty(pane.Rows);
        Assert.Contains("not available", pane.StatusMessage, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("Loading", pane.StatusMessage, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public void Load_NoSessions_IsEmpty()
    {
        var pane = new WatcherSessionsPaneViewModel(new FakeSessionsQuery());

        pane.Load();

        Assert.Equal(PaneState.Empty, pane.State);
        Assert.Empty(pane.Rows);
        Assert.Contains("No sessions observed", pane.StatusMessage, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public void Load_OneFullSession_IsReady_WithAliveVerifiedRow()
    {
        var pane = new WatcherSessionsPaneViewModel(new FakeSessionsQuery(
            Snapshot(harness: new HarnessIdentity("Claude Code", "1.0"),
                     model: new ModelIdentity("Opus 4.8", "2026-08"), spans: 3)));

        pane.Load();

        Assert.Equal(PaneState.Ready, pane.State);
        var row = Assert.Single(pane.Rows);
        Assert.Equal("Claude Code", row.Harness);
        Assert.Equal("Opus 4.8", row.Model);
        Assert.Equal("Alive", row.Liveness.Text);
        Assert.Equal("✓", row.Liveness.Glyph);
        Assert.Equal("Verified", row.Trust);
        Assert.Equal(3, row.SpanCount);
        Assert.Contains("1 session", pane.StatusMessage, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public void Load_SessionWithNoHarnessOrModel_RendersNotRecorded_NeverBlank()
    {
        var pane = new WatcherSessionsPaneViewModel(new FakeSessionsQuery(
            Snapshot(harness: null, model: null, trust: TrustClassification.Asserted)));

        pane.Load();

        var row = Assert.Single(pane.Rows);
        Assert.Equal(WatcherSessionText.NotRecorded, row.Harness);
        Assert.Equal(WatcherSessionText.NotRecorded, row.Model);
        Assert.Equal("Asserted", row.Trust);
        Assert.Contains("Not Recorded", row.DisplayLabel, StringComparison.Ordinal);
    }

    [Fact]
    public void Load_StaleSession_BadgeIsStale_NotColourAlone()
    {
        var pane = new WatcherSessionsPaneViewModel(new FakeSessionsQuery(Snapshot(liveness: LivenessState.Stale)));

        pane.Load();

        var row = Assert.Single(pane.Rows);
        Assert.Equal("Stale", row.Liveness.Text);
        Assert.Equal("~", row.Liveness.Glyph); // glyph carries meaning, not colour
    }

    [Fact]
    public void Load_EndedSession_BadgeIsEnded()
    {
        var pane = new WatcherSessionsPaneViewModel(new FakeSessionsQuery(Snapshot(liveness: LivenessState.Ended)));

        pane.Load();

        var row = Assert.Single(pane.Rows);
        Assert.Equal("Ended", row.Liveness.Text);
        Assert.Equal("×", row.Liveness.Glyph);
    }

    [Fact]
    public void Load_ThrowingQuery_IsError_NeverLoading_NeverBlankSuccess()
    {
        var pane = new WatcherSessionsPaneViewModel(new ThrowingSessionsQuery());

        pane.Load();

        Assert.Equal(PaneState.Error, pane.State);
        Assert.Empty(pane.Rows);
        Assert.DoesNotContain("Loading", pane.StatusMessage, StringComparison.OrdinalIgnoreCase);
        Assert.Contains("unavailable", pane.StatusMessage, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public void Load_PreservesTheQueryOrder()
    {
        var pane = new WatcherSessionsPaneViewModel(new FakeSessionsQuery(
            Snapshot(id: "a", repo: "alpha"), Snapshot(id: "b", repo: "beta"), Snapshot(id: "c", repo: "gamma")));

        pane.Load();

        Assert.Collection(pane.Rows,
            r => Assert.Equal("alpha", r.Repository),
            r => Assert.Equal("beta", r.Repository),
            r => Assert.Equal("gamma", r.Repository));
    }

    [Fact]
    public void Row_AccessibleName_AnnouncesTheWholeRow()
    {
        var row = WatcherSessionRow.From(Snapshot(
            agent: "agent-9", harness: new HarnessIdentity("Copilot", "1"),
            model: new ModelIdentity("GPT-5.6", "1"), liveness: LivenessState.Alive, spans: 2));

        Assert.Contains("Agent agent-9", row.AccessibleName, StringComparison.Ordinal);
        Assert.Contains("Copilot", row.AccessibleName, StringComparison.Ordinal);
        Assert.Contains("Alive", row.AccessibleName, StringComparison.Ordinal);
        Assert.Contains("2 span", row.AccessibleName, StringComparison.Ordinal);
    }

    // --- the query fold over a real store + liveness (D1) --------------------------------------

    [Fact]
    public void Query_FoldsStoreLivenessAndSpanCount_IntoSnapshots()
    {
        var store = new InMemoryWatcherObservationStore();
        var clock = new FakeMonotonicClock();
        var registrar = new TrustedRegistrar(store, new SequentialCapabilityFactory(), clock, () => "s1");
        var host = new IngestHost(store, registrar, new FixedTimeProvider(At));
        var liveness = new LivenessProjection(store, clock, TimeSpan.FromSeconds(30));

        var session = host.Register(WatcherFixtures.HarnessRegistration(harnessName: "Claude Code", modelName: "Opus 4.8"));
        host.Heartbeat(session.SessionId, session.Capability);
        host.Enqueue(new HarnessSpanEvent(session.Capability, new HarnessSpan(
            "trace-1", "span-a", "chat.completion",
            new Dictionary<string, string?>(StringComparer.Ordinal) { [OtelAttributes.SessionId] = session.SessionId })));
        host.DrainAvailable();

        var snapshots = new WatcherSessionsQuery(store, liveness).GetSessions();

        var snapshot = Assert.Single(snapshots);
        Assert.Equal(session.SessionId, snapshot.SessionId);
        Assert.Equal(LivenessState.Alive, snapshot.Liveness);
        Assert.Equal(1, snapshot.SpanCount);
        Assert.Equal("Claude Code", snapshot.Binding.Harness!.Name);
    }
}
