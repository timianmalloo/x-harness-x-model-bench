---
id: proof-phase2
title: "Proof Pack - phase 2 (wave-by-wave joins)"
type: doc
status: draft
owner: "@timianmalloo"
phase: "Phase 2 · smoke on all harnesses"
tags: [proof, phase2, red-first, joins]
links:
  - { to: coordination-finish-harness-bench, rel: relates-to }
  - { to: proof-phase1, rel: relates-to }
review-by: "2026-10-08"
summary: >-
  The evidence for each phase-2 join: what was claimed, the red observed by a non-author, the mutation result, the
  reviewer's verdict, and the residuals. One Claim table per join.
---

# Proof Pack: phase 2

Each join follows the plan's join rule. A non-author re-runs every cited red in a throwaway worktree and sees it fail for the stated reason; `git show --stat` confirms the red touches no `src/`; and a cross-vendor reviewer adds mutants of their own. The suite command is `uv run pytest -q -p no:cacheprovider`, which is offline since SUITE-A. The lint command is `uv run ruff check src tests tools`.

## Join: SUITE-A control (unplanned; the Leader's own defect), 2026-09-24

| claim | evidence | red observed | reviewer |
| --- | --- | --- | --- |
| A bare `pytest` selects no `credentials` test; the documented `-m ""` opt-in still selects them | `tests/test_default_suite_is_offline.py`; `pyproject.toml` `addopts`; `-m credentials` collects 5 items (3 in `tests/e2e`, 2 real handshakes in `test_profiles.py`) | `5013299`: 1 failed, 1 passed (the bare run selected e2e items), by the Leader | none (Leader emergency control); flagged for the wave-1 join review |

**Residual:** before this control, W1-ACP's suite run, the Leader's first W1-HOST join run and the reviewer's runs each started real cells on the Anthropic and OpenAI logins. See `docs/lessons/defect-classes.md` SUITE-A.

## Join: W1-HOST (row 28), Grok `grok-4.7`, 2026-09-24

**Slice 1** (`w1-s1`, joined in `2b5743b`). The worker's transport failed with `output_limit_exceeded` at 906 s, after its last commit (RUN-A). The hand-back below was reconstructed by the Leader from the commits (R-10).

| claim | red → green | red observed (Leader, throwaway worktree) |
| --- | --- | --- |
| A failed job assignment whose wait times out still closes the job and raises `SpawnError` (residual 6a) | `76bb0ae` → `e8ec45c` | `tests/test_procs.py::test_a_timed_out_wait_after_a_failed_assignment_still_closes_the_job`: 1 failed, 13 passed |
| A failed `GlobalMemoryStatusEx` / `QueryUnbiasedInterruptTime` is not a zero reading (residual 6b) | `de2bdc5` → `3c0f962` | `tests/test_host.py`: 2 failed |
| `cmd_report` scans credentials before it prints the table (residual 5) | `0c254d2` → `95d705f` | `tests/test_cli.py::test_report_does_not_print_a_label_before_the_credential_scan`: 1 failed, 20 passed |
| The `base` fixture leaves 0 folders (residual 11, partly) | `a7cc351` (no natural red) | the Test Architect reverted the CLN-A teardown in a throwaway tree: "1 folder(s) left behind" |

**Slice 2** (`w1-host-s2`, joined in `7d73ada`). This is the loop-back for the review's Major: a raised host reading was not contained by the engine. The attempt reached `ready_for_review` in 490 s with 3,260,061 output bytes and 317 notifications, the first measurement for R-11.

| claim | red → green | red observed (Leader) |
| --- | --- | --- |
| A failed memory query is not recorded (`None`), and the outcome row is still written with `host_mem_available: null` | `ed2fa1d` → `dce41ce` | `tests/test_host.py` and `tests/test_engine.py::test_a_failed_memory_query_still_records_the_outcome_with_null`: 2 failed, 108 passed |
| A failed unbiased clock is not recorded, and `SleepDetector.slept()` stays `False` | `c48492c` → `dc15b2c` | `tests/test_host.py`: 2 failed, 1 passed |

**Mutation (cross-vendor reviewer, Claude Test Architect).**

| mutant | result | killing test |
| --- | --- | --- |
| M1 `proc.kill()` → `pass` in `except TimeoutExpired` (`procs.py:235`) | survived (near-equivalent) | none (Minor, open) |
| M2 memory-status check inverted | killed | `test_host.py::test_a_failed_global_memory_status_ex_is_not_a_zero_reading`, plus 48 engine tests |
| M3 table never printed on success | killed | `test_cli.py::test_grade_then_report_writes_the_page` |

