using System.Reflection;
using AiDe.Core.Facts;

namespace AiDe.Core.Tests;

/// <summary>
/// Every disclosure any extractor can emit is classified as a boundary or a gap.
/// </summary>
/// <remarks>
/// <para><b>The distinction has cost this project twice, both measured.</b> Python disclosed 246
/// "unresolved" imports that were all standard library — a boundary reported as a gap — and it was
/// ranked the largest coverage hole in any extractor on the strength of that number. TypeScript's
/// equivalent turned out to be 83% invented facts. Both are DC-050, and the fix each time was to say
/// which kind it was.</para>
///
/// <para><b>The list is read from the SOURCE, not restated here.</b> Writing the names out would be a
/// fixture restating the product's own vocabulary (DC-021) and would go stale in exactly the case
/// that matters: a disclosure added by a new reader and classified by nobody.</para>
/// </remarks>
public sealed class DisclosureKindTests
{
    /// <summary>Every disclosure-name constant declared anywhere in the extraction assembly.</summary>
    /// <remarks>
    /// Found by shape rather than by a list of type names: a nested class called <c>Disclosures</c>,
    /// or the shared <c>ExtractionDisclosures</c>. A reader that puts its constants somewhere new is
    /// the case this would otherwise miss, so the assertion below also requires a plausible count.
    /// </remarks>
    private static IReadOnlyList<string> DeclaredDisclosureNames()
    {
        var names = new List<string>();

        foreach (var type in typeof(Extraction.CSharpExtractor).Assembly.GetTypes())
        {
            if (type.Name is not ("Disclosures" or "ExtractionDisclosures")) continue;

            foreach (var field in type.GetFields(BindingFlags.Public | BindingFlags.Static))
            {
                if (field is { IsLiteral: true, FieldType: { } t } && t == typeof(string)
                    && field.GetRawConstantValue() is string value
                    && value.Contains('-', StringComparison.Ordinal))
                {
                    names.Add(value);
                }
            }
        }

        return [.. names.Distinct(StringComparer.Ordinal).Order(StringComparer.Ordinal)];
    }

    [Fact]
    public void EveryDisclosureHasAKind()
    {
        var declared = DeclaredDisclosureNames();

        // The finder itself is asserted: if it stops finding constants — a reader moves them, a type
        // is renamed — this test would pass by finding nothing, which is the shape of a control that
        // certifies rather than checks (DC-016).
        Assert.True(declared.Count > 20,
            $"only {declared.Count} disclosure constant(s) were found; the finder has stopped seeing "
            + "them and this test would pass by looking at nothing");

        var unclassified = declared.Where(d => !DisclosureKinds.IsClassified(d)).ToList();

        Assert.True(unclassified.Count == 0,
            "these disclosures are emitted and classified as neither boundary nor gap: "
            + string.Join(", ", unclassified)
            + ". An unclassified disclosure defaults to Gap, which is the safe direction and not a "
            + "substitute for deciding (DC-050).");
    }

    [Fact]
    public void AnUnknownDisclosureIsTreatedAsAGap()
    {
        // The two mistakes are not symmetric. A boundary shown as a gap wastes attention once; a gap
        // shown as a boundary is a defect filed under "working as intended".
        Assert.Equal(DisclosureKind.Gap, DisclosureKinds.KindOf("something-nobody-has-classified"));
    }

    [Fact]
    public void AFoldedLineIsClassifiedByItsClassName()
    {
        // The panel and the status line both hold whole folded sentences, not bare names.
        Assert.Equal(
            DisclosureKind.Gap,
            DisclosureKinds.KindOf("knowledge-prose-link-target-missing (109 prose link(s) …)"));

        Assert.Equal(
            DisclosureKind.Boundary,
            DisclosureKinds.KindOf("python-standard-library-not-indexed (256 import(s) …)"));
    }

    [Fact]
    public void AWordingThatReadsLikeABoundaryCanStillBeAGap()
    {
        // The clearest reason this is a list and not a rule about suffixes. `-not-read` looks like
        // every boundary in the set, and raw SQL carrying DDL can leave the recorded schema WRONG
        // rather than merely incomplete.
        Assert.Equal(
            DisclosureKind.Gap, DisclosureKinds.KindOf("schema-changed-by-raw-sql-not-read"));

        Assert.Equal(
            DisclosureKind.Boundary, DisclosureKinds.KindOf("typescript-generated-source-not-read"));
    }

    [Fact]
    public void BothKindsAreActuallyUsed()
    {
        // A classification where everything lands in one bucket is a classification that has stopped
        // discriminating — it would still pass every test above.
        var declared = DeclaredDisclosureNames();

        Assert.Contains(declared, d => DisclosureKinds.KindOf(d) == DisclosureKind.Gap);
        Assert.Contains(declared, d => DisclosureKinds.KindOf(d) == DisclosureKind.Boundary);
    }
}
