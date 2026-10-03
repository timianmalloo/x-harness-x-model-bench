---
id: review-eval-ta-w1e
title: "W1-E discriminate design review: Test Architect lens"
type: doc
status: draft
owner: "@timianmalloo"
phase: "Enterprise evaluation: Wave 1 gate reviews"
tags: [review, test-architect, evaluation-campaign, wave-1, w1-e]
links:
  - { to: design-eval-seam-contracts, rel: relates-to }
review-by: "2026-10-17"
summary: >-
  Test Architect (Adversary Mode) review of W1-E (design/eval-discriminate, 549f7bc4) against W0 rev 5 and R-98.
  BLOCK: R-HOST and the variant compare assume a check that three of five properties do not have; the campaign
  identity compare is stale against rev 5 for_task; untrustworthy records trap a legitimate retry. The SCAN-A
  fixture, T-E1a/T-E1b and the skeleton-first commit are sound in shape.
---

# Test Architect review: W1-E (rv-ta-w1e-e1e4)

Branch `design/eval-discriminate` at `549f7bc4`. Judged against W0 rev 5 and R-98 (DR-E1 ruled (A) per the Leader; I did not read R-98 itself). Severity: blocking / major / minor. Verified = I opened it or ran it.

| # | location | finding | severity | evidence | fix | confidence |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | s8.2 R-HOST, s7, s4.2 | R-HOST needs `probe.deliverable == "ran"`, case ids and `hosts_ready`; the variant compare needs a check's case outcomes. W0 rev 5 s2 (SR-L3): rework, no-guessing and simplicity have no `oracle/check/`. Six of ten tasks can never satisfy R-HOST, and no test covers a check-less task. Simplicity's `v-laundered` flips a scope clause, not a case. | blocking | W1-E 8.2 R-HOST row ("for a loopback or non-property-grader path, not applicable in E1"); W0 s2 rev 5 bullet; s7 simplicity bullet. | Scope `probe`, R-HOST and the variant compare by `config.CHECK_PROPERTIES`; define check-less evidence (hidden-test entry, scope clause) and a fixture per property class; add the test. | Verified |
| 2 | s4.1, s8.2 row 002 | HB-RDY-002 against a campaign "drops `builds/*`" from the baseline manifest. The baseline holds `tasks/<id>` for every campaign task, so its hash never equals the record's single-task hash: every multi-task campaign validates red. W0 rev 5 replaces this with `identity.for_task(baseline, task)`, and `profiles/<h>` covers `profiles.HARNESSES`, not "the plan's harnesses". T-E7b has no baseline case. | blocking | W1-E 4.1 "Engine identity, for the key"; W0 s6 `for_task` and `builds=None` bullets. | Use `for_task`; add a test with a two-task baseline built with `builds`; mutant compares the full baseline hash. | Verified |
| 3 | s4.3, s11, T-E5/T-E6 vs R-98 | R-98 conditions: the link is written only after created-or-equal, never after HB-RDY-010; HB-RDY-010 names the metric before HB-LED-007; reconciliation never degrades to a pass; no option-(a) branch survives. W1-E s11 says the link is "always written when a trial reaches the end of the engine run" (breaks condition 1), no test pins it, and s4.3 keeps a "Fallback if SR-E1 is refused" paragraph and T-E5 a fallback mutant (breaks condition 4). | major | W1-E s11 intro; s4.3 last bullets; T-E5 mutant cell. | Delete the fallback. Add `test_no_link_after_hb_rdy_010` beside T-E6 (no `discrimination-link.json` in the failed run; mutant writes it before the compare). Reconciliation prints `reconciled: no (<reason>)`, one test per reason. | Verified |
| 4 | s4.4, D-E3 | A trial with HB-RDY-011 items (a transient NA: bound fired, host load) is written as a record. The key is unchanged, so the retry's scores differ and the file is never replaced: HB-RDY-010 reports a determinism defect for a transient fault, the class RV-TA W0 7 closed. W0 rev 5 also says "a failed trial writes no record". | major | W1-E 4.4 last sentence. | Write nothing when any HB-RDY-011 item exists (exit non-zero naming it). Keep writing only HB-RDY-003 mismatches, whose fix changes the task version. Test: transient-NA trial, then a clean retry succeeds. | Verified (logic) |
| 5 | s17.2 T1, T-E33 | The claim "the deliverable cannot forge the record because `create_once` runs only after the pass" is false: `create_once` never overwrites, so a file the deliverable pre-created at the path stays and is read as the stored record. The mutant ("call `create_once` before `run_pass` returns") cannot exist, because the scores do not exist yet. The test has no coherent red. | major | W1-E T-E33 row; W0 s4 `create_once` ("Never overwrites"). | Check the key is absent at trial start and again before the write; a file that appeared mid-trial is a tamper failure. Assert that, with a forgery fixture that equals a plausible record. Name the B3 residual (ADR-0016 s8) for the rest. | Verified |
| 6 | T-E31 | Two processes "started together", no barrier. A mutant that locks after planning survives unless both reach planning first. A race, not a proof (W0 s6 used a `between` barrier for the same reason). | major | T-E31 row. | Deterministic form: hold `runs/.discriminate-<task>.lock` in the test, call `run`, assert HB-RUN-005 and no run folder; mutant moves the lock after the plan step. | Verified |
| 7 | s14 (floor item 3), s12 | No test drives the real `bench discriminate` subcommand (T-E1a/T-E1b call `discriminate.run`). T-E9 covers `cmd_validate` without a baseline; the baseline pass-through (SR-E2 4) is untested. Removing either `cli.py` line leaves every X-E test green. | major | T-E1a/T-E1b "real path" cells; W0 rev 5 SR-E2 4. | Add `cli.main(["discriminate", ...])` on `disc_c` and a `cmd_validate` test with a campaign baseline; mutant deletes each wiring line. These join at X-INT, so name the owner. | Verified |
| 8 | T-E20, s5.4 | The assertion is "refuse or label" (unpinned), and the readers (`status.py` X-C, `views.py` X-A1, board) are not X-E's files, so the fix has no owner. | major | T-E20 row; W0 s13 hub table. | Pick one behaviour and send the seam request, or record an accepted residual and drop the test. | Verified |
| 9 | s10 I2, T-E35, s5.1 table | I2 says an "HB-PLN-002-style" refusal; W0 rev 5 fixes HB-PLN-004 naming the combo. s5.1 says `config.HARNESSES` "already lists" `synthetic`; it does not. | major | `config.py:34`: `("claude-code", "codex", "copilot", "grok", "agy")`; W0 s11 HB-PLN-004 row. | Assert HB-PLN-004 and the combo name in T-E35; fix the 5.1 row (X-A1 adds it). | Verified |
| 10 | s8.2 EV-1 row, T-E25 | The contract list lacks the rev 3-5 rules: `oracle/check/` presence by `CHECK_PROPERTIES` in both directions; `ceilings.outside_radius_lines` for simplicity; the case-id charset; the loopback exactly-one shape; the `variants.py` grammar (one assignment, non-literal value, name regex, `old` exactly once, `edits[].file` traversal such as `..` or absolute). "`old` occurs once" and `edits[].file` traversal have no test. | major | W1-E 7 and 8.2; W0 s2, s3 rev 4. | One parametrized case each in T-E25; apply s6 rule 4 to `edits[].file`. | Verified |
| 11 | T-E21 | The sentinel-absent assertion passes on the skeleton (it ignores variants); "flips parsed" has no public path in s8.1. Vacuous today. | minor | T-E21 row. | Run `discriminate` and assert `record["variants"]` holds the parsed flips and the sentinel is absent. | Verified |
| 12 | s7 clauses, s8 hosts | Drift from W1-F rev 3: `Score.evidence` is the `property.json` path, not its directory; `clauses.json` sits in `<out_dir>/check/`; `check.hosts` is the path of `hosts.jsonl` (count `end: ready` lines in that file). `hosts_ready >= len(cases)` should be `==` (one host per case). | minor | W1-F r3 evidence table (`check.hosts`; `Score.evidence` = `.../property/property.json`). | Correct the paths; use `==`. | Verified |
| 13 | T-E13, T-E1b, T-E3, T-E36 | T-E13's fixture is "hook, or a hand-built ledger row" (not pinned). T-E1b lands before X-F and would fail for a missing grader, not its assertion: add it in the commit after X-F joins. T-E3 has two enforcers (readiness, agent) and one mutant; a junction param that skips when unsupported is a quiet skip. T-E36 needs an env-dumping hook in a production file. | minor | those rows. | Pin one fixture each; add the second mutant; fail rather than skip for the junction; keep the dump hook test-only. | Verified |
| 14 | s8.3 `not_comparable` | In a trial every cell must be gradable. A reference cell with `pass_at_1` NA is "not comparable", counted in a local file, and the trial passes; `pass_at_1` has no expected value. | minor | W1-E 8.3 second state; W0 s2. | Treat not-comparable as an HB-RDY-011 item in the discriminate path. | Verified |

