---
id: "adr-0017-engine-identity-and-freeze"
title: "ADR-0017: Engine identity is a per-component content manifest; the freeze admits only recorded defect fixes"
type: adr
status: draft
owner: "@timianmalloo"
phase: "Enterprise evaluation E1 onward"
tags: [benchmark, reproducibility, freeze, eligibility, campaign]
links:
  - { to: arch-evaluation-campaign, rel: refines }
  - { to: spec-enterprise-evaluation, rel: implements }
  - { to: adr-0016-campaign-record, rel: depends-on }
review-by: "2027-10-03"
summary: >-
  A campaign's engine baseline is a manifest of content hashes per engine component (each source module, the
  catalog hash, BOM, prices, profiles, harness builds, uv.lock, the campaign's task versions, platform and
  Python version), not a git commit, so unrelated commits do not break a freeze and a difference is named per
  item. A recorded defect fix replaces named component hashes under a defect class, in a before-hash chain.
  Eligibility is derived; a run-side fix after cells ran makes those runs ineligible and they are re-run (operator
  decision 2026-10-03); the run-side identity is also rechecked before every cell launch.
---

# ADR-0017: Engine identity is a per-component content manifest; the freeze admits only recorded defect fixes

- **Status:** Proposed (operator decision DI6 recorded 2026-10-03)
- **Date:** 2026-10-03
- **Deciders:** @timianmalloo (DR-T3, 2026-10-03); authored by Claude Code with the Enterprise Architect and Data & Persistence lenses
- **Context spec/architecture:** `docs/specs/enterprise-evaluation.md` (EV-16, EV-20, Campaign invariant; the copy row "engine differs from the campaign baseline (grade.formal changed, no recorded fix)").
- **Amended (2026-10-03, ruling R-94; design `eval-identity` section 4.2):** `telemetry/*` moves to the run side; `gateway` (`bench/gateway.yaml`) is a grade-side component. See "Amendment 1" below.

## Context

EV-16 freezes "the bench commit, catalog version, BOM version, price list version, harness builds and pinned dependency set". The repo's HEAD moves with every docs, task-authoring or campaign-record commit (ADR-0016 commits campaign files), so "the bench commit" as identity would make every campaign ineligible the moment its own record is committed. The UI copy needs the differing *component* by name (`grade.formal`). Existing identities already exist piecemeal: `catalog_hash` (R-59 c1), `price_list_hash`, `profile_record`, plan `builds` (sha256 per harness), `grader_build`, `extraction_id`.

## Decision

**1. The manifest.** An engine identity is a JSON map, canonical form, hashed (`identity_hash`):
- `src/<module path>` → `tree_hash` of that one file, for every file under `src/harness_bench/` (the run side and the grade side);
- `catalog` → `catalog_hash`; `bom` → hash of `bench/bom.yaml`; `prices` → `price_list_hash`; `profiles/<harness>` → `profile_record` hash; `builds/<harness>` → the pinned build sha256; `uv.lock` → its hash; `tasks/<id>` → task version hash, for the campaign's tasks; `platform` → `sys.platform`; `python` → `sys.version_info[:3]`.
- The bench commit is recorded beside it for provenance, but is **not** part of the identity.
- Each component is classed `run` side (`engine`, `driver`, `workspace`, `archive`, `procs`, `profiles`, `tools`, `builds`, `tasks`, `platform`, …) or `grade` side (`grade/*`, `telemetry/*`, `views`, `stats`, `report/*`, `catalog`, `prices`). The classification table lives in code, once, with a test that every `src/` file has a class.

**2. Where identities are recorded.** The campaign stores `identity/<hash>.json` (ADR-0016). A run plan built for a campaign records its `identity_hash` and manifest; each grading pass records its grade-side manifest hash in `grading.started`. The differ reports the named components that differ (`grade/formal.py changed`), which is the copy EV-20 shows.

**3. Baseline.** `bench campaign baseline` builds the manifest from the working tree and refuses unless: the tree has no uncommitted change to a manifest component; every property task is authored; catalog 0.7 is frozen in `bench/catalog-freeze.yaml`; spike E4 is cited as passed (EV-16). It then records `baseline.recorded{identity_hash}`.

**4. Recorded defect fixes.** `defect_fix.admitted{defect_class, commit, changes: {component: [before, after]}, scope: run|grade|both}`. Admission refuses: a defect class absent from `docs/lessons/defect-classes.md`; a component whose `before` is not the current **effective identity**'s hash (the baseline with all earlier fixes applied in order); a change to a component no fix names. The list only grows.

**5. Eligibility (derived, EV-20).** A run is eligible iff: its plan names this campaign, its prereg hash equals the registered one (comparison grids) and its ring hash matches the campaign's ring; its run-side manifest equals the run-side part of the effective identity at some point of the chain **and no run-side fix was admitted after its first `cell.launch_intent`**; and the grading pass that the verdict reads has the grade-side part of the **current** effective identity. Otherwise no verdict is shown, and the section names the differing items.

