---
id: "design-eval-catalog-0-7"
title: "Catalog 0.7 (ADR-0019): the eleven property metrics, scenario-7 pass@1 and the missing-pass@1 fix"
type: design
status: proposed
owner: "@timianmalloo"
phase: "Enterprise evaluation: Wave 1, design slice W1-G (builds X-G1 in E1, X-G3 and the _passed fix in E3)"
tags: [benchmark, catalog, metrics, grading, us-4, evaluation-campaign, w1-g]
links:
  - { to: spec-enterprise-evaluation, rel: implements }
  - { to: arch-evaluation-campaign, rel: implements }
  - { to: adr-0019-catalog-0-7-property-metrics, rel: depends-on }
  - { to: design-eval-seam-contracts, rel: depends-on }
  - { to: rulings-register, rel: depends-on }
review-by: "2026-10-17"
summary: >-
  Design of catalog 0.7: the eleven property metrics written out in full YAML with R-79 anchors and no new area;
  the dispatch rule that lets one grader record a metric another grader owns (the property: tag and the new
  also_graded_by key); the per-task formal.pass_rule that makes scenario-7 pass_at_1 a three-valued AND; the
  missing-pass@1 fix and its sweep as the new defect class ABS-A; and the US-4 control, which is a cross-version
  regrade against the committed 0.6 goldens plus an append-only, chain-linked corrected_from record.
---

# Catalog 0.7: property metrics, scenario-7 pass@1, the missing-pass@1 fix

**Slice:** W1-G, session `w1g-catalog-e1e4`, tier T2, fan-out 0. Author: Claude Sonnet (`claude-sonnet-5-5`, R-91). 2026-10-03.
**Inputs read on `3c1c9827`:** ADR-0019; spec EV-2..EV-6, EV-10, EV-11; W0 rev 2 sections 2, 7, 9, 11, 13, 14; R-59, R-79, R-86, R-90; `bench/metrics.yaml`, `bench/catalog-freeze.yaml`, `tools/freeze_catalog.py`; `report/pack_improvement.py`, `grade/formal.py`, `grade/runner.py`, `composites.py`, `config.py`, `board.py`, `tests/test_catalog_version.py`; `tasks/G1`, `tasks/G2`. Labels: **V** = Verified (opened or ran), **I** = Inferred (with the check that would confirm it).

## 0. Findings that shaped the design (each was checked, none assumed)

| # | Finding | Source | Effect on the design |
| --- | --- | --- | --- |
| F1 | `config.py` refuses a catalog that does not have exactly seven areas: `if len(metrics.get("areas") or {}) != 7` (V). | `config.py` end of `validate_catalog` | **No new area.** The eleven metrics go into existing areas (section 4.1). A new area would need a `config.py` change in X-A1's hub, and it would add a `measures` row to every board (`board.py:550, 770` iterate `cat.areas`), which moves board bytes for runs that have nothing to do with properties. |
| F2 | A metric's owner is its one `grader` string, and `applicable` groups by it (`runner.py:166-167`, V). `pass_at_1` is `grader: correctness`. G2's graders are `formal, drift, cost, process`, with no `correctness` (V, `tasks/G2/task.yaml`). A second entry with the same id is refused (`config.py:151`, V). | as cited | ADR-0019 item 3 ("the formal grader records `pass_at_1`") cannot be met by the formal grader alone: GradedOncePerPass would fail the pass with HB-GRD-004 on a key outside its applicable set (`runner.py:358, 365`, V). Section 4.2 adds one optional catalog key, `also_graded_by`. |
| F3 | G1 already names `correctness` (V, `tasks/G1/task.yaml:27-29`), so it already has a `pass_at_1` owner. | as cited | The owner rule (first of `[grader, *also_graded_by]` that the task names) keeps exactly one row per cell for G1 and G2. |
| F4 | The US-4 fixtures are two X1 mini-runs, `c44dd2b-no-heads` and `heads` (V, `tests/fixtures/ledger/`; `test_catalog_version.py:FIXTURES`). There is **no** committed grid-3 or grid-4 archive: `runs/` is git-ignored (V, `git check-ignore`). | as cited | ADR-0019 item 6 and EV-10 name "the frozen grid-3 and grid-4 fixtures". They do not exist as fixtures. The control is built on what is committed (section 4.5). The ADR wording is an amendment note, not a scope change. |
| F5 | The existing check (a) compares a fixture graded under the **current** catalog with the golden for the **current** version, so it is self-referential for a new version: the 0.7 golden is written from 0.7's own output. It cannot say "every 0.6 value is unchanged". | `test_catalog_version.py:60-110` (V) | The 0.6-to-0.7 claim needs a new cross-version test that compares 0.7's output with the committed **0.6** goldens (section 4.5). |
| F6 | The freeze control's check (e) fails if any `versions[v]` entry that exists at the merge base changes (V, `test_catalog_version.py:87`). ADR-0019 item 4's `corrected_from` edits the 0.6 entry. | as cited | (e) needs one narrow, tested exception (section 4.5), or the correction can never land. |
| F7 | `board.export` does not import `pack_improvement` (V, grep) and the two committed fixtures hold no scenario-7 cell (V). | as cited | The `_passed` fix **cannot move any committed 0.6 golden**. ADR-0019 item 4 says it "can". The correction record is therefore built, tested on a synthetic case, and used only if a real freeze run shows a moved hash. |
| F8 | Measured on `runs/grid-4` (V, scratchpad spike `g2rule.py`): all 12 G2 cells have `formal_checks_clean = statement_integrity = model_non_vacuity = 1`, and **no** `pass_at_1` row. On `runs/grid-3`: all 12 G2 cells have the three metrics NA and `pass_at_1` NA `task changed since the plan (version hash mismatch)`, which `_passed` counts as 12 fails. | scratchpad spike | The declared rule gives 12/12 = 1 on grid-4. G2 is saturated; recording `pass_at_1` makes it rankable but does not make it discriminate (section 14). Grid-3 shows the defect: 12 of 12 NA cells are read as failures. |
| F9 | `bench verify` verifies a run's ledger (`cli.py:349-356`, V). It does not read `bench/catalog-freeze.yaml`. | as cited | ADR-0019 item 4's "`bench verify` can show the chain" is not available. The chain is shown by the US-4 control's printed lines (section 4.5). Amendment note for the ADR. |
| F10 | `board.py:480` reads `c.scores.get("pass_at_1", Measure(0)).value == 1` (V). With a `None` value the comparison is false either way, so the result is the same as `Measure(None)`. | as cited | Same defect shape as `_passed` (absence given a failing default). Sweep row in section 4.4. |
| F11 | W0 section 9 lists `grade/property.py` as a new module (X-F), and `config.validate_catalog` refuses a grader with no module in `harness_bench.grade` (V, `config.py:158`). | as cited | Ordering: X-F's skeleton must join before X-G1's green commit (seam request, section 12). |

## 1. Responsibility, boundary, phasing

**One responsibility:** fix, in one place and one version, what the catalog says about the property metrics, scenario-7 `pass_at_1` and absent `pass_at_1`, so no later track re-derives it.

