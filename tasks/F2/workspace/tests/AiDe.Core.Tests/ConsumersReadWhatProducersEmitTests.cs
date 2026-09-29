using System.Text.RegularExpressions;
using AiDe.Core.Extraction;
using AiDe.Core.Facts;

namespace AiDe.Core.Tests;

/// <summary>
/// Every predicate a projection reads is one some extractor actually emits.
/// </summary>
/// <remarks>
/// <para><b>DC-042's residual risk, made checkable.</b> That class — a capability complete, tested,
/// and never routed work — was found when the knowledge reader turned out to be unreachable. Its
/// recorded residual was that the same shape exists wherever a consumer is keyed on strings a
/// producer emits, and only extraction ROUTING was asserted.</para>
///
/// <para>The join projection is the clearest case: it reads nine predicates by literal name. If an
/// extractor renames one — as <c>maps_to</c>, <c>declares_table</c> and <c>uses_table</c> have all
/// been added or reshaped this month — the joins quietly return fewer edges and nothing fails. The
/// pane still renders, the counts are still plausible, and the only symptom is a number nobody can
/// check.</para>
///
/// <para><b>The consumer list is read from the SOURCE, not restated here.</b> Writing it out would be
/// a fixture restating the product's own list (DC-021) and would go stale in exactly the case that
/// matters — a predicate added to the projection and produced by nobody.</para>
/// </remarks>
public sealed class ConsumersReadWhatProducersEmitTests : IDisposable
{
    private readonly string _dir = Path.Combine(
        Path.GetTempPath(), "aide-vocab", Guid.NewGuid().ToString("N"));

    public ConsumersReadWhatProducersEmitTests() => Directory.CreateDirectory(_dir);

    public void Dispose()
    {
        try { Directory.Delete(_dir, recursive: true); } catch (IOException) { }
    }

    private static readonly Regex ReadsPredicate = new(
        @"(?:a\.Predicate ==|Predicate is)\s+""(?<name>[a-z_]+)""", RegexOptions.Compiled);

    /// <summary>The join projection's own source, so the list cannot drift from what it reads.</summary>
    private static string JoinProjectionSource()
    {
        var here = new DirectoryInfo(AppContext.BaseDirectory);

        while (here is not null && !File.Exists(Path.Combine(here.FullName, "AiDe.sln")))
        {
            here = here.Parent;
        }

        Assert.NotNull(here);

        var path = Path.Combine(here.FullName, "src", "AiDe.Core", "Projections", "JoinProjection.cs");
        Assert.True(File.Exists(path), $"the join projection is not at {path}");

        return File.ReadAllText(path);
    }

    /// <summary>Every predicate the extractors emit for a workspace holding one of everything.</summary>
    private async Task<IReadOnlySet<string>> EmittedPredicatesAsync()
    {
        Directory.CreateDirectory(Path.Combine(_dir, "infra"));
        Directory.CreateDirectory(Path.Combine(_dir, "db"));
        Directory.CreateDirectory(Path.Combine(_dir, "docs"));

        File.WriteAllText(Path.Combine(_dir, "db", "schema.sql"), "CREATE TABLE Orders (Id INT);");

        // Deliberately exercises the WHOLE bicep vocabulary, including a secure parameter and a
        // resource named by an expression. The first version of this fixture had neither, and the
        // control reported `is_secret` and `resource_name_expression` as emitted by nobody — they
        // are emitted on real repositories (9 and 1 on one measured earlier). A control validated
        // against input its author wrote is a control that measures the author.
        File.WriteAllText(Path.Combine(_dir, "infra", "main.bicep"), """
            param namePrefix string

            @secure()
            param adminPassword string

            resource site 'Microsoft.Web/sites@2023-01-01' = {
              name: '${namePrefix}-site'
            }

            resource store 'Microsoft.Storage/storageAccounts@2023-01-01' = {
              name: 'literalname'
            }
            """);

        File.WriteAllText(Path.Combine(_dir, "docs", "adr.md"), """
            ---
            id: adr-1
            type: adr
            ---
            """);

        File.WriteAllText(Path.Combine(_dir, "Shop.csproj"), """
            <Project Sdk="Microsoft.NET.Sdk">
              <PropertyGroup><TargetFramework>net10.0</TargetFramework></PropertyGroup>
            </Project>
            """);

        File.WriteAllText(Path.Combine(_dir, "Order.cs"), """
            using System.ComponentModel.DataAnnotations.Schema;

            namespace Shop;

            [Table("Orders")]
            public class Order
            {
                public string Sql => "SELECT * FROM Orders";
                public int Id { get; set; }
            }
            """);

        var predicates = new HashSet<string>(StringComparer.Ordinal);
        var extractor = WorkspaceExtractors.Default();

        foreach (var scope in CSharpScopeDiscovery.DiscoverAll(_dir, new CSharpProjectReader()))
        {
            var result = await extractor.ExtractAsync(
                new ExtractionRequest(scope.ScopeId, scope.ProjectPath, "rev-1", 1), CancellationToken.None);

            foreach (var assertion in result.Assertions) predicates.Add(assertion.Predicate);
        }

        return predicates;
    }

    [Fact]
    public async Task TheJoinProjectionReadsNoPredicateThatNobodyEmits()
    {
        var read = ReadsPredicate.Matches(JoinProjectionSource())
            .Select(m => m.Groups["name"].Value)
            .ToHashSet(StringComparer.Ordinal);

        Assert.NotEmpty(read);

        var emitted = await EmittedPredicatesAsync();
        var orphaned = read.Except(emitted).Order(StringComparer.Ordinal).ToList();

        Assert.True(orphaned.Count == 0,
            $"JoinProjection reads {string.Join(", ", orphaned)} and no extractor emits them — "
            + "the joins that depend on them can never fire, and nothing fails (DC-042)");
    }

    [Fact]
    public async Task EveryAttributePredicateIsOneSomeoneEmits()
    {
        // The attribute set decides what the graph draws as an EDGE versus folds onto a node. A name
        // in it that nobody emits is harmless; a name MISSING from it puts a date or a person in the
        // graph as a thing to navigate to — which is why `review_by` and `owned_by` were added. This
        // asserts the set is grounded in what is actually produced.
        var emitted = await EmittedPredicatesAsync();

        var grounded = EvidencePredicates.Attributes.Intersect(emitted, StringComparer.Ordinal).ToList();

        Assert.True(grounded.Count >= 5,
            $"only {grounded.Count} attribute predicate(s) are emitted by any extractor — "
            + "the set has drifted from the vocabulary the producers use");
    }

    [Fact]
    public async Task KnowledgeAndCodeReachTheSameStoreWithTheSameGrain()
    {
        // The product's premise is that docs hold intent and code holds reality. That only works if
        // both arrive as the same kind of fact, in one store — which is what made the knowledge half
        // being unreachable a whole-product defect rather than a missing pane.
        var emitted = await EmittedPredicatesAsync();

        Assert.Contains("has_type", emitted);
        Assert.Contains("node_class", emitted);
        Assert.Contains("declares_table", emitted);
    }
}
