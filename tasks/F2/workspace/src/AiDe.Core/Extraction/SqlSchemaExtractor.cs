using System.Text.RegularExpressions;
using AiDe.Core.Facts;

namespace AiDe.Core.Extraction;

/// <summary>
/// Tables declared in raw SQL, for repositories whose schema is not EF migrations.
/// </summary>
/// <remarks>
/// <para><b>Found by measuring a SECOND repository.</b> BioHacker declares its whole schema in
/// <c>src/Baseline.Sql/Schema/001-schema.sql</c> — eight <c>CREATE TABLE</c> statements in 197
/// lines — and the tool reported <c>sql-not-analysed (2 file(s))</c> and produced <b>zero</b> joins.
/// The disclosure was honest and the graph was still blind to the entire schema side of that
/// repository. Every measurement before it came from a codebase that happened to use EF.</para>
///
/// <para><b>Same node shape as <see cref="EfSchemaExtractor"/>, deliberately.</b> A table is
/// <c>table:Name</c> with <c>has_type table</c> and <c>has_column</c>, because the join projection
/// already reads that vocabulary — a second spelling for the same thing would be DC-022 with two
/// producers of one predicate, and the joins would silently see half the tables.</para>
///
/// <para><b>The scripts are FOLDED, not just read.</b> A schema is the sum of its statements in
/// order. MEASURED: one repository carries 125 <c>ALTER TABLE … ADD</c> statements, so reading
/// <c>CREATE</c> alone would have shown its schema as it stood at the first migration and presented
/// that as current — the same defect the EF reader avoids by folding migrations. Drops are applied
/// too, because a column that no longer exists is a WRONG fact rather than a missing one.</para>
///
/// <para><c>simplify: line-oriented recognition of CREATE TABLE, ALTER TABLE ADD/DROP COLUMN and
/// DROP TABLE, not a SQL grammar; ceiling is table and column NAMES; upgrade trigger = a consumer
/// needs column types, constraints, indexes, or renames followed.</c></para>
/// </remarks>
public sealed class SqlSchemaExtractor : IExtractor
{
    public string ScopeKind => "sql";

    private const string ExtractorId = "sql-schema-extractor";
    private const string ExtractorVersion = "1.0.0";

    /// <summary>Gaps this reader always has, stated on every scope it produces.</summary>
    public static class Disclosures
    {
        /// <summary>A rename is not followed, so the table or column keeps its earlier name.</summary>
        public const string RenamesNotFollowed = "sql-renames-not-followed";

        /// <summary>DDL inside a string literal — a message, or dynamic SQL nobody evaluated.</summary>
        public const string DynamicDdlNotEvaluated = "sql-dynamic-ddl-not-evaluated";

        /// <summary>Column types, constraints and indexes are not read.</summary>
        public const string ColumnDetailNotRead = "sql-column-detail-not-read";

        /// <summary>This is the schema the FILES declare, not what a server holds.</summary>
        public const string NotTheDatabase = "sql-schema-from-files-not-database";
    }

    // `CREATE TABLE [dbo].[Thing]`, `CREATE TABLE dbo.Thing`, `CREATE TABLE Thing` — and the
    // OR ALTER / IF NOT EXISTS preambles that real scripts carry.
    private static readonly Regex CreateTable = new(
        @"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?<name>(?:\[[^\]]+\]|""[^""]+""|`[^`]+`|[A-Za-z_][\w$]*)"
        + @"(?:\s*\.\s*(?:\[[^\]]+\]|""[^""]+""|`[^`]+`|[A-Za-z_][\w$]*))*)",
        RegexOptions.Compiled | RegexOptions.IgnoreCase);

    // `ALTER TABLE X ADD [Col] type` — MEASURED: one real repository carries 125 of these and zero
    // CREATE-only tables, so reading CREATE alone would have shown its schema as it was at the first
    // migration and called that current.
    private static readonly Regex AlterAdd = new(
        @"ALTER\s+TABLE\s+(?<table>(?:\[[^\]]+\]|""[^""]+""|`[^`]+`|[A-Za-z_][\w$]*)"
        + @"(?:\s*\.\s*(?:\[[^\]]+\]|""[^""]+""|`[^`]+`|[A-Za-z_][\w$]*))*)"
        + @"\s+ADD\s+(?!CONSTRAINT|PRIMARY|FOREIGN|UNIQUE|CHECK|INDEX)"
        + @"(?<column>\[[^\]]+\]|""[^""]+""|`[^`]+`|[A-Za-z_][\w$]*)\s+[A-Za-z]",
        RegexOptions.Compiled | RegexOptions.IgnoreCase);

