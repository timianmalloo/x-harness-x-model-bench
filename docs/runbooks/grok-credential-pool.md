---
id: runbook-grok-credential-pool
title: "Runbook: add Grok bench credential homes (the credential pool)"
type: doc
status: draft
owner: "@timianmalloo"
tags: [runbook, grok, credentials, parallelism, lean-benchmark]
links:
  - { to: adr-0025-transport-seam-grok-and-agy-cells, rel: depends-on }
review-by: "2027-04-13"
summary: >-
  Each Grok bench credential home lets one more Grok cell run at once. The operator logs in once into each new home,
  checks every home still authenticates, lists all of them in HB_GROK_CRED_HOME (separated by ';' on Windows), and
  sets harness_parallelism {grok: N} with N no more than the number of homes.
---

# Add Grok bench credential homes

Each Grok cell seeds from a bench credential home and writes its refreshed token back to the same home, under a lock
(ADR-0025 s7, Amendment 2026-10-13). One home allows one Grok cell at a time. N homes allow N.

The commands below were checked against the pinned Grok 1.0.41 on 2026-10-13. `grok login` is the sign-in command
(`grok login --help`). `GROK_HOME` moves Grok's home: Grok's own docs call it "Override config directory (default:
`~/.grok`)", and `grok du` run with `GROK_HOME` set wrote into that folder. A login under `GROK_HOME` writes
`$GROK_HOME\auth.json`; the existing bench home has that layout.

## Steps (PowerShell 7, from the repo root)

1. Install the pinned builds once: `uv run bench tools install`. The Grok exe is then
   `.tools\harness\node_modules\.grok-home\bin\grok.exe`.
2. Create the new home outside `~\.grok`. Turn self-update off **before** the login (an unpinned home updated itself
   within a minute):

   ```powershell
   $g = "$PWD\.tools\harness\node_modules\.grok-home\bin\grok.exe"
   $h = "$env:USERPROFILE\.harness-bench\grok-cred-2"
   New-Item -ItemType Directory -Force $h | Out-Null
   Set-Content -Path "$h\config.toml" -Value "[cli]`nauto_update = false" -Encoding utf8
   ```

3. Log in into that home only, then clear the variable:

   ```powershell
   $env:GROK_HOME = $h; & $g login; Remove-Item Env:GROK_HOME
   ```

   `grok login` opens the browser. Use `--device-auth` on a machine without one.
4. Check **every** home, plus the real one. Each check must exit 0. A later login might sign out an earlier home
   (Inferred, not yet observed), so run this after the last login:

   ```powershell
   foreach ($d in "$env:USERPROFILE\.harness-bench\grok-cred", $h) { $env:GROK_HOME = $d; & $g models; "$d exit $LASTEXITCODE" }
   Remove-Item Env:GROK_HOME; & $g models; "real home exit $LASTEXITCODE"
   ```

5. List every home in the variable, separated by `;`. The first home is the one the refresh gate reads:

   ```powershell
   $env:HB_GROK_CRED_HOME = "$env:USERPROFILE\.harness-bench\grok-cred;$env:USERPROFILE\.harness-bench\grok-cred-2"
   ```

6. In the matrix, set `harness_parallelism: {grok: N}`, where N is at most the number of homes. If N is higher,
   `bench plan` refuses with HB-PRE-011 and names the count.

## Rules

- **Never copy `auth.json` from one home to another, or from `~\.grok`.** A copy shares one token family. The first
  refresh in one home strands the other (CRED-COPY-A). Every home needs its own `grok login`.
- One home is the old behaviour exactly: a cap of 1, one cell at a time.
- If a home fails authentication, a cell ends as infrastructure and Grok launches pause (HB-CELL-202). Log in into
  that home again (step 3), then re-run step 4.
- **Resume is open (ADR-0025 s7 Amendment, Open).** A resumed leftover copy does not record which home it came from.
  Before resuming a run with live Grok cells, run step 4 on every home.
