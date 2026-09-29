using AiDe.Core.Extraction;
using AiDe.Core.Facts;

namespace AiDe.Core.Tests;

/// <summary>
/// A TypeScript class carries its own members, and what is still nested says how much.
/// </summary>
/// <remarks>
/// <para><b>MEASURED across both corpora before anything was built.</b> 8 hand-written files (6 on
/// TheTerrace, 2 here), <b>2</b> column-zero classes carrying <b>11</b> members between them,
/// <b>0</b> interfaces, and <b>0</b> hand-written <c>.ts</c> or <c>.tsx</c> files anywhere — every
/// TypeScript file found in either repository was a vendored <c>.d.ts</c> under build output.
/// Against that, <b>54</b> nested declarations, 27 in each repository and all of them in one shared
/// 660-line UMD module. The nested gap is five times the member prize, and both numbers are here
/// rather than in a summary because the next person to rank this work needs them.</para>
///
/// <para><b>Why members were built for 11 facts.</b> Not for the 11. The nested COUNT cannot be
/// computed without separating a member from a hidden declaration — a method at a class's body
/// indent is reachable through its type and is not hidden — and without that separation the
/// disclosure would have said 38 where the truth is 27. Once the scan exists, emitting what it
/// found costs one line and fills two empty boxes in a class diagram that already draws
/// <c>typescript-class</c>.</para>
///
/// <para><b>The interface half is honestly unverified on real code.</b> There is no hand-written
/// interface in either repository to measure, so the interface tests here are fixtures and nothing
/// else — DC-016, named rather than papered over. It is the same code path as a class body (one
/// entry in one pattern), which is why refusing to read it would have been the stranger choice.</para>
/// </remarks>
public sealed class TypeScriptMemberTests : IDisposable
{
    private readonly string _dir = Path.Combine(
        Path.GetTempPath(), "aide-ts-members", Guid.NewGuid().ToString("N"));

    public TypeScriptMemberTests() => Directory.CreateDirectory(_dir);

    public void Dispose()
    {
        try { Directory.Delete(_dir, recursive: true); } catch (IOException) { }
    }

    private async Task<IReadOnlyList<EvidenceAssertion>> ExtractAsync(string source, string file = "module.ts")
    {
        File.WriteAllText(Path.Combine(_dir, file), source);

        return (await new TypeScriptExtractor().ExtractAsync(
            new ExtractionRequest("typescript:.", _dir, "rev-1", 1), CancellationToken.None)).Assertions;
    }

    private static IReadOnlyList<string> MembersOf(IEnumerable<EvidenceAssertion> facts, string owner) =>
        [.. facts
            .Where(a => a.Predicate == "has_member"
                && a.Subject.EndsWith("." + owner, StringComparison.Ordinal))
            .Select(a => a.Object)
            .Order(StringComparer.Ordinal)];

    private static string? NestedDisclosure(IEnumerable<EvidenceAssertion> facts) =>
        facts.Where(a => a.Predicate == "discloses")
            .Select(a => a.Object)
            .FirstOrDefault(o => o.StartsWith(
                TypeScriptExtractor.Disclosures.NestedDeclarationsNotAnalysed, StringComparison.Ordinal));

    [Fact]
    public async Task AClassCarriesTheMembersDeclaredInItsBody()
    {
        var facts = await ExtractAsync("""
            export class Order {
                id = 0;
                total() {
                    return 0;
                }
                async refresh() {
                }
            }
            """);

        var members = MembersOf(facts, "Order");

        Assert.Contains("+ id", members);
        Assert.Contains("+ total()", members);
        Assert.Contains("+ refresh()", members);
    }

    [Fact]
    public async Task AnInterfaceCarriesItsMembers()
    {
        // Fixture-only: neither measured repository contains a hand-written interface, or indeed a
        // hand-written `.ts` file at all. Recorded as such rather than claimed as coverage (DC-016).
        var facts = await ExtractAsync("""
            export interface Repository {
                readonly name: string;
                find(id: string): Order;
            }
            """);

        var members = MembersOf(facts, "Repository");

        Assert.Contains("+ name", members);
        Assert.Contains("+ find()", members);
    }

