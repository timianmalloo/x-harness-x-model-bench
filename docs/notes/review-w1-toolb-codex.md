---
id: review-w1-toolb-codex
title: W1-TOOLB cross-vendor join review
type: note
owner: worker-codex-rtoolb
tags: [coordination, review, TOOL-B]
links:
  - type: relates-to
    target: coordination-finish-harness-bench
review-by: 2026-10-24
---

# W1-TOOLB join review — Codex

**Verdict: CLEAR for the R-19 unit-level join scope.** The red commit is tests only and fails for the absent control; the fix passes the focused test file. The three independently seeded review mutants were each killed by a named test. This verdict does not re-derive the phase-1 figure 2267: R-19 expressly flags that figure and schedules a later run with a retained session database (`docs/notes/rulings.md:279-290`).

## Findings

| Finding | Evidence and judgment |
| --- | --- |
| F1 — red and green observed | `e53a7bc` changes only `tests/test_mutate_check.py` (`git show --stat e53a7bc`); the added cases are at `tests/test_mutate_check.py:65-210`. In a detached worktree of that SHA, `uv run pytest -q -p no:cacheprovider tests/test_mutate_check.py` gave **14 failed, 8 passed**: the new API was absent and the `--cosmic-ray` CLI branch treated the option as a path. `0e5ddb3` changes only `tools/mutate_check.py` (`git show --stat 0e5ddb3`); the same focused command in a detached worktree gave **22 passed**. |
| F2 — kill requires a named pytest failure | `tools/mutate_check.py:37-46` extracts `FAILED <node id>` lines and matches an exact named node, a named parametrized case, or a test under a named file; `tools/mutate_check.py:73-85` requires a normal worker, Cosmic Ray outcome `killed`, and that match before returning `killed` with the matched test ID. `tools/mutate_check.py:121-150` derives each dump row, counts only derived `killed` rows, names the matched test, and counts Cosmic Ray's overstated kills separately. The positive and unrelated-failure cases are asserted at `tests/test_mutate_check.py:80-95,133-135`; the CLI positive case is at `tests/test_mutate_check.py:197-210`. **Yes** for the tested pytest output contract. |
| F3 — collection error, timeout, exit-2-shaped interruption are not kills | Collection error and interrupted-run fixtures have no `FAILED` line and expect `error` (`tests/test_mutate_check.py:96-112`); the timeout sentinel expects `timeout` (`tests/test_mutate_check.py:113-117`). The classification branches are at `tools/mutate_check.py:73-85`, and the CLI marks a timeout an overstated kill with exit 1 (`tests/test_mutate_check.py:181-194`; `tools/mutate_check.py:139-151`). **Yes** for all three seeded cases. Cosmic Ray's dump has no exit-code field (`cosmic_ray/work_item.py:32-39` in the installed 8.7.0 package), so the exit-2 case is identified by its representative interruption output, not by a numeric exit-code assertion. |
| F4 — dump schema established from Cosmic Ray itself | The installed package metadata says version 8.7.0 (`cosmic_ray-8.7.0.dist-info/METADATA:1-3`). Its `cosmic_ray/cli.py:204-210,225-229` specifies and emits one JSON `[WorkItem, WorkResult|null]` pair per line; `cosmic_ray/cli.py:56-68` stringifies module paths and serializes outcome enum values. `cosmic_ray/work_item.py:32-39,77-86` defines the fields. Cosmic Ray labels any nonzero subprocess result and timeout `KILLED` (`cosmic_ray/testing.py:69-79`). The control consumes that pair at `tools/mutate_check.py:108-135`; its synthetic dump fixture has the matching shape (`tests/test_mutate_check.py:156-161`). **Yes**: the implementation's stated schema matches source inspected at the pinned version, rather than an inferred format. |
| F5 — narrow test weakness, no join block | The mixed-row test asserts `overstated == 1` for one named kill plus one error (`tests/test_mutate_check.py:164-178`). Review mutant M3 reversed the condition at `tools/mutate_check.py:126`; its two wrong contributions canceled, so that particular test passed. Both single-row CLI tests at `tests/test_mutate_check.py:181-210` failed and killed M3. A later test improvement could assert per-row overstatement or include unequal populations; the existing CLI checks still detect this mutant. |

## Independent mutation probes

All probes used one detached `git worktree add --detach` at `0e5ddb3`. I restored `tools/mutate_check.py` to that commit between probes and ran `uv run pytest -q -p no:cacheprovider tests/test_mutate_check.py --tb=no` for each. The clean baseline was 22 passed. The worktree was clean and removed after the probes; the `w1-toolb-control` checkout was not edited.

| Mutant of `tools/mutate_check.py` | Result | Named killing test |
| --- | --- | --- |
| M1, line 82: `if match is not None` → `if match is None` | **Killed**, 6 failed / 16 passed | `tests/test_mutate_check.py::test_cosmic_ray_verdict_only_a_named_failure_is_a_kill[result0-killed-tests/test_ledger.py::test_tail_repaired]` (`tests/test_mutate_check.py:80-85,133-135`) |
| M2, line 76: `output == "timeout"` → `output == "time-out"` | **Killed**, 2 failed / 20 passed | `tests/test_mutate_check.py::test_cosmic_ray_verdict_only_a_named_failure_is_a_kill[result5-timeout-None]` (`tests/test_mutate_check.py:113-117,133-135`) |
| M3, line 126: `outcome != "killed"` → `outcome == "killed"` | **Killed**, 2 failed / 20 passed | `tests/test_mutate_check.py::test_cli_cosmic_ray_mode_exits_1_on_an_overstated_kill` (`tests/test_mutate_check.py:181-194`) |

Scope limit: the reviewed tests feed source-shaped dump rows, rather than a retained phase-1 session database. That is the R-19 evidence boundary, not a re-derivation of 2267 (`docs/notes/rulings.md:279-290`; `docs/proof/phase1.md:114,129,196`).
