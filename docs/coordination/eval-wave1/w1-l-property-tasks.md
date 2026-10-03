---
id: coordination-eval-brief-w1-l-property-tasks
title: "W1-L brief: the remaining property tasks: resilience, rework, no-guessing, simplicity (×2 each)"
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
  Self-contained Wave 1 dispatch brief (w1-l-property-tasks): session, branch, pinned model, owned paths, inputs, W0 sections,
  gate lenses, budget, exit evidence, fallback and not-in-scope. The launcher passes only this file's path.
---

# W1-L brief: the remaining property tasks: resilience, rework, no-guessing, simplicity (×2 each)

**Read first:** `C:\Projects\x-harness-x-model-bench\docs\coordination\eval-wave1\README.md` (the common rules). Then do this brief. Pass nothing else; this file is the whole dispatch.

| field | value |
| --- | --- |
| session | `w1l-tasks-e1e4` (`export AGENT_SESSION=w1l-tasks-e1e4`) |
| branch / tree | `design/eval-property-tasks` → `C:\Projects\x-harness-x-model-bench-design-eval-property-tasks` |
| model (pinned) | Claude Sonnet `claude-sonnet-5` (Agent tool `model: sonnet`; never a default) |
| first command | `python docs/ai-forward-pack/scripts/audit-log.py start --session w1l-tasks-e1e4 --skill design-slice` |
| tier · fan-out cap | T2 · 0 |
| budget | 160 tool calls · 200k tokens · 2 dispatches (1: resilience + rework; 2: no-guessing + simplicity) · 3 h |
| leader epoch | 13 |
| fallback | a fresh session of the same pinned model from this retained brief, after the Coordinator reads your report (resume starts with the `start` line) |

## Goal
Run `/design-slice` for **W1-L the remaining property tasks: resilience, rework, no-guessing, simplicity (×2 each)**, producing `docs/design/eval-property-tasks.md`. Follow its flow (`.claude/skills/design-slice/reference/flow.md`, read once at Stage 0). Settle the data model first. Name the patterns past both the Patterns Expert and the Simplifier. Write the E7 surface list, the failure-mode and STRIDE-lite analyses, the telemetry, and the test plan by node id (red-first tests named). Run the spikes the doc's contracts need. Leave the Gate record pending with the reviewers below.

## Done when (the plan row, verbatim)
Gate PASS; for resilience ×2, no-guessing ×2, simplicity ×2 and rework ×2: base codebase, latent requirement, hidden check, reference and naive, expected values; which graders are new (`verified_before_use`, `hallucinated_symbol_errors`, diff statistics).

**Convergence condition (enough):** each of the eight tasks has every W0 §2 field filled or marked with the design question that blocks it.

## You own (authored; nothing else)
- `docs/design/eval-property-tasks.md`

`docs/docs-index.js`, `docs/audit/audit-log.jsonl` and `docs/audit/change-log.jsonl` are derived or register files: regenerate or append, never claim.

## Inputs (read these; quote what you rely on)
- `docs/design/eval-seam-contracts.md`: §1, §2, §3, §7 (DR-4 provisional (a): the strategy helpers `grade/rework.py`, `grade/noguess.py`, `grade/diffstats.py` named in §9)
- docs/specs/enterprise-evaluation.md EV-1, EV-3, EV-4, EV-5, EV-6, EV-7; decisions DR-T1, DR-E4, DR-E6
- docs/adr/0015 §1, §8 (turns, graded snapshots); docs/adr/0018 §3 (loopback, after SP-LB), §5, §6; docs/adr/0019 item 2
- tasks/README.md (Property tasks), the eight stubs tasks/{RS1,RS2,RW1,RW2,NG1,NG2,SM1,SM2}/task.yaml
- Code: grade/process.py and grade/_changes.py (tool-call order, diff and scope_creep: EV-6 forbids counting a line twice)

## Gate (lens reviewers; you never clear a veto)
- RV-PAT (Patterns Expert)
- RV-SIM (Simplifier, soft veto)
- RV-TA (Test Architect, **hard veto**)

## Exit evidence (in your 10-line report)
- the commit SHAs on `design/eval-property-tasks`, the doc path, and `docs-graph.py validate` exit 0;
- each "Done when" item above, with where in the doc it is met;
- open decision and seam request ids; spikes run, with results;
- budget used against the budget above.

## Not in scope
authoring tasks/**, the runner (W1-F), the loopback fake harness itself (X-LB), any code. W0 itself (send a seam request instead). Any hub file. Any merge or push.
