---
id: note-spike-gr-code-stryker
title: "Spike GR-CODE c6a - Stryker.NET 4.16.0 is in the offline cache and is not installed as a tool"
type: decision-note
status: accepted
owner: "@timianmalloo"
tags: [spike, grading, dotnet, stryker, mutation, r-59]
links:
  - { to: design-phase3-graders, rel: relates-to }
review-by: "2026-10-09"
summary: >-
  dotnet-stryker 4.16.0 is extracted in the offline NuGet cache and is not an installed tool.
  `--version` does not print it (exit 1); the startup banner and the assembly ProductVersion do.
  The first offline run on D1's reference plus hidden tests exited 1 in 2.973 s: analysis of
  AiDe.Core for net10.0 failed and no mutants were scored.
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
| `dotnet nuget locals global-packages -l` | 0 | `global-packages: C:\Users\malla\.nuget\packages\` |
| `dotnet nuget locals all -l` | 0 | `http-cache: C:\Users\malla\AppData\Local\NuGet\v3-cache`; `global-packages: C:\Users\malla\.nuget\packages\`; `temp: C:\Users\malla\AppData\Local\Temp\NuGetScratch`; `plugins-cache: C:\Users\malla\AppData\Local\NuGet\plugins-cache`. |
| `Get-ChildItem -Path C:\Users\malla\.nuget\packages -Directory -Filter *stryker*` | 0 | One directory: `C:\Users\malla\.nuget\packages\dotnet-stryker`. Its only child version directory is `4.16.0` (same listing, depth 2). |
| `Get-Content C:\Users\malla\.nuget\packages\dotnet-stryker\4.16.0\dotnet-stryker.nuspec` | 0 | `<id>dotnet-stryker</id>`, `<version>4.16.0</version>`, package type `DotnetTool`. |
| `Get-Content C:\Users\malla\.nuget\packages\dotnet-stryker\4.16.0\tools\net8.0\any\DotnetToolSettings.xml` | 0 | Command name `dotnet-stryker`, entry point `Stryker.CLI.dll`, runner `dotnet`. |

The package is extracted. `Stryker.CLI.dll` is at `C:\Users\malla\.nuget\packages\dotnet-stryker\4.16.0\tools\net8.0\any\Stryker.CLI.dll`. **Inferred:** a global or local `dotnet tool install` is not required to execute this build; `dotnet exec` of that DLL is the offline runner (confirmed by the help command below).

## Version string and the tool_versions probe

Catalog-version rule 3 says `dotnet-stryker` is the pinned tool's `--version`, measured once, 30 s timeout, and an absent tool reads `not recorded` (`runner.tool_versions` / `tools.measured_version`: last stdout line, and only on exit 0).

**Verified.** The design's flag is not the tool version on this build.

| Command | Exit | Observed |
| --- | ---: | --- |
| `dotnet exec C:\Users\malla\.nuget\packages\dotnet-stryker\4.16.0\tools\net8.0\any\Stryker.CLI.dll --version` | 1 | `Missing value for option 'version'`. No version string. |
| `dotnet exec C:\Users\malla\.nuget\packages\dotnet-stryker\4.16.0\tools\net8.0\any\Stryker.CLI.dll --help` | 0 | `-v\|--version` is documented as "Project version used in dashboard reporter and baseline feature", default empty. The banner does not contain `4.16.0`. |
| `[System.Diagnostics.FileVersionInfo]::GetVersionInfo('C:\Users\malla\.nuget\packages\dotnet-stryker\4.16.0\tools\net8.0\any\Stryker.CLI.dll').ProductVersion` | 0 | `4.16.0+f9109e24c615a7030a3b33e5532c665c974e4ec5` |
| `[System.Diagnostics.FileVersionInfo]::GetVersionInfo('C:\Users\malla\.nuget\packages\dotnet-stryker\4.16.0\tools\net8.0\any\Stryker.CLI.dll').FileVersion` | 0 | `4.16.0.0` |

**Pinned version string:** `4.16.0` (package folder and nuspec). The assembly ProductVersion adds the build commit `f9109e24c615a7030a3b33e5532c665c974e4ec5`, the same commit the nuspec records.

**The command that prints it** (what a `tool_versions` probe can run; `measured_version` keeps the last stdout line only when the exit is 0):

```powershell
powershell -NoProfile -Command "[System.Diagnostics.FileVersionInfo]::GetVersionInfo('C:\Users\malla\.nuget\packages\dotnet-stryker\4.16.0\tools\net8.0\any\Stryker.CLI.dll').ProductVersion"
```

Exit 0. Last line: `4.16.0+f9109e24c615a7030a3b33e5532c665c974e4ec5`.

**Inferred.** `PINNED_TOOLS["dotnet-stryker"] = ["dotnet-stryker", "--version"]` would measure `not recorded` on this host: the command is not on PATH, and on 4.16.0 `--version` is a dashboard project version that requires a value. The probe above is the one that prints the pin. c6b should record that argv, not `--version`.

## D1 run

The throwaway copy is `C:\Projects\_spike-stryker-c6a\d1`: `tasks/D1/workspace`, then `tasks/D1/tests` overlaid (`D1.HiddenTests/`, `NuGet.Config`), then `tasks/D1/oracle/reference/src/AiDe.Core/Projections/EvidenceCensusProjection.cs` copied onto `src/AiDe.Core/Projections/`. The copy's `Directory.Build.props` sets `RestoreSources=.` and `NuGetAudit=false`. A `NuGet.Config` at `C:\Projects\_spike-stryker-c6a` clears package sources. Process environment for the run: `DOTNET_CLI_TELEMETRY_OPTOUT=1`, `DOTNET_CLI_HOME`, `TEMP`, `TMP`, and `NUGET_HTTP_CACHE_PATH` pointed inside the throwaway, `NUGET_CERT_REVOCATION_MODE=offline`, `MSBUILDDISABLENODEREUSE=1`, `UseSharedCompilation=false`. `NUGET_PACKAGES` was left unset so restore reads the existing global-packages folder.

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

**Verified.** `ilspycmd -t Stryker.Configuration.Options.Inputs.AdditionalTimeoutInput C:\Users\malla\.nuget\packages\dotnet-stryker\4.16.0\tools\net8.0\any\Stryker.Configuration.dll` exited 0. `AdditionalTimeoutInput.Default` is `5000`. The decompiler also printed its own update notice (`ilspycmd` 11.0.0.9375 vs 11.1.0.9782). That notice is not a Stryker install. `additional-timeout` is the only timeout setting this build exposes; 5000 ms is added to the time of the initial test run. The mutate glob is the reference file only: the design mutates the non-test `.cs` the cell added, and the reference solution adds this one file. The hidden tests call `Compute` by reflection.

The run command, cwd = the copy, is:

```text
dotnet exec C:\Users\malla\.nuget\packages\dotnet-stryker\4.16.0\tools\net8.0\any\Stryker.CLI.dll --skip-version-check --break-on-initial-test-failure --config-file stryker-config.json
```

`--skip-version-check` is set so the CLI does not look for a newer Stryker online.

**Verified, run 1.** Same command, cwd = `C:\Projects\_spike-stryker-c6a\d1`. `dotnet --version` in that directory exited 0 and printed `10.0.303`.

| | |
| --- | --- |
| Exit | 1 |
| Wall time | 2.973 s (`00:00:02.6898822` inside the log) |
| Started | 2026-09-25T18:12:22Z |

Stdout begins with the Stryker banner and the line `Version: 4.16.0`, then:

- `Stryker will use a max of 4 parallel testsessions.` (the pinned concurrency)
- `Analyzing 1 test project(s).`
- `Analysis of project src\AiDe.Core\AiDe.Core.csproj failed for frameworks net10.0.`
- `Could not find an assembly reference to a mutable assembly` for `D1.HiddenTests.csproj`. It then looked at the project reference.
- `Project ...\src\AiDe.Core\AiDe.Core.csproj analysis failed hence can't be mutated.`
- The test project "analysis succeeded" and "can be mutated", then `Stryker.NET failed to mutate your project` and `Failed to analyze project builds. Stryker cannot continue.`

No report file was written. Killed, timeout, survived, and no-coverage counts were not produced. A second run is not comparable until a run completes. The log tells us to re-run with `--diag`. That diagnosis, and any completed run, is appended after this commit.
