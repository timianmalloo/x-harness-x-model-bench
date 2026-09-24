---
name: start-benchmark
description: Start a cross-harness benchmark run from a prose description of the matrix and BOM subset ("sonnet 5 in claude code and gpt-6-sol in codex, pack on and off, X1, one rep"). Compiles the prose into matrix.yaml (CO-S0), shows the plan for confirmation, then drives bench run → status → report → verify → teardown. The only way a benchmark run starts.
runs_as: Coordinator
---

# /start-benchmark — compile a matrix, then run it end to end

This session compiles the matrix, confirms the plan with the user, starts `bench run`, watches it through `bench status --json`, and reports. It never does benchmark work itself. Every measured cell is a separate native harness process that the `bench` engine launches in its own working copy and harness home (ADR-0013). No cell ever runs in this session, through a native subagent, or through the pack's coordination runner.

**Source of truth:** `docs/design/phase1-walking-skeleton.md` (contracts, exit codes, CLI states) and `docs/specs/harness-bench.md`. **Phase 1 scope:** harnesses `claude-code` and `codex`; one prompted turn per cell; no resume, no judges, no statistics.

## Grounding (first action)

1. **CO-S0 compile first.** Run `/compile` on the user's prose. The compiled output is the matrix, nothing more: combos (harness + pinned model id), pack settings, BOM subset, repetitions. Every unresolved clause becomes a decision request to the user, never a guess.
2. **CO-S1 declare the seat.** This session is the Owner/Coordinator. It is never a measured cell.
3. Mark the run start: `python docs/ai-forward-pack/scripts/audit-log.py start --session <id>`.

## Hard rules

- **Models are pinned.** Resolve each model name to the exact id the harness accepts (for example `claude-sonnet-5`, `gpt-6-sol`). `auto` is refused. A name that fits more than one id (for example "opus") is a decision request.
- **Phase 1 runs `claude-code` and `codex` only.** A Copilot combo is a decision request (drop it, or wait for phase 2), never silently dropped or substituted.
- **Subscriptions only.** Never set or ask for an API key; the cells use the operator's harness logins.
- **Refuse tasks that are not `ready`** (`tasks/<ID>/task.yaml`). Report them; authoring is `/new-bench-task`.
- **Never start a second `bench run` for a run id.** A run that ended `incomplete` is re-planned under a new run id (phase 1 has no resume).

## Stages

| # | Stage | Command | Output |
| --- | --- | --- | --- |
| 0 | Compile | `/compile`, then write `runs/<run_id>/matrix.yaml` | `schema: bench-matrix/1`; quote pack values (`"on"`, `"off"`) |
| 1 | Plan | `bench plan --matrix runs/<run_id>/matrix.yaml --run-id <run_id>` | combos, models, planned builds, pack revision, cells, envelope |
| 2 | Confirm | show the plan and its envelope; on the user's yes, re-run with `--confirm` | `runs/<run_id>/plan.json` (frozen) |
| 3 | Run | `bench run <run_id>` as a background process; it grades when every cell ends | the ledger and archive under `runs/<run_id>/` |
| 4 | Watch | `bench status <run_id> --json` at intervals | a `bench-status/1` document (below) |
| 5 | Report | `bench report <run_id>` | CLI table and `runs/<run_id>/report.html` |
| 6 | Verify | `bench verify <run_id>` | `verify: ok`, or the integrity findings |
| 7 | Teardown | `bench teardown <run_id>` | archived cells' working copies removed |

The matrix shape (`bench/matrix.phase1.yaml` is a complete example; `bench plan` refuses anything else):

```yaml
schema: bench-matrix/1
run_id: phase1-a
bom: { file: bench/bom.yaml, subset: [X1] }   # a list of task ids, or smoke, or full
repetitions: 1
packs: ["on", "off"]                           # quoted: YAML 1.1 reads bare on/off as booleans
combos:
  - { id: cc-sonnet, harness: claude-code, model: claude-sonnet-5 }   # every combo has a unique id
  - { id: codex-sol, harness: codex,       model: gpt-6-sol }
```

Pause only for the plan confirmation (stage 2) and for decision requests. `bench tools install` runs once per machine before the first plan.

**Exit codes:** 0 ok · 1 invalid input (the message on stderr starts with its code; fix the input) · 2 usage · 3 run incomplete · 4 not built (for `bench report`: the run is not graded yet, so run `bench grade <run_id>`) · 5 integrity failure (stop and report it; never re-run over it).

**Preflight codes from `bench run`:** HB-PRE-002 an instruction file above the cells root · HB-PRE-003 disk · HB-PRE-005 Windows long paths off · HB-PRE-007 a planned build missing or changed. Report the code and its message; each needs the user or `bench tools install`, not a retry.

## Reading `bench-status/1`

Fields: `liveness` (`alive` · `stalled` · `not running`), `completion` (`complete` · `in progress` · `incomplete`), `phase` (`starting` · `running`), `stop_code`, `cells_total`, `cells_ended`, `running[]` (`cell_id`, `label`, `elapsed_s`, `budget_s`, `killing`), `outcomes`, `validity`, `causes` (cause codes), `graded`, `lock_age_s`.

- `alive`: report progress (`cells_ended`/`cells_total`, running cells against their budgets) and keep watching.
- `phase: starting`: the run has begun but no cell has reached its process yet (workspace build, spawn, handshake); `elapsed_s` on any listed cell is 0 until its prompt is sent. `phase: running`: at least one cell's process has started; it never reverts to `starting`.
- `stop_code`: null unless the engine recorded `run.launch_stopped` (a run-level stop, e.g. a preflight or disk-floor code); report it as the reason launching new cells stopped.
- `stalled`: the engine holds the lock but has not progressed for `lock_age_s` seconds. Report it to the user; do not start another run.
- `killing: true`: the cell passed its budget (measured from when its prompt was sent, not when its process started) and the engine is confirming its kill. Report it; it resolves itself.
- `not running` + `complete`: go to stage 5. `not running` + `incomplete`: report the counts and causes; the next step is a new plan under a new run id.
- Report only what the document says. It carries no cell text; do not infer one.

## Definition of done

- [ ] Prose compiled; every open clause resolved by the user or recorded as a decision.
- [ ] The plan shown and confirmed by the user before `--confirm`.
- [ ] `bench run` ran as its own process; no cell ran in this session.
- [ ] Report path, the leaderboard rows and the validity counts given to the user; `bench verify` result stated.
- [ ] Any exit code other than 0 reported with its code and meaning, not worked around.

**Audit (last action).** `python docs/ai-forward-pack/scripts/audit-log.py append --shortname "start-benchmark-<run_id>" --session "<id>" --skill start-benchmark --kind command --prompt "<the prose, verbatim>" --summary "<cells run, stages reached, report path>"`.