**Suite on `main` after both joins:** 617 passed, 5 deselected; ruff clean.

**Veto read-back (Claude Test Architect, round 2): CLEARS THE VETO.** Its mutant M2b (the memory check inverted, run on the joined code) was killed by `test_host.py::test_a_failed_global_memory_status_ex_is_not_recorded` and `test_engine.py::test_a_failed_memory_query_still_records_the_outcome_with_null` (2 failed, 109 passed). The M2 row above names the slice-1 test; that test was renamed in `ed2fa1d`.

**Slice 3** (Grok, `w1-host-s3`, 279 s, 1,755,132 bytes; joined `c57cbcb`). `test_no_leftovers.py` now asserts only that its own `base` folder is gone, not a snapshot of the shared folder (the concurrency flake). The untested extra `proc.kill()` is removed (M1).

**Slice 4** (Claude Sonnet 5 per R-29, after Grok failed `protocol_error` at 3.36 s with no commit; joined `6cf7755`), `23c21be`, tests only:

| mutant (applied, run, reverted by the author) | killing test |
| --- | --- |
| M5 `available_memory()` returns `None` on success | `test_host.py::test_available_memory_and_unbiased_seconds_return_real_positive_values` ("isinstance(None, int)" is False) |
| M4 `SleepDetector.slept()` never anchors the first good reading | `test_host.py::test_sleep_detector_recovers_after_a_missing_first_reading` ("assert False is True") |

**Suite on `main` after slice 4:** 619 passed, 5 deselected.

**Still open (Minor):** residual 11 is only partly proven (a suite-wide leftover count is not enforced). The residual-5 sweep of `status`, `run` and `plan` goes to the Security lens.

**Open after slice 2 (Minor, advisory; slices 3 and 4 above closed M1 and the leftovers flake):**
- M1 survives.
- `test_no_leftovers.py` compares a snapshot of the shared `bench-test` folder, so a concurrent suite can fail it. One flake was seen on `main` while another suite ran.
- Residual 11 is only partly proven.
- The class sweep for residual 5 is not done: `bench status`, `bench run` and `bench plan` print plan-derived labels with no scan. This goes to the Security lens.

## Join: W1-TOOLB (row 26), Claude Sonnet 5 (R-10, moved from Agy), 2026-09-24

| claim | red → green | red observed | reviewer |
| --- | --- | --- | --- |
| `mutate_check.py --cosmic-ray` counts a kill only when a named test failed; a collection error, a timeout and an exit-2-shaped interruption are each not a kill; the dump format comes from cosmic-ray 8.7.0's own source | `e53a7bc` → `0e5ddb3` | Leader: 14 failed, 8 passed (tests only) | Codex `gpt-6-sol`, CLEAR (`docs/notes/review-w1-toolb-codex.md`): its own mutants M1 (`is not None` inverted), M2 (the timeout sentinel) and M3 (the overstated condition) were each killed by a named test |

**R-19:** the phase-1 figure of 2267 mutation kills is **not re-derivable (Flagged): the phase-1 cosmic-ray session databases were not kept.** The re-run is a named later window, and no mutation-bar claim is made in phase-2 artifacts until then.

**Follow-up (T0, Claude Sonnet 5; joined `a9f8bbc`).** `mutate_check` reports `error`, never `survived` or `killed`, when a run's output has no pytest summary (for example, the interpreter vanished mid-run; CLN-B). Red `b5847f8`: 3 failed, 23 passed (re-run by the Leader), then green `63a4465`. Leader mutant: `if False and not _ran_to_completion(output):` was killed by `test_only_a_named_failure_is_a_kill[…no-summary…]` ×2. The review was scaled to the tier (T0): the Leader, a non-author, was the reviewer.

## Join: W1-ACP (rows 6, 14), Claude Opus 5.5, 2026-09-24 (joined `124af8e`)

This discharges phase-1 residual 9: "capture one cell's full ACP stream … replace the schema-shaped fixture … re-run D5/D7. Deadline: before phase 2 changes the driver." The recordings were made in the Leader's capture window 1:
- **claude-code** (`claude-sonnet-5`, `end_turn`, 57 updates);
- **codex** (`gpt-6-sol`, `agent-full-access`, `end_turn`, 151 updates);
- **claude-code rejecting `claude-opus-5-5`:** Claude Code 2.1.274 needs 2.1.280 or newer.

