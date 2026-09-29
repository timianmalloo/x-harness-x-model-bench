using AiDe.Core.Extraction;

namespace AiDe.Core.Tests;

/// <summary>
/// Which type talks to which table, for repositories with no ORM at all.
/// </summary>
/// <remarks>
/// <para><b>The honest answer to "verified joins for non-EF repositories".</b> BioHacker has zero
/// `DbContext` files, zero `[Table]` attributes and 191 SQL literals naming tables from inside store
/// classes — so every join it had was a NAME GUESS, and there was no declaration anywhere to make a
/// verified one from.</para>
///
/// <para>There still isn't. A store class issuing four statements against three tables is not MAPPED
/// to any of them, and reusing <c>maps_to</c> would put a confident wrong answer where an honest one
/// belongs. What the source does declare is USAGE, and that is what this emits: 62 edges on that
/// repository, verified because the literal is right there in the type.</para>
/// </remarks>
public sealed class SqlUsageTests : IDisposable
{
    private readonly string _dir = Path.Combine(
        Path.GetTempPath(), "aide-usage", Guid.NewGuid().ToString("N"));

    public SqlUsageTests() => Directory.CreateDirectory(_dir);

    public void Dispose()
    {
        try { Directory.Delete(_dir, recursive: true); } catch (IOException) { }
    }

    private async Task<IReadOnlyList<AiDe.Core.Facts.EvidenceAssertion>> ReadAsync(string source)
    {
        File.WriteAllText(Path.Combine(_dir, "Usage.csproj"), """
            <Project Sdk="Microsoft.NET.Sdk">
              <PropertyGroup><TargetFramework>net10.0</TargetFramework></PropertyGroup>
            </Project>
            """);

        File.WriteAllText(Path.Combine(_dir, "Store.cs"), source);

        var result = await new CSharpExtractor().ExtractAsync(
            new ExtractionRequest("csharp:Usage:net10.0", Path.Combine(_dir, "Usage.csproj"), "rev-1", 1),
            CancellationToken.None);

        return result.Assertions;
    }

    [Fact]
    public async Task ATypeThatQueriesATableSaysSo()
    {
        var facts = await ReadAsync("""
            namespace Shop;

            public class OrderStore
            {
                public string Sql => "SELECT Id FROM dbo.Orders WHERE Id=@id";
            }
            """);

        Assert.Contains(facts, a =>
            a.Subject == "Shop.OrderStore" && a.Predicate == "uses_table" && a.Object == "table:Orders");
    }

    [Fact]
    public async Task ItIsUsageAndNotMapping()
    {
        // A store issuing statements against three tables is mapped to none of them. Reusing
        // `maps_to` would launder usage into a mapping at exactly the point a reader trusts it.
        var facts = await ReadAsync("""
            namespace Shop;

            public class Store
            {
                public string A => "SELECT * FROM Orders";
                public string B => "INSERT INTO Lines (Id) VALUES (1)";
                public string C => "UPDATE Invoices SET Paid=1";
            }
            """);

        Assert.Equal(3, facts.Count(a => a.Predicate == "uses_table"));
        Assert.DoesNotContain(facts, a => a.Predicate == "maps_to");
    }

    [Theory]
    [InlineData("SELECT * FROM Orders", "table:Orders")]
    [InlineData("SELECT * FROM dbo.Orders", "table:Orders")]
    [InlineData("SELECT * FROM [dbo].[Orders]", "table:Orders")]
    [InlineData("INSERT INTO Orders (Id) VALUES (1)", "table:Orders")]
    [InlineData("UPDATE Orders SET X=1", "table:Orders")]
    [InlineData("DELETE FROM Orders WHERE Id=1", "table:Orders")]
    [InlineData("SELECT * FROM A JOIN Orders ON A.Id=Orders.Id", "table:Orders")]
    public async Task TheStatementFormsAndSpellingsThatNameATable(string sql, string expected)
    {
        // The schema qualifier is stripped so dbo.Orders and Orders are ONE node: the EF and SQL
        // readers both emit unqualified names, and a third spelling would point these edges at nodes
        // that do not exist while looking perfectly correct.
        var facts = await ReadAsync($$"""
            namespace Shop;

            public class Store
            {
                public string Sql => "{{sql}}";
            }
            """);

        Assert.Contains(facts, a => a.Predicate == "uses_table" && a.Object == expected);
    }

