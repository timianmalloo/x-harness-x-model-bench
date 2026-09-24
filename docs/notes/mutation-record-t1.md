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
  cosmic-ray 8.7.0, run natively on Windows (mutmut refuses native Windows, probe R13), over lifecycle, errors and 299
  of engine's 765 mutants. Every mutant run is killed or argued equivalent; none is open, none timed out, none was
  not exercised on the platform. The engine functions outside that scope are covered only by tests/mutations/engine.json.
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
- **Engine scope.** Covered: `record`, `_drain`, `_after_append`, `_append_now`, `_stop_launching`, `_kill`, `_check_budgets`, `_end_process`, `_attempt`, `_cell_worker`, `_usage_per_model`, `_code`, `_disk_full`, `_free_bytes`, `_beating`. That is 299 of 765 mutants. **Out of scope:** 466 mutants in `run`, `_launch`, `_run_cell`, `_archive`, `_classify`, `configure_logging`, `_job_query` and `_confirm`. These are covered only by `tests/mutations/engine.json` (44 of 44 killed). Reason: measured at about 50 s per mutant, a full run exceeded the track budget. This is a disclosed gap against the mutation bar, carried to the Proof Pack.
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
