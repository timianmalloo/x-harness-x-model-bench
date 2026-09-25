using System.Text.Json;
using AiDe.Core.Watcher;

namespace AiDe.Core.Tests.Watcher;

/// <summary>
/// The standing is delivered where the agent can read it, and where the pump cannot.
/// </summary>
/// <remarks>
/// <para><b>Why a file and not the MCP tool.</b> C1 added a <c>standing</c> tool to
/// <c>McpToolGateway</c>, which is correct and unreachable: the gateway has no caller and no
/// transport, and ADR-0004 records the transport as spiked and never built. So US-16's deliverable —
/// <i>the agent receives its standing</i> — was not met by adding a tool nothing can call.</para>
///
/// <para><b><c>AIDE_CONTRACT_LOG</c> is the channel that exists.</b> The agent is given the
/// directory, reads its own path from it, and the ingest already proves it works. A file there needs
/// no transport, no new trust boundary and no new environment variable. It stays a pull in the sense
/// ADR-0019 advisory-evaluator-calibration cares about: nothing is injected into the agent's context, the agent chooses to read.</para>
///
/// <para><b>The subdirectory is not tidiness.</b> <c>CoordinationContractLog</c> enumerates
/// <c>Directory.EnumerateFiles(logDir, "*.jsonl")</c> in <c>ReadDirectory</c> — read, not assumed,
/// with no <c>SearchOption</c>, so top-directory-only. A standing file written as <c>*.jsonl</c> in the root
/// would be read by the contract pump on every tick and every line counted MALFORMED: the feature
/// would work while the ingest counters filled with corruption that was not corruption, and the
/// first person to read parse statistics would be debugging a fiction. Two independent properties
/// keep it invisible — the extension and the depth — and both are asserted here so neither can be
/// changed without this failing.</para>
/// </remarks>
public sealed class StandingReachesTheAgentTests
{
    private static ScoredEpisode Episode(string episodeId, double earned, DateTimeOffset at) =>
        new(episodeId, "claude-code", "opus", "operator-1", new ScoreSegment(TestWorkspaces.Repo, "refactor", "weave/1"),
            new Scorecard(
                episodeId, "weave/1", WeaveVerdict.Scored,
                [
                    new DimensionAssessment(
                        ScoreDimension.OutcomeIntegrity, 4, 4, earned,
                        AssessmentPosture.Deterministic, "the suite passed"),
                ],
                [], null, "Scored", at));

    private static string NewDirectory()
    {
        var path = Path.Combine(Path.GetTempPath(), "aide-standing-" + Guid.NewGuid().ToString("N")[..8]);
        Directory.CreateDirectory(path);
        return path;
    }

    [Fact]
    public void TheStandingIsWrittenWhereTheAgentWasToldToLook()
    {
        var coord = NewDirectory();

        try
        {
            var published = StandingPublisher.Publish(
                coord, "session-1",
                [Episode("ep-1", 2, DateTimeOffset.UnixEpoch), Episode("ep-2", 4, DateTimeOffset.UnixEpoch.AddMinutes(5))],
                "ep-2");

            Assert.NotNull(published);
            Assert.True(File.Exists(published), $"nothing was written at {published}");

            var standing = JsonDocument.Parse(File.ReadAllText(published!)).RootElement;
            Assert.Equal("ep-2", standing.GetProperty("episodeId").GetString());
            Assert.True(standing.GetProperty("trend").GetInt32() > 0, "the second episode scored higher");
            Assert.NotEmpty(standing.GetProperty("reasons").EnumerateArray());
        }
        finally
        {
            Directory.Delete(coord, recursive: true);
        }
    }

    [Fact]
    public void TheContractPumpCannotSeeIt()
    {
        // THE COLLISION, asserted rather than trusted. Both properties are checked because either
        // one alone would hide the file today and neither is guaranteed by the other.
        var coord = NewDirectory();

        try
        {
            var published = StandingPublisher.Publish(
                coord, "session-1", [Episode("ep-1", 3, DateTimeOffset.UnixEpoch)], "ep-1");

            // The pump's exact call: CoordinationContractLog.ReadDirectory.
            var pumpSees = Directory.EnumerateFiles(coord, "*.jsonl").ToList();

            Assert.Empty(pumpSees);
            Assert.DoesNotContain(".jsonl", Path.GetFileName(published!), StringComparison.Ordinal);
            Assert.NotEqual(coord, Path.GetDirectoryName(published));
        }
        finally
        {
            Directory.Delete(coord, recursive: true);
        }
    }

    [Fact]
    public void AnUnscoredSessionPublishesNothingRatherThanAnEmptyStanding()
    {
        // An empty standing reads as "you have no rank and no reasons" — a claim about the agent
        // rather than about the absence of a score (DC-087). No file is the honest state.
        var coord = NewDirectory();

        try
        {
            var published = StandingPublisher.Publish(coord, "session-1", [], episodeId: null);

            Assert.Null(published);
            Assert.Empty(Directory.EnumerateFiles(coord, "*", SearchOption.AllDirectories));
        }
        finally
        {
            Directory.Delete(coord, recursive: true);
        }
    }

    [Fact]
    public void RepublishingReplacesRatherThanAppends()
    {
        // The agent reads whatever is there; two standings in one file is not a document it can
        // parse, and an append-only shape here would look like the contract log without being one.
        var coord = NewDirectory();

        try
        {
            StandingPublisher.Publish(coord, "session-1", [Episode("ep-1", 3, DateTimeOffset.UnixEpoch)], "ep-1");

            var second = StandingPublisher.Publish(
                coord, "session-1",
                [Episode("ep-1", 3, DateTimeOffset.UnixEpoch), Episode("ep-2", 1, DateTimeOffset.UnixEpoch.AddMinutes(5))],
                "ep-2");

            var standing = JsonDocument.Parse(File.ReadAllText(second!)).RootElement;

            Assert.Equal("ep-2", standing.GetProperty("episodeId").GetString());
            Assert.Single(Directory.EnumerateFiles(Path.GetDirectoryName(second!)!, "*.json"));
        }
        finally
        {
            Directory.Delete(coord, recursive: true);
        }
    }
}
