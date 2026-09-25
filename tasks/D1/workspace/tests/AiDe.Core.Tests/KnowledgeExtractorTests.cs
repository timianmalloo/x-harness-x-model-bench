using AiDe.Core.Extraction;
using AiDe.Core.Facts;

namespace AiDe.Core.Tests;

/// <summary>
/// The knowledge graph, which was returning zero because nothing ever looked.
/// </summary>
/// <remarks>
/// <para><b>Reported by the user: the graph showed knowledge as ZERO and code as a large count.</b>
/// A reader for these documents had existed since Phase 1, with tests, and scope discovery produced
/// six kinds of scope — none of them knowledge. The capability was real, tested, and unreachable on
/// any real repository, so the answer to "how much knowledge is here" was computed over nothing.</para>
///
/// <para><b>A zero that means "nobody looked" reads as "there is none",</b> which is the shape this
/// product exists to avoid — and it was in the product's own headline surface, on a repository whose
/// premise is that docs hold intent and code holds reality. MEASURED after the fix, on this
/// repository: 466 <c>owned_by</c>, 346 <c>refines</c>, 287 <c>implements</c>, 272
/// <c>relates-to</c>, 66 <c>depends-on</c>.</para>
/// </remarks>
public sealed class KnowledgeExtractorTests : IDisposable
{
    private readonly string _dir = Path.Combine(
        Path.GetTempPath(), "aide-kb", Guid.NewGuid().ToString("N"));

    public KnowledgeExtractorTests() => Directory.CreateDirectory(_dir);

    public void Dispose()
    {
        try { Directory.Delete(_dir, recursive: true); } catch (IOException) { }
    }

    private void Write(string name, string content) =>
        File.WriteAllText(Path.Combine(_dir, name), content);

    private async Task<IReadOnlyList<EvidenceAssertion>> ReadAsync()
    {
        var result = await new KnowledgeExtractor().ExtractAsync(
            new ExtractionRequest("knowledge:docs", _dir, "rev-1", 1), CancellationToken.None);

        return result.Assertions;
    }

    [Fact]
    public async Task ADocumentBecomesANodeWithItsTypeOwnerAndLinks()
    {
        Write("adr-0001.md", """
            ---
            id: adr-0001-fact-store
            type: adr
            owner: "@someone"
            links:
              - { to: spec-workspace, rel: implements }
              - { to: adr-0002-daemon, rel: depends-on }
            ---

            # A decision
            """);

        var facts = await ReadAsync();

        Assert.Contains(facts, a => a.Subject == "adr-0001-fact-store" && a.Predicate == "has_type" && a.Object == "adr");
        Assert.Contains(facts, a => a.Subject == "adr-0001-fact-store" && a.Predicate == "owned_by" && a.Object == "@someone");
        Assert.Contains(facts, a => a.Predicate == "implements" && a.Object == "spec-workspace");
        Assert.Contains(facts, a => a.Predicate == "depends-on" && a.Object == "adr-0002-daemon");
    }

    [Fact]
    public async Task ATrailingCommentIsNotPartOfTheRelation()
    {
        // FOUND ON THIS REPOSITORY, by running the reader over real documents rather than fixtures.
        // The link lines carry a trailing YAML comment, and trimming from the END left it attached:
        // the graph gained a relation called `implements }   # typed edges — registry in …`.
        Write("note.md", """
            ---
            id: note-1
            type: decision-note
            links:
              - { to: other-note, rel: implements }   # typed edges — registry in knowledge-visualization.md V14
            ---
            """);

        var facts = await ReadAsync();

        Assert.Contains(facts, a => a.Predicate == "implements" && a.Object == "other-note");
        Assert.DoesNotContain(facts, a => a.Predicate.Contains('#', StringComparison.Ordinal));
        Assert.DoesNotContain(facts, a => a.Predicate.Contains('}', StringComparison.Ordinal));
    }

    [Fact]
    public async Task ATemplateIsNotANode()
    {
        // Also found on this repository. A template carries frontmatter in exactly the shape a real
        // document does, with placeholders where the values go — so it becomes a node describing the
        // SHAPE of a document, linked to things that do not exist.
        Write("adr.template.md", """
            ---
            id: <artifact-id>
            type: adr
            links:
              - { to: <upstream-artifact-id>, rel: implements }
            ---
            """);

        var facts = await ReadAsync();

        Assert.DoesNotContain(facts, a => a.Subject.StartsWith('<'));
        Assert.DoesNotContain(facts, a => a.Object.StartsWith('<'));
    }

