---
id: coordination-eval-brief-w1-c-campaign-record
title: "W1-C brief: campaign record and `bench campaign`"
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
  Self-contained Wave 1 dispatch brief (w1-c-campaign-record): session, branch, pinned model, owned paths, inputs, W0 sections,
  gate lenses, budget, exit evidence, fallback and not-in-scope. The launcher passes only this file's path.
---

# W1-C brief: campaign record and `bench campaign`

**Read first:** `C:\Projects\x-harness-x-model-bench\docs\coordination\eval-wave1\README.md` (the common rules). Then do this brief. Pass nothing else; this file is the whole dispatch.

| field | value |
| --- | --- |
| session | `w1c-campaign-e1e4` (`export AGENT_SESSION=w1c-campaign-e1e4`) |
| branch / tree | `design/eval-campaign-record` → `C:\Projects\x-harness-x-model-bench-design-eval-campaign-record` |
| model (pinned) | Claude Sonnet `claude-sonnet-5` (Agent tool `model: sonnet`; never a default) |
| first command | `python docs/ai-forward-pack/scripts/audit-log.py start --session w1c-campaign-e1e4 --skill design-slice` |
| tier · fan-out cap | T2 · 0 |
| budget | 140 tool calls · 180k tokens · 1 dispatch · 2 h |
| leader epoch | 13 |
| fallback | a fresh session of the same pinned model from this retained brief, after the Coordinator reads your report (resume starts with the `start` line) |

## Goal
Run `/design-slice` for **W1-C campaign record and `bench campaign`**, producing `docs/design/eval-campaign-record.md`. Follow its flow (`.claude/skills/design-slice/reference/flow.md`, read once at Stage 0). Settle the data model first. Name the patterns past both the Patterns Expert and the Simplifier. Write the E7 surface list, the failure-mode and STRIDE-lite analyses, the telemetry, and the test plan by node id (red-first tests named). Run the spikes the doc's contracts need. Leave the Gate record pending with the reviewers below.

## Done when (the plan row, verbatim)
Gate PASS incl. Security and Distributed Systems; lock-then-read for every command (ADR-0016 §1, council D6); tamper tests named.

**Convergence condition (enough):** every `bench campaign` command has its state guard, idempotency rule, refusal copy and test node.

## You own (authored; nothing else)
- `docs/design/eval-campaign-record.md`

`docs/docs-index.js`, `docs/audit/audit-log.jsonl` and `docs/audit/change-log.jsonl` are derived or register files: regenerate or append, never claim.

## Inputs (read these; quote what you rely on)
- `docs/design/eval-seam-contracts.md`: §5 (the plan's `campaign` block, built by X-C and passed to `build_plan`), §6 (ledger kinds and fields, content-addressed files, `campaign_id` pattern), §8 (`campaign.read` for X-H2), §10 (the ADR-0018 §11(b) quote), §11 HB-CMP-001..009, §13 (cli.py, ledger.py, status.py owners)
  - **W0 revision 2 changes these inputs:** §6: the pre-registration freeze order (attach freezes; HB-CMP-009; `bench run` refuses with HB-CMP-010), the lock protocol (own lock, then a try-probe; HB-CMP-004, HB-GRD-007), the `campaign.lock` line in `.gitignore` (yours, §13), the sweep of `*.tmp-*` under the lock and `verify` ignoring them (§4), and a justification for each ledger kind. §2: the readiness call in `cli.py` `cmd_validate` (a seam from X-E). §7 condition 3: you pass X-E's disagreement list to `gates.pilot`.
- docs/adr/0016-campaign-record.md (all); docs/adr/0017-engine-identity-and-freeze.md §3-§6; docs/adr/0018-hidden-check-harness.md §11
- docs/specs/enterprise-evaluation.md: domain model (lines 117-220), EV-13, EV-14, EV-16, EV-20, Part B user flow UF-E1 and the CLI copy
- docs/adr/0006-append-only-run-ledger-and-derived-results.md (the physical rules you reuse)
- Code: src/harness_bench/ledger.py, oslock.py, status.py, cli.py (command wiring), grade/runner.py (grade.lock)
- docs/notes/rulings.md R-89 (the E1 demo pre-registration: minimum recorded pairs ≤ 3)

## Gate (lens reviewers; you never clear a veto)
- RV-PAT (Patterns Expert)
- RV-SIM (Simplifier, soft veto)
- RV-TA (Test Architect, **hard veto**)
- RV-SEC (Security & Identity, **hard veto**)
- RV-DS (Distributed Systems, **hard veto**)

## Exit evidence (in your 10-line report)
- the commit SHAs on `design/eval-campaign-record`, the doc path, and `docs-graph.py validate` exit 0;
- each "Done when" item above, with where in the doc it is met;
- open decision and seam request ids; spikes run, with results;
- budget used against the budget above.

## Not in scope
the identity manifest builder (W1-D), power and verdict math (W1-H), the alarm (W1-K), any code. W0 itself (send a seam request instead). Any hub file. Any merge or push.
