# A5 Oracle Evidence

Grading copy matches `src/harness_bench/grade/correctness.py`: the workspace under test, then
`tests/test_a5_hidden.py` overlaid, cwd = that copy. The reference spec and controls stay in
`oracle/reference/` and are not reachable from `workspace/`.

The source repository is `https://github.com/timianmalloo/ai-de` pinned at commit
`88e0c33f0b7c419b1e64d87686987374285292d8` (the same repo and commit D1/D2 already vendor
`AgentPlane/WorktreeProvisioner.cs` and `Workbench/AgentWorktree.cs` from; MIT license, Copyright
(c) 2026 timianmalloo).

Run on Windows 11 (CPython 3.14.6 via `uv run` / `python`), 2026-09-29.

## 1. Fail on the base workspace

Command (cwd = copy of `tasks/A5/workspace` plus `tests/test_a5_hidden.py`):

```sh
python -m unittest -v test_a5_hidden
```

Exit code: **1**

Summary: `Ran 7 tests in 0.001s` · `FAILED (failures=7)`

Failing names (all 7, `docs/specs/what-changed-view.md` does not exist):
- `test_spec_file_present`
- `test_spec_required_sections`
- `test_clarification_scope`
- `test_clarification_granularity`
- `test_clarification_source_of_truth`
- `test_clarification_refresh`
- `test_gherkin_acceptance_criteria`

## 2. Pass on the reference specification

Command (cwd = copy of `tasks/A5/workspace` plus `oracle/reference/docs/specs/what-changed-view.md`
as `docs/specs/what-changed-view.md`, plus `tests/test_a5_hidden.py`):

```sh
python -m unittest -v test_a5_hidden
```

Exit code: **0**

Summary: `Ran 7 tests in 0.001s` · `OK`

Failing names: none (0).

## 3. Rejection of each negative control — one plausible wrong answer per clarification

Each control is a complete specification meeting every item except the one named, so a pass on the
other 6 tests confirms the failing test is not tripped by something else (missing sections, a
different clarification, absent Gherkin). Same command as above, `docs/specs/what-changed-view.md`
replaced by each control in turn.

### 3.1 `control_scope_all_lanes.md` — decides scope as every lane / the whole repository

Exit code: **1** · Summary: `Ran 7 tests in 0.001s` · `FAILED (failures=1)`

| Test | Result |
| --- | --- |
| `test_spec_file_present` | ok |
| `test_spec_required_sections` | ok |
| `test_clarification_scope` | **FAIL** |
| `test_clarification_granularity` | ok |
| `test_clarification_source_of_truth` | ok |
| `test_clarification_refresh` | ok |
| `test_gherkin_acceptance_criteria` | ok |

### 3.2 `control_full_diff_content.md` — decides granularity as the full line-by-line diff

Exit code: **1** · Summary: `Ran 7 tests in 0.001s` · `FAILED (failures=1)`

| Test | Result |
| --- | --- |
| `test_spec_file_present` | ok |
| `test_spec_required_sections` | ok |
| `test_clarification_scope` | ok |
| `test_clarification_granularity` | **FAIL** |
| `test_clarification_source_of_truth` | ok |
| `test_clarification_refresh` | ok |
| `test_gherkin_acceptance_criteria` | ok |

### 3.3 `control_audit_log_source.md` — decides the source as the tool-call/audit log

Exit code: **1** · Summary: `Ran 7 tests in 0.002s` · `FAILED (failures=1)`

| Test | Result |
| --- | --- |
| `test_spec_file_present` | ok |
| `test_spec_required_sections` | ok |
| `test_clarification_scope` | ok |
| `test_clarification_granularity` | ok |
| `test_clarification_source_of_truth` | **FAIL** |
| `test_clarification_refresh` | ok |
| `test_gherkin_acceptance_criteria` | ok |

### 3.4 `control_live_streaming.md` — decides refresh as a live-updating stream

Exit code: **1** · Summary: `Ran 7 tests in 0.001s` · `FAILED (failures=1)`

| Test | Result |
| --- | --- |
| `test_spec_file_present` | ok |
| `test_spec_required_sections` | ok |
| `test_clarification_scope` | ok |
| `test_clarification_granularity` | ok |
| `test_clarification_source_of_truth` | ok |
| `test_clarification_refresh` | **FAIL** |
| `test_gherkin_acceptance_criteria` | ok |

Each control fails exactly one test — the one for the clarification it decided wrongly — and passes
the other six, including the other three clarification checks. So each hidden check measures its
own decided content, not a shared on-topic keyword: no single test fires for more than one control,
and no control trips a test other than its own.

## 4. Scripted user matcher precision and recall

Not measured in this slice: `oracle/heldout_questions.yaml` was not authored for A5 (see
`oracle/README.md`, "Not authored in this slice"). `oracle/clarifications.yaml` was checked with
`python -c "from harness_bench.scripted_user import clarifications; clarifications.load('oracle/clarifications.yaml')"`
from the repo root, which parses without error (also exercised by `bench validate`, section 5
below).

## 5. `bench validate`

Command (repo root):

```sh
uv run bench validate
```

Output: `ok`

## 6. Budget and headroom

- Budget: 15 minutes (900 s).
- Reference test suite execution time: 0.001 s.
- Headroom: > 99.9%.
