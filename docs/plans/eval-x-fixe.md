---
id: plan-eval-x-fixe
title: "X-FIXE: the double-run guard on the check-less shape"
type: doc
status: proposed
owner: "@timianmalloo"
summary: "SHAPE-A sweep row 4: a check-less property.json carries the top-level hidden_tests_pass and hidden_tests_ms, and discriminate runs the hidden-test disagreement item for a check-less task."
tags: [evaluation, property, execution-plan]
links:
  - { to: design-eval-seam-contracts, rel: depends-on }
review-by: "2026-10-20"
---

# X-FIXE execution plan

Goal: the double-run guard of W0 R-90 condition 3 covers the check-less property tasks
(rework, no-guessing, simplicity). Done when F1 and F2 each have a red and a green commit and the
R-104 worker gates are read. Not in scope: `grade/noguess.py`, `grade/diffstats.py`, `grade/rework.py`,
`readiness.py`, task folders, the design docs. Tier T1; fan-out cap zero.

## F1: the property grader writes the top-level evidence

- Red `6696c9e1`: `AssertionError: assert None == {'reason': None, 'value': 1}` where the left side
  is `doc.get('hidden_tests_pass')`. Test: `tests/test_property_grade_cell.py::test_a_check_less_cell_carries_the_top_level_hidden_tests_pass`.
- Green `39ceaa97`: `property.lift_hidden_tests(inp)` runs at the end of `grade_cell`. It copies the one
  `strategy.<name>.hidden_tests_pass` to the top level. `hidden_tests()` times its single
  `correctness.grade` call and writes `<label>/hidden_tests_ms`; the lift reads it into `hidden_tests_ms`.
  The test counts `correctness.grade` calls: exactly one (R-90 condition 2). Nothing copies `pass_at_1`.
- Mutant (`tests/mutations/property.json`, commit `1bd8f1fb`): the `lift_hidden_tests(inp)` call replaced by
  `pass`. Killed. The whole file ran once: every mutation killed.
- Finding 1: `hidden_tests_ms` was written nowhere in `src/` before this item, for check-based cells too
  (R-90 condition 3 and W0 section 3 name it). This item adds it for the check-less shape only. The check-based
  `_hidden_check` evidence (`grade/property.py` evidence dict, about line 520) still has no `hidden_tests_ms`.
- Finding 2: `grade/rework.py:175` runs the final-tree hidden tests (`final_tests`) but its section
  (`write_section` at line 239) never records the value, so a rework cell has no top-level `hidden_tests_pass`
  and cannot be compared. The fix is one key in rework's section, a seam request to the rework owner.
  Rework's `property_check_pass` also reads NA "not built" in the fixture runs, with no `property.json`.

## F2: discriminate runs the double-run item for a check-less task

- Red `b4dd5267`: `Failed: DID NOT RAISE BenchError`. Test:
  `tests/test_discriminate.py::test_a_check_less_trial_fails_on_a_hidden_test_disagreement`. It reports a
  disagreement through `readiness.comparable_cells` for the check-less fixture DISC-C and expects HB-RDY-011
  "hidden tests disagree with pass_at_1 in <label>".
- Green `e282d1bf`: `_double_run_items(run_dir, grading_id, labels, spans=...)` is the one place the items are built.
  `_evidence_items` calls it with `spans=True`; the check-less branch of `run` calls it with `spans=False`.
  `readiness.comparable_cells` is unchanged.
- Mutant (commit `1bd8f1fb`): the check-less call replaced by `pass`. Killed.

### Applicability of each item on the check-less shape

- Hidden tests disagree with pass_at_1: applies, and now runs for every task.
- Not comparable (a side is NA): does not run on the check-less shape, because a check-less cell with no hidden-test
  value is NA by its own score row (and rework and a not-built strategy write no top-level value), which
  `_untrustworthy` already holds to the closed NA reason set; running it would fail every rework trial on Finding 2.
  Once Finding 2 is fixed, the item can be switched on for the check-less shape by splitting it from `spans`.
- A span with `unbiased_ok` false: does not apply, because a check-less pass records no `spans` (the spans belong
  to the hidden check's two phases).
- A case `timeout` that nothing declares and the evidence-presence item ("no check evidence found"): do not apply,
  because a check-less pass has no `cases` and no check evidence pointer.

## Gates

See the hand-back report for the exit statuses as read.
