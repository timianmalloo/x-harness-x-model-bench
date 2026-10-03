---
id: review-eval-ta-w1b
title: "W1-B crash-atomic publish design review: Test Architect lens"
type: doc
status: draft
owner: "@timianmalloo"
phase: "Enterprise evaluation: Wave 1 gate reviews"
tags: [review, test-architect, evaluation-campaign, wave-1, w1-b]
links:
  - { to: design-eval-seam-contracts, rel: relates-to }
review-by: "2026-10-17"
summary: >-
  Test Architect (Adversary Mode) review of W1-B against W0 rev 2 section 4 and R-87..R-93. The kill tests, the 26
  mutant map and the recovery table are strong. BLOCK on two controls that cannot fail as specified: the call-site
  classification test (its allowlist contradicts the tree and it has no red fixture) and the Windows no-fsync branch
  test (it overwrites the constant a mutant changes).
---

# Test Architect review: W1-B `docs/design/eval-atomic-publish.md` (branch `design/eval-atomic-publish`, `67e7dc83`)

Session `rv-ta-bd-e1e4`, 2026-10-03. Checked against W0 rev 2 section 4, the RV-DS review (not repeated), and code opened for this review: `archive.py:55-90`, `gateway/store.py:84,161`, `workspace.py:102`, `engine.py:496`, `cli.py:204`, `tests/test_mutate_check.py:704-720`, and a grep of `os.link|rename|replace|shutil.copytree` across `src/`. Verified = opened or run; Inferred = reasoned.

## The four points checked

| point | result |
| --- | --- |
| D1 and D3 red tests named and red today | Named (10.2). D3 is red on the naive helper by the stated protocol. **D1 is red for the wrong reason**: finding 1. |
| 26 mutants (M1-M26) map to killing tests | All 26 are named, and every one maps to a test (M10 to two). **Two mutants survive their own test** (findings 2, 5) and three behaviours have no mutant (finding 6). |
| `test_every_publish_call_site_is_classified` exists | Exists (10.4). **It cannot go green as specified and has no red fixture**: finding 3. |
| Windows no-fsync branch has its test | Test exists (`test_the_folder_fsync_runs_only_on_posix`). **It cannot kill the mutant that matters**: finding 2. |

## Findings

