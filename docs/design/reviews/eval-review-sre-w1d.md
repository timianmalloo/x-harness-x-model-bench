---
id: review-eval-sre-w1d
title: "W1-D engine identity design review: SRE lens"
type: doc
status: draft
owner: "@timianmalloo"
phase: "Enterprise evaluation: Wave 1 gate reviews"
tags: [review, sre, evaluation-campaign, wave-1, w1-d]
links:
  - { to: design-eval-seam-contracts, rel: relates-to }
review-by: "2026-10-17"
summary: >-
  SRE (Adversary Mode) review of W1-D at 71a15a0b. The per-launch recheck is measured on the right row and fails closed,
  but it runs synchronously on the supervisory loop with unbounded retries, the stop is not actionable from bench status,
  and torn-read recoveries and the grading interpreter are not recorded. PASS WITH CONDITIONS.
---

# W1-D engine identity: SRE review

Target: `docs/design/eval-identity.md` on `design/eval-identity` (71a15a0b). Against W0 rev 2 s6/s12, ADR-0017 s7, R-87..R-93. The Test Architect's findings (wiring, G2 fixtures, assertions) are not repeated. `telemetry/*` is provisional.

Answers: measurable by default, yes for latency (`identity_check_ms` on the launch and stop rows, absent not 0). Not yet for false alarms, cold start and the grading interpreter. Failures stop loudly in the ledger, but not at the operator's console (finding 2).

| # | location | finding | severity | evidence | fix | confidence |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 5 "Where", 7 locked file | The check runs inline in the supervisory loop, before `_launch`, inside `while pending ... held < parallelism`. The same loop does `on_tick`, sleep detection, disk-floor and kill handling. Each launch in a tick pays one check (two on a torn read), and the per-file retry (3 x 50 ms) is unbounded in files: one AV scan holding many files costs seconds with no tick. A cold first launch is unmeasured (I). | major | `engine.py:395-407` (loop body); design 5 Budget "first launch is cold (not measured, I)"; 7 row 1 | State a wall-clock bound on the whole check (for example 2 s, then `<n> unreadable`, stop), and state it runs once per tick, not once per launch in that tick. Say the lost tick time is accepted at 13 ms and name the p95 as a per-tick stall. | Verified (loop); Inferred (AV cost) |
| 2 | 5, 9 projection row, 14 F-2 | `HB-IDN-001` is the one stop an operator must act on (restore or record a fix), and `bench status` shows only the code. `Status.stop_code` carries no reason or diff (`status.py:89,160`). The design rates this "low". Stopping a campaign run with no actionable text at the console is **major**: the operator reads the raw ledger. | major | `status.py:89,160-161` (code only); design 14 F-2 | Either X-C prints the last `run.launch_stopped.reason` plus up to N `diff` items under `stop_code`, or the design makes the CLI exit text (`exit 3`) carry them. Name the owner and add a test; do not leave as a finding. | Verified |
| 3 | 5 torn read, 7 row 2 | The second read is immediate. A writer mid-rewrite (a merge, a formatter) is usually still writing 0 ms later, so the recheck proves little; and a recovered torn read is not recorded, so "how often does the recheck save a false stop" cannot be answered. | minor | design 5 "call it once more"; 11 table has no such question | Short fixed pause (50 ms, same `simplify:` marker) before the second read; write `identity_recheck: true` on the launch row when the second read was needed. | Inferred |
| 4 | 5 `identity_check_ms` | Not stated whether the value covers both reads, nor that the cold first row is flagged. Median/max "from the rows" mixes the cold row in; the budget is p95 warm. | minor | design 5, 11 | Define: total wall time of `_identity_ok()`; `identity_check_first: true` (or first row of the run by rule) is excluded from the warm p95. The E1 demo reports both. | Verified |
| 5 | 5 "What is rechecked" | `builds/<h>` is taken from `plan["builds"]`, so inside `launch_check` it compares the plan to itself and can never differ. Coverage is the real per-cell `check_build`, which stops with a different code (`Cause.build_changed`, via `request_stop`) and, being per cell, lets already-launched cells on a swapped binary run to their own check. Not wrong, but the design implies the manifest covers builds. | minor | `engine.py:624-630`; design 3.2 `builds/<h>` row | Say plainly that `builds/<h>` is a plan-consistency key only, and that an executable change surfaces as `build_changed`, not `HB-IDN-001`. Add it to the operator table in finding 2. | Verified |
| 6 | 4.2 residual, 11 | A re-grade on another interpreter or OS is not flagged (`python`/`platform` are run-only) and nothing records which interpreter graded. If a graded value does depend on it, the verdict silently differs and no row shows it. | minor | design 4.2 "Residual (accepted, I)"; 6 | Cheap and measurable: write `python` (3.x.y) and `platform` as plain fields on `grading.started` beside `grade_identity_hash`, not in the hash. The trigger "any graded value differing" then has a data source. | Verified (gap) |
| 7 | 5 stop semantics | `_stop_launching` is first-wins. A drift detected while an earlier stop (disk floor, circuit breaker) already holds is silently dropped from the record. | minor | `engine.py:440-443` | When `stopped` is already set, still append the diff on a `run.identity_drift` note, or document the loss; the next run then stops at launch 1 anyway. | Verified |
| 8 | 5 budget, 11 | The p95 budget has a source (rows) but no consumer: nothing reads the rows after E1, so a drift toward 250 ms on a slower host is unseen. TA 7 covers the gate; this is the operational half. | minor | design 5 "a breach is a finding, not a gate" | Have `bench status` or the campaign report print median and max `identity_check_ms` for the run. One line; no new instrument. | Inferred |

Seams: none found. W0 s12 "launch span" = `cell.launch_intent` (design 5) agrees with W0; the `run.launch_stopped` extra fields agree with `status.py` reading by kind only.

Clearing conditions: 1 and 2 before X-D builds. 3 to 8 may be recorded as next steps or folded in.

`GATE W1-D · SRE · PASS WITH CONDITIONS · 8 findings (rv-sre-e1e4, 2026-10-03)`
