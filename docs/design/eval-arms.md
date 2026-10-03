---
id: "design-eval-arms"
title: "W1-A design: arms in the plan (bench-matrix/2, bench-plan/2, blocked launch order, the pack-reader guard)"
type: design
status: proposed
owner: "@timianmalloo"
phase: "Enterprise evaluation: Wave 1 design slice W1-A (builds as X-A1 in E1 and X-A3 in E3)"
tags: [benchmark, campaign, arms, plan, matrix, launch-order, evaluation-campaign, design-slice]
links:
  - { to: spec-enterprise-evaluation, rel: implements }
  - { to: arch-evaluation-campaign, rel: implements }
  - { to: adr-0014-arm-and-cell-grain, rel: depends-on }
  - { to: design-eval-seam-contracts, rel: depends-on }
  - { to: rulings-register, rel: depends-on }
  - { to: review-eval-ta-w1a, rel: relates-to }
  - { to: review-eval-sim-w1a, rel: relates-to }
  - { to: review-eval-pat-w1a, rel: relates-to }
review-by: "2026-10-17"
summary: >-
  Designs ADR-0014 for the code. One new concept, the arm, replaces the pack setting: bench-matrix/2 declares arms and
  bench-plan/2 freezes one pack revision per pack-bearing arm, one ordered comparison list, a stored launch seed and
  cells keyed by arm, with the cell_id recipe byte-identical (so grid-4 re-plans to the same 276 ids, shown by spike).
  Launch order is blocked by (task, combo, rep) with hash-keyed arm order; an accepted plan meets the 5 % bound,
  found by bounded redraw, and an unsatisfiable shape is refused (HB-PLN-001). A measurement plan refuses a task that is
  not ready (HB-PLN-004). The pack-reader guard is an AST scan with a per-file hit-count ratchet; three readers migrate in its
  commit, and four plan-level readers move to the plan_pack accessor (W0 rev 3). A second ratchet counts the bare
  on/off literals and report.js. The E1 / E3 split, every on/off literal site, the EV-17 test map and six spikes are in
  the doc. Revision 2 applies the RV-TA, RV-SIM and RV-PAT conditions; each finding has a row in the Review disposition.
---

# W1-A design: arms in the plan

**Status.** `proposed`. Author: W1-A (`w1a-arms-e1e4`), Claude Sonnet 5.5, 2026-10-03. Revision 2 (`w1a-arms-r2-e1e4`, 2026-10-03): applies the three gate reviews; gate record in section 15, dispositions in section 16. Built by X-A1 (E1) and X-A3 (E3). Revision 1 was grounded on `main` at `1722e06d` (W0 rev 2); revision 2 is on `main` with **W0 rev 3** merged (`docs/design/eval-seam-contracts.md`, cited as **W0**), rulings R-87..R-96, and re-read on this tree.

**Authority.** ADR-0014 and EV-17 win over this doc; W0 wins over this doc where it fixes a shape. This doc narrows and details W0. It widens nothing. Its revision-1 exceptions (one new HB code, two W0 errata, four seam requests) were all answered in W0 rev 3 and are recorded as such in section 12.

## 1. Responsibility, boundaries, placement

**One responsibility.** Turn a matrix and a BOM into a frozen plan in which every cell belongs to an **arm**, every pack-bearing arm has exactly one frozen pack revision, and the launch order is a recorded, balanced, reproducible function of a seed. It also owns the one place a reader learns a cell's arm and an arm's pack.

**Crosses the boundary.** In: `bench-matrix/1|2` YAML (operator-authored or compiled by `/start-benchmark`), `--arm role=source@commit` bindings, the BOM, `tasks/<id>/task.yaml`. Out: `runs/<run_id>/plan.json` (`bench-plan/2`), the accessors `cell_arm` / `arm_pack` / `plan_comparisons`, `cell.workspace_built` events carrying `arm`. Data it borrows, never owns: pack repositories (read through `workspace.pack_checkout`), the catalog, the campaign block (X-C builds it; this slice writes it verbatim).

**Placement (delivery phasing).** E1 is the walking skeleton: two arms (`off`, `candidate`), the pilot ring (R-89: combo `cc-opus`, k = 3, arms `off` and `candidate`). E3 adds the third arm to real runs, ring-hash refusal, the report readers per comparison pair, and `calibration`. **The plan code is N-arm generic from E1**; only the readers and the ring refusal wait. Mock-substitutable seams: `build_plan` takes already-resolved `arm_packs`, so plan tests need no git; `draw_launch_order` takes an injected `draw`, so a test forces a first-draw failure.

**Internal contracts found and conformed to** (BoK V.1): errors are `BenchError("HB-xxx", msg)`; static matrix problems are `Problems` items (`config.validate_matrix`); the canonical form forbids floats and bools (`ledger.canonical`), so the stored seed is an int and ratios are `Fraction` in memory, decimal strings on the wire; structural rules are AST tests in `tests/test_architecture.py` (`_tree`, `_imports`), and G1 follows that style; fixtures are committed JSON under `tests/fixtures/`.

## 2. Data model (settled first)

**Bounded context: run planning.** Ubiquitous language: **arm** (one treatment level in a run; id `^[a-z][a-z0-9-]{0,15}$`), **role** (an arm declared in a ring with no pack, bound at plan time), **pack revision** (`{source, commit, revision}`), **comparison** (an ordered pair `[reference, treatment]` of arm ids), **block** (one `(task, combo, rep)`), **launch order** (the order of `cells`), **launch seed**. ADR-0014 §1 reserves the id `off` for the pack-off arm (no pack).

| concept | kind | identity | notes |
| --- | --- | --- | --- |
| **Plan** | aggregate root | `run_id`; content address `plan_hash` | the only aggregate this slice touches; write-once (`confirm` opens with `"x"`) |
| Arm | value object inside Plan | its id within the plan | `{pack: PackRevision \| null}` |
| PackRevision | value object | `(commit)`; `revision` is derived from the commit's `INSTALL.md` | `source` is an operator-local path |
| Comparison | value object | the ordered pair | |
| Cell | entity inside Plan | `cell_id` = `sha256(canonical({"task_version","combo","pack","rep"}))[:16]`, the ingredient `pack` carrying the **arm id** | recipe unchanged byte for byte (ADR-0014 §3) |
| LaunchOrder | derived cache | `(launch_seed, cell set)` | the `cells` list is its materialisation |
| Matrix / Ring | input document, hashed into the plan (`matrix_hash`; a ring also `ring.hash`) | content | not an aggregate |

**The one invariant the Plan protects.** *A confirmed plan is an immutable, self-describing document in which `cells` is exactly the product tasks x combos x arms x reps, each once; every `cells[].arm` is a key of `arms`; every non-`off` arm has one frozen pack revision and `off` has none; and `cells` order is the order `launch_seed` generates (or the plan is not written).* Enforced by `build_plan` (HB-PLN-001/002/004 before any write), by `plan_hash` on load, and by the tests in section 10. Other aggregates (Campaign, Run ledger, Grading pass) refer to the plan by `run_id` and read arms only through the accessors.

**Durable representation.** `plan.json` is a frozen dimension document: a new schema is a new version, old plans keep theirs (Type-2 by identity, ADR-0014 *History rule*). No file is rewritten. Facts that change over time (events, scores) are append-only elsewhere and unchanged.

**Grain statements.**
- `cells[]`: one row is exactly one `(task version, combo, arm, repetition)`, identified by `cell_id`, recorded when the plan is built. Measures: `budget_seconds` (additive), `rep`, `scenario` (labels). The plan stores no score.
- `arms{}`: one entry is exactly one arm in this run, identified by its id, recorded at plan time. No measures.
- `comparisons[]`: one row is exactly one ordered pair of arm ids the report may compare. No measures.
- `cell.workspace_built` event (append-only fact): one row is exactly one workspace build of one cell, recorded when it ends. Measure `pack_manifest` = count of written pack paths (additive across cells; not summed across arms in any report).
- `envelope_seconds` (existing, non-additive across plans, semi-derived): untouched.

**History rule per attribute (Type-2 unless stated).**
| attribute | rule |
| --- | --- |
| `schema` | Type-2: `bench-plan/2` is new; `/1` is read forever through the accessors |
| `cells[].arm` (replaces `cells[].pack`) | Type-2 by schema; the `/1` key `pack` is never rewritten |
| top-level `pack` | **dropped in `/2`** (W0 rev 3 section 5, Coordinator ruling on RV-PAT W1-A 1 and 5: one definition, DM7). Legacy plan-level readers read the one accessor `plan_pack` (3.3); the cell-level reader at `pack_improvement.py:747` reads `cell_arm` |
| `arms`, `comparisons`, `launch_seed` | new in `/2`, frozen |
| `matrix` | stored verbatim as read (`/1` stays `/1`; the upcast is in memory only) |
| event key `pack` of `cell.workspace_built` | Type-2: `/2` runs write `arm` (and `pack_commit`); `/1` events keep `pack` |
| `CellView.pack` (views.py) | Type-1 by decision, kept: the view field holds the **arm id**; renaming it touches about 80 reader sites that E3 migrates anyway. A recorded misnomer. **Trigger (RV-PAT 4):** E3 renames it when the G1 ratchet's count for `views.py` and for every other reader file reaches zero; the ratchet fails the E3 gate until it does |

**Derive, don't store (DM7).**
- The launch **order** is derivable from `(launch_seed, cell set)`. The `cells` list is a **rebuildable cache** of it: the engine launches in list order with no engine change (ADR-0014 §4). Equality test: `tests/test_plan.py::test_cells_order_equals_the_order_derived_from_launch_seed`. Not re-derived at load: `plan_hash` already covers a hand edit.
- Launch **balance** is derived (`launch_balance(cells)`), never stored; `bench plan` prints it.
- `comparisons` is **stored, not derived**, deliberately: it is the frozen statement of what the run may compare (a later default-rule change must not reinterpret an old plan). The default rule (below) is applied once, at plan time.
- No second definition of "which pack does a cell get": `arms[arm].pack` is the only one; the top-level `pack` is dropped for that reason. The plan-level single-pack readers get it through `plan_pack`, which derives it from `arms`.

