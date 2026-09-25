---
id: "design-phase2-stop-decisions"
title: "Design: run-level stop, decision requests with a timeout, and the circuit breaker (phase 2, row 10)"
type: design
status: draft
owner: "@timianmalloo"
phase: "Phase 2 · smoke on all harnesses (wave 2: row 10, W2-STOP)"
tags: [benchmark, run-engine, stop, decisions, circuit-breaker, tla, acp, lifecycle]
links:
  - { to: design-phase1-walking-skeleton, rel: refines }
  - { to: design-run-lifecycle-model, rel: refines }
  - { to: spec-harness-bench, rel: implements }
  - { to: arch-harness-bench, rel: implements }
  - { to: adr-0007-run-engine, rel: implements }
  - { to: adr-0006-results-data-model, rel: depends-on }
  - { to: adr-0002-cell-driver, rel: depends-on }
  - { to: adr-0004-static-permissions, rel: relates-to }
  - { to: rulings-register, rel: depends-on }
  - { to: coordination-finish-harness-bench, rel: relates-to }
  - { to: note-20260925-stop-decision-calls, rel: relates-to }
review-by: "2027-03-25"
summary: >-
  How a run stops on purpose and how it asks for, and times out, a decision. `bench stop` and `bench answer` write
  apply-once control files that the engine applies on its own thread; a stop sends ACP session/cancel, closes stdin,
  waits a profile grace of at most 10 s, then terminates the Job Object, so every running cell is `stopped` within 30 s
  (R-21, UXA-10). Three decision kinds (blocked cell, qualification gap, spend cap) pause launching, first resolution
  wins, and the plan's decision_timeout applies the default. The built circuit breaker gets its acceptance criterion
  and seeded-revert reds. The grace is a TLC-checked refinement of the terminate step (22 of 22 variants rejected).
---

# Design: stop, decisions and the circuit breaker (phase 2, row 10)

**Track:** W2-STOP-D (plan version 4, `docs/coordination/coordination-finish-harness-bench.md:157`). **Implemented by:** W2-STOP-I (Codex `gpt-6-sol`, effort high; slice plan in §17). **Author:** Claude Opus 5.5 (`claude-opus-5-5`), 2026-09-25. **Grounded at:** `main` `5feece0`.

**Rulings this design carries:** R-3 (`bench-status/1` fields), R-9 (night window), R-15 (the "not recorded" validity, VIEWS), R-21 (graceful end inside the 30 s bound), R-33 (stipulated models), R-34 c4 (`defaultMode`), R-37 (one prompt per cell; the scripted user is not a decision), R-38 (the smoke run waits for W2-STOP), R-44 (`stopped` and `decisions` join `bench-status/1`).

---

## 1. Responsibility

One responsibility: **let an unattended run end or pause on purpose, and never stall.** Concretely:

1. `bench stop <run_id>` stops a running run: no new launch; every running cell's process tree is gone within 30 s of the engine's clock with outcome `stopped`; any open decision becomes `superseded (stop)`; `bench status` shows `stopped` (US-45, UXA-10).
2. The engine raises a **decision request** for a blocked cell, a qualification gap or the spend cap; launching pauses while one is open; the plan's `decision_timeout` applies the default (US-15, UXA-9); P1 answers with `bench answer`. First resolution wins (ADR-0007 §3).
3. The **circuit breaker** (already built, `engine.py:51`, `:196-201`) gets a written acceptance criterion and seeded-revert reds (§7).
4. The **R-21 graceful end** (ACP `session/cancel`, stdin closed, a bounded grace, then `TerminateJobObject`) on every engine kill: stop, budget, host sleep.

