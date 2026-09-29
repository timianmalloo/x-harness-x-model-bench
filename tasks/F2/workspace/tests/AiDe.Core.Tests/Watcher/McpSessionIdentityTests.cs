using AiDe.Core.Watcher;
using AiDe.Mcp;

namespace AiDe.Core.Tests.Watcher;

/// <summary>
/// Which session is calling — decided from two signals, and refused when they disagree.
/// </summary>
/// <remarks>
/// <para>The environment carries <c>AIDE_SESSION</c>, verified 2026-09-04 to be inherited in full by
/// a stdio MCP server (<c>spikes/mcp-stdio-environment</c>). That same spike found the second signal:
/// the server's working directory is the invocation directory, and an agent terminal runs in its own
/// worktree, whose path the store holds.</para>
///
/// <para><b>Why two.</b> Inheritance is exactly why a shell that outlives its terminal carries a dead
/// session id forward, and nothing in the variable says so. A board post attributed to the wrong
/// agent is the most damaging thing this surface can do — the board's whole purpose is that another
/// agent reads it and believes it.</para>
/// </remarks>
public sealed class McpSessionIdentityTests
{
    private static SessionRecord Session(string sessionId, string terminalId, string worktree) =>
        new(sessionId, new SessionGeneration(1), new SessionBinding(
            new RepositoryIdentity("C:/repos/app", "app"),
            new WorktreeIdentity(new RepositoryIdentity("C:/repos/app", "app"), "main", worktree),
            new TerminalIdentity(terminalId),
            new AgentIdentity("claude-code"),
            null, null, TrustClassification.Verified));

    private static readonly SessionRecord Alpha =
        Session("s-alpha", "agent:claude#alpha", @"C:\Projects\app-agent-alpha");

    private static readonly SessionRecord Beta =
        Session("s-beta", "agent:claude#beta", @"C:\Projects\app-agent-beta");

    private static readonly SessionRecord[] Both = [Alpha, Beta];

    // Platform=Windows: one theory case spells the path with a drive letter, which is not a path on Linux
    [Trait("Platform", "Windows")]
    [Fact]
    public void BothSignalsAgreeing_IsCorroborated()
    {
        var resolved = SessionIdentity.Resolve("agent:claude#alpha", @"C:\Projects\app-agent-alpha", Both);

        Assert.Equal(IdentitySource.Corroborated, resolved.Source);
        Assert.Equal("s-alpha", resolved.Session!.SessionId);
    }

    /// <summary>
    /// The signals naming DIFFERENT sessions is refused, not resolved in favour of either.
    /// </summary>
    /// <remarks>
    /// The case the second signal was added for. Preferring the environment would attribute alpha's
    /// post to whoever is in beta's tree; preferring the worktree would ignore what the agent was
    /// actually told it is. Neither is safe, so neither is chosen, and the message names both so an
    /// operator can see which is stale.
    /// </remarks>
    [Fact]
    public void SignalsNamingDifferentSessions_AreRefused()
    {
        var resolved = SessionIdentity.Resolve("agent:claude#alpha", @"C:\Projects\app-agent-beta", Both);

        Assert.Equal(IdentitySource.Conflict, resolved.Source);
        Assert.Null(resolved.Session);
        Assert.Contains("s-alpha", resolved.Reason);
        Assert.Contains("s-beta", resolved.Reason);
        Assert.Contains("Refusing rather than guessing", resolved.Reason);
    }

    /// <summary>The worktree alone identifies a session, so a sanitised environment still works.</summary>
    /// <remarks>
    /// This is what removes the design's dependence on environment inheritance being universal. A
    /// harness that strips the environment degrades to worktree identification rather than to
    /// nothing.
    /// </remarks>
    [Fact]
    public void WithNoEnvironment_TheWorktreeIdentifiesTheSession()
    {
        var resolved = SessionIdentity.Resolve(null, @"C:\Projects\app-agent-beta", Both);

        Assert.Equal(IdentitySource.Worktree, resolved.Source);
        Assert.Equal("s-beta", resolved.Session!.SessionId);
    }

