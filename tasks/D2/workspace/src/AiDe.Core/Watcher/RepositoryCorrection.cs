namespace AiDe.Core.Watcher;

/// <summary>
/// Resolves the repository a checkout belongs to, when that checkout is a linked worktree.
/// </summary>
/// <remarks>
/// <para>An interface rather than a static so the correction is testable without creating real git
/// worktrees on disk, and so a caller that cannot see the filesystem (a future remote registrant)
/// can supply one that always answers "unknown" rather than having the check silently misfire.</para>
/// </remarks>
public interface IRepositoryLocator
{
    /// <summary>
    /// The repository <paramref name="checkoutPath"/> belongs to, or <c>null</c> when it is not a
    /// linked worktree, is already a repository root, or cannot be determined.
    /// </summary>
    /// <remarks>
    /// <b>Null covers three different situations deliberately</b>, because the caller treats them
    /// identically: in all three there is nothing to correct, and inventing a distinction here would
    /// invite a caller to act on one of them.
    /// </remarks>
    string? RepositoryFor(string checkoutPath);
}

/// <summary>
/// The filesystem answer: a linked worktree's <c>.git</c> is a FILE, a repository root's is a
/// directory.
/// </summary>
/// <remarks>
/// <para><b>Observed, not assumed.</b> In this repository's own trees:
/// <c>C:/Projects/ai-de/.git</c> is a directory, while a linked worktree's <c>.git</c> is a 74-byte
/// file reading <c>gitdir: C:/Projects/ai-de/.git/worktrees/&lt;name&gt;</c>. That pointer file is
/// the only thing distinguishing the two — nothing in the spelling of an absolute path does.</para>
///
/// <para><b>Why a file read and not <c>git rev-parse</c>.</b> Core does not shell out, this runs on
/// the ingest path where a process launch per registration would be a cost per agent, and the file
/// read answers the same question. The shell already uses <c>--git-common-dir</c> where it has a
/// process to spare; this is the same fact by a cheaper route.</para>
///
/// <para><b>Every failure answers "unknown".</b> A missing path, an unreadable file, a pointer that
/// does not match the expected shape — all return null, which the caller treats as nothing to
/// correct. A locator that guessed would reintroduce the split it exists to prevent, silently.</para>
/// </remarks>
public sealed class FileSystemRepositoryLocator : IRepositoryLocator
{
    /// <summary>The marker a linked worktree's <c>.git</c> file begins with.</summary>
    private const string GitDirPrefix = "gitdir:";

    /// <summary>The path segment git puts between the common dir and a worktree's own directory.</summary>
    private const string WorktreesSegment = "worktrees";

    public string? RepositoryFor(string checkoutPath)
    {
        if (string.IsNullOrWhiteSpace(checkoutPath))
        {
            return null;
        }

        try
        {
            // THE IDENTITY-TO-FILESYSTEM BOUNDARY, and it belongs where a path first meets the
            // filesystem rather than in each caller, because both callers legitimately hold an
            // IDENTITY: Apply below passes Repository.CanonicalPath, which Canonicalise spells with a
            // backslash on every platform on purpose so that one repository stays one repository
            // wherever it is read. On Linux "\tmp\x-lane" is a single filename, so File.Exists was
            // false for every linked worktree, this answered "nothing to correct", and the correction
            // silently never fired: the half of INV-0005 left standing after the pointer file's own
            // separators were fixed below.
            var checkout = RepositoryIdentity.ToFileSystemPath(checkoutPath);
            var dotGit = Path.Combine(checkout, ".git");

            // A repository root has a .git DIRECTORY, and a linked worktree has a .git FILE, so
            // "is not a file" already covers both the directory case and the absent case.
            //
            // This was written as `Directory.Exists(dotGit) || !File.Exists(dotGit)`, which reads
            // better and is EQUIVALENT — mutation replay reported the directory check as uncovered,
            // and it was uncovered because no behaviour can distinguish it. A branch no test can
            // ever redden is not defence in depth, it is a permanent false entry on the coverage
            // report that trains the next reader to ignore one.
            if (!File.Exists(dotGit))
            {
                return null;
            }

            var pointer = File.ReadAllText(dotGit).Trim();
            if (!pointer.StartsWith(GitDirPrefix, StringComparison.Ordinal))
            {
                return null;
            }

            // THE PLATFORM'S separator, not a backslash. Git writes the pointer with forward slashes
            // on every OS, so on Windows this still normalises to '\'. On Linux the old hardcoded
            // '\\' turned "/repo/.git/worktrees/x" into "\repo\.git\worktrees\x": the marker below
            // still matched, but Path.GetDirectoryName then saw a string containing no separator the
            // OS recognises, returned empty, and the locator reported "unknown repository" for every
            // linked worktree (INV-0005).
            var separator = Path.DirectorySeparatorChar;
            var gitDir = pointer[GitDirPrefix.Length..].Trim().Replace('/', separator);

            // gitDir is <repository>/.git/worktrees/<name>. Cut at the worktrees segment to get the
            // common dir, whose parent is the repository — the same primitive the shell derives from
            // --git-common-dir, so the two agree by construction rather than by coincidence.
            //
            // THE LAST OCCURRENCE, NOT THE FIRST. "~/worktrees/<project>" is a common way to keep
            // checkouts, and it puts a second worktrees segment in FRONT of the one git writes:
            // "/home/me/worktrees/proj/.git/worktrees/lane" cut at the FIRST match gives "/home/me"
            // as the common dir and "/home" as the repository, grouping every session in every such
            // checkout under one wrong repository. Wrong on Windows exactly as much as on Linux.
            //
            // The last match is right by CONSTRUCTION rather than by luck: git's <name> is one path
            // segment, so nothing after the real marker can hold another separator-terminated
            // "worktrees" - even a worktree named "worktrees" ends the string with no closing
            // separator, which is what
            // AWorktreeWhoseOWNNameIsWorktreesStillResolvesToItsRepository pins.
            //
            // AND THE PLATFORM'S OWN CASE RULE. OrdinalIgnoreCase on every platform resolved
            // "/repo/.GIT/WORKTREES/x" on Linux, where it is a DIFFERENT path that git could not
            // have written - a guess wearing a repository path. This comment already said "one
            // rule, not a second idiom" while spelling the ternary out a second time; it now reads
            // the shared member, which is the only spelling left in the assembly.
            var marker = separator + WorktreesSegment + separator;
            var cut = gitDir.LastIndexOf(marker, PathComparison.ForThisFileSystem);
            if (cut < 0)
            {
                return null;
            }

            var commonDir = gitDir[..cut];
            var repository = Path.GetDirectoryName(commonDir);

            return string.IsNullOrWhiteSpace(repository) ? null : repository;
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException
            or ArgumentException or NotSupportedException)
        {
            // Unknown, which is what the caller needs to hear. Never a guess.
            return null;
        }
    }
}

