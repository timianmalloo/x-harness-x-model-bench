# E4 oracle evidence

Grading matches `src/harness_bench/grade/correctness.py`: the tree under test (the engine's own
`workspace.task_source()` build of `source.repo`@`source.commit`, via a fresh
`workspace.cell_working_copy()`, or that same working copy with `oracle/reference/` overlaid), with
`tasks/E4/tests/` overlaid, executed in its disposable working directory. Produced by `uv run python
tasks/E4/oracle/grade_e4.py` on this Windows host, first 2026-09-29 and re-run 2026-09-29 through
`task.yaml`'s `source.workspace_from: source` opt-in (ORCL-A; docs/lessons/defect-classes.md).

Oracle runner: `unittest` (`src/harness_bench/grade/correctness.py`, `parse_unittest`)
Command:
`uv run --python 3.8 --with-editable . --with docutils python tests/runtests.py -v2 admin_docs.test_utils.TestUtils.test_description_output admin_docs.test_utils.TestUtils.test_initial_header_level admin_docs.test_utils.TestUtils.test_parse_docstring admin_docs.test_utils.TestUtils.test_parse_rst admin_docs.test_utils.TestUtils.test_publish_parts admin_docs.test_utils.TestUtils.test_title_output admin_docs.test_utils.TestUtils.test_parse_rst_with_docstring_no_leading_line_feed`

Runner script: `tasks/E4/oracle/grade_e4.py`

## The tree under test, through the engine's own path

`grade_e4.py` no longer clones Django itself. It calls `workspace.task_source(task_dir,
"grade-e4-probe", tmp / "sources", tmp / "upstream")` — the same function a real cell's bootstrap
calls — which: fetches `source.repo` once into a `--no-checkout` clone cached under `tmp /
"upstream"` (keyed by repo+commit; `workspace.upstream_tree`), verifies that clone's HEAD is
exactly `source.commit` (`workspace._verify_commit`, an exact string match, not "reachable"),
`git archive`s its tree at that commit, overlays `tasks/E4/workspace/` (empty for E4) on top, and
commits the result as the task source's one base commit — no upstream `.git` history reaches it
(R-83). `ws_base` and `ws_ref` are then two independent `workspace.cell_working_copy()` clones of
that one task source, exactly as two real cells of the same task version would get them.

## Fail on the base workspace

Grading call: `correctness.grade(ws_base, task_dir, oracle, out_base, tmp, timeout=300.0)`, where
`ws_base` is the engine's own cell working copy of the task source above, unmodified.

Result:
```python
Result(passed=0, partial_credit=Decimal('0.8571428571428571428571428571'), reason=None,
       evidence='out_base/oracle.log', compile_error=False)
```

Exit code: **1**

Summary from stderr (`parse_unittest`): `Ran 7 tests in 0.194s` / `FAILED (failures=1)` — 6/7 passed.

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
`ws_ref` is a second `workspace.cell_working_copy()` of the same task source as `ws_base`, with
`oracle/reference/` overlaid — the two gold-patched files (`django/contrib/admindocs/utils.py`,
`django/contrib/admindocs/views.py`) at their real repo-relative paths.

Result:
```python
Result(passed=1, partial_credit=Decimal('1'), reason=None, evidence='out_ref/oracle.log',
       compile_error=False)
```

Exit code: **0**

Summary from stderr (`parse_unittest`): `Ran 7 tests in 0.180s` / `OK` — 7/7 passed, including the
previously-failing `test_parse_rst_with_docstring_no_leading_line_feed`.

## Timing (reference solution's own time; budget.minutes: 60)

- `uv run` cold (`uv venv --python 3.8` had never fetched that interpreter on this host): first
  invocation downloaded `cpython-3.8.20-windows-x86_64-none` (~20.6 MiB) — a few seconds, one time.
- Warm-cache `uv run` (original authoring run, 2026-09-29, same repo state and commands; also
  measured standalone under `env -i` with only `HOST_ENV` + the three `PYTHON*` vars set, matching
  the grading step's real environment allowlist): base run **1.068 s** real, reference run
  **3.826 s** real (wall clock, `time` on this Windows/Git-Bash host). Unaffected by the
  `workspace.task_source`/`cell_working_copy` re-run above: that change is to how the tree under
  test is built, not to the `uv run` grading step itself.
- Both are far inside `budget.minutes: 60`; the budget is sized for the agent's own working time on
  the issue, not for install+test.
- The upstream fetch (`workspace.upstream_tree`'s `--no-checkout` clone of `django/django.git`) is
  cached under `upstream_root`, keyed by (repo, commit). `grade_e4.py` uses a fresh
  `tempfile.mkdtemp()` per invocation, so its own `upstream_root` is never reused across separate
  runs of the script: two full runs (fetch, `git archive`, base grade, reference grade) each
  measured **2m 5.9s** wall clock on this host, each paying its own clone. assume: in a real engine
  run, where every cell of a task version shares one `upstream_root` (the tools directory), only
  the first cell pays the clone and later cells reuse it, on the same content-addressed
  create-once-reuse shape `task_source`/`pack_checkout` already use for their own dest; confirm: an
  engine-driven multi-cell E4 run, timing the second cell's `task_source` call; breaks: if
  `upstream_tree`'s landing were per-process rather than per-`upstream_root` path — not the case
  here (`_land`/`os.replace` onto a shared dest, the same mechanism `pack_checkout` uses).

## Env-allowlist check (assume: in oracle/README.md)

Ran the full 7-label command directly (outside `grade_e4.py`, same repo state as the base run above)
under `env -i PATH=... SYSTEMROOT=... SYSTEMDRIVE=... WINDIR=... TEMP=... TMP=...
PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 PYTHONUTF8=1` — i.e. exactly `correctness._env()`'s
`HOST_ENV` set plus its three `PYTHON*` additions, with no `USERPROFILE`/`LOCALAPPDATA`/`APPDATA` —
and got the same `Ran 7 tests ... FAILED (failures=1)` (base, unpatched) and `... OK` (reference,
gold patch applied) results, confirming `uv` does not need those three variables on this host.

## Validate

- `uv run bench validate`: `ok: bom, metrics, example matrix and every task folder are valid`
  (2026-09-29, re-run after `source.workspace_from: source` and `_workspace_builder`'s
  `upstream_root` were wired through; task status `ready`).
