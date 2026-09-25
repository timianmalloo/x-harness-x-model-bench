using AiDe.Core.Extraction;
using AiDe.Core.Facts;

namespace AiDe.Core.Tests;

/// <summary>
/// The half of a knowledge document that is not its frontmatter.
/// </summary>
/// <remarks>
/// <para><b>877 documents were in the graph and not one fact came from their prose.</b> The reader
/// saw frontmatter only and disclosed <c>knowledge-body-not-analysed</c> on every scope. These pin
/// the one thing now read from the body — a markdown hyperlink to another document — and, just as
/// importantly, pin that everything else is COUNTED rather than silently skipped.</para>
///
/// <para><b>Both directions, every time.</b> A disclosure that fires on every scope is noise and one
/// that never fires is decoration (DC-025), so each boundary here is asserted present when there IS
/// something to hide and absent when there is not.</para>
///
/// <para><b>Every fixture here now names a SCOPE and a WORKSPACE, and that is the policy change
/// these tests were rewritten for.</b> They were first written when a scope was the unit of
/// resolution — a link above the scope was its own boundary, because a wider scope might hold the
/// target and this reader had no way to know. That was right then and is wrong now: knowledge scopes
/// NEST, each document is emitted by exactly one scope, and there is no wider scope left to resolve
/// a cross-directory link (DC-051). So resolution reads the whole workspace and emission covers one
/// directory, and a fixture that conflated the two would be testing a topology the product no longer
/// has. The behaviour each test guards is unchanged; what moved is where the boundary sits, and the
/// boundary tests moved with it rather than being relaxed.</para>
/// </remarks>
public sealed class KnowledgeBodyTests : IDisposable
{
    private readonly string _dir = Path.Combine(
        Path.GetTempPath(), "aide-kb-body", Guid.NewGuid().ToString("N"));

    public KnowledgeBodyTests() => Directory.CreateDirectory(_dir);

    public void Dispose()
    {
        try { Directory.Delete(_dir, recursive: true); } catch (IOException) { }
    }

    private void Write(string relative, string content)
    {
        var path = Path.Combine(_dir, relative.Replace('/', Path.DirectorySeparatorChar));
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        File.WriteAllText(path, content);
    }

    /// <summary>Extract ONE scope, resolving against the whole fixture workspace.</summary>
    /// <remarks>
    /// <paramref name="scope"/> is the directory whose documents are emitted; <c>_dir</c> is always
    /// the workspace. Passing the survey explicitly is what the real composition does —
    /// <c>WorkspaceCore</c> builds it once per revision and hands it to every scope — and building it
    /// AFTER the fixture is written matters: the map is a snapshot of the filesystem, so a survey
    /// taken before the files exist would resolve nothing and the test would prove the opposite of
    /// what it says.
    /// </remarks>
    private async Task<IReadOnlyList<EvidenceAssertion>> ReadAsync(string? scope = null)
    {
        var result = await new KnowledgeExtractor().ExtractAsync(
            new ExtractionRequest(
                "knowledge:docs", scope ?? _dir, "rev-1", 1,
                WorkspaceKnowledge: KnowledgeExtractor.Survey(_dir)),
            CancellationToken.None);

        return result.Assertions;
    }

    private static bool Discloses(IEnumerable<EvidenceAssertion> facts, string prefix) =>
        facts.Any(a => a.Predicate == "discloses"
            && a.Object.StartsWith(prefix, StringComparison.Ordinal));

    private static string Disclosure(IEnumerable<EvidenceAssertion> facts, string prefix) =>
        facts.Single(a => a.Predicate == "discloses"
            && a.Object.StartsWith(prefix, StringComparison.Ordinal)).Object;

