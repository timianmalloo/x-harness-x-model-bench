---
id: "findings-t10-engine-mutation"
title: "Findings → tests: track T10 engine-mutation"
type: proof-pack
status: accepted
owner: "@timianmalloo"
phase: "Phase 1 · walking skeleton"
tags: [proof, findings, mutation, cosmic-ray, T10, engine]
links:
  - { to: coordination-phase1-finish, rel: relates-to }
  - { to: mutation-record-t1, rel: relates-to }
review-by: "2026-12-22"
summary: >-
  The Test Architect's required item: the 466 engine.py mutants T1 never ran. All 466 ran under cosmic-ray: 343
  killed, 62 killed after new tests, 61 argued equivalent, 0 open. One design drift was found and fixed red-first: the
  kill-retry backoff capped at 60 s against the design's 30 s (red 70531dc, fix e10b1e9). T10 also found that
  tools/mutate_check.py can leave a stale mutant .pyc.
---

# T10: engine-mutation

**The Coordinator transcribed this file** from the track's report. **The Coordinator also checked the evidence directly:**
- The red `70531dc` is test-only. Re-run in a fresh worktree, it failed at index 6 with `32.0 != 30`.
- The fix `e10b1e9` is the one line `KILL_RETRY_CAP = 60.0` → `30.0`.
- The T10 diff otherwise touches only tests.
- Three T10 dispositions were spot-checked with `tools/mutate_check.py` at `ea012a4`:
  - L53 `39 → 40`: killed by `test_a_windows_disk_full_error_is_a_full_disk`;
  - L231 `< → <=`: killed by `test_free_space_exactly_at_the_floor_is_not_below_it`;
  - L552 `> → >=`: argued equivalent, and it survived, as argued.

## Result
All 466 mutants run: 343 killed, 62 killed after new tests, 61 equivalent, 0 open. Per-function detail and every equivalence argument are in `docs/notes/mutation-record-t1.md`, "Engine, the remaining 466 (T10)".

## Defect: the kill-retry backoff cap drifted from the design
- **Design:** `phase1-walking-skeleton.md:189` says "Retries use capped exponential backoff (1 s doubling to 30 s)".
- **Code:** `KILL_RETRY_CAP = 60.0` since `3d14c73` (T1-8), with no recorded reason. The waits observed were 1, 2, 4, 8, 16, 32, 60, 60.
- **Red:** `70531dc`, `tests/test_engine.py::test_an_unconfirmed_kill_backs_off_from_1_s_doubling_to_the_designs_30_s_cap`.
- **Fix:** `e10b1e9`. The Coordinator admitted this one-line scope change: the design is authoritative, and the drift had no recorded reason.
- The existing `test_an_unconfirmed_kill_is_logged_once_and_retried_with_capped_backoff` reads `engine.KILL_RETRY_CAP` and still passes.

## Tests added (test-only commits `a9800c3`, `ea012a4`, `7cdea3f`, `599d4df`)
The survivor-killing tests are listed per mutant in the mutation record. `tests/mutations/engine.json` gained 5 entries: 4 `_classify` precedence cases and the cap. 49 of 49 are killed.

## Found en route
- **[Major, Verified] `tools/mutate_check.py` can leave a stale mutant `.pyc`.**
  - A size-preserving mutation (`30.0` ↔ `60.0`), whose named test ran in under a second, was restored in the same mtime second.
  - Python's mtime+size check then accepted the mutant's bytecode, and the next full `pytest` in that tree ran the mutant while `git status` was clean.
  - The Coordinator owns that tool (T7) and fixes it red-first; see the defect register, class TOOL-A.
- **[Observed]** Winerror 112 in `DISK_FULL_WINERRORS` never decides anything, because CPython maps it to errno ENOSPC.
- **[Observed]** If the engine thread raises while a turn hangs, the cell lives until process exit, when the Job's kill-on-close fires. This is now pinned by a test.

## Gates (track-reported; the join's recount re-measures them)
- `pytest -m "not credentials"`: 563 passed, 5 deselected, after the stale `.pyc` was removed;
- `ruff`: clean;
- `engine.json`: 49/49.
