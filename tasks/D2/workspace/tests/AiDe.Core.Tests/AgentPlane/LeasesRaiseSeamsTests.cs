using System.Text.Json.Nodes;
using AiDe.Core.AgentPlane;
using AiDe.Core.Tests.Watcher;
using AiDe.Core.Watcher;

namespace AiDe.Core.Tests.AgentPlane;

/// <summary>
/// R4's third bullet: a governed lane's edit <b>outside</b> its lease raises a seam automatically,
/// and the run cannot close with an open one (outcome forced <c>Blocked</c>).
/// </summary>
/// <remarks>
/// <para><b>The negative control is the load-bearing test.</b> An implementation that raises a seam
/// on every edit satisfies "an edit outside the lease raises a seam" perfectly and is worse than
/// nothing: every run would close <c>Blocked</c>, and the steward would learn to resolve seams
/// without reading them. So <see cref="AnEditInsideTheLeaseRaisesNoSeam"/> is not a nicety.</para>
///
/// <para><b>Edits are recognized by the shape the corpus actually carries.</b> Spec §7.2 lists
/// <c>file.edit</c> among the v1 kinds, and <b>no Phase-1 producer emits it</b>: the captured frames
/// (<c>spikes/acp-subscription-lane/frames/write.jsonl</c>) show a file write arriving as a
/// <c>tool_call</c>/<c>tool_call_update</c> with <c>kind:"edit"</c> and a <c>locations[]</c> array —
/// which the mapper normalizes to <c>tool.call</c>/<c>tool.result</c>. Handling a kind with no
/// producer is what N1 forbade, so the monitor reads what exists.</para>
///
/// <para><b>One edit is one seam.</b> The same write appears in the corpus four times — a pending
/// <c>tool_call</c> with an EMPTY <c>locations</c> array, two <c>tool_call_update</c>s, and a
/// permission request. A monitor that raised per frame would report four seams for one violation,
/// and <c>seam_resolution_ratio</c> would then measure frames rather than seams.</para>
/// </remarks>
public sealed class LeasesRaiseSeamsTests
{
    private static readonly DateTimeOffset At = DateTimeOffset.UnixEpoch.AddSeconds(1_700_000_000);

    /// <summary>A root that need not exist: every check here is path arithmetic, not I/O.</summary>
    private static readonly string Root = Path.Combine(Path.GetTempPath(), "aide-lease-root");

    private readonly AcpRunEventMapper _mapper = new("run-1", "lane-1");

    private static Lease PaymentsOnly() => new(["src/Payments/**"]);

    private LeaseMonitor Monitor(Lease? lease = null) => new(lease ?? PaymentsOnly(), Root);

    /// <summary>One frame in the shape the corpus carries, through the real mapper.</summary>
    private RunEvent Edit(string toolCallId, string sessionUpdate, params string[] paths)
    {
        var locations = new JsonArray();
        foreach (var path in paths)
        {
            locations.Add(new JsonObject { ["path"] = path });
        }

        return Frame(toolCallId, sessionUpdate, "edit", locations);
    }

    private RunEvent Frame(string toolCallId, string sessionUpdate, string kind, JsonArray locations)
    {
        var frame = new JsonObject
        {
            ["jsonrpc"] = "2.0",
            ["method"] = "session/update",
            ["params"] = new JsonObject
            {
                ["sessionId"] = "sess-1",
                ["update"] = new JsonObject
                {
                    ["toolCallId"] = toolCallId,
                    ["sessionUpdate"] = sessionUpdate,
                    ["title"] = "Write",
                    ["kind"] = kind,
                    ["locations"] = locations,
                },
            },
        };

        return _mapper.Map(frame.ToJsonString(), At);
    }

    private static string Inside => Path.Combine(Root, "src", "Payments", "PaymentAggregate.cs");

    private static string Outside => Path.Combine(Root, "src", "Ordering", "OrderAggregate.cs");

    // ---- Clause 6: an edit outside the lease raises a seam ----

    /// <summary>THE CLAUSE: an edit outside the lease raises a seam that names the path.</summary>
    [Fact]
    public void AnEditOutsideTheLeaseRaisesASeam()
    {
        var monitor = Monitor();

        var raised = Assert.Single(monitor.Observe(Edit("tc-1", "tool_call_update", Outside)));

        Assert.Equal(Outside, raised.Path);
        Assert.Equal("tc-1", raised.ToolCallId);
        Assert.Equal("run-1", raised.RunId);
        Assert.Equal("lane-1", raised.AgentId);
        Assert.Single(monitor.OpenSeams);
    }

