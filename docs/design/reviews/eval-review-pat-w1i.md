---
id: review-eval-pat-w1i
title: "Patterns Expert review of W1-I, security tasks S1 and S2 (Adversary Mode)"
type: doc
status: draft
owner: "@timianmalloo"
tags: [review, patterns-expert, evaluation-campaign, wave-1, w1-i]
links:
  - { to: design-eval-seam-contracts, rel: relates-to }
review-by: "2026-10-17"
summary: >-
  RV-PAT review of design/eval-security-tasks (2fc8906b) against W0 rev 2, R-87..R-94 and the W1-F rev 2 property
  grader. One blocking seam disagreement: S1 needs app.kind wsgi with a factory, which W1-F rev 2 does not build in
  E1 and tells W1-I not to use. Patterns, folder shape, expected values and naming otherwise fit.
---

# RV-PAT review: W1-I `docs/design/eval-security-tasks.md` against W0 rev 2 and W1-F rev 2

Read in full on `design/eval-security-tasks` (2fc8906b). W0 from `main`; W1-F from `design/eval-property-grader` (rev 2). Opened: `tasks/README.md` property section, `tasks/S1/task.yaml` (stub), `tasks/E5/task.yaml`, `src/harness_bench/config.py:259`. RV-TA and RV-SEC findings are not repeated.

## W1-I: security tasks S1 and S2

| # | Location | Finding | Severity | Evidence | Fix | Confidence |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | W1-I §5.4, §16 vs W1-F §4/§5.5 and W0 §3 (seam) | **Two designs disagree.** S1's `cases.yaml` declares `app.kind: wsgi` plus `factory`, `paths`, `args`, `{state_dir}`. W1-F rev 2 builds only `callable` in E1; a task declaring `wsgi` is NA `not built` for every metric, and readiness refuses it (HB-RDY-005). W1-F also tells W1-I to use `callable` (its "To W1-I" note). So S1 as designed scores NA in the E1 demo and in X-E's discrimination run, and cannot reach `ready`. | blocking | W1-F §4 "Not built in E1 ... `app.kind: wsgi`"; W1-F line 619 "S1's check uses `bench_check.probe_host` with `app.kind: callable`"; W1-F line 150 "`wsgi` is added when W1-I or W1-L names a web-shaped deliverable" (E4); W0 §3 `app: {module, attr, kind}` | Coordinator rules one of: (a) W1-F builds a minimal `wsgi` kind in E1 (S1 is then its first caller; W1-F's own E4 deferral is withdrawn), or (b) W1-I redesigns S1 to a `callable` shape. State the choice in both docs and W0 §3. Seam request `...DPBSM9` must be re-addressed to whichever it is. | Verified |
| 2 | W1-I §16 fallback for `...DPBSM9` | The fallback ("module-level `app` from a fixed config path, config via `HB_CHECK_*`") contradicts the prompt, which fixes `create_app(tokens, db_path)`. It also still needs `kind: wsgi`, so it does not rescue finding 1. Item 5 has "no fallback", yet `leak-2` is one of the ten probes. | major | W1-I §5.3 vs §16 | Give item 5 a real fallback (drop `leak-2` to a stdout-only scan and say the probe count becomes 9) or mark S1 not ready until granted. Rewrite the item 1 fallback to match the prompt. | Verified |
| 3 | W1-I §17 A2 | Cites "W1-F's frame shape (§5.5: `headers`, `body_b64`)". W1-F §5.5 defines only the `callable` frame (`id`, `args`, `kwargs`; `ok`, `value`). The wsgi frame the design leans on does not exist in W1-F. | major | W1-F §5.5 "Lines" list | Delete the citation; the wsgi frame is part of the finding-1 ruling, owned by W1-F. | Verified |
| 4 | W1-I §10 F1 vs §2 G9, §15 | F1 says "8 variants"; G9, the summary and the test row say 9. A count that two sections define differently is the defect shape of a miscounted control. | minor | §10 F1 "(8 variants, G9)" | Use 9 in F1. | Verified |
| 5 | §5.5 probe naming and §12 | Probe ids `inj-/authz-/leak-` match W0's `inj-1` example and ADR-0018's three classes. But the same id means different probes per task (`inj-2` is error-text disclosure in S1, path traversal in S2), and `authz-4` is authentication bypass filed under authorization. Cross-task comparison by id is then meaningless. | minor | §5.5 table; §12 probe set | State once that ids are task-local; keep `authz-4` and note the class label is "access control". If path traversal is not injection, name it `trav-1` in S2. | Verified |
| 6 | §6 patterns | Names fit: Parameterized Test, Canary Token, Factory Method (`create_app`), Fail-closed oracle, mutation-based adequacy (the right control for a dead probe; the `inj-1` dead-probe catch in SP-I2 justifies it). "Test Data Builder" is a mislabel for a shared setup step (a Fixture or Object Mother); a builder has fluent construction. Mutual check with the Simplifier: the accepted cuts (no shared probe library, no DSL) hold. | minor | §6 table, row 2 | Rename to "shared Fixture (Setup D)". | Verified |
| 7 | §5.7, §8 vs `tasks/README.md` | README says `oracle/solutions/{reference,naive}/` hold "the two solution trees"; W1-I stores one overlay file per solution and relies on the synthetic cell to overlay it on the engine-built base. Existing tasks (D2, E5) use `oracle/reference/`, not `oracle/solutions/`. The overlay rule is not in README or W0, and the X-E synthetic-cell step that overlays is unread here. | minor | `tasks/README.md` property bullet 5; `ls tasks/D2/oracle` | X-E states the overlay rule, or README is amended by W0's owner; W1-I cites it. | Inferred (X-E not read) |

