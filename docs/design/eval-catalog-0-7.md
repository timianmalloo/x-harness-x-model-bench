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
  regrade against the committed 0.6 goldens, with the 0.6 definitions read from the freeze commit. Revision 2 applies the
  three W1-G reviews, W0 rev 3 and R-95: the owner rule is ruled, and the corrected_from record is a written contingency.
---

# Catalog 0.7: property metrics, scenario-7 pass@1, the missing-pass@1 fix

**Slice:** W1-G, session `w1g-catalog-e1e4` (rev 2: `w1g-catalog-r2-e1e4`), tier T2, fan-out 0. Author: Claude Sonnet (`claude-sonnet-5-5`, R-91). 2026-10-03.
**Revision 2** (merged with `main` at `f41d2f20`: W0 rev 3 and R-95) applies `eval-review-{ta,pat,sim}-w1g.md`. Every change is in *Review disposition* at the end. Rev-2 text is marked "(rev 2, <finding>)". Code claims added in rev 2 were opened on the merged tree (the 0.6 freeze commit `d6dda42d` was extracted and hashed: section 13, SP-4).
**Inputs read on `3c1c9827`:** ADR-0019; spec EV-2..EV-6, EV-10, EV-11; W0 rev 2 sections 2, 7, 9, 11, 13, 14; R-59, R-79, R-86, R-90; `bench/metrics.yaml`, `bench/catalog-freeze.yaml`, `tools/freeze_catalog.py`; `report/pack_improvement.py`, `grade/formal.py`, `grade/runner.py`, `composites.py`, `config.py`, `board.py`, `tests/test_catalog_version.py`; `tasks/G1`, `tasks/G2`. Labels: **V** = Verified (opened or ran), **I** = Inferred (with the check that would confirm it).

## 0. Findings that shaped the design (each was checked, none assumed)

