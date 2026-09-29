# D1 feature as design / implement / adversarial review

Add one read-only projection in `src/AiDe.Core/Projections/` that summarises the evidence assertions in a supplied snapshot. Use the existing `AiDe.Core.Facts.EvidenceAssertion`, `EvidenceOrigin`, and `VerificationStatus` types. Keep this as a Core projection: no store writes, IPC or UI changes.

## Tracks and model routing

Run the work as three coordinated tracks. You coordinate: plan the tracks, start one sub-agent per track on the model named below, arbitrate between them, and integrate the result. Do not author track work yourself.

Use the model column for the vendor of the models you run on.

| Track | Owns | Model (Anthropic) | Model (OpenAI) |
| --- | --- | --- | --- |
| `design` | `src/AiDe.Core/Projections/EvidenceCensusContract.cs` | `claude-opus-5-5` | `gpt-6-sol` |
| `implement` | `src/AiDe.Core/Projections/EvidenceCensusProjection.cs` | `claude-sonnet-5` | `gpt-6-luna` |
| `adversarial-review` | `tests/**` | `claude-sonnet-5` | `gpt-6-luna` |

No two tracks write the same file. The public contract below is the seam between the tracks, so `implement` and `adversarial-review` can start against it before `design` finishes. A track that needs a change outside its own paths asks you; you decide and record the decision. If a sub-agent cannot be started on its named model, say so when it happens, run it on the nearest model you can, and record which model each track actually used. Never substitute silently.

## Public contract

`AiDe.Core.Projections`. Track `design` owns the shapes below; track `implement` owns the behaviour that produces them.

- `EvidenceCensusQuery(int MaxRows = 50)`.
- `EvidenceCensusRow(string Predicate, EvidenceOrigin Origin, VerificationStatus Status, int Count)`.
- `EvidenceCensusResult(IReadOnlyList<EvidenceCensusRow> Rows, int TotalAssertions, int OmittedRows, IReadOnlyList<string> Disclosures, string SourceRevision)`.
- `EvidenceCensusProjection.Compute(IReadOnlyList<EvidenceAssertion> assertions, EvidenceCensusQuery query, string sourceRevision)` returning `EvidenceCensusResult`.

## Definitions

- One output row is exactly one `(Predicate, Origin, Status)` bucket in the supplied snapshot. Count every supplied assertion once, including repeated inputs; do not merge origin with verification status.
- Predicate equality and ordering use `StringComparer.Ordinal`. Sort rows by count descending, then predicate ascending, then origin and status by enum value.
- `TotalAssertions` counts the full input before capping. Clamp `MaxRows` to 1 through 100. `OmittedRows` counts buckets beyond the cap. Return one disclosure `Omitted (N)` when rows are omitted, otherwise no disclosures.
- Preserve `SourceRevision`, including on empty input. Reject null arguments with `ArgumentNullException`.

## Adversarial review

The `adversarial-review` track does not only prove the contract holds: it actively tries to break the `implement` track's code before you integrate. Add xUnit tests under `tests/` (extend the existing test project or add a new one, your call, record which) that exercise every definition above and the boundary, grouping and ordering cases most likely to hide a bug — empty input, a single bucket, the cap at its floor and at its ceiling, a count tie, a predicate tie under different casing, and repeated assertions. Where a test finds a real defect in `implement`'s code, raise it with `implement` and record the round trip to a fix; do not edit `implement`'s files yourself.

## Conventions

- Keep this as a Core projection: no store writes, IPC or UI changes.
- The whole task fits a 60-minute budget, coordination included.
