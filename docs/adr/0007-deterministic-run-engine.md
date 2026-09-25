---
id: "adr-0007-run-engine"
title: "ADR-0007: A deterministic run engine schedules cells; the LLM coordinator never does"
type: adr
status: draft
owner: "@timianmalloo"
phase: "all phases"
tags: [benchmark, runner, idempotency, concurrency, failure-modes]
links:
  - { to: arch-harness-bench, rel: refines }
  - { to: spec-harness-bench, rel: implements }
review-by: "2027-09-23"
summary: >-
  `bench run` is one deterministic process per run: single writer of the lifecycle log, write-ahead
  launch intents, named containers it can always find and kill, monotonic budgets with host-suspend
  detection, apply-once control files, a closed failure taxonomy that separates infrastructure from
  harness faults, and a circuit breaker. The Claude Code session compiles, confirms and relays; it reads
  only schema-bound status.
---

# ADR-0007: A deterministic run engine schedules cells; the LLM coordinator never does

- **Status:** Proposed
- **Amended by ADR-0013 (2026-09-23):** the cell's handle is its Job Object, not a named container.
  - The launch record is `attempt.process_started`, carrying the PID and process creation time.
  - Kill is `TerminateJobObject`, confirmed when the active-process count reaches 0.
  - Kill-on-close means an engine crash leaves no running cell. Phase 5 names the job `hb-<run>-<cell>-<attempt>` in `cell.launch_intent`, before the spawn; resume opens each recorded job by name, terminates it and waits for 0 active processes; not found means the tree is gone.
  - Failure causes: the Docker, image, container-create and exit-137 causes apply only to Harbor cells. Authored cells need no new causes.
  - Every other decision here is unchanged.
- **Date:** 2026-09-23 (revised after council round 1)
- **Deciders:** @timianmalloo; authored by Claude Code for the architect council
- **Context spec/architecture:** `docs/specs/harness-bench.md` US-6, US-15–US-20, US-44–US-46

## Context

The spec needs:
- at most one prompted attempt per cell, and idempotent resume;
- a decision timeout and a 30-second stop;
- parallelism limits;
- a coordinator that is never a cell and that receives only schema-bound cell output (US-46).

LOA P2 and P3 put scheduling in deterministic code. Council round 1 found missing rules:
- orphan containers, and a crash-safe ledger;
- atomic, apply-once control inputs;
- a race between an answer and a timeout, and concurrent grading;
- clocks across host sleep;
- deadlines on infrastructure calls;
- failure attribution.

## Decision

**1. One engine process per run.**
- `bench run <run_id>` holds an OS file lock on `runs/<run_id>/.lock` (`LockFileEx` / `msvcrt`, released by the OS when the process dies). Liveness is tested by trying the lock, never by PID.
- The engine is the only writer of the lifecycle log (ADR-0006).
- It touches the lock file on every scheduler loop (≤ 5 s); the file's mtime is the heartbeat, so `bench status` can report "alive and progressing" without a second appender or heartbeat rows in the ledger (amended at the phase-1 design gate).
- Its states are exactly those of `models/run_lifecycle.tla`, which is TLC-checked before the engine is built (US-44).

**2. At-most-once launch (write-ahead intent log; Idempotent Action).** Per cell, in order:

| Event | When |
| --- | --- |
| `cell.launch_intent` | fsynced before anything else |
| container created | named `hb-<run>-<cell>` (ADR-0001) |
| `cell.prompt_sent` | before the first `session/prompt` |
| outcome | when the cell ends |
| `cell.archived{manifest_hash}` | after the archive is verified |

