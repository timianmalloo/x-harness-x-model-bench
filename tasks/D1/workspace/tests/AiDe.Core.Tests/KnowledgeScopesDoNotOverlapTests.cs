using AiDe.Core.Extraction;

namespace AiDe.Core.Tests;

/// <summary>
/// Each knowledge document is read by exactly one scope, and a prose link resolves anyway.
/// </summary>
/// <remarks>
/// <para><b>DC-051, both halves, in one fixture — because either half alone is a regression.</b>
/// Knowledge scopes NEST: discovery yields a scope for every directory holding a document with an
/// id, so <c>docs</c> and <c>docs/adr</c> are both scopes and a recursive walk read
/// <c>docs/adr/0001.md</c> from both. MEASURED on TheTerrace: <b>2,371 <c>node_class</c> rows for
/// 878 distinct documents</b>, every knowledge fact stored ~2.7 times.</para>
///
/// <para><b>The obvious fix was made, measured and REVERTED.</b> Walking only each scope's own
/// directory produced exactly 878 documents and 878 rows — and dropped <c>links_to</c> from 42
/// distinct edges to 12, because a link across directories had only ever resolved for the wide
/// scope that read both sides. The duplication metric was perfect and a feature lost 71% of its
/// output.</para>
///
/// <para><b>So this fixture asserts the two together, and is built so that neither can be satisfied
/// on its own.</b> <c>docs/adr</c> and <c>guides</c> are sibling scopes with NO knowledge scope
/// above them — the repository root declares no document — so the edge from <c>adr-0001</c> to
/// <c>guide-setup</c> is one that no single scope's tree contains. Before this change it did not
/// exist at all; after a naive de-duplication it would not exist either. Only reading the whole
/// workspace for RESOLUTION while emitting per DIRECTORY produces both numbers at once.</para>
///
/// <para><b>Watched failing on the unfixed reader</b> — <c>node_class</c> came back 6 rows for 4
/// documents, and the cross-directory edge was absent — and again on the reverted naive fix, where
/// the rows were right and the edge was still absent.</para>
/// </remarks>
public sealed class KnowledgeScopesDoNotOverlapTests : IDisposable
{
    private readonly string _dir = Path.Combine(
        Path.GetTempPath(), "aide-kb-overlap", Guid.NewGuid().ToString("N"));

    private string Repo => Path.Combine(_dir, "repo");

    public KnowledgeScopesDoNotOverlapTests()
    {
        // Two knowledge trees with NO scope above them: the repository root holds no document, so
        // nothing has ever read both `docs` and `guides`. That is what makes the edge below a
        // measurement of workspace-wide resolution rather than of a wide scope's recursive walk.
        Write("docs/index.md", """
            ---
            id: doc-index
            type: doc
            ---

            The decisions are in [the register](adr/0001.md).
            """);

        Write("docs/adr/0001.md", """
            ---
            id: adr-0001
            type: adr
            ---

            Refines [the workspace spec](../specs/workspace.md), and is applied by
            [the setup guide](../../guides/setup.md). Background is in
            [the notes](../../guides/notes/README.md), and [the old plan](../specs/gone.md) moved.
            """);

        Write("docs/specs/workspace.md", """
            ---
            id: spec-workspace
            type: spec
            ---

            # Workspace
            """);

        Write("guides/setup.md", """
            ---
            id: guide-setup
            type: guide
            ---

            # Setup
            """);

        // A directory whose markdown declares no id is NOT a scope. It is in the workspace survey
        // all the same, so a link to it is disclosed as a boundary rather than as a broken link.
        Write("guides/notes/README.md", "# Notes\n\nNo frontmatter, so not a node.\n");
    }

    public void Dispose()
    {
        try { Directory.Delete(_dir, recursive: true); } catch (IOException) { }
    }

    private void Write(string relative, string content)
    {
        var path = Path.Combine(Repo, relative.Replace('/', Path.DirectorySeparatorChar));
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        File.WriteAllText(path, content);
    }

    /// <summary>Everything the product stores for this repository, through the real index path.</summary>
    /// <remarks>
    /// Indexed through <see cref="WorkspaceCore"/> rather than by calling the extractor, because the
    /// workspace survey is composed there. A test that hand-built the request would prove the
    /// reader can use a map it was handed and say nothing about whether anything hands it one — and
    /// an extractor that was correct and unreachable is exactly how DC-041 happened here before.
    /// </remarks>
    private async Task<IReadOnlyList<Store.StoredAssertion>> IndexAsync()
    {
        using var core = WorkspaceCore.Open(
            "ws", Repo, Path.Combine(_dir, "data"), WorkspaceExtractors.Default());

        var result = await core.IndexCSharpAsync("rev-1", CancellationToken.None);

        Assert.Empty(result.Failed);

        using var reader = core.Store.BeginRead();
        return reader.AllCurrentAssertions();
    }

