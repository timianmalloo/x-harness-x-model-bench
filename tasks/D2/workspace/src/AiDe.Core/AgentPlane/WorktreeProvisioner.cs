using System.Diagnostics;
using AiDe.Core.Workbench;

namespace AiDe.Core.AgentPlane;

/// <summary>What one child process did. <c>ExitCode</c> is the fact; the streams are the reason.</summary>
public sealed record ProcessResult(int ExitCode, string StandardOutput, string StandardError);

/// <summary>
/// The seam over launching a child process, so the plane's decisions are testable without a real
/// repository on disk.
/// </summary>
/// <remarks>
/// The thing worth testing about provisioning is <b>which directory a command ran in</b>, and that
/// is invisible to any test that only checks the result. This interface exists so that assertion can
/// be made; it is not an abstraction over process launching in general.
/// </remarks>
public interface IProcessRunner
{
    /// <summary>Runs a command to completion and returns what it did.</summary>
    ProcessResult Run(string fileName, IReadOnlyList<string> arguments, string workingDirectory);
}

/// <summary>The real runner: a child process, captured streams, a bounded wait.</summary>
/// <remarks>
/// <para><b>A timeout, not a hope.</b> A hung <c>git</c> or <c>coord</c> would otherwise hold a lane
/// spawn open forever. On timeout the tree is killed and the result reads as a failure with the
/// reason, which the provisioner then reports rather than guessing past.</para>
///
/// <para><b>Both streams are read before waiting</b> — a child that fills the stderr pipe while the
/// parent waits on exit deadlocks, which is the classic shape of this bug.</para>
///
/// <para><b>And the reads are bounded too</b> — the child's exit does not close a pipe another
/// process inherited, so a wait on the exit alone is a bound on the wrong thing
/// (<c>ProcessRunnerBoundsTheReadTests</c>).</para>
/// </remarks>
public sealed class ProcessRunner : IProcessRunner
{
    private readonly TimeSpan _timeout;

    /// <param name="timeout">How long any one command may take. Defaults to 60 seconds.</param>
    public ProcessRunner(TimeSpan? timeout = null) => _timeout = timeout ?? TimeSpan.FromSeconds(60);

    public ProcessResult Run(string fileName, IReadOnlyList<string> arguments, string workingDirectory)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(fileName);
        ArgumentNullException.ThrowIfNull(arguments);

        // UTF-8 on both streams (Ruling 87's class, DC-177): git writes paths and refs as UTF-8, and
        // a reader left on the console code page turns a non-ASCII branch or path into mojibake.
        var utf8 = new System.Text.UTF8Encoding(encoderShouldEmitUTF8Identifier: false);
        var info = new ProcessStartInfo(fileName)
        {
            WorkingDirectory = workingDirectory,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            StandardOutputEncoding = utf8,
            StandardErrorEncoding = utf8,
            UseShellExecute = false,
            CreateNoWindow = true,
        };

        foreach (var argument in arguments)
        {
            info.ArgumentList.Add(argument);
        }

        try
        {
            using var process = Process.Start(info);
            if (process is null)
            {
                return new ProcessResult(-1, string.Empty, $"'{fileName}' did not start");
            }

            var stdout = process.StandardOutput.ReadToEndAsync();
            var stderr = process.StandardError.ReadToEndAsync();

            if (!process.WaitForExit((int)_timeout.TotalMilliseconds))
            {
                try
                {
                    process.Kill(entireProcessTree: true);
                }
                catch (InvalidOperationException)
                {
                    // It exited between the wait timing out and the kill. Nothing to do.
                }

                return new ProcessResult(-1, string.Empty, $"'{fileName}' did not finish within {_timeout}");
            }

            // The exit is not the end of the streams. End-of-stream arrives when the LAST handle to
            // the pipe's write end closes, and a process that inherited that handle — a background
            // child the command started, anything created while the pipe was inheritable — keeps
            // the reader waiting for as long as it lives. Measured 2026-09-12: the App test host sat
            // 30 minutes in ReadToEnd after git had exited. So the read is bounded by the same
            // timeout, and a read that does not finish is reported as the reason it is.
            if (!Task.WaitAll([stdout, stderr], _timeout))
            {
                return new ProcessResult(
                    process.ExitCode,
                    stdout.IsCompletedSuccessfully ? stdout.Result : string.Empty,
                    $"'{fileName}' exited {process.ExitCode} but its output pipe was held open past {_timeout} by another process; the output is not recorded");
            }

            return new ProcessResult(process.ExitCode, stdout.Result, stderr.Result);
        }
        catch (System.ComponentModel.Win32Exception error)
        {
            // The command is not on the PATH. A reportable fact, not an exception the caller must
            // model separately — every other failure here already arrives as an exit code.
            return new ProcessResult(-1, string.Empty, error.Message);
        }
    }
}

