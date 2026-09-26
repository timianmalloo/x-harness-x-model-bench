---
id: note-d1-vendored-red-baseline
title: "D1 vendored red baseline - dotnet test fails the same 72 layout-bound tests on both runs' cells; the 69/74/75 Stryker counts are the Stryker session's"
type: decision-note
status: accepted
owner: "@timianmalloo"
tags: [grading, dotnet, stryker, mutation, r-75, r-77]
links:
  - { to: design-phase3-graders, rel: relates-to }
  - { to: note-spike-gr-code-stryker, rel: relates-to }
review-by: "2026-10-10"
summary: >-
  R-77 condition 4. The vendored AiDe.Core.Tests suite, run with dotnet test in grading-copy-shaped copies of one
  row15-d1-1 cell and one smoke-1 cell, twice each, fails the same 72 tests in all four runs, every one of them a
  missing-repository-layout failure. The cells add no red test. The run-to-run difference in Stryker's
  initial_failing_tests (69, 74, 75) is not reproduced by dotnet test, so it belongs to Stryker's own test session.
---

# D1 vendored red baseline (R-77 condition 4)

**Result (Verified, 2026-09-26):** `dotnet test` fails the **same 72 of 2696** vendored `AiDe.Core.Tests` tests in all four runs: two cells, each run twice. **No name differs** between runs or cells. Every one of the 72 is a repository-layout failure. The difference in Stryker's count between runs (69 in `smoke-1`, 74 in `row15-d1-1`, 75 once) is **not** reproduced here.

## What was run

The Grok worker (`grok-4.7`, slice `w3-trx`) ran the measurement. It stopped at its 1200 s deadline before writing this note. The Leader read the four TRX files it left and wrote the note.

- Cells:
  - `runs/row15-d1-1` cell `c3d40fa1377ba0dc` (`D1.cc-opus.pack-off.r1`, attempt 1).
  - `runs/smoke-1`'s `D1.cc-opus.pack-off.r1`.
  - The archive digests differ (`3ef0312e…`, `dadfe3d6…`), so these are two archives.
- Copy: each cell's `ws/`, copied to `%TEMP%\d1-vendored-red\<run>-r<n>`. `.git`, `bin`, `obj` and `TestResults` were excluded, which is the grading-copy shape (`_changes.BUILD_OUTPUT`). Nothing was written under `runs/`.
- Command, cwd = the copy, with `NUGET_PACKAGES=%USERPROFILE%\.nuget\packages`:
  `dotnet test tests/AiDe.Core.Tests/AiDe.Core.Tests.csproj --logger "trx;LogFileName=<run>-r<n>.trx" -v:q`
- The four runs went one after another, 14:03 to 14:13 PDT. Nothing else ran a test suite in that window. The runs match R-77 condition 4's idle case. The under-load case was not run, and its cap was used by this pair.

| Run | Failed / total | Wall |
| --- | ---: | ---: |
| row15-d1-1, r1 | 72 / 2696 | 133 s |
| row15-d1-1, r2 | 72 / 2696 | 141 s |
| smoke-1, r1 | 72 / 2696 | 130 s |
| smoke-1, r2 | 72 / 2696 | 131 s |

## The 72, by first message line

| Count | First line of the failure |
| ---: | --- |
| 37 | `Assert.NotNull() Failure: Value is null` (the `AiDe.sln` walk-up, `RepoFiles.Root()` and siblings) |
| 23 | `InvalidOperationException: could not locate spikes/acp-subscription-lane/frames from <copy>\tests\AiDe.Core.Tests\bin\Debug\net10.0\` |
| 5 | `could not locate the repository root from <copy>\tests\AiDe.Core.Tests\bin\Debug\net10.0\` |
| 4 | `TypeInitializationException: The type initializer for 'AiDe.Core.Tests.SiteRuleFixtureTests' threw an exception.` |
| 3 | `InvalidOperationException: could not locate the repository root from the test output directory` |

Each one reads a file the D1 task does not vendor (`tasks/D1/task.yaml` `vendored_paths`: no `AiDe.sln`, no `docs/`, no `spikes/`).

## What this settles and what it does not

- **R-77 item 3's `assume:` holds for these two cells (Verified).** Neither cell added a red test: both sit on the same floor of 72.
- **The floor is layout-bound and deterministic under `dotnet test` (Verified, 4 of 4 runs).** Environment tests such as `AgentLaunchSurvivesIntegrationTests` pass here.
  - They did fail in the Leader's Stryker break-run log on 2026-09-25.
- **The Stryker counts move and the `dotnet test` count does not (Verified).** 72 here, against 69 / 74 / 75 from Stryker's initial test run. So the difference comes from Stryker's own test session. **Inferred cause:** Stryker runs the suite in 4 parallel test sessions (`concurrency: 4`). Tests that share process or temp state, such as the `%TEMP%\aide-providers\*` folders the suite creates, can pass or fail by interleaving and timing. This is not measured. Measuring it would need Stryker's initial run with the names captured; that is the flag R-75 removed, or a `--diag` log.
- **Consequence for the report:** R-77's per-run derivation is the right shape. The baseline belongs to the Stryker session of a run, not to the task. A cell's count is read against its own run's minimum.
- **Not done:** the under-load pair, and a Stryker-session name capture. Both are follow-ups only if a graded cell's count exceeds its run's minimum + 1 (R-75 item 6's upgrade trigger).
