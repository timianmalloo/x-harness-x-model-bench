using AiDe.Core.Ipc;
using AiDe.Core.Upgrade;

namespace AiDe.Core.Tests;

/// <summary>
/// `P2-UPGRADE-01/02` — side-by-side builds, the repoint that commits, and the pairing after a
/// rollback.
/// </summary>
/// <remarks>
/// <para><b>Side-by-side is the thing that makes rollback possible.</b> Restoring a store from its
/// snapshot achieves nothing if the only binary on disk is the one that could not read it. Keeping
/// the previous directory is cheap; recreating it during an incident is not.</para>
/// </remarks>
public sealed class DaemonInstallationTests : IDisposable
{
    private readonly string _root = Path.Combine(
        Path.GetTempPath(), "aide-install", Guid.NewGuid().ToString("N"));

    public DaemonInstallationTests() => Directory.CreateDirectory(_root);

    /// <summary>A stand-in build directory, distinguishable by content.</summary>
    private string Build(string marker)
    {
        var directory = Path.Combine(_root, "builds", marker);
        Directory.CreateDirectory(Path.Combine(directory, "lib"));
        File.WriteAllText(Path.Combine(directory, "AiDe.Daemon.exe"), marker);
        File.WriteAllText(Path.Combine(directory, "lib", "AiDe.Core.dll"), $"{marker}-core");
        return directory;
    }

    private DaemonInstallation Installation() => new(Path.Combine(_root, "install"));

    // ---- installing side by side --------------------------------------------

    [Fact]
    public void BeforeAnythingIsInstalled_ThereIsNoCurrentVersion()
    {
        // Null rather than a guess: "nothing installed" and "the pointer names something gone" are
        // both states a supervisor must handle, and a plausible-looking default would send it to
        // launch a directory that does not exist.
        Assert.Null(Installation().Current);
        Assert.Empty(Installation().Installed);
    }

    [Fact]
    public void TwoVersions_Coexist()
    {
        var installation = Installation();

        installation.Install("1.0.0", Build("v1"));
        installation.Install("1.1.0", Build("v2"));

        Assert.Equal(["1.0.0", "1.1.0"], installation.Installed.Select(v => v.Version));
    }

    [Fact]
    public void AnInstalledBuild_KeepsItsSubdirectories()
    {
        // A flat copy would drop the runtime beside the executable, which fails only at launch.
        var installed = Installation().Install("1.0.0", Build("v1"));

        Assert.Equal("v1", File.ReadAllText(Path.Combine(installed.Directory, "AiDe.Daemon.exe")));
        Assert.Equal("v1-core", File.ReadAllText(Path.Combine(installed.Directory, "lib", "AiDe.Core.dll")));
    }

    [Fact]
    public void InstallingOverAnExistingVersion_RepairsItRatherThanFailing()
    {
        // An interrupted install leaves a partial directory. Refusing to overwrite would make that
        // partial state permanent and the version permanently unusable.
        var installation = Installation();
        installation.Install("1.0.0", Build("v1"));

        var repaired = installation.Install("1.0.0", Build("v1-repaired"));

        Assert.Equal("v1-repaired", File.ReadAllText(Path.Combine(repaired.Directory, "AiDe.Daemon.exe")));
    }

    [Fact]
    public void InstallingFromANonexistentBuild_IsRefused()
    {
        Assert.Throws<DirectoryNotFoundException>(
            () => Installation().Install("1.0.0", Path.Combine(_root, "not-a-build")));
    }

    // ---- the repoint is the commit ------------------------------------------

    [Fact]
    public void Repointing_MakesAVersionCurrent()
    {
        var installation = Installation();
        installation.Install("1.0.0", Build("v1"));

        installation.Repoint("1.0.0");

        Assert.Equal("1.0.0", installation.Current);
    }

    [Fact]
    public void InstallingDoesNotRepoint()
    {
        // Install and repoint are separate because everything between them is where an upgrade
        // decides whether to keep going. Combining them commits before the gate can refuse.
        var installation = Installation();
        installation.Install("1.0.0", Build("v1"));
        installation.Repoint("1.0.0");

        installation.Install("1.1.0", Build("v2"));

        Assert.Equal("1.0.0", installation.Current);
    }

    [Fact]
    public void RepointingToAVersionThatIsNotInstalled_IsRefused()
    {
        // A pointer naming a missing directory is a supervisor that cannot start anything, and it
        // would be discovered at the worst possible moment.
        var installation = Installation();
        installation.Install("1.0.0", Build("v1"));
        installation.Repoint("1.0.0");

        Assert.Throws<InvalidOperationException>(() => installation.Repoint("9.9.9"));

        // The refusal must leave the existing pointer intact. Clearing it on a bad repoint would
        // turn a rejected request into an uninstalled product.
        Assert.Equal("1.0.0", installation.Current);
    }

