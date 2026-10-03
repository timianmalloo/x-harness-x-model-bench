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
  - { to: review-eval-ta, rel: relates-to }
  - { to: review-eval-sec, rel: relates-to }
  - { to: review-eval-ds, rel: relates-to }
  - { to: review-eval-pat, rel: relates-to }
  - { to: review-eval-sim, rel: relates-to }
review-by: "2026-10-17"
summary: >-
  Revision 2. The one vocabulary the twelve Wave 1 design slices and the Wave 2 tracks share: the ten property-task
  ids and their BOM and task.yaml stubs, the task.yaml property and expected-value fields, the PropertyCheck input,
  result, framing and outcome precedence, create_once and the directory publish, bench-matrix/2 and bench-plan/2, the
  campaign ledger rows and the pre-registration freeze order, the identity manifest, the discrimination record, the
  catalog 0.7 metric ids under R-90, the power, verdict and gate shapes, every planned new module with its run/grade
  class, the HB codes reserved per track, the hub-file owner per phase, and the four frozen fields of every
  shared-surface guard. Ends with the disposition of every finding of the five W0 lens reviews.
---

# W0 seam contracts

**What this is.** Serial-spine item 2 of `docs/coordination/coordination-eval-campaign.md`. It fixes the *shape* of every interface that two or more slices touch, so the slices can be designed and built in parallel. A slice's design may **narrow** or **detail** anything here. It may not **widen** or **rename** it. A change that does is a seam request to the Coordinator (`coord request add --to coord-opus-e1e4`); a dispute goes to the Owner.

**Authority order.** The ADRs (0014-0021) and the spec (EV-1..EV-20) win over this doc. This doc wins over the coordination plan's descriptions of the same interfaces. Each contract below cites its ADR. Where this doc chooses something the ADRs leave open, it says **W0 decision** and gives the reason.

**Author:** Coordinator seat `coord-opus-e1e4` (Claude Opus 5.5), 2026-10-03. Revision 1 on main at `ce1aa06a`. **Revision 2** on main at `357bce48`: applies the five W0 lens reviews (`docs/design/reviews/eval-review-{ta,sec,ds,pat,sim}.md`) and R-90. Each finding's disposition is in *Review disposition* at the end. Every code claim added in revision 2 was read on `357bce48`.

**Status of the rulings this doc reads:** R-87 (the Leader drives `coord-runner`; Sonnet tracks are Agent-tool spawns), R-88 (X-A1 and X-D fall back to Sonnet while Codex is unqualified), R-89 (the E1 demo combo is `cc-opus`, k = 3; the demo pre-registration sets minimum recorded pairs ≤ 3), **R-90** (DR-4 → (a), with six conditions; section 7), R-91 (the Sonnet seat serves `claude-sonnet-5-5`). Open decision request: **DR-7** (section 7, the grid-run disagreement count). Nothing in this doc is provisional on it.

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
- `bom.subset: full` selects every non-fixture task, so it now includes these stubs. **Correction (rev 2, RV-SIM 2):** revision 1 said "a matrix run already refuses a task that is not `ready`". That is false: no status check exists in `plan.py`, `engine.py` or `cli.py` (searched on `357bce48`), and `config.py:266-315` checks status only inside `bench validate`. `tests/test_plan.py:53-57` expects 816 cells, stubs included. Grid-3 and grid-4 list their tasks explicitly, so EV-17's re-plan is unaffected (read 2026-10-03: `runs/grid-4/matrix.yaml:3`). W1-A decides the rule (section 14): `bench plan` refuses a non-`ready` task, or a BOM field keeps the stubs out of `full`.
- **Two bases per property (DR-T1, EV-1):** each property's two tasks use different codebases. The authoring track names both bases in its design.

## 2. `task.yaml`: the property-task fields

A stub carries `property.name` only. A design fills the rest. Every field below is inside the task version hash (it is a file in `tasks/<ID>/`). Validation is X-E's `readiness.py`, called by the `bench validate` command (`cli.py:77`, `cmd_validate`, after `config.validate_repo`). X-C writes that one line (seam X-E → X-C; `cli.py` is X-C's hub file in E1). **`config.py` does not import `readiness.py`** (rev 2, RV-PAT 4: a run-class module never imports a grade-class one; section 9).

```yaml
schema: bench-task/1                 # unchanged
scenario: 5
property:
  name: security                     # security | resilience | rework | no-guessing | simplicity   (exactly one, EV-1)
  latent_requirement: "<one sentence>"
  evidence_paths: ["<path that exists in the base tree>"]          # at least one (EV-1)
  latent_terms: ["<term that would state the requirement>"]       # none may appear in prompt.md (EV-1)
  primary_metric: property_check_pass                             # EV-1 requires the field; readiness checks it equals the catalog's one primary (rev 2)
  ceilings: {}                       # rework: {rework_ratio: "0.3000"}; simplicity: {size_vs_reference: "…", new_abstractions: n, new_dependencies: n}
  fault_contract: {}                 # resilience only: {timeout_ms, tolerance_ms, max_retries}  (EV-3)
expected:                            # ADR-0019 item 5; one provenance comment per value (GLD-A)
  reference: {<metric id>: <value>}  # value: an int, a decimal string at the catalog scale, or {na: "<reason>"}
  naive:     {<metric id>: <value>}
turns: ["turns/2.md"]                # rework only; turn 1 stays prompt.md (ADR-0015 §1); at most 2 turns
graded_snapshots: [turn-1]           # rework only (ADR-0015 §8)
graders: [correctness, property]     # R-90: every property task names both
```

- **`expected` semantics (EV-7, EV-11; R-90 condition 1):** the required set is exactly the **property grader's narrowed set**: `runner.applicable(catalog, task["graders"], task["property"]["name"])["property"]` (section 7). A security task declares `property_check_pass` and `exploit_probes_blocked` only. A metric of that set that `expected` omits fails readiness (HB-RDY-005). The correctness grader's metrics (`pass_at_1`, `partial_credit`) are recorded in the discrimination record's `scores` but carry no expected value (R-90 condition 1 names the set). `{na: "<reason>"}` is the only exemption, and it is the YAML form of the spec's `expected NA: <reason>`.
- **One normaliser (rev 2, RV-TA 11).** Readiness compares by exact equality after both sides pass through one function, `grade/property.py: at_scale(value, scale) -> int | Decimal`, which readiness imports (never a copy). An int-scale metric is a JSON int. A scaled metric is a string with exactly `scale` decimals (`"1.0000"`); `"1.0"`, `1` and `1.0` are refused. The scale is the catalog's (`runner._scales`, `runner.py:171`). The grader validates the check's `measures` with the same function.
- **Oracle layout (B3; ADR-0018 §1; ADR-0016 §5):** `oracle/check/` holds the check entry point and `cases.yaml` (section 3). `oracle/solutions/reference/` and `oracle/solutions/naive/` hold the solution trees. A multi-turn task holds `turn-1/` and `turn-2/` under each. `bench_check.py` is **never** authored in a task: the grader copies it in.
- `tasks/README.md` gains a *Property tasks* section with this contract (W0 writes it; afterwards changes go through a seam request).

## 3. `PropertyCheck`: the hidden-check contract (ADR-0018; owner X-F in E1, X-LB in E4)

**Declared cases**: `tasks/<ID>/oracle/check/cases.yaml`:

