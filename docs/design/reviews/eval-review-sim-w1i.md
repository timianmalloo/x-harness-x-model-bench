---
id: review-eval-sim-w1i
title: "Simplifier lens review of W1-I, security tasks S1 and S2"
type: doc
status: draft
owner: "@timianmalloo"
links:
  - { to: design-eval-seam-contracts, rel: relates-to }
review-by: "2026-10-17"
summary: >-
  RV-SIM (Simplifier, soft veto) findings on docs/design/eval-security-tasks.md (design/eval-security-tasks, 2fc8906b)
  against W0 rev 2 and R-87..R-94 on main. All five probe-host asks are needed by S1 and none is S2-only. The S2 probe
  list is premature for E1. Ten probes reduce to nine or eight, eleven hidden tests to nine, and about six of 21 tests
  repeat a check that W1-F, X-E or another test already owns.
---

# Simplifier review: W1-I security tasks S1 and S2 (rv-sim-w1i-e1e4)

Target: `docs/design/eval-security-tasks.md` on `design/eval-security-tasks` (`2fc8906b`), against W0 rev 2 (`docs/design/eval-seam-contracts.md`) and R-87..R-94 on `main`. Verified = read in the design or W0; Inferred = reasoned. RV-TA and RV-SEC findings are not repeated.

## W1-I: security tasks S1 and S2

