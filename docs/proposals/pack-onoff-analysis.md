---
id: proposal-pack-onoff-analysis
title: "Pack on vs pack off: grid-1 analysis and ranked pack changes"
type: doc
status: proposed
owner: "@timianmalloo"
tags: [benchmark, proposal, pack-effect, continuous-improvement]
links:
  - { to: proposal-cross-harness-benchmarking, rel: relates-to }
  - { to: design-phase4-report, rel: relates-to }
review-by: "2026-12-31"
summary: >-
  grid-1 + grid-1-cc (108 cells, pack r97, BOM 0.3 smoke): the pack cost 3.5x tokens and 1.9x wall clock and
  passed 40/54 vs 48/54 (p=0.08); 10 of 14 pack-on failures trace to worktree diversion (WT1) and ceremony
  that ended the turn, not to wrong code. Process changed as intended (goal state 51/54, test-first on D1 8/9
  vs 0/9) but no smoke task can show the payoff; security, privacy, resilience and the Spike Protocol are not
  measurable in this BOM. Seven ranked pack changes. The page is pack-onoff-analysis.html.
---

# Pack on vs pack off: grid-1 analysis

The analysis is the self-contained page [pack-onoff-analysis.html](pack-onoff-analysis.html). This file is its
graph record: the docs graph joins the page to this frontmatter by the shared file stem.