**Writer and compute reader of every persisted field** (DM15).
| field | writer | compute reader |
| --- | --- | --- |
| `arms` | `plan.build_plan` | `plan.arm_pack` (cli `_workspace_builder`, E3 header, `board.compare` in E3) |
| `cells[].arm` | `plan.build_plan` | `plan.cell_arm` (`views.py`, `grade/_changes.py`, `cli.py`, E3 readers) |
| `comparisons` | `plan.build_plan` | `plan.plan_comparisons` (X-C prereg check, X-H2 section 3, E3 board) |
| `launch_seed` | `plan.draw_launch_order` | `launch_order` (the equality test; `bench plan` display). No production reader beyond display and the test: a recorded provenance fact, named as such |
| `kind`, `campaign`, `ring` | `build_plan` (verbatim args) | X-E (`kind`), X-C (`campaign`, via `cli.py` HB-CMP-010), X-A3 (`ring.hash`, E3) |
| `cell.workspace_built.{arm,pack_commit,pack_manifest}` | `_workspace_builder` via the engine | `tests/test_cli.py::test_workspace_builder_installs_each_arms_own_pack` and the E5 audit (X-INT). **No runtime reader exists today** (`pack_manifest` has none either; searched `src/`); stated, not hidden |

**Append-only / interval invariants.** `plan.json` is create-only: existing `test_confirm_freezes_the_plan_and_refuses_a_second_write` (`tests/test_plan.py:274`) attempts the forbidden second write; kept. A rebuild test exists for the one cache (order from seed). **Migration:** none. Expand-migrate-contract is satisfied trivially: `/2` is an expansion (new writers, old readers kept), grids 1-4 are never rewritten, and the contract step (dropping the allowlist) is E3's. No backfill. No ADR is new: ADR-0014 records the representation; section 12 carries its amendment text.

## 3. Contracts

### 3.1 `bench-matrix/2` and the in-memory upcast (owner X-A1, `config.py`)

W0 section 5 fixes the shape. Details added here:

```yaml
schema: bench-matrix/2
run_id: pilot
ring: {tag: pilot}                       # optional; pilot | pack-regression | comparison
bom: {file: bench/bom.yaml, subset: [S1]}
repetitions: 3
arms:                                    # IDS ARE QUOTED STRINGS: see the erratum below
  - {id: "off"}
  - {id: candidate}                      # a ring role: no pack, bound by --arm
comparisons: [["off", candidate]]
combos: [{id: cc-opus, harness: claude-code, model: claude-opus-5-5}]
```

**Erratum 1 to W0 section 5 (verified by SP-A0).** `config.load_yaml` is `yaml.safe_load`; bare `off` is YAML 1.1 for `false`. Run on this tree: `arms: [{id: off}]` loads as `{'id': False}` and `comparisons: [[off, candidate]]` as `[[False, 'candidate']]`. W0's example is unquoted. Rule: every arm id and every comparison entry in a file is a quoted string where it could be a YAML boolean; `validate_matrix` refuses a boolean id or comparison entry with the same hint the existing `packs` check carries (`config.py:109`).

**`validate_matrix` (static; `Problems` items, exit `INVALID`).**
- `schema` is `bench-matrix/1` or `/2`. `/2` forbids `packs`; `/1` forbids `arms`, `comparisons`, `ring`.
- `/2`: `arms` has at least 2 entries (a `/1` file may have 1, as `bench/matrix.qual-r74.yaml` does); each id fullmatches `ARM_ID`; ids unique; at most one `off`; `off` has no `pack`.
- A non-`off` arm's `pack`, when present, is `{source, commit}` with `source` an **absolute** path string and `commit` fullmatching `[0-9a-f]{40}` (a branch name is movable; a leading `-` would reach `git checkout`/`git clone` as an option).
- A non-`off` arm with no `pack` is a role: allowed only when `ring` is present. A non-ring `/2` matrix (a campaign grid) pins every non-`off` arm.
- `comparisons`: pairs of declared ids, reference != treatment, no duplicate pair; required with 3 or more arms; with 2 arms the default applies (below).
- `ring.tag` in the three values. Combos, repetitions, BOM subset: unchanged checks.
- `validate_repo` validates `bench/rings/*.yaml` as well as `matrix.example.yaml`.

**Upcast.** `plan.arms_of(matrix) -> list[dict]` returns `[{"id", "pack"}]` in declared order. `/1`: `packs` order, ids `on`/`off` (`on` is a role bound from `--pack-source`; `off` has no pack). `/2`: as declared.

**Comparisons default: the one reader rule** (W0 section 5), in one function `default_comparisons(arm_ids)`: 0 or 1 arm: `[]`; 2 arms: `[["off", other]]` if one is `off`, else `[[first, second]]` in file order; 3 or more: the file must say. A `/1` file with `packs: ["on", "off"]` gives `[["off", "on"]]` whatever the file's order, which is the legacy pair.

### 3.2 `bench-plan/2` (owner X-A1; `plan.py`)

Field table: W0 section 5, unchanged. Details:

- **Every new plan is `bench-plan/2`**, including one built from a `/1` matrix. One code path; `/1` is read-only history. The plan stores `matrix` verbatim.
- `arms`: `{<id>: {"pack": {"source","commit","revision"} | null}}`, keys in declared order. `off` is `{"pack": null}`.
- `comparisons`: `[[ref, treat], ...]`. `kind`: `"measurement"` (default) or `"discrimination"`. `campaign`: written verbatim when the argument is given, key absent otherwise (never `null`; `plan_hash` covers presence). `ring`: when the matrix has `ring`, `{tag, hash}` with `hash = tree_hash(matrix_path.parent, [matrix_path])`, the one content-address recipe, so a CRLF checkout hashes the same.
- `cells[]`: `{cell_id, label, task, task_version, scenario, combo, harness, model, arm, rep, budget_seconds [, instruction_count]}`. `Cell.pack` is renamed `Cell.arm`; position in the dataclass is unchanged, so positional constructors in `tests/test_plan.py:91-96`, `tests/test_engine.py:88` and `tests/e2e/test_r21_copilot_budget_kill.py:68` still build. `Cell.id` keeps `{"task_version","combo","pack","rep"}` with `"pack": self.arm`, and a comment saying why (key is a frozen label).
- **Label (W0 left the text to this slice).** `f"{task}.{combo}.arm-{arm}.r{rep}"`. It fullmatches `config.LABEL` (`[A-Za-z0-9.\-]{1,80}`, `config.py:22`) because an arm id has no `.` and `_validate_ids` still runs. The readers that parse a label read its first segment (`html._task_id`, `context_growth`): unchanged. `/1` labels are never recomputed.
- **Instruction probe (Copilot, `plan.py:303-310`).** Keyed by `(task, arm)`; installs the arm's pack when `arm_packs[arm]` is not null; the "pack-off loaded instruction files" refusal applies to every arm with no pack. `instruction_lists[].pack` becomes `.arm` in `/2` (no reader outside `plan.py`: searched `src/` and `tests/`).
- `load_confirmed` additionally refuses a `schema` outside `{bench-plan/1, bench-plan/2}` (`HB-USR-002`): an older engine must not half-read a newer plan.
- **Dropped:** top-level `pack`. See the history table and test `test_a_plan_2_has_no_top_level_pack`.

### 3.3 Accessors, defined once in `plan.py` (W0 section 5)

```python
def cell_arm(cell: Mapping) -> str:                 # "arm" if present, else legacy "pack"
def arm_pack(plan: Mapping, arm: str) -> dict | None   # /2: plan["arms"][arm]["pack"]; /1: top-level pack for "on", None for "off"
def plan_comparisons(plan: Mapping) -> list[tuple[str, str]]   # /2: stored; /1: [("off","on")] if both settings occur, else []
def plan_pack(plan: Mapping) -> dict | None         # W0 rev 3: /1: top-level pack; /2: the pack of the only pack-bearing arm; none: None; 2 or more: HB-PLN-005 naming the arms
```
`plan_pack` is the single-pack reader contract for the four plan-level legacy sites (3.8). Its HB-PLN-005 is retired when X-A3 moves the last of them to comparisons in E3.
An arm not in the plan raises `BenchError("HB-USR-002", ...)`, never `KeyError`. `config.ARM_OFF = "off"` and `config.ARM_ID` live in `config.py` (it cannot import `plan.py`: `config.py:434` already imports it locally to avoid the cycle), replacing `config.PACKS`. **"Has a pack" is `cell_arm(cell) != config.ARM_OFF`**, exact because ADR-0014 section 1 makes `off` the only pack-less arm; this is what `grade/_changes.py` needs, since its caller passes a cell and no plan.

### 3.4 Launch order and the balance bound (ADR-0014 section 4)

```python
BALANCE_BOUND = Fraction(5, 100); MAX_DRAWS = 100
def launch_order(cells: Sequence[Cell], seed: int) -> list[Cell]
def launch_balance(cells: Sequence[Cell]) -> Fraction
def draw_launch_order(cells, draw=lambda: secrets.randbits(63)) -> tuple[int, list[Cell], int]   # (seed, ordered, draws)
```
- **`launch_order`.** Blocks are `(task, combo, rep)`. Blocks sort by `sha256(f"{seed}|block|{task}|{combo}|{rep}")`; within a block, arms sort by `sha256(f"{seed}|arm|{task}|{combo}|{rep}|{arm}")`. **Hash keys, not a PRNG:** `random.shuffle`'s algorithm is not guaranteed across Python versions, and a stored seed must replay on any later one. No new dependency, no import of `stats.py` (a grade-class module that a run-class module may not import, W0 section 9).
- **`launch_balance`.** Positions are 0-based indexes in the order. For each arm, `|mean(arm positions) - (N-1)/2| / N`, as a `Fraction`; the result is the maximum over arms. EV-17: the plan is accepted iff this is **strictly less than** 5/100.
- **`draw_launch_order`.** Draws a seed, orders, checks the bound; up to `MAX_DRAWS`; returns the first accepted seed, which is the one stored. After `MAX_DRAWS` failures: `BenchError("HB-PLN-001", "launch order cannot meet the 5 % balance bound after <n> draws: <B> blocks of <A> arms; add tasks, combos or repetitions")`. (RV-PAT 3: the message reports the shape and the draws made and claims no block minimum, because for more than 2 arms the number of blocks that always passes is larger than 2; SP-A6 below).. **A given seed (`launch_seed=` argument, for replay and tests) is one attempt and refuses on failure.**
- **Why a redraw, not a bare refusal (measured, SP-A2).** ADR-0014 says `bench plan` "asserts the bound and refuses otherwise". For small runs the bound fails by chance: the R-89 pilot ring is 3 blocks of 2 arms, and 25 % of seeds fail it (first-draw pass 0.750 over 2,000 seeds). A bare refusal would send the operator to re-run `bench plan` blindly one time in four. Redrawing is the same assertion applied to the seed: the stored seed *always* meets the bound, and the order replays from it. A one-block run is unsatisfiable (0 of 2,000 seeds; one block has deviation >= 1/4 at two arms) and is refused. A shape can also be satisfiable in principle yet exhaust the cap: 2 blocks x 4 arms fails 36 of 2,000 seeds at 100 draws (SP-A6); that is the same named refusal, and the plan is a tiny one. The redraw is restricted randomisation; the analysis pairs within block, so it is not affected by which balanced order was drawn (see the residual in section 14).