| owns (this design) | does not own |
| --- | --- |
| the eleven catalog entries and their anchors; the `property:` and `also_graded_by` catalog keys; the dispatch-rule amendment text; the `formal.pass_rule` field and its semantics; the missing-pass rule and its sweep; the US-4 cross-version control and the `corrected_from` record shape | the property grader's internals (W1-F); any hidden check; the `task.yaml` `expected` block (W0 section 2, W1-I and W1-L fill it); the pilot gate that consumes "not recorded" (W1-H); code (this is a design) |

**Phasing.** E1: X-G1 writes `bench/metrics.yaml` `version: "0.7.dev"` with the eleven entries and the `pass_at_1` key (probe version: the control prints `probe: exempt`, R-59 DR-4). E3: X-A3 lands the `_passed` fix and the sweep control; X-G3 lands `grade/formal.py` `pass_at_1`, G2's `pass_rule`, `tests/fixtures/catalog/0.7/**`; then the Leader runs `python tools/freeze_catalog.py` (R-86 condition 3 shape: commit 1 releases the label `0.7`, commit 2 freezes). Real vs mocked at E1: the catalog validates and the dispatch is unit-tested with injected graders; no property grader runs. Mock-substitutable seams: `runner.applicable` takes a plain dict catalog, and `formal.pass_at_1` is a pure function of the sibling scores.

## 2. Interrogation (Stage 2) and the ladder (L1)

| question | answer | evidence |
| --- | --- | --- |
| Does this need to exist? (YAGNI) | Yes, each part is demanded: the eleven ids by ADR-0019 item 2; the formal `pass_at_1` by item 3; the missing-pass fix by item 4; the control by item 6. | ADR text |
| Reuse in the codebase | `Score(None, reason)` for absence; `composites.gated` already treats a missing `pass_at_1` as NA (V, `composites.py:120-126`); `freeze_catalog.py` and checks (a)-(e) are reused, extended in one place. | opened |
| Stdlib / native / installed dep | YAML, `decimal`, `pytest`: nothing new. No new dependency. | none added |
| One line vs the minimum | The pass rule is one list in `task.yaml` (`all_of`), not a rule language. | section 4.3 |

**Patterns named (and rejected).**

| pattern | where | justification | rejected alternative |
| --- | --- | --- | --- |
| **Special Case / Null Object** (`Score(None, reason)`) | absence is a value with a reason, never `0` | already the grader contract (`grade/__init__.py:27-38`, V) | a `bool`-returning `_passed` (the defect) |
| **Strategy via registry** (existing `GRADERS`) | owner resolution picks which grader's function records a metric | unchanged mechanism; only the owner lookup grows | a second registered grader for `pass_at_1` (R-90 condition 4 refuses the same shape) |
| **Three-valued (Kleene) conjunction** | `pass_rule.all_of` | the smallest correct logic that never turns an unknown into a fail and never hides a definite fail | two-valued AND (a missing input reads as fail: the defect); "any NA gives NA" (hides a recorded 0) |
| **Append-only chain** (event-sourced correction) | `corrected_from` list | freeze entries are already append-only facts (DM5, DM11); a correction is a new fact that points at the old one | overwrite the golden (refused by R-86 (B)) |
| **Parameter Object** (existing `CellInput`) | the formal grader reads `inp.task["formal"]["pass_rule"]` | no new plumbing | a new `CellInput` field |

**Simplifier's likely attack and my answer (pre-empted).** "`also_graded_by` is a new catalog concept for one metric." Answer: the alternatives are worse and cost more. A duplicate id is refused by `config.py:151`. A new id (`formal_pass`) breaks the board's primary, which reads `pass_at_1` by id (`board.py:190, 194`). Adding `correctness` to G2 yields an NA forever (G2 has no hidden-test oracle). A list-valued `grader` breaks every `m["grader"] in graders` reader. The key is one optional list, validated in two lines. `simplify:` marker: `also_graded_by` has one user (`pass_at_1`); upgrade trigger is a second user, at which point it earns its own test in `config.validate_catalog`.

## 3. The data model (settled first)

**Context and language.** Bounded context: *Metric Catalog and Scoring* (inside the benchmark's grading context). Ubiquitous terms: *catalog version* (a frozen snapshot of definitions), *metric* (a definition, a dimension row), *score row* (one recorded value or one recorded absence), *recorded* (a score row with a value), *not recorded* (a score row whose value is NA with a reason, or no row because the metric does not apply), *pass rule* (a task's declared definition of a pass), *correction* (a later fact that supersedes a frozen golden and keeps the old value).

**Aggregates (each with its one invariant).**

| aggregate (root) | invariant it protects | references others by |
| --- | --- | --- |
| **Catalog version** (root: the `version` string with its `catalog_hash`) | once frozen, a version's definitions, weights, anchors and rubrics never change (US-4, R-59). | identity: version string, hash |
| **Freeze record** (root: `versions[v]` in `bench/catalog-freeze.yaml`) | append-only: a pinned hash or golden is never overwritten; a correction only appends a record that names the value it replaces. | version string; fixture name |
| **Score row** (root: the ledger row, in the existing `scores` fact) | exactly one row per (grading pass, cell, applicable metric) (GradedOncePerPass); a value or an NA with a reason, never both, never a default. | `cell_id`, `metric_id`, `grading_id` |
| **Task version** (root: the task folder, hash `task_version_hash`) | the `pass_rule` and `expected` are inside the hash, so a rule change is a new task version. | `task_id` |

**Durable representation (DM5-DM6).** Metrics are a **dimension** with **Type-2 history by whole-version snapshot**: each `versions[v]` is a complete, immutable snapshot, and a change to any definition is a new version. This is already the representation; the decision here is to keep it and not add a column-level effective-date history (that would be a shadow schema over what `catalog_hash` already pins). Score rows are **append-only facts** (the existing `scores` ledger fact). The freeze file is a small append-only fact table of corrections (below).

**Grain statements.**

| table / fact | one row is exactly one | identified by | recorded when |
| --- | --- | --- | --- |
| `scores` (existing; gains rows for the eleven ids and for `pass_at_1` on formal-only tasks) | value-or-absence of one metric for one cell in one grading pass | (`grading_id`, `cell_id`, `metric_id`) | the pass writes it |
| `versions[v]` in the freeze file | frozen catalog snapshot pin for one version | `v` | the Leader's freeze commit |
| `versions[v].corrected_from[i]` (new) | one correction of one pinned golden of one version | (`v`, index `i`) | the Leader's correction commit |
| catalog entry in `metrics.yaml` | one metric definition in one version | (`version`, `id`) | the catalog commit |

**Additivity of the eleven (DM9).**

| metric | scale | class | note |
| --- | --- | --- | --- |
| `property_check_pass`, `turn1_tests_pass`, `verified_before_use` | int 0/1 | additive as a count (summed to a pass count, reported as a rate) | rates are computed over recorded cells only |
| `idempotency_violations`, `hallucinated_symbol_errors`, `new_abstractions`, `new_dependencies` | int | additive within one task across cells; **never summed across properties** (a count of imports and a count of duplicate effects are not one quantity) | reported per task |
| `exploit_probes_blocked`, `fault_suite_pass`, `rework_ratio`, `size_vs_reference` | 4 places | **non-additive** (ratios): averaged per cell, never summed; a pooled ratio is recomputed from its numerators and denominators or not shown | the numerators live in the property evidence (W1-F) |

