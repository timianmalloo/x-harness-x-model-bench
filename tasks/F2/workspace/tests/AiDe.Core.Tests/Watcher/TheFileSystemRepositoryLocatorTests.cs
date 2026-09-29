using System.Diagnostics;
using AiDe.Core.Watcher;

namespace AiDe.Core.Tests.Watcher;

/// <summary>
/// The locator answers against a REAL git worktree, not a fabricated pointer file.
/// </summary>
/// <remarks>
/// <para><b>Why real git.</b> The whole correction rests on one empirical fact: a linked worktree's
/// <c>.git</c> is a FILE containing <c>gitdir: &lt;repo&gt;/.git/worktrees/&lt;name&gt;</c>, while a
/// repository root's is a directory. A fabricated pointer file would test this class's parser
/// against this class's author's belief about git, which is the failure mode the whole evening was
/// about. Building the worktree makes git the source of the fact.</para>
///
/// <para><b>The rest of the suite uses a stub</b>, deliberately: those tests are about what the
/// registration does with an answer, not about how the answer is obtained. This file is the only
/// place the filesystem claim is checked, which is why it must not be a fake.</para>
/// </remarks>
public sealed class TheFileSystemRepositoryLocatorTests
{
    [Fact]
    /// <summary>
    /// Both spellings a caller can hold: the checkout's own path, and its canonical IDENTITY.
    /// </summary>
    /// <remarks>
    /// The identity half is not decoration. It is the only spelling any production caller has -
    /// RepositoryCorrection.Apply passes Repository.CanonicalPath - and Canonicalise writes a
    /// backslash on every platform on purpose, so on Linux the argument arriving here is one
    /// filename with no separators in it. Asking only with the raw path exercised a spelling nothing
    /// in the product ever sends, which is how the locator stayed green on Linux while no linked
    /// worktree was ever corrected there.
    /// </remarks>
    public void ALinkedWorktreeResolvesToItsRepository_ByPathAndByIdentity()
    {
        var root = NewDirectory();
        var linked = root + "-linked";

        try
        {
            Git(root, "init", "-q", "-b", "main");
            Git(root, "config", "user.email", "test@example.invalid");
            Git(root, "config", "user.name", "test");
            File.WriteAllText(Path.Combine(root, "a.txt"), "a");
            Git(root, "add", "-A");
            Git(root, "commit", "-q", "-m", "init");
            Git(root, "worktree", "add", "-q", "-b", "linked", linked);

            var locator = new FileSystemRepositoryLocator();

            // If git did not produce the pointer file this test proves nothing — say which, rather
            // than failing on the comparison with a message about paths.
            Assert.True(File.Exists(Path.Combine(linked, ".git")), "git did not write a .git pointer FILE in the worktree");
            Assert.True(Directory.Exists(Path.Combine(root, ".git")), "the primary checkout's .git is not a directory");

            var resolved = locator.RepositoryFor(linked);

            Assert.NotNull(resolved);
            Assert.Equal(
                new RepositoryIdentity(root, "x").CanonicalPath,
                new RepositoryIdentity(resolved!, "x").CanonicalPath);

            // The same worktree, asked for the way the product asks. Red on Linux without the
            // conversion at the boundary; it cannot redden on Windows, where an identity and a path
            // are the same string - which is the whole reason this went unseen for two commits.
            Assert.Equal(resolved, locator.RepositoryFor(new RepositoryIdentity(linked, "x").CanonicalPath));
        }
        finally
        {
            Delete(linked);
            Delete(root);
        }
    }

    [Fact]
    public void ARepositoryRootAnswersNothingToCorrect()
    {
        var root = NewDirectory();

        try
        {
            Git(root, "init", "-q", "-b", "main");

            // Null means "nothing to correct", which is exactly right for a repository root. It is
            // the same answer as "cannot tell", and the caller treats them identically on purpose.
            Assert.Null(new FileSystemRepositoryLocator().RepositoryFor(root));
        }
        finally
        {
            Delete(root);
        }
    }

