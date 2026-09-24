---
id: "design-phase1-walking-skeleton"
title: "Design: phase 1 walking skeleton (engine, cells, telemetry, grading, report)"
type: design
status: draft
owner: "@timianmalloo"
phase: "Phase 1 · walking skeleton (S-05, S-06, S-07, S-08a/b/f, S-10 skeleton)"
tags: [benchmark, runner, engine, native-cells, acp, telemetry, grading, report]
links:
  - { to: arch-harness-bench, rel: implements }
  - { to: spec-harness-bench, rel: implements }
  - { to: design-run-lifecycle-model, rel: depends-on }
  - { to: adr-0013-native-cells, rel: implements }
  - { to: adr-0002-cell-driver, rel: implements }
  - { to: adr-0003-harness-profile, rel: implements }
  - { to: adr-0006-results-data-model, rel: implements }
  - { to: adr-0007-run-engine, rel: implements }
  - { to: adr-0010-untrusted-cell-output, rel: implements }
  - { to: adr-0012-proportionate-security, rel: implements }
review-by: "2027-03-22"
summary: >-
  The detailed design of the thinnest end-to-end path: prose → confirmed plan → run engine →
  native cells, each in its own git working copy and Job Object, driven over ACP (Claude, Codex) → verified
  archive → telemetry from native records → correctness and cost graded in grading working copies → pure
  projections → CLI table and a
  minimal HTML report. Version 4: cells run natively in their own working copies and Job Objects (ADR-0013);
  validity-first; the engine's launch, kill and record order matched to the checked lifecycle model.
review-suggested: []
---

# Design: phase 1 walking skeleton (v4)

- **Status:** Draft v4, revised for native cells (ADR-0013); the native revision is re-gated below. v3 passed the design gate with conditions at round 3.
- **Spec / architecture:** `docs/specs/harness-bench.md` (the phase-1 subset of US-1, US-3, US-5–US-14, US-16, US-17, US-19, US-20, US-22–US-28, US-39–US-41, US-43, US-44, US-47, US-49, US-50 as amended; US-48 applies only to Harbor tasks); `docs/architecture.md`; ADR-0001..0013; `docs/design/run-lifecycle-model.md`.
- **Threat model:** ADR-0012 and ADR-0013 (owner rulings). One trusted operator, local; each cell works in its own working copy, and nothing more; controls exist for result validity and for what the operator shares.
- **Author / date:** Claude Code (Opus 5.5) for @timianmalloo, 2026-09-23.

## Responsibility

Make one complete, observable, verifiable run possible:
1. `/start-benchmark cc-sonnet and codex-sol, pack on and off, task X1, 1 rep`;
2. a confirmed, frozen plan;
3. four native cells, each in its own git working copy, driven over ACP with the verbatim prompt;
4. each cell archived and verified, then its workspace deleted;
5. usage read from native records;
6. correctness and cost graded in grading working copies;
7. a CLI table and an HTML report whose numbers link to their evidence.

**Not phase 1:** Copilot, stop, decisions, resume, judges, summaries, statistics, comparison, the scripted user, formal graders. Each enters behind a seam below.

## Phase-1 scope and seams

| Area | Real in phase 1 | Seam contract in phase 1 | Replaced in |
| --- | --- | --- | --- |
| Harnesses | Claude Code, Codex | Copilot is not in phase-1 plans; it runs natively with no token from phase 2 (ADR-0013, spike N1.2) | 2 |
| Stop / decisions | — | Absent; a blocked cell ends `blocked (…)` with no request. The model's phase-2 actions are unused. | 2 |
| Resume | — | A crash leaves the run `incomplete`; `bench run` refuses to continue it and says to re-run under a new id | 5 |
| Judged, clarify, summary metrics | — | NOT_RECORDED `not built (phase 3)` | 3 |
| Statistics | — | `interval not computed (n < 2)`, shown as visible text | 4 |
| Price list | `bench/prices.yaml` (empty; its content hash is in the plan) | `cost_usd` NA `no price list entry`; tokens still graded | owner adds prices |

## Module map (`harness_bench`)

| Module | Responsibility | Pattern (named) |
| --- | --- | --- |
| `ledger.py` | Hash-chained JSON Lines segments: `append`, `read`, `seal`, `verify`, torn-tail rule | Append-only log as a linear hash chain (Schneier & Kelsey 1999) with sealed segment heads (RFC 9162 checkpoint idea) |
| `oslock.py` | Portable exclusive file lock (`fcntl.flock` / `msvcrt.locking`), released by the OS on process death | Mutual Exclusion |
| `plan.py` (changed) | Cells, deterministic `cell_id`, content-addressed plan, envelope, parameters, confirmation. Drops `coord-run/1` batching. | — |
| `procs.py` | Every subprocess runs in its own Windows Job Object (`ctypes`, spike N2): spawned suspended, assigned, resumed; kill-on-close, breakaway never allowed; `TerminateJobObject` + active-process count for kill → confirm; peak memory and CPU time from job accounting; deadlines and bounded output | Gateway (PoEAA) + Bulkhead (per-cell lifetime) |
| `gitsafe.py` | Host git with `-c core.fsmonitor=false -c core.hooksPath=<empty>` (ADR-0012 keeps this) | — |
| `workspace.py` | One bench-owned task clone per task version (no remote; hidden tests never in it or its history); one `git clone --local` per cell under the cells root (objects hardlinked; refs, stash and config not shared), then `git remote remove origin`; pack on/off; ancestor check | — |
| `tools.py` | Installs the pinned harness CLIs and adapters from the lockfile into a bench-owned tools folder; resolves each profile's executable by path; re-hashes the planned build at every cell start (US-12). *Why:* harness CLIs update themselves, so the build could otherwise change between cells of one run | — |
| `profiles/` + `bench/profiles/*.yaml` | Harness profile data (Claude, Codex; Copilot stub) and home seeding | Table-driven configuration (data-driven Strategy) |
| `driver.py` | ACP cell driver: bounded line reader, strict parse, deny-all permissions, verbatim prompt, ack barrier | — |
| `engine.py` | Run engine: lock, the scheduler loop (also touches the lock file as heartbeat), launch/kill/record order per the model, failure taxonomy | Producer–Consumer over a bounded buffer (workers produce, the engine thread consumes); Single Writer (the engine thread is the only `events` appender); write-ahead intent (persist before act) for `prompt_sent` |
| `errors.py` | The closed failure-cause enum; each member carries its code and attribution | — |
| `archive.py` | Archive (never follows links), `archive_files`, verify-then-delete, teardown by label | — |
| `telemetry/claude_code.py`, `telemetry/codex.py`, `telemetry/normalize.py` | Native-record readers (bounded) → `model_calls`, `tool_calls` in disjoint buckets | Anti-Corruption Layer → Canonical Data Model (OTel GenAI names) |
| `grade/runner.py`, `grade/correctness.py`, `grade/cost.py` | Grading passes under `grade.lock`, each with its own `grading_id`; correctness in a grading working copy (archive + hidden tests) in its own Job Object | — |
| `views.py` | Pure-Python projections over the verified facts; canonical sorted exports | On-demand Projection |
| `status.py` | `bench status [--json]`: typed, stdout-only | — |
| `report/cli_table.py`, `report/html.py` | CLI table; minimal HTML | — |

