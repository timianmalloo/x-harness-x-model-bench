---
id: review-eval-ta-w1f
title: "W1-F property grader design review: Test Architect lens"
type: doc
status: draft
owner: "@timianmalloo"
phase: "Enterprise evaluation: Wave 1 gate reviews"
tags: [review, test-architect, evaluation-campaign, wave-1, w1-f]
links:
  - { to: design-eval-seam-contracts, rel: relates-to }
review-by: "2026-10-17"
summary: >-
  Test Architect (Adversary Mode) review of W1-F against W0 rev 2. The ADR-0018 red tests are named and can fail.
  Two blocking gaps: the hidden-tests phase has no suspend control (W0 s3 requires one per phase), and the clean-exit
  tamper test (my W0 rev 2 condition) is not specified. The design also still disagrees with W0 rev 2 at four points.
---

# Test Architect review: W1-F `docs/design/eval-property-grader.md` (branch `design/eval-property-grader`, `e41289a2`)

Session `rv-ta-w1f-e1e4`, 2026-10-03. Checked against W0 rev 2 on `main` (s3 invocation, outcome table, `property_check_pass`), ADR-0018 (red tests in s9, s10, s10a), R-90, and the code the design cites (`host.py:154-172`, `grade/runner.py:161`, `grade/correctness.py`, `engine.py:379`). Confidence: Verified = I opened it; Inferred = reasoned.

## W0 rev 2 conditions, checked here

| condition | result | evidence |
| --- | --- | --- |
| `runner.applicable` property argument has its red test | **Met.** `tests/test_grade_runner.py::test_security_task_property_rows_are_exactly_two` (red first, s14) fails if the narrowing is absent: a security task would also get other properties' tagged rows and GradedOncePerPass raises. `::test_untagged_metric_applies_as_before` and `::test_task_changed_fallback_rows_for_property` cover `prop=None`. Today `applicable` takes two parameters (`runner.py:161`), so the first test is red on arrival. One dependency: finding 9. | s5.1, s14 "Runner and catalog" |
| row-3 tamper test includes a tamper that exits cleanly | **Not met.** Finding 1 (blocking). | s14, s9 F12, s10 A8 |

## Findings

