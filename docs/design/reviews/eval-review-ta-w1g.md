---
id: review-eval-ta-w1g
title: "W1-G catalog 0.7 design review: Test Architect lens"
type: doc
status: draft
owner: "@timianmalloo"
phase: "Enterprise evaluation: Wave 1 gate reviews"
tags: [review, test-architect, evaluation-campaign, wave-1, w1-g]
links:
  - { to: design-eval-seam-contracts, rel: relates-to }
review-by: "2026-10-17"
summary: >-
  Test Architect (Adversary Mode) review of W1-G against W0 rev 2 and R-87..R-93. The three-valued _pass fix and the
  pass rule are well tested. BLOCK on three controls that cannot fail as specified: the cross-version regrade (no red
  case, and the 0.6 golden's digest is checked by nothing once 0.7 is current), and the (e) exception (clause v and
  others untested, commit check is a regex).
---

# Test Architect review: W1-G `docs/design/eval-catalog-0-7.md` (branch `design/eval-catalog-0-7`, `b0987941`)

Session `rv-ta-w1g-e1e4`, 2026-10-03. Checked against W0 rev 2 section 7 (conditions 1, 5, 6), R-86, R-90, and the code opened for this review: `tests/test_catalog_version.py` (`us4_problems`), `runner.py:108-112` (`catalog_hash`), `pack_improvement.py:950-1260`, `board.py:470-490`, `cli.py:349-356`, `tools/freeze_catalog.py`, `tests/fixtures/catalog/0.6/*`. Verified = I opened or ran it; Inferred = reasoned.

## The five points the author flagged

| point | result |
| --- | --- |
| Cross-version regrade replaces self-referential (a) | Right move (F5 holds: (a) compares a fixture with the golden of the *current* version). **Not yet a control that can fail**: findings 1, 2, 5. |
| Narrow exception to (e) | Needed (F6 holds). **Under-tested**: findings 3, 4. |
| `_pass()` three-valued fix vs every pass-count/Fisher site | Core design is sound and T-P1..T-P5 are red-first. **Sweep incomplete**: finding 6. |
| Correction chain tested only on a synthetic freeze file | Accepted. F7 holds (Verified: `board.py` does not import `pack_improvement`; the 0.6 views export has no pass rows from it). A synthetic `frozen` fixture is the right place, if findings 3 and 4 are met. |
| "bench verify shows the chain" replaced by a printed chain | Accepted. Verified: `cmd_verify` calls `views.verify` on a run and never reads the freeze file (`cli.py:349-356`). The printed line is only a control if T-U7 asserts it (it does, via capsys). |

## Findings

