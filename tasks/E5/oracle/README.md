# E5 oracle

E5 is the scenario-5 SWE-bench Verified task, 15-60 minute band (`bench/bom.yaml` row 46:
`budget_minutes: 60`), a different repository from E4's `django/django`. It is the proposal's
"Authored task inventory" row for E5: a second SWE-bench Verified instance in the 15-60 minute
band, the issue text as the given and its FAIL_TO_PASS/PASS_TO_PASS tests as the oracle, the
repository at its base commit with a native uv environment (no Docker/Harbor, ADR-0013
Amendment 1). It is also the first task to prove `correctness.grade`'s `runner: pytest` path (the
named `--junitxml` report), which E4's `oracle/README.md` recorded as newly built and untested by
a task.

## Dataset, instance and repository pin

- Dataset: `princeton-nlp/SWE-bench_Verified`, revision `c104f840cc67f8b6eec6f759ebc8b2693d585d4a`
  (confirmed current at authoring 2026-09-29 via `GET
  https://huggingface.co/api/datasets/princeton-nlp/SWE-bench_Verified` — the same revision E4
  pinned, still current). The parquet at that revision
  (`data/test-00000-of-00001.parquet`) holds 500 rows; `difficulty == "15 min - 1 hour"` selects
  261 of them, 144 outside `django/django`.
- Instance: `pylint-dev__pylint-4604` — "unused-import false positive for a module used in a type
  comment" (pylint issue, follow-up to #3112).
- Repository: `https://github.com/pylint-dev/pylint.git`, `base_commit`
  `1e55ae64624d28c5fe8b63ad7979880ee2e6ef3f` (`version` 2.9 in the dataset row).
- `FAIL_TO_PASS` (21): every test in `tests/checkers/unittest_variables.py::TestVariablesChecker`,
  `::TestVariablesCheckerWithTearDown` and `::TestMissingSubmodule` that the hidden test file's own
  new import makes fail on the base (see "Why FAIL_TO_PASS is 21, not 1" below); the full list is
  `task.yaml`'s `oracle.command`.
- `PASS_TO_PASS` (0): empty for this instance — SWE-bench Verified's own row lists no test outside
  the affected file, and (per the same mechanism) every test *inside* that file becomes a
  FAIL_TO_PASS entry rather than a PASS_TO_PASS one, so there is nothing left to hold as a
  regression check. Confirmed by reading the dataset row directly (`json.loads(row["PASS_TO_PASS"])
  == []`), not assumed from a short display.

## Why this instance (and what was rejected)

