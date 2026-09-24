---
id: "findings-t9-cleanup-and-log"
title: "Findings → tests: track T9 cleanup-and-log"
type: proof-pack
status: accepted
owner: "@timianmalloo"
phase: "Phase 1 · walking skeleton"
tags: [proof, findings, red-first, T9, workspace, engine, logging]
links:
  - { to: coordination-phase1-finish, rel: relates-to }
review-by: "2026-12-22"
summary: >-
  Two loop-back defects found by the third real E2E. T9-1: the loser of a build race left its temp folder on
  disk, because git writes read-only object files on Windows and rmtree(ignore_errors=True) failed silently.
  T9-2: engine.configure_logging added a FileHandler per call, so runs in one process wrote into each other's
  engine.log and a finished run's log stayed open. Red e225ff5, fixed in 7f962fb, all three t9.json mutations killed.
---

# T9: cleanup-and-log (two loop-back defects)

**The Coordinator transcribed this file** from the track's report, because the harness refused the track's write. **The Coordinator also checked the evidence directly:**
- The red commit `e225ff5` was re-run in a throwaway worktree. All four new tests failed for the stated reasons:
  - the two leftover `.tmp` folders;
  - `'after B'` found in A's log;
  - `PermissionError: [WinError 32]` when deleting the run's `engine.log`.
- `tests/mutations/t9.json` was re-run: every mutation was killed.
- The diff was read. `engine.py` changes only inside `configure_logging`, so the T1 cosmic-ray record is unaffected: that function is outside the record's scope.

## Defect 1: a lost build leaves its temp folder behind

### Symptom
After the third real E2E (`C:/Projects/bench-test/e2e-1790237978`), `cells/.sources/X1/.b7a29e0336256765.ef3efb55.tmp/.git/objects/...` was still on disk. It was the losing build of the T6 race over the same `task_source` destination.

### Root cause
`workspace.task_source` and `workspace.pack_checkout` removed their temp build in `finally` with `shutil.rmtree(tmp, ignore_errors=True)`. Git writes its object files read-only on Windows, so `rmtree` could not delete them, and `ignore_errors=True` swallowed the `PermissionError`.

### Fix
`workspace.py` gets a `_discard(tmp)` helper. It runs `shutil.rmtree(tmp, onexc=archive.make_writable)`, the idiom already used at `archive.py:103` and `:119`, inside `try/except OSError: pass`.

**Decision: a cleanup failure is still swallowed.** `_discard` runs in a `finally` that may already be carrying a real build exception. A cleanup error raised there would replace that exception and hide it. `make_writable` now fixes the everyday case, read-only git objects. The swallow remains only for the rare case, such as a file another process holds.

## Defect 2: engine log handlers accumulate across runs in one process

### Symptom
Each call to `engine.configure_logging(run_dir, trace_id)` added a `logging.FileHandler` and never removed the previous one. So in one process:
- run B's lines also landed in run A's `engine.log`;
- run A's `engine.log` stayed open and could not be deleted on Windows.

The open file was the second reason the E2E folder was left behind.

### Fix
- `configure_logging` records the handler it installed as an attribute of itself (`configure_logging._installed`).
- On each call, it removes and closes the previous handler before adding the new one. It now returns the new handler.
- `cli.cmd_run` removes and closes that handler in a `try/finally` around the engine run.

## Proof
- **Red:** `e225ff5`.
  - T9-1: `tests/test_workspace.py::test_task_source_built_concurrently_leaves_no_tmp_folder_behind` failed at `tests/test_workspace.py:82` with a leftover `.tmp` path, and `::test_pack_checkout_built_concurrently_leaves_no_tmp_folder_behind` failed at `:92` the same way.
  - T9-2: `tests/test_engine.py::test_configure_logging_replaces_the_previous_handler` failed at `tests/test_engine.py:635` with `assert 'after B' not in ...`. `tests/test_cli.py::test_run_closes_its_engine_log_handler_so_the_file_is_deletable` failed at `tests/test_cli.py:198` with `PermissionError: [WinError 32]`.
- **Fix:** `7f962fb`. All four tests pass.
- **Mutation:** `tests/mutations/t9.json` has 3 entries, and all 3 are killed:
  - `_discard` loses `make_writable`;
  - `configure_logging` stops releasing the previous handler;
  - `cmd_run` stops releasing its handler.
- **Gates (track-reported; the join's recount re-measures them):**
  - `pytest -m "not credentials"`: 505 passed, 5 deselected;
  - `ruff`: clean.

## Other `ignore_errors=True` sites (the sweep; named, not fixed)
None of these is in the product's source (`src/`):
- pack scripts: `docs/ai-forward-pack/scripts/graphify-setup.py:531` and `pack-apply.py:421` (vendored);
- test fixtures and teardowns:
  - `tests/conftest.py:23` (the `base` fixture);
  - `tests/test_workspace.py:159`;
  - `tests/test_profiles.py:143`;
  - `tests/fixtures/ledger/make_fixture.py:61-62`;
- `tests/e2e/test_walking_skeleton.py:103`: the Coordinator fixes this in T7.

The test teardowns explain most of the ~170 folders left under `C:/Projects/bench-test`. They are a residual for the human; the permission check refused deleting them in this session.
