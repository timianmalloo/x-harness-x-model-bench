using AiDe.Core.Presentation;
using AiDe.Core.Watcher;
using Microsoft.Data.Sqlite;

namespace AiDe.Core.Tests.Watcher;

/// <summary>
/// LK-DISPUTE-01..12 - the operator dispute path (conn-4, US-16 / spec rule 12). The claims: a dispute
/// is an append-only fact that NEVER overwrites the Scorecard; it round-trips (whole-score and
/// per-dimension) on both stores and persists across a reopen; the SQLite fact rejects UPDATE/DELETE
/// (DM11); a duplicate dispute id is ignored idempotently; the derived Disputed state is computed from
/// the presence of dispute facts (DM7); and the Leaderboard surface makes disputed episodes discoverable.
/// </summary>
public sealed class ScoreDisputeTests
{
    private static readonly DateTimeOffset At = DateTimeOffset.UnixEpoch;

    private static string NewDbPath()
    {
        var dir = Path.Combine(Path.GetTempPath(), "aide-tests", "watcher-dispute", Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(dir);
        return Path.Combine(dir, "watcher.db");
    }

    private static ScoreDispute Dispute(
        string id = "d1", string episode = "ep-1", string op = "op1",
        ScoreDimension? dim = null, string reason = "the coverage claim is not evidenced", int minute = 0)
        => new(id, episode, op, dim, reason, At.AddMinutes(minute));

    private static ScoredEpisode ScoredEpisode(string id = "ep-1", double weave = 84)
    {
        var card = new Scorecard(id, "weave/1", WeaveVerdict.Partial,
            [new DimensionAssessment(ScoreDimension.OutcomeIntegrity, 30, 4, weave, AssessmentPosture.Deterministic, "r")],
            [], new EvidenceCoverage(9, 10), $"Partial: {weave} / 30 observed", At);
        return new ScoredEpisode(id, "Claude Code", "Opus 4.8", "op1", new ScoreSegment(TestWorkspaces.Repo, "refactor", "weave/1"), card);
    }

    [Fact]
    public void InMemory_AppendThenRead_ReturnsTheDispute()
    {
        var store = new InMemoryWatcherObservationStore();
        store.AppendScoreDispute(Dispute());

        var disputes = store.DisputesForEpisode("ep-1");

        Assert.Single(disputes);
        Assert.Equal("the coverage claim is not evidenced", disputes[0].Reason);
    }

    [Fact]
    public void Sqlite_AppendThenRead_RoundTrips_WholeScoreAndPerDimension()
    {
        using var store = SqliteWatcherObservationStore.Open(NewDbPath());
        store.AppendScoreDispute(Dispute(id: "d1", dim: null, minute: 0));
        store.AppendScoreDispute(Dispute(id: "d2", dim: ScoreDimension.EvidenceDiscipline, minute: 1));

        var disputes = store.DisputesForEpisode("ep-1");

        Assert.Equal(2, disputes.Count);
        Assert.Null(disputes[0].DisputedDimension);                              // whole score
        Assert.Equal(ScoreDimension.EvidenceDiscipline, disputes[1].DisputedDimension); // per-dimension
    }

    [Fact]
    public void Sqlite_Dispute_PersistsAcrossReopen()
    {
        var path = NewDbPath();
        using (var store = SqliteWatcherObservationStore.Open(path))
        {
            store.AppendScoreDispute(Dispute());
        }

        using var reopened = SqliteWatcherObservationStore.Open(path);
        Assert.Single(reopened.DisputesForEpisode("ep-1"));
    }

    [Fact]
    public void Dispute_NeverOverwritesTheScorecard_PriorScorePreserved()
    {
        // Rule 12: "a dispute appends a superseding evaluation record; prior scores are not overwritten."
        using var store = SqliteWatcherObservationStore.Open(NewDbPath());
        store.RecordScorecard(ScoredEpisode(weave: 84));

        store.AppendScoreDispute(Dispute(episode: "ep-1"));

        var scored = store.FindScoredEpisode("ep-1")!;
        Assert.Equal(84, scored.Weave);                            // the score is untouched
        Assert.Single(store.DisputesForEpisode("ep-1"));           // the dispute is recorded alongside
    }

    [Fact]
    public void Sqlite_DisputeFact_IsAppendOnly_UpdateIsRejected()
    {
        var path = NewDbPath();
        using (var store = SqliteWatcherObservationStore.Open(path))
        {
            store.AppendScoreDispute(Dispute());
        }

        using var raw = new SqliteConnection(
            new SqliteConnectionStringBuilder { DataSource = path, Mode = SqliteOpenMode.ReadWrite, Pooling = false }.ToString());
        raw.Open();
        using var update = raw.CreateCommand();
        update.CommandText = "UPDATE score_dispute_fact SET reason = 'tampered';";

        var ex = Assert.Throws<SqliteException>(() => update.ExecuteNonQuery());
        Assert.Contains("append-only", ex.Message, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public void Sqlite_DisputeFact_IsAppendOnly_DeleteIsRejected()
    {
        var path = NewDbPath();
        using (var store = SqliteWatcherObservationStore.Open(path))
        {
            store.AppendScoreDispute(Dispute());
        }

        using var raw = new SqliteConnection(
            new SqliteConnectionStringBuilder { DataSource = path, Mode = SqliteOpenMode.ReadWrite, Pooling = false }.ToString());
        raw.Open();
        using var delete = raw.CreateCommand();
        delete.CommandText = "DELETE FROM score_dispute_fact;";

        var ex = Assert.Throws<SqliteException>(() => delete.ExecuteNonQuery());
        Assert.Contains("append-only", ex.Message, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public void Sqlite_DuplicateDisputeId_IsIgnoredIdempotently()
    {
        using var store = SqliteWatcherObservationStore.Open(NewDbPath());
        store.AppendScoreDispute(Dispute(id: "d1"));

        store.AppendScoreDispute(Dispute(id: "d1", reason: "different text, same id"));

        var disputes = store.DisputesForEpisode("ep-1");
        Assert.Single(disputes);
        Assert.Equal("the coverage claim is not evidenced", disputes[0].Reason); // first write wins, no update
    }

    [Fact]
    public void AllDisputes_ReturnsAcrossEpisodes_InRaiseOrder()
    {
        var store = new InMemoryWatcherObservationStore();
        store.AppendScoreDispute(Dispute(id: "d2", episode: "ep-2", minute: 5));
        store.AppendScoreDispute(Dispute(id: "d1", episode: "ep-1", minute: 1));

        var all = store.AllDisputes();

        Assert.Equal(2, all.Count);
        Assert.Equal("ep-1", all[0].EpisodeId);   // ordered by raised_at, not insert order
        Assert.Equal("ep-2", all[1].EpisodeId);
    }

    [Fact]
    public void DisputeProjection_DerivesTheDisputedState_FromTheFacts()
    {
        var store = new InMemoryWatcherObservationStore();
        store.AppendScoreDispute(Dispute(id: "d1", episode: "ep-1"));
        store.AppendScoreDispute(Dispute(id: "d2", episode: "ep-1", minute: 1));
        var projection = new DisputeProjection(store);

        Assert.True(projection.IsDisputed("ep-1"));
        Assert.Equal(2, projection.DisputeCount("ep-1"));
        Assert.False(projection.IsDisputed("ep-2"));
        Assert.Contains("ep-1", projection.DisputedEpisodeIds());
        Assert.DoesNotContain("ep-2", projection.DisputedEpisodeIds());
    }

    [Fact]
    public void LeaderboardPane_SurfacesTheDisputedCount()
    {
        // The Disputed state is discoverable from the Leaderboard surface (US-16).
        using var store = SqliteWatcherObservationStore.Open(NewDbPath());
        for (var i = 0; i < 5; i++)
        {
            var card = new Scorecard($"ep-{i}", "weave/1", WeaveVerdict.Partial,
                [new DimensionAssessment(ScoreDimension.OutcomeIntegrity, 30, 4, 80 + i, AssessmentPosture.Deterministic, "r")],
                [], new EvidenceCoverage(9, 10), $"Partial: {80 + i} / 30 observed", At);
            store.RecordScorecard(new ScoredEpisode($"ep-{i}", "Claude Code", "Opus 4.8", i % 2 == 0 ? "op1" : "op2", new ScoreSegment(TestWorkspaces.Repo, "refactor", "weave/1"), card));
        }
        store.AppendScoreDispute(Dispute(id: "d1", episode: "ep-0"));
        store.AppendScoreDispute(Dispute(id: "d2", episode: "ep-3"));

        var pane = new WatcherLeaderboardPaneViewModel(new WatcherLeaderboardQuery(store), new WatcherDisputeQuery(store));
        pane.Load();

        Assert.Equal(PaneState.Ready, pane.State);
        Assert.Contains("2 disputed episode(s)", pane.StatusMessage);
    }

    [Fact]
    public void LeaderboardPane_NoDisputeQuery_ShowsNoDisputedCount()
    {
        using var store = SqliteWatcherObservationStore.Open(NewDbPath());
        var card = new Scorecard("ep-0", "weave/1", WeaveVerdict.Partial,
            [new DimensionAssessment(ScoreDimension.OutcomeIntegrity, 30, 4, 80, AssessmentPosture.Deterministic, "r")],
            [], new EvidenceCoverage(9, 10), "Partial: 80 / 30 observed", At);
        store.RecordScorecard(new ScoredEpisode("ep-0", "H", "M", "op1", new ScoreSegment(TestWorkspaces.Repo, "refactor", "weave/1"), card));

        var pane = new WatcherLeaderboardPaneViewModel(new WatcherLeaderboardQuery(store));
        pane.Load();

        Assert.DoesNotContain("disputed", pane.StatusMessage, StringComparison.OrdinalIgnoreCase);
    }
}
