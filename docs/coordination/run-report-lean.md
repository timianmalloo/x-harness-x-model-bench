---
id: run-report-lean
title: "Run report - the lean pack benchmark (pack-on vs pack-off per harness)"
type: doc
status: accepted
owner: "@timianmalloo"
tags: [coordination, run-report, lean-benchmark, pack-effect]
links:
  - { to: spec-lean-pack-benchmark, rel: implements }
  - { to: coordination-lean, rel: relates-to }
  - { to: arch-lean-benchmark, rel: relates-to }
review-by: "2027-04-10"
summary: >-
  The lean benchmark ran 2026-10-10: Claude Code (claude-opus-5-5) and Copilot (gpt-6.1-sol) as two pooled batches,
  and Codex (gpt-6.1-sol) as its own pair on Codex 0.160.0 after the pinned 0.156.0 was refused. No harness shows a
  detectable pack effect on property_check_pass (effect +0.00 each; per-harness MDE 0.31 to 0.42). The pack adds
  tokens: 1.62x for Claude Code, 9.56x for Copilot, 2.28x for Codex (ratio of totals). Total 87.6M tokens against
  an approved 127M; Copilot's figure is a lower bound on 8 cells. Pre-registered (af36296ebcb0) before the first cell.
---

# Run report: the lean pack benchmark

**Status: accepted.** Written by the analysis seat (Claude Code, `claude-opus-5-5`, session `report-lean`) for the
Leader `lean-leader-1`, 2026-10-10. It answers spec LB-8.

**Sources.** Every number is **Verified** (read from a named file) or **Inferred** (the model is stated). Paths:

- **R-b1, R-b2, R-cb1, R-cb2**: `runs/<run>/report.html` in the integration tree
  `C:/Projects/x-harness-x-model-bench-integrate-lean-20` (runs `lean-b1`, `lean-b2`, `lean-codex-b1`,
  `lean-codex-b2`). R-b2 holds the pooled lean section for `lean-b1`+`lean-b2`; R-cb2 holds the pooled Codex pair.
- **P**: `runs/<run>/plan.json` in the same tree. **E**: `runs/<run>/events/*.jsonl`.
- **L**: the Leader's scratch, `C:/tf/lean-leader/` (`*-start.txt`, `engine-id.jsonl`, `owed-docs.md`,
  `codex-probe/`).
