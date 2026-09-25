using AiDe.Core.Extraction;
using AiDe.Core.Facts;

namespace AiDe.Core.Tests;

/// <summary>
/// A boundary of the product is reported as a boundary; a genuine unknown is reported as one.
/// </summary>
/// <remarks>
/// <para><b>DC-050, applied to the reader the register named as the next place it would appear.</b>
/// The Python instance is written up there: 246 "unresolved" imports that were all the standard
/// library, ranked as the largest coverage hole in the product on the strength of the number alone.
/// Its residual-risk line reads <i>"TypeScript discloses 11 unresolved specifiers and has had no
/// equivalent look. They are probably npm packages — probably, which is exactly the word this class
/// is about."</i></para>
///
/// <para><b>MEASURED, so the word is no longer "probably".</b> Of the 12 Inferred specifiers on
/// TheTerrace, exactly <b>two</b> were real: <c>node:url</c> and <c>node:fs/promises</c>. Both are
/// Node's runtime. The other ten were not specifiers at all
/// (<see cref="TypeScriptImportPrecisionTests"/>) — including <c>@playwright/test</c>, which read
/// like the one genuine npm dependency and turned out to be a line of a code-generation template.
/// So the answer to "how big is the TypeScript import gap" is <b>nothing</b>: it was 83% invention
/// and 17% boundary, and 0% coverage hole. That is why the disclosure had to be split before the
/// number could mean anything.</para>
///
/// <para>The npm half is still built and still tested, because a repository with real dependencies
/// will hit it and a rule that only exists after somebody is surprised is a rule that arrives
/// late.</para>
///
/// <para>The second half of DC-050 is one layer along: the boundary is COUNTED, not DRAWN. Drawing
/// the Python standard library put <c>sys</c>, <c>os</c> and <c>json</c> among the most connected
/// nodes in a real graph; <c>fs</c>, <c>path</c> and <c>react</c> would do the same here.</para>
/// </remarks>
public sealed class TypeScriptImportBoundaryTests : IDisposable
{
    private readonly string _dir = Path.Combine(
        Path.GetTempPath(), "aide-ts-boundary", Guid.NewGuid().ToString("N"));

    public TypeScriptImportBoundaryTests() => Directory.CreateDirectory(_dir);

    public void Dispose()
    {
        try { Directory.Delete(_dir, recursive: true); } catch (IOException) { }
    }

    private async Task<IReadOnlyList<EvidenceAssertion>> ExtractAsync(string source)
    {
        File.WriteAllText(Path.Combine(_dir, "app.ts"), source);
        File.WriteAllText(Path.Combine(_dir, "helper.ts"), "export const assist = 1;\n");

        return (await new TypeScriptExtractor().ExtractAsync(
            new ExtractionRequest("typescript:.", _dir, "rev-1", 1), CancellationToken.None)).Assertions;
    }

    private static IReadOnlyList<string> Disclosures(IEnumerable<EvidenceAssertion> assertions) =>
        [.. assertions.Where(a => a.Predicate == "discloses").Select(a => a.Object)];

    private static bool Fired(IEnumerable<string> disclosures, string prefix) =>
        disclosures.Any(d => d.StartsWith(prefix, StringComparison.Ordinal));

    [Fact]
    public async Task NodeBuiltinsAreABoundaryNotAGap()
    {
        // VERBATIM from TheTerrace tests/reconnect-lifecycle.test.mjs.
        var disclosures = Disclosures(await ExtractAsync("""
            import { fileURLToPath } from 'node:url';
            import { readFile } from 'node:fs/promises';
            import * as path from 'path';
            """));

        Assert.True(Fired(disclosures, TypeScriptExtractor.Disclosures.NodeBuiltinsNotIndexed),
            $"disclosed: {string.Join(" | ", disclosures)}");

        Assert.False(Fired(disclosures, TypeScriptExtractor.Disclosures.ImportsNotResolved),
            $"disclosed: {string.Join(" | ", disclosures)}");
    }

    [Fact]
    public async Task AnNpmPackageIsABoundaryNotAGap()
    {
        // VERBATIM from Playwright's own index — a scoped package name cannot be anything else, and
        // is the one bare form that needs no configuration to identify.
        var disclosures = Disclosures(await ExtractAsync("""
            import { test, expect } from '@playwright/test';
            """));

        Assert.True(Fired(disclosures, TypeScriptExtractor.Disclosures.PackagesNotIndexed),
            $"disclosed: {string.Join(" | ", disclosures)}");

        Assert.False(Fired(disclosures, TypeScriptExtractor.Disclosures.ImportsNotResolved),
            $"disclosed: {string.Join(" | ", disclosures)}");
    }

