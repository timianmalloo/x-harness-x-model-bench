---
id: brief-eval-x-j1
title: "Brief X-J1: the multi-turn engine (E2 build) - BLOCKED on W1-J's gate"
type: plan
status: proposed
owner: "@timianmalloo"
links:
  - { to: coordination-eval-wave2-e234-briefs, rel: implements }
  - { to: design-eval-seam-contracts, rel: depends-on }
review-by: "2026-10-17"
summary: "X-J1 builds W1-J's multi-turn engine (driver, turn loop, per-turn snapshots, lifecycle conformance) on Codex gpt-6.1-sol in five turns. Blocked until W1-J passes its gate and merges; carries the four E1 conditions and W0 rev 6.2/6.5's rows as acceptance items."
---

# X-J1: the multi-turn engine

> **BLOCKED.** W1-J (`docs/design/eval-multi-turn.md`, branch `design/eval-multi-turn`) is in its gate revision. Do not dispatch until it merges with TLC output for every ADR-0015 §7 invariant and each seeded variant rejected (campaign plan, serial spine 4). The Coordinator then re-cuts the turn split below against the merged design and compiles X-J1a.

**Harness** Codex via `coord-runner` (Leader, R-87), `gpt-6.1-sol`, effort high, codex-cli 0.160.0 · **contract** `x-j1.contract.json` (J1a; J1b..e reuse it with the suffix) · **deadline** 3,300 s per dispatch · **budget** 320 calls · 200k · 5 dispatches · 5 h · **fallback** a red-only end or a failed read-back: the green follow-on runs as Claude Sonnet (`model: sonnet`, served `claude-sonnet-5-5`) in the same tree (R-87 Option 1).

**Design:** W1-J (once merged), ADR-0015, W0 rev 6.6: §4 (`publish_dir`, `create_once`, the sweep), §5 (`tasks.<id>.turns`), §11 (HB-LED-008, HB-CELL-117), §12 (every row, with the rev 6.2 and rev 6.5 bullets), §13 (your rows).

## Owned paths (E2 hub owner, W0 §13)
`src/harness_bench/driver.py`, `engine.py` (E2), `archive.py` (E2), `lifecycle.py`, `ledger.py` (E2), `views.py` (E2), `errors.py` (E2), `identity.py` (E2), `plan.py` (`turns` only, SR-J3), `status.py` (one hunk, R6.5b), their tests, `tests/fake_acp_agent.py`, `tests/mutations/{engine,driver}.json`. Not `models/*` or `tools/check_models.py` (W1-J's).

## Turns (provisional; re-cut after W1-J merges)
- **J1a, registry first:** `errors.py` E2 rows (HB-LED-008, HB-CELL-117, and W1-J's confirmed rows); `identity.CLASSES` for every new module; `plan.py` `turns` entries `{n, prompt, sha256}`, refused at `load_confirmed` when the text does not hash (HB-LED-002); the "cell start" helper (R6.5b).
- **J1b, the turn loop:** driver open / send turn / close; stdin closed only after the last turn; per-turn `prompt_sent{turn}` through the ack barrier; `cell.turn_ended` for **every** ended turn with `next` (R6.5a).
- **J1c, snapshots:** a create-once snapshot before turn 2 through `publish_dir`; partial-row recovery through `archive.append_missing_rows` (HB-LED-008 for a snapshot, HB-LED-005 for a final archive; the code follows the folder kind); `copy_retries`, `job_active_after`, `job_active_baseline` (R6.5c).
- **J1d, conformance:** `lifecycle.py` against the new invariants; a legacy single-turn archive verifies unchanged.
- **J1e, failure states:** kill in each turn state; EV-4 turn-2-not-reached; a seeded suspend in turn 2 gives `host_suspended`.

## Acceptance items
1. **E1 README §8 conditions (RV-SRE, RV-PAT F2 on W1-J):** (a) `engine._after_append` no longer resets the budget clock on every `cell.prompt_sent`: one budget per cell, from the first `prompt_sent` (test: turn 2 does not get a second budget); (b) claude-code `acp_turn` spend sums every turn, not the last (test: two turns of known usage); (c) a stopping turn (max_tokens, error, engine kill) writes `cell.turn_ended` with `stop_reason` and `next` (R6.5a; test per stop kind); (d) `bench status` reads the first `prompt_sent` (R6.5b; the two-turn test where status elapsed equals the engine clock).
2. **S-J2:** report the snapshot copy cost as a floor (no fsync of the folder, no verify; spike E1-NTFS) with the measured `duration_ms` beside it, never as the full cost.
3. **R6.5c:** the baseline is read at turn 1's first `session/update`, absent (not 0) when none; a helper spawned after the first prompt is not counted as a leaked job (rev 6.2's test).
4. **One count, one name:** if `job_active_after` is the count `job_active_processes` named, rename it; never both with one meaning.
5. Campaign plan exit evidence for X-J1 (all of it) and the Wave 1 testability floor; a mutant per adjacent rule pair in `tests/mutations/{engine,driver}.json`.

## Exit
E1 README §3 join gate per dispatch; served model from the Codex native record. Report per E1 README §4.
