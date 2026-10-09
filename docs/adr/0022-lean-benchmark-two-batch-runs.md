---
id: "adr-0022-lean-benchmark-two-batch-runs"
title: "ADR-0022: The lean benchmark is two 60-cell runs of one lean ring, pooled at report time"
type: adr
status: draft
owner: "@timianmalloo"
phase: "Lean benchmark (operator 2026-10-09)"
tags: [benchmark, lean-benchmark, ring, batch, checkpoint, plan-identity]
links:
  - { to: arch-lean-benchmark, rel: refines }
  - { to: spec-lean-pack-benchmark, rel: implements }
  - { to: adr-0006-results-data-model, rel: depends-on }
  - { to: adr-0017-engine-identity-and-freeze, rel: depends-on }
review-by: "2027-04-09"
summary: >-
  The 120 cells run as two confirmed runs of one new ring, bench/rings/lean.yaml (the pilot ring's 60 cells with
  ring tag lean). Batch 1 runs and grades, the checkpoint reads it, then batch 2 runs. The report pools the two by
  `bench report <batch-2> --pool <batch-1>`, refusing unless both plans share one plan identity. One plan with
  repetitions 2 was rejected: its launch order interleaves repetitions and `bench run` grades only at the end, so
  the checkpoint could not be a real stop. The readiness records are not refreshed.
---

# ADR-0022: The lean benchmark is two 60-cell runs of one lean ring, pooled at report time

- **Status:** Proposed
- **Date:** 2026-10-09
- **Deciders:** @timianmalloo; authored by Claude Code (Leader seat, Opus) with the Tech Lead and Simplifier lenses
- **Context:** `docs/specs/lean-pack-benchmark.md` (LB-1, LB-3, the aggregate invariant); strategy §3 (a) and (e);
  `docs/architecture-lean-benchmark.md`.

## Context

The spec wants 120 cells in two batches of 60, with a checkpoint between them that reads batch 1's **run and
grading** minutes per cell and its tokens. Batch 2 must be stoppable when a threshold trips (LB-3). Both batches
must come from one plan identity (the aggregate's invariant, EV-17's intent).

Read on 2026-10-09 at `307ec787`:
- `plan.launch_order` sorts by `sha256(seed|block|task|combo|rep)` (`plan.py:209-215`). In one plan with
  `repetitions: 2`, repetition-1 and repetition-2 blocks are **interleaved**. The first 60 launched cells are not
  repetition 1. [Verified]
- `bench run` "runs a confirmed plan to completion, then grade[s] it" (`cli.py:725`). There is no repetition
  filter on `plan` or `run`. A plan's grading minutes exist only after the whole plan ran. [Verified]
- A frozen plan carries `matrix_hash`, task `version_hash`es, `builds`, `profiles`, `arms` (with the bound pack
  revision), `comparisons`, `platform`, the `ring` hash and `cells` in **launch order** (`plan.py:547-580`).
  `launch_seed` is drawn per plan from `secrets.randbits(63)` (`plan.py:229`). So two plans of one matrix differ in
  `run_id`, `created_at`, `trace_id`, `launch_seed`, `plan_hash`, the order of `cells`, and (if the slot count
  changes) `parameters` and `envelope_seconds`. [Verified; the gate's finding 10]
- Cell folders are `cells_root/<run_id>/<cell_id>` (`engine.py:727`). The judge verdict store is keyed by
  request, schema, model and invocation hashes, not by cell id (`gateway/store.py:3`, `:30`). Two runs with equal
  `cell_id`s do not collide. [Verified]
- `config.RING_TAGS = ("pilot", "pack-regression", "comparison")` (`config.py:41`); a ring tag outside it is
  refused by `bench validate` (`config.py:170-171`). [Verified]

## Decision

1. **A new ring, `bench/rings/lean.yaml`:** `bench/rings/e5-pilot.yaml`'s content (the ten property tasks, arms
   `off` and `on`, comparison `[off, on]`, the three pinned combos, `repetitions: 1`) with `ring: {tag: lean}`.
   `lean` is added to `config.RING_TAGS`. 60 cells per plan.
2. **Two confirmed runs of it are the two batches.** Both plans bind `--arm on=C:/Projects/ai-forward@<the F-PACK
   head, 40 hex>`. Batch 1 is planned, confirmed, run and graded. The checkpoint reads it. Batch 2 is then planned
   from the **same matrix file at the same commit** and run.
