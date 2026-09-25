using AiDe.Core.Facts;
using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp;
using Microsoft.CodeAnalysis.CSharp.Syntax;

namespace AiDe.Core.Extraction;

/// <summary>
/// The schema extractor — EF Core migrations folded into the tables they create.
/// </summary>
/// <remarks>
/// <para><b>This replaced the planned DDL parser on evidence.</b> The first repository it was checked
/// against holds 62 migration classes and <b>zero</b> <c>.sql</c> files, so a DDL parser would have
/// shipped with no corpus. Measured against EF's own checked-in model snapshot it recovers
/// <b>62 of 62</b> tables in 99 ms (<c>spikes/ef-migration-schema</c>).</para>
///
/// <para><b>Migrations are append-only and ordered, so the schema is a fold over them</b> — the same
/// shape as the fact store itself, which is why schema evidence needs no new table and sits beside
/// code evidence at a different grain. Ordering is by the timestamp prefix in the FILE NAME, which
/// is how EF orders them; any other ordering puts a create after a drop and yields a schema that
/// never existed.</para>
///
/// <para><b>Read as syntax.</b> No EF, no database, no <c>dotnet ef</c>. Phase 2's constraint carries
/// forward without exception.</para>
/// </remarks>
public sealed class EfSchemaExtractor(string extractorVersion = "1.0.0") : IExtractor
{
    public const string ExtractorId = "ef-schema-extractor";

    public string ScopeKind => "schema";

