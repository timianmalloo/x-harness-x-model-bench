using AiDe.Core.Extraction;

namespace AiDe.Core.Tests;

/// <summary>
/// Tables declared in raw SQL, for repositories whose schema is not EF migrations.
/// </summary>
/// <remarks>
/// <para><b>Found by measuring a SECOND repository.</b> BioHacker declares its whole schema in one
/// 197-line file with eight <c>CREATE TABLE</c> statements. The tool said
/// <c>sql-not-analysed (2 file(s))</c> and produced <b>zero</b> joins — honest, and blind to the
/// entire schema side of that codebase. Every measurement before it came from a repository that
/// happened to use EF. After this: 54 <c>has_column</c> facts and 8 joins.</para>
/// </remarks>
public sealed class SqlSchemaExtractorTests : IDisposable
{
    private readonly string _dir = Path.Combine(
        Path.GetTempPath(), "aide-sql", Guid.NewGuid().ToString("N"));

    public SqlSchemaExtractorTests() => Directory.CreateDirectory(_dir);

    public void Dispose()
    {
        try { Directory.Delete(_dir, recursive: true); } catch (IOException) { }
    }

    private async Task<IReadOnlyList<AiDe.Core.Facts.EvidenceAssertion>> ReadAsync(string sql)
    {
        File.WriteAllText(Path.Combine(_dir, "schema.sql"), sql);

        var result = await new SqlSchemaExtractor().ExtractAsync(
            new ExtractionRequest("sql:schema", _dir, "rev-1", 1), CancellationToken.None);

        return result.Assertions;
    }

    [Fact]
    public async Task ATableBecomesTheSameKindOfNodeTheEfReaderProduces()
    {
        // The same vocabulary on purpose: the join projection already reads `table:` / has_type
        // table / has_column. A second spelling would be DC-022 with two producers of one
        // predicate, and the joins would silently see half the tables.
        var facts = await ReadAsync("CREATE TABLE dbo.Principal (Id INT NOT NULL, Name NVARCHAR(200));\n");

        Assert.Contains(facts, a => a.Subject == "table:Principal" && a.Predicate == "has_type" && a.Object == "table");
        Assert.Contains(facts, a => a.Subject == "table:Principal" && a.Predicate == "has_column" && a.Object == "Id");
        Assert.Contains(facts, a => a.Subject == "table:Principal" && a.Predicate == "has_column" && a.Object == "Name");
    }

    [Theory]
    // The spellings a real script actually uses.
    [InlineData("CREATE TABLE Thing (Id INT);")]
    [InlineData("CREATE TABLE dbo.Thing (Id INT);")]
    [InlineData("CREATE TABLE [dbo].[Thing] (Id INT);")]
    [InlineData("create table \"main\".\"Thing\" (Id INT);")]
    [InlineData("CREATE TABLE IF NOT EXISTS Thing (Id INT);")]
    public async Task TheSchemaQualifierAndQuotingAreStrippedToOneNode(string sql)
    {
        // dbo.Principal and Principal must be ONE node: the EF reader emits unqualified names, and
        // two spellings of one table leaves the joins matching half of them — invisibly, because
        // each spelling looks correct on its own.
        var facts = await ReadAsync(sql + "\n");

        Assert.Contains(facts, a => a.Subject == "table:Thing" && a.Predicate == "has_type");
    }

    [Fact]
    public async Task ANestedParenthesisDoesNotEndTheColumnList()
    {
        // A naive scan to the first ')' stops inside DECIMAL(9,2) and silently truncates every
        // column after it — the columns would simply be absent, with nothing to say so.
        var facts = await ReadAsync("""
            CREATE TABLE Money (
                Id INT NOT NULL,
                Amount DECIMAL(9,2) NOT NULL,
                Note NVARCHAR(400) NULL
            );
            """);

        var columns = facts.Where(a => a.Predicate == "has_column").Select(a => a.Object).ToList();

        Assert.Equal(["Id", "Amount", "Note"], columns);
    }

    [Fact]
    public async Task AConstraintLineIsNotClaimedAsAColumn()
    {
        var facts = await ReadAsync("""
            CREATE TABLE Ordered (
                Id INT NOT NULL,
                CONSTRAINT PK_Ordered PRIMARY KEY (Id),
                PRIMARY KEY (Id)
            );
            """);

        var columns = facts.Where(a => a.Predicate == "has_column").Select(a => a.Object).ToList();

        Assert.Equal(["Id"], columns);
    }

    [Fact]
    public async Task EveryTableInAScriptIsRead()
    {
        var facts = await ReadAsync("""
            CREATE TABLE A (Id INT);
            GO
            CREATE TABLE B (Id INT, Other NVARCHAR(10));
            """);

        Assert.Contains(facts, a => a.Subject == "table:A" && a.Predicate == "has_type");
        Assert.Contains(facts, a => a.Subject == "table:B" && a.Predicate == "has_type");
    }

    /// <summary>Writes one script and folds the scope, so ordering can be exercised.</summary>
    private async Task<IReadOnlyList<AiDe.Core.Facts.EvidenceAssertion>> FoldAsync(
        params (string Name, string Sql)[] scripts)
    {
        foreach (var (name, sql) in scripts)
        {
            File.WriteAllText(Path.Combine(_dir, name), sql);
        }

        var result = await new SqlSchemaExtractor().ExtractAsync(
            new ExtractionRequest("sql:schema", _dir, "rev-1", 1), CancellationToken.None);

        return result.Assertions;
    }

