---
id: brief-eval-x-a1
title: "Brief X-A1: arms in the plan, ring plumbing, the pack-reader guard (E1 build)"
type: plan
status: proposed
owner: "@timianmalloo"
links:
  - { to: coordination-eval-wave2-e1-briefs, rel: implements }
  - { to: design-eval-arms, rel: depends-on }
  - { to: design-eval-seam-contracts, rel: depends-on }
review-by: "2026-10-17"
summary: "X-A1 builds bench-matrix/2 and bench-plan/2, the accessors, launch order, ready rule, role binding, the G1 guard and the reader migrations of W1-A rev 2 on Codex gpt-6.1-sol, in two dispatches, each red and green in one turn."
---

# X-A1: arms and ring plumbing

**Harness** Codex via `coord-runner` (Leader, R-87), `gpt-6.1-sol`, effort high, codex-cli 0.160.0 (R-88 condition 1, README §5) · **contract** `x-a1.contract.json` (A1a; A1b reuses it with the suffix `b`) · **deadline** 3,300 s per dispatch · **budget** 220 calls · 200k · 2 dispatches · 3 h · **fallback** a red-only end: the green follow-on runs as Claude Sonnet (`model: sonnet`, served `claude-sonnet-5-5`) in the same tree (R-88 is the Owner review).

**Design:** `docs/design/eval-arms.md` (W1-A rev 2, on `main`, `92e977b2`). **W0 rev 5:** §2 (`CHECK_PROPERTIES`), §6 (the synthetic hunk), §11 (HB-PLN-004 text). **W0 rev 4:** sections 1, 5 (quoted ids incl. `comparisons`, no top-level `pack`, `plan_pack(plan, *, strict=False)`), 7 (`PROPERTY_NAMES`, the two `validate_catalog` checks, R-95 condition 2), 10 G1 (AST tokens, equality ratchet, pins after the migrations), 11, 13.

## Owned paths (E1 hub owner, W0 §13)
`src/harness_bench/plan.py`, `config.py`, `views.py`, `grade/_changes.py` (line 84 only), `cli.py` (the function `_workspace_builder` only), `board.py` and `report/summaries.py` (the one-line `plan_pack` migrations and `board._build_pack_effect`'s status text only), `report/pack_improvement.py` (the `cell_arm` line at 746-747 only), `bench/rings/pilot.yaml` (new; R-89: `cc-opus`, `model: claude-opus-5-5` explicit, k = 3), `tests/test_plan.py`, `test_config.py`, `test_workspace.py`, `test_views.py`, `test_changes_cache.py` (the `pre_turn_commit` case), `tests/test_arms_guard.py` (new), `tests/fixtures/plans/grid4-cells.json` (new), `tests/mutations/plan.json`. **Not yours:** `workspace.py` source (X-B1's `_land` hunk), `cli.py` `cmd_plan` (X-C pastes W1-A §3.9), `report/html.py` (X-H2 takes your header lines).

## Depends on
W1-A ✓; **X-D1** joined (HB-PLN-001/002/004/005 in the registry).

## Dispatches
- **A1a** (`x-a1a-e1e4`, `build/eval-x-a1a`): `config.py` (bench-matrix/2 validation, quoted-id refusal in `arms` and `comparisons`, upcast, `ARM_OFF`, `ARM_ID`, ring validation, `PROPERTY_NAMES`, the `property:` tag check, the `also_graded_by` check: a grader module, differs from `grader`, no repeats); `plan.py` (bench-plan/2 writer, `Cell.arm`, label, `arms`, `comparisons`, `launch_seed`, `kind`, `campaign` verbatim, `ring`, `cell_arm`, `arm_pack`, `plan_pack`, `launch_order`, `launch_balance`, `draw_launch_order`, the ready rule by plan kind, `parse_binding`, `resolve_arms`); the grid-4 golden. **W0 rev 5 (SR-E1 2, SR-L3):** `"synthetic"` joins `config.HARNESSES`; `config.CHECK_PROPERTIES = frozenset({"security", "resilience"})` beside `PROPERTY_NAMES`; `plan.SYNTHETIC_PROFILE_RECORD` (a constant dict) returned by `plan.profile_record(root, "synthetic")`; `build_plan` refuses a **measurement** plan that names a `synthetic` combo with HB-PLN-004 (one refusal by plan kind, listing every offender). Run the full suite: any test that pins `config.HARNESSES` is yours to update in the same commit.
- **A1b** (`x-a1b-e1e4`): `views.py:525`, `grade/_changes.py:84`, `cli._workspace_builder`, the three plan-level readers and `pack_improvement.py:746-747`, `board._build_pack_effect` text, `bench/rings/pilot.yaml`, G1 with its fixtures and the pinned counts taken **after** these migrations.

## Acceptance items (W1-A rev 2's test plan §10 plus the live gate conditions it states as applied; check each against the merged text)
1. EV-17: `test_grid4_replan_gives_the_same_task_combo_arm_rep_set_and_cell_ids` runs `build_plan` over the fixture matrix with injected versions (RV-TA 6), and the fixture carries its provenance (`runs/grid-4/plan.json` and its sha256, no generator; RV-TA 7).
2. Launch balance: refused at exactly 1/20 deviation, with a `<` → `<=` mutant (RV-TA 5); the 2×4 and 3×4 shapes in the redraw test; the cap refusal text does not claim "at least 2 blocks" for more than two arms (RV-PAT 3, 4).
3. G1: one red fixture per form (`x["pack"]`, `.get`, `.pop`, `in`, `getattr`, `itemgetter`, attribute, keyword), a comment-only and a docstring-only file that must not match; `test_pack_hits_equal_the_pinned_counts` asserts equality (RV-PAT W0 delta 3); RV-TA 1's `Constant("on"/"off")` scan with its red fixture and the `report/assets/*.js` text scan.
4. **`test_plan_py_imports_no_campaign_or_identity_module` stays, with a red fixture** (W0 rev 4 ruling on RV-TA 3 vs RV-SIM 7: G2b cannot catch `identity`, which is run class).
5. RV-TA 2: one test through the real `cli._workspace_builder` with two real pack repos, asserting each arm's diff equals its manifest.
6. RV-TA 8: the red commit lands stubs that raise or return neutral wrong values for `launch_order`, `cell_arm`, `draw_launch_order`, so tests fail on behaviour.
7. `test_plan_level_readers_state_the_true_pack_or_refuse`: `board` raises HB-PLN-005 with `strict=True`; the display readers render `several packs`.
8. HB-PLN-004 names every offender (no cap; RV-SIM 4); a discrimination plan admits `draft` and refuses `stub`; a measurement plan with a `synthetic` combo is refused and names the combo (W0 rev 5), with a red fixture and the mutant "skip the harness check"; `profile_record(root, "synthetic")` returns the constant (today it raises `ValueError`, `profiles.py:176`).
9. RV-PAT 6 (for X-E, recorded here so it is not lost): `status: ready` has one predicate; you do not write `ready` anywhere.

## Exit
README §3 join gate per dispatch; served model read from the Codex native record. Report per README §4.
