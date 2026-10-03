---
id: review-eval-sim-w1d
title: "Simplifier lens review of W1-D, engine identity"
type: doc
status: draft
owner: "@timianmalloo"
links:
  - { to: design-eval-seam-contracts, rel: relates-to }
review-by: "2026-10-17"
summary: >-
  RV-SIM (Simplifier, soft veto) findings on docs/design/eval-identity.md (design/eval-identity, 71a15a0b) against
  W0 rev 2 and R-87..R-93 on main. The refusal of a third class is accepted; tests/import_graph.py earns its place;
  the second-read torn-read guard and the doubled grade-side hash need a reason or a trim. telemetry/* is provisional.
---

# Simplifier review: W1-D engine identity (rv-sim-ad-e1e4)

Target: `docs/design/eval-identity.md` on `design/eval-identity` (`71a15a0b`), against W0 rev 2 and ADR-0017 on `main`. The telemetry/* reclassification (request `req-01M41DJ56WN77QNKFCW34GMG3A`) is with the Owner and is provisional here. Filed seam requests are not re-raised.

## W1-D: engine identity

| # | location | finding | severity | evidence | fix | confidence |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 0 row 1, 4.3 no third class | Accepted; my W0 finding 4 is withdrawn for the derive modules. My cure ("classify by whether a change alters a recorded number") does not rescue them: `campaign`, `power`, `verdicts`, `gates`, `readiness` and `discriminate` produce what a verdict shows, and most land before a baseline can exist, so the mid-campaign cost is only `alarm`, `resume` and later helpers. One module does not justify a second axis plus an ADR-0017 amendment. Two classes is the smaller system, and the revisit trigger is read from rows already in the ledger (no new instrument). | none | 4.3 (a)-(c) | none | Verified (the reasoning); Inferred (that only `alarm` is outside the test) |
| 2 | 4.3 trigger | The trigger fires on "two campaigns" with nine module names written out. That list is a second copy of module names to keep in step with `CLASSES`. | minor | 4.3 last bullet | state it as "grade-scope fixes whose keys are all in modules W0 s9 marks derive-only", no literal list | Verified |
| 3 | 7 / 5 torn-read second call | A second whole-manifest call before stopping, to absorb a torn read. No torn read is observed or measured; it is a guess about a Windows merge window. It also overlaps the in-read retry (3 x 50 ms) for locked files: two retry mechanisms with different timing. An immediate second call (no delay) may land in the same rewrite window, so it protects least where it is needed. The cost is small (it runs only on a diff) but it carries a test, a mutant and a "drop the second read" row. | minor | 5 "Where"; 7 rows 1-2; 12 mutation row | use one mechanism: on a non-empty diff, re-hash only the differing keys once after the existing 50 ms delay; or drop the second read until a false `HB-IDN-001` stop is seen in a ledger. If kept, mark it `simplify:` with that trigger | Inferred |
| 4 | 8 / 10 `tests/import_graph.py` | Earns its place. It is an extraction of the existing resolver (`test_architecture.py:90-105`), not new code, and it has three named consumers (G2b, G3, X-F's G5). Writing the resolver three times would be the defect. Keep. | none | 8 G3 bullet | none | Verified (extraction and consumers as stated; not run) |
| 5 | 6 `grade_identity_hash` in E1 | The E1 placement is forced: ADR-0017 section 5 requires the grading pass to carry the grade side of the current identity, and the first verdict needs it. The implementation is one composition of existing functions, no new function, no stored components. The residue is two hashes over `grade/*.py` in one row: `grader_build` (names only) and `grade_identity_hash`. The doc says the manifest entries are "not a second definition", which holds only while both are kept. | minor | 6 paragraph 1; ADR-0017 line 48 | add one line: `grader_build` is retained for non-campaign passes only; state the removal trigger (campaign becomes the only path) | Verified (ADR text); Inferred (that `grader_build` can later go) |
| 6 | 8 D3 entry `SUBPROCESS_CALLERS` | A mapping of file to allowed attribute set, to let `bench_check.py` call only `Popen`. The narrowing blocks `subprocess.run` in a file X-F writes, resting on an `assume:` about code not yet merged. A bare two-path allowlist is simpler and fails no known case. | minor | 8 D3 bullet, the marked assume | start with `{procs.py, grade/bench_check.py}`; add the `Popen` narrowing when a second call form appears | Inferred |
| 7 | 4.2 table, 5, 10 | The per-file table (69 files plus 18 planned) is the right table-driven shape: one table, a coverage test, HB-IDN-002. No abstraction was added (no `Identity` class, no cache; 13 ms measured against a 250 ms budget). Noted as a model of the Ladder. | none | 10 Simplifier pass; 5 Budget | none | Verified |
| 8 | 4.2 telemetry/* | Provisional. On the doc's reading of the `engine.py` and `driver.py` imports, the run-class reading removes 6 allowlist edges; the amendment is the smaller system if the Owner confirms. If the Owner rules grade, `RUN_IMPORTS_GRADE_ALLOWED` grows by 6 pairs and G2b stops being a clean rule. | minor | 4.2 finding; SP-ID-2 variant B | follow the Owner ruling | Inferred |

**Seam disagreements:** none new. For `req-01M41DJDH521RE0M4QJJK1FRTD`, I support the `catalog_hash` single definition only if its fallback test (`test_catalog_component_equals_runner_catalog_hash`) stays.

Blocking: none. Soft veto not exercised.

GATE W1-D · Simplifier · PASS WITH CONDITIONS · 8 findings (rv-sim-ad-e1e4, 2026-10-03)
