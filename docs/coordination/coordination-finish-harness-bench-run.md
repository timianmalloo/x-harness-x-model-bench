---
id: coordination-finish-harness-bench-run
title: "Run record - coordination-finish-harness-bench"
type: doc
status: draft
owner: "@timianmalloo"
phase: "Phase 2 · smoke on all harnesses"
tags: [coordination, run-record, planned-vs-actual]
links:
  - { to: coordination-finish-harness-bench, rel: relates-to }
review-by: "2026-10-08"
summary: >-
  What happened when the finish-harness-bench plan was executed: qualifications, gate rounds, dispatches, slice
  joins, capture windows and planned against actual per track.
---

# Run record: coordination-finish-harness-bench

## Setup (Leader `coord-opus-cq`, 2026-09-24)

| step | result (measured) |
| --- | --- |
| Codex qualification | `qualify-codex-1` (default mode; its escalations were approved by Codex's own model reviewer) and `qualify-codex-2` (`agent-full-access`, selected). See `coordination-phase1-finish-run.md` (commit `e22ca74`) |
| Owner rulings | R-7, R-8, R-9 by the Owner seat (Fable): 44 tool calls, 465 s, 137,703 subagent tokens (as reported). Commit `0a64b0c` |
| Compile | raw `al-01M3AKF5D9FSZ2BE0ARDZCXNKQ` → compiled `al-01M3AKF6FZSG1RCB5FB5MR3C76`, dispatchable. One refusal first: the raw prompt named a forbidden construct, so it was rephrased and recompiled |
| Layer | `req-01M38KX8…` expired with its recorded fallback; `coord doctor` requests ok |
| W0-QUAL (`qualify-6`) | **Grok 1.0.41, no model pin:** `ready_for_review` in 101 s, 1 turn, 0 permission requests, 5 compatibility responses; ACP `selected_model: grok-4.7`. **Agy 1.2.10, no model pin, `accept-edits`:** `ready_for_review` in 75 s, 1 turn, 0 native denials; the conversation store shows executor `gemini-3.8-flash-high` and 17 generations on `gemini-3.8-flash`. Both commits touched only `docs/notes/qualify-worker.md`. The branches were qualification-only and were deleted |
| Stage 8 gate | round 1: Test Architect BLOCK, Tech Lead PASS WITH CONDITIONS, Simplifier BLOCK. Version 2 applied every finding or recorded a rationale. Round 2: Test Architect and Simplifier cleared their vetoes. Spend as reported: Test Architect 14 + 4 calls; Tech Lead 15 calls; Simplifier 25 + 5 calls |

## Correction

The 31-row to-do list said row 11 (power request) was "not built". It was built and wired in phase 1 (`host.py:89`; `engine.py:216/258`). The Simplifier found this at the gate, and the Leader verified it. Row 11 is closed by citation.

## Tracks: planned against actual

| track | harness · model | dispatched | slices / calls · wall | joined | exit evidence verified by the Leader |
| --- | --- | --- | --- | --- | --- |
