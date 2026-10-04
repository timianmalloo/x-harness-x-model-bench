---
id: brief-eval-time-b2
title: "Brief TIME-B2: the thirteen unaudited real-time tests, reproduced by forced delay and put under test-side time control"
type: plan
status: proposed
owner: "@timianmalloo"
links:
  - { to: coordination-eval-wave2-e1-briefs, rel: implements }
  - { to: brief-eval-time-b, rel: depends-on }
review-by: "2026-10-17"
summary: "TIME-B's scan allowlists 13 tests as UNAUDITED (12 in test_engine.py, 1 in test_oslock.py). For each: a forced-delay reproduction that fails on an assertion, then test-side time control (event-driven wait, injected clock or test-scaled bound), or a measured reason it cannot flip. Shipped bounds unchanged. Claude Sonnet, one session."
---

# TIME-B2: the unaudited real-time tests

**Session** `x-timeb2-e1e4` · **branch** `build/eval-time-b2` · **harness** Claude Code Agent tool, `model: sonnet` (served `claude-sonnet-5-5`, R-91) · **budget** 150 calls · 220k · 1 session · 2.5 h · **fallback** a Sonnet follow-on in the same tree for the entries left. No compile (a Sonnet track; E1 README §5).

**The class** (`docs/lessons/defect-classes.md`, **TIME-B**): a test asserts an outcome that holds only while real sleeps and real work keep their idle-machine order. TIME-B (merged `8b4cce33`) fixed the two observed instances and landed the scan `tests/test_timing_hygiene.py`. Its `TIMING_ALLOWED` names 13 entries with the reason `_UNAUDITED`: "real sleep or fake delay whose ordering against other real work is not proven load-safe; none measured failing". These are the next instances, unless a forced delay shows they cannot flip.

## The thirteen entries (from `TIMING_ALLOWED` on `main` `4561daea`)
In this order (the engine invariants that X-J1 and X-K1 extend come first):
1. `test_engine.py::test_no_launch_after_a_stop_while_another_cell_still_runs`
2. `test_engine.py::test_parallelism_is_never_exceeded`
3. `test_engine.py::test_the_run_waits_for_an_open_decision`
4. `test_engine.py::test_no_decision_after_a_launch_stop`
5. `test_engine.py::test_blocked_cell_default_continues_after_the_timeout`
6. `test_engine.py::test_keep_awake_is_held_through_a_stop`
7. `test_engine.py::test_a_worker_still_running_when_the_run_fails_is_refused_at_once_not_left_waiting`
8. `test_engine.py::test_an_engine_thread_failure_exits_the_process_and_leaves_no_cell_running`
9. `test_engine.py::test_after_the_ledger_breaks_no_worker_blocks_forever`
10. `test_engine.py::test_record_waits_through_a_full_inbox_and_a_slow_drain`
11. `test_engine.py::test_the_heartbeat_keeps_beating_after_a_failed_beat`
12. `test_engine.py::grade` (a helper; find which tests call it and what its sleep orders)
13. `test_oslock.py::test_heartbeat_advances_the_mtime`

The six `_UPPER` entries and the `_POLL`/`_HUNG` entries are **not in scope**.

## Rules
- **Test-side time control only.** No `src/` edit. A production clock seam is a seam request to the module's owner (E1 README §2: the request never parks you; build the test-side fallback).
- **Shipped bounds unchanged.** No product constant changes (engine tick, budgets, decision timeouts, heartbeat interval, lock timeouts). A bound **inside the test** may be scaled or replaced by an event.
- **Red first by forced delay, never by load.** For each entry, find the real-time order the assertion relies on. Force the bad order on an idle machine: a delay parameter on the fake, a monkeypatched hook, or a slowed step, sized so it reproduces the order load would produce. Commit that forced-delay variant as a test that fails **on an assertion** today (E1 README §2: never `ImportError`/`AttributeError`/`NameError`). Then the green commit: an event-driven wait (release the slow fake only after the condition is observed, bounded, failing by name), an injected clock, or a test-scaled bound. The forced-delay test and the original both pass after it.
- **When a forced delay cannot flip it.** Try at least the delay that inverts each pair of real-time steps in the test, and say which you tried. If none flips the outcome, the test is load-safe: keep its entry, replace `_UNAUDITED` with a reason that names the measurement ("forced delay of N s on <step> cannot change <assertion>: <why>"), and record it. That is a finding, not a failure.
- **Done means `_UNAUDITED` is gone.** At the end no entry uses it, and the constant is deleted (HYG-A: no dead code). Each fixed entry is removed from `TIMING_ALLOWED`; the scan's both-ways check (`test_no_allowlist_entry_is_stale`) proves the removal matches the tree.

## Owned paths, and who else is in these files
| file | yours | others in flight (2026-10-03, Coordinator #13) | rule |
| --- | --- | --- | --- |
| `tests/test_engine.py` | the twelve named functions and any fake or helper hunk that only they use | **X-D** owns the file in E1 (W0 §13). The X-D2 follow-on is open: `build/eval-x-d2` adds tests after `_events` (`:136`, +181) and one import line (`:28`); no timing hits (grep of its diff). **X-J1** owns `engine.py` in E2 (not dispatched). | Edit only the named functions. Disjoint hunks; rebase on `main` after X-D2 joins. **This track joins after X-D2.** A shared fake (`FakeLauncher`) hunk: one commit of its own, named in your report, so a conflict is one revert. |
| `tests/test_oslock.py` | `test_heartbeat_advances_the_mtime` only | **X-B1c** (Grok, dispatchable now) adds the `acquire_then_probe` tests. | Do this entry last, in its own commit. **This track joins after X-B1c.** |
| `tests/test_timing_hygiene.py` | `TIMING_ALLOWED` and the reason constants | Any track may add one entry for its own new test (E1 README §2, Coordinator #13). | The scan logic and its red fixtures stay as they are. |

**Not yours:** any `src/` file; `docs/lessons/defect-classes.md` (send the class text in your report); `tests/test_driver.py` (TIME-B's; no entry there is in scope).

## Depends on
TIME-B joined (`8b4cce33`) ✓. You may start now; the join waits for X-D2 and X-B1c (above). Nothing waits on this track.

## Acceptance items
1. Per entry: the forced-delay commit (SHA, node, the failing assertion line) and the green commit; or the delays tried and the measured reason it cannot flip.
2. `_UNAUDITED` is deleted; `uv run pytest -q tests/test_timing_hygiene.py` passes, and its two mutant tests (an entry removed, a stale entry) still fail as designed.
3. The full suite under `-n auto` passes **3 times in a row** on your final commit; each run's exit status on its own line in the report.
4. `git diff main -- src` is empty, and no product constant changed (say which constants you checked).
5. The defect-class text for the Coordinator: the mechanism per fixed entry (Verified by the forced delay), the entries proven load-safe, and the new count of allowlisted real-time tests.

## Exit
E1 README §3 join gate (including `uv run python tools/mutate_check.py --touched main`). Report per E1 README §4.
