using AiDe.Core.Watcher;

namespace AiDe.Core.Tests.Watcher;

/// <summary>
/// LK-EP-01..N - the Work Episode lifecycle (design-watcher-work-episode, slice 4). The claims: an
/// episode binds one immutable goal + done-condition to one bounded interval of one authenticated
/// session (capability-verified); changing the goal starts a NEW episode (Superseded + next
/// generation); the projection binds only the spans inside the interval; and the domain mirrors the
/// AI-Forward CT19 goal-state (Goal / DoneWhen / NotInScope).
/// </summary>
public sealed class WorkEpisodeTests
{
    private static readonly DateTimeOffset At = DateTimeOffset.UnixEpoch;

    private sealed class MutableTimeProvider(DateTimeOffset start) : TimeProvider
    {
        public DateTimeOffset Now { get; set; } = start;

        public override DateTimeOffset GetUtcNow() => Now;
    }

    private static Func<string> EpisodeIds()
    {
        var n = 0;
        return () => $"ep-{++n}";
    }

    private static (WorkEpisodeService svc, InMemoryWatcherObservationStore store, RegisteredSession session, MutableTimeProvider time)
        NewService()
    {
        var store = new InMemoryWatcherObservationStore();
        var registrar = new TrustedRegistrar(store, new SequentialCapabilityFactory(), new FakeMonotonicClock(), () => "s1");
        var session = registrar.Register(WatcherFixtures.Binding(
            harness: new HarnessIdentity("Claude Code", "1.0"), model: new ModelIdentity("Opus 4.8", "1")));
        var time = new MutableTimeProvider(At);
        var svc = new WorkEpisodeService(store, registrar, time, EpisodeIds());
        return (svc, store, session, time);
    }

    private static Goal G(string s = "wire the OTLP receiver") => new(s);
    private static DoneCondition D(string s = "the receiver ingests a span and the suite is green") => new(s);

    // --- Open ---------------------------------------------------------------------------------

    [Fact]
    public void Open_BindsGoalDoneAndInterval_AsGeneration1_Active()
    {
        var (svc, store, session, _) = NewService();

        var episode = svc.Open(session.SessionId, session.Capability, G(), D(), notInScope: "the grader");

        Assert.Equal(1, episode.Generation.Value);
        Assert.Equal(EpisodeState.Active, episode.State);
        Assert.Equal("wire the OTLP receiver", episode.Goal.Statement);
        Assert.Equal("the receiver ingests a span and the suite is green", episode.DoneWhen.Statement);
        Assert.Equal("the grader", episode.NotInScope);
        Assert.Null(episode.Outcome);
        Assert.NotNull(store.FindEpisode(episode.EpisodeId));
    }

    [Fact]
    public void Open_BlankNotInScope_BecomesNull()
    {
        var (svc, _, session, _) = NewService();

        var episode = svc.Open(session.SessionId, session.Capability, G(), D(), notInScope: "   ");

        Assert.Null(episode.NotInScope);
    }

    [Theory]
    [InlineData("", "done")]
    [InlineData("goal", "")]
    [InlineData("  ", "done")]
    public void Open_EmptyGoalOrDone_ThrowsInvalidBinding(string goal, string done)
    {
        var (svc, _, session, _) = NewService();

        var ex = Assert.Throws<WatcherException>(() =>
            svc.Open(session.SessionId, session.Capability, new Goal(goal), new DoneCondition(done)));
        Assert.Equal(WatcherErrorCodes.InvalidBinding, ex.Code);
    }

    [Fact]
    public void Open_ForgedCapability_ThrowsForgery()
    {
        var (svc, _, session, _) = NewService();

        var ex = Assert.Throws<WatcherException>(() =>
            svc.Open(session.SessionId, WatcherFixtures.ForgedCapability(), G(), D()));
        Assert.Equal(WatcherErrorCodes.ForgeryRejected, ex.Code);
    }

