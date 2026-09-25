---
id: row15-headroom
title: "Row 15: the headroom rule for raising the parallelism cap"
type: decision-note
status: accepted
owner: "@timianmalloo"
links:
  - { to: coordination-finish-harness-bench, rel: relates-to }
review-by: "2026-10-09"
summary: >-
  The rule, written before the measurement run (R-38 condition 1, plan row 15), that decides what parallelism the D1
  samples support: memory, CPU and host headroom per cell, times the candidate parallelism, against the host figures.
---

# Row 15: the headroom rule

Written by the Leader on 2026-09-25, **before** the run `row15-d1-1` (D1 × `copilot-sol`, `codex-sol`, `cc-opus` × pack on/off × 1, parallelism 2). Rulings: R-9 condition 1 and R-38 condition 1. The rule is fixed here so the measurement cannot shape it.

## What is measured (the engine's own samples, per cell)

| sample | source | meaning |
| --- | --- | --- |
| `peak_memory` | `attempt.process_ended`, the job's peak (`engine.py:427`, `procs.py:157`) | the cell's whole process tree: adapter, agent, and any build it ran |
| `cpu_ms` | `attempt.process_ended`, the job's CPU time (`procs.py:160`) | summed CPU over the tree |
| `host_mem_available` | `cell.outcome` (`engine.py:330`) | free host memory when the cell ended |
| `wall_ms` | the lifecycle events | the cell's wall clock, used with `cpu_ms` for the CPU rate |

Host figures measured on 2026-09-24 (R-9): 24 logical CPUs, 127.4 GB RAM. The run records its own `host_mem_available`.

## Rule

A parallelism `p` from {2, 3, 4} is supported when all four hold:
1. **Samples are complete.** Every cell has non-null `peak_memory`, `cpu_ms` and `host_mem_available`. If any sample is null, the measurement is void, and the cap stays 2 (plan `:149`).
2. **Memory.** `p × max(peak_memory) × 1.5 ≤ min(host_mem_available) − 16 GB`. The factor 1.5 covers a cell larger than any measured. 16 GB is reserved for the operator and the Leader session.
3. **CPU.** `p × max(cpu_ms / wall_ms) ≤ 0.6 × 24` logical CPUs. This keeps 40% of the host free, so the engine's clock and the watchdog are never starved.
4. **No overlap failure.** No cell ended `failed (provider)` in this run (R-9 rule 5). A provider failure means the binding constraint is the allowance, not the host, and the cap stays at the value measured without it.

The cap becomes the largest `p` that passes, up to 4 (R-9 condition 1). The cap is changed in `plan.py` (`PHASE1_MAX_PARALLELISM`, `plan.py:39`) by W2-TASKS-b's last slice, and `tests/test_plan.py` asserts it (R-38 condition 2).

## Result

*Filled in after the run: the per-cell table, the computed bounds, and the cap they support.*
