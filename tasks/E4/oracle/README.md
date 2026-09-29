# E4 oracle

E4 is the scenario-5 SWE-bench Verified task, 15-60 minute band (`bench/bom.yaml` row 42: `budget_minutes: 60`).
It is the proposal's "Authored task inventory" row for E4: one SWE-bench Verified instance in the
15-60 minute band, the issue text as the given and its FAIL_TO_PASS/PASS_TO_PASS tests as the oracle,
the repository at its base commit with a native uv environment (no Docker/Harbor, ADR-0013 Amendment 1).

## Dataset, instance and repository pin

- Dataset: `princeton-nlp/SWE-bench_Verified`, revision `c104f840cc67f8b6eec6f759ebc8b2693d585d4a`
  (the HF dataset repo's own commit sha, from `GET https://huggingface.co/api/datasets/princeton-nlp/SWE-bench_Verified`,
  observed 2026-09-29). The parquet at that revision
  (`data/test-00000-of-00001.parquet`, downloaded from
  `https://huggingface.co/datasets/princeton-nlp/SWE-bench_Verified/resolve/c104f840cc67f8b6eec6f759ebc8b2693d585d4a/data/test-00000-of-00001.parquet`)
  holds 500 rows; `difficulty == "15 min - 1 hour"` selects 261 of them, 117 from `django/django`.
- Instance: `django__django-12155` — `docutils reports an error rendering view docstring when the
  first line is not empty` (Django ticket #30974, PR merged 2019-11-30).
- Repository: `https://github.com/django/django.git`, `base_commit`
  `e8fcdaad5c428878d0a5d6ba820d957013f75595` (`version` 3.1 in the dataset row).
- `FAIL_TO_PASS` (1): `test_parse_rst_with_docstring_no_leading_line_feed (admin_docs.test_utils.TestUtils)`.
- `PASS_TO_PASS` (6): `test_description_output`, `test_initial_header_level`, `test_parse_docstring`,
  `test_parse_rst`, `test_publish_parts`, `test_title_output`, all `(admin_docs.test_utils.TestUtils)`.
  All 7 are in the one file `tests/admin_docs/test_utils.py`.

## Why this instance (and what was rejected)

`bench validate`'s `runner: unittest` grading (`src/harness_bench/grade/correctness.py`) only parses
`unittest.TextTestRunner`'s own summary text (`Ran N tests in ...` / `OK` or `FAILED (...)`) from
stderr — there is no pytest-summary parser (`grade/correctness.py` line 150: only `unittest` and
`dotnet` are built). Most SWE-bench repos (astropy, matplotlib, scikit-learn, pytest, pylint,
requests, flask, sphinx, xarray, seaborn — 269 of the 500 Verified rows) run their suites through
pytest and print pytest's own summary, which this parser cannot read; adding a pytest parser is
grader code and out of scope for this task. Django is the one large SWE-bench repo whose own test
runner (`tests/runtests.py`, `django.test.runner.DiscoverRunner`) is built directly on
`unittest.TextTestRunner` and prints exactly that format — confirmed by running it (below), not
assumed. Within `django/django` at the 15-60 minute band (117 rows), `django__django-12155` was
chosen for portability and the smallest surface that still discriminates: 1 FAIL_TO_PASS + 6
PASS_TO_PASS, all pure Python string/rendering logic in one file (no database backend, no GIS, no
system checks against DB schema, no Selenium, no memcached), so no external service is needed and
`django/db` and `django/contrib/gis` never load. Rejected within the same band while narrowing to
this one: none needed to be run to fail before this one succeeded (this was the first instance
tried, on the strength of the file-count/blast-radius screen above); no other instance was run and
rejected. The dependency it does need beyond Django itself (`docutils`, for `parse_rst`) is pure
Python and installs natively on Windows — confirmed below.

## Correctness: the hidden tests

`tests/tests/admin_docs/test_utils.py` is the file's content **after** SWE-bench's own `test_patch`
for this instance — i.e., the same overlay-a-file-at-its-real-path mechanism E6 and D2 use for their
hidden test projects, here applied to one existing upstream file rather than a new one. It carries
all 7 tests (the 1 FAIL_TO_PASS + 6 PASS_TO_PASS); the `test_trim_docstring` test the patch deletes
is gone. `correctness.grade()` copies `tasks/E4/tests/` over the working copy
(`shutil.copytree(task_dir / "tests", work, dirs_exist_ok=True)`), so this file replaces the
upstream one at grading time only — it is never in the agent's own workspace (`workspace/README.md`).

The base code (`django/contrib/admindocs/utils.py`'s `trim_docstring`, still present, unpatched)
strips indentation using the first line's own indent, which is 0 for a docstring whose text starts
on the opening line — the bug in `prompt.md`. The hidden test's body assertion
(`parse_rst(body, '') == '<p>second line</p>\n'`) fails against that: `trim_docstring` does not
strip the second line's leading four spaces correctly for this shape, so `docutils` renders it as an
indented literal block and emits a `system-message` node instead of a plain `<p>`, which
`captured_stderr` in the same test also converts into a `stderr.getvalue() != ''` follow-on failure
path — a plausible near-miss (e.g. a fix that trims correctly but still writes to stderr) would still
be caught by that second assertion in the same test.

## Reference solution

`oracle/reference/django/contrib/admindocs/{utils.py,views.py}` are the two files SWE-bench's
`patch` changes, in full, at their real repo-relative paths — the same "full file, real path" shape
E6's `oracle/reference/Problem.cs` uses. The fix drops `trim_docstring` entirely and uses
`inspect.cleandoc` (stdlib), which does not privilege the first line's own indentation.

## Environment (uv-managed, native, no Docker)

`task.yaml`'s `oracle.command` is:

```
uv run --python 3.8 --with-editable . --with docutils python tests/runtests.py -v2 <7 dotted test ids>
```

- `uv run --with-editable .` builds and installs the workspace's own `django/` package (Django's
  `setup.py`/`setup.cfg`: `install_requires = asgiref>=3.2, pytz, sqlparse>=0.2.2`) as an ephemeral
  environment rooted at the command's cwd (the grading copy's root, since `correctness.grade()` runs
  the command with `cwd=work`); `--with docutils` adds the one extra dependency `parse_rst` needs
  that is not in Django's own `install_requires`. Python 3.8 is pinned because Django 3.1's
  `setup.cfg` declares `python_requires = >=3.6` and classifies only 3.6/3.7/3.8; `--python 3.8` lets
  `uv` fetch that interpreter itself if the host does not have it (confirmed: this host did not,
  `uv` downloaded `cpython-3.8.20-windows-x86_64-none` on first use).
