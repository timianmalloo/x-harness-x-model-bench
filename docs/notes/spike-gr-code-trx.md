---
id: note-20260925-spike-gr-code-trx
title: "Spike GR-CODE c1 - what D1's per-test TRX and the dotnet build summary contain, measured with the pinned SDK"
type: decision-note
status: accepted
owner: "@timianmalloo"
tags: [spike, grading, dotnet, trx, correctness, dr-g4]
links:
  - { to: design-phase3-graders, rel: relates-to }
  - { to: rulings-register, rel: depends-on }
review-by: "2026-12-25"
summary: >-
  Measured on this host with dotnet 10.0.303: D1's hidden-test step writes one TRX whose ResultSummary/Counters and
  per-test UnitTestResult rows are documented here; with -v:q neither dotnet test nor dotnet build prints a build
  summary, only MSBuild canonical error lines (CSxxxx for a compile error, NUxxxx for a restore error) and no TRX.
  A ProjectReference to a missing project is only warning MSB9008 and exits 0, so the design's broken-reference seed
  does not score 0 under its own definition (flagged).
---

# Spike GR-CODE c1: D1's TRX and the dotnet build summary

**Question** (design `phase3-graders.md`, Consumed contracts, Flagged): what do the dotnet build summary and the per-test TRX contain for D1, and which fields can a grader read? The answer decides how DR-G4 (R-67 c1) tells a compile error from a restore failure.

All facts below are **Verified**: observed on 2026-09-25 on the operator's host (Windows 11 Pro 10.0.26200), by W3-GR-CODE (Claude Opus 5.5). The probe script lived in the session scratchpad and is not committed. Paths in the outputs are the scratch copy's; they are shown here as `<copy>`.

## Method

1. A grading copy, built the way `correctness.grade` builds one: `tasks/D1/workspace` copied, then `tasks/D1/tests` overlaid (`D1.HiddenTests/`, `NuGet.Config`).
2. The environment `correctness.grade` passes to a dotnet step: `_env()` plus `DOTNET_HOST_ENV`. `NUGET_PACKAGES` was unset, so the cache is the profile's `.nuget\packages`.
3. Each step ran through `procs.run` (Job Object, deadline 900 s).
4. Commands:
   - `dotnet --version` in the copy: exit 0, `10.0.303` (`global.json` pins `10.0.303`, `rollForward: latestFeature`).
   - The oracle, exactly as `task.yaml` names it: `cmd.exe /c D1.HiddenTests\run.cmd --logger "trx;LogFileName=d1-hidden.trx" --results-directory TestResults -v:q`. `run.cmd` runs `dotnet test D1.HiddenTests\D1.HiddenTests.csproj -p:RestoreSources=. -p:NuGetAudit=false` with those arguments.
   - The workspace build (no hidden tests), once per `*.csproj` in sorted order: `dotnet build <project> -p:RestoreSources=. -p:NuGetAudit=false -v:q -nologo`.

## The hidden-test step

| Tree | Exit | Seconds | TRX | stdout (what the step prints) |
| --- | ---: | ---: | --- | --- |
| Pinned base | 1 | 5.3 | `TestResults/d1-hidden.trx`, 22,124 bytes | `Test run for <copy>\D1.HiddenTests\bin\Debug\net10.0\D1.HiddenTests.dll (.NETCoreApp,Version=v10.0)`, `A total of 1 test files matched the specified pattern.`, `Results File: <copy>\TestResults\d1-hidden.trx`, `Failed!  - Failed: 5, Passed: 0, Skipped: 0, Total: 5, Duration: 23 ms - D1.HiddenTests.dll (net10.0)`. stderr: one `[xUnit.net 00:00:00.11] EvidenceCensusHiddenTests.<test> [FAIL]` line per test. |
| Reference overlay | 0 | 5.2 | the same path, 8,988 bytes | `Passed!  - Failed: 0, Passed: 5, Skipped: 0, Total: 5, …` |
| Base + `Broken.cs` (syntax error) | 1 | 1.3 | **none** | one line: `<copy>\src\AiDe.Core\Projections\Broken.cs(5,31): error CS1002: ; expected [<copy>\src\AiDe.Core\AiDe.Core.csproj]` |
| Reference, `PathComparison.ForThisFileSystem` deleted | 1 | 2.9 | **none** | 9 lines `…: error CS0117: 'PathComparison' does not contain a definition for 'ForThisFileSystem' […]`, all in files the seed did not touch (`SolutionTreeProjection.cs(131,89)`, `FixtureExtractor.cs(115,89)`, `AttachmentPolicy.cs(228,61)`, `KnowledgeExtractor.cs(487,56)`, `ProjectionService.cs(1508,64)`, `RepositoryCorrection.cs(122,65)`, `ProofPackVerifier.cs` ×3) |
| Reference, `NUGET_PACKAGES` = an empty folder | 1 | 0.7 | **none** | 9 lines `<project> : error NU1101: Unable to find package <id>. No packages exist with this id in source(s): C:\Program Files\dotnet\library-packs, workspace-only` (Microsoft.Data.Sqlite, YamlDotNet, Microsoft.CodeAnalysis.CSharp ×2 each; xunit, xunit.runner.visualstudio, Microsoft.NET.Test.Sdk ×1). No `CS` line. |