    // A dropped column that stays in the graph is a WRONG fact, which is worse than a missing one.
    private static readonly Regex AlterDrop = new(
        @"ALTER\s+TABLE\s+(?<table>(?:\[[^\]]+\]|""[^""]+""|`[^`]+`|[A-Za-z_][\w$]*)"
        + @"(?:\s*\.\s*(?:\[[^\]]+\]|""[^""]+""|`[^`]+`|[A-Za-z_][\w$]*))*)"
        + @"\s+DROP\s+COLUMN\s+(?<column>\[[^\]]+\]|""[^""]+""|`[^`]+`|[A-Za-z_][\w$]*)",
        RegexOptions.Compiled | RegexOptions.IgnoreCase);

    private static readonly Regex DropTable = new(
        @"DROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?(?<table>(?:\[[^\]]+\]|""[^""]+""|`[^`]+`|[A-Za-z_][\w$]*)"
        + @"(?:\s*\.\s*(?:\[[^\]]+\]|""[^""]+""|`[^`]+`|[A-Za-z_][\w$]*))*)",
        RegexOptions.Compiled | RegexOptions.IgnoreCase);

    // DDL keywords inside a quoted string, counted only so the gap can be stated. Strings are
    // blanked before matching, so `PRINT 'about to create table X'` names no table — and neither
    // does dynamic SQL, which this reader has no way to evaluate.
    private static readonly Regex DdlInAString = new(
        @"'[^']*\b(?:CREATE|ALTER|DROP)\s+TABLE\b[^']*'",
        RegexOptions.Compiled | RegexOptions.IgnoreCase);

    // Renames are DISCLOSED rather than half-read: every dialect spells them differently
    // (`sp_rename` on SQL Server, `RENAME COLUMN` elsewhere), and guessing one produces a confidently
    // wrong column name rather than an absent one.
    private static readonly Regex Rename = new(
        @"(?:ALTER\s+TABLE\s+\S+\s+RENAME|EXEC(?:UTE)?\s+sp_rename)",
        RegexOptions.Compiled | RegexOptions.IgnoreCase);

    // A column line inside the parentheses: a name, then a type word. Constraint lines start with a
    // keyword and are skipped rather than claimed as columns.
    private static readonly Regex ColumnLine = new(
        @"^\s*(?<name>\[[^\]]+\]|""[^""]+""|`[^`]+`|[A-Za-z_][\w$]*)\s+[A-Za-z]",
        RegexOptions.Compiled);

    private static readonly HashSet<string> NotAColumn = new(StringComparer.OrdinalIgnoreCase)
    {
        "CONSTRAINT", "PRIMARY", "FOREIGN", "UNIQUE", "CHECK", "INDEX", "KEY", "PERIOD", "WITH",
    };

