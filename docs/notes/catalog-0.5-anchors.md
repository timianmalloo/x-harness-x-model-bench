---
id: note-catalog-0.5-anchors
title: "Catalog 0.5.dev normalisation anchors and weight corrections (R-78 condition 1, R-79)"
type: decision-note
status: accepted
owner: "@timianmalloo"
tags: [catalog, metrics, normalisation, anchors, r-78, r-79, composites]
links:
  - { to: design-phase4-statistics, rel: implements }
  - { to: rulings-register, rel: relates-to }
review-by: "2026-10-10"
summary: >-
  Catalog 0.5.dev normalisation anchors and R-78 weight corrections, approved with changes by the Owner
  seat in R-79. Lists all 49 anchored metrics with kind: score and weight > 0, their better direction,
  anchor [worst, best], source note, and observed values from runs/smoke-1 and runs/row15-d1-1.
---

# Catalog 0.5.dev normalisation anchors and weight corrections (R-78 condition 1, R-79)

**Status:** accepted (R-79: APPROVE WITH CHANGES). **Original draft author:** worker seat `worker-agy-cat05`
(Gemini 3.8 Flash High). **R-79 changes applied by:** worker seat `worker-sonnet-cat05b` (Claude Sonnet 5).
**Grounded at:** ruling R-78 (`docs/notes/rulings.md`), ruling R-79 (`docs/notes/rulings.md`), and
`docs/design/phase4-statistics.md`.

R-79 approved the draft below with these changes: the saturation formula and the three `anchor_note` forms
are now stated in `bench/metrics.yaml`'s own field docs (item 1); `cache_write_amplification`,
`time_to_first_green`, `regression_count` and the seven rubric-less judged-metric anchors are replaced with
the values R-79 item 2 states; and the `context_growth`, `scope_creep`, `stuck_loops`, `cost_usd`,
`static_analysis_delta`, `constraint_violations`, `coordination_overhead` and `convention_drift` notes are
reworded per R-79 item 3 (anchors kept, except `convention_drift`'s note which corrects the cited line from
`:128` to `:426`). The table below is the applied, R-79-conformant state.

## Summary of changes in catalog 0.5.dev

1. **Version:** `bench/metrics.yaml` bumped from `"0.4"` to `"0.5.dev"`.
2. **Normalisation anchors (`anchor: [worst, best]`):** added to all 49 metrics having `kind: score` and `weight > 0`.
   - Direction is consistent with `better` (`worst` is the bad end, `best` is the good end; for `better: higher`, `worst < best`; for `better: lower`, `worst > best`).
   - Every metric has `worst != best`.
   - Anchors are represented in each metric's raw units and declared `scale`.
   - Every anchor carries a one-clause `anchor_note` naming its source: `spec <file>:<line>`, `measured <run> <min>..<max>`, or `convention: <rule>`.
3. **Uniform widening rule for measured anchors, reworded per R-79 item 3** (anchors unchanged; the note now
   states the rule directly and names the re-anchor trigger): "measured, worst = 2x the smoke-1 max,
   re-anchor at 0.6 if any cell saturates."
   - `context_growth`: observed in smoke-1 `14633..2483260` → `worst = 4966520` (`[4966520, 0]`).
   - `scope_creep`: observed in smoke-1 `0..752` → `worst = 1504` (`[1504, 0]`).
   - `stuck_loops`: observed in smoke-1 `0..2` → `worst = 4` (`[4, 0]`).
   - `cache_write_amplification` is **not** in this group after R-79: it is replaced by a spec anchor
     (`[100.0000, 0.0000]`, `docs/design/phase3-cost.md:116`), not a measured/widened one.
4. **R-79 item 2 replacements** (anchor values, not just notes, changed from the original draft):
   - `cache_write_amplification` → `[100.0000, 0.0000]`, spec `docs/design/phase3-cost.md:116`.
   - `time_to_first_green` → `[3600000, 0]`, spec `docs/specs/harness-bench.md:266` (the 60-minute task ceiling).
   - `regression_count` → `[1, 0]`, convention: one regression is a correctness failure (design `phase3-graders.md:331`).
   - Seven judged metrics without a rubric — `honest_completion_claims`, `error_handling`,
     `assumption_disclosure`, `handoff_fidelity` → `[0, 2]`; `goal_drift_slope`, `unrequested_behaviour`,
     `mast_failure_codes` → `[2, 0]` — each noted "judged sum of n items at 0..2 (judge.py:22,
     adr_quality.md:5), n=1 provisional until the rubric lands; re-anchor to 2n at 0.6".
