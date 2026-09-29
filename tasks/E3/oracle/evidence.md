# E3 oracle evidence

Run 2026-09-29 on this Windows host (`worker-sonnet-tb-e3`), against `tasks/E3/tests/test_outputs.py`
and `tasks/E3/oracle/reference/solve.sh` exactly as committed (both verified byte-identical to
`git archive 2fd12b88... -- extract-moves-from-video/{solution/solve.sh,tests/test_outputs.py}`,
with the one recorded native-path edit, by `oracle/vendoring_check.py`, "ok" below).

## Toolchain

- `uv 0.11.26 (396ef7ce4 2026-06-30 x86_64-pc-windows-msvc)`
- `uv run --python 3.13`: resolves to `CPython 3.13.14 (main, Jun 23 2026, 15:19:27) [MSC v.1944 64 bit (AMD64)]`
  (`cpython-3.13.14-windows-x86_64-none`, already present in `uv`'s managed-Python cache on this host).
- `pytest==8.4.1`, `pluggy-1.6.0` (pinned by `--with pytest==8.4.1`, matching upstream `tests/test.sh`'s own pin).

## Base tree (empty `workspace/`; no `solution.txt`)

Command (exactly `task.yaml`'s `oracle.command`, `cwd` = a working copy holding only the vendored
`tests/test_outputs.py`):
```
uv run --python 3.13 --with pytest==8.4.1 pytest test_outputs.py --junitxml=e3.xml -rA
```
Result: **2 failed, 0 passed** (exit 1).
```
FAILED test_outputs.py::test_solution_file_exists - AssertionError: File solution.txt does not exist
FAILED test_outputs.py::test_solution_content_similarity - FileNotFoundError: [Errno 2] No such file or directory: 'solution.txt'
```
`e3.xml`: `tests="2" failures="2" errors="0"`.

## Reference solution (`oracle/reference/solve.sh` run in the same working copy)

`bash oracle/reference/solve.sh` (from the working copy root) writes `solution.txt`, 280 lines,
matching the hidden `SOLUTION` constant verbatim (`solve.sh` is the upstream author's own reference
-- it writes the known-correct transcript directly with `echo ... >> solution.txt`; it does not
itself download or transcribe the video, so the proof needs no network access).

Same command, same working copy, `solution.txt` now present:
Result: **2 passed, 0 failed** (exit 0).
```
PASSED test_outputs.py::test_solution_file_exists
PASSED test_outputs.py::test_solution_content_similarity
```
`e3.xml`: `tests="2" failures="0" errors="0"`.

**The oracle discriminates:** 0/2 on the base tree, 2/2 on the reference solution.

## Vendoring rebuild (R-83 c2 / R-42 c3)

```
$ uv run python tasks/E3/oracle/vendoring_check.py <terminal-bench-2 clone at 2fd12b88...>
ok
```
Run against a fresh clone of `https://github.com/harbor-framework/terminal-bench-2`, `HEAD` already
at `2fd12b88aafdd04a52c298e3940bcb189f9766d6` (verified: no `git checkout` needed after clone).

## The task not selected: `cancel-async-tasks`

`tasks/E3/README.md` "Why `extract-moves-from-video`, not `cancel-async-tasks`" and
`oracle/README.md` give the reasoning; the raw run that produced the finding:

```
$ uv run --python 3.13 --with pytest==8.4.1 pytest test_outputs.py --junitxml=e3.xml -rA
```
(against the upstream `cancel-async-tasks` `tests/test_outputs.py` + `tests/test.py`, the same
`/app/run.py` -> `run.py` native-path edit applied, base tree empty)

Result: **6 failed** (exit 1). 3 of the 6 fail for the expected reason (`run.py` missing /
`ModuleNotFoundError: No module named 'run'`); the other 3
(`test_tasks_cancel_below_max_concurrent`, `test_tasks_cancel_at_max_concurrent`,
`test_tasks_cancel_above_max_concurrent`) fail with:
```
ValueError: Unsupported signal: 2
```
raised from `subprocess.py`'s `Popen.send_signal` (CPython's own Windows implementation), not from
anything the run.py implementation controls -- these three tests cannot execute on this host at
all, regardless of what the agent submits. No task-folder files for `cancel-async-tasks` were
committed; this run was scratch-only, in the session's scratchpad directory outside the repository,
never persisted.

## Validate

`bench validate`: see `../README.md`.
