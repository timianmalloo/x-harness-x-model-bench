# E1 oracle evidence

All commands run on this Windows host, 2026-09-29, from `C:\Projects\x-harness-x-model-bench-w5-e1`
(worktree `w5-e1`) unless noted. The upstream repo was cloned once into a scratch directory outside
this repository (`C:\Users\malla\AppData\Local\Temp\claude\scratch-tb2\terminal-bench-2`); `git
rev-parse HEAD` there prints `2fd12b88aafdd04a52c298e3940bcb189f9766d6`, exactly the pinned commit.

## Toolchain versions

- `uv 0.11.26 (396ef7ce4 2026-06-30 x86_64-pc-windows-msvc)` (`uv --version`)
- `Python 3.13.14` (`uv run --no-project --python 3.13 python --version`; uv downloaded
  `cpython-3.13.14-windows-x86_64-none`, matching the upstream Docker image `python:3.13-slim-bookworm`)
- `pytest 8.4.1` (`uv run --no-project --python 3.13 --with pytest==8.4.1 pytest --version`; the exact
  version upstream's own `tests/test.sh` pins)
- `git 2.x` (host `git`, used for the clone, `git rev-parse HEAD` and `git archive`; version not
  separately recorded — no task requirement pins a git version)

## Vendoring rebuild (R-42 c3)

```
git -C <scratch clone> archive --format=zip 2fd12b88aafdd04a52c298e3940bcb189f9766d6 -- code-from-image/environment/code.png
```

Extracted `code-from-image/environment/code.png` and `tasks/E1/workspace/code.png` both hash to
`sha256:f4d0330407b363a9ef03d563e5c2ffd24aa76345f997613741f9fc0935354305` (95,041 bytes) — byte
identical. `tests/test_e1_vendoring.py::test_e1_workspace_matches_pinned_git_archive_byte_for_byte`
encodes this same rebuild and comparison; it is observed to pass when pointed at the scratch clone
(run manually with `SOURCE` retargeted during this authoring pass) and skips in the committed run
(`uv run pytest -q tests/test_e1_vendoring.py`: `1 passed, 1 skipped`) because no permanent local
clone exists at the conventional `C:/projects/terminal-bench-2` path — the same accepted class as
`test_task_vendoring.py`'s D1 test skipping when `C:/projects/ai-de` is absent.

## Reference algorithm reproduction

`oracle/reference/solve.sh`'s embedded Python (`sha256(sha256(code.png_bytes),
sha256(code.png_bytes)[:10], b"0000TBENCH-SALT")`, hex) was run directly against
`tasks/E1/workspace/code.png`:

```
bee26a133f103b9ecda444c70ec22cafef6e31a3de7af6d047974dc90ce3defe
```

Matches `tests/test_outputs.py`'s hardcoded expected value exactly, and is committed verbatim as
`oracle/reference/output.txt` (64 bytes, no trailing newline).

## Discrimination proof (Done when)

Oracle command (`task.yaml`'s `oracle.command`, run with `cwd` at the working-copy root, exactly as
`correctness.grade()` would run it once its pytest support merges):

```
uv run --no-project --python 3.13 --with pytest==8.4.1 pytest test_outputs.py --junitxml=e1.xml -v
```

### Fail on the base tree

Working copy: `workspace/code.png` + `tests/test_outputs.py` overlaid (no `output.txt`).

```
============================= test session starts =============================
platform win32 -- Python 3.13.14, pytest-8.4.1, pluggy-1.6.0
collected 2 items

test_outputs.py::test_output_file_exists FAILED                          [ 50%]
test_outputs.py::test_output_is_correct FAILED                           [100%]

================================== FAILURES ===================================
___________________________ test_output_file_exists ___________________________
AssertionError: File output.txt does not exist
___________________________ test_output_is_correct ____________________________
FileNotFoundError: [Errno 2] No such file or directory: 'output.txt'
=========================== short test summary info ===========================
FAILED test_outputs.py::test_output_file_exists - AssertionError: File output...
FAILED test_outputs.py::test_output_is_correct - FileNotFoundError: [Errno 2]...
============================== 2 failed in 0.26s ==============================
```

**Exit code: 1. Counts: 2 failed, 0 passed, 0 skipped, 0 errors, total 2.**
`e1.xml`: `errors="0" failures="2" skipped="0" tests="2"`.

### Pass on the reference solution

Working copy: `workspace/code.png` + `oracle/reference/output.txt` overlaid as `output.txt` +
`tests/test_outputs.py` overlaid.

```
============================= test session starts =============================
platform win32 -- Python 3.13.14, pytest-8.4.1, pluggy-1.6.0
collected 2 items

test_outputs.py::test_output_file_exists PASSED                          [ 50%]
test_outputs.py::test_output_is_correct PASSED                           [100%]
============================== 2 passed in 0.06s ==============================
```

**Exit code: 0. Counts: 2 passed, 0 failed, 0 skipped, 0 errors, total 2.**
`e1.xml`: `errors="0" failures="0" skipped="0" tests="2"`.

The oracle discriminates: 0/2 on the unmodified base tree, 2/2 on the reference solution's final
state, with the exact command `task.yaml` names.

## The disclosed grading-pipeline gap

`uv run python tasks/E1/oracle/grade_e1.py` (runs the same two trees through
`correctness.grade()`, the engine's own grading pipeline):

```
BASE_RESULT: Result(passed=None, partial_credit=None, reason="oracle runner 'pytest' not built (phase 1 runs unittest)", evidence='', compile_error=False)
REF_RESULT: Result(passed=None, partial_credit=None, reason="oracle runner 'pytest' not built (phase 1 runs unittest)", evidence='', compile_error=False)
```

Confirmed, not assumed: `src/harness_bench/grade/correctness.py` lines 150, 246 and 388 each gate on
`kind in ("unittest", "dotnet")`; `pytest` is not among them. The grader slice that adds pytest
support (reading a named JUnit XML report) is the Leader's parallel track, not merged into this
worktree. This is the one line for the Leader: **a live cell graded against E1 today reads NA
"oracle runner 'pytest' not built" from `correctness.grade()`, not a real pass/fail** — the
discrimination proof above is the direct pytest command, run and recorded independently of that gap.
Not in scope for this task folder (the correctness grader belongs to the Leader's slice).

## `bench validate`

```
$ uv run bench validate
ok: bom, metrics, example matrix and every task folder are valid
```

Exit code: 0. `validate_task()` (`src/harness_bench/config.py`) has no check on `oracle.runner`'s
value — that gate lives only inside `correctness.grade()` (above) — so `pytest` does not trip
validation; the "if it rejects runner pytest" branch in this task's Done-when did not fire, observed
by running the command, not inferred from reading the code alone.
