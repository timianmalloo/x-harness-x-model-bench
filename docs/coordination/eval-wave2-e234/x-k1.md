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

**Design:** W1-K (once gated); ADR-0021; W0 rev 6.6 §4 (X-K1 sweeps the archive root and each `archive/<cell id>/` under the run lock, with the wrong-pairing red test; `recover_archive` built here, calling `archive.append_missing_rows`), §11 (HB-CELL-118, HB-CELL-119, HB-RUN-008, HB-RUN-009; HB-RUN-004 and HB-RUN-005 reused), §12 (`free_bytes` on `cell.launch_intent`; the resume record; rev 6.9 `resume.has_work`, R-102), §13 (rev 6.9: the `cmd_run` hunk).

## Owned paths (E3 hub owner)
`resume.py` (new, run class), `engine.py` (E3), `errors.py` (E3), `identity.py` (E3), `lifecycle.py` (E3), `archive.py` (`recover_archive` only), `views.py` (`segment_rows`, `completed`, the verify abandoned-head rule; W0 rev 6.8 §13), `cli.py` (E3, **one hunk only**: the `cmd_run` resume branch, `cli.py:157-158` on `c2d8874b`, the HB-USR-002 "already started" refusal replaced by the delegation to `resume.resume_run`, in its own commit; W0 rev 6.9 R6.9a, RV-TA W1-K 3, RV-PAT W1-K 1; every other `cli.py` line is X-K2's), `docs/design/run-lifecycle-model.md` and `models/README.md` (the W1-K §8 rows), `tests/test_resume.py` (new), `tests/test_engine.py` (E3).

## Acceptance items (campaign plan; refined by W1-K)
1. Kill in each state, then resume, for **every row of ADR-0021 §4**, including the per-turn rows and the turn-1 snapshot-crashed row.
2. A resume after a stop finishes the stop and exits 3 with HB-RUN-008 (R-100; ADR-0021 Amendment 1); refusals for a live lock (HB-RUN-005), a drifted identity (HB-IDN-001) and a failed verify (HB-RUN-009, naming the segment); `segment.abandoned`; the per-launch disk check (ADR-0021 §8, HB-RUN-004, `free_bytes`).
3. `recover_archive` holds no second comparison: it returns W1-B's `Recovery(result, missing_rows)` from `append_missing_rows` (DM7).
4. **The real-CLI kill tests go green at this join** (W0 rev 6.9 R6.9a): W2, W3, W3b, W6, W11 and `test_resume.py::test_cli_run_resumes[T2]` drive the real `cli.py run <run_id>` through X-K1's `cmd_run` hunk; deleting the delegation turns `test_cli_run_resumes` red.
5. **One definition of work left** (R-102; W0 rev 6.9 §12 R6.9b): `resume.has_work(plan, rows)` in `resume.py`, the negation of W1-K §3.1 step 4, with the stop row inside it (D-K4); `alarm.py` (X-K2) and `bench status` import it. Red first: `test_finished_stop_is_silent` (a C7 cell in the fixture), `test_alarm_fires_after_crash_in_grading`, `test_alarm_fires_after_crash_before_last_archive`, `test_launch_stop_alarms`. No stored `not_launched` outcome.
6. The resume-owned model branches marked provisional in W1-J (`BetweenSnapped`, `ClassOf`'s else-branch) are settled by W1-K's TLC, not here.

## Turn split (Coordinator #39, 2026-10-06; from W1-K section 13's commit order and section 4's test map)

Both blocks are cleared: W1-K gated (`7e96eee3`), X-J1 joined (J1e `1a837a5d`). Each turn compiles at its predecessor's join. "W1-K Kn" below is W1-K section 13's commit item, not a compile K-item.

| turn | W1-K items | hand-back point |
| --- | --- | --- |
| K1a | W1-K K1 (skeleton `resume.resume_run` raising today's HB-USR-002, a `has_work` skeleton, the `cmd_run` delegation in its own commit, the `resume.py` `PLANNED` key deleted) with the confirmed `errors.py` rows (W0 section 11, registry first); W1-K K2 (`tests/test_resume.py` and the golden-ledger helper, every section 4 node id red on its own assertion, strict-xfail with a reason naming the turn that turns it green) | after W1-K K2 (the turn's end) |
| K1b | W1-K K3 (`lifecycle.py`, the `views.py` hunks, the abandoned-head verify) and W1-K K4 (`classify`, `stop_recorded`, `has_work`; the five classifier mutants run once) | after K3 unless at or below 100k |
| K1c | W1-K K5 (`recover_archive`, sweeps, the refusals with step 3(c)) and W1-K K6 (the `Engine` resume path, `open_engine_segments`, rebuilt run-level state, the heartbeat, the creation-time pid check, the stopped tail) | after K5 unless at or below 100k |
| K1d | W1-K K6b (the disk check in `_launch`, own commit), W1-K K7 (model-docs rows), `tests/mutations/resume.json` (section 4 (d)), the exit-evidence table | after K6b unless at or below 100k |

**`errors.py` rows in K1a:** HB-CELL-118, HB-CELL-119, HB-RUN-008 (the rev 6.8 text: the exit-3 reason), HB-RUN-009, HB-ALM-001, HB-ALM-002.

**Not added:**
- HB-ALM-003: W1-K sections 6.2 and 9 defer it to E5, and its W0 reservation stands.
- HB-PLN-003: X-A3b landed it under #34's pre-grant (`errors.py:53`).
- HB-PLN-005: retired by X-A3c.

## Exit
E1 README §3 join gate per dispatch; served model from the Codex native record. Report per E1 README §4.