| # | Finding | Source | Effect on the design |
| --- | --- | --- | --- |
| F1 | `config.py` refuses a catalog that does not have exactly seven areas: `if len(metrics.get("areas") or {}) != 7` (V). | `config.py` end of `validate_catalog` | **No new area.** The eleven metrics go into existing areas (section 4.1). A new area would need a `config.py` change in X-A1's hub, and it would add a `measures` row to every board (`board.py:550, 770` iterate `cat.areas`), which moves board bytes for runs that have nothing to do with properties. |
| F2 | A metric's owner is its one `grader` string, and `applicable` groups by it (`runner.py:166-167`, V). `pass_at_1` is `grader: correctness`. G2's graders are `formal, drift, cost, process`, with no `correctness` (V, `tasks/G2/task.yaml`). A second entry with the same id is refused (`config.py:151`, V). | as cited | ADR-0019 item 3 ("the formal grader records `pass_at_1`") cannot be met by the formal grader alone: GradedOncePerPass would fail the pass with HB-GRD-004 on a key outside its applicable set (`runner.py:358, 365`, V). Section 4.2 adds one optional catalog key, `also_graded_by`. |
| F3 | G1 already names `correctness` (V, `tasks/G1/task.yaml:27-29`), so it already has a `pass_at_1` owner. | as cited | The owner rule (first of `[grader, *also_graded_by]` that the task names) keeps exactly one row per cell for G1 and G2. |
| F4 | The US-4 fixtures are two X1 mini-runs, `c44dd2b-no-heads` and `heads` (V, `tests/fixtures/ledger/`; `test_catalog_version.py:FIXTURES`). There is **no** committed grid-3 or grid-4 archive: `runs/` is git-ignored (V, `git check-ignore`). | as cited | ADR-0019 item 6 and EV-10 name "the frozen grid-3 and grid-4 fixtures". They do not exist as fixtures. The control is built on what is committed (section 4.5). The ADR wording is an amendment note, not a scope change. |
| F5 | The existing check (a) compares a fixture graded under the **current** catalog with the golden for the **current** version, so it is self-referential for a new version: the 0.7 golden is written from 0.7's own output. It cannot say "every 0.6 value is unchanged". | `test_catalog_version.py:60-110` (V) | The 0.6-to-0.7 claim needs a new cross-version test that compares 0.7's output with the committed **0.6** goldens (section 4.5). |
| F6 | The freeze control's check (e) fails if any `versions[v]` entry that exists at the merge base changes (V, `test_catalog_version.py:87`). ADR-0019 item 4's `corrected_from` edits the 0.6 entry. | as cited | **Rev 2 (Coordinator ruling on RV-SIM W1-G 2, W0 section 7):** the exception is **not built**. It is a written contingency (section 4.5) with a red-gate trigger. Until a gate goes red, (e) is unchanged. |
| F7 | `board.export` does not import `pack_improvement` (V, grep) and the two committed fixtures hold no scenario-7 cell (V). | as cited | The `_passed` fix **cannot move any committed 0.6 golden**. ADR-0019 item 4 says it "can". The correction record is therefore a written contingency, built only if a gate goes red (section 4.5). |
| F8 | Measured on `runs/grid-4` (V, scratchpad spike `g2rule.py`): all 12 G2 cells have `formal_checks_clean = statement_integrity = model_non_vacuity = 1`, and **no** `pass_at_1` row. On `runs/grid-3`: all 12 G2 cells have the three metrics NA and `pass_at_1` NA `task changed since the plan (version hash mismatch)`, which `_passed` counts as 12 fails. | scratchpad spike | The declared rule gives 12/12 = 1 on grid-4. G2 is saturated; recording `pass_at_1` makes it rankable but does not make it discriminate (section 14). Grid-3 shows the defect: 12 of 12 NA cells are read as failures. |
| F9 | `bench verify` verifies a run's ledger (`cli.py:349-356`, V). It does not read `bench/catalog-freeze.yaml`. | as cited | ADR-0019 item 4's "`bench verify` can show the chain" is not available. The chain is shown by the US-4 control's printed lines (section 4.5). Amendment note for the ADR. |
| F10 | `board.py:480` reads `c.scores.get("pass_at_1", Measure(0)).value == 1` (V). With a `None` value the comparison is false either way, so the result is the same as `Measure(None)`. | as cited | Same defect shape as `_passed` (absence given a failing default). Sweep row in section 4.4. |
| F11 | W0 section 9 lists `grade/property.py` as a new module (X-F), and `config.validate_catalog` refuses a grader with no module in `harness_bench.grade` (V, `config.py:158`). | as cited | Ordering (granted, W0 rev 3 section 7 condition 1, `req-01M41DAHY`): X-F's skeleton (docstring only) joins `main` before X-G1's green commit. **X-G1 never creates `grade/property.py`** (X-F's hub file). Until it joins, X-G1's catalog test injects `grader_modules`. |
| F12 (rev 2) | `catalog_hash` covers `bench/metrics.yaml` **and** every file under `bench/rubrics/` (V, `runner.py:108-112`), so a committed `metrics.yaml` copy alone cannot hash to the pin. `git archive d6dda42d bench/metrics.yaml bench/rubrics`, hashed with `catalog_hash`, gives `33bf6dff0ab1...c68f`, equal to `versions['0.6'].catalog_hash` (V, SP-4). | RV-TA W1-G 2 | The 0.6 definitions are read from git at the 0.6 freeze commit `d6dda42d`; nothing 0.6 is copied into the tree (also RV-SIM W1-G 5). |
| F13 (rev 2) | `heads` and `c44dd2b-no-heads` pin the same digest in `versions['0.6']`, for the views goldens and for the board goldens (V, `bench/catalog-freeze.yaml`). | RV-TA W1-G 1 | Control 1 rests on one export per surface. Its power comes from the red cases of section 4.5, not from the second fixture. |
| F14 (rev 2) | `config.validate_catalog` accepts a weight-0 `kind: score` metric with or without an `anchor`, and direction-checks an anchor when present (V, `config.py:160-175`). | RV-SIM W1-G 7 | Not needed for the design to hold: the eleven anchors stay because the plan row's done-when item names them (section 14, U2). |

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
| **Strategy via registry** (existing `GRADERS`) with an ordered first-match owner list (Chain of Responsibility, smallest form; RV-PAT W1-G, rev 2) | owner resolution picks which grader's function records a metric | unchanged mechanism; only the owner lookup grows | a second registered grader for `pass_at_1` (R-90 condition 4 refuses the same shape) |
| **Three-valued (Kleene) conjunction** | `pass_rule.all_of` | the smallest correct logic that never turns an unknown into a fail and never hides a definite fail | two-valued AND (a missing input reads as fail: the defect); "any NA gives NA" (hides a recorded 0) |
| **Append-only chain** (event-sourced correction), *contingency only* (rev 2) | `corrected_from` list | freeze entries are already append-only facts (DM5, DM11); a correction is a new fact that points at the old one. Written, not built (section 4.5) | overwrite the golden (refused by R-86 (B)) |
| **Parameter Object** (existing `CellInput`) | the formal grader reads `inp.task["formal"]["pass_rule"]` | no new plumbing | a new `CellInput` field |

**Simplifier's likely attack and my answer (pre-empted).** "`also_graded_by` is a new catalog concept for one metric." Answer: the alternatives are worse and cost more. A duplicate id is refused by `config.py:151`. A new id (`formal_pass`) breaks the board's primary, which reads `pass_at_1` by id (`board.py:190, 194`). Adding `correctness` to G2 yields an NA forever (G2 has no hidden-test oracle). A list-valued `grader` breaks every `m["grader"] in graders` reader. The key is one optional list, **validated at once** (rev 2, R-95 condition; RV-SIM W1-G 1): in `validate_catalog`, each name is a registered grader module, differs from the entry's `grader`, and does not repeat (section 4.2). The deferred-validation `simplify:` marker of revision 1 is **withdrawn**: a typo that silently means "no owner" is a missing guard on the first user, not a second use. **Ruled (R-95, DR-9, option A):** `applicable` carries two clauses, and the key stays. Ceiling of the mechanism: one key, precedence "first named". Upgrade trigger (R-95): a second metric that needs a different precedence turns the list into a rule, and comes back as a request.

## 3. The data model (settled first)

**Context and language.** Bounded context: *Metric Catalog and Scoring* (inside the benchmark's grading context). Ubiquitous terms: *catalog version* (a frozen snapshot of definitions), *metric* (a definition, a dimension row), *score row* (one recorded value or one recorded absence), *recorded* (a score row with a value), *not recorded* (a score row whose value is NA with a reason, or no row because the metric does not apply), *pass rule* (a task's declared definition of a pass), *correction* (a later fact that supersedes a frozen golden and keeps the old value).

**Aggregates (each with its one invariant).**

| aggregate (root) | invariant it protects | references others by |
| --- | --- | --- |
| **Catalog version** (root: the `version` string with its `catalog_hash`) | once frozen, a version's definitions, weights, anchors and rubrics never change (US-4, R-59). | identity: version string, hash |
| **Freeze record** (root: `versions[v]` in `bench/catalog-freeze.yaml`) | append-only: a pinned hash or golden is never overwritten. (Rev 2: a correction record that names the value it replaces is a written contingency, section 4.5.) | version string; fixture name |
| **Score row** (root: the ledger row, in the existing `scores` fact) | exactly one row per (grading pass, cell, applicable metric) (GradedOncePerPass); a value or an NA with a reason, never both, never a default. | `cell_id`, `metric_id`, `grading_id` |
| **Task version** (root: the task folder, hash `task_version_hash`) | the `pass_rule` and `expected` are inside the hash, so a rule change is a new task version. | `task_id` |

**Durable representation (DM5-DM6).** Metrics are a **dimension** with **Type-2 history by whole-version snapshot**: each `versions[v]` is a complete, immutable snapshot, and a change to any definition is a new version. This is already the representation; the decision here is to keep it and not add a column-level effective-date history (that would be a shadow schema over what `catalog_hash` already pins). Score rows are **append-only facts** (the existing `scores` ledger fact). The freeze file is a small append-only fact table of corrections (below).

**Grain statements.**

| table / fact | one row is exactly one | identified by | recorded when |
| --- | --- | --- | --- |
| `scores` (existing; gains rows for the eleven ids and for `pass_at_1` on formal-only tasks) | value-or-absence of one metric for one cell in one grading pass | (`grading_id`, `cell_id`, `metric_id`) | the pass writes it |
| `versions[v]` in the freeze file | frozen catalog snapshot pin for one version | `v` | the Leader's freeze commit |
| `versions[v].corrected_from[i]` (**contingency, not built**; rev 2) | one correction of one pinned golden of one version | (`v`, index `i`) | the Leader's correction commit, only after a gate goes red |
| catalog entry in `metrics.yaml` | one metric definition in one version | (`version`, `id`) | the catalog commit |

**Additivity of the eleven (DM9).**

| metric | scale | class | note |
| --- | --- | --- | --- |
| `property_check_pass`, `turn1_tests_pass`, `verified_before_use` | int 0/1 | additive as a count (summed to a pass count, reported as a rate) | rates are computed over recorded cells only |
| `idempotency_violations`, `hallucinated_symbol_errors`, `new_abstractions`, `new_dependencies` | int | additive within one task across cells; **never summed across properties** (a count of imports and a count of duplicate effects are not one quantity) | reported per task |
| `exploit_probes_blocked`, `fault_suite_pass`, `rework_ratio`, `size_vs_reference` | 4 places | **non-additive** (ratios): averaged per cell, never summed; a pooled ratio is recomputed from its numerators and denominators or not shown | the numerators live in the property evidence (W1-F) |

**History rule per attribute.** Every metric attribute (`kind`, `better`, `scale`, `anchor`, `weight`, `property`, `also_graded_by`) is **Type-2 by version**: a change is a new catalog version, so a past score never changes meaning. A Type-1 overwrite is a recorded decision to discard history; this design makes none. The one place history could be rewritten on purpose is a golden correction. It would be Type-2 too (the old value stays in the chain), and it is a contingency (section 4.5).

**Derive, don't store (DM7).** The narrowed metric set per task is **derived** by `applicable(catalog, graders, property)`; it is never stored on the task or the plan. The pack section's pass counts are derived from `scores`. `pass_at_1` for a formal task is *stored* as a fact (it is a score row), and it is computed from its sibling rows by the pass rule: this is a materialised derivation, so it is a labelled rebuildable cache with an equality test (section 11, `test_pass_at_1_row_equals_the_rule_over_its_sibling_rows`). Two definitions of "pass" for one cell is the defect signature: there is one function, `formal.pass_at_1(task, scores)`, and one reader of "recorded", `_pass(cell)` (section 4.4).

**Writer and compute reader of every persisted field (DM15).**

| field | writer | compute reader |
| --- | --- | --- |
| catalog entries (eleven + `pass_at_1` key) | X-G1 (`metrics.yaml`) | `runner.applicable`, `composites.load_catalog`, `config.validate_catalog`, `catalog_hash` |
| `property:` tag | X-G1 | `runner.applicable`; `readiness.py` (through the same function, R-90 condition 1) |
| `also_graded_by` (rev 2, RV-PAT W1-G 2: every reader of the owner field named) | X-G1 | **changed:** `runner.applicable` (owner rule); `config.validate_catalog` (new checks, section 4.2). **Unchanged, because each reads the primary `grader` only, which stays a string:** `runner.py:321` (task-changed fallback: it builds `names` from `m["grader"]`, so a changed task gets `correctness` as the `pass_at_1` owner and the NA lands in the `correctness` evidence folder: pinned by T-R5); `pack_improvement.py:491` (`m.get("grader") in task_graders`, judge ids only); `composites.load_catalog` (reads ids and weights); `catalog_hash` (hashes bytes) |
| `formal.pass_rule` | X-G3 (`tasks/G2/task.yaml`) | `formal.pass_at_1`; readiness (`pass_rule_problems`) |
| `pass_at_1` score row (formal task) | `formal.grade_cell` via the runner | `board.py`, `composites.gated`, `pack_improvement._pass`, `html.py` |
| `versions[v].corrected_from` (contingency; rev 2) | the Leader, by hand, only after a gate goes red (section 4.5); no tool flag exists or is built | none until built |

**Migration (expand, migrate, contract; DM16).** *Expand:* 0.7 adds entries and two optional keys; no 0.6 entry changes except `pass_at_1` gains `also_graded_by` (a definition-adjacent key: the entry's bytes change, so `catalog_hash` changes, which is why this is a new version; R-95 amends R-90 condition 6 for exactly this edit). *Migrate:* none; there is nothing to backfill. Old runs keep their graded-under version (R-59 condition 1; grid-3 and grid-4 are never re-scored, EN9). A re-grade of a grid-3 or grid-4 G2 cell under 0.7 would record `pass_at_1` only if the task version still matches the plan; it does not (grid-3: `task changed`, V), so those cells stay un-rankable (ADR-0019 item 3). *Contract:* none; no key is removed. Rollback: revert the `metrics.yaml` commit; a frozen 0.7 is never unfrozen, a defect is `0.8`.

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

### 4.2 Dispatch-rule amendment (text for `design-phase3-graders`, R-90 condition 5; ruled R-95)

The Documentation Steward lands this text. It extends the current rule ("The applicable set is every `kind: score` catalog metric of those graders", `runner.py:16-20`). **Ruled (R-95, DR-9, option A; rev 2):** `applicable(catalog, graders, prop)` carries two clauses, the `property:` narrowing and the owner rule. R-95 amends R-90 conditions 1 and 6 (the `pass_at_1` entry gains `also_graded_by: [formal]`; its bytes change in 0.7). Nothing in this section is provisional. The W0 section 7 text drops "provisional" and ADR-0019's item-3 note is updated by X-G1 in the `metrics.yaml` commit that adds the key (R-95 condition 4).

> **Dispatch, amended for catalog 0.7 (R-90, R-95).** `applicable(catalog, graders, prop)` returns, for each grader a task names, the `kind: score` metrics that grader owns *for this task*. A metric with a `property:` tag applies only when the tag equals `prop` (the task's `property.name`, or `None` when the task has none or has changed). A metric without the tag always applies. A metric's *owner* is the first grader in `[grader, *also_graded_by]` that the task names; the metric is in the owner's set and in no other, so each (cell, metric) gets exactly one row. A metric outside the narrowed set has no row; it is not "NA not built". **Task-changed fallback:** when the runner has no task (`runner.py:318-321`, every catalog grader is "named"), the owner of `pass_at_1` is `correctness`, and its NA `task changed` row lands in the `correctness` evidence folder. Readiness reads the narrowed set through this function (R-90 condition 1).

```python
def applicable(catalog: dict, graders: list[str], prop: str | None = None) -> dict[str, dict[str, dict]]:
    out: dict[str, dict[str, dict]] = {}
    for area in catalog["areas"].values():
        for m in area.get("metrics") or []:
            if m["kind"] != "score":
                continue
            tag = m.get("property")
            if tag is not None and tag != prop:
                continue
            owner = next((g for g in (m["grader"], *m.get("also_graded_by", ())) if g in graders), None)
            if owner is not None:
                out.setdefault(owner, {})[m["id"]] = m
    return out
```

(Rev 2: the parameter is `prop` and the tag test is two steps, as W0 rev 3 section 7 condition 1 fixes it; RV-PAT W1-G 3. With `prop=None`, only untagged metrics apply.) X-F owns this hunk in E1, with T-R1..T-R5 in `tests/test_grade_runner.py`. The clause was requested as `req-01M41DAHV9XTGBY1WES1R5VQH3` (granted in part) and ruled by the Owner as R-95.

**Catalog validation (rev 2; W0 rev 3 section 7 condition 1, `req-01M41DAHY`, R-95 condition; RV-SIM W1-G 1, RV-PAT W1-G 2 and 5).** `config.validate_catalog` gains, at once: (1) a `property:` tag is one of `config.PROPERTY_NAMES` (the one list of the five names; `task.yaml`'s `property.name` and `grade/property.STRATEGIES` are keyed by it, so T-C4 asserts that link, not a literal); (2) each `also_graded_by` entry is a grader module (the existing `grader_modules` check at `config.py:158`), differs from the entry's `grader`, and does not repeat. X-A1 lands both (seam `req-01M41DAHY`). Until X-A1 lands them, T-C4 and T-C6 run against `validate_catalog` with the red fixtures named in section 11 and are marked `xfail(strict=True)` in X-G1's commit, so they fail loudly when the check arrives.

**The non-owner guard (rev 2; W0 rev 3 section 7, RV-PAT W1-G 1).** On a task that names both `formal` and `correctness` (G1), `correctness` owns `pass_at_1`, so `formal`'s `inp.metrics` lacks it. A grader that returns a key outside `inp.metrics` fails the pass with HB-GRD-004 (`runner.py:350`). `formal.grade_cell` therefore emits `pass_at_1` only when it is in `inp.metrics`. X-F owns that line and T-R6 (G1-shaped task through a real `run_pass`: one `pass_at_1` row, no HB-GRD-004; red against an unguarded `grade_cell`). This design states the guard; it does not edit `formal.py` before X-G3's `pass_at_1` exists (X-F lands the guard line with the skeleton of the call, X-G3 adds the rule).

**Worked cases (all asserted by tests in section 11).**

| task graders | `prop` | rows for `property_check_pass`, `exploit_probes_blocked`, `fault_suite_pass` | rows for `pass_at_1` |
| --- | --- | --- | --- |
| `correctness, property` | `security` | `property`: the first two only | `correctness` |
| `correctness, property` | `resilience` | `property_check_pass` and `fault_suite_pass` | `correctness` |
| `formal, drift, cost, process` (G2) | `None` | none (`property_check_pass` is untagged but its grader `property` is not named) | `formal` (owner by `also_graded_by`) |
| `formal, correctness, ...` (G1) | `None` | none | `correctness` (primary owner wins; `formal` records no second row, by the guard) |
| task-changed fallback (`runner.py:318-321`: every catalog grader "named") | `None` | `property_check_pass` NA `task changed` under `property`, no tagged rows | `correctness` NA `task changed`, evidence folder `correctness` (pinned by T-R5; for a current G2 task the same cell's owner is `formal`, so the folder moves with task state: this is consistent with grid-3, and the move is stated here, RV-PAT W1-G 6) |

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

**Semantics (a pure function, `formal.pass_at_1(task, scores) -> Score`, three-valued).** The rows are evaluated **in this order** and the first that matches decides (rev 2, RV-PAT W1-G 4: one state, one reason):

| order | rule inputs | result | reason |
| --- | --- | --- | --- |
| 1 | no `pass_rule` declared | NA | `no pass rule declared` (never 0) |
| 2 | the rule names a metric the grader does not record (not in `inp.metrics`, so also not recorded) | NA | `pass rule names an unrecorded metric: <id>` |
| 3 | any input is `0` | `0` | none (a recorded failure decides even when another input is NA) |
| 4 | no input is `0`, any input is NA | NA | `pass rule input not recorded: <first metric id>` |
| 5 | every input is `1` | `1` | none |

An unknown metric name is a rule error, so it beats a recorded `0` (order 2 before 3); readiness already refuses it (`pass_rule_problems`), and the grade-time row is the degraded form of the same state. The "absent from the scores mapping" case is order 4 (a recorded-nothing input), not a second row. T-F9 pins the order: the input `[unknown id, 0]` gives NA (order 2), and the mutant that swaps orders 2 and 3 gives `0`.

A cascaded cell (`statement_integrity = 0`, the other two NA `given statements edited`) gives `0` by order 3: editing the given statements is a fail, not an unknown. The evidence of the `pass_at_1` score is `grading/<id>/<cell>/formal/pass_rule.json` (`{"inputs": {id: value|null}, "result": 1|0|null}`), so the row can be re-derived from its inputs without trusting the code.

**G1.** G1 names `correctness` (F3), so its `pass_at_1` is the correctness grader's; `formal.pass_rule` is not read for G1 and G1 declares none. `model_conformance` is NA `not built` for G1 (`formal.py:17, 47`, V), so no honest G1 rule exists yet. Not in scope.

**Task-version consequence (ADR-0019 item 3, council D4).** Adding `pass_rule` changes the G2 task version hash, so grid-3 and grid-4's G2 cells (planned under the old version) stay un-rankable; only a new run records it. `bench/task-freeze.yaml` has no G2 entry (V: `grep` found none), so no task freeze needs re-pinning; the Leader re-checks this at the join. The `statement_hash` is untouched (it hashes the statements, not `task.yaml`).

**Effect on boards, stated plainly.** In a new run under 0.7, a G2 cell that fails its proofs now gets `pass_at_1 = 0`, so `composites.gated` returns 0 for it (V, `composites.py:120-121`) where it used to be NA. That is the intended change (G2 becomes rankable) and the reason `catalog 0.7` is a new version. It cannot appear in the two committed X1 fixtures.

### 4.4 The missing-pass@1 fix (ADR-0019 item 4) and its sweep

**The rule.** *Absence is not failure.* A cell whose `pass_at_1` is missing or NA is **not recorded**: out of every pass count, every fail count and every denominator, and listed as not recorded with its reason. A recorded `0` is a fail.

**The single reader.** Replace `_passed(c) -> bool` (`pack_improvement.py:1173-1175`) by `_pass(c) -> bool | None`: `True` for value 1, `False` for value 0, `None` for missing or NA. All call sites then take a position on `None`.

**One count, two jobs, split (rev 2, RV-TA W1-G 6; U3 closed).** `n_pairs` is today both the quality denominator (`saturated`, `floor`, `ceiling_off`, the `n_pairs < 3` rule at `:511`) and the ratio denominator (`n_pairs < 2` at `:567`, the token and wall ratios). Opened: both jobs exist (V, `:497-538, 567`). Decision: **`GroupClassInput` gains `n_recorded`**. Every quality rule and every `n - passes` site reads `n_recorded`; `n_pairs` stays for the ratio rules and the row's display. The two counts are equal when every `pass_at_1` is recorded, so nothing moves for a complete run.

| site (V, `pack_improvement.py` unless noted; sweep run on tree `0fc300af`) | today | after |
| --- | --- | --- |
| `:962-966` per-task `passes_on/off`, `n = len(task_pairs)`, Fisher `n - passes_on` | `None` counts as a fail; `n` counts every pair | `recorded = [p for p in task_pairs if _pass(p.on) is not None and _pass(p.off) is not None]`; passes, `n` and the Fisher `n - passes` are over `recorded`; a task with `len(recorded) == 0` is not tested (no Fisher, not in Holm) and is `TaskInconclusive(task, ("pass_at_1 not recorded: <reason>",))` |
| `:1025-1026` per-group counts | same | same `recorded` filter gives `n_recorded`; `n_pairs = len(group_pairs)` is kept for the ratios; a group with `n_recorded == 0` goes down the existing "not enough pairs" path (`n_pairs < 3` becomes `n_recorded < 3`) |
| `:1053` `harm_groups_failed_pairs += max(0, n_pairs - passes_on)` | every unrecorded pair becomes a failure by subtraction | `max(0, n_recorded - passes_on)` |
| `:1151-1155` failing-test names for the "same failure in both arms" check | `not _passed` includes unrecorded cells | `_pass(...) is False` only |
| `:1244-1245` headline `b = n - passes_on`, `d = n - passes_off` (`n` summed from `task_counts`) | follows `n` | `n` is already over recorded pairs (from the first row); no code change beyond that |
| `:1254` `on_failures = ... not _passed(c)` in the headline | unrecorded on-cells are "pack-on failures" | `_pass(c) is False`; the headline gains `, k_on pack-on and k_off pack-off cells not recorded` when either is above 0 (rev 2, RV-TA W1-G 7: the two counts are stated separately, so an arm-asymmetric cause is visible) |
| `:858-870` `p1_value` | already `None`-safe (V) | unchanged |
| `board.py:480` `scores.get("pass_at_1", Measure(0)).value == 1` | default `Measure(0)` | `Measure(None)`; no behaviour change (F10), removes the copy-paste trap |
| `board.py:319, 226, 267, 405-408, 583-599` | already guard `None` or default `Measure(None)` (V) | unchanged |
| `composites.py:120-126` `gated` | `None` gives NA `pass_at_1 not recorded` (V) | unchanged |

**Why the Fisher input is the recorded pairs only.** Counting an unrecorded cell as a fail makes the arm that has more unrecorded cells look worse for a reason unrelated to the pack. Removing the pair from both arms keeps the two counts over the same pairs, which is what the existing test already assumes (`n` shared by `on` and `off`).

**Defect class (CI2: class, sweep, derive, prevent).** New class **ABS-A: absence read as failure** (an unrecorded value given a failing default, so the report counts what it never measured as a failure). *Rev 2: the class has two shapes.* (1) **A numeric default** on a score lookup. (2) **A failure derived by subtraction**: `n - passes` over a denominator that counts unrecorded cells (`:966`, `:1053`, `:1244-1245`). *Sweep run on tree `0fc300af` (V):* shape 1: **1** hit (`board.py:480`); `_passed(` call lines: **7** (`:962, 963, 1025, 1026, 1152, 1155, 1254`) plus the definition at `:1173`; shape 2: **4** hits (`:966, 1053, 1244, 1245`). `process.py:133` (`stuck.value == 0`, in a function that returns a Score for an agent end first; **I**: X-A3 opens it) and `pack_improvement.py:1016, 1183` (`== 0` after `is not None`: V, safe) are not instances. *Derive:* the invariant "a lookup default is `None`; a comparison to a number needs the `None` branch decided; a failure count is a recorded 0, never `n - passes`". *Prevent (control):* `tests/test_absence_not_failure.py` has two scans, each with its red fixture (section 11, T-A1 and T-A2) and each asserting the **same set** as the sweep (shape 1: `{board.py:480}` before the fix, empty after; shape 2: the four lines before, none after except the ones that read `n_recorded`), plus the behavioural tests, which were observed red on the un-fixed code. X-A3 adds the register entry to `docs/lessons/defect-classes.md` in the same commit (CI6).

### 4.5 The US-4 control (cross-version regrade) and the `corrected_from` contingency

**Control 1: the cross-version regrade (EV-10, ADR-0019 item 6; F4, F5, F12, F13).** One function, `cross_version_problems(root, root06, golden06, freeze, export, board_export) -> list[str]`, in `tests/test_catalog_version.py` beside `us4_problems`, taking the exports as callables as `us4_problems` does, so a red fixture can inject a bad export. It returns the problems; the real-tree test asserts `[]`. Steps, in order (rev 2, RV-TA W1-G 1, 2, 5, 10):

1. **The 0.6 goldens are pinned here, not only by check (c).** Check (c) globs `golden/<current version>` only, so once 0.7 is current nothing else checks `versions['0.6'].golden`. Control 1 hashes each `tests/fixtures/catalog/0.6/*.export` and `*.board.export` and requires equality with `versions['0.6'].golden[fixture]` and `.board_golden[fixture]`. Regenerating a 0.6 golden from 0.7 output (GLD-A) is red here.
2. **The 0.6 definitions come from git, not from a copy.** `root06` is the result of `git archive d6dda42d bench/metrics.yaml bench/rubrics`, where `d6dda42d` is the 0.6 freeze commit (a constant in the test; CI checks out with `fetch-depth: 0`, V `ci.yml:25,45`; an unreachable commit **fails** with a message, never skips). `runner.catalog_hash(root06)` must equal `versions['0.6'].catalog_hash` (SP-4: it does), and every 0.6 entry must equal the same-id entry of the current catalog except `pass_at_1`'s added `also_graded_by` (RV-SIM W1-G 5: no committed 0.6 copy, so no second source of 0.6 truth; it also removes the hash that could never match, RV-TA 2).
3. **Regrade.** For each fixture (`c44dd2b-no-heads`, `heads`): grade it under the 0.7 catalog (`graded_export`, `graded_board_export`) and compare **both surfaces** with the 0.6 goldens: the views export and the board export (the board is the surface that iterates `cat.areas`, `board.py:550, 770`, so a weight-0 entry would move bytes there first; RV-TA 5). Normalisation is **exactly one substitution**: the value of `catalog_version` (`"0.7..."` to `"0.6"`) in the export. Any other byte that differs is red. There is no open-ended drop list (RV-TA 10). **I:** the board export may carry no `catalog_version` at all; X-G3 reads both goldens first, and if any other field names the catalog the test stops and reports instead of widening the substitution (U4).
4. **No leak.** None of the eleven ids appears in either 0.7 export (X1's graders do not name `property`).

Both fixtures pin one digest each per surface (F13), so the control compares one export per surface; its power is the red cases below.

**Red cases (the control's own tests; each is observed failing before the control is called done).**

| id | input | the assertion that must fail the control | why it is a real red |
| --- | --- | --- | --- |
| T-U1a | monkeypatch one X1 grader so one 0.6 metric of one cell moves (the shape of `test_a_grader_change_without_a_bump_is_red_through_a`) | `cross_version_problems(...)` names the surface and fixture | step 3 byte equality |
| T-U1b | a copied 0.7 root where one existing 0.6 `correctness` metric has its weight changed | non-empty; names the board export (composites moved) | the weight-0 safeguard is what keeps 0.6 scores fixed |
| T-U1c | a copy of the 0.6 golden with one byte edited, and, separately, a golden regenerated from 0.7 output | non-empty; names the pin mismatch | step 1 (the GLD-A case) |
| T-U1d | `root06` with `metrics.yaml` edited, and one with a rubric added | non-empty; names the hash | step 2 |
| T-U2 | an `export` callable that returns the real export plus one score row for `exploit_probes_blocked` | non-empty; names the id | step 4. The injection is the red fixture because the real pipeline cannot produce the row for an X1 task, which is exactly what is being asserted |

Skeleton-first (floor item 1): X-G3's first commit adds `cross_version_problems` returning `[]` and these tests; they fail on `assert problems` (not on an import). The second commit implements the steps and they go green. The real-tree test (T-U1) is green on arrival by design: it is the regression guard, and T-U1a..d are the proof that it can fail.

**Control 2: the formal-only shape.** No committed scenario-7 archive exists (F4). The shape is proved by T-R4 (X-F), which is a real `run_pass` over a G2-shaped task (`graders: [formal]`, `formal.pass_rule`) with the formal grader injected as a stub that returns known `Score`s, and asserts exactly one `pass_at_1` row and a completed pass (GradedOncePerPass green). The stub's real-wiring counterpart is T-F3 (the real `formal.grade_cell` through `run_pass` with no toolchain) and the slow-ring T-F8 (real Lean). Rev 2 (RV-SIM W1-G 4): the separate T-U3 fixture is dropped, because T-R4 proves the same thing. No grid archive is copied into the repo.

**The `corrected_from` record: a written contingency, not built (Coordinator ruling on RV-SIM W1-G 2, W0 section 7; ADR-0019 *Amendment 1*).** F7 shows that no committed golden can move, and the design said "expected use: none". The following is the **specification to build if a gate goes red**; no code, no `--correct` flag (RV-TA 9: the Leader edits the YAML by hand and the control is the only gate), and no T-U4..T-U7 are built now. The W1-G plan row's done-when item for the record is met by this written contingency.

*Trigger:* X-G3's before/after run of Control 1 and the existing checks shows a moved golden hash. The existing freeze check already fails on a moved hash, so the trigger is a red gate. Until then check (e) is unchanged, and Control 1 does not read `corrected_from`.

*Record shape:*

```yaml
versions:
  '0.6':
    board_golden:                         # the NEWEST value; the golden check reads this
      c44dd2b-no-heads: <new sha256>
      heads: <new sha256>
    corrected_from:                       # append-only list, oldest first
      - key: board_golden                 # golden | board_golden
        was: { c44dd2b-no-heads: <old sha256>, heads: <old sha256> }
        defect_class: ABS-A               # must exist as "### ABS-A" in docs/lessons/defect-classes.md
        commit: <sha of the code commit that moved the bytes>
```

*Smallest form to build (the ruling):* check (e) admits only an appended record whose `was` equals the base value of `key`, with `key`'s new value different from `was`. *If more of the clauses are built, each needs its own failing test (rev 2, RV-TA 3 and 4):* (i) the earlier records are an unchanged prefix (test: a removed or reordered earlier record); (ii) the chain links with no gap; (iii) `now != was` (test: `was == now`); (iv) `defect_class` is a register heading and `commit` resolves with `git cat-file -e <sha>^{commit}`, not only hex (test: an unknown 40-hex sha); (v) every other key of the entry, including `catalog_hash` and `golden`, is byte-equal to the base (test: a valid record appended together with a `catalog_hash` edit; no mutant that drops (v) may survive). Printed line per record: `corrected: 0.6 board_golden <was12> -> <now12> (ABS-A, <sha7>)`. Add a `simplify:` marker when built (ceiling: one chain, one key kind; trigger: the first real correction; RV-PAT W1-G 7).

**Freeze procedure for 0.7 (R-86 shape; the Leader).** (1) Commit 1 "release label 0.7": `version: "0.7"`, history clause, no other change. (2) Commit 2 "freeze 0.7": `python tools/freeze_catalog.py` (the Windows form), then `tests/fixtures/catalog/0.7/{c44dd2b-no-heads,heads}.{export,board.export}` and the appended `versions['0.7']` entry with `board_export_version: 3` (EXPORT_VERSION is unchanged: no statistics change). (3) `uv run pytest -q tests/test_catalog_version.py tests/test_freeze_catalog.py tests/test_views.py tests/test_grade_runner.py tests/test_grade_formal.py`, output read, not the exit code.

## 5. Change-surface list (E7): store, model, service, wire, client, UI, compute reader

| layer | surface | change | owner · phase |
| --- | --- | --- | --- |
| store | `bench/metrics.yaml` | eleven entries, `pass_at_1` key, `version`, header comment | X-G1 · E1 (`.dev`), X-G3 · E3 (release label), Leader (freeze) |
| store | `bench/catalog-freeze.yaml` | `versions['0.7']`; (`corrected_from` only if the contingency fires) | Leader |
| store | `tests/fixtures/catalog/0.7/**` | new (rev 2: no `0.6/metrics.yaml` copy; the 0.6 definitions are read from git at `d6dda42d`) | X-G3 |
| store | `tests/test_catalog_version.py` | `cross_version_problems` and T-U1/T-U2 (it is a test file X-G3 extends) | X-G3 · E3 |
| store | `tasks/G2/task.yaml` | `formal.pass_rule` | X-G3 · E3 |
| model | `grade/runner.py: applicable` | `property` clause, owner rule (R-95) | X-F · E1 |
| model | `config.py: validate_catalog` and `config.PROPERTY_NAMES` | tag in `PROPERTY_NAMES`; `also_graded_by` is a grader module, differs from `grader`, no repeats | X-A1 · E1 (granted, `req-01M41DAHY`) |
| model | `grade/property.py` skeleton | docstring only; joins before X-G1's green commit. **Not X-G1's file** | X-F · E1 |
| service | `grade/formal.py` | the non-owner guard line in `grade_cell` (X-F · E1); `pass_at_1(task, scores)` called from it (X-G3 · E3) | X-F, X-G3 |
| service | `report/pack_improvement.py`, `board.py:480` | `_pass`, `n_recorded`, recorded pairs, the `n - passes` sites, headline | X-A3 · E3 |
| test | `tests/test_absence_not_failure.py` | the two ABS-A scans | X-A3 · E3 |
| projection / wire | `scores` fact rows; `views.export`; `board.export` | new rows for the eleven ids and formal `pass_at_1`; no schema change | none (existing columns) |
| client type | `views.CellView.scores` (a mapping of id to `Measure`) | none (open mapping) | none |
| UI | report tables (`html.py`, `cli_table.py`) | the EV-11 "not recorded in this run: ..." line already exists as a W1-H and X-H2 item; this design supplies the ids and reasons | X-H2 · E1 |
| compute reader | `readiness.py` (expected set), `gates.py` (pilot "never recorded"), `power.py` (primary metric) | read `applicable(...)` and `_pass`-style `None` handling | X-E, X-H1 |
| docs | `design-phase3-graders` amendment; ADR-0019 amendment notes (F4, F9); ADR-0019:49 item-3 note (R-95); `defect-classes.md` ABS-A | text in sections 4.2, 4.4, 14 U5 | Documentation Steward; X-G1 (ADR-0019:49, in its `metrics.yaml` commit); X-A3 |

## 6. Failure-mode analysis

| # | category | failure mode | disposition | detection (telemetry) | test |
| --- | --- | --- | --- | --- | --- |
| FM1 | input | a pass rule names a metric the grader does not record | prevent (readiness check `pass_rule_problems`, tested there once); degrade at grade time to NA with a reason (order 2 of the table, beats a recorded 0) | NA reason `pass rule names an unrecorded metric: <id>` on the row | T-F5, T-F9 |
| FM2 | input | no `pass_rule` on a formal-only task | mitigate: NA `no pass rule declared`, never 0 | the same reason in the not-recorded list | T-F4 |
| FM3 | input | `property:` tag misspelled in the catalog (`no_guessing`), or an `also_graded_by` name misspelled, repeated or equal to `grader` (a silent "no owner") | prevent: validation in `validate_catalog` (X-A1, granted); red fixtures in the catalog test | `bench validate` problem naming the metric | T-C4, T-C6 |
| FM4 | dependency | Lean or TLC unavailable, so a rule input is NA | mitigate: `pass_at_1` NA (not 0) with the first missing input named; the existing `NOT_WARMED` reasons flow through | NA reasons on the three input rows | T-F3 |
| FM5 | concurrency | two graders both record `pass_at_1` for one cell, or a non-owner `formal` emits a key outside `inp.metrics` | prevent: one owner by construction (section 4.2) and the guard in `formal.grade_cell` (emit only when in `inp.metrics`); detect if it recurs: GradedOncePerPass HB-GRD-004 (`written != 1`; key outside the applicable set, `runner.py:350`) | HB-GRD-004 | T-R3, T-R6 |
| FM6 | state | the pack section hides a real failure by dropping unrecorded cells, or an arm-asymmetric cause (a toolchain missing only on one arm) hides in one number | accept with a visible count: the headline and the inconclusive list state `k_on` and `k_off` not recorded separately; a recorded 0 is always counted | `k_on`, `k_off` in the headline | T-P3 (with `k_on != k_off`) |
| FM7 | state | all cells of a task unrecorded, so the task silently vanishes from the board | mitigate: the task is listed `inconclusive: pass_at_1 not recorded`; the pilot gate fails on "a metric that applies is NA in every cell of that task" (EV-11, W1-H) | inconclusive row; gate item | T-P2 |
| FM8 | state | a correction record skips a link or rewrites a past record | **not applicable until the contingency is built** (section 4.5): check (e) is unchanged and fails on any edit of a pinned entry | the existing (e) failure message | existing `test_an_edited_or_removed_freeze_entry_is_red_through_e` |
| FM9 | state | a golden is regenerated, hiding a real moved score | detect: Control 1 step 1 hashes the 0.6 goldens against `versions['0.6']` (so a regenerated 0.6 golden is red even once 0.7 is current) and step 3 compares 0.7 with the **0.6** golden | the control's problem list | T-U1c |
| FM10 | data | the 0.7 catalog changes a 0.6 score | prevent: weight 0 and no 0.6 entry edit; detect: Control 1 on both the views and the board export | the test | T-U1, T-U1a, T-U1b |
| FM11 | data | a rule evaluates over stale sibling rows from an earlier pass | prevent: `formal.pass_at_1` reads the `Score`s computed in the same `grade_cell` call, not the ledger | evidence file lists the inputs | T-F6 |
| FM12 | time | task-changed fallback pass gives `pass_at_1` to the wrong grader, or to the wrong evidence folder | prevent: owner rule gives `correctness` (NA `task changed`), evidence folder `correctness`; asserted | grid-3's recorded reason (V) | T-R5 |
| FM13 | resource | the new rows grow the ledger | accept: at most 11 rows per property cell and 1 per formal cell; the ledger already holds ~60 per cell (V: grid-3 G2 listed 60 metric ids) | row counts in the pass summary | none (negligible) |
| FM14 | integrity | the ADR names fixtures that do not exist | prevent: F4 recorded; the control uses the committed ones | n/a | T-U1 |
| FM15 (rev 2) | state | an unrecorded pair is turned into a failure by subtraction (`n - passes`) | prevent: `n_recorded` at every such site; scan T-A2 | `harm_groups_failed_pairs` over recorded only | T-P4, T-A2 |

## 7. Adversarial analysis (STRIDE-lite)

**Trust boundaries.** (B1) the agent's output tree is untrusted input to graders, but this slice reads only graders' *scores*, not the tree. (B2) `task.yaml` and `metrics.yaml` are repository content edited by authors (trusted-but-fallible; a malicious or mistaken author is the threat). (B3) the freeze file is Leader-owned; a worker edits it only by mistake. (B4) a report reader trusts the pack section's counts.

| id | boundary | threat | disposition |
| --- | --- | --- | --- |
| S1 | B2 | an author edits `pass_rule` to a weaker set after a campaign started | mitigate: the rule is inside the task version hash; a changed hash makes archived cells `task changed` (V, `runner.py:317`) and the campaign's identity check (ADR-0017) refuses a changed task |
| T1 | B3 | a worker rewrites a pinned golden "as a correction" | mitigate: check (e) is unchanged and fails on any edit of a pinned entry; check (c) pins digests and Control 1 step 1 pins the 0.6 digests after 0.7 is current; `bench/catalog-freeze.yaml` stays Leader-owned (R-86) |
| T2 | B2 | a weight raised from 0 on a property metric, silently changing composites | mitigate: `catalog_hash` covers `metrics.yaml`; check (b) fails any definition or weight edit without a bump |
| R1 | B3 | a correction with no attributable cause | not reachable until the contingency is built; its specification requires `defect_class` and a `commit` that resolves with `git cat-file` (section 4.5) |
| I1 | B4 | a NA reason carries agent text or a path | mitigate: reasons are the closed vocabulary of section 4.3 (metric ids from the catalog only), per `Score` rule "never agent text or a path" (V, `grade/__init__.py:31`) |
| D1 | B2 | a rule list of thousands of names slows grading | accept: `all_of` is read by a 3-line loop; authors are trusted; residual risk nil at this size |
| E1 | B1 | an agent writes a file that makes the rule read a wrong input | transfer (named): the inputs are the formal grader's own `Score`s, produced under that grader's existing STRIDE (`formal.py` module docstring, binary-artifact scan, G6/G10); this design adds no read of agent files |

Negative tests for the mitigations: the existing `test_an_edited_or_removed_freeze_entry_is_red_through_e` (T1), T-U1c (a regenerated 0.6 golden), T-C5 (weight edit without bump is red through (b), reuses the existing `test_a_weight_changed_without_a_bump_is_red_through_b`), T-F7 (changed `pass_rule` changes the task version hash).

## 8. Privacy (LINDDUN-lite)

No personal data: the slice defines metric names, anchors and rules, and reads scores of benchmark cells (no person). One line, an explicit negative.

## 9. Telemetry (IO1-IO12, O1-O13)

Questions an operator will ask, each with a named emitting source (no flag, on the normal path):

| question | source |
| --- | --- |
| How many cells of a task have `pass_at_1` not recorded, and why? | the pack section's inconclusive list and headline `k not recorded` (X-A3); the `scores` rows' `reason` (existing) |
| Which input decided a formal `pass_at_1`? | `grading/<id>/<cell>/formal/pass_rule.json`, referenced by the score's `evidence` |
| Did a property metric apply to this task? | the row exists or does not; `applicable(...)` is the single source (R-90) |
| Did a golden move, and why? | the control's problem list (names the surface, fixture and step); a `corrected_from` record if the contingency was built |
| How long does the pass rule take? | negligible (a loop over three values): not instrumented; **Inferred**, bound by the formal grader's existing `grading_step_timeout` span, which already measures the expensive part |

No new error codes (W0 section 11 reserves none for this track). Structured events: none new; a grader failure keeps `grade.grader_failed` (V, `runner.py:353`). No HTTP surface, so no RFC 9457 response. Load-bearing telemetry with a planned test: the `pass_rule.json` evidence (T-F6) and the not-recorded count (T-P3).

## 10. Testing Strategy: triggered directives

D0 (hygiene) always. The union by code shape: a pure function with a three-valued truth table (D1: property/table-driven unit tests, plus the mutation floor the repo applies to graders), a config/catalog parse (D2: schema validation, negative cases), a dispatch registry (A-series: a contract test per row of section 4.2), a golden/freeze control (the existing US-4 ring, plus a red fixture for each step of Control 1), and a report change (D5: render and count tests). Mutation: `tests/mutations/pack_improvement.json` gains the mutants "`_pass` returns `False` for `None`" and "`n_recorded` replaced by `n_pairs` at `:1053`"; `tests/mutations/formal.json` (X-G3) gains "NA input treated as 0", "any NA gives NA" and "orders 2 and 3 swapped". (Rev 2, RV-SIM W1-G 6: the "`any_of` for `all_of`" mutant is deleted; `any_of` is not an operator.) A test earns its place only if it catches a failure no other catches (memory rule): the table below names, per test, the failure it alone catches.

## 11. Test plan, by node id (rev 2: the testability floor, README section 2a)

Red-first. Per test the table states the assertion that fails today and why (floor 1; never an `ImportError`: where a symbol is new, a **skeleton commit lands first** and the test fails on a value), the red fixture for every guard or scan (floor 2), the real-wiring test beside every fake (floor 3), the mutant that separates adjacent rules (floor 4), and the tree scan behind every sweep claim (floor 5). **I:** test and helper names for code I did not open (`pack_improvement`'s section builder) follow the existing tests in `tests/test_pack_improvement.py`; the owning track opens them first.

| id | file::test (owner · phase) | the assertion that fails today, and why | red fixture / mutant / real wiring |
| --- | --- | --- | --- |
| T-C1 | `tests/test_catalog_version.py::test_catalog_has_the_eleven_property_metrics_with_the_fixed_fields` (X-G1 · E1) | `{eleven ids} <= catalog ids` fails: `bench/metrics.yaml` is 0.6 and holds none of them | mutant: one entry's `better`, `scale`, `property` or area differs from W0 section 7 |
| T-C2 | `::test_every_property_metric_anchor_is_in_a_permitted_r79_form_and_points_the_right_way` | the same presence assertion, first line of the test | fixture: a copied catalog with one `anchor_note` blank and one reversed anchor; both must be flagged |
| T-C3 | `::test_the_06_definitions_read_from_the_freeze_commit_hash_to_the_pin_and_are_unchanged_in_07_except_pass_at_1` (X-G1) | green on arrival (a guard); it fails when a 0.6 entry is edited | fixture: a copy of the current catalog with one 0.6 entry's `better` flipped must give a non-empty problem list; a second with `pass_at_1`'s `weight` changed likewise. Reads `git archive d6dda42d` (SP-4) |
| T-C4 | `::test_a_property_tag_outside_property_names_is_refused_and_property_names_match_the_strategy_keys` (X-G1; production check by X-A1) | `validate_catalog` returns no problem for a tag `no_guessing` today (the tag is unread): `assert problems` fails | fixture: a catalog copy with the misspelt tag. The link test (`config.PROPERTY_NAMES == property.STRATEGIES.keys()`) is X-F's skeleton, asserted here too |
| T-C5 | the existing `test_a_weight_changed_without_a_bump_is_red_through_b` (no new test) | none new | n/a |
| T-C6 (rev 2) | `::test_an_also_graded_by_name_that_is_unknown_equal_to_the_grader_or_repeated_is_refused` (X-G1; production check by X-A1) | `validate_catalog` ignores the key today: `assert problems` fails for each of the three fixtures | three catalog copies: `also_graded_by: [formla]`, `[correctness]` on a `grader: correctness` entry, `[formal, formal]`. Deleting the check turns it red |
| T-R1 | `tests/test_grade_runner.py::test_a_security_task_graded_by_property_writes_exactly_two_property_rows_and_the_pass_completes` (X-F · E1; R-90 condition 5) | through `run_pass` with a stub `property` grader and the 0.7.dev catalog: today `applicable` has no `prop`, so the pass fails HB-GRD-004 (the stub emits the two security rows; the unnarrowed set expects `fault_suite_pass` too) | mutant: narrowing removed. Real wiring: the same test uses the real `run_pass` and the real `applicable` |
| T-R2 | `::test_applicable_with_no_prop_keeps_only_untagged_metrics` (X-F) | through `run_pass` on a task-changed cell: tagged rows appear today | mutant separating the two clauses: `tag is not None and tag != prop` vs `tag != prop` (an untagged metric with `prop=None`) |
| T-R3 | `::test_pass_at_1_has_one_owner_when_correctness_and_formal_are_both_named` (X-F) | through `run_pass`: with `also_graded_by` in the catalog and no owner rule, both graders write the row and HB-GRD-004 fires | mutant: owner chosen as the last, not the first, named grader (G1 and G2 shapes differ: G1 `correctness` first, G2 `formal` only) |
| T-R4 | `::test_a_formal_only_task_gets_pass_at_1_from_formal` (X-F; **real `run_pass`** over the G2-shaped task with a stub formal grader; replaces the dropped T-U3) | today the formal-only task has no applicable `pass_at_1`: `rows == 1` fails with 0 and the pass is incomplete | real-wiring partner: T-F3 (real `formal.grade_cell`, no stub) |
| T-R5 | `::test_the_task_changed_fallback_gives_pass_at_1_to_correctness_as_na_in_the_correctness_folder` (X-F) | pins the owner and the evidence folder of the grid-3 shape; today's rows match (green), the folder assertion is new | mutant: fallback skips owner dispatch (owner `formal`): the folder assertion goes red |
| T-R6 (rev 2) | `::test_a_g1_shaped_task_through_a_real_pass_records_one_pass_at_1_row_and_no_hb_grd_004` (X-F) | against an unguarded `formal.grade_cell` that emits `pass_at_1`, `runner.py:350` records a key outside `inp.metrics` and fails the pass | mutant: the `"pass_at_1" in inp.metrics` guard removed. Real `run_pass`, real `formal.grade_cell` (toolchain absent, as T-F3) |
| T-F1 | `tests/test_grade_formal.py::test_pass_rule_is_a_three_valued_and` (X-G3 · E3; skeleton commit first: `pass_at_1` returns NA `not implemented`) | each row's value assertion fails against the skeleton | table: all 1; one 0 with others 1; one 0 with an NA; one NA with others 1; all NA; cascade 0 then NA, NA. Mutants "NA as 0" and "any NA gives NA" differ on `[0, NA, 1]` |
| T-F2 | `::test_g2_task_yaml_declares_the_three_input_pass_rule` | `tasks/G2/task.yaml` has no `pass_rule` | fixture: none (reads the real file) |
| T-F3 | `::test_an_unavailable_toolchain_gives_pass_at_1_na_not_zero` (X-G3; **real wiring**: the real `formal.grade_cell` through the real `run_pass`, no stub) | skeleton gives the wrong reason; today the row does not exist | mutant: the `pass_at_1` call removed from `grade_cell` leaves no row and HB-GRD-004 fires. **I:** the "toolchain unavailable" switch is the one `tests/test_grade_formal.py` already uses |
| T-F4 | `::test_no_pass_rule_declared_is_na_not_zero` | skeleton gives a different reason | none |
| T-F5 | `::test_a_pass_rule_naming_an_unrecorded_metric_is_na_with_the_metric_named` | skeleton | mutant: unknown id treated as absent (order 4) gives a different reason |
| T-F6 | `::test_pass_at_1_row_equals_the_rule_over_its_sibling_rows_and_writes_its_evidence` | no `pass_rule.json` exists | mutant: reads the ledger instead of this call's scores (FM11) |
| T-F7 | `::test_changing_pass_rule_changes_the_task_version_hash` | `task_version_hash` already covers `formal:` (green on arrival, a guard) | fixture: two copies of G2 differing in one rule entry; deleting `pass_rule` from the hashed set turns it red (S1) |
| T-F8 (slow ring) | `::test_g2_reference_records_pass_at_1_one_and_sorry_records_zero` | no `pass_at_1` row for either tree | needs Lean (`slow_ring`) |
| T-F9 (rev 2) | `::test_an_unknown_metric_beats_a_recorded_zero_in_the_pass_rule_order` | skeleton | input `[unknown id, 0]` must give NA (order 2); the mutant that swaps orders 2 and 3 gives `0` |
| T-P1 | `tests/test_pack_improvement.py::test_a_cell_with_no_pass_at_1_is_not_a_failure` (X-A3 · E3) | `_passed` returns `False` for a NA cell: the on-arm pass count is 2 of 3 instead of 2 of 2 recorded | mutant `_pass` returns `False` for `None` |
| T-P2 | `::test_a_task_with_no_recorded_pairs_is_inconclusive_not_all_fail` | 12 NA cells give 0 of 12: the task is tested and "fails" instead of `TaskInconclusive` | the grid-3 shape (12 NA cells) |
| T-P3 | `::test_headline_counts_failures_over_recorded_cells_and_states_k_on_and_k_off_not_recorded` | `:1254` counts the NA on-cell as a pack-on failure and states no count | input with `k_on = 2`, `k_off = 1` (`k_on != k_off`); mutant: one combined `k` |
| T-P4 | `::test_pass_counts_holm_and_harm_failed_pairs_use_recorded_pairs_only` | `harm_groups_failed_pairs` is `n_pairs - passes_on = 3 - 1 = 2` on a group of 3 pairs with 1 unrecorded and 1 pass, and must be `n_recorded - passes_on = 1`; Fisher gets `n - passes` over all pairs | mutant: `n_recorded` replaced by `n_pairs` at `:1053`. Asserts `harm_groups_failed_pairs` explicitly (RV-TA 6) |
| T-P5 | `::test_failing_test_names_ignore_unrecorded_cells` | `not _passed` includes unrecorded cells at `:1152, 1155` | none |
| T-P6 (rev 2) | `::test_the_quality_rules_read_n_recorded_and_the_ratio_rules_read_n_pairs` | a group of 4 pairs with 2 unrecorded: `saturated` and the `n < 3` rule see 4 today; they must see 2, while the ratio rule (`n_pairs < 2`) still sees 4 | the pair of rules that can give the same result: input with `n_pairs = 4`, `n_recorded = 1`, ratios valid; swapping the two fields in either rule gives a different class |
| T-A1 | `tests/test_absence_not_failure.py::test_no_score_lookup_has_a_numeric_default` (X-A3) | scan finds `board.py:480` (1 hit on tree `0fc300af`) | red fixture: a temp tree with `c.scores.get("x", Measure(0))` that the scan must flag, run before the real tree; asserts the real set equals the sweep set |
| T-A2 (rev 2) | `::test_no_failure_count_is_derived_as_n_minus_passes` (X-A3) | scan finds the four `n - passes` lines (`:966, 1053, 1244, 1245`) | red fixture: a temp file with `max(0, n_pairs - passes_on)`; the real tree passes only where the operand is `n_recorded` or a recorded-only `n` |
| T-U1 | `tests/test_catalog_version.py::test_07_regrades_the_x1_fixtures_to_the_06_goldens_on_both_surfaces` (X-G3) | green on arrival by design (regression guard); proved able to fail by T-U1a..d | real wiring: real graders, real `run_pass`, real `views.export` and `board.export` |
| T-U1a..d | `::test_cross_version_problems_is_red_for_*` (X-G3; skeleton commit first returns `[]`) | `assert problems` fails against the skeleton | the four red cases of section 4.5 (moved 0.6 value; weight changed; edited or regenerated 0.6 golden; edited `root06`) |
| T-U2 | `::test_the_new_metric_ids_are_absent_from_the_x1_exports` | the injected export holds `exploit_probes_blocked`: `assert problems` fails against the skeleton | fixture: an export callable that adds the row; deleting step 4 turns it green and the test red |

T-U3..T-U7 of revision 1 are **removed**: T-U3 is folded into T-R4 (RV-SIM 4); T-U4..T-U7 test the contingency, which is not built (section 4.5). The `ABS-A` register entry is observed failing on the un-fixed tree by T-P1, T-P2, T-P4, T-A1 and T-A2 before any fix lands.

## 12. Ownership, ordering and seam requests

| item | state |
| --- | --- |
| `req-01M41DAHV9XTGBY1WES1R5VQH3` (`applicable` clause) | **closed**: granted in part by W0 rev 3 (parameter `prop`, non-owner guard), and the owner rule **ruled by the Owner as R-95** (DR-9, option A, request `req-01M41E37FGK5CRZ7NCK3RA20JV`). Sections 4.2 and 12 are no longer provisional |
| `req-01M41DAHY7DX8P705CRV31MQPA` (join order; `validate_catalog` checks) | **granted**: X-F's `grade/property.py` skeleton joins before X-G1's green commit; X-G1 is given no file in `grade/`; X-A1 lands the checks and `config.PROPERTY_NAMES` |
| decision requests | `req-01M41E37FGK5CRZ7NCK3RA20JV` (DR-9) ruled R-95. Conditions that land here: `also_graded_by` validated at once (done, section 4.2; the deferred `simplify:` is withdrawn); the reader sweep complete including the task-changed fallback with the NA folder pinned (section 3, T-R5); W0 section 7 and ADR-0019:49 drop "provisional" (X-G1 does the ADR line in its `metrics.yaml` commit). No new request |
| order | X-F skeleton joins; X-F `applicable` clause and the `formal` guard; X-A1 `validate_catalog` checks; X-G1 (red then green; adds `also_graded_by`, updates ADR-0019:49); X-A3 `_pass` fix; X-G3; Leader freeze (plan spine 7: `_passed` first, then X-G3) |
| hub files touched here | none: this design edits only `docs/design/eval-catalog-0-7.md` |

## 13. Spikes (Spike Protocol; read and run)

| spike | what it established | result |
| --- | --- | --- |
| SP-1 `g2spike.py` (scratchpad, ran) | which metrics the G2 cells hold in grid-3 and grid-4 | grid-4: no `pass_at_1` row (V). grid-3: 12 rows, all NA `task changed since the plan (version hash mismatch)` (V) |
| SP-2 `g2rule.py` (scratchpad, ran) | the proposed rule applied to the recorded scores | grid-4: 12 of 12 give `1`. grid-3: 12 of 12 give NA. `bugs_confirmed` is NA `no bug-report artifact defined for this task (not a bug-narrative task)` for G2 (V), which is why it is not an input |
| SP-3 (reads) | `config.py:151` duplicate-id refusal; `config.py` seven-area check; `runner.py:166-167` and `:358-365` dispatch and HB-GRD-004; `board.py` does not import `pack_improvement`; `bench verify` reads a run, not the freeze file | all V (opened) |
| SP-4 (rev 2, ran) | `git archive d6dda42d bench/metrics.yaml bench/rubrics`, then `runner.catalog_hash` on the extracted root | `33bf6dff0ab185129d225339af80f3dd96882cbbcdaaad99879d461a5671c68f` = `versions['0.6'].catalog_hash` (V). The 0.6 definitions are recoverable from git alone |
| SP-5 (rev 2, ran) | the ABS-A sweep on tree `0fc300af` (grep over `src/harness_bench`) | numeric default: 1 hit (`board.py:480`); `_passed(` call lines: 7, plus the definition `:1173`; `n - passes`: 4 lines (`:966, 1053, 1244, 1245`) |

No external SDK, API or MCP contract is consumed, so no further spike applies.

## 14. Residual risk and flagged unknowns

| # | item | label |
| --- | --- | --- |
| U1 | **G2 is saturated** (12 of 12 pass in grid-4, SP-2). Recording `pass_at_1` makes the cell rankable but it cannot separate combos until G2 has a harder variant. Whether G2 counts toward EV-9's "at most four saturated calibration tasks" is a W1-H and plan decision, not this slice's. | V (data), decision open |
| U2 | Provisional count anchors (`idempotency_violations`, `hallucinated_symbol_errors`, `new_abstractions`, `new_dependencies`, `size_vs_reference`) are guesses by convention until E4 discrimination records give measured values; weight 0 contains the harm to the normalised display. Re-anchor at 0.8 or at the first saturation. Rev 2 (RV-SIM W1-G 7): `validate_catalog` would accept these five without an anchor (F14), but the plan row's done-when item names "anchors" for all, and W0 section 7 assigns them to this slice, so they stay; each wrong guess costs a catalog version, accepted. | I, bounded |
| U3 | **Closed (rev 2):** `n_pairs` has two jobs (opened, `pack_improvement.py:497-538, 567`) and is split with `n_recorded` (section 4.4). Still open: `process.py:133` (X-A3 opens it). | V; I |
| U4 | The export fields that name the catalog: the views golden carries `"catalog_version":"0.6"` (RV-TA 10); the board export golden was not opened. X-G3 reads both first; if another field names the catalog, the test stops and reports. | I |
| U5 | ADR-0019 wording to amend (Documentation Steward; W0 rev 3 records *Amendment 1*): item 6 and EV-10 name grid-3 and grid-4 fixtures (none committed, F4); item 4's "`bench verify` shows the chain" (F9); item 4's "can move the 0.6 `board_golden`" (F7); item 5's `expected` set is the narrowed set (W0 section 2); item 3's note at `0019:49` ("R-95: `also_graded_by: [formal]`", X-G1). | V |
| U6 | **Closed (rev 2):** the `also_graded_by` key is ruled (R-95). The fallback of revision 1 (add `correctness` to G2) is refused with option C. | V |
| U7 | A real freeze run might move a golden contrary to F7. The correction mechanism is a written contingency with a red-gate trigger (section 4.5); it is not assumed unused and not built now. | I |
| U8 (rev 2) | `formal`'s `pass_at_1` guard (X-F) and the `n_recorded` split (X-A3) are in other tracks' files; this design states them, it does not verify their landing. Join check: T-R6 and T-P6 are red until they land. | I |

## 15. Self-check against the definition of done (Stage 4, against `reference/definition-of-done.md`; rev 2 against README section 2a)

- [x] Single responsibility; boundaries named (section 1).
- [x] Data model first (section 3): aggregates with invariants, durable representation, grain, additivity, history rule, derive-don't-store with a rebuild test, writer and compute reader (rev 2: every reader of the owner field named), expand-migrate-contract.
- [x] E7 surface list (section 5).
- [x] Placed in the phasing; mock-substitutable seams (section 1).
- [x] Local conventions conformed to: `Score(None, reason)`, the existing control, R-79 note forms (section 4.1).
- [x] Contracts established from opened files; spikes run (section 13).
- [x] Patterns named and justified; Simplifier attack pre-empted (section 2). RV-PAT and RV-SIM have written their gate lines (Gate record).
- [x] Ladder climbed; the `simplify:` marker of revision 1 is withdrawn (R-95 condition) and the mechanism's ceiling and trigger are stated (section 2).
- [x] Failure modes (section 6) and STRIDE-lite (section 7), each with a disposition; negative tests named (section 11).
- [x] Privacy: no personal data (section 8).
- [x] UI design: no user-facing interface in this slice (the report lines are X-H2's); stated, not omitted.
- [x] Testing Strategy union enumerated; every handled failure mode has a test id (sections 10-11).
- [x] Testability floor (README 2a), per named test: (1) the failing assertion and why (section 11 column 3; skeleton commits named); (2) a red fixture for every guard or scan (T-C2, T-C3, T-C4, T-C6, T-A1, T-A2, T-U1a..d, T-U2); (3) the real-wiring partner for each fake (T-R4 with T-F3; T-R6; T-U1); (4) the separating mutant for each adjacent pair (T-R2, T-R3, T-F1, T-F9, T-P6); (5) the sweep checked against the tree (SP-5, T-A1 and T-A2 assert the same sets).
- [x] Telemetry designed (section 9).
- [ ] Hard veto resolved: **RV-TA's rev-1 BLOCK stands until the rev-2 re-review**; the author does not clear it.
- [x] Confidence ledger and residual risk (section 14).
- [x] Status table below.

## Gate

First-round gate lines, verbatim (rev 1, `b0987941`):

- `GATE W1-G · Test Architect · BLOCK · 10 findings (rv-ta-w1g-e1e4, 2026-10-03)`
- `GATE W1-G · Patterns Expert · PASS WITH CONDITIONS · 8 findings (rv-pat-gb-e1e4, 2026-10-03)`
- `GATE W1-G · Simplifier · PASS WITH CONDITIONS · 7 findings (rv-sim-gb-e1e4, 2026-10-03)`

rev 2 pending RV-TA.

## Review disposition (rev 2)

Source: `docs/design/reviews/eval-review-{ta,pat,sim}-w1g.md`. Disposition: **A** applied, **R** refused or reduced (with reason), **D** deferred (owner named), **S** superseded by a ruling.

| finding | disposition | where in this document |
| --- | --- | --- |
| RV-TA 1 (Control 1 and T-U2 have no failing test; the 0.6 goldens are identical) | A | section 4.5 red cases T-U1a..d and T-U2; F13; section 11 |
| RV-TA 2 (0.6 goldens unchecked once 0.7 is current; the 0.6 copy cannot hash) | A | section 4.5 steps 1 and 2; F12; SP-4. The committed copy is replaced by a read from git at `d6dda42d` |
| RV-TA 3 (the (e) exception has untested clauses) | S | W0 section 7 / Coordinator ruling: the exception is cut from E1 and deferred until a gate goes red; the contingency (section 4.5) lists a failing test per clause for when it is built |
| RV-TA 4 (`commit` only hex-checked) | A (in the contingency) | section 4.5: `git cat-file -e <sha>^{commit}` and a red test for an unknown sha |
| RV-TA 5 (board export not compared across versions) | A | section 4.5 step 3 compares the board export too |
| RV-TA 6 (`n - passes`; `n_pairs` doing two jobs) | A | section 4.4 (`n_recorded`, the site table, class shape 2); T-P4, T-P6, T-A2; U3 closed |
| RV-TA 7 (arm-asymmetric exclusions hidden) | A | section 4.4 headline states `k_on` and `k_off`; T-P3 with `k_on != k_off`; FM6 |
| RV-TA 8 (two designs claim one hunk) | S | R-95 and W0 rev 3: parameter `prop`, X-F owns the clause and T-R3..T-R6; section 4.2, 12 |
| RV-TA 9 (`--correct` does not exist; E7 omits `freeze_catalog.py`) | A | no flag is built; the Leader edits by hand (section 3 writer table, 4.5) |
| RV-TA 10 (open-ended drop list) | A | section 4.5 step 3: exactly one substitution of `catalog_version` |
| RV-TA, README 2a floor (five shapes) | A | section 11 columns; section 15 |
| RV-PAT 1 (non-owner `formal` trips HB-GRD-004) | A (stated; X-F owns the line) | section 4.2 guard paragraph; T-R6; FM5 |
| RV-PAT 2 (reader sweep for `also_graded_by`; catalog test) | A | section 3 writer table; T-C6 |
| RV-PAT 3 (one line, two rules; builtin shadow) | A | section 4.2 code: `prop`, `tag = m.get("property")` |
| RV-PAT 4 (semantics rows 3 and 5 overlap) | A | section 4.3: five ordered rows; T-F9 |
| RV-PAT 5 (five names in three places) | A | section 4.2 validation (1): `config.PROPERTY_NAMES`; T-C4 asserts the link |
| RV-PAT 6 (owner flips with task state; evidence folder moves) | A | section 4.2 fallback sentence and last worked row; T-R5 pins the folder |
| RV-PAT 7 (`corrected_from` overwrite in place) | A | the `simplify:` marker is specified for when it is built (section 4.5) |
| RV-PAT 8 (owner rule confirmed) | A (no change) | section 2 |
| RV-SIM 1 (validate `also_graded_by` now) | A | section 4.2 validation (2); T-C6; the deferred `simplify:` withdrawn (R-95 condition) |
| RV-SIM 2 ((e) exception and record built for an impossible case) | S | W0 section 7 ruling; section 4.5 contingency; T-U4..T-U7 removed |
| RV-SIM 3 (decision request for conditions 1 and 6) | S | R-95 (DR-9, option A); sections 4.2, 12; F-note in section 3 migration |
| RV-SIM 4 (T-R4 and T-U3 duplicate) | A | T-U3 folded into T-R4 (a real `run_pass`) |
| RV-SIM 5 (committed 0.6 `metrics.yaml` copy) | A | removed; read from git at `d6dda42d` (section 4.5 step 2) |
| RV-SIM 6 (`any_of` mutant; double test of the unrecorded-metric case) | A | mutant deleted (section 10); the readiness check is tested there once (FM1) |
| RV-SIM 7 (five guessed anchors) | R | kept: the done-when item names anchors; `validate_catalog` would accept their omission (F14, checked); U2 states the cost |

## Status

| | |
|---|---|
| **Completed** | Revision 2 of the W1-G design: the three reviews applied (disposition table above), W0 rev 3 and R-95 applied (owner rule no longer provisional, `also_graded_by` validated at once), the cross-version control with its red cases and the 0.6 definitions read from git (SP-4), the `n_recorded` split and the ABS-A sweep (SP-5), the `corrected_from` record as a written contingency, and the testability floor per test. |
| **Remaining** | RV-TA re-review of revision 2; ADR-0019 amendment notes (U5); the build tracks X-F (skeleton, `applicable`, the `formal` guard), X-A1 (validate checks), X-G1 (E1), X-A3 and X-G3 (E3); the Leader's 0.7 freeze. |
| **Best next action** | RV-TA reviews revision 2; X-F lands the skeleton so X-G1 can go green. |
