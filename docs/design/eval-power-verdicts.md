---
id: "design-eval-power-verdicts"
title: "Design: power, verdicts, dominance, ring gates and report section 3 (W1-H; X-H1, X-H2)"
type: design
status: proposed
owner: "@timianmalloo"
phase: "Enterprise evaluation: Wave 1 design slice W1-H (build in E1)"
tags: [benchmark, statistics, power-analysis, verdict, dominance, ring-gate, report, evaluation-campaign]
links:
  - { to: spec-enterprise-evaluation, rel: implements }
  - { to: arch-evaluation-campaign, rel: implements }
  - { to: adr-0020-power-and-verdicts-stdlib, rel: depends-on }
  - { to: design-eval-seam-contracts, rel: depends-on }
  - { to: adr-0006-results-data-model, rel: depends-on }
  - { to: rulings-register, rel: depends-on }
review-by: "2026-10-17"
summary: >-
  Pure stdlib design for X-H1 (power.py, verdicts.py, gates.py) and the section-3 view for X-H2. Settles the
  derived-view data model (nothing persisted), pins the three reference sizes (93, 53, 115) exactly with an
  independent formula and a seeded-wrong variant, the stratified paired bootstrap and the verdict and dominance
  rules as boundary tables with named mutants, nine pilot gate kinds each with a red fixture, the R-93 warning
  line, and the NA-never-dropped rule. Reports measured spikes, two defects found in W0 text (seed width, resolved
  in rev 3) and four open items.
---

# Design: power, verdicts, dominance, ring gates and report section 3

