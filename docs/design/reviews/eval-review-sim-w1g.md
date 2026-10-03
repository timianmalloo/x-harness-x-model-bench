---
id: review-eval-sim-w1g
title: "Simplifier lens review of W1-G, catalog 0.7"
type: doc
status: draft
owner: "@timianmalloo"
links:
  - { to: design-eval-seam-contracts, rel: relates-to }
review-by: "2026-10-17"
summary: >-
  RV-SIM (Simplifier, soft veto) findings on docs/design/eval-catalog-0-7.md (design/eval-catalog-0-7, b0987941)
  against W0 rev 2 and R-87..R-93 on main. also_graded_by is the smallest correct mechanism; the (e) exception and
  corrected_from record are built for a case the design itself shows cannot occur.
---

# Simplifier review: W1-G catalog 0.7 (rv-sim-gb-e1e4)

Target: `docs/design/eval-catalog-0-7.md` on `design/eval-catalog-0-7` (`b0987941`), against W0 rev 2 section 7 (R-90 conditions 1, 5, 6) on `main`. RV-TA's findings (`eval-review-ta-w1g.md`) are not repeated. Verified = read in the documents; Inferred = reasoned.

## W1-G: catalog 0.7

| # | location | finding | severity | evidence | fix | confidence |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 4.2, section 2 `simplify:` marker | `also_graded_by` is the smallest correct way to meet ADR-0019 item 3. The four alternatives are each worse on the design's own evidence: a duplicate id is refused (`config.py:151`), a new id breaks the board primary, `correctness` on G2 is NA forever, a list `grader` breaks every `m["grader"] in graders` reader. Kept. One gap: the marker defers validation until a second user, but a typo in a grader name silently means "no owner", so `pass_at_1` is never recorded and nothing fails. | minor | design F2, section 2 attack answer; 4.2 code (`owner is None` is skipped, no error) | Validate at once, two lines in `validate_catalog`: each `also_graded_by` entry is a registered grader. This is not a second use, it is the missing guard on the first. T-C4 can carry the case. | Verified |
| 2 | 4.5 (e) exception, `corrected_from`, T-U4..T-U7, FM8/FM9, section 3 writer row | Built for a case the design proves cannot occur. F7: `board.export` does not import `pack_improvement` and both fixtures hold no scenario-7 cell, so the `_passed` fix cannot move a committed 0.6 golden. Section 4.5 then says "Expected use: none". The price is a five-clause grammar added to the freeze control, a new record shape, a `--correct` flag that does not exist (TA 9), a printed-chain line, and about seven tests (T-U4..T-U7) that TA already finds under-tested (TA 3, 4). Those TA findings disappear if the mechanism is not built now. | major | design F7, 4.5 "Expected use: none", section 14 U7; the W1-G plan row lists the record as a done-when item | Keep the record shape and clauses (i)-(v) as a written contingency in the doc. Build nothing until the X-G3 before/after run shows a moved hash (the design already says the Leader decides from measured hashes). Coordinator ruling needed, because the plan row names the record. If kept, ship the smallest form: (e) allows only an appended record whose `was` equals the base value, with T-U5 and T-U6, not five clauses and seven tests. | Verified |
| 3 | 4.2 vs W0 rev 2 section 7 conditions 1 and 6; section 12 "decision requests: none" | Seam disagreement. W0 condition 1 defines `applicable` as one behaviour (tag narrowing; "an untagged metric always applies"). W1-G adds a second behaviour, owner resolution, so one function now carries two rules. Condition 6 says scenario-7 `pass_at_1` "is untouched"; W1-G edits that catalog entry (adds `also_graded_by`, which changes `catalog_hash`). Both can be right (ADR-0019 item 3 demands formal records it), but the design files this as "a narrowing, not a widening" with no decision request. It widens condition 1 and contradicts condition 6 as written. | major | W0 `eval-seam-contracts.md` section 7 lines 323-330; W1-G section 12 row "decision requests: none", section 3 Migration ("`pass_at_1` gains `also_graded_by`") | File a decision request to the Coordinator (an amendment note to W0 conditions 1 and 6), not only a seam request that X-F may or may not land. The section 12 fallback ("design as written; X-G3 reopens") leaves tracks building against an unruled function. | Verified |
| 4 | T-R4 and T-U3 (Control 2) | Two tests prove the same thing: a formal-only task gets one `pass_at_1` row from `formal`. T-R4 is the runner-level case; T-U3 builds a synthetic run with a stub formal grader to show GradedOncePerPass stays green. T-R1 already asserts the pass completes for the narrowed case. | minor | section 11 T-R1, T-R4, T-U3 | Fold T-U3 into T-R4 by making T-R4 a real `run_pass` over the stub grader; drop the separate fixture. Keep T-F8 (real Lean). | Inferred (T-R4 body is not specified) |
| 5 | 4.5 "Provenance of the 0.6 side", T-C3 | A committed copy of the 0.6 `metrics.yaml` plus two tests (hash of the copy; per-entry equality except `pass_at_1`) keeps 0.6 honest once 0.7 is current. Weight 0 and check (b) already stop an unnoticed 0.6 edit in the commit that frees 0.7. The copy is a second source of 0.6 truth with value for one release. | minor | 4.1 "Weight 0 ... skips them", T2 in section 7 | Compare against `git show <0.6 freeze commit>:bench/metrics.yaml` inside the test, or drop the per-entry test and keep the hash test. No committed copy. | Inferred |
| 6 | 4.3 pass-rule table, FM1, T-F4, T-F5, `pass_rule_problems`, `formal.json` mutant "`any_of` for `all_of`" | The rule is data (`all_of: [3 ids]`) with one user (G2) and one operator. The "rule names an unrecorded metric" row, its readiness check and its test exist only because the rule is data. The mutant `any_of` mutates an operator that does not exist. Data is defensible: it puts the rule inside the task version hash (S1, T-F7). | minor | 4.3, section 6 FM1, section 10 | Accept the data form; delete the `any_of` mutant; test the unrecorded-metric case in one place (readiness), not in both the grader and readiness. | Verified |
| 7 | 4.1 anchors for five count metrics | Five anchors are admitted guesses ("provisional until the E4 records"): `idempotency_violations`, `hallucinated_symbol_errors`, `new_abstractions`, `new_dependencies`, `size_vs_reference`. The same section says inventing a range would be the guess R-79 item 2 corrected. W0 section 7 does say W1-G fixes anchors, so a `convention:` form is allowed, but each wrong guess costs a catalog version to fix, and weight 0 means they rank nothing. | minor | 4.1 notes; section 14 U2; W0 line 323 | If `validate_catalog` accepts a weight-0 metric with no anchor (the design marks it Inferred), omit the five and add them at 0.8 with measured values. If not, keep as written. Check the validator first. | Inferred |

**Kept as earning their place:** the no-new-area decision (F1), the Kleene pass rule and its evidence file, `_pass -> bool | None` with the recorded-pairs filter, the cross-version regrade (F5), and the telemetry table.

**Seam disagreements:** W1-G 4.2 and 12 vs W0 rev 2 section 7 conditions 1 and 6 (finding 3). The W1-F `applicable` mismatch is TA 8 and is not repeated.

Blocking: none. Soft veto not exercised. Findings 2 and 3 should be resolved by the Coordinator before X-G3 starts.

GATE W1-G · Simplifier · PASS WITH CONDITIONS · 7 findings (rv-sim-gb-e1e4, 2026-10-03)
