using AiDe.Core.Watcher;

namespace AiDe.Core.Tests.Watcher;

/// <summary>
/// LK-SCORE-PERSIST-01..09 - persistence of a scored episode as a materialized derived cache (DM7)
/// behind <see cref="IWatcherObservationStore"/>. Proves the same contract on both the in-memory and
/// the real SQLite store (D4), that a persisted card equals the value the scorer produced (DM7(c):
/// persisted == in-memory == derived), that a recompute upserts without leaving stale child rows, that
/// null Coverage round-trips as null (not zero), and that <c>AllScoredEpisodes()</c> feeds the
/// <see cref="LeaderboardComposer"/> (the E11 compute-reader path).
/// </summary>
public sealed class ScorePersistenceTests
{
    private static readonly DateTimeOffset At = DateTimeOffset.UnixEpoch;

    private static string NewDbPath()
    {
        var dir = Path.Combine(Path.GetTempPath(), "aide-tests", "watcher-score", Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(dir);
        return Path.Combine(dir, "watcher.db");
    }

    // A real six-dimension card straight from the scorer - so the persistence test also pins DM7(c).
    private static (ScoredEpisode Scored, Scorecard Derived) Subject(
        string id = "ep-subject", string harness = "Claude Code", string model = "Opus 4.8", string op = "op1")
    {
        var episode = new WorkEpisode(id, "s1", new EpisodeGeneration(1),
            new Goal("do X"), new DoneCondition("X done"), null, At, At.AddMinutes(5), EpisodeOutcome.Completed);
        var signals = new DeterministicEpisodeSignals(true, true, true, false,
            new HashSet<FloorDomain>(), 0, false, 3, 3, 2, 2, true, 10, 9);
        var derived = new WeaveScorer().Score(episode, signals, new FixedTimeProvider(At));
        return (new ScoredEpisode(id, harness, model, op, new ScoreSegment(TestWorkspaces.Repo, "refactor", "weave/1"), derived), derived);
    }

    private static void AssertSameCard(ScoredEpisode expected, ScoredEpisode actual)
    {
        Assert.Equal(expected.EpisodeId, actual.EpisodeId);
        Assert.Equal(expected.Harness, actual.Harness);
        Assert.Equal(expected.Model, actual.Model);
        Assert.Equal(expected.OperatorId, actual.OperatorId);
        Assert.Equal(expected.TaskClass, actual.TaskClass);
        Assert.Equal(expected.SchemaVersion, actual.SchemaVersion);
        Assert.Equal(expected.Scorecard.Verdict, actual.Scorecard.Verdict);
        Assert.Equal(expected.Scorecard.Headline, actual.Scorecard.Headline);
        Assert.Equal(expected.Scorecard.EvaluatedAt, actual.Scorecard.EvaluatedAt);
        Assert.Equal(expected.Scorecard.Coverage, actual.Scorecard.Coverage); // EvidenceCoverage is a value record
        Assert.Equal(expected.Weave, actual.Weave, 6);
        Assert.Equal(
            expected.Scorecard.TrippedFloors.OrderBy(f => f),
            actual.Scorecard.TrippedFloors.OrderBy(f => f));
        var e = expected.Scorecard.Assessments.OrderBy(a => a.Dimension).ToList();
        var a = actual.Scorecard.Assessments.OrderBy(x => x.Dimension).ToList();
        Assert.Equal(e.Count, a.Count);
        for (var i = 0; i < e.Count; i++)
        {
            Assert.Equal(e[i].Dimension, a[i].Dimension);
            Assert.Equal(e[i].Weight, a[i].Weight);
            Assert.Equal(e[i].Rubric0to4, a[i].Rubric0to4);
            Assert.Equal(e[i].EarnedPoints, a[i].EarnedPoints);
            Assert.Equal(e[i].Posture, a[i].Posture);
            Assert.Equal(e[i].Rationale, a[i].Rationale);
        }
    }

    [Fact]
    public void InMemory_RecordThenFind_ReturnsEqualCard()
    {
        var store = new InMemoryWatcherObservationStore();
        var (scored, _) = Subject();

        store.RecordScorecard(scored);

        AssertSameCard(scored, store.FindScoredEpisode("ep-subject")!);
    }

    [Fact]
    public void Sqlite_RecordThenFind_ReturnsEqualCard()
    {
        using var store = SqliteWatcherObservationStore.Open(NewDbPath());
        var (scored, _) = Subject();

        store.RecordScorecard(scored);

        AssertSameCard(scored, store.FindScoredEpisode("ep-subject")!);
    }

    [Fact]
    public void Sqlite_PersistedCard_EqualsScorerOutput_AndInMemory()
    {
        // DM7(c): persisted == in-memory == derived. All three must agree for the same input.
        var (scored, derived) = Subject();
        var mem = new InMemoryWatcherObservationStore();
        mem.RecordScorecard(scored);
        using var sql = SqliteWatcherObservationStore.Open(NewDbPath());
        sql.RecordScorecard(scored);

        var fromMem = mem.FindScoredEpisode("ep-subject")!;
        var fromSql = sql.FindScoredEpisode("ep-subject")!;

        AssertSameCard(scored, fromMem);       // == derived (scored wraps the scorer output)
        AssertSameCard(scored, fromSql);
        Assert.Equal(derived.Headline, fromSql.Scorecard.Headline);
    }

    [Fact]
    public void Sqlite_ScoredEpisode_PersistsAcrossReopen()
    {
        var path = NewDbPath();
        var (scored, _) = Subject();
        using (var store = SqliteWatcherObservationStore.Open(path))
        {
            store.RecordScorecard(scored);
        }

        using var reopened = SqliteWatcherObservationStore.Open(path);
        AssertSameCard(scored, reopened.FindScoredEpisode("ep-subject")!);
    }

    [Fact]
    public void Sqlite_Recompute_Upserts_AndLeavesNoStaleDimensionRows()
    {
        using var store = SqliteWatcherObservationStore.Open(NewDbPath());
        // First card: a hand-built two-dimension card with a tripped floor.
        var first = new ScoredEpisode("ep-1", "H", "M", "op1", new ScoreSegment(TestWorkspaces.Repo, "refactor", "weave/1"),
            new Scorecard("ep-1", "weave/1", WeaveVerdict.Blocked,
                [
                    new DimensionAssessment(ScoreDimension.OutcomeIntegrity, 30, 0, null, AssessmentPosture.Deterministic, "floored"),
                    new DimensionAssessment(ScoreDimension.FocusAndTermination, 15, 2, 7.5, AssessmentPosture.Deterministic, "ok"),
                ],
                [FloorDomain.Correctness], null, "Blocked", At));
        store.RecordScorecard(first);

        // Recompute: a single-dimension Partial card with no floors. The upsert must replace children.
        var second = new ScoredEpisode("ep-1", "H", "M", "op1", new ScoreSegment(TestWorkspaces.Repo, "refactor", "weave/1"),
            new Scorecard("ep-1", "weave/1", WeaveVerdict.Partial,
                [new DimensionAssessment(ScoreDimension.OutcomeIntegrity, 30, 4, 30, AssessmentPosture.Deterministic, "clean")],
                [], new EvidenceCoverage(3, 3), "Partial: 30 / 30 observed", At.AddMinutes(1)));
        store.RecordScorecard(second);

        var read = store.FindScoredEpisode("ep-1")!;
        Assert.Equal(WeaveVerdict.Partial, read.Scorecard.Verdict);
        Assert.Single(read.Scorecard.Assessments);                       // stale FocusAndTermination row gone
        Assert.Empty(read.Scorecard.TrippedFloors);                      // stale Correctness floor gone
        Assert.Equal("Partial: 30 / 30 observed", read.Scorecard.Headline);
    }

    [Fact]
    public void Sqlite_NullCoverage_RoundTripsAsNull_NotZero()
    {
        using var store = SqliteWatcherObservationStore.Open(NewDbPath());
        var scored = new ScoredEpisode("ep-nc", "H", "M", "op1", new ScoreSegment(TestWorkspaces.Repo, "refactor", "weave/1"),
            new Scorecard("ep-nc", "weave/1", WeaveVerdict.NotScored,
                [], [], Coverage: null, "Not Scored: no goal", At));

        store.RecordScorecard(scored);

        Assert.Null(store.FindScoredEpisode("ep-nc")!.Scorecard.Coverage);
    }

    [Fact]
    public void Sqlite_AllScoredEpisodes_FeedsLeaderboardComposer()
    {
        // E11-style: persist a real cohort, then read it back THROUGH the composer the UX will use.
        using var store = SqliteWatcherObservationStore.Open(NewDbPath());
        for (var i = 0; i < 5; i++)
        {
            var (scored, _) = Subject(id: $"ep-{i}", op: i % 2 == 0 ? "op1" : "op2");
            store.RecordScorecard(scored);
        }

        var board = new LeaderboardComposer().Compose(store.AllScoredEpisodes(), new ScoreSegment(TestWorkspaces.Repo, "refactor", "weave/1"));

        var cell = board.Cell(LeaderboardFacet.HarnessModel, "Claude Code / Opus 4.8");
        Assert.NotNull(cell);
        Assert.Equal(5, cell!.Cohort);
        Assert.True(cell.Comparable);       // cohort 5, two operators -> comparable
    }

    [Fact]
    public void Empty_ReturnsNoScoredEpisodes()
    {
        using var sql = SqliteWatcherObservationStore.Open(NewDbPath());
        Assert.Empty(sql.AllScoredEpisodes());
        Assert.Null(sql.FindScoredEpisode("nope"));

        var mem = new InMemoryWatcherObservationStore();
        Assert.Empty(mem.AllScoredEpisodes());
    }
}
