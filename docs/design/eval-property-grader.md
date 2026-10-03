---
id: "design-eval-property-grader"
title: "Design W1-F: the hidden-check runner and the property grader (boundary B7, security-sensitive)"
type: design
status: proposed
owner: "@timianmalloo"
phase: "Enterprise evaluation E1: Wave 1 design slice W1-F (built by X-F in E1; loopback by X-LB in E4)"
tags: [benchmark, grading, property-grader, hidden-check, security, trust-boundary, b7, evaluation-campaign, wave-1]
links:
  - { to: spec-enterprise-evaluation, rel: implements }
  - { to: arch-evaluation-campaign, rel: implements }
  - { to: design-eval-seam-contracts, rel: depends-on }
  - { to: adr-0018-hidden-check-harness, rel: depends-on }
  - { to: adr-0010-untrusted-cell-output, rel: depends-on }
  - { to: adr-0012-proportionate-security, rel: depends-on }
  - { to: adr-0013-native-cells, rel: depends-on }
  - { to: adr-0019-catalog-0-7-property-metrics, rel: depends-on }
  - { to: rulings-register, rel: depends-on }
  - { to: note-20261003-spike-e1-job-alone, rel: depends-on }
  - { to: note-20261003-spike-e1-handle-list, rel: depends-on }
  - { to: note-spike-phase1-probes, rel: depends-on }
  - { to: note-20260924-spike-a9-host-sleep, rel: depends-on }
  - { to: design-phase3-graders, rel: refines }
  - { to: coordination-eval-campaign, rel: relates-to }
review-by: "2026-10-17"
summary: >-
  One registered `property` grader (R-90): runner.applicable narrows it to the task's property; it runs the hidden
  tests through correctness.grade() in their own copy, then the task's hidden check in a fresh copy, in a new Job
  Object, started DETACHED with the base interpreter and the grading environment allowlist. The check never imports
  agent code: in-process probes go through a bench_check probe-host child (RV-SEC F1; the forgery was reproduced
  3/3 by spike SP-F2). The grader accepts one result document from a live, lone check, acknowledges it with one
  byte, then classifies by a fixed precedence into the closed outcome set (HB-CHK-001..004, a measured 0, or
  scores). Every ADR-0018 STRIDE row has a control, a test node and a disposition. Gate pending.
---

# Design W1-F: the hidden-check runner and the property grader