Screened `pyarrow.parquet` over the pinned revision's parquet for `difficulty == "15 min - 1 hour"
and repo != "django/django"`: 144 rows across sympy (43), matplotlib (19), scikit-learn (18),
sphinx (17), astropy (15), xarray (15), pytest (8), pylint (5), seaborn (2), requests (2).
`correctness.py`'s pytest runner (`parse_pytest`, reading a named `--junitxml` report) makes every
one of these eligible in principle (E4's `unittest`-only gate no longer excludes them), so the
remaining screen is "smallest surface that discriminates, pure-Python dependencies, runs natively
on this Windows host" — E4's own bar, re-applied. `pytest-dev/pytest`'s own 8 rows were rejected
outright: every one has hundreds to thousands of PASS_TO_PASS tests (947-5254), far past "smallest
surface." `sphinx-doc/sphinx`'s 17 rows were rejected the same way (PASS_TO_PASS 85-3608 each, none
under 85).

Three instances were run and rejected after a live discrimination attempt, not on inspection alone
(NG: check it, not "should still work"):

1. **`psf__requests-2931`** (repo `psf/requests`, `docutils`-free, zero installed dependencies —
   this 2016-era release vendors its own `urllib3`/`chardet` under `requests/packages/`). Rejected:
   collecting its `test_requests.py` under pytest 8.4.2 (the version `uv` resolves for `--with
   pytest` today) returns "found no collectors" / "no match in any of [<Class TestRequests>]" for
   every one of the 85 FAIL_TO_PASS/PASS_TO_PASS node ids, including the FAIL_TO_PASS test itself,
   though the same node id collects and passes fine on its own outside the multi-id command
   (isolated, single-id `pytest tests/checkers/...` runs were not affected by this — the failure is
   specific to `test_requests.py`'s old-style class, not to multi-id invocation in general, since
   E5's own 21-id command against `unittest_variables.py`, below, works). This 2016 test module
   predates pytest's modern collection protocol by several major versions; pinning an old pytest
   compatible with it would add a second pytest version to the task, which `correctness.py`'s
   pytest runner does not parameterize per task today (an engine change, out of scope: "if an
   instance needs one, pick another instance").
2. **`psf__requests-6028`** (same repo, a 2022-era commit; the fix and its 2 FAIL_TO_PASS tests are
   clean, pure-Python, no network). Rejected: running the full FAIL_TO_PASS+PASS_TO_PASS set
   (`tests/test_utils.py`, 213 tests) on this Windows host found `TestExtractZippedPaths::
   test_zipped_paths_extracted` — a PASS_TO_PASS test, unrelated to this instance's patch —
   already failing on the **unpatched** base tree. Read `requests/utils.py`'s
   `extract_zipped_paths`: the test zips `__file__` (its own absolute Windows path, e.g.
   `C:\...\test_utils.py`) with `zipfile.ZipFile.write(__file__)` (arcname defaults to that exact
   drive-letter, backslash path), then reconstructs the expected member name via
   `os.path.splitdrive` + `'/'.join(...)` — a different (drive-stripped, forward-slash) string that
   never matches the zip's real member name on Windows. This is an upstream Windows-portability gap
   in the test itself (not in `requests/utils.py`'s production code, and not caused by this task's
   grading), so it is not a Not-in-scope engine/grader change to work around — it is a reason to
   pick a different instance, which SWE-bench-Verified's PASS_TO_PASS list gives no latitude to
   drop.
3. **`pylint-dev__pylint-4661`** (same repo as the instance finally chosen; "make pylint XDG Base
   Directory Specification compliant" — `appdirs.user_cache_dir("pylint")` instead of
   `~/.pylint.d`). The single FAIL_TO_PASS test passed on both the base and the reference tree when
   run through `grade_e5.py`'s own path (`correctness.grade`, not a hand-rolled `uv run`): **the
   grading step's env allowlist** (`correctness.py`'s `HOST_ENV = (PATH, SYSTEMROOT, SYSTEMDRIVE,
   WINDIR, TEMP, TMP)`, `_env()`) **carries no `USERPROFILE`/`HOME`/`HOMEDRIVE`/`HOMEPATH`**, so
   inside the grading subprocess `os.path.expanduser("~")` returns the literal string `"~"`
   (Python's `ntpath.expanduser` falls back to the unexpanded input when none of those variables
   are set) — both `pylint/config/__init__.py`'s own `USER_HOME == "~"` branch and the hidden
   test's own `if uhome == "~": expected = ".pylint.d"` branch fire identically on the base *and*
   the reference tree, so the grading subprocess never reaches the `appdirs.user_cache_dir(...)`
   line either code path was supposed to add or check. Confirmed by direct measurement (running
   `grade_e5.py` end to end against that instance, not by reading `HOST_ENV` and inferring the
   consequence): `Result(passed=1, ...)` on the *base* tree — the oracle does not discriminate
   under this harness's own grading environment, even though (confirmed separately) it does
   discriminate under a normal full-environment shell. Extending `HOST_ENV` to carry
   `USERPROFILE`/`HOME` is an engine change (`correctness.py`), out of scope here; picking an
   instance whose fix does not depend on home-directory resolution avoids it. `pylint-dev__pylint-
   4604` (within the same repo, a different, earlier issue) was checked and does not touch
   `USER_HOME`, `PYLINT_HOME` or any other home-directory path, so it is not exposed to this gap —
   confirmed by running its own FAIL_TO_PASS set under an `env -i`-restricted shell carrying exactly
   `HOST_ENV` plus `correctness._env()`'s three `PYTHON*` additions (below), which is what led to
   selecting it.

No other instance in the 144-row screen was run: `pylint-dev__pylint-4604` was the fourth live
attempt and it discriminates cleanly (below), so the search stopped there ("smallest correct" —
`.github/instructions/solution-selection-ladder.instructions.md` — governs how much further
screening is owed once a working instance is in hand).

## Why FAIL_TO_PASS is 21, not 1

The gold patch (`oracle/reference/pylint/constants.py`) adds one new module-level constant,
`IS_PYPY = platform.python_implementation() == "PyPy"`, which does not exist in
`pylint/constants.py` at `base_commit`. The hidden test file
(`tests/checkers/unittest_variables.py`, SWE-bench's own `test_patch` for this instance) adds
`from pylint.constants import IS_PYPY` at module level (used only to `@unittest.skipIf(IS_PYPY,
...)` the one new test the patch adds, `test_attribute_in_type_comment`). On the base tree that
import fails (`ImportError: cannot import name 'IS_PYPY'`) **before pytest can collect a single
test in the file** — so every one of the file's 21 previously-passing tests fails to collect, and
SWE-bench Verified's own `FAIL_TO_PASS` list names all 21 rather than just the one new test.
`correctness.grade()`'s `parse_pytest` reads this as one `<testcase>` with `<error
message="collection failure">` in the JUnit XML (`tests="1" errors="1"`, so `passed=0` of
`total=1`) rather than 21 separate failing entries — `oracle/evidence.md`'s base run shows this
exact shape. `pass_at_1` (`passed == total`) is `0` either way, which is what E5's own Done-when
needs ("the base fails a FAIL_TO_PASS test"); the `partial_credit` fraction is `0/1` rather than
`0/21` for this instance, a difference in what the fraction's denominator counts, not in whether
the base fails.

The gold patch's second hunk (`pylint/checkers/variables.py`, `_store_type_annotation_node`) is the
actual functional fix (recurse into an `astroid.Attribute` node — e.g. `foo.Bar` in a `# type:`
comment — so its `expr` name, e.g. `foo`, is recorded as used and `unused-import` stops firing);
`constants.py`'s `IS_PYPY` is incidental to that fix (PyPy's older typed-ast-based parser cannot
parse the new test's own type comments) but is what makes the *test file* fail to import on an
unpatched tree, which is why 20 unrelated tests ride along as FAIL_TO_PASS.

