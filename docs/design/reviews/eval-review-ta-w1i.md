---
id: review-eval-ta-w1i
title: "W1-I security tasks S1 and S2 design review: Test Architect lens"
type: doc
status: draft
owner: "@timianmalloo"
phase: "Enterprise evaluation: Wave 1 gate reviews"
tags: [review, test-architect, evaluation-campaign, wave-1, w1-i]
links:
  - { to: design-eval-seam-contracts, rel: relates-to }
review-by: "2026-10-17"
summary: >-
  Test Architect (Adversary Mode) review of W1-I against W0 rev 2 and R-87..R-94. The probe table, the corrected
  inj-1 and the nine-variant idea are strong. BLOCK on two controls that can be satisfied for the wrong reason: the
  11 hidden tests are red only by a missing module, and the variant test judges outcomes while a fail-closed host
  turns any crash into "exploited".
---

# Test Architect review: W1-I `docs/design/eval-security-tasks.md` (branch `design/eval-security-tasks`, `2fc8906b`)

Session `rv-ta-w1i-e1e4`, 2026-10-03. Checked against W0 rev 2 section 3 (cases shape, `env`, bounds, truth table), EV-1/EV-2/EV-7 as quoted by the design, and the design's own appendix. Nothing was executed: the spike scripts are not committed, so the 1.0000 / 0.4000 figures are the author's report (Inferred from this side). Count note: the test plan has 23 rows, not 22 (counted in section 15).

## Findings

