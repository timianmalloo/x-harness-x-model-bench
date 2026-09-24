---
id: "note-20260923-a6-start-benchmark"
title: "A6 golden cases: the start-benchmark skill, old against new"
type: decision-note
status: accepted
owner: "@timianmalloo"
phase: "Phase 1 · walking skeleton"
tags: [decision-note, skills, a6, evaluation]
links:
  - { to: design-phase1-walking-skeleton, rel: relates-to }
review-by: "2027-03-22"
summary: >-
  The design gates the start-benchmark skill edit with golden cases run on the old and the new skill (test plan T14, A6).
  Five cases, run with the same model (sonnet) as a dry run: the new skill passes all five; the old passes one. The
  compiled matrices are checked by tools/a6_check_matrix.py against the real validator.
---

# A6 golden cases: `skills/start-benchmark/SKILL.md`, old against new

- **Kind:** evaluation record (design test plan T14, directive A6). `test_skills_in_sync` does not satisfy this row.
- **Method:** each case ran as a dry run. A sub-agent (model: sonnet) read only the skill file and the case input and answered as the skill's executor; it ran no command and read no other file. The same prompt was used for the old skill (commit `042b0bf`) and the new one. The compiled matrices (C1, C1b) are scored mechanically by `tools/a6_check_matrix.py`, using `config.validate_matrix` and `plan.expand`. C2 to C4 are scored against the pass criteria below.
- **Confidence:** Verified for these five cases and this model. It is one sample per case, so non-determinism is not measured (residual risk).

## Cases and results

| Case | Input | Pass criteria | Old skill | New skill | Delta |
| --- | --- | --- | --- | --- | --- |
| C1 | "sonnet 5 in claude code and gpt-6-sol in codex, pack on and off, just X1, one repetition, run id phase1-a" | The matrix validates; 4 cells; pinned ids; quoted packs; `bom.subset: [X1]`; no decision request | **Fail**, 4/9 checks. Combos have no ids; it wrote `pack:` and `tasks:` for `packs:` and `bom.subset`; it raised two needless decision requests | **Pass**, 9/9 | the matrix shape is now in the skill |
| C1b | "just gpt-6-sol in codex, pack off only, X1, two repetitions, run id solo-2" (differs from the skill's example) | As C1: 2 cells, `packs: ["off"]`, 2 repetitions | **Fail**, 4/9. `pack: "off"` (not a list); `bom.tasks`; no combo id | **Pass**, 9/9 | the shape generalises beyond the example |
| C2 | "opus in claude code and gpt-6-sol in copilot, smoke BOM, 3 reps" | Decision requests for the ambiguous "opus" and for the Copilot combo (not runnable in phase 1); no matrix yet | **Fail**. Asked about opus and packs, but treated Copilot as runnable ("exact id for gpt-6-sol in Copilot") | **Pass**. Asked about opus; flagged Copilot as not a phase-1 harness, to be dropped or waited for | the phase-1 harness rule |
| C3 | A `bench-status/1` document: stalled (540 s), 2 of 4 ended, one cell past its budget with `killing: true` | Says the run is stalled, 2 of 4 ended, the cell is being killed; starts no run; invents nothing | **Fail**. It put the run's stall on the cell and credited the kill to "coord-runner", which does not exist here | **Pass**. Stated the stall, 2 of 4, and the kill that resolves itself; won't start another run | the `bench-status/1` reading guide |
| C4 | `bench report` exited 4: "not graded yet" | Runs `bench grade`, then `bench report` | **Pass** (it followed the printed hint) | **Pass** | none (the old skill's "exit 2 = not built" was not tested by this case) |

The replies are committed verbatim in `docs/proof/a6-replies/`:
- the case inputs;
- the four compiled-matrix replies;
- the old skill's C2–C4 verdicts.

To re-score a compiled-matrix reply, run `uv run python tools/a6_check_matrix.py <c1|c1b> docs/proof/a6-replies/<old|new>-<case>.txt`. On 2026-09-24 this gave exit 1 for both old replies and exit 0 for both new ones.

The new skill's C2–C4 replies were scored in the session but not saved to a file. The table above is their only record (a disclosed gap).

## Decision

The new skill is accepted: every case passes, and no case regressed. One gap was found while running the cases, and the gate caught it: the first draft of the new skill still did not state the matrix shape. It was fixed before the new-skill runs.
