using System.Reflection;
using AiDe.Core.Extraction;
using AiDe.Core.Facts;

namespace AiDe.Core.Tests;

/// <summary>
/// Every assertion every extractor emits must cite something that is actually on disk.
/// </summary>
/// <remarks>
/// <para><b>DC-229's control.</b> <see cref="Provenance.ArtifactPathId"/> means "the artifact's path
/// relative to its scope". Two extractors passed the <i>scope's own id</i> into it — a value with a
/// colon in it that names no file — and every consumer that resolves the path then computed a path
/// that cannot exist. One of them told the operator (<c>"the source for this node could not be
/// located (typescript:src/frontend)"</c>); the other, content search, counted it as a skip and
/// returned a confident, wrong, empty answer for every TypeScript and Python file in every
/// workspace, for an unknown span of time. A missing citation is a gap; a citation that resolves to
/// nothing arrives labelled <b>Verified</b> and is believed.</para>
///
/// <para><b>Why the reflection guard rather than a list of cases.</b> The two defective extractors
/// were exactly the two with no provenance assertion in any test — the gap and the defect were the
/// same shape. A hand-written list would have the same hole the day a tenth extractor is registered,
/// so <see cref="EveryExtractorInTheAssemblyIsCoveredHere"/> fails on an extractor that has no corpus
/// here. The cost of adding an extractor now includes saying what its provenance points at.</para>
///
/// <para><b>Two shapes pass, and they are both named.</b> A per-artifact citation resolves as a file
/// under the scope. A scope-summary row — the three producers that describe the scope as a whole
/// rather than any one file — cites the scope's own directory by its leaf name. Nothing else passes,
/// and neither shape is a skip: an assertion that matches neither is a failure that names the
/// subject, the predicate and the value, because a skip counter with no reason code is how DC-229
/// stayed invisible.</para>
/// </remarks>
public sealed class ProvenanceNamesAnArtifactThatExistsTests : IDisposable
{
    private readonly string _root = Path.Combine(
        Path.GetTempPath(), "aide-provenance", Guid.NewGuid().ToString("N"));

    public ProvenanceNamesAnArtifactThatExistsTests() => Directory.CreateDirectory(_root);

    public void Dispose()
    {
        try { Directory.Delete(_root, recursive: true); } catch (IOException) { }
    }

    /// <summary>
    /// Extractors that emit no assertions of their own, each named with the reason it is exempt.
    /// </summary>
    /// <remarks>
    /// An exemption is a sentence, not an absence: a type dropped out of the registry silently is
    /// the hole this test exists to close.
    /// </remarks>
    private static readonly IReadOnlyDictionary<Type, string> EmitsNothingOfItsOwn =
        new Dictionary<Type, string>
        {
            [typeof(CompositeExtractor)] =
                "a router: it delegates to the extractor owning the scope prefix and adds no assertion",
        };

    private string Write(string relative, string content)
    {
        var path = Path.Combine(_root, relative.Replace('/', Path.DirectorySeparatorChar));
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        File.WriteAllText(path, content);
        return path;
    }

    /// <summary>One extractor, a corpus in its own notation, and the request that reads it.</summary>
    private sealed record Case(string Name, IExtractor Extractor, string ScopeId, string RootPath);

    private const string Csproj = """
        <Project Sdk="Microsoft.NET.Sdk">
          <PropertyGroup>
            <TargetFramework>net10.0</TargetFramework>
            <Nullable>enable</Nullable>
          </PropertyGroup>
        </Project>
        """;

    /// <summary>
    /// A corpus per extractor, each in the notation that extractor actually reads.
    /// </summary>
    /// <remarks>
    /// Deliberately small and deliberately real: the point is that assertions come out at all, so
    /// that what they cite can be resolved. An extractor that emits nothing here is itself a finding
    /// — <see cref="EveryCaseEmitsSomethingToCheck"/> refuses a vacuous pass.
    /// </remarks>
    private IReadOnlyList<Case> BuildCases()
    {
        var csproj = Write("Shop/Shop.csproj", Csproj);
        Write("Shop/Orders.cs", """
            namespace Shop;

            public interface IRepository { }

            public sealed class OrderRepository : IRepository { }
            """);

        var bicep = Write("infra/main.bicep", """
            param location string = 'westeurope'

            resource store 'Microsoft.Storage/storageAccounts@2023-01-01' = {
              name: 'aidestore'
              location: location
            }
            """);

        Write("efschema/Migrations/20260101000000_Initial.cs", """
            using Microsoft.EntityFrameworkCore.Migrations;
            public partial class M : Migration
            {
                protected override void Up(MigrationBuilder migrationBuilder)
                {
                    migrationBuilder.CreateTable(
                        name: "Orders",
                        columns: table => new { Id = 1, Total = 2 });
                }
                protected override void Down(MigrationBuilder migrationBuilder) { }
            }
            """);

        Write("sql/schema.sql", """
            CREATE TABLE Orders (
                Id INT NOT NULL PRIMARY KEY,
                CustomerName NVARCHAR(200) NOT NULL
            );
            """);

        Write("ts/orders.ts", """
            export interface Order { id: number; }

            export class OrderService {
              find(id: number): Order | undefined { return undefined; }
            }
            """);

        Write("py/orders.py", """
            class OrderService:
                def find(self, order_id):
                    return None
            """);

        Write("docs/workspace.md", """
            ---
            id: doc-workspace
            title: The workspace
            type: doc
            links:
              - { to: doc-other, rel: relates-to }
            ---

            # The workspace
            """);

        Write("fixture/graph.facts", """
            Shop.OrderRepository -> implements -> Shop.IRepository [Verified]
            """);

        return
        [
            new("csharp", new CSharpExtractor(), "csharp:Shop:net10.0", csproj),
            new("bicep", new BicepExtractor(), "bicep:main", bicep),
            // The EF reader is pointed at the Migrations directory itself, not at its parent — the
            // migrations ARE the scope.
            new("schema", new EfSchemaExtractor(), "schema:App", Path.Combine(_root, "efschema", "Migrations")),
            new("sql", new SqlSchemaExtractor(), "sql:schema", Path.Combine(_root, "sql")),
            new("typescript", new TypeScriptExtractor(), "typescript:ts", Path.Combine(_root, "ts")),
            new("python", new PythonExtractor(), "python:py", Path.Combine(_root, "py")),
            new("knowledge", new KnowledgeExtractor(), "knowledge:docs", Path.Combine(_root, "docs")),
            new("fixture", new FixtureExtractor(), "fixture:fixture", Path.Combine(_root, "fixture")),
        ];
    }

