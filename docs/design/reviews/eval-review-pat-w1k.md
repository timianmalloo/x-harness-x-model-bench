---
id: review-eval-pat-w1k
title: "Patterns Expert review of W1-K, resume, liveness and the alarm (Adversary Mode)"
type: doc
status: draft
owner: "@timianmalloo"
tags: [review, patterns-expert, evaluation-campaign, wave-1, w1-k]
links:
  - { to: design-eval-seam-contracts, rel: relates-to }
review-by: "2026-10-17"
summary: >-
  RV-PAT review of design/eval-resume rev 1.1 (315cf1d4) against W0 rev 6.8, R-100 and ADR-0021 with Amendment 1.
  The reconcile-from-log and the one-input classifier are sound; one seam defect (X-K1 cannot reach its own tests),
  one contradiction (a finished stop still alarms), and five smaller pattern gaps. No pattern is named in the doc.
---

# RV-PAT review: W1-K `docs/design/eval-resume.md` rev 1.1 against W0 rev 6.8, R-100, ADR-0021 + Amendment 1

Read in full from `C:\Projects\x-harness-x-model-bench-design-eval-resume` at 315cf1d4; W0, ADR-0021 and R-100 read from `main` at ef4e86dc; `cli.py` and `engine.py` opened on `main`. Session `rv-patsim-w1k-e1e4`, 2026-10-03.

**Pattern verdicts.**
1. Resume as reconcile-from-log: the right idiom (write-ahead-log recovery plus a reconciliation loop: the ledger is the state, `classify` is the diff, the executor applies idempotent actions; W13 and W14 are the idempotence proof).
2. Classifier as one input: a pure decision table, first match wins, one extra boolean (Specification / Special Case). It is not a second table, so R-100 condition 3 is met.
3. Dead segments fenced, never reopened (`segment.abandoned` pins `head_hash`): the standard fencing move.
4. Alarm: a Watchdog polled from outside the process. Standard idiom.

The doc names none of these patterns (finding 5).

| # | location | finding | severity | evidence | fix | confidence |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | section 12 X-K1/X-K2 seam, section 4 (c), section 13 vs W0 rev 6.8 R6.8a | **Seam defect.** X-K1 lands `resume_run` as a skeleton that raises `HB-USR-002`, but the call site (`cmd_run`) is X-K2's second dispatch. Until X-K2 replaces `cli.py:157-158`, the real `cli.py run <run_id>` raises before it reaches `resume_run`. Every T2 test (W2, W3, W3b, W6, W11 and `test_cli_run_resumes`) drives the real CLI, so none can go green at X-K1's join. Yet "X-K1's crash-window tests are the gate's entry condition for X-K1". The doc states both facts and does not see the clash. | blocking | design lines 144, 146, 176, 366, 380-381; `cli.py:157-158` (the `events` guard fires first) | Move the one `cmd_run` hunk to X-K1 (a three-line delegation that a non-fake test needs). X-K2 keeps the alarm, `status`, `cmd_plan` and the runbook. If the seam must stay, X-K1's T2 tests start the child through `python -c "...resume_run..."` and only `test_cli_run_resumes` waits for X-K2. Say which in section 12. | Verified |
| 2 | section 6.2 vs section 3.2 C7 and section 3.1 step 4 | **Contradiction.** The alarm defines pending as "plan cells with no `cell.outcome`" and says a finished stop is silent because no cell is pending. But C7 (never launched) takes no action under a stop, so those cells stay unrecorded after the finish-the-stop resume. A stop with any unlaunched cell then leaves the lock free and pending > 0: `HB-ALM-001` fires every 15 minutes for the rest of the window. `test_finished_stop_is_silent` passes only if its fixture holds no C7 cell. | blocking | design lines 118, 283, 291, 383; R-100 condition 6 rests on the same premise | Define "pending" for the alarm as: a cell with `launch_intent` and no outcome, or a cell with no `launch_intent` while no stop row exists. Put a C7-under-stop cell in the `test_finished_stop_is_silent` fixture so the test is red today. Tell the Coordinator that R-100 condition 6 holds only with that definition. | Verified (text); engine side Inferred |
| 3 | section 6.3, wrapper | **Alert fatigue, no edge.** The wrapper is stateless: while a condition holds it raises a persistent toast and a high-priority push every 15 minutes all night. The idiom is to alert on the transition (or back off) and recover quietly. | major | design lines 299, 309 | Cheapest: ntfy sequence id so the phone keeps one entry per run and code. Or one state file beside `.alarm_check` holding the last alerted code. Test in `-DryRun`. | Inferred |
| 4 | section 6.3 "Alarm of the alarm" | The stamp is written by the thing it watches and read only when a human runs `bench status`. It finds a disabled task only for an operator who looks. ADR-0021 section 7 accepted this; the doc should call `HB-ALM-003` a lint, not a watchdog. The standard idiom (an external dead-man's switch) needs a third party and belongs with the E5 drill. | minor | design line 313; ADR-0021 section 7 residual | Reword the row; link it to the E5 open item (line 371). | Verified |
| 5 | whole doc | No pattern is named, which the Rigor Protocol asks for. | minor | design sections 1-3 | Add a four-line table in section 1: reconciliation loop / WAL recovery (resume), Decision Table + Special Case (classifier), Idempotent Receiver (W13, W14), Fencing (abandoned marker), Watchdog (alarm). | Verified |
| 6 | section 3.2 vs R-100 condition 3 | R-100 writes `classify(plan, rows)` reading the predicate itself; the design passes `stopped` as a third parameter. The design is better (one call to `stop_recorded`), but the ruling and the signature now differ. | minor | design lines 101, 107; R-100 condition 3 | One sentence in 3.2: "the flag is computed once in step 3 and passed in; R-100 condition 3 holds". | Verified |
| 7 | section 3.1 step 5 vs `engine.py:376` | Two writers create the three engine segments (`Engine.run`'s `FACTS` loop and `resume_run` step 5) under a new id rule (D-K7). Without one factory the id format drifts. | minor | `engine.py:49,376`; design lines 61, 99 | One `open_engine_segments(run_dir, ordinal)` used by both (commit K6); the existing `FACTS` sweep tests it. | Inferred |

Seam disagreements named: finding 1 (design section 12 against W0 rev 6.8 R6.8a, which grants the hunks but does not say which commit can be tested); finding 2 (design section 6.2 against R-100 condition 6 and ADR-0021 Amendment 1).

GATE W1-K · Patterns Expert · PASS WITH CONDITIONS · 7 findings (rv-patsim-w1k-e1e4, 2026-10-03)

Conditions: findings 1 and 2 fixed before the gate record is copied; the rest is advice.
