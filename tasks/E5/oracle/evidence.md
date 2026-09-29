# E5 oracle evidence

Grading matches `src/harness_bench/grade/correctness.py`: the tree under test (the engine's own
`workspace.task_source()` build of `source.repo`@`source.commit`, via a fresh
`workspace.cell_working_copy()`, or that same working copy with `oracle/reference/` overlaid), with
`tasks/E5/tests/` overlaid, executed in its disposable working directory. Produced by `uv run
python tasks/E5/oracle/grade_e5.py` on this Windows host, 2026-09-29, through `task.yaml`'s
`source.workspace_from: source` opt-in (ORCL-A; docs/lessons/defect-classes.md) and the `runner:
pytest` oracle path (`_pytest_spec`, `parse_pytest`; E5 is the first task to exercise it).

Oracle runner: `pytest` (`src/harness_bench/grade/correctness.py`, `parse_pytest` reading the named
`--junitxml` report)

Command:
`uv run --python 3.9 --with-editable . --with astroid==2.6.5 --with pytest python -m pytest
tests/checkers/unittest_variables.py::TestVariablesChecker::test_bitbucket_issue_78
tests/checkers/unittest_variables.py::TestVariablesChecker::test_no_name_in_module_skipped
tests/checkers/unittest_variables.py::TestVariablesChecker::test_all_elements_without_parent
tests/checkers/unittest_variables.py::TestVariablesChecker::test_redefined_builtin_ignored
tests/checkers/unittest_variables.py::TestVariablesChecker::test_redefined_builtin_custom_modules
tests/checkers/unittest_variables.py::TestVariablesChecker::test_redefined_builtin_modname_not_ignored
tests/checkers/unittest_variables.py::TestVariablesChecker::test_redefined_builtin_in_function
tests/checkers/unittest_variables.py::TestVariablesChecker::test_unassigned_global
tests/checkers/unittest_variables.py::TestVariablesChecker::test_listcomp_in_decorator
tests/checkers/unittest_variables.py::TestVariablesChecker::test_listcomp_in_ancestors
tests/checkers/unittest_variables.py::TestVariablesChecker::test_return_type_annotation
tests/checkers/unittest_variables.py::TestVariablesChecker::test_attribute_in_type_comment
tests/checkers/unittest_variables.py::TestVariablesCheckerWithTearDown::test_custom_callback_string
tests/checkers/unittest_variables.py::TestVariablesCheckerWithTearDown::test_redefined_builtin_modname_not_ignored
tests/checkers/unittest_variables.py::TestVariablesCheckerWithTearDown::test_redefined_builtin_in_function
tests/checkers/unittest_variables.py::TestVariablesCheckerWithTearDown::test_import_as_underscore
tests/checkers/unittest_variables.py::TestVariablesCheckerWithTearDown::test_lambda_in_classdef
tests/checkers/unittest_variables.py::TestVariablesCheckerWithTearDown::test_nested_lambda
tests/checkers/unittest_variables.py::TestVariablesCheckerWithTearDown::test_ignored_argument_names_no_message
tests/checkers/unittest_variables.py::TestVariablesCheckerWithTearDown::test_ignored_argument_names_starred_args
tests/checkers/unittest_variables.py::TestMissingSubmodule::test_package_all
--junitxml=report.xml`

Runner script: `tasks/E5/oracle/grade_e5.py`

## The tree under test, through the engine's own path

`grade_e5.py` never clones pylint itself. It calls `workspace.task_source(task_dir,
"grade-e5-probe", tmp / "sources", tmp / "upstream")` — the same function a real cell's bootstrap
calls — which: fetches `source.repo` once into a `--no-checkout` clone cached under `tmp /
"upstream"` (keyed by repo+commit; `workspace.upstream_tree`), verifies that clone's HEAD is
exactly `source.commit` (`workspace._verify_commit`, an exact string match, not "reachable"),
`git archive`s its tree at that commit, overlays `tasks/E5/workspace/` (empty for E5) on top, and
commits the result as the task source's one base commit — no upstream `.git` history reaches it
(R-83). `ws_base` and `ws_ref` are then two independent `workspace.cell_working_copy()` clones of
that one task source, exactly as two real cells of the same task version would get them.

## Fail on the base workspace

Grading call: `correctness.grade(ws_base, task_dir, oracle, out_base, tmp, timeout=300.0)`, where
`ws_base` is the engine's own cell working copy of the task source above, unmodified.

Result:
```python
Result(passed=0, partial_credit=Decimal('0'), reason=None, evidence='out_base/oracle.log', compile_error=False)
```

