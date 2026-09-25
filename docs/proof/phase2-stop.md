---
id: "proof-phase2-stop"
title: "Proof Pack: STOP-I (row 10 - stop, decisions, spend cap, circuit breaker)"
type: proof-pack
status: draft
owner: "@timianmalloo"
phase: "Phase 2 · W2-STOP-I slice 6 (the proof pass)"
tags: [proof, phase2, stop-i, red-first, mutation, tla, join-ready]
links:
  - { to: proof-phase2, rel: relates-to }
  - { to: design-phase2-stop-decisions, rel: implements }
review-by: "2026-10-09"
summary: >-
  W2-STOP-I's join evidence (design section 21's Test Architect conditions): every tests/mutations/{engine,driver,
  status,cli,plan,stop}.json mutant observed red on its named test (172/172 killed, two stale-find and one
  wrong-target survivor found and fixed in this slice), R10-1 red on the hard-floor mutant with a clean measured
  stop time (10.03 s), the full check_models.py output (22/22 seeded variants rejected, 2/2 witnesses violated, the
  US-44 bounds safety run passed), the plan `:145` Stop/Race/US-15 clauses mapped to their tests, and the
  test_correctness_dotnet.py timeout test's flake diagnosed (Inferred; not reproduced under measured load). The
  default suite passes and ruff is clean.
---

# Proof Pack: W2-STOP-I slice 6 (the proof pass)

Scope: `docs/design/phase2-stop-decisions.md` section 17 row 6, under rulings R-3, R-49, R-50. This slice runs the
existing checks slices 1-5 built and writes this note; no new feature. Not in scope: `plan.py` and `cli.py`
production code (W3-GRADE-CORE slice 2 owns those seams now), `views.py`, the TLA model beyond running
`check_models.py`, `docs/proof/phase2.md` itself (the Leader folds these figures in).

## 1. Mutation pass: `uv run python tools/mutate_check.py <file>`, one file at a time

| file | entries | result | fixed in this slice |
| --- | --- | --- | --- |
| `tests/mutations/driver.json` | 5 | every mutation killed | - |
| `tests/mutations/status.json` | 12 | every mutation killed | - |
| `tests/mutations/plan.json` | 13 | every mutation killed | - |
| `tests/mutations/cli.json` | 12 | every mutation killed (was 11/12: 1 survived) | yes, see 1.1 |
| `tests/mutations/engine.json` | 49 | every mutation killed (was 43/49: 5 SKIP, 1 survived) | yes, see 1.2 |
| `tests/mutations/stop.json` | 74 | every mutation killed | - |
| **total** | **165 named mutants + a 6th SKIP-fix and a re-fix (T1-1)** | **every mutation killed** | |

No stale `find` text was deleted; each is re-pointed to the current line, same guard, same named test (TA M4:
"a named killer for every mutant").

### 1.1 `cli.json` survivor: "a started run re-run"

`test_run_refuses_a_run_that_already_started`'s plan fixture (`archived_runs.make_run`) carries only two of
`plan.DEFAULT_PARAMETERS`' twelve keys. `plan.require_run_parameters(p)` — checked in `cmd_run` *before* the
`(run_dir / "events").exists()` guard under test — raised `HB-USR-002: old plan missing parameters [...]` for an
unrelated reason, so the test passed whether or not the guard fired. Confirmed by instrumentation (`preflight.check`
spied on: 0 calls either way, and the un-mutated baseline's own stderr read `old plan missing parameters [...]`, not
`has already started`).

Fix (`tests/test_cli.py`, commit `4497a9a`): fill the plan's `parameters` from `DEFAULT_PARAMETERS` (recomputing
`plan_hash`) so the test reaches the real guard, and spy on `preflight.check` (called only after the guard) so the
assertion is pinned to `cli.py`'s own early-exit, not engine.py:372's later, redundant `HB-USR-002` check for the
same condition.

