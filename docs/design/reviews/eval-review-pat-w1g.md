---
id: review-eval-pat-w1g
title: "Patterns Expert review of W1-G, catalog 0.7 (Adversary Mode)"
type: doc
status: draft
owner: "@timianmalloo"
tags: [review, patterns-expert, evaluation-campaign, wave-1, w1-g]
links:
  - { to: design-eval-seam-contracts, rel: relates-to }
review-by: "2026-10-17"
summary: >-
  RV-PAT review of design/eval-catalog-0-7 (b0987941) against W0 rev 2 and R-87..R-93. The owner rule and
  also_graded_by survive the Simplifier check; one real gap (a non-owner formal grader emitting pass_at_1 trips
  HB-GRD-004), an incomplete reader sweep for the new key, and minor idiom points. RV-TA findings are not repeated.
---

# RV-PAT review: W1-G `docs/design/eval-catalog-0-7.md` against W0 rev 2

Read in full on `design/eval-catalog-0-7` (b0987941); W0 and R-90 from `main`. Code opened: `grade/runner.py:161-168,314-368`, `grade/formal.py`, `config.py:140-176`, `pack_improvement.py:491`. Findings of RV-TA (`eval-review-ta-w1g.md`) are not repeated; its finding 8 (the `applicable` hunk claimed by W1-G and absent from W1-F) is the seam finding on `also_graded_by` and stands.

**Patterns that fit.** Special Case (`Score(None, reason)`), Strategy via the existing `GRADERS` registry, Kleene three-valued `all_of`, Parameter Object (`CellInput`), an append-only correction chain, and a labelled rebuildable cache for the stored `pass_at_1` row. The owner rule (first of `[grader, *also_graded_by]` the task names) is an ordered first-match precedence list, the smallest form of Chain of Responsibility. The Simplifier's attack (section 2) is answered with checked alternatives (duplicate id refused at `config.py:151`; a new id breaks the board primary; a list-valued `grader` breaks every `m["grader"] in graders` reader). The `simplify:` marker names the ceiling and the upgrade trigger. Mutual check: the pattern survives.

