---
id: coordination-eval-brief-w1-h-power-verdicts
title: "W1-H brief: power, verdicts, dominance, ring gates and report section 3"
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
  Self-contained Wave 1 dispatch brief (w1-h-power-verdicts): session, branch, pinned model, owned paths, inputs, W0 sections,
  gate lenses, budget, exit evidence, fallback and not-in-scope. The launcher passes only this file's path.
---

# W1-H brief: power, verdicts, dominance, ring gates and report section 3

**Read first:** `C:\Projects\x-harness-x-model-bench\docs\coordination\eval-wave1\README.md` (the common rules). Then do this brief. Pass nothing else; this file is the whole dispatch.

| field | value |
| --- | --- |
| session | `w1h-power-e1e4` (`export AGENT_SESSION=w1h-power-e1e4`) |
| branch / tree | `design/eval-power-verdicts` → `C:\Projects\x-harness-x-model-bench-design-eval-power-verdicts` |
| model (pinned) | Claude Sonnet `claude-sonnet-5` (Agent tool `model: sonnet`; never a default) |
| first command | `python docs/ai-forward-pack/scripts/audit-log.py start --session w1h-power-e1e4 --skill design-slice` |
| tier · fan-out cap | T2 · 0 |
| budget | 120 tool calls · 180k tokens · 1 dispatch · 1.5 h |
| leader epoch | 13 |
| fallback | a fresh session of the same pinned model from this retained brief, after the Coordinator reads your report (resume starts with the `start` line) |

## Goal
Run `/design-slice` for **W1-H power, verdicts, dominance, ring gates and report section 3**, producing `docs/design/eval-power-verdicts.md`. Follow its flow (`.claude/skills/design-slice/reference/flow.md`, read once at Stage 0). Settle the data model first. Name the patterns past both the Patterns Expert and the Simplifier. Write the E7 surface list, the failure-mode and STRIDE-lite analyses, the telemetry, and the test plan by node id (red-first tests named). Run the spikes the doc's contracts need. Leave the Gate record pending with the reviewers below.

## Done when (the plan row, verbatim)
Gate PASS; reference cases 93 / 53 / 115 with the independent formula and the seeded-wrong variant; the verdict and dominance tables with boundary rows; section 3's E1 shape.

**Convergence condition (enough):** every EV-12/18/19 reference case and boundary row is a named test with its tolerance.

## You own (authored; nothing else)
- `docs/design/eval-power-verdicts.md`

`docs/docs-index.js`, `docs/audit/audit-log.jsonl` and `docs/audit/change-log.jsonl` are derived or register files: regenerate or append, never claim.

## Inputs (read these; quote what you rely on)
- `docs/design/eval-seam-contracts.md`: §6 (prereg fields incl. `min_pairs`), §8 (the power, verdict and gate signatures), §11 HB-PWR-001, §13 (report/html.py owner X-H2 in E1)
  - **W0 revision 2 changes these inputs:** §8: `verdict` sorts pairs by `(task, rep)`; `seed_for(prereg_hash, …)` replaces the plan's `launch_seed` as the verdict seed; `VerdictLabel(StrEnum)`; `Pair` is Decimal only; `required_pairs` is a list of rows; `gates.pilot(view, hidden_test_disagreements)` and the GateItem kind `hidden-tests-nondeterministic`.
- docs/adr/0020-power-and-verdicts-stdlib.md (all)
- docs/specs/enterprise-evaluation.md EV-12, EV-14, EV-15, EV-18, EV-19, EV-20 and *Power-analysis inputs* (line 439 on)
- Code: src/harness_bench/stats.py (rng, paired bootstrap), report/html.py (section hooks), report/pack_improvement.py (the existing task-paired bootstrap)
- docs/notes/rulings.md R-89 (E1 demo: k = 3, minimum recorded pairs ≤ 3, expected `inconclusive (underpowered)`)

## Gate (lens reviewers; you never clear a veto)
- RV-PAT (Patterns Expert)
- RV-SIM (Simplifier, soft veto)
- RV-TA (Test Architect, **hard veto**)

## Exit evidence (in your 10-line report)
- the commit SHAs on `design/eval-power-verdicts`, the doc path, and `docs-graph.py validate` exit 0;
- each "Done when" item above, with where in the doc it is met;
- open decision and seam request ids; spikes run, with results;
- budget used against the budget above.

## Not in scope
the campaign ledger (W1-C), eligibility computation (W1-D), any code. W0 itself (send a seam request instead). Any hub file. Any merge or push.
