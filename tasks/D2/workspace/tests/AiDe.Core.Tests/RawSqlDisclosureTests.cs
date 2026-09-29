using AiDe.Core.Extraction;
using AiDe.Core.Facts;

namespace AiDe.Core.Tests;

/// <summary>
/// The raw-SQL disclosure says how much of the schema is actually in question.
/// </summary>
/// <remarks>
/// <para>The EF reader folds migration operations and cannot read <c>migrationBuilder.Sql</c>. It
/// disclosed that as one blanket sentence, which is true and useless: MEASURED on TheTerrace, <b>4 of
/// 23</b> raw statements in <c>Up</c> methods carry DDL. The other 19 are application locks, data
/// moves and index hints that could not change a column list whatever they did.</para>
///
/// <para>Reporting them as one number is DC-050 — a boundary and a gap in the same count — and it is
/// how this reader's own limitation read as larger than it is. It also nearly sent a session building
/// a SQL fold: measured, the one raw statement that adds a column is followed by a raw statement that
/// drops the same one, so the net effect on the graph is zero and the schema shown is correct.</para>
/// </remarks>
public sealed class RawSqlDisclosureTests : IDisposable
{
    private readonly string _dir = Path.Combine(
        Path.GetTempPath(), "aide-rawsql", Guid.NewGuid().ToString("N"));

    public RawSqlDisclosureTests()
    {
        Directory.CreateDirectory(Path.Combine(_dir, "Migrations"));
    }

    public void Dispose()
    {
        try { Directory.Delete(_dir, recursive: true); } catch (IOException) { }
    }

    private async Task<IReadOnlyList<string>> DisclosuresAsync(string migrationBody)
    {
        File.WriteAllText(Path.Combine(_dir, "Migrations", "20260101000000_Test.cs"), $$"""
            using Microsoft.EntityFrameworkCore.Migrations;

            public partial class Test : Migration
            {
                protected override void Up(MigrationBuilder migrationBuilder)
                {
            {{migrationBody}}
                }
            }
            """);

        var result = await new EfSchemaExtractor().ExtractAsync(
            new ExtractionRequest("schema:Migrations", Path.Combine(_dir, "Migrations"), "rev-1", 1), CancellationToken.None);

        return [.. result.Assertions.Where(a => a.Predicate == "discloses").Select(a => a.Object)];
    }

    private static string? RawSql(IEnumerable<string> disclosures) =>
        disclosures.FirstOrDefault(d => d.StartsWith(
            ExtractionDisclosures.SchemaChangedByRawSqlNotRead, StringComparison.Ordinal));

    [Fact]
    public async Task RawSqlCarryingDdlIsCountedApartFromRawSqlThatCannotChangeAnything()
    {
        var disclosure = RawSql(await DisclosuresAsync("""
                    migrationBuilder.Sql("EXEC sp_getapplock @Resource = N'lock';");
                    migrationBuilder.Sql("UPDATE [dbo].[Thing] SET [Name] = 'x';");
                    migrationBuilder.Sql("ALTER TABLE [dbo].[Thing] ADD [Extra] int NULL;");
            """));

        Assert.NotNull(disclosure);
        Assert.Contains("1 of 3", disclosure, StringComparison.Ordinal);
    }

    [Fact]
    public async Task DdlSplitOverSeveralLinesIsStillRecognised()
    {
        // Real migration SQL puts `ALTER TABLE [schema].[Table]` on one line and the `ADD` on the
        // next. A line-anchored pattern sees neither, which is how this count would have read zero
        // while four statements changed tables.
        var disclosure = RawSql(await DisclosuresAsync("""
                    migrationBuilder.Sql(@"
                        ALTER TABLE [sports].[DemoFixture]
                        ADD [ValidationDisplayVersion] nvarchar(64) NULL;");
            """));

        Assert.NotNull(disclosure);
        Assert.Contains("1 of 1", disclosure, StringComparison.Ordinal);
    }

    [Fact]
    public async Task RawSqlThatChangesNoSchemaSaysZero()
    {
        // The disclosure still fires — the statements were not read — but it says the schema is not
        // in question. "Something was skipped" and "your column list may be wrong" are different
        // warnings and only one of them should worry anybody.
        var disclosure = RawSql(await DisclosuresAsync("""
                    migrationBuilder.Sql("EXEC sp_getapplock @Resource = N'lock';");
                    migrationBuilder.Sql("INSERT INTO [dbo].[Seed] ([Id]) VALUES (1);");
            """));

        Assert.NotNull(disclosure);
        Assert.Contains("0 of 2", disclosure, StringComparison.Ordinal);
    }

    [Fact]
    public async Task ADownMethodIsNotCounted()
    {
        // The reader folds only `Up`, because folding both nets to nothing. A count that included
        // `Down` would report roughly double — measured on TheTerrace, 30 statements against the 23
        // that matter, which is exactly the mistake a hand-rolled scan of the same tree made.
        File.WriteAllText(Path.Combine(_dir, "Migrations", "20260101000000_Test.cs"), """
            using Microsoft.EntityFrameworkCore.Migrations;

            public partial class Test : Migration
            {
                protected override void Up(MigrationBuilder migrationBuilder)
                {
                    migrationBuilder.Sql("ALTER TABLE [dbo].[Thing] ADD [Extra] int NULL;");
                }

                protected override void Down(MigrationBuilder migrationBuilder)
                {
                    migrationBuilder.Sql("ALTER TABLE [dbo].[Thing] DROP COLUMN [Extra];");
                    migrationBuilder.Sql("ALTER TABLE [dbo].[Other] DROP COLUMN [Gone];");
                }
            }
            """);

        var result = await new EfSchemaExtractor().ExtractAsync(
            new ExtractionRequest("schema:Migrations", Path.Combine(_dir, "Migrations"), "rev-1", 1), CancellationToken.None);

        var disclosure = RawSql(result.Assertions.Where(a => a.Predicate == "discloses").Select(a => a.Object));

        Assert.NotNull(disclosure);
        Assert.Contains("1 of 1", disclosure, StringComparison.Ordinal);
    }

    [Fact]
    public async Task NoRawSqlMeansNoDisclosure()
    {
        // A disclosure that fires when nothing was hidden trains a reader to ignore disclosures.
        var disclosures = await DisclosuresAsync("""
                    migrationBuilder.CreateTable(name: "Thing", columns: table => new { Id = table.Column<int>() });
            """);

        Assert.Null(RawSql(disclosures));
    }
}
