# E1 — TB2 `code-from-image` (medium-band shortfall)

**Status: ready** (structurally: `bench validate` requirement set, see `oracle/evidence.md` for the
one open item). `prompt.md`, pinned source, `workspace/`, hidden pytest test, and an oracle proven to
fail on the base tree and pass on the reference are all present.

## Selection (R-83)

DR-W5-3 (R-83) selects E1 from the committed survey `docs/notes/tb2-native-survey.md`: E1, E2 and E3
take the first `native` task of the easy, medium and hard bands respectively, by upstream difficulty.
The easy band has zero `native` tasks (all 4 are `apt` or `git-state`), so shortfall rule 1 applies:
E1 takes the nearest band's first-alphabetical `native` task. That is the medium band's
`code-from-image` (the survey's own resolution of the E1/E2 tie-break on the medium band, since E2
also draws from medium — E1 goes first alphabetically, E2 takes the next). This title therefore
records the *actual* band (medium), per shortfall rule 1; `bench/bom.yaml`'s own title field still
reads "easy band" until the Leader lands BOM 0.5 (R-83 condition 5, Not in scope for this slice).

## Upstream task

`code-from-image` (Terminal-Bench 2.0, upstream difficulty `medium`) asks the agent to read a
pseudocode snippet from an image (`code.png`), implement its logic (SHA256 hashing with byte slicing
and a fixed salt over the image's own bytes), run it, and write the resulting hex digest to a file.
It exercises OCR/vision extraction, code comprehension and file I/O — no OS package beyond the
`python:3.13-slim-bookworm` base image, confirmed by the survey (row 12) and re-read here.

## Source pin

- `repo`: `https://github.com/harbor-framework/terminal-bench-2`
- `commit`: `2fd12b88aafdd04a52c298e3940bcb189f9766d6` (the survey's own pinned SHA; re-verified as
  the clone's `HEAD` by `git rev-parse HEAD` immediately after `git clone` into a scratch directory
  outside this repository, 2026-09-29)
- Vendored: `code-from-image/environment/code.png` (upstream-relative path), placed locally as
  `workspace/code.png` (flattened — see "Native-path edits" below). Byte identity: both files hash
  to `f4d0330407b363a9ef03d563e5c2ffd24aa76345f997613741f9fc0935354305` (sha256, 95041 bytes).
  `tests/test_e1_vendoring.py` rebuilds the upstream path from `git archive <commit> --
  code-from-image/environment/code.png` and asserts byte equality against `workspace/code.png`
  (R-42 c3); it skips when no local clone of the upstream is present (same accepted class as
  `tests/test_task_vendoring.py`'s D1 test skipping when `C:/projects/ai-de` is absent) — the rebuild
  was run and observed during this authoring pass (`oracle/evidence.md`).

## Licence

- `license`: `Apache-2.0`
- `copyright`: not recorded. The repo's top-level `LICENSE` carries the Apache-2.0 boilerplate with
  its copyright line unfilled (`Copyright [yyyy] [name of copyright owner]`, verbatim); there is no
  `NOTICE` file and no per-file copyright header anywhere in the repo (checked 2026-09-29, same class
  as B1's task.yaml recording an absence rather than a guess). Full licence text copied to
  `tasks/E1/LICENSE`.

## Native-path edits (R-83 condition 2)

The upstream container places the image at `/app/code.png` (Dockerfile `WORKDIR /app`) and expects
the agent to write `/app/output.txt`; our engine gives each cell a plain working-directory tree, not
a container, so every `/app/...` path becomes a path relative to that working directory (the same
`cwd=ws` convention every task in this repo uses).

- `instruction.md` -> `prompt.md`: `/app/code.png` -> `code.png` (in the current working directory);
  `/app/output.txt` -> `output.txt` (in the current working directory). The hint line is unchanged.
- `tests/test_outputs.py`: `Path("/app/output.txt")` -> `Path("output.txt")` in both test functions
  (two edits, each commented `# native-path edit`). No other line changed; the canary string, the
  docstrings and the expected-hash assertions are verbatim.
- `solution/solve.sh` is vendored **unmodified** into `oracle/reference/solve.sh` (R-83 condition 2:
  provenance for the reference algorithm, not executed by this engine — see "Reference solution"
  below). It still reads/writes `/app/code.png` / `/app/output.txt` internally; that is intentional
  (it documents the upstream algorithm exactly as published) and does not affect grading.

## Reference solution

`correctness.grade()` (`src/harness_bench/grade/correctness.py`) overlays `oracle/reference/` onto a
working copy and then runs the oracle command directly — it does not execute a setup script first
(the E6/E4 precedent: `oracle/reference/` holds the *final correct state* of the files the task
produces, e.g. `Problem.cs`, the two patched Django files). For E1 that final state is one file:
`output.txt`. `oracle/reference/output.txt` is the deterministic SHA256 hex digest that
`oracle/reference/solve.sh`'s own algorithm produces over `workspace/code.png`'s exact bytes —
recomputed and observed to match during this authoring pass (`oracle/evidence.md`), and committed as
a static file since the input (the vendored, pinned image) never changes.

## Workspace & tests architecture

- `workspace/`: `code.png` only (95,041 bytes, vendored above). No test code (US-8).
- `tests/`: `test_outputs.py`, the upstream hidden test file with the two native-path edits above (2
  pytest cases: `test_output_file_exists`, `test_output_is_correct`).
- `oracle/`: `reference/solve.sh` (upstream provenance, unmodified), `reference/output.txt` (the
  overlay-ready final state), `README.md`, `evidence.md`.

## The one disclosed gap

`task.yaml` sets `oracle.runner: pytest`. `src/harness_bench/grade/correctness.py`'s `grade()`,
`build_and_suite_clean()` and `regression_count()` each currently accept only `kind in ("unittest",
"dotnet")` (lines 150, 246, 388) and return `Result`/`Score(None, "oracle runner 'pytest' not built
...")` for any other value, including `pytest` — the parallel grader slice that reads a named JUnit
XML report is not merged into this worktree (per this task's brief, sourced from the Leader). So a
live cell graded against E1 today would read NA with that reason, not a real pass/fail. This is
disclosed, not fixed here (Not in scope: the correctness grader). The discrimination proof below was
therefore run with the exact oracle command directly on this host, outside `correctness.grade()`, and
is recorded with its counts in `oracle/evidence.md`.
