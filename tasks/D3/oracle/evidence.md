# D3 oracle evidence

Measured on 2026-09-29 in the `x-harness-x-model-bench-w5-d3` worktree (Claude Sonnet 5,
worker-sonnet-d3), host `dotnet --version` = `10.0.303`.

## Hidden xUnit discrimination through the shared grader

Command: `uv run python tasks/D3/oracle/probe.py` (exit 0). The probe calls
`harness_bench.grade.correctness.grade` twice. For the reference call, it copies `workspace/` and
overlays `oracle/reference/` (`src/CfdBench.Core/Domain/Wing.cs` and
`src/CfdBench.Core/Derivations/WingDerivations.cs` only — `Units/Quantities.cs` and
`Domain/Station.cs` are given, unchanged, in `workspace/`). The grader then overlays
`tasks/D3/tests/` into its disposable grading copy. The reference never enters the agent's
workspace.

Oracle command (`task.yaml`): `cmd.exe /c D3.HiddenTests\run.cmd --logger
"trx;LogFileName=d3-hidden.trx" --results-directory TestResults -v:q`. The wrapper runs
`dotnet test D3.HiddenTests\D3.HiddenTests.csproj -p:RestoreSources=. -p:NuGetAudit=false`. Both
grading calls exited 0 for `dotnet --version` (`10.0.303`).

| Grading copy | dotnet test exit | Named TRX | xUnit result | `correctness.grade` |
| --- | ---: | --- | --- | --- |
| Pinned base (stubs) | 1 | `TestResults/d3-hidden.trx` | 6 failed, 0 passed, 0 skipped | `passed=0`, `partial_credit=0`, `reason=None` |
| Reference overlay | 0 | `TestResults/d3-hidden.trx` | 0 failed, 6 passed, 0 skipped | `passed=1`, `partial_credit=1`, `reason=None` |

Failing tests on the base, all 6, as runtime xUnit failures (a TRX was written, so this is a 0, not
NA — every stub throws `NotImplementedException` when the test calls it):

- `WingSpineHiddenTests.RectangularWingMatchesItsClosedForms`
- `WingSpineHiddenTests.TaperedWingMatchesItsClosedForms`
- `WingSpineHiddenTests.CrankedWingIntegratesEverySegment`
- `WingSpineHiddenTests.CreateRejectsAnInvalidStationList`
- `WingSpineHiddenTests.WingKeepsItsOwnCopyOfTheStationsInOrder`
- `WingSpineHiddenTests.EveryDerivationRejectsANullWing`

A full `uv run python tasks/D3/oracle/probe.py` round trip (restore already warm, build both
grading copies, run both test suites, base and reference) took **7.8 s wall clock**
(`time (...)`, `real 0m7.808s`) — measured, not modeled. This is the oracle's own run time, not an
agent's authoring time; it evidences that grading itself has no material effect on the 40-minute
cell budget.

## Negative controls: mutants of the reference

Command: `uv run python tasks/D3/oracle/mutants.py` (exit 0). Each mutant is the reference with one
edit, graded like the probe:

| Mutant | `passed` | `partial_credit` | Killed by |
| --- | ---: | ---: | --- |
| `span-half-only` (span = tip position, no doubling) | 0 | 1/3 | rectangular, tapered, cranked, defensive-copy tests |
| `area-max-not-mean` (segment area uses max chord, not mean) | 0 | 2/3 | tapered, cranked tests (constant-chord rectangular does not discriminate this one alone) |
| `aspect-ratio-not-squared` (AR = b / S) | 0 | 5/6 | tapered test (b=1 on rectangular and cranked makes b = b², so those do not discriminate this mutant alone) |
| `mean-chord-inverted` (MGC = b / S) | 0 | 1/2 | rectangular, tapered, cranked tests |
| `no-defensive-copy` (Wing keeps the caller's list) | 0 | 5/6 | `WingKeepsItsOwnCopyOfTheStationsInOrder` |
| `equal-positions-allowed` (`>=` instead of `>`) | 0 | 5/6 | `CreateRejectsAnInvalidStationList` |

Every mutant is killed by at least one hidden test (`passed=0` in every row), and each of the six
hidden tests is the sole or joint killer of at least one mutant, so no test is redundant with the
mutation suite it is meant to guard.

## Reference solution's size and time against the 40-minute budget

The reference implementation is 2 files, ~60 lines total (`Domain/Wing.cs` 39 lines,
`Derivations/WingDerivations.cs` 40 lines with comments) reusing formulas F1 already verified
against Python `fractions` for the same P0 wing spine domain. assume: an agent following
`docs/architecture-note.md` completes this within the 40-minute budget with wide headroom, on the
basis that D1's comparable single-file, single-aggregate scenario-4 slice (a projection with a
similar invariant/producer shape) fits a 45-minute budget, and D3 is smaller (no store, no IPC, two
files instead of one plus focused tests already supplied as hidden, not authored by the agent).
**Confirm:** the first real cell's `duration_seconds` (report row 20) against this task once run in
a harness. **Breaks if false:** the budget in `bench/bom.yaml` (40 min) and `task.yaml` needs
raising; not observed with a live agent run in this worktree (out of scope for a task-authoring
session, per the brief's Not-in-scope: "running the task in a real harness").

## Offline restore

assume: the grading host's NuGet global packages folder (`%USERPROFILE%\.nuget\packages`, or
`NUGET_PACKAGES` when set) holds `Microsoft.NET.Test.Sdk` 17.14.1, `xunit` 2.9.3,
`xunit.runner.visualstudio` 3.1.4 and their dependencies — the same pins D1 and F1 use. **Confirm:**
both probe calls above restored from `RestoreSources=.` on this host with no NuGet source
configured (observed: `ls "$USERPROFILE/.nuget/packages"` shows `microsoft.net.test.sdk`, `xunit`,
`xunit.runner.visualstudio` already present, and both grading `dotnet test` calls exited without a
restore error). **Breaks if false:** on a fresh grading host, restore fails and the grader returns
NA `infrastructure failure before build: restore`; seeding that cache is a harness setup step, as
for D1/F1.
