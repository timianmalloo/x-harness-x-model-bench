# B3 oracle evidence

Grading copy matches `src/harness_bench/grade/correctness.py`: the tree under test, then
`tests/test_b3_hidden.py` overlaid, cwd = that copy. The reference spec and controls stay in
`oracle/reference/` and are not reachable from `workspace/`.

The vendored primer is `workspace/docs/proposals/build-phasing-plan.html`, byte-identical to B1's
copy: 40715 bytes, sha256 `af55c60d8e0c76c77e76a4e6b54d650bd3bdbd45cf63d3de79a8fdf1a4313b43`
(verified by `sha256sum` against `tasks/B1/workspace/docs/proposals/build-phasing-plan.html`,
2026-09-29). It is the `git archive` blob of `docs/proposals/build-phasing-plan.html` at
`496a0a8ca2fae9026927167a8f3e5da0a53f2233` (`git -C C:\projects\cfd-bench rev-parse HEAD`,
re-verified 2026-09-29: the local clone is still pinned at that exact commit). The upstream blob is
CRLF, so `.gitattributes` marks this path `-text` (added alongside B1's entry). `git ls-tree` of
that commit lists no `LICENSE`, `LICENSE.md`, or `COPYING`.

Run on Windows 11 (CPython 3.12.10 via `python`), 2026-09-29.

## 1. Fail on the base workspace

Command (cwd = copy of `tasks/B3/workspace` plus `tests/test_b3_hidden.py`):

```
python -m unittest -v test_b3_hidden
```

Exit code: **1**

Summary: `Ran 4 tests in 0.001s` · `FAILED (failures=4)`

Failing names (all 4, `docs/specs/p1-estimator-validated.md` does not exist):

- `test_spec_file_present`
- `test_spec_required_sections`
- `test_validation_is_against_real_experimental_data`
- `test_section_catalog_detects_selig_and_lednicer`

## 2. Pass on the reference specification

Command (cwd = copy of `tasks/B3/workspace` plus
`oracle/reference/docs/specs/p1-estimator-validated.md` as
`docs/specs/p1-estimator-validated.md`, plus `tests/test_b3_hidden.py`):

```
python -m unittest -v test_b3_hidden
```

Exit code: **0**

Summary: `Ran 4 tests in 0.001s` · `OK`

Failing names: none (0).

## 3. Rejection of each negative control — one plausible wrong answer per decided fact

Each control is a complete specification meeting every item except the one named, so a pass on
the other 3 tests confirms the failing test is not tripped by something else (missing sections, or
the other decided fact). Same command as above, `docs/specs/p1-estimator-validated.md` replaced by
each control in turn.

### 3.1 `control_synthetic_validation.md` — decides validation as a self-consistency/CFD-computed check

Exit code: **1** · Summary: `Ran 4 tests in 0.001s` · `FAILED (failures=1)`

| Test | Result |
| --- | --- |
| `test_spec_file_present` | ok |
| `test_spec_required_sections` | ok |
| `test_validation_is_against_real_experimental_data` | **FAIL** |
| `test_section_catalog_detects_selig_and_lednicer` | ok |

### 3.2 `control_single_format.md` — decides format support as Selig only, caller pre-converts

Exit code: **1** · Summary: `Ran 4 tests in 0.001s` · `FAILED (failures=1)`

| Test | Result |
| --- | --- |
| `test_spec_file_present` | ok |
| `test_spec_required_sections` | ok |
| `test_validation_is_against_real_experimental_data` | ok |
| `test_section_catalog_detects_selig_and_lednicer` | **FAIL** |

Each control fails exactly one test — the one for the decided fact it got wrong — and passes the
other three, including the other content check. So each hidden check measures its own decided
content, not a shared on-topic keyword: no single test fires for more than one control, and no
control trips a test other than its own.

## 4. `bench validate`

Command (repo root):

```
uv run bench validate
```

Output: `ok: bom, metrics, example matrix and every task folder are valid` (CPython 3.14.6 via
`uv run`, 2026-09-29).

## 5. Budget and headroom

- Budget: 20 minutes (1,200 s).
- Reference test suite execution time: 0.001 s.
- Headroom: > 99.99%.