    public Task<ExtractionResult> ExtractAsync(ExtractionRequest request, CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(request);

        var directory = request.RootPath;

        if (!Directory.Exists(directory))
        {
            return Task.FromResult(new ExtractionResult([], Complete: false,
                [new ExtractionDiagnostic("AIDE-SQL-NO-DIRECTORY", request.ScopeId,
                    $"the scope's directory does not exist: {directory}")]));
        }

        var observedAt = DateTimeOffset.UtcNow;
        var assertions = new List<EvidenceAssertion>();
        var scopeNode = CSharpExtractor.ScopeNodeId(request.ScopeId);

        var scopeProvenance = new Provenance(
            Path.GetFileName(directory), "1:1", ExtractorId, ExtractorVersion, observedAt);

        // RenamesNotFollowed is NOT here: it is conditional and carries a count, because a blanket
        // "renames are not followed" says the same thing whether there are none or thirty. The
        // Python reader learned this the other way round — a blanket disclosure that stayed true
        // after the gap it described had closed.
        foreach (var disclosure in new[]
        {
            Disclosures.ColumnDetailNotRead,
            Disclosures.NotTheDatabase,
        })
        {
            assertions.Add(Fact(request, scopeNode, CSharpExtractor.DisclosurePredicate, disclosure, scopeProvenance));
        }

        var unreadable = 0;
        var renames = 0;
        var dynamicDdl = 0;

        // The FOLD. A schema is the sum of its scripts in order, not the first one: MEASURED, a real
        // repository has 125 `ALTER TABLE … ADD` statements, so reading CREATE alone would show its
        // schema as it stood at the first migration and present that as current. Files are taken in
        // name order because migration scripts are named to sort chronologically — the same
        // assumption the EF reader makes, and the reason the ordering is stated rather than implied.
        var tables = new Dictionary<string, TableState>(StringComparer.OrdinalIgnoreCase);

        foreach (var file in Files(directory).OrderBy(f => f, StringComparer.OrdinalIgnoreCase))
        {
            cancellationToken.ThrowIfCancellationRequested();

            string text;
            try { text = File.ReadAllText(file); }
            catch (Exception ex) when (ex is IOException or UnauthorizedAccessException)
            {
                unreadable++;
                continue;
            }

            // Commentary is removed before anything is believed. A commented-out CREATE TABLE is a
            // table that does not exist, and every repository is full of them — the shared
            // invent-rate control found `table:Ghost` and `table:Planned` here on its first run.
            // DDL inside a STRING is either a message or dynamic SQL, and this reader can tell
            // neither from a declaration: `PRINT 'about to create table Something'` names no table.
            // So strings are blanked with the comments, and what that hides is counted.
            dynamicDdl += DdlInAString.Matches(text).Count;

            text = SourceText.WithoutCComments(
                text, doubleDashLineComments: true, blankStrings: true, singleQuotedStringsOnly: true);

            var relative = Path.GetRelativePath(directory, file).Replace((char)92, '/');
            renames += Rename.Matches(text).Count;

            foreach (var (table, columns, line) in Tables(text))
            {
                if (!tables.TryGetValue(table, out var state))
                {
                    tables[table] = state = new TableState(relative, line);
                }

                foreach (var column in columns) state.Columns.Add(column);
            }

            foreach (Match match in AlterAdd.Matches(text))
            {
                var table = Unquote(match.Groups["table"].Value);

                // An ALTER against a table this scope never creates is still evidence the table
                // exists — the CREATE may live in a script nobody put in the repository.
                if (!tables.TryGetValue(table, out var state))
                {
                    tables[table] = state = new TableState(relative, LineOf(text, match.Index));
                }

                state.Columns.Add(Unquote(match.Groups["column"].Value));
            }

            foreach (Match match in AlterDrop.Matches(text))
            {
                if (tables.TryGetValue(Unquote(match.Groups["table"].Value), out var state))
                {
                    state.Columns.Remove(Unquote(match.Groups["column"].Value));
                }
            }

            foreach (Match match in DropTable.Matches(text))
            {
                tables.Remove(Unquote(match.Groups["table"].Value));
            }
        }

        foreach (var (table, state) in tables)
        {
            var node = $"table:{table}";
            var provenance = new Provenance(
                state.Path, $"{state.Line}:1", ExtractorId, ExtractorVersion, observedAt);

            assertions.Add(Fact(request, node, "has_type", "table", provenance));
            assertions.Add(Fact(request, node, "declared_in", request.ScopeId, provenance));

            foreach (var column in state.Columns)
            {
                assertions.Add(Fact(request, node, "has_column", column, provenance));
            }
        }

        if (dynamicDdl > 0)
        {
            assertions.Add(Fact(request, scopeNode, CSharpExtractor.DisclosurePredicate,
                $"{Disclosures.DynamicDdlNotEvaluated} ({dynamicDdl:N0} string(s) contain DDL that "
                + "was not read; it may be a message or it may build a table)", scopeProvenance));
        }

        if (renames > 0)
        {
            // Counted, because "renames are not followed" and "3 renames were not followed" are
            // different statements about how wrong a name in this graph might be.
            assertions.Add(Fact(request, scopeNode, CSharpExtractor.DisclosurePredicate,
                $"{Disclosures.RenamesNotFollowed} ({renames:N0} rename(s); the earlier name is what "
                + "this graph shows)", scopeProvenance));
        }

        if (unreadable > 0)
        {
            assertions.Add(Fact(request, scopeNode, CSharpExtractor.DisclosurePredicate,
                $"sql-source-unreadable ({unreadable:N0} file(s))", scopeProvenance));
        }

        // Identical facts are ONE fact: the same table can be created in two scripts (a baseline and
        // a rebuild), and the store's natural key rejects the duplicate rather than absorbing it.
        var deduplicated = ExtractionFacts.Distinct(assertions);

        return Task.FromResult(new ExtractionResult(deduplicated, Complete: true, []));
    }

