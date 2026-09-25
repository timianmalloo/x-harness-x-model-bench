---
id: review-w2-views-codex
title: "W2-VIEWS cross-vendor join review"
type: decision-note
status: accepted
owner: "@timianmalloo"
links:
  - { to: coordination-finish-harness-bench, rel: relates-to }
review-by: "2026-10-09"
summary: >-
  Codex review of W2-VIEWS at 64d3392: the ruled validity and warning paths pass focused checks;
  a truncated native record can still expose partial time and call-count measures.
---

# W2-VIEWS join review — Codex

**Verdict: CONDITION.** The requested validity precedence, warning separation, mapped-model allowance, and truncated-record cost rule are implemented. Before this projection is treated as complete, resolve F1: an unreadable, truncated native record can still expose partial model time, tool time, idle time, and call count. This review covers `git diff 5feece0..64d3392` on `w2-views` at `64d3392`. The branch checkout at `C:\Projects\x-harness-x-model-bench-w2-views` was not edited. The verdict is based on the committed code and focused tests, not a live benchmark run.

## Findings

| ID | Evidence and judgment |
| --- | --- |
| F1 — partial measures after truncation | **Condition.** The grading pass writes extracted `model_calls` and `tool_calls` before it checks `record_unreadable` (`src/harness_bench/grade/runner.py:127-148`). The view suppresses token totals when `unrecorded` is set, but still passes those partial rows to `_model_time`, `busy_ms`, and `calls_per_cell`; `_idle` can then derive a value from the partial times (`src/harness_bench/views.py:360-377`). `_model_time` and `calls_per_cell` return numeric measures when the pre-cut rows are well formed (`src/harness_bench/views.py:213-220,236-240`). The HTML report displays model, tool and idle time, and the canonical export carries them (`src/harness_bench/report/html.py:184-188`; `src/harness_bench/views.py:463-470`). The truncated-record test proves that pre-cut calls were written, but checks only validity and tokens (`tests/test_views.py:497-504`); the cost test checks only cost (`tests/test_grade.py:355-369`). Gate these native-record-derived measures on unreadability and add a regression case with a truncated record containing complete pre-cut spans and calls. Wall time comes from lifecycle events and does not need that gate. |
| F2 — unreadable usage | **Yes for validity and tokens.** `_extract` distinguishes zero and multiple native records, while `record_unreadable` detects missing ordinal-0 fields and truncation (`src/harness_bench/grade/runner.py:127-130,145-148`; `src/harness_bench/telemetry/normalize.py:102-110`). The pass records each reason on `grading.completed` (`src/harness_bench/grade/runner.py:117-120`), which the view reads for the current pass (`src/harness_bench/views.py:299-308,354-364`). Each becomes `not recorded` / HB-VAL-003 before the empty-served-model HB-VAL-001 branch (`src/harness_bench/views.py:311-328`). Missing and multiple records are checked at `tests/test_grade.py:344-352` and `tests/test_views.py:488-494`; missing ordinal-0 fields at `tests/test_views.py:470-485` and `tests/test_grade.py:372-378`; truncation at `tests/test_views.py:497-504`. For Claude Code with `acp_usage: null` and no `turn_usage` rows, the view takes the same HB-VAL-003 branch (`src/harness_bench/views.py:306-307`; `tests/test_views.py:507-511`). A readable ACP report with no model still receives HB-VAL-001 (`tests/test_views.py:514-518`). |
| F3 — hook denial and precedence | **Yes.** `_validity` is the one state-selection function: invalidating cause, not graded, HB-VAL-004, HB-VAL-003, HB-VAL-001, HB-VAL-002, then valid (`src/harness_bench/views.py:311-328`). `normalize.hook_denials` counts only `outcome_code == "denied"` from the current extraction's tool rows (`src/harness_bench/telemetry/normalize.py:93-99`; `src/harness_bench/views.py:347-349,369-370`). The rev-92 fixture yields eight denials and HB-VAL-004; the rev-95 fixture is valid despite one ordinary failure (`tests/test_views.py:292-325`; `tests/fixtures/native/copilot/provenance.json`, `facts.on-rev92.readings.tool_outcomes` and `facts.on.readings.tool_outcomes`). A denial outranks a missing shutdown and HB-VAL-003 (`tests/test_views.py:315-319`). |
| F4 — warnings | **Yes.** HB-VAL-005 compares Copilot's ACP turn total with the current extraction's disjoint token buckets; absent ACP usage produces a warning saying the check did not run (`src/harness_bench/views.py:253-261,282-296,357-359`). HB-CELL-115 compares the verbatim `agent_version` with the adapter pin or harness pin; a missing version produces HB-VAL-006 (`src/harness_bench/views.py:264-279`). These populate `CellView.warnings` separately from the `_validity` call (`src/harness_bench/views.py:357-380`). Tests cover disagreement without a validity change, matching totals, skipped checks, adapter and harness pins, and nulls (`tests/test_views.py:349-373,419-459`). Warnings reach CLI, HTML and canonical export (`src/harness_bench/report/cli_table.py:45-49`; `src/harness_bench/report/html.py:145-147,187`; `src/harness_bench/views.py:470`). |
| F5 — mapped model | **Yes.** The plan freezes the task's `model_map` (`src/harness_bench/plan.py:136-140,234-237`); the view compares base model ids and allows an entry named there while still rejecting an unrelated model (`src/harness_bench/views.py:326-335`; `tests/test_views.py:386-393`; `tests/test_plan.py:144-153`). |
| F6 — cost and older ledgers | **Yes for the requested cost fix.** A native record marked unreadable cannot reach `cost.cost_usd`; a truncated record returns `None` with the truncation reason, rather than a price for pre-cut rows (`src/harness_bench/grade/runner.py:157-170`; `tests/test_grade.py:355-369`). The R-15 and R-24 reads use absent `unreadable_records` and absent `acp_usage` as old-ledger states (`src/harness_bench/views.py:299-308`). A direct read-back at `64d3392` of both absent-key forms returned `invalid (no model call)` / HB-VAL-001 when the served set was empty, matching the prior behavior. These compatibility forms lack a full-ledger regression test. |

