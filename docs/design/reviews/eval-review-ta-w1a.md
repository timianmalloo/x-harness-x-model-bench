---
id: review-eval-ta-w1a
title: "W1-A arms v2 design review: Test Architect lens"
type: doc
status: draft
owner: "@timianmalloo"
phase: "Enterprise evaluation: Wave 1 gate reviews"
tags: [review, test-architect, evaluation-campaign, wave-1, w1-a]
links:
  - { to: design-eval-seam-contracts, rel: relates-to }
review-by: "2026-10-17"
summary: >-
  Test Architect (Adversary Mode) review of W1-A against W0 rev 2 and R-87..R-93. The EV-17 map is complete and the
  grid-4 fixture is independent of the new code (derived from the live plan). PASS WITH CONDITIONS: no control that
  checks the on/off literal sweep outside Python, a real-wiring gap behind a faked install_pack, an architecture
  test with no red case, and a boundary case for the balance bound.
---

# Test Architect review: W1-A `docs/design/eval-arms.md` (branch `design/eval-arms`, `ab13f0eb`)

Session `rv-ta-w1a-e1e4`, 2026-10-03. Checked against W0 rev 2 section 5/10, EV-17, and code opened on that tree: `plan.py:118-128` (`expand` takes injected `task_versions`), `cli.py:139-150` (`_workspace_builder`), `grade/_changes.py:84`, `tests/test_cli.py:357`.

## Requested checks

| check | result |
| --- | --- |
| EV-17 map (section 10) | All four criteria map to named nodes; W0 trace table complete. Verified. |
| Grid-4 re-plan test can fail | Yes. The fixture is the 276 rows of the live `runs/grid-4/plan.json` (SP-A1 reproduced it; `expand` takes frozen versions, so no drift from `tasks/`). Dropping `pack` from the ingredient dict or renaming its key turns it red; mutant listed. Conditions: findings 6, 7. |
| Balance bound has a test | Yes, with an independent `Fraction` recompute, a pinned failing seed, the cap and the 1-block refusal. One gap: finding 5. |
| E1/E3 split map has a test for a missed on/off site | **Partly.** The `.pack` token is caught by G1 (and E3 narrowing the allowlist makes the guard fail until readers migrate). Bare `"on"`/`"off"` literals and `report.js` are checked by nothing. Finding 1. |
| G1 red fixtures | Yes for the three forms plus a comment-only file. Finding 4 on completeness of forms. |
| Migrated readers | `views.py:525` and `_changes.py:84` each get a test that is red for the right reason today (a `/2` cell has no `pack` key; `candidate` is wrongly treated as pack-less). `_workspace_builder`: see finding 2. |

## Findings

| # | location | finding | severity | evidence | fix | confidence |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | section 5.1, section 10 | The E1/E3 map is a table, not a control. Sites that use a literal without `.pack` (board.py `{"off","on"} <=`, `packs = ("off","on")`, html.py CSS/filter strings, `report.js:79,147-149`) are caught by no test, so a site missed in E3 is silent. G1 is Python-only and token-based. | major (veto condition: the convergence claim has no verification path outside `.pack`) | section 5.1 rows `board.py:540,555,769`, `report.js`; section 10 has only G1 | Add to `test_arms_guard.py` an AST scan for `Constant("on"/"off")` outside an allowlist (same narrowing in E3), plus a text scan of `report/assets/*.js` for `"on"`/`"off"`. Red fixture for each. | Verified |
| 2 | section 10 criterion 4, `test_cli.py` | The per-arm wiring (`plan.arm_pack` to `pack_checkout` to `install_pack`) is proved only with a faked `install_pack`. The real-git test in `test_workspace.py` calls `workspace` functions directly and never goes through `_workspace_builder`, so a wrong arm-to-commit mapping in `build` passes both. The brief's "fake hides the wiring" shape. | major | section 3.7 vs the section 10 row | One test through `cli._workspace_builder` with two tiny real pack repos (the harness at `test_cli.py:357` already builds `build`), asserting the diff per arm. | Verified |
| 3 | section 10, W0 trace row for section 13 | `test_plan_py_imports_no_campaign_or_identity_module`: neither module exists on main, so it passes before the change. No red fixture shows it can fail. | major | section 10 W0 trace table | Parametrise the scan over a temp tree with a `plan.py` that imports `campaign`; assert it is flagged. | Verified |
| 4 | section 3.8 | G1 forms: `getattr(x, "pack")`, a `Subscript` with a non-constant key, and `cell.get(key)` where `key == "pack"` are not matched. Also `test_allowlist_is_exactly_the_e1_set` is a constant restating itself. | minor | section 3.8 token table | Add `getattr` as a fourth form with a fixture; drop or fold the allowlist-equality test into the E3 narrowing check. | Verified |
| 5 | section 3.4, section 10 | The bound is strict (`< 5/100`) but no case sits at exactly 5/100, and the mutant list has no `<` to `<=` mutant. | minor | section 3.4 "strictly less"; mutant list | A hand-built order with deviation exactly 1/20 must be refused; add the mutant. | Verified |
| 6 | section 10 criterion 2 | Entry point of the grid-4 test is not stated. If it calls `expand` only, `build_plan`, `arms_of` and the `/1` upcast are not on the path, which is where `arm`-keyed cells are built. | minor | `expand` signature, `plan.py:118` | Name it: `build_plan` over the fixture matrix with injected versions and a fake pack record, then compare the 276 ids. | Inferred |
| 7 | section 10, SP-A1 | Fixture provenance is stated as "derivable", not recorded. A fixture regenerated from new code would be circular. | minor | SP-A1 text | Commit a one-line provenance note in the fixture (`source: runs/grid-4/plan.json, sha256`), and forbid a generator in the tests. | Verified |
| 8 | section 10 | New tests import symbols that do not exist yet (`launch_order`, `cell_arm`, `draw_launch_order`). Red-first by `ImportError` is red for the wrong reason. | minor | whole section 10 | Land stubs that raise `NotImplementedError` in the red commit so each node fails on behaviour. | Verified |

No seam disagreement with another design found at W0 section 5/10; the two errata (YAML `off`, SP-A4 fixtures) are accepted as verified.

GATE W1-A · Test Architect · PASS WITH CONDITIONS · 8 findings (rv-ta-w1a-e1e4, 2026-10-03)
