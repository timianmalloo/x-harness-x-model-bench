# E4 oracle evidence

Grading matches `src/harness_bench/grade/correctness.py`: the tree under test (a fresh clone of
`source.repo`@`source.commit`, or that clone with `oracle/reference/` overlaid), with `tasks/E4/tests/`
overlaid, executed in its disposable working directory. Produced by `uv run python
tasks/E4/oracle/grade_e4.py` on this Windows host, 2026-09-29.

Oracle runner: `unittest` (`src/harness_bench/grade/correctness.py`, `parse_unittest`)
Command:
`uv run --python 3.8 --with-editable . --with docutils python tests/runtests.py -v2 admin_docs.test_utils.TestUtils.test_description_output admin_docs.test_utils.TestUtils.test_initial_header_level admin_docs.test_utils.TestUtils.test_parse_docstring admin_docs.test_utils.TestUtils.test_parse_rst admin_docs.test_utils.TestUtils.test_publish_parts admin_docs.test_utils.TestUtils.test_title_output admin_docs.test_utils.TestUtils.test_parse_rst_with_docstring_no_leading_line_feed`

Runner script: `tasks/E4/oracle/grade_e4.py`

## Fail on the base workspace

Grading call: `correctness.grade(ws_base, task_dir, oracle, out_base, tmp, timeout=300.0)`, where
`ws_base` is a fresh `git clone` of `https://github.com/django/django.git` checked out at
`e8fcdaad5c428878d0a5d6ba820d957013f75595`, unmodified.

Result:
```python
Result(passed=0, partial_credit=Decimal('0.8571428571428571428571428571'), reason=None,
       evidence='out_base/oracle.log', compile_error=False)
```

Exit code: **1**

Summary from stderr (`parse_unittest`): `Ran 7 tests in 0.118s` / `FAILED (failures=1)` — 6/7 passed.

The one failure is the FAIL_TO_PASS test:
```
FAIL: test_parse_rst_with_docstring_no_leading_line_feed (admin_docs.test_utils.TestUtils)
AssertionError: '<div class="system-message">\n<p class="sy[270 chars]v>\n' != '<p>second line</p>\n'
```

The 6 PASS_TO_PASS tests all pass on the base: `test_description_output`,
`test_initial_header_level`, `test_parse_docstring`, `test_parse_rst`, `test_publish_parts`,
`test_title_output`.

## Pass on the reference solution

Grading call: `correctness.grade(ws_ref, task_dir, oracle, out_ref, tmp, timeout=300.0)`, where
`ws_ref` is `ws_base` (a second copy, `.git` excluded) with `oracle/reference/` overlaid — the two
gold-patched files (`django/contrib/admindocs/utils.py`, `django/contrib/admindocs/views.py`) at
their real repo-relative paths.

Result:
```python
Result(passed=1, partial_credit=Decimal('1'), reason=None, evidence='out_ref/oracle.log',
       compile_error=False)
```

Exit code: **0**

Summary from stderr (`parse_unittest`): `Ran 7 tests in 0.090s` / `OK` — 7/7 passed, including the
previously-failing `test_parse_rst_with_docstring_no_leading_line_feed`.

## Timing (reference solution's own time; budget.minutes: 60)

- `uv run` cold (`uv venv --python 3.8` had never fetched that interpreter on this host): first
  invocation downloaded `cpython-3.8.20-windows-x86_64-none` (~20.6 MiB) — a few seconds, one time.
- Warm-cache `uv run` (both `grade_e4.py` calls above; also measured standalone under `env -i` with
  only `HOST_ENV` + the three `PYTHON*` vars set, matching the grading step's real environment
  allowlist): base run **1.068 s** real, reference run **3.826 s** real (wall clock, `time` on this
  Windows/Git-Bash host).
- Both are far inside `budget.minutes: 60`; the budget is sized for the agent's own working time on
  the issue, not for install+test.

## Env-allowlist check (assume: in oracle/README.md)

Ran the full 7-label command directly (outside `grade_e4.py`, same repo state as the base run above)
under `env -i PATH=... SYSTEMROOT=... SYSTEMDRIVE=... WINDIR=... TEMP=... TMP=...
PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 PYTHONUTF8=1` — i.e. exactly `correctness._env()`'s
`HOST_ENV` set plus its three `PYTHON*` additions, with no `USERPROFILE`/`LOCALAPPDATA`/`APPDATA` —
and got the same `Ran 7 tests ... FAILED (failures=1)` (base, unpatched) and `... OK` (reference,
gold patch applied) results, confirming `uv` does not need those three variables on this host.

## Validate

- `uv run bench validate`: see the command's own recorded output in the worker's report (run after
  this evidence was captured; task status `ready`).
