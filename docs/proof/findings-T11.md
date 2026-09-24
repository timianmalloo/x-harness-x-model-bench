---
id: "findings-t11-verify-later-pass"
title: "Findings → tests: track T11 verify-later-pass"
type: proof-pack
status: accepted
owner: "@timianmalloo"
phase: "Phase 1 · walking skeleton"
tags: [proof, findings, red-first, T11, views, verify, ledger]
links:
  - { to: coordination-phase1-finish, rel: relates-to }
  - { to: mutation-record-t2, rel: relates-to }
review-by: "2026-12-22"
summary: >-
  Test Architect N1: a later grading pass whose events segment was cut back before grading.completed and re-sealed
  verified with warnings and exit 0, silently rolling the current scores back. The honest runner seals events only
  after grading.completed, so bench verify now reports such a segment as HB-LED-002 (exit 5). Red 8edd94f, fixed in
  bdcd2ef, survivors killed in 98414f5; views.json 34/34; scoped cosmic-ray on verify 98 mutants, 0 open. Whole-tail
  deletion (shape A) is disclosed, not fixed.
---

# T11: verify-later-pass (Test Architect N1)

**The Coordinator transcribed this file** from the track's report. **The Coordinator also checked the evidence directly:**
- The red commit `8edd94f` is test-only (`git show --stat`). Re-run in a throwaway worktree, its test failed with `assert (0 == 5)`.
- `tests/mutations/views.json` was re-run: 34 of 34 killed.
- The source diff was read. It is one hunk inside `views.verify`.

## Symptom
The Test Architect's probe ran on a copy of the `heads` golden ledger. Views take the latest completed pass, so both changes below silently rolled the current scores back to the in-run pass.
- **(A)** Deleting all four segments of a later `bench grade` pass gave no finding.
- **(B)** Cutting `events/<later pass>` back before `grading.completed` and re-sealing it gave only HB-LED-004 warnings, and exit 0.

## Root cause
`views.verify` treated every `grade-*` segment outside a completed pass as abandoned, which is HB-LED-004, a warning, whether or not the segment was sealed.

The honest runner never produces a sealed events segment without `grading.completed`. In `grade/runner.py`:
- `:113` seals the other facts;
- `:114` appends `grading.completed`;
- `:116` seals events.

Its `finally` only calls `close()`, which never seals (`ledger.py:241`).

## Fix
In `verify()`, a sealed `events/grade-*` segment that is not a completed pass is now `HB-LED-002` (chain or seal break), an error: `events/<gid>: sealed, but holds no grading.completed`. This mirrors the existing HB-LED-002 case, where a pass is marked complete but is not sealed. Unsealed segments, and the fact segments of an unfinished pass, stay HB-LED-004 warnings. No error code was added.

## Proof
- **Red:** `8edd94f`. `tests/test_verify.py::test_a_later_pass_cut_before_grading_completed_and_resealed_is_exit_5` failed at `tests/test_verify.py:262` with `assert (0 == 5)`. The Coordinator re-ran it.
- **Guard (passed at red and at fix):** `tests/test_verify.py::test_an_in_progress_or_interrupted_pass_is_a_warning_never_an_error`.
  - It covers three crash points of the real `run_pass`: grading a cell; before `grading.completed`; before the events seal.
  - At each point, `verify` run mid-pass has no error. The interrupted pass's events segment is unsealed, and `verify` exits 0 with an HB-LED-004 warning. The next pass then completes and verifies clean.
  - This guard kills the over-broad mutants.
- **Fix:** `bdcd2ef`.
- **Survivor test:** `98414f5`. `test_a_warning_never_stops_the_archive_checks_and_every_edited_archive_is_reported` kills two cosmic-ray survivors in `verify`:
  - a `>=` comparison that let a warning stop the archive checks;
  - an exception replacement that dropped every archive finding after the first.
- **Mutation:** `tests/mutations/views.json` gains 5 entries. All 34 are killed.
- **cosmic-ray** (scoped to `verify`, `views.py:427-466`): 98 mutants, 93 killed, 5 equivalent, 0 open. See the T11 addendum in `docs/notes/mutation-record-t2.md`.
- **Gates (track-reported; the join's recount re-measures them):**
  - `pytest -m "not credentials"`: 521 passed, 5 deselected;
  - `ruff`: clean.

## Disclosed, not fixed: whole-tail deletion (shape A)
`bench verify` can check a grading pass only against something the ledger itself records. A later `bench grade` pass writes its own four segments, and nothing written afterwards names it:
- `run.completed` names only the in-run pass;
- no later pass records the heads of an earlier one.

So deleting all four segments of a later pass leaves a ledger that is internally consistent. It is byte for byte a ledger in which that pass never ran, and the views fall back silently to the previous completed pass.

The same limit covers cutting a later pass's events segment back before `grading.completed` *without* re-sealing it. That leaves exactly what an honest crash leaves, so it stays an HB-LED-004 warning.

Detecting either needs an anchor outside the run's own segments, for example:
- each new pass carrying forward the heads of the passes before it;
- an external log;
- a signed digest.

That is a design decision (ADR-0006, a ruling), not a `verify` change. Until then, the current scores of a run with more than one grading pass are only as trustworthy as the filesystem that holds them.

## Named, not fixed
- **[Minor, Inferred from source]** Deleting only `events/<later pass>` while its sealed fact segments remain gives exit 0 with three HB-LED-004 warnings. This never happens honestly, because `runner.py:101-102` creates events first. It could be detected with the same HB-LED-002 check, but deleting all four segments (shape A) evades it anyway.
- **[Minor, Flagged] T2's record may have overstated two kills.**
  - Under `test_views`, `test_verify` and `test_grade`, two `verify` mutants survived at `bdcd2ef`: the Eq_GtE at `:446` and the ExceptionReplacer at `:464`. T2's record lists neither as equivalent, so it must have counted them killed.
  - The likely cause is T2's survivor re-run, which added `test_status` and `test_engine`. That is not verified.
  - Both mutants are now killed by `test_verify.py` itself and are pinned in `views.json`.