    [Fact]
    public void AfterAnUpgrade_ThePreviousBuildIsStillOnDisk()
    {
        // The whole point. Without it, a rollback restores a store no installed binary can read.
        var installation = Installation();
        installation.Install("1.0.0", Build("v1"));
        installation.Repoint("1.0.0");
        installation.Install("1.1.0", Build("v2"));
        installation.Repoint("1.1.0");

        Assert.Equal("1.1.0", installation.Current);
        Assert.Contains(installation.Installed, v => v.Version == "1.0.0");
    }

    [Fact]
    public void RollingBack_IsRepointingToThePreviousBuild()
    {
        var installation = Installation();
        installation.Install("1.0.0", Build("v1"));
        installation.Install("1.1.0", Build("v2"));
        installation.Repoint("1.1.0");

        installation.Repoint("1.0.0");

        Assert.Equal("1.0.0", installation.Current);
        Assert.Equal(
            "v1",
            File.ReadAllText(Path.Combine(installation.DirectoryFor("1.0.0"), "AiDe.Daemon.exe")));
    }

    // ---- pruning must not eat the running build -------------------------------

    [Fact]
    public void Pruning_KeepsTheNewestBuilds()
    {
        var installation = Installation();
        installation.Install("1.0.0", Build("v1"));
        installation.Install("1.1.0", Build("v2"));
        installation.Install("1.2.0", Build("v3"));
        installation.Repoint("1.2.0");

        var removed = installation.Prune(keep: 2);

        Assert.Equal(["1.0.0"], removed);
        Assert.Equal(["1.1.0", "1.2.0"], installation.Installed.Select(v => v.Version));
    }

    [Fact]
    public void Pruning_NeverRemovesTheCurrentBuild_EvenWhenItIsOld()
    {
        // This is the case a naive "keep the newest N" gets wrong, and it is not exotic: after a
        // rollback the current version IS an older one. Deleting it would remove the build that is
        // running, during the incident that caused the rollback.
        var installation = Installation();
        installation.Install("1.0.0", Build("v1"));
        installation.Install("1.1.0", Build("v2"));
        installation.Install("1.2.0", Build("v3"));
        installation.Repoint("1.0.0"); // rolled back

        var removed = installation.Prune(keep: 1);

        Assert.DoesNotContain("1.0.0", removed);
        Assert.Contains(installation.Installed, v => v.Version == "1.0.0");
        Assert.Equal("1.0.0", installation.Current);
    }

    // ---- P2-UPGRADE-02: the pairing after a rollback ---------------------------

    [Fact]
    public void AfterARollback_AShellOnTheNewMajor_StillMeetsADaemonOnThePreviousOne()
    {
        // The explicit post-rollback cell. Rolling the daemon back leaves a shell that was upgraded
        // alongside it — so the pair is mismatched by exactly one major, which is the case the dual
        // majors exist for. A single-version boundary would make every rollback a coordinated
        // restart of both, which is precisely what a rollback cannot depend on.
        var endpoint = new DaemonEndpoint("ws-1", new CapabilityRegistry(), _ => 1);
        var peer = new IpcPeer("S-1-5-21-owner", 1234, "conn-a");

        var newerShell = endpoint.OpenWorkspace(
            new IpcRequest(IpcVersion.Current, "open", "cmd-1", "ws-1", 1, null, null), peer);
        var olderShell = endpoint.OpenWorkspace(
            new IpcRequest(IpcVersion.Previous, "open", "cmd-2", "ws-1", 1, null, null), peer);

        Assert.True(newerShell.Ok, newerShell.Reason);
        Assert.True(olderShell.Ok, olderShell.Reason);
    }

    [Fact]
    public void APairingTwoMajorsApart_IsRejectedWithWhatIsSupported()
    {
        // Two majors apart is beyond what the pair covers, and the rejection has to say what IS
        // spoken — otherwise the bootstrap can only guess, and guessing across a version boundary is
        // how a downgrade loop starts.
        var endpoint = new DaemonEndpoint("ws-1", new CapabilityRegistry(), _ => 1);

        var response = endpoint.OpenWorkspace(
            new IpcRequest(IpcVersion.Previous - 1, "open", "cmd-1", "ws-1", 1, null, null),
            new IpcPeer("S-1-5-21-owner", 1234, "conn-a"));

        Assert.False(response.Ok);
        Assert.Equal(IpcErrorCodes.UnsupportedVersion, response.ErrorCode);
        Assert.Equal(IpcVersion.Supported, response.SupportedVersions);
    }

    public void Dispose()
    {
        try
        {
            Directory.Delete(_root, recursive: true);
        }
        catch (IOException)
        {
        }
    }
}
