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
  apply-once control files that the engine applies on its own thread. A stop sends ACP session/cancel, closes stdin,
  waits a profile grace of at most 10 s, then terminates the Job Object, so every running cell is `stopped` within 30 s
  (R-21, UXA-10), and a `run.stopped` fact is recorded. Three decision kinds (blocked cell, qualification gap, spend
  cap) pause launching; each request is resolved exactly once; the plan's decision_timeout applies the default. The
  built breaker gets its acceptance criterion and falsifying reverts. The grace is a TLC-checked refinement of the
  terminate step (spike: 22 of 22 variants rejected; the US-44 bounds pass). Revision 2, after the three-lens gate.
---

# Design: stop, decisions and the circuit breaker (phase 2, row 10)

**Track:** W2-STOP-D (plan version 4, `docs/coordination/coordination-finish-harness-bench.md:157`). **Implemented by:** W2-STOP-I (Codex `gpt-6-sol`, effort high; slice plan in §17). **Author:** Claude Opus 5.5 (`claude-opus-5-5`), 2026-09-25. **Grounded at:** `main` `5feece0`. **History:** revision 1 is `0b20b21` (before the gate); revision 2, this one, follows the three-lens gate (§21).

**Rulings this design carries:**
- R-3: the `bench-status/1` fields.
- R-9: the night window.
- R-15: the "not recorded" validity (VIEWS).
- R-21: the graceful end, inside the 30 s bound.
- R-33: stipulated models.
- R-34 c4: `defaultMode`.
- R-37: one prompt per cell; the scripted user is not a decision.
- R-38: the smoke run waits for W2-STOP.
- R-44: `stopped` and `decisions` join `bench-status/1`.

---

## 1. Responsibility

One responsibility: **let an unattended run end or pause on purpose, and never stall.**

1. `bench stop <run_id>` stops a running run:
   - no new launch;
   - every running cell's process tree is gone within 30 s of the engine's clock, with outcome `stopped`;
   - every started cell is archived;
   - any open decision becomes `superseded (stop)`;
   - `bench status` shows `stopped` (US-45, UXA-10).
2. The engine raises a **decision request** for a blocked cell, a qualification gap or the spend cap. Launching pauses while one is open. The plan's `decision_timeout` applies the default (US-15, UXA-9). P1 answers with `bench answer`. Each request is resolved exactly once (ADR-0007 §3).
3. The **circuit breaker** is already built (`engine.py:51`, `:196-201`). It gets a written acceptance criterion and falsifying reverts (§7).
4. The **R-21 graceful end** applies to every engine kill (stop, budget, host sleep): ACP `session/cancel`, stdin closed, a bounded grace, then `TerminateJobObject`.

