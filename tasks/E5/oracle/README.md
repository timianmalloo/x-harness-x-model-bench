# E5 oracle

E5 is the scenario-5 SWE-bench Verified task, 15-60 minute band (`bench/bom.yaml` row 46:
`budget_minutes: 60`), a different repository from E4's `django/django`. It is the proposal's
"Authored task inventory" row for E5: a second SWE-bench Verified instance in the 15-60 minute
band, the issue text as the given and its FAIL_TO_PASS/PASS_TO_PASS tests as the oracle, the
repository at its base commit with a native uv environment (no Docker/Harbor, ADR-0013
Amendment 1). It is also the first task to prove `correctness.grade`'s `runner: pytest` path (the
named `--junitxml` report), which E4's `oracle/README.md` recorded as newly built and untested by
a task.

## Selection rules (in force for this task)

In addition to E4's bar — smallest surface that discriminates, pure-Python dependencies, runs
natively on this Windows host, under `correctness.py`'s own grading env allowlist (not just a full
shell) — E5 adds, after the Leader's join review rejected the first candidate landed here:

> **Reject an instance whose FAIL_TO_PASS tests can only pass if the agent reproduces a symbol,
> file or signature that the issue text does not name.** An oracle that only a patch matching the
> gold patch's own incidental naming can satisfy measures whether the agent guessed those names,
> not whether it fixed the reported bug. Checked by reading the `test_patch`'s added imports and
> fixtures against the `problem_statement`: any newly-imported name (or newly-required fixture)
> that (a) does not appear in the issue text and (b) is introduced by the gold `patch` itself (not
> pre-existing public API) fails this check.

## Dataset, instance and repository pin

- Dataset: `princeton-nlp/SWE-bench_Verified`, revision `c104f840cc67f8b6eec6f759ebc8b2693d585d4a`
  (confirmed current at authoring 2026-09-29 via `GET
  https://huggingface.co/api/datasets/princeton-nlp/SWE-bench_Verified` — the same revision E4
  pinned, still current). The parquet at that revision holds 500 rows; `difficulty == "15 min - 1
  hour"` selects 261 of them, 144 outside `django/django`.
- Instance: `sympy__sympy-24443` — "`_check_homomorphism` is broken on PermutationGroups"
  (`sympy.combinatorics.homomorphisms`).
- Repository: `https://github.com/sympy/sympy.git`, `base_commit`
  `809c53c077485ca48a206cee78340389cb83b7f1` (`version` 1.12 in the dataset row).
- `FAIL_TO_PASS` (1): `sympy/combinatorics/tests/test_homomorphisms.py::test_homomorphism`.
- `PASS_TO_PASS` (1): `sympy/combinatorics/tests/test_homomorphisms.py::test_isomorphisms` — a
  different test in the same file, read directly from the dataset row via `json.loads` (the
  `FAIL_TO_PASS`/`PASS_TO_PASS` parquet columns are JSON-encoded strings, not native lists —
  `len()` on the raw string undercounts/overcounts; every count in this document is from
  `json.loads(row[...])`).

## Why this instance (and what was rejected)

