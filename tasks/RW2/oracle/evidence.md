# RW2 oracle evidence

Status of RW2: `draft`. It stays `draft` until X-J1 (the multi-turn engine) and X-J2b (the rework grader and the multi-turn
discrimination path) have joined and a real-host discrimination record reproduces the `expected` block of `task.yaml`
(W1-L 5.3, W0 rev 6.6 R6.6c). The follow-on in this tree flips `status: ready`, runs `bench discriminate RW2` and commits the
folder and the record together (W0 section 2, the order of the `ready` flip).

Provenance per row: **traced** = derived from the committed source by hand before any run; **measured (stand-in)** = then
observed through `tests/fixtures/property_tasks/rework_standin.py`, which implements W1-L 5.1/6.1 on plain text because
`_changes.product_lines`, `line_delta`, `is_test_path` and `grade/rework.py` (X-J2) have not joined. A stand-in number is
Inferred (FIXT-A), never provenance. The hidden tests ran through the task's own oracle command under CPython 3.14.6
(`sys._base_executable` of the project environment, `-S`), and the pass/fail rows below also through the real
`correctness.grade`.

## Pinned base

- repo `https://github.com/dbader/schedule`, commit `82a43db1b938d8fdf60103bd41f329e06c8d3651` (MIT, `Copyright (c) 2013 Daniel Bader`).
- `git rev-parse 82a43db1b938d8fdf60103bd41f329e06c8d3651^{tree}` printed `113c0a93af441e26f0d7736ff48c5f1e60e03762` (fresh clone, 2026-10-03).
- pin tree: `113c0a93af441e26f0d7736ff48c5f1e60e03762`
- The base used by every test is built by the engine, `workspace.task_source(tasks/RW2, ...)`, over the pinned upstream
  (`upstream_tree` + `git archive`) with `tasks/RW2/workspace/.gitkeep` overlaid. `tasks/RW2/LICENSE` is the upstream MIT text.

## Test-path classification of the base (R2-2; data, W0 rev 6.6 section 13)

`test_schedule.py` is a test path under `_changes.is_test_path(path, base_paths)`: its basename matches `test_*.py`. Every
other `.py` file of the base is a product path; the base has no `tests` or `test` directory. Today
`test_base_test_layout_is_classified_as_data` checks this list against the stand-in rule over the engine-built base. The
follow-on asserts the same list through the real `is_test_path` (no `xfail`).

- test path: `test_schedule.py`
- product path: `docs/conf.py`
- product path: `schedule/__init__.py`
- product path: `setup.py`

## Solutions (overlays; assume: the final tree is base + `turn-1/` + `turn-2/`, a file in `turn-2/` replacing the same path)

Each solution ships `schedule/__init__.py` only. The prompts ask for tests in `test_schedule.py`; the overlays do not model
that edit, because test paths are excluded from every RW2 metric and no hidden test reads `test_schedule.py`.

