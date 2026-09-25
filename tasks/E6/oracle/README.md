# E6 Oracle

The oracle validates candidate C# implementations for the 10 HumanEval problems using an xUnit test project (`tests/E6.Tests.csproj`) executed via `dotnet test` with a named TRX logger (`trx;LogFileName=e6.trx`).

The execution is wrapped in `run.cmd` to keep restore offline. The shared grader passes the host profile and NuGet cache environment to dotnet steps.

## Offline Restore & Local Cache Discipline (ADR-0005)

<!-- assume: local nuget cache -->
assume: Restore works offline without contacting remote package registries by reading cached packages (`xunit 2.9.2`, `xunit.runner.visualstudio 2.8.2`, `Microsoft.NET.Test.Sdk 17.12.0`) from the host NuGet global packages cache at `%USERPROFILE%\.nuget\packages` (or `NUGET_PACKAGES` when set). `tests/NuGet.Config` limits sources to the grading copy; `run.cmd` passes `RestoreSources=.` and disables NuGet audit.
confirm: Running `dotnet restore` with `<clear />` succeeds in ~100 ms with no remote network egress, and `dotnet nuget locals global-packages` confirms the package path.
breaks: If the host cache does not contain `xunit`, `xunit.runner.visualstudio`, or `Microsoft.NET.Test.Sdk`, restore fails.

## Reference Solution

The reference implementation is in `oracle/reference/Problem.cs` and implements all 10 problems canonically, passing all 42 tests.

## Verification

Run `uv run python tasks/E6/oracle/grade_e6.py` to evaluate both the base workspace and the reference solution through `harness_bench.grade.correctness.grade`.
Evidence is committed in `tasks/E6/oracle/evidence.md`.
