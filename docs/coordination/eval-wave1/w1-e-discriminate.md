---
id: coordination-eval-brief-w1-e-discriminate
title: "W1-E brief: discriminate, synthetic profile and readiness (EV-7)"
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
  Self-contained Wave 1 dispatch brief (w1-e-discriminate): session, branch, pinned model, owned paths, inputs, W0 sections,
  gate lenses, budget, exit evidence, fallback and not-in-scope. The launcher passes only this file's path.
---

# W1-E brief: discriminate, synthetic profile and readiness (EV-7)

**Read first:** `C:\Projects\x-harness-x-model-bench\docs\coordination\eval-wave1\README.md` (the common rules). Then do this brief. Pass nothing else; this file is the whole dispatch.

| field | value |
| --- | --- |
| session | `w1e-discrim-e1e4` (`export AGENT_SESSION=w1e-discrim-e1e4`) |
| branch / tree | `design/eval-discriminate` → `C:\Projects\x-harness-x-model-bench-design-eval-discriminate` |
| model (pinned) | Claude Sonnet `claude-sonnet-5` (Agent tool `model: sonnet`; never a default) |
| first command | `python docs/ai-forward-pack/scripts/audit-log.py start --session w1e-discrim-e1e4 --skill design-slice` |
| tier · fan-out cap | T2 · 0 |
| budget | 130 tool calls · 180k tokens · 1 dispatch · 1.5 h |
| leader epoch | 13 |
| fallback | a fresh session of the same pinned model from this retained brief, after the Coordinator reads your report (resume starts with the `start` line) |

## Goal
Run `/design-slice` for **W1-E discriminate, synthetic profile and readiness (EV-7)**, producing `docs/design/eval-discriminate.md`. Follow its flow (`.claude/skills/design-slice/reference/flow.md`, read once at Stage 0). Settle the data model first. Name the patterns past both the Patterns Expert and the Simplifier. Write the E7 surface list, the failure-mode and STRIDE-lite analyses, the telemetry, and the test plan by node id (red-first tests named). Run the spikes the doc's contracts need. Leave the Gate record pending with the reviewers below.

## Done when (the plan row, verbatim)
Gate PASS incl. Security; the SCAN-A red fixture named; the synthetic agent mechanism (a stdlib ACP fake behind `Launcher`, so no `engine.py` edit, Inferred; an engine edit is a seam request to X-D).

**Convergence condition (enough):** each EV-7 bullet maps to a readiness item, an HB-RDY code and a test node.

## You own (authored; nothing else)
- `docs/design/eval-discriminate.md`

`docs/docs-index.js`, `docs/audit/audit-log.jsonl` and `docs/audit/change-log.jsonl` are derived or register files: regenerate or append, never claim.

## Inputs (read these; quote what you rely on)
- `docs/design/eval-seam-contracts.md`: §2 (task.yaml property and expected fields), §6 (the discrimination record and the synthetic profile), §9 (discriminate.py, readiness.py, synthetic_agent.py), §11 HB-RDY-001..009, §13 (profiles.py owner X-E; config.py and `HARNESSES` by seam to X-A1), §14 (the synthetic agent mechanism)
- docs/adr/0016-campaign-record.md §4-§5; docs/adr/0019-catalog-0-7-property-metrics.md item 5
- docs/specs/enterprise-evaluation.md EV-1, EV-7, EV-11
- docs/lessons/defect-classes.md: ORCL-A, ORCL-B, HASH-A, SCAN-A, GLD-A
- Code: src/harness_bench/engine.py:69-85 (the `Launcher` protocol), profiles.py, workspace.py (task_source, cell_working_copy), config.py (validate_task), bench/profiles/*.yaml

## Gate (lens reviewers; you never clear a veto)
- RV-PAT (Patterns Expert)
- RV-SIM (Simplifier, soft veto)
- RV-TA (Test Architect, **hard veto**)
- RV-SEC (Security & Identity, **hard veto**)

## Exit evidence (in your 10-line report)
- the commit SHAs on `design/eval-discriminate`, the doc path, and `docs-graph.py validate` exit 0;
- each "Done when" item above, with where in the doc it is met;
- open decision and seam request ids; spikes run, with results;
- budget used against the budget above.

## Not in scope
the hidden-check runner (W1-F), the task content (W1-I, W1-L), any code. W0 itself (send a seam request instead). Any hub file. Any merge or push.
