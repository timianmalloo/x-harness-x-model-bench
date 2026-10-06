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
- Not comparable (a side is NA): **updated in part 2 (P3, CR47-1): now runs on the check-less shape** (it is split from
  `spans`; `unbiased_failures` stays check-based only). Part 1 held it off because rework wrote no hidden value
  (Finding 2); P1 fixed that.
- A span with `unbiased_ok` false: does not apply, because a check-less pass records no `spans` (the spans belong
  to the hidden check's two phases).
- A case `timeout` that nothing declares and the evidence-presence item ("no check evidence found"): do not apply,
  because a check-less pass has no `cases` and no check evidence pointer.

## Part 2 (Claude Code Sonnet, `x-fixe-e1e4`, CR47-1 to CR47-4, CR47-7)

Split by the CEIL-A rule: P1, P2 and P3 done; P4 (declared case timeout) not started, the context reading after P3 was
155k, above the 133k start limit.

| Item | Red SHA and failing lines | Green SHA | Mutant |
|---|---|---|---|
| P1 rework section records `hidden_tests_pass` | `94f139bc`: `assert None == {'value': 1, 'reason': None}` (multi-turn test); `assert None == {'value': None, 'reason': 'no working copy in the archive'}` (section-pointer test); `DID NOT RAISE BenchError` (flaky final-tree trial) | `c37bfc8c` | rework.json: key deleted from the section |
| P2 check-based `hidden_tests_ms` | `d75f424f`: `assert False + where False = isinstance(None, int)` | `75d627b7` | property.json: key removed |
| P3 not-comparable item for check-less | `7e6ed2a2`: `DID NOT RAISE BenchError` | `98f09423` | property.json: check-less item disabled |

- Order of the hidden-test runs read (P1 counter fixture, `tests/fixtures/property_tasks/make_task.py` `T2_COUNTER_TESTS`):
  the correctness grader's pass first (counter run 1, odd, pass), then per cell rework's turn-1 snapshot run (turn-1 tests
  only, so never the counter test), then the property grader's one final-tree run (counter run 2, even, fail); the cells
  alternate. The trial raised HB-RDY-011 "hidden tests disagree with pass_at_1" with no monkeypatch.
- Deleted test: `test_a_check_less_trial_fails_on_a_hidden_test_disagreement`; it wrapped `readiness.comparable_cells`
  and caught nothing the real fixture does not. The part 1 mutant "check-less double-run item call deleted" now targets
  `test_a_check_less_trial_with_a_flaky_final_tree_fails_on_a_hidden_test_disagreement`.
- Changed DISC-C tests (P3): the shared `first` fixture and its tests (without_a_host, overlay_lands, record_body,
  reconciliation, started/finished) moved to DISC-T; `test_no_link_after_hb_rdy_010` runs on a turns-based `disc_flaky`;
  the variant-without-strategy test stays on DISC-C and asserts the not-comparable item (finding: the variant item is
  reached only when no other item exists, so it cannot fire in a trial).
- Not checked: a real trial of RW1, RW2, NG1, NG2, SM1 and SM2 under the new item (no real-task trial was run in this turn).

## Gates

See the hand-back report for the exit statuses as read.
