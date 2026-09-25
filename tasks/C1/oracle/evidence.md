# C1 oracle evidence

Grading copy matches `src/harness_bench/grade/correctness.py`: the tree under test, then `tests/test_c1_hidden.py` overlaid, cwd = that copy. Reference files stay in `oracle/reference/` and are not in `workspace/`.

## Fail on the base workspace

Command (cwd = copy of `tasks/C1/workspace` plus `tests/test_c1_hidden.py`):

```
python -m unittest -v test_c1_hidden
```

Exit code: **1**

Summary: `Ran 10 tests` / `FAILED (failures=2, errors=8)`

Failing names:

- `test_architecture_document_present` (FAIL) — `docs/architecture.md` missing
- `test_architecture_required_sections` (FAIL) — `docs/architecture.md` missing
- `test_custom_compare_min_heap` (ERROR) — `NotImplementedError` in `PriorityQueue.__init__`
- `test_merge_compare_failure_restores_both` (ERROR) — same
- `test_merge_moves_values_and_empties_other` (ERROR) — same
- `test_merge_with_empty_either_side` (ERROR) — same
- `test_pop_compare_failure_restores` (ERROR) — same
- `test_push_compare_failure_restores` (ERROR) — same
- `test_push_pop_is_max_heap` (ERROR) — same
- `test_top_size_empty_and_index_errors` (ERROR) — same

Same copy, targeted pytest (not the oracle runner; the runner is unittest):

```
uv run pytest -q --tb=line test_c1_hidden.py
```

Exit code: **1**. 10 failed. Same ten names.

## Pass on the reference

Command (cwd = copy of `tasks/C1/oracle/reference/` plus `tests/test_c1_hidden.py`):

```
python -m unittest -v test_c1_hidden
```

Exit code: **0**

Summary: `Ran 10 tests` / `OK`. No failing names.

Same copy:

```
uv run pytest -q --tb=line test_c1_hidden.py
```

Exit code: **0**. 10 passed.

## Validate

`uv run bench validate` exit 0: `ok: bom, metrics, example matrix and every task folder are valid`.
