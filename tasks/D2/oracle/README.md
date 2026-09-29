# D2 oracle

D2 is the scenario-4 task: a new pure import-origin classification rule in `AiDe.Core`'s
`Extraction/`, against the existing architecture, within a 45-minute budget. Nothing in this
folder except `workspace/` reaches the agent.

## Source and licence

`source.commit` is `88e0c33f0b7c419b1e64d87686987374285292d8` — the same ai-de commit D1
(the worked pattern, same repo) vendors. At that commit `src/AiDe.Core/Extraction/` already holds
24 files (verified with `git ls-tree -r --name-only 88e0c33f -- src/AiDe.Core/Extraction/`), so no
newer commit is required. `workspace/` is `diff -rq`-identical to D1's workspace: same
`vendored_paths`, same `excluded_paths` (`src/AiDe.Core/Watcher/DreamCorpusReader.cs` and its test
carry the AI-Forward Pack marker and fail R-42's scan, as in D1), same 531 files, same MIT licence
and `Copyright (c) 2026 timianmalloo`.

## Correctness: the hidden tests

`tests/D2.HiddenTests/` holds 20 xUnit facts/theory-cases (9 named tests, 4 of them `[Theory]`)
over the contract in `prompt.md`. The base workspace has no `ImportOriginRule` or `ImportOrigin`
type, so the hidden test project uses reflection (`Type.GetType`, `MethodInfo.Invoke`) exactly as
D1's does: it compiles unconditionally against the base, and each test fails at runtime by
asserting a non-null reflected type/member. Reflection also means the test project never needs a
compile-time reference to the new `ImportOrigin` enum itself — a test compares the boxed result's
`.ToString()` (its member name) against the expected string, so the base still **builds** even
though the enum does not exist there yet. A build failure before a named TRX is NA under DR-G4, not
a 0; this task's base is a runtime failure, which is a 0.

The rule reuses the existing `PythonStandardLibrary.Contains` and `NodeBuiltinModules.Contains`
lookups (unchanged, already in `workspace/src/AiDe.Core/Extraction/`) rather than a fresh builtin
list, and takes workspace-module membership as an caller-supplied exact-text set — the tests cover
each of the four classification branches, their stated precedence order (builtin beats workspace
membership; relative-path shape beats both), the "no cross-format normalization" rule, and all four
argument-validation cases (null `language`/`specifier`/`workspaceModuleIds`, an unknown `language`,
an empty `specifier`).

The reference in `oracle/reference/src/AiDe.Core/Extraction/ImportOriginRule.cs` (one new file, 51
lines) passes all 20. Six named mutants of it (`mutants.py`, `evidence.md`) are each killed by a
disjoint set of the hidden tests: the python and node relative-path checks dropped separately, the
builtin/workspace precedence swapped, the unknown-language guard removed, the empty-specifier guard
removed, and the final `External`/`Workspace` branches swapped.

## What is not built in this slice

Later waves: mutation grading (the shared grader, not this task's own `mutants.py`, which is only
the discrimination proof) should reuse the six mutants above as a seed set; the rigor and
architecture graders are not built. The architecture grader would additionally confirm the rule
stays pure (no file I/O, no reference to an extractor or the store) — asserted here by review, not
measured, since the shared architecture grader does not run in this slice.

## Offline restore

assume: the grading host's NuGet global packages folder (`%USERPROFILE%\.nuget\packages`, or
`NUGET_PACKAGES` when set) holds `Microsoft.NET.Test.Sdk`, `xunit`, `xunit.runner.visualstudio` and
their dependencies at the versions `Directory.Packages.props` pins — the same cache D1/D3/F1 use, so
the same host cache serves all four tasks. **Confirm:** both probe calls (`probe.py`) restored from
`RestoreSources=.` with no NuGet source configured (observed on this host, `evidence.md`). **Breaks
if false:** on a fresh grading host, restore fails and the grader returns NA
(`infrastructure failure before build: restore`); seeding that cache is a harness setup step, as
for D1/D3/F1.

## macOS (ADR-0013 Amendment 1)

assume: this task runs natively on macOS unchanged. The workspace is portable C#/.NET (net10.0, no
Windows-only API), and — unlike D1/D3/F1's `cmd.exe /c ...\run.cmd` — the oracle command here is
`["dotnet", "test", "D2.HiddenTests/D2.HiddenTests.csproj", ...]`, invoked directly with a
forward-slash path and no shell wrapper, which `harness_bench.grade.correctness.grade` passes to
`procs.run` unshelled on both platforms. **Confirm:** run
`dotnet test tasks/D2/tests/D2.HiddenTests/D2.HiddenTests.csproj -p:RestoreSources=. -p:NuGetAudit=false`
directly on a macOS host with the same NuGet cache pins seeded, from a working copy that also
carries `tasks/D2/tests/NuGet.Config` and the pinned workspace's `src/`, and observe the same 0/20
on the base and 20/20 on the reference. **Breaks if false:** something in the reflection-based test
project or the vendored ai-de source itself is not macOS-portable, which would be a defect specific
to this task rather than the known engine-wide gap ADR-0013 Amendment 1 records for D1/D3/E6/F1's
`cmd.exe` shape. Not measured here (no macOS host in this worktree).
