---
id: "note-20260923-token-source"
title: "Token totals come from the source that is complete for each harness"
type: decision-note
status: draft
owner: "@timianmalloo"
phase: "Phase 1 · walking skeleton"
tags: [decision-note, telemetry, validity]
links:
  - { to: adr-0008-telemetry, rel: refines }
  - { to: design-phase1-walking-skeleton, rel: relates-to }
review-by: "2027-03-22"
summary: >-
  Measured 2026-09-23 with the pinned builds: Claude Code 2.1.274's native record under the ACP adapter
  omits the turn's final API call and its auxiliary title call, while the adapter's prompt response
  carries complete per-model turn usage; for Codex the native record is complete and the adapter
  reports only the last call. Each profile names its authoritative source; the other is a cross-check.
---

# Token totals come from the source that is complete for each harness

- **Kind:** decision (below ADR weight; amends ADR-0008's "native records only").
- **Confidence:** Verified. Same-turn comparisons with the pinned builds on 2026-09-23. The fixtures are in `tests/fixtures/native/*/ok.jsonl` and `tests/fixtures/acp/*-prompt-response.json`.
- **Made during:** `/implement` phase 1, telemetry slice.

## What was measured

| Harness | Native record | Adapter's prompt response (`usage`, `_meta.quota.model_usage`) |
| --- | --- | --- |
| Claude Code 2.1.274 (claude-agent-acp 0.79.0) | 1 call of `claude-sonnet-5`: input 2, cache read 23,729, cache write 9,302, output 116. The final "DONE" call is missing, and so is the `claude-haiku-4-5` title call. The row the record names as the turn's leaf (`leafUuid`) is never written. | `claude-sonnet-5`: input 4, cache read 56,760, cache write 12,297, output 121 (both calls); `claude-haiku-4-5-20251001`: 926 in, 14 out |
| Codex 0.156.0 (codex-acp 1.12.0) | 3 `token_count` events; the final `total_token_usage` is 45,888 input (41,856 cached) + 566 output, the sum of the per-call `last_token_usage` | Only the last call: input 364 uncached, cached 15,232, output 5 |

A graceful exit (stdin closed, the adapter left to exit, 0.2 s) did not change the Claude record, so this is not a lost flush.

## The call

- Each harness profile names `usage_source`: `acp_turn` for Claude Code, `native_record` for Codex.
- The engine records the adapter's prompt response as a `turn_usage` fact. Grain: one model's usage in one turn of one cell. Writer: the engine thread, from the ACP stream, which is archived.
- Token and cost views use the authoritative source. The other source is kept as a cross-check.
- Per-report rows (`model_calls`: one model's usage in one native usage report, with an additive `requests` count; ADR-0006 Amendment 1, ruling R-26) and per-call `tool_calls` rows still come from the native record. For Claude Code and Codex a report is one request; for Copilot it is the per-model entry in the last `session.shutdown` (`usage_source: native_record`, with the ACP `usage` recorded as `acp_usage` for the cross-check, R-24). *(Corrected 2026-09-24 from "Per-call rows", R-26 C1.)*
- The served-model check (US-11) uses the authoritative source. Each profile declares its auxiliary models: `claude-haiku-4-5*` for Claude Code's title generation. A served model that is neither the pin nor declared is `invalid (model mismatch)`.

## Alternatives dismissed

- **Native records only (ADR-0008 as written):** undercounts Claude Code by the final call and every auxiliary call. That is about 40% of this turn's tokens.
- **The adapter's usage for every harness:** for Codex it reports only the last call.

## Validation condition

The choice holds until a harness build changes either source. The profile qualification suite (ADR-0011) re-compares the two sources on a pinned turn for every new build.

## Promotion rule

If a third harness, or a new build, needs its own rule, promote this to an ADR amendment of ADR-0008.
