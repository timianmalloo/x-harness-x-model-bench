---
id: brief-eval-x-int
title: "Brief X-INT: the E1 end-to-end walking skeleton (E1 build)"
type: plan
status: proposed
owner: "@timianmalloo"
links:
  - { to: coordination-eval-wave2-e1-briefs, rel: implements }
  - { to: coordination-eval-campaign, rel: depends-on }
  - { to: design-eval-seam-contracts, rel: depends-on }
review-by: "2026-10-17"
summary: "X-INT proves the joined E1 tracks end to end through the real CLI: the campaign happy path, the T-E19 reader refusals, a two-arm report, and the arm-reader assume, on Sonnet, with the real cells credential-marked."
---

# X-INT: the E1 end-to-end

**Session** `x-int-e1e4` · **branch** `build/eval-x-int` · **harness** Claude Code Agent tool, `model: sonnet` (served `claude-sonnet-5-5`, R-91), spawned with cwd = the tree path; no contract file · **budget** 100 calls · 150k context · 1 session · 1.5 h · **fallback** a fresh Sonnet session from this brief.

**Status: blocked until every E1 item has joined `main`** (README §6: "X-INT: every E1 item"). Start from `main` after the last join and run README §1 step 5 for the whole list below.

**Design and plan:** `docs/coordination/coordination-eval-campaign.md` (E1 phasing row, Done-when 1, DR-3), `docs/architecture-evaluation-campaign.md` (E1 row, line 315), R-89, W0 rev 6 §6 (SR-E3), §10 (G1 note), `docs/design/eval-discriminate.md` §5.4 and T-E19.

## Owned paths (W0 §13)
`tests/e2e/test_e1_walking_skeleton.py` (new), `tests/e2e/conftest.py` (E1 hunk). Nothing else. A `src/` defect you find is a **loop-back**: report it with a red SHA; the owning hub-file owner fixes it (plan: six loop-back slots). Never edit `src/` here.

## Depends on (joined on `main`; the README DAG, every E1 item)
TOOL-GSM, ENV-A, X-G1, X-F (F0..F3), X-D1, X-D2, X-B1a, X-B1b, X-B1c, X-B2, X-A1a, X-A1b, X-I (authoring and the real-grader follow-on), X-H1, X-C, X-E, X-H2, TIME-B. If one is missing, stop and report which.

## Method
Tests are pytest and drive the **real CLI** (`cli.main([...])`) in a temp repo built from the joined tree, with S1 and the real grader and probe host. The synthetic (discrimination) cells and the grading pass run offline. The real-cell steps (`cc-opus`) carry the credentials marker (SUITE-A; `tests/test_default_suite_is_offline.py` stays green) and run only under the Leader. Each step asserts the **rendered surface** or the ledger state, not an exit code alone. Write every test red first against a deliberately wrong neutral value, and record the failing assertion.