All three are scrubbed (paths, emails, account plan labels). The user-level command names in `available_commands_update` are kept as US-13 evidence (known class R1.4).

| claim | evidence (test) | red observed (Leader) | mutation |
| --- | --- | --- | --- |
| (a) the recorder is transparent; `driver.py` untouched until (f) | `test_acp_record.py::test_the_recorder_is_transparent_and_records_every_byte[ok,permission]`; the first driver commit is `586fbb0` (f) | `18c12ad`: 7 failed | — |
| (b) verbatim replay, nothing synthesised | `test_driver.py::test_a_recorded_transcript_replays_verbatim_through_the_driver[3 recordings]` | `4645917`: 7 failed | (d) |
| (c) PAIRING presence parsed from the recordings | `test_every_pairing_but_permission_is_present_in_the_recordings_it_cites` | `c6c4d47`: 3 failed | — |
| (d) one-byte negative control | `test_d5_fails_when_one_byte_of_a_recorded_session_new_result_changes` | `c6c4d47` | the control is itself the mutant |
| (e) provenance per recording, capture date checked against the meta | `test_every_recording_states_its_provenance_from_its_capture` | `c6c4d47` | — |
| (f) `last_update_seconds`: the last update, null (never 0) with none, null for a handshake-time update | `test_last_update_is_the_turn_time_of_the_last_session_update`, `…_is_null_never_zero_with_no_session_update`, `…_of_the_last_update_not_the_first`, `test_a_handshake_time_update_leaves_last_update_null` | `043d1d5`: 2 failed | M1 (first, not last) and M2 (0.0 at handshake) killed |
| HB-CELL-116 for an unsupported model (R-18); one classifier with status precedence (R-23) | `test_a_model_the_harness_refuses_at_the_prompt_is_model_unavailable`; `test_a_prompt_error_is_classified_by_its_status_and_type[…, 4xx-with-api_error-type]`; `test_the_prompt_error_path_calls_the_native_record_classifier` | `b1d0cd0`: 6 failed; `450e349`: 1 failed (Codex F2) | Codex M2 (the classifier bypassed) killed |
| `session/set_model` after `session/new` and before `set_mode`; a refusal is HB-CELL-116 with no prompt sent (R-13, R-30) | `test_a_refused_model_setter_is_model_unavailable_and_the_prompt_is_never_sent[…]` | `30426c6`: 7 failed | Codex M1 (refusal read as `adapter_crash`) killed |
| engine hunks: `model=`, launcher `credential_kind`, `agent_version`, `acp_usage` (R-13, R-24, R-28) | `test_the_credential_kind_is_the_one_the_launcher_reports`, `…session_opened_event_carries_the_agent_version`, `…attempt_end_records_the_acp_usage_verbatim_or_null` | `09a9d07`: 4 failed | — |
| a real `ProfileLauncher` gets the engine past attempt start (Leader seam) | `test_profiles.py::test_a_real_profile_launcher_gets_the_engine_past_attempt_start` | `61acbd6`: 3 failed | — |

**Mutation:** `tests/mutations/driver.json` holds 5 mutants: M1 and M2 from the Test Architect, and three from the Codex reviewer. Run by the Leader with `uv run python tools/mutate_check.py tests/mutations/driver.json`, every mutation was killed. A first run under the system Python (no pytest) reported all 5 as `error`, never `killed`, which is the TOOL-B control behaving correctly.

**Reviewers:**
- Codex `gpt-6-sol` (`docs/notes/review-w1-acp-codex.md`): CONDITION on F2, fixed red-first.
- Claude Test Architect: (a)–(e) met by tests; (f) conditions M1 and M2 closed.

**Suite on `main`:** 662 passed, 5 deselected; ruff clean.

**Residuals:**
- The ledger and `bench status` half of (f) is verified at the wave-1 exit.
- The Copilot ACP recording is due in capture window 2.
- No real `session/request_permission` exemplar exists: every capture had 0 permission requests.
- Replay has no timing, so intra-turn times are replay-speed values.
- The codex recording's chunk boundaries are a scrub artifact (see `provenance.json`).
- The stale `engine.py:369-371` comment is a seam to W2-STOP.
