---
id: brief-eval-x-k1
title: "Brief X-K1: resume in the engine (E3 build) - BLOCKED on W1-K and X-J1"
type: plan
status: proposed
owner: "@timianmalloo"
links:
  - { to: coordination-eval-wave2-e234-briefs, rel: implements }
  - { to: design-eval-seam-contracts, rel: depends-on }
review-by: "2026-10-17"
summary: "X-K1 builds plan-level resume (ADR-0021) on Codex gpt-6.1-sol in four turns. Blocked until W1-K passes its gate and X-J1 has joined (serial spine 6). The Coordinator writes the turn split from W1-K's test map."
---

# X-K1: resume (engine)

> **BLOCKED** on (1) W1-K (`docs/design/eval-resume.md`, not yet written; brief `w1-k.md`) passing its gate, and (2) **X-J1 joined** (serial spine 6: one `engine.py` author at a time; K's per-turn reconciliation rows read J's `turn_ended`, `turn_snapshot_archived` and `prompt_sent`). When both hold, the Coordinator writes the turn split from W1-K's test map and compiles X-K1a.

**Harness** Codex via `coord-runner`, `gpt-6.1-sol`, effort high · **contract** `x-k1.contract.json` · **deadline** 3,300 s per dispatch · **budget** 280 calls · 200k · 4 dispatches · 4.5 h · **fallback** a Sonnet follow-on in the same tree (R-87 Option 1).

**Design:** W1-K (once gated); ADR-0021; W0 rev 6.6 §4 (X-K1 sweeps the archive root and each `archive/<cell id>/` under the run lock, with the wrong-pairing red test; `recover_archive` built here, calling `archive.append_missing_rows`), §11 (HB-CELL-118, HB-CELL-119, HB-RUN-008, HB-RUN-009; HB-RUN-004 and HB-RUN-005 reused), §12 (`free_bytes` on `cell.launch_intent`; the resume record), §13.

## Owned paths (E3 hub owner)
`resume.py` (new, run class), `engine.py` (E3), `errors.py` (E3), `identity.py` (E3), `lifecycle.py` (E3), `archive.py` (`recover_archive` only), `tests/test_resume.py` (new), `tests/test_engine.py` (E3).

## Acceptance items (campaign plan; refined by W1-K)
1. Kill in each state, then resume, for **every row of ADR-0021 §4**, including the per-turn rows and the turn-1 snapshot-crashed row.
2. Refusals after a stop (HB-RUN-008), a live lock (HB-RUN-005), a drifted identity (HB-IDN-001) and a failed verify (HB-RUN-009, naming the segment); `segment.abandoned`; the per-launch disk check (ADR-0021 §8, HB-RUN-004, `free_bytes`).
3. `recover_archive` holds no second comparison: it returns W1-B's `Recovery(result, missing_rows)` from `append_missing_rows` (DM7).
4. The resume-owned model branches marked provisional in W1-J (`BetweenSnapped`, `ClassOf`'s else-branch) are settled by W1-K's TLC, not here.

## Exit
E1 README §3 join gate per dispatch; served model from the Codex native record. Report per E1 README §4.
