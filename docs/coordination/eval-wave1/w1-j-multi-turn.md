---
id: coordination-eval-brief-w1-j-multi-turn
title: "W1-J brief: multi-turn attempt, turn snapshots and the TLA+ model (ADR-0015)"
type: plan
status: proposed
owner: "@timianmalloo"
phase: "Enterprise evaluation: Wave 1 dispatch"
tags: [coordination, brief, wave-1, evaluation-campaign]
links:
  - { to: coordination-eval-wave1-briefs, rel: implements }
  - { to: design-eval-seam-contracts, rel: depends-on }
review-by: "2026-10-17"
summary: >-
  Self-contained Wave 1 dispatch brief (w1-j-multi-turn): session, branch, pinned model, owned paths, inputs, W0 sections,
  gate lenses, budget, exit evidence, fallback and not-in-scope. The launcher passes only this file's path.
---

# W1-J brief: multi-turn attempt, turn snapshots and the TLA+ model (ADR-0015)

**Read first:** `C:\Projects\x-harness-x-model-bench\docs\coordination\eval-wave1\README.md` (the common rules). Then do this brief. Pass nothing else; this file is the whole dispatch.

| field | value |
| --- | --- |
| session | `w1j-multiturn-e1e4` (`export AGENT_SESSION=w1j-multiturn-e1e4`) |
| branch / tree | `design/eval-multi-turn` → `C:\Projects\x-harness-x-model-bench-design-eval-multi-turn` |
| model (pinned) | Claude Sonnet `claude-sonnet-5` (Agent tool `model: sonnet`; never a default) |
| first command | `python docs/ai-forward-pack/scripts/audit-log.py start --session w1j-multiturn-e1e4 --skill design-slice` |
| tier · fan-out cap | T2 · 0 |
| budget | 180 tool calls · 200k tokens · 2 dispatches (1: the design; 2: the TLA+ model and TLC) · 3 h |
| leader epoch | 13 |
| fallback | a fresh session of the same pinned model from this retained brief, after the Coordinator reads your report (resume starts with the `start` line) |

## Goal
Run `/design-slice` for **W1-J multi-turn attempt, turn snapshots and the TLA+ model (ADR-0015)**, producing `docs/design/eval-multi-turn.md`. Follow its flow (`.claude/skills/design-slice/reference/flow.md`, read once at Stage 0). Settle the data model first. Name the patterns past both the Patterns Expert and the Simplifier. Write the E7 surface list, the failure-mode and STRIDE-lite analyses, the telemetry, and the test plan by node id (red-first tests named). Run the spikes the doc's contracts need. Leave the Gate record pending with the reviewers below.

## Done when (the plan row, verbatim)
Gate PASS incl. Distributed Systems and SRE; **TLC run** with `PromptOncePerTurn`, `SnapshotBeforeNextTurn`, `NoSnapshotInFlight`, `CrashedTurnPredicate`, `ArchiveExistsMeansComplete`, each seeded variant **rejected** (output in the doc).

**Convergence condition (enough):** TLC passes the model with every invariant and rejects each seeded variant, and the output is pasted with its command line.

## You own (authored; nothing else)
- `docs/design/eval-multi-turn.md`
- `models/run_lifecycle.tla`
- `models/run_lifecycle.*.cfg`

`docs/docs-index.js`, `docs/audit/audit-log.jsonl` and `docs/audit/change-log.jsonl` are derived or register files: regenerate or append, never claim.

## Inputs (read these; quote what you rely on)
- `docs/design/eval-seam-contracts.md`: §4 (publish_dir for snapshots), §5 (`tasks.<id>.turns`), §11 HB-LED-008 and HB-CELL-117, §12 (every E2 row), §13 (E2 owners: X-J1), §14 (you name the snapshot folder path)
- docs/adr/0015-multi-turn-attempt-and-turn-snapshots.md (all); docs/adr/0007-deterministic-run-engine.md; docs/adr/0013 §2; docs/adr/0021 §4 (the per-turn rows)
- docs/notes/spike-e4-post-turn-prompt.md
- docs/design/run-lifecycle-model.md (how TLC was run before, and the model's bounds)
- Code: src/harness_bench/driver.py:90-111, 249-313; engine.py:684-760, 800-815; archive.py; lifecycle.py; models/run_lifecycle.tla and its .cfg files

## Gate (lens reviewers; you never clear a veto)
- RV-PAT (Patterns Expert)
- RV-SIM (Simplifier, soft veto)
- RV-TA (Test Architect, **hard veto**)
- RV-DS (Distributed Systems, **hard veto**)
- RV-SRE (SRE)

## Exit evidence (in your 10-line report)
- the commit SHAs on `design/eval-multi-turn`, the doc path, and `docs-graph.py validate` exit 0;
- each "Done when" item above, with where in the doc it is met;
- open decision and seam request ids; spikes run, with results;
- budget used against the budget above.

## Not in scope
resume and `NoResumeAfterStop` (W1-K, after you), the rework grader (W1-L / X-J2), any `src/` code. W0 itself (send a seam request instead). Any hub file. Any merge or push.
