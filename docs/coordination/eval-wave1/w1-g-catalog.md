---
id: coordination-eval-brief-w1-g-catalog
title: "W1-G brief: catalog 0.7 (ADR-0019), scenario-7 pass@1 and the missing-pass@1 fix"
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
  Self-contained Wave 1 dispatch brief (w1-g-catalog): session, branch, pinned model, owned paths, inputs, W0 sections,
  gate lenses, budget, exit evidence, fallback and not-in-scope. The launcher passes only this file's path.
---

# W1-G brief: catalog 0.7 (ADR-0019), scenario-7 pass@1 and the missing-pass@1 fix

**Read first:** `C:\Projects\x-harness-x-model-bench\docs\coordination\eval-wave1\README.md` (the common rules). Then do this brief. Pass nothing else; this file is the whole dispatch.

| field | value |
| --- | --- |
| session | `w1g-catalog-e1e4` (`export AGENT_SESSION=w1g-catalog-e1e4`) |
| branch / tree | `design/eval-catalog-0-7` → `C:\Projects\x-harness-x-model-bench-design-eval-catalog-0-7` |
| model (pinned) | Claude Sonnet `claude-sonnet-5` (Agent tool `model: sonnet`; never a default) |
| first command | `python docs/ai-forward-pack/scripts/audit-log.py start --session w1g-catalog-e1e4 --skill design-slice` |
| tier · fan-out cap | T2 · 0 |
| budget | 90 tool calls · 150k tokens · 1 dispatch · 1 h |
| leader epoch | 13 |
| fallback | a fresh session of the same pinned model from this retained brief, after the Coordinator reads your report (resume starts with the `start` line) |

## Goal
Run `/design-slice` for **W1-G catalog 0.7 (ADR-0019), scenario-7 pass@1 and the missing-pass@1 fix**, producing `docs/design/eval-catalog-0-7.md`. Follow its flow (`.claude/skills/design-slice/reference/flow.md`, read once at Stage 0). Settle the data model first. Name the patterns past both the Patterns Expert and the Simplifier. Write the E7 surface list, the failure-mode and STRIDE-lite analyses, the telemetry, and the test plan by node id (red-first tests named). Run the spikes the doc's contracts need. Leave the Gate record pending with the reviewers below.

## Done when (the plan row, verbatim)
Gate PASS; the ten metric entries with anchors (R-79 forms); the scenario-7 pass rule for G2; the US-4 control; the append-only `corrected_from` record. (W0 §7: the entries are eleven.)

**Convergence condition (enough):** all eleven entries are written out in full YAML in the doc, each anchor in one R-79 form.

## You own (authored; nothing else)
- `docs/design/eval-catalog-0-7.md`

`docs/docs-index.js`, `docs/audit/audit-log.jsonl` and `docs/audit/change-log.jsonl` are derived or register files: regenerate or append, never claim.

## Inputs (read these; quote what you rely on)
- `docs/design/eval-seam-contracts.md`: §2 (the `expected` format), §7 (the eleven ids, kind, better, scale, property tag; **DR-4 provisional (a)**), §13 (bench/metrics.yaml owner X-G1, then X-G3)
- docs/adr/0019-catalog-0-7-property-metrics.md (all)
- docs/specs/enterprise-evaluation.md EV-10, EV-11 and the EV-2..EV-6 secondaries
- bench/metrics.yaml (0.6, its header rules), bench/catalog-freeze.yaml, tools/freeze_catalog.py
- Code: report/pack_improvement.py:1173-1175 (`_passed`), grade/formal.py, tasks/G2/task.yaml
- docs/notes/rulings.md R-59, R-79, R-86 (catalog version and anchor rules)

## Gate (lens reviewers; you never clear a veto)
- RV-PAT (Patterns Expert)
- RV-SIM (Simplifier, soft veto)
- RV-TA (Test Architect, **hard veto**)

## Exit evidence (in your 10-line report)
- the commit SHAs on `design/eval-catalog-0-7`, the doc path, and `docs-graph.py validate` exit 0;
- each "Done when" item above, with where in the doc it is met;
- open decision and seam request ids; spikes run, with results;
- budget used against the budget above.

## Not in scope
the property grader's internals (W1-F), any code. W0 itself (send a seam request instead). Any hub file. Any merge or push.
