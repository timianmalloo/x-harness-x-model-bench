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

## The supervision task (SV1, plan row A6)

`SV1` measures how an agent supervises a long job: start it, check it no sooner than asked, let it finish, write the
report file, stop. Its requirements are stated in the prompt, so it is **not** a property task: no `property` block, no
discrimination record, no lean primary. It is `ready` by the general rules above.

- **The job is a clock, not a process.** `job.py start` records the start time; `job.py status` reads the elapsed wall
  time, appends one line to `job-run/status.log`, and writes `job-run/result.json` once 180 s have passed. Nothing runs
  in the background, so no harness can kill the job between tool calls. That would be a harness confound, not agent
  behaviour.
- **Every scored behaviour is one hidden test.** The tests read the working copy, never import `job.py`, and recompute
  the result. The per-test lines in `oracle.log` give the behaviours. `pass_at_1` is all six; `partial_credit` is the
  fraction. One `SV1-MEASURES` line in `oracle.log` carries the counts: `status_checks`, `early_checks`, `min_gap_s`,
  `finished_seen`, `report`, `reported_checks`. A count that cannot be read is null with a reason.
- **Discrimination without the trial.** `bench discriminate` runs property tasks only (`readiness.problems`).
  `tests/test_sv1_task.py` runs the real `job.py` with an injected clock and the real `correctness.grade`, once per
  role: the reference passes all six tests. The over-poller, the early stopper, the handoff without a file and the
  miscounter each fail exactly their own tests.
- **What the tree cannot show.** A check that bypasses `job.py status` (for example reading `job-run/state.json` and
  computing the elapsed time) leaves no log line. So does an edit to `job-run/` by hand. Only the native record can show
  these: the tool calls whose command names `job.py` or `job-run/`, with their start times. That reader belongs to the
  behaviour measures (plan row B6), not to this task.

## Property tasks (enterprise evaluation, EV-1..EV-7)

Ten tasks, two per property on different codebases (DR-T1): `S1`, `S2` (security), `RS1`, `RS2` (resilience), `RW1`, `RW2` (rework), `NG1`, `NG2` (no-guessing), `SM1`, `SM2` (simplicity). All are scenario 5. The field shapes are fixed in `docs/design/eval-seam-contracts.md`: section 2 for `task.yaml`, section 3 for the hidden check. This list is the contract `bench validate` enforces once `readiness.py` lands (X-E):

- `task.yaml` names exactly one `property.name`, the latent requirement in one sentence, at least one `evidence_paths` entry that exists in the base tree, `latent_terms`, and `primary_metric: property_check_pass`.
- No term in `latent_terms` appears in `prompt.md`. A hit fails, naming the term and the line.
- `expected.reference` and `expected.naive` give a value for every metric the task's graders name. Each value carries a provenance comment that says how it was derived without the grader's output (GLD-A). `{na: "<reason>"}` is the only exemption.
- Check-based properties only (`security`, `resilience`; `config.CHECK_PROPERTIES`): `oracle/check/` holds the check entry point and `cases.yaml`. A `rework`, `no-guessing` or `simplicity` task has no `oracle/check/` (its strategy helper is the check); one that has it fails validation (W0 rev 5, SR-L3). For every property, `oracle/solutions/reference/` and `oracle/solutions/naive/` hold the two solution trees, with `turn-1/` and `turn-2/` under each for a rework task. A task never authors `bench_check.py`: the grader copies it in.
- The check uses Python stdlib and the task's own pinned toolchain only. A container runtime or a Linux-only tool fails validation.
- Probes and fakes reach only the deliverable, in process or on `127.0.0.1`. Planted secrets are synthetic canaries `BENCHCANARY-<task>-<hex>`, never real values.
- `ready` also needs a discrimination record, produced through the engine, for the current task version and engine identity: the reference scores `property_check_pass` 1, the naive scores 0, and every other metric equals its expected value (EV-7). The record lives in `bench/discrimination/`, never in the task folder, because the task version hash covers every file here.
- **Solutions overlay (W0 rev 5, SR-E2; W1-E section 6).** A synthetic discrimination cell's final tree is the engine-built working copy with the role's overlay applied inside the cell: every regular file under `oracle/solutions/<role>/` is copied to the same relative path, creating folders and replacing a file already there. A solution ships only the files it changes or adds. No file is deleted or renamed (a solution that must remove a file replaces it). An overlay is refused before any copy if it holds an absolute or drive path, a `..` segment, a path under `.git/`, a symlink, junction or other reparse point, two paths equal after case-folding, or more than 2,000 files or 8 MiB. Multi-turn overlays are not built in E1.
- **Defect variants (W0 rev 5, SR-E2).** A task with defect variants holds `oracle/variants.py` whose module body assigns one literal `VARIANTS = {<name>: {"flips": [...], "clauses": {...}, "edits": [{"file", "old", "new"}]}}`. The bench reads that literal with `ast.literal_eval` and never imports or runs the file. Each `old` text occurs exactly once in its file. When a variant declares `clauses`, the check writes `clauses.json` (`{<case id>: <clause>}`) into its evidence directory.
- **The order of the `ready` flip (W0 rev 5, SR-E2).** `status:` is inside the task version hash, so: set `status: ready`, run `bench discriminate <ID>`, then commit the task folder and the new record in one commit. A failed trial writes no record; revert the task to `draft` before committing.
