using AiDe.Core.Extraction;
using AiDe.Core.Facts;

namespace AiDe.Core.Tests;

/// <summary>
/// Two scopes cannot name the same node, and an import may leave its scope.
/// </summary>
/// <remarks>
/// <para><b>The collision was certain, not theoretical.</b> Both module-shaped extractors named a
/// module by its path relative to ITS OWN SCOPE, and a scope is one directory. Every Python package
/// carries an <c>__init__.py</c>, so a repository with five packages produced five scopes each
/// declaring a module called <c>__init__</c> — one node in the graph holding the merged edges of
/// five unrelated files. Nothing failed and no count could show it.</para>
/// </remarks>
public sealed class ModuleNamingTests : IDisposable
{
    private readonly string _dir = Path.Combine(
        Path.GetTempPath(), "aide-modules", Guid.NewGuid().ToString("N"));

    public ModuleNamingTests() => Directory.CreateDirectory(_dir);

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

    [Fact]
    public async Task TwoPackagesWithAnInitFileDoNotCollapseIntoOneNode()
    {
        Write("alpha/__init__.py", "class Alpha: pass\n");
        Write("beta/__init__.py", "class Beta: pass\n");

        var alpha = await new PythonExtractor().ExtractAsync(
            new ExtractionRequest("python:alpha", Path.Combine(_dir, "alpha"), "rev-1", 1),
            CancellationToken.None);

        var beta = await new PythonExtractor().ExtractAsync(
            new ExtractionRequest("python:beta", Path.Combine(_dir, "beta"), "rev-1", 1),
            CancellationToken.None);

        var alphaModule = Assert.Single(alpha.Assertions,
            a => a.Predicate == "has_type" && a.Object == "python-module").Subject;

        var betaModule = Assert.Single(beta.Assertions,
            a => a.Predicate == "has_type" && a.Object == "python-module").Subject;

        // Before this rule both were "__init__".
        Assert.Equal("alpha/__init__", alphaModule);
        Assert.Equal("beta/__init__", betaModule);
        Assert.NotEqual(alphaModule, betaModule);
    }

    [Fact]
    public async Task AnImportThatLeavesItsScopeResolves_WhenTheWorkspaceIsKnown()
    {
        // A sibling package is a different SCOPE, so this could never resolve from inside the one
        // doing the importing. It was disclosed as unresolvable, and the edge stayed Inferred.
        Write("shared/config.py", "SETTING = 1\n");
        Write("service/app.py", "from shared.config import SETTING\n");

        var workspace = new HashSet<string>(StringComparer.Ordinal)
        {
            "shared/config", "service/app",
        };

        var result = await new PythonExtractor().ExtractAsync(
            new ExtractionRequest(
                "python:service", Path.Combine(_dir, "service"), "rev-1", 1, workspace),
            CancellationToken.None);

        var edge = Assert.Single(result.Assertions, a => a.Predicate == "imports");

        Assert.Equal("shared/config", edge.Object);
        Assert.Equal(VerificationStatus.Verified, edge.Status);
    }

    [Fact]
    public async Task AnImportThatLeavesItsScopeStaysInferred_WhenTheWorkspaceIsNotKnown()
    {
        // Null is "not supplied", which is not "there is nothing there". Without the index the
        // extractor must not upgrade the edge — it has not seen the file.
        Write("service2/app.py", "from shared.config import SETTING\n");

        var result = await new PythonExtractor().ExtractAsync(
            new ExtractionRequest("python:service2", Path.Combine(_dir, "service2"), "rev-1", 1),
            CancellationToken.None);

        var edge = Assert.Single(result.Assertions, a => a.Predicate == "imports");

        Assert.Equal("shared.config", edge.Object);
        Assert.Equal(VerificationStatus.Inferred, edge.Status);

        Assert.Contains(result.Assertions,
            a => a.Predicate == "discloses"
                && a.Object.StartsWith("python-imports-not-resolved", StringComparison.Ordinal));
    }

    [Fact]
    public async Task APackageImportResolvesToItsInitModule()
    {
        // `from shared import thing` names the DIRECTORY; the module behind it is its __init__.
        Write("pkg/shared/__init__.py", "VALUE = 1\n");
        Write("consumer/main.py", "import pkg.shared\n");

        var workspace = new HashSet<string>(StringComparer.Ordinal)
        {
            "pkg/shared/__init__", "consumer/main",
        };

        var result = await new PythonExtractor().ExtractAsync(
            new ExtractionRequest(
                "python:consumer", Path.Combine(_dir, "consumer"), "rev-1", 1, workspace),
            CancellationToken.None);

        var edge = Assert.Single(result.Assertions, a => a.Predicate == "imports");

        Assert.Equal("pkg/shared/__init__", edge.Object);
        Assert.Equal(VerificationStatus.Verified, edge.Status);
    }

    [Fact]
    public void AScopeAtTheRepositoryRootAddsNoPrefix()
    {
        // Discovery writes "." for the root. Qualifying with it would produce "./app".
        Assert.Equal(string.Empty, ModuleNaming.ScopePrefix("python:."));
        Assert.Equal("app", ModuleNaming.Qualify(ModuleNaming.ScopePrefix("python:."), "app"));
        Assert.Equal("src/app", ModuleNaming.Qualify(ModuleNaming.ScopePrefix("typescript:src"), "app"));
    }
}