## Reference solution

`oracle/reference/pylint/{constants.py, checkers/variables.py}` are the two files SWE-bench's
`patch` changes, in full, at their real repo-relative paths — the same "full file, real path" shape
E4 and E6 use.

## Environment (uv-managed, native, no Docker)

`task.yaml`'s `oracle.command` is:

```
uv run --python 3.9 --with-editable . --with astroid==2.6.5 --with pytest python -m pytest <21 dotted test ids> --junitxml=report.xml
```

- `uv run --with-editable .` builds and installs the workspace's own `pylint/` package (pylint's
  `setup.cfg`: `install_requires = astroid>=2.6.5,<2.7, isort>=4.2.5,<6, mccabe>=0.6,<0.7,
  toml>=0.7.1, colorama;sys_platform=="win32"`) as an ephemeral environment rooted at the command's
  cwd; `--with astroid==2.6.5` pins the exact version pylint's own
  `requirements_test_min.txt` pins for its test suite (the range alone would let `uv` resolve a
  newer 2.6.x). Python 3.9 is pinned to match pylint 2.9/2.10's own supported range
  (`setup.cfg`: `Programming Language :: Python :: 3.6` through `3.10`) and SWE-bench's own
  install profile for this pylint version band; `uv` fetched `cpython-3.9.25-windows-x86_64-none`
  itself on first use (this host did not have it cached before this task).
- `astroid` pulls in `wrapt` (a transitive dependency with one optional C extension,
  `src/wrapt/_wrappers.c`). Checked, not assumed: `wrapt`'s own `setup.py` wraps the extension build
  in `optional_build_ext`, catching `CCompilerError`/`DistutilsExecError`/`DistutilsPlatformError`
  (plus `IOError`/`OSError`/`ValueError` on `win32`) and falling back to a pure-Python install on
  failure — confirmed by reading the downloaded sdist's `setup.py` directly
  (`pip download wrapt==1.12.1 --no-binary :all: --no-deps`), not inferred from the package's
  reputation. On this host the C extension did build (`wrapt\_wrappers.cp39-win_amd64.pyd`
  present, MSVC available), so this was not exercised in the failure direction here; if a grading
  host lacks a C compiler, `wrapt` installs without it rather than failing the task.
