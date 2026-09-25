# E6 Oracle

The oracle validates candidate C# implementations for the 10 HumanEval problems using an xUnit test project (`tests/E6.Tests.csproj`) executed via `dotnet test` with a named TRX logger (`trx;LogFileName=e6.trx`).

The execution is wrapped in `run.cmd` to provide standard environment paths (`USERPROFILE`, `APPDATA`, `LOCALAPPDATA`, `ProgramFiles`) to the subprocess under `HOST_ENV` (`correctness.py`), while restoring strictly offline against the local NuGet cache.

## Offline Restore & Local Cache Discipline (ADR-0005)

<!-- assume: local nuget cache -->
assume: Restore works offline without contacting remote package registries by reading cached packages (`xunit 2.9.2`, `xunit.runner.visualstudio 2.8.2`, `Microsoft.NET.Test.Sdk 17.12.0`) from the local NuGet cache at `%USERPROFILE%\.nuget\packages` (on this host: `C:\Users\malla\.nuget\packages`), configured via `tests/NuGet.Config` with `<clear />` and `<add key="local-cache" value="C:\Users\malla\.nuget\packages" />`.
confirm: Running `dotnet restore` with `<clear />` succeeds in ~100 ms with no remote network egress, and `dotnet nuget locals global-packages` confirms the package path.
breaks: If the local cache does not contain `xunit`, `xunit.runner.visualstudio`, or `Microsoft.NET.Test.Sdk`, or if executed in an environment where `C:\Users\malla\.nuget\packages` is not mounted/present, restore fails.

## Reference Solution

The reference implementation is in `oracle/reference/Problem.cs` and implements all 10 problems canonically, passing all 42 tests.

## Verification

Run `uv run python tasks/E6/oracle/grade_e6.py` to evaluate both the base workspace and the reference solution through `harness_bench.grade.correctness.grade`.
Evidence is committed in `tasks/E6/oracle/evidence.md`.