Sound: the skeleton-first commit (14.1) gives well-formed wrong behaviour, so "red today" is an assertion; T-E1a and T-E1b drive the real engine, grader and probe host, with a stub-host mutant on T-E1b; T-E2 and T-E4 hold the overlay in the engine-built copy with the ORCL-A mutant; the SCAN-A fixture matches the class (a mandated build's own output flagged by the check; `docs/lessons/defect-classes.md` SCAN-A) and its arithmetic holds (4 of 5 blocked is `"0.8000"`, primary 0), with the sibling `scan_a_secondary` separating the secondary rule, and T-E10 asserts on the failure list, not on completion. s4.2 matches R-98 (no run ids in the body). I read s14 row by row.

Conditions to clear: findings 1-10. Findings 11-14 with the build.

GATE w1-e-discriminate · Test Architect · BLOCK · 14 findings (rv-ta-w1e-e1e4, 2026-10-03)

## Revision 2 re-review (2026-10-03, rv-ta-e2-e1e4)

Branch `design/eval-discriminate` at `45224a42`, judged against W0 rev 5 and R-98 (read: Ruling 98, conditions 1-5). Round-1 closure first, then new findings, then the section 2a floor on the surviving 26 test rows.

### Round-1 closure

| # | state | where closed | note |
| --- | --- | --- | --- |
| 1 | closed | 4.2, 7, 8.2 R-HOST row, T-E1c, T-E8(d), T-E11 check-less param, F20 | scoped by `CHECK_PROPERTIES`; check-less evidence is `scores` plus `hidden_tests`/`clause`, provisional on SR-E3 (2), marked and fail-closed (HB-RDY-011). New seam gap: R2-2 |
| 2 | closed | 4.1, 8.2 row 002, T-E7 (b2) | `identity.for_task`; two-task baseline built with `builds`; mutant compares the full baseline hash; no `builds/` literal in `readiness.py` |
| 3 | closed | 4.3, 11, T-E5(b), T-E6 | link only after created-or-equal; fallback deleted; seven closed reasons, each a T-E6 param (checked one by one) |
| 4 | closed for HB-RDY-011; **reopened for a `timeout` outcome** | 4.4, 8.4, T-E13 | R2-1 |
| 5 | closed | 4.3, T-E22, F19 | absent at start, absent again before the write; B3 named. R2-7 on the fixture |
| 6 | closed | T-E20 | the test holds the lock; mutant moves the lock |
| 7 | closed | T-E9 | real `cli.main` x3, owner X-C, joins at X-INT. R2-6 on the red |
| 8 | closed | 5.4, T-E19, SR-E3 (1) | one behaviour pinned. R2-4 on the sweep |
| 9 | closed | 5.1, 5.2, T-E23 | HB-PLN-004 and the combo name; `config.py:34` has no `synthetic` (read) |
| 10 | closed | 8.2 EV-1 row, T-E24, T-E11, T-E3 | both-direction `oracle/check/`, `outside_radius_lines`, case-id charset, `old` once, `edits[].file` traversal all have a param |
| 11-14 | closed | T-E11, 5.5, T-E13/T-E1b/T-E3/T-E1a, 8.3 | |

### New findings

| # | location | finding | severity | evidence | fix | confidence |
| --- | --- | --- | --- | --- | --- | --- |
| R2-1 | 4.4, R6, F7, 8.4 | 4.4 says a mismatch "is not transient by construction: a host fault is an NA row, never a wrong value". False. A per-case `timeout` is an outcome, not an NA row, and it makes `property_check_pass` 0 (W0 s3: "`outcome` in {blocked, exploited, passed, failed, timeout}"; "Any exploited, failed or timeout case makes it 0"). W0 DS 4 rejects an automatic re-run of a timeout. So a load-driven timeout on a reference case, or a flipped variant case (F7 says so itself), is HB-RDY-003, **is written**, and the clean retry then differs: HB-RDY-010 on a key that never changes. This is round-1 finding 4 again for the outcome the fix did not cover. R6 and F7 contradict 4.4. | major | W1-E 4.4 last sentence, R6, F7; W0 s3 outcome set and DS 4 row. | Treat a `timeout` outcome (and a variant flip whose cause is a `timeout`) that is not in `expected`/declared `flips` as an HB-RDY-011 item: nothing written. Add a param to T-E13 (timeout case, then clean retry succeeds). Delete the "cannot be" sentence; keep R6 as stated residual. | Verified (logic and W0 text) |
| R2-2 | 4.2, 8.2 R-HOST, T-E8(d) vs W0 s6 | Seam disagreement. W0 s6 rev 5 record bullet: `probe` "readiness requires it for every role, so a hand-written record without it fails HB-RDY-001". W1-E: `probe` present only for `CHECK_PROPERTIES`, and a `probe` on a check-less record is itself HB-RDY-001. Both cannot hold for rework, no-guessing, simplicity. SR-E3 (4) asks only for R-98 text and "readers raise", not this. | major | W0 s6 line "The record (rev 5...)"; W1-E 4.2 and T-E8(d). | Add to SR-E3 (4): W0 rev 6 scopes `probe` by `CHECK_PROPERTIES` and says a check-less record carries none. Mark T-E1c and T-E8(d) provisional on it. | Verified |
| R2-3 | T-E1a "retired when T-E1b is green" | The credential and unlisted-canary environment assertions and the no-path/`USERNAME` scan (SEC F8, I1, E2) live only in T-E1a. Retiring it deletes the only test of the allowlist rule, and T-E1b does not carry them. | major | T-E1a row (assertions); T-E1b row. | Move the environment and leak assertions into T-E1b (or T-E4) before retiring T-E1a, and name where they went. | Verified |
| R2-4 | 13 last row, T-E19 | Floor item 5. The scan lists five reader sites (`cli.py:155`, `runner.py:197`, `status.py:105`, `views.py:537`, `pack_improvement.py`); 5.4 names six readers including `campaign.run_side_check`, `pilot attach`, `attach` and the board. `campaign.py` is not on this base, so `run_side_check` is in no scan. T-E19 lists readers by hand and asserts no set. I re-ran the scan on `main` and it matches the author's list. | major | `git grep "plan.json\|load_confirmed" main -- src`; T-E19 row. | Add a sweep assertion: every `src/` module that calls `load_confirmed` or reads `plan.json` is in T-E19's reader table (allowlist plus count), so a new reader fails the test. Re-run the scan when X-C lands. | Verified |
| R2-5 | 14 header, 14.3 | The headline says 25 tests plus 3 join checks. The table has 26 rows (T-E1a, 1b, 1c, T-E2..T-E24), of which T-E9 and T-E19 are join tests and T-E23 is X-A1's. The count is the floor's own sweep claim. | minor | row count. | State the real split (for example 23 push/readiness tests, 3 join/other-owner rows, J1-J3) and let the test assert nothing about the number. | Verified |
| R2-6 | T-E9(c), T-E13 "today" | T-E9(c): an unknown subcommand is argparse `SystemExit(2)`, a red for the wrong reason unless the skeleton adds the dispatch. T-E13 "today" reads "a file is written/none": the skeleton writes none, so "no file at the key" already passes; only the retry assertion is red. | minor | T-E9, T-E13 rows. | Name the failing assertion in each: T-E9(c) the dispatch lands in X-C's skeleton line; T-E13 `second.outcome == "written"`. | Verified |
| R2-7 | T-E22 | The forged file is written by a deliverable whose environment is `grading_env()` (an allowlist), so a "test-only env var" cannot carry the key path. `disc_c` runs only hidden pytest in a correctness pass. The forged bytes must also differ from the true record, or `create_once` treats them as equal and the harm test is vacuous. | minor | T-E22 row; W1-E 5.1 `argv_env`. | Bake the absolute key path into the overlay at fixture build; forge bytes that differ; assert HB-RDY-011 and not HB-LED-007. | Inferred (allowlist forwards no test var; fixture not yet written) |

### Floor check on the surviving rows (2a items 1-5)

Item 1 holds for all rows except the two wording gaps in R2-6; the skeleton commit (14.1) is well-formed wrong behaviour. Item 2: every guard has a named fixture (`scan_a`, `scan_a_secondary`, `disc_flaky`, `make_task.py` params, the T-E3 forms). Item 3: T-E1b, T-E9, T-E15 and T-E7's T-E1b partner are real compositions. Item 4: R-HOST vs HB-RDY-003 (T-E8 b), written-mismatch vs not-written-011 (T-E10 vs T-E13), HB-RDY-010 vs HB-LED-007 (T-E5) are separated. Item 5: R2-4 only. J1 is a join check with a stated scan.

Conditions to clear before X-E's skeleton commit: R2-1, R2-2, R2-3, R2-4. R2-5 to R2-7 with the build.

GATE w1-e-discriminate · Test Architect · PASS WITH CONDITIONS · 7 findings (rv-ta-e2-e1e4, 2026-10-03)