| # | location | finding | severity | evidence | fix | confidence |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | s14 `test_check_tree_changed_is_tampered`; `test_precedence[hash+handshake]` | Condition 2 is not carried. Neither test says the tamper leaves every handshake fact clean (one alone-at-arrival valid line, ack, exit 0). Rules 3 and 4 give the identical result (NA `invalid (check tampered)`, HB-CHK-002), so `[hash+handshake]` cannot fail if rules 3 and 4 swap, and a test where the tampering deliverable also trips the handshake still passes with rule 3 deleted. Rule 3 is load-bearing only when the document is otherwise valid and the exit is clean. | blocking | s5.6 rules 3 and 4 (same result text); s14 precedence line; W0 s3 row 3 vs row 4; my W0 rev 2 residual | Specify `test_check_tree_changed_is_tampered[clean_exit]`: the deliverable rewrites a `check/` file; the honest check writes one valid `blocked` document, is acked and exits 0. Expected: HB-CHK-002, never the score. Add a `tests/mutations/property.json` entry that deletes rule 3 and must be killed by that test. Replace `[hash+handshake]` with `[hash+clean_valid]` and `[hash+malformed]` (hash mismatch plus a malformed line is HB-CHK-002, not 001): those distinguish rule 3 from rules 4-6. | Verified (text); Inferred (swap is an equivalent mutant) |
| 2 | s5.6 rule 1; s5.2 phase 1; W0 s3 "Bounds per phase" | W0 rev 2 requires the host-suspend rule on **each phase's own span**. The design applies `SleepDetector` "over the check step" only. `correctness.grade` does not detect suspend (`SleepDetector` is used only in `engine.py:379`), so a suspend inside the hidden-tests phase makes a timed-out run, which the Kleene table (row `0 / any`) turns into a **measured 0**: a plausible wrong number from a host event. Nothing in s14 tests it. | blocking | W0 s3 "Bounds per phase"; `host.py:154-172` (compares since its own last call, so one instance per span); `correctness.py:196`; s14 F7 test is the check phase only | One `SleepDetector` per phase. A suspend in either span is rule 1: every metric NA `host suspended`. Add `test_seeded_suspend_in_tests_phase_is_hb_chk_004_not_measured_0` (fake unbiased clock, hidden tests that time out) and a precedence pair `[tests-suspend + tests-fail]`. Record both spans in the evidence (`check.handshake.suspended` is one flag today). | Verified |
| 3 | s5.6, s5.4, s5.7 vs W0 s3 | Three disagreements with W0 rev 2, which this design predates, plus finding 2. (a) W0 has seven rows; the design has eight, adding rule 5 (no line, exit 5, HB-CHK-001); in W0 "no line" is row 4 (tampered). (b) W0 caps the line at 64 KiB; the design sets `MAX_RESULT_BYTES` to 1 MiB and tests `test_result_over_1mib_is_hb_chk_001`. (c) W0 says "tamper NA"; the design records a primary 0 for a tampered run whose hidden tests failed. The design's s16 still calls the W0 amendments pending. Tests are then asserted against a different table than the one W0 says they prove. | major | W0 s3 outcome table and "Framing"; design s5.4, s5.6, s5.7, s16 | Rebase on rev 2. Either the Coordinator amends W0 (exit-5 row, byte cap, tamper with failed tests) or the design conforms. Test row numbers must match the winning table. | Verified |
| 4 | s14 precedence pairs | Listed: suspend+bound, bound+tamper, hash+handshake, tamper+malformed, malformed+did-not-build. Missing adjacent pairs of the design's own table: rule 4 vs 5 (a forger that kills the check with code 5 while not alone; N8 only asserts "NA") and rule 5 vs 6. `[bound+tamper]` is ambiguous between rules 2-3 and 2-4. `test_classify_table` ("one code each") is satisfied by any total function and cannot catch a reordering. | major | s14 lines "precedence pairs" and D1; s5.6 | Key the pair table by rule numbers of the final table, one test per adjacent pair, each asserting the earlier rule's code. Make `test_classify_table` compare against an independent first-match reference written in the test. | Verified |
| 5 | s10 N1 vs s15 vs s5.5 | N1 expects `deliverable: did not start`, primary 0, for a module doing `sys.stdout.write(forged); sys.stdin.buffer.read(1); os._exit(0)` at import. The spike row says the forged line "went to the host's stdout file; the honest result arrived ... honest `exploited`". Two different results; and the spike used a stdout file where s5.5 specifies `pipes=True` (host stdout is a pipe the check reads). The shipped shape was never run. A red test with two possible expected values cannot fail meaningfully. | major | s10 N1 row; s15 table row 3; s5.5 | Re-run SP-F2 on the shipped shape. Fix one expected result in `test_module_body_forgery_in_probe_host_is_refused` (the forged line is read as the ready line, malformed, so `did not start`) and assert no `blocked` outcome appears. State a bound for the ready line: s5.4 `probe_host` gives none, so a blocked host runs to the outer bound and becomes HB-CHK-003, not a measured 0. | Verified (text); Inferred (outcome of the pipes shape) |
| 6 | s9 F17, s5.6 rule 4 | The race test is deterministic through the `_job_view_at_arrival` seam and can fail. F17 `test_honest_check_is_accepted` "repeated 20 times" is statistical: it relies on `GetProcessTimes` exit time agreeing with `GetSystemTimePreciseAsFileTime` within a +0.9..+3.0 ms margin, and rule 4 ("exit at or before `first_byte_ft`") turns any disagreement into a false tamper. Twenty passes do not prove the margin under load and are not repeatable. | major | s5.3, s9 F17, s15 margins | Add a seam test with injected `exit_ft` and `first_byte_ft` covering `<`, `==`, `>`. Keep the 20-run test as a measured false-tamper rate with a stated ceiling, run once under load in the pilot, not per push. | Inferred (clock resolution on a loaded host not measured) |
| 7 | s14 triggered directives | T5 (the check consumes the deliverable's WSGI/HTTP surface) is not listed. E1: the probe-host line protocol is the consumer side. E4: loopback HTTP. | minor | s14 directive list; s5.5 | State T5 as N/A in E1 with the reason (own line protocol, covered by D6 and D7) and triggered at E4 (X-LB). | Verified |
| 8 | s9 F8 | `assume:` the unbiased clock never fails on Windows 10+, confirmed by `test_unbiased_clock_reads_on_windows`. That test passes on this host and cannot fail on one where the read fails. A missing reading makes `SleepDetector.slept()` return False (`host.py:166-169`): the suspend rule is silently off. | minor | `host.py:160-172` | Record `unbiased_ok` per span in the evidence and make an absent reading a pilot-gate item. | Verified |
| 9 | s14 runner tests | `test_security_task_property_rows_are_exactly_two` needs a 0.7 catalog with tags (W1-G/X-G1). Against the committed 0.6 catalog (G14: no `property` key) it cannot discriminate. | minor | s2 G14; s7 catalog row | Build the fixture catalog inside the test (two `security`-tagged, one `resilience`-tagged, one untagged metric). | Verified |
| 10 | s10 A13 | `test_e1_check_opens_no_socket` uses an audit hook inside the check process. The probe host and the deliverable run elsewhere, so "E1: no socket at all" is unverified for them. | minor | s10 A13; s5.5 | Scope the claim to the check process, or add a probe-host-side hook. | Verified |

## ADR-0018 red tests, grader outcomes, adjacent pairs: named-test table

| item | named test | can it fail? |
| --- | --- | --- |
| s9 env | `test_property_check_env_excludes_credentials` | Yes (four names set, deliverable writes its own env keys). |
| s10 result pipe | `test_deliverable_cannot_write_result_pipe` | Yes, asserts on the parsed result. |
| s10a duplicated handle and two variants | `test_forged_result_via_duplicated_handle_is_tampered`, `_forge_then_exit_two_documents`, `_forge_then_kill_check` | Yes. |
| s10a killed before write | `test_check_killed_before_write_is_tampered` | Yes. |
| s10a race | `test_forged_write_racing_deliverable_exit_yields_two_documents` | Yes, forced through the seam. |
| RV-SEC F1 | `test_module_body_forgery_in_probe_host_is_refused` | Expected value inconsistent (finding 5). |
| HB-CHK-001 / 003 / 004 | four, one and one named tests | Yes; HB-CHK-004 covers the check phase only (finding 2). |
| HB-CHK-002 hash | `test_check_tree_changed_is_tampered` | Not as specified (finding 1). |
| measured 0 and scores | `..._did_not_build_is_measured_0`, `..._did_not_start_is_measured_0`, `test_honest_check_is_accepted`, `test_reference_and_naive_fixture_truth_table` | Yes. The truth table needs a tamper-with-failed-tests row to pin finding 3(c). |
| adjacent pairs | `test_precedence[...]`, five cases | Incomplete and partly non-distinguishing (findings 1, 4). |

## Seam disagreements

1. W0 rev 2 s3 outcome table (seven rows, 64 KiB line, "tamper NA", per-phase suspend) vs design s5.4/s5.6/s5.7 (eight rules, 1 MiB, tamper with failed tests is 0, check-step suspend only). Findings 2, 3.
2. Within the design: s15 (probe-host spike, stdout to a file) vs s5.5 (pipes). Finding 5.

## What is sound (Verified)

The aggregate and its invariant are testable. Derived measures have a rebuild test. The Kleene table has a named truth-table test. `-S`, `_env.py` and the `HOST_ENV` single-definition guard each have a test that fails. F1 was reproduced by spike (forged 3 of 3) before it was fixed.

## Gate

Blocking: 1 (clean-exit tamper test, my W0 rev 2 condition) and 2 (hidden-tests suspend). Clears when both are specified with a named test and the mutation entry, and finding 3 is reconciled with W0 rev 2.

GATE design-eval-property-grader · Test Architect · BLOCK · 10 findings (rv-ta-w1f-e1e4, 2026-10-03)

## Revision 2: delta re-review of `design/eval-property-grader` `ba678630` (13011c96, ec94645c), 2026-10-03

Scope: my 10 findings against the Review disposition table (10 TA rows, all "accepted") and the text of s5.2, s5.6, s9, s10, s14, s15. Confidence: Verified (I opened it).

| # | check | result | evidence |
| --- | --- | --- | --- |
| 1 (blocking) | clean-exit row-3 test and mutation | Resolved. `test_check_tree_changed_is_tampered[clean_exit]` is specified as one valid `blocked` line, alone, acked, exit 0, so only row 3 holds. The mutation entry replaces `if facts.hash_after != facts.hash_before:` with `if False:` and names that test as the killer. Every precedence test asserts `Classification.row`, so a row 3/4 swap is caught despite the shared code. Pairs `[r3_hash+r5_malformed]` (HB-CHK-002, not 001) and `[r3_hash+r4_two_lines]` are added. | s5.6 bullets and JSON; s14 row 3 and pairs |
| 2 (blocking) | per-phase suspend | Resolved. A fresh `SleepDetector` per phase span, `slept()` read at phase end; row 1 reads `spans.tests[tree].suspended or spans.check.suspended`. `test_seeded_suspend_in_tests_phase_is_hb_chk_004_not_measured_0` (hidden tests that time out) and `[r1_tests_suspend+tests_fail]` -> row 1 are named. Both spans are in the evidence. | s5.2 step 3; s5.6 row 1; s9 F7; s14 |
| 3 | W0 conformance | Resolved. Seven rows, 64 KiB, exit 5 with no line is row 4, NA on rows 1-5. The truth table pins "tamper with failed hidden tests is NA". | s5.3, s5.6, s14 truth table |
| 4 | pairs | Resolved. Eleven pairs keyed by W0 row, each with its expected row; `test_classify_table` against an independent first-match reference. | s14 "pairs" |
| 5 | N1 | Resolved. SP-F2 re-run on the pipes shape and committed (`tests/fixtures/property/`, `tests/test_property_forgery_fixture.py`, with a positive control); one expected result (row 6, `did not start`, no `blocked`, 9/9). | s10 N1, s15; `git show --stat ec94645c` |
| 6 | F17 | Resolved. `test_exit_time_vs_first_byte[lt,eq,gt]` through seams; the 20-run test becomes a one-time pilot measurement. | s14 rows 4 and 7 |
| 7-10 | minors | Verified true in text: T5 N/A in E1 and triggered at E4; `unbiased_ok` per span with a pilot-gate seam (req-...V67); the runner test builds its own catalog; A13 scoped to the check process. | s14, s5.6, s10 A13 |

Residual (minor, not blocking):
- The mutation set covers row 3 only. A row-1 mutation on the tests span (drop the tests-span term from the `or`) should also be in `tests/mutations/property.json`, killed by the tests-phase suspend test. X-F can add it at build time.
- The ready-line bound for the probe host is "the case bound" (s5.5); its test is the N1 node. Confirm at build that a host that never writes the ready line yields row 6 and not row 2.

GATE design-eval-property-grader · Test Architect · PASS WITH CONDITIONS · 2 findings (rv-ta-w1f-e1e4, 2026-10-03)
