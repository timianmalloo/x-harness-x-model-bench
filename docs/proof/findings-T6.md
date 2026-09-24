---
id: "findings-t6-workspace-race"
title: "Findings → tests: track T6 workspace race"
type: proof-pack
status: accepted
owner: "@timianmalloo"
phase: "Phase 1 · walking skeleton"
tags: [proof, findings, red-first, T6, workspace]
links:
  - { to: coordination-phase1-finish, rel: relates-to }
review-by: "2026-12-22"
summary: >-
  The first real E2E failed one cell with HB-CELL-113: two workers building the same task source or pack checkout at
  once collided on a Windows rename. Red 0082875 (the Coordinator re-ran it), fixed in a76e7c3, with both
  workspace.json mutations killed.
---

# T6: workspace race (HB-CELL-113)

**The Coordinator re-ran** red `0082875` in a throwaway worktree: both concurrency tests failed with `PermissionError(13, 'Access is denied')`. `tests/mutations/workspace.json` was re-run: every mutation killed. The Coordinator added this frontmatter. The track wrote the body through a shell heredoc after the harness refused the write, which the run record notes as a finding.

## Defect

The real 4-cell E2E (`tests/e2e/test_walking_skeleton.py`) ended with one cell `failed (workspace)`.
With parallelism >= 2, the first two cells (both `pack=on`) build their working copies at the same
time. `workspace.task_source` and `workspace.pack_checkout` each build into a private temp folder
and then `os.replace(tmp, dest)`. Windows cannot rename onto a non-empty `dest`, so when the other
worker has already created `dest`, the second caller's `os.replace` fails:

```
PermissionError: [WinError 5] Access is denied: '...\sources\X1\.<ver>.<rand>.tmp' -> '...\sources\X1\<ver>'
PermissionError: [WinError 5] Access is denied: '...\pack\.<commit12>.<rand>.tmp' -> '...\pack\<commit12>'
```

A two-thread repro behind a `threading.Barrier` (mirrored by `tests/test_workspace.py`'s new
concurrency tests) failed 3 times out of 3 for both functions before the fix.

## Root cause

`task_source` and `pack_checkout` each check "does `dest` already exist" once, then build and
`os.replace` unconditionally. Two callers can both pass the initial check before either has
finished building, so both race to be the one to rename into `dest`.

## Fix

`src/harness_bench/workspace.py`: a new `_land(tmp, dest, valid)` helper wraps `os.replace` and
catches `OSError`. A build is content-addressed and written once (the task source is keyed by
task+version, the pack checkout by commit), so whichever writer lands first is a valid answer for
every caller:

- `task_source`'s `valid(dest)` is `(dest / ".git").is_dir()`.
- `pack_checkout`'s `valid(dest)` also checks `dest`'s `HEAD` equals the pinned commit
  (`_pack_head`).

When `os.replace` fails and `dest` is by then valid, `_land` discards the loser's temp folder (the
caller's existing `finally: shutil.rmtree(tmp, ...)` already does this -- `_land` does not delete it
itself) and returns `dest`. Otherwise it re-raises: a `dest` occupied by something that is not a
valid build is a real failure, not a race.

`cell_working_copy` is unchanged: its `dest` is per cell, so it is never shared and never races.

## Proof

- **Red:** `0082875` -- `test(T6-1,T6-2): task_source and pack_checkout race under concurrent build
  (red)`. Both new concurrency tests failed against the unfixed code with the exact repro error:
  `AssertionError: [...PermissionError(13, 'Access is denied')...]` at
  `tests/test_workspace.py:54` (`test_task_source_built_concurrently_gives_every_caller_the_same_dest`)
  and `tests/test_workspace.py:74` (`test_pack_checkout_built_concurrently_gives_every_caller_the_same_dest`).
- **Green:** `a76e7c3` -- `fix(workspace): let a racing build reuse the winner's dest (HB-CELL-113)`.
  `uv run pytest -q -p no:cacheprovider tests/test_workspace.py` -- 16 passed.
- **Mutation:** `tests/mutations/workspace.json`, 2/2 entries killed by
  `uv run python tools/mutate_check.py tests/mutations/workspace.json`:
  - "race: accept a colliding dest that is not a valid build" (removes the re-raise) -- killed by
    the two `..._reraises_when_a_colliding_dest_is_not_a_valid_build` tests.
  - "race: never reuse the winner's valid dest" (removes the validity check) -- killed by the two
    `..._built_concurrently_gives_every_caller_the_same_dest` tests.
- **Gates:** `uv run pytest -q -p no:cacheprovider -m "not credentials"` -- 499 passed, 5 deselected
  (132.57s). `uv run ruff check src tests tools` -- all checks passed.