**History rule per attribute.** Every metric attribute (`kind`, `better`, `scale`, `anchor`, `weight`, `property`, `also_graded_by`) is **Type-2 by version**: a change is a new catalog version, so a past score never changes meaning. A Type-1 overwrite is a recorded decision to discard history; this design makes none. The one place history is rewritten on purpose is a golden correction, and it is Type-2 too: the old value stays in the chain.

**Derive, don't store (DM7).** The narrowed metric set per task is **derived** by `applicable(catalog, graders, property)`; it is never stored on the task or the plan. The pack section's pass counts are derived from `scores`. `pass_at_1` for a formal task is *stored* as a fact (it is a score row), and it is computed from its sibling rows by the pass rule: this is a materialised derivation, so it is a labelled rebuildable cache with an equality test (section 11, `test_pass_at_1_row_equals_the_rule_over_its_sibling_rows`). Two definitions of "pass" for one cell is the defect signature: there is one function, `formal.pass_at_1(task, scores)`, and one reader of "recorded", `_pass(cell)` (section 4.4).

**Writer and compute reader of every persisted field (DM15).**

| field | writer | compute reader |
| --- | --- | --- |
| catalog entries (eleven + `pass_at_1` key) | X-G1 (`metrics.yaml`) | `runner.applicable`, `composites.load_catalog`, `config.validate_catalog`, `catalog_hash` |
| `property:` tag | X-G1 | `runner.applicable`; `readiness.py` (through the same function, R-90 condition 1) |
| `also_graded_by` | X-G1 | `runner.applicable` |
| `formal.pass_rule` | X-G3 (`tasks/G2/task.yaml`) | `formal.pass_at_1`; readiness (`pass_rule_problems`) |
| `pass_at_1` score row (formal task) | `formal.grade_cell` via the runner | `board.py`, `composites.gated`, `pack_improvement._pass`, `html.py` |
| `versions[v].corrected_from` | the Leader (`freeze_catalog.py --correct`, section 4.5) | the US-4 control; `report` reads none |

