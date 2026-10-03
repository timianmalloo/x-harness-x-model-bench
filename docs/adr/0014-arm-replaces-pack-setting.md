---
id: "adr-0014-arm-and-cell-grain"
title: "ADR-0014: An arm replaces the pack setting; one cell is one (task version, combo, arm, repetition)"
type: adr
status: draft
owner: "@timianmalloo"
phase: "Enterprise evaluation E1 (two arms), E3 (three arms)"
tags: [benchmark, data-model, grain, plan, arm, migration]
links:
  - { to: arch-evaluation-campaign, rel: refines }
  - { to: spec-enterprise-evaluation, rel: implements }
  - { to: adr-0006-results-data-model, rel: refines }
review-by: "2027-10-03"
summary: >-
  A plan carries one pack revision per pack-on arm (zero for pack-off), and a cell is one (task version, combo,
  arm, repetition). The cell_id recipe and its key name stay byte-identical, with the arm id in the `pack`
  ingredient and `on`/`off` as the legacy arm ids, so grids 1-4 load, report and verify unchanged and a grid-4
  re-plan gives the same cells. New plans launch in a seeded blocked-randomised order and name their comparison
  pairs; the board and pack section read a comparison pair instead of the literals on/off.
---

# ADR-0014: An arm replaces the pack setting; one cell is one (task version, combo, arm, repetition)

- **Status:** Proposed
- **Amended (2026-10-03, W1-A design `design-eval-arms`; W0 rev 3):** see "Amendment 1" before *Alternatives considered*. The decision text above is unchanged.
- **Date:** 2026-10-03
- **Deciders:** @timianmalloo (DR-E1, 2026-10-03); authored by Claude Code with the Data & Persistence Architect and Distributed Systems lenses
- **Context spec/architecture:** `docs/specs/enterprise-evaluation.md` (C-E1, EV-17, R-E12); `docs/architecture-evaluation-campaign.md`; amends ADR-0006 *Identity* and `docs/architecture.md` *Context*.

## Context

DR-E1 puts pack-off, pack revision X and pack revision Y in one run, so drift between runs cannot pose as a pack effect (measured: +24 % Claude Code pack-off tokens grid-3 → grid-4). Today [Verified, read this session]:
- the plan holds one `pack` `{source, commit, revision}` (`plan.py:342`), and the matrix holds `packs: ["on", "off"]` (`runs/grid-4/matrix.yaml`; `config.py:35` `PACKS = ("on", "off")`);
- `Cell.id` hashes `{"task_version", "combo", "pack", "rep"}` with `pack` ∈ {on, off} (`plan.py:75`);
- the engine launches in `plan["cells"]` order (`engine.py:380`, `pending.pop(0)`); `expand` loops rep → task → pack → combo;
- the board and the pack section hard-code the literals: `board.py:540` (`{"off","on"} <= …`), `:586-620`, `:769`; `report/pack_improvement.py:131-132`, `:995`, `:1012`, `:1254`; `grade/_changes.py:84` (`cell.get("pack") != "on"`); the HTML header reads one `plan["pack"]` (`report/html.py:265`).

Grids 1-4 must still load, report and verify (EN9, US-4), and a grid-4 re-plan must give the same cells (EV-17). Principles in play: P2 (determinism), DM7 (one definition), DM10 (history by identity).

## Decision

**1. Arm.** An arm is one treatment level in a run, with an id matching `^[a-z][a-z0-9-]{0,15}$`. The id `off` is reserved for the pack-off arm, which has no pack revision. Every other arm has exactly one pack revision `{source, commit, revision}`. A run has at least two arms and at most one `off` arm. In a ring, arm ids are the role names (`off`, `incumbent`, `candidate`); in a campaign grid, the pre-registration fixes them (for example `off`, `x`, `y`).

