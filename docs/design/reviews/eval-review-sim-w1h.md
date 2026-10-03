---
id: review-eval-sim-w1h
title: "Simplifier lens review of W1-H, power, verdicts, gates and report section 3"
type: doc
status: draft
owner: "@timianmalloo"
links:
  - { to: design-eval-seam-contracts, rel: relates-to }
review-by: "2026-10-17"
summary: >-
  RV-SIM (Simplifier, soft veto) findings on docs/design/eval-power-verdicts.md (design/eval-power-verdicts,
  2a9faa3c, b5509d66) against W0 rev 3 and R-87..R-96. The core is the smallest correct shape. About a third of the
  label, statement and sweep rows duplicate another row's mutant; one seam with W1-C (pilot arity, admission) is open.
---

# Simplifier review: W1-H power, verdicts, gates, report section 3 (rv-sim-hc-e1e4)

Target: `docs/design/eval-power-verdicts.md` on `design/eval-power-verdicts` (`2a9faa3c`, `b5509d66`), against W0 rev 3 and R-87..R-96 on `main`. RV-TA's findings (`eval-review-ta-w1h.md`) are not repeated; where a row below overlaps one, the TA number is cited. Verified = read in the documents or the tree; Inferred = reasoned.

## The author's question: is each row earning its place?

A row earns its place when it separates a mutant that no other row separates. Counted against that rule:

| group | count | earn their place | delete or merge |
| --- | --- | --- | --- |
| `label_for` rows | 13 | 11 | L12, L13 |
| `statement_for` rows | 10 | 6 (D1, D2, D3, D5, D9, D10) plus D6 with D7 folded in | D4, D8 (D7 merged into D6) |
| gate kinds | 10 (summary says nine) | 9 | merge `cell-failed` with `infrastructure-cell` |
| sweeps S-1..S-5 | 5 | 1 (S-2) | S-1 becomes an invariant; S-3, S-4, S-5 deleted |
| hypothesis tests | 6 | 3 (conservation, order independence, MDE round trip) | label "exclusive" half, monotone, determinism |

## W1-H findings