- This is one command, invokes `uv` directly (no `cmd.exe`/shell wrapper), and uses only
  forward-slash paths (`tests/runtests.py`) — the portable shape D1/D3/E6/F1 do not use.
- No separate install step is needed or possible: `correctness.grade()` runs exactly one command per
  cell (`src/harness_bench/grade/correctness.py`, `grade()`), so setup and test execution are the
  same `uv run` call.
- `docutils_is_available` (checked by the hidden test file's own `@unittest.skipUnless`) is true once
  `docutils` installs, so the suite runs for real rather than skipping.

assume: `uv` resolves its cache and can download the pinned CPython 3.8 build using only the grading
step's environment allowlist (`HOST_ENV` in `correctness.py`: `PATH`, `SYSTEMROOT`, `SYSTEMDRIVE`,
`WINDIR`, `TEMP`, `TMP` — no `USERPROFILE`/`LOCALAPPDATA`/`APPDATA`), rather than needing one of those
added to `DOTNET_HOST_ENV`'s python analogue (there is none yet). **Confirm:** ran the full 7-label
command under `env -i` restricted to exactly that allowlist plus the three `PYTHON*` variables
`correctness._env()` already sets, on this Windows host, and it built/ran/discriminated the same in
both env shapes (evidence.md, "Base run" and "Reference run" sections; both were run with the
allowlist). **Breaks if false:** on a grading host where `uv` genuinely cannot resolve
`%LOCALAPPDATA%` without the env var (untested — this host's `uv` evidently uses the Windows known-
folder API rather than only the env var), `uv run` would fail to place its cache/python and every
`unittest`-runner task that uses `uv` this way would need `HOST_ENV` extended — a one-line, one-time
engine change, not specific to this task.

## macOS (ADR-0013 Amendment 1)

assume: this task runs natively on macOS unchanged — Django 3.1's own test suite and `docutils` are
pure Python with no Windows-only API, `uv run --python 3.8 --with-editable . --with docutils python
tests/runtests.py ...` is the same command on macOS (no `.exe`, no backslash, no shell), and `uv`
resolves and downloads CPython 3.8 the same way on macOS as it did here for Windows. **Confirm:** run
the same command from a clone of `https://github.com/django/django.git` at
`e8fcdaad5c428878d0a5d6ba820d957013f75595` (with `tasks/E4/tests/` overlaid for the base run, and
`oracle/reference/` overlaid on top of that for the reference run) on a macOS host, and observe the
same 6/7-then-7/7. **Breaks if false:** something in Django 3.1 or `docutils`'s own macOS support is
not portable, which would be a defect specific to this instance rather than the engine-wide Windows-
only gap ADR-0013 §5 records (the engine itself — `procs.py`'s Win32 Job Object — is Windows-only
today regardless of this task; that gap is not re-recorded here). Not measured here (no macOS host in
this worktree).

## Budget

`budget.minutes: 60` (matches `bench/bom.yaml` row 42 and the inventory's stated band). The
reference solution's own oracle run took under 4 seconds end to end (evidence.md: 1.07 s base run,
3.83 s reference run, both `real` wall time under `env -i` with a warm `uv` cache; a cold cache adds
one Django wheel build and one CPython 3.8 fetch, together under 10 s, also observed while authoring
this task). This fits the 60-minute budget with very large headroom — the budget is sized for the
agent's own working time on the issue, not for install+test, which is seconds.

## Verification

Run `uv run python tasks/E4/oracle/grade_e4.py` to evaluate both the base workspace (a fresh clone of
`source.repo`@`source.commit`, unmodified) and the reference solution (that same clone with
`oracle/reference/` overlaid) through `harness_bench.grade.correctness.grade` — network access is
needed for the clone and, on a cold `uv` cache, for `uv`'s own downloads. Evidence is committed in
`oracle/evidence.md`.

## No secrets

`prompt.md` is the upstream GitHub issue text verbatim (public, `django/django`, BSD-3-Clause,
`Copyright (c) Django Software Foundation and individual contributors.`, `LICENSE` in this folder).
No credential, customer data or private content is in this task.
