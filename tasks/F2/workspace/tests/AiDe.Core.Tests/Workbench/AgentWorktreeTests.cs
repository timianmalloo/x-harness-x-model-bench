using AiDe.Core.Workbench;

namespace AiDe.Core.Tests.Workbench;

/// <summary>
/// Where an agent session's own git worktree goes, and what its branch is called.
/// </summary>
/// <remarks>
/// <para>Two agents in one checkout share an index, a HEAD and one set of build outputs, so one
/// agent's staging reaches into another's uncommitted work and nothing fails loudly. The naming and
/// placement are the part with judgement in them, so they are pure and tested here; running
/// <c>git worktree add</c> is mechanical and belongs with the caller that owns process launch.</para>
/// </remarks>
public sealed class AgentWorktreeTests
{
    // Platform=Windows: asserts against hardcoded @"C:\Projects" fixtures - a Windows path shape, by design
    [Trait("Platform", "Windows")]
    // Platform=Windows: asserts against hardcoded @"C:\Projects" fixtures - a Windows path shape, by design
    [Trait("Platform", "Windows")]
    // Platform=Windows: asserts against hardcoded @"C:\Projects" fixtures - a Windows path shape, by design
    [Trait("Platform", "Windows")]
    // Platform=Windows: asserts against hardcoded @"C:\Projects" fixtures - a Windows path shape, by design
    [Trait("Platform", "Windows")]
    // Platform=Windows: asserts against hardcoded @"C:\Projects" fixtures - a Windows path shape, by design
    [Trait("Platform", "Windows")]
    // Platform=Windows: asserts against hardcoded @"C:\Projects" fixtures - a Windows path shape, by design
    [Trait("Platform", "Windows")]
    [Fact]
    public void ItPlansASiblingOfTheRepository()
    {
        var plan = AgentWorktree.For(@"C:\Projects\TheTerrace", "claude-code", "a3f81c2ee9679dd2");

        Assert.NotNull(plan);
        Assert.Equal(@"C:\Projects\TheTerrace-agent-claude-code-a3f81c2e", plan!.Path);
        Assert.Equal("agent/claude-code-a3f81c2e", plan.Branch);
    }

    /// <summary>
    /// The tree is a SIBLING, never inside the repository.
    /// </summary>
    /// <remarks>
    /// Inside, it would need git-ignoring, would appear in every search and file watch, and would
    /// put one agent's build outputs inside the tree another agent is reading.
    /// </remarks>
    // Platform=Windows: asserts against hardcoded @"C:\Projects" fixtures - a Windows path shape, by design
    [Trait("Platform", "Windows")]
    [Fact]
    public void ThePlannedPathIsNotInsideTheRepository()
    {
        var root = @"C:\Projects\TheTerrace";

        var plan = AgentWorktree.For(root, "claude-code", "abcdef12")!;

        Assert.False(plan.Path.StartsWith(root + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase));
        Assert.Equal(@"C:\Projects", Path.GetDirectoryName(plan.Path));
    }

    /// <summary>
    /// The branch, the folder and the Sessions row all carry the SAME eight characters.
    /// </summary>
    /// <remarks>
    /// The whole reason the session row shows a short id: an operator looking at a branch in
    /// <c>git branch</c> can tell which session made it without a lookup. If these two drifted, the
    /// short id would be decoration.
    /// </remarks>
    // Platform=Windows: asserts against hardcoded @"C:\Projects" fixtures - a Windows path shape, by design
    [Trait("Platform", "Windows")]
    [Fact]
    public void TheShortIdTiesTheBranchTheFolderAndTheSessionRowTogether()
    {
        const string sessionId = "a3f81c2ee9679dd2";
        var plan = AgentWorktree.For(@"C:\Projects\TheTerrace", "claude-code", sessionId)!;

        var shortId = AgentWorktree.ShortId(sessionId);

        Assert.Equal("a3f81c2e", shortId);
        Assert.Contains(shortId, plan.Branch);
        Assert.Contains(shortId, plan.Path);
    }

