---
id: coordination-eval-brief-w1-a-arms
title: "W1-A brief: arms v2 (ADR-0014)"
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
  Self-contained Wave 1 dispatch brief (w1-a-arms): session, branch, pinned model, owned paths, inputs, W0 sections,
  gate lenses, budget, exit evidence, fallback and not-in-scope. The launcher passes only this file's path.
---

# W1-A brief: arms v2 (ADR-0014)

**Read first:** `C:\Projects\x-harness-x-model-bench\docs\coordination\eval-wave1\README.md` (the common rules). Then do this brief. Pass nothing else; this file is the whole dispatch.

| field | value |
| --- | --- |
| session | `w1a-arms-e1e4` (`export AGENT_SESSION=w1a-arms-e1e4`) |
| branch / tree | `design/eval-arms` → `C:\Projects\x-harness-x-model-bench-design-eval-arms` |
| model (pinned) | Claude Sonnet `claude-sonnet-5` (Agent tool `model: sonnet`; never a default) |
| first command | `python docs/ai-forward-pack/scripts/audit-log.py start --session w1a-arms-e1e4 --skill design-slice` |
| tier · fan-out cap | T2 · 0 |
| budget | 120 tool calls · 180k tokens context ceiling · 1 dispatch · 1.5 h |
| leader epoch | 13 |
| fallback | a fresh session of the same pinned model from this retained brief, after the Coordinator reads your report (resume starts with the `start` line) |

## Goal
Run `/design-slice` for **W1-A arms v2 (ADR-0014)**, producing `docs/design/eval-arms.md`. Follow its flow (`.claude/skills/design-slice/reference/flow.md`, read once at Stage 0). Settle the data model first. Name the patterns past both the Patterns Expert and the Simplifier. Write the E7 surface list, the failure-mode and STRIDE-lite analyses, the telemetry, and the test plan by node id (red-first tests named). Run the spikes the doc's contracts need. Leave the Gate record pending with the reviewers below.

## Done when (the plan row, verbatim)
Gate line with Patterns, Simplifier and Test Architect PASS; the grid-4 re-plan equivalence test (EV-17) specified by node id; the E1 / E3 split stated.

**Convergence condition (enough):** every EV-17 criterion maps to a named test node, and every on/off literal site above maps to an E1 or E3 change.

## You own (authored; nothing else)
- `docs/design/eval-arms.md`

`docs/docs-index.js`, `docs/audit/audit-log.jsonl` and `docs/audit/change-log.jsonl` are derived or register files: regenerate or append, never claim.

## Inputs (read these; quote what you rely on)
- `docs/design/eval-seam-contracts.md`: §5 (bench-matrix/2, bench-plan/2, accessors, label constraint, launch balance), §10 G1 (the pack-reader guard and its E1 allowlist), §11 HB-PLN-001..003, §13 (plan.py, config.py, views.py owners), §14 (label text; whether `full` keeps the property tasks)
- docs/adr/0014-arm-replaces-pack-setting.md (all)
- docs/specs/enterprise-evaluation.md EV-17 (and EV-9, EV-15 for the E3 split)
- docs/architecture-evaluation-campaign.md: component *Arms in the plan*; the E1 and E3 phasing rows
- Code (read, do not edit): src/harness_bench/plan.py:60-130, 272-356; config.py:35, 107-130 (validate_matrix); engine.py:380; board.py:540, 586-620, 769; report/pack_improvement.py:131-132, 995, 1012, 1254; grade/_changes.py:84; report/html.py:265-288; views.py:525
- runs/grid-4/matrix.yaml and runs/grid-4/plan.json in the primary checkout (local, git-ignored; read only)
- docs/notes/rulings.md R-88 (X-A1's route) and R-89 (the E1 pilot ring: arms `off`, `candidate`; combo `cc-opus`, k = 3)

## Gate (lens reviewers; you never clear a veto)
- RV-PAT (Patterns Expert)
- RV-SIM (Simplifier, soft veto)
- RV-TA (Test Architect, **hard veto**)

## Exit evidence (in your 10-line report)
- the commit SHAs on `design/eval-arms`, the doc path, and `docs-graph.py validate` exit 0;
- each "Done when" item above, with where in the doc it is met;
- open decision and seam request ids; spikes run, with results;
- budget used against the budget above.

## Not in scope
the campaign block's content (W1-C), calibration marking (E3), ring-hash refusal logic beyond naming it (E3, X-A3), any code. W0 itself (send a seam request instead). Any hub file. Any merge or push.
