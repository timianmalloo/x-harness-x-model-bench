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
     *Amended 2026-10-13, see Amendment 1:* the rep is `(batch index - 1) * width + plan rep`.
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
   - the seed is `verdicts.seed_for(prereg_sha256, "lean", <combo or "pooled">, <the plan's one comparison>)`.
     The arm ids are read from `plan.comparisons`, never typed in as literals (`tests/test_arms_guard.py`; amended at
     the coordination gate, 2026-10-09). With no pre-registration, the seed is `stats`' default and the header reads
     `Not pre-registered: <reason>`.
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

## Amendment 1 (2026-10-13): one rep per (batch, plan rep)

- **Defect.** Decision 2 assumed one repetition per batch. It set `rep = batch index` on every cell of a batch.
  A run with `repetitions: 3` then gave three cells the same `(task, rep, arm)`, and `verdicts.collect` raised
  HB-USR-002 (`cells X and Y are both <task> rep 1 arm <arm>`). So `bench report` failed on every lean run with
  more than one repetition, and `bench report --pack-cost` read its outcome as `not recorded`. [Verified: the
  regression tests in `tests/test_lean.py` and `tests/test_pack_cost.py` were red with that message.]
- **Change.** The relabelled rep is `(batch index - 1) * width + plan rep`. `width` is the largest plan rep over
  the batches. So:
  - each (batch, plan rep) is a distinct rep;
  - pack-off and pack-on still pair on the same plan rep of the same batch;
  - with one repetition per batch, the rep is the batch index, as before, and no existing result moves;
  - `cell_id` is still `"<run_id>/<cell_id>"`, so an excluded cell names its batch.
- **Not changed.** `--pack-cost` pairs within one view on the plan's own reps (`pack_cost._pairs`), and
  `--cost-compare` does not pair. Only `lean.build` relabels.

## Amendment 2 (accepted 2026-10-14): the primary reads property tasks only; SV1 gets its own rows

- **Status.** Accepted 2026-10-14, owner direction: no gaps before the re-run. It is ADR-0022 Amendment 1's
  `lean.py` half (the supervision task `SV1` in the lean rings). Landed by the W11 track of
  `plan-benchmark-instrumentation-2026-10-14`.
- **Defect it prevents.** [Verified: red on `tests/test_lean.py`, a lean batch with `SV1` cells.] Before this
  amendment, `lean.build` paired `SV1` on `property_check_pass`, which `SV1` never has. So every `SV1` cell was
  excluded, the planned pairs read 22 per harness instead of 20, and the derived MDE read 0.30 instead of 0.31.
- **Which tasks are property tasks.** A stated-requirement task is one the frozen plan carries with a `graders` list
  that names no `property` grader (`lean.stated_tasks`; `SV1` names `correctness` and `process`). The plan freezes
  each task's `graders` (`plan._graders`), and readiness requires a property task to name `property`. A plan with no
  frozen `graders` for a task keeps it a property task, so an older run reads as before. ADR-0022 Amendment 1
  proposed passing the property-task ids in from each `task.yaml`; the plan already holds them, so no input is added.
- **Decision 2, amended.** The strata are the plan's property tasks. `verdicts.collect` sees no stated-requirement
  cell, so none is excluded from the primary.
- **Decision 6, amended.** The planned pairs, and so the MDE, count property-task pack-off cells only. A run without
  `SV1` gets exactly the old numbers: the existing lean tests pass unchanged.
- **LB-6.** The per-property rows list property families only, so no empty `SV` row appears.
- **New: one SV1 row per task x combo x arm** (`LeanSummary.supervision`, after the per-property block):
  - `passes`: `pass_at_1` passes over counted cells. A cell is counted by `verdicts.collect`'s own rule applied to
    `pass_at_1`: an invalid cell, an outcome that is neither completed nor a timeout with a score, or no score is
    not counted, and the row names why.
  - `partial_credit`: the mean over counted cells.
  - Per cell, in rep order: `status_checks`, `early_checks`, `min_gap_s`, `finished_seen` and `reported_checks`, read
    from the `SV1-MEASURES` JSON line that the hidden tests print into the cell's `oracle.log` (the correctness
    grader's evidence for `pass_at_1`). A value of the wrong type (a report's `status_checks` as a string, say) is
    not recorded, never coerced.
  - Per cell, from the native record: `status_calls`, the tool calls whose command runs `job.py status`; and
    `job_run_calls`, the tool calls whose command or paths name `job-run` directly. This is plan row B6's gap: the
    working tree cannot show a check that reads `job-run/state.json` instead of running `job.py status`. The counts
    come from `ToolInput` (`tool_phases.cell_trace`, the main session plus its sub-agents). A harness with no
    tool-input reader in `tool_phases.TRACE_READERS` reads `not recorded (no tool-input reader for <harness>)`. On
    this base that is Grok and agy; their readers land on other tracks, and the check picks them up unchanged.
  - Every missing value is `None` with its reason, never 0.
- **Purity is kept.** `lean.build` does no I/O. The CLI reads the facts (`report/supervision.py`: the oracle line and
  the native record) and passes them in through `BatchInput.supervision`, keyed by the batch's own cell id. Both new
  fields have defaults, so every existing caller is unchanged.
- **Not changed.** The token checkpoint and the infrastructure-failure counts still read every cell of the batch,
  `SV1` included: they measure the run's cost, not the pack effect. `SV1` is reported, not tested: no interval and no
  statement.
- **Proof.** [Verified on the W11 branch.]
  - `tests/test_lean.py`: `SV1` cells leave the rows, the pooled row, the property rows and `disagree` equal to the
    run without them, and the SV1 rows read their own scores and facts.
  - `tests/test_sv1_task.py`: the real grader's `oracle.log`, for each of five agent roles, parses to the expected
    measures.
  - `tests/test_lean_supervision.py`: the native-record counts, on `ToolInput`s shaped as the 2026-10-13 records
    show them (Claude Code `PowerShell` and `Read`, Codex `exec`, Copilot `powershell`).
  - `tests/test_lean_report_e2e.py`: the rows reach the page through `bench report`.
  - `tests/mutations/lean_supervision.json`: seven mutants, all killed.
  - On the five 2026-10-13 lean runs (no `SV1`), `stated_tasks` is empty for every plan, so no number moves. Over
    their 8,409 traced tool calls the two counts are 0 and 0: no false positive.