**2. Matrix and plan.**
- `bench-matrix/2` declares `arms: [{id: off}, {id: x, pack: {source, commit}}, …]`. `bench-matrix/1` (`packs:` plus the plan's single `pack`) is read, in memory, as arms `on` (that pack) and `off`, in the matrix's order. No file is rewritten.
- `bench-plan/2` records `arms: {<id>: {pack: {…} | null}}`, `comparisons` (ordered pairs `[reference, treatment]`; default for two arms `[[off, <other>]]`, so a legacy run's one comparison is `[off, on]`), `launch_seed`, and each cell's `arm`. `bench-plan/1` files keep `pack` per cell and the top-level `pack`; they stay verifiable by their own `plan_hash`.
- One accessor each, defined once in `plan.py`: `cell_arm(cell)` (`arm`, else `pack`) and `arm_pack(plan, arm)` (`arms[arm].pack`, else the legacy top-level `pack` for `on` and `null` for `off`). No reader reads `pack` directly after this change; a guard test greps for it.

**3. Cell grain and identity.** One cell is exactly one (task version, combo, arm, repetition). `cell_id` keeps ADR-0006's recipe **byte for byte**: `sha256(canonical({"task_version", "combo", "pack", "rep"}))[:16]`, where the ingredient named `pack` now carries the arm id. The key name is a frozen label of the recipe, not the concept: renaming it would change every `cell_id` in grids 1-4. A legacy run's ingredients are therefore unchanged, and a three-arm run's cells are distinct because arm ids are distinct within a run.

**4. Launch order: blocked randomisation with a recorded seed.** A new plan's `cells` list *is* the launch order (no engine change). It is built from blocks, one per (task, combo, repetition); within a block the arms appear in a seeded random order, and the blocks are seeded-shuffled. The seed is `launch_seed`, drawn at plan time and recorded. By construction every arm's mean launch position is within one block of the run's mean, which meets EV-17's < 5 % bound for any run of 20 or more blocks; `bench plan` asserts the bound and refuses otherwise. Pairs of one block run close in time, so within-pair drift is minimal. Allocation concealment is not at issue (council Patterns): every block receives every arm, so no person or rule chooses which unit gets which treatment; only the order is randomised, by a seed drawn by the tool after the matrix is fixed.

**5. Board and report.** Every reader of the literals `on`/`off` takes a comparison pair from `plan.comparisons` instead. For a two-arm legacy run the only pair is `(off, on)`, so the output is the same; the existing catalog-freeze `golden` and `board_golden` hashes are the control. The HTML header lists one row per arm with its pack revision and commit. The pack section renders one block per comparison pair (its content per pair unchanged).

**6. Equivalence control (EV-17).** A test re-plans `runs/grid-4/matrix.yaml` with grid-4's frozen task versions (read from its `plan.json`) and asserts the same set of `(task, combo, arm, rep)` and the same `cell_id`s. The order may differ; the set and the ids may not.

**History rule.** No historical file changes. A `bench-plan/1` run is read through the accessors forever (EN9). Type-2 by identity: a new plan schema is a new dimension version; old plans keep theirs.

### Amendment 1 (2026-10-03; W1-A design `docs/design/eval-arms.md` section 12, gate passed; W0 rev 3 sections 5 and 10)

Recorded by the Coordinator (`coord-opus-e1e4`) with W0 rev 3. Items (a)-(e) are W1-A's text, verbatim:

> (a) Section 4: `bench plan` draws the launch seed up to 100 times and stores the first seed whose order meets the bound; a shape with no such seed (a single block) is refused with HB-PLN-001. Ordering uses sorted SHA-256 keys of `(seed, block[, arm])`, not a PRNG, so a stored seed replays on any Python version. (b) Section 2: a `bench-plan/2` plan has no top-level `pack`; `arms` is the only statement of pack revisions. (c) Section 2 and the `Cell` label: a `bench-plan/2` label is `<task>.<combo>.arm-<arm>.r<rep>`. (d) A measurement plan refuses a task whose `status` is not `ready`; a discrimination plan refuses `stub` (HB-PLN-004). (e) Ids in a matrix file are quoted strings: bare `off` is a YAML boolean.

Added by the Coordinator from the W1-A gate (RV-PAT W1-A findings 1, 2, 5):
- (f) Section 2, accessors: with (b), a reader that needs "the run's pack" reads `plan_pack(plan)`, defined once in `plan.py`: the top-level `pack` of a `bench-plan/1` plan, else the pack of the plan's only pack-bearing arm. A plan with two or more pack-bearing arms makes it raise HB-PLN-005, naming the arms, until X-A3 migrates the reader to comparisons (E3). No reader degrades to `None` silently.
- (g) Section 2, "a guard test greps for it": the guard scans the AST, not text. It flags every string constant `"pack"` outside docstrings, every attribute named `pack`, and every keyword argument `pack=`. Its allowlist pins a hit count per allowlisted file (a ratchet: a count may fall, never rise); X-A3 lowers the counts to zero in E3.

## Alternatives considered

- **Rename the ingredient to `arm` in the recipe:** rejected. It changes every `cell_id` in grids 1-4, breaking resume, US-52 joins and the goldens, for a cosmetic gain.
- **Put the pack revision into the cell_id recipe:** rejected. It changes legacy ids, and the arm id is already unique within a run; the plan binds arm → pack revision.
- **Keep `packs` and add a parallel `pack_revisions` list:** rejected. Two definitions of one concept (DM7), and `on` cannot name two pack revisions.
- **A seeded full permutation (no blocks):** rejected. Balance holds only in expectation; a seed can fail the 5 % bound, and pairs drift apart in time.
- **Keep today's deterministic order (rep → task → arm → combo):** rejected. Arms are confounded with launch position inside each task, and EV-17 asks for a seeded permutation.
- **Three runs joined by US-52:** rejected by DR-E1.

## Consequences

- **Positive:** grids 1-4 are untouched; one new concept (arm) generalises the old one exactly; the order is reproducible from the seed; no engine scheduling change.
- **Negative / accepted trade-offs:** the recipe's ingredient name `pack` no longer matches the concept name `arm` (documented here and in the `Cell` docstring); every on/off reader changes in one slice (about a dozen sites listed above), guarded by the goldens.
- **Follow-ups / new risks:** **hard precondition (council D5):** the arm id in `cell_id` carries no pack revision, so two runs' arm `on` may be different pack revisions. Any slice that joins cells across runs (US-52 comparison) must take an explicit arm → pack-revision mapping for both runs and refuse the join when the mapped revisions differ from what the comparison claims; joining by ingredients alone is forbidden after this ADR; the per-arm US-9 workspace check (EV-17 fourth criterion); Copilot's plan-time instruction probe runs once per (task, arm) instead of per (task, on/off) (`plan.py:303`).

## Evidence

- `src/harness_bench/plan.py:60-80, 116-128, 272-347`; `config.py:35, 107-111`; `engine.py:380-406`; `board.py`; `report/pack_improvement.py`; `grade/_changes.py:84`; `report/html.py:265-288` [Verified, read 2026-10-03].
- `runs/grid-4/matrix.yaml` [Verified].
