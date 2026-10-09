---
id: "arch-lean-benchmark"
title: "Architecture amendment: the lean pack benchmark (two batch runs of one lean ring, and a lean summary over verdicts)"
type: architecture
status: draft
owner: "@timianmalloo"
phase: "Lean benchmark (operator 2026-10-09)"
tags: [benchmark, architecture, lean-benchmark, ring, batch, derived-view, report]
links:
  - { to: arch-harness-bench, rel: refines }
  - { to: arch-evaluation-campaign, rel: relates-to }
  - { to: spec-lean-pack-benchmark, rel: implements }
  - { to: plan-strategy-lean-benchmark, rel: depends-on }
  - { to: adr-0022-lean-benchmark-two-batch-runs, rel: depends-on }
  - { to: adr-0023-lean-summary-over-verdicts, rel: depends-on }
  - { to: adr-0020-power-and-verdicts-stdlib, rel: depends-on }
review-by: "2027-04-09"
summary: >-
  The smallest architecture that answers the lean spec. Two confirmed 60-cell runs of a new ring
  (bench/rings/lean.yaml, tag lean) are the two batches, so the checkpoint is a real stop. A new pure module,
  lean.py, pairs with the existing verdicts.collect, takes intervals from stats.paired_delta and one new
  two-stage sibling, stats.paired_ratio, and derives MDEs from power.mde_for. A new report section renders it, and
  `bench report --pool` pools the two batches under board.compare's preconditions plus lean rules. The pack
  effect, verdicts and catalog 0.7 do not change, and no stored quantity is added.
---

# Architecture amendment: the lean pack benchmark

*Status: draft, for the gate below. Authored 2026-10-09 by the Leader seat (Claude Code, Opus) at `307ec787`.
Labels: **Verified** = read or run here; **Inferred** = modelled, model named; **Flagged** = unknown.*

## Context and constraints

The spec (`docs/specs/lean-pack-benchmark.md`) asks one question: per harness, does pack-on beat pack-off on
`property_check_pass`, and at what token cost? It asks it over 120 cells in two batches of 60, with a checkpoint, in about
2 h of run and 2 h of grading. The binding constraints are these:
- reuse first (strategy §3);
- no new metric (catalog 0.7 is frozen);
- no second interval engine;
- a non-lean report stays byte-identical (LBU-5);
- tokens are the only cost axis (Ruling 115);
- pack-off cells carry no instruction files (Ruling 116, HB-PRE-009).

## The system as a system

- **Stocks:** two run ledgers (append-only facts) and two frozen plans (ADR-0006), plus one committed
  pre-registration paragraph.
- **Flows:** cell launches, then grading, then the derived lean summary at report time.
- **The one feedback loop:** the checkpoint. Batch 1's measured run minutes, grading minutes and tokens per cell set
  whether batch 2 starts (LB-3).
- **The boundary:** the campaign machinery (`campaign.py`, power records, registration, the alarm) is outside, and
  stays unused.
- **The leverage point:** *where batch boundaries come from*. The visible decision is "add a measure to the pack
  effect". The structural one is that `plan.launch_order` interleaves repetitions (`plan.py:209-215`, Verified), so
  only separate runs give a real checkpoint. ADR-0022 decides it.

Candidate shapes considered (ADR-0022, ADR-0023): one 2-repetition plan with a mid-run checkpoint; two 1-repetition
runs pooled at report time (**chosen**); a plan-level repetition filter. For the summary: extend the pack effect;
`verdicts.verdict` (vetoed at the gate: a zero-width interval at one pair per task); `verdicts.collect` for pairs
plus `stats.paired_delta` and a two-stage `stats.paired_ratio` for intervals (**chosen**).

## Archetype and tier allocation

- **LOA archetype:** N/A for this amendment. It adds no AI capability: the lean summary calls no model (spec,
  *AI-integrated allocation*). It inherits `arch-harness-bench`'s allocation for the harness runs it measures.
- **Tiers:** every new component is **T0**, deterministic: a matrix file, a pure derived view, a renderer and a
  CLI flag. Grading's judge calls are unchanged.
