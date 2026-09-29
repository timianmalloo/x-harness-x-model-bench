using AiDe.Core.Extraction;
using AiDe.Core.Facts;

namespace AiDe.Core.Tests;

/// <summary>
/// <c>P2-EXT-01..06</c> — the C# extractor, which reads a project file as data and never runs its build.
/// </summary>
/// <remarks>
/// <para>Every fixture here is written to a temp directory rather than committed as a project, so the
/// test project's own sources cannot be swept into a compilation by the default glob — the failure
/// that broke two spike builds in this repo already.</para>
///
/// <para><b>What is asserted is what the extractor EMITS.</b> A type count would miss the defect that
/// matters: an unresolved reference leaves every local type present and correct while the edges into
/// it disappear. So the cases below assert on edges, and on the disclosures that say when edges are
/// missing.</para>
/// </remarks>
public sealed class CSharpExtractorTests : IDisposable
{
    private readonly string _root = Path.Combine(
        Path.GetTempPath(), "aide-ext-tests", Guid.NewGuid().ToString("N"));

    public CSharpExtractorTests() => Directory.CreateDirectory(_root);

    private string WriteProject(string name, string csproj, params (string File, string Source)[] sources)
    {
        var dir = Path.Combine(_root, name);
        Directory.CreateDirectory(dir);
        var path = Path.Combine(dir, name + ".csproj");
        File.WriteAllText(path, csproj);
        foreach (var (file, source) in sources)
        {
            File.WriteAllText(Path.Combine(dir, file), source);
        }

        return path;
    }

    private const string PlainCsproj = """
        <Project Sdk="Microsoft.NET.Sdk">
          <PropertyGroup>
            <TargetFramework>net10.0</TargetFramework>
            <ImplicitUsings>enable</ImplicitUsings>
            <Nullable>enable</Nullable>
          </PropertyGroup>
        </Project>
        """;

    private static ExtractionRequest Request(string projectPath, string scopeId = "scope-1") =>
        new(scopeId, projectPath, "rev-1", 1);

    private static async Task<ExtractionResult> Extract(string projectPath, string scopeId = "scope-1")
    {
        var extractor = new CSharpExtractor();
        return await extractor.ExtractAsync(Request(projectPath, scopeId), CancellationToken.None);
    }

    private static IEnumerable<EvidenceAssertion> Edges(ExtractionResult result, string predicate) =>
        result.Assertions.Where(a => a.Predicate == predicate);

    // ---- P2-EXT-01: real symbols come out ----------------------------------

    [Fact]
    public async Task ExtractsDeclaredTypes_WithTheirKindAndSourceLocation()
    {
        var project = WriteProject("Plain", PlainCsproj, ("Orders.cs", """
            namespace Shop;

            public interface IRepository { }

            public sealed class OrderRepository : IRepository
            {
                public string Name { get; set; } = string.Empty;
            }
            """));

        var result = await Extract(project);

        Assert.True(result.Complete);
        var kinds = Edges(result, "has_type").ToDictionary(a => a.Subject, a => a.Object, StringComparer.Ordinal);
        Assert.Equal("interface", kinds["Shop.IRepository"]);
        Assert.Equal("class", kinds["Shop.OrderRepository"]);

        // Provenance must point at the source, not at the project file — a citation that cannot be
        // opened is not a citation.
        var declaration = result.Assertions.First(a => a.Subject == "Shop.OrderRepository" && a.Predicate == "has_type");
        Assert.Equal("Orders.cs", declaration.Provenance.ArtifactPathId);
        Assert.StartsWith("5:", declaration.Provenance.SourceLocation, StringComparison.Ordinal);
    }

    [Fact]
    public async Task ResolvesImplementsAndDependsOn_IncludingThroughGenerics()
    {
        var project = WriteProject("Deps", PlainCsproj, ("Model.cs", """
            namespace Shop;

            public interface IClock { }

            public sealed class Order { }

            public sealed class Ledger : IClock
            {
                public IReadOnlyList<Order> Orders { get; } = [];
                public Task<Order> LoadAsync(int id) => Task.FromResult(new Order());
            }
            """));

        var result = await Extract(project);

        Assert.Contains(Edges(result, "implements"),
            a => a.Subject == "Shop.Ledger" && a.Object == "Shop.IClock");

        var dependsOn = Edges(result, "depends_on")
            .Where(a => a.Subject == "Shop.Ledger").Select(a => a.Object).ToList();

        // Unwrapped through IReadOnlyList<T> and Task<T>: the interesting edge is to Order, not only
        // to the container type.
        Assert.Contains("Shop.Order", dependsOn);
    }

    // ---- P2-EXT-02/06: what cannot be seen is disclosed, never guessed -----

    [Fact]
    public async Task GeneratedCodeIsAlwaysDisclosed_BecauseNoGeneratorEverRuns()
    {
        var project = WriteProject("Gen", PlainCsproj, ("A.cs", "namespace Shop; public class A { }"));

        var result = await Extract(project);

        Assert.Contains(Edges(result, CSharpExtractor.DisclosurePredicate),
            a => a.Object == ExtractionDisclosures.GeneratedCodeNotAnalysed);
    }

    [Fact]
    public async Task AnUnrestoredProjectDisclosesIt_RatherThanAnsweringAsThoughNothingIsMissing()
    {
        // No obj/project.assets.json — the state every freshly cloned repository is in, and the one
        // the strategy refuses to fix by running a restore (which is MSBuild evaluation).
        var project = WriteProject("Unrestored", """
            <Project Sdk="Microsoft.NET.Sdk">
              <PropertyGroup>
                <TargetFramework>net10.0</TargetFramework>
              </PropertyGroup>
              <ItemGroup>
                <PackageReference Include="Some.Package" Version="1.0.0" />
              </ItemGroup>
            </Project>
            """, ("A.cs", "namespace Shop; public class A { }"));

        var result = await Extract(project);

        Assert.Contains(Edges(result, CSharpExtractor.DisclosurePredicate),
            a => a.Object == ExtractionDisclosures.PackagesNotRestored);
    }

