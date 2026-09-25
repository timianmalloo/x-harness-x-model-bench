using System.Text.Json.Nodes;
using AiDe.Core.AgentPlane;

namespace AiDe.Core.Tests.AgentPlane;

/// <summary>
/// R1 bullet 1's composition: the ACP session's <c>cwd</c> <b>is</b> the provisioned worktree, and
/// the branch <b>is</b> namespaced.
/// </summary>
/// <remarks>
/// <para><b>Neither half proves this.</b> <c>AcpLaneClientTests</c> asserts the client refuses a
/// relative <c>cwd</c> — which is true of any absolute path, including the wrong one.
/// <c>AProvisionedWorktreeIsARealOneTests</c> asserts git really made a tree on a namespaced branch —
/// which is true whether or not the lane ever runs there. A lane rooted in the primary checkout
/// passes both and is the exact isolation failure the worktree exists to prevent.</para>
///
/// <para><b>Real git, and the frame that actually went out.</b> The tree is cut by real git in a real
/// temporary repository, and the assertion reads the <c>session/new</c> frame the peer wrote to the
/// engine's stdin — not the argument the test passed in.</para>
///
/// <para><b>The branch is read back from the tree</b>, with <c>git rev-parse</c> inside it, so
/// "namespaced" is observed rather than planned.</para>
/// </remarks>
public sealed class TheAcpSessionRunsInTheProvisionedWorktreeTests : IDisposable
{
    private readonly string _root = Path.Combine(
        Path.GetTempPath(), "aide-lane-cwd-" + Guid.NewGuid().ToString("n")[..8]);

    private readonly ProcessRunner _runner = new();

    public TheAcpSessionRunsInTheProvisionedWorktreeTests()
    {
        Directory.CreateDirectory(_root);
        Git("init", "--initial-branch=main");
        Git("config", "user.email", "test@example.invalid");
        Git("config", "user.name", "Lane Cwd Test");
        File.WriteAllText(Path.Combine(_root, "README.md"), "fixture\n");
        Git("add", "README.md");
        Git("commit", "-m", "fixture");
    }

    [Fact]
    public async Task TheSessionOpensInTheProvisionedTreeOnANamespacedBranch()
    {
        var tree = new WorktreeProvisioner(_runner).Provision(_root, "Claude Code", "lane-0001");

        var input = new PushTextReader();
        var output = new RecordingTextWriter();
        var peer = new AcpPeer(input, output, new AcpRunEventMapper("run-1", "lane-0001"));
        var client = new AcpLaneClient(peer);

        var run = peer.RunAsync();

        var initialize = client.InitializeAsync();
        input.Push("""{"jsonrpc":"2.0","id":1,"result":{"protocolVersion":1,"authMethods":[]}}""" + "\n");
        await initialize;

        // The overload that takes the TREE, not a string: the composition is in the type, so a lane
        // cannot be rooted anywhere else by passing the wrong path.
        var newSession = client.NewSessionAsync(tree);
        input.Push("""{"jsonrpc":"2.0","id":2,"result":{"sessionId":"sess-1"}}""" + "\n");
        Assert.Equal("sess-1", await newSession);

        input.EndOfStream();
        await run;

        var sent = JsonNode.Parse(output.Lines[1].Line)!.AsObject();
        Assert.Equal("session/new", sent["method"]!.GetValue<string>());

        var cwd = sent["params"]!["cwd"]!.GetValue<string>();

        // (1) the cwd IS the provisioned tree — the same directory, and one that exists
        Assert.Equal(tree.Path, cwd);
        Assert.True(Path.IsPathRooted(cwd), $"session cwd '{cwd}' is not absolute");
        Assert.True(Directory.Exists(cwd), $"session cwd '{cwd}' does not exist");

        // (2) and it is NOT the primary checkout — the failure the tree exists to prevent
        Assert.NotEqual(
            Path.TrimEndingDirectorySeparator(Path.GetFullPath(_root)),
            Path.TrimEndingDirectorySeparator(Path.GetFullPath(cwd)));

        // (3) the branch checked out THERE is the namespaced one, read from the tree itself
        var head = _runner.Run("git", ["rev-parse", "--abbrev-ref", "HEAD"], cwd);
        Assert.Equal(0, head.ExitCode);
        Assert.Equal(tree.Branch, head.StandardOutput.Trim());
        Assert.StartsWith("agent/", head.StandardOutput.Trim(), StringComparison.Ordinal);
    }

    public void Dispose()
    {
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
