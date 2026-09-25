using AiDe.Core.Watcher;

namespace AiDe.Core.Tests.Watcher;

/// <summary>
/// LK-LB-01..N - the leaderboard + per-turn standing (design-watcher-advisory-grader, slice 7). The
/// claims (spec US-14/US-16, rules 10-11): rank harness/model/harness-model within one task class + score
/// schema version; a cell below the cohort minimum or resolving to a single operator is Not Comparable,
/// never a rank; per-turn standing shows rank + trend + one reason per dimension and exposes no single
/// optimizable scalar.
/// </summary>
public sealed class LeaderboardTests
{
    private static readonly DateTimeOffset At = DateTimeOffset.UnixEpoch;
    private static readonly LeaderboardComposer Composer = new();

    private static ScoredEpisode Ep(string id, string harness, string model, string op, double weave, string schema = "weave/1")
    {
        var card = new Scorecard(id, schema, WeaveVerdict.Partial,
            [new DimensionAssessment(ScoreDimension.OutcomeIntegrity, 30, 4, weave, AssessmentPosture.Deterministic, $"reason {id}")],
            [], new EvidenceCoverage(9, 10), $"Partial: {weave} / 30 observed", At);
        return new ScoredEpisode(id, harness, model, op, new ScoreSegment(TestWorkspaces.Repo, "refactor", schema), card);
    }

    // Five episodes for a harness/model across two operators, at a given median weave.
    private static IEnumerable<ScoredEpisode> Cohort(string harness, string model, params double[] weaves)
        => weaves.Select((w, i) => Ep($"{harness}-{i}", harness, model, i % 2 == 0 ? "op1" : "op2", w));

    // --- leaderboard --------------------------------------------------------------------------

    [Fact]
    public void Compose_TwoHarnessesAboveCohort_RankByMedianWeave()
    {
        var episodes = Cohort("Claude Code", "Opus 4.8", 80, 82, 84, 86, 88) // median 84
            .Concat(Cohort("Copilot", "GPT-5.6", 60, 62, 64, 66, 68))          // median 64
            .ToList();

        var board = Composer.Compose(episodes, new ScoreSegment(TestWorkspaces.Repo, "refactor", "weave/1"));

        var claude = board.Cell(LeaderboardFacet.Harness, "Claude Code")!;
        var copilot = board.Cell(LeaderboardFacet.Harness, "Copilot")!;
        Assert.True(claude.Comparable);
        Assert.Equal(1, claude.Rank);
        Assert.Equal(84, claude.MedianWeave);
        Assert.Equal(5, claude.Cohort);
        Assert.Equal(2, copilot.Rank);
    }

    [Fact]
    public void Compose_BelowCohortMinimum_IsNotComparable()
    {
        var episodes = Cohort("Claude Code", "Opus 4.8", 80, 82, 84, 86).ToList(); // only 4

        var cell = Composer.Compose(episodes, new ScoreSegment(TestWorkspaces.Repo, "refactor", "weave/1")).Cell(LeaderboardFacet.Harness, "Claude Code")!;

        Assert.False(cell.Comparable);
        Assert.Null(cell.Rank);
        Assert.Contains("< 5", cell.NotComparableReason);
    }

    [Fact]
    public void Compose_SingleOperator_IsNotComparable_PrivacyProtected()
    {
        // Five episodes, all one operator -> the cell proxies one human (US-10).
        var episodes = Enumerable.Range(0, 5)
            .Select(i => Ep($"m-{i}", "Claude Code", "Opus 4.8", "only-op", 80 + i))
            .ToList();

        var cell = Composer.Compose(episodes, new ScoreSegment(TestWorkspaces.Repo, "refactor", "weave/1")).Cell(LeaderboardFacet.Harness, "Claude Code")!;

        Assert.False(cell.Comparable);
        Assert.Contains("single operator", cell.NotComparableReason);
    }

    [Fact]
    public void Compose_OtherSchemaVersion_IsSegmentedOut()
    {
        var episodes = Cohort("Claude Code", "Opus 4.8", 80, 82, 84, 86, 88)
            .Concat(Enumerable.Range(0, 5).Select(i => Ep($"v2-{i}", "Claude Code", "Opus 4.8", i % 2 == 0 ? "op1" : "op2", 10, schema: "weave/2")))
            .ToList();

        var cell = Composer.Compose(episodes, new ScoreSegment(TestWorkspaces.Repo, "refactor", "weave/1")).Cell(LeaderboardFacet.Harness, "Claude Code")!;

        Assert.Equal(5, cell.Cohort);       // only the weave/1 episodes
        Assert.Equal(84, cell.MedianWeave); // the weave/2 (10) episodes did not drag it down
    }

    [Fact]
    public void Compose_RanksTheHarnessModelFacet()
    {
        var episodes = Cohort("Claude Code", "Opus 4.8", 80, 82, 84, 86, 88).ToList();

        var cell = Composer.Compose(episodes, new ScoreSegment(TestWorkspaces.Repo, "refactor", "weave/1")).Cell(LeaderboardFacet.HarnessModel, "Claude Code / Opus 4.8")!;

        Assert.True(cell.Comparable);
        Assert.Equal(1, cell.Rank);
    }

