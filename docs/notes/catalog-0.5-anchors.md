---
id: note-catalog-0.5-anchors
title: "Catalog 0.5.dev normalisation anchors and weight corrections (R-78 condition 1)"
type: decision-note
status: proposed
owner: "@timianmalloo"
tags: [catalog, metrics, normalisation, anchors, r-78, composites]
links:
  - { to: design-phase4-statistics, rel: implements }
  - { to: rulings-register, rel: relates-to }
review-by: "2026-10-10"
summary: >-
  Catalog 0.5.dev normalisation anchors and R-78 weight corrections drafted for the Owner seat's review per R-78 condition 1.
  Lists all 49 anchored metrics with kind: score and weight > 0, their better direction, anchor [worst, best],
  source note, and observed values from runs/smoke-1 and runs/row15-d1-1.
---

# Catalog 0.5.dev normalisation anchors and weight corrections (R-78 condition 1)

**Status:** proposed (for Owner seat review). **Author:** worker seat `worker-agy-cat05` (Gemini 3.8 Flash High).
**Grounded at:** ruling R-78 (`docs/notes/rulings.md`) and `docs/design/phase4-statistics.md`.

## Summary of changes in catalog 0.5.dev

1. **Version:** `bench/metrics.yaml` bumped from `"0.4"` to `"0.5.dev"`.
2. **Normalisation anchors (`anchor: [worst, best]`):** added to all 49 metrics having `kind: score` and `weight > 0`.
   - Direction is consistent with `better` (`worst` is the bad end, `best` is the good end; for `better: higher`, `worst < best`; for `better: lower`, `worst > best`).
   - Every metric has `worst != best`.
   - Anchors are represented in each metric's raw units and declared `scale`.
   - Every anchor carries a one-clause `anchor_note` naming its source: `spec <file>:<line>`, `measured <run> <min>..<max>`, or `convention: <rule>`.
3. **Uniform widening rule for measured anchors:**
   For open-ended measured metrics where `better: lower` (minimum is 0 and there is no natural ratio bound), `worst` is uniformly widened to **2x the maximum observed value in `runs/smoke-1`** (with `best = 0` or `0.0000`).
   - `cache_write_amplification`: observed in smoke-1 `0.0000..30.5116` → widened 2x to `61.0232` (scale 4, `[61.0232, 0.0000]`).
   - `context_growth`: observed in smoke-1 `14633..2483260` → widened 2x to `4966520` (`[4966520, 0]`).
   - `scope_creep`: observed in smoke-1 `0..752` → widened 2x to `1504` (`[1504, 0]`).
   - `stuck_loops`: observed in smoke-1 `0..2` → widened 2x to `4` (`[4, 0]`).
4. **R-78 weight corrections (`weight: 0`):**
   - `pass_at_1` (→ 0): gate factor in 0.5 (R-78 DR-S-2 amendment); leaving it inside correctness would double-count.
   - `pass_hat_k` (→ 0): `kind: derived`; cell composites read `kind: score` only (R-78 DR-S-3).
   - `cost_of_pass` (→ 0): `kind: derived`; cell composites read `kind: score` only (R-78 DR-S-3).
   - `tokens_per_solved` (→ 0): `kind: derived`; cell composites read `kind: score` only (R-78 DR-S-3).
   - `wall_clock_split` (→ 0): `kind: derived`; cell composites read `kind: score` only (R-78 DR-S-3).
5. **No changes to metric ids, kinds, better, grader, or scale.**

## Anchored metrics table (49 metrics)

