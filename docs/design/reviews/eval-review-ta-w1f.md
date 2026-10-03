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

## Revision 3 delta: `design/eval-property-grader-r3` `f125430a` (section 14 rev-3 table), 2026-10-03

Scope: the 14 rows of the section 14 rev-3 table against the README s2a floor (five items), the start-bound versus case-bound question, RF-11, and the G23 sweep. Tree read: `C:\Projects\x-harness-x-model-bench-design-eval-property-grader-r3`. Confidence: Verified (I opened it; G23 re-run).

**Floor result per row.** All 14 rows name an assertion that fails against the rev-2 build and say why; none is red by import or name error. The real-wiring test (floor 3) is `test_wsgi_app_scores_through_the_real_probe_host`, with the mutant `wsgi dispatch removed`. The red fixture (floor 2) for the one new guard is the four bad temp task dirs of `test_cases_paths_outside_root_are_refused`, with `ok` as the over-refusal control. Mutants separate the adjacent pairs: `PATH_INFO raw`, `REMOTE_ADDR dropped`, `start waits bound_ms(case)`, `paths before root`, `overlap 0`, `fd 0 not moved to NUL` versus `dup2(2, 1) removed` (the three start ends), `str.format` versus `top-level only`. The T5 contract test uses stdlib `wsgiref.validate` and writes the 18-key set from W0 rev 3 (11 CGI keys, 7 `wsgi.*`; I counted W0's list). Gaps follow.

| # | location | finding | severity | evidence | fix | confidence |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | s14 rev-3 table; s5.5 App output; G20; RF-11 | RF-11 ("a grandchild with default stdio writes to neither the protocol nor the app-output file") has no test. G20 and SP-F3's `gc_probe` are a one-time spike; the table's `getstdhandle` parameter writes from the host's own process, so it never exercises inheritance by a child. The stated behaviour is a security-relevant blind spot: S1's `leak-2` scans the app-output file, so a child-process log of the canary is a silent false pass. A claim the design accepts but cannot see regress is a correctness claim with no verification path. | major (condition) | s14 table params `print..import_time` (no child); s5.5 last sentence of App output; s18 RF-11 ("accepted for E1"); s15 grandchild row | Add `test_app_output_grandchild_default_stdio_is_not_captured` (or a `grandchild` parameter of the app-output node) through the real host: the app runs `subprocess.run([python, "-c", "print(TOKEN)"])`; assert rc 0, `output_contains(TOKEN)` False, nothing but EOF on the protocol after the response, and `GetStdHandle(-11)` equal to fd 1's handle. It pins today's behaviour, so the RF-11 upgrade (pass the fd-1 handle) turns it red on purpose. Red on rev 2 by assertion (the protocol carries the child's line). | Verified |
| 2 | s14 `test_probe_host_start_bound_is_the_interface_bound[within,past]`; s5.5 four ends | Only the start side is tested. `past` pins `did not start` / `end: start bound`, and `within` pins that the case bound does not cover the start. No test says a hang after the ready line is still a case-bound `timeout` (`deliverable: ran`, `end: ready`, `start_ms` small). The deleted `test_probe_host_hung_at_import_is_a_case_timeout` was the only node near it, and the rev-2 `test_hanging_deliverable_with_grandchild_is_a_measured_timeout` does not state `deliverable`, `end` or `start_ms`. So a mutant that reports a case-bound hang as `did not start` (or the reverse) is not separated, and a reader of `hosts.jsonl` cannot be shown to tell the two apart. `within` also does not assert `end: ready` or the `hosts.jsonl` line. | major (condition) | s14 start-bound row; s14 D4 list; s5.5 "Four ends" | Make the node `[within,past,case_hang]`. `case_hang`: import instant, the app sleeps past `bound_ms(case)` inside the request; assert `deliverable == "ran"`, outcome `timeout`, `hosts.jsonl` `end == "ready"`, `start_ms < 200`. Assert in `within` the same `end: ready` and `start_ms >= 500`, and in `past` `cases == []`. Mutant `start-miss classed as case timeout` and mutant `case-hang classed as did not start` each fail one parameter. | Verified |
| 3 | s14 rows: forgery re-run, `test_app_output_is_opaque_and_capped_after_the_job_closes`, `[factory_raised]` | Two rows are red by a missing file or a different reason. "The forged line is in the app-output file" and "under rev 2 no file exists at `out_dir/check/host/<case>.log`": a test that opens the path raises `FileNotFoundError` instead of failing an assertion. And `factory_raised` says "rev 2 uses `create_app` itself as the app (it starts)", but the same table says rev 2 returns NA `not built` for `kind: wsgi`, so the stated red reason is wrong. | minor | s14 rows 5, 11, 12 vs row 1 text | Assert `path.exists()` first in both nodes (an assertion failure, not an OS error). Restate the `factory_raised` red reason as NA `not built` (rev 2). | Verified |
| 4 | s14 Sweep (floor 5); G23 | The count is off and no test asserts the set. I re-ran G23's command on `1ceea651`: 7 lines (`probe_host.py` 1, `spike_check.py` 4, `test_property_forgery_fixture.py` 2), not 6. On `f125430a` the per-file counts are 1, 4, 2. Floor 5 asks that the test assert the same set; the design only says X-F leaves the stand-ins alone. | minor | `git grep -n -E "probe_host|kind: wsgi|app\.kind|\"wsgi\"" 1ceea651 -- src tasks tests` | Correct G23 and s14 to 7 lines in 3 files. Add a small scan test asserting that the reader files are exactly those three plus the product files (`bench_check.py`, S1's `check.py`), so a stray reader fails it. Red fixture: a temp tree with one extra reader. | Verified |
| 5 | s14 `test_wsgi_environ_passes_wsgiref_validator`; W0 rev 3 s3 Frames | Two small looseness items. The assertion says "keys superset of `W0_ENVIRON_KEYS`" but the fixture text says "that exact set plus `HTTP_AUTHORIZATION`"; pick one (exact is stronger and catches an extra bench key). The wsgi response frame keys (`id, ok, status, headers, body_b64`; plus the added `error`) are W0's "may not rename" contract, and no node pins them: a rename in host and check together stays green. | minor | s14 row 2 fixture column; W0 s3 "Frames" | Assert `set(environ) == W0_ENVIRON_KEYS | {"HTTP_AUTHORIZATION"}`; assert the request and response frame key sets in the same node (a golden). | Verified |
| 6 | s5.5 "A start that fails on a later case ... still `did not start` for the run"; s14 | Two stated behaviours have no named test: (a) a host start miss on case 2 after case 1 started gives `did not start` for the run with `cases == []`; (b) the app-output file reaches reports only through `egress.check` (s3, N12): `test_task_canary_is_withheld` is the only egress node and names no app-output file. | minor | s5.5 line 4 of the start-bound list; s3 line 157; s14 Egress | Add a `case2` parameter to the `did_not_start` node (case 1 honest, case 2 import sleeps past the bound; assert `deliverable == "did not start"`, `cases == []`, two `hosts.jsonl` lines). Add `app_output` to the egress node: a canary in `host/<case>.log` is withheld from the judge and report view. | Verified |

Seam check: W1-F matches W0 rev 3 s3 on the frame field names (it adds `error`, allowed), the app keys, the start bound (`bounds_ms[interface]`, `start_ms` recorded, miss is row 6) and app-output routing. No disagreement between the two documents.

Conditions to clear: findings 1 and 2 specified with named nodes and mutants; findings 3 to 6 may be applied at build.

GATE design-eval-property-grader · Test Architect · PASS WITH CONDITIONS · 6 findings (rv-ta-f3-e1e4, 2026-10-03)