- **Status:** In review (Gate record pending).
- **Spec / architecture:** `docs/specs/enterprise-evaluation.md` EV-12, EV-14, EV-15, EV-18, EV-19, EV-20, EVX-6, EVX-7, EVU-1..EVU-8 · ADR-0020 · `docs/design/eval-seam-contracts.md` rev 3 sections 3, 6, 7, 8, 13 (re-read after the Leader's notice; rev 3 is on main at `1ceea651`, the W1-H answers at `8295e3c9`).
- **Delivery phase:** build in E1 (X-H1: `power.py`, `verdicts.py`, `gates.py`; X-H2: `report/campaign_section.py` and the `report/html.py` hook). E1 demo shape (R-89): one harness (`cc-opus`), k = 3, `min_pairs` <= 3, expected label `inconclusive (underpowered)`.
- **Author / date:** `w1h-power-e1e4` (Claude Sonnet 5.5, `claude-sonnet-5-5`), 2026-10-03.

## 1. Responsibility and boundaries

One responsibility: turn recorded inputs into **derived** answers, with no I/O in the three modules (ADR-0020 §5, W0 §8).

| unit | does | does not |
| --- | --- | --- |
| `power.py` | sizes pairs per (property, harness, comparison); solves the MDE back; costs the grid | read a run, pick a plan, store anything |
| `verdicts.py` | forms pairs and exclusions from `CellView`s; computes label, intervals, token ratio, statement | decide eligibility (X-D/X-C) or admission |
| `gates.py` | lists failing items for a pilot run; says `regression signal` or not for a regression ring | read files (X-E passes lists in) |
| `report/campaign_section.py` (X-H2) | renders the verdict rows, the exclusions block, the NA counts and the R-93 line | compute any statistic |

Crossings: in from `campaign.read` (X-C), `readiness.hidden_test_disagreements` and `readiness.unbiased_failures` (X-E), `views.CellView`, `views.cell_arm` (X-A1, G1). Out to X-C's registration check (gate items), the completion summary and the report.

## 2. Data model (settled first)

**Bounded context:** evaluation analysis. **Ubiquitous language:** *pair* (one task, one repetition, both arms recorded), *stratum* (a task), *effect*, *interval*, *MDE*, *label*, *verdict*, *statement*, *gate item*, *NA count*.

**Aggregates:** none. Every output is a value object recomputed on read (DM7, ADR-0006 *Derived, never stored*). The campaign stores only inputs and decisions (`power/<input_hash>.json`, `prereg/<hash>.json`, W0 §6; writer X-C, compute reader this slice). The one invariant this slice protects is a function property, not a transaction: **the label is a total function of `(n_pairs, min_pairs, lo, hi, mde)` through one function, `label_for`**, and no other code path emits a label.

**Durable representation:** no new store, so no new ADR (DM13). ADR-0020 stays the decision. *Note for the Coordinator:* ADR-0020 §2 still says "streams from `stats.rng(plan seed, key)`"; W0 rev 2 replaced the plan's seed with `seed_for`. The ADR needs a one-line amendment (not mine to edit).

**Grain, additivity, history (per output):**

| output | one row is exactly one | additivity | history rule |
| --- | --- | --- | --- |
| `Pair` | (task, rep) of one (harness, comparison) in which both arms recorded the primary metric | `n_pairs` additive across tasks | none; derived |
| `Verdict` | (property, harness, comparison) of one campaign grid, at one set of attached runs | `n_pairs`, `excluded` count additive; **effect, interval, ratios non-additive** (never average two verdicts' effects; a ratio is recomputed from the sums) | Type-2 by recomputation: a re-grade changes inputs, so a verdict is never edited, it is recomputed and names the fixes it was computed under (EV-16) |
| `PowerResult.required_pairs` row | (harness, comparison) of one property in one input hash | `n` is not additive across harnesses (each harness is its own test) | input hash is the version |
| `cells`, `hours`, `tokens` | one property in one input hash | additive across properties (sum over five properties = the 2,430 / 4,230 / 5,220 cells in the spec) | same |
| `GateItem` | (kind, ident) in one ring run | counts additive | derived |

**Derive-don't-store decisions:** `alpha_per_test`, `resamples`, `reps_per_task`, the MDE back-solve, the token ratio and `statement` are computed, never fields in a stored file. **No verdict cache in E1.** *simplify:* verdicts recomputed on every report write. Ceiling: measured 0.35 s for n = 115 at 40,000 resamples (spike S3); a worst-case 90 verdicts at 18,000 resamples is about 40 s (Inferred from the spike), paid once at report-write, not at page load. Upgrade trigger: `verdicts_ms` (telemetry, section 12) above 60,000 for one report write. The upgrade is a labelled rebuildable cache `verdicts/<input_hash>.json` with an equality test against the derivation.

**Writer and compute reader for every persisted field this slice touches:** `bench-power-inputs/1` (writer X-C, reader `power.analyse`); `bench-prereg/1` (writer X-C, reader `verdicts`, `gates`); the `Score` rows and `property.json` evidence (writer X-F, readers `views`, `readiness`, `gates`). This slice writes no field.

## 3. Contracts

### 3.1 W0 text relied on (quoted)

- §8: "verdict sorts pairs by (task, rep) before any use, so input order never changes a resample"; "`seed_for` ... `int(sha256(...).hexdigest()[:15], 16)`"; "`pilot(view, hidden_test_disagreements, unbiased_failures)`"; "kinds ... `check-tampered` and `suspend-detector-blind`".
- §3 rev 3: "An NA cell appears in `Verdict.excluded` with its reason ... **Refused:** changing a verdict's label because of an NA count. That rule is ADR-0020's and would need the Owner." This design therefore never lets an NA count touch `label_for`.
- §7 condition 3 (R-93): the warning line is "in report section 3, beside ADR-0020's exclusions, and **not** in the EV-20 header. It changes no verdict, no exclusion and no eligibility."
- ADR-0020 §2: "not enough recorded pairs -> `inconclusive (not recorded)`; lower > 0 -> `better`; upper < 0 -> `worse`; interval strictly inside (-MDE, +MDE) -> `no difference >= MDE`; else `inconclusive (underpowered)`." §3: "`A dominates B` iff A vs B is `better` or `no difference >= MDE` **and** the ratio's upper bound < 1. No other rule emits the word."

### 3.2 Exposed

```python
# power.py  (grade class; stdlib: statistics.NormalDist, math, decimal)
PAIRING = ("unpaired", "task-harness-rep")           # the only accepted pairing_unit values (seam req-...YG)
def n_unpaired_exact(p0: float, p1: float, alpha: float, power: float) -> float     # Fleiss, Levin & Paik, no continuity correction
def n_paired_exact(psi: float, delta: float, alpha: float, power: float) -> float   # Connor 1987
def mde_for(n: int, sizer: Callable[[float], float], lo: float = 0.001, hi: float = 0.999) -> float  # bisection, 60 steps
def analyse(inputs: Mapping) -> Mapping[str, PowerResult]        # W0 §8; HB-PWR-001 names the field
# PowerResult adds (additive to W0): alpha_per_test, reachable_mde (None unless planned_reps_per_task given), descriptive {sd, rep_spread}

# verdicts.py  (grade class)
def alpha_per_test(prereg) -> Decimal            # alpha/m for bonferroni and holm (DR-H1), alpha for none
def resamples_for(alpha_per_test: Decimal) -> int   # max(2000, ceil(20 / alpha_per_test)); > 100000 -> HB-USR-002
def seed_for(...) -> int                         # W0 §8 rev 3
def label_for(n_pairs: int, min_pairs: int, lo: Decimal, hi: Decimal, mde: Decimal) -> VerdictLabel
def statement_for(label, treat: str, ref: str, ratio: Ratio | None) -> str | None
@dataclass(frozen=True) class VerdictSpec:       # W0 §8 allows this narrowing; meanings unchanged
    prop: str; harness: str; comparison: tuple[str, str]; tasks: tuple[str, ...]   # the admitted tasks of the property
    mde: Decimal; alpha_per_test: Decimal; min_pairs: int; seed: int; resamples: int; required_pairs: int | None
def collect(cells, spec, primary: str = "property_check_pass") -> tuple[list[Pair], list[tuple[str, str]], dict[str, int]]
def verdict(spec, pairs, excluded, na_counts) -> Verdict   # verdict(prop, harness, ...) of W0 is spec + these three
# Verdict adds (additive): level, mde, resamples, seed, reason (NOT_RECORDED text), pairs_by_task, na_counts {reason: n}, required_pairs

# gates.py  (grade class)
class GateKind(StrEnum): CELL_FAILED="cell-failed"; INFRASTRUCTURE="infrastructure-cell"; BND_A="bnd-a-loss"; GRADER_ERROR="grader-error";
    METRIC_UNRECORDED="metric-not-recorded"; PRIMARY_UNRECORDED="primary-not-recorded"; TASK_NO_PRIMARY="task-no-primary";
    CHECK_TAMPERED="check-tampered"; SUSPEND_BLIND="suspend-detector-blind"; HIDDEN_NONDETERMINISTIC="hidden-tests-nondeterministic"
def ring_items(view, expected_na) -> list[GateItem]      # the cell-level items, shared by pilot and the regression ring's "withheld"
def pilot(view, hidden_test_disagreements, unbiased_failures, expected_na) -> list[GateItem]   # sorted by (kind, ident)
def pack_regression(view, mde) -> Mapping[str, str]
```

`expected_na` and `planned_reps_per_task`, `slots` are additive items in seam request `req-01M41EX52AX93PQS1FHYCSA0YG` (section 14); sections that rest on them are **provisional (seam req-01M41EX52AX93PQS1FHYCSA0YG)**.

### 3.3 Consumed, with confidence

| contract | source | confidence |
| --- | --- | --- |
| `stats.rng(seed, key)` accepts any int; `Params` refuses `seed >= 2**63` | `stats.py:37-41`, `:58-59` | Verified (read, and run in spike S2) |
| `stats._percentile` is `j = B*25//1000` (95% only) and private; the existing `paired_delta` resamples tasks as well as repetitions | `stats.py:143-148`, `:157-208` | Verified (read). So neither is reusable: a new corrected-level, task-stratified routine is needed (section 5) |
| `CellView` fields `outcome`, `cause`, `code`, `validity`, `wall_ms`, `tokens`, `scores: dict[str, Measure]` with `.value`/`.reason` | `views.py:110-136` | Verified |
| `views.sum_tokens` returns `None`, never 0, when not recorded | `views.py:268-276` | Verified |
| A grader exception writes NA with reason starting `HB-GRD-003` | `grade/runner.py:357` | Verified |
| `Cause` attributions: `infrastructure` and `benchmark` invalidate | `errors.py:16-45` | Verified |
| BND-A cells carry code `HB-CELL-107` (protocol) | `docs/lessons/defect-classes.md:627-634` (instance) | Verified for the instance; *assume:* every BND-A loss is `HB-CELL-107`. Confirm: the pilot report of the first real ring lists no cell lost to a size bound under another code. Breaks if false: that cell reports as `cell-failed`, still a gate item, only the kind name is wrong |
| `views.cell_arm(cell)` | W0 §10 G1 (X-A1 delivers) | Provisional (W1-A). Fallback: `cell.pack` until X-A1 lands, behind one helper `_arm(cell)` |
| HB-CHK-002 NA reason text is `invalid (check tampered)` | W0 §3 outcome table row 3 | Verified in W0 text; *assume:* it survives into `Measure.reason` unchanged. Confirm: X-F's `test_check_tampered_reason_reaches_the_view` (named in section 11). Breaks if false: tampered cells fall to `primary-not-recorded` |

### 3.4 Spikes run (2026-10-03, Python 3.12.10 locally; ADR-0020 ran 3.14.6)

| id | question | result |
| --- | --- | --- |
| S1 | Do 93 / 53 / 115 reproduce, and what does a wrong z give? | 92.99884 -> 93; 52.52075 -> 53; 114.24879 -> 115 (`NormalDist().inv_cdf`). One-sided z (the seeded-wrong variant): 73.13 / 41.13 / 103.11, so it differs by far more than 1 [Verified] |
| S1b | Does the MDE solve back? | n = 93, p0 = 0.5: 0.199999. n = 53, psi = 0.28: 0.19913. n = 115 (alpha/45): 0.19937. All within 0.005 of 0.20 [Verified] |
| S1c | Does ceil vs round matter? | 114.2488 rounds to 114 but must ceil to 115. 114 is inside the spec's +-1, so a tolerance test would not catch a `round` mutant. **The tests pin the integers exactly** (stricter than EV-12) [Verified] |
| S2 | Is W0 rev 2's `seed_for` a legal `Params` seed? | No: 49.9% of 100,000 seeds were >= 2**63 and `Params` raised HB-USR-002. Fixed in W0 rev 3 (`[:15]`). Fixture row: prereg hash `e1746a8b...effc`, `[:16]` = 14055141998388353605 (illegal), `[:15]` = 878446374899272100 (legal) [Verified] |
| S3 | Cost of the stratified bootstrap | n = 115, B = 2,000: 0.02 s; B = 40,000: 0.35 s; int-draw loop, `stats.rng` stream [Verified, this host] |
| S4 | Coverage, effect, 1,000 datasets, n = 53 (27 + 26 pairs), true effect 0.20, generator `random.Random(20261003)`, B = 2,000 | **0.936** (in 0.93-0.97, thin margin; see R-H2) [Verified] |
| S5 | Coverage, token ratio, same seed, lognormal tokens, true ratio E[T]/E[C] | **0.948** [Verified] |
| S6 | 400 pairs (two tasks of 200), true diff 0.20 vs the normal-approximation interval | normal [0.16366, 0.26634]; bootstrap B = 2,000 [0.1625, 0.2650]; B = 10,000 [0.1650, 0.2675]. Gaps 0.0012 / 0.0013 (EV-18 tolerance 0.01) [Verified] |
| S7 | Hours table | 2,430 cells -> 44.02 h; 4,230 -> 76.63 h; 5,220 -> 94.57 h at 130.44 s per cell and 2 slots (spec: about 45 / 77 / 95) [Verified] |

## 4. Patterns (each past the Patterns Expert and the Simplifier)

| pattern | where | why the smallest correct idiom | rejected alternative |
| --- | --- | --- | --- |
| Pure functions over frozen value objects (Value Object; LOA functional core) | all three modules | ADR-0020 §5; reproducible from inputs and seed | a `Verdict` service with a cache: not needed at measured cost |
| Single decision function (a table-driven rule; "Specification" in one place) | `label_for`, `statement_for`, `_classify_cell` | the four rule orders each live once, so a mutant has one place to land and adjacent rules are separately killable | rules inlined in `verdict`: the sweep "no other path emits a label" would be unenforceable |
| Parameter Object (frozen) | `VerdictSpec` | W0 §8 allows it by narrowing; 8 scalar parameters become one | keep eight positional parameters: error-prone ordering of `Decimal`s |
| Table-of-checks (closed enum + one predicate per kind) | `gates.py` | each EV-14 bullet is one predicate; `GateKind` is closed and tested for coverage | a rule engine: YAGNI |
| Bootstrap with a keyed stream per quantity (existing idiom, `stats.rng`) | `verdicts._boot` | the repo's own T-S3 property: adding a quantity does not move another | `random` global state; a new RNG |
| Stdlib-only (`NormalDist`, `math`, `decimal`) | `power.py` | ADR-0020; spike S1 | `scipy`/`statsmodels` (rejected by ADR-0020) |

Ladder climbed: YAGNI cuts the graded-metric formula (`sd` is carried as descriptive only), the pooled-harness verdict, the verdict cache and a Holm step-down. Reuse: `stats.rng`, `Decimal` context discipline, `views.sum_tokens`, `errors.Cause`. New code only where the stdlib and repo have nothing (corrected-level stratified percentile).

## 5. Algorithms

**Power (`analyse`).** For each property: validate (HB-PWR-001 names the field). `alpha_pt = alpha/m` for `bonferroni` and `holm`, `alpha` for `none`. `unpaired`: `n_unpaired_exact(p0, p0 + mde, ...)`, `p0 = control_rate` or 0.5 when `"assumed"` (listed in `assumed`). `task-harness-rep`: `n_paired_exact(psi, mde, ...)`, with `psi = discordance`, or, when absent or `"assumed"`, `psi = p0(1-p1) + p1(1-p0)` under independence (0.5 at p0 = 0.5; listed in `assumed`). `n = ceil(exact - 1e-9)` (*simplify:* the epsilon snaps float noise on an exact integer; ceiling: none seen in S1; upgrade trigger: a reference that lands within 1e-9 of an integer). `reps_per_task = ceil(n / len(tasks))`. `cells = len(tasks) * len(harnesses) * len(arms) * reps_per_task` (`arms` = distinct arms over `comparisons`; calibration cells excluded and stated). `hours = cells * mean_wall_per_cell_s / slots / 3600`. `tokens = cells * mean_tokens_per_cell`. `mde` in the result is `mde_for(n)`, the MDE the integer `n` actually detects; `reachable_mde = mde_for(len(tasks)*planned_reps_per_task)` when given (EV-12 last bullet; the plan shows it instead of the target). `sd` and `rep_spread` are echoed into `descriptive` and **not** used for sizing in E1 (a binary primary); a test proves changing them leaves `n` unchanged. Graded primaries are out of scope (DR-E5).

**Verdict.** `pairs` sorted by `(task, rep)`; a duplicate `(task, rep)` is refused (HB-USR-002), because it would double count. Metric values are scaled to integers at 10^4 (the catalog's finest scale); a value that is not an exact multiple is refused. Strata are `spec.tasks`. **A stratum with no pairs makes the label `inconclusive (not recorded)` with the reason `task <id>: 0 pairs recorded`**, because dropping it would silently change the estimand from "both tasks weighted equally" to one task. Per resample: for each stratum in task order draw `w` indexes with `int(rng.random() * w)` (the repo's `_draw` contract), take the stratum mean; the statistic is the mean of stratum means, held as an exact integer over the common denominator `lcm(w_t) * k * 10^4`, so no float decides a boundary. Endpoints: the sorted statistics at index `floor(B * alpha_pt / 2)` and `B - 1 - floor(...)`, converted to `Decimal` with the module context. Streams: `stats.rng(seed, "effect")`, `"ratio"`, `f"task|{id}"`. The token ratio is `sum(treat_tokens)/sum(ref_tokens)` over resampled pairs at the fixed 95% level (EV-19), `None` when the denominator is 0 or any token count is unrecorded in the pair set; wall ratio is the point value. Percentile intervals are invariant to the log transform, so the "log scale" is a display choice only.

**Rules** (`label_for`, in this order, one function):

```
1. n_pairs < min_pairs                      -> NOT_RECORDED
2. lo > 0                                   -> BETTER
3. hi < 0                                   -> WORSE
4. -mde < lo and hi < mde                   -> NO_DIFFERENCE
5. otherwise                                -> UNDERPOWERED
```

`both_tasks` is `True` iff the label is `BETTER` (`WORSE`) and every task's own interval has `lo > 0` (`hi < 0`); `False` if a task disagrees or has fewer than 2 pairs; `None` for other labels. `statement_for`: `BETTER` or `NO_DIFFERENCE` with ratio `hi < 1` -> `"<treat> dominates <ref>"`; else `BETTER` -> `"better at ×<r> tokens"` (any ratio, with its interval shown by the section); else `None`; `None` too when the ratio is not recorded.

**Collecting pairs (`collect`).** For the cells of one `(harness, ref arm, treat arm)` in scope, every cell lands in **exactly one** place: a pair half, or `excluded` with `(cell_id, reason)`. Order of reasons (first match): `calibration or non-admitted task`, `invalid (<attribution>)`, `<outcome label> (<cause>)` for blocked, failed, timed_out without the primary, stopped, `<NA reason of the primary>` (this is where `invalid (check tampered)` and `HB-GRD-003 ...` land, and `na_counts[reason] += 1`), `pair partner not recorded (<partner id or absent>)`. Conservation: `2 * len(pairs) + len(excluded) == cells in scope` (hypothesis test, section 11).

**Gates.** `ring_items(view, expected_na)`, per cell, first match wins: `bnd-a-loss` (`code == "HB-CELL-107"`), `infrastructure-cell` (`Cause` attribution `infrastructure` or `benchmark`), `cell-failed` (outcome `failed`, or any `blocked`). Per cell: `grader-error` (any score reason starts `HB-GRD-003`); `check-tampered` (primary reason is `invalid (check tampered)`); `primary-not-recorded` (primary NA for any other reason and not already tampered or grader-error: one item per cell). Per (task, metric): `metric-not-recorded` when a metric with a row is NA in every cell of the task and not in `expected_na[task]` (detail names the reasons). Per task: `task-no-primary` when no cell of the task has a `property_check_pass` row at all (the grid-4 G2 shape). `pilot = ring_items + hidden-tests-nondeterministic (per id) + suspend-detector-blind (per id)`, sorted by `(kind, ident)`, unique. *assume:* the pilot's tasks are property tasks, so the primary id is the constant `property_check_pass` (W0 §2 SIM 5). Confirm: readiness checks it. Breaks if false: a non-property task reports `task-no-primary`. `pack_regression`: per property, effect = candidate minus incumbent; `"regression signal"` iff the 95% interval has `hi < 0`; else `f"no regression detected at {mde}"`; if an arm is absent the value is `"Result withheld: ring is missing <arm>."`. Seed `seed_for(ring_hash, prop, "ring", (incumbent, candidate))`. *simplify:* fixed 95% uncorrected. Ceiling: one comparison per property per ring. Upgrade trigger: a ring with more than one candidate.

## 6. Report section 3 (X-H2; the E1 shape)

Section id `property-verdicts` for a comparison-grid report, `regression-check` for a ring report, inserted as the third section (after `validity`, before `leaderboard`). `html.render` gains `campaign_obj=None`; with `None` the section is absent and the page is unchanged (EVU-4; `tests/test_report_builder.py:165` pins the id list).

Blocks, in DOM order: campaign block (sub-block of section 1 per spec; not rebuilt here), legend, **exclusions block**, verdict table, dominance lines, exploratory note.

**Exclusions block (R-93).** One line `excluded <n> cells in total` with the list disclosure (id, arm, cause) that EV-18 and US-43 require; then, immediately after it, the NA count line `not recorded by reason: invalid (check tampered) 1; ...` (rev 3 obligation); then the warning line, rendered **only when the count is above 0**:

```html
<p class="warn" data-kind="hidden-test-disagreement" data-count="2">Hidden tests disagreed with pass@1 in 2 cells: C-014, C-031.
These cells' hidden-test results are not deterministic. No verdict, exclusion or eligibility changed.</p>
```

State table for this line: list non-empty -> the element, with the count and ids; empty list -> **no element** (DOM count 0); `None` (the X-E reader failed or was not run) -> `<p class="warn" data-kind="hidden-test-agreement-not-recorded">Hidden-test agreement not recorded: <reason>.</p>`. The third state goes beyond R-93's literal text (which names n > 0 only) so that a failed reader is never shown as "no disagreement"; it is a flagged extension, section 13 R-H3. The count and ids come only from the `Sequence[str]` argument the caller reads from `readiness.hidden_test_disagreements`; the section computes nothing.

**Verdict cell** follows the UI spec's eight-part order. Additions from this design: part 7 reads `n <pairs> of <required>` when `required_pairs` is known (the honest companion to a small-n label, R-H1); part 8 is `excluded <n>` plus the NA counts by reason. Copy strings are the UI spec's table, produced from `Verdict` fields. `data-interval-lo`, `data-interval-hi`, `data-mde` on effect marks; the ratio bar carries the lo/hi only. The ring section never prints `better`, `worse` or `dominates`.

**Single source of the word `dominates`.** `statement` is the only origin. The section prints `statement` and appends context. The empty state `No arm dominates another.` is the one literal allowed in the section (sweep S-2, section 11).

## 7. Failure-mode analysis

| # | mode (category) | disposition | telemetry / test |
| --- | --- | --- | --- |
| F1 | invalid power input: alpha, power, mde outside (0,1); m < 1; unknown method or pairing; `psi < mde^2` (Connor's root would be imaginary); missing tasks (input) | **prevent**: HB-PWR-001 names the field | `test_power_inputs_each_invalid_field_is_named` |
| F2 | float noise lands a size on an integer boundary (state) | **mitigate**: `ceil(x - 1e-9)`, *simplify:* above | boundary test P-B |
| F3 | W0's old `seed_for` >= 2**63 (input) | **prevent**: rev 3 `[:15]`; red row in `test_seed_for_is_a_legal_params_seed` | |
| F4 | input order changes a resample (state) | **prevent**: sort; duplicate key refused | `test_input_order_never_changes_a_verdict` |
| F5 | a stratum has no pairs, silently changing the estimand (state) | **detect**: NOT_RECORDED with reason | `test_empty_stratum_is_not_recorded` |
| F6 | an NA or lost cell dropped without trace (state; seam req-01M41DM7X) | **prevent**: conservation invariant; **detect**: `na_counts`, `excluded`, `check-tampered` gate item | conservation test, tampered fixtures |
| F7 | clock unreadable, suspend undetected (dependency) | **detect**: `suspend-detector-blind` item per cell | `test_gate_suspend_blind_*` |
| F8 | tiny sample gives a zero-width interval and a confident label (state) | **accept with rationale**: `min_pairs` is pre-registered (R-89 allows <= 3 for the demo only); the cell shows `n <pairs> of <required>`; residual R-H1; test pins the behaviour so a change is a conscious one | `test_degenerate_sample_is_labelled_by_rule_not_hidden` |
| F9 | tail too thin for a corrected level (resources) | **prevent**: `resamples_for` gives >= 10 tail draws; > 100,000 refused | `test_resamples_for_tail_depth` |
| F10 | verdict cost grows with m (resources) | **detect**: `verdicts_ms`; *simplify:* trigger in section 2 | telemetry test |
| F11 | metric value not on the 10^4 grid (input) | **prevent**: refused HB-USR-002 | `test_off_scale_value_is_refused` |
| F12 | zero ref tokens, unrecorded tokens (input) | **mitigate**: ratio `None`, statement `None`, cell shows `tokens: not recorded`; never 0 | `test_ratio_not_recorded_*` |
| F13 | reader of `hidden_test_disagreements` or `unbiased_failures` fails (dependency) | **mitigate**: `None` is a distinct input; `pilot` raises HB-USR-002 on a `None` list (see note) | `test_pilot_refuses_unread_lists` |
| F14 | coverage test passes by luck of the seed (time) | **prevent**: recorded seed chosen before the run; a failure is a finding, never a re-seed (R-H2) | |
| F15 | two definitions of the same quantity (state) | **prevent**: tokens via `views.sum_tokens`; cause attribution via `errors.Cause`; label via `label_for` | sweeps S-1, S-3 |

Note on F13: a pilot with an unread list must refuse. The pure function takes `Sequence[str]`, so "unread" is X-C's call-site duty; `pilot` rejects `None` with `BenchError("HB-USR-002", ...)` so the failure is loud. No new HB code is reserved: this slice retires none and adds none; it uses `HB-PWR-001` (reserved) and the existing `HB-USR-002`.

## 8. Adversarial analysis (STRIDE-lite)

Trust boundaries: (1) cell outputs and evidence reaching the view (agent-influenced); (2) the inputs file and prereg (operator-authored, content-addressed); (3) the rendered HTML (reader). No personal data (section 9).

| threat | disposition | negative test |
| --- | --- | --- |
| **T** a deliverable turns a measured 0 into NA to hide a failure (W1-F RF-5) | **mitigate**: NA stays in `excluded` with its reason, in `na_counts`, and a `check-tampered` pilot item; the label is not changed by NA (W0 §3, refused) | `test_check_tampered_is_listed_not_dropped` |
| **T** a tampered score row removes a pair to flip a label | **accept** with rationale: the ledger chain and `verify` (X-C) guard rows; this slice shows the excluded list | covered at join |
| **S** a verdict computed from a different run than the one attached | **transfer, named**: X-C attach/freeze (W0 §6) and eligibility (EV-20); the header names the pre-registration hash | X-C tests |
| **R** a reader cannot tell which seed or level a verdict used | **mitigate**: `Verdict.seed`, `resamples`, `level` shown in the cell tooltip | DOM test |
| **I** report text leaks evidence | **transfer, named**: egress gate (`_publish`, `html.py:2266`) wraps every `<section id>`; the new section uses the same shape `<section id="[a-z0-9-]+">` | `test_section_is_inside_the_egress_gate` |
| **D** crafted input forces a huge bootstrap | **mitigate**: `resamples` capped at 100,000; pairs bounded by the plan | `test_resamples_cap` |
| **E** none identified (no privileged action) | n/a | |
| **Spoof the word `dominates`** by another module | **mitigate**: sweep S-2 | `test_only_verdicts_emits_dominates` |

## 9. Privacy (LINDDUN-lite)

This slice touches no personal data: it handles counts, ids of cells and task ids, and decimal metrics. Explicit negative; no retention or rights path applies.

## 10. UI design (report section 3)

Medium: self-contained HTML over `file://`; WCAG 2.2 AA; archetype B3 (inherited, no deviation). Tokens: the report's existing tokens only; no new colour, size or radius literal. Encodings, copy strings, per-component state set, motion (none) and accessibility are the UI spec's Part C, implemented as written; this design adds only the three items in section 6 (exclusions block with the R-93 line, the NA-by-reason line, `n of required`). Component states exercised by fixtures (EVU-3): campaign block; legend; verdict table (rows, ineligible, empty); verdict cell (each of the five labels, zero recorded pairs, `k of min` recorded); excluded list (0, 1, > 10); dominance line (present, `No arm dominates another.`); exploratory note; regression table (signal, no signal, gate failed, arm missing, no property tasks, first run). axe (EVU-5) and the UIA-12 contrast check run in the browser ring against the same fixtures. `ui-craft-gate.py` runs on the built report with the CD12 floors. HAX/Shape-of-AI: N/A (spec: no AI content).

## 11. Test plan (by node id; red-first)

**Red-first protocol (all groups).** Commit 1 adds skeletons with the final signatures that return the *neutral wrong value* (`analyse` returns rows with `n = 0`; `label_for` returns `UNDERPOWERED`; `verdict` returns an interval `(0, 0)`; `pilot` returns `[]`; `pack_regression` returns `"no regression detected at 0"`; `campaign_section.build` returns `None`; `html.render` accepts and ignores `campaign_obj`). Commit 2 adds the tests and they fail by **assertion** on a value, never on an import or attribute. The column "fails today because" states the skeleton's value. Where a test can fail against the repo as it is today with no skeleton, that is stated.

Ring: fast ring unless marked. Hypothesis (a dev dependency, `pyproject.toml:19`) provides the property tests. Mutants are `tests/mutations/{power,verdicts,gates,campaign_section}.json` in the repo's find/replace format; `tests/test_mutate_check.py` already proves each `find` occurs exactly once, and `tools/mutate_check.py` proves each is killed by its named tests.

### 11.1 `tests/test_power.py`

| node id | pins | tolerance | fails today because | red fixture / guard | real-wiring or independence | mutant (adjacent rules) |
| --- | --- | --- | --- | --- | --- | --- |
| `test_unpaired_reference_93` | p0 .5, p1 .7, .05, .8 -> `n == 93` exact; `n_unpaired_exact` = 92.99884 +- 1e-4 | exact int | skeleton n = 0 | | the test file holds a hand formula with literal z 1.959963984540054 and 0.8416212335729143 | `ceil` -> `round` is invisible at 93; killed by the 115 row. `z two-sided -> one-sided` (73) killed here |
| `test_paired_reference_53` | psi .28, delta .20 -> 53 exact; exact 52.52075 +- 1e-4 | exact | n = 0 | | same literal-z formula | `sqrt(psi - d*d)` -> `sqrt(psi)` gives a different n |
| `test_bonferroni_reference_115` | alpha/45 -> 115 exact; exact 114.24879 +- 1e-4 | exact (EV-12 allows +-1; 114 is inside it, so exact is required to kill `round`) | n = 0 | | literal z for alpha/90 (3.2608, four places, is within 1 of the exact integer; the exact-int assertion is on the module, the literal formula uses +-1) | `ceil` -> `round` (114) killed; `alpha/m` -> `alpha` (53) killed |
| `test_holm_is_sized_like_bonferroni` | DR-H1 option A: `holm` m 45 -> 115 | exact | n = 0 | `none` method with m 45 must give 53 | | `method in (bonferroni, holm)` -> `== bonferroni` gives 53 for holm |
| `test_alpha_and_power_echo_exactly` | `result.alpha == inputs alpha`, `power == inputs power` (EV-12) | `==` | skeleton returns 0 | | | alpha replaced by `alpha_per_test` |
| `test_mde_solves_back_within_0_005` | MDE of n 93 / 53 / 115 vs 0.20 | 0.005 | skeleton mde 0 | | `mde_for` is checked against the literal-formula `n(delta)` | bisection bounds off (hi 0.5) |
| `test_seeded_wrong_one_sided_variant_fails` | `check_references(power_with(one_sided_z))` **raises AssertionError**; `check_references(real analyse)` passes | -- | the check helper is defined in the test; the fake is a patched `inv_cdf`; the real run passes only once `analyse` is correct | the wrong variant is the red fixture for the reference test | **real-wiring beside the fake**: the same helper on the real `analyse` | |
| `test_determinism_two_runs_identical` | `json.dumps(analyse(x)) == json.dumps(analyse(x))` and pinned golden | exact | skeleton equal to itself, so pair with the golden: golden n == 53 fails | | | iteration over a `set` |
| `test_assumed_control_rate_is_labelled` | `"assumed"` -> p0 .5, `assumed == ["control_rate"]`; a given rate -> `[]` | exact | `assumed` empty | rate given vs not | | label dropped |
| `test_monotone_properties` (hypothesis) | n non-increasing in mde, non-decreasing in power, non-increasing in alpha, non-decreasing in m | integer | skeleton constant 0 passes monotonicity, so each example also asserts `n >= 1` | | | `m` ignored |
| `test_mde_roundtrip_property` (hypothesis) | `n_for(mde_for(n)) <= n` and `n_for(mde_for(n) - 0.005) > n - 2` | | n = 0 | | | |
| `test_power_inputs_each_invalid_field_is_named` | table: alpha 0, 1; power 1.2; m 0; method `sidak`; pairing `paired`; psi .03 with mde .2 (psi < mde^2); tasks `[]`; mde 0 -> `BenchError` code `HB-PWR-001`, message names the field | exact | skeleton returns rows, no raise | one row per guard | | each guard line deleted |
| `test_cells_hours_tokens_reference_table` | sum over five properties of `cells` = 2,430 / 4,230 / 5,220 for n 53 / 93 / 115; `hours` 44.02 / 76.63 / 94.57 | cells exact; hours +-0.05 (spec "about 45 / 77 / 95") | cells 0 | | | `ceil(n/tasks)` -> `n // tasks` (26 for 53: 2,340) |
| `test_sd_and_rep_spread_do_not_change_n` | change both; `n` equal; `descriptive` echoes them | exact | skeleton `descriptive` missing | | | `n` reads `sd` |
| `test_reachable_mde_when_plan_is_short` | planned reps 10 -> `reachable_mde > mde` and equals `mde_for(20)` | 1e-9 | `None` | planned reps absent -> `None` | | provisional (seam) |
| `test_result_round_trips_through_json` | `required_pairs` rows are plain dicts | | | | | |

### 11.2 `tests/test_verdicts.py`

**Rule table** `test_label_for_boundary_table` (EV-18; hand-computed; each row a parametrize id; MDE 0.30 unless stated):

| id | n, min | lo, hi | expect | distinguishes (mutant) |
| --- | --- | --- | --- | --- |
| L1 | 5, 6 | 0.10, 0.50 | NOT_RECORDED | rule 1 evaluated after rule 2 |
| L2 | 6, 6 | 0.10, 0.50 | BETTER | rule 1 `<` -> `<=` |
| L3 | 6, 6 | 0, 0.50 | UNDERPOWERED | rule 2 `lo > 0` -> `>=` |
| L4 | 6, 6 | -0.50, 0 | UNDERPOWERED | rule 3 `hi < 0` -> `<=` |
| L5 | 6, 6 | -0.50, -0.01 | WORSE | rules 2/3 swapped to `hi > 0` |
| L6 | 6, 6 | 0.05, 0.15 | BETTER (not NO_DIFFERENCE) | rule 4 before rule 2 |
| L7 | 6, 6 | -0.15, -0.05 | WORSE (not NO_DIFFERENCE) | rule 4 before rule 3 |
| L8 | 6, 6 | -0.30, 0.10 | UNDERPOWERED | rule 4 `-mde < lo` -> `<=` |
| L9 | 6, 6 | -0.10, 0.30 | UNDERPOWERED | rule 4 `hi < mde` -> `<=` |
| L10 | 6, 6 | -0.29, 0.29 | NO_DIFFERENCE | rule 4 `and` -> `or` |
| L11 | 6, 6 | 0, 0 | NO_DIFFERENCE | the degenerate point (pinned, R-H1) |
| L12 | 6, 6 | -0.50, 0.50 | UNDERPOWERED | rule 5 default changed |
| L13 | 0, 0 | 0, 0 | NO_DIFFERENCE (n 0 is not below a minimum of 0; the empty-stratum rule, not this one, catches an empty set) | rule 1 `<` -> `<=` (also L2) |

Fails today because the skeleton returns UNDERPOWERED: L1, L2, L5-L7, L10, L11 fail by value; L3, L4, L8, L9, L12 pass on the skeleton, which is why each is paired with a mutant that flips it and the mutate_check run is the proof those rows bite (a row that passes on the skeleton earns its place only through its mutant). `test_label_for_is_total_and_exclusive` (hypothesis, `lo <= hi`): exactly one label; `BETTER` implies `lo > 0`; `WORSE` implies `hi < 0`; `NO_DIFFERENCE` implies both bounds strictly inside; `NOT_RECORDED` implies `n < min`. Kills a rule that returns two different labels for the same input.

**Dominance table** `test_statement_for_table` (EV-19):

| id | label | ratio hi (lo, r) | expect | mutant |
| --- | --- | --- | --- | --- |
| D1 | BETTER | 0.99 | `dominates` | |
| D2 | BETTER | 1.00 (boundary) | `better at ×r tokens` (not `dominates`) | `hi < 1` -> `<=` |
| D3 | NO_DIFFERENCE | 0.99 | `dominates` | `or NO_DIFFERENCE` dropped |
| D4 | NO_DIFFERENCE | 1.00 | `None` | `<=` as D2 |
| D5 | WORSE | 0.50 | `None` | WORSE added to the set |
| D6 | UNDERPOWERED | 0.50 | `None` | UNDERPOWERED added |
| D7 | NOT_RECORDED | 0.50 | `None` | |
| D8 | BETTER | lo 1.2, hi 1.5 | `better at ×… tokens` | statement uses `lo` |
| D9 | BETTER | ratio `None` | `None` | `None` treated as 0 |
| D10 | BETTER | lo 0.8, hi 1.4 (straddles 1) | `better at ×… tokens`, never `dominates` | `hi` replaced by `r` |

Fails today: skeleton returns `None`; D1, D2, D3, D8, D10 fail by value. D4-D7, D9 pass on the skeleton and are held by their mutants.

| node id | pins | tolerance | fails today because | red fixture | real wiring | mutant |
| --- | --- | --- | --- | --- | --- | --- |
| `test_normal_approximation_400_pairs` | two tasks of 200, true .20: bounds within 0.01 of normal [0.16366, 0.26634] (observed gap 0.0013) | 0.01 | skeleton interval (0,0) | | `Verdict` built through the real `verdict()` | percentile index `B*alpha_pt/2` -> `B*alpha_pt` (90% interval, gap > 0.01) |
| `test_stratified_equal_task_weight` | tasks of 10 and 90 pairs with effects .5 and 0: `effect == Decimal("0.25")` exactly | exact | skeleton effect 0 | the unequal-size fixture | | weights by pair count (gives .05); pooled resample |
| `test_per_task_and_both_tasks` | `both_tasks` True only if both task intervals exclude 0 the same way; one task with 1 pair -> False; non-directional labels -> None | | skeleton `None` for all | | | `all` -> `any` |
| `test_level_uses_corrected_alpha` | same pairs, m 1 vs 45: the m 45 interval is wider and equals a golden | exact golden | skeleton equal | | | `alpha/m` -> `alpha` |
| `test_resamples_for_tail_depth` | `resamples_for(0.05) == 2000`, `(0.05/45) == 18000`, `(0.0002) == 100000`, `(0.0001) -> HB-USR-002`; tail index `B*alpha/2 >= 10` | exact | skeleton returns 0 | the 0.0001 refusal row | | `20` -> `10` |
| `test_seed_for_is_a_legal_params_seed` | the section-3.4 S2 row: `stats.Params(seed=seed_for("e1746a8b...effc","security","cc-opus",("off","candidate")))` constructs and equals 878446374899272100; hypothesis over 2,000 hashes: all `< 2**63` | exact | **fails today against W0 rev 2's text** (14055141998388353605 -> HB-USR-002); against the rev 3 skeleton `0` fails the equality | the S2 row is the red fixture | `Params` is the real class | `[:15]` -> `[:16]`; any one of the five fields dropped from the key (one test per field changes it and asserts the seed moves) |
| `test_input_order_never_changes_a_verdict` | permute pairs (hypothesis): equal `Verdict` | `==` | skeleton equal for all, so the golden-interval assertion carries the failure | | | sort removed |
| `test_duplicate_pair_key_is_refused` | two pairs same (task, rep) -> HB-USR-002 | | no raise | the duplicate | | guard deleted |
| `test_off_scale_value_is_refused` | `Decimal("0.00001")` -> HB-USR-002 | | no raise | | | |
| `test_empty_stratum_is_not_recorded` | one task has 0 pairs: `NOT_RECORDED`, reason names the task, `n_pairs >= min_pairs` still | | skeleton UNDERPOWERED | task list `["a","b"]`, pairs only in `a` | | strata taken from the pairs instead of `spec.tasks` |
| `test_golden_interval_and_draws` | a 6-pair fixture: interval bytes and the first five draws of `stats.rng(seed, "effect")` | exact | skeleton (0,0) | | pins the Python-version assumption already pinned by `test_stats` T-S4 | stream key renamed |
| `test_adding_a_quantity_does_not_move_the_effect_interval` | with and without tokens: same effect interval | exact | | | | shared stream between effect and ratio |
| `test_ratio_reference_and_not_recorded` | treat = 2 x ref tokens on every pair: ratio `(2, 2, 2)`; zero ref sum -> `None`; missing tokens -> `None`; wall ratio point | exact | skeleton `None` | the zero-sum fixture | | `None` -> 0 |
| `test_conservation_every_cell_in_a_pair_or_excluded` (hypothesis) | random cells with outcomes, validity, NA, calibration, partners: `2*pairs + excluded == cells in scope`, and every excluded id unique | | skeleton returns no pairs and no excluded (0 != n) | | `collect` runs on real `CellView` objects | an `if value is None: continue` that drops silently |
| `test_calibration_cells_do_not_change_any_verdict` (EV-9) | add calibration cells (any values): every `Verdict` equal | `==` | skeleton equal, golden carries it | | | calibration filter removed |
| `test_check_tampered_is_listed_not_dropped` | a cell with primary NA `invalid (check tampered)`: appears in `excluded` with that reason, `na_counts == {"invalid (check tampered)": 1}`, label unchanged vs the same data without that cell's pair | | skeleton empty `excluded` | the tampered cell | | NA cells filtered before the list; label made to depend on `na_counts` (W0 refuses this) |
| `test_one_blocked_cell_shows_excluded_1` (EV-18 last bullet) | `excluded == [(id, "blocked (auth)")]` | | | | the same fixture is rendered in the three places in 11.4 | |
| `test_degenerate_sample_is_labelled_by_rule_not_hidden` | three pairs all +1 -> `BETTER`; three pairs all 0 -> `NO_DIFFERENCE`; both carry `n_pairs 3`, `required_pairs` | | skeleton UNDERPOWERED | | documents R-H1 | |
| `test_e1_demo_shape` (R-89) | k 3, one harness, `min_pairs 3`, mixed diffs (+1, 0, 0 per task): `UNDERPOWERED`, `n_pairs 6` | | the skeleton already says UNDERPOWERED, so the assertion that fails is the golden interval by value | | | |
| `test_coverage_effect` (**slow**) | 1,000 datasets, `random.Random(20261003)`, n 53, true .20, B 2,000: coverage in [0.93, 0.97] (observed 0.936) | 0.93..0.97 | skeleton interval (0,0) covers 0 of 1,000 | | the real `verdict()` | percentile `/2` removed (coverage ~0.89) |
| `test_coverage_ratio` (**slow**) | same seed, lognormal tokens: coverage in [0.93, 0.97] (observed 0.948) | | | | | |

### 11.3 `tests/test_gates.py`

One fixture view per kind; each is the red fixture for its guard, and `test_every_gate_kind_has_a_red_fixture` asserts `set(FIXTURES) == set(GateKind)` (checked against the enum in the tree, so a new kind without a fixture fails).

| node id | fixture | expected | fails today because | adjacent-rule mutant |
| --- | --- | --- | --- | --- |
| `test_clean_view_passes` | a view with no defect | `pilot(...) == []` | passes on the skeleton: the rest of the group carries the failure | a check always firing |
| `test_gate_cell_failed` | one `failed` cell, one `blocked` cell | two `cell-failed` items | skeleton `[]` | `blocked` dropped |
| `test_gate_infrastructure_beats_failed` | cell code `HB-CELL-112` (disk, infrastructure) | exactly one item, kind `infrastructure-cell` | `[]` | precedence swapped to `cell-failed` |
| `test_gate_bnd_a_beats_infrastructure` | code `HB-CELL-107` | one item `bnd-a-loss` | `[]` | precedence swapped |
| `test_gate_timed_out_with_primary_is_not_a_loss` | `timed_out` with primary recorded | no item | passes on skeleton; held by mutant | `timed_out` treated as failed |
| `test_gate_grader_error` | score reason `HB-GRD-003 grader property failed: ValueError` | `grader-error` once per cell, not also `primary-not-recorded` | `[]` | dedupe removed |
| `test_gate_check_tampered_beats_primary_unrecorded` | primary NA `invalid (check tampered)` | one `check-tampered`, no `primary-not-recorded` | `[]` | precedence swapped |
| `test_gate_other_na_is_primary_unrecorded` | primary NA `check exceeded its bound` | `primary-not-recorded`, not `check-tampered` | `[]` | tampered test uses `startswith("invalid")` (caught: also matches `invalid (check output ...)`) |
| `test_gate_metric_not_recorded_with_expected_na_exception` | a secondary NA in every cell; once with `expected_na` naming it | item vs no item | `[]` | exception ignored; `every` -> `any` |
| `test_gate_task_no_primary` | a task whose cells have no `property_check_pass` row | `task-no-primary` | `[]` | uses "value None" instead of "no row" (would fire on NA cells too) |
| `test_gate_hidden_tests_nondeterministic` | list `["c3","c7"]` | two items, idents c3, c7 | `[]` | list ignored |
| `test_gate_suspend_detector_blind` | list `["c5"]` | one item | `[]` | list ignored |
| `test_pilot_refuses_unread_lists` | `None` for either list | HB-USR-002 | no raise | guard deleted |
| `test_pilot_output_is_sorted_unique_and_order_independent` (hypothesis) | shuffled cells | equal list, sorted by (kind, ident), no duplicate (kind, ident) | | sort removed |
| `test_pack_regression_table` | hi < 0 -> `regression signal`; hi == 0 -> `no regression detected at 0.30`; straddle; good direction; exact strings | exact | skeleton always "no regression" so hi < 0 row fails | `hi < 0` -> `<=` |
| `test_pack_regression_missing_arm_is_withheld` | candidate absent | `Result withheld: ring is missing candidate.` | | |
| `test_regression_strings_carry_no_verdict_words` (EVX-6, sweep S-4) | every string constant in `gates.py` and every value from the table | no match for `better\|worse\|dominates` | passes today; held by a mutant adding "worse" to the signal text | |

### 11.4 Section and report (`tests/test_campaign_section.py`, `tests/test_report.py` additions)

| node id | pins | fails today because | red fixture | real wiring | mutant |
| --- | --- | --- | --- | --- | --- |
| `test_r93_warning_line_renders_with_count_and_ids` | seeded list `["C-014","C-031"]`: exactly one `p[data-kind=hidden-test-disagreement]`, `data-count=2`, both ids in the text, placed after the exclusions summary and before the verdict table | **fails today by assertion**: `html.render` has no section, so the element is absent (the skeleton accepts `campaign_obj` and ignores it) | the seeded-disagreement fixture | `html.render(..., campaign_obj=fixture)` end to end, no fake builder | condition `n > 0` -> `n >= 0` (kills the next test) |
| `test_r93_line_absent_when_zero` | `[]` -> 0 elements | passes today (no section); held by the mutant | `[]` | | `>= 0` |
| `test_r93_not_recorded_when_reader_failed` | `None` -> the `hidden-test-agreement-not-recorded` element, never the disagreement element | absent today | `None` | | `None` coerced to `[]` |
| `test_r93_line_changes_no_verdict` | the same verdict cells with and without the line: byte-equal verdict table | | | | line text feeding the label |
| `test_section_reads_the_real_readiness_function` (join test, owner X-INT; **a condition of "done" for X-H2**) | a graded fixture run where the final tree's `hidden_tests_pass` differs from `pass_at_1` for one cell: the report shows that cell id | red until X-E lands | real `readiness.hidden_test_disagreements` | the real function (the fake in the rows above is the list literal) | |
| `test_na_counts_by_reason_beside_every_verdict` | each verdict cell shows `not recorded by reason: ...` equal to `Verdict.na_counts` | absent today | | | |
| `test_excluded_one_cell_in_three_places` (EV-18) | `excluded 1` and the id and cause in the cell, the completion summary and the validity banner | absent today | one blocked cell | | one place dropped |
| `test_evu_1_4_8` | verdict word as text; non-campaign page unchanged and `tests/test_report_builder.py:165` list intact; eight-part order | absent today | | | |
| `test_evu_2_interval_marks` | `data-interval-lo/hi`, `data-mde` on effect marks, equal in the table alternative | | | | |
| `test_evu_3_state_pairs` | one assertion per (component, state) of section 10 | | | | |
| `test_evu_6_ring_section_has_no_verdict_words` | regression section text has none of `better\|worse\|dominates` | | | | |
| `test_evu_7_exploratory_labels` | header text and a badge in every intention-verdict cell; counts > 0 on a campaign report, 0 on a non-campaign one | | | | |
| browser ring: `test_evu_5_axe_light_and_dark`, 1280x800 first-row visibility (EVX-2) | `pytest -m browser` | | | | |

### 11.5 Sweeps and allowlists (each checked against the tree on 2026-10-03)

| id | sweep | root | tokens | allowlist (constant) | tree check |
| --- | --- | --- | --- | --- | --- |
| S-1 | no module other than `verdicts.py` assigns or returns a `VerdictLabel` | `src/harness_bench/`, `*.py`, recursive | `VerdictLabel\.` and the five literal label strings | `LABEL_EMITTERS = {"verdicts.py"}`; readers (`report/campaign_section.py`) only compare | grep for `dominat`, `no difference ≥ MDE`: 0 hits in `src/` and `tests/` today |
| S-2 | the word `dominates` appears only in `verdicts.py` and the one empty-state string | same | `dominates` (case-insensitive) | `DOMINATES_ALLOWED = {"verdicts.py": any, "report/campaign_section.py": {"No arm dominates another."}}` | 0 hits today; red fixture: a temp module containing the word must fail the sweep |
| S-3 | tokens are summed only through `views.sum_tokens`; cause attribution only through `errors.Cause` | the three modules | `\.tokens\.values\(\)`, `attribution ==` | none | the three files are new; the sweep is vacuous until they exist, so its red fixture is a temp file with the pattern |
| S-4 | `gates.py` string constants carry no verdict words | `gates.py` | `better\|worse\|dominates` | none | |
| S-5 | the three modules import no `harness_bench.gateway` (G3) | | | X-D owns G3; listed here only so the trace is complete | |

An allowlist entry that no longer matches a file in the tree fails its sweep (so a stale entry cannot hide a gap).

### 11.6 Trace from W0 and the spec to tests

| contract | test |
| --- | --- |
| W0 §8 power inputs and result | 11.1 |
| §8 `verdict`, sort, `seed_for`, `Pair` Decimal | 11.2 (`input_order`, `seed_for`, `off_scale`) |
| §8 `pilot` three parameters, kinds | 11.3 |
| §3 NA rule, refused label change | `test_check_tampered_is_listed_not_dropped`, `test_gate_check_tampered_*` |
| §7 R-93 | 11.4 R-93 rows |
| seam req-01M41DM7X | conservation, tampered, suspend-blind, na-counts rows |
| EV-12 / 18 / 19 reference cases and boundary rows | 11.1 / 11.2 tables |
| EV-14, EV-15 | 11.3 |
| EV-20, EVU-1..8, EVX-6, EVX-7 | 11.4 |

Testing Strategy union: D0 hygiene (ruff, types, `simplify:` markers); pure-function boundary and property tests (this section); mutation (`tests/mutations/*.json` for the three modules and the section); golden for intervals; browser ring for axe and layout; slow ring for the two coverage simulations (ADR-0020). Not triggered: concurrency, I/O, migration, security-negative beyond section 8.

## 12. Telemetry

Questions an operator asks, with the emitting source (caller side, because the modules are pure; a caller that omits the event fails `test_*_emits`):

| question | event and fields | emitter |
| --- | --- | --- |
| how long and how big was the analysis | `power.analysed` {properties, input_hash, ms, assumed_count} | X-C `bench campaign power` |
| how long were verdicts, how many resamples | `verdicts.computed` {verdicts, resamples_total, ms, excluded_total, na_total, labels{label: n}} | X-H2 at report write |
| what did a gate find | `gate.evaluated` {tag, items{kind: n}, ms} | X-C at register, X-H2 at ring report |
| did the R-93 reader run | `section.built` {hidden_disagreements: n or "not recorded"} | X-H2 |

Every field degrades to `"not recorded"`, never to 0 (IO). Error codes: `HB-PWR-001`, `HB-USR-002`. No HTTP surface. *assume:* the report writer can append a structured event beside the report (as `html.write` already records timings). Confirm: X-H2 reads `html.write` before building. Breaks if false: the events move to the run ledger writer.

## 13. Flagged risks and residual unknowns

| id | risk | disposition |
| --- | --- | --- |
| R-H1 | A zero-variance sample gives a zero-width interval, so three identical pairs read `better` or `no difference`. W0 refused label changes from NA, and the spec fixes the rule order, so no rule is added | shown as `n <pairs> of <required>`; pinned by a test; the pre-registration `min_pairs` is the control, so X-C should warn when `min_pairs` < the power-required n (suggestion to W1-C) |
| R-H2 | Effect coverage measured 0.936, thin above the 0.93 floor (percentile bootstrap under-covers at n = 53) | the seed 20261003 was fixed before the run; if a build moves coverage below 0.93 it is a finding about the interval method (upgrade: BCa or studentised), never a re-seed |
| R-H3 | the `None` state of the R-93 line goes beyond the ruling's text | flagged to the Owner through the Gate; reversible |
| R-H4 | `holm` is mapped to the Bonferroni level | decision request `req-01M41EPSB7E91C4APYT1QGN3FV` (recommended option A, provisional) |
| R-H5 | verdict compute cost at m = 45 | measured, section 2 trigger |
| R-H6 | the EV-11 exception needs `expected_na`, the sizing needs `slots` and `planned_reps_per_task` | seam `req-01M41EX52AX93PQS1FHYCSA0YG`, provisional |
| R-H7 | `views.cell_arm` is not yet on main | `_arm(cell)` helper, fallback `cell.pack` |
| R-H8 | Python 3.12 here, 3.14.6 in ADR-0020's spike; the `random` stream stability is an existing assumption (`stats.py:34`) | the golden test is the detector |

## 14. Change surfaces (E7) and requests

Store (`power/<hash>.json`, `prereg/<hash>.json`; X-C) -> model (`power.py`, `verdicts.py`, `gates.py`) -> service (`campaign.read`, X-E readers, `cli.py` register check in X-C) -> projection/wire (`PowerResult` and `Verdict` as JSON for `bench campaign power` and the completion summary; `Pair` builder `collect`) -> client type (none) -> UI (`report/campaign_section.py`, the `html.py` hook, the egress section shape, `report.js` untouched) -> compute readers (registration refusal, ring report, EV-20 header, completion summary). Also: `tests/mutations/{power,verdicts,gates,campaign_section}.json`; the G3 lint set (X-D); `docs/docs-index.js`.

| request | id | status |
| --- | --- | --- |
| `seed_for` 60 bits | `req-01M41EPKRBCVQ28MS96CHNTDRZ` | granted in W0 rev 3 |
| `pilot` unbiased list | `req-01M41EPKVYZQ9NH97HEJR7M5PY` | granted in W0 rev 3 (kind named `suspend-detector-blind`) |
| `expected_na`, `slots`, `planned_reps_per_task`, `pairing_unit` values | `req-01M41EX52AX93PQS1FHYCSA0YG` | open; provisional |
| `holm` semantics (decision) | `req-01M41EPSB7E91C4APYT1QGN3FV` | open; recommendation A |

Hub files: `report/html.py` (X-H2 in E1, W0 §13). This design edits none.

## 15. Conformance notes

Self-check against the definition of done: data model first (yes, no aggregate by design); E7 list (section 14); phasing (E1, demo shape named); spikes (section 3.4); patterns (section 4); ladder climbed with three `simplify:` markers; failure modes (7); STRIDE (8); privacy negative (9); UI (10; `DESIGN.md` is the existing report design language, unchanged, so no new tokens and no re-lint); test plan with the union (11); telemetry (12). **Unmet:** the rollups `docs/security/threat-model.md` and `privacy-review.md` are not refreshed (they are not files this slice owns). The HB-CHK-002 reason text and `HB-CELL-107` for BND-A rest on marked assumptions.

## Status & next action

| | |
|---|---|
| **Completed** | design of X-H1 and the X-H2 section 3 view, with spikes and the test plan |
| **Remaining** | gate reviewers; answers to the open seam and decision; W1-H follow-up for findings |
| **Best next action** | RV-TA, RV-PAT, RV-SIM review; then `/implement` X-H1 (skeleton commit, red tests, green) |

## Gate record

`GATE w1-h-power-verdicts · pending · RV-TA (hard veto), RV-PAT, RV-SIM (soft veto)`
