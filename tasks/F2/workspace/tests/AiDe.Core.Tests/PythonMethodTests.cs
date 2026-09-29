using AiDe.Core.Extraction;
using AiDe.Core.Facts;

namespace AiDe.Core.Tests;

/// <summary>
/// A Python class carries its own methods, and what is still nested says how much.
/// </summary>
/// <remarks>
/// <para>The reader was column-zero only, and right about what it refused: an indented <c>def</c> is
/// not a module-level function, and claiming it as one puts a symbol in the graph no importer can
/// reach. It was wrong that the only two options were "module function" or "invisible" — a method is
/// a member OF its class, which is what <c>has_member</c> already records for C#.</para>
///
/// <para>MEASURED across 113 Python files in two repositories before building: 33 methods on 22
/// classes, against 1,204 module-level functions. Thin, and the difference between a class diagram
/// that works for Python and one that shows empty boxes.</para>
/// </remarks>
public sealed class PythonMethodTests : IDisposable
{
    private readonly string _dir = Path.Combine(
        Path.GetTempPath(), "aide-py-methods", Guid.NewGuid().ToString("N"));

    public PythonMethodTests() => Directory.CreateDirectory(_dir);

    public void Dispose()
    {
        try { Directory.Delete(_dir, recursive: true); } catch (IOException) { }
    }

    private async Task<IReadOnlyList<EvidenceAssertion>> ExtractAsync(string code)
    {
        File.WriteAllText(Path.Combine(_dir, "mod.py"), code);

        return (await new PythonExtractor().ExtractAsync(
            new ExtractionRequest("python:.", _dir, "rev-1", 1), CancellationToken.None)).Assertions;
    }

    private static IReadOnlyList<string> MembersOf(IEnumerable<EvidenceAssertion> facts, string owner) =>
        [.. facts.Where(a => a.Predicate == "has_member" && a.Subject.EndsWith(owner, StringComparison.Ordinal))
            .Select(a => a.Object)];

    [Fact]
    public async Task AClassCarriesTheMethodsDeclaredInItsBody()
    {
        var facts = await ExtractAsync("""
            class Order:
                def __init__(self):
                    pass

                def total(self):
                    return 0

                async def refresh(self):
                    pass
            """);

        var members = MembersOf(facts, "Order");

        Assert.Contains("__init__", members);
        Assert.Contains("total", members);
        Assert.Contains("refresh", members);
    }

    [Fact]
    public async Task AClosureInsideAMethodIsNotAMember()
    {
        // A closure is not reachable by an importer and is not a member of anything. Claiming it
        // would be the same error the column-zero rule was written to avoid, one level in.
        var facts = await ExtractAsync("""
            class Order:
                def total(self):
                    def helper():
                        return 1
                    return helper()
            """);

        var members = MembersOf(facts, "Order");

        Assert.Contains("total", members);
        Assert.DoesNotContain("helper", members);
    }

    [Fact]
    public async Task AModuleLevelFunctionIsStillAFunctionAndNotAMember()
    {
        // The rule that was already right must survive the change.
        var facts = await ExtractAsync("""
            class Order:
                def total(self):
                    return 0

            def run():
                return Order()
            """);

        Assert.Contains(facts, a => a.Predicate == "has_type"
            && a.Object == "python-function" && a.Subject.EndsWith(".run", StringComparison.Ordinal));

        Assert.DoesNotContain("run", MembersOf(facts, "Order"));
    }

    [Fact]
    public async Task TheBodyIndentIsTakenFromTheFileRatherThanAssumed()
    {
        // A file indented with eight spaces, or with tabs, is still Python. A hard-coded four would
        // read every one of its methods as a closure and report the class as empty.
        var facts = await ExtractAsync(
            "class Wide:\n"
            + "        def first(self):\n"
            + "                return 1\n"
            + "\n"
            + "        def second(self):\n"
            + "                return 2\n");

        var members = MembersOf(facts, "Wide");

        Assert.Contains("first", members);
        Assert.Contains("second", members);
    }

    [Fact]
    public async Task ASecondClassGetsItsOwnMethodsAndNotTheFirstOnes()
    {
        var facts = await ExtractAsync("""
            class First:
                def alpha(self):
                    pass

            class Second:
                def beta(self):
                    pass
            """);

        Assert.Equal(["alpha"], MembersOf(facts, "First"));
        Assert.Equal(["beta"], MembersOf(facts, "Second"));
    }

    [Fact]
    public async Task WhatIsStillNestedIsCountedRatherThanStatedFlatly()
    {
        // The disclosure fired on every scope whether or not anything was nested, and said nothing
        // about size — which is what decides whether the gap is worth closing (DC-050, DC-025).
        var facts = await ExtractAsync("""
            class Order:
                def total(self):
                    def helper():
                        return 1

                    class Inner:
                        pass

                    return helper()
            """);

        var disclosure = facts
            .Where(a => a.Predicate == "discloses")
            .Select(a => a.Object)
            .FirstOrDefault(o => o.StartsWith(
                PythonExtractor.Disclosures.NestedDeclarationsNotAnalysed, StringComparison.Ordinal));

        Assert.NotNull(disclosure);
        Assert.Contains("2 declaration(s)", disclosure, StringComparison.Ordinal);
    }

    [Fact]
    public async Task NothingNestedMeansNoDisclosure()
    {
        var facts = await ExtractAsync("""
            class Order:
                def total(self):
                    return 0
            """);

        Assert.DoesNotContain(facts, a => a.Predicate == "discloses"
            && a.Object.StartsWith(
                PythonExtractor.Disclosures.NestedDeclarationsNotAnalysed, StringComparison.Ordinal));
    }

    [Fact]
    public void MembersAreAnAttributeInPythonToo()
    {
        // Same reasoning as C#: a method is a property OF a class, not a peer of it. Emitting it as
        // a relation would put every method in the graph as a thing to navigate to.
        Assert.Contains("has_member", EvidencePredicates.Attributes);
    }
}
