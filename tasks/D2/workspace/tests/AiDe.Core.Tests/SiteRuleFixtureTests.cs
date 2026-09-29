using System.Text.Json;
using AiDe.Core.Watcher;
using AiDe.Core.Tests.Watcher;

namespace AiDe.Core.Tests;

/// <summary>
/// Binds the public site's JavaScript demos to the C# rules they mirror.
/// </summary>
/// <remarks>
/// <para><b>Why this exists.</b> <c>site/assets/site.js</c> reimplements <see cref="WeaveScorer"/>,
/// <see cref="LeaderboardComposer"/> and <see cref="GraderInjectionScanner"/> so the published page
/// runs offline with no server and no network. Its README said "the C# is the authority; if they
/// disagree, the JavaScript is wrong" — which is a note, and a note has no failure mode. A weight
/// or a cohort rule could change here and the site would go on publishing the old one, confidently.
/// </para>
///
/// <para><b>Both sides evaluate the same file.</b> <c>tests/fixtures/site-rules.json</c> holds the
/// cases. This test runs the shipped types against it; <c>tools/verify-site-rules.mjs</c> runs
/// <c>site.js</c> against it under Node. A divergence fails one of the two.</para>
///
/// <para><b>The fixture is not the authority either.</b> Its expectations are re-derived here from
/// the real types, so a fixture edited to agree with a broken implementation fails on this side.
/// </para>
/// </remarks>
public sealed class SiteRuleFixtureTests
{
    private static readonly JsonElement Fixture = LoadFixture();

    private static JsonElement LoadFixture()
    {
        var dir = new DirectoryInfo(AppContext.BaseDirectory);
        while (dir is not null && !File.Exists(Path.Combine(dir.FullName, "AiDe.sln")))
        {
            dir = dir.Parent;
        }

        Assert.NotNull(dir);
        var path = Path.Combine(dir!.FullName, "tests", "fixtures", "site-rules.json");
        Assert.True(File.Exists(path), $"the shared site-rule fixture is missing at {path}");
        return JsonDocument.Parse(File.ReadAllText(path)).RootElement.Clone();
    }

    // ------------------------------------------------------------------ schema

    /// <summary>
    /// The fixture's copy of <c>weave/1</c> matches the shipped schema, dimension for dimension.
    /// </summary>
    /// <remarks>
    /// Checked before any case runs. If a weight moved in C# and not in the fixture, every case
    /// below would fail with an arithmetic message that hides the real cause.
    /// </remarks>
    [Fact]
    public void TheFixturesSchemaMatchesWeave1()
    {
        var schema = Fixture.GetProperty("weaveSchema");
        Assert.Equal(ScoreSchema.Weave1Version, schema.GetProperty("version").GetString());
        Assert.Equal(ScoreSchema.Weave1.TotalWeight, schema.GetProperty("totalWeight").GetInt32());

        var expected = schema.GetProperty("dimensions").EnumerateArray().ToList();
        Assert.Equal(ScoreSchema.Weave1.Dimensions.Count, expected.Count);

        var observedWeight = 0;
        for (var i = 0; i < expected.Count; i++)
        {
            var shipped = ScoreSchema.Weave1.Dimensions[i];
            Assert.Equal(shipped.Weight, expected[i].GetProperty("weight").GetInt32());
            Assert.Equal(shipped.Posture.ToString(), expected[i].GetProperty("posture").GetString());
            Assert.Equal(Key(shipped.Dimension), expected[i].GetProperty("key").GetString());
            if (shipped.Posture == AssessmentPosture.Deterministic)
            {
                observedWeight += shipped.Weight;
            }
        }

        Assert.Equal(observedWeight, schema.GetProperty("observedWeight").GetInt32());
    }

    private static string Key(ScoreDimension d) => d switch
    {
        ScoreDimension.OutcomeIntegrity => "outcome",
        ScoreDimension.FocusAndTermination => "focus",
        ScoreDimension.GuidanceAdherence => "guidance",
        ScoreDimension.CoordinationAndLearning => "coordination",
        ScoreDimension.EvidenceDiscipline => "evidence",
        ScoreDimension.SolutionEconomy => "economy",
        _ => throw new ArgumentOutOfRangeException(nameof(d)),
    };

