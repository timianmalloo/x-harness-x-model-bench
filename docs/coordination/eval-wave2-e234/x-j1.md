---
id: brief-eval-x-j1
title: "Brief X-J1: the multi-turn engine (E2 build) - unblocked by W1-J rev 2; starts after X-D joins"
type: plan
status: proposed
owner: "@timianmalloo"
links:
  - { to: coordination-eval-wave2-e234-briefs, rel: implements }
  - { to: design-eval-seam-contracts, rel: depends-on }
  - { to: design-eval-multi-turn, rel: depends-on }
review-by: "2026-10-17"
summary: "X-J1 builds W1-J rev 2's multi-turn engine (open_session/send_turn/Session.close, the turn loop with turn_ended.next, per-turn snapshots through publish_dir, append_missing_rows, the lifecycle turn rules) on Codex gpt-6.1-sol in five turns cut to W1-J section 11's commit order. W1-J's gate passed (merged f23d35ed). X-J1a starts after X-D (X-D1 and its D2 engine recheck) has joined, because X-D owns engine.py in E1 and engine.py edits are serialised."
---

# X-J1: the multi-turn engine

> **Unblocked by design** (Coordinator #9). W1-J rev 2 (`docs/design/eval-multi-turn.md`) passed its gate (TA, PAT, SIM, SRE, DS, all PASS WITH CONDITIONS, applied in rev 2) and merged at `f23d35ed` with `run_lifecycle.tla`, `turns.cfg` and `check_models.py` in one unit (`check_models --quick` 29/29, 4/4 witnesses). **X-J1a still waits on E1 joins:** X-D (X-D1 and the D2 engine recheck; X-D owns `engine.py` in E1, and edits to `engine.py` are serialised, so X-J1 never runs beside an open X-D tree), X-C, X-B2, X-B1b, X-A1a (README §3 DAG).

**Harness** Codex via `coord-runner` (Leader, R-87), `gpt-6.1-sol`, effort high, codex-cli 0.160.0 · **contract** `x-j1.contract.json` (J1a; J1b..e reuse it with the suffix and their own compilation) · **deadline** 3,600 s per dispatch · **budget** 320 calls · 200k · 5 dispatches · 5 h · **fallback** a red-only end or a failed read-back: the green follow-on runs as Claude Sonnet (`model: sonnet`, served `claude-sonnet-5-5`) in the same tree (R-87 Option 1).

**Design:** W1-J rev 2 (sections 2-4, 7, 8, 11, 12 bind you; section 11's commit order is your commit order), ADR-0015, W0 rev 6.7: §4 (`publish_dir`, `create_once`, folder-form `sweep_temps(folder, lock)`), §5 (`tasks.<id>.turns` `{n, prompt, sha256}`), §11 (HB-LED-008, HB-CELL-117), §12 (every row, with the rev 6.2 and **R6.5a, R6.5b, R6.5c** bullets), §13 (your rows). `models/*` and `tools/check_models.py` are W1-J's and already on `main`: do not edit them.

## Owned paths (E2 hub owner, W0 §13)
`src/harness_bench/driver.py`, `engine.py` (E2), `archive.py` (E2), `lifecycle.py`, `ledger.py` (E2; W1-J §7 row 10 Verified it needs no change), `views.py` (E2), `errors.py` (E2), `identity.py` (E2), `plan.py` (`turns` only, SR-J3), `status.py` (one hunk, R6.5b), their tests, `tests/fake_acp_agent.py`, `tests/test_archive_readers.py` (new, T-SWEEP-1), `tests/mutations/{engine,driver}.json`.

## The names (W1-J rev 2, final; use these and no other spelling)
- **Driver (§4.1):** `TurnRecord`, `Session` with idempotent `Session.close()` (the single owner of stdin, D-J13), `open_session(...) -> Session | None`, `send_turn(session, prompt, before_send, turn, on_first_update=None) -> TurnRecord | None`, `run_turn` kept as the unchanged wrapper. `TurnResult.turns`; its `stop_reason`, `usage`, `turn_seconds`, `last_update_seconds` become read-only properties over `turns[-1]`.
- **Engine (§4.2-4.5):** the turn loop in `_attempt`; `record_session_opened` (writes `attempt.session_opened` once; `barrier_for(n)` writes only `cell.prompt_sent{turn: n}`); `_snapshot_turn`; usage summed over `result.turns`.
- **Archive (§2, §3):** `archive.snapshot_folder(run_dir, cell_id, turn)` → `<run_dir>/archive/<cell_id>/turn-<n>/` (only `ws/`); `archive.snapshot_cell(...)` through `atomic.publish_dir`; `archive.snapshot_of(row)` (the one final-row predicate: absent or `"final"` reads `final`); `archive.append_missing_rows(folder, rows, present, code)`. Final rows never carry `snapshot` (D-J2).
- **Events (§3):** `cell.prompt_sent{turn}` (absent reads 1); `cell.turn_ended{turn, stop_reason, turn_ms, usage, next}` (`turn_ms` an int, W1-J Amendment 1; was `turn_seconds`) with `job_active_baseline` on turn 1 only; `cell.turn_snapshot_archived{turn, snapshot_hash, files, bytes, duration_ms, job_active_processes, job_active_after, copy_retries}`.
- **Lifecycle (§4.6):** `lifecycle.is_cell_start(row)` (`row.get("turn", 1) == 1`); replay keyed by `(kind, turn)`; rule names `PromptOncePerTurn`, `SnapshotBeforeNextTurn`, `SnapshotAfterTurnEnd`, `CrashedTurnPredicate` (provisional for W1-K).
- **Errors (§3):** HB-LED-008 (merged meaning, D-J9); `Cause.archive = ("HB-CELL-117", "infrastructure", "failed (archive)")`. HB-CELL-118 and -119 stay X-K1's.

## Turns (re-cut on W1-J rev 2 §11's commit order K1..K4)
Each turn ends red and green and is joined before the next. J1a's red is the whole K3 table; a later turn's red is K3's existing red assertions for its group, re-run and pasted at the turn's start.
- **J1a, fake agent, skeleton, red tests, the clock:** registry first (`errors.py` HB-LED-008 text and `Cause.archive`; `identity.CLASSES` for every new module); **K1** the fake-agent options `per_turn`, `prompts_log`, `helper`, `daemon_after_update`; **K2** the skeleton that deliberately carries the bugs (§11 K2 row; all existing tests stay green); **K3** the whole test table, red on K2 by assertion, the commit message pasting the red lines of T-ENG-2, T-ENG-4, T-ENG-6 and T-DRV-1; then **K4(1)** the budget clock through `lifecycle.is_cell_start` and the `status.py` hunk (T-ENG-2, T-STATUS-1 green).
- **J1b, the turn loop:** K4(2) usage summed over turns (T-ENG-4 with no HB-VAL-005, T-ENG-11); K4(3) the `end_turn` gate and `turn_ended` with `next` for every returned turn (T-ENG-6, T-ENG-10); K4(4) one handshake and the idempotent `Session.close()` (T-DRV-1, T-DRV-2). **Coordinator #35 (W0 rev 6.12 R6.12a, R6.12b; W1-J Amendment 1):** the row's duration is `turn_ms` (an int), and T-ENG-11 is restated in integer ms. J1b also writes the one `lifecycle.TABLE` entry `cell.turn_ended` (`TurnEnd`, after `cell.prompt_sent`, rule `turn_ended follows its prompt_sent`) and its one `SEEDED` case in `tests/test_lifecycle_conformance.py`, in the K4(3) commit, because `check_writer` refuses an unmapped kind at write time. With that entry, T-LIF-1's single-turn case passes, so J1b splits T-LIF-1's marker per parameter: `count=1` unmarked (green by J1b's entry), and `count=2` keeping the J1d reason verbatim.
- **J1c, snapshots:** K4(5) `snapshot_cell` through `publish_dir`, the folder-form sweep, the cancel-aware retry, `append_missing_rows`, E2 snapshot recovery, the baseline and the two counts (T-ENG-1, T-ENG-5, T-ENG-7..9, T-SNAP-1..7); spike **S-J5**.
- **J1d, readers and conformance:** K4(6) `views` (KEYS `snapshot` through `snapshot_of`, the final-rows filter, the snapshot loop over events), `lifecycle` TABLE rules, `plan` `turns` (T-VER-1..7, T-LIF-1..3, T-PLAN-1, T-PLAN-2, T-SWEEP-1, T-WIRE-1); a legacy single-turn archive verifies unchanged. **Coordinator #35:** J1d builds on J1b's `cell.turn_ended` TABLE entry and its seeded case. It makes the entry's `after` check turn-keyed, and it owns every other TABLE change. It reads `turn_ms`, never `turn_seconds` (W1-J Amendment 1).
- **J1e, mutants and the baseline spike:** every §11 mutant as a row in `tests/mutations/{engine,driver}.json`, killed under `uv run` `mutate_check`; spike **S-J4**; the campaign plan's exit evidence.

## Acceptance items
1. **The budget clock (E1 README §8 (a); W1-J §4.3):** `engine._after_append` sets `a.prompt_mono` only when `lifecycle.is_cell_start(row)`, i.e. `turn == 1`; one budget per cell, measured across the snapshot copy and turn 2. Test T-ENG-2 (turn 2 does not get a second budget), mutant M-CLOCK.
2. **Spend summed across turns (E1 README §8 (b); W1-J §4.5):** `usage` is the concatenation of every turn record's entries; the ACP side of `views._token_cross_check` is the sum over the `turn_ended` rows present; a turn with no row is `not recorded`, never 0. T-ENG-4 (5 + 7 = 12, no HB-VAL-005), mutants M-LAST, M-XCHECK.
3. **`turn_ended` for stopping turns (R6.5a; W1-J §4.2, D-J11):** `cell.turn_ended` is written for every turn that returned a response, before the continue decision, with `stop_reason` and `next` ∈ {`snapshot`, `final`, `stop`, `cancel`}; only `end_turn` continues; a turn for which `send_turn` returned `None` has no row (its reason is the outcome cause). T-ENG-6, T-ENG-10, mutants M-STOP, M-CANCELFIRST.
4. **`status.py` reads the first `prompt_sent` (R6.5b; W1-J §4.3):** through the shared `lifecycle.is_cell_start`, so the status clock and the engine clock have one definition. T-STATUS-1 (two-turn fixture: status elapsed equals the engine budget clock at the same instant), mutant M-LASTWINS.
5. **`job_active_baseline` at turn 1's first update (R6.5c; W1-J §4.4, D-J12):** read once per attempt through `send_turn(on_first_update=...)`, written on `cell.turn_ended{1}`, absent (never 0) when no update arrived; `job_active_processes` (before the copy) and `job_active_after` (after it) both stay; a noisy snapshot is derived by readers, never stored; `copy_retries` is `publish_dir`'s returned count. T-SNAP-5, mutants M-ZERO, M-EARLY.
6. **`append_missing_rows` is yours (W0 rev 6.2/6.3, SR-J4):** one implementation, `archive.append_missing_rows(folder, rows, present, code)`; it appends only the missing keys and raises `code` on a present row that differs; the code follows the folder kind (snapshot HB-LED-008, final HB-LED-005). X-K1 calls it in E3 and holds no second comparison (DM7). T-SNAP-3, mutants M-DUP, M-CODE.
7. **E2 snapshot recovery is yours (W1-J §3, RV-DS 1):** on `FileExistsError` from `publish_dir`, `_snapshot_turn` verifies the folder and calls `append_missing_rows(..., "HB-LED-008")`; it never re-publishes. In E2 the path is reached by the retry of the same attempt; a planted `turn-1` on a fresh start is refused (T-SNAP-2).
8. **Spikes S-J4 and S-J5 (W1-J §12), run by X-J1 and recorded in the turn's report; W1-J §12's result column is updated by the Coordinator from that report (the design is not in your owned paths):**
   - **S-J5 (J1c):** a snapshot's cost through the real `atomic.publish_dir` on D1, cold and warm, at parallelism 3. Report the measured `duration_ms` beside S-J2's 1.3 s figure, which stays a floor (no folder fsync, no verify), never the full cost. A snapshot over the 10 s ceiling is a recorded finding, never a kill (F7).
   - **S-J4 (J1e):** on each of the three real adapters, count `job.active` right after `session/new`, at turn 1's first update, and at the end of a no-tool turn 1. If the first-update count is below the end-of-turn count, the read point moves only by a W0 amendment (send the seam request; do not move it yourself). If an adapter cannot be launched from your tree, report S-J4 as **not run** for it, with the reason; the residual "baseline not validated" stays in the report. Never a guessed count.
9. **One count, one name:** `job_active_processes` and `job_active_after` are two instants and both stay (R6.5c); no third name for either.
10. The campaign plan's exit evidence for X-J1 (all of it) and the Wave 1 testability floor; the §11 mutants as rows in `tests/mutations/{engine,driver}.json`.

## Exit
E1 README §3 join gate per dispatch; served model from the Codex native record. Report per E1 README §4.
