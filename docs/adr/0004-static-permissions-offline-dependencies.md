---
id: "adr-0004-static-permissions"
title: "ADR-0004: A static, symmetric permission profile and offline task dependencies"
type: adr
status: draft
owner: "@timianmalloo"
phase: "all phases"
tags: [benchmark, permissions, security]
links:
  - { to: arch-harness-bench, rel: refines }
  - { to: spec-harness-bench, rel: implements }
  - { to: note-spike-isolation-permissions, rel: depends-on }
review-by: "2027-09-23"
summary: >-
  Every harness runs with the same tool classes allowed statically, with no model-based approval:
  file edits and shell inside the container, no web tools, no package registry. Task dependencies are
  restored into the image before the clock starts.
---

# ADR-0004: A static, symmetric permission profile and offline task dependencies

- **Status:** Proposed
- **Date:** 2026-09-23 (revised after council round 1)
- **Deciders:** @timianmalloo; authored by Claude Code for the architect council
- **Context spec/architecture:** `docs/specs/harness-bench.md` US-14, US-46; spec risk R14

## Context

US-14 requires the same allowlist on every harness, with no approval made by a model. The spikes showed:
- the Codex default ACP mode delegates approvals to an automatic model reviewer (R2.2);
- Claude's `dontAsk` mode exists but is not advertised over ACP (R2);
- each harness has a static mechanism that ran shell and edits with zero prompts (R2.1).

With ADR-0001 the container is the sandbox, so a harness's own sandbox is not needed inside it. Agent-run package installs execute third-party code and need the network (R14).

## Decision

We will give each harness a static profile that allows exactly these tool classes: **file read and edit inside `/work`, shell inside the container**. It denies:
- web fetch and search tools;
- MCP servers other than the task's own;
- any other tool the harness offers.

| Harness | Mechanism |
| --- | --- |
| Claude | Per-cell `settings.json`: `permissions.allow = [Bash, Edit, Write, Read, Glob, Grep]`, `defaultMode = dontAsk`. |
| Codex | ACP mode `agent-full-access` inside the container (approval `never`, reviewer `user`), and per-cell `config.toml` with web search off. |
| Copilot | `--allow-tool shell --allow-tool write`, no `--allow-all*`, `--disable-builtin-mcps`. |

The permission files are mounted read-only over the writable home (ADR-0001), so an agent cannot widen its own profile. The driver refuses every permission callback, so anything outside the profile fails closed and is recorded. Task dependencies (NuGet, pip) are restored into the task image at bootstrap. Cells have no package-registry access (ADR-0005).

## Alternatives considered

- **Each harness's own recommended mode (Codex `agent`, Claude `acceptEdits`, Copilot defaults):** rejected. Codex self-approves through a model while the other two block (spike 2.5): an asymmetric treatment.
- **`bypassPermissions` or `--allow-all-tools` everywhere:** rejected. It widens beyond the declared classes (web, MCP) and is not a declared allowlist.
- **Allow package installs from public registries:** rejected. It runs untrusted code with network access, makes results depend on registry state, and breaks the "warm before the clock" rule.

## Consequences

- **Positive:**
  - One declared, symmetric capability set.
  - No model approves anything (US-14).
  - Deterministic dependencies.
- **Negative / accepted trade-offs:**
  - A task that genuinely needs a new dependency cannot fetch one. Task authors must declare dependencies in the task, and an agent adding one is scope creep by definition.
  - Harness web tools are unavailable, which some harness users rely on. This is recorded as a benchmark condition.
- **Follow-ups / new risks:**
  - Qualify each profile with a fixture: an allowed shell call succeeds; a web fetch and an out-of-profile tool are refused and recorded.
  - The Codex web-search setting name is to be read from the installed CLI's config reference (S-06).

## Evidence

- `docs/notes/spike-isolation-permissions.md` R2.1–R2.3 [Verified].
- The codex-acp mode definitions read from `@agentclientprotocol/codex-acp@1.12.0` [Verified].
- The Claude adapter's mode list read from `claude-agent-acp@0.79.0` `session-mode.js` [Verified].