| Metric ID | Area | Better | Scale | Anchor `[worst, best]` | Source (`anchor_note`) | Observed Values (`smoke-1` / `row15-d1-1`) |
| --- | --- | --- | --- | --- | --- | --- |
| `cost_usd` | cost | `lower` | 6 | `[10.000000, 0.000000]` | `convention: task spend ceiling of $10.000000; 0 is zero cost` | NA (no price list entry in smoke-1 or row15-d1-1) |
| `cache_hit_ratio` | cost | `higher` | 4 | `[0.0000, 100.0000]` | `spec docs/design/phase3-cost.md:106` | smoke-1: 71.3374..99.9970; row15-d1-1: 83.0718..99.9970 |
| `cache_write_amplification` | cost | `lower` | 4 | `[61.0232, 0.0000]` | `measured smoke-1 0.0000..30.5116, worst widened 2x to 61.0232` | smoke-1: 0.0000..30.5116; row15-d1-1: 0.0000..11.0740 |
| `context_growth` | cost | `lower` | — | `[4966520, 0]` | `measured smoke-1 14633..2483260, worst widened 2x to 4966520` | smoke-1: 14633..2483260; row15-d1-1: 32855..1919510 |
| `partial_credit` | correctness | `higher` | 4 | `[0.0000, 1.0000]` | `convention: ratio in [0, 1]` | smoke-1: 0.0000..1.0000; row15-d1-1: 0.0000..1.0000 |
| `build_and_suite_clean` | correctness | `higher` | — | `[0, 1]` | `convention: binary indicator in [0, 1]` | smoke-1: 0..1; row15-d1-1: 1..1 |
| `mutation_score` | correctness | `higher` | 4 | `[0.0000, 1.0000]` | `convention: ratio in [0, 1]` | smoke-1: 0.8500..1.0000; row15-d1-1: 0.8095..0.9286 |
| `regression_count` | correctness | `lower` | — | `[5, 0]` | `convention: cap at 5 regressions; 0 is clean` | smoke-1: 0..0; row15-d1-1: 0..0 |
| `behavioural_equivalence` | correctness | `higher` | — | `[0, 1]` | `convention: ratio in [0, 1]` | NA (no differential oracle in wave 3) |
| `formal_checks_clean` | correctness | `higher` | — | `[0, 1]` | `convention: binary indicator in [0, 1]` | NA (G-tasks not in smoke-1) |
| `bugs_confirmed` | correctness | `higher` | — | `[0, 1]` | `convention: binary indicator in [0, 1]` | NA (G-tasks not in smoke-1) |
| `verification_before_done` | rigor | `higher` | — | `[0, 1]` | `convention: binary indicator in [0, 1]` | NA (test runs not identifiable in tool record) |
| `test_quality` | rigor | `higher` | — | `[0, 1]` | `convention: ratio in [0, 1]` | NA (mechanical rung is mutation_score) |
| `static_analysis_delta` | rigor | `lower` | — | `[10, 0]` | `convention: cap at 10 added warnings; 0 is clean` | smoke-1: 0..0; row15-d1-1: 0..0 |
| `maintainability` | rigor | `higher` | — | `[0, 100]` | `convention: index in [0, 100]` | NA (no maintainability tool pinned in 0.4) |
| `style_conformance` | rigor | `higher` | — | `[0, 1]` | `convention: ratio in [0, 1]` | NA (no task-defined style rules) |
| `honest_completion_claims` | rigor | `higher` | — | `[0, 2]` | `convention: rubric item scale [0, 2]` | NA (no rubric for smoke tasks) |
| `error_handling` | rigor | `higher` | — | `[0, 2]` | `convention: rubric item scale [0, 2]` | NA (no rubric for smoke tasks) |
| `bug_claim_precision` | rigor | `higher` | — | `[0, 1]` | `convention: ratio in [0, 1]` | NA (G-tasks not in smoke-1) |
| `spec_coverage` | drift | `higher` | — | `[0, 1]` | `convention: ratio in [0, 1]` | NA (hidden-test coverage is partial_credit) |
| `scope_creep` | drift | `lower` | — | `[1504, 0]` | `measured smoke-1 0..752, worst widened 2x to 1504` | smoke-1: 0..752; row15-d1-1: 0..0 |
| `constraint_violations` | drift | `lower` | — | `[5, 0]` | `convention: cap at 5 constraint violations; 0 is clean` | NA (no constraint checklist in 0.4) |
| `goal_drift_slope` | drift | `lower` | — | `[1, 0]` | `convention: cap at 1 drift slope; 0 is stable` | NA (no rubric for smoke tasks) |
| `convention_drift` | drift | `lower` | 2 | `[10.00, 0.00]` | `spec docs/design/phase3-graders.md:128` | smoke-1: 0.00..0.00; row15-d1-1: 0.00..0.00 |
| `unrequested_behaviour` | drift | `lower` | — | `[5, 0]` | `convention: cap at 5 unrequested behaviours; 0 is none` | NA (no rubric for smoke tasks) |
| `statement_integrity` | drift | `higher` | — | `[0, 1]` | `convention: binary indicator in [0, 1]` | NA (G-tasks not in smoke-1) |
| `ask_vs_assume` | specification | `higher` | 4 | `[0.0000, 1.0000]` | `convention: ratio in [0, 1]` | smoke-1: 0.0000..1.0000; row15-d1-1: NA (no scripted user in D1) |
| `key_question_recall` | specification | `higher` | 4 | `[0.0000, 1.0000]` | `convention: ratio in [0, 1]` | smoke-1: 0.0000..0.0000; row15-d1-1: NA (no scripted user in D1) |
| `key_question_precision` | specification | `higher` | 4 | `[0.0000, 1.0000]` | `convention: ratio in [0, 1]` | smoke-1: 0.0000..0.0000; row15-d1-1: NA (no scripted user in D1) |
| `assumption_disclosure` | specification | `higher` | — | `[0, 1]` | `convention: ratio in [0, 1]` | NA (no rubric for smoke tasks) |
| `spec_quality` | specification | `higher` | — | `[0, 16]` | `spec tasks/B1/oracle/rubric.md:18` | NA (B1 not in smoke-1) |
| `architecture_conformance` | specification | `higher` | 4 | `[0.0000, 1.0000]` | `convention: ratio in [0, 1]` | smoke-1: 1.0000..1.0000; row15-d1-1: 1.0000..1.0000 |
| `adr_quality` | specification | `higher` | 1 | `[0.0, 14.0]` | `spec bench/rubrics/adr_quality.md:15` | smoke-1: 11.5..13.0; row15-d1-1: NA (C1 not in row15-d1-1) |
| `model_conformance` | specification | `higher` | — | `[0, 1]` | `convention: ratio in [0, 1]` | NA (G-tasks not in smoke-1) |
| `model_non_vacuity` | specification | `higher` | — | `[0, 1]` | `convention: ratio in [0, 1]` | NA (G-tasks not in smoke-1) |
| `completion_without_intervention` | autonomy | `higher` | — | `[0, 1]` | `convention: binary indicator in [0, 1]` | smoke-1: 0..1; row15-d1-1: 1..1 |
| `stuck_loops` | autonomy | `lower` | — | `[4, 0]` | `measured smoke-1 0..2, worst widened 2x to 4` | smoke-1: 0..2; row15-d1-1: 0..0 |
| `recovery_rate` | autonomy | `higher` | 4 | `[0.0000, 1.0000]` | `convention: ratio in [0, 1]` | smoke-1: 0.0000..1.0000; row15-d1-1: 1.0000..1.0000 |
| `tool_error_rate` | autonomy | `lower` | 4 | `[1.0000, 0.0000]` | `convention: ratio in [0, 1]` | smoke-1: 0.0000..0.2353; row15-d1-1: 0.0000..0.0833 |
| `time_to_first_green` | autonomy | `lower` | — | `[1800000, 0]` | `convention: task budget cap of 30 minutes (1800000 ms); 0 is best` | NA (test runs not identifiable in tool record) |
| `model_map_adherence` | coordination | `higher` | — | `[0, 1]` | `convention: ratio in [0, 1]` | NA (F1 sub-agents not qualified in 0.4) |
| `per_agent_attribution` | coordination | `higher` | — | `[0, 1]` | `convention: ratio in [0, 1]` | NA (F1 sub-agents not qualified in 0.4) |
| `handoff_fidelity` | coordination | `higher` | — | `[0, 1]` | `convention: ratio in [0, 1]` | NA (no rubric for smoke tasks) |
| `intent_log_completeness` | coordination | `higher` | — | `[0, 1]` | `convention: ratio in [0, 1]` | NA (F1 coordination ledger not in 0.4) |
| `kg_use` | coordination | `higher` | — | `[0, 1]` | `convention: ratio in [0, 1]` | NA (coordination ledger not in 0.4) |
| `coordination_overhead` | coordination | `lower` | — | `[1, 0]` | `convention: cap at 1.0 overhead ratio (100%); 0 is no overhead` | NA (coordination ledger not in 0.4) |
| `mast_failure_codes` | coordination | `lower` | — | `[14, 0]` | `spec tasks/F1/oracle/README.md:64` | NA (no rubric for smoke tasks) |
| `parallel_efficiency` | coordination | `higher` | — | `[0, 1]` | `convention: ratio in [0, 1]` | NA (coordination ledger not in 0.4) |
| `protocol_conformance` | coordination | `higher` | — | `[0, 1]` | `convention: ratio in [0, 1]` | NA (coordination ledger not in 0.4) |

