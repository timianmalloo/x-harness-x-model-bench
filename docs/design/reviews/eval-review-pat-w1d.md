---
id: review-eval-pat-w1d
title: "Patterns Expert review of W1-D, engine identity (Adversary Mode)"
type: doc
status: draft
owner: "@timianmalloo"
tags: [review, patterns-expert, evaluation-campaign, wave-1, w1-d]
links:
  - { to: design-eval-seam-contracts, rel: relates-to }
review-by: "2026-10-17"
summary: >-
  RV-PAT review of design/eval-identity (71a15a0b) against W0 rev 2 and R-87..R-93. The injected check, the single
  CLASSES table, import_graph.py and the refusal of a tooling class survive; the refusal's cost model prices only
  grade-side edits and omits the run-side shared kernel, the launch check's reference identity is unfiled, and the
  SUBPROCESS_CALLERS mapping inherits a matcher that misses aliased imports. telemetry/* is provisional.
---

# RV-PAT review: W1-D `docs/design/eval-identity.md` against W0 rev 2

Read in full on `design/eval-identity` (71a15a0b); W0 from `main`. Code opened on `main`: `tests/test_architecture.py:44-52,85-108,222-232`, `cli.py:22-43`. The `telemetry/*` reclassification is the Owner's open ruling (`req-01M41DJ56WN77QNKFCW34GMG3A`) and is treated as provisional.

**Patterns that fit.** Value Object (manifest, named by its hash), Strategy by injected callable (`EngineConfig.identity_check`, as `EngineConfig.grade` already is, so `engine` imports no `plan`), table-driven classification with a coverage test, double-checked read (a second read before a stop), fail closed on a raising check. No `Identity` class, registry or cache: the Simplifier mirror agrees (13 ms measured). Extracting the AST resolver into `tests/import_graph.py` is reuse, not a new abstraction; it has three callers (G2b, G3, X-F's G5). Mutual check with RV-SIM: the injected callable and the single table survive both.

**The refusal of a third class (judging the reasoning).** The conclusion stands for E1; the cost model under it does not.
- (a) holds: `campaign`, `power`, `verdicts`, `gates`, `readiness`, `discriminate` and `synthetic_agent` land before a baseline can exist, so they are frozen by construction.
- (b) conflates two things. "Derive, don't store" says one definition of a quantity; it does not say the deriving code must sit in the freeze. The real alternative to freezing is not an unfrozen module but a hash of it recorded on the verdict and re-derived without a re-grade. Refusing it is a cost argument (an ADR-0017 s1 amendment for, in (c)'s own count, one module), and the doc should say so instead of claiming the test "rejects" it.
- (c) holds on count: only `alarm.py` falls outside "alters a recorded number".
- The cost model (4.3) prices grade-side edits only. See finding 1.
I withdraw the W0 proposal of a `tooling` class for E1 on those grounds, with the conditions in finding 1.

| # | location | finding | severity | evidence | fix | confidence |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 4.1 "a module used by both is run", 4.3 cost | **The cost of the two-class rule is priced on the wrong side.** Run dominates, and `cli.py` (run, exempt from G2b; it imports `grade.judge`, `grade.runner` and `report.*`), `errors.py`, `ledger.py` and `__init__` are run. A post-baseline edit to any of them (a new HB code for a grade module, a campaign or report command, a flag) is a run-side change: runs become ineligible and must be re-run, which is dearer than the re-grade 4.3 prices. 4.3 counts only `grade` fixes, and the revisit trigger watches only `scope: grade` rows, so the trigger cannot see this cost. | major | `cli.py:39-43`; design 4.1, 4.3 | List which E2/E3 tracks touch `cli.py` and `errors.py` after the baseline (W0 s13 owners). Land those edits before the baseline, or name them as recorded fixes with their cost. Extend the trigger to count `scope: run` fixes whose `changes` keys are all in {`cli.py`, `errors.py`}. Read the E1 count at the demo, not after two campaigns. | Verified (imports); Inferred (which later tracks edit them) |
| 2 | 3.1 `launch_check(root, plan)`, 14 F-1 | **Seam: the launch check's reference identity.** It compares the tree with the run-side identity stored in the plan. If the plan was stamped from the working tree, drift between the baseline and the plan is not seen at launch; the reference must be the chain's effective identity. F-1 says only `grid.attached` should compare, and it is "for W1-C": it is not in `req-01M41DJDH521RE0M4QJJK1FRTD` (the 7 W0 changes) or the Owner request. | major | design 3.1, 14 | File F-1 as a seam: W0 s6 says `plan.campaign.identity` is built from the effective identity, and `launch_check` takes it from the plan only after `campaign` has verified it. Test: a plan stamped from a drifted tree is refused at plan time (X-C) and at the first launch. | Verified (text); Inferred (the stamping path, which X-C owns) |
| 3 | 8 D3 entry, `SUBPROCESS_CALLERS` | **The mapping narrows by a matcher that misses aliased imports.** The existing test only matches `subprocess.<attr>` where the receiver is a `Name` (`test_architecture.py:46-50`), so `from subprocess import Popen`, `import subprocess as sp` and `getattr(subprocess, "run")` pass in every file. The old single-file allowlist had the same hole; a per-file attribute allowlist now depends on it. `None` as "any" is a sentinel that reads as "no entry". | minor | `tests/test_architecture.py:44-52`; design 8 | Build `_spawn_offenders` on the alias resolver being extracted to `tests/import_graph.py`, with fixtures for `from subprocess import Popen`, an `as` alias and `os.system` through `from os import system`. Use a named `ANY = frozenset({"*"})`. | Verified (matcher); Inferred (that X-F does not use an alias) |
| 4 | 3.1 `PLANNED`, W0 s9, G3 `IMPORT_LINT_MODULES` | **Four lists of the same modules** (W0 s9 table, `CLASSES`, `PLANNED`, `IMPORT_LINT_MODULES`), kept in step by hand. | minor | design 3.1, 8 | Test that `PLANNED` entries are absent from disk (a landed module must leave it) and that `CLASSES` covers every W0 s9 row. A drift is then red, not a review item. | Verified (text) |
| 5 | 4.1 `RUN_IMPORTS_GRADE_ALLOWED` | **Three run-to-grade edges are allowlisted on a prose trigger** ("when the validators leave `config.py`"). `config.py` (run) lazily imports `egress`, `gateway.backend` and `gateway.scrub` (grade); a change to them can change what the plan validator accepts, and that edit is classed grade. | minor | design 4.1 (`config.py:410,466,467`) | Give each pair an owner and a dated review in the constant, and a test that fails when the lazy import no longer exists (a stale pair). | Verified (text); Inferred (that validation outcome can differ) |
| 6 | 4.2 `telemetry/*` run (provisional) | **If the Owner rules `grade`, the six run-to-grade edges must not enter `RUN_IMPORTS_GRADE_ALLOWED`.** They sit on the spend-cap path (`engine.py`, `driver.py`), which is a run behaviour; an allowlist entry would hide the exact defect the direction test exists for. On the evidence in 4.2 and SP-ID-2 variant B, `run` is the right class. | minor | design 4.2 | If ruled `grade`, keep G2b red until the engine reads telemetry through an injected callable, and record the ruling in ADR-0017 s1. | Inferred (ruling pending) |

**Seam disagreements (E2E-D).** Finding 2 (W1-D F-1 vs W0 s6, not filed). The `sys.platform` and `python` components and the W0 `identity: {hash, components}` shape are covered by the Coordinator's request and not re-raised. No disagreement with W1-A: neither `plan.py` nor `engine.py` edits overlap.

**Residual risk.** Finding 1 is the one that can cost a campaign; it is a scheduling fact, cheap to read now.

GATE W1-D · Patterns Expert · PASS WITH CONDITIONS · 6 findings (rv-pat-ad-e1e4, 2026-10-03)

Conditions: findings 1 and 2 before X-D starts; 3 to 6 may be recorded (6 after the Owner's ruling). Advisory lens; RV-TA's hard gate stands independently.
