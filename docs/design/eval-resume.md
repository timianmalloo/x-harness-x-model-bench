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
  to one ADR-0021 section 4 action; one predicate `resume.has_work` is the only definition of remaining work, shared by the resume and the alarm (R-102);
  the refusals (including an unrepairable archive) run in a fixed order under the run lock, before any row is written; the dead engine's segments
  are marked abandoned, never written into; one `run.resumed` row per resume is the whole resume record (counts are
  derived). A resume of a stopped run finishes the stop (R-100) with the engine's own post-stop tail (R-101): it launches nothing, records `stopped`
  for every intent-without-outcome cell, archives, grades, writes `run.completed{grading}` and exits 3; the model's invariant is `NoLaunchAfterStop`,
  and no liveness property carries a crash exception. The TLA+ model also settles the two resume branches W1-J left provisional by the
  recorded `next` of each turn, and TLC rejects every new seeded variant. Liveness is the newest `recorded_at` over the segment tails; the alarm is a scheduled Windows task whose
  primary and required channel for an unattended run is an ntfy phone push (R-102), edge-triggered with a delivery log; the toast is optional and joins at the E5 drill.
---

# Design: plan-level resume, liveness and the alarm channel (W1-K)

**Session** `w1k-resume-e1e4`, revision 1.1 `w1k-resume-r2-e1e4` (R-100), **revision 1.2 `w1k-resume-r3-e1e4`** (the gate revision: R-101, R-102 and the five lens reviews applied; main merged in) · **branch** `design/eval-resume` · **tier** T2 · **fan-out** 0 · base `66ec885f` (main with W0 rev 6.7, R-87..R-99, W1-J).
Builds: **X-K1** (E3: `resume.py` with `has_work`, `engine.py`, `errors.py`, `identity.py`, `lifecycle.py`, the `cmd_run` hunk of `cli.py`, the E3 model hand-over) and **X-K2** (E3: `status.py`, the rest of `cli.py`, `alarm.py`, the runbook, the ntfy wrapper). Not in scope: the alarm-channel **drill** (kickoff Not-in-scope), any `src/` file, ADR text.

## Status table