| # | location | finding | severity | evidence | fix | confidence |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 4.2 owner rule + 4.3 `formal.pass_at_1`; T-R3 | **A non-owner `formal` grader can trip HB-GRD-004.** The owner rule gives G1 `pass_at_1` to `correctness` only. `formal` is also named on G1, so `inp.metrics` for `formal` lacks `pass_at_1`. The runner records every key a grader returns that is not in `inp.metrics` as "outside" and fails the pass. The design says `grade_cell` calls `pass_at_1(task, scores)` and that G1 declares no rule (NA `no pass rule declared`), but never says the call is guarded by `"pass_at_1" in inp.metrics`. T-R3 tests `applicable` only, not a pass through `run_pass`. | major | `runner.py:350` (`self.outside.update(... out.keys() - inp.metrics.keys())`), `runner.py:358,365` (`_check_complete`); graders return mappings; design 4.2 G1 row, 4.3 "G1" | State the guard in 4.3 (emit only when in `inp.metrics`). Add a test that runs a G1-shaped task (graders `formal` and `correctness`) through a real pass and requires one `pass_at_1` row and no HB-GRD-004; it must be red against an unguarded `grade_cell`. | Verified (runner); Inferred (that `grade_cell` would emit it unguarded) |
| 2 | 3 "Writer and compute reader" (DM15); 4.2 | **The reader sweep for `also_graded_by` is incomplete.** The table lists `runner.applicable` as its only reader. Other code reads the single-owner `grader` field: `config.validate_catalog` (`:158` checks `grader` is a known module, so a misspelled name in `also_graded_by` is unvalidated and an owner never matches), the task-changed fallback that builds `names` from `m["grader"]` (`runner.py:321`), and `pack_improvement.py:491` (`m.get("grader") in task_graders`, judge ids only). A key that changes what "grader" means needs each reader named and decided. | minor | `config.py:158,176`; `runner.py:321`; `pack_improvement.py:491` | Add the three rows to the DM15 table with "unchanged because ..." or the change. Add a catalog test: every `also_graded_by` name is a known grader module, differs from `grader`, and has no repeats. | Verified |
| 3 | 4.2 code | **One line encodes two rules and shadows a builtin.** `m.get("property", property) != property` means "untagged applies, tagged must equal". It reads as a default and misreads for `property: null` or a non-string tag. The parameter `property` shadows the Python builtin (W0 section 7 fixed the name, so the cost is local). | minor | design 4.2 code block | Name it: `tag = m.get("property")` then `if tag is not None and tag != property: continue`. If the W0 name must stay, say so in the amendment text. | Verified (text) |
| 4 | 4.3 semantics table | **Rows 3 and 5 overlap and the precedence is undefined.** An input that is "absent" (row 3, reason `pass rule input not recorded`) and one "not in `inp.metrics`" (row 5, reason `pass rule names an unrecorded metric`) are the same state seen from two sides. Row 2 says any recorded 0 decides; it does not say whether an unknown metric name beats a 0. Two reasons for one state is the two-definitions signature. | minor | design 4.3 table | State an order: (1) unknown name is a rule error (readiness already refuses it, `pass_rule_problems`), NA with row 5's reason; (2) any 0; (3) any NA; (4) all 1. Or drop row 5 and let row 3 carry it. One test per order. | Verified (text) |
| 5 | 4.1 `property:` tags; T-C4 | **The five property names live in three places.** Catalog tags, a task's `property.name`, and W1-F's `STRATEGIES` registry. T-C4 hard-codes "the five names" as a literal. A sixth property needs three edits and one test change. | minor | design 4.1 entries; T-C4 row; R-90 cond. 4 (STRATEGIES) | Make `STRATEGIES` the one list; `validate_catalog` (the seam already adds the skeleton) checks each tag against its keys, and T-C4 asserts that link instead of a literal. | Inferred (W1-F text not re-opened here) |
| 6 | 4.2 worked cases, last row | **The owner of one metric flips with task state.** For a current G2 task `pass_at_1` is recorded by `formal`; in the task-changed fallback every catalog grader is "named", so the owner is `correctness` and the NA lands in the `correctness` evidence folder. One (cell, metric) is owned by two graders depending on whether the task hash matched. Consistent with grid-3, but the evidence path moves. | minor | `runner.py:318-321`; design 4.2 last row | Say so in the amendment and in 4.3's evidence-path sentence, or have the fallback skip owner dispatch. A test pins the folder. | Verified (code); Inferred (impact on evidence readers) |
| 7 | 4.5 `corrected_from` | **The current value is overwritten in place and the history sits beside it.** `board_golden` holds the newest hash; `was` holds the old one. The repo's preference (DM5) is the fact appended, with the current value derived. The chain control makes this safe and ADR-0019 item 4 asks for the mechanism, so the pattern survives. "Expected use: none" means it ships exercised only by a synthetic file. Advisory. | minor | design 4.5 "Expected use: none" | Keep; add a `simplify:` marker (ceiling: one chain, one key kind; trigger: the first real correction). | Inferred |
| 8 | 4.2 `also_graded_by` | Owner rule and the single optional key confirmed as the smallest correct form. No change. | nit | design section 2 table; `config.py:151` | none | Verified |

**Seam disagreements (E2E-D).** W1-G 4.2 and 12 vs W1-F `applicable` (parameter `prop`, no `also_graded_by`): recorded as RV-TA 8. Add only that W0 section 7 condition 1 names the parameter `property`, so W1-F is the outlier. No other disagreement with W0 rev 2 or R-90 conditions 1, 4, 5 found.

**Residual risk.** Finding 1 fails a pass only on the G1 shape, which no test in section 11 builds.

GATE W1-G · Patterns Expert · PASS WITH CONDITIONS · 8 findings (rv-pat-gb-e1e4, 2026-10-03)

Conditions: finding 1 before X-G3 starts; finding 2 with the seam; 3 to 7 may be recorded. Advisory lens; RV-TA's BLOCK stands independently.