    [Fact]
    public async Task AProseLinkToAnotherDocumentIsAnEdge()
    {
        // THE POINT OF THE WHOLE CHANGE. MEASURED before building it: 237 prose .md links on
        // TheTerrace, 128 of which resolve to a document that is a node — 42 of them naming a
        // document the frontmatter does not, from 19 documents. All 42 were invisible.
        Write("adr/0001.md", """
            ---
            id: adr-0001-fact-store
            type: adr
            ---

            The rationale is set out in [the workspace spec](../specs/workspace.md).
            """);

        Write("specs/workspace.md", """
            ---
            id: spec-workspace
            type: spec
            ---

            # Workspace
            """);

        // The two documents are in SIBLING directories, which are two scopes. Under the old policy
        // this edge existed only because a wider scope walked both; now it exists because resolution
        // reads the workspace, and the scope emitting it is the one that owns `0001.md`.
        var facts = await ReadAsync(Path.Combine(_dir, "adr"));

        var edge = Assert.Single(facts, a => a.Predicate == "links_to");

        Assert.Equal("adr-0001-fact-store", edge.Subject);
        Assert.Equal("spec-workspace", edge.Object);
        Assert.Equal(VerificationStatus.Verified, edge.Status);

        // Provenance names the line the link is ON, not the frontmatter. A citation that points at
        // line 4 of every document is a citation nobody can follow back.
        Assert.Equal("6:1", edge.Provenance.SourceLocation);
    }

    [Fact]
    public async Task ALinkIsARelationRatherThanAnAttribute()
    {
        // A heading and a term are PROPERTIES of a document; a link names another thing. Getting
        // this wrong in either direction is expensive — an attribute drawn as an edge put dates and
        // unevaluated strings in the graph as things to navigate to, and a relation classified as an
        // attribute would make this edge invisible to the graph and to search.
        Assert.DoesNotContain("links_to", EvidencePredicates.Attributes);
    }

    [Fact]
    public async Task AProseLinkThatRepeatsADeclaredRelationIsNotEmittedAgain()
    {
        // MEASURED: 81 of the 128 resolving prose links on TheTerrace name a document the
        // frontmatter already links, with a TYPED relation. An untyped second edge between the same
        // pair adds no information and doubles the pair's weight wherever edges are counted.
        Write("adr/0001.md", """
            ---
            id: adr-0001-fact-store
            type: adr
            links:
              - { to: spec-workspace, rel: implements }
            ---

            As set out in [the spec](../specs/workspace.md).
            """);

        Write("specs/workspace.md", """
            ---
            id: spec-workspace
            ---
            """);

        var facts = await ReadAsync(Path.Combine(_dir, "adr"));

        Assert.Contains(facts, a => a.Predicate == "implements" && a.Object == "spec-workspace");
        Assert.DoesNotContain(facts, a => a.Predicate == "links_to");
    }

    [Fact]
    public async Task ADocumentDoesNotLinkToItself()
    {
        // A link back to the top of the same file is a table of contents. An edge from a node to
        // itself renders as a loop nobody drew.
        Write("a.md", """
            ---
            id: doc-a
            ---

            Back to [the top](a.md).
            """);

        Assert.DoesNotContain(await ReadAsync(), a => a.Predicate == "links_to");
    }

    [Fact]
    public async Task ALinkInsideAFencedCodeBlockIsNotAnEdge()
    {
        // THIS CONTROL CANNOT FIRE ON EITHER REAL CORPUS — measured, zero .md links inside fences
        // across 1,069 documents — so the fixture is the only thing that can prove it works
        // (DC-016). It is kept because a document explaining how to write a link is exactly the
        // document that would produce a false edge, and this repository's own docs are full of them.
        Write("guide.md", """
            ---
            id: doc-guide
            ---

            Write a cross-reference like this:

            ```markdown
            [the spec](specs/workspace.md)
            ```

            And inline, spell it `[the spec](specs/workspace.md)` without following it.
            """);

        Write("specs/workspace.md", """
            ---
            id: spec-workspace
            ---
            """);

        // The target is now REACHABLE — it is in the workspace map — so the only thing that can stop
        // the edge is the fence. Before workspace-wide resolution this fixture had a second reason to
        // pass and could not tell them apart.
        Assert.DoesNotContain(await ReadAsync(), a => a.Predicate == "links_to");
    }

