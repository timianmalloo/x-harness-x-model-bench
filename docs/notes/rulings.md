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