/// <summary>A worktree the plane created for one lane.</summary>
/// <param name="RepositoryRoot">The checkout the tree was cut from.</param>
/// <param name="Branch">The namespaced branch, from <see cref="AgentWorktree"/>'s plan.</param>
/// <param name="Path">The sibling directory the tree lives in.</param>
/// <param name="CoordInstalled">
/// Whether <c>coord install</c> succeeded <b>in this tree</b>. False reads as "not recorded /
/// failed", never as "not needed".
/// </param>
public sealed record ProvisionedWorktree(string RepositoryRoot, string Branch, string Path, bool CoordInstalled);

/// <summary>What a tree is carrying — the two facts that make a deletion unsafe.</summary>
/// <param name="HasUncommittedChanges">Working-tree or index changes that exist only here.</param>
/// <param name="HasUnpushedWork">Commits that exist nowhere else, <b>or an upstream that could not be asked</b>.</param>
public sealed record WorktreeState(bool HasUncommittedChanges, bool HasUnpushedWork);

/// <summary>How the lane ended, as far as anyone declared.</summary>
public enum LaneClosure
{
    /// <summary>The work reached the target branch.</summary>
    Merged,

    /// <summary>Someone explicitly abandoned it. A declaration, never inferred from a crash.</summary>
    Abandoned,

    /// <summary>Anything else — including every kill, crash and timeout.</summary>
    Unresolved,
}

/// <summary>What happened to a tree at lane close.</summary>
public enum WorktreeDispositionKind
{
    /// <summary>Deleted, because it was provably safe and removal was asked for.</summary>
    Removed,

    /// <summary>Kept and reported. The default for everything else.</summary>
    Parked,
}

/// <summary>A disposition and the reason it was reached. A parked tree with no cause is one nobody dares delete.</summary>
public sealed record WorktreeDisposition(WorktreeDispositionKind Kind, string Path, string Reason);

/// <summary>
/// Provisions and releases a lane's worktree — spec §6.4.
/// </summary>
/// <remarks>
/// <para><b>Reuse, recorded.</b> The naming and placement decisions are
/// <see cref="AgentWorktree.For"/>'s and are not re-derived here; this type is the execution half
/// that <c>WorkbenchShell.ProvisionAgentWorktree</c> held, moved into Core so a lane can be
/// provisioned with no App present. The one deliberate behavioural difference: the shell could
/// always fall back to sharing the workspace and therefore swallowed git's stderr, while a governed
/// lane has no such fallback — sharing the checkout would put two writers on one index — so a
/// failure here is fatal and carries git's own reason.</para>
///
/// <para><b><c>coord install</c> runs inside the new tree.</b> <c>.git/config</c> is per-clone and a
/// worktree has its own, so an install in the parent leaves the new tree with no merge drivers and
/// no hooks — and nothing fails: the lane runs, and the first coordination conflict resolves the
/// wrong way.</para>
///
/// <para><b>DC-053 / WT13:</b> a worktree isolates the working tree and the index. <c>stash</c>,
/// <c>bisect</c> and notes are repository-global and are <i>not</i> isolated by anything here.</para>
///
/// <para><b>Cleanup is fail-safe and opt-in.</b> A wrong park costs a stale directory; a wrong
/// removal costs work that exists nowhere else. So every state but "provably safe AND asked for"
/// parks, and the reason travels with the disposition.</para>
/// </remarks>
public sealed class WorktreeProvisioner
{
    private readonly IProcessRunner _runner;
    private readonly string _coordCommand;

    /// <param name="runner">How child processes are launched.</param>
    /// <param name="coordCommand">
    /// The coordination CLI. Injectable because the pack's scripts are invoked differently per
    /// machine — <c>python3</c> is not present on Windows, where the shim is what resolves it — and
    /// a hard-coded name would make this fail on one platform and pass on the other.
    /// </param>
    public WorktreeProvisioner(IProcessRunner runner, string coordCommand = "coord")
    {
        ArgumentNullException.ThrowIfNull(runner);
        ArgumentException.ThrowIfNullOrWhiteSpace(coordCommand);
        _runner = runner;
        _coordCommand = coordCommand;
    }