    [Fact]
    public async Task EveryDocumentIsEmittedByExactlyOneScope()
    {
        // THE DE-DUPLICATION. `node_class` is the row this is counted on because it is emitted once
        // per document per reading scope and never for anything else, which is what made the
        // 2,368-rows-for-877-documents measurement possible in the first place.
        var stored = await IndexAsync();

        var knowledge = stored.Where(a => a.Predicate == "node_class" && a.Object == "knowledge").ToList();

        Assert.Equal(4, knowledge.Select(a => a.Subject).Distinct(StringComparer.Ordinal).Count());
        Assert.Equal(4, knowledge.Count);

        // And the scope that owns each one is the directory the file is in — not an ancestor that
        // happened to walk past it. A document counted once but attributed to the wrong scope would
        // pass the count above and still put the node in the wrong place in every grouped view.
        Assert.Equal("knowledge:docs/adr",
            Assert.Single(knowledge, a => a.Subject == "adr-0001").ScopeId);
        Assert.Equal("knowledge:guides",
            Assert.Single(knowledge, a => a.Subject == "guide-setup").ScopeId);
    }

    [Fact]
    public async Task NoDocumentIsDeclaredInMoreThanOneScope()
    {
        // The same duplication seen from the fact that ANSWERS "where does this live". Before the
        // change `declared_in` was the one predicate whose row count and distinct-pair count agreed
        // while still being wrong — 2,371 rows AND 2,371 distinct pairs for 878 documents, because
        // each duplicate named a different scope. Counting distinct subjects is the only way to see
        // it, and that is the number this pins.
        var stored = await IndexAsync();

        var declared = stored
            .Where(a => a.Predicate == "declared_in" && a.ScopeId.StartsWith("knowledge:", StringComparison.Ordinal))
            .ToList();

        Assert.Equal(
            declared.Select(a => a.Subject).Distinct(StringComparer.Ordinal).Count(),
            declared.Count);
    }

    [Fact]
    public async Task AProseLinkResolvesAcrossTheWholeWorkspaceAndNotJustItsOwnScope()
    {
        // THE HALF THAT WAS PAID FOR LAST TIME. `docs/adr` and `guides` are sibling scopes with no
        // scope above them, so this edge exists in no single scope's tree: it is produced only by
        // resolving against the workspace while emitting per directory.
        var stored = await IndexAsync();

        var edges = stored
            .Where(a => a.Predicate == "links_to")
            .Select(a => (a.Subject, a.Object))
            .ToHashSet();

        // ACROSS the top of the tree — the one no scope could see before.
        Assert.Contains(("adr-0001", "guide-setup"), edges);

        // SIDEWAYS between two sibling scopes under `docs`, which only the recursive parent used to
        // resolve and which a narrow walk alone would have lost.
        Assert.Contains(("adr-0001", "spec-workspace"), edges);

        // DOWNWARD from a parent scope into a child scope's directory, which is the direction the
        // narrow walk changes most: `docs` no longer reads `docs/adr` at all.
        Assert.Contains(("doc-index", "adr-0001"), edges);

        // And each of them exactly once. An edge emitted by two scopes is the duplication moved
        // rather than removed.
        Assert.Equal(3, stored.Count(a => a.Predicate == "links_to"));
    }

    [Fact]
    public async Task ABrokenLinkIsStillAGapAndAnUnindexedFileIsStillABoundary()
    {
        // THE NUMBER THAT WOULD GET WORSE IF THE WIDENING WERE WRONG (DC-051's own lesson).
        // Resolution now looks across the whole workspace, and the failure mode of looking wider is
        // that broken cross-references quietly become found ones. `../specs/gone.md` is not there
        // and must stay counted; `guides/notes/README.md` IS there, declares no id, and must be
        // counted as this product's boundary rather than as a defect in the document (DC-050).
        var stored = await IndexAsync();

        var disclosures = stored
            .Where(a => a.Predicate == "discloses" && a.ScopeId == "knowledge:docs/adr")
            .Select(a => a.Object)
            .ToList();

        Assert.Contains(disclosures, d => d.StartsWith(
            $"{KnowledgeExtractor.Disclosures.LinkTargetMissing} (1 prose link(s)",
            StringComparison.Ordinal));

        Assert.Contains(disclosures, d => d.StartsWith(
            $"{KnowledgeExtractor.Disclosures.LinkTargetNotANode} (1 prose link(s)",
            StringComparison.Ordinal));

        // And nothing claims a boundary that is no longer there. Every link in this fixture is
        // inside the workspace, so the only remaining escape hatch must stay silent.
        Assert.DoesNotContain(disclosures, d => d.StartsWith(
            KnowledgeExtractor.Disclosures.LinkTargetOutsideWorkspace, StringComparison.Ordinal));
    }
}
