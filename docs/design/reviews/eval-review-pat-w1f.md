---
id: review-eval-pat-w1f
title: "Patterns Expert review of W1-F, the property grader (Adversary Mode)"
type: doc
status: draft
owner: "@timianmalloo"
tags: [review, patterns-expert, evaluation-campaign, wave-1, w1-f]
links:
  - { to: design-eval-seam-contracts, rel: relates-to }
review-by: "2026-10-17"
summary: >-
  RV-PAT review of design/eval-property-grader (441da4ba, e41289a2) against W0 rev 2 (3c1c9827). Patterns named
  correctly, four divergences from W0 rev 2 flagged as seams, no blocker.
---

# RV-PAT review: W1-F `docs/design/eval-property-grader.md` against W0 rev 2

Read in full on branch `design/eval-property-grader`; W0 rev 2 read from `main` at 3c1c9827. Pattern fit is good: Strategy via the existing `GRADERS` registry plus `STRATEGIES` (R-90 c4), Special Case (NA `Score`), Gateway (`procs`), Acknowledged Message (one-byte ack, spike E1-S3), an out-of-process proxy for the probe host, and a decision table for classification. W0 rev 2 did adopt W1-F's names and outcome order for rows 1-4.

| # | location | finding | severity | evidence | fix | confidence |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | W1-F 5.7 vs W0 rev 2 section 3 | **Seam.** W1-F records a primary **0** for a tampered run whose hidden tests failed ("known 0 is not raised") and uses a Kleene table. W0 says the first matching outcome row decides, so rows 1-5 are NA for the whole run, and its test list says "tamper NA". Two docs give two answers for the same cell. The Kleene idea is sound but it changes what a score row means for the pilot gate and the discrimination record. | major | W1-F 5.7 rows "0 \| any, including NA \| 0" and line 280; W0 `eval-seam-contracts.md:152,164`, `:150` ("tamper NA") | Pick one and write it in both. Smallest: keep W0 (NA wins on rows 1-5) and drop the 0-on-NA rows from W1-F; if the Kleene rule is wanted, W0 must say "an outcome row decides the secondaries and the check conjunct; the primary follows Kleene". Seam request to the Coordinator. | Verified |
| 2 | W1-F 5.6 row 5 vs W0 outcome table | **Seam.** W1-F adds a row "no document, exit code 5" to HB-CHK-001 and narrows tamper to "no document with exit other than 5". W0 has no such row, and its row 4 lists "no line" as tamper. | minor | W1-F `:247-248`; W0 `:159-160` | Add the exit-5 row to W0 (it is a check-error label), or drop it from W1-F. | Verified |
| 3 | W1-F 5.3, 5.6 rule 6 vs W0 framing | **Seam.** Result size cap differs: W1-F `MAX_RESULT_BYTES = 1 MiB`, "over 1 MiB" malformed; W0 framing: one line, "at most 64 KiB". The probe-host line cap (1 MiB) is a different thing and is fine. | minor | W1-F `:194,249`; W0 `:144` | One constant, one number, named in W0; W1-F cites it. | Verified |
| 4 | W1-F 5.6 rule 1 vs W0 "bounds per phase" | **Seam.** W0: the suspend rule (HB-CHK-004) applies to **each phase's** span, including each test run. W1-F's rule 1 says "over the check step" only, so a suspend during the hidden-tests phase can turn `correctness.grade` into a measured 0 with no HB-CHK-004. | major | W1-F `:244`; W0 `:131` | Either apply `SleepDetector` around the tests phase too (reuse the same helper, one definition) or state that correctness already covers it and cite where. | Verified (text); Inferred (that correctness lacks it; not opened) |
| 5 | W1-F 5.9 vs W0 section 3 `env` | **Seam.** W0 says a dotnet toolchain's names are `correctness.DOTNET_HOST_ENV`, "imported, never copied". W1-F moves the definition to `grade/_env.py` and has `correctness` and `mutation` import it. W1-F's direction is the better one (one home, DM7), so the W0 text should change. | minor | W1-F `:301-309`; W0 `:112-113` area | Coordinator edits W0 to "defined in `grade/_env.py`". | Verified |
| 6 | W1-F 6, "Half-Sync process boundary" | Mis-named pattern. Half-Sync/Half-Async is a threading layering pattern. The probe host is an out-of-process proxy / broker with a narrow line protocol (Proxy + Sandbox). A wrong name sends the implementer to the wrong literature. | minor | W1-F `:329` | Rename to "Out-of-process Proxy (sandboxed broker)". | Verified |
| 7 | W1-F 5.6 "Chain of Responsibility" | The code shape described (ordered rules, first match wins, one function) is a decision table / rule list, not a Chain of Responsibility (no handler objects, no successor links). Naming it CoR invites a class hierarchy the Simplifier rightly rejects. | nit | W1-F `:330,253` | Call it an ordered decision table; keep it one function returning `Classification`. | Verified |
| 8 | W1-F 5.2 `STRATEGIES` | Dict of `Callable[[CellInput, Context], dict[str, Score]]` where `security` and `resilience` share `_hidden_check`: fine. But `Context` is not defined in the design (W1-F 5.4 defines a different `bench_check.Context`). Two types with one name in one module family. | minor | W1-F `:162,206` | Rename the grader-side one `GradeContext`. | Verified |
| 9 | W1-F 3, 5.1 | Narrowing matches W0 section 7 c1 exactly (`applicable(catalog, graders, prop=None)`, tagged applies only on equal tag, `None` means untagged only, task-changed fallback gives `property_check_pass` NA). The three-reader requirement (runner, readiness, discrimination) is met by naming the single function. | nit | W1-F `:149-155`; W0 `:325` | none; the earlier RV-PAT 3 is closed here | Verified |
| 10 | W1-F 4 (`correctness.grade` through the module attribute) and 14 | Good seam: module-attribute call so tests substitute a `Result` (Test Double at one boundary). Check also covers R-90 c2 one-definition. Noted so the Simplifier need not revisit. | nit | W1-F `:142` | none | Verified |
| 11 | W1-F 5.2 imports vs W0 section 9 | `grade/property.py` is class grade and imports `plan.tree_hash`, `procs`, `egress` (existing modules, presumably run-class). The direction grade imports run is allowed by W0 rule, but X-F edits `procs.py` and `egress.py` in E1: an edit to a run-class file is a run-side identity change, forcing re-runs, for a grader feature. W1-F changes `spawn` only by a defaulted keyword, so behaviour is unchanged, but W0/W1-D should record it. | minor | W1-F `:284-295,312-314`; W0 `:373` rule | W1-D to confirm the class of `procs.py` and `egress.py`; X-F to prove the default path byte-equal (the US-4-style control W1-F already uses for `_env`). | Inferred (existing classes not opened) |

**Seams (E2E-D).** W1-F vs W0 rev 2: findings 1, 2, 3, 4, 5 (five items; 1 and 4 matter). Rows 1-4 of the outcome order and the narrowing agree. All five go to the Coordinator as W0 edits or W1-F edits; none needs the Owner.

**Residual risk.** The primary-score rule on a tampered run (finding 1) feeds the discrimination record and the pilot gate; if left split, X-E will implement one and X-H1 the other.

GATE W1-F · Patterns Expert · PASS WITH CONDITIONS · 11 findings (rv-pat-e1e4, 2026-10-03)
