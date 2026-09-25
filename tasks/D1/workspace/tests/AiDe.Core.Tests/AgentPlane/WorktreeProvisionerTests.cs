using AiDe.Core.AgentPlane;
using AiDe.Core.Workbench;

namespace AiDe.Core.Tests.AgentPlane;

/// <summary>
/// The worktree provisioner — spec §6.4. It executes <see cref="AgentWorktree"/>'s plan, runs
/// <c>coord install</c> <b>inside</b> the new tree, and at lane close parks anything it cannot prove
/// is safe to delete.
/// </summary>
/// <remarks>
/// <para><b>Why "inside" is the load-bearing word.</b> <c>.git/config</c> is per-clone, and a
/// worktree has its own. An install run in the parent checkout leaves the new tree with no merge
/// drivers and no hooks — and nothing fails: the lane runs, and the first coordination conflict
/// resolves the wrong way. The assertion is therefore on the <i>working directory of the invocation</i>,
/// which is the only place that mistake is visible.</para>
///
/// <para><b>Why cleanup is the half that rots</b> (WT9-WT12). Deletion is opt-in, and a tree is
/// removable only when it is not carrying work that exists nowhere else. Anything else is reported,
/// never removed — the failure mode of a wrong PARK is a stale directory, and of a wrong REMOVE is
/// lost work.</para>
///
/// <para><b>DC-053 / WT13, recorded rather than assumed:</b> a worktree isolates the working tree and
/// the index, but <c>stash</c>, <c>bisect</c> and notes are repository-global. Nothing here may be
/// read as isolating those.</para>
/// </remarks>
public sealed class WorktreeProvisionerTests
{
    private const string RepositoryRoot = "/repos/app";

    /// <summary>A runner that records every invocation and answers from a caller-supplied rule.</summary>
    private sealed class RecordingRunner : IProcessRunner
    {
        public List<(string FileName, IReadOnlyList<string> Arguments, string WorkingDirectory)> Calls { get; } = [];

        public Func<string, IReadOnlyList<string>, ProcessResult> Respond { get; set; }
            = (_, _) => new ProcessResult(0, string.Empty, string.Empty);

        public ProcessResult Run(string fileName, IReadOnlyList<string> arguments, string workingDirectory)
        {
            Calls.Add((fileName, [.. arguments], workingDirectory));
            return Respond(fileName, arguments);
        }
    }

    private static (WorktreeProvisioner Provisioner, RecordingRunner Runner) New()
    {
        var runner = new RecordingRunner();
        return (new WorktreeProvisioner(runner), runner);
    }

    private static ProvisionedWorktree Tree()
        => new(RepositoryRoot, "agent/claude-code-lane-001", "/repos/app-agent-claude-code-lane-001", CoordInstalled: true);

    /// <summary>The branch is namespaced, and it is the plan's — not a second naming scheme.</summary>
    [Fact]
    public void TheWorktreeIsProvisionedOnTheNamespacedBranchAgentWorktreePlanned()
    {
        var (provisioner, runner) = New();

        var tree = provisioner.Provision(RepositoryRoot, "Claude Code", "lane-0001");

        var planned = AgentWorktree.For(RepositoryRoot, "Claude Code", "lane-0001")!;
        Assert.Equal(planned.Branch, tree.Branch);
        Assert.Equal(planned.Path, tree.Path);
        Assert.StartsWith("agent/", tree.Branch, StringComparison.Ordinal);

        var add = runner.Calls[0];
        Assert.Equal("git", add.FileName);
        Assert.Equal(["worktree", "add", "-b", planned.Branch, planned.Path], add.Arguments);
        Assert.Equal(RepositoryRoot, add.WorkingDirectory);
    }

