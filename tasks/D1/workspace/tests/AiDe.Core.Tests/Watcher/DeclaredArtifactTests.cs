using AiDe.Core.Watcher;

namespace AiDe.Core.Tests.Watcher;

/// <summary>
/// The evidence channel: an agent names a file, and the product records what it named.
/// </summary>
/// <remarks>
/// <para><b>The gap this closes.</b> <c>ClosedEpisodeScoring</c> passed <c>HasProofPack: false</c>
/// as a literal, which collapsed two states wanting opposite responses — <i>we looked and there was
/// none</i> (about this episode) and <i>there is nowhere to look</i> (about the product). It was
/// always the second, spelled as the first, so a scorecard made a claim about an agent when the true
/// claim was about a missing channel.</para>
///
/// <para><b>Why this is admitted where <c>acceptance_met</c> is refused.</b> An agent cannot make a
/// path exist by asserting it harder. ADR-0019 advisory-evaluator-calibration's anti-Goodhart concern is about accepting a verdict;
/// this accepts a pointer and then goes and looks. Every test below is about keeping that
/// distinction intact — nothing here verifies a path, and nothing here may.</para>
/// </remarks>
public sealed class DeclaredArtifactTests
{
    // ---------------------------------------------------------------- the wire format

    /// <summary>
    /// An absent attribute is not a malformed one.
    /// </summary>
    /// <remarks>
    /// The normal case for every agent that never declares evidence, and it must cost them nothing:
    /// the episode still closes and still scores Not Scored, which was already the honest answer.
    /// </remarks>
    [Fact]
    public void AnAbsentAttributeSucceedsWithNoPaths()
    {
        Assert.True(DeclaredArtifactBounds.TryParse(null, out var paths));
        Assert.Empty(paths);
    }

    /// <summary>
    /// Present but blank FAILS, where absent succeeds.
    /// </summary>
    /// <remarks>
    /// An agent that sent the key meant to say something. Accepting a blank as "no evidence" would
    /// let a value lost in transit read as a deliberate silence — the two rendering alike is the
    /// shape this vertical has been corrected for three times.
    /// </remarks>
    [Theory]
    [InlineData("")]
    [InlineData("   ")]
    [InlineData("\n\n")]
    public void PresentButBlankIsMalformedRatherThanEmpty(string value)
    {
        Assert.False(DeclaredArtifactBounds.TryParse(value, out var paths));
        Assert.Empty(paths);
    }

    [Fact]
    public void PathsAreNewlineSeparatedAndTrimmed()
    {
        Assert.True(DeclaredArtifactBounds.TryParse(
            "docs/proof/one.md\n  docs/proof/two.md  \n", out var paths));

        Assert.Equal(["docs/proof/one.md", "docs/proof/two.md"], paths);
    }

    /// <summary>
    /// A path containing spaces survives, because the separator cannot occur inside one.
    /// </summary>
    /// <remarks>
    /// The reason the separator is a newline rather than a space, comma or semicolon: all three
    /// occur in real paths, and a separator that can appear inside a value is a parser that silently
    /// splits one path into two — producing two paths that do not exist from one that does.
    /// </remarks>
    [Fact]
    public void APathWithSpacesIsOnePath()
    {
        Assert.True(DeclaredArtifactBounds.TryParse("docs/proof/my report, final.md", out var paths));

        Assert.Equal("docs/proof/my report, final.md", Assert.Single(paths));
    }

    // ---------------------------------------------------------------- bounds

    /// <summary>
    /// Over a bound the line is quarantined, never truncated.
    /// </summary>
    /// <remarks>
    /// A silently shortened evidence list is a partial record rendered as a whole one. The agent
    /// believes it declared five paths, the product kept three, and nothing tells either of them.
    /// </remarks>
    [Fact]
    public void TooManyPathsIsRefusedRatherThanTruncated()
    {
        var value = string.Join("\n",
            Enumerable.Range(0, DeclaredArtifactBounds.MaxPaths + 1).Select(i => $"docs/proof/{i}.md"));

        Assert.False(DeclaredArtifactBounds.TryParse(value, out var paths));
        Assert.Empty(paths);
    }

    [Fact]
    public void ExactlyTheMaximumIsAccepted()
    {
        var value = string.Join("\n",
            Enumerable.Range(0, DeclaredArtifactBounds.MaxPaths).Select(i => $"docs/proof/{i}.md"));

        Assert.True(DeclaredArtifactBounds.TryParse(value, out var paths));
        Assert.Equal(DeclaredArtifactBounds.MaxPaths, paths.Count);
    }

    [Fact]
    public void AnOverlongPathIsRefused()
    {
        Assert.False(DeclaredArtifactBounds.TryParse(
            new string('x', DeclaredArtifactBounds.MaxPathLength + 1), out _));
    }

    // ------------------------------------------------- declared, never verified

    /// <summary>
    /// A path that is absolute, escapes the repository, or does not exist is recorded verbatim.
    /// </summary>
    /// <remarks>
    /// <para><b>The load-bearing property of this whole design.</b> The store keeps what was
    /// <i>said</i>; the scoring side decides what is <i>true</i>. Rejecting a suspicious path here
    /// would feel safer and would destroy the only evidence that separates an agent that lied from a
    /// file that moved — and it would move a security decision into a parser that has no repository
    /// root to check against.</para>
    ///
    /// <para>These strings are untrusted input and are stored as data, exactly like board content.
    /// Nothing on this path opens, resolves or stats them.</para>
    /// </remarks>
    [Theory]
    [InlineData("/etc/passwd")]
    [InlineData("C:\\Windows\\System32\\config\\SAM")]
    [InlineData("../../../outside/the/repo.md")]
    [InlineData("docs/proof/does-not-exist.md")]
    [InlineData("not-even-under-docs-proof.txt")]
    public void AnUntrustworthyPathIsRecordedExactlyAsSent(string path)
    {
        Assert.True(DeclaredArtifactBounds.TryParse(path, out var paths));

        Assert.Equal(path, Assert.Single(paths));
    }
}