**Not this component:**
- resume (phase 5; ADR-0007 §4's deadline restart is not built);
- the scripted user (R-37: a tool call inside the one prompt, never a decision request);
- the R-15 "not recorded" validity state (W2-VIEWS);
- the model gateway's spend enforcement (ADR-0009, wave 3).

**Boundaries:**
- **Inputs:** control files under `runs/<run_id>/control/`; cell outcomes and per-cell token totals (from the engine's own workers); the plan's parameters; the profile's grace.
- **Outputs:** `events` rows (ledger), process kills, `bench-status/1` fields.
- **Owned and borrowed:** it owns the stop and decision state. It borrows the cell lifecycle (phase 1) and the ledger (ADR-0006).

## 2. Delivery phasing and seams

Row 10 is on the critical path: STOP-D → STOP-I → USER-W → the smoke run (plan `:183`, R-38). The smoke run needs stop and the timeout (plan `:235`).

| seam | from → to | what | resolution |
| --- | --- | --- | --- |
| S1 | VIEWS → STOP-I | new HB-VAL codes in `errors.py` `RUN_CODES` | STOP-I slice 1, **verbatim from VIEWS's seam request**. STOP-I's own codes are `HB-RUN-006` and `HB-RUN-007` (§4.9). They use a different prefix, so the codes never collide, whichever lands first. If the Leader grants S1 to VIEWS and it is on `main` first, slice 1 skips it (check: the codes are present on `main`) |
| S2 | VIEWS → STOP-I | the `VALIDITY` tuple (`status.py:33-34`) | STOP-I slice 1. STOP-I's own `OUTCOMES` change (`:32`) is an adjacent hunk, so **slice 1 lands S2 and the `OUTCOMES` line in one commit**. If S2 is already on `main`, slice 1 rebases on it first |
| S3 | VIEWS → STOP-I | `model_map` frozen in the plan's task record | STOP-I slice 1. `plan.build_plan` adds `"model_map"` (from `task.yaml`; a dict or null) to `tasks[<id>]` (`plan.py:229`). The task folder is inside the version hash, so no new hash field is needed |
| S4 (new) | STOP-I → VIEWS | `views._validity` returns `("not started", None)` for the outcome `skipped (decision)`. One line, at `views.py:245` | Without it, a skipped cell reads `invalid (no model call)`: a wrong label (IO rule). Request to the Leader: grant the line to STOP-I, or VIEWS takes it. STOP-I's tests read status, which does not depend on it |
| S5 (new) | STOP-I → Leader | `tools/check_models.py` gains the `VARIANTS` line `"no_escalate": ("prop", "StopReachesTerminal")` and a second witness, `NoGraceState` (expected violated). **Both witnesses run inside the scripted `main()`**, so the gate fails when either stops being violated; today `WITNESS` is a single constant (`check_models.py:68`; TA N3). `tests/test_check_models.py` gains the **reverse** test: every `BUG = "x"` or `BUG # "x"` literal in the `.tla` must be a `VARIANTS` key (TA M5b) | STOP-I does not own these paths. Without them, the new variant never runs and nothing notices (class MOD-A). **The grant is a precondition of slice 3's commit**: without it, slice 3 cannot claim the TLC clause of plan `:145` (TA N2) |
| S6 (new) | STOP-I → Leader | the live Copilot grace test (R21-3, `@pytest.mark.credentials`) | A live turn on the GitHub login, run in a Leader capture window (R-9 rule 1). It must be **red on the commit before slice 3 and green after it, in the same window** (TA M9). Until then the claim is Flagged in the Proof Pack |
| S7 (flag) | plan `:132` → STOP-I | "`last_update` in `bench status`" was a wave-1 seam to W2-STOP; the version-4 STOP-I row does not carry it | Leader: confirm it is dropped, or add it. Not designed here |

**Mock-substitutable seams** make every clause testable with no model turn:
- the `Launcher` Protocol: a `FakeLauncher` over `tests/fake_acp_agent.py`;
- one injected engine clock (`EngineConfig.clock`, default `time.monotonic`);
- a tick hook (`EngineConfig.on_tick`, default `None`; §6.2);
- the control directory: plain files.

## 3. Data model

**Bounded context:** Run Execution (ADR-0006, ADR-0007). **Ubiquitous language** (the spec glossary, `harness-bench.md:190-218`): run, cell, execution outcome, decision request, spend cap, plan.

**Aggregates.** Each one is bounded by one invariant and referenced by id only.

| aggregate (root) | invariant it protects | model invariant |
| --- | --- | --- |
| **Run stop** (the run, `run_id`) | a run stop is recorded at most once; after it, no cell launches and no decision opens | `NoLaunchAfterStop`, `ControlAppliedOnce`, `StoppedNeverRelaunched` |
| **Decision request** (`decision_id`) | it is resolved exactly once; while any request is open, no cell launches | `DecisionResolvedOnce`, `NoLaunchWhileDecisionOpen` |
| **Control message** (`uuid`) | it is consumed at most once, and recorded before its file is removed | `ControlAppliedOnce` |

The cell aggregate (phase 1) gains two terminal outcomes: `stopped` and `skipped (decision)`.

**Durable representation.** The new rows are append-only facts in the existing `events` segment (ADR-0006). There is no new table, no new segment and no migration. Every new kind is additive, so old runs have none of them and read unchanged.

**Grain and fields.** One row per fact (PE-1, S-1): *launching stopped* and *run stopped* are two facts, so they are two kinds.

| kind | one row is exactly one … | fields (enums, ids and ints only; no free text from a cell) | writer | compute reader |
| --- | --- | --- | --- | --- |
| `control.applied` | **consumed** control file, keyed by `uuid`. The grain is "consumed", because rejections are rows too; the name is kept for the model mapping | `uuid`; `control` (`stop` \| `answer`); `decision_id` (answer) or null; `effect` (`applied` \| `rejected (already resolved)` \| `rejected (invalid)` \| `no-op (already stopped)` \| `no-op (run ending)`) | engine thread | `lifecycle.replay` (ControlAppliedOnce); phase-5 resume (rebuilds the dedup set from these rows) |
| `run.launch_stopped` (exists) | stop of launching, **at most one per run** (unchanged, `engine.py:267-274`) | `code`, `reason` | engine thread | `status.stop_code` (R-3); replay NoLaunchAfterStop |
| `run.stopped` (new) | **run stop, at most one per run** (the model's `ApplyStop`) | `code` (`HB-RUN-006` operator, `HB-RUN-007` spend cap); `decision_id` or null (a stop that came from a decision) | engine thread | `status.phase`, `status.text`, replay |
| `decision.opened` | decision request, keyed by `decision_id` (`D1`, `D2`, … in opening order) | `decision_id`; `decision_kind` (`blocked_cell` \| `qualification_gap` \| `spend_cap`); `subject` (a harness, a combo id, or the `run_id`); `cause_code`; `options` (a list of enums); `default` (enum). For `spend_cap` also `spend_tokens` and `cells_unmeasured` (a snapshot). The timeout and the cap are **not** copied, because both are in the frozen plan (S-8) | engine thread | `status.decisions`, the skill, replay |
| `decision.resolved` | resolution of one decision (**exactly one per `decision_id`**) | `decision_id`; `state` (`answered` \| `default applied (timeout)` \| `superseded (stop)`); `option` (null when superseded). The answering control is derived: the one `control.applied{decision_id, effect: applied}` (S-9) | engine thread | `status.decisions`, replay |
| `cell.outcome` (exists) | the cell's terminal outcome (still one per cell, HB-LED-003) | the outcome gains `stopped` (cause null) and `skipped (decision)` (cause null, plus `decision_id`; **the cell's first and only row**) | engine thread | views (through S4), status, grading |
| `attempt.process_ended` (exists) | end of the cell's process | gains `ended_by`: `exit` (the job emptied with no kill requested), `grace` (a kill was requested and the job emptied before any `TerminateJobObject`), or `terminate` (a `TerminateJobObject` was issued, by the engine's floor or by the worker's `_end_process`). It is derived from one flag, `a.terminated`, set under `a.lock` by whoever issues the call (PE-3) | engine thread | the run record; the R-21 measurement per harness |

**Additivity.** `spend_tokens` on `decision.opened` is a **point-in-time snapshot**: the evidence for opening the request. It is non-additive and is not a stored measure. Every count in `bench-status/1` is derived.

**History rule.** Every row is append-only; nothing is updated. A decision's current state is derived from its rows and never stored.

**Derive, don't store** (DM7):
- the run phase (`starting`, `running`, `stopping`, `stopped`), each decision's state and the time to default are derived by `status.build` from `events` and the plan;
- the run's spend is an in-memory running sum on the engine thread, fed by one `SPEND` inbox item per ended cell (the `STOP` item's pattern, `engine.py:47,174`). It is not persisted. Each cell's tokens can be derived from its archived native record by `normalize.totals`, so a rebuild is a re-read.

**Append-only invariants, enforced and tested.** `lifecycle.replay` gains the rules in §8.3. Each has a seeded-ledger test that attempts the forbidden sequence.

**Migration.** None: the new kinds and fields only add. `bench run` refuses any plan whose `parameters` lack a key of `DEFAULT_PARAMETERS` (HB-USR-002, "plan predates <keys>; plan a new run"). So no default is guessed into a frozen plan, and one check covers both new keys (S-12).

## 4. Contracts

### 4.1 `bench stop <run_id>` (the control channel; the model's `controlFile`)

- It writes `runs/<run_id>/control/<uuid>.json` as `<uuid>.json.tmp`, then calls `os.replace` (ADR-0007 §3). The `uuid` is `uuid.uuid4().hex`.
- It refuses, with exit 1, in two cases:
  - the run is unknown (HB-USR-001);
  - the run's lock is not held (HB-USR-002: "run <id> is not running (<completion>); nothing to stop").
- Otherwise it prints `stop requested (<uuid>). bench status <run_id> shows stopped within 30 s.` and exits 0. It does not wait (YAGNI).

**The control file, `bench-control/1`.** Strict: ≤ 4 KiB, exactly these keys, and **the file-name stem equals `uuid`** (PE-14).

```json
{"schema": "bench-control/1", "uuid": "<32 hex>", "control": "stop" | "answer",
 "decision_id": "D<n>" | null, "option": "<option enum>" | null, "requested_at": "<UTC ISO>"}
```

**The engine side, every loop tick** (engine thread, `loop_interval` 0.2 s):
- It lists `control/*.json`. A `*.tmp` file is never read.
- It orders **stop files first**, then answers by (`requested_at`, `uuid`).
- For each file:
  - **An `OSError`** on read, rename or delete (for example, a file held by antivirus or the indexer): the file is left and retried next tick (PE-9).
  - **A parse or schema failure:** the file is renamed `<name>.rejected` (kept as evidence) and logged with HB-USR-002 and the file name only. It gets no ledger row.
  - **A `uuid` already in the dedup set:** the file is deleted, with no row.
  - **Otherwise:** the engine appends `control.applied` with its effect, applies the effect (§5, §6), then deletes the file. A failed delete after the row is harmless, because the dedup set skips the file next tick.
- The dedup set is an in-memory `set()` that starts empty (Simplifier N-1). `simplify:` a run's `events` never exist before its engine starts (`engine.py:211-212`), so there is nothing to rebuild. **Upgrade trigger:** phase-5 resume, which rebuilds the set from the `control.applied` rows.
- **After grading, just before `run.completed`**, one final pass records each remaining file as `control.applied{effect: no-op (run ending)}` and deletes it (PE-10). A `bench stop` sent during grading, while the lock is still held (`engine.py:243-246`), is therefore recorded too (Simplifier N-2). A control never disappears unrecorded.

### 4.2 `bench answer <run_id> <decision_id> <option>`

- It is the coordinator's only writer. ADR-0007 §10 denies the `/start-benchmark` session access to `runs/**`.
- At write time it checks that the decision exists, is open and offers `option`. If not, it refuses with HB-USR-002 and names the valid options.
- It then writes an `answer` control file, as in §4.1.
- The engine re-checks when it applies the file. If the decision was resolved in between, the row is `control.applied{effect: rejected (already resolved)}`.

### 4.3 Plan parameters (`plan.py:41-52`, US-6)

Both keys go in `DEFAULT_PARAMETERS`, so `build_plan` merges them (`plan.py:220`).

| parameter | default | meaning |
| --- | --- | --- |
| `decision_timeout` | `1800` s (spec US-15: "default 30 minutes") | how long an open decision waits before its default applies, on the engine clock |
| `spend_cap_tokens` | `null` (no cap) | the run's cap on Σ tokens over ended cells (§6.3). **The unit is an open decision request, DR-1** |

`bench plan` gains `--decision-timeout-minutes` and `--spend-cap-tokens`. The confirmation output prints `decision timeout: 30 min; spend cap: none`, because US-6 names both.

### 4.4 The profile datum (R-21 c1)

- Each `bench/profiles/<harness>.yaml` gains `shutdown_grace_seconds`: a number with `0 < x ≤ 10`. `profiles.load` refuses a larger value (HB-USR-002).
- All three profiles start at `10`. No harness's shutdown time has been measured yet, and 10 is the phase-1 `end_grace` (`engine.py:84`).
- `simplify:` one ceiling for all harnesses. **Upgrade trigger:** a harness whose `ended_by` shows `terminate` on routine ends (its shutdown needs longer, measured), or a measured shorter need.
- `ProfileLauncher` and the `Launcher` Protocol gain `shutdown_grace: float`. `plan.profile_record` records it, so a run reads its own dimensions (US-26).
- `EngineConfig.end_grace` is removed. One grace serves both the end of a turn and every kill.

### 4.5 The driver contract (ACP `session/cancel`)

**Established (Verified).** Source: ACP SDK 1.5.0 `schema/schema.json`, the pinned `@agentclientprotocol/sdk` in `.tools/harness/node_modules`.
- `CancelNotification` is `x-method: session/cancel`. It is a notification, so it has no id.
- Its params are `{sessionId}`, which is required.
- The agent "MUST" answer the pending `session/prompt` with `stopReason: "cancelled"`.
- The agent must answer every pending `session/request_permission` with the outcome `cancelled`.

**Not established (Flagged).** Whether `claude-agent-acp` 0.81.2, `codex-acp` and Copilot 1.0.89-1 honour it. The design does not depend on it: the hard kill fires at the grace end regardless. The per-harness answer is measured by `ended_by` (§3) and by the Copilot live test (S6).

**The mechanism: a `threading.Event`** (S-5). An Event is level-triggered, so it also removes PE-5's lost-wakeup hazard.
- `run_turn(..., cancel: threading.Event | None = None)`. The default keeps today's behaviour for every existing caller.
- `_Channel.rpc` polls its inbox with `timeout=min(wait, 0.2)`.
- The first time `rpc` sees `cancel.is_set()`, it acts on the **worker** thread (the engine thread never writes a pipe):
  - if `session/prompt` is in flight, it sends `{"jsonrpc": "2.0", "method": "session/cancel", "params": {"sessionId": sid}}`;
  - in every phase, it closes stdin.
- After a cancel, `_Channel.send` **drops writes instead of raising `_Eof`** (PE-6). So a late permission request does not end the read loop. The loop keeps reading until one of three things happens:
  - the prompt's response arrives (`stopReason: cancelled`, with the usage it carries);
  - EOF;
  - the engine's kill.
- `run_turn` checks `cancel.is_set()` immediately before it writes `session/prompt`, and does not send the prompt if a cancel was requested. This is the model's `SendPrompt` guard, `~killRequested[c]`.
- The poll adds at most 0.2 s, far inside the 30 s bound.
- **Classifying the cancel.** `stopReason: cancelled` is not a completed stop reason (`engine.py:50`). The outcome comes from `kill_reason`: `stopped`, `timed_out` or `failed (host suspended)`, never `adapter crash` (§16, R21-4).

### 4.6 `bench-status/1` additions (R-3, R-44)

The schema stays `/1`: under R-3, the producer and its only consumer move in one commit, and nothing stores a status document. `status.parse` stays strict.

| field | change |
| --- | --- |
| `phase` | The closed enum gains `stopping` and `stopped`. **`stopping`:** a `run.stopped` row exists and some launched cell has no outcome. **`stopped`:** a `run.stopped` row exists and every launched cell has an outcome |
| `outcomes` keys | `OUTCOMES` gains `stopped` and `skipped (decision)`. `not started` already exists |
| `decisions` | a list of `{decision_id, decision_kind, subject, cause_code, options, default, state, default_in_s}`. `state` is one of `open`, `answered`, `default applied (timeout)`, `superseded (stop)`. `default_in_s` is a non-negative int while the request is open, else null; it is computed from `decision.opened.recorded_at` + the plan's `decision_timeout` − now. It is for display only: the engine's deadline is on its own clock. `subject` matches the harness names, the combo grammar, or `RUN_ID`. No free strings (ADR-0007 §10, boundary B2) |
| `stop_code` | unchanged (R-3): the `run.launch_stopped` code. If the breaker fired before a `bench stop`, it shows the breaker's code; the run-stop code is shown by `phase` and the text line |

**Text form** (`status.text`). UXA-7 requires the subject, the cause and an action:
- `Run <id>: stopped (HB-RUN-006). <n> stopped, <m> never started, <k> ended before the stop.`
- `Run <id>: stopping. <r> cells still ending.`
- `Decision D1 · blocked cell · claude-code · HB-CELL-202 · options continue | stop · default continue in 29 min. Answer: bench answer <run_id> D1 <option>`

**The `/start-benchmark` skill** (`.claude/skills/start-benchmark/SKILL.md` and `.agents/skills/start-benchmark/SKILL.md`):
- Its field list and reading rules change **in the same commit as every `bench-status/1` change**, in slices 1, 4 and 5 (R-3 c3; TA M6).
- It relays each open decision: id, kind, subject, cause code, options, default and time to default. It never relays cell text.
- It writes the answer with `bench answer`. When P1 says "stop", it runs `bench stop`.

### 4.7 R-34 condition 4: `defaultMode`

**Decision: declare `default` outright** in `bench/profiles/claude-code.yaml` (`"defaultMode": "default"`), and keep recording `permission_mode_effective`.
- **Evidence (Verified):** the session reports `default` today, in the `claude-code-x1.jsonl` recording (`tests/test_driver.py:692-700`). The stderr fallback line is at `tests/test_allowlist_classes.py:127`.
- **Why not `dontAsk`:** a later build that honours `dontAsk` would refuse an unlisted tool silently, with no `session/request_permission`. The driver would then count 0, and US-14's control would pass vacuously on the very asymmetry R-34 found.
- **Red-first:** `tests/test_profiles.py:266` asserts `dontAsk` today; the new assertion is `default`, and it is red first. A second test compares the declared mode with the recording's effective mode.
- **Blast radius:** the profile hash changes, so plans made after this differ from the wave-1 baseline's `profile_hash`. Behaviour is the same, because the effective mode does not change. The run record says so.

### 4.8 Consumed contracts

| contract | source | confidence |
| --- | --- | --- |
| the ACP `session/cancel` notification; `stopReason: cancelled` | `@agentclientprotocol/sdk` 1.5.0 `schema/schema.json` | Verified (read) |
| each adapter honours `session/cancel` | none | Flagged; not depended on |
| `TerminateJobObject` kills the whole tree | spike N2 (`phase1-walking-skeleton.md:127`); `procs.py:164` | Verified (phase 1) |
| `os.replace` is atomic within a directory on NTFS | ADR-0007 §3 | Verified (phase-1 design) |
| every ledger row carries `mono_ns` from `time.monotonic_ns`: real time, never the injected clock | `ledger.stamp` (`ledger.py`) | Verified (read) |

### 4.9 Error codes (`errors.py`, STOP-I)

| code | meaning |
| --- | --- |
| HB-RUN-006 | run stopped by the operator (`bench stop`, or a decision answered `stop`): running cells stopped, no new launch |
| HB-RUN-007 | spend cap reached: the run stopped (the `spend_cap` default or answer) |

HB-USR-001 and HB-USR-002 are reused for CLI refusals and malformed control files. The circuit breaker keeps its built code, the third failure's cell code (`engine.py:199`).

## 5. The stop sequence and its 30-second budget

**On the engine thread, in one tick, for a stop file:**
- If a `run.stopped` row already exists, the engine writes only `control.applied{effect: no-op (already stopped)}`.
- Otherwise it takes these steps in order:
  1. append `control.applied{uuid, control: stop, effect: applied}`;
  2. call `_stop_launching("HB-RUN-006", "bench stop")`. It writes `run.launch_stopped` only if launching was not already stopped, so R-3's `stop_code` stays meaningful;
  3. append `run.stopped{code: HB-RUN-006}`, the model's `ApplyStop`. It is written whether or not launching was already stopped (S-1, PE-1);
  4. for every open decision, append `decision.resolved{state: superseded (stop)}`;
  5. for every active cell **whose turn has not ended**, call `_kill(a, "stop")`. It sets `kill_reason` (the first reason wins), sets `kill_deadline = clock() + shutdown_grace`, and sets `a.cancel`. A cell with no process yet gets `kill_reason` too, so its worker never spawns (§11).

**A turn that ended first keeps its own outcome** (PE-2, S-6).
- `a.ended`, set under `a.lock` (`engine.py:419-420`), is the linearization point, and `_kill` keeps its `ended` guard (`engine.py:290`).
- Such a cell is already in `_end_process`, which closes stdin and waits the same `shutdown_grace` before it terminates. So it ends at most one grace after the stop.
- It is recorded `completed` (or its own cause), never `stopped`.

**The hard floor.** On every later tick, `_check_kills(clock())` terminates each cell that is past its `kill_deadline`, still has a live job, and has not ended its turn. It sets `a.terminated` under `a.lock` (R-21: "the kill still fires at the bound regardless").

**The worker then:**
1. waits in `_end_process` until `min(its own end deadline, a.kill_deadline)`: one deadline, one owner (PE-3);
2. confirms the job is empty;
3. records `attempt.process_ended{ended_by}`;
4. with `kill_reason == "stop"`, records `cell.outcome{stopped}` **without** the provider-error scan. A stop takes precedence over every cause: the spec says `stopped`;
5. archives the cell.

| step | bound | source |
| --- | --- | --- |
| file written → applied | ≤ `loop_interval` + one drain (0.2 s + 0.2 s) | `engine.py:224-236` |
| applied → `TerminateJobObject` | ≤ `shutdown_grace_seconds` ≤ 10 s. The kills run **concurrently across cells** (one deadline each, all set in the same tick), so N cells take 10 s, not 10 × N | R-21 c1 |
| terminate → job empty (confirmed) | milliseconds on the phase-1 evidence; unbounded only in the HB-RUN-002 defect case | spike N2; `engine.py:447-454` |
| confirmed → `cell.outcome{stopped}` appended | the stderr drain join ≤ 5 s (the pipe closes with the tree), an immediate `cp.wait`, two records | `engine.py:423-435` |
| **total, worst case outside HB-RUN-002** | ≤ 0.4 + 10 + 5 + ε ≈ 16 s, inside 30 s | Inferred; R10-1 measures it on the ledger's `mono_ns` |

**A cell still building its workspace** has no process tree. Its worker checks `kill_reason` after each build step and before the spawn, then records `stopped` with no process.
- `assume:` a single workspace-build step (a local clone, a pack install) takes much less than 20 s on this host.
- **Confirm:** `cell.workspace_built.mono_ns − cell.launch_intent.mono_ns` in the wave-1 exit run's ledger. The Leader reads it at the STOP-I join.
- **Breaks:** a stop during a slow build shows `stopping` past 30 s, and the ledger shows it. The fix is a cancel hook in `workspace.py`, which STOP-I does not own.

**After the last active cell's worker exits:**
1. grading runs on the terminal cells (US-45);
2. the final control pass runs (§4.1);
3. `run.completed` is written;
4. `bench run` exits 3, and unlaunched cells stay `not started`.

The same kill path (grace, then the hard floor) serves the budget kill (`timeout`) and host sleep (`host_suspended`). A broken ledger (`aborted`) uses it too, though nothing is recorded then.

## 6. Decision requests (US-15)

### 6.1 Triggers, options, defaults

A decision opens on the engine thread when a `cell.outcome` or a `SPEND` item is processed. It opens only when it can change something, and at most once per (`decision_kind`, `subject`, `cause_code`). The cause is in the key so that a `blocked (permission)` on a harness does not hide a later `blocked (auth)` on the same harness, which is the expired login PE-4 exists for (Simplifier N-3):
- The two pending-cell kinds (`blocked_cell`, `qualification_gap`) open only while launching is not stopped for **any** reason (breaker, disk floor, `build_changed` or a stop), and only while affected cells are pending (S-4, PE-13, TA M8).
- `spend_cap` opens even after a launch stop, because running cells still spend.
- No decision opens after a run stop (model `RaiseDecision` guard `~stopApplied`).

| `decision_kind` | trigger | `subject` | options (closed enum) | default (on timeout) | effect of the default |
| --- | --- | --- | --- | --- | --- |
| `blocked_cell` | a `cell.outcome` whose cause is `blocked_auth` (HB-CELL-202) or `blocked_permission` (HB-CELL-201) | the **harness** (PE-4): one expired login blocks every cell of that harness, so it costs one wait, not N × 30 min | `continue`, `stop` | `continue` | none: blocked cells keep their `blocked (…)` outcome, and launching resumes |
| `qualification_gap` | a `cell.outcome` whose cause is `model_unavailable` (HB-CELL-116: the combo's pinned model is not served, ADR-0003) | the combo id | `skip_combo`, `stop` (S-2: `continue` would only relaunch cells that fail the same way) | `skip_combo` | every pending cell of that combo gets `cell.outcome{skipped (decision), decision_id}` and leaves the queue |
| `spend_cap` | Σ run tokens ≥ `spend_cap_tokens` after a `SPEND` item | the `run_id` | `stop`, `continue` | `stop` | a run stop with code HB-RUN-007 (§5), recorded as `run.stopped{decision_id}` |

- "Blocked cell" and "qualification gap" are this design's reading of US-15 against the closed cause list, recorded in `docs/notes/stop-decision-calls.md` (call 1).
- An answer of `stop` on any decision is an operator stop (HB-RUN-006, `run.stopped{decision_id}`).
- An answer of `continue` on `spend_cap` disables the cap for the rest of the run.

### 6.2 Tick order and exactly-once resolution

**The engine thread runs each tick in this order:**
1. `on_tick(n)` (tests only);
2. drain;
3. **controls** (stops, then answers);
4. **expire decisions:** when `clock() ≥ opened_at + decision_timeout`, append `decision.resolved{default applied (timeout)}` and apply the default's effect;
5. budgets;
6. kill deadlines;
7. sleep and disk checks;
8. launch: `while pending and not stopped and not broken and no decision open and len(active) < parallelism`.

**Three rules follow from this order:**
- **The loop runs while any decision is open**, as well as while cells are pending or active. So an open request is always resolved (model liveness `DecisionEventuallyResolved`; UXA-9).
- **A control and an expiry in the same tick:** the control wins, because controls come first. A test pins this (TA M3).
- **Exactly-once resolution by a state guard** (PE-15). One method, `_resolve(decision_id, state, option)`, returns without a row when the decision is already resolved. Every path calls it: answer, timeout and supersede. The losing answer is visible as `control.applied{effect: rejected (already resolved)}`.

**One clock** (PE-8). `EngineConfig.clock` is the single source for every **engine-thread** deadline: budgets (`prompt_mono`), `kill_deadline` and decision deadlines. The worker's own wait in `_end_process` stays on `time.monotonic`, so a test with a frozen injected clock never hangs in it (Simplifier N-4). The engine's hard floor still bounds that wait, because it terminates at `kill_deadline`. Only `ledger.stamp` keeps the real `mono_ns`. So a test that injects the clock must not measure on `mono_ns` (TA residual), and R10-1 uses the real clock.

**The state machine.** The decision logic is `_Decisions` in `engine.py`, a **Functional Core**: its methods `open`, `answer`, `expire(now)` and `supersede_all()` return the rows to append and do no I/O. The engine loop is the Imperative Shell.
- `simplify:` one class in `engine.py`, not a new module (STOP-I owns no new file).
- **Upgrade trigger:** a second consumer of the decision logic.

### 6.3 Spend

**A cell's tokens** = Σ over `normalize.BUCKETS` of `normalize.totals(profile.usage_source, extraction, turn_usage)` (`normalize.py:28,75`). That is the report's own definition, so there is no second one.
- The worker computes it from the extraction it already reads for the provider-error scan (`engine.py:463-466`): read once, used twice.
- The worker sends `SPEND{cell_id, tokens | null}` before its outcome.
- `null` means not recorded (for example, Copilot with no `session.shutdown`, R-21 c2). It adds to `cells_unmeasured`, never to the sum.
- A stopped cell sends no `SPEND`.

**Residual, disclosed at confirmation.** With `usage_source: native_record`, tokens are known only when a cell ends, so the cap is checked per ended cell. A run can pass the cap by up to what its running cells spend, and the cap is blind to unmeasured cells. `bench plan` prints: `spend cap: <n> tokens, checked when each cell ends; cells whose usage is not recorded are not counted`.

## 7. The circuit breaker: acceptance criterion

**What is built:** `CIRCUIT_BREAKER = 3` (`engine.py:51`) and the streak in `_after_append` (`engine.py:193-201`). It is a **one-shot breaker (a fuse)**: it trips open and has no manual reset. ADR-0007 §7's decision request is the manual-reset half, and DR-2 defers it (PE-11).

**Existing tests:** `test_the_circuit_breaker_stops_launching_once` (`tests/test_engine.py:405`), `…_fires_at_its_threshold_not_before` (`:411`), and `test_a_success_resets_the_infrastructure_streak` (`:838`).

**AC-CB (the acceptance criterion):**
1. **Fires.** When the third *consecutive* counted `cell.outcome` is appended (in ledger append order), the engine thread appends `run.launch_stopped{code: <that cause's code>, reason: "circuit breaker: 3 consecutive infrastructure failures"}`, and no `cell.launch_intent` follows it. **Counted** means the cause `invalidates` (attribution `infrastructure` or `benchmark`, `errors.py:39-42`) and is not `model_unavailable`.
2. **Not before.** Two consecutive counted outcomes never stop launching.
3. **Resets.** An outcome with no cause (`completed`) or with a non-invalidating cause (attribution agent, harness or none) sets the streak to 0.
4. **Neutral outcomes (new).** Three outcomes neither count nor reset:
   - `stopped`;
   - `skipped (decision)`;
   - `failed (model unavailable)`. The qualification-gap decision owns an unserved combo; without this rule, that combo's running cells would trip a whole-run stop that US-15 does not want (S-3).
5. **Running cells continue.** The breaker kills nothing and writes no `stopped` outcome.
6. **Once.** At most one `run.launch_stopped` per run. A breaker after any launch stop writes nothing.
7. **End state.** The run ends with `run.completed` (if the ledger did not break) and exit 3. Unlaunched cells are `not started`. `bench status` shows `stop_code` = the cause's code, and `phase` is not `stopped`: a launch stop is not a run stop.
8. **No decision request.** This deviates from ADR-0007 §7 (DR-2).

**Falsifying reverts** (`tests/mutations/stop.json`).
- Before slice 2 commits, each mutant is applied and its named test is observed red.
- For criteria 1–3, 5 and 6 the code already exists, so the red *is* the revert.
- Every assertion uses literals, never `engine.CIRCUIT_BREAKER`. TA B1: `test_engine.py:415` compares with the mutated constant, which is a tautology. STOP-I rewrites it as `== 3`.

| mutant (find → replace) | red test, and the assertion that makes it red |
| --- | --- |
| `CIRCUIT_BREAKER = 3` → `4` | `…_fires_at_its_threshold_not_before`, rewritten: 5 failing cells at parallelism 1 give **exactly 3** `cell.launch_intent` rows (the mutant gives 4) |
| `CIRCUIT_BREAKER = 3` → `2` | the same test (the mutant gives 2) |
| delete `self.infra_streak = 0` | `test_a_success_resets_the_infrastructure_streak` (`:838`: fail, ok, fail, fail, fail, ok → 5 intents; the mutant stops after the third cell) |
| `cause.invalidates` → `cause is not None` | new `test_harness_failures_do_not_trip_the_breaker`: **4** `adapter_crash` cells at parallelism 1 give 4 intents and **no** `run.launch_stopped` row (the mutant stops after 3; TA B1a) |
| the neutral-outcome guard removed | new unit test `test_neutral_outcomes_neither_count_nor_reset`, on `_after_append` with synthetic rows: fail, fail, `stopped`, fail → launching stopped; fail, fail, `model unavailable`, fail → launching stopped. TA M1: a `stopped` row cannot be observed at engine level before a stop |
| only the `model_unavailable` exclusion removed (it is counted again) | the same test's **"not counted" half** (TA N1): after fail, fail, `model unavailable`, **no** launch stop yet; and three `model unavailable` rows alone stop nothing. The mutant stops launching on the third row in both cases |
| `_stop_launching`'s `if self.stopped: return` removed | `…_stops_launching_once` (already in `engine.json`; kept) |
| `self._kill_all(...)` added to the breaker path | new `test_the_breaker_leaves_running_cells_running`: at parallelism 2, a slow `ok` cell beside three fast failures ends `completed` |

`…_stops_launching_once` is **not** credited with the 3→4 mutant: its 4 cells trip a threshold of 4 too (TA B1b).

## 8. The R-21 grace as a TLA refinement (`models/**`)

### 8.1 The refinement

The **terminate step** (`EngineKill` or `StopCell`'s running branch, then `CellDies`) is refined by one variable and two actions. Every other action is unchanged apart from `UNCHANGED grace`.

```tla
VARIABLES ..., grace   \* [cell -> BOOLEAN] engine memory: cancel sent, stdin closed, TerminateJobObject not yet issued (R-21)

EngineKill(c) == ... /\ grace' = [grace EXCEPT ![c] = TRUE] ...     \* was: killRequested, killReason only
StopCell(c)   == ... running branch: /\ grace' = [grace EXCEPT ![c] = TRUE]
CellDies(c)   == /\ proc[c] = "running" /\ killRequested[c]
                 /\ ~grace[c]   \* R-21: TerminateJobObject was issued
                 /\ ...          \* unchanged otherwise
Crash         == ... /\ grace' = [c \in Cells |-> FALSE]   \* the grace is engine memory; kill-on-close is a hard kill (PE-7)

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
NoGraceState == \A c \in Cells : ~grace[c]   \* second reachability witness: must be VIOLATED (TA M5c)
```

**The refinement mapping** (hide `grace`):
- `GracefulExit(c)` ↦ `CellDies(c)`: the same effect on every other variable;
- `EndGrace(c)` ↦ a stutter;
- `Crash`'s reset of `grace` ↦ the same `Crash`;
- the strengthened `CellDies` only removes behaviours.

So every behaviour of the refined spec is a behaviour of the version-3 spec, and safety carries over. `WF_vars(EndGrace(c))` (and, after a crash, `WF(Resume)`) restores the progress that `CellDies`'s new guard would otherwise block, so liveness carries over too.

This meets R-21 c3's "keeps its semantics": the same 16 invariants and 5 properties, unchanged. The Patterns Expert reviewed the mapping and found it sound.

**Timing is not in the model;** the model is untimed. The 30 s bound and the ≤ 10 s grace are code and test obligations (§5, §16), as the phase-1 budget kill already was.

**The new seeded variant `no_escalate`** disables `EndGrace`, so a child that ignores the cancel keeps its process forever. `StopReachesTerminal` rejects it, checked alone (MOD-A).

**The new witness `NoGraceState`** is expected to be violated. It shows that the grace state is reached, and `GracefulExit` is enabled in exactly that state, so `GracefulExit` is not vacuous.

`GraceImpliesKill` (PE-7) is **not** added as an invariant. It would need a contrived seeded variant to meet MOD-A, and the refinement mapping already implies it.

### 8.2 Spike evidence (Verified, this session)

**Method.**
- The refinement, including PE-7's crash reset, was applied by script to a scratch copy of `models/run_lifecycle.tla` at `5feece0`.
- The `no_escalate` line was added to a scratch copy of `tools/check_models.py`.
- `python tools/check_models.py` (full) ran with the pinned `tla2tools.jar` (sha256 `936a2620…0e88`) on JDK 21.0.11.

| run | result | distinct states (refined / version 3) |
| --- | --- | --- |
| liveness (5 properties, 1 cell) | ok | 58,016 / 57,344 |
| grading (2 cells, 2 passes) | ok | 17,129,408 / 16,325,776 |
| safety, small bounds (16 invariants, with `bench grade`) | ok | 4,798,704 / 4,503,440 |
| **safety, US-44 bounds** (3 cells, parallelism 2, 1 crash, symmetry, 16 invariants) | **ok, 397 s** | 85,060,752 / 77,212,448 (version 3 took 5 min 37 s) |
| witness `NotAllCellsFinished` | violated as expected | — |
| witness `NoGraceState` (small bounds and liveness bounds; a separate run) | violated as expected | — |
| 21 existing seeded variants | 21 of 21 rejected, each by its own target alone | — |
| `no_escalate` | rejected by `StopReachesTerminal` | — |
| the whole script | "all model checks passed", 27 `ok` lines, exit 0 | — |

- Revision 1's run, without the crash reset, also passed: 85,283,136 states at the US-44 bounds, in 406 s.
- **CI cost:** about 10 % more states and 20 % more time on the nightly run.
- Slice 3 re-runs the full check on the real files and cites its output (TA M5).

### 8.3 Conformance: the lifecycle table and the replay (`lifecycle.py`)

| new or changed `TABLE` entry | model action | replay rule (a violation names it) |
| --- | --- | --- |
| `control.applied` | `ApplyStop` / `ApplyAnswer` (the `controlApplied` half) | **ControlAppliedOnce**: a second row for one `uuid` |
| `run.stopped` | `ApplyStop` (`stopApplied`) | **one per run**; NoLaunchAfterStop also fires on an intent after `run.stopped` |
| `decision.opened` | `RaiseDecision` | **NoDecisionAfterStop**: none after `run.stopped` |
| `decision.resolved` | `ApplyAnswer` / `TimeoutDefault` / `ApplyStop`'s supersede | **DecisionResolvedOnce**: a second row per id; it must **follow its `decision.opened`** |
| `cell.launch_intent` | `WriteIntent` | **NoLaunchWhileDecisionOpen**: an intent while any decision is open |
| `cell.outcome{skipped (decision)}` | none: the cell is never launched (a filter on the queue) | allowed as a cell's **first** row; any later row for that cell violates WRITE_INTENT_ONCE / AT_MOST_ONCE |
| `cell.outcome{stopped}` | `RecordExit` after `StopCell` (with a process), or `StopCell`'s record branch (without one) | NoOutcomeWhileRunning (exists) |

**The mapping table in `run-lifecycle-model.md`:**
- The phase-2 rows (`StopCell`; `WriteControl`/`ApplyStop`/`ApplyAnswer`/`RemoveControl`; `RaiseDecision`/`TimeoutDefault`) are marked implemented, with `ApplyStop` ↔ `run.stopped`.
- Two rows are added: `GracefulExit` (→ `attempt.process_ended{ended_by: grace}`) and `EndGrace` (the engine's `TerminateJobObject` at `kill_deadline`; no event).

**Decisions in the model.** The model has one abstract decision; the engine has one per `decision_id`.
- The mapping holds per id, because decisions interact only through the launch guard (any open request → no launch) and the stop (which supersedes all).
- Interleavings of several decisions are not TLC-checked (a residual, §19).
- A spend-cap stop has no control file. In the ledger it is the model's `WriteControl("stop"); ApplyStop`.
- Several stop uuids map onto the model's single `controlFile["stop"]`; every one after the first is a stutter (`no-op (already stopped)`).
- The ledger never shows `WriteControl` for any stop, so the replay is unaffected.

## 9. Patterns (named, and past the Ladder)

| pattern | where | why (ladder rung) |
| --- | --- | --- |
| **Command Mailbox + Single Writer** (ADR-0007 §3) | control files, applied on the engine thread | already the engine's shape (rung 2: reuse); the `STOP` inbox item is the precedent |
| **Idempotent Receiver** (EIP) | `control.applied{uuid}` before the delete; replayed uuids skipped by an in-memory set (the ledger rebuild is phase 5) | ADR-0007 §3; the model's `ControlAppliedOnce` |
| **Invalid Message Channel** (EIP) | malformed files → `.rejected`; transient I/O errors retried | PE-9 |
| **Dead Letter** handling | the final control pass: `no-op (run ending)` | PE-10 |
| **Atomic file write** (temp + `os.replace`) | `bench stop`, `bench answer` | stdlib (rung 3) |
| **Exactly-once resolution by a state guard**; **Functional Core, Imperative Shell** | `_Decisions._resolve`; `_Decisions` returns rows, the loop appends them | one guard for every resolution path; pure, so the race tests are deterministic |
| **Two-phase termination** (a cooperative cancel, then a hard deadline; one deadline, one owner) | `threading.Event` + `kill_deadline` + `TerminateJobObject` | R-21. The phase-1 end-of-turn path already closes stdin, then terminates (`engine.py:438-458`); this reuses it for kills. The Event is stdlib (rung 3) |
| **Correlation by the failing resource** | `blocked_cell` keyed by harness; `qualification_gap` keyed by combo | one wait per broken dependency, not one per cell (PE-4) |
| **One-shot breaker (a fuse)** | built | the acceptance criterion only; the manual reset is deferred (DR-2) |
| **Refinement mapping** (Lamport) | §8.1 | proves "keeps its semantics" without a second model file |

**Rejected:**
- a named pipe or socket for `bench stop`: a second IPC mechanism, where files are ADR-0007's and the model's;
- writing `session/cancel` from the engine thread: it can block on a stuck adapter's pipe, and it races the worker's writes;
- a bespoke cancellation token with callbacks: a level-triggered `threading.Event` needs no bind step (S-5, PE-5);
- a Maildir `tmp/new` layout: the stem check and ignoring `*.tmp` are enough (PE-14);
- a new `decisions.py` module: not an owned path, and it would have one consumer;
- a separate abstract TLA module checked by `INSTANCE`: it would duplicate 590 lines;
- a half-open breaker: YAGNI until DR-2.

## 10. Change-surface list (E7), with owners

| surface | change | owner |
| --- | --- | --- |
| store (`events`) | `control.applied`, `run.stopped`, `decision.opened`, `decision.resolved`; the outcomes `stopped` and `skipped (decision)`; `ended_by`; codes HB-RUN-006/007 | STOP-I (`engine.py`, `errors.py`) |
| model and lifecycle | `lifecycle.TABLE` and the replay rules (§8.3); `models/run_lifecycle.tla` (§8.1); the mapping table in `docs/design/run-lifecycle-model.md` | STOP-I; `tools/check_models.py` and `tests/test_check_models.py` through S5 |
| service (engine) | the control reader and the final pass; `_Decisions`; `SPEND`; the graceful kill path, `_check_kills` and `a.terminated`; the pre-spawn stop check; the neutral outcomes; one clock and `on_tick`; the stale `getattr` removed (`engine.py:369-371`) | STOP-I |
| driver | the cancel Event; `session/cancel` and the stdin close on the worker thread; writes dropped after a cancel; no prompt after a cancel | STOP-I (`driver.py`) |
| plan and profile | `decision_timeout`, `spend_cap_tokens`, the generic old-plan refusal; `shutdown_grace_seconds` (≤ 10); `model_map` (S3); `defaultMode: default` | STOP-I (`plan.py`, `profiles.py`, `bench/profiles/*.yaml`) |
| wire (`bench-status/1`) | the `phase` enum, `OUTCOMES`, `decisions`; `VALIDITY` (S2) | STOP-I (`status.py`) |
| client (CLI) | `bench stop`, `bench answer`, the plan flags, the confirmation lines | STOP-I (`cli.py`) |
| UI (the skill) | the `start-benchmark` field list and relay rules, in every slice that changes the wire | STOP-I (both skill copies) |
| compute reader | views: `skipped (decision)` → `not started` validity (S4). The report has no change in wave 2 (the banner's "stopped" line is wave 4, row 20) | VIEWS, or granted (S4) |

## 11. Error and concurrency model

- **One writer.** The engine thread appends every new row. Workers hand `SPEND` and their records through the bounded inbox (`engine.py:116`), as today.
- **Linearization points:**
  - **turn ended vs a stop:** `a.ended` under `a.lock`. Whichever comes first wins: an ended turn keeps its outcome, and a stopped turn is `stopped` (PE-2);
  - **a stop:** the append of its `run.stopped` row;
  - **a spawn:** the worker's check of `kill_reason` under `a.lock`, just before `procs.spawn`;
  - **a prompt send:** `run_turn`'s cancel check before it writes `session/prompt` (the model's `SendPrompt` guard).
- **The spawn race.** The spawn check sets `a.spawning`. `_kill` on a cell with no process sets `kill_reason`. After the spawn, the worker sees it under the lock and terminates the new job at once: no grace, because no prompt was sent.
  - In the model, a spawn that passed its check before the stop is a `StartCell` before `ApplyStop`.
  - Its `attempt.process_started` row may land after `run.stopped`, because the ledger lags. The replay's NoLaunchAfterStop concerns intents only.
  - Test R10-10 (m3) forces this case.
- **The engine thread never blocks on a cell:**
  - `cancel.set()` is a flag;
  - `TerminateJobObject` is one non-blocking call (`_job_query` swallows `OSError`, `engine.py:517-522`);
  - `a.lock` is held only for field updates and `cp.close()`;
  - control-file I/O errors are retried next tick, never raised.
- **Clocks.** One injected clock drives every engine deadline (ADR-0007 §4). `default_in_s` in status uses the wall clock, for display only.
- **Crash.** Unchanged from phase 1: a crash leaves the run `incomplete`. Open decisions stay open in the ledger, and resume is phase 5 (ADR-0007 §4 restarts their deadlines from the resume). A control file left in `control/` stays there.

## 12. Failure-mode analysis

| failure mode | from | disposition | how | detection | test |
| --- | --- | --- | --- | --- | --- |
| A grandchild holds the pipe and ignores the cancel and stdin EOF | the cooperative cancel | prevent | the hard floor at `kill_deadline` | `ended_by: terminate` | R10-1 |
| The adapter never answers `session/cancel` | the per-harness contract is not verified | mitigate | not depended on; the grace ends it | `ended_by` per harness | R10-1; S6 |
| The adapter answers `cancelled` | the ACP "MUST" | handle | the outcome comes from `kill_reason`, never `adapter crash` | the outcome | R21-4 |
| A late permission request after the cancel | stdin is closed | prevent | writes dropped, not raised; reading continues | the usage is kept | D-2 |
| Terminate is unconfirmed (the OS refuses) | Job Object | detect | the HB-RUN-002 path, unchanged; the stop bound is then missed, visibly | `killing (unconfirmed)`; HB-RUN-002 | the existing T1-8 tests |
| A stop during the workspace build | build steps have no cancel hook | mitigate + accept | a check after each step; the residual is one step | `stopping` past 30 s | R10-5 |
| A stop between the spawn check and the spawn | spawn is not atomic with a stop | prevent | terminated at once after the spawn | the outcome `stopped`; no prompt | R10-10 (m3) |
| A stop between the prompt ack and the send | the ack barrier | prevent | the cancel is checked before `session/prompt` | `prompts` never 2 | R10-6 |
| A turn ends in the same tick as a stop | two paths end a cell | prevent | `a.ended` is the linearization point | the outcome stays `completed` | R10-11 |
| A stop after the breaker, disk floor or `build_changed` | an earlier launch stop | prevent | a separate `run.stopped` fact | `phase: stopped` | R10-12 |
| Answer, timeout and stop in any order or tick | three resolution paths | prevent | the `_resolve` guard; a fixed tick order | one `decision.resolved` | R10-4 |
| A duplicate stop file, or `bench stop` twice | the operator | prevent | `no-op (already stopped)` | the row | R10-8 |
| A malformed or oversized control file | a hostile or buggy writer | detect + contain | `.rejected`, an HB-USR-002 log, no row, no effect | `engine.log` | R10-9 |
| A control file locked by antivirus or the indexer | Windows file sharing | recover | retried next tick, never quarantined | — | R10-9b |
| A control file arrives after the loop | the run is ending | detect | the final pass: `no-op (run ending)` | the row | R10-13 |
| A stale answer | the TOCTOU between the CLI and the engine | prevent | the engine re-checks | `rejected (already resolved)` | R10-4 |
| One broken login stalls the run N × 30 min | a decision per cell | prevent | the harness is the subject; later cells join | one `decision.opened` | US15-6 |
| A decision with nothing it can change | a launch stop, or nothing pending | prevent | the guards in §6.1 | no row | US15-4 |
| The run ends with a decision still open | the loop condition | prevent | the loop runs while any decision is open | — | US15-5 |
| An unserved combo trips the whole-run breaker | `model_unavailable` invalidates | prevent | neutral for the breaker | no `run.launch_stopped` | CB-neutral |
| The running cells overshoot the spend cap | spend known at cell end | accept | disclosed at confirmation (§6.3) | `spend_tokens` on the decision | US15-3 |
| Unmeasured cells hide spend | `native_record` sources | detect + accept | `cells_unmeasured`; disclosed | the row | US15-3b |
| A plan made before STOP-I | old plans | prevent | the generic refusal | HB-USR-002 | P-2 |
| `keep_awake` not released on an exception | the engine's `finally` | prevent | already in `finally` (`engine.py:260`); now tested | — | R10-7b |
| A profile grace over 10 s | a profile edit | prevent | `profiles.load` refuses it | HB-USR-002 | PR-2 |

## Adversarial analysis (STRIDE-lite)

| Trust boundary | STRIDE threat | Disposition | Control / rationale | Negative test |
| --- | --- | --- | --- | --- |
| `runs/<run>/control/`, which any process of the operator's account can write, **including a cell's agent** (native cells run as the same user, ADR-0013) | S/T: a cell's agent writes a stop or an answer | accept (ADR-0012 scope: authored tasks, a trusted operator; `runs/` is outside the cell's working copy) | Every control is recorded (`control.applied{uuid, effect}` with its time) and shown in the run record. The effect set is closed: stop, or a listed option. The residual is a spurious stop or answer by an agent, visible in the ledger | R10-9, R10-8 |
| control file content | T/E: an oversized or crafted file (a path, nested JSON, a big string) | mitigate | ≤ 4 KiB; exact keys; enum values; the uuid and decision-id grammars; the stem equals the uuid; the name is never used as a path beyond `control/` | R10-9 |
| control file content | D: a flood of files | mitigate | Each tick reads one directory listing, and malformed files are moved aside once. `simplify:` no rate limit; upgrade trigger: a tick over 1 s in `engine.log` | — |
| `bench-status/1` → the coordinator session (B2) | I: cell text reaches the LLM session | mitigate | decisions carry only enums, ids and codes; `parse` rejects any free string | ST-3 |
| engine → adapter stdin | D: a stuck adapter blocks the engine thread | mitigate | only the worker writes stdin; the engine only sets an Event | R10-1 (the fake ignores stdin) |
| engine log | R: who stopped the run | accept | the ledger records the control's uuid and time, not its writer; the OS gives no writer identity for a file on this host | — |

## Privacy analysis (LINDDUN-lite)

This component touches no personal data. Checked: control files and the new rows hold only enums, bench ids, codes, token counts and times. They hold no cell text, prompt, transcript or credential. `bench-status/1` stays free of strings.

## 14. Telemetry

**The ledger (load-bearing, O12).** The rows in §3 each carry `recorded_at` and `mono_ns`. So every run, by default and with no flag, measures:
- the stop latency: `control.applied` → the last `cell.outcome{stopped}`;
- the grace outcome per harness: `ended_by`;
- the decision latency: `decision.opened` → `decision.resolved`.

**`engine.log`** (JSON lines, trace-correlated, `engine.py:569-600`) adds these events:
- `control rejected` (HB-USR-002, with the file name only);
- `control retried` (with the `OSError` class);
- `stop applied` (HB-RUN-006 or HB-RUN-007);
- `decision opened` and `decision resolved` (with the `decision_id` and the code);
- `grace ended; terminating` (with the `cell_id`).

**Questions an operator asks, and their sources:**
- How long did the stop take? The `mono_ns` deltas.
- Did the grace work for Copilot? `ended_by` counts per harness.
- Why did the run stop? `phase` and the text line for a run stop; `stop_code` for a launch stop.
- What is waiting on me? `decisions` in status.
- How much has the run spent? `spend_tokens` on a `spend_cap` decision; the report's tokens after grading.

## 16. Test plan: promise → test

Every test file here is in STOP-I's owned set except `tests/test_check_models.py` and `tools/check_models.py`, which are reached only through the S5 grant (TA N2). The row ids name the tests that `tests/mutations/stop.json` credits (TA M4).

### 16.1 Row 10's exit condition, clause by clause (plan `:145`, verbatim)

| # | clause (verbatim) | test (file · name), and what makes it falsifying | red first against |
| --- | --- | --- | --- |
| R10-1 | "a real process tree with a child that ignores termination is stopped within 30 s by the engine's clock, with outcome `stopped`" | `test_engine.py::test_stop_ends_stubborn_trees_within_30s`, under `_engine_run(limit=60)` (`test_engine.py:96-112`). **Setup:** **two** stubborn cells at parallelism 2. `fake_acp_agent.py` gains `{"child": "stubborn"}`: the agent ignores `session/cancel` and stdin EOF, and starts a **grandchild that inherits its stdout** and sleeps. On Windows termination cannot be ignored, so the hard case is a process holding the pipe (TA M2). The fake writes the grandchild's (pid, creation_time), the daemon fixture's identity (`fake_acp_agent.py:64-71`). The profile's grace is 10 s, the worst case. **Assertions, per cell:** `cell.outcome{stopped}.mono_ns − control.applied.mono_ns ≤ 30e9`; `ended_by == "terminate"`; the (pid, creation_time) identity is gone; `cell.archived` exists (US-45: "every started cell is archived") | **the hard-floor mutant**: with the `_check_kills` body removed, termination waits for a turn that never ends, and the `limit` fails it. The feature being absent is not the red |
| R10-2 | "any open decision becomes `superseded (stop)`" | `test_engine.py::test_a_stop_supersedes_every_open_decision`. Two open decisions (a blocked harness and a qualification gap), then a stop. Exactly one `decision.resolved{superseded (stop), option: null}` per id. The clock is then advanced past the timeout, and no default follows | the mutant with the supersede loop removed |
| R10-3 | "`bench status` shows `stopped` within 30 s (UXA-10)" | `test_status.py::test_status_shows_stopped_with_counts`: the rows give `phase: stopped`, `outcomes.stopped` and `outcomes["not started"]`. Also inside R10-1: `status.build` is polled from the control write until `phase == "stopped"`, with elapsed ≤ 30 s on `time.monotonic` | `PHASE` lacks `stopped` |
| R10-4 | "Race: both orderings are forced deterministically (injected clock or barrier, no sleep), and each gives exactly one terminal decision state and one ledger event" | **Pure:** `test_engine.py::test_decision_resolves_exactly_once_in_every_order`, parametrized over `itertools.permutations` of every non-empty subset of {answer, timeout, stop} (15 orders) on `_Decisions` (S-7). Each order asserts exactly one `decision.resolved`, the expected `state`, and the losing answer's `control.applied{rejected (already resolved)}`. **Engine:** `test_engine.py::test_resolution_order_through_the_loop`, parametrized over the pairs answer/timeout and stop/timeout in both orders, plus the **same-tick** case (answer and expiry in one tick → `answered`, which pins §6.2). The mechanism is `EngineConfig.on_tick(n)`: it drops the file at tick N and advances the injected clock at tick N or N+1 (TA M3). No `sleep`. "One ledger event" means exactly one `decision.resolved` per id; a losing answer's `control.applied{rejected}` is a separate consumption row | the mutant with `_resolve`'s guard removed (two rows) |
| US15-1 | "US-15: one test per default (blocked; …" | `test_engine.py::test_blocked_cell_default_continues_after_the_timeout`. A `blocked (auth)` cell opens `decision.opened{blocked_cell, subject: <harness>, default: continue}`. While it is open, no `cell.launch_intent` is written, and a running cell of another harness **reaches its outcome** (US-15: "running cells continue", TA m1). After the clock passes `decision_timeout`, `decision.resolved{default applied (timeout), continue}` is written, launching resumes, and the blocked cell's outcome is unchanged | no decisions |
| US15-2 | "… qualification gap → `skipped (decision)`; …" | `test_engine.py::test_qualification_gap_default_skips_the_combos_pending_cells`. A `model unavailable` cell of combo A; after the timeout, the default gives every pending A cell `cell.outcome{skipped (decision), decision_id}` with no intent. Combo B cells launch. A second `model unavailable` cell of A opens **no** second decision (TA m1) | no decisions |
| US15-3 | "… spend cap → stop)" | `test_engine.py::test_spend_cap_default_stops_the_run`. The cap is set below one cell's tokens (the fake's fixed `_meta.quota` usage). `decision.opened{spend_cap, spend_tokens}` is written with **a literal expected value** from the fake's fixed buckets, not one recomputed with `normalize.totals` (TA m2). After the timeout, `run.stopped{HB-RUN-007, decision_id}` is written and running cells are `stopped`. **US15-3b:** a cell with no usage adds to `cells_unmeasured` | no cap |
| CB | "Circuit breaker: its acceptance criterion is written in the design, with a red-first test" | §7 AC-CB-1..8 and the falsifying-revert table (`tests/mutations/stop.json`). Each mutant is observed red before slice 2 commits | the reverts in §7 |
| R10-7a | "The existing power request (`host.keep_awake`, `engine.py:216/258`) stays held through stop …" (today at `:218` and `:260`) | `test_engine.py::test_keep_awake_is_held_through_a_stop`. `keep_awake` is monkeypatched to record `(flag, len(eng.active), eng.stopped)`. After a stop with a running cell, the record is `[(True, 0, None), (False, 0, "HB-RUN-006")]`: the request is released only after every stopped cell's worker has ended | the mutant with `host.keep_awake(False)` added to the stop path |
| R10-7b | "… and exception (test)" | `test_engine.py::test_keep_awake_is_released_when_the_run_raises`. `_check_budgets` is monkeypatched to raise `RuntimeError` mid-run; under `pytest.raises`, the calls are `[True, False]` | the mutant with `keep_awake(False)` moved out of `finally` |
| TLC | "The TLC seeded variants still fail" | In slice 3, `python tools/check_models.py` (full, including the US-44 bounds) on the real files, **with its output cited in the commit**: 22 of 22 `ok`, `no_escalate` rejected by `StopReachesTerminal`, both witnesses violated. `tests/test_check_models.py` is green, including the S5 reverse test | the spike (§8.2); the reverse test is red on a seeded, unregistered `BUG` literal |

### 16.2 The other promises

| # | promise | test |
| --- | --- | --- |
| R21-1 | a budget kill sends `session/cancel` and closes stdin; the agent's shutdown record is written before any terminate | `test_engine.py::test_a_budget_kill_lets_the_agent_write_its_shutdown_record` (the fake writes a file on stdin EOF; red on today's immediate `terminate`) |
| R21-2 | a turn that ended keeps `completed`, and its process ends within the grace through `_end_process` | `test_engine.py::test_an_ended_turn_keeps_its_outcome_under_a_stop` (the same test as R10-11) |
| R21-3 | Copilot timeout: `session.shutdown` is present and the tokens are recorded after a budget kill (R-21) | `test_engine.py::test_copilot_budget_kill_records_session_shutdown`, `@pytest.mark.credentials`. S6: red before slice 3 and green after, in one capture window |
| R21-4 | the adapter answers the cancel with `stopReason: cancelled`: `ended_by` is `grace`, and the outcome is `stopped` (stop) or `timed_out` (budget), never `adapter crash` | `test_engine.py::test_a_cancelled_turn_is_classified_by_its_kill_reason`, parametrized over stop and budget. The fake gains `{"on_cancel": "cancelled"}` and exits after answering. Its message shapes are asserted against the SDK 1.5.0 schema's `CancelNotification` and `StopReason` (TA M7, D7) |
| R21-5 | the hard floor also holds for `timeout` and `host_suspended` | R10-1's stubborn fake, parametrized over the three kill reasons (TA m4) |
| R21-6 | `ended_by` is `terminate` when the fake exits at grace + ε | `test_engine.py::test_ended_by_records_who_ended_the_job` (PE-3) |
| R10-5 | a stop during the workspace build: no spawn, and the outcome is `stopped` | `test_engine.py::test_a_stop_during_the_build_never_spawns` |
| R10-6 | a stop between the ack and the send: no prompt | `test_driver.py::test_no_prompt_after_a_cancel_request` |
| R10-8 | a second stop is a no-op, with one `run.stopped` | `test_engine.py::test_a_second_stop_is_recorded_as_a_no_op` |
| R10-9 | a malformed or oversized control file is quarantined and logged, with no row | `test_engine.py::test_a_malformed_control_file_is_quarantined`. Postel cases: an extra key, a missing key, 5 KiB, not JSON, a stem that is not the uuid. **R10-9b:** an `OSError` on read (monkeypatched) leaves the file for the next tick |
| R10-10 | a stop between the spawn check and the spawn | `test_engine.py::test_a_stop_during_the_spawn_terminates_at_once` (`procs.spawn` is monkeypatched to apply the stop before it returns; TA m3) |
| R10-11 | a turn that ends in the same tick as a stop keeps `completed` | `test_engine.py::test_an_ended_turn_keeps_its_outcome_under_a_stop` (PE-2) |
| R10-12 | the breaker, then `bench stop` → `phase: stopped` | `test_engine.py::test_a_stop_after_the_breaker_is_still_a_run_stop` (S-1, PE-1) |
| R10-13 | a control file after the loop, or during grading → `no-op (run ending)` | `test_engine.py::test_a_late_control_is_recorded_not_lost` (PE-10). The file is dropped from inside the grading hook, and the test asserts the row lies between `grading.completed` and `run.completed` (Simplifier N-2) |
| R10-14 | stop precedence: a stopped cell whose record carries a provider error is still `stopped` | `test_engine.py::test_stop_outranks_a_provider_error` (TA M4) |
| US15-4 | no decision with nothing pending, or after a launch stop (the breaker, then a `model unavailable` cell) | `test_engine.py::test_no_decision_after_a_launch_stop` (TA M8) |
| US15-5 | the loop waits for an open decision when nothing else is left | `test_engine.py::test_the_run_waits_for_an_open_decision` |
| US15-6 | three blocked cells of one harness open one decision and cause one wait | `test_engine.py::test_one_blocked_harness_opens_one_decision` (PE-4) |
| US15-7 | an answer of `stop` → `run.stopped{HB-RUN-006}`; `continue` on `spend_cap` disables the cap | `test_engine.py` (two tests; TA m1) |
| D-1 | `session/cancel` is a notification with `{sessionId}`, sent once and only while a prompt is in flight; stdin is closed in the handshake | `test_driver.py::test_cancel_sends_session_cancel_during_the_prompt`, `…_closes_stdin_during_the_handshake` |
| D-2 | a permission request after the cancel raises no `_Eof`; `stopReason: cancelled` and the usage are read | `test_driver.py::test_writes_after_a_cancel_are_dropped` (PE-6) |
| CLI-1..4 | `bench stop` and `bench answer`: an atomic write (no `.tmp` left); the refusals (unknown run, not running, bad decision, bad option); the exit codes | `test_cli.py` |
| P-1..3 | the plan records `decision_timeout`, `spend_cap_tokens` and `model_map`; `bench run` refuses a plan missing any `DEFAULT_PARAMETERS` key; the confirmation prints both | `test_plan.py`, `test_cli.py` |
| PR-1..3 | `shutdown_grace_seconds` is loaded and ≤ 10 (11 is refused); `defaultMode` is `default` and equals the recording's effective mode (R-34 c4) | `test_profiles.py` |
| ST-1..3 | `bench-status/1`: the `phase` values, the `decisions` shape, and the strict parse rejecting a free string in a decision | `test_status.py` |
| SK-1 | both skill copies name every `bench-status/1` field and every `phase` and outcome value (R-3 c3) | `test_status.py::test_the_skill_names_every_status_field`. **Red first in slice 1**, and each later wire change keeps it green (TA M6) |
| LC-1..6 | each replay rule in §8.3, with a seeded forbidden ledger | `test_lifecycle_conformance.py` |
| ERR-1 | HB-RUN-006 and HB-RUN-007 exist; every design-table code is pinned | `test_errors.py` |

**Every `tests/mutations/stop.json` entry names its killer:**

| mutant | killer |
| --- | --- |
| the breaker entries | the §7 table |
| the hard floor | R10-1 |
| the `_resolve` guard | R10-4 |
| cancel-before-send | R10-6 |
| stop precedence | R10-14 |
| the `a.ended` guard dropped from `_kill` | R10-11 |
| `run.stopped` skipped when launching was already stopped | R10-12 |
| the neutral outcomes | CB-neutral |
| `keep_awake` | R10-7a/b |
| the supersede loop | R10-2 |
| the decision guard after a launch stop | US15-4 |
| writes raising after a cancel | D-2 |

### 16.3 Testing Strategy directives (the union)

| trigger | directive | here |
| --- | --- | --- |
| — | D0 hygiene | No dead code. The stale `assume:`/`getattr` at `engine.py:369-371` is removed: `TurnResult.last_update_seconds` exists (`driver.py:101`). ruff clean |
| T1 | D1 unit + mutation | `_Decisions`, the breaker, stop precedence, the plan and profile validators. The mutations are in `tests/mutations/stop.json`, each killed by the test named in §16.2. The kill is re-derived, never only counted (TOOL-B) |
| T2 | D2 property | **Hypothesis** (installed, `pyproject.toml:18`): arbitrary JSON objects given to the control-file parser never raise and never apply an effect outside the closed set. The decision space is finite, so R10-4 is exhaustive |
| T3 | D3 structure | The design D3 import lint (only the driver speaks ACP) stays green: `session/cancel` lives in `driver.py` |
| T4 | D4 real infra | Real files for the control directory (`os.replace`). Real Job Objects and processes in R10-1, R21-1, R21-5 and R21-6 |
| T6 | D5-provider | `bench-status/1` as the skill's contract: the strict parse, plus SK-1 |
| T7 | D6 schema + golden | `bench-control/1` and the new `events` kinds: golden rows in `test_lifecycle_conformance.py`. Old-run fixtures (with no new kinds) still replay |
| T8 | D7 mock fidelity | `FakeLauncher` + `fake_acp_agent.py` for the cancel, paired with the ACP 1.5.0 schema (R21-4) and the live Copilot test (S6) |
| — | model check | TLC, as in §8 |

## 17. Slice plan for W2-STOP-I

Codex `gpt-6-sol`, effort high (R-33: stipulated). The plan has six slices of at most 55 minutes each:
- Each slice ends at a commit, with its tests green and its mutants killed.
- Each slice touches only the paths STOP-I owns, plus S4/S5 if granted.
- **Red first in every slice:** each new test is observed failing, and the commit message cites that run.

| slice | content | tests (red first) | depends on | ends at |
| --- | --- | --- | --- | --- |
| 1 · seams, data, skill test | S1 (VIEWS's HB-VAL codes, verbatim) + HB-RUN-006/007 (`errors.py`); S2 + the `OUTCOMES` line (`status.py`, one commit) **with both skill copies and SK-1**; S3 `model_map` (`plan.py`); `decision_timeout` and `spend_cap_tokens` in `DEFAULT_PARAMETERS`, the generic old-plan refusal, the plan flags and confirmation lines (`plan.py`, `cli.py`); the stale `getattr` removed. It skips whatever of S1–S3 is already on `main` | ERR-1, P-1..3, ST-1 (enums), SK-1 | VIEWS's S1/S2 request text | a commit; the seams are delivered (the plan's "S1–S3 by slice 2" is met by slice 1) |
| 2 · breaker and power | the neutral outcomes (AC-CB 4, unit level); the `== 3` literal; the breaker and `keep_awake` entries in `tests/mutations/stop.json`; R10-7b | the §7 table (each revert observed red), CB-neutral, R10-7b | 1 | a commit; AC-CB is proven |
| 3 · the grace (driver, profile, model) | the cancel Event, `session/cancel`, writes dropped after a cancel, no prompt after a cancel; `shutdown_grace_seconds` (profiles, launcher, plan record); one clock and `on_tick`; `kill_deadline`, `_check_kills`, `a.terminated`, `ended_by`; `end_grace` removed; the `models/run_lifecycle.tla` refinement; the `run-lifecycle-model.md` rows; `defaultMode: default` (R-34 c4); the fake modes `stubborn` and `on_cancel` | D-1, D-2, R10-6, R21-1, R21-4..6, PR-1..3; a full `check_models.py` run showing 22 variants, 2 witnesses and the US-44 bounds, its output cited | 1; **the S5 grant is a precondition of the commit** | a commit; the grace, and 22 of 22 variants rejected |
| 4 · stop | the control reader, the dedup set and the final pass (after grading); `bench stop`; `run.stopped`; the stop sequence; the pre-spawn check; stop precedence; the replay rules for stop and control; the `stopping`/`stopped` phase **with the skill** | R10-1, R10-3, R10-5, R10-7a, R10-8..14, R21-2, CLI-1..2, LC (stop, control) | 3 | a commit; the plan `:145` "Stop" clauses |
| 5 · decisions | `_Decisions`, the triggers and guards, `SPEND`, `bench answer`, the supersede, the loop condition; `decisions` in `bench-status/1` **with the skill** (R-3) | R10-2, R10-4, US15-1..7, CLI-3..4, ST-2..3, LC (decisions, skip) | 4 | a commit; the "Race" and "US-15" clauses |
| 6 · proof | the full mutation pass over `tests/mutations/{engine,driver,status,cli,plan,stop}.json`; `python tools/check_models.py` (full); the Proof Pack figures for `docs/proof/phase2.md`, handed to the Leader; S4 if granted | all; the `pytest` default suite; ruff | 5 | a commit; join-ready |

**At the join (Leader):**
- `git diff --stat` against the owned paths (R-44 c3);
- R21-3 in a capture window (S6);
- the §5 `assume:` confirmed from the wave-1 ledger;
- the Test Architect's implementation gate. It needs a Proof Pack with three things: each `stop.json` mutant observed red on its named test; R10-1 red on the hard-floor mutant; and the full `check_models.py` output.

## 18. `driver.py`

**`driver.py` changed.** Four changes:
1. `run_turn` gains `cancel: threading.Event | None`.
2. `_Channel.rpc` polls the Event. On a cancel it sends the ACP `session/cancel` notification (only while `session/prompt` is in flight) and closes stdin, both from the worker thread.
3. After a cancel, `_Channel.send` drops writes instead of raising.
4. `run_turn` does not write `session/prompt` after a cancel.

Nothing else changes: the handshake, the deny-all permissions, `set_model`, the usage capture and the error classification are untouched.

## 19. Open decision requests, flags and residuals

**Decision requests to the Owner** (question · default taken by this design · what breaks):
- **DR-1 · the spend cap's unit.**
  - **Question:** should `spend_cap_tokens` count total tokens (the report's four buckets, from the same `normalize.totals`), given that cost is `NA` by decision on subscriptions?
  - **Default:** tokens, checked per ended cell, with unmeasured cells disclosed.
  - **What breaks:** if the Owner wants USD, the cap needs the price list (`bench/prices.yaml`) and a cost basis per harness (Copilot's AI units are wave 3, R-15 Q6). US15-3 still holds; only the measure changes.
- **DR-2 · the breaker's manual reset (ADR-0007 §7).**
  - **Question:** ADR-0007 §7 says the breaker raises a decision (resume launches or stop; default stop). The built breaker is a fuse that only stops launching. Which should wave 2 have?
  - **Default:** keep the fuse for wave 2, and add an amendment note to ADR-0007 §7 (the Leader writes it at the join).
  - **What breaks:** the ADR behaviour is a fourth `decision_kind` (`circuit_breaker`, options `resume`/`stop`, default `stop`): one trigger row in §6.1 and one test. It is also a behaviour change: after the timeout, that default **kills** running cells, where today they finish.

**Leader items:**
- the S4, S5 and S6 grants;
- S7 (`last_update` in status);
- the §5 `assume:`, confirmed from the wave-1 ledger.

**Flagged:**
- whether each adapter honours `session/cancel` (measured by `ended_by` and S6);
- interleavings of several decisions are outside the TLC model (it has one abstract decision), and so is the combo skip (a queue filter, covered by a replay rule and US15-2);
- the stop bound for a cell still in its workspace build (the §5 `assume:`).

**Residuals (accepted):**
- a cell's agent can write a control file (STRIDE row 1);
- the running cells can overshoot the spend cap;
- `bench stop` on a run that is not running is refused, not queued until resume (phase 5);
- tests that inject the clock cannot measure on `mono_ns`, which is real time.

**Deviations recorded:**
- ADR-0007 §7 (DR-2).
- The design-slice skill's rollup step (`docs/security/threat-model.md`, `privacy-review.md`) is **not run**. The brief limits this track to the design, the docs index and audit files, and `docs/notes/`. The STRIDE rows above feed the next rollup run (the Leader, or STOP-I).

**Confidence ledger:**

| claim | evidence | label |
| --- | --- | --- |
| The refinement, with the crash reset, keeps all 16 invariants and 5 properties, including at the US-44 bounds, and 22 of 22 variants are rejected | the spike's full run, §8.2 | Verified (at the author's seat; the Test Architect labels it Inferred until slice 3 cites the real run) |
| The grace state is reachable, so `GracefulExit` is not vacuous | the `NoGraceState` witness, violated | Verified |
| The ACP `session/cancel` shape and the `cancelled` stop reason | the SDK 1.5.0 schema, read | Verified |
| Claude Code's effective mode is `default` | the recording at `tests/test_driver.py:692-700` | Verified (by citation) |
| The stop fits in 30 s outside HB-RUN-002 | the step table, §5 | Inferred until R10-1 runs |
| The workspace-build step is short | none yet | `assume:` (§5) |
| Each adapter honours the cancel | none | Flagged |

## 20. Conformance notes

- **ADR-0007:**
  - §3 (control files, apply once, first resolution wins): as written.
  - §4 (monotonic deadlines): yes, with one injected clock.
  - §5 (stop within 30 s): yes, through R-21's grace.
  - §7: a deviation (DR-2).
- **ADR-0006:** additive `events` kinds and fields; no new fact table.
- **ADR-0011:** C4 (`bench-status/1` is schema-bound, with no free strings) is extended. C6 (idempotency keys) covers the control uuids.
- **R-3:** the schema stays `/1`, and the skill changes in the same commit as each wire change.
- **R-37:** a scripted-user question is never a decision request. The end-of-turn kill and the grace are untouched.

## 21. Gate record

The gate ran on revision 1 (`0b20b21`) on 2026-09-25. Three lenses were convened as subagents on `opus`, in Adversary Mode. The author cleared none of the vetoes.

**Test Architect** (hard veto): **BLOCK** on B1. Findings B1, M1–M9 and m1–m5; all are applied in revision 2.
- **B1:** §7 now uses 4 cells plus an assertion of no `run.launch_stopped`, and the literal `3`. `…_stops_launching_once` is no longer credited with the 3→4 mutant.
- **M1:** a unit-level neutral-outcome test; the engine-level skip test in slice 5.
- **M2:** R10-1 uses two stubborn cells, a grandchild that holds the pipe, the (pid, creation_time) identity, `_engine_run(limit)` and a `cell.archived` check, and it is red on the hard-floor mutant.
- **M3:** the `on_tick` mechanism; stop-vs-timeout at engine level; the same-tick case; "one ledger event" defined.
- **M4:** a named killer for every mutant; R10-14 added.
- **M5:** §8.4 filled in; the reverse test and the second witness through S5; the witness run.
- **M6:** SK-1 in slice 1; the skill changes in every wire slice.
- **M7:** R21-4 and the `on_cancel` fake.
- **M8:** the launch-stop guard; US15-4.
- **M9:** S6 red then green in one capture window.
- **m1–m5:** US15-7, the literal spend value, R10-10, R21-5, Hypothesis.
- The veto's stated clearing condition ("correct the §7 table … then PASS-WITH-CONDITIONS with M1–M9 written in") is met in the text. The Test Architect's re-read of revision 2 is recorded under the re-gate below.

**Simplifier** (soft veto): **BLOCK** on S-1. Findings S-1 to S-13.
- **S-1, applied:** the `run.stopped` fact; `RUN_STOP_CODES` deleted; test R10-12.
- **Applied:**
  - S-2: `continue` removed from `qualification_gap`;
  - S-3: `model_unavailable` is neutral for the breaker;
  - S-4: the launch-stop guard;
  - S-5: a `threading.Event`;
  - S-6: the `a.ended` guard is kept, and the floor applies only to turns that have not ended;
  - S-7: one permutations test;
  - S-8 and S-9: the derived fields are dropped;
  - S-10: one `rejected (invalid)` effect;
  - S-12: the generic old-plan refusal;
  - S-13: §8.4 filled in.
- **S-11, kept:** the `stopping` phase stays. It is one enum value, it tells P1 the stop is under way, and the lens allowed it.

**Patterns Expert** (advisory): **PASS WITH CONDITIONS**. Findings PE-1 to PE-15.
- **Merged with the Simplifier's:** PE-1 = S-1, PE-2 = S-6 and PE-13 = S-4, all applied.
- **Applied:**
  - PE-3: one deadline, one owner; `a.terminated`; R21-6;
  - PE-4: the harness as the subject; US15-6;
  - PE-6: writes dropped after a cancel; D-2;
  - PE-7: a crash resets the grace; re-verified;
  - PE-8: one clock;
  - PE-9: the transient-error retry; the dedup set rebuilt from the ledger;
  - PE-10: the final pass; R10-13;
  - PE-11: the breaker is named a fuse;
  - PE-12: §8.4 filled in;
  - PE-14: the file stem equals the uuid;
  - PE-15: the pattern names.
- **PE-5, resolved another way.** S-5's `threading.Event` replaces PE-5's callback token. It is level-triggered, so the lost-wakeup hazard PE-5 found cannot occur, and the Simplifier's stdlib rung wins.
- **Not added:** `GraceImpliesKill`, from PE-7 (§8.1).

**Re-gate of revision 2 (`fef5ebb`).** The same two agents re-read it. Revision 2.1 applies both sets of conditions.

**Test Architect: PASS WITH CONDITIONS. The hard veto is cleared at the design gate.** B1 is resolved, and M1–M9 and m1–m5 are applied in a form that can fail.
- **N1 (Major):** the "not counted" half of the `model_unavailable` rule gets its own assertion and its own mutant (§7). It is observed red in slice 2.
- **N2:** S5 is a precondition of slice 3's commit (§2, §16, §17).
- **N3:** both witnesses run inside `check_models.py main()` (§2 S5).
- **At the STOP-I join, the veto clears only with a Proof Pack containing:**
  - each `stop.json` mutant observed red on its named test, including N1's mutant;
  - R10-1 red on the hard-floor mutant;
  - the full `check_models.py` output (22 variants, 2 witnesses, the US-44 bounds);
  - S6 red then green, or R21-3 listed as Flagged.

**Simplifier: PASS WITH CONDITIONS. The soft veto is cleared.**
- **N-1:** the dedup set is in memory, and the rebuild is phase 5 (§4.1).
- **N-2:** the final pass runs after grading (§4.1, §5, R10-13).
- **N-3:** the decision key is (kind, subject, cause_code) (§6.1).
- **N-4:** the worker's end grace stays on `time.monotonic` (§6.2).
- **N-5:** the duplicate bullet is deleted.

**Patterns Expert:** PASS WITH CONDITIONS on revision 1; every condition is applied in revision 2. It was not re-convened, because the fan-out cap is 3 and its verdict was advisory.

`GATE design · phase2-stop-decisions · PASS WITH CONDITIONS · round 2 · 2026-09-25 · hard veto cleared by the Test Architect, soft veto by the Simplifier, none by the author`

## Status

| | |
| --- | --- |
| **Completed** | the row-10 design: stop, decisions, the spend cap, the circuit-breaker acceptance criterion, the R-21 grace refinement (spiked, full run), R-34 c4 and the STOP-I slice plan; revision 2, after the three-lens gate |
| **Remaining** | W2-STOP-I (implementation); the Owner's DR-1 and DR-2; the Leader's S4–S7 |
| **Best next action** | dispatch W2-STOP-I slice 1 (Codex `gpt-6-sol`) on this design |

---
**Handoff:** → `/implement` (W2-STOP-I).