    // --- Reframe (changing the goal starts a new episode) -------------------------------------

    [Fact]
    public void Reframe_SupersedesTheOldEpisode_AndOpensTheNextGenerationWithTheNewGoal()
    {
        var (svc, store, session, time) = NewService();
        var first = svc.Open(session.SessionId, session.Capability, G("plan A"), D("A is done"));

        time.Now = At.AddMinutes(5);
        var second = svc.Reframe(first.EpisodeId, session.Capability, G("plan B"), D("B is done"));

        var oldRow = store.FindEpisode(first.EpisodeId)!;
        Assert.Equal(EpisodeState.Closed, oldRow.State);
        Assert.Equal(EpisodeOutcome.Superseded, oldRow.Outcome);
        Assert.Equal("plan A", oldRow.Goal.Statement); // the old goal is immutable, not rewritten

        Assert.NotEqual(first.EpisodeId, second.EpisodeId);
        Assert.Equal(2, second.Generation.Value);
        Assert.Equal("plan B", second.Goal.Statement);
        Assert.Equal(EpisodeState.Active, second.State);
    }

    [Fact]
    public void Reframe_ForgedCapability_ThrowsForgery_AndLeavesTheEpisodeUntouched()
    {
        var (svc, store, session, _) = NewService();
        var first = svc.Open(session.SessionId, session.Capability, G(), D());

        var ex = Assert.Throws<WatcherException>(() =>
            svc.Reframe(first.EpisodeId, WatcherFixtures.ForgedCapability(), G("hijacked"), D("x")));

        Assert.Equal(WatcherErrorCodes.ForgeryRejected, ex.Code);
        Assert.Equal(EpisodeState.Active, store.FindEpisode(first.EpisodeId)!.State); // untouched
    }

    [Fact]
    public void Reframe_UnknownEpisode_Throws()
    {
        var (svc, _, session, _) = NewService();

        var ex = Assert.Throws<WatcherException>(() =>
            svc.Reframe("nope", session.Capability, G(), D()));
        Assert.Equal(WatcherErrorCodes.InvalidBinding, ex.Code);
    }

    [Fact]
    public void Reframe_AlreadyClosedEpisode_Throws()
    {
        var (svc, _, session, _) = NewService();
        var first = svc.Open(session.SessionId, session.Capability, G(), D());
        svc.Close(first.EpisodeId, session.Capability, EpisodeOutcome.Completed);

        var ex = Assert.Throws<WatcherException>(() =>
            svc.Reframe(first.EpisodeId, session.Capability, G("late"), D("x")));
        Assert.Equal(WatcherErrorCodes.InvalidBinding, ex.Code);
    }

    // --- Close --------------------------------------------------------------------------------

    [Fact]
    public void Close_RecordsOutcomeAndClosesTheInterval()
    {
        var (svc, store, session, time) = NewService();
        var episode = svc.Open(session.SessionId, session.Capability, G(), D());

        time.Now = At.AddMinutes(3);
        var closed = svc.Close(episode.EpisodeId, session.Capability, EpisodeOutcome.Completed);

        Assert.Equal(EpisodeState.Closed, closed.State);
        Assert.Equal(EpisodeOutcome.Completed, closed.Outcome);
        Assert.Equal(At.AddMinutes(3), closed.ClosedAt);
        Assert.Equal(EpisodeOutcome.Completed, store.FindEpisode(episode.EpisodeId)!.Outcome);
    }

    [Fact]
    public void Close_AlreadyClosed_Throws()
    {
        var (svc, _, session, _) = NewService();
        var episode = svc.Open(session.SessionId, session.Capability, G(), D());
        svc.Close(episode.EpisodeId, session.Capability, EpisodeOutcome.Completed);

        var ex = Assert.Throws<WatcherException>(() =>
            svc.Close(episode.EpisodeId, session.Capability, EpisodeOutcome.Abandoned));
        Assert.Equal(WatcherErrorCodes.InvalidBinding, ex.Code);
    }

