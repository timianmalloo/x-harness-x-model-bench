using AiDe.Core.Watcher;

namespace AiDe.Core.Tests.Watcher;

/// <summary>
/// LK-EPCAP-01..06 - the audit-log episode source (ep-capture). The claims: an entry that declares a
/// goal-state (goal + done_when + session, AL5b) becomes an imported closed <see cref="WorkEpisode"/>
/// with the declared goal/done-condition, its interval from started_at->datetime, and an honest outcome
/// mapping (only an explicit success is Completed); an entry missing any of the three fields is NOT an
/// episode (no fabrication); a corrupt line is skipped; and the host import records them (upsert).
/// </summary>
public sealed class AuditLogEpisodeSourceTests
{
    private const string GoalEntry =
        """{"id":"al-0271","session":"sess-1","goal":"Ship slice 4","done_when":"20 tests green","outcome":"success","started_at":"2026-08-31T13:41:28Z","datetime":"2026-08-31T13:57:31Z"}""";

    private const string BlockedEntry =
        """{"id":"al-0999","session":"sess-2","goal":"Wire the judge","done_when":"dispute round-trips","outcome":"blocked","datetime":"2026-08-31T15:00:00Z"}""";

    private const string NoGoalEntry =
        """{"id":"al-0100","session":"sess-3","prompt":"just a note","summary":"did a thing","outcome":"success"}""";

    [Fact]
    public void Parse_GoalStateEntry_BecomesAClosedEpisode_WithTheDeclaredGoalAndInterval()
    {
        var episodes = AuditLogEpisodeSource.Parse([GoalEntry]);

        var episode = Assert.Single(episodes);
        Assert.Equal("ep:al-0271", episode.EpisodeId);
        Assert.Equal("sess-1", episode.SessionId);
        Assert.Equal("Ship slice 4", episode.Goal.Statement);
        Assert.Equal("20 tests green", episode.DoneWhen.Statement);
        Assert.Equal(EpisodeState.Closed, episode.State);
        Assert.Equal(EpisodeOutcome.Completed, episode.Outcome); // "success" is the only met outcome
        Assert.Equal(DateTimeOffset.Parse("2026-08-31T13:41:28Z"), episode.OpenedAt); // started_at
        Assert.Equal(DateTimeOffset.Parse("2026-08-31T13:57:31Z"), episode.ClosedAt); // datetime
    }

    [Fact]
    public void Parse_NonSuccessOutcome_IsNotSilentlyCompleted()
    {
        var episode = Assert.Single(AuditLogEpisodeSource.Parse([BlockedEntry]));
        Assert.Equal(EpisodeOutcome.Blocked, episode.Outcome);
        // no started_at -> the interval opens at datetime (a point episode), never a wrong time.
        Assert.Equal(episode.OpenedAt, episode.ClosedAt);
    }

    [Fact]
    public void Parse_EntryWithoutAGoalState_IsNotAnEpisode()
    {
        // The fabrication guard: an audit entry that never declared a goal/done-when is skipped, not
        // turned into an episode with an invented goal (spec L127, NG1).
        Assert.Empty(AuditLogEpisodeSource.Parse([NoGoalEntry]));
    }

    [Fact]
    public void Parse_SkipsBlankAndCorruptLines_KeepsTheValidOnes()
    {
        var episodes = AuditLogEpisodeSource.Parse(["", "   ", "{ this is not json", GoalEntry, NoGoalEntry]);
        var episode = Assert.Single(episodes);
        Assert.Equal("ep:al-0271", episode.EpisodeId);
    }

    [Fact]
    public void ReadFile_MissingFile_YieldsNoEpisodes()
    {
        var missing = Path.Combine(Path.GetTempPath(), $"aide-no-audit-{Guid.NewGuid():N}.jsonl");
        Assert.Empty(AuditLogEpisodeSource.ReadFile(missing));
    }

    [Fact]
    public void ImportEpisodesFromAuditLog_RecordsTheGoalStateEpisodes_IntoTheStore()
    {
        var data = Path.Combine(Path.GetTempPath(), $"aide-epcap-data-{Guid.NewGuid():N}");
        var coord = Path.Combine(Path.GetTempPath(), $"aide-epcap-coord-{Guid.NewGuid():N}");
        var auditPath = Path.Combine(Path.GetTempPath(), $"aide-epcap-audit-{Guid.NewGuid():N}.jsonl");
        Directory.CreateDirectory(data);
        Directory.CreateDirectory(coord);
        File.WriteAllLines(auditPath, [GoalEntry, BlockedEntry, NoGoalEntry]);

        try
        {
            using var host = WatcherHost.Open(data, coord);

            var imported = host.ImportEpisodesFromAuditLog(auditPath);
            Assert.Equal(2, imported); // the two goal-state entries; the note is skipped

            var episodes = host.Store.AllEpisodes();
            Assert.Equal(2, episodes.Count);
            Assert.Contains(episodes, e => e.EpisodeId == "ep:al-0271" && e.Outcome == EpisodeOutcome.Completed);
            Assert.Contains(episodes, e => e.EpisodeId == "ep:al-0999" && e.Outcome == EpisodeOutcome.Blocked);

            // Idempotent: a re-import upserts, it does not duplicate.
            host.ImportEpisodesFromAuditLog(auditPath);
            Assert.Equal(2, host.Store.AllEpisodes().Count);
        }
        finally
        {
            try { Directory.Delete(data, recursive: true); } catch (IOException) { }
            try { Directory.Delete(coord, recursive: true); } catch (IOException) { }
            try { File.Delete(auditPath); } catch (IOException) { }
        }
    }
}