    [Theory]
    [InlineData("")]
    [InlineData("   ")]
    public void AnEmptyPathAnswersNothing(string path)
        => Assert.Null(new FileSystemRepositoryLocator().RepositoryFor(path));

    [Fact]
    public void APathThatDoesNotExistAnswersNothing_RatherThanThrowing()
    {
        // The registrant's filesystem may simply not be ours. Unknown is the honest answer and it
        // must not travel as an exception through the ingest path.
        var missing = Path.Combine(Path.GetTempPath(), "aide-absent-" + Guid.NewGuid().ToString("N")[..8]);

        Assert.Null(new FileSystemRepositoryLocator().RepositoryFor(missing));
    }

    [Fact]
    public void AGitFileThatIsNotAWorktreePointerAnswersNothing()
    {
        // A .git file exists but says something else. Guessing from a shape we do not recognise is
        // how the split gets reintroduced silently.
        var root = NewDirectory();

        try
        {
            File.WriteAllText(Path.Combine(root, ".git"), "something else entirely");

            Assert.Null(new FileSystemRepositoryLocator().RepositoryFor(root));
        }
        finally
        {
            Delete(root);
        }
    }

    [Fact]
    public void ARepositoryKeptUNDERADirectoryCalledWorktreesResolvesToITSELF()
    {
        // THE FIRST-OCCURRENCE DEFECT, and it needs no POSIX to show: the pointer simply contains
        // the marker twice.
        //
        // "~/worktrees/<project>" is a common way to keep checkouts, and it puts a literal
        // /worktrees/ segment in front of the .git/worktrees/ one that git writes. Cutting at the
        // FIRST match cuts at the user's own directory, so the repository resolved to the parent of
        // that - two levels above the project, on Windows exactly as much as on Linux. Every session
        // in every such checkout would then be grouped under one wrong repository.
        var container = NewDirectory();
        var root = Path.Combine(container, "worktrees", "proj");
        var linked = root + "-linked";

        try
        {
            Directory.CreateDirectory(root);
            Git(root, "init", "-q", "-b", "main");
            Git(root, "config", "user.email", "test@example.invalid");
            Git(root, "config", "user.name", "test");
            File.WriteAllText(Path.Combine(root, "a.txt"), "a");
            Git(root, "add", "-A");
            Git(root, "commit", "-q", "-m", "init");
            Git(root, "worktree", "add", "-q", "-b", "linked", linked);

            // If the pointer does not actually contain the marker twice this test proves nothing -
            // say which, rather than failing on a comparison about paths.
            var pointer = File.ReadAllText(Path.Combine(linked, ".git"));
            Assert.Contains("worktrees", pointer[..pointer.LastIndexOf("worktrees", StringComparison.Ordinal)], StringComparison.Ordinal);

            var resolved = new FileSystemRepositoryLocator().RepositoryFor(linked);

            Assert.NotNull(resolved);
            Assert.Equal(
                new RepositoryIdentity(root, "x").CanonicalPath,
                new RepositoryIdentity(resolved!, "x").CanonicalPath);
        }
        finally
        {
            Delete(linked);
            Delete(container);
        }
    }