/// <summary>
/// The outcome of checking a registration's claimed repository: the binding to use, and what to tell
/// the registrant if it was not the one they sent.
/// </summary>
public sealed record RepositoryCorrectionResult(
    SessionBinding Binding, string? RepositorySent, string? RepositoryUsed, string? Reason)
{
    /// <summary>True when the binding differs from what the registrant claimed.</summary>
    public bool Corrected => Reason is not null;
}

/// <summary>
/// Corrects a registration that claims a <b>worktree</b> as its repository, and reports that it did.
/// </summary>
/// <remarks>
/// <para><b>The defect this closes.</b> <c>repo.path</c> is the grouping key in the fleet map, the
/// registration guard, the scoring segment, AND the message board partition. An externally
/// registering agent composes its own attributes; AI-DE's shell sends the repository, but nothing
/// enforced that anyone else does. An agent sending its worktree posts to a board nobody is on, and
/// — worse — every reply it makes to another session's thread is REFUSED by
/// <c>MessageBoard.RequireParent</c> as a cross-repository thread, with an error saying exactly that
/// to an agent which knows perfectly well it is in the same repository. It would read as the product
/// being broken.</para>
///
/// <para><b>Correct, do not reject.</b> Rejecting the registration was the other candidate and it
/// cannot work: detecting a worktree-shaped path and correcting it are the SAME filesystem read, so
/// a rejection can only fire in the case where a correction would have succeeded, and is silent in
/// the case — a path this machine cannot see — that motivated it. Rejection also removes the agent
/// from observation entirely to protect a segmentation key, taking the board with it, which is the
/// opposite of what the value is for.</para>
///
/// <para><b>But never silently.</b> Rewriting a registrant's own claim about itself without telling
/// them leaves them sending the wrong value forever, with the correction depending permanently on
/// our resolution staying right. The reason travels back to the agent, which is why this returns a
/// result rather than just a binding.</para>
///
/// <para><b>Not a guess.</b> The corrected value is read out of the registrant's own checkout — its
/// <c>.git</c> pointer file — so it is better evidence than the registrant supplied about itself,
/// not worse.</para>
/// </remarks>
public static class RepositoryCorrection
{
    /// <summary>The reason recorded when a worktree was resolved to its repository.</summary>
    public const string WorktreeResolvedReason =
        "the registered path is a linked worktree; its repository is used so the fleet map, the "
        + "message board and the score segment all agree with the other worktrees of that repository";

    /// <summary>
    /// Returns the binding to register, corrected when the claimed repository is a linked worktree.
    /// </summary>
    public static RepositoryCorrectionResult Apply(SessionBinding binding, IRepositoryLocator locator)
    {
        ArgumentNullException.ThrowIfNull(binding);
        ArgumentNullException.ThrowIfNull(locator);

        var claimed = binding.Repository.CanonicalPath;
        var actual = locator.RepositoryFor(claimed);

        if (actual is null)
        {
            return new RepositoryCorrectionResult(binding, null, null, null);
        }

        var corrected = new RepositoryIdentity(actual, Path.GetFileName(actual.TrimEnd('\\', '/')));

        // Canonicalisation runs on construction, so compare the canonical forms rather than the raw
        // strings: a worktree whose pointer resolves back to itself is not a correction.
        if (string.Equals(corrected.CanonicalPath, binding.Repository.CanonicalPath, StringComparison.Ordinal))
        {
            return new RepositoryCorrectionResult(binding, null, null, null);
        }

        // The worktree keeps its OWN path — it is still the checkout the session is in. Only the
        // repository changes, which is the whole point: one repository, several worktrees.
        var rebound = binding with
        {
            Repository = corrected,
            Worktree = binding.Worktree with { Repository = corrected },
        };

        return new RepositoryCorrectionResult(
            rebound, binding.Repository.CanonicalPath, corrected.CanonicalPath, WorktreeResolvedReason);
    }
}