| # | location | finding | severity | evidence | fix | confidence |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 4.5 Control 1; T-U1, T-U2 | **No test makes Control 1 or T-U2 fail.** Both are green on arrival, so nothing shows they would catch a moved 0.6 score. T-U2 asserts that property ids are absent from an export of a task that cannot have them. Also, the two 0.6 goldens are byte-identical (`cmp heads.export c44dd2b-no-heads.export`), so the control rests on one export. | blocking | `tests/fixtures/catalog/0.6/` (cmp: identical); section 11 has no red case for T-U1/T-U2 | Add the negative tests: (i) monkeypatch one X1 grader to move one 0.6 value (or set a property metric weight above 0 in a copied root) and require T-U1 red; (ii) a 0.7 root where a property grader is wrongly named for the X1 tasks, requiring T-U2 red. Observe both red before the fix is called done. | Verified |
| 2 | 4.5 "Provenance of the 0.6 side"; T-C3 | **The 0.6 golden is no longer protected once 0.7 is current.** Check (c) globs `golden/<current version>` only, so after 0.7 nothing checks the digests in `versions['0.6'].golden`. The design says the golden is pinned "check (c)", which is true only while 0.6 is current. Regenerating `tests/fixtures/catalog/0.6/*.export` from 0.7 output would pass Control 1 (GLD-A, the exact class the design cites). Separately, `catalog_hash` covers `bench/metrics.yaml` **and** `bench/rubrics/*` (`runner.py:108-112`; `adr_quality.md` exists), so the committed 0.6 `metrics.yaml` copy alone cannot hash to the pinned value and T-C3 can never go green. | blocking | `us4_problems`: `files = sorted(... (golden / version).glob("*.export") ...)`; `runner.py:108-112` | Control 1 hashes the 0.6 goldens and requires equality with `versions['0.6'].golden` (and the board digests, if finding 5 is taken). Add a red test: edit a 0.6 golden, expect red. Commit the 0.6 rubrics beside the `metrics.yaml` copy, or build the hash root from both. | Verified |
| 3 | 4.5 (e) exception, clauses (i)-(v); T-U4..T-U6 | **Four of five clauses have no failing test.** T-U5 covers a rewrite with no record and a skipped link (ii). T-U6 covers a missing class (iv). Nothing covers (v): a valid correction record appended **together with a `catalog_hash` or `golden` edit** passes if (v) is deleted. Nothing covers (i) (an earlier record removed or reordered) or (iii) (new value equals `was`). A mutant that drops (v) survives, and (v) is the clause that stops the exception becoming a general overwrite. | blocking | section 11 T-U4..T-U7 | Add one red test per clause: valid record plus changed `catalog_hash` (v); truncated or reordered earlier record (i); `was == now` (iii). Add the mutants to `tests/mutations`. | Verified |
| 4 | 4.5 clause (iv); FM9, R1 | `commit` is only checked to be hex. Any 40-hex string passes, so "attributable cause" (R1) is not enforced. `defect_class` is checked against the register, which is fine. | major | 4.5: "`commit` is a hex sha" | Require `git cat-file -e <sha>^{commit}` in the control, with a red test for an unknown sha. A worker cannot then invent a cause. | Verified (design text) |
| 5 | 4.5 Control 1 | Control 1 compares the **views** export only. The board export is the surface that iterates `cat.areas` (`board.py:550, 770`), so a weight-0 entry in `correctness` and `rigor` is the likelier place for bytes to move; F1 asserts it does not and nothing checks. | major | design F1; `board.py:550, 770` | Compare the 0.7 board export with the 0.6 board golden (dropping `catalog_version` only), or record that the board is excluded and why. | Inferred (not run) |
| 6 | 4.4 sweep, T-P4 | **ABS-A sweep misses the derived-failure sites.** `harm_groups_failed_pairs += max(0, n_pairs - passes_on)` (`:1053`) turns every unrecorded pair into a failure by subtraction. The headline `b = n - passes_on` and the Fisher `n - passes_on` (`:964`) have the same shape. `n_pairs` is one variable with two jobs: quality denominator (`saturated`, `floor`, `n_pairs < 3`) and ratio rule (`n_pairs < 2`, `:567`). The design leaves this as "I: confirm at X-A3" (U3); I confirmed it here: both jobs exist. T-A1 (regex for a numeric default) cannot catch the subtraction shape. | major | `pack_improvement.py:497-538, 567, 1053, 1243-1248` | Decide now: add `n_recorded`, used by every `n - passes` site and the quality rules, with `n_pairs` kept for ratios. T-P4 must assert `harm_groups_failed_pairs` on a group with unrecorded pairs. Name "failure derived as `n - passes`" in the ABS-A class. | Verified |
| 7 | FM6, 4.4 | Dropping an unrecorded pair from both arms hides an **arm-asymmetric** cause (for example, a toolchain missing only on the pack-on side). The headline gives one `k not recorded`. | minor | 4.4 "Why the Fisher input is the recorded pairs only" | State `k_on` and `k_off` separately in the headline and the inconclusive row; test with k_on != k_off. | Inferred |
| 8 | 4.2 vs W1-F (seam, E2E-D) | **Two designs claim one hunk.** W1-G says X-F owns the `also_graded_by` owner rule in `applicable`. W1-F's `applicable` (its `:149`) has neither `also_graded_by` nor the owner rule (grep: no match), and names the parameter `prop` where W0 section 7 condition 1 and W1-G say `property`. Tests T-R3, T-R4, T-R5 are assigned to X-F, but W1-F's test list does not contain them. Until seam `req-01M41DAHV9XTGBY1WES1R5VQH3` is granted, they have no owner. | major | W0 s7 cond 1; W1-G 4.2, 11, 12; W1-F `applicable` | The Coordinator grants the seam and W1-F adds the clause and the three tests, or W1-G moves the tests to X-G1. Pick one name for the parameter. | Verified |
| 9 | Section 3 writer table; section 5 | The writer of `corrected_from` is "`freeze_catalog.py --correct`". 4.5 does not define it, section 5 (E7) omits `tools/freeze_catalog.py`, and the tool has no such flag (grep). | minor | `tools/freeze_catalog.py` | Add the row to section 5 and a test, or say the Leader edits the YAML by hand and the control is the only gate. | Verified |
| 10 | 4.5 U4 | The catalog name inside the export is only `"catalog_version":"0.6"`; there is no hash field in the 0.6 export (grep of `heads.export`). The "version and hash" drop list is wrong, and an open-ended drop list is itself a weak spot. | minor | `heads.export` | Replace the drop with exactly one substitution of `catalog_version`; any other difference is red. | Verified |

