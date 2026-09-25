# F1 oracle evidence

Measured on 2026-09-25 in the `w2-tasks-f1` worktree (Claude Opus 5.5, W2-TASKS-c).

## Pinned base and vendor selection

- `git -C <cfd-bench clone> rev-parse HEAD` exited 0 with `496a0a8ca2fae9026927167a8f3e5da0a53f2233`. `git status --short` printed nothing, so the clone was clean.
- The workspace was extracted with `git archive --format=tar 496a0a8… -- <vendored_paths>` (the list in `task.yaml`). It has **29 files, 227,614 bytes** in the working tree (CRLF on this host's `core.autocrlf=true`).
- Blob identity: the 29 blob ids under `tasks/F1/workspace/` in commit `0f8cc9f` equal the ids of the same paths in cfd-bench `496a0a8` (`git ls-tree -r`, then `diff`: exit 0, no output). The committed tree is the source's bytes.
- `uv run python tasks/F1/oracle/vendoring_check.py C:/projects/cfd-bench` exited 0 and printed `29 files, 227614 bytes; archive 29 files` and `ok`. It checked byte equality with a fresh `git archive`, the `bench/pack-markers.txt` markers, the forbidden folders (`bin/`, `obj/`, caches, pack folders), secret-shaped suffixes, `harness_bench.config.PROFILE_PATH`, and e-mail addresses.

## Hidden xUnit discrimination through the shared grader

Command: `uv run python tasks/F1/oracle/probe.py` (exit 0). The probe calls `harness_bench.grade.correctness.grade` twice. For the reference call, it copies `workspace/` and overlays `oracle/reference/` (`src/CfdBench.Core/**`). The grader then overlays `tasks/F1/tests/` into its disposable grading copy. The reference never enters the agent's workspace.

Oracle command (`task.yaml`): `cmd.exe /c F1.HiddenTests\run.cmd --logger "trx;LogFileName=f1-hidden.trx" --results-directory TestResults -v:q`. The wrapper runs `dotnet test F1.HiddenTests\F1.HiddenTests.csproj -p:RestoreSources=. -p:NuGetAudit=false`. The grader recorded `dotnet --version` = `10.0.303` on both calls, each exiting 0.

| Grading copy | dotnet exit | Named TRX | xUnit result | `correctness.grade` |
| --- | ---: | --- | --- | --- |
| Pinned base (docs only) | 1 | `TestResults/f1-hidden.trx` | 10 failed, 0 passed, 0 skipped | `passed=0`, `partial_credit=0`, `reason=None` |
| Reference overlay | 0 | `TestResults/f1-hidden.trx` | 0 failed, 10 passed, 0 skipped | `passed=1`, `partial_credit=1`, `reason=None` |

Failing tests on the base, all 10, as runtime xUnit failures (a TRX was written, so this is a 0, not NA):

- `WingSpineHiddenTests.UnitsConvertAndRejectNonFiniteValues`
- `WingSpineHiddenTests.RectangularWingMatchesItsClosedForms`
- `WingSpineHiddenTests.TaperedWingMatchesItsClosedForms`
- `WingSpineHiddenTests.CrankedWingIntegratesEverySegment`
- `WingSpineHiddenTests.SweepAndTwistDoNotChangeThePlanformQuantities`
- `WingSpineHiddenTests.MillimetreStationsGiveTheSameQuantities`
- `WingSpineHiddenTests.WashoutIsRootTwistMinusTipTwist`
- `WingSpineHiddenTests.CreateRejectsAnInvalidStationList`
- `WingSpineHiddenTests.WingKeepsItsOwnCopyOfTheStationsInOrder`
- `WingSpineHiddenTests.EveryDerivationRejectsANullWing`

Not observed: the per-test failure message on the base, because `-v:q` prints names only. By construction it is the `CfdBench.Core` assembly-not-found `XunitException` in `WingSpineHiddenTests.Core()`. That is Inferred, not read from the TRX.

## Negative controls: mutants of the reference

Command: `uv run python tasks/F1/oracle/mutants.py` (exit 0). Each mutant is the reference with one edit, graded like the probe:

| Mutant | `passed` | `partial_credit` | Killed by |
| --- | ---: | ---: | --- |
| `span-half-only` (span = tip position) | 0 | 0.4 | the rectangular, tapered, cranked, sweep, millimetre and defensive-copy tests |
| `mac-is-mgc` (MAC integrand = mean chord) | 0 | 0.5 | the rectangular, tapered, cranked, sweep and millimetre tests |
| `washout-sign` | 0 | 0.9 | `WashoutIsRootTwistMinusTipTwist` |
| `root-and-tip-only` (last segment only) | 0 | 0.9 | `CrankedWingIntegratesEverySegment` |
| `no-defensive-copy` | 0 | 0.9 | `WingKeepsItsOwnCopyOfTheStationsInOrder` |
| `equal-positions-allowed` | 0 | 0.9 | `CreateRejectsAnInvalidStationList` |

## Offline restore

assume: the grading host's NuGet global packages folder (`%USERPROFILE%\.nuget\packages`, or `NUGET_PACKAGES` when set) holds `Microsoft.NET.Test.Sdk` 17.14.1, `xunit` 2.9.3, `xunit.runner.visualstudio` 3.1.4 and their dependencies. These are the same pins D1 uses. **Confirm:** both probe calls restored from `RestoreSources=.` on this host with no NuGet source configured (observed). **Breaks if false:** on a fresh grading host, restore fails and the grader returns NA `infrastructure failure before build: restore`. Seeding that cache is a harness setup step, as for D1. The agent's own `CfdBench.Core` project in the reference has no package references.
