---
id: "plan-spec-backlog"
title: "Spec backlog: from proposal to a running benchmark"
type: plan
status: draft
owner: "@timianmalloo"
tags: [benchmark, backlog, specs]
links:
  - { to: proposal-cross-harness-benchmarking, rel: implements }
  - { to: note-proposal-grounding-findings, rel: depends-on }
review-by: "2026-10-23"
summary: >-
  The ordered list of specs, architecture decisions and task-authoring units that turn the
  proposal into a working benchmark. Each unit names the pack skill that produces it, the proposal
  phase it serves, its dependencies, and the scaffold code it will replace.
---

# Spec backlog

Every `bench` command and module stub that is not built names one of these ids. Work top to bottom inside a phase; the critical path is marked ◆.

Source: `docs/proposals/cross-harness-benchmarking-proposal.md`. Open questions: `docs/notes/proposal-grounding-findings.md` (F1–F8).

## Phase 0: ground

| Id | Unit | Pack skill | Depends on | Resolves | Replaces |
| --- | --- | --- | --- | --- | --- |
| ◆ S-02 | Architecture of record: coordinator, worker isolation, pack on/off, coord-runner integration, results data model | `/define-architecture` (ADR per decision) | — | F1, F3 | `docs/architecture.md` (not yet written) |
| S-03 | BOM v0 freeze: upstream instance ids, pinned commits, E-task budgets, 22 vs 24 tasks | `/specify` | — | F5, F7 | `bench/bom.yaml` assumptions |

## Phase 1: runner

| Id | Unit | Pack skill | Depends on | Resolves | Replaces |
| --- | --- | --- | --- | --- | --- |
| S-01 | `/start-benchmark` compilation: prose → `matrix.yaml`, model-id resolution, run id | `/specify` → `/design-slice` | S-02 | — | `skills/start-benchmark` stage 0 |
| ◆ S-06 | Harness adapters over ACP: Claude Code, Codex, Copilot; model pin and served-model check | Spike Protocol per harness → `/design-slice` | S-02 | F3 | `adapters/*.py` |
| ◆ S-05 | Runner: bootstrap (pack on/off), coord-run/1 contracts, archive, teardown | `/design-slice` → `/implement` | S-02, S-06 | F2 | `runner/*.py`, `bench run`, `bench teardown` |
| ◆ S-07 | Telemetry: one event schema, OTel GenAI names; Codex reader first, then wrap `session-profile.py` | `/design-slice` → `/implement` | S-05 | — | `grade/telemetry/*`, `grade/normalize_telemetry.py` |

Phase 1 exit (proposal): one E-task runs end to end on every combo, and `usage.parquet` is populated from every harness.

## Phase 2: deterministic graders

| Id | Unit | Pack skill | Depends on | Replaces |
| --- | --- | --- | --- | --- |
| ◆ S-08a | Cost: prices, cost-of-pass, tokens per solved, cache ratios, context curve | `/design-slice` → `/implement` | S-07 | `grade/cost.py` |
| S-08b | Correctness and mutation | `/design-slice` → `/implement` | S-05 | `grade/correctness.py`, `grade/mutation.py` |
| S-08c | Rigor, drift, process | `/design-slice` → `/implement` | S-07 | `grade/rigor.py`, `grade/drift.py`, `grade/process.py` |
| S-08d | Clarify and architecture conformance | `/design-slice` → `/implement` | S-04 | `grade/clarify.py`, `grade/architecture.py` |
| S-08e | Coordination (reuse coord-core, audit-log selfcheck, cfd-bench grade-benchmarks axes) | `/design-slice` → `/implement` | S-07 | `grade/coordination.py` |
| S-08f | Normalisation, composites, `results.duckdb` schema (declare the grain first) | `/design-slice` → `/implement` | S-02 | `grade/normalize_scores.py`, `bench grade` |

Phase 2 exit: `bench grade` reproduces fixture scores byte-for-byte.

## Phase 3: tasks

| Id | Unit | Pack skill | Depends on |
| --- | --- | --- | --- |
| S-04 | Scripted user (likely an MCP `ask_user` tool; spike first) | Spike Protocol → `/design-slice` | S-06 |
| T-E1 | Smoke task E1 (Terminal-Bench 2.0 via Harbor) | `/new-bench-task` | S-03 |
| T-D1 | Smoke task D1 (ai-de Projections) | `/new-bench-task` | S-03 |
| T-B1 | Smoke task B1 (cfd-bench P0 primer) | `/new-bench-task` | S-03 |
| T-A1 | Smoke task A1 (ClarifyCodeBench) | `/new-bench-task` | S-03, S-04 |
| T-C1 | Smoke task C1 (ProjDevBench) | `/new-bench-task` | S-03 |
| T-F1 | Smoke task F1 (three-track wing spine) | `/new-bench-task` | S-03, S-05 |

Phase 3 exit: the smoke BOM (6 tasks × 1 rep) completes on all combos.

## Phases 4–6

| Id | Unit | Pack skill | Depends on |
| --- | --- | --- | --- |
| S-09 | Judges: rubrics, 30-item calibration sets, two blind vendor judges, cached verdicts | `/specify` → `/design-slice` | S-08f |
| S-10 | Report: CLI table, HTML (mockup is the layout target; fix F6), AI summaries | `/ui-design` → `/implement` | S-08f, S-09 |
| S-11 | Statistics: bootstrap CIs, correctness-gated ranking, repetition policy | `/specify` | S-08f |

Remaining BOM tasks (A2–A5, B2–B3, C2, D2–D3, E2–E7, F2) follow the smoke six through `/new-bench-task`.
