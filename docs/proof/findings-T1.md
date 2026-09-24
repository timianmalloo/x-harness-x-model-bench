---
id: "findings-t1-engine-hardening"
title: "Findings to tests: T1 engine hardening"
type: proof-pack
status: accepted
owner: "@timianmalloo"
phase: "Phase 1 · walking skeleton"
tags: [proof, red-first, engine, lifecycle, errors, T1]
links:
  - { to: coordination-phase1-finish, rel: relates-to }
  - { to: mutation-record-t1, rel: relates-to }
review-by: "2026-12-22"
summary: >-
  The T1 checklist, finding by finding: the test node, the red commit that added the test alone, the failing line at
  that commit, and the fix commit. Items 14 and 15 were missing controls, not defects, so their red is shown under a
  named mutant. The Coordinator transcribed this file (the harness refused the sub-agent's write) and re-ran two red
  SHAs.
---

# Findings to tests: T1 engine hardening

**Transcribed by the Coordinator.** The harness refused the T1 sub-agent's write of this file ("Subagents should return findings as text"), so the Coordinator transcribed it from the track's report. The Coordinator itself re-ran these red SHAs in a throwaway worktree, and each failed on the recorded assertion:
- **item 1** `0569fe7`: `assert ('timed_out',..., 'timed_out') == ('completed',...d_turn', None)`.
- **item 7** `6e85129`: `['HB-CELL-115', 'HB-CELL-115'] == ['HB-CELL-115']` and `['HB-CELL-114', 'HB-CELL-114'] == ['HB-CELL-114']`.

`tests/mutations/engine.json` was re-run at head `5e75436`: every mutation killed (44 of 44).

Branch `track/t1-engine-hardening` (base `e5ee302`, merged with `impl/phase1` at `bb338f5` and `7d95665`). The failing line is the first `E` line of `uv run pytest -q -p no:cacheprovider --tb=line <node>` run at the red SHA.

| # | finding | test node (tests/…) | red | failing line at red | fix |
| --- | --- | --- | --- | --- | --- |
| 1 | A budget kill after the turn ended recorded `timed_out`; `ended` was set late; terminate raced close | test_engine.py::test_a_budget_expiring_after_the_turn_ended_is_not_a_timeout | 0569fe7 | `AssertionError: assert ('timed_out',..., 'timed_out') == ('completed',...d_turn', None)` | de9c046 |
| 2 | A failure after seed or spawn left the credential copy, a live process and an open job; `seed` ran before `argv_env` | test_engine.py::test_a_failing_argv_env_leaves_no_credential_copy | 8e48d40 | `AssertionError: assert not [WindowsPath('…/home/.credentials.json')]` | 57be27c, 71f110d |
| 2 | (same) | test_engine.py::test_a_failure_after_spawn_ends_the_process_and_cleans_the_credentials | 8e48d40 | `ConformanceError: NoOutcomeWhileRunning: kill, confirm, then record: cell.outcome for cell 0474a28fb408f031 after [...]` | 57be27c |
| 2 | (same) | test_engine.py::test_a_ledger_failure_after_spawn_still_cleans_the_credentials | 8e48d40 | `AssertionError: assert not [WindowsPath('…/home/.credentials.json')]` | 57be27c |
| 2 | T-CELL-credclean, the spawn-failure variant (`missing_exe=True`): a regression control | test_engine.py::test_credentials_are_gone_after_a_spawn_failure | 8e48d40 | passed (that path already cleaned) | n/a |
| 3 | A failure after the outcome was swallowed and the run reported complete | test_engine.py::test_an_archive_failure_is_recorded_and_the_run_is_incomplete | 2e41baf | `AssertionError: assert [] == [('0474a28fb4...HB-CELL-199')]` | 6b4619e |
| 4 | After the ledger broke, the loop stopped draining and queued workers blocked forever | test_engine.py::test_after_the_ledger_breaks_no_worker_blocks_forever | fbdc3b5 | `AssertionError: the engine did not finish within 30 s` (strengthened in 9bd5d55; still red on the fbdc3b5 engine) | 715c56d |
| 5 | `record()` did not validate on the worker side | test_engine.py::test_record_rejects_a_non_canonical_value_on_the_worker_side | e8191a9 | `assert (not True)` | ea91288 |
| 5 | Any append error broke the run, not only a write or fsync `OSError` | test_engine.py::test_a_bad_record_fails_its_cell_not_the_run | e8191a9 | `KeyError: '0474a28fb408f031'` | ea91288 |
| 6 | `turn_usage` entries for one model were separate rows | test_engine.py::test_turn_usage_is_summed_per_model_before_it_is_recorded | d3718d1 | `AssertionError: assert [('m-a', 1, 2..., 2, 3, 4, 5)] == [('m-a', 2, 4..., 2, 3, 4, 5)]` | 9eadcd4 |
| 7 | Workers wrote `run.launch_stopped` themselves | test_engine.py::test_two_workers_asking_to_stop_give_one_launch_stopped | 6e85129 | `AssertionError: assert ['HB-CELL-115', 'HB-CELL-115'] == ['HB-CELL-115']` | 919ca5e |
| 7 | The worker-side circuit breaker stopped once per extra failure | test_engine.py::test_the_circuit_breaker_stops_launching_once | 6e85129 | `AssertionError: assert ['HB-CELL-114', 'HB-CELL-114'] == ['HB-CELL-114']` | 919ca5e |
| 8 | T-FI-unkillable: retries every 30 s with no backoff (procs seam: `Job.terminate` fails for 4.5 s) | test_engine.py::test_an_unconfirmed_kill_is_logged_once_and_retried_with_capped_backoff | c68724b | `assert [1, 30] == [1, 1, 2]` | 3d14c73 |
| 8b | T3-5: a job query that raises `OSError` crashed the end path | test_engine.py::test_a_failing_job_query_is_an_unconfirmed_kill_not_a_crash | 151f583 | `ConformanceError: NoOutcomeWhileRunning: … cell.outcome for cell 0474a28fb408f031 after [...]` | c73bbc3 |
| 8b | (the same, through `procs._query` after the merge) | test_engine.py::test_job_queries_failing_through_the_procs_seam_hold_the_slot_until_confirmed | 4f3c1c6 (added after the fix) | n/a | c73bbc3 |
| 9 | `engine.log` dropped every extra except `error_code` and `cell_id` | test_engine.py::test_engine_log_keeps_the_whitelisted_extras_only | 37e1b4e | `AssertionError: assert {'error_code'...t': None, ...} == {'error_code'...'events', ...}` | b251ab1 |
| 10 | No heartbeat during the grading hook | test_engine.py::test_the_heartbeat_runs_during_the_grading_hook | 74a4225 | `AssertionError: the lock's mtime (the heartbeat) did not move while grading` | aa35bf7 |
| 11 | The outcome had no `updates` or `last_update_ms` | test_engine.py::test_the_outcome_records_updates_and_last_update_ms | d12a785 | `KeyError: 'updates'` | 2e242c0 |
| 12 | ENOSPC was `failed (workspace)` | test_engine.py::test_a_full_disk_while_building_the_workspace_is_a_disk_failure | 91bba55 | `AssertionError: assert ('workspace', 'HB-CELL-113') == ('disk', 'HB-CELL-112')` | 716d135 |
| 12 | The disk floor ignored `run_dir`'s volume | test_engine.py::test_the_disk_floor_also_checks_the_run_dirs_volume | 91bba55 | `AssertionError: assert [] == ['HB-RUN-004']` | 716d135 |
| 12 | A failed stderr-tail write replaced the real outcome | test_engine.py::test_the_outcome_is_recorded_before_the_best_effort_files | 91bba55 | `AssertionError: assert 'failed' == 'completed'` | 716d135 |
| 13 | No "run lock held" code; the engine used HB-RUN-003 | test_errors.py::test_a_held_run_lock_and_a_refused_teardown_have_their_own_codes | 63b666d | `KeyError: 'HB-RUN-005'` | 05f9f21 |
| 13 | (same) | test_engine.py::test_a_second_engine_on_a_held_run_is_refused_with_run_lock_held | 63b666d | `AssertionError: assert 'HB-RUN-003' == 'HB-RUN-005'` | 05f9f21 |
| 14 | T-LOG-nosecret missing (a control) | test_engine.py::test_an_echoed_credential_reaches_the_archive_but_never_engine_log_or_status | 78468c3 | passed at red. Under the engine.json mutant "T1-14 the outcome's detail logged": `assert 'sk-ant-FAKE-login-5f1c0de' not in '[{"ts": "20...ail.log\'"}]'` | n/a |
| 15 | T-ENG-suspend missing (injected clock) | test_engine.py::test_a_host_sleep_mid_turn_kills_the_cell_as_host_suspended | 3700560 | passed at red. Under the mutant "T1-15 a host sleep is ignored": `AssertionError: the engine did not finish within 45 s` | n/a |
| 15 | T-JOB-daemon missing | test_engine.py::test_a_build_server_left_by_the_turn_is_gone_when_the_end_is_recorded (renamed `…_gone_before_the_job_is_closed` in 9bd5d55) | 3700560 | passed at red. Under the mutant "T1-15 the job is not ended at end_turn": `assert [[5784, 8212, 28428]] == [[]]` | n/a |
| 15 | T-ARC-full missing (its behaviour was fixed by items 3 and 12) | test_engine.py::test_a_full_disk_during_the_archive_records_archive_failed_as_disk | 3700560 | passed at red. Under the mutant "T1-15 … not a disk code": `AssertionError: assert [('0474a28fb4...HB-CELL-199')] == [('0474a28fb4...HB-CELL-112')]` | n/a |
| 16 | Two sources of transitions; the engine never consulted the table | test_lifecycle_conformance.py::test_the_engine_consults_the_table_and_writes_only_its_own_rows | 5d6563e | `Failed: DID NOT RAISE ConformanceError` | de85172 |
| 16 | (same) | test_lifecycle_conformance.py::test_every_engine_row_of_the_table_is_written_by_the_engine | 5d6563e | `AttributeError: module 'harness_bench.lifecycle' has no attribute 'ENGINE_TRANSITIONS'` | de85172 |
| 16 | A seeded case was rejected under a different rule than the one it names | test_lifecycle_conformance.py::test_each_seeded_out_of_order_ledger_is_rejected_under_its_rule[prompt_sent before process_started (WriteIntent/StartCell order)] | 5d6563e | `AssertionError: Regex pattern did not match.` | de85172 |
| 16 | Six guards had no seeded case | test_lifecycle_conformance.py::test_every_guard_of_the_table_has_a_seeded_case | 5d6563e | `AttributeError: … no attribute 'RULES'` | de85172 |
| 17 | Dead `process_alive` and `read_events`; an always-overwritten `archive_file` literal | test_engine.py::test_the_engine_keeps_no_dead_helpers_or_literals | 6e409dd | `AssertionError: assert (not True)` | 77b4dbb |

**Item 16: why the scan.** The item allows an AST scan only with a reason. This test does a text scan of the engine's source for dotted `"kind"` literals, not an AST scan. Reason: a table cannot show that a row is still written; only the writer's source can.

**Behaviour changes to know about:**
- A run with a `cell.archive_failed` event writes no `run.completed` and exits 3. The workspace is kept.
- `cell.archive_failed` is a new lifecycle transition: it comes after the outcome, with no live process.
- `archive_files` rows lose the dead `"kind": "archive_file"` key. The row's own `kind` (`file` or `link`) was already the value that won.
- `peak_memory` and `cpu_ms` are null when a job query fails.
- `last_update_ms` is null until the driver exposes `TurnResult.last_update_seconds`. This is seam request `req-01M38KX8503601BEP857749VVF` to T3, which had already finished, so it is carried to the Proof Pack as a follow-up.
- Interfaces kept: the `TurnResult.usage` shape, `segment_heads` (R-2), the procs seam signatures, and HB-RUN-003 still meaning "teardown refused".