    // --- per-turn standing (US-16) ------------------------------------------------------------

    private static ScoredEpisode SixDimensionSubject(string harness = "Claude Code", string model = "Opus 4.8")
    {
        var episode = new WorkEpisode("ep-subject", "s1", new EpisodeGeneration(1),
            new Goal("do X"), new DoneCondition("X done"), null, At, At.AddMinutes(5), EpisodeOutcome.Completed);
        var signals = new DeterministicEpisodeSignals(true, true, true, false,
            new HashSet<FloorDomain>(), 0, false, 3, 3, 2, 2, true, 10, 9);
        var card = new WeaveScorer().Score(episode, signals, new FixedTimeProvider(At));
        return new ScoredEpisode("ep-subject", harness, model, "op1", new ScoreSegment(TestWorkspaces.Repo, "refactor", "weave/1"), card);
    }

    [Fact]
    public void Standing_ComparableCell_ShowsRankTrend_AndOneReasonPerDimension()
    {
        var board = Composer.Compose(Cohort("Claude Code", "Opus 4.8", 80, 82, 84, 86, 88).ToList(), new ScoreSegment(TestWorkspaces.Repo, "refactor", "weave/1"));
        var subject = SixDimensionSubject();

        // A HISTORY, not a trend. These tests used to pass `trend: 3` — a number nothing in the
        // product produced — so they asserted that the composer copies its argument. The trend is
        // now derived from the same cohort, which is what makes the assertion about behaviour.
        var earlier = Ep("ep-earlier", "Claude Code", "Opus 4.8", "op1", subject.Weave - 3);

        var standing = new StandingComposer().Compose(subject, board, [earlier, subject]);

        Assert.True(standing.RankComparable);
        Assert.Equal(1, standing.Rank);
        Assert.Equal(3, standing.Trend);
        Assert.Equal(subject.Scorecard.Assessments.Count, standing.Reasons.Count); // one reason per dimension
    }

    [Fact]
    public void Standing_InsufficientCohort_RankNotComparable_ButReasonsAndTrendPresent()
    {
        var board = Composer.Compose(Cohort("Claude Code", "Opus 4.8", 80, 82, 84).ToList(), new ScoreSegment(TestWorkspaces.Repo, "refactor", "weave/1")); // cohort 3
        var subject = SixDimensionSubject();

        var earlier = Ep("ep-earlier", "Claude Code", "Opus 4.8", "op1", subject.Weave + 1);

        var standing = new StandingComposer().Compose(subject, board, [earlier, subject]);

        Assert.False(standing.RankComparable);
        Assert.Null(standing.Rank);
        Assert.Equal(-1, standing.Trend);                       // trend still delivered
        Assert.NotEmpty(standing.Reasons);                      // evidence still delivered
    }

    [Fact]
    public void AgentStanding_ExposesNoSingleOptimizableScalar()
    {
        // US-16: the standing offers no single scalar to optimize - by design it has rank, trend, and
        // per-dimension reasons, but no aggregate score/weave/points field.
        var names = typeof(AgentStanding).GetProperties().Select(p => p.Name).ToList();

        Assert.DoesNotContain("Score", names);
        Assert.DoesNotContain("Weave", names);
        Assert.DoesNotContain("Points", names);
        Assert.Contains("Reasons", names);
        Assert.Contains("Trend", names);
    }

    // ---- S2: TaskClasses.FreeForm is an ordinary class, not a second Unclassified -----------------

    /// <summary>
    /// <c>free-form</c> is a declared class, not an absence: a segment carrying it is a cohort, unlike
    /// one carrying <see cref="ScoreSegment.Unclassified"/> (ADR-0033 §4; Ruling 72's reading of
    /// ADR-0028: "a `free-form` class is a legitimate cohort key").
    /// </summary>
    [Fact]
    public void ASegmentCarryingFreeFormIsComparable_UnlikeUnclassified()
    {
        var freeForm = new ScoreSegment(TestWorkspaces.Repo, TaskClasses.FreeForm, "weave/1");
        var unclassified = new ScoreSegment(TestWorkspaces.Repo, ScoreSegment.Unclassified, "weave/1");

        Assert.True(freeForm.IsComparable, freeForm.IncomparableReason);
        Assert.Null(freeForm.IncomparableReason);

        Assert.False(unclassified.IsComparable);
        Assert.NotNull(unclassified.IncomparableReason);
    }

    /// <summary>The partition key treats <c>free-form</c> as its own cohort, distinct from other classes.</summary>
    [Fact]
    public void FreeFormPartitionsAsItsOwnCohort_SeparateFromOtherTaskClasses()
    {
        var episodes = Cohort("Claude Code", "Opus 4.8", 80, 82, 84, 86, 88)
            .Select(e => e with { Segment = e.Segment with { TaskClass = TaskClasses.FreeForm } })
            .ToList();

        var board = Composer.Compose(episodes, new ScoreSegment(TestWorkspaces.Repo, TaskClasses.FreeForm, "weave/1"));
        var cell = board.Cell(LeaderboardFacet.Harness, "Claude Code")!;

        Assert.True(cell.Comparable);
        Assert.Equal(5, cell.Cohort);
    }
}