    [Fact]
    public async Task ABrokenCrossReferenceIsAGapAndAnUnindexedTargetIsABoundary()
    {
        // DC-050, applied at the point it would have been made. Both are "the link produced no
        // edge", and they are different statements: one is a defect in the document, the other is
        // this product indexing documents that opt in. MEASURED on TheTerrace, the `knowledge:docs`
        // scope discloses 109 broken cross-references.
        //
        // The not-a-node half NOW FIRES ON A REAL CORPUS, and that is the boundary moving out to the
        // workspace root made visible: the 19 candidates in this repository all point at
        // `../../spikes/*/RESULT.md`, and until this change they were counted as "outside this
        // scope" — a boundary claimed where there was none, since the files are right there and
        // simply declare no id. Measured after: 19 on ai-de, 0 on TheTerrace.
        Write("a.md", """
            ---
            id: doc-a
            ---

            See [the moved one](gone.md) and [the plain one](notes.md).
            """);

        Write("notes.md", "# Just a file\n\nNo frontmatter.\n");

        var facts = await ReadAsync();

        Assert.Contains("(1 prose link(s) name a markdown file that is not in this workspace)",
            Disclosure(facts, KnowledgeExtractor.Disclosures.LinkTargetMissing), StringComparison.Ordinal);

        Assert.Contains("(1 prose link(s) resolve to",
            Disclosure(facts, KnowledgeExtractor.Disclosures.LinkTargetNotANode), StringComparison.Ordinal);
    }

    [Fact]
    public async Task ALinkAboveTheWORKSPACEIsItsOwnBoundaryAndAUrlIsNotCountedAsOne()
    {
        // THE DECISION THIS CHANGE REVERSES, rewritten rather than deleted. The boundary used to be
        // the SCOPE: a link one directory up was refused because a wider scope might hold the target
        // and this reader had no way to know. Once each document is emitted by exactly one scope
        // there is no wider scope, so refusing it would mean the edge exists nowhere — measured, that
        // is 30 of 42 prose-link edges (DC-051). The boundary has not been relaxed, it has MOVED to
        // the workspace root, which is the real edge of what this product reads.
        //
        // The escape and the broken link are still different statements: a document outside the
        // workspace may well exist and this reader will not stat paths outside the tree it was given
        // to find out. The URL half is the DC-050 guard on the guard — 329 http links on TheTerrace
        // would have made this count describe something that does not exist.
        //
        // MEASURED: this fires on NEITHER corpus (0 of TheTerrace's 237 prose links and 0 of this
        // repository's escape the workspace), so this fixture is the only thing that proves it works
        // (DC-016). It is kept because a docs tree linking into a sibling checkout is one commit
        // away, and the alternative is calling such a link broken, which is a wrong number.
        Write("inner/a.md", """
            ---
            id: doc-a
            ---

            See [the parent](../../../elsewhere.md) and [the standard](https://example.com/spec.md).
            """);

        var facts = await ReadAsync(Path.Combine(_dir, "inner"));

        Assert.Contains("(1 prose link(s) point above the workspace root)",
            Disclosure(facts, KnowledgeExtractor.Disclosures.LinkTargetOutsideWorkspace),
            StringComparison.Ordinal);

        Assert.False(Discloses(facts, KnowledgeExtractor.Disclosures.LinkTargetMissing));
    }

    [Fact]
    public async Task ALinkAboveTheSCOPEButInsideTheWorkspaceIsAnEdgeRatherThanABoundary()
    {
        // THE OTHER DIRECTION of the policy change, and the one that has to be asserted for the
        // rewrite above to mean anything: the same shape of link — a path climbing out of the
        // emitting scope — is now FOLLOWED when it lands inside the workspace. Without this, moving
        // the boundary out would be indistinguishable from deleting the disclosure.
        Write("inner/a.md", """
            ---
            id: doc-a
            ---

            See [the sibling](../outer/b.md).
            """);

        Write("outer/b.md", """
            ---
            id: doc-b
            ---
            """);

        var facts = await ReadAsync(Path.Combine(_dir, "inner"));

        var edge = Assert.Single(facts, a => a.Predicate == "links_to");

        Assert.Equal("doc-a", edge.Subject);
        Assert.Equal("doc-b", edge.Object);
        Assert.False(Discloses(facts, KnowledgeExtractor.Disclosures.LinkTargetOutsideWorkspace));
    }

