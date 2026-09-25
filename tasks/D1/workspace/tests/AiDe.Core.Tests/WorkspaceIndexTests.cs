using AiDe.Core;
using AiDe.Core.Extraction;

namespace AiDe.Core.Tests;

/// <summary>
/// <c>P2-EXT-02</c> and the scope grain, through the path the shell actually calls.
/// </summary>
/// <remarks>
/// <para><b>The property under test is containment.</b> A repository is many projects, and the
/// unpredictable ones are environmental — a missing SDK, a broken project file, a project that takes
/// too long. Any of those must cost the user <i>that project's</i> evidence and nothing else. A
/// refresh that fails whole because one project would not load is the failure mode that makes an
/// indexer useless on real repositories.</para>
///
/// <para>These run against a temp repository rather than this one, so a project added to AiDe later
/// cannot silently change what a count here means.</para>
/// </remarks>
public sealed class WorkspaceIndexTests : IDisposable
{
    private readonly string _root = Path.Combine(
        Path.GetTempPath(), "aide-index-tests", Guid.NewGuid().ToString("N"));

    private readonly string _data = Path.Combine(
        Path.GetTempPath(), "aide-index-data", Guid.NewGuid().ToString("N"));

    public WorkspaceIndexTests()
    {
        Directory.CreateDirectory(_root);
        Directory.CreateDirectory(_data);
    }

    private const string Plain = """
        <Project Sdk="Microsoft.NET.Sdk">
          <PropertyGroup>
            <TargetFramework>net10.0</TargetFramework>
            <ImplicitUsings>enable</ImplicitUsings>
          </PropertyGroup>
        </Project>
        """;

    private void WriteProject(string name, string csproj, string source)
    {
        var dir = Path.Combine(_root, name);
        Directory.CreateDirectory(dir);
        File.WriteAllText(Path.Combine(dir, name + ".csproj"), csproj);
        File.WriteAllText(Path.Combine(dir, "Source.cs"), source);
    }

    private WorkspaceCore Open() =>
        WorkspaceCore.Open("ws-1", _root, _data, new CompositeExtractor(new CSharpExtractor(), new FixtureExtractor()));

    // ---- discovery and the scope grain -------------------------------------

    [Fact]
    public void DiscoveryYieldsOneScopePerProjectAndTargetFramework()
    {
        WriteProject("Single", Plain, "namespace A; public class One { }");
        WriteProject("Multi", """
            <Project Sdk="Microsoft.NET.Sdk">
              <PropertyGroup><TargetFrameworks>net10.0;netstandard2.0</TargetFrameworks></PropertyGroup>
            </Project>
            """, "namespace B; public class Two { }");

        var scopes = CSharpScopeDiscovery.Discover(_root);

        Assert.Equal(3, scopes.Count);
        Assert.Contains(scopes, s => s.ScopeId == "csharp:Single:net10.0");
        Assert.Contains(scopes, s => s.ScopeId == "csharp:Multi:net10.0");
        Assert.Contains(scopes, s => s.ScopeId == "csharp:Multi:netstandard2.0");
    }

    [Fact]
    public void DiscoverySkipsBuildOutput_SoAProjectIsNotIndexedTwice()
    {
        WriteProject("Real", Plain, "namespace A; public class One { }");

        // A copy of the project file where a build would have left one. Indexing it would produce a
        // second scope for the same code, and the graph would show every type twice.
        var stale = Path.Combine(_root, "Real", "obj", "Debug");
        Directory.CreateDirectory(stale);
        File.WriteAllText(Path.Combine(stale, "Real.csproj"), Plain);

        Assert.Single(CSharpScopeDiscovery.Discover(_root));
    }

    // ---- P2-EXT-02: a broken project quarantines itself --------------------

