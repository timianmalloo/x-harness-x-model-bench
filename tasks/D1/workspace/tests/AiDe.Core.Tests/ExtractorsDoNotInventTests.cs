using AiDe.Core.Extraction;
using AiDe.Core.Facts;

namespace AiDe.Core.Tests;

/// <summary>
/// Every extractor, fed input that only LOOKS like its notation, must produce nothing.
/// </summary>
/// <remarks>
/// <para><b>The invent-direction of DC-033, made a control instead of a habit.</b> That class was
/// registered for readers that recognise one spelling and report the rest as absent. The same root
/// cause runs the other way and is worse: the `uses_table` reader matched a SQL keyword anywhere in
/// a string, so the sentence <i>"we update the record"</i> became an edge to a table called
/// <c>the</c> — 63 such strings in one repository, and the count fell from 150 to 56 once the reader
/// required a statement shape. A missing fact is a gap; an invented one arrives labelled
/// <b>Verified</b> and is believed.</para>
///
/// <para><b>Why a shared test rather than one per extractor.</b> The finding was manual, on one
/// repository, for one reader. Nothing stopped the next reader repeating it, and "remember to check
/// for prose" is the kind of lesson that lives in prose. Each extractor here is fed a corpus with no
/// declarations at all and plenty of text SHAPED like declarations: comments containing real syntax,
/// documentation quoting keywords, config that reuses the same words.</para>
///
/// <para><b>Disclosures are exempt and nothing else is.</b> A reader saying what it could not see is
/// the honest half of every one of these; a reader saying what is there when nothing is, is the
/// defect.</para>
/// </remarks>
public sealed class ExtractorsDoNotInventTests : IDisposable
{
    private readonly string _dir = Path.Combine(
        Path.GetTempPath(), "aide-noise", Guid.NewGuid().ToString("N"));

    public ExtractorsDoNotInventTests() => Directory.CreateDirectory(_dir);

    public void Dispose()
    {
        try { Directory.Delete(_dir, recursive: true); } catch (IOException) { }
    }

    private string Write(string relative, string content)
    {
        var path = Path.Combine(_dir, relative.Replace('/', Path.DirectorySeparatorChar));
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        File.WriteAllText(path, content);
        return path;
    }

    /// <summary>Facts that claim something exists, as opposed to admitting what was not read.</summary>
    private static IReadOnlyList<EvidenceAssertion> Claims(ExtractionResult result) =>
        [.. result.Assertions.Where(a => a.Predicate != "discloses")];

    private static string Describe(IEnumerable<EvidenceAssertion> claims) =>
        string.Join("; ", claims.Take(5).Select(a => $"{a.Subject} {a.Predicate} {a.Object}"));

    [Fact]
    public async Task TheSqlReaderDoesNotReadCommentsOrProse()
    {
        // A commented-out CREATE TABLE is a table that does not exist. So is one described in a
        // header comment explaining what the script WILL do.
        Write("schema.sql", """
            -- This script used to CREATE TABLE Ghost (Id INT) before we moved it.
            -- TODO: CREATE TABLE Planned (Id INT);
            /* CREATE TABLE Historical (Id INT); */
            PRINT 'about to create table Something';
            """);

        var result = await new SqlSchemaExtractor().ExtractAsync(
            new ExtractionRequest("sql:schema", _dir, "rev-1", 1), CancellationToken.None);

        var claims = Claims(result);
        Assert.True(claims.Count == 0, $"invented: {Describe(claims)}");
    }

    [Fact]
    public async Task TheTypeScriptReaderDoesNotReadCommentedOutCode()
    {
        // A block comment whose lines begin at column zero is exactly what a line-oriented reader
        // cannot tell from code, and is exactly what a file of examples looks like.
        Write("module.ts", """
            /*
            export class Removed {}
            export interface AlsoRemoved {}
            */
            // export class LineCommented {}
            const notExported = 1;
            """);

        var result = await new TypeScriptExtractor().ExtractAsync(
            new ExtractionRequest("typescript:.", _dir, "rev-1", 1), CancellationToken.None);

        var claims = Claims(result).Where(a => a.Object != "typescript-module").ToList();
        Assert.True(claims.Count == 0, $"invented: {Describe(claims)}");
    }

    [Fact]
    public async Task ThePythonReaderDoesNotReadCommentedOutCode()
    {
        Write("mod.py", """
            # class Removed:
            # def removed():
            '''
            class DocstringExample:
                pass
            '''
            value = 1
            """);

        var result = await new PythonExtractor().ExtractAsync(
            new ExtractionRequest("python:.", _dir, "rev-1", 1), CancellationToken.None);

        var claims = Claims(result).Where(a => a.Object != "python-module").ToList();
        Assert.True(claims.Count == 0, $"invented: {Describe(claims)}");
    }

    [Fact]
    public async Task TheCSharpReaderDoesNotTurnProseIntoSchema()
    {
        // THE ORIGINAL DEFECT. Every string here contains a SQL keyword and none is SQL.
        var project = Write("Prose/Prose.csproj", """
            <Project Sdk="Microsoft.NET.Sdk">
              <PropertyGroup><TargetFramework>net10.0</TargetFramework></PropertyGroup>
            </Project>
            """);

        Write("Prose/Copy.cs", """
            namespace Shop;

            public class Copy
            {
                public string A => "Suggests a scoreline from the table, form and team news.";
                public string B => "We update the record when a member joins.";
                public string C => "Answers a member's own question from the club's data.";
                public string D => "delete from your account to remove it";
            }
            """);

        var result = await new CSharpExtractor().ExtractAsync(
            new ExtractionRequest("csharp:Prose:net10.0", project, "rev-1", 1), CancellationToken.None);

        var invented = result.Assertions.Where(a => a.Predicate == "uses_table").ToList();
        Assert.True(invented.Count == 0, $"invented: {Describe(invented)}");
    }

