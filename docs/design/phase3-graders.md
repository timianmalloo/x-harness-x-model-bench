---
id: "design-phase3-graders"
title: "Design: full graders — per-cell grader input, dispatch by task graders, catalog 0.4 versioning, and the byte-identity gate (phase 3, row 16)"
type: design
status: draft
owner: "@timianmalloo"
phase: "Phase 3 · grading and judges (wave 3: row 16, W3-GRADE-D)"
tags: [benchmark, grading, metrics, catalog, versioning, na, determinism, mutation, drift, clarification]
links:
  - { to: spec-harness-bench, rel: implements }
  - { to: arch-harness-bench, rel: implements }
  - { to: adr-0006-results-data-model, rel: depends-on }
  - { to: adr-0008-telemetry, rel: depends-on }
  - { to: adr-0009-model-gateway, rel: relates-to }
  - { to: adr-0010-untrusted-cell-output, rel: depends-on }
  - { to: adr-0013-native-cells, rel: depends-on }
  - { to: design-phase1-walking-skeleton, rel: refines }
  - { to: design-phase2-scripted-user, rel: depends-on }
  - { to: note-spike-s04-scripted-user, rel: relates-to }
  - { to: rulings-register, rel: depends-on }
  - { to: coordination-finish-harness-bench, rel: relates-to }
  - { to: proposal-cross-harness-benchmarking, rel: refines }
review-by: "2027-03-25"
summary: >-
  Row 16: every metric the ready tasks A1, C1, D1 and E6 name through their `graders:` lists gets a definition, an
  oracle rung (US-25), its NA reasons (US-27), an additivity class and a fixture with a stated expected value, cut
  from runs/row15-d1-1, runs/a1-capture-1 or the C1/E6 reference solutions. A frozen per-cell `CellInput` replaces
  `grade(run_dir, task_dir)`. A registry dispatch by the task's `graders`, with a completeness check before
  `grading.completed`, replaces the fixed `METRICS` tuple. Catalog `0.4.dev` is a probe version (R-59). `catalog_hash`
  and tool versions ride on `grading.started`. The US-4 control fails on a score change or a catalog-hash change
  without a version bump. The four gate tasks are frozen. The byte-identity gate compares `views.export` bytes of two
  asserted passes, never ledger bytes. Revision 2 clears the Test Architect's and the D&P Architect's vetoes.
---

# Design: full graders (row 16)

