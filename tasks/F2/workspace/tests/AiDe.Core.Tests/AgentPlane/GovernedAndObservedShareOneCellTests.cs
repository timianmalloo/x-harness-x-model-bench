using AiDe.Core.AgentPlane;
using AiDe.Core.Tests.Watcher;
using AiDe.Core.Watcher;
using Microsoft.Data.Sqlite;

namespace AiDe.Core.Tests.AgentPlane;

/// <summary>
/// R4's decisive clause: one governed episode and one observed (audit-imported) episode, in
/// <b>one store</b>, land in <b>one <see cref="ScoreSegment"/> cell</b> carrying <b>two distinct
/// modes</b>.
/// </summary>
/// <remarks>
/// <para><b>Why one test and not two.</b> Two tests — "the governed path scores" and "the observed
/// path scores" — can both pass while the two episodes never meet, which is the only thing R4
/// actually asserts. The failure worth catching is a cohort split, and a split is invisible from
/// inside either half.</para>
///
/// <para><b>Why the positive shape.</b> "Mode is absent from the partition key" is checked in
/// <c>ScoredEpisodeModeMigrationTests.ModeIsNotAScoreSegmentMember</c>, and that assertion is a
/// compile-time tautology: it re-reads a constructor signature the compiler already fixed. It cannot
/// fail for the right reason, because no behaviour reaches it. This test asserts what must be true
/// of the data: one segment, two modes, both present, both stamped.</para>
///
/// <para><b>Why the STORED task class is read, and not the call argument.</b>
/// <see cref="Leaderboard"/>'s comparability rule makes only <see cref="ScoreSegment.Unclassified"/>
/// and a null workspace incomparable — so <c>"audit-import"</c>, the parameter default on
/// <see cref="WatcherHost.ImportAndScoreEpisodesFromAuditLog"/>, is a <b>comparable</b> class. An
/// episode that acquired its class by default does not surface as unranked; it ranks silently inside
/// the wrong cohort. Asserting the argument would prove only that the test passed a string.</para>
///
/// <para><b>Why a real SQLite store.</b> "One store" is the clause. An in-memory double would make
/// the sentence true by construction and prove nothing about the column the two paths share.</para>
/// </remarks>
public sealed class GovernedAndObservedShareOneCellTests : IDisposable
{
    /// <summary>
    /// The caller's own class — deliberately neither parameter default.
    /// </summary>
    /// <remarks>
    /// It differs from <c>"audit-import"</c> (<c>WatcherHost.ImportAndScoreEpisodesFromAuditLog</c>'s
    /// default) and from <see cref="ScoreSegment.Unclassified"/>
    /// (<c>ClosedEpisodeScoring.Run</c>'s), so a default reaching either path shows up as a stored
    /// value that is not this one.
    /// </remarks>
    private const string CallerChosenClass = "payments-extraction";

    private readonly string _dir = Path.Combine(
        Path.GetTempPath(), "aide-one-cell-" + Guid.NewGuid().ToString("n")[..8]);

    public GovernedAndObservedShareOneCellTests()
    {
        Directory.CreateDirectory(Path.Combine(_dir, "data"));
        Directory.CreateDirectory(Path.Combine(_dir, "coord"));
    }

    public void Dispose()
    {
        SqliteConnection.ClearAllPools();
        try
        {
            Directory.Delete(_dir, recursive: true);
        }
        catch (IOException)
        {
            // A temp file still held open is not a test failure.
        }

        GC.SuppressFinalize(this);
    }

    private WatcherHost OpenHost(TimeProvider time)
        => WatcherHost.Open(Path.Combine(_dir, "data"), Path.Combine(_dir, "coord"), time);

    private static GoalBlock Block() => new(
        "Move PaymentAggregate and handlers into Payments.Domain",
        "Payments.Domain builds; its tests green; no references from Ordering",
        "IPaymentGateway contract edits (serial spine)",
        Tier: "T1",
        FanOutCap: 0,
        Budget: new RunBudget(250, 600_000));

    private static LaneIdentity Lane() => new(
        LaneId: "lane-0001",
        AgentName: "payments-refactorer",
        RepositoryPath: "C:/repos/app",
        RepositoryDisplay: "app",
        WorktreeBranch: "agent/claude-code-lane-000",
        WorktreePath: "C:/repos/app-agent-claude-code-lane-000",
        Harness: "claude-code",
        Model: "sonnet");

    /// <summary>One audit entry with the three fields (AL5b) that make it an episode.</summary>
    private string WriteObservedAuditLog()
    {
        var path = Path.Combine(_dir, "audit-log.jsonl");
        File.WriteAllLines(path,
        [
            """{"id":"al-observed-1","session":"grok-build-sess","goal":"Extract the payment gateway port","done_when":"Ordering no longer references Payments internals","outcome":"success"}""",
        ]);
        return path;
    }

    /// <summary>The governed door: register, open from the block, close, score, stamp.</summary>
    private static string RunGovernedLane(WatcherHost host, TimeProvider time)
    {
        var session = new GovernedLaneSource(host.Ingest).Open(Lane(), Block());
        session.Close(EpisodeOutcome.Completed);
        LaneScoring.ScoreGoverned(host.Store, time, session.EpisodeId, CallerChosenClass);
        return session.EpisodeId;
    }