    /// <summary>A table as the scripts have left it so far.</summary>
    /// <remarks>
    /// Columns are an ORDERED set: order is the declaration order a reader expects, and set
    /// semantics mean re-adding a column two scripts later is not a duplicate fact.
    /// </remarks>
    private sealed class TableState(string path, int line)
    {
        public string Path { get; } = path;

        public int Line { get; } = line;

        public HashSet<string> Columns { get; } = new(StringComparer.OrdinalIgnoreCase);
    }

    private static int LineOf(string text, int index) =>
        text.Take(index).Count(c => c == '\n') + 1;

    /// <summary>Every table a script creates, with the columns declared inside its parentheses.</summary>
    /// <remarks>
    /// The body is taken by matching parentheses from the first one after the name, so a nested
    /// <c>DECIMAL(9,2)</c> or a table-level <c>CHECK (...)</c> does not end the definition early —
    /// which a naive scan to the first <c>)</c> does, silently truncating the column list.
    /// </remarks>
    internal static IEnumerable<(string Table, IReadOnlyList<string> Columns, int Line)> Tables(string text)
    {
        foreach (Match match in CreateTable.Matches(text))
        {
            var name = Unquote(match.Groups["name"].Value);
            var line = text.Take(match.Index).Count(c => c == '\n') + 1;

            var open = text.IndexOf('(', match.Index + match.Length);
            if (open < 0)
            {
                yield return (name, [], line);
                continue;
            }

            var depth = 0;
            var close = -1;

            for (var i = open; i < text.Length; i++)
            {
                if (text[i] == '(') depth++;
                else if (text[i] == ')' && --depth == 0) { close = i; break; }
            }

            if (close < 0)
            {
                yield return (name, [], line);
                continue;
            }

            yield return (name, Columns(text[(open + 1)..close]), line);
        }
    }

    private static List<string> Columns(string body)
    {
        var columns = new List<string>();
        var depth = 0;
        var start = 0;

        // Split on commas at depth zero: a comma inside DECIMAL(9,2) does not separate columns.
        for (var i = 0; i <= body.Length; i++)
        {
            if (i < body.Length && body[i] == '(') depth++;
            else if (i < body.Length && body[i] == ')') depth--;

            if (i != body.Length && (body[i] != ',' || depth != 0)) continue;

            var piece = body[start..i];
            start = i + 1;

            var match = ColumnLine.Match(piece.TrimStart('\r', '\n'));
            if (!match.Success) continue;

            var name = Unquote(match.Groups["name"].Value);
            if (NotAColumn.Contains(name)) continue;

            columns.Add(name);
        }

        return columns;
    }

    /// <summary>
    /// The bare name, without brackets, quotes or a schema qualifier.
    /// </summary>
    /// <remarks>
    /// The schema prefix is dropped so <c>dbo.Principal</c> and <c>Principal</c> are one node. The
    /// EF reader emits unqualified names, and two spellings of one table would leave the joins
    /// matching half of them — the divergence being invisible because both look correct alone.
    /// </remarks>
    private static string Unquote(string raw)
    {
        var last = raw.Split('.')[^1].Trim();

        return last.Trim('[', ']', '"', '`', ' ');
    }

    private static EvidenceAssertion Fact(
        ExtractionRequest request, string subject, string predicate, string obj, Provenance provenance) =>
        new(request.ScopeId, request.ArtifactRevision, subject, predicate, obj,
            EvidenceOrigin.Static, VerificationStatus.Verified, provenance);

    private static IEnumerable<string> Files(string directory)
    {
        var skip = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        {
            "node_modules", "bin", "obj", ".git", "packages",
        };

        var pending = new Stack<string>();
        pending.Push(directory);

        while (pending.Count > 0)
        {
            var current = pending.Pop();

            string[] files;
            try { files = Directory.GetFiles(current, "*.sql"); }
            catch (Exception ex) when (ex is IOException or UnauthorizedAccessException) { continue; }

            foreach (var file in files) yield return file;

            IEnumerable<string> children;
            try { children = Directory.EnumerateDirectories(current); }
            catch (Exception ex) when (ex is IOException or UnauthorizedAccessException) { continue; }

            foreach (var child in children)
            {
                if (!skip.Contains(Path.GetFileName(child))) pending.Push(child);
            }
        }
    }
}