    [Fact]
    public async Task AScopeEmitsForItsOwnDirectoryAndNotForTheOneBeneathIt()
    {
        // THE DE-DUPLICATION, at the level of the reader. `docs` and `docs/adr` are both scopes
        // because both hold a document with an id, and a recursive walk had `docs` emit `adr-0001`
        // as well — 2,371 `node_class` rows for 878 distinct documents on TheTerrace.
        //
        // The nested document is still READ: its id is in the workspace survey, which is why the
        // link below resolves. Read widely, emit narrowly — asserting only the absence would pass
        // just as well on a reader that had stopped looking at the directory altogether.
        Write("index.md", """
            ---
            id: doc-index
            ---

            The register is [here](adr/0001.md).
            """);

        Write("adr/0001.md", """
            ---
            id: adr-0001
            ---
            """);

        var facts = await ReadAsync();

        Assert.Contains(facts, a => a.Subject == "doc-index" && a.Predicate == "node_class");
        Assert.DoesNotContain(facts, a => a.Subject == "adr-0001");
        Assert.Contains(facts, a => a.Predicate == "links_to" && a.Object == "adr-0001");
    }

    [Fact]
    public async Task TheHeadingBoundaryCarriesBothCountsAndIsAbsentWhenThereAreNoHeadings()
    {
        // Headings are counted and not extracted, on measured grounds rather than taste: simulated
        // on the real store, 40 heading attributes per scope push `has_type`, `node_class`,
        // `owned_by`, `refines` and `review_by` out of a document's own node card (DC-035). Saying
        // so with the size of what was skipped is the difference between a boundary and a silence.
        Write("structured.md", """
            ---
            id: doc-structured
            ---

            # One
            ## Two
            ### Three
            """);

        Assert.Contains("(3 heading(s) in 1 document(s)",
            Disclosure(await ReadAsync(), KnowledgeExtractor.Disclosures.HeadingsNotAnalysed),
            StringComparison.Ordinal);

        File.Delete(Path.Combine(_dir, "structured.md"));

        Write("flat.md", """
            ---
            id: doc-flat
            ---

            One paragraph, no structure at all.
            """);

        // The other direction. A boundary that is disclosed when nothing was hidden trains a reader
        // to skip the list, which costs the disclosures that matter.
        Assert.False(Discloses(await ReadAsync(), KnowledgeExtractor.Disclosures.HeadingsNotAnalysed));
    }

    [Fact]
    public async Task TheInlineCodeBoundaryStatesTheNoInferenceDecisionWithACount()
    {
        // The user's decision of 2026-08-30, made auditable. Of 26,924 inline code spans in
        // TheTerrace's documents, ZERO exactly name a C# node — so an exact-match code reader could
        // never have fired, and the only way to make it produce anything is the resemblance matching
        // that produced 7,426 false Verified edges once already.
        Write("a.md", """
            ---
            id: doc-a
            ---

            The `AppDbContext` type is configured by `PlatformDataProtectionOptions`.
            """);

        var facts = await ReadAsync();

        Assert.Contains("(2 inline code span(s) are not matched against code symbols)",
            Disclosure(facts, KnowledgeExtractor.Disclosures.InlineCodeNotResolved), StringComparison.Ordinal);

        // And nothing was emitted about them. A backticked name that resembles a type is the exact
        // input the no-inference decision is about.
        Assert.DoesNotContain(facts, a => a.Object.Contains("AppDbContext", StringComparison.Ordinal));
    }

    [Fact]
    public async Task AGlossaryIsRecognisedByItsTypeOrItsNameAndItsTermsAreDisclosedUnread()
    {
        // Both, because both are used: TheTerrace's two glossaries carry `type: glossary`, and this
        // repository's fourteen are `type: knowledge` in a file called `glossary.md`. Their terms
        // are written in three incompatible shapes across the two repositories, and the bare one is
        // indistinguishable from ordinary bold-led prose — the same pattern matches 506 lines in 114
        // NON-glossary documents on TheTerrace.
        Write("by-type.md", """
            ---
            id: gloss-typed
            type: glossary
            ---

            - **Fixture** - one scheduled match.
            """);

        Write("glossary.md", """
            ---
            id: gloss-named
            type: knowledge
            ---

            | Term | Definition |
            |---|---|
            | **SCIP** | A code index format. |
            """);

        var facts = await ReadAsync();

        Assert.Contains("(2 document(s) declare themselves a glossary",
            Disclosure(facts, KnowledgeExtractor.Disclosures.GlossaryTermsNotAnalysed),
            StringComparison.Ordinal);

        // Counted, and not read. A term is a PROPERTY of its glossary, so extracting one would be an
        // attribute — and on `knowledge-epl-glossary` that costs 14 of its 17 `uses-term` backlinks.
        Assert.DoesNotContain(facts, a => a.Object.Contains("Fixture", StringComparison.Ordinal));
        Assert.DoesNotContain(facts, a => a.Object.Contains("SCIP", StringComparison.Ordinal));
    }

