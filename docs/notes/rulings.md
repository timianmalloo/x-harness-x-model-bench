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

## R-5 · 2026-09-24 · Owner seat (Fable) · N5: disclose, flag and keep the strict xfail

- **Ruling:** (a) keep `xfail(strict)`, record the contamination in the Proof Pack, and flag Codex cells `user-config exposed (N5)`.
- **Reasoning:** three independent attempts fail identically:
  - a per-cell `USERPROFILE`/`HOME`;
  - Codex's `skip_host_skill_discovery` flag;
  - a third party's four-flag set on 0.154.

  So a fourth guess is not evidence. The leak is one skill and is identical for pack on and off, so pack comparisons stay valid, and only Codex-against-Claude harness comparisons carry a disclosed confound.
- **Conditions:**
  1. The flag appears in the report header of every run with a Codex cell, and on each Codex row or cell in the harness-comparison view. The leaked skill (`microsoft-foundry`) is named as the evidence.
  2. The `xfail` reason cites `docs/notes/spike-n5-codex-skill-roots.md`.
  3. N5 reopens on any of these:
     - the Windows known-folder probe (the note's "cheapest next probe") lands;
     - Codex's version changes;
     - a second leaked item appears in the canary;
     - the strict xfail goes green (a fix to verify).
  4. No ADR-0013 amendment.
- **Coordinator's implementation note:** the report names the spike note and the canary as the evidence. The leaked skill's name, which is specific to this operator's profile, is recorded in the Proof Pack rather than hard-coded in the report source.

## R-6 · 2026-09-24 · Owner seat (Fable) · R-5 re-review: N4 (pack-on/off claim) and N5 (skill name)

- **Ruling:**
  - **N4: amend R-5's reasoning by reference.** The sentence "the leak is identical for pack on and off, so pack comparisons stay valid" is **Inferred**, not Verified. It must not be stated as fact anywhere. The pack-seeded probe is a **named, dated next step, not a merge gate**.
  - **N5: accept the Coordinator's implementation** of condition 1.
- **Reasoning:**
  - **N4:**
    - The canary's probe is always a bare cell (`test_us13_canary.py:59-60`: `seed_home` and an empty pack argument), so pack-on was never measured.
    - The inference rests on a mechanism: the leak is `~/.agents/skills`, resolved from the operator's `USERPROFILE`, a path the pack does not touch. That is a model. The `<recommended_plugins>` block seen only in the pack-on Codex context is one observed difference between the two contexts, and its source is unverified.
    - So the claim keeps its model, gains its label, and names the probe that would confirm or break it.
    - The merge is not blocked. The report already flags every Codex cell, pack on or off, so no unflagged comparison reaches a reader. The probe is one extra canary turn, and the benchmark is wanted today.
  - **N5:**
    - The report is an operator-independent surface. An operator's skill name belongs in the run's proof record, not in source.
    - `report/__init__.py` names the note and the canary, and `docs/proof/phase1.md` Claim 5 names `microsoft-foundry`. That satisfies condition 1's intent: the evidence is findable from the flag.
    - One gap: the canary prints leaked *classes* only (`sorted(leaked.values())`). The name in the Proof Pack was transcribed by hand from a pytest introspection line; the measurement did not emit it (IO: emitted on the normal path).
- **Conditions:**
  1. Before merge, `docs/proof/phase1.md` Claim 5 splits its confidence:
     - the leak's existence is **Verified**;
     - pack-invariance is **Inferred**. The model: the leak path is profile-resolved and pack-independent. The probe: run the US-13 canary with the pack seeded into the probe cell, pack on and pack off, and compare the leaked sets;
     - `<recommended_plugins>` is **Flagged** (source unverified, seen pack-on only).

     Any other surface that repeats the pack-invariance claim carries the same label.
  2. The pack-seeded probe joins the human's list beside "N5 review (2)". **R-5 reopens** if either of these happens (add both to R-5 condition 3 by reference):
     - a pack-on leaked set differs from the pack-off set;
     - `<recommended_plugins>` turns out to have a pack-dependent source.
  3. The canary's `Leaked` message and its printed summary name the leaked items (the canary keys), not only their classes. Then the Proof Pack's skill name is copied from a measurement.
  4. R-5 condition 1 is read as: the flag names where the evidence is (the note and the canary), and the run's Proof Pack names the observed item. No skill name goes in report source.
