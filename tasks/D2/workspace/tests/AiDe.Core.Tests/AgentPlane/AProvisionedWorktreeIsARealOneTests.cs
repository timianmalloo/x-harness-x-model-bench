using AiDe.Core.AgentPlane;

namespace AiDe.Core.Tests.AgentPlane;

/// <summary>
/// The provisioner against REAL git, in a real temporary repository.
/// </summary>
/// <remarks>
/// <para><b>Why a fake-runner test is not enough here.</b> Every assertion in
/// <see cref="WorktreeProvisionerTests"/> is about the argument vector this code builds — which is
/// the right oracle for "did we run it in the right directory", and no oracle at all for "is that a
/// command git accepts". The two failures look identical from inside a fake: a mis-ordered
/// <c>-b</c>, a path git rejects, a branch name that is not a legal ref. This test is the only one
/// that can tell.</para>
///
/// <para><b>Not Windows-specific.</b> It builds its paths from <see cref="Path.GetTempPath"/> and
/// asserts nothing about path shape, so it carries no platform trait — git behaves the same on both.
/// </para>
///
/// <para><c>coord install</c> is expected to fail here (coord is not necessarily on the path), which
/// is itself the assertion that a coord failure does not cost the tree.</para>
/// </remarks>
public sealed class AProvisionedWorktreeIsARealOneTests : IDisposable
{
    private readonly string _root = Path.Combine(
        Path.GetTempPath(), "aide-worktree-" + Guid.NewGuid().ToString("n")[..8]);

    private readonly ProcessRunner _runner = new();

    public AProvisionedWorktreeIsARealOneTests()
    {
        Directory.CreateDirectory(_root);
        Git("init", "--initial-branch=main");
        Git("config", "user.email", "test@example.invalid");
        Git("config", "user.name", "Provisioner Test");
        File.WriteAllText(Path.Combine(_root, "README.md"), "fixture\n");
        Git("add", "README.md");
        Git("commit", "-m", "fixture");
    }

    [Fact]
    public void GitReallyCreatesTheTreeOnTheNamespacedBranchAndTheProvisionerFindsIt()
    {
        var provisioner = new WorktreeProvisioner(_runner);

        var tree = provisioner.Provision(_root, "Claude Code", "lane-0001");

        Assert.True(Directory.Exists(tree.Path), $"the provisioner reported {tree.Path}, which does not exist");
        Assert.StartsWith("agent/", tree.Branch, StringComparison.Ordinal);

        // The branch git actually checked out in that tree — read from the tree, not from our plan.
        var head = _runner.Run("git", ["rev-parse", "--abbrev-ref", "HEAD"], tree.Path);
        Assert.Equal(0, head.ExitCode);
        Assert.Equal(tree.Branch, head.StandardOutput.Trim());

        // A tree with nothing in it is clean, and its brand-new branch has no upstream — so the
        // fail-safe rule parks it even though the lane closed merged and removal was asked for.
        var state = provisioner.Inspect(tree);
        Assert.False(state.HasUncommittedChanges);
        Assert.True(state.HasUnpushedWork);
        Assert.Equal(
            WorktreeDispositionKind.Parked,
            provisioner.Release(tree, LaneClosure.Merged, state, removeWhenSafe: true).Kind);
    }

    public void Dispose()
    {
        // Best effort: the temp trees are siblings of _root, so both are swept.
        foreach (var directory in Directory.EnumerateDirectories(
            Path.GetDirectoryName(_root)!, Path.GetFileName(_root) + "*"))
        {
            try
            {
                DeleteReadOnly(directory);
            }
            catch (IOException)
            {
                // A temp directory a virus scanner still holds is not a test failure.
            }
            catch (UnauthorizedAccessException)
            {
            }
        }

        GC.SuppressFinalize(this);
    }

    /// <summary>Git marks objects read-only, which <see cref="Directory.Delete(string, bool)"/> refuses.</summary>
    private static void DeleteReadOnly(string directory)
    {
        foreach (var file in Directory.EnumerateFiles(directory, "*", SearchOption.AllDirectories))
        {
            File.SetAttributes(file, FileAttributes.Normal);
        }

        Directory.Delete(directory, recursive: true);
    }

    private void Git(params string[] arguments)
    {
        var result = _runner.Run("git", arguments, _root);
        Assert.True(result.ExitCode == 0, $"git {string.Join(' ', arguments)} failed: {result.StandardError}");
    }
}