    // ------------------------------------------------------------------ weave

    public static TheoryData<int> WeaveCaseIndexes() => Indexes("weaveCases");

    [Theory]
    [MemberData(nameof(WeaveCaseIndexes))]
    public void EveryWeaveCaseMatchesTheShippedScorer(int index)
    {
        var kase = Fixture.GetProperty("weaveCases")[index];
        var name = kase.GetProperty("name").GetString();
        var s = kase.GetProperty("signals");
        var expect = kase.GetProperty("expect");

        var closed = s.GetProperty("closed").GetBoolean();
        var completed = s.GetProperty("completed").GetBoolean();

        var episode = new WorkEpisode(
            "ep-1", "session-1", new EpisodeGeneration(1),
            new Goal("a goal"), new DoneCondition("a done condition"), null,
            DateTimeOffset.UnixEpoch,
            closed ? DateTimeOffset.UnixEpoch.AddMinutes(5) : null,
            closed ? (completed ? EpisodeOutcome.Completed : EpisodeOutcome.Abandoned) : null);

        var floors = new HashSet<FloorDomain>();
        if (s.GetProperty("security").GetBoolean())
        {
            floors.Add(FloorDomain.Security);
        }

        var signals = new DeterministicEpisodeSignals(
            HasVerificationPath: s.GetProperty("verifpath").GetBoolean(),
            AcceptanceCriteriaMet: s.GetProperty("acceptance").GetBoolean(),
            RequiredVerificationExecuted: s.GetProperty("verifrun").GetBoolean(),
            RegressionPresent: s.GetProperty("regression").GetBoolean(),
            UnresolvedFloorBlockers: floors,
            ActionsAfterDoneCondition: s.GetProperty("afterdone").GetBoolean() ? 1 : 0,
            PrematureCompletion: s.GetProperty("premature").GetBoolean(),
            RequiredGuidanceTriggers: s.GetProperty("guidanceRequired").GetInt32(),
            SatisfiedGuidanceTriggers: s.GetProperty("guidanceSatisfied").GetInt32(),
            RequiredCoordinationSignals: s.GetProperty("coordRequired").GetInt32(),
            ObservedCoordinationSignals: s.GetProperty("coordObserved").GetInt32(),
            CoverageCalibrated: false,
            RequiredSignalTotal: 0,
            ObservedSignalTotal: 0);

        var card = new WeaveScorer().Score(
            episode, signals, new FixedTimeProvider(DateTimeOffset.UnixEpoch));

        Assert.True(
            expect.GetProperty("verdict").GetString() == card.Verdict.ToString(),
            $"'{name}': fixture says {expect.GetProperty("verdict").GetString()}, the scorer says {card.Verdict}");

        if (expect.TryGetProperty("tripped", out var tripped))
        {
            Assert.Equal(
                tripped.EnumerateArray().Select(t => t.GetString() ?? "").ToList(),
                card.TrippedFloors.Select(f => f.ToString()).ToList());
        }

        if (expect.TryGetProperty("earned", out var earned))
        {
            var scored = card.Assessments.Where(a => a.EarnedPoints is not null).ToList();
            Assert.Equal(earned.GetDouble(), scored.Sum(a => a.EarnedPoints!.Value), 3);
            Assert.Equal(
                expect.GetProperty("observedWeight").GetInt32(),
                scored.Sum(a => a.Weight));
        }
    }

    // ------------------------------------------------------------------ leaderboard

    public static TheoryData<int> LeaderboardCaseIndexes() => Indexes("leaderboardCases");

