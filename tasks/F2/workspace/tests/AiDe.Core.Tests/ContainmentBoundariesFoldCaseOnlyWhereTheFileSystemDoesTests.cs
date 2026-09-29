using AiDe.Core.Extraction;
using AiDe.Core.Facts;
using AiDe.Core.Projections;

namespace AiDe.Core.Tests;

/// <summary>
/// A containment boundary admits a path only when THIS filesystem agrees the path is the same one.
/// </summary>
/// <remarks>
/// <para><b>The same defect, four times.</b> `x.StartsWith(root + separator, OrdinalIgnoreCase)` is
/// this repository's containment shape, and the unconditional case fold in it is right on Windows
/// and wrong everywhere else. It was repaired at INV-0005, at
/// <c>RepositoryIdentity.ToFileSystemPath</c>, and at
/// <c>RepositoryCorrection</c>/<see cref="Watcher.ProofPackVerifier"/> — one call site each time —
/// while three more sites carried it untouched. These tests pin the rule itself and the two sites
/// where the rule is OBSERVABLE through a public surface;
/// <c>tools/verify-containment-comparisons.py</c> is what stops a fifth site being written.</para>
///
/// <para><b>Not skipped on Windows.</b> There is a true and DIFFERENT assertion to make on each
/// platform, so each test asserts the platform's own answer rather than printing a reason and
/// proving nothing. Every one of these can only REDDEN on POSIX; the Windows branch is a
/// characterisation that pins the Windows answer against a fix that over-corrects both platforms at
/// once. This is the idiom <c>ProofPackVerifierTests</c> established.</para>
/// </remarks>
public sealed class ContainmentBoundariesFoldCaseOnlyWhereTheFileSystemDoesTests : IDisposable
{
    private static readonly DateTimeOffset Observed =
        new(2026, 9, 10, 0, 0, 0, TimeSpan.Zero);

    private readonly string _base = Path.Combine(
        Path.GetTempPath(), "aide-containment", Guid.NewGuid().ToString("N"));

    public void Dispose()
    {
        try { Directory.Delete(_base, recursive: true); } catch (IOException) { }
        catch (UnauthorizedAccessException) { }
    }

    [Fact]
    public void TheOnePathRuleIsTheFileSystemsOwnAnswerAndNothingElse()
    {
        // The rule every containment boundary now shares. Asserted directly, because the three
        // sites below reach it through enough machinery that a wrong rule could be masked by a
        // scenario rather than reported by it.
        var expected = OperatingSystem.IsWindows()
            ? StringComparison.OrdinalIgnoreCase
            : StringComparison.Ordinal;

        Assert.Equal(expected, PathComparison.ForThisFileSystem);
    }

    [Fact]
    public void AKnowledgeLinkThatLeavesTheRootByCASEResolvesONLYWhereTheFILESYSTEMSaysItIsTheSameDirectory()
    {
        // SITE 2 — KnowledgeExtractor.Resolve (src/AiDe.Core/Extraction/KnowledgeExtractor.cs).
        //
        // `../DOCS/b.md` written inside `<base>/docs` lands at `<base>/DOCS/b.md`. On Windows that
        // IS the resolution root, spelled differently, so resolving the link is right. On POSIX it
        // is a DIFFERENT directory that happens to be spelled similarly, and resolving it emits a
        // knowledge edge to a document outside the root the extractor was bounded to — the bound
        // silently not applying is worse than the edge being missing, because the graph then
        // asserts a relationship nothing checked.
        //
        // Pure string arithmetic: Resolve touches no filesystem, so there is nothing to create.
        var root = Path.Combine(_base, "docs");
        var fromFile = Path.Combine(root, "a.md");

        var resolved = KnowledgeExtractor.Resolve(fromFile, "../DOCS/b.md", root);

        if (OperatingSystem.IsWindows())
        {
            Assert.Equal(Path.GetFullPath(Path.Combine(_base, "DOCS", "b.md")), resolved);
        }
        else
        {
            Assert.Null(resolved);
        }
    }

    [Fact]
    public void AWorkspaceFileReachedByCASEIsSearchedONLYWhereTheFILESYSTEMSaysItIsInsideTheWorkspace()
    {
        // SITE 3 — ProjectionService.ResolveWithinWorkspace
        // (src/AiDe.Core/Projections/ProjectionService.cs).
        //
        // The scope records its location as `..`, so an artifact path of `WS/secret.md` resolves to
        // `<base>/WS/secret.md` while the workspace root is `<base>/ws`. On Windows those are one
        // directory and serving the content is correct. On POSIX they are two, and the search
        // returns a line from a file OUTSIDE the workspace it was asked about — the exact escape
        // the separator-terminated prefix test exists to refuse, defeated by the case fold beside
        // it.
        Directory.CreateDirectory(Path.Combine(_base, "ws"));
        Directory.CreateDirectory(Path.Combine(_base, "WS"));
        File.WriteAllText(Path.Combine(_base, "WS", "secret.md"), "escaped-content-marker\n");

        using var workspace = TestWorkspace.Create();

        workspace.CommitSnapshot("s", 1, "rev-1",
            new EvidenceAssertion(
                "s", "rev-1", "s", "declared_at", "..", EvidenceOrigin.Static,
                VerificationStatus.Verified,
                new Provenance("scope.md", "1:1", "fixture-extractor", "1.0.0", Observed)),
            new EvidenceAssertion(
                "s", "rev-1", "node:secret", "has_type", "Document", EvidenceOrigin.Static,
                VerificationStatus.Verified,
                new Provenance("WS/secret.md", "1:1", "fixture-extractor", "1.0.0", Observed)));

        var projections = new ProjectionService(workspace.Store, Path.Combine(_base, "ws"));

        var found = projections.SearchContent("escaped-content-marker", 10);

        Assert.Equal(OperatingSystem.IsWindows() ? 1 : 0, found.Matches.Count);
    }

    [Fact]
    public async Task AFixtureRootStillExtractsEveryFileItActuallyContains()
    {
        // SITE 1 — FixtureExtractor (src/AiDe.Core/Extraction/FixtureExtractor.cs:98).
        //
        // THIS TEST IS GREEN BEFORE AND AFTER THE FIX, AND THAT IS REPORTED RATHER THAN DRESSED UP.
        // The case rule at that site is NOT observable through ExtractAsync: `root` is
        // Path.GetFullPath(RootPath) and every path Directory.EnumerateFiles yields is that same
        // `root` string with segments appended, so `resolved.StartsWith(root + separator)` is true
        // by construction on both platforms whatever comparison it is given. The site is still
        // repaired — it is the same rule, and the gate refuses the shape — but its proof is the
        // gate observed failing on that line, plus the rule pinned above, NOT this test.
        //
        // What this test does own: the fix must not start REFUSING files that are genuinely inside
        // the root. That is the failure a narrowed comparison could plausibly introduce, and it is
        // the half nothing else here would notice.
        var root = Path.Combine(_base, "fixture");
        Directory.CreateDirectory(Path.Combine(root, "nested"));

        File.WriteAllText(Path.Combine(root, "top.facts"), "A -> calls -> B [Verified]\n");
        File.WriteAllText(Path.Combine(root, "nested", "deep.facts"), "C -> calls -> D [Verified]\n");

        var result = await new FixtureExtractor().ExtractAsync(
            new ExtractionRequest("fixture:x", root, "rev-1", 1), CancellationToken.None);

        Assert.Empty(result.Diagnostics);
        Assert.True(result.Complete);
        Assert.Equal(2, result.Assertions.Count);
    }
}
