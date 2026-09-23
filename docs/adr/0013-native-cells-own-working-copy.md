---
id: "adr-0013-native-cells"
title: "ADR-0013: Cells run natively, each in its own git working copy"
type: adr
status: draft
owner: "@timianmalloo"
phase: "all phases"
tags: [benchmark, runner, validity, owner-ruling]
links:
  - { to: arch-harness-bench, rel: refines }
  - { to: adr-0001-cell-containers, rel: supersedes }
  - { to: adr-0012-proportionate-security, rel: depends-on }
  - { to: note-spike-isolation-permissions, rel: depends-on }
  - { to: spec-harness-bench, rel: refines }
review-by: "2027-09-23"
summary: >-
  Owner ruling: isolation beyond a working copy is not required. Each authored-task cell is a native
  process on the operator's Windows workstation, working in its own git working copy, with its own harness
  home and a symmetric unsandboxed permission profile. A Windows Job Object is how the engine stops a
  cell and knows it has stopped, not a sandbox. Containers, the egress proxy and every other isolation
  control are dropped for authored tasks; Harbor tasks keep their containers.
review-suggested: []
---

# ADR-0013: Cells run natively, each in its own git working copy

- **Status:** Proposed. **Owner ruling, 2026-09-23.** Supersedes ADR-0001 for authored tasks.
- **Deciders:** @timianmalloo; authored by Claude Code.
- **The ruling:**
  - "Why do we actually even need docker and containers? Our current coordination model allows us to spawn CLI instances without that. We don't need extra isolation."
  - "Again, I think the security and isolation constraints are excessive. If an agent benchmark is operating in its own worktree, that's all we are looking for."
  - On an agent running with the operator's rights: "that's a risk that I am not worried about."
- **Context spec/architecture:** `docs/specs/harness-bench.md` (US-8, US-12, US-13, US-14, US-48, US-49 as amended); `docs/architecture.md`; ADR-0012.

## Context

ADR-0001 put each cell in a Linux container, mostly for security (US-48, US-49), and for symmetric containment. Natively, Codex ran in its own Windows sandbox while Claude and Copilot did not (spike R2.3). ADR-0012 then scoped security to one trusted operator, and the owner has now ruled that a working copy is the only isolation wanted. Spikes N1 and N2 (`docs/notes/spike-isolation-permissions.md`) confirm that the native path works:
- **N1.1 [Verified]:** with Codex in ACP mode `agent-full-access`, all three harnesses run natively the same way. None is sandboxed, and there are 0 permission requests.
- **N1.2 [Verified]:** Copilot runs natively with an empty per-cell home. Its login comes from the Windows credential store, so no token is needed.
- **N1.3 [Verified]:** every harness records the exact commands it ran in its native record.
- **N2 [Verified]:** a Windows Job Object kills a cell's whole process tree and confirms it (active processes 2 → 0). With kill-on-close, the tree dies when the engine dies. It also reports peak memory.

## Decision

**1. A cell is a native process working in its own git working copy.**
- The engine keeps one bench-owned local clone per task version, at the base commit, with no remote: the task source.
- Each cell gets its own `git clone --local` of the task source (objects hardlinked, nothing else shared), under `<cells root>/<run_id>/<cell_id>/ws`. The clone's `origin` remote is removed at once (`git remote remove origin`, which also drops the `origin/*` refs), so the working copy has no remote.
- The cells root defaults to `C:\Projects\bench-cells`.
- **Why not `git worktree`**, the owner's word: worktrees of one clone share refs, stashes and config, so one cell's commits, stashes and added remotes appear in every other cell. For example, a pack-on solution would show in its pack-off twin's `git log --all`, which is a measurement leak. Distributed Systems and the Test Architect each confirmed this at the gate in a scratch repository. A local clone per cell is the same idea (the agent's own working copy) with nothing shared.

**2. What else a cell gets, and why.** Each item is kept because it changes what is measured, not to isolate anything.

