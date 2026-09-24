---
id: "mutation-record-t1"
title: "Mutation record: T1 (engine, errors, lifecycle)"
type: decision-note
status: accepted
owner: "@timianmalloo"
phase: "Phase 1 · walking skeleton"
tags: [mutation, cosmic-ray, engine, lifecycle, errors, T1]
links:
  - { to: coordination-phase1-finish, rel: relates-to }
  - { to: findings-t1-engine-hardening, rel: relates-to }
review-by: "2026-12-22"
summary: >-
  cosmic-ray 8.7.0, run natively on Windows (mutmut refuses native Windows, probe R13), over lifecycle, errors and
  every engine.py mutant: T1 ran 299 (301 at T10's count) and track T10 ran the remaining 466. Every mutant is killed
  or argued equivalent; none is open, none timed out, none was not exercised on the platform. T10 found and fixed one
  design drift (the kill-retry cap).
---

# Mutation record: T1

**Transcribed by the Coordinator** from the T1 track's report (the harness refused the sub-agent's write).

- **Tool.** `uv run --with cosmic-ray==8.7.0`, local distributor, native Windows 11. A first attempt used the test command `python -m pytest`, which resolved to a Python without pytest. Its baseline failed and every mutant counted as "killed". That run was discarded. The runs below use the project venv's `python.exe` and pass their baseline.
- **Test commands** (all with `-x -q -p no:cacheprovider`):
  - lifecycle: `tests/test_lifecycle_conformance.py tests/test_grade.py`
  - errors: `tests/test_errors.py tests/test_status.py tests/test_engine.py`
  - engine: `tests/test_engine.py tests/test_lifecycle_conformance.py`
- **SHAs.**
  - lifecycle and errors ran at `67e956b`; `lifecycle.py` and `errors.py` are unchanged since.
  - engine ran at `769fb90`; `engine.py` is unchanged since.
  - Re-verification (`cosmic-ray mutate-and-test`) ran at `6158a96` and `39aa9f4`, after the new tests.
  - T7 checks with `git diff <sha> HEAD -- <module>` that each record is still current.
- **Engine scope.** Covered: `record`, `_drain`, `_after_append`, `_append_now`, `_stop_launching`, `_kill`, `_check_budgets`, `_end_process`, `_attempt`, `_cell_worker`, `_usage_per_model`, `_code`, `_disk_full`, `_free_bytes`, `_beating`. That is 299 of 765 mutants. **Out of scope:** 466 mutants in `run`, `_launch`, `_run_cell`, `_archive`, `_classify`, `configure_logging`, `_job_query` and `_confirm`. These are covered only by `tests/mutations/engine.json` (44 of 44 killed). Reason: measured at about 50 s per mutant, a full run exceeded the track budget. This is a disclosed gap against the mutation bar, carried to the Proof Pack. **Closed: track T10 ran all 466 (see "Engine, the remaining 466 (T10)" below).**
- **Timeouts and "not exercised on platform":** none. Everything ran natively.

## Results

| module | run | killed | killed after new tests | equivalent | open |
| --- | --- | --- | --- | --- | --- |
| lifecycle | 107 | 91 | 0 | 16 | 0 |
| errors | 13 | 11 | 1 (`set(RUN_CODES) - …`: test_every_cause_and_run_code_is_a_valid_bench_error_code) | 1 | 0 |
| engine | 247 run + 52 skipped as annotations | 186 | 30 | 28 + 3 run annotations + 52 skipped annotations | 0 |

