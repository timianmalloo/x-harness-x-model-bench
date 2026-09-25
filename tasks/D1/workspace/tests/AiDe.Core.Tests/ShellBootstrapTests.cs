using System.Runtime.Versioning;
using AiDe.Core.Ipc;

namespace AiDe.Core.Tests;

/// <summary>
/// The shell reaching a daemon — starting one if it must.
/// </summary>
/// <remarks>
/// <para><b>This is the step that makes the process split the product rather than a demonstration.</b>
/// Everything beneath it was proven in tests while the shell still ran the core in-process, which is
/// the "built but inert" state this session has closed twice already.</para>
///
/// <para>Every case here starts a <b>real daemon process</b>. A fake would answer the question
/// "does the bootstrap call what I told it to" rather than "does a shell get a working daemon",
/// which is the only question worth asking of a launcher.</para>
/// </remarks>
[SupportedOSPlatform("windows")]
[Trait("Platform", "Windows")]
public sealed class ShellBootstrapTests : IDisposable
{
    private readonly List<string> _workspaces = [];

    private string FreshWorkspace()
    {
        var path = Path.Combine(Path.GetTempPath(), $"aide-bootstrap-{Guid.NewGuid():N}");
        Directory.CreateDirectory(path);
        _workspaces.Add(path);
        return path;
    }

    /// <summary>
    /// Where a daemon launched by these tests keeps its state: beside the temp workspace.
    /// </summary>
    /// <remarks>
    /// <para><b>Not the machine-wide default, which is what these tests used to leave behind.</b> The
    /// daemon derived its own directory under LocalAppData, so every run wrote into the user's real
    /// profile. MEASURED: one run of this suite left <b>12</b> workspace directories there, and 2,674
    /// had built up over four days — all but one an empty store from a test.</para>
    ///
    /// <para>A test that writes outside its own temp directory is not isolated, however green it is.
    /// The cleanup below removes the workspace and its state together, which was impossible while the
    /// state lived somewhere the test never named.</para>
    /// </remarks>
    private static string DataFor(string workspace) => Path.Combine(workspace, ".aide-data");

    /// <summary>
    /// The daemon built alongside THESE tests.
    /// </summary>
    /// <remarks>
    /// <para><b>The configuration comes from this assembly's own path</b>, not from whichever
    /// configuration directory happens to exist. It used to prefer Release when a Release directory
    /// was present — so a single <c>dotnet publish -c Release</c>, run for something else entirely,
    /// left these Debug tests launching a Release daemon built hours earlier. When the IPC protocol
    /// changed, three tests failed with <c>ipc.unsupported_version</c>, which is the protocol
    /// working correctly and the harness pointing at the wrong binary (DC-023: a gate running a
    /// stale build).</para>
    ///
    /// <para>The staleness check is the half that matters. Picking the right directory does not help
    /// if what is in it was built before the change under test, and "the daemon is old" is otherwise
    /// indistinguishable from "the daemon is broken".</para>
    /// </remarks>
    private static string DaemonPath()
    {
        var here = new DirectoryInfo(AppContext.BaseDirectory);
        var configuration =
            here.FullName.Contains($"{Path.DirectorySeparatorChar}Release{Path.DirectorySeparatorChar}",
                StringComparison.OrdinalIgnoreCase) ? "Release" : "Debug";

        var root = Path.GetFullPath(Path.Combine(
            AppContext.BaseDirectory, "..", "..", "..", "..", "..", "src", "AiDe.Daemon", "bin"));
        var candidate = Path.Combine(root, configuration, "net10.0-windows", "AiDe.Daemon.exe");

        Assert.True(
            File.Exists(candidate),
            $"the daemon was not built in {configuration}. Expected it at:\n  {candidate}\n"
            + "Build the solution rather than the test project alone.");

        // Not timestamps: a daemon that did not need rebuilding is OLDER than the tests and
        // perfectly current, so a time comparison reports staleness on every incremental build.
        // What actually matters is whether it carries the same AiDe.Core — the protocol, the
        // envelope and the operations all live there — and .NET builds deterministically, so equal
        // source gives equal bytes.
        var mine = Path.Combine(AppContext.BaseDirectory, "AiDe.Core.dll");
        var theirs = Path.Combine(Path.GetDirectoryName(candidate)!, "AiDe.Core.dll");

        if (File.Exists(mine) && File.Exists(theirs))
        {
            Assert.True(
                File.ReadAllBytes(mine).AsSpan().SequenceEqual(File.ReadAllBytes(theirs)),
                $"the {configuration} daemon at\n  {candidate}\n"
                + "was built against a different AiDe.Core than these tests. Launching it would test "
                + "a build that is not the one under test — which is how an IPC protocol change "
                + "looked like three broken tests (DC-023). Build the solution.");
        }

        return candidate;
    }

