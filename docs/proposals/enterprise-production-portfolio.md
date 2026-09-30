---
id: proposal-enterprise-production-portfolio
title: "An Enterprise/Production portfolio for harness-bench"
type: doc
status: proposed
owner: "@timianmalloo"
tags: [benchmark, proposal, bom, security, privacy, resilience, rework, simplicity]
links:
  - { to: proposal-cross-harness-benchmarking, rel: relates-to }
  - { to: proposal-pack-onoff-analysis, rel: depends-on }
review-by: "2026-12-31"
summary: >-
  BOM 0.5 measures SWE capability on small, saturated tasks; no task carries a latent enterprise requirement
  with a mechanical oracle. Proposes eight task families (H security, I privacy, J compliance, K resilience,
  L operability, M long-horizon rework, N unfamiliar API / spike, O simplicity controls, P drift), their
  mechanical metrics, sample sizes (about 39 cells per arm for a 0.30 pass-rate delta), the map to each pack
  intention, and a phased rollout that fixes measurement first. The page is enterprise-production-portfolio.html.
---

# An Enterprise/Production portfolio for harness-bench

The proposal is the self-contained page [enterprise-production-portfolio.html](enterprise-production-portfolio.html).
This file is its graph record: the docs graph joins the page to this frontmatter by the shared file stem.