    [Fact]
    public async Task AMemberIsNamedAndNeverTyped()
    {
        // The reader holds a line of text, not a compiled symbol, and `typescript-types-not-checked`
        // is a standing disclosure rather than a formality. A member that carried a type would be
        // right about the easy cases and inventing on the rest.
        var facts = await ExtractAsync("""
            export class Store {
                save(id: number, order: Order): Promise<void> {
                }
            }
            """);

        Assert.Equal(["+ save()"], MembersOf(facts, "Store"));
    }

    [Fact]
    public async Task VisibilityComesFromWhatTheLineActuallySays()
    {
        var facts = await ExtractAsync("""
            export class Guarded {
                public open() {
                }
                protected middle() {
                }
                private closed() {
                }
                #hidden = 1;
            }
            """);

        var members = MembersOf(facts, "Guarded");

        Assert.Contains("+ open()", members);
        Assert.Contains("# middle()", members);
        Assert.Contains("- closed()", members);
        Assert.Contains("- #hidden", members);
    }

    [Fact]
    public async Task ADeclarationInsideAMethodIsNotAMember()
    {
        // A closure is not reachable by an importer and is not a member of anything. Claiming it
        // would be the column-zero error one level in.
        var facts = await ExtractAsync("""
            export class Outer {
                inner() {
                    class Hidden {}
                    function alsoHidden() {}
                }
            }
            """);

        var members = MembersOf(facts, "Outer");

        Assert.Contains("+ inner()", members);
        Assert.DoesNotContain("+ Hidden()", members);
        Assert.DoesNotContain("+ alsoHidden()", members);
    }

    [Fact]
    public async Task AnObjectLiteralAtColumnZeroOwnsNothing()
    {
        // THE REAL-CORPUS HAZARD, taken from `tests/reconnect-lifecycle.test.mjs` on TheTerrace: a
        // fake DOM built as a class immediately followed by one built as an object literal, both
        // indented identically. If the object literal's shorthand methods were attributed, the class
        // above it would gain members it does not have — an invented fact arriving labelled Verified,
        // which is the failure this reader was rewritten for.
        var facts = await ExtractAsync("""
            class Element {
                focus() {
                }
            }

            const document = {
                visibilityState: "visible",
                getElementById(id) {
                    return null;
                },
                addEventListener() {},
            };
            """);

        var members = MembersOf(facts, "Element");

        Assert.Equal(["+ focus()"], members);
        Assert.Empty(MembersOf(facts, "document"));
    }

    [Fact]
    public async Task ASecondTypeGetsItsOwnMembersAndNotTheFirstOnes()
    {
        var facts = await ExtractAsync("""
            class First {
                alpha() {
                }
            }

            class Second {
                beta() {
                }
            }
            """);

        Assert.Equal(["+ alpha()"], MembersOf(facts, "First"));
        Assert.Equal(["+ beta()"], MembersOf(facts, "Second"));
    }

    [Fact]
    public async Task TheBodyIndentIsTakenFromTheFileRatherThanAssumed()
    {
        // A file indented with tabs is still JavaScript. A hard-coded width would read every one of
        // its members as a closure and report the class as empty.
        var facts = await ExtractAsync(
            "class Wide {\n"
            + "\tfirst() {\n"
            + "\t\treturn 1;\n"
            + "\t}\n"
            + "\tsecond() {\n"
            + "\t\treturn 2;\n"
            + "\t}\n"
            + "}\n");

        var members = MembersOf(facts, "Wide");

        Assert.Contains("+ first()", members);
        Assert.Contains("+ second()", members);
    }

