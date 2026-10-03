---
id: "adr-0021-plan-level-resume-and-liveness"
title: "ADR-0021: Plan-level resume of a run, with per-turn reconciliation and a progress signal an alarm can watch"
type: adr
status: draft
owner: "@timianmalloo"
phase: "Enterprise evaluation E3 (needed by E5's multi-night grid)"
tags: [benchmark, run-engine, resume, liveness, sre, multi-night]
links:
  - { to: arch-evaluation-campaign, rel: refines }
  - { to: spec-enterprise-evaluation, rel: implements }
  - { to: adr-0007-run-engine, rel: refines }
  - { to: adr-0015-multi-turn-attempt-and-turn-snapshots, rel: depends-on }
  - { to: adr-0017-engine-identity-and-freeze, rel: depends-on }
review-by: "2027-10-03"
summary: >-
  A restarted `bench run` for an existing run id resumes it: it verifies the ledger, proves each cell terminal
  from its recorded outcome event, reconciles every non-terminal cell by ADR-0007's rules extended per turn
  (ADR-0015), relaunches only never-prompted cells in the frozen plan order, and grades once every cell is
  terminal. It refuses a resume after a stop or under a drifted run-side identity. `bench status` exposes
  last_progress_at, and `bench status --alarm-after` gives a scheduled check a non-zero exit when progress
  stalls. A per-launch disk check and a stated worst-case cell and grading time complete the multi-night story.
---

# ADR-0021: Plan-level resume of a run, with per-turn reconciliation and a progress signal

- **Status:** Proposed (added at the architecture council, SRE blocking finding)
- **Date:** 2026-10-03
- **Deciders:** @timianmalloo; authored by Claude Code with the SRE, Distributed Systems and Data & Persistence lenses
- **Context spec/architecture:** `docs/specs/enterprise-evaluation.md` (DR-E5 multi-night grid; US-18 resume); ADR-0007 §1-§2, §5 (heartbeat, resume cases); ADR-0015 §5a-§7.

## Context

