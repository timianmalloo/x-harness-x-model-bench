# E3 -- TB2 software-engineering task, hard band

**Status: ready.** `prompt.md`, pinned source, `workspace/`, hidden tests, and an oracle that fails
on the base tree and passes on `oracle/reference/` are all present. `uv run bench validate` prints
`ok` (see below).

Selected task: **`extract-moves-from-video`** (Terminal-Bench 2.0, hard band), not
`cancel-async-tasks` (the band's first-alphabetical native task, per
`docs/notes/tb2-native-survey.md`). Why, below.

## Why `extract-moves-from-video`, not `cancel-async-tasks`

R-83 (`docs/notes/rulings.md`) has E3 take "the hard band's first-alphabetical native task" from
the committed survey: `cancel-async-tasks`. Its own hidden test suite
(`tests/test_outputs.py`, upstream) drives 3 of its 6 tests by sending `SIGINT` to a child process
via `subprocess.Popen(...).send_signal(signal.SIGINT)`, then asserting the child's `finally:`
cleanup code ran. Run on this Windows host, against the upstream tests with only the same class of
native-path edit E3 uses elsewhere (`/app/run.py` -> `run.py`), those three tests do not fail on
a missing implementation -- they raise from CPython's own `subprocess.py`:
```
ValueError: Unsupported signal: 2
```
Windows' `Popen.send_signal` implements only `CTRL_C_EVENT`/`CTRL_BREAK_EVENT` for a plain child
process (not POSIX `SIGINT`), and even those require the child to be started with
`CREATE_NEW_PROCESS_GROUP`. This is a genuine platform gap in the *test harness itself*, not
something a native-path edit (a file location) can fix -- rewriting the signal-delivery mechanism
would change what the hidden tests verify, which is authoring a different oracle, exactly what
R-83 forbids as the shortfall response. The other 3 of 6 tests do fail as expected (missing
`run.py`). Full proof, exact command and output: `oracle/evidence.md`.

Per the compiled brief's Done-when ("if `cancel-async-tasks` turns out not to run natively here
after all, stop, record why in the task README, and take the next native task of the same band
from the survey (name it), never an authored substitute"), this folder stops on
`cancel-async-tasks` and takes the survey's next native hard-band task in alphabetical order:
`extract-moves-from-video` (survey list: `cancel-async-tasks`, `extract-moves-from-video`,
`llm-inference-batching-scheduler`, `model-extraction-relu-logits`, `protein-assembly`,
`regex-chess`, `sparql-university`, `torch-pipeline-parallelism`, `torch-tensor-parallelism`).
Checked before committing to it: a repo-wide grep of its `tests/` and `solution/` for
`signal.`/`SIGINT`/`SIGTERM`/`os.fork`/`chroot`/`/proc/`/`setsid`/`subprocess.Popen`/`cuda` found
none (the other seven candidates were grepped the same way with the same result, but
`extract-moves-from-video` is the next one in order and was taken without further screening beyond
that grep and the run itself). No `cancel-async-tasks` files were ever written into this
repository; the finding above is recorded here, not as a stub task folder.

## Upstream task

- **`extract-moves-from-video`**: download a YouTube video of someone playing the text-adventure
  Zork, transcribe the commands the player types, write them one per line to `solution.txt`. Hidden
  tests: `solution.txt` exists, and its Levenshtein similarity to a 280-line reference transcript is
  >= 90%.
- `environment/Dockerfile`: `FROM ubuntu:24.04` / `WORKDIR /app`, no further `RUN` lines -- nothing
  beyond the base image is installed (the survey's own citation for this task's `native` verdict).
- Upstream `task.toml`: `[agent] timeout_sec = 1800.0`, `[verifier] timeout_sec = 1800.0` (30
  minutes) -- smaller than this row's `budget.minutes: 60` (`bench/bom.yaml` row 44). Recorded here
  per R-83 c4; the BOM value itself is the Leader's at the R-83 c5 join (not in this worker's scope)
  and stays 60 in `task.yaml` to agree with the current `bench/bom.yaml`, per the `new-bench-task`
  skill's rule that the task file must agree with the BOM's `budget_minutes`.

## Source pin

- `repo`: `https://github.com/harbor-framework/terminal-bench-2`
- `commit`: `2fd12b88aafdd04a52c298e3940bcb189f9766d6` (full SHA; `git rev-parse HEAD` on a fresh
  clone matched immediately, no `git checkout` needed -- the pinned commit is the default branch's
  tip, same as the survey's own citation).

## Licence

- `license`: `Apache-2.0`. Full text copied verbatim to `tasks/E3/LICENSE` (`diff` against the
  clone's `LICENSE`: identical).
- `copyright`: not stated in-tree. The vendored `LICENSE` is Apache's own boilerplate with its
  `Copyright [yyyy] [name of copyright owner]` placeholder unfilled, and no `NOTICE` file exists at
  this commit (`find . -iname 'NOTICE*'` and a repo-wide grep for a line starting `Copyright` at the
  repo root: both empty, checked on the clone). Recorded as `null` in `task.yaml` rather than
  guessed; GitHub org of record is `harbor-framework`.

## Workspace & tests architecture

- `workspace/`: empty (plus its own `README.md`, overlaid into the base tree along with it, matching
  `tasks/E4/workspace/`'s precedent). Upstream gives the agent nothing to start from either.
- `tests/`: `test_outputs.py`, vendored from upstream with the one native-path edit (`oracle/README.md`).
- `oracle/`: `reference/solve.sh` (vendored unmodified -- it writes the known-correct
  `solution.txt` directly, so proving the oracle discriminates needs no network access),
  `README.md` (methodology), `evidence.md` (the proof run), `vendoring_check.py` (the R-42 c3
  rebuild-equality check).

## `bench validate`

```
$ uv run bench validate
ok: bom, metrics, example matrix and every task folder are valid
```
(2026-09-29, on this host, task status `ready`.)