**Not this component:** resume (phase 5; ADR-0007 §4's deadline restart is not built), the scripted user (R-37: a tool call inside the one prompt, never a decision request), the R-15 "not recorded" validity state (W2-VIEWS), the model gateway's spend enforcement (ADR-0009, wave 3).

**Boundaries.** Inputs: control files under `runs/<run_id>/control/` (written by `bench stop` / `bench answer`), cell outcomes and per-cell token totals (from the engine's own workers), the plan's parameters, the profile's grace. Outputs: `events` rows (ledger), process kills, `bench-status/1` fields. It owns the decision and stop state; it borrows the cell lifecycle (phase 1) and the ledger (ADR-0006).

## 2. Delivery phasing and seams

Row 10 is on the critical path: STOP-D → STOP-I → USER-W → the smoke run (plan `:183`, R-38). The smoke run needs stop and the timeout (plan `:235`).

| seam | from → to | what | resolution |
| --- | --- | --- | --- |
| S1 | VIEWS → STOP-I | new HB-VAL codes in `errors.py` `RUN_CODES` | STOP-I slice 1, **verbatim from VIEWS's seam request**. STOP-I's own codes are `HB-RUN-006`, `HB-RUN-007` (§4.9): a disjoint prefix, so the order of landing never collides. If the Leader grants S1 to VIEWS and it is on `main` first, slice 1 skips it (check: the codes are present on `main`) |
| S2 | VIEWS → STOP-I | the `VALIDITY` tuple (`status.py:33-34`) | STOP-I slice 1. STOP-I's own `status.py` change (the `OUTCOMES` tuple, `:32`) is an adjacent hunk, so **slice 1 lands S2 and the `OUTCOMES` line in one commit**; if S2 is already on `main`, slice 1 rebases on it first |
| S3 | VIEWS → STOP-I | `model_map` frozen in the plan's task record | STOP-I slice 1: `plan.build_plan` adds `"model_map": task.yaml's model_map (dict or null)` to `tasks[<id>]` (`plan.py:229`). The task folder is inside the version hash, so no new hash field |
| S4 (new) | STOP-I → VIEWS | `views._validity` returns `("not started", None)` for outcome `skipped (decision)`; one line at `views.py:245` | Without it a skipped cell reads `invalid (no model call)`: a wrong label (IO rule). Request to the Leader: grant the line to STOP-I, or VIEWS takes it. STOP-I's test reads status, which does not depend on it |
| S5 (new) | STOP-I → Leader | one `VARIANTS` line in `tools/check_models.py` (`"no_escalate": ("prop", "StopReachesTerminal")`) | `tools/check_models.py` is not in STOP-I's owned paths. Without the line the new seeded variant is never run (vacuity, class MOD-A). Grant with slice 3 |
| S6 (new) | STOP-I → Leader | the live Copilot grace test (`@pytest.mark.credentials`, §16 row R21-3) | a live turn on the GitHub login: a Leader capture window (R-9 rule 1) |
| S7 (flag) | plan `:132` → STOP-I | "`last_update` in `bench status`" was a wave-1 seam to W2-STOP; the version-4 STOP-I row does not carry it | Leader: confirm dropped, or add it. Not designed here |

**Mock-substitutable seams** (so every clause is testable with no model turn): the `Launcher` Protocol (a `FakeLauncher` over `tests/fake_acp_agent.py`), an injected engine clock (`EngineConfig.clock`, default `time.monotonic`), and the control directory (plain files).

## 3. Data model

**Bounded context:** Run Execution (ADR-0006/0007). **Ubiquitous language** (spec glossary, `harness-bench.md:190-218`): run, cell, execution outcome, decision request, spend cap, plan.

**Aggregates** (each bounded by one invariant, referenced by id only):

| aggregate (root) | invariant it protects | model invariant |
| --- | --- | --- |
| **Run stop** (the run, `run_id`) | once a stop is applied, no cell launches and no decision opens; the stop is applied at most once | `NoLaunchAfterStop`, `ControlAppliedOnce`, `StoppedNeverRelaunched` |
| **Decision request** (`decision_id`) | resolved exactly once; the first resolution wins; while any is open, no cell launches | `DecisionResolvedOnce`, `NoLaunchWhileDecisionOpen` |
| **Control message** (`uuid`) | applied at most once, recorded before its file is removed | `ControlAppliedOnce` |

The cell aggregate (phase 1) gains two terminal outcomes: `stopped` and `skipped (decision)`.

**Durable representation:** append-only facts in the existing `events` segment (ADR-0006; no new table, no new segment, no migration). Every new kind is additive; old runs have none of them and read unchanged.

**Grain and fields** (one row is exactly one …):

| kind | one row is exactly one … | fields (all enums, ids, ints; no free text from a cell) | writer | compute reader |
| --- | --- | --- | --- | --- |
| `control.applied` | consumed control file, keyed by `uuid` | `uuid`, `control` (`stop`\|`answer`), `decision_id` (answer) or null, `effect` (`applied` \| `rejected (already resolved)` \| `rejected (unknown decision)` \| `rejected (invalid option)` \| `no-op (already stopped)`) | engine thread | `lifecycle.replay` (ControlAppliedOnce); the run record |
| `run.launch_stopped` (existing) | stop of launching; **at most one per run** | `code`, `reason`. New codes `HB-RUN-006` (operator stop) and `HB-RUN-007` (spend-cap stop) mark a **run stop** (`errors.RUN_STOP_CODES`); every other code stays "launching stopped, running cells continue" | engine thread | `status.stop_code` (R-3), `status.phase`, `lifecycle.replay` |
| `decision.opened` | decision request, keyed by `decision_id` (`D1`, `D2`, … in opening order) | `decision_id`, `decision_kind` (`blocked_cell`\|`qualification_gap`\|`spend_cap`), `subject` (a `cell_id`, a combo id, or the `run_id`), `cause_code`, `options` (list of enum), `default` (enum), `timeout_s`; for `spend_cap`: `spend_tokens`, `spend_cap_tokens`, `cells_unmeasured` | engine thread | `status.decisions`, the skill, replay |
| `decision.resolved` | resolution of one decision (**exactly one per `decision_id`**) | `decision_id`, `state` (`answered`\|`default applied (timeout)`\|`superseded (stop)`), `option` (null when superseded), `control_uuid` (answered) or null | engine thread | `status.decisions`, replay |
| `cell.outcome` (existing) | the cell's terminal outcome (still one per cell, HB-LED-003) | outcome gains `stopped` (cause null) and `skipped (decision)` (cause null, `decision_id`; **the cell's first and only row**) | engine thread | views (via S4), status, grading |
| `attempt.process_ended` (existing) | end of the cell's process | gains `ended_by` (`exit`\|`grace`\|`terminate`): whether the job emptied by itself after end of turn, within the kill grace, or needed `TerminateJobObject` | engine thread | the run record; the R-21 measurement per harness |

**Additivity.** `spend_tokens` on `decision.opened` is a **point-in-time snapshot** (non-additive; the evidence for opening the request), not a stored measure. Counts in `bench-status/1` are derived.

**History rule.** Every row is append-only; nothing is updated. A decision's current state is derived from its rows, never stored.

**Derive, don't store** (DM7):
- the run's phase (`starting`/`running`/`stopping`/`stopped`), a decision's open/resolved state, and the time to default: derived by `status.build` from `events`;
- the run's spend: an in-memory running sum on the engine thread, fed by one `SPEND` inbox item per ended cell (the `STOP` item's pattern, `engine.py:47,174`). It is not persisted: each cell's tokens are derivable from its archived native record by `normalize.totals` (the same function views uses, `normalize.py:75`), so a rebuild is a re-read. The snapshot on `decision.opened` has a test that it equals Σ `normalize.totals` over the cells ended at that point (§16).

**Append-only and interval invariants, enforced and tested:** `lifecycle.replay` gains the rules in §8.3; each has a seeded-ledger test that attempts the forbidden sequence (a second `decision.resolved`, a launch while a decision is open, a second `control.applied` for one `uuid`, a launch after a skip).

**Migration.** None. Additive kinds and fields (expand only). `bench run` refuses a plan confirmed without `decision_timeout` (HB-USR-002, "plan predates decision_timeout; plan a new run"), so no default is guessed into a frozen plan.

## 4. Contracts

### 4.1 `bench stop <run_id>` (the control channel; the model's `controlFile`)

- Writes `runs/<run_id>/control/<uuid>.json` as `<uuid>.json.tmp`, then `os.replace` (ADR-0007 §3; atomic on NTFS within a directory). `uuid` is `uuid.uuid4().hex`.
- Refuses (exit 1) when the run is unknown (HB-USR-001), or when its lock is not held (HB-USR-002: "run <id> is not running (<completion>); nothing to stop"). Resume would consume a stale file; phase 5 decides that.
- Prints: `stop requested (<uuid>). bench status <run_id> shows stopped within 30 s.` Exit 0. It does not wait (YAGNI; UXA-10 is on `bench status`).

**Control file, `bench-control/1`** (strict; ≤ 4 KiB; exactly these keys):

```json
{"schema": "bench-control/1", "uuid": "<32 hex>", "control": "stop" | "answer",
 "decision_id": "D<n>" | null, "option": "<option enum>" | null, "requested_at": "<UTC ISO>"}
```

**Engine side, every loop tick (engine thread, `loop_interval` 0.2 s):** list `control/*.json` (never `*.tmp`); order **stop files first**, then answers by (`requested_at`, `uuid`). For each file:
1. parse strictly; a malformed or oversized file is renamed `<name>.rejected` (kept as evidence), logged with HB-USR-002 and no content, and gets no ledger row;
2. a `uuid` already applied in this engine: delete the file, no row;
3. otherwise append `control.applied` with its effect, apply the effect (§5, §6), then delete the file.

### 4.2 `bench answer <run_id> <decision_id> <option>`

Checks at write time that the decision exists, is open and offers `option` (else HB-USR-002 naming the valid options), then writes an `answer` control file like §4.1. The engine re-checks at apply time (time-of-check to time-of-use): a decision resolved in between gives `control.applied{effect: rejected (already resolved)}`.

### 4.3 Plan parameters (`plan.py:41-52`, US-6)

| parameter | default | meaning |
| --- | --- | --- |
| `decision_timeout` | `1800` (s; spec US-15 "default 30 minutes") | seconds an open decision waits before its default applies, on the engine's monotonic clock |
| `spend_cap_tokens` | `null` (no cap) | the run's cap on Σ tokens over ended cells (§6.3). **Unit is an open decision request, DR-1** |

`bench plan` gains `--decision-timeout-minutes` and `--spend-cap-tokens`. The confirmation output prints `decision timeout: 30 min; spend cap: none` (US-6 names both).

### 4.4 Profile datum (R-21 c1)

`bench/profiles/<harness>.yaml` gains `shutdown_grace_seconds` (number, `0 < x ≤ 10`; `profiles.load` refuses more, HB-USR-002). All three profiles start at `10`: no harness's shutdown time is measured yet, and 10 is the phase-1 `end_grace` (`engine.py:84`). `simplify:` one ceiling for all; upgrade trigger: a harness whose `ended_by` shows `terminate` on routine ends (the shutdown needs longer, measured), or a measured shorter need. `ProfileLauncher` and the `Launcher` Protocol gain `shutdown_grace: float`; `plan.profile_record` records it (US-26: a run reads its own dimensions). `EngineConfig.end_grace` is removed: one grace for end of turn and for kills.

### 4.5 Driver contract (ACP `session/cancel`)

**Established (Verified):** ACP SDK 1.5.0 `schema/schema.json` (the pinned `@agentclientprotocol/sdk` in `.tools/harness/node_modules`): `CancelNotification` is `x-method: session/cancel`, a notification (no id), params `{sessionId}` required; the agent "MUST" answer the pending `session/prompt` with `stopReason: "cancelled"` and answer pending `session/request_permission` with outcome `cancelled`.
**Not established (Flagged):** whether `claude-agent-acp` 0.81.2, `codex-acp` and Copilot 1.0.89-1 honour it. The design does not depend on it: the hard kill fires at the grace end regardless. The per-harness answer is measured by `ended_by` (§3) and the Copilot live test (S6).

`driver.CancelToken` (new): `request()` is non-blocking and idempotent; it puts `("cancel", None)` on the bound `_Channel.inbox`, or sets a flag the channel reads when it binds. **Only the worker thread writes the adapter's stdin** (the engine thread never writes a pipe, so a stuck adapter cannot block it). On `cancel` inside `_Channel.rpc`: if `session/prompt` is in flight, send `{"jsonrpc": "2.0", "method": "session/cancel", "params": {"sessionId": sid}}`; in every phase, close stdin; then keep reading until the prompt's response, EOF, or the engine's kill. `run_turn` checks the token immediately before writing `session/prompt` and does not send it if a cancel was requested (the model's `SendPrompt` guard `~killRequested[c]`). `run_turn(..., cancel: CancelToken | None = None)`; the default keeps today's behaviour for every existing caller.

### 4.6 `bench-status/1` additions (R-3, R-44)

The schema stays `/1` (R-3: producer and only consumer move in one commit; nothing stores a status document). `status.parse` stays strict.

| field | change |
| --- | --- |
| `phase` | closed enum gains `stopping` and `stopped`. `stopping`: a run stop is recorded (`run.launch_stopped` with a code in `RUN_STOP_CODES`) and some launched cell has no outcome. `stopped`: a run stop is recorded and every launched cell has an outcome |
| `outcomes` keys | `OUTCOMES` gains `stopped` and `skipped (decision)` (`not started` exists) |
| `decisions` | list of `{decision_id, decision_kind, subject, cause_code, options, default, state, default_in_s}`; `state` ∈ {`open`, `answered`, `default applied (timeout)`, `superseded (stop)`}; `default_in_s` is a non-negative int while open, else null (from `decision.opened.recorded_at` + `timeout_s` − now; display only, the engine's deadline is monotonic). `subject` matches `CELL_ID`, the combo grammar, or `RUN_ID`. No free strings (ADR-0007 §10, boundary B2) |
| `stop_code` | unchanged semantics (R-3): the `run.launch_stopped` code, now possibly `HB-RUN-006`/`HB-RUN-007` |

**Text form** (`status.text`; UXA-7 names the subject, the cause and an action):
- `Run <id>: stopped (HB-RUN-006). <n> stopped, <m> never started, <k> ended before the stop.`
- `Run <id>: stopping. <r> cells still ending.`
- `Decision D1 · blocked cell <cell_id> · HB-CELL-202 · options continue | stop · default continue in 29 min. Answer: bench answer <run_id> D1 <option>`

The `/start-benchmark` skill (`.claude/skills/start-benchmark/SKILL.md` and `.agents/skills/start-benchmark/SKILL.md`) updates its field list and reading rules **in the same commit** (R-3 c3): it relays each open decision (id, kind, subject, cause code, options, default, time to default; never cell text) and writes the answer with `bench answer`; P1 saying "stop" runs `bench stop`.

### 4.7 R-34 condition 4: `defaultMode`

**Decision: declare `default` outright** in `bench/profiles/claude-code.yaml` (`"defaultMode": "default"`), and keep recording `permission_mode_effective`.
- Evidence (Verified): the session reports `default` today (`tests/test_driver.py:692-700`, the `claude-code-x1.jsonl` recording; the stderr fallback line in `tests/test_allowlist_classes.py:127`).
- Why not keep `dontAsk`: a later build that honours `dontAsk` would refuse an unlisted tool **silently**, with no `session/request_permission`. The driver's count would then read 0, and US-14's control would pass vacuously on exactly the asymmetry R-34 found. Under `default`, an unlisted tool surfaces as a counted permission request.
- The declared mode then equals the effective one. The report header keeps showing the effective mode (R-34 c4). The profile comment loses its fallback paragraph.
- Red-first: `tests/test_profiles.py:266` asserts `dontAsk` today; the new assertion is `default`, red first. A second test compares the declared mode with the recording's effective mode.
- Blast radius: the profile hash changes, so plans made after it differ from the wave-1 baseline's `profile_hash`; behaviour is the same (the effective mode is unchanged). The run record says so.

### 4.8 Consumed contracts

| contract | source | confidence |
| --- | --- | --- |
| ACP `session/cancel` notification, `stopReason: cancelled` | `@agentclientprotocol/sdk` 1.5.0 `schema/schema.json` (`CancelNotification`, `StopReason`) | Verified (read) |
| Each adapter honours `session/cancel` | none | Flagged; not depended on |
| `TerminateJobObject` kills the whole tree, whatever the child does | spike N2 (`phase1-walking-skeleton.md:127`); `procs.py:164` | Verified (phase 1) |
| `os.replace` is atomic within a directory on NTFS | ADR-0007 §3 | Verified (phase-1 design); not re-run here |
| every ledger row carries `mono_ns` (the engine's clock) | `ledger.stamp` (`ledger.py`) | Verified (read) |

### 4.9 Error codes (`errors.py`, STOP-I)

| code | meaning |
| --- | --- |
| HB-RUN-006 | run stopped by the operator (`bench stop`, or a decision answered `stop`): running cells stopped, no new launch |
| HB-RUN-007 | spend cap reached: the run stopped (the `spend_cap` default or answer) |

`errors.RUN_STOP_CODES = ("HB-RUN-006", "HB-RUN-007")`. HB-USR-001/002 are reused for CLI refusals and malformed control files. The circuit breaker keeps its built code: the third failure's cell code (`engine.py:199`).

## 5. The stop sequence and its 30-second budget

On the engine thread, in one tick, for a stop file:
1. `control.applied{uuid, control: stop, effect: applied}` (or `no-op (already stopped)` if a run stop is already recorded);
2. `run.launch_stopped{code: HB-RUN-006, reason: "bench stop"}` (`_stop_launching`, idempotent; model `ApplyStop`);
3. every open decision: `decision.resolved{state: superseded (stop)}`;
4. every active cell: `_kill(a, "stop")`: sets `kill_reason` (first reason wins), `kill_deadline = now + shutdown_grace`, and `a.cancel.request()`. A cell with no process yet has `kill_reason` set too, so its worker never spawns (§11).

Every later tick, `_check_kills(now)` issues `TerminateJobObject` for each cell past its `kill_deadline` with a live job, **whether or not its turn has ended** (the hard floor, R-21: "the kill still fires at the bound regardless"). The worker then confirms the job is empty (`_end_process`), records `attempt.process_ended{ended_by}` and, with `kill_reason == "stop"`, `cell.outcome{stopped}` **without** the provider-error scan (a stop takes precedence over every cause; the spec says `stopped`), then archives.

| step | bound | source |
| --- | --- | --- |
| file written → applied | ≤ `loop_interval` + one drain (0.2 s + 0.2 s) | `engine.py:224-236` |
| applied → `TerminateJobObject` | ≤ `shutdown_grace_seconds` ≤ 10 s | R-21 c1 |
| terminate → job empty (confirmed) | ms on the phase-1 evidence; unbounded only in the HB-RUN-002 defect case | spike N2; `engine.py:447-454` |
| confirmed → `cell.outcome{stopped}` appended | stderr drain join ≤ 5 s (pipes are closed, so immediate in practice), `cp.wait` immediate, two records | `engine.py:423-435` |
| **total, worst case outside HB-RUN-002** | ≤ 0.4 + 10 + 5 + ε ≈ 16 s, inside 30 s | Inferred; the §16 test measures it on the ledger's `mono_ns` |

A cell that is still building its workspace has no process tree. Its worker checks `kill_reason` after each build step and before the spawn, then records `stopped` with no process. `assume:` a single workspace-build step (a local clone, a pack install) takes far less than 20 s on this host. **Confirm:** `cell.workspace_built.mono_ns − cell.launch_intent.mono_ns` in the wave-1 exit run's ledger (the Leader reads it at the STOP-I join). **Breaks:** a stop during a slow build shows `stopping` past 30 s; the ledger shows it, and the fix is a cancel hook in `workspace.py` (not owned by STOP-I).

After the last active cell's worker exits, the loop ends as today: grading runs on the terminal cells (US-45), `run.completed` is written, and `bench run` exits 3 (unlaunched cells stay `not started`).

The same kill path (grace, then hard floor) serves the budget kill (`timeout`) and host sleep (`host_suspended`). A broken ledger (`aborted`) uses it too; nothing is recorded then, so the grace changes nothing there.

## 6. Decision requests (US-15)

### 6.1 Triggers, options, defaults

Opened on the engine thread when a `cell.outcome` (or a `SPEND` item) is processed, **only when it can change something** (affected cells are still pending), never after a run stop (model `RaiseDecision` guard `~stopApplied`), and at most once per (`decision_kind`, `subject`):

| `decision_kind` | trigger | `subject` | options (closed enum) | default (on timeout) | effect of the default |
| --- | --- | --- | --- | --- | --- |
| `blocked_cell` | a `cell.outcome` whose cause is `blocked_auth` (HB-CELL-202) or `blocked_permission` (HB-CELL-201) | the `cell_id` | `continue`, `stop` | `continue` | none: the cell keeps its `blocked (…)` outcome; launching resumes |
| `qualification_gap` | a `cell.outcome` whose cause is `model_unavailable` (HB-CELL-116: the combo's pinned model is not served, ADR-0003) | the combo id | `skip_combo`, `continue`, `stop` | `skip_combo` | every pending cell of that combo: `cell.outcome{skipped (decision), decision_id}`, removed from the queue |
| `spend_cap` | Σ run tokens ≥ `spend_cap_tokens` after a `SPEND` item | the `run_id` | `stop`, `continue` | `stop` | a run stop, code HB-RUN-007 (§5) |

The two definitions ("blocked cell", "qualification gap") are this design's reading of US-15 against the closed cause list. They are recorded in `docs/notes/stop-decision-calls.md` (call 1). An answer of `stop` on any decision is an operator stop (HB-RUN-006). An answer of `continue` on `spend_cap` disables the cap for the rest of the run.

### 6.2 Tick order and "first resolution wins"

Engine thread, each tick: drain → **controls (stops, then answers)** → **expire decisions** (`now ≥ opened_mono + timeout_s`: `decision.resolved{default applied (timeout)}` and the default's effect) → budgets → kill deadlines → sleep and disk checks → launch (`while pending and not stopped and not broken and no decision open and len(active) < parallelism`).
- The loop runs **while any decision is open**, as well as while cells are pending or active, so an open request is always resolved (model liveness `DecisionEventuallyResolved`; UXA-9).
- Resolution goes through one method, `_resolve(decision_id, state, option, control_uuid)`, which returns without a row when the decision is already resolved. Every path calls it: answer, timeout, supersede. That method **is** the "first resolution wins" rule; the losing answer is visible as `control.applied{effect: rejected (already resolved)}`.

The decision state machine lives in `engine.py` as a small pure class (`_Decisions`: `open`, `answer`, `expire(now)`, `supersede_all()`, each returning the rows to append). It does no I/O, so the race tests call it directly in both orders. `simplify:` one class in `engine.py`, not a new module (STOP-I owns no new file). Upgrade trigger: a second consumer of decision logic.

### 6.3 Spend

A cell's tokens = Σ over `normalize.BUCKETS` of `normalize.totals(profile.usage_source, extraction, turn_usage)` (`normalize.py:28,75`). That is the report's own definition, so there is no second one. The worker computes it from the extraction it already reads for the provider-error scan (`engine.py:463-466`; read once, used twice), and sends `SPEND{cell_id, tokens | null}` before its outcome. `null` means not recorded (for example Copilot with no `session.shutdown`, R-21 c2); it adds to `cells_unmeasured` and never to the sum. A stopped cell sends no `SPEND`.
**Residual (disclosed at confirmation):** with `usage_source: native_record`, the tokens are known only when a cell ends. The cap is checked per ended cell, so a run can pass it by up to what the running cells spend. And the cap is blind to unmeasured cells: `bench plan` prints `spend cap: <n> tokens, checked when each cell ends; cells whose usage is not recorded are not counted`.

## 7. The circuit breaker: acceptance criterion

Built: `CIRCUIT_BREAKER = 3` (`engine.py:51`), the streak in `_after_append` (`engine.py:193-201`). Existing tests: `test_the_circuit_breaker_stops_launching_once` (`tests/test_engine.py:405`), `…_fires_at_its_threshold_not_before` (`:411`), `test_a_success_resets_the_infrastructure_streak` (`:838`).

**AC-CB (the acceptance criterion):**
1. **Fires.** When the third *consecutive* `cell.outcome` (in ledger append order) whose cause `invalidates` (attribution `infrastructure` or `benchmark`, `errors.py:39-42`) is appended, the engine thread appends `run.launch_stopped{code: <that cause's code>, reason: "circuit breaker: 3 consecutive infrastructure failures"}` before any further `cell.launch_intent`, and no `cell.launch_intent` follows it.
2. **Not before.** Two consecutive invalidating outcomes never stop launching.
3. **Resets.** An outcome with no cause (`completed`) or a non-invalidating cause (agent, harness, none) sets the streak to 0.
4. **Neutral outcomes (new).** `stopped` and `skipped (decision)` neither count nor reset. Today a cause-less outcome resets (`engine.py:200-201`), so a stop or a skip would reset the streak; that is red first once those outcomes exist.
5. **Running cells continue.** The breaker kills nothing and writes no `stopped` outcome; running cells reach their own outcome.
6. **Once.** At most one `run.launch_stopped` per run; a breaker after a run stop writes nothing.
7. **End state.** The run ends with `run.completed` (no ledger break), exit 3; unlaunched cells are `not started`; `bench status` shows `stop_code` = the cause's code.
8. **No decision request.** This deviates from ADR-0007 §7 ("raises a decision request (resume launches / stop the run; default: stop)"). It is recorded, and DR-2 asks the Owner.

**Seeded-revert reds** (`tests/mutations/stop.json`; each is run and observed red before the slice commits; for criteria 1–3, 5 and 6 the code already exists, so the red *is* the seeded revert):

| mutant (find → replace) | red test(s) |
| --- | --- |
| `CIRCUIT_BREAKER = 3` → `4` | `…_fires_at_its_threshold_not_before`, `…_stops_launching_once` |
| `CIRCUIT_BREAKER = 3` → `2` | `…_fires_at_its_threshold_not_before` (new assertion: exactly 3 intents with 5 failing cells) |
| delete `self.infra_streak = 0` | `test_a_success_resets_the_infrastructure_streak` |
| `cause.invalidates` → `cause is not None` | new `test_harness_failures_do_not_trip_the_breaker` (three `adapter_crash` cells, all launched) |
| the neutral-outcome guard removed | new `test_a_stop_or_skip_neither_counts_nor_resets_the_streak` |
| `_stop_launching`'s `if self.stopped: return` removed | `…_stops_launching_once` (already in `engine.json`; kept) |
| `_kill(...)` added to the breaker path | new `test_the_breaker_leaves_running_cells_running` |

## 8. The R-21 grace as a TLA refinement (`models/**`)

### 8.1 The refinement

The **terminate step** (`EngineKill`, `StopCell`'s running branch → `CellDies`) is refined by one variable and two actions. Every other action is unchanged apart from `UNCHANGED grace`.

```tla
VARIABLES ..., grace   \* [cell -> BOOLEAN] physical: cancel sent, stdin closed, TerminateJobObject not yet issued (R-21)

EngineKill(c) == ... /\ grace' = [grace EXCEPT ![c] = TRUE] ...          \* was: killRequested, killReason only
StopCell(c)   == ... running branch: /\ grace' = [grace EXCEPT ![c] = TRUE]
CellDies(c)   == /\ proc[c] = "running" /\ killRequested[c]
                 /\ ~grace[c]   \* R-21: TerminateJobObject was issued
                 /\ ...          \* unchanged otherwise

\* The cell may end on its own within the grace (an abstract CellDies) ...
GracefulExit(c) ==
    /\ proc[c] = "running" /\ killRequested[c] /\ grace[c]
    /\ proc' = [proc EXCEPT ![c] = "exited"]
    /\ killRequested' = [killRequested EXCEPT ![c] = FALSE]
    /\ grace' = [grace EXCEPT ![c] = FALSE]
    /\ UNCHANGED <<all other variables>>

\* ... or the engine issues TerminateJobObject when the grace ends (an abstract stutter).
EndGrace(c) ==
    /\ BUG # "no_escalate"
    /\ engine = "up"
    /\ proc[c] = "running" /\ killRequested[c] /\ grace[c]
    /\ grace' = [grace EXCEPT ![c] = FALSE]
    /\ UNCHANGED <<all other variables>>

Next     == ... \/ GracefulExit(c) \/ EndGrace(c)
Fairness == ... /\ WF_vars(EndGrace(c))     \* no fairness on GracefulExit: a child may ignore the cancel
TypeOK   == ... /\ grace \in [Cells -> BOOLEAN]
```

**Refinement mapping** (hide `grace`): `GracefulExit(c)` ↦ `CellDies(c)` (the same effect on every other variable); `EndGrace(c)` ↦ a stutter; the strengthened `CellDies` removes behaviours only; `EngineKill` and `StopCell` map to themselves. So every behaviour of the refined spec is a behaviour of the version-3 spec (safety carries over), and `WF_vars(EndGrace(c))` restores the progress that `CellDies`'s new guard would otherwise block (liveness carries over). R-21 c3 "keeps its semantics": the same 16 invariants and 5 properties, unchanged.

**Timing is not in the model** (it is untimed). The 30 s bound and the ≤ 10 s grace are code and test obligations (§5, §16), as the phase-1 budget kill already was.

**New seeded variant** `no_escalate` (`EndGrace` disabled): a child that ignores the cancel keeps its process forever. It is rejected by `StopReachesTerminal`, checked alone (MOD-A). It needs the S5 line in `tools/check_models.py`.

### 8.2 Spike evidence (Verified, this session)

The refinement was applied by script to a scratch copy of `models/run_lifecycle.tla` at `5feece0`, with the `no_escalate` line added to a scratch copy of `tools/check_models.py`. Then `python tools/check_models.py --quick` was run with the pinned `tla2tools.jar` (sha256 `936a2620…0e88`) on JDK 21.0.11:

| run | result | distinct states (refined / version 3) |
| --- | --- | --- |
| liveness (5 properties, 1 cell) | ok | 58,256 / 57,344 |
| grading (2 cells, 2 passes) | ok | 17,213,024 / 16,325,776 |
| safety, small bounds (16 invariants) | ok | 4,832,976 / 4,503,440 |
| witness `NotAllCellsFinished` | violated as expected | — |
| 21 existing seeded variants | 21 of 21 rejected, each by its own target alone | — |
| `no_escalate` | rejected by `StopReachesTerminal` | — |

The US-44-bounds safety run (3 cells, parallelism 2) on the refined model: see §8.4.

### 8.3 Conformance: the lifecycle table and the replay (`lifecycle.py`)

| new/changed `TABLE` entry | model action | replay rule (a violation names it) |
| --- | --- | --- |
| `control.applied` | `ApplyStop` / `ApplyAnswer` (the `controlApplied` half) | **ControlAppliedOnce**: a second row for one `uuid` |
| `run.launch_stopped` with a `RUN_STOP_CODES` code | `ApplyStop` (`stopApplied`) | NoLaunchAfterStop (exists); **one per run** |
| `decision.opened` | `RaiseDecision` | **NoDecisionAfterStop**: none after a run stop |
| `decision.resolved` | `ApplyAnswer` / `TimeoutDefault` / `ApplyStop`'s supersede | **DecisionResolvedOnce**: a second row per id; **follows its `decision.opened`** |
| `cell.launch_intent` | `WriteIntent` | **NoLaunchWhileDecisionOpen**: an intent while any decision is open |
| `cell.outcome{skipped (decision)}` | none (the cell is never launched; a filter on the queue) | allowed as a cell's **first** row; any later row for that cell violates WRITE_INTENT_ONCE / AT_MOST_ONCE |
| `cell.outcome{stopped}` | `RecordExit` after `StopCell` (with a process) or `StopCell`'s record branch (none) | NoOutcomeWhileRunning (exists) |

`run-lifecycle-model.md`'s mapping table marks the phase-2 rows (`StopCell`, `WriteControl`/`ApplyStop`/`ApplyAnswer`/`RemoveControl`, `RaiseDecision`/`TimeoutDefault`) implemented, and adds `GracefulExit` (→ `attempt.process_ended{ended_by: grace}`) and `EndGrace` (the engine's `TerminateJobObject` at `kill_deadline`, no event).

**Decisions in the model:** the model has one abstract decision; the engine has one per `decision_id`. The mapping holds per id because decisions interact only through the launch guard (any open → no launch) and the stop (supersedes all). Multi-decision interleavings are not TLC-checked (residual, §19). The spend-cap stop has no control file: in the ledger it is the model's `WriteControl("stop"); ApplyStop`. The ledger never shows `WriteControl` for any stop, so the replay is unaffected.

### 8.4 US-44-bounds safety on the refined model

`python tools/check_models.py` (full, the scratch copy of §8.2): `safety` (3 cells, parallelism 2, 1 crash, symmetry, all 16 invariants) **ok, 85,283,136 distinct states, 406 s** (version 3: 77,212,448 states, 5 min 37 s). The whole run printed "all model checks passed", with the 22 variants again rejected by their own targets. STOP-I's CI budget: the nightly US-44 run grows by about 10 % in states and 20 % in time (Verified here; CI hardware may differ).

## 9. Patterns (named, and past the Ladder)

| pattern | where | why (ladder rung) |
| --- | --- | --- |
| **Command mailbox + Single Writer** (ADR-0007 §3) | control files applied on the engine thread | already the engine's shape (rung 2: reuse); the `STOP` inbox item is the precedent |
| **Idempotent Receiver** (EIP) | `control.applied{uuid}` before delete; replayed uuids skipped | ADR-0007 §3; the model's `ControlAppliedOnce` |
| **Atomic file write** (temp + `os.replace`) | `bench stop`, `bench answer` | stdlib (rung 3) |
| **State machine, first-writer-wins** | `_Decisions._resolve` | one method guards every resolution path |
| **Graceful shutdown with a hard deadline** (cooperative cancel, then kill) | `CancelToken` + `kill_deadline` + `TerminateJobObject` | R-21; the phase-1 end-of-turn path already does stdin-close-then-terminate (`engine.py:438-458`), so this reuses it for kills |
| **Circuit Breaker** (Nygard), open-only | built | the acceptance criterion only; no half-open state (DR-2) |
| **Refinement mapping** (Lamport) | §8.1 | proves "keeps its semantics" without a second model file |

**Rejected:** a named pipe or socket for `bench stop` (a second IPC mechanism; files are ADR-0007's and the model's); a thread that writes `session/cancel` from the engine thread (it can block on a stuck adapter's pipe and races the worker's writes); a new `decisions.py` module (not an owned path; one consumer); a separate abstract TLA module to check the refinement by `INSTANCE` (it would duplicate 590 lines; the mapping plus the unchanged property set plus the variants is the smaller correct proof); a half-open circuit breaker (YAGNI until DR-2).

## 10. Change-surface list (E7), with owners

| surface | change | owner |
| --- | --- | --- |
| store (`events`) | `control.applied`, `decision.opened`, `decision.resolved`; outcomes `stopped`, `skipped (decision)`; `ended_by`; codes HB-RUN-006/007 | STOP-I (`engine.py`, `errors.py`) |
| model/lifecycle | `lifecycle.TABLE` + replay rules (§8.3); `models/run_lifecycle.tla` (§8.1); `docs/design/run-lifecycle-model.md` mapping table | STOP-I; `tools/check_models.py` via S5 |
| service (engine) | control reader, `_Decisions`, `SPEND`, graceful kill path, `_check_kills`, pre-spawn stop check, neutral outcomes in the breaker, the stale `getattr` removed (`engine.py:369-371`) | STOP-I |
| driver | `CancelToken`; `session/cancel` + stdin close on the worker thread; no prompt after a cancel | STOP-I (`driver.py`) |
| plan / profile | `decision_timeout`, `spend_cap_tokens`; `shutdown_grace_seconds` (≤ 10); `model_map` (S3); `defaultMode: default` | STOP-I (`plan.py`, `profiles.py`, `bench/profiles/*.yaml`) |
| wire (`bench-status/1`) | `phase` enum, `OUTCOMES`, `decisions`; `VALIDITY` (S2) | STOP-I (`status.py`) |
| client (CLI) | `bench stop`, `bench answer`, plan flags, the plan confirmation lines | STOP-I (`cli.py`) |
| UI (skill) | `start-benchmark` field list and relay rules, same commit as `status.py` | STOP-I (both skill copies) |
| compute reader | views: `skipped (decision)` → `not started` validity (S4); report: none in wave 2 (the banner's "stopped" line is wave 4, row 20) | VIEWS or granted (S4) |

## 11. Error and concurrency model

- **One writer.** Every new row is appended by the engine thread. Workers hand `SPEND` and records through the bounded inbox (`engine.py:116`), as today.
- **Linearization points.**
  - A **stop** takes effect when its `run.launch_stopped` row is appended.
  - A **spawn** takes effect at the worker's check of `kill_reason` under `a.lock`, just before `procs.spawn`. The check sets `a.spawning`. `_kill` on a cell with no process sets `kill_reason`, and the worker, after the spawn, sees it under the lock and terminates the new job at once (no grace; no prompt was sent). A spawn that passed its check before the stop is, in the model, a `StartCell` before `ApplyStop`; its `attempt.process_started` row may land after `run.launch_stopped` (the ledger lags; the replay's NoLaunchAfterStop concerns intents only).
  - A **prompt send** takes effect at `run_turn`'s cancel check before writing `session/prompt` (the model's `SendPrompt` guard).
- **The engine thread never blocks on a cell.** `CancelToken.request()` is a queue put, and `TerminateJobObject` is one non-blocking call (`_job_query` swallows `OSError`, `engine.py:517-522`). `a.lock` is held only for field updates and `cp.close()`.
- **Clocks.** Decision deadlines and `kill_deadline` use the injected monotonic clock (ADR-0007 §4). `default_in_s` in status uses the wall clock (display only).
- **Crash.** Unchanged from phase 1: a crash leaves the run `incomplete`; open decisions stay open in the ledger, and resume is phase 5 (ADR-0007 §4 restarts their deadlines from the resume). A control file left in `control/` stays there.

## 12. Failure-mode analysis

| failure mode | from | disposition | how | detection | test |
| --- | --- | --- | --- | --- | --- |
| A child ignores cancel and stdin EOF | cooperative cancel | prevent | the hard floor at `kill_deadline`, whatever the turn state | `ended_by: terminate` | R10-1 |
| The adapter never answers `session/cancel` | unverified per-harness contract | mitigate | not depended on; the grace ends it | `ended_by` per harness | R10-1; S6 |
| Terminate unconfirmed (OS refuses) | Job Object | detect | the HB-RUN-002 path, unchanged; the stop bound is then missed and shown | `killing (unconfirmed)` in status; HB-RUN-002 | existing T1-8 tests |
| Stop during the workspace build | build steps have no cancel hook | mitigate + accept | a check after each step; residual bounded by one step | `stopping` past 30 s in status | R10-5 |
| Stop between the prompt ack and the send | ack barrier | prevent | cancel checked before `session/prompt` | `prompts` never 2; the outcome is `stopped` | R10-6 |
| Answer and timeout in one window | two resolution paths | prevent | `_resolve` first-wins; fixed tick order | `control.applied{rejected (already resolved)}` | R10-4a/b |
| Stop and timeout / stop and answer | three resolution paths | prevent | the same | one `decision.resolved` per id | R10-4c–f |
| Duplicate stop file, or `bench stop` twice | the operator | prevent | `no-op (already stopped)` | the row | R10-8 |
| Malformed or oversized control file | a hostile or buggy writer | detect + contain | quarantined `.rejected`, HB-USR-002 log, no row, no effect | `engine.log` | R10-9 |
| Stale answer (decision already resolved) | TOCTOU between the CLI and the engine | prevent | the engine re-checks | `rejected (already resolved)` | R10-4a |
| A decision opened with nothing pending | the trigger | prevent | open only when affected cells are pending | no row | US15-4 |
| The run ends with a decision open | the loop condition | prevent | the loop runs while any decision is open | — | US15-5 |
| The spend cap passed by the running cells | spend known at cell end | accept | disclosed at confirmation (§6.3); residual up to the running cells' spend | `spend_tokens` on the decision | US15-3 |
| Unmeasured cells hide spend | `native_record` sources | detect + accept | `cells_unmeasured` on the decision; disclosed | the row | US15-3b |
| Stop or skip resets the breaker | cause-less outcomes | prevent | neutral outcomes | — | CB-5 |
| A plan without `decision_timeout` | plans made before STOP-I | prevent | refused, never defaulted | HB-USR-002 | P-2 |
| `keep_awake` not released on an exception | the engine's `finally` | prevent | already in `finally` (`engine.py:260`); now tested | — | R10-7b |
| A grace over 10 s in a profile | profile edit | prevent | `profiles.load` refuses | HB-USR-002 | PR-2 |

## Adversarial analysis (STRIDE-lite)

| Trust boundary | STRIDE threat | Disposition | Control / rationale | Negative test |
| --- | --- | --- | --- | --- |
| `runs/<run>/control/` (written by any process of the operator's account, **including a cell's agent**: native cells run as the same user, ADR-0013) | S/T: a cell's agent writes a stop or an answer | accept (ADR-0012 scope: authored tasks, trusted operator; runs is outside the cell's working copy) | every control is recorded (`control.applied{uuid, effect}`, time) and shown in the run record; the effect set is closed (stop, or a listed option); the residual is a spurious stop or answer by an agent, visible in the ledger | R10-9 (malformed); R10-8 |
| control file content | T/E: an oversized or crafted file (path, nested JSON, a big string) | mitigate | ≤ 4 KiB, exact keys, enum values, uuid and decision-id grammars; the file name is never used as a path component beyond `control/` | R10-9 |
| control file content | D: a flood of files | mitigate | each tick reads a directory listing; malformed files are moved aside once. `simplify:` no rate limit; upgrade trigger: a tick over 1 s in `engine.log` | — |
| `bench-status/1` → the coordinator session (B2) | I: cell text reaches the LLM session | mitigate | decisions carry enums, ids and codes only; `parse` rejects any free string | ST-3 |
| engine → adapter stdin | D: a stuck adapter blocks the engine thread | mitigate | only the worker writes stdin; the engine only queues | R10-1 (the fake ignores stdin) |
| engine log | R: who stopped the run | accept | the ledger records the control's uuid and time, not its writer; the OS gives no writer identity for a file on this host | — |

## Privacy analysis (LINDDUN-lite)

This component touches no personal data. Checked: control files and the new rows hold enums, bench ids, codes, token counts and times; no cell text, prompt, transcript or credential. `bench-status/1` stays free of strings.

## 14. Telemetry

- **Ledger (load-bearing, O12):** the rows in §3. Each carries `recorded_at` and `mono_ns`, so the stop latency (`control.applied` → last `cell.outcome{stopped}`), the grace outcome per harness (`ended_by`) and the decision latency (`decision.opened` → `decision.resolved`) are measured on every run by default, with no flag.
- **`engine.log`** (JSON lines, trace-correlated, `engine.py:569-600`): `control rejected` (HB-USR-002, the file name only), `stop applied` (HB-RUN-006/007), `decision opened` / `decision resolved` (`decision_id`, the code), `grace ended; terminating` (`cell_id`).
- **Questions an operator asks → source:** How long did the stop take? (`mono_ns` deltas.) Did the grace work for Copilot? (`ended_by` counts per harness.) Why did the run stop? (`stop_code`.) What is waiting on me? (`decisions` in status.) How much has the run spent? (`spend_tokens` on a `spend_cap` decision; the report's tokens after grading.)

## 16. Test plan: promise → test

### 16.1 Row 10's exit condition, clause by clause (plan `:145`, verbatim)

| # | clause (verbatim) | test (file · name) | red first against | label |
| --- | --- | --- | --- | --- |
| R10-1 | "a real process tree with a child that ignores termination is stopped within 30 s by the engine's clock, with outcome `stopped`" | `test_engine.py::test_stop_ends_a_tree_whose_child_ignores_termination_within_30s`. `fake_acp_agent.py` gains `{"child": "stubborn"}` (it starts a child that ignores CTRL events, and the agent ignores `session/cancel` and stdin EOF, and writes the child's pid). A real `bench stop` is run in-process. Assert: the last `cell.outcome{stopped}.mono_ns − control.applied.mono_ns ≤ 30e9`; `ended_by == "terminate"`; the child's pid no longer exists; the grace used is the profile's 10 s (the worst case) | no `bench stop` / control reader | real processes (D4) |
| R10-2 | "any open decision becomes `superseded (stop)`" | `test_engine.py::test_a_stop_supersedes_every_open_decision`: two open decisions (a blocked cell and a qualification gap), then a stop. Exactly one `decision.resolved{superseded (stop), option: null}` per id; no default applies later (the clock is advanced past the timeout) | no supersede | |
| R10-3 | "`bench status` shows `stopped` within 30 s (UXA-10)" | `test_status.py::test_status_shows_stopped_with_counts` (unit: the rows → `phase: stopped`, `outcomes.stopped`, `outcomes["not started"]`, `stop_code: HB-RUN-006`), and inside R10-1: `status.build` polled from the control write until `phase == "stopped"`, elapsed ≤ 30 s on `time.monotonic` | `PHASE` lacks `stopped` | |
| R10-4 | "Race: both orderings are forced deterministically (injected clock or barrier, no sleep), and each gives exactly one terminal decision state and one ledger event" | `test_engine.py`, pure `_Decisions`, **six tests, both orders of each pair**: (a) answer then timeout, (b) timeout then answer, (c) stop then timeout, (d) timeout then stop, (e) answer then stop, (f) stop then answer. Each asserts exactly one `decision.resolved` for the id, its `state`, and (a, b, f) the losing answer's `control.applied{rejected (already resolved)}`. Plus one engine-level test with an injected clock: the answer file dropped in tick N and the clock advanced past the deadline in tick N+1, then the reverse; no `sleep` | no `_Decisions` | D1 |
| US15-1 | "US-15: one test per default (blocked; …" | `test_engine.py::test_blocked_cell_default_continues_after_the_timeout`: a `blocked (auth)` cell → `decision.opened{blocked_cell, default: continue}`; no `cell.launch_intent` while open; the clock advanced past `decision_timeout` → `decision.resolved{default applied (timeout), continue}`; launching resumes; the blocked cell's outcome is unchanged | no decisions | |
| US15-2 | "… qualification gap → `skipped (decision)`; …" | `test_engine.py::test_qualification_gap_default_skips_the_combos_pending_cells`: a `model unavailable` cell of combo A → the default after the timeout → every pending A cell `cell.outcome{skipped (decision), decision_id}` with no intent; combo B cells launch | no decisions | |
| US15-3 | "… spend cap → stop)" | `test_engine.py::test_spend_cap_default_stops_the_run`: a cap below one cell's tokens (a fake `_meta.quota` usage) → `decision.opened{spend_cap, spend_tokens, spend_cap_tokens}`; the default after the timeout → `run.launch_stopped{HB-RUN-007}`; running cells `stopped`. **US15-3b:** `spend_tokens` equals Σ `normalize.totals` over the ended cells; a cell with no usage adds to `cells_unmeasured` | no cap | |
| CB | "Circuit breaker: its acceptance criterion is written in the design, with a red-first test" | §7 AC-CB-1..8; the seeded-revert table in §7 (`tests/mutations/stop.json`) plus the three new tests. Red observed per mutant before the slice commits | seeded reverts | D1 |
| R10-7a | "The existing power request (`host.keep_awake`, `engine.py:216/258`) stays held through stop …" (today `:218`/`:260`) | `test_engine.py::test_keep_awake_is_held_through_a_stop`: `keep_awake` monkeypatched to record `(flag, len(eng.active), eng.stopped)`; after a stop with a running cell the record is `[(True, 0, None), (False, 0, "HB-RUN-006")]`, so it is released only after every stopped cell's worker has ended | mutant: `host.keep_awake(False)` moved into `_stop_launching` | |
| R10-7b | "… and exception (test)" | `test_engine.py::test_keep_awake_is_released_when_the_run_raises`: `_check_budgets` monkeypatched to raise `RuntimeError` mid-run → `pytest.raises`, and the calls are `[True, False]` | mutant: `keep_awake(False)` moved out of `finally` | |
| TLC | "The TLC seeded variants still fail" | `python tools/check_models.py` (full, including the US-44 bounds): 22 of 22 `ok`, with `no_escalate` rejected by `StopReachesTerminal`; `tests/test_check_models.py` green (every target has a variant; every variant is seeded) | the spike (§8.2) | model check |

### 16.2 The other promises

| # | promise | test |
| --- | --- | --- |
| R21-1 | budget kill: `session/cancel` sent, stdin closed, the agent's shutdown record written before any terminate | `test_engine.py::test_a_budget_kill_lets_the_agent_write_its_shutdown_record` (the fake writes a file on stdin EOF; red on today's immediate `terminate`) |
| R21-2 | the kill fires at the grace end even after the turn ended | `test_engine.py::test_the_hard_floor_fires_after_the_turn_ended` |
| R21-3 | Copilot timeout: `session.shutdown` present and tokens recorded after a budget kill (R-21) | `test_engine.py::test_copilot_budget_kill_records_session_shutdown`, `@pytest.mark.credentials`: run by the Leader in a capture window (S6) |
| R10-5 | a stop during the workspace build: no spawn, outcome `stopped` | `test_engine.py::test_a_stop_during_the_build_never_spawns` |
| R10-6 | a stop between the ack and the send: no prompt | `test_driver.py::test_no_prompt_after_a_cancel_request` |
| R10-8 | a second stop is a no-op; one `run.launch_stopped` | `test_engine.py::test_a_second_stop_is_recorded_as_a_no_op` |
| R10-9 | a malformed or oversized control file: quarantined, logged, no row | `test_engine.py::test_a_malformed_control_file_is_quarantined` (Postel cases: an extra key, a missing key, 5 KiB, not JSON) |
| D-1 | `session/cancel` is a notification with `{sessionId}`, sent once, only while a prompt is in flight | `test_driver.py::test_cancel_sends_session_cancel_during_the_prompt` and `…_closes_stdin_during_the_handshake` |
| US15-4/5 | no decision with nothing pending; the loop waits for open decisions | `test_engine.py` (two tests) |
| CLI-1..4 | `bench stop` and `bench answer`: the file is atomic (no `.tmp` left), the refusals (unknown run, not running, bad decision, bad option), the exit codes | `test_cli.py` |
| P-1..3 | the plan records `decision_timeout`, `spend_cap_tokens` and `model_map`; `bench run` refuses a plan without `decision_timeout`; the confirmation prints both | `test_plan.py`, `test_cli.py` |
| PR-1..3 | `shutdown_grace_seconds` loaded and ≤ 10 (11 refused); `defaultMode` is `default` and equals the recording's effective mode (R-34 c4) | `test_profiles.py` |
| ST-1..3 | `bench-status/1`: `phase` values, `decisions` shape, the strict parse rejecting a free string in a decision | `test_status.py` |
| LC-1..5 | each replay rule in §8.3, with a seeded forbidden ledger | `test_lifecycle_conformance.py` |
| ERR-1 | HB-RUN-006/007 exist; `RUN_STOP_CODES`; every design-table code is pinned | `test_errors.py` |
| SK-1 | the skill's field list names every `bench-status/1` field | the existing skill-sync test, where one exists; otherwise a `test_status.py` assertion over the skill text |

### 16.3 Testing Strategy directives (the union)

| trigger | directive | here |
| --- | --- | --- |
| — | D0 hygiene | no dead code; the stale `assume:`/`getattr` at `engine.py:369-371` is removed (`TurnResult.last_update_seconds` exists, `driver.py:101`); ruff clean |
| T1 | D1 unit + mutation | `_Decisions`, the breaker, the stop precedence, the plan and profile validators; mutations in `tests/mutations/stop.json` (breaker, keep_awake, first-wins, the hard floor, cancel-before-send, the neutral outcomes), each killed by a named test (TOOL-B: the kill is re-derived, never only counted) |
| T2 | D2 property | the control-file parser: arbitrary JSON objects never raise and never apply an effect outside the closed set; the decision state machine: any interleaving of answer, timeout and stop gives exactly one resolution (a Hypothesis test if Hypothesis is installed; otherwise an exhaustive loop over the orders of the three events; the repo's choice) |
| T3 | D3 structure | the driver-only-ACP import lint (design D3) stays green: `session/cancel` lives in `driver.py` |
| T4 | D4 real infra | real files for the control directory (`os.replace`), real Job Objects and processes in R10-1, R21-1, R21-2 |
| T6 | D5-provider | `bench-status/1` as the skill's contract: the strict parse plus the skill text test |
| T7 | D6 schema + golden | `bench-control/1` and the new `events` kinds: golden rows in `test_lifecycle_conformance.py`; old-run fixtures (no new kinds) still replay |
| T8 | D7 mock fidelity | `FakeLauncher` + `fake_acp_agent.py` for cancel: paired with the ACP 1.5.0 schema (the message shape asserted against `CancelNotification`'s required keys) and with the live Copilot test (S6) |
| — | model check | TLC as in §8 |

## 17. Slice plan for W2-STOP-I

Codex `gpt-6-sol`, effort high (R-33: stipulated). Six slices of at most 55 minutes, each ending at a commit with its tests green and its mutants killed. Paths are only those STOP-I owns, plus S4/S5 if granted. **Red first** in every slice: each new test is observed failing, and the run is cited in the commit message.

| slice | content | tests (red first) | depends on | ends at |
| --- | --- | --- | --- | --- |
| 1 · seams and data | S1 (VIEWS's HB-VAL codes, verbatim) + HB-RUN-006/007 + `RUN_STOP_CODES` (`errors.py`); S2 + the `OUTCOMES` line (`status.py`, one commit); S3 `model_map` (`plan.py`); `decision_timeout`, `spend_cap_tokens`, the refusal of old plans, the plan flags and confirmation lines (`plan.py`, `cli.py`); the stale `getattr` removed. Skips whatever of S1–S3 is already on `main` | ERR-1, P-1..3, ST-1 (enums) | VIEWS's S1/S2 request text | commit: seams delivered (the plan's "S1–S3 by slice 2" is met by slice 1) |
| 2 · circuit breaker and power | AC-CB 4 (neutral outcomes); `tests/mutations/stop.json` breaker and `keep_awake` entries; R10-7b; the new breaker tests | CB table (seeded reverts observed red), R10-7b | 1 | commit: AC-CB proven |
| 3 · the grace (driver, profile, model) | `driver.CancelToken`, `session/cancel`, no prompt after a cancel; `shutdown_grace_seconds` (profiles, launcher, plan record); `EndGrace`/`kill_deadline`/`_check_kills`, `ended_by`, `end_grace` removed; `models/run_lifecycle.tla` refinement; `run-lifecycle-model.md` rows; R-34 c4 `defaultMode` | D-1, R10-6, R21-1, R21-2, PR-1..3; `check_models.py` full run (needs S5) | 1 | commit: the grace, and 22 of 22 variants |
| 4 · stop | control reader, `bench stop`, the stop sequence, the pre-spawn check, stop precedence, the replay rules for stop and control; `stopping`/`stopped` phase | R10-1, R10-3, R10-5, R10-7a, R10-8, R10-9, CLI-1..2, LC (stop, control) | 3 | commit: plan `:145` "Stop" clauses |
| 5 · decisions | `_Decisions`, the triggers, `SPEND`, `bench answer`, supersede, the loop condition, `decisions` in `bench-status/1` **and the skill in the same commit** (R-3) | R10-2, R10-4 (a–f + the engine-level pair), US15-1..5, CLI-3..4, ST-2..3, LC (decisions, skip), SK-1 | 4 | commit: "Race" and "US-15" clauses |
| 6 · proof | the full mutation pass over `tests/mutations/{engine,driver,status,cli,plan,stop}.json`; `python tools/check_models.py` (full); the proof figures for `docs/proof/phase2.md` handed to the Leader; S4 if granted | all; `pytest` default suite; ruff | 5 | commit: join-ready |

**At the join (Leader):** `git diff --stat` against the owned paths (R-44 c3); R21-3 in a capture window (S6); the `assume:` in §5 confirmed from the wave-1 ledger.

## 18. `driver.py`

**driver.py changed:** `CancelToken`; on a cancel, `_Channel.rpc` sends the ACP `session/cancel` notification (only while `session/prompt` is in flight) and closes stdin, from the worker thread; `run_turn` gains `cancel=` and does not write `session/prompt` after a cancel request. Nothing else changes: the handshake, the deny-all permissions, `set_model`, the usage capture and the error classification are untouched.

## 19. Open decision requests, flags and residuals

**Decision requests to the Owner** (question · default taken by this design · what breaks):
- **DR-1 · the spend cap's unit.** Should `spend_cap_tokens` be total tokens (the report's four buckets, from the same `normalize.totals`), given cost is `NA` by decision on subscriptions? · Default: tokens, checked per ended cell, unmeasured cells disclosed. · If the Owner wants USD, the cap needs the price list (`bench/prices.yaml`) and a cost basis per harness (Copilot's AI units are wave 3, R-15 Q6). US15-3 still holds, and only the measure changes.
- **DR-2 · the circuit breaker vs ADR-0007 §7.** The ADR says the breaker raises a decision (resume launches / stop; default stop). The built breaker only stops launching. · Default: keep the built behaviour for wave 2 and add an amendment note to ADR-0007 §7 (the Leader writes it at the join). · If the Owner wants the ADR behaviour, a fourth `decision_kind` (`circuit_breaker`, options `resume`/`stop`, default `stop`) is one more trigger row in §6.1 and one more test. Breaking change: the default then **kills** running cells after the timeout, where today they finish.

**Leader items:** S4, S5, S6 grants; S7 (`last_update` in status); the §5 `assume:` confirmed from the wave-1 ledger.

**Flagged:**
- whether each adapter honours `session/cancel` (measured by `ended_by` and S6);
- multi-decision interleavings are outside the TLC model (one abstract decision), and so is the combo skip (a queue filter, covered by the replay rule and US15-2);
- the stop bound for a cell in its workspace build (§5 `assume:`).

**Residuals (accepted):** a cell's agent can write a control file (STRIDE row 1); the spend cap can be overshot by the running cells; `bench stop` on a not-running run is refused rather than queued until resume (phase 5).

**Deviations recorded:**
- ADR-0007 §7 (DR-2).
- The design-slice skill's rollup step (`docs/security/threat-model.md`, `privacy-review.md`) is **not run**: the brief limits this track to the design, the docs index and audit files, and `docs/notes/`. The STRIDE rows above feed the next rollup run (Leader or STOP-I).

**Confidence ledger:**

| claim | evidence | label |
| --- | --- | --- |
| The refinement keeps all 16 invariants and 5 properties at small bounds, and 22 of 22 variants are rejected | the spike run, §8.2 | Verified |
| … and at the US-44 bounds (all 16 invariants), and the full run passes (27 `ok` lines, exit 0) | the spike's full run, §8.4 | Verified |
| ACP `session/cancel` shape and `cancelled` stop reason | SDK 1.5.0 schema, read | Verified |
| Claude Code's effective mode is `default` | `tests/test_driver.py:692-700` recording | Verified (by citation) |
| The stop fits in 30 s outside HB-RUN-002 | the step table, §5 | Inferred until R10-1 runs |
| The workspace-build step is short | none yet | `assume:` (§5) |
| Each adapter honours the cancel | none | Flagged |

## 20. Conformance notes

- **ADR-0007:** §3 (control files, apply once, first resolution wins): implemented as written. §4 (monotonic deadlines): yes. §5 (stop within 30 s): yes, via R-21's grace. §7: deviation (DR-2).
- **ADR-0006:** additive `events` kinds and fields; no new fact table.
- **ADR-0011:** C4 (`bench-status/1` schema-bound, no free strings) extended; C6 (idempotency keys) for control uuids.
- **R-3:** the schema stays `/1`; the skill changes in the same commit.
- **R-37:** a scripted-user question is never a decision request; the end-of-turn kill and the grace are untouched by it.

## Gate record

To be filled after the three-lens gate (Patterns Expert, Simplifier, Test Architect; the Test Architect holds the hard veto).

## Status

| | |
| --- | --- |
| **Completed** | the row-10 design: stop, decisions, spend cap, circuit-breaker acceptance, the R-21 grace refinement (spiked), R-34 c4, the STOP-I slice plan |
| **Remaining** | W2-STOP-I (implementation); the Owner's DR-1, DR-2; the Leader's S4–S7 |
| **Best next action** | dispatch W2-STOP-I slice 1 (Codex `gpt-6-sol`) on this design, after the gate |

---
**Handoff:** → `/implement` (W2-STOP-I).
