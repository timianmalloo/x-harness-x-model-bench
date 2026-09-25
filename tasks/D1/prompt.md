# New evidence census projection

Add one read-only projection in `src/AiDe.Core/Projections/` that summarises the evidence assertions in a supplied snapshot. Use the existing `AiDe.Core.Facts.EvidenceAssertion`, `EvidenceOrigin`, and `VerificationStatus` types. Keep this as a Core projection: no store writes, IPC or UI changes.

Provide these public types in `AiDe.Core.Projections`:

- `EvidenceCensusQuery(int MaxRows = 50)`.
- `EvidenceCensusRow(string Predicate, EvidenceOrigin Origin, VerificationStatus Status, int Count)`.
- `EvidenceCensusResult(IReadOnlyList<EvidenceCensusRow> Rows, int TotalAssertions, int OmittedRows, IReadOnlyList<string> Disclosures, string SourceRevision)`.
- `EvidenceCensusProjection.Compute(IReadOnlyList<EvidenceAssertion> assertions, EvidenceCensusQuery query, string sourceRevision)` returning `EvidenceCensusResult`.

One output row is exactly one `(Predicate, Origin, Status)` bucket in the supplied snapshot. Count every supplied assertion once, including repeated inputs; do not merge origin with verification status. Predicate equality and ordering use `StringComparer.Ordinal`. Sort rows by count descending, then predicate ascending, then origin and status by enum value. `TotalAssertions` counts the full input before capping. Clamp `MaxRows` to 1 through 100. `OmittedRows` counts buckets beyond the cap. Return one disclosure `Omitted (N)` when rows are omitted, otherwise no disclosures. Preserve `sourceRevision`, including on empty input. Reject null arguments with `ArgumentNullException`.

Add focused tests for the new projection. The task is scoped to this projection and its tests within the 45-minute budget.
