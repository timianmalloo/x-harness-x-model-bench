using System.Runtime.Versioning;
using AiDe.Core.Ipc;

namespace AiDe.Core.Tests;

/// <summary>
/// `P2-IPC-06` — one daemon per workspace, and the pipe name that follows from it.
/// </summary>
/// <remarks>
/// <para><b>What two daemons on one workspace would cost.</b> Both would work. Each would believe it
/// owned the epoch, both would write facts, and nothing above would notice — the damage appears
/// later as a store whose history has two authors and whose epoch fence means nothing. That is why
/// the lock is taken before anything is opened and why failing to take it is fatal rather than
/// degrading.</para>
/// </remarks>
[SupportedOSPlatform("windows")]
[Trait("Platform", "Windows")]
public sealed class WorkspaceLockTests
{
    private static string FreshWorkspace() =>
        Path.Combine(Path.GetTempPath(), $"aide-ws-{Guid.NewGuid():N}");

    // ---- the pipe name ------------------------------------------------------

    [Fact]
    public void ThePipeName_IsStableForOneWorkspace()
    {
        var workspace = FreshWorkspace();

        Assert.Equal(IpcPipeName.ForWorkspace(workspace), IpcPipeName.ForWorkspace(workspace));
    }

    [Fact]
    public void ThePipeName_IsCaseAndSeparatorInsensitive()
    {
        // Windows paths are case-insensitive and tolerate either separator. The same workspace
        // reached two ways must be ONE daemon, or the lock guards nothing — two processes would take
        // two different locks and both proceed.
        Assert.Equal(
            IpcPipeName.ForWorkspace(@"C:\Work\Repo"),
            IpcPipeName.ForWorkspace("c:/work/repo/"));
    }

    [Fact]
    public void DifferentWorkspaces_GetDifferentPipes()
    {
        Assert.NotEqual(
            IpcPipeName.ForWorkspace(@"C:\Work\alpha"),
            IpcPipeName.ForWorkspace(@"C:\Work\beta"));
    }

    [Fact]
    public void ThePipeName_DoesNotDiscloseTheWorkspacePath()
    {
        // Pipe names are enumerable by any process on the machine. A name built from the path would
        // tell anything that can list a directory which client's repository a user has open.
        var name = IpcPipeName.ForWorkspace(@"C:\clients\acme-holdings\secret-merger");

        Assert.DoesNotContain("acme", name, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("merger", name, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("clients", name, StringComparison.OrdinalIgnoreCase);
        Assert.StartsWith("aide.", name, StringComparison.Ordinal);
    }

    // ---- the lock -----------------------------------------------------------

    [Fact]
    public void TheFirstHolder_TakesTheLock()
    {
        var workspace = FreshWorkspace();

        Assert.True(WorkspaceLock.TryAcquire(workspace, out var held));
        using (held)
        {
            Assert.NotNull(held);
        }
    }

    [Fact]
    public void ASecondHolder_IsRefused_WhileTheFirstLives()
    {
        var workspace = FreshWorkspace();

        Assert.True(WorkspaceLock.TryAcquire(workspace, out var first));
        using (first)
        {
            Assert.False(WorkspaceLock.TryAcquire(workspace, out var second));
            Assert.Null(second);
        }
    }

    [Fact]
    public void ReleasingTheLock_LetsTheNextHolderTakeIt()
    {
        // Otherwise restarting a daemon would need a reboot, and the lock protecting the store would
        // be the thing that made the workspace unopenable.
        var workspace = FreshWorkspace();

        Assert.True(WorkspaceLock.TryAcquire(workspace, out var first));
        first!.Dispose();

        Assert.True(WorkspaceLock.TryAcquire(workspace, out var second));
        second!.Dispose();
    }

    [Fact]
    public void DifferentWorkspaces_DoNotContend()
    {
        var alpha = FreshWorkspace();
        var beta = FreshWorkspace();

        Assert.True(WorkspaceLock.TryAcquire(alpha, out var first));
        using (first)
        {
            Assert.True(WorkspaceLock.TryAcquire(beta, out var second));
            second!.Dispose();
        }
    }

    [Fact]
    public void DisposingTwice_IsHarmless()
    {
        var workspace = FreshWorkspace();
        Assert.True(WorkspaceLock.TryAcquire(workspace, out var held));

        held!.Dispose();
        held.Dispose();

        // Still releasable to the next holder, which is what proves the double dispose did no harm.
        Assert.True(WorkspaceLock.TryAcquire(workspace, out var next));
        next!.Dispose();
    }
}