**Status:** proposed, revision 1, gate pending (see [Gate record](#gate-record)). **Author:** W1-F, session `w1f-property-e1e4` (Claude Opus 5.5). **Grounded at:** `main` `5092455c` (W0 and Owner ruling R-90). **Builds:** X-F in E1. X-LB adds loopback in E4.

**Provisional sections.** RV-SEC and RV-TA both blocked W0 (reviews `review/eval-sec` `8b2f910e` and `review/eval-ta` `6ef9dad1`). This design is written to the fixes. It needs W0 §3 text changes, which this slice may not make. Sections marked **provisional (seam ...)** follow the three seam requests in [Seam requests and decisions](#16-seam-requests-and-decisions). They become final when the Coordinator amends W0.

## 1. Responsibility and boundaries

**One responsibility.** The grader turns one archived property cell into the narrowed property metric rows: `property_check_pass` plus the secondaries tagged with the task's property. It does this without letting the agent's deliverable decide its own score.

| It owns | It borrows (by identity, read-only) |
| --- | --- |
| `grade/property.py`: the grader, the check runner, classification and scoring | the archive `run_dir/archive/<cid>/attempt-<n>/ws` (`CellInput.archive`) |
| `grade/bench_check.py`: the stdlib helper copied into every grading copy | the task's `oracle/check/` and `task.yaml` (`CellInput.task_dir`, `.task`) |
| `grade/_env.py`: the one grading-environment allowlist (ADR-0018 §9, DM7) | `correctness.grade()`, the one definition of "hidden tests pass" (R-90 c2) |
| the `property` line in `runner.GRADERS` and the `property:` narrowing in `runner.applicable` | the catalog entries with their `property:` tag (W1-G / X-G1) |
| `procs.spawn(console=False)`, `CellProcess.exit_time()`, `procs.now_filetime()` | `host.SleepDetector` (spike A9) |
| the `task_canary` class in `egress.py` (R-E9) | `campaign.verify` and the campaign lock (X-C; ADR-0018 §11) |

**What crosses the boundary.** Into the grader: a `CellInput`. Out: one `Score` per applicable metric, plus one evidence file. Into the check: argv, an allowlisted environment, a fresh grading copy. Out of the check: one JSON line on its stdout, and nothing else the grader reads as a result.

**Out of scope here.** Loopback fakes and listeners (E4, X-LB; this design names the seam only, §5.5). Task content: probes, payloads and S1's check (W1-I). The rework, no-guessing and simplicity strategy helpers (X-J2, X-LG). They plug into §5.2's strategy table. No code is written in this slice.

## 2. Grounding (facts this design stands on)

Labels: **Verified** means read or run by this slice. **Inferred** means reasoned, with the confirming check named.

| # | Fact | Source | Label |
| --- | --- | --- | --- |
| G1 | A grader is `grade_cell(inp) -> Mapping[str, Score]`. A `Score` carries a reason only when its value is `None`. | `grade/__init__.py` (`Score.__post_init__`) | Verified |
| G2 | The runner gives each grader "every `kind: score` catalog metric of those graders". Nothing passes one grader's output to another. GradedOncePerPass raises HB-GRD-004 on a missing, duplicate or outside key. | `grade/runner.py` (`applicable`, `_grade_cell`, `_check_complete`) | Verified |
| G3 | `correctness.grade(ws, task_dir, oracle, out_dir, run_dir, timeout, work_dir)` copies the tree to `work_dir/work`, runs the oracle through `procs.run`, removes the copy and writes `oracle.log` into `out_dir`. | `grade/correctness.py:196-268` | Verified |
| G4 | `HOST_ENV` is defined twice (`correctness.py:48`, `mutation.py:38`). `DOTNET_HOST_ENV` already differs between them: mutation adds `PROCESSOR_ARCHITECTURE` (`mutation.py:39-42`). That is a live instance of the drift ADR-0018 §9 exists to stop. | read | Verified |
| G5 | `procs.spawn` creates the process `CREATE_SUSPENDED \| CREATE_NO_WINDOW`, `close_fds=True`, assigns it to a kill-on-close job with breakaway never allowed, then resumes it. `Job.pids()` reads `JobObjectBasicProcessIdList`. A failed query raises. | `procs.py` (`_spawn_win32`, `Job`) | Verified |
| G6 | D3: only `procs.py` may call `subprocess.Popen`. R-60: only `{engine, gitsafe, grade/correctness, host, plan, procs, tools, workspace}` may reach `procs`. | `tests/test_architecture.py:44-51, 228` | Verified |
| G7 | With the base interpreter and `DETACHED_PROCESS`, the job's process list is exactly `{check}` before and after the deliverable. Under the venv launcher or `CREATE_NO_WINDOW` it is not. | spike E1-S3 | Verified |
| G8 | `Popen(close_fds=True)` with explicit stdio is the handle list: a child cannot reach an inheritable pipe that is not in the list. `OpenProcess` plus `DuplicateHandle` still can, so ADR-0018 §10a is load-bearing. | spike E1-S2 | Verified |
| G9 | Grandchildren never leave the cell's job. Nothing survives `TerminateJobObject`. | probe N4 | Verified |
| G10 | `SleepDetector` flags a suspend when wall-clock time minus unbiased time exceeds its gap. A missing unbiased reading returns "not slept". | `host.py:154-172`; spike A9 | Verified |
| G11 | Views read the latest completed pass, and every pass grades every archived cell. So "re-run next pass" (HB-CHK-004) needs no new mechanism. | `views.py:178`; `runner.py` docstring | Verified |
| G12 | The base interpreter runs `json`, `ctypes`, `subprocess`, `msvcrt` and `hashlib` under `-S`, with no `site-packages` on `sys.path`. | run 2026-10-03, CPython 3.14.6 | Verified |
| G13 | `plan.tree_hash(base, files)` is the one content-address recipe (CRLF read as LF). | `plan.py:93` | Verified |
| G14 | The catalog (0.6) has no `property` key on any metric today. | `bench/metrics.yaml` | Verified |
| G15 | A module-body forgery inside the check process is **accepted** as a valid result: 3 of 3 trials. | spike SP-F2 (§15) | Verified |

Quoted rules this design rests on (DC-189):
- ADR-0018 §1: "The check starts the deliverable as its own child (so it is in the same job), only through `bench_check.spawn_deliverable`".
- ADR-0018 §10a(b): "It accepts the result only if **all** hold: the pipe carried exactly one JSON document and no trailing bytes; when that document's first byte arrived, the grader's immediate job query showed the check alive and alone in the job; the check then exited by itself with the expected exit code, after the document arrived ...; and the outer bound did not fire."
- ADR-0018 STRIDE row (Tampering): "the check tree hashed before and after; a mismatch is NOT_RECORDED `check tampered`".
- EV-1: "**Given** a cell whose deliverable does not build or start **When** the hidden check runs **Then** the primary metric is recorded as 0 with reason `deliverable did not build` (a measured failure)."
- R-90 c2: "The property grader calls `correctness.grade(ws, task_dir, oracle, out_dir, run_dir, timeout, work_dir)` ... in its own grading copy ..., never a re-implementation".
- R-90 c4: "`rework.py`, `noguess.py`, `diffstats.py` ... are called by `property.grade_cell` and are not registered in `GRADERS`".

## 3. Data model (settled first)

**Bounded context.** Grading. Ubiquitous language: *hidden tests* (the correctness oracle), *hidden check* (the task's `oracle/check/`), *case* (one declared probe, fault or static check), *outcome* (a case's closed result), *result document* (the check's one JSON line), *acknowledgement* (the one byte), *check run* (one execution of the check for one cell in one pass), *measured 0* versus *NOT_RECORDED*.

**Aggregate.** `CheckRun`. Its root is identified by `(grading_id, cell_id)`. Its one invariant: **the grader accepts at most one result document, and only from a live check that is alone in its job, whose own clean exit follows that document. Otherwise every metric of the run is NOT_RECORDED.** Everything else is a value object: `CaseDecl` (id, kind, bound), `CaseResult` (id, outcome, duration), `ResultDoc`, `Classification` (code, reason). A `CheckRun` references the cell, the task version and the pass by identity only. It is never persisted as an entity. It is the unit of one transaction: the grader writes its rows and its evidence file once.

**Durable representation. No new fact table.** The grader writes into two existing stores:

| Store | Grain ("one row is exactly one ...") | Writer | Compute readers | History rule |
| --- | --- | --- | --- | --- |
| `scores` ledger fact (existing, ADR-0006) | one metric value of one cell in one grading pass, identified by `(grading_id, cell_id, metric_id)` and recorded at the pass | `runner._score` | views, board, readiness (X-E), verdicts and gates (X-H1), the campaign section (X-H2) | append-only per pass (existing); a re-grade is a new pass, never an update |
| `grading/<gid>/<cid>/property/property.json` (new evidence file) | one check run: the inputs a score row was derived from, identified by `(grading_id, cell_id)` and recorded when the grader returns | `property.grade_cell` | `Score.evidence` pointers; X-E's discrimination record (the hidden-test agreement, R-90 c3); the pilot gate (EV-14); reports via the egress gate | written once per pass, under the pass's own `out_dir`; never rewritten |

**Measures and their additivity (DM9).**

| Metric | Built here? | Class | Derivation (derive-don't-store, DM7) |
| --- | --- | --- | --- |
| `property_check_pass` | yes | non-additive across metrics; additive as a pass count across cells | derived by the grader from the hidden-test result and the cases (§5.7); never taken from the check |
| `exploit_probes_blocked` | yes | non-additive (a ratio: recompute from counts, never average ratios) | `blocked ÷ probe cases`, by the grader from `cases` |
| `fault_suite_pass` | yes | non-additive (ratio) | `passed ÷ fault cases`, by the grader from `cases` |
| `idempotency_violations` | yes (E4 tasks) | additive across cells (a count) | reported by the check in `measures`; it cannot be derived from outcomes |
| `rework_ratio`, `turn1_tests_pass` | no (X-J2, E2) | — | strategy helper `rework.py` |
| `hallucinated_symbol_errors`, `verified_before_use` | no (X-LG, E4) | — | strategy helper `noguess.py` |
| `size_vs_reference`, `new_abstractions`, `new_dependencies` | no (X-LG, E4) | — | strategy helper `diffstats.py` |

The derived score rows are the ledger's record. The evidence file keeps their inputs, so a **rebuild test** recomputes every derived row from `property.json` and asserts equality (`test_derived_measures_rebuild_from_evidence`).

**Evidence file `bench-property-evidence/1`.** Every field has a writer (`property.grade_cell`) and a named reader:

| Field | Reader |
| --- | --- |
| `task`, `task_version`, `cell_id`, `grading_id`, `property`, `seed`, `interface` | discrimination record (X-E), re-grade determinism test |
| `hidden_tests[tree] = {passed, partial_credit, reason, evidence, hidden_tests_ms}` | R-90 c3: X-E compares `final.passed` with the pass's `pass_at_1` row ("hidden tests non-deterministic") |
| `check.classification = {code, reason}`; `check.deliverable` | pilot gate (EV-14), report |
| `check.cases[] = {id, kind, outcome, duration_ms}`; `check.measures` | rebuild test; the first failing case for the report (W0 measured-0 rule) |
| `check.hash_before`, `check.hash_after` | HB-CHK-002 evidence |
| `check.handshake = {first_byte_ft, job_view_at_arrival, documents, trailing_bytes, acked, exit_code, exit_ft, outer_bound_s, bound_fired, suspended}` | HB-CHK-002/003/004 evidence; SRE |
| `check.wall_ms`, `check.stdio[]` (each file's path, bytes, `truncated`) | SRE; report (egress-scanned) |

No field is a free text from the deliverable. Deliverable stdio is copied to files beside the evidence, at most 64 KiB each, and those files reach a judge or a report only through `egress.check` (US-47).

**Schema changes.** The only one is the catalog `property:` tag (X-G1 writes it; ADR-0019). It is additive: a metric without the tag keeps today's behaviour. So there is no migration and no backfill. A re-grade of an old run under 0.7 adds no property rows for tasks that do not name `property` (ADR-0019 item 6, `test_catalog_version`).

## 4. Delivery phasing and mock-substitutable seams

- **E1 slice (this build).** Security task S1, `interface: in-process` only. Real parts: the runner narrowing, `property.grade_cell`, `bench_check` (spawn, sweep, write-once, probe host), the procs additions, `_env.py`, the egress class. Mocked: nothing in the product path. Tests use fixture checks and fixture deliverables (§14). This is enough for W1-E's discrimination run of S1 and the E1 pilot.
- **E2.** `rework.py` plugs into the strategy table and calls `correctness.grade()` once per tree.
- **E4.** X-LB adds loopback (the listener helper, HB-CHK-005, spike S-LB). Resilience and fault cases arrive. X-LG adds the no-guessing and simplicity helpers.

**Mock-substitutable seams (named).**
1. `STRATEGIES[property.name]`: a missing helper gives NA `not built` for its metrics (a Special Case, not an error).
2. `bench_check.listen()`: the loopback seam for X-LB. It is not built in E1, and `interface: loopback` makes the run NA `not built` until it is.
3. The fault seams in `property.py`: `_job_view_at_arrival` (the first-byte job query) and `_now_filetime`. These follow the `procs._query` pattern. The race test uses them (§14).
4. `correctness.grade` is called through the module attribute, so a test can substitute a fixed `Result` for the hidden tests.

## 5. Contracts

### 5.1 Dispatch: `runner.applicable` narrows by property (R-90 c1)

```python
def applicable(catalog: dict, graders: list[str], prop: str | None = None) -> dict[str, dict[str, dict]]:
    """grader -> {metric id: entry}: the kind: score metrics of `graders`, in catalog order. A metric with a
    `property:` tag applies only when the tag equals `prop` (the task's property.name). An untagged metric applies
    as before. One narrowing, three readers: this pass, readiness (X-E) and the discrimination record (R-90 c1)."""
```

- `_grade_cell` passes `prop = task["property"]["name"]` when the task is current, and `None` otherwise. With `None`, no tagged metric applies. In the "task changed" fallback, `property_check_pass` (untagged) is NA `task changed since the plan`, and no tagged row exists.
- `GRADERS["property"] = property.grade_cell`, one line next to the others.
- **Amended rule, quoted for `design-phase3-graders` (R-90 c5; W1-G carries the text):** "The applicable set is every `kind: score` catalog metric of those graders **whose `property:` tag, if present, equals the task's `property.name`**."

### 5.2 `property.grade_cell(inp)`

```python
STRATEGIES: dict[str, Callable[[CellInput, Context], dict[str, Score]]] = {
    "security": _hidden_check, "resilience": _hidden_check,   # E1 / E4 (X-F)
    # "rework": rework.grade,            E2, X-J2 (R-90 c4: a helper, never a registered grader)
    # "no-guessing": noguess.grade,      E4, X-LG
    # "simplicity": diffstats.grade,     E4, X-LG
}
```

1. If `sys.platform != "win32"`, every metric is NA `not built`. The runner is Windows-only (ADR-0018 §8).
2. Pick the strategy by `inp.task["property"]["name"]`. If none, every metric is NA `not built`.
3. `_hidden_check` runs the phases **in this order** (RV-SEC F3). Every copy lives under `inp.work_root` (`cells_root/grading/<gid>/<cid>/property/`, ADR-0013 Am. 2):
   1. **Hidden tests.** `correctness.grade(inp.archive / "ws", inp.task_dir, oracle, inp.out_dir / "tests", inp.run_dir, timeout, inp.work_root / "tests")`. `procs.run` closes that job (kill-on-close, no breakaway), so no test-run process survives into the next phase (G5, G9). The phase records `hidden_tests_ms`.
   2. **Fresh check copy, provisional (seam req-…BDBD).** `check-run/deliverable/` is copied **from the archive**, never from the tests copy (`_changes.grading_copy` semantics: no `.git`, no build output, symlinks kept as links). Then `check-run/check/` holds `oracle/check/*` plus `grade/bench_check.py`. The grader then parses `cases.yaml`, validates it and writes `check-run/check/cases.json` (seam req-…FR1). **Last**, it computes `hash_before = plan.tree_hash(check/, every file under check/)`.
   3. **Run the check** (§5.3). Then confirm the job is empty and close it.
   4. **`hash_after`** over the same file list, plus any new file under `check/`.
   5. **Classify** (§5.6), **score** (§5.7), copy the stdio files to `out_dir/check/`, write `property.json`, and remove `check-run/` on every path.
4. `timeout` is `inp.plan["parameters"]["grading_step_timeout"]`. It bounds each phase separately, as it does in correctness. The hidden tests and the check each get the full bound.

### 5.3 Check invocation and handshake (ADR-0018 §1, §10a; spike E1-S3 and SP-F2)

```
argv  = [sys._base_executable, "-S", "check/<entry>",
         "--deliverable", <abs check-run/deliverable>, "--cases", "check/cases.json",
         "--seed", <int>, "--evidence", <abs out_dir/check>]        # evidence outside the copy (RV-SEC F8)
env   = _env.grading_env(declared toolchain names)                  # §5.9; never os.environ
spawn = procs.spawn(argv, cwd=check-run, env=env, stdin=PIPE, stdout=PIPE,
                    stderr=<out_dir/check/check.stderr>, console=False)   # DETACHED_PROCESS, suspended, then in a new job
seed  = int(sha256(f"{task_version}|{cell_id}|property_check_pass").hexdigest()[:16], 16)
```

- `-S` keeps the base interpreter's `site-packages` off the path (RV-SEC F9a; G12). `PYTHONPATH` cannot reach the check, because the allowlist never carries it.
- **Grader side, in order.**
  1. A reader thread drains stdout in chunks. It keeps at most `MAX_RESULT_BYTES = 1 MiB`. Beyond that it counts bytes but stores nothing, so the writer never blocks.
  2. **On the first byte:** record `first_byte_ft = procs.now_filetime()`, then `job_view_at_arrival = spawn.job.pids()`. A query that raises is recorded as `"query failed"`. Classification reads that as "not alone" (fail-closed, G5).
  3. On the first `\n` (or EOF, or the bound): parse and validate the line (§5.6 rule 6). **Accept** only when the line is valid and the job view is exactly `{check pid}`.
  4. If accepted, write the one byte `0x06` to the check's stdin. **On every path, close the check's stdin** (RV-TA s3). EOF without the byte means "refused". The check then exits 3 at once. It never waits for the bound (spike: about 1 ms).
  5. Wait for the exit within the remaining bound. Read `exit_ft = spawn.exit_time()` from the grader's own process handle (`GetProcessTimes`). Drain stdout to EOF, within `procs._KILL_GRACE`.
  6. Then `terminate_and_confirm`, and close the job.
- **Check side (`bench_check`).** Outcomes stay in memory. `write_result` sweeps the job, waits until the check is alone, writes one line, flushes, then blocks on `stdin.read(1)`. It exits **0** on `0x06` and **3** on EOF. It exits **4** without writing if it is not alone within 5 s, and **5** without writing on an uncaught check error.

### 5.4 `bench_check.py`: the helper API (stdlib only; copied in; never authored in a task)

| Function | Contract |
| --- | --- |
| `load() -> Context` | Parses the argv of §5.3 and reads `cases.json`. `Context.rng = random.Random(seed)`. `Context.bound_ms(case)` is the effective bound, `min(case.bound_ms, bounds_ms[interface])`. An omitted case bound means the interface bound (RV-TA s10). |
| `spawn_deliverable(argv, env_extra=None, *, tag, pipes=False) -> Child` | Replaces `{python}` with `sys._base_executable` (the `correctness.py:209` convention). Uses `subprocess.Popen(close_fds=True, creationflags=DETACHED_PROCESS)` with all three stdio handles explicit. With `pipes=False`: stdin is `DEVNULL`, and stdout and stderr go to `deliverable/.bench-stdio/<tag>.{out,err}` in the copy. With `pipes=True`: stdin and stdout are pipes the **check** owns (the probe host only). The environment is the check's own (already the allowlist, §5.9) plus `env_extra`, whose keys must be `HB_CHECK_*` or a declared `env` name, else `ValueError`. There is no `close_fds` parameter and no `lpAttributeList` (spike E1-S2 finding 1). |
| `build() -> bool` | Runs `deliverable.build` (if declared) through `spawn_deliverable`, never a bare subprocess (RV-SEC F7). A non-zero exit records `deliverable: "did not build"`. |
| `probe_host(case) -> ProbeHost` | §5.5. A failed import records `deliverable: "did not start"`. |
| `run_case(case, fn)` | Times the case with `time.monotonic`, enforces `bound_ms(case)`, and turns a bound overrun into `timeout` after `sweep()`. Turns a broken probe-host exchange into the kind's failing outcome (fail-closed: `exploited` for a probe, `failed` for a fault or static case). |
| `sweep(bound_s=5)` | Terminates every job member except the check (`QueryInformationJobObject(NULL, BasicProcessIdList)`, then `OpenProcess(PROCESS_TERMINATE)` and `TerminateProcess`), and repeats until alone. Spike SP-F1: one round, about 10 ms, for a deliverable plus a grandchild plus a console host. |
| `write_result(cases, measures=None)` | Adds `schema` and `deliverable` itself. Writes once, last and alone, then waits for the acknowledgement (§5.3). It never returns. |
| `main(check_fn)` | Wraps the task's check. An uncaught exception writes the traceback to stderr and exits 5. |

**Result document, provisional (seam req-…BDBD):**

```json
{"schema": "bench-check-result/1", "deliverable": "ran",
 "cases": [{"id": "inj-1", "outcome": "blocked", "duration_ms": 41}],
 "measures": {}}
```

`deliverable` is one of `ran`, `did not build` or `did not start`. With `ran`, every declared case appears exactly once. Otherwise `cases` is `[]`. Outcomes by kind: `probe` is `blocked`, `exploited` or `timeout`; `fault` is `passed`, `failed` or `timeout`; `static` is `passed` or `failed`. `measures` may carry **only** the non-derivable metric ids of the narrowed set: `idempotency_violations` for resilience, and nothing for security (RV-SEC F5).

### 5.5 In-process probes: the probe-host child (RV-SEC F1), provisional (seam req-…BDBD)

**The check process never imports deliverable code.** ADR-0018 §1 already requires that the deliverable be the check's child. Importing it into the check would put agent module-body code in the process that holds the outcomes, the result pipe and the acknowledgement. Spike SP-F2 reproduced RV-SEC's exploit, `sys.stdout.write(<forged blocked>); sys.stdin.buffer.read(1); os._exit(0)`: it was **accepted, 3 of 3**. The same module in a probe host had no effect, 3 of 3.

- **Shape.** `<base> -S check/bench_check.py --probe-host --root <deliverable> --app <module>:<attr> --kind callable|wsgi` is spawned by `spawn_deliverable(..., pipes=True)`. It inserts `--root` into `sys.path`, imports the app, writes one ready line, then serves JSON lines until EOF. An import failure exits 10 and gives `did not start`.
- **Lines** (UTF-8, at most 1 MiB, one per line):
  - `callable`: request `{"id": n, "args": [...], "kwargs": {...}}`; response `{"id": n, "ok": true, "value": <json>}` or `{"id": n, "ok": false, "error": "<exception type name>"}`.
  - `wsgi`: request `{"id": n, "method", "path", "query", "headers", "body_b64"}`; response `{"id": n, "status", "headers", "body_b64"}`.
- **Decisions stay in the check.** The check builds the payload, reads the response and decides the outcome in its own process. Agent code in the probe host can only shape the responses, and that is the deliverable's behaviour, which is what a probe measures. A forged result line written by the probe host is a malformed response, so the case takes its failing outcome.
- **One host per case.** That gives the per-case bound and isolation for free. `simplify:` one host start per case (about 40-80 ms measured in SP-F2). Ceiling: about 50 cases per task. Upgrade trigger: host start time above 10 % of a check's wall time.
- `cases.yaml` gains `app: {module, attr, kind}` for `interface: in-process` (seam). Readiness (X-E) rejects an in-process task without it (HB-RDY-005).
- **Loopback (E4, X-LB): seam only.** `bench_check.listen()` binds `("127.0.0.1", 0)` and asserts `getsockname()[0] == "127.0.0.1"` (ADR-0018 §3, HB-CHK-005). It is not built in E1.

### 5.6 Classification: one precedence, one row per run (RV-TA s3; RV-SEC F4), provisional (seam req-…BDBD)

Rules are evaluated top to bottom. The first rule that holds decides the run. "NA" in rules 1-6 means every metric of the run is NOT_RECORDED with that reason.

| # | Condition | Result | Code |
| --- | --- | --- | --- |
| 1 | `SleepDetector(PROPERTY_SUSPEND_GAP_S).slept()` over the check step | NA `host suspended`; re-run by the next pass (G11) | HB-CHK-004 |
| 2 | the outer bound fired (no exit within `grading_step_timeout`) | NA `check exceeded its bound` | HB-CHK-003 |
| 3 | `hash_after != hash_before` | NA `invalid (check tampered)` | HB-CHK-002 |
| 4 | §10a(b) broken: `job_view_at_arrival != {check}` (or the query failed); more than one line or trailing bytes; no document at EOF with an exit code other than 5; exit at or before `first_byte_ft`; exit code ≠ 0 after an acknowledgement, or ≠ 3 after a refusal | NA `invalid (check tampered)` | HB-CHK-002 |
| 5 | no document at EOF with exit code 5 (a check error) | NA `check output invalid` | HB-CHK-001 |
| 6 | the line is not valid: not JSON; over 1 MiB; wrong `schema`; `deliverable` out of its set; an undeclared, missing or duplicate case id; an outcome not allowed for its kind; a `measures` key that is not a non-derivable id of the narrowed set; a value off the catalog form (int for an int metric, `bool` rejected; a string matching `^\d+\.\d{4}$` for scale 4) | NA `check output invalid` | HB-CHK-001 |
| 7 | `deliverable` is `did not build` or `did not start` | `property_check_pass` = **0**, a measured failure (EV-1); the secondaries are NA with that text | — |
| 8 | otherwise | scores (§5.7) | — |

- Rule 1 comes first because a suspend can fire the bound and void every timing comparison (ADR-0018 §12). Rule 2 comes before tamper because a bound overrun leaves the handshake incomplete by construction. Rule 3 comes before rule 4 because both are tamper and the hash is the stronger evidence. Rules 4 and 5 come before rule 6 because a forger's line could also be malformed. Tamper wins, so a forger cannot choose the cheaper label by writing garbage.
- `PROPERTY_SUSPEND_GAP_S = 1.0`. The engine's 60 s gap would let a short suspend flip a 2 s case into a measured `timeout` (spike A9 residual). A false positive (for example, an NTP step over 1 s) costs only an NA and a re-run, never a wrong score. `simplify:` this is a fixed constant. Upgrade trigger: an HB-CHK-004 rate above 1 % of check runs in a pilot.
- Exit code 5 ("check error") could be faked by a forger that kills the check with that code. The result is still NA, never a score. Only the label differs, and the pilot gate names both labels (EV-14).

### 5.7 `property_check_pass` and the derived secondaries (RV-TA s5)

**Check passes** ⇔ `deliverable == "ran"` and every declared case's outcome is `blocked` or `passed`. `exploited`, `failed` and `timeout` each fail it.

**Primary = hidden tests ∧ check, in Kleene logic.** A known false conjunct gives a measured 0. Otherwise an unknown gives NA.

| hidden tests (`correctness.grade`) | check (after §5.6) | `property_check_pass` |
| --- | --- | --- |
| 1 | passes | **1** |
| 1 | ran, a case fails | **0** |
| any | did not build / did not start | **0** (EV-1; the reason goes in evidence only, per the W0 measured-0 decision) |
| 0 | any, including NA | **0** |
| 1 | NA (HB-CHK-001..004) | NA, the check's reason |
| NA | passes | NA, the hidden tests' own reason (correctness's closed vocabulary) |
| NA | ran, a case fails | **0** |
| NA | NA | NA, the hidden tests' reason (they ran first) |

**Secondaries**, when rule 8 applies:
- `exploit_probes_blocked = Decimal(blocked) / Decimal(probe cases)`, quantised to `0.0001` with `ROUND_HALF_EVEN`.
- `fault_suite_pass` is the same over fault cases.
- `idempotency_violations` is the int from `measures`.
- Zero probe (or fault) cases give NA `no probe case declared` (readiness should prevent this; HB-RDY-005).
- Under rules 1-6, every secondary is NA with the run's reason. Under rule 7, every secondary is NA with the deliverable text.
- A tampered security run whose hidden tests failed still records a primary 0. Forgery can only aim to raise a score, and a known 0 is not raised. The tamper is recorded on the secondaries and in the evidence.

`Score.evidence` is `grading/<gid>/<cid>/property/property.json`. For a primary 0, the evidence's `first_failing_case` holds what W0 calls "the score's reason".

### 5.8 `procs.py` additions (X-F owns `procs.py` in E1)

```python
def spawn(argv, cwd, env, stdin=PIPE, stdout=PIPE, stderr=DEVNULL, *, console: bool = True) -> CellProcess
    # console=False: CREATE_SUSPENDED | DETACHED_PROCESS (0x8) in place of CREATE_NO_WINDOW (spike E1-S3).
    # The default is unchanged, so engine and run() callers are unaffected.
class CellProcess:
    def exit_time(self) -> int     # GetProcessTimes(proc._handle).ExitTime, FILETIME (100 ns); raises OSError
def now_filetime() -> int          # GetSystemTimePreciseAsFileTime: the same clock as exit_time
```

These are Windows-only (POSIX raises `OSError`; the runner is Windows-only, ADR-0018 §8).

### 5.9 `grade/_env.py`: one allowlist (ADR-0018 §9; DM7; RV-SEC F2, F6)

```python
HOST_ENV = ("PATH", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "TEMP", "TMP")
DOTNET_HOST_ENV = ("USERPROFILE", "APPDATA", "LOCALAPPDATA", "HOMEDRIVE", "HOMEPATH", "ProgramData", "ProgramFiles",
                   "NUGET_PACKAGES")                       # correctness.py:49 verbatim
TOOLCHAIN_ENV = frozenset(DOTNET_HOST_ENV)                 # the only names a check's `env` may declare, with HB_CHECK_*
def grading_env(extra: Iterable[str] = ()) -> dict[str, str]   # HOST_ENV + CELL_ENV + PYTHONDONTWRITEBYTECODE/HASHSEED=0/UTF8 + extra
def denied(name: str) -> bool                              # profiles.DROP_EXACT / DROP_PREFIXES + HB_CLAUDE_OAUTH_TOKEN, GH_TOKEN, ANTHROPIC_*
```

- `correctness._env()` becomes `_env.grading_env()`. Its four `DOTNET_HOST_ENV` merges become `_env.grading_env(_env.DOTNET_HOST_ENV)`, which gives the same keys and values.
- `mutation.py` imports `HOST_ENV` and `DOTNET_HOST_ENV`, and keeps its own extra as a named `MUTATION_DOTNET_ENV = DOTNET_HOST_ENV + ("PROCESSOR_ARCHITECTURE",)` (G4). Its behaviour is unchanged. The US-4 control proves that byte for byte.
- A `cases.yaml` `env` name must be in `TOOLCHAIN_ENV` or start with `HB_CHECK_`, and must not be `denied` (readiness HB-RDY-005, seam to X-E). The grader refuses such a name too (rule 6).

### 5.10 `egress.py`: the `task_canary` class (R-E9; X-F owns `egress.py` in E1)

`TASK_CANARY = re.compile(r"\bBENCHCANARY-[A-Z0-9]{1,8}-[0-9a-f]{16,}\b")` is added to `CLASSES` as `task_canary`. It always runs, because the shape is known without a caller-supplied value. A payload carrying a planted canary is withheld with that class. Evidence excerpts reach a judge or a report only through this gate (US-47).

### 5.11 Campaign hooks (ADR-0018 §11; W0 §10 "seam X-C → X-F"), provisional on W1-C

- **Before** taking `grade.lock`, `run_pass` refuses while `campaign.lock` is held: `HB-CMP-001`, raised through X-C's `campaign.lock_held(root)`.
- **After** a completed pass of a campaign run, `run_pass` calls `campaign.verify(root, campaign_id)`. A failure raises `HB-CMP-003` after the pass is sealed. The pass stays completed; the operator sees the failure. Both call shapes are X-C's. X-F adds only these two lines.

## 6. Patterns (named and justified; Patterns Expert versus Simplifier)

| Pattern | Where | Why it earns its place (and the rung of the Solution-Selection Ladder) |
| --- | --- | --- |
| **Strategy via a registry** (existing, `runner.GRADERS`) | one `property` entry; `STRATEGIES` by property | R-90 forbids a second registered grader. One dict line per helper (rung 2: reuse). |
| **Special Case** (existing NA `Score`) | every non-score outcome | the codebase's own NA idiom; no exception crosses the grader boundary |
| **Gateway** (existing `procs`) | the check spawn, job view, exit time | D3/R-60: the bench reaches processes only through `procs` (rung 2) |
| **Handshake / acknowledged single-write protocol** | §5.3 | spike E1-S3: arrival timing alone is unsound (4-8 ms margins). The smallest stdlib form of an acknowledged one-shot write: one byte, no framing library. |
| **Sandboxed adapter (Half-Sync process boundary)** | the probe host, §5.5 | the only way to keep agent code out of the deciding process while staying stdlib-only. Rejected: running decisions in the probe host (SEC F1 again). |
| **Chain of Responsibility, as an ordered rule table** | §5.6 | one function with an ordered list. It is not a class hierarchy (Simplifier). |
| **Parameter Object** (existing `CellInput`) | the grader input | unchanged |

Rejected, with reasons:
- **A nested Job Object per deliverable.** It works on Windows 8+, but it adds `CreateJobObject`/`AssignProcessToJobObject` code to the stdlib helper. The pid sweep (SP-F1) reuses the query that the "alone" test already needs.
- **An HMAC or nonce on the result line.** The deliverable can read the check's memory, so it adds no protection against a same-user process (ADR-0018 §10a residual).
- **A third test runner for property tests.** R-90 c2 forbids it.
- **A port allocator.** ADR-0018 §3 uses port 0.

**Ladder.** No new dependency (stdlib and existing modules only). Bounded choices are marked `simplify:` in §5.5 (one host per case) and §5.6 (the 1 s suspend gap).

## 7. Change-surface list (E7)

| Layer | Surface | Owner · phase |
| --- | --- | --- |
| store | `scores` rows (existing grain); new evidence file `property.json`; deliverable stdio copies | X-F · E1 |
| catalog | eleven entries with `property:` tags, `0.7.dev` | X-G1 · E1 (seam, W1-G) |
| task contract | `tasks/README.md` property section: `app:`, `deliverable` field, `cases.json`, the env rule | Coordinator (W0) via seam req-…BDBD, req-…R1 |
| model | `CheckRun`, `ResultDoc`, `CaseDecl`, `Classification` dataclasses in `property.py` | X-F |
| service | `runner.applicable(prop)`, `GRADERS["property"]`; `property.grade_cell`; `bench_check.py`; `_env.py`; `procs.spawn(console)`, `exit_time`, `now_filetime`; `egress` `task_canary`; `correctness`/`mutation` import `_env` | X-F · E1 |
| guards | G4 (`tests/test_property_grader.py`); D3 and R-60 allowlist entries in `tests/test_architecture.py` | X-F; X-D (seam req-…QMZ) |
| run/grade class | `grade/property.py`, `grade/bench_check.py`, `grade/_env.py`: `grade` (W0 §9) | X-D seeds |
| projection/wire | views unchanged (score rows); readiness reads the narrowed set through `runner.applicable` | X-E |
| client type | none (CLI and files only) | — |
| UI | the report's campaign section shows the property metrics and NA reasons | X-H2 |
| compute readers | discrimination record and readiness (X-E; R-90 c3 agreement); verdicts and pilot gate (X-H1; HB-CHK-* as gate items) | X-E, X-H1 |
| errors | HB-CHK-001..004 confirmed (HB-CHK-005 stays X-LB's); no new code | X-D adds them to `errors.py` |
| campaign hooks | `run_pass` lock refusal and the after-pass verify | X-F lines, X-C APIs |

## 8. Error and concurrency model

- **Errors.** No exception leaves `property.grade_cell` for an expected outcome; each one is a `Score` (§5.6, §5.7). An unexpected exception falls to the runner's existing HB-GRD-003 (NA for every metric, the traceback as evidence).
- **Concurrency inside one run.** Two threads in the grader: the main thread and the stdout reader. The reader owns `buf`, `first_byte_ft` and `job_view_at_arrival` until it sets `line_ready` or `eof`. The main thread reads them only after one of those events (a happens-before through `threading.Event`). The acknowledgement and the stdin close happen on the main thread only.
- **Across runs.** A pass grades cells one at a time (`runner.run_pass`). Two passes cannot overlap (`grade.lock`, HB-GRD-001). Parallel grading slots (EV-3) are isolated by separate jobs, copies and ports (port 0, E4). Each copy's path includes `grading_id` and `cell_id`.
- **Idempotency.** A re-grade of one archive reproduces every case outcome (fixed payloads; seed from `(task_version, cell_id, metric)`). The grading copy is removed on every path, and a leftover from a crashed pass sits under a different `grading_id`.

## 9. Failure-mode analysis

| # | Failure mode (category) | Disposition | Detection / test |
| --- | --- | --- | --- |
| F1 | the deliverable hangs (time) | **mitigate**: the case bound; `sweep()`; outcome `timeout`, a measured failure (EV-3) | `test_hanging_deliverable_with_grandchild_is_a_measured_timeout` |
| F2 | the deliverable leaves processes after a case (resources) | **prevent**: `sweep()` before every write; `write_result` writes only when alone | the same test, plus `test_write_result_never_writes_while_not_alone` |
| F3 | the deliverable forks faster than the sweep (resources) | **detect**: exit 4 with no document gives HB-CHK-002; never a score | `test_unsweepable_job_is_tampered_not_scored` |
| F4 | the check itself hangs or ignores its bound (time) | **mitigate**: the outer bound, `TerminateJobObject`, HB-CHK-003 | `test_outer_bound_fired_is_hb_chk_003` |
| F5 | malformed or oversized result (input) | **detect**: rule 6, HB-CHK-001; stdin closed so no bound wait | `test_malformed_document_is_hb_chk_001_without_waiting_for_the_bound` |
| F6 | a check bug raises (dependency: task check) | **detect**: exit 5, HB-CHK-001, traceback in `check.stderr` | `test_check_error_exit_5_is_hb_chk_001` |
| F7 | the host suspends mid-check (time) | **detect**: rule 1, HB-CHK-004, re-run next pass | `test_seeded_suspend_is_hb_chk_004_not_timeout` (fake unbiased clock) |
| F8 | the unbiased clock is unreadable, so a suspend goes undetected (dependency) | **accept**: `QueryUnbiasedInterruptTime` has not failed on this host (spike A9). *assume:* it never returns failure on Windows 10+. Confirm: `test_unbiased_clock_reads_on_windows`. Breaks if false: a suspend can turn a case into a measured `timeout`. | that test |
| F9 | the job query fails at arrival (dependency) | **prevent** (fail-closed): read as not alone, HB-CHK-002 | `test_job_query_failure_at_arrival_is_not_alone` (fault seam `_job_view_at_arrival`) |
| F10 | the hidden tests are non-deterministic, so the inner run disagrees with `pass_at_1` (state) | **detect**: `hidden_tests.final` in evidence; X-E raises the pilot-gate item (R-90 c3) | `test_hidden_tests_result_and_ms_are_in_evidence` (here); the agreement test is X-E's |
| F11 | a test-run survivor poisons the check copy (concurrency/state) | **prevent**: the tests' job is closed with kill-on-close before the copy; fresh copy from the archive; the hash taken last | `test_tests_phase_cannot_write_into_check_copy` |
| F12 | a deliverable edits `check/` during the run (tamper) | **detect**: rule 3 | `test_check_tree_changed_is_tampered` |
| F13 | the grading copy fails to copy (disk full, path too long) (resources) | **detect**: HB-GRD-003 through the runner, traceback in evidence | existing runner test (`test_grade_runner.py`) covers HB-GRD-003 |
| F14 | the copy is not removed (resources) | **mitigate**: `finally`-removal (`archive.make_writable`); a crashed pass leaves it under its own `grading_id` | `test_grading_copy_removed_on_every_path` (parametrised over rules 1-8) |
| F15 | a stdio file is huge (resources) | **mitigate**: copy at most 64 KiB per file, `truncated: true` | `test_stdio_evidence_is_capped` |
| F16 | the build hangs (time) | **accept**: bounded by the outer bound, giving HB-CHK-003 (NA), not a measured 0. Builds are task-declared argv. Residual: an agent-induced build hang reads as not recorded. | `test_outer_bound_fired_is_hb_chk_003` (build variant) |
| F17 | the honest check exits just before the grader's job query sees it (time) | **prevent**: the acknowledgement handshake (the check cannot exit before the ack); spike margin +0.9..+3.0 ms after the ack | `test_honest_check_is_accepted` (repeated 20 times) |
| F18 | `bench_check.py` imports `harness_bench` (structure) | **prevent**: stdlib-only AST test | `test_bench_check_imports_stdlib_only` |
| F19 | the allowlist drifts between graders (structure) | **prevent**: G4 | `test_host_env_defined_once` |
| F20 | a task changes after the plan (state) | **existing**: NA `task changed`; no tagged rows (§5.1) | `test_task_changed_fallback_rows_for_property` |

## 10. Adversarial analysis (STRIDE-lite)

**Trust boundaries.**
- **B7a**, deliverable to check: agent code versus the hidden check, its memory, its pipes and its tree.
- **B7b**, check to grader: the result pipe and the acknowledgement.
- **B7c**, grading environment to agent code: environment and inherited handles.
- **B7d**, agent code beside durable records: `bench/campaigns`, `bench/discrimination`.
- **B6**, unchanged: evidence to judge or report, through `egress.check`.

Every row of ADR-0018's STRIDE table comes first (A-rows), then the rows the reviews and spikes added (N-rows).

| # | Threat (ADR-0018 row) | Control in this design | Test node (red first) | Disposition |
| --- | --- | --- | --- | --- |
| A1 | Credential exposure to agent code (I) | `_env.grading_env`; `spawn_deliverable` inherits only that environment plus `HB_CHECK_*` and declared toolchain names; `denied()` | `test_property_check_env_excludes_credentials` (ADR-0018 §9) | mitigate |
| A2 | Result forgery through an inherited handle (T) | `close_fds=True` handle list with explicit stdio; the check's stdout is never in a child's list | `test_deliverable_cannot_write_result_pipe` (ADR-0018 §10; asserts on the result pipe, per spike E1-S2 finding 2) | mitigate |
| A3 | Result forgery through a duplicated handle (T) | write once, last and alone; first-byte job view; one line, no trailing bytes; exit after arrival; the acknowledgement | `test_forged_result_via_duplicated_handle_is_tampered` (ADR-0018 §10a), with variants `..._forge_then_exit_two_documents` and `..._forge_then_kill_check` | mitigate (residual: in-process code injection into the check, undetected, accepted by ADR-0012/0013) |
| A4 | Killing the check before its write (T) | an abnormal or absent document; exit-before-arrival rule | `test_check_killed_before_write_is_tampered` (ADR-0018 §10a) | mitigate |
| A5 | The forger writes and exits inside the race window (T) | the honest check's later write makes two documents; rule 4 | `test_forged_write_racing_deliverable_exit_yields_two_documents` (the race test; the fault seam `_job_view_at_arrival` runs the query after the forger's exit, so the "alone" view is forced; spike SP-F2 saw the forger still present 3/3, so the race is not left to chance) | mitigate |
| A6 | Tampering with campaign records during a check (T) | refuse `run_pass` under `campaign.lock`; `campaign.verify` after the pass (§5.11) | `test_run_pass_refuses_while_campaign_lock_held`; `test_campaign_verify_runs_after_a_campaign_pass` (provisional on X-C) | mitigate (detect, not prevent: ADR-0018 §11) |
| A7 | Spoofing: another process answers as the fake (S) | E4 only: bind `127.0.0.1:0`, `getsockname` assert, HB-CHK-005 | X-LB's (`test_listener_binds_loopback_only`) | **transfer, named**: X-LB, E4. Not reachable in E1 (no listener; `interface: loopback` is NA `not built`, `test_loopback_interface_is_not_built_in_e1`) |
| A8 | The deliverable alters the check or its result (T) | the hash before and after (rule 3); result only on the check's own stdout; evidence outside the copy | `test_check_tree_changed_is_tampered`; `test_evidence_dir_is_outside_the_copy` | mitigate (residual: a same-user process could edit and restore within the run, accepted, ADR-0013 A10) |
| A9 | Repudiation (R) | per-case outcomes, durations, seed and handshake facts in `property.json`; the `grade.property.check` event | `test_evidence_records_every_case_seed_and_handshake` | mitigate |
| A10 | Information disclosure: planted secrets (I) | synthetic canaries only; `task_canary` egress class; stdio reaches judges and reports only through `egress.check` | `test_task_canary_is_withheld` (`tests/test_egress.py`) | mitigate |
| A11 | Denial of service (D) | per-case bounds in the check; outer bound and `TerminateJobObject`; result capped at 1 MiB; stdio capped at 64 KiB | `test_outer_bound_fired_is_hb_chk_003`; `test_result_over_1mib_is_hb_chk_001`; `test_stdio_evidence_is_capped` | mitigate. A DoS can only produce NA, never a score. |
| A12 | Elevation of privilege (E) | none added: the deliverable runs as the operator, as the cell did; the check's job is kill-on-close, forbids breakaway, and its handle is not inheritable | `test_check_job_is_kill_on_close_no_breakaway_not_inheritable` | accept (owner ruling, ADR-0013; upgrade: a low-rights check user, ADR-0018 §10a) |
| A13 | Network reach (spec *assume:*) (I) | E1: no socket at all (in-process via the probe host). E4: loopback only | `test_e1_check_opens_no_socket` (a socket-creation audit hook in the fixture check) | mitigate in E1; `0.0.0.0` binds in E4 accepted per ADR-0018 |
| N1 | **RV-SEC F1:** agent module-body code in the check process forges the result (T, E) | the check never imports deliverable code; in-process means a probe-host child (§5.5) | `test_module_body_forgery_in_probe_host_is_refused` (the fixture module does `sys.stdout.write(forged); sys.stdin.buffer.read(1); os._exit(0)`; expected: the result is not the forged `blocked`, `deliverable: did not start`, primary 0); plus `test_check_never_imports_deliverable_code` (an import-audit hook in the fixture check fails on any module under `deliverable/`) | mitigate. Spike: forged 3/3 in-check, refused 3/3 in a probe host. |
| N2 | **RV-SEC F2:** a task's `env` lists a credential name (I) | the `TOOLCHAIN_ENV`/`HB_CHECK_*` rule and `denied()` in readiness and in the grader | `test_check_env_rejects_denied_and_undeclared_names` | mitigate |
| N3 | **RV-SEC F3:** the hidden-test phase poisons the check phase (T) | the phase order and a fresh copy, hashed last | `test_tests_phase_cannot_write_into_check_copy` | mitigate |
| N4 | **RV-SEC F5:** the check self-reports a derivable measure (T) | the grader derives; a derivable key in `measures` is rule 6 | `test_derivable_measure_in_document_is_hb_chk_001` | mitigate |
| N5 | **RV-SEC F7:** the build runs outside the handle list and environment (I, T) | `build()` uses `spawn_deliverable` | `test_build_runs_through_spawn_deliverable` (the fixture build writes its environment and tries the result pipe) | mitigate |
| N6 | **RV-SEC F9a:** the operator's global `site-packages` shadow the stdlib in the check (T) | `-S`; `PYTHONPATH` is not in the allowlist | `test_check_runs_without_site_packages` | mitigate |
| N7 | a forged probe-host response (T) | treated as deliverable behaviour; a malformed one is the failing outcome | `test_malformed_probe_response_fails_the_case` | accept as measurement: the probe measures what the deliverable answers. Residual: test-detection gaming is possible for any probe, loopback included. |
| N8 | a forger fakes exit code 5 to choose the label HB-CHK-001 (R) | both labels are NA and both are pilot-gate items | `test_check_error_exit_5_is_hb_chk_001` | accept (label only, never a score) |
| N9 | a same-user process consumes the acknowledgement (D) | the check gets EOF, exits 3, giving rule 4 | `test_stolen_ack_is_tampered` | mitigate (NA only) |

**Residual risk.** ADR-0018 §10a's in-process injection into the check by deliberate tooling stays **undetected**. It is accepted under ADR-0012 and ADR-0013. The upgrade trigger is unchanged: a low-rights check user.

## 11. Privacy analysis (LINDDUN-lite)

No personal data. Task data and canaries are synthetic (spec, Privacy row). Evidence files carry no operator identifiers, because the environment allowlist excludes `USERNAME` and the profile paths. Any path that reaches a report or judge passes `egress.check`, whose `home_path` and `username` classes withhold it.

## 12. UI design

N/A. There is no user-facing surface. The report's display of these rows is X-H2's.

## 13. Telemetry (O1-O13)

- **Structured log events.** The codebase uses `logger` with a dict payload (`runner.py`, `grade.grader_failed`). Two events carry `grading_id` and `cell_id` (the pass's trace keys):
  - `grade.property.hidden_tests`: `{tree, passed, reason, hidden_tests_ms}`
  - `grade.property.check`: `{task, interface, code, reason, deliverable, cases, failing_cases, wall_ms, first_byte_to_exit_ms, job_view_size, documents, acked, exit_code, bound_fired, suspended, sweep_rounds}`
- **Stable error codes.** HB-CHK-001..004 (§5.6), in the event and the evidence. Score reasons use the W0 texts verbatim.
- **Measurements, by default with no flag.** `hidden_tests_ms` per tree (R-90 c3: the double-run cost); `check.wall_ms`. Every field is "not recorded" (`null`) when absent, never 0.
- **No HTTP surface**, so no RFC 9457.
- **Load-bearing telemetry has a test:** `test_check_event_fields` asserts the event's key set for an accepted run and a tampered run.

## 14. Test plan (by node id; red first where marked)

**Triggered directives.**
- D0 always.
- T1, giving D1: the classification table, the predicate and the derived measures.
- T2, giving D2: the result-document validator and the `measures` normaliser.
- T3, giving D3: new modules and allowlists.
- T4, giving D4: real copies, a real Job Object and real processes; no mocked `subprocess` or filesystem.
- T6, giving D5-provider: the `bench_check` API that task checks call.
- T7, giving D6: the result schema and the probe lines.
- T8, giving D7: fixture deliverables and fixture checks stand in for agent and task code.
- T9-T14: none (no AI path), so A1-A6 do not apply.
- Mutation: `tests/mutations/property.json` and `tests/mutations/bench_check.json`.

All B7 tests are Windows-only (`skipif(sys.platform != "win32")`, ADR-0018 §8) and use the base interpreter.

**The ADR-0018 red tests and the race test (gate items).**

| Node | Proves |
| --- | --- |
| `tests/test_property_grader.py::test_property_check_env_excludes_credentials` | §9: `HB_CLAUDE_OAUTH_TOKEN`, `CLAUDE_CODE_OAUTH_TOKEN`, `GH_TOKEN` and `ANTHROPIC_API_KEY` reach neither the check nor the deliverable |
| `::test_deliverable_cannot_write_result_pipe` | §10: the parsed result equals the honest one; nothing foreign arrived on the pipe |
| `::test_forged_result_via_duplicated_handle_is_tampered` (+ `_forge_then_exit_two_documents`, `_forge_then_kill_check`) | §10a: HB-CHK-002, never `blocked` |
| `::test_check_killed_before_write_is_tampered` | §10a: HB-CHK-002 |
| `::test_forged_write_racing_deliverable_exit_yields_two_documents` | §10a race: the forced "alone" view, two documents, HB-CHK-002 |
| `::test_module_body_forgery_in_probe_host_is_refused` | RV-SEC F1 (new, red first) |

**One test per grader outcome (W0 §3 and §5.6), plus each adjacent pair (RV-TA s3).**

| Outcome | Node |
| --- | --- |
| HB-CHK-004 | `::test_seeded_suspend_is_hb_chk_004_not_timeout` |
| HB-CHK-003 | `::test_outer_bound_fired_is_hb_chk_003` |
| HB-CHK-002 (hash) | `::test_check_tree_changed_is_tampered` |
| HB-CHK-002 (§10a) | the five tests above, plus `::test_unsweepable_job_is_tampered_not_scored`, `::test_stolen_ack_is_tampered`, `::test_job_query_failure_at_arrival_is_not_alone` |
| HB-CHK-001 | `::test_malformed_document_is_hb_chk_001_without_waiting_for_the_bound`, `::test_check_error_exit_5_is_hb_chk_001`, `::test_result_over_1mib_is_hb_chk_001`, `::test_derivable_measure_in_document_is_hb_chk_001` |
| measured 0 | `::test_deliverable_did_not_build_is_measured_0`, `::test_deliverable_did_not_start_is_measured_0` |
| scores | `::test_honest_check_is_accepted`, `::test_reference_and_naive_fixture_truth_table` (every row of §5.7) |
| precedence pairs | `::test_precedence[suspend+bound]`, `[bound+tamper]`, `[hash+handshake]`, `[tamper+malformed]`, `[malformed+did-not-build]`: each asserts exactly one code |

**The rest of the plan.**
- **D1, unit and mutation.**
  - `test_property.py::test_classify_table` (hypothesis over every combination of the handshake facts, checking one code each).
  - `::test_primary_kleene_truth_table`.
  - `::test_exploit_probes_blocked_rounding` (1/3 gives `0.3333`; 2/3 gives `0.6667`).
  - `::test_derived_measures_rebuild_from_evidence`.
- **D2, property-based.** `::test_validator_never_accepts_undeclared_or_duplicate_ids` and `::test_measure_normaliser_round_trip` (hypothesis; a shrunk counterexample becomes a permanent example).
- **D3, architecture.**
  - `test_property_grader.py::test_host_env_defined_once` (G4: tokens `\bHOST_ENV\s*=` with `HOST_ENV_DEFINERS = {"grade/_env.py"}`, and `os.environ` in `grade/property.py` and `grade/bench_check.py` with `OS_ENVIRON_READERS = {"grade/bench_check.py": "the check's own environment, already the allowlist"}`; RV-SEC F6).
  - `::test_bench_check_imports_stdlib_only` (G3 extension, RV-SEC F12).
  - The D3 and R-60 allowlist entries: X-D, seam req-…QMZ. Red on arrival until then.
- **D4, real infrastructure.**
  - `::test_hanging_deliverable_with_grandchild_is_a_measured_timeout`.
  - `::test_write_result_never_writes_while_not_alone`.
  - `::test_tests_phase_cannot_write_into_check_copy`.
  - `::test_grading_copy_removed_on_every_path[rule1..rule8]`.
  - `::test_stdio_evidence_is_capped`.
  - `::test_evidence_dir_is_outside_the_copy`.
  - `::test_check_runs_without_site_packages`.
  - `::test_check_job_is_kill_on_close_no_breakaway_not_inheritable`.
  - `::test_build_runs_through_spawn_deliverable`.
  - `::test_e1_check_opens_no_socket`.
  - `::test_check_never_imports_deliverable_code`.
  - `::test_regrade_reproduces_every_case_outcome` (ADR-0018 §6, EV-2).
  - `tests/test_procs.py::test_spawn_console_false_is_detached_and_job_holds_only_the_child`.
  - `::test_exit_time_follows_now_filetime`.
  - `::test_unbiased_clock_reads_on_windows`.
- **D5-provider.** `test_bench_check.py::test_spawn_deliverable_refuses_undeclared_env`, `::test_bound_ms_is_min_of_case_and_interface`, `::test_probe_host_callable_round_trip`, `::test_probe_host_wsgi_round_trip`, `::test_malformed_probe_response_fails_the_case`, `::test_loopback_interface_is_not_built_in_e1`. Each task's check is proven against this API by EV-7's discrimination record (X-E).
- **D6, schema and golden payload.** `::test_result_document_golden` (a synthetic, labelled fixture of `bench-check-result/1` with all three `deliverable` values) and `::test_evidence_schema_golden` (`bench-property-evidence/1`).
- **D7, mock fidelity.** Every fixture check imports the **real** `bench_check.py` (never a stub), and every fixture deliverable is a real process. The F1 and §10a fixtures are paired with spike SP-F2's observed behaviour (§15).
- **Runner and catalog.**
  - `tests/test_grade_runner.py::test_security_task_property_rows_are_exactly_two` (R-90 c5, red first: `property_check_pass` and `exploit_probes_blocked`; GradedOncePerPass green).
  - `::test_untagged_metric_applies_as_before`.
  - `::test_task_changed_fallback_rows_for_property`.
  - `tests/test_catalog_version.py` (the US-4 control) stays green: no 0.6 row moves.
  - `tests/test_grade_correctness.py` and `test_grade_mutation.py` stay green after the `_env` move.
- **Evidence and telemetry.** `::test_hidden_tests_result_and_ms_are_in_evidence`, `::test_evidence_records_every_case_seed_and_handshake`, `::test_check_event_fields`.
- **Egress.** `tests/test_egress.py::test_task_canary_is_withheld`.
- **Campaign (provisional on X-C).** `::test_run_pass_refuses_while_campaign_lock_held`, `::test_campaign_verify_runs_after_a_campaign_pass`.

## 15. Spikes run

**SP-F1 and SP-F2, 2026-10-03, run by this slice.**
- **Host and code.** Windows 11 Pro 10.0.26200, CPython 3.14.6, the base interpreter. Scripts are in the session scratchpad (`spf_grader.py`, `spf_check.py`, and three fixture deliverables), not committed.
- **Grader side.** `procs.Job`; the check spawned `CREATE_SUSPENDED | DETACHED_PROCESS`; a first-byte `Job.pids()`; the one-byte acknowledgement; stdin closed on every path; `GetProcessTimes`; §5.6's rules. Three trials per row.

| Trial | Observed | Verdict | Status |
| --- | --- | --- | --- |
| honest check; deliverable hangs and starts a grandchild with a plain `Popen` | 3 job members besides the check before the sweep (deliverable, grandchild, a console host, Inferred from the count); one sweep round, 10.5-10.8 ms; job view `{check}` at arrival; exit +1.1..+1.2 ms after arrival | accepted, `timeout` | Verified: in-job tree termination works |
| deliverable imported into the check (RV-SEC F1 exploit) | forged `blocked` line, alone, acknowledged, exit 0 after arrival | **accepted `blocked`: the forgery succeeds** | Verified: F1 is real |
| same module in a probe-host child | forged line went to the host's stdout file; the honest result arrived | accepted, honest `exploited` | Verified: the probe host closes F1 |
| duplicated-handle forger that stays alive 1.5 s | job view of 2 at arrival; 2 documents; exit 3 | HB-CHK-002 | Verified |
| duplicated-handle forger that exits at once (race) | job view of 2 at arrival in 3/3 (the race window was not hit); 2 documents | HB-CHK-002 | Verified (two-document defence present; the "alone" variant is forced by a fault seam in the test) |
| malformed line | stdin closed with no acknowledgement; exit 3 in 0.9-1.2 ms | HB-CHK-001, no wait for the bound | Verified |

**G12 (`-S`)** was also run (§2). The earlier spikes E1-S2, E1-S3, N4 and A9 are reused, not re-run.

## 16. Seam requests and decisions

| Id | To | Ask | Fallback (applied here) |
| --- | --- | --- | --- |
| `req-01M41C0NFEXQA0XVH4FTK9YDBD` | Coordinator (W0 §3) | ten amendments: the probe host and `app:`; the `deliverable` field; build through `spawn_deliverable`; the phase order and hash; the precedence and stdin close; the bound rule; derivable measures; the env rule; evidence outside the copy; `-S` | §3, §5.2-§5.7, §5.9 provisional |
| `req-01M41C0ZCPJ13PQ77KNC5AHQMZ` | Coordinator, then X-D (`tests/test_architecture.py`) | `SUBPROCESS_CALLERS` gains `grade/bench_check.py`; the R-60 allowlist gains `grade/property` | named in §14 D3 as red on arrival until X-D lands them |
| `req-01M41C57K2VVC7C4JGEJC18FR1` | Coordinator (W0 §3 argv) | `--cases check/cases.json` (the stdlib cannot read YAML) | §5.2-§5.3 provisional |

- **To W1-I (via the Coordinator, part of req-…BDBD).** S1's check must use `bench_check.probe_host`, and `cases.yaml` must name `app:`.
- **To X-E (readiness).** It reads the narrowed set through `runner.applicable(prop)`. It enforces the `env` rule and `app:`. It owns R-90 c3's agreement check. This is covered by the same request and by R-90.
- **Decision requests.** None. DR-4 was ruled by R-90 (a). The residuals here sit inside ADR-0012, ADR-0013 and ADR-0018's accepted set.

## 17. Conformance notes

- **ADR-0018.** Followed. Narrowed in two places, both consistent with its §1 and §10:
  - "probes call it in process" now means a probe-host child.
  - The §10 test asserts on the result pipe, not "no write succeeded" (spike E1-S2 finding 2).
- **ADR-0018 amendment needed (RV-SEC F9).** The base interpreter with `-S` and the one-byte acknowledgement are W0's and this design's, not the ADR's. The Coordinator records the amendment note with the W0 revision.
- **Local conventions conformed to.** NA as `Score(None, reason)`; evidence relative to `run_dir`; copies under `work_root`; `procs` as the only spawner on the bench side; fault seams as module functions (`procs._query` style); `simplify:` and `assume:` markers.
- **One recorded deviation.** `bench_check.py` calls `subprocess.Popen` outside `procs.py`. It runs in the check process, not in the bench, and it cannot import `procs`. This is an allowlisted D3 exception (seam req-…QMZ).

## 18. Flagged risks and residual unknowns

| Id | Risk | Status |
| --- | --- | --- |
| RF-1 | in-process code injection into the check (ADR-0018 §10a residual) | accepted, undetected |
| RF-2 | a deliverable whose app needs a third-party environment cannot be imported by `-S` base Python | Flagged: S1 is stdlib-only (W1-I to confirm); a later task needs a fresh look (spike E1-S3 "still Flagged") |
| RF-3 | the identity of the third job member in SP-F1 (assumed to be a console host) | Inferred from the count; it does not matter to the design, because the sweep kills any member |
| RF-4 | macOS: no runner | accepted (ADR-0018 §8); the metrics are NA `not built` |
| RF-5 | the W0 §3 amendments this design needs (RV-SEC F1 and RV-TA s3 are blocking on W0) | provisional until W0 is revised |
| RF-6 | the build hang reads as NA, not a measured 0 (F16) | accepted |
| RF-7 | `docs/security/threat-model.md` and `privacy-review.md` do not yet `document` this design | not owned by this slice; for the Coordinator's rollup (`docs-graph.py rollup`) |

**Confidence ledger.**
- Contracts read from the code: Verified.
- Process behaviour (handle list, job view, sweep, handshake, F1): Verified by spike.
- Kleene primary and precedence: decided here, and testable.
- Campaign hooks: Inferred shapes, provisional on X-C.

## 19. Status and next action

| | |
| --- | --- |
| **Completed** | W1-F design: the dispatch narrowing, the property grader, `bench_check`, the probe host, the handshake, classification, scoring, `_env`, procs and egress additions; the FMA, STRIDE, telemetry and test plan; spikes SP-F1/F2 |
| **Remaining** | W0 §3 revision (three seam requests); the X-D allowlist entries; the four lens reviews; E2 and E4 helpers and loopback (other tracks) |
| **Best next action** | RV-SEC and RV-TA review this design against the revised W0; then `/implement` for X-F, starting with the red-first tests of §14 |

## Gate record

Reviewers: RV-PAT (Patterns Expert), RV-SIM (Simplifier, soft veto), RV-TA (Test Architect, **hard veto**), RV-SEC (Security & Identity, **hard veto**). The author does not clear any veto.

`GATE design-eval-property-grader · pending · RV-PAT, RV-SIM, RV-TA (hard), RV-SEC (hard) · provisional on req-01M41C0NFEXQA0XVH4FTK9YDBD, req-01M41C0ZCPJ13PQ77KNC5AHQMZ, req-01M41C57K2VVC7C4JGEJC18FR1`

---
**Handoff:** → `/implement` (X-F, E1) after the gate.