    [Fact]
    public async Task APlaceholderIdIsNotAnIdEvenOutsideATemplateFile()
    {
        // The file-name rule catches the convention; this catches the content. Both are needed —
        // a template copied to a real name still carries placeholders until somebody fills them in.
        Write("copied.md", """
            ---
            id: <artifact-id>
            type: adr
            ---
            """);

        Assert.DoesNotContain(await ReadAsync(), a => a.Subject.StartsWith('<'));
    }

    [Fact]
    public async Task OrdinaryMarkdownIsNotANodeAndIsNotAComplaint()
    {
        // Every repository is full of README files. They are not nodes and they are not broken.
        Write("README.md", "# Just a readme\n\nNo frontmatter here.\n");

        var facts = await ReadAsync();

        Assert.DoesNotContain(facts, a => a.Predicate == "has_type");
        Assert.DoesNotContain(facts,
            a => a.Object.StartsWith(KnowledgeExtractor.Disclosures.ArtifactsWithoutIds, StringComparison.Ordinal));
    }

    [Fact]
    public async Task ADocumentThatMEANTToBeANodeAndCannotIsCountedAndDisclosed()
    {
        // Frontmatter with no id is a defect IN THAT DOCUMENT, distinct from a file that was never
        // meant to join the graph. Collapsing the two reports every README as broken, or hides this.
        Write("broken.md", """
            ---
            type: adr
            owner: "@someone"
            ---
            """);

        var facts = await ReadAsync();

        Assert.Contains(facts,
            a => a.Object.StartsWith(KnowledgeExtractor.Disclosures.ArtifactsWithoutIds, StringComparison.Ordinal));
    }

    [Fact]
    public async Task ADocumentWithNoDeclaredTypeIsUnverifiedRatherThanOmitted()
    {
        // "Its kind is unknown" and "it has no kind" are different claims, and the second is one
        // this reader cannot make.
        Write("untyped.md", """
            ---
            id: untyped-1
            ---
            """);

        var fact = Assert.Single(await ReadAsync(), a => a.Subject == "untyped-1" && a.Predicate == "has_type");

        Assert.Equal("unknown", fact.Object);
        Assert.Equal(VerificationStatus.Unverified, fact.Status);
    }

    [Fact]
    public void TheRouterSendsKnowledgeScopesToThisExtractor() =>
        Assert.Equal("knowledge", WorkspaceExtractors.RoutedKinds["knowledge:"]);

    [Fact]
    public void EveryRouteHasAProducerAndEveryProducerHasARoute()
    {
        // THE CONTROL FOR DC-041. The knowledge reader was correct, tested, and unreachable for the
        // whole life of the project because discovery emitted six scope kinds and the router
        // answered for a seventh nobody produced. Both sides passed their own tests; only the
        // comparison between them was missing, and it was being made in somebody's head.
        var root = Path.Combine(_dir, "repo");
        Directory.CreateDirectory(Path.Combine(root, "docs"));
        Directory.CreateDirectory(Path.Combine(root, "pkg"));
        Directory.CreateDirectory(Path.Combine(root, "web"));
        Directory.CreateDirectory(Path.Combine(root, "db"));

        File.WriteAllText(Path.Combine(root, "docs", "adr.md"), """
            ---
            id: adr-1
            type: adr
            ---
            """);

        File.WriteAllText(Path.Combine(root, "pkg", "mod.py"), """
            class Thing:
                pass
            """);

        File.WriteAllText(Path.Combine(root, "web", "app.ts"), "export class App {}");
        File.WriteAllText(Path.Combine(root, "db", "schema.sql"), "CREATE TABLE T (Id INT);");
        File.WriteAllText(Path.Combine(root, "main.bicep"), "param name string");

        var discovered = CSharpScopeDiscovery
            .DiscoverAll(root, new CSharpProjectReader())
            .Select(s => s.ScopeId[..(s.ScopeId.IndexOf(':', StringComparison.Ordinal) + 1)])
            .ToHashSet(StringComparer.Ordinal);

        var routed = WorkspaceExtractors.RoutedKinds.Keys.ToHashSet(StringComparer.Ordinal);

        // A discovered kind with no route falls to the fallback and is read by the wrong reader.
        Assert.True(discovered.IsSubsetOf(routed),
            $"discovery emits {string.Join(", ", discovered.Except(routed))} with no route");

        // A route with no producer is a reader that can never run — which is what happened here.
        // `schema:` is exempt: it needs an EF Migrations directory, which this fixture has no
        // reasonable way to fake, and it is covered by its own tests.
        var unreachable = routed.Except(discovered).Except(["csharp:", "schema:"]).ToList();

        Assert.True(unreachable.Count == 0,
            $"nothing discovers work for {string.Join(", ", unreachable)} — the reader can never run");
    }
}
