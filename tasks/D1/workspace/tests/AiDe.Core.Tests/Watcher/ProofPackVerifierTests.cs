using AiDe.Core.Watcher;

namespace AiDe.Core.Tests.Watcher;

/// <summary>
/// A path an agent declares becomes evidence only if the product can see the file.
/// </summary>
/// <remarks>
/// <para><b>The distinction this defends.</b> The watcher observes rather than accepts testimony,
/// which is why an <c>episode-close</c> carrying its own <c>acceptance_met</c> is refused. A declared
/// path is admissible because the agent names a file and the product checks whether it is there —
/// the agent cannot make the check pass by asserting harder.</para>
///
/// <para><b>Containment is a security boundary.</b> Declared paths are recorded verbatim by the
/// ingest half, uninspected and deliberately so, which means absolute paths, traversal and escaping
/// all arrive intact and this layer is the one that decides. A path escaping the repository would
/// let one session point at another repository's evidence, or at any file on the machine whose mere
/// existence would then become a score.</para>
///
/// <para><b>Three verdicts, never a bool.</b> Collapsing "we looked and it is not there" into "we
/// could not look" is the exact defect being fixed one layer up, where <c>HasProofPack: false</c>
/// was hardcoded.</para>
/// </remarks>
public sealed class ProofPackVerifierTests : IDisposable
{
    private readonly string _repository = NewDirectory();

    public void Dispose() => Delete(_repository);

    private string GivenProofPack(string relative)
    {
        var full = Path.Combine(_repository, relative.Replace('/', Path.DirectorySeparatorChar));
        Directory.CreateDirectory(Path.GetDirectoryName(full)!);
        File.WriteAllText(full, "proof");
        return full;
    }

    // Platform=Windows: assert backslash paths resolve and directory matching ignores case - both Windows semantics
    [Trait("Platform", "Windows")]
    // Platform=Windows: assert backslash paths resolve and directory matching ignores case - both Windows semantics
    [Trait("Platform", "Windows")]
    [Fact]
    public void ACommittedProofPackIsVerified()
    {
        GivenProofPack("docs/proof/ep-1.md");

        Assert.Equal(
            ProofPackVerdict.Verified,
            ProofPackVerifier.Verify(_repository, "docs/proof/ep-1.md"));
    }

    // Platform=Windows: asserts Windows path semantics: backslashes resolve, directory matching ignores case
    [Trait("Platform", "Windows")]
    [Fact]
    public void BackslashesAndForwardSlashesBothWork()
    {
        // The agent's platform is not ours to assume, and the ingest records the path verbatim.
        GivenProofPack("docs/proof/ep-1.md");

        Assert.Equal(
            ProofPackVerdict.Verified,
            ProofPackVerifier.Verify(_repository, @"docs\proof\ep-1.md"));
    }

    [Fact]
    public void AnAbsolutePathInsideTheRepositoryIsVerified()
    {
        var full = GivenProofPack("docs/proof/ep-1.md");

        Assert.Equal(ProofPackVerdict.Verified, ProofPackVerifier.Verify(_repository, full));
    }

    [Fact]
    public void ADeclaredPathThatIsNotThereIsNotFound()
    {
        // We could look, and it is not there. A statement about this episode.
        Assert.Equal(
            ProofPackVerdict.NotFound,
            ProofPackVerifier.Verify(_repository, "docs/proof/never-written.md"));
    }

    [Fact]
    public void ARealFileOutsideTheProofDirectoryIsNotEvidence()
    {
        // Existing is not enough. A Proof Pack is a committed artifact in a known place, and any
        // file counting would make "I touched a file" a score.
        GivenProofPack("docs/notes/ep-1.md");

        Assert.Equal(
            ProofPackVerdict.NotFound,
            ProofPackVerifier.Verify(_repository, "docs/notes/ep-1.md"));
    }

