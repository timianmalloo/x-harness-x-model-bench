# A4 Oracle Evidence

Grading copy matches `src/harness_bench/grade/correctness.py`: the workspace under test, then `tests/test_a4_hidden.py` overlaid, cwd = that copy. The reference spec stays in `oracle/reference/` and is not reachable from `workspace/`.

The source repository is `https://github.com/timianmalloo/cfd-bench` pinned at commit `496a0a8ca2fae9026927167a8f3e5da0a53f2233` (the same repo pin as B1, D3, F1; operator license decision 2026-09-25: none, operator's own repository).

## 1. Fail on the base workspace

Command (cwd = copy of `tasks/A4/workspace` plus `tests/test_a4_hidden.py`):

```sh
python -m unittest -v test_a4_hidden
```

Exit code: **1**

Summary: `Ran 8 tests in 0.002s` · `FAILED (failures=8)`

Failing names (all 8):
- `test_spec_file_present` (FAIL) — `docs/specs/reusable-wing-definition.md` is missing
- `test_spec_required_sections` (FAIL) — `docs/specs/reusable-wing-definition.md` is missing
- `test_clarification_persistence_vs_sharing` (FAIL) — `docs/specs/reusable-wing-definition.md` is missing
- `test_clarification_format` (FAIL) — `docs/specs/reusable-wing-definition.md` is missing
- `test_clarification_versioning` (FAIL) — `docs/specs/reusable-wing-definition.md` is missing
- `test_clarification_validation` (FAIL) — `docs/specs/reusable-wing-definition.md` is missing
- `test_clarification_scope` (FAIL) — `docs/specs/reusable-wing-definition.md` is missing
- `test_gherkin_acceptance_criteria` (FAIL) — `docs/specs/reusable-wing-definition.md` is missing

## 2. Pass on the reference specification

Command (cwd = copy of `tasks/A4/workspace` plus `oracle/reference/docs/specs/reusable-wing-definition.md` and `tests/test_a4_hidden.py`):

```sh
python -m unittest -v test_a4_hidden
```

Exit code: **0**

Summary: `Ran 8 tests in 0.009s` · `OK`

Failing names: none (0).

## 3. Rejection of negative control (`assumes_cloud_sharing.md`)

Command (cwd = copy of `tasks/A4/workspace` with control spec as `docs/specs/reusable-wing-definition.md` plus `tests/test_a4_hidden.py`):

```sh
python -m unittest -v test_a4_hidden
```

Exit code: **1**

Summary: `Ran 8 tests in 0.003s` · `FAILED (failures=7)`

Passing: `test_spec_file_present` (file exists).
Failing names (7):
- `test_spec_required_sections` (FAIL)
- `test_clarification_persistence_vs_sharing` (FAIL)
- `test_clarification_format` (FAIL)
- `test_clarification_versioning` (FAIL)
- `test_clarification_validation` (FAIL)
- `test_clarification_scope` (FAIL)
- `test_gherkin_acceptance_criteria` (FAIL)

The hidden tests discriminate: they fail on the base workspace, pass on the reference spec, and reject a spec that assumes the wrong architectural paradigm (cloud sharing vs local file persistence).

## 4. Scripted user matcher precision and recall

Evaluating `oracle/heldout_questions.yaml` (39 labelled questions across 5 clarifications, near-misses, and off-topic questions) against `oracle/clarifications.yaml` via `harness_bench.scripted_user.matcher.match`:
- Total questions: 39
- Correct match decisions: 39 / 39 (100% precision and recall on exact, normalised, near-miss, and off-topic sets)
- Zero ambiguous collisions across the 5 clarification queries.

## 5. Budget and Headroom

Budget: 15 minutes (900 seconds).
Reference test suite execution time: 0.009 s.
Headroom: > 99.99%.