## Checked and fits

- **Contracts.** `cases.yaml` keys `schema`, `entry`, `interface`, `bounds_ms`, `toolchain`, `env: []`, case `kind: probe` match W0 §3. `measures` empty and the effective bound `min(case, interface)` (1600 under 2000, derived from a measured duration) follow W0 rev 2. `expected` holds exactly the narrowed set `{property_check_pass, exploit_probes_blocked}`, int and `"1.0000"` string forms as `at_scale` requires, with provenance by hand trace (GLD-A).
- **Folder shape.** `task.yaml`, `prompt.md`, `tests/`, `oracle/check/{check.py,cases.yaml}`, `oracle/solutions/{reference,naive}`, `oracle/evidence.md` match README's property bullets; `expected` lives in `task.yaml` and the discrimination record stays in `bench/discrimination/`. `workspace_from: source` is the E5 precedent (`tasks/E5/task.yaml:12`, `config.py:259`).
- **Reference/naive pattern.** Reference scores 1 and naive 0 by the truth table, the naive passes the same hidden tests, and nine seeded-defect variants prove each probe live. This is the right EV-2 / EV-7 shape.
- **Egress.** `BENCHCANARY-S1-<16 hex>` matches W1-F §5.10's `task_canary` regex.

GATE W1-I · Patterns Expert · BLOCK · 7 findings (rv-pat-w1i-e1e4, 2026-10-03)

## Revision 2 re-review, 2026-10-03 (delta only)

Read `design/eval-security-tasks` rev 2 (e95af01a) against W0 rev 3 §3 on `main` (7d7d4d88) and the rev 2 disposition table.

| # | Check | Result | Evidence | Confidence |
| --- | --- | --- | --- | --- |
| 1 | S1 uses W0 rev 3 §3 names exactly | Yes. `app: {module, attr, kind: wsgi, factory, paths, args}`, `{state_dir}` in `args`, `paths` relative to the deliverable root. Request frame `{id, method, path, query, headers, body_b64}` and response `{id, ok, status, headers, body_b64}` are quoted from W0 and used as written. App output for `leak-2` is the file under `<out_dir>/check`, as W0 says. | S1 §5.4, §5.5 vs W0 lines 105-107, 122-128 | Verified |
| 2 | PAT 1 (blocking) | Resolved by ruling C-1; seam table re-addressed. | S1 disposition row PAT 1; W0 line 649 | Verified |
| 3 | PAT 2 | Resolved. Rev 1 fallbacks removed. New rule if the built host lacks item 5: drop `leak-2`, 7 probes, naive blocked {authz-3, leak-1, leak-3} = 3/7 = "0.4286" (arithmetic checked), never default `blocked`, new task version. | S1 §16 | Verified |
| 4 | PAT 3 | Resolved. A2 cites W0 rev 3 names; no unwritten W1-F text cited. | S1 §17 A2 | Verified |
| 5 | PAT 4 | Resolved. G9, F1 and the test row now agree on 13 variants; no "8 variants" remains. | S1 G9, F1 | Verified |
| 6 | PAT 5 | Resolved. Ids stated task-local in §3; `authz-4` cut; S2 path traversal named as its own class. | S1 §3, §12 | Verified |
| 7 | PAT 6 | Resolved. "Shared Fixture". | S1 §6 | Verified |
| 8 | PAT 7 | Accepted as recorded: S1 follows `tasks/README.md` `oracle/solutions/`; X-E is asked to state the overlay rule in its own design. Open item for X-E, not for W1-I. | S1 §5.7 | Inferred (X-E not read) |

New minor note: the 13 variants m9-m13 are Inferred until X-I runs them (S1 says so); the variant test is the control. No new finding.

GATE W1-I · Patterns Expert · PASS · 0 findings (rev 2, rv-pat-w1i-e1e4, 2026-10-03)