| item | state |
| --- | --- |
| Data model (resume record, segments, alarm state) | done, section 2 |
| Resume protocol and the classifier | done, section 3 |
| Every ADR-0021 section 4 row mapped to a kill-then-resume test by node id | done, section 4 |
| `NoLaunchAfterStop` (R-100), the two provisional branches settled, TLC run | done, section 5 (commands, counts, exit statuses recorded) |
| Alarm channel chosen (ntfy primary, R-102), runbook path fixed | done, section 6 |
| Surface list, X-K1 / X-K2 split (the `cmd_run` hunk now X-K1's), seams | done, sections 8 and 12 |
| Gate record | five lines copied (all PASS WITH CONDITIONS); every finding has a row in the Review disposition table |
| F-1 (grading after a finish-the-stop) | **closed: R-101 (DR-K2)**: the resume takes the engine's post-stop tail |
| DR-K3 (R-102) | one `resume.has_work`; ntfy primary and required unattended; applied in rev 1.2 |
| `cmd_run` hunk | **moved to X-K1** (TA 3, PAT 1); seam `req-01M420GY3H75665W0N5T04NHRQ` filed to `coord-opus-e1e4` |
| Decision request `req-01M41V2MC1RTCBB4APR3TSXEYP` (crash during a stop) | **closed: R-100 (DR-K1) ruled (B)**; (A) refused; applied in rev 1.1 |
| W0 rev 6.8 seams R6.8a-c and ADR-0021 Amendment 1 (D-K1, D-K2, D-K4, D-K5, R-100) | granted on `main`; cited in section 12 |

## 1. Responsibility, and what this design decides

ADR-0021 fixes the behaviour. This design decides what the ADR left open and corrects it where the code disagrees. Each correction is a **verified fact** read on `66ec885f`, stated with its source.

| # | decision | why (evidence) |
| --- | --- | --- |
| D-K1 | The refusal "naming the PID" becomes "naming the heartbeat age and the lock path". | `oslock.RunLock.acquire` writes no PID (`oslock.py:52-61`); `msvcrt.locking` is mandatory on Windows, so a second process cannot read bytes under the lock. A PID needs a byte-range design that buys nothing the age does not. **ADR text to amend (draft status).** |
| D-K2 | "Terminate the named job if present" becomes "confirm the recorded process is gone". | The Job Object is **unnamed** (`procs.py:216`, `CreateJobObjectW(None, None)`) and kill-on-close (`procs.py:220`), so after the engine dies the OS has already ended the tree and there is no job to name. The check is `attempt.process_started.pid` gone, waited for at most `pid_wait_s` (30), where **gone** means: no process with that pid, **or** one whose creation time differs from the recorded `process_started.created_at` (`OpenProcess` plus `GetProcessTimes`; a recycled pid is a different process, DS 4). Where no `created_at` was recorded (the crash fell before the row), kill-on-close already ended the tree and the cell is gone by definition. `os.kill(pid, 0)` is forbidden on Windows (CPython maps any non-console signal to `TerminateProcess`, Python docs for `os.kill`; not run); the check uses `OpenProcess(SYNCHRONIZE)` and a zero-timeout wait on win32. |
| D-K3 | A never-prompted cell's old cell folder is **discarded before the relaunch**. | `workspace.cell_working_copy` raises `HB-USR-002 "...already exists; a cell's working copy is built once"` (`workspace.py:195`). ADR row 2 never mentions it, so the relaunch would fail on the first real crash. Safe because nothing was prompted: no work exists to archive. |
| D-K4 | The stop-refusal predicate reads **three** rows, not two. | `engine._read_controls` appends `control.applied{control: stop}` and *then* calls `_apply_stop`, which appends `run.stopped` (`engine.py:518-524, 449-453`); an answered `stop` decision appends `decision.resolved{option: stop}` before `run.stopped` (`engine.py:353-356`). A crash between any two leaves no `run.stopped`. Predicate: `run.stopped` **or** `control.applied{control: "stop", effect: "applied"}` **or** `decision.resolved{option: "stop"}`. `run.launch_stopped` alone (disk low, spend-cap default) is **not** a stop: that run resumes once the cause is cleared. The predicate is **one input** to the classifier (3.2), not a refusal (R-100). ADR-0021 Amendment 1 carries this correction. |
| D-K5 | A run that holds `run.completed` can still be resumed, and `completed` is redefined. | A launch stop (HB-RUN-004, disk low) ends the loop with `ended_whole` true, so the engine writes `run.completed` with cells never launched (`engine.py:413-425`); that run is the main multi-night case. `views.load` sets `completed = any(run.completed)` (`views.py:542`), which would read "complete" while the resumed engine runs. New rule: **complete iff a `run.completed` row follows the last `run.resumed` row (or there is none).** Resume of a run for which `has_work` is false (D-K12) is a no-op (no segment, no row). **The stop row, not `run.completed`, decides the exit status** (R-101): no stop row, exit 0 "run is complete"; a stop row, exit 3 with the HB-RUN-008 line. A finish-the-stop resume writes `run.resumed` first and `run.completed` last, so the one completion rule holds. |
| D-K6 | A run whose `events` folder exists but holds no `run.started` row is **started** by the resume. | `cmd_run` and `Engine.run` both refuse once `events` exists (`cli.py:158`, `engine.py:372`); a crash between segment creation and the first row would block the run for good. |
| D-K7 | Engine segment ids gain a resume ordinal: `engine-<first unix>-r<NNN>` (three digits, zero padded; the first incarnation keeps `engine-<first unix>`). **The ordinal is the highest `-rNNN` suffix on disk over all three facts, plus one; the base stamp is the first incarnation's, never a new clock reading.** One factory, `open_engine_segments(run_dir, ordinal)`, is used by `Engine.run` and `resume_run` (PAT 7). | `SegmentWriter.create` opens `xb`, so two incarnations in one second collide. `views.rows` sorts segment file names and needs `engine-` as prefix (`views.py:64, 87-99`); zero padding keeps `r010` after `r009`. A count of `run.resumed` rows would pick a taken name after a crash between the exclusive create and the row; a new wall-clock stamp would sort a resume before its predecessor after a clock step back (DS 5, SRE 3). |
| D-K8 | Engine segments marked `segment.abandoned` **stay readable**; the marker pins their head. | A grading segment abandoned is skipped by views (`views.py:93`); an engine segment holds the run's history and must not be. The marker's `head_hash` and `line_count` are checked by `bench verify` (new rule, section 3.6). |
| D-K9 | **Withdrawn (R-100).** Option A had added a `StopCrashed` disjunct to four liveness properties of the model (section 5). | It existed because option A refused a resume after a stop, so the cells a crashed stop was killing kept no outcome. No liveness property carries a crash exception. Under finish-the-stop, `Resume` and `ReconcileRecord(c)` (which records `stopped`) are already in `Fairness`, so the four promises hold through a crash after `ApplyStop`. |
| D-K10 | The invariant is **`NoLaunchAfterStop`** (`~flags["launchAfterStop"]`, the existing flag set by `WriteIntent` and `StartCell`), stated on the earliest of the three stop rows (`stopApplied`). `NoResumeAfterStop` is dropped. | R-100 condition 2: the invariant ADR-0021 section 2 protects is no launch after a stop. The model collapses the three rows into one step, which is at least as early as the code's. `Resume` takes no stop guard. |

| D-K11 | **Run-level state is rebuilt from the ledger before step 7** (DS 2, 8, 9). Open decisions (`decision.requested` with no `decision.resolved`/`superseded`), `applied_controls` (uuids of `control.applied`), the spend cap and spend total (the `SPEND` rows) are restored. A `control/<uuid>.json` whose uuid is in the ledger is deleted, not re-applied. Controls are read **once before step 7**, so an operator's `stop` file written before the crash is honoured before any relaunch. A finish-the-stop appends the `supersede_all` rows for every open decision, as `_apply_stop` does. A stop's code is read from `decision.requested.kind` (`spend_cap` gives HB-RUN-007), not from the `decision.resolved` row. | `engine.py:335-360, 393-394, 449-457, 510-530` keep these in memory; without the rebuild a decision stays open and pauses launching for ever, a control is applied twice, and a multi-night run overspends its cap by one night per crash. |
| D-K12 | **One predicate, `resume.has_work(plan, rows) -> bool`, is the only definition of remaining work** (R-102, DR-K3). It is true iff any of: (1) a cell with `cell.launch_intent` and no `cell.outcome`; (2) a cell with no `cell.launch_intent` **and no stop row** (`stop_recorded(rows)`; `run.launch_stopped` alone is not a stop); (3) a `cell.outcome` with no `cell.archived`; (4) no `run.completed` after the latest `run.resumed` (or `run.started`). Step 4 "nothing to do" is `not has_work`; the alarm's "pending" is `has_work`. It lives in `resume.py` (X-K1); `alarm.py` imports it and carries no pending logic of its own. | R-102 item 1: two definitions of "work left" (section 6.2's no-outcome count against step 4's four conditions) was the defect (SRE 1, 2; PAT 2; DS 1b). A never-launched cell is not work once a stop row exists; "n cells never launched" is derived and printed by `bench status`, never stored. |
| D-K13 | **A resume that leaves a cell untouched (pid still alive) writes no grading pass and no `run.completed`** (DS 7). It exits 3 with its own line `run is not finished: cell <id> process still alive, run again` (not HB-RUN-008) and one `resume.cell_deferred` event (SRE 10). `has_work` stays true (1), so the alarm fires. | Under R-101 the tail would otherwise write `run.completed` over a pending cell and silence the alarm. |
| D-K14 | **An unrepairable archive is a read-only refusal in step 3** (DS 6): a `cell.archived` or `archive_files` row recorded while its folder is absent refuses with `HB-LED-005` naming the folder, before step 5 writes anything. | The check used to run after step 5 had written `run.resumed` and three segments, so each retry added rows and failed again. |

## Patterns used (RV-PAT 5)

| need | pattern |
| --- | --- |
| resume | write-ahead-log recovery plus a reconciliation loop: the ledger is the state, `classify` is the diff, the executor applies idempotent actions |
| classifier | Decision Table with a Special Case (the stop flag), a pure function |
| W13, W14, the idempotent finish-the-stop | Idempotent Receiver |
| `segment.abandoned` | Fencing of a dead writer (the marker pins `head_hash`) |
| the alarm | Watchdog polled from outside the process (a scheduled check); `HB-ALM-003` is a lint of the watchdog, not a second watchdog (deferred to E5, section 6.3) |

## 2. Data model (settled first)

**Aggregate.** `Run` (identity `run_id`). The invariant it guards: *one engine incarnation writes at a time, and nothing launches after a stop* (a resume may still run, to finish the stop). A resume is a **state transition of the run**, not a new entity, so it creates no second run id (ADR-0021 Alternatives, DR-E1). Cells are referenced by `cell_id`. Bounded context: the run engine.

**Durable representation** (the pack default: append-only facts, derived views).

| fact | grain: one row is exactly one … | store | written by | history rule |
| --- | --- | --- | --- | --- |
| `run.resumed` | resume of one run by one engine incarnation | `events` fact, **first row** of the new engine segment | resume, before anything else | append-only; never updated. The resume's order is the order of segment ids; **no `n` is stored** |
| `segment.abandoned` | engine segment of one fact that a resume found unsealed | `events`, rows 2..k+1 of the new segment (one per `fact/segment_id`) | resume | append-only; the existing ADR-0006 row, same fields as the grading pass writes (`grade/runner.py:243`): `code HB-LED-004, fact, segment_id, line_count, head_hash, error` |
| `cell.outcome` by reconciliation | reconciled cell, once | `events` | resume | the existing row; **adds** one field `resume: {segment_id, turn, phase}` where `phase` is `mid-turn`, `between-turns` or `turn-complete`. This carries the RV-SRE 8 hand-off (W1-J next step 1). The `code` is `HB-CELL-118` or `HB-CELL-119`. `resume` also carries `rule` (`"C2"`..`"C6"`) and, under a stop, `stop_row` (`control.applied`, `decision.resolved` or `run.stopped`), so an operator can tell which classifier row and which ledger row decided the cell (SRE 11a) |
| `cell.launch_intent` | launch of one cell | `events` | engine | existing row; E3 adds `free_bytes` (W0 section 12). A relaunch after R2 writes a **second** `cell.launch_intent` for the same cell: legal, because the first never reached a prompt. `lifecycle.AT_MOST_ONCE` must allow it (surface list) |
| `last_alarm_check_at` | the newest alarm check of one run | file `runs/<run_id>/.alarm_check`, **mtime only** | `bench status --alarm-after` | overwritten; **not** a fact, never in the ledger (ADR-0021 section 7). **Deferred to E5 with `HB-ALM-003`** (SIM 4); the section stands as the E5 design |
| wrapper alert edge state | the last alert sent for one run | file `runs/<run_id>/.alarm_edge` (JSON `{code, first_sent_at, last_sent_at}`), beside `.alarm_check`, outside the repo | `tools/alarm-task.ps1` | overwritten; not a fact (R-102) |
| wrapper delivery log | one wrapper run | a local text file, one line per run: time, exit code, `push ok` or `push failed: <exception type>`; **never the topic or a URI**; path named in the runbook | `tools/alarm-task.ps1` | append-only text; `bench status` does not read it |

`run.resumed` fields: `kind, run_id, plan_hash, segment_id` (equals the file's stem; a test asserts it), `trace_id` (the plan's trace id, unchanged: one trace per run across resumes). Stamped by `ledger.stamp` (`recorded_at`, `mono_ns`), so the resume's time is the row's `recorded_at`.

**Derived, never stored** (derive-don't-store, DM): `resumed n times` (count of `run.resumed`), each resume's time and segment id, `cells skipped / launched / reconciled` per resume, `last_progress_at`, the pending set, `completed`. One reader computes them: `resume.history(run_dir) -> list[ResumeRecord]` over **per-segment** rows (a new `views.segment_rows(run_dir, fact) -> list[tuple[str, list[dict]]]`; `views.rows` flattens and loses the segment). `ResumeRecord = (n, at, segment_id, skipped, launched, reconciled: tuple[(cell_id, code, turn, phase)])`; `skipped` = cells terminal and archived in earlier segments; `launched` = `cell.launch_intent` rows in this segment; `reconciled` = `cell.outcome` rows in this segment carrying `resume`. A cell that this resume *completes* normally after relaunch is `launched`, not `reconciled`.

**Why not a counter or a status row?** Two definitions of one quantity is a defect signature (DM); the segment list is already the truth.

## 3. The resume protocol

`bench run <run_id>` (the cli branch, X-K2) calls `resume.resume_run(run_dir, root, plan, cfg) -> RunSummary` (X-K1). It is idempotent: a second call over the same ledger makes the same decisions (section 4, W13/W14).

### 3.1 Order of operations

1. `plan.load_confirmed` (existing). If `events` does not exist: this is a first run, take the existing path.
2. **Acquire the run lock** (`RunLock.acquire(.lock, code="HB-RUN-005")`). Held: refuse, naming heartbeat age and path (D-K1). **From here to the end the resume heartbeats the lock** (DS 3, SRE 8): inside the pid wait loop, between cell actions, and around the snapshot redo and `recover_archive` copies, with the engine's `_beating` wrapper reused for the whole of steps 5-8 including the grading tail. `lock_staleness` is 120 s (`plan.py:53`) against a pid wait of up to 30 s per cell. `resume.started` is emitted before the first wait.
3. **Refusals, fixed order, each reading the ledger and the disk only (nothing is written yet):**
   (a) run-side identity differs from the plan (ADR-0017 section 7; X-D's `identity_check`): `HB-IDN-001` with the diff;
   (b) `views.verify` has an error finding: `HB-RUN-009` naming the segment;
   (c) a `cell.archived` or `archive_files` row is recorded while its archive folder is absent: `HB-LED-005` naming the folder (D-K14). Unrepairable, so it must not grow the ledger on each retry (DS 6).
   A stop is **not** a refusal (R-100): `resume.stop_recorded(rows)` (D-K4's three rows) is read after (a)-(c) and sets the classifier's stop input (3.2). Order matters the other way now: a stopped run with a drifted identity or a broken chain must not be finished on a ledger that cannot be trusted. Test: a ledger failing (a) and (b) reports (a); a ledger failing (c) writes nothing (`test_refusal_writes_nothing`).
   **Run-level state is rebuilt** (D-K11) here, from the rows: open decisions, `applied_controls`, spend cap and total; stale `control/<uuid>.json` files whose uuid is in the ledger are removed; controls are read once.
4. **Nothing to do?** `not resume.has_work(plan, rows)` (D-K12, R-102: the one definition of remaining work, also read by the alarm). Then: no segment is created and no row is written. With no stop row print "run is complete" and exit 0; **with a stop row print the HB-RUN-008 line ("run is stopped: n cells recorded stopped, m archived, graded, 0 launched") and exit 3** (idempotent re-run, W12e). The stop row, not `run.completed`, decides the exit status (R-101; D-K5). Never-launched (C7) cells are not work once a stop row exists, so a finished stop reaches this step.
5. **Open the new segments** with the one factory `open_engine_segments(run_dir, ordinal)` (D-K7, PAT 7): `engine-<first unix>-r<NNN>` for `events`, `turn_usage`, `archive_files` (`SegmentWriter.create`, exclusive), the ordinal being the highest suffix on disk plus one. First `events` rows, in order: `run.resumed`, then one `segment.abandoned` per unsealed dead engine segment of each fact (head and count from `ledger.verify_segment`; a torn tail is ignored, not repaired). **The resume never opens the old file for append.** A crash anywhere after step 5 leaves a resume that the next resume classifies like any other (W13). A stray empty segment from a crash between two creates is skipped by the ordinal rule (r003 opens after an empty r002).
6. **Sweep** `sweep_temps(run_dir/"archive", lock)` and `sweep_temps(run_dir/"archive"/<cell>, lock)` for every cell folder (W0 section 4 rev 6.3). The caller's own wrong-pairing red test is in section 4. Before `archive_cell`, the resume cleans the cell home of seeded credentials as the engine's `finally` does (`launcher.clean`; DS 11, advice, RV-SEC to confirm).
7. **Classify** every plan cell with the pure function `resume.classify(plan, rows, stopped) -> list[Action]` (3.2), where `stopped = stop_recorded(rows)` is computed once in step 3 and passed in (R-100 condition 3 holds: the predicate is read once, as one input), and record `resume.classified` telemetry. If `stopped` and no `run.stopped` row exists (windows 1 and 2), write `run.stopped` in this segment now: code `HB-RUN-006` for a `bench stop`; for an answered `stop` decision the code is read from the `decision.requested` row's `kind` (`spend_cap` gives `HB-RUN-007`; DS 9). A finish-the-stop also appends the `supersede_all` rows for every open decision (D-K11). Then execute the actions of non-terminal cells in **plan order**, reconciliation before any launch (the model's `reconciling` gate). A cell whose recorded pid is still alive after `pid_wait_s` (gone means: no process, or a different creation time than `created_at`) is **deferred**: untouched, one `resume.cell_deferred` event (D-K13).
8. **Not stopped:** continue the engine loop as `Engine.run` does (launch the never-prompted cells in plan order under the existing parallelism, budget and disk rules), then grade and write `run.completed` as today. In-run grading is `run_pass`, which already abandons an unfinished pass and starts a new one (`grade/runner.py:228-246`); extractions already written are reused (write-once). **No new grading code.**
   **Stopped (finish-the-stop, R-100 and R-101):** restore `run_stopped` from the ledger before the loop (the engine after `_apply_stop` is already "launch nothing, drain, grade, `run.completed`, exit 3": `_stop_launching`, `run_stopped`; `engine.py:412-436`, where `ended_whole` ignores `run_stopped`). Run the same reconciliation with launching disabled: one flag read from rows, the same actions. The loop writes no `cell.launch_intent`, runs the archive step for every recorded cell, then takes the **live tail unchanged**: drain, the grading pass when `cfg.grade` is set (a failed pass is recorded in `grading` and never costs the run), `run.completed` with `grading`, seal, and exit 3 with the HB-RUN-008 line "run is stopped: n cells recorded stopped, m archived, graded, 0 launched". A stop finished live and a stop finished by a resume leave the same rows (R-101, DM7). **F-1 is closed by R-101** (section 5.3).
   **Deferred cell (D-K13):** if any cell was deferred in step 7, write neither the grading pass nor `run.completed`; print `run is not finished: cell <id> process still alive, run again` and exit 3 (a different line from HB-RUN-008, so an operator or script can tell "stopped" from "not finished").

### 3.2 The classifier (the ADR section 4 table, as a function of ledger rows only)

`classify` reads rows and a **stop flag** (`stop_recorded(rows)`, D-K4's three-row predicate, computed once and passed in: one input, not a second table; R-100 condition 3 wrote `classify(plan, rows)` and the signature differs only by that parameter, PAT 6) and nothing else (no filesystem, no clock), so every row of the table is a unit test and a fixture. Inputs per cell: `launch_intent`, `process_started.pid`, `prompt_sent{k}`, `turn_ended{k}.next`, `turn_snapshot_archived{k}`, `cell.outcome`, `cell.archived`, `cell.archive_failed`.

| # | recorded state (first match wins, top to bottom) | action |
| --- | --- | --- |
| C0 | `cell.outcome` and `cell.archived` | **skip** (a leftover workspace is `bench teardown`'s, not the resume's) |
| C1 | `cell.outcome`, no `cell.archived` (including a `cell.archive_failed` row) | **archive**: `recover_archive` (3.3). Never re-run the cell |
| C2 | prompt sent for turn k, no `turn_ended{k}` (a **crashed turn**, any k) | confirm gone (D-K2), record `failed (coordinator crash)` HB-CELL-118, `phase mid-turn`, archive (C1), **never relaunch**. **Stop set: record `stopped`** (below) |
| C3 | `turn_ended{k}.next == snapshot`, no `prompt_sent{k+1}` (**between turns**), snapshot event recorded | confirm gone, record `failed (coordinator crash between turns)` HB-CELL-119, `phase between-turns`, turn k+1 `NOT_RECORDED "turn k+1 not reached"`, archive with the turn-k snapshot, never relaunch. **Stop set: record `stopped`** |
| C4 | as C3, snapshot event **absent** | redo the snapshot (3.4), then C3 (**stop set: then `stopped`**; the redo still runs, because the archive must hold the turn-k tree). If the redo fails after bounded retry: record `failed (archive)` HB-CELL-117 (W0 section 11, reused), `phase between-turns`, archive, never relaunch. **Not modelled** (symmetric with `SnapFail`; `simplify:` ceiling one cell, trigger: a second observed failure shape) |
| C5 | a turn ended and none is owed: the last planned turn ended, or `turn_ended{k}.next` is `final`, `stop` or `cancel`, and no outcome (**the ELSE**) | confirm gone, record `failed (coordinator crash)` HB-CELL-118, `phase turn-complete`, archive (C1), never relaunch. The cell is **never** recorded `completed`: the outcome needs exit status and extraction that the resume cannot recompute without guessing. **Stop set: record `stopped`** |
| C6 | `launch_intent` and no `prompt_sent{1}` | confirm gone (D-K2), discard the cell folder (D-K3), **launch once** (a second `launch_intent`). **Stop set: record `stopped`, archive the working copy as is, launch nothing** (no discard: the folder is archived like any other) |
| C7 | no `launch_intent` | launch in plan order. **Stop set: no action** (a normal stop leaves never-launched cells unlaunched and unrecorded; `run.launch_stopped` and `run.stopped` are the record). A C7 cell is **work only while no stop row exists** (`has_work` clause 2, D-K12; R-102 refused a stored outcome for it) |

**The stop input (R-100 condition 3; the grading clause is superseded by R-101).** With the stop flag set, C2, C3, C5 and C6 record `cell.outcome{stopped}` instead of their rows above: cause `None`, no SPEND, `phase` as today, the `resume` object `{segment_id, turn, phase}` (it also says the resume, not a live worker, recorded it). The engine's kill-reason rule for `stop` (`engine.py:634, 654, 669`) is the source of "stopped", applied from the same rows: a cell with `launch_intent` and no outcome in a ledger holding a stop row was killed by the stop, because the stop row precedes the kill in `_apply_stop` and kill-on-close (`procs.py:216-220`) finished what the kill began. C0 and C1 are unchanged; C4 still redoes the snapshot first. **`run.launch_stopped` alone is not a stop** (D-K4): it sets no flag. `HB-CELL-118/119` stay the crash records of an un-stopped run and are never written for a stopped one.

A crashed turn is judged **before** between turns (C2 before C3): a cell that has a crashed turn 2 also has `turn_ended{1}`. The model's `ClassOf` has the same order. A `turn_ended` row with no `next` (a legacy single-turn row) reads `final` (W0 rev 6.5 condition 3).

**Settled provisional branches (W1-J asked W1-K).** `BetweenSnapped` is a guard on `next == snapshot` only: a turn that ended with `next = stop` took no snapshot and owes none, so waiting for one would block C5 forever (the model's `snapshot_when_stopping` variant). The final ELSE of `ClassOf` is exactly C5. The W1-J suggestion "`stop_reason == end_turn` in the 119 rule" is **declined**: `next` is the engine's recorded decision and the only reader input for "why turn n+1 was not sent" (W0 rev 6.5, condition 4); a second input would be a second definition.

### 3.3 `recover_archive` (X-K1 builds it; W1-B section 5 is its specification)

`archive.recover_archive(...) -> Recovery(result, missing_rows)` calls `archive.append_missing_rows` (X-J1, E2; one comparison, DM7) and `sweep_temps`. States: no final folder (sweep, then `archive_cell`); final folder, rows absent / partial / complete, `cell.archived` absent (append missing rows, then the event); rows or event recorded but folder absent (`HB-LED-005`, names it, changes nothing; **refused at step 3(c), before any row is written**, D-K14). X-K1's crash-window tests for it are the **entry condition for this design's gate** (RV-TA W1-B R2-2); they are rows C1/W10/W11 in section 4.

### 3.4 Snapshot redo (C4)

The working copy is turn k's tree because turn k+1 was never sent. The resume calls the same `engine._snapshot_turn` path (X-J1) so the code is one: `sweep_temps(archive/<cell>)`, then `publish_dir`; if `FileExistsError`, verify the folder and `append_missing_rows` with `HB-LED-008` (W0 rev 6.3), never re-publish. Quiescence: the old process tree is gone (D-K2); the check is the recorded pid, not `job_active_processes` (a fresh job reads 0 for processes that are not in it; the ADR's reasoning for row 5 does not hold and is replaced by D-K2).

### 3.5 What stays out

No change to the cell's launch seed, plan order or budget. A resumed cell's budget is not restarted because a crashed cell is never continued (C2, C3, C5) and a never-prompted cell has no clock yet (C6). `parallelism` and `disk_floor_bytes` apply unchanged.

### 3.6 `bench verify` after a resume

New rule (`views.verify`, X-K1 hunk): for each `segment.abandoned` row naming an **engine** segment, the segment verifies, is unsealed, and its `line_count` and head equal the row's; else `HB-LED-002` naming it. Without it, a dead segment could be cut back after the fact and the chain would still verify. `_sealed_record` is unchanged (it checks `run.completed.segment_heads` of the segment that holds it; with `run.completed` possibly in several segments it loops all of them, as today).

## 4. ADR-0021 section 4: every row, a kill-then-resume test, by node id

**Two techniques, both real code.** (T1) *Prefix fixture*: one real two-turn engine run is the golden ledger; a window is the golden ledger cut after row *i* (rows are fsynced in order, so a prefix is exactly what a crash leaves) plus the folder state the real functions leave at that point (a half-filled `*.tmp-*` from `publish_dir`, a renamed folder with no rows). (T2) *Real kill*: the real `cli.py run` in a child process against `tests/fake_acp_agent.py`, killed with `Popen.kill()` when the ledger shows the target row, then the real `cli.py run <run_id>`. T2 is used only where a window needs a second process or a polled row (W2, W11) and for the one wiring test. **The `cmd_run` hunk is X-K1's** (section 12; TA 3, PAT 1), so every T2 test can go green on X-K1's own branch.

Files: **`tests/test_resume.py`** (X-K1), **`tests/test_alarm.py`**, **`tests/test_status.py`** (X-K2). Test (a) = the assertion that fails today and why. Every red is an assertion on the real output (exit status, rows present), never an `ImportError` and never a mutant's failure (TA 4): X-K1's first commit is a **skeleton** `resume.resume_run` that implements today's behaviour (raise `HB-USR-002 "already started"`) with the `cmd_run` delegation already in place, so each test fails on its own assertion. The mutant that would also fail it is in column (d).

**The classifier windows are sweep rows, not tests of their own** (SIM 1, 2). `classify` is pure, so W1, W3, W3b, W6, W7 and W8 are rows of the exhaustive sweep below, each one assertion against the independent oracle, with no child process. The windows that need disk state or a second process stay:

| window | ADR row | ledger and disk state at the kill | node id | (a) assertion red today, and why |
| --- | --- | --- | --- | --- |
| W2 | `launch_intent`, no `prompt_sent{1}` | process started (pid recorded), cell folder present (T2: agent hangs in `session/new`) | `test_resume.py::test_window[W2_launched_not_prompted]` | `exit_code == 0, exactly one prompt in prompts_log and a second launch_intent` fails: the skeleton raises `HB-USR-002`. D-K3's discard is guarded by M-NODISCARD |
| W2b | as W2, folder already gone | crash after the discard, before the second intent (T1) | `...[W2b_folder_already_gone]` | `exit_code == 0 and the relaunch succeeds` fails today. The discard reuses `workspace._discard` and is a no-op on a missing folder, a partial clone, read-only files (DS 10) |
| W4 | `turn_ended{1}`, snapshot copy in flight | `archive/<c>/turn-1.tmp-<pid>-<uuid>` half filled, no event (T1) | `...[W4_snapshot_tmp]` | `no *.tmp-* left and snapshot event present and HB-CELL-119` fails |
| W4b | as W4 but the snapshot **event absent** (C4), and under a stop | event absent, stop row set, a C4 cell (T1) | `...[W4b_snapshot_event_absent_under_stop]` | `the turn-1 tree is archived and the outcome is stopped` fails today (exit code) |
| W4c | C4, the redo fails after bounded retry | `publish_dir` forced to raise (T1) | `...[W4c_redo_fails]` | `outcome.code == "HB-CELL-117" and phase == "between-turns" and archived` fails today; M-NOREDO (the redo dropped) |
| W5 | `turn_ended{1}`, snapshot folder renamed, event absent | final `turn-1/` complete; rows none / partial / all (three params) | `...[W5a_rows_none]`, `[W5b_rows_partial]`, `[W5c_rows_all]` | `exit_code == 0 and the event present and archive_files rows exactly the absent keys` fails today (skeleton raises). M-APPENDALL separates the partial and complete cases |
| W9 | outcome, archive tmp in flight | outcome row, `archive/<c>/attempt-1.tmp-...` (T1) | `...[W9_archive_tmp]` | `a verified archive and cell.archived and no tmp` fails |
| W10 | outcome, archive renamed, event absent | final `attempt-1/` with rows none / partial / all | `...[W10a_rows_none]` etc. | as W5, with `HB-LED-005` on a differing row |
| W11 | outcome and `cell.archived` | workspace still present (T2: poll for `cell.archived`) | `...[W11_done_skip]` | `no new row for this cell and the run exits 0` fails; leftover workspace untouched |
| W12 | stop, three windows (finish-the-stop, R-100, R-101) | `control.applied{stop}` only / `decision.resolved{stop}` only / `run.stopped` only, each with **five** cells: one each in the C2, C3, C5 and C6 states **and one C7 cell (no `launch_intent`)**, plus a variant of `[control_applied]` with a C4 cell (event absent) | `test_resume.py::test_resume_finishes_the_stop[control_applied]`, `[decision_resolved]`, `[run_stopped]` | asserts: every intent cell gains `cell.outcome{stopped}` with the resume object and is archived; **the C7 cell gains no `cell.launch_intent` and no `cell.outcome`**; no new `cell.launch_intent` for any cell; **a grading pass ran (the `grading` object, or its `error_code` with the pass made to fail) and exactly one `run.completed` follows the last `run.resumed`**; `run.stopped` present exactly once; exit 3; `bench verify` exits 0 (the new segments are sealed by `run.completed`). Red today: the skeleton raises `HB-USR-002`, so the exit-code and row assertions fail |
| W12d | `run.launch_stopped` only (disk low) | no stop row | `...::test_launch_stopped_is_not_a_stop` | `the unlaunched cells launch and the run resumes normally` fails today (no resume); M-LAUNCHSTOPPEDISSTOP |
| W12e | idempotent re-run | the W12 ledger resumed twice, with the C7 cell present | `...::test_finish_the_stop_is_idempotent` | the second call: **`has_work` is false, no `run.completed`, no segment, byte-identical ledger, exit 3, stdout holds the HB-RUN-008 text "run is stopped: 0 cells recorded stopped, m archived, graded, 0 launched"**. Fails today (no resume). M-DOUBLECOMPLETED (the second call re-writes `run.completed`) |
| W12f | stop row and `run.completed` after `run.resumed`, nothing to archive, a C7 cell | the end state of W12 (DS 1b) | `...::test_finished_stop_with_unlaunched_cell_is_a_noop` | exit 3, nothing written. M-NOPENDINGSTOP (C7 counted as work under a stop) |
| W13 | crash right after `run.resumed` | new segment holds `run.resumed` and k `segment.abandoned`, no reconcile row | `test_resume.py::test_resume_of_a_resume[W13]` | `exit_code == 0 and the final per-cell outcome map equals an uninterrupted resume` fails today (skeleton raises); the duplicate-abandoned-row check is the mutant column (M-WRITEOLD-like duplicate) |
| W13b | crash between the exclusive create and the `run.resumed` row (DS 5a) | a stray empty `events/engine-<t>-r002.jsonl` | `...[W13b_stray_segment]` | `exit_code == 0 and r003 is opened` fails today. M-ORDINALCOUNT (ordinal = count of `run.resumed`) |
| W13c | clock stepped back (DS 5b) | `time.time` mocked 1 h earlier at the resume | `...[W13c_clock_back]` | `the new segment sorts after the old ones in views.rows` fails today. The base stamp is the first incarnation's |
| W14 | crash mid-reconcile | some reconciled `cell.outcome` rows in the resume segment | `...[W14]` | `exit_code == 0 and the same per-cell outcome map as an uninterrupted resume` fails today (skeleton raises) |
| W15 | `events` exists, no `run.started` | segment created, zero rows | `test_resume.py::test_run_started_by_resume[W15]` | `exit 0` fails: `HB-USR-002` |
| W16 | `run.completed` with unlaunched cells | launch stop HB-RUN-004, run completed, 2 cells never launched | `test_resume.py::test_resume_after_launch_stop[W16]` | `the 2 cells run and status.completion goes "in progress" then "complete"` fails (D-K5); M-ANYCOMPLETED |

**Run-level state and liveness during a resume** (DS 2, 3, 4, 8, 9; SRE 8). `test_stop_window_with_open_decision` (the finish-the-stop appends the supersede rows and launching is not paused), `test_leftover_applied_control_not_duplicated` (no second `control.applied` for a uuid already in the ledger), `test_spend_total_survives_resume`, `test_stop_control_file_honoured_before_relaunch`, `test_stop_code_read_from_decision_kind` (a `spend_cap` decision gives `HB-RUN-007`). `test_resume_heartbeats_the_lock` (a stub cell whose pid wait exceeds `lock_staleness`, fake clock: `bench status` stays "alive"; M-NOBEAT). `test_recycled_pid_is_gone` (a live unrelated process holding the recorded pid with a different creation time resolves as gone; the pid-only check waits and fails; M-PIDREUSE). `test_pid_alive_defers_and_writes_no_completed` (pid-alive fixture: no grading pass, no `run.completed`, exit 3 with the "not finished" line that differs from HB-RUN-008, `has_work` true, the alarm fires; M-PIDKILL for a check that terminates the foreign process).

**Sweep over every row (the exhaustive net, now also the classifier's window tests).** `test_resume.py::test_every_ledger_prefix_matches_the_adr_table` runs `classify` on **every prefix** of the golden ledger, **for both values of `stopped`**, against two *independent* oracle tables keyed by the last row's kind (one per stop value), written from the ADR's wording and not from `classify`'s predicates. It also runs one **two-cell golden ledger with interleaved rows**. W1 (no `launch_intent`), W3 and W3b (crashed turn 1 and 2), W6 (between turns, snapshot recorded), W7 (`next = stop`) and W8 (the ELSE) are named rows of the oracle, each with its own assertion id (`...[W3_turn1_crashed]` and so on), so a failure still names the window. It asserts `len(prefixes) == N1` and `len(two-cell prefixes) == N2`, literals counted by X-K1 at its skeleton commit and recorded in the test. Deleting a branch of `classify` fails at least one prefix; the five classifier mutants (C2/C3, C3/C5, C5/completed, C6/C2, C2/continued turn) are kept in `tests/mutations/resume.json`, each named to the sweep's two node ids, so every join that touches `resume.py` or `test_resume.py` re-proves that the sweep kills them (R-110; SIM 2 reversed: SIM 1 made the sweep the only proof of six windows, so the sweep needs a standing control). *(Erratum, Coordinator #47 at K1d's join, Ruling 110 condition 2; the sentence it replaces said the five were run once at K4 and not kept.)*

**Refusals** (`tests/test_resume.py`): `test_refused_live_lock` (a child holds the lock; `HB-RUN-005`; message holds the age, not a PID), `test_refused_identity_drift` (`HB-IDN-001`), `test_refused_verify_failure_names_segment` (`HB-RUN-009`, tamper one byte of an engine segment), `test_refused_unrepairable_archive_writes_nothing` (`HB-LED-005` at step 3, DS 6), `test_refusal_order` (a ledger failing identity and verify raises `HB-IDN-001`; a stopped ledger with drifted identity is refused, never finished), `test_refusal_writes_nothing` (no new segment, no `.alarm_check`, no change to any file: hash the run dir before and after, over every refusal above). The `lifecycle.py` replay rule (section 8) is tested by `test_lifecycle.py::test_launch_intent_after_a_stop_row_is_rejected` and `::test_run_resumed_after_a_stop_row_is_accepted` (red fixture: a ledger with `cell.launch_intent` after `run.stopped`).

**(b) Red fixtures.** Each refusal and the sweep has its fixture above, run before the real tree. `test_sweep_pairing_refuses_wrong_lock`: a held lock of another folder passed with `archive/` raises `ValueError` (W0 rev 6.1, RV-SEC decision A); deleting the pairing line turns it red. `test_abandoned_marker_pins_head`: cut a dead engine segment by one row after the resume; `bench verify` must report `HB-LED-002`.

**(c) Real wiring beside the fakes.** `classify` is pure and unit-tested; `test_resume.py::test_cli_run_resumes[T2]` drives the real `cli.py` command twice around a real kill and fails if the `cmd_run` branch or the `resume_run` call is removed. **Both live in X-K1**, so it is green on X-K1's branch. T2 is also W2 and W11.

**(d) Mutants that separate adjacent rules** (`tests/mutations/resume.json`, X-K1):

| mutant | swaps | input on which the pair differs |
| --- | --- | --- |
| M-SKIPARCH | C1 vs C0 | W9, W10: cell skipped without archive |
| M-NODISCARD | C6 | W2: relaunch raises on the existing folder |
| M-NOREDO | C4's snapshot redo | W4b, W4c: the archive lacks the turn-1 tree |
| M-APPENDALL | `append_missing_rows` | W5b, W10b: duplicate key |
| M-WRITEOLD | step 5 | `test_abandoned_marker_pins_head` / the old segment's byte hash changes; a second resume adds a duplicate `segment.abandoned`; killing node since K1d part 2 (`4d859200`): `test_resume.py::test_the_resume_opens_new_segments_and_never_the_dead_one` (the golden fixture ERRORs under this mutant, which `mutate_check` counts as not killed, CR47-14) |
| M-ORDER | refusal order | `test_refusal_order` |
| M-ORDINALCOUNT | the segment ordinal | W13b |
| M-STOPONLYRUNSTOPPED | the stop predicate | `[control_applied]` and `[decision_resolved]` windows launch (they hold no `run.stopped` row) |
| M-LAUNCHSTOPPEDISSTOP | `run.launch_stopped` vs a stop row | W12d: nothing launches |
| M-STOPCRASHREC | the stop input vs C2/C3/C5 | W12: `HB-CELL-118/119` instead of `stopped` |
| M-STOPLAUNCHES | the stop input vs C6 | W12 (the C6 cell): a second `launch_intent` is written |
| M-STOPC7 | the stop input vs C7 | W12 (the C7 cell): its `resume.cell` record's `action` is `launch` instead of `skip` and `resume.done.launched` is not 0 (the stopped engine refuses the launch, so no `launch_intent` appears; erratum, Coordinator #47, CR47-5; TA 1) |
| M-STOPNOGRADE | R-101's tail | W12: the grading pass is skipped (no `grading` object) |
| M-DOUBLECOMPLETED | step 4's no-op | W12e: a second `run.completed` or segment |
| M-NOPENDINGSTOP | `has_work` clause (2) | W12f: a finished stop with a C7 cell writes a segment |
| M-ANYCOMPLETED | D-K5's `completed` | W16: a reader keeping `any(run.completed)` reads "complete" |
| M-PIDREUSE | D-K2's creation-time test | `test_recycled_pid_is_gone` |
| M-PIDKILL | D-K2's "confirm gone" | the check terminates a foreign process |
| M-NOBEAT | the lock heartbeat | `test_resume_heartbeats_the_lock` |

*Errata to this table (Coordinator #47, K1d's join): rows M-WRITEOLD and M-STOPC7 above (CR47-5); Ruling 110 adds the five classifier mutants to `resume.json` beside these nineteen (`:199`). Outside this table, `tests/mutations/engine.json`'s "launch after a stop" (NoLaunchAfterStop) moved its find from the launch loop's `not self.stopped` to `_launch`'s `if self.stopped: return`, before `cell.launch_intent` (CR47-13, X-K1d part 3 `75b1c264`): K6b (section 7) made that guard the one enforcing site, and the loop condition is a pre-filter with no mutant.*

**(e) Sweeps against the tree.** (1) The three FACTS the engine writes are `("events", "turn_usage", "archive_files")` (`engine.py:49`): the test asserts the set of segments abandoned equals `{f for f in engine.FACTS}` intersect the unsealed ones, so a fourth fact added later fails here. (2) Readers of "completed" (`views.load`, `status.build`, `cli._require_running`, `grade/runner.py`): X-K1 runs `rg "run.completed" src` on its base and pins the hit count in `test_completed_has_one_definition`; the test fails if a reader keeps its own `any(... run.completed)`. The count on **main `ef4e86dc` is 17 matching lines** (TA 6, grep -r, Verified by the reviewer; X-K1 re-takes it at its skeleton commit and pins that number). (3) Readers of "work left": `test_alarm.py::test_alarm_has_no_pending_logic_of_its_own` asserts `alarm.check` imports `resume.has_work` (M-ALARMPENDING: a local copy fails).

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
- **Grading after a finish-the-stop (F-1): closed by R-101.** The resumed engine grades, as the model already allows (`GradeStart(p, "engine")` stays enabled on a stopped run), and the code takes the live tail (`engine.py:412-426`). So `ArchivedCellsGetGraded` holds through a crash after `ApplyStop` by a step the code also takes. No model edit and no `StopCrashed` disjunct. `bench grade` remains the re-run path for a grading pass that failed, as for a live run (US-26). One exception stays outside the model: a resume that defers a cell whose pid is still alive (D-K13) grades nothing until a later resume; the model has no pid, so this is code-level and tested in section 4.
- The model lets a cell outlive an engine crash; kill-on-close means the engine's cannot (header of the `.tla`); the safety results therefore carry over. The pid check (D-K2) is code, not model.
- A copy that fails during the redo (C4) is not modelled; the in-run `SnapFail` is its twin.
- Liveness runs without symmetry at one cell, one crash (`liveness.cfg`).

### 5.4 TLC evidence (revision 1.1, after R-100; unchanged in 1.2)

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

**Liveness with a crash after `ApplyStop` reachable (R-100 condition 2).** `liveness.cfg` has `MaxCrashes = 1`, one cell, no symmetry, and checks all five properties (`DecisionEventuallyResolved`, `StopReachesTerminal`, `EndedCellsGetArchived`, `PromptedCellsEnd`, `ArchivedCellsGetGraded`) with **no** `StopCrashed` disjunct: the row above, 170,552 distinct states, exit 0. Reachability of the crash-after-stop state inside that configuration: a scratch copy of the model with one extra operator `NoCrashAfterStopWitness == ~(stopApplied /\ engine = "down" /\ \E c : intent[c] /\ outcome[c] = "none")`, run as the only invariant on the `liveness.cfg` constants (command: `python reach.py` in the session scratchpad, TLC `-workers 4`): **violated** at a 5-state trace `Init, WriteControl, WriteIntent, ApplyStop, Crash` (524 generated, 290 distinct), exit 12. So the liveness run explores the state, and the four promises hold through it because `Resume` and `ReconcileRecord(c)` (now recording `stopped`) are in `Fairness`. One-time evidence; not a continuous ring, and the witness operator is not added to the model (`WITNESSES` is pinned by `tests/test_check_models.py`). **Reproducible from this document (TA 7):** the script below is the `reach.py` that produced it; save it, run `python reach.py <empty scratch dir>` from any directory with the pinned `.tools/tla2tools.jar` and Java on `PATH`, and expect `exit 12` and a violation trace of 5 states. Revision 1.2 changed no `.tla` or `.cfg` file (R-101: no model edit), so the evidence above stands and `check_models.py --quick` is not repeated.

```python
import re, subprocess, sys
from pathlib import Path

root = Path(r"C:\Projects\x-harness-x-model-bench-design-eval-resume")  # the tree root
scratch = Path(sys.argv[1]); scratch.mkdir(exist_ok=True)
tla = (root / "models/run_lifecycle.tla").read_text(encoding="utf-8").rstrip()
extra = '\nNoCrashAfterStopWitness == ~(stopApplied /\\ engine = "down" /\\ \\E c \\in Cells : intent[c] /\\ outcome[c] = "none")\n'
idx = tla.rindex("\n====") + 1
(scratch / "run_lifecycle.tla").write_text(tla[:idx] + extra + "\n" + tla[idx:], encoding="utf-8")
cfg = (root / "models/run_lifecycle.liveness.cfg").read_text(encoding="utf-8")
(scratch / "w.cfg").write_text(cfg.split("INVARIANTS")[0] + "INVARIANTS\n    NoCrashAfterStopWitness\n\nCHECK_DEADLOCK FALSE\n", encoding="utf-8")
r = subprocess.run(["java", "-cp", str(root / ".tools/tla2tools.jar"), "tlc2.TLC", "-workers", "4", "-config", "w.cfg", "run_lifecycle.tla"],
                   cwd=scratch, capture_output=True, text=True)
print("exit", r.returncode)
for line in (r.stdout + r.stderr).splitlines():
    if re.search(r"violated|distinct states|State \d+:|Error", line):
        print(line)
```

**The new variants and the one that lost its lift** (direct TLC through `check_models.tlc`, each against its target alone; `exit 12` is TLC's invariant-violation status):

| variant | target | bounds | trace length (states) | generated / distinct | time |
| --- | --- | --- | --- | --- | --- |
| `stop_recorded_as_crash` (new) | `StopResumeRecordsStopped` | small | 7 | 22,738 / 7,802 | 2 s |
| `stop_resume_launches` (new) | `NoLaunchAfterStop` | small | 5 | 5,558 / 2,246 | 2 s |
| `launch_after_stop` (existing, the invariant R-100 names) | `NoLaunchAfterStop` | small | rejected in the quick run | n/a | n/a |
| `relaunch_stopped` (existing; its `Resume` lift is removed because `Resume` has no guard) | `StoppedNeverRelaunched` | small | 8 | 33,247 / 10,857 | 2 s |
| `resume_after_stop` | retired | | | | |

**MOD-C, both directions (each new or removed guard against every other variant).** Removed: the `Resume` guard and its `relaunch_stopped` lift; `relaunch_stopped` is still rejected (row above), and no variant needed the lift for any other reason. New: the stop branch of `ReconcileRecord` (with its `BetweenSnapped` guard on prompted cells) and the `StartCell` lift for `stop_resume_launches`. The proof that neither starves another variant is the quick run itself: all 34 variants report `rejected by own target`, including the stop-sensitive ones (`launch_after_stop`, `relaunch_stopped`, `stop_ignored`, `no_escalate`, `record_without_kill`, `kill_between_turns`, `between_without_snapshot`). The two new variants are themselves the reverse check on the new branch: each is rejected only because the branch it breaks is reachable.

**US-44 bounds (3 cells, parallelism 2, 1 crash, the non-quick `safety` run): not re-run for revisions 1.1 and 1.2** (SIM 7: the model has not changed since 1.1). The revision 1 result (357,112,128 distinct states, 39 min 34 s, exit 0) was for a model with `Resume` guarded and is **stale** for this one. It is one-time evidence outside every continuous ring; the quick run covers the same invariants at small bounds, and the Leader may order the 40-minute run before the gate merge if the lenses ask.

## 6. Liveness and the alarm

### 6.1 `last_progress_at` (ADR-0021 section 7)

The **maximum `recorded_at`** over the tail row of **each** events segment (engine segments and grading-pass segments, a pass in progress and an abandoned pass included, so a long grading pass counts as progress), **never chosen by file name** (SRE 3: `grade-...` sorts after every `engine-...`, so a name-sorted "newest" reads a stale old pass on a resumed launch-stop run, the D-K5 case). Each tail is read by seeking to the segment end and parsing the last complete line; a torn last line is skipped to the previous one. It is a liveness probe, not an integrity check: it does **not** verify the chain (`bench verify` does). Unreadable: `not recorded`, and the alarm raises (fail closed). Tests: `test_status.py::test_last_progress_ignores_segment_name_order` (a sealed old grading segment and a newer engine segment; M-NAMESORT). `bench status --json` gains `last_progress_at` (string or null) and the schema string becomes `bench-status/2`; `status.parse` accepts `/1` (new keys read as null) and `/2`. `bench-campaign-status/1` is unchanged (W1-C).

### 6.2 The check: `bench status <run_id> --alarm-after <seconds>`

Pure core `alarm.check(run_dir, after_s, now, lock_age) -> AlarmResult | None` in `alarm.py` (grade class, W0 section 9); the CLI renders it. **Work left is `resume.has_work(plan, rows)` (D-K12, R-102), imported, never re-implemented**: `alarm.py` carries no pending logic of its own (`test_alarm_has_no_pending_logic_of_its_own`, M-ALARMPENDING). R-100 condition 6 reads, from R-102: *alarm and status read `resume.has_work`; neither carries a definition of pending of its own. After a finish-the-stop resume `has_work` is false, so the alarm is silent by the record; a crash mid-stop leaves `has_work` true and the alarm fires until someone resumes.* Consequences, all by the record: a crash in the grading pass or before the last `cell.archived` alarms (SRE 1); a launch stop (disk low, no stop row) alarms; a finished stop with a C7 cell is silent (the stop row is inside the definition); a **named, never-started run alarms** (armed deliberately). `bench status` prints "stopped, n cells never launched" from exactly those rows (n derived, never stored). Causes:

| code | when | message names |
| --- | --- | --- |
| `HB-ALM-001` engine not alive | `has_work`, and the lock is **free** (not running), or held with heartbeat age greater than `lock_staleness` (stalled) | `not running` or `stalled`, the age, the last progress time, and `bench run <run_id>` as the action |
| `HB-ALM-002` progress stalled | the lock is held and fresh, `has_work`, and `now - last_progress_at > after_s` | the gap, the threshold, the last row kind |

A free lock with `has_work` fires at once (no threshold wait): this is the common failure (engine crash, reboot), and the ADR text "heartbeat is stale" does not cover a lock that was released by the OS. A run for which `has_work` is false never alarms.

**Deferred to E5 with the drill (SIM 4, 5; PAT 4): `HB-ALM-003`, the `.alarm_check` stamp and `ALARM_INTERVAL_S`, `bench campaign status --alarm-after`, the `report/html.py` resume header and the `bench plan` worst-case lines.** No lens requires them for E3; the goal of E3 (a crashed night is recovered, recorded and alarmed) is met without them. They stay named so the E5 design starts from the text: `HB-ALM-003` is a lint of the watchdog (it prints only when a human runs `bench status`), the stamp is written by the wrapper (`--stamp`) so a manual check cannot mask a dead task, and the interval is read from the runbook value (SRE 7). The campaign alarm checks only attached runs that have started and have work. Kept in E3: `run.resumed`, `segment.abandoned`, `cell.outcome.resume`, `resume.started/classified/done`, and "resumed n times" with each time and segment id in `bench status`. Not deferred, because the alarm needs it: `bench plan` still prints the one `--alarm-after` number (below).

**Exit codes** (`cli.py:45` has 0, 1, 3, 4, 5): add `ALARM = 6`. `--alarm-after` exits 6 when it raises (stderr line `HB-ALM-00x: <cause>`; `--json` adds `alarm: {code, cause, last_progress_at, age_s}`), 0 otherwise. Any other failure of the check (unknown run `1`, unreadable ledger `5`) is also non-zero: **a check that errors never reads as "no alarm"**. **Exit 3 from `bench run` means "stopped" (HB-RUN-008) or "not finished: a cell's process is still alive" (D-K13); the stderr line tells them apart** (SRE 10).

**Choosing `--alarm-after`.** It must exceed the longest honest gap between events. One budget covers every turn (ADR-0015 section 3), so a cell's longest gap is about `budget_seconds` plus archive time, and the grading pass (now inside the alarm's reach, because `has_work` covers it) has a gap of up to the largest `grading_step_timeout`. The runbook sets `--alarm-after = max(budget_seconds, worst-case grading step) + 1800` (SRE 12), and `bench plan` prints that one number (a `cmd_plan` print only, X-K2). A host sleep makes the engine kill cells as `host_suspended`, and ALM-002 can fire on wake before the engine writes its next row: **accepted and documented** in the runbook (one 15-minute interval later the next row has landed). Too small causes false alarms; the worst-case envelope, not the mean, is the basis (ADR section 8).

### 6.3 The channel (ADR-0021 section 7: "chosen at `/design-slice`"; amended by R-102)

**Chosen (R-102, DR-K3): an ntfy phone push is the primary channel and is required for an unattended run; the toast is optional and joins at the E5 drill.** ADR-0021 section 7's "a Windows toast at minimum" reads, by R-102 condition 1, "a push to the operator's phone the operator acknowledges at the drill, at minimum; a desktop toast is an optional local echo". The mechanism: a **Windows Task Scheduler task** every 15 minutes in a nightly repetition window, running `powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/alarm-task.ps1 -RunId <id> -AlarmAfter <s>`. E3's wrapper does three things: run `bench status <id> --alarm-after <s>`; **POST on the edge**; append the delivery log.

| option | verdict |
| --- | --- |
| ntfy phone push (chosen, primary, required unattended) | the away-from-terminal path ADR-0021 asks for, and the only one that reaches an operator who is asleep. One HTTPS POST per alert to `https://ntfy.sh/<topic>` (or a self-hosted base URL from the optional `HB_ALARM_NTFY_URL`) carrying only the run id, the `HB-ALM` code, the cause text and the age. No task content, path, cell id, credential or hostname. **Egress accepted by the Owner for the alarm only; nothing else in the bench may reuse the channel without a ruling.** The topic is a bearer secret: the user environment variable `HB_ALARM_NTFY_TOPIC` only, never in the plan, ledger, repo, logs or output (R6.8b(2)) |
| desktop toast (optional, joins at the E5 drill) | a local echo, not a wake-up: needs a signed-in, awake, un-muted desktop, and spike S-K1 only built the types. Not on E3's path; the WinRT, AUMID and XML code, and the `powershell.exe` 5.1 constraint, are added at the drill if the operator wants it. An attended single-night run may use the toast alone, and the runbook says in those words that **a toast wakes no one** |
| e-mail, Teams or Slack webhook | rejected: needs stored credentials or a webhook secret |
| `msg.exe` | rejected: absent on Home editions; no persistence |
| event log only | rejected: nobody watches it (the ADR's own test: "reaches the operator") |

**Unattended means required.** With `HB_ALARM_NTFY_TOPIC` unset the wrapper exits non-zero with the fixed line `alarm channel not configured: set HB_ALARM_NTFY_TOPIC (runbook)` and writes one event-log line. `bench campaign register` for a multi-night grid refuses until the drill record exists (ADR-0021 section 7; the record kind is E5's, section 12), and the drill cannot pass without the push. The runbook requires a recorded test push before an unattended run starts.

**Edge alerting, not a repeat (SRE 6, PAT 3; the SIM decline is overruled on the SRE lens by R-102).** One state file `runs/<run_id>/.alarm_edge` (JSON `{code, first_sent_at, last_sent_at}`, git-ignored with `runs/`) holds the last alert: send on a **new code**, re-send at most **hourly** while the code persists, send **once on recovery** (exit 0 after a non-zero) and clear it. Twenty pushes a night train the operator to mute the only channel; the cost is a dozen lines of PowerShell. A **delivery log** (`runs/<run_id>/alarm-delivery.log`, one line per wrapper run: time, exit code, `push ok` or `push failed: <exception type>`, no topic, no URI; the runbook names the path) is the wrapper's record and the sink for "how often does the alarm fire" (SRE 11b); `bench status` does not read it.

**The topic is never printed (SRE 5).** The POST is wrapped in `try/catch` that writes the fixed text `push failed: <exception type>` and never `$_`, its message or its `TargetObject` (in `powershell.exe` 5.1 a failed `Invoke-RestMethod` carries the full URI there). TLS 1.2 is set explicitly for 5.1. Test: `test_alarm_task.py::test_push_failure_does_not_print_topic` runs the script with a **stub `Invoke-RestMethod` that throws with the URL in its message** and asserts the topic is absent from stdout, stderr and the delivery log (red fixture: the script without the catch). The dry-run takes the network branch through the stub.

**Task Scheduler flags (SRE 4), in the runbook's `schtasks` line / task XML:** start when available (`StartWhenAvailable`), do not stop on battery and do not require AC (`DisallowStartIfOnBatteries` and `StopIfGoingOnBatteries` off), `WakeToRun` on (the operator decides whether the machine may wake; the runbook states the sleeping-host residual), run only when the user is logged on, `ExecutionTimeLimit` 5 minutes, `MultipleInstances IgnoreNew`.

**Window, not always-on.** The task has a daily trigger at the start of the run window with a repetition interval of 15 minutes for the window's length. This is how a *planned* night boundary does not nag all day: a pause is the engine ending, the alarm window ending, and the operator re-registering or letting the next night's trigger fire. `bench stop` is **not** a pause: the next resume finishes the stop and exits 3, launching nothing new (R-100, R-101).

**Runbook path:** `docs/runbooks/resume-and-alarm.md` (new folder; X-K2 creates it), outline: the `schtasks` command and the flags above; the window; how to choose `--alarm-after`; **ntfy setup** (install the app, choose a random topic name, set the user variable `HB_ALARM_NTFY_TOPIC`, the self-host option `HB_ALARM_NTFY_URL`); the recorded test push before an unattended run; the delivery-log path and the edge file; what each `HB-ALM` code means and the action; exit 3's two meanings; "a toast wakes no one"; the host-sleep note; and the one-line check that the task is enabled (`Get-ScheduledTask`). The wrapper `tools/alarm-task.ps1` and its test are new paths (granted, R6.8b).

**Alarm of the alarm: deferred to E5 (SIM 4).** The ADR accepts the "never looks" residual; the stamp, `HB-ALM-003` and the interval belong with the drill, where a disabled task is actually tested.

**Spike S-K1 (run in this slice).** `powershell.exe` 5.1.26100.9549: the WinRT toast types load and `ToastNotification` / `CreateToastNotifier` objects build with the PowerShell AUMID `{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe`, exit 0 [Observed]. A toast was **not shown** (an interactive session is needed) and `notifier.Setting` printed empty [Observed]. Display, persistence and dismissal are **Inferred** and belong to the drill, which is why the toast left E3's path. `pwsh` 7 does not load these types [Inferred from the WinRT projection].

## 7. Disk and worst case (ADR-0021 section 8)

- `_free_bytes` calls `shutil.disk_usage` with no handler (`engine.py:893-897`). An `OSError` raised in the loop today ends the engine, against the ADR ("if the query itself fails, the measurement is recorded `not recorded` and launching continues"). X-K1 moves the check into `_launch`, before `cell.launch_intent`, **as its own commit (K6b) so it can ship or revert alone** (SIM 6). `free_bytes` is the measured value (int); on a failed query it is written explicitly as `null`, which differs from a row written before the field existed (SRE 9c). The stop reason `disk low` with `HB-RUN-004` is the existing code. **Each path is measured alone** (SRE 9a): a failed path is dropped from the minimum and the floor applies to the paths that answered; both failed: launch, `free_bytes: null`. A failing query emits `disk.query_failed{path_role, errno}` and logs a warning on the third in a row (SRE 9b: a blind guard is visible). Tests: `test_engine.py::test_disk_query_failure_is_not_recorded_and_launching_continues` (monkeypatch `shutil.disk_usage` to raise; red today: the engine raises), `::test_launch_intent_records_free_bytes` (red today: no field), `::test_disk_low_stops_launching_before_the_intent` (red fixture: the stop row precedes the cell's intent), `::test_one_path_failing_still_applies_floor_to_the_other`.
- The `bench plan` worst-case slot occupancy and worst-case grading lines are **deferred to E5** (SIM 5); the one `--alarm-after` number (6.2) is the part E3 needs, and it comes from fields the plan already freezes. `plan.json` does not change.

## 8. Surface list (E7: store, model, service, wire, client, UI, compute reader)

| layer | change | owner · phase |
| --- | --- | --- |
| model | `run_lifecycle.tla` v6, `safety.cfg`, `turns.cfg`, `check_models.py` data rows | W1-K (this slice, done) |
| model docs | `docs/design/run-lifecycle-model.md` mapping rows (`ReconcileRecord` under `stopApplied` to the classifier's stop input; `Resume` unguarded to `resume_run`'s stop branch; `turnNext` to `turn_ended.next`; `NoResumeAfterStop` reads `NoLaunchAfterStop`, R6.8d) and `models/README.md` line | X-K1 (E3 hub row, by seam, section 12) |
| store | `run.resumed`, `segment.abandoned` on engine segments, `cell.outcome.resume`, `cell.launch_intent.free_bytes`, segment id `engine-<unix>-r<NNN>`, `.alarm_check` | X-K1 (rows, segment id, engine); X-K2 (`.alarm_check`) |
| service | `resume.py` (`classify`, `stop_recorded`, `history`, `resume_run`), `archive.recover_archive`, `Engine` accepting a resume plan, pid-gone check | X-K1 |
| test (archive readers) | `tests/test_archive_readers.py` (T-SWEEP-1): `READERS` is nine files with `resume.py` the ninth, a sanctioned archive reader (W1-J section 7 erratum, CR46-0); every commit touching `resume.py`, `engine.py` or `archive.py` runs it | X-K1 (erratum, Coordinator #47 at K1d's join, QUOTE-A) |
| service | `resume.has_work(plan, rows)` (D-K12; the only definition of remaining work), `open_engine_segments`, run-level state rebuild (D-K11), the lock heartbeat during a resume, the creation-time pid check | X-K1 |
| service | `alarm.py` (`check`, importing `resume.has_work`) | X-K2 |
| ledger projection | `views.segment_rows`, `views.load.completed` (D-K5), `views.verify` abandoned-head rule | X-K1 (seam for the `views.py` hunk, section 12) |
| lifecycle mirror | `lifecycle.py`: second `cell.launch_intent` allowed (R2 relaunch); `cell.outcome` with `resume` object; replay rule `NoLaunchAfterStop` (a `cell.launch_intent` after a stop row is rejected; a `run.resumed` after a stop row is **accepted**, R-100) | X-K1 |
| wire | `bench-status/2` (`last_progress_at`, `resumes`), exit code 6, `HB-RUN-008/009`, `HB-CELL-118/119`, `HB-ALM-001..002` (confirmed, section 9; `HB-ALM-003` is E5) | X-K1 (`errors.py`), X-K2 (`status.py`) |
| client type | `status.Status` and `status.parse` (accept `/1` and `/2`) | X-K2 |
| UI (CLI text) | `bench status` and the completion summary: "resumed n times" with each time and segment id; per resume, cells skipped / launched / reconciled, each reconciled cell with its code, rule and phase; "stopped, n cells never launched" | X-K2 |
| UI (report) | the report header lists the resumes | **E5** (SIM 5; the seam R6.8c stays granted) |
| entry | `cli.py` `cmd_run`: the `events`-exists branch calls `resume.resume_run` | **X-K1** (moved from X-K2, TA 3, PAT 1) |
| entry | `cli.py`: `status --alarm-after`, exit 6, `cmd_plan`'s one `--alarm-after` line | X-K2 |
| compute reader | `views.rows` already reads all engine segments; `grade/runner.py` abandons an unfinished pass (no change); `resume.classify` and `resume.has_work` are the only readers of `resume.stop_recorded`; `status` and `alarm` call `has_work` and carry no stop exception of their own | X-K1, X-K2 |
| docs | `docs/runbooks/resume-and-alarm.md` (ntfy setup, task flags, delivery log); `tools/alarm-task.ps1` (push, edge file, delivery log; no toast in E3) | X-K2 |

## 9. HB codes (W0 section 11 confirms or drops)

Confirmed: `HB-CELL-118`, `HB-CELL-119`, `HB-RUN-009`, `HB-ALM-001..002`. `HB-ALM-003` is **deferred to E5** (section 6.2), its W0 row stands. `HB-RUN-008` is **confirmed, re-pointed** (W0 rev 6.8 section 11, R-100 condition 4, R-101 condition 1): the stopped run's **exit-3 reason**, no longer a refusal. Every finish-the-stop resume emits "run is stopped: n cells recorded stopped, m archived, graded, 0 launched", and so does an idempotent re-run with zero actions (the "graded" word is R-101's). The "not finished" exit-3 line (D-K13) carries no code of its own (stderr text); it is not a refusal. Reused unchanged: `HB-RUN-004`, `HB-RUN-005`, `HB-RUN-006`, `HB-RUN-007`, `HB-CELL-117`, `HB-LED-005`, `HB-LED-008`, `HB-IDN-001`, `HB-USR-002`. **None dropped, none added.** `HB-ALM-001` carries "not running" and "stalled" as its cause text (W0 merge preference).

## 10. Failure-mode analysis

| failure | effect | detection | response |
| --- | --- | --- | --- |
| the engine dies during a resume | partial reconcile rows | next resume reads the ledger | W13, W14: same decisions; abandoned rows are not duplicated (a segment already named is skipped) |
| the engine dies mid-stop | cells without outcome; the run holds a stop row (one of the three windows) | `has_work` is true, so the alarm fires (free lock); `bench status` shows them | `bench run <run_id>` finishes the stop: `stopped` outcomes, archive, grade, `run.completed`, exit 3 with HB-RUN-008. No unreachable state (W12) |
| the engine dies in grading or before the last archive | zero pending cells, a free lock | `has_work` clauses (3) and (4): the alarm fires | `bench run <run_id>` resumes (C1 archive, a new grading pass) |
| a pid is reused by another process | the recorded creation time differs from the live process | `OpenProcess` plus `GetProcessTimes` | the cell is **gone** (D-K2); a live process with the same creation time is the cell's own: the check waits `pid_wait_s`, then the cell is **deferred** (D-K13): no grading pass, no `run.completed`, exit 3 "not finished", `resume.cell_deferred`; the alarm fires; run again later (idempotent) |
| a resume's pid wait or archive copies exceed `lock_staleness` | the alarm reads "stalled" | the resume heartbeats the lock (step 2) | none needed; `test_resume_heartbeats_the_lock` |
| an unrepairable archive (rows recorded, folder gone) | every retry would grow the ledger | step 3(c) refuses with `HB-LED-005`, nothing written | the operator repairs the folder or the rows by hand; the run is not wedged by retries |
| `shutil.disk_usage` raises | today the engine dies | section 7 | `free_bytes: null`, launching continues; three failures in a row warn |
| `last_progress_at` unreadable | cannot judge progress | the check | raises (fail closed) |
| the push fails or the topic is unset | no alarm reaches the phone | the delivery log line `push failed: <exception type>`; an unset topic exits non-zero with the fixed line | the operator reads the log; the drill proves the channel; the topic is never printed |
| the alarm task is disabled | no alarm | none in E3 (`HB-ALM-003` is deferred to E5) | accepted residual (ADR-0021 section 7), recorded here |
| time skew between the engine host clock and the check | gap wrong | same host (single machine, ADR scope) | none; a different host is out of scope |

## 11. Telemetry (instrumentation over inference)

Emitted on the normal path, no flag: `resume.started {run_id, segment_id, dead_segments, cells_total, has_work}`, `resume.classified {counts per action C0..C7}`, `resume.cell {cell_id, rule, action, code, phase, turn, duration_ms}`, `resume.cell_deferred {cell_id, pid}`, `resume.done {skipped, launched, reconciled, duration_ms}`, `alarm.check {run_id, outcome: ok|HB-ALM-001|HB-ALM-002|error, age_s, gap_s, duration_ms}`, `launch free_bytes`, `disk.query_failed`. Sinks: `resume.*` go to the existing run log; `alarm.check` is an event of the `bench` process, and the wrapper's delivery log (section 6.3) is the record of how often the alarm fired and whether the push left (SRE 11b). Questions answered: how long does a resume take, how many cells does a night lose to a crash, which window and which rule (`rule` on the `resume` object) killed them, how often does the alarm fire. A refusal's reason lives in its message and exit status only, not in a durable record (SRE 11c; accepted, a refusal writes nothing by design). Every path degrades to "not recorded", never to a plausible zero.

## 12. Seams, decisions, open items

| id | what | to | fallback built meanwhile |
| --- | --- | --- | --- |
| DR `req-01M41V2MC1RTCBB4APR3TSXEYP` | crash during a stop | owner-fable | **closed: R-100 ruled (B)**; (A) refused; applied in rev 1.1 |
| DR-K2 `req-01M42049A4NZ66MG3XNXBX10D6` | F-1, grading after a finish-the-stop | owner-fable | **closed: R-101 ruled (a)**; the resume takes the engine's post-stop tail; no model edit; applied in rev 1.2 (steps 4 and 8, section 5.3, W12) |
| DR-K3 `req-01M420CWKVYADEVB241PYEP6RB` | "pending", and the alarm channel | owner-fable | **closed: R-102 ruled**; one `resume.has_work`, ntfy primary; applied in rev 1.2 (D-K12, sections 3.1 step 4, 6.2, 6.3, 13) |
| seam X-K1 -> X-K2 (brief item 7), **moved to X-K1** | the `cmd_run` resume branch. **X-K1 owns the hunk** (`cli.py:156-158`, the `HB-USR-002 "already started"` lines become a call to `resume.resume_run`), in its first commit beside the skeleton, so every real-CLI kill test (W2, W11, `test_cli_run_resumes`) can go green on X-K1's own branch (TA 3, PAT 1). X-K2 keeps the alarm, `status`, `--alarm-after`, exit 6, `cmd_plan`'s single `--alarm-after` print, the runbook and the wrapper | `req-01M420GY3H75665W0N5T04NHRQ` to `coord-opus-e1e4`, to be recorded in W0 section 13 (`cli.py` E3 row); a Coordinator records it in parallel | the recommended fallback, built to green: X-K1 carries the three-line delegation in its own commit; X-K2's branch rebases on X-K1's join for `cli.py` |
| seam | `views.py` E3 hunks (`segment_rows`, `completed`, verify rule) have no E3 owner in W0 section 13 | `coord-opus-e1e4` | X-K1 edits them in its own commit and names the hunk (granted, R6.8a) |
| seam | `docs/design/run-lifecycle-model.md` and `models/README.md` rows (W0 section 13 hands the model to X-K1 after W1-K) | `coord-opus-e1e4` | listed in section 8; X-K1 appends. The model doc states that `ArchivedCellsGetGraded` after a finish-the-stop holds through the resumed engine's own tail (R-101) |
| seam | new paths `tools/alarm-task.ps1`, `tests/test_alarm_task.py`, `docs/runbooks/resume-and-alarm.md` | `coord-opus-e1e4` | **granted (R6.8b)**; conditions: Windows-only `-DryRun` test, the ntfy topic never printed, `powershell.exe` 5.1, frontmatter on the runbook |
| seam | `report/html.py` resume header lines | X-H2 / X-A3 | **deferred to E5** (SIM 5); CLI text only. R6.8c stays granted for when it is built |
| open (E5, not here) | the drill record that `bench campaign register` checks (ADR section 7) has no record kind in W1-C; the drill is out of scope | X-C / E5 | none; flagged. Operator action before E5 (R-102 condition 4): install the ntfy app, choose a random topic, set `HB_ALARM_NTFY_TOPIC`, run the drill |
| ADR amendment text | D-K1 (PID), D-K2 (named job), D-K4 (three stop rows), D-K5, R-100; R-102 condition 1 adds two lines (section 7 "while `resume.has_work` holds"; "a push the operator acknowledges at the drill, at minimum") | Coordinator | ADR-0021 Amendment 1 on `main` (W0 rev 6.8, R6.8d); the two R-102 lines land with this slice's gate merge. The section 4 row 5 reasoning (job_active_processes) is replaced by D-K2 |
| seams R6.8a-c (W0 rev 6.8) | `views.py` hunks for X-K1 beside X-A3's `CellView.pack` rename, disjoint, after X-J1's join (R6.8a); X-K2's new paths (R6.8b); the `report/html.py` header (R6.8c) | X-K1, X-K2 | **granted** |
| ~~finding F-1~~ | closed by R-101 | | |

Seam request ids, in table order: `views.py` and model docs `req-01M41XGYS25EXAHKPZV5EE1QT2` (R6.8a); X-K2's new paths `req-01M41XGZ3WV678S30APNX8HBMK` (R6.8b); the report header `req-01M41XGZF3ACCY2QB5Y3ATYDQK` (R6.8c); the `cmd_run` move `req-01M420GY3H75665W0N5T04NHRQ`. Decision requests: `req-01M41V2MC1RTCBB4APR3TSXEYP` (R-100), `req-01M42049A4NZ66MG3XNXBX10D6` (R-101), `req-01M420CWKVYADEVB241PYEP6RB` (R-102).

## 13. Commit order

**X-K1 (Codex, E3):** K1 skeleton `resume.resume_run` (today's refusal), **the `cmd_run` delegation hunk**, `has_work` as a skeleton returning today's answer, and `tests/fake_acp_agent.py` hang options if X-J1 did not land them; K2 `tests/test_resume.py` and the golden-ledger helper (single-cell and two-cell), red; K3 `errors.py`, `lifecycle.py`, `views.py` hunks, abandoned-head verify; K4 `classify`, `stop_recorded` and `has_work` (the five classifier mutants run once here); K5 `recover_archive`, sweeps, the refusals including step 3(c); K6 `Engine` resume path, `open_engine_segments`, rebuilt run-level state, the lock heartbeat, the pid check with creation time, the live tail for a stopped run; **K6b** the disk check in `_launch` as its own commit; K7 model-docs rows. X-K1's crash-window tests, the real-CLI ones included, are the gate's entry condition for X-K1 (RV-TA W1-B R2-2).
**X-K2 (Agy, E3):** two dispatches. First: `alarm.py` (imports `resume.has_work`), `status.py` (`last_progress_at` by maximum `recorded_at`, `bench-status/2`, "resumed n times", "stopped, n cells never launched"), `--alarm-after`, exit 6, `tests/test_alarm.py`, `tests/test_status.py`. Second (after X-K1 joins, for `cli.py` rebase only): `cmd_plan`'s single `--alarm-after` line, the runbook and `tools/alarm-task.ps1` (**push only; the toast branch is not an E3 commit**, SIM 3 and R-102). `HB-ALM-003`, the stamp, `campaign status --alarm-after`, the report header and the `bench plan` envelope lines are E5.

**Alarm tests (X-K2), all through the real `cli.main`:** `test_alarm.py::test_stale_progress_exits_6_with_alm_002` (fresh heartbeat, last row 2 h old, `has_work`. Red because `exit == 6` fails: X-K2's first commit adds the flag as a skeleton that returns 0, so the failure is the assertion, not argparse's unknown-argument exit 2); `::test_free_lock_with_work_exits_6_alm_001`; `::test_stalled_heartbeat_exits_6`; `::test_complete_run_exits_0`; **`::test_finished_stop_is_silent` (R-102: its fixture holds a C7 cell, a stop row and `run.completed` after `run.resumed`; red today, PAT 2)**; `::test_mid_stop_crash_alarms` (a stop row in each of the three windows, intent cells without outcome, free lock: exit 6 with `HB-ALM-001`; red fixture for the absence of a stop exception); `::test_crash_in_grading_alarms` (no pending cell, no `run.completed` after the last outcome, free lock: exit 6; red today, SRE 1); `::test_outcome_without_archive_alarms`; `::test_launch_stop_alarms`; `::test_pending_zero_does_not_raise_alm_002` (a long grading pass: fresh heartbeat, old last row, `has_work` true only by clause (4), gap under `after_s`: exit 0); `::test_unreadable_progress_fails_closed`; `::test_alarm_has_no_pending_logic_of_its_own`; `test_status.py::test_last_progress_ignores_segment_name_order`. Wrapper, `test_alarm_task.py` (Windows-only `-DryRun`, a stub `bench` and a stub `Invoke-RestMethod`): `::test_nonzero_exit_produces_payload` (exit 0, 1, 5, 6: a payload for the last three and none for 0), `::test_two_runs_in_a_row_send_once` (the edge file), `::test_recovery_sends_once`, `::test_unset_topic_exits_nonzero_with_fixed_line`, `::test_push_failure_does_not_print_topic` (stub throws with the URL; red fixture: the script without the catch), `::test_delivery_log_has_no_topic`, and **`::test_wrapper_calls_bench_with_the_alarm_argv`**: the wrapper, without `-DryRun`, calls `bench status <id> --alarm-after <s>` against a stub on `PATH` and the test asserts the argv (TA 9). Mutants (`tests/mutations/alarm.json`): M-HEARTBEATONLY (reads the lock mtime as progress: separates ALM-002 from fresh-heartbeat stall), M-GE (`>=` for `>`), M-UNITS (ms for s), M-ZEROISOK (an error returns 0), M-PENDINGONLY (the old no-outcome definition: separates `test_crash_in_grading_alarms`), M-ALARMPENDING (a local copy of the work definition), M-NAMESORT (name-sorted newest segment), M-STOPEXEMPT (a stop row silences the alarm: separates `test_mid_stop_crash_alarms` from `test_finished_stop_is_silent`).

## 14. Stage 4 self-check (`definition-of-done.md`)

- Data model first, grain declared, derived counts not stored: done (section 2).
- Testability floor items 1-5 per named test: done (section 4 columns (a)-(e); alarm tests in section 13 name the red assertion; the alarm sweep (e) is the `has_work` import test; counts for the `rg` sweeps and for N1 and N2 are taken by X-K1 at its skeleton, with the main scan of 17 recorded).
- Model before code, TLC output in the doc, seeded variants rejected, `tests/test_check_models.py` and `check_models.py --quick` green: section 5.4 (no model change in rev 1.2, R-101; the quick run is not repeated).
- Surface list from store to compute reader: section 8.
- Unmet or provisional: spike S-K1 shows API presence only (the toast left E3's path); counts for the `rg` sweeps are taken by the builders on their base; the drill is out of scope; `HB-ALM-003`, the report header, the campaign alarm and the `bench plan` envelope lines are E5; the US-44 non-quick run is stale and one-time (section 5.4).

## Review disposition (rev 1.2)

Every finding of the five reviews has a row. States: **applied** (text or test changed here), **answered** (a ruling covers it), **deferred** (to E5, named), **advice-taken**, **declined** (with the reason).

| id | finding (short) | state | where |
| --- | --- | --- | --- |
| TA 1 | no C7 or C4 stop cells in the stop tests | applied | W12 (C7 cell, C4 variant), W4b, W4c, M-STOPC7, M-NOREDO |
| TA 2 | W12e idempotence vs unsealed new segments | applied (R-101: `run.completed` seals the new segments) | step 4, W12 (`bench verify` exit 0), W12e, W12f |
| TA 3 | X-K1's real-CLI tests need X-K2's `cmd_run` hunk | applied (hunk moved to X-K1) | section 4 intro and (c), section 12, section 13; seam `req-01M420GY3H75665W0N5T04NHRQ` |
| TA 4 | reds for W5, W10, W13, W14 are mutant-shaped | applied | W5, W10, W13, W14 column (a) now exit status and rows |
| TA 5 | sweep lacks a stop axis and a multi-cell ledger | applied | sweep over both `stopped` values, two oracle tables, two-cell ledger, N1 and N2 |
| TA 6 | no mutant for D-K5, D-K2; the `rg` count | applied | M-ANYCOMPLETED, M-PIDKILL, M-PIDREUSE; count 17 on main `ef4e86dc` |
| TA 7 | `reach.py` not committed; US-44 stale | applied / answered | the witness source is in section 5.4; the US-44 run stays stale and one-time (R-101: no model change, so the safety result is not newly invalidated; the Leader may order it) |
| TA 8 | F-1: the model grades, the code would not | applied (R-101 closes it) | section 5.3, step 8, section 12 |
| TA 9 | wrapper test does not assert the real argv | applied | `test_wrapper_calls_bench_with_the_alarm_argv` |
| TA A1 | W12 and M-STOPGRADES encode the superseded rule | applied | W12 (three params assert grading and one `run.completed`), W12e, M-STOPNOGRADE, M-DOUBLECOMPLETED, step 4, D-K5 (the stop row decides exit 3) |
| TA A2 | s5.3, s12, step 8 text still old | applied | rewritten per R-101 item 4 |
| DS 1a | stale against R-101 | applied | steps 4 and 8, W12, W12e, M-STOPNOGRADE, section 5.3, section 9 (HB-RUN-008 gains "graded"), section 12 |
| DS 1b | C7 cells make "no pending" never true | applied | D-K12 `has_work` clause (2); W12f; M-NOPENDINGSTOP |
| DS 2 | decisions, controls and spend cap not rebuilt | applied | D-K11, step 3, tests in section 4 |
| DS 3 | the resume does not heartbeat the lock | applied | step 2, `test_resume_heartbeats_the_lock`, M-NOBEAT |
| DS 4 | pid reuse ignores recorded creation time | applied | D-K2, `test_recycled_pid_is_gone`, M-PIDREUSE |
| DS 5 | segment ordinal and order | applied | D-K7, W13b, W13c, M-ORDINALCOUNT |
| DS 6 | HB-LED-005 wedges on retry | applied | D-K14, step 3(c), `test_refused_unrepairable_archive_writes_nothing` |
| DS 7 | pid-alive exit would write `run.completed` | applied | D-K13, step 8, `test_pid_alive_defers_and_writes_no_completed` |
| DS 8 | controls read after launches | applied (advice taken) | D-K11 (read once before step 7), `test_stop_control_file_honoured_before_relaunch` |
| DS 9 | stop code from `decision.requested.kind` | applied (advice taken) | step 7, `test_stop_code_read_from_decision_kind` |
| DS 10 | discard a no-op when the folder is gone | applied (advice taken) | W2b |
| DS 11 | clean the cell home before archive (cross-lens) | advice-taken; RV-SEC to confirm | step 6 |
| SRE 1 | two definitions of work left | answered (R-102 item 1) | D-K12, section 6.2, `test_crash_in_grading_alarms`, `test_outcome_without_archive_alarms`, M-PENDINGONLY |
| SRE 2 | C7 cells make a finished stop alarm | answered (R-102 item 1: the stop row is inside the definition) | D-K12, `test_finished_stop_is_silent` with a C7 cell; "stopped, n cells never launched" |
| SRE 3 | "newest" segment undefined | applied | section 6.1, M-NAMESORT |
| SRE 4 | toast does not reach a sleeping operator; task flags | answered (R-102 item 2) and applied | section 6.3 (ntfy primary and required, flags, runbook) |
| SRE 5 | the topic printed by a failed POST | answered and applied | section 6.3 try/catch, `test_push_failure_does_not_print_topic` |
| SRE 6 | no dedupe, escalation or delivery record | answered and applied | section 6.3 edge file and delivery log, two tests |
| SRE 7 | alarm of the alarm is weak, a manual check masks it | deferred to E5 (SIM 4), the design notes (b) and (c) | sections 6.2, 6.3 |
| SRE 8 | no lock heartbeat before the loop | applied | step 2, `test_resume_heartbeats_the_lock` (same as DS 3) |
| SRE 9 | disk-check edges | applied (advice taken) | section 7 |
| SRE 10 | exit 3 means stopped and not-finished | applied | D-K13, section 6.2, section 9 |
| SRE 11 | classifier row, sinks, refusal reason | applied (a, b); c accepted | `resume.rule` and `stop_row`, section 11 |
| SRE 12 | `--alarm-after` ignores grading; host sleep | applied | section 6.2 formula `max(...)`, host-sleep note |
| PAT 1 | seam: the `cmd_run` hunk | applied | as TA 3 |
| PAT 2 | a finished stop still alarms (C7) | answered (R-102) | as SRE 2 |
| PAT 3 | no alert edge | answered and applied | as SRE 6 |
| PAT 4 | call `HB-ALM-003` a lint | applied (deferred to E5) | section 6.2 |
| PAT 5 | name the patterns | applied | the Patterns table after section 1 |
| PAT 6 | `classify` takes `stopped` as a parameter | applied | step 7 sentence |
| PAT 7 | one factory for engine segments | applied | D-K7, step 5, K6 |
| SIM 1 | two proofs of one classifier table | applied | W1, W3, W3b, W6, W7, W8 are sweep rows; T2 kept for W2, W11 and the wiring test |
| SIM 2 | five classifier mutants | reversed by R-110 | kept in `resume.json`, sweep-named |
| SIM 3 | two deliveries where one reaches the operator | answered (R-102: ntfy only in E3) | section 6.3, K-order; SIM's decline of the dedupe state is overruled by R-102 (the SRE lens) |
| SIM 4 | `HB-ALM-003` and the stamp | deferred to E5 | sections 6.2, 6.3 |
| SIM 5 | report header, plan lines, campaign alarm, history detail | deferred to E5 (`resume.history` per-resume detail stays: it is the resume record of ADR-0021 section 6) | sections 6.2, 7, 12 |
| SIM 6 | disk query as its own commit | applied | K6b |
| SIM 7 | do not re-run US-44 | applied | section 5.4 unchanged; the quick run is not repeated (no model change) |
| SIM 8 | state the grading path in the model doc | applied (R-101 supersedes: the resumed engine grades) | section 5.3, model-doc row |

## Gate record

| lens | verdict | line |
| --- | --- | --- |
| RV-TA (Test Architect, hard veto) | PASS WITH CONDITIONS | GATE W1-K · Test Architect · PASS WITH CONDITIONS · 9 findings (rv-ta-w1k-e1e4, 2026-10-03) |
| RV-DS (Distributed Systems, hard veto) | PASS WITH CONDITIONS | GATE W1-K · Distributed Systems · PASS WITH CONDITIONS · 11 findings (rv-ds-w1k-e1e4, 2026-10-03) |
| RV-SRE (SRE, hard veto) | PASS WITH CONDITIONS | GATE W1-K · SRE · PASS WITH CONDITIONS · 12 findings (rv-sre-w1k-e1e4, 2026-10-03) |
| RV-PAT (Patterns Expert) | PASS WITH CONDITIONS | GATE W1-K · Patterns Expert · PASS WITH CONDITIONS · 7 findings (rv-patsim-w1k-e1e4, 2026-10-03) |
| RV-SIM (Simplifier, soft veto) | PASS WITH CONDITIONS | GATE W1-K · Simplifier · PASS WITH CONDITIONS · 8 findings (rv-patsim-w1k-e1e4, 2026-10-03) |

Conditions were applied in revision 1.2 (the table above); the model is unchanged, so `check_models.py --quick` is not repeated (R-101).
