---
id: design-eval-resume
title: "Design: plan-level resume, liveness and the alarm channel (W1-K, ADR-0021)"
type: design
status: proposed
owner: "@timianmalloo"
phase: "Enterprise evaluation: Wave 1 (E3 build tracks X-K1, X-K2)"
tags: [evaluation-campaign, resume, liveness, alarm, sre, tla, wave-1]
links:
  - { to: spec-enterprise-evaluation, rel: implements }
  - { to: arch-evaluation-campaign, rel: implements }
  - { to: adr-0021-plan-level-resume-and-liveness, rel: depends-on }
  - { to: adr-0015-multi-turn-attempt-and-turn-snapshots, rel: depends-on }
  - { to: adr-0007-run-engine, rel: depends-on }
  - { to: design-eval-seam-contracts, rel: depends-on }
  - { to: design-eval-multi-turn, rel: depends-on }
  - { to: design-eval-atomic-publish, rel: depends-on }
  - { to: design-run-lifecycle-model, rel: refines }
review-by: "2026-10-17"
summary: >-
  How a restarted `bench run <run_id>` resumes: a pure classifier over the ledger maps every recorded cell state
  to one ADR-0021 section 4 action; the refusals run in a fixed order under the run lock; the dead engine's segments
  are marked abandoned, never written into; one `run.resumed` row per resume is the whole resume record (counts are
  derived). A resume of a stopped run finishes the stop (R-100): it launches nothing, records `stopped` for every intent-without-outcome cell, archives and exits 3; the model's invariant is `NoLaunchAfterStop`, and no liveness property carries a crash exception. The TLA+ model also settles the two resume branches W1-J left provisional by the
  recorded `next` of each turn, and TLC rejects every new seeded variant. Liveness is `last_progress_at` read from the
  ledger tail; the alarm is a scheduled Windows task that raises a toast (and an optional phone push) on a non-zero
  `bench status --alarm-after`, with a stamp file for the alarm of the alarm.
---

# Design: plan-level resume, liveness and the alarm channel (W1-K)

**Session** `w1k-resume-e1e4`, revision 1.1 `w1k-resume-r2-e1e4` (Owner ruling R-100 applied before the lens reviews; main merged in) · **branch** `design/eval-resume` · **tier** T2 · **fan-out** 0 · base `66ec885f` (main with W0 rev 6.7, R-87..R-99, W1-J).
Builds: **X-K1** (E3: `resume.py`, `engine.py`, `errors.py`, `identity.py`, `lifecycle.py`, the E3 model hand-over) and **X-K2** (E3: `status.py`, `cli.py`, `alarm.py`, the runbook). Not in scope: the alarm-channel **drill** (kickoff Not-in-scope), any `src/` file, ADR text.

## Status table

| item | state |
| --- | --- |
| Data model (resume record, segments, alarm state) | done, section 2 |
| Resume protocol and the classifier | done, section 3 |
| Every ADR-0021 section 4 row mapped to a kill-then-resume test by node id | done, section 4 |
| `NoLaunchAfterStop` (R-100), the two provisional branches settled, TLC run | done, section 5 (commands, counts, exit statuses recorded) |
| Alarm channel chosen, runbook path fixed | done, section 6 |
| Surface list, X-K1 / X-K2 split, seams | done, sections 8 and 12 |
| Gate record | **pending** (RV-TA, RV-DS, RV-SRE, RV-PAT, RV-SIM) |
| Decision request `req-01M41V2MC1RTCBB4APR3TSXEYP` (crash during a stop) | **closed: R-100 (DR-K1) ruled (B)**; (A) refused; applied in rev 1.1 |
| W0 rev 6.8 seams R6.8a-c and ADR-0021 Amendment 1 (D-K1, D-K2, D-K4, D-K5, R-100) | granted on `main`; cited in section 12 |

## 1. Responsibility, and what this design decides

ADR-0021 fixes the behaviour. This design decides what the ADR left open and corrects it where the code disagrees. Each correction is a **verified fact** read on `66ec885f`, stated with its source.

| # | decision | why (evidence) |
| --- | --- | --- |
| D-K1 | The refusal "naming the PID" becomes "naming the heartbeat age and the lock path". | `oslock.RunLock.acquire` writes no PID (`oslock.py:52-61`); `msvcrt.locking` is mandatory on Windows, so a second process cannot read bytes under the lock. A PID needs a byte-range design that buys nothing the age does not. **ADR text to amend (draft status).** |
| D-K2 | "Terminate the named job if present" becomes "confirm the recorded process is gone". | The Job Object is **unnamed** (`procs.py:216`, `CreateJobObjectW(None, None)`) and kill-on-close (`procs.py:220`), so after the engine dies the OS has already ended the tree and there is no job to name. The check is `attempt.process_started.pid` gone, waited for at most `pid_wait_s` (30). `os.kill(pid, 0)` is forbidden on Windows (CPython maps any non-console signal to `TerminateProcess`, Python docs for `os.kill`; not run); the check uses `OpenProcess(SYNCHRONIZE)` and a zero-timeout wait on win32. |
| D-K3 | A never-prompted cell's old cell folder is **discarded before the relaunch**. | `workspace.cell_working_copy` raises `HB-USR-002 "...already exists; a cell's working copy is built once"` (`workspace.py:195`). ADR row 2 never mentions it, so the relaunch would fail on the first real crash. Safe because nothing was prompted: no work exists to archive. |
| D-K4 | The stop-refusal predicate reads **three** rows, not two. | `engine._read_controls` appends `control.applied{control: stop}` and *then* calls `_apply_stop`, which appends `run.stopped` (`engine.py:518-524, 449-453`); an answered `stop` decision appends `decision.resolved{option: stop}` before `run.stopped` (`engine.py:353-356`). A crash between any two leaves no `run.stopped`. Predicate: `run.stopped` **or** `control.applied{control: "stop", effect: "applied"}` **or** `decision.resolved{option: "stop"}`. `run.launch_stopped` alone (disk low, spend-cap default) is **not** a stop: that run resumes once the cause is cleared. The predicate is **one input** to the classifier (3.2), not a refusal (R-100). ADR-0021 Amendment 1 carries this correction. |
| D-K5 | A run that holds `run.completed` can still be resumed, and `completed` is redefined. | A launch stop (HB-RUN-004, disk low) ends the loop with `ended_whole` true, so the engine writes `run.completed` with cells never launched (`engine.py:413-425`); that run is the main multi-night case. `views.load` sets `completed = any(run.completed)` (`views.py:542`), which would read "complete" while the resumed engine runs. New rule: **complete iff a `run.completed` row follows the last `run.resumed` row (or there is none).** Resume of a run with no pending cell and a valid grading pass is a no-op (exit 0, no segment). |
| D-K6 | A run whose `events` folder exists but holds no `run.started` row is **started** by the resume. | `cmd_run` and `Engine.run` both refuse once `events` exists (`cli.py:158`, `engine.py:372`); a crash between segment creation and the first row would block the run for good. |
| D-K7 | Engine segment ids gain a resume ordinal: `engine-<unix>-r<NNN>` (three digits, zero padded; the first incarnation keeps `engine-<unix>`). | `SegmentWriter.create` opens `xb`, so two incarnations in one second collide. `views.rows` sorts segment file names and needs `engine-` as prefix (`views.py:64, 87-99`); zero padding keeps `r010` after `r009`. |
| D-K8 | Engine segments marked `segment.abandoned` **stay readable**; the marker pins their head. | A grading segment abandoned is skipped by views (`views.py:93`); an engine segment holds the run's history and must not be. The marker's `head_hash` and `line_count` are checked by `bench verify` (new rule, section 3.6). |
| D-K9 | **Withdrawn (R-100).** Option A had added a `StopCrashed` disjunct to four liveness properties of the model (section 5). | It existed because option A refused a resume after a stop, so the cells a crashed stop was killing kept no outcome. No liveness property carries a crash exception. Under finish-the-stop, `Resume` and `ReconcileRecord(c)` (which records `stopped`) are already in `Fairness`, so the four promises hold through a crash after `ApplyStop`. |
| D-K10 | The invariant is **`NoLaunchAfterStop`** (`~flags["launchAfterStop"]`, the existing flag set by `WriteIntent` and `StartCell`), stated on the earliest of the three stop rows (`stopApplied`). `NoResumeAfterStop` is dropped. | R-100 condition 2: the invariant ADR-0021 section 2 protects is no launch after a stop. The model collapses the three rows into one step, which is at least as early as the code's. `Resume` takes no stop guard. |