- **Plan**: `docs/coordination/coordination-lean.md`, *Errata (Coordinator #64)* and *(Coordinator #66)*.
- **Register**: `docs/lessons/defect-classes.md`, *Coordinator #64 entries* and *Coordinator #66 entries*.

Tokens are the only cost axis in this report.

## Result

**No harness shows a detectable pack effect on `property_check_pass` at this design's power.** The measured effect
(pack-on minus pack-off) is +0.00 for Claude Code, Copilot and Codex. Every 95% interval contains zero. The design
could detect only an effect of about 0.31 or more per harness (0.42 if task repeats count as one). So a smaller
effect, in either direction, is not ruled out. The pack does change token use. For the same tasks, pack-on used
**1.62x** the tokens of pack-off in Claude Code, **9.56x** in Copilot and **2.28x** in Codex (ratio of totals). Per
pair, that is about 0.29M more tokens in Claude Code, 2.01M in Copilot and 0.26M in Codex.

### Per harness (Verified: R-b2 lean section for Claude Code, Copilot and their pooled row; R-cb2 for Codex)

| Harness (model) | Effect on `property_check_pass` | 95% interval | MDE | Pairs | Statement | Token ratio of totals, on/off [95% interval] |
| --- | --- | --- | --- | --- | --- | --- |
| Claude Code (`claude-opus-5-5`) | +0.00 | [-0.20, +0.20] | 0.31 | 20 of 20 | no detectable effect | 1.62x [1.28, 2.03] |
| Copilot (`gpt-6.1-sol`) | +0.00 | [-0.25, +0.30] | 0.31 | 20 of 20 | no detectable effect | 9.56x [8.40, 11.29] |
| Codex (`gpt-6.1-sol`, Codex 0.160.0; own pair) | +0.00 | [-0.10, +0.10] | 0.31 | 20 of 20 | no detectable effect | 2.28x [2.00, 2.85] |
| Pooled, Claude Code + Copilot only | +0.00 | [-0.18, +0.18] | 0.19 | 40 of 60 | no detectable effect | 4.27x [2.79, 6.41] |

- **Codex in `lean-b1`/`lean-b2`: 0 pairs, by ruling.** R-b2 lists Codex as "0 of 20 pairs recorded": 36 cells
  skipped by decision D1 and 4 invalid (2 per batch, "failed (model unavailable)"). Its Codex numbers come from the
  separate pair (R-cb2), whose own pooled row repeats the Codex row.
- **There is no three-harness pooled row.** The Codex pair ran on a different engine identity: commit `f6389964`,
  not `6140844f`, with the Codex build bumped to 0.160.0 and its own ring file (`bench/rings/lean-codex.yaml`).
  Rule S7 allows pooling only within one engine identity (Plan, erratum 10). So the pooled row covers the two
  harnesses that share `lean-b1`/`lean-b2`'s identity. It is not a three-harness answer.
- The token ratio is total pack-on tokens over total pack-off tokens. R-b2 notes that its *Pack improvement*
  section shows the median of per-pair ratios instead, so the two can differ.

## The two MDEs and the clustering caveat

- **Per harness: between 0.31 and 0.42** (Verified: the Limits note in R-b2 and R-cb2; Inferred as a range in the
  spec). 0.31 assumes 20 independent pairs. But each harness ran the same 10 tasks twice (one repeat per batch).
  Repeats of one task are correlated, so the effective sample lies between 20 pairs and 10 tasks. With 10 tasks the
  MDE is 0.42.
- **Pooled two-harness: 0.19 is a design figure.** It was computed for 60 planned pairs (three harnesses). Only 40
  were recorded (R-b2: "40 of 60 pairs recorded"), because Codex left this pool. So 0.19 overstates the power of the
  row that exists. Inferred (model: MDE scales with 1/sqrt(n), from the 0.31 at n = 20): with 40 independent pairs
  the MDE is about 0.22 (0.31 x sqrt(20/40)); with clustering down to 20 task clusters it is about 0.30 (0.42 x
  sqrt(10/20)). The measured pooled interval is ±0.18 (Verified, R-b2).

## Per property (exploratory)

*Exploratory: 4 pairs per harness per property (2 tasks x 2 batches). Not powered for any per-property finding.
The counts below are reported, not judged.* Verified: R-b2 (Claude Code, Copilot) and R-cb2 (Codex).

| Property | Claude Code, off -> on | Copilot, off -> on | Codex, off -> on |
| --- | --- | --- | --- |
| NG | 4/4 -> 4/4 (0) | 4/4 -> 4/4 (0) | 4/4 -> 4/4 (0) |
| RS | 4/4 -> 4/4 (0) | 4/4 -> 2/4 (-2) | 2/4 -> 2/4 (0) |
| RW | 4/4 -> 3/4 (-1) | 3/4 -> 3/4 (0) | 3/4 -> 3/4 (0) |
| S | 1/4 -> 1/4 (0) | 2/4 -> 3/4 (+1) | 2/4 -> 2/4 (0) |
| SM | 3/4 -> 4/4 (+1) | 3/4 -> 4/4 (+1) | 4/4 -> 4/4 (0) |

Cells are passes / recorded pairs; the bracket is the change in passes. Inferred (model: the per-harness MDE of
0.31 at 20 pairs, scaled by 1/sqrt(n) to 4 pairs, is about 0.69): a change of one or two passes in four is below
what this size can separate from chance.

## Checkpoint numbers per batch

Verified: the Limits note of each batch's report (R-b1, R-b2, R-cb1, R-cb2). The estimates beside them are the
plan's Inferred figures, as the reports print them.

| Batch | Run min / cell (est. 1.12) | Grading min / cell (est. 1.16) | Infrastructure failures |
| --- | --- | --- | --- |
| `lean-b1` | 1.27 | 0.11 | Codex 2 of 20 (model unavailable); Copilot 0 of 20; Claude Code 0 of 20 |
| `lean-b2` | 0.82 | 0.10 | Codex 2 of 20 (model unavailable); Copilot 0 of 20; Claude Code 0 of 20 |
| `lean-codex-b1` | 0.85 | 0.10 | Codex 0 of 20 |
| `lean-codex-b2` | 0.81 | 0.10 | Codex 0 of 20 |

Mean tokens per cell (estimate 1,060,000 for every combo):

| Batch | Claude Code off | Claude Code on | Copilot off | Copilot on | Codex off | Codex on |
| --- | --- | --- | --- | --- | --- | --- |
| `lean-b1` | 474,156 | 793,712 | 233,269 | 2,208,852 | not recorded | not recorded |
| `lean-b2` | 463,590 | 729,848 | 236,643 | 2,284,781 | not recorded | not recorded |
| `lean-codex-b1` | - | - | - | - | 198,809 | 441,168 |
| `lean-codex-b2` | - | - | - | - | 209,884 | 489,465 |

Grading ran about ten times faster than estimated. Only Copilot pack-on cells exceeded the token estimate.

## Tokens per harness and arm

Each figure is a per-cell mean (Verified, above) x 10 cells per batch-arm, summed over two batches. Inferred only in
one respect: the means are printed rounded to a whole token, so each product can be off by at most 5 tokens per
batch-arm.

| Harness | Pack-off | Pack-on | Total | Added by the pack |
| --- | --- | --- | --- | --- |
| Claude Code | 9,377,460 | 15,235,600 | 24,613,060 | 5,858,140 |
| Copilot | 4,699,120 | 44,936,330 | 49,635,450 | 40,237,210 |
| Codex | 4,086,930 | 9,306,330 | 13,393,260 | 5,219,400 |
| **All** | 18,163,510 | 69,478,260 | **87,641,770** | 51,314,750 |

The total is 69.0% of the operator's approval of 127M tokens (2026-10-09), and under the spec's 150M ceiling. The
Leader's figures (Claude Code 24,613,060; Copilot 49,635,450; Codex 13,393,260; total 87,641,770) match this
recomputation exactly. The 4 refused Codex cells in `lean-b1`/`lean-b2` have no token record and are not counted.

**Copilot's total is a lower bound on 8 cells.** See *Limits*, HB-VAL-005.

## Wall and machine time

Start: the Leader's start notes (L, `b1-start.txt`, `b2-start.txt`, `cb1-start.txt`, `cb2-start.txt`). End: the
`run.completed` / `grading.completed` events (E). All on 2026-10-10, UTC. Each span includes its own grading.

| Batch | Start | End | Span |
| --- | --- | --- | --- |
| `lean-b1` | 00:10:42Z | 01:26:39Z | 75 min 57 s |
| `lean-b2` | 13:58:39Z | 14:47:48Z | 49 min 9 s |
| `lean-codex-b1` | 15:24:56Z | 15:41:54Z | 16 min 58 s |
| `lean-codex-b2` | 15:42:22Z | 15:58:40Z | 16 min 18 s |

Machine time across the four batches: 158 min 22 s (2 h 38 min), run and grading together. The spec's target was
2.5 h of run plus 2.5 h of grading. The gap between `lean-b1` and `lean-b2` (about 12.5 h) is outside this figure.

## Engine identity and pack revision

Verified: L, `engine-id.jsonl`.

| Runs | Engine commit | identity_hash |
| --- | --- | --- |
| `lean-b1`, `lean-b2` | `6140844f71c222135ebbe0c62ef9d43a5512cf16` | `f12c63b87654bc9a01e3182e3402fc43121b2e56a759f8234e27253c6dde4c8c` |
| `lean-codex-b1`, `lean-codex-b2` | `f6389964b3968a8c3ca9ffeb46451af62d369f16` | `d69b43b3cf918b797b3c6688e92c2f15e651535bcbba0504be8383ec5cc93e51` |

The identity is equal within each pair, as S7 requires. It differs between the pairs.

**Pack revision (pack-on arm):** `C:/Projects/ai-forward` at `e1f8ad5e9e3d42acbbbffbde0702deed8699c019`, revision 99.
Verified: the `pack` block of all four `plan.json` files. The commit (2026-10-08) is on the ai-forward branch
`fix/xh-finish-upstream` (Verified, `git branch --contains`). The Leader calls it the F-PACK head; that label was
not checked here.

## Pre-registration

**Pre-registered.** `docs/notes/lean-preregistration.md` hashes to `af36296ebcb0` (sha256, first 12; Verified: the
file at `415bc4cc` and at this report's base both hash to it, and R-b2 and R-cb2 print the same value). It reached
`main` in merge `415bc4cc`, committed 2026-10-09T14:46:52-07:00 (21:46:52Z), and the join `47721f98` followed at
21:46:57Z; `47721f98` is on `origin/main` (Verified, `git log` and `git branch -r --contains`). `lean-b1`'s first
event is 2026-10-10T00:10:43Z (E). So the pre-registration was committed and pushed about 2 h 24 min before the first
cell. The push time itself is not recorded; it is bounded by the commit and by the next fetch that saw it.

## What changed from the plan, and why

**The Codex pin refusal.** Batch 1 refused every Codex cell it launched with HB-CELL-116. The bench pinned Codex
0.156.0, which does not serve `gpt-6.1-sol` on a ChatGPT account ("not supported when using Codex with a ChatGPT
account"); the global 0.160.0 does (the Leader's spike, `C:/tf/lean-leader/codex-spike/`). No real-model cell had run
the lean pins before batch 1. The Leader's decision D1 defaulted to `skip_combo` after 30 min, while the question
was still open with the operator. Sources: L, `owed-docs.md` item 23; Plan, erratum 10.

**The operator's ruling.** Keep `lean-b1` and `lean-b2` as run (Claude Code and Copilot; Codex skipped). Run Codex's
40 cells as their own lean pair on Codex 0.160.0, from `bench/rings/lean-codex.yaml`. The bump was a new track,
L-CODEX-PIN (merge `e10175a7`, join `f6389964`).

**The one-cell probe.** Before the pair, one cell ran through the full cell path (ACP via codex-acp 1.12.0 and Codex
0.160.0; X1 fixture, pack off). It completed and was valid (Verified: L, `codex-probe/run.txt`: "completed 1",
"valid 1").

**The consequence.** The Codex rows carry their own engine identity, and there is no three-harness pooled row.

**The build phase.**
- Nine planned tracks (L-CONTRACT, L-MATRIX, L-SUM-A, L-SUM-B1, L-SUM-C, L-FIX-TEXTIO, L-FIX-RF11, L-DOCS, L-READY),
  joined in J0-J2, plus L-CODEX-PIN after the refusal.
- Two external turns split on CEIL-A context floors: L-MATRIX on Grok (floor about 117k at the first edit) and
  L-SUM-B1 on Agy (about 166k). Both took the Opus sub-agent fallback; L-SUM-C was compiled for Opus from the start.
- Join recounts went red on flaky tests (FLAKE-A: engine no-launch[4], disc check-less-variant); LOOP-J0 measured them
  and cleared L-CONTRACT.
- Register: new classes CONSOLE-FLAG-MASKS-TEST, RED-ONE-GATE-A, HELP-A (Coordinator #64); GATE-RACE-A,
  COARSE-SEED-A, TOOL-UNPINNED-A (Coordinator #66). Instances added to CEIL-A, FLAKE-A, EDIT-B, TEST-A, HELP-A,
  DEP-A, GUARD-A, MUT-E, SERVE-A, COORD-B, GOLD-A.

## Limits

- **Two repetitions per task, correlated.** Each harness ran 10 tasks twice. The per-harness MDE is 0.31 only if the
  repeats are independent; it is up to 0.42 if they are not.
- **"No detectable effect" is not evidence of no effect.** It means the interval contains zero at this power. An
  effect below about 0.31 (per harness) could exist and go unseen.
- **Copilot HB-VAL-005 warnings (token cross-check).** On 8 of 40 Copilot cells (RW1 and RW2, both arms, both
  batches) the ACP turn total differs from the sum of `model_calls` (Verified: the validity section of R-b1 and R-b2).
  It is a warning; it does not change a cell's validity. It does affect the token figures: Copilot's token source is
  the native record (`bench/profiles/copilot.yaml`, `usage_source: native_record`), and on every one of the 8 cells
  the ACP total is higher, by 1.34x to 1.67x. Summed over the 8 cells the ACP total is 23,674,150 against 15,163,027
  in `model_calls`, a gap of 8,511,123 tokens (Verified arithmetic; total = inputTokens + outputTokens, since
  Copilot's `inputTokens` includes cache read and write, `views.ACP_TOTAL_KEYS`). Which source is right is not
  settled. Inferred (model: the ACP total replaces `model_calls` on those 8 cells): Copilot's total would be
  58,146,573, the grand total 96,152,893 (still under 127M), and Copilot's ratio of totals about 9.70x rather than
  9.56x. So the Copilot token figures here are a lower bound. The pass/fail effect is not touched.
- **Other warnings.** HB-VAL-006 (the executed-build check skipped: no recorded `agent_version`) appears on cells in
  all four reports. It flags a check that did not run; it changes no number above.
- **The pooled row.** It pools two harnesses only, and its 0.19 MDE was sized for 60 pairs (see above).
- **One model per harness, one pack revision, one account per vendor.** The result does not reach other models,
  other pack revisions or other harness builds.
