# E1 oracle

The oracle validates a candidate's `output.txt` against the upstream TB2 test suite
(`tests/test_outputs.py`, 2 pytest cases, native-path edited — see `../README.md`), executed via a
pinned `uv`-managed Python 3.13 and pytest 8.4.1, with a named JUnit XML report.

## Command

```
uv run --no-project --python 3.13 --with pytest==8.4.1 pytest test_outputs.py --junitxml=e1.xml -v
```

- `--no-project`: the grading working copy is a disposable tree, never the harness-bench repo itself;
  without this flag `uv run`, invoked from inside a checkout, discovers and builds `harness-bench`'s
  own `pyproject.toml` (observed on this host during authoring — a real, not hypothetical, failure
  mode this flag avoids).
- `--python 3.13`: matches the upstream Docker image exactly (`python:3.13-slim-bookworm`); `uv`
  resolved and downloaded `cpython-3.13.14` on this host (see `evidence.md`).
- `pytest==8.4.1`: the exact version upstream's own `tests/test.sh` pins.
- `--junitxml=e1.xml`: a bare file name (no directory component), the form the (unmerged) pytest
  grader slice reads.

## Grading gap (disclosed, not fixed here)

`src/harness_bench/grade/correctness.py` only builds `oracle.runner` values `"unittest"` and
`"dotnet"`; `"pytest"` returns NA `"oracle runner 'pytest' not built"` from every one of its three
gates (`grade`, `build_and_suite_clean`, `regression_count`). The grader slice that adds a pytest
runner reading a named JUnit XML report is not merged into this worktree. The discrimination proof
below therefore runs the command above directly (the same working-copy shape `correctness.grade()`
builds: `workspace/` with `tests/` overlaid, or with `oracle/reference/` overlaid), not through
`correctness.grade()` itself. Not in scope for this task folder: the correctness grader (the Leader's
parallel slice).

## Reference solution

`oracle/reference/solve.sh` is the upstream `solution/solve.sh`, vendored unmodified (R-83 condition
2) — it documents the exact algorithm (`sha256(sha256(img_bytes), sha256(img_bytes)[:10],
b"0000TBENCH-SALT")`, hex-encoded) as published. `oracle/reference/output.txt` is that algorithm's
deterministic output over `workspace/code.png`'s exact vendored bytes, computed and verified during
this authoring pass (`evidence.md`) and committed as a static file — it is the overlay `grade_e1.py`
and any future `correctness.grade()` pytest support apply on top of `workspace/` to build the
"passes on the reference" working copy, the same shape `oracle/reference/Problem.cs` (E6) and the two
patched Django files (E4) already use.

## macOS (ADR-0013 Amendment 1)

assume: this task runs natively on macOS unchanged — the hidden test (`test_outputs.py`) is pure
Python stdlib (`pathlib`), the reference algorithm (`hashlib.sha256`, byte slicing) is pure Python
stdlib too, `uv run --no-project --python 3.13 --with pytest==8.4.1 pytest test_outputs.py
--junitxml=e1.xml -v` is the same command on macOS (no `.exe`, no backslash, no shell), and `uv`
resolves and downloads CPython 3.13 the same way on macOS as it did here for Windows. **Confirm:**
run the same command against `workspace/` (base) and `workspace/` + `oracle/reference/output.txt`
(reference) on a macOS host, and observe the same 0/2-then-2/2. **Breaks if false:** something in
`uv`'s macOS resolution of CPython 3.13 or pytest 8.4.1 is not portable, a defect specific to this
instance rather than the engine-wide Windows-only gap ADR-0013 §5 already records. Not measured here
(no macOS host in this worktree).

## Verification

`uv run python tasks/E1/oracle/grade_e1.py` runs `correctness.grade()` against both trees through the
present (pytest-less) grader and records its NA reason — confirming, not contradicting, the disclosed
gap above. The real discrimination proof (fail on base, pass on reference, with pytest's own counts)
is the direct `uv run ... pytest ...` command above, recorded in `evidence.md`.
