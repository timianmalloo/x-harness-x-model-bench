---
id: coordination-eval-brief-w1-d-identity
title: "W1-D brief: engine identity, freeze and per-launch recheck"
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
  Self-contained Wave 1 dispatch brief (w1-d-identity): session, branch, pinned model, owned paths, inputs, W0 sections,
  gate lenses, budget, exit evidence, fallback and not-in-scope. The launcher passes only this file's path.
---

# W1-D brief: engine identity, freeze and per-launch recheck

**Read first:** `C:\Projects\x-harness-x-model-bench\docs\coordination\eval-wave1\README.md` (the common rules). Then do this brief. Pass nothing else; this file is the whole dispatch.

| field | value |
| --- | --- |
| session | `w1d-identity-e1e4` (`export AGENT_SESSION=w1d-identity-e1e4`) |
| branch / tree | `design/eval-identity` → `C:\Projects\x-harness-x-model-bench-design-eval-identity` |
| model (pinned) | Claude Sonnet `claude-sonnet-5` (Agent tool `model: sonnet`; never a default) |
| first command | `python docs/ai-forward-pack/scripts/audit-log.py start --session w1d-identity-e1e4 --skill design-slice` |
| tier · fan-out cap | T2 · 0 |
| budget | 110 tool calls · 150k tokens · 1 dispatch · 1.5 h |
| leader epoch | 13 |
| fallback | a fresh session of the same pinned model from this retained brief, after the Coordinator reads your report (resume starts with the `start` line) |

## Goal
Run `/design-slice` for **W1-D engine identity, freeze and per-launch recheck**, producing `docs/design/eval-identity.md`. Follow its flow (`.claude/skills/design-slice/reference/flow.md`, read once at Stage 0). Settle the data model first. Name the patterns past both the Patterns Expert and the Simplifier. Write the E7 surface list, the failure-mode and STRIDE-lite analyses, the telemetry, and the test plan by node id (red-first tests named). Run the spikes the doc's contracts need. Leave the Gate record pending with the reviewers below.

## Done when (the plan row, verbatim)
Gate PASS incl. SRE; the run / grade classification table reviewed (ADR-0017 follow-up "load-bearing"); the launch recheck and `identity_check_ms`.

**Convergence condition (enough):** every existing `src/` file and every W0 §9 module has a class with a one-line reason, and the drift test is named.

## You own (authored; nothing else)
- `docs/design/eval-identity.md`

`docs/docs-index.js`, `docs/audit/audit-log.jsonl` and `docs/audit/change-log.jsonl` are derived or register files: regenerate or append, never claim.

## Inputs (read these; quote what you rely on)
- `docs/design/eval-seam-contracts.md`: §6 (the identity API and the launch recheck), §9 (**review the whole run/grade table**: ADR-0017 calls it load-bearing), §10 G2 and G3, §11 HB-IDN-001..002, §12 (`run.launch_stopped`, `identity_check_ms`), §13 (engine.py, errors.py, identity.py, tests/test_architecture.py owner X-D), §14 (whether `grade_identity_hash` lands in E1 or E3)
  - **W0 revision 2 changes these inputs:** §9: the class rule is refined; `discriminate.py` and `synthetic_agent.py` are now grade; no run-class module imports a grade-class one; you rule on the cost of the grade-class tooling modules (§14). §10 G3: imports are resolved through the AST resolver; `bench_check.py` imports stdlib only. §6: `platform` = `sys.platform`.
- docs/adr/0017-engine-identity-and-freeze.md (all); docs/adr/0011-loa-conformance-in-python.md Amendment 1 (the import lint)
- docs/architecture-evaluation-campaign.md: *Observability* rows for `identity_check_ms`
- Code: src/harness_bench/plan.py (file_hash, tree_hash, profile_record, builds, price_list_hash); grade/runner.py (grader_build, catalog_hash); engine.py:520-540 (the launch path); tests/test_architecture.py; the file list of src/harness_bench/

## Gate (lens reviewers; you never clear a veto)
- RV-PAT (Patterns Expert)
- RV-SIM (Simplifier, soft veto)
- RV-TA (Test Architect, **hard veto**)
- RV-SRE (SRE)

## Exit evidence (in your 10-line report)
- the commit SHAs on `design/eval-identity`, the doc path, and `docs-graph.py validate` exit 0;
- each "Done when" item above, with where in the doc it is met;
- open decision and seam request ids; spikes run, with results;
- budget used against the budget above.

## Not in scope
the baseline and defect-fix commands themselves (W1-C), eligibility rendering (W1-H), any code. W0 itself (send a seam request instead). Any hub file. Any merge or push.