    /// <summary>The clause: <c>coord install</c> runs in the NEW tree, never in the parent checkout.</summary>
    [Fact]
    public void CoordInstallRunsInsideTheNewTreeNotTheParent()
    {
        var (provisioner, runner) = New();

        var tree = provisioner.Provision(RepositoryRoot, "Claude Code", "lane-0001");

        var install = runner.Calls.Single(c => c.Arguments.Contains("install"));
        Assert.Equal(tree.Path, install.WorkingDirectory);
        Assert.NotEqual(RepositoryRoot, install.WorkingDirectory);
        Assert.True(tree.CoordInstalled);
    }

    /// <summary>A repository root no sibling can be derived from is refused, not silently shared.</summary>
    [Fact]
    public void ARootWithNoDerivableSiblingIsRefused()
    {
        var (provisioner, _) = New();

        var error = Assert.Throws<AgentPlaneException>(() => provisioner.Provision("   ", "Claude Code", "lane-0001"));

        Assert.Equal(AgentPlaneErrorCodes.WorktreeProvisionFailed, error.Code);
    }

    /// <summary>
    /// A failed <c>git worktree add</c> refuses, carrying git's own reason.
    /// </summary>
    /// <remarks>
    /// The App-layer path this moves into Core discarded stderr and announced a guess
    /// ("git could not create a worktree"), because it could always fall back to sharing the
    /// workspace. A governed lane has no such fallback: sharing the checkout would put two writers on
    /// one index, so the failure is fatal here and the reason must survive.
    /// </remarks>
    [Fact]
    public void AFailedGitWorktreeAddRefusesAndCarriesGitsReason()
    {
        var (provisioner, runner) = New();
        runner.Respond = (_, args) => args.Contains("worktree")
            ? new ProcessResult(128, string.Empty, "fatal: a branch named 'agent/claude-code-lane-001' already exists")
            : new ProcessResult(0, string.Empty, string.Empty);

        var error = Assert.Throws<AgentPlaneException>(() => provisioner.Provision(RepositoryRoot, "Claude Code", "lane-0001"));

        Assert.Equal(AgentPlaneErrorCodes.WorktreeProvisionFailed, error.Code);
        Assert.Contains("already exists", error.Message, StringComparison.Ordinal);
    }

    /// <summary>
    /// A failed <c>coord install</c> is recorded, never guessed and never fatal.
    /// </summary>
    /// <remarks>
    /// <c>coord</c> may simply not be on the path. Destroying a tree that git created because a
    /// nicety failed would be the destructive answer to a recoverable state; asserting it installed
    /// would be a false measurement. So the tree is returned with <c>CoordInstalled: false</c>,
    /// which reads as "not recorded" rather than as success.
    /// </remarks>
    [Fact]
    public void AFailedCoordInstallIsRecordedAndDoesNotDestroyTheTree()
    {
        var (provisioner, runner) = New();
        runner.Respond = (file, _) => file == "git"
            ? new ProcessResult(0, string.Empty, string.Empty)
            : new ProcessResult(9009, string.Empty, "'coord' is not recognized");

        var tree = provisioner.Provision(RepositoryRoot, "Claude Code", "lane-0001");

        Assert.False(tree.CoordInstalled);
        Assert.Contains(runner.Calls, c => c.Arguments.Contains("install") && c.WorkingDirectory == tree.Path);
    }

    // ---- Fail-safe cleanup (spec §6.4) ----

