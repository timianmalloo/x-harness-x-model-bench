---
id: coordination-eval-brief-w1-b-atomic-publish
title: "W1-B brief: crash-atomic publish (archive rename + create_once)"
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
  Self-contained Wave 1 dispatch brief (w1-b-atomic-publish): session, branch, pinned model, owned paths, inputs, W0 sections,
  gate lenses, budget, exit evidence, fallback and not-in-scope. The launcher passes only this file's path.
---

# W1-B brief: crash-atomic publish (archive rename + create_once)

**Read first:** `C:\Projects\x-harness-x-model-bench\docs\coordination\eval-wave1\README.md` (the common rules). Then do this brief. Pass nothing else; this file is the whole dispatch.

| field | value |
| --- | --- |
| session | `w1b-publish-e1e4` (`export AGENT_SESSION=w1b-publish-e1e4`) |
| branch / tree | `design/eval-atomic-publish` → `C:\Projects\x-harness-x-model-bench-design-eval-atomic-publish` |
| model (pinned) | Claude Sonnet `claude-sonnet-5` (Agent tool `model: sonnet`; never a default) |
| first command | `python docs/ai-forward-pack/scripts/audit-log.py start --session w1b-publish-e1e4 --skill design-slice` |
| tier · fan-out cap | T2 · 0 |
| budget | 100 tool calls · 150k tokens · 1 dispatch · 1 h |
| leader epoch | 13 |
| fallback | a fresh session of the same pinned model from this retained brief, after the Coordinator reads your report (resume starts with the `start` line) |

## Goal
Run `/design-slice` for **W1-B crash-atomic publish (archive rename + create_once)**, producing `docs/design/eval-atomic-publish.md`. Follow its flow (`.claude/skills/design-slice/reference/flow.md`, read once at Stage 0). Settle the data model first. Name the patterns past both the Patterns Expert and the Simplifier. Write the E7 surface list, the failure-mode and STRIDE-lite analyses, the telemetry, and the test plan by node id (red-first tests named). Run the spikes the doc's contracts need. Leave the Gate record pending with the reviewers below.

## Done when (the plan row, verbatim)
Gate PASS incl. Security and Distributed Systems; the D1 and D3 red tests named; the Windows no-directory-fsync branch stated (spike E1-NTFS); the defect class text for "exists means complete".

**Convergence condition (enough):** both implementation tracks (X-B1 `atomic.py`, X-B2 `archive.py`) can start red-first from the doc alone.

## You own (authored; nothing else)
- `docs/design/eval-atomic-publish.md`

`docs/docs-index.js`, `docs/audit/audit-log.jsonl` and `docs/audit/change-log.jsonl` are derived or register files: regenerate or append, never claim.

## Inputs (read these; quote what you rely on)
- `docs/design/eval-seam-contracts.md`: §4 (the `atomic.py` API: create_once, publish_dir, stale_temps), §11 HB-LED-007, §13 (archive.py owner X-B2; atomic.py X-B1), §12 (E2 snapshot use by X-J1)
- docs/adr/0015-multi-turn-attempt-and-turn-snapshots.md §5a; docs/adr/0016-campaign-record.md §2a; docs/adr/0021-plan-level-resume-and-liveness.md §4 (the `*.tmp-*` and complete-folder rows)
- docs/notes/spike-e1-ntfs-atomic-publish.md (measured NTFS behaviour; quote it)
- Code: src/harness_bench/archive.py (all, esp. 55-112); engine.py:580-600, 800-815 (archive call and `cell.archive_failed`); views.py:686
- docs/lessons/defect-classes.md (find the nearest existing class; propose the 'exists means complete' class text)

## Gate (lens reviewers; you never clear a veto)
- RV-PAT (Patterns Expert)
- RV-SIM (Simplifier, soft veto)
- RV-TA (Test Architect, **hard veto**)
- RV-SEC (Security & Identity, **hard veto**)
- RV-DS (Distributed Systems, **hard veto**)

## Exit evidence (in your 10-line report)
- the commit SHAs on `design/eval-atomic-publish`, the doc path, and `docs-graph.py validate` exit 0;
- each "Done when" item above, with where in the doc it is met;
- open decision and seam request ids; spikes run, with results;
- budget used against the budget above.

## Not in scope
resume logic (W1-K), snapshot paths (W1-J), any code. W0 itself (send a seam request instead). Any hub file. Any merge or push.
