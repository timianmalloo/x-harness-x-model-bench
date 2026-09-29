# E5 oracle evidence

Grading matches `src/harness_bench/grade/correctness.py`: the tree under test (the engine's own
`workspace.task_source()` build of `source.repo`@`source.commit`, via a fresh
`workspace.cell_working_copy()`, or that same working copy with `oracle/reference/` overlaid), with
`tasks/E5/tests/` overlaid, executed in its disposable working directory. Produced by `uv run
python tasks/E5/oracle/grade_e5.py` on this Windows host, 2026-09-29, through `task.yaml`'s
`source.workspace_from: source` opt-in (ORCL-A; docs/lessons/defect-classes.md) and the `runner:
pytest` oracle path (`_pytest_spec`, `parse_pytest`).

This is the second instance authored for E5. `pylint-dev__pylint-4604` was rejected at Leader join
review (oracle/README.md, "Why this instance (and what was rejected)", item 4) for a symbol-
coupling defect the join review found: its FAIL_TO_PASS tests could only pass if the agent's patch
happened to add a specific incidental constant (`IS_PYPY`) the issue text never names. This file
records the proof for the replacement instance, `sympy__sympy-24443`.

Oracle runner: `pytest` (`src/harness_bench/grade/correctness.py`, `parse_pytest` reading the named
`--junitxml` report)

Command:
`uv run --python 3.11 --with-editable . --with pytest python -m pytest
sympy/combinatorics/tests/test_homomorphisms.py::test_homomorphism
sympy/combinatorics/tests/test_homomorphisms.py::test_isomorphisms --junitxml=report.xml`

Runner script: `tasks/E5/oracle/grade_e5.py`

## The tree under test, through the engine's own path

`grade_e5.py` never clones sympy itself. It calls `workspace.task_source(task_dir,
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
Result(passed=0, partial_credit=Decimal('0.5'), reason=None, evidence='out_base/oracle.log', compile_error=False)
```

Exit code: **1**

