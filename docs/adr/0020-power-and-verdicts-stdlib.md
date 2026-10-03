---
id: "adr-0020-power-and-verdicts-stdlib"
title: "ADR-0020: Power analysis, verdicts, dominance and ring gates are pure stdlib functions checked against reference cases"
type: adr
status: draft
owner: "@timianmalloo"
phase: "Enterprise evaluation E1 onward"
tags: [benchmark, statistics, power-analysis, verdict, ring, derived-view]
links:
  - { to: arch-evaluation-campaign, rel: refines }
  - { to: spec-enterprise-evaluation, rel: implements }
  - { to: adr-0006-results-data-model, rel: depends-on }
review-by: "2027-10-03"
summary: >-
  The power analysis (two-proportion and Connor paired-binary sizes, MDE solved back), the per-property verdict
  rule with task-stratified bootstrap intervals, the token-ratio dominance rule and the per-tag ring gates are
  pure Python-stdlib functions of recorded inputs and a seed. No statistics dependency is added:
  statistics.NormalDist reproduces the spec's reference sizes (93, 53, 115) in this session. Outputs are derived
  views; tests check closed-form references, an independent hand-coded formula, a seeded-wrong variant and
  seeded coverage simulations.
---

# ADR-0020: Power analysis, verdicts, dominance and ring gates are pure stdlib functions

- **Status:** Proposed
- **Date:** 2026-10-03
- **Deciders:** @timianmalloo; authored by Claude Code with the Tech Lead and Test Architect lenses
- **Context spec/architecture:** `docs/specs/enterprise-evaluation.md` (EV-12, EV-14, EV-15, EV-18, EV-19); ADR-0006 (*Derived, never stored*); `stats.py` (seeded streams).

## Context

EV-12 needs sample sizes that match closed-form references within ±1 and MDEs within 0.005, checked against an independent implementation. EV-18 needs a task-stratified paired bootstrap with a verdict rule applied in a fixed order, EV-19 a ratio interval and a dominance rule. The repo already has `stats.py` with `rng(seed, key)` streams and a task-paired bootstrap in the pack section. The solution-selection ladder asks for stdlib before a dependency.

**Spike (run 2026-10-03, Python 3.14.6, `uv run --no-sync`).** `statistics.NormalDist().inv_cdf`: z₀.₉₇₅ = 1.9599639845400536, z₀.₈₀ = 0.8416212335729144. Unpaired 0.50 → 0.70: 92.9988 → **93**. Connor ψ = 0.28, δ = 0.20: 52.5207 → **53**; with α = 0.05/45: 114.2488 → **115**. All three spec references reproduced [Verified].

## Decision

1. **Power (`power` module, T0).** Inputs (ADR-0016 `power/<input_hash>.json`) → outputs per property: α, power, MDE, pairing unit, correction, required pairs per (harness, comparison), implied repetitions per task (⌈n/2⌉ for two tasks), cells, hours (from the named source runs' measured mean wall per cell) and tokens. A missing control rate uses 0.5 labelled `assumed` (EV-12). Same inputs → identical outputs; no randomness.
2. **Verdicts (`verdicts` view, T0).** Per (property, harness, comparison): effect on the primary metric, paired by (task, harness, repetition), with a bootstrap stratified by task (repetitions resampled within each task, the two tasks weighted equally), the pre-registered level and correction, streams from `stats.rng(plan seed, key)`. The rule, in order: not enough recorded pairs → `inconclusive (not recorded)`; lower > 0 → `better`; upper < 0 → `worse`; interval strictly inside (−MDE, +MDE) → `no difference ≥ MDE`; else `inconclusive (underpowered)`. Per-task effects shown beside; "on both tasks" only when both agree. Exclusions (calibration, invalid, lost cells) listed with id and reason.
3. **Dominance (EV-19).** Token ratio Σ tokens over the same pairs with a bootstrap interval (log scale); `A dominates B` iff A vs B is `better` or `no difference ≥ MDE` **and** the ratio's upper bound < 1. No other rule emits the word.
4. **Ring gates (EV-14, EV-15).** One pure function per tag over a ring run's view: `pilot` returns the named failing items (blocked/failed/infrastructure cells, grader errors, EV-11 metrics, NOT_RECORDED primaries, BND-A losses, tasks without a primary); `pack-regression` returns per property `regression signal` or `no regression detected at <MDE>`, never verdict words (EVX-6).
5. **Derived, never stored.** Every output above is recomputed on read (ADR-0006); the campaign stores only inputs and decisions.
6. **Controls.** Closed-form reference cases (93; 53; 115) with tolerances; the same values from an independent hand-coded formula with literal z constants inside the test (not the module); a seeded-wrong variant (one-sided z) that must fail; the 400-pair normal-approximation reference (±0.01); seeded coverage simulations (1,000 datasets, 93-97 %) for the verdict interval and the ratio; hand-computed verdict and dominance tables with the boundary rows (EV-18, EV-19).

## Alternatives considered

- **`statsmodels` / `scipy`:** rejected as a runtime dependency; stdlib reproduces every reference, and a heavy dependency enters the engine identity (ADR-0017) for one function. A test-only use was also rejected: the hand-coded independent formula meets EV-12's "independent implementation" without one.
- **Cluster bootstrap over tasks:** rejected by the spec (two tasks give three distinct resamples).
- **McNemar test p-values as the verdict:** rejected; the verdict needs an interval to compare with the MDE.

## Consequences

- **Positive:** no new dependency; outputs reproducible from inputs and seed; every number has a reference test.
- **Negative / accepted trade-offs:** coverage simulations cost test time (bounded by 1,000 datasets; placed in the slow ring per CE rules).
- **Follow-ups / new risks:** the population definition for the power inputs must be named (R-E5); pilot rates are weak estimates (R-E7: use the interval).

## Evidence

- Scratch spike output above [Verified, this session]; `stats.py:36-51` (`rng`, seed bounds) [Verified]; spec power-analysis inputs and formulas.
