---
id: coordination-eval-brief-rv-pat
title: "RV-PAT brief: Patterns Expert lens reviewer (Adversary Mode)"
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
  Self-contained Wave 1 dispatch brief (rv-pat): session, branch, pinned model, owned paths, inputs, W0 sections,
  gate lenses, budget, exit evidence, fallback and not-in-scope. The launcher passes only this file's path.
---

# RV-PAT brief: Patterns Expert lens reviewer (Adversary Mode)

**Read first:** `C:\Projects\x-harness-x-model-bench\docs\coordination\eval-wave1\README.md` (the common rules). Then do this brief.

| field | value |
| --- | --- |
| session | `rv-pat-e1e4` (`export AGENT_SESSION=rv-pat-e1e4`) |
| branch / tree | `review/eval-pat` → `C:\Projects\x-harness-x-model-bench-review-eval-pat` |
| model (pinned) | Claude Sonnet `claude-sonnet-5` (Agent tool `model: sonnet`; never a default) |
| first command | `python docs/ai-forward-pack/scripts/audit-log.py start --session rv-pat-e1e4 --skill design-slice-review` (again at the start of every later batch message) |
| tier · fan-out cap | T2 · 0 |
| budget | about 40 tool calls per slice; context ceiling 150k: past it, commit, report, and the Coordinator starts a fresh `RV-PAT` session from this brief |
| your lens | `.claude/agents/patterns-expert*.md` (read it once; you are that persona, in Adversary Mode) |
| veto | advisory; with RV-SIM a mutual check (a pattern survives only if it passes both) |
| slices | all twelve (W1-A..W1-L) and W0 |

## How you work
You are one session per lens, continued across batches by `SendMessage`. Each message names the slices to review now and their branches. For each slice:
1. Read the design from its branch, read-only: `git -C C:\Projects\x-harness-x-model-bench show <branch>:docs/design/<file>.md` (branch and file are in `docs/coordination/eval-wave1/README.md` §5; W0 is `docs/design/eval-seam-contracts.md` on `main`). Never edit another track's file.
2. Check it against its ADRs, the spec criteria its brief cites, and W0. Open the code it cites; never assert the code's shape from memory.
3. Write findings as a table: location · finding · severity (blocking / major / minor) · evidence (file:line or quote) · fix · confidence (Verified / Inferred).
4. End the slice's section with one gate line, exactly: `GATE <slice id> · Patterns Expert · PASS | PASS WITH CONDITIONS | BLOCK · <n> findings (rv-pat-e1e4, <date>)`.
5. A finding that two designs disagree at a seam is the most valuable thing you can find (E2E-D). Name both docs and the W0 section.

## You own
- `docs/design/reviews/eval-review-pat.md`: one file for your lens, one `##` section per slice, appended per batch. Frontmatter: `id: review-eval-pat`, `type: doc`, `status: draft`, `owner: "@timianmalloo"`, `links: [{to: design-eval-seam-contracts, rel: relates-to}]`, `review-by`, and a summary.

After each batch: `docs-graph.py derive` and `validate`, the audit `append` (skill `design-slice-review`), then commit by named paths. Report in at most 10 lines: the gate lines, verbatim; blocking findings in one line each; seam disagreements; budget used.

## Not in scope
Editing any design or W0 (findings only); re-designing a slice; reviewing slices outside your list (say so if asked); any code; any merge.