    public Task<ExtractionResult> ExtractAsync(ExtractionRequest request, CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(request);

        var directory = Path.GetFullPath(request.RootPath);
        if (!Directory.Exists(directory))
        {
            return Task.FromResult(new ExtractionResult(
                [], Complete: false,
                [new ExtractionDiagnostic("AIDE-SCHEMA-MISSING", request.RootPath, "no migrations directory at this path")]));
        }

        var files = Directory
            .EnumerateFiles(directory, "*.cs", SearchOption.TopDirectoryOnly)
            .Where(f => !f.EndsWith(".Designer.cs", StringComparison.OrdinalIgnoreCase))
            .Where(f => !f.EndsWith("ModelSnapshot.cs", StringComparison.OrdinalIgnoreCase))
            .OrderBy(Path.GetFileName, StringComparer.Ordinal)
            .ToList();

        if (files.Count == 0)
        {
            return Task.FromResult(new ExtractionResult(
                [], Complete: false,
                [new ExtractionDiagnostic("AIDE-SCHEMA-EMPTY", request.ScopeId, "no migration classes found")]));
        }

        var tables = new Dictionary<string, TableState>(StringComparer.OrdinalIgnoreCase);
        var rawSql = 0;
        var rawSqlChangingSchema = 0;

        foreach (var file in files)
        {
            cancellationToken.ThrowIfCancellationRequested();

            string source;
            try { source = File.ReadAllText(file); }
            catch (IOException) { continue; }

            var tree = CSharpSyntaxTree.ParseText(source, path: file);
            var migration = Path.GetFileNameWithoutExtension(file);

            // Only Up. Down undoes things, and folding both nets to nothing.
            var up = tree.GetRoot().DescendantNodes().OfType<MethodDeclarationSyntax>()
                .FirstOrDefault(m => m.Identifier.ValueText == "Up");

            if (up is null) continue;

            foreach (var call in up.DescendantNodes().OfType<InvocationExpressionSyntax>())
            {
                if (call.Expression is not MemberAccessExpressionSyntax member) continue;

                switch (member.Name.Identifier.ValueText)
                {
                    case "CreateTable":
                        {
                            var name = Named(call, "name");
                            if (name is null) break;
                            var state = Ensure(tables, name, migration, Line(source, call.SpanStart), file);
                            foreach (var column in Columns(call)) state.Columns.Add(column);
                            break;
                        }

                    case "AddColumn":
                        {
                            var table = Named(call, "table");
                            var column = Named(call, "name");
                            if (table is null || column is null) break;
                            Ensure(tables, table, migration, Line(source, call.SpanStart), file).Columns.Add(column);
                            break;
                        }

                    case "DropColumn":
                        {
                            var table = Named(call, "table");
                            var column = Named(call, "name");
                            if (table is not null && column is not null && tables.TryGetValue(table, out var state))
                            {
                                state.Columns.Remove(column);
                            }

                            break;
                        }

                    case "DropTable":
                        {
                            var name = Named(call, "name");
                            if (name is not null) tables.Remove(name);
                            break;
                        }

                    case "RenameColumn":
                        {
                            // The one unhandled operation that changes a NAME rather than a
                            // decoration. Without it a renamed column keeps its old name in the
                            // graph — a wrong fact, which is worse than a missing one, and silent
                            // because there was no default case to notice. EF states the rename in
                            // named arguments, so unlike raw SQL (where every dialect spells it
                            // differently and the SQL reader can only disclose it) this one is
                            // simply readable.
                            var table = Named(call, "table");
                            var from = Named(call, "name");
                            var to = Named(call, "newName");

                            if (table is not null && from is not null && to is not null
                                && tables.TryGetValue(table, out var state)
                                && state.Columns.Remove(from))
                            {
                                state.Columns.Add(to);
                            }

                            break;
                        }

                    case "RenameTable":
                        {
                            var from = Named(call, "name");
                            var to = Named(call, "newName");
                            if (from is not null && to is not null && tables.Remove(from, out var state))
                            {
                                tables[to] = state;
                            }

                            break;
                        }

                    case "Sql":
                        // Raw SQL can create tables, add columns and move data, and none of it is
                        // folded into the schema here.
                        //
                        // Counted in TWO buckets, because "30 raw statements were not read" and
                        // "8 of them change the schema" are different statements about how wrong
                        // this picture might be, and only the second is worth anybody's attention.
                        // MEASURED on the corpus repository: 30 raw bodies, of which 8 carry DDL —
                        // the other 22 are application locks, data moves and index hints that could
                        // not change a column list whatever they did.
                        //
                        // Reporting them as one number is the defect DC-050 is about, and it is why
                        // this reader's own gap was over-stated for weeks: the blanket sentence made
                        // 22 harmless statements look like 30 unknowns.
                        rawSql++;

                        if (Ddl.IsMatch(RawSqlBody(call))) rawSqlChangingSchema++;

                        break;
                }
            }
        }

        var observedAt = DateTimeOffset.UtcNow;
        var assertions = new List<EvidenceAssertion>();

        EvidenceAssertion Fact(string subject, string predicate, string obj, Provenance provenance) =>
            new(request.ScopeId, request.ArtifactRevision, subject, predicate, obj,
                EvidenceOrigin.Static, VerificationStatus.Verified, provenance);

        foreach (var (table, state) in tables)
        {
            var node = $"table:{table}";
            var provenance = new Provenance(
                state.RelativePath(directory), $"{state.Line}:1", ExtractorId, extractorVersion, observedAt);

            assertions.Add(Fact(node, "has_type", "table", provenance));
            assertions.Add(Fact(node, "declared_in", request.ScopeId, provenance));

            // The migration that introduced it, so a reader can answer "when did this appear" from
            // the graph rather than by reading 62 files.
            assertions.Add(Fact(node, "introduced_by", state.Migration, provenance));

            foreach (var column in state.Columns)
            {
                assertions.Add(Fact(node, "has_column", column, provenance));
            }
        }

        var scopeNode = CSharpExtractor.ScopeNodeId(request.ScopeId);
        var scopeProvenance = new Provenance(
            Path.GetFileName(directory), "1:1", ExtractorId, extractorVersion, observedAt);

        // Always. This is the schema the code INTENDS, not what a server holds, and they diverge.
        assertions.Add(Fact(
            scopeNode, CSharpExtractor.DisclosurePredicate,
            ExtractionDisclosures.SchemaFromMigrationsNotDatabase, scopeProvenance));

        if (rawSql > 0)
        {
            // The count that matters leads. A reader who sees "8 of 30" knows how much of the schema
            // is in question; one who sees only "raw SQL was not read" has to go and look.
            assertions.Add(Fact(
                scopeNode, CSharpExtractor.DisclosurePredicate,
                $"{ExtractionDisclosures.SchemaChangedByRawSqlNotRead} "
                + $"({rawSqlChangingSchema:N0} of {rawSql:N0} raw statement(s) carry DDL and were not folded)",
                scopeProvenance));
        }

        return Task.FromResult(new ExtractionResult(assertions, Complete: true, []));
    }