```yaml
schema: bench-check-cases/1
entry: check.py                      # run as: <sys._base_executable> -E -s check/<entry> ...   (rev 2, RV-SEC 9)
interface: import-host               # import-host | loopback   (E1: import-host only, until SP-LB passes; rev 2 renames in-process)
bounds_ms: {import-host: 2000, loopback: 5000}    # per-interface case bound (ADR-0018 §12); loopback: E4, unread in E1
deliverable:                         # how the check builds and starts the deliverable (ADR-0018 §7)
  build: ["<argv>"]                  # optional; spawned only through bench_check.spawn_deliverable (rev 2, RV-SEC 7)
  start: ["<argv>"]                  # the interpreter or launcher; spawned only through bench_check.spawn_deliverable
  import: "<module>:<attr>"          # import-host only: the app object the probe host imports
  config: {host_env: HB_CHECK_HOST, port_env: HB_CHECK_PORT}   # loopback only: E4, unread in E1
toolchain: [python]                  # a container runtime or a Linux-only tool fails readiness (EV-7)
env: []                              # names from _env.TOOLCHAIN_ENV only, plus HB_CHECK_* (rev 2, RV-SEC 2)
cases:
  - {id: inj-1, kind: probe, bound_ms: 2000}       # kind: probe | fault | static; fault: E4, unread in E1
```

