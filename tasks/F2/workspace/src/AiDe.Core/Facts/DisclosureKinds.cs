namespace AiDe.Core.Facts;

/// <summary>Whether a disclosure describes a decision or a defect.</summary>
public enum DisclosureKind
{
    /// <summary>
    /// The product never intended to read this. A statement about scope.
    /// </summary>
    /// <remarks>
    /// The .NET base class library, the Python standard library, a minified bundle, a heading. A
    /// reader can act on it only by asking for the product to grow — nothing in their repository is
    /// wrong.
    /// </remarks>
    Boundary,

    /// <summary>
    /// The product meant to read this and could not. Usually a defect somebody can fix.
    /// </summary>
    /// <remarks>
    /// A prose link naming a file that is not there, an import nobody can identify, a project
    /// reference that does not resolve, source that did not parse. These are the ones worth a
    /// person's attention.
    /// </remarks>
    Gap,
}

/// <summary>
/// Which disclosures are boundaries and which are gaps, stated once.
/// </summary>
/// <remarks>
/// <para><b>Why this is a list and not a rule about names.</b> The convention is real —
/// <c>-not-indexed</c> and <c>-not-analysed</c> tend to be boundaries, <c>-missing</c> and
/// <c>-not-resolved</c> tend to be gaps — and it is a convention, not a guarantee.
/// <c>schema-changed-by-raw-sql-not-read</c> reads like a boundary and is a gap: the schema can be
/// quietly wrong. A suffix rule would classify it confidently and wrongly, which is worse than a
/// list somebody has to maintain, because the list has a test that fails when it goes stale.</para>
///
/// <para><b>Why the distinction earns its own type.</b> Conflating the two has cost this project
/// twice, both measured. Python disclosed 246 "unresolved" imports that were all standard library —
/// a boundary reported as a gap — and it was ranked the largest coverage hole in any extractor on
/// the strength of the number. TypeScript's equivalent was 83% invented facts. Both are DC-050, and
/// the fix each time was to say which kind it was.</para>
///
/// <para>A surface that can show only one line should show a gap; a panel listing everything should
/// separate them. Neither should have to infer it from a name.</para>
/// </remarks>
public static class DisclosureKinds
{
    private static readonly Dictionary<string, DisclosureKind> Known = new(StringComparer.Ordinal)
    {
        // GAPS — something is wrong, and a person can usually fix it.
        ["knowledge-prose-link-target-missing"] = DisclosureKind.Gap,
        ["knowledge-artifacts-without-ids"] = DisclosureKind.Gap,
        ["python-imports-not-resolved"] = DisclosureKind.Gap,
        ["typescript-imports-not-resolved"] = DisclosureKind.Gap,
        ["typescript-exports-not-recognised"] = DisclosureKind.Gap,
        ["packages-not-restored"] = DisclosureKind.Gap,
        ["project-reference-unresolved"] = DisclosureKind.Gap,
        ["source-did-not-parse"] = DisclosureKind.Gap,
        ["calls-not-resolved"] = DisclosureKind.Gap,

        // A boundary by its wording and a GAP by its consequence: raw SQL that carries DDL can leave
        // the recorded schema wrong rather than merely incomplete. The clearest case for why this is
        // a list rather than a rule about suffixes.
        ["schema-changed-by-raw-sql-not-read"] = DisclosureKind.Gap,

        // BOUNDARIES — the product does not read this, by decision.
        ["knowledge-headings-not-analysed"] = DisclosureKind.Boundary,
        ["knowledge-inline-code-not-resolved"] = DisclosureKind.Boundary,
        ["knowledge-glossary-terms-not-analysed"] = DisclosureKind.Boundary,
        ["knowledge-prose-link-target-not-a-node"] = DisclosureKind.Boundary,
        ["knowledge-prose-link-target-outside-workspace"] = DisclosureKind.Boundary,
        ["python-standard-library-not-indexed"] = DisclosureKind.Boundary,
        ["python-dynamic-imports-not-analysed"] = DisclosureKind.Boundary,
        ["python-nested-declarations-not-analysed"] = DisclosureKind.Boundary,
        ["typescript-node-builtins-not-indexed"] = DisclosureKind.Boundary,
        ["typescript-packages-not-indexed"] = DisclosureKind.Boundary,
        ["typescript-types-not-checked"] = DisclosureKind.Boundary,
        ["typescript-dynamic-imports-not-analysed"] = DisclosureKind.Boundary,
        ["typescript-nested-declarations-not-analysed"] = DisclosureKind.Boundary,
        ["typescript-non-exported-not-analysed"] = DisclosureKind.Boundary,
        ["typescript-generated-source-not-read"] = DisclosureKind.Boundary,
        ["generated-code-not-analysed"] = DisclosureKind.Boundary,
        ["generated-source-not-read-for-mappings"] = DisclosureKind.Boundary,
        ["generated-types-not-indexed"] = DisclosureKind.Boundary,
        ["xaml-generated-members-not-analysed"] = DisclosureKind.Boundary,
        ["build-conditions-not-evaluated"] = DisclosureKind.Boundary,
        ["bicep-expressions-not-evaluated"] = DisclosureKind.Boundary,
        ["bicep-resource-count-indeterminate"] = DisclosureKind.Boundary,
        ["schema-from-migrations-not-database"] = DisclosureKind.Boundary,
        ["sql-schema-from-files-not-database"] = DisclosureKind.Boundary,
        ["sql-column-detail-not-read"] = DisclosureKind.Boundary,
        ["sql-dynamic-ddl-not-evaluated"] = DisclosureKind.Boundary,
        ["sql-renames-not-followed"] = DisclosureKind.Boundary,
        ["calls-outside-this-repository"] = DisclosureKind.Boundary,
        ["calls-within-one-type"] = DisclosureKind.Boundary,
        ["calls-dispatched-at-runtime"] = DisclosureKind.Boundary,
        ["calls-through-a-delegate"] = DisclosureKind.Boundary,
        ["calls-through-reflection"] = DisclosureKind.Boundary,
        ["calls-dynamically-bound"] = DisclosureKind.Boundary,
        ["calls-outside-a-type"] = DisclosureKind.Boundary,
        ["python-source-unreadable"] = DisclosureKind.Gap,
        ["knowledge-body-not-analysed"] = DisclosureKind.Boundary,
    };

    /// <summary>
    /// The kind of a disclosure, by class name or by a whole folded line.
    /// </summary>
    /// <remarks>
    /// An unknown name is a <see cref="DisclosureKind.Gap"/>, deliberately. A disclosure nobody has
    /// classified is more likely to be new than to be harmless, and the cost of the two mistakes is
    /// not symmetric: a boundary shown as a gap wastes a reader's attention once, while a gap shown
    /// as a boundary is a defect filed under "working as intended". <c>EveryDisclosureHasAKind</c>
    /// exists so this default stays a safety net rather than a habit.
    /// </remarks>
    public static DisclosureKind KindOf(string disclosure)
    {
        ArgumentNullException.ThrowIfNull(disclosure);

        var split = disclosure.IndexOf(' ', StringComparison.Ordinal);
        var name = split < 0 ? disclosure : disclosure[..split];

        return Known.TryGetValue(name, out var kind) ? kind : DisclosureKind.Gap;
    }

    /// <summary>Whether this disclosure has been classified at all.</summary>
    public static bool IsClassified(string disclosureClass) =>
        Known.ContainsKey(disclosureClass ?? throw new ArgumentNullException(nameof(disclosureClass)));
}
