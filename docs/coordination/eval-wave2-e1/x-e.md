---
id: brief-eval-x-e
title: "Brief X-E: discriminate, synthetic agent and readiness (E1 build)"
type: plan
status: proposed
owner: "@timianmalloo"
links:
  - { to: coordination-eval-wave2-e1-briefs, rel: implements }
  - { to: design-eval-discriminate, rel: depends-on }
  - { to: design-eval-seam-contracts, rel: depends-on }
review-by: "2026-10-17"
summary: "X-E builds discriminate.py, readiness.py and synthetic_agent.py of W1-E rev 2 under W0 rev 6 and R-98, red first, on Sonnet: the skeleton first, then the engine-only tests, then the host tests once X-F's host has joined."
---

# X-E: discriminate, synthetic agent, readiness

**Session** `x-e-e1e4` · **branch** `build/eval-x-e` · **harness** Claude Code Agent tool, `model: sonnet` (served `claude-sonnet-5-5`, R-91), spawned with cwd = the tree path; no contract file · **budget** 240 calls · 200k context per session · up to 3 sessions (a fresh one per group past 150k) · 3.5 h (Inferred from the plan; phase 1 ran 2-14x long) · **fallback** a fresh Sonnet session from this brief (the tree and its commits carry the state).

**Status: unblocked.** The W1-E gate passed (RV-TA and RV-PAT rev 2 re-reviews: PASS WITH CONDITIONS; the conditions are items 1-6 below).

**Design:** `docs/design/eval-discriminate.md` (W1-E rev 2, on `main`). **W0 rev 6 wins over the design** (`docs/design/eval-seam-contracts.md`): sections 2 (variants, overlay), 3 (`check_segment`, case ids), 4 (`sweep_temps` takes a folder), 6 (the record, the link, reconciliation, SR-E3), 7 (the readers), 8, 11, 13, and the "Revision 6 change table" row for X-E. **R-98** in `docs/notes/rulings.md`. Reviews: `docs/design/reviews/eval-review-ta-w1e.md` and `eval-review-pat-w1e.md` (the "Revision 2 re-review" sections).