**On resume:**
- **Intent, no container, no `prompt_sent`:** the cell was never prompted, and it may launch once.
- **Intent, container present, no `prompt_sent`:** the container is killed and removed by name, confirmed absent by `inspect`, and the cell may launch once.
- **`prompt_sent` without an outcome:** the cell is killed by name, confirmed absent by `inspect`, recorded `failed (coordinator crash)`, then archived (kill → confirm → record → archive, as the model's `ReconcileKill → ReconcileRecord → Archive`). It is never relaunched.
- **Archiving** waits until `docker inspect` shows the container absent or exited.

**3. Control inputs (Single Writer + command mailbox).**
- `bench stop` and decision answers write control files: temp file, then `os.replace`. Each carries a UUID, and answers carry the `decision_id` they answer.
- The engine records `control.applied{uuid}` before it deletes the file, and skips UUIDs already applied.
- **First resolution wins:** an answer that arrives after a timeout default is recorded `rejected (already resolved)`, and vice versa.

**4. Clocks.**
- Budgets and decision deadlines use `time.monotonic()`.
- A gap between wall-clock and monotonic elapsed time above 60 s means the host was suspended. Running cells then end `failed (host suspended)`, attributed to infrastructure. [Flagged: whether Python's monotonic clock on Windows advances during sleep is spiked in phase 1; the gap check works either way.]
- On resume, open decision deadlines restart from the resume time.
- Phase 2 (the first overnight run) adds a power request (`SetThreadExecutionState`) to keep the host awake.

**5. Deadlines and kills.** Deadline values and the heartbeat staleness threshold (after which `bench status` says `stalled`) are plan parameters, shown at confirmation and recorded in the plan. Initial values: Docker calls 120 s (build 20 min), handshake 60 s, stale heartbeat 120 s.
- Every subprocess has a deadline: `docker build`, `pull`, `run`, `inspect`, `kill`, `rm`, and git.
- The ACP handshake has its own deadline (ADR-0002).
- Stop means kill by container name, confirmed by `inspect`, within 30 s (US-45).

**6. Failure taxonomy (closed enum).** Every non-`completed` outcome carries a cause from a closed list. Each cause has an attribution: agent, harness, infrastructure or benchmark. An infrastructure or benchmark cause sets the cell's validity to `invalid (infrastructure)`, so it is never scored against a harness.

| Cause | Attribution |
| --- | --- |
| `timed_out` | agent |
| `blocked (permission)`, `blocked (disk cap)` | agent |
| `failed (adapter crash)`, `failed (protocol error)`, `blocked (auth)` | harness |
| `failed (vendor 429/5xx)` | infrastructure; the harness's own retry count is kept as evidence, since retry behaviour differs by harness |
| `failed (docker unavailable)`, `failed (image)`, `failed (container create)`, `failed (OOM)`, `failed (disk full)`, `failed (handshake timeout)`, `failed (host suspended)`, `blocked (network)` | infrastructure |
| `failed (coordinator crash)` | benchmark |
| `failed (unclassified)` | none; target count 0, shown in `bench status` |

Each failure carries a fixed evidence set:
- the container exit code and the `OOMKilled` flag;
- the last 20 typed driver events;
- the stderr tail, which goes to the archive only.

**7. Circuit breaker.** After 3 consecutive infrastructure failures, the engine stops launching and raises a decision request (resume launches / stop the run; default: stop). One Docker outage then costs a few cells, not the run.

**Wave-2 amendment (R-49, 2026-09-25).** The implemented breaker is a one-shot fuse: after three consecutive invalidating outcomes other than `model_unavailable`, it stops launching, leaves running cells to finish, and opens no decision. Unlaunched cells stay `not started`; the run records `run.launch_stopped` and ends with exit 3. The decision half above is deferred. If a future `circuit_breaker` decision offers `resume` / `stop`, its timeout default is **launches stay stopped**. A timeout never kills running cells.

**8. Grading concurrency.** Every grading pass, whether from `bench grade` or from the engine (after a run or a stop, US-45), takes `runs/<run_id>/grade.lock`. It grades only cells that have `cell.archived{manifest_hash}`, and each score records that hash (ADR-0006).

**9. Instrumentation.** Every phase of every cell is a span on its `events` rows: `run_id` (the trace), `cell_id`, `phase`, `span_id`, UTC start and end, monotonic start and end, `duration_ms`, `outcome`, `error_code`. The phases are workspace build, image build, container start, handshake, prompt turn, archive, hash, teardown, reader and grader.

Per cell the engine also samples:
- peak memory, and CPU throttling (cgroup `nr_throttled`);
- archive bytes.

Preflight checks, before the first cell:
- the projected disk need (measured archive size × planned cells × 1.5, plus images) fits;
- the Docker Desktop and WSL2 limits fit parallelism × per-cell limits;
- Docker auto-update and Windows restart hours are noted.

`bench plan` prints the worst-case and expected wall-clock time.

**10. The LLM coordinator (the `/start-benchmark` session).**
- Compiles prose to a matrix and runs `bench plan`, then presents the plan (US-6).
- Starts `bench run` in the background.
- Reads `bench status --json`. That status has a schema: enums, bench-assigned ids matching a fixed grammar, hashes and counts, **no free strings**; task display names map to bench ids.
- Relays decision requests (no cell text) and writes P1's answers as control files.
- Writes the pack audit-log entries.

The AI summaries are generated by `bench report` through the model gateway (ADR-0009), not by the session. A permission deny rule for `runs/**` and `bench-cells/**` goes into the coordinator's settings. **Residual (accepted in writing):** that rule does not stop a shell command in the session from reading those paths.

## Alternatives considered

- **The LLM session schedules cells itself (the proposal):** rejected. A model on the scheduling path is nondeterministic, cannot be model-checked, reads cell free text and bills scheduling to model tokens.
- **Multiple writers with a lock, or a message broker:** rejected. A single writer plus a mailbox maps one-to-one onto the TLA+ model; one machine and ≤ 4 cells do not need a broker.
- **PID files for liveness:** rejected. Windows reuses PIDs.
- **Wall-clock budgets:** rejected. Host sleep would time out every running cell at once and blame the agents.

## Consequences

- **Positive:**
  - Crash, stop and resume semantics are provable (TLC) and testable (a kill in each state, and a test that no container survives).
  - Infrastructure faults never count against a harness.
  - The coordinator's context holds no cell text.
- **Negative / accepted trade-offs:**
  - The run lives as long as its engine. Suspend or reboot ends the running cells.
  - Resume arrives in the full milestone; in smoke, a crash means re-running.
  - The whole-run envelope can exceed one night: a smoke worst case of 6 tasks × 60 min × 8 cells ÷ 4 ≈ 12 h. `bench plan` states it.
- **Follow-ups / new risks:**
  - TLA+ obligations grow (see the architecture's lifecycle model list).
  - Spike the monotonic clock across sleep on Windows.

## Evidence

- Spec US-15, US-18, US-44, US-45 (gate-cleared).
- LOA P2, P3, P8.
- Council round 1: Distributed Systems V1–V6, SRE B1–B2 and advisories, Security advisory 1.
