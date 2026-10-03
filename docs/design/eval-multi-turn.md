---
id: design-eval-multi-turn
title: "Design: multi-turn attempt, turn snapshots and the TLA+ model (W1-J, ADR-0015)"
type: design
status: proposed
owner: "@timianmalloo"
phase: "Enterprise evaluation: Wave 1 (E2 build track X-J1)"
tags: [evaluation-campaign, multi-turn, snapshot, run-engine, archive, lifecycle, tla, wave-1]
links:
  - { to: spec-enterprise-evaluation, rel: implements }
  - { to: arch-evaluation-campaign, rel: implements }
  - { to: adr-0015-multi-turn-attempt-and-turn-snapshots, rel: depends-on }
  - { to: adr-0007-run-engine, rel: depends-on }
  - { to: adr-0013-native-cells, rel: depends-on }
  - { to: design-eval-seam-contracts, rel: depends-on }
  - { to: design-run-lifecycle-model, rel: refines }
  - { to: note-20261003-spike-e4-post-turn-prompt, rel: depends-on }
review-by: "2026-10-17"
summary: >-
  How a cell holds a second user turn on one ACP session: the driver splits into open, send-turn and close; the
  engine snapshots the working copy between turns into archive/<cell>/turn-<n>/ through the crash-atomic publish
  of W0 section 4 before turn n+1's prompt_sent is durable; archive_files gains a snapshot key part that old rows
  read as final, so every existing verify result is unchanged; the budget clock starts once, at turn 1. The
  lifecycle model gains a turn index, a snapshot protocol and phased archive writes. TLC passes it and rejects
  every seeded variant of the five ADR-0015 section 7 invariants.
---

# Design: multi-turn attempt, turn snapshots and the TLA+ model (W1-J)

