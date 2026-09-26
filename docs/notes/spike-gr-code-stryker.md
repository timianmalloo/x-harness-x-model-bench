---
id: note-spike-gr-code-stryker
title: "Spike GR-CODE c6a - cached Stryker.NET 4.16.0 runs offline on D1; --version does not print the pin"
type: decision-note
status: accepted
owner: "@timianmalloo"
tags: [spike, grading, dotnet, stryker, mutation, r-59]
links:
  - { to: design-phase3-graders, rel: relates-to }
review-by: "2026-10-09"
summary: >-
  dotnet-stryker 4.16.0 is extracted in the offline NuGet cache and is not an installed tool.
  `dotnet exec` of that DLL, with NUGET_PACKAGES pointed at the cache and additional-timeout
  5000, scored D1's reference file twice: killed 12, timeout 0, survived 2, no coverage 0,
  and the two mutation-report.json files were byte-identical. `--version` exits 1.
---

# Spike GR-CODE c6a: does pinned Stryker.NET run offline on D1?

**Question** (design `phase3-graders.md`, Mutation; Catalog-version rule 3, R-59 c4): on this host, is a pinned Stryker.NET available without a network install, and if it is, what does one offline run against D1's reference plus hidden tests report?

No `dotnet tool install` was run. No NuGet package was downloaded. The grading copy lived under `C:\Projects\_spike-stryker-c6a` and is not committed. `grade/mutation.py` was not edited.

## Cache and tool lists

**Verified.** 2026-09-25, Windows host, cwd = this repo unless noted.

