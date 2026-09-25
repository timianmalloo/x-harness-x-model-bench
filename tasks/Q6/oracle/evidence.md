# Q6 oracle evidence

Grading copy matches `src/harness_bench/grade/correctness.py`: the tree under test, then `tests/test_q6_hidden.py` overlaid, cwd = that copy. The base workspace is empty apart from `README.md`. Both files the hidden tests read are created during the turn, so the pass case is a throwaway copy with those two files added, not a reference tree.

## Fail on the empty workspace

Command (cwd = copy of `tasks/Q6/workspace` plus `tests/test_q6_hidden.py`):

```
python -m unittest -v test_q6_hidden
```

Exit code: **1**

Summary: `Ran 2 tests` / `FAILED (errors=2)`

Failing names:

- `test_delegated_txt` (ERROR) — `delegated.txt` is missing
- `test_main_txt_is_the_model_id` (ERROR) — `main.txt` is missing

## Pass when both files are added

Command (cwd = throwaway copy of the empty workspace plus `tests/test_q6_hidden.py`, with `delegated.txt` containing the single line `written by a sub-agent` and `main.txt` containing the single line `gpt-6-luna`):

```
python -m unittest -v test_q6_hidden
```

Exit code: **0**

Summary: `Ran 2 tests` / `OK`. No failing names.
