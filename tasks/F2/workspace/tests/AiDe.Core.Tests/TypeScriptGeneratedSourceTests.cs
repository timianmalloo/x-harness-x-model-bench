using AiDe.Core.Extraction;
using AiDe.Core.Facts;

namespace AiDe.Core.Tests;

/// <summary>
/// A bundle nobody wrote is not source, and the count of what was skipped is on the scope.
/// </summary>
/// <remarks>
/// <para><b>MEASURED on TheTerrace.</b> Of the 88 <c>typescript-module</c> nodes the reader produced,
/// the great majority were Playwright's vendored browser bundle under
/// <c>tests/TheTerrace.E2ETests/bin/Debug/net10.0/.playwright/</c> and Obsidian plugin bundles under
/// <c>docs/.obsidian/plugins/</c>. Every one of the invented import specifiers came from one of them:
/// two from a compiled diff routine, two from a template literal in a bundled copy of commander, two
/// from a generated audit-log data file.</para>
///
/// <para><b>Two different mistakes, and both are fixed here.</b> The first is that the extractor's
/// own directory walk did not skip <c>bin</c> and <c>obj</c> while scope discovery did — two lists
/// deciding one question, which is DC-022's shape and is exactly the note already written above
/// <c>CSharpScopeDiscovery.Skip</c> about <c>artifacts</c>. The second is that a bundle can sit
/// anywhere: <c>docs/.obsidian/plugins/juggl/main.js</c> is in no build directory at all.</para>
///
/// <para><b>The line-length rule was measured, not chosen.</b> Across both corpora the longest line
/// in a file a person wrote is <b>331</b> characters (a JSX file full of class lists); the shortest
/// longest-line in a generated file is <b>1,101</b> (<c>docs/docs-index.js</c>), and the bundles run
/// to <b>2,945,894</b>. The threshold sits between the two populations at <b>500</b> — above every
/// hand-written line observed, four times the most permissive common <c>max-len</c> setting, and
/// well below anything generated.</para>
/// </remarks>
public sealed class TypeScriptGeneratedSourceTests : IDisposable
{
    private readonly string _dir = Path.Combine(
        Path.GetTempPath(), "aide-ts-generated", Guid.NewGuid().ToString("N"));

    public TypeScriptGeneratedSourceTests() => Directory.CreateDirectory(_dir);

    public void Dispose()
    {
        try { Directory.Delete(_dir, recursive: true); } catch (IOException) { }
    }

    private void Write(string relative, string content)
    {
        var path = Path.Combine(_dir, relative.Replace('/', Path.DirectorySeparatorChar));
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        File.WriteAllText(path, content);
    }

    private async Task<IReadOnlyList<EvidenceAssertion>> ExtractAsync() =>
        (await new TypeScriptExtractor().ExtractAsync(
            new ExtractionRequest("typescript:.", _dir, "rev-1", 1), CancellationToken.None)).Assertions;

    private static IReadOnlyList<string> Modules(IEnumerable<EvidenceAssertion> assertions) =>
        [.. assertions
            .Where(a => a.Predicate == "has_type" && a.Object == "typescript-module")
            .Select(a => a.Subject)];

    [Fact]
    public async Task AMinifiedBundleIsNotSource()
    {
        // The shape of docs/.obsidian/plugins/*/main.js: one line, everything on it, including
        // strings that a line-oriented reader will happily believe.
        Write("main.js", "var e=require;" + new string('x', 900) +
                         ";export class NotReallyDeclaredHere{}\n");
        Write("real.ts", "export class Real {}\n");

        var assertions = await ExtractAsync();

        Assert.DoesNotContain(Modules(assertions), m => m.EndsWith("main", StringComparison.Ordinal));
        Assert.Contains(Modules(assertions), m => m.EndsWith("real", StringComparison.Ordinal));
    }

    [Fact]
    public async Task AGeneratedDataFileIsNotSource()
    {
        // The shape of docs/audit/audit-data.js and docs/docs-index.js: ordinary short lines with a
        // few enormous ones carrying serialised prose. This is the file that produced
        // "the product must include full fantasy management," as an import specifier.
        Write("audit-data.js", "window.AUDIT = [\n  { \"prompt\": \"" + new string('a', 1200) + "\" }\n];\n");
        Write("real.ts", "export class Real {}\n");

        var assertions = await ExtractAsync();

        Assert.DoesNotContain(Modules(assertions), m => m.EndsWith("audit-data", StringComparison.Ordinal));
    }

    [Fact]
    public async Task WhatWasSkippedIsCountedAndDisclosed()
    {
        // A skipped file is a boundary, and a boundary is only honest with a number on it.
        Write("main.js", new string('x', 900) + "\n");
        Write("vendor.min.js", "var a=1;\n");
        Write("real.ts", "export class Real {}\n");

        var disclosure = (await ExtractAsync())
            .FirstOrDefault(a => a.Predicate == "discloses"
                && a.Object.StartsWith(
                    TypeScriptExtractor.Disclosures.GeneratedSourceNotRead, StringComparison.Ordinal))
            ?.Object;

        Assert.NotNull(disclosure);
        Assert.Contains("2", disclosure);
    }

    [Fact]
    public async Task NothingIsDisclosedWhenNothingWasSkipped()
    {
        // A disclosure that fires when nothing was hidden trains a reader to ignore disclosures.
        Write("real.ts", "export class Real {}\n");

        Assert.DoesNotContain(await ExtractAsync(), a => a.Predicate == "discloses"
            && a.Object.StartsWith(
                TypeScriptExtractor.Disclosures.GeneratedSourceNotRead, StringComparison.Ordinal));
    }

    [Fact]
    public async Task ALongLineDoesNotHideTheRestOfTheRepository()
    {
        // The other direction, and the one this codebase has got wrong before: a tightening that
        // stops matching anything at all. A file with an ordinary longest line is read, and the
        // threshold has to be genuinely above what people write.
        Write("wide.ts", "export const message = '" + new string('y', 300) + "';\n");

        Assert.Contains(Modules(await ExtractAsync()), m => m.EndsWith("wide", StringComparison.Ordinal));
    }

    [Fact]
    public async Task BuildOutputIsNotWalked()
    {
        // The two-lists defect. CSharpScopeDiscovery has skipped bin, obj and artifacts since it was
        // written; the extractor's own walk did not, so a scope rooted at `tests/` descended into
        // `tests/X/bin/Debug/net10.0/.playwright/package/` and indexed a vendored browser driver.
        Write("bin/Debug/net10.0/vendor/index.js", "export class Vendored {}\n");
        Write("obj/generated/thing.ts", "export class Generated {}\n");
        Write("artifacts/publish/app.js", "export class Published {}\n");
        Write("src/real.ts", "export class Real {}\n");

        var assertions = await ExtractAsync();

        Assert.DoesNotContain(assertions, a => a.Subject.EndsWith(".Vendored", StringComparison.Ordinal));
        Assert.DoesNotContain(assertions, a => a.Subject.EndsWith(".Generated", StringComparison.Ordinal));
        Assert.DoesNotContain(assertions, a => a.Subject.EndsWith(".Published", StringComparison.Ordinal));
        Assert.Contains(assertions, a => a.Subject.EndsWith(".Real", StringComparison.Ordinal));
    }
}
