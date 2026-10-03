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
  with identity_check_ms, grading.started.grade_identity_hash (E1), and the guards. Rev 2 applies R-94 (telemetry/* run,
  gateway grade; ADR-0017 Amendment 1) and the four first-round reviews: a real-wiring test, red fixtures for every
  scan, one retry mechanism with a wall-clock cap, and a cost model that prices run-class edits. All 69 existing files
  and 18 planned modules classed; no third "tooling" class.
---

# W1-D: engine identity, freeze and per-launch recheck (revision 2)

Evidence labels: **V** verified (opened or run this session), **I** inferred, **A** `assume:`. Base of every count: `84980979` (main merged into this branch; W0 rev 3, R-87..R-96).

## 0. Rulings (the items routed to this slice)

| # | item | ruling | where |
| --- | --- | --- | --- |
| 1 | third class `tooling` (PAT W0 4, SIM W0 4) | **No.** Two classes stay (RV-SIM 1 and RV-PAT accept the conclusion). The cost model now prices run-class edits too (RV-PAT 1). | 4.3 |
| 2 | classes of `procs.py`, `egress.py` (PAT W1-F 11) | `procs.py` **run**, `egress.py` **grade**. | 4.4 |
| 3 | allowlist entries `test_architecture.py:50`, `:228` | `SUBPROCESS_CALLERS` is a frozenset of two paths, matched through the alias resolver (RV-SIM 6, RV-PAT 3; seam, 14). The R-60 entry gains `grade/property`. | 8 |
| 4 | SEC F11 `platform` | Stays `sys.platform`. A leak test pins it. | 3.4 |
| 5 | `grade_identity_hash` E1 or E3 | **E1.** | 6 |
| 6 | `telemetry/*` and `gateway` | **Ruled: R-94 (DR-8), granted.** `telemetry/*` is run; `gateway` is a grade-side component; ADR-0017 *Amendment 1* is written on this branch (it lands with the gate merge); `RUN_IMPORTS_GRADE_ALLOWED` stays at the 3 `config.py` pairs. | 4.2, 15 |

## 1. Responsibility and phasing

One responsibility: **name what the engine is, and notice when it has moved.** It does not store campaign state (W1-C), render eligibility (W1-H) or admit fixes (campaign.py). Phase: E1, X-D, before X-F's code lands (for the two guard entries) and before the first discrimination record. Order inside E1: all `src/` edits merge, then discrimination, then baseline. An edit after that is a recorded fix.

## 2. Data model (settled first)

- **Context.** Evaluation Campaign, sub-context *Engine identity*. Terms: component, manifest, side (run or grade), drift, effective identity (W1-C).
- **Value objects, no aggregate.** A *manifest* is an immutable value `{"schema": "bench-identity/1", "components": {key: str}}`. No identity of its own, no invariant over time; its name is its hash. The only aggregate that holds identities is the campaign (W1-C: ledger + chain). No entity is added here.
- **Grain.** One component = exactly one input of the engine (one file, one tree, one setting). One manifest = the components at one instant. Components are **non-additive** (hashes); nothing is summed.
- **Durable representation.** Content-addressed `identity/<hash>.json` (W0 s6, written by X-C through `create_once`). History is the append-only chain (`baseline.recorded`, `defect_fix.admitted`, W1-C); **no Type-2 columns**: a change is a new manifest, never a rewrite.
- **Derive, don't store.** The run and grade parts are derived by `side()` from the one `CLASSES` table; the class is not written into the manifest. `plan.campaign.identity` stores the **run side only**, and W0 s6 fixes what it holds: the chain's **effective** run side, never a stamp of the working tree (checked by X-C at plan time and at `grid.attached`: W1-C `check_plan`, V `eval-campaign-record.md` on `design/eval-campaign-record`). The grade side is stored as one hash in `grading.started`.
- **Why not store the class in the manifest.** A re-class would rewrite history. `identity.py` is run-class and hashed: editing `CLASSES` is itself a run-side change.

## 3. The contract

### 3.1 API (`src/harness_bench/identity.py`, class run, X-D)

```python
SCHEMA = "bench-identity/1"
CLASSES: Mapping[str, Literal["run", "grade"]]    # section 4, keyed by path under src/harness_bench/
PLANNED: frozenset[str]                           # W0 s9 modules not yet on disk (stale-entry exemption)
RUN_IMPORTS_GRADE_ALLOWED: Mapping[tuple[str, str], str]   # (importer, imported) -> reason + removal trigger; 3 pairs
def catalog_hash(root: Path) -> str               # moved here from grade/runner.py:108 (ONE definition; W0 s6)
def manifest(root: Path, tasks: Sequence[str], builds: Mapping[str, Mapping] | None = None) -> dict
def identity_hash(m: dict) -> str                 # sha256(ledger.canonical(m))
def side(m: dict, which: Literal["run", "grade"]) -> dict   # same shape, only that side's components
def diff(a: dict, b: dict) -> list[str]           # sorted: "grade/formal.py changed" | "<key> added" | "<key> removed"
# pure scans; each takes the table as a parameter so a fixture can drive it (rev 2, RV-TA 2, 3):
def unclassed(root: Path, classes: Mapping[str, str], planned: frozenset[str]) -> list[str]   # on disk, no class
def stale(root: Path, classes: Mapping[str, str], planned: frozenset[str]) -> list[str]       # keyed, not on disk, not planned; or on disk AND planned
# Erratum 1 (W0 rev 6.4, req-01M41KBTSTZ738NAGXNK0SRVXH): the two direction scans live in tests/import_graph.py, beside
# the resolver they need; production code cannot import a test helper. Same signatures; G2b calls them from there.
# tests/import_graph.py:
#   def import_violations(root: Path, classes: Mapping[str, str], allowed: Mapping, exempt: frozenset[str]) -> list[tuple[str, str]]
#   def stale_allowed(root: Path, classes: Mapping[str, str], allowed: Mapping) -> list[tuple[str, str]]   # listed, no longer imported
class CheckResult(NamedTuple): diff: list[str]; rechecked: bool
def launch_check(root: Path, plan: dict, *, clock=time.monotonic, sleep=time.sleep, deadline_s: float = 2.0) -> Callable[[], CheckResult] | None
```

`builds` is `plan["builds"]` (the `Build.record()` dicts, V `tools.py:127`); identity never imports `tools`. `launch_check` returns `None` for a plan with no `campaign` block, else a callable that compares `side(manifest(...), "run")` with `plan["campaign"]["identity"]`. `clock` and `sleep` are injected so tests control time. `unclassed`, `stale` (in `identity.py`) and `import_violations`, `stale_allowed` (in `tests/import_graph.py`, Erratum 1) are what G2 calls on a fixture tree and on the real tree; `manifest` calls `unclassed` and raises HB-IDN-002. `identity.py` keeps the tables the scans read (`CLASSES`, `PLANNED`, `RUN_IMPORTS_GRADE_ALLOWED`).

### 3.2 Components and recipes (all reuse existing recipes, V)

| key | value | class |
| --- | --- | --- |
| `src/harness_bench/<path>` (every file except `__pycache__`, **including non-`.py`**) | `plan.tree_hash(file.parent, [file])` | per section 4 |
| `catalog` | `catalog_hash(root)` (`tree_hash` of `metrics.yaml` + `rubrics/`) | grade |
| `prices` | `plan.file_hash(bench/prices.yaml)` (equals `plan["price_list_hash"]`, V `plan.py:344`) | grade |
| `gateway` (R-94) | `file_hash(bench/gateway.yaml)`; `""` when absent (V `config.py:381`: optional) | grade |
| `bom` | `file_hash(bench/bom.yaml)` | run |
| `uv.lock` | `file_hash(uv.lock)` | run |
| `profiles/<h>` | sha256 of `ledger.canonical(plan.profile_record(root, h))` | run |
| `builds/<h>` | sha256 of `ledger.canonical(builds[h])` | run |
| `tasks/<id>` | `plan.task_version_hash(tasks/<id>)` | run |
| `platform` | `sys.platform` | run |
| `python` | `"3.14.6"` from `sys.version_info[:3]` | run |

A missing optional file records `""`. A file under `src/harness_bench/` with no class raises `BenchError("HB-IDN-002", "<path> has no run/grade class")`; `launch_check` turns that into a diff item, so a stray file stops launching.

### 3.3 Not in the manifest, with reasons (V by grep)

`bench/pack-markers.txt`, `bench/task-freeze.yaml` (task-validation inputs, `config.py:201,436`); `bench/calibration/**` (judge qualification, its own ledger); `bench/regrade-allowed-findings.yaml` (report filter, `report/__init__.py:109`); `bench/catalog-freeze.yaml` (checked at baseline against `catalog`). Docs, tests, `tools/`, `.github`: never (ADR-0017).

### 3.4 `platform` (SEC F11)

`sys.platform` only. A Windows build number or CPU arch would make every OS update break a freeze. Arch is covered where it matters: native build hashes differ per arch. T-11 sets `USERNAME`, `COMPUTERNAME`, `HOME`, `USERPROFILE` and a temp root to sentinels and asserts none occurs in `ledger.canonical(manifest)`.

## 4. The run / grade classification (reviewed whole)

### 4.1 Rule

ADR-0017 s1 + W0 s9 (adopted by R-94 as the reading of s1). A change that can alter what a measured cell **does or records while it executes**, or the plan a measurement run is built from, is **run**. Everything that only computes, displays or gates a derived number is **grade**. **A module used by both is run** (run dominates). **Direction test (G2b):** no run-class file imports a grade-class file, resolved by the AST resolver, lazy and `TYPE_CHECKING` imports included. Exempt: `cli.py` (the composition root; it injects `grade` into `EngineConfig`, V `cli.py:171`).

`RUN_IMPORTS_GRADE_ALLOWED` holds **exactly three pairs**, each with its reason and removal trigger (R-94 condition 3; a fourth is a decision request, not an allowlist edit): `config.py` -> `egress.py`, `config.py` -> `gateway/backend.py`, `config.py` -> `gateway/scrub.py` (V `config.py:410,466,467`: validate-time lazy imports, not on a cell's path). Reason text per pair: "validate-time check, not on a cell's path; owner X-A1/X-A3; review 2027-10-03; remove when the validators leave `config.py`". The stale-pair test (section 8) fails when a listed import is gone, so the list only shrinks.

### 4.2 The table (69 existing files: 28 run, 41 grade; scan on `84980979`: 0 unclassed, 0 stale, 3 run-to-grade edges, all allowlisted)

- **run (28):** `__init__`, `archive`, `cli`, `config`, `driver`, `engine`, `errors`, `gitsafe`, `host`, `ledger`, `lifecycle`, `oslock`, `plan`, `preflight`, `procs`, `profiles`, `tools`, `workspace`; `scripted_user/*` (5); `telemetry/*` (5).
- **grade (41):** `board`, `composites`, `egress`, `stats`, `status`, `views`; `gateway/*` (8 `.py`) and `gateway/schemas/*.json` (2); `grade/*` (14); `report/*` (9 `.py`) and `report/assets/report.js`.

**`telemetry/*` is run (R-94).** ADR-0017 s1 listed it as grade; the engine reads every native record at cell end for the recorded cause and the spend stop (V `engine.py:661`, `_read_records` `:852`; `profiles.py:262`; `driver.py:39,237,290`). Under the grade list the scan finds 6 run-to-grade edges in `driver`, `engine`, `profiles` (R-94, counted as importing file -> telemetry file; the request's "5" was wrong). The direction test is the control: with `telemetry/*` run, the real-tree edge set equals the three `config.py` pairs exactly (T-12d).

**`gateway` is grade (R-94).** No run-class module reads `bench/gateway.yaml` on a cell's path (readers `grade/judge.py:94`, `report/judges.py:256`, `gateway/calibration.py`, validate-time `config.py:381`). It fixes the judge model and invocation behind every judged score. Absent -> present is a grade-side fix by design (R-94 condition 4); the baseline command does not require the file.

W0 s9 planned modules, reviewed: all 18 rows **confirmed**, no change: run `atomic`, `identity`, `resume`; grade `campaign`, `power`, `verdicts`, `gates`, `discriminate`, `readiness`, `synthetic_agent`, `grade/property`, `grade/bench_check`, `grade/_env`, `report/campaign_section`, `grade/rework`, `alarm`, `grade/noguess`, `grade/diffstats`. None of the run rows imports a grade one (`resume` and `atomic` import only `ledger`, `errors`, `lifecycle`); `grade/runner` -> `identity` is grade -> run (allowed). T-22 keeps this table and W0 s9 in step. Residual (accepted, I): `python` and `platform` are run-only, so a re-grade on another interpreter is not flagged by the hash; rev 2 adds both as plain fields on `grading.started` (section 6) so the trigger "a graded value differs across interpreters" has a data source.

### 4.3 Ruling 1: no third class, with the cost priced on both sides

- **Grade-side cost (V ADR-0017 s4, s6).** A grade-class edit after the baseline is a recorded fix (needs a defect class; verdicts are withheld until a new grading pass) or an unrecorded drift (ineligible). A re-grade is a new local pass (ADR-0006); its duration is `grading.started` -> `grading.completed`, **not yet measured on a campaign** (the E1 demo reports it).
- **Run-side cost (RV-PAT 1, the dearer one).** Run dominates, so `cli.py`, `errors.py`, `ledger.py`, `identity.py` and `__init__` are run, and a post-baseline edit to any of them makes the campaign's runs ineligible and forces a **re-run** (DI6), not a re-grade. W0 s13 (V) shows who edits them after E1: `cli.py` X-K2 (E3); `errors.py` X-J1 (E2), X-K1 (E3), X-LG (E4); `ledger.py` X-J1 (E2); `identity.py` X-J1, X-K1, X-LG; `engine.py` X-J1, X-K1. **Consequence, for the Coordinator's sequencing:** a campaign baselined in E1 meets each of those edits as a recorded run-scope fix or an ineligible run. The E1 demo campaign (R-89, `min_pairs` <= 3) is disposable. A campaign whose verdicts are published should baseline after the last planned `src/` edit, or its plan should list those edits as fixes with the cost named. This slice does not set that schedule (W0 s13 does); it states the price.
- **Why still two classes.** (a) The derive-only grade modules (`campaign`, `power`, `verdicts`, `gates`, `readiness`, `discriminate`, `synthetic_agent`) land before a baseline can exist, so they are frozen by construction; only `alarm` (E3) lands later. (b) These modules derive what a verdict shows. A hash of the module recorded on the verdict and re-derived without a re-grade is the real alternative to freezing them; it is refused on cost, not on principle: it needs an ADR-0017 s1 amendment for, in (a)'s own count, one module (`alarm`). (c) A narrower run class (an `errors.py` split so grade codes sit in a grade file) is not proposed: no measured fix yet (YAGNI).
- **Revisit trigger (measured, no new instrument; read at the E1 demo, then per campaign).** Count `defect_fix.admitted` rows with `scope: grade` whose `changes` keys all lie in modules W0 s9 marks derive-only (read from W0 s9 and `CLASSES`, no literal list here), and rows with `scope: run` whose keys all lie in {`cli.py`, `errors.py`, `ledger.py`}. Two campaigns with either count above zero, or one with both: raise a `tooling` class (or an `errors.py` split) to the Owner with those rows.

### 4.4 Ruling 2: `procs.py` and `egress.py`

`procs.py` run: `engine.py` spawns every cell through it and `driver`, `workspace`, `tools`, `host`, `gitsafe` call it (V). `egress.py` grade: it gates judge and report payloads and imports `report.html` (V). X-F's edits (`procs.spawn(console=...)`, `task_canary`) are one run-side and one grade-side change. Both merge in E1 before the baseline, so they cost nothing; after it they are a recorded fix each. X-F's byte-equal control for the default `spawn` path stands: `test_spawn_default_path_unchanged` (X-F).

## 5. The launch recheck (`engine.py`, X-D)

**Pattern.** Strategy by an injected callable, as `EngineConfig.grade` already is (V). `EngineConfig` gains `identity_check: Callable[[], CheckResult] | None = None`. The engine imports no `identity` and no `plan`; `cli.py` passes `identity.launch_check(root, p)` (None for a non-campaign plan), one keyword in `cmd_run` (X-C's file, W0 s13).

**Where and how often (RV-SRE 1).** One site, in the launch loop (V `engine.py:395-407`): `_identity_ok()` runs **once per tick**, before the first `_launch` of the tick, and its result clears every launch in that tick. ADR-0017 s7 reads "again before each `cell.launch_intent`"; the launches of one tick are milliseconds apart (a thread start), so the check that cleared the first covers the others. This is a stated narrowing, not a skip: with parallelism `p` the cost is one check per tick, not `p`. `_identity_ok()` times the call with `cfg.clock` (V `engine.py:96`), stores `self._check_ms` and `self._check_rechecked`, and returns `not diff`. A raised exception stops the same way with `reason: "engine identity check failed: <ExceptionType>"` (fail closed). On a non-empty diff: `_stop_launching("HB-IDN-001", "engine identity drift", diff=diff, identity_check_ms=ms)`. `_stop_launching` gains `**fields` (extra keys only; existing rows unchanged, T-32). Running cells finish (V `run.launch_stopped` semantics, `status.py:160`). A stop already held (disk floor, circuit breaker) wins first (V `engine.py:440-443`); the drift is then not recorded in that run, and the next run's first tick stops on it again: documented, not built (RV-SRE 7).

**One retry mechanism, in `identity.py` (RV-SIM 3, RV-SRE 3).** `launch_check` hashes each file; a locked or vanished file is retried 3x at 50 ms inside the read. When the diff is non-empty it **re-hashes only the differing keys once after a 50 ms pause** (`sleep` injected); keys that now match are dropped, and `rechecked` is true if the pause changed the result. The engine makes no second call. `simplify:` ceiling: fixed 50 ms pause and one recheck; upgrade trigger: a measured false `HB-IDN-001` stop, or a `rechecked` rate above 1 % of launches (then backoff). **Wall-clock cap (RV-SRE 1):** the whole call, retries and recheck included, stops at `deadline_s` (2.0 s, `clock` injected); keys not yet read are reported `<key> unreadable (deadline)` and launching stops. Fail closed.

**`identity_check_ms` (RV-TA 5, RV-SRE 4).** Defined as the **total wall time of one `_identity_ok()` call**, both reads and the pause included. It is written on the `cell.launch_intent` row of every launch cleared by that check (the hand-off is `self._check_ms`, set by `_identity_ok()` and read by `_launch`), with `identity_recheck: true` when the pause changed the result (absent otherwise), and on the `run.launch_stopped` row of a stop. The field is absent for a non-campaign run, never `0` (IO1). The first intent row of a run is the cold one by rule; the E1 demo reports median and max of the rest (warm) and the first separately. W0 s12's "launch span" is the `cell.launch_intent` row.

**What is rechecked.** src + `bom` + `uv.lock` + `profiles` + `tasks` + `platform` + `python` (run side). **`builds/<h>` is a plan-consistency key only (RV-SRE 5):** it is taken from the plan, so inside `launch_check` it compares the plan with itself. Executable drift is caught per cell by `tools.check_build` at cell start (V `engine.py:624-630`) and surfaces as `Cause.build_changed`, not `HB-IDN-001`. Re-hashing builds per launch would double 432 ms (716 MB, warm) for no coverage. The operator table:

| what stopped | code or cause | what the operator does |
| --- | --- | --- |
| a `src/`, task, profile, bom or lockfile component moved | `HB-IDN-001`, `diff` lists the keys | restore the file, or record a fix (`bench campaign fix`) and plan a new run |
| a file with no class | `HB-IDN-001` (`<path> has no run/grade class`) | send the class to X-D's `CLASSES` (seam), or restore |
| a pinned executable changed | `build_changed` (per cell) | reinstall the pinned build |
| the check could not read a file | `HB-IDN-001` (`<key> unreadable`) | free the lock (antivirus) and rerun |

**Console visibility (RV-SRE 2, major).** `bench run` ends by printing `status.text(...)`, which shows `stop_code` only (V `status.py:89,160`). `Status` gains `stop_reason` and `stop_diff` (first 5 keys plus a count line), read from the last `run.launch_stopped` row and shown under the code. `status.py` is X-C's in E1: seam request `req-01M41FVFTZ0QXT2XY7C2KHNE79` (provisional); test `test_status_shows_the_identity_stop_reason_and_diff` (X-C).

**Budget.** Measured (SP-ID-1, warm cache, this host): 66 src files / 974 KB 6 ms; small files 0.3 ms; 3 campaign-sized tasks 6.5 ms; all 38 tasks 200 ms. Expected check about 13 ms, which is the size of the supervisory-tick stall (accepted). **Budget p95 <= 250 ms warm**; hard cap 2 s per call. The cold first launch is unmeasured (I). **E1 exit evidence (RV-TA 7):** the E1 demo reports median, max and the cold first value of `identity_check_ms`; a breach is a finding, not a gate. A standing consumer after E1 (one line in `bench status` or the campaign report) is a next step, not built here (RV-SRE 8).

## 6. `grading.started` additions (E1, X-F writes)

- `grade_identity_hash` = `identity_hash(side(manifest(root, (), None), "grade"))`, computed once per pass in `grade/runner.py` beside `grader_build`, **only on a campaign run** (plan has `campaign`; absent otherwise, tested). It is not a second definition of `grader_build`, which hashes `grade/*.py` by name only (V `runner.py:87`). **`grader_build` is retained for non-campaign passes only; removal trigger:** `bench grade` is only offered for campaign plans (RV-SIM 5).
- `python` (`"3.x.y"`) and `platform` (`sys.platform`) as plain fields beside the hash, **not** in it (RV-SRE 6), so a verdict that differs across interpreters has a data source. Same leak rule as 3.4.
- The named diff for an ineligible verdict needs no stored grade components: `diff(effective, working tree)` when the tree drifted, or the keys of the later `defect_fix.admitted.changes` when a fix came after the pass; a pass on an unrecorded tree reads `graded under an engine not in the chain (<h12>)`. **Fix keys are manifest keys** (`src/harness_bench/grade/formal.py`), not diff labels.

## 7. Failure modes and security

| mode | category | disposition | test |
| --- | --- | --- | --- |
| file locked or vanished mid-hash (AV on Windows) | resource | retry 3x at 50 ms inside the read, then `<key> unreadable`, stop (fail closed) | T-13 |
| torn read of a file being rewritten | concurrency | re-hash the differing keys once after 50 ms; recorded as `identity_recheck` | T-14, T-15 |
| slow or hung disk | time | call-wide cap `deadline_s`; unread keys named | T-16 |
| merge into the checkout during a run | state | stop at the next tick, named diff | T-26 |
| stale plan (edited between plan and run) | state | stop at the first tick, no `cell.launch_intent` | T-27 |
| a plan stamped from a drifted tree | state | refused at plan time and attach (X-C, W1-C P-4); stopped at the first launch here | T-25 (real `bench run`) |
| unclassed new file | input | HB-IDN-002 at baseline; diff item at launch | T-8, T-9 |
| check raises | dependency | fail closed, reason carries the exception type | T-28 |
| CRLF vs LF checkout | input | `tree_hash` normalises (V `plan.py:93`) | T-1 |

STRIDE-lite (boundary: the working tree to the engine; single operator, ADR-0012). **T**ampering: a hand-edited plan or manifest is caught by the chain and `campaign verify` (name = hash); an operator who edits both is outside the threat model. **R**epudiation: the stop row carries the diff in the hash chain. **I**nformation disclosure: only repo-relative names, hex hashes, `sys.platform`, `3.x.y`; pinned by T-11 (negative security test). **D**oS: bounded by file count and `deadline_s`. **S**poofing, **E**oP: none (read-only hashing, no execution). LINDDUN: no personal data in any component.

## 8. Guards (G2, G3, the two named entries)

- **G2** `tests/test_identity.py`, both halves driven by the pure functions of 3.1 (`classes` is a parameter, so fixtures do not depend on the real table):
  - (a) coverage: `unclassed(root, classes, planned)` and `stale(root, classes, planned)`. Red fixtures on `tmp_path` trees: a new `.py` file; a new `.json`; a new `.js`; a key neither on disk nor in `PLANNED`; a key on disk and also in `PLANNED` (a landed module must leave `PLANNED`). The real-tree test calls the same functions with the real table (base `84980979`: 69 files, 0 unclassed, 0 stale).
  - (b) direction: `import_violations(root, classes, allowed, exempt)`. Red fixtures (synthetic tree and table): run imports grade at module level; the same inside a function; relative `from ..x import y`; `import harness_bench.grade.x as g`; `from harness_bench import grade`; the same under `if TYPE_CHECKING:` (flagged: a typing edge is still an edge); an allowed pair stays silent; `cli.py` exempt. `stale_allowed(...)` returns a listed pair whose import is gone, and the test fails on it. The real-tree test asserts the edge set **equals** `RUN_IMPORTS_GRADE_ALLOWED` exactly (3 pairs on `84980979`, scan output count 3; an extra or a stale pair both fail).
- **G3** `tests/test_architecture.py`: `IMPORT_LINT_MODULES` = the "yes" rows of W0 s9, red fixtures as W0 s10 lists; a test that every member is a key of `CLASSES`. Both guards use `tests/import_graph.py` (the resolver extracted from `test_architecture.py:90-105`, V; W0 s10), which X-F's G5 also uses.
- **D3 entry (`:44-52`).** `SUBPROCESS_CALLERS = frozenset({"procs.py", "grade/bench_check.py"})` and `_spawn_offenders(sources)` built on the alias resolver in `tests/import_graph.py`, not the `Name`-receiver match (V `test_architecture.py:46-50`), so aliases are seen (RV-PAT 3). No `Popen` narrowing (RV-SIM 6; the W0 s10 mapping is reversed by seam, 14). Fixtures: `grade/bench_check.py` calling `subprocess.Popen` is clean; `grade/property.py` calling `subprocess.Popen` is flagged; `from subprocess import Popen` in `workspace.py` is flagged; `import subprocess as sp; sp.run(...)` is flagged; `from os import system` is flagged; `os.system` is flagged. `main`'s rule allows only `procs.py`, so the first fixture is red on arrival (T-33).
- **R-60 entry (`:228`).** Add `"grade/property"` to `allowed`. Fixture in the existing `cases` map: `"the-property-grader-reaches-procs": (False, {"src/harness_bench/grade/property.py": "from harness_bench import procs\n\ndef spawn(a):\n    return procs.spawn(a)\n"})`. The closed side is proven by `a-new-grader-spawns-through-procs` (True).
- Each guard's doc comment states root, recursion, tokens and allowlist constant (W0 s10) and lands with the code that makes it green.

## 9. E7 surface list

| layer | surface | owner |
| --- | --- | --- |
| store | `identity/<hash>.json`; `plan.campaign.identity` (run side, effective); `grading.started.{grade_identity_hash, python, platform}`; `cell.launch_intent.{identity_check_ms, identity_recheck}`; `run.launch_stopped.{reason, diff, identity_check_ms}` | X-C writes files; X-A1/X-C plan field; X-F; X-D |
| model | `identity.py` (`CLASSES`, `PLANNED`, `RUN_IMPORTS_GRADE_ALLOWED`, the scans, `catalog_hash`) | X-D |
| service | `engine.py` `_identity_ok`, `_stop_launching(**fields)`; `grade/runner.py` hash and the `catalog_hash` import (lines 108-112 deleted, and line 60's `plan` import drops `tree_hash` and gains a top-level `from harness_bench.identity import catalog_hash`; X-D by seam, W0 rev 6.4); `cli.py` one kwarg (X-C) | X-D, X-F, X-C |
| projection/wire | `lifecycle.TABLE` unchanged (V: keyed by kind only, `lifecycle.py:122-127`); `status.py` gains `stop_reason`, `stop_diff` (seam) | X-C |
| client type | `Status` gains the two fields; `STOP_CODE` validation unchanged | X-C |
| UI | W1-H renders `diff()` strings; they are display copy, machine readers use manifest keys | W1-H |
| compute reader | eligibility and effective identity read `side`, `identity_hash`, `diff` (W1-C/X-C) | X-C |

`errors.py` (X-D, first commit): `HB-IDN-001` and `HB-IDN-002` with the W0 s11 copy, `RUN_CODES` entries, pinned by `test_errors.py`.

## 10. Patterns and the Ladder

Named: **Value Object** (manifest), **Strategy by injected callable** (the recheck, as `grade` is), **Content-addressed store** (existing), **Table-driven classification** with pure coverage functions (one table, ADR-0017). Simplifier pass: no `Identity` class, no registry, no cache (13 ms measured; trigger: p95 > 250 ms), no stored class, no `tooling` class, no new function for the grade hash, no per-launch build hashing, no stored grade components, one retry mechanism not two. One reuse move: `catalog_hash` single definition; RV-SIM supports it only with the fallback test `test_catalog_component_equals_runner_catalog_hash`, which is T-7.

## 11. Telemetry (IO1-IO12)

| question | source |
| --- | --- |
| how long was the check; was it cold | `cell.launch_intent.identity_check_ms` (first row of a run is the cold one) |
| how often did the recheck save a false stop | count of `identity_recheck: true` rows |
| why did launching stop; which components | `run.launch_stopped{code, reason, diff, identity_check_ms}`; shown by `bench status` (seam) |
| how often does drift stop a run | count of `HB-IDN-001` stop rows per campaign (derived) |
| which engine and interpreter graded a pass | `grading.started.{grade_identity_hash, python, platform}` |
| is the budget met | median, max and cold value of the rows, reported by the E1 demo |
| what did the telemetry class cost | `defect_fix.admitted` rows with `scope: run` whose keys all lie under `telemetry/` (R-94 condition 5) |

Every path degrades to field-absent, never a plausible value.

## 12. Test plan by node id (red first)

**Skeleton commit (lands first, so no test fails on an import):** `identity.py` with the 3.1 API as stubs (`manifest` returns `{"schema": SCHEMA, "components": {}}`; `identity_hash`, `side`, `diff` trivial; `unclassed`, `stale`, `import_violations`, `stale_allowed` return `[]`; `CLASSES = {}`; `launch_check` returns a callable returning `CheckResult([], False)`), the two `errors.py` codes, and `EngineConfig.identity_check` unused. Every "fails today" below is an assertion against that skeleton (or against `main` for the guard entries), never an `ImportError`, `AttributeError` or `NameError`. Files: `tests/test_identity.py` (T-1..T-25b), `tests/test_engine.py` (T-26..T-32), `tests/test_architecture.py` (T-33..T-35).

| id | test | the assertion that fails today, and why | red fixture | real wiring | mutant |
| --- | --- | --- | --- | --- | --- |
| T-1 | `test_manifest_is_deterministic_and_line_ending_independent` | `components.get("src/harness_bench/engine.py") == plan.tree_hash(...)` is false: the stub has no components | temp root; same file as LF and as CRLF | real `plan.tree_hash` | hash raw bytes (CRLF differs) |
| T-2 | `test_side_partitions_every_component` | both sides non-empty and their key union equals the manifest's: the stub's sides are empty | real tree | real `CLASSES` | a key in both sides |
| T-3 | `test_telemetry_edit_changes_the_run_side_only` (R-94) | after editing `telemetry/normalize.py` in a temp copy, the run-side hash differs and the grade-side hash is equal: the stub's run hash never differs | temp copy of `src/` | real `side` | class `telemetry/*` as grade: the grade hash changes, test red |
| T-4 | `test_gateway_is_a_grade_component` (R-94) | `bench/gateway.yaml` absent -> `""`; present -> its `file_hash`; an edit changes the grade-side hash and not the run-side one: the stub has no `gateway` key | temp root, three states | real `file_hash` | class `gateway` as run |
| T-5 | `test_diff_names_changed_added_removed` | `diff` returns `["grade/formal.py changed", "x added", "y removed"]`, sorted: the stub returns `[]` | two hand-built manifests | n/a | unsorted output |
| T-6 | `test_unrelated_files_do_not_change_the_hash` | hash equal after editing `docs/`, `tests/`, `tools/`; differs after editing `src/`: the stub's hash never differs | temp root | real `manifest` | hash the whole root |
| T-7 | `test_components_equal_the_existing_recipes` (includes the `catalog_hash` fallback) | `tasks/<id>`, `profiles/<h>`, `catalog`, `prices` equal `plan.task_version_hash`, the `plan.profile_record` hash, `grade.runner.catalog_hash`, `plan["price_list_hash"]`: the stub has none | real tree | real recipes | recompute `prices` from another file |
| T-8 | `test_unclassed_flags_each_new_file_kind` | returns the new `.py`, `.json` and `.js` paths: the stub returns `[]` | `tmp_path` tree with three extra files, `classes` without them | n/a | scan `*.py` only |
| T-9 | `test_unclassified_file_refused` | `manifest` on a tree with an extra non-`.py` file raises `HB-IDN-002`: the stub returns a manifest | `tmp_path` tree | real `manifest` | skip the call |
| T-10 | `test_stale_flags_ghost_and_landed_keys` | returns a key with no file and not planned, and a key on disk and in `PLANNED`: the stub returns `[]` | two `tmp_path` fixtures | n/a | drop the on-disk-and-planned case |
| T-10b | `test_real_tree_is_fully_classed` | `len(CLASSES) >= 69` and `unclassed == [] and stale == []` on the real tree: the stub's `CLASSES` is empty | real tree, real table | real table | delete one `CLASSES` key |
| T-11 | `test_manifest_leaks_no_environment_or_path` | no sentinel (`USERNAME`, `COMPUTERNAME`, `HOME`, `USERPROFILE`, temp root) occurs in the canonical manifest, and `platform` is one of `win32`, `linux`, `darwin`: the stub's manifest has no `platform` | sentinel environment | real `manifest` | `platform.platform()` |
| T-12 | `test_import_violations_red_fixtures` (parametrized, 6 forms in 8) | each form returns its edge: the stub returns `[]` | synthetic tree and table, one file per form | n/a | resolver ignores the lazy form |
| T-12b | `test_allowed_pair_and_cli_are_silent` | an allowed pair and `cli.py` return `[]` while the same import in another file returns an edge: the stub fails the second half | synthetic | n/a | exempt every file |
| T-12c | `test_stale_allowed_pair_fails` | `stale_allowed` returns a listed pair with no import: the stub returns `[]` | synthetic | n/a | drop the check |
| T-12d | `test_real_tree_edges_equal_the_allowlist` | the edge set equals the 3 `config.py` pairs: the stub's scan returns `[]` | real tree | real table | class `telemetry/*` grade: 6 extra edges |
| T-22 | `test_classes_match_w0_section_9` | a parser over a fixture snippet of W0 s9 reports one class mismatch; over the real doc, none: the stub has no entries | doc snippet with one wrong class | real doc | delete a `CLASSES` row |
| T-13 | `test_unreadable_component_is_named_after_retries` | a fake open raising `PermissionError` 4 times gives diff `"<key> unreadable"` after 3 sleeps of 50 ms: the stub returns no diff | injected `open`, `sleep` | n/a | retry forever |
| T-14 | `test_a_torn_read_is_not_drift` | a fake `sleep` restores the file during the pause: `CheckResult([], True)`: the stub reports `rechecked=False` | file rewritten at the pause | real `launch_check` | skip the recheck |
| T-15 | `test_a_persistent_diff_survives_the_recheck` | the file is still changed after the pause: diff names it, `rechecked=False`: the stub returns no diff | file left changed | real `launch_check` | recheck drops every key |
| T-16 | `test_check_stops_at_the_deadline` | a fake clock jumps 3 s on the first file: remaining keys listed `unreadable (deadline)`: the stub lists none | injected `clock` | n/a | drop the cap |
| T-17 | `test_run_edit_stops_launch_grade_edit_does_not` | real `launch_check` on a temp tree: an `engine.py` edit gives a non-empty diff, a `grade/formal.py` edit gives an empty one: the stub is empty for both | temp copy | real `launch_check` | class swapped |
| T-18 | `test_non_campaign_plan_has_no_check` | `launch_check(root, plan_without_campaign) is None`: the stub returns a callable | plan with no block | n/a | return a callable |
| T-25 | `test_bench_run_stops_on_a_drifted_run_side_file` (**real wiring**, RV-TA 1, R2-1) | real `cli.main([... "run", "r1"])` on **its own fixture**: a real confirmed `plan.json` with one cell and a `campaign` block (`identity.side(manifest(...))`, `plan_hash` re-stamped with `plan.plan_hash`, because `load_confirmed` rejects any edit, `plan.py:374`), the **real `engine.Engine`**, only `preflight.check` stubbed. A **run-class `src/` file** is edited after the plan (not a task file: a changed task stops `cmd_run` itself with `HB-USR-002`, `cli.py:134-136`, before the engine). Asserts exit 3, last `run.launch_stopped` in the run's `events` has code `HB-IDN-001` and a `diff` naming the file, zero `cell.launch_intent`; today the run launches. The T9-2 fixture (`test_cli.py:247-277`) stubs `engine.Engine` with `_FakeEngine`, writes `plan.json` as `{}` and stubs `load_confirmed`; it cannot be reused (RV-TA R2-1, V). Not run in this session: the fixture is specified, not executed; X-D's skeleton commit runs it first | the edited run-class file | real `cmd_run`, real `Engine`, no fake | drop `identity_check=identity.launch_check(root, p),` in `cli.py` (`tests/mutations/cli.json`) |
| T-25b | `test_bench_run_without_drift_launches` (R2-2, the twin) | same fixture, **no edit**: exactly one `cell.launch_intent` and no `run.launch_stopped` with `HB-IDN-001`; the cell's own outcome is not asserted. Proves the fixture reaches the engine, so T-25's zero intents is not a bad fixture or a preflight failure | none (control) | real `cmd_run`, real `Engine` | `launch_check` always returns a diff: red |
| T-26 | `test_a_drifted_file_stops_launching_with_a_named_diff` | the stop row equals `{"code": "HB-IDN-001", "reason": "engine identity drift", "diff": ["engine.py changed"], "identity_check_ms": <fake clock value>}` exactly; running cells finish; no later intent; exit 3: the engine ignores `identity_check` today | fake check | n/a | invert the diff test; drop the call |
| T-27 | `test_drift_before_the_first_launch_records_no_intent` | zero intents, one stop row, exit 3 | fake check drifted from tick 1 | n/a | check after `_launch` |
| T-28 | `test_a_raising_check_stops_launching` | stop row code `HB-IDN-001`, reason `engine identity check failed: OSError` | fake raises | n/a | swallow the exception |
| T-29 | `test_non_campaign_run_has_no_check_and_no_field` | no intent row has `identity_check_ms` (key absent, not 0) | `identity_check=None` | n/a | write `0` |
| T-30 | `test_launch_intent_carries_its_own_identity_check_ms` | a fake clock gives 7, 11, 13 ms to three ticks (parallelism 1): intents carry 7, 11, 13; `identity_recheck` is present only on the tick whose fake result has `rechecked=True` | fake clock | n/a | constant value; previous tick's value |
| T-31 | `test_one_check_per_tick` | parallelism 3, three pending in one tick: the fake is called once, the three intents carry the same value | counting fake | n/a | check per launch |
| T-32 | `test_other_stop_rows_are_unchanged` | a disk-floor stop row has exactly the keys it has on `main` (`kind`, `code`, `reason` + stamps) after `_stop_launching` gains `**fields` | disk-floor fixture | n/a | add `diff: None` to every row |
| T-33 | `test_only_procs_calls_subprocess_or_spawns` (+ section 8 fixtures) | the `bench_check.py` fixture is flagged on `main` (the old rule allows only `procs.py`) | fixtures | n/a | allow every `grade/` file |
| T-34 | `test_a_judge_backend_is_reached_only_through_egress_check_and_release` (+ the new case) | `"the-property-grader-reaches-procs"` expects False and `main`'s `allowed` lacks `grade/property` | the new case | n/a | drop `grade/property` |
| T-35 | `test_identity_campaign_power_verdict_gate_property_modules_never_import_gateway` | the three W0 red fixtures (`from ..gateway import x`, `import harness_bench.gateway as g`, `from harness_bench import gateway`) are flagged | fixtures | n/a | resolver without `node.level` |
| X-F | `tests/test_grade_runner.py::test_grading_started_records_the_grade_identity` | changes with a `grade/*.py` edit, not an `engine.py` edit; **absent on a non-campaign pass** (RV-TA 8); carries `python` and `platform` | temp edits | real `run_pass` | hash `grade/*.py` names only |
| X-C | `tests/test_status.py::test_status_shows_the_identity_stop_reason_and_diff` | `status.text` prints `stop_reason` and up to 5 diff keys plus a count line | a stop row with 7 diffs | real `status.build` | print the code only |
| errors | `tests/test_errors.py` rows | `HB-IDN-001`, `HB-IDN-002` in `RUN_CODES` with the W0 s11 copy | n/a | n/a | n/a |

Mutation files: `tests/mutations/engine.json`, `cli.json` and `identity.json` carry the mutants above, each naming its test. Where a fake check is used (T-26..T-32), T-25 is the real-composition test beside it and fails if the wiring line is removed. Adjacent pairs: torn read vs persistent drift are separated by T-14/T-15 (one code path, different file state after the pause); check per tick vs per launch by T-31; reason on drift vs on raise by T-26/T-28.

## 13. Spikes

- **SP-ID-1 cost** (first revision): results in 5. Not committed (outside owned paths).
- **SP-ID-2 class table vs tree**, re-run on the rev 2 base `84980979` with `scan.py` (session scratchpad, read-only): 69 files, 28 run, 41 grade, 3 non-`.py` files, 0 unclassed, 0 stale, **3** run-to-grade edges (`config.py` -> `egress.py`, `gateway/backend.py`, `gateway/scrub.py`). A first scan counted the package `gateway/__init__.py` as a fourth edge for `from harness_bench.gateway import backend`; the rule is: the target is the submodule when it exists, else the package. X-D's resolver states this rule and T-12 pins it.
- Read, not run: `run.launch_stopped` extra fields are safe (V `lifecycle.py`, `status.py`).

## 14. Requests and findings

- Owner `req-01M41DJ56WN77QNKFCW34GMG3A`: **ruled R-94 (DR-8), granted.**
- Coordinator seam `req-01M41DJDH521RE0M4QJJK1FRTD`: **answered in W0 rev 3** (all seven asks and both riders).
- New seam `req-01M41FVFTZ0QXT2XY7C2KHNE79`: (1) `status.py` gains `stop_reason`, `stop_diff` (X-C); (2) W0 s10 D3 `SUBPROCESS_CALLERS` becomes a two-path frozenset with no `Popen` narrowing (reverses W0 rev 3's mapping), matched through the alias resolver. Until answered, sections 5 and 8 mark both **provisional**.
- F-1 (the effective-identity comparison): **granted** in W0 rev 3 s6 and designed by W1-C (`check_plan`, `effective_identity`, P-1, P-4). This design reads `plan["campaign"]["identity"]` and does not compare with the chain (X-C does, under the lock).
- Not produced here: rollups `threat-model.md` and `privacy-review.md` (Coordinator).

## 15. ADR-0017 Amendment 1

Written on this branch in ADR-0006's form (a header bullet plus an "Amendment 1" section; s1's body is not rewritten) and landing with this slice's gate merge (R-94). It restates the s1 list with `telemetry/*` under run and `gateway` under grade, gives the reason with the cell-end read cited, records the accepted cost (a telemetry fix is `scope: run`) and records this as the first review of the "load-bearing" follow-up. Tests that pin it: T-3, T-4, T-12d.

## Review disposition

Round 1: RV-TA (BLOCK, 8), RV-SRE (PASS WITH CONDITIONS, 8), RV-SIM (PASS WITH CONDITIONS, 8), RV-PAT (PASS WITH CONDITIONS, 6). Applied = in this revision; Accepted = no change, reason given; Deferred = recorded next step.

| # | finding | disposition | where |
| --- | --- | --- | --- |
| TA 1 | no test fails if `cli.py` drops the check | Applied: T-25 drives real `cmd_run` and `Engine`; mutant on the `cli.py` line | 12 |
| TA 2 | G2 coverage half has no red fixtures | Applied: pure `unclassed`/`stale` taking the table; T-8..T-10 fixtures | 3.1, 8, 12 |
| TA 3 | direction test lacks forms and stale pair | Applied: `import ... as g`, `from harness_bench import grade`, `TYPE_CHECKING`, stale pair, synthetic `classes` | 8, T-12..T-12d |
| TA 4 | edge set not pinned after the ruling | Applied: T-12d equals the 3-pair allowlist exactly | 8 |
| TA 5 | no clock-controlled `identity_check_ms` test | Applied: hand-off specified; T-30 with a fake clock | 5, 12 |
| TA 6 | loose stop-row assertions | Applied: T-26 exact row, T-28 reason, T-32 other stops unchanged | 12 |
| TA 7 | budget cannot fail | Accepted: stays a finding; the E1 exit evidence names median, max and the cold value | 5 |
| TA 8 | grade hash absent on non-campaign pass | Applied: X-F test row | 12 |
| SRE 1 | unbounded retry, per-launch cost | Applied: once per tick; `deadline_s` 2 s cap; T-16, T-31 | 5 |
| SRE 2 | stop not actionable at the console | Applied: `stop_reason`, `stop_diff` in `Status` by seam (provisional) | 5, 14 |
| SRE 3 | torn-read recheck is immediate and unrecorded | Applied: 50 ms pause, `identity_recheck` on the row | 5, 11 |
| SRE 4 | `identity_check_ms` definition, cold row | Applied: total wall time; first row cold by rule | 5 |
| SRE 5 | `builds/<h>` is a self-comparison | Applied: stated; operator table | 5 |
| SRE 6 | grading interpreter not recorded | Applied: `python`, `platform` plain fields on `grading.started` (X-F) | 6 |
| SRE 7 | first stop wins, drift lost | Accepted: documented; the next run stops on it | 5 |
| SRE 8 | budget has no consumer after E1 | Deferred: one line in `bench status` or the report; next step | 5 |
| SIM 1 | no third class accepted | Accepted | 0, 4.3 |
| SIM 2 | literal nine-module list in the trigger | Applied: read from `CLASSES`/W0 s9 | 4.3 |
| SIM 3 | second whole-manifest read | Applied: collapsed into one retry in `identity.py`, marked `simplify:` | 5 |
| SIM 4 | `import_graph.py` earns its place | Accepted (kept) | 8 |
| SIM 5 | two hashes over `grade/*.py`; removal trigger | Applied: trigger stated | 6 |
| SIM 6 | drop the `Popen` narrowing | Applied: two-path frozenset; seam to reverse W0 s10 | 8, 14 |
| SIM 7 | table-driven shape a model | Accepted | 10 |
| SIM 8 | telemetry provisional | Applied: R-94 granted, `run` | 4.2 |
| PAT 1 | cost priced on the wrong side | Applied: run-side cost, tracks named, trigger extended | 4.3 |
| PAT 2 | launch check's reference identity unfiled | Applied: W0 rev 3 s6 and W1-C `check_plan`, P-4; this design reads the plan's effective stamp | 2, 14 |
| PAT 3 | `SUBPROCESS_CALLERS` misses aliases | Applied: alias resolver; fixtures | 8 |
| PAT 4 | four lists of the same modules | Applied: stale/landed test; T-22 against W0 s9; G3 members in `CLASSES` | 8, 12 |
| PAT 5 | allowlist on a prose trigger | Applied: reason, trigger and review date per pair; stale-pair test | 4.1 |
| PAT 6 | telemetry grade must not enter the allowlist | Applied: R-94 `run`; allowlist stays 3; a flip keeps G2b red | 4.2 |
| R-94 | telemetry run, gateway grade, Amendment 1, red-first pins | Applied: T-3, T-4, T-12d, section 15, ADR-0017 edited | 4.2, 15 |
| R2-1 | RV-TA rev 2: T-25's `assume:` is false (the T9-2 fixture fakes the engine) | Applied: T-25 rewritten with its own fixture (real confirmed plan, real `Engine`, run-class file edit); the `assume:` is removed | 12 |
| R2-2 | RV-TA rev 2: T-25 needs a no-drift twin | Applied: T-25b | 12 |

## Gate

`GATE W1-D · Test Architect · BLOCK · 8 findings (rv-ta-bd-e1e4, 2026-10-03)`
`GATE W1-D · SRE · PASS WITH CONDITIONS · 8 findings (rv-sre-e1e4, 2026-10-03)`
`GATE W1-D · Simplifier · PASS WITH CONDITIONS · 8 findings (rv-sim-ad-e1e4, 2026-10-03)`
`GATE W1-D · Patterns Expert · PASS WITH CONDITIONS · 6 findings (rv-pat-ad-e1e4, 2026-10-03)`
`GATE W1-D · Test Architect · PASS WITH CONDITIONS · 2 findings (rv-ta-d2-e1e4, 2026-10-03)`

## Status

| | |
|---|---|
| **Completed** | rev 2: R-94 applied, 30 review findings dispositioned, ADR-0017 Amendment 1, one seam request (`req-01M41FVFTZ0QXT2XY7C2KHNE79`) |
| **Remaining** | RV-TA re-review of rev 2; Coordinator answer on the seam; derive and merge at the gate |
| **Best next action** | RV-TA re-review; then X-D builds the skeleton commit and the tests in section 12 |