**Killed after new tests (engine, each re-verified with `mutate-and-test`, result `killed`):**
- L150, L151, L155, L156 (`record` backpressure): test_record_waits_through_a_full_inbox_and_a_slow_drain
- L162 ×3 (`_drain` deadline `+`→`-`/`*`/`**`): test_a_drain_appends_what_arrives_before_its_deadline
- L164 (`max(…, 0)`→`1`): test_a_drain_with_nothing_queued_returns_at_its_deadline
- L169 (`or`→`and`): test_once_the_engine_has_ended_a_queued_record_fails_unwritten
- L187 `>`, `>=`: test_the_budget_runs_from_the_prompt_not_from_the_working_copy
- L196 `<=`: test_the_circuit_breaker_fires_at_its_threshold_not_before
- L199 `0`→`1`/`-1`: test_a_success_resets_the_infrastructure_streak
- L271: test_a_failed_append_of_the_stop_ends_the_run_incomplete_not_raised
- L311 `>`, `>=`: test_an_archive_refused_with_a_bench_error_is_recorded_under_its_code
- L315 `[:300]`→`[:299]`: test_a_failing_argv_env_leaves_no_credential_copy (the detail is capped at 300)
- L398 `or`→`and` and L404 ×2 (`attempt` 1): test_happy_run… (asserts the attempt and the session ids)
- L417 ×6 (`-1` sentinel) and L446: test_a_process_whose_status_never_arrives_is_recorded_as_minus_one
- L431: test_a_stdin_that_fails_to_close_still_ends_the_turn
- L494: test_the_heartbeat_keeps_beating_after_a_failed_beat

## Equivalent mutants (diff, then a one-line argument)

**Annotations: lifecycle L81 ×11 and engine L284, L383, L397, plus 52 skipped.**
- Diff: `str | None` → `str <op> None`.
- Argument: `from __future__ import annotations` keeps every annotation an unevaluated string. In engine.py every `|` is an annotation (checked with grep).

**lifecycle**
- L71 `t.writer == "engine"` → `<= "engine"`. "engine" is the least of the closed writer set {engine, grading, ledger}, so the same rows are selected.
- L71 `==` → `is`, and L84 `t.writer != writer` → `is not`. The writer values are identifier-like literals, which CPython interns, so identity equals equality for every caller.
- L123 `kind == "attempt.process_started"` → `<=`. The only other kind that is `<=` is `attempt.process_ended`. Its cell is already in `running` (the after-rule guarantees a start), so the extra `add` does nothing.
- L127 `kind == "attempt.process_ended"` → `<=`. No table kind sorts below it, and unmapped kinds fail earlier.

**errors**
- L70 `set(RUN_CODES) | {causes}` → `^`. The two code sets are disjoint, so the symmetric difference equals the union.

**engine**
- L127, L141 `fact == "events"` → `is`; L172 `fact == STOP` → `is`; L187 and L191 `kind == "<literal>"` → `is`; L311 `code == "HB-RUN-001"` → `is`.
  Argument: the compared values are the engine's own string constants, passed through by reference. On CPython 3.14 they are the same objects; the survival observed this.
- L538 `errno == ENOSPC` → `is`. Small ints are cached.
- L196 `>=` → `==` / `is`. The streak grows by 1 and is compared to 3; after the first stop, `_stop_launching` does nothing anyway.
- L296 `now - a.prompt_mono` → `now % a.prompt_mono`. Monotonic readings are far larger than any budget, so `now % p` equals `now - p` while `now < 2p`.
- L296 `>` → `>=`. Float equality of elapsed time never happens.
- L434 `< deadline` → `<=`. Same reason.
- L171, L175, L180 `continue` → `break` in `_drain`. Leftover items are handled by the next drain, which runs every loop; after the end, `record()` fails them itself.
- L322 `except BenchError` → other. The worker thread ends either way; only the stderr from the thread hook differs.
- L394 and L497 `daemon=True` → `False`. The tail reader ends at pipe EOF, and the heartbeat thread is joined in `finally`, so nothing outlives the run.
- L416 `join(timeout=5)` → 4/6; L435 `sleep(0.1)` → 1.1; L445 `wait(timeout=10)` → 9/11. These are poll and wait constants: timing only, with no recorded difference.
- L434 `_job_query(cp.job.active, 1)` → 2. The value stays truthy, so the behaviour is identical.
- L434 → 0. When the job cannot be queried, the grace wait ends at once instead of at the deadline. Either way the end goes through `_confirm`, which holds the slot until it confirms, so the ledger is identical.
- L543 `path.parent != path` → `is not` / `<` / `<=`. Every path the engine passes lies on a mounted volume, whose root exists, so the loop stops at an existing folder before the comparison can differ.

## Engine, the remaining 466 (T10)

*Run by track T10 and transcribed by the Coordinator. The Coordinator re-ran the cap red (`70531dc`). It also spot-checked two kills and one equivalent with `tools/mutate_check.py` at `ea012a4`: the two kills were killed, and the equivalent survived, as argued.*

