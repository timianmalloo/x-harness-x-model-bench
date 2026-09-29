# E2 oracle evidence

Grading copy layout matches `src/harness_bench/grade/correctness.py`'s own `grade()`: the tree under
test (`tasks/E2/workspace` for the base run, or the same tree plus a produced `answer.txt` for the
reference run), with the *contents* of `tasks/E2/tests/` copied into the same directory
(`shutil.copytree(task_dir / "tests", work, dirs_exist_ok=True)` — the destination is the copy's
root, not a `tests/` subdirectory there, which is why `oracle.command` targets `test_outputs.py`,
not `tests/test_outputs.py`).

Oracle runner: `pytest` (`task.yaml`'s `oracle.runner`). **Not yet dispatched by
`src/harness_bench/grade/correctness.py`**: `grade()` accepts only `kind in ("unittest", "dotnet")`
today (`src/harness_bench/grade/correctness.py:150`); a `pytest` oracle-runner slice exists on
branch `w5-pytest`, unmerged at authoring time (`git log w5-pytest` shows no commits past `main`'s
tip `ab407c7` — the branch is a reserved pointer, not yet started). This proof therefore runs the
exact `oracle.command` from `task.yaml` directly (`uv run --python 3.13 --with pytest==8.4.1
pytest test_outputs.py --junitxml=e2.xml -rA`), with `cwd` built the same way `grade()` builds it,
rather than through `harness_bench.grade.correctness.grade`.

`bench validate` does **not** reject `oracle.runner: pytest` (the "if bench validate rejects runner
pytest ... say so and leave that one line for the Leader" contingency in the brief does not apply):
`validate_task` in `src/harness_bench/config.py` checks `task.yaml`'s structure (id, schema, status,
scenario/budget agreement with the BOM, graders, source pin, workspace presence, vendoring/pack
scan, profile-path scan) but never reads `oracle.runner`'s value against an enum. See "Validate"
below for the actual, measured `bench validate` output.

## Toolchain versions (R-83 c3)

- `uv`: `0.11.26 (396ef7ce4 2026-06-30 x86_64-pc-windows-msvc)`
- Python (via `uv run --python 3.13`): `3.13.14` (`uv`-managed, matching the upstream
  `python:3.13-slim-bookworm` base image's major.minor)
- `pytest`: `8.4.1` (pinned, matching upstream `tests/test.sh`'s own `-w pytest==8.4.1`)
- Reference-solution packages (pinned in `oracle/reference/solve.sh`, matching upstream
  `solution/solve.sh`): `datasets==4.0.0`, `transformers==4.56.0`, `jinja2==3.1.6`
- macOS: **unverified** (ADR-0013 Amendment 1 / R-83 c3 — not a reason to skip this task)

## `task.toml` agent timeout (R-83 c4)

Upstream `task.toml` (`tasks/E2/oracle/upstream/task.toml`): `[agent] timeout_sec = 900.0` (15 min)
and `[verifier] timeout_sec = 900.0`. Both are below the BOM's 60-minute budget
(`bench/bom.yaml` E2: `budget_minutes: 60`), so this row does not need the budget tightened
(R-83 c4: "the BOM budget stays 60 unless the timeout is smaller"). `bench/bom.yaml` is not in
scope for this task folder (Leader join, R-83 c5).

## A second native-run finding, disclosed (reference solution only, not the task or the test)

`oracle/reference/solve.sh` (upstream-pinned, the one native-path edit only) calls
`ds.map(count_tokens, num_proc=os.cpu_count())` with no `if __name__ == "__main__":` guard. Under
Linux's fork-based multiprocessing (the upstream container) that is fine; under Windows' spawn
start method each worker process re-imports and re-executes the top-level module, re-entering
`ds.map` and spawning again. **Measured:** the first attempt at this proof, run with the vendored
`num_proc=os.cpu_count()` unchanged, produced a 29 MB `run.log` of repeated
`RuntimeError: An attempt has been made to start a new process before the current process has
finished its bootstrapping phase` before the run was stopped (`TaskStop`); no stray process
survived the stop (`Get-CimInstance Win32_Process -Filter "Name='python.exe'"` after the stop,
filtered for `count_tokens`/`scratch-tb2` in `CommandLine`: none). This proof's reference run
therefore drops `num_proc` (single-process `ds.map(count_tokens)`) — the filtered dataset is 26
rows, and single-process mapping took under 1 second. **This is not a task-content or test-content
edit** (unlike the `/app/answer.txt` path substitution): `oracle/reference/solve.sh` still carries
only that one documented edit (`tasks/E2/README.md`; `oracle/vendoring_check.py` proves it), and an
agent attempting this task is free to write a multiprocessing-safe script of its own, or none at
all — nothing in `prompt.md` or `tests/test_outputs.py` mentions or requires multiprocessing. The
script actually run for this proof is recorded here rather than silently substituted.

## Fail on the base tree

Command (`cwd` = the grading copy's root: `tasks/E2/workspace/` — empty, `workspace/README.md`
only — with `tasks/E2/tests/test_outputs.py` copied in as `test_outputs.py`):

```
uv run --python 3.13 --with pytest==8.4.1 pytest test_outputs.py --junitxml=e2.xml -rA
```

Exit code: **1**

```
============================= test session starts =============================
platform win32 -- Python 3.13.14, pytest-8.4.1, pluggy-1.6.0
collected 1 item

test_outputs.py F                                                        [100%]

================================== FAILURES ===================================
_____________________ test_command_output_content_example _____________________
    def test_command_output_content_example():
        expected_output = "79586"
>       actual_output = Path("answer.txt").read_text()
E       FileNotFoundError: [Errno 2] No such file or directory: 'answer.txt'
=========================== short test summary info ===========================
FAILED test_outputs.py::test_command_output_content_example - FileNotFoundErr...
============================== 1 failed in 0.14s ==============================
```

Counts: **1 collected, 0 passed, 1 failed.**

## Pass on the reference solution

`oracle/reference/solve.sh` run first (single-process variant, above) against a fresh HuggingFace
download of `Qwen/Qwen2.5-1.5B-Instruct` (tokenizer only) and
`ryanmarten/OpenThoughts-1k-sample` (`metadata` config, `train` split, 26 rows after filtering to
`domain in {chemistry, biology, physics}`), producing `answer.txt` = `79586` (matches upstream
`tests/README.md`'s stated correct answer). Then the same command as above, `cwd` = the grading
copy's root with that `answer.txt` present:

```
uv run --python 3.13 --with pytest==8.4.1 pytest test_outputs.py --junitxml=e2.xml -rA
```

Exit code: **0**

```
============================= test session starts =============================
platform win32 -- Python 3.13.14, pytest-8.4.1, pluggy-1.6.0
collected 1 item

test_outputs.py .                                                        [100%]

=================================== PASSES ====================================
=========================== short test summary info ===========================
PASSED test_outputs.py::test_command_output_content_example
============================== 1 passed in 0.15s ===============================
```

Counts: **1 collected, 1 passed, 0 failed.**

An oracle that passes the base tree measures nothing; it does not here.

## Vendoring

`uv run python tasks/E2/oracle/vendoring_check.py <terminal-bench-2 clone>`: `ok` (7 destination
files checked against 6 archived paths, `git -c core.autocrlf=false archive
2fd12b88aafdd04a52c298e3940bcb189f9766d6 -- <paths>`).

## Validate

- `uv run bench validate`: `ok: bom, metrics, example matrix and every task folder are valid`
  (status `draft`; see `task.yaml`'s status comment for the remaining step to `ready`).