**Migration (expand, migrate, contract; DM16).** *Expand:* 0.7 adds entries and two optional keys; no 0.6 entry changes except `pass_at_1` gains `also_graded_by` (a definition-adjacent key: the entry's bytes change, so `catalog_hash` changes, which is why this is a new version). *Migrate:* none; there is nothing to backfill. Old runs keep their graded-under version (R-59 condition 1; grid-3 and grid-4 are never re-scored, EN9). A re-grade of a grid-3 or grid-4 G2 cell under 0.7 would record `pass_at_1` only if the task version still matches the plan; it does not (grid-3: `task changed`, V), so those cells stay un-rankable (ADR-0019 item 3). *Contract:* none; no key is removed. Rollback: revert the `metrics.yaml` commit; a frozen 0.7 is never unfrozen, a defect is `0.8`.

## 4. Contracts

### 4.1 The eleven catalog entries (X-G1 writes these lines; weight 0, source D, kind score, grader `property`)

Placement: **existing areas only** (F1). `property_check_pass` and the four checks-and-counts that decide pass or fail go in `correctness`; the process-shaped counts go in `rigor`. Weight 0 means `composites.area` skips them (`weight <= 0`, V, `composites.py:94`), so **no area composite and no overall moves** (this is also why the 0.6 values cannot move).

```yaml
  correctness:   # appended to the existing list, after bugs_confirmed
      - { id: property_check_pass,       source: [D], better: higher, grader: property, kind: score, weight: 0, anchor: [0, 1], anchor_note: "convention: binary indicator in [0, 1]", note: "the property verdict; untagged, applies to every property task (R-90). 1 only when the stated ask's hidden tests pass and the property's check passes" }
      - { id: exploit_probes_blocked,    source: [D], better: higher, grader: property, property: security,   kind: score, weight: 0, scale: 4, anchor: [0.0000, 1.0000], anchor_note: "spec docs/specs/enterprise-evaluation.md:244", note: "blocked / probes" }
      - { id: fault_suite_pass,          source: [D], better: higher, grader: property, property: resilience, kind: score, weight: 0, scale: 4, anchor: [0.0000, 1.0000], anchor_note: "spec docs/specs/enterprise-evaluation.md:256", note: "checks passed / checks" }
      - { id: idempotency_violations,    source: [D], better: lower,  grader: property, property: resilience, kind: score, weight: 0, anchor: [5, 0], anchor_note: "convention: cap at 5 duplicated effects; provisional until the E4 discrimination records give the naive solution's measured count; 0 is clean", note: "count of duplicate deliveries that produced a duplicate effect" }
      - { id: turn1_tests_pass,          source: [D], better: higher, grader: property, property: rework,     kind: score, weight: 0, anchor: [0, 1], anchor_note: "convention: binary indicator in [0, 1]", note: "turn-1 hidden tests on the turn-1 snapshot (EV-4)" }
  rigor:         # appended to the existing list, after bug_claim_precision
      - { id: rework_ratio,              source: [D], better: lower,  grader: property, property: rework,     kind: score, weight: 0, scale: 4, anchor: [1.0000, 0.0000], anchor_note: "spec docs/specs/enterprise-evaluation.md:263", note: "turn-1-added lines that turn 2 changed or deleted / turn-1-added lines" }
      - { id: hallucinated_symbol_errors, source: [D], better: lower, grader: property, property: no-guessing, kind: score, weight: 0, anchor: [5, 0], anchor_note: "convention: cap at 5 build-log errors naming a missing member; provisional until the E4 discrimination records; 0 is clean", note: "EV-5" }
      - { id: verified_before_use,       source: [D], better: higher, grader: property, property: no-guessing, kind: score, weight: 0, anchor: [0, 1], anchor_note: "spec docs/specs/enterprise-evaluation.md:270", note: "1 when a read or probe of the API precedes the first edit that uses it, by tool-call order" }
      - { id: size_vs_reference,         source: [D], better: lower,  grader: property, property: simplicity,   kind: score, weight: 0, scale: 4, anchor: [3.0000, 1.0000], anchor_note: "convention: 3x the reference's added lines is the worst, at or under the reference is the best (EV-6 :274 defines the ratio, not a range); provisional until the E4 discrimination records", note: "added product lines / the reference's added product lines" }
      - { id: new_abstractions,          source: [D], better: lower,  grader: property, property: simplicity,   kind: score, weight: 0, anchor: [4, 0], anchor_note: "convention: cap at 4 new types or interfaces; provisional until the E4 discrimination records; 0 is none (EV-6 :275)", note: "new types and interfaces" }
      - { id: new_dependencies,          source: [D], better: lower,  grader: property, property: simplicity,   kind: score, weight: 0, anchor: [2, 0], anchor_note: "convention: cap at 2 new dependencies; provisional until the E4 discrimination records; 0 is none (EV-6 :276)", note: "" }
```

The `pass_at_1` line gains one key and nothing else (the rest is byte-identical to 0.6):

```yaml
      - { id: pass_at_1, source: [D], better: higher, grader: correctness, also_graded_by: [formal], kind: score, weight: 0, note: "gate factor in 0.5 (R-78 DR-S-2 amendment); 0.7: a formal-only task records it from formal.pass_rule (also_graded_by)" }
```

Header comment additions (X-G1): `version: "0.7.dev"`; history clause `0.7: property metrics, scenario-7 pass_at_1 (also_graded_by), per-metric expected values in task.yaml (ADR-0019, R-90)`; and two key definitions beside `scale:`/`kind:` in the header comment: `# property: a metric applies only to a task whose property.name equals it (untagged: every property task)` and `# also_graded_by: further graders that may record the metric; the owner for a task is the first of [grader, *also_graded_by] it names`.

- **Direction check (V against `config.py` rule):** every `anchor` has `worst != best`; `better: higher` has `worst < best`, `better: lower` has `worst > best`. All eleven pass (`rework_ratio [1,0]` lower; `size_vs_reference [3,1]` lower).
- **R-79 forms:** eight of eleven use a `convention:` note and four of those carry "provisional ... re-anchor", per R-79 item 1 ("a measured or provisional anchor is re-anchored in the next version when a run saturates a cell"). `exploit_probes_blocked`, `fault_suite_pass`, `rework_ratio` and `verified_before_use` cite spec lines opened for this design. No `measured` form is used because no property task has been run: inventing a range would be the guess R-79 item 2 corrected.
- **Weight 0, so the anchors do not rank anything in 0.7** (ADR-0019 item 2: "they decide verdicts, not the leaderboard"). The anchors set the normalised display only. The task's own `ceilings` (W0 section 2) decide the primary metric, not these anchors.
- **I:** `kind: score` with weight 0 and an anchor passes `validate_catalog` (the anchor is optional at weight 0 and, when present, is direction-checked, V `config.py:166-175`).

### 4.2 Dispatch-rule amendment (text for `design-phase3-graders`, R-90 condition 5)

The Documentation Steward lands this text. It extends the current rule ("The applicable set is every `kind: score` catalog metric of those graders", `runner.py:16-20`).

> **Dispatch, amended for catalog 0.7 (R-90).** `applicable(catalog, graders, property)` returns, for each grader a task names, the `kind: score` metrics that grader owns *for this task*. A metric with a `property:` tag applies only when the tag equals `property` (the task's `property.name`, or `None` when the task has none or has changed). A metric without the tag always applies. A metric's *owner* is the first grader in `[grader, *also_graded_by]` that the task names; the metric is in the owner's set and in no other, so each (cell, metric) gets exactly one row. A metric outside the narrowed set has no row; it is not "NA not built". Readiness reads the narrowed set through this function (R-90 condition 1).

```python
def applicable(catalog: dict, graders: list[str], property: str | None = None) -> dict[str, dict[str, dict]]:
    out: dict[str, dict[str, dict]] = {}
    for area in catalog["areas"].values():
        for m in area.get("metrics") or []:
            if m["kind"] != "score" or m.get("property", property) != property:
                continue
            owner = next((g for g in (m["grader"], *m.get("also_graded_by", ())) if g in graders), None)
            if owner is not None:
                out.setdefault(owner, {})[m["id"]] = m
    return out
```

(`m.get("property", property) != property` is the tag clause: untagged entries compare equal to themselves; a tagged one must equal the task's property. With `property=None`, only untagged metrics apply, matching W0 section 7 condition 1.) X-F owns this hunk in E1 (seam request `req-01M41DAHV9XTGBY1WES1R5VQH3`).

**Worked cases (all asserted by tests in section 11).**

| task graders | `property` | rows for `property_check_pass`, `exploit_probes_blocked`, `fault_suite_pass` | rows for `pass_at_1` |
| --- | --- | --- | --- |
| `correctness, property` | `security` | `property`: the first two only | `correctness` |
| `correctness, property` | `resilience` | `property_check_pass` and `fault_suite_pass` | `correctness` |
| `formal, drift, cost, process` (G2) | `None` | none (`property_check_pass` is untagged but its grader `property` is not named) | `formal` (owner by `also_graded_by`) |
| `formal, correctness, ...` (G1) | `None` | none | `correctness` (primary owner wins; `formal` records no second row) |
| task-changed fallback (`runner.py:318-321`: every catalog grader "named") | `None` | `property_check_pass` NA `task changed` under `property`, no tagged rows | `correctness` NA `task changed` (this reproduces what grid-3 recorded, V) |

### 4.3 Scenario-7 `pass_at_1` and the pass rule (ADR-0019 item 3)

**Field name (W0 section 14 left it to this design):** `formal.pass_rule`, inside the existing `formal:` block of `task.yaml`, so it is inside the task version hash.

```yaml
formal:
  tool: lean
  ...
  pass_rule:                      # catalog 0.7 (ADR-0019 item 3). Provenance: the three metrics are the ones whose
    all_of:                       # failure means the proofs do not stand (formal.py module docstring); bugs_confirmed and
      - formal_checks_clean       # bug_claim_precision are NA for G2 (grid-4: "not a bug-narrative task"), so they are not inputs.
      - statement_integrity
      - model_non_vacuity
```

**Semantics (a pure function, `formal.pass_at_1(task, scores) -> Score`, three-valued):**

| rule inputs | result | reason |
| --- | --- | --- |
| no `pass_rule` declared | NA | `no pass rule declared` (never 0) |
| any input is `0` | `0` | none (a recorded failure decides even when another input is NA) |
| no input is `0`, any input is NA or absent | NA | `pass rule input not recorded: <first metric id>` |
| every input is `1` | `1` | none |
| the rule names a metric the grader does not record (not in `inp.metrics`) | NA | `pass rule names an unrecorded metric: <id>` |

A cascaded cell (`statement_integrity = 0`, the other two NA `given statements edited`) gives `0` by row 2: editing the given statements is a fail, not an unknown. The evidence of the `pass_at_1` score is `grading/<id>/<cell>/formal/pass_rule.json` (`{"inputs": {id: value|null}, "result": 1|0|null}`), so the row can be re-derived from its inputs without trusting the code.

**G1.** G1 names `correctness` (F3), so its `pass_at_1` is the correctness grader's; `formal.pass_rule` is not read for G1 and G1 declares none. `model_conformance` is NA `not built` for G1 (`formal.py:17, 47`, V), so no honest G1 rule exists yet. Not in scope.

**Task-version consequence (ADR-0019 item 3, council D4).** Adding `pass_rule` changes the G2 task version hash, so grid-3 and grid-4's G2 cells (planned under the old version) stay un-rankable; only a new run records it. `bench/task-freeze.yaml` has no G2 entry (V: `grep` found none), so no task freeze needs re-pinning; the Leader re-checks this at the join. The `statement_hash` is untouched (it hashes the statements, not `task.yaml`).

**Effect on boards, stated plainly.** In a new run under 0.7, a G2 cell that fails its proofs now gets `pass_at_1 = 0`, so `composites.gated` returns 0 for it (V, `composites.py:120-121`) where it used to be NA. That is the intended change (G2 becomes rankable) and the reason `catalog 0.7` is a new version. It cannot appear in the two committed X1 fixtures.

### 4.4 The missing-pass@1 fix (ADR-0019 item 4) and its sweep

**The rule.** *Absence is not failure.* A cell whose `pass_at_1` is missing or NA is **not recorded**: out of every pass count, every fail count and every denominator, and listed as not recorded with its reason. A recorded `0` is a fail.

**The single reader.** Replace `_passed(c) -> bool` (`pack_improvement.py:1173-1175`) by `_pass(c) -> bool | None`: `True` for value 1, `False` for value 0, `None` for missing or NA. All call sites then take a position on `None`:

| site (V, `pack_improvement.py` unless noted) | today | after |
| --- | --- | --- |
| `:962-963` per-task `passes_on/off`, `n = len(task_pairs)` | `None` counts as a fail; `n` counts every pair | `recorded = [p for p in task_pairs if _pass(p.on) is not None and _pass(p.off) is not None]`; passes and `n` are over `recorded`; a task with `len(recorded) == 0` is not tested (no Fisher, not in Holm) and is `TaskInconclusive(task, ("pass_at_1 not recorded: <reason>",))` |
| `:1025-1026` per-group counts, `n_pairs` | same | same `recorded` filter; token and wall ratios keep using all pairs (they do not read `pass_at_1`); a group with no recorded pair is classed by the existing `classify_group` "not enough pairs" path (**I**: confirm at X-A3 that `GroupClassInput.n_pairs` is the quality denominator; if it also feeds a ratio rule, add a separate `n_recorded` field) |
| `:1151-1155` failing-test names for the "same failure in both arms" check | `not _passed` includes unrecorded cells | `_pass(...) is False` only |
| `:1254` `on_failures = ... not _passed(c)` in the headline | unrecorded on-cells are "pack-on failures" | `_pass(c) is False`; the headline gains `, k not recorded` when `k > 0` |
| `:858-870` `p1_value` | already `None`-safe (V) | unchanged |
| `board.py:480` `scores.get("pass_at_1", Measure(0)).value == 1` | default `Measure(0)` | `Measure(None)`; no behaviour change (F10), removes the copy-paste trap |
| `board.py:319, 226, 267, 405-408, 583-599` | already guard `None` or default `Measure(None)` (V) | unchanged |
| `composites.py:120-126` `gated` | `None` gives NA `pass_at_1 not recorded` (V) | unchanged |

**Why the Fisher input is the recorded pairs only.** Counting an unrecorded cell as a fail makes the arm that has more unrecorded cells look worse for a reason unrelated to the pack. Removing the pair from both arms keeps the two counts over the same pairs, which is what the existing test already assumes (`n` shared by `on` and `off`).

**Defect class (CI2: class, sweep, derive, prevent).** New class **ABS-A: absence read as failure** (an unrecorded value given a failing default, so the report counts what it never measured as a failure). *Sweep done in this design:* every `scores.get`/`.scores[...]` comparison in `src/harness_bench` (grep of `Measure(0)`, `.value == 0`, `.value == 1`, `.value != 1`, `not _passed`, `_passed(`; V). Result: three instances of the shape (`_passed` and its four call sites, and `board.py:480`), `process.py:133` (`stuck.value == 0`, in a function that returns a Score for an agent end first; **I**: X-A3 opens it) and `pack_improvement.py:1016, 1183` (`== 0` after `is not None`: V, safe). *Derive:* the invariant "a lookup default is `None`, a comparison to a number needs the `None` branch decided". *Prevent (control):* `tests/test_absence_not_failure.py` fails when a score lookup has a numeric default (regex on `src/harness_bench`), plus the behavioural tests of section 11, which were observed red on the un-fixed code. X-A3 adds the register entry to `docs/lessons/defect-classes.md` in the same commit (CI6).

### 4.5 The US-4 control and the append-only `corrected_from` record

**Control 1: the cross-version regrade (EV-10, ADR-0019 item 6; F4, F5).** For each committed fixture (`c44dd2b-no-heads`, `heads`): grade it offline under the 0.7 catalog (`graded_export`, the existing helper), parse the export, drop the fields that name the catalog (**I**: only the catalog version and hash; X-G3 reads `views.export` first and lists them), and require byte equality with the committed **0.6** golden `tests/fixtures/catalog/0.6/<fixture>.export`, parsed and dropped the same way. A second assertion requires that none of the eleven new ids appears in the 0.7 export (X1's graders do not name `property`). This is the first test that compares across versions; check (a) stays as is.

**Provenance of the 0.6 side.** The 0.6 golden is a Leader-pinned file (digest in `catalog-freeze.yaml`, check (c)), not output of this slice's code, so the test is not a golden pinned from the implementation's own output (GLD-A). To keep the 0.6 *definitions* honest too, X-G1 commits a copy of the 0.6 `metrics.yaml` at `tests/fixtures/catalog/0.6/metrics.yaml` and a test requires `runner.catalog_hash` over a root built from that copy to equal `versions['0.6'].catalog_hash` (so the copy is the real one), and that every 0.6 entry equals the same-id entry in the current catalog except `pass_at_1`'s added `also_graded_by`.

**Control 2: the formal-only shape.** No committed scenario-7 archive exists (F4). One small synthetic fixture is built with `archived_runs.make_run` (a G2-shaped task with `graders: [formal]`, `formal.pass_rule`, and the formal grader injected as a stub that returns known `Score`s, through `run_pass`'s `graders` mapping). It proves, through a real pass, that the formal-only cell gets exactly one `pass_at_1` row and the pass completes (GradedOncePerPass green). The real Lean path is one slow-ring test on the existing `tests/fixtures/grade/formal/g2/{reference,sorry}` trees (section 11). No grid archive is copied into the repo.

**The `corrected_from` record (ADR-0019 item 4; F6, F7, F9).**

```yaml
versions:
  '0.6':
    catalog_hash: ...                     # unchanged: a view fix does not change the catalog
    board_golden:                         # the NEWEST value; the golden check reads this
      c44dd2b-no-heads: <new sha256>
      heads: <new sha256>
    corrected_from:                       # append-only list, oldest first; absent unless a golden moved
      - key: board_golden                 # which pinned map this record replaces (golden | board_golden)
        was: { c44dd2b-no-heads: <old sha256>, heads: <old sha256> }
        defect_class: ABS-A               # must exist as "### ABS-A" in docs/lessons/defect-classes.md
        commit: <sha of the code commit that moved the bytes>
```

Check (e) gains exactly one exception, and nothing else about it changes. An entry present at the merge base may differ in the current file **only if** (i) its `corrected_from` list is the base's list with records appended (the base list is a prefix), (ii) for each appended record, `was` equals the base's (or the previous record's replacement) value of `key`, so the chain links with no gap, (iii) the value now under `key` differs from `was`, (iv) `defect_class` is a heading in the register and `commit` is a hex sha, and (v) every other key of the entry is byte-equal to the base. Otherwise (e) fails as today. The control **prints** one line per record, `corrected: 0.6 board_golden <was12> -> <now12> (ABS-A, <sha7>)`, which is how "the chain is shown" (F9). Check (c) pins the digest of the newest golden file as it does today.

**Expected use: none.** F7 says no committed golden can move. X-G3 runs the control before and after the `_passed` fix; if no hash moves, the freeze commit records no correction, and the mechanism stays tested on a synthetic freeze file (section 11). The Leader decides at the join, from the measured hashes, not from this design.

**Freeze procedure for 0.7 (R-86 shape; the Leader).** (1) Commit 1 "release label 0.7": `version: "0.7"`, history clause, no other change. (2) Commit 2 "freeze 0.7": `python tools/freeze_catalog.py` (the Windows form), then `tests/fixtures/catalog/0.7/{c44dd2b-no-heads,heads}.{export,board.export}` and the appended `versions['0.7']` entry with `board_export_version: 3` (EXPORT_VERSION is unchanged: no statistics change). (3) `uv run pytest -q tests/test_catalog_version.py tests/test_freeze_catalog.py tests/test_views.py tests/test_grade_runner.py tests/test_grade_formal.py`, output read, not the exit code.

## 5. Change-surface list (E7): store, model, service, wire, client, UI, compute reader

| layer | surface | change | owner · phase |
| --- | --- | --- | --- |
| store | `bench/metrics.yaml` | eleven entries, `pass_at_1` key, `version`, header comment | X-G1 · E1 (`.dev`), X-G3 · E3 (release label), Leader (freeze) |
| store | `bench/catalog-freeze.yaml` | `versions['0.7']`; optional `corrected_from` | Leader |
| store | `tests/fixtures/catalog/0.6/metrics.yaml`, `tests/fixtures/catalog/0.7/**` | new | X-G1, X-G3 |
| store | `tasks/G2/task.yaml` | `formal.pass_rule` | X-G3 · E3 |
| model | `grade/runner.py: applicable` | `property` clause, owner rule | X-F · E1 (seam) |
| model | `config.py: validate_catalog` | `property` value and `also_graded_by` checks | X-A1 · E1 (seam; fallback test-only) |
| service | `grade/formal.py` | `pass_at_1(task, scores)`, called from `grade_cell` | X-G3 · E3 |
| service | `report/pack_improvement.py`, `board.py:480` | `_pass`, recorded pairs, headline | X-A3 · E3 |
| projection / wire | `scores` fact rows; `views.export`; `board.export` | new rows for the eleven ids and formal `pass_at_1`; no schema change | none (existing columns) |
| client type | `views.CellView.scores` (a mapping of id to `Measure`) | none (open mapping) | none |
| UI | report tables (`html.py`, `cli_table.py`) | the EV-11 "not recorded in this run: ..." line already exists as a W1-H and X-H2 item; this design supplies the ids and reasons | X-H2 · E1 |
| compute reader | `readiness.py` (expected set), `gates.py` (pilot "never recorded"), `power.py` (primary metric) | read `applicable(...)` and `_pass`-style `None` handling | X-E, X-H1 |
| docs | `design-phase3-graders` amendment; ADR-0019 amendment notes (F4, F9); `defect-classes.md` ABS-A | text in sections 4.2, 4.4, 15 | Documentation Steward; X-A3 |

## 6. Failure-mode analysis

| # | category | failure mode | disposition | detection (telemetry) | test |
| --- | --- | --- | --- | --- | --- |
| FM1 | input | a pass rule names a metric the grader does not record | prevent (readiness check `pass_rule_problems`); degrade at grade time to NA with a reason | NA reason `pass rule names an unrecorded metric: <id>` on the row | T-F5 |
| FM2 | input | no `pass_rule` on a formal-only task | mitigate: NA `no pass rule declared`, never 0 | the same reason in the not-recorded list | T-F4 |
| FM3 | input | `property:` tag misspelled in the catalog (`no_guessing`) | prevent: validation in `validate_catalog` (seam) or the catalog test | `bench validate` problem naming the metric | T-C4 |
| FM4 | dependency | Lean or TLC unavailable, so a rule input is NA | mitigate: `pass_at_1` NA (not 0) with the first missing input named; the existing `NOT_WARMED` reasons flow through | NA reasons on the three input rows | T-F3 |
| FM5 | concurrency | two graders both record `pass_at_1` for one cell | prevent: one owner by construction (section 4.2); detect if it recurs: GradedOncePerPass HB-GRD-004 (`written != 1`) | HB-GRD-004 | T-R3 |
| FM6 | state | the pack section hides a real failure by dropping unrecorded cells | accept with a visible count: the headline and the inconclusive list state `k not recorded`, so a reader sees the exclusion; a recorded 0 is always counted | `not recorded` count in the headline | T-P3 |
| FM7 | state | all cells of a task unrecorded, so the task silently vanishes from the board | mitigate: the task is listed `inconclusive: pass_at_1 not recorded`; the pilot gate fails on "a metric that applies is NA in every cell of that task" (EV-11, W1-H) | inconclusive row; gate item | T-P2 |
| FM8 | state | a correction record skips a link or rewrites a past record | prevent: check (e) exception (i)-(v) | control failure message naming the version and key | T-U5 |
| FM9 | state | a golden is regenerated, hiding a real moved score as a "correction" | detect: the exception demands a register-listed defect class and a commit; the cross-version test (Control 1) still compares 0.7 with the **0.6** golden and does not read `corrected_from` | the test | T-U1 |
| FM10 | data | the 0.7 catalog changes a 0.6 score | prevent: weight 0 and no 0.6 entry edit; detect: Control 1 | the test | T-U1 |
| FM11 | data | a rule evaluates over stale sibling rows from an earlier pass | prevent: `formal.pass_at_1` reads the `Score`s computed in the same `grade_cell` call, not the ledger | evidence file lists the inputs | T-F6 |
| FM12 | time | task-changed fallback pass gives `pass_at_1` to the wrong grader | prevent: owner rule gives `correctness` (NA `task changed`); asserted | grid-3's recorded reason (V) | T-R5 |
| FM13 | resource | the new rows grow the ledger | accept: at most 11 rows per property cell and 1 per formal cell; the ledger already holds ~60 per cell (V: grid-3 G2 listed 60 metric ids) | row counts in the pass summary | none (negligible) |
| FM14 | integrity | the ADR names fixtures that do not exist | prevent: F4 recorded; the control uses the committed ones | n/a | T-U1 |

## 7. Adversarial analysis (STRIDE-lite)

**Trust boundaries.** (B1) the agent's output tree is untrusted input to graders, but this slice reads only graders' *scores*, not the tree. (B2) `task.yaml` and `metrics.yaml` are repository content edited by authors (trusted-but-fallible; a malicious or mistaken author is the threat). (B3) the freeze file is Leader-owned; a worker edits it only by mistake. (B4) a report reader trusts the pack section's counts.

| id | boundary | threat | disposition |
| --- | --- | --- | --- |
| S1 | B2 | an author edits `pass_rule` to a weaker set after a campaign started | mitigate: the rule is inside the task version hash; a changed hash makes archived cells `task changed` (V, `runner.py:317`) and the campaign's identity check (ADR-0017) refuses a changed task |
| T1 | B3 | a worker rewrites a pinned golden "as a correction" | mitigate: check (e) exception requires the chain, a register-listed class and a commit; check (c) pins digests; `bench/catalog-freeze.yaml` stays Leader-owned (R-86) |
| T2 | B2 | a weight raised from 0 on a property metric, silently changing composites | mitigate: `catalog_hash` covers `metrics.yaml`; check (b) fails any definition or weight edit without a bump |
| R1 | B3 | a correction with no attributable cause | mitigate: `defect_class` and `commit` are required fields; the control prints them |
| I1 | B4 | a NA reason carries agent text or a path | mitigate: reasons are the closed vocabulary of section 4.3 (metric ids from the catalog only), per `Score` rule "never agent text or a path" (V, `grade/__init__.py:31`) |
| D1 | B2 | a rule list of thousands of names slows grading | accept: `all_of` is read by a 3-line loop; authors are trusted; residual risk nil at this size |
| E1 | B1 | an agent writes a file that makes the rule read a wrong input | transfer (named): the inputs are the formal grader's own `Score`s, produced under that grader's existing STRIDE (`formal.py` module docstring, binary-artifact scan, G6/G10); this design adds no read of agent files |

Negative tests for the mitigations: T-U5 (forged correction), T-U6 (correction without a register class), T-C5 (weight edit without bump is red through (b), reuses the existing `test_a_weight_changed_without_a_bump_is_red_through_b`), T-F7 (changed `pass_rule` changes the task version hash).

## 8. Privacy (LINDDUN-lite)

No personal data: the slice defines metric names, anchors and rules, and reads scores of benchmark cells (no person). One line, an explicit negative.

## 9. Telemetry (IO1-IO12, O1-O13)

Questions an operator will ask, each with a named emitting source (no flag, on the normal path):

| question | source |
| --- | --- |
| How many cells of a task have `pass_at_1` not recorded, and why? | the pack section's inconclusive list and headline `k not recorded` (X-A3); the `scores` rows' `reason` (existing) |
| Which input decided a formal `pass_at_1`? | `grading/<id>/<cell>/formal/pass_rule.json`, referenced by the score's `evidence` |
| Did a property metric apply to this task? | the row exists or does not; `applicable(...)` is the single source (R-90) |
| Did a golden move, and why? | the control's printed `corrected:` lines; the `corrected_from` record |
| How long does the pass rule take? | negligible (a loop over three values): not instrumented; **Inferred**, bound by the formal grader's existing `grading_step_timeout` span, which already measures the expensive part |

No new error codes (W0 section 11 reserves none for this track). Structured events: none new; a grader failure keeps `grade.grader_failed` (V, `runner.py:353`). No HTTP surface, so no RFC 9457 response. Load-bearing telemetry with a planned test: the `pass_rule.json` evidence (T-F6) and the not-recorded count (T-P3).

## 10. Testing Strategy: triggered directives

D0 (hygiene) always. The union by code shape: a pure function with a three-valued truth table (D1: property/table-driven unit tests, plus the mutation floor the repo applies to graders), a config/catalog parse (D2: schema validation, negative cases), a dispatch registry (A-series: a contract test per row of section 4.2), a golden/freeze control (the existing US-4 ring, plus a red test for each new branch), and a report change (D5: render and count tests). Mutation: `tests/mutations/pack_improvement.json` gains the mutant "`_pass` returns `False` for `None`"; `tests/mutations/formal.json` (X-G3) gains "NA input treated as 0" and "`any_of` for `all_of`". A test earns its place only if it catches a failure no other catches (memory rule): the table below names, per test, the failure it alone catches.

## 11. Test plan, by node id (red first; each is observed red on the un-fixed code before its fix)

| id | file::test (owner · phase) | catches (and nothing else does) |
| --- | --- | --- |
| T-C1 | `tests/test_catalog_version.py::test_catalog_has_the_eleven_property_metrics_with_the_fixed_fields` (X-G1 · E1) | an id, `kind`, `better`, `scale`, `property` tag, `grader`, `weight` or area differing from W0 section 7 |
| T-C2 | `::test_every_property_metric_anchor_is_in_a_permitted_r79_form_and_points_the_right_way` (X-G1) | an unmarked anchor or a reversed direction |
| T-C3 | `::test_the_committed_06_metrics_copy_hashes_to_the_pinned_06_catalog_hash` and `::test_every_06_entry_is_unchanged_in_07_except_pass_at_1_also_graded_by` (X-G1) | a 0.6 definition edited in the 0.7 commit |
| T-C4 | `::test_a_property_tag_outside_the_five_names_is_refused` (X-G1; production check if the seam is granted) | FM3 |
| T-C5 | the existing `test_a_weight_changed_without_a_bump_is_red_through_b` (no new test) | T2 |
| T-R1 | `tests/test_grade_runner.py::test_a_security_task_graded_by_property_writes_exactly_two_property_rows_and_the_pass_completes` (X-F · E1; R-90 condition 5) | the narrowing, and GradedOncePerPass green |
| T-R2 | `::test_applicable_with_no_property_keeps_only_untagged_metrics` (X-F) | the `property=None` branch, the task-changed fallback |
| T-R3 | `::test_pass_at_1_has_one_owner_when_correctness_and_formal_are_both_named` (X-F) | FM5 (G1 shape) |
| T-R4 | `::test_a_formal_only_task_gets_pass_at_1_from_formal` (X-F) | the `also_graded_by` path (G2 shape) |
| T-R5 | `::test_the_task_changed_fallback_gives_pass_at_1_to_correctness_as_na` (X-F) | FM12 (the grid-3 shape) |
| T-F1 | `tests/test_grade_formal.py::test_pass_rule_is_a_three_valued_and` (parametrised table: all 1; one 0 with others 1; one 0 with an NA; one NA with others 1; all NA; cascade `0` then NA, NA) (X-G3 · E3) | the truth table; mutants "NA as 0", "any NA gives NA" |
| T-F2 | `::test_g2_task_yaml_declares_the_three_input_pass_rule` (X-G3) | the rule drifting from the design |
| T-F3 | `::test_an_unavailable_toolchain_gives_pass_at_1_na_not_zero` (X-G3) | FM4 |
| T-F4 | `::test_no_pass_rule_declared_is_na_not_zero` (X-G3) | FM2 |
| T-F5 | `::test_a_pass_rule_naming_an_unrecorded_metric_is_na_with_the_metric_named` (X-G3) | FM1 |
| T-F6 | `::test_pass_at_1_row_equals_the_rule_over_its_sibling_rows_and_writes_its_evidence` (X-G3) | the cache-equals-derivation rule (DM7); FM11 |
| T-F7 | `::test_changing_pass_rule_changes_the_task_version_hash` (X-G3) | S1 |
| T-F8 (slow ring) | `::test_g2_reference_records_pass_at_1_one_and_sorry_records_zero` over `tests/fixtures/grade/formal/g2/{reference,sorry}` (X-G3) | the rule wired to the real grader; needs Lean (`slow_ring` marker) |
| T-P1 | `tests/test_pack_improvement.py::test_a_cell_with_no_pass_at_1_is_not_a_failure` (X-A3 · E3) | the defect itself (red on `_passed`) |
| T-P2 | `::test_a_task_with_no_recorded_pairs_is_inconclusive_not_all_fail` (X-A3) | FM7; the grid-3 shape (12 NA cells) |
| T-P3 | `::test_headline_counts_failures_over_recorded_cells_and_states_the_unrecorded_count` (X-A3) | the `:1254` site and FM6 |
| T-P4 | `::test_pass_counts_and_holm_use_recorded_pairs_only` (X-A3) | the `:962`, `:1025` sites; Holm over tested tasks only |
| T-P5 | `::test_failing_test_names_ignore_unrecorded_cells` (X-A3) | the `:1151-1155` site |
| T-A1 | `tests/test_absence_not_failure.py::test_no_score_lookup_has_a_numeric_default` (X-A3; red on `board.py:480`) | the ABS-A class (shape recurrence) |
| T-U1 | `tests/test_catalog_version.py::test_07_regrades_the_x1_fixtures_to_the_06_goldens_on_every_06_metric` (X-G3) | any 0.6 score moved (EV-10); F5 |
| T-U2 | `::test_the_new_metric_ids_are_absent_from_the_x1_exports` (X-G3) | a property row leaking onto a non-property task |
| T-U3 | `tests/test_grade_formal.py::test_a_formal_only_cell_in_a_real_pass_gets_one_pass_at_1_row` (injected stub formal grader; X-G3) | Control 2: GradedOncePerPass with the `also_graded_by` row |
| T-U4 | `tests/test_catalog_version.py::test_a_correction_appended_with_a_linked_chain_is_accepted_by_e` (X-G3) | the exception works |
| T-U5 | `::test_a_rewritten_golden_without_a_correction_record_is_red_through_e`, `::test_a_correction_that_skips_a_link_is_red_through_e` (X-G3) | FM8, T1 |
| T-U6 | `::test_a_correction_naming_no_register_class_is_red_through_e` (X-G3) | R1 |
| T-U7 | `::test_the_control_prints_one_corrected_line_per_record` (X-G3) | F9: the chain is shown |

The `ABS-A` register entry is observed failing on the un-fixed tree by T-P1, T-P2 and T-A1 before any fix lands (CI: "a control is not a control until observed failing").

## 12. Ownership, ordering and seam requests

| item | state |
| --- | --- |
| `req-01M41DAHV9XTGBY1WES1R5VQH3` (to `coord-opus-e1e4`): `also_graded_by` and the owner rule inside X-F's `applicable` hunk | sent; sections 4.2 and 12 are **provisional (seam)** until granted. Fallback: design as written; X-G3 reopens if X-F did not land it |
| `req-01M41DAHY7DX8P705CRV31MQPA`: `grade/property.py` skeleton before X-G1's green, and two `config.validate_catalog` lines (X-A1) | sent. Fallback: injected `grader_modules` in the catalog test, and the tag check test-only |
| decision requests | none. Everything decided here is a narrowing or detailing of W0 section 7 and ADR-0019, not a widening |
| order | X-F skeleton joins, X-G1 (red then green), X-F `applicable`, X-A3 `_pass` fix, X-G3, Leader freeze (plan spine 7: `_passed` first, then X-G3) |
| hub files touched here | none: this design edits only `docs/design/eval-catalog-0-7.md` |

## 13. Spikes (Spike Protocol; read and run)

| spike | what it established | result |
| --- | --- | --- |
| SP-1 `g2spike.py` (scratchpad, ran) | which metrics the G2 cells hold in grid-3 and grid-4 | grid-4: no `pass_at_1` row (V). grid-3: 12 rows, all NA `task changed since the plan (version hash mismatch)` (V) |
| SP-2 `g2rule.py` (scratchpad, ran) | the proposed rule applied to the recorded scores | grid-4: 12 of 12 give `1`. grid-3: 12 of 12 give NA. `bugs_confirmed` is NA `no bug-report artifact defined for this task (not a bug-narrative task)` for G2 (V), which is why it is not an input |
| SP-3 (reads) | `config.py:151` duplicate-id refusal; `config.py` seven-area check; `runner.py:166-167` and `:358-365` dispatch and HB-GRD-004; `board.py` does not import `pack_improvement`; `bench verify` reads a run, not the freeze file | all V (opened) |

No external SDK, API or MCP contract is consumed, so no further spike applies.

## 14. Residual risk and flagged unknowns

| # | item | label |
| --- | --- | --- |
| U1 | **G2 is saturated** (12 of 12 pass in grid-4, SP-2). Recording `pass_at_1` makes the cell rankable but it cannot separate combos until G2 has a harder variant. Whether G2 counts toward EV-9's "at most four saturated calibration tasks" is a W1-H and plan decision, not this slice's. | V (data), decision open |
| U2 | Provisional count anchors (`idempotency_violations`, `hallucinated_symbol_errors`, `new_abstractions`, `new_dependencies`, `size_vs_reference`) are guesses by convention until E4 discrimination records give measured values; weight 0 contains the harm to the normalised display. Re-anchor at 0.8 or at the first saturation. | I, bounded |
| U3 | `pack_improvement.classify_group` input semantics (`n_pairs`) and `process.py:133` were not opened to the line; X-A3 opens both first. | I (check named) |
| U4 | The export fields that name the catalog (Control 1 normalisation) were not enumerated. X-G3 reads `views.export` first. If the comparison needs more than version and hash dropped, the test stops and reports instead of widening the drop list. | I |
| U5 | ADR-0019 wording to amend (Documentation Steward): item 6 and EV-10 name grid-3 and grid-4 fixtures (none committed, F4); item 4's "`bench verify` shows the chain" (F9); item 4's "can move the 0.6 `board_golden`" (F7: it cannot for the committed fixtures); item 5's `expected` set is the narrowed set (W0 section 2). | V |
| U6 | The `also_graded_by` key is the one new catalog concept. If the Coordinator refuses the seam request, the fallback is to add `correctness` to G2's `graders` and have `correctness.grade_cell` return the formal pass rule for a task with a `formal:` block, which breaks R-90's "pass_at_1 stays the formal grader's" and is the weaker design. | I |
| U7 | A real freeze run might move a golden contrary to F7. The correction mechanism is built for that; it is not assumed unused. | I |

## 15. Self-check against the definition of done (Stage 4, against `reference/definition-of-done.md`)

- [x] Single responsibility; boundaries named (section 1).
- [x] Data model first (section 3): aggregates with invariants, durable representation, grain, additivity, history rule, derive-don't-store with a rebuild test, writer and compute reader, expand-migrate-contract. The ADR for the durable representation is ADR-0019 itself (no new ADR: the representation is unchanged; the new key and the correction record are recorded here and in the amendment notes of section 14 U5).
- [x] E7 surface list (section 5).
- [x] Placed in the phasing; mock-substitutable seams (section 1).
- [x] Local conventions conformed to: `Score(None, reason)`, the existing control, R-79 note forms (section 4.1).
- [x] Contracts established from opened files; spikes run (section 13).
- [x] Patterns named and justified; Simplifier attack pre-empted (section 2). **Open:** the Patterns Expert and Simplifier reviews are pending (RV-PAT, RV-SIM); I did not clear them.
- [x] Ladder climbed; one `simplify:` marker (section 2).
- [x] Failure modes (section 6) and STRIDE-lite (section 7), each with a disposition; negative tests named (section 11).
- [x] Privacy: no personal data (section 8).
- [x] UI design: no user-facing interface in this slice (the report lines are X-H2's); stated, not omitted.
- [x] Testing Strategy union enumerated; every handled failure mode has a test id (sections 10-11).
- [x] Telemetry designed (section 9).
- [ ] Hard veto resolved: **RV-TA is pending**; the author does not clear it.
- [x] Confidence ledger and residual risk (section 14).
- [x] Status table below.

## Gate

`GATE w1-g-catalog-0-7 · pending · RV-TA (hard veto), RV-PAT, RV-SIM (soft veto)` — reviewers write their gate lines; the author copies them verbatim here after the follow-up. Findings that widen the slice go to the Coordinator.

## Status

| | |
|---|---|
| **Completed** | The design of W1-G: eleven catalog entries in full YAML, the dispatch amendment, the scenario-7 pass rule, the missing-pass fix with its sweep and class, the US-4 control and the `corrected_from` record, the failure-mode and STRIDE-lite tables, the telemetry and the named red-first test plan. |
| **Remaining** | Gate reviews (RV-TA, RV-PAT, RV-SIM); the two seam requests; the ADR-0019 amendment notes (section 14 U5); the build tracks X-G1 (E1), X-A3 and X-G3 (E3); the Leader's 0.7 freeze. |
| **Best next action** | RV-TA reviews this design; in parallel the Coordinator answers the two seam requests so X-F can include the `applicable` clause in its E1 hunk. |
