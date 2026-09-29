using AiDe.Core.Extraction;
using AiDe.Core.Facts;

namespace AiDe.Core.Tests;

/// <summary>
/// The dynamic-import disclosure fires when there is a dynamic import, and says how many.
/// </summary>
/// <remarks>
/// <para>It used to fire on every TypeScript scope in every repository, whether or not the source
/// contained a single <c>import(...)</c>. MEASURED with the reader's own generated-file filter
/// applied: 5 across 3 of TheTerrace's 6 hand-written files, and <b>zero</b> anywhere in this
/// repository — where it was disclosing on every scope regardless.</para>
///
/// <para>That is DC-025: a disclosure that fires when nothing was hidden is indistinguishable from
/// one that fires when something was, so a reader learns to skip all of them — and it is DC-050:
/// with no number attached, nothing says whether the gap is worth closing.</para>
///
/// <para><c>typescript-types-not-checked</c> is deliberately left unconditional in the same change.
/// It is unconditionally true — this reader does not typecheck any file, ever — and making a true
/// statement conditional would be the opposite error.</para>
/// </remarks>
public sealed class TypeScriptDynamicImportTests : IDisposable
{
    private readonly string _dir = Path.Combine(
        Path.GetTempPath(), "aide-ts-dynamic", Guid.NewGuid().ToString("N"));

    public TypeScriptDynamicImportTests() => Directory.CreateDirectory(_dir);

    public void Dispose()
    {
        try { Directory.Delete(_dir, recursive: true); } catch (IOException) { }
    }

    private async Task<IReadOnlyList<EvidenceAssertion>> ExtractAsync(string code, string name = "a.js")
    {
        File.WriteAllText(Path.Combine(_dir, name), code);

        return (await new TypeScriptExtractor().ExtractAsync(
            new ExtractionRequest("typescript:.", _dir, "rev-1", 1), CancellationToken.None))
            .Assertions;
    }

    private static string? Disclosure(IEnumerable<EvidenceAssertion> facts, string kind) =>
        facts.Where(a => a.Predicate == "discloses")
            .Select(a => a.Object)
            .FirstOrDefault(o => o.StartsWith(kind, StringComparison.Ordinal));

    [Fact]
    public async Task ADynamicImportIsDisclosedAndCounted()
    {
        var facts = await ExtractAsync("""
            export async function load(name) {
              const first = await import(`./plugins/${name}.js`);
              const second = require("./legacy.js");
              return [first, second];
            }
            """);

        var disclosure = Disclosure(facts, TypeScriptExtractor.Disclosures.DynamicImportsNotAnalysed);

        Assert.NotNull(disclosure);
        Assert.Contains("2 call(s)", disclosure, StringComparison.Ordinal);
    }

    [Fact]
    public async Task NoDynamicImportMeansNoDisclosure()
    {
        // The whole point. This repository has zero dynamic imports and was disclosing on every
        // scope, which is how a reader learns that disclosures carry no information.
        var facts = await ExtractAsync("""
            import { readFile } from "node:fs/promises";

            export function run() { return readFile("x"); }
            """);

        Assert.Null(Disclosure(facts, TypeScriptExtractor.Disclosures.DynamicImportsNotAnalysed));
    }

    [Fact]
    public async Task AStaticImportIsNotADynamicOne()
    {
        // A static import is RESOLVED by this reader and drawn as an edge. Counting it as hidden
        // would disclose a gap that is not there, which is the same defect as hiding one that is.
        var facts = await ExtractAsync("""
            import { a } from "./a.js";
            import "./side-effect.js";
            export const value = a;
            """);

        Assert.Null(Disclosure(facts, TypeScriptExtractor.Disclosures.DynamicImportsNotAnalysed));
    }

    [Fact]
    public async Task AMethodNamedImportOrRequireIsNotAModuleLoad()
    {
        // The lookbehind earns its place here. Without it `loader.import(` and `config.require(`
        // are indistinguishable from the real thing, and the count becomes a number nobody can act
        // on — the failure this change exists to fix, one level down.
        var facts = await ExtractAsync("""
            export function wire(loader, config) {
              loader.import("a");
              config.require("b");
            }
            """);

        Assert.Null(Disclosure(facts, TypeScriptExtractor.Disclosures.DynamicImportsNotAnalysed));
    }

    [Fact]
    public async Task ACommentedOutRequireIsNotCounted()
    {
        // Counted on comment-stripped text. Disclosing a gap because of code somebody deleted is
        // the same class of wrong answer as disclosing one that never existed.
        var facts = await ExtractAsync("""
            // const old = require("./gone.js");
            /* await import("./also-gone.js"); */
            export const kept = 1;
            """);

        Assert.Null(Disclosure(facts, TypeScriptExtractor.Disclosures.DynamicImportsNotAnalysed));
    }

    [Fact]
    public async Task TypesNotCheckedStaysUnconditional()
    {
        // The other half of the judgement, pinned. This reader does not typecheck ANY file, so the
        // statement is unconditionally true and must keep firing. Making a true, always-applicable
        // disclosure conditional would be the mirror-image defect of the one being fixed here.
        var facts = await ExtractAsync("export const x = 1;\n");

        Assert.NotNull(Disclosure(facts, TypeScriptExtractor.Disclosures.TypesNotChecked));
    }

    [Fact]
    public void TheDisclosureIsStillClassified()
    {
        // The folded line reaches the status bar and the panel by its class name, not the whole
        // sentence — so attaching a count must not change which side of boundary/gap it lands on.
        Assert.Equal(
            DisclosureKind.Boundary,
            DisclosureKinds.KindOf(
                TypeScriptExtractor.Disclosures.DynamicImportsNotAnalysed + " (2 call(s) …)"));
    }
}
