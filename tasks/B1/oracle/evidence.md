# B1 oracle evidence

Grading copy matches `src/harness_bench/grade/correctness.py`: the tree under test, then `tests/test_b1_hidden.py` overlaid, cwd = that copy. The reference spec stays in `oracle/reference/` and is not in `workspace/`.

The vendored primer is `workspace/docs/proposals/build-phasing-plan.html`. It is the `git archive` blob of `docs/proposals/build-phasing-plan.html` at `496a0a8ca2fae9026927167a8f3e5da0a53f2233` (`git -C C:\projects\cfd-bench rev-parse HEAD`). Working tree and index both match that blob: 40715 bytes, sha256 `af55c60d8e0c76c77e76a4e6b54d650bd3bdbd45cf63d3de79a8fdf1a4313b43`. The upstream blob is CRLF, so `.gitattributes` marks this path `-text`. `git ls-tree` of that commit lists no `LICENSE`, `LICENSE.md`, or `COPYING`.

## Fail on the base workspace

Command (cwd = copy of `tasks/B1/workspace` plus `tests/test_b1_hidden.py`):

```
python -m unittest -v test_b1_hidden
```

Exit code: **1**

Summary: `Ran 2 tests` / `FAILED (failures=2)`

Failing names:

- `test_spec_file_present` (FAIL) — `docs/specs/p0-conventions-and-spine.md` is missing
- `test_spec_required_sections` (FAIL) — `docs/specs/p0-conventions-and-spine.md` is missing

## Pass on the reference

Command (cwd = copy of `tasks/B1/oracle/reference/` plus `tests/test_b1_hidden.py`):

```
python -m unittest -v test_b1_hidden
```

Exit code: **0**

Summary: `Ran 2 tests` / `OK`. No failing names.

## Status

`ready`. The skill checklist holds: source repo and commit are pinned, `prompt.md` is present, `workspace/` holds the primer, `tests/` and `oracle/` are non-empty, and the hidden tests fail on the base workspace and pass on the reference spec. The licence is recorded as none because the operator decided on 2026-09-25 to proceed without a licence file.