| role | turn 1 | turn 2 |
| --- | --- | --- |
| reference | `Job.failures`, a `try/except` in `Scheduler._run_job` that calls one private `_record_failure(job, exc)` (count, log, reschedule) | `Scheduler.on_failure` and its list; `_record_failure` also iterates the callbacks and pauses on a `False` return or the third failure; `Job.paused`, `Job.resume`; the `should_run` guard; the log line now says how many in a row (the one turn-1 line turn 2 rewrites) |
| alt | the same behaviour held by a small `_FailureBus` that the scheduler owns | the bus gains `add` and the listeners and the pause rule; `Scheduler.on_failure` forwards to it |
| naive | the `try/except` and the counter inline in `_run_job` | the policy moves into `Job.run` (it reads the scheduler's callback list), and `_run_job` goes back to the base shape, so every turn-1 line in `_run_job` is rewritten |

W1-L 6.3 has the naive "edit the same block" in turn 2. Doing that only inserts lines, and a pure insertion scores a ratio of
0, which is the known blind spot (RQ-1) and would not separate the naive from the reference. The committed naive moves the
policy into `Job.run`, a plausible alternative design, which is a rewrite. This is recorded as a deviation (below).

## Turn-1-added product lines and the ratio (W1-L 6.1; B-RW2)

Traced by hand, then measured (stand-in).

- reference |T1| = 11: the `self.failures` line in `Job.__init__`; six lines of `_run_job` (`try:`, the re-indented `ret = job.run()`, `except Exception as exc:`, the call to `_record_failure`, `return`, `job.failures = 0`); four of `_record_failure` (`def`, `job.failures += 1`, the log line, `job._schedule_next_run()`). Turn 2 rewrites one: the log line. 1/11 = 0.0909.
- naive |T1| = 9: the `self.failures` line and eight of `_run_job` (`try:`, `ret = job.run()`, `except`, the log line, `job.failures += 1`, `job._schedule_next_run()`, `return`, `job.failures = 0`). Turn 2 moves them out, so eight are removed; the `self.failures` line survives. 8/9 = 0.8889.
- alt |T1| = 13, 0 changed, 0.0000 (below the ceiling).

- ratio reference: t1=11 changed=1 ratio=0.0909
- ratio naive: t1=9 changed=8 ratio=0.8889
- ratio alt: t1=13 changed=0 ratio=0.0000

Design targets: reference at most 0.1000 (met, 0.0909, close to the edge), naive at least 0.6000 (met, 0.8889), ceiling 0.3000.
The naive loses on the ratio clause alone: it passes all nine hidden tests. EV-4 through the engine is shown in the follow-on.

## Hidden tests (9) and the real grader

| solution | turn 1 on the snapshot | turn 1 and 2 on the final tree |
| --- | --- | --- |
| base (no change) | fails | fails |
| stub (`on_failure` and `resume` return a unique sentinel, `Job.failures` is the sentinel) | 3 of 3 fail on an assertion | 9 of 9 fail on an assertion |
| reference, naive, alt | 3 of 3 pass | 9 of 9 pass |

`correctness.grade` returned `passed=1` for each of the three solutions on both trees and `passed=0` on the base. The tests
make a job due by setting `job.next_run` themselves, and call `run_pending()` through a helper that turns an escaping exception
into an assertion failure, so a base that lets the exception out fails on an assertion, not by an error.

## Wrong apps (9)

Each is the final reference tree with one substitution; `oracle/wrong_apps.py` declares the exact set of tests it turns red,
each by an assertion failure. A rule that several tests share turns all of them red (`wa-pause2` pauses after two failures, so the flaky jobs of T1-3 and T2-5 never run their third time; `wa-count-once` breaks the counter, which
T1-2, T1-3, T2-3, T2-4 and T2-5 all read); the declared set says so.

## Variants (7)

`oracle/variants.py` is W0's one `VARIANTS` literal. For this check-less task `flips` lists metric ids whose observed value
differs from the reference's.

| variant | what it does | flips | deciding clause |
| --- | --- | --- | --- |
| `ratiohigh` | turn 2 edits the policy into the run loop: the `_record_failure` call becomes inline lines and the method is deleted | `property_check_pass`, `rework_ratio` | `ratio` |
| `t1regress` | turn 2 inserts a `break` after a failing job in `run_pending`, so later due jobs do not run (T1-1 only; a pure insertion) | `property_check_pass` | `turn1` |
| `t2short` | turn 2 reverted: the final tree is the snapshot | `property_check_pass`, `rework_ratio` | `tests` |
| `nohookorder` | callbacks run in reverse order | `property_check_pass` | `tests` (T2-1 only) |
| `ignorereturn` | the callbacks are called and their return value is ignored | `property_check_pass` | `tests` (T2-6 only) |
| `padturn1` | turn 1 and turn 2 both carry 20 dead lines in `_record_failure` | `rework_ratio` | none: it passes |
| `duplicate` | the new behaviour is a sibling method `_record_failure_v2` that nothing calls; `_record_failure` is untouched | `property_check_pass`, `rework_ratio` | `tests` (by test, with a ratio of 0) |

**R-W1 (named residual, reported with every rework result).** `padturn1` passes with a ratio (1/31 = 0.0323) below the
reference's (0.0909): padding turn 1 with dead lines grows the denominator. The ratio sees only turn-1 lines that turn 2
changes or deletes, so insertion-only work scores 0. `duplicate` is the named case: ratio 0, yet it fails the hidden tests
(T2-1..T2-4, T2-6), because its new behaviour is never called.

## Deviations from W1-L rev 2, each found by running

1. The naive moves the policy into `Job.run` instead of editing the same block (above).
2. `job.resume()` also sets `failures` back to 0, and turn 2's text says so: with the counter kept, the first failure after a
   resume would pause the job again, and a prompt that leaves that open lets two correct solutions differ.
3. The reference rewrites the log line in turn 2 (it now says how many failures in a row), so its ratio is a non-zero 1/11 and
   `padturn1` can show a lower one. Without one rewritten line the reference would score 0 and the residual could not be shown.
4. The latent-term scan covers `prompt.md` only. `turns/2.md` must say `Scheduler.on_failure(callback)`, which contains
   `callback`, a latent term; W1-L 6.3's turn-2 shape does the same.
5. T2-4 pauses the job by repeated failures and measures the pause point from the run count, so it does not depend on the
   threshold of three that T2-3 pins.

## What the follow-on needs

X-J1 and X-J2b joined; X-J2a's `_changes` functions joined (the stand-in file is then deleted and the tests call the real
functions); `status: ready`; `bench discriminate RW2` run on the real host through the multi-turn path; the record committed
with the folder; the `expected` values re-read against the record (they are Inferred until then, blocking item B-RW2).
