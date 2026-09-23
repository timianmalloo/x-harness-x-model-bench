---
id: "adr-0003-harness-profile"
title: "ADR-0003: A pinned, per-cell harness profile with a scoped credential and a verified model"
type: adr
status: draft
owner: "@timianmalloo"
phase: "all phases"
tags: [benchmark, harness, identity, model-pinning]
links:
  - { to: arch-harness-bench, rel: refines }
  - { to: spec-harness-bench, rel: implements }
  - { to: note-spike-isolation-permissions, rel: depends-on }
review-by: "2027-09-23"
summary: >-
  Each harness has a versioned profile (Ports & Adapters): pinned CLI build, a fresh per-cell home
  seeded only with a credential and read-only permission files, a per-cell model pin, and a post-cell
  check that at least one model call succeeded on the pinned model. Operator subscription logins may run
  only operator-authored tasks; every archive and egress is scanned for the exact credential values issued
  to the run.
---

# ADR-0003: A pinned, per-cell harness profile with a scoped credential and a verified model

- **Status:** Proposed
- **Date:** 2026-09-23 (revised after council round 1)
- **Deciders:** @timianmalloo; authored by Claude Code for the architect council
- **Context spec/architecture:** `docs/specs/harness-bench.md` US-11, US-12, US-13, US-47, US-48, US-50

## Context

From the spikes:
- adapters run bundled CLI builds unless overridden, and the bundled Codex rejected the pinned model while ACP reported `end_turn` (spikes 1.3, R11.5);
- the model comes from different places per harness, and only Copilot is pinned through ACP (spike 1.4);
- per-cell homes keep sign-in and drop user-level skills (R1.1–R1.2);
- Claude's account context survives any isolation under a claude.ai login (R1.4).

The workstation has no API keys today. Codex uses a ChatGPT-account login, and the Copilot token lives in the Windows credential store (R11.3).

A copied subscription login is the **operator's account credential**: long-lived, refreshable, and readable by the agent that runs as the same user in the container.

## Decision

**One versioned harness profile per harness** (data, Ports & Adapters). It holds:
- the image layer and CLI build (version and hash);
- the ACP entry point and literal mode;
- the model-pin mechanism: Claude `ANTHROPIC_MODEL`; Codex `model` in the per-cell `config.toml` plus `session/set_model`; Copilot `--model` plus `session/set_model`;
- the seeded home files;
- the native-record reader.

**Per cell:**
1. Create a fresh home.
2. Seed it with the profile's permission files (mounted read-only, ADR-0001) and the credential.
3. Run the cell.
4. Remove the credential copy before archiving.
5. Verify the native record: **at least one successful model call**, and every call on the pin, or on a model the task's `model_map` or the profile's auxiliary list allows.

Home seeding is a function of the profile, not a separate component.

**Credential kinds and where each may be used:**

| Kind | Allowed for |
| --- | --- |
| Vendor API key, or a fine-grained GitHub token with Copilot access only, for a benchmark-only identity (revocable, spend-capped) | Any task, including third-party and hostile fixtures |
| A dedicated benchmark subscription account | Any task |
| The operator's own subscription login, copied | **Operator-authored tasks only.** No Harbor or third-party task, no hostile fixture. The run engine refuses any other combination. The run header states `credential: operator subscription`. |

**Operator-authored** is derived by the bench from task provenance: a task under `tasks/`, committed by the operator, and not imported from Harbor or any third party. It is never read from a field in the task.

**Exact-value scan.** The run engine keeps the exact values of every credential issued to the run, in memory only. Before deleting a cell's credential copy, it reads every token value now in the cell's credential files (a CLI may have refreshed them) and adds them to the scan set. The scan also matches base64 and URL-encoded forms. Before any cell's archive is written and before any egress (ADR-0005), every archived byte is scanned for those values. A hit:
- quarantines the whole cell from egress;
- records `credential exposed`;
- marks the credential for rotation in the completion summary.

## Alternatives considered

- **Mount the operator's real harness homes read-only:** rejected. Every user-level instruction, skill and memory would enter the cell (spike 1.5, R1).
- **Environment variables for every harness:** rejected as the only mechanism. Claude and Codex subscription logins are files. Variables are used for API keys and the Copilot token.
- **Pattern-based secret scanning only:** rejected. OAuth tokens and JWTs are missed by key patterns. The exact values are known and are the precise test.
- **Trust the ACP-advertised model:** rejected. The advertised model is not the served model (spike 1.4).

## Consequences

- **Positive:**
  - Every cell's build, model, configuration and credential kind is known.
  - Two models of one harness can share a run.
  - Zero-call "completed" cells become `invalid (no model call)`.
  - An exposed credential is caught exactly, and never leaves the host.
- **Negative / accepted trade-offs:**
  - Until the owner creates benchmark credentials, only operator-authored tasks run.
  - Copilot cells are `blocked (auth)` without a token.
  - Claude cells carry account context under a subscription login, which the report states.
  - **Residual (accepted in writing):** a cell can always reach its own model credential by design.
- **Owner ruling (2026-09-23): subscriptions only, no API keys.** Every cell runs on a copied subscription login, so only operator-authored tasks may run until the owner chooses between swapping third-party smoke tasks for authored ones, a dedicated benchmark subscription account, or a recorded deviation. Copilot cells need a Copilot-only fine-grained token (still billed to the subscription), else `blocked (auth)`.
- **Follow-ups / new risks:**
  - Spike whether a cell's OAuth refresh rotates and invalidates the host login. Until then, copies are refreshed from the host before each cell and never written back.
  - The owner decides whether to create benchmark credentials.

## Evidence

- `docs/notes/spike-runner-path.md` 1.3, 1.4 [Verified].
- `docs/notes/spike-isolation-permissions.md` R1.1–R1.4, R11.3, R11.5 [Verified].
- Credential locations read by key name only [Verified].
- Security council round 1, V3.
