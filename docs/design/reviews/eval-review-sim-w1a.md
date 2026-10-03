---
id: review-eval-sim-w1a
title: "Simplifier lens review of W1-A, arms v2"
type: doc
status: draft
owner: "@timianmalloo"
links:
  - { to: design-eval-seam-contracts, rel: relates-to }
review-by: "2026-10-17"
summary: >-
  RV-SIM (Simplifier, soft veto) findings on docs/design/eval-arms.md (design/eval-arms, ab13f0eb) against W0 rev 2
  and R-87..R-93 on main. The hash-keyed blocked order with a bounded redraw earns its place; HB-PLN-004 and G1 earn
  theirs. Three tests and one comparison table are weight that can go.
---

# Simplifier review: W1-A arms v2 (rv-sim-ad-e1e4)

Target: `docs/design/eval-arms.md` on `design/eval-arms` (`ab13f0eb`), against W0 rev 2 and ADR-0014 section 4 on `main`. Filed seams SR-2, SR-3 and the two W0 errata are not re-raised. Verified = read in the documents; Inferred = reasoned.

## W1-A: arms v2

| # | location | finding | severity | evidence | fix | confidence |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 3.4 hash-keyed order + redraw | Earns its place. Hash keys are the stdlib rung and replay on any Python (no `random.shuffle` dependence). The redraw is the ADR's own "asserts the bound and refuses" applied to the seed, and the 25 % first-draw failure at the pilot shape is measured (SP-A2), not assumed. ADR-0014 rejected the plain permutation because "a seed can fail the 5 % bound"; the redraw is the missing half of the chosen option. | none | eval-arms.md 3.4 table; ADR-0014 line 63 | none | Verified |
| 2 | 3.4 / 4 alternatives | The rejected-alternatives column omits the one simpler rival: a seeded base arm permutation rotated by block index (Latin-square counterbalance). It balances by construction, needs no redraw loop, no `MAX_DRAWS`, no `draw_launch_order` and no `secrets` default. It costs a predictable period-A pattern inside the arm order, which the ADR's "seeded random order" forbids. The doc should say that in one line so the choice reads as made, not missed. Block order does not affect the bound (every arm shares the block starts), so only within-block arm order needs the draw. | minor | 3.4 `launch_order` and `launch_balance` definitions; the table shows 1.00 pass from 6 blocks up | add the rotation to section 4 "rejected alternatives" with the ADR sentence as the reason | Inferred (the block-start claim is arithmetic on the definition, not run) |
| 3 | 3.4 pass-rate table | Eight rows of pass rates, mean draws and max draws, with a 2,000-seed run behind them. Two facts carry the decision: the pilot shape fails 25 %, and one block is unsatisfiable. The 2 x 3 row is the 40-draw ceiling for `MAX_DRAWS`. The other rows are evidence for a cap that already has a `simplify:` ceiling. | minor | rows 4 x 2, 6 x 2, 3 x 3, 6 x 3 | cut to the pilot, 1 x A and 2 x 3 rows; the spike script stays the record | Verified |
| 4 | 3.5 HB-PLN-004 | Earns its place. It replaces a raw `FileNotFoundError` (`plan.py:151` reads `prompt.md` unconditionally) with a named refusal, and option A states readiness once, in `task.yaml status` (DM7), rather than in a BOM field. Measured: `bom.subset: full` selects a stub today. The two-kind rule (discrimination accepts `draft`) is forced by EV-7, not speculative. One part is polish: "names every offender, first 12 then a count" is a formatting rule with no failure behind it. | minor | 3.5 bullets 1-3 | name every offender; drop the 12-cap and its test arm | Verified |
| 5 | 3.8 / 10 G1 | The guard earns its place: ADR-0014 section 2 promises it, three readers were found outside the allowlist, and the regex form was shown to over-match (`formal.py:256`). AST over regex is the `test_architecture.py` style, not a new mechanism. The E1 allowlist of seven files is migration scaffolding with a stated narrowing (E3 to `plan.py`); that trigger is real. | none | 3.8 table and bullet 1 | none | Verified |
| 6 | 10 test map, G1 rows | Four G1 tests where two catch distinct failures. `test_the_guard_ignores_comments_and_docstrings` is the comment-only file already in `test_the_guard_flags_each_form_in_a_fixture_tree` (3.8 red-first fixture says "one comment-only file"). `test_allowlist_is_exactly_the_e1_set` pins a constant to a copy of itself and fails only on a deliberate edit; E3's narrowing would then edit it twice. | minor | 3.8 "Red-first fixture"; 10 trace table, G1 row | keep the fixture test and the real-tree test; drop the other two | Verified |
| 7 | 10 trace table, last row | `test_plan_py_imports_no_campaign_or_identity_module` duplicates the G3 import lint that X-D owns in `test_architecture.py` (the row cites both). Two owners for one rule drift. | minor | 10 last trace row; W1-D 8 (G3) | keep only X-D's G3 entry; delete the plan.py copy | Verified |
| 8 | 10 mutants | Five new mutants plus two re-pointed ones on top of the unit tests. The balance, unbound-role and not-ready mutants each name a failure with its own test; "sort blocks by the wrong key" has no balance consequence (finding 2) and "keep `pack` under another name" repeats the ingredient-key test. | minor | 10 "Other nodes" | keep three: drop the balance check, drop the unbound-role check, drop the not-ready check | Inferred |

**Seam disagreements:** none new. The `launch_seed=` one-attempt mode (3.4) is needed for replay and tests; it stays.

Blocking: none. Soft veto not exercised. The design is the smallest correct shape for the bound; the conditions are trims, not redesign.

GATE W1-A · Simplifier · PASS WITH CONDITIONS · 8 findings (rv-sim-ad-e1e4, 2026-10-03)
