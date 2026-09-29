# C2 oracle evidence

Grading copy matches `src/harness_bench/grade/correctness.py`: the tree under test, then
`tests/test_c2_hidden.py` overlaid, cwd = that copy. The reference architecture note and the two
controls stay in `oracle/reference/` and are not reachable from `workspace/`.

The given spec, `workspace/docs/specs/freshness-prober.md`, is a byte-for-byte copy of
`tasks/B2/oracle/reference/docs/specs/freshness-prober.md` (`diff` exits 0, no output) — R-82
condition 2: "the given is the spec named above, verbatim." `workspace/LICENSE` is the same ai-de
MIT license text B2/A5/D2 already vendor from commit `88e0c33f0b7c419b1e64d87686987374285292d8`.

Run on Windows 11 (CPython 3.12.10 via `python`), 2026-09-29. Each case below copies
`tasks/C2/workspace/` plus `tests/test_c2_hidden.py` into a fresh temp directory, places the
candidate `docs/architecture.md` (or none, for the base case), and runs from that directory.

## 1. Fail on the base workspace

Command (cwd = copy of `tasks/C2/workspace` plus `tests/test_c2_hidden.py`; the workspace carries
no `docs/architecture.md`):

```
python -m unittest -v test_c2_hidden
```

Exit code: **1**

Summary: `Ran 5 tests in 0.001s` / `FAILED (failures=5)`

Failing names (all five — `docs/architecture.md` itself is missing):

- `test_architecture_document_present`
- `test_architecture_required_sections`
- `test_decision_names_alternatives`
- `test_comparison_source_is_the_repository_not_the_daemon`
- `test_prober_does_not_repair_the_drift_itself`

## 2. Pass on the reference

Command (cwd = copy of `tasks/C2/workspace` plus `oracle/reference/docs/architecture.md` as
`docs/architecture.md`, plus `tests/test_c2_hidden.py`):

```
python -m unittest -v test_c2_hidden
```

Exit code: **0**

Summary: `Ran 5 tests in 0.001s` / `OK`. No failing names.

## 3. Content-check discrimination: one committed negative control per check

Each control is a complete, structurally-passing architecture note (all 8 required headings
present and non-empty, `## Decision` names an alternative) that is wrong on exactly one decided
fact, in the pattern `tasks/A5` uses. Same command as above, `docs/architecture.md` replaced by
each control in turn.

### 3.1 `control_daemon_state_source.md` — `IRevisionProbe` returns the daemon's own cached state instead of reading the repository

Exit code: **1** · Summary: `Ran 5 tests in 0.001s` / `FAILED (failures=1)`

| Test | Result |
| --- | --- |
| `test_architecture_document_present` | ok |
| `test_architecture_required_sections` | ok |
| `test_decision_names_alternatives` | ok |
| `test_comparison_source_is_the_repository_not_the_daemon` | **FAIL** |
| `test_prober_does_not_repair_the_drift_itself` | ok |

### 3.2 `control_prober_self_repairs.md` — `FreshnessProbeService` re-extracts the drifted scope itself before raising the incident

Exit code: **1** · Summary: `Ran 5 tests in 0.001s` / `FAILED (failures=1)`

| Test | Result |
| --- | --- |
| `test_architecture_document_present` | ok |
| `test_architecture_required_sections` | ok |
| `test_decision_names_alternatives` | ok |
| `test_comparison_source_is_the_repository_not_the_daemon` | ok |
| `test_prober_does_not_repair_the_drift_itself` | **FAIL** |

Each control fails exactly the one test for the decided fact it got wrong, and passes the other
four — including the other content check and the three structural checks. So each decided-content
check measures its own decided fact, not a shared on-topic keyword: no single test fires for more
than one control, and no control trips a test other than its own.

**Note on a first-draft miss (recorded for the class, not hidden):** the first drafts of both
control files carried a one-line editorial preamble above `# Freshness Prober architecture`
("This control is otherwise complete and correct... it must fail only `test_...`"). That preamble
itself contained the words the regex looks for (e.g. "the daemon's own cached state, not the
repository"), so `control_daemon_state_source.md` passed every test on the first run instead of
failing its own check — the meta-commentary, not the candidate document, satisfied the check. Both
preambles were removed so each control file is nothing but the candidate document, matching
`tasks/A5`'s controls (title line straight into `## Context`, no editorial wrapper). Re-run after
the fix is section 3 above.

## 4. `bench validate`

Command (repo root):

```
uv run bench validate
```

Output: `ok`

## 5. Budget and headroom

- Budget: 30 minutes (1800 s), matching `bench/bom.yaml`'s C2 row and R-82 condition 2.
- Hidden-test execution time (all four cases above): `Ran 5 tests in 0.001s` each — under 0.1% of
  budget.
- The given spec is 111 lines, the same document B2 already produces at a 20-minute budget; this
  task asks for a design derived from it (8 headings, one ADR-style decision), not a second
  authoring of the spec's own content, so 30 minutes carries headroom over B2's 20.

## 6. Status

`ready`. Source repo and commit are pinned (same ai-de commit as B2/D1/D2), `prompt.md` is
present, `workspace/` holds the given spec and `LICENSE`, `tests/` and `oracle/` are non-empty,
and the hidden tests fail on the base workspace and pass on the reference architecture note, with
each of the two content checks individually discriminating against its own committed control.