5. **R-79 item 3 notes reworded, anchors kept:**
   - `cost_usd`: "$10 is provisional until the first priced run" (was an unqualified spend ceiling).
   - `static_analysis_delta`: "no spec ceiling; a negative delta clamps to 100" (kept the cap-at-10 fact).
   - `constraint_violations`: "provisional until the first checklist exists" (kept the cap-at-5 fact).
   - `coordination_overhead`: "undefined in code today" (kept the cap-at-1.0 fact).
   - `convention_drift`: line citation corrected from `phase3-graders.md:128` (wrong; History rules section)
     to `:426` (the metric's own unit definition, Verified).
6. **R-78 weight corrections (`weight: 0`), unchanged by R-79:**
   - `pass_at_1` (→ 0): gate factor in 0.5 (R-78 DR-S-2 amendment); leaving it inside correctness would double-count.
   - `pass_hat_k` (→ 0): `kind: derived`; cell composites read `kind: score` only (R-78 DR-S-3).
   - `cost_of_pass` (→ 0): `kind: derived`; cell composites read `kind: score` only (R-78 DR-S-3).
   - `tokens_per_solved` (→ 0): `kind: derived`; cell composites read `kind: score` only (R-78 DR-S-3).
   - `wall_clock_split` (→ 0): `kind: derived`; cell composites read `kind: score` only (R-78 DR-S-3).
7. **No changes to metric ids, kinds, better, grader, or scale.**

## Anchored metrics table (49 metrics)

| Metric ID | Area | Better | Scale | Anchor `[worst, best]` | Source (`anchor_note`) | Observed Values (`smoke-1` / `row15-d1-1`) |
| --- | --- | --- | --- | --- | --- | --- |
| `cost_usd` | cost | `lower` | 6 | `[10.000000, 0.000000]` | `convention: $10 is provisional until the first priced run; 0 is zero cost` | NA (no price list entry in smoke-1 or row15-d1-1) |
| `cache_hit_ratio` | cost | `higher` | 4 | `[0.0000, 100.0000]` | `spec docs/design/phase3-cost.md:106` | smoke-1: 71.3374..99.9970; row15-d1-1: 83.0718..99.9970 |
| `cache_write_amplification` | cost | `lower` | 4 | `[100.0000, 0.0000]` | `spec docs/design/phase3-cost.md:116` | smoke-1: 0.0000..30.5116; row15-d1-1: 0.0000..11.0740 |
| `context_growth` | cost | `lower` | — | `[4966520, 0]` | `measured smoke-1 14633..2483260, worst = 2x the smoke-1 max, re-anchor at 0.6 if any cell saturates` | smoke-1: 14633..2483260; row15-d1-1: 32855..1919510 |
| `partial_credit` | correctness | `higher` | 4 | `[0.0000, 1.0000]` | `convention: ratio in [0, 1]` | smoke-1: 0.0000..1.0000; row15-d1-1: 0.0000..1.0000 |
| `build_and_suite_clean` | correctness | `higher` | — | `[0, 1]` | `convention: binary indicator in [0, 1]` | smoke-1: 0..1; row15-d1-1: 1..1 |
| `mutation_score` | correctness | `higher` | 4 | `[0.0000, 1.0000]` | `convention: ratio in [0, 1]` | smoke-1: 0.8500..1.0000; row15-d1-1: 0.8095..0.9286 |
| `regression_count` | correctness | `lower` | — | `[1, 0]` | `convention: one regression is a correctness failure (design phase3-graders.md:331)` | smoke-1: 0..0; row15-d1-1: 0..0 |
| `behavioural_equivalence` | correctness | `higher` | — | `[0, 1]` | `convention: ratio in [0, 1]` | NA (no differential oracle in wave 3) |
| `formal_checks_clean` | correctness | `higher` | — | `[0, 1]` | `convention: binary indicator in [0, 1]` | NA (G-tasks not in smoke-1) |
| `bugs_confirmed` | correctness | `higher` | — | `[0, 1]` | `convention: binary indicator in [0, 1]` | NA (G-tasks not in smoke-1) |
| `verification_before_done` | rigor | `higher` | — | `[0, 1]` | `convention: binary indicator in [0, 1]` | NA (test runs not identifiable in tool record) |
| `test_quality` | rigor | `higher` | — | `[0, 1]` | `convention: ratio in [0, 1]` | NA (mechanical rung is mutation_score) |
| `static_analysis_delta` | rigor | `lower` | — | `[10, 0]` | `convention: cap at 10 added warnings; no spec ceiling; a negative delta clamps to 100` | smoke-1: 0..0; row15-d1-1: 0..0 |
| `maintainability` | rigor | `higher` | — | `[0, 100]` | `convention: index in [0, 100]` | NA (no maintainability tool pinned in 0.4) |
| `style_conformance` | rigor | `higher` | — | `[0, 1]` | `convention: ratio in [0, 1]` | NA (no task-defined style rules) |
| `honest_completion_claims` | rigor | `higher` | — | `[0, 2]` | `judged sum of n items at 0..2 (judge.py:22, adr_quality.md:5), n=1 provisional until the rubric lands; re-anchor to 2n at 0.6` | NA (no rubric for smoke tasks) |
| `error_handling` | rigor | `higher` | — | `[0, 2]` | `judged sum of n items at 0..2 (judge.py:22, adr_quality.md:5), n=1 provisional until the rubric lands; re-anchor to 2n at 0.6` | NA (no rubric for smoke tasks) |
| `bug_claim_precision` | rigor | `higher` | — | `[0, 1]` | `convention: ratio in [0, 1]` | NA (G-tasks not in smoke-1) |
| `spec_coverage` | drift | `higher` | — | `[0, 1]` | `convention: ratio in [0, 1]` | NA (hidden-test coverage is partial_credit) |
| `scope_creep` | drift | `lower` | — | `[1504, 0]` | `measured smoke-1 0..752, worst = 2x the smoke-1 max, re-anchor at 0.6 if any cell saturates` | smoke-1: 0..752; row15-d1-1: 0..0 |
| `constraint_violations` | drift | `lower` | — | `[5, 0]` | `convention: cap at 5 constraint violations; provisional until the first checklist exists; 0 is clean` | NA (no constraint checklist in 0.4) |
| `goal_drift_slope` | drift | `lower` | — | `[2, 0]` | `judged sum of n items at 0..2 (judge.py:22, adr_quality.md:5), n=1 provisional until the rubric lands; re-anchor to 2n at 0.6` | NA (no rubric for smoke tasks) |
| `convention_drift` | drift | `lower` | 2 | `[10.00, 0.00]` | `spec docs/design/phase3-graders.md:426` | smoke-1: 0.00..0.00; row15-d1-1: 0.00..0.00 |
| `unrequested_behaviour` | drift | `lower` | — | `[2, 0]` | `judged sum of n items at 0..2 (judge.py:22, adr_quality.md:5), n=1 provisional until the rubric lands; re-anchor to 2n at 0.6` | NA (no rubric for smoke tasks) |
| `statement_integrity` | drift | `higher` | — | `[0, 1]` | `convention: binary indicator in [0, 1]` | NA (G-tasks not in smoke-1) |
| `ask_vs_assume` | specification | `higher` | 4 | `[0.0000, 1.0000]` | `convention: ratio in [0, 1]` | smoke-1: 0.0000..1.0000; row15-d1-1: NA (no scripted user in D1) |
| `key_question_recall` | specification | `higher` | 4 | `[0.0000, 1.0000]` | `convention: ratio in [0, 1]` | smoke-1: 0.0000..0.0000; row15-d1-1: NA (no scripted user in D1) |
| `key_question_precision` | specification | `higher` | 4 | `[0.0000, 1.0000]` | `convention: ratio in [0, 1]` | smoke-1: 0.0000..0.0000; row15-d1-1: NA (no scripted user in D1) |
| `assumption_disclosure` | specification | `higher` | — | `[0, 2]` | `judged sum of n items at 0..2 (judge.py:22, adr_quality.md:5), n=1 provisional until the rubric lands; re-anchor to 2n at 0.6` | NA (no rubric for smoke tasks) |
| `spec_quality` | specification | `higher` | — | `[0, 16]` | `spec tasks/B1/oracle/rubric.md:18` | NA (B1 not in smoke-1) |
| `architecture_conformance` | specification | `higher` | 4 | `[0.0000, 1.0000]` | `convention: ratio in [0, 1]` | smoke-1: 1.0000..1.0000; row15-d1-1: 1.0000..1.0000 |
| `adr_quality` | specification | `higher` | 1 | `[0.0, 14.0]` | `spec bench/rubrics/adr_quality.md:15` | smoke-1: 11.5..13.0; row15-d1-1: NA (C1 not in row15-d1-1) |
| `model_conformance` | specification | `higher` | — | `[0, 1]` | `convention: ratio in [0, 1]` | NA (G-tasks not in smoke-1) |
| `model_non_vacuity` | specification | `higher` | — | `[0, 1]` | `convention: ratio in [0, 1]` | NA (G-tasks not in smoke-1) |
| `completion_without_intervention` | autonomy | `higher` | — | `[0, 1]` | `convention: binary indicator in [0, 1]` | smoke-1: 0..1; row15-d1-1: 1..1 |
| `stuck_loops` | autonomy | `lower` | — | `[4, 0]` | `measured smoke-1 0..2, worst = 2x the smoke-1 max, re-anchor at 0.6 if any cell saturates` | smoke-1: 0..2; row15-d1-1: 0..0 |
| `recovery_rate` | autonomy | `higher` | 4 | `[0.0000, 1.0000]` | `convention: ratio in [0, 1]` | smoke-1: 0.0000..1.0000; row15-d1-1: 1.0000..1.0000 |
| `tool_error_rate` | autonomy | `lower` | 4 | `[1.0000, 0.0000]` | `convention: ratio in [0, 1]` | smoke-1: 0.0000..0.2353; row15-d1-1: 0.0000..0.0833 |
| `time_to_first_green` | autonomy | `lower` | — | `[3600000, 0]` | `spec docs/specs/harness-bench.md:266 (the 60-minute task ceiling)` | NA (test runs not identifiable in tool record) |
| `model_map_adherence` | coordination | `higher` | — | `[0, 1]` | `convention: ratio in [0, 1]` | NA (F1 sub-agents not qualified in 0.4) |
| `per_agent_attribution` | coordination | `higher` | — | `[0, 1]` | `convention: ratio in [0, 1]` | NA (F1 sub-agents not qualified in 0.4) |
| `handoff_fidelity` | coordination | `higher` | — | `[0, 2]` | `judged sum of n items at 0..2 (judge.py:22, adr_quality.md:5), n=1 provisional until the rubric lands; re-anchor to 2n at 0.6` | NA (no rubric for smoke tasks) |
| `intent_log_completeness` | coordination | `higher` | — | `[0, 1]` | `convention: ratio in [0, 1]` | NA (F1 coordination ledger not in 0.4) |
| `kg_use` | coordination | `higher` | — | `[0, 1]` | `convention: ratio in [0, 1]` | NA (coordination ledger not in 0.4) |
| `coordination_overhead` | coordination | `lower` | — | `[1, 0]` | `convention: cap at 1.0 overhead ratio (100%); undefined in code today; 0 is no overhead` | NA (coordination ledger not in 0.4) |
| `mast_failure_codes` | coordination | `lower` | — | `[2, 0]` | `judged sum of n items at 0..2 (judge.py:22, adr_quality.md:5), n=1 provisional until the rubric lands; re-anchor to 2n at 0.6` | NA (no rubric for smoke tasks) |
| `parallel_efficiency` | coordination | `higher` | — | `[0, 1]` | `convention: ratio in [0, 1]` | NA (coordination ledger not in 0.4) |
| `protocol_conformance` | coordination | `higher` | — | `[0, 1]` | `convention: ratio in [0, 1]` | NA (coordination ledger not in 0.4) |

## Verification and test suite status (final, post-R-79)

- **`uv run bench validate`:** exits 0 (`ok: bom, metrics, example matrix and every task folder are valid`).
- **`uv run ruff check src tests tools`:** clean.
- **Test suite (`uv run pytest -q -p no:cacheprovider -n auto`):** every test passes except exactly one --
  `tests/test_gate_stamp.py::test_current_grader_inputs_match_gate_stamp` -- which is **expected** to fail on
  this branch. `bench/metrics.yaml` is a gate-stamp input, so the stamp is stale until the Leader renews it
  with a real `pytest -m gate` run (R-79 condition 2: "the stale gate stamp is renewed by the Leader ... before
  the merge"). Neither the stamp file nor that test is edited here.
- The four tests that previously hard-coded catalog `"0.4"` now read the catalog's own loaded version (or
  `make_root`'s release label) instead, so they remain correct under `0.5.dev` without weakening what they
  proved:
  1. `tests/test_grade_runner.py::test_a_committed_mini_run_regrades_to_its_0_3_values_with_every_other_metric_not_built`
  2. `tests/test_report_judges.py::test_a_dev_catalog_pass_reads_probe_pass`
  3. `tests/test_check_regrade.py` (`gate_run` fixture)
  4. `tests/test_gate_stamp.py` itself is excluded from this fix -- it is *meant* to fail until the Leader's
     stamp renewal (above), per R-79 condition 2 and this branch's own scope.
  Per slice scope ("catalog content only; not in scope: composites or any code; freezing 0.5 (the Leader,
  after R-78 condition 5)"), no other code or the gate stamp is touched.