3. **Pooling is explicit:** `bench report <batch-2> --pool <batch-1>`. In the pooled view, the `--pool` run's
   cells are repetition 1 and the reported run's cells are repetition 2. Pooling uses **one** comparability
   function: `board.compare`'s preconditions (`board.py:726-795`: graded, ring hash, combos, BOM, catalog, task
   versions, platform) are extracted into a function that `compare` keeps calling, with the same messages. The
   pooling check adds three lean rules to it, and refuses with HB-STA-002, naming each difference:
   - both plans carry ring tag `lean`;
   - both plans have equal `cells` **as a set keyed by `cell_id`**, compared on task, combo, arm and model. The
     stored list is in launch order, which depends on `launch_seed`, and that differs per plan
     (`secrets.randbits(63)`, `plan.py:229`);
   - both plans have equal `arms` (pack revisions), `builds`, `profiles` and `instruction_lists`.

   `parameters` (including `parallelism`) and `envelope_seconds` are **shown as differences, never refused**.
   Dropping batch 2 to 2 slots is the spec's own rate-limit response. `run_id`, `created_at`, `trace_id`,
   `launch_seed` and `plan_hash` are ignored.
3a. **A lean ring is refused with `--campaign`** (HB-CMP-010, as `pack-regression` already is;
   `campaign.py:1170-1175`). A lean run never enters campaign state.
4. **The lean shape is the ring tag.** A run whose plan's ring tag is `lean` renders the lean summary (ADR-0023):
   `1 of 2 batches` alone, `2 of 2` with `--pool`. Every other run renders exactly as today.
5. **Engine identity:** the Leader runs both batches from one gated commit, in one tree it does not edit between
   the batches. The run report records, at each batch start, that commit and
   `identity.identity_hash(identity.manifest(...))` (ADR-0017's content-addressed identity). Unequal values are a
   stop, not a footnote.
6. **Readiness records (strategy §3 e):** not refreshed. `plan.py` and `run` do not import `readiness` (strategy
   §2, read by grep). Before batch 1 the Leader runs `bench validate` and one `bench discriminate` trial each for
   NG1 and S2, whose base trees changed under Ruling 116. A failed trial stops the run and goes to the operator.

## Consequences

- The checkpoint is a real stop. Batch 1's run and grading are both measured before batch 2 starts. Batch 2's
  time is then known before it is spent.
- Wall time is sequential: about 1.1 h run + 1.2 h grading per batch, about 4.6 h end to end (Inferred from
  grid-4's rates). Grading batch 1 while batch 2 runs is not possible and is not needed: each `bench run` grades
  its own cells, and LB-3 requires batch 1 graded before batch 2.
- **Spec drift, superseded here (L-DOCS adds dated errata to the spec):**
  - LB-1 says one `bench plan` lists 120 cells. Under this ADR, two `bench plan` calls list 60 each, from one ring
    and one arm binding.
  - The NFR table's Compatibility row defines the lean shape as "2 arms". Under this ADR it is the ring tag `lean`.
- The lean ring is a new matrix file. `e5-pilot.yaml` stays the campaign's pilot ring, unchanged. A lean run
  never touches campaign state.
- No new stored quantity. The two batch runs are ordinary runs (ADR-0006: append-only ledgers, frozen plans).
  The lean benchmark's identity is the ring hash, the arm binding and the two run ids, which the run report records.

## Alternatives considered

- **One plan, `repetitions: 2`, checkpoint by reading `bench status` mid-run.** Rejected. The interleaved launch
  order means no point in the run is "repetition 1 done". Grading minutes are not measured until the end. A
  `bench stop` mid-run leaves a partial mix of both repetitions. The checkpoint would read run minutes and tokens
  only, and LB-3 needs grading minutes.
- **A repetition filter or offset on `bench plan`** (for example, plan repetition 2 only). Rejected. It changes
  the matrix schema and the cell-id recipe (ADR-0006) to save a report-side relabel.
- **Reuse `e5-pilot.yaml` (tag `pilot`) and trigger the lean summary with a report flag.** Rejected. Then the
  report's content would depend on a flag, not on the data. The `pilot` tag also carries campaign semantics
  (`campaign.py:1462`).
- **Refresh the ten readiness records** (about 1 h of Leader machine time, Inferred). Rejected. The lean path does
  not read them. The two trials cover the base trees that changed.