    [Fact]
    public async Task ARegexLiteralCarryingABraceDoesNotDerailTheReader()
    {
        // MEASURED, and the reason this reader counts indentation and never braces. Of the 8
        // hand-written files across both repositories, `scripts/check-mockup-imagery.js` on
        // TheTerrace leaves brace depth at MINUS FOUR: it contains four regex literals of the form
        // `/function esc\([\s\S]*?\n}/`, each carrying a `}` and no `{`, and SourceText has no
        // regex-literal state and cannot get one without becoming a lexer. A depth-counting reader
        // is lost from that line onward and attributes members to whatever it thinks is open.
        var facts = await ExtractAsync("""
            const grab = (re) => re.source;
            const first = grab(/function esc\([\s\S]*?\n}/);
            const second = grab(/function crest\([\s\S]*?\n}/);
            const third = grab(/function teamName\([\s\S]*?\n}/);
            const fourth = grab(/function playerFace\([\s\S]*?\n}/);

            class Afterwards {
                stillFound() {
                }
            }
            """, "regexes.js");

        Assert.Equal(["+ stillFound()"], MembersOf(facts, "Afterwards"));
    }

    [Fact]
    public async Task ATemplateLiteralIsNotAMemberList()
    {
        // A backtick string may hold lines shaped exactly like members, and SourceText.WithoutCComments
        // does not know backticks. `name: value` inside an indented fragment passes every syntactic
        // test for a property, so without the template toggle the class gains a member nobody wrote.
        var facts = await ExtractAsync("""
            export class Renderer {
                render() {
                    return `
                    name: value
                    other: thing
                    `;
                }
            }
            """);

        var members = MembersOf(facts, "Renderer");

        Assert.Equal(["+ render()"], members);
    }

    [Fact]
    public async Task AMemberInsideACommentIsNotAMember()
    {
        // Commented-out code is the worst input for a line-oriented reader because it IS real
        // syntax. Four readers were caught inventing from it on one day.
        var facts = await ExtractAsync("""
            export class Live {
                kept() {
                }
                // removed() {
                // }
                /* alsoRemoved() {
                } */
            }
            """);

        Assert.Equal(["+ kept()"], MembersOf(facts, "Live"));
    }

    [Fact]
    public async Task WhatIsStillNestedIsCountedRatherThanStatedFlatly()
    {
        // A UMD module: the whole body sits inside a factory function, so every declaration in it is
        // unreachable by name. This is not a hypothetical — it is the exact shape of
        // `docs/ai-forward-pack/scripts/docs-explorer-core.js`, which is present in BOTH repositories
        // and accounts for all 54 measured nested declarations.
        var facts = await ExtractAsync("""
            (function (root, factory) {
                root.Core = factory();
            })(globalThis, function () {
                function sortedUnique(values) {
                    return values;
                }

                function canonicalJson(value) {
                    return value;
                }

                class Helper {}

                return { sortedUnique, canonicalJson, Helper };
            });
            """, "umd.js");

        var disclosure = NestedDisclosure(facts);

        Assert.NotNull(disclosure);
        Assert.Contains("3 declaration(s)", disclosure, StringComparison.Ordinal);
    }

    [Fact]
    public async Task AMethodIsNotCountedAsAHiddenDeclaration()
    {
        // The reason members had to be read before the count could be trusted. A method sits at a
        // class's body indent and IS reachable through its type; counting it as hidden would have
        // reported 38 nested declarations on TheTerrace where the true figure is 27.
        var facts = await ExtractAsync("""
            export class Order {
                total() {
                    return 0;
                }
                refresh() {
                }
            }
            """);

        Assert.Null(NestedDisclosure(facts));
    }

    [Fact]
    public async Task NothingNestedMeansNoDisclosure()
    {
        // It used to fire on all 13 of TheTerrace's TypeScript scopes; MEASURED, only 2 of them hide
        // anything. A disclosure that fires when nothing was hidden teaches a reader to skip
        // disclosures (DC-025).
        var facts = await ExtractAsync("""
            export function run() {
                return 1;
            }
            """);

        Assert.Null(NestedDisclosure(facts));
    }

    [Fact]
    public void MembersAreAnAttributeInTypeScriptToo()
    {
        // A member is a property OF a type, not a peer of it. Emitting it as a relation would put
        // every method and field in the node table as something to navigate to.
        Assert.Contains("has_member", EvidencePredicates.Attributes);
    }
}
