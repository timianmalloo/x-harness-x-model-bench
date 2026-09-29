# F2 oracle

F2 is the scenario-6 task: D1's feature (the evidence census projection) run as three coordinated
tracks (`design`, `implement`, `adversarial-review`) whose sub-agents run on the models in
`task.yaml`'s `model_map`, following the pattern F1 established for scenario 6 (a flat
`role@vendor` map per R-73, the `delegate` tool class per R-74) and the portable oracle shape D2
established (the oracle command invokes `dotnet` directly, no `cmd.exe` wrapper). Nothing in this
folder except `workspace/` reaches the agent.

## Source, licence and vendoring

`source.commit` is `88e0c33f0b7c419b1e64d87686987374285292d8` — the same ai-de commit D1 (the
worked pattern for this feature) and D2 vendor. `tasks/F2/workspace/` was built by copying
`tasks/D1/workspace/` byte for byte (`diff -rq tasks/D1/workspace tasks/D2/workspace` already
proved D1 and D2 are identical at this pin; the same copy for F2 was verified the same way:
531 files, 5,272,935 bytes, `diff -rq tasks/F2/workspace tasks/D1/workspace` exits 0 with no
output). Same `vendored_paths`, same `excluded_paths`
(`src/AiDe.Core/Watcher/DreamCorpusReader.cs` and its matching test carry the AI-Forward Pack
marker and fail R-42's scan, as in D1/D2), same MIT licence and `Copyright (c) 2026
timianmalloo`. `rg -n -F -f bench/pack-markers.txt tasks/F2/workspace tasks/F2/tests tasks/F2/oracle
tasks/F2/prompt.md tasks/F2/task.yaml` returned no matches (`rg` exit 1). No new file introduces a
user-profile path or e-mail address; the one pre-existing fixture literal D2's evidence describes
(`tests/AiDe.Core.Tests/Composer/TheVocabularyIsClosedTests.cs:283`) is unchanged, vendored byte
for byte, and under a `vendored_paths` entry the profile-path scan already skips.

## The feature, reframed as three tracks

The feature is exactly D1's: one read-only projection, `AiDe.Core.Projections.EvidenceCensusProjection`,
over the existing `AiDe.Core.Facts.EvidenceAssertion` types. F2 does not change the contract; it
changes who builds it and how. `prompt.md` splits D1's single-agent brief into three tracks so
their sub-agents cannot collide on a file:

- `design` owns `src/AiDe.Core/Projections/EvidenceCensusContract.cs` — the three record shapes
  (`EvidenceCensusQuery`, `EvidenceCensusRow`, `EvidenceCensusResult`).
- `implement` owns `src/AiDe.Core/Projections/EvidenceCensusProjection.cs` — the `Compute` method
  that produces them.
- `adversarial-review` owns `tests/**` — not a proof-the-contract-holds test suite (that is the
  hidden oracle's job, never seen by the agent), but tests aimed at breaking `implement`'s code
  before integration, with a recorded round trip on any real defect found.

Reflection means the split costs nothing at the oracle: the hidden tests below look up
`AiDe.Core.Projections.EvidenceCensusQuery`/`EvidenceCensusResult`/`EvidenceCensusProjection` by
name in the compiled assembly, not by source file, so it does not matter which track's file defines
which type as long as the assembly exposes the names in `prompt.md`.

## Correctness: the hidden tests

`tests/F2.HiddenTests/` holds D1's 5 xUnit tests unchanged (same file, same assertions — the
contract is unchanged) over the same reflection harness D1 and D2 use: the base workspace has no
`EvidenceCensusProjection`/`EvidenceCensusQuery`/`EvidenceCensusResult` types, so the test project
compiles unconditionally and each test fails at runtime, asserting a non-null reflected
type/member. The grading copy receives `tests/` only after the model turn.

The reference in `oracle/reference/src/AiDe.Core/Projections/` (two files, split the same way the
prompt asks the `design` and `implement` tracks to split it: `EvidenceCensusContract.cs` for the
three records, `EvidenceCensusProjection.cs` for `Compute`) passes all 5 hidden tests. This proves
the track split itself does not change what the hidden oracle measures.

## Discrimination proof

Command: `uv run python tasks/F2/oracle/probe.py`. The probe calls
`harness_bench.grade.correctness.grade` twice. For the reference call, it copies `workspace/` and
overlays both reference files under `src/AiDe.Core/Projections/`. The shared grader then overlays
`tasks/F2/tests/` into its own disposable grading copy. The reference never enters the agent
workspace.

The `task.yaml` oracle command is `["dotnet", "test", "F2.HiddenTests/F2.HiddenTests.csproj",
"-p:RestoreSources=.", "-p:NuGetAudit=false", "--logger", "trx;LogFileName=f2-hidden.trx",
"--results-directory", "TestResults", "-v:q"]` — invoked directly, no shell wrapper, forward-slash
path, the same portable shape D2 uses (not D1's/F1's `cmd.exe /c ...\run.cmd`).

| Grading copy | dotnet exit | Named TRX | xUnit result | `correctness.grade` result |
| --- | ---: | --- | --- | --- |
| Pinned base | 1 | `TestResults/f2-hidden.trx` | 5 failed, 0 passed, 0 skipped | `passed=0`, `partial_credit=0`, `reason=None` |
| Reference overlay | 0 | `TestResults/f2-hidden.trx` | 0 failed, 5 passed, 0 skipped | `passed=1`, `partial_credit=1`, `reason=None` |

Exact counts and the command transcript are in `evidence.md`.

## Every hidden check fails for a plausible wrong answer

Command: `uv run python tasks/F2/oracle/mutants.py`. Six named mutants of the reference, each one
localized text change a real implementer plausibly makes, are each overlaid on the workspace in
place of the reference and graded through the same shared correctness grader. Every mutant is
killed (`passed=0`), and between them they cover all 5 hidden tests — no test in the suite is a
keyword/no-op check that cannot fail:

| Mutant (plausible wrong answer) | Killed by |
| --- | --- |
| `ascending-count-sort` — sorts rows by count ascending instead of descending | `CountsEveryInputWithoutCollapsingOriginOrVerificationStatus`, `SortsByCountThenOrdinalPredicateThenEnumValues` |
| `cap-unclamped` — uses `query.MaxRows` as the cap with no `Math.Clamp(1, 100)` | `CapsBucketsButKeepsFullTotalsAndDisclosesOmissions` |
| `status-ignored-in-grouping` — groups by predicate and origin only, reporting `Verified` for every row's `Status` | `CountsEveryInputWithoutCollapsingOriginOrVerificationStatus` |
| `null-query-check-removed` — drops `ArgumentNullException.ThrowIfNull(query)` (a `null` query then throws `NullReferenceException` at `query.MaxRows`, not `ArgumentNullException`) | `RejectsNullInputs` |
| `revision-not-preserved` — always returns the literal `"unknown"` instead of the supplied `sourceRevision` | `EmptySnapshotStillCarriesItsRevision` |
| `no-disclosure-ever` — never emits the `Omitted (N)` disclosure, even when rows are capped | `CapsBucketsButKeepsFullTotalsAndDisclosesOmissions` |

assume: removing `ArgumentNullException.ThrowIfNull(assertions)` alone does **not** discriminate —
tried first and observed `passed=1` (`evidence.md`) — because `Enumerable.GroupBy`'s own
implementation already throws `ArgumentNullException` for a `null` source, so the reference's
explicit check on `assertions` is redundant with the BCL's own guard for this exact code shape.
**Confirm:** re-run `uv run python tasks/F2/oracle/mutants.py` with that mutant restored; it should
still show `passed=1`. **Breaks if false:** the framework's null-source behaviour has changed, and
the `RejectsNullInputs` test's assertions-argument case is unguarded by anything in the reference
except the BCL. The mutation suite instead discriminates the `query`-argument null check, which has
no such BCL backstop (`query.MaxRows` is a direct property read on a possibly-null reference).

## Coordination grader notes (for `grade/coordination.py`, not built)

As F1 (`tasks/F1/oracle/README.md`'s "Coordination grader notes"), with F2's three roles in place
of F1's: model-map adherence per role (`design`/`implement`/`adversarial-review`) against the
served model, by base id; per-agent attribution against the disjoint owned paths above
(`EvidenceCensusContract.cs`, `EvidenceCensusProjection.cs`, `tests/**`); intent-log completeness
(pack=on only) expecting one delegation per track naming its model, any cross-track change request
and its decision, the `adversarial-review` round trip on a found defect (if any), and the
integration step; and the contract section of `prompt.md` as the one planned seam.

## MAST coding notes (for the judge)

As F1's MAST table (`tasks/F1/oracle/README.md`), unchanged: the same 14 modes apply, with F2's own
anchors — for example 1.2 (disobey role specification) anchors on the coordinator writing
`EvidenceCensusContract.cs` or `EvidenceCensusProjection.cs` itself, or `adversarial-review` editing
either of those files instead of raising the round trip described in `prompt.md`; 2.3 (task
derailment) anchors on out-of-scope work such as a store write, an IPC change, or a UI surface,
which `prompt.md` explicitly excludes.

## Reference solution's size and time against the 60-minute budget

The reference is D1's own reference split across two files (49 lines total, counting blank lines
and braces: `EvidenceCensusContract.cs` 19 lines, `EvidenceCensusProjection.cs` 30 lines —
`wc -l`, `evidence.md`). `dotnet test` itself completes in well under one second
against both the base and the reference (`evidence.md`) — the oracle's own run time, not an agent's
authoring time. assume: the coordination overhead (planning three tracks, one delegation each,
arbitrating any seam request, integrating) fits the 60-minute budget with headroom, on the basis
that F1 — a larger single-file-per-track surface (units, an aggregate with invariants, six derived
quantities, plus a full xUnit project) under the same three-track shape — fits the same 60-minute
budget, and F2's per-track surface is smaller than any one of F1's three tracks (one
record file, one 24-line compute method, and tests against a 5-case contract already fully
specified in `prompt.md`, versus F1's from-scratch units/aggregate/derivations/tests).
**Confirm:** the first real cell's `duration_seconds` (report row 21) once F2 runs in a harness.
**Breaks if false:** the budget in `bench/bom.yaml` (60 min) and `task.yaml` needs raising; not
observed with a live agent run in this worktree (out of scope for a task-authoring session, per the
brief's Not-in-scope: "running the task in a real harness").

## Offline restore

assume: the grading host has a NuGet global packages cache at `%USERPROFILE%\.nuget\packages` (or
`NUGET_PACKAGES` when set) holding `Microsoft.NET.Test.Sdk`, `xunit`, `xunit.runner.visualstudio`
and their dependencies at the versions `Directory.Packages.props` pins — the same cache D1/D2/D3/F1
use, so the same host cache serves all of them. **Confirm:** both `probe.py` calls restored from
`RestoreSources=.` with no NuGet source configured (observed on this host, `evidence.md`). **Breaks
if false:** on a fresh grading host, restore fails and the grader returns NA
(`infrastructure failure before build: restore`); seeding that cache is a harness setup step, as for
D1/D2/D3/F1.

## macOS (ADR-0013 Amendment 1)

assume: this task runs natively on macOS unchanged, on the same basis D2 records: the workspace is
portable C#/.NET (net10.0, no Windows-only API), and the oracle command here is
`["dotnet", "test", "F2.HiddenTests/F2.HiddenTests.csproj", ...]`, invoked directly with a
forward-slash path and no shell wrapper, which `harness_bench.grade.correctness.grade` passes to
`procs.run` unshelled on both platforms — the exact command D2 already confirmed runs unmodified
from a macOS host once its NuGet cache pins are seeded. **Confirm:** run
`dotnet test tasks/F2/tests/F2.HiddenTests/F2.HiddenTests.csproj -p:RestoreSources=. -p:NuGetAudit=false`
directly on a macOS host with the same cache seeded, from a working copy carrying
`tasks/F2/tests/NuGet.Config` and the pinned workspace's `src/`, and observe the same 0/5 on the
base and 5/5 on the reference. **Breaks if false:** something specific to this task's reflection
harness or the vendored ai-de source is not macOS-portable, distinct from the known
`cmd.exe`-wrapper gap ADR-0013 Amendment 1 already records for D1/D3/E6/F1. Not measured here (no
macOS host in this worktree).

## Later waves

A mutation grader should reuse `mutants.py`'s six mutants as its seed set, as D2's does. The
coordination and judge graders named in `task.yaml` are not built; their expected inputs are the
notes above.