    // ---- launching -----------------------------------------------------------

    [Fact]
    public async Task WithNoDaemonRunning_OneIsLaunchedAndAnswers()
    {
        var workspace = FreshWorkspace();

        await using var client = await ShellBootstrap.ConnectOrLaunchAsync(
            workspace, DaemonPath(), CancellationToken.None, DataFor(workspace));

        // A connected client is not enough — it must answer, which means the daemon opened its
        // store and registered its operations, not merely accepted a pipe.
        var result = await client.FindAsync("", 10, CancellationToken.None);

        Assert.NotNull(result);
        Assert.True(client.Epoch > 0, "the handshake did not carry a usable epoch");
    }

    [Fact]
    public async Task ASecondShell_ReusesTheRunningDaemon_RatherThanStartingAnother()
    {
        // One daemon per workspace is the store's single-writer invariant. The bootstrap tries the
        // pipe before launching precisely so the common case costs nothing — and if it launched
        // first, the second shell would start a process whose only job is to discover it is
        // redundant and exit.
        var workspace = FreshWorkspace();

        await using var first = await ShellBootstrap.ConnectOrLaunchAsync(
            workspace, DaemonPath(), CancellationToken.None, DataFor(workspace));

        // Readiness barrier (DC-040): prove the first daemon is actually *serving* before the second
        // shell arrives, so reuse is measured against a ready daemon rather than a still-starting one.
        // Gating on an observed answer — not a fixed delay — is what makes this deterministic.
        Assert.NotNull(await first.FindAsync("", 1, CancellationToken.None));

        await using var second = await ShellBootstrap.ConnectOrLaunchAsync(
            workspace, DaemonPath(), CancellationToken.None, DataFor(workspace));

        // The reuse invariant is one logical daemon — one store, one epoch — per workspace, enforced
        // by WorkspaceLock. Epoch equality is the DETERMINISTIC, workspace-scoped proof of it: even
        // if a second shell momentarily launched a redundant process under load, that process loses
        // the workspace lock and exits, and the shell then connects to the incumbent — so the epoch
        // it sees is the incumbent's.
        //
        // This replaced a system-wide `AiDe.Daemon` process count (DC-040). That count was a category
        // error: the daemon deliberately outlives its client (the idle grace holds warm state through
        // a shell restart), so other tests' lingering daemons polluted a machine-global counter, and
        // an ordinary load-induced-then-lock-resolved redundant launch — harmless in production —
        // could false-fail it. The counter measured the machine; the invariant is per workspace.
        Assert.Equal(first.Epoch, second.Epoch);

        // Triangulate the workspace-scoped invariant: a third connect finds the same incumbent. first,
        // second and third overlap in scope, so the daemon cannot idle-shut-down between them, which
        // is what makes the three-way epoch equality a stable oracle rather than a timing gamble.
        await using var third = await ShellBootstrap.ConnectOrLaunchAsync(
            workspace, DaemonPath(), CancellationToken.None);

        Assert.Equal(first.Epoch, third.Epoch);
    }

