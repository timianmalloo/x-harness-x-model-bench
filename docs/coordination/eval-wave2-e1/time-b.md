---
id: brief-eval-time-b
title: "Brief TIME-B: two load-sensitive timing tests made deterministic, and the scan that keeps the class out"
type: plan
status: proposed
owner: "@timianmalloo"
links:
  - { to: coordination-eval-wave2-e1-briefs, rel: implements }
review-by: "2026-10-17"
summary: "Reproduce, then fix, the two tests that fail under full-suite -n auto load (an injected clock or an event-driven wait), and add a scan test for real-sleep and wall-clock assertions under tests/ with a named allowlist; Claude Sonnet, one session."
---

# TIME-B: load-sensitive timing tests

**Session** `x-timeb-e1e4` · **branch** `build/eval-time-b` · **harness** Claude Code Agent tool, `model: sonnet` (served `claude-sonnet-5-5`, R-91) · **budget** 60 calls · 120k · 1 session · 1 h · **fallback** a fresh Sonnet session from this brief. Routed to Sonnet, not Grok: no compile or Grok slot is needed, and the two Grok slots carry X-G1 and X-B1.

**The class** (`docs/lessons/defect-classes.md`, **TIME-B**, candidate; sibling of TIME-A): a test asserts an outcome that holds only while real sleeps and real work keep their idle-machine order. Evidence (Leader, 2026-10-03): in two full-suite runs (`-n auto`, about 2,240 tests) on worker trees, `tests/test_engine.py::test_the_breaker_leaves_running_cells_running` failed in both and `tests/test_driver.py::test_every_message_type_the_fake_emits_is_paired_and_every_pairing_is_emitted` failed in one; on `main` the two files alone under `-n auto` passed 245 of 245, three times. The mechanism of each failure is **Inferred** until you reproduce it.

## Owned paths
`tests/test_engine.py`: the function `test_the_breaker_leaves_running_cells_running` only, plus a `FakeLauncher` hunk only if the event-driven wait needs one (disjoint from X-D's hunks; X-D owns the file in E1, W0 §13). `tests/test_driver.py`: the function `test_every_message_type_the_fake_emits_is_paired_and_every_pairing_is_emitted` and its fake's hooks only. `tests/test_timing_hygiene.py` (new). **Not yours:** any `src/` file (a production clock seam is a seam request to the module's owner), `docs/lessons/defect-classes.md` (send the class text in your report).

## Depends on
**X-D1 joined** (you edit one function of X-D's test file; start from a base that has its hunks). Nothing waits on this track.

## Work
1. **Reproduce, red first, deterministic.** For each test, find the timing it relies on (read the test and its fake; for the breaker test, the slow cell's real `sleep: 3` against the four `provider_error` cells and the breaker). Force the bad order without load: a forced delay in the fake (a parameter or a monkeypatched hook) that makes the slow path finish first or the other work arrive late. Commit the forced-delay variant as a test that fails **on an assertion** today. If a test cannot be made to fail by a forced delay, stop for that test and report what you measured.
2. **Green.** Replace the dependence on real time: an injected clock, or an event-driven wait (the test releases the slow fake only after the condition it asserts on is observed, with a bound that fails by name). The forced-delay test and the original test both pass.
3. **The control.** `tests/test_timing_hygiene.py` scans `tests/**/*.py` with `ast` for `time.sleep(` calls, real-sleep parameters passed to fakes (`"sleep"` keys, `sleep=`/`delay=` keywords), and assertions on differences of `time.monotonic()`/`time.time()`/`perf_counter()`. Every hit must be in a named allowlist constant `TIMING_ALLOWED: Mapping[str, str]` (`"<file>::<function>"` → reason), checked against the tree both ways (an entry that no longer matches fails). Red fixtures: one temp file per form, plus one that must not match (a sleep inside a fake's own module that a test does not assert on). Seed the allowlist from the sweep below, with a reason per entry; do not fix tests beyond the two named ones.

## Acceptance items
1. Per named test: the forced-delay reproduction fails on an assertion before the fix (SHA, node, assertion line in your report) and passes after it.
2. The full suite under `-n auto` passes 3 times in a row on your final commit (each run's exit status on its own line in the report).
3. `tests/test_timing_hygiene.py` fails on each red fixture, passes on the tree, and fails when an allowlist entry is removed or goes stale (two mutants).
4. **Sweep, recorded in the report:** every hit of the scan, by file, with its classification (clock-controlled, event-driven, or allowlisted with reason). The count is the sweep's output, not an estimate.
5. The defect-class text for the Coordinator: the mechanism per test (now Verified by the reproduction), the sweep result, the control, status `controlled` proposed.

## Exit
README §3 join gate. Report per README §4.
