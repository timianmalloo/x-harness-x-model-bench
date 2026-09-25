# D1 oracle evidence

## Pinned base and vendor selection

`git -C C:/projects/ai-de rev-parse 88e0c33f` exited 0 and returned `88e0c33f0b7c419b1e64d87686987374285292d8`. The source working tree was dirty, so all 531 workspace files came from `git archive` of that commit, using the include and exclude pathspecs in `task.yaml`. The two exclusions are `DreamCorpusReader.cs` and its matching existing test: the source comments contain the `AI-Forward Pack` marker and fail R-42's scan. `LICENSE` at the pinned commit is MIT with `Copyright (c) 2026 timianmalloo` and is present at the workspace root.

The workspace has **531 files, 5,272,935 bytes**. `uv run pytest -q -p no:cacheprovider tests/test_task_vendoring.py` exited 0: 2 passed. That test rebuilt the selected tree through `git archive` and compared every file byte for byte, and scanned every file for `bench/pack-markers.txt` tokens and prohibited generated or pack paths. A separate `rg -n -F -f bench/pack-markers.txt tasks/D1/workspace` returned no matches (rg exit 1). A scratch copy of the workspace built the existing `tests/AiDe.Core.Tests/AiDe.Core.Tests.csproj` with `dotnet build ... -p:RestoreSources=. -v:q`: exit 0, 0 warnings, 0 errors. From that scratch copy, `dotnet test tests/AiDe.Core.Tests/AiDe.Core.Tests.csproj --no-restore --filter FullyQualifiedName~EntryPointsProjectionTests -v:q` exited 0: 7 passed.

## Hidden xUnit discrimination through the shared grader

Command: `uv run python tasks/D1/oracle/probe.py` (exit 0, rerun for W2-TASKS-b slice 3). The probe calls `harness_bench.grade.correctness.grade` twice. For the reference call, it copies `workspace/` and overlays only `oracle/reference/src/AiDe.Core/Projections/EvidenceCensusProjection.cs`. The shared grader then overlays `tasks/D1/tests/` into its disposable grading copy. The reference never enters the agent workspace.

The `task.yaml` oracle command is `cmd.exe /c D1.HiddenTests\run.cmd --logger "trx;LogFileName=d1-hidden.trx" --results-directory TestResults -v:q`. The wrapper invokes `dotnet test D1.HiddenTests\D1.HiddenTests.csproj -p:RestoreSources=. -p:NuGetAudit=false` with the same logger arguments. `NuGet.Config` clears package sources and names only the grading copy. The shared grader passes the host profile and NuGet cache environment to dotnet steps. The grader recorded `dotnet --version` as `10.0.303` on both calls.

| Grading copy | dotnet exit | Named TRX | xUnit result | `correctness.grade` result |
| --- | ---: | --- | --- | --- |
| Pinned base | 1 | `TestResults/d1-hidden.trx` | 5 failed, 0 passed, 0 skipped | `passed=0`, `partial_credit=0`, `reason=None` |
| Reference overlay | 0 | `TestResults/d1-hidden.trx` | 0 failed, 5 passed, 0 skipped | `passed=1`, `partial_credit=1`, `reason=None` |

Failing test names on the base:

- `CountsEveryInputWithoutCollapsingOriginOrVerificationStatus`
- `RejectsNullInputs`
- `EmptySnapshotStillCarriesItsRevision`
- `SortsByCountThenOrdinalPredicateThenEnumValues`
- `CapsBucketsButKeepsFullTotalsAndDisclosesOmissions`

The base failures are runtime xUnit failures: the hidden test project compiles without the new projection, then reflection reports its absence. The named TRX is parsed by `correctness.grade`; a build failure before TRX would be NA and would not satisfy this evidence.

assume: the grading host has the dependencies in its NuGet global packages cache at `%USERPROFILE%\.nuget\packages` (or `NUGET_PACKAGES` when set). Confirm with the same probe on the actual grading host while registry access is disabled. If false, restore fails and the grader returns NA. No package registry is configured in the grading copy.
