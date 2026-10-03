---
id: "design-eval-seam-contracts"
title: "W0 seam contracts: the interfaces every Evaluation Campaign slice designs and builds against"
type: design
status: proposed
owner: "@timianmalloo"
phase: "Enterprise evaluation: W0 (serial spine item 2), before Wave 1"
tags: [benchmark, campaign, seam-contracts, coordination, w0, evaluation-campaign]
links:
  - { to: arch-evaluation-campaign, rel: implements }
  - { to: spec-enterprise-evaluation, rel: implements }
  - { to: coordination-eval-campaign, rel: implements }
  - { to: adr-0014-arm-and-cell-grain, rel: depends-on }
  - { to: adr-0015-multi-turn-attempt-and-turn-snapshots, rel: depends-on }
  - { to: adr-0016-campaign-record, rel: depends-on }
  - { to: adr-0017-engine-identity-and-freeze, rel: depends-on }
  - { to: adr-0018-hidden-check-harness, rel: depends-on }
  - { to: adr-0019-catalog-0-7-property-metrics, rel: depends-on }
  - { to: adr-0020-power-and-verdicts-stdlib, rel: depends-on }
  - { to: adr-0021-plan-level-resume-and-liveness, rel: depends-on }
  - { to: note-20261003-spike-e1-ntfs-atomic-publish, rel: depends-on }
  - { to: note-20261003-spike-e1-job-alone, rel: depends-on }
  - { to: note-20261003-spike-e1-handle-list, rel: depends-on }
  - { to: rulings-register, rel: depends-on }
review-by: "2026-10-17"
summary: >-
  The one vocabulary the twelve Wave 1 design slices and the Wave 2 tracks share: the ten property-task ids and their
  BOM and task.yaml stubs, the task.yaml property and expected-value fields, the PropertyCheck input and result,
  create_once and the directory publish, bench-matrix/2 and bench-plan/2, the campaign ledger rows, the identity
  manifest, the discrimination record, the catalog 0.7 metric ids, the power, verdict and gate shapes, every planned
  new module with its run/grade class, the HB codes reserved per track, the hub-file owner per phase, and the four
  frozen fields of every shared-surface guard.
---

# W0 seam contracts

**What this is.** Serial-spine item 2 of `docs/coordination/coordination-eval-campaign.md`. It fixes the *shape* of every interface that two or more slices touch, so the slices can be designed and built in parallel. A slice's design may **narrow** or **detail** anything here. It may not **widen** or **rename** it. A change that does is a seam request to the Coordinator (`coord request add --to coord-opus-e1e4`); a dispute goes to the Owner.

**Authority order.** The ADRs (0014-0021) and the spec (EV-1..EV-20) win over this doc. This doc wins over the coordination plan's descriptions of the same interfaces. Each contract below cites its ADR. Where this doc chooses something the ADRs leave open, it says **W0 decision** and gives the reason.

**Author:** Coordinator seat `coord-opus-e1e4` (Claude Opus 5.5), 2026-10-03, on main at `ce1aa06a` (rulings R-87..R-89 merged).

**Status of the rulings this doc reads:** R-87 (the Leader drives `coord-runner`; Sonnet tracks are Agent-tool spawns), R-88 (X-A1 and X-D fall back to Sonnet while Codex is unqualified), R-89 (the E1 demo combo is `cc-opus`, k = 3; the demo pre-registration sets minimum recorded pairs ≤ 3). One open decision request: **DR-4** (section 7). Section 7 is written to its recommended option and is **provisional** until the Owner rules.

## 1. The ten property tasks (ids fixed)

| id | property | track (authoring) | phase it becomes ready | BOM budget (provisional) |
| --- | --- | --- | --- | --- |
| `S1` | security | X-I | E1 | 45 |
| `S2` | security | X-I (S2) | E4 | 45 |
| `RS1`, `RS2` | resilience | X-RS | E4 (after SP-LB and X-LB) | 45 |
| `RW1` | rework | X-RW | E2 | 60 |
| `RW2` | rework | X-RW | E4 | 60 |
| `NG1`, `NG2` | no-guessing | X-NG | E4 | 45 |
| `SM1`, `SM2` | simplicity | X-SM | E4 | 45 |

- **W0 decision: scenario 5** ("Code from a prompt") for all ten. A property task is code written from a prompt in an existing codebase. Scenario 5 needs no change to `config.SCENARIOS` or the smoke-BOM rule. The property is a task field (section 2), not a scenario.
- **BOM:** `bench/bom.yaml` 0.6 adds the ten as `stub` entries, `smoke: false`, `source: authored`. Each authoring track edits **only its own entry** (a disjoint hunk) and its own `tasks/<ID>/`. The budget is provisional. The task's design (W1-I or W1-L) fixes it, within 1-60 minutes (`config.MAX_BUDGET_MINUTES`). A rework task's one budget covers both turns (ADR-0015 §3).
- `bom.subset: full` selects every non-fixture task, so it now includes these stubs. A matrix run already refuses a task that is not `ready`, and `G1` is already a stub in `full`. Grid-3 and grid-4 list their tasks explicitly, so EV-17's re-plan is unaffected (read 2026-10-03: `runs/grid-4/matrix.yaml:3`).
- **Two bases per property (DR-T1, EV-1):** each property's two tasks use different codebases. The authoring track names both bases in its design.

