---
id: "design-phase4-statistics"
title: "Design: statistics — composites, bootstrap intervals, ranking with ties, pack effect and run comparison (phase 4, wave 4 row 19)"
type: design
status: draft
owner: "@timianmalloo"
phase: "Phase 4 · statistics and full report (wave 4: row 19)"
tags: [benchmark, statistics, bootstrap, ranking, pack-effect, composites, normalisation, determinism]
links:
  - { to: spec-harness-bench, rel: implements }
  - { to: arch-harness-bench, rel: implements }
  - { to: adr-0006-results-data-model, rel: depends-on }
  - { to: design-phase3-graders, rel: depends-on }
  - { to: design-phase3-cost, rel: relates-to }
  - { to: design-phase3-gateway-judges, rel: relates-to }
  - { to: rulings-register, rel: depends-on }
  - { to: coordination-finish-harness-bench, rel: relates-to }
  - { to: proposal-cross-harness-benchmarking, rel: refines }
review-by: "2027-03-27"
summary: >-
  Row 19 (S-08f composites + S-11 statistics): normalisation by catalog anchors and the correctness-gated
  composite at the cell grain; a two-stage (tasks, then repetitions) percentile bootstrap, 95%, at least 2,000
  resamples, keyed per quantity from a recorded seed so the same results and seed give identical intervals;
  ranking where overlapping intervals share a tier and a pass@1 interval entirely below another can never rank
  above it (US-36, C1); the pack effect on minus off per area and combo with E1-E3 excluded and `no detectable
  effect` when the interval touches zero (US-37); the two-run comparison with its refusal rule (US-52). Everything
  is derived at read time; nothing new is stored. Six decision requests (DR-S-1..6) carry recommended defaults.
---

# Design: statistics (phase 4, wave 4 row 19)

