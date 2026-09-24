---
id: "mutation-record-phase1"
title: "Mutation record: phase 1 (compiled)"
type: decision-note
status: accepted
owner: "@timianmalloo"
phase: "Phase 1 · walking skeleton"
tags: [mutation, cosmic-ray, phase1, proof]
links:
  - { to: mutation-record-t1, rel: relates-to }
  - { to: mutation-record-t2, rel: relates-to }
  - { to: coordination-phase1-finish, rel: relates-to }
review-by: "2026-12-22"
summary: >-
  Phase 1's mutation evidence in one place. Every cosmic-ray mutant of lifecycle, errors, engine, ledger, views and
  grade/** (2699) was run, then re-run with bytecode off (T12): 0 open. The re-run closed 29 kills the records had
  overstated. Every hand-written tests/mutations/*.json entry (198) is killed under the fixed named-test checker.
---

# Mutation record: phase 1 (compiled)

The tool is **cosmic-ray 8.7.0**, run natively on Windows. mutmut refuses native Windows (probe R13), so this is a recorded design deviation. The detailed records are:
- `docs/notes/mutation-record-t1.md`: lifecycle, errors, engine;
- `docs/notes/mutation-record-t2.md`: ledger, views, grade.

## cosmic-ray, per module

These are the final counts from T12's full re-run with bytecode off: `src` at `ceed6c1`, each module's recorded command, survivors re-run one by one at `a0c4f52`. They supersede the per-track counts, which T12 found overstated (below).

| module | mutants | killed | equivalent (argued) | open | first run |
| --- | --- | --- | --- | --- | --- |
| `lifecycle.py` | 107 | 91 | 16 | 0 | T1 |
| `errors.py` | 13 | 12 | 1 | 0 | T1 |
| `engine.py` | 767 | 624 | 143 (99 annotation, 44 argued) | 0 | T1 (301) + T10 (466) |
| `ledger.py` | 379 | 375 | 4 | 0 | T2 |
| `views.py` | 790 | 630 | 160 (143 annotation, 17 argued) | 0 | T2, T11 |
| `grade/**` | 643 | 535 | 108 (99 annotation, 9 argued) | 0 | T2 |
| **total** | **2699** | **2267** | **432** | **0** | |

"Open" means survived and not argued equivalent, timed out, incompetent, or not exercised on this platform. It is 0 everywhere.

**Current while** `git diff ceed6c1 HEAD -- src/harness_bench/{lifecycle,errors,engine,ledger,views}.py src/harness_bench/grade` is empty.

**What the re-run corrected (classes TOOL-A, TOOL-B):**
- **29 mutants recorded killed were not killed** (ledger 8, views 20, grade 1). New test-only commit `a0c4f52` kills them. Five more are equivalent. The Coordinator re-verified three with the named-test checker: each survived at `ceed6c1` and was killed at `a0c4f52`.
- **Engine L394's equivalence argument was wrong.** The mutant is killed.
- **Transcription errors:** duplicate equivalent rows and impossible annotation counts, corrected in `mutation-record-t2.md`.
- **The cause was not stale bytecode**, because cosmic-ray already disables it. The likely causes: cosmic-ray counts any non-zero exit or timeout as KILLED, and some counts were derived by hand.
- **Caution:** each "killed" count is cosmic-ray's verdict, meaning a non-zero exit. Every disagreement with the records was dispositioned one mutant at a time, but the 2267 kills were not each re-checked for a named test failing. A named-test re-derivation from `cosmic-ray dump` is the TOOL-B control, and it is not built yet.

## Hand-written mutation files, re-run at the close

Each entry is a named mutation with the tests that must kill it. The hardened `tools/mutate_check.py`:
- counts a kill only when pytest exits 1 with a named test failing (`ae6e8f0`);
- restores every file byte for byte;
- since `6d26c76`, writes no bytecode from a mutant (TOOL-A).

The first close re-run (`d13b222`, 188/188) was made with the pre-TOOL-A checker, so it could have been affected by stale bytecode. It is **superseded** by this re-run with the fixed checker, at `ceed6c1` on 2026-09-24, one file at a time. After the run, `git status -- src` was clean.

| file | entries | result |
| --- | --- | --- |
| `architecture.json` | 5 | every mutation killed |
| `archive.json` | 6 | every mutation killed |
| `cli.json` | 11 | every mutation killed |
| `engine.json` | 49 (T10 added 5) | every mutation killed |
| `grade.json` | 17 | every mutation killed |
| `ledger.json` | 20 | every mutation killed |
| `report.json` | 22 | every mutation killed |
| `status.json` | 12 | every mutation killed |
| `t3.json` | 15 | every mutation killed |
| `t8.json` | 2 | every mutation killed |
| `t9.json` | 3 | every mutation killed |
| `views.json` | 34 (T11 added 5) | every mutation killed |
| `workspace.json` | 2 | every mutation killed |
| **total** | **198** | **198 killed; each checker run exited 0** |

## Gaps

- **The engine gap is closed.** T10 ran the 466 out-of-scope mutants, and T12 re-ran all 767.
- **Remaining:** the kill counts are cosmic-ray's non-zero-exit verdicts, not each re-checked for a named test (TOOL-B, above).