- Red first (mutant `"a started run re-run"` hand-applied to `src/harness_bench/cli.py`, then reverted):
  `tests/test_cli.py::test_run_refuses_a_run_that_already_started` — `KeyError: 'tasks'` at `cli.py:153` (the mutant
  falls through the bypassed guard into code that assumed it had already returned).
- Green: same test, unmutated code, 1 passed.
- `mutate_check tests/mutations/cli.json`: 12/12 killed (was 11/12).

### 1.2 `engine.json`: five stale finds, one wrong-target survivor

`tests/mutations/engine.json` had drifted from `src/harness_bench/engine.py` across STOP-I slices 1-5 (signatures
and guard shapes changed). Five `find` texts no longer matched anything (`SKIP: text not found`); a sixth matched,
but the *wrong* occurrence.

| mutant | was | cause | re-pointed to |
| --- | --- | --- | --- |
| "record the outcome before the process is confirmed gone" | SKIP | `_end_process(cp)` grew a 3rd return (`ended_by`) and 2 new params | `engine.py:727`, same guard |
| "budget never enforced" | SKIP | `_check_budgets()` grew a `now` param | `engine.py:548` |
| "T1-1 a turn that has ended is still killed by its budget" | SKIP, then wrong target | the single-line guard moved; first repoint targeted `_check_kills`'s escalation `continue` (survived — wrong method) | `_kill()`'s own `if a.ended or a.kill_reason: return` (`engine.py:539-540`) |
| "T1-2 seed before argv_env" | SKIP | `argv_env(cell, ...)` -> `argv_env(argv_cell, ...)` (scripted-user Copilot handling); comment reworded | `engine.py:641-643`, same swap |
| "T1-15 the job is not ended at end_turn" | SKIP | `_confirm(...)` call gained a `not active or` short-circuit | `engine.py:760` |
| "T1-12 a failed stderr-tail write costs the cell" | survived | the generic `except OSError as exc:\n    log.warning(` find matched the *first* such pair in the file (the control-file reader, `engine.py:466-467`), not the stderr-tail writer (`:675-676`) the named test targets | anchored on the tail-specific log text (`"adapter stderr tail not kept"`), unique in the file |

Each repoint was verified red first (the corrected mutant hand-applied, the named test observed failing) then
restored and re-verified green via `mutate_check`. The first T1-1 repoint attempt (targeting `_check_kills`)
survived on its own re-run and was corrected before commit — recorded here rather than silently dropped.

- Red, T1-1 (corrected mutant): `tests/test_engine.py::test_a_budget_expiring_after_the_turn_ended_is_not_a_timeout`
  — `AssertionError: assert ('timed_out', ..., 'timed_out') == ('completed', ..., None)`.
- Red, T1-12 (corrected mutant): `tests/test_engine.py::test_the_outcome_is_recorded_before_the_best_effort_files`
  fails when `IsADirectoryError` (an `OSError` subtype the narrowed `except FileNotFoundError` does not catch)
  propagates out of the stderr-tail write.
- Green (commit `ae9944d`): `mutate_check tests/mutations/engine.json`: 49/49 killed.

## 2. `stop.json`: every mutant, its named test

All 74 killed. (`M` = mutant name, `T` = the test file's `::test_...` that failed it; file omitted, all in
`tests/test_engine.py` unless noted.)

