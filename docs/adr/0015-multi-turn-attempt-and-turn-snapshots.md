---
id: "adr-0015-multi-turn-attempt-and-turn-snapshots"
title: "ADR-0015: A cell attempt may hold a second user turn; each non-final turn leaves an append-only snapshot"
type: adr
status: draft
owner: "@timianmalloo"
phase: "Enterprise evaluation E2 (spike E4 passed on Windows)"
tags: [benchmark, run-engine, archive, grain, multi-turn, lifecycle]
links:
  - { to: arch-evaluation-campaign, rel: refines }
  - { to: spec-enterprise-evaluation, rel: implements }
  - { to: adr-0006-results-data-model, rel: refines }
  - { to: adr-0007-run-engine, rel: refines }
  - { to: adr-0013-native-cells, rel: refines }
review-by: "2027-10-03"
summary: >-
  A multi-turn task's cell sends turn 2 as a second session/prompt on the same ACP session and the same stdin
  channel, after turn 1 returns end_turn and after the working copy is archived as a turn snapshot. Spike E4
  verified this on all three harnesses on Windows (macOS unverified). The Cell keeps one prompted attempt;
  prompt_sent and the snapshot carry a turn index; prompt-once becomes once per (cell, turn); archive_files gains
  a snapshot key part whose absence reads 'final'. The driver, engine and archiver need named changes.
---

# ADR-0015: A cell attempt may hold a second user turn; each non-final turn leaves an append-only snapshot

- **Status:** Proposed. Spike E4 passed on Windows (`docs/notes/spike-e4-post-turn-prompt.md`, id `note-20261003-spike-e4-post-turn-prompt`, commit `ebf21cee`, merging to main after this draft); macOS unverified.
- **Date:** 2026-10-03
- **Deciders:** @timianmalloo (DR-E4, 2026-10-03); authored by Claude Code with the Distributed Systems and Data & Persistence lenses
- **Context spec/architecture:** `docs/specs/enterprise-evaluation.md` (EV-4, C-E3, C-E12, R-E6); amends ADR-0006 (`archive_files` grain), ADR-0007 (prompt-once), ADR-0013 §2 (job termination per turn).

## Context

DR-E4 decided that a rework task's turn-2 requirement arrives as a second user message in the same attempt, once turn 1 ends, and that the turn-1 tree is archived first (C-E12). Today [Verified]:
- the driver sends one `session/prompt` and waits for its result with `stopReason` (`driver.py:249-313`);
- ADR-0007 writes `cell.prompt_sent` before the first `session/prompt`, with an ack barrier, and the TLA+ model's invariant is "at most one prompt per cell" (`models/run_lifecycle.tla:53-54, 169-184`);
- ADR-0013 §2: "At the end of every turn the engine terminates the job";
- the archiver copies the whole cell folder after the job is empty, into rows keyed `(run_id, cell_id, archive_attempt, path)` (`archive.py`; ADR-0006).

Forces: P8 (idempotency at the prompt boundary), US-9 (verbatim prompts), US-19 (archive verification), snapshot consistency (the tree must not change while it is copied).

## Decision

**1. Turns.** A task may declare `turns: [<path to turn 2 prompt>, …]` (prompt files outside `workspace/`, inside the task version hash). Turn 1 is `prompt.md` as today. The plan records each turn prompt's sha256 (US-9 per turn).

**2. Delivery.** After turn n's `session/prompt` returns `stopReason: end_turn`, the engine (a) records `cell.turn_ended{turn, stop_reason, turn_seconds}`; (b) archives the working copy `ws` (not the home) as snapshot `turn-<n>`; (c) records `cell.turn_snapshot_archived{turn, snapshot_hash, files, bytes, duration_ms, job_active_processes}`; (d) queues and persists `cell.prompt_sent{turn: n+1}` through the existing ack barrier; (e) sends the next `session/prompt` on the **same** session id over the **same** stdin channel — no second `session/new`, stdin never closed between turns. Any other stop reason, a timeout, a stop or a failure ends the attempt: later turns are not sent, and their metrics are NOT_RECORDED `turn <k> not reached` (EV-4).
- **[Verified, Windows, spike E4]:** on claude-code (claude-opus-5-5), codex (gpt-6-sol) and copilot (gpt-6-sol), the sequence `initialize → session/new → (session/set_model, Copilot only) → session/prompt #1 → end_turn → tree snapshot → session/prompt #2` on the same channel completed `end_turn`, kept the session id, raised no permission request and no error, and returned per-turn usage in each `session/prompt` response on all three. Context carry is strongly indicated (turn 2's `cachedReadTokens` exceed turn 1's total input) but not isolated (prompt 2 named the file).
- **[Flagged]:** macOS (not run); a third prompt (not run; this ADR bounds turns to 2 until checked); a turn 2 after a failed or cancelled turn 1 (not run, and not needed: rule (2) never sends one).
- The restart-plus-`session/load` fallback considered while the spike was open is **not** adopted; it stays unspiked.

