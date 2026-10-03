---
id: "design-eval-identity"
title: "W1-D design: engine identity, freeze and per-launch recheck"
type: design
status: proposed
owner: "@timianmalloo"
phase: "Enterprise evaluation: Wave 1 (W1-D; builds as X-D in E1)"
tags: [benchmark, campaign, identity, freeze, evaluation-campaign]
links:
  - { to: spec-enterprise-evaluation, rel: implements }
  - { to: arch-evaluation-campaign, rel: implements }
  - { to: adr-0017-engine-identity-and-freeze, rel: depends-on }
  - { to: adr-0016-campaign-record, rel: depends-on }
  - { to: adr-0021-plan-level-resume-and-liveness, rel: depends-on }
  - { to: design-eval-seam-contracts, rel: depends-on }
review-by: "2026-10-17"
summary: >-
  Designs identity.py (manifest, hash, side, diff, the one CLASSES table), the per-launch run-side recheck in engine.py
  with identity_check_ms, grading.started.grade_identity_hash (E1), and the guards. Rules on the run/grade table: all 69
  existing files and 18 planned modules classed; no third "tooling" class; procs run, egress grade; telemetry/* moves to run
  (Owner request); platform stays sys.platform.
---

# W1-D: engine identity, freeze and per-launch recheck

Evidence labels: **V** verified (opened or run this session), **I** inferred, **A** `assume:`.

## 0. Rulings (the items routed to this slice)

| # | item | ruling | where |
| --- | --- | --- | --- |
| 1 | third class `tooling` (PAT W0 4, SIM W0 4) | **No.** Two classes stay. The five modules derive the numbers a verdict shows, so they stay `grade`; the cost is bounded (a re-grade, only on a mid-campaign defect fix). Revisit trigger is read from the ledger. | 4.3 |
| 2 | classes of `procs.py`, `egress.py` (PAT W1-F 11) | `procs.py` **run** (the engine spawns cells through it, V). `egress.py` **grade** (judge/report gate; imports `report.html`, V). X-F's edits cost nothing if they merge before the first discrimination record and the baseline. | 4.4 |
| 3 | allowlist entries `test_architecture.py:50`, `:228` | Specified exactly, with fixtures; `SUBPROCESS_CALLERS` is a mapping that narrows `bench_check.py` to `Popen`. | 8 |
| 4 | SEC F11 `platform` | Stays `sys.platform` (ADR-0017 s1). No version, no arch. A leak test pins it. | 3.4 |
| 5 | `grade_identity_hash` E1 or E3 | **E1.** ADR-0017 s5 needs it for the first verdict. | 6 |
| 6 | found en route | ADR-0017 s1 lists `telemetry/*` as grade, but the run path imports it (V). Owner request `req-01M41DJ56WN77QNKFCW34GMG3A` (recommendation A, provisional). | 4.2 |

## 1. Responsibility and phasing

One responsibility: **name what the engine is, and notice when it has moved.** It does not store campaign state (W1-C), render eligibility (W1-H) or admit fixes (campaign.py). Phase: E1, X-D, before X-F's code lands (for the two guard entries) and before the first discrimination record (the identity is a key of it). Order inside E1: all `src/` edits merge, then discrimination, then baseline. An edit after that is a recorded fix.

## 2. Data model (settled first)

- **Context.** Evaluation Campaign, sub-context *Engine identity*. Ubiquitous terms: component, manifest, side (run or grade), drift, effective identity (W1-C).
- **Value objects, no aggregate.** A *manifest* is an immutable value: `{"schema": "bench-identity/1", "components": {key: str}}`. It has no identity of its own and no invariant over time; its name is its hash. The only aggregate that holds identities is the campaign (W1-C: ledger + chain). No entity is added here.
- **Grain.** One component = exactly one input of the engine (one file, one tree, one setting). One manifest = the components at one instant. Components are **non-additive** (hashes); nothing is summed.
- **Durable representation.** Content-addressed `identity/<hash>.json` (W0 s6, written by X-C through `create_once`); the only row facts are `baseline.recorded`, `defect_fix.admitted` (W1-C). History is the append-only chain; **no Type-2 columns**: a change is a new manifest, never a rewrite.
- **Derive, don't store.** The run and grade parts are derived by `side()` from the one `CLASSES` table; the class is not written into the manifest, so there is no second definition. `plan.campaign.identity` stores the **run side only** (seam, below). The grade side is stored as one hash in `grading.started`; its components are not stored (named diffs come from the effective identity and the fix rows, 6).
- **Why not store the class in the manifest.** A re-class would then rewrite history. Instead `identity.py` is run-class and is hashed: editing `CLASSES` is itself a run-side change.

## 3. The contract

### 3.1 API (`src/harness_bench/identity.py`, class run, X-D)

```python
SCHEMA = "bench-identity/1"
CLASSES: Mapping[str, Literal["run", "grade"]]   # section 4, keyed by path under src/harness_bench/
PLANNED: frozenset[str]                           # W0 s9 modules not yet on disk (stale-entry exemption)
def catalog_hash(root: Path) -> str               # moved here from grade/runner.py:108 (ONE definition; seam)
def manifest(root: Path, tasks: Sequence[str], builds: Mapping[str, Mapping] | None = None) -> dict
def identity_hash(m: dict) -> str                 # sha256(ledger.canonical(m))
def side(m: dict, which: Literal["run", "grade"]) -> dict   # same shape, only that side's components
def diff(a: dict, b: dict) -> list[str]           # sorted: "grade/formal.py changed" | "<key> added" | "<key> removed"
def launch_check(root: Path, plan: dict) -> Callable[[], list[str]] | None
```

`builds` is `plan["builds"]` (the `Build.record()` dicts, V `tools.py:127`); identity never imports `tools`. `profiles/<h>` is derived for the keys of `builds`.

### 3.2 Components and recipes (all reuse existing recipes, V)

| key | value | class |
| --- | --- | --- |
| `src/harness_bench/<path>` (every file except `__pycache__`, **including non-`.py`**) | `plan.tree_hash(file.parent, [file])` | per section 4 |
| `catalog` | `catalog_hash(root)` (`tree_hash` of `metrics.yaml` + `rubrics/`) | grade |
| `prices` | `plan.file_hash(bench/prices.yaml)` (equals `plan["price_list_hash"]`, V `plan.py:344`) | grade |
| `gateway` (new; Owner request) | `file_hash(bench/gateway.yaml)`; `""` when absent (V `config.py:381`: optional) | grade |
| `bom` | `file_hash(bench/bom.yaml)` | run |
| `uv.lock` | `file_hash(uv.lock)` | run |
| `profiles/<h>` | sha256 of `ledger.canonical(plan.profile_record(root, h))` | run |
| `builds/<h>` | sha256 of `ledger.canonical(builds[h])` | run |
| `tasks/<id>` | `plan.task_version_hash(tasks/<id>)` | run |
| `platform` | `sys.platform` | run |
| `python` | `"3.14.6"` from `sys.version_info[:3]` | run |

A missing optional file records `""` (the `file_hash` convention). A file under `src/harness_bench/` with no class raises `BenchError("HB-IDN-002", "<path> has no run/grade class")`; `launch_check` turns that into a diff item, so a stray file stops launching.

### 3.3 Not in the manifest, with reasons (V by grep)

`bench/pack-markers.txt`, `bench/task-freeze.yaml` (task-validation inputs, read by `config.py:201,436`); `bench/calibration/**` (judge qualification, recorded in its own ledger); `bench/regrade-allowed-findings.yaml` (report filter, `report/__init__.py:109`); `bench/catalog-freeze.yaml` (checked at baseline against `catalog`). Docs, tests, `tools/`, `.github`: never (that is the point of ADR-0017).

### 3.4 `platform` (SEC F11)

`sys.platform` only: `win32`, `linux` or `darwin`. A Windows build number or CPU arch would make every OS update break a freeze (the class ADR-0017 rejected for the commit). Arch is covered where it matters: native build hashes (`builds/<h>`) differ per arch. Test `test_manifest_leaks_no_environment_or_path` sets `USERNAME`, `COMPUTERNAME`, `HOME`, `USERPROFILE` and a temp root to sentinels and asserts none occurs in `ledger.canonical(manifest)`; every key is a repo-relative posix path or a fixed name.

## 4. The run / grade classification (reviewed whole)

### 4.1 Rule

ADR-0017 s1 + W0 s9, made testable. A change that can alter what a measured cell **does or records while it executes**, or the plan a measurement run is built from, is **run**. Everything that only computes, displays or gates a derived number is **grade**. **A module used by both is run** (run dominates: a run-side change forces a re-run, which includes a re-grade). **Direction test (G2b):** no run-class file imports a grade-class file, resolved by the AST resolver, lazy imports included. Exempt: `cli.py` (the composition root; it injects `grade` into `EngineConfig`, V `cli.py:171`). Allowed, each a named pair in `RUN_IMPORTS_GRADE_ALLOWED` with its reason: `config.py` -> `egress.py`, `gateway/backend.py`, `gateway/scrub.py` (V `config.py:410,466,467`: validate-time lazy imports, not on a cell's path). Removal trigger: when the validators leave `config.py`.

### 4.2 The table (69 existing files: 28 run, 41 grade; SP-ID-2 found 0 unclassed, 0 stale)

- **run (28):** `__init__`, `archive`, `cli`, `config`, `driver`, `engine`, `errors`, `gitsafe`, `host`, `ledger`, `lifecycle`, `oslock`, `plan`, `preflight`, `procs`, `profiles`, `tools`, `workspace`; `scripted_user/*` (5: the engine's scripted user answers during a cell); `telemetry/*` (5).
- **grade (41):** `board`, `composites`, `egress`, `stats`, `status`, `views`; `gateway/*` (8 `.py`) and `gateway/schemas/*.json` (2); `grade/*` (14); `report/*` (9 `.py`) and `report/assets/report.js`.

**Finding (V): `telemetry/*` is run, against ADR-0017 s1's list.** `engine.py:46,663,734,787,857` and `driver.py:39,237,290` call `normalize` for usage, cause classification and `_spend`, which drives the spend-cap stop; `profiles.py:24,212` binds the readers. Under the ADR's grade class a change to `normalize.classify` would be a re-grade although it changes a cell's recorded cause. Flipping them to grade produces 6 run-to-grade edges in 3 modules (SP-ID-2 variant B). Owner request recommends the amendment. Until ruled, the table carries `telemetry/*` as run (provisional).

W0 s9 planned modules, reviewed: all 18 rows **confirmed**, no change: run `atomic`, `identity`, `resume`; grade `campaign`, `power`, `verdicts`, `gates`, `discriminate`, `readiness`, `synthetic_agent`, `grade/property`, `grade/bench_check`, `grade/_env`, `report/campaign_section`, `grade/rework`, `alarm`, `grade/noguess`, `grade/diffstats`. Checks: none of the run rows imports a grade one (`resume` and `atomic` import only `ledger`, `errors`, `lifecycle`); `grade/runner` -> `identity` is grade -> run (allowed). Residual (accepted, I): `python` and `platform` are run-only, so a re-grade on another interpreter is not flagged; trigger: any graded value differing across interpreters makes them dual (needs an Owner class value).

### 4.3 Ruling 1: no third class

- **Cost of the current rule (V ADR-0017 s4, s6).** A grade-class edit after the baseline is either a recorded fix (needs a defect class; verdicts are withheld until each campaign run has a new grading pass) or an unrecorded drift (the campaign is ineligible). Re-grade is a new local pass (ADR-0006); its duration is already in `grading.started` -> `grading.completed`, **not yet measured on a campaign** (the E1 demo reports it).
- **Why it is acceptable.** (a) `campaign`, `power`, `verdicts`, `gates`, `readiness`, `discriminate`, `synthetic_agent` all land before a baseline can exist (the baseline command and its preconditions are in them), so they are frozen *by construction*; only `alarm` (E3), `resume` (E3) and the strategy helpers land later, after the E1 campaign has concluded. (b) These modules **derive** what a verdict shows (eligibility, MDE, power, gate items, labels). With derive-don't-store, the code is part of the measurement; excluding it would let an edit change a verdict outside the freeze, which is what SIM W0 4's own cure ("classify by whether a change alters a recorded number") rejects for them. (c) Only `alarm.py` is outside that test, and one module does not justify amending ADR-0017 s1.
- **Revisit trigger (measured, no new instrument).** If `defect_fix.admitted` rows with `scope: grade` whose `changes` keys all lie in {`campaign`, `alarm`, `readiness`, `power`, `gates`, `verdicts`, `discriminate`, `synthetic_agent`, `report/campaign_section`} appear in two campaigns, raise the `tooling` class to the Owner with those rows.

### 4.4 Ruling 2: `procs.py` and `egress.py`

`procs.py` run: `engine.py` spawns every cell through it and `driver`, `workspace`, `tools`, `host`, `gitsafe` call it (V graph). `egress.py` grade: it gates judge and report payloads and imports `report.html` (V). X-F's edits (`procs.spawn(console=...)`, `task_canary`) are therefore one run-side and one grade-side change. Both merge in E1 before the baseline, so they cost nothing; after it they are a recorded fix each. X-F's byte-equal control for the default `spawn` path stands (PAT W1-F 11): `test_spawn_default_path_unchanged` (X-F).

## 5. The launch recheck (`engine.py`, X-D)

**Pattern.** Dependency injection of a strategy callable, as `EngineConfig.grade` already is (V). `EngineConfig` gains `identity_check: Callable[[], list[str]] | None = None`. The engine imports nothing new; `cli.py` passes `identity.launch_check(root, plan)` (None for a non-campaign plan). Chosen over a direct import so the engine tests use a fake and `engine` still imports no `plan`.

**Where.** One site, inside the launch loop, before `self._launch(...)` (V `engine.py:404-407`): the first launch is "when a campaign run starts", every later one is "before each launch" (ADR-0017 s7, quoted: "The engine recomputes the run-side part of the manifest when a campaign run starts and again before each `cell.launch_intent`"). Pseudocode of `_identity_ok()`: time the call; on a non-empty diff call it **once more** (a torn read is not drift); still non-empty -> `_stop_launching("HB-IDN-001", "engine identity drift", diff=diff, identity_check_ms=ms)` and stop launching; a raised exception stops the same way with `reason: "engine identity check failed: <ExceptionType>"` (fail closed). `_stop_launching` gains `**fields`. Running cells finish (V `run.launch_stopped` semantics, `status.py:160`).

**`identity_check_ms`.** Written on the `cell.launch_intent` row (the only launch record; no other span exists, V grep) and on the stop row. Absent for a non-campaign run, never `0` (IO1). W0 s12's "launch span" = this row (seam).

**What is rechecked.** src + `bom` + `uv.lock` + `profiles` + `tasks` + `platform` + `python` (run side). `builds` come from the plan: the real executables are already re-hashed at every cell start and a change stops the run (V `engine.py:625-629`, `tools.check_build`). Re-hashing them per launch would double 432 ms (716 MB, warm) for no coverage.

**Budget.** Measured (SP-ID-1, warm cache, this host): 66 src files / 974 KB 6 ms; small files 0.3 ms; 3 campaign-sized tasks 6.5 ms; all 38 tasks 200 ms. Expected check about 13 ms. **Budget p95 <= 250 ms warm**; the first launch is cold (not measured, I). The first E1 run reports median and max from the rows; a breach is a finding, not a gate.

## 6. `grading.started.grade_identity_hash` (E1, X-F writes)

`identity_hash(side(manifest(root, (), None), "grade"))`, computed once per pass in `grade/runner.py` beside `grader_build` (kept: it serves non-campaign passes; this is a campaign-side addition, and the manifest's `grade/*.py` entries are not a second definition of `grader_build`, which hashes `grade/*.py` by name only, V `runner.py:87`). Only on a campaign run (plan has `campaign`). The named diff for an ineligible verdict needs no stored grade components: it is `diff(effective, working tree)` when the tree drifted, or the keys of the later `defect_fix.admitted.changes` when a fix came after the pass; a pass on an unrecorded tree reads `graded under an engine not in the chain (<h12>)`. **Fix keys are manifest keys** (`src/harness_bench/grade/formal.py`), not diff labels.

## 7. Failure modes and security

| mode | category | disposition | test |
| --- | --- | --- | --- |
| file locked or vanished mid-hash (AV on Windows) | resource | retry 3x at 50 ms inside the read (`simplify:` ceiling: fixed retry; upgrade: backoff if measured), then diff `<key> unreadable` and stop: fail closed | `test_unreadable_component_is_named_after_retries` |
| torn read of a file being rewritten | concurrency | second read before stopping | `test_a_torn_read_is_not_drift` |
| merge into the checkout during a run | state | stop at the next launch, named diff | `test_a_drifted_file_stops_launching_with_a_named_diff` |
| stale plan (edited between plan and run) | state | stop at the first launch, no `cell.launch_intent` | `test_drift_before_the_first_launch_records_no_intent` |
| unclassed new file | input | HB-IDN-002 at baseline; diff item at launch | `test_unclassified_file_refused` |
| check is slow (cold disk) | time | recorded, never skipped | `identity_check_ms` rows |
| check raises | dependency | fail closed | `test_a_raising_check_stops_launching` |
| CRLF vs LF checkout | input | `tree_hash` normalises (V `plan.py:93`) | `test_manifest_is_line_ending_independent` |

STRIDE-lite (boundary: the working tree to the engine; single operator, ADR-0012). **T**ampering: a hand-edited plan or manifest is caught by the chain and `campaign verify` (name = hash); an operator who edits both is outside the threat model. **R**epudiation: the stop row carries the diff in the hash chain. **I**nformation disclosure: only repo-relative names, hex hashes, `sys.platform`, `3.x.y`; pinned by the leak test (negative security test). **D**oS: bounded by file count; unreadable fails closed. **S**poofing, **E**oP: none (read-only hashing, no execution; `profile_record` uses the existing loader). LINDDUN: no personal data in any component (same test).

## 8. Guards (G2, G3, and the two named entries)

- **G2** `tests/test_identity.py`: (a) every file under `src/harness_bench/` (not `*.py` only, not `__pycache__`) has a class; every `CLASSES` key not on disk is in `PLANNED`; (b) the direction test with `RUN_IMPORTS_GRADE_ALLOWED` and `cli.py` exempt. Red fixtures for (b), as synthetic trees: run imports grade at module level; the same lazily inside a function; relative `from ..x import y`; an allowed pair stays silent; `cli.py` exempt.
- **G3** `tests/test_architecture.py`: constant `IMPORT_LINT_MODULES` = the "yes" rows of W0 s9; red fixtures as W0 s10 lists. Both use a new helper `tests/import_graph.py` (the resolver extracted from `test_architecture.py:90-105`, V; seam), which X-F's G5 also uses.
- **D3 entry (`:44-52`).** Replace `path != SRC / "procs.py"` with `SUBPROCESS_CALLERS = {"procs.py": None, "grade/bench_check.py": frozenset({"Popen"})}` (None = any) and a function `_spawn_offenders(sources)`. Fixtures: `bench_check.py` calling `subprocess.Popen` is clean; calling `subprocess.run` is flagged; calling `os.system` is flagged; `grade/property.py` calling `subprocess.Popen` is flagged. `assume:` W1-F's `bench_check.py` spawns only through `subprocess.Popen` (V `eval-property-grader.md:207`); confirm: the D3 test is green on X-F's code; if false: widen the frozenset by seam.
- **R-60 entry (`:228`).** Add `"grade/property"` to `allowed`. Fixture in the existing `cases` map: `"the-property-grader-reaches-procs": (False, {"src/harness_bench/grade/property.py": "from harness_bench import procs\n\ndef spawn(a):\n    return procs.spawn(a)\n"})`. The closed side is already proven by `a-new-grader-spawns-through-procs` (True).
- Each guard's doc comment states root, recursion, tokens and allowlist constant (W0 s10), and lands with the code that makes it green (W0 rule).

## 9. E7 surface list

| layer | surface | owner |
| --- | --- | --- |
| store | `identity/<hash>.json`; `plan.campaign.identity` (run side); `grading.started.grade_identity_hash`; `cell.launch_intent.identity_check_ms`; `run.launch_stopped.{diff,identity_check_ms}` | X-C writes files; X-A1 plan field; X-F; X-D |
| model | `identity.py` (`CLASSES`, `PLANNED`, `catalog_hash`) | X-D |
| service | `engine.py` recheck; `grade/runner.py` hash and the `catalog_hash` import (lines 108-112, X-D by seam); `cli.py` one kwarg (X-C) | X-D, X-F, X-C |
| projection/wire | `lifecycle.TABLE` unchanged (V: keyed by kind only, `lifecycle.py:122-127`); `status.stop_code` already shows `HB-IDN-001`; the diff is not in `bench status` (finding F-2) | -- |
| client type | `Status` unchanged | -- |
| UI | W1-H renders `diff()` strings; they are display copy, machine readers use manifest keys | W1-H |
| compute reader | eligibility and effective identity read `side`, `identity_hash`, `diff` (W1-C/X-C) | X-C |

`errors.py` (X-D, first commit): `HB-IDN-001` "engine identity drift: launching stopped; the stop row names the differing components" and `HB-IDN-002` "a file under src/harness_bench has no run/grade class"; `RUN_CODES` entries, pinned by `test_errors.py`. Both W0 rows confirmed; no merge possible (different operator actions).

## 10. Patterns and the Ladder

Named: **Value Object** (manifest), **Strategy by injected callable** (the recheck, as `grade` is), **Content-addressed store** (existing, W0), **Table-driven classification** with a coverage test (one table, ADR-0017). Simplifier pass: no `Identity` class, no registry, no cache (13 ms measured does not need a stat cache; trigger: p95 > 250 ms), no stored class, no `tooling` class, no new function for the grade hash, no per-launch build hashing, no stored grade components. One reuse move: `catalog_hash` single definition (fallback if the seam is refused: keep both and add `test_catalog_component_equals_runner_catalog_hash`).

## 11. Telemetry (IO1-IO12)

| question | source |
| --- | --- |
| how long was the check; was it cold | `cell.launch_intent.identity_check_ms` (first row of a run is the cold one) |
| why did launching stop; which components | `run.launch_stopped{code, reason, diff}` |
| how often does drift stop a run | count of `HB-IDN-001` stop rows per campaign (derived) |
| which engine graded a pass | `grading.started.grade_identity_hash` |
| is the budget met | median/max of the rows, reported by the E1 demo |

Every path degrades to field-absent, never a plausible value.

## 12. Test plan by node id (red first; each fails before its code exists)

| W0 / ADR contract | test |
| --- | --- |
| s6 API; ADR-0017 s1 manifest | `tests/test_identity.py::test_manifest_is_deterministic`, `::test_manifest_is_line_ending_independent`, `::test_side_partitions_every_component`, `::test_diff_names_changed_added_removed`, `::test_unrelated_files_do_not_change_the_hash` (docs, tests, `tools/`) |
| builds/tasks/catalog/prices recipes | `::test_components_equal_the_existing_recipes` (`plan.task_version_hash`, `plan.profile_record`, `plan["price_list_hash"]`, `runner.catalog_hash`) |
| G2 (a) | `::test_every_src_file_has_a_class`, `::test_no_stale_class_entries`, `::test_unclassified_file_refused` (HB-IDN-002, includes a non-`.py` file) |
| G2 (b) | `::test_run_class_never_imports_grade_class` and its five red fixtures |
| SEC F11 | `::test_manifest_leaks_no_environment_or_path` |
| s6 recheck; ADR-0017 s7 | `tests/test_engine.py::test_a_drifted_file_stops_launching_with_a_named_diff` (running cells finish, no later intent, exit 3), `::test_drift_before_the_first_launch_records_no_intent`, `::test_a_torn_read_is_not_drift`, `::test_a_raising_check_stops_launching`, `::test_non_campaign_run_has_no_check_and_no_field`, `::test_launch_intent_carries_identity_check_ms` |
| class semantics end to end | `tests/test_identity.py::test_run_edit_stops_launch_grade_edit_does_not` (real `launch_check` on a temp tree) |
| s12 rows | the two engine tests above read the fields |
| HB-IDN-001/002 | `tests/test_errors.py` rows (existing pinning test) |
| D3, R-60 entries | `tests/test_architecture.py::test_only_procs_calls_subprocess_or_spawns` (+ fixtures, section 8), `::test_a_judge_backend_is_reached_only_through_egress_check_and_release` (+ the new case) |
| G3 | `tests/test_architecture.py::test_identity_campaign_power_verdict_gate_property_modules_never_import_gateway` |
| `grade_identity_hash` | X-F: `tests/test_grade_runner.py::test_grading_started_records_the_grade_identity` (changes with a `grade/*.py` edit, not with an `engine.py` edit) |
| mutation | `tests/mutations/engine.json`: drop the call; invert the diff test; drop the second read; each names a test above |

## 13. Spikes (run this session)

- **SP-ID-1 cost**, `spike_cost.py` over this checkout: results in 5. Not committed (outside owned paths); command: the script in the session scratchpad, read-only.
- **SP-ID-2 class table vs tree**: 69 files, 0 unclassed, 0 stale, 3 allowed lazy edges, 0 other violations; variant B (telemetry grade): 6 violations in `driver`, `engine`, `profiles`.
- Read, not run: `run.launch_stopped` extra fields are safe (V `lifecycle.py`, `status.py`).

## 14. Requests and findings

- Owner: `req-01M41DJ56WN77QNKFCW34GMG3A` (telemetry run; component `gateway`). Its evidence line says "5 more allowlist entries": the measured number is **6 edges** (correction).
- Coordinator seam: `req-01M41DJDH521RE0M4QJJK1FRTD` (7 W0 changes: `manifest` signature, E1 for the grade hash, plan stores run side, G2 scope and direction test, `catalog_hash` single definition with a runner edit, `tests/import_graph.py`, `SUBPROCESS_CALLERS` mapping; plus the `cli.py` kwarg and "launch span").
- F-1 (for W1-C): `grid.attached` should compare the plan's run-side identity hash with the effective identity; W0 s6 does not say so.
- F-2: `bench status` shows `HB-IDN-001` but not the diff (`status.py` is X-C's); low.
- Not produced here: rollups `threat-model.md` and `privacy-review.md` are not owned by this slice (Coordinator).

## Gate

`GATE w1-d-identity · pending · RV-PAT, RV-SIM (soft), RV-TA (hard), RV-SRE`

## Status

| | |
|---|---|
| **Completed** | the design above, both requests, three spikes |
| **Remaining** | reviewers' gate lines; apply findings; Owner ruling on the telemetry amendment; Coordinator answer on the seam |
| **Best next action** | RV-TA and RV-SRE review; then X-D builds the tests in section 12 |
