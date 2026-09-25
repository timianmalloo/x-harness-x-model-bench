using AiDe.Core.Extraction;
using AiDe.Core.Facts;

namespace AiDe.Core.Tests;

/// <summary>
/// Every specifier in this file is text the TypeScript reader once turned into an import edge.
/// </summary>
/// <remarks>
/// <para><b>MEASURED on TheTerrace, not imagined.</b> The reader produced 14 import edges. <b>10 of
/// the 12 Inferred ones named nothing that exists</b>: a sentence out of an audit log
/// (<c>the product must include full fantasy management,</c>), two fragments of bundled help text
/// (<c>${url}</c>, <c>.command()</c>), two spans of compiled JavaScript beginning
/// <c> + quoteFileNameIfNeeded(</c>, and <c>@playwright/test</c> — which reads like the one real
/// dependency in the list and is a line of a code-generation template inside Playwright's own
/// bundle. The other two edges were Verified and were a module importing ITSELF, because
/// <c>index.js</c> and <c>index.mjs</c> reduce to one module id. <b>Not one of the 14 described a
/// dependency between two things in the repository.</b></para>
///
/// <para><b>The cause was one missing anchor.</b> The <c>from '…'</c> matcher was unanchored, so the
/// word <c>from</c> anywhere in a file — inside prose, inside a template literal, at the end of one
/// string literal with the next literal supplying the closing quote — began an import statement.
/// This is the <c>uses_table</c> defect exactly: a keyword matched anywhere in a string turned
/// <i>"we update the record"</i> into a table called <c>the</c>.</para>
///
/// <para>Each case below is <b>verbatim</b> from the file that produced it, and each has a paired
/// positive assertion — narrowing a matcher until it can no longer fire is not a fix (DC-016).</para>
/// </remarks>
public sealed class TypeScriptImportPrecisionTests : IDisposable
{
    private readonly string _dir = Path.Combine(
        Path.GetTempPath(), "aide-ts-precision", Guid.NewGuid().ToString("N"));

    public TypeScriptImportPrecisionTests() => Directory.CreateDirectory(_dir);

    public void Dispose()
    {
        try { Directory.Delete(_dir, recursive: true); } catch (IOException) { }
    }

    private async Task<IReadOnlyList<EvidenceAssertion>> ExtractAsync(string name, string source)
    {
        File.WriteAllText(Path.Combine(_dir, name), source);

        return (await new TypeScriptExtractor().ExtractAsync(
            new ExtractionRequest("typescript:.", _dir, "rev-1", 1), CancellationToken.None)).Assertions;
    }

    private static IReadOnlyList<string> Imports(IEnumerable<EvidenceAssertion> assertions) =>
        [.. assertions.Where(a => a.Predicate == "imports").Select(a => a.Object)];

    private static string Describe(IEnumerable<string> objects) =>
        string.Join(" | ", objects.Select(o => $"\"{o}\""));

    [Fact]
    public async Task ProseIsNotAnImport()
    {
        // VERBATIM from TheTerrace docs/audit/audit-data.js line 89 — a prompt recorded in an audit
        // log, inside a JSON string, inside a generated data file.
        var imports = Imports(await ExtractAsync("audit-data.js", """
            window.AUDIT = { "entries": [ {
              "prompt": "(4) separate 'fantasy UX worth studying' from 'the product must include full fantasy management,' which remains an open product-scope question."
            } ] };
            """));

        Assert.True(imports.Count == 0, $"invented: {Describe(imports)}");
    }

    [Fact]
    public async Task CompiledJavaScriptIsNotAnImport()
    {
        // VERBATIM from Playwright's bundled lib/utilsBundle.js. The specifier the reader reported
        // began at the `from ` inside one string literal and ended at the opening quote of the next.
        var imports = Imports(await ExtractAsync("utilsBundle.js", """
            function toUnifiedDiff(patch) {
              if (patch.isRename) {
                ret.push("rename from " + quoteFileNameIfNeeded(((_c = patch.oldFileName) !== null && _c !== void 0 ? _c : "").replace(/^a\//, "")));
              }
            }
            """));

        Assert.True(imports.Count == 0, $"invented: {Describe(imports)}");
    }

    [Fact]
    public async Task ATemplateLiteralIsNotAnImport()
    {
        // VERBATIM from Playwright's bundled commander copy, and from the Obsidian smart-connections
        // plugin bundle. Both are help text and error text inside backticks.
        var imports = Imports(await ExtractAsync("program.js", """
            const executableMissing = `'${executableFile}' does not exist
             - if '${subcommandName}' is not meant to be an executable command, remove description parameter from '.command()' and use '.description()' instead`;
            const failed = `Failed to download or write file "${_path}" from "${url}"`;
            """));

        Assert.True(imports.Count == 0, $"invented: {Describe(imports)}");
    }

    [Fact]
    public async Task AnImportStatementInsideAGeneratedTemplateIsNotAnImport()
    {
        // THE ONE THAT LOOKED REAL. `@playwright/test` was the single unresolved specifier on
        // TheTerrace that everybody — this task's brief included — read as a genuine npm dependency.
        // MEASURED: it is a line of a code-generation TEMPLATE inside Playwright's own bundle, the
        // text it emits when it scaffolds a test file, and the interpolation in the middle of it is
        // what proves it. The file imports nothing of the sort.
        //
        // It is the case that matters most, because nothing about the specifier is suspicious: a
        // reader looking at the graph would have believed it, and only opening the source says
        // otherwise. The anchor rejects it because a statement cannot cross a quote, so it cannot run
        // out of one string literal and into another.
        var imports = Imports(await ExtractAsync("coreBundle.js", """
            function generate(options) {
              return `
              import { test, expect${options.deviceName ? ", devices" : ""} } from '@playwright/test';
              `;
            }
            """));

        Assert.True(imports.Count == 0, $"invented: {Describe(imports)}");
    }

    [Fact]
    public async Task ARealImportIsStillRead()
    {
        // THE OTHER DIRECTION, and the reason it is next to the tightening rather than in another
        // file. This codebase has already shipped a fix for over-matching that matched nothing, and
        // only measuring both directions caught it.
        var imports = Imports(await ExtractAsync("app.ts", """
            import { readFile } from './helper';
            import './side-effect';
            import * as everything from './helper';
            export { thing } from './helper';
            export * from './helper';
            """));

        Assert.Contains(imports, i => i.EndsWith("helper", StringComparison.Ordinal));
        Assert.Contains(imports, i => i.EndsWith("side-effect", StringComparison.Ordinal));
    }

    [Fact]
    public async Task AnImportStatementSpreadOverSeveralLinesIsStillRead()
    {
        // The form an anchor most easily breaks: `from` is on its own line, so a matcher anchored to
        // "a line beginning with import" and nothing else would silently drop the commonest
        // multi-symbol import in TypeScript.
        var imports = Imports(await ExtractAsync("app.ts", """
            import {
                readFile,
                writeFile,
            } from './helper';
            """));

        Assert.Contains(imports, i => i.EndsWith("helper", StringComparison.Ordinal));
    }
}
