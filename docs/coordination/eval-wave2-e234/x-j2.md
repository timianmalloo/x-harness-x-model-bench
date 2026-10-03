---
id: brief-eval-x-j2
title: "Brief X-J2: _changes, the rework grader, per-turn synthetic cells and multi-turn discrimination (E2) - unblocked by W1-J rev 2"
type: plan
status: proposed
owner: "@timianmalloo"
links:
  - { to: coordination-eval-wave2-e234-briefs, rel: implements }
  - { to: design-eval-property-tasks, rel: depends-on }
  - { to: design-eval-seam-contracts, rel: depends-on }
  - { to: design-eval-multi-turn, rel: depends-on }
review-by: "2026-10-17"
summary: "X-J2 lands grade/_changes.py's four counting functions (J2a, waits on the X-F and X-A1a joins), then rework.py, per-turn synthetic cells, the multi-turn discrimination path and the variant reader's two new edit forms (J2b, unblocked by W1-J rev 2's gate; waits on X-J2a, X-E, X-LB0 and X-J1's turn record), on Agy gemini-3.8-flash-high."
---

# X-J2: counting rules, rework grader, multi-turn discrimination

> **J2a waits on E1 joins only** (X-F, X-A1a: the E1 writers of `grade/_changes.py`); compiled (CO-S0, Coordinator #9). **J2b is unblocked by design:** W1-J rev 2 passed its gate and merged (`f23d35ed`), so the turn record it grades is fixed. J2b still waits on X-J2a, X-E joining (the E1 owner of `discriminate.py`, `synthetic_agent.py`, `profiles.py`) and X-LB0 (`property.hidden_tests`); it builds against X-J1's record contract with fixtures, and its turn-1 snapshot test needs X-J1 joined.

**Harness** Agy, `gemini-3.8-flash-high` · **contract** `x-j2.contract.json` (J2a; J2b reuses it with the suffix `b`) · **deadline** 3,300 s per dispatch · **budget** 160 calls · 180k · 2 dispatches · 2.5 h · **fallback** a Sonnet follow-on in the same tree (R-87 Option 1).

**Design:** W1-L `docs/design/eval-property-tasks.md` §3, §5.1, §6.1 with *Erratum 1*; W1-J rev 2 (`docs/design/eval-multi-turn.md`, merged `f23d35ed`) §2, §3, §4.2 for J2b; W0 rev 6.6 or later §2 (variant reader f, g), §13 (`_changes`, `drift.py`, `discriminate.py`/`synthetic_agent.py`, `profiles.py` rows).

## Owned paths
`grade/_changes.py` (E2 functions), `grade/drift.py` (one hunk), `grade/rework.py` (new), `grade/runner.py` (E2 hub owner; only a hunk W1-J or W1-L names), the `STRATEGIES["rework"]` line in `grade/property.py` (W1-L §3), `profiles.py` (E2), `discriminate.py` and `synthetic_agent.py` (E2, rev 6.6), the `variants.py` reader function (rev 6.6, that function only), `tests/test_changes.py`, `tests/test_rework.py` (new), the two-turn case in the profile qualification suite.

## J2a: the counting rules (first E2 commit, SR-L4, SR-L6)
- `product_lines(path)`, `in_radius(path, radius)` (moved from `drift._in_radius`; `drift.py:131` calls `_changes.in_radius`, the `simplify:` marker moves; `tests/test_grade_drift.py` green unedited), `line_delta(old, new)`, and **`is_test_path(path, base_paths)`** exactly as W0 rev 6.6 §13 states.
- **R2-2:** a fixture asserts `humanfriendly/tests.py` is a test path. **R2-3:** a new `tinydb/tests/_first.py` is a product path while a file the base tree already has under `tinydb/tests/` is a test path. Mutant: "exempt any `test` directory part" must be killed.

## J2b: rework and multi-turn discrimination (W1-J rev 2 merged)
- **W1-J rev 2's names (final; read them, never re-spell them):** the snapshot folder comes only from `archive.snapshot_folder(run_dir, cell_id, turn)` (`<run_dir>/archive/<cell_id>/turn-<n>/`), and the graded copy for `graded_snapshots: [turn-1]` is `<snapshot folder>/ws`; whether an `archive_files` row is final comes only from `archive.snapshot_of(row)` (never `r.get("snapshot") is None`); `grade/runner.py` reads `archive.snapshot_folder` and changes nothing else for this (W1-J §7 row 11). "Turn k not reached" is derived by counting `cell.turn_ended` events against `len(plan.tasks.<id>.turns) + 1`, with the reason from `turn_ended.next` and the outcome cause (W1-J §4.2; derive, don't store). A snapshot is used only when its `cell.turn_snapshot_archived{n}` event exists.
- `rework.grade` (W1-L §6.1): `rework_ratio` on the turn-1 snapshot and the final tree, `turn1_tests_pass`.
- **R2-4 (W0 rev 6.6 §13):** synthetic cells apply per-turn overlays `oracle/solutions/<role>/turn-<n>/`; the turn-1 snapshot comes through X-J1's engine; `bench discriminate` admits a `turns` task (W1-E line 181's HB-RDY-005 `not built in E1` is lifted). Test: a two-turn fixture task gets a discrimination record whose values match its `expected`.
- **Variant reader (W0 rev 6.6 §2 g):** the create form `{"file", "old": "", "new"}` (refused when `file` is in the reference overlay) and the `turn-<n>/` prefix for a `turns` task: one test and one refused case each.

## Acceptance items
1. The campaign plan's exit evidence for X-J2; every function defined once (DM7).
2. The Wave 1 testability floor; mutants per adjacent rule pair.

## Exit
E1 README §3 join gate per dispatch; served model from Agy's `cli.log`. Report per E1 README §4.
