---
id: "rulings-register"
title: "Owner rulings"
type: decision-note
status: accepted
owner: "@timianmalloo"
phase: "Phase 1 · walking skeleton"
tags: [rulings, register, coordination]
links:
  - { to: coordination-phase1-finish, rel: relates-to }
review-by: "2027-03-22"
summary: >-
  The append-only register of Owner rulings (class `register`, union-merged). Each entry records the ruling verbatim
  or its chosen option, who ruled, when, and what it decided.
---

# Owner rulings

Append only. One entry per ruling. Newest last.

## R-1 · 2026-09-24 · Owner (Tim Mallalieu) · sub-agent harnesses and seats

> "use grok, and agy for sub agent tasks · use the Owner (fable), Coordinator (opus 5.5), Sub.Agent (right model for the right job and delegate to instances of grok and agy)"

- **Decides:** the sub-agents of `coordination-phase1-finish` run on grok and agy; the Owner seat is Fable, and the Coordinator seat is Opus 5.5.
- **Recorded dissent** (Tech Lead, Simplifier): run the critical-path track on Claude Code, the only harness whose edit boundary is qualified here.
- **Resolution:** the plan keeps R-1 and moves a track to Claude Code only if its harness fails qualification or the track stalls.
- **Also ruled (same message):** grok runs on the Owner's subscription, not an API key. Every grok worker is launched with `XAI_API_KEY` removed; checked: "You are logged in with grok.com".

## R-2 · 2026-09-24 · Owner seat (Fable) · `grading.completed` carries its heads

- **Ruling:** (a) yes, as stated. `verify` checks each segment's own chain and seal, but nothing ties a later `bench grade` pass's scores segment to its `grading.completed`. So a scores segment that was cut and re-sealed, or deleted, is invisible. The runner already computes `heads` for its facts and discards them; recording them is the minimal mechanism.
- **Conditions:**
  - `heads` excludes `events`, since a segment cannot carry its own head.
  - A `grading.completed` without `heads` (the `c44dd2b` golden fixture) verifies with a warning, never an error.
  - A missing or mismatched head is exit 5.

## R-3 · 2026-09-24 · Owner seat (Fable) · `bench-status/1` gains `stop_code` and a `phase`

- **Ruling:** (a) yes, and the schema stays `bench-status/1`. The producer (`status.py`) and the only consumer (`skills/start-benchmark/SKILL.md`) live in this repo and move in one change, and nothing stores a status document.
- **Conditions:**
  - `stop_code` is null unless `run.launch_stopped` was recorded.
  - `phase` is a closed enum (`starting`, `running`).
  - The skill's field list and reading rules update in the same commit.
  - If a status document is ever stored or consumed outside the repo, that change bumps the schema to `/2`.

## R-4 · 2026-09-24 · Owner seat (Fable) · sub-agents fall back to Claude Code

- **Ruling:** (a) apply R-1's recorded fallback now, for every track. Both qualification failures were measured on this host (run `qualify-1`):
  - grok 1.0.30: ACP `protocol_error` on the first prompt, 0 turns. The runner's compatibility path targets grok 1.0.34.
  - agy 1.2.3: a native permission denial on the first turn in `accept-edits` mode, 0 turns.

  Option (b), upgrading grok, would alter the operator's machine unattended; option (c), waiting, forfeits the deadline.
- **Conditions:**
  - The Coordinator records each move with the measured evidence.
  - Nobody widens agy's permission mode or upgrades grok while the human is offline. Both are listed as next steps for the human, and R-1 stands for re-qualification when they return.
