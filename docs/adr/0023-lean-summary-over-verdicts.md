---
id: "adr-0023-lean-summary-over-verdicts"
title: "ADR-0023: The lean summary pairs with verdicts.collect and intervals with stats.paired_delta, plus a two-stage paired_ratio"
type: adr
status: draft
owner: "@timianmalloo"
phase: "Lean benchmark (operator 2026-10-09)"
tags: [benchmark, lean-benchmark, statistics, derived-view, report, token-ratio]
links:
  - { to: arch-lean-benchmark, rel: refines }
  - { to: spec-lean-pack-benchmark, rel: implements }
  - { to: adr-0020-power-and-verdicts-stdlib, rel: depends-on }
  - { to: adr-0006-results-data-model, rel: depends-on }
review-by: "2027-04-09"
summary: >-
  A new pure module, harness_bench/lean.py, builds the lean summary from one or two batch RunViews. It pairs and
  excludes with the existing verdicts.collect, and takes the effect interval from stats.paired_delta, the
  two-stage bootstrap (task, then repetition) the spec names. The token ratio uses one new sibling,
  stats.paired_ratio, with paired_delta's exact draw scheme. verdicts.verdict was rejected at the gate: its
  stratified interval has zero width at one pair per task. The pack-effect measures list is not changed, so no
  existing report golden moves.
---

# ADR-0023: The lean summary pairs with `verdicts.collect`, and takes its intervals from `stats.paired_delta` and a two-stage `paired_ratio`

- **Status:** Proposed (revised at the gate, 2026-10-09: the Test Architect's veto, findings 1 and 2)
- **Date:** 2026-10-09
- **Deciders:** @timianmalloo; authored by Claude Code (Leader seat, Opus) with the Tech Lead and Simplifier lenses.
  The adversary council was an Opus sub-agent.
- **Context:** `docs/specs/lean-pack-benchmark.md` LB-2 to LB-8, Parts B and C; strategy §3 (b) to (d); ADR-0020;
  `docs/architecture-lean-benchmark.md`.

## Context

The strategy expected the smallest change to be adding `property_check_pass` to the pack effect's measures
(`board.py:588`, `:825`). Read at `307ec787`:

- **Golden churn.** `_pack_effect_pair` builds rows for `["pass_at_1", *cat.areas]` on **every** run with two
  arms. Adding a measure adds rows to every two-arm report, and LBU-5 forbids that. [Verified]
- **`stats.paired_delta` is the right interval.** It is a two-stage percentile bootstrap: shared tasks are drawn
  first, then each arm's repetitions within the task (`stats.py:157-208`). The spec names it (LB-4). [Verified]
- **`verdicts.collect` is the right pairing.** It pairs by (task, rep, arm) and lists every excluded cell with
  its cause, including `pair partner not recorded`. That is the spec's exclusion rule (LB-2), and LB-4's "excluded
  cells with causes" (`verdicts.py:162-198`). [Verified]
- **`verdicts.verdict` is the wrong interval here.** Its bootstrap holds tasks fixed as strata and resamples
  only within each one (`verdicts.py:218-232`). With one pair per task (one batch), the interval has zero width.
  Gate probe, re-run by the author: 10 tasks, 4 of them improved, 1 repetition each. `verdict` gives effect
  [0.4, 0.4] and token ratio [2, 2]; `paired_delta` gives [0.1, 0.7]. [Verified]
- **No two-stage ratio exists.** The board has a mean token `Measure` per combo with no interval
  (`board.py:298-310`). `verdicts._ratio` has the stratified defect above. `pack_improvement` renders a
  **median** per-pair token ratio with no interval (`report/pack_improvement.py:147-180`). [Verified]

## Decision

1. **A new pure module, `src/harness_bench/lean.py` (T0, stdlib, no I/O).** Its seam contract is in the
   architecture's *Contracts*. Its inputs are:
   - the batch views;
   - the numeric run and grading durations (passed in by the CLI; decision 7);
   - the pre-registration status.
2. **Pairing and exclusion: `verdicts.collect`, once per harness.**
   - Each batch's cells are relabelled first, with `rep = batch index` and `cell_id = "<run_id>/<cell_id>"`, so an
     excluded cell names its batch (`dataclasses.replace`; `CellView` is a plain dataclass, `views.py:146`).
   - Strata are the lean ring's ten tasks.
   - `VerdictSpec`'s label-only fields (`mde`, `level_rule`, `min_pairs`) are filled but not used.
   - `verdicts.verdict` is **not called**.
3. **Effect: `stats.paired_delta`.** The collected pairs become `stats.Obs(task, rep, value)` for each arm, with
   `key = "lean|<combo>"`. Pooled: every harness's pairs, with `task = "<combo>/<task>"` (30 tasks) and
   `key = "lean|pooled"`.
4. **Token ratio: a new `stats.paired_ratio(ref, treat, labels, params, key)`.**
   - It sits beside `paired_delta` and uses the **same** streams and draw order: one shared-task draw, then A's
     repetitions, then B's.
   - The statistic is Σ treat tokens / Σ ref tokens over the drawn cells. The point is the ratio of totals.
   - It is fed only the token-complete pairs. A pair whose tokens are not recorded, or whose pack-off tokens are 0,
     is excluded from the ratio and counted (LB-7; a missing value never becomes 0).
   - `paired_delta` and its goldens are untouched.
5. **Statement:** `no detectable effect` exactly when `stats.no_detectable_effect(interval)` is true (the only
   definition). Otherwise `pack-on higher by <effect>` or `pack-on lower by <|effect|>`. With 0 pairs:
   `not recorded (0 pairs)`. No verdict word or `dominates` appears anywhere in the section.
6. **MDEs are derived, never typed in:** `power.mde_for(n, lambda d: power.n_paired_exact(0.28, d, 0.05, 0.8))`,
   quantized to 2 dp. Per harness that is 20 → 0.31 or 10 → 0.42; pooled, 60 → 0.19 or 30 → 0.26. A test pins all
   four.
7. **Checkpoint numbers (LB-3, the limits note), each from one definition:**
   - **run minutes per cell:** a numeric helper extracted from `report/html.py`'s `_run_wall_clock` (for example
     `views.run_wall_ns(run_dir)`). `_run_wall_clock` formats its result, keeping its output byte-identical;
   - **grading minutes per cell:** (`grading.completed` − `grading.started`) `mono_ns` over `cells_graded` for the
     current pass. Both events come from one runner process, and `ledger.stamp` puts `mono_ns` on every row
     (`grade/runner.py:263-299`, `ledger.py:69-73`);
   - **tokens per cell, per combo and arm:** `views.sum_tokens`;
   - **infrastructure failures per combo:** `(k, n, causes)` from `CellView.outcome` and `cause`. A combo over 20%
     is named (LB-3).
