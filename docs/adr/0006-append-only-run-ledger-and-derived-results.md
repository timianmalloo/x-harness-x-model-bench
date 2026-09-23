---
id: "adr-0006-results-data-model"
title: "ADR-0006: A hash-chained, append-only record per run; every result is a derived view"
type: adr
status: draft
owner: "@timianmalloo"
phase: "all phases"
tags: [benchmark, data-model, persistence, grain]
links:
  - { to: arch-harness-bench, rel: refines }
  - { to: spec-harness-bench, rel: implements }
review-by: "2027-09-23"
summary: >-
  The durable record is a set of append-only, hash-chained JSON Lines facts per run with declared
  grains (lifecycle events, model calls, tool calls, archive files, grading passes, scores, verdict uses,
  egress events), immutable content-addressed dimensions, and one shared content-addressed verdict cache.
  Current states, costs, composites and statistics are derived views in in-memory DuckDB; no results
  database is persisted.
---

# ADR-0006: A hash-chained, append-only record per run; every result is a derived view

- **Status:** Proposed
- **Date:** 2026-09-23 (revised after council round 1)
- **Deciders:** @timianmalloo; authored by Claude Code with the Data & Persistence Architect lens
- **Context spec/architecture:** `docs/specs/harness-bench.md` (conceptual model; US-4, US-17–US-19, US-22–US-27, US-47, US-52)

## Context

The spec's model has immutable versioned entities (task version, BOM, catalog, price list, plan) and change over time as events. Its constraints:
- grading is a pure function of an archive (US-26);
- resume is idempotent (US-18);
- historical scores never move silently (US-4);
- derived quantities are never stored as truth.

The domain standard defaults to dimensions plus append-only facts (DM5), with analytical layers as derived projections (DM6). Council round 1 found:
- a re-grade would collide on the score key;
- several spec facts had no declared grain;
- cached verdicts were stored inside one run but reused by others;
- a key part could be null;
- append-only was not enforced across a crash.

## Decision

### Physical form and integrity (DM11)

- **Where facts live.** `runs/<run_id>/` holds one directory per fact. Each writer session appends to its own **segment** file (JSON Lines).
- **Every line is a hash chain.** Each line carries `seq`, `prev_hash` and `hash` (sha256 of the line content plus `prev_hash`). It is written with one `write`, then flush, then `os.fsync`.
- **Torn tail.** On open, only a final line with no newline, or one that fails to parse, may be dropped, and it is recorded as a `ledger.tail_repaired` event. Any other broken line or chain break is an integrity error that stops the run.
- **Verification.** `bench verify <run_id>` checks every chain. Tests that attempt a rewrite, a truncation and a mid-file insert must fail verification before phase 1 closes.
- **Single writer.** Each fact directory has exactly one writer process at a time. The run engine writes lifecycle facts. A grading pass (from `bench grade` or from the engine) writes grading facts and its `events` rows only while holding `grade.lock`, which excludes every other writer of `events` (ADR-0007).

### Identity

- `cell_id` = a deterministic hash of `(task_version_hash, combo_id, pack_setting, repetition)`, computed in the plan. Resume and run comparison (US-52) use it.
- Dimension files (plan, BOM version, catalog version, price list version, harness profile, image manifest) are content-addressed. A test asserts that each id equals the file's hash.

### Facts and their grains

| Fact | Grain: one row is exactly one … | Key | Measures and additivity | Writer |
| --- | --- | --- | --- | --- |
| `events` | state transition of one run-scoped entity: the run, a cell, an attempt, a decision request, a control input, or a grading pass. Its states are those of `models/run_lifecycle.tla`. | `(run_id, segment_id, seq)`, plus `entity_kind`, `entity_id` and `recorded_at` | none. Rows carry the transition's attributes: e.g. `attempt.started` holds the executed harness build, image digest, container name and native session ids; `cell.archived` holds the archive manifest hash. | run engine; grade process for grading passes |
| `model_calls` | model request made by one principal (a cell, the coordinator session, or the model gateway) | `(run_id, principal, native_session_id, native_ordinal)`; `cell_id` when the principal is a cell | Tokens in **disjoint buckets**: uncached input, cache read, cache write, output (additive). Reasoning is a component of output, never added to it. Start and end timestamps (not durations). Native billing units (additive). | telemetry normaliser |
| `tool_calls` | tool invocation inside one cell | `(run_id, cell_id, native_session_id, native_ordinal)` | start and end timestamps | telemetry normaliser |
| `archive_files` | file or link in one cell archive | `(run_id, cell_id, path)` | size (additive); sha256; kind (file or link, never followed) | archiver |
| `scores` | value of one metric for one cell in one grading pass | `(run_id, grading_id, cell_id, metric_id)` | value (non-additive); NULL with a reason when NOT_RECORDED; the archive hash graded, which is derived from the cell's sorted `archive_files` rows (no separate manifest file) | grade process |
| `verdict_uses` | use of a cached verdict or match by one grading pass | `(run_id, grading_id, cell_id, item_id, judge_or_matcher)` | cache hit (yes/no) | grade process |
| `egress_events` | scan-and-send attempt | `(scope_id, seq)`, where the scope is a run or a report (a report over two runs publishes once) | payload hash; destination; purpose; result: sent, withheld or quarantined | egress gate |

