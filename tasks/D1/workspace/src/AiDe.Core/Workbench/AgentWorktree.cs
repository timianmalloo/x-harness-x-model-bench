using System.Text.RegularExpressions;

namespace AiDe.Core.Workbench;

/// <summary>
/// Where an agent session's own git worktree goes, and what its branch is called.
/// </summary>
/// <remarks>
/// <para><b>Why an agent gets its own tree.</b> Two agents in one checkout share an index, a HEAD
/// and one set of build outputs, so one agent's staging silently reaches into another's uncommitted
/// work and nothing fails loudly. Working in the primary checkout is the recorded exception, not the
/// default.</para>
///
/// <para><b>Pure, so the decisions are testable without git.</b> The names and the path are the part
/// with judgement in them; running <c>git worktree add</c> is mechanical and lives with the caller
/// that owns process launching.</para>
/// </remarks>
public static class AgentWorktree
{
    /// <summary>Everything about one agent session's tree, derived from its identity.</summary>
    /// <param name="Branch">The branch to create, namespaced so it is obvious in <c>git branch</c>.</param>
    /// <param name="Path">The directory the worktree goes in — a SIBLING of the repository.</param>
    public sealed record Plan(string Branch, string Path);

    /// <summary>
    /// The only characters allowed through — everything else collapses to a single hyphen.
    /// </summary>
    /// <remarks>
    /// <b>The dot is excluded deliberately.</b> An earlier version allowed it, and a session id of
    /// <c>../../escape</c> produced the branch <c>agent/claude-code-..-..-es</c>: <c>..</c> is
    /// invalid in a git ref AND is path traversal in the directory name, so the one input that
    /// mattered defeated both. A dot buys nothing here — harness slugs and session ids have no use
    /// for one — so the safe set is the small one. Found by a test written against hostile input
    /// rather than the happy path.
    /// </remarks>
    private static readonly Regex Unsafe = new(@"[^a-zA-Z0-9_-]+", RegexOptions.Compiled);

    /// <summary>
    /// Plans the worktree for one agent session, or <c>null</c> when there is no repository.
    /// </summary>
    /// <remarks>
    /// <para><b>A sibling directory, not a child.</b> Inside the repository the tree would need
    /// git-ignoring, would appear in every search and file watch, and would put one agent's build
    /// outputs inside the tree another agent is reading. A sibling is also what a person does by
    /// hand, so the result is recognisable rather than novel.</para>
    ///
    /// <para><b>The short id is the session's, so the branch, the folder and the Sessions row all
    /// carry the same eight characters.</b> That is the whole reason the row shows one: an operator
    /// looking at a branch in <c>git branch</c> can find which session made it without a lookup.</para>
    /// </remarks>
    public static Plan? For(string? repositoryRoot, string harness, string sessionId)
    {
        if (string.IsNullOrWhiteSpace(repositoryRoot))
        {
            return null;
        }

        var root = repositoryRoot.TrimEnd('\\', '/');
        var repoName = System.IO.Path.GetFileName(root);
        if (string.IsNullOrEmpty(repoName))
        {
            // A drive root has no name to build a sibling from, and a sibling of "C:\" would be
            // outside anything the operator thinks of as their project.
            return null;
        }

        var parent = System.IO.Path.GetDirectoryName(root);
        if (string.IsNullOrEmpty(parent))
        {
            return null;
        }

        var slug = Slug(harness);
        var shortId = ShortId(sessionId);

        return new Plan(
            $"agent/{slug}-{shortId}",
            System.IO.Path.Combine(parent, $"{repoName}-agent-{slug}-{shortId}"));
    }

    /// <summary>The eight characters the Sessions row also shows.</summary>
    public static string ShortId(string sessionId)
    {
        var cleaned = Unsafe.Replace(sessionId ?? string.Empty, "-").Trim('-');
        return cleaned.Length == 0 ? "session"
            : cleaned.Length <= 8 ? cleaned
            : cleaned[..8];
    }

    /// <summary>
    /// A harness name reduced to something a git ref and a directory both accept.
    /// </summary>
    /// <remarks>
    /// "Claude Code" becomes "claude-code". Lower-cased because half of git's ref rules are
    /// case-sensitive and half of Windows' path rules are not, and a name that differs only by case
    /// between the two is a bug waiting for the first person who types it.
    /// </remarks>
    public static string Slug(string harness)
    {
        var cleaned = Unsafe.Replace(harness ?? string.Empty, "-").Trim('-').ToLowerInvariant();
        return cleaned.Length == 0 ? "agent" : cleaned;
    }
}
