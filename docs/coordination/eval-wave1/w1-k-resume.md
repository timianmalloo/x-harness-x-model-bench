---
id: coordination-eval-brief-w1-k-resume
title: "W1-K brief: plan-level resume, liveness and the alarm channel (ADR-0021)"
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
  Self-contained Wave 1 dispatch brief (w1-k-resume): session, branch, pinned model, owned paths, inputs, W0 sections,
  gate lenses, budget, exit evidence, fallback and not-in-scope. The launcher passes only this file's path.
---

# W1-K brief: plan-level resume, liveness and the alarm channel (ADR-0021)

**Read first:** `C:\Projects\x-harness-x-model-bench\docs\coordination\eval-wave1\README.md` (the common rules). Then do this brief. Pass nothing else; this file is the whole dispatch.

| field | value |
| --- | --- |
| session | `w1k-resume-e1e4` (`export AGENT_SESSION=w1k-resume-e1e4`) |
| branch / tree | `design/eval-resume` → `C:\Projects\x-harness-x-model-bench-design-eval-resume` |
| model (pinned) | Claude Sonnet `claude-sonnet-5` (Agent tool `model: sonnet`; never a default) |
| first command | `python docs/ai-forward-pack/scripts/audit-log.py start --session w1k-resume-e1e4 --skill design-slice` |
| tier · fan-out cap | T2 · 0 |
| budget | 140 tool calls · 180k tokens · 1 dispatch · 2 h |
| leader epoch | 13 |
| fallback | a fresh session of the same pinned model from this retained brief, after the Coordinator reads your report (resume starts with the `start` line) |

## Goal
Run `/design-slice` for **W1-K plan-level resume, liveness and the alarm channel (ADR-0021)**, producing `docs/design/eval-resume.md`. Follow its flow (`.claude/skills/design-slice/reference/flow.md`, read once at Stage 0). Settle the data model first. Name the patterns past both the Patterns Expert and the Simplifier. Write the E7 surface list, the failure-mode and STRIDE-lite analyses, the telemetry, and the test plan by node id (red-first tests named). Run the spikes the doc's contracts need. Leave the Gate record pending with the reviewers below.

## Done when (the plan row, verbatim)
Gate PASS incl. Distributed Systems and SRE; every ADR-0021 §4 row mapped to a kill-then-resume test; `NoResumeAfterStop` added to the model **after W1-J**, with TLC output; the alarm channel chosen (ADR-0021 §7: "The channel is chosen at `/design-slice`"); the drill is out of scope.

**Convergence condition (enough):** every §4 row has a test node and its recorded cause; TLC output for `NoResumeAfterStop` and its seeded variant is in the doc.

## You own (authored; nothing else)
- `docs/design/eval-resume.md`
- models/run_lifecycle.tla and models/run_lifecycle.*.cfg — only after W1-J's model is on `main`, and only the `NoResumeAfterStop` addition

`docs/docs-index.js`, `docs/audit/audit-log.jsonl` and `docs/audit/change-log.jsonl` are derived or register files: regenerate or append, never claim.

## Inputs (read these; quote what you rely on)
- `docs/design/eval-seam-contracts.md`: §11 HB-CELL-118, HB-CELL-119, HB-RUN-008, HB-RUN-009, HB-ALM-001..003 (and reuse of HB-RUN-004, HB-RUN-005, HB-IDN-001), §12 (the resume record), §13 (E3 owners X-K1, X-K2), §14 (the alarm channel)
- docs/adr/0021-plan-level-resume-and-liveness.md (all); docs/adr/0007 §1, §2, §5; docs/adr/0015 §5a-§7
- W1-J's model on `main` (models/run_lifecycle.tla). If it is not there yet, design §1-§8 first and stop before the model step; report "waiting for W1-J"
- Code: src/harness_bench/engine.py:379-416 (sleep detector, heartbeat, disk floor), oslock.py (heartbeat_age), preflight.py:4, 47, status.py, cli.py

## Gate (lens reviewers; you never clear a veto)
- RV-PAT (Patterns Expert)
- RV-SIM (Simplifier, soft veto)
- RV-TA (Test Architect, **hard veto**)
- RV-DS (Distributed Systems, **hard veto**)
- RV-SRE (SRE)

## Exit evidence (in your 10-line report)
- the commit SHAs on `design/eval-resume`, the doc path, and `docs-graph.py validate` exit 0;
- each "Done when" item above, with where in the doc it is met;
- open decision and seam request ids; spikes run, with results;
- budget used against the budget above.

## Not in scope
the alarm drill acceptance (kickoff Not-in-scope), per-turn engine changes (W1-J), any `src/` code. W0 itself (send a seam request instead). Any hub file. Any merge or push.