This section closes the "Out of scope" gap above. These are the 466 engine mutants T1 did not run. With T1's 301 (T1 counted 299; the 2 extra are T9's `configure_logging` change), they cover all 767 mutants of `engine.py` at `e8c32a3`.

- **Tool.** cosmic-ray 8.7.0, local distributor, native Windows 11.
  - 10 detached shards `C:/Projects/bench-test/cr-t10-*`, each with its own venv. Each kept `index % 10 == k` of one line-filtered master session.
  - Each shard used an absolute interpreter and `PYTHONUTF8=1`.
  - All 10 baselines passed.
  - `git status -- src` was clean in every shard after each phase. The shards were removed afterwards.
- **Scope** (`cr-filter-lines`): `1-125, 200-264, 273-282, 298-304, 324-381, 448-484, 504-518, 546-589`. That is every line outside T1's 15 functions:
  - `run`, `_launch`, `_run_cell`, `_classify`, `_archive`, `_job_query`, `_confirm`, `configure_logging` (394 mutants);
  - the module constants and classes;
  - `span_id`, `__init__`, `_kill_all`, `_outcome`, `_keep_tail`.
- **Test command:** `tests/test_engine.py tests/test_lifecycle_conformance.py tests/test_cli.py` (`-x -q -p no:cacheprovider`).
- **SHAs and wall time:**
  - phase 1: all 466 at `e8c32a3` (1836 s);
  - phase 2: 123 survivors at `a9800c3`, after the survivor tests (1329 s);
  - `mutate-and-test` re-verification: 60/60 `killed` (619 s);
  - the two cap mutants re-verified after the fix `e10b1e9`.
- **No timeout, no incompetent, no "not exercised on platform".**

| function | mutants | killed | killed after new tests | equivalent | open |
| --- | --- | --- | --- | --- | --- |
| module constants | 14 | 5 | 6 | 3 | 0 |
| classes (Launcher, EngineConfig, RunSummary, _Active) | 8 | 4 | 2 | 2 | 0 |
| `span_id` | 2 | 0 | 2 | 0 | 0 |
| `__init__` | 6 | 4 | 2 | 0 | 0 |
| `run` | 123 | 108 | 9 | 6 | 0 |
| `_launch` | 2 | 0 | 2 | 0 | 0 |
| `_kill_all` | 1 | 1 | 0 | 0 | 0 |
| `_outcome` | 24 | 13 | 0 | 11 | 0 |
| `_run_cell` | 155 | 132 | 22 | 1 | 0 |
| `_classify` | 56 | 20 | 3 | 33 | 0 |
| `_archive` | 42 | 39 | 3 | 0 | 0 |
| `_job_query` | 1 | 1 | 0 | 0 | 0 |
| `_confirm` | 1 | 1 | 0 | 0 | 0 |
| `_keep_tail` | 17 | 1 | 11 | 5 | 0 |
| `configure_logging` | 14 | 14 | 0 | 0 | 0 |
| **total** | **466** | **343** | **62** | **61** | **0** |

**The design drift this found.** The design (`phase1-walking-skeleton.md:189`) says kill retries back off "1 s doubling to 30 s". Since `3d14c73` (T1-8), the code had capped at 60 s, with no recorded reason. The L54 cap mutants survived, because no test pinned the cap.
- Red: `70531dc`, `test_an_unconfirmed_kill_backs_off_from_1_s_doubling_to_the_designs_30_s_cap`, failing at index 6 with `32.0 != 30`.
- Fix: `e10b1e9`, `KILL_RETRY_CAP = 30.0`.
- The mutants 30.0 → 29.0 / 31.0 were re-verified with `mutate-and-test`, result `killed`.
- `engine.json` pins the drift itself (30.0 → 60.0).

