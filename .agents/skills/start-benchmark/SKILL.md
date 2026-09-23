---
name: start-benchmark
description: Start a cross-harness benchmark run from a prose description of the matrix and BOM subset ("gpt-6-sol in codex and copilot, opus-5.5 in claude code, pack on and off, smoke BOM, 3 reps"). Compiles the prose into matrix.yaml (CO-S0), then runs plan → bootstrap → run → grade → report → teardown as the Owner/Coordinator, pausing only on a coordination decision request. The only way a benchmark run starts.
runs_as: Coordinator
---

# /start-benchmark — compile a matrix, then run it end to end

The coordinator plans, spawns, grades and reports. It never does benchmark work itself. Every measured cell is a separate harness process launched by the pack's `coord-runner.py`, with its own worktree, session, pinned model, deadline and turn cap.

**Source of truth:** `docs/proposals/cross-harness-benchmarking-proposal.md` (Architecture; Run lifecycle). **Build status:** each stage below names the `bench` command and the spec that builds it (`docs/specs/README.md`). A stage whose command exits 2 is not built: stop there, report which spec is missing, and do not improvise the stage by hand.

## Grounding (first action)

1. **CO-S0 compile first.** Run `/compile` on the user's prose. The compiled output is the matrix, nothing more: combos (harness + pinned model), pack settings, BOM subset, repetitions. Every unresolved clause becomes a decision request, never a guess.
2. **CO-S1 declare the seat.** This session is the Owner/Coordinator. The harness this skill was started from is the coordinator harness; record it in `matrix.yaml` under `coordinator`.
3. Mark the run start: `python docs/ai-forward-pack/scripts/audit-log.py start --session <id>`.

## Hard rules

- **The coordinator is never a measured cell.** If the coordinator's harness is in the matrix, that cell is a second process launched by `coord-runner.py`, exactly like any other worker.
- **Never run a measured cell through the harness's native subagent mechanism.** A native subagent shares the parent's session, context and billing, so its cost would land on the coordinator. Native subagents appear only inside scenario-6 tasks, where the worker is the orchestrator under test.
- **Coordinator tokens are overhead.** Record them under `coordinator_overhead`; never charge them to a cell.
- **Models are pinned.** Resolve every model name to the exact id the harness accepts. `auto` is refused. After launch, check the model the harness's own usage events report.
- **Refuse tasks that are not `ready`** (`tasks/<ID>/task.yaml`). Report them; do not author them in this skill (that is `/new-bench-task`).

## Stages

| # | Stage | Command | Spec | Output |
| --- | --- | --- | --- | --- |
| 0 | Compile | `/compile` → write `runs/<run_id>/matrix.yaml` | S-01 | matrix with resolved model ids and run id |
| 1 | Plan | `bench plan --matrix runs/<run_id>/matrix.yaml` | built | ordered cells, coord-run/1 batches |
| 2 | Bootstrap | `bench run` (first step per cell) | S-05 | per-cell workspace, pack on/off applied, tree hash |
| 3 | Run | `bench run` → `coord-runner.py prepare` then `run` per batch | S-05, S-06 | per-cell artifacts in `runs/<run_id>/<cell>/` |
| 4 | Grade | `bench grade runs/<run_id>` | S-07, S-08, S-09 | `results.duckdb` |
| 5 | Report | `bench report runs/<run_id>` | S-10 | CLI table, HTML report, two AI summaries |
| 6 | Teardown | `bench teardown runs/<run_id>` | S-05 | workspaces deleted after archive verified |

Stages 1–6 run without further prompts. Pause only for a coordination decision request: a worker blocked, a qualification gap, a budget cap reached.

`matrix.yaml` rules: `schema: bench-matrix/1`; quote pack values (`"on"`, `"off"`) because YAML 1.1 reads bare on/off as booleans; `bench validate` and `bench plan` refuse an invalid matrix.

## Definition of done

- [ ] Prose compiled; every open clause resolved by the user or recorded as a decision.
- [ ] `runs/<run_id>/matrix.yaml` written and accepted by `bench plan`.
- [ ] Every cell ran as a coord-runner worker, never in the coordinator's session.
- [ ] Every stage that is not built was reported with its spec id, not worked around.
- [ ] Report paths and the two AI summaries given to the user; coordinator overhead stated.

**Audit (last action).** `python docs/ai-forward-pack/scripts/audit-log.py append --shortname "start-benchmark-<run_id>" --session "<id>" --skill start-benchmark --kind command --prompt "<the prose, verbatim>" --summary "<cells run, stages reached, report path>"`.
