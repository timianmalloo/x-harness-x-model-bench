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
  Phase 1's mutation evidence in one place. cosmic-ray 8.7.0 ran over lifecycle, errors, 299 of engine's 765 mutants,
  ledger, views and grade/**: no mutant is open. Every hand-written tests/mutations/*.json file was re-run under the
  hardened checker on the integrated code, and every entry was killed. The one gap is engine.py's 466 out-of-scope
  cosmic-ray mutants.
---

# Mutation record: phase 1 (compiled)

The tool is **cosmic-ray 8.7.0**, run natively on Windows. mutmut refuses native Windows (probe R13), so this is a recorded design deviation. The detailed records are:
- `docs/notes/mutation-record-t1.md`: lifecycle, errors, engine;
- `docs/notes/mutation-record-t2.md`: ledger, views, grade.

## cosmic-ray, per module

| module | record | mutants run | killed | equivalent (argued) | open | record current at the close? |
| --- | --- | --- | --- | --- | --- | --- |
| `lifecycle.py` | T1 | 107 | 91 | 16 | 0 | yes: `git diff 67e956b HEAD` is empty |
| `errors.py` | T1 | 13 | 12 (1 after a new test) | 1 | 0 | yes: `git diff 67e956b HEAD` is empty |
| `engine.py` (in scope) | T1 | 299 (247 run and 52 annotations skipped) | 216 (30 after new tests) | 83 (28 argued, 55 annotations) | 0 | yes for the in-scope functions. The diff since `769fb90` is two hunks inside `configure_logging` (T9-2), which is outside the record's scope |
| `engine.py` (out of scope) | T1 | 466 not run | - | - | - | covered only by `tests/mutations/engine.json` (see below) |
| `ledger.py` | T2 | 379 | 376 | 3 | 0 | yes: `git diff 2263575 HEAD` is empty |
| `views.py` | T2 | 781 | 631 | 150 | 0 | yes |
| `grade/**` | T2 | 643 | 539 | 104 | 0 | yes |

"Open" means survived and not argued equivalent, timed out, incompetent, or not exercised on this platform. It is 0 everywhere.

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

## Gap carried to the Proof Pack

`engine.py`'s `run`, `_launch`, `_run_cell`, `_archive`, `_classify`, `configure_logging`, `_job_query` and `_confirm` have no cosmic-ray run: 466 mutants. They are covered by the hand-written `engine.json` and `t9.json` entries and by the unit, conformance and E2E tests. Running them would take about 6.5 h at the measured ~50 s per mutant.

**Re-run trigger:** any change to those functions, or a phase-2 hardening pass.