| Command | Exit | Observed |
| --- | ---: | --- |
| `dotnet tool list -g` | 0 | Package Ids `dotnet-ef` 10.0.11, `dotnet-stack` 10.0.745401, `ilspycmd` 11.0.0.9375. No `dotnet-stryker`. |
| `dotnet tool list --local` | 0 | Header only. No local tool manifest entries. |
| `Get-Command dotnet-stryker -ErrorAction SilentlyContinue` | 0 | No application. The script printed `NOT_ON_PATH`. `SilentlyContinue` is why the exit is 0. |
| `where.exe dotnet-stryker` | 1 | `INFO: Could not find files for the given pattern(s).` |
| `dotnet nuget locals global-packages -l` | 0 | `global-packages: %USERPROFILE%\.nuget\packages\` |
| `dotnet nuget locals all -l` | 0 | `http-cache: %USERPROFILE%\AppData\Local\NuGet\v3-cache`; `global-packages: %USERPROFILE%\.nuget\packages\`; `temp: %USERPROFILE%\AppData\Local\Temp\NuGetScratch`; `plugins-cache: %USERPROFILE%\AppData\Local\NuGet\plugins-cache`. |
| `Get-ChildItem -Path %USERPROFILE%\.nuget\packages -Directory -Filter *stryker*` | 0 | One directory: `%USERPROFILE%\.nuget\packages\dotnet-stryker`. Its only child version directory is `4.16.0` (same listing, depth 2). |
| `Get-Content %USERPROFILE%\.nuget\packages\dotnet-stryker\4.16.0\dotnet-stryker.nuspec` | 0 | `<id>dotnet-stryker</id>`, `<version>4.16.0</version>`, package type `DotnetTool`. |
| `Get-Content %USERPROFILE%\.nuget\packages\dotnet-stryker\4.16.0\tools\net8.0\any\DotnetToolSettings.xml` | 0 | Command name `dotnet-stryker`, entry point `Stryker.CLI.dll`, runner `dotnet`. |

The package is extracted. `Stryker.CLI.dll` is at `%USERPROFILE%\.nuget\packages\dotnet-stryker\4.16.0\tools\net8.0\any\Stryker.CLI.dll`. **Verified:** `dotnet exec` of that DLL runs this build with no `dotnet tool install` (the `--help` command below, and the scoring runs).

## Version string and the tool_versions probe

Catalog-version rule 3 says `dotnet-stryker` is the pinned tool's `--version`, measured once, 30 s timeout, and an absent tool reads `not recorded` (`runner.tool_versions` / `tools.measured_version`: last stdout line, and only on exit 0).

**Verified.** The design's flag is not the tool version on this build.

| Command | Exit | Observed |
| --- | ---: | --- |
| `dotnet exec %USERPROFILE%\.nuget\packages\dotnet-stryker\4.16.0\tools\net8.0\any\Stryker.CLI.dll --version` | 1 | `Missing value for option 'version'`. No version string. |
| `dotnet exec %USERPROFILE%\.nuget\packages\dotnet-stryker\4.16.0\tools\net8.0\any\Stryker.CLI.dll --help` | 0 | `-v\|--version` is documented as "Project version used in dashboard reporter and baseline feature", default empty. The banner does not contain `4.16.0`. |
| `[System.Diagnostics.FileVersionInfo]::GetVersionInfo('%USERPROFILE%\.nuget\packages\dotnet-stryker\4.16.0\tools\net8.0\any\Stryker.CLI.dll').ProductVersion` | 0 | `4.16.0+f9109e24c615a7030a3b33e5532c665c974e4ec5` |
| `[System.Diagnostics.FileVersionInfo]::GetVersionInfo('%USERPROFILE%\.nuget\packages\dotnet-stryker\4.16.0\tools\net8.0\any\Stryker.CLI.dll').FileVersion` | 0 | `4.16.0.0` |

**Pinned version string:** `4.16.0` (package folder and nuspec). The assembly ProductVersion adds the build commit `f9109e24c615a7030a3b33e5532c665c974e4ec5`, the same commit the nuspec records.

**The command that prints it** (what a `tool_versions` probe can run; `measured_version` keeps the last stdout line only when the exit is 0):

```powershell
powershell -NoProfile -Command "[System.Diagnostics.FileVersionInfo]::GetVersionInfo('%USERPROFILE%\.nuget\packages\dotnet-stryker\4.16.0\tools\net8.0\any\Stryker.CLI.dll').ProductVersion"
```

Exit 0. Last line: `4.16.0+f9109e24c615a7030a3b33e5532c665c974e4ec5`.

**Inferred.** `PINNED_TOOLS["dotnet-stryker"] = ["dotnet-stryker", "--version"]` would measure `not recorded` on this host: the command is not on PATH, and on 4.16.0 `--version` is a dashboard project version that requires a value. The probe above is the one that prints the pin. c6b should record that argv, not `--version`.

## D1 run

The throwaway copy is `C:\Projects\_spike-stryker-c6a\d1`: `tasks/D1/workspace`, then `tasks/D1/tests` overlaid (`D1.HiddenTests/`, `NuGet.Config`), then `tasks/D1/oracle/reference/src/AiDe.Core/Projections/EvidenceCensusProjection.cs` copied onto `src/AiDe.Core/Projections/`. For the two scoring runs the copy's `Directory.Build.props` is the workspace original. A `NuGet.Config` at `C:\Projects\_spike-stryker-c6a` clears package sources (the copy also has the tests' `NuGet.Config`). Process environment: `DOTNET_CLI_TELEMETRY_OPTOUT=1`, `DOTNET_CLI_HOME`, `TEMP`, `TMP`, and `NUGET_HTTP_CACHE_PATH` inside the throwaway, `NUGET_CERT_REVOCATION_MODE=offline`, `MSBUILDDISABLENODEREUSE=1`, `UseSharedCompilation=false`, and `NUGET_PACKAGES=%USERPROFILE%\.nuget\packages`.

`stryker-config.json` in the copy pins the timeout and the run shape:

```json
{
  "stryker-config": {
    "additional-timeout": 5000,
    "concurrency": 4,
    "project": "AiDe.Core.csproj",
    "test-projects": ["D1.HiddenTests/D1.HiddenTests.csproj"],
    "mutate": ["**/EvidenceCensusProjection.cs"],
    "reporters": ["Json", "ClearText"],
    "verbosity": "info",
    "thresholds": { "high": 80, "low": 60, "break": 0 }
  }
}
```

**Verified.** `ilspycmd -t Stryker.Configuration.Options.Inputs.AdditionalTimeoutInput %USERPROFILE%\.nuget\packages\dotnet-stryker\4.16.0\tools\net8.0\any\Stryker.Configuration.dll` exited 0. `AdditionalTimeoutInput.Default` is `5000`. The decompiler also printed its own update notice (`ilspycmd` 11.0.0.9375 vs 11.1.0.9782). That notice is not a Stryker install. `additional-timeout` is the only timeout setting this build exposes; 5000 ms is added to the time of the initial test run. The mutate glob is the reference file only: the design mutates the non-test `.cs` the cell added, and the reference solution adds this one file. The hidden tests call `Compute` by reflection.

The run command, cwd = the copy, is:

```text
dotnet exec %USERPROFILE%\.nuget\packages\dotnet-stryker\4.16.0\tools\net8.0\any\Stryker.CLI.dll --skip-version-check --break-on-initial-test-failure --config-file stryker-config.json
```

This fixture was a new project `D1.HiddenTests` with no vendored test, so it did not cover a red vendored baseline (R-75).

`--skip-version-check` is set so the CLI does not look for a newer Stryker online.

`dotnet --version` with cwd = the copy exited 0 and printed `10.0.303`.

**Verified, first attempt (exit 1).** Same `dotnet exec` command, cwd = the copy, `DOTNET_CLI_HOME` pointed at the throwaway, `NUGET_PACKAGES` unset. Started 2026-09-25T18:12:22Z. Exit 1. Wall time 2.973 s. The banner's first version line is `Version: 4.16.0`. Analysis of `src\AiDe.Core\AiDe.Core.csproj` failed for `net10.0`, and the process printed `Failed to analyze project builds. Stryker cannot continue.` No report file.

**Verified, diagnosis.** The same command plus `--diag` (no `--break-on-initial-test-failure`) exited 1 in 2.988 s. The log records `_OutputPackagesPath=C:\Projects\_spike-stryker-c6a\dotnet-home\.nuget\packages\` and MSBuild `NU1101` (`Unable to find package`) for `Microsoft.Data.Sqlite`, `YamlDotNet`, and `Microsoft.CodeAnalysis.CSharp`. **Inferred:** `DOTNET_CLI_HOME` moved the NuGet global-packages folder off the host cache. The copy's `Directory.Build.props` had also been given `RestoreSources=.`, which this build resolved to `src\AiDe.Core`. Both edits were removed before the runs below: props restored to the workspace original, and `NUGET_PACKAGES=%USERPROFILE%\.nuget\packages` set while `DOTNET_CLI_HOME` stayed inside the throwaway.

**Verified, preflight of that copy.** `dotnet test D1.HiddenTests\D1.HiddenTests.csproj -p:RestoreSources=. -p:NuGetAudit=false -v:q --nologo`, cwd = the copy, with `NUGET_PACKAGES` set as above. Exit 0. Wall time 5.217 s. `Passed! - Failed: 0, Passed: 5, Skipped: 0, Total: 5`.

**Verified, two scoring runs.** Same `dotnet exec` command as above, same config, same `NUGET_PACKAGES`. `--skip-version-check` kept the CLI from looking for a newer Stryker.

| Run | Exit | Wall time | Report |
| --- | ---: | ---: | --- |
| A | 0 | 47.745 s | `StrykerOutput\2026-09-25.11-16-23\reports\mutation-report.json` (170,760 bytes) |
| B | 0 | 44.963 s (started 2026-09-25T18:18:12Z) | `StrykerOutput\2026-09-25.11-18-13\reports\mutation-report.json` (170,760 bytes) |

Both stdout logs contain `Version: 4.16.0`, `Stryker will use a max of 4 parallel testsessions.`, and these lines:

- `20295 mutants created`
- `4388 mutants got status CompileError. Reason: Mutant caused compile errors`
- `1 mutants got status Ignored. Reason: Removed by block already covered filter`
- `15892 mutants got status Ignored. Reason: Removed by mutate filter`
- `14 total mutants will be tested`
- `The final mutation score is 85.71 %`

The mutate glob was applied: 15,892 mutants were ignored because of it. The 14 tested mutants are the reference file.

**The report file.** `mutation-report.json` (the tool's default report name). Top-level keys: `schemaVersion` (`"2"`), `thresholds` (`{"high": 80, "low": 60}`), `projectRoot`, `files`, `testFiles`. There is no top-level killed / timeout / survived / no-coverage object. Each mutant lives at `files.<path>.mutants[]` with `status` (and, when present, `statusReason`, `id`, `mutatorName`, `replacement`, `location`, `static`, `coveredBy`, `killedBy`).

**Verified, reference file** `src\AiDe.Core\Projections\EvidenceCensusProjection.cs`, both runs:

| `status` | Count |
| --- | ---: |
| `Killed` | 12 |
| `Timeout` | 0 |
| `Survived` | 2 |
| `NoCoverage` | 0 |
| `CompileError` | 5 |
| `Ignored` | 1 (`Removed by block already covered filter`) |

`Timeout` and `NoCoverage` do not occur as `status` values in this report. They are status strings this build knows (the cleartext header names timeout and no coverage). **Inferred:** the design's score counts those four statuses and leaves `CompileError` and `Ignored` out. On this file that is `(12 + 0) / (12 + 0 + 2 + 0) = 0.8571428571428571`, which is the logged `85.71 %`.

The cleartext table's wrapped header is score, killed, timeout, survived, no coverage, and a sixth `#` whose glyph in the log is `.`. The reference row reads `85.71`, `12`, `0`, `8`, `0`, `5`. The `5` equals `CompileError`. The `8` equals `Survived + CompileError + Ignored` (`2 + 5 + 1`). **Inferred:** that survived cell is not the JSON `Survived` count. The grader should count `status`.