| # | location | finding | severity | evidence | fix | confidence |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 11.2 L12, L13 | L12 (-0.50, 0.50 -> UNDERPOWERED, mutant "rule 5 default changed") is the same fall-through that L3, L4, L8 and L9 already reach, so every one of them kills that mutant. L13 (n 0, min 0) admits in its own text that it is caught by "the empty-stratum rule, not this one" and that its mutant is "also L2". | minor | 11.2 table, L13 "distinguishes" cell; L3/L4/L8/L9 expect UNDERPOWERED | Delete L12 and L13. 11 rows remain, each with a mutant no other row has. | Verified |
| 2 | 11.2 D4, D7, D8 | D4 repeats D2's boundary (`hi < 1` -> `<=`) on the other label; `statement_for` has one `hi < 1` expression (section 5), so one mutant, two rows. D8 names the mutant "statement uses `lo`" but lo 1.2 makes `lo < 1` false, so the mutant still returns "better at"; the row cannot kill it. D10 (lo 0.8) does. D7 and D6 differ only by label, and the rule is one set-membership test. | minor | section 5 `statement_for`; D8 `lo 1.2`; D10 `lo 0.8, hi 1.4` | Delete D4 and D8. Fold D7 into D6 as a `non-directional` parametrize id. Same coverage, 3 fewer rows. Matches TA 1 (D8 attribution). | Verified |
| 3 | 3.1 vs 5, summary | Count error: summary and the brief say nine gate kinds; the `GateKind` enum has ten. Separately, `cell-failed` and `infrastructure-cell` split one EV-14 bullet ("a cell ends blocked, failed or with an infrastructure-classified cause"), and the operator action is the same (a cell is lost; read the cause). The split costs a precedence test (`test_gate_infrastructure_beats_failed`) and a first-match rule. | minor | section 3.2 enum (10 members); `docs/specs/enterprise-evaluation.md` EV-14 first bullet | Correct the count. Merge into one kind `cell-lost` with the cause in `detail`; drop the infrastructure-beats-failed test. TA 4 already shows the bnd-a/infrastructure pair has an equivalent mutant. | Verified |
| 4 | 11.5 S-1, S-3, S-4, S-5 | S-5 is "listed only so the trace is complete": no root, token or allowlist, owned by X-D. Delete it. S-4 scans string constants in `gates.py`, but only values the code returns reach a reader; `test_regression_strings_carry_no_verdict_words` and `test_evu_6` already assert the values and the DOM. S-3 says of itself "vacuous until they exist"; the regex `attribution ==` is brittle, and `test_ratio_not_recorded_*` (F12) already fails if someone sums raw tokens instead of `views.sum_tokens`. S-1 ("no module other than `verdicts.py` assigns or returns a `VerdictLabel`") is better stated as a behavioural invariant: for every `Verdict` from `verdict()`, `label == label_for(n_pairs, min_pairs, lo, hi, mde)`. That fails for any other path, with no allowlist to rot. | minor | 11.5 table; 11.3 `test_regression_strings_carry_no_verdict_words`; 11.4 `test_evu_6` | Keep S-2 only (the word `dominates` is the highest-stakes claim). Replace S-1 by the invariant inside `test_input_order_never_changes_a_verdict`. Delete S-3, S-4, S-5. | Verified |
| 5 | 11.5 S-2 | The allowlist constant `DOMINATES_ALLOWED = {"verdicts.py": any, ...}` uses the builtin `any` as a "no limit" sentinel. It reads like code, tests nothing, and a `None` or a missing key would behave the same under a careless edit. | minor | 11.5 S-2 | Use a set of `(file, string)` pairs, `{("verdicts.py", "dominates"), ("report/campaign_section.py", "No arm dominates another.")}`. Keep the "stale entry fails" rule for this one allowlist. | Verified |
| 6 | 11.1, 11.2 hypothesis | Four tests cannot fail on a mutant the table or references do not already kill. (a) `test_label_for_is_total_and_exclusive`: a pure function returns one value, so "two different labels for one input" is impossible; the implications restate rules 2 to 5 and duplicate L2..L11. (b) `test_monotone_properties` tests `NormalDist`; `m` ignored is killed by the 115 and holm rows. (c) `test_determinism_two_runs_identical` runs an arithmetic function twice; its "iteration over a set" mutant has no set (section 5). (d) `test_result_round_trips_through_json` has an empty assertion cell. | minor | 11.1 rows named; 11.2 hypothesis paragraph | Delete (a) to (d). Keep `test_mde_roundtrip_property` (it pins the bisection bounds) and the golden in `test_golden_interval_and_draws`. | Verified |
| 7 | 3.2 `PowerResult.descriptive`, 11.1 | `descriptive {sd, rep_spread}` is added to the result only to echo two inputs that section 5 says are "not used for sizing in E1", plus a test that changing them leaves `n` unchanged. The graded-primary case is out of scope (DR-E5). W0 section 8 already lists `sd` and `rep_spread` as inputs, so validating them is enough. | minor | section 5 Power ("echoed ... and not used"); W0 section 8 inputs | Drop `descriptive` and `test_sd_and_rep_spread_do_not_change_n`; keep input validation. Upgrade trigger: a graded primary enters scope. | Verified |
| 8 | 3.2 `collect(primary=...)`, 5 Verdict, F11 | `collect` takes a `primary` parameter whose only value is `property_check_pass` (W0 section 2: int 0/1, untagged), and metric values are scaled to 10^4 with an off-scale refusal (F11, `test_off_scale_value_is_refused`). The scale is "the catalog's finest scale", which matters for graded primaries only. | minor | 3.2 signature; section 5 "scaled to integers at 10^4" | E1: accept only 0 or 1 and refuse anything else with HB-USR-002; drop the parameter. Keep `Pair` as `Decimal` (W0). Upgrade trigger: a graded primary in a verdict. | Inferred (the 10^4 path may be wanted for tokens; tokens are ints already) |
| 9 | 5 Collecting pairs | `collect` returns `na_counts` and `excluded` separately and `verdict` takes both. `na_counts` is a count of `excluded` reasons that came from the primary's NA; two definitions of one quantity (DM7), and a parameter more. | minor | 3.2 `collect`, `verdict` signatures | Tag each `excluded` entry with `na: bool` (or keep NA reasons in one list) and derive `na_counts` inside `verdict`. | Inferred |
| 10 | 3.2 / 5 vs W1-C sections 5, 14 (seam) | **Seam disagreement.** W0 section 8 gives `pilot(view, hidden_test_disagreements, unbiased_failures)`. W1-H makes it `pilot(view, hidden_test_disagreements, unbiased_failures, expected_na)` (provisional, seam `req-01M41EX52AX93PQS1FHYCSA0YG`). W1-C's `pilot pass` calls `gates.pilot(view, disagreements)` "with the third parameter" and never mentions `expected_na`, so it cannot call W1-H's function. W1-H is also silent on OI-2 and OI-3: `VerdictSpec.tasks` is "the admitted tasks", but nothing says who computes saturation or where W1-C's `admission.decided` rows reach `collect`; W1-H sizes with `len(tasks)` of the power inputs (pre-admission), W1-C's coverage reads admitted tasks. | major | W0 section 8 `pilot`; W1-H 3.2 `pilot`; W1-C section 5 `pilot pass`, section 14 OI-2/OI-3 | Coordinator rules one arity (give `expected_na` a default of `{}` so the W0 call is valid, or W1-C passes it from the inputs file). W1-H states one admission input to `VerdictSpec.tasks` and says power sizes on the pre-admission tasks (a note, not a new field). | Verified |
| 11 | 6 R-93 state table | Correct under R-96 ruling 2 (three states, never share a `data-kind`). Not a complexity finding; recorded so the R-H3 flag in section 13 can be closed by R-96, and the section 13 row removed. | minor | `docs/notes/rulings.md` R-96 ruling 2 | Delete R-H3 from section 13 and cite R-96. | Verified |

## What earns its place (kept deliberately)

- **No aggregate, no store, no verdict cache.** Derived-on-read with a measured cost and a named upgrade trigger is the right rung (ladder: YAGNI, reuse).
- **`label_for` as the single decision function.** One place per rule order is what makes the 11 remaining label rows cheap.
- **The 93 / 53 / 115 pins with the seeded-wrong variant,** and the conservation test over real `CellView`s: the two checks that guard the headline numbers and the NA rule.
- **`holm` mapped to alpha/m (R-96).** One definition (`alpha_per_test`), no step-down.
- **The R-93 line with its DOM tests.** Small, asked for by a ruling.

Blocking: none. Soft veto not exercised. Finding 10 is a seam between W1-H and W1-C and needs one Coordinator ruling before X-H1 and X-C start; findings 1 to 9 are deletions the author can apply in the follow-up.

GATE W1-H · Simplifier · PASS WITH CONDITIONS · 11 findings (rv-sim-hc-e1e4, 2026-10-03)
