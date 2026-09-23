# Tasks

One folder per BOM task. The folder name is the task id in `bench/bom.yaml`.

```
tasks/<ID>/
  task.yaml     scenario, prompt, budget, blast radius, model map, graders   (always)
  prompt.md     the exact text every combo receives                          (ready)
  workspace/    base commit reference or Harbor environment                  (ready)
  tests/        hidden tests; never copied into the run workspace            (ready)
  oracle/       rubric, reference spec, annotated clarifications             (ready)
  grade.py      task-specific grading on top of the shared graders           (ready, optional for public tasks)
```

`tasks/_template/` is the copy source. `bench validate` checks every folder against the contract below.

## Status

| status | meaning | what `bench validate` requires |
| --- | --- | --- |
| `stub` | named in the BOM, not authored | `task.yaml` with id, scenario, title, status, source, budget |
| `draft` | being authored | as `stub`, plus `prompt.md` |
| `ready` | runnable | everything above, plus non-empty `tests/` or `oracle/`, and `workspace/` |

A matrix run refuses any task that is not `ready`.

## Rules (from the proposal)

- The prompt text is identical for every combo. No harness-specific phrasing.
- Hidden tests and oracles never enter the run workspace. The grader reads them from here.
- `pack=on` means the pack is installed into the workspace before the clock starts. `pack=off` is the same workspace with the pack stripped (`src/harness_bench/runner/bootstrap.py` holds the strip list).
- A-tasks: the scripted user answers only questions that match an annotated clarification in `oracle/clarifications.yaml`. Everything else gets "decide and state your assumption".
- cfd-bench slices need no UI, no OpenFOAM and no STEP export: pure domain code with numeric oracles.
- Public tasks keep their upstream graders; ours add on top.
- Scenario 7 (G-tasks): pinned formal toolchain, given statements hashed, at least one bug-seeded variant the reference model or proof rejects, and a reproducing test per seeded bug. A reported bug counts only when a failing test reproduces it.
- Authored tasks are private and versioned. Contamination-prone public tasks (E1-E3) are excluded from the pack-effect analysis.