**Verified, the two runs match.** sha256 of both report files is `a7b83bb186357a988ec4c221eb2ee4cc96d06bf8946e72bd91ea61fdbe899b8d` (python `hashlib.sha256`, exit 0). Per-file status counts are equal. The reference file's `(id, mutatorName, start line, start column, status)` tuples are equal.

Summing every `status` in the JSON gives `Killed` 12, `Survived` 2, `CompileError` 125, `Ignored` 142. That is not the log's project-wide 4,388 compile errors or 15,892 filtered mutants. **Verified:** the report does not list every mutant the log counted. The reference file's 20 mutants are in the report.

## The call

c6b can pin `dotnet-stryker` `4.16.0` and run it offline on this host without an install: `dotnet exec` of `Stryker.CLI.dll` from the global-packages cache, `NUGET_PACKAGES` left at that cache (do not point `DOTNET_CLI_HOME` at an empty folder unless `NUGET_PACKAGES` is set), `--skip-version-check`, and `additional-timeout` `5000` in `stryker-config.json`. The `tool_versions` probe that prints the pin and exits 0 is the `FileVersionInfo` `ProductVersion` command above, not `--version`. The score reads `mutation-report.json` mutant `status` values `Killed`, `Timeout`, `Survived`, and `NoCoverage`. On D1's reference plus hidden tests those counts were 12, 0, 2, and 0, and a second run wrote the same report bytes.
