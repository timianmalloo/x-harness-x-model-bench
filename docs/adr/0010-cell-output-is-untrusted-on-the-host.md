---
id: "adr-0010-untrusted-cell-output"
title: "ADR-0010: Cell output is untrusted on the host; grading runs in containers"
type: adr
status: draft
owner: "@timianmalloo"
phase: "all phases"
tags: [benchmark, security, grading, boundary]
links:
  - { to: arch-harness-bench, rel: refines }
  - { to: spec-harness-bench, rel: implements }
  - { to: adr-0001-cell-containers, rel: depends-on }
review-by: "2027-09-23"
summary: >-
  Boundary B6: everything a cell wrote is untrusted. No host process executes, builds, imports or
  tests it; graders that run cell content do so in fresh no-network grading containers with read-only
  mounts. Host git runs only with a bench-owned configuration, the archiver never follows links, and no
  agentic tool on the host opens a cell workspace.
---

# ADR-0010: Cell output is untrusted on the host; grading runs in containers

- **Status:** Proposed
- **Date:** 2026-09-23
- **Deciders:** @timianmalloo; authored by Claude Code for the architect council (Security V1–V2, round 1)
- **Context spec/architecture:** `docs/architecture.md` boundaries; spec US-8, US-28–US-33, US-48

## Context

ADR-0001 contains the agent while it runs. After the cell ends, the host handles what the agent left behind.
- **Grading executes agent code.** Hidden tests, builds, mutation testing and formal tools all run it. Run on the host, that is delayed code execution as the operator.
- **Git on the workspace runs agent commands.** The agent controls `.git/config` (`core.fsmonitor`, `core.hooksPath`, filter and textconv drivers) and `.git/hooks`, so host git would run its commands.
- **Relative symlinks reach host secrets.** A link to `../../../../Users/<u>/.ssh/…` would pull host secrets into the archive, which is later sent to judges.
- **Agent-written tool configuration can fire on the host.** `.claude/settings.json` hooks or `.vscode/tasks.json` would run if an agentic tool on the host opened the workspace.

## Decision

Add boundary **B6 · cell output ↔ host tooling**. Everything under a cell's workspace, home and archive is untrusted.

1. **No host execution.** No host process executes, builds, imports or tests cell content. Every grader step that runs cell content runs in a fresh **grading container** with:
   - the ADR-0001 hardening and `--network none`;
   - the archive mounted read-only and the hidden tests mounted read-only;
   - schema-validated output only.
2. **Safe host git.** Host-side git runs only with a bench-owned configuration: `GIT_CONFIG_NOSYSTEM=1`, `GIT_CONFIG_GLOBAL=<bench file>`, `-c core.fsmonitor=false -c core.hooksPath=<empty dir>`, and no filter or textconv drivers. Otherwise it runs inside the grading container.
3. **No link following.** The archiver never follows symlinks, junctions or reparse points; it records them as links (`archive_files.kind = link`, ADR-0006).
4. **No host tooling on cell content.** No agentic tool on the host opens a cell workspace or archive. The coordinator session's deny rule covers these paths (ADR-0007).
5. **Failing-first tests.** Each of the three threats has one before phase 1 closes:
   - a planted `core.fsmonitor` marker command is not run;
   - a planted symlink to a host canary file is archived as a link, not as content;
   - a planted `.claude/settings.json` hook in a workspace is not triggered by any bench command.

## Alternatives considered

- **Grade on the host, with care:** rejected. "Care" is not a boundary, and a build or test run executes agent code by definition.
- **Grade inside the same cell container after the agent finishes:** rejected. The agent could have planted persistent processes or altered the toolchain in its own container. A fresh container from the task image, with read-only archive mounts, is the clean state.

## Consequences

- **Positive:**
  - The operator's host never runs agent code.
  - Archive integrity holds against link tricks.
- **Negative / accepted trade-offs:**
  - Each grading step pays a container start.
  - Graders are written against mounted paths, not host paths.
- **Follow-ups / new risks:**
  - The grading container image is the task environment image without the harness layer.
  - Timings are measured in phase 1.

## Evidence

- Security council round 1, V1 and V2 (threats Inferred; the tests above confirm them).