    [Fact]
    public void Close_ForgedCapability_ThrowsForgery()
    {
        var (svc, _, session, _) = NewService();
        var episode = svc.Open(session.SessionId, session.Capability, G(), D());

        var ex = Assert.Throws<WatcherException>(() =>
            svc.Close(episode.EpisodeId, WatcherFixtures.ForgedCapability(), EpisodeOutcome.Completed));
        Assert.Equal(WatcherErrorCodes.ForgeryRejected, ex.Code);
    }

    [Fact]
    public void TwoSequentialEpisodes_HaveIncrementingGenerations()
    {
        var (svc, _, session, _) = NewService();
        var first = svc.Open(session.SessionId, session.Capability, G("A"), D("a"));
        svc.Close(first.EpisodeId, session.Capability, EpisodeOutcome.Completed);
        var second = svc.Open(session.SessionId, session.Capability, G("B"), D("b"));

        Assert.Equal(1, first.Generation.Value);
        Assert.Equal(2, second.Generation.Value);
    }

    // --- Projection: interval-bound observable activity ---------------------------------------

    private static ObservedSpan SpanAt(string sessionId, string source, DateTimeOffset recordedAt) =>
        new(sessionId, "trace-1", source, "chat.completion", recordedAt);

    [Fact]
    public void ObservedSpanCount_BindsOnlySpansInsideTheInterval_EndpointsInclusive()
    {
        var (svc, store, session, time) = NewService();
        var episode = svc.Open(session.SessionId, session.Capability, G(), D()); // opened at At
        time.Now = At.AddMinutes(10);
        var closed = svc.Close(episode.EpisodeId, session.Capability, EpisodeOutcome.Completed); // [At, At+10m]

        store.TryAppendSpan(SpanAt(session.SessionId, "before", At.AddMinutes(-1))); // outside (before)
        store.TryAppendSpan(SpanAt(session.SessionId, "at-open", At));               // inclusive endpoint
        store.TryAppendSpan(SpanAt(session.SessionId, "inside", At.AddMinutes(5)));  // inside
        store.TryAppendSpan(SpanAt(session.SessionId, "at-close", At.AddMinutes(10))); // inclusive endpoint
        store.TryAppendSpan(SpanAt(session.SessionId, "after", At.AddMinutes(11)));  // outside (after)

        var projection = new EpisodeProjection(store, time);
        Assert.Equal(3, projection.ObservedSpanCount(closed)); // at-open, inside, at-close
    }

    [Fact]
    public void ObservedSpanCount_OpenEpisode_CountsUpToNow()
    {
        var (svc, store, session, time) = NewService();
        var episode = svc.Open(session.SessionId, session.Capability, G(), D()); // active, opened at At

        store.TryAppendSpan(SpanAt(session.SessionId, "s1", At.AddMinutes(1)));
        store.TryAppendSpan(SpanAt(session.SessionId, "s2", At.AddMinutes(2)));
        store.TryAppendSpan(SpanAt(session.SessionId, "future", At.AddMinutes(30))); // after 'now'

        time.Now = At.AddMinutes(5); // an open episode's interval is [OpenedAt, now]
        var projection = new EpisodeProjection(store, time);

        Assert.Equal(2, projection.ObservedSpanCount(episode)); // s1, s2 - not the future one
    }

    [Fact]
    public void ForSession_ReturnsEpisodesInGenerationOrder()
    {
        var (svc, store, session, time) = NewService();
        var first = svc.Open(session.SessionId, session.Capability, G("A"), D("a"));
        time.Now = At.AddMinutes(1);
        svc.Reframe(first.EpisodeId, session.Capability, G("B"), D("b"));

        var episodes = new EpisodeProjection(store, time).ForSession(session.SessionId);

        Assert.Equal(2, episodes.Count);
        Assert.Equal(1, episodes[0].Generation.Value);
        Assert.Equal(2, episodes[1].Generation.Value);
    }