## 2. `task.yaml`: the property-task fields

A stub carries `property.name` only. A design fills the rest. Every field below is inside the task version hash (it is a file in `tasks/<ID>/`). Validation is X-E's `readiness.py`, called from `config.validate_task` through one hook line (X-A1 writes it; seam).

```yaml
schema: bench-task/1                 # unchanged
scenario: 5
property:
  name: security                     # security | resilience | rework | no-guessing | simplicity   (exactly one, EV-1)
  latent_requirement: "<one sentence>"
  evidence_paths: ["<path that exists in the base tree>"]          # at least one (EV-1)
  latent_terms: ["<term that would state the requirement>"]       # none may appear in prompt.md (EV-1)
  primary_metric: property_check_pass                             # kind: score, source D (EV-1; ADR-0019 item 2)
  ceilings: {}                       # rework: {rework_ratio: "0.3000"}; simplicity: {size_vs_reference: "…", new_abstractions: n, new_dependencies: n}
  fault_contract: {}                 # resilience only: {timeout_ms, tolerance_ms, max_retries}  (EV-3)
expected:                            # ADR-0019 item 5; one provenance comment per value (GLD-A)
  reference: {<metric id>: <value>}  # value: an int, a decimal string at the catalog scale, or {na: "<reason>"}
  naive:     {<metric id>: <value>}
turns: ["turns/2.md"]                # rework only; turn 1 stays prompt.md (ADR-0015 §1); at most 2 turns
graded_snapshots: [turn-1]           # rework only (ADR-0015 §8)
graders: [correctness, property]     # DR-4 (a): every property task names both
```

- **`expected` semantics (EV-7, EV-11):** readiness compares by exact equality at the catalog scale. `{na: "<reason>"}` is the only exemption, and it is the YAML form of the spec's `expected NA: <reason>`. A metric a task's graders name and `expected` omits fails readiness.
- **Oracle layout (B3; ADR-0018 §1; ADR-0016 §5):** `oracle/check/` holds the check entry point and `cases.yaml` (section 3). `oracle/solutions/reference/` and `oracle/solutions/naive/` hold the solution trees. A multi-turn task holds `turn-1/` and `turn-2/` under each. `bench_check.py` is **never** authored in a task: the grader copies it in.
- `tasks/README.md` gains a *Property tasks* section with this contract (W0 writes it; afterwards changes go through a seam request).

## 3. `PropertyCheck`: the hidden-check contract (ADR-0018; owner X-F in E1, X-LB in E4)

**Declared cases**: `tasks/<ID>/oracle/check/cases.yaml`:

```yaml
schema: bench-check-cases/1
entry: check.py                      # run with the base interpreter (sys._base_executable), never a venv launcher
interface: in-process                # in-process | loopback   (E1: in-process only, until SP-LB passes)
bounds_ms: {in-process: 2000, loopback: 5000}     # per-case wall bounds, per interface (ADR-0018 §12)
deliverable:                         # how the check builds and starts the deliverable (ADR-0018 §7)
  build: ["<argv>"]                  # optional; failure => primary 0, "deliverable did not build"
  start: ["<argv>"]                  # spawned only through bench_check.spawn_deliverable
  config: {host_env: HB_CHECK_HOST, port_env: HB_CHECK_PORT}   # loopback only: how host and port reach it
toolchain: [python]                  # a container runtime or a Linux-only tool fails readiness (EV-7)
env: []                              # extra variable names the check may pass, beyond HOST_ENV
cases:
  - {id: inj-1, kind: probe, bound_ms: 2000}       # kind: probe | fault | static
```

**Invocation.** The grader builds a grading copy under `cells_root/grading/<gid>/<cid>/property/` (ADR-0013 Am. 2) holding `deliverable/` (the archived final tree, or a named snapshot), `check/` (the oracle check) and `check/bench_check.py` (copied from `grade/bench_check.py`). It starts the check in a new Job Object with the outer bound `grading_step_timeout`, with `DETACHED_PROCESS`, and with `grade/_env.py`'s environment:

```
<sys._base_executable> check/<entry> --deliverable <abs> --cases check/cases.yaml --seed <int> --evidence <abs evidence dir>
```

- `seed = int(sha256(f"{task_version}|{cell_id}|{metric_id}").hexdigest()[:16], 16)` with `metric_id = property_check_pass` (ADR-0018 §6).
- The check calls only `bench_check.spawn_deliverable(argv, env_extra)` (explicit handle list, `HOST_ENV`, stdio redirected to files; §9, §10) and `bench_check.write_result(doc)` (one write, after the job holds the check alone; §10a(a)).

**Result.** Exactly one JSON document on the check's stdout, nothing after it:

```json
{"schema": "bench-check-result/1",
 "cases": [{"id": "inj-1", "outcome": "blocked", "duration_ms": 41}],
 "measures": {"exploit_probes_blocked": "1.0000"}}
```