| mutant | named test |
| --- | --- |
| operator stop code omitted | `test_errors.py::test_stop_and_spend_cap_have_the_designs_run_codes` |
| spend cap stop code omitted | `test_errors.py::test_stop_and_spend_cap_have_the_designs_run_codes` |
| decision skip omitted from skill | `test_status.py::test_the_skill_names_every_status_field` |
| decision timeout default changed | `test_plan.py::test_stop_parameters_are_frozen_with_the_ruling_units` |
| spend cap shown in dollars instead of total tokens | `test_cli.py::test_plan_flags_and_confirmation_name_the_timeout_and_token_cap` |
| row15 parallelism cap reverted to two | `test_plan.py::test_row15_supports_parallelism_four_and_refuses_five` |
| old plan reaches engine without parameter check | `test_cli.py::test_bench_run_refuses_a_confirmed_old_plan_before_starting` |
| last update value discarded from status | `test_status.py::test_last_update_is_reported_for_timed_out_and_stopped_cells` |
| package label guessed as ACP agent version | `test_tools.py::test_resolve_names_version_executable_adapter_and_hash` |
| decision skip absent from status enum | `test_status.py::test_stopped_and_decision_skip_are_closed_outcomes` |
| breaker threshold raised to four | `test_the_circuit_breaker_fires_at_its_threshold_not_before` |
| breaker threshold lowered to two | `test_the_circuit_breaker_fires_at_its_threshold_not_before` |
| breaker success no longer resets streak | `test_a_success_resets_the_infrastructure_streak` |
| breaker counts harness failures | `test_harness_failures_do_not_trip_the_breaker` |
| breaker neutral stopped guard removed | `test_neutral_outcomes_neither_count_nor_reset[stopped-None]` |
| breaker neutral decision skip guard removed | `test_neutral_outcomes_neither_count_nor_reset` |
| breaker neutral outcome guards removed | `test_neutral_outcomes_neither_count_nor_reset` |
| breaker counts model unavailable | `test_neutral_outcomes_neither_count_nor_reset[...]`, `test_model_unavailable_alone_does_not_count_toward_the_breaker` |
| breaker repeats launch stop | `test_the_circuit_breaker_stops_launching_once` |
| breaker kills running cells | `test_the_breaker_leaves_running_cells_running` |
| power request released at launch stop | `test_keep_awake_is_held_through_a_stop` |
| power release moved out of finally | `test_keep_awake_is_released_when_the_run_raises` |
| prompt sent after cancel races the send | `test_driver.py::test_the_channel_drops_a_prompt_if_cancel_races_the_send` |
| writes not dropped after cancel | `test_driver.py::test_writes_after_a_cancel_are_dropped` |
| grace above ten seconds accepted | `test_profiles.py::test_shutdown_grace_is_a_bounded_profile_datum_and_reaches_launcher` |
| kill before the grace ends | `test_engine_kill_deadline_uses_one_injected_clock` |
| hard kill retry suppressed while the job lives | `test_hard_kill_retries_until_the_job_is_empty` |
| a control file applied twice | `test_control_file_is_applied_once_even_if_delete_fails` |
| a second stop applied again | `test_a_second_stop_is_recorded_as_a_no_op` |
| a cell spawned after the stop | `test_a_stop_after_the_build_check_is_caught_at_the_spawn` |
| a stop during the build reaches the seed | `test_a_stop_during_the_build_never_spawns` |
| a spawn that raced the stop is not terminated | `test_a_stop_during_the_spawn_terminates_at_once` |
| the grace skipped on stop | `test_an_operator_stop_gives_the_grace_before_the_kill` |
| run.stopped not recorded | `test_a_second_stop_is_recorded_as_a_no_op` |
| run.stopped skipped when launching was already stopped | `test_a_stop_after_the_breaker_is_still_a_run_stop` |
| **the hard floor removed (R10-1)** | **`test_stop_ends_stubborn_trees_within_30s`** — see section 3 |
| the final control pass after grading removed | `test_a_late_control_is_recorded_not_lost` |
| stop precedence dropped | `test_stop_outranks_a_provider_error` |
| the ended guard dropped from the kill | `test_an_ended_turn_keeps_its_outcome_under_a_stop` |
| power request released at an operator stop | `test_keep_awake_is_held_through_an_operator_stop` |
| a stopped run exits 0 | `test_a_stop_during_the_build_never_spawns` |
| a control append failure raises out of the run | `test_a_failed_append_of_a_control_row_ends_the_run_incomplete_not_raised` |
| a malformed control file not quarantined | `test_a_malformed_control_file_is_quarantined` |
| an unreadable control file raises | `test_a_control_file_that_cannot_be_read_is_retried_next_tick` |
| stopped phase absent from status | `test_status.py::test_status_shows_stopped_with_counts` |
| stopping phase never shown | `test_status.py::test_status_shows_stopping_while_a_launched_cell_has_no_outcome` |
| bench stop writes in place | `test_cli.py::test_stop_writes_an_atomic_control_file` |
| bench stop accepts a run that is not running | `test_cli.py::test_stop_refuses_unknown_and_unlocked_runs` |
| replay accepts a control applied twice | `test_lifecycle_conformance.py::test_each_seeded_out_of_order_ledger_is_rejected_under_its_rule` |
| replay accepts a run stopped twice | `test_lifecycle_conformance.py::test_each_seeded_out_of_order_ledger_is_rejected_under_its_rule` |
| a decision resolved twice (the _resolve guard removed) | `test_decision_resolves_exactly_once_in_every_order` |
| the decision guard after a launch stop removed | `test_no_decision_after_a_launch_stop` |
| the decision guard with nothing pending removed | `test_no_decision_after_a_launch_stop` |
| the cap not disabled on continue | `test_continue_on_the_spend_cap_disables_the_cap` |
| the supersede loop skipped | `test_a_stop_supersedes_every_open_decision` |
| SPEND null counted as 0 | `test_a_cell_with_no_usage_is_unmeasured_never_zero` |
| the expiry runs before the controls | `test_resolution_order_through_the_loop` |
| a launch while a decision is open | `test_blocked_cell_default_continues_after_the_timeout` |
| the loop ends with a decision open | `test_the_run_waits_for_an_open_decision` |
| skip_combo skips nothing | `test_qualification_gap_default_skips_the_combos_pending_cells` |
| an answer of stop not applied | `test_an_answer_of_stop_is_an_operator_stop` |
| a spend-cap stop recorded as an operator stop | `test_spend_cap_default_stops_the_run` |
| a blocked cell keyed by the cell, not its harness | `test_one_blocked_harness_opens_one_decision` |
| bench answer accepts an option the decision does not offer | `test_cli.py::test_answer_refuses_what_the_engine_could_not_apply` |
| bench answer accepts a resolved decision | `test_cli.py::test_answer_refuses_what_the_engine_could_not_apply` |
| bench answer writes in place | `test_cli.py::test_answer_writes_an_atomic_control_file` |
| status time to default goes negative | `test_status.py::test_status_carries_each_decision_and_its_time_to_default` |
| status accepts a free-string decision subject | `test_status.py::test_a_decision_carries_no_free_string` |
| status accepts options outside the decision's kind | `test_status.py::test_a_decision_carries_no_free_string` |
| replay accepts a launch while a decision is open | `test_lifecycle_conformance.py::test_each_seeded_decision_ledger_is_rejected_under_its_rule` |
| replay accepts a decision resolved twice | `test_lifecycle_conformance.py::test_each_seeded_decision_ledger_is_rejected_under_its_rule` |
| replay accepts a decision after the run stopped | `test_lifecycle_conformance.py::test_each_seeded_decision_ledger_is_rejected_under_its_rule` |
| replay refuses a skipped cell's first row | `test_lifecycle_conformance.py::test_a_skipped_cells_outcome_is_its_first_and_only_row` |
| the answer command dropped from the skill | `test_status.py::test_the_skill_names_every_status_field` |