## 2. Data model (settled first)

**Aggregate.** `Run` (identity `run_id`). The invariant it guards: *one engine incarnation writes at a time, and nothing launches after a stop* (a resume may still run, to finish the stop). A resume is a **state transition of the run**, not a new entity, so it creates no second run id (ADR-0021 Alternatives, DR-E1). Cells are referenced by `cell_id`. Bounded context: the run engine.

**Durable representation** (the pack default: append-only facts, derived views).

| fact | grain: one row is exactly one … | store | written by | history rule |
| --- | --- | --- | --- | --- |
| `run.resumed` | resume of one run by one engine incarnation | `events` fact, **first row** of the new engine segment | resume, before anything else | append-only; never updated. The resume's order is the order of segment ids; **no `n` is stored** |
| `segment.abandoned` | engine segment of one fact that a resume found unsealed | `events`, rows 2..k+1 of the new segment (one per `fact/segment_id`) | resume | append-only; the existing ADR-0006 row, same fields as the grading pass writes (`grade/runner.py:243`): `code HB-LED-004, fact, segment_id, line_count, head_hash, error` |
| `cell.outcome` by reconciliation | reconciled cell, once | `events` | resume | the existing row; **adds** one field `resume: {segment_id, turn, phase}` where `phase` is `mid-turn`, `between-turns` or `turn-complete`. This carries the RV-SRE 8 hand-off (W1-J next step 1). The `code` is `HB-CELL-118` or `HB-CELL-119` |
| `cell.launch_intent` | launch of one cell | `events` | engine | existing row; E3 adds `free_bytes` (W0 section 12). A relaunch after R2 writes a **second** `cell.launch_intent` for the same cell: legal, because the first never reached a prompt. `lifecycle.AT_MOST_ONCE` must allow it (surface list) |
| `last_alarm_check_at` | the newest alarm check of one run | file `runs/<run_id>/.alarm_check`, **mtime only** | `bench status --alarm-after` | overwritten; **not** a fact, never in the ledger (ADR-0021 section 7) |

`run.resumed` fields: `kind, run_id, plan_hash, segment_id` (equals the file's stem; a test asserts it), `trace_id` (the plan's trace id, unchanged: one trace per run across resumes). Stamped by `ledger.stamp` (`recorded_at`, `mono_ns`), so the resume's time is the row's `recorded_at`.

