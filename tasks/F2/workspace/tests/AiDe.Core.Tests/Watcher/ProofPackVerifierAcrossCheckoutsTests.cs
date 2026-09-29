using AiDe.Core.Watcher;

namespace AiDe.Core.Tests.Watcher;

/// <summary>
/// The tri-state survives the fold across several checkouts (DC-115).
/// </summary>
/// <remarks>
/// <para><b>Why this is not covered by the end-to-end reproduction.</b>
/// <c>AGovernedLaneIsCreditedForItsOwnBranchTests</c> proves the composed behaviour through real git
/// and real scoring, but scoring collapses the verdict to a bool at
/// <c>EpisodeEvidence.HasProofPack</c> — so <c>NotFound</c> and <c>Unverifiable</c> are
/// indistinguishable from there. The distinction is the whole reason the enum exists, and the only
/// place it can be asserted is here, where the verdict is still three-valued.</para>
///
/// <para><b>The precedence, stated once:</b> <c>Verified</c> beats <c>NotFound</c> beats
/// <c>Unverifiable</c>. Finding it anywhere is finding it; "we looked in a real checkout and it is
/// not there" is a fact about the evidence and outranks "we could not look", which is a fact about
/// the product; and looking nowhere claims nothing.</para>
/// </remarks>
public sealed class ProofPackVerifierAcrossCheckoutsTests : IDisposable
{
    private const string Declared = "docs/proof/ep-1.md";

    private readonly string _first = NewDirectory();
    private readonly string _second = NewDirectory();
    private readonly string _missing =
        Path.Combine(Path.GetTempPath(), "aide-gone-" + Guid.NewGuid().ToString("N")[..8]);

    public void Dispose()
    {
        Delete(_first);
        Delete(_second);
    }

    [Fact]
    public void FindingItInTheSecondCheckoutIsFindingIt()
    {
        GivenAProofPackIn(_second);

        Assert.Equal(
            ProofPackVerdict.Verified,
            ProofPackVerifier.VerifyInCheckouts([_first, _second], Declared));
    }

    /// <summary>The fold is a fold: which root is passed first cannot change the answer.</summary>
    [Fact]
    public void TheFoldIsOrderIndependent()
    {
        GivenAProofPackIn(_second);

        Assert.Equal(
            ProofPackVerifier.VerifyInCheckouts([_first, _second], Declared),
            ProofPackVerifier.VerifyInCheckouts([_second, _first], Declared));
    }

    [Fact]
    public void TwoRealCheckoutsWithoutItAreNotFound()
        => Assert.Equal(
            ProofPackVerdict.NotFound,
            ProofPackVerifier.VerifyInCheckouts([_first, _second], Declared));

    /// <summary>
    /// The collapse this enum exists to prevent, at the new boundary: nowhere to look is not an
    /// absence.
    /// </summary>
    [Fact]
    public void NoReachableCheckoutIsUnverifiable_NeverAnAbsence()
        => Assert.Equal(
            ProofPackVerdict.Unverifiable,
            ProofPackVerifier.VerifyInCheckouts([_missing, _missing + "-2"], Declared));

    /// <summary>An unreachable root must not swallow a real answer from a reachable one.</summary>
    [Fact]
    public void AnUnreachableCheckoutDoesNotHideARealAnswer()
    {
        Assert.Equal(
            ProofPackVerdict.NotFound,
            ProofPackVerifier.VerifyInCheckouts([_missing, _first], Declared));

        GivenAProofPackIn(_first);

        Assert.Equal(
            ProofPackVerdict.Verified,
            ProofPackVerifier.VerifyInCheckouts([_missing, _first], Declared));
    }

    /// <summary>Looking nowhere claims nothing — the honest answer for an empty set.</summary>
    [Fact]
    public void AnEmptySetIsUnverifiable()
        => Assert.Equal(ProofPackVerdict.Unverifiable, ProofPackVerifier.VerifyInCheckouts([], Declared));

    /// <summary>
    /// A blank entry is tolerated, so a caller need not filter an absent worktree out — and it
    /// claims nothing on its own.
    /// </summary>
    [Fact]
    public void ABlankCheckoutIsToleratedAndClaimsNothing()
    {
        Assert.Equal(ProofPackVerdict.Unverifiable, ProofPackVerifier.VerifyInCheckouts([null, "   "], Declared));

        GivenAProofPackIn(_first);

        Assert.Equal(ProofPackVerdict.Verified, ProofPackVerifier.VerifyInCheckouts([null, _first], Declared));
    }

    /// <summary>
    /// Several roots is several complete containment checks, never a widened one.
    /// </summary>
    /// <remarks>
    /// The security boundary is the reason the verifier exists at all: a declared path escaping the
    /// root it is checked against would let one session be scored for another repository's evidence.
    /// Adding roots must not create a seam between them — a file outside every root stays outside,
    /// and the separator-terminated prefix test still refuses a NEIGHBOURING directory whose name
    /// merely begins with a root's.
    /// </remarks>
    [Fact]
    public void ContainmentSurvivesTheFold()
    {
        var outside = NewDirectory();
        var neighbour = _first + "-other";

        try
        {
            Directory.CreateDirectory(neighbour);
            GivenAProofPackIn(outside);
            GivenAProofPackIn(neighbour);

            Assert.Equal(
                ProofPackVerdict.NotFound,
                ProofPackVerifier.VerifyInCheckouts(
                    [_first, _second], Path.Combine(outside, "docs", "proof", "ep-1.md")));

            Assert.Equal(
                ProofPackVerdict.NotFound,
                ProofPackVerifier.VerifyInCheckouts(
                    [_first, _second], Path.Combine(neighbour, "docs", "proof", "ep-1.md")));
        }
        finally
        {
            Delete(outside);
            Delete(neighbour);
        }
    }

    [Fact]
    public void ANullSetIsARefusal_NotAVerdict()
        => Assert.Throws<ArgumentNullException>(() => ProofPackVerifier.VerifyInCheckouts(null!, Declared));

    private static void GivenAProofPackIn(string root)
    {
        var full = Path.Combine(root, "docs", "proof", "ep-1.md");
        Directory.CreateDirectory(Path.GetDirectoryName(full)!);
        File.WriteAllText(full, "proof");
    }

    private static string NewDirectory()
    {
        var path = Path.Combine(Path.GetTempPath(), "aide-fold-" + Guid.NewGuid().ToString("N")[..8]);
        Directory.CreateDirectory(path);
        return path;
    }

    private static void Delete(string path)
    {
        try
        {
            if (Directory.Exists(path))
            {
                Directory.Delete(path, recursive: true);
            }
        }
        catch (IOException)
        {
        }
    }
}