Re-screened the pinned revision's parquet for `difficulty == "15 min - 1 hour" and repo !=
"django/django"` with the counts corrected (`json.loads`, not the raw string length), then sorted
by `len(FAIL_TO_PASS) + len(PASS_TO_PASS)` ascending — "smallest surface that discriminates," E4's
own bar, applied without the earlier miscount. The smallest rows: `pylint-dev__pylint-4661` (1+0,
rejected below), `sympy__sympy-24443` (1+1), `sphinx-doc__sphinx-8035` (1+2),
`sympy__sympy-23413` (1+2), `sympy__sympy-23824` (1+2), `sphinx-doc__sphinx-8593` (2+1),
`astropy__astropy-7671` (1+3), `sympy__sympy-15349` (1+3), ... `pylint-dev__pylint-4604` (21+0,
the instance landed here first, before this re-screen). `sympy` is pure-Python (`setup.py`:
`install_requires = ['mpmath>=0.19']`, no C extension in `mpmath` or `sympy` itself), BSD-3-Clause
licensed, and has by far the most rows in this band (43) if the first pick needs replacing again.

Four instances were run and rejected after a live discrimination attempt, not on inspection alone
(NG: check it, not "should still work"):

1. **`psf__requests-2931`** — collecting its 2016-era `test_requests.py` under pytest 8.4.2 (the
   version `uv` resolves for `--with pytest`) returns "found no collectors" for every requested
   node id in a multi-id command, including the FAIL_TO_PASS test itself, though the same node id
   collects and passes fine in isolation. Pinning an old, compatible pytest would add a second
   pytest version to the task, which `correctness.py`'s pytest runner does not parameterize per
   task today (an engine change, out of scope).
2. **`psf__requests-6028`** — a PASS_TO_PASS test (`TestExtractZippedPaths::
   test_zipped_paths_extracted`) fails on the **unpatched base** natively on Windows: it zips
   `__file__` (its own absolute, drive-letter, backslash path) and then reconstructs the expected
   zip-member name via `os.path.splitdrive` + `'/'.join(...)`, a different string that never
   matches the real member name on Windows. An upstream Windows-portability gap in the test itself,
   unrelated to this instance's patch — not a Not-in-scope engine/grader change to work around, and
   SWE-bench's own PASS_TO_PASS list gives no latitude to drop it.
3. **`pylint-dev__pylint-4661`** ("make pylint XDG Base Directory Specification compliant" —
   `appdirs.user_cache_dir("pylint")` instead of `~/.pylint.d`). Discriminates under a normal shell
   but **not** under `correctness.py`'s own grading env allowlist (`HOST_ENV` carries no
   `USERPROFILE`/`HOME`/`HOMEDRIVE`/`HOMEPATH`): inside the grading subprocess
   `os.path.expanduser("~")` returns the literal `"~"`, so both the base and the reference tree
   take the same `USER_HOME == "~"` branch and the fix is never reached either way. Confirmed by
   running `grade_e5.py` end to end against it: `Result(passed=1, ...)` on the *base* tree.
4. **`pylint-dev__pylint-4604`** ("unused-import false positive for a module used in a type
   comment") — the instance landed here in the previous pass, **rejected at Leader join review**
   under the new selection rule above. Its 21 FAIL_TO_PASS tests fail on the base only because
   SWE-bench's own `test_patch` adds `from pylint.constants import IS_PYPY` to the top of
   `tests/checkers/unittest_variables.py`, and `IS_PYPY` is a constant the gold `patch` invents
   (`pylint/constants.py`: `IS_PYPY = platform.python_implementation() == "PyPy"`) — not named,
   implied or derivable from the issue text (which only describes a false-positive `unused-import`
   warning on a type comment). An agent that fixes the real bug (the recursion into
   `astroid.Attribute` nodes in `_store_type_annotation_node`, `pylint/checkers/variables.py`)
   without also adding a constant named exactly `IS_PYPY` to `pylint/constants.py` produces a tree
   where the hidden test file still fails to import, so all 21 tests still fail at collection —
   `pass_at_1` would then measure whether the agent's patch happens to add that one incidental name
   pylint's own maintainers chose, not whether the reported bug is fixed. Checked directly against
   the rule: the `test_patch`'s only new import (`from pylint.constants import IS_PYPY`) does not
   appear anywhere in `prompt.md`'s issue text, and `IS_PYPY` does not exist in `pylint/constants.py`
   before the gold `patch` adds it (`grep -c IS_PYPY` on the base tree's `pylint/constants.py`: 0) —
   both halves of the rule's check fail, so the instance is rejected regardless of how well it
   otherwise ran (it did: E5's evidence.md from the prior pass recorded a clean
   `passed=0`/`passed=1` split through `grade_e5.py`, under the same `env -i`-restricted
   environment used for `pylint-dev__pylint-4661` above; that measurement was sound, only the
   instance choice was wrong).

`sympy__sympy-24443` was checked against the same rule before being run: its `test_patch` (diff
against `sympy/combinatorics/tests/test_homomorphisms.py`) adds no new `import` line at all — it
only adds two lines inside the existing `test_homomorphism` function body (`D3 = DihedralGroup(3)`;
`T = homomorphism(D3, D3, D3.generators, D3.generators)`; `assert T.is_isomorphism()`), and every
name used (`DihedralGroup`, `homomorphism`, `.is_isomorphism()`) is pre-existing public API already
imported at the top of the file before SWE-bench's `test_patch` (`from
sympy.combinatorics.named_groups import ..., DihedralGroup, ...`; `from
sympy.combinatorics.homomorphisms import homomorphism, ...`), used elsewhere in the same test
function against other `homomorphism(...)` calls that pre-date this patch entirely. The gold
`patch` (`sympy/combinatorics/homomorphisms.py`) only rewrites the *internals* of the private
function `_check_homomorphism` and its nested `_image` closure — it adds no new public name the
test could be coupled to. No further instance in the re-screened list needed to be run: this one
passes the new rule on inspection and then discriminates live (below), so the search stopped there
("smallest correct" — `.github/instructions/solution-selection-ladder.instructions.md`).

## Reference solution

`oracle/reference/sympy/combinatorics/homomorphisms.py` is the one file SWE-bench's `patch`
changes, in full, at its real repo-relative path — the same "full file, real path" shape E4 and E6
use.

## Environment (uv-managed, native, no Docker)

`task.yaml`'s `oracle.command` is:

```
uv run --python 3.11 --with-editable . --with pytest python -m pytest sympy/combinatorics/tests/test_homomorphisms.py::test_homomorphism sympy/combinatorics/tests/test_homomorphisms.py::test_isomorphisms --junitxml=report.xml
```

- `uv run --with-editable .` builds and installs the workspace's own `sympy/` package (sympy's
  `setup.py`: `install_requires = ['mpmath>=0.19']`) as an ephemeral environment rooted at the
  command's cwd. No version pin is added for `mpmath`: unlike E4 (`docutils`, unpinned) or the
  rejected pylint instances (`astroid==2.6.5`, pinned to match pylint's own
  `requirements_test_min.txt`), sympy ships no `requirements_test*.txt` or other test-time pin for
  `mpmath` — `uv` resolves the newest version satisfying `>=0.19`, matching how sympy's own CI and
  `pip install -e .` resolve it.
- Python 3.11 is pinned to match sympy 1.12's own supported range (`setup.py`: `python_requires =
  '>=3.8'`, classifiers list 3.8 through 3.11); `uv` used its own already-cached
  `cpython-3.11...-windows-x86_64-none` build (fetched earlier in this authoring session for a
  different task).
- Both `sympy` and `mpmath` are pure Python — no C extension, no native-toolchain dependency at
  all (unlike the rejected pylint instances' transitive `wrapt`, whose optional C extension has a
  pure-Python fallback per its own `setup.py`, checked in the prior pass's evidence).
- This is one command, invokes `uv` directly (no `cmd.exe`/shell wrapper), and uses only
  forward-slash paths (`sympy/combinatorics/tests/test_homomorphisms.py`) — the portable shape
  D1/D3/E4/E6/F1 use.
- No separate install step is needed or possible: `correctness.grade()` runs exactly one command
  per cell (`grade()`), so setup and test execution are the same `uv run` call.
- `report.xml` is a bare filename (no directory component), as `correctness.py`'s `_pytest_spec`
  requires; it lands directly under the grading copy's root (the command's cwd), and
  `_report_matches` finds it there.

assume: the grading step's env allowlist (`HOST_ENV`: `PATH`, `SYSTEMROOT`, `SYSTEMDRIVE`,
`WINDIR`, `TEMP`, `TMP` — no `USERPROFILE`/`HOME`/`LOCALAPPDATA`/`APPDATA`) is sufficient for `uv`
to resolve its cache and for this instance's install/test step, the same finding E4's
`oracle/README.md` recorded for `unittest`/Django. **Confirm:** ran the 2-id command under `env -i`
restricted to exactly that allowlist plus the three `PYTHON*` variables `correctness._env()` sets,
on this Windows host, on the base tree (unpatched `homomorphisms.py`, patched test file) and on the
reference tree (both files patched); got the same `1 failed, 1 passed` (base) and `2 passed`
(reference) results as the unrestricted run and as `grade_e5.py`'s own run through
`correctness.grade` (`oracle/evidence.md`). This is the specific check `pylint-dev__pylint-4661`
failed and `sympy__sympy-24443` passes: neither the gold patch nor the hidden test reads
`USERPROFILE`, `HOME` or any other home-directory path (grepped both changed files and the hidden
test file for `expanduser|HOME|USERPROFILE`: no matches). **Breaks if false:** the same one-line,
one-time, task-independent `HOST_ENV` extension E4 already named would be needed — not specific to
E5.

## macOS (ADR-0013 Amendment 1)

assume: this task runs natively on macOS unchanged — sympy 1.12's own test suite and `mpmath` are
pure Python with no Windows-only API, and `uv run --python 3.11 --with-editable . --with pytest
python -m pytest ...` is the same command on macOS (no `.exe`, no backslash, no shell).
**Confirm:** run the same command from a clone of `https://github.com/sympy/sympy.git` at
`809c53c077485ca48a206cee78340389cb83b7f1` (with `tasks/E5/tests/` overlaid for the base run, and
`oracle/reference/` overlaid on top of that for the reference run) on a macOS host (the
`macos-latest` CI job PLAT-A wired), and observe the same `1 failed, 1 passed`-then-`2 passed`
shape. **Breaks if false:** a defect specific to this instance, not the engine-wide Windows-only
gap ADR-0013 §5 already records. Not measured here (no macOS host in this worktree).

## Budget

`budget.minutes: 60` (matches `bench/bom.yaml` row 46 and the inventory's stated band). The
reference solution's own oracle run (through `grade_e5.py`, warm `uv` cache) took well under 1
second of pytest's own reported time (`oracle/evidence.md`); a cold cache adds one sympy build and
one CPython 3.11 fetch, together a few seconds more. This fits the 60-minute budget with very large
headroom — the budget is sized for the agent's own working time on the issue, not for install+test.

## Verification

Run `uv run python tasks/E5/oracle/grade_e5.py` to evaluate both the base workspace (a fresh build
of `source.repo`@`source.commit` via the engine's own `workspace.task_source()` and
`workspace.cell_working_copy()`, unmodified) and the reference solution (that same base with
`oracle/reference/` overlaid) through `harness_bench.grade.correctness.grade` — network access is
needed for the clone and, on a cold `uv` cache, for `uv`'s own downloads. Evidence is committed in
`oracle/evidence.md`.

## No secrets

`prompt.md` is the upstream GitHub issue text verbatim (public, `sympy/sympy`, BSD-3-Clause,
`Copyright (c) 2006-2022 SymPy Development Team`, `LICENSE` in this folder). No credential,
customer data or private content is in this task.