    /// <summary>An edit outside the worktree entirely is outside the lease — the strongest case.</summary>
    [Fact]
    public void AnEditOutsideTheWorktreeEntirelyRaisesASeam()
    {
        var monitor = Monitor();
        var elsewhere = Path.Combine(Path.GetTempPath(), "some-other-repo", "src", "Payments", "X.cs");

        var raised = Assert.Single(monitor.Observe(Edit("tc-9", "tool_call_update", elsewhere)));

        Assert.Equal(elsewhere, raised.Path);
    }

    // ---- Clause 7: THE NEGATIVE CONTROL ----

    /// <summary>
    /// An edit inside the lease raises NOTHING.
    /// </summary>
    /// <remarks>
    /// Without this, a monitor that seams on every edit passes every other test in this file.
    /// </remarks>
    [Fact]
    public void AnEditInsideTheLeaseRaisesNoSeam()
    {
        var monitor = Monitor();

        Assert.Empty(monitor.Observe(Edit("tc-2", "tool_call_update", Inside)));
        Assert.Empty(monitor.OpenSeams);
        Assert.Empty(monitor.AllSeams);
        Assert.Equal(1.0, monitor.SeamResolutionRatio);
    }

    /// <summary>A tool call that is not an edit raises nothing, wherever it points.</summary>
    [Fact]
    public void ANonEditToolCallRaisesNoSeamEvenOutsideTheLease()
    {
        var monitor = Monitor();
        var locations = new JsonArray { new JsonObject { ["path"] = Outside } };

        Assert.Empty(monitor.Observe(Frame("tc-3", "tool_call_update", "read", locations)));
        Assert.Empty(monitor.AllSeams);
    }

    /// <summary>
    /// The corpus's pending frame carries an EMPTY <c>locations</c> array; nothing is observed yet.
    /// </summary>
    /// <remarks>
    /// This is the frame a monitor that treated "no path" as "not covered" would seam on — turning
    /// the first announcement of every edit into a violation.
    /// </remarks>
    [Fact]
    public void APendingEditWithNoLocationYetRaisesNoSeam()
    {
        var monitor = Monitor();

        Assert.Empty(monitor.Observe(Edit("tc-4", "tool_call")));
        Assert.Empty(monitor.AllSeams);
    }

    /// <summary>One edit seen across four frames is one seam, not four.</summary>
    [Fact]
    public void TheSameEditSeenInSeveralFramesRaisesOneSeam()
    {
        var monitor = Monitor();

        monitor.Observe(Edit("tc-5", "tool_call"));
        monitor.Observe(Edit("tc-5", "tool_call_update", Outside));
        monitor.Observe(Edit("tc-5", "tool_call_update", Outside));

        Assert.Single(monitor.AllSeams);
        Assert.Equal(1, monitor.RaisedCount);
    }

    /// <summary>Two different edits outside the lease are two seams.</summary>
    [Fact]
    public void TwoDistinctEditsOutsideTheLeaseAreTwoSeams()
    {
        var monitor = Monitor();

        monitor.Observe(Edit("tc-6", "tool_call_update", Outside));
        monitor.Observe(Edit("tc-7", "tool_call_update", Path.Combine(Root, "docs", "readme.md")));

        Assert.Equal(2, monitor.AllSeams.Count);
    }

    /// <summary>One frame naming two paths, one covered and one not, raises exactly one seam.</summary>
    [Fact]
    public void OnlyTheUncoveredPathOfAMixedEditRaisesASeam()
    {
        var monitor = Monitor();

        var raised = Assert.Single(monitor.Observe(Edit("tc-8", "tool_call_update", Inside, Outside)));

        Assert.Equal(Outside, raised.Path);
    }

    // ---- Clause 8: an open seam forces Blocked ----

    /// <summary>THE CLAUSE: a run closing with an open seam is forced to <c>Blocked</c>.</summary>
    [Fact]
    public void ClosingWithAnOpenSeamForcesBlocked()
    {
        var (source, store, _) = Governed();
        var monitor = Monitor();
        monitor.Observe(Edit("tc-a", "tool_call_update", Outside));
        Assert.NotEqual(1.0, monitor.SeamResolutionRatio);

        var lane = new GovernedLane(source.Open(Lane(), Block()), Provisioner(), worktree: null, monitor);

        var teardown = lane.Close(
            EpisodeOutcome.Completed, LaneClosure.Merged, new WorktreeState(false, false), removeWorktreeWhenSafe: false);

        Assert.Equal(EpisodeOutcome.Blocked, teardown.Outcome);
        Assert.Equal(EpisodeOutcome.Blocked, Assert.Single(store.AllEpisodes()).Outcome);
    }

