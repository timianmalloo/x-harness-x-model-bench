using AiDe.Core.Extraction;
using AiDe.Core.Facts;

namespace AiDe.Core.Tests;

/// <summary>
/// A boundary of the product is reported as a boundary; a genuine unknown is reported as one.
/// </summary>
/// <remarks>
/// <para>Every unresolved Python import was counted together and disclosed as
/// <c>python-imports-not-resolved (246 import(s) name something this scope does not contain)</c>.
/// MEASURED on a real workspace: <b>all 246, across all 32 distinct names, were the standard
/// library</b> — sys, pathlib, json, argparse, os, subprocess, urllib.</para>
///
/// <para>The number was arithmetically right and said something false. It read as the largest
/// coverage hole in any built extractor, and was prioritised as one on that reading alone. The cost
/// of the conflation was not the wrong wording, it was the wrong plan.</para>
/// </remarks>
public sealed class PythonImportBoundaryTests : IDisposable
{
    private readonly string _dir = Path.Combine(
        Path.GetTempPath(), "aide-py-imports", Guid.NewGuid().ToString("N"));

    public PythonImportBoundaryTests() => Directory.CreateDirectory(_dir);

    public void Dispose()
    {
        try { Directory.Delete(_dir, recursive: true); } catch (IOException) { }
    }

    private async Task<IReadOnlyList<EvidenceAssertion>> ExtractAsync(string code)
    {
        File.WriteAllText(Path.Combine(_dir, "tool.py"), code);
        File.WriteAllText(Path.Combine(_dir, "helper.py"), "def assist():\n    return 1\n");

        return (await new PythonExtractor().ExtractAsync(
            new ExtractionRequest("python:.", _dir, "rev-1", 1), CancellationToken.None)).Assertions;
    }

    private static IReadOnlyList<string> Disclosures(IEnumerable<EvidenceAssertion> assertions) =>
        [.. assertions.Where(a => a.Predicate == "discloses").Select(a => a.Object)];

    [Fact]
    public async Task StandardLibraryImportsAreABoundaryNotAGap()
    {
        var disclosures = Disclosures(await ExtractAsync("""
            import sys
            import json
            from pathlib import Path
            from urllib.request import urlopen
            """));

        Assert.Contains(disclosures, d =>
            d.StartsWith(PythonExtractor.Disclosures.StandardLibraryNotIndexed, StringComparison.Ordinal));

        // And NOT reported as something the scope cannot resolve, which is what made it read as a
        // hole worth a session's work.
        Assert.DoesNotContain(disclosures, d =>
            d.StartsWith(PythonExtractor.Disclosures.ImportsNotResolved, StringComparison.Ordinal));
    }

    [Fact]
    public async Task AnImportNobodyCanIdentifyIsStillReportedAsUnresolved()
    {
        // The half that must survive: a third-party or misspelled import is a real unknown, and it
        // was invisible inside the standard-library count.
        var disclosures = Disclosures(await ExtractAsync("""
            import sys
            import some_package_nobody_has
            """));

        Assert.Contains(disclosures, d =>
            d.StartsWith(PythonExtractor.Disclosures.ImportsNotResolved, StringComparison.Ordinal));

        Assert.Contains(disclosures, d =>
            d.StartsWith(PythonExtractor.Disclosures.StandardLibraryNotIndexed, StringComparison.Ordinal));
    }

    [Fact]
    public async Task AnImportOfSomethingInTheScopeStillResolves()
    {
        var assertions = await ExtractAsync("""
            import helper
            """);

        var edge = assertions.Single(a => a.Predicate == "imports");

        Assert.Equal(VerificationStatus.Verified, edge.Status);
        Assert.DoesNotContain(Disclosures(assertions), d =>
            d.StartsWith(PythonExtractor.Disclosures.ImportsNotResolved, StringComparison.Ordinal));
    }

    [Fact]
    public async Task NeitherDisclosureFiresWhenThereIsNothingToDisclose()
    {
        // A disclosure that appears when nothing was hidden teaches a reader to skip disclosures.
        var disclosures = Disclosures(await ExtractAsync("""
            import helper
            """));

        Assert.DoesNotContain(disclosures, d =>
            d.StartsWith(PythonExtractor.Disclosures.StandardLibraryNotIndexed, StringComparison.Ordinal));
    }

    [Fact]
    public async Task TheStandardLibraryIsCountedRatherThanDrawn()
    {
        // The same reasoning one layer along. Drawing these put `sys`, `os`, `json` and `re` among
        // the most connected nodes in a real graph — 226 edges to the runtime — and the C# extractor
        // already declines to draw the BCL because a view centred on it is not a picture of anybody's
        // domain.
        var assertions = await ExtractAsync("""
            import sys
            import json
            import helper
            """);

        var targets = assertions.Where(a => a.Predicate == "imports").Select(a => a.Object).ToList();

        Assert.DoesNotContain("sys", targets);
        Assert.DoesNotContain("json", targets);
        Assert.Contains(targets, t => t.Contains("helper", StringComparison.Ordinal));
    }

    [Fact]
    public void TheStandardLibrarySetMatchesOnTheTopLevelPackage()
    {
        // `urllib.request` is the standard library exactly as much as `urllib` is, and enumerating
        // every submodule would be a set that goes stale one Python release at a time.
        Assert.True(PythonStandardLibrary.Contains("sys"));
        Assert.True(PythonStandardLibrary.Contains("urllib.request"));
        Assert.True(PythonStandardLibrary.Contains("importlib.util"));
        Assert.True(PythonStandardLibrary.Contains("os.path"));

        Assert.False(PythonStandardLibrary.Contains("requests"));
        Assert.False(PythonStandardLibrary.Contains("numpy.linalg"));
        Assert.False(PythonStandardLibrary.Contains(""));
    }
}