    [Fact]
    public async Task AnUnresolvedEdgeIsNotEmitted_BecauseItWouldPointAtANodeThatMayNotExist()
    {
        var project = WriteProject("Broken", PlainCsproj, ("A.cs", """
            namespace Shop;

            public sealed class A
            {
                public SomeTypeThatDoesNotExist? Thing { get; set; }
            }
            """));

        var result = await Extract(project);

        // The type itself survives — the file still declares it.
        Assert.Contains(Edges(result, "has_type"), a => a.Subject == "Shop.A");

        // But nothing claims an edge to a name the compiler could not bind.
        Assert.DoesNotContain(Edges(result, "depends_on"),
            a => a.Object.Contains("SomeTypeThatDoesNotExist", StringComparison.Ordinal));
    }

    [Fact]
    public async Task DisclosuresHangOffTheScopeNode_SoAProjectionOverThatScopeCanSurfaceThem()
    {
        var project = WriteProject("Scoped", PlainCsproj, ("A.cs", "namespace Shop; public class A { }"));

        var result = await Extract(project, "csharp:Scoped:net10.0");

        Assert.All(
            Edges(result, CSharpExtractor.DisclosurePredicate),
            a => Assert.Equal(CSharpExtractor.ScopeNodeId("csharp:Scoped:net10.0"), a.Subject));
    }

    // ---- the scope grain ---------------------------------------------------

    [Fact]
    public async Task AMultiTargetedProjectYieldsDifferentTypesPerFramework()
    {
        // The grain finding: one scope per project would have to pick a framework and be silently
        // wrong about the #if-gated types in the others.
        var project = WriteProject("Multi", """
            <Project Sdk="Microsoft.NET.Sdk">
              <PropertyGroup>
                <TargetFrameworks>net10.0;netstandard2.0</TargetFrameworks>
              </PropertyGroup>
            </Project>
            """, ("Shapes.cs", """
            namespace Shop;

            public class Always { }

            #if NET10_0_OR_GREATER
            public class ModernOnly { }
            #endif

            #if NETSTANDARD2_0
            public class LegacyOnly { }
            #endif
            """));

        var extractor = new CSharpExtractor();
        Assert.Equal(["net10.0", "netstandard2.0"], extractor.TargetFrameworks(project));

        var modern = await Extract(project, "csharp:Multi:net10.0");
        var legacy = await Extract(project, "csharp:Multi:netstandard2.0");

        var modernTypes = Edges(modern, "has_type").Select(a => a.Subject).ToList();
        var legacyTypes = Edges(legacy, "has_type").Select(a => a.Subject).ToList();

        Assert.Contains("Shop.ModernOnly", modernTypes);
        Assert.DoesNotContain("Shop.ModernOnly", legacyTypes);
        Assert.Contains("Shop.LegacyOnly", legacyTypes);
        Assert.DoesNotContain("Shop.LegacyOnly", modernTypes);
    }

    // ---- P2-EXT-04: the scope budget --------------------------------------

    [Fact]
    public async Task AnExpiredScopeBudget_QuarantinesTheScopeInsteadOfFailingTheRefresh()
    {
        var project = WriteProject("Slow", PlainCsproj, ("A.cs", "namespace Shop; public class A { }"));

        using var expired = new CancellationTokenSource();
        await expired.CancelAsync();

        var result = await new CSharpExtractor().ExtractAsync(Request(project), expired.Token);

        // Incomplete, with a reason — not an exception that would abort every other scope's refresh.
        Assert.False(result.Complete);
        Assert.Contains(result.Diagnostics, d => d.ErrorCode == "AIDE-EXT-TIMEOUT");

        // And no partial evidence: a half-extracted scope committed as a snapshot would be a graph
        // that silently lost edges, which is worse than one that reports it could not finish.
        Assert.Empty(result.Assertions);
    }

    [Fact]
    public async Task AMissingProjectIsAnIncompleteExtraction_NotACrash()
    {
        var result = await Extract(Path.Combine(_root, "nope", "Nope.csproj"));

        Assert.False(result.Complete);
        Assert.Contains(result.Diagnostics, d => d.ErrorCode == "AIDE-EXT-PROJECT-MISSING");
    }

    // ---- idempotency -------------------------------------------------------

    [Fact]
    public async Task ReExtractingAnUnchangedProject_ProducesIdenticalAssertionIds()
    {
        // The store's replay guarantee depends on this: a re-extraction must be idempotent rather
        // than a second set of rows saying the same thing.
        var project = WriteProject("Stable", PlainCsproj, ("A.cs", """
            namespace Shop;
            public sealed class A { public string Name { get; set; } = ""; }
            """));

        var first = await Extract(project);
        var second = await Extract(project);

        Assert.Equal(
            first.Assertions.Select(a => a.AssertionId).OrderBy(x => x, StringComparer.Ordinal),
            second.Assertions.Select(a => a.AssertionId).OrderBy(x => x, StringComparer.Ordinal));
    }

    [Fact]
    public async Task TheExtractorAdvertisesItsScopeKind() =>
        await Task.Run(() => Assert.Equal("csharp", new CSharpExtractor().ScopeKind));

    public void Dispose()
    {
        try { Directory.Delete(_root, recursive: true); }
        catch (IOException) { }
    }
}