**Removed:**
- `runner/coord_contract.py`, `plan.batches`, `MAX_WORKERS_PER_CONTRACT`, and the `coord-run/1` wording in `cli.py`, `README.md`, `config.py` comments and `skills/start-benchmark/SKILL.md` (owner ruling: the benchmark must not run in the coordinator's runner);
- `grade/normalize_telemetry.py`, replaced by `telemetry/normalize.py` (one normaliser).

**Moved:** `grade/telemetry/` → `telemetry/`; `adapters/` → `profiles/`.

**Rejected alternatives:**

| Alternative | Why not |
| --- | --- |
| The official ACP Python SDK (`agent-client-protocol` on PyPI) | asyncio + Pydantic, against a threads-and-stdlib engine; the driver uses a small subset of ACP |
| A container per cell (ADR-0001) | Superseded by ADR-0013 (owner ruling: a working copy is the only isolation wanted) |
| DuckDB or `sqlite3` views | At ≤ 576 cells, pure functions over dataclasses do the same, without an engine |
| A JSON Schema validator dependency | D6 allows a typed equivalent enforced by tests |

## Contracts

### Exposed

- **`bench plan --matrix <m> [--confirm]`.** Prints the plan: combos, models, planned builds, pack revision, cells, envelope (⌈Σ budgets ÷ p⌉ + max budget), parameters, price-list hash. `--confirm` writes `runs/<run_id>/plan.json` (content-addressed, frozen).
- **`bench run <run_id>`.** Refuses without a confirmed plan (US-6), or an `incomplete` run (phase 1). Runs to completion, then grades.
- **`bench status <run_id> [--json]`.**
  - `--json` writes only valid `bench-status/1` JSON to stdout, under TTY, non-TTY and `NO_COLOR` alike; errors go to stderr with a code.
  - The type is dataclasses with a strict loader: unknown or missing fields rejected; enums, ids, hashes, counts, ISO times; no free text from cells.
  - Liveness: `alive` (lock held and lock-file mtime within the staleness threshold), `stalled` (lock held, mtime stale), `not running` (lock free).
- **`bench grade`, `bench report`, `bench verify`, `bench teardown <run_id>`** (teardown removes the run's working copies and home folders; it refuses while the run's lock is held).

**Exit codes:**

| Code | Meaning |
| --- | --- |
| 0 | ok |
| 1 | invalid input |
| 2 | usage (argparse only) |
| 3 | run incomplete |
| 4 | not built |
| 5 | integrity failure |

### Consumed

| Dependency | Contract relied on | Confidence |
| --- | --- | --- |
| Windows Job Objects (`kernel32` via `ctypes`) | `CreateJobObjectW`, `AssignProcessToJobObject` on a suspended process, `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`, `TerminateJobObject`, `QueryInformationJobObject` (active processes, `PeakJobMemoryUsed`) | Verified (spike N2); a node adapter's child CLI staying in the job: Inferred → probe N4 |
| `git clone --local` | A full clone with hardlinked objects and its own refs, stash and config; removed by path at teardown | Inferred (standard git) → T-WS-gitleak |
| ACP adapters (pinned lockfile) | As `docs/architecture.md` | Verified |
| Claude Code native record | `projects/<slug>/<sid>.jsonl`: `type=assistant` rows with `message.model` and `message.usage.*`; `tool_use` / `tool_result`. **The ACP session id equals `<sid>`.** | Verified (spike records) |
| Codex native record | `sessions/…/rollout-*-<sid>.jsonl`: `turn_context.model`, token usage in `info.last_token_usage.*` (input includes cached), `task_complete.error`. **The ACP session id equals `<sid>`.** | Verified (spike records) |
| Provider error signal in native records | Codex: `event_msg`/`task_complete` with `error.message` (embeds `status` and `error.type`); Claude: an assistant row with `isApiErrorMessage: true`, `apiErrorStatus`, `error`, `message.model = "<synthetic>"` and zero usage | Verified (spike R11.5; probe W3, `docs/notes/spike-phase1-probes.md`) |
| `pack-apply.py apply --install --json` | Non-interactive install of the pinned revision; JSON rows list every path written | Verified (probe W1) |

## Data model (ADR-0006, applied)

Aggregates as in the spec: the Run (frozen plan) and the Cell (at most one prompted attempt, exactly one execution outcome).

**Physical rules:**
The physical rules are ADR-0006's (one definition); in short:
- One segment per writer process and fact: the engine process, and each grading pass. In the engine process, the engine thread is the only appender to every fact, including `archive_files`, whose rows the archiver hands over through the queue.
- `hash` = sha256 of the UTF-8 canonical form (sorted keys, compact separators, integers and strings only; a non-integer measure is a decimal string at its catalog scale). One write + flush + `os.fsync` per line.
- `segment.sealed{count, head_hash}` closes a segment. `run.completed` lists the engine process's segment heads, including its own grading pass. A later `bench grade` pass is self-sealed.
- A grading segment left unsealed by a dead writer is named by the next pass, under `grade.lock`, in a `segment.abandoned{segment_id, line_count, head_hash}` line in **its own** segment; nobody writes into another writer's file. `verify` reports it as HB-LED-004 (warning, exit 0), and views skip it.
- Only a segment's own writer repairs its torn tail (`ledger.tail_repaired`). Readers ignore the torn tail of an unsealed segment.

**Facts written in phase 1** (each field has a writer and a compute reader):

| Fact | Grain / key | Fields | Writer · when | Reader |
| --- | --- | --- | --- | --- |
| `events` | one transition of one entity (`run \| cell \| attempt \| grading \| ledger`) · `(run_id, segment_id, seq)` | `recorded_at` (UTC), `mono_ns`, `entity_kind`, `entity_id`, `transition` (the lifecycle mapping), attributes: PID and process creation time, executed build + hash, credential kind, network mode (on `attempt.process_started`); ACP session id (`attempt.session_opened`); cause and evidence path (`cell.outcome`, attribution derived from cause, not stored); `archive_attempt` and `archive_hash` (`cell.archived`; the hash is a commitment that `verify` recomputes from `archive_files`, HB-LED-005 on a mismatch); `grading_id`, catalog version, grader build (grading) | engine thread · as each transition happens; grading pass · its own segment | views, status, conformance replay |
| `model_calls` | one model request by one principal · `(run_id, extraction_id, principal, native_session_id, native_ordinal)` | `cell_id`, model, uncached_input, cache_read, cache_write, output (additive), reasoning (component of output), start/end from the native record | grading pass (normaliser, `extraction_id` = normaliser build hash; `native_ordinal` = 1-based line number in the native file) · after archive, **once per extraction**: skipped when a completed pass already holds that cell's `extraction_id` | served-model and ≥ 1-call checks, cost, time split (current extraction only) |
| `turn_usage` | one model's usage in one prompt turn of one cell, as the adapter reports it · `(run_id, cell_id, attempt, model)` | uncached_input, cache_read, cache_write, output (additive), reasoning (component) | engine thread · from the ACP prompt response, at the end of the turn | token and cost views for profiles with `usage_source: acp_turn` (Claude Code); a cross-check otherwise (`docs/notes/decision-token-source-per-harness.md`) |
| `tool_calls` | one tool invocation in a cell · `(run_id, extraction_id, cell_id, native_session_id, native_ordinal)` | tool class, start/end, ok | grading pass · after archive | time split (US-24): wall, model, tool, idle |
| `archive_files` | one file or link in one archive attempt · `(run_id, cell_id, archive_attempt, path)` | kind (file/link, never followed), size, sha256, link target | archiver, appended by the engine thread · per attempt | `archive_hash` check in `verify`, teardown check, report drill-down |
| `scores` | one metric for one cell in one grading pass · `(run_id, grading_id, cell_id, metric_id)` | value or NULL + reason, evidence pointer, `archive_attempt` graded, `extraction_id` read (unit comes from the catalog, not stored) | grading pass | views |

**Rules:**
- Views read only verified, sealed segments and only **completed** grading passes; the current score rule is ADR-0006's.
- **Current extraction:** the `extraction_id` named by the cell's current scores for the catalog version being reported. Token, cost and time views read only that extraction's rows, so a normaliser fix never double-counts.
- Views **refuse** duplicates: a second `cell.outcome` for a cell, or a duplicate key in any fact, is an integrity error (HB-LED-003), never "latest wins".
- Derived, never stored: current outcome and validity (incl. `invalid (no model call | model mismatch | infrastructure)`), wall time, the US-24 time split, token totals, pass@1 over repetitions, leaderboard rows, banner counts.
- Stored per cell by the grading pass (`scores`, catalog 0.3): `pass_at_1` (this cell's hidden tests all passed: 1 or 0), `partial_credit` (decimal string, scale 4), `cost_usd` (decimal string, scale 6, or NA with a reason). A `cost_usd` score is a rebuildable cache of the current extraction × the plan's price list. A view test checks it against a fresh derivation (spec, data model).
- Canonical exports are produced in Python (sorted keys and rows) for the byte-identical re-grade test.

**Store (E7 #1):** `runs/<run_id>/{plan.json, events/, model_calls/, tool_calls/, turn_usage/, archive_files/, scores/, archive/<cell>/, grading/<grading_id>/<cell>/oracle.log, engine.log, report.html}`, `.lock`, `grade.lock`.

## Change-surface list (E7)

| # | Surface | Phase-1 change |
| --- | --- | --- |
| 1 | Store | As above |
| 2 | Model | Dataclasses per fact, plan and profile; `errors.py` cause enum |
| 3 | Service | `engine`, `driver`, `procs` (Job Objects), `workspace` (working copies), `tools`, `archive`, `telemetry`, `grade` |
| 4 | Projection / wire | `views.py`; `bench-status/1` (typed + golden JSON) |
| 5 | Client | `skills/start-benchmark/SKILL.md` reads `bench-status/1`, drops coord-runner; re-synced (A6 gate below) |
| 6 | UI | CLI table; `report.html` |
| 7 | Compute reader | Validity checks, correctness and cost graders, report |
| 8 | Docs | README (commands, exit codes); `docs/specs/README.md`; ADR-0006 amendment and `docs/notes/decision-sqlite-views.md` updated (pure projections) |
| 9 | CI | `models` job; pytest; the import lint |

## Error & concurrency model

- **Threads.**
  - **The engine thread** is the only `events` appender. It runs the scheduler loop and touches the lock file every loop iteration (≤ 5 s): this is the heartbeat, outside the ledger.
  - **One worker thread per running cell** runs its driver and hands typed results to the engine through a **bounded** `queue.Queue(maxsize=64)`.
  - **Long I/O** (archiving, working copy builds, job termination) runs in worker threads, never on the engine thread.
- **Ack barrier.** A worker that must persist a transition before acting on it (`prompt_sent`) enqueues it with a `concurrent.futures.Future` and **blocks** on it until the engine thread has appended and fsynced it (model `QueuePromptSent → PersistPromptSent → SendPrompt`). The driver never retries `session/prompt`. If the append fails, the future carries HB-RUN-001 as its exception, and the worker never sends the prompt. *Why in phase 1, when a crashed run is discarded rather than resumed:* the barrier is a few lines now, the model requires the order, and retrofitting it under phase 5's resume would change the driver's contract after its tests exist.
- **Cell process.** The driver creates the cell's job (kill-on-close, breakaway not allowed, handle not inheritable, so an engine crash always kills the tree; naming the job for resume is phase 5), spawns the adapter suspended with an explicit handle list (only its own pipes), assigns it, then resumes it. If the assignment fails, it terminates the suspended process and confirms it is gone before recording `failed (spawn)`. Cells and grading jobs run with `MSBUILDDISABLENODEREUSE=1`, `UseSharedCompilation=false` and `core.fsmonitor=false`, so no shared build server outlives a turn or joins another cell's job.
- **Kill → confirm → record.** At `end_turn` or adapter EOF, the engine always terminates the cell's job; a budget or handshake deadline does the same. It then queries the job until its active-process count is 0. Retries use capped exponential backoff (1 s doubling to 30 s) and never give up. After 5 minutes unconfirmed, the engine logs HB-RUN-002 once, with the job's remaining process ids and image names, and `bench status` shows the cell `killing (unconfirmed)`; this is a defect signal, not a termination. The parallelism slot stays held until confirmed. The outcome is recorded after that (model `EngineKill → CellDies → RecordExit`).
- **Cause classification before the outcome.** After the cell's job is empty and before `RecordExit`, the cell's worker runs the harness's bounded provider-error scan over the cell's home (`telemetry/<harness>.provider_errors`). A provider or quota error row takes precedence: a cell that timed out or lost its adapter after one is recorded `failed (provider)` (HB-CELL-108, infrastructure), not `timed_out` (agent). The scan reads only error rows; `model_calls` and `tool_calls` are still written by the grading pass.
- **Disk floor.** Every scheduler loop, the engine checks free space on the cells volume and the runs volume with `shutil.disk_usage`, which does no tree scan. Below the floor (plan parameter, default 10 GB), it stops launching (HB-RUN-004), and running cells continue. A write failure in a cell or the ledger is `failed (disk)` or HB-RUN-001.
- **Outcome evidence.** `cell.outcome` carries the adapter's exit status (NTSTATUS), the Win32 error for a spawn failure, and the host's CPU load and available memory at that moment. A bounded tail of the adapter's stderr (64 KiB) is archived.
- **Host awake.** For the whole run, the engine holds a power request (`SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)`). Suspend detection compares the wall clock with `QueryUnbiasedInterruptTime`, which excludes sleep. A gap over 60 s gives HB-CELL-106. *[Inferred → probe A9.]*
- **Failure before a prompt.** A working-copy, home, build-check or spawn failure is recorded `failed (workspace | build changed | spawn)` (`StartFails`). A cell that exits before its prompt is recorded `failed (cause)` (`CellExits → RecordExit`).
- **Crash (phase 1).** No resume: the run stays `incomplete`, and a new run id re-executes. The phase-5 resume implements `ReconcileKill/ReconcileRecord`.
  - **No launch beside an orphan (the phase-1 form of `NoLaunchBesideOrphan`)** holds by construction: every cell job is kill-on-close, so the engine's death kills every cell (spike N2.2).
  - `bench teardown <run_id>` refuses while that run's lock is held by a live engine (HB-RUN-003), so it never kills live cells.
- **Grading.** After all cells are terminal. Each pass (engine or `bench grade`) takes `grade.lock`, writes its own segment and grades only archived cells. It seals its other segments, then writes `grading.completed`, then seals its events segment, so a pass that dies at any point is not completed. The engine records its pass's summary (`grading_id`, heads) in `run.completed`. A failed pass is recorded there as `{error_code}` and never costs the run, because the run can be re-graded from the archive (US-26). The hidden tests run in a grading copy (archived working copy + the task's `tests/`), in their own job, under `grading_step_timeout` (HB-GRD-002). The copy is removed afterwards, and the oracle output is kept as evidence.
- **Deadlines** (plan parameters): git calls 120 s; spawn and job calls 30 s; handshake 60 s; cell budget from the task; grading step 15 min; lock staleness 120 s.

## Failure taxonomy (`errors.py`; one definition: cause → code, attribution)

| Cause | Code | Attribution | Detected by |
| --- | --- | --- | --- |
| `timed_out` | HB-CELL-301 | agent | budget deadline |
| `blocked (permission)` | HB-CELL-201 | agent | refused ACP permission request |
| `failed (adapter crash)` | HB-CELL-105 | harness | EOF before `end_turn` |
| `failed (protocol)` | HB-CELL-107 | harness | > 20 non-JSON lines or a line over 1 MiB (the line cap); junk archived |
| `failed (provider)` | HB-CELL-108 | infrastructure | status 408, 429, 5xx or overload in the native error row (Claude `apiErrorStatus`; Codex `task_complete.error`), found by the pre-outcome scan; takes precedence over `timed_out` and `adapter crash` |
| `failed (model unavailable)` | HB-CELL-116 | benchmark | any other 4xx model error (for example 404 `model_not_found`, 400 `invalid_request_error`): the plan pinned a model the account cannot serve (probe W3) |
| `failed (handshake timeout)` | HB-CELL-104 | infrastructure | handshake deadline |
| `failed (workspace)` | HB-CELL-113 | infrastructure | task clone, working copy or home could not be built |
| `failed (build changed)` | HB-CELL-115 | infrastructure | the planned harness build's hash differs at cell start; the cell does not start and the engine stops launching |
| `failed (memory)` | HB-CELL-103 | infrastructure | adapter exit status `STATUS_NO_MEMORY` (0xC0000017) or commit limit (0xC000012D), or an out-of-memory signature in the stderr tail; takes precedence over `adapter crash` |
| `failed (spawn)` | HB-CELL-114 | infrastructure | the adapter could not be spawned or assigned to its job |
| `failed (disk)` | HB-CELL-112 | infrastructure | a write failure (disk full) in the cell's working copy |
| `failed (host suspended)` | HB-CELL-106 | infrastructure | wall/monotonic gap > 60 s, checked at each append |
| `failed (unclassified)` | HB-CELL-199 | none | anything else; the exception class, stack hash and `exception.stacktrace` go to `engine.log`; `bench status` counts it (target 0) |

**Run-level codes:**

| Code | Meaning |
| --- | --- |
| HB-PRE-002 | An agent instruction file (`CLAUDE.md`, `.claude/CLAUDE.md`, `AGENTS.md`) in an ancestor of the cells root |
| HB-PRE-003 | Free disk below 20 GB, or below the projected need |
| HB-PRE-005 | Long paths not enabled (Windows `LongPathsEnabled`, git `core.longpaths`) |
| HB-PRE-007 | A planned harness build is missing from the tools folder, or its hash differs (US-12) |
| HB-RUN-003 | Teardown refused: the run's lock is held by a live engine |
| HB-RUN-001 | Ledger append failed: stop launching, write the code to stderr, run `incomplete` |
| HB-RUN-002 | A kill unconfirmed after 5 minutes (retries continue; the slot stays held); logs the job's remaining processes |
| HB-RUN-004 | Free space below the floor; launching stopped, running cells continue |
| HB-LED-001 | Tail repaired |
| HB-LED-002 | Chain or seal break |
| HB-LED-003 | Duplicate key or second outcome |
| HB-LED-004 | Abandoned grading segment (warning; skipped by views) |
| HB-LED-005 | `archive_hash` does not match the attempt's `archive_files` rows |
| HB-GRD-001 | Grade lock held |
| HB-GRD-002 | Grading step timeout |
| HB-VAL-001 | Validity: no model call |
| HB-VAL-002 | Validity: model mismatch |
| HB-SEC-001 | Credential value found in a report to be published |
| HB-USR-001 | Unknown run id |
| HB-TEL-001 | Native-record field missing → NOT_RECORDED |

**Recorded as report-header facts, not failures:** platform (native Windows, ADR-0013) and SDK versions; Defender real-time exclusion status of the cells root; network mode; credential kind.

## Failure-mode analysis

| Failure mode | From which choice | Disposition | Detection | Test |
| --- | --- | --- | --- | --- |
| Engine and a second thread append to one chain | Single Writer | prevent | — | T-LED-concurrent (two threads call `append`; `verify` passes because only the engine thread appends, and a direct second appender is rejected) |
| Crash after prompt sent but before `prompt_sent` is durable | Ack barrier | prevent | — | Model `send_before_persist` variant; T-ENG-ack (kill the engine between enqueue and fsync; the prompt was not sent) |
| Crash between `outcome` and kill (orphan runs forever) | Kill → confirm → record | prevent | — | Model `record_without_kill`; T-ENG-kill (kill in each state; no process remains in the cell's job) |
| Engine crash leaves a cell running | Job Object kill-on-close | prevent | — | T-ENG-crash-no-orphan (record every descendant's `(pid, created_at)`, hard-kill the engine mid-turn, assert all are gone; spike N2.2) |
| An adapter's child CLI escapes the cell's job | Job Object | prevent + detect | Breakaway never allowed | T-JOB-tree (during a turn the job's process list includes the harness CLI, and the job's limit flags are kill-on-close with no breakaway); probe N4 |
| Kill never confirmed | Windows | mitigate | HB-RUN-002 after 5 minutes; `bench status` shows the cell `killing (unconfirmed)` with its elapsed time | T-FI-unkillable (fake `TerminateJobObject` failures via `procs.py`'s test seam) |
| Disk fills during a cell or the ledger | One volume | mitigate + detect | Preflight HB-PRE-003; the disk floor each loop (HB-RUN-004); HB-CELL-112 / HB-RUN-001 on a write failure | T-FI-disk (size-limited volume under the ledger and the workspace) |
| Provider quota or 429/529 mid-cell, including a harness that retries until the budget runs out | External | detect + attribute | HB-CELL-108 (pre-outcome scan, precedence over `timed_out`) | T-TEL-provider (golden records per harness with the error row); T-ENG-provider-timeout (an error row plus a budget kill gives HB-CELL-108, attribution infrastructure) |
| Adapter writes junk or a huge line | ACP stdout | mitigate + detect | HB-CELL-107; the junk is archived | T-DRV-junk (fake agent: update banner, 10 MB line) |
| Windows path length | Nested paths | prevent | HB-PRE-005 | T-PRE-longpaths |
| Working copy or spawn fails | `workspace.py`, `procs.py` | detect | HB-CELL-113 / 114 | T-FI-workspace; T-FI-spawn (job assignment fails: the suspended pid is gone before the outcome is recorded) |
| Planned harness build missing or changed | Tools folder | prevent | HB-PRE-007 at preflight; HB-CELL-115 at each cell start | T-PRE-build; T-CELL-build (replace the binary after preflight: the next cell does not start) |
| One cell's git state (commits, stash, remote) visible to another | Per-cell clone | prevent | — | T-WS-gitleak (cell A commits, stashes and adds a remote; cell B sees none of it); T-WS-noremote at each cell start (no `origin` left by the clone) |
| A copied Claude or Codex login left behind after a cell | Per-cell home | prevent | — | T-CELL-credclean (after every cell end, including a kill and a spawn failure, no `.credentials.json` or `auth.json` remains in the cell's home) |
| A build server keeps a cell's job alive, or joins a sibling's job | Job Object; build-server settings | prevent | Job terminated at every `end_turn` | T-JOB-daemon (a turn runs `dotnet build`; after `end_turn` the job has 0 processes and no sibling build is killed) |
| A native out-of-memory kill blamed on the harness | Adapter exit status | detect + attribute | HB-CELL-103, with available memory recorded at the outcome; a memory preflight from the measured phase-1 peaks is a phase-2 upgrade | T-FI-memory (a fixture adapter exits 0xC0000017: `failed (memory)`, infrastructure) |
| Handshake hangs | Driver | detect | HB-CELL-104 | T-FI-handshake |
| Turn completes with zero model calls | Spikes 1.4, R11.5 | detect | HB-VAL-001 | T-VAL-nocall |
| Served model ≠ pin | Spike 1.4 | detect | HB-VAL-002 | T-VAL-mismatch |
| Budget exceeded | US-16 | mitigate | HB-CELL-301 | T-ENG-budget |
| Torn ledger line; tampered or truncated ledger | ADR-0006 | recover / detect | HB-LED-001 / 002 | T-LED-torn; T-LED-tamper (rewrite, mid-insert, tail cut of a sealed segment, whole-segment rewrite without the seal) |
| Duplicate facts | Re-run teardown or a buggy writer | detect | HB-LED-003 | T-VIEW-dupe (second outcome; duplicate key) |
| A re-grade duplicates `model_calls`, or two extractions are summed | Extraction keys | prevent | Write-once extractions; the current extraction is named by the current scores | T-GRD-regrade-same (same normaliser: no new rows, `verify` passes, byte-identical exports); T-GRD-regrade-new (a new normaliser: totals equal the new extraction's alone) |
| A killed `bench grade` leaves an unsealed segment | Per-pass segments | recover | HB-LED-004; named `segment.abandoned` by the next pass, in its own segment | T-GRD-abandoned (kill a pass mid-write, leaving a torn line; the next pass records `segment.abandoned` in its own segment and never touches the dead file; `verify` exits 0 with the warning; views skip it) |
| Archive rows and the committed hash disagree | Archive commitment | detect | HB-LED-005 | T-LED-archive-hash (alter one `archive_files` row) |
| A new run launches beside a crashed run's cells, or teardown removes a live run | Phase-1 crash without resume | prevent | Kill-on-close (no survivor); HB-RUN-003 | T-ENG-crash-no-orphan; T-TEARDOWN-live |
| Archive failure / sharing violation on delete | US-19 | mitigate | Workspace kept; teardown exits non-zero; bounded retry | T-ARC-full, T-ARC-locked |
| Hidden tests in the agent's own working copy | Workspace builder | prevent | — | T-WS-oracle (no oracle path or blob in the task clone's history or the working copy) |
| An agent instruction file in an ancestor of the cells root (for example a root under the user profile) | Spike R1.3 | prevent | HB-PRE-002 | T-PRE-ancestor |
| Native-record format drift; malformed, huge or deeply nested record | ADR-0008 | detect + contain | HB-TEL-001; bounded reader: line ≤ 1 MiB, file ≤ 256 MiB, and a line whose parse raises `RecursionError` is malformed | T-TEL-golden, T-TEL-missing, T-TEL-fuzz (D2, including a 100,000-deep nesting case) |
| Grading an unarchived cell / two grade processes | ADR-0007 | prevent | HB-GRD-001 | T-GRD-unarchived, T-LOCK |
| Host suspended | ADR-0007 | detect | HB-CELL-106 | T-ENG-suspend (injected clocks); probe A9 |

**Accepted** (owner, ADR-0012, ADR-0013):
- an agent's reach outside its working copy: other repositories, the operator's logins, the bench repository (including hidden tests), the host toolchain and shared package caches;
- network egress from cells;
- an agent corrupting its own native record (caught in common cases by HB-VAL-001/002);
- a phase-1 crash costs a re-run.

## Adversarial analysis (STRIDE-lite)

Scoped by ADR-0012 and ADR-0013: each cell works in its own working copy, and nothing more; controls exist only for result validity and for what the operator shares.

| Boundary | Threat | Disposition | Control | Test |
| --- | --- | --- | --- | --- |
| Agent ↔ host | E/T: damage to host files or credentials | accept (owner, ADR-0013) | — | — |
| Agent ↔ oracle | I: hidden tests in the agent's own tree | mitigate | The task clone never contains `tests/` or `oracle/`, in its tree or history | T-WS-oracle |
| Agent ↔ git remote | T: push by accident | mitigate | No remote in the task clone (`gh` stays available; owner-accepted) | T-WS-noremote |
| Cell output ↔ host git | E: run an agent-written hook | mitigate | `gitsafe.py` flags | T-B6-fsmonitor |
| Credential ↔ published report | I: a token in a shared report | mitigate | Exact-value check before `bench report --publish`. The value set is built at publish time from the host's current credential files and every credential file in the archived cell homes (tokens rotated during a cell), each also in base64 and URL-encoded forms | T-SEC-report (positive controls: a planted host token, and a rotated token present only in an archived home, are both found, and publishing refuses) |
| Everything else in the former analysis | — | accept (owner) | ADR-0012 | — |

## Privacy analysis (LINDDUN-lite)

| Data | Finding | Disposition | Control | Retention |
| --- | --- | --- | --- | --- |
| Operator email in Claude transcripts (account context) | Identifiability | mitigate | Archives local (`runs/`, gitignored); the report embeds no transcript text | Until the owner deletes `runs/<id>` |
| Username and home paths | Identifiability | mitigate | Cells root outside the profile; the report shows archive-relative paths | As above |

## UI & interaction design (CLI table, status, HTML skeleton)

- **Medium:**
  - CLI: Rich; `NO_COLOR` and non-TTY give ASCII.
  - HTML: a static file, pre-rendered, no JavaScript, light mode only (`color-scheme: light`).
- **Recorded deviation (accepted by UX & Accessibility, round 1):** `DESIGN.md` is produced in S-10. The skeleton declares one `:root` token block from the mockup seed, used everywhere:
  - `--bg`, `--panel`, `--ink`, `--ink-2`, `--rule`;
  - `--focus` (≥ 3:1 on `--bg` and `--panel`);
  - `--ink-3` never used for text.
- **Build to the S-10 shape now:**
  - stable section ids (`header`, `validity`, `leaderboard`, `runs`);
  - numbers use tabular figures, right-aligned, with units;
  - rank ties shown `2=`.

**States:**

| Component | Default | Empty | Error / partial | NA / not computed |
| --- | --- | --- | --- | --- |
| Header | fields incl. credential kind, network mode, Defender status | — | missing field `not recorded` | `NA (reason)` |
| Validity banner | counts + list | `All <n> cells completed and are valid.` | each class counted; run `incomplete`: states the run state and the count of never-started cells | — |
| Leaderboard | rows (combo, pack, pass@1, tokens, wall) | `No cell completed in this run. Run bench status <run-id> to see why.` | invalid combos listed below | pass@1 shows `interval not computed (n < 2)` as visible text; `NA` + reason text |
| Runs table | rows with evidence pointers | `No cells in this run.` | cause per row | — |
| Evidence pointer | path | — | archive absent → `This copy doesn't include the run archive. Evidence path: <pointer>.` | — |

**CLI states** (`bench report` table, `bench status`):

| Surface | State | Exact text (stdout unless noted) |
| --- | --- | --- |
| CLI table | empty | `No cell completed in run <run-id>. Run bench status <run-id> to see why.` |
| CLI table | not graded | `Run <run-id> is not graded yet. Run bench grade <run-id>.` (exit 4) |
| `bench status` | alive | `Run <run-id>: running. <done>/<total> cells ended, <n> running.` |
| `bench status` | stalled | `Run <run-id>: stalled. The engine holds the lock but has not progressed for <s> s.` |
| `bench status` | not running | `Run <run-id>: not running (<complete \| incomplete>). <done>/<total> cells ended.` |
| `bench status` | killing | per cell: `<cell-id>: killing (unconfirmed, <s> s)` |
| any | unknown run id | stderr: `HB-USR-001: no run <run-id> under runs/. Run bench plan to create one.` (exit 1) |

**Accessibility:**
- semantic tables (`<caption>`, `<th scope>`);
- each scroll container is `role="region"`, `tabindex="0"`, `aria-labelledby` its caption;
- `:focus-visible` outline in `--focus`;
- no colour-only meaning;
- `lang`, `<title>`;
- reflow at 320 px;
- no network request.

## Telemetry

- **Trace.** A W3C trace id (32 hex) is minted per run and recorded in the plan. `TRACEPARENT` is passed into cell and grading processes. Phase spans are **derived** from transition timestamps (the ledger is the only timing source). A span id is a pure function, so a log line written before its span is derived still joins it: `span_id` = the first 16 hex of sha256(`trace_id` | `entity_id` | phase).
- **Logs.** JSON via stdlib `logging` to `runs/<run_id>/engine.log`, fields `ts, severity_number, severity_text, trace_id, span_id, event, error_code`, plus `exception.stacktrace` for HB-CELL-199. No cell text; credentials never logged; `procs.py` never logs argv values.
- **Error codes** come from `errors.py` (one definition).
- **Metrics.** Derived at status time: cells by outcome and cause, `failed (unclassified)`. Per cell at the end: archive bytes, and peak memory and CPU time from the cell's job accounting (`not recorded` if the query fails). Enum labels only. Phase-span p50/p95 are deferred to phase 2 (n = 4 is meaningless).
- **O12.** Every fault-injection test asserts that its code is written to `engine.log` with a `span_id`; T-STATUS-json covers the status output.

## Test plan (Testing Strategy)

| Trigger | Directive | Tests |
| --- | --- | --- |
| always | **D0** | ruff; no dead code; a grep test that every `coord-run/1` path is gone, covering the synced skill copies (`.claude/skills/`, `.agents/skills/`) as well as `skills/` |
| T1 | **D1** unit + mutation | `cell_id`, envelope, cause→code/attribution, validity, current-score rule, cost NA paths, time split, leaderboard, ties. **Mutation:** mutmut, run in WSL if native Windows fails (probe R13). Mutation confidence must be measured before `/implement` closes, not carried as Inferred. **Bar:** every surviving mutant in `ledger`, `engine`, `errors`, `views` and the graders is killed by a new test or justified in writing (equivalent mutant) in the implementation's mutation record. |
| T2 | **D2** property (`hypothesis`, dev dependency) | Ledger: append/verify round trip; any byte change, cut or insert detected; torn tail at any offset. ACP line reader: any bytes and lengths never crash it and stay bounded. Native-record readers: fuzzed records → NOT_RECORDED, never a crash. `bench-status/1` round trip. |
| T3 | **D3** | Import lint: engine, driver and archive never import `grade`/`report`; only `procs.py` calls `subprocess`; only `gitsafe.py` runs git; only `driver.py` speaks ACP. **Conformance (US-44 AC3):** (a) an enumeration test, in both directions, fails if any `transition` value the engine can write is absent from the phase-1 mapping table or maps to more than one model action, and if any phase-1 row of the table is never written by the engine; (b) every event sequence produced by the T-ENG and T-FI tests replays against a Python transcription of the model's phase-1 guards; (c) **one seeded out-of-order ledger per phase-1 guard** in the mapping table (e.g. `prompt_sent` before `process_started`, an outcome before the cell's job is empty, `archived` before the outcome, `workspace_deleted` before `archived`, a score for an unarchived cell) is rejected by the replay. |
| T4 | **D4** real infra | Real filesystem and git working copies (temp dirs); real processes and Job Objects (marked `native`, run on the workstation) for kill paths, T-ENG-crash-no-orphan, T-JOB-tree, T-FI-*. No mocked `os` or `subprocess` except `procs.py`'s fault seam. |
| T5 | **D5-consumer** analogue | Recorded ACP transcripts per adapter version, scrubbed of email and paths, labelled, replayed through the driver |
| T6 / T10 | **D5-provider / D6 / A2** | `bench status --json`: stdout carries only valid `bench-status/1` under TTY, non-TTY and `NO_COLOR`; errors on stderr with a code; golden outputs; the skill's expectations checked against them |
| T7 | **D6** | Golden native records (Claude, Codex; incl. the provider-error rows); golden **ledger** fixtures for every row type (`events` transitions, `model_calls`, `tool_calls`, `archive_files`, `scores`), versioned and required to keep passing; Postel tests |
| T8 | **D7** | The fake ACP agent's emitted message types are listed. Each type is paired with a recorded real transcript or the ACP schema; a type with neither fails the fidelity test. Types without a real exemplar yet (permission request, hang, EOF) are paired with the ACP schema and flagged for a recording in the phase-2 permission probe. |
| T14 | **A6** | The `skills/start-benchmark/SKILL.md` edit is gated by golden cases (prose → compiled matrix; reading a `bench-status/1` document) run on the old and the new skill, with per-case deltas recorded. `test_skills_in_sync` does not satisfy this row. |
| T9, T11–T13 | A1, A3–A5 | Not triggered in phase 1: no model gateway or structured LLM output; the cell prompt is task data passed verbatim |
| UI | UIA subset | T-UI-axe (zero violations; `lang`, `<title>`, `<caption>`); T-UI-reflow (320 px); T-UI-states (one fixture per state-table cell, exact string); T-UI-NA (no NOT_RECORDED renders as 0/0%/$0); T-UI-tokens (no colour/size/radius literal outside `:root`); T-UI-contrast (text ≥ 4.5:1, focus ≥ 3:1, light mode); T-UI-keyboard (scroll regions focusable); T-CLI-plain (`NO_COLOR` and redirected stdout give ASCII with textual NA and invalid marks); T-CLI-exit (each exit code); T-CLI-states (one fixture per CLI state row, exact string); T-UI-numerics (numeric cells use tabular figures, are right-aligned, and carry their unit) |
| Canary controls | positive + negative | US-13: the user-config canary absent with isolation on, present in a control cell with isolation off (E2E). T-SEC-report plants a token and expects it found. T-LOG-nosecret plants the credential in a fake agent's output and expects it absent from `engine.log` and status, and present in the archive (where it is allowed). |

**E2E (phase-1 exit):** `tests/e2e/test_walking_skeleton.py` (marked `native`, `credentials`, run on the workstation). It runs X1 × {cc-sonnet, codex-sol} × {on, off} × 1 and asserts:
- 4 cells terminal;
- the verbatim prompt hash (US-10);
- served model with ≥ 1 call (US-11);
- executed build = planned (US-12);
- the US-13 canary: absent, and present in the control;
- zero permission requests (US-14);
- `bench verify` passes;
- archives verify (US-19);
- the re-grade gives byte-identical canonical exports;
- CLI and `report.html` render offline;
- no process remains in any cell job, and teardown removes the run's working copies.

**Model:** `tools/check_models.py --quick` in CI. The hash-mismatch path of the jar fetch is tested automatically (`tests/test_check_models.py`: a corrupted jar is deleted and the script exits non-zero).

## Conformance notes

- **ADR-0011:** C4 via `bench-status/1`; C5, C9 via the import lint; C6 via intents and the ack barrier; C10 via `bench verify`; C11 via the credential kind on `attempt.process_started`. C3 not applicable (no gateway).
- **Deviations:**
  - no `DESIGN.md` in phase 1 (accepted);
  - the HTML skeleton is light mode only, against spec UIA-2/UIA-12, which test both modes. Dark mode and its contrast test arrive with S-10;
  - forced-colors (Windows High Contrast) is not checked in phase 1 (residual, S-10);
  - security scope per ADR-0012 (owner ruling).

## Flagged risks & residual unknowns

| # | Unknown | Probe |
| --- | --- | --- |
| W1 | `pack-apply.py --install` into an arbitrary task directory | **Done 2026-09-23 (Verified):** `docs/notes/spike-phase1-probes.md` |
| W3 | Claude's provider-error row shape in the native record | **Done 2026-09-23 (Verified):** `docs/notes/spike-phase1-probes.md` |
| A3 | OAuth refresh rotation invalidating the host login | Watch the credential file across a long cell |
| A9 | Monotonic clock across Windows sleep | Sleep the host mid-cell |
| R13 | mutmut on Windows | Run on a small module; else WSL |
| N5 | Codex 0.156 lists `C:/Users/<operator>/.agents/skills` as a skill root inside a cell despite its own `CODEX_HOME` (seen in the golden record, 2026-09-23), so user-level skills may reach Codex cells (US-13) | The E2E US-13 canary per configuration class, for Codex; if it shows, pin the skill roots (a per-cell `HOME`/`USERPROFILE`, or Codex's skills setting) |
| N4 | A node adapter's child CLI stays in the cell's Job Object | **Done 2026-09-23 (Verified):** `docs/notes/spike-phase1-probes.md` |

## Status & next action

| | |
| --- | --- |
| **Completed** | Lifecycle model (TLC at the US-44 bounds; 21 seeded variants each rejected by its own target); phase-1 walking-skeleton design, passed at gate round 3 with conditions |
| **Remaining** | Phase 2 designs (Copilot profile, stop/decisions, T0 matcher, Harbor E1), then phases 3–5 |
| **Best next action** | `/implement` phase 1 (probes W1, W3 and N4 done): ledger and engine first (red-first against the model's phase-1 guards), then driver, profiles, archive, telemetry, grading, views, report, E2E |

## Gate record

**Round 1 (2026-09-23).** Blocked: Test Architect, Security, Distributed Systems, Data & Persistence, SRE (advisory), UX & Accessibility. Soft-blocked: Simplifier. Passed with conditions: Patterns Expert. Resolutions:

| Lens | Items and how they were resolved |
| --- | --- |
| Distributed Systems | Heartbeat moved to lock-file mtime (no second appender); ack barrier; kill → confirm → record; grade lock with 2 passes and the `no_lock` variant; kill retried until confirmed, slot held; bounded queue; long I/O off the engine thread |
| Test Architect | A6 and A2 rows; model v2 covers the phase-1 failure paths; trace-replay conformance with a seeded out-of-order ledger; state-based `StoppedNeverRelaunched`; variants for `StopReachesTerminal` and `EndedCellsGetArchived`; property-targeted liveness variants; reachability witness; positive controls; D7 per message type; D6 ledger goldens; mutation measured before close |
| Data & Persistence | No heartbeat rows; ADR-0006 amendment; `tool_calls` read by the US-24 view; `extraction_id` in the telemetry keys, written by the grading pass; `ledger` entity kind; `archive_attempt` in the key; attribution and unit derived, not stored; duplicate refusal; canonical exports in Python; E7 additions |
| SRE | Disk-full during a cell and the ledger; `failed (provider)`; `failed (protocol)` with a line cap; WSL2 memory and exit-137 cause; clock-offset handling; long paths; Defender status; pre-pull by digest; W3C trace id; stacktrace; O12 assertions; peak-memory source; grading deadline and code |
| UX & Accessibility | UI tests; scroll regions and `--focus`; the three state rows; light-only mode; S-10 shape |
| Patterns Expert | Sealed segment heads; canonical JSON; ACP SDK recorded as rejected; portable lock; process-tree kill; patterns renamed; leftovers removed |
| Simplifier | Heartbeat thread dropped; spans derived; SBOM deferred (ADR-0012); JSON Schema file replaced by a typed equivalent; teardown merged; one error definition; projections in pure Python (no SQL engine); p50/p95 deferred; provenance dropped. **Kept:** peak memory and archive bytes, which the architecture's phase-1 row requires. |
| Security | By owner ruling ADR-0012, provenance, the allowlist, hostile fixtures, the full scan scope and bench-minted-id enforcement are closed as not required. **Kept as validity:** T-IMG-oracle (build context), bounded native-record parsers, the container-configuration test, the report credential check, the automated hash-mismatch test. |

**Round 2 (2026-09-23).** Blocked: Test Architect, Data & Persistence. Passed with conditions: Distributed Systems (veto cleared), Security (veto cleared), UX & Accessibility (veto cleared for the design), SRE, Simplifier, Patterns Expert. Resolutions:

| Lens | Items and how they were resolved |
| --- | --- |
| Test Architect | Every safety invariant now runs against the real design in CI (`safety-small` in every mode; the US-44 bounds per the lifecycle design). The full-bounds placeholder is replaced by measured results. `ArchivedCellsGetGraded` (with `GradedOncePerPass`: graded exactly once) and the `grade_skipped` variant. Conformance: an enumeration test for unmapped transitions, and one seeded out-of-order ledger per phase-1 guard. The mutation bar is stated. `test_every_checked_property_has_a_seeded_variant` (the reverse check; observed red when a variant is removed). |
| Data & Persistence | Write-once extractions and the current-extraction rule; `extraction_id` and `archive_attempt` on `scores`; `archive_hash` only on `cell.archived`, recomputed by `verify` (HB-LED-005). `archive_files` is appended by the engine thread. Abandoned grading segments are sealed by the next pass (HB-LED-004). ADR-0006 was amended in place (hash rule, UTF-8, decimal strings, seals, keys, `ledger` entity kind, `attempt.container_created`), so it carries one definition with this design. |
| Distributed Systems | `NoOutcomeWhileRunning` and the `record_while_running` variant (the phase-1 kill order). `PromptedCellsEnd` with fairness on `EngineKill`, and the `no_budget_kill` variant. HB-PRE-006 (no launch beside an orphan) and HB-RUN-003 (no teardown of a live run). The ack future carries HB-RUN-001. Only the owning writer repairs a torn tail. ADR-0007 was amended (lock-file heartbeat; the kill → record → archive order). |
| Security | T-SEC-report's value set includes rotated tokens from archived homes, with encoded forms and a rotated-token positive control. T-HARD-config asserts the home mount's source. Native-record reader limits, with a deep-nesting fuzz case. T-IMG-oracle compares content hashes. |
| SRE | Pre-outcome provider-error scan, with HB-CELL-108 taking precedence over `timed_out` (T-ENG-provider-timeout). Deterministic `span_id`. Workspace cap measured every 30 s. HB-RUN-002 for an unconfirmed kill. |
| UX & Accessibility | CLI state rows with exact strings (T-CLI-states), T-UI-numerics, and light-only mode and forced-colors recorded as deviations. |
| Simplifier | The ack-barrier rationale is written. Config substitutions fail on drift. `models/README.md` is current. Removing `COORD` and `CoordinatorNeverACell` was first declined because US-44 named the invariant. It was **adopted** after the owner amended US-44 (2026-09-23). |
| Patterns Expert | Producer–Consumer plus Single Writer, and write-ahead intent named. A `Future` for the ack. Windows tree kill with `taskkill /T /F`. Capped backoff with an escalation code. Schneier & Kelsey cited. The D0 grep covers the synced skill copies. |

**Round 3 (2026-09-23).** Re-check by the two lenses that blocked in round 2.
- **Data & Persistence:** passed with conditions; veto cleared. The one new Major is resolved: a pass never writes into another writer's file, and an abandoned segment is named by `segment.abandoned` in the next pass's own segment. Two Minors are resolved: no boolean in the canonical form, and the current extraction is defined per catalog version.
- **Test Architect:** passed with conditions; veto cleared. One Minor is resolved: the `--deep` comment wrongly said "nightly".
- **Found at this gate:** a new invariant had pre-empted two older variants. The variant runs caught it; it is recorded as defect class MOD-A and controlled by checking each target alone.
- **Not taken (Simplifier, Minor):** the grading configuration at 1 cell. At 2 cells it runs in a measured 63 s, within budget.

**Conditions carried to `/implement`** (not discretionary):
- T3 conformance tests written red-first;
- the mutation record meeting the T1 bar;
- probes W1 and W3 before the driver and telemetry code;
- a Proof Pack at merge.

`GATE design · PASS WITH CONDITIONS · round 3 · 2026-09-23 · vetoes cleared by Test Architect, Data & Persistence, Distributed Systems, Security, UX & Accessibility (none by the author)`

**Native revision (ADR-0013), 2026-09-23.** The owner ruled that containers go and each cell works in its own working copy, and nothing more.
- **Convened:** Distributed Systems, Test Architect, SRE and Simplifier.
- **Not convened:** Security. The owner's rulings made the isolation decisions, and the two remaining security controls (safe host git and the published-report credential check) are unchanged.
- **Round 1:** Test Architect blocked and Simplifier soft-blocked. Distributed Systems (veto cleared) and SRE passed with conditions.
- **Round 2:** Test Architect and Simplifier passed with conditions, and both cleared their vetoes.

| Lens | Items and how they were resolved |
| --- | --- |
| Test Architect | Blocker: worktrees of one clone share refs, stash and config (verified in a scratch repo). Now one `git clone --local` per cell, with `origin` removed; T-WS-gitleak; T-WS-noremote at each cell start. US-12 re-checked at every cell start (HB-CELL-115, T-CELL-build). `StartFails` terminates the suspended process first (T-FI-spawn). `cell.image_ready` removed; enumeration in both directions. T-JOB-tree asserts the limit flags. T-ENG-crash-no-orphan records every descendant. US-48 criteria Harbor-only. T-CELL-credclean added. |
| Distributed Systems | Per-cell clone (the same finding). The job handle is not inheritable; the job is terminated at every `end_turn`; build servers are off (`MSBUILDDISABLENODEREUSE`, `UseSharedCompilation=false`, `core.fsmonitor=false`). Spawned suspended with an explicit handle list. Resume by job name is recorded for phase 5 (ADR-0007 amendment). |
| SRE | `failed (memory)` (HB-CELL-103) from the exit status or the stderr signature. Exit status, Win32 error, host CPU and available memory on `cell.outcome`; a stderr tail archived. Power request for the run; suspend detection with `QueryUnbiasedInterruptTime` (probe A9). HB-RUN-002 logs the remaining processes. Disk: a volume floor (HB-RUN-004) instead of a per-cell cap. **Not taken:** per-cell TEMP (isolation-shaped; the volume floor covers the disk); a job memory limit. |
| Simplifier | Size cap deleted; HB-PRE-002 narrowed to ancestor instruction files; the tools-folder reason written; the STRIDE control column cleared. Round 2: job naming deferred to phase 5 (no resume in phase 1); HB-PRE-004's guessed 4 GB estimate deleted (a measured-peak preflight is a phase-2 upgrade). |

**Conditions carried to `/implement`:**
- every test observed red before green;
- probe N4 (the child CLI stays in the job; handle not inherited);
- probe A9;
- a Proof Pack at merge.

**Residual risks:**
- a process launched through a broker (WMI, COM) escapes the job;
- the end-of-turn kill must be revisited for multi-turn cells (the phase-3 scripted user).

`GATE design · native revision · PASS WITH CONDITIONS · round 2 · 2026-09-23 · vetoes cleared by Test Architect, Distributed Systems, Simplifier (none by the author); SRE advisory`

---
**Handoff:** → `/implement`.