| blocks x arms | first-draw pass | mean draws | max draws seen | unsatisfiable (2,000 seeds, cap 100) |
| --- | --- | --- | --- | --- |
| 1 x 2 or 3 | 0 | none | none | 2,000 |
| **3 x 2 (pilot)** | **0.750** | 1.34 | 7 | 0 |
| 2 x 3 | 0.180 | 5.86 | 40 | 0 |

The other shapes of the revision-1 table (2 x 2, 4 x 2, 6 x 2 and up, 3 x 3, 6 x 3 and up) are cut (RV-SIM 3): every shape from 6 blocks passes first time, and the spike recipe is the record. Two 4-arm rows added by RV-PAT 3 are in SP-A6.

- **Old rationale replaced.** Today's order puts combos innermost so provider drift touches every combo alike (`plan.py` module doc). The blocked order puts every arm of one `(task, combo, rep)` next to each other, which serves the paired comparison (EV-17's purpose) and replaces that rationale; the module doc is rewritten.

### 3.5 The ready rule (W0 section 14 item for this slice)

**Decision: `bench plan` refuses a task that is not `ready` (option A), by plan kind.**
- `kind = "measurement"`: every selected task must be `ready`. `kind = "discrimination"` (X-E): `draft` or `ready`, because a task becomes `ready` only through its discrimination record (EV-7). `stub` is refused in both: a stub has no `prompt.md`, and `_prompt` (`plan.py:151`) reads it unconditionally.
- Refusal: `BenchError("HB-PLN-004", ...)` naming **every** offending task with its status (no cap, RV-SIM 4: a 12-name cap is a formatting rule with no failure behind it). Code granted by W0 rev 3 section 11.
- Why A and not a BOM field. The BOM field would be a second statement of readiness beside `task.yaml status` (DM7), set by ten tracks, and `full` would then silently mean "less than every task". Option A states the truth once and turns today's raw `FileNotFoundError` into a named refusal. Measured today: `bom.subset: full` selects `G1` (`stub`) plus the ten property stubs, so it cannot be planned now; grid-4 names its 23 tasks (all `ready`, read 2026-10-03; W0 section 1 says grid-3 likewise), so EV-17's re-plan is unaffected.
- **One predicate (RV-PAT 6).** The check reads `task.yaml status` and nothing else. `assume:` `status: ready` is written only by X-E's readiness path (W0 section 3, `bench validate` runs `readiness.py`), so `bench plan` cannot accept a task that `bench validate` refuses; confirmed when X-E's design is read at the E1 join (what breaks if false: `bench plan` accepts a task whose `expected` or discrimination record fails). One test pins it at X-E's seam: a task with `status: ready` and a failing `expected` is refused by `cmd_validate`; owned by X-E, named here so the seam is visible.
- `expand` is unchanged (it enumerates), so `tests/test_plan.py:52` (816 cells) stays true; its comment is corrected. The check lives in `build_plan` and `cmd_plan --json` calls it too, so nothing prints cells it would refuse to freeze.

### 3.6 Role binding (`--arm`), pure and in `plan.py`

```python
def parse_binding(text: str) -> tuple[str, str, str]      # "candidate=C:/repo@<40 hex>" -> (role, source, commit); partition("=") then rpartition("@")
def resolve_arms(matrix: Mapping, bindings: Mapping[str, tuple[str, str]]) -> dict[str, dict | None]
```
`resolve_arms` returns `{arm: {"source","commit"} | None}` or raises `HB-PLN-002` for: a role with no binding (unbound role); a binding for an id that is not an arm; a binding for `off`, or for an arm that already has a pack; a binding whose source is not absolute or commit not 40-hex; a `/2` file given the legacy `--pack-source`. For `/1`, the caller passes `bindings["on"]` built from `--pack-source`'s HEAD, so the legacy route and the role route are one code path. The CLI then adds `revision` per pack (section 3.9).

### 3.7 The workspace builder (X-A1 owns this one function in `cli.py`, W0 section 13)

