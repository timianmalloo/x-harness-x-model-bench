---
id: review-eval-pat-w1h
title: "Patterns Expert review of W1-H: power, verdicts, gates, report section 3 (Adversary Mode)"
type: doc
status: draft
owner: "@timianmalloo"
tags: [review, patterns-expert, evaluation-campaign, wave-1]
links:
  - { to: design-eval-seam-contracts, rel: relates-to }
review-by: "2026-10-17"
summary: >-
  RV-PAT review of docs/design/eval-power-verdicts.md (design/eval-power-verdicts, 2a9faa3c, b5509d66) against W0 rev 3
  and R-87..R-96. The design predates R-96; the holm level_rule disclosure and its second test row are missing. Six
  findings, no blocking, gate PASS WITH CONDITIONS.
---

# RV-PAT on W1-H (session `rv-pat-hc-e1e4`, 2026-10-03)

Read from `design/eval-power-verdicts` at b5509d66 (452 lines), W0 rev 3, `docs/notes/rulings.md` R-93 and R-96, and `stats.py`.

| # | location | finding | severity | evidence | fix | confidence |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | s3.2 `alpha_per_test`; s11.1 `test_holm_is_sized_like_bonferroni`; s13 R-H4 | R-96 condition 1 is not met. The design has no `level_rule` field and no legend sentence; R-H4 still reads "open, recommendation A". `holm` maps to the Bonferroni level correctly (one function), but a reader of section 3 is not told that no step-down ran. | major | R-96 cond. 1: carry `alpha_per_test` and a `level_rule` string, "alpha/m (Bonferroni; Holm's first step)"; grep `level_rule` in the design: 0 hits | Add `level_rule` to `PowerResult` and `Verdict`, derived beside `alpha_per_test` from one table keyed by method, so the two names cannot diverge. Print it in the legend beside the level. Close R-H4 citing R-96. | Verified |
| 2 | s11.2 | R-96 condition 2 asks for a second row: the verdict interval endpoints under `holm` equal those under `bonferroni` for the same seed and pairs. Only the sizing test exists. The mutant `holm -> alpha` must fail both. | major | R-96 cond. 2; design line 252 is the sizing row only | Add `test_holm_verdict_interval_equals_bonferroni`; add the mutant to `tests/mutations/verdicts.json`. | Verified |
| 3 | s3.2 `pilot(view, hidden, unbiased, expected_na)` against W0 s8 and W1-C s5 `pilot pass` | **Seam disagreement.** W0 s8 gives `pilot` three parameters. W1-H gives it four (`expected_na`, provisional on `req-01M41EX52AX93PQS1FHYCSA0YG`). W1-C `pilot pass` calls `gates.pilot(view, disagreements)` plus the third and names no source for `expected_na`. Until the seam is answered, X-H1 and X-C code against different arities. | major | W1-H line 106; W1-C line 196 | Coordinator rules the arity in one place; both designs cite it. Keep `expected_na` a keyword defaulting to empty so the W0 three-argument call stays valid. | Verified (both docs opened) |
| 4 | s13 R-H1 | W1-H asks X-C to warn when `min_pairs` is below the power-required n. W1-C `register` has no such check. The request lives in a risk table only. | minor | W1-H line 416; W1-C s5 `register` refusal list | Raise it as a seam item to W1-C, or state it is out of scope. | Verified |
| 5 | s11.2 row L13 | `label_for(0, 0, ...)` returns `NO_DIFFERENCE`. A registered `min_pairs` of 0 switches off the "not recorded" rule for an empty set; the empty-stratum rule is the only backstop. | minor | design line 284 | Refuse `min_pairs < 1` at `VerdictSpec` construction (HB-USR-002) with a red fixture, or drop L13. | Verified |
| 6 | s4 pattern table | "Specification" names a decision table. Specification is a composable predicate object. The code is one ordered-rules function, which is the right idiom; only the name is off. The `GateKind` table-of-checks is correctly named. | minor | design line 145 | Rename to "Decision table, one function". No code change. | Verified |

**R-93 and R-96 outcomes.** The three-state line (list, empty, `None`) is in the design and is now ruled as R-93 read with IO; R-H3 closes. The pattern holds: one reader, three states, two elements that never share a `data-kind`. The `holm` mapping is correct and not a silent alias once finding 1 lands. A Holm step-down stays out (R-96 refused option B); the ladder cut is sound.

**Pattern checks that passed.** Pure functions over frozen value objects, keyed streams per quantity (`stats.rng`), one `label_for`, one `statement_for` (sweep S-2 enforces it), Parameter Object for `VerdictSpec`. The verdict cache and Holm are already cut, so nothing here is left for the Simplifier to remove.

GATE W1-H · Patterns Expert · PASS WITH CONDITIONS · 6 findings (rv-pat-hc-e1e4, 2026-10-03)