    /// <summary>
    /// A harness name with spaces and capitals becomes something git and Windows both accept.
    /// </summary>
    /// <remarks>
    /// Lower-cased because half of git's ref rules are case-sensitive and half of Windows' path
    /// rules are not, and a name differing only by case between the two is a bug waiting for the
    /// first person who types it.
    /// </remarks>
    [Theory]
    [InlineData("Claude Code", "claude-code")]
    [InlineData("GitHub Copilot", "github-copilot")]
    [InlineData("pwsh", "pwsh")]
    [InlineData("", "agent")]
    [InlineData("!!!", "agent")]
    public void AHarnessNameBecomesASafeSlug(string harness, string expected)
        => Assert.Equal(expected, AgentWorktree.Slug(harness));

    /// <summary>
    /// The branch is namespaced, so it is obvious in <c>git branch</c> what made it.
    /// </summary>
    /// <remarks>
    /// A bare "claude-code-a3f81c2e" among a person's own branches reads as something they created
    /// and forgot. The prefix says the product made it and can be listed or deleted as a group.
    /// </remarks>
    // Platform=Windows: asserts against hardcoded @"C:\Projects" fixtures - a Windows path shape, by design
    [Trait("Platform", "Windows")]
    [Fact]
    public void TheBranchIsNamespacedUnderAgent()
    {
        var plan = AgentWorktree.For(@"C:\Projects\TheTerrace", "Claude Code", "abcdef12")!;

        Assert.StartsWith("agent/", plan.Branch);
    }

    /// <summary>
    /// A ref name never contains a character git refuses.
    /// </summary>
    /// <remarks>
    /// Asserted over hostile input rather than the happy path, because the session id is a machine
    /// value today and a `git worktree add` that fails on a stray character would fall back to the
    /// shared workspace — a silent loss of the isolation the feature exists for.
    /// </remarks>
    // Platform=Windows: asserts against hardcoded @"C:\Projects" fixtures - a Windows path shape, by design
    [Trait("Platform", "Windows")]
    [Theory]
    [InlineData("agent:claude#6d40a4")]
    [InlineData("term inal 1")]
    [InlineData("../../escape")]
    [InlineData("~^:?*[\\")]
    public void AHostileSessionIdStillYieldsAUsableBranchAndPath(string sessionId)
    {
        var plan = AgentWorktree.For(@"C:\Projects\TheTerrace", "claude-code", sessionId)!;

        Assert.DoesNotContain("..", plan.Branch);
        Assert.DoesNotContain("..", Path.GetFileName(plan.Path));
        Assert.All(
            new[] { ' ', '~', '^', ':', '?', '*', '[', '\\', '#' },
            c => Assert.DoesNotContain(c, plan.Branch["agent/".Length..]));
        Assert.Equal(@"C:\Projects", Path.GetDirectoryName(plan.Path));
    }

    /// <summary>No repository means no plan — a stated absence, not a guessed path.</summary>
    [Theory]
    [InlineData(null)]
    [InlineData("")]
    [InlineData("   ")]
    public void NoRepositoryYieldsNoPlan(string? root)
        => Assert.Null(AgentWorktree.For(root, "claude-code", "abcdef12"));

    /// <summary>
    /// A drive root yields no plan rather than a sibling of the drive.
    /// </summary>
    /// <remarks>
    /// A sibling of <c>C:\</c> would be outside anything the operator thinks of as their project,
    /// and creating directories at the filesystem root is not a thing a tool should do quietly.
    /// </remarks>
    [Fact]
    public void ADriveRootYieldsNoPlan()
        => Assert.Null(AgentWorktree.For(@"C:\", "claude-code", "abcdef12"));

    /// <summary>A trailing separator does not change the answer.</summary>
    // Platform=Windows: asserts against hardcoded @"C:\Projects" fixtures - a Windows path shape, by design
    [Trait("Platform", "Windows")]
    [Fact]
    public void ATrailingSeparatorIsIgnored()
    {
        var withSlash = AgentWorktree.For(@"C:\Projects\TheTerrace\", "claude-code", "abcdef12")!;
        var without = AgentWorktree.For(@"C:\Projects\TheTerrace", "claude-code", "abcdef12")!;

        Assert.Equal(without.Path, withSlash.Path);
        Assert.Equal(without.Branch, withSlash.Branch);
    }
}
