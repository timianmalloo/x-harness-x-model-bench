using System.IO;

namespace AiDe.Core.Tests.Sessions;

/// <summary>
/// Repository files these tests read as evidence — the Addendum B spec and the audit log.
/// </summary>
/// <remarks>
/// <b>The same walk-up SiteRuleFixtureTests uses.</b> A test that reads a committed document has to
/// find the repository from the test binary's directory; the solution file is the marker that
/// already works from every build output layout.
/// </remarks>
internal static class RepoFiles
{
    internal static string Root()
    {
        var dir = new DirectoryInfo(AppContext.BaseDirectory);
        while (dir is not null && !File.Exists(Path.Combine(dir.FullName, "AiDe.sln")))
        {
            dir = dir.Parent;
        }

        Assert.NotNull(dir);
        return dir!.FullName;
    }

    internal static string AddendumBHtml()
        => File.ReadAllText(Path.Combine(
            Root(), "docs", "specs", "conductor", "ai-de-spec-addendum-b-prompt-templates.html"));

    internal static string AuditLogJsonl()
        => File.ReadAllText(Path.Combine(Root(), "docs", "audit", "audit-log.jsonl"));

    internal static string SourceFile(params string[] parts)
        => File.ReadAllText(Path.Combine(Root(), Path.Combine(parts)));
}
