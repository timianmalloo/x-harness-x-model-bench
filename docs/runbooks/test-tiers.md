---
id: runbook-test-tiers
title: "Runbook: the test tiers and the stamped tier"
type: doc
status: draft
owner: "@timianmalloo"
tags: [runbook, testing, ci, gate-stamp, stamped]
links:
  - { to: note-20260927-ci-opt-proposal, rel: depends-on }
review-by: "2026-12-31"
summary: >-
  Which tests run when: per join, per batch, when the stamped inputs moved, and once a day. The `stamped` marker,
  its own stamp, the exact commands, and the control that keeps a stamped test honest.
---

# Runbook: the test tiers and the stamped tier

The slow tests that depend only on the grader and verdict inputs run **when those inputs changed**, plus once a
day. Everything else runs every time. Cheaper is never weaker: any input change runs them.

## The tiers

| Tier | When | Command |
|---|---|---|
| Per join | every join | `docs/coordination/join.json` `recount`: `uv run pytest -q -p no:cacheprovider -n 4 --deselect tests/test_gate_stamp.py::test_current_grader_inputs_match_gate_stamp` |
| Batch ring | before a push | `HB_REQUIRE_DOTNET=1 uv run pytest -q -n 4 -m "not credentials and not gate and not stamped"`, plus the stamped tier below when it is due |
| Stamped | `python tools/gate_stamp.py --check-stamped` exits 1 | `python tools/gate_stamp.py --renew-stamped` runs `pytest -m stamped` with `HB_REQUIRE_DOTNET=1`, refuses on a skip, and writes `tests/fixtures/gate/stamped-stamp.yaml` |
| Daily | once per 24 h, whatever the digest says | the same `--check-stamped` returns 1 when the stamp is older than 24 h |
| Gate ring | `gate_stamp --print` differs from `gate-stamp.yaml` | `HB_GATE_RUNS=<runs> HB_REQUIRE_DOTNET=1 uv run pytest -m gate`, then `python tools/gate_stamp.py --renew` (77-81 min) |

`pyproject.toml` `addopts` is the one definition of the default selection: it excludes `credentials`, `slow`, `gate` and
`browser` (`tests/test_join_contract.py` forbids a copy of it in `join.json`; `test_catalog_version.py` pins it). Every
`stamped` test is also `slow`, so the per-join recount already leaves them out: it needs only `-n 4`, no `-m`. A
command-line `-m` replaces `addopts`, so `-m stamped` runs only the stamped tier, and the old batch ring
`-m "not credentials and not gate"` ran them on every batch; `and not stamped` is the saving.

## What is stamped

`@pytest.mark.stamped` is on the real-dotnet D1 grader tests (`test_correctness_dotnet`, `test_grade_correctness`,
`test_grade_mutation`, `test_grade_rigor`) and the verdicts coverage tests (`test_coverage_golden`, `test_coverage_band`).
All are also `slow`. Measured 2026-10-06: 21 tests, 543 s at `-n 4` (23 `slow` tests in that run, 2 of them `mutate_check`).

The stamped digest is the **gate digest plus** `errors.py`, `power.py`, `stats.py` and `verdicts.py` from
`src/harness_bench/` (`STAMPED_EXTRA_INPUTS` in `tools/gate_stamp.py`). It has its own stamp file, so an edit to
`verdicts.py` does not trigger the 77-minute gate ring. The gate digest itself is unchanged.

## The Leader's rule

At each batch gate run `python tools/gate_stamp.py --check-stamped`. Exit 1 names why (inputs moved, no stamp, daily run
due): run `python tools/gate_stamp.py --renew-stamped` and commit the new stamp with the batch. Exit 0: skip `-m stamped`.

## The control

`tests/test_gate_stamp.py::test_every_module_a_stamped_test_file_imports_is_a_stamped_input_or_named_glue` fails when a
file holding a `stamped` test imports a `harness_bench` module that is neither a stamped input, nor under `grade/`, nor in
`STAMPED_GLUE` (each with a reason). Decide every new import: move it into `STAMPED_EXTRA_INPUTS`, or name it as glue.

Residual risk (Inferred): glue modules (`archive`, `config`, `plan`, `procs`, `profiles`, `host`, `gitsafe`, `views`) can
change without moving the stamp. Their own fast tests run every join, and the daily run covers the rest.
