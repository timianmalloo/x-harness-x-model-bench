using AiDe.Core.Facts;

namespace AiDe.Core.Tests;

/// <summary>
/// Sixty near-identical disclosures become one line per class, with the counts added up.
/// </summary>
/// <remarks>
/// <para>MEASURED on a real index of TheTerrace: <b>178 disclosure strings, 108 distinct, for 28
/// classes</b>. `knowledge-headings-not-analysed` appeared 39 times — once per knowledge scope, each
/// with its own count — so `Distinct()` merged none of them. The list filled the user's window and
/// buried the one finding that mattered: 109 prose links naming a file that is not there.</para>
///
/// <para>Every one of those disclosures was correct. The rule this codebase arrived at — conditional,
/// counted, per scope — is right, and nobody had asked what a reader does with sixty of them. This is
/// the other half of that rule.</para>
/// </remarks>
public sealed class DisclosureSummaryTests
{
    [Fact]
    public void TheSameClassFromManyScopesBecomesOneLineWithTheTotal()
    {
        var folded = DisclosureSummary.Fold([
            "knowledge-inline-code-not-resolved (100 inline code span(s) are not matched against code symbols)",
            "knowledge-inline-code-not-resolved (250 inline code span(s) are not matched against code symbols)",
            "knowledge-inline-code-not-resolved (1,000 inline code span(s) are not matched against code symbols)",
        ]);

        var line = Assert.Single(folded);

        Assert.Contains("1,350", line, StringComparison.Ordinal);
        Assert.Contains("across 3 scope(s)", line, StringComparison.Ordinal);
    }

    [Fact]
    public void AStalePerScopeNumberIsCutRatherThanLeftBesideTheTotal()
    {
        // The defect this nearly shipped with: summing the leading count and keeping the rest of one
        // scope's sentence rendered "4,471 heading(s) in 10 document(s)" — a true workspace total
        // beside one scope's document count, which reads as though somebody counted both. Worse than
        // either number alone.
        var folded = DisclosureSummary.Fold([
            "knowledge-headings-not-analysed (914 heading(s) in 59 document(s); the body is served whole)",
            "knowledge-headings-not-analysed (86 heading(s) in 3 document(s); the body is served whole)",
        ]);

        var line = Assert.Single(folded);

        Assert.Contains("1,000 heading(s)", line, StringComparison.Ordinal);
        Assert.DoesNotContain("59", line, StringComparison.Ordinal);
        Assert.DoesNotContain("document(s)", line, StringComparison.Ordinal);
    }

    [Fact]
    public void TheCutDoesNotLeaveADanglingWord()
    {
        // "914 heading(s) in 59 document(s)" cut at the second number leaves "914 heading(s) in".
        // A dangling preposition reads like truncation damage rather than a decision.
        var line = Assert.Single(DisclosureSummary.Fold([
            "x (10 thing(s) in 5 place(s))",
            "x (10 thing(s) in 5 place(s))",
        ]));

        Assert.Equal("x (20 thing(s), across 2 scope(s))", line);
    }

    [Fact]
    public void OneScopeKeepsItsOwnSentenceExactly()
    {
        // A single scope's sentence is precisely true, including its later numbers. Folding it would
        // throw away detail to solve a problem it does not have.
        var original = "schema-changed-by-raw-sql-not-read (4 of 23 raw statement(s) carry DDL and were not folded)";

        Assert.Equal(original, Assert.Single(DisclosureSummary.Fold([original])));
    }

    [Fact]
    public void ADisclosureWithNoCountIsKeptAsItIs()
    {
        var folded = DisclosureSummary.Fold([
            "typescript-types-not-checked",
            "typescript-types-not-checked",
            "typescript-types-not-checked",
        ]);

        Assert.Equal("typescript-types-not-checked", Assert.Single(folded));
    }

    [Fact]
    public void DifferentClassesStaySeparateAndSorted()
    {
        // Folding must not merge two different admissions into one — a boundary and a gap reported
        // as one number is the defect DC-050 is about.
        var folded = DisclosureSummary.Fold([
            "zebra-not-read (1 thing(s))",
            "alpha-not-read (2 thing(s))",
            "alpha-not-read (3 thing(s))",
        ]);

        Assert.Equal(2, folded.Count);
        Assert.StartsWith("alpha-not-read", folded[0], StringComparison.Ordinal);
        Assert.Contains("5", folded[0], StringComparison.Ordinal);
        Assert.StartsWith("zebra-not-read", folded[1], StringComparison.Ordinal);
    }

    [Fact]
    public void TheOrderIsStableSoTheListDoesNotShuffleBetweenRuns()
    {
        string[] input = ["b (1 x)", "a (1 x)", "c (1 x)", "a (2 x)"];

        Assert.Equal(DisclosureSummary.Fold(input), DisclosureSummary.Fold(input));
        Assert.Equal(["a (3 x, across 2 scope(s))", "b (1 x)", "c (1 x)"], DisclosureSummary.Fold(input));
    }

    [Fact]
    public void NothingInMeansNothingOut()
    {
        Assert.Empty(DisclosureSummary.Fold([]));
    }
}
