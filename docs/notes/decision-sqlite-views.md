---
id: "note-20260923-sqlite-views"
title: "Results views are pure-Python projections, with no SQL engine, until a measured trigger"
type: decision-note
status: draft
owner: "@timianmalloo"
phase: "Phase 1 · walking skeleton"
tags: [decision-note, data-model, dependencies]
links:
  - { to: adr-0006-results-data-model, rel: relates-to }
  - { to: design-phase1-walking-skeleton, rel: relates-to }
review-by: "2027-03-22"
review-suggested:
  - { by: adr-0006-results-data-model, on: 2026-09-24, reason: "Amendment 1: model_calls grain re-declared per native usage report with requests and model in the key; tool_calls.outcome_code (R-26, R-27)" }
summary: >-
  The derived results views (ADR-0006) are pure-Python functions over the verified fact dataclasses; no
  SQL engine (DuckDB or sqlite3) is used. Blast radius: views.py only; the facts on disk are unchanged.
---

# Results views are pure-Python projections, with no SQL engine, until a measured trigger

- **Kind:** decision
- **Confidence:** Inferred. Pure functions over stdlib dataclasses, and the data volume is small by construction. The build time is measured in phase 1.
- **Made during:** `/design-slice` of the phase-1 walking skeleton, 2026-09-23.

## The call

`views.py` reads the run's verified JSON Lines facts into dataclasses and computes each derived view with a pure function. No database is used or persisted (ADR-0006). (Revised at the design gate: the first draft used in-memory `sqlite3`; the Simplifier showed pure functions do the same at this volume.)

**Why:** the Solution-Selection Ladder stops at stdlib (rung 3). A run has at most 576 cells, so the facts are at most tens of thousands of rows. DuckDB's JSON reader was an unspiked assumption in the architecture, and a new dependency needs a reason past rung 5.

`simplify:` ceiling 10⁶ fact rows or a 30 s report build. Upgrade trigger: either one is exceeded in a measured run.

## Alternatives dismissed

- **DuckDB reading JSON Lines directly:** a new dependency for a volume stdlib handles; unspiked.
- **In-memory `sqlite3` views:** an engine and a second language for derivations that are a few pure functions.

## Validation condition

Holds until a measured report build exceeds 30 s, or a run's facts exceed 10⁶ rows. The full-grid run (576 cells × 3 repetitions of model calls) is the first likely trip point.

## Promotion rule

If the views grow into an analytical layer that other tools query, promote this to an ADR amendment of ADR-0006.