| # | location | finding | severity | evidence | fix | confidence |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 5.6; plan row `..._hidden_tests_fail_on_the_base_and_pass_on_both_solutions` | **The 11 hidden tests are red for one reason only: the module is missing (ImportError).** The only red case is "the base". Nothing shows a test fails on a *wrong* app, so a test with a weak assertion (for example 5, 6, 7: id order, ASCII-case search, empty match) is red on the base and green on both solutions. G8 says the 11 have not been written or run. | blocking | G8; 5.6 "11 fail on the base because the module is missing" | Add 3 to 4 wrong-app fixtures that import cleanly but break one stated behaviour (search is case-sensitive; list unordered; missing id returns 200; non-object body accepted; DELETE leaves the row). Each must turn exactly its own test red. Without them 5.6 has no verification path for its assertions. | Verified (text) |
| 2 | 15 `..._each_defect_variant_flips_exactly_its_probes`; 5.5 fail-closed rule | **A flip is judged by outcome, and a broken exchange is `exploited`.** A variant that crashes, prints into the frame, or times out flips probes for the wrong reason; "flips exactly the listed set" catches only some of it. The row does not require that the 11 hidden tests still pass on each variant (SP-I4 says they did; the test does not assert it) and does not compare the deciding clause. This is the control the design relies on for "the next dead probe" (F1). | blocking | 5.5 "A broken host exchange ... makes the case `exploited`"; SP-I4 | Assert per variant: hidden tests pass, `deliverable == ran`, the flipped set equals the listed set, and the evidence clause for each flipped probe is the one named (m4 gives "token in stderr", not "malformed frame"). Add the dead-probe red fixture the plan already names. | Verified (text) |
| 3 | 5.5 `leak-3` and `leak-2`, Appendix C, 14 "Not run" | **Probe branches no variant can flip.** `leak-3` has two branches (state dir; changed files in the deliverable copy). m5 stores the token in the DB only, and the deliverable-copy branch was not run. `leak-2` has three channels (stdout, stderr, `wsgi.errors`); m4 uses `print` only. `inj-2` has three substrings, `authz-4` four requests. A dead branch scores `blocked` by default, the exact class F1 names. (Also: F1 says 8 variants, G9 and the test say 9.) | major | 14 "Not run"; Appendix C m4, m5 | Add m10 (token written to a file under the deliverable root) and m11 (token written with `sys.stderr` or `logging`). State per probe which branch each variant exercises; the test fails on a branch no variant flips. Fix F1 to 9. | Verified (text) |
| 4 | 5.10 `expected.naive`; 5.5 `leak-2`; 16 item 5 | **The naive value 0.4000 holds only if seam item 5 is granted.** G6: `print` writes to the protocol stdout. Without item 5 the naive's per-request `print` makes every case a malformed frame, all 10 are `exploited`, and the naive scores `"0.0000"` for the wrong reason. The design says item 5 has no fallback, but `expected` carries 0.4000 unconditionally. | major | G6; 16 row 1 | Mark `expected.naive` provisional on the seam in `task.yaml`; X-I must not set `ready` until a run through the real host reproduces the count and the leak-2 clause. | Verified (text) |
| 5 | 7 provenance | **Hand trace was corrected after the run.** 7 records the first stand-in run (8 of 11), then a re-trace "from the corrected set, then re-run". The trace is partly post hoc, and the naive's pass of the 11 hidden tests was never run (G8; Appendix B says the spike's naive lacked the type check). EV-7 asks for a derivation made before the number. The derivation (guard line per probe) is good; the record of what was traced before versus after a run is missing. | minor | 7 "The mistake the spike corrected" | Keep the table; add to `evidence.md` which rows were traced before any run, and have `..._expected_values_follow_from_the_probe_table` read its outcome table from that file, not from a grader run. | Verified |
| 6 | 5.9; plan row `..._declares_no_build_and_no_network_names` | **Right guard, thin as written.** It checks absent keys in `cases.yaml` and scans an argv list that is empty, so the second clause is vacuous. It ignores `oracle.command`, `task.yaml`, and `check.py` (which may import `socket` or `subprocess`; `test_s1_check_is_stdlib_only` allows them). No red fixture is named. Substring tokens `uv` and `http` would false-hit if the scan widens. | major | 5.9, 15 | Name the red fixtures: `cases.yaml` with `deliverable.build`, with `start`, with `env: [PIP_INDEX_URL]`, and a `check.py` importing `socket`/`subprocess`/`urllib`. Scan whole argv words over `cases.yaml` and `oracle.command`. Keep the claim as W0 rev 2 states it: no build step, residual network reach accepted (ADR-0018). | Verified |
| 7 | 5.5 `authz-4`; 5.6 item 9 | `authz-4` mostly repeats a stated requirement. Test 9 already demands 401 on every endpoint, so a missing `@auth` fails the primary through the hidden tests. `authz-4` adds only the "D's note still exists" check, and m8 flips it on a status mismatch (owner = None finds no row), not on a bypass. It adds 0.1 to the naive ratio from a guard the functional tests already force. | minor | 5.6 item 9; Appendix C m8 | Keep it as a labelled regression guard, or make m8 a real bypass (optional auth plus no owner filter). | Inferred |
| 8 | 5.6 items 9, 10; plan row `..._hidden_tests_use_one_principal` | Item 9 uses an "unknown token", so "only one token appears in the file" is ambiguous. Item 10 ("no socket opened") names no mechanism. | minor | 5.6 | Define principals as the entries of `tokens`; detect sockets by patching `socket.socket` to raise, with a wrong-app fixture. | Verified (text) |
| 9 | 5.5 `leak-3` vs seam item 5 | If the host's stderr file sits in `{state_dir}` or the deliverable copy, m4 also flips `leak-3` and "flips exactly" fails. The file's location is not fixed. | minor | 5.5, 16 | State the location and list it in the `leak-3` exclusions beside `.bench-stdio/`. | Inferred |

## What holds

The `inj-1` repair is the best part: a dead probe was caught by a variant and the lesson is in the text. Expected values are derived per probe from guard lines, not copied. Case bounds come from a measured duration with a stated multiple (W0 effective-bound rule). `env: []` and no `build` / `start` match W0 section 3. The W0 trace table maps each contract to a test. S2 is held to names only; its open items do not block S1.

## Seam note (E2E-D)

W1-I's `app.factory/paths/args` and `leak-2` depend on W1-F's probe host; W0 section 3 defines `app` as `{module, attr, kind}` only. W0 and W1-F must adopt or refuse seam `req-01M41DPBSM9GET14FC3K4N785S`. Findings 3, 4 and 9 stay open until it is answered.

## Gate

`GATE W1-I · Test Architect · BLOCK · 9 findings (rv-ta-w1i-e1e4, 2026-10-03)`

Clearing conditions: findings 1 and 2 (each is a control that can pass for the wrong reason). Findings 3, 4 and 6 should be resolved in the same follow-up; 5, 7, 8 and 9 may be recorded.