Exit code: **4** (pytest's own "collection error, nothing ran" exit status)

Summary (`parse_pytest`, reading `report.xml`'s one `<testsuite>`):
`tests="1" errors="1" failures="0" skipped="0"` — 0 of 1 "passed" (pytest folds the 21 requested,
uncollectable node ids into a single collection-failure test case for the whole module, as
`oracle/README.md`'s "Why FAIL_TO_PASS is 21, not 1" explains). The stdout carries the real cause:

```
ERROR collecting tests/checkers/unittest_variables.py
ImportError while importing test module '...\tests\checkers\unittest_variables.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
...\importlib\__init__.py:127: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
tests\checkers\unittest_variables.py:30: in <module>
    from pylint.constants import IS_PYPY
E   ImportError: cannot import name 'IS_PYPY' from 'pylint.constants' ('...\pylint\constants.py')
```

followed by 21 `ERROR: found no collectors for ...<each requested node id>` lines (pytest still
tries to resolve each explicitly-named id against the failed module). This is exactly
`pylint-dev__pylint-4604`'s FAIL_TO_PASS mechanism: the hidden test file's own new import
(`IS_PYPY`, added by SWE-bench's `test_patch`) does not exist in the base `pylint/constants.py`, so
none of the file's 21 previously-passing tests can even be collected until the gold patch adds it.

## Pass on the reference solution

Grading call: `correctness.grade(ws_ref, task_dir, oracle, out_ref, tmp, timeout=300.0)`, where
`ws_ref` is a second `workspace.cell_working_copy()` of the same task source as `ws_base`, with
`oracle/reference/` overlaid — the two gold-patched files (`pylint/constants.py`,
`pylint/checkers/variables.py`) at their real repo-relative paths.

Result:
```python
Result(passed=1, partial_credit=Decimal('1'), reason=None, evidence='out_ref/oracle.log', compile_error=False)
```

Exit code: **0**

Summary (`parse_pytest`, reading `report.xml`): `tests="21" errors="0" failures="0" skipped="0"` —
21 of 21 passed (`collected 21 items` / `tests\checkers\unittest_variables.py
.....................  [100%]` / `21 passed, 1 warning in 0.21s`), including
`test_attribute_in_type_comment`, the one genuinely new test the patch adds, and every one of the
20 tests that only failed on the base because the module could not import.

## Rejected instances (live discrimination attempts, not inspection alone)

`oracle/README.md`'s "Why this instance (and what was rejected)" has the full account. Summary:

| instance | rejected because | evidence |
| --- | --- | --- |
| `psf__requests-2931` | pytest 8.4.2 cannot collect its 2016-era `test_requests.py`'s node ids in this multi-id command shape (`found no collectors` for all 85, including the FAIL_TO_PASS test) | live run, this host |
| `psf__requests-6028` | a PASS_TO_PASS test (`TestExtractZippedPaths::test_zipped_paths_extracted`) fails on the unpatched base natively on Windows — an upstream Windows-portability gap in the test itself, unrelated to this instance's patch | live run, this host |
| `pylint-dev__pylint-4661` | discriminates under a full shell environment but **not** under `correctness.py`'s own grading env allowlist (`HOST_ENV` carries no `USERPROFILE`/`HOME`): `os.path.expanduser("~")` returns the literal `"~"` in the grading subprocess, so both the base and the reference tree take the same `USER_HOME == "~"` branch and the fix (`appdirs.user_cache_dir`) is never reached either way | `grade_e5.py` run against that instance: `Result(passed=1, ...)` on the base tree |

## Env-allowlist check (assume: in oracle/README.md)

Ran the full 21-id command directly (outside `grade_e5.py`, same repo state as the base and
reference runs above) under `env -i PATH=... SYSTEMROOT=... SYSTEMDRIVE=... WINDIR=... TEMP=...
TMP=... PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 PYTHONUTF8=1` — i.e. exactly
`correctness._env()`'s `HOST_ENV` set plus its three `PYTHON*` additions, with no
`USERPROFILE`/`HOME`/`LOCALAPPDATA`/`APPDATA` — and got the same shapes: collection `ImportError`
(base, unpatched) and `21 passed` (reference, gold patch applied). This is the check that led to
rejecting `pylint-dev__pylint-4661` (above) and selecting `pylint-dev__pylint-4604` instead.

## Timing (reference solution's own time; budget.minutes: 60)

- Both the base and reference `uv run` steps (warm `uv` cache; `cpython-3.9.25-windows-x86_64-none`
  already fetched from an earlier step in this authoring session) completed in well under 1 second
  of pytest's own reported time (`0.13s` base collection failure, `0.21s` reference), with `uv`'s
  own dependency install (`Installed 17 packages in ...ms`) and pylint's editable build each under
  half a second.
- The upstream fetch (`workspace.upstream_tree`'s `--no-checkout` clone of `pylint-dev/pylint.git`)
  is cached under `upstream_root`, keyed by (repo, commit); `grade_e5.py` uses a fresh
  `tempfile.mkdtemp()` per invocation, so its own `upstream_root` is never reused across separate
  script runs — the same shape E4's `evidence.md` records, with the same assume: about a real
  engine run sharing one `upstream_root` across a task version's cells.
- Both are far inside `budget.minutes: 60`; the budget is sized for the agent's own working time on
  the issue, not for install+test.

## Validate

- `uv run bench validate`: see the worker's final report (run after this file was written, with the
  task at status `ready`).