**Killed after new tests** (commits `a9800c3`, `ea012a4`; each re-verified with `mutate-and-test`, cosmic-ray job-id prefixes in T10's report):
- `test_classify_applies_the_cause_precedence_in_order`: L48 ×2, L458, L460, L464.
- `test_a_windows_disk_full_error_is_a_full_disk`: L53 39 → 40/38.
- `test_the_engine_loop_passes_every_fifth_of_a_second_and_never_spins`: L83 ×2.
- `test_span_ids_are_w3c_parent_ids`: L105 ×2.
- `test_the_inbox_is_the_designs_bounded_queue`: L114 ×2.
- `test_the_host_is_kept_awake_for_the_run_and_released_at_its_end`: L216, L258.
- `test_free_space_exactly_at_the_floor_is_not_below_it`: L231.
- `test_a_run_with_nothing_left_to_launch_ends_without_an_idle_wait`: L238, L257.
- `test_grading_never_runs_on_a_run_that_needs_recovery`: L241.
- `test_a_worker_still_running_when_the_run_fails_is_refused_at_once_not_left_waiting`: L256.
- `test_the_run_releases_every_ledger_segment_when_it_returns`: L259.
- `test_a_plan_of_more_than_256_cells_can_end_complete`: L262.
- `test_a_failed_append_of_the_launch_intent_ends_the_run_incomplete_not_raised`: L277.
- `test_an_engine_thread_failure_exits_the_process_and_leaves_no_cell_running`: L279.
- `test_a_spawn_failure_with_no_win32_error_records_zero`: L358 ×3.
- `test_turn_usage_is_recorded_under_attempt_one`: L364 ×2.
- `test_the_outcome_records_times_in_milliseconds_and_a_capped_detail`: L370, L373, L374 (17 mutants).
- `test_a_workspace_that_fails_before_any_folder_exists_is_still_archived`: L473.
- `test_the_archive_is_recorded_as_attempt_one`: L477 ×2.
- `test_the_stderr_tail_keeps_the_last_bytes_up_to_its_limit`: L552 ×5, L553 ×4.
- `test_a_stderr_pipe_that_fails_ends_the_tail_quietly`: L554 ×2.
- `test_an_unconfirmed_kill_backs_off_from_1_s_doubling_to_the_designs_30_s_cap`: L54 ×2, after the fix.

`tests/mutations/engine.json` gained 5 entries: 4 `_classify` precedence cases and the cap. The result is 49/49 killed.

### Equivalent mutants (T10)

**Annotations (44).** L325 ×11, L449 ×11, L450 ×22. The diff is `X | None` → `X <op> None`. Argument: `from __future__ import annotations` keeps every annotation an unevaluated string.

**Argued one by one (17):**
- **L53 `(39, 112)` → 113/111.** CPython maps winerror 112 to errno ENOSPC (`OSError(0, "", None, 112).errno == 28`). So `errno == ENOSPC` already decides every ERROR_DISK_FULL, and 112 in the tuple never does.
- **L55 `RECORD_POLL` 0.5 → 1.5.** A poll period. No outcome and no row changes (the class of L435/L445 above).
- **L82 `end_grace` 10.0 → 9.0/11.0.** A timing constant. The end always goes through `_confirm`, so the ledger is identical.
- **L233 `len(self.active) < parallelism` → `!=` / `is not`.** Only this loop adds to `active`, one at a time, so it stops at equality either way. `parallelism` is 1–2, and CPython caches small ints.
- **L238/L257 `_drain(0)` → `_drain(-1)`.** `_drain` clamps with `max(deadline - now, 0)`.
- **L250 `fact != "events"` → `is not`.** An interned literal on both sides.
- **L262 `==` → `>=`.** `outcomes` is keyed by plan cell ids, so it can never exceed `len(cells)`.
- **L366 `is Cause.timed_out` → `==`.** `Enum.__eq__` is identity.
- **L550 `read1(65536)` → 65537/65535.** This changes the chunk size only, and the tail is the last `limit` bytes however the stream is chunked.
- **L552 `len(tail) > limit` → `>=` / `!=` / `is not`.** `del tail[:-limit]` deletes nothing when `len(tail) <= limit`.

**Observed, not a defect.**
- The 112 in `DISK_FULL_WINERRORS` is dead weight (see L53).
- If the engine thread raises while a turn hangs, `run()` returns without killing that turn. The cell dies at process exit, because the workers are daemon threads and the Job's kill-on-close fires then. `test_an_engine_thread_failure_exits_the_process_and_leaves_no_cell_running` pins this.