## Owned paths (W0 §13)
`src/harness_bench/discriminate.py`, `readiness.py`, `synthetic_agent.py` (all new, grade class); `tests/test_discriminate.py`, `tests/test_readiness.py`, `tests/test_synthetic_agent.py` (new); `tests/fixtures/property_tasks/**` (new: `disc_c`, `disc_p`, `disc_rw`, `disc_flaky`, `scan_a`, `scan_a_secondary`, `make_task.py`); `bench/discrimination/**` (records, S1's at the join only). The plan names `tests/fixtures/discrimination/**`; the design places fixtures under `property_tasks/`. Use the design's path.
**Not yours:** `profiles.py` (your hunk is empty: no `bench/profiles/synthetic.yaml`, W0 §6), `config.py`, `plan.py` (X-A1), `errors.py` and `tests/test_architecture.py` (X-D: HB-RDY rows, 011, `CLASSES` seed), `atomic.py`, `oslock.py` (X-B1), `grade/**` (X-F), `cli.py` (X-C: the `discriminate` dispatch and the `cmd_validate` line are X-C's, T-E9 joins at X-INT), `tasks/S1/**` (X-I; S1 stays `draft` until your join, then see item 15). A line in another owner's file is a seam request.

## Depends on (joined on `main`)
- **X-A1b:** `plan.kind`, `plan.SYNTHETIC_PROFILE_RECORD`, `config.CHECK_PROPERTIES`, `plan_packs`. **X-B1b:** `atomic.create_once`, `is_temp_name`, `sweep_temps(folder, lock)`. **X-D2:** `identity.for_task`, `manifest(..., builds=None)`, the HB-RDY-011 row. **X-G1:** the property tags `runner.applicable` narrows on. **X-I:** S1 at `draft` (J2 only).
- **X-F in two steps (W1-E §15 order).** `grade/_env.py` (`grading_env()`) must be on `main` before your skeleton commit, because `SyntheticLauncher.argv_env` imports it. The **host** is needed only for T-E1b, T-E10 (host parts), T-E11, T-E12, T-E13 (host form), T-E15 on a real run.
- **Tests that can start before X-F's host** (real `correctness` grader only): the skeleton; T-E1a; T-E1c; T-E2; T-E3; T-E4; T-E5; T-E6; T-E7; T-E8 (hand-built records); T-E10 engine-only part; T-E14 and T-E15 on hand-built folders; T-E16; T-E17; T-E18; T-E20; T-E21; T-E22; T-E24. **After the host joins:** T-E1b, T-E10 (host part), T-E11, T-E12, T-E13 timeout and HB-CHK params, T-E15 (real graded run). Do the first set, ask the Leader to merge, then rebase and do the second.
- `check_segment` (`grade/property.py`) is X-F's. If X-F has not landed it, add it as one granted hunk with its W0 §3 fixtures and tell the Leader.

## Before the skeleton commit (RV-TA rev 2 conditions R2-1..R2-4; RV-PAT conditions)
Write each into the skeleton or the first red commit. A skeleton commit without them is refused at the join.
1. **R2-1.** A per-case `timeout` outcome that is not in `expected` (or a variant flip whose cause is a `timeout`) is an **HB-RDY-011** item, not HB-RDY-003: nothing is written, so the clean retry never meets HB-RDY-010. Delete the W1-E §4.4 sentence "not transient by construction". Add a timeout param to T-E13: first trial times out, second runs clean and returns `written`.
2. **R2-2.** `probe` is present only when `property.name in config.CHECK_PROPERTIES`. A check-less record with a `probe` key fails HB-RDY-001. W0 rev 6 §6 now says so; T-E1c and T-E8(d) are no longer provisional.
3. **R2-3.** Retiring T-E1a must not delete its allowlist, canary and leak assertions. Move them, by name, into `test_synthetic_environment_and_record_leak_scan` (survives): the agent's keys equal `set(grading_env()) | {"HB_SYNTH_OVERLAY", "TRACEPARENT"}` (RV-PAT 4: `extra` stays empty and the two names are set after the call); `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GH_TOKEN`, `HB_CLAUDE_OAUTH_TOKEN` and the unlisted canary `HB_TEST_UNLISTED_SECRET` are absent; the record and link hold no absolute path, `USERNAME` or `BENCHCANARY-`. Only the end-to-end `exists()` assertion retires with T-E1a.
4. **R2-4.** T-E19 gets a sweep assertion: every `src/` module that calls `load_confirmed` or reads `plan.json` is in T-E19's reader table (allowlist plus count), so a new reader fails the test. `campaign.py` is not on your base, so the scan runs at X-INT on the joined tree (see x-int.md); on your tree it covers the readers present (`cli.py`, `grade/runner.py`, `status.py`, `views.py`, `report/pack_improvement.py`).
5. **RV-PAT 1 (reader seam).** The readers return `list[str]` or raise `BenchError("HB-USR-002", <reason>)`; `discriminate` converts to an HB-RDY-011 item whose detail is the reason. Write that, not "the W0 rule", in the docstrings (W0 rev 6 §7/§8 states it). No bare `None`.
6. **RV-PAT 2, 3, 4.** The link's sort key is wall-clock `recorded_at` alone; `mono_ns` is informational (T-E6: two links, equal `mono_ns`, differing `recorded_at`). `clauses.json` is read through `property.json` `check.clauses` (X-F lands it, SR-E3 2 granted); if it is absent on your base, keep `<dir of Score.evidence>/check/clauses.json` marked `provisional (seam SR-E3 2)` and add one join test that fails when the check evidence dir moves.

7. **W0 rev 6.1 (RV-TA and RV-SEC on rev 6).** (a) R2-1 is now W0 text: the HB-RDY-011 row names an undeclared case `timeout`; one parameter on T-E13 (a timeout trial writes nothing, the clean retry succeeds). (b) `check_segment` caller tests, red when the call is deleted: variant name `nul` and overlay component `con/x.py` through readiness; the overlay-component `rx` is `^[A-Za-z0-9._-]+$`. (c) The sweep of `bench/discrimination/<task>/` has a red test on the **wrong** pairing (another folder's held lock refuses). (d) Read a plan's kind only through `plan.kind_of` (absent = `measurement`). (e) R-98 condition 4 is a join checklist item: at the join the Coordinator reads every comparison of a stored record under `src/`.

## Minors with the build (R2-5..R2-7, RV-PAT 5)
- **R2-5.** The test count is not asserted anywhere. Report the real split: 23 push/readiness tests, T-E9 and T-E19 (other owners, join at X-INT), T-E23 (X-A1's), J1-J3.
- **R2-6.** Name the failing assertion: T-E9(c) is red because the dispatch line is X-C's (not an `argparse` `SystemExit(2)`); T-E13's red is `second.outcome == "written"`.
- **R2-7.** T-E22: the absolute key path is baked into the overlay at fixture build (the deliverable's environment is the allowlist and forwards no test variable); the forged bytes differ from the true record; assert HB-RDY-011 and not HB-LED-007.
- **RV-PAT 5.** One join check runs the T-E3 bad-name set through `grade/_changes` `_copy_tree` and records whether it refuses them (a sentence in the report if it need not).

## Commit groups (each red then green; record every red SHA and failing assertion)
- **E0 skeleton:** the three modules with final signatures and well-formed wrong behaviour (W1-E §14.1), the fixtures, items 1-6 above. No red test is an `ImportError`, `AttributeError` or `NameError`.
- **E1 engine-only:** the synthetic agent and `SyntheticLauncher`, the overlay rule, `discriminate.run` (lock, sweep, record, link), `readiness` record items; the tests of the "before the host" list.
- **E2 host (after X-F's host joins):** the host-driven tests and the variant trial.
- **E3 close:** `problems()`, the `note:` lines, telemetry fields (§11), the J1..J3 checks.

## Acceptance items (each testable)
1. **R-98 condition 1:** `test_no_link_after_hb_rdy_010` (T-E5b): a differing re-run leaves the stored bytes unchanged **and** the failed run folder holds no `discrimination-link.json`; the same after a failed trial and after HB-RDY-011. Mutant: write the link before the compare.
2. **Condition 2:** HB-RDY-010 is raised **before** HB-LED-007; the message names the first differing JSON path (`scores.naive.exploit_probes_blocked`, `probe.reference.cases.inj-3`), the stored and new value; a param where only a `probe` outcome differs (T-E5a).
3. **Condition 3:** reconciliation never degrades to a pass. One `reconciled: yes` or `reconciled: no (<reason>)` line, `<reason>` from the closed set of seven; one parametrized case per reason (T-E6); only a score or `probe` difference fails (HB-RDY-004); a forged `probe` outcome fails HB-RDY-004 when its run exists.
4. **Condition 4:** no option-(a) branch ever. A test (grep over `discriminate.py` and `readiness.py`) finds no compare-subset code; a retry at an unchanged key returns `outcome == "confirmed"` with identical bytes (T-E4; mutant: put `run_id` back in the body, `create_once` raises HB-LED-007).
5. **The body is a pure function of its key.** Fields: `schema`, `task`, `task_version`, `identity_hash`, `platform`, `scores`, `expected`, `probe` (check-based only), `variants` (only if declared), `readiness_failures`. A test asserts the key set and that no key or value holds a clock, duration, pid, path, `run_id` or `grading_id`; two trials in different run folders give byte-identical files.
6. **`probe` only for `CHECK_PROPERTIES` tasks:** T-E1c (no `probe` key, `problems()` is `[]`); T-E8 (a) no record, (b) no `probe`, (c) `hosts_ready` 0, (d) a check-less record carrying a `probe` fails HB-RDY-001. Mutant: R-HOST applied to a check-less task.
7. **The link fields:** `record_stem`, `record_sha256`, `run_id`, `grading_id`, `recorded_at` and `mono_ns` (the ledger `stamp`), timings and counts. **Newest link by `recorded_at` only**, among links whose `record_stem` equals the record's stem.
8. **Readers and conversion:** `hidden_test_disagreements` and `unbiased_failures` return `list[str]` or raise HB-USR-002 with the reason (T-E14, T-E15); `discriminate` converts to an HB-RDY-011 item carrying the reason; not-comparable cells are HB-RDY-011 items in a trial. Mutant: return `[]` on the raise.
9. **`check_segment` on every name that becomes a path part:** case ids (HB-RDY-005; also the `paths` drive/root test `C:foo`, `\foo`, `test_cases_paths_outside_root_are_refused` readiness side), variant names, and every overlay and `edits[].file` component. The T-E3 fixtures include `nul`, `NUL` and `com1` under a permissive pattern, `lpt9.log`, `a:b`, `x.`, `x `, `"ok\n"`; readiness and the real agent give equal verdicts (differential). Controls `inj-1`, `null`, `con-1` pass.
10. **Variants file rules:** one top-level `VARIANTS` literal read with `ast.literal_eval`, never imported (a sentinel file is not created, T-E11); at most 64 KiB; two assignments, an annotated or augmented one, a non-literal, a bad name, a `clauses` text over 200 characters, `old` matching 0 or 2 times: HB-RDY-005; `SyntaxError`, `RecursionError` and `MemoryError` while reading: HB-RDY-005 (one param each). The record copies the declared clause text only. A crash variant fails assertions (1) or (2), not a flip (T-E12).
11. **`clauses.json`** is read through `property.json` `check.clauses`, parsed after the egress scan, capped at 64 KiB; a pointer that does not resolve is HB-RDY-011 (fail closed).
12. **No `config.validate_matrix`:** `discriminate` builds its `bench-matrix/1` in memory and calls `plan.build_plan` directly; a grep assertion finds neither `validate_matrix` nor `config.HARNESSES` in the three modules. Another grep assertion: no `startswith("builds/")` and no `builds/` literal in `readiness.py` (T-E7). T-E7 (b2): a two-task baseline holding `builds`, valid for task one, passes.
13. **Sweeper:** `discriminate.run` takes `runs/.discriminate-<task>.lock` before planning (T-E20: held lock gives HB-RUN-005 and no run folder), then `atomic.sweep_temps(bench/discrimination/<task>/, lock)` before the write; readers use `is_temp_name`, skip and name each temp in a `note:` line and never delete (T-E17, with the non-temp name `x.tmp-notes` surviving). The test pins the lock to its folder (RV-SEC: `atomic` does not know the pairing).
14. **Telemetry (IO):** events `discriminate.started`, `discriminate.finished` (`outcome`, `error_code`), `readiness.validated` (`reconciled=`); `detail` holds `plan_ms engine_ms grade_ms compare_ms write_ms cells=n`; each field is `null` when not recorded, never 0. One test reads them from a real trial.
15. **Joins:** J1 (`tests/test_profiles.py`, `tests/test_acp_record.py` unchanged and green); J2 (S1's real discrimination, `oracle/evidence.md` and the 15-cell wall time; per W0 §2 order: set `status: ready`, run `bench discriminate S1`, commit `tasks/S1/` and the record in one commit; the Leader runs it, not you); J3 (spike S-E1 on Python 3.14.6).
16. The required end-to-end test T-E1b: the real probe host spawned by the real grader, reference `property_check_pass == 1`, naive `0`, `probe.reference.hosts_ready == len(cases)`; mutant: a stub host returning `blocked` for all cases.
17. SCAN-A (T-E10): `scan_a` gives reference `exploit_probes_blocked` `"0.8000"` against expected `"1.0000"`, and `property_check_pass` 0; `problems()` names the metric, expected and observed; `scan_a_secondary` fails on the secondary only.

## Exit
README §3 join gate, then report per README §4, with the T-E19 reader list, the R2-5 split and every `assume:` you wrote. Seam requests: `tests/test_architecture.py` entries (X-D), the `cmd_validate` and `discriminate` lines (X-C, SR-E2).