**2a. Required code changes** (read from source in spike E4; the slice owns them):
- `driver.run_turn` (`driver.py:249-313`) sends exactly one `session/prompt` (`:300`) and `TurnResult` (`:90-111`) models one turn → split into *open* (handshake), *send turn* (one prompt, one per-turn result) and *close*.
- `engine._attempt` (`engine.py:684-747`): the `finally` at `:728` always runs `_end_process` (`:732`), which closes stdin (`:752`) after the single turn → close only after the last turn.
- The archiver has no snapshot primitive: `archive.archive_cell` (`archive.py:55-58`) writes `attempt-{n}` once and refuses a second write → a separate create-once snapshot write into a sibling folder of the final archive, with the same refuse-if-exists rule.
- The attempt number is hard-coded to 1 (`engine.py:665, 719, 810`) and the record model has no turn index → `turn` on `cell.prompt_sent`, `cell.turn_ended` and the snapshot event and rows (absent reads 1 / `final`).
- The ack barrier (`driver.py:294`; `engine.py:710-714`) records session-opened and prompt-sent once → each turn gets its own `prompt_sent` record through the same barrier; `session_opened` stays once.

**3. The cell budget covers every turn.** One attempt, one budget, one execution outcome. The job is terminated at the end of the attempt's **last** turn (amends ADR-0013 §2 "every turn"). Between turns the adapter stays alive, so the job is not terminated.