    [Fact]
    public void TheProofDirectoryItselfIsNotAProofPack()
    {
        Directory.CreateDirectory(Path.Combine(_repository, "docs", "proof"));

        Assert.Equal(ProofPackVerdict.NotFound, ProofPackVerifier.Verify(_repository, "docs/proof"));
    }

    [Fact]
    public void TraversalOutOfTheRepositoryIsRefused_EvenWhenTheFileExists()
    {
        // THE ATTACK. A neighbouring directory's real proof pack, reached by climbing out. The file
        // exists and is under a docs/proof path — only containment stops it.
        var outside = NewDirectory();

        try
        {
            var escaped = Path.Combine(outside, "docs", "proof");
            Directory.CreateDirectory(escaped);
            File.WriteAllText(Path.Combine(escaped, "ep-1.md"), "someone else's evidence");

            var traversal = Path.Combine("..", Path.GetFileName(outside), "docs", "proof", "ep-1.md");

            Assert.Equal(ProofPackVerdict.NotFound, ProofPackVerifier.Verify(_repository, traversal));
        }
        finally
        {
            Delete(outside);
        }
    }

    [Fact]
    public void ASiblingRepositoryWithAMatchingPrefixIsRefused()
    {
        // THE PREFIX TRAP, and the reason containment appends a separator before comparing. A plain
        // StartsWith says C:\repos\app-other is inside C:\repos\app — a neighbouring repository
        // admitted as this one's evidence, which is the containment failure most likely to be
        // written and least likely to be noticed.
        var sibling = _repository + "-other";

        try
        {
            var proof = Path.Combine(sibling, "docs", "proof");
            Directory.CreateDirectory(proof);
            File.WriteAllText(Path.Combine(proof, "ep-1.md"), "the neighbour's evidence");

            Assert.Equal(
                ProofPackVerdict.NotFound,
                ProofPackVerifier.Verify(_repository, Path.Combine(sibling, "docs", "proof", "ep-1.md")));
        }
        finally
        {
            Delete(sibling);
        }
    }

    [Fact]
    public void AnUnreachableRepositoryIsUnverifiable_NotAbsent()
    {
        // THE DISTINCTION THAT MATTERS. The registrant's filesystem may simply not be ours. Saying
        // NotFound here would be the hardcoded false all over again — a claim about the agent, in
        // the one case where the product is what cannot see.
        var missing = Path.Combine(Path.GetTempPath(), "aide-absent-" + Guid.NewGuid().ToString("N")[..8]);

        Assert.Equal(ProofPackVerdict.Unverifiable, ProofPackVerifier.Verify(missing, "docs/proof/ep-1.md"));
        Assert.Equal(ProofPackVerdict.Unverifiable, ProofPackVerifier.Verify(null, "docs/proof/ep-1.md"));
        Assert.Equal(ProofPackVerdict.Unverifiable, ProofPackVerifier.Verify("   ", "docs/proof/ep-1.md"));
    }

    [Theory]
    [InlineData(null)]
    [InlineData("")]
    [InlineData("   ")]
    public void AnEmptyDeclarationIsNotFound_NotUnverifiable(string? declared)
    {
        // We could look; there was nothing to look for. That is about the declaration, not about us.
        Assert.Equal(ProofPackVerdict.NotFound, ProofPackVerifier.Verify(_repository, declared));
    }

    [Fact]
    public void ASiblingWhoseNameEXTENDSTheRootIsRefused()
    {
        // THE CASE CONTAINMENT ACTUALLY PREVENTS, and the one the other sibling test does NOT reach.
        //
        // Mutation replay found this: removing the separator from the containment comparison
        // reddened nothing, because in the neighbouring-directory test the escaped path's remainder
        // ("-other/docs/proof/...") fails the docs/proof check anyway. So that test passes for a
        // reason it does not name.
        //
        // Here the sibling is named <root>docs, so the remainder after a PLAIN prefix strip is
        // exactly "docs/proof/x.md" — it passes the directory check, the file exists, and a plain
        // StartsWith would return Verified for another directory's file. Only the appended separator
        // stops it.
        var sibling = _repository + "docs";

        try
        {
            var proof = Path.Combine(sibling, "proof");
            Directory.CreateDirectory(proof);
            File.WriteAllText(Path.Combine(proof, "x.md"), "not this repository's evidence");

            Assert.Equal(
                ProofPackVerdict.NotFound,
                ProofPackVerifier.Verify(_repository, Path.Combine(sibling, "proof", "x.md")));
        }
        finally
        {
            Delete(sibling);
        }
    }

