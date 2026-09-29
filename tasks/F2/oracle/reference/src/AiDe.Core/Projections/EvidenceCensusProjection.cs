using AiDe.Core.Facts;

namespace AiDe.Core.Projections;

public static class EvidenceCensusProjection
{
    public static EvidenceCensusResult Compute(
        IReadOnlyList<EvidenceAssertion> assertions, EvidenceCensusQuery query, string sourceRevision)
    {
        ArgumentNullException.ThrowIfNull(assertions);
        ArgumentNullException.ThrowIfNull(query);
        ArgumentNullException.ThrowIfNull(sourceRevision);

        var buckets = assertions
            .GroupBy(a => (a.Predicate, a.Origin, a.Status))
            .Select(group => new EvidenceCensusRow(
                group.Key.Predicate, group.Key.Origin, group.Key.Status, group.Count()))
            .OrderByDescending(row => row.Count)
            .ThenBy(row => row.Predicate, StringComparer.Ordinal)
            .ThenBy(row => row.Origin)
            .ThenBy(row => row.Status)
            .ToList();

        var cap = Math.Clamp(query.MaxRows, 1, 100);
        var omitted = Math.Max(0, buckets.Count - cap);
        IReadOnlyList<string> disclosures = omitted > 0 ? [$"Omitted ({omitted})"] : [];
        return new EvidenceCensusResult(
            buckets.Take(cap).ToList(), assertions.Count, omitted, disclosures, sourceRevision);
    }
}