    [Fact]
    public async Task ProseThatMENTIONSAKeywordIsNotAStatement()
    {
        // THE DEFECT THIS FILE SHIPPED AND THEN CAUGHT. Matching `UPDATE\s+(\w+)` anywhere in a
        // string turns the sentence "update the record" into an edge to a table called `the`.
        // MEASURED: 63 prose strings in one repository would have produced confident wrong edges,
        // and removing them took that repository's uses_table count from 150 to 56.
        //
        // A SQL literal is a STATEMENT. English sentences do not begin with SELECT or UPDATE.
        var facts = await ReadAsync("""
            namespace Shop;

            public class Copy
            {
                public string A => "Suggests a scoreline from the table, form and team news.";
                public string B => "We update the record when a member joins.";
                public string C => "declared in AiProviders.All but absent from the registry";
            }
            """);

        Assert.DoesNotContain(facts, a => a.Predicate == "uses_table");
    }

    [Fact]
    public async Task SqlSplitAcrossConcatenatedLiteralsIsReadAsOneStatement()
    {
        // Real code writes SQL this way, and the piece holding the table does not begin with a verb.
        // Reading fragments individually is what let prose through; demanding a verb of each
        // fragment found nothing at all on the repository that motivated the feature. The chain is
        // one constant, so it is read as one.
        var facts = await ReadAsync("""
            namespace Shop;

            public class JobStore
            {
                public string Sql =>
                    "SELECT TOP 1 JobId, State " +
                    "FROM dbo.AssessmentJob ORDER BY CreatedUtc DESC;";
            }
            """);

        Assert.Contains(facts, a =>
            a.Subject == "Shop.JobStore" && a.Predicate == "uses_table" && a.Object == "table:AssessmentJob");
    }

    [Fact]
    public async Task AChainContainingSomethingBuiltAtRuntimeIsNotRead()
    {
        // A table name assembled at runtime is exactly what the literal-only rule excludes. Folding
        // only the literal halves would read `"SELECT * FROM " + table` as naming no table, or
        // worse, as naming whatever followed.
        var facts = await ReadAsync("""
            namespace Shop;

            public class Dynamic
            {
                private const string Name = "Orders";
                public string Sql => "SELECT * FROM " + Name;
            }
            """);

        Assert.DoesNotContain(facts, a => a.Predicate == "uses_table");
    }

    [Fact]
    public async Task ASecondStatementInTheSameLiteralIsAlsoRead()
    {
        // One literal often carries several statements separated by semicolons, and only the first
        // would be considered if the shape test looked at the start of the string alone.
        var facts = await ReadAsync("""
            namespace Shop;

            public class Cleanup
            {
                public string Sql => "DELETE FROM Candidate WHERE Id=@i; DELETE FROM UploadJob WHERE Id=@i;";
            }
            """);

        Assert.Contains(facts, a => a.Predicate == "uses_table" && a.Object == "table:Candidate");
        Assert.Contains(facts, a => a.Predicate == "uses_table" && a.Object == "table:UploadJob");
    }

    [Fact]
    public async Task ATemporaryOrVariableTableIsNotASchemaTable()
    {
        var facts = await ReadAsync("""
            namespace Shop;

            public class Store
            {
                public string A => "SELECT * FROM #Scratch";
                public string B => "SELECT * FROM @Rows";
            }
            """);

        Assert.DoesNotContain(facts, a => a.Predicate == "uses_table");
    }

    [Fact]
    public async Task TheSameTableNamedTwiceInOneTypeIsOneFact()
    {
        // This crashed the indexer on a real repository: identical triples hit the store's natural
        // key as a raw SQLite constraint error from the middle of a run. The key is right; the
        // duplicate carried no information.
        var facts = await ReadAsync("""
            namespace Shop;

            public class Store
            {
                public string A => "SELECT * FROM Orders";
                public string B => "DELETE FROM Orders";
            }
            """);

        Assert.Single(facts, a => a.Predicate == "uses_table" && a.Object == "table:Orders");
    }

    [Fact]
    public async Task AStringWithNoTableAfterTheKeywordYieldsNothing()
    {
        // `FROM (SELECT ...)` names no table. A guess here produces an edge to a node that does not
        // exist, which reads as a schema the repository does not have.
        var facts = await ReadAsync("""
            namespace Shop;

            public class Store
            {
                public string A => "SELECT * FROM (SELECT 1) x";
                public string B => "just a sentence with the word from in it";
            }
            """);

        Assert.DoesNotContain(facts, a => a.Predicate == "uses_table" && a.Object.Contains("SELECT"));
    }
}