**Status:** draft, revision 3, after the three-lens gate and its re-review (see [Gate record](#gate-record)). **Author:** W3-GRADE-D (Claude Opus 5.5). **Grounded at:** `87606c6`.

Confidence labels:
- **Verified:** observed in this session (a file opened, a command run).
- **Inferred:** reasoned, not observed.
- **Flagged:** open, with the reason.

File:line citations are against `87606c6`.

## Responsibility

One responsibility: **turn one archived cell into one versioned set of metric values.** Each value is a number, or NA with a reason (US-27). It is a pure function of three things: the archive, the frozen task version and the catalog version (US-26).

In scope:
- the per-cell grader input and the dispatch;
- each metric's definition, rung, NA reasons, class and fixture;
- catalog versioning (US-4, R-59);
- the tasks freeze;
- the byte-identity gate;
- the slice plan.

Not in scope:
- the judge gateway, cache, blinding and calibration (W3-GW-D, `docs/design/phase3-gateway-judges.md`);
- the egress gate (W3-EGRESS);
- statistics and composites (row 19);
- implementation code.

## Grounding (the facts this design stands on)

| # | Fact | Evidence | Label |
| --- | --- | --- | --- |
| G1 | The runner grades a fixed tuple, `METRICS = ("pass_at_1", "partial_credit", "cost_usd")`. The correctness and cost calls are inline in `_grade_cell`. | `grade/runner.py:34`, `:142-174` | Verified |
| G2 | Every other grader is a stub `grade(run_dir, task_dir) -> Result` that raises `not_built`. `Score.value` is a `float`, but the ledger bans floats (`runner.py:16`). | `grade/judge.py:13`, `grade/__init__.py:16-20` | Verified |
| G3 | `grading.started` records `catalog_version` as a bare string, plus `grader_build` and `extraction_id`. `grader_build()` hashes only `grade/*.py`. | `runner.py:50-54`, `:111-112` | Verified |
| G4 | `grading_id` is `grade-<utc>-<rand>`, so ledger bytes differ on every pass. | `runner.py:80` | Verified |
| G5 | `views.export` leaves out pass identity, evidence paths and weights. `_current_pass` takes the latest completed pass, optionally for one `catalog_version`. `rows` reads every completed pass, and `_refuse_duplicates` raises HB-LED-003 for the whole run on a duplicate key. | `views.py:544-556`, `:174-182`, `:82-90`, `:158-171` | Verified |
| G6 | The 0.3 export digests at `87606c6`, each measured twice: `row15-d1-1` `8b35fdf9…e1d2` (7917 bytes, pass `grade-20260925T063930-dec9eb`); `a1-capture-1` `30126414…2022` (3980 bytes, pass `grade-20260925T075419-1dc414`). | `views.load(run, "0.3")` + `export`, run in this session | Verified |
| G7 | `task_version_hash` hashes every file under the task folder. Current values: A1 `0127daa0…7627`, C1 `d9d72e41…7a2b`, D1 `b2b3170e…e519`, E6 `b3fd1ea1…352f`. A1 and D1 equal the versions frozen in their archived plans. | `plan.py:91-97`; computed in this session | Verified |
| G8 | `tests/test_grade.py:328` asserts `catalog_version == "0.3"` against a copy of the real `bench/metrics.yaml` (`tests/archived_runs.py:44`). No test fails on a score change without a version bump. | files read | Verified |
| G9 | An archived working copy is a git repo. The root commit is `"<task> base (<ver12>)"`. With the pack on, a first-parent child `"ai-forward pack revision <n>"` adds about 430 pack files, **including a root `.editorconfig`** (absent in pack-off trees). The agent's changes are uncommitted files or later commits. Untracked `bin/` and `obj/` hold the agent's build output. | `workspace.py:89`, `:145`; `git log`, `git status`, `ls-tree` on row15 cells | Verified |
| G10 | Tool-call rows carry `name`, `tool_class`, `ok`, `outcome_code`, `start` and `end`. They carry **no arguments or command text**. Every Codex row has `ok = null`, class `shell` and name `exec`. | `telemetry/__init__.py:47-55`; row15 and a1 `tool_calls` | Verified |
| G11 | A Copilot `model_calls` row summarises several requests and has no per-call `start`. `model_call_rows` has no `grading_id` field, and its `principal` is the cell id. | `telemetry/__init__.py:25-33`; `normalize.py:129-133` | Verified |
| G12 | A1 scripted-user logs: cc-opus asked 1 question, and T0 matched none (`rung: none`). Codex and Copilot each show `tool_listed: true, calls: 0`. | the three `scripted-user.jsonl` files | Verified |
| G13 | C1's hidden tests already check `docs/architecture.md` and its six sections (`HiddenArchitecture`). | `tasks/C1/tests/test_c1_hidden.py:144-150` | Verified |
| G14 | D1 base `src/**.cs` with a namespace: 228 files. 228 of 228 use a file-scoped namespace. 214 of 228 (93.9 %) have a namespace equal to the path. Several types per file is normal. | a scan run in this session; sampled Projections files | Verified |
| G15 | The plan's task record has no `graders` field. `validate_task` checks that grader names exist, not that they are unique. | `row15-d1-1/plan.json`; `config.py:228-230` | Verified |
| G16 | D1 `pass_at_1` = 1,1,1,1,1,0. The 0 is cc-opus pack-on `35af195cfe821dca`, whose working copy holds **no** added Projections or census test file (the agent worked in `ws-evidence-census/`, outside `ws/`). The three A1 cells have `pass_at_1` = 1. Every `cost_usd` is NA. | scores segments; archive listing | Verified |
| G17 | The default test ring is `-m 'not credentials'`. No `slow` marker is registered, and CI has no dotnet setup. | `pyproject.toml` addopts; Test Architect's read of `ci.yml:25` | Verified (addopts); the CI line was Verified by the reviewer |

## Data model (settled first)

**Bounded context:** grading. Ubiquitous language: *pass*, *cell input*, *grader*, *metric*, *applicable set*, *score*, *NA reason*, *catalog version*, *probe pass*, *frozen task*.

**Aggregates.** ADR-0006's aggregates are unchanged, and this design adds none.

| Aggregate (root) | The one invariant it protects | How it is enforced now |
| --- | --- | --- |
| Grading pass (`grading_id`) | **GradedOncePerPass:** in a completed pass, the written (cell, metric) set equals the applicable set exactly: one row each, none missing, none extra. | **At the store.** Before it appends `grading.completed`, the runner compares the written key set with the applicable set. On any mismatch it raises HB-GRD-004, and the pass is never completed, so views skip it (G5). This is new. Today, nothing enforces the "no row missing" half. |
| Catalog version (a content-addressed dimension) | **One version label, one content:** a non-`.dev` `version` has exactly one `catalog_hash`. | The US-4 control (§Catalog-version rule 4) fails on a hash change or a score change without a bump. |
| Task version (a content-addressed dimension) | **A frozen task's bytes do not change** during the freeze window. | The freeze record and the `bench validate` check (§Tasks freeze). |

**Applicable set** of a cell in one pass:
1. Start from the de-duplicated grader list: the plan's frozen `graders` (seam S-1), else `task.yaml`'s.
2. Take every catalog metric with `kind: score` whose `grader` is in that list.
3. **Fallback.** The plan froze no `graders` (G15) and the task is not current. Then the changed `task.yaml` cannot be trusted. The applicable set becomes:
   - every `kind: score` metric of every catalog grader except `cost` and `process`, registered or not (D&P N5), each NA `task changed since the plan (version hash mismatch)`;
   - plus `cost` and `process`, graded normally.

   The fallback is disclosed by that NA reason.

**Grain statements.** Only the first two are persisted by the pass.

| Fact / record | One row is exactly one … | Change |
| --- | --- | --- |
| `scores` (ADR-0006) | value of one metric for one cell in one grading pass; key `(run_id, grading_id, cell_id, metric_id)` | Columns unchanged. The applicable set replaces `METRICS`. |
| `events` · `grading.started` | start of one grading pass | Adds `catalog_hash` (str) and `tool_versions` ({tool key: measured version string, or `"not recorded"`}). Both are attributes of an immutable pass entity. |
| `bench/task-freeze.yaml` (new, Leader-owned) | frozen task `(task_id, version_hash)` | New. Read by `validate_repo`. **Lifecycle:** it lives through wave 3 only and is deleted at the close. |
| `bench/catalog-freeze.yaml` (new, Leader-owned) | frozen catalog version: `(version, catalog_hash, {fixture: golden export sha256})` | New. Read by the US-4 test. **Lifecycle:** permanent, and append-only per version (D&P N1, N3). |
| `tests/fixtures/catalog/<version>/<fixture>.export` | canonical export of one fixture run under one catalog version | Golden data for US-4. Its digest is pinned in `catalog-freeze.yaml`. There is no `meta.json`. |

**Additivity.** Every class is stated **across cells within one grading pass and one catalog version**.
- **No metric is additive across `grading_id` or `catalog_version`.** Two passes are re-measurements of the same cell, so summing them counts twice.
- Row 19's composites take the current pass only. A row-19 test must reject multi-pass input; this is recorded as an obligation on row 19.
- At the fact level, the `scores.value` column is non-additive (ADR-0006). The class tells a reader which cross-cell aggregation is legal:
  - **additive:** counts and 0/1 indicators. The sum is meaningful and the mean is a rate.
  - **non-additive:** ratios and rubric scores. Use the mean or median, never the sum.
- Within those axes no metric is semi-additive: none is a point-in-time level.

**History rules.**
- A catalog version is Type-2 by identity: a new version, never an overwrite.
- A score row is never rewritten.
- A `.dev` pass stays in the ledger and is never current.
- `tool_versions` is recorded per pass, so a tool bump is visible, and the US-4 control fails if it moved a score without a bump.

**Derive, don't store (DM7): one definition per quantity.**
- `kind: derived` metrics never become score rows:
  - `pass_at_k`, `pass_hat_k`, `cost_of_pass`, `tokens_per_solved` and `coordinator_overhead` (their grain is above the cell);
  - `tokens_by_type`, `wall_clock_split` and **`turns_and_tool_calls`**, which are already view measures: `views.py:433-446`. The model-call count is `calls_per_cell` (`views.py:249-253`, Σ `requests`), and the tool-call count is the view's non-meta `tool_calls` count. This is the single definition, fixed now.
- `cost_usd` remains a score row, as the spec's named rebuildable cache (`:255`).
- The process metrics are score rows that act as **rebuildable caches** of `tool_calls`, `model_calls` and `events`. They stay score rows, not view measures, so that their definitions sit under the catalog version (US-4). A view-derived definition would move history whenever the views code changed.
- The rebuild test reads the rows **back from the sealed ledger segments**, under the score row's `extraction_id`, from whichever completed pass wrote them. Pass B writes none, because extractions are written only once (`runner.py:135`). The test re-derives the values and compares them with the stored score.
- Two quantities that could have been defined twice are separated:
  - `test_quality` versus `mutation_score`;
  - `spec_coverage` versus `partial_credit`.

  Each pair is resolved by an NA reason in the table. `build_and_suite_clean` (does the workspace build) is a different quantity from `pass_at_1` (do the hidden tests pass).

**Writers and compute readers (DM15):**

| Field | Writer | Compute reader |
| --- | --- | --- |
| `grading.started.catalog_hash` | `runner` (CORE s2) | the US-4 test; `tools/check_regrade.py` (gate criterion 3); `RunView.header["catalog_hash"]` → the report header |
| `grading.started.tool_versions` | `runner` (CORE s2) | `RunView.header["tool_versions"]` → the report header; the Leader's run record |
| `bench/task-freeze.yaml` `tasks` | Leader | `config.validate_repo` |
| `bench/catalog-freeze.yaml` `versions` | Leader, at each freeze | `tests/test_catalog_version.py` |

`RunView.header` is not part of `export` (`views.py:556`), so its new keys do not move the 0.3 bytes.

**Migration and rollback.** The migration is additive only:
- New event attributes read as "not recorded" on older passes.
- New catalog fields.
- No backfill.

**Rollback is a `git revert` of the code and the catalog together, never the catalog alone.** The reason: `kind` is required in 0.4's `validate_metrics`, and new code grading under a `0.3` label would write a `0.3`-labelled pass with 0.4 semantics. That would move the 0.3 export.

After a revert:
1. Re-measure the 0.3 digests.
2. Compare them with the committed baseline (L-1).
3. The 0.4 passes stay in the ledger. Views select by version.

**Tested:** `test_catalog_version.py::test_0_3_code_and_catalog_regrade_the_0_3_fixture_to_its_golden`.

## Delivery phasing

- **Slice served:** row 16, which feeds wave 3's gate "the smoke archive re-grades byte-identically" (plan v5).
- **Real:** the archive, the ledger, and the dotnet and python oracles.
- **Mocked in CORE and GR-* tests:** judges. `GRADERS["judge"]` is a registered fake that returns fixed `Score`s. It is paired with GW-I's contract tests (D7). The registry entry is the only seam GW-I replaces.

## Contracts

### Exposed: the per-cell grader input (replaces `grade(run_dir, task_dir)`)

```python
# grade/__init__.py  (W3-GRADE-CORE slice 1)
@dataclass(frozen=True)
class Score:
    value: int | Decimal | None      # None <=> NA; a Decimal is written at the catalog scale (no floats, ADR-0006)
    reason: str | None               # set iff value is None (US-27); from the closed vocabulary below
    evidence: str = ""               # a path relative to run_dir, optionally ":line" or "@offset"
    # __post_init__ raises ValueError unless (value is None) == (reason is not None)

@dataclass(frozen=True)
class CellInput:                     # everything a grader may read; nothing else
    run_dir: Path                    # evidence paths are relative to it
    root: Path                       # bench root: bench/metrics.yaml, bench/rubrics/
    plan: Mapping                    # the confirmed plan (read-only); the grading step timeout is plan["parameters"]
    cell: Mapping                    # the plan's cell record
    task: Mapping                    # task.yaml as loaded (a reads_task grader only runs when the task is current)
    task_dir: Path
    archive: Path                    # run_dir/archive/<cid>/attempt-<n>  (READ-ONLY)
    out_dir: Path                    # run_dir/grading/<gid>/<cid>/<grader>/: the only place a grader writes
    events: tuple[Mapping, ...]      # this cell's engine events
    record_reason: str | None        # why the native record was unreadable (R-15), or None
    model_calls: tuple[Mapping, ...] # this cell's rows under the pass's extraction_id (unstamped)
    tool_calls: tuple[Mapping, ...]
    turn_usage: tuple[TurnUsage, ...]
    metrics: Mapping[str, Mapping]   # the catalog entries of this grader's applicable metrics
    allow_model_calls: bool          # R-58 DR-2: False in the in-run pass

GraderFn = Callable[[CellInput], Mapping[str, Score]]

def grading_copy(inp: CellInput, tag: str) -> ContextManager[Path]: ...
# A free function, lifted from correctness.py:117-140. It makes a disposable copy of archive/ws under
# out_dir/<tag>, without .git and without build output (bin/, obj/, TestResults/, __pycache__/), copied
# with symlinks=True, and removes it on exit.
```

**Pattern:** Parameter Object plus a registry-backed Strategy (GoF Strategy in its Pluggable-Selector form).
- `GRADERS: dict[str, Grader]` in `runner.py` maps a `graders:` name to `Grader(fn, reads_task: bool)`.
- A frozen input replaces `(run_dir, task_dir)` because the runner already reads the plan, events and extraction for each cell (`runner.py:95-104`, `:129-140`). Handing the rows over gives one reader per fact.

### Exposed: the dispatch (replaces `METRICS`, `runner.py:34`)

For each archived cell, in `cell_id` order:
1. Build the `CellInput` and compute the applicable set (§Data model).
2. For each grader `g` in the **de-duplicated** list, in catalog order, let `wanted` be `g`'s applicable metric ids.
3. Pick the rows to write:
   - `g` has `reads_task` and the task is not current: every `m` in `wanted` is NA `task changed since the plan (version hash mismatch)`.
   - `g` is not in `GRADERS`: every `m` is NA `not built`.
   - Otherwise, `out = fn(inp)`:
     - A missing `m` is NA `not built`.
     - Any other exception makes every `m` NA `HB-GRD-003 grader <g> failed: <ExceptionType>`. The traceback goes to `out_dir/error.log`, which is the evidence.
4. Write exactly one row per `m in sorted(wanted)`. Decimals are written at `scale` (`runner.py:176-178`).
5. **Completeness check (GradedOncePerPass, D&P fix 2).** After the last cell and before `grading.completed`, count the written rows per (cell, metric) key. Every count must be exactly 1, and the key set must equal the applicable set; a set comparison alone would hide a duplicate (D&P N2). Also check that no grader returned a key outside `wanted`. Any difference raises HB-GRD-004, and the pass is never completed.

   Why the check sits here: a duplicate row in a completed pass would make the whole run unreadable forever (HB-LED-003, G5). `validate_task` also rejects duplicate grader names (seam V-3).

**Applicability versus NA.** A metric whose grader is not in the task's list has no row: it is **not applicable**. A metric that applies but cannot be measured is **NA with a reason** (US-27).

`reads_task`:
- True: correctness, mutation, rigor, drift, architecture, clarify, judge.
- False: cost and process.

### Consumed

| Contract | Source | Status |
| --- | --- | --- |
| `task_version_hash` and its recipe | `plan.py:91-97` | Verified. It becomes `tree_hash` (seam S-2). |
| `normalize.model_call_rows` / `tool_call_rows`, `record_unreadable` | `telemetry/normalize.py:129-139`, `runner.py:148` | Verified |
| `views._current_pass`, `rows`, `export` | `views.py:82-90`, `:174-182`, `:544-556` | Verified |
| scripted-user log `bench-scripted-user-log/1` | phase-2 design §8; the three archived logs | Verified |
| dotnet build summary and per-test TRX `UnitTestResult` | the TRX totals parse is Verified (`correctness.py:91-107`) | **Flagged:** GR-CODE c1 spike |
| Stryker.NET CLI and JSON report (`mutation-testing-elements`) | not in the repo | **Flagged:** GR-CODE c6 spike (Spike Protocol) before any dependency |
| judge grader contract; the gateway's per-call record; `verdict_uses` grain and key | W3-GW-D | seam S-5: **CORE writes no `verdict_uses` until GW-D's ADR fixes its grain, key, placement and `heads` entry** |

## Catalog 0.4 (`bench/metrics.yaml`)

- **Version.** `version: "0.4.dev"` through wave 3. The Leader sets `"0.4"` at the freeze (R-59 c3).
- **New fields per metric**, validated by `config.validate_metrics`:
  - `kind: score | derived` (required);
  - `rubrics: {<task_id>: <file under bench/rubrics/>}`, on judged metrics only. A task that is not a key gets NA `no rubric for this task` (R-59 c2).
  - There is no `scenarios` field (Simplifier 1). `behavioural_equivalence` is NA on every task, with a reason that names why; see the table.
  - **Recorded deviation (D&P N4):** on non-D tasks this is an NA row where "not applicable" would be more exact. The reason `not a D-task` keeps the two cases apart in the report. They are not counted in the NA-by-design disclosure.
- **New metrics**, all `score` with weight 0:
  - `asked_unmatched` (clarify; R-52 c2);
  - `scope_creep_files` (drift). US-30 counts files **and** lines, `spec:453`.
- **C1's rubric.** The judged metric that C1's rubric scores is **`adr_quality`** (R-59 c2). In the proposal, `:273`, ADR quality is "options considered, trade-offs, reversibility". C1's rubric items 1, 4 and 5 are that, for C1's one architecture decision. W3-GW-D confirms it (S-5).
- **The rubric file.** `bench/rubrics/adr_quality.md` is **byte-identical** to `tasks/C1/oracle/rubric.md` (R-59 DR-5). The catalog entry is `rubrics: {C1: adr_quality.md}`.
  - `simplify:` one rubric file per metric. Ceiling: a second task that scores `adr_quality`. Upgrade trigger: that task.
- **`catalog_hash`** uses `task_version_hash`'s recipe over `bench/metrics.yaml` and every file under `bench/rubrics/`:
  - the path is relative to `bench/`;
  - each entry is the path, NUL, the CRLF-normalised bytes, NUL;
  - entries are in sorted path order.

  It is computed by `plan.tree_hash` (S-2), the single recipe.

## Metric table

**Rungs** (US-25; `metrics.yaml:7-8`):
- **proof** (proof or model check), **trace** (trace conformance), **tests**;
- **analysis:** a deterministic measurement of the archive, such as a diff, build output or a log;
- **telemetry:** a deterministic measurement of the extracted rows;
- **judge.**

No wave-3 metric has a proof or trace rung, because G-tasks and `protocol_conformance` are out of scope. Every rung named here is the strongest available for the task version.

**Expected values** are exact where the archived rows or files decide them (computed in this session, **Verified**). A value decided by a tool run (dotnet, Stryker) is a **characterization value**. The slice records it the first time, and it is accepted only if the same metric's seeded fixtures, which have exact expected values, pass in the same run. It is never "whatever came out".

Cell ids: D1 cells are from `runs/row15-d1-1`, A1 cells from `runs/a1-capture-1`. In the D1 labels, cp = copilot-sol, cx = codex-sol and cc = cc-opus; "on" and "off" are the pack setting.

**Shared NA reasons** (every `reads_task` grader):
- `task changed since the plan (version hash mismatch)`
- `no working copy in the archive`
- `pre-turn commit not found in the working copy`
- `HB-GRD-002 grading step timeout after <n> s`
- `HB-GRD-003 grader <g> failed: <ExceptionType>`
- `not built`

### Correctness: grader `correctness`, owned by W3-GR-CODE (A1, C1, D1, E6)

**`pass_at_1`**
- Kind and class: score · additive (0/1).
- Definition: 1 iff the hidden-test step exits 0 and every hidden test passes (built, `correctness.py:164`).
  - **0.4 change (DR-G4), decided by cause:** after a **successful restore**, any compiler error scores **0**, wherever it sits, including in a file the cell did not touch.
  - Failures before compilation stay NA: restore, a missing SDK, `dotnet --version` failing, or a timeout.
- Rung: tests.
- NA reasons (besides the shared ones): `oracle runner <kind> not built`; `infrastructure failure before build: <restore|sdk>`; `no hidden test ran`.
- Fixtures:
  - D1 cells: `4a62…` 1, `3ff0…` 1, `35af…` **0**, `caa8…` 1, `2535…` 1, `c3d4…` 1 (G16).
  - A1: all three cells 1.
  - C1 and E6: the reference scores 1 and the base scores 0 (`oracle/evidence.md`).
  - **Seeded:** D1 base plus an added file with a syntax error → 0. D1 reference with one member deleted that an unchanged vendored file uses → 0. An empty `NUGET_PACKAGES` → NA `infrastructure failure before build: restore`.

**`partial_credit`**
- Kind and class: score · non-additive (fraction, scale 4).
- Definition: hidden tests passed ÷ hidden tests run. A compile error gives `0.0000`.
- Rung: tests.
- NA reasons: as `pass_at_1`.
- Fixtures: as `pass_at_1`. `35af…` = `0.0000` (5 of 5 failed).

**`build_and_suite_clean`**
- Kind and class: score · additive (0/1).
- Definition: 1 iff the cell's working copy builds on its own, and 0 otherwise.
  - dotnet: `dotnet build` of the workspace, including its own test projects, exits 0.
  - python: `python -m compileall -q` over the copy exits 0.
- Rung: analysis.
- NA reasons: `infrastructure failure before build: <restore|sdk>`.
- Fixtures:
  - Characterization: the 6 D1 cells.
  - Exact: the C1 reference = 1.
  - **Seeded:** a `.py` with a syntax error → 0; a broken `ProjectReference` in a D1 test project → 0.

**`regression_count`**
- Kind and class: score · additive (count).
- Definition: the workspace public tests, by fully qualified name, that pass on the **pre-turn tree** and fail, error or are missing on the cell's tree. The base run is memoised within one pass per task version.
- Rung: tests.
- NA reasons: `task has no public tests` (A1, C1, E6; Verified: none of their workspaces has a test project); `workspace does not build`.
- Fixtures:
  - Characterization: the D1 cells.
  - **Seeded:** D1 base with one vendored `AiDe.Core.Tests` assertion inverted → exactly 1.

**`behavioural_equivalence`**
- Kind and class: score · non-additive.
- Definition: differential tests against the reference.
- Rung: none available.
- NA reasons: `not a D-task` on A1, C1 and E6 (a recorded deviation, D&P N4); `no differential oracle in this task version` on D1. `simplify:` there is no scenario filter. Upgrade trigger: the first D-task with a differential oracle.
- Fixtures: every cell → that NA.

**`pass_at_k`, `pass_hat_k`**
- Kind: **derived**, at the grain task version × combo × pack.
- Definition: row 19 derives them from `pass_at_1` (US-28 c2).
- They have no score row.

### Mutation: grader `mutation`, owned by W3-GR-CODE (D1)

**`mutation_score`**
- Kind and class: score · non-additive (scale 4).
- Definition: pinned Stryker.NET, in a grading copy. Its version is on `grading.started`, and its timeout settings are pinned in the tool config (F8).
  - Mutate the non-test `.cs` files the cell **added or changed** relative to the pre-turn tree.
  - Test with the test projects the cell added or changed.
  - Score = (killed + timeout) ÷ (killed + timeout + survived + no coverage).
  - `simplify:` pre-existing tests in a changed test project also count. Ceiling: a task that edits vendored tests.
- Rung: tests.
- NA reasons: `no tests written` (US-29 c2); `no non-test source changed`; `no mutants generated`; `mutation tool not available`; `mutation run failed: <exit code>`.
- Fixtures:
  - `35af…` → `no tests written` (exact: its working copy has no census test file, G16).
  - The other 5 D1 cells each added one Projections file and a test file: characterization values, graded **twice** in the slow ring, and the two must be equal.
  - **Seeded:** D1 reference plus a test that never calls `Compute` → `0.0000` exact (every mutant NoCoverage). The seed test sits in a **new** test project, so that no vendored test can cover the reference file (TA re-review 5).

### Rigor: grader `rigor`, owned by W3-GR-CODE (D1)

**`static_analysis_delta`**
- Kind and class: score · additive (a difference of counts; may be negative).
- Definition: the distinct (file, line, code) warnings from `dotnet build` of the cell's tree, minus the same on the pre-turn tree.
  - The pack's `.editorconfig` sits on both sides of a pack-on cell (G9), so the delta stays within one treatment.
- Rung: analysis.
- NA reasons: `workspace does not build`; `pre-turn tree does not build`.
- Fixtures:
  - Characterization: the 6 D1 cells.
  - **Seeded:** an added unused local (CS0168) → exactly +1.

**`verification_before_done`**
- Kind and class: score · additive.
- Definition: the agent ran a build or test before its final message.
- NA reason: `test runs not identifiable in the tool record (no command text extracted)` (DR-G2).
- Fixtures: every cell → that NA.

**`test_quality`**
- Kind and class: score · non-additive.
- Its mechanical rung is `mutation_score`, already a metric of its own. Its judge rung needs a rubric.
- NA reason: `mechanical rung is mutation_score (not counted twice); no rubric for this task`.
- Fixtures: every D1 cell → that NA.

**`maintainability`**
- Kind and class: score · non-additive.
- Definition: complexity, duplication and size of the diff.
- NA reason: `no maintainability tool pinned in this catalog version`.
- Fixtures: every D1 cell → that NA.

**`style_conformance`**
- Kind and class: score · non-additive.
- Definition: analyzer style violations on changed files.
- NA reason: `no task-defined style rules (a root .editorconfig exists only in pack-on trees: a treatment)`; `no rubric for this task`.
  - The reason: pack-on trees get the pack's `.editorconfig` (G9) and pack-off trees have none. Scoring against it would score the pack itself.
- Fixtures: every D1 cell → that NA.

### Drift: grader `drift`, owned by W3-GR-CODE (D1)

**`scope_creep`**
- Kind and class: score · additive (lines).
- Definition: lines added plus deleted (CRLF-normalised, `difflib`) in files outside `blast_radius`, cell tree against the pre-turn tree. Build output is excluded.
- Rung: analysis.
- NA reasons: shared only.
- Fixtures:
  - The 6 D1 cells → 0 exactly (Verified with `git ls-files --others/--modified` and `diff-tree` under `GIT_OPTIONAL_LOCKS=0`):
    - four cells added exactly one Projections file plus `tests/AiDe.Core.Tests/EvidenceCensusProjectionTests.cs`, uncommitted;
    - cx on `3ff0…` **committed** the same two files as its own third commit, `3075d92`, after the pack commit. It is the real fixture for "changes after the pre-turn commit count";
    - cc on `35af…` changed nothing inside `ws/`.
  - **Seeded:** a 3-line edit in `src/AiDe.Mcp/…` → exactly 3.
  - **Seeded, pack-on:** a pack-commit stand-in whose files lie **outside** `blast_radius` → 0. The mutant "use the base commit as the base" then scores more than 0 and is killed.

**`scope_creep_files`**
- Kind and class: score · additive (files) · weight 0.
- Definition: the files counted by `scope_creep`.
- Rung: analysis.
- Fixtures: D1 cells 0; the seeded edit 1; the pack-on stand-in 0.

**`convention_drift`**
- Kind and class: score · non-additive (per 100 changed lines, scale 2).
- Definition: violations of the **hardcoded D1 rule set** in added or changed `.cs` lines, per 100 changed lines. The rule set was measured in this session (G14):
  - R1, a file-scoped `namespace …;`, holds in 228/228 files and is **kept**;
  - R2, namespace equals the path, holds in 214/228 = 93.9 %, below 95 %, and is **dropped**.
- The rule table sits in `drift.py`, keyed by task id. `simplify:` ceiling D1; upgrade trigger: a second task.
- Rung: analysis.
- NA reasons: `no lines changed`; `no convention rules for this task`.
- Fixtures:
  - D1 cells: the Projections files of the 5 cells that added one are file-scoped, so those files contribute 0 violations. Test files are characterized at c3.
  - `35af…` → `no lines changed` (exact: nothing in `ws/` changed).
  - **Seeded:** a block-scoped namespace in a 10-line file → 1 violation per 10 lines = `10.00`.

**`spec_coverage`**
- Kind and class: score · non-additive.
- NA reason: `hidden-test coverage is partial_credit (not counted twice); no rubric for this task`.
- Fixtures: D1 → that NA.

**`constraint_violations`**
- Kind and class: score · additive.
- NA reason: `no constraint checklist in this task version`.
- Fixtures: D1 → that NA.

**`instruction_reread_rate`**
- Kind and class: score · non-additive · weight 0.
- NA reason: `read targets not in the tool record (no arguments extracted)` (DR-G2).
- Fixtures: D1 → that NA.

### Architecture: grader `architecture`, owned by W3-GR-CODE (C1, D1)

**`architecture_conformance`**
- Kind and class: score · non-additive (rules passed ÷ rules, scale 4).
- Definition: dependency direction, meaning the component depends only on the platform and its own layer.
  - **C1:** every `.py` the cell added or changed imports only `sys.stdlib_module_names` or modules in the working copy.
  - **D1:** every `using` in a `.cs` file added or changed under `src/AiDe.Core/Projections/` names `System`, `System.*`, `AiDe.Core` or `AiDe.Core.*`.
  - The rule table sits in `architecture.py`, keyed by task id, and is hashed by `grader_build`. `simplify:` ceiling C1 and D1; upgrade trigger: a third task or a new task version, when the rules move to `tasks/<id>/oracle/architecture.yaml`.
  - Not re-checked here, because they are measured elsewhere: the C1 section checks (hidden tests, G13) and the D1 layer boundary (`scope_creep`).
- Rung: analysis.
- NA reasons: `no architecture rules for this task`; `no source file changed`.
- Fixtures, all exact:
  - The C1 reference (no imports) = `1.0000`. C1 reference plus `import numpy` = `0.0000`.
  - D1 cells `4a62…`, `3ff0…`, `caa8…`, `2535…`, `c3d4…`: each added one Projections file whose only `using` is `AiDe.Core.Facts` → `1.0000`.
  - `35af…` → `no source file changed`.
  - D1 reference plus `using Newtonsoft.Json;` → `0.0000`.

### Clarification: grader `clarify`, delegated to **W3-GR-CLAR** (A1); the contract level is fixed here

The grader reads the archived `scripted-user.jsonl`, which is the store (design §7.3). It reads the **stored decisions and never re-matches** (T-39-3b).

Common NA reasons:
- `tool not reached`
- `no scripted-user log`
- `scripted-user log unreadable: <torn tail|invalid row>`
- `clarification set changed since the plan`
- `matcher version differs from the plan's`

**`key_question_recall`**
- Kind and class: score · non-additive.
- Definition: **distinct** annotated ids matched by any `call` row's stored decision ÷ annotated clarifications in the plan-frozen set.
- Rung: analysis.
- NA reasons: the common ones.
- Fixtures: cc-opus `30f8…` 0 (G12); codex `4267…` 0; copilot `600f…` 0.

**`key_question_precision`**
- Kind and class: score · non-additive.
- Definition: matched `call` rows ÷ `call` rows.
- Rung: analysis.
- NA reasons: the common ones, plus `no question asked` (0/0).
- Fixtures: cc-opus 0; codex and copilot → `no question asked`.

**`ask_vs_assume`**
- Kind and class: score · non-additive.
- Definition: min(calls, annotated) ÷ annotated. This is the proposal's ratio (`:268`), capped at 1. **"No question asked" is an assume and scores 0.**
- Rung: analysis.
- NA reasons: the common ones.
- Fixtures: cc-opus 1; codex 0; copilot 0.

**`asked_unmatched`** (new)
- Kind and class: score · additive · weight 0.
- Definition: `call` rows whose decision matched nothing (R-52 c2).
- Rung: analysis.
- NA reasons: the common ones.
- Fixtures: cc-opus 1; codex 0; copilot 0.

**Seeded logs, which exercise the matched branch (TA 2, 7):**
- (a) One `call` row with stored decision `goal-maximum` → recall 1, precision 1, `ask_vs_assume` 1, `asked_unmatched` 0.
- (b) Two calls that both match `goal-maximum` → recall **1** (never 2), precision 1, `ask_vs_assume` 1 (the cap), `asked_unmatched` 0.
- (c) The `end` row with `tool_listed: false` → every metric NA `tool not reached`.
- (d) A torn last line → NA `scripted-user log unreadable: torn tail`.

Mutants that must be killed: "constant 0"; "count call rows, not distinct ids"; "drop the cap"; "no question asked → NA"; "re-match instead of reading the stored decision".

The report derives the `low-confidence matcher` label (R-52 c1) from the log's `matcher_version`; it is not stored. A later matcher version, GW-I's model rung, is a new catalog version.

### Process: grader `process`, delegated to **W3-GR-PROC** (A1, C1, D1, E6); the contract level is fixed here

Inputs: `inp.tool_calls` sorted by `native_ordinal`, `inp.model_calls`, `inp.events` and `cell.budget_seconds`. Rows of `tool_class == "meta"` are excluded everywhere (R-54 c3).

Exact values below were computed from the archived rows in this session (Verified).

**`tool_error_rate`**
- Kind and class: score · non-additive (scale 4).
- Definition: calls with `ok == 0` ÷ calls.
- Rung: telemetry.
- NA reasons: `no tool call`; `per-call outcome missing on <k> of <n> calls` (any null `ok`; never a partial ratio).
- Fixtures:
  - D1: cc on `35af…` 1/23 = `0.0435`; cc off `c3d4…` 1/12 = `0.0833`; cp on `4a62…` 0/41 = `0.0000`; cp off `caa8…` 0/25 = `0.0000`; the 2 Codex cells → `per-call outcome missing on 18 of 18 calls` and `… 8 of 8 …`.
  - A1: cc `30f8…` 0/3 = `0.0000` (1 meta row excluded); cp `600f…` 0/6 = `0.0000`; cx → NA.
  - **Seeded:** a failed meta row → rate unchanged.

**`stuck_loops`**
- Kind and class: score · additive (count).
- Definition: maximal runs of **≥ 3** consecutive calls with the same `name` and `ok == 0`.
  - `simplify:` the rows carry no arguments (G10). Ceiling: repeated successful calls. Upgrade trigger: DR-G2's extraction.
- Rung: telemetry.
- NA reasons: `no tool call`; `per-call outcome missing …`.
- Fixtures: every cell with outcomes → 0. **Seeded:** a 2-run → 0; a 3-run → 1; a 4-run → 1; two separate 3-runs → 2.

**`recovery_rate`**
- Kind and class: score · non-additive.
- Definition: failed calls followed later by an `ok == 1` call of the same `name` ÷ failed calls.
- Rung: telemetry.
- NA reasons: `no failed tool call`; `per-call outcome missing …`.
- Fixtures: D1 cc on (fail `Bash` #106) = `1.0000`; cc off (fail `Bash` #63) = `1.0000`; Copilot cells and A1 cc → `no failed tool call`. **Seeded:** a failure that is never followed by a success → `0.0000`.

**`planning_ratio`**
- Kind and class: score · non-additive · weight 0.
- Definition: Σ `requests` of model calls that start before the first `edit`-class call ÷ Σ `requests`.
- Rung: telemetry.
- NA reasons: `no edit-class tool call (edits through the shell are not classed)`; `model calls not itemised in time (summary rows)`.
- Fixtures: D1 cc on 7/20 = `0.3500`; cc off 4/12 = `0.3333`; A1 cc 3/5 = `0.6000`; Codex → the first NA; Copilot → the second NA (G11).

**`completion_without_intervention`**
- Kind and class: score · additive (0/1).
- Definition:
  - **0** when the cell ended for an agent-attributable reason (budget or timeout, or a refusal), whatever `stuck_loops` is.
  - Otherwise, when `outcome == "completed"` and `stop_reason == "end_turn"`: **1** iff `stuck_loops == 0`, **0** iff `stuck_loops ≥ 1`, and **NA `stuck-loop count not measurable`** when `stuck_loops` is NA. This rule prevents NA-as-0 (TA 8).
- Rung: telemetry.
- NA reasons: `no cell outcome`; `cell ended by infrastructure: <cause>`; `stuck-loop count not measurable`.
- Fixtures:
  - the D1 and A1 cc and cp cells → 1; the D1 and A1 Codex cells → `stuck-loop count not measurable`.
  - **Seeded:** a budget end → 0; an infrastructure cause → NA; completed with a 3-run of failures → 0.

**`time_to_first_green`**
- Kind and class: score · additive (ms).
- Definition: prompt → the first passing test run by the agent.
- Rung: none.
- NA reason: `test runs not identifiable in the tool record (no command text extracted)` (DR-G2).
- Fixtures: every cell → that NA.

### Cost: grader `cost`, delegated to **W3-COST** phase 2 (A1, C1, D1, E6); kind and class are fixed here

- **Score rows:**
  - `cost_usd` · additive. It is a rebuildable cache (`:255`), with today's NA reasons (`runner.py:161-173`).
  - COST's design decides the rest of the cell-grain metrics under DM7: `tokens_per_minute`, `output_tokens_per_turn`, `cache_hit_ratio`, `cache_write_amplification` and `context_growth` (peak), all non-additive; and `compactions`, additive.
  - The rule: **one definition per quantity**. A metric that is already a view measure stays a view measure.
- **Derived:** `tokens_by_type`, `wall_clock_split`, `turns_and_tool_calls` (see DM7 above), `cost_of_pass`, `tokens_per_solved` and `coordinator_overhead`.
- **Fixtures:** all 9 cells → today's NA reasons, exact: `no price list entry for gpt-6-sol` or `… claude-haiku-4-5-20251001` (G16).

### Judged: grader `judge`, delegated to **W3-GW-D** (design) and W3-GW-I (build) (C1); the seam is fixed here

Nine metrics: `honest_completion_claims`, `error_handling`, `goal_drift_slope`, `unrequested_behaviour`, `assumption_disclosure`, `spec_quality`, `adr_quality`, `handoff_fidelity`, `mast_failure_codes`. All are non-additive rubric scores. Their rung is **judge**, because no mechanical oracle applies (DR-G1 places that sentence).

| Case | Value or NA reason |
| --- | --- |
| a metric with no `rubrics` entry for the task (8 of 9 on C1) | `no rubric for this task` (R-59 c2) |
| `adr_quality` on C1, in-run pass, or a cache miss without `--allow-model-calls` | `judge calls not allowed in this pass` (R-58 DR-2) |
| the judges differ by more than one rubric step | `judges disagree` (US-35 c2) |
| the backend is down | `judge backend unavailable` |
| a cache hit, or an allowed call | the verdict, synthesised per GW-D |

Fixtures: C1 smoke cells, once they exist, and W3-CAL's synthetic items (R-58 c5). CORE and GR-* use a fake judge (D7).

**NA-by-design in wave 3 (disclosed):** `behavioural_equivalence`, `verification_before_done`, `test_quality`, `maintainability`, `style_conformance`, `spec_coverage`, `constraint_violations`, `instruction_reread_rate`, `time_to_first_green`, plus 8 of the 9 judged metrics on C1.
- One constant table `{metric: reason}` in each grader.
- One parametrized test asserts `value is None` and the exact reason for each (Simplifier 7).
- DR-G5 asks the Owner about them at `0.5`.

## Reasons are deterministic (a byte-identity precondition)

- A reason is a fixed string from the tables above. Its only parameters are deterministic ones: counts, an exit code, an exception **type**, or a model id.
- A reason never contains a path, a timestamp, an exception message, a duration or any text the agent wrote.
- `export` includes `reason` (`_enc(Measure)`) and leaves out `evidence`.
- **Test** (CORE, one parametrized test over every committed fixture; Simplifier 9):
  1. Grade each fixture twice.
  2. The `(value, reason)` maps must be equal, and so must the export bytes.
  3. A lint over every reason rejects path separators, digits in a timestamp shape, and the fixture's temporary directory name.

## Catalog-version rule (R-59)

### 1. `0.4.dev` is a probe

- A pass whose `catalog_version` ends in `.dev` is never current: `views._current_pass(…, None)` skips it.
- `views.load(run, "0.4.dev")` still reads it, so the probe stays inspectable.
- `RunView.header["probe_passes"]` counts the skipped passes, and the report shows `probe pass: <n>`.
- This needs a seam, V-1.
- The 0.3 exports are read by explicit version, so they do not move.

### 2. `catalog_hash` on `grading.started` (R-59 c1)

Computed by `plan.tree_hash` (seam S-2).

### 3. `tool_versions` on `grading.started` (R-59 c4)

Each version is **measured** once at pass start, with a 30 s timeout:
- `python`: `sys.version.split()[0]`;
- `dotnet[<task>]`: `dotnet --version`, run with `cwd` = `tasks/<task>/workspace`, once per dotnet task in the plan. `global.json` selects the SDK (D&P 9);
- `dotnet-stryker`: the pinned tool's `--version`.

A tool that is absent reads `"not recorded"`, never empty or guessed.

### 4. The US-4 control: `tests/test_catalog_version.py` (CORE s2; absent today, G8)

Golden data: `tests/fixtures/catalog/<version>/<fixture>.export`. The version's `catalog_hash` and each golden file's sha256 are pinned in `bench/catalog-freeze.yaml`. That file is **Leader-only**: it goes in the lane map as a Leader path, and a track edit to it is a join-time `git diff --stat` finding (plan v5 controls).

The test grades each committed fixture offline, with the fake judge, under the current catalog. For a current `version` that does not end in `.dev`, it **fails** when any of these holds:
- (a) an export differs from its golden file. That is a score or reason moved with no bump.
- (b) the current `catalog_hash` differs from the one pinned for that version in `bench/catalog-freeze.yaml`. That is a weight, rubric, definition or anchor edit with no bump, which the export cannot see (D&P 1, TA 5, N1).
- (c) the golden files' sha256 differ from the digests pinned there. This stops a same-commit rewrite of the golden files.
- (d) no golden file exists for the version ("a freeze needs a golden export").
- (e) an entry already present in `bench/catalog-freeze.yaml` at the merge base (`git show <merge-base>:bench/catalog-freeze.yaml`, read-only) was changed or removed. The file is append-only per version (TA re-review 6).

A `.dev` version is exempt **only here** (R-59 c1). The test prints `probe: exempt`.

Red-first cases:
- a grader constant changed without a bump → red through (a);
- a weight changed without a bump → red through (b);
- a golden file rewritten → red through (c);
- a `.dev` version → green, and the exemption is visible.

Where the fixtures run:
- **Default ring:** correctness (python), process, clarify, cost, C1 architecture, the fake judge.
- **`slow` ring:** the dotnet graders (correctness, build, regression, rigor, drift on D1, mutation).
  - The `slow` marker is registered. **Both** selectors exclude it:
    - `addopts` becomes `-m 'not credentials and not slow'`;
    - `.github/workflows/ci.yml:25`'s own `-m "not credentials"` becomes `-m "not credentials and not slow"`.

    A command-line `-m` replaces the one in `addopts` (TA re-review 1, reproduced by the reviewer), so both must change. Seam V-4.
  - The ring runs at the **Leader's pre-freeze step on the grading host**: `HB_REQUIRE_DOTNET=1 python -m pytest -m slow`.
    - With `HB_REQUIRE_DOTNET=1`, a missing dotnet **fails** the test.
    - Without it, the slow tests skip with the reason `dotnet not required`.

    A test covers both cases. The result goes in the Proof Pack. CI has no dotnet (G17).
  - Every fake `dotnet` used in the default ring is paired with a slow-ring run of the same fixture (D7).

`test_grade.py:328`'s `"0.3"` literal becomes the catalog file's own `version` (seam V-2).

### 5. Rubrics

- `config.validate_repo` asserts `bench/rubrics/adr_quality.md` == `tasks/C1/oracle/rubric.md` byte for byte.
- It also asserts that each `rubrics:` value names an existing file.
- Seam V-3.

### 6. The freeze (R-59 c3)

The Leader freezes `0.4` only when all of these hold:
- every wave-3 grader's fixture values are recorded;
- the rubric is in the catalog;
- Q6's `total_nano_aiu` is in place;
- the slow ring is green on the grading host;
- golden exports and digests are committed.

A change after the freeze is `0.5`.

## Tasks-freeze rule (R-59 c5, R-62)

**The record.** Before CORE s1 joins, the Leader commits:

```yaml
schema: bench-task-freeze/1
tasks: {A1: 0127daa0…, C1: d9d72e41…, D1: b2b3170e…, E6: b3fd1ea1…}   # full hashes (G7); from the archives' plans where a cell exists
```

At the 0.4 freeze the Leader also appends to `bench/catalog-freeze.yaml`:

```yaml
schema: bench-catalog-freeze/1
versions: {"0.4": {catalog_hash: <hex>, golden: {<fixture>: <sha256>}}}
```

**Checks.**
- **Validate.** `config.validate_repo` fails with `tasks/<id> changed while frozen (R-59 c5): <hash> != <frozen>`. CI's `bench validate` turns any byte change under the four folders red. `validate_task` also rejects duplicate grader names. Both are seam V-3.
- **Plan.** `bench plan` makes the same check, seam S-3: `cmd_plan` does not call `validate_repo` today (verified by grep).
- **Grade.** Built today (`runner.py:154`), and now applied to every `reads_task` grader.

**Consequence.** No wave-3 grader adds a file under those folders. Task-specific oracle data goes in one of two places, or the metric is NA:
- the catalog (`bench/rubrics/**`);
- the grader code (the `architecture.py` and `drift.py` rule tables).

**End of the freeze.** The Leader deletes the `tasks` entry at the wave-3 close. After that, a task edit creates a new task version (spec `:237`).

## The byte-identity gate (defined precisely)

It is run by the Leader with `tools/check_regrade.py` (CORE s2; its own red-first tests).

**Gate archive.** Every completed run whose plan names A1, C1, D1 or E6 cells (R-59 DR-6). Today that is `row15-d1-1` and `a1-capture-1`, plus the smoke run once it exists.

**Preconditions:**
- P1: `0.4` is frozen.
- P2: `bench/prices.yaml` equals each run's `price_list_hash`.
- P3: `bench validate` is green.
- P4: no run is `running` (R-58 c3).
- P5: the 0.3 baseline digests (G6, and the smoke run's when it exists) are committed before CORE s1 joins (L-1).

**Steps per gate run R:**
1. `E03_before = sha256(export(load(R, "0.3")))`.
2. Pass A: `bench grade R --allow-model-calls`. Record `A_id`.
3. `VA = load(R, "0.4")`; `EA = sha256(export(VA))`.
4. Pass B: `bench grade R --allow-model-calls`. It runs **with the flag**, so that zero calls is a measured result of the cache, not a refusal. Record `B_id`.
5. `VB = load(R, "0.4")`; `EB = sha256(export(VB))`.
6. `E03_after = sha256(export(load(R, "0.3")))`.

**Pass criteria (all of them):**
1. **Both passes are real and distinct (TA 1).**
   - `VA.grading_id == A_id` and `VB.grading_id == B_id`, with `A_id != B_id`.
   - Each has a `grading.completed` row.
   - Without this, a dead pass B would make `EB` pass A's export again.
2. `EA == EB`.
3. `E03_before == E03_after ==` the committed baseline. For a run with **no 0.3 pass**, e.g. a smoke run graded in-run under `0.4.dev`, the check records `no 0.3 pass` and asserts `load(R, "0.3").grading_id is None` (TA re-review 3).
4. A's and B's `catalog_hash` equal the frozen hash.
5. **Non-vacuity (TA 4).**
   - In pass A, `pass_at_1` and `partial_credit` equal the 0.3 values for every cell. DR-G4 changes no current value (G16).
   - For a run with no 0.3 pass, the correctness values are compared with the exact values in the metric table instead.
   - Each metric's non-NA cell count equals the expected count in `tests/fixtures/gate/expected-counts.yaml`, an input to `check_regrade.py` written by CORE s2 from the metric table (TA re-review 4). For D1, for example: `pass_at_1` 6/6, `mutation_score` 5/6, `architecture_conformance` 5/6, `tool_error_rate` 4/6, `recovery_rate` 2/6, `planning_ratio` 2/6 (all from the metric table).
   - No reason in A starts with `HB-GRD-` or `infrastructure failure`.
6. **Judge calls (TA 3, D&P 6).**
   - Pass B makes **0 backend calls**, counted in the gateway's per-call record for B's `grading_id`. That fact and its columns are named by GW-D (S-5). Today's `model_calls` has neither a `grading_id` nor a gateway principal (G11), so this criterion cites GW-D's record, not today's columns.
   - The criterion needs **at least one judged item** in the gate archive.
   - With no C1 cells, the gate records `judge half not exercised: not proven` and does not claim a pass for it.
   - Red-first: a seeded cache miss in pass B turns it red (GW-I's test).
7. `bench verify R` exits 0, and `anchor: not recorded` is a warning (R-61 c1).

Red-first tests for `check_regrade.py`:
- pass B killed → red;
- pass B completes with one changed value → red;
- a 0.3 byte moved → red;
- every metric NA → red.

**Why the gate does not compare ledger bytes.** `grading_id` embeds a UTC time and random bytes (G4). Every ledger row carries `recorded_at`, `mono_ns` and a hash chain. So `export` is the reproducibility surface (US-26). It leaves out pass identity and evidence, and it includes every value and reason.

**Constraint on every wave-3 track.** The shape of `views.export` does not change in wave 3. A key or encoding change moves the 0.3 bytes and fails criterion 3. New measures appear only as score rows, which reach the 0.4 export through `scores`, or as `RunView.header` keys, which are not exported.

## Change-surface list (E7)

| Surface | Change | Owner |
| --- | --- | --- |
| store: `bench/metrics.yaml` | `0.4.dev`; `kind`, `rubrics`; 2 new ids | CORE s1 |
| store: `bench/rubrics/adr_quality.md` | a byte copy of C1's rubric | GW-I |
| store: `bench/task-freeze.yaml`, `bench/catalog-freeze.yaml` | new | Leader |
| model: `grade/__init__.py` | `Score`, `CellInput`, `grading_copy`; `_NotRecorded` and `not_built` retired (V-2) | CORE s1 |
| service: `grade/runner.py` | registry, dispatch, completeness check, `catalog_hash`, `tool_versions` | CORE s1, s2 |
| service: `grade/_changes.py` | pre-turn commit and change set; read-only git | GR-CODE c1 |
| service: each grader `grade_cell(inp)` | signature hunk, then the bodies | CORE s1 → GR-*, COST, GW-I |
| tool: `tools/check_regrade.py` | the gate checker | CORE s2 |
| validation: `config.py` | new fields; rubric equality; freeze; duplicate graders; `graders` checked against the registry | CORE (V-3) |
| plan: `plan.tree_hash`; `graders` frozen in the task record; the `cmd_plan` freeze check | — | STOP-I (S-1..S-3) |
| errors: `HB-GRD-003`, `HB-GRD-004` | — | STOP-I (S-4) |
| test config: the `slow` marker, `addopts`, and `ci.yml`'s `-m` | — | Leader grant (V-4) |
| projection: `views._current_pass` `.dev` skip; header keys | — | CORE s2 (V-1) |
| wire: `views.export` | **unchanged (a gate constraint)** | — |
| UI: the header shows probe passes, `catalog_hash`, `tool_versions`, `low-confidence matcher` | — | row 20; GW-I header hunk |
| compute readers: the US-4 test, `check_regrade.py`, row 19 (applicable set; rejects multi-pass input) | — | CORE s2; row 19 |

## Patterns (named and justified)

- **Parameter Object (`CellInput`).** It holds only what the runner already computes.
- **Strategy via a registry (`GRADERS`).** One line per grader. `validate` checks task `graders` against the registry, not against every `grade/*.py` stem. Today `runner` would pass as a grader.
- **Rebuildable cache (DM7)** for the telemetry-derived score rows, with a rebuild test that reads the ledger.
- **Golden master (characterization)** for US-4, together with the `catalog_hash` check.
- **Special Case** for NA: `Score(None, reason)`, one NA representation from the grader to the ledger and to the view.

**Solution-Selection Ladder:**
- **YAGNI:** argument extraction (DR-G2), a scenario filter, runtime convention mining and a `pre_turn_head` event field are all deferred.
- **Reuse:** `tree_hash`, `normalize.*_rows`, `procs.run` (Job Object and deadline), `correctness.parse_trx`, and correctness's copy-and-remove.
- **stdlib:** `difflib`, `ast`, `sys.stdlib_module_names`, `hashlib`, `filecmp`.
- **The one new external tool is Stryker.NET.** US-29 names it. It is pinned, spiked and measured each pass.
- No new Python dependency.

## Error and concurrency model

- **Concurrency is unchanged.** One pass holds `grade.lock`. Graders run sequentially.
  - `simplify:` ceiling: the D1 pass time, which is measured. Upgrade trigger: a gate pass longer than 2 h.
- **Errors.**
  - A grader failure is NA HB-GRD-003, and the pass continues.
  - A completeness mismatch is HB-GRD-004, and the pass is never completed.
  - A timeout is HB-GRD-002.
- **The archive is immutable.**
  - `_changes` finds the pre-turn commit with `git log --first-parent --reverse --format=%H%x00%s` and applies the tamper rule (STRIDE).
  - It materialises that commit with `git archive <commit> | tar -x` into `out_dir/pre-turn`. Both are read-only, and neither touches the index.
  - It computes the change set by comparing that tree with a `grading_copy`, CRLF-normalised, with build output excluded (Simplifier 4).
  - It never runs `git status` or `git diff` against the archived work tree.
  - Test: the archive's file hashes are equal before and after a fixture is graded.

## Failure-mode analysis

| # | Mode | Disposition | Test |
| --- | --- | --- | --- |
| F1 | NA recorded as 0 | **prevent:** `Score.__post_init__`; every NA reason has an exact fixture | the parametrized NA test plus each grader's NA fixtures |
| F2 | a duplicate or missing row in a completed pass (D&P 2) | **prevent:** grader de-duplication, the `validate_task` duplicate check, and the completeness check (HB-GRD-004) | `test_duplicate_graders_write_one_row_each`; `test_a_missing_or_extra_row_fails_the_pass_before_completed` (red first) |
| F3 | a grader raises | **mitigate:** NA HB-GRD-003 | `test_a_raising_grader_is_na_with_its_type_and_the_pass_completes` |
| F4 | a grader is not built | **mitigate:** NA `not built` | `test_an_unbuilt_grader_is_na_not_built` |
| F5 | a score, weight, rubric or tool change with no bump | **detect:** US-4 checks (a) to (c); `tool_versions` | `test_catalog_version.py` red cases |
| F6 | a `.dev` pass shown as current | **prevent:** the skip | `test_a_dev_pass_is_never_current_and_is_counted` |
| F7 | a task changes during the gate | **prevent:** the freeze in validate and plan; **detect:** the grade-time hash | `test_validate_fails_a_changed_frozen_task` |
| F8 | nondeterminism: reasons, or Stryker timeouts under load | **prevent:** the closed reason vocabulary; pinned Stryker timeouts; **detect:** grade twice (default ring), D1 mutation twice (slow ring) | the parametrized twice-test; `test_mutation_twice_is_equal` (slow) |
| F9 | a grader writes into the archive | **prevent:** read-only git and `grading_copy`; **detect:** the archive-hash test | `test_grading_leaves_the_archive_bytes_unchanged` |
| F10 | the pack install counted as scope creep | **prevent:** the base is the pack commit | the seeded pack-on test with stand-in files outside the blast radius |
| F11 | history rewritten, so the builder commit cannot be found | **mitigate:** NA `pre-turn commit not found…` | `_changes`: a rebased history → NA |
| F12 | a tool missing or changed | **detect:** `tool_versions`; **mitigate:** NA `mutation tool not available` | `test_mutation_tool_missing_is_na` |
| F13 | offline restore fails | **mitigate:** NA `infrastructure failure before build: restore`, never 0 (DR-G4 decides by cause) | seeded empty `NUGET_PACKAGES` |
| F14 | Codex has no per-call `ok` | **accept** in wave 3, disclosed (DR-G3) | the Codex NA fixtures |
| F15 | a slow D1 pass | **detect:** `grade.grader_done` durations; **accept** ≤ 2 h per gate pass | measured on the first D1 re-grade |
| F16 | a judged miss in pass B calls the backend | **detect:** gate criterion 6 | GW-I's seeded miss |
| F17 | a hostile working copy: a huge file, a symlink, a build target | **transfer:** ADR-0010 and ADR-0013 (Job Object, deadline); **mitigate:** bounded reads; `symlinks=True` | `_changes`: a symlink and a 300 MB file are not read past the bounds |
| F18 | the gate passes on a dead pass B, or on an all-NA run (TA 1, 4) | **detect:** gate criteria 1 and 5 | `check_regrade.py` red-first tests |
| F19 | rolling back the catalog alone rewrites 0.3 semantics (D&P 4) | **prevent:** rollback is a revert of code and catalog together | `test_0_3_code_and_catalog_regrade_the_0_3_fixture_to_its_golden` |

## Adversarial analysis (STRIDE-lite)

**The trust boundary:** archived cell output, written by the agent → the grader, running as host code. The agent's build and test code also runs during grading. This is the same boundary as correctness has today (ADR-0010, ADR-0013).

| Threat | Disposition | Test |
| --- | --- | --- |
| **T:** a fake `scripted-user.jsonl` or TRX | **accept**, as in phase-2 §8; parse strictly; stale TRX is deleted (built) | built TRX test; the clarify invalid-row test |
| **T:** a commit with a builder message, to move the base | **mitigate:** the base must be the root commit (depth 1), and the pack commit its first-parent child, both with exact messages; later look-alikes are ignored | `_changes`: a late look-alike commit is ignored |
| **I:** agent text or host paths reach the report through a reason | **prevent:** the closed vocabulary and its lint | the reason lint |
| **D:** an oversized log or diff; a build that never ends | **mitigate:** bounded reads; HB-GRD-002 | built timeout test; an oversized-log test |
| **E:** build targets run agent code on the host | **transfer:** ADR-0013 (Job Object, minimal env) | built |
| **S, R** | not applicable: there is no identity at this boundary, and scores are attributed to a sealed pass | — |
| judge injection and egress | **transfer:** W3-GW-D and W3-EGRESS | theirs |

## Privacy analysis (LINDDUN-lite)

There is no new personal-data flow.
- Graders read the operator's local archives and write numbers and fixed reasons. The reason lint keeps host paths, and so the user name, out of reports.
- Committed fixtures are cut from rows that carry session UUIDs and no paths, and from task files, which are public or authored. No transcript text is committed.
- Judge egress belongs to GW-D and EGRESS.

## UI and interaction design

N/A. The report surfaces are row 20 and GW-I's header hunk. This design only names the header keys they read.

## Telemetry

- **The log event** `grade.grader_done {grading_id, cell_id, grader, ms, outcome: ok|na|failed|not_built, na_count}` goes on the `harness_bench.grade` logger with the trace id. It lands in `engine.log` inside a run, and on stderr standalone.
  - It answers F15 and "which grader fails".
  - It is not a ledger fact.
  - Pass duration is already `grading.completed − grading.started` in the ledger, so no event is added for it (Simplifier 11).
- **Codes:** HB-GRD-003, HB-GRD-004 (new); HB-GRD-001, HB-GRD-002, HB-LED-004 (built).
- **Pass facts:** `catalog_hash`, `tool_versions`.
- **Test:** `test_grader_done_is_logged_per_grader`.

## Test plan (the Testing Strategy union)

Triggers:
- T1: pure metric functions.
- T2: parsers (TRX per test, build output, Stryker JSON, the scripted-user log, `ast` imports).
- T4: the archive, grading copies, git plumbing.
- T7: the score row, `grading.started`, the catalog schema, the export.
- T8: the fake judge, the fake dotnet.

Directives: **D0 + D1 + D2 + D4 + D6 + D7.** A1, A3 and A5 apply to the judge (GW-D and GW-I). **D3 deviation (recorded):** no layer or project reference is added.

| Directive | What | Owner |
| --- | --- | --- |
| D0 | Hermetic tests: no clock, no network; fixtures committed; no test reads `runs/`. Local naming `test_<behaviour>` (repo convention). | all |
| D1 | Per metric: exact positive fixtures, every NA reason, and seeded negatives. `tests/mutations/<grader>.json` names the mutants listed in the tables; each is paired with a fixture that kills it (TA 7): the meta exclusion (a failed meta row); the stuck-loop threshold (2-run and 4-run); the cap (two calls); the base (stand-in pack outside the radius); distinct ids (two calls on one id); constant 0 (the matched log); NA→0; a flipped comparison; the dropped `.dev` skip; the dropped freeze check; the dropped completeness check. | each slice |
| D2 | Properties: `Score` never allows value and reason together; the stuck-loop count is monotone in run length; `ask_vs_assume` ∈ [0,1]; `scope_creep` is 0 for any change inside the radius; recall ≤ 1. | GR-PROC, GR-CLAR, GR-CODE |
| D4 | Real git on temporary repos for `_changes`; real dotnet in the slow ring; the archive-immutability test. | GR-CODE |
| D6 | Golden exports with the `catalog_hash` and pinned digests (US-4); the `grading.started` shape; `validate_metrics` accepts and rejects the new fields; rubric byte equality; a Postel test that a 0.3 pass without `catalog_hash` reads as "not recorded". | CORE |
| D7 | The fake judge paired with GW-I's contract test; the fake dotnet paired with a slow-ring real run of the same fixture. | CORE, GR-CODE |
| Rebuild (DM7, DM11) | process and cost: the stored score equals a re-derivation from rows **read back from the sealed ledger segments** under the score's `extraction_id` (TA 12, D&P 7) | GR-PROC, COST |
| Byte identity (US-26) | the parametrized twice-test; CORE re-grades 2 committed mini-runs to equal exports; the 0.3 fixture's golden export is unchanged by 0.4 code; `check_regrade.py` red-first | CORE |
| Forbidden update (DM11) | a pass that would write a second row for (cell, metric) fails HB-GRD-004 before `grading.completed` | CORE |

**Fixtures.** They are cut and committed under `tests/fixtures/grade/<grader>/`, owned by the slice that needs them.
- **Row graders:** the cell's unstamped `tool_calls` and `model_calls` rows, its engine events and `scripted-user.jsonl`, all from the two runs, a few KB each; plus the seeded variants named above.
- **Working-copy graders:** an overlay of the cell's added and changed files (1–2 files, under 10 KB for the D1 pack-off cells, Verified).
  - It is applied to the frozen `tasks/<id>/workspace` in a temporary git repo that reproduces G9's commits.
  - Its pack-commit stand-in has files outside the blast radius, and no pack material.
  - C1 and E6 overlays are `oracle/reference/**`, copied from the frozen task at test time.

## Seams and delegations

| Id | From → to | What | When |
| --- | --- | --- | --- |
| S-1 | CORE → **W2-STOP-I** | freeze `graders` in the plan's task record | before CORE s2; fallback: §Data model |
| S-2 | CORE → **W2-STOP-I** | `plan.tree_hash(base, files)`; `task_version_hash` calls it (R-59 c1, R-62 a2) | before CORE s2 |
| S-3 | CORE → **W2-STOP-I** | `cmd_plan` makes the freeze check | with S-2 |
| S-4 | CORE → **W2-STOP-I** | `HB-GRD-003`, `HB-GRD-004` in `errors.py` | before CORE s1 joins |
| — | GW-I → **W2-STOP-I** | `cmd_grade --allow-model-calls` (R-58 c3) | GW-I's slice |
| V-1 | CORE → **Leader** | grant the `views.py` hunks: the `.dev` skip and the header keys | CORE s2 |
| V-2 | CORE → **Leader** | grant the `tests/test_grade.py` hunks (lines 164-166, 328, 332) | CORE s1 |
| V-3 | CORE → **Leader** | grant `config.py`: new fields, rubric equality, freeze, duplicate graders, the registry check | CORE s1–s2 |
| V-4 | CORE → **Leader** | grant `pyproject.toml` (the `slow` marker, `addopts`) and `.github/workflows/ci.yml:25` (`-m "not credentials and not slow"`) | CORE s2 |
| S-5 | GRADE-D ↔ **W3-GW-D** | C1's rubric scores `adr_quality`; `judge.grade_cell(inp)` returns the 9 ids under the NA rules above; GW-D names the gateway's per-call record (fact, `grading_id` column, principal) and `verdict_uses`' grain, key, placement and `heads` entry in an ADR amendment; CORE writes `verdict_uses` only after that | GW-D design → CORE s2 |
| C-1 | CORE → **W3-COST** | CORE s1 moves `runner.py:161-174` verbatim into `cost.grade_cell(inp)`, byte-equal on fixtures | CORE s1 |
| C-2 | CORE → **W3-GR-CODE** | CORE s1 moves `runner.py:153-160` verbatim into `correctness.grade_cell(inp)` | CORE s1 |
| L-1 | **Leader** | commit `bench/task-freeze.yaml` and the G6 baseline digests; send S-4 | before CORE s1 joins |
| R-19 | GRADE-D → **row 19** | composites take the applicable set per task and reject multi-pass input | row 19's design |
| SEC | GRADE-D → **Leader** | add the `documents` link from `docs/security/threat-model.md` and `privacy-review.md` to this design, and refresh the rollups. Those files are outside this track's owned path. | at the GRADE-D join |

## Slice plan

- Every row stipulates its model (R-33).
- Every slice is red first and ends with its mutation file and the default ring green. No slice runs `pytest -m ""`.
- `cli.py` and `plan.py` edits are **seam requests to W2-STOP-I until it joins (R-62 a2)**.

| Slice | Track · harness · model | Owns (paths) | Depends on | Exit evidence |
| --- | --- | --- | --- | --- |
| **CORE s1** (≤ 55 min) | W3-GRADE-CORE · Codex · `gpt-6-sol` | `grade/__init__.py`; `grade/runner.py`; the signature hunk of every grader module; the `cost.py` / `correctness.py` adapter hunks (C-1, C-2); `bench/metrics.yaml`; `tests/test_grade_runner.py`; `tests/mutations/grade.json`; granted: `tests/test_grade.py` hunks (V-2), `config.py` (V-3) | this design; S-4; L-1 | Red first: dispatch, `not built`, HB-GRD-003, the completeness check (HB-GRD-004), duplicate graders. On 2 committed mini-runs, `pass_at_1`, `partial_credit` and `cost_usd` equal 0.3's, and every other applicable metric is `not built`. The 0.3 fixture export is unchanged. |
| **CORE s2** (≤ 55 min) | W3-GRADE-CORE · Codex · `gpt-6-sol` | `grade/runner.py` (`catalog_hash`, `tool_versions`); `tests/test_catalog_version.py`; `tests/fixtures/catalog/**`; `tools/check_regrade.py` and its test; granted: `views.py` (V-1), `config.py`, `pyproject.toml` (V-4) | S-1..S-3 (or the STOP-I join); S-5 for `verdict_uses` | US-4 red cases (a)–(c); `.dev` exempt and visible; `catalog_hash` present; a `.dev` pass never current; rubric equality and freeze red on violation; `check_regrade.py` red on a dead pass B, a moved value, a moved 0.3 byte, and all-NA; US-4 check (e) red on an edited freeze entry; CI's `-m` excludes `slow`; the `HB_REQUIRE_DOTNET` test covers both cases (TA conditions 1–2) |
| **GR-CODE c1** | W3-GR-CODE · Codex · `gpt-6-sol` | `grade/_changes.py`; `grade/correctness.py` (`build_and_suite_clean`, DR-G4 by cause); their tests, mutation file and fixtures | CORE s1 | Spike note: per-test TRX and the build summary. Red first on the syntax-error, deleted-member and empty-cache fixtures and on the pack-on base. The archive-immutability test passes. |
| **GR-CODE c2** | same | `grade/correctness.py` (`regression_count`, the `behavioural_equivalence` NA) | c1 | seeded inverted test = 1; A1/C1/E6 → `task has no public tests` |
| **GR-CODE c3** | same | `grade/drift.py`; its test and mutation file | c1 | `scope_creep` and `_files` 0 on the 6 D1 cells; seeded edit = 3 lines and 1 file; pack-on stand-in 0; the block-namespace seed = `10.00`; drift NA reasons exact |
| **GR-CODE c4** | same | `grade/architecture.py`; its test and mutation file | c1 | the exact values in the table (C1 1/0; five D1 cells 1; `35af…` NA; Newtonsoft 0) |
| **GR-CODE c5** | same | `grade/rigor.py`; its test and mutation file | c1 | CS0168 seed = +1; D1 characterization in the slow ring; the 4 rigor NA reasons exact |
| **GR-CODE c6** | same | `grade/mutation.py`; the Stryker.NET pin and pinned timeouts; its test and mutation file | c1; the Stryker spike | spike note; `tool_versions` has Stryker; `35af…` → `no tests written`; the NoCoverage seed = `0.0000`; 5 D1 cells graded twice, equal |
| **GR-PROC p1–p3** (≤ 3 × 12 min) | W3-GR-PROC · Grok · `grok-4.7` | `grade/process.py`; `tests/test_grade_process.py`; `tests/mutations/process.json`; `tests/fixtures/grade/process/**` | CORE s1 | p1: `tool_error_rate`, `stuck_loops` (exact values and seeds). p2: `recovery_rate`, `planning_ratio`. p3: `completion_without_intervention` (its three seeds), the `time_to_first_green` NA, and the rebuild test from sealed segments. |
| **GR-CLAR l1** (≤ 2) | W3-GR-CLAR · Agy · `gemini-3.8-flash-high` | `grade/clarify.py` (the T0 half); `tests/test_grade_clarify.py`; `tests/mutations/clarify.json`; `tests/fixtures/grade/clarify/**` | CORE s1 | the 3 `a1-capture-1` logs and seeded logs (a)–(d) give the exact values in the table; the 5 named mutants are killed |
| **COST phase 2** | W3-COST · Claude · `claude-sonnet-5` | `grade/cost.py`, `tests/test_grade_cost.py` | CORE s1 (C-1) | its own design, under the one-definition rule |
| **GW-I** | W3-GW-I · Codex · `gpt-6-sol` | `grade/judge.py`; `bench/rubrics/adr_quality.md` | GW-D, CORE s1, EGRESS s1 | per GW-D; the judge NA table above |

**Critical path:** L-1 and S-4 → CORE s1 → (GR-CODE c1…c6 ∥ GR-PROC ∥ GR-CLAR ∥ COST phase 2 ∥ GW-I) → CORE s2 (S-1..S-3, S-5) → the Leader's slow ring and 0.4 freeze → the two gate passes. GR-CODE is the longest branch.

## Decision requests (open)

- **DR-G1 — the rubric preamble versus byte identity.**
  - The conflict: R-59 c2 wants the rubric's preamble to state why no mechanical oracle applies. DR-5 and c5 keep `bench/rubrics/adr_quality.md` byte-identical to the frozen C1 file, which only implies the reason (`rubric.md:3`).
  - **Recommended:** put the US-25 sentence in the catalog entry, either the existing `note:` field (the Simplifier's smaller form) or a `why_judged:` field. GW-I's judge input puts it before the rubric as its preamble. The file stays byte-identical.
  - Alternative: the catalog file becomes preamble + C1 bytes, and the equality check becomes "ends with".
- **DR-G2 — command intent in the tool record.**
  - The gap: `verification_before_done`, `time_to_first_green` and `instruction_reread_rate` need command or read-target text, and no reader extracts it (G10).
  - **Recommended:** NA in wave 3. A later row adds `ToolCall.intent`, which creates a new `extraction_id` and leaves the 0.3 export unchanged.
  - Alternative: a wave-3 slice across all three readers.
- **DR-G3 — Codex has no per-call outcome.**
  - The gap: every Codex row has `ok = null` (G10). So `tool_error_rate`, `stuck_loops`, `recovery_rate` and, through the NA rule, `completion_without_intervention` are NA for every Codex cell.
  - **Recommended:** accept and disclose in wave 3, then add a Codex reader row for exec exit codes.
  - Alternative: leave the process area out of cross-harness comparisons until then.
- **DR-G4 — a compile failure is 0, decided by cause.**
  - **Recommended for 0.4:** after a successful restore, any compiler error scores `pass_at_1` = 0 and `partial_credit` = 0, even when the error sits in a file the cell did not change (TA 9). Restore, SDK and timeout failures stay NA.
  - No current value changes (G16).
- **DR-G5 — nine metrics are NA by design.** They stay disclosed through wave 3. At `0.5` the Owner retires, re-sources or keeps each one.

## Conformance notes

- The design follows local conventions:
  - frozen result dataclasses;
  - exact reason strings (`runner.py:155`, `:163`);
  - `procs.run` for child processes;
  - no floats;
  - `tests/mutations/*.json`.
- **Recorded deviation:** `_NotRecorded` and `not_built` are retired in favour of `Score(None, reason)` (V-2).
- The design security rollups link is **not** added by this track, because it is outside the track's owned path. It goes to the Leader as seam SEC.
- Patterns appear in code as `# Pattern: …`.

## Flagged risks and residual unknowns

- **Flagged:** the dotnet build summary, the per-test TRX and Stryker.NET are unspiked (GR-CODE c1, c6). Their definitions are Inferred until the spikes run.
- **Flagged:** the D1 pass time is unmeasured. The design accepts up to 2 h per gate pass.
- **Flagged:** C1 and E6 have no archived cells, so the judge half of the gate is `not proven` until the smoke run exists.
- `assume:` the offline NuGet cache on the grading host holds every package the new build, test and Stryker steps restore.
  - Confirm: GR-CODE c1 builds the D1 fixture with `RestoreSources=.` and no network.
  - If false: the dotnet metrics are NA `infrastructure failure before build: restore`, and the gate's criterion 5 goes red.
- `assume:` `sys.stdlib_module_names` on Python 3.14.6 is the stdlib set the C1 prompt means.
  - Confirm: c4 records it.
  - If false: a stdlib import would score 0.
- **Residual:** tampering with the scripted-user log or the TRX is accepted (phase-2 §8; ADR-0010).
- **Residual:** the Codex process metrics are NA (DR-G3); nine metrics are NA by design (DR-G5).

## Status and next action

| | |
| --- | --- |
| **Completed** | Row 16 design, revision 2: the metric table with exact fixture values; `CellInput`, the dispatch and the completeness check; catalog `0.4.dev`, `catalog_hash`, `tool_versions` and the US-4 control; the tasks freeze; the byte-identity gate with non-vacuity checks; the slice plan and its seams. |
| **Remaining** | Row 17 (W3-GW-D, in parallel); the row-16 build (CORE, GR-CODE, GR-PROC, GR-CLAR, COST phase 2); the Leader's slow ring, freeze and gate; DR-G1..G5. |
| **Best next action** | The Leader does L-1 (the freeze record and baseline digests) and sends S-4 to STOP-I, then dispatches W3-GRADE-CORE s1 against this design. |

## Gate record

Reviewers ran in Adversary Mode, each on `opus`, on revision 1. The author cleared no veto. Each disposition below is written into revision 2.

**Test Architect: VETO on revision 1** (Blockers 1–2; Majors 3–10; Minors 11–12).

| # | Finding | Disposition in revision 2 |
| --- | --- | --- |
| 1 | The gate passes on pass A alone | **fixed:** criterion 1 asserts `A_id` and `B_id` and a completed row for each; `check_regrade.py` red on a dead pass B |
| 2 | No test reaches the matched branch in clarify | **fixed:** seeded logs (a) and (b); the "constant 0" and "count calls not ids" mutants |
| 3 | Criterion 4 cites columns that do not exist | **fixed:** criterion 6 cites GW-D's record (S-5); ≥ 1 judged item, else `not proven`; GW-I's seeded miss |
| 4 | An all-NA run passes the gate | **fixed:** criterion 5, non-vacuity |
| 5 | US-4 is blind to weights and rubrics, and to golden rewrites | **fixed:** checks (b) and (c); the weight red case |
| 6 | The slow ring has no home | **fixed:** the `slow` marker (V-4); run at the Leader's pre-freeze step on the grading host; a missing dotnet fails |
| 7 | Named mutants survive the fixtures | **fixed:** a failed meta row, 2-run and 4-run seeds, the two-call cap seed, stand-in pack files outside the radius |
| 8 | `completion_without_intervention` with `stuck_loops` NA | **fixed:** an NA rule plus three seeds |
| 9 | DR-G4 by file location rewards breaking unchanged files | **fixed:** decided by cause; the deleted-member seed |
| 10 | "Recorded at cN" values cannot fail | **fixed:** exact values from rows and files computed now; tool-run values are characterization accepted only with exact seeds passing |
| 11 | Stryker timeouts are nondeterministic | **fixed:** pinned timeouts; graded twice in the slow ring |
| 12 | The rebuild test is tautological | **fixed:** it re-reads the sealed ledger segments |

**Data & Persistence Architect: VETO on revision 1** (Blockers 1–2; Majors 3–6; Minors 7–10).

| # | Finding | Disposition in revision 2 |
| --- | --- | --- |
| 1 | The catalog invariant is not enforced | **fixed:** US-4 check (b) on `catalog_hash`; the weight red case |
| 2 | Duplicate rows poison the run; nothing enforces "no missing row" | **fixed:** grader de-duplication; the `validate_task` duplicate check; the completeness check before `grading.completed` (HB-GRD-004) |
| 3 | "Semi-additive: none" was false across passes | **fixed:** classes stated within one pass and one catalog version; the row-19 obligation (seam R-19) |
| 4 | Catalog-only rollback breaks the 0.3 semantics | **fixed:** rollback is a revert of code and catalog together, then a digest check; `test_0_3_code_and_catalog_…` |
| 5 | The applicable set is undefined with no plan graders and a changed task | **fixed:** the fallback rule in §Data model |
| 6 | `verdict_uses` and the gateway rows are unspecified | **fixed:** CORE writes no `verdict_uses` until GW-D's ADR amendment (S-5); criterion 6 cites that |
| 7 | The rebuild source was wrong | **fixed:** it reads under the score's `extraction_id` from whichever pass wrote the rows |
| 8 | `until:` had no reader | **fixed:** removed. The `golden` key's reader is the US-4 test. |
| 9 | `dotnet --version` depends on `global.json` | **fixed:** measured per task with `cwd` = its workspace |
| 10 | `turns_and_tool_calls` overlaps `calls_per_cell` | **fixed:** it is `kind: derived`, and the single definition is named |

**The Simplifier: APPROVE WITH CONDITIONS on revision 1** (Minors 1–9, Nits 10–12).

| # | Finding | Disposition in revision 2 |
| --- | --- | --- |
| 1 | Drop `scenarios` | **applied** |
| 2 | Drop the runtime HB-GRD-004 | **defended:** the D&P hard veto requires GradedOncePerPass enforced at the store. HB-GRD-004 now guards completeness, not only extras. A parametrized test "each grader's keys ⊆ its catalog ids" is added as well. |
| 3 | Drop `task_current` and `step_timeout`; make `grading_copy` a free function | **applied** |
| 4 | `_changes` via `git archive` | **applied** |
| 5 | Drop S-6 `pre_turn_head` | **applied** |
| 6 | Hardcode the convention rules | **applied**; measured now: R1 kept, R2 dropped at 93.9 % |
| 7 | One NA table with a parametrized test | **applied** |
| 8 | Fewer slices | **applied:** GR-PROC 3, GR-CLAR ≤ 2 (not 1, because of the added seeds) |
| 9 | One parametrized twice-test | **applied** |
| 10 | The golden-version clause is redundant | **applied, then superseded by D&P N1:** there is no `meta.json`; the hash and digests are pinned in `bench/catalog-freeze.yaml` |
| 11 | `grade.pass_done` is derivable | **applied:** dropped |
| 12 | `why_judged` could be `note:` | **carried** to the Owner as an option in DR-G1 |

**Re-review of revision 2** (the same reviewers, Adversary Mode, `opus`):

- **D&P: APPROVE WITH CONDITIONS. The veto clears once N1 is fixed.**

  | # | Finding | Disposition |
  | --- | --- | --- |
  | N1 (Major) | `meta.json` could be rewritten in the same commit as a weight | **fixed:** `meta.json` is removed. The `catalog_hash` and the golden digests are pinned in the Leader-only `bench/catalog-freeze.yaml`, and check (b) compares against it. |
  | N2 | A set comparison hides a duplicate | **fixed:** every (cell, metric) key must be written exactly once |
  | N3 | Two grains in one freeze file | **fixed:** `task-freeze.yaml` (wave 3 only) and `catalog-freeze.yaml` (permanent) are separate files |
  | N4 | `behavioural_equivalence` NA on non-D tasks | **recorded deviation:** the reason `not a D-task` |
  | N5 | The fallback wording | **fixed:** every catalog grader except `cost` and `process` |

- **Test Architect: APPROVE WITH CONDITIONS (PASS-WITH-CONDITIONS). The design-level veto is cleared.** Findings 1–2 must close before CORE s2 exits.

  | # | Finding | Disposition |
  | --- | --- | --- |
  | 1 (Major) | CI's command-line `-m` overrides `addopts`, so the slow tests run in CI | **fixed:** `ci.yml:25` added to V-4 and E7. The `HB_REQUIRE_DOTNET=1` opt-in, with a test for both cases. |
  | 2 (Major) | `meta.json` bypass | **fixed** by D&P N1 above |
  | 3 | No 0.3 pass | **fixed:** criterion 3 asserts `grading_id is None`; criterion 5 uses the table values |
  | 4 | No count numbers | **fixed:** `tests/fixtures/gate/expected-counts.yaml`, with D1 examples |
  | 5 | The NoCoverage seed could be covered by a vendored test | **fixed:** the seed test is in a new test project |
  | 6 | The golden digests rely on ownership alone | **fixed:** check (e), append-only against the merge base |

**The final state.** No Blocker is open, and no hard veto stands. The conditions are carried into the slice exit evidence: TA 1–2 before CORE s2 exits. At implementation, the Test Architect still requires traced tests, red observed before green, and a Proof Pack.
