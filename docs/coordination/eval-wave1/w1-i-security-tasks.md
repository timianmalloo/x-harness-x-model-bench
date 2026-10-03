---
id: coordination-eval-brief-w1-i-security-tasks
title: "W1-I brief: security tasks S1 and S2 (task design)"
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
  Self-contained Wave 1 dispatch brief (w1-i-security-tasks): session, branch, pinned model, owned paths, inputs, W0 sections,
  gate lenses, budget, exit evidence, fallback and not-in-scope. The launcher passes only this file's path.
---

# W1-I brief: security tasks S1 and S2 (task design)

**Read first:** `C:\Projects\x-harness-x-model-bench\docs\coordination\eval-wave1\README.md` (the common rules). Then do this brief. Pass nothing else; this file is the whole dispatch.

| field | value |
| --- | --- |
| session | `w1i-security-e1e4` (`export AGENT_SESSION=w1i-security-e1e4`) |
| branch / tree | `design/eval-security-tasks` → `C:\Projects\x-harness-x-model-bench-design-eval-security-tasks` |
| model (pinned) | Claude Sonnet `claude-sonnet-5` (Agent tool `model: sonnet`; never a default) |
| first command | `python docs/ai-forward-pack/scripts/audit-log.py start --session w1i-security-e1e4 --skill design-slice` |
| tier · fan-out cap | T2 · 0 |
| budget | 140 tool calls · 180k tokens · 1 dispatch · 2 h |
| leader epoch | 13 |
| fallback | a fresh session of the same pinned model from this retained brief, after the Coordinator reads your report (resume starts with the `start` line) |

## Goal
Run `/design-slice` for **W1-I security tasks S1 and S2 (task design)**, producing `docs/design/eval-security-tasks.md`. Follow its flow (`.claude/skills/design-slice/reference/flow.md`, read once at Stage 0). Settle the data model first. Name the patterns past both the Patterns Expert and the Simplifier. Write the E7 surface list, the failure-mode and STRIDE-lite analyses, the telemetry, and the test plan by node id (red-first tests named). Run the spikes the doc's contracts need. Leave the Gate record pending with the reviewers below.

## Done when (the plan row, verbatim)
Gate PASS incl. Security; two real codebases on different bases (DR-T1); the latent requirement; in-process probes (injection, authz bypass, secret leak with a `BENCHCANARY-` value); reference and naive solutions; expected values with provenance (GLD-A).

**Convergence condition (enough):** S1 is specified to the point that X-I can author it without a question; S2's base and probes are named.

## You own (authored; nothing else)
- `docs/design/eval-security-tasks.md`

`docs/docs-index.js`, `docs/audit/audit-log.jsonl` and `docs/audit/change-log.jsonl` are derived or register files: regenerate or append, never claim.

## Inputs (read these; quote what you rely on)
- `docs/design/eval-seam-contracts.md`: §1 (ids, scenario 5, budgets), §2 (every property field), §3 (the check contract; E1 is in-process only)
- docs/specs/enterprise-evaluation.md EV-1, EV-2, EV-7; decisions DR-T1 and DR-E6 (two codebases)
- docs/adr/0018-hidden-check-harness.md §2-§4, §7, §9 (canaries `BENCHCANARY-<task>-<hex>`, the egress `task canary` class)
- tasks/README.md (the Property tasks section), tasks/S1/task.yaml and tasks/S2/task.yaml (the stubs), a precedent oracle: tasks/D2/oracle/evidence.md
- docs/lessons/defect-classes.md: GLD-A, HASH-A, ORCL-A

## Gate (lens reviewers; you never clear a veto)
- RV-PAT (Patterns Expert)
- RV-SIM (Simplifier, soft veto)
- RV-TA (Test Architect, **hard veto**)
- RV-SEC (Security & Identity, **hard veto**)

## Exit evidence (in your 10-line report)
- the commit SHAs on `design/eval-security-tasks`, the doc path, and `docs-graph.py validate` exit 0;
- each "Done when" item above, with where in the doc it is met;
- open decision and seam request ids; spikes run, with results;
- budget used against the budget above.

## Not in scope
authoring tasks/S1/** or tasks/S2/** (Wave 2, X-I), the runner (W1-F), any code. W0 itself (send a seam request instead). Any hub file. Any merge or push.
