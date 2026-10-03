---
id: review-eval-pat-w1l
title: "Patterns Expert review of W1-L, the eight property tasks (Adversary Mode)"
type: doc
status: draft
owner: "@timianmalloo"
tags: [review, patterns-expert, evaluation-campaign, wave-1, w1-l]
links:
  - { to: design-eval-seam-contracts, rel: relates-to }
review-by: "2026-10-17"
summary: >-
  RV-PAT review of design/eval-property-tasks (5da93d91) against W0 rev 3, R-87..R-96, the merged W1-F strategy and
  registration pattern, W1-G catalog 0.7 and W1-I's task pattern. The pin, NOTICE, wrong-app and variant pattern
  conforms. Seven findings: an E2/E4 phasing contradiction for the shared product-line counter, an agent-editable
  vendored library, an under-specified fault-case predicate, and strategy and catalog fit gaps. PASS WITH CONDITIONS.
---

# RV-PAT review: W1-L `docs/design/eval-property-tasks.md`

Read in full on `design/eval-property-tasks` (5da93d91). Compared with `main`: `eval-property-grader.md` §4, §5.2, §5.7 (rev 3), `eval-catalog-0-7.md` lines 140-149, `eval-seam-contracts.md` §2-§3, `eval-security-tasks.md` (pin rule), `tasks/README.md`, `src/harness_bench/grade/drift.py:73,131`. RV-TA and RV-SIM findings are not repeated.

**Conforms.** Pin and licence pattern (40-hex, `^{tree}` in `evidence.md`, `NOTICE.md`, offline, no `deliverable.build`) matches S1. Wrong-app fixtures, variants and "expected is Inferred until the real host" follow W1-I. Helpers stay out of `GRADERS` (R-90 c4). Metric ids and `property:` tags match the eleven in catalog 0.7. Seams SR-L1 (telemetry `target`) and SR-L2 (loopback with a callable app) are the right asks; SR-L3 is needed (see 6).

| # | Location | Finding | Severity | Evidence | Fix | Conf. |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | §3 single definitions, §4 phasing | `diffstats.product_lines` and `_changes.in_radius` are built by X-LG in E4, yet `rework.py` (X-J2, E2) and RW1 (ready in E2) use both. RW1 cannot be ready in E2. The move also edits `drift.py`, which W0 §13 gives to other hunks. | major | W1-L §3 "moved ... in X-LG's first E4 commit"; §4 RW1 "E2 (X-RW)"; `drift.py:73` (`_in_radius`, private, one caller at :131) | Land `product_lines` and `in_radius` in `_changes.py` as X-J2's first E2 commit; file a seam (SR-L4) for the W0 §13 hunk; `diffstats` imports them | Verified |
| 2 | §7.3 NG1, §7.4 NG2, §7.1 | `vendor/<lib>/**` sits in the agent's workspace. The agent can add `RateLimiter` or `get` to the vendored library; the hidden tests and the resolver then see the edited copy and the count is 0. The design says the resolver uses "the vendored path" without saying whose copy. | major | §3 grain row `vendor/<lib>/**` "the agent (readable)"; §7.1 "sys.path = the vendored path only"; blast radius excludes `vendor/` | Grading overlays the pristine `vendor/` from `tasks/<ID>/workspace/` onto the grading copy before the tests and the resolver; add `v-vendor-edit` (reference plus an added member) that must keep the count at the true value | Inferred |
| 3 | §9.1, §9.2 `f-slow-first`, `g-slow-first`, `f-lost-response` | The case predicate says `effects == 1` if the call "should succeed", `0` if it "should fail", but no case declares which. After a slow first response the effect is already applied. A correct call that raises `LedgerError` at 3 s fails the effect clause, and one that retries passes: the prompt only promises "return or raise within 3 seconds". This contradicts §13 "predicates accept sets of correct behaviours". | major | §9.1 clause 3; prompt shape §9.2; `v-attempt-3s` flips by time | Add `expect: succeed \| fail \| either` per case in `cases.yaml`; for `either`, the effect clause is `effects <= 1`; keep `succeed` only where the prompt makes it unavoidable (`f-5xx-burst`) | Verified (text) |
| 4 | §3, §6.1, §7, §8.1, §10 vs W1-F §5.2, §5.7 | W1-F's strategy table is `(CellInput, GradeContext) -> dict[str, Score]`, keyed by `config.PROPERTY_NAMES` (`rework`, `no-guessing`, `simplicity`). W1-L never names the three `STRATEGIES` lines or keys (it says only `noguess`, `diffstats`). W1-F has one evidence file `property.json` that the rebuild test reads; W1-L §10 adds `rework.json`, `diffstats.json`, `noguess.json`. W1-F's `property_check_pass` table has no ceilings clause; W1-L adds "ratio ≤ ceiling" and calls `correctness.grade` per tree itself without the reparse-safe copy, per-phase span or `procs` job. | major | W1-F §5.2 `STRATEGIES` line 192; §3 evidence file table; §5.7 table | State the three lines (`"rework": rework.grade`, `"no-guessing": noguess.grade`, `"simplicity": diffstats.grade`); each helper writes a section of `property.json`; put the ceilings clause in W1-F §5.7 by a seam to X-F; name the resolver spawn through `procs.spawn` with the `_env.py` allowlist | Verified |
| 5 | catalog 0.7 `hallucinated_symbol_errors` row vs §7.1 | Catalog anchor note says "cap at 5 build-log errors naming a missing member". Option A of DR-L1 is a final-tree static count. If the Owner rules A, W1-G's note and anchor basis are wrong, and no seam goes to X-G1. | minor | `eval-catalog-0-7.md:145` | Add a note on DR-L1: the ruling must name the catalog edit; send the seam on ruling | Verified |
| 6 | §8.1, SR-L3 vs `tasks/README.md:47` | README makes `oracle/check/` plus `cases.yaml` part of the `bench validate` contract. SR-L3 asks readiness to accept their absence; the README is not in the ask. | minor | `tasks/README.md:47` | Extend SR-L3: amend that README line to "check-based properties only" in the same change as `readiness.py` | Verified |
| 7 | §15 `test_<id>_pin_is_a_full_commit` | W1-I's pin test also asserts the engine-built base has the `^{tree}` hash in `evidence.md`. W1-L's fixtures name only a branch and a missing `NOTICE.md`. | minor | `eval-security-tasks.md` §15 `test_s1_pin_is_a_full_commit` | Add the tree-hash fixture (a wrong tree hash) | Verified |

**Seams.** SR-L1, SR-L2, SR-L3 and DR-L1 are consistent with W0 §3 text. Finding 1 needs a new seam (SR-L4) and finding 4 needs one to X-F. No two merged designs disagree at a seam beyond 4 and 5.

GATE W1-L · Patterns Expert · PASS WITH CONDITIONS · 7 findings (rv-pat-w1l-e1e4, 2026-10-03)