**Track:** W1-J, session `w1j-multiturn-e1e4` (first pass) and `w1j-multiturn-r2-e1e4` (**revision 2, the author's gate revision**), model `claude-sonnet-5-5`, tier T2. **Implemented by:** X-J1 (E2), after this model passes TLC (plan serial-spine item 4). **Grounded at:** first pass on W0 revision 2 (`124395fb`); revision 2 on main merged in at `cb82cee9` (W0 rev 6.3).
**Rulings and seams carried:** DR-E4 (second turn in the same attempt); W0 section 4 (`publish_dir`, folder-form `sweep_temps(folder, lock)`, rev 6), section 5 (`tasks.<id>.turns`, rev 6.2: `{n, prompt, sha256}`), section 11 (HB-LED-008, HB-CELL-117), section 12 (ledger rows; rev 6.2 `job_active_baseline`), section 13 (hub owners; rev 6.3 SR-J2), section 14 (this doc names the snapshot folder). **Rev 6.2/6.3 rulings that bind this revision:** one `archive.append_missing_rows(folder, rows, present, code)` owned by X-J1; X-J1 owns E2 snapshot recovery and the code follows the folder kind (final HB-LED-005, snapshot HB-LED-008); `turns` entries `{n, prompt, sha256}`; `job_active_baseline` read after the lazy helper spawns; the per-cell archive sweep; closed `NA_REASONS`; SR-J2: `WIDER` data first, logic lines listed, one commit.

## Revision 2: what changed and why

The five gate lenses all returned PASS WITH CONDITIONS (Gate record). Every finding has a row in the *Review disposition* table at the end; the changes that move the design are:

| area | change | from |
| --- | --- | --- |
| Model | `CrashedTurnPredicate` is stated from the ledger facts (`CrashedLit`, `WaitingLit`), independent of `ClassOf`, in three implications; a reverse variant `crashed_turn_as_between` joins `kill_between_turns`; `TurnEnd` no longer requires `~killRequested`; the two resume-owned branches are marked provisional for W1-K | RV-TA 2, RV-SRE 1, RV-DS 4, RV-SIM 6 |
| `check_models.py` | the turn variants and witnesses are `WIDER` data rows; **two logic lines** remain (section 6, *The grant*); the `.tla`, the turns `.cfg`, the script and its test land in one commit | SR-J2 ruling, RV-TA 1, RV-SIM 1 |
| Engine loop | `turn_ended` is written for every turn that returned, before the continue decision, with a `next` field; `Session.close()`; `record_session_opened` split from `barrier_for` | RV-PAT F1, F2, F8; RV-SRE 1; RV-DS 4 |
| Snapshot step | fresh publish or verify-and-complete (`append_missing_rows`, owned by X-J1); retry temps are swept; the retry honours `a.cancel`; folder-form sweep | W0 rev 6.2/6.3; RV-DS 1, 2, 6; RV-SRE 5 |
| Readers | `status.py` joins the surface list (first `prompt_sent` is the clock); `archive.snapshot_of(row)` is the one final-row predicate | RV-SRE 2; RV-PAT F5 |
| Tests | a skeleton-commit order so each engine test is red by assertion; fake-agent options named; writer-side final-row pin; `views` cross-check assertion; code mirrors of the five invariants | RV-TA 4-8; RV-DS 3 |
| Evidence | TLC re-run on the revised model (section 6.1); a second-crash run; the US-44 row is one-time evidence | RV-TA 3, RV-SIM 3, RV-DS 9 |

## Status table

| item | status |
| --- | --- |
| Data model, snapshot path, record contracts | done (sections 2, 3) |
| Driver and engine design | done (section 4) |
| TLA+ model, TLC run, seeded variants | done; output in section 6 |
| Surface list, failure modes, STRIDE-lite, telemetry | done (sections 7 to 10) |
| Test plan by node id, with the four testability checks | done (section 11) |
| Spikes | S-J1 (TLC feasibility), S-J2 (copy cost), S-J3 (lingering writer) run (section 12) |
| Gate record | all five lenses PASS WITH CONDITIONS; this revision applies them (Review disposition); the lenses re-confirm |
| Revision 2 | done: model, check_models, doc; TLC output in section 6.1 |
| Seam requests and open decisions | section 13; provisional seams marked there |

## 1. Responsibility

One responsibility: **let one prompted attempt of a cell hold a second user turn on the same ACP session, and leave an append-only, verifiable snapshot of the working copy at the end of every non-final turn.** It does not grade the snapshot (X-J2), resume a run (X-K1), or define the rework task (W1-L).

Constraints (all quoted from ADR-0015 and checked against the code in section 4):
- "The Cell keeps one prompted attempt; prompt_sent and the snapshot carry a turn index; prompt-once becomes once per (cell, turn)."
- Turn n+1's prompt is sent only "after the working copy is archived as a turn snapshot" (ADR-0015 section 2 (b)-(e)); "A turn-2 intent is never written before the turn-1 snapshot event" (section 6).
- "One attempt, one budget, one execution outcome" (section 3). At most two turns (section 2; W0 section 2, "at most 2 turns").

## 2. Data model (settled first)

**Domain terms.** *Turn*: one user prompt and the agent's response to it, inside one attempt. *Snapshot*: the verified copy of the working copy `ws/` taken between turn n and turn n+1.

**Aggregate.** The **Cell** stays the aggregate (root `cell_id`). Its one invariant is unchanged: one prompted attempt, one budget, one execution outcome. A *turn* is not an entity of its own: it is a position `(cell_id, turn)` in the attempt's event sequence, referenced by identity. A *snapshot* is an append-only fact about that position, never an aggregate (it has no invariant of its own beyond "written once, verified").

**Durable representation (already decided; recorded here, not re-opened).** ADR-0015 section 5: new events and a key part on an existing fact. Nothing is a new table or file format. This design adds no ADR; the amendments it proposes to ADR-0015 are listed in section 13.

| fact | grain: one row is exactly one ... | key | new in this design |
| --- | --- | --- | --- |
| `events` `cell.prompt_sent` | prompt delivered to the adapter for one turn of one cell | (cell_id, turn) | `turn` (absent reads 1) |
| `events` `cell.turn_ended` | end of one turn of one cell (a stop reason came back) | (cell_id, turn) | new kind |
| `events` `cell.turn_snapshot_archived` | one published, verified turn snapshot of one cell | (cell_id, turn) | new kind |
| `archive_files` | one file or link in one snapshot (or the final tree) of one archive attempt of one cell | (run_id, cell_id, archive_attempt, **snapshot**, path) | `snapshot` key part |
| `turn_usage` | one model's token buckets summed over all turns of one attempt of one cell | (run_id, cell_id, attempt, model) | none (sum rule, section 4.5) |

**Additivity.**

| measure | class | rule |
| --- | --- | --- |
| `files`, `bytes` (snapshot event) | additive over snapshots | equal to the count and size sum of that snapshot's rows (equality test, below) |
| `duration_ms`, `turn_seconds` | additive over turns | summed by readers; never stored as a total |
| token buckets (`turn_usage`) | additive over turns | the engine sums the turns' entries before the one row per model (section 4.5) |
| `job_active_processes` | non-additive (a gauge at one instant) | never summed; read with its baseline (section 4.4) |
| `snapshot_hash`, `archive_hash` | non-additive (identifiers) | recomputed by `bench verify` |

**History rule per attribute.** Every new fact is append-only and never rewritten, so each attribute is Type-2 by construction. "Absent reads the default" is the whole migration: an old `cell.prompt_sent` has no `turn` and reads 1; an old `archive_files` row has no `snapshot` and reads `final`. This is expand-only. **No backfill exists**, so nothing can guess (DM16). **Final rows never carry the `snapshot` field** (decision D-J2): the writer omits it, only snapshot rows write `"snapshot": "turn-<n>"`. The bytes of every existing final row, and therefore every `archive_hash`, are unchanged. W0 section 12 allows both spellings; omitting is the choice that keeps legacy and new final rows identical. **One reader predicate (RV-PAT F5):** `archive.snapshot_of(row) -> str` returns `"final"` for an absent field or `"final"`, else the stored `turn-<n>`. `views.verify`'s final-rows filter, the `archive_files` key (so a W0-legal `"snapshot": "final"` row collides with a bare final row, not slips past `_refuse_duplicates`) and any later reader (X-J2, the report) call it; none re-spells `r.get("snapshot") is None`. The writer pin is T-VER-5, the reader pin T-VER-7.

**Derive, don't store.** `snapshot_hash` is `archive.archive_hash(rows)` over the snapshot's own rows (decision D-J3): the same function and the same `ROW_FIELDS` as the final archive, so there is one hash definition (DM7). The event's `files` and `bytes` are a rebuildable cache of the rows; `bench verify` checks the equality (HB-LED-008). `views.verify` recomputes everything; nothing trusts the event alone.

**Writers and readers of every persisted field.**

| field | writer | compute reader |
| --- | --- | --- |
| `cell.prompt_sent.turn` | `engine._attempt` barrier (worker thread, through the ack barrier) | `lifecycle.replay`; `engine._after_append` (budget clock); X-K1 resume predicate |
| `cell.turn_ended.{turn, stop_reason, turn_seconds, usage, next}` (`job_active_baseline` on turn 1 only, section 4.4) | `engine._attempt` (every turn that returned, before the continue decision, section 4.2) | `lifecycle.replay`; X-J2 (turn-2 NOT_RECORDED reason, counts events against the plan's turns); `views` (usage); the report (why turn 2 was not sent: `next`) |
| `cell.turn_snapshot_archived.{turn, snapshot_hash, files, bytes, duration_ms, job_active_processes}` | `engine._snapshot_turn` | `views.verify` (HB-LED-008); X-J2 (`graded_snapshots`); report (filter on quiescence) |
| `archive_files.snapshot` | `engine._snapshot_turn` (rows of a snapshot only) | `views.verify`, `views._refuse_duplicates` (key), `archive.snapshot_folder` callers |
| `tasks.<id>.turns[]` | `plan.build_plan` (X-J1, `turns` only) | `engine._attempt` (prompt text), `lifecycle`, X-J2 |

**Snapshot folder (W0 section 14 asks this doc to name it).** `<run_dir>/archive/<cell_id>/turn-<n>/`, holding only the cell's `ws/` tree, with row paths relative to the cell folder (`ws/a.txt`), the same convention as the final archive's `ws/a.txt`. One helper builds the path: `archive.snapshot_folder(run_dir, cell_id, turn)` (decision D-J1). Why this name:
- It is a sibling of `attempt-1/` inside `archive/<cell_id>/`, as ADR-0015 section 5 requires ("a sibling folder of the final archive").
- It does **not** start with `attempt-`. Section 8 lists the readers that glob that prefix; none of them can see `turn-<n>`.
- `publish_dir`'s temporary sibling is `turn-<n>.tmp-<pid>-<uuid4 hex>` (W0 section 4), also invisible to those globs. **The sweep (W0 rev 6, folder form; RV-DS 2):** `atomic.sweep_temps(archive/<cell_id>, run_lock)` takes the **cell's archive folder** (it is not recursive, so the archive root would never see a temp one level down) and the caller's own held `RunLock`; it deletes every `is_temp_name` entry there, by `TEMP_RE`. `stale_temps(target)` and `<name>.tmp-*` matching are the withdrawn form. X-J1 calls `sweep_temps` (a) before it publishes a snapshot into that folder and (b) after each failed `publish_dir` attempt of the retry (section 4.4 step 3), so one failing snapshot leaves nothing behind on the non-crash path; `archive/<cell_id>/` is written only by this cell's worker, so the sweep cannot meet a live copy. X-K1 (E3) sweeps the same folder on resume.
- The graded copy for `graded_snapshots: [turn-1]` is `<snapshot folder>/ws`, the same shape as the final tree's `attempt-1/ws` (section 8).
- Only `ws/` is copied, never `home/` (ADR-0015 "Alternatives": the home's native record keeps growing and only the tree is graded). Credential files are excluded by the same `exclude_names` as the final archive, though `ws/` holds none; the test pins it (T-SNAP-4).

## 3. The record contract

```text
cell.prompt_sent                {cell_id, turn}                                  turn absent reads 1
cell.turn_ended                 {cell_id, turn, stop_reason, turn_seconds, usage, next}   usage = {"usage":..., "meta":...} verbatim or null (R-24 shape)
                                next ∈ {"snapshot","final","stop","cancel"}  (granted, W0 rev 6.5a): the engine's recorded decision; absent on a
                                legacy single-turn row reads "final"; a turn with no row is a crashed turn, never read as "final"
                                job_active_baseline (turn 1 only, section 4.4; granted, W0 rev 6.5c); absent, never 0, when no update arrived
cell.turn_snapshot_archived     {cell_id, turn, snapshot_hash, files, bytes, duration_ms, job_active_processes, job_active_after, copy_retries}
                                (the last two granted, W0 rev 6.5c) job_active_processes = the count BEFORE the copy, job_active_after = the count
                                AFTER it (two instants, so both stay); copy_retries = the count publish_dir returns (no second counter)
archive_files row (snapshot)    {run_id, cell_id, archive_attempt: 1, snapshot: "turn-<n>", path, kind, size, sha256, link_target}
archive_files row (final)       unchanged: no snapshot field
```

**Ledger order for one two-turn cell (the sequence the model checks):**
`launch_intent, workspace_built, process_started, session_opened, prompt_sent{1}, turn_ended{1}, [snapshot rows], turn_snapshot_archived{1}, prompt_sent{2}, turn_ended{2}, process_ended, outcome, [final rows], archived, workspace_deleted`.
Rows are appended before the event that commits them, as `engine._archive` does today (`engine.py:803-815`). **Every new cell writes `turn_ended{1}`** (a single-turn cell has one turn), so the ledger of a run that never uses a second turn gains one row per cell; old ledgers read unchanged (T-LIF-1 holds a single-turn stream with `turn_ended{1}`, T-VER-3 the legacy golden). A live reader may see a snapshot's rows with no `turn_snapshot_archived` yet; the snapshot loop in `views.verify` iterates **events**, so rows without an event are ignored, not flagged (T-VER-6).

**The crash windows and their one recovery rule (W0 section 4, quoted):** "if `final` exists and its rows are absent, recompute the rows from the folder, compare them with the source (still in the archive root or the working copy), then append them. If `final` exists and its rows are present, verify only." The snapshot adds a third state the W0 text does not name: **some rows present** (a crash after k of n row appends). **W0 rev 6.2/6.3 settles it:** `archive.append_missing_rows(folder, rows, present, code) -> list[dict]` is the one implementation (owner X-J1, E2; X-K1 calls it), and X-J1 owns snapshot recovery in E2: when `publish_dir` raises `FileExistsError` because `turn-<n>/` already exists, `_snapshot_turn` verifies the folder, then calls `append_missing_rows(..., code="HB-LED-008")`, which appends only the rows whose key is missing and raises `code` on any present row that differs. It **never re-publishes**. The code follows the folder kind: a final archive is HB-LED-005, a turn snapshot HB-LED-008. Without the rule the retry hits `HB-LED-003 duplicate archive_files key` (`views.py:162`).
- **When this runs in E2 (RV-DS 1).** Resume is X-K1's and ships in E3, so in E2 the path is reached by the **retry of the same attempt**: a transient ledger or rows failure after the rename makes the loop run again, finds the folder, and completes it. A fresh start never finds the folder (T-SNAP-2 covers a planted one: refuse). X-K1's `recover_archive` calls the same function and holds no second comparison (DM7).
- **What resume does in E2 (RV-DS 1 d).** The existing predicate classes every prompted cell `crashfail` (stricter than the model, safe). The model's `crashbetween` path, and the redo of a between-turns snapshot, is E3 behaviour (X-K1); nothing in the measurement plan relies on it before then.

**HB codes (W0 section 11 asks this design to confirm or drop its rows).**
- **HB-LED-008 confirmed**, with a merged meaning (RV-SIM 10): "a turn snapshot does not match its record": the `snapshot_hash` differs from the rows, the event's `files` or `bytes` differ from the rows, a row's file is missing or changed under the folder, or the event exists with no rows. The message names which. It is raised by `bench verify` **and** by `append_missing_rows` on a present row that differs (the code follows the folder kind, W0 rev 6.3; HB-LED-005 is the final archive's, in both places).
- **HB-CELL-117 confirmed**: `failed (archive)`, infrastructure. It becomes `Cause.archive = ("HB-CELL-117", "infrastructure", "failed (archive)")` in `errors.py` (X-J1). The shared `cell.archive_failed` event (`engine.py:591`) is the final archive's failure; a snapshot failure ends the attempt with this cause instead.
- HB-CELL-118 and -119 stay X-K1's.

## 4. Driver and engine

### 4.1 Driver: open, send turn, close (ADR-0015 section 2a)

Today `driver.run_turn` (`driver.py:249-313`) builds the `_Channel` (`:128`), does the handshake (`initialize`, `session/new`, optional `set_model`, `set_mode`), calls `before_send` (the ack barrier, `:294`), sends one `session/prompt` (`:300`), and returns. The channel dies with the function.

New shape, in the same file:

```python
@dataclass
class TurnRecord:                 # one per session/prompt
    turn: int; stop_reason: str | None; turn_seconds: float
    usage: dict | None; last_update_seconds: float | None

class Session:                    # owns the _Channel from open to close; created by open_session
    channel: _Channel; result: TurnResult     # result is the attempt-level record
    def close(self) -> None       # idempotent: closes the channel's stdin once (RV-PAT F1); the engine's finally calls it

def open_session(cell, cwd, mode, handshake_timeout, model=None, result=None, mcp_servers=None, cancel=None) -> Session | None
    # the handshake of today's run_turn, unchanged; None means result.cause is set (same failure paths as today)
def send_turn(session, prompt, before_send, turn, on_first_update=None) -> TurnRecord | None
    # before_send(session_id) then one session/prompt; None means the turn did not end cleanly (result.cause set);
    # on_first_update() fires once, on turn 1's first session/update (the baseline read point, section 4.4)
def run_turn(...)                 # unchanged signature: open_session, then send_turn(turn=1), then close. Existing callers and tests keep working.
```

**The failure convention is the protocol (RV-PAT F1).** `open_session` and `send_turn` return `None` and set `result.cause`; that is stated in both docstrings, and the engine checks `session is None` **once, before the loop**. One object owns the channel from `open_session` to `Session.close()`; `_end_process` (kill and reap the tree) stays in the outer `finally` and calls `session.close()` first, so stdin is closed exactly once, after the last turn or on an early exit (T-DRV-2: `close()` twice is a no-op, `send_turn` after `close()` returns `None` with the cause set).

`TurnResult` stays the attempt-level record. Its `stop_reason`, `usage`, `turn_seconds` and `last_update_seconds` are **read-only properties over `turns[-1]`** (RV-PAT F7; `None` while `turns` is empty), so the quantity exists once (derive, don't store) and `engine._classify` and the outcome row read the same names as today. `turns: list[TurnRecord]` holds every turn. `assume:` the failure paths in `driver.py` do not assign these four names without a `TurnRecord` (confirm: grep the assignments before X-J1 converts them; if one does, that path appends a `TurnRecord` with `stop_reason=None` first); if false, a failure path would lose its recorded stop reason, which T-DRV-1's failure cases (`prompt_error`, EOF) catch. `last_update_seconds` and `_Channel.turn_start` are reset at the start of each `send_turn`. Session-level fields (`session_id`, `agent_version`, `permission_mode_effective`, `handshake_seconds`) are set once by `open_session`. `permission_requests` and `updates` stay cumulative.

### 4.2 Engine: `_attempt` becomes a turn loop

`_attempt` (`engine.py:684-747`) keeps its structure: spawn, `try:` the turns, `finally:` end the process and record `attempt.process_ended`. Inside the `try:` the single `driver.run_turn` call becomes:

```python
session = driver.open_session(cp, cwd=ws, mode=..., handshake_timeout=..., model=..., result=result, mcp_servers=..., cancel=a.cancel)
if session is None: return                      # result.cause is set; the finally still runs (one None check, RV-PAT F1)
self.record_session_opened(cid, session)        # attempt.session_opened, once; barrier_for no longer writes it (RV-PAT F8)
turns = [prompt] + [t["prompt"] for t in task.get("turns", [])]        # from the plan (D-J11)
for n, text in enumerate(turns, 1):
    rec = driver.send_turn(session, text, before_send=barrier_for(n), turn=n, on_first_update=baseline if n == 1 else None)
    if rec is None: break                       # no response came back: the cause is on the outcome row; there is no turn_ended
    nxt = (("cancel" if a.kill_reason == "stop" else "stop") if a.cancel.is_set() else "final" if n == len(turns)
           else "stop" if rec.stop_reason != "end_turn" else "snapshot")      # W0 rev 6.5a
    self.record("events", {"kind": "cell.turn_ended", "cell_id": cid, "turn": n, "stop_reason": rec.stop_reason,
                           "turn_seconds": rec.turn_seconds, "usage": rec.usage, "next": nxt, ...})     # BEFORE the decision
    if nxt != "snapshot": break
    if not self._snapshot_turn(a, cell, cell_dir, n, launcher, cp): break      # records HB-CELL-117 cause on failure
```

- **`turn_ended` is written for every turn that returned a response, before the continue decision** (RV-SRE 1, RV-PAT F2, RV-DS 4). It says "this turn ran", whatever the stop reason (`max_tokens`, `refusal`, an error reply that still carries a stop reason) and whether or not a kill has landed since. The decision to continue is the separate `nxt` computed beside it. A returned turn that the loop then stops on therefore keeps its `turn_seconds` and its verbatim usage in the ledger, and X-J2 counting `turn_ended` against the plan reads a finished turn as reached. A turn for which `send_turn` returned `None` (EOF, a refused prompt, a kill before the reply) has no `turn_ended`: its reason is the `cell.outcome` cause (F10, F11).
- **`next` answers "why was turn 2 not sent" in one field** (granted, W0 rev 6.5a; a recorded decision, because a stop can arrive between the turn's end and the next prompt): `snapshot` (a next turn follows, so the snapshot is taken), `final` (the last planned turn ended), `stop` (a stop reason other than `end_turn`, a budget or a deadline ends the cell), `cancel` (the run is cancelled, `kill_reason == "stop"`). A turn with no `turn_ended` row is a crashed turn; an absent `next` on a legacy row reads `final`. The cell outcome never restates the turn decision. A snapshot that then fails is `HB-CELL-117` on the outcome row, not a `next` value, because `turn_ended` is written before the copy. The idle gap before turn 2 (F17) is `prompt_sent{2}.recorded_at - turn_ended{1}.recorded_at`.
- `record_session_opened` writes `attempt.session_opened` once, after `open_session` returns (the session id and `agent_version` are known then) and before `send_turn`; `barrier_for(n)` writes only `cell.prompt_sent{turn: n}`. The order `session_opened` before `prompt_sent{1}` is unchanged (RV-PAT F8, checked against the `before_send(session_id)` call at `driver.py:294`, which runs after the handshake). A kill that lands between the two leaves a `session_opened` with no `prompt_sent`, which the lifecycle table already allows.
- The `finally:` is unchanged in shape: `a.ended = True`, then `session.close()` and `_end_process` (`:749`), which closes stdin (`:752`). Because the loop is inside the `try`, stdin is closed only after the last turn or an early exit. **Stdin is never closed between turns.**
- **Only `end_turn` continues.** `COMPLETED_STOP_REASONS` (`engine.py:60`, which includes `max_tokens`, `max_turn_requests`, `refusal`) still decides the outcome class; it must not decide whether turn 2 is sent. ADR-0015 section 2: "Any other stop reason ... ends the attempt". T-ENG-6 pins the difference (`max_tokens` on turn 1).
- **The cancel check.** A budget, stop or suspend kill sets `a.cancel` (`_kill`, `engine.py:541-548`). `nxt` reads it after the response and before any snapshot; `send_turn` also checks it after the barrier, as `run_turn` does today (`driver.py:295-297`). **Exactly one thing can happen in the gap (RV-DS 5):** the loop checks `cancel`, `barrier_for(2)` makes `prompt_sent{2}` durable, then a kill lands before `send_turn`'s own check. So `prompt_sent{2}` **may be written and the prompt never sent** (the model allows exactly this state: `promptSent` true, `prompts` 0; a resume classes it `crashfail`, which is safe). Delivery is therefore counted by `turn_ended`, never by `prompt_sent`. A snapshot already published stays.
- **Turns not reached** need no new field: X-J2 derives "turn k not reached" by counting `cell.turn_ended` events against `len(plan.tasks.<id>.turns) + 1`, and reads `next` and the outcome cause for the reason (derive, don't store).

### 4.3 One budget for every turn (ADR-0015 section 3)

`_after_append` sets `a.prompt_mono = self.clock()` on **every** `cell.prompt_sent` (`engine.py:277-283`). With turn 2 that would restart the budget clock and give the cell two budgets. The fix is one condition: set it only when `row.get("turn", 1) == 1`. `_check_budgets` (`:556`) then measures from turn 1's prompt across the snapshot copy and turn 2. The snapshot's copy time counts against the budget (decision D-J7); it is measured (`duration_ms`) and small (section 12, S-J2). `a.ended` stays False until the last turn ends, so `_kill` (`:538`) still acts between turns. ADR-0013 section 2's "At the end of every turn the engine terminates the job" becomes "at the end of the attempt's last turn" (ADR-0015 section 3; already decided).

**The operator's clock must agree (RV-SRE 2).** `status.py:128-136` builds `prompt_sent = {cell_id: event}` with the **last** row winning, so with a second turn the elapsed time of `bench status` would restart at `prompt_sent{2}` and the `over budget` flag would disagree with the engine's kill clock. X-J1 changes that one reader (granted, W0 rev 6.5b; `status.py` is on the surface list, section 7): take the **first** `cell.prompt_sent` per cell (`turn` absent or 1). **One definition of the cell's start (the rev 6.5b condition):** `lifecycle.is_cell_start(row)` (`row.get("turn", 1) == 1`), read by both `status.py` and the engine's `_after_append` clock, so neither can drift; T-STATUS-1 asserts that for a two-turn cell `bench status` elapsed equals the engine's budget clock at the same instant. The same hunk may add the turn number to `RunningCell` (the count of `prompt_sent` rows) and a `snapshotting` word while a snapshot is in flight (a `turn_ended{n}` with `next == "snapshot"` and no `turn_snapshot_archived{n}`); the second is optional, the first is the condition. T-STATUS-1 pins it.

### 4.4 The snapshot step (`engine._snapshot_turn`, worker thread)

1. `atomic.sweep_temps(archive/<cid>, run_lock)` (the folder form, section 2); then count `job_active_processes = _job_query(cp.job.active, None)` (a number, or null = not recorded, never a guessed 0; the same `_job_query` the engine uses at `:758`).
2. `archive.snapshot_cell(cell_dir, run_dir/"archive"/cid, turn=n, exclude_names)` which is `atomic.publish_dir(snapshot_folder, fill, verify)` (W0 section 4, owner X-B1): `fill(tmp)` copies `ws/` (links recorded, never followed, as `archive_cell` does today), `verify(tmp)` compares the folder's file set and every row's size and sha256. **`fill` checks `a.cancel` between files** and raises on cancel (RV-SRE 5, RV-DS 6).
3. **Retry (RV-DS 2, 6; RV-SRE 5).** A `PermissionError` or `OSError` raised by `fill` is retried up to 3 times, waiting `a.cancel.wait(delay)` for 1 s, 2 s, then 4 s, so a stop or a budget kill ends the wait at once; each failed `publish_dir` is followed by `sweep_temps(archive/<cid>, run_lock)` before the next try, so no more than one temp exists at a time. A set `a.cancel` abandons the temp (swept), writes no event, and ends the attempt on the cancel's own cause. After the third failure the attempt ends with `Cause.archive` (HB-CELL-117). The retry class is justified by S-J3: an exclusive lock or a no-share handle raises `PermissionError`; a shared handle copies. **This loop is not W0's WIN-A loop (RV-SIM 9):** `atomic.rename_with_retry` retries the `os.rename` inside `publish_dir` on `PermissionError`; this loop retries a whole `publish_dir` after `fill` could not read a locked **source** file. They fail at different calls. `copy_retries` on the event is `publish_dir`'s own returned count of the rename retries (no second counter, W0 rev 6.5c); the fill-level retries are counted only by the test (T-SNAP-6).
4. **If `publish_dir` raises `FileExistsError`** (the folder exists, so an earlier pass renamed it), do not re-publish: verify the folder and call `archive.append_missing_rows(folder, rows, present, "HB-LED-008")` (section 3).
5. Append the rows (only the missing ones), then `cell.turn_snapshot_archived` (with `copy_retries`). The event is the commit. Only after it is durable does the loop reach `barrier_for(n+1)`.

**Non-quiescent snapshots (ADR-0015 section 4, accepted).** `job_active_processes` counts every process in the cell's Job Object, **including the adapter and its own children**, so the raw count alone cannot tell "the agent left a build server running" from "the adapter has two helper processes" [Verified in `_end_process`: it waits for `job.active` to reach 0 after stdin closes, so the adapter counts]. W0 rev 6.2 granted `job_active_baseline` with RV-SRE's condition, and rev 6.5c moved it to `turn_ended{turn 1}`: **the baseline is read after the harness's lazy helper process has spawned.** The read point and its row, decided here:
- **Read point: the first `session/update` of turn 1**, through `send_turn(on_first_update=...)`, one `_job_query(cp.job.active, None)`. A helper that the adapter spawns lazily at the first prompt exists by the time the adapter streams its first update. `assume:` this order holds on the three adapters (confirm: count `job.active` right after `session/new`, at the first update and at the end of a no-tool turn 1, on each real adapter; if the first-update count is still below the end-of-turn count of a no-tool prompt, the read point moves, by a W0 amendment). If turn 1 sees no `session/update`, the field is **absent, never 0**. If false, the filter flags every quiet tree as noisy; the residual is stated in the report as "baseline not validated". Not run here (needs the three adapters on the operator's host): spike S-J4, open.
- **Read once per attempt, not per turn.** The baseline describes the adapter family, not the turn. A process the agent starts after the first update is exactly what the filter must count.
- **Row: `cell.turn_ended{1}.job_active_baseline`, not `attempt.session_opened`.** Rev 6.2 named `session_opened`, but that row is appended before the prompt (the ledger is append-only), so a reading taken after the first update cannot be on it. Granted by W0 rev 6.5c (seam SR-J7).
- **Two counts per snapshot (RV-SRE 4).** The event carries `job_active_processes` (before the copy) and `job_active_after` (after it), because a short-lived child can exit during the copy and the tree can still change. They are two instants, so both names stay (rev 6.5c asks each one's meaning in one line, given in section 3). A noisy snapshot, `job_active_processes > job_active_baseline` or `job_active_after > job_active_baseline`, is **derived by the reader, never stored**.
- Test: a fake agent that spawns a helper at the start of the prompt (before the first update) is **not** counted as a leaked job; one spawned after the first update is (T-SNAP-5).

### 4.5 Usage across turns

Today `usage = normalize.turn_usage({"_meta": (result.usage or {}).get("meta")})` (`engine.py:663`) reads the one response. For `acp_turn` profiles (claude-code) that would record **only the last turn's tokens** as the cell's spend. The fix: build `usage` as the concatenation of each turn record's entries (`[u for t in result.turns for u in normalize.turn_usage({"_meta": (t.usage or {}).get("meta")})]`); `_usage_per_model` (`:871`) already sums entries per model before the one `turn_usage` row per `(run, cell, attempt, model)`, so no key changes. (`_usage_per_model` is at `engine.py:871`.) `attempt.process_ended.acp_usage` (`:740`, R-24 "verbatim") keeps the last response; per-turn verbatim usage lives in `cell.turn_ended.usage`. `views._token_cross_check` (`views.py:354`) compares one ACP total with `model_calls`; with two turns the ACP side must be the sum, or HB-VAL-005 warns spuriously (X-J1 sums `turn_ended.usage`; **T-ENG-4 asserts `views.verify` on the two-turn run has no `HB-VAL-005`**, RV-TA 5, mutant M-XCHECK: the cross-check reads the last turn). The ACP side is the sum over the `turn_ended` rows present; a turn with no row has usage `not recorded`, never 0 (R-21 c2), so a turn-2 failure after a good turn 1 compares turn 1's ACP usage with the native record of the turns that ran. **Units (RV-SRE 6):** `cell.outcome.turn_ms` and `stop_reason` are the **last** turn's values; agent time is the sum of `turn_ended.turn_seconds` and snapshot time the sum of `duration_ms` (reader rule for X-A3); the outcome row gains `turns` (the count of `turn_ended` rows), derived by readers, not stored.

### 4.6 `lifecycle.py`: the table gains the turn rules

`lifecycle.TABLE` and `replay` (`lifecycle.py:67-190`) are the conformance mirror of the model. Today `AT_MOST_ONCE` fails on any repeated kind per cell (`replay`, `if kind in done`), and `cell.turn_ended` is "unmapped". The change (X-J1, hub file in E2):
- `replay` keys the per-cell history by `(kind, turn)` for the three turn-carrying kinds (`cell.prompt_sent`, `cell.turn_ended`, `cell.turn_snapshot_archived`); absent `turn` reads 1.
- New rules, each named for the model invariant it transcribes:

| TABLE entry | model action | rule name (the string the replay raises) |
| --- | --- | --- |
| `cell.prompt_sent#n` | QueuePromptSent, PersistPromptSent, SendPrompt | `PromptOncePerTurn` (second record of `(kind, turn)`) |
| `cell.prompt_sent#n`, n>1, after `cell.turn_snapshot_archived#(n-1)` | QueuePromptSent guard | `SnapshotBeforeNextTurn` |
| `cell.turn_ended#n` after `cell.prompt_sent#n` | TurnEnd | `turn_ended follows its prompt_sent` |
| `cell.turn_snapshot_archived#n` after `cell.turn_ended#n`, not after `cell.prompt_sent#(n+1)` | CopyBegin (idle adapter), SnapRecord | **`SnapshotAfterTurnEnd`** (RV-TA 9): a snapshot is committed only between its turn's end and the next prompt. It is **not** the model's `NoSnapshotInFlight`: a copy that *starts* while a turn runs and finishes after the turn ended is invisible in the ledger, so the model property stays model-only and is carried in code by the engine's loop order (T-ENG-1 M-ORDER) |
| `cell.outcome` with code `HB-CELL-119` / `HB-CELL-118` (X-K1's resume codes, E3) | ReconcileRecord, `ClassOf` | **`CrashedTurnPredicate`** (RV-DS 3; provisional for W1-K, who owns resume): `HB-CELL-119` requires every `prompt_sent{j}` to have `turn_ended{j}`, and some `turn_ended{k}` with `turn_snapshot_archived{k}` and no `prompt_sent{k+1}`; `HB-CELL-118` forbids exactly that shape (a cell that is waiting between turns with its snapshot recorded is 119, not 118). The model's `TurnEnd` abstracts the stop reason; W1-K may add that a between-turns cell's `turn_ended{k}` carries `stop_reason == "end_turn"` |
| `cell.archived`, `cell.turn_snapshot_archived` | CopyPublish then the record action | **`ArchiveExistsMeansComplete` has no replay rule**: "a name exists only after its copy verified" is a property of the folder, not of any ledger order. Its code mirror is the structural `publish_dir` test (T-SNAP-1, mutant M-INPLACE) and `bench verify`'s recompute (HB-LED-005, HB-LED-008) |

`CrashedTurnPredicate` has an *independent* statement in the model (`CrashedLit`, `WaitingLit`, section 6) and the replay rule above is a third statement of it, written from ledger kinds. X-K1's resume test asserts the recorded code over real ledgers for the four windows: (1) `prompt_sent{k}` and no `turn_ended{k}` (118); (2) `turn_ended{k}` durable, snapshot not yet recorded, no `prompt_sent{k+1}` (119 after the redo); (3) `turn_ended{k}`, snapshot recorded, no `prompt_sent{k+1}` (119); (4) `prompt_sent{k+1}` written, prompt not sent (118, `crashfail`, safe) (T-LIF-3 holds the streams; X-K1 runs them against the real resume).

`docs/design/run-lifecycle-model.md`'s mapping table gains the same rows (data rows, granted with SR-J2).

## 5. Patterns, and the Simplifier's challenge

| pattern | where | why it is the smallest correct idiom | the Simplifier's attack, and the answer |
| --- | --- | --- | --- |
| **Write-ahead intent with an ack barrier** (existing, ADR-0007) | `prompt_sent{turn}` through `barrier_for(n)` | reuse: turn 2 uses the same barrier as turn 1; no second mechanism | "Why not a lighter record for turn 2?" The prompt-once guarantee (P8) is the reason the barrier exists; a cheaper record loses it. Kept. |
| **Create-once / write-to-temp-then-rename** (`publish_dir`, W0 section 4) | snapshot and final archive | reuse of X-B1's helper; no second archive primitive (DM7) | "A snapshot is a copy; why not `shutil.copytree`?" A crash mid-copy leaves a folder that reads as complete; ADR-0015 section 5a is the defect class. Kept. |
| **Split a closed function into open / step / close** | `driver.run_turn` | the smallest change that lets one channel serve two prompts (spike E4 option b) | "Add a `turns` parameter to `run_turn` instead." Rejected: the barrier, the snapshot and the cancel check must interleave between prompts, and they live in the engine. `run_turn` stays as a two-line wrapper so existing callers and tests do not change. |
| **Key part with an absent-reads-default** | `snapshot`, `turn` | expand-only schema evolution; no backfill | "Two tables." Rejected in ADR-0015 (a separate `turn_snapshots` fact duplicates `archive_files` and its verify path). |
| **Event-sourced commitment** (rows, then one event that hashes them) | `cell.turn_snapshot_archived` | the shape `cell.archived` already has | none; it is reuse. |

**The snapshot is a checkpoint (RV-PAT F4).** It is a write-once, hash-sealed *archived checkpoint*, a value object with no restore: not a Memento (no opaque state handed back to an originator). "Restore" is a non-goal and no `restore` method is added. The commitment shape is the event-sourced row above.

Simplifier cuts accepted: no per-turn budgets, no snapshot of `home/`, no `turn` field on the plan cell, no third turn, no new fact, no sweep action in the model (section 6). Solution-Selection Ladder: every step reuses (rung 2) or is stdlib (rung 3); no new dependency.

## 6. The lifecycle model (`models/run_lifecycle.tla`, version 5)

**What changed, and why each addition is there.**
- `NumTurns` (constant, 1 or 2). With 1 the model is the version-4 lifecycle plus phased archive writes; with 2 it adds the turn rules. ADR-0015 bounds a task to two turns, so the model does too.
- Per-cell, per-turn: `promptSent[c][k]`, `prompts[c][k]`, `turnEnded[c][k]`, `snapEv[c][k]` (ledger); `queued[c]`, `pendingSend[c]` now hold the turn number (0 none).
- Archive writes are phased as the engine will do them (ADR-0015 section 5a): `CopyBegin` (fill a temporary sibling) then `CopyPublish` (verify and rename to the final name) then a record action (`Archive` for the final tree, `SnapRecord` for a snapshot). `tmp[c][a]` and `fin[c][a]` hold the two names' states for artifact `a` (0 the final archive, k the turn-k snapshot); `copying[c]` names the one copy in progress (volatile, lost at a crash). A crash leaves a rename done and its event unrecorded; the record action then completes on resume (the W0 recovery rule).
- New actions: `TurnEnd(c,k)`, `CopyBegin`, `CopyPublish`, `SnapFail(c,k)` (HB-CELL-117), `SnapRecord(c,k)`. `QueuePromptSent(c,k)` for k>1 requires `turnEnded[c][k-1]` and `snapEv[c][k-1]`. **`TurnEnd` no longer requires `~killRequested` (rev 2):** the ledger records `turn_ended` for every turn that returned, whether or not a kill has landed since (section 4.2); no invariant depended on the old guard, and TLC re-run (section 6.1) confirms it. `TurnEnd` also abstracts the stop reason: whether turn k+1 follows is the engine's rule (T-ENG-6), not the model's.
- Resume classification: `ClassOf(c)` records `crashfail` for a crashed turn (`promptSent[c][k]` and no `turnEnded[c][k]`), `crashbetween` for a cell between turns (`turnEnded[c][k]`, no `promptSent[c][k+1]`), else `crashfail` (all turns ended, no outcome: ADR-0007's rule). A cell between turns first has its snapshot redone (`BetweenSnapped`), as ADR-0021 section 4 row 3 says. **Provisional for W1-K (RV-SIM 6):** `BetweenSnapped` and the final `ELSE` branch of `ClassOf` are the resume rules that X-K1 builds in E3 and W1-K may refine (for instance by reading the turn's stop reason); they are marked so in the `.tla` header and W1-K owns them at its join. W1-J adds nothing for resume to the E2 build list; what *is* held here is the invariant (next row) and its seeded variants.
- **Not modelled, on purpose:** the temporary-folder sweep. W0 names temps `<name>.tmp-<pid>-<uuid>`, so a stale temp can never collide with a later copy; a Crash clears `tmp` in the model because a leftover is inert. The sweep is bookkeeping, tested at file level (T-SNAP-1). Also not modelled: the budget clock (code-level, T-ENG-2), the process-count gauge, row-by-row appends (T-SNAP-3).

**The five invariants of ADR-0015 section 7** (all in `run_lifecycle.turns.cfg` at two turns; `run_lifecycle.safety.cfg` lists them too at `NumTurns = 1`, where `SnapshotBeforeNextTurn` is vacuous and `NoSnapshotInFlight`, `CrashedTurnPredicate` and `ArchiveExistsMeansComplete` constrain the final archive and the single-turn resume):

| invariant | definition (TLA+) | seeded variant TLC must reject | the variant's change |
| --- | --- | --- | --- |
| `PromptOncePerTurn` | `\A c, k : prompts[c][k] <= 1` | `relaunch_prompted`, `send_before_persist` (existing, retargeted from `AtMostOnePrompt`), `resend_turn_on_resume` (new) | reconciliation reopens a crashed turn k>1 and the cell is launched and prompted again |
| `SnapshotBeforeNextTurn` | `(promptSent[c][k] \/ prompts[c][k] >= 1) => snapEv[c][k-1]` | `prompt_before_snapshot` | `QueuePromptSent(c,k)` drops the `snapEv[c][k-1]` guard |
| `NoSnapshotInFlight` | `copying[c] # NoCopy => ~InFlight(c)` | `snapshot_in_flight` | `CopyBegin(c,k)` is allowed while turn k is still in flight |
| `CrashedTurnPredicate` (rev 2: independent of `ClassOf`, RV-TA 2) | for a recorded crash outcome: `CrashedLit(c) => outcome = crashfail`; `WaitingLit(c) => outcome = crashbetween`; `outcome = crashbetween => WaitingLit(c)`, where `CrashedLit(c) == \E k : promptSent[c][k] /\ ~turnEnded[c][k]` and `WaitingLit(c)` is "no crashed turn, and some `turnEnded[c][k]` with no `promptSent[c][k+1]`" (ADR-0015 section 7's `promptSent /\ ~turnEnded /\ ~terminal`, stated from ledger facts) | `kill_between_turns` (a between-turns cell classed `crashfail`: fails the second implication); **`crashed_turn_as_between`** (new; a crashed turn classed `crashbetween`: fails the first and third) | the old predicate, and its reverse |
| `ArchiveExistsMeansComplete` | `\A c, a : fin[c][a] # "none" => fin[c][a] = "complete"` | `archive_in_place` (a=0), `snapshot_in_place` (a>0) | the copy fills the final name directly |

`SnapshotBeforeNextTurn` and `NoSnapshotInFlight` are adjacent rules about the same step: the first orders the **next prompt** after the snapshot event, the second forbids the **copy** while a turn runs. `prompt_before_snapshot` leaves copies alone and removes only the ordering guard; `snapshot_in_flight` removes only the idleness guard. Each is rejected by its own invariant checked alone (`only_invariant` in `check_models.py`), so neither can hide behind the other.

**Witnesses (each must be violated, so a pass is not vacuous):** `NotAllTurnsDelivered` (a cell completes both turns after the turn-1 snapshot) and `NotCrashBetween` (a resume classes a between-turns cell with its snapshot recorded).

**Configurations.**
- `run_lifecycle.turns.cfg` (new): 2 cells, parallelism 1, 1 crash, 1 pass, engine grading, `NumTurns = 2`, symmetry.
- `run_lifecycle.liveness.cfg`: 1 cell, `NumTurns = 2`. The fairness set gained `CopyBegin`, `CopyPublish`, `SnapRecord` for every artifact. The first liveness run found a real gap: without fairness on the redo copy a resumed between-turns cell could wait forever on its snapshot, and `PromptedCellsEnd` failed; the fairness is the engine's own duty (it redoes the snapshot), not an assumption about the environment.
- `run_lifecycle.safety.cfg`, `run_lifecycle.grading.cfg`: `NumTurns = 1`.

**The grant: `tools/check_models.py` (seam `req-01M41F2PAKH97KH6BDGXCTA1KK`, SR-J2 ruled in W0 rev 6.3).** The ruling: use RV-SIM's `WIDER` route for the turn variants as **data**; only the lines that cannot be data are granted as logic, and this revision lists them. The `.tla`, `run_lifecycle.turns.cfg`, `tools/check_models.py` and `tests/test_check_models.py` land **in one commit**, proved by `tests/test_check_models.py` and `check_models.py --quick` green on the merged tree (command, exit status and counts in section 6.1). Without the script the reverse MOD-A check (`unregistered_variants`) and three tests fail the moment the `.tla` lands.

*Data (no logic):* the `AtMostOnePrompt` to `PromptOncePerTurn` rename (2 rows); 7 new `VARIANTS` rows (`resend_turn_on_resume`, `prompt_before_snapshot`, `snapshot_in_flight`, `kill_between_turns`, `crashed_turn_as_between`, `archive_in_place`, `snapshot_in_place`); one `TWO_TURNS = {"NumTurns = 1": "NumTurns = 2"}` substitution; 8 new `WIDER` rows (the six variants that need a second turn and the two turn witnesses, keyed by label); 2 `WITNESSES` rows (`turns-witness`, `between-witness`); the one equality in `tests/test_check_models.py` that lists `WITNESSES`, and the `AtMostOnePrompt` string in the single-target test.

*Logic, listed (the only two lines that could not be data):*

| line | what | why it cannot be data |
| --- | --- | --- |
| **L1** | `runs = [..., ("safety-turns", turns)]`, with `turns = (MODELS / "run_lifecycle.turns.cfg").read_text(...)` | the real design must pass at two turns with the turn invariants; `SMALL` is shared by every variant and witness, so putting `NumTurns = 2` there would also move every old variant and the bench-grading real run to two turns (size not measured, and the engine-only `turns.cfg` is 14.9M states, 74 s). A new run is a new list entry |
| **L2** | the witness loop: `only_invariant(substitute(small, WIDER.get(label, {})), name)` | the existing loop passes `small` unchanged; the two turn witnesses need two turns, so the loop must look up `WIDER` by label as the variant loop already does |

RV-PAT F6 (the `VARIANTS` shape): the data rows reuse the existing `WIDER`/`substitute` mechanism instead of a parallel `TURN_VARIANTS` set, so no third dispatch is added; if a third bounds class appears, fold `WIDER` into `VARIANTS[bug] = (kind, target, bounds)` then (`simplify:` ceiling: one substitution dict per label; trigger: a third bounds class).

### 6.1 TLC run (the evidence; revision 2 re-run on the revised model)

**TLC version and host.** TLC2 2.19 (08 August 2024), `tla2tools.jar` from `.tools/` (the pinned jar `check_models.py` verifies by sha256), Java 21.0.11, 24 workers, this Windows host, 2026-10-03. The model and the script are the revised ones of this commit (`TurnEnd` without `~killRequested`, the independent `CrashedTurnPredicate`, the variant `crashed_turn_as_between`, the `WIDER` rows). The first-pass numbers (v5) are kept in the history table at the end of this section.

**The command** (every run; `<cfg>` is the file named in the table; from the `models/` folder; `check_models.py` runs the same line through `subprocess`):

```text
java -XX:+UseParallelGC -XX:MaxRAMPercentage=75 -cp <repo>/.tools/tla2tools.jar tlc2.TLC -workers auto -metadir <scratch> -config <cfg> run_lifecycle.tla
```

**The gate command and its result (SR-J2).** From the merged tree, in this order:

```text
PYTHONPATH=src python -m pytest tests/test_check_models.py -q      -> 7 passed, exit 0
python tools/check_models.py --quick                               -> exit 0, "all model checks passed"
```

**The real design passes (BUG = "none").** Exit status 0 and "No error has been found" for each (distinct states and time from the `--quick` output below):

| run | config | distinct states | time | exit |
| --- | --- | --- | --- | --- |
| liveness (5 properties), 1 cell, 1 crash, `NumTurns = 2` | `run_lifecycle.liveness.cfg` | 154,632 | 23 s | 0 |
| grading, 2 cells, 2 passes, engine and bench | `run_lifecycle.grading.cfg` (`NumTurns = 1`) | 38,172,744 | 177 s | 0 |
| safety small (2 cells, parallelism 1, engine and bench grading) | `safety.cfg` with `check_models.SMALL` (`NumTurns = 1`) | 12,996,464 | 56 s | 0 |
| **safety, two turns** (2 cells, parallelism 1, 1 crash): all five ADR-0015 invariants and the ten others | `run_lifecycle.turns.cfg` (`NumTurns = 2`) | 14,946,904 | 74 s | 0 |
| **two crashes, two turns, 1 cell** (RV-TA 3, RV-DS 9: a second crash in the redo copy of a between-turns cell) | `turns.cfg` with `Cells = {c1}`, `MaxCrashes = 2` | 230,320 (736,197 generated, depth 37; collision estimate 4.4E-8 actual) | 3 s | 0 |
| **two crashes, two turns, 2 cells** (parallelism 1 beside a copying cell) | `turns.cfg` with `MaxCrashes = 2` | 43,280,528 (176,170,525 generated, depth 59; collision 1.1E-4 actual, 3.1E-4 optimistic) | 255 s | 0 |
| **US-44 bounds** (3 cells, parallelism 2, 1 crash), fingerprint function 7 (`-fp 7`) | `run_lifecycle.safety.cfg` (`NumTurns = 1`) | 363,738,864 (1,855,270,173 generated, depth 58; collision estimate 4.1E-3 actual, 2.9E-2 optimistic; the same distinct count as the first pass) | 42 min 46 s | 0 |

The two-crash rows close RV-TA 3's gap directly: the run that the first pass skipped is now a measured row (both pass). They are one-time evidence for this model revision and are **not** added to `check_models.py` (no new run line: RV-SIM's rule that the script gains data rows, not runs; `--deep` already adds 2 crashes at the safety bounds). The US-44 row is **one-time evidence** (RV-SIM 3): the archive protocol did not change in this revision (only `TurnEnd`'s guard and an invariant's formula did), `--quick` skips it, and it is not in any ring; it is re-run, with `--deep`, only when a change touches the archive protocol. It uses a different fingerprint function from the first pass (`-fp 7` against the default), so the two runs together bound the miss that RV-TA 3 named; the first-pass collision estimate was 2.8e-3 (actual).

**Every seeded variant is rejected by its own target, and all four witnesses are violated.** Verbatim output of `python tools/check_models.py --quick` on the merged tree (exit 0):

```text
ok   liveness                 real design, 154632 states, 23s
ok   grading                  real design, 38172744 states, 177s
ok   safety-small             real design, 12996464 states, 56s
ok   safety-turns             real design, 14946904 states, 74s
ok   witness                  NotAllCellsFinished violated (3s)
ok   grace-witness            NoGraceState violated (1s)
ok   turns-witness            NotAllTurnsDelivered violated (3s)
ok   between-witness          NotCrashBetween violated (3s)
ok   relaunch_prompted        rejected by PromptOncePerTurn
ok   send_before_persist      rejected by PromptOncePerTurn
ok   launch_after_outcome     rejected by NoPromptAfterOutcome
ok   archive_live             rejected by NoArchiveWhileLive
ok   delete_before_archive    rejected by NothingDeletedUnarchived
ok   grade_twice              rejected by GradedOncePerPass
ok   grade_unarchived         rejected by GradedOnlyWhenArchived
ok   no_lock                  rejected by AtMostOneActivePass
ok   apply_twice              rejected by ControlAppliedOnce
ok   launch_after_stop        rejected by NoLaunchAfterStop
ok   exceed_parallelism       rejected by ParallelismBound
ok   reconcile_no_wait        rejected by NoLaunchBesideOrphan
ok   relaunch_stopped         rejected by StoppedNeverRelaunched
ok   double_resolution        rejected by DecisionResolvedOnce
ok   launch_while_open        rejected by NoLaunchWhileDecisionOpen
ok   record_while_running     rejected by NoOutcomeWhileRunning
ok   no_timeout               rejected by DecisionEventuallyResolved
ok   stop_ignored             rejected by StopReachesTerminal
ok   record_without_kill      rejected by EndedCellsGetArchived
ok   no_budget_kill           rejected by PromptedCellsEnd
ok   grade_skipped            rejected by ArchivedCellsGetGraded
ok   no_escalate              rejected by StopReachesTerminal
ok   resend_turn_on_resume    rejected by PromptOncePerTurn
ok   prompt_before_snapshot   rejected by SnapshotBeforeNextTurn
ok   snapshot_in_flight       rejected by NoSnapshotInFlight
ok   kill_between_turns       rejected by CrashedTurnPredicate
ok   crashed_turn_as_between  rejected by CrashedTurnPredicate
ok   archive_in_place         rejected by ArchiveExistsMeansComplete
ok   snapshot_in_place        rejected by ArchiveExistsMeansComplete
seeded variants: 29/29 rejected by own target
reachability witnesses: 4/4 violated
all model checks passed
exit=0
```

The new variants are the last seven lines before the totals; with the retargeted rows they cover the five ADR-0015 section 7 invariants (`PromptOncePerTurn` also keeps its older variants; `CrashedTurnPredicate` has one variant in each direction; `ArchiveExistsMeansComplete` has one for the final archive and one for a snapshot). Each was run against **its target alone** (`only_invariant`), at two turns through the `WIDER` rows when it needs a second turn. **`snapshot_in_place` stays (RV-SIM 4, advice declined):** `InPlace(a)` is one predicate with two branches in one action, and I found no snapshot-only branch in `CopyBegin` either, so its marginal power is low (Inferred). It is kept because it costs one short TLC run in `--quick` and `a > 0` is the artifact index the code uses for snapshots; if a reviewer wants 28, drop that one row. The user-visible counts are 29/29 variants and 4/4 witnesses.

**What the revised invariant separates (RV-TA 2).** `kill_between_turns` classes a between-turns cell `crashfail`, which fails the second implication of the new `CrashedTurnPredicate` (`WaitingLit(c) => crashbetween`); `crashed_turn_as_between` classes a crashed turn `crashbetween`, which fails the first and the third. A wrong `ClassOf` that tested the between-turns case first cannot differ at `NumTurns = 2` (the two cases are disjoint there), so that ordering is not seeded; both directions of a wrong *result* are.

**History (first pass, v5).** Liveness 154,632; grading 38,172,744; safety small 12,996,464; safety turns 14,946,904 in 83 s; US-44 bounds 363,738,864 distinct (1,840,589,597 generated) in 41 min 54 s, collision estimate 2.8e-3; 28/28 variants. The distinct-state counts of the four `--quick` runs are unchanged by the revision: dropping `~killRequested` from `TurnEnd` adds transitions, not states, (Inferred: a state with a pending kill and a finished turn was already reachable by finishing the turn first; the equal counts are the Verified part.) **What the first runs found** (kept as evidence the checks have teeth): (1) a liveness property failed on the first extension: a resumed between-turns cell waited forever for a snapshot nobody was obliged to take; the fix was fairness on `CopyBegin` for every artifact. (2) A counterexample showed a stale temporary folder being published by an unrelated later copy when `copying` was a boolean; the fix made `copying[c]` name the artifact in progress. (3) `PromptedCellsEnd` read `promptSent[c]` as a boolean after the variable became a per-turn function; TLC rejected the non-boolean at the initial state.

**Without the grant, what breaks on main.** With main's `tools/check_models.py` and `tests/test_check_models.py` and this model: `3 failed, 4 passed` (`test_every_checked_property_has_a_seeded_variant`, `test_every_seeded_variant_targets_a_declared_property`, `test_an_unregistered_seeded_bug_is_rejected_by_the_reverse_check`). That is why the `.tla`, the turns `.cfg`, the script and its test land in **one commit** (SR-J2 ruling).

## 7. Change-surface list (E7)

store (`events`, `archive_files` segments, the archive folder tree) -> model (`run_lifecycle.tla`, `lifecycle.TABLE`) -> service (`driver.py`, `engine.py`, `archive.py`) -> projection and wire (`views.KEYS`, `views.verify`, `plan.py`) -> client type (`TurnResult`, `TurnRecord`, `Cause.archive`) -> UI (report) -> compute reader (grade, report).

| # | surface | what changes | owner (W0 section 13) | reached by test |
| --- | --- | --- | --- | --- |
| 1 | `models/run_lifecycle.tla` and `.cfg` | this design | W1-J | TLC (section 6.1) |
| 2 | `tools/check_models.py` (data rows plus two listed logic lines, section 6); `tests/test_check_models.py` (two data edits); `docs/design/run-lifecycle-model.md` and `models/README.md` (mapping rows, the config list) | variants, witnesses, turns run | SR-J2, ruled in W0 rev 6.3; lands **in one commit with the `.tla` and the turns `.cfg`** | `test_check_models.py` (7 tests green) and `check_models.py --quick` (section 6.1) |
| 3 | `lifecycle.py` `TABLE` and `replay` | the turn rules and the two code mirrors (section 4.6) | X-J1 | T-LIF-1..3 |
| 4 | `driver.py` | `open_session`, `send_turn`, `Session.close`, `TurnRecord`, `run_turn` wrapper | X-J1 (not a hub-table file; the driver has no other E2 owner, section 13 note) | T-DRV-1, T-DRV-2, T-ENG-1 |
| 5 | `engine.py` `_attempt`, `_after_append`, `record_session_opened`, `_snapshot_turn`, usage sum, barrier | the turn loop, `turn_ended` for every returned turn, and the budget fix | X-J1 | T-ENG-1..11 |
| 6 | `archive.py` | `snapshot_cell`, `snapshot_folder`, `snapshot_of`, `append_missing_rows` (the one helper, W0 rev 6.2); shares `_copy` with `archive_cell` | X-J1 (X-B2 changed `archive_cell` to `publish_dir` in E1) | T-SNAP-1..8, T-VER-7 |
| 7 | `views.py` `KEYS["archive_files"]`, `verify` | add `snapshot` (through `snapshot_of`); final-rows filter; snapshot verification over events | X-J1 | T-VER-1..7 |
| 8 | `errors.py` | `HB-LED-008` text, `Cause.archive` (`HB-CELL-117`) | X-J1 | `test_errors.py` (existing registry test) |
| 9 | `plan.py` | `tasks.<id>.turns` `[{n, prompt, sha256}]` and the refusal of a text that does not hash (HB-LED-002) | X-J1 (`turns` only) | T-PLAN-1, T-PLAN-2 |
| 10 | `ledger.py` | nothing: **Verified** (RV-TA 10): `ledger.py` carries no kind allowlist, so the new kinds are plain `events` rows | X-J1 | T-ENG-1 (a row of each kind is appended) |
| 11 | `grade/runner.py` | reads `archive.snapshot_folder` for `graded_snapshots`; no other change | X-J2 | out of scope here; the helper is the contract |
| 12 | `report/*` | quiescence filter (`job_active_*` against the baseline); per-turn rows; agent time as the sum of `turn_seconds` | X-A3 / later | out of scope here |
| 13 | `tests/fake_acp_agent.py` | options `per_turn`, `prompts_log`, `helper`, `daemon_after_update` (section 11) | X-J1 (tests) | T-ENG-1, T-SNAP-5 |
| 14 | `status.py:128-136` | elapsed and the over-budget flag read the **first** `cell.prompt_sent`; optional turn number and `snapshotting` | X-J1, granted by W0 rev 6.5b (one hunk, shared cell-start definition) | T-STATUS-1 |

**Sweep: every reader of the archive folder, checked against the tree** (`grep -rn '"archive"' src --include=*.py`, run in this worktree):

| file:line | what it reads | sees `turn-<n>`? |
| --- | --- | --- |
| `engine.py:807` | writes `archive/<cid>/attempt-1` | n/a (writer) |
| `grade/runner.py:306` | `archive/<cid>/attempt-{attempt}` (fixed name) | no |
| `report/credentials.py:91-94` | `archive.glob("*/attempt-*/home")` | no |
| `report/judges.py:216` | `(archive/<cell>).glob("attempt-*")`, then `int(name.split("-")[1])` | no |
| `report/pack_improvement.py:783-786` | `base.glob("attempt-*")`, filtered by a digit suffix | no |
| `report/summaries.py:235` | `archive/<cell>/attempt-1` (fixed) | no |
| `report/html.py:2305` | `(run_dir/"archive").is_dir()` | no |
| `views.py:686` | `archive/<cid>/attempt-{attempt}` per `cell.archived` event | no; **gains** the snapshot loop |

A name such as `attempt-1-turn-1` would have matched three of these globs (`int("1")` parses; `rsplit("-",1)[-1].isdigit()` is true). That is why the folder is `turn-<n>` (D-J1). **The scan and its count (RV-TA 8, README 2a item 5), run on this revision's base `cb82cee9`:** `grep -rnE '"archive"|archive_dir|attempt-' src --include=*.py` outside `archive.py` gives 14 lines in 11 files: **8 files in the table** (one writer, `engine.py`, and 7 readers), **1 annotation** (`grade/__init__.py:56`, a comment-only type note) and **2 false positives** (`git archive` calls in `grade/_changes.py:98` and `workspace.py:154`). RV-TA's independent re-scan on main found the same 8 readers and the annotation. T-SWEEP-1 asserts that exact set of files, with the annotation and the two `git archive` files in a named allowlist, and runs the scan against a synthetic source tree (`archive/<cid>` plus `glob("*")`) that it must flag.

## 8. Failure-mode analysis

| # | category | failure mode | disposition | residual / test |
| --- | --- | --- | --- | --- |
| F1 | state | crash during a snapshot copy | prevent: copy to a temp sibling, rename after verify; the retry and resume sweep the temp (`sweep_temps(archive/<cid>, run_lock)`) and redo the copy | T-SNAP-1 (no `*.tmp-*` left after HB-CELL-117); model `ArchiveExistsMeansComplete` |
| F2 | state | crash after the rename, before the rows or event | recover: `FileExistsError` then verify and `append_missing_rows(..., "HB-LED-008")`, never a re-publish (X-J1 in E2) | T-SNAP-3 |
| F3 | state | crash between turns | accept: the adapter died with the engine (kill-on-close); record `failed (coordinator crash between turns)` (X-K1), never relaunch | model `CrashedTurnPredicate`, witness `NotCrashBetween`; X-K1 owns the code |
| F4 | concurrency | a process the agent left running writes during the copy | accept (ADR-0015 section 4); measure via `job_active_processes` and the baseline | T-SNAP-5; residual: a report that ignores the filter counts a noisy snapshot |
| F5 | concurrency | a kill (budget, stop, suspend) arrives during the copy | prevent turn 2: `fill` and the retry wait check `a.cancel`; the cancel check follows the copy; keep a published snapshot, abandon an unpublished temp | T-ENG-7 |
| F6 | resource | a lingering process holds a file exclusively | mitigate: bounded retry, then `failed (archive)` HB-CELL-117 | T-SNAP-6; S-J3 |
| F7 | resource | the copy takes long and eats the budget | accept: counted in the one budget, measured in `duration_ms`. **The 1.3 s figure is `archive_cell` only and a floor** (S-J2 did not time `publish_dir`'s per-file fsync or its verify re-read, and N cells snapshot together at the supervisory tick). Ceiling to hold: **10 s per snapshot**; exceeding it is a recorded finding in the report (a `duration_ms` over the ceiling), never a kill. The first real run replaces the quote | S-J2 (re-run through the real `publish_dir`, spike S-J5, open); a `bench plan` envelope already adds copy time (ADR-0021 section 8) |
| F8 | resource | disk fills during the copy | detect: the copy raises `OSError`; `Cause.disk` is the existing cause (`_disk_full`), the attempt ends | covered by the retry branch classification (T-SNAP-6 variant) |
| F9 | input | turn 1 ends with `max_tokens`, `refusal` or an error | prevent turn 2: only `end_turn` continues; `turn_ended{1}` is written with `next: "stop"` | T-ENG-6 |
| F10 | input | the adapter dies between turns (EOF on turn 2's send) | detect: `send_turn` returns `None` with `adapter_crash`; the attempt ends; the snapshot stays; turn 2 has no `turn_ended` | T-ENG-8 |
| F11 | dependency | auth fails on turn 2 | detect: `blocked_auth` through `_prompt_error_cause`, never NOT_RECORDED (council R4) | T-ENG-9 |
| F12 | time | host sleeps during turn 2 or the snapshot | detect: `SleepDetector` covers the whole attempt (`engine.py:379-397`); `host_suspended` | T-ENG-5 |
| F13 | state | the turn-2 budget restarts | prevent: set `prompt_mono` only at turn 1 | T-ENG-2 |
| F14 | state | the final `archive_hash` absorbs snapshot rows and every verify fails | prevent: `verify` filters final rows; KEYS carries `snapshot` | T-VER-1 |
| F15 | state | two turn-1 prompts after a resume | prevent: `PromptOncePerTurn` in the model and `replay` | T-LIF-1; X-K1 test |
| F16 | dependency | the third-prompt behaviour is unverified | prevent: the plan refuses more than one entry in `turns` (the readiness check is X-E's; the engine loop is generic but the model is bounded at 2) | T-PLAN-2 |
| F17 | state | `session/prompt` for turn 2 arrives after the adapter's own timeout | accept: the session lived for the spike's seconds. **Measured by default (RV-SRE 9):** the idle gap is `prompt_sent{2}.recorded_at - turn_ended{1}.recorded_at`, and a stale session shows as turn 2's `turn_seconds` against turn 1's (section 10) | the first rework run reads the gap; no test beyond T-ENG-1's ordering |
| F18 | state | a turn-2 failure after a good turn 1 loses turn 1's spend | prevent: `turn_ended{1}` carries turn 1's verbatim usage and is written before the snapshot; the ACP side of HB-VAL-005 is the sum over the rows present, missing usage reads `not recorded` | T-ENG-4, T-ENG-8 |
| F19 | state | the operator's clock disagrees with the kill clock on a two-turn cell | prevent: `status.py` reads the first `cell.prompt_sent` | T-STATUS-1 |
| F20 | state | a live `bench verify` sees snapshot rows with no event yet | prevent: the snapshot loop iterates events; rows without an event are ignored | T-VER-6 |

## 9. STRIDE-lite and privacy

**Trust boundaries.** (1) Agent -> working copy: the agent is untrusted and writes `ws/`. (2) Working copy -> archive: bench copies the agent's bytes. (3) Archive -> grader: `graded_snapshots` hands the snapshot to a grader.

| threat | boundary | disposition | negative test |
| --- | --- | --- | --- |
| **S**poofing: a snapshot folder planted before bench writes it | 2 | `publish_dir` refuses an existing final name; `verify` compares rows with the event | T-SNAP-2 (pre-existing `turn-1`: refuse, never merge) |
| **T**ampering: the agent edits an archived snapshot afterwards | 2, 3 | `bench verify` recomputes `snapshot_hash` and each file (HB-LED-008) | T-VER-2 |
| **T**ampering: a symlink or junction in `ws/` makes the copy read outside | 1, 2 | links are recorded as rows and never followed (existing `archive_cell` rule, kept in the shared `_copy`) | T-SNAP-7 |
| **R**epudiation: a turn's prompt text changes after planning | 2 | the plan stores each turn's prompt and sha256 (US-9) | T-PLAN-1 |
| **I**nformation disclosure: credentials in a snapshot | 2 | only `ws/` is copied; `exclude_names` applies | T-SNAP-4 |
| **D**enial of service: a huge or many-file `ws/` stalls the copy | 1, 2 | the copy is inside the one budget; the kill check follows it | T-ENG-7 |
| **E**levation: the agent in turn 1 plants a file the grader runs from the snapshot | 3 | unchanged from the final tree's exposure: the grader runs hidden checks on a copy under its own sandbox (W1-F's contract); no new class | not a new surface |

**Privacy (LINDDUN).** No personal data: the snapshot holds what the agent wrote into a benchmark task workspace, and the turn prompts are authored task text. The existing archive retention and credential exclusion apply unchanged. No data leaves the host. Privacy veto: not triggered.

## 10. Telemetry (Observability Standard; instrumentation over inference)

Questions an operator will ask, and the named source that answers each, on the normal path with no flag:

| question | source |
| --- | --- |
| how long did each turn take | `cell.turn_ended.turn_seconds` |
| how long did each snapshot take | `cell.turn_snapshot_archived.duration_ms` |
| how much did it copy | `.files`, `.bytes` |
| how many snapshots / turns per cell | count of the two kinds per `cell_id` |
| did it fail, and why | the cell's `cell.outcome` with `code: HB-CELL-117` (snapshot) or the turn's cause; `log.error` with `error_code` |
| why was turn 2 not sent | `cell.turn_ended{1}.next` (`stop`, `cancel`, `final`) and `.stop_reason`; a snapshot failure is the outcome's `HB-CELL-117` |
| how long was the idle gap before turn 2 (F17) | `prompt_sent{2}.recorded_at - turn_ended{1}.recorded_at`; turn 2's `turn_seconds` against turn 1's |
| how often does the copy hit a lock | `cell.turn_snapshot_archived.copy_retries` |
| was the tree quiescent | `.job_active_processes` and `.job_active_after` against `cell.turn_ended{1}.job_active_baseline` (read at turn 1's first update, section 4.4) |
| agent time and snapshot time of a cell | sum of `turn_ended.turn_seconds`; sum of `duration_ms` (the outcome's `turn_ms` is the last turn only) |
| what did each turn spend | `cell.turn_ended.usage` (verbatim); the summed `turn_usage` row |
| did the model check pass | the `check_models.py` log lines (build-time control, as for the existing model) |

Cost axes covered: latency (turn and copy), volume (files, bytes), spend (usage per turn), failure rate (HB-CELL-117 outcomes). Every path degrades to null, never to 0: `job_active_processes` and `usage` are null when not reported. One structured log line per snapshot: `log.info("turn snapshot archived", extra={cell_id, turn, files, bytes, duration_ms})`, and on failure `log.error(..., extra={error_code: "HB-CELL-117", ...})`, using the existing logger and `trace_id` correlation (`engine.py:924`). The planned test for the load-bearing fields is T-ENG-1 (schema and plausibility of each field).

## 11. Test plan, by node id

**The five testability checks (README 2a), per test.** (a) the **assertion that fails on the skeleton commit K2** below, and why; "red" is never an `ImportError`, `AttributeError` or `NameError`. (b) the red fixture for every guard or scan. (c) the real-wiring test beside any fake. (d) the mutant that separates adjacent rules. (e) the allowlist or sweep, with its scan count (section 7). Each mutant is a `tests/mutations/<module>.json` row, run by the repo's existing mutation runner.

Real wiring used throughout: the real `driver` and `engine` against `tests/fake_acp_agent.py`, a separate OS process that speaks ACP on stdio (the existing pattern in `test_engine.py`); the real `archive`, `atomic.publish_dir` and `views` on `tmp_path`; no fake driver anywhere. The fake agent is the only fake. **Beside it (README 2a item 3), T-WIRE-1 drives the real `cli.py` commands** (`bench plan` then `bench run`) over a two-turn task: it fails if the line that carries `turns` from the plan into the engine loop is removed.

### Commit order for X-J1 (RV-TA 4, 6)

| commit | content | why this order |
| --- | --- | --- |
| **K1** fake-agent options | `tests/fake_acp_agent.py` gains `per_turn` (a list, one config per `session/prompt`: `sleep`, `usage`, `stop_reason`, `prompt_error`, files to write), `prompts_log` (a path: one JSON line per `session/prompt` with a sequence number, one `eof` line when stdin closes), `helper` (a detached helper spawned at the start of the prompt, before the first update) and `daemon_after_update` (the existing `daemon`, started after the first update). `daemon` and `prompt_error` exist today (`fake_acp_agent.py:17-19,171-176`); `per_turn`, `prompts_log`, `helper` and `daemon_after_update` do **not**. | a test that sets an option the fake does not have fails on the missing option, the wrong red. Options first; no test yet |
| **K2** skeleton, deliberately carrying the bugs | `driver.open_session`/`send_turn`/`Session` with `send_turn` **re-handshaking** per turn and `Session.close` not idempotent; `run_turn` as a wrapper; `archive.snapshot_folder` (a path function), `archive.snapshot_cell` as a plain `shutil.copytree(cell_dir, folder)` (follows links, copies `home/`, no temp, no verify), `archive.append_missing_rows` that appends **all** rows; `engine._attempt` loop that sends turn n+1 straight after turn n, **gated on `COMPLETED_STOP_REASONS`**, writes no `turn_ended` and no snapshot, with `_after_append` (resets on every `prompt_sent`) and the last-response usage read **unchanged**; `plan` reading `turns` from the task dict. All existing tests stay green. | every behaviour the tests assert is absent or wrong in K2, so each fails on an assertion. The two engine bugs (the clock reset at `engine.py:280-283`, the last-response usage at `:663`) are **real on today's code**; K2 keeps them so T-ENG-2 and T-ENG-4 fail on the bug itself, not on "turn 2 never sent" |
| **K3** tests | the whole table below, red on K2. The commit message pastes the red assertion line of T-ENG-2 (a cell that completes), T-ENG-4 (a sum of 7), T-ENG-6 (`prompt_sent{2}` present) and T-DRV-1 (two `session/new`) | the red output is the evidence |
| **K4..** fixes, one per commit | (1) `_after_append` sets the clock only at turn 1; (2) usage summed over turns; (3) the `end_turn` gate; (4) `Session` single handshake and idempotent close; (5) `turn_ended`, `snapshot_cell` through `publish_dir`, `append_missing_rows`, retry and sweep; (6) `views`, `lifecycle`, `plan`, `status`, `errors` | each commit turns a named group green |

### The tests

| id | test (file) | (a) assertion that fails on K2, and why | (b) red fixture | (c) real wiring | (d) mutant |
| --- | --- | --- | --- | --- | --- |
| **T-ENG-1** | two turns on one session: ordered ledger; snapshot content differs from final; `prompts_log` shows one `session/new`, `[p1, p2]`, and one `eof` after `p2` (this absorbs the old T-ENG-3, RV-SIM 10) (`tests/test_engine.py`) | `kinds == [..., prompt_sent, turn_ended, turn_snapshot_archived, prompt_sent, turn_ended, ...]` fails: K2 writes neither `turn_ended` nor a snapshot event; `snapshot a.txt == "1"` fails: no snapshot folder; the `session/new` count is 2 (K2 re-handshakes) | n/a (behavioural) | whole path; `lifecycle.replay(events)` runs on the engine's real output | **M-ORDER** snapshot after the send (the snapshot then holds `a.txt == 2`); **M-ONCE** `session_opened` per turn (two rows); **M-CLOSE** `_end_process` after turn 1 (the log shows `eof` before `p2`) |
| **T-ENG-2** | the budget does not restart at turn 2 (`test_engine.py`; engine `clock` injected) | `outcome.code == "timed_out"` fails: with the budget 10 s, turn 1 taking 6 s and turn 2 taking 6 s, K2's `_after_append` resets the clock at `prompt_sent{2}`, so the cell **completes** (the real bug, `engine.py:280-283`); the test also asserts `prompt_sent{2}` is present, so "turns ignored" cannot satisfy it | budget 10 s; `per_turn` sleeps 6 s and 6 s | real driver, fake agent | **M-CLOCK** drop the `turn == 1` condition: cell completes, test red |
| **T-ENG-4** | spend and `turn_usage` are the sum over turns, `acp_turn` and `native_record`; **`views.verify` on the run has no `HB-VAL-005`** (RV-TA 5) (`test_engine.py`) | `sum(turn_usage) == 12` fails: K2 reads the last response, **7**; `no HB-VAL-005` fails: the ACP side (7) disagrees with the native record (12), so `views._token_cross_check` (`views.py:350`) warns | `per_turn` usage 5 and 7; the fake's native record reports 12 | real | **M-LAST** `result.usage` only (sum 7); **M-XCHECK** the cross-check reads the last turn (warns) |
| **T-ENG-5** | a suspend gap during turn 2 yields `host_suspended` (R3) | `outcome.code == "host_suspended"` holds on K2, but the same test asserts `turn_snapshot_archived{1}` is present before the gap (K2 has none) and fails there | injected `SleepDetector.slept` true after `prompt_sent{2}` | real engine loop | **M-RESET** re-create the detector between turns |
| **T-ENG-6** | `max_tokens` (a "completed" reason) on turn 1: `turn_ended{1}` is written with `stop_reason == "max_tokens"` and `next == "stop"`; no `prompt_sent{2}`; no snapshot (RV-PAT F2) | `prompt_sent{2}` absent fails: K2 gates on `COMPLETED_STOP_REASONS`, which includes `max_tokens`, and sends turn 2; `turn_ended{1}` present fails too | `per_turn` stop reasons `max_tokens`, then `end_turn` | real | **M-STOP** gate on `COMPLETED_STOP_REASONS` (turn 2 is sent) |
| **T-ENG-7** | a budget kill during the snapshot copy: no `turn-1` at its final name, no `*.tmp-*` left, no `turn_snapshot_archived`, no `prompt_sent{2}`; outcome `timed_out`; the kill ends a retry wait at once (RV-SRE 5, RV-DS 6) | `prompt_sent{2}` absent fails: K2 has no snapshot step and sends turn 2 | a per-file delay hook in `fill` (test-only) so the kill lands mid-copy; a `fill` that fails once so the kill lands in the 1 s backoff | real kill path | **M-NOCHECK** drop the cancel check before turn 2; **M-SLEEP** `time.sleep` in the backoff (the test bounds the end at 0.5 s) |
| **T-ENG-8** | EOF on turn 2's send ends the attempt with `adapter_crash`; snapshot 1 kept; `turn_ended{2}` absent | `turn_snapshot_archived{1}` present fails: K2 has none | the fake exits after prompt 1 | real | **M-SWALLOW** treat `send_turn` None as success |
| **T-ENG-9** | an auth error on turn 2 is `blocked_auth`, never NOT_RECORDED | `turn_snapshot_archived{1}` present fails: K2 has none | `per_turn` `prompt_error` only on the second prompt | real | **M-CAUSE** map any turn-2 error to `adapter_crash` |
| **T-ENG-10** | a kill that lands as turn 1 returns: `turn_ended{1}` is written with `next == "cancel"` and its usage; no `prompt_sent{2}` (RV-DS 4, RV-SRE 1) | `turn_ended{1}` present fails: K2 writes none | `per_turn` turn 1 reply delayed past the injected-clock budget | real | **M-CANCELFIRST** the `cancel` test before the record (the old `break`) |
| **T-ENG-11** | `cell.outcome` for a two-turn cell: `turn_ms` is the last turn's; agent time = sum of `turn_ended.turn_seconds` | `sum(turn_seconds)` fails: no `turn_ended` rows on K2 | `per_turn` sleeps 1 s and 2 s | real | **M-SUM** read only the last row |
| **T-DRV-1** | `open_session` then `send_turn` x2 on one channel: one `session/new`, two `session/prompt`; `run_turn` unchanged for one turn; the failure cases (`prompt_error`, EOF) keep their `stop_reason`/cause (the `assume:` in section 4.1) (`tests/test_driver.py`) | `session/new` count is 1 fails: K2's `send_turn` re-handshakes (2) | the fake counts `session/new` | real subprocess | **M-NEWSESSION** `send_turn` re-handshakes |
| **T-DRV-2** | `Session.close()` is idempotent: stdin closed once; `send_turn` after `close()` returns `None` with the cause set (RV-PAT F1) | `close()` twice must not raise: K2's second close raises `ValueError` on the closed handle | close twice, then send | real | **M-CLOSE2** close without a guard |
| **T-SNAP-1** | kill during the copy leaves no final name; a rerun completes; `sweep_temps(archive/<cid>, run_lock)` finds and removes the leftover temp; after the retry's failed attempts no `*.tmp-*` remains (RV-DS 2) (`tests/test_archive.py`) | `not (archive/<cid>/"turn-1").exists()` fails: K2's `copytree` writes the final name directly | a child process killed (`os._exit`) after 2 files; a `fill` that raises `PermissionError` | real filesystem, real child | **M-INPLACE** copy straight to the final name |
| **T-SNAP-2** | a planted `turn-1` (a stray file, no rows) is refused: `FileExistsError` then the verify finds the mismatch and raises HB-LED-008; nothing is changed or merged | `raises` fails: K2's `copytree` raises `FileExistsError` unhandled instead of HB-LED-008, and a re-run merges (`dirs_exist_ok`) in the variant the test also runs | folder pre-created with a stray file | real | **M-MERGE** drop the verify |
| **T-SNAP-3** | crash after k of n row appends: a second `_snapshot_turn` on the same cell dir finds the folder, appends only the missing rows and the event; a present row that differs raises **HB-LED-008** (a final archive's helper call raises HB-LED-005); the helper is `archive.append_missing_rows` (the one, W0 rev 6.2) (`tests/test_engine.py`, `tests/test_archive.py`) | `HB-LED-003 duplicate archive_files key` on the second call: K2's helper appends all rows | `record` raising after k rows on the first call | real ledger, real `views.verify` over the result | **M-DUP** append all rows; **M-CODE** raise HB-LED-005 for a snapshot |
| **T-SNAP-4** | only `ws/` is copied; no `home/`, no credential file | `home` absent fails: K2 copies the whole cell dir | home holds `.credentials.json`; ws holds a file named like a credential | real | **M-HOME** include every top-level folder |
| **T-SNAP-5** | the quiescence filter (SR-J1 condition): a helper spawned **before the first update** (`helper`) is in the baseline and the snapshot count equals it; a process spawned **after** the first update (`daemon_after_update`) gives `job_active_processes > job_active_baseline` (`test_engine.py`) | `turn_ended{1}.get("job_active_baseline") is not None` fails: K2 records none | the two fake options | real job object | **M-ZERO** record a constant 0; **M-EARLY** read the baseline at session open (the lazy helper is then counted as a leak) |
| **T-SNAP-6** | an exclusive lock on one file: three retries, then HB-CELL-117; no turn 2; the fake counts three fill attempts (the count is the test's, not the event's) | `outcome.code == "HB-CELL-117"` fails: K2 has no snapshot step, the cell completes | a child holds `msvcrt.locking` (S-J3 recipe) | real lock | **M-RETRYALL** retry forever |
| **T-SNAP-7** | a link in `ws/` is a row, not a copy | the row `kind == "link"` fails: K2's `copytree` follows the link | a junction/symlink to a sentinel outside | real | **M-FOLLOW** the existing mutation row "follow links" |
| **T-VER-1** | `views.verify` accepts a run with snapshot rows that reuse a final row's path | **red today**: `views.load` raises `HB-LED-003 duplicate archive_files key` (KEYS lacks `snapshot`), so `findings == []` fails (`tests/test_verify.py`, built on `archived_runs.make_run`) | the fixture itself: same `(cell, attempt, path)` in a final and a snapshot row | real `views.verify` | **M-KEY** remove `snapshot` from KEYS (duplicate); **M-FILTER** drop the final-rows filter (`HB-LED-005` on the final hash): they fail differently |
| **T-VER-2** | HB-LED-008 for each of: tampered snapshot file; `snapshot_hash` wrong; `files`/`bytes` wrong; event with no rows | **red today**: `verify` does not look at snapshots, so the `findings` contains `HB-LED-008` assertion fails | four tampered fixtures, one per branch | real | one mutant per branch (skip file check, skip hash, skip counts, skip empty-rows) |
| **T-VER-4** | the final `archive_hash` is unchanged by adding snapshot rows | **red today** with T-VER-1's fixture (it errors earlier) | same fixture | real | **M-FILTER** |
| **T-VER-5** | **the writer omits `snapshot` on final rows** (RV-TA 7): the rows `engine._archive` appends for a one-turn and a two-turn cell have no `snapshot` key; `archive_hash` of a fixed row list equals a **committed literal** | green today (the writer omits it) and stays green: a regression pin, with the mutant as its red-first proof (RV-SIM: no new golden file, the literal sits in the test) | the fixed row list | real `engine._archive` | **M-FINALKEY** the writer adds `"snapshot": "final"` (the ledger bytes and head hashes of new final rows change) |
| **T-VER-6** | rows with no `turn_snapshot_archived` yet (a live reader) give **no finding** (RV-DS 7) | **red today**: the snapshot-keyed rows hit `HB-LED-003` in `views.load` | rows only, no event | real | **M-ROWS** iterate rows instead of events |
| **T-VER-7** | one reader predicate (RV-PAT F5): a final row with `"snapshot": "final"` has the same `archive_hash` as the bare row, and a bare and a `"final"` row on one path are a duplicate (`HB-LED-003`) | green today for the hash; the duplicate half is red-first by the mutant (today's KEYS has no `snapshot`, so both collide already) | the two row spellings | real `views.verify` | **M-RAWKEY** key on `row.get("snapshot")` instead of `archive.snapshot_of` (the two spellings stop colliding) |
| *(named, no new test)* | legacy ledgers verify unchanged: `test_verify.py::test_a_golden_ledger_keeps_its_hashes_and_row_counts` (RV-SIM 10: this was T-VER-3) | green today and stays green | the committed golden ledgers | real | **M-LEGACY** treat an absent `snapshot` as non-final |
| **T-LIF-1** | `replay` accepts a valid two-turn stream and a single-turn stream with `turn_ended{1}` | **red today**: `cell.turn_ended` is "unmapped" and a second `cell.prompt_sent` trips `AT_MOST_ONCE`, so `replay(good)` raises | the valid streams | the same stream the real engine emits in T-ENG-1 | n/a |
| **T-LIF-2** | `replay` rejects each of four streams, naming its rule: second `prompt_sent{2}` (`PromptOncePerTurn`); `prompt_sent{2}` before `snapshot{1}` (`SnapshotBeforeNextTurn`); `snapshot{1}` before `turn_ended{1}` (`SnapshotAfterTurnEnd`); `turn_ended{2}` with no `prompt_sent{2}` | **red today**: the first stream raises the old `AT_MOST_ONCE` text and the others `unmapped transition`; none names the new rule, so `rule in str(error)` fails for all four | the four streams | real `lifecycle.replay` | one TABLE-row mutant per rule; the `snapshot{1}`-before-`turn_ended{1}` and `prompt_sent{2}`-before-`snapshot{1}` pair separates `SnapshotAfterTurnEnd` from `SnapshotBeforeNextTurn` |
| **T-LIF-3** | the code mirror of `CrashedTurnPredicate` (RV-DS 3): an `HB-CELL-119` outcome with a crashed turn, and an `HB-CELL-118` outcome on a between-turns cell with its snapshot recorded, are each rejected naming the rule; the two valid streams (and window 4, `prompt_sent{2}` unsent, as 118) are accepted | **red today**: `cell.outcome` rows with these codes have no rule, so the two invalid streams are **accepted** and `pytest.raises` fails | four hand-built streams, one per window (section 4.6) | real `lifecycle.replay`; X-K1 runs the same windows against the real resume (E3) | **M-CODE** swap 118 and 119 in the rule |
| **T-PLAN-1** | `build_plan` records `turns: [{n, prompt, sha256}]`, LF-normalised; `plan.load_confirmed` refuses an entry whose text does not hash (HB-LED-002) | **red today**: the plan task has no `turns` key (`plan.py:153-154` handles `prompt.md` only), and `load_confirmed` does not check | a task dir with `turns/2.md` in CRLF; a plan JSON with the text edited | real `build_plan`, real `load_confirmed` | **M-CRLF** hash the raw bytes; **M-NOCHECK** drop the hash check |
| **T-PLAN-2** | more than one `turns` entry is refused | `raises` fails: K2 accepts any number | a task with two turn files | real | **M-BOUND** remove the bound |
| **T-STATUS-1** | `bench status` elapsed and the over-budget flag read the **first** `cell.prompt_sent` (RV-SRE 2): a two-turn fixture with turn 2 sent after 70 % of the budget shows elapsed from turn 1, and equals the engine budget clock at the same instant through `lifecycle.is_cell_start` (W0 rev 6.5b) | **red today**: `status.py:128` keeps the last row, so elapsed restarts at turn 2 and the assertion `elapsed >= 0.7 * budget` fails | a ledger with `prompt_sent{1}` and `prompt_sent{2}` | real `status.collect` and the engine clock | **M-LASTWINS** the dict keeps the last row |
| **T-WIRE-1** | the real `bench plan` then `bench run` over a two-turn task writes the snapshot folder and both prompts | `turn-1/` exists fails on K2 (no snapshot step) | a two-turn task, the fake agent | real `cli.py` | remove the `turns` line from `engine._attempt`'s prompt list: the cell sends one prompt and the test fails |
| **T-SWEEP-1** | the archive-reader list in section 7 equals the tree's: the set of 8 files, the annotation and the two `git archive` files named in an allowlist (RV-TA 8) (`tests/test_archive_readers.py`) | a synthetic source with `archive/<cid>` and `glob("*")` must be **flagged**: the scan, run on the red fixture first, fails if the rule is deleted; against the real tree it is a guard (green today by construction) | the synthetic source | scans the real `src/` | **M-ADD** add a reader file: the test names it |
| **TLC** | `python tools/check_models.py`: real design passes, each variant rejected by its own target, witnesses violated | the seeded variants are the red fixtures (section 6.1): the script before this change does not know the 7 new variants or the 4 retargeted/renamed rows (the reverse MOD-A check and 3 tests fail on the `.tla` alone, section 6.1) | the seeded variants | TLC is the real checker | removing a guard from the model: the variant row fails to be rejected, so the script fails |

**Dropped (RV-SIM 10).** T-MOD-1 (`TURN_VARIANTS` subset pin): the structure it pinned no longer exists, and the seven existing `test_check_models.py` tests plus the script's own failure on a misspelt label cover the rest. T-VER-3 became a named existing test. T-ENG-3 folded into T-ENG-1.

**Conformance.** `tests/test_lifecycle_conformance.py` (existing) checks the table against the model; T-LIF-1 to T-LIF-3 extend its GOOD stream and its seeded-ledger set.

**Not tested, by decision (tests earn their place).** The model's own row-by-row append is covered at file level (T-SNAP-3), not by TLC. The temp sweep is T-SNAP-1. A second turn on macOS is not run (spike E4 residual, ADR-0015). **The US-44-bounds TLC run is one-time evidence for this model revision (RV-SIM 3):** it is not in any continuous ring; it is re-run, with `--deep`, only on a model change that touches the archive protocol.

## 12. Spikes

| id | question | method | result |
| --- | --- | --- | --- |
| S-J1 | Does TLC finish the extended model at useful bounds, and does it reject every variant? | the real `check_models.py` flow (section 6.1), re-run in revision 2 | yes; sizes and times in section 6.1 |
| S-J2 | What does a snapshot copy cost on real workspaces? | `archive.archive_cell` (the copy loop `snapshot_cell` shares) on the committed task workspaces, each made a git repository, 5 runs each, this Windows host | D1 (largest: 560 files, 7,072,817 bytes) 1,205 to 1,436 ms; B2 (30 files, 217,445 bytes) 52 to 110 ms; A4 (42 files, 37,757 bytes) 70 to 136 ms. **Verified** on this host for `archive_cell` only. **It is a floor, not the cost of a snapshot (RV-SRE 3):** `publish_dir` adds a per-file fsync through the write handle and a `verify` re-read of every file, and N cells snapshot together. Not a macOS figure |
| S-J3 | What does a lingering writer do to the copy? | a child process holds one file three ways, then `archive_cell` copies | shared handle (Python `open("a")`): copies (the content is whatever was flushed: a non-quiescent snapshot); `msvcrt.locking` byte-range lock: `PermissionError`; a handle opened with no sharing: `PermissionError`. `winerror` is `None` on these `PermissionError`s, so the retry catches `PermissionError`, not a winerror. **Verified.** Today's `archive_cell` copies straight into the final folder, so this failure leaves a partial `attempt-1` there: the D1 defect that `publish_dir` removes |
| S-J4 | Is the first `session/update` of turn 1 after the adapter's lazy helper spawns, on each real adapter? | count `job.active` right after `session/new`, at the first update, and at the end of a no-tool turn 1, on each of the three adapters | **open, not run** (needs the adapters on the operator's host). Section 4.4 carries it as an `assume:` with its confirmation and its failure effect |
| S-J5 | What does a snapshot cost through the real `publish_dir`, cold and warm, at parallelism 3? | X-B1's `publish_dir` (or a 20-line stand-in with fsync and verify) on D1 | **open**: `atomic.py` does not exist until E1. Until it is run, no document may quote 1.3 s as the budget cost; the ceiling is 10 s per snapshot (F7) |

Script: `w1j_spike.py` was run from the session scratchpad and is not committed (it writes only temp folders). Its recipe is the table above.

## 13. Open decisions, seam requests and proposed amendments

**Decisions made here (the author's, for the reviewers to attack):** D-J1 folder `turn-<n>`; D-J2 final rows omit `snapshot`, one reader predicate `snapshot_of`; D-J3 one hash function; D-J4 `run_turn` stays as a wrapper; D-J5 `TurnResult` holds `turns` and the last-turn fields are read-only properties over it; D-J6 usage is summed; D-J7 the copy counts against the one budget; D-J8 only `end_turn` continues; D-J9 HB-LED-008 merged meaning, HB-CELL-117 confirmed; D-J10 the model has `NumTurns` 1 or 2 and no sweep action; **D-J11 (rev 2)** `turn_ended` is written for every turn that returned a response, before the continue decision; **D-J12 (rev 2)** the baseline is read once, at turn 1's first update, and rides on `turn_ended{1}`; **D-J13 (rev 2)** `Session.close()` is the single owner of stdin; **D-J14 (rev 2)** `CrashedTurnPredicate` is stated independently of `ClassOf`.

**Seam requests.**

| id | to | ask | status |
| --- | --- | --- | --- |
| `req-01M41F2PAKH97KH6BDGXCTA1KK` (SR-J2) | coord-opus-e1e4 | `tools/check_models.py`, `tests/test_check_models.py`, `models/README.md`, `docs/design/run-lifecycle-model.md` | **ruled, W0 rev 6.3**: `WIDER` data first, logic lines listed (section 6: L1, L2), one commit with the `.tla` and the turns `.cfg`, proved by the test file and `--quick` green |
| SR-J1 | coord-opus-e1e4 | `job_active_baseline` | **granted, moved by W0 rev 6.5c** to `turn_ended{turn 1}`, read at the first update (section 4.4) |
| SR-J3 | coord-opus-e1e4 | `tasks.<id>.turns` entries `{n, prompt, sha256}` | **granted, W0 rev 6.2** |
| SR-J4 | coord-opus-e1e4 | one `append_missing_rows` | **granted, W0 rev 6.2**: owner X-J1, X-K1 calls it; code by folder kind (rev 6.3) |
| SR-J5 `req-01M41P7K51N6VC9RCK3DGP2EB7` | coord-opus-e1e4 | `turn_ended.next` | **granted, W0 rev 6.5a** |
| SR-J6 `req-01M41P7KF85ZXZEQ9BBQY209CF` | coord-opus-e1e4 | `status.py` joins X-J1's E2 surface, first `prompt_sent` | **granted, W0 rev 6.5b**, with the shared cell-start definition and an equality test |
| SR-J7 `req-01M41PFB77Y4H857FWYSEHGPBY` | coord-opus-e1e4 | baseline moves to `turn_ended{1}`; the snapshot row gains `job_active_after` and `copy_retries` | **granted, W0 rev 6.5c** |

**Proposed amendments to ADR-0015 (the Coordinator or Owner decides; this design does not edit the ADR).**
1. Section 5a names the temporary sibling `<name>.tmp-<pid>`; W0 section 4 names it `<name>.tmp-<pid>-<uuid4 hex>`, creates it exclusively and sweeps it by folder (`sweep_temps(folder, lock)`). The W0 text wins; the ADR line should say so.
2. Section 5a "On resume ... a final folder with no archived event is re-verified": extend to "and its rows, if partial, are completed" (section 3).
3. Section 2 (d) should state the ordering the model checks: the snapshot **event** (not only the rename) precedes `prompt_sent{n+1}`.
4. Section 6's "A turn-2 intent is never written before the turn-1 snapshot event" is `SnapshotBeforeNextTurn`; record the invariant names beside it.
5. Section 7's `CrashedTurnPredicate` ("iff `promptSent /\ ~turnEnded /\ ~terminal`") is stated in the model as three implications (section 6); the ADR line should carry them, since "iff" over a cell that is merely waiting between turns is the case the third implication covers.

**Open decision:** the code for "more than one `turns` entry" (T-PLAN-2): reuse an `HB-RDY` row from W1-E's readiness set. No new code is invented here.

**Next steps (captured, not built here).** (1) X-K1 (E3): the resume outcome row carries `turn` and `phase` (`mid-turn` or `between-turns`) so the CLI count by code can split (RV-SRE 8). (2) W1-K: refine `BetweenSnapped` and the final `ELSE` of `ClassOf`, and the stop-reason clause of the 119 rule (section 4.6). (3) Spikes S-J4 and S-J5 (section 12). (4) A fifth `check_models.py` row for the one-cell two-crash run (2 s) if a ring owner wants it (section 6.1 declines it here).

## 14. Definition-of-done self-check (Stage 4)

- Single responsibility; boundaries named: yes (section 1).
- Data model first; aggregate and invariant; grain; additivity; history; derive-don't-store; writers and readers: yes (section 2). Append-only enforcement tests: T-VER-2, T-SNAP-2 (forbidden overwrite), T-SNAP-3, T-VER-5. No rebuild claim is made, so no rebuild test.
- Surface list: section 7 (14 rows, `status.py` added). Delivery phasing: E2, X-J1 after this model passes TLC.
- Patterns named and attacked: section 5. Ladder: section 5.
- Contracts established, unfamiliar ones spiked: ACP second prompt (spike E4, Verified on Windows); copy cost and lock behaviour (S-J2, S-J3); the baseline read point (S-J4) and the real `publish_dir` cost (S-J5) are **open**.
- Failure modes: section 8 (F1-F20). STRIDE-lite: section 9. Privacy: none (section 9). UI: none (no interface; the report is X-A3's). Rollups: `docs/security/threat-model.md` and `privacy-review.md` were not refreshed (section 9 states no new boundary class and no personal data); **unmet**, left to the gate (no lens asked for it).
- Telemetry: section 10. Tests by node id with the five checks and a commit order: section 11.
- Hard vetoes: the author clears none; the lenses re-confirm this revision.
- Unmet or provisional: the resume branches (provisional for W1-K); S-J4 and S-J5 open; the rollup refresh; macOS unverified.

## Review disposition

Every finding of the five gate reviews has a row. *Applied* = changed in this revision (where); *Answered* = the position is argued, no change; *Declined* = advice not taken, with the reason; *Handed off* = a next step for another owner.

| finding | disposition | where / reason |
| --- | --- | --- |
| RV-TA 1 (check_models exceeds its grant; not on the branch) | Applied | section 6 *The grant*: data rows plus the two listed logic lines L1, L2; script, test, `.tla` and cfg in one commit (SR-J2, W0 rev 6.3) |
| RV-TA 2 (`CrashedTurnPredicate` circular; one direction) | Applied | section 6: `CrashedLit`/`WaitingLit` in three implications; variant `crashed_turn_as_between`; 6.1 explains why an ordering variant cannot differ at two turns |
| RV-TA 3 (US-44 row carries no turn invariant; no two-crash run) | Applied | 6.1: one-cell and two-cell two-crash rows pass; US-44 re-run with `-fp 7`; its place as one-time evidence |
| RV-TA 4 (engine-bug tests red for the wrong reason) | Applied | section 11 commit order, K2 keeps the bugs; T-ENG-2 and T-ENG-4 fail on the bug |
| RV-TA 5 (cross-check untested) | Applied | T-ENG-4 asserts no `HB-VAL-005`; mutant M-XCHECK |
| RV-TA 6 (about 15 tests with no failing assertion; missing fake options) | Applied | every row has its assertion on K2; K1 adds `per_turn`, `prompts_log`, `helper`, `daemon_after_update` |
| RV-TA 7 (final-row omission pinned on the reader only) | Applied | T-VER-5 (writer pin, committed literal, M-FINALKEY) |
| RV-TA 8 (sweep count) | Applied | section 7: 14 lines, 11 files, 8 in the table, 1 annotation, 2 false positives; T-SWEEP-1 asserts the set |
| RV-TA 9 (ledger rule named like the model property) | Applied | renamed `SnapshotAfterTurnEnd`, with what it cannot see (4.6) |
| RV-TA 10 (`ledger.py` kind list Inferred) | Applied | section 7 row 10, Verified |
| RV-PAT F1 (no `close`; Optional plus out-parameter) | Applied | 4.1 `Session.close()`, one `None` check, the failure convention, T-DRV-2 |
| RV-PAT F2 (`turn_ended` after the break) | Applied | 4.2, D-J11, T-ENG-6, T-ENG-10 |
| RV-PAT F3 (two recovery helpers) | Applied | W0 rev 6.2/6.3: one `append_missing_rows`, X-J1; code by folder kind (section 3) |
| RV-PAT F4 (Memento) | Applied | section 5 *The snapshot is a checkpoint* |
| RV-PAT F5 (final-row predicate spelled per reader) | Applied | section 2 `archive.snapshot_of`; T-VER-7 |
| RV-PAT F6 (check_models shape) | Answered | the SR-J2 ruling took the `WIDER` data route, so no parallel `TURN_VARIANTS` set exists; `simplify:` trigger recorded in section 6 |
| RV-PAT F7 (`TurnResult` duplicates) | Applied | 4.1 read-only properties; the `assume:` with its check |
| RV-PAT F8 (`barrier_for(1)` writes two records) | Applied | 4.2 `record_session_opened` |
| RV-SIM 1 (reuse `WIDER`) | Applied | section 6: 8 `WIDER` rows |
| RV-SIM 2 (derive the turns cfg from `small`) | Declined | the brief and the ruling land the cfg; engine-only grading keeps the real two-turn run at 14.9M states, 74 s; the size of `small` plus bench grading at two turns is unmeasured (L1 states why) |
| RV-SIM 3 (US-44 one-time) | Applied | 6.1 and section 11 *Not tested, by decision* |
| RV-SIM 4 (drop `snapshot_in_place`) | Declined | advice; kept, reason and the one-row removal in 6.1 |
| RV-SIM 5 (variants map; keep) | Answered | no change |
| RV-SIM 6 (resume-owned branches provisional) | Applied | `.tla` header, section 6, 4.6 |
| RV-SIM 7 (`snapshot` field earns its place) | Answered | no change |
| RV-SIM 8 (snapshot per turn earns its place) | Answered | no change |
| RV-SIM 9 (retry vs W0's WIN-A loop) | Answered | 4.4 step 3: a different call (a locked source file in `fill`, not the rename); `copy_retries` is `publish_dir`'s own count |
| RV-SIM 10 (three duplicate tests) | Applied | T-MOD-1 dropped, T-VER-3 named, T-ENG-3 folded into T-ENG-1 |
| RV-SRE 1 (break before `turn_ended`; no reason for "not sent") | Applied | 4.2; `next` (W0 rev 6.5a); T-ENG-6, T-ENG-10 |
| RV-SRE 2 (`status.py` clock) | Applied | 4.3; surface row 14; shared `lifecycle.is_cell_start`; T-STATUS-1 (W0 rev 6.5b) |
| RV-SRE 3 (S-J2 is a floor) | Applied | S-J2 row, F7 (10 s ceiling), S-J5 open |
| RV-SRE 4 (baseline too early, counted once) | Applied | 4.4: read point, two counts, `assume:`, S-J4 open (W0 rev 6.5c) |
| RV-SRE 5 (retry sleeps through a stop) | Applied | 4.4 step 3 `a.cancel.wait`, T-ENG-7 M-SLEEP |
| RV-SRE 6 (`turn_ms` last turn only) | Applied | 4.5 *Units*, T-ENG-11 |
| RV-SRE 7 (missing-turn usage) | Applied | 4.5, F18 |
| RV-SRE 8 (resume status text) | Handed off | section 13 next step (1), X-K1 |
| RV-SRE 9 (measure the F17 gap) | Applied | F17, section 10 |
| RV-DS 1 (no E2 owner for partial rows; two codes) | Applied | section 3: X-J1 owns it in E2, reached by the same-attempt retry, code by folder kind, E2 resume stated; T-SNAP-3 |
| RV-DS 2 (stale sweep; retry temps leak) | Applied | section 2 folder-form `sweep_temps`; 4.4 step 3 sweeps between tries; T-SNAP-1, F1 |
| RV-DS 3 (two invariants with no code mirror) | Applied | 4.6 rows and the four windows; T-LIF-3; the mirror of `ArchiveExistsMeansComplete` is structural (T-SNAP-1) |
| RV-DS 4 (`turn_ended` skipped on cancel) | Applied | 4.2; `~killRequested` dropped from `TurnEnd`, TLC re-run; T-ENG-10 |
| RV-DS 5 (`prompt_sent{2}` may be written and not sent) | Applied | 4.2 *The cancel check* |
| RV-DS 6 (retry sleeps through a stop) | Applied | with RV-SRE 5 |
| RV-DS 7 (rows without an event) | Applied | section 3; T-VER-6; F20 |
| RV-DS 8 (`turn_ended` now in every cell) | Applied | section 3; T-LIF-1 |
| RV-DS 9 (deep run skipped) | Applied / Declined in part | the run is recorded (6.1); not added to the script as a run row |

## Gate record

The reviewers' gate lines, copied verbatim. Each lens passed with conditions; this revision applies them (Review disposition). The author clears no veto; the lenses re-confirm.

| lens | verdict | line |
| --- | --- | --- |
| RV-PAT (Patterns Expert) | PASS WITH CONDITIONS | `GATE W1-J · Patterns Expert · PASS WITH CONDITIONS · 8 findings (rv-pat-w1j-e1e4, 2026-10-03)` |
| RV-SIM (Simplifier, soft veto) | PASS WITH CONDITIONS | `GATE W1-J · Simplifier · PASS WITH CONDITIONS · 10 findings (rv-sim-w1j-e1e4, 2026-10-03)` |
| RV-TA (Test Architect, hard veto) | PASS WITH CONDITIONS | `GATE W1-J · Test Architect · PASS WITH CONDITIONS · 10 findings (rv-ta-w1j-e1e4, 2026-10-03)` |
| RV-DS (Distributed Systems, hard veto) | PASS WITH CONDITIONS | `GATE W1-J · Distributed Systems · PASS WITH CONDITIONS · 9 findings (rv-ds-j-e1e4, 2026-10-03)` |
| RV-SRE (SRE) | PASS WITH CONDITIONS | `GATE W1-J · SRE · PASS WITH CONDITIONS · 9 findings (rv-sre-j-e1e4, 2026-10-03)` |

## Appendix A: the `tools/check_models.py` change (SR-J2, as landed)

The change is in the commit with the `.tla`. The data rows are listed in section 6; the two logic lines are:

```diff
-    runs = [("liveness", liveness), ("grading", grading), ("safety-small", small)]
+    turns = (MODELS / f"{MODEL}.turns.cfg").read_text(encoding="utf-8")   # L1
+    runs = [("liveness", liveness), ("grading", grading), ("safety-small", small), ("safety-turns", turns)]
...
-        code, out, secs = tlc(only_invariant(small, name), label)
+        code, out, secs = tlc(only_invariant(substitute(small, WIDER.get(label, {})), name), label)   # L2
```
