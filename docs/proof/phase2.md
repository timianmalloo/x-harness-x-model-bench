---
id: proof-phase2
title: "Proof Pack - phase 2 (wave-by-wave joins)"
type: doc
status: draft
owner: "@timianmalloo"
phase: "Phase 2 · smoke on all harnesses"
tags: [proof, phase2, red-first, joins]
links:
  - { to: coordination-finish-harness-bench, rel: relates-to }
  - { to: proof-phase1, rel: relates-to }
review-by: "2026-10-08"
summary: >-
  The evidence for each phase-2 join: what was claimed, the red observed by a non-author, the mutation result, the
  reviewer's verdict, and the residuals. One Claim table per join.
---

# Proof Pack: phase 2

Each join follows the plan's join rule. A non-author re-runs every cited red in a throwaway worktree and sees it fail for the stated reason; `git show --stat` confirms the red touches no `src/`; and a cross-vendor reviewer adds mutants of their own. The suite command is `uv run pytest -q -p no:cacheprovider`, which is offline since SUITE-A. The lint command is `uv run ruff check src tests tools`.

## Join: SUITE-A control (unplanned; the Leader's own defect), 2026-09-24

| claim | evidence | red observed | reviewer |
| --- | --- | --- | --- |
| A bare `pytest` selects no `credentials` test; the documented `-m ""` opt-in still selects them | `tests/test_default_suite_is_offline.py`; `pyproject.toml` `addopts`; `-m credentials` collects 5 items (3 in `tests/e2e`, 2 real handshakes in `test_profiles.py`) | `5013299`: 1 failed, 1 passed (the bare run selected e2e items), by the Leader | none (Leader emergency control); flagged for the wave-1 join review |

**Residual:** before this control, W1-ACP's suite run, the Leader's first W1-HOST join run and the reviewer's runs each started real cells on the Anthropic and OpenAI logins. See `docs/lessons/defect-classes.md` SUITE-A.

## Join: W1-HOST (row 28), Grok `grok-4.7`, 2026-09-24

**Slice 1** (`w1-s1`, joined in `2b5743b`). The worker's transport failed with `output_limit_exceeded` at 906 s, after its last commit (RUN-A). The hand-back below was reconstructed by the Leader from the commits (R-10).

| claim | red → green | red observed (Leader, throwaway worktree) |
| --- | --- | --- |
| A failed job assignment whose wait times out still closes the job and raises `SpawnError` (residual 6a) | `76bb0ae` → `e8ec45c` | `tests/test_procs.py::test_a_timed_out_wait_after_a_failed_assignment_still_closes_the_job`: 1 failed, 13 passed |
| A failed `GlobalMemoryStatusEx` / `QueryUnbiasedInterruptTime` is not a zero reading (residual 6b) | `de2bdc5` → `3c0f962` | `tests/test_host.py`: 2 failed |
| `cmd_report` scans credentials before it prints the table (residual 5) | `0c254d2` → `95d705f` | `tests/test_cli.py::test_report_does_not_print_a_label_before_the_credential_scan`: 1 failed, 20 passed |
| The `base` fixture leaves 0 folders (residual 11, partly) | `a7cc351` (no natural red) | the Test Architect reverted the CLN-A teardown in a throwaway tree: "1 folder(s) left behind" |

**Slice 2** (`w1-host-s2`, joined in `7d73ada`). This is the loop-back for the review's Major: a raised host reading was not contained by the engine. The attempt reached `ready_for_review` in 490 s with 3,260,061 output bytes and 317 notifications, the first measurement for R-11.

| claim | red → green | red observed (Leader) |
| --- | --- | --- |
| A failed memory query is not recorded (`None`), and the outcome row is still written with `host_mem_available: null` | `ed2fa1d` → `dce41ce` | `tests/test_host.py` and `tests/test_engine.py::test_a_failed_memory_query_still_records_the_outcome_with_null`: 2 failed, 108 passed |
| A failed unbiased clock is not recorded, and `SleepDetector.slept()` stays `False` | `c48492c` → `dc15b2c` | `tests/test_host.py`: 2 failed, 1 passed |

**Mutation (cross-vendor reviewer, Claude Test Architect).**

| mutant | result | killing test |
| --- | --- | --- |
| M1 `proc.kill()` → `pass` in `except TimeoutExpired` (`procs.py:235`) | survived (near-equivalent) | none (Minor, open) |
| M2 memory-status check inverted | killed | `test_host.py::test_a_failed_global_memory_status_ex_is_not_a_zero_reading`, plus 48 engine tests |
| M3 table never printed on success | killed | `test_cli.py::test_grade_then_report_writes_the_page` |

**Suite on `main` after both joins:** 617 passed, 5 deselected; ruff clean.

**Open (Minor, advisory):**
- M1 survives.
- `test_no_leftovers.py` compares a snapshot of the shared `bench-test` folder, so a concurrent suite can fail it. One flake was seen on `main` while another suite ran.
- Residual 11 is only partly proven.
- The class sweep for residual 5 is not done: `bench status`, `bench run` and `bench plan` print plan-derived labels with no scan. This goes to the Security lens.

## Join: W1-TOOLB (row 26), Claude Sonnet 5 (R-10, moved from Agy), 2026-09-24

| claim | red → green | red observed | reviewer |
| --- | --- | --- | --- |
| `mutate_check.py --cosmic-ray` counts a kill only when a named test failed; a collection error, a timeout and an exit-2-shaped interruption are each not a kill; the dump format comes from cosmic-ray 8.7.0's own source | `e53a7bc` → `0e5ddb3` | Leader: 14 failed, 8 passed (tests only) | Codex `gpt-6-sol`, CLEAR (`docs/notes/review-w1-toolb-codex.md`): its own mutants M1 (`is not None` inverted), M2 (the timeout sentinel) and M3 (the overstated condition) were each killed by a named test |

**R-19:** the phase-1 figure of 2267 mutation kills is **not re-derivable (Flagged): the phase-1 cosmic-ray session databases were not kept.** The re-run is a named later window, and no mutation-bar claim is made in phase-2 artifacts until then.
