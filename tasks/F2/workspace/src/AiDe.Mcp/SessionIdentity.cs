using AiDe.Core.Watcher;

namespace AiDe.Mcp;

/// <summary>How the server decided which session is calling, and on what evidence.</summary>
public enum IdentitySource
{
    /// <summary>Both signals agreed: the environment named a session and its worktree is our cwd.</summary>
    Corroborated,

    /// <summary>The environment named a live session; there was no worktree to cross-check against.</summary>
    Environment,

    /// <summary>No environment, but our cwd is exactly one session's worktree.</summary>
    Worktree,

    /// <summary>Nothing identified a session. Not an error — a state, and it is served as one.</summary>
    None,

    /// <summary>The two signals named DIFFERENT sessions. Refused rather than guessed.</summary>
    Conflict,
}

/// <summary>
/// The resolved caller, or the stated reason there is none.
/// </summary>
/// <param name="Session">The session, when one was identified.</param>
/// <param name="Source">Which evidence identified it.</param>
/// <param name="Reason">A sentence for the agent when <see cref="Session"/> is null.</param>
public sealed record ResolvedIdentity(SessionRecord? Session, IdentitySource Source, string? Reason)
{
    public bool IsResolved => Session is not null;
}

/// <summary>
/// Decides which AI-DE session is calling, from two independent signals.
/// </summary>
/// <remarks>
/// <para><b>Two signals, because one of them goes stale silently.</b> The environment is inherited —
/// verified 2026-09-04, <c>spikes/mcp-stdio-environment</c>: a stdio server sees the launching
/// client's environment in full, so <c>AIDE_SESSION</c> arrives without configuration. But
/// inheritance is exactly why a shell that outlives its terminal carries a DEAD session id forward,
/// and nothing in the variable says so.</para>
///
/// <para>The same spike found the second signal: the server's working directory is the invocation
/// directory, and since <c>c235611</c> an agent terminal runs in its own git worktree — a path the
/// store already holds. So identity can be corroborated rather than merely claimed.</para>
///
/// <para><b>Disagreement is refused, not resolved.</b> A board post attributed to the wrong agent is
/// the most damaging thing this surface can do: the board's whole purpose is that another agent
/// reads it and believes it. When the two signals name different sessions the honest answer is
/// neither, with both named so the operator can see which is stale.</para>
///
/// <para>Pure but for the two ambient reads, which are injected — so the whole decision table is
/// testable without an environment or a filesystem.</para>
/// </remarks>
public static class SessionIdentity
{
    /// <summary>The variable AI-DE sets on every terminal it launches.</summary>
    public const string SessionVariable = "AIDE_SESSION";

    /// <summary>Resolves the caller from the environment, the working directory, and the store.</summary>
    public static ResolvedIdentity Resolve(
        string? environmentSessionId,
        string? workingDirectory,
        IReadOnlyList<SessionRecord> sessions)
    {
        ArgumentNullException.ThrowIfNull(sessions);

        var fromEnvironment = FindByExternalId(sessions, environmentSessionId);
        var fromWorktree = FindByWorktree(sessions, workingDirectory);

        // Both present and disagreeing. Named first because it is the case that must never be
        // silently resolved in favour of either.
        if (fromEnvironment is not null && fromWorktree is not null
            && !string.Equals(fromEnvironment.SessionId, fromWorktree.SessionId, StringComparison.Ordinal))
        {
            return new ResolvedIdentity(
                null,
                IdentitySource.Conflict,
                $"{SessionVariable} names session '{fromEnvironment.SessionId}' but this directory is "
                + $"session '{fromWorktree.SessionId}'s worktree. Refusing rather than guessing which "
                + "is right — the likeliest cause is a shell that outlived the terminal that set the "
                + "variable. Open a fresh terminal from AI-DE.");
        }

        if (fromEnvironment is not null)
        {
            return new ResolvedIdentity(
                fromEnvironment,
                fromWorktree is null ? IdentitySource.Environment : IdentitySource.Corroborated,
                null);
        }

        if (fromWorktree is not null)
        {
            return new ResolvedIdentity(fromWorktree, IdentitySource.Worktree, null);
        }

        // An id that names nothing is a different fact from no id at all, and the fix differs too:
        // one is a stale shell, the other is a terminal AI-DE did not launch.
        return new ResolvedIdentity(
            null,
            IdentitySource.None,
            string.IsNullOrWhiteSpace(environmentSessionId)
                ? $"No {SessionVariable} in the environment and this directory is not a known agent "
                  + "worktree, so this is not an AI-DE session. Open a terminal from AI-DE's Terminal "
                  + "menu and the variable is set for you."
                : $"{SessionVariable} is '{environmentSessionId}', which no session in this workspace "
                  + "matches. The likeliest cause is a shell that outlived the terminal that set it.");
    }

    /// <summary>
    /// Matches on the TERMINAL id, which is what <c>AIDE_SESSION</c> actually carries.
    /// </summary>
    /// <remarks>
    /// The shell sets <c>AIDE_SESSION</c> to the surface id, and the registrar mints its own internal
    /// session id — the two are different strings for the same thing, and the binding's terminal id
    /// is the durable bridge between them. Matching on the internal id would find nothing, which is
    /// the kind of near-miss that reads as "no session" rather than as a bug.
    /// </remarks>
    private static SessionRecord? FindByExternalId(IReadOnlyList<SessionRecord> sessions, string? externalId)
    {
        if (string.IsNullOrWhiteSpace(externalId))
        {
            return null;
        }

        // LAST match: a terminal that survived a restart has several generations in the store, and
        // the newest is the one now running.
        return sessions.LastOrDefault(s =>
            string.Equals(s.Binding.Terminal.TerminalId, externalId, StringComparison.Ordinal));
    }

    /// <summary>
    /// Matches a working directory to the session whose worktree it is.
    /// </summary>
    /// <remarks>
    /// <b>Exactly one, or none.</b> If two sessions record the same worktree path — two agents told
    /// to share a tree — the directory identifies neither, and picking one would attribute a post by
    /// a coin toss. Ambiguity resolves to no answer, which the caller renders as a stated absence.
    /// </remarks>
    private static SessionRecord? FindByWorktree(IReadOnlyList<SessionRecord> sessions, string? workingDirectory)
    {
        if (string.IsNullOrWhiteSpace(workingDirectory))
        {
            return null;
        }

        var normalised = Normalise(workingDirectory);
        var matches = sessions
            .Where(s => string.Equals(Normalise(s.Binding.Worktree.Path), normalised, StringComparison.Ordinal))
            .Select(s => s.SessionId)
            .Distinct(StringComparer.Ordinal)
            .ToList();

        return matches.Count == 1
            ? sessions.Last(s => string.Equals(s.SessionId, matches[0], StringComparison.Ordinal))
            : null;
    }

    /// <summary>
    /// One spelling of a path, so two spellings of one directory are one directory.
    /// </summary>
    /// <remarks>
    /// The same normalisation <see cref="RepositoryIdentity"/> already applies, and for the same
    /// reason it was added there: git reports forward slashes where .NET reports backslashes, a
    /// trailing separator is indistinguishable from its absence, and Windows paths are
    /// case-insensitive. Comparing raw strings would make a worktree fail to match itself.
    /// </remarks>
    private static string Normalise(string path)
    {
        if (string.IsNullOrWhiteSpace(path))
        {
            return string.Empty;
        }

        var normalised = path.Replace('/', '\\').TrimEnd('\\');
        return OperatingSystem.IsWindows() ? normalised.ToLowerInvariant() : normalised;
    }
}
