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

**Track:** W1-J, session `w1j-multiturn-e1e4`, model `claude-sonnet-5-5`, tier T2. **Implemented by:** X-J1 (E2), after this model passes TLC (plan serial-spine item 4). **Grounded at:** worktree base `124395fb` (W0 revision 2).
**Rulings and seams carried:** DR-E4 (second turn in the same attempt); W0 section 4 (`publish_dir`, rev 2), section 5 (`tasks.<id>.turns`), section 11 (HB-LED-008, HB-CELL-117), section 12 (ledger rows), section 13 (hub owners), section 14 (this doc names the snapshot folder).

## Status table

| item | status |
| --- | --- |
| Data model, snapshot path, record contracts | done (sections 2, 3) |
| Driver and engine design | done (section 4) |
| TLA+ model, TLC run, seeded variants | done; output in section 6 |
| Surface list, failure modes, STRIDE-lite, telemetry | done (sections 7 to 10) |
| Test plan by node id, with the four testability checks | done (section 11) |
| Spikes | S-J1 (TLC feasibility), S-J2 (copy cost), S-J3 (lingering writer) run (section 12) |
| Gate record | **pending**: RV-PAT, RV-SIM, RV-TA (hard veto), RV-DS (hard veto), RV-SRE |
| Seam requests and open decisions | section 13; two seams provisional |

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

**History rule per attribute.** Every new fact is append-only and never rewritten, so each attribute is Type-2 by construction. "Absent reads the default" is the whole migration: an old `cell.prompt_sent` has no `turn` and reads 1; an old `archive_files` row has no `snapshot` and reads `final`. This is expand-only. **No backfill exists**, so nothing can guess (DM16). **Final rows never carry the `snapshot` field** (decision D-J2): the writer omits it, only snapshot rows write `"snapshot": "turn-<n>"`. The bytes of every existing final row, and therefore every `archive_hash`, are unchanged. W0 section 12 allows both spellings; omitting is the choice that keeps legacy and new final rows identical.

**Derive, don't store.** `snapshot_hash` is `archive.archive_hash(rows)` over the snapshot's own rows (decision D-J3): the same function and the same `ROW_FIELDS` as the final archive, so there is one hash definition (DM7). The event's `files` and `bytes` are a rebuildable cache of the rows; `bench verify` checks the equality (HB-LED-008). `views.verify` recomputes everything; nothing trusts the event alone.

**Writers and readers of every persisted field.**