- `outcome` ∈ {`blocked`, `exploited`, `passed`, `failed`, `timeout`}. Case ids come only from `cases.yaml`. A `measures` key is a catalog metric id of the task's property. Its value is an int or a decimal string at the catalog scale.
- **One-byte acknowledgement (spike E1-S3).** After the grader has validated and accepted the document, it writes one byte to the check's stdin. The check exits 0 only after reading it. Then the grader applies §10a(b): one document, arrived while the check was alive and alone in the job, followed by the check's own clean exit after arrival.
- **Grader outcomes** (closed vocabulary; `Score.reason` text):

  | condition | score row |
  | --- | --- |
  | malformed document | NA `check output invalid` (HB-CHK-001) |
  | §10a(b) violated | NA `invalid (check tampered)` (HB-CHK-002) |
  | outer bound fired | NA `check exceeded its bound` (HB-CHK-003) |
  | host suspend gap in the step | NA `host suspended`, re-run next pass (HB-CHK-004) |
  | build or start failed | `property_check_pass` = **0**, a measured failure (EV-1) |
- **W0 decision: a measured 0 carries no `Score.reason`.** `Score` allows a reason only with `value None` (`grade/__init__.py`, `Score.__post_init__`). EV-1's "0 with reason `deliverable did not build`", and the architecture's "the score's reason names the first failing case", are written into the evidence file, which `Score.evidence` points at (`<evidence file>:<line>`). `Score` does not change.

## 4. Crash-atomic writes: `src/harness_bench/atomic.py` (owner X-B1; consumers X-B2, X-C, X-E, X-J1)

```python
def create_once(path: Path, data: bytes) -> bool:
    """ADR-0016 §2a. Temp file in path.parent, write, fsync, close, os.link(tmp, path), unlink tmp.
    True = created; False = path existed with equal bytes (no-op).
    Different bytes: raise BenchError("HB-LED-007", ...) naming the path. Never overwrites."""

def publish_dir(final: Path, fill: Callable[[Path], T]) -> T:
    """ADR-0015 §5a. tmp = final.with_name(f"{final.name}.tmp-{os.getpid()}"); fill(tmp) copies into it;
    fsync every file; os.rename(tmp, final). On any exception the tmp sibling is left for the resume sweep.
    final exists before the rename: FileExistsError propagates (the caller decides; a resume re-verifies)."""

def stale_temps(final: Path) -> list[Path]:
    """The `<final.name>.tmp-*` siblings a resume deletes before redoing the copy (ADR-0021 §4)."""
```

- **Windows branch (spike E1-NTFS, quoted):** "a directory cannot be opened for fsync at all (PermissionError), so ADR-0015 section 5a's 'fsync the folder' is POSIX-only". `publish_dir` fsyncs the folder only when `os.name == "posix"`. W1-B states the branch and its test.
- Every create-only file (identity, prereg and power files; discrimination records) is written with `create_once(path, ledger.canonical(obj))`. Every archive and turn snapshot is written with `publish_dir`. There is no second helper (DM7).

## 5. `bench-matrix/2` and `bench-plan/2` (ADR-0014, ADR-0016 §6; owner X-A1 in E1, X-A3 in E3)

**`bench-matrix/2`:**

```yaml
schema: bench-matrix/2
bom: {file: bench/bom.yaml, subset: [S1]}
repetitions: 3
arms:                                # 2+ arms, ids ^[a-z][a-z0-9-]{0,15}$, at most one `off`, which has no pack
  - {id: off}
  - {id: candidate, pack: {source: "<repo>", commit: "<sha>"}}   # in a ring: role arms carry no pack (bound at plan time)
comparisons: [[off, candidate]]      # optional for 2 arms (default [[off, other]]; [[first, second]] with no off); required for 3+
combos: [{id: cc-opus, harness: claude-code, model: claude-opus-5-5}]
ring: {tag: pilot}                   # rings only: pilot | pack-regression | comparison
```