    [Fact]
    public void ADirectoryUNDERTheProofFolderIsNotAProofPack()
    {
        // The sibling of TheProofDirectoryItselfIsNotAProofPack, and the one that actually exercises
        // the File.Exists check: "docs/proof" alone is rejected earlier, by the trailing-separator in
        // ProofDirectory, so it never reaches the existence test. A directory INSIDE docs/proof does.
        Directory.CreateDirectory(Path.Combine(_repository, "docs", "proof", "run-1"));

        Assert.Equal(
            ProofPackVerdict.NotFound,
            ProofPackVerifier.Verify(_repository, "docs/proof/run-1"));
    }

    // Platform=Windows: asserts Windows path semantics: backslashes resolve, directory matching ignores case
    [Trait("Platform", "Windows")]
    [Fact]
    public void TheProofDirectoryMatchIgnoresCase()
    {
        // Windows paths are case-insensitive, so the file the agent named IS the file on disk. A
        // case-sensitive directory match would reject real evidence for how the agent spelled it,
        // which is a claim about the agent's typing rather than about its work.
        GivenProofPack("docs/proof/ep-1.md");

        Assert.Equal(
            ProofPackVerdict.Verified,
            ProofPackVerifier.Verify(_repository, "DOCS/PROOF/ep-1.md"));
    }

    [Fact]
    public void AnUnusablePathIsNotFound_RatherThanThrowing()
    {
        // Something the filesystem refuses to evaluate is not evidence, and must not travel as an
        // exception through the scoring path.
        //
        // A 400-character segment was the first attempt and it does NOT throw on modern .NET, so the
        // catch was never exercised and disabling it reddened nothing. A NUL byte does throw, which
        // is what makes this a test of the handler rather than of a long string.
        Assert.Equal(
            ProofPackVerdict.NotFound,
            ProofPackVerifier.Verify(_repository, "docs/proof/a\0b.md"));
    }

    [Fact]
    public void AnUpperCasedProofDirectoryIsEvidenceONLYWhereTheFILESYSTEMSaysItIsTheSameFile()
    {
        // THE POSIX HALF OF TheProofDirectoryMatchIgnoresCase, and the reason that test carries
        // [Trait("Platform", "Windows")] while this one does not.
        //
        // Case-folding the directory match is CORRECT on Windows - DOCS\PROOF\ep-1.md and
        // docs\proof\ep-1.md are one file there, so rejecting the agent's spelling would be a claim
        // about its typing rather than about its work. On Linux they are two different files, and
        // folding admits a path the rest of the system would never write: the verdict Verified then
        // means something slightly different from what every reader takes it to mean.
        //
        // NOT SKIPPED ON WINDOWS. There is a true and different assertion to make on each platform,
        // so this asserts the platform's own answer rather than printing a reason and proving
        // nothing. It can only REDDEN on Linux; the Windows branch is a characterisation that pins
        // the Windows answer against a fix that over-corrects both platforms at once.
        GivenProofPack("DOCS/PROOF/ep-1.md");

        var onThisFilesystem = OperatingSystem.IsWindows()
            ? ProofPackVerdict.Verified
            : ProofPackVerdict.NotFound;

        Assert.Equal(onThisFilesystem, ProofPackVerifier.Verify(_repository, "DOCS/PROOF/ep-1.md"));
    }

    private static string NewDirectory()
    {
        var path = Path.Combine(Path.GetTempPath(), "aide-proof-" + Guid.NewGuid().ToString("N")[..8]);
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
        catch (UnauthorizedAccessException)
        {
        }
    }
}
