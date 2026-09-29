using AiDe.Core.Extraction;

namespace AiDe.Core.Tests;

/// <summary>
/// Every spelling of an export this reader claims to know, and an alarm for the ones it does not.
/// </summary>
/// <remarks>
/// <para><b>DC-033 swept into this file.</b> The class is "a reader recognises one spelling of a
/// pattern and reports the rest as absent", and its signature is a ratio nobody looks at. The sweep
/// measured TheTerrace: <b>124 `export interface`, 26 `export type`, 16 `export const`, and 4
/// `export namespace`</b> — and the reader did not know the last of those, so four declarations were
/// reported as nothing rather than as unread. `async`, generator stars, `let` and `var` were missing
/// by the same construction.</para>
///
/// <para>The durable half is not the wider pattern, which will be wrong again for the next spelling.
/// It is that the reader now COUNTS what it failed to read and says so on the scope, which is the
/// only thing that turns this class from something a person finds by grepping into something the
/// output announces.</para>
/// </remarks>
public sealed class TypeScriptExportFormsTests : IDisposable
{
    private readonly string _dir = Path.Combine(
        Path.GetTempPath(), "aide-ts-forms", Guid.NewGuid().ToString("N"));

    public TypeScriptExportFormsTests() => Directory.CreateDirectory(_dir);

    public void Dispose()
    {
        try { Directory.Delete(_dir, recursive: true); } catch (IOException) { }
    }

    private async Task<IReadOnlyList<string>> SubjectsAsync(string source)
    {
        File.WriteAllText(Path.Combine(_dir, "module.ts"), source);

        var result = await new TypeScriptExtractor().ExtractAsync(
            new ExtractionRequest("typescript:.", _dir, "rev-1", 1), CancellationToken.None);

        return [.. result.Assertions
            .Where(a => a.Predicate == "has_type" && a.Object != "typescript-module")
            .Select(a => a.Subject)];
    }

    private async Task<string?> DisclosureAsync(string source)
    {
        File.WriteAllText(Path.Combine(_dir, "module.ts"), source);

        var result = await new TypeScriptExtractor().ExtractAsync(
            new ExtractionRequest("typescript:.", _dir, "rev-1", 1), CancellationToken.None);

        return result.Assertions
            .FirstOrDefault(a => a.Predicate == "discloses"
                && a.Object.StartsWith(
                    TypeScriptExtractor.Disclosures.ExportsNotRecognised, StringComparison.Ordinal))
            ?.Object;
    }

    [Theory]
    [InlineData("export class Thing {}", "Thing")]
    [InlineData("export interface Thing {}", "Thing")]
    [InlineData("export type Thing = number;", "Thing")]
    [InlineData("export enum Thing {}", "Thing")]
    [InlineData("export function Thing() {}", "Thing")]
    [InlineData("export const Thing = 1;", "Thing")]
    [InlineData("export default class Thing {}", "Thing")]
    [InlineData("export abstract class Thing {}", "Thing")]
    [InlineData("export declare class Thing {}", "Thing")]
    // The forms the sweep found missing.
    [InlineData("export namespace Thing {}", "Thing")]
    [InlineData("export async function Thing() {}", "Thing")]
    [InlineData("export function* Thing() {}", "Thing")]
    [InlineData("export let Thing = 1;", "Thing")]
    [InlineData("export var Thing = 1;", "Thing")]
    public async Task AnExportedDeclarationIsRead(string source, string name)
    {
        var subjects = await SubjectsAsync(source + "\n");

        Assert.Contains(subjects, s => s.EndsWith("." + name, StringComparison.Ordinal));
    }

    [Fact]
    public async Task AReExportIsNotCountedAsAMissedDeclaration()
    {
        // `export { A }` and `export * from` are not declarations. Counting them would give a miss
        // rate that never reaches zero, which is a number that says nothing.
        var disclosure = await DisclosureAsync(
            "export { A } from './a';\n" +
            "export * from './b';\n" +
            "export type { C } from './c';\n" +
            "export class Real {}\n");

        Assert.Null(disclosure);
    }

    [Fact]
    public async Task ExportingAnExpressionByDefaultIsNotCountedAsAMissedDeclaration()
    {
        // FOUND ON A SECOND REPOSITORY, which is the only reason it surfaced. `export default
        // defineConfig({...})` and `export default test;` declare nothing new — the value is either
        // anonymous or already declared above — so counting them made the miss rate fire on nearly
        // every real TypeScript codebase, where `export default` is ubiquitous. A disclosure that
        // always fires is noise.
        //
        // The exclusion had been WRITTEN IN THE DOC COMMENT before it was implemented, which is the
        // same defect shape as the evidence page documenting a byte cap it did not apply.
        var disclosure = await DisclosureAsync("""
            import { defineConfig } from 'x';
            const test = 1;
            export default defineConfig({ a: 1 });
            """);

        Assert.Null(disclosure);
    }

    [Fact]
    public async Task ExportingADeclarationByDefaultIsStillRead()
    {
        // The exclusion must not swallow the real thing: `export default class Foo {}` declares Foo.
        const string source = "export default class Foo {}\n";

        var subjects = await SubjectsAsync(source);
        Assert.Contains(subjects, s => s.EndsWith(".Foo", StringComparison.Ordinal));

        Assert.Null(await DisclosureAsync(source));
    }

    [Fact]
    public async Task AnExportSpellingTheReaderDoesNotKnowIsCountedAndDisclosed()
    {
        // THE CONTROL. A form nobody has thought of must announce itself on the scope rather than
        // wait to be found by somebody grepping a repository by hand.
        var disclosure = await DisclosureAsync(
            "export class Known {}\n" +
            "export somethingNobodyAnticipated Weird = 1;\n");

        Assert.NotNull(disclosure);
        Assert.Contains("1", disclosure);
    }
}