DR-E5 makes the comparison grid multi-night (about 2 nights at grid-4's throughput, Inferred). A night boundary, a reboot or an engine crash must not lose a grid. ADR-0007 §2 already defines per-cell resume cases, written for containers, and the architecture of record schedules resume for its phase 5. Today the engine has no resume entry point [Verified: no `resume` in `engine.py` or `cli.py`, 2026-10-03]. Liveness today is the lock file's mtime, touched every loop (ADR-0007 §1), which proves the engine is alive but not that it is progressing, and nothing pushes an alarm.

## Decision

**1. Entry point.** `bench run <run_id>` on a run whose `plan.json` is confirmed and whose `events` exist is a resume. It is idempotent: running it twice makes the same decisions.

**2. Refusals, checked first (under the run lock).**
- The run lock is held by a live engine (heartbeat fresher than the plan's staleness threshold): refused, naming the PID.
- The run has a `run.stopped` or `stop` event: refused (the "no launch after a stop" invariant).
- The run-side engine identity differs from the plan's recorded identity (ADR-0017 §7): refused with the named diff. A resume never continues a run on a different instrument.
- `bench verify` fails on any chain: refused, naming the segment.

**3. How the ledger proves a cell terminal.** A cell is terminal iff its `events` hold its outcome transition (the closed taxonomy of ADR-0007, recorded once by the engine thread). `cell.archived` is a separate, later fact; terminal-but-not-archived is a reconciliation case, not a terminal-and-done one. The dead engine's unsealed segment is recorded `segment.abandoned{segment_id, line_count, head_hash}` by the resuming engine in its own new segment (the ADR-0006 rule already used for grading segments); the resuming engine never writes into the old file.

**4. Per-cell reconciliation** (ADR-0007 §2, with containers read as Job Objects by name, and ADR-0015's per-turn predicate):

| Recorded state | Action |
| --- | --- |
| no `launch_intent` | launch, in the frozen plan order |
| `launch_intent`, no `prompt_sent{1}` | terminate the named job if present, confirm empty, launch once |
| `prompt_sent{k}`, no `turn_ended{k}`, no outcome (turn k crashed) | terminate and confirm, record `failed (coordinator crash)`, archive, never relaunch |
| `turn_ended{1}`, no `prompt_sent{2}`, no outcome (between turns) | the ACP session died with the old engine (kill-on-close): record `failed (coordinator crash between turns)`, turn 2 NOT_RECORDED `turn 2 not reached`, archive with the turn-1 snapshot, never relaunch |
| `turn_ended{1}`, no `cell.turn_snapshot_archived{1}` (the turn-1 snapshot copy crashed mid-write; a `*.tmp-*` sibling may exist) | delete the temporary sibling and redo the snapshot from the working copy through ADR-0015 §5a; turn 2 was never sent, so the tree is turn 1's (any write by a lingering process is visible in `job_active_processes`, which reads 0 after the restart); record the snapshot event, then proceed as the between-turns row below |
| outcome, no `cell.archived` | archive through the crash-atomic write (ADR-0015 §5a): a `*.tmp-*` folder is redone; a complete final folder is re-verified and its event recorded |
| outcome and `cell.archived` | skip |

**5. Grading resumes after the cells.** Grading starts once every cell is terminal and archived, as today. A grading pass interrupted by the crash is abandoned by the ADR-0006 rule and a new pass runs from the start; extractions already written are reused (write-once extractions).

**6. What the operator sees.** `bench status` and the completion summary show: resumed n times, with each resume's time and segment id; per resume, cells skipped / launched / reconciled, and each reconciled cell with its recorded cause. The report header lists the resumes. A multi-night grid is the same run resumed each night.

**7. Progress signal (council R1).** `bench status --json` gains `last_progress_at`: the timestamp of the last lifecycle event appended to the run's `events` (derived from the ledger tail, no new rows). `bench status <run_id> --alarm-after <seconds>` exits non-zero, naming the cause, when the heartbeat is stale **or** `now − last_progress_at` exceeds the threshold while cells are pending. A scheduled task (Windows Task Scheduler, every 15 minutes, documented in the runbook) runs it during a campaign run. `bench campaign status --alarm-after` does the same over the campaign's active run.
- **Delivery channel — a hard precondition of E5 (SRE condition).** A non-zero exit is useless unless it reaches the operator. Before E5's comparison grid starts, the scheduled task must turn a non-zero exit into a notification the operator sees away from the terminal: a Windows toast at minimum, and a push to the operator's phone if one is configured. The channel is chosen at `/design-slice` and proven by a drill: a seeded stale run must produce a notification the operator acknowledges. `bench campaign register` refuses for a multi-night grid until that drill is recorded.
- **Residual: no alarm for the alarm.** If the scheduled task is disabled, deleted or failing, nothing fires. Cheapest mitigation: each alarm check stamps `last_alarm_check_at` (a file beside the run lock, not a ledger row); `bench status` and `bench campaign status` print a warning when no alarm check ran in the last 2 × the task interval during an active run. A human who looks sees it; a human who never looks is the accepted residual.

**8. Disk and worst-case time (council SRE minors).**
- Before each `cell.launch_intent` the engine reads free space under the cells root (`shutil.disk_usage`, as preflight `HB-PRE-003` does at start). Below the plan's threshold it stops launching with the stop reason `disk low` and the measured value; if the query itself fails, the measurement is recorded `not recorded` and launching continues (preflight already passed).
- **Worst-case slot occupancy per cell** = `budget_seconds` (one budget covers every turn, ADR-0015 §3) + archive and snapshot copy time (measured, recorded on the spans). **Worst-case grading per cell** = Σ over the task's graders of `grading_step_timeout` (the hidden check's outer bound is one of them, ADR-0018 §5). `bench plan` shows both envelopes beside the measured means from the named source runs, so a night is planned against the worst case and judged against the mean.

**9. Lifecycle model.** The TLA+ model already checks crash and resume (US-44); it gains the per-turn cases of §4 through ADR-0015 §7 (`CrashedTurnPredicate`), and the "no resume after a stop" refusal as an invariant.

## Alternatives considered

- **Re-plan the remaining cells as a new run:** rejected; it splits one grid into runs, which DR-E1 forbids (drift between runs) and which breaks the launch seed.
- **Relaunch a cell whose turn 2 was never sent, in a new session:** rejected; a second session breaks "one attempt per cell" and DR-E4's same-session rule.
- **Heartbeat rows in the ledger:** rejected at the phase-1 gate (ADR-0007 §1); the ledger tail already carries progress.
- **Resume under a drifted identity and let eligibility sort it out:** rejected; the run would spend a night on ineligible cells (ADR-0017 §7).

## Consequences

- **Positive:** a multi-night grid survives reboots and crashes with every cell accounted for; a stalled run is noticed within one alarm interval; the worst case is visible before the operator commits a night.
- **Negative / accepted trade-offs:** a cell caught between turns by a crash is lost (recorded, infrastructure-attributed, excluded from verdicts with its id); the alarm depends on an operator-installed scheduled task.
- **Backlog (SRE condition, CAUSE-A):** on the non-campaign board, auth expiry (`blocked (auth)`, `HB-CELL-202`) is still attributed to the harness (`errors.py:20`). Campaign views exclude it as infrastructure, but harness-bench reports do not. Recorded as a backlog item against defect class CAUSE-A; the Leader files the defect-class entry, and changing the attribution is a separate, report-moving decision.
- **Follow-ups / new risks:** kill-in-each-state-then-resume tests for every row of §4, including the snapshot-crashed row (red first); the runbook entry for the scheduled task; a fixture that seeds a stale `last_progress_at` and asserts the non-zero exit.

## Evidence

- ADR-0007 §1, §2, §5 [Verified, read 2026-10-03]; `engine.py:379-416` (sleep detector, heartbeat) and `preflight.py:4, 47` (disk check) [Verified]; no resume entry point in `engine.py`/`cli.py` [Verified by search].
