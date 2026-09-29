using AiDe.Core.Presentation;
using AiDe.Core.Watcher;

namespace AiDe.Core.Tests.Watcher;

/// <summary>
/// LK-LEADER-PANE-01..08 - the Leaderboard surface read model (conn-2, US-14). The claims: the pane
/// composes one leaderboard per (task class, score schema) segment and never compares across a segment
/// (rule 11); a comparable cohort shows a rank; a below-cohort or single-operator cell shows
/// "Not Comparable" with a reason and never a rank (US-10/US-14); it never strands on Loading and
/// never renders an unreadable store as a blank success (DC-011).
/// </summary>
public sealed class WatcherLeaderboardPaneViewModelTests
{
    private static readonly DateTimeOffset At = DateTimeOffset.UnixEpoch;

    private sealed class FakeLeaderboardQuery(params ScoredEpisode[] episodes) : IWatcherLeaderboardQuery
    {
        public IReadOnlyList<ScoredEpisode> GetScoredEpisodes() => episodes;
    }

    private sealed class ThrowingLeaderboardQuery : IWatcherLeaderboardQuery
    {
        public IReadOnlyList<ScoredEpisode> GetScoredEpisodes() =>
            throw new InvalidOperationException("the observation store could not be read");
    }

    private static ScoredEpisode Ep(string id, string harness, string model, string op, double weave,
        string task = "refactor", string schema = "weave/1")
    {
        var card = new Scorecard(id, schema, WeaveVerdict.Partial,
            [new DimensionAssessment(ScoreDimension.OutcomeIntegrity, 30, 4, weave, AssessmentPosture.Deterministic, $"reason {id}")],
            [], new EvidenceCoverage(9, 10), $"Partial: {weave} / 30 observed", At);
        return new ScoredEpisode(id, harness, model, op, new ScoreSegment(TestWorkspaces.Repo, task, schema), card);
    }

    private static IEnumerable<ScoredEpisode> Cohort(string harness, string model, string task, params double[] weaves)
        => weaves.Select((w, i) => Ep($"{harness}-{task}-{i}", harness, model, i % 2 == 0 ? "op1" : "op2", w, task));

    [Fact]
    public void Load_NullQuery_IsEmpty_AndSaysWhatIsUnavailable()
    {
        var pane = new WatcherLeaderboardPaneViewModel(query: null);

        pane.Load();

        Assert.Equal(PaneState.Empty, pane.State);
        Assert.Empty(pane.Rows);
        Assert.Contains("not available", pane.StatusMessage, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("Loading", pane.StatusMessage, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public void Load_NoScoredEpisodes_IsEmpty()
    {
        var pane = new WatcherLeaderboardPaneViewModel(new FakeLeaderboardQuery());

        pane.Load();

        Assert.Equal(PaneState.Empty, pane.State);
        Assert.Contains("No scored episodes", pane.StatusMessage, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public void Load_ComparableCohort_ShowsARank()
    {
        var pane = new WatcherLeaderboardPaneViewModel(new FakeLeaderboardQuery(
            Cohort("Claude Code", "Opus 4.8", "refactor", 80, 82, 84, 86, 88).ToArray()));

        pane.Load();

        Assert.Equal(PaneState.Ready, pane.State);
        var hm = pane.Rows.Single(r => r.Facet == "HarnessModel" && r.Label == "Claude Code / Opus 4.8");
        Assert.True(hm.Comparable);
        Assert.Equal(1, hm.Rank);
        Assert.Equal("#1", hm.RankText);
        Assert.Equal(5, hm.Cohort);
    }

    [Fact]
    public void Load_SingleOperator_IsNotComparable_PrivacyProtected()
    {
        // Five episodes but ONE operator -> a rank would de-anonymise one operator (US-10).
        var episodes = Enumerable.Range(0, 5)
            .Select(i => Ep($"solo-{i}", "Codex", "GPT", "only-op", 70 + i))
            .ToArray();
        var pane = new WatcherLeaderboardPaneViewModel(new FakeLeaderboardQuery(episodes));

        pane.Load();

        var hm = pane.Rows.Single(r => r.Facet == "HarnessModel" && r.Label == "Codex / GPT");
        Assert.False(hm.Comparable);
        Assert.Equal(WatcherLeaderboardRow.NotComparableText, hm.RankText);
        Assert.False(string.IsNullOrEmpty(hm.NotComparableReason));
    }

    [Fact]
    public void Load_BelowCohortMinimum_IsNotComparable()
    {
        var pane = new WatcherLeaderboardPaneViewModel(new FakeLeaderboardQuery(
            Cohort("H", "M", "refactor", 80, 82, 84).ToArray())); // cohort 3 < 5

        pane.Load();

        var hm = pane.Rows.Single(r => r.Facet == "HarnessModel" && r.Label == "H / M");
        Assert.False(hm.Comparable);
        Assert.Equal("—", hm.MedianText);
    }

    [Fact]
    public void Load_TwoTaskClasses_AreSegmented_NeverCompared()
    {
        var episodes = Cohort("Claude Code", "Opus 4.8", "refactor", 80, 82, 84, 86, 88)
            .Concat(Cohort("Claude Code", "Opus 4.8", "bugfix", 40, 42, 44, 46, 48))
            .ToArray();
        var pane = new WatcherLeaderboardPaneViewModel(new FakeLeaderboardQuery(episodes));

        pane.Load();

        var segments = pane.Rows.Select(r => r.Segment).Distinct().ToList();
        Assert.Contains("refactor·weave/1", segments);
        Assert.Contains("bugfix·weave/1", segments);
        // The refactor and bugfix HarnessModel cells are distinct rows with their own medians.
        var refactor = pane.Rows.Single(r => r.Segment == "refactor·weave/1" && r.Facet == "HarnessModel");
        var bugfix = pane.Rows.Single(r => r.Segment == "bugfix·weave/1" && r.Facet == "HarnessModel");
        Assert.Equal(84, refactor.MedianWeave);
        Assert.Equal(44, bugfix.MedianWeave);
    }

    [Fact]
    public void Load_StoreThrows_IsError_NotLoading_NotBlankSuccess()
    {
        var pane = new WatcherLeaderboardPaneViewModel(new ThrowingLeaderboardQuery());

        pane.Load();

        Assert.Equal(PaneState.Error, pane.State);
        Assert.Empty(pane.Rows);
        Assert.Contains("unavailable", pane.StatusMessage, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("Loading", pane.StatusMessage, StringComparison.OrdinalIgnoreCase);
    }
}
