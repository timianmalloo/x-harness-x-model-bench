---
id: proposal-benchmark-state-and-target
title: "Benchmark: state and target"
type: doc
status: proposed
owner: "@timianmalloo"
tags: [benchmark, proposal, pack-effect, enterprise, assessment]
links:
  - { to: proposal-pack-onoff-analysis, rel: relates-to }
  - { to: proposal-enterprise-production-portfolio, rel: relates-to }
  - { to: proposal-cross-harness-benchmarking, rel: relates-to }
review-by: "2026-12-31"
summary: >-
  After grids 1-4 the tool works (276-cell grids, verify ok, CI green) and its pack-improvement loop
  found and verified real fixes (pack-attributed failures 4 -> 0, ceremony waste -79%), but it cannot
  answer the question it was built for: the tasks are mostly saturated, the judge metrics never record,
  and no task tests security, resilience, rework or the Spike Protocol. On these tasks the pack costs
  2.9-10.8x tokens with no pass gain and worse drift. Approach: an Enterprise/Production task family with
  mechanical checks, metrics that record, a power analysis, a pilot ring and an engine freeze, and one
  well-powered grid comparing pack-off, the current pack and a slimmed pack. The page is
  benchmark-state-and-target.html.
---

# Benchmark: state and target

The proposal is the self-contained page [benchmark-state-and-target.html](benchmark-state-and-target.html).
This file is its graph record: the docs graph joins the page to this frontmatter by the shared file stem.
