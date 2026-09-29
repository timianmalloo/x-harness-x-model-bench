using AiDe.Core.Facts;
using AiDe.Core.Mcp;
using AiDe.Core.Presentation;
using AiDe.Core.Watcher;

namespace AiDe.Core.Tests.Watcher;

/// <summary>
/// An agent receives its standing, and a trend it does not have is Not Recorded rather than zero.
/// </summary>
/// <remarks>
/// <para><b>US-16 is written from the agent's seat</b> — <i>"As an agent, I want to see how my
/// harness and model are scoring and why, each turn"</i> — and its acceptance criterion is that the
/// agent <b>receives</b> its standing. <c>StandingComposer</c> was built, unit-tested and had zero
/// production callers; the slice's first acceptance criterion said only that a standing is
/// <i>produced</i>, which the leaderboard pane could satisfy while the operator saw it and the agent
/// received nothing. That is a criterion that does not reach its own deliverable.</para>
///
/// <para><b>The agent's only channels are the MCP tools.</b> Three of the five are writes;
/// <c>describe</c> and <c>find</c> are pulls. A <b>pull</b> is the right shape and not merely the
/// cheapest: a push would put the scorer's output into the agent's context every turn whether or not
/// it asked, and ADR-0019 advisory-evaluator-calibration's anti-Goodhart section is precisely about what an agent is shown
/// regarding its own scoring.</para>
///
/// <para><b>And nothing computed a trend.</b> <c>StandingComposer.Compose</c> took <c>int trend</c>
/// as a parameter with no producer anywhere in <c>src/</c>, and <c>AgentStanding.Trend</c> was a
/// plain <c>int</c> — so an agent's first scored episode reported <b>0</b>, which is
/// indistinguishable from "no change" in the one feature whose purpose is telling an agent whether
/// it is improving or regressing. The spec settles it rather than taste: <i>"Every displayed
/// evaluation or learning claim has evidence/confidence, or renders Not Recorded."</i></para>
/// </remarks>
public sealed class AnAgentCanPullItsOwnStandingTests
{
    private const string Workspace = "ws-1";

    private static McpCallerContext Caller(string workspace = Workspace) =>
        new(workspace, "session-1", SessionProcessingClass.LocalOnly,
            new CallerPrincipal("agent-1", CallerKind.McpClient));

    /// <summary>A scored episode for one harness/model, at a given point in the sequence.</summary>
    private static ScoredEpisode Episode(string id, string harness, string model, double earned) =>
        new(id, harness, model, "operator-1", new ScoreSegment(TestWorkspaces.Repo, "refactor", "weave/1"),
            new Scorecard(
                id, "weave/1", WeaveVerdict.Scored,
                [
                    new DimensionAssessment(
                        ScoreDimension.OutcomeIntegrity, 4, 4, earned,
                        AssessmentPosture.Deterministic,
                        "the suite passed and a red test was observed failing first"),
                ],
                [], null, "Scored", DateTimeOffset.UnixEpoch));

    private sealed class Episodes(params ScoredEpisode[] episodes) : IWatcherLeaderboardQuery
    {
        public IReadOnlyList<ScoredEpisode> GetScoredEpisodes() => episodes;
    }

    private static AgentStanding? Standing(McpToolResult result) => result.Payload as AgentStanding;

    [Fact]
    public void AnAgentPullsItsStandingAndGetsReasons()
    {
        // THE DELIVERABLE. Not "a standing is produced somewhere" — the agent asks and receives.
        var gateway = Gateway(new Episodes(
            Episode("ep-1", "claude-code", "opus", 3),
            Episode("ep-2", "claude-code", "opus", 4)));

        var result = gateway.Standing(Caller(), "ep-2");

        Assert.False(result.IsError);

        var standing = Standing(result);
        Assert.NotNull(standing);
        Assert.Equal("ep-2", standing!.EpisodeId);
        Assert.NotEmpty(standing.Reasons);
    }

    [Fact]
    public void AFirstEpisodeHasNoTrendRatherThanATrendOfZero()
    {
        // THE MODELLING DEFECT. With `int Trend`, an agent's first turn reports 0 — the same value
        // as "you did not move" — in the feature whose entire purpose is telling it whether it is
        // improving. Absence must be distinguishable from no-change.
        var gateway = Gateway(new Episodes(Episode("ep-1", "claude-code", "opus", 3)));

        var standing = Standing(gateway.Standing(Caller(), "ep-1"));

        Assert.NotNull(standing);
        Assert.Null(standing!.Trend);
    }

    [Fact]
    public void ASecondEpisodeReportsMovementAgainstTheFirst()
    {
        // The other half: once there IS history, the trend is a real observation. Without this a
        // fix that always returned null would satisfy the test above.
        var gateway = Gateway(new Episodes(
            Episode("ep-1", "claude-code", "opus", 2),
            Episode("ep-2", "claude-code", "opus", 4)));

        var standing = Standing(gateway.Standing(Caller(), "ep-2"));

        Assert.NotNull(standing);
        Assert.NotNull(standing!.Trend);
        Assert.True(standing.Trend > 0, "the second episode scored higher, so the trend is upward");
    }

    [Fact]
    public void AnUnknownEpisodeIsAnErrorRatherThanAnEmptyStanding()
    {
        // An empty standing would read as "you have no rank and no reasons", which is a claim about
        // the agent rather than about the lookup (DC-087).
        var gateway = Gateway(new Episodes(Episode("ep-1", "claude-code", "opus", 3)));

        var result = gateway.Standing(Caller(), "ep-missing");

        Assert.True(result.IsError);
    }

    [Fact]
    public void ACrossWorkspaceCallerIsRefusedLikeEveryOtherTool()
    {
        // The tool inherits the gateway's existing guard rather than adding one. If it did not, the
        // standing would be the one MCP tool without a workspace check.
        var gateway = Gateway(new Episodes(Episode("ep-1", "claude-code", "opus", 3)));

        var result = gateway.Standing(Caller("other-ws"), "ep-1");

        Assert.True(result.IsError);
        Assert.Equal(McpErrorCodes.CrossWorkspace, result.ErrorCode);
    }

    private static McpToolGateway Gateway(IWatcherLeaderboardQuery episodes) =>
        new(new AiDe.Core.Projections.ProjectionService(TestWorkspace.Create().Store), Workspace, episodes);
}
