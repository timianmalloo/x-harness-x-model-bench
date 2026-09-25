using AiDe.Core.Facts;

namespace AiDe.Core.Extraction;

/// <summary>
/// Shared rules every extractor applies to the facts it is about to return.
/// </summary>
/// <remarks>
/// <para><b>Written on the third copy, not the first.</b> The Python and TypeScript readers each grew
/// the same six-line dedupe after the same failure — a raw
/// <c>UNIQUE constraint failed: evidence_assertion_fact…</c> from the middle of an index on a real
/// repository — and the C# reader hit it a third time the moment it started emitting
/// <c>uses_table</c>, because one store class names the same table in four statements.</para>
///
/// <para><b>Why the store's key is not the thing to loosen.</b> P1-STORE-05 rejects the same fact
/// twice for one revision deliberately: it is the control that catches a producer emitting
/// contradictory or duplicated evidence. Silencing it would trade a loud correct failure for a quiet
/// wrong graph. An identical triple carries no information, so removing it before the write is the
/// honest fix — and doing it in one place means the fourth extractor inherits it.</para>
/// </remarks>
public static class ExtractionFacts
{
    /// <summary>
    /// One fact per distinct subject-predicate-object, keeping the first occurrence.
    /// </summary>
    /// <remarks>
    /// The FIRST is kept because provenance points at where a fact was first seen, and the earliest
    /// mention is the one a reader following the graph would want to open. Status is deliberately
    /// not part of the key: an extractor that asserts the same triple both Verified and Inferred has
    /// a defect, and collapsing the pair here would hide it — the store's key still catches that.
    /// </remarks>
    public static IReadOnlyList<EvidenceAssertion> Distinct(IEnumerable<EvidenceAssertion> assertions)
    {
        ArgumentNullException.ThrowIfNull(assertions);

        var seen = new HashSet<(string, string, string)>();
        var kept = new List<EvidenceAssertion>();

        foreach (var assertion in assertions)
        {
            if (seen.Add((assertion.Subject, assertion.Predicate, assertion.Object)))
            {
                kept.Add(assertion);
            }
        }

        return kept;
    }
}