| field | writer | compute reader |
| --- | --- | --- |
| `cell.prompt_sent.turn` | `engine._attempt` barrier (worker thread, through the ack barrier) | `lifecycle.replay`; `engine._after_append` (budget clock); X-K1 resume predicate |
| `cell.turn_ended.{turn, stop_reason, turn_seconds, usage}` | `engine._attempt` | `lifecycle.replay`; X-J2 (turn-2 NOT_RECORDED reason, counts events against the plan's turns); `views` (usage) |
| `cell.turn_snapshot_archived.{turn, snapshot_hash, files, bytes, duration_ms, job_active_processes}` | `engine._snapshot_turn` | `views.verify` (HB-LED-008); X-J2 (`graded_snapshots`); report (filter on quiescence) |
| `archive_files.snapshot` | `engine._snapshot_turn` (rows of a snapshot only) | `views.verify`, `views._refuse_duplicates` (key), `archive.snapshot_folder` callers |
| `tasks.<id>.turns[]` | `plan.build_plan` (X-J1, `turns` only) | `engine._attempt` (prompt text), `lifecycle`, X-J2 |

**Snapshot folder (W0 section 14 asks this doc to name it).** `<run_dir>/archive/<cell_id>/turn-<n>/`, holding only the cell's `ws/` tree, with row paths relative to the cell folder (`ws/a.txt`), the same convention as the final archive's `ws/a.txt`. One helper builds the path: `archive.snapshot_folder(run_dir, cell_id, turn)` (decision D-J1). Why this name:
- It is a sibling of `attempt-1/` inside `archive/<cell_id>/`, as ADR-0015 section 5 requires ("a sibling folder of the final archive").
- It does **not** start with `attempt-`. Section 8 lists the readers that glob that prefix; none of them can see `turn-<n>`.
- `publish_dir`'s temporary sibling is `turn-<n>.tmp-<pid>-<uuid>` (W0 section 4), also invisible to those globs, and `stale_temps(target)` finds it.
- The graded copy for `graded_snapshots: [turn-1]` is `<snapshot folder>/ws`, the same shape as the final tree's `attempt-1/ws` (section 8).
- Only `ws/` is copied, never `home/` (ADR-0015 "Alternatives": the home's native record keeps growing and only the tree is graded). Credential files are excluded by the same `exclude_names` as the final archive, though `ws/` holds none; the test pins it (T-SNAP-4).

## 3. The record contract

```text
cell.prompt_sent                {cell_id, turn}                                  turn absent reads 1
cell.turn_ended                 {cell_id, turn, stop_reason, turn_seconds, usage}   usage = {"usage":..., "meta":...} verbatim or null (R-24 shape)
cell.turn_snapshot_archived     {cell_id, turn, snapshot_hash, files, bytes, duration_ms, job_active_processes}
archive_files row (snapshot)    {run_id, cell_id, archive_attempt: 1, snapshot: "turn-<n>", path, kind, size, sha256, link_target}
archive_files row (final)       unchanged: no snapshot field
```

**Ledger order for one two-turn cell (the sequence the model checks):**
`launch_intent, workspace_built, process_started, session_opened, prompt_sent{1}, turn_ended{1}, [snapshot rows], turn_snapshot_archived{1}, prompt_sent{2}, turn_ended{2}, process_ended, outcome, [final rows], archived, workspace_deleted`.
Rows are appended before the event that commits them, as `engine._archive` does today (`engine.py:803-815`).

**The crash windows and their one recovery rule (W0 section 4, quoted):** "if `final` exists and its rows are absent, recompute the rows from the folder, compare them with the source (still in the archive root or the working copy), then append them. If `final` exists and its rows are present, verify only." The snapshot adds a third state the W0 text does not name: **some rows present** (a crash after k of n row appends). This design extends the rule: append only the rows whose key is missing, and refuse (HB-LED-008) a present row that differs from the recomputed one. Without this, the retry hits `HB-LED-003 duplicate archive_files key` (`views.py:162`). The final archive has the same exposure today; W1-B owns that half, and the helper `archive.append_missing_rows(present, recomputed)` should be shared (seam request, section 13).

**HB codes (W0 section 11 asks this design to confirm or drop its rows).**
- **HB-LED-008 confirmed**, with a merged meaning (RV-SIM 10): "a turn snapshot does not match its record": the `snapshot_hash` differs from the rows, the event's `files` or `bytes` differ from the rows, a row's file is missing or changed under the folder, or the event exists with no rows. The message names which.
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

class Session:                    # owns the _Channel; created by open_session
    channel: _Channel; result: TurnResult     # result is the attempt-level record

def open_session(cell, cwd, mode, handshake_timeout, model=None, result=None, mcp_servers=None, cancel=None) -> Session | None
    # the handshake of today's run_turn, unchanged; None means result.cause is set (same failure paths as today)
def send_turn(session, prompt, before_send, turn) -> TurnRecord | None
    # before_send(session_id) then one session/prompt; None means the turn did not end cleanly (result.cause set)
def run_turn(...)                 # unchanged signature: open_session, then send_turn(turn=1). Existing callers and tests keep working.
```

`TurnResult` stays the attempt-level record. Its `stop_reason`, `usage`, `turn_seconds` and `last_update_seconds` fields hold the **last sent turn** (so `engine._classify` and the outcome row read what they read today), and `turns: list[TurnRecord]` holds every turn. `last_update_seconds` and `_Channel.turn_start` are reset at the start of each `send_turn`. Session-level fields (`session_id`, `agent_version`, `permission_mode_effective`, `handshake_seconds`) are set once by `open_session`. `permission_requests` and `updates` stay cumulative.

### 4.2 Engine: `_attempt` becomes a turn loop

`_attempt` (`engine.py:684-747`) keeps its structure: spawn, `try:` the turns, `finally:` end the process and record `attempt.process_ended`. Inside the `try:` the single `driver.run_turn` call becomes:

```python
session = driver.open_session(cp, cwd=ws, mode=..., handshake_timeout=..., model=..., result=result, mcp_servers=..., cancel=a.cancel)
turns = [prompt] + [t["prompt"] for t in task.get("turns", [])]        # from the plan (D-J11)
for n, text in enumerate(turns, 1):
    if session is None: break
    rec = driver.send_turn(session, text, before_send=barrier_for(n), turn=n)
    if rec is None or rec.stop_reason != "end_turn" or a.cancel.is_set(): break
    self.record("events", {"kind": "cell.turn_ended", "cell_id": cid, "turn": n, "stop_reason": rec.stop_reason, ...})
    if n < len(turns):
        if not self._snapshot_turn(a, cell, cell_dir, n, launcher, cp): break      # records HB-CELL-117 cause on failure
```

- `barrier_for(1)` records `attempt.session_opened` and `cell.prompt_sent{turn: 1}`; `barrier_for(n>1)` records only `cell.prompt_sent{turn: n}` (`session_opened` stays once, ADR-0015 section 2a).
- The `finally:` is unchanged: `a.ended = True`, then `_end_process` (`:749`), which closes stdin (`:752`). Because the loop is inside the `try`, stdin is closed only after the last turn or an early exit. **Stdin is never closed between turns.**
- **Only `end_turn` continues.** `COMPLETED_STOP_REASONS` (`engine.py:60`, which includes `max_tokens`, `max_turn_requests`, `refusal`) still decides the outcome class; it must not decide whether turn 2 is sent. ADR-0015 section 2: "Any other stop reason ... ends the attempt". T-ENG-6 pins the difference (`max_tokens` on turn 1).
- **The cancel check.** A budget, stop or suspend kill sets `a.cancel` (`_kill`, `engine.py:541-548`). The loop checks it after the snapshot and before sending turn 2; `send_turn` also checks it after the barrier, as `run_turn` does today (`driver.py:295-297`). A snapshot already published stays. No turn-2 `prompt_sent` is written after a kill.
- **Turns not reached** need no new field: X-J2 derives "turn k not reached" by counting `cell.turn_ended` events against `len(plan.tasks.<id>.turns) + 1` (derive, don't store).

### 4.3 One budget for every turn (ADR-0015 section 3)

`_after_append` sets `a.prompt_mono = self.clock()` on **every** `cell.prompt_sent` (`engine.py:277-283`). With turn 2 that would restart the budget clock and give the cell two budgets. The fix is one condition: set it only when `row.get("turn", 1) == 1`. `_check_budgets` (`:556`) then measures from turn 1's prompt across the snapshot copy and turn 2. The snapshot's copy time counts against the budget (decision D-J7); it is measured (`duration_ms`) and small (section 12, S-J2). `a.ended` stays False until the last turn ends, so `_kill` (`:538`) still acts between turns. ADR-0013 section 2's "At the end of every turn the engine terminates the job" becomes "at the end of the attempt's last turn" (ADR-0015 section 3; already decided).

### 4.4 The snapshot step (`engine._snapshot_turn`, worker thread)

1. Count `job_active_processes = _job_query(cp.job.active, None)` (a number, or null = not recorded, never a guessed 0; the same `_job_query` the engine uses at `:758`).
2. `archive.snapshot_cell(cell_dir, run_dir/"archive"/cid, turn=n, exclude_names)` which is `atomic.publish_dir(snapshot_folder, fill, verify)` (W0 section 4, owner X-B1): `fill(tmp)` copies `ws/` (links recorded, never followed, as `archive_cell` does today), `verify(tmp)` compares the folder's file set and every row's size and sha256.
3. A `PermissionError` or `OSError` during the copy is retried up to 3 times (1 s, 2 s, 4 s) and then ends the attempt with `Cause.archive` (HB-CELL-117). The retry class is justified by S-J3: an exclusive lock or a no-share handle raises `PermissionError`; a shared handle copies.
4. Append the rows (only the missing ones, section 3), then `cell.turn_snapshot_archived`. The event is the commit. Only after it is durable does the loop reach `barrier_for(n+1)`.

**Non-quiescent snapshots (ADR-0015 section 4, accepted).** `job_active_processes` counts every process in the cell's Job Object, **including the adapter and its own children**, so the raw count alone cannot tell "the agent left a build server running" from "the adapter has two helper processes" [Verified in `_end_process`: it waits for `job.active` to reach 0 after stdin closes, so the adapter counts]. To make the field interpretable I propose one additive field on the existing `attempt.session_opened` event: `job_active_baseline`, the count measured right after `session/new`, before any prompt (seam request SR-J1, provisional). The report's filter is "snapshot count greater than baseline". If the seam is refused, the field is recorded exactly as W0 section 12 states and the report cannot filter; that residual is stated, not hidden.

### 4.5 Usage across turns

Today `usage = normalize.turn_usage({"_meta": (result.usage or {}).get("meta")})` (`engine.py:663`) reads the one response. For `acp_turn` profiles (claude-code) that would record **only the last turn's tokens** as the cell's spend. The fix: build `usage` as the concatenation of each turn record's entries (`[u for t in result.turns for u in normalize.turn_usage({"_meta": (t.usage or {}).get("meta")})]`); `_usage_per_model` (`:871`) already sums entries per model before the one `turn_usage` row per `(run, cell, attempt, model)`, so no key changes. (`_usage_per_model` is at `engine.py:871`.) `attempt.process_ended.acp_usage` (`:740`, R-24 "verbatim") keeps the last response; per-turn verbatim usage lives in `cell.turn_ended.usage`. `views._token_cross_check` (`views.py:354`) compares one ACP total with `model_calls`; with two turns the ACP side must be the sum, or HB-VAL-005 warns spuriously (X-J1 sums `turn_ended.usage`; T-ENG-4).

### 4.6 `lifecycle.py`: the table gains the turn rules

`lifecycle.TABLE` and `replay` (`lifecycle.py:67-190`) are the conformance mirror of the model. Today `AT_MOST_ONCE` fails on any repeated kind per cell (`replay`, `if kind in done`), and `cell.turn_ended` is "unmapped". The change (X-J1, hub file in E2):
- `replay` keys the per-cell history by `(kind, turn)` for the three turn-carrying kinds (`cell.prompt_sent`, `cell.turn_ended`, `cell.turn_snapshot_archived`); absent `turn` reads 1.
- New rules, each named for the model invariant it transcribes:

| TABLE entry | model action | rule name (the string the replay raises) |
| --- | --- | --- |
| `cell.prompt_sent#n` | QueuePromptSent, PersistPromptSent, SendPrompt | `PromptOncePerTurn` (second record of `(kind, turn)`) |
| `cell.prompt_sent#n`, n>1, after `cell.turn_snapshot_archived#(n-1)` | QueuePromptSent guard | `SnapshotBeforeNextTurn` |
| `cell.turn_ended#n` after `cell.prompt_sent#n` | TurnEnd | `turn_ended follows its prompt_sent` |
| `cell.turn_snapshot_archived#n` after `cell.turn_ended#n`, not after `cell.prompt_sent#(n+1)` | CopyBegin (idle adapter), SnapRecord | `NoSnapshotInFlight` (ledger form: a snapshot is committed only between its turn's end and the next prompt) |

`docs/design/run-lifecycle-model.md`'s mapping table gains the same rows (seam request SR-J2).

## 5. Patterns, and the Simplifier's challenge

| pattern | where | why it is the smallest correct idiom | the Simplifier's attack, and the answer |
| --- | --- | --- | --- |
| **Write-ahead intent with an ack barrier** (existing, ADR-0007) | `prompt_sent{turn}` through `barrier_for(n)` | reuse: turn 2 uses the same barrier as turn 1; no second mechanism | "Why not a lighter record for turn 2?" The prompt-once guarantee (P8) is the reason the barrier exists; a cheaper record loses it. Kept. |
| **Create-once / write-to-temp-then-rename** (`publish_dir`, W0 section 4) | snapshot and final archive | reuse of X-B1's helper; no second archive primitive (DM7) | "A snapshot is a copy; why not `shutil.copytree`?" A crash mid-copy leaves a folder that reads as complete; ADR-0015 section 5a is the defect class. Kept. |
| **Split a closed function into open / step / close** | `driver.run_turn` | the smallest change that lets one channel serve two prompts (spike E4 option b) | "Add a `turns` parameter to `run_turn` instead." Rejected: the barrier, the snapshot and the cancel check must interleave between prompts, and they live in the engine. `run_turn` stays as a two-line wrapper so existing callers and tests do not change. |
| **Key part with an absent-reads-default** | `snapshot`, `turn` | expand-only schema evolution; no backfill | "Two tables." Rejected in ADR-0015 (a separate `turn_snapshots` fact duplicates `archive_files` and its verify path). |
| **Event-sourced commitment** (rows, then one event that hashes them) | `cell.turn_snapshot_archived` | the shape `cell.archived` already has | none; it is reuse. |

Simplifier cuts accepted: no per-turn budgets, no snapshot of `home/`, no `turn` field on the plan cell, no third turn, no new fact, no sweep action in the model (section 6). Solution-Selection Ladder: every step reuses (rung 2) or is stdlib (rung 3); no new dependency.

## 6. The lifecycle model (`models/run_lifecycle.tla`, version 5)

**What changed, and why each addition is there.**
- `NumTurns` (constant, 1 or 2). With 1 the model is the version-4 lifecycle plus phased archive writes; with 2 it adds the turn rules. ADR-0015 bounds a task to two turns, so the model does too.
- Per-cell, per-turn: `promptSent[c][k]`, `prompts[c][k]`, `turnEnded[c][k]`, `snapEv[c][k]` (ledger); `queued[c]`, `pendingSend[c]` now hold the turn number (0 none).
- Archive writes are phased as the engine will do them (ADR-0015 section 5a): `CopyBegin` (fill a temporary sibling) then `CopyPublish` (verify and rename to the final name) then a record action (`Archive` for the final tree, `SnapRecord` for a snapshot). `tmp[c][a]` and `fin[c][a]` hold the two names' states for artifact `a` (0 the final archive, k the turn-k snapshot); `copying[c]` names the one copy in progress (volatile, lost at a crash). A crash leaves a rename done and its event unrecorded; the record action then completes on resume (the W0 recovery rule).
- New actions: `TurnEnd(c,k)`, `CopyBegin`, `CopyPublish`, `SnapFail(c,k)` (HB-CELL-117), `SnapRecord(c,k)`. `QueuePromptSent(c,k)` for k>1 requires `turnEnded[c][k-1]` and `snapEv[c][k-1]`.
- Resume classification: `ClassOf(c)` records `crashfail` for a crashed turn (`promptSent[c][k]` and no `turnEnded[c][k]`), `crashbetween` for a cell between turns (`turnEnded[c][k]`, no `promptSent[c][k+1]`), else `crashfail` (all turns ended, no outcome: ADR-0007's rule; W1-K may refine). A cell between turns first has its snapshot redone (`BetweenSnapped`), as ADR-0021 section 4 row 3 says.
- **Not modelled, on purpose:** the temporary-folder sweep. W0 names temps `<name>.tmp-<pid>-<uuid>`, so a stale temp can never collide with a later copy; a Crash clears `tmp` in the model because a leftover is inert. The sweep is bookkeeping, tested at file level (T-SNAP-1). Also not modelled: the budget clock (code-level, T-ENG-2), the process-count gauge, row-by-row appends (T-SNAP-3).

**The five invariants of ADR-0015 section 7** (all in `run_lifecycle.turns.cfg` at two turns; `run_lifecycle.safety.cfg` lists them too at `NumTurns = 1`, where `SnapshotBeforeNextTurn` is vacuous and `NoSnapshotInFlight`, `CrashedTurnPredicate` and `ArchiveExistsMeansComplete` constrain the final archive and the single-turn resume):

| invariant | definition (TLA+) | seeded variant TLC must reject | the variant's change |
| --- | --- | --- | --- |
| `PromptOncePerTurn` | `\A c, k : prompts[c][k] <= 1` | `relaunch_prompted`, `send_before_persist` (existing, retargeted from `AtMostOnePrompt`), `resend_turn_on_resume` (new) | reconciliation reopens a crashed turn k>1 and the cell is launched and prompted again |
| `SnapshotBeforeNextTurn` | `(promptSent[c][k] \/ prompts[c][k] >= 1) => snapEv[c][k-1]` | `prompt_before_snapshot` | `QueuePromptSent(c,k)` drops the `snapEv[c][k-1]` guard |
| `NoSnapshotInFlight` | `copying[c] # NoCopy => ~InFlight(c)` | `snapshot_in_flight` | `CopyBegin(c,k)` is allowed while turn k is still in flight |
| `CrashedTurnPredicate` | `outcome[c] \in {crashfail, crashbetween} => outcome[c] = ClassOf(c)` | `kill_between_turns` | reconciliation records `crashfail` for any prompted non-terminal cell (the old predicate) |
| `ArchiveExistsMeansComplete` | `\A c, a : fin[c][a] # "none" => fin[c][a] = "complete"` | `archive_in_place` (a=0), `snapshot_in_place` (a>0) | the copy fills the final name directly |

`SnapshotBeforeNextTurn` and `NoSnapshotInFlight` are adjacent rules about the same step: the first orders the **next prompt** after the snapshot event, the second forbids the **copy** while a turn runs. `prompt_before_snapshot` leaves copies alone and removes only the ordering guard; `snapshot_in_flight` removes only the idleness guard. Each is rejected by its own invariant checked alone (`only_invariant` in `check_models.py`), so neither can hide behind the other.

**Witnesses (each must be violated, so a pass is not vacuous):** `NotAllTurnsDelivered` (a cell completes both turns after the turn-1 snapshot) and `NotCrashBetween` (a resume classes a between-turns cell with its snapshot recorded).

**Configurations.**
- `run_lifecycle.turns.cfg` (new): 2 cells, parallelism 1, 1 crash, 1 pass, engine grading, `NumTurns = 2`, symmetry.
- `run_lifecycle.liveness.cfg`: 1 cell, `NumTurns = 2`. The fairness set gained `CopyBegin`, `CopyPublish`, `SnapRecord` for every artifact. The first liveness run found a real gap: without fairness on the redo copy a resumed between-turns cell could wait forever on its snapshot, and `PromptedCellsEnd` failed; the fairness is the engine's own duty (it redoes the snapshot), not an assumption about the environment.
- `run_lifecycle.safety.cfg`, `run_lifecycle.grading.cfg`: `NumTurns = 1`.

**Registered change outside my owned paths (seam request `req-01M41F2PAKH97KH6BDGXCTA1KK`).** `tools/check_models.py` must carry the new variants, the retargeted ones, the turns run and the two witnesses, or main's reverse MOD-A check (`unregistered_variants`) and three tests in `tests/test_check_models.py` fail the moment the `.tla` lands (section 6.1 shows which). The proposed `check_models.py` is the one the runs below used; its diff against `tools/check_models.py` at the base is in Appendix A.

### 6.1 TLC run (the evidence)

**TLC version and host.** TLC2 2.19 (08 August 2024), `tla2tools.jar` from `.tools/` (the pinned jar `check_models.py` verifies by sha256), Java 21.0.11, 24 workers, this Windows host, 2026-10-03. Model files at the time of the runs: `run_lifecycle.tla` sha256 `6d4a07cf...`, `.turns.cfg` `894e12b2...`.

**The command** (every run; `<cfg>` is the file named in the table; from the `models/` folder; `check_models.py` runs the same line through `subprocess`):

```text
java -XX:+UseParallelGC -XX:MaxRAMPercentage=75 -cp <repo>/.tools/tla2tools.jar tlc2.TLC -workers auto -metadir <scratch> -config <cfg> run_lifecycle.tla
```

**The real design passes (BUG = "none").** Exit status 0 and "No error has been found" for each:

| run | config | states generated | distinct states | depth | time | exit |
| --- | --- | --- | --- | --- | --- | --- |
| liveness (5 properties), 1 cell, 1 crash, `NumTurns = 2` | `run_lifecycle.liveness.cfg` | 501,735 | 154,632 | 36 | 12 s | 0 |
| grading, 2 cells, 2 passes, engine and bench | `run_lifecycle.grading.cfg` (`NumTurns = 1`) | 187,025,487 | 38,172,744 | 47 | 2 min 53 s | 0 |
| safety small (2 cells, parallelism 1, engine and bench grading) | `safety.cfg` with `check_models.SMALL` (`NumTurns = 1`) | 61,778,797 | 12,996,464 | 43 | 58 s | 0 |
| **safety, two turns** (2 cells, parallelism 1, 1 crash): all five ADR-0015 invariants and the ten others | `run_lifecycle.turns.cfg` (`NumTurns = 2`) | 61,049,395 | 14,946,904 | 57 | 1 min 23 s | 0 |
| safety at the US-44 bounds (3 cells, parallelism 2, 1 crash) | `run_lifecycle.safety.cfg` (`NumTurns = 1`) | 1,840,589,597 | 363,738,864 | 58 | 41 min 54 s | 0 |

The deep run (2 crashes) was not run, as before. Two honest notes. (1) The US-44 run is 4.3 times the distinct states and about 7 times the time of the version-4 model (85,060,752 states, run-lifecycle-model.md); the three-step archive write is the cause. `check_models.py --quick` skips it, and it belongs in the post-merge ring, not every push (CE principles). (2) TLC's fingerprint-collision estimate at 3.6e8 states is 2.8e-3 (actual) and 2.9e-2 (optimistic); the version-4 run's estimate was not recorded. That is a weak margin for a 64-bit fingerprint set; the smaller runs are at 1e-6 to 1e-4. Residual: a collision could hide a state at the US-44 bounds. The smaller runs and the two-turn run carry the turn invariants, so the residual does not touch them.

**Every seeded variant is rejected by its own target, and all four witnesses are violated.** Verbatim output of the proposed `python tools/check_models.py --quick` (exit 0; `--quick` skips only the US-44 row above, which was run directly):

```text
ok   liveness                 real design, 154632 states, 13s
ok   grading                  real design, 38172744 states, 225s
ok   safety-small             real design, 12996464 states, 72s
ok   safety-turns             real design, 14946904 states, 83s
ok   witness                  NotAllCellsFinished violated (3s)
ok   grace-witness            NoGraceState violated (1s)
ok   turns-witness            NotAllTurnsDelivered violated (2s)
ok   between-witness          NotCrashBetween violated (2s)
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
ok   archive_in_place         rejected by ArchiveExistsMeansComplete
ok   snapshot_in_place        rejected by ArchiveExistsMeansComplete
seeded variants: 28/28 rejected by own target
reachability witnesses: 4/4 violated
all model checks passed
exit=0
```

The last six variant lines are the new ones; together they cover the five ADR-0015 section 7 invariants (`PromptOncePerTurn` also keeps its two older variants; `ArchiveExistsMeansComplete` has one for the final archive and one for a snapshot). Each was run against **its target alone** (`only_invariant`), at `run_lifecycle.turns.cfg` bounds when it needs a second turn (`TURN_VARIANTS`). One counterexample, run directly (`kill_between_turns`, `CrashedTurnPredicate` only, exit 12 = invariant violated): 14 states, the shortest being turn 1 ends, the adapter exits, the snapshot is taken and recorded, the engine crashes, resumes, and `ReconcileRecord` writes `crashfail` where `ClassOf` says `crashbetween`. That is ADR-0015 section 7's "kills a cell whose turn 1 ended".

**What the first runs found (kept as evidence the checks have teeth).** (1) A liveness property failed on the first extension: a resumed between-turns cell waited forever for a snapshot nobody was obliged to take; the fix was fairness on `CopyBegin` for every artifact. (2) A counterexample showed a stale temporary folder being published by an unrelated later copy when `copying` was a boolean; the fix made `copying[c]` name the artifact in progress. (3) `PromptedCellsEnd` read `promptSent[c]` as a boolean after the variable became a per-turn function; TLC rejected the non-boolean at the initial state.

**Without the grant, what breaks on main.** Run in a temporary tree with main's `tools/check_models.py` and `tests/test_check_models.py` and this model: `3 failed, 4 passed` (`test_every_checked_property_has_a_seeded_variant`, `test_every_seeded_variant_targets_a_declared_property`, `test_an_unregistered_seeded_bug_is_rejected_by_the_reverse_check`; the last names the six new variants). With the proposed `check_models.py` and the existing, unchanged test file: `7 passed`. The seam (section 13) is therefore one file, plus an optional test pin (T-MOD-1).

## 7. Change-surface list (E7)

store (`events`, `archive_files` segments, the archive folder tree) -> model (`run_lifecycle.tla`, `lifecycle.TABLE`) -> service (`driver.py`, `engine.py`, `archive.py`) -> projection and wire (`views.KEYS`, `views.verify`, `plan.py`) -> client type (`TurnResult`, `TurnRecord`, `Cause.archive`) -> UI (report) -> compute reader (grade, report).

| # | surface | what changes | owner (W0 section 13) | reached by test |
| --- | --- | --- | --- | --- |
| 1 | `models/run_lifecycle.tla` and `.cfg` | this design | W1-J | TLC (section 6.1) |
| 2 | `tools/check_models.py` (required); `tests/test_check_models.py` (one pin, T-MOD-1); `docs/design/run-lifecycle-model.md` and `models/README.md` (mapping rows, the config list) | variants, witnesses, turns run | seam SR-J2 (granted to W1-J, or X-J1 in the same commit) | `test_check_models.py` (7 existing tests green with the proposed script) |
| 3 | `lifecycle.py` `TABLE` and `replay` | the four turn rules | X-J1 | T-LIF-1, T-LIF-2 |
| 4 | `driver.py` | `open_session`, `send_turn`, `TurnRecord`, `run_turn` wrapper | X-J1 (not a hub-table file; the driver has no other E2 owner, section 13 note) | T-DRV-1, T-ENG-1 |
| 5 | `engine.py` `_attempt`, `_after_append`, `_snapshot_turn`, usage sum, barrier | the turn loop and the budget fix | X-J1 | T-ENG-1..9 |
| 6 | `archive.py` | `snapshot_cell`, `snapshot_folder`, `append_missing_rows`; shares `_copy` with `archive_cell` | X-J1 (X-B2 changed `archive_cell` to `publish_dir` in E1) | T-SNAP-1..4 |
| 7 | `views.py` `KEYS["archive_files"]`, `verify` | add `snapshot`; final-rows filter; snapshot verification | X-J1 | T-VER-1..4 |
| 8 | `errors.py` | `HB-LED-008` text, `Cause.archive` (`HB-CELL-117`) | X-J1 | `test_errors.py` (existing registry test) |
| 9 | `plan.py` | `tasks.<id>.turns` | X-J1 (`turns` only) | T-PLAN-1 |
| 10 | `ledger.py` | nothing: the new kinds are plain `events` rows. If `ledger.py` carries a kind allowlist, X-J1 adds the two kinds. [Inferred; the text was not read for a kind list.] | X-J1 | T-ENG-1 (a row of each kind is appended) |
| 11 | `grade/runner.py` | reads `archive.snapshot_folder` for `graded_snapshots`; no other change | X-J2 | out of scope here; the helper is the contract |
| 12 | `report/*` | quiescence filter; per-turn rows | X-A3 / later | out of scope here |
| 13 | `tests/fake_acp_agent.py` | `per_turn` config and a prompts log | X-J1 (tests) | T-ENG-1 |

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

A name such as `attempt-1-turn-1` would have matched three of these globs (`int("1")` parses; `rsplit("-",1)[-1].isdigit()` is true). That is why the folder is `turn-<n>` (D-J1). T-SWEEP-1 pins the list.

## 8. Failure-mode analysis

| # | category | failure mode | disposition | residual / test |
| --- | --- | --- | --- | --- |
| F1 | state | crash during a snapshot copy | prevent: copy to a temp sibling, rename after verify; resume deletes the temp and redoes the copy | T-SNAP-1; model `ArchiveExistsMeansComplete` |
| F2 | state | crash after the rename, before the rows or event | recover: the recovery rule, extended to partial rows | T-SNAP-3 |
| F3 | state | crash between turns | accept: the adapter died with the engine (kill-on-close); record `failed (coordinator crash between turns)` (X-K1), never relaunch | model `CrashedTurnPredicate`, witness `NotCrashBetween`; X-K1 owns the code |
| F4 | concurrency | a process the agent left running writes during the copy | accept (ADR-0015 section 4); measure via `job_active_processes` and the baseline | T-SNAP-5; residual: a report that ignores the filter counts a noisy snapshot |
| F5 | concurrency | a kill (budget, stop, suspend) arrives during the copy | prevent turn 2: the cancel check follows the copy; keep the published snapshot | T-ENG-7 |
| F6 | resource | a lingering process holds a file exclusively | mitigate: bounded retry, then `failed (archive)` HB-CELL-117 | T-SNAP-6; S-J3 |
| F7 | resource | the copy takes long and eats the budget | accept: counted in the one budget, measured in `duration_ms`; 1.3 s for the largest committed workspace | S-J2; a `bench plan` envelope already adds copy time (ADR-0021 section 8) |
| F8 | resource | disk fills during the copy | detect: the copy raises `OSError`; `Cause.disk` is the existing cause (`_disk_full`), the attempt ends | covered by the retry branch classification (T-SNAP-6 variant) |
| F9 | input | turn 1 ends with `max_tokens`, `refusal` or an error | prevent turn 2: only `end_turn` continues | T-ENG-6 |
| F10 | input | the adapter dies between turns (EOF on turn 2's send) | detect: `send_turn` returns `None` with `adapter_crash`; the attempt ends; the snapshot stays | T-ENG-8 |
| F11 | dependency | auth fails on turn 2 | detect: `blocked_auth` through `_prompt_error_cause`, never NOT_RECORDED (council R4) | T-ENG-9 |
| F12 | time | host sleeps during turn 2 or the snapshot | detect: `SleepDetector` covers the whole attempt (`engine.py:379-397`); `host_suspended` | T-ENG-5 |
| F13 | state | the turn-2 budget restarts | prevent: set `prompt_mono` only at turn 1 | T-ENG-2 |
| F14 | state | the final `archive_hash` absorbs snapshot rows and every verify fails | prevent: `verify` filters final rows; KEYS carries `snapshot` | T-VER-1 |
| F15 | state | two turn-1 prompts after a resume | prevent: `PromptOncePerTurn` in the model and `replay` | T-LIF-1; X-K1 test |
| F16 | dependency | the third-prompt behaviour is unverified | prevent: the plan refuses more than one entry in `turns` (the readiness check is X-E's; the engine loop is generic but the model is bounded at 2) | T-PLAN-2 |
| F17 | state | `session/prompt` for turn 2 arrives after the adapter's own timeout | accept: the session lived for the spike's seconds; a long idle gap is unmeasured. The gap is the snapshot (about a second) plus the barrier | residual; a follow-up when a rework task has been run end to end |

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
| was the tree quiescent | `.job_active_processes` against `attempt.session_opened.job_active_baseline` |
| what did each turn spend | `cell.turn_ended.usage` (verbatim); the summed `turn_usage` row |
| did the model check pass | the `check_models.py` log lines (build-time control, as for the existing model) |

Cost axes covered: latency (turn and copy), volume (files, bytes), spend (usage per turn), failure rate (HB-CELL-117 outcomes). Every path degrades to null, never to 0: `job_active_processes` and `usage` are null when not reported. One structured log line per snapshot: `log.info("turn snapshot archived", extra={cell_id, turn, files, bytes, duration_ms})`, and on failure `log.error(..., extra={error_code: "HB-CELL-117", ...})`, using the existing logger and `trace_id` correlation (`engine.py:924`). The planned test for the load-bearing fields is T-ENG-1 (schema and plausibility of each field).

## 11. Test plan, by node id

**The four checks, per test.** (a) the assertion that fails today and why, on a seam that exists today; where the symbol does not exist yet the test is **created with its module** and says so, with the red-first proof moved to the mutant. (b) the red fixture for every guard or scan. (c) a real-wiring test beside any fake. (d) the mutant that distinguishes adjacent rules or states (each mutant is a `tests/mutations/<module>.json` row, run by the repo's existing mutation runner).

Real wiring used throughout: the real `driver` and `engine` against `tests/fake_acp_agent.py`, a separate OS process that speaks ACP on stdio (the existing pattern in `test_engine.py`); the real `archive`, `atomic.publish_dir` and `views` on `tmp_path`; no fake driver anywhere.

| id | test (file) | (a) fails today because | (b) red fixture | (c) real wiring | (d) mutant |
| --- | --- | --- | --- | --- | --- |
| **T-ENG-1** | two turns, one session, ordered ledger, snapshot content differs from final (`tests/test_engine.py`) | a plan task with `turns` is ignored by `_attempt` (`engine.py:724`), so the fake receives one prompt: `prompts_log == [p1, p2]` fails on the existing `Engine.run` seam | n/a (behavioural) | whole path; `lifecycle.replay(events)` runs on the engine's real output | **M-ORDER** swap the snapshot after the send: the snapshot then holds `a.txt == 2`; **M-ONCE** call `session_opened` barrier per turn: two `session_opened` rows |
| **T-ENG-2** | the budget does not restart at turn 2 (`test_engine.py`; engine `clock` injected) | with `turns` ignored the cell completes; expected `timed_out` fails | budget 10 s, turn 1 takes 6 s, turn 2 takes 6 s | real driver, fake agent `sleep` per turn | **M-CLOCK** drop the `turn == 1` condition in `_after_append`: cell completes, test red; this distinguishes it from "turns ignored" (which also completes) by also asserting `prompt_sent{2}` is present |
| **T-ENG-3** | stdin stays open between turns, closes after the last (`test_engine.py`) | one-prompt flow: the fake logs `eof` after prompt 1 and there is no prompt 2 | the fake logs `eof` and prompt events with a sequence number | real | **M-CLOSE** call `_end_process` after turn 1: the agent sees EOF before prompt 2 |
| **T-ENG-4** | spend and `turn_usage` are the sum over turns; `acp_turn` and `native_record` (`test_engine.py`) | today the sum equals turn 1 only (the last response): expected `u1 + u2` fails | fake returns `usage` 5 and 7 | real | **M-LAST** use `result.usage` only: sum 7, not 12 |
| **T-ENG-5** | a suspend gap during turn 2 yields `host_suspended` (R3) | turn 2 never starts today | injected `SleepDetector.slept` true after `prompt_sent{2}` | real engine loop | **M-RESET** re-create the detector between turns |
| **T-ENG-6** | `max_tokens` (a "completed" reason) on turn 1 sends no turn 2 and no snapshot | today the single prompt returns and the test's `prompt_sent{2}` absence holds trivially, so this test is red-first by M-STOP below, **created with the loop** | fake stop reason `max_tokens`, then `end_turn` | real | **M-STOP** gate on `COMPLETED_STOP_REASONS` instead of `== "end_turn"`: turn 2 is sent |
| **T-ENG-7** | a budget kill during the snapshot: the snapshot stays, no `prompt_sent{2}`, outcome `timed_out` | created with the loop | fake barrier slows `snapshot_cell` (a 50 ms per-file delay hook on `archive.snapshot_cell`'s `fill`, test-only) | real kill path | **M-NOCHECK** drop the cancel check before turn 2 |
| **T-ENG-8** | EOF on turn 2's send ends the attempt with `adapter_crash`, snapshot kept | created with the loop | fake exits after prompt 1's snapshot | real | **M-SWALLOW** treat `send_turn` None as success |
| **T-ENG-9** | an auth error on turn 2 is `blocked_auth` | created with the loop; the existing seam `driver._prompt_error_cause` is tested for turn 1 | fake `prompt_error` only on the second prompt | real | **M-CAUSE** map any turn-2 error to `adapter_crash` |
| **T-DRV-1** | `open_session` then `send_turn` x2 on one channel; `run_turn` unchanged for one turn (`tests/test_driver.py`) | `open_session` does not exist: **created with its module**. Today's seam is `run_turn`; its existing tests must stay green and are the regression half | the fake counts `session/new` | real subprocess | **M-NEWSESSION** `send_turn` re-handshakes: two `session/new` |
| **T-SNAP-1** | kill during the copy leaves no final name; a rerun completes; `stale_temps` finds the leftover (`tests/test_archive.py`) | the `archive_cell` half is red today (partial `attempt-1`, rerun raises HB-USR-002) and goes green with X-B2 in E1; the `snapshot_cell` half is **created with the function** | a child process killed (`os._exit`) after 2 files | real filesystem, real child | **M-INPLACE** copy straight to the final name |
| **T-SNAP-2** | a pre-existing `turn-1` is refused, never merged | **created with the function** (today's analogue: `archive_cell` refuses an existing folder, `test_archive.py` HB-USR-002 path) | folder pre-created with a stray file | real | **M-MERGE** drop the exists check |
| **T-SNAP-3** | crash after k of n row appends: resume appends only the missing rows and the event (`tests/test_engine.py`) | today re-running `_archive` after partial rows raises HB-USR-002 (the folder exists); the snapshot path is **created with its module** | engine killed by a raising ledger after k rows | real ledger | **M-DUP** append all rows: `HB-LED-003` |
| **T-SNAP-4** | only `ws/` is copied; no `home/`, no credential file | **created with the function** | home holds `.credentials.json`; ws holds a file named like a credential | real | **M-HOME** include every top-level folder |
| **T-SNAP-5** | a lingering process (fake `daemon` option) shows `job_active_processes > baseline` | created with the field | fake starts a detached grandchild | real job object | **M-ZERO** record a constant 0 |
| **T-SNAP-6** | an exclusive lock on one file: three retries, then HB-CELL-117; no turn 2 | created with the retry | a child holds `msvcrt.locking` (S-J3 recipe) | real lock | **M-RETRYALL** retry forever |
| **T-SNAP-7** | a link in `ws/` is a row, not a copy | existing rule in `archive_cell` (`test_archive.py` links test); the shared `_copy` must keep it | a junction/symlink to a sentinel outside | real | **M-FOLLOW** the existing mutation row "follow links" |
| **T-VER-1** | `views.verify` accepts a run with snapshot rows that reuse a final row's path | **red today**: `views.load` raises `HB-LED-003 duplicate archive_files key` (KEYS lacks `snapshot`), so `findings == []` fails (`tests/test_verify.py`, built on `archived_runs.make_run`) | the fixture itself: same `(cell, attempt, path)` in a final and a snapshot row | real `views.verify` | **M-KEY** remove `snapshot` from KEYS: duplicate; **M-FILTER** drop the final-rows filter: `HB-LED-005` on the final hash. The two fail differently, so they are distinguishable |
| **T-VER-2** | HB-LED-008 for each of: tampered snapshot file; `snapshot_hash` wrong; `files`/`bytes` wrong; event with no rows | **created with the check** (today `verify` does not look at snapshots, so a tampered snapshot passes: the `findings` contains `HB-LED-008` assertion fails) | four tampered fixtures, one per branch | real | one mutant per branch (skip file check, skip hash, skip counts, skip empty-rows) |
| **T-VER-3** | legacy ledgers verify unchanged: the committed golden ledgers (`test_verify.py::test_a_golden_ledger_keeps_its_hashes_and_row_counts`) | green today; it must stay green | n/a | real | **M-LEGACY** treat an absent `snapshot` as non-final: the golden fails |
| **T-VER-4** | the final `archive_hash` is unchanged by adding snapshot rows | **red today** with T-VER-1's fixture (it errors earlier), green after | same fixture | real | **M-FILTER** (as above) |
| **T-LIF-1** | `replay` accepts a valid two-turn stream | **red today**: `cell.turn_ended` is "unmapped" and a second `cell.prompt_sent` trips `AT_MOST_ONCE` (`lifecycle.py`), so `replay(good)` raises | the valid stream | the same stream the real engine emits in T-ENG-1 | n/a |
| **T-LIF-2** | `replay` rejects each of four streams, each naming its rule: second `prompt_sent{2}`; `prompt_sent{2}` before `snapshot{1}`; `snapshot{1}` before `turn_ended{1}`; `turn_ended{2}` with no `prompt_sent{2}` | **red today**: the first stream raises the old `AT_MOST_ONCE` text ("AtMostOnePrompt") and the other three raise `unmapped transition`; none names the new rule, so `rule in str(error)` fails for all four | the four streams | real `lifecycle.replay` | one TABLE-row mutant per rule; the `snapshot{1}-before-turn_ended{1}` and `prompt_sent{2}-before-snapshot{1}` pair distinguishes `NoSnapshotInFlight` from `SnapshotBeforeNextTurn` |
| **T-PLAN-1** | `build_plan` records `turns: [{n, prompt, sha256}]`, LF-normalised | **red today**: the plan task has no `turns` key (`plan.py:153-154` handles `prompt.md` only) | a task dir with `turns/2.md` in CRLF | real `build_plan` | **M-CRLF** hash the raw bytes |
| **T-PLAN-2** | more than one `turns` entry is refused | created with the check | a task with two turn files | real | **M-BOUND** remove the bound |
| **T-SWEEP-1** | the archive-reader list in section 7 equals the tree's | **red today** only if the list drifts; it is a guard (`tests/test_archive_readers.py`) | a synthetic source with `archive/<cid>` and `glob("*")` is flagged | scans the real `src/` | **M-ADD** add a reader file: the test names it |
| **T-MOD-1** | `TURN_VARIANTS` is a subset of `VARIANTS`, and each `TURN_WITNESSES` name is defined in the model (`tests/test_check_models.py`) | **created with the script change**; today `TURN_*` do not exist | a `TURN_WITNESSES` entry naming an undefined invariant | real file read | **M-DEF** delete a witness definition from the `.tla` copy |
| **TLC** | `python tools/check_models.py` (proposed): real design passes, each variant rejected by its own target, witnesses violated | the six new variants and the retargeted ones are unknown to today's script (**created with the script change**; the model itself is the red-first artifact: section 6.1 shows each rejection) | the seeded variants are the red fixtures | TLC is the real checker | removing a guard from the model: the variant row fails to be rejected, so the script fails |

**Conformance.** `tests/test_lifecycle_conformance.py` (existing) checks the table against the model; T-LIF-1 and T-LIF-2 extend its GOOD stream and its seeded-ledger set.

**Not tested, by decision (tests earn their place).** The model's own row-by-row append is covered at file level (T-SNAP-3), not by TLC. The temp sweep is T-SNAP-1. A second turn on macOS is not run (spike E4 residual, ADR-0015).

## 12. Spikes

| id | question | method | result |
| --- | --- | --- | --- |
| S-J1 | Does TLC finish the extended model at useful bounds, and does it reject every variant? | the real `check_models.py` flow (section 6.1) | yes; sizes and times in section 6.1 |
| S-J2 | What does a snapshot copy cost on real workspaces? | `archive.archive_cell` (the same copy loop `snapshot_cell` will share) on the committed task workspaces, each made a git repository, 5 runs each, this Windows host | D1 (largest: 560 files, 7,072,817 bytes) 1,205 to 1,436 ms; B2 (30 files, 217,445 bytes) 52 to 110 ms; A4 (42 files, 37,757 bytes) 70 to 136 ms. **Verified** on this host; not a macOS figure |
| S-J3 | What does a lingering writer do to the copy? | a child process holds one file three ways, then `archive_cell` copies | shared handle (Python `open("a")`): copies (the content is whatever was flushed: a non-quiescent snapshot); `msvcrt.locking` byte-range lock: `PermissionError`; a handle opened with no sharing: `PermissionError`. `winerror` is `None` on these `PermissionError`s, so the retry catches `PermissionError`, not a winerror. **Verified.** Today's `archive_cell` copies straight into the final folder, so this failure leaves a partial `attempt-1` there: the D1 defect that `publish_dir` removes (the same copy into a temp sibling leaves nothing at the final name) |

Script: `w1j_spike.py` was run from the session scratchpad and is not committed (it writes only temp folders). Its recipe is the table above.

## 13. Open decisions, seam requests and proposed amendments

**Decisions made here (the author's, for the reviewers to attack):** D-J1 folder `turn-<n>`; D-J2 final rows omit `snapshot`; D-J3 one hash function; D-J4 `run_turn` stays as a wrapper; D-J5 `TurnResult` holds the last turn plus `turns`; D-J6 usage is summed; D-J7 the copy counts against the one budget; D-J8 only `end_turn` continues; D-J9 HB-LED-008 merged meaning, HB-CELL-117 confirmed; D-J10 the model has `NumTurns` 1 or 2 and no sweep action.

**Seam requests.**

| id | to | ask | status |
| --- | --- | --- | --- |
| `req-01M41F2PAKH97KH6BDGXCTA1KK` (SR-J2) | coord-opus-e1e4 | grant W1-J (or fold into X-J1's first commit) `tools/check_models.py` (required: Appendix A is the whole change), `tests/test_check_models.py` (T-MOD-1 pin, optional), `models/README.md` and `docs/design/run-lifecycle-model.md` (mapping rows); main must not receive my `.tla` without `check_models.py` | sent; fallback: my branch is held from merge until it lands |
| SR-J1 | coord-opus-e1e4 | W0 section 12: add `attempt.session_opened.job_active_baseline` (count right after `session/new`) so `job_active_processes` is interpretable | **provisional**: designed as if granted; if refused the field degrades as section 4.4 says |
| SR-J3 | coord-opus-e1e4 | W0 section 5: `tasks.<id>.turns` entries are `{n, prompt, sha256}`, not `{n, sha256}`: the engine sends the plan's frozen text (`plan.py:153` freezes turn 1 this way; US-10) | **provisional** |
| SR-J4 | coord-opus-e1e4 | W1-B and W1-J share one `archive.append_missing_rows` helper for the partial-rows recovery (section 3) | to tell W1-B; not blocking |

**Proposed amendments to ADR-0015 (the Coordinator or Owner decides; this design does not edit the ADR).**
1. Section 5a names the temporary sibling `<name>.tmp-<pid>`; W0 section 4 (rev 2) names it `<name>.tmp-<pid>-<uuid>` and creates it exclusively. The W0 text wins; the ADR line should say so.
2. Section 5a "On resume ... a final folder with no archived event is re-verified": extend to "and its rows, if partial, are completed" (section 3).
3. Section 2 (d) should state the ordering the model checks: the snapshot **event** (not only the rename) precedes `prompt_sent{n+1}`.
4. Section 6's "A turn-2 intent is never written before the turn-1 snapshot event" is `SnapshotBeforeNextTurn`; record the invariant names beside it.

**Open decision:** the code for "more than one `turns` entry" (T-PLAN-2): reuse an `HB-RDY` row from W1-E's readiness set. No new code is invented here.

## 14. Definition-of-done self-check (Stage 4)

- Single responsibility; boundaries named: yes (section 1).
- Data model first; aggregate and invariant; grain; additivity; history; derive-don't-store; writers and readers: yes (section 2). Append-only enforcement tests: T-VER-2, T-SNAP-2 (forbidden overwrite), T-SNAP-3. No rebuild claim is made, so no rebuild test.
- Surface list: section 7. Delivery phasing: E2, X-J1 after this model passes TLC.
- Patterns named and attacked: section 5. Ladder: section 5.
- Contracts established, unfamiliar ones spiked: ACP second prompt (spike E4, Verified on Windows); copy cost and lock behaviour (S-J2, S-J3).
- Failure modes: section 8. STRIDE-lite: section 9. Privacy: none (section 9). UI: none (no interface; the report is X-A3's). Rollups: `docs/security/threat-model.md` and `privacy-review.md` were not refreshed (section 9 states no new boundary class and no personal data); **unmet**, to be decided at the gate.
- Telemetry: section 10. Tests by node id with the four checks: section 11.
- Hard vetoes: **pending** reviewers; the author clears none.
- Unmet or provisional: SR-J1 and SR-J3 provisional; the rollup refresh; the `ledger.py` kind list is Inferred (section 7 row 10); macOS unverified.

## Gate record

| lens | verdict | line |
| --- | --- | --- |
| RV-PAT (Patterns Expert) | pending | |
| RV-SIM (Simplifier, soft veto) | pending | |
| RV-TA (Test Architect, hard veto) | pending | |
| RV-DS (Distributed Systems, hard veto) | pending | |
| RV-SRE (SRE) | pending | |

The author applies findings in a follow-up message and copies each reviewer's gate line here verbatim. No veto is cleared by the author.

## Appendix A: the proposed `tools/check_models.py` change (seam SR-J2)

A unified diff against `tools/check_models.py` at the base `124395fb` (line endings normalised). Applying it makes `tests/test_check_models.py` pass unchanged (7 of 7) and `check_models.py --quick` pass as in section 6.1.

```diff
@@ -34,8 +34,8 @@
 MODEL = "run_lifecycle"
 # Seeded bug -> the invariant ("inv") or temporal property ("prop") that must reject it.
 VARIANTS = {
-    "relaunch_prompted": ("inv", "AtMostOnePrompt"),
-    "send_before_persist": ("inv", "AtMostOnePrompt"),
+    "relaunch_prompted": ("inv", "PromptOncePerTurn"),
+    "send_before_persist": ("inv", "PromptOncePerTurn"),
     "launch_after_outcome": ("inv", "NoPromptAfterOutcome"),
     "archive_live": ("inv", "NoArchiveWhileLive"),
     "delete_before_archive": ("inv", "NothingDeletedUnarchived"),
@@ -56,7 +56,16 @@
     "no_budget_kill": ("prop", "PromptedCellsEnd"),
     "grade_skipped": ("prop", "ArchivedCellsGetGraded"),
     "no_escalate": ("prop", "StopReachesTerminal"),
+    # ADR-0015 section 7: the turn rules. These run at the two-turn bounds (run_lifecycle.turns.cfg).
+    "resend_turn_on_resume": ("inv", "PromptOncePerTurn"),
+    "prompt_before_snapshot": ("inv", "SnapshotBeforeNextTurn"),
+    "snapshot_in_flight": ("inv", "NoSnapshotInFlight"),
+    "kill_between_turns": ("inv", "CrashedTurnPredicate"),
+    "archive_in_place": ("inv", "ArchiveExistsMeansComplete"),
+    "snapshot_in_place": ("inv", "ArchiveExistsMeansComplete"),
 }
+TURN_VARIANTS = {"resend_turn_on_resume", "prompt_before_snapshot", "snapshot_in_flight", "kill_between_turns",
+                 "snapshot_in_place"}  # need NumTurns = 2 (a snapshot, a second prompt); the rest run at one turn
 # The real design and the variants run at small bounds (2 cells, parallelism 1, 1 crash, 1 pass, the
 # engine and `bench grade` both grading); two-pass variants use the grading config. Every seeded
 # defect is reachable there.
@@ -67,6 +76,7 @@
 # Variants whose defect needs a free slot beside an orphan run at parallelism 2.
 WIDER = {"reconcile_no_wait": {"Parallelism = 1": "Parallelism = 2"}}
 WITNESSES = {"witness": "NotAllCellsFinished", "grace-witness": "NoGraceState"}
+TURN_WITNESSES = {"turns-witness": "NotAllTurnsDelivered", "between-witness": "NotCrashBetween"}
 
 
 def ensure_jar() -> Path:
@@ -145,7 +155,8 @@
     failures = []
 
     grading = (MODELS / f"{MODEL}.grading.cfg").read_text(encoding="utf-8")
-    runs = [("liveness", liveness), ("grading", grading), ("safety-small", small)]
+    turns = (MODELS / f"{MODEL}.turns.cfg").read_text(encoding="utf-8")
+    runs = [("liveness", liveness), ("grading", grading), ("safety-small", small), ("safety-turns", turns)]
     if "--quick" not in argv:
         runs.append(("safety", safety))
     if "--deep" in argv:
@@ -161,8 +172,8 @@
         real_clean[label] = clean
 
     witnessed = 0
-    for label, name in WITNESSES.items():
-        code, out, secs = tlc(only_invariant(small, name), label)
+    for label, name in {**WITNESSES, **TURN_WITNESSES}.items():
+        code, out, secs = tlc(only_invariant(turns if name in TURN_WITNESSES.values() else small, name), label)
         reached = f"Invariant {name} is violated" in out
         print(f"{'ok  ' if reached else 'FAIL'} {label:<24} {name} violated ({secs:.0f}s)", flush=True)
         if reached:
@@ -175,7 +186,7 @@
         if kind == "prop":
             base = only_property(liveness, target)
         else:
-            base = only_invariant(grading if bug in TWO_PASS else small, target)
+            base = only_invariant(grading if bug in TWO_PASS else turns if bug in TURN_VARIANTS else small, target)
         cfg = with_bug(substitute(base, WIDER.get(bug, {})), bug)
         code, out, secs = tlc(cfg, bug)
         expected = (f"Invariant {target} is violated" if kind == "inv"
@@ -189,7 +200,7 @@
         else:
             rejected += 1
     print(f"seeded variants: {rejected}/{len(VARIANTS)} rejected by own target", flush=True)
-    print(f"reachability witnesses: {witnessed}/{len(WITNESSES)} violated", flush=True)
+    print(f"reachability witnesses: {witnessed}/{len(WITNESSES) + len(TURN_WITNESSES)} violated", flush=True)
     if "--quick" not in argv:
         print(f"US-44 bounds: {'passed' if real_clean.get('safety') else 'FAILED'} (3 cells, parallelism 2, 1 crash)", flush=True)
     print(f"{len(failures)} failure(s)" if failures else "all model checks passed", flush=True)
```
