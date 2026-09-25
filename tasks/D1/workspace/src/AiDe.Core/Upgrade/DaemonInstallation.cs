namespace AiDe.Core.Upgrade;

/// <summary>One daemon build on disk.</summary>
public sealed record InstalledVersion(string Version, string Directory);

/// <summary>
/// Side-by-side daemon builds, and the pointer that says which one runs.
/// </summary>
/// <remarks>
/// <para><b>Side-by-side is what makes rollback possible at all.</b> An installer that overwrote the
/// previous build would leave nothing to go back to: the store could be restored from its snapshot
/// and there would be no binary able to read it. Keeping the old directory is cheap; recreating it
/// after a failed upgrade means downloading a build during an incident.</para>
///
/// <para><b>Repointing is one small atomic write, and it is the commit point.</b> Everything before
/// it — unpacking, migrating, gating — is reversible by doing nothing. A pointer file replaced by
/// rename means a process reading it during an upgrade sees the old version or the new one, never a
/// partial name, and never a directory that is still being written.</para>
///
/// <para><b>Pruning never removes the current build or the one before it.</b> The previous build is
/// not history — it is the rollback target, and reclaiming its disk is trading an incident's
/// recovery path for a few megabytes.</para>
/// </remarks>
public sealed class DaemonInstallation(string root)
{
    private const string PointerFile = "current";

    /// <summary>Where builds live, one directory per version.</summary>
    public string VersionsDirectory { get; } = Path.Combine(root, "versions");

    private string PointerPath => Path.Combine(root, PointerFile);

    /// <summary>The version currently pointed at, or <c>null</c> before the first install.</summary>
    /// <remarks>
    /// Null rather than a guess. "Nothing is installed yet" and "the pointer names something that is
    /// gone" are both states a supervisor must handle, and inventing a plausible version here would
    /// send it to launch a directory that may not exist.
    /// </remarks>
    public string? Current
    {
        get
        {
            if (!File.Exists(PointerPath))
            {
                return null;
            }

            var version = File.ReadAllText(PointerPath).Trim();
            return string.IsNullOrEmpty(version) ? null : version;
        }
    }

    /// <summary>Every build on disk, newest name last.</summary>
    public IReadOnlyList<InstalledVersion> Installed =>
        Directory.Exists(VersionsDirectory)
            ? [.. Directory.EnumerateDirectories(VersionsDirectory)
                .Select(d => new InstalledVersion(Path.GetFileName(d), d))
                .OrderBy(v => v.Version, StringComparer.Ordinal)]
            : [];

    /// <summary>The directory a version lives in, whether or not it exists yet.</summary>
    public string DirectoryFor(string version) => Path.Combine(VersionsDirectory, version);

    /// <summary>
    /// Places a build beside the others. Does <b>not</b> make it current.
    /// </summary>
    /// <remarks>
    /// Installing and repointing are separate because everything between them is where an upgrade
    /// decides whether to keep going. A combined step would make the commit happen before the gate
    /// had a chance to refuse.
    /// </remarks>
    public InstalledVersion Install(string version, string sourceDirectory)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(version);
        ArgumentException.ThrowIfNullOrWhiteSpace(sourceDirectory);

        if (!Directory.Exists(sourceDirectory))
        {
            throw new DirectoryNotFoundException($"no build to install at '{sourceDirectory}'");
        }

        var target = DirectoryFor(version);
        Directory.CreateDirectory(target);

        foreach (var file in Directory.EnumerateFiles(sourceDirectory, "*", SearchOption.AllDirectories))
        {
            var relative = Path.GetRelativePath(sourceDirectory, file);
            var destination = Path.Combine(target, relative);
            Directory.CreateDirectory(Path.GetDirectoryName(destination)!);

            // Overwrite so re-installing the same version is a repair rather than a failure: a
            // half-copied build from an interrupted install must not be permanent.
            File.Copy(file, destination, overwrite: true);
        }

        return new InstalledVersion(version, target);
    }

    /// <summary>Makes <paramref name="version"/> the one that runs. The commit point.</summary>
    public void Repoint(string version)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(version);

        if (!Directory.Exists(DirectoryFor(version)))
        {
            // Refused rather than written: a pointer naming a directory that does not exist is a
            // supervisor that cannot start anything, discovered at the worst moment.
            throw new InvalidOperationException(
                $"version '{version}' is not installed, so it cannot be made current");
        }

        Directory.CreateDirectory(root);

        var temporary = PointerPath + ".tmp";
        File.WriteAllText(temporary, version);
        File.Move(temporary, PointerPath, overwrite: true);
    }

    /// <summary>
    /// Removes old builds, keeping the newest <paramref name="keep"/> plus whatever is current.
    /// </summary>
    /// <remarks>
    /// The current build is protected explicitly rather than by relying on it being among the
    /// newest: after a rollback the current version is an <i>older</i> one, which is precisely when
    /// a naive "keep the newest N" would delete the build that is running.
    /// </remarks>
    public IReadOnlyList<string> Prune(int keep)
    {
        ArgumentOutOfRangeException.ThrowIfLessThan(keep, 1);

        var current = Current;
        var all = Installed;
        var protectedVersions = all
            .TakeLast(keep)
            .Select(v => v.Version)
            .ToHashSet(StringComparer.Ordinal);

        if (current is not null)
        {
            protectedVersions.Add(current);
        }

        var removed = new List<string>();

        foreach (var version in all.Where(v => !protectedVersions.Contains(v.Version)))
        {
            try
            {
                Directory.Delete(version.Directory, recursive: true);
                removed.Add(version.Version);
            }
            catch (IOException)
            {
                // A build in use cannot be removed. Disk to reclaim later, not a failed prune.
            }
        }

        return removed;
    }
}
