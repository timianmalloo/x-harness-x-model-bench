---
id: review-eval-sim-w1f
title: "Simplifier lens review of W1-F, the property grader"
type: doc
status: draft
owner: "@timianmalloo"
links:
  - { to: design-eval-seam-contracts, rel: relates-to }
  - { to: design-eval-property-grader, rel: relates-to }
review-by: "2026-10-17"
summary: >-
  RV-SIM (Simplifier, soft veto) findings on docs/design/eval-property-grader.md (design/eval-property-grader,
  441da4ba and e41289a2) checked against W0 rev 2 on main 3c1c9827.
---

# Simplifier review: W1-F (rv-sim-e1e4)

Target: `docs/design/eval-property-grader.md` on `design/eval-property-grader`, against W0 rev 2 (`main` 3c1c9827). Confidence: Verified = read in both documents or in code; Inferred = reasoned.

## W1-F: the hidden-check runner and the property grader

| # | location | finding | severity | evidence | fix | confidence |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | W1-F §5.6 vs W0 rev 2 §3 outcome table | Seam disagreement on classification. W0 has 7 rows and puts "no line" under row 4 (`invalid (check tampered)`, HB-CHK-002). W1-F has 8 rules and sends "no document at EOF with exit code 5" to rule 5 (`check output invalid`, HB-CHK-001), and numbers the measured 0 as rule 7 (W0: row 6). Tests named "one per row" will not map to the same numbers. | major | W1-F `:247-251` vs W0 rev 2 outcome table (rows 4-7, "no line") | Conform to W0's seven rows and renumber, or send one seam request that adds "check error (exit 5)" as a W0 row. The label-only split of exit 5 is the kind W1-F itself calls forgeable (N8), so the cheaper fix is W0's single row | Verified |
| 2 | W1-F §3, §4, §5.7 vs W0 rev 2 "Not built in E1" | W0 says `kind: fault`, `bounds_ms.loopback`, `deliverable.config` are unread in E1 and "W1-F does not build them". W1-F builds, in E1, the `fault` and `static` outcome sets in the validator (§5.4), `fault_suite_pass` derivation and `idempotency_violations` normalising (§5.7, §3 table "yes"), and registers `"resilience": _hidden_check` (§5.2). All of it has no E1 caller (S1 is a security task). | major | W1-F `:107-109`, `:162-167`, `:223`, `:275-277`; W0 rev 2 "Not built in E1" bullet | Build E1 for `probe` only. Move the fault, static and idempotency code, and the `resilience` registration, to X-LB/E4. Costs: 2 derivation branches, 1 dict line, about 6 validator cases and their tests | Verified |
| 3 | W1-F §5.5 | The probe host carries two kinds, `callable` and `wsgi`, with a base64 request/response schema for wsgi. No E1 task is named that needs wsgi. A second wire format is a second thing to keep honest against the forgery fixtures. | minor | W1-F `:229-232`; W0 rev 2 `app:` line (`kind: callable | wsgi`) | W0 allows narrowing: ship `callable`; add `wsgi` when W1-I or W1-L names a web-shaped deliverable. Keep the `kind` key so the task file does not change | Verified (text); need for wsgi Inferred |
| 4 | W1-F status, 13 "provisional (seam ...)" marks, Gate line | Stale against W0 rev 2. The design says it is waiting for the three seam requests and for W0 §3 to be amended. W0 rev 2 has applied them (probe host, `app:`, `deliverable`, `cases.json`, `-S`, phase order, bounds). Every "provisional" tag makes X-F and the reviewers check a closed question again (same class as my W0 finding 1). | major | W1-F `:40`, `:174`, `:215`, `:225`, `:238`, status and gate lines; W0 rev 2 lines on `-S`, `cases.json`, `app:` | Author removes the tags, rewrites §16 as "answered in W0 rev 2", and states the one remaining seam (`req-…QMZ`, X-D allowlist entries) | Verified |
| 5 | W1-F §3 evidence vs W0 rev 2 §3 and §7 | Two names for one fact: W1-F writes `hidden_tests[tree] = {passed, partial_credit, reason, evidence, hidden_tests_ms}`, W0 and `readiness.hidden_test_disagreements` read `hidden_tests_pass`. Also W0 rev 2 places `at_scale(value, scale)` in `grade/property.py` for readiness to import, and W1-F's change-surface list (§7) never mentions it. | major | W0 rev 2 evidence bullet, `at_scale` bullet, §7 condition 3; W1-F `:121`, `:349` | Use W0's field name (or state the mapping in one line) and add `at_scale` to §5.7 and §7 with its test. Without it X-E and X-F each write a normaliser | Verified |
| 6 | W1-F §5.2 code block | The `STRATEGIES` dict is shown with three commented-out future entries. Commented-out code in a design block gets copied into the tree (HYG-A), and the same lines name E2/E4 modules that R-90 c4 only allows when they exist. | minor | W1-F `:162-167` | Keep the E1 dict (`security` only after finding 2); describe E2/E4 helpers in prose | Verified |
| 7 | W1-F §13 vs §3 | Two stores for the same fields: the `property.json` evidence file and the two `grade.property.*` log events repeat `cases`, `failing_cases`, `hidden_tests_ms`, `exit_code`, `bound_fired`, `suspended`. A copy that is not the record is a second definition. | minor | W1-F `:116-126`, `:439-441` | Events carry the classification code, `wall_ms` and the evidence path only; the rest reads from `property.json`. Fewer fields for `test_check_event_fields` | Verified |
| 8 | W1-F §5.4 / §5.3 | Exit codes 3, 4, 5, 10, byte `0x06`, `sweep` rounds, `PROPERTY_SUSPEND_GAP_S`, a 1 MiB result cap and a 64 KiB stdio cap are each defensible, but the protocol is spread over five sections. A builder must hold 5 exit codes and 8 rules together. | minor | W1-F §5.3 step 4-5, §5.4 `write_result`, §5.6 | One small table "exit code, who sets it, rule it feeds" in §5.3. No new rules | Verified |
| 9 | W1-F §5.9 | `denied()` re-lists `profiles.DROP_EXACT`/`DROP_PREFIXES` plus three names. If `profiles.py` already defines the set, import it; do not copy it. W1-F says "profiles.DROP_*" so intent looks right but the file is not shown to be imported rather than copied. | minor | W1-F `:305` | State "imports, never copies", as W0 does for `DOTNET_HOST_ENV` | Inferred |

**Resolved since my W0 review (checked):** G4's token. W1-F uses `\bHOST_ENV\s*=` (`:1` of §14 D3). `DOTNET_HOST_ENV =` has `_` before `HOST_ENV`, which is a word character, so there is no boundary and the guard stays green on the dotnet constants. W1-F also keeps `mutation.py`'s `PROCESSOR_ARCHITECTURE` difference as a named constant. This closes my W0 finding 3.

**Sound, no finding:** one registered `property` grader and no second registered grader (R-90 c4); the Kleene primary table follows from the EV-1 rule; the measured 0 keeps `Score` unchanged; the stdlib-only handshake, with HMAC and nested jobs rejected with reasons; `simplify:` markers carry a ceiling and a trigger.

**Seam disagreements:** W1-F §5.6 vs W0 rev 2 outcome table (1); W1-F §3/§5.7 vs W0 rev 2 "Not built in E1" (2); W1-F evidence field name vs W0 rev 2 (5).

Blocking: none. Soft veto not exercised. Findings 1, 2, 4 and 5 should be applied before RV-TA and RV-SEC clear the gate, since they change what X-F builds.

GATE W1-F · Simplifier · PASS WITH CONDITIONS · 9 findings (rv-sim-e1e4, 2026-10-03)