| Kept | Why (the measurement it protects) | Evidence |
| --- | --- | --- |
| Hidden tests and oracle never in the task clone or its history | Otherwise the agent has the answer key, and the score means nothing (US-3, US-8) | — |
| A per-cell harness home (`CLAUDE_CONFIG_DIR`, `CODEX_HOME`, `COPILOT_HOME`) | Without it the operator's own `CLAUDE.md`, skills and Codex config load into every cell, so a pack-off cell is not bare and pack on/off blur (US-13). It also gives each cell its own native record (telemetry) and the model pin. | R1.1–R1.2, spike 1.5 [Verified] |
| No agent instruction file in any ancestor of the cells root | Claude reads `CLAUDE.md` from every parent directory, so a root under the user profile (which holds `.claude/CLAUDE.md`) loads the operator's instructions anyway (same confound). Preflight refuses a root with `CLAUDE.md`, `.claude/CLAUDE.md` or `AGENTS.md` in an ancestor (HB-PRE-002). | R1.3 [Verified] |
| A symmetric, static permission profile (below) | The same freedom for every harness, so the comparison is fair (US-14), and no prompts, so cells run unattended | N1.1 [Verified] |
| Pinned harness builds in a bench-owned tools folder, invoked by path and re-hashed at every cell start | The report must say which build was measured (US-12). Harness CLIs update themselves [Verified: the installed Claude Code went 2.1.280 → 2.1.281 during the 2026-09-23 session, leaving `claude.exe.old.*` beside it], so without a pinned copy the build could change between cells of one run. | spike 1.3 [Verified] |
| A Job Object per cell | Not isolation: it is how the engine enforces the time budget and a stop, and knows the cell has stopped before recording its outcome. It also means an engine crash leaves no running cell. Its handle is not inheritable, so kill-on-close fires when the engine dies. Phase 5 (resume) names the job in the launch intent so resume can find it; phase 1 has no resume and needs no name. At the end of every turn the engine terminates the job, so a lingering build server never keeps it alive. | N2 [Verified]; inheritance Inferred → probe N4 |

**Cell process environment.** The adapter is spawned suspended with an explicit handle list (only its own three pipes), then assigned to its job, then resumed, so no other cell's pipe or handle leaks in. Shared build servers that would outlive the turn or join another cell's job are switched off in cells and grading jobs: `MSBUILDDISABLENODEREUSE=1`, `UseSharedCompilation=false`, and `core.fsmonitor=false` (through `GIT_CONFIG_COUNT`).

**Profiles:**

| Harness | Home and credential | Permission profile |
| --- | --- | --- |
| Claude | `CLAUDE_CONFIG_DIR=<home>`; `.credentials.json` copied in, deleted at cell end | `settings.json`: allow Bash, Edit, Write, Read, Glob, Grep; `defaultMode: dontAsk`; `ANTHROPIC_MODEL` pinned |
| Codex | `CODEX_HOME=<home>`; `auth.json` copied in, deleted at cell end | ACP mode `agent-full-access`; `config.toml` pins the model |
| Copilot | `COPILOT_HOME=<home>` (empty); the Windows credential store | `--allow-tool shell --allow-tool write`, `--model` pinned |

**3. Dropped for authored tasks.** None of these is replaced:
- containers and images;
- the per-cell network and egress proxy;
- the container-configuration test;
- grading containers;
- limits on what an agent may read or write outside its working copy.

Grading runs natively too: each step that runs cell content works in its own grading working copy (the archive, plus the hidden tests), inside its own Job Object with a deadline.

**4. Harbor tasks keep containers.** Harbor's task format is a container, so Harbor (E-task) cells run in Harbor's environments under Docker Desktop, as the proposal had it. That design is decided with spike A6 in phase 2.

**5. Platform.** Authored-task cells run on Windows, the operator's platform. The report header says so.

## Alternatives considered

- **Keep a container per cell (ADR-0001):** rejected by the owner ruling. Its costs were Docker Desktop, images, WSL2 memory, bind-mount speed, clock skew, a Linux-only platform and a Copilot token.
- **Worktrees of one shared clone:** rejected at the gate. They share refs, stashes and config between cells (Decision 1).
- **Native, plus validity controls in place of containment:** rejected as excess by the owner. Those were a reach audit of tool calls, a host-drift check and per-cell package caches.
- **Native, with `taskkill /T` and no Job Object:** rejected. It cannot confirm that the tree is gone, and an engine crash leaves cells running (N2.2 shows the job does both).

## Consequences

- **Positive:**
  - No Docker Desktop for authored tasks.
  - Copilot needs no token: owner decision 6 closes, and probe C1 is not needed.
  - Cells run where the operator works.
  - No cell survives an engine crash.
  - A whole failure layer goes: images, pulls, WSL2 memory and exit 137, container create, clock skew.
- **Accepted by the owner:**
  - An agent runs with the operator's rights and can read or write outside its working copy, including other repositories, the operator's logins and the bench repository.
  - An agent could read a hidden test from the bench repository, or change the host toolchain that later cells use. Nothing detects this. If it is ever seen in a result, the reach audit in the alternatives above is the ready upgrade.
  - Agent-run package installs go to the shared user caches.
- **Follow-ups:**
  - Probe N4 (phase 1): an adapter's child CLI stays inside the job [Inferred: breakaway is never allowed].
  - `models/run_lifecycle.tla` keeps its semantics. Its container becomes the cell's process tree, and the more general behaviour it checks (a tree may outlive a crash) is a sound superset of kill-on-close.

## Evidence

- `docs/notes/spike-isolation-permissions.md` N1, N2, R1, R2 [Verified].
- `codex-acp` 1.12.0 `AgentFullAccess` mode [Verified by reading].
