---
id: "adr-0001-cell-containers"
title: "ADR-0001: Every measured cell runs in its own hardened Linux container"
type: adr
status: draft
owner: "@timianmalloo"
phase: "all phases"
tags: [benchmark, isolation, security, containers]
links:
  - { to: arch-harness-bench, rel: refines }
  - { to: spec-harness-bench, rel: implements }
  - { to: note-spike-isolation-permissions, rel: depends-on }
review-by: "2027-09-23"
summary: >-
  Each cell runs in a fresh, hardened Linux container under Docker Desktop (WSL2), with a deterministic
  name, its own network, only its workspace and its own harness home mounted, and read-only permission
  files. It is the only option that gives all three harnesses the same containment and keeps host
  credentials unreachable by construction.
---

# ADR-0001: Every measured cell runs in its own hardened Linux container

- **Status:** Proposed. Supersedes the proposal's "authored tasks run natively on your workstation"; the spec is amended to match.
- **Date:** 2026-09-23 (revised after council round 1)
- **Deciders:** @timianmalloo (owner); authored by Claude Code for the architect council
- **Context spec/architecture:** `docs/specs/harness-bench.md`, `docs/architecture.md`

## Context

The spec requires symmetric containment across harnesses (US-14), no reach to host credentials (US-48), no external irreversible actions (US-49) and workspace isolation (US-8, US-13). The spikes measured the native option:
- only Codex sandboxes its commands on native Windows;
- Claude's `Bash` and Copilot's `shell` run as the operator (spike R2.3);
- a workspace under the user profile also loads `~/.claude/CLAUDE.md` (spike R1.3).

A Linux container with two mounts showed no host drives, an empty home and no secret variables. Claude and Codex completed the task inside one (spike R11.1–R11.2).

LOA P3 and P11 apply. The Sandboxed Executor and Bulkhead patterns are used (LOA 5.2).

## Decision

We will run every measured cell in a fresh Linux container, one per cell, under Docker Desktop (WSL2).

**Identity of the container.**
- Name `hb-<run_id>-<cell_id>`, labels `bench.run` and `bench.cell`, `--restart=no`.
- The name is the physical guard against a second launch, and the handle for killing and inspecting it (ADR-0007).

**Hardening.**
- Non-root user; `--cap-drop ALL`; `--security-opt no-new-privileges`; Docker's default seccomp profile.
- Never `--privileged`; no host PID, IPC or network namespace.
- Read-only root filesystem, with `tmpfs /tmp` mounted `noexec,nosuid`.
- `--pids-limit`, a `nofile` ulimit, and CPU and memory limits. Initial values: 2 CPU and 6 GB per cell. Phase 1 measures them, and preflight checks that parallelism × limits plus headroom fits inside the WSL2 VM.
- A per-cell workspace size cap, enforced by the run engine. Exceeding it ends the cell `blocked (disk cap)`.

**Mounts.**
- Only the cell's workspace at `/work`, and the cell's harness home at the harness's home path.
- The permission files (`settings.json`, `config.toml`) are mounted read-only over the writable home.
- No Docker socket, no host-profile path.

**Network.**
- One Docker network per cell: no cell-to-cell traffic.
- The only route out is the egress proxy (ADR-0005).
- Bootstrap refuses to run if the Docker daemon is exposed on TCP.

**Images.**
- One image per task environment (.NET 10 SDK, Python, or a Harbor task environment), carrying the pinned harness layer for all three harnesses. The image count is the number of task environments, not tasks × harnesses.
- Base images are referenced `FROM …@sha256`.
- Every CLI is installed from the pinned lockfile with integrity hashes, using `--ignore-scripts` where the package allows it. OS packages come from a dated snapshot.
- Each image gets an SBOM and a CVE scan at bootstrap. A known-exploited CVE in the harness layer blocks the build.
- Images are local only and never pushed: Claude Code and Copilot are proprietary.

**Paths.** Workspaces and homes live under a bench-owned root outside the user profile (default `C:\Projects\bench-cells`). Bootstrap refuses a root whose ancestors contain agent instruction files.

**Host version.** A minimum Docker Desktop version is pinned. Preflight records the version at run start and end.

## Alternatives considered

- **Native Windows with per-cell config homes:** rejected. Claude and Copilot run shell unsandboxed as the operator while Codex is sandboxed. US-14, US-48 and US-49 fail for two of three harnesses, and the asymmetry is itself a harness effect (spike R2.3).
- **A separate low-privilege Windows account:** rejected for v0. It needs administrator rights, gives no network control, and leaves containment asymmetric inside the account. Not spiked.
- **Windows Sandbox or a Hyper-V VM per cell:** rejected for v0. Heavier, not spiked, and gives nothing a container lacks for these CLIs.
- **Harbor as the environment and runner for every cell:** considered with ADR-0002 (runner). Harbor's container environments are reused as base images for its own tasks. Harbor's orchestration is not the cell runner, for the reasons recorded there.
- **Cloud sandboxes:** excluded by spec NG2.

## Consequences

- **Positive:**
  - The same containment for every harness.
  - Host credentials, other repos and the operator profile are unreachable by construction.
  - One environment shape for all tasks; reproducible images.
  - Per-cell native records by construction.
- **Negative / accepted trade-offs:**
  - Cells run on Linux, not Windows; every report header says so.
  - C# tasks rely on .NET 10 on Linux. [Inferred: AiDe.Core is cross-platform per the proposal]
  - Bind mounts from Windows paths may slow builds; named volumes are the measured fallback.
  - Docker Desktop is a hard prerequisite.
  - **Residual (accepted in writing):** an escape from the Docker Desktop WSL2 VM would reach the Windows drives. The hardening above and the pinned minimum version reduce but do not remove this.
- **Follow-ups / new risks:**
  - Harbor images that assume root conflict with the non-root rule (R12).
  - .NET SDK and Stryker in the image are unproven.
  - The measured resource limits are recorded in phase 1.

## Evidence

- `docs/notes/spike-isolation-permissions.md` R1.3, R2.3, R11.1, R11.2 [Verified].
- `docs/notes/spike-runner-path.md` 1.5 [Verified].
- Council round 1 (Security, SRE, Distributed Systems, Simplifier) requirements, recorded in `docs/architecture.md` Gate record.