| # | location | finding | severity | evidence | fix | confidence |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 5.5 `authz-4` vs 5.6 test 9 | `authz-4` repeats a stated requirement. The prompt says a missing or unknown token gets 401, and hidden test 9 asserts it on every endpoint. A solution that fails `authz-4` (variant m8) already fails test 9 and scores 0. The probe adds only the ratio and a "foreign note survives" read. It is not a latent guard, which blurs F4 ("no test rewards a latent guard"). | major | 5.3 "gets status 401"; 5.6 item 9; 7 naive `authz-4` blocked; 15 `test_s1_authz_4_catches_an_unauthenticated_route` | Drop `authz-4` and variant m8, or move the unauthenticated-DELETE-then-read check into `authz-2` (it already deletes as `S`). Ten probes become nine. Spec classes (injection, authorization bypass, secret leak) are still all covered. Expected naive value becomes 4/9 = 0.4444 before it is recorded. | Verified |
| 2 | 5.5 `inj-2`, 10 F1, 14 SP-I4 | `inj-2` is not independently live. Variant m1 flips `inj-1` and `inj-2` together, so no variant shows `inj-2` catches something `inj-1` misses. Its distinct content is error-text leakage (`str(exc)`), which the design says catches habit. | minor | G9 "inj-1 and inj-2 share one"; SP-I4 m1 | Fold the five quote-break payloads into `inj-1` as extra requests, with the error-text clause added to its predicate. Or keep `inj-2` and add a variant that changes only the error handler (the one edit it claims to catch). Pick one. | Verified |
| 3 | 5.4 `bound_ms: 1600` on ten rows, 5.8, test `..bounds_equal_the_stated_multiple..` | The measured bound does no work. 1600 ms is within 20 percent of the interface default of 2000 ms, it is identical on all ten rows, and a test asserts the arithmetic `1600 = 20 x 80`. A multiplier of 20 over a measurement the design itself calls Inferred for 3.14.6 is a default in disguise. | minor | 5.4 cases; 5.8 "x20 gives 1600, under the interface bound of 2000"; 15 row 18 | Omit per-case `bound_ms` so the interface bound applies, and delete the arithmetic test. Keep the 400 ms trigger as an evidence field. Check first that W0 section 3 lets a case omit it. | Inferred (W0 cases schema not re-read) |
| 4 | 15, test list | About six of 21 tests repeat a check another owner holds or another test already proves. Candidates: `..second_security_task_has_a_different_base` (the row says HB-RDY-007 does it, and S2 does not exist in E1); `..property_check_pass_follows_the_truth_table` (W1-F's grader test); `..case_ids_match_cases_yaml..` (W1-F's `cases.json` validation); `..only_synthetic_values_are_planted` (same regex as `..canary_shape_matches_task_canary`); `..bounds_equal..` (finding 3); `..expected_values_follow_from_the_probe_table` (re-derives what `..reference_blocks..` and `..naive_exploits_exactly..` already pin). | major | 15 table rows 4, 7, 8, 12, 13, 18, 20; memory rule "a test stays only if it catches a failure no other does" | Cut these six, or name for each the failure only it catches. Several are one-time authoring proofs (`pin_is_a_full_commit`, `no_oracle_string..`): run them at readiness, not in the every-push ring. | Verified (rows); Inferred (owners' tests) |
| 5 | 5.6 hidden tests 4, 7, 8, 11 | Four of eleven overlap. Test 7 (empty search) is a second assertion of test 6. Test 4 (missing id 404) is the second half of test 8 (delete then 404) and a branch of test 3. Test 11 (persistence across `create_app`) is not stated as a requirement in the prompt (it says "create the file and its table if they do not exist"), and the design's own test `every_hidden_assertion_is_in_the_prompt` would have to stretch to cover it. | minor | 5.3 first paragraph; 5.6 list | Fold 7 into 6, 4 into 3, drop 11 or add the sentence it needs to the prompt. Eleven become eight or nine. They are cheap to run, so the saving is in prompt and traceability, not time. | Verified |
| 6 | 5.5 payload lists (4 + 5 + 4) | Section 6 cut (4) says "the fewest payloads that flip its defect variant". That is not what the spike shows. One tautology flips m1 and one flips m9. Multiple payloads are justified only as defence against partial fixes (quote-doubling, a numeric check), and nothing says which payload catches which partial fix. | minor | 6 cut (4); SP-I4 | In `evidence.md`, record a leave-one-out for each payload: the variant that only this payload flips, else drop it. | Inferred |
| 7 | 12 S2 probe set, `Open before X-I authors S2` | The S2 probe list is premature for E1. S1's own spike found a dead probe (`inj-1`) that the first, armchair payload set produced (5.5, 7 "mistake the spike corrected"). Section 12 then lists nine S2 probes, the latent sentence and evidence paths without any spike on bottle beyond an import under `-S`. It copies S1's ids (`inj-2` becomes path traversal), so the id list suggests S2 is S1 renamed. Open item 5 ("does the host support a `Bottle` instance without `factory`") is moot: the S2 deliverable line already says `create_app(...)`. | major | 12 table and bullets 3-5; E1 phasing: S2 is E4 (R-89 grid, W0 section 1 row `S2`, E4) | Reduce section 12 to base, pin, licence, tenancy unit and probe classes, and state that ids and payloads are fixed only after an S2 spike in E4. Delete open item 5. Do not spend E1 gate review on S2 payloads. | Verified |
| 8 | 9 variants as files | The nine variants are one-edit mutations of one file. The design does not say how X-I stores them. Nine committed trees would triple the oracle folder and each needs a hash and a review. | minor | 15 `..each_defect_variant_flips..`; Appendix C | Store them as nine `(old, new)` substitutions in one file applied to the reference at test time. The variant test is a readiness-ring proof, not an every-push test: 9 variants x 10 cases is about 90 host starts. | Inferred |

**Kept as earning their place.** Nine of the ten probes (after findings 1 and 2) each have a variant that flips them and a guard named in the reference. The fail-closed rule, one user in the hidden tests (so no test rewards a latent guard), `workspace_from: source` (E5 precedent), no build and no `start` (offline by construction), no shared probe library, no payload DSL and no seed use. The nine variants are the only liveness proof; the design's own spike found a dead probe with them. Keep.

## The five probe-host asks (seam `req-01M41DPBSM9GET14FC3K4N785S`)

| ask | S1 (E1) | S2 (E4) | verdict |
| --- | --- | --- | --- |
| 1 factory app with args | Needed. The prompt fixes `create_app(tokens, db_path)` and the canary tokens must be injected. The fallback (module-level app plus `HB_CHECK_*` env) contradicts the prompt's "importing the module must not open a database". | Same ask, no new field. | Keep. |
| 2 extra `sys.path` | Needed. microdot lives in `src/` of the base (G1); the agent's import would fail without it. | Not needed: bottle is a single `bottle.py` at the root. | Keep for S1. |
| 3 `{state_dir}` placeholder | Needed. Fresh DB per case, and `leak-3` scans it. | Same; the planted outside-file probe also needs a per-case dir the check made. | Keep. |
| 4 complete WSGI environ | Needed. Verified blocker: `REMOTE_ADDR` raises `KeyError`, and `PATH_INFO` must be decoded (G5, SP-I2). This is a host defect, not a feature. | Same. | Keep; ask W1-F to fix it as a defect, not weigh it as an option. |
| 5 stdout and stderr routing | Needed for `leak-2` (no fallback, design 16) and F8 (a printing app breaks the frame protocol on every property task, not only security). | Same. | Keep; it is the one ask whose absence loses a probe. |

**Result: all five are needed by S1, so none is speculative for E1.** None is S2-only; S2 adds no sixth ask once open item 5 is removed (finding 7). The speculative item is S2's payload list, not any host change. The second seam (`req-01M41DT67G68NQ7Y7D8YQM1A98`, start bound) is not in the five. It is not E1-critical: W0's NA fallback covers a blocked import, so ask W1-F for it after the five.

**Seam disagreements.** None between this design and W0 rev 2. One dependency: W1-I section 5.4 adds `app.factory`, `app.paths` and `app.args` beyond W0 section 3's `{module, attr, kind}`. W0 must carry them, or S1's `cases.yaml` fails the W0 schema; the Coordinator should answer the seam request as a W0 amendment, not only as a W1-F note.

Blocking: none. Soft veto not exercised. Findings 1, 4 and 7 should be settled before X-I starts S1.

GATE W1-I · Simplifier · PASS WITH CONDITIONS · 8 findings (rv-sim-w1i-e1e4, 2026-10-03)
