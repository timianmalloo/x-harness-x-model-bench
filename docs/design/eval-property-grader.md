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
  - { to: review-eval-ta-w1f, rel: relates-to }
  - { to: review-eval-sec-w1f, rel: relates-to }
  - { to: review-eval-pat-w1f, rel: relates-to }
  - { to: review-eval-sim-w1f, rel: relates-to }
review-by: "2026-10-17"
summary: >-
  Revision 2, conformed to W0 rev 2. One registered `property` grader (R-90): runner.applicable narrows it to the
  task's property; it runs the hidden tests through correctness.grade() and then the task's hidden check in a fresh,
  reparse-safe copy, in a new Job Object, started DETACHED with the base interpreter under -S and the grading
  environment allowlist. The check never imports agent code: probes go through a probe-host child whose pipes the check
  owns (the module-body forgery is committed as a fixture with its positive control). The grader accepts one line from a
  live, lone check, acknowledges it with one byte, and classifies by W0's seven ordered rows, with the suspend rule on
  each phase's span. E1 builds the security strategy, probe cases and `callable` apps only. Gate: rev 2 pending.
---

# Design W1-F: the hidden-check runner and the property grader

**Status:** proposed, **revision 2**, gate pending (see [Gate record](#gate-record)). **Authors:** revision 1 `w1f-property-e1e4`; revision 2 `w1f-property-r2-e1e4` (both Claude Opus 5.5, `claude-opus-5-5`). **Grounded at:** `main` `5f34c261` (W0 rev 2, rulings R-87..R-93, the four W1-F reviews), merged into this branch. **Builds:** X-F in E1. X-LB adds loopback and fault cases in E4.

**What revision 2 changed.** It applies the four W1-F reviews ([Review disposition](#review-disposition)). The default rule is **W0 rev 2 wins**: the outcome table is W0's seven rows, the result line is capped at 64 KiB, a run that matches W0 rows 1-5 is NA for every metric, the suspend rule covers each phase, and E1 builds only what W0 does not list as "Not built in E1". The three revision-1 seam requests were granted in W0 rev 2, so their provisional marks are gone. Two new seam requests are open (§16).

## 1. Responsibility and boundaries

**One responsibility.** The grader turns one archived property cell into the narrowed property metric rows: `property_check_pass` plus the secondaries tagged with the task's property. It does this without letting the agent's deliverable decide its own score.

| It owns | It borrows (by identity, read-only) |
| --- | --- |
| `grade/property.py`: the grader, the check runner, classification, scoring and `at_scale` | the archive `run_dir/archive/<cid>/attempt-<n>/ws` (`CellInput.archive`) |
| `grade/bench_check.py`: the stdlib helper copied into every grading copy | the task's `oracle/check/` and `task.yaml` (`CellInput.task_dir`, `.task`) |
| `grade/_env.py`: the one `HOST_ENV`, `TOOLCHAIN_ENV` and `grading_env` (ADR-0018 §9, DM7) | `correctness.grade()`, the one definition of "hidden tests pass" (R-90 c2) |
| the `property` line in `runner.GRADERS` and the `property:` narrowing in `runner.applicable` | the catalog entries with their `property:` tag (W1-G / X-G1) |
| `procs.spawn(console=False)`, `CellProcess.exit_time()`, `procs.now_filetime()` | `host.SleepDetector` (spike A9) |
| the `task_canary` class in `egress.py` (R-E9) | `campaign.verify` and the campaign lock (X-C; ADR-0018 §11) |

**What crosses the boundary.** Into the grader: a `CellInput`. Out: one `Score` per applicable metric, plus one evidence file. Into the check: argv, an allowlisted environment, a fresh grading copy. Out of the check: one JSON line on its stdout, and nothing else the grader reads as a result.

**Out of scope here.** Loopback fakes and listeners (E4, X-LB; this design names the seam only, §5.5). Task content: probes, payloads and S1's check (W1-I). The rework, no-guessing and simplicity strategy helpers (X-J2, X-LG). No product code is written in this slice. The committed spike fixture (§15) is test code only.

## 2. Grounding (facts this design stands on)

Labels: **Verified** means read or run by this slice. **Inferred** means reasoned, with the confirming check named.

| # | Fact | Source | Label |
| --- | --- | --- | --- |
| G1 | A grader is `grade_cell(inp) -> Mapping[str, Score]`. A `Score` carries a reason only when its value is `None`. | `grade/__init__.py` (`Score.__post_init__`) | Verified |
| G2 | The runner gives each grader "every `kind: score` catalog metric of those graders". Nothing passes one grader's output to another. GradedOncePerPass raises HB-GRD-004 on a missing, duplicate or outside key. | `grade/runner.py` (`applicable`, `_grade_cell`, `_check_complete`) | Verified |
| G3 | `correctness.grade(ws, task_dir, oracle, out_dir, run_dir, timeout, work_dir)` copies the tree to `work_dir/work`, runs the oracle through `procs.run`, removes the copy and writes `oracle.log` into `out_dir`. | `grade/correctness.py:196-268` | Verified |
| G4 | `HOST_ENV` is defined twice (`correctness.py:48`, `mutation.py:38`). `DOTNET_HOST_ENV` differs between them: mutation adds `PROCESSOR_ARCHITECTURE` (`mutation.py:39-42`). | read | Verified |
| G5 | `procs.spawn` creates the process `CREATE_SUSPENDED \| CREATE_NO_WINDOW`, `close_fds=True`, assigns it to a kill-on-close job with breakaway never allowed, then resumes it. `Job.pids()` reads `JobObjectBasicProcessIdList`. A failed query raises. | `procs.py` (`_spawn_win32`, `Job`) | Verified |
| G6 | D3: only `procs.py` may call `subprocess.Popen`. R-60: only `{engine, gitsafe, grade/correctness, host, plan, procs, tools, workspace}` may reach `procs`. W0 rev 2 granted the two allowlist entries (X-D adds them). | `tests/test_architecture.py:44-51, 228`; W0 *Seam requests answered* | Verified |
| G7 | With the base interpreter and `DETACHED_PROCESS`, the job's process list is exactly `{check}` before and after the deliverable. Under the venv launcher or `CREATE_NO_WINDOW` it is not. | spike E1-S3 | Verified |
| G8 | `Popen(close_fds=True)` with explicit stdio is the handle list: a child cannot reach an inheritable pipe that is not in the list. `OpenProcess` plus `DuplicateHandle` still can, so ADR-0018 §10a is load-bearing. | spike E1-S2 | Verified |
| G9 | Grandchildren never leave the cell's job. Nothing survives `TerminateJobObject`. | probe N4 | Verified |
| G10 | `SleepDetector` flags a suspend when wall-clock time minus unbiased time exceeds its gap, compared since its own last call. A missing unbiased reading returns "not slept". | `host.py:154-172`; spike A9 | Verified |
| G11 | Views read the latest completed pass, and every pass grades every archived cell. So "re-run next pass" (HB-CHK-004) needs no new mechanism. | `views.py:178`; `runner.py` docstring | Verified |
| G12 | The base interpreter runs `json`, `ctypes`, `subprocess`, `msvcrt` and `hashlib` under `-S`, with no `site-packages` on `sys.path`. | run 2026-10-03, CPython 3.14.6 | Verified |
| G13 | `plan.tree_hash(base, files)` is the one content-address recipe (CRLF read as LF). | `plan.py:93` | Verified |
| G14 | The catalog (0.6) has no `property` key on any metric today. | `bench/metrics.yaml` | Verified |
| G15 | A module-body forgery inside the check process is **accepted** as a valid result. In the shipped probe-host shape (pipes the check owns) it is refused, and the honest host answers a probe. | spike SP-F2, revision 1 (3/3) and revision 2, committed (§15) | Verified |
| G16 | `shutil.copytree(..., symlinks=True)` **follows** a directory junction and copies its target's files into the copy. `shutil.rmtree` does not enter a junction (the target survives). | run 2026-10-03, CPython 3.14.6 (§15) | Verified |
| G17 | `_env.py` importing `correctness.DOTNET_HOST_ENV` at module top while `correctness.py` imports `HOST_ENV` from `_env.py` is an import cycle (`ImportError: ... partially initialized module`). | run 2026-10-03 (§15) | Verified |
| G18 | `grading_step_timeout` defaults to 900 s; `procs._KILL_GRACE` is 30 s. | `plan.py:52`; `procs.py:42` | Verified |

Quoted rules this design rests on (DC-189):
- ADR-0018 §1: "The check starts the deliverable as its own child (so it is in the same job), only through `bench_check.spawn_deliverable`".
- ADR-0018 §10a(b): "It accepts the result only if **all** hold: the pipe carried exactly one JSON document and no trailing bytes; when that document's first byte arrived, the grader's immediate job query showed the check alive and alone in the job; the check then exited by itself with the expected exit code, after the document arrived ...; and the outer bound did not fire."
- W0 rev 2 §3: "**Grader outcomes: evaluated in this order; the first matching row decides**". Row 1: "a host suspend gap in the phase's span". "Bounds per phase: ... The host-suspend rule (HB-CHK-004) applies to each phase's own span."
- W0 rev 2 §3 framing: "The document is one line of canonical JSON ended by `\n`, at most 64 KiB."
- W0 rev 2 §3: "Truth-table test: reference 1, naive 0, tamper NA, did-not-build 0."
- W0 rev 2 §3: "**Not built in E1:** `interface: loopback`, `bounds_ms.loopback`, `deliverable.config` and `kind: fault` keep their shape for seam stability. They are unread in E1, and W1-F does not build them".
- EV-1: "**Given** a cell whose deliverable does not build or start **When** the hidden check runs **Then** the primary metric is recorded as 0 with reason `deliverable did not build` (a measured failure)."
- R-90 c2: "The property grader calls `correctness.grade(ws, task_dir, oracle, out_dir, run_dir, timeout, work_dir)` ... in its own grading copy ..., never a re-implementation".
- R-90 c4: "`rework.py`, `noguess.py`, `diffstats.py` ... are called by `property.grade_cell` and are not registered in `GRADERS`".
- R-93: "The grader-side `hidden_tests_agree` half of RV-DS 10 stays rejected". The grader records `hidden_tests_pass`; X-E's `readiness.hidden_test_disagreements` compares it.

## 3. Data model (settled first)

**Bounded context.** Grading. Ubiquitous language: *hidden tests* (the correctness oracle), *hidden check* (the task's `oracle/check/`), *case* (one declared probe), *outcome* (a case's closed result), *result line* (the check's one JSON line), *acknowledgement* (the one byte), *phase* (tests, then check), *span* (one phase's wall time, the suspend rule's unit), *check run* (one execution of the check for one cell in one pass), *measured 0* versus *NOT_RECORDED*.

**Aggregate.** `CheckRun`. Its root is identified by `(grading_id, cell_id)`. Its one invariant: **the grader accepts at most one result line, and only from a live check that is alone in its job, whose own clean exit follows that line, in a run with no suspend in either phase's span. Otherwise every metric of the run is NOT_RECORDED** (W0 rows 1-5). Everything else is a value object: `CaseDecl` (id, kind, bound), `CaseResult` (id, outcome, duration), `ResultDoc`, `Span` (wall_ms, suspended, unbiased_ok), `Classification` (row, code, reason). A `CheckRun` references the cell, the task version and the pass by identity only. It is never persisted as an entity. It is the unit of one transaction: the grader writes its rows and its evidence file once.

**Durable representation. No new fact table.** The grader writes into two existing stores:

| Store | Grain ("one row is exactly one ...") | Writer | Compute readers | History rule |
| --- | --- | --- | --- | --- |
| `scores` ledger fact (existing, ADR-0006) | one metric value of one cell in one grading pass, identified by `(grading_id, cell_id, metric_id)` and recorded at the pass | `runner._score` | views, board, readiness (X-E), verdicts and gates (X-H1), the campaign section (X-H2) | append-only per pass (existing); a re-grade is a new pass, never an update |
| `grading/<gid>/<cid>/property/property.json` (new evidence file) | one check run: the inputs a score row was derived from, identified by `(grading_id, cell_id)` and recorded when the grader returns | `property.grade_cell` | `Score.evidence` pointers; X-E's `readiness.hidden_test_disagreements` (R-90 c3, R-93); the pilot gate (EV-14); reports via the egress gate | written once per pass, under the pass's own `out_dir`; never rewritten |

**Measures and their additivity (DM9).**

| Metric | Built in E1? | Class | Derivation (derive-don't-store, DM7) |
| --- | --- | --- | --- |
| `property_check_pass` | yes | non-additive across metrics; additive as a pass count across cells | derived by the grader from the hidden-test result and the cases (§5.7); never taken from the check |
| `exploit_probes_blocked` | yes | non-additive (a ratio: recompute from counts, never average ratios) | `blocked ÷ probe cases`, by the grader from `cases` |
| `fault_suite_pass` | no (E4, X-LB; W0 "Not built in E1") | non-additive (ratio) | W0 §3: passed fault cases ÷ fault cases, by the grader |
| `idempotency_violations` | no (E4, X-LB) | additive across cells (a count) | W0 §3: the one non-derivable `measures` key for resilience |
| `rework_ratio`, `turn1_tests_pass` | no (X-J2, E2) | — | strategy helper `rework.py` |
| `hallucinated_symbol_errors`, `verified_before_use` | no (X-LG, E4) | — | strategy helper `noguess.py` |
| `size_vs_reference`, `new_abstractions`, `new_dependencies` | no (X-LG, E4) | — | strategy helper `diffstats.py` |

The derived score rows are the ledger's record. The evidence file keeps their inputs, so a **rebuild test** recomputes every derived row from `property.json` and asserts equality (`test_derived_measures_rebuild_from_evidence`).

**Evidence file `bench-property-evidence/1`.** Every field has a writer (`property.grade_cell`) and a named reader:

| Field | Reader |
| --- | --- |
| `task`, `task_version`, `cell_id`, `grading_id`, `property`, `seed`, `interface` | discrimination record (X-E), re-grade determinism test |
| `hidden_tests[tree] = {hidden_tests_pass, partial_credit, reason, evidence, hidden_tests_ms}` (W0 §3 names) | `readiness.hidden_test_disagreements` (X-E; R-90 c3, R-93) compares the final tree's `hidden_tests_pass` with the pass's `pass_at_1` row. The grader writes no agreement field (R-93). |
| `spans = {tests[tree]: Span, check: Span}`, `Span = {wall_ms, suspended, unbiased_ok}` | HB-CHK-004 evidence; the pilot gate (`unbiased_ok: false` is an item, seam req-…V67); SRE |
| `check.classification = {row, code, reason}`; `check.deliverable` | pilot gate (EV-14), report |
| `check.cases[] = {id, kind, outcome, duration_ms}`; `check.measures`; `check.first_failing_case` | rebuild test; the report (W0 measured-0 rule) |
| `check.hash_before`, `check.hash_after` | HB-CHK-002 evidence (row 3) |
| `check.handshake = {first_byte_ft, job_view_at_arrival, documents, trailing_bytes, acked, exit_code, exit_ft, outer_bound_s, bound_fired}` | HB-CHK-002/003 evidence (rows 2 and 4); SRE |
| `check.copy.skipped_reparse_points[]` (relative paths only) | SEC review; report (egress-scanned) |
| `check.stdio[]` (each file's path, bytes, `truncated`) | SRE; report (egress-scanned) |

No field is a free text from the deliverable. Deliverable stdio is copied to files beside the evidence, at most 64 KiB each, and those files reach a judge or a report only through `egress.check` (US-47).

**Schema changes.** The only one is the catalog `property:` tag (X-G1 writes it; ADR-0019). It is additive: a metric without the tag keeps today's behaviour. So there is no migration and no backfill. A re-grade of an old run under 0.7 adds no property rows for tasks that do not name `property` (ADR-0019 item 6, `test_catalog_version`).

## 4. Delivery phasing and mock-substitutable seams

- **E1 slice (this build).** Security task S1: `interface: in-process`, `kind: probe` cases, `app.kind: callable`. Real parts: the runner narrowing, `property.grade_cell`, `bench_check` (spawn, sweep, write-once, probe host), the procs additions, `_env.py`, `at_scale`, the egress class. Mocked: nothing in the product path. Tests use fixture checks and fixture deliverables (§14). This is enough for W1-E's discrimination run of S1 and the E1 pilot.
- **Not built in E1** (W0 §3; RV-SIM W1-F 2, 3). `interface: loopback`, `kind: fault`, `kind: static`, `app.kind: wsgi`, the `resilience` strategy, `fault_suite_pass` and `idempotency_violations`. A task that declares any of them is NA `not built` for every metric, before any copy is made. Readiness (X-E) refuses them in E1 (HB-RDY-005). The keys keep their W0 shape, so no task file changes when they are built.
- **E2.** `rework.py` plugs into the strategy table and calls `correctness.grade()` once per tree.
- **E4.** X-LB adds loopback (the listener helper, HB-CHK-005, spike S-LB), `kind: fault`, the `resilience` strategy and its two metrics. `wsgi` is added when W1-I or W1-L names a web-shaped deliverable. X-LG adds the no-guessing and simplicity helpers.

**Mock-substitutable seams (named).**
1. `STRATEGIES[property.name]`: a missing helper gives NA `not built` for its metrics (a Special Case, not an error).
2. `bench_check.listen()`: the loopback seam for X-LB, not built in E1.
3. The fault seams in `property.py`: `_job_view_at_arrival` (the first-byte job query), `_now_filetime`, `_exit_filetime` and `_sleep_detector` (one per span). These follow the `procs._query` pattern. The race test, the exit-time test and the suspend tests use them (§14).
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
STRATEGIES: dict[str, Callable[[CellInput, GradeContext], dict[str, Score]]] = {"security": _hidden_check}
```

`GradeContext` is the grader-side context (the plan's `grading_step_timeout`, the seed, the narrowed metric set). It is not `bench_check.Context`, the check-side one (RV-PAT W1-F 8). Later helpers each add one line when they exist: `rework.grade` (E2, X-J2), `noguess.grade` and `diffstats.grade` (E4, X-LG), and `"resilience": _hidden_check` (E4, X-LB). Under R-90 c4 none is registered in `GRADERS`.

1. If `sys.platform != "win32"`, every metric is NA `not built`. The runner is Windows-only (ADR-0018 §8).
2. Pick the strategy by `inp.task["property"]["name"]`. If none, or the task declares a §4 "Not built in E1" item, every metric is NA `not built`.
3. `_hidden_check` runs the phases **in this order** (W0 §3 *Invocation*). Every copy lives under `inp.work_root` (`cells_root/grading/<gid>/<cid>/property/`, ADR-0013 Am. 2). **Each phase has its own span**: a fresh `_sleep_detector()` (`host.SleepDetector(PROPERTY_SUSPEND_GAP_S)`) is made when the phase starts and read once (`slept()`) when it ends. The span records `wall_ms`, `suspended` and `unbiased_ok` (whether both unbiased readings were present, `host.py:166`).
   1. **Hidden tests.** `correctness.grade(inp.archive / "ws", inp.task_dir, oracle, inp.out_dir / "tests", inp.run_dir, timeout, inp.work_root / "tests")`, once per graded tree. `procs.run` closes that job (kill-on-close, no breakaway), so no test-run process survives into the next phase (G5, G9). The phase records `hidden_tests_pass` and `hidden_tests_ms`.
   2. **Fresh check copy.** `check-run/deliverable/` is copied **from the archive**, never from the tests copy: no `.git`, no build output, symlinks kept as links, and **no reparse point followed** (below). Then `check-run/check/` holds `oracle/check/*` plus `grade/bench_check.py`. The grader parses `cases.yaml`, validates it and writes `check-run/check/cases.json` with sorted keys. **Last**, it computes `hash_before = plan.tree_hash(check/, every file under check/)`.
   3. **Run the check** (§5.3). Then confirm the job is empty and close it.
   4. **`hash_after`** over the same file list, plus any new file under `check/`.
   5. **Classify** (§5.6), **score** (§5.7), copy the stdio files to `out_dir/check/`, write `property.json`, and remove `check-run/` on every path.
4. `timeout` is `inp.plan["parameters"]["grading_step_timeout"]`. It bounds each phase separately, as it does in correctness. **Whole-step ceiling** (W0 §3 asks for it): one tree is at most `2 × grading_step_timeout + 2 × procs._KILL_GRACE` plus the copy and the two hashes, so `2 × 900 + 2 × 30 = 1,860 s` plus copy time with the default plan (G18; bound arithmetic, Inferred). The measured value of every run is in `spans`; the E1 pilot reports its maximum.

**Reparse-safe copy and removal (RV-SEC W1-F 3).** `shutil.copytree` follows a directory junction and copies the target's files (G16), so the check copy does not use it. `property._copy_tree(src, dest)` walks with `os.scandir` and `entry.stat(follow_symlinks=False)`. An entry whose `st_file_attributes` has `FILE_ATTRIBUTE_REPARSE_POINT` is never entered. A symlink is reproduced as a link (today's `_changes.grading_copy` semantics). Any other reparse point (a junction, a mount point) is **not reproduced** and its relative path goes into `check.copy.skipped_reparse_points`. Removal is `shutil.rmtree`, which does not enter a junction (G16). Its `onexc` handler `lstat`s the path first: a reparse point is unlinked (`os.unlink`, or `os.rmdir` for a directory link) and never `chmod`ed; only a plain entry gets `archive.make_writable`. `test_grading_copy_with_junction_leaves_target_untouched` proves both halves. The hidden-tests phase keeps `correctness.grade`'s own copy (R-90 c2); that copy has the same junction behaviour, which is a class finding for the Coordinator (RF-9), not built here.

### 5.3 Check invocation and handshake (ADR-0018 §1, §10a; spike E1-S3 and SP-F2)

```
argv  = [sys._base_executable, "-S", "check/<entry>",
         "--deliverable", <abs check-run/deliverable>, "--cases", "check/cases.json",
         "--seed", <int>, "--evidence", <abs out_dir/check>]        # W0 §3; evidence outside the copy
env   = _env.grading_env(declared toolchain names)                  # §5.9; never os.environ
spawn = procs.spawn(argv, cwd=check-run, env=env, stdin=PIPE, stdout=PIPE,
                    stderr=<out_dir/check/check.stderr>, console=False)   # DETACHED_PROCESS, suspended, then in a new job
seed  = int(sha256(f"{task_version}|{cell_id}|property_check_pass").hexdigest()[:16], 16)
```

- `-S` keeps the base interpreter's `site-packages` off the path (G12). `PYTHONPATH` cannot reach the check, because the allowlist never carries it.
- **Grader side, in order.**
  1. A reader thread drains stdout in chunks from the start. It keeps at most `MAX_RESULT_BYTES = 64 * 1024` (W0 framing). Beyond that it counts bytes but stores nothing, so the writer never blocks.
  2. **On the first byte:** record `first_byte_ft = _now_filetime()`, then `job_view_at_arrival = _job_view_at_arrival(spawn.job)`. A query that raises is recorded as `"query failed"`. Classification reads that as "not alone" (fail-closed, G5).
  3. On the first `\n` (or EOF, or the bound): parse and validate the line (§5.6 row 5). **Accept** only when the line is valid and the job view is exactly `{check pid}`.
  4. If accepted, write the one byte `0x06` to the check's stdin. **On every path, close the check's stdin.** EOF without the byte means "refused". The check then exits 3 at once. It never waits for the bound (spike: about 1 ms).
  5. Wait for the exit within the remaining bound. Read `exit_ft = _exit_filetime(spawn)` (`spawn.exit_time()`, `GetProcessTimes` on the grader's own process handle). Drain stdout to EOF, within `procs._KILL_GRACE`.
  6. Then `terminate_and_confirm`, and close the job.
- **Check side (`bench_check`).** Outcomes stay in memory. `write_result` sweeps the job, waits until the check is alone, writes one line, flushes, then blocks on `stdin.read(1)`.

**Exit codes, in one place (RV-SIM W1-F 8).** None of them is a result; each only feeds a row of §5.6.

| Exit | Set by | Meaning | Row it feeds |
| --- | --- | --- | --- |
| 0 | check, after reading `0x06` | the line was accepted | 6 or 7 when every process fact is clean; row 4 otherwise |
| 3 | check, on stdin EOF with no byte | the line was refused | row 5 when the line was malformed and the process facts are clean; row 4 when the refusal was for "not alone" |
| 4 | check, not alone within 5 s; writes no line | the sweep failed | row 4 ("no line") |
| 5 | check's `main`, uncaught error; writes no line | a check bug | row 4 ("no line"; W0 has no separate row). `check.stderr` holds the traceback |
| 10 | probe host, import failed | the deliverable did not start | none directly: the check records `deliverable: did not start` (row 6) |
| other, or none | a kill | — | row 2 when the bound fired, else row 4 |

### 5.4 `bench_check.py`: the helper API (stdlib only; copied in; never authored in a task)

| Function | Contract |
| --- | --- |
| `load() -> Context` | Parses the argv of §5.3 and reads `cases.json`. `Context.rng = random.Random(seed)`. `Context.bound_ms(case)` is the effective bound, `min(case.bound_ms, bounds_ms[interface])`. An omitted case bound means the interface bound. |
| `spawn_deliverable(argv, env_extra=None, *, tag, pipes=False) -> Child` | Replaces `{python}` with `sys._base_executable` (the `correctness.py:209` convention). Uses `subprocess.Popen(close_fds=True, creationflags=DETACHED_PROCESS)` with all three stdio handles explicit. With `pipes=False`: stdin is `DEVNULL`, and stdout and stderr go to `deliverable/.bench-stdio/<tag>.{out,err}` in the copy. With `pipes=True`: stdin and stdout are pipes the **check** owns (the probe host only). The environment is the check's own (already the allowlist, §5.9) plus `env_extra`. `env_extra`'s keys must be `HB_CHECK_*` or a declared `env` name, else `ValueError`. **An `HB_CHECK_*` value comes only from `env_extra`**, set by the check's code; it is never read from the check's own environment (RV-SEC W1-F 5). There is no `close_fds` parameter and no `lpAttributeList` (spike E1-S2 finding 1). |
| `build() -> bool` | Runs `deliverable.build` (if declared) through `spawn_deliverable`, never a bare subprocess. A non-zero exit records `deliverable: "did not build"`. |
| `probe_host(case) -> ProbeHost` | §5.5. A failed start records `deliverable: "did not start"`. |
| `run_case(case, fn)` | Times the case with `time.monotonic`, enforces `bound_ms(case)`, and turns a bound overrun into `timeout` after `sweep()`. Turns a broken probe-host exchange into `exploited` (fail-closed). |
| `sweep(bound_s=5)` | Terminates every job member except the check (`QueryInformationJobObject(NULL, BasicProcessIdList)`, then `OpenProcess(PROCESS_TERMINATE)` and `TerminateProcess`), and repeats until alone. Spike SP-F1: one round, about 10 ms, for a deliverable plus a grandchild plus a console host. |
| `write_result(cases, measures=None)` | Adds `schema` and `deliverable` itself. Writes once, last and alone, as one line of canonical JSON, then waits for the acknowledgement (§5.3). It never returns. |
| `main(check_fn)` | Wraps the task's check. An uncaught exception writes the traceback to stderr and exits 5. |

**Result line** (W0 §3, verbatim shape):

```json
{"schema": "bench-check-result/1", "deliverable": "ran",
 "cases": [{"id": "inj-1", "outcome": "blocked", "duration_ms": 41}],
 "measures": {}}
```

`deliverable` is one of `ran`, `did not build` or `did not start`. With `ran`, every declared case appears exactly once. Otherwise `cases` is `[]`. In E1 every case is a `probe`, and its outcome is `blocked`, `exploited` or `timeout`. `measures` may carry **only** the non-derivable metric ids of the narrowed set; for `security` that set is empty, so `measures` must be `{}`.

### 5.5 In-process probes: the probe-host child (W0 §3 `in-process`, redefined)

**The check process never imports deliverable code** (W0 rev 2 §3; ADR-0018 §1). Spike SP-F2 reproduced the exploit `sys.stdout.write(<forged blocked>); sys.stdin.buffer.read(1); os._exit(0)` against the in-check shape: **accepted**. Revision 2 committed that fixture with its positive control and ran it against the shipped pipes shape (§15).

- **Shape.** `<base> -S check/bench_check.py --probe-host --root <deliverable> --app <module>:<attr>` is spawned by `spawn_deliverable(..., pipes=True)`, one host per case. It inserts `--root` into `sys.path`, imports the app, writes **one ready line** `{"ready": "bench-probe-host/1"}`, then serves JSON lines until stdin EOF. An import failure exits 10.
- **The start, bounded (RV-TA W1-F 5).** The check reads the host's stdout on a reader thread. The start ends at the host's **first line**, and it waits for that line at most the case's effective bound `bound_ms(case)` (the host start is inside the case's span). Three ends, each deterministic:
  - the first line is the ready line: the host started; the probe runs within what is left of the bound;
  - the host exits before any line, or its first line is **anything other than the ready line**: the check closes the host's stdin, sweeps, and records `deliverable: did not start` (W0: "a start or import that raised, or a process that exited before it was ready"). A forged result line written at import is such a line;
  - no line within the bound: the check sweeps and the case is `timeout` (EV-3's measured hang; spike-free, by construction). The run never reaches the outer bound on a hung import.
- **Lines** (UTF-8, at most `PROBE_LINE_MAX = 1 MiB`, one per line; a different cap from the 64 KiB result line):
  - `callable`: request `{"id": n, "args": [...], "kwargs": {...}}`; response `{"id": n, "ok": true, "value": <json>}` or `{"id": n, "ok": false, "error": "<exception type name>"}`.
  - `wsgi`: not built in E1 (§4). The `kind` key stays, so a task does not change when it is built.
- **The reader is bounded (RV-SEC W1-F 6).** The host-side reader thread uses `readline(PROBE_LINE_MAX + 1)`. A line longer than the cap, or a line with no newline by the case bound, ends the exchange: the check stops reading, closes the host's stdin, sweeps (which ends the reader's blocking read by killing the writer), joins the reader with a timeout of 1 s, and records the probe's failing outcome, `exploited`. Nothing grows without bound, and a blocked pipe read never outlives the case bound plus the sweep.
- **Decisions stay in the check.** The check builds the payload, reads the raw response and decides the outcome in its own process. Agent code in the probe host can only shape the responses, and that is the deliverable's behaviour, which is what a probe measures.
- **One host per case.** That gives the per-case bound and isolation for free. `simplify:` one host start per case (about 40-80 ms measured in SP-F2). Ceiling: about 50 cases per task. Upgrade trigger: host start time above 10 % of a check's wall time.
- **Residual (RV-SEC W1-F 8).** The host runs agent code in the same grading copy as `check/`, so it can read the check source and the cases. RF-8.
- **Loopback (E4, X-LB): seam only.** `bench_check.listen()` binds `("127.0.0.1", 0)` and asserts `getsockname()[0] == "127.0.0.1"` (ADR-0018 §3, HB-CHK-005). It is not built in E1.

### 5.6 Classification: W0's seven rows, first match decides

This is an **ordered decision table**: one function, `_classify(facts) -> Classification(row, code, reason)`, a list of rows, the first that holds decides the run. It is not a handler chain (RV-PAT W1-F 7). The rows, conditions and results are W0 rev 2 §3's, verbatim in substance; the column "how the grader reads it" is this design's.

| Row | W0 condition | How the grader reads it | Result |
| --- | --- | --- | --- |
| 1 | a host suspend gap in the phase's span | `spans.tests[tree].suspended or spans.check.suspended` | NA `host suspended`, re-run next pass (HB-CHK-004) |
| 2 | the outer bound fired | no exit within `grading_step_timeout`, in the check phase | NA `check exceeded its bound` (HB-CHK-003) |
| 3 | the `check/` hash after the exit differs from the hash taken at copy time | `hash_after != hash_before` | NA `invalid (check tampered)` (HB-CHK-002) |
| 4 | a §10a(b) failure: not alone in the job at the line's first byte; more than one line, or trailing bytes; an exit before the line arrived; no line; exit code ≠ 0 after the ack, or ≠ 3 after a refusal | `job_view_at_arrival != {check}` (a failed query counts); `documents != 1` or trailing bytes; `exit_ft <= first_byte_ft` (an equal stamp is read as "before": fail-closed); no line at EOF, whatever the exit code (so exits 4 and 5 land here); exit code ≠ 0 after the ack, or ≠ 3 after a refusal | NA `invalid (check tampered)` (HB-CHK-002) |
| 5 | the line is malformed (schema, size, case ids, `measures` keys or values) | not JSON; over 64 KiB; wrong `schema`; `deliverable` out of its set; an undeclared, missing or duplicate case id; an outcome outside the probe set; any `measures` key outside the narrowed non-derivable set, or a value that fails `at_scale` | NA `check output invalid` (HB-CHK-001) |
| 6 | `deliverable` is `did not build` or `did not start` | the accepted line says so | `property_check_pass` = **0**, a measured failure (EV-1) |
| 7 | otherwise | — | the scores, by the predicate (§5.7) |

- **Why this order** (W0's reasoning, kept). A suspend explains everything after it. A bound kill makes every later process fact an artifact of the kill. Row 3 before row 4: both are tamper and the hash is the stronger evidence. Rows 3 and 4 before row 5: a forger's line could also be malformed, so tamper wins and a forger cannot choose the cheaper label by writing garbage.
- **Rows 3 and 4 share a code but not a row.** `Classification.row` is recorded in evidence and asserted by every precedence test, so a swap of rows 3 and 4 is caught (RV-TA W1-F 1, 4).
- **Row 3 is load-bearing only on an otherwise clean run.** The test `test_check_tree_changed_is_tampered[clean_exit]` is that run: the deliverable rewrites a `check/` file, and the honest check writes one valid `blocked` line, alone, is acknowledged and exits 0. Without row 3 that run scores. Its mutation entry, in `tests/mutations/property.json` (X-F writes `_classify`'s row-3 line exactly as the `find` text):

```json
{"name": "row 3 deleted: a changed check tree with a clean handshake scores (W0 s3 row 3)",
 "file": "src/harness_bench/grade/property.py",
 "find": "    if facts.hash_after != facts.hash_before:",
 "replace": "    if False:",
 "tests": ["tests/test_property_grader.py::test_check_tree_changed_is_tampered[clean_exit]"]}
```

- `PROPERTY_SUSPEND_GAP_S = 1.0`, applied to each span. The engine's 60 s gap would let a short suspend flip a 2 s case into a measured `timeout` (spike A9 residual). A false positive (for example, an NTP step over 1 s) costs only an NA and a re-run, never a wrong score. `simplify:` this is a fixed constant. Upgrade trigger: an HB-CHK-004 rate above 1 % of check runs in a pilot.
- **An unreadable unbiased clock is not silent (RV-TA W1-F 8).** `SleepDetector.slept()` returns False when a reading is missing (G10), so the suspend rule is off for that span. The span records `unbiased_ok: false`, and seam req-…V67 asks X-H1 to make that a pilot-gate item.

### 5.7 `property_check_pass` and the derived secondaries

**Check passes** ⇔ `deliverable == "ran"` and every declared case ended `blocked` or `passed` (W0 predicate). In E1 every case is a probe, so that means `blocked`; `passed` belongs to the fault and static kinds, not built in E1. `exploited` and `timeout` each fail it.

**The run's row decides first** (W0: "the first matching row decides"; RV-PAT W1-F 1, RV-TA W1-F 3c). Under rows 1-5 **every** metric of the run is NA with that row's reason, whatever the hidden tests said: W0's "tamper NA". Under row 6 the primary is 0. Only under row 7 do the hidden tests and the cases combine, in Kleene logic (a known false conjunct gives 0; otherwise an unknown gives NA):

| Run row | hidden tests (`hidden_tests_pass`) | cases | `property_check_pass` |
| --- | --- | --- | --- |
| 1-5 | any | any | NA, the row's reason |
| 6 | any | — | **0** (EV-1; the reason goes in evidence only, W0 measured-0 rule) |
| 7 | true | all `blocked` | **1** |
| 7 | true | one fails | **0** |
| 7 | false | any | **0** |
| 7 | NA (correctness's own reason) | all `blocked` | NA, the hidden tests' reason |
| 7 | NA | one fails | **0** |

A hidden-tests NA caused by a suspend is row 1, not a row-7 NA: a suspend in the tests span voids the run before the tests' own result is read (RV-TA W1-F 2).

**Secondaries**, under row 7: `exploit_probes_blocked = at_scale(Decimal(blocked) / Decimal(probe cases), 4)`. Zero probe cases give NA `no probe case declared` (readiness prevents it; HB-RDY-005). Under rows 1-5, every secondary is NA with the row's reason. Under row 6, NA with the deliverable text.

**`at_scale(value, scale) -> int | Decimal`** (W0 §2 *One normaliser*; RV-SIM W1-F 5). It lives in `grade/property.py`; readiness imports it, never a copy. `scale` is the catalog's (`runner._scales`). An int-scale value must be a JSON int (`bool` refused). A scaled value is quantised with `ROUND_HALF_EVEN`; on input from a check it must be a string with exactly `scale` decimals (`"1.0000"`), and `"1.0"`, `1` and `1.0` are refused. The grader uses the same function to validate any `measures` value (row 5) and to quantise its own ratios.

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

These are Windows-only (POSIX raises `OSError`; the runner is Windows-only, ADR-0018 §8). `procs.py` is a run-class file (W0 §9), so an edit to it is a run-side identity change; the default path must stay byte-equal in behaviour: `test_spawn_default_flags_unchanged` asserts `CREATE_SUSPENDED | CREATE_NO_WINDOW` when `console` is not passed (RV-PAT W1-F 11). W1-D confirms the class of `procs.py` and `egress.py`.

### 5.9 `grade/_env.py`: one allowlist (ADR-0018 §9; W0 §3 `env`, §10 G4)

```python
HOST_ENV = ("PATH", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "TEMP", "TMP")     # moved here; G4's one definer
def toolchain_env() -> frozenset[str]: ...   # frozenset(correctness.DOTNET_HOST_ENV), imported inside the function
def grading_env(extra: Iterable[str] = ()) -> dict[str, str]   # HOST_ENV + CELL_ENV + PYTHONDONTWRITEBYTECODE/HASHSEED=0/UTF8 + extra
def denied(name: str) -> bool                # imports profiles.DROP_EXACT / DROP_PREFIXES (never a copy) + HB_CLAUDE_OAUTH_TOKEN, GH_TOKEN
```

- **W0 as written** (G4): `HOST_ENV` moves to `_env.py`; `correctness.py` and `mutation.py` import it; `mutation.py`'s `__all__` keeps re-exporting the name. **`DOTNET_HOST_ENV` stays where it is** in both modules, because the two tuples differ (G4). `ENVIRON_READERS = {"grade/_env.py"}`: only `_env.py` reads `os.environ` among the G4-scanned files.
- **`TOOLCHAIN_ENV`, provisional (seam req-…V6HZ).** W0 names `_env.TOOLCHAIN_ENV` and says a dotnet toolchain's names are `correctness.DOTNET_HOST_ENV`, "imported, never copied". With `correctness` importing `HOST_ENV` from `_env`, a module-top import the other way is a cycle (G17). Until the Coordinator rules, the name is the function `toolchain_env()` with the import inside it. The seam asks W0 to move correctness's tuple verbatim to `_env.py` instead (one home, no cycle, mutation's own tuple unchanged).
- `correctness._env()` becomes `_env.grading_env()`. Its `DOTNET_HOST_ENV` merges keep their keys and values. The US-4 control (`test_catalog_version`) and the correctness and mutation suites prove the move byte for byte.
- A `cases.yaml` `env` name must be in the toolchain names or start with `HB_CHECK_`, and must not be `denied` (readiness HB-RDY-005; X-E). The grader re-checks it when it writes `cases.json`: a bad name is a task defect, not check output, so the grader raises `ValueError` before any copy, and the runner's existing HB-GRD-003 makes every metric NA with the message as evidence. No new reason text; readiness is the place that stops it first.

### 5.10 `egress.py`: the `task_canary` class (R-E9; X-F owns `egress.py` in E1)

`TASK_CANARY = re.compile(r"\bBENCHCANARY-[A-Z0-9]{1,8}-[0-9a-f]{16,}\b")` is added to `CLASSES` as `task_canary`. It always runs, because the shape is known without a caller-supplied value. A payload carrying a planted canary is withheld with that class. Evidence excerpts reach a judge or a report only through this gate (US-47).

### 5.11 Campaign hooks (ADR-0018 §11; W0 §10 "seam X-C → X-F"); call shapes from W1-C

- **Before** taking `grade.lock`, `run_pass` refuses while `campaign.lock` is held: `HB-CMP-001`, raised through X-C's `campaign.lock_held(root)`.
- **After** a completed pass of a campaign run, `run_pass` calls `campaign.verify(root, campaign_id)`. A failure raises `HB-CMP-003` after the pass is sealed. The pass stays completed; the operator sees the failure. Both call shapes are X-C's (W1-C's design). X-F adds only these two lines.

## 6. Patterns (named and justified; Patterns Expert versus Simplifier)

| Pattern | Where | Why it earns its place (and the rung of the Solution-Selection Ladder) |
| --- | --- | --- |
| **Strategy via a registry** (existing, `runner.GRADERS`) | one `property` entry; `STRATEGIES` by property | R-90 forbids a second registered grader. One dict line per helper (rung 2: reuse). |
| **Special Case** (existing NA `Score`) | every non-score outcome | the codebase's own NA idiom; no exception crosses the grader boundary |
| **Gateway** (existing `procs`) | the check spawn, job view, exit time | D3/R-60: the bench reaches processes only through `procs` (rung 2) |
| **Acknowledged Message** (one-byte ack) | §5.3 | spike E1-S3: arrival timing alone is unsound (4-8 ms margins). The smallest stdlib form: one byte, no framing library. |
| **Out-of-process Proxy (sandboxed broker)** | the probe host, §5.5 | the only way to keep agent code out of the deciding process while staying stdlib-only. Rejected: running decisions in the probe host (SEC F1 again). |
| **Ordered decision table** | §5.6 | one function over a row list, first match wins; no handler objects (Simplifier) |
| **Parameter Object** (existing `CellInput`) | the grader input | unchanged |

Rejected, with reasons:
- **A nested Job Object per deliverable.** It works on Windows 8+, but it adds `CreateJobObject`/`AssignProcessToJobObject` code to the stdlib helper. The pid sweep (SP-F1) reuses the query that the "alone" test already needs.
- **An HMAC or nonce on the result line.** The deliverable can read the check's memory, so it adds no protection against a same-user process (ADR-0018 §10a residual).
- **A third test runner for property tests.** R-90 c2 forbids it.
- **A port allocator.** ADR-0018 §3 uses port 0.
- **Fault, static, `wsgi` and `resilience` in E1.** No E1 caller (W0 "Not built in E1"; RV-SIM W1-F 2, 3).

**Ladder.** No new dependency (stdlib and existing modules only). Bounded choices are marked `simplify:` in §5.5 (one host per case) and §5.6 (the 1 s suspend gap).

## 7. Change-surface list (E7)

| Layer | Surface | Owner · phase |
| --- | --- | --- |
| store | `scores` rows (existing grain); new evidence file `property.json`; deliverable stdio copies | X-F · E1 |
| catalog | eleven entries with `property:` tags, `0.7.dev` | X-G1 · E1 (W1-G) |
| task contract | W0 §3 (`app:`, `deliverable`, `cases.json`, the env rule), already in W0 rev 2; `tasks/README.md` property section | Coordinator (done in W0 rev 2) |
| model | `CheckRun`, `ResultDoc`, `CaseDecl`, `Span`, `Classification`, `GradeContext` dataclasses in `property.py` | X-F |
| service | `runner.applicable(prop)`, `GRADERS["property"]`; `property.grade_cell`, `_classify`, `_copy_tree`, **`at_scale`** (readiness imports it); `bench_check.py`; `_env.py`; `procs.spawn(console)`, `exit_time`, `now_filetime`; `egress` `task_canary`; `correctness`/`mutation` import `HOST_ENV` | X-F · E1 |
| guards | G4 and G5 (`tests/test_property_grader.py`); D3 and R-60 allowlist entries in `tests/test_architecture.py` (granted in W0 rev 2) | X-F; X-D |
| run/grade class | `grade/property.py`, `grade/bench_check.py`, `grade/_env.py`: `grade` (W0 §9) | X-D seeds |
| projection/wire | views unchanged (score rows); readiness reads the narrowed set through `runner.applicable` and normalises through `property.at_scale` | X-E |
| client type | none (CLI and files only) | — |
| UI | the report's campaign section shows the property metrics, NA reasons and NA counts (seam req-…V67) | X-H2 |
| compute readers | `readiness.hidden_test_disagreements` (X-E; R-90 c3, R-93) reads `hidden_tests_pass`; verdicts and pilot gate (X-H1; HB-CHK-* and `unbiased_ok` as gate items, seam req-…V67) | X-E, X-H1 |
| errors | HB-CHK-001..004 confirmed (HB-CHK-005 stays X-LB's); no new code | X-D adds them to `errors.py` |
| campaign hooks | `run_pass` lock refusal and the after-pass verify | X-F lines, X-C APIs |

## 8. Error and concurrency model

- **Errors.** No exception leaves `property.grade_cell` for an expected outcome; each one is a `Score` (§5.6, §5.7). An unexpected exception falls to the runner's existing HB-GRD-003 (NA for every metric, the traceback as evidence).
- **Concurrency inside one run.** Two threads in the grader: the main thread and the stdout reader. The reader owns `buf`, `first_byte_ft` and `job_view_at_arrival` until it sets `line_ready` or `eof`. The main thread reads them only after one of those events (a happens-before through `threading.Event`). The acknowledgement and the stdin close happen on the main thread only. Inside the check, the probe-host reader thread is bounded the same way (§5.5).
- **Across runs.** A pass grades cells one at a time (`runner.run_pass`). Two passes cannot overlap (`grade.lock`, HB-GRD-001). Parallel grading slots (EV-3) are isolated by separate jobs, copies and ports (port 0, E4). Each copy's path includes `grading_id` and `cell_id`.
- **Idempotency.** A re-grade of one archive reproduces every case outcome (fixed payloads; seed from `(task_version, cell_id, metric)`). The grading copy is removed on every path, and a leftover from a crashed pass sits under a different `grading_id`.

## 9. Failure-mode analysis

| # | Failure mode (category) | Disposition | Detection / test |
| --- | --- | --- | --- |
| F1 | the deliverable hangs (time) | **mitigate**: the case bound; `sweep()`; outcome `timeout`, a measured failure (EV-3) | `test_hanging_deliverable_with_grandchild_is_a_measured_timeout` |
| F2 | the deliverable leaves processes after a case (resources) | **prevent**: `sweep()` before every write; `write_result` writes only when alone | the same test, plus `test_write_result_never_writes_while_not_alone` |
| F3 | the deliverable forks faster than the sweep (resources) | **detect**: exit 4 with no line gives row 4, HB-CHK-002; never a score. The NA count reaches the pilot gate (seam req-…V67) | `test_unsweepable_job_is_tampered_not_scored` |
| F4 | the check itself hangs or ignores its bound (time) | **mitigate**: the outer bound, `TerminateJobObject`, HB-CHK-003 | `test_outer_bound_fired_is_hb_chk_003` |
| F5 | malformed or oversized result (input) | **detect**: row 5, HB-CHK-001; stdin closed so no bound wait | `test_malformed_document_is_hb_chk_001_without_waiting_for_the_bound`, `test_result_over_64kib_is_hb_chk_001` |
| F6 | a check bug raises (dependency: task check) | **detect**: exit 5 and no line, row 4 (HB-CHK-002, W0); traceback in `check.stderr`, exit code in evidence | `test_check_error_exit_5_without_a_line_is_row_4` |
| F7 | the host suspends during a phase (time) | **detect**: row 1, HB-CHK-004, re-run next pass, for **either** span | `test_seeded_suspend_is_hb_chk_004_not_timeout` (check span); `test_seeded_suspend_in_tests_phase_is_hb_chk_004_not_measured_0` (tests span); fake detector via `_sleep_detector` |
| F8 | the unbiased clock is unreadable, so a suspend goes undetected (dependency) | **detect**: `unbiased_ok: false` per span in evidence; a pilot-gate item (seam req-…V67). *assume:* it reads on every E1 host. Confirm: the pilot's `unbiased_ok` count is 0. Breaks if false: a suspend can turn a case into a measured `timeout`, and the gate item names the cell. | `test_missing_unbiased_reading_is_recorded_per_span` (fault seam) |
| F9 | the job query fails at arrival (dependency) | **prevent** (fail-closed): read as not alone, row 4 | `test_job_query_failure_at_arrival_is_not_alone` (fault seam `_job_view_at_arrival`) |
| F10 | the hidden tests are non-deterministic, so the inner run disagrees with `pass_at_1` (state) | **detect**: `hidden_tests_pass` in evidence; X-E's `hidden_test_disagreements` feeds the pilot gate and the section-3 line (R-90 c3, R-93) | `test_hidden_tests_result_and_ms_are_in_evidence` (here); the comparison is X-E's |
| F11 | a test-run survivor poisons the check copy (concurrency/state) | **prevent**: the tests' job is closed with kill-on-close before the copy; fresh copy from the archive; the hash taken last | `test_tests_phase_cannot_write_into_check_copy` |
| F12 | a deliverable edits `check/` during the run (tamper) | **detect**: row 3, including a run whose handshake is otherwise clean | `test_check_tree_changed_is_tampered[clean_exit]` (+ the mutation entry, §5.6) |
| F13 | the grading copy fails to copy (disk full, path too long) (resources) | **detect**: HB-GRD-003 through the runner, traceback in evidence | existing runner test (`test_grade_runner.py`) covers HB-GRD-003 |
| F14 | the copy is not removed, or removal walks out of the copy (resources, tamper) | **mitigate**: `finally`-removal; reparse points unlinked, never entered or `chmod`ed (§5.2); a crashed pass leaves it under its own `grading_id` | `test_grading_copy_removed_on_every_path[row1..row7]`; `test_grading_copy_with_junction_leaves_target_untouched` |
| F15 | a stdio file is huge (resources) | **mitigate**: copy at most 64 KiB per file, `truncated: true` | `test_stdio_evidence_is_capped` |
| F16 | the build hangs (time) | **accept**: bounded by the outer bound, giving HB-CHK-003 (NA), not a measured 0 (W0 §3). Residual: an agent-induced build hang reads as not recorded. | `test_outer_bound_fired_is_hb_chk_003` (build variant) |
| F17 | the honest check's exit time disagrees with the arrival stamp (time) | **prevent**: the acknowledgement handshake (the check cannot exit before the ack); spike margin +0.9..+3.0 ms after the ack. The rule's boundary is tested deterministically; the real-clock rate is measured, not asserted per push | `test_exit_time_vs_first_byte[lt,eq,gt]` (injected `exit_ft` and `first_byte_ft`: `<` and `==` give row 4, `>` passes); the false-tamper rate of 20 honest runs under load is a one-time pilot measurement with a ceiling of 0 |
| F18 | `bench_check.py` imports `harness_bench` (structure) | **prevent**: G5, the stdlib-only AST test | `test_bench_check_imports_stdlib_only` |
| F19 | the allowlist drifts between graders (structure) | **prevent**: G4 | `test_host_env_defined_once` |
| F20 | a task changes after the plan (state) | **existing**: NA `task changed`; no tagged rows (§5.1) | `test_task_changed_fallback_rows_for_property` |
| F21 | the probe host blocks the check (an endless line, or no newline) (resources) | **mitigate**: the bounded reader (§5.5); the failing outcome | `test_unbounded_probe_response_is_a_failing_outcome` |
| F22 | the probe host hangs at import (time) | **mitigate**: the ready line waits at most the case bound; the case is `timeout` | `test_probe_host_hung_at_import_is_a_case_timeout` |

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
| A1 | Credential exposure to agent code (I) | `_env.grading_env`; `spawn_deliverable` inherits only that environment plus `HB_CHECK_*` (from `env_extra` only) and declared toolchain names; `denied()` | `test_property_check_env_excludes_credentials` (ADR-0018 §9, the four names as a smoke case); `test_every_grading_child_env_is_the_allowlist[tests,build,probe_host,check]` (exact key set; all four credentials set in the grader) | mitigate |
| A2 | Result forgery through an inherited handle (T) | `close_fds=True` handle list with explicit stdio; the check's stdout is never in a child's list | `test_deliverable_cannot_write_result_pipe` (ADR-0018 §10; asserts on the result pipe, per spike E1-S2 finding 2) | mitigate |
| A3 | Result forgery through a duplicated handle (T) | write once, last and alone; first-byte job view; one line, no trailing bytes; exit after arrival; the acknowledgement | `test_forged_result_via_duplicated_handle_is_tampered` (ADR-0018 §10a), with variants `..._forge_then_exit_two_documents` and `..._forge_then_kill_check` | mitigate (residual: in-process code injection into the check, undetected, accepted by ADR-0012/0013) |
| A4 | Killing the check before its write (T) | an absent line is row 4 | `test_check_killed_before_write_is_tampered` (ADR-0018 §10a) | mitigate. The NA it produces cannot hide a failure: seam req-…V67 |
| A5 | The forger writes and exits inside the race window (T) | the honest check's later write makes two lines; row 4 | `test_forged_write_racing_deliverable_exit_yields_two_documents` (the race test; the fault seam `_job_view_at_arrival` runs the query after the forger's exit, so the "alone" view is forced; spike SP-F2 saw the forger still present 3/3, so the race is not left to chance) | mitigate |
| A6 | Tampering with campaign records during a check (T) | refuse `run_pass` under `campaign.lock`; `campaign.verify` after the pass (§5.11) | `test_run_pass_refuses_while_campaign_lock_held`; `test_campaign_verify_runs_after_a_campaign_pass` (call shapes from W1-C) | mitigate (detect, not prevent: ADR-0018 §11) |
| A7 | Spoofing: another process answers as the fake (S) | E4 only: bind `127.0.0.1:0`, `getsockname` assert, HB-CHK-005 | X-LB's (`test_listener_binds_loopback_only`) | **transfer, named**: X-LB, E4. Not reachable in E1 (no listener; `interface: loopback` is NA `not built`, `test_not_built_in_e1_items_are_na[loopback]`) |
| A8 | The deliverable alters the check or its result (T) | the hash before and after (row 3); result only on the check's own stdout; evidence outside the copy | `test_check_tree_changed_is_tampered[clean_exit]`; `test_evidence_dir_is_outside_the_copy` | mitigate (residual: a same-user process could edit and restore within the run, accepted, ADR-0013 A10) |
| A9 | Repudiation (R) | per-case outcomes, durations, seed, spans, row and handshake facts in `property.json`; the `grade.property.check` event | `test_evidence_records_every_case_seed_and_handshake` | mitigate |
| A10 | Information disclosure: planted secrets (I) | synthetic canaries only; `task_canary` egress class; stdio reaches judges and reports only through `egress.check` | `test_task_canary_is_withheld` (`tests/test_egress.py`) | mitigate |
| A11 | Denial of service (D) | per-case bounds in the check; outer bound and `TerminateJobObject`; result line capped at 64 KiB; probe lines at 1 MiB with a bounded reader; stdio capped at 64 KiB; the copy never follows a junction | `test_outer_bound_fired_is_hb_chk_003`; `test_result_over_64kib_is_hb_chk_001`; `test_unbounded_probe_response_is_a_failing_outcome`; `test_stdio_evidence_is_capped`; `test_grading_copy_with_junction_leaves_target_untouched` | mitigate. A DoS gives only NA or a failing outcome, never a raised score; NA counts reach the gate (seam req-…V67). |
| A12 | Elevation of privilege (E) | none added: the deliverable runs as the operator, as the cell did; the check's job is kill-on-close, forbids breakaway, and its handle is not inheritable | `test_check_job_is_kill_on_close_no_breakaway_not_inheritable` | accept (owner ruling, ADR-0013; upgrade: a low-rights check user, ADR-0018 §10a) |
| A13 | Network reach (spec *assume:*) (I) | **the check opens no socket in E1** (probes run in the probe host; no listener). The deliverable's and the build's reach is not confined: an accepted residual (ADR-0012/0013), declared offline per task by W1-I and W1-L | `test_e1_check_opens_no_socket` (a socket-creation audit hook in the fixture check: scoped to the check process) | mitigate for the check; accept for the deliverable and build (RV-SEC W1-F 7, RV-TA W1-F 10) |
| N1 | **RV-SEC F1:** agent module-body code in the check process forges the result (T, E) | the check never imports deliverable code; in-process means a probe-host child whose first line must be the ready line (§5.5) | committed now: `tests/test_property_forgery_fixture.py::test_module_body_forgery_is_accepted_when_imported_in_check` (positive control: row 7, the forged `blocked`, 3 trials), `::test_module_body_forgery_in_probe_host_is_refused` (row 6, `deliverable: did not start`, no `blocked`, 3 trials), `::test_probe_host_control_answers_with_the_raw_response` (row 7, `exploited`, 3 trials). X-F: `tests/test_property_grader.py::test_module_body_forgery_in_probe_host_is_refused` on the real `bench_check` with the same fixture and the same single expected result, and `::test_check_never_imports_deliverable_code` | mitigate. Spike: forged in-check, refused in the pipes shape, 9/9 trials each (§15) |
| N2 | **RV-SEC F2:** a task's `env` lists a credential name (I) | the toolchain/`HB_CHECK_*` rule and `denied()` in readiness and in the grader | `test_check_env_rejects_denied_and_undeclared_names` | mitigate |
| N3 | **RV-SEC F3:** the hidden-test phase poisons the check phase (T) | the phase order and a fresh copy, hashed last | `test_tests_phase_cannot_write_into_check_copy` | mitigate |
| N4 | **RV-SEC F5:** the check self-reports a derivable measure (T) | the grader derives; a derivable key in `measures` is row 5 | `test_derivable_measure_in_document_is_hb_chk_001` | mitigate |
| N5 | **RV-SEC F7:** the build runs outside the handle list and environment (I, T) | `build()` uses `spawn_deliverable` | `test_build_runs_through_spawn_deliverable` (the fixture build writes its environment and tries the result pipe) | mitigate |
| N6 | **RV-SEC F9a:** the operator's global `site-packages` shadow the stdlib in the check (T) | `-S`; `PYTHONPATH` is not in the allowlist | `test_check_runs_without_site_packages` | mitigate |
| N7 | a forged probe-host response (T) | treated as deliverable behaviour; a malformed one is the failing outcome | `test_malformed_probe_response_fails_the_case` | accept as measurement: the probe measures what the deliverable answers. Residual: test-detection gaming is possible for any probe, loopback included. |
| N8 | a sabotaged run turns a known failure into NA (R) (RV-SEC W1-F 2) | the grader keeps NA (it cannot know the truth); the consumers fail closed: any HB-CHK-002 count is a pilot-gate and verdict-validity item, and the report shows NA counts | X-H1's and X-E's tests (seam req-…V67) | **transfer, named**: X-H1, X-E |
| N9 | a same-user process consumes the acknowledgement (D) | the check gets EOF, exits 3, giving row 4 | `test_stolen_ack_is_tampered` | mitigate (NA only) |
| N10 | a junction in the archive makes the copy read, or removal walk, outside the copy (T, D) (RV-SEC W1-F 3) | reparse-safe copy and removal (§5.2) | `test_grading_copy_with_junction_leaves_target_untouched` | mitigate |
| N11 | probe-host code reads the check source and the cases (I) (RV-SEC W1-F 8) | none in E1 | — | accept (ADR-0013; RF-8) |

**Residual risk.** ADR-0018 §10a's in-process injection into the check by deliberate tooling stays **undetected**. It is accepted under ADR-0012 and ADR-0013. The upgrade trigger is unchanged: a low-rights check user.

## 11. Privacy analysis (LINDDUN-lite)

No personal data. Task data and canaries are synthetic (spec, Privacy row). Evidence files carry no operator identifiers, because the environment allowlist excludes `USERNAME` and the profile paths, and `skipped_reparse_points` holds paths relative to the copy only. Any path that reaches a report or judge passes `egress.check`, whose `home_path` and `username` classes withhold it.

## 12. UI design

N/A. There is no user-facing surface. The report's display of these rows is X-H2's.

## 13. Telemetry (O1-O13)

- **Structured log events.** The codebase uses `logger` with a dict payload (`runner.py`, `grade.grader_failed`). Two events carry `grading_id` and `cell_id` (the pass's trace keys). They carry the classification and the cost, and point at the evidence; every other fact is read from `property.json`, the one record (RV-SIM W1-F 7):
  - `grade.property.hidden_tests`: `{tree, hidden_tests_ms, evidence}`
  - `grade.property.check`: `{task, row, code, wall_ms, evidence}`
- **Stable error codes.** HB-CHK-001..004 (§5.6), in the event and the evidence. Score reasons use the W0 texts verbatim.
- **Measurements, by default with no flag.** Each span's `wall_ms` (the tests span is `hidden_tests_ms`, R-90 c3's double-run cost); the check's `wall_ms`; `unbiased_ok` per span. Every field is "not recorded" (`null`) when absent, never 0.
- **Operator questions and their source.** How long: `wall_ms` per span. Which path: `row`, `code`. Did it fail: `code`, and the NA counts (X-H1). How often a suspend or a clock gap: `spans.*.suspended`, `spans.*.unbiased_ok`.
- **No HTTP surface**, so no RFC 9457.
- **Load-bearing telemetry has a test:** `test_check_event_fields` asserts each event's exact key set for an accepted run and a tampered run.

## 14. Test plan (by node id; red first where marked)

**Triggered directives.**
- D0 always.
- T1, giving D1: the classification table, the predicate and the derived measures.
- T2, giving D2: the result-line validator and `at_scale`.
- T3, giving D3: new modules and allowlists.
- T4, giving D4: real copies, a real Job Object and real processes; no mocked `subprocess` or filesystem.
- **T5 (the check consumes the deliverable's WSGI/HTTP surface): N/A in E1.** The check consumes the probe host's own line protocol, covered by D6 (the line schema) and D7 (the committed fixture pair). Triggered at E4 by loopback HTTP (X-LB) (RV-TA W1-F 7).
- T6, giving D5-provider: the `bench_check` API that task checks call.
- T7, giving D6: the result schema and the probe lines.
- T8, giving D7: fixture deliverables and fixture checks stand in for agent and task code.
- T9-T14: none (no AI path), so A1-A6 do not apply.
- Mutation: `tests/mutations/property.json` (including the row-3 entry, §5.6) and `tests/mutations/bench_check.json`.

All B7 tests are Windows-only (`native` marker, ADR-0018 §8) and use the base interpreter.

**Committed in revision 2 (green now; the D7 pair for N1).** `tests/test_property_forgery_fixture.py` with `tests/fixtures/property/{forge_module,probe_host,spike_check,vulnerable_app}.py` (§15). X-F keeps `forge_module.py` unchanged and re-runs it through the real grader; `probe_host.py` and `spike_check.py` are spike stand-ins X-F replaces with `bench_check`.

**The ADR-0018 red tests and the race test (gate items).**

| Node | Proves |
| --- | --- |
| `tests/test_property_grader.py::test_property_check_env_excludes_credentials` | §9: `HB_CLAUDE_OAUTH_TOKEN`, `CLAUDE_CODE_OAUTH_TOKEN`, `GH_TOKEN` and `ANTHROPIC_API_KEY` reach neither the check nor the deliverable |
| `::test_every_grading_child_env_is_the_allowlist[tests,build,probe_host,check]` | RV-SEC W1-F 4: each child's key set ⊆ `HOST_ENV + CELL_ENV + the PYTHON* trio + declared names`, with all four credentials set in the grader |
| `::test_hb_check_values_come_from_env_extra_only` | RV-SEC W1-F 5: an `HB_CHECK_X` set in the grader's environment never reaches the deliverable; one passed in `env_extra` does |
| `::test_deliverable_cannot_write_result_pipe` | §10: the parsed result equals the honest one; nothing foreign arrived on the pipe |
| `::test_forged_result_via_duplicated_handle_is_tampered` (+ `_forge_then_exit_two_documents`, `_forge_then_kill_check`) | §10a: row 4, HB-CHK-002, never `blocked` |
| `::test_check_killed_before_write_is_tampered` | §10a: row 4 |
| `::test_forged_write_racing_deliverable_exit_yields_two_documents` | §10a race: the forced "alone" view, two lines, row 4 |
| `::test_module_body_forgery_in_probe_host_is_refused` | RV-SEC F1 on the real `bench_check`: row 6, `did not start`, no `blocked`; three trials in one node. Its positive control is committed (above). |

**One test per W0 row, plus each adjacent pair.** Every precedence test asserts `Classification.row`, not only the code.

| W0 row | Node |
| --- | --- |
| 1 | `::test_seeded_suspend_is_hb_chk_004_not_timeout` (check span); `::test_seeded_suspend_in_tests_phase_is_hb_chk_004_not_measured_0` (tests span, hidden tests that time out) |
| 2 | `::test_outer_bound_fired_is_hb_chk_003` (+ build variant) |
| 3 | `::test_check_tree_changed_is_tampered[clean_exit]` (one valid `blocked` line, alone, acked, exit 0: only row 3 holds), and its mutation entry (§5.6) |
| 4 | the §10a tests above, plus `::test_unsweepable_job_is_tampered_not_scored`, `::test_stolen_ack_is_tampered`, `::test_job_query_failure_at_arrival_is_not_alone`, `::test_check_error_exit_5_without_a_line_is_row_4`, `::test_exit_time_vs_first_byte[lt,eq]` |
| 5 | `::test_malformed_document_is_hb_chk_001_without_waiting_for_the_bound` (refused, exit 3), `::test_result_over_64kib_is_hb_chk_001`, `::test_derivable_measure_in_document_is_hb_chk_001`, `::test_measures_value_failing_at_scale_is_hb_chk_001` |
| 6 | `::test_deliverable_did_not_build_is_measured_0`, `::test_deliverable_did_not_start_is_measured_0` |
| 7 | `::test_honest_check_is_accepted`, `::test_exit_time_vs_first_byte[gt]`, `::test_reference_and_naive_fixture_truth_table` |
| pairs | `::test_precedence[r1_tests_suspend+tests_fail]` → row 1; `[r1_check_suspend+r2_bound]` → 1; `[r2_bound+r3_hash]` → 2; `[r2_bound+r4_forged_line]` → 2 (W0's "a forged line plus a hang"); `[r3_hash+r4_two_lines]` → 3; `[r3_hash+r5_malformed]` → 3 (HB-CHK-002, not 001); `[r4_not_alone+r5_malformed]` → 4; `[r4_no_line_exit5+r5]` → 4; `[r5_malformed_refused_exit3+r6]` → 5 (W0's "a malformed line refused, then exit 3"); `[r5_bad_measure+r6_did_not_build]` → 5; `[r6_did_not_build+r7_tests_pass]` → 6 |

**The truth table** `::test_reference_and_naive_fixture_truth_table` pins W0's line "reference 1, naive 0, tamper NA, did-not-build 0", plus the §5.7 rows: tamper with failed hidden tests is NA (not 0); row 7 with hidden tests NA and all `blocked` is NA; row 7 with hidden tests NA and one failing case is 0.

**The rest of the plan.**
- **D1, unit and mutation.**
  - `test_property.py::test_classify_table` (hypothesis over every combination of the row facts). The expected row comes from an **independent first-match reference** written in the test (a plain list of seven predicates), so a reordering of `_classify` fails it (RV-TA W1-F 4).
  - `::test_primary_kleene_truth_table`.
  - `::test_exploit_probes_blocked_rounding` (1/3 gives `0.3333`; 2/3 gives `0.6667`).
  - `::test_derived_measures_rebuild_from_evidence`.
- **D2, property-based.** `::test_validator_never_accepts_undeclared_or_duplicate_ids`; `::test_at_scale_refuses_loose_forms` (`"1.0"`, `1`, `1.0`, `True` refused for scale 4; `"1.0000"` accepted; a JSON int for an int metric; a shrunk counterexample becomes a permanent example).
- **D3, architecture.**
  - `test_property_grader.py::test_host_env_defined_once` (W0 G4: token 1 `\bHOST_ENV\s*=` over `src/harness_bench/grade/` with `HOST_ENV_DEFINERS = {"grade/_env.py"}`; token 2 `os.environ` over `grade/property.py` and `grade/_env.py` with `ENVIRON_READERS = {"grade/_env.py"}`).
  - `::test_bench_check_imports_stdlib_only` (W0 G5).
  - The D3 and R-60 allowlist entries: X-D (granted in W0 rev 2). Red on arrival until X-D lands them.
- **D4, real infrastructure.**
  - `::test_hanging_deliverable_with_grandchild_is_a_measured_timeout`.
  - `::test_write_result_never_writes_while_not_alone`.
  - `::test_tests_phase_cannot_write_into_check_copy`.
  - `::test_grading_copy_removed_on_every_path[row1..row7]`.
  - `::test_grading_copy_with_junction_leaves_target_untouched` (a junction in the fixture archive points at a sentinel directory outside the tree: the copy holds no sentinel file, the junction is in `skipped_reparse_points`, and after removal the sentinel's files, bytes and modes are unchanged) (RV-SEC W1-F 3).
  - `::test_stdio_evidence_is_capped`.
  - `::test_evidence_dir_is_outside_the_copy`.
  - `::test_check_runs_without_site_packages`.
  - `::test_check_job_is_kill_on_close_no_breakaway_not_inheritable`.
  - `::test_build_runs_through_spawn_deliverable`.
  - `::test_e1_check_opens_no_socket` (the check process only; A13).
  - `::test_check_never_imports_deliverable_code`.
  - `::test_regrade_reproduces_every_case_outcome` (ADR-0018 §6, EV-2).
  - `::test_missing_unbiased_reading_is_recorded_per_span`.
  - `::test_not_built_in_e1_items_are_na[loopback,fault,static,wsgi,resilience]`.
  - `tests/test_procs.py::test_spawn_console_false_is_detached_and_job_holds_only_the_child`.
  - `::test_spawn_default_flags_unchanged`.
  - `::test_exit_time_follows_now_filetime`.
- **D5-provider.** `test_bench_check.py::test_spawn_deliverable_refuses_undeclared_env`, `::test_bound_ms_is_min_of_case_and_interface`, `::test_probe_host_callable_round_trip`, `::test_malformed_probe_response_fails_the_case`, `::test_unbounded_probe_response_is_a_failing_outcome`, `::test_probe_host_hung_at_import_is_a_case_timeout`, `::test_probe_host_non_ready_first_line_is_did_not_start`. Each task's check is proven against this API by EV-7's discrimination record (X-E).
- **D6, schema and golden payload.** `::test_result_document_golden` (a synthetic, labelled fixture of `bench-check-result/1` with all three `deliverable` values) and `::test_evidence_schema_golden` (`bench-property-evidence/1`, with `hidden_tests_pass`, `spans` and `row`).
- **D7, mock fidelity.** Every fixture check imports the **real** `bench_check.py` (never a stub), and every fixture deliverable is a real process. The F1 fixture is paired with its positive control (committed, §15).
- **Runner and catalog.**
  - `tests/test_grade_runner.py::test_security_task_property_rows_are_exactly_two` (R-90 c5, red first: `property_check_pass` and `exploit_probes_blocked`; GradedOncePerPass green). **Its catalog is built inside the test**: two `security`-tagged, one `resilience`-tagged and one untagged metric, so it discriminates without the 0.7 catalog (RV-TA W1-F 9).
  - `::test_untagged_metric_applies_as_before`.
  - `::test_task_changed_fallback_rows_for_property`.
  - `tests/test_catalog_version.py` (the US-4 control) stays green: no 0.6 row moves.
  - `tests/test_grade_correctness.py` and `test_grade_mutation.py` stay green after the `HOST_ENV` move.
- **Evidence and telemetry.** `::test_hidden_tests_result_and_ms_are_in_evidence`, `::test_evidence_records_every_case_seed_and_handshake`, `::test_check_event_fields`.
- **Egress.** `tests/test_egress.py::test_task_canary_is_withheld`.
- **Campaign (call shapes from W1-C).** `::test_run_pass_refuses_while_campaign_lock_held`, `::test_campaign_verify_runs_after_a_campaign_pass`.
- **Pilot measurement, once (not per push).** 20 honest check runs under load: the false-tamper rate, with a ceiling of 0 (F17).

## 15. Spikes run

**SP-F1 and SP-F2, revision 1, 2026-10-03.** Windows 11 Pro 10.0.26200, CPython 3.14.6, the base interpreter. Grader side: `procs.Job`; the check spawned `CREATE_SUSPENDED | DETACHED_PROCESS`; a first-byte `Job.pids()`; the one-byte acknowledgement; stdin closed on every path; `GetProcessTimes`. Three trials per row.

| Trial | Observed | Verdict | Status |
| --- | --- | --- | --- |
| honest check; deliverable hangs and starts a grandchild with a plain `Popen` | 3 job members besides the check before the sweep (deliverable, grandchild, a console host, Inferred from the count); one sweep round, 10.5-10.8 ms; job view `{check}` at arrival; exit +1.1..+1.2 ms after arrival | accepted, `timeout` | Verified: in-job tree termination works |
| deliverable imported into the check (RV-SEC F1 exploit) | forged `blocked` line, alone, acknowledged, exit 0 after arrival | **accepted `blocked`: the forgery succeeds** | Verified: F1 is real |
| same module in a probe-host child, **stdout to a file** (not the shipped shape; RV-TA W1-F 5) | forged line went to the host's stdout file; the honest result arrived | accepted, honest `exploited` | superseded by revision 2 below |
| duplicated-handle forger that stays alive 1.5 s | job view of 2 at arrival; 2 lines; exit 3 | row 4 | Verified |
| duplicated-handle forger that exits at once (race) | job view of 2 at arrival in 3/3 (the race window was not hit); 2 lines | row 4 | Verified (two-line defence present; the "alone" variant is forced by a fault seam in the test) |
| malformed line | stdin closed with no acknowledgement; exit 3 in 0.9-1.2 ms | row 5, no wait for the bound | Verified |

**SP-F2, revision 2, 2026-10-03: the shipped shape, committed** (RV-SEC W1-F 1, RV-TA W1-F 5). Same host. `tests/test_property_forgery_fixture.py`, `native`, three trials per node, run three times (9 trials per node). The grader side classifies by W0 rows 2 and 4-7.

| Node | Shape | Observed | Status |
| --- | --- | --- | --- |
| `test_module_body_forgery_is_accepted_when_imported_in_check` | fixture imported into the check | row 7, the forged `blocked` accepted, 9/9 | Verified: the fixture bites |
| `test_module_body_forgery_in_probe_host_is_refused` | probe host, stdin and stdout **pipes the check owns**, ready line required | the forged line is the host's first line, not the ready line: row 6, `deliverable: did not start`, no `blocked`, 9/9 | Verified: one expected result |
| `test_probe_host_control_answers_with_the_raw_response` | same host, an unescaped-echo app | row 7, `ran`, `exploited`, 9/9 | Verified: the refusal is not vacuous |

Wall time per node: 0.16-0.43 s for three trials.

**Two small runs, 2026-10-03.**
- **Junction (G16).** A junction `ws/link → sentinel/` copied by `shutil.copytree(ws, copy, symlinks=True)`: `copy/link/secret.txt` exists and `copy/link` is not a junction (the target was copied). `shutil.rmtree(ws)` left `sentinel/secret.txt`. CPython 3.14.6 and 3.12.10.
- **Import cycle (G17).** Two stub modules shaped like `correctness.py` (imports `HOST_ENV` from `_env` at the top) and `_env.py` (imports `DOTNET_HOST_ENV` from `correctness` at the top): `ImportError: cannot import name 'DOTNET_HOST_ENV' from partially initialized module`.

**G12 (`-S`)** was run in revision 1 (§2). The earlier spikes E1-S2, E1-S3, N4 and A9 are reused, not re-run.

## 16. Seam requests and decisions

**Revision 1's three requests were granted in W0 rev 2** (W0 *Seam requests answered in revision 2*): `req-01M41C0NFEXQA0XVH4FTK9YDBD` (the ten §3 amendments), `req-01M41C0ZCPJ13PQ77KNC5AHQMZ` (X-D's two allowlist entries; X-D adds them in its first commit), `req-01M41C57K2VVC7C4JGEJC18FR1` (`cases.json`). Nothing in this design is provisional on them.

**Open, sent by revision 2:**

| Id | To | Ask | Fallback (applied here) |
| --- | --- | --- | --- |
| `req-01M41DM7XQG9GYVR32TJ762V67` | Coordinator, for X-H1 and X-E | a property cell NA under W0 rows 1-5 is never silently dropped: any HB-CHK-002 count above zero is a pilot-gate and verdict-validity item; the report shows the NA count beside every property metric; a span with `unbiased_ok: false` is a pilot-gate item (RV-SEC W1-F 2, RV-TA W1-F 8) | the grader records `row`, `code` and per-span `unbiased_ok` in evidence and the event; it assumes nothing about aggregation |
| `req-01M41DM80KBD42GYARADW4V6HZ` | Coordinator (W0 §3 `env`) | move `correctness.DOTNET_HOST_ENV` verbatim to `_env.py` (correctness imports it; mutation's own tuple unchanged), because W0's text as written is an import cycle (G17) (RV-PAT W1-F 5) | §5.9: `toolchain_env()` with the import inside the function, provisional |

- **To W1-I (via the Coordinator; already in W0 rev 2).** S1's check uses `bench_check.probe_host` with `app.kind: callable`, and `cases.yaml` names `app:`. S1 is stdlib-only (RF-2).
- **To X-E (readiness).** It reads the narrowed set through `runner.applicable(prop)`, normalises through `property.at_scale`, enforces the `env` rule and `app:`, refuses the §4 "Not built in E1" items, and owns `hidden_test_disagreements` (R-90 c3, R-93).
- **Decision requests.** None. DR-4 was ruled by R-90 (a); DR-7 by R-93. The residuals here sit inside ADR-0012, ADR-0013 and ADR-0018's accepted set.

## 17. Conformance notes

- **W0 rev 2.** Conformed: the seven-row outcome table and its order (§5.6); the 64 KiB line (§5.3); "tamper NA" (§5.7); the suspend rule per phase span (§5.2, §5.6); `hidden_tests_pass` and `at_scale` (§3, §5.7); "Not built in E1" (§4); G4's `HOST_ENV` move with `DOTNET_HOST_ENV` left in place (§5.9). One divergence is held as a seam, not taken: the `TOOLCHAIN_ENV` import (req-…V6HZ).
- **ADR-0018.** Followed. Narrowed in two places, both consistent with its §1 and §10:
  - "probes call it in process" now means a probe-host child.
  - The §10 test asserts on the result pipe, not "no write succeeded" (spike E1-S2 finding 2).
- **ADR-0018 amendment note** (W0 rev 2 §3 asks this design to carry it). Four deviations from ADR-0018's text, each decided in W0 rev 2 and specified here: (a) the check runs under `sys._base_executable -S` (no site-packages), not "the task's pinned interpreter", and is stdlib only; (b) the one-byte acknowledgement, its framing and the exit codes 0 and 3 come from spike E1-S3 and this design (§5.3); (c) the probe host's stdio are pipes owned by the check, not files (§5.5); (d) the check reads `cases.json`, the grader's normalised copy of `cases.yaml`. The ADR's owner records the amendment against these sections.
- **Local conventions conformed to.** NA as `Score(None, reason)`; evidence relative to `run_dir`; copies under `work_root`; `procs` as the only spawner on the bench side; fault seams as module functions (`procs._query` style); `simplify:` and `assume:` markers.
- **One recorded deviation.** `bench_check.py` calls `subprocess.Popen` outside `procs.py`. It runs in the check process, not in the bench, and it cannot import `procs`. W0 §10 names it: `SUBPROCESS_CALLERS = {"procs.py", "grade/bench_check.py"}`.

## 18. Flagged risks and residual unknowns

| Id | Risk | Status |
| --- | --- | --- |
| RF-1 | in-process code injection into the check (ADR-0018 §10a residual) | accepted, undetected |
| RF-2 | a deliverable whose app needs a third-party environment cannot be imported by `-S` base Python | Flagged: S1 is stdlib-only (W1-I to confirm); W1-F and W1-I settle a later task together (W0 §3) |
| RF-3 | the identity of the third job member in SP-F1 (assumed to be a console host) | Inferred from the count; it does not matter to the design, because the sweep kills any member |
| RF-4 | macOS: no runner | accepted (ADR-0018 §8); the metrics are NA `not built` |
| RF-5 | a sabotaged run turns a known failure into NA | transferred to X-H1/X-E (seam req-…V67) |
| RF-6 | the build hang reads as NA, not a measured 0 (F16) | accepted (W0 §3) |
| RF-7 | `docs/security/threat-model.md` and `privacy-review.md` do not yet `document` this design | not owned by this slice; for the Coordinator's rollup (`docs-graph.py rollup`) |
| RF-8 | probe-host code can read the check source and the cases in the same copy, and special-case them | accepted under ADR-0013 (RV-SEC W1-F 8) |
| RF-9 | **class finding:** every grading copy made with `shutil.copytree` follows a directory junction (G16): `_changes.grading_copy` (`_changes.py:118`), `correctness.py:207`, `formal.py:280`. This design's check copy is reparse-safe; the hidden-tests phase uses `correctness.grade`'s copy (R-90 c2) | for the Coordinator: one fix in one helper serves every grader. Whether an archive can carry a junction is Inferred (confirm: the D4 junction fixture through the archive path) |
| RF-10 | an honest check bug (exit 5, no line) is labelled `invalid (check tampered)` under W0's row 4 | accepted: NA either way; the exit code and the traceback are in evidence |

**Confidence ledger.**
- Contracts read from the code and from W0 rev 2: Verified.
- Process behaviour (handle list, job view, sweep, handshake, F1 in both shapes): Verified by spike; the probe-host shape is now committed.
- The precedence, the primary rule and the per-phase suspend rule: W0's, specified and testable.
- The whole-step ceiling: bound arithmetic, Inferred; measured per run in `spans`.
- Campaign hooks: call shapes from W1-C.

## 19. Status and next action

| | |
| --- | --- |
| **Completed** | Revision 2: all four W1-F reviews dispositioned (38 findings); W0 rev 2 conformance; the SP-F2 fixture, its positive control and the shipped-shape refusal committed and run; two seam requests sent |
| **Remaining** | RV-TA re-review (BLOCK on findings 1 and 2) and RV-SEC's conditions check; the two open seam requests; X-D's allowlist entries; E2 and E4 helpers and loopback (other tracks) |
| **Best next action** | RV-TA and RV-SEC re-review revision 2; then `/implement` for X-F, starting with the red-first tests of §14 |

## Review disposition

Every finding of the four W1-F reviews, in review order. "accepted" means applied in the named section.

| Lens | Id | Severity | Disposition | Section |
| --- | --- | --- | --- | --- |
| TA | 1 | blocking | accepted: `[clean_exit]` test; row-3 mutation entry; `Classification.row` asserted; `[r3_hash+r5_malformed]` and `[r3_hash+r4_two_lines]` pairs | §5.6, §9 F12, §14 |
| TA | 2 | blocking | accepted: one `SleepDetector` per phase span; a suspend in either span is row 1; tests-span test and `[r1_tests_suspend+tests_fail]` pair; both spans in evidence | §3, §5.2, §5.6, §5.7, §9 F7, §14 |
| TA | 3 | major | accepted, conformed to W0: seven rows (exit-5 row dropped), 64 KiB, tamper NA; truth table has the tamper-with-failed-tests row | §5.3, §5.6, §5.7, §14, §17 |
| TA | 4 | major | accepted: pairs keyed by W0 row numbers, one per adjacent pair; `test_classify_table` against an independent first-match reference | §14 |
| TA | 5 | major | accepted: SP-F2 re-run on the pipes shape and committed; one expected result (row 6, `did not start`); ready-line bound = the case bound | §5.5, §10 N1, §15 |
| TA | 6 | major | accepted: `test_exit_time_vs_first_byte[lt,eq,gt]` through seams; the 20-run test becomes a one-time pilot measurement | §4, §9 F17, §14 |
| TA | 7 | minor | accepted: T5 N/A in E1 with the reason; triggered at E4 | §14 |
| TA | 8 | minor | accepted: `unbiased_ok` per span; pilot-gate item by seam | §3, §5.6, §9 F8, §16 (req-…V67) |
| TA | 9 | minor | accepted: the runner test builds its own catalog | §14 |
| TA | 10 | minor | accepted: A13 scoped to the check process | §10 A13, §14 |
| SEC | 1 | major (condition) | accepted: fixture module committed; positive control; refusal three trials in one node; in-check and probe-host D7 pair | §10 N1, §14, §15 |
| SEC | 2 | major (condition) | accepted: seam request to X-H1/X-E | §10 N8, §16 (req-…V67), RF-5 |
| SEC | 3 | major (condition) | accepted: reparse-safe copy and removal; junction test; class finding RF-9 | §5.2, §9 F14, §10 N10, §14, §18 |
| SEC | 4 | minor | accepted: exact key-set test across four children | §10 A1, §14 |
| SEC | 5 | minor | accepted: `HB_CHECK_*` values from `env_extra` only; test | §5.4, §14 |
| SEC | 6 | minor | accepted: bounded probe-host reader; test | §5.5, §9 F21, §14 |
| SEC | 7 | minor | accepted: A13 reworded | §10 A13 |
| SEC | 8 | minor | accepted: RF-8 and N11 | §5.5, §10 N11, §18 |
| PAT | 1 | major | accepted, conformed to W0: rows 1-5 NA for every metric | §5.7 |
| PAT | 2 | minor | accepted, conformed to W0: no exit-5 row; exit 5 with no line is row 4 | §5.3, §5.6, RF-10 |
| PAT | 3 | minor | accepted: one constant, 64 KiB, as W0 | §5.3 |
| PAT | 4 | major | accepted (as TA 2) | §5.2, §5.6 |
| PAT | 5 | minor | seam request: W0 as written is an import cycle; designed to W0 with a deferred import meanwhile | §5.9, §16 (req-…V6HZ) |
| PAT | 6 | minor | accepted: "Out-of-process Proxy (sandboxed broker)" | §6 |
| PAT | 7 | nit | accepted: "ordered decision table" | §5.6, §6 |
| PAT | 8 | minor | accepted: `GradeContext` | §5.2 |
| PAT | 9 | nit | no change (finding confirms conformance) | §5.1 |
| PAT | 10 | nit | no change (finding confirms the seam) | §4 |
| PAT | 11 | minor | accepted: `test_spawn_default_flags_unchanged`; W1-D confirms the class | §5.8, §14 |
| SIM | 1 | major | accepted (as TA 3) | §5.6 |
| SIM | 2 | major | accepted: E1 builds probe cases and `security` only; fault, static, idempotency, `resilience` are NA `not built` | §3, §4, §5.2, §5.4 |
| SIM | 3 | minor | accepted: `wsgi` not built in E1; the key stays | §4, §5.5 |
| SIM | 4 | major | accepted: the 13 stale provisional marks removed; §16 rewritten | header, §5, §16 |
| SIM | 5 | major | accepted: `hidden_tests_pass`; `at_scale` in §5.7 and §7 with its test | §3, §5.7, §7, §14 |
| SIM | 6 | minor | accepted: no commented-out entries; later helpers in prose | §5.2 |
| SIM | 7 | minor | accepted: events carry row, code, `wall_ms` and the evidence path | §13 |
| SIM | 8 | minor | accepted: one exit-code table | §5.3 |
| SIM | 9 | minor | accepted: `denied()` imports `profiles.DROP_*`, never a copy | §5.9 |

## Gate record

Reviewers: RV-PAT (Patterns Expert), RV-SIM (Simplifier, soft veto), RV-TA (Test Architect, **hard veto**), RV-SEC (Security & Identity, **hard veto**). The author does not clear any veto.

First round (revision 1, `441da4ba`, `e41289a2`), verbatim:

`GATE design-eval-property-grader · Test Architect · BLOCK · 10 findings (rv-ta-w1f-e1e4, 2026-10-03)`

`GATE W1-F · Security & Identity · PASS WITH CONDITIONS · 8 findings (rv-sec-w1f-e1e4, 2026-10-03)`

`GATE W1-F · Patterns Expert · PASS WITH CONDITIONS · 11 findings (rv-pat-e1e4, 2026-10-03)`

`GATE W1-F · Simplifier · PASS WITH CONDITIONS · 9 findings (rv-sim-e1e4, 2026-10-03)`

Revision 2: **rev 2 pending RV-TA (and RV-SEC conditions)**.

---
**Handoff:** → `/implement` (X-F, E1) after the gate.