**Derived, never stored** (derive-don't-store, DM): `resumed n times` (count of `run.resumed`), each resume's time and segment id, `cells skipped / launched / reconciled` per resume, `last_progress_at`, the pending set, `completed`. One reader computes them: `resume.history(run_dir) -> list[ResumeRecord]` over **per-segment** rows (a new `views.segment_rows(run_dir, fact) -> list[tuple[str, list[dict]]]`; `views.rows` flattens and loses the segment). `ResumeRecord = (n, at, segment_id, skipped, launched, reconciled: tuple[(cell_id, code, turn, phase)])`; `skipped` = cells terminal and archived in earlier segments; `launched` = `cell.launch_intent` rows in this segment; `reconciled` = `cell.outcome` rows in this segment carrying `resume`. A cell that this resume *completes* normally after relaunch is `launched`, not `reconciled`.

**Why not a counter or a status row?** Two definitions of one quantity is a defect signature (DM); the segment list is already the truth.

## 3. The resume protocol

`bench run <run_id>` (the cli branch, X-K2) calls `resume.resume_run(run_dir, root, plan, cfg) -> RunSummary` (X-K1). It is idempotent: a second call over the same ledger makes the same decisions (section 4, W13/W14).

### 3.1 Order of operations

1. `plan.load_confirmed` (existing). If `events` does not exist: this is a first run, take the existing path.
2. **Acquire the run lock** (`RunLock.acquire(.lock, code="HB-RUN-005")`). Held: refuse, naming heartbeat age and path (D-K1).
3. **Refusals, fixed order, each reading the ledger only (nothing is written yet):**
   (a) run-side identity differs from the plan (ADR-0017 section 7; X-D's `identity_check`): `HB-IDN-001` with the diff;
   (b) `views.verify` has an error finding: `HB-RUN-009` naming the segment.
   A stop is **not** a refusal (R-100): `resume.stop_recorded(rows)` (D-K4's three rows) is read after (a) and (b) and sets the classifier's stop input (3.2). Order matters the other way now: a stopped run with a drifted identity or a broken chain must not be finished on a ledger that cannot be trusted. Test: a ledger failing both refusals reports (a).
4. **Nothing to do?** no pending cell, a `run.completed` after the last `run.resumed`, no cell with outcome and no `cell.archived`, and **no stop row**: print "run is complete" and exit 0. No segment is created. A stopped run is never "complete" (the engine exits 3 after a stop, `engine.py:436`): with a stop row and nothing left to record or archive, the resume prints the HB-RUN-008 line ("run is stopped: 0 cells recorded stopped, m archived, 0 launched"), creates no segment, writes nothing and exits 3 (idempotent re-run, W12e).
5. **Open the new segments**: `engine-<unix>-r<NNN>` for `events`, `turn_usage`, `archive_files` (`SegmentWriter.create`, exclusive). First `events` rows, in order: `run.resumed`, then one `segment.abandoned` per unsealed dead engine segment of each fact (head and count from `ledger.verify_segment`; a torn tail is ignored, not repaired). **The resume never opens the old file for append.** A crash anywhere after step 5 leaves a resume that the next resume classifies like any other (W13).
6. **Sweep** `sweep_temps(run_dir/"archive", lock)` and `sweep_temps(run_dir/"archive"/<cell>, lock)` for every cell folder (W0 section 4 rev 6.3). The caller's own wrong-pairing red test is in section 4.
7. **Classify** every plan cell with the pure function `resume.classify(plan, rows, stopped) -> list[Action]` (3.2), where `stopped = stop_recorded(rows)`, and record `resume.classified` telemetry. If `stopped` and no `run.stopped` row exists (windows 1 and 2), write `run.stopped` in this segment now (code `HB-RUN-006` for a `bench stop`, the decision id for an answered `stop`; code and reason are read from the control or decision row). Then execute the actions of non-terminal cells in **plan order**, reconciliation before any launch (the model's `reconciling` gate).
8. **Not stopped:** continue the engine loop as `Engine.run` does (launch the never-prompted cells in plan order under the existing parallelism, budget and disk rules), then grade and write `run.completed` as today. In-run grading is `run_pass`, which already abandons an unfinished pass and starts a new one (`grade/runner.py:228-246`); extractions already written are reused (write-once). **No new grading code.**
   **Stopped (finish-the-stop, R-100):** restore `run_stopped` from the ledger before the loop (the engine after `_apply_stop` is already "launch nothing, drain, exit 3": `_stop_launching`, `run_stopped`). Run the same reconciliation with launching disabled: one flag read from rows, the same actions. The loop writes no `cell.launch_intent`, **no `run.completed` and no grading pass**, runs the archive step for every recorded cell, and exits 3 with the HB-RUN-008 line "run is stopped: n cells recorded stopped, m archived, 0 launched". This differs from a live stop's tail only in the grading pass (the live engine at `engine.py:414` grades after a stop); `bench grade` grades the archive afterwards (US-26). See the open finding F-1 in section 12.

### 3.2 The classifier (the ADR section 4 table, as a function of ledger rows only)

`classify` reads rows and a **stop flag** (`stop_recorded(rows)`, D-K4's three-row predicate: one input, not a second table) and nothing else (no filesystem, no clock), so every row of the table is a unit test and a fixture. Inputs per cell: `launch_intent`, `process_started.pid`, `prompt_sent{k}`, `turn_ended{k}.next`, `turn_snapshot_archived{k}`, `cell.outcome`, `cell.archived`, `cell.archive_failed`.

| # | recorded state (first match wins, top to bottom) | action |
| --- | --- | --- |
| C0 | `cell.outcome` and `cell.archived` | **skip** (a leftover workspace is `bench teardown`'s, not the resume's) |
| C1 | `cell.outcome`, no `cell.archived` (including a `cell.archive_failed` row) | **archive**: `recover_archive` (3.3). Never re-run the cell |
| C2 | prompt sent for turn k, no `turn_ended{k}` (a **crashed turn**, any k) | confirm gone (D-K2), record `failed (coordinator crash)` HB-CELL-118, `phase mid-turn`, archive (C1), **never relaunch**. **Stop set: record `stopped`** (below) |
| C3 | `turn_ended{k}.next == snapshot`, no `prompt_sent{k+1}` (**between turns**), snapshot event recorded | confirm gone, record `failed (coordinator crash between turns)` HB-CELL-119, `phase between-turns`, turn k+1 `NOT_RECORDED "turn k+1 not reached"`, archive with the turn-k snapshot, never relaunch. **Stop set: record `stopped`** |
| C4 | as C3, snapshot event **absent** | redo the snapshot (3.4), then C3 (**stop set: then `stopped`**; the redo still runs, because the archive must hold the turn-k tree). If the redo fails after bounded retry: record `failed (archive)` HB-CELL-117 (W0 section 11, reused), `phase between-turns`, archive, never relaunch. **Not modelled** (symmetric with `SnapFail`; `simplify:` ceiling one cell, trigger: a second observed failure shape) |
| C5 | a turn ended and none is owed: the last planned turn ended, or `turn_ended{k}.next` is `final`, `stop` or `cancel`, and no outcome (**the ELSE**) | confirm gone, record `failed (coordinator crash)` HB-CELL-118, `phase turn-complete`, archive (C1), never relaunch. The cell is **never** recorded `completed`: the outcome needs exit status and extraction that the resume cannot recompute without guessing. **Stop set: record `stopped`** |
| C6 | `launch_intent` and no `prompt_sent{1}` | confirm gone (D-K2), discard the cell folder (D-K3), **launch once** (a second `launch_intent`). **Stop set: record `stopped`, archive the working copy as is, launch nothing** (no discard: the folder is archived like any other) |
| C7 | no `launch_intent` | launch in plan order. **Stop set: no action** (a normal stop leaves never-launched cells unlaunched and unrecorded; `run.launch_stopped` and `run.stopped` are the record) |

**The stop input (R-100 condition 3).** With the stop flag set, C2, C3, C5 and C6 record `cell.outcome{stopped}` instead of their rows above: cause `None`, no SPEND, `phase` as today, the `resume` object `{segment_id, turn, phase}` (it also says the resume, not a live worker, recorded it). The engine's kill-reason rule for `stop` (`engine.py:634, 654, 669`) is the source of "stopped", applied from the same rows: a cell with `launch_intent` and no outcome in a ledger holding a stop row was killed by the stop, because the stop row precedes the kill in `_apply_stop` and kill-on-close (`procs.py:216-220`) finished what the kill began. C0 and C1 are unchanged; C4 still redoes the snapshot first. **`run.launch_stopped` alone is not a stop** (D-K4): it sets no flag. `HB-CELL-118/119` stay the crash records of an un-stopped run and are never written for a stopped one.

A crashed turn is judged **before** between turns (C2 before C3): a cell that has a crashed turn 2 also has `turn_ended{1}`. The model's `ClassOf` has the same order. A `turn_ended` row with no `next` (a legacy single-turn row) reads `final` (W0 rev 6.5 condition 3).

**Settled provisional branches (W1-J asked W1-K).** `BetweenSnapped` is a guard on `next == snapshot` only: a turn that ended with `next = stop` took no snapshot and owes none, so waiting for one would block C5 forever (the model's `snapshot_when_stopping` variant). The final ELSE of `ClassOf` is exactly C5. The W1-J suggestion "`stop_reason == end_turn` in the 119 rule" is **declined**: `next` is the engine's recorded decision and the only reader input for "why turn n+1 was not sent" (W0 rev 6.5, condition 4); a second input would be a second definition.

### 3.3 `recover_archive` (X-K1 builds it; W1-B section 5 is its specification)

`archive.recover_archive(...) -> Recovery(result, missing_rows)` calls `archive.append_missing_rows` (X-J1, E2; one comparison, DM7) and `sweep_temps`. States: no final folder (sweep, then `archive_cell`); final folder, rows absent / partial / complete, `cell.archived` absent (append missing rows, then the event); rows or event recorded but folder absent (stop: `HB-LED-005`, names it, changes nothing). X-K1's crash-window tests for it are the **entry condition for this design's gate** (RV-TA W1-B R2-2); they are rows C1/W10/W11 in section 4.

### 3.4 Snapshot redo (C4)

The working copy is turn k's tree because turn k+1 was never sent. The resume calls the same `engine._snapshot_turn` path (X-J1) so the code is one: `sweep_temps(archive/<cell>)`, then `publish_dir`; if `FileExistsError`, verify the folder and `append_missing_rows` with `HB-LED-008` (W0 rev 6.3), never re-publish. Quiescence: the old process tree is gone (D-K2); the check is the recorded pid, not `job_active_processes` (a fresh job reads 0 for processes that are not in it; the ADR's reasoning for row 5 does not hold and is replaced by D-K2).

### 3.5 What stays out

No change to the cell's launch seed, plan order or budget. A resumed cell's budget is not restarted because a crashed cell is never continued (C2, C3, C5) and a never-prompted cell has no clock yet (C6). `parallelism` and `disk_floor_bytes` apply unchanged.

### 3.6 `bench verify` after a resume

New rule (`views.verify`, X-K1 hunk): for each `segment.abandoned` row naming an **engine** segment, the segment verifies, is unsealed, and its `line_count` and head equal the row's; else `HB-LED-002` naming it. Without it, a dead segment could be cut back after the fact and the chain would still verify. `_sealed_record` is unchanged (it checks `run.completed.segment_heads` of the segment that holds it; with `run.completed` possibly in several segments it loops all of them, as today).

## 4. ADR-0021 section 4: every row, a kill-then-resume test, by node id

**Two techniques, both real code.** (T1) *Prefix fixture*: one real two-turn engine run is the golden ledger; a window is the golden ledger cut after row *i* (rows are fsynced in order, so a prefix is exactly what a crash leaves) plus the folder state the real functions leave at that point (a half-filled `*.tmp-*` from `publish_dir`, a renamed folder with no rows). (T2) *Real kill*: the real `cli.py run` in a child process against `tests/fake_acp_agent.py`, killed with `Popen.kill()` when the ledger shows the target row, then the real `cli.py run <run_id>`. T2 is used where a row boundary can be polled; T1 where the window is shorter than a poll.

Files: **`tests/test_resume.py`** (X-K1), **`tests/test_alarm.py`**, **`tests/test_status.py`** (X-K2). Test (a) = the assertion that fails today and why. Every red is an assertion, never an `ImportError`: X-K1's first commit is a **skeleton** `resume.resume_run` that implements today's behaviour (raise `HB-USR-002 "already started"`), so each test fails on its own assertion.

| window | ADR row | ledger and disk state at the kill | node id | (a) assertion red today, and why |
| --- | --- | --- | --- | --- |
| W1 | no `launch_intent` | `run.started`, no cell rows | `test_resume.py::test_window[W1_no_launch_intent]` | `exit_code == 0 and cells launched in plan order` fails: `cmd_run` raises `HB-USR-002` |
| W2 | `launch_intent`, no `prompt_sent{1}` | process started (pid recorded), cell folder present (T2: agent hangs in `session/new`) | `...[W2_launched_not_prompted]` | `exactly one prompt in prompts_log and a second launch_intent` fails: no resume exists. Also red for D-K3: with the discard line removed the relaunch raises `HB-USR-002` (mutant M-NODISCARD) |
| W3 | `prompt_sent{1}`, no `turn_ended{1}` | T2: agent hangs inside prompt 1 | `...[W3_turn1_crashed]` | `outcome.code == "HB-CELL-118"` and `prompts_log` still one line, fails |
| W3b | same, turn 2 | `prompt_sent{2}` durable, no `turn_ended{2}` (T2) | `...[W3b_turn2_crashed]` | `HB-CELL-118`, `turn == 2`, `phase == "mid-turn"`, turn-1 snapshot kept in the archive, fails |
| W4 | `turn_ended{1}`, snapshot copy in flight | `archive/<c>/turn-1.tmp-<pid>-<uuid>` half filled, no event (T1) | `...[W4_snapshot_tmp]` | `no *.tmp-* left and snapshot event present and HB-CELL-119` fails |
| W5 | `turn_ended{1}`, snapshot folder renamed, event absent | final `turn-1/` complete; rows none / partial / all (three params: `W5a`, `W5b`, `W5c`) | `...[W5a_rows_none]`, `[W5b_rows_partial]`, `[W5c_rows_all]` | `duplicate archive_files key HB-LED-003` fails on the partial and complete cases when a mutant appends all rows; the real run must append only the absent keys and the event |
| W6 | between turns, snapshot recorded | `turn_snapshot_archived{1}`, no `prompt_sent{2}` (T2: poll for the event, kill) | `...[W6_between_snapped]` | `HB-CELL-119` and `turn 2 NOT_RECORDED "turn 2 not reached"` and archive holds `turn-1` fails |
| W7 | between turns, `next = stop` | `turn_ended{1}.next == "stop"` (budget kill), no outcome (T1) | `...[W7_next_stop]` | `code == "HB-CELL-118" and phase == "turn-complete"` fails (the `between_ignores_next` mutant gives 119 here) |
| W8 | the ELSE | `turn_ended{2}.next == "final"`, no outcome (T1) | `...[W8_all_turns_ended]` | `code == "HB-CELL-118" and outcome != "completed"` fails |
| W9 | outcome, archive tmp in flight | outcome row, `archive/<c>/attempt-1.tmp-...` (T1) | `...[W9_archive_tmp]` | `a verified archive and cell.archived and no tmp` fails |
| W10 | outcome, archive renamed, event absent | final `attempt-1/` with rows none / partial / all (`W10a/b/c`) | `...[W10a_rows_none]` etc. | as W5, with `HB-LED-005` on a differing row |
| W11 | outcome and `cell.archived` | workspace still present (T2: poll for `cell.archived`) | `...[W11_done_skip]` | `no new row for this cell and the run exits 0` fails; leftover workspace untouched |
| W12 | stop, three windows (finish-the-stop, R-100) | `control.applied{stop}` only / `decision.resolved{stop}` only / `run.stopped` only, each with one cell in each of the C2, C3, C5 and C6 states | `test_resume.py::test_resume_finishes_the_stop[control_applied]`, `[decision_resolved]`, `[run_stopped]` | `every intent cell gains cell.outcome{stopped} with the resume object, is archived; no new launch_intent, no run.completed, no grading pass; run.stopped present exactly once; exit 3` fails today: the skeleton raises `HB-USR-002`, so the exit-code and row assertions fail, not an import |
| W12d | `run.launch_stopped` only (disk low) | no stop row | `...::test_launch_stopped_is_not_a_stop` | `the unlaunched cells launch and the run resumes normally` fails today (no resume); M-LAUNCHSTOPPEDISSTOP makes it fail later |
| W12e | idempotent re-run | the W12 ledger resumed twice | `...::test_finish_the_stop_is_idempotent` | `the ledger is byte-identical after the second call; zero actions; exit 3; stdout holds the HB-RUN-008 text "run is stopped: 0 cells recorded stopped, m archived, 0 launched"` fails today (no resume) |
| W13 | crash right after `run.resumed` | new segment holds `run.resumed` and k `segment.abandoned`, no reconcile row | `test_resume.py::test_resume_of_a_resume[W13]` | `exactly one abandoned row per dead segment (no duplicate on the second resume)` fails |
| W14 | crash mid-reconcile | some reconciled `cell.outcome` rows in the resume segment | `...[W14]` | `the same decisions as an uninterrupted resume` fails (compare the final per-cell outcome map) |
| W15 | `events` exists, no `run.started` | segment created, zero rows | `test_resume.py::test_run_started_by_resume[W15]` | `exit 0` fails: `HB-USR-002` |
| W16 | `run.completed` with unlaunched cells | launch stop HB-RUN-004, run completed, 2 cells never launched | `test_resume.py::test_resume_after_launch_stop[W16]` | `the 2 cells run and status.completion goes "in progress" then "complete"` fails (D-K5) |

**Sweep over every row (the exhaustive net).** `test_resume.py::test_every_ledger_prefix_matches_the_adr_table` runs `classify` on **every prefix** of the golden ledger and compares with an *independent* oracle: a table in the test keyed by the last row's kind, written from the ADR's wording and not from `classify`'s predicates. It asserts `len(prefixes) == N` where N is a literal taken from the scan on this design's base (golden ledger of the two-turn fake: counted by X-K1 at its skeleton commit, and the count recorded in the test; (e) allowlist/sweep rule). Deleting a branch of `classify` fails at least one prefix.

**Refusals** (`tests/test_resume.py`): `test_refused_live_lock` (a child holds the lock; `HB-RUN-005`; message holds the age, not a PID), `test_refused_identity_drift` (`HB-IDN-001`), `test_refused_verify_failure_names_segment` (`HB-RUN-009`, tamper one byte of an engine segment), `test_refusal_order` (a ledger failing identity and verify raises `HB-IDN-001`; a stopped ledger with drifted identity is refused, never finished), `test_refusal_writes_nothing` (no new segment, no `.alarm_check`, no change to any file: hash the run dir before and after). The `lifecycle.py` replay rule (section 8) is tested by `test_lifecycle.py::test_launch_intent_after_a_stop_row_is_rejected` and `::test_run_resumed_after_a_stop_row_is_accepted` (red fixture: a ledger with `cell.launch_intent` after `run.stopped`).

**(b) Red fixtures.** Each refusal and the sweep has its fixture above, run before the real tree. `test_sweep_pairing_refuses_wrong_lock`: a held lock of another folder passed with `archive/` raises `ValueError` (W0 rev 6.1, RV-SEC decision A); deleting the pairing line turns it red. `test_abandoned_marker_pins_head`: cut a dead engine segment by one row after the resume; `bench verify` must report `HB-LED-002`.

**(c) Real wiring beside the fakes.** `classify` is pure and unit-tested; `test_resume.py::test_cli_run_resumes[T2]` drives the real `cli.py` command twice around a real kill and fails if the `cmd_run` branch (X-K2) or `resume_run` call is removed. T2 is also W2, W3, W3b, W6, W11.

**(d) Mutants that separate adjacent rules** (`tests/mutations/resume.json`, X-K1):

| mutant | swaps | input on which the pair differs |
| --- | --- | --- |
| M-OLDPRED | C2 vs C3 (the old "prompted and not terminal" test) | W6 (between turns, snapshot recorded): 118 instead of 119 |
| M-IGNORENEXT | C3 vs C5 | W7 (`next = stop`): 119 instead of 118 |
| M-ELSEDONE | C5 vs a `completed` record | W8 |
| M-LAUNCHAFTERINTENT | C6 vs C2 | W2 relaunches vs fails; W3 relaunches |
| M-RESEND | C2 vs a continued turn | W3b: second prompt in `prompts_log` |
| M-SKIPARCH | C1 vs C0 | W9, W10: cell skipped without archive |
| M-NODISCARD | C6 | W2: relaunch raises on the existing folder |
| M-STOPONLYRUNSTOPPED | the stop predicate | `[control_applied]` and `[decision_resolved]` windows launch (they hold no `run.stopped` row) |
| M-LAUNCHSTOPPEDISSTOP | `run.launch_stopped` vs a stop row | W12d: nothing launches |
| M-STOPCRASHREC | the stop input vs C2/C3/C5 | W12: `HB-CELL-118/119` instead of `stopped` |
| M-STOPLAUNCHES | the stop input vs C6 | W12 (the C6 cell): a second `launch_intent` is written |
| M-STOPGRADES | finish-the-stop vs the live tail | W12: a grading pass or `run.completed` appears |
| M-ORDER | refusal order | `test_refusal_order` |
| M-WRITEOLD | step 5 | `test_abandoned_marker_pins_head` / the old segment's byte hash changes |
| M-APPENDALL | `append_missing_rows` | W5b, W10b: duplicate key |

**(e) Sweeps against the tree.** (1) The three FACTS the engine writes are `("events", "turn_usage", "archive_files")` (`engine.py:49`): the test asserts the set of segments abandoned equals `{f for f in engine.FACTS}` intersect the unsealed ones, so a fourth fact added later fails here. (2) Readers of "completed" (`views.load`, `status.build`, `cli._require_running`, `grade/runner.py`): X-K1 runs `rg "run.completed" src` on its base and pins the hit count in `test_completed_has_one_definition`; the test fails if a reader keeps its own `any(... run.completed)`. The count on **this** design's base is recorded by X-K1's skeleton commit; this doc does not assert a number it did not scan.

## 5. The lifecycle model (`models/run_lifecycle.tla`, version 6)

### 5.1 What changed

| change | where | why |
| --- | --- | --- |
| `turnNext[c][k]`, a ledger variable | `TurnEnd` sets it: `final` at the last turn, `stop` when a kill or a stop is pending, else `snapshot` | the recorded `turn_ended.next` (W0 rev 6.5) decides "between turns" (section 3.2) |
| `BetweenTurns` (in `ClassOf`) and `BetweenSnapped` and `WaitingLit` read `next = snapshot` | settles the two provisional branches | C3, C4, C5 |
| `CopyBegin(c, a>0)` requires `turnNext = snapshot` | a snapshot is taken only when a next turn is owed | W0 rev 6.5 |
| `Resume` takes **no** stop guard and sets no flag (R-100) | ADR-0021 section 2, Amendment 1 | the invariant is the existing `NoLaunchAfterStop == ~flags["launchAfterStop"]`, set by `WriteIntent` and `StartCell` |
| `ReconcileRecord(c)` under `stopApplied` records `stopped` for every intent-without-outcome cell (prompted or not), after the snapshot redo for a between-turns cell | R-100 condition 2, classifier rows C2-C6 | new invariant `StopResumeRecordsStopped == ~flags["crashUnderStop"]`; the flag name replaces `resumeAfterStop` and is set only by the seeded variant |
| `StopCrashed` and its four disjuncts are **removed** | D-K9 withdrawn (R-100) | the four liveness properties are stated as W1-J had them; `Resume` and `ReconcileRecord` are in `Fairness`, so they hold through a crash after `ApplyStop` |
| three invariants: `StopResumeRecordsStopped`, `BetweenRecordedWithSnapshot`, `SnapshotOnlyWhenNext` (`NoResumeAfterStop` retired) | `safety.cfg` and `turns.cfg` | each has a seeded variant |

`BetweenSnapped` had **no** seeded variant and no invariant in W1-J: it was an untested guard. `BetweenRecordedWithSnapshot` (a recorded `crashbetween` has the snapshot event of its waiting turn) and the variant `between_without_snapshot` now test it.

### 5.2 Seeded variants (all registered as **data rows** in `tools/check_models.py`: `VARIANTS` 5 rows added and 1 retired, `WIDER` 3 rows; no logic line, no witness row)

| variant | change | rejected by | bounds |
| --- | --- | --- | --- |
| `stop_recorded_as_crash` | under a stop, `ReconcileRecord` records `ClassOf(c)` (a crash class) and sets the flag | `StopResumeRecordsStopped` | small |
| `stop_resume_launches` | under a stop, `ReconcileRecord` takes the relaunch branch and `StartCell` is allowed (the finish-the-stop resume launches) | `NoLaunchAfterStop` | small |
| ~~`resume_after_stop`~~ | **retired** (R-100): `Resume` has no guard to lift | | |
| `between_without_snapshot` | `ReconcileRecord` drops `BetweenSnapped` | `BetweenRecordedWithSnapshot` | `NumTurns = 2` |
| `between_ignores_next` | `BetweenTurns` ignores `next` | `CrashedTurnPredicate` (a `next = stop` cell recorded `crashbetween`) | `NumTurns = 2` |
| `snapshot_when_stopping` | `CopyBegin` snapshots a `next = stop` turn | `SnapshotOnlyWhenNext` | `NumTurns = 2` |

No new witness: `WITNESSES` is pinned by an equality in `tests/test_check_models.py` (`test_grace_variant_and_both_reachability_witnesses_are_checked`), a file this track does not own. `between_ignores_next` being rejected is itself the reachability proof of the `next = stop` crash state.

### 5.3 Abstractions and limits (stated, not hidden)

- `stopApplied` stands for three ledger rows (D-K4, D-K10). The model finishes the stop at the earliest; the **code** windows are the three `test_resume_finishes_the_stop` params.
- **Grading after a finish-the-stop (finding F-1).** R-100 says the finish-the-stop resume starts no grading pass; the live engine does grade after a stop (`engine.py:414`), and the model keeps `GradeStart(p, "engine")` enabled on a stopped run. So the model's `ArchivedCellsGetGraded` holds through a crash after `ApplyStop` because the model's resumed engine may still grade; the code will not. Gating the resumed engine's grade in the model would need an exception in `ArchivedCellsGetGraded`, which R-100 forbids ("no `StopCrashed` disjunct"). This design keeps the model as it is, states the gap here, and asks RV-DS and the Owner to confirm that `bench grade` after the exit-3 is the intended grading path (section 12, F-1).
- The model lets a cell outlive an engine crash; kill-on-close means the engine's cannot (header of the `.tla`); the safety results therefore carry over. The pid check (D-K2) is code, not model.
- A copy that fails during the redo (C4) is not modelled; the in-run `SnapFail` is its twin.
- Liveness runs without symmetry at one cell, one crash (`liveness.cfg`).

### 5.4 TLC evidence (revision 1.1, after R-100)

**Command and result (the run that counts, on the final `.tla`, `.cfg` files and `check_models.py`).** From the tree root `C:\Projects\x-harness-x-model-bench-design-eval-resume`, Temurin 21.0.11, TLC 2.19 (08 August 2024) from the pinned `.tools/tla2tools.jar` (sha256 checked by the script), 24 workers:

```
uv run python tools/check_models.py --quick      # wall 15:51:06 to 16:00:02 (8 min 56 s), exit status 0
```

```
ok   liveness                 real design, 170552 states, 15s
ok   grading                  real design, 39191368 states, 256s
ok   safety-small             real design, 13362512 states, 63s
ok   safety-turns             real design, 17751072 states, 91s
ok   witness / grace-witness / turns-witness / between-witness   violated (3 / 2 / 4 / 2 s)
seeded variants: 34/34 rejected by own target
reachability witnesses: 4/4 violated
all model checks passed
exit 0
```

State counts are **distinct** states. A first run of this revision failed to parse (a `\notin` I typed in a Python string became a newline; SANY reported it, exit 1 with 0/34 rejected); it was fixed and rerun, and only the second run is recorded. `PYTHONPATH=src uv run python -m pytest tests/test_check_models.py -q`: 7 passed, exit 0. `uv run ruff check tools/check_models.py`: exit 0.

**Liveness with a crash after `ApplyStop` reachable (R-100 condition 2).** `liveness.cfg` has `MaxCrashes = 1`, one cell, no symmetry, and checks all five properties (`DecisionEventuallyResolved`, `StopReachesTerminal`, `EndedCellsGetArchived`, `PromptedCellsEnd`, `ArchivedCellsGetGraded`) with **no** `StopCrashed` disjunct: the row above, 170,552 distinct states, exit 0. Reachability of the crash-after-stop state inside that configuration: a scratch copy of the model with one extra operator `NoCrashAfterStopWitness == ~(stopApplied /\ engine = "down" /\ \E c : intent[c] /\ outcome[c] = "none")`, run as the only invariant on the `liveness.cfg` constants (command: `python reach.py` in the session scratchpad, TLC `-workers 4`): **violated** at a 5-state trace `Init, WriteControl, WriteIntent, ApplyStop, Crash` (524 generated, 290 distinct), exit 12. So the liveness run explores the state, and the four promises hold through it because `Resume` and `ReconcileRecord(c)` (now recording `stopped`) are in `Fairness`. One-time evidence; not a continuous ring, and the witness operator is not added to the model (`WITNESSES` is pinned by `tests/test_check_models.py`).

**The new variants and the one that lost its lift** (direct TLC through `check_models.tlc`, each against its target alone; `exit 12` is TLC's invariant-violation status):

| variant | target | bounds | trace length (states) | generated / distinct | time |
| --- | --- | --- | --- | --- | --- |
| `stop_recorded_as_crash` (new) | `StopResumeRecordsStopped` | small | 7 | 22,738 / 7,802 | 2 s |
| `stop_resume_launches` (new) | `NoLaunchAfterStop` | small | 5 | 5,558 / 2,246 | 2 s |
| `launch_after_stop` (existing, the invariant R-100 names) | `NoLaunchAfterStop` | small | rejected in the quick run | n/a | n/a |
| `relaunch_stopped` (existing; its `Resume` lift is removed because `Resume` has no guard) | `StoppedNeverRelaunched` | small | 8 | 33,247 / 10,857 | 2 s |
| `resume_after_stop` | retired | | | | |

**MOD-C, both directions (each new or removed guard against every other variant).** Removed: the `Resume` guard and its `relaunch_stopped` lift; `relaunch_stopped` is still rejected (row above), and no variant needed the lift for any other reason. New: the stop branch of `ReconcileRecord` (with its `BetweenSnapped` guard on prompted cells) and the `StartCell` lift for `stop_resume_launches`. The proof that neither starves another variant is the quick run itself: all 34 variants report `rejected by own target`, including the stop-sensitive ones (`launch_after_stop`, `relaunch_stopped`, `stop_ignored`, `no_escalate`, `record_without_kill`, `kill_between_turns`, `between_without_snapshot`). The two new variants are themselves the reverse check on the new branch: each is rejected only because the branch it breaks is reachable.

**US-44 bounds (3 cells, parallelism 2, 1 crash, the non-quick `safety` run): not re-run for revision 1.1.** The revision 1 result (357,112,128 distinct states, 39 min 34 s, exit 0) was for a model with `Resume` guarded and is **stale** for this one. It is one-time evidence outside every continuous ring; the quick run covers the same invariants at small bounds, and the Leader may order the 40-minute run before the gate merge if the lenses ask.

## 6. Liveness and the alarm

### 6.1 `last_progress_at` (ADR-0021 section 7)

The `recorded_at` of the **last data row of the newest events segment of any kind** (engine segments and grading-pass segments, a pass in progress included, so a long grading pass counts as progress), read by seeking to the segment tail and parsing the last complete line; a torn last line is skipped to the previous one. It is a liveness probe, not an integrity check: it does **not** verify the chain (`bench verify` does). Unreadable: `not recorded`, and the alarm raises (fail closed). `bench status --json` gains `last_progress_at` (string or null) and the schema string becomes `bench-status/2`; `status.parse` accepts `/1` (new keys read as null) and `/2`. `bench-campaign-status/1` is unchanged (W1-C).

### 6.2 The check: `bench status <run_id> --alarm-after <seconds>`

Pure core `alarm.check(run_dir, after_s, now, lock_age) -> AlarmResult | None` in `alarm.py` (grade class, W0 section 9); the CLI renders it. **Pending** = plan cells with no `cell.outcome`. There is **no stop exception** (R-100 condition 6): after a finish-the-stop resume no cell is pending, so the alarm is silent by the record; a crash that lands mid-stop leaves pending cells and a free lock, so it fires until somebody resumes, which is correct (the operator asked for a stop and the ledger does not yet say it finished). Causes:

| code | when | message names |
| --- | --- | --- |
| `HB-ALM-001` engine not alive | pending > 0, and the lock is **free** (not running), or held with heartbeat age greater than `lock_staleness` (stalled) | `not running` or `stalled`, the age, the last progress time, and `bench run <run_id>` as the action |
| `HB-ALM-002` progress stalled | the lock is held and fresh, pending > 0, and `now - last_progress_at > after_s` | the gap, the threshold, the last row kind |
| `HB-ALM-003` warning (never an exit code) | the lock is held and no check ran within 2 x 900 s (`ALARM_INTERVAL_S = 900`, a constant; `simplify:` ceiling one interval, trigger: the operator changes the task interval) | the age of `.alarm_check`, or "never" measured from the latest `run.started` or `run.resumed` |

A free lock with pending cells fires at once (no threshold wait): this is the common failure (engine crash, reboot), and the ADR text "heartbeat is stale" does not cover a lock that was released by the OS. A run with no pending cell, or `run.completed` after the last `run.resumed`, never alarms. A stop that was finished (no pending cell) is silent for the same reason. A launch stop (disk low) leaves pending cells and a free lock, so it alarms: the run needs the operator. **A named, never-started run alarms** (armed deliberately); `bench campaign status --alarm-after` checks only attached runs (`pilot_runs`, `grid_runs` of `bench-campaign-status/1`) that **have started** and have pending cells, so a grid's later runs do not alarm before their turn.

**Exit codes** (`cli.py:45` has 0, 1, 3, 4, 5): add `ALARM = 6`. `--alarm-after` exits 6 when it raises (stderr line `HB-ALM-00x: <cause>`; `--json` adds `alarm: {code, cause, last_progress_at, age_s}`), 0 otherwise. Any other failure of the check (unknown run `1`, unreadable ledger `5`) is also non-zero: **a check that errors never reads as "no alarm"**. `.alarm_check` is touched at the **start** of every check, so a check that crashes after the stamp still counts as having run, and the task wrapper reports the failure.

**Choosing `--alarm-after`.** It must exceed the longest honest gap between events. One budget covers every turn (ADR-0015 section 3), so the longest gap is about `budget_seconds` plus archive time. The runbook sets `--alarm-after = budget_seconds + 1800`, and `bench plan` prints it (surface list, ADR section 8). Too small causes false alarms; the worst-case envelope, not the mean, is the basis (ADR section 8).

### 6.3 The channel (ADR-0021 section 7: "chosen at `/design-slice`")

**Chosen:** a **Windows Task Scheduler task** every 15 minutes, in a nightly repetition window, running `powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/alarm-task.ps1 -RunId <id> -AlarmAfter <s>`. The script runs `bench status <id> --alarm-after <s>`; on **any** non-zero exit it (1) shows a persistent **Windows toast** (`<toast scenario="reminder">`, stays until dismissed), and (2) if the user environment variable `HB_ALARM_NTFY_TOPIC` is set, POSTs the same text to `https://ntfy.sh/<topic>` (priority high). The payload is the run id, the `HB-ALM` code, the cause and the age. No task content, path or credential.

| option | verdict |
| --- | --- |
| toast + task wrapper (chosen) | zero third party, no secret, works while the operator is signed in; needs "run only when user is logged on" |
| ntfy phone push (optional, off by default) | the away-from-terminal path ADR-0021 asks for. The topic name is a bearer secret: it lives only in a user environment variable, never in the plan, ledger or repo. Self-hosting is possible. Egress: one HTTPS POST of the payload above |
| e-mail, Teams or Slack webhook | rejected: needs stored credentials or a webhook secret |
| `msg.exe` | rejected: absent on Home editions; no persistence |
| event log only | rejected: nobody watches it (the ADR's own test: "reaches the operator") |

**Window, not always-on.** The task has a daily trigger at the start of the run window with a repetition interval of 15 minutes for the window's length. This is how a *planned* night boundary does not nag all day: a pause is the engine ending, the alarm window ending, and the operator re-registering or letting the next night's trigger fire. `bench stop` is **not** a pause: the next resume finishes the stop and exits 3, launching nothing (R-100).

**Runbook path:** `docs/runbooks/resume-and-alarm.md` (new folder; X-K2 creates it): the `schtasks` command, the window, how to choose `--alarm-after`, how to set `HB_ALARM_NTFY_TOPIC`, what each `HB-ALM` code means and the action, and the one-line check that the task is enabled (`Get-ScheduledTask`). The wrapper `tools/alarm-task.ps1` and its test are new paths (seam, section 12).

**Alarm of the alarm.** If the task is disabled or failing, the check never stamps `.alarm_check`; `bench status` and `bench campaign status` print the `HB-ALM-003` warning while an engine is alive. A human who never looks is the accepted residual (ADR-0021 section 7).

**Spike S-K1 (run in this slice).** `powershell.exe` 5.1.26100.9549: the WinRT toast types load and `ToastNotification` / `CreateToastNotifier` objects build with the PowerShell AUMID `{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe`, exit 0 [Observed]. A toast was **not shown** (an interactive session is needed) and `notifier.Setting` printed empty [Observed]. Display, persistence and dismissal are **Inferred** and belong to the drill. `pwsh` 7 does not load these types; the task must name `powershell.exe` (5.1) [Inferred from the WinRT projection; X-K2 confirms in its first commit].

## 7. Disk and worst case (ADR-0021 section 8)

- `_free_bytes` calls `shutil.disk_usage` with no handler (`engine.py:893-897`). An `OSError` raised in the loop today ends the engine, against the ADR ("if the query itself fails, the measurement is recorded `not recorded` and launching continues"). X-K1 moves the check into `_launch`, before `cell.launch_intent`; `free_bytes` is the measured value (int) or absent ("not recorded") on a failed query; the stop reason `disk low` with `HB-RUN-004` is the existing code. Tests: `test_engine.py::test_disk_query_failure_is_not_recorded_and_launching_continues` (monkeypatch `shutil.disk_usage` to raise; red today: the engine raises), `::test_launch_intent_records_free_bytes` (red today: no field), `::test_disk_low_stops_launching_before_the_intent` (red fixture: the stop row precedes the cell's intent).
- `bench plan` prints, per task, **worst-case slot occupancy** = `budget_seconds` + measured archive and snapshot copy time, and **worst-case grading** = sum of the graders' `grading_step_timeout`, beside the measured means (X-K2, `cli.py` `cmd_plan` print only; the numbers come from fields the plan already freezes). It does not change `plan.json`.

## 8. Surface list (E7: store, model, service, wire, client, UI, compute reader)

| layer | change | owner · phase |
| --- | --- | --- |
| model | `run_lifecycle.tla` v6, `safety.cfg`, `turns.cfg`, `check_models.py` data rows | W1-K (this slice, done) |
| model docs | `docs/design/run-lifecycle-model.md` mapping rows (`ReconcileRecord` under `stopApplied` to the classifier's stop input; `Resume` unguarded to `resume_run`'s stop branch; `turnNext` to `turn_ended.next`; `NoResumeAfterStop` reads `NoLaunchAfterStop`, R6.8d) and `models/README.md` line | X-K1 (E3 hub row, by seam, section 12) |
| store | `run.resumed`, `segment.abandoned` on engine segments, `cell.outcome.resume`, `cell.launch_intent.free_bytes`, segment id `engine-<unix>-r<NNN>`, `.alarm_check` | X-K1 (rows, segment id, engine); X-K2 (`.alarm_check`) |
| service | `resume.py` (`classify`, `stop_recorded`, `history`, `resume_run`), `archive.recover_archive`, `Engine` accepting a resume plan, pid-gone check | X-K1 |
| service | `alarm.py` (`check`), stamp writer | X-K2 |
| ledger projection | `views.segment_rows`, `views.load.completed` (D-K5), `views.verify` abandoned-head rule | X-K1 (seam for the `views.py` hunk, section 12) |
| lifecycle mirror | `lifecycle.py`: second `cell.launch_intent` allowed (R2 relaunch); `cell.outcome` with `resume` object; replay rule `NoLaunchAfterStop` (a `cell.launch_intent` after a stop row is rejected; a `run.resumed` after a stop row is **accepted**, R-100) | X-K1 |
| wire | `bench-status/2` (`last_progress_at`, `resumes`), exit code 6, `HB-RUN-008/009`, `HB-CELL-118/119`, `HB-ALM-001..003` (confirmed, section 9) | X-K1 (`errors.py`), X-K2 (`status.py`) |
| client type | `status.Status` and `status.parse` (accept `/1` and `/2`) | X-K2 |
| UI (CLI text) | `bench status` and the completion summary: "resumed n times" with each time and segment id; per resume, cells skipped / launched / reconciled, each reconciled cell with its code and phase; `HB-ALM-003` warning line | X-K2 |
| UI (report) | the report header lists the resumes (`report/html.py` reads `resume.history`) | X-K2 text; `report/html.py` hunk by seam to X-H2/X-A3 (section 12) |
| entry | `cli.py` `cmd_run`: the `events`-exists branch calls `resume.resume_run`; `cmd_plan` envelope lines; `status --alarm-after`; `campaign status --alarm-after` | **X-K2** |
| compute reader | `views.rows` already reads all engine segments; `grade/runner.py` abandons an unfinished pass (no change); `resume.classify` is the only reader of `resume.stop_recorded`; `status` and `alarm` need no stop exception | X-K1, X-K2 |
| docs | `docs/runbooks/resume-and-alarm.md`; `tools/alarm-task.ps1` | X-K2 |

## 9. HB codes (W0 section 11 confirms or drops)

Confirmed: `HB-CELL-118`, `HB-CELL-119`, `HB-RUN-009`, `HB-ALM-001..003`. `HB-RUN-008` is **confirmed, re-pointed** (W0 rev 6.8 section 11, R-100 condition 4): the stopped run's **exit-3 reason**, no longer a refusal. Every finish-the-stop resume emits "run is stopped: n cells recorded stopped, m archived, 0 launched", and so does an idempotent re-run with zero actions. Reused unchanged: `HB-RUN-004`, `HB-RUN-005`, `HB-CELL-117`, `HB-LED-005`, `HB-LED-008`, `HB-IDN-001`, `HB-USR-002`. **None dropped, none added.** `HB-ALM-001` carries "not running" and "stalled" as its cause text (W0 merge preference).

## 10. Failure-mode analysis

| failure | effect | detection | response |
| --- | --- | --- | --- |
| the engine dies during a resume | partial reconcile rows | next resume reads the ledger | W13, W14: same decisions; abandoned rows are not duplicated (a segment already named is skipped) |
| the engine dies mid-stop | cells without outcome; the run holds a stop row (one of the three windows) | the alarm fires (pending cells, free lock); `bench status` shows them pending | `bench run <run_id>` finishes the stop: `stopped` outcomes, archive, exit 3 with HB-RUN-008. No unreachable state (W12) |
| a pid is reused by another process | the pid check waits, then reports "still alive" | log line `resume.pid_alive` | the cell is **not touched**; the resume finishes the others and exits 3; run it again later (idempotent). `HB-RUN-002`'s wording (a slot held) is the analogy |
| `shutil.disk_usage` raises | today the engine dies | section 7 | `not recorded`, launching continues |
| `last_progress_at` unreadable | cannot judge progress | the check | raises (fail closed) |
| the alarm task is disabled | no alarm | `HB-ALM-003` warning | accepted residual |
| time skew between the engine host clock and the check | gap wrong | same host (single machine, ADR scope) | none; a different host is out of scope |

## 11. Telemetry (instrumentation over inference)

Emitted on the normal path, no flag: `resume.started {run_id, segment_id, dead_segments, cells_total, pending}`, `resume.classified {counts per action C0..C7}`, `resume.cell {cell_id, action, code, phase, turn, duration_ms}`, `resume.done {skipped, launched, reconciled, duration_ms}`, `alarm.check {run_id, outcome: ok|HB-ALM-001|HB-ALM-002|error, age_s, gap_s, duration_ms}`, `launch free_bytes`. Questions answered: how long does a resume take, how many cells does a night lose to a crash, which window kills them, how often does the alarm fire. Every path degrades to "not recorded", never to a plausible zero.

## 12. Seams, decisions, open items

| id | what | to | fallback built meanwhile |
| --- | --- | --- | --- |
| DR `req-01M41V2MC1RTCBB4APR3TSXEYP` | crash during a stop | owner-fable | **closed: R-100 ruled (B)**; (A) refused; applied in rev 1.1 |
| seam X-K1 -> X-K2 (brief item 7) | the `cmd_run` resume branch. **X-K1** lands `resume.resume_run(run_dir, root, plan, cfg) -> RunSummary` as a skeleton in its first commit and joins first; **X-K2** replaces `cmd_run`'s `HB-USR-002 "already started"` lines (`cli.py:156-158`) with the call, rebased on X-J1's R6.5b `status.py` hunk and X-K1's join. X-K2 does not wait on X-K1 for the alarm work, only for this one hunk | Coordinator | X-K2 lands everything else and leaves the hunk to its second dispatch |
| seam | `views.py` E3 hunks (`segment_rows`, `completed`, verify rule) have no E3 owner in W0 section 13 | `coord-opus-e1e4` | X-K1 edits them in its own commit and names the hunk |
| seam | `docs/design/run-lifecycle-model.md` and `models/README.md` rows (W0 section 13 hands the model to X-K1 after W1-K) | `coord-opus-e1e4` | listed in section 8; X-K1 appends |
| seam | new paths `tools/alarm-task.ps1`, `tests/test_alarm_task.py`, `docs/runbooks/resume-and-alarm.md` | `coord-opus-e1e4` | the script text lives inside the runbook as a fenced block until the paths are granted |
| seam | `report/html.py` resume header lines | X-H2 / X-A3 | CLI text only |
| open (E5, not here) | the drill record that `bench campaign register` checks (ADR section 7) has no record kind in W1-C; the drill is out of scope | X-C / E5 | none; flagged |
| ADR amendment text | D-K1 (PID), D-K2 (named job), D-K4 (three stop rows), D-K5, R-100 | Coordinator | **done**: ADR-0021 Amendment 1 on `main` (W0 rev 6.8, R6.8d). The section 4 row 5 reasoning (job_active_processes) is replaced by D-K2 and stays this design's statement |
| seams R6.8a-c (W0 rev 6.8) | `views.py` hunks for X-K1 beside X-A3's `CellView.pack` rename, disjoint, after X-J1's join (R6.8a); X-K2's `tools/alarm-task.ps1`, `tests/test_alarm_task.py`, `docs/runbooks/resume-and-alarm.md` under four conditions: Windows-only `-DryRun` test, the ntfy topic never printed, `powershell.exe` 5.1, frontmatter on the runbook (R6.8b); the `report/html.py` header as one X-K2 hunk after X-A3c and X-K1 join, no-resume header byte-identical, one wording with `bench status` (R6.8c) | X-K1, X-K2 | **granted**; the three rows above stand as the builders' paths |
| finding F-1 (not a request) | R-100 says a finish-the-stop resume does no grading; the live engine grades after a stop and the model keeps the engine's grade enabled (section 5.3) | RV-DS, owner-fable | recorded; no model exception added |

Seam request ids, in table order: `views.py` and model docs `req-01M41XGYS25EXAHKPZV5EE1QT2` (R6.8a); X-K2's new paths `req-01M41XGZ3WV678S30APNX8HBMK` (R6.8b); the report header `req-01M41XGZF3ACCY2QB5Y3ATYDQK` (R6.8c). Decision request: `req-01M41V2MC1RTCBB4APR3TSXEYP` (R-100).

## 13. Commit order

**X-K1 (Codex, E3):** K1 skeleton `resume.resume_run` (today's refusal) and `tests/fake_acp_agent.py` hang options if X-J1 did not land them; K2 `tests/test_resume.py` and the golden-ledger helper, red; K3 `errors.py`, `lifecycle.py`, `views.py` hunks, abandoned-head verify; K4 `classify` and `stop_recorded`; K5 `recover_archive`, sweeps; K6 `Engine` resume path, segment ids, disk check in `_launch`; K7 model-docs rows. X-K1's crash-window tests are the gate's entry condition for X-K1 (RV-TA W1-B R2-2).
**X-K2 (Agy, E3):** two dispatches. First: `alarm.py`, `status.py` (`last_progress_at`, `bench-status/2`, `HB-ALM-003`), `--alarm-after`, exit 6, `tests/test_alarm.py`, `tests/test_status.py`. Second: the `cmd_run` branch (after X-K1 joins), `cmd_plan` envelopes, `campaign status --alarm-after`, the runbook and `tools/alarm-task.ps1`.

**Alarm tests (X-K2), all through the real `cli.main`:** `test_alarm.py::test_stale_progress_exits_6_with_alm_002` (fresh heartbeat, last row 2 h old, pending cells. Red because `exit == 6` fails: X-K2's first commit adds the flag as a skeleton that returns 0, so the failure is the assertion, not argparse's unknown-argument exit 2); `::test_free_lock_with_pending_cells_exits_6_alm_001`; `::test_stalled_heartbeat_exits_6`; `::test_complete_run_exits_0`; `::test_finished_stop_is_silent` (after a finish-the-stop resume no cell is pending: exit 0, by the record); `::test_mid_stop_crash_alarms` (a stop row in each of the three windows, cells without outcome, free lock: exit 6 with `HB-ALM-001`; red fixture for the absence of a stop exception); `::test_launch_stop_with_pending_cells_alarms`; `::test_pending_zero_does_not_raise_alm_002` (long grading pass: fresh heartbeat, old last row, no pending); `::test_unreadable_progress_fails_closed`; `::test_check_touches_alarm_stamp_first`; `::test_alm_003_warning_when_stamp_is_old`; `::test_campaign_alarm_skips_never_started_runs`; the wrapper `test_alarm_task.py::test_nonzero_exit_produces_payload` runs `tools/alarm-task.ps1 -DryRun` with a stub `bench` for exit 0, 1, 5, 6 and asserts the payload for the last three and none for 0 (red fixture: the script before the toast branch). Mutants (`tests/mutations/alarm.json`): M-HEARTBEATONLY (reads the lock mtime as progress: separates ALM-002 from fresh-heartbeat stall), M-GE (`>=` for `>`), M-UNITS (ms for s), M-ZEROISOK (an error returns 0), M-STOPEXEMPT (a stop row silences the alarm: separates `test_mid_stop_crash_alarms` from `test_finished_stop_is_silent`).

## 14. Stage 4 self-check (`definition-of-done.md`)

- Data model first, grain declared, derived counts not stored: done (section 2).
- Testability floor items 1-5 per named test: done (section 4 columns (a)-(e); alarm tests in section 13 name the red assertion; the alarm sweep (e) is the `rg "last_progress"` count that X-K2 pins at its skeleton).
- Model before code, TLC output in the doc, seeded variants rejected, `tests/test_check_models.py` and `check_models.py --quick` green: section 5.4.
- Surface list from store to compute reader: section 8.
- Unmet or provisional: finding F-1 (grading after a finish-the-stop, section 5.3); spike S-K1 shows API presence only; counts for the `rg` sweeps are taken by the builders on their base; the drill is out of scope; `report/html.py` header is a seam.

## Gate record

| lens | verdict | line |
| --- | --- | --- |
| RV-TA (Test Architect, hard veto) | pending | |
| RV-DS (Distributed Systems, hard veto) | pending | |
| RV-SRE (SRE, hard veto) | pending | |
| RV-PAT (Patterns Expert) | pending | |
| RV-SIM (Simplifier, soft veto) | pending | |