A `bench-matrix/1` file is read in memory as arms `on` (the plan's single `pack`) and `off`, in the file's order. No file is rewritten.

**`bench-plan/2`** is `bench-plan/1` with these changes:

| field | shape | phase · owner |
| --- | --- | --- |
| `schema` | `"bench-plan/2"` | E1 · X-A1 |
| `arms` | `{<arm id>: {"pack": {source, commit, revision} \| null}}` | E1 · X-A1 |
| `comparisons` | `[[reference, treatment], …]` | E1 · X-A1 |
| `launch_seed` | int, drawn at plan time; `cells` order = blocked randomisation by it | E1 · X-A1 |
| `cells[].arm` | arm id; replaces `cells[].pack`. `cell_id` keeps the recipe byte for byte: the ingredient named `pack` carries the arm id (ADR-0014 §3) | E1 · X-A1 |
| `kind` | `"measurement"` (default) \| `"discrimination"` (ADR-0016 §5) | E1 · X-A1 writes the field; X-E passes `discrimination` |
| `campaign` | absent, or `{campaign_id, prereg_hash: str \| null, identity: {hash, components}}`: written verbatim from a `build_plan` argument; plan.py imports neither campaign nor identity | E1 · X-A1 writes the field; X-C builds the block |
| `ring` | absent, or `{tag, hash}` (hash = `tree_hash` of the ring file) | E1 · X-A1 |
| `tasks.<id>.turns` | `[{n, sha256}]` for turns 2..n (US-9 per turn) | E2 · X-J1 (plan.py edit by seam to the E2 phase owner) |
| `cells[].calibration` | bool, EV-9 | E3 · X-A3 |

- **Accessors**, defined once in `plan.py`: `cell_arm(cell) -> str` (`arm`, else `pack`) and `arm_pack(plan, arm) -> dict | None` (`arms[arm].pack`; legacy: the top-level `pack` for `on`, `None` for `off`). No other reader reads `pack` (guard G1, section 10).
- **Label (W0 constraint, X-A1 picks the text):** a bench-plan/2 label must match `config.LABEL` (`[A-Za-z0-9.\-]{1,80}`) and name the arm. bench-plan/1 labels are never recomputed.
- **Launch balance (ADR-0014 §4, quoted):** "`bench plan` asserts the bound and refuses otherwise" → `HB-PLN-001`.

## 6. Campaign records (ADR-0016, ADR-0017; owner X-C, identity X-D)

**Ledger** `bench/campaigns/<campaign_id>/ledger.jsonl`. ADR-0006 rules: `ledger.canonical`, `stamp` (`recorded_at`, `mono_ns`) and the chain (`seq`, `prev_hash`, `hash`). A single writer, under `bench/campaigns/<id>/campaign.lock` (`oslock`). Lock first, then read the state (council D6). Every row is `{"kind": <kind>, "campaign_id": <id>, …fields}`, with this closed kind enum (ADR-0016 §1):

| kind | fields |
| --- | --- |
| `campaign.created` | `question` (str; never crosses B2) |
| `baseline.recorded` | `identity_hash`, `bench_commit` (**W0 refinement:** ADR-0017 §1 says the commit "is recorded beside it for provenance"; this is the place) |
| `defect_fix.admitted` | `defect_class`, `commit`, `changes: {component: [before, after]}`, `scope: run \| grade \| both` |
| `power.recorded` | `role: prior \| final`, `input_hash` |
| `ring_run.attached` | `tag`, `ring_hash`, `run_id` |
| `pilot.passed` | `run_id`, `grading_id`, `gate_input_hash` |
| `admission.decided` | `task`, `admitted: bool`, `reason` |
| `registered` | `prereg_hash` |
| `grid.attached` | `run_id` |
| `concluded` | — |
| `abandoned` | `reason` |

`campaign_id` matches `^[a-z0-9][a-z0-9-]{0,39}$` (W0 decision: a folder name that is safe on Windows and fits a label).

**Content-addressed files.** Each file's bytes = `ledger.canonical(obj)`, and its name = sha256 of those bytes. Each is written through `create_once`.

| file | `schema` | body |
| --- | --- | --- |
| `identity/<hash>.json` | `bench-identity/1` | `{"schema", "components": {<component>: <str>}}`. Components per ADR-0017 §1: `src/harness_bench/<path>` → `tree_hash` of that file; `catalog`; `bom`; `prices`; `profiles/<h>`; `builds/<h>`; `uv.lock`; `tasks/<id>`; `platform`; `python` (`"3.14.6"`). `identity_hash` = the file name. |
| `prereg/<hash>.json` | `bench-prereg/1` | EV-13's fields: `question`, `arms` (id → pack), `primary_metric` (property → metric), `mde` (property → decimal string), `alpha`, `power`, `correction {method, m}`, `pairing_unit`, `method`, `exclusions`, `min_pairs` (int; **R-89:** ≤ 3 for the E1 demo) |
| `power/<input_hash>.json` | `bench-power-inputs/1` | the inputs only (section 8) |

**Identity API (`identity.py`, X-D):**

```python
CLASSES: Mapping[str, Literal["run", "grade"]]        # one table, in code (ADR-0017 §1); section 9 seeds it
def manifest(root: Path, tasks: Sequence[str]) -> dict  # {"schema": "bench-identity/1", "components": {...}}
def identity_hash(m: dict) -> str
def side(m: dict, which: Literal["run", "grade"]) -> dict   # the run-side or grade-side part
def diff(a: dict, b: dict) -> list[str]                  # ["grade/formal.py changed", ...] (the EV-20 copy)
```

- The launch recheck (`engine.py`, X-D) compares `side(manifest(…), "run")` with the plan's `campaign.identity`, before each `cell.launch_intent` (ADR-0017 §7). On a mismatch: `run.launch_stopped{code: "HB-IDN-001", reason: "engine identity drift", diff: [...]}`, and the launch span carries `identity_check_ms`.
- `grading.started` gains `grade_identity_hash`. X-F writes it in `grade/runner.py`, calling `identity`. W1-D states whether this lands in E1 or E3.

**Discrimination record** (ADR-0016 §4; owner X-E), `bench/discrimination/<task>/<tv[:16]>-<identity[:16]>-<platform>.json`, written through `create_once`:

```json
{"schema": "bench-discrimination/1", "task": "S1", "task_version": "<64 hex>", "identity_hash": "<64 hex>",
 "platform": "win32", "run_id": "...", "grading_id": "...",
 "scores": {"reference": {"<metric>": 1}, "naive": {"<metric>": {"na": "<reason>"}}},
 "expected": {"reference": {...}, "naive": {...}},
 "readiness_failures": ["<item>"]}
```

- **Synthetic profile (X-E):** harness id `synthetic`, profile file `bench/profiles/synthetic.yaml`, combos `synthetic-reference` and `synthetic-naive`, arm `off`, rep 1. `synthetic` joins `config.HARNESSES` through a seam request to X-A1. The profile is excluded from every leaderboard and from the qualification suite's measured set (ADR-0016 *Follow-ups*).

## 7. Catalog 0.7: metric ids (ADR-0019; owner X-G1, then X-G3) and DR-4

`bench/metrics.yaml` `version: "0.7.dev"` in E1 and E2, and `"0.7"` when frozen (E3, then the Leader's `freeze_catalog.py`). ADR-0019 item 2 names **eleven** metrics: `property_check_pass` plus ten secondaries. The plan's "ten metrics" is a miscount; the ADR wins.

| id | kind | better | scale | property tag | DR-4 (a): grader |
| --- | --- | --- | --- | --- | --- |
| `property_check_pass` | score | higher | int 0/1 | every property | `property` |
| `exploit_probes_blocked` | score | higher | 4 | security | `property` |
| `fault_suite_pass` | score | higher | 4 | resilience | `property` |
| `idempotency_violations` | score | lower | int | resilience | `property` |
| `rework_ratio` | score | lower | 4 | rework | `property` |
| `turn1_tests_pass` | score | higher | int 0/1 | rework | `property` |
| `hallucinated_symbol_errors` | score | lower | int | no-guessing | `property` |
| `verified_before_use` | score | higher | int 0/1 | no-guessing | `property` |
| `size_vs_reference` | score | lower | 4 | simplicity | `property` |
| `new_abstractions` | score | lower | int | simplicity | `property` |
| `new_dependencies` | score | lower | int | simplicity | `property` |

- All eleven have weight 0 and source D. W1-G fixes `anchor`, `anchor_note` (R-79 forms) and the area. Scenario-7 `pass_at_1` keeps its existing id; the pass rule is a per-task `task.yaml` field that W1-G names.
- **DR-4 (open; recommended option applied provisionally).** `property_check_pass` needs "the stated ask's hidden tests pass" (EV-2..EV-6) plus the property's own checks. Today the hidden tests are the `correctness` grader's, and a grader cannot read another grader's output in the same pass (`grade/runner.py`: one `grade_cell` per grader, each over its own applicable set). Options:
  - **(a) Recommended.** One `property` grader records all eleven metrics. `runner.applicable` narrows its applicable set to the metrics tagged with the task's `property.name`, plus `property_check_pass`; the catalog gains a `property:` field per metric. The property grader runs the hidden tests by calling the correctness module's own test-run function (one definition), in its own grading copy. The task still names `correctness`, so `pass_at_1` stays on the board. Cost: hidden tests run twice per property cell, measured on the grading span. Rework, no-guessing and simplicity logic live in strategy helpers (section 9), not in registered graders.
  - (b) As (a), but property tasks drop `correctness`: tests run once, and `pass_at_1` is absent on property tasks (NOT_RECORDED after ADR-0019 item 4).
  - (c) `property` reads the correctness grader's evidence from the same pass (catalog order). This adds an ordering coupling between graders that GradedOncePerPass does not have. Not recommended.

  (a) and (b) amend `design-phase3-graders`' dispatch rule ("the applicable set is every `kind: score` catalog metric of those graders"), which is why this needs an Owner ruling. Until it is ruled, W1-F, W1-G and W1-L design to (a) and mark the dependence.

## 8. Power, verdicts, dominance, gates (ADR-0020; owner X-H1, section 3 X-H2)

Pure functions with no I/O. The campaign stores inputs only (ADR-0020 §5).

```python
# power.py
def analyse(inputs: Mapping) -> Mapping[str, PowerResult]      # property -> result; same inputs => same outputs
#   inputs (bench-power-inputs/1): population {description, exclusions}, source_run_ids, alpha, power,
#     correction {method: bonferroni|holm|none, m}, pairing_unit, harnesses, comparisons,
#     properties {<property>: {primary_metric, tasks, control_rate | "assumed", discordance, sd, rep_spread, mde}},
#     mean_wall_per_cell_s, mean_tokens_per_cell
#   PowerResult: alpha, power, mde, pairing_unit, correction, required_pairs {(harness, comparison): n},
#     reps_per_task, cells, hours, tokens, assumed: [input names]

# verdicts.py
@dataclass(frozen=True)
class Pair: task: str; rep: int; ref: int | Decimal; treat: int | Decimal; ref_tokens: int; treat_tokens: int; ref_wall_ms: int; treat_wall_ms: int
def verdict(prop: str, harness: str, comparison: tuple[str, str], pairs: Sequence[Pair],
            excluded: Sequence[tuple[str, str]], prereg: Mapping, seed: int, resamples: int) -> Verdict
#   Verdict: label ∈ {"better", "worse", "no difference ≥ MDE", "inconclusive (underpowered)", "inconclusive (not recorded)"},
#     effect, interval (lo, hi), per_task {task: (effect, lo, hi)}, both_tasks: bool | None, n_pairs,
#     excluded [(cell_id, reason)], token_ratio (r, lo, hi), wall_ratio, statement: "A dominates B" | "better at ×<r> tokens" | None
#   streams: stats.rng(seed, key); seed = the plan's launch_seed (W0 decision: one recorded seed per run)

# gates.py
def pilot(view) -> list[GateItem]                              # GateItem(kind, ident, detail); empty = pass (EV-14)
def pack_regression(view, mde: Mapping[str, Decimal]) -> Mapping[str, str]  # "regression signal" | "no regression detected at <MDE>"
```

`report/campaign_section.py` (X-H2) renders a `Verdict` list plus the EV-20 header from the ledger reader `campaign.read(campaign_id) -> CampaignState` (X-C). Until X-C joins, it builds against fixtures of that shape.

## 9. Planned new modules and their run / grade class (ADR-0017 §1; X-D seeds them all in E1)

The rule (W0 decision, for the new modules only): **run** if the module runs on a cell's execution or launch path, or builds a plan; otherwise **grade**. W1-D reviews the whole table (ADR-0017: "the run/grade classification is load-bearing and needs review at the gate"). A module not in this table needs a seam request to that phase's `identity.py` owner.

| module | class | track · phase | in the C5/C9 import-lint set (G3) |
| --- | --- | --- | --- |
| `src/harness_bench/atomic.py` | run | X-B1 · E1 | — |
| `src/harness_bench/identity.py` | run | X-D · E1 | yes |
| `src/harness_bench/campaign.py` | grade | X-C · E1 | yes |
| `src/harness_bench/power.py` | grade | X-H1 · E1 | yes |
| `src/harness_bench/verdicts.py` | grade | X-H1 · E1 | yes |
| `src/harness_bench/gates.py` | grade | X-H1 · E1 | yes |
| `src/harness_bench/discriminate.py` | run (it builds a plan) | X-E · E1 | — |
| `src/harness_bench/readiness.py` | grade | X-E · E1 | — |
| `src/harness_bench/synthetic_agent.py` (the synthetic "agent"; W1-E may move it within `src/harness_bench/`, by seam) | run | X-E · E1 | — |
| `src/harness_bench/grade/property.py` | grade | X-F · E1 | yes |
| `src/harness_bench/grade/bench_check.py` | grade | X-F · E1 | yes |
| `src/harness_bench/grade/_env.py` | grade | X-F · E1 | yes |
| `src/harness_bench/report/campaign_section.py` | grade | X-H2 · E1 | — |
| `src/harness_bench/grade/rework.py` (strategy helper under DR-4 (a)) | grade | X-J2 · E2 | — |
| `src/harness_bench/resume.py` | run | X-K1 · E3 | — |
| `src/harness_bench/alarm.py` | grade | X-K2 · E3 | — |
| `src/harness_bench/grade/noguess.py` (strategy helper) | grade | X-LG · E4 | — |
| `src/harness_bench/grade/diffstats.py` (strategy helper) | grade | X-LG · E4 | — |

`identity.py` is in the lint set because ADR-0011 Am. 1 names "the campaign, identity, power, verdict, gate and property-grader modules".

## 10. Guards over shared surfaces: the four frozen fields (GO14a)

Each guard's doc comment states these four fields verbatim, with a **named allowlist constant**. The clause it discharges carries the same qualifier. A later edit that widens a field turns other tracks red at the join; an edit that narrows one stays green. An allowlist entry cites its ruling or this section.

| # | guard (trigger quoted) | owner · file | root | recursion | tokens | allowlist (constant) | jointly satisfiable because |
| --- | --- | --- | --- | --- | --- | --- | --- |
| G1 | ADR-0014 §2: "No reader reads `pack` directly after this change; a guard test greps for it." | X-A1 · `tests/test_arms_guard.py` | `src/harness_bench/` | yes | `["pack"]`, `.get("pack"`, `.pack` on a cell or view row | `PACK_READERS_ALLOWED`. **E1:** `plan.py`, `board.py`, `report/pack_improvement.py`, `report/html.py`, `report/summaries.py`. **E3:** X-A3 narrows it to `plan.py` | X-C, X-E, X-H2, X-J1 and X-K1 read the arm only through `cell_arm` / `arm_pack`. The legacy readers stay listed until X-A3 migrates them. *assume:* they render a non-`on` arm id without raising. **Confirm:** X-INT renders a two-arm (`off`, `candidate`) report. **If false,** X-A3's reader migration moves into E1 |
| G2 | ADR-0017 §1: "The classification table lives in code, once, with a test that every `src/` file has a class." | X-D · `tests/test_identity.py` | `src/harness_bench/` | yes | every `*.py` path | none (`CLASSES` is the table) | section 9 lists every planned module; X-D seeds them all. An unplanned module is a seam request |
| G3 | Architecture amendment table: "ADR-0011 C5/C9 import lint · extended to the campaign, identity, power, verdict, gate and property-grader modules" | X-D · `tests/test_architecture.py` | the files marked "yes" in section 9 | no | `harness_bench.gateway`, `from .gateway`, `from harness_bench import gateway` | none | ADR-0020 §5 (pure functions) and ADR-0018 (no model call): none of them needs the gateway |
| G4 | ADR-0018 §9: "The allowlist is one constant moved to a shared grading module so the three graders cannot drift (DM7)." | X-F · `tests/test_property_grader.py` | `src/harness_bench/grade/` | yes | `HOST_ENV =` | `HOST_ENV_DEFINERS = {"grade/_env.py"}` | in E1 only X-F edits `correctness.py` and `mutation.py`; X-A1 edits only `grade/_changes.py:84` |

Not scan-shaped, but quoted so no slice paraphrases them (DC-189):
- ADR-0018 §11(b): "after every grading pass of a campaign run, and before every `bench campaign` command, `bench campaign verify` checks the campaign ledger's hash chain, that every content-addressed file's name equals its hash, and `git status --porcelain bench/campaigns bench/discrimination`". X-C owns `verify`; X-F adds the after-grading hook line (seam X-C → X-F).
- ADR-0015 §5a: "copy into a temporary sibling folder (`<name>.tmp-<pid>`), fsync the files and the folder, verify the rows against the copy, then `os.rename` it to the final name". Section 4 is its API.
- ADR-0015 §7: "each with a seeded-bug variant TLC must reject **before the build starts**". W1-J's exit evidence.
- ADR-0021 §7: "`bench status <run_id> --alarm-after <seconds>` exits non-zero, naming the cause, when the heartbeat is stale **or** `now − last_progress_at` exceeds the threshold while cells are pending". X-K2.
- ADR-0017 §7: "The engine recomputes the run-side part of the manifest when a campaign run starts and again before each `cell.launch_intent`". X-D.

## 11. HB codes reserved per track

These ids are reserved, never reused. Each W1 design confirms or drops its rows; a dropped id is retired. The phase's `errors.py` owner adds the confirmed rows in its first commit: X-D in E1, X-J1 in E2, X-K1 in E3, X-LG in E4. Existing codes are reused where the meaning is already there: `HB-RUN-004` (disk low at launch, ADR-0021 §8), `HB-RUN-005` (live run lock), `HB-USR-002`.

| code | meaning | track · phase |
| --- | --- | --- |
| HB-LED-007 | create-once conflict: a create-only file exists with different bytes (determinism defect; never overwritten) | X-B1 · E1 |
| HB-IDN-001 | engine identity drift: launching stopped; the stop event names the differing components | X-D · E1 |
| HB-IDN-002 | a `src/` file has no run/grade class | X-D · E1 |
| HB-PLN-001 | launch-balance bound violated (EV-17) | X-A1 · E1 |
| HB-PLN-002 | arm or role binding invalid (unbound role, a pack on `off`, a duplicate arm, more than one `off`) | X-A1 · E1 |
| HB-PWR-001 | power-analysis inputs invalid (names the field) | X-H1 · E1 |
| HB-CHK-001 | check output invalid | X-F · E1 |
| HB-CHK-002 | invalid (check tampered) | X-F · E1 |
| HB-CHK-003 | check exceeded its bound | X-F · E1 |
| HB-CHK-004 | grading step spans a host suspend: NOT_RECORDED, re-run next pass | X-F · E1 |
| HB-RDY-001 | no discrimination record for the current task version | X-E · E1 |
| HB-RDY-002 | the record's engine identity differs from the current one (or the baseline) | X-E · E1 |
| HB-RDY-003 | a metric differs from its declared expected value (names metric, expected, observed) | X-E · E1 |
| HB-RDY-004 | discrimination record stale against its run (`<metric> copy <a>, run <b>`) | X-E · E1 |
| HB-RDY-005 | property-task contract field missing or invalid (EV-1) | X-E · E1 |
| HB-RDY-006 | prompt states a listed latent-requirement term (names term and line) | X-E · E1 |
| HB-RDY-007 | property pair rule violated: not two tasks, or one base (DR-T1) | X-E · E1 |
| HB-RDY-008 | check declares a container runtime or a Linux-only tool | X-E · E1 |
| HB-RDY-009 | a frozen task value differs from the canonical function's output (HASH-A) | X-E · E1 |
| HB-CMP-001 | campaign lock held | X-C · E1 |
| HB-CMP-002 | command refused in the campaign's current state (names the item and an action) | X-C · E1 |
| HB-CMP-003 | campaign verify failed (chain, name ≠ hash, or a changed committed file; names it) | X-C · E1 |
| HB-CMP-004 | refused: a campaign run's `grade.lock` is held | X-C · E1 |
| HB-CMP-005 | unknown campaign id | X-C · E1 |
| HB-CMP-006 | baseline refused (ADR-0017 §3; names the unmet precondition) | X-C · E1 |
| HB-CMP-007 | defect fix refused (ADR-0017 §4: class absent, before-hash mismatch, or an unnamed component) | X-C · E1 |
| HB-CMP-008 | registration refused (pilot gate, pilot coverage, or an MDE not accepted) | X-C · E1 |
| HB-CMP-009 | pre-registration frozen: the grid has started | X-C · E1 |
| HB-LED-008 | turn `snapshot_hash` does not match its `archive_files` rows | X-J1 · E2 |
| HB-CELL-117 | `failed (archive)`: a turn snapshot copy failed after bounded retry (infrastructure) | X-J1 · E2 |
| HB-CELL-118 | `failed (coordinator crash)` (infrastructure) | X-K1 · E3 |
| HB-CELL-119 | `failed (coordinator crash between turns)` (infrastructure) | X-K1 · E3 |
| HB-RUN-008 | resume refused: the run was stopped | X-K1 · E3 |
| HB-RUN-009 | resume refused: `bench verify` failed (names the segment) | X-K1 · E3 |
| HB-PLN-003 | comparison refused: ring hashes differ (names the differences, EV-15) | X-A3 · E3 |
| HB-ALM-001 | alarm: heartbeat stale | X-K2 · E3 |
| HB-ALM-002 | alarm: progress stalled while cells are pending | X-K2 · E3 |
| HB-ALM-003 | warning: no alarm check ran within 2 × the interval | X-K2 · E3 |
| HB-CHK-005 | a check listener is not bound to `127.0.0.1` | X-LB · E4 |

## 12. Run-ledger additions (ADR-0015, ADR-0021; for the record model and `lifecycle.py`)

| event / row | fields | phase · owner |
| --- | --- | --- |
| `cell.prompt_sent` | `+ turn` (absent reads 1) | E2 · X-J1 |
| `cell.turn_ended` | `cell_id, turn, stop_reason, turn_seconds, usage` | E2 · X-J1 |
| `cell.turn_snapshot_archived` | `cell_id, turn, snapshot_hash, files, bytes, duration_ms, job_active_processes` | E2 · X-J1 |
| `archive_files` row | `+ snapshot` ∈ {`turn-<n>`, `final`} (absent reads `final`) | E2 · X-J1 |
| `run.launch_stopped` | `code: HB-IDN-001`, `diff` | E1 · X-D |
| launch span | `identity_check_ms`; E3 adds `free_bytes` | E1 · X-D; E3 · X-K1 |
| resume record | how a resume is recorded (ADR-0021 §6: "resumed n times, with each resume's time and segment id") | E3 · X-K1, designed in W1-K |

## 13. Hub files: one owner per phase

This is the authoritative copy (the plan's table is its planning record). Another track that needs a line in a hub file sends `coord request add --to <owner>`. Hand-overs between phases are joins on `main`.

| hub file | E1 | E2 | E3 | E4 |
| --- | --- | --- | --- | --- |
| `engine.py` | X-D | X-J1 | X-K1 (starts after X-J1 joins) | — |
| `cli.py` | X-C | — | X-K2 | — |
| `config.py` | X-A1 | — | X-A3 | — |
| `errors.py` | X-D | X-J1 | X-K1 | X-LG |
| `identity.py` | X-D | X-J1 | X-K1 | X-LG |
| `archive.py` | X-B2 | X-J1 | — | — |
| `views.py` | X-A1 | X-J1 | — | — |
| `ledger.py` | X-C | X-J1 | — | — |
| `plan.py` | X-A1 | X-J1 (`turns` only) | X-A3 | — |
| `grade/runner.py` | X-F | X-J2 | — | X-LG |
| `grade/property.py`, `grade/bench_check.py` | X-F | — | — | X-LB |
| `procs.py`, `egress.py` | X-F | — | — | — |
| `profiles.py` | X-E | X-J2 | — | — |
| `report/html.py` | X-H2 | — | X-A3 | — |
| `report/pack_improvement.py`, `board.py`, `report/summaries.py` | — | — | X-A3 | — |
| `status.py` | X-C | — | X-K2 | — |
| `lifecycle.py`, `models/run_lifecycle.tla` and `.cfg` | — | W1-J (model and TLC first), then X-J1 | W1-K (`NoResumeAfterStop`), then X-K1 | — |
| `bench/metrics.yaml` | X-G1 | — | X-G3 | — |
| `bench/bom.yaml` | W0 (the ten stubs); then each task track edits only its own entry | ← | ← | ← |
| `tasks/README.md` (property section) | W0; then by seam request | ← | ← | ← |
| `tests/test_<module>.py`, `tests/mutations/<module>.json` | the source module's owner in that phase | | | |
| `tests/test_architecture.py` | X-D | — | — | — |

Correction to the plan, recorded here: `plan.py` in E2 (the `turns` field) belongs to X-J1. The plan listed no E2 owner for it, but ADR-0015 §1 puts the turn hashes in the plan.

## 14. Open items this doc does not fix (each owned by one design)

| item | decided in |
| --- | --- |
| the turn-snapshot folder path (ADR-0015 §5: "the slice names the path") | W1-J |
| the bench-plan/2 label text (section 5's constraint) | W1-A |
| whether `bom.subset: full` keeps the property tasks (W0 left them in; `tests/test_plan.py` now expects 816 cells, not 576). If not, a BOM field excludes them and the count goes back to 576 | W1-A |
| whether `grading.started.grade_identity_hash` lands in E1 or E3 | W1-D |
| the synthetic agent mechanism (Inferred: a stdlib ACP fake behind `Launcher`, so no `engine.py` edit) | W1-E |
| catalog anchors, area and the scenario-7 pass-rule field name | W1-G |
| the alarm channel (ADR-0021 §7: "The channel is chosen at `/design-slice`") | W1-K |
| task bases, latent requirements, final budgets | W1-I, W1-L |

## Gate

W0 is reviewed by RV-PAT, RV-SIM, RV-TA, RV-SEC and RV-DS (plan, Order of operations step 5) in their first batch, alongside batch-a slices. A finding that changes a contract here is applied by the Coordinator before the dependent slice's gate. The author does not clear any veto.

`GATE w0-seam-contracts · pending · RV-PAT, RV-SIM, RV-TA (hard), RV-SEC (hard), RV-DS (hard) · DR-4 open (provisional (a))`
