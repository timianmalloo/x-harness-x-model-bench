---
id: "adr-0019-catalog-0-7-property-metrics"
title: "ADR-0019: Catalog 0.7 adds the property metrics, scenario-7 pass@1 and per-metric expected values; a missing pass@1 is never a fail"
type: adr
status: draft
owner: "@timianmalloo"
phase: "Enterprise evaluation E1 (0.7.dev), E3 (0.7 frozen)"
tags: [benchmark, catalog, metrics, grading, us-4]
links:
  - { to: arch-evaluation-campaign, rel: refines }
  - { to: spec-enterprise-evaluation, rel: implements }
  - { to: design-pack-improvement-section, rel: relates-to }
review-by: "2027-10-03"
summary: >-
  Catalog 0.7 is a new version under the R-59/R-86 rules: it adds property_check_pass and the EV-2..EV-6
  secondaries, a pass_at_1 for scenario-7 (formal) tasks, and expected-value declarations per metric in each
  property task's task.yaml. The pack section's rule that counts a missing pass_at_1 as a fail is a defect and is
  fixed: missing is NOT_RECORDED and excluded. The US-4 control is the catalog-freeze golden for every 0.6 metric.
---

# ADR-0019: Catalog 0.7: property metrics, scenario-7 pass@1, expected values

- **Status:** Proposed
- **Amended (2026-10-03, W1-G design `design-eval-catalog-0-7` section 14 U5; W0 rev 3):** see "Amendment 1" before *Alternatives considered*. The decision text above is unchanged.
- **Date:** 2026-10-03
- **Deciders:** @timianmalloo; authored by Claude Code with the Data & Persistence and Test Architect lenses
- **Context spec/architecture:** `docs/specs/enterprise-evaluation.md` (EV-1, EV-7, EV-10, EV-11, EV-14 "the grid-4 G2 shape"); R-59 (content-addressed catalog), R-86 (version rules); `bench/catalog-freeze.yaml`.

## Context

[Verified, read 2026-10-03] `bench/metrics.yaml` is version `0.6`; `pass_at_1` is a correctness-grader score (`metrics.yaml:45`) that scenario-7 (formal) tasks never record. `report/pack_improvement._passed` returns `s is not None and s.value == 1`, so a formal cell with no `pass_at_1` counts as a **fail** in the pack section, and G2 cannot be ranked. `bench/catalog-freeze.yaml` holds per-version `catalog_hash`, view `golden` and `board_golden` hashes: the existing US-4 control. EV-7 requires each property task to declare the expected value of every metric its graders name, so a SCAN-A-shaped false zero fails readiness.

## Decision

1. **Version.** The changes below are catalog `0.7` (`0.7.dev` during E1-E2; frozen with goldens before any campaign baseline, EV-16). Each new metric has `kind`, `better`, `scale` where non-integer, an `anchor` and an `anchor_note` in a permitted form (R-79).
2. **Property metrics.** `property_check_pass` (score, binary, source D, grader `property`) and the secondaries `exploit_probes_blocked`, `fault_suite_pass`, `idempotency_violations`, `rework_ratio`, `turn1_tests_pass`, `hallucinated_symbol_errors`, `verified_before_use`, `size_vs_reference`, `new_abstractions`, `new_dependencies`. Weight 0 in composites in 0.7 (they decide verdicts, not the leaderboard); the operator may weight them in a later version.
3. **Scenario-7 `pass_at_1`.** The formal grader records `pass_at_1` = 1 when its task's declared pass rule holds (the rule is per task in `task.yaml`, defined at design-slice from the existing formal metrics). This adds rows where none existed; no 0.6 value moves. **What it does not do (council D4):** because the rule lives in `task.yaml`, it is inside the task version hash, so adding it makes a **new** G2 task version. Grid-3 and grid-4's G2 cells ran under the old version; re-grading them does not give them a `pass_at_1`, and they stay un-rankable. Only a new run under the new task version records it (re-scoring old grids is also out of scope, EN9).
4. **Missing is not a fail (defect fix).** `_passed` and every pass count treat a missing or NOT_RECORDED `pass_at_1` as *not recorded*: excluded from pass and fail counts and listed under EV-11's "not recorded in this run". This is a view change: it can move the 0.6 `board_golden` for runs with scenario-7 cells, so the change is recorded in the freeze file **append-only** (council P2): the old hash is never overwritten; the version's entry gains the new value with `corrected_from: {hash: <old>, defect_class: <id>, commit: <sha>}` beside it, and the golden check accepts the newest value while `bench verify` can show the chain. It also carries its defect class (a new class in `docs/lessons/defect-classes.md`, "absence read as failure", with the sweep over every `scores.get(...)` comparison).
5. **Expected values.** A property task's `task.yaml` declares `expected: {reference: {<metric>: <value>}, naive: {<metric>: <value>}}` with a provenance comment per value (GLD-A), inside the task version hash. Readiness (EV-7) compares by exact equality at the catalog scale; `expected NA: <reason>` is the only exemption (EV-11).
6. **US-4 control.** A test grades the frozen grid-3 and grid-4 fixture archives under 0.7 and asserts every 0.6 metric's value unchanged and the new metrics absent for tasks whose graders do not name them (EV-10).

