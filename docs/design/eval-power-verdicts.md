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
  rules as boundary tables with named mutants, nine pilot gate kinds each with a red fixture, the EV-8 admission
  function, the R-93 three-state warning line, the R-96 level rule (holm is sized like Bonferroni, disclosed), and
  the NA-never-dropped rule. Revision 2 applies the three gate reviews (all PASS WITH CONDITIONS). Reports measured
  spikes, two defects found in W0 text (seed width, resolved in rev 3) and the residual risks.
---

# Design: power, verdicts, dominance, ring gates and report section 3

- **Status:** Revision 2 (gate passed: RV-TA, RV-PAT, RV-SIM all PASS WITH CONDITIONS; findings applied in the Review disposition table at the end).
- **Spec / architecture:** `docs/specs/enterprise-evaluation.md` EV-8, EV-12, EV-14, EV-15, EV-18, EV-19, EV-20, EVX-6, EVX-7, EVU-1..EVU-8 · ADR-0020 and its Amendment 1 · `docs/design/eval-seam-contracts.md` rev 4 sections 3, 6, 7, 8, 13 (merged from main at `109f8c0b`; rev 4 answers this slice's seam `req-01M41EX52AX93PQS1FHYCSA0YG`, W1-C OI-1/OI-2/OI-3, and R-96).
- **Delivery phase:** build in E1 (X-H1: `power.py`, `verdicts.py`, `gates.py`; X-H2: `report/campaign_section.py` and the `report/html.py` hook). E1 demo shape (R-89): one harness (`cc-opus`), k = 3, `min_pairs` <= 3, expected label `inconclusive (underpowered)`.
- **Author / date:** `w1h-power-e1e4` (Claude Sonnet 5.5, `claude-sonnet-5-5`), 2026-10-03. Revision 2: `w1h-power-r2-e1e4`, same model, 2026-10-03.

## 1. Responsibility and boundaries

One responsibility: turn recorded inputs into **derived** answers, with no I/O in the three modules (ADR-0020 §5, W0 §8).

| unit | does | does not |
| --- | --- | --- |
| `power.py` | sizes pairs per (property, harness, comparison); solves the MDE back; costs the grid | read a run, pick a plan, store anything |
| `verdicts.py` | forms pairs and exclusions from `CellView`s; computes label, intervals, token ratio, statement | decide eligibility (X-D/X-C) or admission |
| `gates.py` | lists failing items for a pilot run; says `regression signal` or not for a regression ring; decides task admission (EV-8, `admission`) | read files (X-E passes lists in); record an admission (X-C's `admit` does) |
| `report/campaign_section.py` (X-H2) | renders the verdict rows, the exclusions block, the NA counts and the R-93 line | compute any statistic |

Crossings: in from `campaign.read` (X-C), `readiness.hidden_test_disagreements`, `readiness.unbiased_failures` and `readiness.expected_na` (X-E), `views.CellView`, `views.cell_arm` (X-A1, G1). Out to X-C's registration check and `register` preview (gate items, `alpha_per_test`, `level_rule`), X-C's `admit` (the `admission` output, recorded as `admission.decided` rows), the completion summary and the report.

## 2. Data model (settled first)

**Bounded context:** evaluation analysis. **Ubiquitous language:** *pair* (one task, one repetition, both arms recorded), *stratum* (a task), *effect*, *interval*, *MDE*, *label*, *verdict*, *statement*, *gate item*, *NA count*.

**Aggregates:** none. Every output is a value object recomputed on read (DM7, ADR-0006 *Derived, never stored*). The campaign stores only inputs and decisions (`power/<input_hash>.json`, `prereg/<hash>.json`, W0 §6; writer X-C, compute reader this slice). The one invariant this slice protects is a function property, not a transaction: **the label is a total function of `(n_pairs, min_pairs, lo, hi, mde)` through one function, `label_for`**, and no other code path emits a label.

**Durable representation:** no new store, so no new ADR (DM13). ADR-0020 stays the decision. Its *Amendment 1* (R-96 ruling 3, on main) records `seed_for` for the plan seed and the `holm` level at `alpha/m`; this design codes to the amended text.

**Grain, additivity, history (per output):**

| output | one row is exactly one | additivity | history rule |
| --- | --- | --- | --- |
| `Pair` | (task, rep) of one (harness, comparison) in which both arms recorded the primary metric | `n_pairs` additive across tasks | none; derived |
| `Verdict` | (property, harness, comparison) of one campaign grid, at one set of attached runs | `n_pairs`, `excluded` count additive; **effect, interval, ratios non-additive** (never average two verdicts' effects; a ratio is recomputed from the sums) | Type-2 by recomputation: a re-grade changes inputs, so a verdict is never edited, it is recomputed and names the fixes it was computed under (EV-16) |
| `PowerResult.required_pairs` row | (harness, comparison) of one property in one input hash | `n` is not additive across harnesses (each harness is its own test) | input hash is the version |
| `cells`, `hours`, `tokens` | one property in one input hash | additive across properties (sum over five properties = the 2,430 / 4,230 / 5,220 cells in the spec) | same |
| `GateItem` | (kind, ident) in one ring run | counts additive | derived |

**Derive-don't-store decisions:** `alpha_per_test`, `level_rule`, `resamples`, `reps_per_task`, the MDE back-solve, the token ratio and `statement` are computed, never fields in a stored file. The prereg stores `correction.method` as the operator wrote it; a registered `holm` is read as `holm` and the effective rule is the derived `level_rule` (R-96 condition 3). **No verdict cache in E1.** *simplify:* verdicts recomputed on every report write. Ceiling: measured 0.35 s for n = 115 at 40,000 resamples (spike S3); a worst-case 90 verdicts at 18,000 resamples is about 40 s (Inferred from the spike), paid once at report-write, not at page load. Upgrade trigger: `verdicts_ms` (telemetry, section 12) above 60,000 for one report write. The upgrade is a labelled rebuildable cache `verdicts/<input_hash>.json` with an equality test against the derivation.

**Writer and compute reader for every persisted field this slice touches:** `bench-power-inputs/1` (writer X-C, reader `power.analyse`); `bench-prereg/1` (writer X-C, reader `verdicts`, `gates`); the `Score` rows and `property.json` evidence (writer X-F, readers `views`, `readiness`, `gates`). This slice writes no field.

## 3. Contracts

### 3.1 W0 text relied on (quoted)

- §8 (rev 4): "verdict sorts pairs by (task, rep) before any use, so input order never changes a resample"; "`seed_for` ... `int(sha256(...).hexdigest()[:15], 16)`"; `pilot(view, hidden_test_disagreements, unbiased_failures, *, expected_na: Mapping[str, frozenset[str]] = EMPTY)`; "`PowerResult` ... + alpha_per_test, level_rule, reachable_mde. alpha_per_test and level_rule come from ONE table in power.py keyed by correction.method (bonferroni and holm: alpha/m; none: alpha); the Verdict carries both"; "`admission(view, tasks, off_arm='off') -> Mapping[str, tuple[int, str]]` ... 1 in every cell -> `(0, "saturated")`; 0 in every cell -> `(0, "floor")`, by exact equality (R-85); otherwise `(1, "")`. A task with an NA primary in any off-arm cell raises HB-USR-002"; `expected_na` source is "X-E's `readiness.expected_na(root, tasks)`"; "kinds ... `check-tampered` and `suspend-detector-blind`".
- §6 (rev 4, OI-2): the grid a pre-registration names is the final power inputs; no prereg field. OI-1: ring eligibility is X-C's reader, not this slice's.
- §3 rev 3: "An NA cell appears in `Verdict.excluded` with its reason ... **Refused:** changing a verdict's label because of an NA count. That rule is ADR-0020's and would need the Owner." This design therefore never lets an NA count touch `label_for`.
- §7 condition 3 (R-93): the warning line is "in report section 3, beside ADR-0020's exclusions, and **not** in the EV-20 header. It changes no verdict, no exclusion and no eligibility." R-96 ruling 2, inside R-93: three states (list non-empty -> the warning with count and ids; empty list -> no element; `None` -> the `hidden-test-agreement-not-recorded` element with the reason, no count, no ids); the two elements never share a `data-kind`; the not-recorded one never carries `data-count`.
- R-96 ruling 1, binding: `holm` is sized and levelled at `alpha/m` (Holm's first step), "not a silent alias": `alpha_per_test` is the one definition, `level_rule` is `"alpha/m (Bonferroni; Holm's first step)"` for `holm`, shown in the power output, the verdict view and the section-3 legend. No step-down runs.
- ADR-0020 §2: "not enough recorded pairs -> `inconclusive (not recorded)`; lower > 0 -> `better`; upper < 0 -> `worse`; interval strictly inside (-MDE, +MDE) -> `no difference >= MDE`; else `inconclusive (underpowered)`." §3: "`A dominates B` iff A vs B is `better` or `no difference >= MDE` **and** the ratio's upper bound < 1. No other rule emits the word."

### 3.2 Exposed

```python
# power.py  (grade class; stdlib: statistics.NormalDist, math, decimal)
PAIRING = ("unpaired", "task-harness-rep")           # the only accepted pairing_unit values (W0 rev 4, req-...YG 3)
LEVEL_RULES = {                                      # THE one table (R-96 c1; W0 rev 4 section 8): method -> (divisor, level_rule)
    "bonferroni": (True,  "alpha/m (Bonferroni)"),
    "holm":       (True,  "alpha/m (Bonferroni; Holm's first step)"),   # R-96's exact sentence; no step-down runs
    "none":       (False, "alpha (no correction)"),
}
def level_for(method: str, alpha: Decimal, m: int) -> tuple[Decimal, str]   # (alpha_per_test, level_rule); the only reader of LEVEL_RULES
def n_unpaired_exact(p0: float, p1: float, alpha: float, power: float) -> float     # Fleiss, Levin & Paik, no continuity correction
def n_paired_exact(psi: float, delta: float, alpha: float, power: float) -> float   # Connor 1987
def _snap(x: float) -> int                                                           # ceil(x - 1e-9); one line, tested (F2)
def mde_for(n: int, sizer: Callable[[float], float], lo: float = 0.001, hi: float = 0.999) -> float  # bisection, 60 steps
def analyse(inputs: Mapping) -> Mapping[str, PowerResult]        # W0 §8 rev 4; HB-PWR-001 names the field
# PowerResult adds (W0 rev 4, additive): alpha_per_test, level_rule, reachable_mde (None unless planned_reps_per_task given)
# inputs add (W0 rev 4): slots (int >= 1, required), planned_reps_per_task (int >= 1, optional). sd and rep_spread are validated, not echoed (E1: binary primary)

# verdicts.py  (grade class)
def alpha_per_test(prereg) -> Decimal            # reads power.level_for(prereg.correction.method, ...)[0]; defines nothing itself
def resamples_for(alpha_per_test: Decimal) -> int   # max(2000, ceil(20 / alpha_per_test)); > 100000 -> HB-USR-002
def seed_for(...) -> int                         # W0 §8 rev 3
def label_for(n_pairs: int, min_pairs: int, lo: Decimal, hi: Decimal, mde: Decimal) -> VerdictLabel
def statement_for(label, treat: str, ref: str, ratio: Ratio | None) -> str | None
@dataclass(frozen=True) class VerdictSpec:       # W0 §8 allows this narrowing; meanings unchanged
    prop: str; harness: str; comparison: tuple[str, str]; tasks: tuple[str, ...]   # the ADMITTED tasks of the property (X-C's admission.decided rows with admitted = 1)
    mde: Decimal; method: str; alpha_per_test: Decimal; level_rule: str; min_pairs: int; seed: int; resamples: int; required_pairs: int | None
    # __post_init__: min_pairs < 1 -> BenchError("HB-USR-002") (PAT 5)
def collect(cells, spec) -> tuple[list[Pair], list[tuple[str, str]], dict[str, int]]
    # E1: the primary is property_check_pass, an int 0/1 (W0 §2); any other value -> HB-USR-002. No `primary` parameter (SIM 8)
def verdict(spec, pairs, excluded, na_counts) -> Verdict   # verdict(prop, harness, ...) of W0 is spec + these three
# Verdict adds (additive): method (as registered), level (= 1 - alpha_per_test), alpha_per_test, level_rule, mde, resamples, seed, reason (NOT_RECORDED text), pairs_by_task, na_counts {reason: n}, required_pairs

# gates.py  (grade class)
class GateKind(StrEnum): CELL_LOST="cell-lost"; BND_A="bnd-a-loss"; GRADER_ERROR="grader-error";
    METRIC_UNRECORDED="metric-not-recorded"; PRIMARY_UNRECORDED="primary-not-recorded"; TASK_NO_PRIMARY="task-no-primary";
    CHECK_TAMPERED="check-tampered"; SUSPEND_BLIND="suspend-detector-blind"; HIDDEN_NONDETERMINISTIC="hidden-tests-nondeterministic"    # nine
def ring_items(view, expected_na) -> list[GateItem]      # the cell-level items, shared by pilot and the regression ring's "withheld"
def pilot(view, hidden_test_disagreements, unbiased_failures, *, expected_na=EMPTY) -> list[GateItem]   # W0 rev 4 arity; sorted by (kind, ident)
def pack_regression(view, mde) -> Mapping[str, str]
def admission(view, tasks, off_arm="off") -> Mapping[str, tuple[int, str]]   # EV-8; X-H1's (W0 rev 4 section 8, W1-C OI-3); X-C's `admit` records it
```

All rev 4 items above are **granted** in W0 rev 4 (`req-01M41EX52AX93PQS1FHYCSA0YG` 1 to 3; RV-PAT W1-H 3). X-C's `pilot pass` passes `expected_na` from X-E's `readiness.expected_na(root, tasks)` and turns a failed reader into `None`.

### 3.3 Consumed, with confidence

| contract | source | confidence |
| --- | --- | --- |
| `stats.rng(seed, key)` accepts any int; `Params` refuses `seed >= 2**63` | `stats.py:37-41`, `:58-59` | Verified (read, and run in spike S2) |
| `stats._percentile` is `j = B*25//1000` (95% only) and private; the existing `paired_delta` resamples tasks as well as repetitions | `stats.py:143-148`, `:157-208` | Verified (read). So neither is reusable: a new corrected-level, task-stratified routine is needed (section 5) |
| `CellView` fields `outcome`, `cause`, `code`, `validity`, `wall_ms`, `tokens`, `scores: dict[str, Measure]` with `.value`/`.reason` | `views.py:110-136` | Verified |
| `views.sum_tokens` returns `None`, never 0, when not recorded | `views.py:268-276` | Verified |
| A grader exception writes NA with reason starting `HB-GRD-003` | `grade/runner.py:357` | Verified |
| `Cause` attributions: `infrastructure` and `benchmark` invalidate | `errors.py:16-45` | Verified |
| BND-A cells carry code `HB-CELL-107` (protocol) | `docs/lessons/defect-classes.md:627-634` (instance) | Verified for the instance; *assume:* every BND-A loss is `HB-CELL-107`. Confirm: the pilot report of the first real ring lists no cell lost to a size bound under another code. Breaks if false: that cell reports as `cell-lost`, still a gate item, only the kind name is wrong |
| `views.cell_arm(cell)` | W0 §10 G1 (X-A1 delivers) | Provisional (W1-A). Fallback: `cell.pack` until X-A1 lands, behind one helper `_arm(cell)` |
| HB-CHK-002 NA reason text is `invalid (check tampered)` | W0 §3 outcome table row 3 | Verified in W0 text; *assume:* it survives into `Measure.reason` unchanged. Confirm: X-F's `test_check_tampered_reason_reaches_the_view` (named in section 11). Breaks if false: tampered cells fall to `primary-not-recorded` |
| `readiness.expected_na(root, tasks) -> Mapping[str, frozenset[str]]` (metric ids whose `expected.reference` is `{na: ...}`); `gates.admission` is X-H1's | W0 rev 4 section 8 | Verified in W0 rev 4 text; the function is X-E's and not yet built (the call site is X-C's) |

### 3.4 Spikes run (2026-10-03, Python 3.12.10 locally; ADR-0020 ran 3.14.6)

| id | question | result |
| --- | --- | --- |
| S1 | Do 93 / 53 / 115 reproduce, and what does a wrong z give? | 92.99884 -> 93; 52.52075 -> 53; 114.24879 -> 115 (`NormalDist().inv_cdf`). One-sided z (the seeded-wrong variant): 73.13 / 41.13 / 103.11, so it differs by far more than 1 [Verified] |
| S1b | Does the MDE solve back? | n = 93, p0 = 0.5: 0.199999. n = 53, psi = 0.28: 0.19913. n = 115 (alpha/45): 0.19937. All within 0.005 of 0.20 [Verified] |
| S1c | Does ceil vs round matter? | 114.2488 rounds to 114 but must ceil to 115. 114 is inside the spec's +-1, so a tolerance test would not catch a `round` mutant. **The tests pin the integers exactly** (stricter than EV-12) [Verified] |
| S2 | Is W0 rev 2's `seed_for` a legal `Params` seed? | No: 49.9% of 100,000 seeds were >= 2**63 and `Params` raised HB-USR-002. Fixed in W0 rev 3 (`[:15]`). Fixture row: prereg hash `e1746a8b...effc`, `[:16]` = 14055141998388353605 (illegal), `[:15]` = 878446374899272100 (legal) [Verified] |
| S3 | Cost of the stratified bootstrap | n = 115, B = 2,000: 0.02 s; B = 40,000: 0.35 s; int-draw loop, `stats.rng` stream [Verified, this host] |
| S4 | Coverage, effect, 1,000 datasets, n = 53 (27 + 26 pairs), true effect 0.20, generator `random.Random(20261003)`, B = 2,000 | **0.936** (in 0.93-0.97; standard error about 0.007 at 1,000 datasets, so about one sigma above the floor; the test design in 11.2 answers this, TA 5) [Verified; the script is not committed, X-H1 commits it as the test body] |
| S5 | Coverage, token ratio, same seed, lognormal tokens, true ratio E[T]/E[C] | **0.948** [Verified] |
| S6 | 400 pairs (two tasks of 200), true diff 0.20 vs the normal-approximation interval | normal [0.16366, 0.26634]; bootstrap B = 2,000 [0.1625, 0.2650]; B = 10,000 [0.1650, 0.2675]. Gaps 0.0012 / 0.0013 (EV-18 tolerance 0.01) [Verified] |
| S7 | Hours table | 2,430 cells -> 44.02 h; 4,230 -> 76.63 h; 5,220 -> 94.57 h at 130.44 s per cell and 2 slots (spec: about 45 / 77 / 95) [Verified] |

## 4. Patterns (each past the Patterns Expert and the Simplifier)

| pattern | where | why the smallest correct idiom | rejected alternative |
| --- | --- | --- | --- |
| Pure functions over frozen value objects (Value Object; LOA functional core) | all three modules | ADR-0020 §5; reproducible from inputs and seed | a `Verdict` service with a cache: not needed at measured cost |
| Decision table, one function (an ordered-rules function; not the GoF Specification, which is a composable predicate) | `label_for`, `statement_for`, `_classify_cell`, `level_for` (one table keyed by method) | the four rule orders each live once, so a mutant has one place to land and adjacent rules are separately killable | rules inlined in `verdict`: the sweep "no other path emits a label" would be unenforceable |
| Parameter Object (frozen) | `VerdictSpec` | W0 §8 allows it by narrowing; 8 scalar parameters become one | keep eight positional parameters: error-prone ordering of `Decimal`s |
| Table-of-checks (closed enum + one predicate per kind) | `gates.py` | each EV-14 bullet is one predicate; `GateKind` is closed and tested for coverage | a rule engine: YAGNI |
| Bootstrap with a keyed stream per quantity (existing idiom, `stats.rng`) | `verdicts._boot` | the repo's own T-S3 property: adding a quantity does not move another | `random` global state; a new RNG |
| Stdlib-only (`NormalDist`, `math`, `decimal`) | `power.py` | ADR-0020; spike S1 | `scipy`/`statsmodels` (rejected by ADR-0020) |

Ladder climbed: YAGNI cuts the graded-metric formula (`sd` and `rep_spread` are validated and ignored; no `descriptive` echo), the graded-primary path in `collect` (E1 accepts 0 or 1 only), the pooled-harness verdict, the verdict cache and a Holm step-down (R-96 refused it). Reuse: `stats.rng`, `Decimal` context discipline, `views.sum_tokens`, `errors.Cause`. New code only where the stdlib and repo have nothing (corrected-level stratified percentile).

## 5. Algorithms

**Power (`analyse`).** For each property: validate (HB-PWR-001 names the field; `sd` and `rep_spread`, when present, must be numbers >= 0). `(alpha_pt, level_rule) = level_for(method, alpha, m)`: `alpha/m` for `bonferroni` and `holm`, `alpha` for `none`, from the one `LEVEL_RULES` table (R-96: `holm` is sized like Bonferroni, never a separate branch, and its `level_rule` says so). `level_for` is the only reader of the table; `verdicts.alpha_per_test` calls it, so the sizing and the verdict level cannot diverge. `unpaired`: `n_unpaired_exact(p0, p0 + mde, ...)`, `p0 = control_rate` or 0.5 when `"assumed"` (listed in `assumed`). `task-harness-rep`: `n_paired_exact(psi, mde, ...)`, with `psi = discordance`, or, when absent or `"assumed"`, `psi = p0(1-p1) + p1(1-p0)` under independence (0.5 at p0 = 0.5; listed in `assumed`). `n = _snap(exact)`, where `_snap(x) = ceil(x - 1e-9)` is a one-line helper tested at its edge (*simplify:* the epsilon snaps float noise on an exact integer; ceiling: none seen in S1; upgrade trigger: a reference that lands within 1e-9 of an integer). `reps_per_task = ceil(n / len(tasks))`. `cells = len(tasks) * len(harnesses) * len(arms) * reps_per_task` (`arms` = distinct arms over `comparisons`; calibration cells excluded and stated). `hours = cells * mean_wall_per_cell_s / slots / 3600`. `tokens = cells * mean_tokens_per_cell`. `mde` in the result is `mde_for(n)`, the MDE the integer `n` actually detects; `reachable_mde = mde_for(len(tasks)*planned_reps_per_task)` when given (EV-12 last bullet; the plan shows it instead of the target). `sd` and `rep_spread` are validated and **not** used for sizing and not echoed in E1 (a binary primary). Upgrade trigger: a graded primary enters scope (DR-E5). `PowerResult` carries `alpha_per_test` and `level_rule`.

**Verdict.** `pairs` sorted by `(task, rep)`; a duplicate `(task, rep)` is refused (HB-USR-002), because it would double count. In E1 the primary is `property_check_pass`, an int 0 or 1 (W0 section 2); a `Pair` value that is not `Decimal(0)` or `Decimal(1)` is refused (HB-USR-002), so no scaling is needed. Upgrade trigger: a graded primary enters a verdict (then a scale and an off-scale refusal return). Strata are `spec.tasks`. **A stratum with no pairs makes the label `inconclusive (not recorded)` with the reason `task <id>: 0 pairs recorded`**, because dropping it would silently change the estimand from "both tasks weighted equally" to one task. Per resample: for each stratum in task order draw `w` indexes with `int(rng.random() * w)` (the repo's `_draw` contract), take the stratum mean; the statistic is the mean of stratum means, held as an exact integer over the common denominator `lcm(w_t) * k` (k strata), so no float decides a boundary. Endpoints: the sorted statistics at index `floor(B * alpha_pt / 2)` and `B - 1 - floor(...)`, converted to `Decimal` with the module context. Streams: `stats.rng(seed, "effect")`, `"ratio"`, `f"task|{id}"`. The token ratio is `sum(treat_tokens)/sum(ref_tokens)` over resampled pairs at the fixed 95% level (EV-19), `None` when the denominator is 0 or any token count is unrecorded in the pair set; wall ratio is the point value. Percentile intervals are invariant to the log transform, so the "log scale" is a display choice only.

**Rules** (`label_for`, in this order, one function):

```
1. n_pairs < min_pairs                      -> NOT_RECORDED
2. lo > 0                                   -> BETTER
3. hi < 0                                   -> WORSE
4. -mde < lo and hi < mde                   -> NO_DIFFERENCE
5. otherwise                                -> UNDERPOWERED
```

`both_tasks` is `True` iff the label is `BETTER` (`WORSE`) and every task's own interval has `lo > 0` (`hi < 0`); `False` if a task disagrees or has fewer than 2 pairs; `None` for other labels. **No NA count and no `level_rule` ever enters `label_for`** (W0 section 3). `statement_for`: `BETTER` or `NO_DIFFERENCE` with ratio `hi < 1` -> `"<treat> dominates <ref>"`; else `BETTER` -> `"better at ×<r> tokens"` (any ratio, with its interval shown by the section); else `None`; `None` too when the ratio is not recorded.

**Collecting pairs (`collect`).** For the cells of one `(harness, ref arm, treat arm)` in scope, every cell lands in **exactly one** place: a pair half, or `excluded` with `(cell_id, reason)`. Order of reasons (first match): `calibration or non-admitted task`, `invalid (<attribution>)`, `<outcome label> (<cause>)` for blocked, failed, timed_out without the primary, stopped, `<NA reason of the primary>` (this is where `invalid (check tampered)` and `HB-GRD-003 ...` land, and `na_counts[reason] += 1`), `pair partner not recorded (<partner id or absent>)`. Conservation: `2 * len(pairs) + len(excluded) == cells in scope` (hypothesis test, section 11). `na_counts` stays derived in this one place (the NA-reason branch above), and the conservation test also asserts `sum(na_counts.values())` equals the number of excluded entries that came through that branch (SIM 9; W0 section 8 fixes `excluded` as `(cell_id, reason)` pairs, so no tag is added to them). `spec.tasks` are the **admitted** tasks (the `admission.decided` rows with `admitted = 1` that X-C's `campaign.read` returns); a cell of a non-admitted task is excluded with `calibration or non-admitted task`. Power sizes on the **pre-admission** tasks of the inputs file (`properties.<p>.tasks`), because the grid is the final power inputs (W0 rev 4 section 6, OI-2); the two sets can differ after `admit` (Inferred ordering; W1-C OI-3; a note, not a field).

**Gates.** `ring_items(view, expected_na)`, per cell, first match wins: `bnd-a-loss` (`code == "HB-CELL-107"`), then `cell-lost` (outcome `failed`, any `blocked`, or `Cause` attribution `infrastructure` or `benchmark`; the cause and code go in `detail`; SIM 3 merged the former `cell-failed` and `infrastructure-cell`, which are one EV-14 bullet with one operator action). Only `bnd-a-loss` versus `cell-lost` can differ on one cell, and only where code is 107 and outcome is `failed` (TA 4). Per cell: `grader-error` (any score reason starts `HB-GRD-003`); `check-tampered` (primary reason is `invalid (check tampered)`); `primary-not-recorded` (primary NA for any other reason and not already tampered or grader-error: one item per cell). Per (task, metric): `metric-not-recorded` when a metric with a row is NA in every cell of the task and not in `expected_na[task]` (detail names the reasons). Per task: `task-no-primary` when no cell of the task has a `property_check_pass` row at all (the grid-4 G2 shape). `pilot = ring_items + hidden-tests-nondeterministic (per id) + suspend-detector-blind (per id)`, sorted by `(kind, ident)`, unique. `admission(view, tasks, off_arm)` follows W0 rev 4 section 8 as written: per task, the `off_arm` cells' `property_check_pass`; all 1 -> `(0, "saturated")`; all 0 -> `(0, "floor")`, by exact int equality (R-85); otherwise `(1, "")`; an NA primary in any off-arm cell raises `BenchError("HB-USR-002")`. *assume:* a task with no `off_arm` cell also raises HB-USR-002 (nothing to decide on). Confirm: X-C's `admit` pre-check, W1-C section 5. Breaks if false: such a task is admitted by the `otherwise` branch with no data. *assume:* the pilot's tasks are property tasks, so the primary id is the constant `property_check_pass` (W0 §2 SIM 5). Confirm: readiness checks it. Breaks if false: a non-property task reports `task-no-primary`. `pack_regression`: per property, effect = candidate minus incumbent; `"regression signal"` iff the 95% interval has `hi < 0`; else `f"no regression detected at {mde}"`; if an arm is absent the value is `"Result withheld: ring is missing <arm>."`. Seed `seed_for(ring_hash, prop, "ring", (incumbent, candidate))`. *simplify:* fixed 95% uncorrected. Ceiling: one comparison per property per ring. Upgrade trigger: a ring with more than one candidate.

## 6. Report section 3 (X-H2; the E1 shape)

Section id `property-verdicts` for a comparison-grid report, `regression-check` for a ring report, inserted as the third section (after `validity`, before `leaderboard`). `html.render` gains `campaign_obj=None`; with `None` the section is absent and the page is unchanged (EVU-4; `tests/test_report_builder.py:165` pins the id list).

Blocks, in DOM order: campaign block (sub-block of section 1 per spec; not rebuilt here), legend, **exclusions block**, verdict table, dominance lines, exploratory note.

**Legend and the level rule (R-96).** The legend prints, beside the interval level, `Interval level: <1 - alpha_per_test> (<level_rule>)`, e.g. `Interval level: 0.9989 (alpha/m (Bonferroni; Holm's first step))` when the registered method is `holm` (alpha 0.05, m 45), so no reader believes a step-down ran. The legend element carries `data-method` (as registered), `data-alpha-per-test` and `data-level-rule`. Each verdict cell's tooltip repeats the level and the rule (the R row of section 8). The legend text comes from `Verdict.level_rule`; the section computes none of it. X-C's `register` preview prints the same two values from the same `LEVEL_RULES` table before the hash is taken (W0 rev 4 section 8).

**Exclusions block (R-93).** One line `excluded <n> cells in total` with the list disclosure (id, arm, cause) that EV-18 and US-43 require; then, immediately after it, the NA count line `not recorded by reason: invalid (check tampered) 1; ...` (rev 3 obligation); then the warning line, rendered **only when the count is above 0**:

```html
<p class="warn" data-kind="hidden-test-disagreement" data-count="2">Hidden tests disagreed with pass@1 in 2 cells: C-014, C-031.
These cells' hidden-test results are not deterministic. No verdict, exclusion or eligibility changed.</p>
```

State table for this line: list non-empty -> the element, with the count and ids; empty list -> **no element** (DOM count 0); `None` (the X-E reader failed or was not run) -> `<p class="warn" data-kind="hidden-test-agreement-not-recorded">Hidden-test agreement not recorded: <reason>.</p>`, with no `data-count` and no ids. The third state is **R-93 read with IO, ruled in R-96 ruling 2** (a failed reader is never shown as "no disagreement"). Rules: the two elements never share a `data-kind`; the not-recorded one never carries `data-count` and the disagreement element is then absent; with no campaign (EVU-4) neither element exists; neither element is in the EV-20 header; `section.built` records `hidden_disagreements: "not recorded"` for `None`. The count and ids come only from the `Sequence[str]` argument the caller reads from `readiness.hidden_test_disagreements`; the section computes nothing.

**Verdict cell** follows the UI spec's eight-part order. Additions from this design: part 7 reads `n <pairs> of <required>` when `required_pairs` is known (the honest companion to a small-n label, R-H1); part 8 is `excluded <n>` plus the NA counts by reason. Copy strings are the UI spec's table, produced from `Verdict` fields. `data-interval-lo`, `data-interval-hi`, `data-mde` on effect marks; the ratio bar carries the lo/hi only. The ring section never prints `better`, `worse` or `dominates`.

**Single source of the word `dominates`.** `statement` is the only origin. The section prints `statement` and appends context. The empty state `No arm dominates another.` is the one literal allowed in the section (sweep S-2, section 11).

## 7. Failure-mode analysis

| # | mode (category) | disposition | telemetry / test |
| --- | --- | --- | --- |
| F1 | invalid power input: alpha, power, mde outside (0,1); m < 1; unknown method or pairing; `psi < mde^2` (Connor's root would be imaginary); missing tasks (input) | **prevent**: HB-PWR-001 names the field | `test_power_inputs_each_invalid_field_is_named` |
| F2 | float noise lands a size on an integer boundary (state) | **mitigate**: `_snap(x) = ceil(x - 1e-9)`, *simplify:* above | `test_snap_at_the_integer_edge` (11.1) |
| F3 | W0's old `seed_for` >= 2**63 (input) | **prevent**: rev 3 `[:15]`; red row in `test_seed_for_is_a_legal_params_seed` | |
| F4 | input order changes a resample (state) | **prevent**: sort; duplicate key refused | `test_input_order_never_changes_a_verdict` |
| F5 | a stratum has no pairs, silently changing the estimand (state) | **detect**: NOT_RECORDED with reason | `test_empty_stratum_is_not_recorded` |
| F6 | an NA or lost cell dropped without trace (state; seam req-01M41DM7X) | **prevent**: conservation invariant; **detect**: `na_counts`, `excluded`, `check-tampered` gate item | conservation test, tampered fixtures |
| F7 | clock unreadable, suspend undetected (dependency) | **detect**: `suspend-detector-blind` item per cell | `test_gate_suspend_blind_*` |
| F8 | tiny sample gives a zero-width interval and a confident label (state) | **accept with rationale**: `min_pairs` is pre-registered (R-89 allows <= 3 for the demo only); the cell shows `n <pairs> of <required>`; residual R-H1; test pins the behaviour so a change is a conscious one | `test_degenerate_sample_is_labelled_by_rule_not_hidden` |
| F9 | tail too thin for a corrected level (resources) | **prevent**: `resamples_for` gives >= 10 tail draws; > 100,000 refused | `test_resamples_for_tail_depth` |
| F10 | verdict cost grows with m (resources) | **detect**: `verdicts_ms`; *simplify:* trigger in section 2 | `test_verdicts_computed_event_fields` (12) |
| F11 | primary value not 0 or 1 (input) | **prevent**: refused HB-USR-002 (E1: binary primary only) | `test_non_binary_primary_is_refused` |
| F12 | zero ref tokens, unrecorded tokens (input) | **mitigate**: ratio `None`, statement `None`, cell shows `tokens: not recorded`; never 0 | `test_ratio_not_recorded_*` |
| F13 | reader of `hidden_test_disagreements` or `unbiased_failures` fails (dependency) | **mitigate**: `None` is a distinct input; `pilot` raises HB-USR-002 on a `None` list (see note) | `test_pilot_refuses_unread_lists` |
| F14 | coverage test passes by luck of the seed, or fails on a Python stream change (time) | **prevent**: recorded seed chosen before the run; the golden count (936 of 1,000) tells a stream change from a method change; the method claim is a band at N = 4,000 (11.2); a failure is a finding, never a re-seed (R-H2) | `test_coverage_effect_golden`, `test_coverage_effect_band` |
| F15 | two definitions of the same quantity (state) | **prevent**: tokens via `views.sum_tokens`; cause attribution via `errors.Cause`; label via `label_for`; level via `power.level_for` | `test_ratio_not_recorded_*` (fails if tokens are summed raw), the label invariant inside `test_input_order_never_changes_a_verdict`, `test_level_rule_table` |
| F16 | `holm` believed to run a step-down (state) | **prevent**: `level_rule` disclosed in the power output, the verdict view and the legend; one table (R-96) | `test_level_rule_table`, `test_legend_prints_level_rule`, `test_holm_is_sized_like_bonferroni`, `test_holm_verdict_interval_equals_bonferroni` |
| F17 | `min_pairs` below 1 switches off the "not recorded" rule (input) | **prevent**: `VerdictSpec` refuses it (HB-USR-002) | `test_min_pairs_below_one_is_refused` |

Note on F13: a pilot with an unread list must refuse. The pure function takes `Sequence[str]`, so "unread" is X-C's call-site duty; `pilot` rejects `None` with `BenchError("HB-USR-002", ...)` so the failure is loud. No new HB code is reserved: this slice retires none and adds none; it uses `HB-PWR-001` (reserved) and the existing `HB-USR-002`.

## 8. Adversarial analysis (STRIDE-lite)

Trust boundaries: (1) cell outputs and evidence reaching the view (agent-influenced); (2) the inputs file and prereg (operator-authored, content-addressed); (3) the rendered HTML (reader). No personal data (section 9).

| threat | disposition | negative test |
| --- | --- | --- |
| **T** a deliverable turns a measured 0 into NA to hide a failure (W1-F RF-5) | **mitigate**: NA stays in `excluded` with its reason, in `na_counts`, and a `check-tampered` pilot item; the label is not changed by NA (W0 §3, refused) | `test_check_tampered_is_listed_not_dropped` |
| **T** a tampered score row removes a pair to flip a label | **accept** with rationale: the ledger chain and `verify` (X-C) guard rows; this slice shows the excluded list | covered at join |
| **S** a verdict computed from a different run than the one attached | **transfer, named**: X-C attach/freeze (W0 §6) and eligibility (EV-20); the header names the pre-registration hash | X-C tests |
| **R** a reader cannot tell which seed or level a verdict used | **mitigate**: `Verdict.seed`, `resamples`, `level` shown in the cell tooltip | DOM test |
| **R** a reader believes `holm` ran a step-down (R-96) | **mitigate**: the legend and tooltip print `level_rule` | `test_legend_prints_level_rule` |
| **I** report text leaks evidence | **transfer, named**: egress gate (`_publish`, `html.py:2266`) wraps every `<section id>`; the new section uses the same shape `<section id="[a-z0-9-]+">` | `test_section_is_inside_the_egress_gate` |
| **D** crafted input forces a huge bootstrap | **mitigate**: `resamples` capped at 100,000; pairs bounded by the plan | `test_resamples_cap` |
| **E** none identified (no privileged action) | n/a | |
| **Spoof the word `dominates`** by another module | **mitigate**: sweep S-2 | `test_only_verdicts_emits_dominates` |

## 9. Privacy (LINDDUN-lite)

This slice touches no personal data: it handles counts, ids of cells and task ids, and decimal metrics. Explicit negative; no retention or rights path applies.

## 10. UI design (report section 3)

Medium: self-contained HTML over `file://`; WCAG 2.2 AA; archetype B3 (inherited, no deviation). Tokens: the report's existing tokens only; no new colour, size or radius literal. Encodings, copy strings, per-component state set, motion (none) and accessibility are the UI spec's Part C, implemented as written; this design adds only the three items in section 6 (exclusions block with the R-93 line, the NA-by-reason line, `n of required`). Component states exercised by fixtures (EVU-3): campaign block; legend; verdict table (rows, ineligible, empty); verdict cell (each of the five labels, zero recorded pairs, `k of min` recorded); excluded list (0, 1, > 10); dominance line (present, `No arm dominates another.`); exploratory note; regression table (signal, no signal, gate failed, arm missing, no property tasks, first run). axe (EVU-5) and the UIA-12 contrast check run in the browser ring against the same fixtures. `ui-craft-gate.py` runs on the built report with the CD12 floors. HAX/Shape-of-AI: N/A (spec: no AI content).

## 11. Test plan (by node id; red-first)

**Red-first protocol (all groups; revised for TA 3).** Commit 1 adds skeletons with the final signatures that return a value **outside the expected domain**, so no row can pass on a skeleton: `level_for` returns `(Decimal(-1), "unimplemented")`; `analyse` returns rows with `n = -1` and `level_rule = "unimplemented"`; `label_for` returns `None`; `statement_for` returns the string `"unimplemented"`; `verdict` returns the impossible interval `(Decimal(1), Decimal(-1))` (numeric, so a coverage loop fails by value and never by `TypeError`); `collect` returns `([], [("unimplemented", "")], {})`; `pilot` returns `[GateItem("unimplemented", "")]`; `pack_regression` returns `{"": "unimplemented"}`; `admission` returns `{task: (-1, "unimplemented")}`; `campaign_section.build` returns `<section id="unimplemented"></section>`; `html.render` accepts `campaign_obj` and ignores it. Commit 2 adds the tests and every one fails by **assertion** on a value, never on an import or attribute. The column "fails today because" names the skeleton value. Where a test can fail against the repo as it is today, that is stated.

Ring: fast ring unless marked. Hypothesis (a dev dependency, `pyproject.toml:19`) provides the property tests. Mutants are `tests/mutations/{power,verdicts,gates,campaign_section}.json` in the repo's find/replace format; each entry's `tests` lists **parametrize node ids** (`test_label_for_boundary_table[L8]`), never a bare function, because `tools/mutate_check.py` counts a kill only when a named test fails. `tests/test_mutate_check.py` proves each `find` occurs once. **No ring runs `tools/mutate_check.py` today** (RV-TA searched `.github/workflows`, `pyproject.toml` and `tests/conftest.py` on main: no call; Verified by that review). So mutants are the second line, run by hand at X-H1's Proof Pack as `python tools/mutate_check.py tests/mutations/<name>.json`; a row's red-first failure never depends on that run. Wiring the tool into a ring is a request for X-INT, not part of this slice.

### 11.1 `tests/test_power.py`

| node id | pins | tolerance | fails today because | red fixture / guard | real-wiring or independence | mutant (adjacent rules) |
| --- | --- | --- | --- | --- | --- | --- |
| `test_unpaired_reference_93` | p0 .5, p1 .7, .05, .8 -> `n == 93` exact; `n_unpaired_exact` = 92.99884 +- 1e-4 | exact int | skeleton n = -1 | | the test file holds a hand formula with literal z 1.959963984540054 and 0.8416212335729143 | `ceil` -> `round` is invisible at 93; killed by the 115 row. `z two-sided -> one-sided` (73) killed here |
| `test_paired_reference_53` | psi .28, delta .20 -> 53 exact; exact 52.52075 +- 1e-4 | exact | n = -1 | | same literal-z formula | `sqrt(psi - d*d)` -> `sqrt(psi)` gives a different n |
| `test_bonferroni_reference_115` | alpha/45 -> 115 exact; exact 114.24879 +- 1e-4 | exact (EV-12 allows +-1; 114 is inside it, so exact is required to kill `round`) | n = -1 | | literal z for alpha/90 (3.2608, four places, is within 1 of the exact integer; the exact-int assertion is on the module, the literal formula uses +-1) | `ceil` -> `round` (114) killed; `alpha/m` -> `alpha` (53) killed |
| `test_holm_is_sized_like_bonferroni` (R-96 c2, first row) | `holm` m 45 -> 115, same as `bonferroni` | exact | n = -1 | `none` method with m 45 must give 53 | | `holm` mapped to `alpha` (53) fails this row **and** `test_holm_verdict_interval_equals_bonferroni`; `method in (bonferroni, holm)` -> `== bonferroni` gives 53 for holm |
| `test_level_rule_table` (R-96 c1, PAT 1) | `level_for` for the three methods: `bonferroni` -> (alpha/m, `"alpha/m (Bonferroni)"`); `holm` -> (alpha/m, `"alpha/m (Bonferroni; Holm's first step)"`, R-96's sentence verbatim); `none` -> (alpha, `"alpha (no correction)"`); `analyse` for `holm`, m 45 carries `alpha_per_test == Decimal("0.05")/45` and the holm sentence; `verdicts.alpha_per_test(prereg)` equals `level_for(...)[0]` | exact | skeleton `(Decimal(-1), "unimplemented")` | `holm` row asserts the sentence, so a silent alias (no `level_rule`) is red | the same table read by `analyse` and `verdicts` | `holm` row's string replaced by the bonferroni one; `holm` divisor `False`; a second table in `verdicts.py` (alpha_per_test no longer reading `level_for`) |
| `test_alpha_and_power_echo_exactly` | `result.alpha == inputs alpha`, `power == inputs power` (EV-12) | `==` | skeleton returns 0 | | | alpha replaced by `alpha_per_test` |
| `test_mde_solves_back_within_0_005` | MDE of n 93 / 53 / 115 vs 0.20 | 0.005 | skeleton mde 0 | | `mde_for` is checked against the literal-formula `n(delta)` | bisection bounds off (hi 0.5) |
| `test_seeded_wrong_one_sided_variant_fails` | `check_references(power_with(one_sided_z))` **raises AssertionError**; `check_references(real analyse)` passes | -- | the check helper is defined in the test; the fake is a patched `inv_cdf`; the real run passes only once `analyse` is correct | the wrong variant is the red fixture for the reference test | **real-wiring beside the fake**: the same helper on the real `analyse` | |
| `test_assumed_control_rate_is_labelled` | `"assumed"` -> p0 .5, `assumed == ["control_rate"]`; a given rate -> `[]` | exact | `assumed` has the value `["unimplemented"]` | rate given vs not | | label dropped |
| `test_mde_roundtrip_property` (hypothesis) | `n_for(mde_for(n)) <= n` and `n_for(mde_for(n) - 0.005) > n - 2` (pins the bisection bounds) | | n = -1 | | | |
| `test_power_inputs_each_invalid_field_is_named` | table: alpha 0, 1; power 1.2; m 0; method `sidak`; pairing `paired`; psi .03 with mde .2 (psi < mde^2); tasks `[]`; mde 0; `slots` 0 and absent; `planned_reps_per_task` 0; `sd` -1; `rep_spread` -1 -> `BenchError` code `HB-PWR-001`, message names the field | exact | skeleton returns rows, no raise | one row per guard | | each guard line deleted |
| `test_cells_hours_tokens_reference_table` | sum over five properties of `cells` = 2,430 / 4,230 / 5,220 for n 53 / 93 / 115; `hours` 44.02 / 76.63 / 94.57 (`slots` 2) | cells exact; hours +-0.05 (spec "about 45 / 77 / 95") | cells -1 | | | `ceil(n/tasks)` -> `n // tasks` (26 for 53: 2,340) |
| `test_reachable_mde_when_plan_is_short` | planned reps 10 -> `reachable_mde > mde` and equals `mde_for(20)` | 1e-9 | `reachable_mde` is the sentinel `-1` | planned reps absent -> `None` | | `planned_reps_per_task` ignored |
| `test_snap_at_the_integer_edge` (TA 8) | `_snap(93.0000000001) == 93`; `_snap(93.001) == 94`; `_snap(93.0) == 93` | exact | skeleton `_snap` returns -1 | the two edge inputs | | epsilon removed (first row gives 94); epsilon widened to 1e-2 (second row gives 93) |

Dropped on the SIM review (6, 7): the determinism, monotone and JSON round-trip tests and `test_sd_and_rep_spread_do_not_change_n`. Their mutants are killed by the reference, holm and 115 rows or have no code to land on (no `set` is iterated; `descriptive` is gone).

### 11.2 `tests/test_verdicts.py`

**Rule table** `test_label_for_boundary_table` (EV-18; hand-computed; each row a parametrize id; MDE 0.30 unless stated). Renumbered after TA 1 and SIM 1 (old L11 is now L10; old L10, L12, L13 are gone, see the Review disposition):

| id | n, min | lo, hi | expect | distinguishes (mutant) |
| --- | --- | --- | --- | --- |
| L1 | 5, 6 | 0.10, 0.50 | NOT_RECORDED | rule 1 evaluated after rule 2 |
| L2 | 6, 6 | 0.10, 0.50 | BETTER | rule 1 `<` -> `<=` |
| L3 | 6, 6 | 0, 0.50 | UNDERPOWERED | rule 2 `lo > 0` -> `>=` |
| L4 | 6, 6 | -0.50, 0 | UNDERPOWERED | rule 3 `hi < 0` -> `<=` |
| L5 | 6, 6 | -0.50, -0.01 | WORSE | rules 2/3 swapped to `hi > 0` |
| L6 | 6, 6 | 0.05, 0.15 | BETTER (not NO_DIFFERENCE) | rule 4 before rule 2 |
| L7 | 6, 6 | -0.15, -0.05 | WORSE (not NO_DIFFERENCE) | rule 4 before rule 3 |
| L8 | 6, 6 | -0.30, 0.10 | UNDERPOWERED | rule 4 `-mde < lo` -> `<=`; **and** rule 4 `and` -> `or` (under `or`, `hi < mde` is true, giving NO_DIFFERENCE) |
| L9 | 6, 6 | -0.10, 0.30 | UNDERPOWERED | rule 4 `hi < mde` -> `<=`; **and** rule 4 `and` -> `or` (`-mde < lo` is true) |
| L10 | 6, 6 | 0, 0 | NO_DIFFERENCE | rule 4 deleted (falls to UNDERPOWERED); the degenerate point is pinned (R-H1) |

Every row fails today because the skeleton returns `None`. The `and` -> `or` mutant lists `[L8]` and `[L9]` as its tests. `label_for` is called by `verdict` only: the empty-stratum rule passes `n = 0` to it, and rule 1 then fires because `min_pairs >= 1` is guaranteed by `VerdictSpec` (PAT 5), so there is one emitter. The invariant "no other path emits a label" is a behavioural assertion in `test_input_order_never_changes_a_verdict` (SIM 4): for every `Verdict` produced, `label == label_for(n_for_rule, spec.min_pairs, lo, hi, spec.mde)` with `n_for_rule = 0` when a stratum is empty, else `n_pairs`.

**Dominance table** `test_statement_for_table` (EV-19; renumbered after SIM 2):

| id | label | ratio (lo, hi, r) | expect | mutant |
| --- | --- | --- | --- | --- |
| D1 | BETTER | hi 0.99 | `dominates` | |
| D2 | BETTER | hi 1.00 (boundary), r 1.00 | `better at ×1.00 tokens` (not `dominates`) | `hi < 1` -> `<=` (one expression serves both labels, so no second row) |
| D3 | NO_DIFFERENCE | hi 0.99 | `dominates` | `or NO_DIFFERENCE` dropped |
| D4 | WORSE | hi 0.50 | `None` | WORSE added to the set |
| D5 | UNDERPOWERED and NOT_RECORDED (two parametrize ids, `non-directional`) | hi 0.50 | `None` | either label added to the set |
| D6 | BETTER | ratio `None` | `None` | `None` treated as 0 |
| D7 | BETTER | lo 0.8, hi 1.4, **r 0.9** (straddles 1) | `better at ×0.9 tokens`, never `dominates` | statement reads `lo` (0.8 < 1 would say `dominates`); `hi` replaced by `r` (0.9 < 1 would say `dominates`) |

Every row fails today because the skeleton returns the string `"unimplemented"`.

| node id | pins | tolerance | fails today because | red fixture | real wiring | mutant |
| --- | --- | --- | --- | --- | --- | --- |
| `test_normal_approximation_400_pairs` | two tasks of 200, true .20: bounds within **0.005** of normal [0.16366, 0.26634] (observed gap 0.0013) | 0.005 | skeleton interval (1, -1) | | `Verdict` built through the real `verdict()` | percentile index `B*alpha_pt/2` -> `B*alpha_pt` shifts each bound by 0.0083 (a 90% interval: half-width 0.05134 x 1.6449/1.9600 = 0.04309), which exceeds 0.005; `test_golden_interval_and_draws` is the second killer |
| `test_stratified_equal_task_weight` | tasks of 10 and 90 pairs with effects .5 and 0: `effect == Decimal("0.25")` exactly | exact | skeleton effect absent | the unequal-size fixture | | weights by pair count (gives .05); pooled resample |
| `test_per_task_and_both_tasks` | `both_tasks` True only if both task intervals exclude 0 the same way; one task with 1 pair -> False; non-directional labels -> None | | skeleton label `None` | | | `all` -> `any` |
| `test_level_uses_corrected_alpha` | same pairs, m 1 vs 45: the m 45 interval is wider and equals a golden | exact golden | skeleton equal (1, -1) | | | `alpha/m` -> `alpha` |
| `test_holm_verdict_interval_equals_bonferroni` (R-96 c2, second row) | same seed, same pairs, m 45: `holm` and `bonferroni` give equal `interval`, `level` and `alpha_per_test`; `method` echoes as registered (`"holm"`, never rewritten, R-96 c3) and `level_rule` differs (holm sentence vs `"alpha/m (Bonferroni)"`); the `none` verdict with the same pairs is narrower | exact | skeleton `method` and `level_rule` absent | the `none` control | real `verdict()` | `holm` mapped to `alpha` fails this row **and** `test_holm_is_sized_like_bonferroni` (listed under both in `verdicts.json` and `power.json`) |
| `test_resamples_for_tail_depth` | `resamples_for(0.05) == 2000`, `(0.05/45) == 18000`, `(0.0002) == 100000`, `(0.0001) -> HB-USR-002`; tail index `B*alpha/2 >= 10` | exact | skeleton returns -1 | the 0.0001 refusal row | | `20` -> `10` |
| `test_min_pairs_below_one_is_refused` (PAT 5) | `VerdictSpec(min_pairs=0)` and `-1` -> HB-USR-002; `1` constructs | | no raise | the zero row | | guard deleted |
| `test_seed_for_is_a_legal_params_seed` | the section-3.4 S2 row: `stats.Params(seed=seed_for("e1746a8b...effc","security","cc-opus",("off","candidate")))` constructs and equals 878446374899272100; hypothesis over 2,000 hashes: all `< 2**63` | exact | **fails today against W0 rev 2's text** (14055141998388353605 -> HB-USR-002); against the rev 3 skeleton the equality fails | the S2 row is the red fixture | `Params` is the real class | `[:15]` -> `[:16]`; any one of the five fields dropped from the key (one test per field changes it and asserts the seed moves) |
| `test_input_order_never_changes_a_verdict` (hypothesis) | permute pairs: equal `Verdict`; **plus the label invariant** above for every example | `==` | skeleton equal for all, so the golden-interval assertion and the invariant carry the failure (`label_for` returns `None`) | | | sort removed; a code path that returns a `VerdictLabel` without `label_for` |
| `test_duplicate_pair_key_is_refused` | two pairs same (task, rep) -> HB-USR-002 | | no raise | the duplicate | | guard deleted |
| `test_non_binary_primary_is_refused` | `Decimal("0.5")` and `Decimal("2")` as a `Pair` value -> HB-USR-002; 0 and 1 accepted | | no raise | | | guard deleted |
| `test_empty_stratum_is_not_recorded` | one task has 0 pairs: `NOT_RECORDED`, reason names the task, `n_pairs >= min_pairs` still | | skeleton label `None` | task list `["a","b"]`, pairs only in `a` | | strata taken from the pairs instead of `spec.tasks` |
| `test_golden_interval_and_draws` | a 6-pair fixture: interval bytes and the first five draws of `stats.rng(seed, "effect")` | exact | skeleton (1, -1) | | pins the Python-version assumption already pinned by `test_stats` T-S4 | stream key renamed |
| `test_adding_a_quantity_does_not_move_the_effect_interval` | with and without tokens: same effect interval | exact | | | | shared stream between effect and ratio |
| `test_ratio_reference_and_not_recorded` | treat = 2 x ref tokens on every pair: ratio `(2, 2, 2)`; zero ref sum -> `None`; missing tokens -> `None`; wall ratio point | exact | skeleton ratio absent | the zero-sum fixture | | `None` -> 0 |
| `test_conservation_every_cell_in_a_pair_or_excluded` (hypothesis) | random cells with outcomes, validity, NA, calibration, non-admitted tasks, partners: `2*pairs + excluded == cells in scope`; every excluded id unique; `sum(na_counts.values())` equals the excluded entries from the NA branch | | skeleton: one bogus excluded entry (1 != n) | | `collect` runs on real `CellView` objects | an `if value is None: continue` that drops silently |
| `test_calibration_cells_do_not_change_any_verdict` (EV-9) | add calibration cells (any values): every `Verdict` equal | `==` | skeleton equal, golden carries it | | | calibration filter removed |
| `test_check_tampered_is_listed_not_dropped` | a cell with primary NA `invalid (check tampered)`: appears in `excluded` with that reason, `na_counts == {"invalid (check tampered)": 1}`, label unchanged vs the same data without that cell's pair | | skeleton `na_counts == {}` | the tampered cell | | NA cells filtered before the list; label made to depend on `na_counts` (W0 refuses this) |
| `test_one_blocked_cell_shows_excluded_1` (EV-18 last bullet) | `excluded == [(id, "blocked (auth)")]` | | skeleton excluded `[("unimplemented", "")]` | | the same fixture is rendered in the three places in 11.4 | |
| `test_degenerate_sample_is_labelled_by_rule_not_hidden` | three pairs all +1 -> `BETTER`; three pairs all 0 -> `NO_DIFFERENCE`; both carry `n_pairs 3`, `required_pairs` | | skeleton label `None` | | documents R-H1 | |
| `test_e1_demo_shape` (R-89) | k 3, one harness, `min_pairs 3`, mixed diffs (+1, 0, 0 per task): `UNDERPOWERED`, `n_pairs 6` | | skeleton label `None` | | | |
| `test_coverage_golden[effect\|ratio]` (**slow**, TA 5) | the S4 and S5 script, committed as the test body by X-H1: 1,000 datasets, `random.Random(20261003)`, n 53, true .20, B 2,000 (ratio: lognormal tokens). Asserts the **count** 936 of 1,000 (effect) and 948 (ratio) | exact count | skeleton interval (1, -1) covers 0 | | the real `verdict()` | percentile `/2` removed (coverage ~0.89); a changed stream key |
| `test_coverage_band[effect\|ratio]` (**slow**, TA 5) | the same script at N = 4,000 datasets (standard error about 0.0035): coverage in [0.93, 0.97] | 0.93..0.97 | skeleton covers 0 | | the real `verdict()` | percentile `/2` removed |

Coverage tests, stated plainly: the golden count is a regression pin on this Python's `random` stream (R-H8), the band is the method claim, not a proof of nominal coverage. A golden failure with the band green is a stream change (update the golden once, with the Python version named); a band failure is a finding about the interval method (R-H2: BCa or studentised), never a re-seed (F14). The 936 and 948 are measured at N = 1,000 (S4, S5); the N = 4,000 value is **not yet measured** (Inferred: about 0.936 with standard error 0.0035; if it lands below 0.93, that is the R-H2 finding, recorded rather than hidden).

Dropped on the SIM review (6): `test_label_for_is_total_and_exclusive` (a pure function cannot return two labels; its implications restate rules 2 to 5).

### 11.3 `tests/test_gates.py`

One fixture view per kind; each is the red fixture for its guard, and `test_every_gate_kind_has_a_red_fixture` asserts `set(FIXTURES) == set(GateKind)` (checked against the enum in the tree, so a new kind without a fixture fails; the enum has **nine** members).

| node id | fixture | expected | fails today because | adjacent-rule mutant |
| --- | --- | --- | --- | --- |
| `test_clean_view_passes` | a view with no defect | `pilot(...) == []` | skeleton returns `[GateItem("unimplemented", "")]` | a check always firing |
| `test_gate_cell_lost_failed_and_blocked` | one `failed` cell, one `blocked` cell | two `cell-lost` items | skeleton item kind is `unimplemented` | `blocked` dropped |
| `test_gate_cell_lost_by_infrastructure_cause` | cell code `HB-CELL-112` (disk, infrastructure), outcome `timed_out`, primary recorded | exactly one `cell-lost`, `detail` names the code | same | the attribution clause dropped (the pair with the next row differs only in cause) |
| `test_gate_timed_out_with_primary_is_not_a_loss` | `timed_out` with primary recorded, cause not infrastructure | no item | same | `timed_out` treated as lost |
| `test_gate_bnd_a_beats_cell_lost` (TA 4) | code `HB-CELL-107`, outcome `failed` (the only cell shape on which the two rules differ) | exactly one item, kind `bnd-a-loss` | same | precedence swapped (gives `cell-lost`) |
| `test_gate_grader_error` | score reason `HB-GRD-003 grader property failed: ValueError` | `grader-error` once per cell, not also `primary-not-recorded` | same | dedupe removed |
| `test_gate_check_tampered_beats_primary_unrecorded` | primary NA `invalid (check tampered)` | one `check-tampered`, no `primary-not-recorded` | same | precedence swapped |
| `test_gate_other_na_is_primary_unrecorded` | primary NA `check exceeded its bound` | `primary-not-recorded`, not `check-tampered` | same | tampered test uses `startswith("invalid")` (caught: also matches `invalid (check output ...)`) |
| `test_gate_metric_not_recorded_with_expected_na_exception` | a secondary NA in every cell; once with `expected_na` naming it (keyword); once with the three-argument W0 call | item vs no item; the three-argument call is valid; `expected_na` passed positionally raises `TypeError` | same | exception ignored; `every` -> `any`; keyword-only dropped |
| `test_gate_task_no_primary` | a task whose cells have no `property_check_pass` row | `task-no-primary` | same | uses "value None" instead of "no row" (would fire on NA cells too) |
| `test_gate_hidden_tests_nondeterministic` | list `["c3","c7"]` | two items, idents c3, c7 | same | list ignored |
| `test_gate_suspend_detector_blind` | list `["c5"]` | one item | same | list ignored |
| `test_pilot_refuses_unread_lists` | `None` for either list | HB-USR-002 | no raise | guard deleted |
| `test_pilot_output_is_sorted_unique_and_order_independent` (hypothesis) | shuffled cells | equal list, sorted by (kind, ident), no duplicate (kind, ident) | skeleton: one item, equal for all, so the clean-view assertion on the same examples carries it | sort removed |
| `test_pack_regression_table` | hi < 0 -> `regression signal`; hi == 0 -> `no regression detected at 0.30`; straddle; good direction; exact strings; **and** no value matches `better\|worse\|dominates` (EVX-6; replaces the former string-constant sweep) | exact | skeleton `{"": "unimplemented"}` | `hi < 0` -> `<=`; "worse" added to the signal text |
| `test_pack_regression_missing_arm_is_withheld` | candidate absent | `Result withheld: ring is missing candidate.` | same | |
| `test_admission_table` (EV-8; W0 rev 4 section 8) | per row, off-arm `property_check_pass` per cell: A1 `[1,1,1]` -> `(0, "saturated")`; A2 `[0,0,0]` -> `(0, "floor")`; A3 `[1,1,0]` -> `(1, "")`; A4 `[0,0,1]` -> `(1, "")`; A5 other arms all 1, `off` mixed -> `(1, "")` (the `off_arm` argument is honoured) | exact | skeleton `(-1, "unimplemented")` | `all` -> `any` (A3 and A4 turn red); `off_arm` ignored (A5) |
| `test_admission_na_primary_raises` | one off-arm cell with NA primary -> HB-USR-002 (the pilot gate has named it); a task with no off-arm cell -> HB-USR-002 (*assume:* section 5) | | no raise | | NA treated as 0 |

Dropped on the SIM review (3, 4): `test_gate_infrastructure_beats_failed` (merged kind) and the separate `test_regression_strings_carry_no_verdict_words` (it passes on a sentinel skeleton and its values are already in the table above).

### 11.4 Section and report (`tests/test_campaign_section.py`, `tests/test_report.py` additions)

| node id | pins | fails today because | red fixture | real wiring | mutant |
| --- | --- | --- | --- | --- | --- |
| `test_r93_warning_line_renders_with_count_and_ids` | seeded list `["C-014","C-031"]`: exactly one `p[data-kind=hidden-test-disagreement]`, `data-count=2`, both ids in the text, placed after the exclusions summary and before the verdict table | **fails today by assertion**: `html.render` has no section, so the element is absent (the skeleton accepts `campaign_obj` and ignores it) | the seeded-disagreement fixture | `html.render(..., campaign_obj=fixture)` end to end, no fake builder | condition `n > 0` -> `n >= 0` (kills the next test) |
| `test_r93_line_absent_when_zero` | `[]` -> 0 disagreement elements and 0 not-recorded elements, **and** `#property-verdicts` exists with the text `excluded 0 cells in total` | the section is absent today and the skeleton emits `<section id="unimplemented">` | `[]` | | `>= 0` |
| `test_r93_not_recorded_when_reader_failed` (R-96 ruling 2) | `None` -> exactly one `[data-kind=hidden-test-agreement-not-recorded]`, **no `data-count` attribute, no cell ids in its text**, zero `hidden-test-disagreement` elements; the two `data-kind` values differ in every state | absent today | `None` | | `None` coerced to `[]`; `data-count` added to the not-recorded element; shared `data-kind` |
| `test_r93_line_not_in_the_header` (TA 6, W0 section 7 condition 3) | seeded list and `None`: the EV-20 header block exists (asserted first) and contains no `[data-kind^=hidden-test]` element | the skeleton renders no header block, so the existence assertion fails | seeded list; `None` | | the line also printed by the header builder |
| `test_r93_line_changes_no_verdict` | the same verdict cells with and without the line: byte-equal verdict table | absent today | | | line text feeding the label |
| `test_section_reads_the_real_readiness_function` (join test, owner X-INT; **a condition of "done" for X-H2**) | a graded fixture run where the final tree's `hidden_tests_pass` differs from `pass_at_1` for one cell: the report shows that cell id | red until X-E lands | real `readiness.hidden_test_disagreements` | the real function (the fake in the rows above is the list literal) | |
| `test_legend_prints_level_rule` (R-96 c1) | registered `holm`, m 45: the legend text contains `0.9989` and `alpha/m (Bonferroni; Holm's first step)`; `data-method="holm"`, `data-alpha-per-test`, `data-level-rule` equal the verdict's; `bonferroni` and `none` print their own rules | absent today | the three methods | real `html.render` | legend prints the bonferroni string for `holm`; legend omits the rule |
| `test_na_counts_by_reason_beside_every_verdict` | each verdict cell shows `not recorded by reason: ...` equal to `Verdict.na_counts` | absent today | | | |
| `test_excluded_one_cell_in_three_places` (EV-18) | `excluded 1` and the id and cause in the cell, the completion summary and the validity banner | absent today | one blocked cell | | one place dropped |
| `test_evu_1_4_8` | verdict word as text; the non-campaign page unchanged (also called with `campaign_obj=None` and a `None` reader list: no R-93 element of either kind, TA 7 / EVU-4) and `tests/test_report_builder.py:165` list intact; eight-part order | absent today (the order and text legs) | | | `None` list rendered without a campaign |
| `test_evu_2_interval_marks` | `data-interval-lo/hi`, `data-mde` on effect marks, equal in the table alternative | | | | |
| `test_evu_3_state_pairs` | one assertion per (component, state) of section 10 | | | | |
| `test_evu_6_ring_section_has_no_verdict_words` | regression section text has none of `better\|worse\|dominates` | | | | |
| `test_evu_7_exploratory_labels` | header text and a badge in every intention-verdict cell; counts > 0 on a campaign report, 0 on a non-campaign one | | | | |
| browser ring: `test_evu_5_axe_light_and_dark`, 1280x800 first-row visibility (EVX-2) | `pytest -m browser` | | | | |

### 11.5 Sweep (checked against the tree on 2026-10-03, base `109f8c0b`)

| id | sweep | root | tokens | allowlist (constant) | tree check |
| --- | --- | --- | --- | --- | --- |
| S-2 | the word `dominates` appears only in `verdicts.py` and the one empty-state string | `src/harness_bench/`, files `*.py`, `*.js`, `*.html` (the section copy could come from `report/assets/report.js`, TA 9) | `dominates`, case-insensitive | `DOMINATES_ALLOWED = {("verdicts.py", "dominates"), ("report/campaign_section.py", "No arm dominates another.")}` (a set of pairs; SIM 5) | `grep -rIil dominat src tests` returns 0 files (run 2026-10-03 on `109f8c0b`; it covers `report/assets/report.js`, the only non-Python asset); **red fixture:** a temp tree with a module and a `.js` file each containing the word must fail the sweep |

An allowlist pair that no longer matches the tree fails the sweep (so a stale entry cannot hide a gap). Former S-1 is the label invariant inside `test_input_order_never_changes_a_verdict`; former S-3, S-4 and S-5 are deleted (see the Review disposition, SIM 4).

### 11.6 Trace from W0 and the spec to tests

| contract | test |
| --- | --- |
| W0 §8 power inputs and result (rev 4: `slots`, `planned_reps_per_task`, `level_rule`) | 11.1 |
| §8 `verdict`, sort, `seed_for`, `Pair` Decimal | 11.2 (`input_order`, `seed_for`, `non_binary_primary`) |
| §8 `pilot` arity (`expected_na` keyword-only), kinds | 11.3 |
| §8 `admission` (EV-8) | `test_admission_table`, `test_admission_na_primary_raises` |
| §3 NA rule, refused label change | `test_check_tampered_is_listed_not_dropped`, `test_gate_check_tampered_*` |
| §7 R-93 and R-96 ruling 2 | 11.4 R-93 rows |
| R-96 conditions 1 to 3 | `test_level_rule_table`, `test_holm_is_sized_like_bonferroni`, `test_holm_verdict_interval_equals_bonferroni`, `test_legend_prints_level_rule` |
| seam req-01M41DM7X | conservation, tampered, suspend-blind, na-counts rows |
| EV-12 / 18 / 19 reference cases and boundary rows | 11.1 / 11.2 tables |
| EV-14, EV-15 | 11.3 |
| EV-20, EVU-1..8, EVX-6, EVX-7 | 11.4 |

Testing Strategy union: D0 hygiene (ruff, types, `simplify:` markers); pure-function boundary and property tests (this section); mutation (`tests/mutations/*.json` for the three modules and the section, run by hand at the Proof Pack); golden for intervals and coverage counts; browser ring for axe and layout; slow ring for the coverage simulations (ADR-0020). Not triggered: concurrency, I/O, migration, security-negative beyond section 8.

## 12. Telemetry

Questions an operator asks, with the emitting source (caller side, because the modules are pure). Each event has a **named test** (TA 10); the test asserts every field and that an unavailable field reads `"not recorded"`, never 0 (IO):

| question | event and fields | emitter | test |
| --- | --- | --- | --- |
| how long and how big was the analysis | `power.analysed` {properties, input_hash, ms, assumed_count, level_rule} | X-C `bench campaign power` | `test_power_analysed_event_fields` (X-C's `tests/test_campaign_power.py`, named here so the field list is fixed) |
| how long were verdicts, how many resamples | `verdicts.computed` {verdicts, resamples_total, ms, excluded_total, na_total, labels{label: n}} | X-H2 at report write | `test_verdicts_computed_event_fields` (`tests/test_campaign_section.py`) |
| what did a gate find | `gate.evaluated` {tag, items{kind: n}, ms} | X-C at register, X-H2 at ring report | `test_gate_evaluated_event_fields` (the ring-report leg in `tests/test_campaign_section.py`; the register leg is X-C's) |
| did the R-93 reader run | `section.built` {hidden_disagreements: n or "not recorded"} | X-H2 | `test_section_built_event_fields` (`tests/test_campaign_section.py`; `None` -> the string `"not recorded"`, `[]` -> `0`, a list -> its length; R-96 ruling 2) |

Error codes: `HB-PWR-001`, `HB-USR-002`. No HTTP surface. *assume:* the report writer can append a structured event beside the report (as `html.write` already records timings). Confirm: X-H2 reads `html.write` before building. Breaks if false: the events move to the run ledger writer.

## 13. Flagged risks and residual unknowns

| id | risk | disposition |
| --- | --- | --- |
| R-H1 | A zero-variance sample gives a zero-width interval, so three identical pairs read `better` or `no difference`. W0 refused label changes from NA, and the spec fixes the rule order, so no rule is added | shown as `n <pairs> of <required>`; pinned by a test; the pre-registration `min_pairs` is the control. **Closed on the W0 side:** rev 4 section 8 makes X-C's `register` preview warn (not refuse) when `min_pairs` < the required `n`. `VerdictSpec` refuses `min_pairs < 1` (PAT 5) |
| R-H2 | Effect coverage measured 0.936 at N = 1,000, about one sigma above the 0.93 floor (percentile bootstrap under-covers at n = 53) | the golden count pins the stream, the N = 4,000 band is the method claim (11.2); a band failure is a finding about the interval method (upgrade: BCa or studentised), never a re-seed |
| ~~R-H3~~ | the `None` state of the R-93 line | **closed:** R-96 ruling 2 reads it inside R-93 with IO; no flag remains |
| ~~R-H4~~ | `holm` is mapped to the Bonferroni level | **closed:** R-96 ruling 1 grants (A) with conditions 1 to 3, all met in this revision (`level_rule`, the second row, recorded as written) |
| R-H5 | verdict compute cost at m = 45 | measured, section 2 trigger |
| ~~R-H6~~ | `expected_na`, `slots`, `planned_reps_per_task` | **closed:** granted in W0 rev 4 (`req-01M41EX52AX93PQS1FHYCSA0YG`) |
| R-H7 | `views.cell_arm` is not yet on main | `_arm(cell)` helper, fallback `cell.pack` |
| R-H8 | Python 3.12 here, 3.14.6 in ADR-0020's spike; the `random` stream stability is an existing assumption (`stats.py:34`) | the golden tests are the detector; they tell a stream change from a method change (F14) |
| R-H9 | `readiness.expected_na` (X-E) and the `admit` caller (X-C) do not exist yet | W0 rev 4 fixes both signatures; the tests here use fixtures of that shape; the join test is X-INT's |
| R-H10 | the N = 4,000 coverage value is unmeasured | Inferred (about 0.936); measured when X-H1 commits the test body; a result below 0.93 is the R-H2 finding |

## 14. Change surfaces (E7) and requests

Store (`power/<hash>.json`, `prereg/<hash>.json`, `admission.decided` rows; X-C) -> model (`power.py` incl. `LEVEL_RULES`/`level_for`, `verdicts.py`, `gates.py` incl. `admission`) -> service (`campaign.read`, X-E readers incl. `readiness.expected_na`, `cli.py` register check, `register` preview and `admit` in X-C) -> projection/wire (`PowerResult` and `Verdict` as JSON for `bench campaign power` and the completion summary, both carrying `alpha_per_test` and `level_rule`; `Pair` builder `collect`) -> client type (none) -> UI (`report/campaign_section.py` incl. the legend, the `html.py` hook, the egress section shape, `report.js` untouched) -> compute readers (registration refusal, ring report, EV-20 header, completion summary). Also: `tests/mutations/{power,verdicts,gates,campaign_section}.json`; the G3 lint set (X-D); `docs/docs-index.js`.

| request | id | status |
| --- | --- | --- |
| `seed_for` 60 bits | `req-01M41EPKRBCVQ28MS96CHNTDRZ` | granted in W0 rev 3 |
| `pilot` unbiased list | `req-01M41EPKVYZQ9NH97HEJR7M5PY` | granted in W0 rev 3 (kind named `suspend-detector-blind`) |
| `expected_na`, `slots`, `planned_reps_per_task`, `pairing_unit` values | `req-01M41EX52AX93PQS1FHYCSA0YG` | **granted, all three** in W0 rev 4 (`expected_na` keyword-only, default empty; source `readiness.expected_na`) |
| `holm` semantics (decision) | `req-01M41EPSB7E91C4APYT1QGN3FV` | **ruled R-96 (DR-10), option A**; ADR-0020 Amendment 1 written |
| W1-C OI-1, OI-2, OI-3 (to W1-H) | W0 rev 4 changes table | **ruled:** OI-1 and OI-2 are X-C's readers and the final power inputs (no prereg field); OI-3 `gates.admission` is X-H1's (this design, 11.3) |

Hub files: `report/html.py` (X-H2 in E1, W0 §13). This design edits none.

## 15. Conformance notes

Self-check against the definition of done: data model first (yes, no aggregate by design); E7 list (section 14); phasing (E1, demo shape named); spikes (section 3.4); patterns (section 4); ladder climbed with three `simplify:` markers; failure modes (7); STRIDE (8); privacy negative (9); UI (10; `DESIGN.md` is the existing report design language, unchanged, so no new tokens and no re-lint); test plan with the union (11; every row red by assertion on an out-of-domain skeleton, TA 3); telemetry (12, four named tests). **Unmet:** the rollups `docs/security/threat-model.md` and `privacy-review.md` are not refreshed (they are not files this slice owns). The HB-CHK-002 reason text and `HB-CELL-107` for BND-A rest on marked assumptions; `tools/mutate_check.py` runs in no ring.

## Review disposition (revision 2)

Source: `docs/design/reviews/eval-review-{ta,pat,sim}-w1h.md`. Every finding has a row; **applied** = changed in this revision, **applied (modified)** = changed in a different form, **declined** = reason given. "TA/PAT/SIM n" are the reviews' own numbers.

| # | finding (short) | disposition | where |
| --- | --- | --- | --- |
| TA 1 | L10, D8 and D10 mutants not killed by the row that names them | **applied.** `and` -> `or` moved to L8 and L9 (verified: L8 `-0.30, 0.10` gives NO_DIFFERENCE under `or`); old L10 dropped (no mutant of its own); D8 dropped, `statement uses lo` moved to D7 (old D10); D7's `r` is stated (0.9); mutation entries list parametrize node ids | 11.2 |
| TA 2 | 400-pair tolerance 0.01 cannot kill `B*alpha/2` -> `B*alpha` | **applied.** Tolerance 0.005 (observed gap 0.0013, mutant shift 0.0083); `test_golden_interval_and_draws` named as the second killer | 11.2 |
| TA 3 | rows green on the skeleton | **applied.** Every skeleton returns an out-of-domain value (`None`, `"unimplemented"`, a sentinel `GateItem`, an impossible interval); the rows that would still pass (absent-element, `test_clean_view_passes`) gain an assertion the placeholder fails. No ring runs `mutate_check`; stated, with the by-hand Proof Pack run | 11 intro, 11.3, 11.4 |
| TA 4 | bnd-a vs infrastructure is an equivalent pair | **applied.** The pair is renamed `bnd-a` vs `cell-lost` (code 107, outcome `failed`, the only shape on which they differ); the attribution clause is separated from the outcome clause by a fixture that differs only in cause | 5 Gates, 11.3 |
| TA 5 | coverage gate one sigma above its floor | **applied.** Golden count (936, 948) separates stream from method; band [0.93, 0.97] at N = 4,000 is the method claim; the S4 script is committed by X-H1 as the test body; docstring says regression pin. The N = 4,000 figure is unmeasured and labelled Inferred (R-H10) | 11.2, 3.4, 13 |
| TA 6 | "not in the EV-20 header" untested | **applied.** `test_r93_line_not_in_the_header` | 11.4 |
| TA 7 | R-96 negative assertions, EVU-4 row, R-H3 stale | **applied.** Not-recorded row asserts no `data-count`, no ids, no disagreement element; no-campaign leg in `test_evu_1_4_8`; `section.built` "not recorded"; R-H3 closed | 6, 11.4, 12, 13 |
| TA 8 | F2 cites a test that does not exist; epsilon unguarded | **applied.** `_snap` helper and `test_snap_at_the_integer_edge` with two mutants | 5, 11.1 |
| TA 9 | scans without red fixture; roots too narrow | **applied (modified).** S-2 gains a red fixture and a root of `*.py`, `*.js`, `*.html`; S-1 became an invariant and S-3, S-4, S-5 were deleted on SIM 4, which removes the rest of this finding | 11.5 |
| TA 10 | telemetry tests are a pattern, not nodes | **applied.** Four named tests with the "not recorded, never 0" assertion | 12 |
| TA R-96 conditions | `alpha_per_test` and `level_rule`, second holm row, never rewritten | **applied.** See PAT 1, PAT 2 | 3.2, 11 |
| PAT 1 | R-96 `level_rule` field and legend missing | **applied.** `LEVEL_RULES` table and `level_for` in `power.py` (the one definition), `level_rule` on `PowerResult` and `Verdict`, legend and tooltip print it, `test_level_rule_table`, `test_legend_prints_level_rule`; R-H4 closed. The `bonferroni` and `none` sentences are this design's wording; the `holm` sentence is R-96's verbatim | 3.2, 5, 6, 11 |
| PAT 2 | second holm row | **applied.** `test_holm_verdict_interval_equals_bonferroni`; the `holm` -> `alpha` mutant is listed under it and under the sizing row | 11.2 |
| PAT 3 | `pilot` arity disagreement with W1-C | **applied.** W0 rev 4 rules it: `expected_na` keyword-only, default empty, source `readiness.expected_na`; the three-argument W0 call is a test; the seam is granted | 3.2, 11.3, 14 |
| PAT 4 | `min_pairs` warning lives only in a risk table | **applied.** W0 rev 4 section 8 puts the warning on X-C's `register` preview; R-H1 cites it | 13 |
| PAT 5 | `min_pairs` 0 switches off the not-recorded rule | **applied.** `VerdictSpec` refuses `min_pairs < 1`; L13 dropped (SIM 1) | 3.2, 11.2 |
| PAT 6 | "Specification" is the wrong pattern name | **applied.** "Decision table, one function" | 4 |
| SIM 1 | drop L12, L13 | **applied** | 11.2 |
| SIM 2 | drop D4, D8; fold D7 into D6 | **applied.** D4 (old) covered by D2's single `hi < 1` expression; D8 (old) by D7 (new); old D6 and D7 are one `non-directional` row | 11.2 |
| SIM 3 | nine vs ten gate kinds; merge `cell-failed` and `infrastructure-cell` | **applied.** One kind `cell-lost`; the enum has nine members; summary, enum and the every-kind test agree. `test_gate_infrastructure_beats_failed` dropped | 3.2, 5, 11.3 |
| SIM 4 | S-1 to S-5 | **applied.** S-1 is the label invariant in `test_input_order_never_changes_a_verdict`; S-3, S-4, S-5 deleted; S-2 kept. The values of `pack_regression` are asserted in `test_pack_regression_table` | 11.2, 11.3, 11.5 |
| SIM 5 | `any` sentinel in the S-2 allowlist | **applied.** A set of pairs | 11.5 |
| SIM 6 | four hypothesis tests that cannot fail alone | **applied.** Deleted: label total-and-exclusive, monotone, determinism, JSON round trip; `test_mde_roundtrip_property` kept | 11.1, 11.2 |
| SIM 7 | `descriptive` echo | **applied.** Dropped with its test; `sd` and `rep_spread` are validated; upgrade trigger named | 3.2, 5, 11.1 |
| SIM 8 | `collect(primary=...)` and the 10^4 scale | **applied.** E1 accepts `Decimal(0)` or `Decimal(1)` only; `test_off_scale_value_is_refused` becomes `test_non_binary_primary_is_refused`; upgrade trigger named (Inferred by the review; the W0 section 2 int 0/1 text is Verified) | 3.2, 5, 11.2, F11 |
| SIM 9 | `na_counts` and `excluded` are two definitions | **declined, with the guard kept.** W0 section 8 fixes `excluded` as `(cell_id, reason)` pairs and the `verdict` signature; tagging the pairs changes a W0 shape. `na_counts` is derived in one place (`collect`'s NA branch) and the conservation test asserts its sum equals the NA-branch entries | 5, 11.2 |
| SIM 10 | `pilot` seam; OI-2 and OI-3 silent | **applied.** Arity as PAT 3; `VerdictSpec.tasks` are the admitted tasks from `admission.decided`; power sizes on the pre-admission tasks (a note); `admission` designed and tested here | 3.2, 5, 11.3, 14 |
| SIM 11 | close R-H3 | **applied** (with R-96 ruling 2) | 13 |
| R-96 / R-93 / ADR | ruling 2 third state, ADR-0020 Amendment 1 | **applied.** Section 2 note and section 6 state table updated | 2, 6 |

## Status & next action

| | |
|---|---|
| **Completed** | design of X-H1 and the X-H2 section 3 view, with spikes and the test plan; gate passed (three PASS WITH CONDITIONS); revision 2 applies all findings |
| **Remaining** | derive/validate and audit; the N = 4,000 coverage measurement (X-H1); `readiness.expected_na` (X-E) and the `admit` call site (X-C) |
| **Best next action** | `/implement` X-H1 (skeleton commit with the out-of-domain values, red tests, green); then X-H2 |

## Gate record

`GATE w1-h-power-verdicts · PASSED (PASS WITH CONDITIONS x3; conditions applied in revision 2, see Review disposition) · RV-TA (hard veto), RV-PAT, RV-SIM (soft veto)`

- `GATE W1-H · Test Architect · PASS WITH CONDITIONS · 10 findings (rv-ta-hc-e1e4, 2026-10-03)`
- `GATE W1-H · Patterns Expert · PASS WITH CONDITIONS · 6 findings (rv-pat-hc-e1e4, 2026-10-03)`
- `GATE W1-H · Simplifier · PASS WITH CONDITIONS · 11 findings (rv-sim-hc-e1e4, 2026-10-03)`