8. **Pre-registration:**
   - the CLI resolves `--prereg PATH` to the file's sha256 and its commit time (`git log -1 --format=%cI`; None if
     uncommitted);
   - `lean.build` compares that time with batch 1's first cell start, read from the view;
   - the seed is `verdicts.seed_for(prereg_sha256, "lean", <combo or "pooled">, ("off", "on"))`. With no
     pre-registration, the seed is `stats`' default and the header reads `Not pre-registered: <reason>`.
9. **Rendering: a new `report/lean_section.py` at the campaign section's slot** (after validity, before the
   leaderboard; `report/html.py:2259-2266`), on a lean-shaped run (ADR-0022 §4). The header carries:
   - the question and the pre-registration status;
   - `Batches: n of 2`;
   - both run ids and plan hashes;
   - on a pooled report, the scope line `Sections below cover batch <run_id> only`.

   The ratio's label is **"token ratio of totals (pack-on / pack-off)"**, with one line saying how it differs from
   the pack-improvement section's median per-pair ratio. The CLI table is unchanged (YAGNI).

## Consequences

- `stats` gains one function. `verdicts`, `power`, `board`'s pack effect and catalog 0.7 are unchanged, and every
  existing golden holds.
- The spec's own engine and pair are used, so LB-4's text stands without an erratum. The architecture's choice of
  ring tag for the lean shape still needs one (ADR-0022).
- `paired_delta` resamples each arm's repetitions independently within a task. So the pairing is held at the task
  level in the bootstrap, while exclusion is at the pair level. This is the spec's method as written (glossary,
  *Paired difference*). It is conservative, not degenerate.
- Two token-ratio figures appear on a lean page: the lean ratio of totals, with an interval, and the
  pack-improvement median, a point per task. Both are labelled, and the lean one is the decision figure.

## Alternatives considered

- **`verdicts.verdict` for the effect and ratio** (this ADR's first draft). Rejected at the gate: the zero-width
  interval at one pair per task (probe above), which contradicts LB-4, LB-7 and LBU-4.
- **Add `property_check_pass` to the pack-effect measures.** Rejected: it moves every two-arm golden (LBU-5) and
  leaves LB-7 unbuilt.
- **A 1-batch ratio rendered as "interval not computed"** (a spec erratum). Rejected. `paired_ratio` is about 25
  lines on an existing draw scheme, and the spec asks for the interval.