- **Rejected:** any model-backed summary or narrative (`--summaries` stays out of the lean path).

## Domain model and durable representation

- **Bounded context:** Evaluation (the spec's).
- **Aggregate:** *Lean benchmark*. Its invariant: every pair shares task, repetition, harness, model pin, engine
  identity and the pack-off workspace rule, and only the arm differs. Both batches come from one plan identity.
- **Enforcement:**
  - the ring file fixes tasks, arms and pins;
  - `--pool`'s plan-identity check refuses a drifted batch (ADR-0022 §3);
  - the Leader's engine-identity record at each batch start (ADR-0022 §5);
  - HB-PRE-009 at plan time.
- **Durable representation:** unchanged. The batches are ordinary runs: frozen plans as dimensions and
  append-only ledgers as facts (ADR-0006). The `LeanSummary` is a **derived projection**, recomputed on every
  `bench report`. It is never stored and never a second source of truth.
- **No new stored quantity:**
  - pairs, effects, intervals, ratios and the checkpoint numbers are all derived;
  - the MDEs are derived by `power.mde_for` (Verified, spike below);
  - the pre-registration is a committed text file whose sha256 seeds the bootstrap.
- **Data & Persistence:** no schema change, no migration.

## Component map

| component | kind | change | owner track |
| --- | --- | --- | --- |
| `bench/rings/lean.yaml` | matrix (ring tag `lean`, 60 cells, 1 repetition) | new; copied from `e5-pilot.yaml` | L-MATRIX |
| `config.RING_TAGS` | validation | add `"lean"` | L-MATRIX |
| `campaign.plan_block` | validation | refuse ring `lean` with `--campaign` (HB-CMP-010) | L-MATRIX |
| `harness_bench/lean.py` | pure derived view (T0) | new: `build(...) -> LeanSummary` (contract below) | L-SUMMARY |
| `stats.paired_ratio` | statistic | new: ratio of totals on `paired_delta`'s draw scheme | L-SUMMARY |
| `views.run_wall_ns` (name Inferred) | numeric helper | extracted from `report/html.py` `_run_wall_clock`; the formatted output stays byte-identical | L-SUMMARY |
| grading duration helper | numeric helper | (`grading.completed` − `grading.started`) `mono_ns`, and `cells_graded`, for the current pass | L-SUMMARY |
| `board` comparability | precondition function | extracted from `board.compare` (`:726-795`); `compare` keeps calling it with the same messages | L-SUMMARY |
| `report/lean_section.py` | renderer | new: the Part B/C section | L-SUMMARY |
| `report/html.py` | page assembly | insert the section at the campaign section's slot (`:2259-2266`) when the ring tag is `lean` | L-SUMMARY |
| `report/pack_improvement.py` | existing section | **no change**; its median per-pair token ratio is named beside the lean ratio of totals | - |
| `cli.py` `report` | CLI | add `--pool RUN_ID` and `--prereg PATH`; build the pooled input; HB-STA-002 on drift | L-SUMMARY |
| `verdicts.py` (`collect` only), `stats.paired_delta`, `power.py`, `board.py` pack effect, catalog 0.7 | existing engine | **no change** (called, not edited) | - |
| `docs/notes/lean-preregistration.md` (path Inferred; design-slice fixes it) | committed paragraph (LB-2) | new | L-DOCS |
| spec, `coordination-finish.md`, `architecture-evaluation-campaign.md`, `enterprise-evaluation.md` | docs | dated errata (supersession table; ADR-0022/0023 drift) | L-DOCS |

## Contracts at the seams

**`lean.build(batches: Sequence[BatchInput], prereg: Prereg | None) -> LeanSummary`.**
- Pure: same inputs give the same bytes.
- One or two batches, in batch order.
- The CLI has already run the pooling check, and supplies the durations and the pre-registration (no I/O in
  `lean`).
- It raises `BenchError` on a view whose ring tag is not `lean`.

```
BatchInput
  view: RunView
  run_wall_ns: int | None            # from the extracted wall-clock helper
  grading_ns: int | None; cells_graded: int | None   # current pass, from grading.started/completed mono_ns
Prereg
  sha256: str; committed_at: datetime | None          # None = not committed
LeanSummary
  batches: int                       # 1 or 2
  run_ids: tuple[str, ...]; plan_hashes: tuple[str, ...]
  prereg_status: str                 # "pre-registered (<sha12>)" | "Not pre-registered: <reason>"
  rows: tuple[LeanRow, ...]          # one per combo, plan order
  pooled: LeanRow                    # task key "<combo>/<task>"
  disagree: bool                     # two harness intervals wholly on opposite sides of 0
  properties: tuple[PropertyRow, ...]
  checkpoint: tuple[BatchCheckpoint, ...]
LeanRow
  combo: str; harness: str; model: str
  effect: Decimal | None; lo: Decimal | None; hi: Decimal | None   # stats.paired_delta (two-stage)
  mde: Decimal                       # power.mde_for: per harness 20->0.31 or 10->0.42; pooled 60->0.19 or 30->0.26
  pairs: int; planned_pairs: int     # "k of 20 pairs recorded"
  excluded: tuple[tuple[str, str], ...]      # ("<run_id>/<cell_id>", cause), from verdicts.collect
  statement: str                     # "no detectable effect" | "pack-on higher by x" | "pack-on lower by x" | "not recorded (0 pairs)"
  token_ratio: Interval | None       # stats.paired_ratio over token-complete pairs (ratio of totals)
  ratio_excluded: int                # pairs without recorded tokens, or with 0 pack-off tokens
PropertyRow
  family: str; harness: str          # S, RS, RW, NG, SM x combo
  off: tuple[int, int]; on: tuple[int, int]  # (passes, recorded)
  direction: "up" | "down" | "same"
BatchCheckpoint
  run_id: str; cells: int
  run_min_per_cell: Decimal | None; grade_min_per_cell: Decimal | None   # None = "not recorded", never 0
  tokens_per_cell: Mapping[(combo, arm), Decimal | None]
  infra_failures: Mapping[combo, (int, int, tuple[str, ...])]          # (k, n, causes); > 20% is named (LB-3)
ESTIMATE                             # module constant: LB-3's Inferred estimates, shown beside the measured values
  run_min_per_cell = 1.12; grade_min_per_cell = 1.16; tokens_per_cell = 1_060_000
```

**Identity classes (gate amendment, 2026-10-09).** `test_identity.py:103-106` requires every `src/harness_bench`
file in `identity.CLASSES`. `lean.py` is classed `"grade"`, as `verdicts.py` is (`identity.py:103`), by
L-CONTRACT. `report/lean_section.py` is classed `"grade"`, as `report/pack_improvement.py` is (`:94`), by
L-SUM-B1. **Arm ids** come from `plan.comparisons` and `config.ARM_OFF`, never new `"on"`/`"off"` or `"pack"`
literals (`tests/test_arms_guard.py:26`, `:96-97`).

**`bench report <run> [--pool <run>] [--prereg <path>]`:**
- a non-lean run with `--pool` is refused;
- a lean run without `--pool` renders `1 of 2 batches`;
- a lean run with `--pool` renders `2 of 2`, or refuses with HB-STA-002 and lists every difference (ADR-0022 §3);
- `parameters` and `envelope_seconds` differences are shown, not refused;
- on a pooled page, the lean header names both run ids and plan hashes, and says the other sections cover the
  reported batch only;
- every other run's output is byte-identical to today's (LBU-5's golden).

**`stats.paired_ratio(ref, treat, labels, params, key) -> Interval`:** `paired_delta`'s signature, streams and draw
order. The statistic is Σ treat / Σ ref over the drawn values, and the point is the ratio of totals. A test pins
it on a hand-computed case, and checks that its interval has nonzero width when tasks differ.

## Cross-cutting concerns

- **Security and identity:** no new trust boundary. The pack-on binding is the existing `--arm`. No new egress.
  `--summaries` is not used.
- **Observability:** the checkpoint numbers are measured from the ledgers. The report's existing statistics timing
  line covers the new intervals. A value that is not recorded renders as `not recorded`, never 0 (US-27).
- **Idempotency:** the summary is a pure function. Re-running `bench report` rewrites the same bytes for the same
  inputs and seed.
- **Failure modes:**
  - a lost cell drops its pair and is listed with its cause;
  - a lost task drops its stratum and is named;
  - a harness with 0 pairs reads `not recorded (0 pairs)`;
  - a batch from a drifted plan is refused at `--pool`.

## LOA conformance

C1-C11 are written for AI capabilities. This amendment adds none, so the AI-specific criteria are N/A. The
general ones hold:
- determinism at the floor: T0 only;
- verification over plausibility: every number is derived from recorded facts, and every MDE from a solver that a
  test pins against the spec.

## Delivery phasing (vertical slices)

1. **Walking skeleton: one batch, end to end.** The lean ring and tag (L-MATRIX), and `lean.build` for one view
   with per-harness rows and statements. `lean_section` renders the header and the per-harness table, through
   `bench report <run>` on a synthetic 60-cell fixture run.
   - *Real:* plan, report, `verdicts`, `power`.
   - *Fake:* the cell outcomes (fixture ledger).
   - *Human check:* open the fixture's `report.html` and read `1 of 2 batches` and MDE 0.42.
   - *Tests:* the LB-4 rows on known pairs, LBU-4, and LBU-5 (the existing golden is unchanged).
2. **Two batches, pooled.** `--pool` with the identity check, the pooled row and the disagreement note, the token
   ratio with exclusions, the per-property table, and the limits note with the checkpoint.
   - *Tests:* LB-5 to LB-7, LBI-1 to LBI-4, and HB-STA-002 on a drifted plan.
3. **The real run** (no code): pre-registration, batch 1, checkpoint, batch 2, `bench report <b2> --pool <b1>`,
   and the run report.

Slices 1 and 2 are one track (L-SUMMARY), or two parallel tracks split at the `LeanSummary` contract above: the
view against fixtures, and the renderer against a hand-built `LeanSummary`. That choice is
`/prepare-for-coordination`'s.

## Evidence ledger (spikes and reads, 2026-10-09 at `307ec787`)

| claim | label | evidence |
| --- | --- | --- |
| launch order interleaves repetitions | Verified | `plan.py:209-215` |
| `bench run` grades only at the end; no repetition filter | Verified | `cli.py:714-725` |
| two runs of one matrix do not collide on disk or in the verdict store | Verified | `engine.py:727`; `gateway/store.py:3,30` |
| `verdicts.collect` pairs by (task, rep) and drops a partnerless pair with its cause | Verified | `verdicts.py:162-198` |
| `verdicts.verdict`'s stratified interval has zero width at one pair per task | Verified | probe: effect [0.4, 0.4] and ratio [2, 2]; `paired_delta` on the same data gives [0.1, 0.7] (`verdicts.py:218-232`) |
| `stats.paired_delta` is a two-stage bootstrap (task, then repetition) | Verified | `stats.py:157-208` |
| `power.mde_for` at ψ 0.28, α 0.05, power 0.8: 10 → 0.415, 20 → 0.312, 30 → 0.26, 60 → 0.188; n(0.20) = 52.52 | Verified | spike run, `uv run --no-sync` |
| `launch_seed` differs per plan, and `cells` is stored in launch order | Verified | `plan.py:229` (`secrets.randbits(63)`), `:208-214` |
| grading minutes are derivable: `grading.started` and `grading.completed` with `mono_ns`, and `cells_graded` | Verified | `grade/runner.py:263-299`; `ledger.py:69-73` |
| the run wall clock today is a formatted string inside `report/html.py` | Verified (gate read) | `report/html.py:195-212` |
| the first cell's start time is readable from the view, for LB-2 | Inferred (gate read names `attempt.process_started`) | design-slice confirms the field |

## Residual architectural risk

- **Correlated repetitions:** the true per-harness MDE lies between 0.31 and 0.42 (spec). It is stated, not
  solved.
- **Sequential wall time** is about 4.6 h (Inferred), against the spec's 2.5 h + 2.5 h ceiling. The checkpoint
  measures it.
- **Batch 2's grading may be faster** through judge-store cache hits on identical requests. If the ledger records
  the hit count, it goes beside the grading minutes; if not, this is a named caveat.
- **`paired_delta` resamples each arm's repetitions independently within a task**, so the interval is
  conservative at the pair level. This is the spec's method (glossary, *Paired difference*).

## Gate record

*Adversary-mode council, 2026-10-09: an Opus sub-agent with the Simplifier, Test Architect, Data & Persistence,
SRE, Enterprise and Distributed lenses, reading the code at `307ec787`. The author did not clear any finding
alone. Every veto finding was re-run by the author.*

| # | lens | finding | resolution |
| --- | --- | --- | --- |
| 1, 2 | Test Architect | **VETO.** `verdicts.verdict`'s effect and ratio intervals have zero width at one pair per task (probe [0.4, 0.4] and [2, 2]). | Accepted. The effect is now `stats.paired_delta`; the ratio is the new two-stage `stats.paired_ratio`. ADR-0023 is revised. **Veto cleared by the change, not by argument.** |
| 3 | Test Architect | Pooled pairs cannot come from one `collect` call (harness filter, strata names). | `collect` once per harness, then pooled task key `<combo>/<task>` for `paired_delta`. |
| 4 | Test Architect | Equal `cell_id`s across batches make excluded cells ambiguous. | Relabel `cell_id = "<run_id>/<cell_id>"`. |
| 5 | Test Architect | LB-2's timing is not computable from a pure function with only a sha. | `Prereg(sha256, committed_at)` from `--prereg`, and the first cell start from the view; a defined seed with no pre-registration. |
| 6 | Test Architect | LB-3's infrastructure-failure criterion has no field. | `BatchCheckpoint.infra_failures`. |
| 7 | Test Architect | Notes on `verdict`'s empty strata. | Moot: `verdict` is not called. |
| 8 | SRE | Grading minutes are derivable (Flagged → Verified). | Adopted; the fallback was removed. |
| 9 | SRE / D&P | The run wall clock would gain a second definition. | Extract one numeric helper; `_run_wall_clock` formats it, byte-identical. |
| 10 | Enterprise | The identity exclusion list was wrong (launch order, `parameters`, `envelope_seconds`). | ADR-0022 §3: cells compared as a set; `parameters` and `envelope_seconds` shown, not refused. |
| 11 | Enterprise / Simplifier | A third "comparable runs" definition. | The pooling check is `board.compare`'s extracted preconditions plus the lean rules. |
| 12 | Enterprise | `lean` with `--campaign` would be treated as a campaign ring. | Refused (HB-CMP-010), ADR-0022 §3a. |
| 13 | UX fit | The slot "before the pack effect" fails LBU-1. | The section goes in the campaign slot (`report/html.py:2259-2266`). |
| 14 | D&P | Two token ratios on one page. | Labelled "ratio of totals", with one line naming the pack-improvement median; `pack_improvement` is added to the surface list. |
| 15 | D&P | A pooled page's other sections cover batch 2 only. | A scope line in the lean header. |
| 16 | D&P | A wrong batch-1 run could be pooled. | Both run ids and plan hashes are in the header. |
| 17 | Spec drift | The lean-shape definition differs from the spec's NFR row. | Added to ADR-0022's errata list (L-DOCS). |
| 18 | Simplifier | The `lean` tag, `--pool` and the module split are justified. | Kept. |
| 19 | Distributed | No ordering issue with sequential runs; possible judge-cache speed-up. | Residual risk, above. |

**Verdicts after revision:** Test Architect veto cleared by the change (findings 1 and 2), with findings 3 to 7
resolved in the contract. Data & Persistence: pass (no new stored quantity), with findings 9, 14 and 15 resolved.
Security and Distributed Systems: no hard-veto trigger (no new trust boundary, no async or messaging).