    /// <summary>
    /// Cuts a worktree for one lane and installs the coordination layer inside it.
    /// </summary>
    /// <exception cref="AgentPlaneException">
    /// <see cref="AgentPlaneErrorCodes.WorktreeProvisionFailed"/> when no sibling location can be
    /// derived, or when git refuses. Fatal by design: a governed lane sharing the primary checkout
    /// is the isolation failure the tree exists to prevent.
    /// </exception>
    public ProvisionedWorktree Provision(string repositoryRoot, string harness, string sessionId)
    {
        var plan = AgentWorktree.For(repositoryRoot, harness, sessionId)
            ?? throw new AgentPlaneException(
                AgentPlaneErrorCodes.WorktreeProvisionFailed,
                $"no sibling worktree location can be derived from repository root '{repositoryRoot}'");

        var add = _runner.Run("git", ["worktree", "add", "-b", plan.Branch, plan.Path], repositoryRoot);
        if (add.ExitCode != 0)
        {
            throw new AgentPlaneException(
                AgentPlaneErrorCodes.WorktreeProvisionFailed,
                $"git could not create the worktree at '{plan.Path}' on '{plan.Branch}': "
                + Reason(add, "git exited " + add.ExitCode));
        }

        // INSIDE the new tree. .git/config is per-clone, so an install in the parent does not carry.
        var install = _runner.Run(_coordCommand, ["install"], plan.Path);

        // A coord that is not on the PATH must not cost a tree git already created: destroying it
        // would be the destructive answer to a recoverable state, and claiming it installed would be
        // a false measurement. False reads as "not recorded", which is what it is.
        return new ProvisionedWorktree(repositoryRoot, plan.Branch, plan.Path, install.ExitCode == 0);
    }

    /// <summary>
    /// Reads what the tree is carrying.
    /// </summary>
    /// <remarks>
    /// <b>An unanswerable upstream query counts as unpushed work.</b> <c>git rev-list @{u}..HEAD</c>
    /// fails outright on a branch with no upstream — which is exactly the state a freshly provisioned
    /// agent branch is in. Reading that failure as "nothing unpushed" would delete the one tree whose
    /// commits exist in no other place. Every measurement here degrades toward "unsafe", never toward
    /// a plausible clean answer.
    /// </remarks>
    public WorktreeState Inspect(ProvisionedWorktree tree)
    {
        ArgumentNullException.ThrowIfNull(tree);

        var status = _runner.Run("git", ["status", "--porcelain"], tree.Path);
        var dirty = status.ExitCode != 0 || !string.IsNullOrWhiteSpace(status.StandardOutput);

        var ahead = _runner.Run("git", ["rev-list", "--count", "@{u}..HEAD"], tree.Path);
        var unpushed = ahead.ExitCode != 0
            || !long.TryParse(ahead.StandardOutput.Trim(), out var count)
            || count > 0;

        return new WorktreeState(dirty, unpushed);
    }

    /// <summary>
    /// Decides what happens to the tree at lane close, and does it.
    /// </summary>
    /// <param name="tree">The tree.</param>
    /// <param name="closure">How the lane ended, as declared.</param>
    /// <param name="state">What the tree is carrying — from <see cref="Inspect"/> or from the caller.</param>
    /// <param name="removeWhenSafe">
    /// Deletion is <b>opt-in</b>. Absent this, a provably safe tree is still parked: the product does
    /// not delete a person's directory because a lane finished.
    /// </param>
    public WorktreeDisposition Release(
        ProvisionedWorktree tree, LaneClosure closure, WorktreeState state, bool removeWhenSafe)
    {
        ArgumentNullException.ThrowIfNull(tree);
        ArgumentNullException.ThrowIfNull(state);

        // First blocking reason wins, so the report names the thing to deal with rather than a list.
        if (state.HasUncommittedChanges)
        {
            return Park(tree, "it holds uncommitted changes, which exist nowhere else");
        }

        if (state.HasUnpushedWork)
        {
            return Park(tree, "it holds commits that exist nowhere else, or its upstream could not be asked");
        }

        if (closure is not (LaneClosure.Merged or LaneClosure.Abandoned))
        {
            return Park(tree, $"the lane closed {closure} — neither merged nor explicitly abandoned");
        }

        if (!removeWhenSafe)
        {
            return Park(tree, "it is safe to remove, but removal is opt-in and was not requested");
        }

        var remove = _runner.Run("git", ["worktree", "remove", tree.Path], tree.RepositoryRoot);
        return remove.ExitCode == 0
            ? new WorktreeDisposition(WorktreeDispositionKind.Removed, tree.Path, $"merged or abandoned, clean, and removal was requested ({closure})")
            : Park(tree, "git refused the removal: " + Reason(remove, "git exited " + remove.ExitCode));
    }

    private static WorktreeDisposition Park(ProvisionedWorktree tree, string reason)
        => new(WorktreeDispositionKind.Parked, tree.Path, reason);

    private static string Reason(ProcessResult result, string fallback)
    {
        var stderr = result.StandardError.Trim();
        return stderr.Length > 0 ? stderr : fallback;
    }
}