    [Fact]
    public async Task TwoWorkspaces_GetTheirOwnDaemons()
    {
        // The lock and the pipe name are both per workspace; sharing a daemon across two would put
        // two stores behind one epoch.
        var one = FreshWorkspace();
        var two = FreshWorkspace();

        await using var alpha = await ShellBootstrap.ConnectOrLaunchAsync(
            one, DaemonPath(), CancellationToken.None, DataFor(one));
        await using var beta = await ShellBootstrap.ConnectOrLaunchAsync(
            two, DaemonPath(), CancellationToken.None, DataFor(two));

        var alphaResult = await alpha.FindAsync("", 5, CancellationToken.None);
        var betaResult = await beta.FindAsync("", 5, CancellationToken.None);

        Assert.NotNull(alphaResult);
        Assert.NotNull(betaResult);
    }

    // ---- failure is reported, never degraded ---------------------------------

    [Fact]
    public async Task WhenNoDaemonIsInstalled_TheFailureSaysSo()
    {
        // Distinguished from "the daemon would not start": a missing build is an installation
        // problem, and reporting it as a startup failure sends the investigation somewhere else.
        //
        // What must NOT happen is a silent fallback to running the core in this process. That would
        // work, and would abandon the trust boundary, the workspace lock and the epoch fence at the
        // moment they were most obviously needed.
        var missing = Path.Combine(Path.GetTempPath(), $"no-daemon-{Guid.NewGuid():N}.exe");

        var thrown = await Assert.ThrowsAsync<DaemonUnavailableException>(
            () => ShellBootstrap.ConnectOrLaunchAsync(
                FreshWorkspace(), missing, CancellationToken.None));

        Assert.Contains("installed", thrown.Message, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public async Task Cancellation_IsHonouredWhileWaitingForALaunchedDaemon()
    {
        // The launch deadline is thirty seconds. A shell closing during a cold start must not be
        // held open for the rest of it.
        using var cancellation = new CancellationTokenSource();
        await cancellation.CancelAsync();

        await Assert.ThrowsAnyAsync<OperationCanceledException>(
            () =>
            {
                var workspace = FreshWorkspace();
                return ShellBootstrap.ConnectOrLaunchAsync(
                    workspace, DaemonPath(), cancellation.Token, DataFor(workspace));
            });
    }

    [Fact]
    public async Task ADaemonToldWhereToKeepItsState_WritesNowhereElse()
    {
        // The control for DC-049. Before the daemon accepted `--data` it derived its own directory
        // under the user's LocalAppData and no caller could say otherwise, so every test that
        // launched one wrote into the real profile: 12 directories per run of this suite, 2,674
        // accumulated over four days, all but one an empty store belonging to a finished test.
        //
        // Nothing failed then and nothing would fail now — which is why the assertion has to be
        // about the directory that must stay untouched, not about the one that must be written.
        var machineWide = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "AiDe", "workspaces");

        var workspace = FreshWorkspace();

        // THIS daemon's directory, by name, rather than a snapshot of the whole folder.
        //
        // The first version compared the directory before and after. That is a machine-global
        // location, so anything else creating a workspace during the test failed it — and something
        // does: `dotnet test AiDe.sln` runs the App and Core assemblies concurrently, and the suite
        // is not alone on the machine. It failed once in a solution run and passed alone, which is
        // the signature of a control asserting about shared state rather than about its subject.
        var mine = Path.Combine(machineWide, IpcPipeName.ForWorkspace(workspace));

        await using (await ShellBootstrap.ConnectOrLaunchAsync(
            workspace, DaemonPath(), CancellationToken.None, DataFor(workspace)))
        {
            Assert.True(File.Exists(Path.Combine(DataFor(workspace), "workspace.db")),
                $"the daemon was told to keep its state in {DataFor(workspace)} and did not");
        }

        Assert.False(Directory.Exists(mine),
            $"launching a daemon with an explicit state directory still created {mine} — the daemon "
            + "wrote into the user's profile despite being told where to put its state");
    }

    public void Dispose()
    {
        foreach (var workspace in _workspaces)
        {
            try
            {
                Directory.Delete(workspace, recursive: true);
            }
            catch (IOException)
            {
            }
            catch (UnauthorizedAccessException)
            {
            }
        }
    }
}