    // --- D4: SQLite persistence ---------------------------------------------------------------

    private sealed class TempDbFile : IDisposable
    {
        public string Path { get; } = System.IO.Path.Combine(
            System.IO.Path.GetTempPath(), $"aide-episode-{Guid.NewGuid():N}.db");

        public void Dispose()
        {
            foreach (var f in new[] { Path, Path + "-wal", Path + "-shm" })
            {
                try { File.Delete(f); } catch (IOException) { }
            }
        }
    }

    [Fact]
    public void Sqlite_EpisodePersistsAcrossReopen_WithImmutableGoalAndOutcome()
    {
        using var db = new TempDbFile();
        string episodeId;
        {
            using var store = SqliteWatcherObservationStore.Open(db.Path);
            var registrar = new TrustedRegistrar(store, new SequentialCapabilityFactory(), new FakeMonotonicClock(), () => "s1");
            var session = registrar.Register(WatcherFixtures.Binding());
            var svc = new WorkEpisodeService(store, registrar, new MutableTimeProvider(At), EpisodeIds());
            var episode = svc.Open(session.SessionId, session.Capability, G("persist me"), D("done"), notInScope: "later");
            svc.Close(episode.EpisodeId, session.Capability, EpisodeOutcome.Completed);
            episodeId = episode.EpisodeId;
        }

        using var reopened = SqliteWatcherObservationStore.Open(db.Path);
        var loaded = reopened.FindEpisode(episodeId)!;
        Assert.Equal("persist me", loaded.Goal.Statement);
        Assert.Equal("done", loaded.DoneWhen.Statement);
        Assert.Equal("later", loaded.NotInScope);
        Assert.Equal(EpisodeState.Closed, loaded.State);
        Assert.Equal(EpisodeOutcome.Completed, loaded.Outcome);
    }

    [Fact]
    public void Sqlite_SpanCountInInterval_OverRealRecordedAt()
    {
        using var db = new TempDbFile();
        using var store = SqliteWatcherObservationStore.Open(db.Path);

        store.TryAppendSpan(SpanAt("s1", "before", At.AddMinutes(-1)));
        store.TryAppendSpan(SpanAt("s1", "inside", At.AddMinutes(5)));
        store.TryAppendSpan(SpanAt("s1", "after", At.AddMinutes(20)));

        Assert.Equal(1, store.SpanCountInInterval("s1", At, At.AddMinutes(10)));
    }

    // --- E11: composition through the real registrar + store ----------------------------------

    [Fact]
    public void Composition_RegisterOpenIngestClose_ProjectionReportsClosedAndBoundSpanCount()
    {
        var store = new InMemoryWatcherObservationStore();
        var registrar = new TrustedRegistrar(store, new SequentialCapabilityFactory(), new FakeMonotonicClock(), () => "s1");
        var time = new MutableTimeProvider(At);
        var svc = new WorkEpisodeService(store, registrar, time, EpisodeIds());
        var session = registrar.Register(WatcherFixtures.Binding());

        var episode = svc.Open(session.SessionId, session.Capability, G(), D());
        store.TryAppendSpan(SpanAt(session.SessionId, "in-1", At.AddMinutes(1)));
        store.TryAppendSpan(SpanAt(session.SessionId, "in-2", At.AddMinutes(2)));
        time.Now = At.AddMinutes(5);
        var closed = svc.Close(episode.EpisodeId, session.Capability, EpisodeOutcome.Completed);

        var projection = new EpisodeProjection(store, time);
        Assert.Equal(EpisodeState.Closed, closed.State);
        Assert.Equal(2, projection.ObservedSpanCount(closed));
        Assert.Equal(EpisodeOutcome.Completed, projection.ForSession(session.SessionId)[0].Outcome);
    }
}
