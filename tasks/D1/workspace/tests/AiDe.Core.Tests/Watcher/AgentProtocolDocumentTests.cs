using AiDe.Core.Watcher;

namespace AiDe.Core.Tests.Watcher;

/// <summary>
/// The document that tells an agent Loomkeeper exists.
/// </summary>
/// <remarks>
/// Two registered, trust-Verified agents were asked whether they knew about Loomkeeper on
/// 2026-09-03. Both correctly said no; one had grepped <c>.claude/</c>, <c>.github/</c>,
/// <c>docs/</c> and its own settings first. Every document explaining the protocol lived in AI-DE's
/// repository, and an agent reads the WORKSPACE's repository.
/// </remarks>
public sealed class AgentProtocolDocumentTests : IDisposable
{
    private readonly string _root = Path.Combine(
        Path.GetTempPath(), "aide-protocol-" + Guid.NewGuid().ToString("n")[..8]);

    public AgentProtocolDocumentTests() => Directory.CreateDirectory(_root);

    public void Dispose()
    {
        try { Directory.Delete(_root, recursive: true); } catch (IOException) { /* best effort */ }
    }

    [Fact]
    public void ItIsWrittenWhereTheProductOwnsTheDirectory()
    {
        var path = AgentProtocolDocument.WriteTo(_root);

        Assert.NotNull(path);
        Assert.Equal(Path.Combine(_root, ".aide", "AGENT-PROTOCOL.md"), path);
        Assert.True(File.Exists(path));
    }

    /// <summary>
    /// It never writes outside <c>.aide/</c>.
    /// </summary>
    /// <remarks>
    /// The workspace's own <c>CLAUDE.md</c> and <c>AGENTS.md</c> are AGENT-maintained, and the
    /// standing rule is that what an agent generates an agent updates. Writing there would be the
    /// product overwriting someone else's file — the exact failure the provenance rule exists to
    /// prevent, committed by the feature that most wants the reach.
    /// </remarks>
    [Fact]
    public void ItTouchesNothingOutsideItsOwnDirectory()
    {
        File.WriteAllText(Path.Combine(_root, "CLAUDE.md"), "the user's own file");
        File.WriteAllText(Path.Combine(_root, "AGENTS.md"), "also theirs");

        AgentProtocolDocument.WriteTo(_root);

        Assert.Equal("the user's own file", File.ReadAllText(Path.Combine(_root, "CLAUDE.md")));
        Assert.Equal("also theirs", File.ReadAllText(Path.Combine(_root, "AGENTS.md")));
        Assert.Equal(
            [".aide", "AGENTS.md", "CLAUDE.md"],
            Directory.GetFileSystemEntries(_root).Select(Path.GetFileName).Order());
    }

    /// <summary>
    /// Rewritten every time — this one the product owns outright.
    /// </summary>
    /// <remarks>
    /// The opposite of the Daydream record's <c>index.md</c>, which a person may add to and is
    /// therefore written once. This is reference material that must stay accurate: a human edit
    /// would be silently wrong the moment the protocol changed. Both rules coexist, and each file
    /// says in itself which it follows.
    /// </remarks>
    [Fact]
    public void ItIsRewrittenRatherThanPreserved()
    {
        var path = AgentProtocolDocument.WriteTo(_root)!;
        File.WriteAllText(path, "someone edited this");

        AgentProtocolDocument.WriteTo(_root);

        Assert.DoesNotContain("someone edited this", File.ReadAllText(path));
        Assert.Contains("do not hand-edit", File.ReadAllText(path));
    }

    /// <summary>No workspace is a stated absence, not an exception and not a guess at a path.</summary>
    [Fact]
    public void NoWorkspaceWritesNothingAndSaysSo()
    {
        Assert.Null(AgentProtocolDocument.WriteTo(null));
        Assert.Null(AgentProtocolDocument.WriteTo(""));
        Assert.Null(AgentProtocolDocument.WriteTo(Path.Combine(_root, "does-not-exist")));
    }

    /// <summary>
    /// The marker in the text agrees with the constant.
    /// </summary>
    /// <remarks>
    /// The document is a raw string rather than an interpolated one, because its JSON samples are
    /// full of <c>}}</c>. That makes the marker a literal, and a literal can drift from its
    /// constant — a provenance claim nothing checks. This is the check.
    /// </remarks>
    [Fact]
    public void TheDocumentCarriesItsOwnProvenanceMarker()
    {
        var content = AgentProtocolDocument.Content();

        Assert.Contains($"generated-by: {AgentProtocolDocument.GeneratedBy}", content);
        Assert.StartsWith("<!-- generated-by:", content);
    }

    /// <summary>
    /// It explains every channel an agent needs, including the ones nobody had been told about.
    /// </summary>
    /// <remarks>
    /// Derived from the measured failures rather than from a wish-list: the board and the model
    /// declaration were absent from every harness root except Copilot's, and "All 3012 sessions
    /// report no model" was the visible consequence. A document that omits one of these recreates
    /// the gap it was written to close.
    /// </remarks>
    [Theory]
    [InlineData("AIDE_CONTRACT_LOG")]
    [InlineData("gen_ai.request.model")]
    [InlineData("episode-open")]
    [InlineData("episode-close")]
    [InlineData("episode.artifacts")]
    [InlineData("board-post")]
    [InlineData("standing/")]
    [InlineData("board/board.json")]
    [InlineData("registration/")]
    public void ItNamesEveryChannelAnAgentNeeds(string token)
    {
        Assert.Contains(token, AgentProtocolDocument.Content());
    }

    /// <summary>
    /// It says an agent is ALREADY registered, because both agents assumed they were not.
    /// </summary>
    /// <remarks>
    /// The single most load-bearing sentence in the file. Both agents reported no awareness of
    /// registration while being registered and trust-Verified, so a document that only listed the
    /// events an agent may send would leave the same false belief in place.
    /// </remarks>
    [Fact]
    public void ItStatesThatRegistrationHasAlreadyHappened()
    {
        var content = AgentProtocolDocument.Content();

        Assert.Contains("already registered", content);
        Assert.Contains("before your process started", content);
    }

    /// <summary>The refusal that keeps evidence honest is stated, not just the happy path.</summary>
    [Fact]
    public void ItRefusesToOfferASelfAssessedVerdict()
    {
        Assert.Contains("no `episode.acceptance_met`", AgentProtocolDocument.Content());
    }
}
