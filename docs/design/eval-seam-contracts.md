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
  Revision 4 (the batch-b seam answers and the RV-PAT, RV-SIM, RV-SEC and RV-DS cross-slice findings on W1-B, W1-C, W1-D and
  W1-H; rev-4 change table and the delta re-read list at the end; rev 3's table kept). The one vocabulary the twelve Wave 1 design slices and the Wave 2 tracks share: the ten property-task
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

**Author:** Coordinator seat `coord-opus-e1e4` (Claude Opus 5.5), 2026-10-03. Revision 1 on main at `ce1aa06a`. **Revision 2** on main at `357bce48`: applies the five W0 lens reviews (`docs/design/reviews/eval-review-{ta,sec,ds,pat,sim}.md`) and R-90. Each finding's disposition is in *Review disposition* at the end. Every code claim added in revision 2 was read on `357bce48`. **Revision 3** on branch `design/eval-w0-rev3` (base `e466acb5`): answers the Wave 1 seam requests and the seam findings of the Wave 1 lens reviews, and records R-93 and R-94. Each change is in the *Revision 3 change table* at the end, by seam id and section. Rev-3 text is marked "(rev 3, <seam>)". Code claims added in rev 3 are the requesting slices' (each cites its spike or line); the Coordinator re-read only the lines named in this table: `grade/runner.py:108-112,161-168`, `config.py:135-176`, `bench/metrics.yaml:45`. **Revision 4** on branch `coord/eval-w0-rev4-wave2` (base `9c9056df`, author `coord-opus-e1e4`, Coordinator session #4): answers the seven seam requests addressed to the Coordinator after rev 3 (W1-B rev 2, W1-C, W1-D rev 2, W1-H, W1-J) and the cross-slice findings of RV-PAT, RV-SIM, RV-SEC and RV-DS on W1-C and W1-H, and records R-95 and R-96. Each change is in the *Revision 4 change table* at the end; rev-4 text is marked "(rev 4, <seam>)". Code lines the Coordinator re-read for rev 4: `ledger.py:43` (bool refused), `cli.py:48-49` (`_exit_for`), `oslock.py:79-91` (`is_held`), `workspace.py:89-113` (`RENAME_BACKOFF`, `_land`), `tools/check_models.py:36-69,116-137`. Every other code claim added in rev 4 is the requesting design's or review's, cited.

**Status of the rulings this doc reads:** R-87 (the Leader drives `coord-runner`; Sonnet tracks are Agent-tool spawns), R-88 (X-A1 and X-D fall back to Sonnet while Codex is unqualified), R-89 (the E1 demo combo is `cc-opus`, k = 3; the demo pre-registration sets minimum recorded pairs ≤ 3), **R-90** (DR-4 → (a), with six conditions; section 7), R-91 (the Sonnet seat serves `claude-sonnet-5-5`), R-92 (Grok re-qualification), **R-93** (DR-7: grid runs show the hidden-test disagreement count as a warning line in report section 3; section 7), **R-94** (DR-8: `telemetry/*` is run class; `gateway` is a grade-side identity component; section 9). **R-95** (DR-9: the `also_graded_by` owner rule; R-90 conditions 1 and 6 amended; section 7), **R-96** (DR-10: `holm` is sized and levelled at `alpha/m`; R-93's not-recorded state; ADR-0020 *Amendment 1*; section 8). No decision request against this doc is open (rev 4).

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
- `bom.subset: full` selects every non-fixture task, so it now includes these stubs. **Correction (rev 2, RV-SIM 2):** revision 1 said "a matrix run already refuses a task that is not `ready`". That is false: no status check exists in `plan.py`, `engine.py` or `cli.py` (searched on `357bce48`), and `config.py:266-315` checks status only inside `bench validate`. `tests/test_plan.py:53-57` expects 816 cells, stubs included. Grid-3 and grid-4 list their tasks explicitly, so EV-17's re-plan is unaffected (read 2026-10-03: `runs/grid-4/matrix.yaml:3`). W1-A decides the rule (section 14): `bench plan` refuses a non-`ready` task, or a BOM field keeps the stubs out of `full`. **Decided (rev 3, SR-1; W1-A 3.5):** `build_plan` refuses, by plan kind. A measurement plan refuses a task that is not `ready`; a discrimination plan refuses a `stub` (it admits `draft`, because a task becomes `ready` only through its discrimination record). The refusal is HB-PLN-004 and names every offending task with its status. `expand` is unchanged, so `tests/test_plan.py`'s 816 cells stay true.
- **Two bases per property (DR-T1, EV-1):** each property's two tasks use different codebases. The authoring track names both bases in its design.

## 2. `task.yaml`: the property-task fields

A stub carries `property.name` only. A design fills the rest. Every field below is inside the task version hash (it is a file in `tasks/<ID>/`). Validation is X-E's `readiness.py`, called by the `bench validate` command (`cli.py:77`, `cmd_validate`, after `config.validate_repo`). X-C writes that one line (seam X-E → X-C; `cli.py` is X-C's hub file in E1). **`config.py` does not import `readiness.py`** (rev 2, RV-PAT 4: a run-class module never imports a grade-class one; section 9).

```yaml
schema: bench-task/1                 # unchanged
scenario: 5
property:
  name: security                     # one of config.PROPERTY_NAMES: security | resilience | rework | no-guessing | simplicity   (exactly one, EV-1; rev 3)
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
entry: check.py                      # run as: <sys._base_executable> -S check/<entry> ...   (rev 2, RV-SEC 9; W1-F seam)
interface: in-process                # in-process | loopback   (E1: in-process only, until SP-LB passes; rev 2 redefines in-process)
bounds_ms: {in-process: 2000, loopback: 5000}     # per-interface case bound (ADR-0018 §12); loopback: E4, unread in E1
app: {module: "<module>", attr: "<attr>", kind: callable}      # in-process only: what the probe host imports; kind: callable | wsgi (both built in E1, rev 3)
#   optional (rev 3, req-01M41DPBSM9): factory: true      -> the host calls attr(**args) to build the app
#                                      args: {<name>: <JSON value>}   string values may use {state_dir}
#                                      paths: ["<rel>"]   relative to the deliverable root; added to sys.path after it
deliverable:                         # how the check builds and starts the deliverable (ADR-0018 §7)
  build: ["<argv>"]                  # optional; spawned only through bench_check.spawn_deliverable (rev 2, RV-SEC 7)
  start: ["<argv>"]                  # loopback: the process; spawned only through bench_check.spawn_deliverable
  config: {host_env: HB_CHECK_HOST, port_env: HB_CHECK_PORT}   # loopback only: E4, unread in E1
toolchain: [python]                  # a container runtime or a Linux-only tool fails readiness (EV-7)
env: []                              # names from _env.TOOLCHAIN_ENV only, plus HB_CHECK_* (rev 2, RV-SEC 2)
cases:
  - {id: inj-1, kind: probe, bound_ms: 2000}       # kind: probe | fault | static; fault: E4, unread in E1
```

- **Effective case bound (rev 2, RV-TA 10):** `min(case.bound_ms, bounds_ms[interface])`. An omitted `bound_ms` means the interface bound. W1-I and W1-L set each bound from the reference solution's measured duration with a stated multiplier, recorded with the task (RV-DS 4).
- **`env` (rev 2, RV-SEC 2; ADR-0018 §9):** a name is allowed only if it is in `grade/_env.py: TOOLCHAIN_ENV` (X-F defines it; a dotnet toolchain's names are `_env.DOTNET_HOST_ENV`, one definition) or starts with `HB_CHECK_`. **Rev 3 (req-01M41DM80):** `correctness.DOTNET_HOST_ENV` moves verbatim to `grade/_env.py`, and `correctness.py` imports it from there, so `correctness.DOTNET_HOST_ENV` still resolves. Revision 2's "imported from correctness" with G4's "correctness imports `HOST_ENV` from `_env.py`" was an import cycle (W1-F reproduced the `ImportError`, 2026-10-03). `mutation.py` keeps its own, different tuple unchanged. No grader's environment changes (US-4 byte-equal). Readiness refuses any other name, and any name in the profiles denylist (`profiles.DROP_EXACT`, `profiles.DROP_PREFIXES`), with HB-RDY-005. `spawn_deliverable(argv, env_extra)` raises on a key outside the declared `env` and `HB_CHECK_*`. Values come from the grader's allowlisted environment only, never `os.environ` read in the check.
- **`in-process`, redefined (rev 2, RV-SEC 1, blocking; ADR-0018 §1, §2, §10; W1-F seam `req-01M41C0N`).** The check process **never imports agent code**. ADR-0018 §1 already says "The check starts the deliverable as its own child (so it is in the same job), only through `bench_check.spawn_deliverable`". For an `in-process` task, the check spawns a **probe host** through `spawn_deliverable`: the bench-provided `bench_check.py` run in host mode. The probe host imports `app` and answers each probe with the **raw** response, as framed request and response lines over pipes the check owns. The handle list holds exactly the child's own stdio handles, and the check's result pipe is never in it. The check decides every outcome from the raw response. So a forger in the deliverable's module body can write only into the deliverable's own response channel, as a loopback deliverable could. There is still no socket ("probes call it in process: no socket at all", ADR-0018 §2: the call is made inside the probe host). The value keeps its ADR-0018 §12 name because the old meaning (importing into the check) no longer exists anywhere. W1-F fixes the frame shape and the probe host's interpreter flags; a deliverable with third-party dependencies needs its own site-packages, which W1-F and W1-I settle together. **Red-first test** `test_import_time_forgery_cannot_reach_result`: a fixture deliverable whose module body writes a forged `bench-check-result/1` document to `sys.stdout`, reads one byte from stdin and calls `os._exit(0)`. The grader's parsed result must never be the forged document (W1-F's spike SP-F1 reproduced the forgery against revision 1's text, 3 of 3).
- **`app.kind: wsgi` is built in E1 (rev 3, Coordinator ruling C-1 on RV-PAT W1-I 1-3).** S1, the only E1 property task (section 1), is a microdot app whose prompt fixes `create_app(tokens, db_path)`: a WSGI factory. W1-F rev 2 cut `wsgi` for having no E1 caller, and its own trigger ("added when W1-I or W1-L names a web-shaped deliverable") has now fired. ADR-0018 §2 names "a WSGI/ASGI app" as the in-process case, so no ADR meaning changes. X-F builds the minimal `wsgi` kind with the probe-host items below. Redesigning S1 as `callable` was refused: it rewrites W1-I's task and its prompt signature for no reduction in X-F's risk.
- **Probe host (rev 3, req-01M41DPBSM9, W1-I spike SP-I1).**
  - *Frames.* Each line is one canonical JSON object. `callable`: request `{id, args, kwargs}`, response `{id, ok, value}` (W1-F §5.5). `wsgi`: request `{id, method, path, query, headers: [[name, value]], body_b64}`, response `{id, ok, status, headers: [[name, value]], body_b64}`. W1-F may add fields; it may not rename these.
  - *Environ.* For `wsgi` the host builds a complete PEP 3333 environ: `REQUEST_METHOD`, `SCRIPT_NAME`, `PATH_INFO` (percent-decoded), `QUERY_STRING`, `CONTENT_TYPE`, `CONTENT_LENGTH`, `SERVER_NAME`, `SERVER_PORT`, `SERVER_PROTOCOL`, `REMOTE_ADDR` = `127.0.0.1`, `REMOTE_PORT`, `HTTP_*`, and every `wsgi.*` key. A missing `REMOTE_ADDR` raised `KeyError` in microdot (observed by W1-I), so an incomplete environ is a host defect, not an agent failure.
  - *`{state_dir}`.* The check substitutes a per-case empty folder `check-run/state/<case id>/`. It is outside `check/`, so the app's writes never trip outcome row 3.
  - *`paths`.* Relative paths under the deliverable root only. Readiness refuses an absolute path or one that leaves the root (HB-RDY-005).
  - *App output.* The app's output (file descriptors 1 and 2, `sys.stdout`, `sys.stderr`, `wsgi.errors`) never reaches the protocol channel: the host runs the protocol on a private duplicate of its pipe and redirects 1 and 2 before it imports the app. The app's output is captured to a file under `<out_dir>/check`, egress-scanned like all evidence, and the check may scan it for a canary (S1's `leak-2`). The mechanism is W1-F's. Without this rule a reference that prints a line would fail as `exploited`.
  - *Start bound (rev 3, req-01M41DT67, granted in part).* The host's ready line must arrive within `bounds_ms[interface]` (there is no case at start, so the bound is the interface's, not a case's). If it does not, the check kills the host and reports `deliverable: did not start` (row 6, a measured 0; EV-3 makes a hang a measured failure, and an app that serves at import is an agent defect). The evidence records `start_ms`, so a load-driven miss is visible. Row 2 (the outer bound, NA) is unchanged for the step as a whole.
- **Not built in E1:** `interface: loopback`, `bounds_ms.loopback`, `deliverable.config` and `kind: fault` keep their shape for seam stability. They are unread in E1, and W1-F does not build them (rev 2, RV-SIM 7).

**Invocation.** The property step runs in two phases, in this order (rev 2, RV-SEC 3):

1. **Tests.** `correctness.grade(ws, task_dir, oracle, out_dir, run_dir, timeout, work_dir)` (`correctness.py:196`, R-90 condition 2), once per graded tree (the final tree; for rework also the turn-1 snapshot), under `cells_root/grading/<gid>/<cid>/property/tests/`, with `timeout = grading_step_timeout`.
2. **Check.** It starts only after the tests phase's job holds no process (`procs.run` confirms the job is empty; W1-F seam). Then the grader builds a **fresh** copy `cells_root/grading/<gid>/<cid>/property/check-run/` (ADR-0013 Am. 2): first `deliverable/` (from the archive: the final tree, or a named snapshot), then `check/` (the oracle check), `check/bench_check.py` (copied from `grade/bench_check.py`) and `check/cases.json`, copied **last**. `cases.json` is the grader's parsed and validated form of `cases.yaml`, written with sorted keys, because the check is stdlib only and the stdlib has no YAML parser (W1-F seam `req-01M41C57`). Authors still write `cases.yaml`, and it stays the hashed task file. The grader hashes `check/` with `plan.tree_hash` at that moment, and again after the check exits. It starts the check in a new Job Object with the outer bound `grading_step_timeout`, with `DETACHED_PROCESS`, and with `grade/_env.py`'s environment:

```
<sys._base_executable> -S check/<entry> --deliverable <abs> --cases check/cases.json --seed <int> --evidence <out_dir>/check
```

- **Evidence directory (rev 2, RV-SEC 8; W1-F seam):** `<out_dir>/check`, which is outside the grading copy (`grade/__init__.py:57`: `out_dir` is the grader's only write place). Evidence is egress-scanned (US-47), with canaries in class `task canary` (R-E9), before any judge or report reads it.
- **Bounds per phase (rev 2, RV-DS 13):** each phase has its own `grading_step_timeout` bound (R-90 condition 2 for each test run; ADR-0018 §5 for the check). The host-suspend rule (HB-CHK-004) applies to each phase's own span. The evidence records each span. W1-F states the measured worst case of the whole step.
- `seed = int(sha256(f"{task_version}|{cell_id}|{metric_id}").hexdigest()[:16], 16)` with `metric_id = property_check_pass` (ADR-0018 §6, recipe kept verbatim). The seed is per (cell, property check), **not per tree**: a rework cell's two test runs and its check share it (rev 2, RV-PAT 11).
- The check calls only `bench_check.spawn_deliverable(argv, env_extra)` (explicit handle list, the allowlisted environment; §9, §10; `build`, `start` and the probe host all go through it) and `bench_check.write_result(doc)` (one write, after the job holds the check alone; §10a(a)).

**Result.** Exactly one JSON document on the check's stdout (rev 2 framing, RV-DS 3):

```json
{"schema": "bench-check-result/1",
 "deliverable": "ran",
 "cases": [{"id": "inj-1", "outcome": "blocked", "duration_ms": 41}],
 "measures": {}}
```

- **Framing.** The document is one line of canonical JSON ended by `\n`, at most 64 KiB. The grader reads the check's stdout line by line on its own thread from the start, so a large write never blocks the check. "No trailing bytes" (§10a(b)) is checked at EOF, after the check exits, not before the ack.
- **Acknowledgement (spike E1-S3; Acknowledged Message).** After the grader has validated and accepted the line, it writes one byte to the check's stdin. The grader closes the check's stdin on **every** path. On a rejected line it closes stdin with no byte. The check exits **0** only after reading the byte. Stdin EOF with no byte means "refused", and the check exits **3** at once. So a rejected document never waits for the outer bound (RV-TA 4, RV-PAT 7; the exit codes are W1-F's).
- `deliverable` ∈ {`ran`, `did not build`, `did not start`} (closed; W1-F seam). `cases` is empty unless `ran`. "Did not" means the step ran to its own end and failed: a non-zero build exit, a start or import that raised, a process that exited before it was ready, or (rev 3) a probe host whose ready line missed the start bound. A build or start still running when the outer bound fires is NA `check exceeded its bound` (rev 2, RV-DS 4).
- `outcome` ∈ {`blocked`, `exploited`, `passed`, `failed`, `timeout`}. Case ids come only from `cases.yaml`. Each case appears exactly once.
- **`measures` (rev 2, RV-SEC 5, RV-SIM 8; W1-F seam):** a metric that is a function of `cases` is computed **by the grader** from `cases` and must not appear in `measures` (one definition): `property_check_pass` (below), `exploit_probes_blocked` = blocked probes ÷ probes, `fault_suite_pass` = passed fault cases ÷ fault cases. `measures` carries only non-derivable metric ids of the task's narrowed set (resilience: `idempotency_violations`). Any other key, or a value that fails `at_scale`, is `check output invalid`.

**`property_check_pass` (rev 2, RV-TA 5; R-90 condition 2; EV-1).** It is 1 iff the final tree's hidden tests pass **and** `deliverable` is `ran` **and** every declared case ended `blocked` or `passed`. Any `exploited`, `failed` or `timeout` case makes it 0, and so do `did not build` and `did not start` (EV-1's measured 0). A property may narrow this by a per-property rule in W1-F or W1-L (for example a ceiling as a `static` case). Nobody may widen it. Truth-table test: reference 1, naive 0, tamper NA, did-not-build 0.

**Grader outcomes: evaluated in this order; the first matching row decides** (rev 2, RV-TA 4, blocking; RV-SEC 4; the order is W1-F's, seam `req-01M41C0N`). A suspend explains everything after it. A bound kill makes every later process fact (alone, exit time, exit code) an artifact of the kill, so the bound comes next. A document is judged only when the process facts are clean.

| # | condition | score row |
| --- | --- | --- |
| 1 | a host suspend gap in the phase's span | NA `host suspended`, re-run next pass (HB-CHK-004) |
| 2 | the outer bound fired | NA `check exceeded its bound` (HB-CHK-003) |
| 3 | the `check/` hash after the exit differs from the hash taken at copy time | NA `invalid (check tampered)` (HB-CHK-002) |
| 4 | a §10a(b) failure: not alone in the job at the line's first byte; more than one line, or trailing bytes; an exit before the line arrived; no line; exit code ≠ 0 after the ack, or ≠ 3 after a refusal | NA `invalid (check tampered)` (HB-CHK-002) |
| 5 | the line is malformed (schema, size, case ids, `measures` keys or values) | NA `check output invalid` (HB-CHK-001) |
| 6 | `deliverable` is `did not build` or `did not start` | `property_check_pass` = **0**, a measured failure (EV-1) |
| 7 | otherwise | the scores, by the predicate above |

Tests: one red-first test per row, plus one per adjacent pair, to prove the order (a malformed line refused, then exit 3 → row 5; a forged line plus a hang → row 2).

**NA is never a dropped cell (rev 3, req-01M41DM7X, granted in part; RV-SEC W1-F 2, RV-TA W1-F 8).** A deliverable can turn a measured 0 into NA (leave an unsweepable process, kill the check), and the grader cannot know which happened. So W0 keeps NA, and the consumers fail closed:
- `gates.pilot` emits `GateItem(kind="check-tampered", ident=<cell_id>)` for every cell with an HB-CHK-002 row, and `GateItem(kind="suspend-detector-blind", ident=<cell_id>)` for every cell with a phase span whose `unbiased_ok` is false (the suspend detector could not read the unbiased clock). X-H1; the cell list comes from X-E's `readiness.unbiased_failures` (section 8, req-01M41EPKV).
- The report shows the NA count, by reason, beside every property metric and every verdict row. X-H2.
- An NA cell appears in `Verdict.excluded` with its reason (section 8; ADR-0020's shape). **Refused:** changing a verdict's label because of an NA count. That rule is ADR-0020's and would need the Owner.

**Grading copies do not follow reparse points (rev 3, RV-SEC W1-F RF-9).** `copytree` follows a junction, and three grading copies use it today: `grade/_changes.grading_copy`, `correctness.py:207` and `formal.py:280`. W1-F's reparse-safe copy (its `_copy_tree`: scandir, no entry into a reparse point, junctions skipped and listed) is the one helper. X-F moves it to a module all three may import without a cycle (`grade/_changes.py`, beside `grading_copy`; no new module) and switches the three sites in E1. Test: `test_grading_copy_with_junction_leaves_target_untouched`, run through each of the three graders.

**Section 3 additions (rev 4; RV-SEC W1-F rev 3 findings 2, 3, 4, 6; RV-TA W1-F rev 3 finding 5 and its W0 owner gap).**
- **Case ids are path segments, so their charset is fixed:** `^[a-z0-9][a-z0-9_-]{0,31}$` (RV-SEC 3: `..`, an NTFS stream `a:b` and a device name `nul` must not reach `state/<case id>/` or `host/<case id>.log`). X-F's `cases.json` writer refuses another id (`ValueError`, so HB-GRD-003 makes every metric NA, as for a bad `env` name), and X-E's readiness refuses it first (HB-RDY-005). Red fixtures: `..`, `a:b`, `nul`. S1's ids (`inj-1`, `authz-1..3`, `leak-1..3`, W1-I) conform.
- **`{state_dir}` is fresh and reparse-safe** (RV-SEC 2): the check `lstat`s `check-run/state/<case id>/`; anything there (a folder an earlier case's host seeded, or a junction) is removed without entering a reparse point; then it is created with `exist_ok=False`. X-F, red fixture: case 1's app creates `state/<case 2>/seed.db`, and a junction variant; case 2 sees an empty folder.
- **App output: what the capture measures** (RV-SEC 4, 6). The cap on the app-output file bounds the evidence, not the disk: the host can write to it until the case bound ends (same-user disk reach is ADR-0013's accepted residual). The capture holds the probe host's file descriptors 1 and 2 only. A grandchild with default stdio is not captured (W1-F RF-11, accepted for E1), so S1's `leak-2` measures accidental logging, not a deliberate leak through a child process or a file. W1-I's `leak-2` text says so (X-I).
- **Owners of two tests W0 named without an owner** (RV-TA W1-F rev 3 finding 5). (a) The `paths` rule (HB-RDY-005): X-E owns the readiness test (`tests/test_readiness.py`, with the same four bad paths as X-F's `test_cases_paths_outside_root_are_refused` plus the `ok` control); X-F keeps its writer-side test. (b) **The frame golden:** X-F, one node that asserts the exact request and response key sets of both kinds (`callable`: `{id, args, kwargs}` / `{id, ok, value}`; `wsgi`: `{id, method, path, query, headers, body_b64}` / `{id, ok, status, headers, body_b64}`; plus W1-F's added `error`) and the exact environ key set (`set(environ) == W0_ENVIRON_KEYS | {"HTTP_AUTHORIZATION"}`), so a rename made in the host and the check together turns it red.

- **Evidence per cell:** for each tree, `hidden_tests_pass` and `hidden_tests_ms` (R-90 condition 3); per case, the outcome and `duration_ms`; the seed; the `check/` hash before and after; each phase's span.
- **W0 decision: a measured 0 carries no `Score.reason`.** `Score` allows a reason only with `value None` (`grade/__init__.py`, `Score.__post_init__`). EV-1's "0 with reason `deliverable did not build`", and the architecture's "the score's reason names the first failing case", are written into the evidence file, which `Score.evidence` points at (`<evidence file>:<line>`). `Score` does not change.
- **ADR-0018 deviations recorded here (rev 2, RV-SEC 9):** (a) the check runs under `sys._base_executable -S` (no site-packages at all), not "the task's pinned interpreter"; the check is stdlib only; (b) the one-byte acknowledgement, its framing and exit codes come from spike E1-S3 and W1-F, and are not in the ADR; (c) the probe host's stdio are pipes owned by the check, not files; (d) the check reads `cases.json`, the grader's normalised copy of `cases.yaml`. **Rev 3:** the amendment note is recorded as ADR-0018 *Amendment 1*, with these four, the probe host, the `wsgi` kind and the start bound.

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
    lstat-ed first: a reparse point (a junction or symlink) is unlinked, never recursed into. Each deletion is logged.
    Rev 3: a sibling is listed only if is_temp_name(name) holds (TEMP_RE), not by the glob. Pure listing, sorted."""

# rev 3 (req-01M41DMZX, S-B1; RV-SIM W1-B 8):
TEMP_RE = re.compile(r"^(?P<base>.+)\.tmp-(?P<pid>[0-9]+)-(?P<nonce>[0-9a-f]{32})$")   # the one definition of a temp name
def is_temp_name(name: str) -> bool: ...          # TEMP_RE.fullmatch; used by stale_temps, `bench campaign verify`, tests
def sweep_temps(target: Path, lock: RunLock) -> list[Path]: ...  # deletes what stale_temps lists (the one reparse-point guard); returns them
#   rev 4 (S-B4 2): raises ValueError before deleting anything unless oslock.is_held(lock.path)
def make_writable(func, path, _exc) -> None: ... # moved from archive.py; archive re-exports it; workspace imports it from atomic (rev 4)
#   rev 4 (S-B4 5; RV-SEC W1-B 6): lstat first; never chmod through a link or reparse point; adds S_IWUSR to the current mode

# rev 4 (req-01M41FDXHDYP8YG3HPDNDGQHAN, S-B4 1; RV-PAT W1-B 1):
RENAME_BACKOFF = (0.05, 0.1, 0.2, 0.4, 0.8, None)   # moved from workspace.py:89; the one copy
def rename_with_retry(src: Path, dst: Path, *, replace: bool = False, settled: Callable[[], bool] | None = None) -> int: ...
#   the one WIN-A loop: PermissionError is retried (or returns when settled() is true); every other OSError,
#   FileExistsError included, propagates at once; returns the retry count. publish_dir and workspace._land call it.
# atomic.py imports stdlib, harness_bench.errors and harness_bench.oslock only (rev 4)
```

- **Windows branch (spike E1-NTFS, quoted):** "a directory cannot be opened for fsync at all (PermissionError), so ADR-0015 section 5a's 'fsync the folder' is POSIX-only". `publish_dir` fsyncs the folder only when `os.name == "posix"`. W1-B states the branch and its test. Each file's fsync goes through its write handle: a read-only fsync fails (spike E1-S1).
- **Temp names and the sweep (rev 2, RV-TA 6, 12; RV-DS 5, 6; RV-SEC 10; RV-PAT 6).** Both helpers name temps `<name>.tmp-<pid>-<uuid4 hex>` and create them exclusively, so PID reuse cannot fill an old folder. A resume (X-K1) calls `sweep_temps` before it redoes a copy. A `bench campaign` write command (X-C) calls `sweep_temps` over the campaign folder only, under `campaign.lock`. **Rev 4 (S-B4 3; RV-DS W1-B 3):** the sweeper of `bench/discrimination/<task>/` is **X-E**, under the discrimination run's own lock (W1-E names it), because `bench discriminate` does not take `campaign.lock`; X-C never deletes there. `sweep_temps` refuses unless the caller's lock is held (S-B4 2). `bench campaign verify` skips every name for which `is_temp_name` holds: they are not content-addressed records, and the sweep owns them. **Rev 4 (S-B4 4; RV-SEC W1-B 1, 8):** it does not skip silently: it names each temp-named entry (file or folder) in a warning line, and it `lstat`s `campaign.lock` and fails HB-CMP-003 unless it is a regular file; acquiring the lock refuses a non-regular `campaign.lock` the same way. Test: kill between the write and the link, then verify and resume.
- **Readers of the archive folder (rev 3, S-B3).** `archive.attempt_dirs(run_dir, cell_id) -> list[Path]` (X-B2, E1; `re.fullmatch(r"attempt-(\d+)")`, sorted by number) is the one reader of attempt folders. `report/judges.py:216` uses it in E1 (X-B2); `pack_improvement._attempt_dirs` switches to it in E3 (X-A3). A leaked `attempt-1.tmp-…` raises `ValueError` in `judges.py` today (RV-SIM W1-B 7, Verified).
- **`recover_archive` is built by X-K1 in E3 (rev 3, Coordinator ruling on RV-SIM W1-B 1).** Its first caller is resume (X-K1, E3), and the crash fixtures exist there. W1-B's design keeps the recovery rule and its state table as the contract; X-B2 ships `archive_cell`, the strict `verify` and `attempt_dirs` in E1.
- **The crash window between the rename and the row append (rev 2, RV-DS 9).** The caller's one recovery rule: if `final` exists and its rows are absent, recompute the rows from the folder, compare them with the source (still in the archive root or the working copy), then append them. If `final` exists and its rows are present, verify only. X-K1 carries the test (with `recover_archive`, section 4 above), and W1-J for turn snapshots (rev 4, RV-TA W1-B R2-1; rev 3 moved `recover_archive` to X-K1).
- Every create-only file (identity, prereg and power files; discrimination records) is written with `create_once(path, ledger.canonical(obj))`. Every archive and turn snapshot is written with `publish_dir`. There is no second helper (DM7). A hard-link failure on a volume without `os.link` is a hard error, never a silent fallback (RV-DS residual). **Rev 3 (S-B1, refused in part):** the `OSError` from `os.link` propagates unchanged, with the path in its message; there is no HB-LED-009. No volume in scope lacks hard links (spike E1-S1: `os.link` works on NTFS), and a broad mapping would mislabel a `FileNotFoundError` or a transient `PermissionError` (RV-DS W1-B 2, RV-SIM W1-B 5). A code is added when a volume that cannot link appears.

## 5. `bench-matrix/2` and `bench-plan/2` (ADR-0014, ADR-0016 §6; owner X-A1 in E1, X-A3 in E3)

**`bench-matrix/2`:**

```yaml
schema: bench-matrix/2
bom: {file: bench/bom.yaml, subset: [S1]}
repetitions: 3
arms:                                # 2+ arms, ids ^[a-z][a-z0-9-]{0,15}$, at most one "off", which has no pack
  - {id: "off"}                      # ids are QUOTED: PyYAML reads a bare off as False (rev 3, SR-1)
  - {id: "candidate", pack: {source: "<repo>", commit: "<sha>"}}   # in a ring: role arms carry no pack (bound at plan time)
comparisons: [["off", "candidate"]]  # optional for 2 arms; required for 3+ (the one reader rule below)
combos: [{id: cc-opus, harness: claude-code, model: claude-opus-5-5}]
ring: {tag: pilot}                   # rings only: pilot | pack-regression | comparison
```

- **Ids are strings (rev 3, SR-1; W1-A spike SP-A0).** `config.load_yaml` (PyYAML `safe_load`) reads a bare `off` as `False`: revision 2's example loaded as `arms [{'id': False}]`. Arm ids in a matrix file are quoted strings, in `arms` and in every `comparisons` entry (rev 4, RV-PAT W0 delta nit), and `validate_matrix` refuses a non-string id (a `Problems` item naming the arm's position).
- **Role (rev 2, RV-SIM 9; ADR-0016 §6):** a ring arm is a *role*: an arm declared with no pack (`{id: incumbent}`, `{id: candidate}`), which `bench plan --arm <role>=<source>@<commit>` binds to a pack revision. An unbound role is refused (HB-PLN-002).
- **Comparisons default: one reader rule in `plan.py`:** with 2 arms and no `comparisons`, the comparison is `[[off, other]]` if one arm is `off`, else `[[first, second]]` in file order. With 3+ arms, `comparisons` is required.

A `bench-matrix/1` file is read in memory as arms `on` (the plan's single `pack`) and `off`, in the file's order. No file is rewritten.

**`bench-plan/2`** is `bench-plan/1` with these changes:

| field | shape | phase · owner |
| --- | --- | --- |
| `schema` | `"bench-plan/2"` | E1 · X-A1 |
| `pack` (top level) | **removed** (rev 3; `arms` replaces it; readers use `plan_pack`, below) | E1 · X-A1 |
| `arms` | `{<arm id>: {"pack": {source, commit, revision} \| null}}` | E1 · X-A1 |
| `comparisons` | `[[reference, treatment], …]` | E1 · X-A1 |
| `launch_seed` | int, drawn once at plan time and **stored in the plan**; `cells` order = blocked randomisation by it. A confirmed plan is never re-planned under the same run id (`plan.py:365` already refuses) (rev 2, RV-DS 14) | E1 · X-A1 |
| `cells[].arm` | arm id; replaces `cells[].pack`. `cell_id` keeps the recipe byte for byte: the ingredient named `pack` carries the arm id (ADR-0014 §3). **Golden test (rev 3, SR-4; replaces rev 2's fixture names):** `tests/fixtures/plans/grid4-cells.json`, committed by X-A1, extracted from `runs/grid-4/plan.json`: grid-4's 276 real cells, each with its `cell_id` and its recipe ingredients. The test recomputes every id with the bench-plan/2 code (arm ids `on` and `off`) and is red if one differs. Rev 2 named the two ledger plan fixtures; they carry hand-made ids `a` and `b` and no schema field, so 0 of 4 equal the recipe (W1-A spike SP-A4), and a golden over them is red on arrival or vacuous | E1 · X-A1 |
| `kind` | `"measurement"` (default) \| `"discrimination"` (ADR-0016 §5) | E1 · X-A1 writes the field; X-E passes `discrimination` |
| `campaign` | absent, or `{campaign_id, prereg_hash: str \| null, identity: {hash, components}}`: written verbatim from a `build_plan` argument; plan.py imports neither campaign nor identity. `identity` is the campaign's effective **run side** only (rev 3, section 6) | E1 · X-A1 writes the field; X-C builds the block |
| `ring` | absent, or `{tag, hash}` (hash = `tree_hash` of the ring file) | E1 · X-A1 |
| `tasks.<id>.turns` | `[{n, sha256}]` for turns 2..n (US-9 per turn) | E2 · X-J1 (plan.py edit by seam to the E2 phase owner) |
| `cells[].calibration` | bool, EV-9 | E3 · X-A3 |

- **Accessors**, defined once in `plan.py`: `cell_arm(cell) -> str` (`arm`, else `pack`) and `arm_pack(plan, arm) -> dict | None` (`arms[arm].pack`; legacy: the top-level `pack` for `on`, `None` for `off`). No other reader reads `pack`, except the listed legacy readers (guard G1, section 10).
- **No top-level `pack` in bench-plan/2 (rev 3, Coordinator ruling on RV-PAT W1-A 1 and 5; W1-A AD-2).** `arms` is the only statement of pack revisions (DM7). Revision 2 did not list the removal, and four readers read the top-level `pack` and would degrade silently on a `/2` plan: `report/pack_improvement.py:742-748` (`planned` empty), `board.py:755-757` (`same_pack_revision` becomes `None`, so ADR-0014's hard precondition is skipped, not failed), `report/summaries.py:175-178` (`pack_revision: None` in the ranking manifest), `report/html.py:265,266,288` ("not recorded" for a run that has a pack). **Migration, E1:** a third accessor `plan_pack(plan) -> dict | None` in `plan.py`: the top-level `pack` of a bench-plan/1 plan, else the pack of the plan's only pack-bearing arm, else (two or more pack-bearing arms) it raises HB-PLN-005 naming the arms. **Rev 4 (RV-PAT W0 rev 3 delta 2): only `board.compare` lets it raise** (ADR-0014's hard precondition must fail, not be skipped). One accessor, as W1-A rev 2 §3.3 builds it: `plan_pack(plan, *, strict=False)`; `board.py` passes `strict=True`. The display readers (`report/html.py` header, `report/summaries.py` ranking manifest) call it with the default and render the label `several packs` (never a single revision) for two or more pack-bearing arms, so a two-pack run's report renders. `report/pack_improvement.py:746-747` reads a **cell**, so it reads `cell_arm`, not `plan_pack` (W1-A rev 2 §3.8). Each of the four sites reads `plan_pack` instead (one line each): X-A1 in `pack_improvement.py`, `board.py` and `summaries.py` (no E1 owner; section 13), and X-H2 in `html.py` (its E1 hub), from X-A1's lines. Test (X-A1): each of the four readers on a `/2` plan with one pack-bearing arm states the true revision; on a plan with two pack-bearing arms `board.compare` raises HB-PLN-005 and each display reader renders `several packs` (rev 4; W1-A rev 2 `test_plan_level_readers_state_the_true_pack_or_refuse`); red against today's code. X-A3 migrates them to comparisons in E3.
- **Label (W0 constraint, X-A1 picks the text):** a bench-plan/2 label must match `config.LABEL` (`[A-Za-z0-9.\-]{1,80}`) and name the arm. bench-plan/1 labels are never recomputed. **Picked (rev 3; W1-A AD-4):** `<task>.<combo>.arm-<arm>.r<rep>`.
- **Launch balance (ADR-0014 §4, quoted):** "`bench plan` asserts the bound and refuses otherwise" → `HB-PLN-001`.

## 6. Campaign records (ADR-0016, ADR-0017; owner X-C, identity X-D)

**Ledger** `bench/campaigns/<campaign_id>/ledger.jsonl`. ADR-0006 rules: `ledger.canonical`, `stamp` (`recorded_at`, `mono_ns`) and the chain (`seq`, `prev_hash`, `hash`). A single writer, under `bench/campaigns/<id>/campaign.lock` (`oslock`). Lock first, then read the state (council D6). Every row is `{"kind": <kind>, "campaign_id": <id>, …fields}`, with this closed kind enum (ADR-0016 §1):

| kind | fields |
| --- | --- |
| `campaign.created` | `question` (str; never crosses B2) |
| `baseline.recorded` | `identity_hash`, `bench_commit` (**W0 refinement:** ADR-0017 §1 says the commit "is recorded beside it for provenance"; this is the place) |
| `defect_fix.admitted` | `defect_class`, `commit`, `changes: {component: [before, after]}`, `scope: run \| grade \| both` |
| `power.recorded` | `role: prior \| final`, `input_hash` |
| `ring_run.attached` | `ring_hash`, `run_id`, `plan_hash` (rev 4: `tag` dropped, it is always `pilot`, RV-SIM W1-C OI-4; `plan_hash` added, RV-SEC W1-C 7) |
| `pilot.passed` | `run_id`, `grading_id`, `gate_input_hash` |
| `admission.decided` | `task`, `admitted: int` (0 or 1; rev 4, SR-C2 a: `ledger.canonical` refuses a bool, `ledger.py:43`), `reason` |
| `registered` | `prereg_hash` |
| `grid.attached` | `run_id`, `plan_hash` (rev 4, RV-SEC W1-C 7) |
| `concluded` | — |
| `abandoned` | `reason` |

W1-C justifies each kind against "can the state be derived from the other rows?" (rev 2, RV-SIM 11). It may merge kinds by narrowing. It may not add one.

**`plan_hash` (rev 4; RV-SEC W1-C 7; W0 refinement of ADR-0016 §1, like `bench_commit`).** The ledger bound a plan by run id only, and `runs/<id>/plan.json` is gitignored and editable after attach, so a post-attach edit could drop tasks or arms and still pass. `plan_hash` = `file_hash` of the run's `plan.json` bytes (written once by `plan.confirm`, mode `x`), recorded under `campaign.lock` by `pilot attach` and `attach`. The run-side check (below) recomputes it and refuses a mismatch with HB-CMP-010 naming the run. `check_plan` also recomputes `identity_hash` from the block's `components` (W1-C's own fix). Rejected: a second statement of the grid as a cell-set rule (that is the final power inputs' job, below).

`campaign_id` matches `^[a-z0-9][a-z0-9-]{0,39}$` (W0 decision: a folder name that is safe on Windows and fits a label).

**Pre-registration freeze: the order (rev 2, RV-DS 1, blocking; ADR-0016 §3, EV-13).**
1. `grid.attached{run_id, plan_hash}` is appended under `campaign.lock` **before** the run's first `cell.launch_intent`. Attaching is refused unless the plan's `campaign.prereg_hash` equals the current `registered.prereg_hash` (HB-CMP-010; rev 4, SR-C2 d). **Rev 4 (RV-SEC W1-C 5):** under the same lock, `attach` also computes the working tree's `side(manifest(...), "run")` and refuses HB-CMP-010, naming the components, when it differs from the effective run side, so a drifted tree is caught before the freeze, not at the first launch.
2. **W0 decision: once any grid run is attached, re-registering is refused** (HB-CMP-009), launched or not. ADR-0016 §3 allows a different hash "only while no attached grid run has a `cell.launch_intent`". This is a necessary condition, and W0 narrows it. Reason: the launch check below runs outside `campaign.lock`. Only a freeze at attach time closes the window between that check and the first launch. Before it attaches a run, the operator can still re-register freely.
3. `bench run` of a plan that carries a `campaign` block refuses (HB-CMP-010) unless the ledger holds `grid.attached` for this run id **and** its current `registered.prereg_hash` equals `plan.campaign.prereg_hash`. **Rev 4 (SR-C2 c; W1-C W-3):** a **pilot** plan carries the block with `prereg_hash: null`; for it the condition is a `ring_run.attached` row for this run id whose `ring_hash` equals `plan.ring.hash`. A null hash never matches `grid.attached`; a non-null hash never matches `ring_run.attached`. In both cases the row's `plan_hash` must equal the plan file's hash, and the campaign must not be `concluded` or `abandoned` (HB-CMP-002 naming the state). One function, `campaign.run_side_check(root, plan, run_id)` (X-C). **Rev 4 (RV-DS W1-C 2), where it runs:** inside the engine, **after** the run lock (`runs/<id>/.lock`, `engine.py:374`) is held and before the first `cell.launch_intent`, through an injected keyword `campaign_check: Callable[[], None] | None` that `cli.py` passes (one line beside `identity_check=`). The callable try-probes `campaign.lock` (held: HB-CMP-001, nothing launched), then re-reads the ledger lock-free. That is the same own-lock-then-probe order as every other pair: `conclude` and `abandon` hold `campaign.lock` and probe the run lock, so a run and a conclusion can never both proceed. X-D adds the keyword in `engine.py` (its E1 hub; a fake-callable test); X-C writes the function and the `cli.py` line with the real-wiring test. `plan.py` and `engine.py` still import no campaign code.
4. The freeze now reads only the campaign's own ledger, under its lock. It no longer reads another process's live `events` file (RV-DS 12 is moot).

Test: two processes. One re-registers while the other attaches and launches, in both interleavings. The ledger's registered hash always equals the hash the grid ran under.

**The grid a pre-registration names (rev 4, W1-C OI-2).** The prereg body is EV-13's fields and names no tasks or combos. "The grid the pre-registration names" (ADR-0016 §7) is the **final power inputs** (`properties.<p>.tasks`, `harnesses`, `comparisons`), which `register` already requires to match the prereg's `mde`, `alpha`, `power`, `correction` and `pairing_unit`. Pilot coverage reads them. No prereg field is added.

**Ring eligibility (rev 4, W1-C OI-1; W0 decision).** ADR-0017 §5's "its ring hash matches the campaign's ring" is read from each attached grid run's `plan.json` `ring.hash` (ADR-0016 §7: eligibility is recomputed from the runs on read), after its `plan_hash` is checked. The campaign's comparison ring is the `ring.hash` of the first attached grid run (`null` when that plan has no ring). A later grid run with a different value is ineligible, named. A grid run whose `plan.json` is absent locally is ineligible with reason `not recorded`, never assumed eligible. X-C's eligibility reader (W1-C §8).

**Locks (rev 2, RV-DS 7, 8; ADR-0018 §11(a)).**
- **Protocol.** Each side takes its **own** lock first, then try-probes the other's lock (non-blocking). If the probe finds it held, the side releases its own and refuses: `bench campaign` with HB-CMP-004 when a campaign run's `grade.lock` is held; a grading pass of a campaign run with HB-GRD-007 when `campaign.lock` is held (X-F, `grade/runner.py`; `runner.py:201` takes `grade.lock` today).
- **One function (rev 4, SR-C1; RV-PAT W1-C 3, 4; RV-DS W1-C 3).** `oslock.acquire_then_probe(own: Path, own_code: str, others: Sequence[tuple[Path, str]], *, between: Callable[[], None] | None = None) -> RunLock`. It acquires `own` (held: `own_code`), probes each of `others` in order with `is_held`, and on the first held one releases `own` and raises that entry's code. `between` is a test hook called **after the first operation and before the second** (so a mutant that swaps acquire and probe still has the barrier between its two operations); production passes `None`; tests use `Barrier(2).wait(timeout=10)`. **Owner: X-B1** in `oslock.py` (E1; section 13), with its unit tests. Callers: X-C (own `campaign.lock` / HB-CMP-001; others: every attached run's `grade.lock` plus the argument run's, each HB-CMP-004) and X-F (in `grade/runner.py` where `grade.lock` is taken: own `grade.lock` / HB-GRD-001; others `[(bench/campaigns/<plan.campaign.campaign_id>/campaign.lock, HB-GRD-007)]`, only for a plan with a `campaign` block). **W1-F §5.11's "refuses while `campaign.lock` is held: HB-CMP-001, raised through X-C's `campaign.lock_held(root)`" is superseded**: that is check-then-act, and the grading side's code is HB-GRD-007. X-F builds the path inline (`campaign.py` does not exist when X-F lands; marked `simplify:`); X-C replaces it with `campaign.lock_path` in its runner hunk (below).
- **Test (rev 4, SR-C2 b; W1-C W-2).** Two processes start together: **never both proceed**. Both refusing is allowed and leaves every file unchanged (W1-C spike S-C4 measured it: 14 of 90 runs both refused, 0 both proceeded; the count is a characterisation, not the proof: the barrier test with the swap mutant is).
- **Reads are lock-free (rev 4, RV-SIM W1-C 2).** `bench campaign status` and stand-alone `bench campaign verify` take no lock, probe nothing and sweep nothing: they read through `campaign.read` and `verify()` (a torn tail is ignored, ADR-0006). Only write commands use the session protocol (own lock, probe, read, verify, sweep, write). So `status` works while a campaign run is being graded.
- **Lock domain (rev 4, RV-DS W1-C 7).** *assume:* both sides of every pair run in one OS lock domain on a local disk (Windows `msvcrt` or POSIX `flock`, not mixed, not a synced or network folder). Confirm: the operator doc says so. If false: the two sides do not exclude each other.
- **`.gitignore`.** `campaign.lock` sits in a committed folder, and `.gitignore:33` ignores only `*.jsonl.lock`. X-C adds three lines to `.gitignore` in its first commit (rev 3, S-B2): `bench/campaigns/**/*.tmp-*`, `bench/discrimination/**/*.tmp-*` and `bench/campaigns/*/campaign.lock`, with its test `test_gitignore_covers_every_temp_name_and_the_campaign_lock` (W1-B 10.2). `git status --porcelain` does not list ignored files, so `verify` reads the lock and a leaked temp as clean (measured, spike E1-S2, `-uall`).
- **`verify`'s git witness (rev 4, SR-C2; W1-C W-6; RV-PAT W1-C 2; RV-SEC W1-C 3, 4; RV-DS W1-C 1).** ADR-0018 §11(b)'s `git status --porcelain` is a witness to be read, not compared with empty: an append to the ledger shows ` M` after every command (W1-C spike S-C3). The rule keys on content, not on status letters (RV-SEC 3a): for a path in `HEAD`, the ledger's `HEAD` blob **cut at its last newline** must be a byte prefix of the working file (append-only; the cut keeps a torn tail that `reopen` repairs from failing every later command, RV-DS 1), and a content file's bytes must equal `HEAD`'s; for a path not in `HEAD`, a content file's name must equal its hash. Staged states (`A `, `AM`, `MM`) therefore need no rule of their own. Also findings: any `git ls-files -v` flag `h` or `S` under the two folders, and any ignored path there other than a temp name or `campaign.lock` (RV-SEC 3b). Not a work tree: refused, no bypass. A failure is HB-CMP-003, exit 5 (`cli._exit_for` gains the `HB-CMP-003` prefix, X-C; `cli.py:48-49` maps only `HB-LED*` and `HB-SEC*` today). The committed-history rewrite (RV-SEC 4: one commit that rewrites a ledger prefix) is W1-C's to fix (walk the ledger's commits) or to name as an accepted residual.

**Content-addressed files.** Each file's bytes = `ledger.canonical(obj)`, and its name = sha256 of those bytes. Each is written through `create_once`.

| file | `schema` | body |
| --- | --- | --- |
| `identity/<hash>.json` | `bench-identity/1` | `{"schema", "components": {<component>: <str>}}`. Components per ADR-0017 §1: `src/harness_bench/<path>` → `tree_hash` of that file; `catalog`; `bom`; `prices`; `profiles/<h>`; `builds/<h>`; `uv.lock`; `tasks/<id>`; `platform` (= `sys.platform`, ADR-0017 §1: no hostname, user or path; rev 2, RV-SEC 11, with a test that no `os.environ` value and no path appears in a manifest); `python` (`"3.14.6"`); **`gateway`** (rev 3, R-94: `file_hash(bench/gateway.yaml)`, `""` when absent; grade side). `identity_hash` = the file name, the hash of the **full** manifest (both sides). |
| `prereg/<hash>.json` | `bench-prereg/1` | EV-13's fields: `question`, `arms` (id → pack), `primary_metric` (property → metric), `mde` (property → decimal string), `alpha`, `power`, `correction {method, m}`, `pairing_unit`, `method`, `exclusions`, `min_pairs` (int; **R-89:** ≤ 3 for the E1 demo) |
| `power/<input_hash>.json` | `bench-power-inputs/1` | the inputs only (section 8) |

**Identity API (`identity.py`, X-D):**

```python
CLASSES: Mapping[str, Literal["run", "grade"]]        # one table, in code (ADR-0017 §1); section 9 seeds it
def manifest(root: Path, tasks: Sequence[str], builds: Sequence[dict] | None = None) -> dict
#   {"schema": "bench-identity/1", "components": {...}}; builds = plan["builds"] (Build.record() dicts) (rev 3, W1-D 1:
#   identity.py imports no `tools` module)
def identity_hash(m: dict) -> str
def side(m: dict, which: Literal["run", "grade"]) -> dict   # the run-side or grade-side part
def diff(a: dict, b: dict) -> list[str]                  # ["grade/formal.py changed", ...] (the EV-20 copy)
def catalog_hash(root: Path) -> str                      # rev 3, W1-D 5: the ONE definition (moved from grade/runner.py:108-112)
def launch_check(root: Path, plan: dict) -> ...          # rev 3: the engine's recheck; cli.py passes it (below)
```

- **`plan.campaign.identity` (rev 3, W1-D 3; RV-PAT W1-D 2).** It holds the **run side only**: `{hash, components}` of `side(m, "run")`. `baseline.recorded.identity_hash` is the full manifest's hash. The run side in the plan is the campaign chain's **effective** run-side identity (the baseline's, with every admitted `defect_fix.admitted` of scope `run` or `both` applied), never a stamp of the working tree. Two checks hold it there, both X-C's: (1) `bench plan` with a campaign refuses (HB-CMP-002, naming the differing components) when the working tree's run side differs from the effective one; (2) `grid.attached` (under `campaign.lock`) refuses a plan whose `campaign.identity.hash` is not the effective one. W1-C carries both and the test "a plan stamped from a drifted tree is refused at plan time and at the first launch". `plan.py` and `engine.py` still import no campaign code.
- The launch recheck (`engine.py`, X-D) compares `side(manifest(…), "run")` with the plan's `campaign.identity`, before each `cell.launch_intent` (ADR-0017 §7). On a mismatch: `run.launch_stopped{code: "HB-IDN-001", reason: "engine identity drift", diff: [...]}`, and the `cell.launch_intent` row carries `identity_check_ms` (rev 3: "the launch span" is that row). `cli.py` wires it with one keyword, `identity_check=identity.launch_check(root, p)`, plus the import (seam X-D → X-C; `cli.py` is X-C's in E1). A test drives the real `bench run` command, not a fake, and fails if that line is removed (README *Testability floor* item 3). **Rev 4 (req-01M41FVFTZ0QXT2XY7C2KHNE79 1; RV-SRE W1-D 2):** `status.Status` gains `stop_reason: str | None` and `stop_diff: tuple[str, ...]` (at most 5 components plus a count line), read from the last `run.launch_stopped` row and shown beside `stop_code` in the text view, so the operator sees the drifted component at the console. X-C (`status.py`, E1), test `test_status_shows_the_identity_stop_reason_and_diff`.
- `grading.started` gains `grade_identity_hash`. X-F writes it in `grade/runner.py`, calling `identity`. **Lands in E1 (rev 3, W1-D 2):** ADR-0017 §5 needs it for the first verdict.
- **`catalog_hash` (rev 3, W1-D 5).** One definition, in `identity.py`. X-D replaces `grade/runner.py:108-112` (the `def`) by an import in its first commit: its only hunk in X-F's hub file. X-F rebases on it.

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
  1. **One narrowing, three readers (rev 2, RV-PAT 3).** The single function is `grade/runner.py: applicable(catalog, graders, prop: str | None) -> dict[str, dict[str, dict]]`. **Rev 3 (RV-TA W1-G 8, RV-PAT W1-G 3):** the parameter is named `prop` (W1-F's name; `property` shadows the builtin), and the tag test is two explicit steps: `tag = m.get("property")`, then skip the metric when `tag is not None and tag != prop`. A metric with a `property:` tag applies only when the tag equals `property`. An untagged metric always applies. With `property=None`, only untagged metrics apply. This covers the runner's task-changed fallback (`runner.py:318-321`, which has no task), so a changed task gets `property_check_pass` NA `task changed` and no tagged rows. The runner passes `task["property"]["name"]` (or `None`). `readiness.py` imports this function, never a copy (section 2). Today's signature is `applicable(catalog, graders)` (`runner.py:161`); X-F changes it in E1.
     - **Owner resolution: ruled, R-95 (rev 4; provisional in rev 3 on `req-01M41E37FGK5CRZ7NCK3RA20JV`; req-01M41DAHV; RV-SIM W1-G 3).** ADR-0019 item 3 has the formal grader record scenario-7 `pass_at_1`, but catalog 0.6 names `grader: correctness` for it (`metrics.yaml:45`) and `config.py:151` refuses a duplicate id. W1-G's mechanism: an optional catalog key `also_graded_by: [<grader>]`, and a metric's **owner** for a task is the first of `[grader, *also_graded_by]` that the task names, so a cell still gets exactly one row per metric. Only `pass_at_1` carries it in 0.7 (`also_graded_by: [formal]`). This is a second rule inside condition 1's one function and an edit to the entry condition 6 calls untouched, so the Owner rules it. R-95 granted (A) and amended R-90 conditions 1 and 6 to say so. X-F builds the clause with T-R3..T-R5 in `tests/test_grade_runner.py` (X-F's). X-G1 adds `also_graded_by: [formal]` to `pass_at_1` and, in the same commit, updates ADR-0019's item-3 note from "provisional on the request" to "R-95: `also_graded_by: [formal]`" (R-95 condition 4).
     - **The non-owner guard (rev 3, RV-PAT W1-G 1).** On a task that names both `formal` and `correctness` (G1), `correctness` owns `pass_at_1`, so `formal`'s `inp.metrics` lacks it. A grader that returns a key outside `inp.metrics` fails the pass (`runner.py:350`, HB-GRD-004). So `formal.grade_cell` emits `pass_at_1` only when it is in `inp.metrics`. Test: a G1-shaped task through a real `run_pass` records one `pass_at_1` row and no HB-GRD-004; red against an unguarded `grade_cell`.
     - **Catalog validation (rev 3, req-01M41DAHY; seam X-G1 → X-A1).** `config.validate_catalog` gains two checks: a `property:` tag is one of `config.PROPERTY_NAMES` (the one list of the five names; `task.yaml`'s `property.name` and `grade/property.STRATEGIES` are keyed by it, RV-PAT W1-G 5; `config.py` imports no grade code, section 9), and each `also_graded_by` name has a grade module (the existing `grader_modules` check, RV-SIM W1-G 1). The second check is ruled (R-95 condition 2): the name is a grader module, differs from `grader`, and is not repeated.
     - **Join order (rev 3, req-01M41DAHY).** `validate_repo` refuses a metric whose grader has no module (`config.py:158`), so catalog 0.7.dev is red until `grade/property.py` exists. X-F's first commit (the `grade/property.py` skeleton, docstring only) joins `main` before X-G1's green commit. X-G1 never creates that file (X-F's hub).
  2. One definition of "hidden tests pass": `correctness.grade(...)` (section 3), per graded tree.
  3. **The double run is measured; its disagreement is a finding (rev 2, RV-TA 9, RV-DS 10, RV-PAT 10).** The property evidence records `hidden_tests_pass` and `hidden_tests_ms` per tree (section 3). One function, X-E's `readiness.hidden_test_disagreements(run_dir, grading_id) -> list[str]` (cell ids), reads the pass **after both graders have written**. It compares the final tree's `hidden_tests_pass` with the pass's own `pass_at_1` row for the same cell. The grader never reads another grader's output (that is the (c) coupling R-90 refused). `gates.pilot` takes that list as an input (section 8) and emits one `GateItem(kind="hidden-tests-nondeterministic", ident=<cell_id>)` per cell. **DR-7, ruled (R-93; rev 3):** grid runs surface the count too, as a warning line naming the cell ids in report section 3, beside ADR-0020's exclusions, and **not** in the EV-20 header. It changes no verdict, no exclusion and no eligibility; the pilot gate keeps its item. X-H2 renders the line from the same `readiness.hidden_test_disagreements` list.
  4. The strategy helpers (`grade/rework.py`, `grade/noguess.py`, `grade/diffstats.py`) are called by `property.grade_cell` and never registered in `GRADERS`.
  5. W1-G's design carries the dispatch-rule amendment text for `design-phase3-graders`, with the red test: a security task graded by `property` yields rows for exactly `property_check_pass` and `exploit_probes_blocked`, and GradedOncePerPass is green.
  6. Scenario-7 `pass_at_1` is untouched. (Rev 4: R-95 amends this condition: `pass_at_1` stays the formal grader's through `also_graded_by: [formal]`, and the entry's bytes change in 0.7.)
- **The freeze-file correction record is not built in E1 (rev 3, Coordinator ruling on RV-SIM W1-G 2).** W1-G's own evidence (F7) shows that no committed golden can move under the `_passed` fix, and its section 4.5 says "expected use: none". The check (e) exception and the `corrected_from` record stay a written contingency in W1-G's design (record shape and clauses (i)-(v)); T-U4..T-U7 and the `--correct` flag are not built. Trigger: X-G3's before/after run shows a moved golden hash. The existing freeze check already fails on a moved hash, so the trigger is a red gate. Then X-G3 builds the smallest form: (e) admits only an appended record whose `was` equals the base value, with T-U5 and T-U6. ADR-0019 *Amendment 1* records this. The W1-G plan row's done-when item for the record is met by the written contingency.

## 8. Power, verdicts, dominance, gates (ADR-0020; owner X-H1, section 3 X-H2)

Pure functions with no I/O. The campaign stores inputs only (ADR-0020 §5).

```python
# power.py
def analyse(inputs: Mapping) -> Mapping[str, PowerResult]      # property -> result; same inputs => same outputs
#   inputs (bench-power-inputs/1): population {description, exclusions}, source_run_ids, alpha, power,
#     correction {method: bonferroni|holm|none, m}, pairing_unit, harnesses, comparisons,
#     properties {<property>: {primary_metric, tasks, control_rate | "assumed", discordance, sd, rep_spread, mde}},
#     mean_wall_per_cell_s, mean_tokens_per_cell
#   rev 4 (req-01M41EX52AX93PQS1FHYCSA0YG 1, 3): + slots (int >= 1, required): hours = cells * mean_wall_per_cell_s / slots / 3600
#     + planned_reps_per_task (int >= 1, optional): PowerResult.reachable_mde, None when absent (EV-12 last bullet)
#     pairing_unit is exactly "unpaired" | "task-harness-rep" (the same closed set in bench-prereg/1); other values HB-PWR-001
#   PowerResult: alpha, power, mde, pairing_unit, correction,
#     required_pairs: [{harness, comparison: [ref, treat], n}]   (rev 2, RV-PAT 9: rows, so the result serialises as JSON)
#     reps_per_task, cells, hours, tokens, assumed: [input names]
#     rev 4 (R-96 condition 1; RV-PAT W1-H 1): + alpha_per_test, level_rule, reachable_mde. alpha_per_test and level_rule come from
#     ONE table in power.py keyed by correction.method (bonferroni and holm: alpha/m; none: alpha); the Verdict carries both

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
#   int(sha256(f"{prereg_hash}|{prop}|{harness}|{ref}|{treat}").hexdigest()[:15], 16): one seed per verdict, valid
#   across several attached runs (rev 2, RV-DS 11; replaces revision 1's "the plan's launch_seed")
#   rev 3 (req-01M41EPKR): 15 hex digits = 60 bits; rev 2's [:16] gave a value >= 2**63 about half the time (measured
#   49.9 % of 100000), which stats.Params refuses (stats.py:58-59, HB-USR-002)

# gates.py
def pilot(view, hidden_test_disagreements: Sequence[str] | None, unbiased_failures: Sequence[str] | None, *,
          expected_na: Mapping[str, frozenset[str]] = EMPTY) -> list[GateItem]      # rev 4: expected_na keyword-only, default empty
#   GateItem(kind, ident, detail); empty = pass (EV-14). rev 3 (req-01M41EPKV): unbiased_failures comes from X-E's
#   readiness.unbiased_failures(run_dir, grading_id) -> list[str] (cell ids with any span unbiased_ok false, read from
#   property.json), the same pattern as hidden_test_disagreements; HB-CHK-002 is read from the view's score reasons
#   kinds: W1-H enumerates them; fixed here: "hidden-tests-nondeterministic" (section 7, R-90 condition 3),
#   "check-tampered" and "suspend-detector-blind" (rev 3, section 3 "NA is never a dropped cell")
def pack_regression(view, mde: Mapping[str, Decimal]) -> Mapping[str, str]  # "regression signal" | "no regression detected at <MDE>"
def admission(view, tasks: Sequence[str], off_arm: str = "off") -> Mapping[str, tuple[int, str]]      # rev 4 (W1-C OI-3): EV-8
```

**Rev 4 (req-01M41EX52AX93PQS1FHYCSA0YG 2; RV-PAT W1-H 3, W1-C 5; RV-SIM W1-C 8): one arity.** `expected_na` is keyword-only and defaults to empty, so W0 rev 3's three-argument call stays valid. X-C's `pilot pass` passes it from X-E's `readiness.expected_na(root, tasks) -> Mapping[str, frozenset[str]]`: for each task, the metric ids whose `expected.reference` value is `{na: <reason>}`. **W0 decision:** the reference is the task's declaration of what a correct solution cannot record (EV-11's "a metric the task declares `expected NA`"); a naive-only NA says nothing about real cells. **A failed reader** (RV-PAT W1-C 5b; W1-H F13): X-C's call site turns a reader exception into `None` and keeps the exception text; `pilot` raises HB-USR-002 naming the `None` list; `pilot pass` writes no row and prints the reason.

**`admission` (rev 4, W1-C OI-3; X-H1, E1).** EV-8 as one pure function. For each task, the `off_arm` cells' `property_check_pass`: 1 in every cell → `(0, "saturated")`; 0 in every cell → `(0, "floor")`, by exact equality (R-85); otherwise `(1, "")`. A task with an NA primary in any off-arm cell raises HB-USR-002 (the pilot gate has already named it `primary-not-recorded`). X-C's `admit` command records exactly this output as `admission.decided` rows. E1 has no operator override; one would be a request.

**`register` preview obligations (rev 4, RV-PAT W1-C 5c, 5d; R-96 condition 1; W1-H R-H1), X-C.** Before the prereg hash is taken, the preview prints `alpha_per_test` and `level_rule` for the registered method (from X-H1's one table), and a **warning** (not a refusal: R-89 allows `min_pairs` ≤ 3 for the demo) for every (property, harness, comparison) whose registered `min_pairs` is below the final power result's required `n`.

`Pair` carries one numeric type: an int-scale metric is `Decimal(0)` or `Decimal(1)`. W1-H may group `verdict`'s inputs into a frozen parameter object by narrowing. It may not change what they mean.

**Report obligations fixed in rev 3 (X-H2):** the NA count by reason beside every property metric and verdict row (section 3), and R-93's hidden-test disagreement warning line in report section 3 (section 7).

`report/campaign_section.py` (X-H2) renders a `Verdict` list plus the EV-20 header from the ledger reader `campaign.read(campaign_id) -> CampaignState` (X-C). Until X-C joins, it builds against fixtures of that shape.

## 9. Planned new modules and their run / grade class (ADR-0017 §1; X-D seeds them all in E1)

The rule (W0 decision, for the new modules only; rev 2, RV-SIM 4): **run** if a change to the module can alter a *measured* cell's behaviour or a measured run's plan, which means it sits on a measured cell's launch or execution path or builds a measurement plan. Otherwise **grade**. Grade is the conservative default: a grade-side change withholds verdicts until a re-grade (ADR-0017 §6), while a run-side change makes runs ineligible and forces a re-run (§5). A run-class module never imports a grade-class module (rev 2, RV-PAT 4: this is why `config.py` does not import `readiness.py`, section 2). **Consequence for W1-D to rule on at its gate (RV-SIM 4):** `campaign.py`, `readiness.py`, `alarm.py` and `gates.py` change no cell and no score, but they decide admission, eligibility and what a verdict shows, so the grade class is correct for them, and each edit to them during a campaign costs a recorded fix and a re-grade. W1-D states whether that cost is acceptable or proposes a narrower rule. A third class outside the identity would amend ADR-0017 §1 ("every `src/` file has a class") and needs an Owner request; W0 does not make one.

W1-D reviews the whole table (ADR-0017: "the run/grade classification is load-bearing and needs review at the gate"). A module not in this table needs a seam request to that phase's `identity.py` owner.

**Rev 3 (W1-D 4; R-94).**
- **Existing modules, R-94:** all five `telemetry/*` files are **run** class: the engine reads every native record at cell end for the cause and the spend stop (`engine.py:661,854`; `profiles.py:262`). The new grade-side component `gateway` is in section 6. W1-D writes ADR-0017 *Amendment 1* on its own branch (R-94).
- **"Every `src/` file", not every `*.py`:** `CLASSES` covers every file under `src/harness_bench/` except `__pycache__/` (for example `report/assets/report.js` and `gateway/schemas/*.json` are graded surfaces). **A track that adds any file under `src/`, of any type, sends a seam request to X-D for its `CLASSES` entry.**
- **The direction rule is a test:** no run-class module imports a grade-class one, with the named allowlist `RUN_IMPORTS_GRADE_ALLOWED`. It holds exactly the three `config.py` validate-time pairs W1-D names (`config.py:410,466,467`); a fourth entry is a decision request, not an allowlist edit (R-94 condition 3). `cli.py` is exempt as the composition root.
- **The cost of the grade-class tooling modules** (this section's first paragraph) is answered in W1-D's design (4.3). RV-PAT W1-D 1 adds that `cli.py` and `errors.py` are run class, so a post-baseline edit there forces a re-run; that is a W1-D design condition, not a W0 change.

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
| `src/harness_bench/grade/bench_check.py` | grade | X-F · E1 | yes (gateway lint); stdlib only by G5 |
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
| G1 | ADR-0014 §2: "No reader reads `pack` directly after this change; a guard test greps for it." | X-A1 · `tests/test_arms_guard.py` | `src/harness_bench/`, `*.py` only (rev 2: `report/assets/report.js:79,147` read `dataset.pack`, an HTML attribute, not a cell) | yes | **rev 3 (SR-1; RV-PAT W1-A 2): AST nodes, not regexes.** Rev 2's `\.pack\b` matched the comment at `grade/formal.py:256`. The scan flags every string `Constant` equal to `"pack"` outside docstrings (a docstring is the first statement of a module, class or function body when it is a string-constant `Expr`; rev 4, RV-PAT W0 delta nit) (so `x["pack"]`, `.get("pack")`, `.pop("pack")`, `"pack" in x`, `getattr(x, "pack")`, `itemgetter("pack")`), every `Attribute` named `pack`, and every `keyword(arg="pack")`. Red fixture: one temp file per form, plus a comment-only file and a docstring-only file that must not match | `PACK_READERS_ALLOWED`, **a mapping file → pinned hit count** (rev 3: a ratchet. Rev 4, RV-PAT W0 delta 3: the test asserts **equality** with each pinned count, so a count that falls is lowered in the same commit and the pin never lags; X-A1 takes the pins **after** the four-site `plan_pack` migration and the three G1 migrations, not on its base). **E1** (rev 2, RV-TA 1): `plan.py`, `board.py`, `report/pack_improvement.py`, `report/html.py`, `report/summaries.py`, `report/cli_table.py`, `report/context_growth.py`. **E3:** X-A3 lowers every count except `plan.py`'s to zero | Every other reader found on `357bce48` is **migrated by X-A1 in the guard's commit**: `views.py:525` (`pack=cell["pack"]` → `cell_arm(cell)`; X-A1's hub file), `grade/_changes.py:84` (`cell.get("pack") != "on"`), and `cli.py:145-148` `_workspace_builder` (`cell["pack"]`, `p["pack"]` → `arm_pack(plan, cell_arm(cell))`; section 13 gives X-A1 this one function in X-C's hub file). X-C, X-E, X-H2, X-J1 and X-K1 read the arm only through `cell_arm` / `arm_pack`. The listed legacy readers read the view row's `pack` attribute, which `views.py` fills with the arm id. **Rev 3 (W1-A spike SP-A3): confirmed in part.** They render an `off` / `candidate` view without raising, but say false things: `board._build_pack_effect` (`board.py:540`) prints "This run has one pack setting; no effect to show." for a two-arm run, and the header shows no pack revision. **Fix in E1 (SR-3, option (a)):** X-A1 edits the `_build_pack_effect` status text; the `html.py` header reads `plan_pack` (section 5) through X-H2. `pack_improvement`'s `no_pairs` stays an empty section until E3. X-INT still renders a two-arm report as the join check |
| G2 | ADR-0017 §1: "The classification table lives in code, once, with a test that every `src/` file has a class." | X-D · `tests/test_identity.py` | `src/harness_bench/` | yes | every file path except under `__pycache__/` (rev 3, W1-D 4; rev 2 said every `*.py`). Second test (W1-D calls it G2b), the direction rule: every import of a run-class module, resolved through `tests/import_graph.py`, whose target is grade class | none for the class table (`CLASSES` is the table); `RUN_IMPORTS_GRADE_ALLOWED` (three `config.py` pairs, R-94 condition 3) for the direction test; `cli.py` exempt (composition root) | section 9 lists every planned module; X-D seeds them all. An unplanned file of any type is a seam request |
| G3 | Architecture amendment table: "ADR-0011 C5/C9 import lint · extended to the campaign, identity, power, verdict, gate and property-grader modules" | X-D · `tests/test_architecture.py` | the files marked "yes" in section 9 | no | (rev 2, RV-TA 3) every import **resolved through the existing AST resolver** (`tests/test_architecture.py:98-99`, which resolves `node.level`; rev 3, W1-D 6: X-D extracts it to the test helper `tests/import_graph.py` in its first commit, consumed by G2, G3 and G5): a resolved target `harness_bench.gateway` or under it. Red fixtures: `from ..gateway import x`, `import harness_bench.gateway as g`, `from harness_bench import gateway` | none | ADR-0020 §5 (pure functions) and ADR-0018 (no model call): none of them needs the gateway |
| G4 | ADR-0018 §9: "The allowlist is one constant moved to a shared grading module so the three graders cannot drift (DM7)." | X-F · `tests/test_property_grader.py` | `src/harness_bench/grade/` for token 1; `grade/property.py` and `grade/_env.py` for token 2 (not `bench_check.py`: it runs inside the check's already-allowlisted environment, cannot import `_env.py` (G5), and passes that environment on; the quoted runtime test below covers it) | yes | (rev 2, RV-TA 2, RV-SIM 3, RV-SEC 6) token 1: regex `\bHOST_ENV\s*=` (word-bounded, so `DOTNET_HOST_ENV = (` at `correctness.py:49` and `mutation.py:39` does not match); token 2: `os.environ` | `HOST_ENV_DEFINERS = {"grade/_env.py"}` (token 1); `ENVIRON_READERS = {"grade/_env.py"}` (token 2: only `_env.py` reads `os.environ`, to build the allowlisted environment) | In E1 only X-F edits `correctness.py` and `mutation.py`: each imports `HOST_ENV` from `_env.py`, and `mutation.py`'s `__all__` keeps re-exporting the name (a string, so no match). **Rev 3 (req-01M41DM80):** `correctness.DOTNET_HOST_ENV` moves verbatim to `_env.py` (one home, no import cycle); `mutation.py`'s own tuple **stays where it is**: the two tuples differ (`mutation.py:39-42` adds `PROCESSOR_ARCHITECTURE`), so merging them would change a grader's environment. Token 1 is word-bounded, so `DOTNET_HOST_ENV = (` in `_env.py` does not match. X-A1 edits only `grade/_changes.py:84`; X-F edits `grading_copy` in the same file (section 3, RF-9), a disjoint hunk |
| G5 | RV-SEC 12 (no ADR trigger; W1-F seam `req-01M41C0Z`): `bench_check.py` "imports stdlib only (no `harness_bench`)" | X-F · `tests/test_property_grader.py` | `grade/bench_check.py` | no | every import, resolved as in G3, whose top-level module is not in `sys.stdlib_module_names` | none | `bench_check.py` runs inside the grading copy beside agent code and is copied alone, so it can import nothing from `harness_bench`; X-F owns both the file and the test |

**Existing guards widened by named entries in E1** (W1-F seam `req-01M41C0Z`; X-D edits `tests/test_architecture.py`, its E1 hub file, in its first commit, before X-F's code lands; both are red on arrival otherwise, as read on `357bce48`):
- D3 `test_only_procs_calls_subprocess_or_spawns` (`:44-52`, today only `procs.py` may call `subprocess`): a named constant `SUBPROCESS_CALLERS = frozenset({"procs.py", "grade/bench_check.py"})`, matched through the alias resolver in `tests/import_graph.py` (rev 4, req-01M41FVFTZ0QXT2XY7C2KHNE79 2; RV-SIM W1-D 6, RV-PAT W1-D 3; this reverses rev 3's per-call mapping. The security property, an explicit handle list, is proven at run time by X-F's `test_deliverable_cannot_write_result_pipe` and `test_forged_result_via_duplicated_handle_is_tampered`, not by the called name). Reason: `bench_check.py` runs inside the check process from the grading copy, stdlib only (G5), so it cannot import `procs`; ADR-0018 §10 names `subprocess.Popen` with an explicit handle list.
- The R-60 procs-caller set (`:228`, `allowed = {...}`) gains `grade/property`: it spawns the check through `procs.spawn` and reads the job's process list and the check's exit time.

Not scan-shaped, but quoted so no slice paraphrases them (DC-189):
- ADR-0018 §11(b): "after every grading pass of a campaign run, and before every `bench campaign` command, `bench campaign verify` checks the campaign ledger's hash chain, that every content-addressed file's name equals its hash, and `git status --porcelain bench/campaigns bench/discrimination`". X-C owns `verify`. **Rev 4 (SR-C2 e; RV-DS W1-C 4; RV-SIM W1-C 2):** the hook runs after the grading pass is sealed and `grade.lock` is released, and calls `campaign.verify_for_plan(root, plan)`, which is lock-free (no own lock, no probe; `verify` writes nothing). A finding raises HB-CMP-003 after the pass is sealed; the pass stays completed and the operator sees the failure. `campaign.py` does not exist when X-F joins, so the hook hunk in `grade/runner.py` is **X-C's**, written after X-F has joined (section 13), with `test_campaign_verify_runs_after_a_campaign_pass` in X-C's tests.
- ADR-0018 §9 (rev 2, RV-SEC 6): "**Test (red first):** `test_property_check_env_excludes_credentials` sets those four names in the grader's environment, runs a fixture check whose fixture deliverable writes its own `os.environ` keys to its evidence file, and asserts that neither the check's nor the deliverable's environment contains any of them." X-F. It is the runtime half of G4: `env=None` or `{**os.environ}` passes a token scan and fails this test.
- ADR-0015 §5a: "copy into a temporary sibling folder (`<name>.tmp-<pid>`), fsync the files and the folder, verify the rows against the copy, then `os.rename` it to the final name". Section 4 is its API: `verify` is the hook for "verify the rows against the copy" (rev 2, RV-PAT 5), and the uuid suffix narrows the `<pid>` name.
- ADR-0015 §7: "each with a seeded-bug variant TLC must reject **before the build starts**". W1-J's exit evidence.
- ADR-0021 §7: "`bench status <run_id> --alarm-after <seconds>` exits non-zero, naming the cause, when the heartbeat is stale **or** `now − last_progress_at` exceeds the threshold while cells are pending". X-K2.
- ADR-0017 §7: "The engine recomputes the run-side part of the manifest when a campaign run starts and again before each `cell.launch_intent`". X-D.

## 11. HB codes reserved per track

These ids are reserved, never reused. Each W1 design confirms or drops its rows; a dropped id is retired. **Merge preference (rev 2, RV-SIM 10):** a design merges rows that share the operator's action into one code, with the cause named in the message, and retires the rest. The phase's `errors.py` owner adds the confirmed rows in its first commit: X-D in E1, X-J1 in E2, X-K1 in E3, X-LG in E4. Existing codes are reused where the meaning is already there: `HB-RUN-004` (disk low at launch, ADR-0021 §8), `HB-RUN-005` (live run lock), `HB-USR-002`, `HB-GRD-001` (grade lock held). **Registry first (rev 4, W1-C W-7):** the error registry rejects an unknown code (`errors.py:118`, W1-C spike S-C1), so every reserved E1 row lands in X-D's first commit; X-C, X-E, X-F, X-H1 and X-A1 test their codes only after X-D has joined (a real DAG edge).

| code | meaning | track · phase |
| --- | --- | --- |
| HB-LED-007 | create-once conflict: a create-only file exists with different bytes (determinism defect; never overwritten) | X-B1 · E1 |
| ~~HB-LED-009~~ | not reserved (rev 3, S-B1 refused in part): a failed `os.link` propagates its `OSError` with the path (section 4) | — |
| HB-IDN-001 | engine identity drift: launching stopped; the stop event names the differing components | X-D · E1 |
| HB-IDN-002 | a `src/` file has no run/grade class | X-D · E1 |
| HB-PLN-001 | launch-balance bound violated (EV-17) | X-A1 · E1 |
| HB-PLN-002 | arm or role binding invalid (unbound role, a pack on `off`, a duplicate arm, more than one `off`) | X-A1 · E1 |
| HB-PLN-004 | plan refused: a measurement plan names a task that is not `ready`, or a discrimination plan names a `stub` (names every task and its status) (rev 3, SR-1) | X-A1 raises · X-D adds the row · E1 |
| HB-PLN-005 | a single-pack reader got a plan with two or more pack-bearing arms (names the arms; `plan_pack`, section 5). Raised only by `board.compare` in E1 (rev 4); X-A3 retires it in E3 when `board.compare` reads comparison pairs (rev 3, RV-PAT W1-A 1) | X-A1 · E1 |
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
| HB-CMP-010 | campaign run refused: the run is not attached, or its plan's `prereg_hash` is not the registered one (rev 2, RV-DS 1). Rev 4: also `attach` refused on a prereg-hash mismatch or a drifted tree, a pilot plan with no matching `ring_run.attached`, and a `plan_hash` mismatch | X-C · E1 |
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
| launch span = the `cell.launch_intent` row (rev 3, W1-D) | `+ identity_check_ms`; E3 adds `free_bytes` | E1 · X-D; E3 · X-K1 |
| resume record | how a resume is recorded (ADR-0021 §6: "resumed n times, with each resume's time and segment id") | E3 · X-K1, designed in W1-K |

## 13. Hub files: one owner per phase

This is the authoritative copy (the plan's table is its planning record). Another track that needs a line in a hub file sends `coord request add --to <owner>`. Hand-overs between phases are joins on `main`.

| hub file | E1 | E2 | E3 | E4 |
| --- | --- | --- | --- | --- |
| `engine.py` | X-D (rev 4: plus the `campaign_check=` keyword, section 6) | X-J1 | X-K1 (starts after X-J1 joins) | — |
| `cli.py` | X-C, except the function `_workspace_builder` (X-A1, the G1 migration; rev 2). Rev 3: X-C also carries the `cmd_plan` wiring from W1-A 3.9 verbatim (SR-2; after X-A1's `plan.parse_binding` and `plan.resolve_arms` join) and X-D's `identity_check=` keyword | — | X-K2 | — |
| `config.py` | X-A1 | — | X-A3 | — |
| `errors.py` | X-D | X-J1 | X-K1 | X-LG |
| `identity.py` | X-D | X-J1 | X-K1 | X-LG |
| `archive.py` | X-B2 | X-J1 | — | — |
| `views.py` | X-A1 | X-J1 | — | — |
| `ledger.py` | X-C | X-J1 | — | — |
| `plan.py` | X-A1 | X-J1 (`turns` only) | X-A3 | — |
| `grade/runner.py` | X-F, except lines 108-112 (`catalog_hash` → an import; X-D's first commit, rev 3) and the after-grading `verify` hook hunk (X-C, after X-F joins; rev 4, SR-C2 e) | X-J2 | — | X-LG |
| `grade/_changes.py` (rev 3) | X-A1 (line 84, the G1 migration) and X-F (`grading_copy` and the reparse-safe copy helper, section 3) in disjoint hunks | — | — | — |
| `grade/correctness.py`, `grade/formal.py` (rev 3) | X-F (`DOTNET_HOST_ENV` move; the copy-helper switch at `correctness.py:207`, `formal.py:280`; `formal`'s non-owner guard) | — | — | — |
| `grade/property.py`, `grade/bench_check.py` | X-F | — | — | X-LB |
| `procs.py`, `egress.py` | X-F | — | — | — |
| `profiles.py` | X-E | X-J2 | — | — |
| `report/html.py` | X-H2 (rev 3: plus the header's `plan_pack` lines handed over by X-A1, SR-3) | — | X-A3 | — |
| `board.py`, `report/pack_improvement.py`, `report/summaries.py` | rev 3: X-A1, only the `plan_pack` one-line migrations (section 5) and `board._build_pack_effect`'s status text (SR-3) | — | X-A3 | — |
| `report/cli_table.py`, `report/context_growth.py` | — | — | X-A3 | — |
| `report/judges.py` (rev 3) | X-B2 (`archive.attempt_dirs`, S-B3) | — | — | — |
| `status.py` | X-C (rev 4: plus `stop_reason`, `stop_diff`) | — | X-K2 | — |
| `oslock.py` (rev 4, SR-C1) | X-B1 (`acquire_then_probe`) | — | — | — |
| `workspace.py` (rev 4, S-B4 1) | X-B1: the `_land` hunk (it calls `atomic.rename_with_retry`; `RENAME_BACKOFF` moves) and the `make_writable` import only. `tests/test_workspace.py` stays X-A1's and X-B1 does not edit it (W1-B: its tests stay green unchanged) | — | — | — |
| `tests/mutations/workspace.json` (rev 4) | X-B1 (the WIN-A mutant is re-pointed at the `_land` line) | — | — | — |
| `tests/test_atomic_sites.py` (rev 4) | X-B1; X-F deletes the three grader `copytree` allowlist entries in its RF-9 commit (one granted hunk) | — | — | — |
| `tools/check_models.py`, `tests/test_check_models.py`, `models/README.md`, `docs/design/run-lifecycle-model.md` (rev 4, req-01M41F2PAKH97KH6BDGXCTA1KK) | Wave 1: W1-J (data rows only: the new seeded variants in `VARIANTS`, the `AtMostOnePrompt` → `PromptOncePerTurn` rename, the `turns` cfg, the mapping table; no change to the checker's logic) | X-J1 | W1-K (`NoResumeAfterStop`, by seam), then X-K1 | — |
| `.gitignore` (the `campaign.lock` line and, rev 3, the two `*.tmp-*` lines) | X-C | — | — | — |
| `lifecycle.py`, `models/run_lifecycle.tla` and `.cfg` | — | W1-J (model and TLC first), then X-J1 | W1-K (`NoResumeAfterStop`), then X-K1 | — |
| `bench/metrics.yaml` | X-G1 | — | X-G3 | — |
| `bench/bom.yaml` | W0 (the ten stubs); then each task track edits only its own entry | ← | ← | ← |
| `tasks/README.md` (property section) | W0; then by seam request | ← | ← | ← |
| `tests/test_<module>.py`, `tests/mutations/<module>.json` | the source module's owner in that phase | | | |
| `tests/test_architecture.py` | X-D | — | — | — |
| `tests/import_graph.py` (rev 3, the extracted AST resolver) | X-D | — | — | — |
| `tests/fixtures/plans/grid4-cells.json` (rev 3) | X-A1 | — | — | — |

Correction to the plan, recorded here: `plan.py` in E2 (the `turns` field) belongs to X-J1. The plan listed no E2 owner for it, but ADR-0015 §1 puts the turn hashes in the plan.

## 14. Open items this doc does not fix (each owned by one design)

| item | decided in |
| --- | --- |
| the turn-snapshot folder path (ADR-0015 §5: "the slice names the path") | W1-J |
| the bench-plan/2 label text (section 5's constraint) | W1-A: **decided** (rev 3, section 5) |
| how stubs are kept out of a measurement: `bench plan` refuses a non-`ready` task, or a BOM field keeps them out of `full` (then `tests/test_plan.py` goes back to 576 cells). Today nothing refuses them (section 1) | W1-A: **decided**, refuse by plan kind, HB-PLN-004 (rev 3, section 1) |
| whether `grading.started.grade_identity_hash` lands in E1 or E3 | W1-D: **decided, E1** (rev 3, section 6) |
| the run/grade cost of the grade-class tooling modules (section 9) | W1-D: answered in its 4.3 (rev 3, section 9) |
| the synthetic agent mechanism (Inferred: a stdlib ACP fake behind `Launcher`, so no `engine.py` edit) | W1-E |
| catalog anchors, area and the scenario-7 pass-rule field name | W1-G |
| `TOOLCHAIN_ENV`; the probe-host frame details beyond the field names fixed in section 3 (rev 3) and the interpreter flags; `app.kind` beyond `callable` and `wsgi` (both built in E1, rev 3); the per-property narrowing of `property_check_pass`, confirmed by its truth-table test; the ADR-0018 amendment note | W1-F |
| the `GateItem` kinds beyond `hidden-tests-nondeterministic` | W1-H |
| which ledger kinds can be derived (section 6) | W1-C |
| the alarm channel (ADR-0021 §7: "The channel is chosen at `/design-slice`") | W1-K |
| task bases, latent requirements, final budgets, case bounds from measured reference durations, offline build pinning (a build reaches no package index; network reach stays ADR-0018's accepted residual) | W1-I, W1-L |

## Gate

W0 revision 1 was reviewed by RV-PAT, RV-SIM, RV-TA, RV-SEC and RV-DS (plan, Order of operations step 5). Revision 2 applies every blocking finding and every major finding it accepts. Each finding's disposition is below. Revision 2 goes back to the three blocking reviewers (RV-TA, RV-SEC, RV-DS). The author does not clear any veto.

**Trace requirement (rev 2, RV-TA 14).** Each slice design maps every W0 contract it implements to a named test (red first), and the Test Architect checks that map at the slice's gate.

**Gate record: the five lens lines, copied verbatim** (RV-PAT and RV-SIM from their revision-1 reviews, conditions applied in revision 2; RV-TA, RV-SEC and RV-DS from their revision-2 delta re-reviews):

```
GATE w0-seam-contracts · Test Architect · PASS WITH CONDITIONS · 2 findings (rv-ta-e1e4, 2026-10-03)
GATE w0-seam-contracts rev 2 · Security & Identity · PASS WITH CONDITIONS · 2 findings (rv-sec-e1e4, 2026-10-03)
GATE w0-seam-contracts · Distributed Systems · PASS WITH CONDITIONS · 2 residual findings (rv-ds-e1e4, 2026-10-03)
GATE W0 · Patterns Expert · PASS WITH CONDITIONS · 13 findings (rv-pat-e1e4, 2026-10-03)
GATE w0-seam-contracts · Simplifier · PASS WITH CONDITIONS · 12 findings (rv-sim-e1e4, 2026-10-03)
```

Revision 2's gate passed on these five lines. RV-DS's condition 1 (DR-7 ruled so a grid-run disagreement is visible) is met by R-93 (section 7).

`GATE w0-seam-contracts · rev 3 · the Wave 1 seam answers · delta check owed by the lenses whose findings it answers: RV-TA and RV-SEC on section 3 (the wsgi kind, the probe host, the start bound, NA handling), RV-PAT on sections 5 and 10 (plan_pack, G1) · Owner request req-01M41E37FGK5CRZ7NCK3RA20JV open (section 7, one provisional clause)`

`GATE w0-seam-contracts · rev 4 · the batch-b seam answers · the rev 3 delta check is still owed and is now combined with rev 4's: see "Delta re-read list (rev 3 + rev 4)" below · req-01M41E37FGK5CRZ7NCK3RA20JV closed by R-95 · no decision request open`

## Seam requests answered in revision 2 (from W1-F, `w1f-property-e1e4`)

| request | ask | answer | section |
| --- | --- | --- | --- |
| `req-01M41C0NFEXQA0XVH4FTK9YDBD` | ten §3 amendments (probe-host child, `deliverable` field, `build` through `spawn_deliverable`, the two-phase order, the outcome order, the effective bound, derivable `measures`, `env`, `--evidence`, `-S`) | **granted in full.** Revision 2 had already made eight of the ten; W0 adopts W1-F's names and order where they differed: `in-process` kept and redefined, `app: {module, attr, kind}`, `deliverable` ∈ {`ran`, `did not build`, `did not start`}, the outcome order with the bound before the hash, exit codes 0 and 3, `out_dir/check`, `-S` | 3 |
| `req-01M41C0ZCPJ13PQ77KNC5AHQMZ` | two named allowlist entries in `tests/test_architecture.py` (X-D) for `bench_check.py` (subprocess) and `grade/property` (procs) | **granted.** Both are confirmed red on arrival otherwise (`test_architecture.py:50`, `:228`, read). X-D adds them in its first commit. The stdlib-only assertion is X-F's own (G5) | 10 |
| `req-01M41C57K2VVC7C4JGEJC18FR1` | the check reads `cases.json` (the grader's normalised copy), not `cases.yaml` | **granted.** The stdlib has no YAML parser, and the check is stdlib only (G5). `cases.yaml` stays the authored, hashed file | 3 |

## Revision 3 change table (seam id → section)

Every seam request addressed to `coord-opus-e1e4` on 2026-10-03, and every Wave 1 lens finding the Leader routed to the Coordinator. Each request's full resolution text is in its `coord request` record (`coord-core.py request list --status all`).

| seam / finding | from | answer | section |
| --- | --- | --- | --- |
| `req-01M41DAHV9XTGBY1WES1R5VQH3` | W1-G | granted in part: owner rule provisional on Owner request `req-01M41E37FGK5CRZ7NCK3RA20JV`; parameter `prop`; non-owner guard | 7 |
| `req-01M41DAHY7DX8P705CRV31MQPA` | W1-G | granted: join order (X-F skeleton first; no file grant to X-G1); two `validate_catalog` checks via X-A1; `config.PROPERTY_NAMES` | 2, 7 |
| `req-01M41DJ9Q6KTQ3RKNFVZHPRJ8V` (SR-1) | W1-A | granted: quoted ids and the string-id check; HB-PLN-004; G1 as AST nodes | 1, 5, 10, 11 |
| `req-01M41DJ9TBKNZ0JJXY79SWS5Y4` (SR-2) | W1-A | granted: X-C carries `cmd_plan` from W1-A 3.9 | 13 |
| `req-01M41DJ9Y9WYKGDX5N37N8FFN0` (SR-3) | W1-A | granted, option (a): `board.py` text by X-A1, `html.py` header through X-H2 | 10, 13 |
| `req-01M41DK5M0WS3PNX3WFNZ222WW` (SR-4) | W1-A | granted: golden over `tests/fixtures/plans/grid4-cells.json` | 5, 13 |
| `req-01M41DJDH521RE0M4QJJK1FRTD` | W1-D | granted, all seven and both riders; with R-94 | 6, 9, 10, 12, 13 |
| `req-01M41DM7XQG9GYVR32TJ762V67` | W1-F | granted in part: pilot items `check-tampered`, `suspend-detector-blind`; NA counts in the report. Refused: a verdict-label change (ADR-0020's rule) | 3, 8 |
| `req-01M41DM80KBD42GYARADW4V6HZ` | W1-F | granted: `DOTNET_HOST_ENV` moves to `_env.py` | 3, 10 |
| `req-01M41DMZX6GYN6NP8PRFXBFZDZ` (S-B1) | W1-B | granted in part: `TEMP_RE`, `is_temp_name`, `sweep_temps`, `make_writable`. Refused: HB-LED-009 (the `OSError` propagates; no volume in scope lacks links) | 4, 11 |
| `req-01M41DMZZXE2KY9XDJJ5QZCX51` (S-B2, S-B3) | W1-B | granted: three `.gitignore` lines (X-C); `archive.attempt_dirs` the one reader | 4, 6, 13 |
| `req-01M41DPBSM9GET14FC3K4N785S` | W1-I | granted: `factory`, `args`, `paths`, `{state_dir}`, the PEP 3333 environ, app output off the protocol channel | 3 |
| `req-01M41DT67G68NQ7Y7D8YQM1A98` | W1-I | granted in part: start bound = `bounds_ms[interface]` (not a case bound); `start_ms` recorded | 3 |
| `req-01M41EPKRBCVQ28MS96CHNTDRZ` | W1-H | granted: `seed_for` takes 15 hex digits (60 bits) | 8 |
| `req-01M41EPKVYZQ9NH97HEJR7M5PY` | W1-H | granted: `pilot` gains `unbiased_failures`; X-E's `readiness.unbiased_failures` | 3, 8 |
| Coordinator ruling C-1 (RV-PAT W1-I 1-3) | Leader | `app.kind: wsgi` built in E1 by X-F (option (a)); wsgi frame field names fixed | 3 |
| RV-PAT W1-A 1, 5 | Leader | bench-plan/2 drops the top-level `pack`; `plan_pack` accessor; four readers migrated in E1; HB-PLN-005 | 5, 11, 13 |
| RV-PAT W1-A 2 | Leader | G1 tokens widened to every `"pack"` constant, attribute and keyword; allowlist is a per-file count ratchet | 10 |
| RV-PAT W1-D 2 (W1-D F-1) | Leader | `plan.campaign.identity` is the chain's effective run side, checked at plan time and at `grid.attached` (X-C, W1-C) | 6 |
| RV-SEC W1-F RF-9 | Leader | one reparse-safe copy helper (X-F) for the three grading copies | 3, 13 |
| RV-SIM W1-B 1 | Leader | `recover_archive` built by X-K1 in E3 | 4 |
| RV-SIM W1-B 8 | Leader | the strict temp regex is the W0 text | 4 |
| RV-SIM W1-G 2 | Leader | the freeze-check (e) exception and `corrected_from` are deferred to a red-gate trigger | 7 |
| RV-SIM W1-G 3, RV-TA W1-G 8 | Leader | owner rule raised to the Owner (`req-01M41E37FGK5CRZ7NCK3RA20JV`) | 7 |
| RV-PAT W1-G 1 | Leader | `formal`'s non-owner guard stated, with a real-pass test | 7 |
| R-93 (DR-7), R-94 (DR-8) | Owner | recorded | header, 6, 7, 8, 9 |

**ADR amendment notes recorded with rev 3** (appended; no decision text edited): ADR-0014 *Amendment 1* (W1-A section 12, plus `plan_pack` and the G1 ratchet), ADR-0018 *Amendment 1* (the probe host, `-S`, the ack, `cases.json`, the `wsgi` kind, the start bound), ADR-0019 *Amendment 1* (W1-G U5: the fixtures, the chain, the golden that cannot move, the expected set, `also_graded_by` provisional). ADR-0017 *Amendment 1* is W1-D's (R-94).

**Who re-reads what (rev 3 is a contract change).**

| slice / track | re-read |
| --- | --- |
| W1-F (delta for C-1) / X-F | 3 (wsgi kind, frames, probe-host items, start bound, NA rule, RF-9 copy helper, `DOTNET_HOST_ENV`); 6 (`grade_identity_hash` in E1, `catalog_hash` import); 7 (`prop`, owner clause, non-owner guard, join order); 10 (G4, `SUBPROCESS_CALLERS`, `tests/import_graph.py` for G5); 13 |
| W1-I / S1 | 3 (wsgi kind and frames, `{state_dir}` path, `paths` rule, app-output capture, start bound) |
| W1-A / X-A1 | 1, 5 (quoted ids, golden fixture, top-level `pack` removal, `plan_pack`), 7 (`PROPERTY_NAMES`, two `validate_catalog` checks), 10 (G1 tokens and ratchet, SR-3), 11, 13 |
| W1-D / X-D | 6, 9, 10 (G2, direction test, G3 resolver), 11 (HB-PLN-004, HB-PLN-005 rows for `errors.py`), 12, 13 |
| W1-G / X-G1, X-G3 | 7 (all rev-3 bullets) |
| W1-B / X-B1, X-B2 | 4, 11 (HB-LED-009 refused), 13 (`judges.py`) |
| W1-C / X-C | 4 (`sweep_temps`, `is_temp_name` in `verify`), 6 (`.gitignore`, effective identity at plan time and attach, `identity_check=` keyword), 13 (`cmd_plan` wiring) |
| W1-H / X-H1, X-H2 | 3 (NA rule), 8 (two new GateItem kinds, `pilot`'s third parameter, `seed_for` 60 bits, report obligations), 7 (R-93 warning line), 13 (`html.py` header lines) |
| W1-E / X-E | 3 (NA rule), 3 `paths` readiness check (HB-RDY-005), 8 (`readiness.unbiased_failures`) |
| W1-K / X-K1 | 4 (`sweep_temps`; `recover_archive` is now X-K1's) |
| X-A3 (E3) | 4 (`attempt_dirs`), 5 (`plan_pack` readers to migrate), 10 (G1 counts to zero) |

## Revision 4 change table (seam id → section)

Every seam request addressed to `coord-opus-e1e4` after rev 3, and every cross-slice finding the Leader routed to the Coordinator from the RV-PAT, RV-SIM, RV-SEC and RV-DS reviews of W1-B, W1-C, W1-D and W1-H. Each request's resolution text is also in its `coord request` record.

| seam / finding | from | answer | section |
| --- | --- | --- | --- |
| `req-01M41F6QRJ49VE2VES5Y527K61` (SR-C1) | W1-C | **granted in part.** `oslock.acquire_then_probe` is granted as the one protocol function, widened to a set of `others` (RV-PAT W1-C 3, RV-DS concurs) with `between` keyword-only and defined between the two operations (RV-PAT 4, RV-DS 3). **Refused:** `oslock.py` to X-C. It goes to **X-B1**: X-F is the first caller and joins long before X-C (X-C waits on X-B1, X-D, X-H1, X-A1), and X-B1 already works on the lock-aware sweep | 6, 13 |
| `req-01M41F6R2NR3JTJDA1JMX9V0KX` (SR-C2) | W1-C | **granted.** (a) `admitted` is int 0/1; (b) the test is "never both proceed", both-refused allowed; (c) a pilot plan (`prereg_hash: null`) is admitted by `ring_run.attached`; (d) attach refusal is HB-CMP-010; (e) the after-grading `verify` runs after `grade.lock` is released, through `campaign.verify_for_plan`, now lock-free (RV-SIM, RV-DS 4); the hook hunk is X-C's. Also from W1-C §0: the ledger-prefix witness rule (W-6), HB-CMP-003 → exit 5 (W-8), every HB code registered in X-D's first commit (W-7) | 6, 10, 11, 13 |
| `req-01M41FDXHDYP8YG3HPDNDGQHAN` (S-B4) | W1-B rev 2 | **granted, all five.** (1) public `rename_with_retry`, `RENAME_BACKOFF` moves to `atomic.py`; X-B1 owns the `_land` hunk of `workspace.py` and `tests/mutations/workspace.json` (`tests/test_workspace.py` stays X-A1's, unedited); (2) `sweep_temps(target, lock)` checks the lock; (3) the discrimination sweeper is X-E; (4) `verify` names temps and `lstat`s the lock; (5) `make_writable` lstat-first, adds `S_IWUSR` | 4, 13 |
| `req-01M41FVFTZ0QXT2XY7C2KHNE79` | W1-D rev 2 | **granted, both.** (1) `Status.stop_reason`, `stop_diff` (X-C); (2) `SUBPROCESS_CALLERS` is a two-path frozenset through the alias resolver | 6, 10, 13 |
| `req-01M41EX52AX93PQS1FHYCSA0YG` | W1-H | **granted, all three**, with the arity ruled once: `expected_na` keyword-only, default empty; its source is X-E's `readiness.expected_na` (reference-side `{na}`); `slots` required int ≥ 1; `planned_reps_per_task` optional; `pairing_unit` ∈ {`unpaired`, `task-harness-rep`} in both power inputs and prereg | 8 |
| `req-01M41F2PAKH97KH6BDGXCTA1KK` | W1-J | **granted.** W1-J edits `tools/check_models.py`, `tests/test_check_models.py`, `models/README.md` and `docs/design/run-lifecycle-model.md` for data rows only (variants, the invariant rename, the `turns` cfg, the mapping table); the checker's logic is unchanged (`check_models.py:36-69` is a table, `:116-137` reads it) | 13 |
| RV-PAT W1-H 3, W1-C 5a; RV-SIM W1-C 8 | Leader | `gates.pilot` arity ruled once (above) | 8 |
| RV-PAT W1-C 5b; W1-H F13 | Leader | failed reader: `None` → HB-USR-002 in `pilot`; X-C's call site maps an exception to `None` and prints it; no row | 8 |
| RV-PAT W1-C 5c; R-96 c1 | Leader | `register` preview prints `alpha_per_test` and `level_rule` (X-C, from X-H1's one table) | 8 |
| RV-PAT W1-C 5d; W1-H R-H1 | Leader | `register` preview warns when `min_pairs` < required `n` (X-C); a warning, not a refusal | 8 |
| W1-C OI-1 | W1-C → W1-H, unanswered | ring eligibility read from the attached runs' plans (after `plan_hash`); the campaign's ring is the first grid run's; absent plan → ineligible `not recorded` | 6 |
| W1-C OI-2 | W1-C → W1-H, unanswered | the grid a prereg names is the final power inputs; no prereg field | 6 |
| W1-C OI-3 | W1-C → W1-H, unanswered | `gates.admission` (X-H1), EV-8 exact rule; X-C's `admit` records its output; no operator override in E1 | 8 |
| RV-SEC W1-C 7 | Leader | **`plan_hash` on `grid.attached` and `ring_run.attached`** (a W0 refinement; the cell-set alternative refused as a second statement of the grid); `check_plan` re-hashes `components` (W1-C's) | 6 |
| RV-SEC W1-C 5 | Leader | `attach` also checks the tree's run side under the lock (HB-CMP-010) | 6 |
| RV-SEC W1-C 3, 4; RV-PAT W1-C 2; RV-DS W1-C 1 | Leader | the git witness keys on content, not status letters; HEAD blob cut at its last newline; `h`/`S` flags and stray ignored paths are findings; the committed-rewrite case stays W1-C's (fix or named residual) | 6 |
| RV-SIM W1-C 2 | Leader | `status` and stand-alone `verify` are lock-free reads | 6 |
| RV-SIM W1-C 1 (OI-4) | Leader | `ring_run.attached.tag` dropped (always `pilot`); `ring_hash` kept, its reader is the run-side check | 6 |
| RV-DS W1-C 2 | Leader | the run side takes its own lock, then probes `campaign.lock` and re-reads, through an injected `campaign_check=` in `engine.py`: X-D adds the keyword, X-C the function and the `cli.py` line | 6, 13 |
| RV-DS W1-C 7 | Leader | lock domain stated as an `assume:` | 6 |
| RV-PAT W1-C 1 (BLOCK: no re-pilot path after a fix in `registered`) | Leader | **no W0 change.** W0 §6 fixes kinds and fields, not the state table; either fix RV-PAT names fits inside W0 (no kind added). It goes back to W1-C's author in rev 2 | — |
| W1-F §5.11 (found while answering SR-C1) | Coordinator | superseded: the grading side uses `acquire_then_probe` with HB-GRD-007, not a `campaign.lock_held` pre-check with HB-CMP-001; `campaign.verify` moves to X-C's hook hunk | 6, 10 |
| RV-SEC W1-F rev 3 findings 2, 3, 4, 6 | Leader | case-id charset (X-F writer, X-E readiness); fresh reparse-safe `{state_dir}`; the app-output cap bounds evidence, not disk; the capture measures accidental logging only (S1 `leak-2` text) | 3 |
| RV-TA W1-F rev 3 finding 5 and the W0 owner gap | Leader | the `paths` readiness test is X-E's; the frame and environ golden is X-F's | 3 |
| RV-PAT W0 rev 3 delta (`eval-review-pat.md`, last section) 1-3 and nits | Leader | 1: the `SUBPROCESS_CALLERS` frozenset (as W1-D's seam). 2: `plan_pack(plan, *, strict=False)` raises only for `board.py`'s `strict=True` call; display readers render `several packs` (as W1-A rev 2, `92e977b2`, already builds). 3: the G1 ratchet asserts equality; pins taken after the migrations. Nits: quoted ids in `comparisons`; "docstring" defined; HB-PLN-005 "raised only by `board.compare`"; G2b named | 5, 10, 11 |
| RV-TA W1-B R2-1 | Leader | the rename-to-row-append recovery test is X-K1's (and W1-J's for snapshots), not W1-B's | 4 |
| RV-TA W1-A 3 vs RV-SIM W1-A 7 (conflict) | Coordinator | **TA 3 wins:** keep `test_plan_py_imports_no_campaign_or_identity_module` with a red fixture. G2's direction test cannot catch it for `identity`, which is run class like `plan.py` (section 9), and G3 checks only gateway imports | 5 |
| R-95, R-96 | Owner | recorded; section 7's provisional clause closed; ADR-0020 *Amendment 1* written | header, 7, 8 |

**ADR amendment notes recorded with rev 4** (appended; no decision text edited): ADR-0020 *Amendment 1* (R-96 ruling 3: `seed_for` replaces the plan seed; R-96 ruling 1: the `holm` level is `alpha/m`). It is a separate commit on this branch so the Leader can land it before X-H1's first commit even if rev 4's review takes longer.

### Delta re-read list (rev 3 + rev 4)

Rev 3's delta check was never run. It is combined here with rev 4's so each lens reads once. The author does not review it.

| lens | rev 3 delta (owed) | rev 4 delta |
| --- | --- | --- |
| **RV-TA** (hard veto) | §3: the `app.kind: wsgi` bullet; the probe-host items (frames, environ, `{state_dir}`, `paths`, app output, start bound); "NA is never a dropped cell"; the reparse-safe copy (RF-9) and its three-grader test; the `env` bullet (`DOTNET_HOST_ENV` move) | §3 "Section 3 additions (rev 4)" (case ids, `{state_dir}`, the two owners); §4 `rename_with_retry`, `sweep_temps(target, lock)`, `make_writable`; §6 `acquire_then_probe` and its barrier definition, the "never both proceed" test, lock-free reads, the git-witness rule and its cut-at-newline case, `plan_hash`, the run-side check in the engine; §8 `pilot` arity, `readiness.expected_na`, the failed-reader rule, `admission`, the power inputs; §10 D3 |
| **RV-SEC** (hard veto) | §3: the `wsgi` environ, app-output capture, the start bound, the `paths` containment rule, the NA rule, the RF-9 copy helper | §3 "Section 3 additions (rev 4)" (the case-id charset, `{state_dir}`, what the app-output capture measures); §4 S-B4 (sweep lock check, `make_writable` link rule, `verify` names temps, non-regular lock refused); §6 the git witness (content-keyed; `h`/`S` flags; ignored paths), `plan_hash`, the attach-time drift check; §10 D3 (the `Popen` narrowing is dropped: confirm the runtime handle-list tests carry the property) |
| **RV-PAT** | **done** (PASS WITH CONDITIONS, `eval-review-pat.md` last section; conditions applied in rev 4) | §5 `plan_pack(strict=)` and §10 the G1 ratchet text (its own conditions, as applied); §6 `acquire_then_probe` signature; §8 the one `pilot` arity and `admission` in `gates.py`; §13 the new rows (`oslock.py`, `workspace.py`, `tests/test_atomic_sites.py`, the model-check files) |
| **RV-DS** (hard veto; rev 4 only) | — | §6 the lock protocol (set of `others`, `between`), the run-side check after the run lock, lock-free reads, the witness cut at the last newline, the lock-domain `assume:`; §10 the lock-free after-grading hook |

`RV-SIM` has no owed delta: rev 4 applies its W1-C findings 1, 2 and 8 and W1-D 6 as asked.

### Who re-reads what (rev 4 is a contract change)

| slice / track | re-read |
| --- | --- |
| **W1-C rev 2 / X-C** | 6 (all rev-4 bullets: `admitted` int, `plan_hash`, freeze steps 1 and 3, `run_side_check`, `acquire_then_probe`, lock-free reads, the git witness, OI-1, OI-2, `stop_reason`), 4 (sweep scope, `verify` warnings), 8 (`pilot` call with `expected_na`, the failed-reader rule, `admission`, the `register` preview), 10 (the hook hunk), 11 (HB-CMP-010; registry first), 13 |
| W1-H / X-H1, X-H2 | 8 (arity, `expected_na`, `admission`, power inputs, `alpha_per_test` and `level_rule` from one table); ADR-0020 *Amendment 1* |
| W1-B / X-B1 | 4 (as granted), 6 (`acquire_then_probe` is X-B1's), 13 (`oslock.py`, `workspace.py`, `tests/mutations/workspace.json`, `tests/test_atomic_sites.py`) |
| W1-D / X-D | 6 (`campaign_check=` keyword in `engine.py`; `stop_reason` and `stop_diff` are X-C's), 10 (D3), 11 (registry first), 13 |
| W1-F / X-F | 6 (the grading side's `acquire_then_probe`; W1-F §5.11 superseded), 10 (the hook moves to X-C), 13 (`grade/runner.py`, `tests/test_atomic_sites.py`) |
| W1-E / X-E | 4 (X-E sweeps `bench/discrimination/<task>/` under its own lock), 8 (`readiness.expected_na`) |
| W1-J | 13 (the model-check files) |
| W1-K / X-K1 | 4 (`sweep_temps` now takes the caller's lock: resume passes the run lock) |
| W1-A / X-A1 | 13 (`workspace.py` source belongs to X-B1 for one hunk; `tests/test_workspace.py` stays X-A1's); the TA 3 / SIM 7 ruling in the change table |

## Review disposition

One row per finding id per lens. *Accepted in part* names the rejected part and why. "Section changed" is the section of this doc that carries the change.

| lens · # | severity | disposition | section changed | reason (when not fully accepted) |
| --- | --- | --- | --- | --- |
| TA 1 | blocking | accepted | 10 G1, 13 | — the E1 allowlist gains `cli_table.py` and `context_growth.py`; `views.py`, `_changes.py` and `cli.py` `_workspace_builder` are migrated by X-A1 in the guard's commit |
| TA 2 | major | accepted | 10 G4 | — word-bounded token; `DOTNET_HOST_ENV` stays where it is (the two tuples differ) |
| TA 3 | major | accepted | 10 G3 | — the AST resolver handles `node.level` (`test_architecture.py:99`, read) |
| TA 4 | blocking | accepted | 3 (outcome order, framing, ack) | — the order is suspend, bound, hash mismatch, other §10a(b), malformed, did-not-build, score (W1-F's order, from its spike); stdin is closed on every path; exit 0 after the ack, 3 after a refusal |
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
| SEC 1 | blocking | accepted | 3 (`in-process` redefined) | — the check never imports agent code; a probe-host child does. The value keeps its ADR-0018 §12 name, because the old meaning no longer exists (the reviewer's rename applied only "if in-process is kept for the old meaning") |
| SEC 2 | major | accepted | 3 (`env`), 11 (HB-RDY-005) | — |
| SEC 3 | major | accepted | 3 (two phases) | — |
| SEC 4 | major | accepted | 3 (outcome row 2) | — |
| SEC 5 | minor | accepted | 3 (`measures`) | — |
| SEC 6 | major | accepted | 10 G4, quote list | — |
| SEC 7 | major | accepted in part | 3, 14 | `build` goes through `spawn_deliverable` (accepted). Rejected: "readiness rejects a build that needs a package index", because readiness cannot observe a build's network reach. The task declares an offline build (W1-I), and network reach stays ADR-0018's accepted residual |
| SEC 8 | minor | accepted | 3 | — `out_dir/check` (W1-F's name) |
| SEC 9 | minor | accepted | 3 (interpreter flags, deviations) | — `-S` (W1-F seam): no site-packages, global or user. Not `-I`, which drops the script folder from `sys.path`, so `import bench_check` would fail. The amendment note goes to W1-F |
| SEC 10 | minor | accepted | 4 | — |
| SEC 11 | minor | accepted | 6 | — ADR-0017 §1 already says `sys.platform` |
| SEC 12 | minor | accepted | 9, 10 G5 | — G5 is in X-F's own test file (W1-F seam), so X-D's file is not touched for it |
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