## Acceptance items (each testable; from the plan's E1 done-when and phasing row)
1. **Campaign happy path through the real CLI** (`test_e1_campaign_happy_path`): `bench campaign create <id> --question Q` (draft) → `baseline` (identity manifest) → `power` (prior) → `pilot attach <id> <run>` → `pilot pass` (the pilot ring's two arms `off` and `candidate` on one combo, R-89) → `admit` → `power` (final) → `register --prereg FILE` preview, then `--confirm <hash12>` → `attach` (grid) → `bench run` → grade → `campaign verify` exits 0 → report section 3 renders (command shapes: `docs/design/eval-campaign-record.md`, commands table). Each step asserts the campaign state it leaves, and a skipped or reordered step is refused with its code.
2. **UF-E1 front half:** S1 `draft` → `status: ready` set → `bench validate` fails with an HB-RDY item naming the missing record → `bench discriminate S1` writes the record → `bench validate` is clean → the record is committed with the task (W0 §2 order). The failing readiness item is read from the rendered `validate` output (`x HB-RDY-001 S1: ...`).
3. **The E1 demo combo (R-89):** `cc-opus` (claude-code, `claude-opus-5-5`), k = 3, 1 task (S1) × 1 combo × 3 reps × 2 arms = 6 cells; the registered **minimum recorded pairs per verdict is 3 or fewer** (R-89 condition 1; a minimum above 3 turns the expected verdict into `inconclusive (not recorded)`). The test asserts the registered minimum is <= 3 and the verdict reads `inconclusive (underpowered)`; the power input names grid-4 as its source run (R-89 condition 2). The real-cell variant is credential-marked; the offline variant uses the joined fake agent with the same plan shape.
4. **Report section 3 (EV-20):** one verdict renders with the EV-20 header, the catalog line `0.7.dev` and the word "exploratory" (not frozen); drilling from the verdict reaches the cell rows. A non-campaign run's report golden is unchanged (EVU-4).
5. **T-E19 (W1-E, SR-E3 1; joins here):** `test_a_discrimination_run_is_refused_or_labelled_by_each_reader`. A real discrimination run folder (from item 2) is refused with HB-CMP-010 by `attach`, `pilot attach` and `campaign.run_side_check`, and with HB-PLN-004 naming the kind by `bench run`, `bench report` and the board's run listing; `bench status` labels it `kind: discrimination` and does not refuse. One parameter per reader; the failing assertion of each is recorded (skip the check in one reader: its param is red).
6. **T-E19 sweep (RV-TA R2-4):** every `src/harness_bench` module that calls `load_confirmed` or reads `plan.json` appears in T-E19's reader table (allowlist plus count). `campaign.py` is now on the base, so this covers `run_side_check`. A new reader fails the test. Re-run `git grep "plan.json\|load_confirmed" -- src` and put the result in the report.
7. **Two-arm report renders (W0 §10 G1 note):** a plan with arms `off` and `candidate` renders the full legacy report, the board and `report/pack_improvement` without raising. This confirms or refutes the plan's *assume:* "the legacy readers render a non-`on` arm id without raising". If refuted, report it as a finding: X-A3's reader migration moves into E1 (plan row). Also assert the text fixed in SR-3: the board's pack-effect section no longer prints "This run has one pack setting; no effect to show." for a two-arm run, and the header shows the pack revision.
8. **Arm guard:** `tests/test_arms_guard.py` (G1) is green with its pinned counts; X-C, X-E, X-H2 read the arm only through `cell_arm` / `arm_pack` (a grep assertion over those modules).
9. **Synthetic exclusion:** a `measurement` plan naming a `synthetic` combo is refused with HB-PLN-004 naming the combo (T-E23, real `plan.build_plan`); `synthetic` is in no leaderboard row.
10. **Cross-surface consistency (E7):** the same S1 run, read through `status --json`, the ledger, `campaign verify` and section 3, gives the same cell counts, the same task version hash and the same identity hash. One test compares the four.
11. **Rings:** the credentials-marked tests are skipped without `HB_CLAUDE_OAUTH_TOKEN` and counted in the report; the default suite stays offline (SUITE-A) and leaves no leftovers (`tests/test_no_leftovers.py`).
12. **T-E9 (X-C's lines, owned by X-C, joins here):** `cli.main(["validate"])` for S1 marked `ready` with no record fails; with a campaign baseline it passes the baseline through; `cli.main(["discriminate", "S1", ...])` dispatches. Record the failing assertion of each part from X-C's red commits or add the join test if X-C left none.
13. **W1-C cross-track joins (design section "Cross-track joins", owner X-INT; X-C is not done until these pass):** `test_full_walk_with_real_gates_power_and_readiness` (create to attach with the real `gates.pilot`, `gates.admission`, `power.analyse` and `readiness.*`: item 1 with no fakes for those four); `test_run_pass_of_a_campaign_run_is_refused_while_campaign_lock_is_held` (X-F's HB-GRD-007 through the real runner, both orders of the helper); `test_after_grading_hook_is_lock_free_and_verifies_with_two_attached_runs_one_graded` (the hook prints `campaign verify: ok` with a sibling attached run's `grade.lock` held; HB-CMP-005 prints `not run`).

`assume:` (written by this brief, each to be confirmed at the build)
- `assume:` the subcommand names are those of W1-C rev 2 (`create`, `baseline`, `fix`, `power`, `pilot attach`, `pilot pass`, `admit`, `register`, `attach`, `conclude`, `abandon`, `verify`, `status`; read in the design, not yet in code). Confirm: `bench campaign --help` on the joined tree. Breaks if false: item 1 uses the real names, and the report lists the rename.
- `assume:` the offline variant of item 3 can use a fake agent behind `Launcher` for the six cells and still reach `inconclusive (underpowered)`, because the verdict reads recorded `property_check_pass` pairs, not model identity. Confirm: run it. Breaks if false: item 3 runs only under the Leader's credentials, and the offline test covers pairs and the minimum only.
- `assume:` S1 is `ready` with a committed record when X-INT starts (J2 done by the Leader). Confirm: `python -m harness_bench validate` shows no S1 item. Breaks if false: item 2 builds the record in the test's temp repo and says so.

## Exit
README §3 join gate on the final commit, then report per README §4 (add: the T-E19 reader list with the sweep count, the item 7 finding, loop-backs with red SHAs, and the offline versus credentialed split). On a green join, tell the Leader "E1 demo ready"; the demo itself (UF-E1 with the operator, B-3) is the Leader's.