**Status:** draft. **Author:** worker seat `w4-stats-design` (Claude Opus 5.5). **Grounded at:** `3d06948` (the
worktree's base, `main`). **Workflow:** `/design-slice`. **Brief:** compiled prompt `al-01M3JJ40PZ4PAPDTMXCWSMNGJR`.

Confidence labels: **Verified** (observed in this session: a file opened, a command run, a measurement taken),
**Inferred** (reasoned or recalled, not observed), **Decision** (this design's own call, inside the authority that
`docs/design/phase3-graders.md` gives row 19: "statistics and composites (row 19)", `:61`, and obligation R-19,
`:924`). A question this design cannot settle alone is a decision request **DR-S-n** (section "Decision requests")
with a recommended default. No DR is silently resolved in the text: where the text depends on one, it says so.

## Responsibility

One responsibility: **turn the current grading pass of a run (or of two runs) into the derived statistics the
report shows** — normalised scores, area and correctness-gated composites, pass@k and pass^k, 95% bootstrap
intervals, ranks with ties, the pack effect and the run comparison — deterministically, from stored inputs only.

In scope:
- normalisation and composites (S-08f, `docs/specs/README.md:55`; delegated to row 19 by `phase3-graders.md:61`);
- pass@k and pass^k (delegated by `phase3-graders.md:345-349`);
- the bootstrap, the ranking rule, the pack effect, the run comparison (S-11; US-36, US-37, US-52);
- where each result reaches the CLI table, the HTML page and the canonical export, and the text shown when a
  quantity cannot be computed;
- the contracts, error codes, determinism guarantee, test plan and slice plan.

Not in scope (brief): implementation; the full report UI (row 20: whiskers, heatmap, frontier, summaries);
the full grid (wave 5); anything under `runs/`; any push. Also not here: cost-of-pass and tokens per solved task
(row 20 columns, US-39); the US-38 stability warning (tag `full`, row 20; it reads this design's pass^k and pass@1).

## Grounding (the facts this design stands on)

| # | Fact | Evidence | Label |
| --- | --- | --- | --- |
| G1 | `views.leaderboard` ranks rows on the pass@1 **point** estimate (equal values tie) and fills `Row.interval` with a placeholder: `interval not computed (n < 2)` when fewer than 2 valid cells, else `interval not computed (statistics are phase 4)`. | `src/harness_bench/views.py:554-589` | Verified |
| G2 | `views.export` writes the leaderboard, including `rank` and `interval`. The pinned 0.4 golden export `heads.export` holds `"interval": "interval not computed (statistics are phase 4)"` and `"rank": "1"`. | `views.py:612-615`; `tests/fixtures/catalog/0.4/heads.export` (parsed in this session) | Verified |
| G3 | The US-4 control grades the fixtures under the **current** catalog version only, and exempts a `.dev` version (it prints `probe: exempt`). A golden file of an older version is not re-checked once the version moves on. | `tests/test_catalog_version.py:50-75` | Verified |
| G4 | `grade/normalize_scores.py` is a 4-line docstring stub. No code computes a normalised score, an area composite or a gated composite (`grep -rniE "composite|normali[sz]"` over `src/`). | the file; the search | Verified |
| G5 | Catalog `0.4` is frozen (`bench/catalog-freeze.yaml`, hash `286a0daa…`) and declares **no normalisation anchors**. The spec defines normalisation as "fixed anchors per metric in the catalog version. It does not depend on the other cells in the run." | `bench/metrics.yaml`; `docs/specs/harness-bench.md:212` | Verified |
| G6 | Four `kind: derived` metrics carry `weight: 1`: `pass_hat_k`, `cost_of_pass`, `tokens_per_solved`, `wall_clock_split`. `kind: derived` is "computed above the cell or in views; never a score row". | `bench/metrics.yaml:12-14`, areas `cost`, `correctness` | Verified |
| G7 | `config.validate_metrics` checks schema, ids, `source`, `better` and `grader`; it accepts unknown keys, so an `anchor` field would pass unvalidated. | `src/harness_bench/config.py:127-144` | Verified |
| G8 | A plan cell carries `task`, `rep`, `task_version`, `combo`, `pack`, `scenario`. The plan carries `matrix.repetitions`, `matrix.combos` (id, harness, model), `bom_version`, `pack.revision`. `CellView` has no `task`, `rep` or `task_version`. | `runs/smoke-1/plan.json` in the primary checkout (read only); `views.py:108-135` | Verified |
| G9 | `CellView.scores` holds only the current pass's rows (`s["grading_id"] == grading_id`), so one `RunView` is one pass by construction. | `views.py:465`, `:514` | Verified |
| G10 | The judge grader stores a single verdict as NA `second judge not qualified` (R-63 b), so a composite that excludes NA already honours "no composite includes a single verdict". | `src/harness_bench/grade/judge.py:19-23`, `:196` | Verified |
| G11 | Every error code outside `HB-LED`/`HB-SEC` exits with the invalid-input code. `HB-USR-002` is "invalid input". | `src/harness_bench/cli.py:46-47`; `errors.py` RUN_CODES | Verified |
| G12 | `report.disclosure_rows` is the one source of the header rows for both the CLI and the HTML page. | `report/cli_table.py:40`; `report/__init__.py:156` | Verified |
| G13 | One two-stage percentile bootstrap of 24 tasks × 3 reps at B = 2,000 with `Decimal` arithmetic takes **0.024 s** (Python 3.12.10); the same seed and key give the identical interval in two separate processes. | spike, Appendix A | Verified (measured) |
| G14 | Coverage of the 95% two-stage percentile interval for a pass rate, 300 trials each: 0.92–0.99 at 24 tasks; 0.97–0.98 at 6 tasks × 3 reps; **0.74 at 6 tasks × 1 rep when the true pass rate is 0.8** (0.98 at 0.5). | spike, Appendix A | Verified (measured) |
| G15 | `hypothesis` is declared (`pyproject.toml:18`, `>=6.100`) and installed in the primary checkout's `.venv` (6.168.1). | the files; `import hypothesis` | Verified |
| G16 | Python guarantees across versions only that `random.Random.random()` yields the same sequence for the same seed (the "compatible seeder"); `randrange`, `choice` and `choices` may change. | Python `random` docs, "Notes on Reproducibility" (recalled, not opened in this session) | Inferred |
| G17 | Tests pin the placeholder strings: `tests/test_views.py:1316`, `:1383`, `:1400`; `tests/test_report.py:51`. Mutation files `tests/mutations/report.json` and `r35_r36.json` name leaderboard tests (combo flags). | the files | Verified |
| G18 | `runner.grader_build()` hashes `grade/*.py` and is only recorded on `grading.started`; no reader compares it. | `grade/runner.py:86`, `:235`; `grep grader_build src/` | Verified |
| G19 | Obligation R-19 on row 19: "composites take the applicable set per task and reject multi-pass input". | `docs/design/phase3-graders.md:119`, `:924` | Verified |
| G20 | `plan.matrix.repetitions` is 1 in `smoke-1`; the smoke run has 6 tasks (A1, B1, C1, D1, E6, F1) × 3 combos × pack {on, off}. E1–E3 exist only as `status: stub` task folders. | `runs/smoke-1/plan.json`; `tasks/E1..E3/task.yaml` | Verified |

## Data model (settled first)

**Bounded context:** reporting statistics (the read side of the results context; ADR-0006: "Derived, never
stored"). **Ubiquitous language:** *observation*, *measure*, *stratum* (a task), *repetition*, *sample*,
*resample*, *percentile interval*, *seed*, *resample count*, *tier*, *overlap*, *dominance*, *pack effect*,
*comparison*, *`no detectable effect`*, *`not computed`*, *anchor*, *normalised score*, *area composite*,
*overall composite*, *correctness-gated composite*.

**Aggregates.** This design adds **no aggregate and no stored fact.** It reads four existing ones, by identity:

| Aggregate (root) | Read for | Invariant this design relies on |
| --- | --- | --- |
| Run (`run_id`) | combos, BOM version, pack revision, repetitions, each cell's task, rep and task version | the plan is frozen at confirmation |
| Grading pass (`grading_id`) | the score rows, through `views.load` | GradedOncePerPass (`phase3-graders.md`, Data model) |
| Metric catalog version | areas, weights, `better`, anchors | one version label, one content (`catalog_hash`) |
| BOM version | the task versions two runs share | a referenced BOM's task set never changes |

The rules this design owns are **policies over those aggregates**, not aggregate invariants:
- **One pass per input (R-19).** A statistic reads one grading pass per run. Two inputs from the same run are refused (`HB-STA-001`).
- **Same inputs, same bytes.** The same observations, catalog, seed and resample count give byte-identical output.

**Value objects** (frozen dataclasses; section Contracts): `Params(seed, resamples)`, `Obs(task, rep, value)`,
`Interval(point, lo, hi, n, reason)`, `Tiered(row, rank, reason)`, `Anchor(worst, best)`.

**Grain, declared before the columns.** Every row below is computed at read time; none is persisted.

| Quantity | One row is exactly one … | Identified by | Additivity |
| --- | --- | --- | --- |
| Observation | value of one measure for one **valid** cell in the current pass | (run_id, grading_id, cell_id, measure) | follows the measure |
| Normalised score | metric of one cell, mapped to 0–100 by the catalog's anchor | (cell_id, metric_id, catalog_version) | non-additive (an index) |
| Area composite | area of one cell | (cell_id, area_id, catalog_version) | non-additive (a weighted mean) |
| Overall composite | cell | (cell_id, catalog_version) | non-additive |
| Correctness-gated composite | cell | (cell_id, catalog_version) | non-additive |
| pass@1 observation | cell | (cell_id) | additive (0/1 indicator: the sum is a count, the mean a rate) |
| pass@k, pass^k | task version × combo × pack in one run | (run_id, task, combo, pack) | additive indicator per task; the row value is a rate |
| Row estimate | measure × combo × pack in one run's current pass | (run_id, combo, pack, measure) | non-additive (a mean) |
| Row interval | row estimate × params | (run_id, combo, pack, measure, seed, resamples) | non-additive |
| Rank | combo × pack in one run, under one primary measure | (run_id, combo, pack, primary) | ordinal: never summed or averaged |
| Pack effect | combo × measure in one run: on − off | (run_id, combo, measure, seed, resamples) | non-additive (a difference of means) |
| Comparison delta | combo × pack × measure across two runs: B − A | (run_a, run_b, combo, pack, measure, seed, resamples) | non-additive |

Measures (the `measure` key): `pass_at_1`, `gated`, `pass_at_k`, `pass_hat_k`, and each of the seven area ids.

**Across which axes a mean is legal.** Only across cells of **one pass** (G9) and **one catalog version**. No
statistic sums or averages across `grading_id` or `catalog_version` (`phase3-graders.md`, Additivity).

**History rules.** Nothing here has history of its own. The catalog is Type-2 by version (existing). A change to
this design's method (resampling unit, interval type, quantile rule, draw order) changes the published numbers,
so it must change the method string the output records (section Determinism): the method string is the
statistics' version label.

**Derive, don't store (DM7).** Stored inputs: score rows (ledger), the catalog (`bench/metrics.yaml` at a
`catalog_hash`), the plan, and the parameters seed and resample count. Derived and never stored: every row in
the grain table. One definition per quantity, each in one function (section Contracts). The pass@1 row value
and the rank move out of `views.py` into the statistics projection so that no quantity keeps two homes (class
DM-A): `views.leaderboard`, `views.Row` and `views._row` are deleted, not kept beside the new code.

**Where the seed and resample count live (reproducibility).** Per DR-S-5's default: `stats.DEFAULT_SEED` and
`stats.MIN_RESAMPLES` are code constants; `bench report --seed N --resamples B` overrides them; every output
records both — the report header row (`report.disclosure_rows`), the HTML page, and the statistics export
bytes. A reader reproduces any published interval from the run's ledger, the catalog at the recorded
`catalog_version`, and the recorded seed and resample count.

**Writer and compute reader of each input this design adds** (DM15):

| Input | Writer | Compute reader |
| --- | --- | --- |
| `anchor: [worst, best]` per metric in `bench/metrics.yaml` (DR-S-1) | the Leader, in the catalog `0.5.dev` edit | `composites.normalise` |
| seed, resample count | `stats` constants, or the `bench report` flags | `stats.interval`, `stats.paired_delta` |

**Durable representation and migration.** None. ADR-0006 is unchanged, no ledger fact changes, no ADR is needed
(DM13 applies to a durable-representation choice; this design makes none). The catalog edit (anchors) is a new
catalog version under the existing R-59 rule, not a migration.

## Normalisation and composites (S-08f)

**Normalisation** (spec `:212`; depends on DR-S-1 for the anchors). A metric with `kind: score` and `weight > 0`
carries `anchor: [worst, best]` in raw units. For a recorded raw value `x`:

    t = (x − worst) / (best − worst)        # Decimal
    N = 100 × min(1, max(0, t))             # clamped to 0..100

`better: higher` requires `best > worst`; `better: lower` requires `best < worst`; `worst == best` is refused
by `bench validate` (a seam, section Seams). So `N` is monotone in the good direction by construction, and a
value beyond an anchor saturates at 0 or 100. `N` never reads another cell (spec `:212`).

NA rules (US-27; never 0):
- the score is NA → the normalised score is NA with the score's reason;
- the metric has no anchor in the loaded catalog → NA `no normalisation anchor for <metric> in catalog <v>`;
- the pass's `catalog_hash` differs from the loaded catalog's → every normalised score is NA `graded under
  catalog <v> (<hash12>); the loaded catalog is <v2> (<hash12>)`. The fix is a re-grade (US-26: pure, cached).

**Area composite** (spec `:211`, US-27). For one cell and one area: the weighted mean of the normalised scores of
the area's metrics that have `kind: score`, `weight > 0` and a non-NA normalised score, with the weights
renormalised over the included metrics. The excluded metrics are listed with their reasons. If none is
included, the area composite is NA `no <area> metric recorded`. `kind: derived` metrics never enter a cell
composite (their grain is above the cell; DR-S-3).

**Overall composite** (DR-S-2 default). The unweighted mean of the cell's non-NA area composites. NA when all
seven are NA.

**Correctness-gated composite** (DR-S-2 default). Per cell: `gated = pass_at_1 × overall`, on 0–100.
- `pass_at_1 = 0` → `gated = 0`. This is a measured failure, not missing data, and it holds even when `overall` is NA.
- `pass_at_1 = 1` and `overall` NA → NA with `overall`'s reason.
- `pass_at_1` NA → NA with its reason.

So a failing cell never scores above a passing one ("a cheap failure never outranks an expensive pass",
`metrics.yaml:17`). At the row level the gate is enforced by the ranking rule, not by this formula alone.

## pass@k and pass^k

For one (task, combo, pack) in one run: `K = plan.matrix.repetitions` (G8). `R` is the list of that group's
valid cells whose `pass_at_1` is recorded.

| | value 1 when | value 0 when | NA otherwise, with reason |
| --- | --- | --- | --- |
| pass@k | any cell in `R` passed | `len(R) == K` and none passed | `<K − len(R)> of <K> repetitions not recorded` |
| pass^k | `len(R) == K` and all passed | any cell in `R` failed | the same reason |

A recorded failure makes pass^k 0 even with repetitions missing, and a recorded pass makes pass@k 1: a
known outcome is never withheld, and an unknown one is never assumed. With `K = 1`, both equal pass@1. The
row value is the task-balanced mean over tasks with a value, a point with no interval: the report shows pass^k
without one (spec `:933`), so none is computed (Gate record, Simplifier S2).

## The bootstrap (defined precisely)

**Type: percentile interval, not BCa** (Decision; Patterns-vs-Simplifier, Gate record P1). **Level: 95%.
Resampling unit: two-stage — tasks, then repetitions within each drawn task** (spec `:511`, `:1081`: "the unit
of resampling (tasks × repetitions)"). **Statistic: the task-balanced mean.**

Input: a list of observations `Obs(task, rep, value)` for one measure and one row (all from one pass).
1. **Canonical order.** Group by `task`; sort the task ids (string order); within a task, sort by `rep`. So
   `T = [t_1 … t_n]` and `V_t = [v_1 … v_k_t]`. The input's order never matters.
2. **n** is the number of tasks with at least one observation. `n = 0` → `Interval(None, None, None, 0,
   "not computed (no valid cell with a value)")`. `n = 1` → the point is computed, and `lo`, `hi` are None with
   reason `interval not computed (n < 2)` (the spec's copy, `:1032`, with n counted in tasks).
3. **Point estimate** `θ̂ = (1/n) Σ_t mean(V_t)`. The mean of the task means weights every task equally; it
   equals the plain mean over cells when every task has the same number of observations (the planned case).
4. **Stream.** `rng = random.Random(int.from_bytes(sha256(f"{seed}|{key}".encode()).digest()[:8], "big"))`.
   A draw of an index below `m` is `int(rng.random() * m)`. Only `random()` is called (G16).
5. **Resample** `B` times (`B = params.resamples ≥ 2000`): for `i` in `1..n`, draw a task `t = T[draw(n)]`, then
   draw `len(V_t)` values from `V_t` with replacement (`V_t[draw(len(V_t))]` each) and take their mean. The
   resample statistic is the mean of those `n` task means. Draws happen in exactly this order: the draw order
   is part of the contract, and the golden test pins it.
6. **Quantiles, no interpolation.** Sort the `B` statistics ascending. `j = B × 25 // 1000`. `lo = s[j]`,
   `hi = s[B − 1 − j]`. At `B = 2000`: `lo` is the 51st smallest and `hi` the 1950th.
7. **Arithmetic.** `Decimal` inside `decimal.localcontext(Context(prec=28, rounding=ROUND_HALF_EVEN))`, so an
   ambient context set by a caller cannot change a result. No float enters a value (ADR-0006's rule, applied to
   derived values too). Exact values are kept for comparisons; output is quantised at the edge (section
   Determinism).

**NA cells.** A cell enters only when it is `valid` (views' validity, unchanged) and its measure is not NA. An
invalid cell or an NA value is excluded, never 0 (US-27). The row reports the counts it excluded (`n_valid`,
and `<m> of <n_valid> valid cells NA: <first reason>` in the row's footnote, as `views._row` already does for
cost).

**The per-quantity key** names the quantity, not its position: `f"{measure}|{combo}|{pack}"` for a row interval.
Adding or removing another row never changes this row's interval (property test).

**Paired difference** (pack effect, comparison). Inputs: a reference arm `A` and a treatment arm `B`, each a
list of `Obs`, with labels (`off`/`on`, or run ids). `T` is the sorted set of tasks with at least one
observation in **both** arms; `n = len(T)`. Three streams: `rng_T` keyed `key|tasks`, `rng_A` keyed
`key|arm|<label A>`, `rng_B` keyed `key|arm|<label B>`; `key` sorts the two labels, so it does not depend on which
arm is the reference. Each resample draws `n` tasks from `rng_T` (shared, so the pairing holds), then the
repetitions of that task in `A` from `rng_A` and in `B` from `rng_B`, and adds `mean_B − mean_A`. The statistic
is that sum ÷ n. The point is `(1/n) Σ_t (mean(V^B_t) − mean(V^A_t))`. Swapping the arms gives exactly
`(−hi, −lo)` (property test). Tasks present in only one arm are named in the output, not silently dropped.

**`no detectable effect`.** A computed interval with `lo ≤ 0 ≤ hi` (touching zero counts, the conservative side).
The label is attached by one function, `stats.no_detectable_effect`, the only definition (US-37, US-52 and the
US-42 claim check all read it).

**Minimum n.** An interval needs `n ≥ 2` tasks; paired, `n ≥ 2` tasks present in both arms. Below it: the point
where `n = 1`, and the reason `interval not computed (n < 2)`; never a zero-width interval and never 0.

**Known limit (measured, G14).** At 6 tasks × 1 repetition with a high true pass rate, an all-pass sample gives a
zero-width interval `[1.00, 1.00]`, and coverage falls to 0.74. Two rules in this design keep that from
misleading: touching intervals overlap (so a zero-width interval ties with any interval that reaches it), and
touching zero is `no detectable effect`. Recorded as residual risk R1 with an upgrade trigger.

## Ranking with ties (US-36, conflict C1)

**Rule** (spec `:506-508`, C1 `:677`). (i) Two rows whose 95% intervals on the correctness-gated composite
overlap share a rank, shown as `k=`. (ii) A row whose pass@1 interval lies entirely below another row's never
ranks above it.

**Primary measure.** `gated` (the correctness-gated composite). While the loaded catalog has no anchors, DR-S-1's
default makes the primary measure `pass_at_1` for the whole run, never per row, and the header says so.

**Definitions.** Intervals are closed. `overlap(a, b)` iff `a.lo ≤ b.hi and b.lo ≤ a.hi`. `below(a, b)` iff
`a.hi < b.lo`.

**Algorithm** (`stats.rank`):
1. **Ranked set** `S`: rows whose primary interval is computed. Every other row is unranked: rank `""`, reason
   `not ranked: <its interval reason>`.
2. **Tiers from overlap.** Sort `S` by primary `lo` ascending (ties: `hi`, then row id). Sweep: a row whose `lo`
   is at most the running maximum `hi` joins the current tier, else it starts a new one. The tiers are the
   connected components of the overlap graph. They are totally ordered. Order them best first.
3. **The gate.** One pass over every ordered pair `(X, Y)` in `S` (sorted by row id): if
   `below(pass@1(X), pass@1(Y))` and `tier(X)` is **currently** before `tier(Y)`, merge every tier from `tier(X)`
   through `tier(Y)` into one. One pass suffices: a merge only coarsens tiers, so it never creates a new
   violation, and a pair checked earlier stays satisfied (Test Architect note, Gate record round 2). The loop is
   bounded by the number of pairs (the termination variant). A row whose pass@1 interval is not computed takes
   part in no gate check (T-R16).
4. **Rank numbers** (competition ranking). A tier's rank is 1 + the number of rows in the tiers before it. A
   tier with more than one row prints `<rank>=`.
5. **Display order.** By tier, then primary point descending, then combo, then pack. Then the unranked rows by
   combo and pack.

**Why components, not "1 + the number of rows strictly better"** (Decision). The count rule gives A = 1, B = 1,
C = 2 for a chain where A overlaps B, B overlaps C and A is above C. B and C then overlap but hold different
ranks, which breaks (i) as the spec words it. Components satisfy (i) for every pair. They are conservative:
a chain can tie rows whose own intervals are disjoint. With two criteria, the count rule can also rank X above Y
while Y's pass@1 dominates X, because a non-transitive "beats" relation makes counts inconsistent. The tier
merge in step 3 cannot.

**Why the gate merges a contiguous range** (Decision). Suppose X is in tier 1, Z in tier 2 and Y in tier 3, and
Y's pass@1 dominates X's. Merging only X and Y leaves no consistent place for Z: Z is below X on the composite and
above Y. Merging tiers 1–3 is the smallest change that satisfies (i) and (ii) together.

**Edge cases** (each an exact-fixture test, section Test plan):

| # | Case | Result |
| --- | --- | --- |
| K1 | no row has a computed interval | no rank; every row `-` with its reason; the table note says `No row could be ranked.` |
| K2 | one ranked row | `1` |
| K3 | every interval overlaps | every row `1=` |
| K4 | chain: A overlaps B, B overlaps C, A above C | A, B, C all `1=` |
| K5 | touching intervals (`a.hi == b.lo`) | tie |
| K6 | identical zero-width intervals | tie |
| K7 | disjoint on the composite, but the lower row's pass@1 interval is entirely above the upper row's | the two tiers merge: tie |
| K8 | K7 across a middle tier | the three tiers merge |
| K9 | two separate tiers with no gate conflict | `1`, `2` (or `1=`, `1=`, `3`) |
| K10 | a row with n < 2 among ranked rows | that row unranked; the others are ranked without it |
| K11 | input rows shuffled | the same ranks |

## Pack effect (US-37)

For each combo with both pack settings in the run, and for each measure in {the seven areas, `pass_at_1`}
(Decision, Gate record S3): `effect = paired_delta(A = pack off, B = pack on)`. So the effect is `on − off`
with a 95% interval over tasks × repetitions.

- **Contamination exclusion.** Tasks `E1`, `E2`, `E3` are removed from both arms before pairing (spec `:513`;
  proposal `:370`). `stats.CONTAMINATION_PRONE = ("E1", "E2", "E3")`. `simplify:` a constant keyed by task id,
  as the spec names them. Ceiling: the BOM's public calibration tasks are exactly E1–E3. Upgrade trigger: a
  fourth public-calibration task, or any of E1–E3 re-authored as private; then this becomes a `task.yaml` field.
  The section always states the rule: `Excluded as contamination-prone: E1, E3` (those present), or
  `Excluded as contamination-prone: none in this run`.
- **Label.** `no detectable effect` per `stats.no_detectable_effect`; otherwise the signed delta and interval.
  Every area is 0–100 with higher better, so a positive delta means the pack helped on that area.
- **States** (the spec's copy, `:1033`): the run has one pack setting → the section reads `This run has one pack
  setting; no effect to show.`; a combo with one setting → its rows read `Pack effect needs both settings.`;
  n < 2 → `interval not computed (n < 2)`; an area NA in an arm → `not computed (no <area> score in pack=<arm>)`.

## Run comparison (US-52)

`bench report <run_b> --baseline <run_a>` adds a comparison section to run B's report: `delta = paired_delta(A =
run_a, B = run_b)` per (combo, pack, measure), measures as in the pack effect, pairing by task.

**Preconditions.** Each one is checked. **Every** failure is named in one refusal, `HB-STA-002` (invalid-input
exit, G11), and nothing else is printed for the comparison:
1. both runs have a current pass: `run <id> is not graded`;
2. the same combo set, compared by (id, harness, model) from `plan.matrix.combos`: `combos differ: only in A: …;
   only in B: …`;
3. the same `plan.bom_version`: `BOM version differs: A 0.3, B 0.4`;
4. the same catalog version of the current pass: `catalog version differs: A 0.4, B 0.5`;
5. the same `task_version` for every task both runs hold (implied by 3; checked defensively): `task version of
   D1 differs`;
6. different run ids: the same run twice is `HB-STA-001` (R-19: two passes of one run are never one input).

A shared pack revision is allowed: the header says `same pack revision (<n>): a replication`. The spec's Given
names different revisions, but its refusal list does not include the revision. Different BOM subsets are not a
refusal: the pairing uses the shared tasks, and the section names the tasks only one run holds. Whether E1–E3 are
also excluded here is DR-S-6.

## Where each result reaches the report

The report's full UI is row 20. Row 19 delivers the data and the minimal text surfaces below, so that every number
it computes is visible and testable. It adds no chart.

| Surface | Row 19 change | Text when not computable |
| --- | --- | --- |
| Header rows (`report.disclosure_rows`, CLI + HTML, G12) | one row: `statistics: percentile bootstrap, 95%, <B> resamples, seed <s>, resampled by task then repetition, Python <major.minor> random stream; ranked on <correctness-gated composite \| pass@1 (catalog <v> has no normalisation anchors)>` | — |
| CLI leaderboard (`report/cli_table.py`) | columns `Rank`, `Combo`, `Pack`, `Valid`, `pass@1`, `pass@1 95%`, `Gated`, `Gated 95%`, then the existing `Tokens/cell`, `Wall/cell`, `Cost/cell`. The `Interval` column is removed | `-` for an unranked row, and a footnote `<combo> <pack>: not ranked: <reason>`; an interval cell prints its reason, e.g. `interval not computed (n < 2)`; an NA point prints `NA (<reason>)` (`report.na`) |
| CLI pack-effect table (new, after the leaderboard) | one row per combo × measure: delta, `[lo, hi]`, label | the state lines of section Pack effect |
| HTML `#leaderboard` (`report/html.py`) | the same columns; each interval cell carries `data-interval-lo` / `data-interval-hi` (UIA-5) | as the CLI; the attributes are omitted when not computed, never set to 0 |
| HTML `#pack-effect` (new section, a table only) | as the CLI table, with `data-interval-*` | as the CLI |
| HTML `#comparison` (with `--baseline` only) | per combo × pack × measure, B − A | the refusal replaces the section: `Runs not comparable: <each difference>` |
| Canonical statistics export (`board.export`) | all of the above, plus the method string, seed and resample count (not the Python version: bytes must not move with the environment when no number moves) | reasons as strings; bounds `null`, never 0 |
| `views.export` | loses the `leaderboard` key (DR-S-4) | — |

Number format: rates (`pass_at_1`, pass@k, pass^k) with 2 decimals, `[0.33, 0.83]`; composites and area deltas
with 1 decimal, `[41.2, 63.0]`. The export keeps 4 decimals (section Determinism).

## Contracts

**Exposed.** Three new modules, one responsibility each (Patterns: section Patterns). Signatures are the contract;
bodies are implementation.

`src/harness_bench/stats.py` — pure, stdlib plus `harness_bench.errors`; no I/O, no catalog, no views:

```python
METHOD = "percentile bootstrap, 95%, two-stage (task, then repetition), task-balanced mean"
DEFAULT_SEED: int = 20260927          # DR-S-5
MIN_RESAMPLES, MAX_RESAMPLES = 2000, 100_000
CONTAMINATION_PRONE = ("E1", "E2", "E3")

@dataclass(frozen=True)
class Params:
    seed: int = DEFAULT_SEED          # 0 <= seed < 2**63, else BenchError("HB-USR-002")
    resamples: int = MIN_RESAMPLES    # MIN..MAX, else BenchError("HB-USR-002")

@dataclass(frozen=True)
class Obs:
    task: str
    rep: int
    value: Decimal

@dataclass(frozen=True)
class Interval:
    point: Decimal | None
    lo: Decimal | None
    hi: Decimal | None
    n: int                            # tasks (paired: tasks in both arms)
    reason: str | None                # set whenever lo/hi are None

def interval(obs: Sequence[Obs], params: Params, key: str) -> Interval: ...
def paired_delta(ref: Sequence[Obs], treat: Sequence[Obs], labels: tuple[str, str],
                 params: Params, key: str) -> tuple[Interval, tuple[str, ...]]: ...  # + tasks in one arm only
def no_detectable_effect(iv: Interval) -> bool | None: ...   # None when not computed
def pass_k(outcomes: Sequence[int], planned: int) -> tuple[Measure, Measure]: ...  # (pass@k, pass^k) of one task
def rank(rows: Mapping[RowId, tuple[Interval, Interval]]) -> dict[RowId, tuple[str, str | None]]: ...
    # RowId = tuple[str, str] (combo, pack); value (primary, pass@1) -> (rank "1" | "2=" | "", reason)
```

`src/harness_bench/composites.py` — pure over a loaded catalog. It reads a file only in `load_catalog`:

```python
@dataclass(frozen=True)
class Catalog:
    version: str
    hash: str                          # runner.catalog_hash(root): the one definition
    metrics: Mapping[str, Mapping]     # id -> the metric's catalog entry
    areas: Mapping[str, tuple[str, ...]]
    has_anchors: bool                  # every kind:score, weight>0 metric has an anchor

def load_catalog(root: Path) -> Catalog: ...
def normalise(metric_id: str, raw: Measure, cat: Catalog) -> Measure: ...
def area(scores: Mapping[str, Measure], area_id: str, cat: Catalog) -> tuple[Measure, tuple[tuple[str, str], ...]]: ...
def gated(scores: Mapping[str, Measure], cat: Catalog) -> Measure: ...
```

`src/harness_bench/board.py` — the statistics projection over `RunView`s (replaces `views.leaderboard`):

```python
@dataclass
class BoardRow:
    combo: str; pack: str; harness: str; model: str
    n_cells: int; n_valid: int
    pass_at_1: Interval; gated: Interval; pass_at_k: Measure; pass_hat_k: Measure   # points only (spec :933)
    rank: str; rank_reason: str | None
    tokens: Measure; wall_ms: Measure; cost_usd: Measure     # moved verbatim from views._row

@dataclass
class Board:
    run_id: str; catalog_version: str | None; params: Params
    primary: str; primary_reason: str | None     # "gated" | "pass_at_1" (DR-S-1)
    rows: list[BoardRow]; pack_effect: PackEffect

def build(view: RunView, cat: Catalog, params: Params) -> Board: ...
def compare(base: RunView, view: RunView, cat: Catalog, params: Params) -> Comparison: ...  # HB-STA-001/002
def export(board: Board, comparison: Comparison | None = None) -> bytes: ...  # ledger.canonical
```

**Consumed** (all opened in this session): `views.load`, `RunView`, `CellView`, `Measure` (`views.py`);
`plan["cells"][i]` fields `task`, `rep`, `task_version` and `plan["matrix"]["repetitions"]`,
`plan["matrix"]["combos"]`, `plan["bom_version"]`, `plan["pack"]["revision"]` (G8); `runner.catalog_hash`
(`grade/runner.py:106`); `config.load_yaml`; `ledger.canonical` (used by `views.export`, `views.py:615`);
`report.disclosure_rows`, `report.na`, `report.rate`.

**Error codes** (new codes are a seam to `errors.py`'s wave-4 owner; both exit with the invalid-input code, G11):

| Code | Meaning | Raised by |
| --- | --- | --- |
| `HB-STA-001` | statistics input spans more than one grading pass of one run (R-19); e.g. `--baseline` names the run itself | `board.compare` |
| `HB-STA-002` | runs not comparable: every difference named | `board.compare` |
| `HB-STA-003` | `--resamples` below 2,000 in `bench report` (US-36, R-78 condition 7) | `cli.cmd_report` |
| `HB-USR-002` (existing) | `--seed` or `--resamples` out of range | `stats.Params` |

**CLI** (a seam to `cli.py`'s owner): `bench report <run_id> [--seed N] [--resamples B] [--baseline <run_id>]`.

## Determinism guarantee

**Statement.** `board.export(board.build(views.load(run), load_catalog(root), Params(s, B)))` is byte-identical for
the same run ledger (current pass), the same catalog bytes, the same `s` and `B`, and the same statistics code
(US-36 criterion 3). The same holds for the CLI table and the HTML page, apart from the one timing line
(section Telemetry), which is printed to the CLI only.

**Mechanism.** No wall-clock, no ambient state:
- canonical input order (tasks, then reps, sorted);
- one RNG stream per quantity, seeded from sha256(`seed|key`);
- only `Random.random()` is called (G16);
- `Decimal` in a fixed local context;
- output quantised to 4 decimals with `ROUND_HALF_UP` at the export edge, as strings;
- `ledger.canonical` for the bytes.

The export records `METHOD`, `seed` and `resamples`. The header row also names the Python `major.minor` that
produced the random stream (class ENV-A: the stream is a property of the environment, so it is recorded, not
assumed constant). That field is kept **out of the export bytes**, so a CI Python bump that moves no number
moves no golden (Test Architect round 3, finding 2). A bump that does move the stream fails T-S4 and T-B3,
which is the intended signal.

`assume:` CPython's `random.Random(int).random()` sequence is stable across Python versions (G16, recalled from
the docs, not opened). **Confirm:** the golden stream test (T-S4) pins the first draws and one full interval;
it runs on every commit in CI's Python. **Breaks if false:** after a Python upgrade the same seed gives different
intervals and T-S4 fails loudly. The published numbers stay reproducible on the recorded Python (the header row
names it). The remedy is a counter-based stream built on `hashlib` (sha256 of `seed|key|i`), which needs
no `random` at all.

## Change-surface list (E7)

| Layer | Change | Slice |
| --- | --- | --- |
| Store (ledger) | none | — |
| Model: catalog | `anchor` per weighted score metric; derived weights (DR-S-1, DR-S-3); `0.5.dev`, then the `0.5` freeze with new goldens | Leader |
| Model: validation | `config.validate_metrics`: anchor shape, direction agrees with `better`, `worst != best` | S4 (seam) |
| Service | `stats.py`, `composites.py`, `board.py` (new); `grade/normalize_scores.py` deleted (the stub; `grader_build` only records the hash, G18) | S1–S5 |
| Projection / wire | `board.export` bytes (new); `views.export` drops `leaderboard` (DR-S-4) | S5 |
| Client type | `BoardRow`, `Board`, `PackEffect`, `Comparison` replace `views.Row` | S5 |
| UI | CLI leaderboard columns, the pack-effect table, the header row; HTML `#leaderboard`, `#pack-effect`, `#comparison` tables with `data-interval-*` | S6, S7 |
| CLI | `--seed`, `--resamples`, `--baseline` | S6 (seam) |
| Compute readers | US-42's claim check and summary 2 (row 20) read `board.export` and `stats.no_detectable_effect`, never a re-derivation | row 20 |
| Tests to move | `tests/test_views.py:1316`, `:1383`, `:1400` and `tests/test_report.py:51` (the placeholder strings) move to `tests/test_board.py`; the leaderboard flag tests named in `tests/mutations/report.json` and `r35_r36.json` keep passing against `board` rows | S5, S6 |

## Patterns (named and justified)

The Solution-Selection Ladder was climbed first. **Need:** yes, US-36/37/52 are smoke/full criteria. **Reuse:**
`views.Measure`, `ledger.canonical`, `runner.catalog_hash`, `report.disclosure_rows` and `report.na` are reused
as they are. **Stdlib:** `random`, `hashlib`, `decimal` do the whole job (G13: 0.024 s per interval). **No new
dependency:** numpy or scipy is not justified at this size (rung 5 not reached), and it would bring float into the
values.

| Pattern | Where | Why this one |
| --- | --- | --- |
| On-demand Projection (the existing `views.py` pattern) | `board.py` | Derived, never stored (ADR-0006); the same pattern as `views`, in its own module, so `views` stays about facts and validity |
| Pure functions over value objects (Functional Core, Imperative Shell) | `stats.py`, `composites.py` | T1/T2 code: the property tests call them with no fixture; the shell (`load_catalog`, `views.load`, the CLI) does the I/O |
| Nonparametric bootstrap, percentile interval, two-stage cluster resampling (Efron & Tibshirani 1993; Davison & Hinkley 1997, ch. 3.8 on hierarchical data) | `stats.interval`, `stats.paired_delta` | The spec names bootstrap and the tasks × repetitions unit; percentile is the smallest correct interval; two-stage keeps the task clustering that a flat cell resample would ignore |
| Keyed RNG streams (counter/key-based stream splitting, as in reproducible simulation practice) | `stats` | One stream per quantity makes an interval independent of what else is computed |
| Interval-order components plus a monotone merge (a fixpoint) | `stats.rank` | The only rule found that meets US-36 (i) and (ii) for every input (section Ranking) |
| Table-driven configuration | the catalog anchors | The catalog already drives weights, areas and graders |

Rejected: **BCa** (bias-corrected and accelerated). Its acceleration needs a jackknife over tasks, which is
unstable at n = 6 and has no stable analogue for the two-stage design; upgrade trigger in R1. **A flat cell
bootstrap**: it ignores the task clustering. At k = 1 it equals the task stage, but at k = 3 it is too narrow.
**The cluster-only bootstrap** (resample tasks, keep each task's repetitions whole): measured on the same seeds
(Appendix A), it covers 0.85–0.88 at 6 tasks × 3 reps against the two-stage design's 0.97, and 0.92–0.96 at
24 × 3 against 0.98–0.99. It is nearer nominal at the full grid but under-covers at the sizes this benchmark
runs. The spec's aim is to refuse separations the data cannot support, so the conservative two-stage design is
kept. Upgrade trigger: T-S8 shows two-stage coverage above 0.99 at the full grid (it is too wide to separate
anything real). Then switch to cluster-only for grids of at least 24 tasks.
**Stratified-by-task with tasks fixed**: at k = 1 every stratum has one value, so every interval has zero width
(G20: the smoke run is k = 1). **Ranking by "1 + rows strictly better"**: it breaks US-36 (i) (section Ranking).
**numpy**: not needed (G13).

## Error and concurrency model

- Pure functions; no shared state; no concurrency. `board.build` is called once per report.
- A value that cannot be computed is a `Measure(None, reason)` or an `Interval` with `reason`, never an exception
  and never 0.
- Only three exceptions: `HB-USR-002` (params), `HB-STA-001`, `HB-STA-002`. Each is a `BenchError`, so the CLI maps
  it to an exit code and prints its message, as today.
- An integrity failure in the ledger stays `views.load`'s (HB-LED-002/003). This design adds no second check.

## Failure-mode analysis

| # | Mode (from a design choice) | Disposition | Test |
| --- | --- | --- | --- |
| F1 | n < 2 tasks: a degenerate interval would look certain | **prevent**: `interval not computed (n < 2)` | T-S1 |
| F2 | every valid cell NA for a measure; an NA or invalid cell entering as 0 | **prevent**: `board` filters before `stats`; point NA with the reason; never 0 | T-B8, T-S1, T-C1 |
| F3 | unequal repetitions per task (some NA) | **prevent**: the task-balanced mean; tasks weigh equally | T-S2 |
| F4 | the pass was graded under another catalog than the loaded one | **detect**: every normalised score NA, reason names both versions and hashes | T-C3 |
| F5 | two passes of one run mixed (R-19) | **prevent**: one `RunView` is one pass (G9); `--baseline` on the same run raises `HB-STA-001` | T-B4 |
| F6 | a caller changed the ambient `decimal` context | **prevent**: `localcontext` inside `stats` | T-S5 |
| F7 | Python changes the `random()` stream | **detect**: the golden stream test fails (T-S4); `assume:` marker | T-S4 |
| F8 | overlap is not transitive, so count-based ranks contradict (i) | **prevent**: components | T-R1..R11 |
| F9 | the composite order contradicts pass@1 dominance | **prevent**: the tier merge | T-R7, T-R8 |
| F10 | the percentile interval under-covers at small n (G14) | **accept** (R1), mitigated by closed-interval overlap and "touching zero" | T-S8 (calibration) |
| F11 | E1–E3 exclusion removes all tasks | **prevent**: n < 2 → `not computed`; the exclusion line always prints | T-P3 |
| F12 | runs differ in combos, BOM or catalog | **prevent**: `HB-STA-002` naming every difference | T-B5 |
| F13 | `--resamples` huge (a slow report) or < 2,000 | **prevent**: bounds 2,000–100,000, `HB-USR-002` | T-S6 |
| F14 | an anchor with `worst == best` (division by zero) or its direction against `better` | **prevent**: `bench validate` refuses | T-C4 |
| F15 | a raw value outside its anchors | **mitigate**: clamp to 0 or 100 (monotone, bounded) | T-C2 |
| F16 | the rank and the pass@1 row defined twice (views and board) | **prevent**: `views.leaderboard`/`Row` deleted in the same slice; an `ast` test forbids the symbols in `views.py` | T-B6, T-B9 |
| F17 | an export golden moved by statistics code while the catalog did not change (US-4 false alarm) | **prevent**: statistics leave `views.export` (DR-S-4); `board.export` has its own golden | T-B3 |
| F18 | a pack-on arm has an area the pack-off arm cannot have (P-source metrics) | **detect**: `not computed (no <area> score in pack=off)` | T-P4 |
| F19 | full-grid cost | **accept**: about 130 intervals × 0.024 s ≈ 3 s (G13, Inferred for the count) | timing line |

## Adversarial analysis (STRIDE-lite)

Trust boundaries: (1) the ledger segments that `views.load` reads; (2) `bench/metrics.yaml` (a repo file, the
Leader's); (3) `bench report` arguments (the operator); (4) the report file that leaves the machine.

| Boundary | Threat | Disposition |
| --- | --- | --- |
| 1 | **T**: a score row edited to move a rank | **transfer**, named: the hash chain and seals that `views.load` verifies (HB-LED-002), and `bench verify` |
| 2 | **T**: an anchor edited after the freeze to move composites | **transfer**, named: the US-4 control (b) on `catalog_hash` (`tests/test_catalog_version.py`) |
| 3 | **D**: `--resamples 10**9` | **mitigate**: the 100,000 bound (T-S6) |
| 3 | **T**: a chosen seed to shop for a favourable interval | **mitigate**: the seed is printed in the header and the export, so a reader sees it. **Accept** the rest: a single operator (ADR-0012), and the default seed is fixed in code |
| 4 | **I**: statistics add text to a published report | **transfer**, named: the report's existing credential/egress scan (`html.scan`, US-47). The new text is combo ids, area ids, task ids and numbers only |
| all | **S**, **R**, **E** | none new: a local CLI with no identity, no privilege change, and the seed and parameters recorded |

## Privacy analysis (LINDDUN-lite)

No personal data: the statistics read numeric scores, combo, task and area identifiers, and plan fields only.

## UI and interaction design

The full UI is row 20 (`/ui-design`, S-10). Row 19's surfaces are the text tables in section "Where each result
reaches the report", using the existing report tokens, copy style and states. The copy strings are the spec's
own (`:1031-1054`): `2=`, `interval not computed (n < 2)`, `no detectable effect`, `This run has one pack setting;
no effect to show.`, `Pack effect needs both settings.` A reader never sees 0 where a value is missing. The UI
craft gate and the full state set are row 20's.

## Telemetry

`bench report` is a local batch command; the report path has no spans today (`cli_table.py`, `html.py` import
none), and this design adds none (Decision: a span per report would have no collector to read it). What is
measured on the normal path, with no flag:
- the CLI prints `statistics: <m> intervals in <t> s` after the tables (how long, how much), from
  `time.perf_counter` around `board.build`; it never enters the HTML or the export, so bytes stay deterministic;
- the counts that answer "which path": ranked vs unranked rows, rows whose interval is `not computed`, and the
  primary measure. All are in the export and the header;
- stable error codes `HB-STA-001`, `HB-STA-002`, and `HB-USR-002` for the parameters.

The timing line has a test (T-B7: present, parseable, and absent from the HTML).

## Test plan (the Testing Strategy union)

Triggers (`.claude/knowledge/testing-strategy.md` §3) and their directives:
- **T1** (pure calculation) → **D1**, unit tests plus mutation: `tests/mutations/stats.json`, `composites.json` and `board.json`, all killed.
- **T2** (math over a wide input domain) → **D2**, property tests with `hypothesis` (G15). A shrunk counterexample becomes a permanent example test.
- **T3** (a new module and a dependency direction) → **D3**, a structural test: `stats` imports only stdlib and `harness_bench.errors`; `views` imports none of `stats`, `composites`, `board`; `board` imports no `grade` module except through `composites.load_catalog`.
- **T7** (a canonical payload) → **D6**, a golden statistics export with a pinned digest.
- **T4** (filesystem ledger) → **D4**, one test through the real `views.load` on the committed ledger fixture (`tests/fixtures/ledger/heads`), not a hand-built `RunView`.
- **D0** applies to every test. The seed is fixed. There is no clock except T-B7's, which asserts shape, not value.

`stats` (`tests/test_stats.py`):
- **T-S1** (red first for S1): `interval` returns `interval not computed (n < 2)` for 1 task, and a point NA for 0 tasks. Never a zero-width interval, never 0.
- **T-S2**: the task-balanced point on an unbalanced fixture. Exact: 3 tasks with 1, 2 and 3 reps.
- **T-S3** (hypothesis, over generated observation sets). The generator must produce unbalanced repetition counts; The unbalanced branch is counted: A counter incremented in the property body is asserted `> 0` after the decorated function returns (the test calls the `@given` function, then asserts), and one deterministic `@example` takes the branch. Properties:
  - the same seed and key give an identical `Interval`;
  - shuffling the input gives the same interval;
  - adding another quantity does not move this one;
  - `min(values) ≤ lo ≤ hi ≤ max(values)`;
  - constant data gives `lo == hi == value`.

  A `hypothesis` `assume` is not used to discard most inputs, so the corpus cannot be empty (class GATE-A). Each property also has one example test. NA handling is not tested here: `Obs.value` admits no NA, so the filter lives in `board` and is tested by T-B8.
- **T-S4** (D6, golden): the first 5 draws of `rng(20260927, "k")` and one full `Interval` over a committed 6-task fixture, pinned as exact strings **in the test source**.
- **T-S5**: set `getcontext().prec = 5` and compute. The bytes are unchanged.
- **T-S6**: `Params` refuses resamples 1999 and 100001, seed −1 and seed `2**63`, each with `HB-USR-002`. It accepts 2000, 100000 and `2**63 − 1`.
- **T-S7** (paired):
  - swapping arms gives `(−hi, −lo)` exactly (hypothesis);
  - tasks in one arm only are listed;
  - paired `n < 2` gives `interval not computed (n < 2)`;
  - `no_detectable_effect`: `(lo=−1, hi=0)` → True, `(lo=0, hi=2)` → True, `(lo=1, hi=2)` → False, `(lo=−3, hi=−1)` → False, not computed → None.
- **T-S8** (calibration, `slow` ring): the Appendix A coverage simulation at **6 tasks × 3 reps, p = 0.5**, 200 trials with fixed seeds.
  - It asserts coverage ≥ 0.93. The two-stage design measured 0.973 and the rejected cluster-only variant 0.883, so the threshold separates them.
  - It also asserts the **exact covered count**, pinned when S1 first runs it. With fixed seeds, any change to the quantile rule or the draw order fails the test.
- **T-K** (pass@k, pass^k): the table in section pass@k, one example per cell of the table, including `K − len(R)` missing with a recorded failure → pass^k 0.

`rank` (`tests/test_stats.py`):
- **T-R1..R11**: exact fixtures for K1–K11. **T-R3** (all overlap → `1=`) is S2's red-first test.
- **T-R12** (hypothesis), over random interval sets. Rank strings are compared numerically after stripping `=`. Properties:
  - (i) any two overlapping rows hold equal ranks;
  - (ii) `below(pass@1(X), pass@1(Y))` ⇒ `rank(X) ≥ rank(Y)`;
  - ranks are competition ranks;
  - with no gate conflict, the tiers equal the overlap components.
- **T-R13** (hypothesis, a second strategy): it constructs X, Y with `below(pass@1(X), pass@1(Y))` and X's composite interval entirely above Y's. It adds random other rows, asserts (ii), and counts the gate-conflict branch (A counter incremented in the property body is asserted `> 0` after the decorated function returns (the test calls the `@given` function, then asserts), and one deterministic `@example` takes the branch.), so clause (ii) is never vacuous.
- **T-R14** (K12): composites disjoint and `X.pass@1.hi == Y.pass@1.lo` (touching, not below) → ranks `1`, `2`. It kills a `below` written as `<=`.
- **T-R15** (K13): four rows giving `1`, `2=`, `2=`, `4`, the spec's own `2=` example.
- **T-R16**: X is ranked with its pass@1 interval not computed; Y's composite interval is entirely below X's; Y's pass@1 interval is entirely above every other row's. The ranks are `1` (X) and `2` (Y), with no merge: a row without a pass@1 interval takes part in the tiers and in no gate check.

`composites` (`tests/test_composites.py`):
- **T-C1** (red first for S4; **hypothesis**, as spec `:442` requires "a property test over generated score sets"). It generates score sets with at least 2 metrics of weight > 0, and m's normalised value is non-zero in most draws. It asserts that composite(S) with m NA equals composite(S without m), weights renormalised. Where that differs from the composite with m's normalised score set to 0, setting m to 0 gives a different result. The zero-differs branch is counted: A counter incremented in the property body is asserted `> 0` after the decorated function returns (the test calls the `@given` function, then asserts), and one deterministic `@example` takes the branch. One example test is kept.
- **T-C2** (hypothesis): normalisation is monotone in `better`'s direction and bounded to 0–100. The strategy draws raw values on an interval strictly containing the anchors (`worst − span .. best + span`), and asserts `N == 0` beyond `worst` and `N == 100` beyond `best`, so the clamp mutant dies.
- **T-C3**: a pass whose `catalog_hash` differs from the loaded one → NA with both versions named.
- **T-C4**: `bench validate` refuses `worst == best`, and refuses a direction that disagrees with `better`.
- **T-C5**: the gated composite.
  - The three rows of its rule: `pass_at_1 = 0` gives 0 even when `overall` is NA.
  - `overall` is NA only when all seven areas are NA: six NA and one present gives that one area's value.

`board` (`tests/test_board.py`). **Board fixtures are produced by the real pipeline, never by editing rows.** The committed `tests/fixtures/ledger/heads` run holds one task (X1) and one pack arm (Verified), so every interval on it is `n < 2`. Editing rows in a copy breaks the hash chain (HB-LED-002), and `ledger.py` has no public append or seal function. The fixtures come from a shared builder, `tests/stats_fixtures.py::stats_run(root, tmp_path, *, tasks, reps, arms, outcomes)`, which generalises `tests/test_views.py::_copilot_run` (the real writer, sealed segments, one graded pass). It covers at least 6 tasks including E1 and E2, `matrix.repetitions = 3`, both pack arms, and per-(task, rep, arm) pass/fail outcomes. Every board test reads its run through the real `views.load`: this is the D7 fidelity pairing. T-B1 alone stays on `heads` (points only; one task is enough).
- **T-B1** (red first for S5, D4): `build` on the committed fixture. Its pass@1 points equal **named constants** taken from `tests/fixtures/catalog/0.4/heads.export` (pinned in the test before S5 deletes `views._row`).
- **T-B2**: the header row text (method, resamples, seed, unit, primary, Python version).
- **T-B3** (D6): the `board.export` golden.
  - It is built by `stats_run` with fixed inputs and S4's committed **test** catalog with anchors, never from the live `bench/metrics.yaml`. The export holds no run timestamp or grading id, so the build's own identifiers do not reach the bytes.
  - Its sha256 is pinned in the test source, outside the US-4 goldens tree, so the `.dev` exemption cannot reach it.
  - A comment states that the digest changes only with `METHOD` or the fixture.
- **T-B6** (D3, `ast`): `views.py` defines none of `leaderboard`, `Row`, `_row`, `_mean`. `views.export(fixture)` has no `leaderboard` key.
- **T-B7**: the timing line is printed by the CLI, parseable, and absent from the HTML.
- **T-B8** (US-27 at the row layer): a `stats_run` build. One valid cell's `pass_at_1` is NA, produced by the grader path that records NA (a missing hidden-test result), with its reason `r`. One cell is invalid, through the validity path `_copilot_run` already exercises. Asserts:
  - `n_valid`;
  - the row interval equals `stats.interval` over the remaining cells only, and differs from the interval with the NA cell as 0;
  - the footnote is exactly `1 of <n_valid> valid cells NA: r`.
- **T-B9** (D3, `ast` import graph): `stats` imports only stdlib and `harness_bench.errors`; `views` imports none of `stats`, `composites`, `board`; `board` reaches `grade` only through `composites.load_catalog`.

Pack effect (`tests/test_board.py`):
- **T-P1**: `on − off` sign on a fixture where the pack helps.
- **T-P2**: `no detectable effect` on a fixture crossing zero.
- **T-P3**: on a fixture holding E1 and E2 cells, the pack effect **equals** `paired_delta` over the arms with E1–E3 removed by hand, and **differs** from the unfiltered value. The exclusion line is asserted in the pack-effect section only. A second fixture with none present prints `none in this run`.
- **T-P4**: the one-setting and missing-arm states with the spec's copy.

Report (`tests/test_report.py`):
- **T-U1** (red first for S6): the CLI prints the columns and the header row.
- **T-U2**: the HTML intervals carry `data-interval-lo`/`-hi`, and the attributes are absent when not computed.
- **T-U3**: the existing combo-flag tests stay green.

Comparison (`tests/test_board.py`, `tests/test_report.py`):
- **T-M1** (red first for S7): the refusal naming each difference, end to end through the CLI exit code. The HTML section reads `Runs not comparable: <each difference>`.
- **T-M2**: a shared pack revision labelled `a replication`.
- **T-M3** (US-52 criterion 1): run A is a `stats_run` build; run B is a **second build** with one (task, rep) outcome flipped from pass to fail in one (combo, pack). No row is edited. `compare(base=A, view=B)` gives:
  - that row's delta point exactly `−1/n` (task-balanced), with `lo` and `hi` present;
  - the label from `stats.no_detectable_effect`;
  - the one-run task list.

  `compare(base=B, view=A)` gives the negated point.
- **T-B4**: `compare` on the same run → `HB-STA-001`.
- **T-B5** (parametrised, one `HB-STA-002` naming all of them): combos, BOM version and catalog version differ; a run not graded; a task version differs.

**Named mutants** (D1; each must be killed by the test named, and the slice's mutation file lists exactly these at least):

| File | Mutant | Killed by |
| --- | --- | --- |
| `stats.json` | the n < 2 guard deleted | T-S1 |
| `stats.json` | `j = B × 25 // 1000` off by one (`+1`) | T-S4 |
| `stats.json` | the seed left out of the key | T-S3 (key isolation), T-S4 |
| `stats.json` | `localcontext` removed | T-S5 |
| `stats.json` | a bound of `Params` loosened | T-S6 |
| `stats.json` | `no_detectable_effect` as `lo <= 0` | T-S7 (`−3, −1`) |
| `stats.json` | `below` as `<=` | T-R14 |
| `stats.json` | the gate merges only X and Y | T-R8 (K8) |
| `stats.json` | the tier sweep uses `<` instead of `≤` | T-R5 (K5) |
| `stats.json` | pass^k returns NA when a failure is recorded with reps missing | T-K |
| `composites.json` | the clamp removed | T-C2 |
| `composites.json` | NA metric's weight kept in the denominator | T-C1 |
| `composites.json` | `gated` NA when `pass_at_1 = 0` and `overall` NA | T-C5 |
| `board.json` | an NA cell enters as 0 | T-B8 |
| `board.json` | an invalid cell enters | T-B8 |
| `board.json` | the E1–E3 filter dropped (line kept) | T-P3 |
| `board.json` | the HB-STA-001 check dropped | T-B4 |
| `board.json` | one HB-STA-002 precondition dropped (each, parametrised) | T-B5 |
| `board.json` | `base` and `view` swapped in `compare` | T-M3 |
| `board.json` | seed or resamples left out of the export | T-B3 |

## Seams

| # | From → to | What | When |
| --- | --- | --- | --- |
| Z-1 | row 19 → Leader | the catalog `0.5.dev` edit: anchors (DR-S-1), derived weights (DR-S-3); later the `0.5` freeze with new goldens (DR-S-4) | before S5 |
| Z-2 | row 19 → `errors.py` owner | `HB-STA-001`, `HB-STA-002` | before S5 |
| Z-3 | row 19 → `cli.py` owner | `--seed`, `--resamples`, `--baseline` | S6, S7 |
| Z-4 | row 19 → `config.py` owner | the anchor validation | S4 |
| Z-5 | row 19 → Leader | grant the `views.py` hunks (delete `leaderboard`, `Row`, `_row`, `_mean`; drop `leaderboard` from `export`) and the moved test lines in `tests/test_views.py` / `tests/test_report.py` | S5 |
| Z-6 | row 19 → row 20 | US-38 stability, cost-of-pass, tokens per solved, charts and summaries read `board.export` / `Board`; no re-derivation | row 20's design |
| Z-7 | row 19 → Leader | add the `documents` link from `docs/security/threat-model.md` and `docs/security/privacy-review.md` to this design and refresh the rollups (`docs-graph.py rollup`); those files are outside this track's owned path (the same seam as `phase3-graders.md`'s SEC row) | at the join |

## Slice plan (dependency order)

Each slice is red first and ends with its mutation file all killed and the default ring green. The intended
harness for row 19 is Codex `gpt-6-sol` (`coordination-finish-harness-bench.md:255`). The Leader stipulates the
model per slice (R-33).

| Slice | Owns | Depends on | Red-first test | Exit evidence |
| --- | --- | --- | --- | --- |
| **S1** bootstrap core | `stats.py` (`Params`, `Obs`, `Interval`, `interval`, the stream), `tests/test_stats.py`, `tests/mutations/stats.json`, the golden fixture | this design | T-S1 | T-S1..S6, T-S8 green (T-S8's exact count pinned); the named `stats.json` mutants killed |
| **S2** ranking | `stats.rank`; its tests | S1 (`Interval`) | T-R3 | T-R1..R16 green |
| **S3** paired delta, pass@k | `stats.paired_delta`, `no_detectable_effect`, `pass_k`, `CONTAMINATION_PRONE` | S1 | T-S7 (the antisymmetry example) | T-S7, T-K green |
| **S4** composites | `composites.py`, `tests/test_composites.py`, `tests/mutations/composites.json`; delete `grade/normalize_scores.py`; Z-4 | DR-S-1..3 ruled; a test catalog with anchors (no dependency on the Leader's edit) | T-C1 | T-C1..C5 green |
| **S5** board projection | `board.py`, `tests/stats_fixtures.py` (the `stats_run` builder, written first), `tests/test_board.py`, `tests/mutations/board.json`; Z-2, Z-5 | S1–S4; Z-1 at `0.5.dev` (the US-4 exemption, G3) | T-B1 | T-B1..B3, T-B6..B9, T-P1..P4 green; the named `board.json` mutants killed; `views.export` without `leaderboard` |
| **S6** report wiring | `report/cli_table.py`, `report/html.py`, `report/__init__.py` (the header row); Z-3 flags | S5 | T-U1 | T-U1..U3 green; `bench report smoke-1` read by the Leader |
| **S7** comparison | `board.compare`, the `#comparison` section, `--baseline` | S5, S6 | T-M1 | T-M1..M3, T-B4, T-B5 green |

S1 and S4 have no dependency on each other and can run in parallel. S2 and S3 each need only S1.
The critical path is S1 → S2 → S5 → S6 → S7 (S4 joins at S5).

## Decision requests (open)

| # | Question | Options | Recommended default | Why |
| --- | --- | --- | --- | --- |
| **DR-S-1** | The spec (`:212`) normalises by catalog anchors; the frozen `0.4` has none (G5). How are composites and the rank computed? | (a) catalog `0.5` adds `anchor: [worst, best]` to every weighted score metric; until a pass is graded under it, composites are NA and the **primary measure is pass@1** for the whole run, disclosed in the header; (b) the same, but rows are unranked until `0.5`; (c) implicit anchors from each metric's natural range | **(a)** | Keeps a useful, honest rank under `0.4`. It is the same algorithm with the primary measure named. (c) invents anchors the catalog does not hold (spec `:212`). The re-grade under `0.5` is pure and cached (US-26) |
| **DR-S-2** | The gated composite is named (`metrics.yaml:17`, spec `:213`, proposal `:300`) but never given a formula | (a) per cell `pass_at_1 × overall`, where `overall` is the unweighted mean of the non-NA area composites; (b) lexicographic (pass@1 first): no single number, so no interval; (c) `overall` over passing cells only | **(a)** | The only option that gives one number per cell for the bootstrap. A failing cell is 0 (a measured failure). The pass@1 dominance rule carries the gate at row level (C1) |
| **DR-S-3** | Four `kind: derived` metrics have `weight: 1` (G6), but a cell composite cannot hold a quantity above the cell grain | (a) cell composites read `kind: score` metrics only, and `0.5` sets those four weights to 0 so the catalog states what the code does; (b) compute composites at the task grain | **(a)** | (b) breaks the tasks × repetitions resampling unit. With (a) the catalog and the code agree (no DM-A) |
| **DR-S-4** | The `0.4` golden export pins the leaderboard's placeholder interval and pass@1 rank (G2); any statistics change moves it | (a) the leaderboard leaves `views.export`; statistics get their own canonical bytes (`board.export`) and golden; the change lands in the `0.5.dev` window (the US-4 exemption, G3), and the Leader re-pins at the `0.5` freeze; (b) keep the statistics inside `views.export` | **(a)** | `views.export` guards scores under a catalog version (US-4). Statistics code is not catalog content; coupling them makes every statistics fix look like "a score moved without a bump" |
| **DR-S-5** | The spec lists "the bootstrap seed" among stored inputs (`:255`) but names no store | (a) a code constant plus `--seed`/`--resamples`, recorded in every output; (b) freeze the seed in the plan at confirmation (a plan field; old plans need a default anyway) | **(a)** | The smallest option that meets "seed recorded" (US-36). The recorded value reproduces any report. (b) adds a plan field whose only reader is the report |
| **DR-S-6** | US-37 excludes E1–E3 from the pack effect. Does US-52's comparison (a pack-change validation) exclude them too? | (a) yes, the same rule and the same statement; (b) no, only US-37 | **(a)** | A comparison of pack revisions is a pack-effect analysis (proposal `:370`, "excluded from the pack-effect analysis"); contamination biases both equally |

## Conformance notes

- ADR-0006 "Derived, never stored": conformed. There is no new fact. `Decimal`, never float, for values.
- `phase3-graders.md` obligation R-19: current pass only, and multi-pass input refused (F5, T-B4).
- R-63: no single verdict enters a composite (G10).
- Spec copy strings reused verbatim (`:1031-1054`).
- `n` counts tasks, not cells (Decision). The spec's copy `interval not computed (n < 2)` is kept. The header's
  unit line says what n counts.
- Deviation: the pass@1 row point becomes the task-balanced mean. It equals today's value whenever every task has
  the same number of valid recorded cells (the planned case; smoke-1 has k = 1). T-B1 pins the equality on the
  fixture.

## Flagged risks and residual unknowns

- **R1** (measured, G14): at 6 tasks × 1 repetition, intervals under-cover (0.74) when nearly every cell passes.
  Mitigated, not removed, by closed-interval overlap and "touching zero". **Upgrade trigger:** the first report
  used to claim a separation at fewer than 10 tasks, or T-S8 failing. Then move to a studentized or BCa variant,
  or print `small sample (n = <n> tasks)` beside such intervals.
- **R2**: the tier rule is conservative. A chain can tie rows whose own intervals are disjoint (K4). This is
  intended: the spec prefers "cannot separate" to a false winner.
- **R3** (Inferred, G16): Python's `random()` stream stability. Detected by T-S4.
- **R4**: DR-S-1..6 are open. S4–S7 depend on DR-S-1..4. S1–S3 depend on none.
- **R5**: the full-grid cost (F19) is extrapolated from one measured interval. The timing line measures it on the
  first full run.

## Gate record

**Round 1 — Patterns Expert ⇄ Simplifier** (run inline by the author, Stage 4; the author's own review, so it
clears nothing by itself). Each pattern had to survive both.

| # | Lens | Finding | Disposition |
| --- | --- | --- | --- |
| P1 | Patterns | Name the interval. Percentile or BCa? BCa has better coverage for skewed statistics | Percentile kept. BCa's jackknife acceleration is unstable at n = 6 and has no clean two-stage form; BCa remains R1's upgrade path |
| P2 | Patterns | The textbook for clustered data is the cluster (top-stage-only) bootstrap; two-stage double-counts repetition variance | **Measured, not argued** (Appendix A). Cluster-only under-covers at 6 × 3 (0.85–0.88); two-stage holds 0.97. Kept two-stage, with an upgrade trigger for the full grid (section Patterns) |
| P3 | Patterns | Count-based ranking ("1 + rows better") is the common leaderboard idiom | Rejected with a counterexample (section Ranking): it breaks US-36 (i) and, with two criteria, (ii) |
| P4 | Patterns | Name the RNG discipline | Keyed per-quantity streams, draw order in the contract, golden-pinned (T-S4) |
| S1 | Simplifier | Three new modules; fold `composites` into `board`? | Kept. `composites` carries the US-27 property and the S-08f semantics, testable without a `RunView`; `board` is the projection. Each module has one reason to change |
| S2 | Simplifier | Intervals for pass@k and pass^k: nothing shows them (spec `:933` shows `pass^k` with no ±) | **Accepted.** Points only; the contract changed |
| S3 | Simplifier | The pack effect adds `pass_at_1` beyond the spec's "each area" | Kept, with a reason. Under DR-S-1's default every area is NA until catalog `0.5`, and pass@1 is the gate measure (C1). Without it the smoke pack effect would show nothing |
| S4 | Simplifier | The comparison's task-version check (precondition 5) is implied by the BOM invariant | Kept. This session did not check where the BOM invariant is enforced, and pairing across runs is only valid on equal task versions. It costs one comparison |
| S5 | Simplifier | Separate arm streams keyed by label add machinery | Kept. The streams make the delta independent of which arm is the reference, and the exact antisymmetry test (T-S7) depends on it. The cost is a few lines |
| S6 | Simplifier | `MAX_RESAMPLES` for a single-operator tool | Kept. It is one bound, it prevents F13, and it costs nothing |

Verdict round 1: **Patterns: pass. Simplifier: pass** after S2. No soft veto stands.

**Round 2 — Test Architect (hard veto)**. An independent seat: a subagent on `claude-fable-5-1`, read-only, on
the draft at `30af0a5` plus round 1. **Verdict: BLOCK (3 Blockers, 7 Majors, 9 Minors).** It found no
counterexample to the ranking algorithm. Every finding was applied as stated:

| # | Sev. | Finding | Applied |
| --- | --- | --- | --- |
| 1 | Blocker | US-52 criterion 1 (a successful comparison's direction, interval, label) had no falsifying test; swapping `base`/`view` passed | T-M3 added; mutant "base and view swapped" named |
| 2 | Blocker | The NA/invalid cell filter lives in `board`, but only `stats` was tested (`Obs` admits no NA) | T-B8 added (exact footnote, n_valid, differs-from-0); F2 re-pointed; two `board.json` mutants |
| 3 | Blocker | T-S8 at 24 × 3 with ≥ 0.90 stays green under the rejected cluster-only method (measured 0.960) | T-S8 moved to 6 × 3, p = 0.5, ≥ 0.93 (0.973 vs 0.883), plus the exact covered count pinned |
| 4 | Major | `no_detectable_effect` as `lo <= 0` survived | T-S7 adds `(−3, −1)` → False and `(−1, 0)` → True |
| 5 | Major | Spec `:442` requires a property test for US-27; T-C1 was an example and could be vacuous | T-C1 made `@given` with an asserted `hypothesis.event` |
| 6 | Major | "All mutants killed" over unnamed mutants is green on an empty list (GATE-A) | The named-mutant table added (20 mutants, each with its killing test) |
| 7 | Major | T-P3 passable by printing the exclusion line while keeping E1–E3 (TEST-A) | T-P3 asserts equality with a hand-filtered delta and inequality with the unfiltered one |
| 8 | Major | T-B1 compared with `views._row`, which S5 deletes | T-B1 pins named constants from `heads.export` |
| 9 | Major | T-B3's golden could be regenerated under the `.dev` exemption, or move with the live catalog | T-B3 uses the committed test catalog; digest pinned in the test source, outside the US-4 tree |
| 10 | Minor | T-R12 may never generate a gate conflict | T-R13, a constructive strategy with an asserted event |
| 11 | Minor | `below` strictness untested | T-R14 (K12, touching pass@1 intervals) |
| 12 | Minor | No fixture yields the spec's `2=` | T-R15 (K13: `1`, `2=`, `2=`, `4`) |
| 13 | Minor | The `2**63` seed bound untested | T-S6 extended |
| 14 | Minor | Preconditions 1 and 5 and the HTML refusal untested | T-B5 parametrisation and T-M1's HTML assertion extended |
| 15 | Minor | T-B4/T-B5 test S7's `compare` but sat in S5's exit | Moved to S7's exit |
| 16 | Minor | The D3 test had no id; T-B6 grepped a substring | T-B9 (`ast` import graph); T-B6 by `ast` over the four symbols and the export key |
| 17 | Minor | Paired n < 2, a ranked row without a pass@1 interval, and "overall NA only when all seven NA" untested | Added to T-S7, T-R16, T-C5 |
| 18 | Minor | D7: hand-built RunViews not paired with the real `views.load` shape | Every board fixture is built from `tests/fixtures/ledger/heads` through `views.load`, then mutated as a ledger |
| 19 | Minor | ENV-A: the Python version is not recorded | Recorded in the header row (round 3 moved it out of the export) |
| note | — | The gate loop needs only one pass (a merge never separates rows) | Step 3 rewritten as one pass, with the reason |

**Round 3 — Test Architect re-review** (same seat) of the round-2 fixes. It found the 19 fixes sufficient, but
**BLOCK** on one new Blocker. All round-3 findings were applied:

| # | Sev. | Finding | Applied |
| --- | --- | --- | --- |
| 1 | Blocker | The board fixtures were infeasible: `heads` holds one task (X1) and pack off only (**re-verified by the author**: 2 cells). Edited rows break the hash chain, and `ledger.py` has no public append/seal | The shared real-pipeline builder `tests/stats_fixtures.py::stats_run` (generalises `_copilot_run`); T-M3's run B is a second build; T-B8's NA and invalid cells come from the grader and validity paths; T-B1 alone stays on `heads` |
| 2 | Major | The Python version in `board.export` made T-B3's digest move on a Python bump with no numeric change | Kept in the header row only, out of the export bytes |
| 3 | Minor | T-C2 could not kill the clamp mutant | Raw values drawn beyond the anchors; asserts `N == 0` / `100` there |
| 4 | Minor | "`hypothesis.event` asserted" is not a Hypothesis API | A branch counter asserted `> 0` after the `@given` function returns, plus a deterministic `@example` |
| 5 | Nit | T-R16 gave the outcome, not the construction | The construction stated; ranks `1`, `2`, no merge |

**Round 4 — Test Architect** (same seat, re-read after the author saved finding 2). **Verdict: CLEARS THE VETO
at the design gate — PASS WITH CONDITIONS.** Fixes 1–5 were verified present and sufficient, and nothing
vacuous was introduced. The conditions are carried to the slice Proof Packs and do not reopen the design:
1. **(Major if missing)** Each slice's Proof Pack shows its named red-first test observed red before the slice
   (T-S1, T-R3, T-S7, T-C1, T-B1, T-U1, T-M1). It also shows every named mutant in the table above killed. An
   empty or partial mutation file is GATE-A and re-blocks at the join.
2. **(Minor)** T-S8's exact covered count and T-B3's digest are characterisations pinned on first green. The
   Proof Pack labels them so (D6). Red is carried by the ≥ 0.93 threshold and by the mutants that hit the export.
3. **(Minor)** `tests/stats_fixtures.py` is in S5's Owns column, so no slice hand-builds a `RunView` while it
   waits. **Applied** (Slice plan).

**Gate summary.**

| Seat | Verdict |
| --- | --- |
| Patterns Expert | pass |
| Simplifier | pass, after S2 |
| Test Architect (hard veto) | cleared at round 4, with conditions 1–3 |

Security and Distributed Systems: no trigger. There is no trust-boundary change beyond the STRIDE table's
transfers, and no async or messaging. Residual risk: R1, R3, R5 (section Flagged risks).

## Status and next action

| | |
| --- | --- |
| **Completed** | the row-19 design: data model, composites, bootstrap, ranking, pack effect, comparison, report surfaces, contracts, tests, slices |
| **Remaining** | the DR-S-1..6 rulings; the catalog `0.5.dev` edit; row 20 (`/ui-design`, full report, summaries) |
| **Best next action** | the Leader rules DR-S-1..6, then dispatches S1 and S4 in parallel (`/implement`) |

## Appendix A — the spikes (measurements behind G13 and G14)

Both were run in this session on Python 3.12.10, stdlib only, from scratch scripts (not committed; S1's T-S8
turns the second into a test).
- **Cost and determinism.** A two-stage bootstrap as specified above (tasks drawn with `int(rng.random() * n)`,
  then reps within each drawn task), 24 tasks × 3 reps of `Decimal` values, B = 2,000, stream seeded from
  sha256(`20260927|row|cc-opus|on|gated`). Wall time 0.024 s (`Decimal`) and 0.014 s (int). Two processes gave
  the same interval and the same first draws.
- **Coverage.** Task pass probabilities `p_t ~ Beta(a, b)`, cells `Bernoulli(p_t)`. Estimand: `a / (a + b)`.
  300 trials per row, B = 2,000, fixed seeds:

| tasks × reps | true rate 0.5 (Beta 2,2) | true rate 0.8 (Beta 4,1) |
| --- | --- | --- |
| 6 × 1 | 0.977 (mean width 0.62) | **0.740** (0.43) |
| 6 × 3 | 0.973 (0.59) | 0.967 (0.44) |
| 24 × 1 | 0.920 (0.40) | 0.937 (0.30) |
| 24 × 3 | 0.987 (0.31) | 0.977 (0.25) |

Resampling at both stages over-covers when there are repetitions (0.97–0.99), which errs toward "cannot
separate". The 6 × 1 high-rate cell is the all-pass degenerate case (R1).

The rejected cluster-only variant (tasks resampled, repetitions kept whole), measured with the same seeds and
trials at k = 3: 6 × 3 gives 0.883 (width 0.47) and 0.853 (0.35); 24 × 3 gives 0.960 (0.27) and 0.920 (0.21). At k = 1
the two variants are the same procedure.
