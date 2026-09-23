---
id: "adr-0008-telemetry"
title: "ADR-0008: Usage telemetry comes from each cell's archived native session record"
type: adr
status: draft
owner: "@timianmalloo"
phase: "all phases"
tags: [benchmark, telemetry, cost]
links:
  - { to: arch-harness-bench, rel: refines }
  - { to: spec-harness-bench, rel: implements }
  - { to: note-spike-runner-path, rel: depends-on }
review-by: "2027-09-23"
summary: >-
  After a cell ends, the harness's native session record in the cell's own home is archived and
  hashed, then normalised into model_calls rows with OpenTelemetry GenAI attribute names. No OTel
  collector runs in v0.
---

# ADR-0008: Usage telemetry comes from each cell's archived native session record

- **Status:** Proposed. Supersedes the proposal's "OTel collector as telemetry sink".
- **Date:** 2026-09-23 (revised after council round 1)
- **Deciders:** @timianmalloo; authored by Claude Code for the architect council
- **Context spec/architecture:** `docs/specs/harness-bench.md` US-22–US-24

## Context

The spikes showed the following:
- The ACP transport returns no usage (spike 1.2).
- Each harness's native record holds per-call tokens by type, model and timing:
  - Claude: `projects/<slug>/<session>.jsonl`;
  - Codex: the `sessions/…/rollout-*.jsonl` file;
  - Copilot: `session-store.db` `assistant_usage_events`, with a native AI-unit price per token type.
- With per-cell homes (ADR-0003), these records land in the cell's own home (R1.2, R11.2).

The proposal's OTel sink is uneven: Codex exec OTel metrics were reported missing, and Copilot has no OTel export (proposal, cited issues).

## Decision

When a cell ends:
1. The run engine archives the cell home's native records, excluding the credential, and records each file's hash (US-19).
2. One reader per harness profile parses only the record whose session id matches the cell's ACP session id (US-22).
3. The normaliser (an Anti-Corruption Layer into a Canonical Data Model) writes `model_calls` and `tool_calls` rows (ADR-0006) using OpenTelemetry GenAI semantic-convention names (`gen_ai.request.model`, `gen_ai.response.model`, `gen_ai.usage.*`). It converts each harness's token fields into **disjoint buckets** (uncached input, cache read, cache write, output, with reasoning as a component of output), because the harnesses define input differently [Verified in spike records]. It keys each call by native session id and native ordinal: a cell can hold several sessions (sub-agents). A field the harness does not report is NOT_RECORDED with the reason.
4. The coordinator session's own native record is read the same way at run end, as principal `coordinator` (US-17).

The pack's `session-profile.py` is reused for the Claude and Copilot parsing where it accepts a record path. Otherwise the bench reader follows its field mapping (S-07).

## Alternatives considered

- **An OTel collector receiving live telemetry:** rejected for v0. Coverage is uneven across harnesses, it adds a service, and native records already carry the fields. It can be revisited if a harness's record drops a field its OTel export has.
- **Headless JSON summaries (`claude -p --output-format json`, `codex exec --json`):** not available on the chosen ACP path (ADR-0002).

## Consequences

- **Positive:**
  - One post-hoc, archived, hashable source per cell.
  - Re-grading re-reads the archive.
  - No live service.
- **Negative / accepted trade-offs:**
  - Record formats are undocumented and change between CLI builds. Each reader is pinned to the profile's CLI build and has a fixture test from a real record.
- **Follow-ups / new risks:**
  - Reader fixtures from the spike records (Claude, Codex, Copilot).
  - Model, tool and idle time fields per harness (US-24), mapped in S-07.

## Evidence

- `docs/notes/spike-runner-path.md` 1.2 [Verified].
- `docs/notes/spike-isolation-permissions.md` R1.2, R11.2 [Verified].