    /// <summary>The directory a relative <c>ArtifactPathId</c> is resolved against.</summary>
    /// <remarks>
    /// A scope's root is a directory for most extractors and a single project or template FILE for
    /// the C# and Bicep readers, which is why this is a function and not a field.
    /// </remarks>
    private static string ScopeDirectory(string rootPath) =>
        File.Exists(rootPath) ? Path.GetDirectoryName(Path.GetFullPath(rootPath))! : Path.GetFullPath(rootPath);

    /// <summary>
    /// The tenth extractor is covered the day it is registered, or this fails.
    /// </summary>
    [Fact]
    public void EveryExtractorInTheAssemblyIsCoveredHere()
    {
        var implementations = typeof(IExtractor).Assembly
            .GetTypes()
            .Where(t => t is { IsClass: true, IsAbstract: false } && typeof(IExtractor).IsAssignableFrom(t))
            .ToList();

        var covered = BuildCases().Select(c => c.Extractor.GetType()).ToHashSet();
        var missing = implementations
            .Where(t => !covered.Contains(t) && !EmitsNothingOfItsOwn.ContainsKey(t))
            .Select(t => t.Name)
            .Order(StringComparer.Ordinal)
            .ToList();

        Assert.True(
            missing.Count == 0,
            $"these extractors emit provenance that nothing here resolves: {string.Join(", ", missing)}. " +
            "Add a corpus to BuildCases, or name the type in EmitsNothingOfItsOwn with the reason it " +
            "emits no assertions of its own.");
    }

    /// <summary>A corpus that produces no assertions would let the oracle pass by emitting nothing.</summary>
    [Fact]
    public async Task EveryCaseEmitsSomethingToCheck()
    {
        var silent = new List<string>();
        foreach (var @case in BuildCases())
        {
            var result = await @case.Extractor.ExtractAsync(
                new ExtractionRequest(@case.ScopeId, @case.RootPath, "rev-1", 1), CancellationToken.None);
            if (result.Assertions.Count == 0)
            {
                silent.Add(@case.Name);
            }
        }

        Assert.True(
            silent.Count == 0,
            $"these corpora produced no assertions, so the provenance oracle would pass vacuously " +
            $"over them: {string.Join(", ", silent)}");
    }

    public static TheoryData<string> ExtractorNames()
    {
        var data = new TheoryData<string>();
        foreach (var name in new[]
                 {
                     "csharp", "bicep", "schema", "sql", "typescript", "python", "knowledge", "fixture",
                 })
        {
            data.Add(name);
        }

        return data;
    }

    [Theory]
    [MemberData(nameof(ExtractorNames))]
    public async Task EveryAssertionCitesAnArtifactThatResolves(string name)
    {
        var @case = BuildCases().Single(c => c.Name == name);
        var scopeDirectory = ScopeDirectory(@case.RootPath);
        var scopeLeaf = Path.GetFileName(scopeDirectory);

        var result = await @case.Extractor.ExtractAsync(
            new ExtractionRequest(@case.ScopeId, @case.RootPath, "rev-1", 1), CancellationToken.None);

        var unresolved = new List<string>();
        foreach (var assertion in result.Assertions)
        {
            var cited = assertion.Provenance.ArtifactPathId;

            // Shape 1 — a per-artifact citation: a file under the scope, openable by a reader.
            if (!string.IsNullOrEmpty(cited)
                && File.Exists(Path.Combine(scopeDirectory, cited.Replace('/', Path.DirectorySeparatorChar))))
            {
                continue;
            }

            // Shape 2 — a scope-summary row: the scope's own directory, cited by its leaf name.
            // EfSchemaExtractor, KnowledgeExtractor and SqlSchemaExtractor each emit one for the
            // disclosures that describe the scope as a whole rather than any single file.
            if (string.Equals(cited, scopeLeaf, StringComparison.Ordinal))
            {
                continue;
            }

            unresolved.Add(
                $"{assertion.Subject} {assertion.Predicate} {assertion.Object} cites '{cited}'");
        }

        Assert.True(
            unresolved.Count == 0,
            $"{name}: {unresolved.Count} of {result.Assertions.Count} assertions cite an artifact that " +
            $"does not resolve under '{scopeDirectory}'. A citation that cannot be opened is not a " +
            $"citation — and the same field feeds content search, which counts it as a skip and " +
            $"returns \"no matches\".{Environment.NewLine}  " +
            string.Join(Environment.NewLine + "  ", unresolved.Take(10)));
    }
}
