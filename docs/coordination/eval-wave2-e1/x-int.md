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
summary: "X-INT proves the joined E1 tracks end to end through the real CLI, test-only: the campaign walk with real gates, power and readiness, the S1 discrimination run and the T-E19 reader refusals, a two-arm report, the lock and hook partners of C2a and C3b, on Sonnet from the integration head (R-105 re-cut, Coordinator #28)."
---

# X-INT: the E1 end-to-end (R-105 re-cut, Coordinator #28)

This brief was re-cut by Coordinator #28 on `coord/eval-c27-xc3b` at `bc1d075a` (= `integrate/b6-stage` `1c615832` with X-C3a joined, plus the C3b brief). It replaces the earlier text in full; git holds the old one. Where it differs from README §1-§4, this brief wins.

## R-105 header
- **Seat:** Claude Code Sonnet sub-agent, `model: sonnet`, served `claude-sonnet-5-5` expected. The served id is the first line of your report. X-INT was always planned as Claude Code Sonnet, so R-105 changes only its base, not its harness. Record: "planned Claude Code · Sonnet; ran Sonnet (`model: sonnet`, served `claude-sonnet-5-5`); base under R-105 (integration head)".
- **Session** `x-int-e1e4` · **branch** `build/eval-x-int` · no contract file.
- **Base:** the integration head at the moment of dispatch (`integrate/b6-stage` or its successor on the integration line), never `main`. It must carry X-C3b's merge and this brief. From the primary: `python docs/ai-forward-pack/scripts/coord-core.py worktree new --branch build/eval-x-int --session x-int-e1e4 --base <integration head>`. Use absolute paths into the printed tree. Never `EnterWorktree`; never checkout or switch in the primary. Record the base SHA.
- **Preconditions, each on its own line; stop and report if one of the first four fails:**
  1. `git merge-base --is-ancestor 96b83c86 HEAD` (X-C3a's merge)
  2. `git log --oneline -1 --merges --grep "X-C3b"` prints a merge commit (X-C3b joined)
  3. `grep -n "Coordinator #28" docs/coordination/eval-wave2-e1/x-int.md` (this brief is on your base)
  4. `grep -n "Ruling 106" docs/notes/rulings.md`
  5. Record, do not stop: `grep -n "def verify_for_plan" src/harness_bench/campaign.py`, `grep -n "any_kind" src/harness_bench/views.py src/harness_bench/status.py`, `grep -n "def decimal_view" src/harness_bench/campaign.py`, `grep -n "campaign_obj=" src/harness_bench/cli.py`. These are C3b's names. They were **not landed** when this brief was cut, so every item that uses one says "read on your base". If a name is absent (C3b handed a remainder to a C3c turn), the items that need it are reported as "blocked: C3c" with the missing name. They are never built here.

## Owned paths
- `tests/test_e1_e2e.py` (new): every offline test of this brief (the default ring).
- `tests/e2e/test_e1_walking_skeleton.py` (new): the credentials-marked real-cell variant of item 3 **only**.
- Nothing else. Not `tests/e2e/conftest.py`.
- **Why the offline tests are not under `tests/e2e/`** (read on `bc1d075a`): `tests/test_default_suite_is_offline.py:21-24` asserts that a bare collect of `tests/e2e` selects nothing. Also, `tests/e2e/conftest.py:10-16` is a session-scoped autouse fixture that runs `tools.install` (`npm ci`, timeout 900 s) when `.tools/harness` is absent, as it is in a fresh worktree. An unmarked test there turns SUITE-A red and installs the harness builds.
- **X-INT is test-only.** It never edits `src/`. A needed `src/` change is a finding for a C3c or follow-on turn: write the test, record its red SHA and failing assertion, and report the owner. Never an edit.
- **Test helpers:** you may import `cli_rc`, `make_repo` and `real_run` from `tests/test_cli_campaign.py`, and `FakeLauncher` from `tests/test_engine.py`. In items 1 and 13 **never** use the raw-row helpers `put`, `append` or `walk_to` (`tests/test_cli_campaign.py:83`, `:122`, `:134`). Every campaign row in those items is written by a real `bench campaign` command.

## S1 and the discrimination record
- S1 is `draft` on the base (`tasks/S1/task.yaml:5`). F4 (keep or drop for the ten payloads) is open (README §8, #19 and #23). **X-INT must not flip S1** in the tree. It must not commit a discrimination record, and it must not edit `tasks/S1/**`.
- The Leader's J2 measurement is on `leader/s1-discrimination` at `5f54cf0b` (based on `e6a7160a`, not for merge). It holds one file, `bench/discrimination/S1/cafd00925c15b59a-a29e75cbd70b4a44-win32.json`. The commit message gives: 59.3 s; outcome written; `readiness_failures []`; 15/15 variants flip their declared probe with their declared clause; naive 0.3750 / reference 1.0000.
- S1's task version on `bc1d075a` is `cafd00925c15b59ac2d386009cbd72a6d94bb8d7b1a98405440075d7b3c5d990` (measured, `plan.task_version_hash`). It matches the record's name prefix.
- Items 2 and 5 run the **real** `bench discriminate S1` in the test's temp repo. Setting `status: ready` happens only in the temp repo's copy. Cross-check the temp run against the J2 numbers above (outcome `written`, 15/15 flips, naive 0.3750, reference 1.0000), and read the J2 record with `git show 5f54cf0b:<path>` if you need its bytes. *assume:* the identity hash in the record's name (`a29e75cbd70b4a44`) equals the temp repo's identity hash at your base. *Confirm:* compare the name of the record your run writes. *If false:* compare outcome and counts only, and report the hash difference as a fact (the identity moved between `e6a7160a` and your base).

## Acceptance items (each a test in `tests/test_e1_e2e.py` unless marked; each asserts the rendered output or the ledger state, never an exit code alone)
1. **Campaign walk through the real CLI** (`test_e1_campaign_happy_path`). Drives `cli.main` with each of `bench campaign create <id> --question Q` → `baseline` → `power` (prior) → `bench plan --campaign <id>` (the pilot ring, arms `off` and `candidate`, one combo, R-89) → `bench run` → `pilot attach` → `pilot pass` → `admit` → `power` (final) → `register --prereg FILE` (preview), then `--confirm <hash12>` → `bench plan --campaign <id>` (grid) → `attach` → `bench run` → `campaign verify` → `bench report`. *Observable:* after each step, the campaign state from `bench campaign status` (and `--json` if it is on your base, read on your base) is the expected state. A skipped or reordered step (for example `admit` before `pilot pass`) is refused with its HB code, and the refusal text is read. `campaign verify` prints ok and exits 0, and the report's HTML holds section 3 (item 4). Faked: only what `real_run` fakes (launcher, workspace builder, preflight), and **grading is real**. `plan --campaign` and the `bench report` binding are C3b's: read them on your base. Command shapes: `docs/design/eval-campaign-record.md`, commands table, and the 13-row `cli.CAMPAIGN_COMMANDS` (`cli.py:131`). The old subcommand-name `assume:` is confirmed by that table.
2. **UF-E1 front half** (`test_uf_e1_front_half`). In the temp repo: S1 `draft` → set `status: ready` → `readiness.problems(root)` names S1's missing record with an HB-RDY item → `bench discriminate S1` writes the record (stdout `discriminate S1: written <path>`) → `readiness.problems(root)` has no S1 item. *The `bench validate` legs cannot pass tonight:* T-E9 (a) is held for the operator, and `cmd_validate` (`cli.py:174-179`) prints only `config.validate_repo`. So the CLI leg (the rendered `x HB-RDY-… S1: …` line) is a separate test, `test_uf_e1_validate_names_the_missing_record`, marked `pytest.mark.xfail(strict=True, reason="T-E9 (a) held for the operator: readiness.problems not in cmd_validate")`. Record its failing assertion. A strict xfail turns red when the line lands, and the marker is then removed.
3. **The E1 demo combo (R-89)** (`test_e1_demo_combo_offline`). `cc-opus` (claude-code, `claude-opus-5-5`), k = 3; 1 task (S1) × 1 combo × 3 reps × 2 arms = 6 cells. *Observable:* the registered minimum recorded pairs per verdict is ≤ 3 (R-89 c1); the rendered verdict reads `inconclusive (underpowered)`; the power input names grid-4 as its source run (R-89 c2). The offline variant runs `FakeLauncher` behind the launcher seam with the same plan shape. The real-cell variant, `tests/e2e/test_e1_walking_skeleton.py::test_e1_demo_combo_real`, carries `pytest.mark.credentials` and runs only under the Leader. *assume:* the offline variant reaches `inconclusive (underpowered)` because the verdict reads recorded `property_check_pass` pairs, not the model's identity. *Confirm:* run it. *If false:* the verdict leg runs only under the Leader's credentials, and the offline test covers the pairs and the minimum only.
4. **Report section 3 (EV-20)** (`test_section_3_renders_from_the_cli`). `bench report` of item 1's grid run. *Observable:* one verdict with the EV-20 header, the catalog line `0.7.dev` and the word "exploratory"; the registered `mde` and `min_pairs`; drilling from the verdict reaches the cell rows. A non-campaign run's report is unchanged (EVU-4; the golden in `tests/test_report_builder.py`). This uses C3b's `campaign_obj=` binding: read it on your base.
5. **T-E19 with a real discrimination run** (`test_a_discrimination_run_is_refused_or_labelled_by_each_reader`, one parameter per reader). It uses the run folder that item 2's real `bench discriminate S1` wrote. *Observable:*
   - refused with HB-CMP-010: `bench campaign attach`, `bench campaign pilot attach`, `campaign.run_side_check`;
   - refused with HB-PLN-004 naming the kind: `bench run`, `bench report`, the board's run listing;
   - `bench status`: prints `kind: discrimination` as its first line, exits 0, and does not refuse. This uses C3b's `views.load(..., any_kind=True)` from `status.build` (#27's grant). Read it on your base.
   - This confirms or refutes C3b's `assume:` ("a discrimination view builds once the refusal is skipped") on a **real** run. C3b used a hand-written plan. If it is refuted, the test records the failure, and the full status of a discrimination run is a finding for C3c. It is never fixed here.
   - Record each parameter's failing assertion (skip the check in one reader: its parameter is red).
6. **T-E19 sweep (RV-TA R2-4).** Run `git grep -n "plan.json\|load_confirmed" -- src` on your base and put the output in the report. Every module it names must be in `tests/test_discriminate.py`'s set, which is `{"cli.py", "grade/runner.py", "status.py", "views.py", "readiness.py", "campaign.py"}` on `bc1d075a` (`:558`). `cmd_status`'s `load_confirmed` is inside `cli.py`. Item 6 is a check plus a report line, with no new test, unless the set is short on your base. If it is short, that is a finding (the X-E file is not yours).
7. **Two-arm report renders (W0 §10 G1 note)** (`test_two_arm_plan_renders_every_legacy_reader`). A plan with arms `off` and `candidate` renders the full legacy report, the board and `report/pack_improvement` without raising. This confirms or refutes the plan's *assume:* "the legacy readers render a non-`on` arm id". If it is refuted, report a finding: X-A3's reader migration moves into E1. Also assert SR-3's text: for a two-arm run the board does not print "This run has one pack setting; no effect to show.", and the header shows the pack revision.
8. **Arm guard.** `tests/test_arms_guard.py` is green with its pinned counts. Add one grep assertion that `campaign.py`, `report/campaign_section.py` and `verdicts.py` read the arm only through `cell_arm` / `arm_pack`.
9. **Synthetic exclusion** (`test_measurement_plan_naming_synthetic_is_refused`). A `measurement` plan naming a `synthetic` combo is refused by the real `plan.build_plan` with HB-PLN-004 naming the combo (`plan.py:487-489`). `synthetic` is in no leaderboard row.
10. **Cross-surface consistency (E7)** (`test_one_run_four_surfaces_agree`). Item 1's grid run read through `bench status --json`, the ledger, `campaign verify` and section 3. *Observable:* the same cell counts, the same task version hash and the same identity hash on all four.
    - **The completion-summary leg owed by X-H2 item 9** (EV-18; spec `enterprise-evaluation.md:382`) is the separate test `test_one_blocked_cell_is_named_in_the_completion_summary`. One blocked cell must be named, with its id and cause, in the completion summary that `bench run` prints. That summary is `status.text(status.build(run_dir))` (`cli.py:284`).
    - On `bc1d075a`, `status.text` prints only the counts lines `Outcomes`, `Validity` and `Causes` (`status.py:185-213`, `text` ends before `to_json` at `:216`), with no cell id. So this leg needs `src/` code. Mark the test `xfail(strict=True, reason="EV-18 completion-summary leg: no cell id in status.text; C3c")` and report it as a finding for C3c. *If* your base already prints the id, drop the marker.
11. **Rings.** The credentials-marked test is skipped without `HB_CLAUDE_OAUTH_TOKEN` and is counted in the report. `tests/test_default_suite_is_offline.py` and `tests/test_no_leftovers.py` stay green with your files present.
12. **T-E9 (X-C's lines; joins here).**
    - Legs (a) and (b) are `cli.main(["validate"])` for S1 marked `ready` with no record (fails), and with a campaign baseline (passes the baseline through). **They cannot pass tonight:** the line is held for the operator, because it would turn CI's `bench validate` red on 8 HB-RDY-005 items (README §8, #26 and #27). Write both legs as `xfail(strict=True, reason="T-E9 held for the operator")`, and record each failing assertion.
    - Leg (c): `cli.main(["discriminate", "S1", ...])` dispatches. It is live: C3a's `tests/test_cli_discriminate.py` covers it with a fake `run`, and item 2 covers it for real. Cite both in the report. Do not add a third test.
13. **W1-C cross-track joins (X-INT-1..3; X-C is not done until these pass).** These are the real partners of the stubbed unit tests.
    - **X-INT-1** `test_full_walk_with_real_gates_power_and_readiness`: item 1's walk from create to attach, with **none** of the names that `tests/test_campaign_register.py:63-80` (`stubs`) patches: `gates.pilot` (C-23), `gates.admission` (C-26), the three readiness readers `hidden_test_disagreements`, `unbiased_failures` and `expected_na` (C-48), and `views.load`. It also covers `power.analyse` (C-17) over the final inputs. *Correction to #27, read on `bc1d075a`:* C-17's test (`tests/test_campaign.py:729`) already calls the real `power.analyse` through `bench campaign power` (`campaign.py:1081`), and no test patches it (grep). So X-INT-1's C-17 leg is the final-power analyse after a real pilot pass, not the replacement of a stub. *Observable:* the `pilot.passed` and `admission.decided` rows hold the real gate outputs. The test module patches none of the six names: assert it with a grep over its own source.
    - **X-INT-2** `test_run_pass_of_a_campaign_run_is_refused_while_campaign_lock_is_held`: X-F's HB-GRD-007 through the real runner, in both orders of the helper (`grade.lock` then the campaign-lock probe, and the probe while `campaign.lock` is held first). It is the real-runner partner of C2a's `tests/test_campaign_locks.py:383`, which hand-writes the campaign block. Here the plan comes from `bench plan --campaign`. *Observable:* HB-GRD-007, and no `grade-*.jsonl` written.
    - **X-INT-3** `test_after_grading_hook_is_lock_free_and_verifies_with_two_attached_runs_one_graded`: with a sibling attached run's `grade.lock` held, the hook prints `campaign verify: ok (<n> rows)`; an unknown campaign prints `campaign verify: not run (HB-CMP-005)`. It is the real-runner partner of C3b item 5. The hook and `verify_for_plan` are C3b's: read them on your base.
14. **C3b's test-only remainder, if any.** If C3b's report or merge message on your base says that its item 9 (L-10, C-45, C-46, the missing C-47 rows) was not reached, those tests are yours, in `tests/test_e1_e2e.py`, with the ids and definitions of the C3b section of `x-c.md`. If C3b finished item 9, this item is empty: say so.

## Method
- Write every test red first: assert a deliberately wrong neutral value, run it, record the failing assertion line, then correct the expected value and commit green. The code is landed, so the red is in the expectation, never in `src/`.
- Commit a skeleton first (the two test files with final names, each test body `pytest.fail("skeleton")` or a wrong expectation), and run the guard files on it.
- The `xfail(strict=True)` tests (items 2, 10 and 12) are findings with an executable record, not muted tests. Each reason names the hold or the owner.

## Gate (R-104; each command on its own line, exit status read, never behind a pipe; no `--touched`)
1. `uv run pytest -q tests/test_architecture.py tests/test_identity.py tests/test_atomic_sites.py tests/test_arms_guard.py tests/test_discriminate.py tests/test_mutate_check.py` (the guard files, on the skeleton commit and on the final commit)
2. `uv run pytest -q tests/test_e1_e2e.py tests/test_default_suite_is_offline.py tests/test_no_leftovers.py` (your own file, plus the two ring guards that your new files can break)
3. `uv run pytest -q -m browser tests/test_report_browser.py` (once)
4. `uv run ruff check src tests tools`
5. `python docs/ai-forward-pack/scripts/docs-graph.py validate`

No `mutate_check`: X-INT adds no `src/` line and no mutation ledger. The whole suite and the credentials ring are the Leader's at the join (R-104).

## Not in scope
- Any `src/` edit (a finding for C3c or a follow-on).
- The `bench validate` / T-E9 (a, b) line (held for the operator).
- Flipping S1, editing `tasks/S1/**`, or committing a discrimination record (F4 is open).
- `tests/e2e/conftest.py`, X-E's `tests/test_discriminate.py`, and any other owner's test file.
- The E1 demo with the operator (UF-E1, B-3): the Leader's.
- Merging or pushing.

## Budget and fit
180 calls, context under 400k, one Sonnet session of at most 2 h. *Basis (measured):* C3a went from its compile commit to its green commit in 39 minutes for about 22 ids (README §8, #27). X-INT has about 20 tests, but heavier fixtures. Each real `bench discriminate S1` takes about 59 s (J2), so build the discrimination run once per module in a module-scoped fixture, and items 2 and 5 share it. *Inferred:* items 1-13 fit in 2 h. **The cut line, if the budget runs short, from the end:** item 14 (C3b's remainder) moves to a later Sonnet turn, X-INT-b, compiled at X-INT's join; then item 7. Items 1, 2, 5 and 13 are never cut. At 85 % of the budget: commit, stop, and report what remains by test id.

## Report (README §4, plus)
- the base SHA and the five precondition results (with the C3b-name greps);
- the red SHA, node and failing assertion of every test, including each strict xfail;
- the item 2 and item 5 cross-check against J2 (outcome, flips, naive and reference values, record name);
- the T-E19 parameter list and the item 6 `git grep` output;
- the item 7 finding (confirmed or refuted);
- the offline versus credentialed split (item 11);
- each finding for C3c or a follow-on, with its red evidence (items 2, 10 and 12, and any refuted `assume:`);
- every `assume:` you wrote and whether you confirmed it;
- what moved past the cut line.

On a green join, tell the Leader "E1 demo ready (T-E9 held)".
