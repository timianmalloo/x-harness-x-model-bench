using AiDe.Core.Facts;

namespace AiDe.Core.Projections;

/// <summary>A bounded view of evidence in one supplied snapshot.</summary>
public sealed record EvidenceCensusQuery(int MaxRows = 50);

/// <summary>One exact predicate, acquisition origin, and verification status bucket.</summary>
public sealed record EvidenceCensusRow(
    string Predicate, EvidenceOrigin Origin, VerificationStatus Status, int Count);

/// <summary>The census over one snapshot: the (capped) buckets, the true totals, and any
/// disclosure the cap forced.</summary>
public sealed record EvidenceCensusResult(
    IReadOnlyList<EvidenceCensusRow> Rows,
    int TotalAssertions,
    int OmittedRows,
    IReadOnlyList<string> Disclosures,
    string SourceRevision);