The status parser accepts both new validity labels (`src/harness_bench/status.py:33-34`; `tests/test_status.py:60-73`). The HTML and CLI tests assert the rendered states and warnings (`tests/test_report.py:441-508`).

## Independent mutation probes

I created a detached throwaway worktree of `64d3392`. Its unmodified baseline passed `uv run pytest -q -p no:cacheprovider tests/test_views.py tests/test_grade.py tests/test_status.py`: **166 passed**. I applied each mutant alone, ran the named focused test, and restored the source before the next mutant. These are my review mutants, separate from `tests/mutations/validity.json`.

| Mutant | Result | Named killing test |
| --- | --- | --- |
| M1, `src/harness_bench/views.py:320-323`: move the HB-VAL-003 return before the hook-denial return. | **Killed:** expected HB-VAL-004, got HB-VAL-003. | `tests/test_views.py::test_a_hook_denial_outranks_an_unreadable_record` |
| M2, `src/harness_bench/grade/runner.py:165`: disable the unreadable-record cost branch, allowing a truncated record to be priced. | **Killed:** got `0.046454` instead of NA with the truncation reason. | `tests/test_grade.py::test_a_truncated_record_has_no_cost_from_a_partial_sum` |
| M3, `src/harness_bench/views.py:326`: remove the task `model_map` exception from mismatch detection. | **Killed:** got HB-VAL-002 instead of valid. | `tests/test_views.py::test_a_model_the_task_model_map_names_is_valid` |

After restoration, `tests/test_report.py tests/test_plan.py tests/test_errors.py` passed **101 tests**. The full suite, `tests/e2e`, and `-m ""` were not run. The throwaway worktree was removed after the probes.
