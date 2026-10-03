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
- A task is a tree, not a repository: a task whose mechanic depends on git history, reflog or dangling objects is not selectable (R-83). First instance: Terminal-Bench 2.0's `fix-git`, which recovers a commit reachable only through `.git/logs/HEAD`.
- A large public task can pin its base tree to an upstream commit instead of vendoring it: `task.yaml`'s `source.workspace_from: source` (default `workspace`) has `workspace.task_source()` build the base tree as `source.repo`@`source.commit` (a cached, verified clone, extracted with `git archive`) with `tasks/<ID>/workspace/` overlaid on top, still one base commit and no upstream history in the cell (R-83). First instance: E4 (SWE-bench Verified, Django).
- Public tasks keep their upstream graders; ours add on top.
- Scenario 7 (G-tasks): pinned formal toolchain, given statements hashed, at least one bug-seeded variant the reference model or proof rejects, and a reproducing test per seeded bug. A reported bug counts only when a failing test reproduces it.
- Authored tasks are private and versioned. Contamination-prone public tasks (E1-E3) are excluded from the pack-effect analysis.

## Property tasks (enterprise evaluation, EV-1..EV-7)

Ten tasks, two per property on different codebases (DR-T1): `S1`, `S2` (security), `RS1`, `RS2` (resilience), `RW1`, `RW2` (rework), `NG1`, `NG2` (no-guessing), `SM1`, `SM2` (simplicity). All are scenario 5. The field shapes are fixed in `docs/design/eval-seam-contracts.md`: section 2 for `task.yaml`, section 3 for the hidden check. This list is the contract `bench validate` enforces once `readiness.py` lands (X-E):

- `task.yaml` names exactly one `property.name`, the latent requirement in one sentence, at least one `evidence_paths` entry that exists in the base tree, `latent_terms`, and `primary_metric: property_check_pass`.
- No term in `latent_terms` appears in `prompt.md`. A hit fails, naming the term and the line.
- `expected.reference` and `expected.naive` give a value for every metric the task's graders name. Each value carries a provenance comment that says how it was derived without the grader's output (GLD-A). `{na: "<reason>"}` is the only exemption.
- `oracle/check/` holds the check entry point and `cases.yaml`. `oracle/solutions/reference/` and `oracle/solutions/naive/` hold the two solution trees, with `turn-1/` and `turn-2/` under each for a rework task. A task never authors `bench_check.py`: the grader copies it in.
- The check uses Python stdlib and the task's own pinned toolchain only. A container runtime or a Linux-only tool fails validation.
- Probes and fakes reach only the deliverable, in process or on `127.0.0.1`. Planted secrets are synthetic canaries `BENCHCANARY-<task>-<hex>`, never real values.
- `ready` also needs a discrimination record, produced through the engine, for the current task version and engine identity: the reference scores `property_check_pass` 1, the naive scores 0, and every other metric equals its expected value (EV-7). The record lives in `bench/discrimination/`, never in the task folder, because the task version hash covers every file here.
