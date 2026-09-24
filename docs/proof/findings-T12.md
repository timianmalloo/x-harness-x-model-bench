---
id: "findings-t12-mutation-rerun"
title: "Findings → tests: track T12 mutation-rerun"
type: proof-pack
status: accepted
owner: "@timianmalloo"
phase: "Phase 1 · walking skeleton"
tags: [proof, findings, mutation, cosmic-ray, T12, records]
links:
  - { to: coordination-phase1-finish, rel: relates-to }
  - { to: mutation-record-t1, rel: relates-to }
  - { to: mutation-record-t2, rel: relates-to }
review-by: "2026-12-22"
summary: >-
  Every cosmic-ray mutant (2699) re-run with bytecode off. 0 open. The records overstated 29 kills in ledger, views and
  grade (now killed by new tests in a0c4f52) and argued one engine mutant equivalent on a false argument. Stale bytecode
  was not the cause, because cosmic-ray already disables it. The likely causes are cosmic-ray counting any non-zero exit
  or timeout as a kill, and hand-transcribed counts.
---

# T12: mutation-rerun (defect class TOOL-A sweep)

**The Coordinator transcribed this file** from the track's report. **The Coordinator also checked the evidence directly:**
- Commit `a0c4f52` is test-only: 184 lines across `test_ledger`, `test_views`, `test_verify` and `test_grade`.
- The installed `cosmic_ray/testing.py` was read.
  - Lines 52–56 force `PYTHONDONTWRITEBYTECODE=1`.
  - Lines 73–75 return `KILLED` with output `"timeout"` on a timeout, and every non-zero exit is `KILLED`.
- Three "recorded killed, now survived" mutants were re-run with the named-test checker (`tools/mutate_check.py`), against each module's recorded test files:
  - `ledger.py:115:21` `==` → `is`;
  - `ledger.py:225:30` `==` → `is`;
  - `views.py:365:18` `Finding(frozen=True)` → `False`.

  **All three survived at `ceed6c1` and were killed at `a0c4f52`.** So the records overstated these kills, and T12's tests close them.

## Result (bytecode off; `src` at `ceed6c1`, tests at `a0c4f52`)

| module | mutants | killed | equivalent | open |
| --- | --- | --- | --- | --- |
| lifecycle | 107 | 91 | 16 | 0 |
| errors | 13 | 12 | 1 | 0 |
| engine | 767 | 624 | 143 | 0 |
| ledger | 379 | 375 (8 by new tests) | 4 | 0 |
| views | 790 | 630 (20 by new tests) | 160 | 0 |
| grade/** | 643 | 535 (1 by a new test) | 108 | 0 |
| **total** | **2699** | **2267** | **432** | **0** |

- **Shards:** 16, each with its own venv, running each module's recorded command.
- **Bytecode:** no `src/**/__pycache__` existed after any of the 192 phases or the 496 single-mutant jobs. A positive-control run without the variable did write bytecode.
- **Wall time:** phase 1 took about 73 min, and phase 2 about 31 min.
- **One timeout:** views `202:35`, `31e9 ** 1e9`, now killed early by a test ordered first in `test_views.py`.

The detail is in the "Re-run with bytecode off (T12, TOOL-A)" sections of `mutation-record-t1.md` and `mutation-record-t2.md`.

## What the re-run found
1. **29 recorded kills were not kills** (ledger 8, views 20, grade 1). They survived under each record's own command, and are now killed by new tests. Five more "recorded killed" mutants are equivalent (ledger 2, views 1, grade 2). These counts come from the per-module lists and the result table. The track's summary said "28" and "33", which is one fewer than its own lists.
2. **One recorded equivalent is killable:** engine L394 `daemon=True` → `False`. When a cell hangs, a non-daemon stderr drain keeps the process alive, and T10's `test_an_engine_thread_failure_exits_the_process_and_leaves_no_cell_running` kills it. T1's argument did not hold.
3. **The records contain transcription errors:**
   - 8 duplicate equivalent rows with no second job: E2, E5, E7, E9, E14, E18, E20, T11-E3;
   - per-line annotation counts that cannot occur, because each `|` yields 11 jobs.
4. **TOOL-A did not reach cosmic-ray.** cosmic-ray 8.7.0 already disables bytecode for its tests. Only `tools/mutate_check.py` was exposed, and it is fixed.
5. **Likely cause of 1–3 (Flagged, not verified):**
   - cosmic-ray counts any non-zero exit, including an error, and any timeout as KILLED;
   - record counts were derived by hand (total minus the listed survivors).

   The extra test files of T2's survivor re-runs were measured and excluded: 32 of the 33 finished still survive with them.
6. **A false kill in the re-run itself.** Engine L325 (an annotation) was "killed" by `FileExistsError` on a leftover `C:/Projects/bench-test/<hex8>` folder that collided with `conftest.base`'s random name. Run alone, it survived. This is a CLN-A sibling. The unit tests left about 103 more folders there during this run.

## Gates (track-reported; the join's recount re-measures them)
- `pytest -m "not credentials"`: 592 passed, 5 deselected;
- `ruff`: clean.