    [Fact]
    public async Task ANonGlossaryDocumentDoesNotTripTheGlossaryBoundary()
    {
        // The other direction of the same control. Bold-led bullets are ordinary prose in both
        // corpora, and a boundary claiming a glossary where there is none is a wrong number.
        Write("a.md", """
            ---
            id: doc-a
            type: design
            ---

            - **Durability** - the ledger survives a restore.
            """);

        Assert.False(Discloses(
            await ReadAsync(), KnowledgeExtractor.Disclosures.GlossaryTermsNotAnalysed));
    }

    [Fact]
    public async Task NoDisclosureFiresOnAScopeWithNothingToHide()
    {
        // The whole reason `knowledge-body-not-analysed` had to go. It fired on every scope forever,
        // whether or not anything had been hidden, and it would now be FALSE on any scope whose
        // prose links resolve — the Python reader's `imports-not-resolved` lesson, one file along.
        Write("a.md", """
            ---
            id: doc-a
            type: adr
            owner: "@someone"
            ---

            One sentence of prose and nothing else.
            """);

        Assert.DoesNotContain(await ReadAsync(), a => a.Predicate == "discloses");
    }

    [Fact]
    public async Task TheFrontmatterBlockIsNotSurveyedAsProse()
    {
        // FIRST WRITTEN AGAINST AN UNTERMINATED BLOCK, and the mutation that should have killed it
        // survived: there are ZERO unterminated frontmatter blocks in either corpus, and the fixture
        // contained no line a body survey would read differently. The fixture could not reproduce
        // what it guarded, which is the third time that has happened here.
        //
        // Re-grounded on what the corpora DO contain: 15 frontmatter lines across the two
        // repositories open with `#` — `# ---- Prior revisions ----` in the pack's INSTALL.md,
        // `# Syntax palette ...` in DESIGN.md. Surveyed as prose they are headings, and the
        // boundary's count would be wrong on the documents that carry them.
        Write("a.md", """
            ---
            id: doc-a
            type: adr
            # ---- Prior revisions ----
            links:
              - { to: doc-b, rel: refines }
            ---

            One line of prose, and no headings at all.
            """);

        var facts = await ReadAsync();

        Assert.False(Discloses(facts, KnowledgeExtractor.Disclosures.HeadingsNotAnalysed));
        Assert.DoesNotContain(facts, a => a.Predicate == "links_to");
    }

    [Theory]
    // A sibling directory whose name STARTS with the root's is not inside it. Without the trailing
    // separator on the prefix test, `docs-old` resolves as though it were under `docs`.
    [InlineData("../docs-old/x.md", false)]
    [InlineData("../x.md", false)]
    [InlineData("sub/x.md", true)]
    [InlineData("./x.md", true)]
    [InlineData("/x.md", false)]
    [InlineData("https://example.com/x.md", false)]
    [InlineData("x.html", false)]
    [InlineData("x.cs", false)]
    public void OnlyAMarkdownPathInsideTheResolutionRootResolves(string target, bool expected)
    {
        // The ROOT passed here is now the workspace, not the scope — the same containment check, one
        // level out. The cases are unchanged because the rule is: a path is refused by WHERE IT
        // LANDS, whatever the root happens to be. What changed is which root the caller supplies,
        // and `ALinkAboveTheSCOPEButInsideTheWorkspaceIsAnEdgeRatherThanABoundary` is where that is
        // pinned.
        var root = Path.Combine(_dir, "docs");
        var from = Path.Combine(root, "a.md");

        Assert.Equal(expected, KnowledgeExtractor.Resolve(from, target, root) is not null);
    }
}