    [Fact]
    public async Task AnInstalledPackageIsIdentifiedFromNodeModules()
    {
        // The check that could not otherwise fire in the environment that verifies it (DC-016):
        // NEITHER measured repository has a node_modules, so a bare specifier is only ever
        // identifiable by syntax there. Injecting the thing it compares against is the prescription.
        Directory.CreateDirectory(Path.Combine(_dir, "node_modules", "obsidian"));
        File.WriteAllText(Path.Combine(_dir, "node_modules", "obsidian", "package.json"), "{}");

        var assertions = await ExtractAsync("import { Plugin } from 'obsidian';\n");
        var disclosures = Disclosures(assertions);

        Assert.True(Fired(disclosures, TypeScriptExtractor.Disclosures.PackagesNotIndexed),
            $"disclosed: {string.Join(" | ", disclosures)}");

        Assert.False(Fired(disclosures, TypeScriptExtractor.Disclosures.ImportsNotResolved),
            $"disclosed: {string.Join(" | ", disclosures)}");
    }

    [Fact]
    public async Task ASpecifierNobodyCanIdentifyIsStillReportedAsUnresolved()
    {
        // The half that must survive. `@/components/Card` is a tsconfig path alias, `~/lib/x` is
        // another, and a bare name with no node_modules beside it may be either a package that is
        // not installed or a build-time alias. This reader reads no configuration, so it says so
        // rather than picking.
        var disclosures = Disclosures(await ExtractAsync("""
            import { Card } from '@/components/Card';
            import { thing } from '~/lib/thing';
            import { other } from 'some-package-nobody-installed';
            """));

        Assert.True(Fired(disclosures, TypeScriptExtractor.Disclosures.ImportsNotResolved),
            $"disclosed: {string.Join(" | ", disclosures)}");
    }

    [Fact]
    public async Task TheBoundaryIsCountedRatherThanDrawn()
    {
        var assertions = await ExtractAsync("""
            import * as fs from 'node:fs';
            import * as path from 'path';
            import { test } from '@playwright/test';
            import { assist } from './helper';
            """);

        var targets = assertions.Where(a => a.Predicate == "imports").Select(a => a.Object).ToList();

        Assert.DoesNotContain("node:fs", targets);
        Assert.DoesNotContain("path", targets);
        Assert.DoesNotContain("@playwright/test", targets);
        Assert.Contains(targets, t => t.EndsWith("helper", StringComparison.Ordinal));
    }

    [Fact]
    public async Task NoBoundaryDisclosureFiresWhenNothingWasHidden()
    {
        // A disclosure that appears when nothing was hidden teaches a reader to skip disclosures.
        var disclosures = Disclosures(await ExtractAsync("import { assist } from './helper';\n"));

        Assert.False(Fired(disclosures, TypeScriptExtractor.Disclosures.NodeBuiltinsNotIndexed),
            $"disclosed: {string.Join(" | ", disclosures)}");
        Assert.False(Fired(disclosures, TypeScriptExtractor.Disclosures.PackagesNotIndexed),
            $"disclosed: {string.Join(" | ", disclosures)}");
        Assert.False(Fired(disclosures, TypeScriptExtractor.Disclosures.ImportsNotResolved),
            $"disclosed: {string.Join(" | ", disclosures)}");
    }

    [Fact]
    public void TheBuiltinSetMatchesOnTheTopLevelModule()
    {
        // `fs/promises` is Node exactly as much as `fs` is, and the `node:` prefix is reserved by
        // the runtime, so nothing on npm can claim it.
        Assert.True(NodeBuiltinModules.Contains("fs"));
        Assert.True(NodeBuiltinModules.Contains("fs/promises"));
        Assert.True(NodeBuiltinModules.Contains("node:url"));
        Assert.True(NodeBuiltinModules.Contains("node:test"));
        Assert.True(NodeBuiltinModules.Contains("node:anything-node-adds-later"));

        // `test`, `sqlite` and `sea` are builtins ONLY behind the prefix — the runtime's own list
        // says so — so a bare `test` is a package on npm, not Node's test runner.
        Assert.False(NodeBuiltinModules.Contains("test"));
        Assert.False(NodeBuiltinModules.Contains("sqlite"));

        Assert.False(NodeBuiltinModules.Contains("react"));
        Assert.False(NodeBuiltinModules.Contains("path-browserify"));
        Assert.False(NodeBuiltinModules.Contains(""));
    }
}