**4. Snapshot consistency.** The snapshot is taken while the adapter is idle between turns. A process the agent started and left running may still write to the tree; it is not killed (killing it would change the agent's environment for turn 2). The `job_active_processes` count at snapshot time makes this visible; a non-quiescent snapshot is graded as recorded, and the report can filter on it. This is accepted rather than prevented.

**5. Grain change (ADR-0006 `archive_files`).** One row is exactly one file or link in one **snapshot** of one archive attempt of one cell. Key: `(run_id, cell_id, archive_attempt, snapshot, path)`, with `snapshot` ∈ {`turn-1`, `turn-2`, …, `final`}. A row with no `snapshot` field (every row before this ADR) reads `final`. `cell.archived.archive_hash` keeps covering the `final` rows only, so every existing `verify` result is unchanged; each `turn-<n>` snapshot has its own `snapshot_hash` on its event, recomputed by `bench verify` (a new HB-LED code). A snapshot is an append-only archive entry in a sibling folder of the final archive (the slice names the path), written once through the crash-atomic write of §5a, before the next turn, and never rewritten (C-E12).

**Record model, summarised:** `cell.prompt_sent{turn}` (one per turn, through the ack barrier); `cell.turn_ended{turn, stop_reason, turn_seconds, usage}` (the per-turn usage the `session/prompt` response returns, kept as evidence; the token totals stay ADR-0008's native-record extraction); `cell.turn_snapshot_archived{turn, snapshot_hash, files, bytes, duration_ms, job_active_processes}`; `archive_files` rows with `snapshot: turn-<n>`. Absent `turn` reads 1; absent `snapshot` reads `final`.

**5a. Crash-atomic archive writes (council D1; applies to the existing end-of-attempt archive too).** Today `archive.archive_cell` checks `folder.exists()` once (`archive.py:56-58`) and then copies file by file (`:61-77`) with no temporary folder. A crash mid-copy leaves a partial `attempt-<n>` folder with no `cell.archived` event, and a resume then fails `HB-USR-002 already exists`: the cell deadlocks. This is a **pre-existing defect** of the final archive, not only of snapshots; its class is recorded in `docs/lessons/defect-classes.md` at implementation (class → sweep every "exists means complete" check → control). The fix, for every archive and snapshot write: copy into a temporary sibling folder (`<name>.tmp-<pid>`), fsync the files and the folder, verify the rows against the copy, then `os.rename` it to the final name. "The final folder exists" then means "the copy is complete". On resume (ADR-0021): a `*.tmp-*` sibling is deleted and the copy redone; a final folder with no archived event is re-verified against the still-present workspace (it is deleted only after the event, US-19) and the event is then recorded. A directory rename on the same NTFS volume is a single metadata operation [Inferred]; the kill-during-copy test (below) is the evidence.

**6. Prompt-once becomes once per (cell, turn); the resume predicate is per turn (council D2).** For each turn k: *turn k crashed* ⇔ `cell.prompt_sent{k}` is recorded **and** neither `cell.turn_ended{k}` nor the cell's terminal outcome is recorded. A crashed turn is a coordinator crash — kill by job name, confirm, record `failed (coordinator crash)`, archive, never relaunch. A turn-2 intent is never written before the turn-1 snapshot event. **Between turns** (`turn_ended{1}` recorded, no `prompt_sent{2}`) the cell is *not* in a crashed turn, and a live engine never kills it. After an **engine** restart the case differs: the adapter died with the engine (kill-on-close, ADR-0013), so the ACP session no longer exists and turn 2 cannot be sent in the same session. Resume records `failed (coordinator crash between turns)`, infrastructure-attributed, with turn-2 metrics NOT_RECORDED `turn 2 not reached`, archives the cell with its turn-1 snapshot, and never relaunches it (one attempt per cell). This is stated plainly for the D2 re-check: under kill-on-close, a cell between turns cannot survive an engine restart.

**7. Lifecycle model.** `run_lifecycle.tla` gains a turn index per cell (bound 2), `turnEnded[c][k]` and `snapshot[c][k]`, and these named invariants, each with a seeded-bug variant TLC must reject **before the build starts**: `PromptOncePerTurn` (at most one prompt per (cell, turn) across any number of crashes); `SnapshotBeforeNextTurn` (no turn k+1 prompt before turn k's snapshot); `NoSnapshotInFlight` (no snapshot while a turn is in flight); `CrashedTurnPredicate` (resume classifies a turn as crashed iff `promptSent[c][k] /\ ~turnEnded[c][k] /\ ~terminal[c]`; its seeded variant kills a cell whose turn 1 ended); `ArchiveExistsMeansComplete` (a final archive or snapshot name exists only after its copy verified; the seeded variant writes in place).

**7a. Host sleep (council R3).** The engine loop's `SleepDetector` (`engine.py:379, 396`) already covers the whole attempt, so turn 2 is covered; a test seeds a suspend gap during turn 2 and asserts `host_suspended`. Per-turn auth failure maps to `blocked_auth` (`errors.py:20`, `driver._prompt_error_cause`), never to NOT_RECORDED (council R4).

**8. Grading.** The final tree stays the graded deliverable. A task names a snapshot as an extra graded input (`graded_snapshots: [turn-1]`); the grader builds that grading copy from the snapshot. Telemetry stays one extraction over the whole native session; a per-turn token split is a design-slice question (the per-turn usage in each `session/prompt` response is available on all three harnesses; production profiles read the native record for Codex and Copilot, ADR-0008).

## Alternatives considered

- **A fresh session for turn 2 (the portfolio sketch):** rejected by DR-E4; it loses the turn-1 conversation, which is what rework measures.
- **Two cells per rework trial (turn-1 cell, turn-2 cell):** rejected; it breaks "one attempt, one outcome" and needs a cross-cell dependency in the scheduler.
- **Terminate the job between turns and resume the session with `session/load`:** rejected; spike E4 shows the same channel works, and this path adds a process restart and an unspiked contract.
- **Snapshot the whole cell folder (ws + home):** rejected; the home's native record keeps growing across turns, and only the tree is graded.
- **A separate `turn_snapshots` fact:** rejected; it duplicates `archive_files`' shape and its verify path (DM7). A key part is the smaller change.

## Consequences

- **Positive:** the Cell aggregate's invariant survives (one attempt, one outcome); history is append-only; legacy archives verify unchanged.
- **Negative / accepted trade-offs:** a snapshot may be non-quiescent (measured, not prevented); the lifecycle model grows a dimension (TLC time to be measured); archive size grows by one tree per extra turn; the driver and `_attempt` change shape (open / send turn / close), which touches the most-tested path in the engine.
- **Tests named by the council:** kill the engine during an archive copy and during a snapshot copy, then resume: the cell completes its archive and never reports `HB-USR-002` (D1, red first against today's `archive_cell`); TLC rejects each seeded variant of §7 (D2); a seeded suspend during turn 2 yields `host_suspended` (R3).
- **Follow-ups / new risks:** macOS re-run of spike E4 after the port; a third-prompt check before any task declares three turns; context carry shown by a prompt that does not restate turn-1 facts (the spike's prompt 2 named the file); the per-turn telemetry split; a `synthetic` profile (ADR-0016) must apply per-turn solution trees so the rework discrimination record exercises the same path.

## Evidence

- `driver.py:249-313`, `archive.py:1-12, 55-112`, `run_lifecycle.tla:53-54, 169-184`, ADR-0007 §2, ADR-0013 §2 [Verified, read 2026-10-03].
- Spike E4, `docs/notes/spike-e4-post-turn-prompt.md` (commit `ebf21cee`) [Verified on Windows for all three harnesses; macOS not run]. The frontmatter `depends-on` link to `note-20261003-spike-e4-post-turn-prompt` is added when the note merges to main (it is not on main at this draft, and a link to a missing id fails `docs-graph validate`).