Summary (`parse_pytest`, reading `report.xml`'s one `<testsuite>`): `tests="2" failures="1"
errors="0" skipped="0"` — 1 of 2 passed (`collected 2 items` / `sympy\combinatorics\tests\
test_homomorphisms.py F.  [100%]` / `1 failed, 1 passed, 4 warnings in 0.50s`). The failure is the
FAIL_TO_PASS test:

```
FAILED sympy/combinatorics/tests/test_homomorphisms.py::test_homomorphism - ValueError: The given
images do not define a homomorphism
```

raised from `sympy/combinatorics/homomorphisms.py`'s `homomorphism()` — the unpatched
`_check_homomorphism()` still mishandles an inverted generator, exactly as `prompt.md`'s issue text
describes. `test_isomorphisms` (the PASS_TO_PASS test) passes on the base, unaffected by this bug.

## Pass on the reference solution

Grading call: `correctness.grade(ws_ref, task_dir, oracle, out_ref, tmp, timeout=300.0)`, where
`ws_ref` is a second `workspace.cell_working_copy()` of the same task source as `ws_base`, with
`oracle/reference/` overlaid — the one gold-patched file
(`sympy/combinatorics/homomorphisms.py`) at its real repo-relative path.

Result:
```python
Result(passed=1, partial_credit=Decimal('1'), reason=None, evidence='out_ref/oracle.log', compile_error=False)
```

Exit code: **0**

Summary (`parse_pytest`, reading `report.xml`): `tests="2" failures="0" errors="0" skipped="0"` —
2 of 2 passed (`collected 2 items` / `sympy\combinatorics\tests\test_homomorphisms.py ..  [100%]` /
`2 passed, 4 warnings in ...s`), including the previously-failing `test_homomorphism`.

## Rejected instances (live discrimination attempts, not inspection alone)

`oracle/README.md`'s "Why this instance (and what was rejected)" has the full account. Summary:

| instance | rejected because | evidence |
| --- | --- | --- |
| `psf__requests-2931` | pytest 8.4.2 cannot collect its 2016-era `test_requests.py`'s node ids in this multi-id command shape (`found no collectors` for all 85, including the FAIL_TO_PASS test) | live run, this host |
| `psf__requests-6028` | a PASS_TO_PASS test (`TestExtractZippedPaths::test_zipped_paths_extracted`) fails on the unpatched base natively on Windows — an upstream Windows-portability gap in the test itself, unrelated to this instance's patch | live run, this host |
| `pylint-dev__pylint-4661` | discriminates under a full shell environment but **not** under `correctness.py`'s own grading env allowlist (`HOST_ENV` carries no `USERPROFILE`/`HOME`): `os.path.expanduser("~")` returns the literal `"~"` in the grading subprocess, so both the base and the reference tree take the same `USER_HOME == "~"` branch and the fix (`appdirs.user_cache_dir`) is never reached either way | `grade_e5.py` run against that instance: `Result(passed=1, ...)` on the base tree |
| `pylint-dev__pylint-4604` | **rejected at Leader join review**: its FAIL_TO_PASS tests fail on the base only because the hidden test file imports a constant (`IS_PYPY`) the gold patch invents and the issue text never names — an agent that fixes the real reported bug without also inventing that exact constant name would still fail all 21 tests at collection. New selection rule added (oracle/README.md) | Leader join review, 2026-09-29; confirmed by grep: `IS_PYPY` in neither `prompt.md` nor the base tree's `pylint/constants.py` |

## Env-allowlist check

Ran the 2-id command directly (outside `grade_e5.py`) under `env -i PATH=... SYSTEMROOT=...
SYSTEMDRIVE=... WINDIR=... TEMP=... TMP=... PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0
PYTHONUTF8=1` — i.e. exactly `correctness._env()`'s `HOST_ENV` set plus its three `PYTHON*`
additions, with no `USERPROFILE`/`HOME`/`LOCALAPPDATA`/`APPDATA` — on both the base tree (unpatched
`homomorphisms.py`, patched test file) and the reference tree (both files patched), and got the
same `1 failed, 1 passed` (base) and `2 passed` (reference) results as the unrestricted run and as
`grade_e5.py`'s own run through `correctness.grade`. This is the check that `pylint-dev__pylint-
4661` failed (above) and that this instance passes, confirming `sympy__sympy-24443` does not depend
on `USERPROFILE`/`HOME` resolution anywhere in its fix or its tests.

## Timing (reference solution's own time; budget.minutes: 60)

- Both the base and reference `uv run` steps (warm `uv` cache; `cpython-3.11...-windows-x86_64-none`
  already fetched from an earlier step in this authoring session) completed in well under 1 second
  of pytest's own reported time (`0.50s` base, well under 1s reference), with `uv`'s own dependency
  install (`Installed 8 packages in ...ms`) and sympy's editable build each under a second.
- The upstream fetch (`workspace.upstream_tree`'s `--no-checkout` clone of `sympy/sympy.git`) is
  cached under `upstream_root`, keyed by (repo, commit); `grade_e5.py` uses a fresh
  `tempfile.mkdtemp()` per invocation, so its own `upstream_root` is never reused across separate
  script runs — the same shape E4's `evidence.md` records, with the same assume: about a real
  engine run sharing one `upstream_root` across a task version's cells. `sympy/sympy.git` is a much
  larger clone than `pylint-dev/pylint.git` (a monorepo with a long history), so this fetch is the
  dominant cost in a cold-cache authoring run; it is a one-time, per-task-version cost under a real
  engine run, not paid per cell.
- Both are far inside `budget.minutes: 60`; the budget is sized for the agent's own working time on
  the issue, not for install+test.

## Validate

- `uv run bench validate`: see the worker's final report (run after this file was written, with the
  task at status `ready`).