A grading pass is an entity in `events` (`grading.started` / `grading.completed`), carrying `grading_id`, catalog version and grader build hash. The **current score** of a cell for a catalog version is the value from the latest completed grading pass for that catalog version: the greatest `recorded_at` on `grading.completed`, tie-broken by `grading_id`. This rule is defined once, in the projection. A re-grade (after a judge outage or a grader fix) is a new grading pass. Nothing is overwritten.

**Shared verdict cache.** Judge verdicts and clarification matches live in one content-addressed store outside any run, `cache/verdicts/<key>.json`, written create-if-absent (the first writer wins; an existing key is never replaced). The key covers: artifact hash, rubric or matcher version, prompt-template version, output-schema version, model id and backend. A run's own `verdict_uses` rows make its grading reproducible alone, as long as the cache is kept.

### Dimensions

Dimensions are immutable, content-addressed versions (DM10 Type-2 by identity): task version, BOM version, catalog version (definitions, weights, normalisation anchors, rubrics, radar axis order), price list version, combo, harness profile, image manifest, plan. The planned harness build lives in the plan; the executed build lives in `events` (`attempt.started`); US-12 compares the two.

### Derived, never stored (DM7)

All of these are DuckDB views over the JSON Lines, opened in memory by `bench report`, with no persisted database:
- current cell outcome and validity;
- cell wall time (outcome time − launch-intent time);
- `cost_usd` (model calls × the price list version named in the report);
- coordinator overhead (the coordinator and gateway principals);
- composites, pass@k, pass^k, cost-of-pass;
- bootstrap intervals (the seed is in the plan);
- pack effect, comparison and ranking.

"Identical results" (US-26) is claimed for **canonical sorted exports** of the views. A test rebuilds them twice and compares the hashes.

**Comparison (US-52).** Each run's plan names its own catalog, price list and BOM versions. A comparison reads both plans, refuses if they differ in combos, BOM or catalog, and otherwise joins by `cell_id` ingredients (task version, combo, pack, repetition).

### Retention

- `runs/` is kept until P1 deletes it. Ledgers may outlive pruned archives: pruning records `archive.pruned` in `events`, and US-41's "archive absent" state covers it.
- The verdict cache is kept as long as any run references it. Pruning the cache makes those runs' re-grades call judges again, and the run says so.

## Alternatives considered

- **A persisted `results.duckdb` as the operational store:** rejected. It is mutable, duplicates the archive, and makes grading impure.
- **Separate current-state files (`cell_outcomes`):** rejected. They are the terminal transition of a cell, already in `events`; a second record of one fact would drift (DM7).
- **One fact file per entity kind (`decision_events`, `attempts`, `run_events`):** rejected in favour of one lifecycle log with a declared grain ("one state transition of one run-scoped entity"). One ordered, single-writer log maps one-to-one onto the TLA+ model's trace and keeps one hash chain.
- **Per-file manifest hashed at close:** rejected. A crashed run's files are never closed. The per-line chain survives a crash.
- **Normalised relational schema, or event sourcing of scores:** rejected. Nothing mutates in place, and scores are recomputed, not replayed.

## Consequences

- **Positive:**
  - The audit trail is the data.
  - Resume reads `events`.
  - Re-grades and new catalog versions append beside the old ones.
  - Integrity is checkable offline.
- **Negative / accepted trade-offs (DM13 deviation):**
  - The operational store is files, not a database.
  - Current-state reads scan `events`, accepted at ≤ 576 cells per run.
  - Token buckets must be normalised per harness: OpenAI-style input includes cached tokens; Anthropic-style input excludes them. [Verified in spike records: Codex input 19,597 includes 12,672 cached; Copilot input 12,948 includes 12,945 cache-write; Claude input 2 with cache counted separately]
- **Follow-ups / new risks:**
  - Property tests for the chain, the grains and the current-score rule.
  - The DuckDB JSON reader is confirmed in S-08f. [Inferred]

## Evidence

- Spec conceptual model (gate-cleared).
- `domain-and-data-modelling.md` DM5–DM13.
- Spike native records (token semantics) [Verified].
- Council round 1: Data & Persistence V1–V5, Distributed Systems V2 and V4, Simplifier 2–5.
