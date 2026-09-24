---
id: "findings-t3-process-edges"
title: "Findings → tests: track T3 process-edges"
type: proof-pack
status: accepted
owner: "@timianmalloo"
phase: "Phase 1 · walking skeleton"
tags: [proof, findings, red-first, T3]
links:
  - { to: coordination-phase1-finish, rel: relates-to }
review-by: "2026-12-22"
summary: >-
  Track T3's findings→tests map: nine findings, each with a test-only red commit and a separate fix. The harness
  refused the sub-agent's write of this file, so the Coordinator transcribed it from the track's report and
  re-ran two red SHAs itself.
---

# Findings → tests: track T3 process-edges

**Transcribed by the Coordinator.** The harness refused the T3 sub-agent's write of this file ("subagents should not write report files"), so the Coordinator transcribed it from the track's report. The Coordinator itself re-ran these red SHAs in a throwaway worktree, and both failed on the recorded line:
- **T3-5** `2f78e2f`: "DID NOT RAISE OSError".
- **T3-8** `1aa5230`: `test_meta_is_kept_when_the_adapter_reports_no_usage` failed.

`tests/mutations/t3.json` was re-run at head `1d85e9f`: every mutation killed (15 of 15).

| # | finding | red SHA → fix SHA | test node(s) | failing line at red |
| --- | --- | --- | --- | --- |
| T3-1 | D2: the ACP line reader must never crash | `8c67ef6` → `51a563a` | `tests/test_driver.py::test_a_deeply_nested_line_is_junk_never_a_crash[list]`, `test_line_reader_never_crashes_and_stays_bounded` | `RecursionError: Stack overflow ... decoding a JSON array` (the reader thread died without sending `eof`) |
| T3-2 | D2: T-TEL fuzz of both native readers | `9182845` → `da504c0` | `tests/test_telemetry.py::test_fuzzed_records_never_crash_either_reader_and_stay_typed`, `test_foreign_types_in_known_fields_are_ignored_not_crashed_on[*]` | `TypeError: cannot use 'list' as a dict key` |
| T3-3 | a newline-free record is read in bounded memory | `f8cbb9e` → `2802edc` | `test_a_newline_free_record_is_read_in_bounded_memory` | `peak 16917706 bytes for an 8 MiB line` |
| T3-4 | a missing usage field is HB-TEL-001, not a silent zero | `eb652db` → `bb9758f` | `test_a_missing_usage_field_is_hb_tel_001_not_a_silent_zero[*]` | `'Extraction' object has no attribute 'missing'` |
| T3-5 | a failed job query raises from the last error | `2f78e2f` → `64db0a4` | `tests/test_procs.py::test_a_failed_job_query_raises_from_the_last_error`, `test_a_closed_job_is_not_reported_empty` | `DID NOT RAISE OSError` (a closed job's NULL handle was answering for the caller's own job) |
| T3-6 | `procs.run` leaks nothing on an unconfirmed kill | `baf6e00` → `095fdc0` | `test_run_with_an_unconfirmed_kill_raises_nothing_and_leaks_nothing` | `subprocess.TimeoutExpired ... timed out after 3` |
| T3-7 | D5: recorded fixtures state their provenance and replay through the driver | `948fc82` → `b62550a` | `test_every_recorded_acp_fixture_states_its_provenance`, `test_a_recorded_prompt_result_replays_through_the_driver[*]` | `FileNotFoundError: ...provenance.json` |
| T3-8 | `_meta` is kept when the adapter reports no usage | `1aa5230` → `ce5c8a8` | `test_meta_is_kept_when_the_adapter_reports_no_usage` | `assert None == {'usage': None, 'meta': ...}` |
| T3-9 | D7: the emitted set comes from real fake-agent runs; a seeded unpaired type fails | `0cd34ee` → `c8373b0` | `test_every_message_type_the_fake_emits_is_paired_and_every_pairing_is_emitted`, `test_the_fidelity_check_fails_on_a_seeded_unpaired_type` | `pairings no real run of the fake emits: ['session/set_model.result']` |
| T3-10 | Simplifier minors: unused knobs removed | `e5b2ab0` → `094b27d` | `test_run_turn_has_no_model_switch`, `test_unused_knobs_are_gone` | `assert 'model' not in mappingproxy(...)` |

**D5 caveat (disclosed by the track):**
- Only the two prompt results are real recordings. No full transcript survives, because the probe folders were deleted.
- The scrub rule is marked unknown.
- The replay's handshake replies are labelled as schema shapes, not recordings.

**Seam raised:** `req-01M38NTSV1RDHVS8SX2TEES0RQ` → T2. `grade/runner.py` should score `cost_usd` as NOT_RECORDED when `Extraction.missing` is non-empty. The Coordinator relayed it.

**Residual, not fixed** (same classes as T3-5 and T3-6):
- `spawn()` can raise `TimeoutExpired` before `job.close()` after a failed assignment.
- `host.py` does not check the results of `GlobalMemoryStatusEx` and `QueryUnbiasedInterruptTime`.

Both are recorded for the Proof Pack's residual-risk list.