    [Fact]
    public void AWorktreeWhoseOWNNameIsWorktreesStillResolvesToItsRepository()
    {
        // THE DISCONFIRMING HALF of the fix above, and the reason LastIndexOf is correct here rather
        // than merely less wrong. Git's <name> in .git/worktrees/<name> is ONE path segment, so the
        // marker's real occurrence is always the last one - even when the worktree is itself called
        // "worktrees", which is the only way a later occurrence could plausibly appear. The pointer
        // then ends ".git/worktrees/worktrees", whose trailing segment carries no closing separator
        // and so is not a match at all.
        //
        // Green before the fix and after it. It exists so that "the last match is the right one" is
        // a checked claim rather than a reading of git's source.
        var root = NewDirectory();
        var linked = Path.Combine(root + "-tree", "worktrees");

        try
        {
            Directory.CreateDirectory(Path.GetDirectoryName(linked)!);
            Git(root, "init", "-q", "-b", "main");
            Git(root, "config", "user.email", "test@example.invalid");
            Git(root, "config", "user.name", "test");
            File.WriteAllText(Path.Combine(root, "a.txt"), "a");
            Git(root, "add", "-A");
            Git(root, "commit", "-q", "-m", "init");
            Git(root, "worktree", "add", "-q", "-b", "linked", linked);

            var pointer = File.ReadAllText(Path.Combine(linked, ".git"));
            Assert.EndsWith("worktrees/worktrees", pointer.Trim(), StringComparison.Ordinal);

            var resolved = new FileSystemRepositoryLocator().RepositoryFor(linked);

            Assert.NotNull(resolved);
            Assert.Equal(
                new RepositoryIdentity(root, "x").CanonicalPath,
                new RepositoryIdentity(resolved!, "x").CanonicalPath);
        }
        finally
        {
            Delete(Path.GetDirectoryName(linked)!);
            Delete(root);
        }
    }

    [Fact]
    public void APointerSpelledInADIFFERENTCASEIsResolvedONLYWhereTheFilesystemSaysItIsTheSamePath()
    {
        // The marker match was OrdinalIgnoreCase on every platform. On Windows that is right -
        // ".GIT\WORKTREES\x" and ".git\worktrees\x" are one directory. On Linux they are two, and
        // folding makes the locator answer about a pointer git could not have written, which is a
        // guess wearing a repository path.
        //
        // NOT SKIPPED ON WINDOWS: there is a true and different answer to assert on each platform.
        // Only the Linux branch can redden; the Windows branch pins the answer a fix must not break
        // while correcting the other platform.
        //
        // A FABRICATED pointer, unlike the tests above, because git will not write this file - the
        // same reason AGitFileThatIsNotAWorktreePointerAnswersNothing fabricates one.
        var root = NewDirectory();

        try
        {
            File.WriteAllText(
                Path.Combine(root, ".git"),
                "gitdir: " + root.Replace(Path.DirectorySeparatorChar, '/') + "/.GIT/WORKTREES/lane");

            var expected = OperatingSystem.IsWindows()
                ? new RepositoryIdentity(root, "x").CanonicalPath
                : null;

            var resolved = new FileSystemRepositoryLocator().RepositoryFor(root);

            Assert.Equal(expected, resolved is null ? null : new RepositoryIdentity(resolved, "x").CanonicalPath);
        }
        finally
        {
            Delete(root);
        }
    }

    private static string NewDirectory()
    {
        var path = Path.Combine(Path.GetTempPath(), "aide-loc-" + Guid.NewGuid().ToString("N")[..8]);
        Directory.CreateDirectory(path);
        return path;
    }

    private static void Delete(string path)
    {
        try
        {
            if (!Directory.Exists(path))
            {
                return;
            }

            // git marks objects read-only; a plain recursive delete refuses on Windows.
            foreach (var file in Directory.EnumerateFiles(path, "*", SearchOption.AllDirectories))
            {
                File.SetAttributes(file, FileAttributes.Normal);
            }

            Directory.Delete(path, recursive: true);
        }
        catch (IOException)
        {
            // A leaked temp directory is not worth failing a passing assertion over.
        }
        catch (UnauthorizedAccessException)
        {
        }
    }

    private static void Git(string workingDirectory, params string[] arguments)
    {
        var info = new ProcessStartInfo("git")
        {
            WorkingDirectory = workingDirectory,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
        };

        foreach (var argument in arguments)
        {
            info.ArgumentList.Add(argument);
        }

        using var process = Process.Start(info)
            ?? throw new InvalidOperationException("git could not be started; this test needs a real repository.");

        process.WaitForExit(30_000);

        if (process.ExitCode != 0)
        {
            throw new InvalidOperationException(
                $"git {string.Join(' ', arguments)} failed ({process.ExitCode}): {process.StandardError.ReadToEnd()}");
        }
    }
}