    [Fact]
    public async Task ABrokenProjectQuarantinesItself_AndEveryOtherProjectStillIndexes()
    {
        WriteProject("Good", Plain, "namespace A; public class Good { }");
        WriteProject("AlsoGood", Plain, "namespace B; public class AlsoGood { }");

        // Not valid XML: the project file itself cannot be read. The extractor must report that and
        // the run must continue.
        var broken = Path.Combine(_root, "Broken");
        Directory.CreateDirectory(broken);
        File.WriteAllText(Path.Combine(broken, "Broken.csproj"), "<Project><Unclosed>");
        File.WriteAllText(Path.Combine(broken, "Source.cs"), "namespace C; public class Broken { }");

        using var core = Open();
        var result = await core.IndexCSharpAsync("rev-1");

        Assert.Equal(3, result.ScopesFound);
        Assert.Equal(2, result.ScopesIndexed);
        Assert.Single(result.Failed);
        Assert.Contains("Broken", result.Failed[0], StringComparison.Ordinal);

        // The evidence from the healthy projects is committed and queryable — the whole point.
        Assert.True(result.Assertions > 0);
        var describe = core.Projections.Describe("A.Good", 10);
        Assert.Equal("A.Good", describe.Node.NodeId);
        Assert.NotEmpty(describe.Neighbors);
    }

    [Fact]
    public async Task AFailedScopeRaisesAHealthIncident_RatherThanFailingSilently()
    {
        WriteProject("Good", Plain, "namespace A; public class Good { }");
        var broken = Path.Combine(_root, "Broken");
        Directory.CreateDirectory(broken);
        File.WriteAllText(Path.Combine(broken, "Broken.csproj"), "<Project><Unclosed>");

        using var core = Open();
        await core.IndexCSharpAsync("rev-1");

        // An operator must be able to see WHY the graph is missing a project.
        Assert.NotEmpty(core.Incidents.Read());
    }

    [Fact]
    public async Task AScopeThatExceedsItsBudget_IsQuarantined_AndTheRunContinues()
    {
        WriteProject("A", Plain, "namespace A; public class One { }");
        WriteProject("B", Plain, "namespace B; public class Two { }");

        using var core = Open();

        // A budget nothing can meet. The run must still complete and report, rather than throwing
        // and costing every scope.
        var result = await core.IndexCSharpAsync("rev-1", perScopeBudget: TimeSpan.Zero);

        Assert.Equal(2, result.ScopesFound);
        Assert.Equal(0, result.ScopesIndexed);
        Assert.Equal(2, result.Failed.Count);
    }

    // ---- disclosures reach the summary -------------------------------------

    [Fact]
    public async Task TheSummaryCarriesWhatWasNotAnalysed_SoAPartialGraphNeverLooksComplete()
    {
        WriteProject("Packaged", """
            <Project Sdk="Microsoft.NET.Sdk">
              <PropertyGroup><TargetFramework>net10.0</TargetFramework></PropertyGroup>
              <ItemGroup><PackageReference Include="Some.Package" Version="1.0.0" /></ItemGroup>
            </Project>
            """, "namespace A; public class One { }");

        using var core = Open();
        var result = await core.IndexCSharpAsync("rev-1");

        Assert.Contains(ExtractionDisclosures.PackagesNotRestored, result.Disclosures);
        Assert.Contains(ExtractionDisclosures.GeneratedCodeNotAnalysed, result.Disclosures);
    }

    [Fact]
    public async Task AnEmptyWorkspaceSaysSo_RatherThanReportingSuccess()
    {
        using var core = Open();
        var result = await core.IndexCSharpAsync("rev-1");

        Assert.Equal(0, result.ScopesFound);
        Assert.Equal(0, result.ScopesIndexed);
    }

    public void Dispose()
    {
        Microsoft.Data.Sqlite.SqliteConnection.ClearAllPools();
        foreach (var dir in new[] { _root, _data })
        {
            try { Directory.Delete(dir, recursive: true); } catch (IOException) { }
        }
    }
}