    [Theory]
    [MemberData(nameof(LeaderboardCaseIndexes))]
    public void EveryLeaderboardCaseMatchesTheShippedComposer(int index)
    {
        var kase = Fixture.GetProperty("leaderboardCases")[index];
        var name = kase.GetProperty("name").GetString();
        var cohortMinimum = kase.GetProperty("cohortMinimum").GetInt32();

        // One episode per cohort member, with `operators` distinct operator ids spread across them,
        // and a Weave whose MEDIAN is the fixture's figure. The composer is given episodes, not
        // cells, so the fixture's cell shape has to be built into real inputs here - which is the
        // point: it exercises the real segmentation, not a re-statement of it.
        var episodes = new List<ScoredEpisode>();
        foreach (var cell in kase.GetProperty("cells").EnumerateArray())
        {
            var label = cell.GetProperty("label").GetString()!;
            var parts = label.Split(" / ");
            var cohort = cell.GetProperty("cohort").GetInt32();
            var operators = cell.GetProperty("operators").GetInt32();
            var median = cell.GetProperty("median").GetDouble();

            for (var i = 0; i < cohort; i++)
            {
                episodes.Add(new ScoredEpisode(
                    $"{label}-{i}", parts[0], parts[1], $"op-{label}-{i % operators}",
                    new ScoreSegment(TestWorkspaces.Repo, "task", ScoreSchema.Weave1Version),
                    Card($"{label}-{i}", median)));
            }
        }

        var board = new LeaderboardComposer().Compose(
            episodes, new ScoreSegment(TestWorkspaces.Repo, "task", ScoreSchema.Weave1Version), cohortMinimum);

        foreach (var expected in kase.GetProperty("expect").EnumerateArray())
        {
            var label = expected.GetProperty("label").GetString()!;
            var cell = board.Cell(LeaderboardFacet.HarnessModel, label);
            Assert.True(cell is not null, $"'{name}': no harness-model cell for '{label}'");

            Assert.True(
                expected.GetProperty("comparable").GetBoolean() == cell!.Comparable,
                $"'{name}': '{label}' comparable={cell.Comparable}, fixture says {expected.GetProperty("comparable").GetBoolean()}");

            var rank = expected.GetProperty("rank");
            if (rank.ValueKind == JsonValueKind.Null)
            {
                Assert.Null(cell.Rank);
            }
            else
            {
                Assert.Equal(rank.GetInt32(), cell.Rank);
            }

            if (expected.TryGetProperty("reason", out var reason))
            {
                Assert.Equal(reason.GetString(), cell.NotComparableReason);
            }
        }
    }

    /// <summary>A card whose single scored dimension yields exactly <paramref name="weave"/> points.</summary>
    private static Scorecard Card(string episodeId, double weave) => new(
        episodeId, ScoreSchema.Weave1Version, WeaveVerdict.Partial,
        [new DimensionAssessment(
            ScoreDimension.OutcomeIntegrity, 30, 4, weave, AssessmentPosture.Deterministic, "fixture")],
        [], null, "fixture", DateTimeOffset.UnixEpoch);

    // ------------------------------------------------------------------ injection

    public static TheoryData<int> InjectionCaseIndexes() => Indexes("injectionCases");

    [Theory]
    [MemberData(nameof(InjectionCaseIndexes))]
    public void EveryInjectionCaseMatchesTheShippedScanner(int index)
    {
        var kase = Fixture.GetProperty("injectionCases")[index];
        var text = kase.GetProperty("text").GetString();

        Assert.True(
            kase.GetProperty("flagged").GetBoolean() == GraderInjectionScanner.LooksLikeInjection(text),
            $"'{text}': the scanner says {GraderInjectionScanner.LooksLikeInjection(text)}");
    }

    // ------------------------------------------------------------------ shared

    /// <summary>
    /// Index the cases rather than inlining them, so a case added to the fixture is run without
    /// touching this file — and an EMPTY array fails rather than passing vacuously (R4).
    /// </summary>
    private static TheoryData<int> Indexes(string property)
    {
        var data = new TheoryData<int>();
        var count = Fixture.GetProperty(property).GetArrayLength();
        Assert.True(count > 0, $"the fixture's '{property}' is empty; a rule with no cases is unbound");
        for (var i = 0; i < count; i++)
        {
            data.Add(i);
        }

        return data;
    }
}
