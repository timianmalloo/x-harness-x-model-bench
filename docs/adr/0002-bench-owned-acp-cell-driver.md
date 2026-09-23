---
id: "adr-0002-cell-driver"
title: "ADR-0002: The bench drives cells with its own ACP cell driver, not the pack's coord-runner or Harbor"
type: adr
status: draft
owner: "@timianmalloo"
phase: "all phases"
tags: [benchmark, runner, acp, pack, harbor]
links:
  - { to: arch-harness-bench, rel: refines }
  - { to: spec-harness-bench, rel: implements }
  - { to: note-spike-runner-path, rel: depends-on }
  - { to: note-spike-isolation-permissions, rel: depends-on }
review-by: "2027-09-23"
summary: >-
  Measured cells are launched by a small bench-owned driver that speaks ACP to the containerised
  harness with a container-side cwd, a verbatim prompt, a per-cell model pin, deny-all permissions and a
  deadline on every step. The pack's coord-runner cannot meet US-9, US-10 or US-11 as installed; Harbor's
  one-shot, permissive agent runs cannot meet US-10 (scenario 1), US-14 or at-most-once. Both are
  recorded, with a trigger to re-evaluate.
---

# ADR-0002: The bench drives cells with its own ACP cell driver, not the pack's coord-runner or Harbor

- **Status:** Proposed. Supersedes the proposal's "every measured cell is a worker in a coord-run/1 contract".
- **Date:** 2026-09-23 (revised after council round 1)
- **Deciders:** @timianmalloo; authored by Claude Code for the architect council
- **Context spec/architecture:** `docs/specs/harness-bench.md`, `docs/architecture.md`

## Context

The proposal routed every cell through the pack's `coord-runner.py`. The spikes found five blockers in revision 92:
- a pack-shaped prompt with a pack-script preamble even in `pack=off` (spike 2.4; fails US-9 and US-10);
- model pin and check for Copilot only (spike 1.4; fails US-11);
- no per-worker environment;
- the host `cwd` in `session/new`, which a container cannot resolve (R11.4);
- worktrees taken from the invoking checkout.

The proposal also named Harbor as "runner infrastructure worth reusing rather than rebuilding". Harbor was not spiked.

## Decision

We will launch measured cells with a bench-owned ACP cell driver (Python, stdlib only). It:
- starts the cell container (ADR-0001) with `docker run -i` under its deterministic name;
- speaks ACP over stdio, sending `session/new` with `cwd=/work`;
- selects the profile's literal mode, pins the model per cell (ADR-0003), and sends the task prompt **verbatim** (plus scripted-user replies for scenario 1);
- refuses every permission callback.

**The driver as a host input surface.**
- It advertises `fs` and `terminal` capabilities as false.
- It accepts only `session/update` notifications and `session/request_permission` requests from the agent; every other agent-to-client method gets `Method not supported`.
- It parses strictly and bounds line length and total bytes.
- It forwards only typed events (ids, enums, counts, timings) to the run engine. The adapter's and CLI's stderr tail is written to the cell archive, never to the engine's status.

**Deadlines everywhere.** Every Docker call (`build`, `run`, `inspect`, `kill`, `rm`) has its own deadline, and so does the pre-prompt handshake (`initialize`, `session/new`, `set_mode`, `set_model`). A handshake timeout ends the cell `failed (handshake timeout)`, attributed to infrastructure (ADR-0007). Stopping a cell is `docker kill hb-<run>-<cell>` confirmed by `docker inspect`, because killing the host client does not stop the container.

**The pack stays the treatment.** The pack's coordination layer is used inside `pack=on` cells and inside scenario-6 cells. The spec's anti-corruption layer to the pack is the grader that reads a cell's coordination ledger (US-34).

## Alternatives considered

- **coord-runner as installed:** rejected. It fails US-9, US-10 and US-11 and cannot reach a container.
- **Change coord-runner upstream, then `/updatepack`:** rejected for v0. Four changes in another repo on the critical path, and it would turn the pack's coordination runner into a benchmark runner. Filed as a tracked request to ai-forward: container cwd mapping, verbatim-prompt mode, per-worker environment. **Re-evaluation trigger:** when a pack revision ships all three, re-test coord-runner as the cell launcher against this driver's contract tests.
- **Reuse `coord_transport.run_session`:** rejected. One `cwd` serves both the host process and the ACP session. Its failure discipline (bounded reads, owned cleanup) is the driver's design reference.
- **Harbor as the runner for all cells:** rejected [Inferred; Harbor not spiked]. Its installed agents run headless and one-shot (`claude -p`, `codex exec`), install CLIs at run time and use permissive modes. That breaks:
  - the multi-turn verbatim scripted user (US-10);
  - the static symmetric allowlist (ADR-0004);
  - pinned builds with no registry access (US-50);
  - the at-most-once launch ledger (ADR-0007).
- **This driver as a Harbor custom agent:** deferred. Spike A6 (phase 2) tests it on task E1. If it works, Harbor tasks run through Harbor's harness while keeping this driver's guarantees.

## Consequences

- **Positive:**
  - Verbatim, pack-free prompt delivery; per-cell model pins; container-native cwd.
  - A small, fully tested driver with a narrow input surface.
- **Negative / accepted trade-offs:**
  - **The benchmark no longer runs on the pack's coordination layer at scale.** The proposal intended to dogfood `coord-run/1`, the board and the audit log as the run's own record. That coverage is lost for v0. The pack is measured as a treatment, not exercised as the benchmark's runner.
  - The `/start-benchmark` skill still writes the pack's audit-log entries for each run.
  - The bench owns an ACP client, so adapter upgrades must pass its contract tests (the profile qualification suite, ADR-0011).
  - The proposal's promise of a task format portable to and from Harbor is kept only if spike A6 succeeds. Otherwise it is dropped on the record.
- **Follow-ups / new risks:**
  - The upstream request to ai-forward.
  - Spike A6 (the driver as a Harbor agent).
  - Per-harness ACP contract tests from recorded fixtures.

## Evidence

- `docs/notes/spike-runner-path.md` 1.4, 2.1–2.5 [Verified].
- `docs/notes/spike-isolation-permissions.md` R11.4 [Verified].
- `coord_transport.py:663` [Verified by reading].
- The spike driver `spikes/runner-path/container_acp.py` completed Claude and Codex turns in containers [Verified].
- Harbor's behaviour is from the proposal and the Enterprise Architect's review [Inferred].