### Amendment 1 (2026-10-03; W1-G design `docs/design/eval-catalog-0-7.md` F4, F7, F9, section 14 U5; W0 rev 3 section 7)

Recorded by the Coordinator (`coord-opus-e1e4`) with W0 rev 3. W1-G's gate is open (RV-TA BLOCK); this note records facts W1-G verified, not its open findings.
- **Item 6 and EV-10, the fixtures.** There is no committed grid-3 or grid-4 archive: `runs/` is git-ignored. The US-4 control runs over the committed fixtures `tests/fixtures/ledger/c44dd2b-no-heads` and `tests/fixtures/ledger/heads` (W1-G F4).
- **Item 4, "can move the 0.6 `board_golden`".** For the committed fixtures it cannot: `board.export` does not import `pack_improvement`, and neither fixture holds a scenario-7 cell (W1-G F7). The append-only `corrected_from` record therefore stays a written contingency. It is built only if X-G3's before/after run shows a moved golden hash; the existing freeze check fails on a moved hash, so the trigger is a red gate, not a memory (Coordinator ruling, W0 rev 3 section 7, on RV-SIM W1-G 2).
- **Item 4, "`bench verify` can show the chain".** `bench verify` verifies a run's ledger and does not read `bench/catalog-freeze.yaml` (W1-G F9). The chain, if one is ever recorded, is shown by the US-4 control's printed lines.
- **Item 5, the expected set.** The required set is the property grader's narrowed set, `runner.applicable(catalog, graders, prop)["property"]` (W0 section 2, R-90 condition 1).
- **Item 3, how the formal grader records `pass_at_1`.** Provisional on the Owner decision request `req-01M41E37FGK5CRZ7NCK3RA20JV`: an optional catalog key `also_graded_by: [formal]` on `pass_at_1`, and a metric's owner for a task is the first of `[grader, *also_graded_by]` that the task names.

## Alternatives considered

- **Put property metrics in a separate catalog:** rejected; two catalogs would need two version rules and two freeze files (DM7).
- **Treat missing `pass_at_1` as 0 and add formal pass@1 only:** rejected; it keeps the defect for every other missing case (a grader crash would still read as a fail).
- **Expected values in the discrimination record instead of `task.yaml`:** rejected; they would be derived from a grader run, which is not provenance (GLD-A).

## Consequences

- **Positive:** G2 becomes rankable in new runs (not in grids 3-4); the pack section stops penalising absence; readiness catches recorded-but-wrong metrics.
- **Negative / accepted trade-offs:** one view golden may move under item 4, recorded as a correction; ten new metrics in the catalog.
- **Follow-ups / new risks:** the per-task formal pass rule; the defect class and its sweep.

## Evidence

- `bench/metrics.yaml:11, 45-51`; `bench/catalog-freeze.yaml`; `report/pack_improvement.py:1173-1175` [Verified, read 2026-10-03].