## W0 trace map (TA 14)

W0 section 7 conditions 1 (applicable narrowing), 5 (security task gives exactly two property rows, GradedOncePerPass green) and 6 (`pass_at_1` untouched) map to T-R1, T-R2, T-R5 and T-F1..T-F7. The mapping is present. T-R1 is red on arrival (the signature has two parameters today), which is correct. The truth-table cases in T-F1 distinguish the "NA as 0" and "any NA gives NA" mutants. No finding there.

## Gate

`GATE W1-G · Test Architect · BLOCK · 10 findings (rv-ta-w1g-e1e4, 2026-10-03)`

Clearing conditions: findings 1, 2 and 3 (each is a control with no failing case); findings 4, 6 and 8 should be resolved in the same follow-up; 5, 7, 9 and 10 may be recorded.

## Revision 2 re-review (delta only) - 2026-10-03

Target: `design/eval-catalog-0-7` at `30bda577` (main merged: W0 rev 3, R-95). Read: the Review disposition, sections 4.4, 4.5, 11, and `git cat-file -t d6dda42d` (returns `commit`, Verified).

| rev-1 finding | disposition check | result |
| --- | --- | --- |
| 1 (no red case) | T-U1a..d and T-U2 added; skeleton commit returns `[]` so they fail on `assert problems`, not on import. T-U2 injects a bad export because the real pipeline cannot produce the row; that is the honest shape. | Closed |
| 2 (0.6 golden unpinned; rubrics) | Step 1 hashes the 0.6 goldens (views and board) against `versions['0.6']`; T-U1c covers an edited and a regenerated golden. 0.6 definitions come from `git archive d6dda42d metrics.yaml rubrics`, hash equals the pin (SP-4); an unreachable commit fails, never skips. | Closed |
| 3 (e exception untested) | Superseded: the Coordinator cut the exception from E1 (W0 rev 3); it is a written contingency with a red-gate trigger, per-clause failing tests listed if built. (e) is unchanged and its existing test still applies. | Closed by scope cut |
| 4 (commit regex) | Contingency spec requires `git cat-file`. Not built, so not tested; acceptable. | Closed |
| 5 (board not compared) | Control 1 step 3 compares both surfaces; T-U1b changes a weight and expects the board export named. | Closed |
| 6 (`n - passes` sites) | `n_recorded` splits `n_pairs`; `:966`, `:1053`, `:1244-1245` read recorded pairs; T-P4 asserts `harm_groups_failed_pairs`, T-P6 swaps the two fields, T-A1 and T-A2 have red fixtures. | Closed |
| 7, 9, 10 | Per-arm counts in the headline; no `--correct` flag; one-substitution normaliser. | Closed |
| 8 (seam) | R-95 rules the owner rule; `prop` name and validation lines adopted; T-R1..R5 assigned to X-F. Whether W1-F carries T-R3..R5 is W1-F's gate, not this one. | Closed here |

New findings:

| # | finding | severity | fix | confidence |
| --- | --- | --- | --- | --- |
| R2-1 | T-U1b (weight changed on a 0.6 `correctness` metric) must be shown to move the board export before it is relied on; if the weight-0 safeguard makes it move nothing on these fixtures it is vacuous. The design asserts the board moves but did not run it. | minor (condition) | X-G3 observes the red on the skeleton run and records the problem text. | Inferred |
| R2-2 | T-A2 passes "only where the operand is `n_recorded` or a recorded-only `n`": a textual scan cannot tell a recorded-only `n` from an all-pairs `n` (`:966`, `:1244`). T-P4's behavioural assertion is what covers it; say so, and keep the scan a floor. | minor (condition) | Note in section 11 that T-P4/T-P6 carry the proof. | Verified (design text) |

`GATE W1-G · Test Architect · PASS WITH CONDITIONS · 2 findings (rv-ta-w1g-e1e4, 2026-10-03)`