    [Fact]
    public async Task ScriptsAreFoldedInOrder_SoTheSchemaIsTheSumAndNotTheFirstScript()
    {
        // MEASURED: one real repository carries 125 `ALTER TABLE ... ADD` statements. Reading CREATE
        // alone shows its schema as it stood at the first migration and calls that current.
        var facts = await FoldAsync(
            ("001-create.sql", "CREATE TABLE Members (Id INT);"),
            ("002-add.sql", "ALTER TABLE [Members] ADD [AnnualEquityAward] decimal(18,2) NULL;"));

        var columns = facts
            .Where(a => a.Subject == "table:Members" && a.Predicate == "has_column")
            .Select(a => a.Object)
            .Order(StringComparer.Ordinal)
            .ToList();

        Assert.Equal(["AnnualEquityAward", "Id"], columns);
    }

    [Fact]
    public async Task ADroppedColumnLeavesTheGraph()
    {
        // A column that no longer exists is a WRONG fact, worse than a missing one: a reader would
        // join to it, search for it, and find code that does not use it.
        var facts = await FoldAsync(
            ("001-create.sql", "CREATE TABLE T (Id INT, Legacy INT);"),
            ("002-drop.sql", "ALTER TABLE T DROP COLUMN Legacy;"));

        Assert.Contains(facts, a => a.Predicate == "has_column" && a.Object == "Id");
        Assert.DoesNotContain(facts, a => a.Predicate == "has_column" && a.Object == "Legacy");
    }

    [Fact]
    public async Task ADroppedTableLeavesTheGraphEntirely()
    {
        var facts = await FoldAsync(
            ("001-create.sql", "CREATE TABLE Gone (Id INT);"),
            ("002-drop.sql", "DROP TABLE Gone;"));

        Assert.DoesNotContain(facts, a => a.Subject == "table:Gone");
    }

    [Fact]
    public async Task AConstraintAddedByAlterIsNotClaimedAsAColumn()
    {
        var facts = await FoldAsync(
            ("001.sql", "CREATE TABLE T (Id INT); ALTER TABLE T ADD CONSTRAINT PK_T PRIMARY KEY (Id);"));

        var columns = facts.Where(a => a.Predicate == "has_column").Select(a => a.Object).ToList();

        Assert.Equal(["Id"], columns);
    }

    [Fact]
    public async Task AnAlterAgainstATableNoScriptCreatesStillEvidencesTheTable()
    {
        // The CREATE may live in a script nobody put in the repository. Ignoring the ALTER would
        // hide a table the code demonstrably uses.
        var facts = await FoldAsync(
            ("001.sql", "ALTER TABLE Elsewhere ADD [Note] nvarchar(10);"));

        Assert.Contains(facts, a => a.Subject == "table:Elsewhere" && a.Predicate == "has_type");
        Assert.Contains(facts, a => a.Predicate == "has_column" && a.Object == "Note");
    }

    [Fact]
    public async Task ARenameIsCountedAndDisclosed_NotGuessedAt()
    {
        // Every dialect spells a rename differently (sp_rename on SQL Server, RENAME COLUMN
        // elsewhere). Guessing one produces a confidently WRONG column name rather than an absent
        // one, so the count is disclosed and the earlier name is what the graph shows.
        var facts = await FoldAsync(
            ("001.sql", "CREATE TABLE T (Id INT); EXEC sp_rename 'T.Id', 'Identifier', 'COLUMN';"));

        var disclosure = Assert.Single(facts,
            a => a.Object.StartsWith(SqlSchemaExtractor.Disclosures.RenamesNotFollowed, StringComparison.Ordinal));

        Assert.Contains("1 rename", disclosure.Object);
    }

    [Fact]
    public async Task NoRenamesMeansNoRenameDisclosure()
    {
        // A blanket disclosure says the same thing whether there are none or thirty, which is how a
        // closed gap ends up reported as open.
        var facts = await FoldAsync(("001.sql", "CREATE TABLE T (Id INT);"));

        Assert.DoesNotContain(facts,
            a => a.Object.StartsWith(SqlSchemaExtractor.Disclosures.RenamesNotFollowed, StringComparison.Ordinal));
    }

    [Fact]
    public async Task WhatItCannotSeeIsDisclosedRatherThanSilent()
    {
        // Column types, constraints and indexes are all unread. A schema that looks complete and is
        // not is worse than one that says which half it is.
        var facts = await ReadAsync("CREATE TABLE Thing (Id INT);");

        Assert.Contains(facts, a => a.Object == SqlSchemaExtractor.Disclosures.ColumnDetailNotRead);
        Assert.Contains(facts, a => a.Object == SqlSchemaExtractor.Disclosures.NotTheDatabase);
    }

    [Fact]
    public async Task SqlIsNoLongerReportedAsUnanalysed()
    {
        // A closed gap reported as open is the same defect as hiding one that is not — and this
        // list has now needed the correction three times, once per extractor added.
        File.WriteAllText(Path.Combine(_dir, "schema.sql"), "CREATE TABLE Thing (Id INT);");
        await Task.Yield();

        Assert.DoesNotContain(
            UnanalysedLanguages.Survey(_dir),
            d => d.StartsWith("sql-not-analysed", StringComparison.Ordinal));
    }

    [Fact]
    public void TheRouterSendsSqlScopesToThisExtractor()
    {
        // Asserted rather than trusted: the composition takes six optional extractors positionally,
        // and getting that order wrong once routed every bicep scope to the schema reader.
        Assert.Equal("sql", WorkspaceExtractors.RoutedKinds["sql:"]);
    }
}