    /// <summary>
    /// Every state but "provably safe AND opted in" parks. The reason travels, because a parked tree
    /// with no cause is a directory nobody dares delete.
    /// </summary>
    [Theory]
    [InlineData(true, false, LaneClosure.Merged, true, "uncommitted")]
    [InlineData(false, true, LaneClosure.Merged, true, "nowhere else")]
    [InlineData(false, false, LaneClosure.Unresolved, true, "neither merged nor")]
    [InlineData(false, false, LaneClosure.Merged, false, "opt-in")]
    public void AnythingNotProvablySafeIsParkedAndReported(
        bool uncommitted, bool unpushed, LaneClosure closure, bool removeWhenSafe, string reasonFragment)
    {
        var (provisioner, runner) = New();

        var disposition = provisioner.Release(
            Tree(), closure, new WorktreeState(uncommitted, unpushed), removeWhenSafe);

        Assert.Equal(WorktreeDispositionKind.Parked, disposition.Kind);
        Assert.Contains(reasonFragment, disposition.Reason, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain(runner.Calls, c => c.Arguments.Contains("remove"));
    }

    /// <summary>The one path that deletes: merged or explicitly abandoned, clean, and opted in.</summary>
    [Theory]
    [InlineData(LaneClosure.Merged)]
    [InlineData(LaneClosure.Abandoned)]
    public void AProvablySafeTreeIsRemovedOnlyWhenRemovalWasAskedFor(LaneClosure closure)
    {
        var (provisioner, runner) = New();

        var disposition = provisioner.Release(Tree(), closure, new WorktreeState(false, false), removeWhenSafe: true);

        Assert.Equal(WorktreeDispositionKind.Removed, disposition.Kind);
        var remove = runner.Calls.Single(c => c.Arguments.Contains("remove"));
        Assert.Equal(["worktree", "remove", Tree().Path], remove.Arguments);
    }

    /// <summary>A removal git refuses parks instead of reporting a deletion that did not happen.</summary>
    [Fact]
    public void ARemovalGitRefusesParksInstead()
    {
        var (provisioner, runner) = New();
        runner.Respond = (_, args) => args.Contains("remove")
            ? new ProcessResult(128, string.Empty, "fatal: validation failed, cannot remove working tree")
            : new ProcessResult(0, string.Empty, string.Empty);

        var disposition = provisioner.Release(Tree(), LaneClosure.Merged, new WorktreeState(false, false), removeWhenSafe: true);

        Assert.Equal(WorktreeDispositionKind.Parked, disposition.Kind);
        Assert.Contains("cannot remove working tree", disposition.Reason, StringComparison.Ordinal);
    }

    /// <summary>
    /// Unpushed work cannot be proven absent, so it is assumed present.
    /// </summary>
    /// <remarks>
    /// <c>git rev-list @{u}..HEAD</c> fails outright on a branch with no upstream, which is exactly
    /// the state a freshly provisioned agent branch is in. Reading that failure as "nothing unpushed"
    /// would delete the one tree whose commits exist in no other place.
    /// </remarks>
    [Fact]
    public void AnUnanswerableUpstreamQueryCountsAsUnpushedWork()
    {
        var (provisioner, runner) = New();
        runner.Respond = (_, args) => args.Contains("rev-list")
            ? new ProcessResult(128, string.Empty, "fatal: no upstream configured for branch")
            : new ProcessResult(0, string.Empty, string.Empty);

        var state = provisioner.Inspect(Tree());

        Assert.True(state.HasUnpushedWork);
    }

    /// <summary>A clean tree with a pushed branch inspects as safe — the negative control.</summary>
    [Fact]
    public void ACleanAndFullyPushedTreeInspectsAsSafe()
    {
        var (provisioner, runner) = New();
        runner.Respond = (_, args) => args.Contains("rev-list")
            ? new ProcessResult(0, "0", string.Empty)
            : new ProcessResult(0, string.Empty, string.Empty);

        var state = provisioner.Inspect(Tree());

        Assert.False(state.HasUncommittedChanges);
        Assert.False(state.HasUnpushedWork);
    }

    /// <summary>Porcelain output means uncommitted work, whatever its shape.</summary>
    [Fact]
    public void PorcelainOutputMeansUncommittedWork()
    {
        var (provisioner, runner) = New();
        runner.Respond = (_, args) => args.Contains("status")
            ? new ProcessResult(0, " M src/Payments.cs\n?? scratch.txt", string.Empty)
            : new ProcessResult(0, "0", string.Empty);

        Assert.True(provisioner.Inspect(Tree()).HasUncommittedChanges);
    }
}