    /// <summary>
    /// Whether a raw SQL body carries schema DDL at all.
    /// </summary>
    /// <remarks>
    /// <para>Deliberately a recogniser and not a parser. It answers "could this have changed the
    /// column list", which is the question the disclosure asks; folding the change would need the
    /// statement understood, and MEASURED on the corpus repository that would buy nothing today —
    /// exactly one raw statement adds a column and a later raw statement drops the same one, so the
    /// net effect on the graph is zero and the schema shown is correct.</para>
    ///
    /// <para>Multi-line on purpose: real migration SQL puts <c>ALTER TABLE [schema].[Table]</c> on
    /// one line and <c>ADD [Column] nvarchar(64) NULL;</c> on the next, so a line-anchored pattern
    /// sees neither. That is how this count would have read zero while eight statements changed
    /// tables.</para>
    /// </remarks>
    private static readonly System.Text.RegularExpressions.Regex Ddl = new(
        @"\b(CREATE\s+TABLE|ALTER\s+TABLE|DROP\s+TABLE|DROP\s+COLUMN|CREATE\s+INDEX|CREATE\s+VIEW)\b",
        System.Text.RegularExpressions.RegexOptions.IgnoreCase
        | System.Text.RegularExpressions.RegexOptions.Compiled);

    /// <summary>The literal text a <c>migrationBuilder.Sql(...)</c> call carries, or empty.</summary>
    /// <remarks>
    /// Only a literal is read. An interpolated or composed argument is SQL this reader cannot see at
    /// all, and guessing at it would be inventing schema — it still counts toward the raw total, so
    /// the disclosure stays honest about it.
    /// </remarks>
    private static string RawSqlBody(InvocationExpressionSyntax call) =>
        call.ArgumentList.Arguments.Count > 0
        && call.ArgumentList.Arguments[0].Expression is LiteralExpressionSyntax literal
            ? literal.Token.ValueText
            : string.Empty;

    private sealed record TableState(string Migration, int Line, string File)
    {
        internal HashSet<string> Columns { get; } = new(StringComparer.OrdinalIgnoreCase);

        internal string RelativePath(string root) =>
            Path.GetRelativePath(root, File).Replace((char)92, '/');
    }

    private static TableState Ensure(
        Dictionary<string, TableState> tables, string name, string migration, int line, string file)
    {
        if (!tables.TryGetValue(name, out var state))
        {
            state = new TableState(migration, line, file);
            tables[name] = state;
        }

        return state;
    }

    private static int Line(string source, int position) =>
        source.Take(position).Count(c => c == '\n') + 1;

    /// <summary>
    /// A named argument's literal value.
    /// </summary>
    /// <remarks>
    /// EF's generated migrations always use named arguments, which is what makes this readable
    /// without binding: <c>name:</c> is unambiguous where argument POSITION differs between
    /// overloads. A hand-edited migration using positional arguments is not read.
    /// </remarks>
    private static string? Named(InvocationExpressionSyntax call, string argument) =>
        call.ArgumentList.Arguments
            .FirstOrDefault(a => a.NameColon?.Name.Identifier.ValueText == argument)
            ?.Expression is LiteralExpressionSyntax literal && literal.IsKind(SyntaxKind.StringLiteralExpression)
            ? literal.Token.ValueText
            : null;

    private static IEnumerable<string> Columns(InvocationExpressionSyntax call)
    {
        var columns = call.ArgumentList.Arguments
            .FirstOrDefault(a => a.NameColon?.Name.Identifier.ValueText == "columns")
            ?.Expression;

        if (columns is not SimpleLambdaExpressionSyntax lambda) yield break;
        if (lambda.ExpressionBody is not AnonymousObjectCreationExpressionSyntax anonymous) yield break;

        foreach (var initializer in anonymous.Initializers)
        {
            var name = initializer.NameEquals?.Name.Identifier.ValueText
                ?? (initializer.Expression as IdentifierNameSyntax)?.Identifier.ValueText;

            if (!string.IsNullOrEmpty(name)) yield return name;
        }
    }
}