    /// <summary>The environment alone works where the cwd is not a known worktree.</summary>
    [Fact]
    public void WithNoMatchingWorktree_TheEnvironmentStillIdentifies()
    {
        var resolved = SessionIdentity.Resolve("agent:claude#alpha", @"C:\somewhere\else", Both);

        Assert.Equal(IdentitySource.Environment, resolved.Source);
        Assert.Equal("s-alpha", resolved.Session!.SessionId);
    }

    /// <summary>Neither signal is a stated absence naming the remedy, not an error.</summary>
    [Fact]
    public void NeitherSignal_IsAStatedAbsence()
    {
        var resolved = SessionIdentity.Resolve(null, @"C:\somewhere\else", Both);

        Assert.Equal(IdentitySource.None, resolved.Source);
        Assert.Null(resolved.Session);
        Assert.Contains("not an AI-DE session", resolved.Reason);
        Assert.Contains("Terminal menu", resolved.Reason);
    }

    /// <summary>
    /// An id naming nothing is a DIFFERENT absence from no id, and says so.
    /// </summary>
    /// <remarks>
    /// The remedies differ: a stale shell versus a terminal AI-DE never launched. One message for
    /// both would send half the readers to the wrong fix.
    /// </remarks>
    [Fact]
    public void AnUnknownSessionIdNamesItsLikelyCause()
    {
        var resolved = SessionIdentity.Resolve("agent:claude#gone", @"C:\somewhere\else", Both);

        Assert.Equal(IdentitySource.None, resolved.Source);
        Assert.Contains("outlived the terminal", resolved.Reason);
        Assert.Contains("agent:claude#gone", resolved.Reason);
    }

    /// <summary>
    /// Two sessions sharing a worktree identify neither.
    /// </summary>
    /// <remarks>
    /// Ambiguity resolves to no answer rather than to the first match: picking one would attribute a
    /// post by a coin toss, and the whole point of the second signal is to stop exactly that.
    /// </remarks>
    [Fact]
    public void TwoSessionsInOneWorktreeIdentifyNeither()
    {
        var shared = @"C:\Projects\app";
        SessionRecord[] sessions =
        [
            Session("s-one", "agent:claude#one", shared),
            Session("s-two", "agent:claude#two", shared),
        ];

        var resolved = SessionIdentity.Resolve(null, shared, sessions);

        Assert.Equal(IdentitySource.None, resolved.Source);
        Assert.Null(resolved.Session);
    }

    /// <summary>
    /// Two spellings of one directory are one directory.
    /// </summary>
    /// <remarks>
    /// Git reports forward slashes where .NET reports backslashes, a trailing separator is
    /// indistinguishable from its absence, and Windows paths are case-insensitive — so a raw string
    /// comparison would make a worktree fail to match itself. The same normalisation
    /// <c>RepositoryIdentity</c> already applies, and for the same reason it was added there.
    /// </remarks>
    // Platform=Windows: one theory case spells the path with a drive letter, which is not a path on Linux
    [Trait("Platform", "Windows")]
    [Theory]
    [InlineData(@"C:\Projects\app-agent-alpha")]
    [InlineData("C:/Projects/app-agent-alpha")]
    [InlineData(@"C:\Projects\app-agent-alpha\")]
    [InlineData(@"c:\projects\APP-AGENT-ALPHA")]
    public void OneDirectorySpelledSeveralWaysIsOneDirectory(string spelling)
    {
        var resolved = SessionIdentity.Resolve(null, spelling, Both);

        Assert.Equal("s-alpha", resolved.Session?.SessionId);
    }

    /// <summary>The newest generation wins when a terminal has survived restarts.</summary>
    /// <remarks>
    /// A terminal that outlived several AI-DE restarts has one session id and several generations in
    /// the store (see <c>RestartDoesNotMultiplySessionsTests</c>); the newest is the one running now.
    /// </remarks>
    [Fact]
    public void TheNewestGenerationOfATerminalIsTheOneIdentified()
    {
        SessionRecord[] generations =
        [
            Alpha,
            Alpha with { Generation = new SessionGeneration(2) },
            Alpha with { Generation = new SessionGeneration(3) },
        ];

        var resolved = SessionIdentity.Resolve("agent:claude#alpha", null, generations);

        Assert.Equal(3, resolved.Session!.Generation.Value);
    }
}
