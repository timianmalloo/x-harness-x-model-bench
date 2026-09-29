using AiDe.Core.Watcher;

namespace AiDe.Core.Tests.Watcher;

/// <summary>
/// The workspace keys the scoring tests segment on.
/// </summary>
/// <remarks>
/// A shared constant rather than a literal per file: a leaderboard cell only forms when every episode
/// in it shares a segment, so two files spelling the same repository differently would silently
/// produce two cohorts and the cells would fall under the minimum for a reason that looked like
/// privacy. <see cref="Other"/> exists so the crossing can be asserted rather than assumed.
/// </remarks>
internal static class TestWorkspaces
{
    /// <summary>The repository the scoring tests key on.</summary>
    public static readonly WorkspaceKey Repo = WorkspaceKey.From("C:/repos/app")!;

    /// <summary>A second, unrelated repository - never comparable with <see cref="Repo"/>.</summary>
    public static readonly WorkspaceKey Other = WorkspaceKey.From("C:/repos/other")!;
}
