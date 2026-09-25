---
id: "note-20260925-stop-decision-calls"
title: "Row 10 design calls: decision triggers, the spend-cap unit, and defaultMode"
type: decision-note
status: draft
owner: "@timianmalloo"
phase: "Phase 2 · smoke on all harnesses (wave 2: row 10, W2-STOP)"
tags: [decision-note, stop, decisions, spend-cap, permissions]
links:
  - { to: design-phase2-stop-decisions, rel: relates-to }
  - { to: spec-harness-bench, rel: relates-to }
  - { to: rulings-register, rel: relates-to }
review-by: "2026-12-24"
review-suggested: []
summary: >-
  Three calls made while designing row 10 (W2-STOP-D): which cell causes raise a "blocked cell" or a "qualification
  gap" decision; that the spend cap counts tokens until the Owner rules DR-1; and that the Claude Code profile declares
  defaultMode "default" (R-34 condition 4). They shape the engine's triggers, the plan parameters and one profile line.
---

# Row 10 design calls: decision triggers, the spend-cap unit, and defaultMode

- **Kind:** decision (calls 1 and 3); an assumption awaiting a ruling (call 2)
- **Confidence:** call 1 Inferred (a reading of US-15 against the closed cause list); call 2 Flagged (DR-1); call 3 Verified (the effective mode is recorded)
- **Made during:** `/design-slice` for `docs/design/phase2-stop-decisions.md` (W2-STOP-D, 2026-09-25)

## The calls

1. **Decision triggers (US-15).** A "blocked cell" is a `cell.outcome` whose cause is `blocked_auth` (HB-CELL-202) or `blocked_permission` (HB-CELL-201). A "qualification gap" is one whose cause is `model_unavailable` (HB-CELL-116): the combo's pinned model is not served, so every cell of that combo would fail the same way. Why: these are the only causes in the closed taxonomy (`errors.py`) that name a blocked state or a combo-wide qualification failure. A decision opens only when pending cells can be affected, at most once per kind and subject, and never after a run stop.
2. **Spend-cap unit.** `spend_cap_tokens` is compared with Σ tokens over the four disjoint buckets, taken from `normalize.totals` (the report's own definition), checked when each cell ends. Why: cost is `NA` by decision on subscriptions, and tokens are the only spend measure the engine can read during a run. Cells whose usage is not recorded are counted and disclosed, never summed as 0.
3. **`defaultMode: default`.** The Claude Code profile declares `default`, which is the mode the session already reports. Why: a build that honoured `dontAsk` would refuse unlisted tools silently, with no permission request. US-14's count would then pass vacuously on the very asymmetry R-34 found.

## Alternatives dismissed

- Trigger a qualification gap on any `benchmark`-attributed cause: today that set is exactly `model_unavailable`, so an explicit list is the same set and clearer.
- A spend cap in USD: it needs a cost basis that phase 2 does not have (Copilot AI units are wave 3, R-15 Q6).
- Keep `dontAsk` with the disclosure: it keeps a stale declared datum and the silent-refusal risk above.

## Validation condition

Call 2 holds until the Owner rules DR-1. Call 1 holds until a new `Cause` is added to `errors.py`; a new blocked or benchmark cause re-opens it. Call 3 holds until a pinned Claude Code build reports a different effective mode (`permission_mode_effective`).

## Promotion rule

If a later wave adds decision kinds, or the gateway (ADR-0009) takes over spend, promote calls 1 and 2 into an amendment of ADR-0007.