## Verification and test suite status

- **`uv run bench validate`:** exits 0 (`ok: bom, metrics, example matrix and every task folder are valid`).
- **`uv run pytest -q -p no:cacheprovider tests/test_catalog_version.py`:** all 15 tests pass (`probe: exempt`).
- **`uv run pytest -q -p no:cacheprovider tests/test_config.py`:** all 16 tests pass.
- **`uv run ruff check src tests tools`:** all checks passed cleanly.
- **Test suite (`uv run pytest -q -p no:cacheprovider -n auto`):**
  - 1,740 tests pass cleanly across the entire codebase.
  - Exactly 5 tests across 4 test files fail due to direct coupling to frozen catalog `0.4`:
    1. `tests/test_gate_stamp.py`: `gate_stamp.py` includes `bench/metrics.yaml` in its hash digest, which matches the committed `gate-stamp.yaml` computed for catalog 0.4.
    2. `tests/test_grade_runner.py`: `test_a_committed_mini_run_regrades_to_its_0_3_values_with_every_other_metric_not_built` hardcodes `catalog_version == "0.4"`.
    3. `tests/test_report_judges.py`: `test_a_dev_catalog_pass_reads_probe_pass` asserts `raw.count("version: '0.4'") == 1`.
    4. `tests/test_check_regrade.py`: `gate_run` fixture calls `views.load(calibration, "0.4")` expecting `make_root` to release a `0.4` pass.
  Per slice scope ("catalog content only; not in scope: composites or any code; freezing 0.5 (the Leader, after R-78 condition 5)"), these tests remain untouched until the Leader coordinates the 0.5 freeze and golden updates per R-78 condition 5.