    /// <summary>Resolved, the ratio reaches 1.0 and the declared outcome stands.</summary>
    [Fact]
    public void AResolvedSeamRestoresTheRatioAndLetsTheRunCloseAsDeclared()
    {
        var (source, store, _) = Governed();
        var monitor = Monitor();
        var seam = Assert.Single(monitor.Observe(Edit("tc-b", "tool_call_update", Outside)));

        Assert.True(monitor.Resolve(seam.SeamId, "the steward admitted the scope change"));
        Assert.Equal(1.0, monitor.SeamResolutionRatio);
        Assert.Empty(monitor.OpenSeams);

        var lane = new GovernedLane(source.Open(Lane(), Block()), Provisioner(), worktree: null, monitor);

        var teardown = lane.Close(
            EpisodeOutcome.Completed, LaneClosure.Merged, new WorktreeState(false, false), removeWorktreeWhenSafe: false);

        Assert.Equal(EpisodeOutcome.Completed, teardown.Outcome);
        Assert.Equal(EpisodeOutcome.Completed, Assert.Single(store.AllEpisodes()).Outcome);
    }

    /// <summary>A run that raised no seam at all closes as declared — the ratio is 1.0, not 0/0.</summary>
    [Fact]
    public void ARunWithNoSeamsClosesAsDeclared()
    {
        var (source, store, _) = Governed();
        var monitor = Monitor();
        monitor.Observe(Edit("tc-c", "tool_call_update", Inside));

        var lane = new GovernedLane(source.Open(Lane(), Block()), Provisioner(), worktree: null, monitor);

        var teardown = lane.Close(
            EpisodeOutcome.Completed, LaneClosure.Merged, new WorktreeState(false, false), removeWorktreeWhenSafe: false);

        Assert.Equal(1.0, monitor.SeamResolutionRatio);
        Assert.Equal(EpisodeOutcome.Completed, teardown.Outcome);
        Assert.Equal(EpisodeOutcome.Completed, Assert.Single(store.AllEpisodes()).Outcome);
    }

    /// <summary>Resolving an id nobody raised changes nothing and says so.</summary>
    [Fact]
    public void ResolvingAnUnknownSeamRecordsNothing()
    {
        var monitor = Monitor();
        monitor.Observe(Edit("tc-d", "tool_call_update", Outside));

        Assert.False(monitor.Resolve("seam-that-does-not-exist", "ruling"));
        Assert.Single(monitor.OpenSeams);
    }

    // ---- fixtures ----

    private static GoalBlock Block() => new(
        "Move PaymentAggregate into Payments.Domain",
        "Payments.Domain builds and its tests are green",
        "IPaymentGateway contract edits",
        Tier: "T1",
        FanOutCap: 0,
        Budget: new RunBudget(250, 600_000));

    private static LaneIdentity Lane() => new(
        LaneId: "lane-1",
        AgentName: "payments-refactorer",
        RepositoryPath: "C:/repos/app",
        RepositoryDisplay: "app",
        WorktreeBranch: "agent/claude-code-lane-1",
        WorktreePath: "C:/repos/app-agent-claude-code-lane-1",
        Harness: "claude-code",
        Model: "sonnet");

    private static WorktreeProvisioner Provisioner() => new(new AlwaysSucceedsRunner());

    private static (GovernedLaneSource Source, InMemoryWatcherObservationStore Store, TimeProvider Time) Governed()
    {
        var store = new InMemoryWatcherObservationStore();
        var time = new FixedTimeProvider(DateTimeOffset.UnixEpoch.AddSeconds(1_700_000_000));
        var n = 0;
        var registrar = new TrustedRegistrar(
            store, new SequentialCapabilityFactory(), new FakeMonotonicClock(), () => $"session-{++n}");
        return (new GovernedLaneSource(new IngestHost(store, registrar, time)), store, time);
    }

    private sealed class AlwaysSucceedsRunner : IProcessRunner
    {
        public ProcessResult Run(string fileName, IReadOnlyList<string> arguments, string workingDirectory)
            => new(0, string.Empty, string.Empty);
    }
}
