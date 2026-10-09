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

**Pre-registration.** The question: with the AI-Forward pack on versus off, does each harness (Claude Code `claude-opus-5-5`, Codex `gpt-6.1-sol`, Copilot `gpt-6.1-sol`) do better on the ten property tasks, and at what token cost? The primary metric is `property_check_pass`, one binary value per cell. The comparison is pack-off (arm `off`) vs pack-on (arm `on`), run as two 60-cell batch runs of one lean ring, `bench/rings/lean.yaml`, with one arm binding, pooled at report time (ADR-0022). The pair is task × repetition × harness: the pack-off cell and the pack-on cell that share them, where batch 1 is repetition 1 and batch 2 is repetition 2. The exclusion rule: a cell with no recorded primary value is excluded from its pair, and the pair is dropped. The design minimum detectable effects (MDE) are 0.31 per harness (20 pairs) and 0.19 pooled (60 pairs), with both batches run; with batch 1 alone they are 0.42 and 0.26 (ADR-0023 §6). The effect and its interval come from `stats.paired_delta`, which draws tasks first and then repetitions within each task, seeded from this file's sha256; the token cost is the token ratio of totals (pack-on / pack-off) with its interval, from `stats.paired_ratio` (ADR-0023 §3, §4, §8). Timing rule: this paragraph is committed before batch 1's first cell starts; if its commit time is not earlier than that start, the run report labels the result "not pre-registered" (LB-2).
