# E2 — Terminal-Bench 2.0 `count-dataset-tokens` (medium band)

**Status: draft**, advancing to `ready` once `oracle/evidence.md` records the discrimination proof
run on this host (this slice). `prompt.md`, pinned source, `workspace/`, hidden pytest test, and the
upstream reference solution under `oracle/reference/` are all present.

Selected under R-83 (DR-W5-3): `docs/notes/tb2-native-survey.md` verdicts `count-dataset-tokens`
`native` (medium band, first-alphabetical after E1's shortfall claim on `code-from-image`); no
substitute considered (R-83 refuses (b) and (c) as the shortfall).

## Source Pin

- `repo`: `https://github.com/harbor-framework/terminal-bench-2`
- `commit`: `2fd12b88aafdd04a52c298e3940bcb189f9766d6` (the full SHA `2fd12b88` abbreviates; verified
  as the clone's `HEAD` by `git rev-parse HEAD` after `git clone`, same as the survey's method)
- upstream task folder: `count-dataset-tokens/`

## Licence

Terminal-Bench 2.0 is licensed Apache-2.0 (`license: Apache-2.0`). The `LICENSE` file at this
commit is the unfilled template (`Copyright [yyyy] [name of copyright owner]`); no copyright holder
is stated in-repo at this commit, so `task.yaml`'s `source.copyright` records that fact rather than
a guessed name. Full licence text copied to `tasks/E2/LICENSE`.

## Vendored Paths (R-42 c3, R-83 c2)

`task.yaml`'s `source.vendored_paths` lists six files from the upstream `count-dataset-tokens/`
folder, rebuildable byte-for-byte from `git archive 2fd12b88aafdd04a52c298e3940bcb189f9766d6 --
<path>` against a full clone of the upstream repo (`tasks/E2/oracle/vendoring_check.py`; no upstream
clone is committed here, ADR-0013):

| Upstream path | This folder | Edited? |
| --- | --- | --- |
| `count-dataset-tokens/environment/Dockerfile` | `oracle/upstream/Dockerfile` | no (provenance only; no container is built, ADR-0013 Amendment 1) |
| `count-dataset-tokens/task.toml` | `oracle/upstream/task.toml` | no (provenance; source of the `900s` agent/verifier timeout, R-83 c4) |
| `count-dataset-tokens/README.md` | `oracle/upstream/README.md` | no (provenance; the upstream task description) |
| `count-dataset-tokens/instruction.md` | `oracle/upstream/instruction.md` (unedited copy) **and** `prompt.md` (edited copy) | `prompt.md` only |
| `count-dataset-tokens/tests/test_outputs.py` | `tests/test_outputs.py` | yes |
| `count-dataset-tokens/solution/solve.sh` | `oracle/reference/solve.sh` | yes |

Neither `tests/test_outputs.py` nor `oracle/reference/solve.sh` enters `workspace/` (US-8; R-83 c2).

## Native-Path Edit (R-83 c2: "any native-path edit recorded as a diff in the folder's README")

The upstream task runs the agent and the verifier inside a Docker container built `FROM
python:3.13-slim-bookworm` with `WORKDIR /app`, and both the prompt and the test hard-code the
absolute in-container path `/app/answer.txt`. This bench runs the task natively (no container,
ADR-0013 Amendment 1; R-83 condition 1's `native` verdict for this task), so `/app` does not exist
on the host. The one edit, applied identically in all three files, replaces the absolute
in-container path with a path relative to the task's own working directory (the cell's `cwd`, which
plays the role `/app` played inside the container):

```diff
- write the integer number of tokens without spaces or commas (e.g. "1000000") to the file /app/answer.txt.
+ write the integer number of tokens without spaces or commas (e.g. "1000000") to the file answer.txt.
```

```diff
- actual_output = Path("/app/answer.txt").read_text()
+ actual_output = Path("answer.txt").read_text()
```

```diff
- python3 count_tokens.py > /app/answer.txt
+ python3 count_tokens.py > answer.txt
```

No other line differs from the upstream file in each case (`tasks/E2/oracle/vendoring_check.py`
proves it: it undoes exactly this one substitution and asserts byte-equality against the archived
original). `assume:` the cell's working directory is the correct native stand-in for the upstream
`/app` (both are "the one directory the agent's tools default to and the verifier reads from");
**confirm:** `oracle/evidence.md`'s discrimination proof runs `pytest tests/test_outputs.py` with
`cwd` set to the grading copy's working-directory root and finds `answer.txt` there; **breaks:** if
the engine's `task_source()`/`cell_working_copy()` cwd convention ever differs from the grading
copy's cwd, the prompt's instruction and the test's read would point at different places.

## Oracle Runner (R-83 c2, "done when")

`task.yaml`'s `oracle.runner: pytest` is not yet built by `src/harness_bench/grade/correctness.py`
(`grade()` accepts only `"unittest"` and `"dotnet"` today; a `pytest` oracle-runner slice with a
named `--junitxml` report exists on branch `w5-pytest`, not merged at authoring time). `bench
validate` does not gate on `oracle.runner`'s value (`validate_task` in `src/harness_bench/config.py`
checks structure, not the runner enum), so this folder validates `ok` today even though
`grade_cell()` would currently return `Result(None, None, "oracle runner 'pytest' not built ...")`
for a live cell. See `oracle/README.md` and `oracle/evidence.md` for the proof, run directly with
the exact `oracle.command` from `task.yaml` (not yet through `harness_bench.grade.correctness`,
since that module does not dispatch `pytest` yet).

## Workspace

Empty by upstream design (`tasks/E2/workspace/README.md`): the upstream Dockerfile installs nothing
beyond the base image and copies no starter file. `source.workspace_from` is left at its default
(`workspace`), not `source`: this is a per-task subfolder of an 89-task monorepo (E6's pattern, R-83
c2), not a whole-repository pin (E4's pattern), so nothing is vendored beyond the six paths above.
