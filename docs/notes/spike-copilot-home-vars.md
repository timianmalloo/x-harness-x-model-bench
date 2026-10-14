---
id: "note-spike-copilot-home-vars"
title: "Spike: Copilot with HOME and USERPROFILE at the cell home, and repo hooks in -p and ACP"
type: doc
status: draft
owner: "@timianmalloo"
tags: [benchmark, spike, copilot, isolation, hooks]
links:
  - { to: adr-0013-native-cells, rel: refines }
review-by: "2027-04-14"
summary: >-
  Copilot 1.0.89-1 serving gpt-6.1-sol keeps its login with HOME and USERPROFILE at the cell home. A command naming
  $env:USERPROFILE is still denied unless the cell home is an allowed directory, so the profile also passes
  --add-dir {home}. uv keeps working when APPDATA stays the operator's. Repo hooks (.github/hooks) run under copilot
  --acp but not under copilot -p, in a folder that is not in trustedFolders.
---

# Spike: Copilot with HOME and USERPROFILE at the cell home, and repo hooks in -p and ACP

Date: 2026-10-14 (track instr/w16). Binary: the pinned `copilot.exe` (the session record says `copilotVersion`
1.0.89-1), `--model gpt-6.1-sol --reasoning-effort low`, the profile's tool list, no `XAI_API_KEY`. Each run used an
isolated `COPILOT_HOME` seeded like a cell (only a `.gitconfig`; the login is the Windows credential store). Runs were
under `C:\tf\w16\<name>\{home,ws}`, outside the system temp folder (Copilot allows the temp folder by default, which
hid the effect in the first runs). All figures are Verified from the run's `out.jsonl` and `events.jsonl`.

## Home variables (owner decision 2026-10-14)

| Run | Setup | `Get-ChildItem $env:USERPROFILE` | `~` | `uv run python -c "print(1)"` |
| --- | --- | --- | --- | --- |
| control | HOME and USERPROFILE are the operator's profile | denied ("Permission denied and could not request permission") | not run | not run |
| b1 | HOME = USERPROFILE = COPILOT_HOME = the cell home, no `--add-dir` | denied | allowed | allowed |
| b2 | HOME = USERPROFILE = another folder, no `--add-dir` | denied | allowed | allowed |
| b4 | as b1 plus `--add-dir <cell home>` | **allowed** (prints the cell home) | allowed | allowed |

b4 is the bench's shape and the evidence for the choice. (Two attempts to run b2 with `--add-dir` hit script errors and
did not apply the flag; they are not counted.)

- Login survives and `gpt-6.1-sol` is served (the `session.start` record: `selectedModel` gpt-6.1-sol).
- The cell home alone is not an allowed directory: only the working directory and the system temp folder are. So the
  profile passes `--add-dir {home}` in both launches.
- `~` was never denied; only the `$env:USERPROFILE` form was.
- uv: with `APPDATA` and `LOCALAPPDATA` left alone, `uv run` used its managed CPython 3.14.6 and worked (b1, b4).
  With both moved into the cell home (run c1), `uv python dir` pointed into the empty cell home and uv fell back to the
  operator's system Python 3.12 under `C:\Users\<user>\AppData\Local\Programs\Python`. That works only because such a
  Python exists, and its path is outside the cell. So the profile does not move them. Running the managed Python by
  its full path (`uv python find`, then `& <path> -c ...`) was not denied (run d1).
- Residual (Inferred, not run): a command that lists or reads files under the uv store directory itself
  (`%APPDATA%\uv\python`) would still be outside every allowed directory. It is the 1 of 9 HB-VAL-012 cells W9 saw.
  Confirm with a run that lists that folder; the fix would be an `--add-dir` for it, which is host-specific.

## Repo hooks: do `copilot -p` and `copilot --acp` run `.github/hooks/*.json`?

A scratch git repo with `.github/hooks/h.json` (version 1) wiring `sessionStart`, `userPromptSubmitted`,
`preToolUse`, `postToolUse` and `sessionEnd` to a command that appends the event name to a file outside the
workspace. One prompt, one `Get-Content hello.txt` tool call, cell-like home, folder not in `trustedFolders`.

| Mode | Folder trusted | Lines written |
| --- | --- | --- |
| `copilot -p` | no (cell shape) | **none**, in 3 runs (2 under the temp folder, 1 under `C:\tf`) |
| `copilot -p` | yes (`trustedFolders` = the workspace in the home's `config.json`) | all five events |
| `copilot --acp` | no (cell shape) | **all five events**, in 3 runs |
| `copilot --acp` | yes | all five events |

- Answer: under `-p`, repo hooks do not run in a cell, because the cells do not seed `trustedFolders` (ruling R-14).
  The positive control (trusted folder fires them) shows the hook file was valid.
- Under `--acp` they run without any trust. So the ACP transport control (plan row A3) runs the pack's session-start
  and pre-tool hooks that the `-p` cells never run. That is a confound for any ACP-versus-`-p` comparison on a pack-on
  cell.
- The five-event order observed in the file was userPromptSubmitted, sessionStart, preToolUse, postToolUse,
  sessionEnd.

## Tokens used

19 Copilot sessions that reached a model (summed from the records' `session.shutdown` metrics): 377,116 input
(243,163 cache read, 133,794 cache write), 1,781 output, 21 reasoning tokens. Runs that failed to start used none.
