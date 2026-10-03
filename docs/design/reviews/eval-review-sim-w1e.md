---
id: review-eval-sim-w1e
title: "Simplifier review of W1-E (discriminate, synthetic profile, readiness)"
type: doc
status: draft
owner: "@timianmalloo"
links:
  - { to: design-eval-seam-contracts, rel: relates-to }
review-by: "2026-10-17"
summary: >-
  RV-SIM (Adversary Mode, soft veto) on design/eval-discriminate 549f7bc4 against W0 rev 5 and R-98. PASS WITH
  CONDITIONS: the SyntheticLauncher, variants-as-cells and the HB-RDY set are the smallest correct mechanism for E1;
  defer the empty FROZEN registry (HB-RDY-009) to E4, fold about ten test nodes, key the run link by record name,
  and drop the build re-hash.
---

# Simplifier review: W1-E, discriminate and readiness

Reviewed: `docs/design/eval-discriminate.md` @ `design/eval-discriminate` 549f7bc4, against W0 rev 5 (sections 2, 6, 7, 9, 11) and R-98. RV-TA (BLOCK) and RV-SEC (PASS WITH CONDITIONS) findings are not repeated. Code opened: `engine.py:60-90,618-630`, `plan.py:240,272-345`, `config.py:34,117`. Confidence: Verified = opened; Inferred = reasoned.

## Is each mechanism the smallest correct one for E1?

| mechanism | verdict | why |
| --- | --- | --- |
| `SyntheticLauncher` + stdlib ACP agent | keep (one trim, finding 4) | Reuses the `Launcher` port; spike S-E1 ran it with no `engine.py` edit. The alternatives are weaker or bigger: an in-process fake skips the engine-built working copy (ORCL-A), an `engine.py` edit costs a seam. |
| variants as extra cells of the same run | keep | The grading pass and the probe host already do everything a variant trial needs; a separate harness would be a second grading path. Cost is wall time (15 serial cells for S1, unmeasured; the design names it as a join check). The `edits[{file,old,new}]` table is a third way to build a tree beside the overlay (`oracle/variants/<name>/` dirs would reuse s6 rules 1-4); W0 s2 already fixes the table, so revisit when a second task authors variants, not now. |
| ~35 test nodes | cut to about 24 (finding 2) | 36 ids, two of them (T-E29, T-E30) are join checks, not tests. |
| HB-RDY-001..011 | keep ten, defer one | 001-005, 010, 011 are distinct operator actions. 006-008 are cheap static checks EV-1/EV-7 require. 009 is vacuous in E1 (finding 1). |
| discrimination-link reconciliation | keep, simpler (finding 3) | ADR-0016 s4 asks for it and R-98 leaves the link as the only tie. It runs only where `runs/` exists, so it can never be a gate input; the design already prints `note:` and never fails. |

## Findings

| # | location | finding | severity | evidence | fix | confidence |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | s8.2 row EV-7 b8, HB-RDY-009, T-E23 | `FROZEN` is a registry "empty for property tasks in E1" (the design's own scan: 3 `statement_hash` files, none a property task), built for X-LG's E4 recipe, with a test that injects a fake registry. Speculative generality with a code path no E1 task reaches. Defer to X-LG in E4, where the first real entry and its red fixture arrive together. Needs a W0 s11 note that HB-RDY-009 lands in E4 (the row says E1). | major | W1-E s8.2 and s13 row 3; W0 s11 HB-RDY-009 | Remove `FROZEN`, T-E23; move the HB-RDY-009 owner/phase to X-LG, E4. | Verified (design text); the deferral itself is a judgement |
| 2 | s14.3 test plan | Thirty-four real tests, many driving the engine (2 to 15 cells each). Folds that keep every assertion and drop only a function or a trial: T-E22, T-E24, T-E26, T-E27 into T-E25's parametrization (same `make_task` builder, same `problems` call; four fewer); T-E18 into T-E17 (same temp fixture); T-E4 into T-E2 (same `disc_c` trial, and "never deletes" tests code nobody writes); T-E34 and T-E36 into T-E1a/T-E1b as assertions on the record, link and agent environment of that trial (two fewer engine runs); T-E21 into T-E11 (TA 11 already wants it through `discriminate`); T-E23 per finding 1. About ten fewer nodes and about five fewer engine trials; red-first, fixtures and mutants stay. T-E1a duplicates T-E1b's path once X-F lands: keep it only until then. | major | W1-E s14.3, rows named | Apply the folds; keep a mutant per folded assertion. | Verified (rows); Inferred (that folds lose nothing: check each mutant column survives) |
| 3 | s4.3 run link; s8.2 row 004 | The link is found by "the newest link whose `record` equals the record's path": a scan of `runs/*/discrimination-link.json` plus a recency rule the file's own stamp decides (SEC F6 is about the same hole). One fixed name removes both: `runs/discrimination-links/<record file stem>.json`, rewritten per trial (it is local, not a fact), holding `run_id`, `grading_id`, timings and counts. Lookup is a path; "newest" disappears; T-E28 gets simpler. | minor | W1-E s4.3; R-98 (link local) | Key the link by record stem. | Inferred |
| 4 | s5.1 `check_build` | `check_build` re-hashes `synthetic_agent.py` against `builds["synthetic"]` and raises `BuildChanged`. The file is grade class (W0 s9, seeded by X-D), so the identity manifest already hashes it and a trial and its record carry that identity; the plan and the cell run in one process within seconds. The engine only needs a dict back and `plan.builds` a key (`plan.py:288-290` raises HB-PRE-007 without it). Return `{"version": SYNTHETIC_VERSION}`; drop the sha256 pair and the `BuildChanged` branch. | minor | `engine.py:625-632`; `plan.py:288-290`; W0 s9 row for `synthetic_agent.py` | Constant dict. | Verified (readers); Inferred (that nothing else reads the sha) |

## What can wait for E3/E4

HB-RDY-009 and `FROZEN` (finding 1). Beyond that, nothing in the E1 build path: multi-turn and loopback are already refused ("not built in E1"), `--all` is already deferred, and the `clauses` comparison rides on evidence X-F writes anyway. Two review items the design could also defer, left as the author's call: `not_comparable` counts and `start_ms` in the link are telemetry the first campaign will not read until E3.

**Seam disagreements.** W0 s6 (main, record body with ids, option (a)) vs W1-E s4.2 (no ids): R-98 decides for W1-E; W0 rev 6 and the design's leftover option-(a) fallback text (s4.3, s15) are stale (RV-TA 3 covers the design side).

Blocking: none. Soft veto: not exercised; findings 1 and 2 should be applied by the author's follow-up before X-E starts.

GATE w1-e-discriminate · Simplifier · PASS WITH CONDITIONS · 4 findings (rv-sim-w1e-e1e4, 2026-10-03)