`74/74 killed` (`mutate_check` exit 0), run once concurrently with the `check_models.py` TLC process (see section 4)
and re-checked line-by-line above against that log — no survivor, no SKIP, no timeout despite the shared-machine
load (multiple other coordination tracks' processes were also running; TLC alone held ~40 GB RSS during the
US-44-bounds safety run).

## 3. R10-1: the hard-floor mutant, red, and the measured stop time

**Red** (`"the hard floor removed"`, `src/harness_bench/engine.py` — `a.terminated = True; _job_query(a.proc.job.terminate, None)`
replaced with `pass`, inside `mutate_check`'s temporary, auto-restored patch): `killed` — `test_engine.py::
test_stop_ends_stubborn_trees_within_30s` fails (the `_engine_run` limit is what fails it; the guard's absence is
never itself the observed red, per design M2).

**Measured stop time** (clean, isolated run — no concurrent load; `check_models.py` and `stop.json`'s mutation
pass had both finished): two stubborn cells, parallelism 2, `shutdown_grace=10`.

```
R10-1 measured: last cell.outcome{stopped} 10.03 s after control.applied; bench status showed stopped 10.33 s after the control file was written
```

8 passed (`test_stop_ends_stubborn_trees_within_30s` plus `test_check_models.py`'s 7). Both figures are well inside
the 30 s floor (design section 5); the worst-case grace configured for this test is 10 s.

## 4. `check_models.py` (full run), verbatim

```
ok   liveness                 real design, 58016 states, 5s
ok   grading                  real design, 17129408 states, 67s
ok   safety-small             real design, 4798704 states, 20s
ok   safety                   real design, 85060752 states, 422s
ok   witness                  NotAllCellsFinished violated (2s)
ok   grace-witness            NoGraceState violated (1s)
ok   relaunch_prompted        rejected by AtMostOnePrompt
ok   send_before_persist      rejected by AtMostOnePrompt
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
seeded variants: 22/22 rejected by own target
reachability witnesses: 2/2 violated
US-44 bounds: passed (3 cells, parallelism 2, 1 crash)
all model checks passed
```

**Summary line: `all model checks passed`** — 22/22 seeded variants rejected by their own registered target
(including `no_escalate` -> `StopReachesTerminal`, the S5 grant's addition), 2/2 witnesses violated (`witness` /
`NotAllCellsFinished` and `grace-witness` / `NoGraceState`, confirming the grace state is reachable and not
vacuous), and the real design's own safety run passed at the US-44 bounds (3 cells, parallelism 2, 1 crash;
85,060,752 states, 422 s). `tests/test_check_models.py` (the reverse-coverage test, TA M5b) is green — see section 3.
This clears design section 21's Test Architect condition N3 (both witnesses run inside the scripted `main()`) and
retires the confidence-ledger row "The stop fits in 30 s outside HB-RUN-002" from Inferred to Verified (measured,
section 3) and "The refinement... 22 of 22 variants are rejected" from Inferred (at the author's seat) to Verified
(this run).

(First attempt at this run was corrupted by an unrelated shell mistake — `check_models.py --help` piped through
`head -20`, which SIGPIPE'd the process after 20 of ~33 output lines. Discarded; the run above is the complete,
cleanly-redirected one.)

## 5. Plan `:145` clauses mapped to their tests

Verbatim row-10 exit conditions (`docs/coordination/coordination-finish-harness-bench.md:145`, design section 16.1):

| clause | tests | evidence |
| --- | --- | --- |
| **Stop:** a real process tree with a child that ignores termination is stopped within 30 s by the engine's clock, outcome `stopped` | `test_stop_ends_stubborn_trees_within_30s` (R10-1) | section 3: killed on the hard-floor mutant; 10.03 s measured, clean |
| **Stop:** any open decision becomes `superseded (stop)` | `test_a_stop_supersedes_every_open_decision` (R10-2) | section 2: killed |
| **Stop:** `bench status` shows `stopped` within 30 s (UXA-10) | `test_status_shows_stopped_with_counts` (R10-3); also asserted inside R10-1 (`shown <= 30`) | section 2 and 3: killed; 10.33 s measured |
| **Race:** both orderings are forced deterministically, each gives exactly one terminal decision state and one ledger event | `test_decision_resolves_exactly_once_in_every_order` (pure, 15 permutations; R10-4), `test_resolution_order_through_the_loop` (engine, incl. the same-tick case) | section 2: killed (`a decision resolved twice`, `the expiry runs before the controls`) |
| **US-15:** blocked -> continue after the timeout | `test_blocked_cell_default_continues_after_the_timeout` (US15-1) | section 2: killed (`a launch while a decision is open`) |
| **US-15:** qualification gap -> `skipped (decision)` | `test_qualification_gap_default_skips_the_combos_pending_cells` (US15-2) | section 2: killed (`skip_combo skips nothing`) |
| **US-15:** spend cap -> stop | `test_spend_cap_default_stops_the_run` (US15-3) | section 2: killed (`a spend-cap stop recorded as an operator stop`) |
| **Circuit breaker:** acceptance criterion, red-first test | design section 7 AC-CB-1..8; `stop.json`'s 10 `breaker *` / `power *` mutants | section 2: all killed, incl. N1's `model_unavailable`-not-counted mutant (`breaker counts model unavailable`) |
| power request (`host.keep_awake`) held through stop and exception | `test_keep_awake_is_held_through_a_stop` / `..._an_operator_stop` (R10-7a), `test_keep_awake_is_released_when_the_run_raises` (R10-7b) | section 2: killed |
| TLC seeded variants still fail | `check_models.py` (full) | section 4: 22/22 rejected |
| **R21-3 (design 16.2): Verified in one Copilot capture window (2026-09-25)** | `tests/e2e/test_r21_copilot_budget_kill.py::test_copilot_budget_kill_records_session_shutdown` (`@pytest.mark.credentials`; a real copilot-sol C1 cell, budget resealed to 45 s) | Red on `5192b3e^1` (before STOP-I slice 3): the budget-killed Copilot record has no `session.shutdown` (hard kill). Green on main at the join of the test: `session.shutdown` present and the tokens recorded (R-21 c2). Both runs by the Leader, back to back. |

**Design 16.2 and 16.3 (Test Architect gate at the join, spot-checked, not exhaustive):** 13 of the 16.2 named tests exist at HEAD (D-1 is `test_driver.py::test_cancel_closes_stdin_during_the_handshake`; R21-4 is two functions, `test_engine.py:729` and `:739`). 16.3's T2 (Hypothesis) exists at `test_engine.py:337-339`, and T3 holds (`session/cancel` appears in no `src` module but `driver.py`). The one hole found is R21-3, flagged above.

**Join fixes (Leader, after the gate):** the `cli.json` "a started run re-run" mutant now fails on the test's own assertion (`'HB-PRE-003: preflight reached'` does not start with `HB-USR-002`), not on a `KeyError`: the fixture plan carries an empty task map, and the `preflight.check` spy raises after recording. The dotnet timeout test's liveness check is `host.process_alive` (exit code, not `os.kill(pid, 0)`), so an ended process whose object is still held elsewhere reads as ended (section 6's lingering-handle candidate).

## 6. `test_correctness_dotnet.py::test_dotnet_oracle_timeout_is_na_and_leaves_no_process` — diagnosis

**Reported symptom** (slice 5, full-suite load): `os.kill(pid, 0)` at line 146 did not raise `OSError` once — i.e.
the killed process's PID still answered as alive immediately after `correctness.grade` returned. The same test
passes reliably alone.

**Mechanism under test.** `procs.run` spawns the `dotnet` process suspended, inside a fresh Windows Job Object
(`KILL_ON_JOB_CLOSE`), and resumes it. On the 2 s grading timeout, `terminate_and_confirm` calls
`TerminateJobObject` (repeated every 1 s) and polls `Job.active()` (the OS's own `ActiveProcesses` count) for up to
`_KILL_GRACE` = 30 s before `run()` returns. `TerminateJobObject` is a hard OS-level kill: the CLR gets no chance to
block it, and `Environment.ProcessId` inside the fixture (framework-dependent `dotnet <dll>` execution: no
apphost/child process) is the same PID `procs.spawn` reports. The mechanism does not depend on the process
cooperating.

**Measured.** Built the fixture once, then ran the "hang" scenario through `correctness.grade` (unmutated code)
under two escalating levels of synthetic concurrent-process load (standing in for "full-suite load" — this suite
runs single-process, no `xdist`, so contention must come from concurrently spawned processes, matching what
slice 5's run and this coordination run's other, concurrently-running tracks both do):

| run | load | trials | result |
| --- | --- | --- | --- |
| 1 | 8 concurrent `cmd /c ver` churners | 5 | 5/5 confirmed dead (`os.kill(pid, 0)` raised `OSError`); ~2.0-2.1 s per trial |
| 2 | 24 concurrent `python -c pass` churners (heavier: DLL loads, handle-table growth per spawn) | 8 | 8/8 confirmed dead; ~2.0-2.1 s per trial |

0/13 anomalies across both runs (script: scratchpad `dotnet_flake_probe.py`, not committed — a throwaway
measurement tool). The kill path's timing was flat and well inside budget in every trial; no reproduction.

**Diagnosis: Inferred**, not Verified — 13 measured attempts under synthetic load did not reproduce the failure, so
the specific mechanism is not confirmed, only the two most likely candidates are narrowed:

- `assume:` the slice-5 failure was Windows PID reuse — the test's only liveness check is `os.kill(pid, 0)` with no
  execution barrier against a *different* process being assigned the same, just-freed PID between `cell.close()`
  and the test's check. This is architecturally possible (the job/process kernel objects are freed once every
  handle closes, i.e. essentially immediately after `run()` returns) and needs heavier, more simultaneous process
  churn than this slice's budget could safely generate (slice-5's actual load was the *entire* suite plus, on this
  shared coordination host, other tracks' concurrent processes — visibly ~15+ `python.exe` and other processes at
  once during this slice, an intensity this probe's 24 churners did not match).
  - **Confirm:** reproduce with heavier, sustained churn (e.g. hundreds of processes/s) or add a creation-time
    check (`host.creation_time(pid)`, already used by R10-1/R21-5) to the test itself and see it catch a mismatch.
  - **Breaks:** if wrong, the true cause is something in `procs.py`'s kill path that only manifests under real
    full-suite conditions (not reproduced here), and this diagnosis under-covers it.
- Not the OS-level kill mechanism itself: `TerminateJobObject` + `Job.active()` confirmation is a hard, non-
  cooperative kill with a 30 s budget against a task that needs ~0 s once triggered; 13/13 clean, fast trials here
  give no evidence of a genuine race inside `procs.py`.

**No fix applied.** Per the no-guessing protocol, a code change for an unconfirmed race is a guess, not a fix; NG
also permits marking Inferred with what would confirm it and what breaks if wrong, which is what this section does.
The test is unchanged; the observed slice-5 failure is disclosed here as a single, unreproduced data point, not
labeled flaky and not silenced.

## 7. Suite and lint

- `uv run ruff check src tests tools`: **All checks passed!** (run after this slice's `tests/test_cli.py` and
  `tests/mutations/engine.json` edits.)
- `uv run pytest -q -p no:cacheprovider`: **1393 passed, 4 skipped, 8 deselected in 425.53 s (0:07:05)**. No
  failures. (The 8 deselected are the `credentials` marker, per `pyproject.toml`'s `addopts` (SUITE-A); out of
  scope here.)

## 8. Commits this slice

| SHA | what |
| --- | --- |
| `4497a9a` | fix(test): kill the cli.json survivor on the events-exists guard |
| `ae9944d` | fix(test): re-point 5 stale engine.json finds; fix a 6th's wrong-target survivor |

No red commits: every red observation in this slice was a `mutate_check`-style hand-applied, then restored,
mutation (never committed) — this is a proof pass over slices 1-5's existing tests, not a TDD feature build, so
there is no red/green commit pair to cite per fix; the mutation record above (with each mutant's find/replace and
the failing assertion it produces) is the evidence in its place.

---
**Handoff:** -> the STOP-I join (Leader). This note, `docs/proof/phase2.md`'s figures folded in per that doc's
convention, plus `git diff --stat` against the owned paths, R21-3 (S6 capture) and the section 5 `assume:`
confirmation are the Leader's remaining join items (design section 17, "At the join").
