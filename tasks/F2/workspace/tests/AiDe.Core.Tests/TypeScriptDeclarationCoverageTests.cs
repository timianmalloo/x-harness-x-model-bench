using AiDe.Core.Extraction;
using AiDe.Core.Facts;

namespace AiDe.Core.Tests;

/// <summary>
/// What the reader can see beyond the export keyword, and what it still refuses to guess at.
/// </summary>
/// <remarks>
/// <para><b>MEASURED on TheTerrace before this existed:</b> 13 TypeScript scopes, 194 facts, and the
/// only node kinds in any of them were <c>typescript-module</c> (88) and <c>typescript-const</c>
/// (18). Not one class, function, interface or type — while the scope disclosed
/// <c>typescript-non-exported-not-analysed</c> on every single one of the 13.</para>
///
/// <para><b>A declaration is a declaration whether or not it is exported.</b> A class at column zero
/// in a module is a thing that exists; the export keyword says who may reach it, which is an
/// ATTRIBUTE of the declaration rather than a condition on its existence. Recording it as
/// <c>is_exported</c> is what stops widening the reader from destroying the one thing the narrow
/// version could answer — which of these is the module's public surface.</para>
///
/// <para><b>Value bindings are still export-gated, deliberately.</b> An exported <c>const</c> is the
/// module's surface and belongs in the graph; a module-local <c>const</c> is a variable. The Python
/// reader draws the same line — it reads <c>class</c> and <c>def</c>, never module-level assignment —
/// and putting every local constant in the graph would repeat the <c>has_member</c> mistake of adding
/// thousands of nodes to serve nothing.</para>
/// </remarks>
public sealed class TypeScriptDeclarationCoverageTests : IDisposable
{
    private readonly string _dir = Path.Combine(
        Path.GetTempPath(), "aide-ts-coverage", Guid.NewGuid().ToString("N"));

    public TypeScriptDeclarationCoverageTests() => Directory.CreateDirectory(_dir);

    public void Dispose()
    {
        try { Directory.Delete(_dir, recursive: true); } catch (IOException) { }
    }

    private async Task<IReadOnlyList<EvidenceAssertion>> ExtractAsync(string source)
    {
        File.WriteAllText(Path.Combine(_dir, "module.ts"), source);

        return (await new TypeScriptExtractor().ExtractAsync(
            new ExtractionRequest("typescript:.", _dir, "rev-1", 1), CancellationToken.None)).Assertions;
    }

    private static IReadOnlyList<string> Kinds(IEnumerable<EvidenceAssertion> assertions, string name) =>
        [.. assertions
            .Where(a => a.Predicate == "has_type" && a.Subject.EndsWith("." + name, StringComparison.Ordinal))
            .Select(a => a.Object)];

    [Theory]
    [InlineData("class Thing {}", "typescript-class")]
    [InlineData("abstract class Thing {}", "typescript-class")]
    [InlineData("interface Thing {}", "typescript-interface")]
    [InlineData("type Thing = number;", "typescript-type")]
    [InlineData("enum Thing {}", "typescript-enum")]
    [InlineData("function Thing() {}", "typescript-function")]
    [InlineData("async function Thing() {}", "typescript-function")]
    [InlineData("function* Thing() {}", "typescript-function")]
    [InlineData("namespace Thing {}", "typescript-namespace")]
    public async Task ADeclarationThatIsNotExportedIsStillADeclaration(string source, string kind)
    {
        Assert.Contains(kind, Kinds(await ExtractAsync(source + "\n"), "Thing"));
    }

    [Fact]
    public async Task WhetherADeclarationIsExportedIsRecordedAsAnAttribute()
    {
        // Widening the reader must not cost the answer the narrow reader could give. `is_exported`
        // is an ATTRIBUTE — a property OF the declaration, not a link to another thing — so it is
        // registered in EvidencePredicates.Attributes and never drawn as an edge.
        var assertions = await ExtractAsync("""
            export class Public {}
            class Internal {}
            """);

        Assert.Contains(assertions, a =>
            a.Predicate == "is_exported" && a.Subject.EndsWith(".Public", StringComparison.Ordinal)
            && a.Object == "true");

        Assert.Contains(assertions, a =>
            a.Predicate == "is_exported" && a.Subject.EndsWith(".Internal", StringComparison.Ordinal)
            && a.Object == "false");

        Assert.Contains("is_exported", EvidencePredicates.Attributes);
    }

    [Fact]
    public async Task AModuleLocalValueBindingIsNotADeclaration()
    {
        // The deliberate limit. `const` at column zero with no export is a variable, and the same
        // rule that keeps `has_member` out of the node table keeps these out of it.
        var assertions = await ExtractAsync("""
            export const Surface = 1;
            const local = 2;
            let mutable = 3;
            var old = 4;
            """);

        Assert.Contains("typescript-const", Kinds(assertions, "Surface"));
        Assert.Empty(Kinds(assertions, "local"));
        Assert.Empty(Kinds(assertions, "mutable"));
        Assert.Empty(Kinds(assertions, "old"));
    }

    [Fact]
    public async Task ADeclarationInSIDEAnotherThingIsStillInvisible()
    {
        // The ceiling, unchanged and still disclosed: column zero is what tells a top-level
        // declaration from a method or a closure, exactly as it does for Python.
        //
        // The disclosure is now CONDITIONAL and CARRIES A COUNT, which is what this assertion had to
        // be rewritten to express. It compared for equality against the bare string, so a disclosure
        // that said HOW MUCH was hidden failed it — a test pinning the weaker of two behaviours.
        // Two declarations are hidden here and the disclosure now says two; `inner()` is not among
        // them, because a method is reachable through its type and is emitted as a member rather
        // than counted as a loss.
        var assertions = await ExtractAsync("""
            export class Outer {
                inner() {
                    class Hidden {}
                    function alsoHidden() {}
                }
            }
            """);

        Assert.Empty(Kinds(assertions, "Hidden"));
        Assert.Empty(Kinds(assertions, "alsoHidden"));

        var disclosure = assertions
            .Where(a => a.Predicate == "discloses")
            .Select(a => a.Object)
            .Single(o => o.StartsWith(
                TypeScriptExtractor.Disclosures.NestedDeclarationsNotAnalysed, StringComparison.Ordinal));

        Assert.Contains("2 declaration(s)", disclosure, StringComparison.Ordinal);

        Assert.Contains(assertions, a => a.Predicate == "has_member"
            && a.Subject.EndsWith(".Outer", StringComparison.Ordinal)
            && a.Object == "+ inner()");
    }

    [Fact]
    public async Task TheClosedGapIsNoLongerDisclosedAsOpen()
    {
        // Disclosing a gap that has been closed is the same defect as hiding one that has not —
        // written into UnanalysedLanguages after that list needed the same correction three times.
        var assertions = await ExtractAsync("class Internal {}\n");

        Assert.DoesNotContain(assertions, a => a.Predicate == "discloses"
            && a.Object == TypeScriptExtractor.Disclosures.NonExportedNotAnalysed);
    }
}