```python
def build(cell, cell_dir):
    arm = plan.cell_arm(cell); pack = plan.arm_pack(p, arm)
    ...clone as today...
    info = {"arm": arm, "pack_manifest": 0}
    if pack is not None:
        pack_dir = workspace.pack_checkout(Path(pack["source"]), pack["commit"], pack_root)
        manifest = workspace.install_pack(pack_dir, ws, project=cell["task"], timeout=p["parameters"]["git_timeout"] * 5)
        info |= {"pack_manifest": len(manifest), "pack_commit": pack["commit"]}
    return info
```
`pack_checkout` lands each commit in `pack_root/<commit[:12]>`, so two arms with two commits never collide (`workspace.py:206-221`). **Per-arm US-9 (EV-17 criterion 4)** holds by construction (a workspace is the task base clone plus at most one commit, the arm's pack install; `_changes.pre_turn_commit` recognises it by subject) and is proved by `tests/test_workspace.py::test_each_arms_workspace_differs_from_pack_off_only_by_its_manifest` (section 10).

### 3.8 The pack-reader guard G1 (X-A1, `tests/test_arms_guard.py`), its four frozen fields, and the literal ratchet

Discharges ADR-0014 section 2: "No reader reads `pack` directly after this change; a guard test greps for it." W0 rev 3 section 10 fixed the shape (AST nodes, a per-file count ratchet); this section pins the numbers. The doc comment states the four fields verbatim:

| field | value |
| --- | --- |
| root | `src/harness_bench/`, `*.py` only |
| recursion | yes |
| tokens (W0 rev 3) | as AST nodes, outside docstrings: every string `Constant` equal to `"pack"` (covers `x["pack"]`, `.get("pack")`, `.pop("pack")`, `"pack" in x`, `getattr(x, "pack")`, `itemgetter("pack")`, a `{"pack": ...}` key), every `Attribute` named `pack`, every `keyword(arg="pack")` |
| allowlist (constant) | `PACK_READERS_ALLOWED: dict[str, int]`, file to pinned hit count (a ratchet: a count may fall, never rise). **E1 values below.** E3: X-A3 lowers every count to its permanent floor |

**Pinned counts (SP-A6, measured on this tree with the rev-3 token set; "after E1" subtracts the hits the E1 migrations remove).**
| file | now | after E1 | why it stays |
| --- | --- | --- | --- |
| `board.py` | 30 | 28 | E3 migrates to comparisons (`plan_pack` replaces the two plan reads at 756-757) |
| `report/html.py` | 40 | 37 | E3; X-H2 replaces the three header reads at 265, 266, 288 with `plan_pack` |
| `report/pack_improvement.py` | 9 | 7 | E3; X-A1 replaces the cell read at 746-747 with `cell_arm` |
| `report/summaries.py` | 6 | 5 | E3; line 177 reads `plan_pack` |
| `report/cli_table.py` | 7 | 7 | E3 column naming |
| `report/context_growth.py` | 2 | 2 | E3 column naming |
| `views.py` | 2 | 1 | the `CellView.pack` field name (AD-8); E3 renames it, count 0 |
| `plan.py` | 8 | pinned by X-A1 at the green commit | the frozen recipe key `"pack"` (permanent) and the probe dir name |
| `cli.py` | 7 | 2 | two `/ "pack"` path segments (the pack repo's own folder, `cli.py:110, 169`); permanent |
| `workspace.py` | 2 | 2 | two `/ "pack"` path segments (`workspace.py:225, 233`); permanent. **New in the allowlist:** revision 1's three-form scan did not see them |

`grade/_changes.py` (1 hit) migrates to 0 and is not in the mapping; every other file must have 0 hits. The one-line comment beside `workspace.py` and `cli.py` says the hits are a directory name, not a cell read; a path-operand exemption would add a rule, and a pinned count costs one table row (Ladder: reuse the ratchet).

- **Migrated by X-A1 in the guard's commit** (W0 rev 2 RV-TA 1, rev 3): `views.py:525` `pack=cell["pack"]` becomes `pack=cell_arm(cell)`; `grade/_changes.py:84` `cell.get("pack") != "on"` becomes `cell_arm(cell) == config.ARM_OFF` (returns the base commit for the pack-less arm; any other arm falls through to the pack-commit check); `cli.py:145-148` as section 3.7. **Plus the four plan-level readers (W0 rev 3 section 5, E1):** `report/pack_improvement.py:746-747` reads `cell_arm(c)` (it reads a **cell**, so `plan_pack` does not apply; W0's "four sites read `plan_pack`" is true of the other three, and this is the one-line difference), `board.py:755-756` and `report/summaries.py:177` read `plan_pack(plan)`, and `report/html.py:265-266, 288` read `plan_pack` through X-H2 (its E1 hub, from X-A1's lines). The first three are X-A1's one-line edits (W0 section 13). Test: section 10, `test_plan_level_readers_state_the_true_pack_or_refuse`.
- **Red-first fixtures (one per form).** A temp tree with one file per token form (`x["pack"]`, `x.get("pack")`, `x.pop("pack")`, `"pack" in x`, `getattr(x, "pack")`, `x.pack`, `f(pack=1)`), plus a comment-only file and a docstring-only file that must not match, run **before** the real tree; deleting a form's rule turns the test red. The real tree is then green against the pinned counts.
- **The literal ratchet (RV-TA 1).** The `.pack` tokens do not catch the bare literals that E3 must move: `board.py` `{"off","on"} <=` and `packs = ("off","on")`, `html.py` strings, `report.js:148-149`. A second pair of tests in the same file, same ratchet shape: (i) every string `Constant` equal to `"on"` or `"off"` outside docstrings, per file; (ii) a text scan of `report/assets/*.js` for the quoted `"on"` / `"off"`. Pinned (SP-A6): `board.py` 12, `report/html.py` 7, `report/pack_improvement.py` 7, `report/summaries.py` 2, `config.py` and `plan.py` pinned by X-A1 at the green commit (the `/1` `PACKS` tuple and `ARM_OFF`; `plan.py` ends with none outside the `/1` upcast), `report.js` 2. `cli.py` (1) and `grade/_changes.py` (1) migrate to 0 and are not in the mapping. E3 lowers `board.py`, `html.py`, `pack_improvement.py`, `summaries.py` and `report.js` to 0. A site missed in E3 is then a red count, not a silent leftover. Red fixtures: a temp `.py` with `x == "on"` and a temp `.js` with `setting === "on"`.
- **The W0 assume, confirmed in part (SP-A3), and now closed for E1.** *assume (W0 G1):* legacy readers render a non-`on` arm id without raising. Confirmed: `board.build`, `pack_improvement.assemble` and `html.render` ran on an `off` / `candidate` view with no exception. They said false things: `board._build_pack_effect` returned "This run has one pack setting; no effect to show." for a run with two arms, `pack_improvement` returned `no_pairs`, and the header showed no pack revision. W0 rev 3 section 10 (SR-3, option (a)): X-A1 edits the `_build_pack_effect` status text; the header reads `plan_pack` through X-H2; `no_pairs` stays an empty section until E3.

### 3.9 `cmd_plan` wiring for X-C (W0 section 13: `cli.py` is X-C's in E1; seam request SR-2)

```python
pl.add_argument("--arm", action="append", default=[], metavar="ROLE=SOURCE@COMMIT", help="bind a role arm to a pack revision (repeatable)")
pl.add_argument("--pack-source", default=None, help="legacy bench-matrix/1 only: the pack clone whose HEAD is arm 'on'")
# cmd_plan, after validate_matrix and before build_plan:
bindings = {r: (s, c) for r, s, c in map(plan.parse_binding, args.arm)}
if matrix["schema"] == "bench-matrix/1" and "on" in matrix["packs"]:
    source = Path(args.pack_source or root.parent / "ai-forward")
    bindings["on"] = (str(source), gitsafe.git(["rev-parse", "HEAD"], cwd=source, timeout=60).stdout.strip())
elif args.pack_source:
    raise BenchError("HB-PLN-002", "--pack-source applies to a bench-matrix/1 file; use --arm role=source@commit")
arm_packs = {a: (_pack_record(Path(p["source"]), p["commit"], pack_root) if p else None)
             for a, p in plan.resolve_arms(matrix, bindings).items()}      # _pack_record = today's _pack(), commit given
p = plan.build_plan(root, matrix, bom, run_id, builds, arm_packs, parallelism=..., parameters=..., tools_dir=..., cells_root=...,
                    matrix_path=matrix_path, kind=..., campaign=...)
```
The summary table gains one row per arm (id, pack revision, commit, cells) and the line `launch order: seed <s>, draw <n>, max arm deviation <x.xx> % of cells (bound 5 %)`. `--json` prints `expand` output through the same readiness check. Behaviour change recorded: a `/1` matrix with only `packs: ["off"]` no longer needs a pack clone (the arm has no pack).

## 4. Patterns, named and justified (Ladder climbed)

| decision | rung | pattern | rejected alternatives |
| --- | --- | --- | --- |
| arm accessors `cell_arm` / `arm_pack` / `plan_comparisons` | reuse-in-codebase (`resolved_model_map` is the precedent: one resolver in `plan.py`, readers import it) | **Anti-corruption layer / Facade over a versioned document** (the `/1` and `/2` shapes behind one reader) | each reader branching on schema (dozen copies, DM7) |
| `plan_pack` for the plan-level readers | reuse (same module, same accessor idiom; W0 rev 3) | **Facade / ACL** (the single-pack reader contract) | each reader branching on `plan["arms"]` vs `plan["pack"]` (three copies, DM7) |
| `/1` read as `/2` arms in memory | one line per site | **Adapter** (upcast at the edge); no file rewritten | migrating grids 1-4 (violates EN9) |
| ordering by sorted hash keys | stdlib (`hashlib`) | **Seeded deterministic ordering** (a pure function; no stateful PRNG) | `random.shuffle` (not stable across Python versions); `stats.rng` (grade-class import); a full permutation (ADR rejected it); **a seeded base arm permutation rotated by block index (Latin-square counterbalance, RV-SIM 2).** It balances by construction and needs no redraw loop, no `MAX_DRAWS` and no `secrets` default. Rejected because it makes the arm order inside blocks a predictable period-A pattern, and ADR-0014 section 4 asks for a "seeded random order"; a predictable pattern also lets drift that has the same period alias with one arm. Block order does not affect the bound (every arm shares the block starts), so the redraw only has to vary the within-block arm order |
| bounded redraw of the seed | minimum that meets the ADR's assertion | **Rejection sampling with a recorded outcome** | bare refusal (25 % false refusals at the pilot shape, measured) |
| role arms bound at plan time | reuse (`bench-matrix/2` per ADR-0016 section 6, W0 section 5) | **Template + late binding** | a separate `bench-ring/1` (rejected in the architecture council) |
| the guard and its ratchet | reuse (`tests/test_architecture.py` style) | **Fitness function (architecture test)** with a **ratchet** (a pinned count that may fall, never rise) | a regex grep (over-matches prose, shown); a wholesale file allowlist (hides a new read in an allowlisted file, RV-PAT 2) |
| readiness refusal | one `if` in `build_plan` | **Guard clause / fail fast** | a BOM flag (second source of truth) |
| `Cell.pack` renamed `arm`, recipe key kept | rename one field | **Frozen label** (the key name is part of the hash recipe, ADR-0014 section 3) | renaming the key (changes every id in grids 1-4) |

**Patterns Expert test.** Every row reuses an idiom the repo already has or a standard one; no bespoke registry, base class or plugin point is added. **Simplifier test.** Nothing here is speculative: the N-arm generality is needed by EV-17 (3 arms) and costs no extra code over 2; `comparisons` exists because the board and the pack section read a pair; `ring` and `campaign` are written verbatim because W0 fixed them for X-C and X-A3. Bounded shortcuts, marked in code:
- `simplify:` `MAX_DRAWS = 100`; ceiling: the longest chance run seen is 40 draws (2 blocks x 3 arms; 44 in the SP-A6 re-run); upgrade trigger: a plan shape that exhausts it, which refuses (2 blocks x 4 arms does so for 1.8 % of seeds, SP-A6) and is a signal to add blocks, not to raise the cap.
- `simplify:` positions are compared with exact `Fraction` arithmetic over all cells, O(N x arms); ceiling: 100,000 cells x 100 draws is under 10^7 operations; trigger: plans past that.
- No `MAX_ARMS` cap: arm count is operator-chosen and cells are bounded by the confirmed envelope the operator reads (accepted, section 8 D).

## 5. The E1 / E3 split (stated)

**E1 (X-A1, Sonnet per R-88).**
| deliverable | files |
| --- | --- |
| `bench-matrix/2` validation, upcast, quoted-id rule, `ARM_OFF`, `ARM_ID`, ring validation | `config.py` |
| `bench-plan/2` writer, `Cell.arm`, label, `arms`, `comparisons`, `launch_seed`, `kind`, `campaign`, `ring`, accessors, `launch_order`, `launch_balance`, `draw_launch_order`, ready rule, `parse_binding`, `resolve_arms`, the Copilot probe per `(task, arm)`, schema check on load | `plan.py` |
| `CellView.pack` filled from `cell_arm` | `views.py` |
| `pre_turn_commit` reads the arm | `grade/_changes.py` |
| `_workspace_builder` per arm | `cli.py` (this function only) |
| `bench/rings/pilot.yaml` (R-89 shape) | new |
| G1 guard with the E1 allowlist | `tests/test_arms_guard.py` (new) |
| tests and fixtures, mutants | `tests/test_plan.py`, `test_config.py`, `test_views.py`, `test_workspace.py`, `test_cli.py` (that function), `tests/mutations/plan.json`, `tests/fixtures/plans/grid4-cells.json` |
| `cmd_plan` lines | X-C (SR-2, granted), `cli.py` |
| `plan_pack` one-line migrations (W0 rev 3); `_build_pack_effect` status text (SR-3 (a), granted) | `report/pack_improvement.py` (`cell_arm`), `board.py`, `report/summaries.py`; `html.py` header lines handed to X-H2 |

**E3 (X-A3).** The readers move from literals to comparison pairs; the ring refusal; `calibration`; the allowlist narrows. Nothing in `plan.py` changes shape.
| deliverable | files |
| --- | --- |
| `cells[].calibration` (EV-9: at most DR-T5 tasks, marked, excluded from verdicts) | `plan.py`, `config.py` (field), X-H1/X-H2 read it |
| ring-hash refusal on comparison (`HB-PLN-003`, EV-15), using the `ring.hash` E1 already writes | `board.py` compare, `plan.py` helper |
| pack section and board per comparison pair; `plan.comparisons` replaces the literals | `board.py`, `report/pack_improvement.py`, `report/summaries.py` |
| header: one row per arm with pack revision and commit; CSS/JS `pack-on` / `pack-off` toggles from the arm list | `report/html.py`, `report/assets/report.js` |
| `board.compare` pack-revision equality via `arm_pack` per arm (ADR-0014 hard precondition) | `board.py:756` |
| `cli_table.py`, `context_growth.py` column naming | those files |
| third-arm end-to-end fixture, 3-arm report | tests |

### 5.1 Every on/off literal site, mapped (convergence condition)

| site (read this tree) | what it does | change | phase |
| --- | --- | --- | --- |
| `config.py:35` `PACKS = ("on","off")`; `:107-111` `packs` check | validates `/1` packs | `PACKS` kept for `/1` only; arms rules added | E1 |
| `plan.py:75, 80` `Cell.id`, `label` | recipe and label | `arm`; recipe key kept | E1 |
| `plan.py:124` loop `for pack in matrix["packs"]` | enumerates | `for arm in arms_of(matrix)` | E1 |
| `plan.py:303-310` probe `arm == "on"`, `arm == "off"` | install pack / refuse instruction files | by `arm_packs[arm] is None` | E1 |
| `plan.py:342, 347` body `pack`, `cells[].pack` | writes | `arms`, `cells[].arm` | E1 |
| `cli.py:145-148` | installs pack by literal `on` | section 3.7 | E1 |
| `cli.py:110-124` `_pack`, table | one pack | per arm (SR-2) | E1 (X-C) |
| `views.py:525` | `pack=cell["pack"]` | `cell_arm(cell)` | E1 |
| `grade/_changes.py:84` | `!= "on"` | `== ARM_OFF` | E1 |
| `board.py:540, 555` `{"off","on"} <=` | "one pack setting" gate | comparison pair; the status text edit is E1 (SR-3 (a), granted) | E3 (text E1) |
| `board.py:586, 597, 605, 620, 646` | off/on observations, labels | comparison pair | E3 |
| `board.py:755-757` | `plan["pack"]["revision"]` | `plan_pack(plan)` in E1 (W0 rev 3); `arm_pack` per arm in E3 | E1 / E3 |
| `board.py:769` `packs = ("off","on")` | compare rows | comparison pair | E3 |
| `report/pack_improvement.py:746-747` | reads the raw cell `pack` to count planned cells | `cell_arm(c)` (a cell field; W0 rev 3's four-reader list, the cell-level one) | E1 |
| `report/pack_improvement.py:131-132` | pairs need `on` and `off` | pair by comparison | E3 |
| `report/pack_improvement.py:995, 1012, 1254` | `!= "on"`, `.get("off")`, `== "on"` | reference/treatment arm | E3 |
| `report/summaries.py:207, 211` | `== "off"`, `!= "on"` | reference/treatment arm | E3 |
| `report/summaries.py:177`, `report/html.py:265-266, 288` | plan-level pack revision | `plan_pack(plan)` in E1 (`html.py` through X-H2); per-arm header in E3 | E1 / E3 |
| `report/html.py:143-144, 717, 1224, 1245, 1449, 1474` | CSS toggles, setting filter, dashed marker, arm loop | arm list from the plan | E3 |
| `report/assets/report.js:79, 147-149` | `setting === "on"` / `"off"` | arm list; counted by the literal ratchet (3.8) | E3 |
| `report/cli_table.py`, `report/context_growth.py` | print `r.pack` / group by it | column named by the arm | E3 (they render any id without change) |

## 6. Change-surface list (E7): store, model, service, wire, client, UI, compute reader

1. **Store.** `bench/rings/pilot.yaml` (new); `runs/<id>/matrix.yaml` (`/start-benchmark` must emit quoted ids: the compile skill's template is X-C/Coordinator territory, noted in section 13); `runs/<id>/plan.json` `/2`; `cell.workspace_built` events; `tests/fixtures/plans/grid4-cells.json`.
2. **Model.** `config.py` (`ARM_ID`, `ARM_OFF`, `validate_matrix`, `validate_repo` rings); `plan.py` (everything in 3.1-3.6).
3. **Service.** `cli.py` `cmd_plan` (SR-2), `_workspace_builder`; `engine.py` needs **no** edit (it launches `plan["cells"]` in order and reads no arm: `engine.py:380`; searched for `pack`: no hits); `preflight.py` and `status.py` read labels only (pattern unchanged).
4. **Projection / wire.** `views.py` (`CellView.pack` = arm id); `bench-status/1` label/id patterns (unchanged); board and report row objects keep the attribute name `pack`.
5. **Client type.** `report/assets/report.js` and `data-pack` attributes carry the arm id; `on`/`off` toggles are E3.
6. **UI.** Report header (`plan_pack`, through X-H2) and section 2 text (SR-3 (a)); E3 per-pair blocks.
7. **Compute reader.** `grade/_changes.py` (migrated now); the four plan-level readers move to `plan_pack` / `cell_arm` in E1 (3.8); `board.py`, `pack_improvement.py`, `summaries.py` literals (E3); the two ratchets (3.8) record exactly what is not yet migrated.

## 7. Failure-mode analysis

| # | mode (category) | disposition | detect | test node |
| --- | --- | --- | --- | --- |
| F1 | bare `off`/`on` in YAML becomes a boolean (input) | **prevent**: refuse boolean id / comparison entry | `validate_matrix` Problems item naming the field and the quoting fix | `test_config.py::test_an_unquoted_off_arm_id_is_refused` |
| F2 | arm set malformed: duplicate id, two `off`, `off` with a pack, one arm in `/2`, bad id (input) | prevent | Problems items | `test_config.py::test_matrix_2_arm_rules` (parametrised) |
| F3 | pack `commit` is a branch, short, or starts with `-`; `source` relative (input, hostile) | prevent: 40-hex, absolute | Problems / `HB-PLN-002` | `test_config.py::test_pack_commit_must_be_a_full_hex_sha_and_source_absolute` |
| F4 | role unbound; binding names no arm, `off`, or an arm that already has a pack (input) | prevent | `HB-PLN-002` naming the arm | `test_plan.py::test_resolve_arms_refuses_each_binding_error` |
| F5 | launch order cannot meet the 5 % bound (one block) (state) | prevent: refuse | `HB-PLN-001` naming blocks and arms | `test_plan.py::test_a_one_block_plan_is_refused_hb_pln_001` |
| F6 | a chance seed fails the bound (state) | recover: bounded redraw; stored seed always passes | plan output prints seed and draw count; `plan.order.drawn` log | `test_plan.py::test_a_failing_first_draw_is_redrawn_and_the_stored_seed_replays` |
| F7 | redraw loop runs away (resource) | prevent: `MAX_DRAWS` | `HB-PLN-001` | `test_plan.py::test_redraw_stops_at_the_cap` |
| F8 | a selected task is not `ready` (state) | prevent: refuse, list all | `HB-PLN-004` | `test_plan.py::test_a_measurement_plan_refuses_every_task_that_is_not_ready` |
| F9 | `bench plan` for a `/1` matrix with only `["off"]` needs a pack (state) | prevent: no pack resolved | n/a | `test_cli.py::test_an_off_only_matrix_plans_without_a_pack_clone` |
| F10 | two arms share one pack checkout dir (concurrency/state) | prevent: `pack_checkout` keys by commit prefix; same commit means the same pack by design | `HB-PRE-007` if a dir is at another head | `test_workspace.py::test_two_arms_with_two_commits_get_two_checkouts` |
| F11 | an arm's workspace gets another arm's pack (state) | prevent: builder reads `arm_pack(plan, cell_arm(cell))` only | event `pack_commit` | `test_cli.py::test_workspace_builder_installs_each_arms_own_pack` |
| F12 | legacy plan-level reader degrades silently on a `/2` plan (state) | **prevent (E1)**: the four readers read `plan_pack` / `cell_arm`; a plan with 2 or more pack-bearing arms raises HB-PLN-005 | stable code; the E3 migration retires it | `test_plan.py::test_plan_pack_reads_both_schemas_and_refuses_two_pack_arms`; `test_report.py::test_plan_level_readers_state_the_true_pack_or_refuse` (the four readers, red today); `::test_an_off_candidate_run_renders_without_raising` |
| F22 | a new direct read of `pack`, or a bare `"on"`/`"off"`, appears in an allowlisted file (state) | **prevent**: the per-file count ratchets | `tests/test_arms_guard.py` | `::test_no_file_exceeds_its_pinned_pack_hit_count`, `::test_bare_arm_literals_do_not_exceed_their_pinned_counts` |
| F13 | plan `/2` read by an engine that predates it (state) | prevent: schema allow-list on load | `HB-USR-002` | `test_plan.py::test_load_confirmed_refuses_an_unknown_schema` |
| F14 | a `/1` run read through the accessors drifts (state) | prevent: accessors + golden | | `test_plan.py::test_plan_1_loads_through_the_accessors` |
| F15 | two `bench plan --confirm` for one run id race (concurrency) | prevent: `confirm` opens with `"x"`; the first writer wins and the loser fails; the seeds differ, so the loser's plan is simply not frozen | `HB-USR-002` "already confirmed" | existing `test_confirm_freezes_the_plan_and_refuses_a_second_write` |
| F16 | crash mid-write leaves a truncated `plan.json` (partial write) | **consciously accept** for E1: pre-existing; `load_confirmed` fails on a truncated file rather than reading it. Residual: the operator re-plans under a new run id. Upgrade trigger: `atomic.create_once` lands (X-B1) and a separate request moves `confirm` onto it (it changes the conflict code from `HB-USR-002` to `HB-LED-007`, so it is not done here) | JSON error on load | none (no change) |
| F17 | resume re-draws the order (time/state) | prevent: the order is stored; resume reads `cells` | | covered by the stored-order equality test |
| F18 | host clock skew or timezone changes the seed (time) | prevent: seed from `secrets`, not time | | n/a by design |
| F19 | huge plan (resource) | consciously accept: bounded by what the operator confirms (envelope shown) | | |
| F20 | `launch_seed` collides with another plan's (state) | accept: a seed names an order for one cell set; collisions are harmless | | |
| F21 | an arm id with a trailing newline passes `$`-anchored regex (input, hostile) | prevent: `fullmatch` | | `test_config.py::test_arm_id_uses_fullmatch` |

## 8. Adversarial analysis (STRIDE-lite)

**Trust boundaries.** (A) matrix/ring YAML (committed, operator-authored, or compiled from prose) into `config` and `plan`. (B) `--arm role=source@commit` argv into `parse_binding`. (C) pack repository content into the cell workspace via `pack-apply.py` (existing; unchanged by this slice). (D) `plan.json` at rest into engine, grader, report. (E) arm ids into file paths, labels, HTML attributes and `git` argv.

| STRIDE | threat | disposition | negative test |
| --- | --- | --- | --- |
| S | an arm named `off` (or `on`) carries a pack, so a reader treats it as pack-less or pack-bearing wrongly | **mitigate**: `off` may not carry a pack; every other arm must (or be a bound role); the migrated readers use `cell_arm != ARM_OFF` | `test_off_arm_with_a_pack_is_refused`; `test_pre_turn_commit_treats_every_non_off_arm_as_pack_bearing` |
| T | `commit` as `--upload-pack=...` or `source` as an option reaches `git clone`/`checkout` | **mitigate**: 40-hex commit and absolute source (a path never starts with `-`) | `test_pack_commit_must_be_a_full_hex_sha_and_source_absolute` |
| T | a confirmed plan edited to change an arm's pack | **mitigate**: `plan_hash` recomputed on load (existing, covers `arms`) | existing `test_load_confirmed_detects_an_edited_plan`, extended with an `arms` edit |
| T | arm id used as a path segment (`../x`) in the Copilot probe dir `probe/homes/<task>/<arm>` | **mitigate**: id regex excludes `.` and `/`; `fullmatch` | `test_arm_id_uses_fullmatch` (includes `../x`, `a\nb`) |
| R | no evidence which pack a cell ran | **mitigate**: `cell.workspace_built` records `arm` and `pack_commit`; the plan records `arms` | `test_workspace_builder_installs_each_arms_own_pack` |
| I | `source` is an operator-local path (may carry a user name) written to `plan.json` and, in X-C, perhaps into a committed prereg | **mitigate in part, hand-off**: the plan is a run-local file (as `plan.pack.source` is today); the **prereg must store `{commit, revision}`, not the path**: W1-C decides, noted in section 13. Report headers show revision and commit only (unchanged) | W1-C's test |
| D | a matrix with very many arms/combos/reps | **accept**: the envelope is shown before `--confirm`; the order loop is bounded (`MAX_DRAWS` x O(N log N)) | none |
| E | a role binding gives a hostile repo's pack to the `candidate` arm | **transfer, named**: the pack content runs `pack-apply.py` in the cell workspace under the existing cell sandbox and egress rules (ADR-0013); the operator supplies the commit by hand; this slice adds no new execution | n/a (existing control) |

No new network access, credentials or process spawning enter this slice (the builder's `install_pack` call is unchanged).

**Privacy (LINDDUN-lite).** The slice touches no personal data about a person: arm ids, commit hashes, task ids. One line to record: `pack.source` is a local filesystem path that may contain a user name; it exists in `plan.json` today (grid-4's reads `C:\Projects\ai-forward-fix-close-artifacts`), `plan.json` is git-ignored, and the reports print revision and commit only. No retention or rights-path change.

## 9. Telemetry (Observability Standard)

Questions an operator asks, each with a named source:
| question | source |
| --- | --- |
| which seed, how many redraws, how balanced is this order? | `bench plan` output line and log event `plan.order.drawn` {`run_id`, `launch_seed`, `draws`, `max_arm_deviation_ppm`, `blocks`, `arms`} |
| why was the plan refused? | stable codes `HB-PLN-001/002/004`, each message naming the arm, task or shape; event `plan.refused` {`code`, `run_id`} |
| how long did planning take (the Copilot probe dominates)? | `plan.built` {`run_id`, `cells`, `arms`, `kind`, `plan_ms`} from the one `logger` already in `plan.py` |
| which pack did this cell's workspace get? | `cell.workspace_built` {`arm`, `pack_commit`, `pack_manifest`} |
| how many cells per arm? | the plan table (one row per arm) |

All through `logging.getLogger("harness_bench.plan")` structured `extra` (the module's existing logger); `max_arm_deviation_ppm` is an int (the canonical form has no floats). No HTTP surface, so no RFC 9457. Planned tests: `test_plan.py::test_plan_logs_order_drawn_and_built` (caplog: fields present, no path and no environment value in them). Degrades to "not recorded": a refused plan emits `plan.refused` only.

## 10. Test plan (red first; node ids; Testing Strategy union)

**Directives selected.** D0 always (no wall clock, no sleeps; seeds injected; temp dirs; the Copilot probe stays faked through the fake-exe tests already in `tests/test_plan.py`). T1 pure functions (`launch_order`, `launch_balance`, `default_comparisons`, accessors, `parse_binding`, `resolve_arms`): **D1**, with property tests on the balance bound. T2 parsers / validators (`validate_matrix`, `parse_binding`, ARM_ID): **D2**, hostile and boundary inputs. T3 structural (G1 and the literal ratchet; run-class modules do not import grade-class ones): **D3**. The rule that `plan.py` imports neither `campaign` nor `identity` is X-D's G3, not tested here (RV-SIM 7). T4 filesystem (plan.json write-once, ring file hash): **D4**. T7 persisted payload schema (`bench-plan/2`, golden `/1` read): **D6**. T8 fakes (fake pack repo, fake `install_pack`): **D7**, each paired with a fidelity test (the real-git `_workspace_builder` test). T5/T6/T9-T14: not triggered (no network consumer or provider, no model call).

**Red must fail on behaviour (README 2a.1; RV-TA 8).** The first red commit is a **skeleton** commit: stubs for every new symbol that raise `NotImplementedError` (`config.ARM_OFF`, `config.ARM_ID`, `plan.cell_arm`, `arm_pack`, `plan_comparisons`, `plan_pack`, `arms_of`, `default_comparisons`, `parse_binding`, `resolve_arms`, `launch_order`, `launch_balance`, `draw_launch_order`). No test imports a name that does not exist, so none is red by `ImportError`, `AttributeError` or `NameError`; each fails on an assertion or on the stub's `NotImplementedError` at the line that calls it. The tests that exercise existing symbols (the reader and workspace tests) fail on their assertion today: a `/2` cell has no `pack` key (`views.py`), `candidate` is wrongly treated as pack-less (`_changes.py`), the workspace for arm `candidate` gets no pack (`cli.py:145`).

**EV-17 criterion map (each to a named node).**
| EV-17 criterion | test nodes (red first) |
| --- | --- |
| 1: three arms, one pack per pack-on arm, none for off, one cell per arm per `(task, combo, rep)` | `tests/test_plan.py::test_a_three_arm_plan_has_one_cell_per_task_combo_rep_per_arm`; `::test_arms_freeze_one_pack_revision_per_non_off_arm_and_none_for_off` |
| 2: **grid-4 re-plan equivalence** | **Entry point (RV-TA 6): `plan.build_plan`**, not `expand` alone, so `arms_of`, the cell construction with `arm` and the `/1` read are on the path: `tests/test_plan.py::test_grid4_replan_gives_the_same_task_combo_arm_rep_set_and_cell_ids` calls `build_plan` over grid-4's matrix with injected frozen task versions and a fake pack record per arm (`on`, `off`), and asserts the set and each of the 276 ids equal (order free). **Fixture provenance (RV-TA 7):** `tests/fixtures/plans/grid4-cells.json` is extracted once from `runs/grid-4/plan.json` and carries a header `{"source": "runs/grid-4/plan.json", "sha256": "<of that file>", "extracted": "2026-10-03"}`; no generator exists in `tests/`, and a test (`::test_grid4_fixture_declares_its_source`) fails if the header is absent, so a fixture regenerated from the new code cannot pass. Red today: `build_plan` has no `arms` (a `NotImplementedError` stub path); the `/1` ids it must reproduce are the ones SP-A1 matched. Companions: `::test_cell_id_ingredients_keep_the_pack_key_name` (red if the ingredient dict's keys change); `::test_plan_1_loads_through_the_accessors` (arm of every legacy cell; `arm_pack` on and off; comparisons `[("off","on")]`) |
| 3: seeded permutation recorded with its seed; mean launch position within 5 % | `::test_launch_order_is_a_pure_function_of_the_seed`; `::test_every_block_holds_every_arm_exactly_once`; `::test_accepted_plans_meet_the_balance_bound` (parametrised 3x2, 4x2, 20x2, 138x2, 3x3, 20x3, 3x4 over 50 seeds each, bound recomputed independently from raw positions with `Fraction`); `::test_the_bound_is_strict` (a hand-built order whose deviation is **exactly** 1/20 is refused by `draw_launch_order(launch_seed=...)`, and one at 1/20 minus one position is accepted; RV-TA 5); `::test_a_four_arm_shape_refuses_with_the_shape_and_draws` (2 blocks x 4 arms with a pinned seed from SP-A6 that exhausts a lowered cap: the message names 2 blocks, 4 arms and the draws made, and no block minimum; RV-PAT 3); `::test_cells_order_equals_the_order_derived_from_launch_seed`; `::test_a_one_block_plan_is_refused_hb_pln_001`; `::test_a_failing_first_draw_is_redrawn_and_the_stored_seed_replays` (the pilot shape, a seed pinned from SP-A2 that fails, `draw` injected); `::test_redraw_stops_at_the_cap` |
| 4: per-arm workspace differs only by that arm's manifest | **Real wiring (RV-TA 2): `tests/test_cli.py::test_workspace_builder_real_git_gives_each_arm_its_own_pack`** drives `cli._workspace_builder` itself (the harness at `tests/test_cli.py:357` already builds `build`) with two tiny real pack repos at two commits and the real `install_pack`, for arms `x`, `y` and `off`; it asserts `git diff --name-status <base>..HEAD` equals that arm's manifest and is empty for `off`. Red today: the builder keys on the literal `on` (`cli.py:145`), so arm `x` gets no pack and the diff is empty. It fails if the `arm_pack(plan, cell_arm(cell))` line is removed or points at the wrong commit. Beside it, the fast fake test `::test_workspace_builder_installs_each_arms_own_pack` (fake `install_pack`; `pack_commit` per arm in the event) stays. The revision-1 `test_workspace.py` node is dropped: it called `workspace` functions directly and is covered by the builder test |

**Trace requirement (W0 section 14 / RV-TA 14): each W0 contract this slice implements maps to a named test.**
| W0 contract | test node |
| --- | --- |
| section 5 `bench-matrix/2` shape and arm rules | `test_config.py::test_matrix_2_arm_rules`, `::test_an_unquoted_off_arm_id_is_refused`, `::test_rings_validate_in_validate_repo` |
| section 5 role: unbound role refused (HB-PLN-002) | `test_plan.py::test_resolve_arms_refuses_each_binding_error` |
| section 5 comparisons default | `test_plan.py::test_default_comparisons_follow_the_one_reader_rule` (0/1/2/3 arms, `off` first or second) |
| section 5 `bench-plan/2` fields, `launch_seed` stored, `campaign` verbatim, `ring` hash | `test_plan.py::test_plan_2_records_arms_comparisons_seed_kind`, `::test_campaign_block_is_written_verbatim_and_absent_otherwise`, `::test_ring_hash_is_the_tree_hash_of_the_ring_file_and_ignores_crlf` |
| section 5 accessors | `::test_cell_arm_and_arm_pack_read_both_schemas`, `::test_an_unknown_arm_raises_a_bench_error` |
| section 5 label constraint | `::test_plan_2_labels_match_config_label_and_name_the_arm` |
| section 5 `cell_id` golden (RV-TA 13), see erratum 2 | `::test_grid4_replan_...` (real ids) |
| section 5 launch balance HB-PLN-001 | the EV-17 criterion 3 nodes |
| section 10 G1 (four fields, rev 3 tokens and ratchet) | `tests/test_arms_guard.py::test_no_file_exceeds_its_pinned_pack_hit_count` (the real tree), `::test_the_guard_flags_each_token_form_in_a_fixture_tree` (one file per form including `.pop`, `in`, `getattr`, keyword; plus the comment-only and docstring-only files; red fixture), `::test_a_count_above_its_pin_fails_and_below_passes` (fixture tree, ratchet direction). Dropped (RV-SIM 6): the comment-only test (a fixture file in the flag test) and the allowlist-equality test (a constant checked against a copy of itself; E3's narrowing is the ratchet itself). The allowlist is checked against the tree by the scan: SP-A6 pinned counts, 114 hits in 11 files on the base |
| W0 rev 3 literal sweep (RV-TA 1) | `tests/test_arms_guard.py::test_bare_arm_literals_do_not_exceed_their_pinned_counts` (Python, 34 string `Constant`s in 8 files on the base), `::test_report_js_arm_literals_do_not_exceed_the_pinned_count` (2 on the base), each with its red fixture (3.8) |
| W0 rev 3 section 5 `plan_pack` and the four readers | `test_plan.py::test_plan_pack_reads_both_schemas_and_refuses_two_pack_arms`; `test_report.py::test_plan_level_readers_state_the_true_pack_or_refuse` (the three plan-level readers and the cell-level `pack_improvement` read, each on a `/2` plan with one pack-bearing arm stating the true revision or count, and on two pack-bearing arms raising HB-PLN-005; red against today's code) |
| section 10 G1 migrations | `test_views.py::test_cellview_pack_is_the_arm_id`, `test_changes_cache.py::test_pre_turn_commit_treats_every_non_off_arm_as_pack_bearing` |
| section 11 HB-PLN-001, 002, 004, 005 | the nodes above and `::test_a_measurement_plan_refuses_every_task_that_is_not_ready` (names every task, no cap), `::test_a_discrimination_plan_accepts_draft_and_refuses_stub` |
| section 13 `plan.py` / `config.py` / `views.py` ownership | none here. "`plan.py` imports neither `campaign` nor `identity`" is X-D's G3 in `tests/test_architecture.py` (RV-SIM 7; RV-TA 3's red-fixture condition moves with it: *assume:* G3 carries a red fixture for `from . import campaign`; confirmed when X-D's design is read at the join; if false, a campaign import in `plan.py` is caught by nothing) |

**Other nodes.** Run-side D3: `plan.py` imports no `grade` or `report` module (existing structural test extended to `plan`). **Mutants** (`tests/mutations/plan.json`, kept in step; RV-SIM 8 cut the list to what separates a failure): the two Copilot-probe mutants are re-pointed at the new lines (`if arm == "on":` and `if arm == "off" and rows:` no longer exist); new mutants, each killed by a named test: **drop the balance check** (`test_accepted_plans_meet_the_balance_bound`), **drop the unbound-role check** (`test_resolve_arms_refuses_each_binding_error`), **drop the not-ready check** (`test_a_measurement_plan_refuses_every_task_that_is_not_ready`), and, from RV-TA 5, **`<` to `<=` in the bound** (`test_the_bound_is_strict`). Dropped: "sort blocks by the wrong key" (no balance consequence, RV-SIM 2/8) and "keep `pack` under another name" (repeats the ingredient-key test). **Non-regression:** `EVU-4`-style report goldens for non-campaign `/1` runs unchanged (existing `test_pack_improvement_golden.py`, `board_golden`, catalog `golden` hashes: not edited by this slice; a red there is a defect).

**Rings.** Fast ring (every push): all of the above; the grid-4 fixture test is pure computation (a few ms). One-time proof: SP-A1 (live `runs/grid-4` vs the committed fixture) was run once now; it does not become a continuous test, because the fixture test catches every drift the live one would.

## 11. Spikes and evidence (read and run, 2026-10-03, on this tree)

| id | question | result |
| --- | --- | --- |
| SP-A0 | does `config.load_yaml` read bare `off` as a string? | **No.** `arms: [{id: off}]` loads as `{'id': False}`; `comparisons: [[off, candidate]]` as `[[False, 'candidate']]`; `["off", on, yes, no]` as `['off', True, True, False]` (PyYAML 6.0.3, `safe_load`). W0 section 5 is unquoted: erratum 1 |
| SP-A1 | does today's `expand`, given grid-4's matrix, frozen task versions and `bench/bom.yaml`, reproduce `runs/grid-4/plan.json`? | **Yes, exactly:** 276 of 276 cell ids, tuples `(task, combo, pack, rep)`, labels and order equal; no BOM budget drift in the 23 tasks. So the equivalence test compares against a real baseline, and the fixture is derivable |
| SP-A2 | does the blocked, hash-keyed order meet the 5 % bound, and how often does a chance seed fail? | table in section 3.4 (2,000 seeds per shape, cap 100 draws). One block unsatisfiable; the pilot shape fails 25 % on the first draw and always passes within 7 draws; 138 blocks x 2 arms (grid-4 shape) and every shape from 6 blocks pass first time |
| SP-A3 | do the legacy readers raise on arm ids `off` / `candidate`? (W0 G1 assume) | **No exception** from `board.build`, `pack_improvement.assemble`, `html.render`. **Wrong statements:** board says "This run has one pack setting; no effect to show."; the pack section is `no_pairs`; the header shows no pack revision. SR-3 |
| SP-A4 | do the fixtures W0 names for the `cell_id` golden carry real ids? | **No:** `tests/fixtures/ledger/heads/run/plan.json` and `c44dd2b-no-heads/run/plan.json` have ids `a`, `b`, no `schema`; 0 of 4 equal the recipe. Erratum 2 |
| SP-A5 | which files read the arm outside the allowlist (the G1 scan, run) | **By the revision-1 three-form AST scan, exactly three:** `cli.py` (145, 146, 148), `grade/_changes.py` (84), `views.py` (525). By W0 rev 2's regex, four (plus `grade/formal.py`, a comment). Superseded for counts by SP-A6 (the rev-3 token set) |
| SP-A6 | **(revision 2)** the rev-3 token set and the literal sweep, run on this tree (merged main), plus two 4-arm shapes | **`"pack"` tokens:** 114 hits in 11 files: `board.py` 30, `report/html.py` 40, `report/pack_improvement.py` 9, `report/cli_table.py` 7, `report/summaries.py` 6, `cli.py` 7, `plan.py` 8, `report/context_growth.py` 2, `views.py` 2, `workspace.py` 2, `grade/_changes.py` 1. **`workspace.py` (225, 233) and two `cli.py` hits (110, 169) are `/ "pack"` path segments**, not cell reads, which the three-form scan missed. **Bare `"on"`/`"off"` constants:** 34 in 8 files (`board.py` 12, `report/html.py` 7, `report/pack_improvement.py` 7, `report/summaries.py` 2, `config.py` 2, `plan.py` 2, `cli.py` 1, `grade/_changes.py` 1); **`report.js`:** 2. **Balance, 2,000 seeds, cap 100, hash-keyed recipe of 3.4 (a different draw sequence from SP-A2, so maxima differ by a few draws):** 3 x 2 first-draw 0.757, max 6; 2 x 3 0.180, max 44; **2 x 4 0.046, mean 22.7, max 100, 36 unsatisfiable (1.8 %)**; 3 x 4 0.303, max 22; 4 x 4 0.650, max 9; 6 x 4 0.987, max 2 |

Scratch scripts were not committed (one-time proofs). The numbers are reproducible from the recipe in sections 3.4 and 10.

## 12. Decisions, errata, seam requests, ADR amendment text

**Decisions made here** (all inside W0's "narrow or detail").
| id | decision | reversible by |
| --- | --- | --- |
| AD-1 | every new plan is `bench-plan/2`, including from a `/1` matrix | a later schema |
| AD-2 | top-level `pack` is dropped in `/2`; **ratified by W0 rev 3 section 5** (the removal is listed there, with `plan_pack` and HB-PLN-005) | cheap until E3 |
| AD-3 | hash-keyed order; bounded redraw; `MAX_DRAWS = 100` | change the constant or the key |
| AD-4 | label `{task}.{combo}.arm-{arm}.r{rep}` | `/1` labels untouched, so cheap |
| AD-5 | ready rule A, by plan kind | one `if` |
| AD-6 | G1 as AST nodes | the test file |
| AD-7 | event key `arm` (+ `pack_commit`) | additive |
| AD-8 | `CellView.pack` keeps its name (holds the arm id) | E3 rename |
| AD-9 | `--pack-source` applies to `/1` only; `--arm` binds roles | CLI flag |
| AD-10 | (revision 2) the plan-level readers read `plan_pack`; the cell-level `pack_improvement` read uses `cell_arm`; G1 is a per-file count ratchet; a second ratchet counts bare `on`/`off` and `report.js`; `workspace.py` and `cli.py` carry two permanent directory-name hits | the test file |
No decision here needs the Owner; no decision request was filed.

**Seam requests and errata: all answered in W0 rev 3** (the Coordinator's change table, by seam id). Revision 1 flagged them `provisional`; they no longer are.
| id | request | W0 rev 3 answer |
| --- | --- | --- |
| SR-1 `req-01M41DJ9Q6KTQ3RKNFVZHPRJ8V` | quote the ids in section 5 (SP-A0); `HB-PLN-004`; G1 tokens as AST nodes | granted: sections 1, 5, 10, 11. Rev 3 widened the tokens further (every `"pack"` constant) and made the allowlist a count ratchet (RV-PAT W1-A 2) |
| SR-2 `req-01M41DJ9TBKNZ0JJXY79SWS5Y4` | X-C pastes the `cmd_plan` lines of 3.9 | granted: X-C carries `cmd_plan` (section 13) |
| SR-3 `req-01M41DJ9Y9WYKGDX5N37N8FFN0` | E1 report text | granted, option (a): `board.py` text by X-A1, `html.py` header through X-H2 (sections 10, 13) |
| SR-4 `req-01M41DK5M0WS3PNX3WFNZ222WW` | `cell_id` golden fixtures | granted: `tests/fixtures/plans/grid4-cells.json` (sections 5, 13) |
| RV-PAT W1-A 1, 5 (not filed as a request) | the top-level `pack` drop | granted: `plan_pack`, HB-PLN-005, four readers migrated in E1 (section 5) |


**HB codes (all in W0 rev 3 section 11).** `HB-PLN-001` confirmed (launch-balance bound). `HB-PLN-002` confirmed, merged (unbound role, unknown role, a pack on `off`, a duplicate or second `off` at plan time, a malformed binding, `--pack-source` with a `/2` file; the cause is in the message). `HB-PLN-003` is not this slice's (E3). **`HB-PLN-004`** (granted): a measurement plan names a task that is not `ready` (every task and status listed). **`HB-PLN-005`** (W0 rev 3): a single-pack reader got a plan with two or more pack-bearing arms (`plan_pack`; names the arms; retired in E3). Static matrix-shape problems stay `Problems` items, not codes.

**ADR-0014 amendment text (for the Coordinator to append; this slice does not own the ADR).**
> *Amendment 1 (W1-A design, 2026-10-03; W0 rev 3 recorded it on the ADR).* (a) Section 4: `bench plan` draws the launch seed up to 100 times and stores the first seed whose order meets the bound; a shape with no such seed (a single block) is refused with HB-PLN-001. Ordering uses sorted SHA-256 keys of `(seed, block[, arm])`, not a PRNG, so a stored seed replays on any Python version. (b) Section 2: a `bench-plan/2` plan has no top-level `pack`; `arms` is the only statement of pack revisions. (c) Section 2 and the `Cell` label: a `bench-plan/2` label is `<task>.<combo>.arm-<arm>.r<rep>`. (d) A measurement plan refuses a task whose `status` is not `ready`; a discrimination plan refuses `stub` (HB-PLN-004). (e) Ids in a matrix file are quoted strings: bare `off` is a YAML boolean. (f) *(revision 2)* The plan-level readers of the pack read `plan_pack(plan)`; a plan with two or more pack-bearing arms raises HB-PLN-005 until the readers move to comparison pairs (E3). The guard of section 2 is a per-file count ratchet.

## 13. Hand-offs and open items (each owned elsewhere)

- **X-C (`/start-benchmark` compile, `cmd_plan`).** The compiled `matrix.yaml` must quote `off`/`on` arm ids. W1-C: the prereg should store each arm's `{commit, revision}`, not the local `source` path (section 8, Information disclosure).
- **X-E.** Passes `kind="discrimination"` and tasks in `draft`; reads the arm only through the accessors.
- **X-H2 / X-A3.** Read `plan_comparisons(plan)`; the E1 allowlist lists what is left.
- **Plan file atomicity** (F16): a follow-up for X-B1 / Coordinator, not scope here.
- **Residual: restricted randomisation.** The redraw conditions the order on balance. The analysis pairs within `(task, combo, rep)` blocks, so the drawn order does not enter any statistic; a reviewer who wants unconditional randomisation can ask for `MAX_DRAWS = 1` plus a bare refusal, at 25 % refusals for the pilot shape.
- **Residual: SR-3 is closed** by W0 rev 3 (option (a)). What remains in E1: `pack_improvement`'s section is `no_pairs` (empty) for an `off` / `candidate` run until E3; that sentence is true, not misleading.
- **Hand-offs from revision 2.** X-H2 (the `html.py` header lines 265, 266, 288 to `plan_pack`, from X-A1's lines); X-D (G3 must carry a red fixture for a `plan.py` import of `campaign` or `identity`); X-E (`status: ready` written only by the readiness path, 3.5).
- **Flagged unknown.** The engine's behaviour with an order that is not rep-major (it launches `pending.pop(0)`, `engine.py:380`) was read, not run on a randomised list; the existing `tests/test_engine.py` builds cells in any order and passes `cells` straight through, so the risk is low. X-INT's E1 run confirms.

## 14. Confidence ledger

| claim | label |
| --- | --- |
| today's `expand` reproduces grid-4's 276 ids, tuples, labels, order | Verified (SP-A1, executed) |
| bare `off` loads as `False` | Verified (SP-A0) |
| balance and redraw figures | Verified (SP-A2, executed; the prototype is the recipe in 3.4, the shipped code is X-A1's) |
| legacy readers do not raise on `off` / `candidate`; they print a wrong sentence | Verified (SP-A3, executed on the shown entry points) |
| the named fixtures hold hand-made ids | Verified (SP-A4) |
| engine reads no arm and launches in list order | Verified by reading (`engine.py:380`, search of `pack`); not run on a shuffled plan: Inferred for the run |
| no runtime reader of `pack_manifest` / `workspace_built.pack` | Verified by search of `src/` |
| the AST guard is green after the three migrations | Verified for the scan (SP-A5 lists exactly three outside files); green-after-migration is proven by the red-then-green commit |
| a `views.py` import of `plan` adds no cycle | Verified: `views.py:41` already imports `plan` |
| the rev-3 token scan finds 114 `"pack"` hits in 11 files, and 34 bare `on`/`off` constants in 8 files, plus 2 in `report.js` | Verified (SP-A6, executed) |
| 2 blocks x 4 arms exhausts the cap for 1.8 % of seeds; 3 x 4 and above do not | Verified (SP-A6, 2,000 seeds; the prototype is the recipe of 3.4) |
| `status: ready` is written only by X-E's readiness path | Inferred (assume: in 3.5) |
| X-D's G3 carries a red fixture for a `plan.py` import of `campaign`/`identity` | Inferred (assume: in section 10) |

## 15. Self-check against the Definition of Done, and Gate record

Met: single responsibility and contracts (1, 3); data model first with aggregates, invariant, representation, grain, additivity, history, derive-don't-store, writer and reader (2); E7 list (6); phasing and mock seams (1, 5); local conventions (1); consumed contracts established and spiked (11); patterns named, Ladder climbed, `simplify:` markers (4); failure modes (7); STRIDE (8); privacy one-line negative (8); no UI of its own (the report text is SR-3); testing union and EV-17 map (10); telemetry (9); confidence ledger and residuals (13, 14). **Unmet / not done here:** the ADR-0014 amendment is text only; the hard vetoes are not cleared by the author; UI craft, DESIGN.md and generated assets are not applicable (no new interface).

**Revision 2 self-check.** Testability floor (README 2a): (1) the skeleton commit makes every new test red on behaviour, not on `ImportError` (section 10); (2) red fixtures for the guard, the literal ratchet and the ratchet direction (3.8); (3) the real-wiring `_workspace_builder` test beside the fake (section 10, criterion 4); (4) the mutant that separates the strict bound from `<=` (section 10); (5) the allowlist and the "every reader migrated" claim cite the scan run on this base, 114 and 34 hits (SP-A6). Unmet: the two `assume:` lines (3.5, section 10) await X-E's and X-D's designs; the hard veto is not cleared by the author.

### Gate record (copied verbatim from the three reviews in `docs/design/reviews/`)

`GATE W1-A · Test Architect · PASS WITH CONDITIONS · 8 findings (rv-ta-w1a-e1e4, 2026-10-03)`
`GATE W1-A · Simplifier · PASS WITH CONDITIONS · 8 findings (rv-sim-ad-e1e4, 2026-10-03)`
`GATE W1-A · Patterns Expert · PASS WITH CONDITIONS · 6 findings (rv-pat-ad-e1e4, 2026-10-03)`

Slice status: gate passed (RV-TA hard veto: no block; RV-SIM and RV-PAT: no blocking finding). Conditions applied in revision 2 (section 16). The author clears no veto.

| | |
|---|---|
| **Completed** | W1-A arms v2 design, revision 2: data model, contracts, E1/E3 split, EV-17 test map, guard with ratchets, `plan_pack` migration, six spikes; all 22 review findings dispositioned (section 16) |
| **Remaining** | X-H2 header lines; X-D and X-E hand-offs (section 13) |
| **Best next action** | X-A1 builds red-first from section 10: skeleton commit, then tests, then code |

## 16. Review disposition

Reviews: `docs/design/reviews/eval-review-ta-w1a.md` (TA), `eval-review-sim-w1a.md` (SIM), `eval-review-pat-w1a.md` (PAT). Disposition: **applied** (changed in this revision), **applied in part**, **settled** (answered by W0 rev 3), **recorded** (kept as a note), **declined** (with reason).

| id | finding (short) | disposition | where |
| --- | --- | --- | --- |
| TA 1 (major) | E1/E3 map has no control for bare `on`/`off` literals or `report.js` | applied: a second ratchet, Python constants (34 on the base) and a text scan of `report.js` (2), each with a red fixture | 3.8, 10 (trace), SP-A6, F22 |
| TA 2 (major) | per-arm wiring proved only with a faked `install_pack` | applied: `test_workspace_builder_real_git_gives_each_arm_its_own_pack` through `cli._workspace_builder`; the fake test stays; the `test_workspace.py` node is dropped as covered | 10 criterion 4 |
| TA 3 (major) | "`plan.py` imports no campaign/identity" test passes today, no red fixture | applied by deletion under SIM 7: the rule is X-D's G3; the red-fixture condition moves with it as a marked `assume:` and a hand-off | 10 (trace row), 13, 14 |
| TA 4 (minor) | G1 misses `getattr`, non-constant subscript; allowlist-equality test restates a constant | applied in part: `getattr`, `.pop`, `in`, keyword, `itemgetter` are now tokens with a fixture each (W0 rev 3 fixed the set); the equality test is dropped. A `cell.get(key)` read through a variable cannot be seen by any static scan; the ratchet bounds the files where it could hide | 3.8, 10 |
| TA 5 (minor) | no case at exactly 5/100; no `<` to `<=` mutant | applied: `test_the_bound_is_strict` and the mutant | 10 |
| TA 6 (minor) | grid-4 test entry point unstated | applied: `build_plan` with injected versions and a fake pack record per arm | 10 criterion 2 |
| TA 7 (minor) | fixture provenance "derivable", not recorded | applied: header with source path and sha256, no generator in `tests/`, a test that requires the header | 10 criterion 2 |
| TA 8 (minor) | new tests red by `ImportError` | applied: the skeleton commit of `NotImplementedError` stubs lands first | 10 |
| SIM 1 | hash-keyed order and redraw earn their place | recorded: no change | 3.4 |
| SIM 2 (minor) | name the Latin-square rotation as a rejected alternative | applied, with the reason (predictable period against the ADR's "seeded random order"; drift aliasing) | 4 |
| SIM 3 (minor) | pass-rate table to 3 rows | applied: 1 x A, 3 x 2 pilot, 2 x 3 | 3.4 |
| SIM 4 (minor) | HB-PLN-004 earns its place; drop the 12-offender cap | applied: every offender named, the cap and its test arm are gone | 3.5 |
| SIM 5 | G1 earns its place; allowlist is scaffolding | recorded: no change; the ratchet makes the narrowing measurable | 3.8 |
| SIM 6 (minor) | drop two G1 tests (comment-only, allowlist-equality) | applied | 10 (trace) |
| SIM 7 (minor) | drop the duplicate `plan.py` import test (X-D's G3 covers it) | applied; conflicts with TA 3 resolved as in TA 3 above | 10, 13 |
| SIM 8 (minor) | cut the mutants to 3 | applied in part: the three kept, two dropped, plus the `<` to `<=` mutant that TA 5 requires (4 new mutants); the extra one is the only one that separates the strict bound | 10 |
| PAT 1 (major) | top-level `pack` drop turns four readers into silent degraders | settled by W0 rev 3 (`plan_pack`, HB-PLN-005); applied: the four sites migrate in E1, `pack_improvement.py:746-747` through `cell_arm` (it reads a cell, so `plan_pack` does not apply), a test per reader on `/2` plans with one and two pack-bearing arms | 2, 3.3, 3.8, 5.1, 7 (F12), 10 |
| PAT 2 (major) | G1 tokens miss `.pop`, `in`, `getattr`, keyword; allowlisted files exempt wholesale | settled by W0 rev 3 and applied: widened tokens, per-file count ratchet with pinned counts; consequence found by the wider scan: two permanent directory-name hits each in `workspace.py` and `cli.py` | 3.8, SP-A6 |
| PAT 3 (minor) | refusal text and cap shaped by the 2-arm case; 4-arm shapes untested | applied: the message reports shape and draws and claims no block minimum; 2 x 4 and 3 x 4 measured (2 x 4 exhausts the cap for 1.8 % of seeds, so the cap is not raised and the refusal is named); two tests added | 3.4, 10, SP-A6 |
| PAT 4 (minor) | three names for one concept; nothing makes E3 rename `CellView.pack` | applied: the rename is triggered by the ratchet reaching zero | 2 |
| PAT 5 (major) | the `pack` drop is in no seam request | settled by W0 rev 3 section 5; AD-2 records the ratification | 12 |
| PAT 6 (minor) | "ready" may be two predicates | applied in part: one predicate stated, with an `assume:` that `status: ready` is written only by X-E's readiness path and a hand-off test at X-E's seam; not confirmed here | 3.5, 13 |

The revision-1 requests SR-1..SR-4 are answered in W0 rev 3; section 12 records each answer.
