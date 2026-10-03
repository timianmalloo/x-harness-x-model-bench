---
id: brief-eval-x-k2
title: "Brief X-K2: liveness and the alarm (E3 build) - BLOCKED on W1-K"
type: plan
status: proposed
owner: "@timianmalloo"
links:
  - { to: coordination-eval-wave2-e234-briefs, rel: implements }
  - { to: design-eval-seam-contracts, rel: depends-on }
review-by: "2026-10-17"
summary: "X-K2 builds bench status --alarm-after, last_progress_at, the alarm channel W1-K chooses, and the resume entry line in cli.py, on Agy gemini-3.8-flash-high in two turns. Blocked until W1-K passes its gate."
---

# X-K2: liveness and alarm

> **BLOCKED** on W1-K passing its gate (W1-K chooses the alarm channel, ADR-0021 §7, and fixes the runbook path). Also waits on X-C (E1 `status.py`, `cli.py`) and X-J1 (its one `status.py` hunk, W0 rev 6.5 R6.5b) joined. Does not wait on X-K1.

**Harness** Agy, `gemini-3.8-flash-high` · **contract** `x-k2.contract.json` · **deadline** 3,300 s per dispatch · **budget** 140 calls · 150k · 2 dispatches · 2 h · **fallback** a Sonnet follow-on in the same tree (R-87 Option 1).

**Design:** W1-K (once gated); ADR-0021 §7; W0 rev 6.6 §9 (`alarm.py`: grade), §10 (the alarm guard row), §11 (HB-ALM-001..003), §13.

## Owned paths (E3 hub owner)
`status.py` (E3), `cli.py` (E3, including the `bench run <run_id>` resume entry line X-K1 needs), `alarm.py` (new), the runbook entry (path fixed in W1-K), `tests/test_status.py` (E3), `tests/test_alarm.py` (new).

## Acceptance items
1. ADR-0021 §7, quoted: "`bench status <run_id> --alarm-after <seconds>` exits non-zero, naming the cause, when the heartbeat is stale **or** `now − last_progress_at` exceeds the threshold while cells are pending": the stale-progress fixture exits non-zero (HB-ALM-001, HB-ALM-002); the `last_alarm_check_at` warning (HB-ALM-003).
2. `last_progress_at` and elapsed read through X-J1's one "cell start" definition (R6.5b); no second clock.
3. The alarm channel built as W1-K chose it; the drill is out of scope.

## Exit
E1 README §3 join gate per dispatch; served model from Agy's `cli.log`. Report per E1 README §4.