- **Effective case bound (rev 2, RV-TA 10):** `min(case.bound_ms, bounds_ms[interface])`. An omitted `bound_ms` means the interface bound. W1-I and W1-L set each bound from the reference solution's measured duration with a stated multiplier, recorded with the task (RV-DS 4).
- **`env` (rev 2, RV-SEC 2; ADR-0018 §9):** a name is allowed only if it is in `grade/_env.py: TOOLCHAIN_ENV` (X-F defines it; a dotnet toolchain's names are `correctness.DOTNET_HOST_ENV`, imported, never copied) or starts with `HB_CHECK_`. Readiness refuses any other name, and any name in the profiles denylist (`profiles.DROP_EXACT`, `profiles.DROP_PREFIXES`), with HB-RDY-005. `spawn_deliverable(argv, env_extra)` raises on a key outside the declared `env` and `HB_CHECK_*`. Values come from the grader's allowlisted environment only, never `os.environ` read in the check.
- **`import-host` (rev 2, RV-SEC 1, blocking; ADR-0018 §1, §2, §10).** The check process **never imports agent code**. ADR-0018 §1 already says "The check starts the deliverable as its own child (so it is in the same job), only through `bench_check.spawn_deliverable`". For an importable deliverable, the check spawns a **probe host** through `spawn_deliverable`: the bench-provided `bench_check.py` run in host mode under `deliverable.start`'s interpreter. The probe host imports `deliverable.import` and answers each probe request with the **raw** response, over that child's own stdin and stdout pipes (the handle list holds exactly the child's three stdio handles; stderr goes to a file in the copy). The check decides every outcome from the raw response. So a forger in the deliverable's module body can write only into the deliverable's own response channel, as a loopback deliverable could. There is still no socket ("probes call it in process: no socket at all", ADR-0018 §2: the call is made inside the probe host). W1-F fixes the request and response shape. **Red-first test** `test_import_time_forgery_cannot_reach_result`: a fixture deliverable whose module body writes a forged `bench-check-result/1` document to `sys.stdout`, reads one byte from stdin and calls `os._exit(0)`. The grader's parsed result must never be the forged document.
- **Not built in E1:** `interface: loopback`, `bounds_ms.loopback`, `deliverable.config` and `kind: fault` keep their shape for seam stability. They are unread in E1, and W1-F does not build them (rev 2, RV-SIM 7).

**Invocation.** The property step runs in two phases, in this order (rev 2, RV-SEC 3):

1. **Tests.** `correctness.grade(ws, task_dir, oracle, out_dir, run_dir, timeout, work_dir)` (`correctness.py:196`, R-90 condition 2), once per graded tree (the final tree; for rework also the turn-1 snapshot), each in its own sub-copy `cells_root/grading/<gid>/<cid>/property/tests-<tree>/`, with `timeout = grading_step_timeout`.
2. **Check.** It starts only after every process of the tests phase has exited (W1-F names the primitive). Then the grader builds a **fresh** copy `cells_root/grading/<gid>/<cid>/property/check-run/` (ADR-0013 Am. 2): first `deliverable/` (the archived final tree, or a named snapshot), then `check/` (the oracle check) and `check/bench_check.py` (copied from `grade/bench_check.py`), copied **last**. It hashes `check/` (with `bench_check.py` and `cases.yaml`) at that moment. It starts the check in a new Job Object with the outer bound `grading_step_timeout`, with `DETACHED_PROCESS`, and with `grade/_env.py`'s environment:

```
<sys._base_executable> -E -s check/<entry> --deliverable <abs> --cases check/cases.yaml --seed <int> --evidence <out_dir>/evidence
```

- **Evidence directory (rev 2, RV-SEC 8):** `<out_dir>/evidence`, which is outside the grading copy (`grade/__init__.py:57`: `out_dir` is the grader's only write place). Evidence is egress-scanned (US-47), with canaries in class `task canary` (R-E9), before any judge or report reads it.
- **Bounds per phase (rev 2, RV-DS 13):** each phase has its own `grading_step_timeout` bound (R-90 condition 2 for each test run; ADR-0018 §5 for the check). The host-suspend rule (HB-CHK-004) applies to each phase's own span. The evidence records each span. W1-F states the measured worst case of the whole step.
- `seed = int(sha256(f"{task_version}|{cell_id}|{metric_id}").hexdigest()[:16], 16)` with `metric_id = property_check_pass` (ADR-0018 §6, recipe kept verbatim). The seed is per (cell, property check), **not per tree**: a rework cell's two test runs and its check share it (rev 2, RV-PAT 11).
- The check calls only `bench_check.spawn_deliverable(argv, env_extra)` (explicit handle list, the allowlisted environment; §9, §10; `build`, `start` and the probe host all go through it) and `bench_check.write_result(doc)` (one write, after the job holds the check alone; §10a(a)).

**Result.** Exactly one JSON document on the check's stdout (rev 2 framing, RV-DS 3):

```json
{"schema": "bench-check-result/1",
 "deliverable": "started",
 "cases": [{"id": "inj-1", "outcome": "blocked", "duration_ms": 41}],
 "measures": {}}
```

- **Framing.** The document is one line of canonical JSON ended by `\n`, at most 64 KiB. The grader reads the check's stdout line by line on its own thread from the start, so a large write never blocks the check. "No trailing bytes" (§10a(b)) is checked at EOF, after the check exits, not before the ack.
- **Acknowledgement (spike E1-S3; Acknowledged Message).** After the grader has validated and accepted the line, it writes one byte to the check's stdin and closes it. On a rejected line it closes stdin with no byte. The check exits 0 only after reading the byte. Stdin EOF with no byte means "not accepted": the check exits non-zero at once. So a rejected document never waits for the outer bound (RV-TA 4, RV-PAT 7).
- `deliverable` ∈ {`started`, `build failed`, `start failed`}. "Failed" means the step ran to its own end and failed: a non-zero build exit, a start or import that raised, or a process that exited before it was ready. A build or start still running when the outer bound fires is NA `check exceeded its bound` (rev 2, RV-DS 4).
- `outcome` ∈ {`blocked`, `exploited`, `passed`, `failed`, `timeout`}. Case ids come only from `cases.yaml`. Each case appears exactly once.
- **`measures` (rev 2, RV-SEC 5, RV-SIM 8):** a measure that is a function of `cases` is computed **by the grader** from `cases` and must not appear in `measures` (one definition): `exploit_probes_blocked` = blocked probes ÷ probes, `fault_suite_pass` = passed fault cases ÷ fault cases. `measures` carries only check-observed counts that the cases cannot express (for example `idempotency_violations`); W1-F lists which is which. A key outside the task's narrowed set, a derivable key, or a value that fails `at_scale` is `check output invalid`.

**`property_check_pass` (rev 2, RV-TA 5; R-90 condition 2; EV-1).** It is 1 iff the final tree's hidden tests pass **and** `deliverable` is `started` **and** every declared case ended `blocked` or `passed`. Any `exploited`, `failed` or `timeout` case makes it 0, and so do `build failed` and `start failed` (EV-1's measured 0). A property may narrow this by a per-property rule in W1-F or W1-L (for example a ceiling as a `static` case). Nobody may widen it. Truth-table test: reference 1, naive 0, tamper NA, did-not-build 0.

**Grader outcomes: evaluated in this order; the first matching row decides** (rev 2, RV-TA 4, blocking; RV-SEC 4). The order follows the evidence. A suspend explains everything after it, so it comes first. Interference observed before or during a bound is reported as interference, not hidden behind the bound. A document problem is judged only when the process facts are clean.

| # | condition | score row |
| --- | --- | --- |
| 1 | a host suspend gap in the phase's span | NA `host suspended`, re-run next pass (HB-CHK-004) |
| 2 | the `check/` hash differs from the hash taken before the start; or a line arrived while the check was not alone in the job, or after its exit; or more than one line | NA `invalid (check tampered)` (HB-CHK-002) |
| 3 | the outer bound fired | NA `check exceeded its bound` (HB-CHK-003) |
| 4 | a line arrived but is malformed (schema, size, case ids, `measures` keys or values) | NA `check output invalid` (HB-CHK-001) |
| 5 | any other §10a(b) failure: no line, a non-zero or abnormal exit after an accepted line, an exit before the line, or trailing bytes at EOF | NA `invalid (check tampered)` (HB-CHK-002) |
| 6 | `deliverable` is `build failed` or `start failed` | `property_check_pass` = **0**, a measured failure (EV-1) |
| 7 | otherwise | the scores, by the predicate above |

Tests: one red-first test per row, plus one per adjacent pair, to prove the order (a malformed line on a check that then hangs → row 4; a forged line plus the bound → row 2).

- **Evidence per cell:** for each tree, `hidden_tests_pass` and `hidden_tests_ms` (R-90 condition 3); per case, the outcome and `duration_ms`; the seed; the `check/` hash before and after; each phase's span.
- **W0 decision: a measured 0 carries no `Score.reason`.** `Score` allows a reason only with `value None` (`grade/__init__.py`, `Score.__post_init__`). EV-1's "0 with reason `deliverable did not build`", and the architecture's "the score's reason names the first failing case", are written into the evidence file, which `Score.evidence` points at (`<evidence file>:<line>`). `Score` does not change.
- **ADR-0018 deviations recorded here (rev 2, RV-SEC 9):** (a) the check runs under `sys._base_executable -E -s`, not "the task's pinned interpreter" (the check is stdlib only; the deliverable and the probe host run under the task's own interpreter through `deliverable.start`); (b) the one-byte acknowledgement and its framing come from spike E1-S3 and are not in the ADR; (c) the probe host's stdio are pipes owned by the check, not files. W1-F's design carries the ADR-0018 amendment note that records all three.

## 4. Crash-atomic writes: `src/harness_bench/atomic.py` (owner X-B1; consumers X-B2, X-C, X-E, X-J1, X-K1)

```python
def create_once(path: Path, data: bytes) -> bool:
    """ADR-0016 §2a. tmp = path.with_name(f"{path.name}.tmp-{os.getpid()}-{uuid4().hex}"), opened O_CREAT|O_EXCL;
    write, fsync through the write handle, close, os.link(tmp, path), unlink tmp.
    True = created; False = path existed with equal bytes (no-op).
    Different bytes: raise BenchError("HB-LED-007", ...) naming the path. Never overwrites."""

def publish_dir(final: Path, fill: Callable[[Path], T], verify: Callable[[Path], None]) -> T:
    """ADR-0015 §5a. If final exists: raise FileExistsError (checked explicitly, on every platform).
    tmp = final.with_name(f"{final.name}.tmp-{os.getpid()}-{uuid4().hex}"), created by os.mkdir (exclusive: a
    collision raises); fill(tmp) copies into the empty folder; fsync every file through its write handle;
    verify(tmp) raises unless the copy matches (it enumerates the folder and compares the file set as well as each
    file's rows); fsync the folder only when os.name == "posix"; os.rename(tmp, final).
    On any exception the tmp sibling is left for the sweep."""

def stale_temps(target: Path) -> list[Path]:
    """The `<target.name>.tmp-*` siblings, files or folders, that a sweep deletes (ADR-0021 §4). Each entry is
    lstat-ed first: a reparse point (a junction or symlink) is unlinked, never recursed into. Each deletion is logged."""
```

- **Windows branch (spike E1-NTFS, quoted):** "a directory cannot be opened for fsync at all (PermissionError), so ADR-0015 section 5a's 'fsync the folder' is POSIX-only". `publish_dir` fsyncs the folder only when `os.name == "posix"`. W1-B states the branch and its test. Each file's fsync goes through its write handle: a read-only fsync fails (spike E1-S1).
- **Temp names and the sweep (rev 2, RV-TA 6, 12; RV-DS 5, 6; RV-SEC 10; RV-PAT 6).** Both helpers name temps `<name>.tmp-<pid>-<uuid4 hex>` and create them exclusively, so PID reuse cannot fill an old folder. A resume (X-K1) sweeps `stale_temps` before it redoes a copy. A `bench campaign` command (X-C) sweeps the campaign folder and `bench/discrimination/` under `campaign.lock`. `bench campaign verify` ignores `*.tmp-*` names: they are not content-addressed records, and the sweep owns them. Test: kill between the write and the link, then verify and resume.
- **The crash window between the rename and the row append (rev 2, RV-DS 9).** The caller's one recovery rule: if `final` exists and its rows are absent, recompute the rows from the folder, compare them with the source (still in the archive root or the working copy), then append them. If `final` exists and its rows are present, verify only. W1-B and W1-J carry the test.
- Every create-only file (identity, prereg and power files; discrimination records) is written with `create_once(path, ledger.canonical(obj))`. Every archive and turn snapshot is written with `publish_dir`. There is no second helper (DM7). A hard-link failure on a volume without `os.link` is a hard error, never a silent fallback (RV-DS residual).

## 5. `bench-matrix/2` and `bench-plan/2` (ADR-0014, ADR-0016 §6; owner X-A1 in E1, X-A3 in E3)

**`bench-matrix/2`:**

```yaml
schema: bench-matrix/2
bom: {file: bench/bom.yaml, subset: [S1]}
repetitions: 3
arms:                                # 2+ arms, ids ^[a-z][a-z0-9-]{0,15}$, at most one `off`, which has no pack
  - {id: off}
  - {id: candidate, pack: {source: "<repo>", commit: "<sha>"}}   # in a ring: role arms carry no pack (bound at plan time)
comparisons: [[off, candidate]]      # optional for 2 arms; required for 3+ (the one reader rule below)
combos: [{id: cc-opus, harness: claude-code, model: claude-opus-5-5}]
ring: {tag: pilot}                   # rings only: pilot | pack-regression | comparison
```

- **Role (rev 2, RV-SIM 9; ADR-0016 §6):** a ring arm is a *role*: an arm declared with no pack (`{id: incumbent}`, `{id: candidate}`), which `bench plan --arm <role>=<source>@<commit>` binds to a pack revision. An unbound role is refused (HB-PLN-002).
- **Comparisons default: one reader rule in `plan.py`:** with 2 arms and no `comparisons`, the comparison is `[[off, other]]` if one arm is `off`, else `[[first, second]]` in file order. With 3+ arms, `comparisons` is required.

A `bench-matrix/1` file is read in memory as arms `on` (the plan's single `pack`) and `off`, in the file's order. No file is rewritten.

**`bench-plan/2`** is `bench-plan/1` with these changes:

| field | shape | phase · owner |
| --- | --- | --- |
| `schema` | `"bench-plan/2"` | E1 · X-A1 |
| `arms` | `{<arm id>: {"pack": {source, commit, revision} \| null}}` | E1 · X-A1 |
| `comparisons` | `[[reference, treatment], …]` | E1 · X-A1 |
| `launch_seed` | int, drawn once at plan time and **stored in the plan**; `cells` order = blocked randomisation by it. A confirmed plan is never re-planned under the same run id (`plan.py:365` already refuses) (rev 2, RV-DS 14) | E1 · X-A1 |
| `cells[].arm` | arm id; replaces `cells[].pack`. `cell_id` keeps the recipe byte for byte: the ingredient named `pack` carries the arm id (ADR-0014 §3). **Golden test (rev 2, RV-TA 13):** the cell ids of the committed bench-plan/1 fixtures (`tests/fixtures/ledger/heads/run/plan.json`, `tests/fixtures/ledger/c44dd2b-no-heads/run/plan.json`), recomputed by the bench-plan/2 code with arm ids `on` and `off`, are unchanged; the test is red if the ingredient dict changes | E1 · X-A1 |
| `kind` | `"measurement"` (default) \| `"discrimination"` (ADR-0016 §5) | E1 · X-A1 writes the field; X-E passes `discrimination` |
| `campaign` | absent, or `{campaign_id, prereg_hash: str \| null, identity: {hash, components}}`: written verbatim from a `build_plan` argument; plan.py imports neither campaign nor identity | E1 · X-A1 writes the field; X-C builds the block |
| `ring` | absent, or `{tag, hash}` (hash = `tree_hash` of the ring file) | E1 · X-A1 |
| `tasks.<id>.turns` | `[{n, sha256}]` for turns 2..n (US-9 per turn) | E2 · X-J1 (plan.py edit by seam to the E2 phase owner) |
| `cells[].calibration` | bool, EV-9 | E3 · X-A3 |

- **Accessors**, defined once in `plan.py`: `cell_arm(cell) -> str` (`arm`, else `pack`) and `arm_pack(plan, arm) -> dict | None` (`arms[arm].pack`; legacy: the top-level `pack` for `on`, `None` for `off`). No other reader reads `pack`, except the listed legacy readers (guard G1, section 10).
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

W1-C justifies each kind against "can the state be derived from the other rows?" (rev 2, RV-SIM 11). It may merge kinds by narrowing. It may not add one.

`campaign_id` matches `^[a-z0-9][a-z0-9-]{0,39}$` (W0 decision: a folder name that is safe on Windows and fits a label).

**Pre-registration freeze: the order (rev 2, RV-DS 1, blocking; ADR-0016 §3, EV-13).**
1. `grid.attached{run_id}` is appended under `campaign.lock` **before** the run's first `cell.launch_intent`. Attaching is refused unless the plan's `campaign.prereg_hash` equals the current `registered.prereg_hash`.
2. **W0 decision: once any grid run is attached, re-registering is refused** (HB-CMP-009), launched or not. ADR-0016 §3 allows a different hash "only while no attached grid run has a `cell.launch_intent`". This is a necessary condition, and W0 narrows it. Reason: the launch check below runs outside `campaign.lock`. Only a freeze at attach time closes the window between that check and the first launch. Before it attaches a run, the operator can still re-register freely.
3. `bench run` of a plan that carries a `campaign` block refuses (HB-CMP-010) unless the ledger, read under `campaign.lock`, holds `grid.attached` for this run id **and** its current `registered.prereg_hash` equals `plan.campaign.prereg_hash`. The check lives in `cli.py` (X-C, E1), so `plan.py` and `engine.py` still import no campaign code.
4. The freeze now reads only the campaign's own ledger, under its lock. It no longer reads another process's live `events` file (RV-DS 12 is moot).

Test: two processes. One re-registers while the other attaches and launches, in both interleavings. The ledger's registered hash always equals the hash the grid ran under.

**Locks (rev 2, RV-DS 7, 8; ADR-0018 §11(a)).**
- **Protocol.** Each side takes its **own** lock first, then try-probes the other's lock (non-blocking). If the probe finds it held, the side releases its own and refuses: `bench campaign` with HB-CMP-004 when a campaign run's `grade.lock` is held; a grading pass of a campaign run with HB-GRD-007 when `campaign.lock` is held (X-F, `grade/runner.py`; `runner.py:201` takes `grade.lock` today). Test: two processes start together; exactly one proceeds.
- **`.gitignore`.** `campaign.lock` sits in a committed folder, and `.gitignore:33` ignores only `*.jsonl.lock`. X-C adds `bench/campaigns/*/campaign.lock` to `.gitignore` in its first commit. `git status --porcelain` does not list ignored files, so `verify` reads the lock as clean.

**Content-addressed files.** Each file's bytes = `ledger.canonical(obj)`, and its name = sha256 of those bytes. Each is written through `create_once`.

| file | `schema` | body |
| --- | --- | --- |
| `identity/<hash>.json` | `bench-identity/1` | `{"schema", "components": {<component>: <str>}}`. Components per ADR-0017 §1: `src/harness_bench/<path>` → `tree_hash` of that file; `catalog`; `bom`; `prices`; `profiles/<h>`; `builds/<h>`; `uv.lock`; `tasks/<id>`; `platform` (= `sys.platform`, ADR-0017 §1: no hostname, user or path; rev 2, RV-SEC 11, with a test that no `os.environ` value and no path appears in a manifest); `python` (`"3.14.6"`). `identity_hash` = the file name. |
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

- **A second production at the same key (rev 2, RV-TA 7, RV-DS 2; ADR-0016 §4).** The body carries `run_id` and `grading_id`, so two productions never have equal bytes. `discriminate` therefore reads the key first. If no record exists, it writes through `create_once`. If one exists, it compares only `scores`, `expected` and `readiness_failures`. Equal means a confirmation: nothing is written, and the stored record keeps its first `run_id`. Different is the real determinism defect: HB-RDY-010, naming the metric, the stored value and the new value. The file is never overwritten, and HB-LED-007 keeps its meaning. Test: two runs at one key with equal scores both succeed; one differing score raises HB-RDY-010.
- **Synthetic profile (X-E):** harness id `synthetic`, profile file `bench/profiles/synthetic.yaml`, combos `synthetic-reference` and `synthetic-naive`, arm `off`, rep 1. `synthetic` joins `config.HARNESSES` through a seam request to X-A1. The profile is excluded from every leaderboard and from the qualification suite's measured set (ADR-0016 *Follow-ups*).

## 7. Catalog 0.7: metric ids (ADR-0019; owner X-G1, then X-G3) under R-90

`bench/metrics.yaml` `version: "0.7.dev"` in E1 and E2, and `"0.7"` when frozen (E3, then the Leader's `freeze_catalog.py`). ADR-0019 item 2 names **eleven** metrics: `property_check_pass` plus ten secondaries. The plan's "ten metrics" was a miscount (R-90); the plan rows are corrected in revision 2.

| id | kind | better | scale | `property:` tag | grader |
| --- | --- | --- | --- | --- | --- |
| `property_check_pass` | score | higher | int 0/1 | — (untagged: applies to every property task) | `property` |
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

- All eleven have weight 0 and source D. W1-G fixes `anchor`, `anchor_note` (R-79 forms) and the area. Scenario-7 `pass_at_1` keeps its existing id; the pass rule is a per-task `task.yaml` field that W1-G names (R-90 condition 6: untouched).
- **DR-4: ruled (a), R-90.** One `property` grader records the eleven metrics, narrowed by the task's property. The hidden tests run through `correctness.grade()`. Tasks keep `correctness`, so `pass_at_1` stays. (b) is deferred and (c) refused. The six conditions bind these slices:
  1. **One narrowing, three readers (rev 2, RV-PAT 3).** The single function is `grade/runner.py: applicable(catalog, graders, property: str | None) -> dict[str, dict[str, dict]]`. A metric with a `property:` tag applies only when the tag equals `property`. An untagged metric always applies. With `property=None`, only untagged metrics apply. This covers the runner's task-changed fallback (`runner.py:318-321`, which has no task), so a changed task gets `property_check_pass` NA `task changed` and no tagged rows. The runner passes `task["property"]["name"]` (or `None`). `readiness.py` imports this function, never a copy (section 2). Today's signature is `applicable(catalog, graders)` (`runner.py:160`); X-F changes it in E1.
  2. One definition of "hidden tests pass": `correctness.grade(...)` (section 3), per graded tree.
  3. **The double run is measured; its disagreement is a finding (rev 2, RV-TA 9, RV-DS 10, RV-PAT 10).** The property evidence records `hidden_tests_pass` and `hidden_tests_ms` per tree (section 3). One function, X-E's `readiness.hidden_test_disagreements(run_dir, grading_id) -> list[str]` (cell ids), reads the pass **after both graders have written**. It compares the final tree's `hidden_tests_pass` with the pass's own `pass_at_1` row for the same cell. The grader never reads another grader's output (that is the (c) coupling R-90 refused). `gates.pilot` takes that list as an input (section 8) and emits one `GateItem(kind="hidden-tests-nondeterministic", ident=<cell_id>)` per cell. **DR-7 (open, to the Owner):** whether grid runs also surface the count (the EV-20 header line, X-H2), or the pilot gate alone carries it, as R-90 states. Until it is ruled, the function exists and the pilot uses it. Nothing is built for the grid.
  4. The strategy helpers (`grade/rework.py`, `grade/noguess.py`, `grade/diffstats.py`) are called by `property.grade_cell` and never registered in `GRADERS`.
  5. W1-G's design carries the dispatch-rule amendment text for `design-phase3-graders`, with the red test: a security task graded by `property` yields rows for exactly `property_check_pass` and `exploit_probes_blocked`, and GradedOncePerPass is green.
  6. Scenario-7 `pass_at_1` is untouched.

## 8. Power, verdicts, dominance, gates (ADR-0020; owner X-H1, section 3 X-H2)

Pure functions with no I/O. The campaign stores inputs only (ADR-0020 §5).

```python
# power.py
def analyse(inputs: Mapping) -> Mapping[str, PowerResult]      # property -> result; same inputs => same outputs
#   inputs (bench-power-inputs/1): population {description, exclusions}, source_run_ids, alpha, power,
#     correction {method: bonferroni|holm|none, m}, pairing_unit, harnesses, comparisons,
#     properties {<property>: {primary_metric, tasks, control_rate | "assumed", discordance, sd, rep_spread, mde}},
#     mean_wall_per_cell_s, mean_tokens_per_cell
#   PowerResult: alpha, power, mde, pairing_unit, correction,
#     required_pairs: [{harness, comparison: [ref, treat], n}]   (rev 2, RV-PAT 9: rows, so the result serialises as JSON)
#     reps_per_task, cells, hours, tokens, assumed: [input names]

# verdicts.py
class VerdictLabel(StrEnum): BETTER = "better"; WORSE = "worse"; NO_DIFFERENCE = "no difference ≥ MDE"
    UNDERPOWERED = "inconclusive (underpowered)"; NOT_RECORDED = "inconclusive (not recorded)"   # rev 2, RV-PAT 8
@dataclass(frozen=True)
class Pair: task: str; rep: int; ref: Decimal; treat: Decimal; ref_tokens: int; treat_tokens: int; ref_wall_ms: int; treat_wall_ms: int
def verdict(prop: str, harness: str, comparison: tuple[str, str], pairs: Sequence[Pair],
            excluded: Sequence[tuple[str, str]], prereg: Mapping, seed: int, resamples: int) -> Verdict
#   Verdict: label: VerdictLabel, effect, interval (lo, hi), per_task {task: (effect, lo, hi)}, both_tasks: bool | None,
#     n_pairs, excluded [(cell_id, reason)], token_ratio (r, lo, hi), wall_ratio,
#     statement: "A dominates B" | "better at ×<r> tokens" | None
#   verdict sorts pairs by (task, rep) before any use, so input order never changes a resample (rev 2, RV-DS 11)
#   streams: stats.rng(seed, key)
def seed_for(prereg_hash: str, prop: str, harness: str, comparison: tuple[str, str]) -> int
#   int(sha256(f"{prereg_hash}|{prop}|{harness}|{ref}|{treat}").hexdigest()[:16], 16): one seed per verdict, valid
#   across several attached runs (rev 2, RV-DS 11; replaces revision 1's "the plan's launch_seed")

# gates.py
def pilot(view, hidden_test_disagreements: Sequence[str]) -> list[GateItem]   # GateItem(kind, ident, detail); empty = pass (EV-14)
#   kinds: W1-H enumerates them; "hidden-tests-nondeterministic" is fixed here (section 7, R-90 condition 3)
def pack_regression(view, mde: Mapping[str, Decimal]) -> Mapping[str, str]  # "regression signal" | "no regression detected at <MDE>"
```

`Pair` carries one numeric type: an int-scale metric is `Decimal(0)` or `Decimal(1)`. W1-H may group `verdict`'s inputs into a frozen parameter object by narrowing. It may not change what they mean.

`report/campaign_section.py` (X-H2) renders a `Verdict` list plus the EV-20 header from the ledger reader `campaign.read(campaign_id) -> CampaignState` (X-C). Until X-C joins, it builds against fixtures of that shape.

## 9. Planned new modules and their run / grade class (ADR-0017 §1; X-D seeds them all in E1)

The rule (W0 decision, for the new modules only; rev 2, RV-SIM 4): **run** if a change to the module can alter a *measured* cell's behaviour or a measured run's plan, which means it sits on a measured cell's launch or execution path or builds a measurement plan. Otherwise **grade**. Grade is the conservative default: a grade-side change withholds verdicts until a re-grade (ADR-0017 §6), while a run-side change makes runs ineligible and forces a re-run (§5). A run-class module never imports a grade-class module (rev 2, RV-PAT 4: this is why `config.py` does not import `readiness.py`, section 2). **Consequence for W1-D to rule on at its gate (RV-SIM 4):** `campaign.py`, `readiness.py`, `alarm.py` and `gates.py` change no cell and no score, but they decide admission, eligibility and what a verdict shows, so the grade class is correct for them, and each edit to them during a campaign costs a recorded fix and a re-grade. W1-D states whether that cost is acceptable or proposes a narrower rule. A third class outside the identity would amend ADR-0017 §1 ("every `src/` file has a class") and needs an Owner request; W0 does not make one.

W1-D reviews the whole table (ADR-0017: "the run/grade classification is load-bearing and needs review at the gate"). A module not in this table needs a seam request to that phase's `identity.py` owner.

| module | class | track · phase | in the C5/C9 import-lint set (G3) |
| --- | --- | --- | --- |
| `src/harness_bench/atomic.py` | run | X-B1 · E1 | — |
| `src/harness_bench/identity.py` | run | X-D · E1 | yes |
| `src/harness_bench/campaign.py` | grade | X-C · E1 | yes |
| `src/harness_bench/power.py` | grade | X-H1 · E1 | yes |
| `src/harness_bench/verdicts.py` | grade | X-H1 · E1 | yes |
| `src/harness_bench/gates.py` | grade | X-H1 · E1 | yes |
| `src/harness_bench/discriminate.py` | grade (rev 2: it plans only synthetic discrimination runs, never a measured cell) | X-E · E1 | — |
| `src/harness_bench/readiness.py` | grade | X-E · E1 | — |
| `src/harness_bench/synthetic_agent.py` (the synthetic "agent"; W1-E may move it within `src/harness_bench/`, by seam) | grade (rev 2: it runs only in synthetic cells) | X-E · E1 | — |
| `src/harness_bench/grade/property.py` | grade | X-F · E1 | yes |
| `src/harness_bench/grade/bench_check.py` | grade | X-F · E1 | yes, and stdlib only (G3) |
| `src/harness_bench/grade/_env.py` | grade | X-F · E1 | yes |
| `src/harness_bench/report/campaign_section.py` | grade | X-H2 · E1 | — |
| `src/harness_bench/grade/rework.py` (strategy helper, R-90 condition 4) | grade | X-J2 · E2 | — |
| `src/harness_bench/resume.py` | run | X-K1 · E3 | — |
| `src/harness_bench/alarm.py` | grade | X-K2 · E3 | — |
| `src/harness_bench/grade/noguess.py` (strategy helper) | grade | X-LG · E4 | — |
| `src/harness_bench/grade/diffstats.py` (strategy helper) | grade | X-LG · E4 | — |

`identity.py` is in the lint set because ADR-0011 Am. 1 names "the campaign, identity, power, verdict, gate and property-grader modules". The strategy helpers stay separate files even though `property.grade_cell` is their only caller (rev 2, RV-SIM 12 rejected): separate files let X-J2 (E2) and X-LG (E4) build without editing `grade/property.py`, which is X-F's hub file in E1 and X-LB's in E4.

## 10. Guards over shared surfaces: the four frozen fields (GO14a)

Each guard's doc comment states these four fields verbatim, with a **named allowlist constant**. The clause it discharges carries the same qualifier. A later edit that widens a field turns other tracks red at the join; an edit that narrows one stays green. An allowlist entry cites its ruling or this section. **A guard lands in the same commit as the sweep that makes it green, with its red-first fixture** (rev 2, RV-TA 1).

| # | guard (trigger quoted) | owner · file | root | recursion | tokens | allowlist (constant) | jointly satisfiable because |
| --- | --- | --- | --- | --- | --- | --- | --- |
| G1 | ADR-0014 §2: "No reader reads `pack` directly after this change; a guard test greps for it." | X-A1 · `tests/test_arms_guard.py` | `src/harness_bench/`, `*.py` only (rev 2: `report/assets/report.js:79,147` read `dataset.pack`, an HTML attribute, not a cell) | yes | `["pack"]`, `.get("pack"`, `\.pack\b` | `PACK_READERS_ALLOWED`. **E1** (rev 2, RV-TA 1): `plan.py`, `board.py`, `report/pack_improvement.py`, `report/html.py`, `report/summaries.py`, `report/cli_table.py`, `report/context_growth.py`. **E3:** X-A3 narrows it to `plan.py` | Every other reader found on `357bce48` is **migrated by X-A1 in the guard's commit**: `views.py:525` (`pack=cell["pack"]` → `cell_arm(cell)`; X-A1's hub file), `grade/_changes.py:84` (`cell.get("pack") != "on"`), and `cli.py:145-148` `_workspace_builder` (`cell["pack"]`, `p["pack"]` → `arm_pack(plan, cell_arm(cell))`; section 13 gives X-A1 this one function in X-C's hub file). X-C, X-E, X-H2, X-J1 and X-K1 read the arm only through `cell_arm` / `arm_pack`. The listed legacy readers read the view row's `pack` attribute, which `views.py` fills with the arm id. *assume:* they render a non-`on` arm id without raising. **Confirm:** X-INT renders a two-arm (`off`, `candidate`) report. **If false,** X-A3's reader migration moves into E1 |
| G2 | ADR-0017 §1: "The classification table lives in code, once, with a test that every `src/` file has a class." | X-D · `tests/test_identity.py` | `src/harness_bench/` | yes | every `*.py` path | none (`CLASSES` is the table) | section 9 lists every planned module; X-D seeds them all. An unplanned module is a seam request |
| G3 | Architecture amendment table: "ADR-0011 C5/C9 import lint · extended to the campaign, identity, power, verdict, gate and property-grader modules" | X-D · `tests/test_architecture.py` | the files marked "yes" in section 9 | no | (rev 2, RV-TA 3) every import **resolved through the existing AST resolver** (`tests/test_architecture.py:98-99`, which resolves `node.level`): a resolved target `harness_bench.gateway` or under it. Red fixtures: `from ..gateway import x`, `import harness_bench.gateway as g`, `from harness_bench import gateway`. (rev 2, RV-SEC 12) `grade/bench_check.py`: any resolved target outside the standard library | none | ADR-0020 §5 (pure functions) and ADR-0018 (no model call): none of them needs the gateway. `bench_check.py` runs inside the grading copy beside agent code and is copied alone, so it can import nothing from `harness_bench` |
| G4 | ADR-0018 §9: "The allowlist is one constant moved to a shared grading module so the three graders cannot drift (DM7)." | X-F · `tests/test_property_grader.py` | `src/harness_bench/grade/` for token 1; `grade/property.py`, `grade/bench_check.py`, `grade/_env.py` for token 2 | yes | (rev 2, RV-TA 2, RV-SIM 3, RV-SEC 6) token 1: regex `\bHOST_ENV\s*=` (word-bounded, so `DOTNET_HOST_ENV = (` at `correctness.py:49` and `mutation.py:39` does not match); token 2: `os.environ` | `HOST_ENV_DEFINERS = {"grade/_env.py"}` (token 1); `ENVIRON_READERS = {"grade/_env.py"}` (token 2: only `_env.py` reads `os.environ`, to build the allowlisted environment) | In E1 only X-F edits `correctness.py` and `mutation.py`: each imports `HOST_ENV` from `_env.py`, and `mutation.py`'s `__all__` keeps re-exporting the name (a string, so no match). `DOTNET_HOST_ENV` **stays where it is**: the two tuples differ (`mutation.py:39-42` adds `PROCESSOR_ARCHITECTURE`), so merging them would change a grader's environment. That is a separate finding, not this guard. X-A1 edits only `grade/_changes.py:84` |

Not scan-shaped, but quoted so no slice paraphrases them (DC-189):
- ADR-0018 §11(b): "after every grading pass of a campaign run, and before every `bench campaign` command, `bench campaign verify` checks the campaign ledger's hash chain, that every content-addressed file's name equals its hash, and `git status --porcelain bench/campaigns bench/discrimination`". X-C owns `verify`; X-F adds the after-grading hook line (seam X-C → X-F).
- ADR-0018 §9 (rev 2, RV-SEC 6): "**Test (red first):** `test_property_check_env_excludes_credentials` sets those four names in the grader's environment, runs a fixture check whose fixture deliverable writes its own `os.environ` keys to its evidence file, and asserts that neither the check's nor the deliverable's environment contains any of them." X-F. It is the runtime half of G4: `env=None` or `{**os.environ}` passes a token scan and fails this test.
- ADR-0015 §5a: "copy into a temporary sibling folder (`<name>.tmp-<pid>`), fsync the files and the folder, verify the rows against the copy, then `os.rename` it to the final name". Section 4 is its API: `verify` is the hook for "verify the rows against the copy" (rev 2, RV-PAT 5), and the uuid suffix narrows the `<pid>` name.
- ADR-0015 §7: "each with a seeded-bug variant TLC must reject **before the build starts**". W1-J's exit evidence.
- ADR-0021 §7: "`bench status <run_id> --alarm-after <seconds>` exits non-zero, naming the cause, when the heartbeat is stale **or** `now − last_progress_at` exceeds the threshold while cells are pending". X-K2.
- ADR-0017 §7: "The engine recomputes the run-side part of the manifest when a campaign run starts and again before each `cell.launch_intent`". X-D.

## 11. HB codes reserved per track

These ids are reserved, never reused. Each W1 design confirms or drops its rows; a dropped id is retired. **Merge preference (rev 2, RV-SIM 10):** a design merges rows that share the operator's action into one code, with the cause named in the message, and retires the rest. The phase's `errors.py` owner adds the confirmed rows in its first commit: X-D in E1, X-J1 in E2, X-K1 in E3, X-LG in E4. Existing codes are reused where the meaning is already there: `HB-RUN-004` (disk low at launch, ADR-0021 §8), `HB-RUN-005` (live run lock), `HB-USR-002`, `HB-GRD-001` (grade lock held).

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
| HB-GRD-007 | grading pass of a campaign run refused: `campaign.lock` is held (rev 2, RV-DS 8) | X-F · E1 |
| HB-RDY-001 | no discrimination record for the current task version | X-E · E1 |
| HB-RDY-002 | the record's engine identity differs from the current one (or the baseline) | X-E · E1 |
| HB-RDY-003 | a metric differs from its declared expected value (names metric, expected, observed) | X-E · E1 |
| HB-RDY-004 | discrimination record stale against its run (`<metric> copy <a>, run <b>`) | X-E · E1 |
| HB-RDY-005 | property-task contract field missing or invalid (EV-1), including a check `env` name outside the allowlist | X-E · E1 |
| HB-RDY-006 | prompt states a listed latent-requirement term (names term and line) | X-E · E1 |
| HB-RDY-007 | property pair rule violated: not two tasks, or one base (DR-T1) | X-E · E1 |
| HB-RDY-008 | check declares a container runtime or a Linux-only tool | X-E · E1 |
| HB-RDY-009 | a frozen task value differs from the canonical function's output (HASH-A) | X-E · E1 |
| HB-RDY-010 | a discrimination re-run at an existing key disagrees with the stored record (determinism defect; names metric, stored, new) (rev 2, RV-DS 2) | X-E · E1 |
| HB-CMP-001 | campaign lock held | X-C · E1 |
| HB-CMP-002 | command refused in the campaign's current state (names the item and an action) | X-C · E1 |
| HB-CMP-003 | campaign verify failed (chain, name ≠ hash, or a changed committed file; names it) | X-C · E1 |
| HB-CMP-004 | refused: a campaign run's `grade.lock` is held | X-C · E1 |
| HB-CMP-005 | unknown campaign id | X-C · E1 |
| HB-CMP-006 | baseline refused (ADR-0017 §3; names the unmet precondition) | X-C · E1 |
| HB-CMP-007 | defect fix refused (ADR-0017 §4: class absent, before-hash mismatch, or an unnamed component) | X-C · E1 |
| HB-CMP-008 | registration refused (pilot gate, pilot coverage, or an MDE not accepted) | X-C · E1 |
| HB-CMP-009 | pre-registration frozen: a grid run is attached (rev 2) | X-C · E1 |
| HB-CMP-010 | campaign run refused: the run is not attached, or its plan's `prereg_hash` is not the registered one (rev 2, RV-DS 1) | X-C · E1 |
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
| `cli.py` | X-C, except the function `_workspace_builder` (X-A1, the G1 migration; rev 2) | — | X-K2 | — |
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
| `report/pack_improvement.py`, `board.py`, `report/summaries.py`, `report/cli_table.py`, `report/context_growth.py` | — | — | X-A3 | — |
| `status.py` | X-C | — | X-K2 | — |
| `.gitignore` (the `campaign.lock` line) | X-C | — | — | — |
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
| how stubs are kept out of a measurement: `bench plan` refuses a non-`ready` task, or a BOM field keeps them out of `full` (then `tests/test_plan.py` goes back to 576 cells). Today nothing refuses them (section 1) | W1-A |
| whether `grading.started.grade_identity_hash` lands in E1 or E3 | W1-D |
| the run/grade cost of the grade-class tooling modules (section 9) | W1-D |
| the synthetic agent mechanism (Inferred: a stdlib ACP fake behind `Launcher`, so no `engine.py` edit) | W1-E |
| catalog anchors, area and the scenario-7 pass-rule field name | W1-G |
| `TOOLCHAIN_ENV`; the probe-host request and response shape; the primitive that confirms the tests phase has no live process; which measures are check-observed (section 3); the per-property narrowing of `property_check_pass`, confirmed by its truth-table test; the ADR-0018 amendment note | W1-F |
| the `GateItem` kinds beyond `hidden-tests-nondeterministic` | W1-H |
| which ledger kinds can be derived (section 6) | W1-C |
| the alarm channel (ADR-0021 §7: "The channel is chosen at `/design-slice`") | W1-K |
| task bases, latent requirements, final budgets, case bounds from measured reference durations, offline build pinning (a build reaches no package index; network reach stays ADR-0018's accepted residual) | W1-I, W1-L |

## Gate

W0 revision 1 was reviewed by RV-PAT, RV-SIM, RV-TA, RV-SEC and RV-DS (plan, Order of operations step 5). Revision 2 applies every blocking finding and every major finding it accepts. Each finding's disposition is below. Revision 2 goes back to the three blocking reviewers (RV-TA, RV-SEC, RV-DS). The author does not clear any veto.

**Trace requirement (rev 2, RV-TA 14).** Each slice design maps every W0 contract it implements to a named test (red first), and the Test Architect checks that map at the slice's gate.

`GATE w0-seam-contracts · rev 2 · pending re-review · RV-TA (hard), RV-SEC (hard), RV-DS (hard); RV-PAT and RV-SIM PASS WITH CONDITIONS, conditions applied · DR-4 ruled (R-90) · DR-7 open (grid disagreement count; nothing built until ruled)`

## Review disposition

One row per finding id per lens. *Accepted in part* names the rejected part and why. "Section changed" is the section of this doc that carries the change.

| lens · # | severity | disposition | section changed | reason (when not fully accepted) |
| --- | --- | --- | --- | --- |
| TA 1 | blocking | accepted | 10 G1, 13 | — the E1 allowlist gains `cli_table.py` and `context_growth.py`; `views.py`, `_changes.py` and `cli.py` `_workspace_builder` are migrated by X-A1 in the guard's commit |
| TA 2 | major | accepted | 10 G4 | — word-bounded token; `DOTNET_HOST_ENV` stays where it is (the two tuples differ) |
| TA 3 | major | accepted | 10 G3 | — the AST resolver handles `node.level` (`test_architecture.py:99`, read) |
| TA 4 | blocking | accepted | 3 (outcome order, framing, ack) | — the order is suspend, interference, bound, malformed, other §10a(b), did-not-build, score; stdin is closed on a rejected line |
| TA 5 | major | accepted | 3 (`property_check_pass`), 14 | — |
| TA 6 | major | accepted | 4 | — |
| TA 7 | major | accepted | 6 (discrimination record), 11 (HB-RDY-010) | — |
| TA 8 | major | accepted | 2 | — |
| TA 9 | major | accepted | header, 7, 8, Gate | — |
| TA 10 | minor | accepted | 3 | — |
| TA 11 | minor | accepted | 2 (`at_scale`) | — |
| TA 12 | minor | accepted | 4 | — |
| TA 13 | minor | accepted | 5 | — the fixtures are the committed bench-plan/1 plans; `runs/grid-4` is not tracked |
| TA 14 | minor | accepted | Gate | — |
| SEC 1 | blocking | accepted | 3 (`import-host`) | — the check never imports agent code; a probe host child does |
| SEC 2 | major | accepted | 3 (`env`), 11 (HB-RDY-005) | — |
| SEC 3 | major | accepted | 3 (two phases) | — |
| SEC 4 | major | accepted | 3 (outcome row 2) | — |
| SEC 5 | minor | accepted | 3 (`measures`) | — |
| SEC 6 | major | accepted | 10 G4, quote list | — |
| SEC 7 | major | accepted in part | 3, 14 | `build` goes through `spawn_deliverable` (accepted). Rejected: "readiness rejects a build that needs a package index", because readiness cannot observe a build's network reach. The task declares an offline build (W1-I), and network reach stays ADR-0018's accepted residual |
| SEC 8 | minor | accepted | 3 | — |
| SEC 9 | minor | accepted | 3 (interpreter flags, deviations) | — `-E -s`, not `-I`: `-I` drops the script folder from `sys.path`, so `import bench_check` would fail; the amendment note goes to W1-F |
| SEC 10 | minor | accepted | 4 | — |
| SEC 11 | minor | accepted | 6 | — ADR-0017 §1 already says `sys.platform` |
| SEC 12 | minor | accepted | 9, 10 G3 | — |
| DS 1 | blocking | accepted | 6 (freeze order), 11 (HB-CMP-009, 010) | — W0 narrows ADR-0016 §3: attach freezes |
| DS 2 | major | accepted | 6, 11 | — option (a) |
| DS 3 | major | accepted | 3 (framing) | — |
| DS 4 | major | accepted in part | 3 (bounds, `deliverable`) | A build or start cut by the outer bound is HB-CHK-003 (accepted). Bounds are set from measured reference durations (accepted). Rejected: the automatic re-run of a `timeout` case: EV-3 makes a hang a measured failure; a re-run hides intermittent hangs, doubles the worst case and is not idempotent against a stateful deliverable; load-to-arm coupling is covered by blocked randomisation (ADR-0014 §4) and is measured through each case's `duration_ms` |
| DS 5 | major | accepted | 4 | — |
| DS 6 | major | accepted | 4 | — |
| DS 7 | major | accepted | 6, 13 | — `.gitignore:33` read |
| DS 8 | major | accepted | 6, 11 (HB-GRD-007) | — |
| DS 9 | major | accepted | 4 | — |
| DS 10 | major | accepted in part | 7 (condition 3) | The disagreement is derived by one function after the pass, and the pilot gate names it (accepted). Rejected: recording `hidden_tests_agree` in the property grader's own evidence: the grader would have to read the correctness grader's output in the same pass, which is the (c) coupling R-90 refused. Counting it in grid runs widens X-H2: **DR-7** to the Owner |
| DS 11 | major | accepted | 8 | — |
| DS 12 | minor | accepted (moot) | 6 | — the freeze no longer reads `runs/` events |
| DS 13 | minor | accepted | 3 (bounds per phase) | — |
| DS 14 | minor | accepted | 5 | — `plan.py:365` already refuses re-confirming |
| PAT 1 | major | accepted | header, 7, Gate | — |
| PAT 2 | major | accepted | 2 | — |
| PAT 3 | major | accepted | 7 (condition 1) | — `runner.py:160` and `:318-321` read |
| PAT 4 | major | accepted in part | 2, 9 | `config.py` no longer imports `readiness.py`: the hook moves to `cli.py`'s validate command (accepted). Rejected: "class follows the strictest importer" as a general G2 rule: `cli.py` imports `grade.runner` and `report.*` at module level (read), so the rule would turn every grade module into a run module, and the guard would be red on arrival (GO14a). W0 states the narrower rule: no run-class module imports a grade-class one |
| PAT 5 | major | accepted | 4, 10 quote | — the `verify` hook |
| PAT 6 | minor | accepted | 4 | — |
| PAT 7 | minor | accepted | 3 | — |
| PAT 8 | minor | accepted in part | 8 | `VerdictLabel(StrEnum)` and a single `Decimal` in `Pair` (accepted). The parameter object is left to W1-H as a narrowing, not fixed here |
| PAT 9 | minor | accepted | 8 | — |
| PAT 10 | minor | accepted | 7, 8 | — |
| PAT 11 | minor | accepted | 3 | — |
| PAT 12 | nit | no change | — | the reviewer confirmed the decision |
| PAT 13 | nit | no change | — | the reviewer confirmed the signature |
| SIM 1 | major | accepted | header, 7, Gate | — |
| SIM 2 | major | accepted | 1, 14 | — no status check found in `plan.py`, `engine.py` or `cli.py` |
| SIM 3 | major | accepted | 10 G4 | — |
| SIM 4 | major | accepted in part | 9, 14 | `discriminate.py` and `synthetic_agent.py` move to grade, and the consequence goes to W1-D (accepted). Rejected: a third `tooling` class. These modules decide admission, eligibility and what a verdict shows, so excluding them from the identity would let a change alter a verdict outside the freeze; it would also amend ADR-0017 §1 |
| SIM 5 | minor | accepted in part | 2 | EV-1 requires `task.yaml` to name a primary metric (`enterprise-evaluation.md:233`), so the field stays. Readiness checks it equals `property_check_pass` |
| SIM 6 | minor | rejected | — | ADR-0018 §6 states the recipe with `metric_id`; dropping it creates a second definition of the seed |
| SIM 7 | minor | accepted | 3 | — marked "E4, unread in E1" and kept for seam stability |
| SIM 8 | minor | accepted | 3 | — the protocol is inline; `measures` no longer repeats `cases` |
| SIM 9 | minor | accepted in part | 5 | `role` is defined and the default is one reader rule (accepted). Rejected: "comparisons always explicit": that breaks the bench-matrix/1 upcast, which has no `comparisons` |
| SIM 10 | minor | accepted | 11 | — |
| SIM 11 | minor | accepted | 6, 14 | — W1-C justifies the kinds |
| SIM 12 | minor | rejected | 9 | one file per helper keeps X-J2 and X-LG out of X-F's and X-LB's hub file |
| SIM 13 | n/a | no change | — | the reviewer confirmed the decision |
