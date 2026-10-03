---
id: coordination-eval-brief-sp-lb-loopback
title: "SP-LB brief: loopback firewall spike (Windows; the operator runs it)"
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
  Self-contained Wave 1 dispatch brief (sp-lb-loopback): session, branch, pinned model, owned paths, inputs, W0 sections,
  gate lenses, budget, exit evidence, fallback and not-in-scope. The launcher passes only this file's path.
---

# SP-LB brief: loopback firewall spike (Windows; the operator runs it)

**Read first:** `C:\Projects\x-harness-x-model-bench\docs\coordination\eval-wave1\README.md` (the common rules). Then do this brief. Pass nothing else; this file is the whole dispatch.

| field | value |
| --- | --- |
| session | `splb-loopback-e1e4` (`export AGENT_SESSION=splb-loopback-e1e4`) |
| branch / tree | `spike/s-lb-loopback` → `C:\Projects\x-harness-x-model-bench-spike-s-lb-loopback` |
| model (pinned) | Claude Sonnet `claude-sonnet-5` (Agent tool `model: sonnet`; never a default) |
| first command | `python docs/ai-forward-pack/scripts/audit-log.py start --session splb-loopback-e1e4 --skill spike` |
| tier · fan-out cap | T1 · 0 |
| budget | 40 tool calls · 100k tokens · 1 dispatch · 0.5 h, plus an operator session |
| leader epoch | 13 |
| fallback | a fresh session of the same pinned model from this retained brief, after the Coordinator reads your report (resume starts with the `start` line) |

## Goal
Write the spike script and its note. The script is stdlib only, takes `--mode loopback|positive-control|report`, copies the interpreter to a fresh path (step 1), binds and exchanges one request (step 2), snapshots `Get-NetFirewallRule` before and after (step 3), and prints one JSON result. Check it with `python -m py_compile` only. **Do not run a bind.** The note (frontmatter `type: decision-note`) holds the procedure, the exact operator command lines, the pass rule quoted, and an empty results table. The Leader runs it with the operator present (B-2) and fills the table.

## Done when (the plan row, verbatim)
The procedure in the architecture doc run on Windows, **operator present**: no prompt and no new rule for the loopback bind, **and** the `0.0.0.0` positive control fires.

**Convergence condition (enough):** the script runs the four steps with one command per mode, prints a machine-readable result, and the note holds the procedure and an empty results table for the operator's run.

## You own (authored; nothing else)
- `tools/spikes/s_lb_loopback.py`
- `docs/notes/spike-s-lb-loopback.md`

`docs/docs-index.js`, `docs/audit/audit-log.jsonl` and `docs/audit/change-log.jsonl` are derived or register files: regenerate or append, never claim.

## Inputs (read these; quote what you rely on)
- `docs/design/eval-seam-contracts.md`: §3 (`interface: loopback`, `bounds_ms`)
- docs/architecture-evaluation-campaign.md: *Spike S-LB (loopback firewall), how it settles the flag* (steps 1-4 and the pass rule: quote them)
- docs/adr/0018-hidden-check-harness.md §3 (the `assume:` this spike confirms or refutes)
- an existing spike note's shape: docs/notes/spike-e1-ntfs-atomic-publish.md

## Gate (lens reviewers; you never clear a veto)
- no lens review; the operator's run is the evidence (B-2)

## Exit evidence (in your 10-line report)
- the commit SHAs on `spike/s-lb-loopback`, the doc path, and `docs-graph.py validate` exit 0;
- each "Done when" item above, with where in the doc it is met;
- open decision and seam request ids; spikes run, with results;
- budget used against the budget above.

## Not in scope
running any bind yourself (a firewall dialog with no one watching is the failure this spike looks for); macOS; any `src/` code. W0 itself (send a seam request instead). Any hub file. Any merge or push.