    /// <summary>
    /// THE CLAUSE. Two doors, one store, one cell, two modes — asserted positively, in both
    /// ingest orders, with no sleep anywhere.
    /// </summary>
    /// <remarks>
    /// <b>Both orders run</b> because "does not depend on ingest order" is a property, and a single
    /// fixed order cannot distinguish "order-independent" from "we happened to pick the one that
    /// works".
    /// </remarks>
    [Theory]
    [InlineData(true)]
    [InlineData(false)]
    public void OneGovernedAndOneObservedEpisodeShareOneCellAsTwoModes(bool governedFirst)
    {
        var time = TimeProvider.System;
        using var host = OpenHost(time);
        var auditLog = WriteObservedAuditLog();

        string governedId;
        IReadOnlyList<string> observedIds;

        if (governedFirst)
        {
            governedId = RunGovernedLane(host, time);
            observedIds = LaneScoring.ImportObserved(host, auditLog, TestWorkspaces.Repo, CallerChosenClass);
        }
        else
        {
            observedIds = LaneScoring.ImportObserved(host, auditLog, TestWorkspaces.Repo, CallerChosenClass);
            governedId = RunGovernedLane(host, time);
        }

        var observedId = Assert.Single(observedIds);

        // ---- one cell: every scored row in this store shares ONE segment ----
        var scored = host.Store.AllScoredEpisodes();
        Assert.Equal(2, scored.Count);
        var segment = Assert.Single(scored.Select(s => s.Segment).Distinct());

        // The cell is a cohort at all — an Unclassified or workspace-less cell ranks nowhere, and an
        // episode that ranks nowhere is not "scored" in the sense R4 means.
        Assert.True(segment.IsComparable, segment.IncomparableReason);

        // ---- two modes, both present, exactly two ----
        var modes = scored
            .Select(s => host.Store.FindEpisodeMode(s.EpisodeId))
            .Order(StringComparer.Ordinal)
            .ToArray();
        Assert.Equal(new[] { LaneMode.Governed, LaneMode.Observed }, modes);

        // ---- and each mode is on the episode that actually came through that door ----
        Assert.Equal(LaneMode.Governed, host.Store.FindEpisodeMode(governedId));
        Assert.Equal(LaneMode.Observed, host.Store.FindEpisodeMode(observedId));
    }

    /// <summary>
    /// Neither episode's task class arrived by parameter default — read from the STORE, not the call.
    /// </summary>
    /// <remarks>
    /// The two defaults are named as constants rather than described, so this test goes red the day
    /// either path stops requiring the caller to say what kind of work it was.
    /// </remarks>
    [Fact]
    public void NeitherStoredTaskClassCameFromAParameterDefault()
    {
        var time = TimeProvider.System;
        using var host = OpenHost(time);

        var governedId = RunGovernedLane(host, time);
        var observedId = Assert.Single(
            LaneScoring.ImportObserved(host, WriteObservedAuditLog(), TestWorkspaces.Repo, CallerChosenClass));

        foreach (var id in new[] { governedId, observedId })
        {
            var stored = host.Store.FindScoredEpisode(id)!.Segment.TaskClass;

            Assert.Equal(CallerChosenClass, stored);
            Assert.NotEqual(LaneScoring.AuditImportDefaultClass, stored);
            Assert.NotEqual(ScoreSegment.Unclassified, stored);
        }
    }

    /// <summary>
    /// The governed path <b>cannot</b> be called without a task class — the structural half of the
    /// clause above.
    /// </summary>
    /// <remarks>
    /// The stored-value assertion catches a default that is used; this catches one that is
    /// <i>added</i>. A future edit that gives <c>taskClass</c> a default would leave every existing
    /// caller passing a value and the test above green.
    /// </remarks>
    [Fact]
    public void TheGovernedScoringApiRequiresATaskClass()
    {
        foreach (var name in new[] { nameof(LaneScoring.ScoreGoverned), nameof(LaneScoring.ImportObserved) })
        {
            var parameter = Assert.Single(
                typeof(LaneScoring).GetMethod(name)!.GetParameters(), p => p.Name == "taskClass");

            Assert.False(parameter.HasDefaultValue, $"{name}.taskClass has a default value");
        }
    }

    /// <summary>
    /// Clause 1 alone: a governed episode reaches the store and is scored by the UNCHANGED
    /// <see cref="ScoringService"/>.
    /// </summary>
    /// <remarks>
    /// The scorecard's schema version comes from the scorer, so a scored row carrying
    /// <c>weave/1</c> is evidence the existing scorer ran — not a shape this path composed itself.
    /// </remarks>
    [Fact]
    public void AGovernedEpisodeIsScoredByTheUnchangedScoringService()
    {
        var time = TimeProvider.System;
        using var host = OpenHost(time);

        var id = RunGovernedLane(host, time);

        var scored = host.Store.FindScoredEpisode(id)!;
        Assert.Equal(ScoreSchema.Weave1Version, scored.SchemaVersion);
        Assert.Equal("claude-code", scored.Harness);
        Assert.Equal("sonnet", scored.Model);
        Assert.Equal(TestWorkspaces.Repo, scored.Segment.Workspace);
    }
}