    [Fact]
    public async Task TheBicepReaderDoesNotReadAResourceOutOfAComment()
    {
        // MEASURED first, then pinned: the Bicep matchers are line-anchored on `resource`, `module`
        // and `param`, and a sweep of a repository they were not written against found no invented
        // values — real parameter names and real Azure types only. This keeps that true.
        var template = Write("infra/main.bicep", """
            // resource ghost 'Microsoft.Storage/storageAccounts@2023-01-01' = {
            //   name: 'ghostAccount'
            // }
            @description('A parameter that mentions resource and module in its text.')
            param realParam string
            """);

        var result = await new BicepExtractor().ExtractAsync(
            new ExtractionRequest("bicep:main", template, "rev-1", 1), CancellationToken.None);

        var resources = result.Assertions
            .Where(a => a.Predicate == "has_type" && a.Object == "azure-resource")
            .ToList();

        Assert.True(resources.Count == 0, $"invented: {Describe(resources)}");
    }

    [Fact]
    public async Task BlankingCommentsKeepsProvenanceLineNumbersTrue()
    {
        // The reason comments are BLANKED rather than deleted, asserted rather than assumed. A
        // reader that reports the wrong line is one nobody can follow back to the source, and the
        // whole point of provenance is that a claim can be opened and checked.
        Write("schema.sql", """
            -- a comment
            /* a
               multi-line
               comment */
            CREATE TABLE OnLineSix (Id INT);
            """);

        var result = await new SqlSchemaExtractor().ExtractAsync(
            new ExtractionRequest("sql:schema", _dir, "rev-1", 1), CancellationToken.None);

        var table = Assert.Single(result.Assertions,
            a => a.Subject == "table:OnLineSix" && a.Predicate == "has_type");

        Assert.Equal("5:1", table.Provenance.SourceLocation);
    }

    [Fact]
    public async Task TheBicepReaderIgnoresACommentedOutResourceToo()
    {
        // The last line-oriented reader still parsing raw text. It passed this control before the
        // stripping was added; this keeps it passing for the reason rather than by luck.
        Write("infra/main.bicep", """
            // resource ghost 'Microsoft.Storage/storageAccounts@2023-01-01' = {
            //   name: 'ghostAccount'
            // }
            /* resource alsoGhost 'Microsoft.KeyVault/vaults@2023-01-01' = {
                 name: 'ghostVault'
               } */
            param realParam string
            """);

        var result = await new BicepExtractor().ExtractAsync(
            new ExtractionRequest("bicep:main", Path.Combine(_dir, "infra", "main.bicep"), "rev-1", 1),
            CancellationToken.None);

        Assert.DoesNotContain(result.Assertions,
            a => a.Predicate == "has_type" && a.Object == "azure-resource");

        // And the real declaration beside them is still read.
        Assert.Contains(result.Assertions,
            a => a.Predicate == "has_type" && a.Object == "azure-parameter");
    }

    [Fact]
    public async Task TheKnowledgeReaderDoesNotTurnProseIntoLinks()
    {
        // The reader that reads DOCUMENTS, on the corpus most likely to fool it: documents about
        // links. The `uses_table` reader turned "we update the record" into a table called `the`;
        // the same shape here is a document that quotes a link, names another document in prose, or
        // spells an id in backticks — and every one of those is a real sentence in this repository.
        //
        // MEASURED before the reader was written: 372 backticked spans across TheTerrace's documents
        // exactly match another document's id, and `architecture` — an id here — names an MCP tool
        // in 4 of its 5 occurrences. A name collides (DC-022), so none of them is read.
        Write("docs/guide.md", """
            ---
            id: doc-guide
            type: doc
            ---

            # Writing a cross-reference

            The target document is `spec-workspace`, and its file is at specs/workspace.md.
            Never write the id and the path and expect a link: see spec-workspace, or the
            architecture, or `AppDbContext`, and nothing here is an edge.

            Spell it like this:

            ```markdown
            [the workspace spec](specs/workspace.md)
            ```
            """);

        Write("docs/specs/workspace.md", """
            ---
            id: spec-workspace
            type: spec
            ---

            # Workspace
            """);

        var result = await new KnowledgeExtractor().ExtractAsync(
            new ExtractionRequest("knowledge:docs", Path.Combine(_dir, "docs"), "rev-1", 1),
            CancellationToken.None);

        var invented = Claims(result)
            .Where(a => a.Predicate == "links_to")
            .ToList();

        Assert.True(invented.Count == 0, $"the knowledge reader invented: {Describe(invented)}");
    }

    [Fact]
    public async Task AnEmptyWorkspaceProducesNoClaimsAtAll()
    {
        // The floor. A reader that finds something in nothing has no lower bound on what it will
        // find in noise.
        Write("notes.txt", "CREATE TABLE, export class, def thing, resource foo — all just words.");

        foreach (var (extractor, scope) in new (IExtractor, string)[]
        {
            (new SqlSchemaExtractor(), "sql:."),
            (new PythonExtractor(), "python:."),
            (new TypeScriptExtractor(), "typescript:."),
            (new KnowledgeExtractor(), "knowledge:."),
        })
        {
            var result = await extractor.ExtractAsync(
                new ExtractionRequest(scope, _dir, "rev-1", 1), CancellationToken.None);

            var claims = Claims(result);
            Assert.True(claims.Count == 0, $"{extractor.GetType().Name} invented: {Describe(claims)}");
        }
    }
}
