# E3 oracle

Upstream `extract-moves-from-video`'s own `tests/test_outputs.py` (2 tests, unmodified except the
one native-path edit below), run with `pytest` under a pinned, uv-managed CPython 3.13.

## Runner

`oracle.runner: pytest` is set in `task.yaml`, ahead of the grader: `src/harness_bench/grade/correctness.py`'s
`grade()` accepts only `kind in ("unittest", "dotnet")` today (a `pytest` runner that reads a named
JUnit XML report is in a parallel slice, not yet merged -- Measured, per the compiled brief). The
discrimination proof below was therefore run directly with the exact `task.yaml` `oracle.command`,
outside the engine, per R-83 condition 3 ("the upstream tests run on this host fail on the base
tree and pass on the reference"). Once the pytest runner lands, `grade()`'s own
`shutil.copytree(task_dir / "tests", work, dirs_exist_ok=True)` places `tests/test_outputs.py` at
the top level of the working copy, alongside the agent's `solution.txt`, and the command runs with
`cwd=work` -- exactly the layout this proof reproduces by hand.

## The native-path edit

Upstream's `test_outputs.py` hardcodes `Path("/app/solution.txt")` (`/app` is the Dockerfile's
`WORKDIR`, in both `test_solution_file_exists` and `test_solution_content_similarity`). This
benchmark has no container and no `/app`; the agent's `solution.txt` lands at the top level of its
own working copy, so both occurrences become `Path("solution.txt")`, resolved against the oracle
command's `cwd`. No other line changed.

```diff
-    solution_path = Path("/app/solution.txt")
+    solution_path = Path("solution.txt")
```
(applies at both call sites; `oracle/vendoring_check.py` proves it is the *only* difference from
the upstream blob at the pinned commit).

`prompt.md` carries the matching edit: "create a file `solution.txt` in the top level of your
working directory" replaces "create a file `/app/solution.txt`" (one clause; the rest of
`instruction.md` is verbatim).

## Vendored paths (R-83 c2 / R-42 c3)

`task.yaml`'s `source.vendored_paths`:
- `extract-moves-from-video/solution/solve.sh` -> `oracle/reference/solve.sh`, byte-for-byte.
- `extract-moves-from-video/tests/test_outputs.py` -> `tests/test_outputs.py`, plus the one edit above.

`oracle/vendoring_check.py <terminal-bench-2 clone>` rebuilds both from
`git archive <commit> -- <path>` and diffs them against what is committed here (reversing the
edit for the second file). Run against a fresh clone at the pinned commit: `ok` (below).

## Why `extract-moves-from-video`, not `cancel-async-tasks`

R-83's rule takes "the hard band's first-alphabetical native task" -- `cancel-async-tasks` in the
survey. That task's hidden tests (3 of 6) drive their SIGINT-cancellation checks through
`subprocess.Popen(...).send_signal(signal.SIGINT)`. On this Windows host that call raises
`ValueError: Unsupported signal: 2` from the CPython standard library itself (`subprocess.py`'s
`send_signal`: Windows only implements `CTRL_C_EVENT`/`CTRL_BREAK_EVENT` for a plain `Popen`, and
even those need the child started with `CREATE_NEW_PROCESS_GROUP`) -- not a failure of any
implementation under test, the test harness cannot run at all. Full run and exact text: `../README.md`.

This is a real "not native here" finding, not a fixable path reference: rewriting the SIGINT
delivery mechanism would change what the hidden test verifies, which is authoring a different
oracle, the thing R-83 forbids. Per the compiled brief's Done-when, the folder stopped there and
moved to the hard band's next native task, `extract-moves-from-video` (the survey's alphabetical
order: `cancel-async-tasks`, `extract-moves-from-video`, ...). `extract-moves-from-video`'s own
hidden tests use only `pathlib.Path` and a pure-Python Levenshtein distance -- no signals, no
`chroot`/`/proc`/`setsid`, confirmed by a repo-wide grep before selecting it (`../README.md`).