**6. Re-grade policy (EV-16).** When a grade-side fix is admitted, every campaign run's verdicts are withheld until a new grading pass under the new effective identity exists for it; the verdict names the fixes it was computed under.

**Operator decision (DI6), decided 2026-10-03:** "No — re-run them." Cells that ran before a run-side defect fix become exploratory, and the campaign re-runs them (§5 as written). The alternative (a fix may declare "does not affect completed cells") was rejected because it puts judgement back into the freeze.

**7. Run-side identity is checked at every cell launch (council R2).** The engine recomputes the run-side part of the manifest when a campaign run starts and again before each `cell.launch_intent`. On the first mismatch with the plan's recorded identity it stops launching (a stop with reason `engine identity drift`), records the named diff in the stop event, and lets running cells finish. A drifted engine therefore never spends a night producing ineligible cells; eligibility at verdict time (§5) remains the backstop. The recomputation hashes about a hundred small files and is measured on the first E1 run (`identity_check_ms` on the launch span).

## Alternatives considered

- **Identity = bench commit:** rejected; every unrelated commit (including the campaign's own records) breaks the freeze, and a difference cannot be named per component.
- **Identity = `grader_build` + `extraction_id` only:** rejected; it misses the run side (driver, workspace), tasks, builds and dependencies.
- **A coarse identity (one hash over `src/`):** rejected; it cannot tell the operator which component moved, and a fix cannot be scoped.
- **Freeze by branch (a campaign branch nobody touches):** rejected; it is a convention, not a check, and parallel worktrees routinely merge to main.

## Consequences

- **Positive:** docs and record commits never break a freeze; every ineligibility names its cause; fixes are scoped and chained, so the effective identity is computable offline.
- **Negative / accepted trade-offs:** a refactor that touches any `src/` file after the baseline is either a recorded fix or makes runs ineligible (that is the freeze working); the manifest has a few hundred entries.
- **Follow-ups / new risks:** the run/grade classification is load-bearing and needs review at the gate; `uv.lock` changes from unrelated tooling count (correct: a dependency changed).

### Amendment 1 (2026-10-03, ruling R-94 / DR-8; design `eval-identity` section 4.2)

Section 1's text above is not rewritten; this amendment is appended and governs where they differ.

- **The list, restated.** Run side: `engine`, `driver`, `workspace`, `archive`, `procs`, `profiles`, `tools`, `builds`, `tasks`, `platform`, `python`, **`telemetry/*`**, and the other modules a measured cell executes or is planned from. Grade side: `grade/*`, `views`, `stats`, `report/*`, `catalog`, `prices`, and the new component **`gateway`** = `file_hash(bench/gateway.yaml)`, `""` when the file is absent. A module used by both sides is run (run dominates).
- **Why.** Telemetry was listed as grade because extraction looked like grading, but the engine reads every native record at cell end for the recorded cause and the spend-cap stop (`engine.py:661`, `_read_records` `:852`; `profiles.py:262`), so a change to it can alter what a measured cell records while it executes, which is s1's own test for run side. `gateway` fixes the judge model and invocation behind every judged score and no existing component covered it.
- **Accepted cost.** A telemetry fix after a baseline is `scope: run`, so cells launched before it are re-run (operator decision DI6, s6). The measured price is `defect_fix.admitted` rows with `scope: run` whose `changes` keys all lie under `src/harness_bench/telemetry/`. `bench/gateway.yaml` appearing after a baseline is a grade-side fix: every campaign run's verdicts are withheld until a new grading pass.
- **Controls.** `identity.py` lists every `telemetry/*` file as run and `gateway` as grade; `tests/test_identity.py` pins both (an edit to `telemetry/normalize.py` changes the run-side hash and not the grade-side hash; a `bench/gateway.yaml` edit, and absent to present, does the reverse). The direction test (no run-class file imports a grade-class one) holds an allowlist of exactly three `config.py` validate-time pairs; a fourth is a decision request.
- **Follow-up closed.** This is the first review of the "classification is load-bearing" follow-up; it found one mis-listed glob and one missing component, both corrected here.

## Evidence

- `plan.py` (`file_hash`, `profile_record`, `builds`, `price_list_hash`), ADR-0006 (`grader_build`, `extraction_id`), `bench/catalog-freeze.yaml` [Verified, read 2026-10-03].

## Note, 2026-10-08 (Ruling 115; written by Coordinator #55)

R-115: the USD rendering is retired at X-NOPRICE; the `prices` identity component (0017) and `cost_usd`/`cost_of_pass` in catalog 0.7 (0019) stand until the post-E5 retirement, condition 5. Nothing this ADR guarantees changes before E5; the post-E5 track X-PRICERET amends it.
