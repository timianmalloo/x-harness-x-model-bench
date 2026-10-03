---
id: coordination-eval-brief-w1-f-property-grader
title: "W1-F brief: hidden-check runner and property grader (security-sensitive)"
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
  Self-contained Wave 1 dispatch brief (w1-f-property-grader): session, branch, pinned model, owned paths, inputs, W0 sections,
  gate lenses, budget, exit evidence, fallback and not-in-scope. The launcher passes only this file's path.
---

# W1-F brief: hidden-check runner and property grader (security-sensitive)

**Read first:** `C:\Projects\x-harness-x-model-bench\docs\coordination\eval-wave1\README.md` (the common rules). Then do this brief. Pass nothing else; this file is the whole dispatch.

| field | value |
| --- | --- |
| session | `w1f-property-e1e4` (`export AGENT_SESSION=w1f-property-e1e4`) |
| branch / tree | `design/eval-property-grader` → `C:\Projects\x-harness-x-model-bench-design-eval-property-grader` |
| model (pinned) | Claude Opus `claude-opus-5-5` (Agent tool `model: opus`; never a default) |
| first command | `python docs/ai-forward-pack/scripts/audit-log.py start --session w1f-property-e1e4 --skill design-slice` |
| tier · fan-out cap | T2 · 0 |
| budget | 160 tool calls · 200k tokens · 1 dispatch · 2.5 h |
| leader epoch | 13 |
| fallback | a fresh session of the same pinned model from this retained brief, after the Coordinator reads your report (resume starts with the `start` line) |

## Goal
Run `/design-slice` for **W1-F hidden-check runner and property grader (security-sensitive)**, producing `docs/design/eval-property-grader.md`. Follow its flow (`.claude/skills/design-slice/reference/flow.md`, read once at Stage 0). Settle the data model first. Name the patterns past both the Patterns Expert and the Simplifier. Write the E7 surface list, the failure-mode and STRIDE-lite analyses, the telemetry, and the test plan by node id (red-first tests named). Run the spikes the doc's contracts need. Leave the Gate record pending with the reviewers below.

## Done when (the plan row, verbatim)
Gate PASS with **Security & Identity as hard-veto reviewer**; the four ADR-0018 red tests and the race test named; the job-alone constraints adopted ("starts the check with `sys._base_executable` ... and `DETACHED_PROCESS`", plus the one-byte ack, spike E1-S3).

**Convergence condition (enough):** every STRIDE row of ADR-0018 has a control, a test node and a disposition, and every grader outcome in W0 §3 has a test.

## You own (authored; nothing else)
- `docs/design/eval-property-grader.md`

`docs/docs-index.js`, `docs/audit/audit-log.jsonl` and `docs/audit/change-log.jsonl` are derived or register files: regenerate or append, never claim.

## Inputs (read these; quote what you rely on)
- `docs/design/eval-seam-contracts.md`: §2, §3 (the PropertyCheck contract, including the one-byte ack and the measured-0 rule), §7 (catalog ids and **DR-4, provisional (a)**), §9, §10 G4 and the ADR-0018 §11(b) quote, §11 HB-CHK-001..004, §13 (grade/runner.py, procs.py, egress.py owner X-F)
- docs/adr/0018-hidden-check-harness.md (all; §9, §10, §10a are the hard-veto core); docs/adr/0010-cell-output-is-untrusted-on-the-host.md; docs/adr/0013-native-cells-own-working-copy.md Amendment 2
- docs/notes/spike-e1-job-alone.md, spike-e1-handle-list.md, spike-phase1-probes.md (N4 is Verified), spike-a9-host-sleep.md
- Code: src/harness_bench/grade/__init__.py (Score, CellInput), grade/runner.py (GRADERS, applicable), grade/correctness.py:48-97, grade/mutation.py:38, 195, procs.py (Job, spawn), egress.py
- docs/specs/enterprise-evaluation.md EV-1 (the measured 0), EV-2, EV-3 and the STRIDE table

## Gate (lens reviewers; you never clear a veto)
- RV-PAT (Patterns Expert)
- RV-SIM (Simplifier, soft veto)
- RV-TA (Test Architect, **hard veto**)
- RV-SEC (Security & Identity, **hard veto**)

## Exit evidence (in your 10-line report)
- the commit SHAs on `design/eval-property-grader`, the doc path, and `docs-graph.py validate` exit 0;
- each "Done when" item above, with where in the doc it is met;
- open decision and seam request ids; spikes run, with results;
- budget used against the budget above.

## Not in scope
loopback fakes (E4, X-LB: name the seam only), task content (W1-I), any code. W0 itself (send a seam request instead). Any hub file. Any merge or push.
