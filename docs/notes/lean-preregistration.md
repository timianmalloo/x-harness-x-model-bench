---
id: "lean-preregistration"
title: "Lean benchmark pre-registration (LB-2)"
type: decision-note
status: draft
owner: "@timianmalloo"
phase: "Lean benchmark (operator 2026-10-09)"
tags: [benchmark, lean-benchmark, pre-registration, statistics, mde]
links:
  - { to: spec-lean-pack-benchmark, rel: implements }
  - { to: adr-0022-lean-benchmark-two-batch-runs, rel: relates-to }
  - { to: adr-0023-lean-summary-over-verdicts, rel: relates-to }
  - { to: plan-strategy-lean-benchmark, rel: relates-to }
review-by: "2026-12-31"
summary: >-
  The lean benchmark's pre-registration (spec LB-2), committed before batch 1's first cell: the question, the primary
  metric property_check_pass, pack-off vs pack-on, the pair, the exclusion rule, and the design MDEs 0.31 per harness
  and 0.19 pooled.
---

# Lean benchmark pre-registration (LB-2)

**Pre-registration.** The question is whether the pack (arm `on`) changes the pass rate of the primary metric relative to pack-off (arm `off`) on the lean task set, per harness and pooled. The primary metric is `property_check_pass`, one recorded value per cell. The comparison is pack-off vs pack-on, with the arm binding fixed in the plan (ADR-0022: two 60-cell batch runs of one lean ring). The pair is one task × one repetition × one harness: the pack-off cell and the pack-on cell that share that task, repetition and harness. The exclusion rule is that a cell with no recorded primary value is excluded from its pair, and the pair is dropped. The design minimum detectable effects (MDE) are 0.31 per harness and 0.19 pooled across harnesses. This statement is committed before batch 1's first cell starts; if the commit is not earlier than that cell's start time, the run report labels the result "not pre-registered" (LB-2).