- This is one command, invokes `uv` directly (no `cmd.exe`/shell wrapper), and uses only
  forward-slash paths (`tests/checkers/unittest_variables.py`) — the portable shape D1/D3/E4/E6/F1
  use.
- No separate install step is needed or possible: `correctness.grade()` runs exactly one command
  per cell (`grade()`), so setup and test execution are the same `uv run` call.
- `report.xml` is a bare filename (no directory component), as `correctness.py`'s `_pytest_spec`
  requires; it lands directly under the grading copy's root (the command's cwd), and
  `_report_matches` finds it there.

assume: the grading step's env allowlist (`HOST_ENV`: `PATH`, `SYSTEMROOT`, `SYSTEMDRIVE`,
`WINDIR`, `TEMP`, `TMP` — no `USERPROFILE`/`HOME`/`LOCALAPPDATA`/`APPDATA`) is sufficient for `uv`
to resolve its cache and download the pinned CPython 3.9 build and for this instance's install/test
step, the same finding E4's `oracle/README.md` recorded for `unittest`/Django. **Confirm:** ran the
full 21-id command under `env -i` restricted to exactly that allowlist plus the three `PYTHON*`
variables `correctness._env()` sets, on this Windows host, both before and after the gold patch;
got the same collection-ImportError (base) and 21/21-pass (reference) results as the unrestricted
run and as `grade_e5.py`'s own run through `correctness.grade` (`oracle/evidence.md`). **Breaks if
false:** the same one-line, one-time, task-independent `HOST_ENV` extension E4 already named would
be needed — not specific to E5. This assume: is *narrower* than E4's, because E5's own live
discrimination check (item 3 above) already found and rejected the one instance in this search
where that gap changed the *result*, not just the mechanism; E5's chosen instance does not read
`USERPROFILE`/`HOME` anywhere in its fix or its tests, confirmed by grep over both changed files and
the hidden test file for `expanduser|HOME|USERPROFILE` (no matches).

## macOS (ADR-0013 Amendment 1)

assume: this task runs natively on macOS unchanged — pylint 2.9's own test suite, `astroid==2.6.5`
and `wrapt` (pure-Python fallback available, as above) have no Windows-only API, and `uv run
--python 3.9 --with-editable . --with astroid==2.6.5 --with pytest python -m pytest ...` is the
same command on macOS (no `.exe`, no backslash, no shell). **Confirm:** run the same command from a
clone of `https://github.com/pylint-dev/pylint.git` at `1e55ae64624d28c5fe8b63ad7979880ee2e6ef3f`
(with `tasks/E5/tests/` overlaid for the base run, and `oracle/reference/` overlaid on top of that
for the reference run) on a macOS host (the `macos-latest` CI job PLAT-A wired), and observe the
same collection-ImportError-then-21/21 shape. **Breaks if false:** a defect specific to this
instance, not the engine-wide Windows-only gap ADR-0013 §5 already records. Not measured here (no
macOS host in this worktree).

## Budget

`budget.minutes: 60` (matches `bench/bom.yaml` row 46 and the inventory's stated band). The
reference solution's own oracle run (through `grade_e5.py`, warm `uv` cache) took well under 5
seconds end to end (`oracle/evidence.md`); a cold cache adds one pylint/astroid/wrapt build and one
CPython 3.9 fetch, together a few seconds more (also observed while authoring this task, in the
earlier manual runs above). This fits the 60-minute budget with very large headroom — the budget is
sized for the agent's own working time on the issue, not for install+test.

## Verification

Run `uv run python tasks/E5/oracle/grade_e5.py` to evaluate both the base workspace (a fresh build
of `source.repo`@`source.commit` via the engine's own `workspace.task_source()` and
`workspace.cell_working_copy()`, unmodified) and the reference solution (that same base with
`oracle/reference/` overlaid) through `harness_bench.grade.correctness.grade` — network access is
needed for the clone and, on a cold `uv` cache, for `uv`'s own downloads. Evidence is committed in
`oracle/evidence.md`.

## No secrets

`prompt.md` is the upstream GitHub issue text verbatim (public, `pylint-dev/pylint`,
GPL-2.0-or-later, `Copyright (c) https://github.com/PyCQA/pylint`, `LICENSE` in this folder). No
credential, customer data or private content is in this task.