| # | location | finding | severity | evidence | fix | confidence |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 10.1 red-first, 10.2 D1 row, `test_a_corrupted_copy_fails_verification_before_the_rename`, `test_attempt_dirs_ignores_a_leaked_temp_sibling`, `test_recover_archive_...` | **The D1 test is red today, but not on the assertion the design names.** The child patches `archive._copy_hashed`, which does not exist in `archive.py` (functions: `_sha`, `_is_link`, `archive_hash`, `archive_cell`, `verify`, `make_writable`...). With a strict patch the child dies on `AttributeError`; the test is red without ever showing a partial `attempt-1` and an `HB-USR-002` redo, so "red today" proves nothing about D1. The same shape hits the corrupted-copy test (`_copy_hashed`), `attempt_dirs` and `recover_archive` (new symbols). The protocol gives X-B1 naive stubs (10.1) and X-B2 none. | major | `archive.py:55-80` (copy is inline `shutil.copyfile`, line 74); 10.1 last paragraph; 10.2 D1 row | X-B2's first commit patches an existing seam for the red step (`shutil.copyfile`), or adds stubs of the new symbols so the failure is on the assertion. State the red reason per test in the proof pack. | Verified |
| 2 | 3.2 `_POSIX`; `test_the_folder_fsync_runs_only_on_posix` (M14) | **The Windows branch test sets the very constant a mutant changes.** The test monkeypatches `atomic._POSIX` to False and True. A mutant `_POSIX = True` (or the comparison inverted) is overwritten by the patch, so it survives. The real default is exercised only by an unrelated baseline test, and only on Windows (where a directory fsync raises). On the POSIX CI job nothing pins that the default follows the platform. | blocking | 3.2 "module constant so a test can flip the fsync branch"; 10.2 M14 row | Add one test that asserts the default without patching it: `atomic._POSIX == (os.name == "posix")`, plus a Windows-only run of the real `publish_dir` asserting no `_fsync_dir` call (recorder on the real function). Keep the flip tests for the branch bodies. | Verified (design text) |
| 3 | 10.4 `test_every_publish_call_site_is_classified`; 12.1 sweep | **The control cannot go green as specified, and cannot be shown to fail.** (a) The scan lists `os.link/os.rename/os.replace/shutil.move/shutil.copytree`, but the allowlist omits real sites: `gateway/store.py:161` `os.rename` (`move_orphan`), and three `shutil.copytree` sites (`grade/correctness.py:207-208`, `grade/formal.py:280`, `grade/_changes.py:118`). (b) The allowlist names the "engine rejected-file rename", which is `path.replace(...)` at `engine.py:496`, a `Path` method the scan list does not cover, so that entry is stale or the scan is incomplete. (c) The sweep in 12.1 therefore missed at least the same sites. (d) No red fixture: nothing shows the scanner fails on a new `os.replace` site, an aliased import (`from os import replace`, `import shutil as sh`) or `Path.rename/replace`. (e) No check that an allowlist entry still matches a site. | blocking | grep over `src/harness_bench`; 10.4; 12.1 Sweep | Decide the scan's verbs (include `Path.rename/replace/hardlink_to` and `from x import` aliases) and classify every hit, including the copytree sites (grader scratch copies: reason `not a published name`). Add red fixtures: a synthetic tree with a new site per verb and per alias form; a stale allowlist entry; each fails. State root, recursion, tokens and allowlist constant in the doc comment (W0 section 10). | Verified |
| 4 | 11, `archive.recovered`, `atomic.rename_retry`, `atomic.create_once`, `atomic.publish_failed`; M21 | The design says "load-bearing telemetry has a test" but only `atomic.publish` and `atomic.temp_swept` are asserted. `rename_retries` (the operator's "how often does the OS refuse a rename" question) is only asserted to be an integer, so a mutant that hard-wires 0 survives. `archive.recovered` fields (`state`, `rows_appended`) are asserted nowhere. | major | 10.2 `test_publish_logs_one_record_with_phase_timings`; 11 | The open-handle test also asserts `rename_retries >= 1` and one `atomic.rename_retry` record; the recovery test asserts one `archive.recovered` with the right `state` per S2/S3/S4; one `publish_failed` case (`phase=verify`). Add the three mutants. | Verified (design text) |
| 5 | M15 (no retry), `test_a_rename_refused_by_an_open_handle_succeeds_once_it_closes` | The only test that shows a retry **succeeding** is Windows-only. On the POSIX job M15 is killed only through the exhaustion test, which counts attempts but never the success path. Also nothing kills a mutant that retries on `FileExistsError` (3.3 step 7 says it must propagate at once). | major | 10.2; 3.3 step 7 | Portable test: `os.rename` patched to raise `PermissionError` twice then succeed (sleep patched), publish succeeds with `rename_retries == 2`; and one that raises `FileExistsError`, expects one call and the error. Keep the real-handle test as the sibling (D7). | Verified (design text) |
| 6 | 10.2 vs 8 and 5 | Behaviours with no test and no mutant: (a) S6 (no final, rows present: `verify` must report `HB-LED-005`) is in the table in 5 but in no test; (b) F28 (missing parent) claims coverage by "setup" of a test that does not create that case; (c) `create_once` write or fsync failure mid-way (disk full) must leave no temp (3.3 step 5 `try/finally`); a mutant dropping the `finally` survives. | minor | 5 table S6; 8 F19, F28; 3.3 step 5 | Add S6 as a param of the recovery test, F28 as a one-line test, and a `create_once` case with `os.fsync` raising. | Verified (design text) |
| 7 | 10.4 `test_atomic_imports_only_stdlib_and_errors`; hypothesis on `is_temp_name` | The import-direction test has no red fixture (a synthetic `atomic.py` importing `archive` must fail). The hypothesis property for `is_temp_name` names no oracle, so it can only restate the regex. | minor | 10.2, 10.4 | Add the red fixture; give the property an independent oracle (build names from parts, assert membership). | Verified (design text) |

## What holds up (no finding)

The kill tests use a real child and `os._exit` over a real filesystem (D4). The four DS dispositions are restated as named tests (9). The recovery rule is one table (S0-S6) with a rebuild test that compares `archive_hash` to a fresh archive. The `bench verify` characterization step is placed before the stricter `verify` ships. `test_every_named_test_in_the_mutation_sets_exists` (`test_mutate_check.py:704`) does keep the mutant ids honest, so M1-M26 cannot rot silently once the JSON exists.

## Gate

`GATE W1-B · Test Architect · BLOCK · 7 findings (rv-ta-bd-e1e4, 2026-10-03)`

Clearing conditions: findings 2 and 3 (each is a control with no failing case). Findings 1, 4 and 5 should be resolved in the same follow-up; 6 and 7 may be recorded.