## The TRX (namespace `http://microsoft.com/schemas/VisualStudio/TeamTest/2010`)

- **Root** `TestRun`, attributes `id`, `name`, `runUser`. Children: `Times`, `TestSettings`, `Results`, `TestDefinitions`, `TestEntries`, `TestLists`, `ResultSummary`.
- **`ResultSummary`** has `outcome` (`Failed` on the base) and one `Counters` child with 16 attributes: `total`, `executed`, `passed`, `failed`, `error`, `timeout`, `aborted`, `inconclusive`, `passedButRunAborted`, `notRunnable`, `notExecuted`, `disconnected`, `warning`, `completed`, `inProgress`, `pending`. Base: `total=5 executed=5 passed=0 failed=5`, the rest `0`.
- **Per test**, `Results/UnitTestResult`, attributes `computerName`, `duration`, `endTime`, `executionId`, `outcome`, `relativeResultsDirectory`, `startTime`, `testId`, `testListId`, `testName`, `testType`. A failed result has children `Output/ErrorInfo/Message` and `StackTrace`. `outcome` is `Failed` or `Passed`. `testName` is `EvidenceCensusHiddenTests.<Method>`: the class name without a namespace (the hidden class is in the global namespace).
- **`TestDefinitions/UnitTest`**, attributes `name`, `storage` (the lower-cased absolute DLL path), `id` (= the result's `testId`). Child `TestMethod`: `codeBase` (absolute DLL path), `adapterTypeName` = `executor://xunit/VsTestRunner3/netcore/`, `className`, `name`.

**Fields the grader reads.**
- c1 reads only `ResultSummary/Counters@total` and `@passed` (`correctness.parse_trx`, unchanged).
- For c2's per-test names (`regression_count` by fully qualified name), the stable key is `TestMethod@className + "." + TestMethod@name`, joined to `UnitTestResult@outcome` through `testId`. `testName` alone carries no namespace. Inferred, not measured here: the public suite (`tests/AiDe.Core.Tests`) writes the same shape; c2 measures it.
- **Never read, copy or report:** `runUser` and `computerName` (the host's user and machine names), `storage`, `codeBase` and the `Results File:` line (absolute host paths), and every time or duration. None of them is deterministic, and the first two identify the operator.

## The build summary

- With `-v:q`, **neither `dotnet test` nor `dotnet build` prints a "Build succeeded" or "Build FAILED" summary**. A failed build prints only MSBuild's canonical error lines, `<origin>: error <code>: <text> [<project>]`, on stdout; stderr is empty.
- A compile error is `: error CSnnnn: `; a restore error is `: error NUnnnn: `. Neither run printed both. `correctness.BUILD_ERROR` matches `": error (NU|CS)\d{4}: "`, and a restore code wins when both appear (restore precedes compilation).
- **The workspace build** (6 projects: `src/AiDe.Core`, `src/AiDe.Daemon`, `src/AiDe.Mcp`, `tests/AiDe.Core.AcpProbe`, `tests/AiDe.Core.TerminalHost`, `tests/AiDe.Core.Tests`): every build exited 0 on the base, 2.1–4.2 s each, 16.3 s in all with `dotnet --version`. The grader's `assume:` (design, Flagged risks) that the offline cache holds every package the build and test steps restore is **confirmed on this host**: `RestoreSources=.` names no network source.
- **A `ProjectReference` to a missing project is not a build failure.** Adding `<ProjectReference Include="../Nowhere/Nowhere.csproj" />` to `tests/AiDe.Core.Tests/AiDe.Core.Tests.csproj` gave `warning MSB9008: The referenced project ../Nowhere/Nowhere.csproj does not exist.` (twice) and **exit 0** for every project.

## Consequences for the design

1. **DR-G4 by cause is decidable from the step's output.** A dotnet step that wrote no TRX is `restore` when a `NU` code appears, `compile` when only a `CS` code appears, and unexplained otherwise (kept as today's NA `named TRX result file missing`). R-67 c1's control then decides a `compile` case against the pre-turn tree.
2. **Flagged: the design's seeded fixture "a broken `ProjectReference` in a D1 test project → `build_and_suite_clean` 0" contradicts the design's own definition** ("`dotnet build` … exits 0"): it measures exit 0, so it scores 1. c1 does not change the definition. Its dotnet `build_and_suite_clean` = 0 seeds are the syntax-error file and the deleted member instead. **Decision request for the Leader:** keep the definition and retire that seed, or make MSB9008 an error (`-warnaserror:MSB9008`) as a new definition under the catalog version.
3. The residual stands as the design accepts it (phase-2 §8, ADR-0010): agent build targets run during grading, so they can print a fake error line or write a fake TRX.

## GR-CODE c2: the public suite (`regression_count`)

Measured on 2026-09-25 on the same host and SDK by W3-GR-CODE c2 (Claude Opus 5.5), on a copy of `tasks/D1/workspace` with no `.git` (as a grading copy has none). All **Verified** unless labelled.

- **The public test project.** Of D1's six projects only `tests/AiDe.Core.Tests` references `Microsoft.NET.Test.Sdk`; `AiDe.Core.AcpProbe` and `AiDe.Core.TerminalHost` set `IsTestProject=false`. A1 and C1 have no `test*.py`, and E6's one project has no test SDK, so the three are NA `task has no public tests`.
- **The command:** `dotnet test tests/AiDe.Core.Tests/AiDe.Core.Tests.csproj -p:RestoreSources=. -p:NuGetAudit=false --logger "trx;LogFileName=public-0.trx" --results-directory TestResults -v:q`. On the base: exit 1, 139 s including the build, a 4.5 MB TRX.
- **The TRX shape matches the hidden suite's.** `TestMethod` carries `className` (with the namespace, e.g. `AiDe.Core.Tests.IpcFramingTests`), `name`, `adapterTypeName` and `codeBase`. The base run has 2,667 `UnitTest` definitions and 2,682 results (2,609 `Passed`, 72 `Failed`, 1 `NotExecuted`), but only **2,241 distinct `className.name` keys**: 122 keys carry several results, the cases of an xUnit theory. So a key passes only when every one of its cases passes.
- **Stable on the base, n = 2.** Two consecutive runs gave the same passing key set. The 72 base failures fail the same way on both trees, so they are never a regression. Their cause is not measured; it is **Inferred** that they need a git repository around them, because the grading copy has no `.git`. Beyond n = 2 the suite's determinism is also **Inferred**.
- **A measured flake.** On `row15-d1-1`, cell `caa8…` (its change adds only the projection and its own test file) first read 1 regression: `UpgradeTests.AJournalBeingRewritten_IsNeverObservedHalfWritten`. That test failed in 1 of 16 full-suite runs this session, and passed 5 of 5 when run alone on both of that cell's trees. So a candidate now counts only if it also fails on a second run of the cell's tree, which costs one suite run and happens only when there is a candidate. A flake that fails twice in a row stays possible. That is a disclosed residual (the `assume:` in `correctness.regression_count`), and a **decision request for the Leader**: keep the confirming run, or quarantine named tests under the catalog version.
- **The seed.** Inverting the one assertion of `IpcFramingTests.Utf8Content_SurvivesIntact` (`Assert.Equal` to `Assert.NotEqual`) gives `regression_count` = 1, the regressed key `AiDe.Core.Tests.IpcFramingTests.Utf8Content_SurvivesIntact` (311 s for the whole cell).
- **Nothing that identifies the host is kept.** The reader takes `UnitTest@id`, `TestMethod@className`, `@name`, `UnitTestResult@testId` and `@outcome` only. The TRX stays inside the disposable tree, and the evidence log holds each command and its exit code, never the step's output (which carries the `Results File:` path).
