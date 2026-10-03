---
id: review-eval-ta-w1j
title: "W1-J multi-turn design review: Test Architect lens"
type: doc
status: draft
owner: "@timianmalloo"
phase: "Enterprise evaluation: Wave 1 gate reviews"
tags: [review, test-architect, evaluation-campaign, wave-1, w1-j]
links:
  - { to: design-eval-seam-contracts, rel: relates-to }
review-by: "2026-10-17"
summary: >-
  Test Architect (Adversary Mode) review of W1-J (multi-turn attempt, turn snapshots, TLA+ model v5) against W0 rev 6
  and the rulings on main. PASS WITH CONDITIONS: the model evidence is real and each ADR-0015 section 7 invariant has
  its own variant, but the check_models.py change exceeds its grant and is not on the branch, the two engine-bug tests
  are red for the wrong reason, and the final-row omission is pinned on the reader side only.
---

# Test Architect review: W1-J `docs/design/eval-multi-turn.md` (branch `design/eval-multi-turn`, `08fabe34`, `6b838ff2`)

Session `rv-ta-w1j-e1e4`, 2026-10-03. Checked against W0 rev 6 (sections 4, 12, 13, 14), the seam grant `req-01M41F2PAKH97KH6BDGXCTA1KK`, ADR-0015 section 7, `models/run_lifecycle.tla` (768 lines, read in the invariant, `CopyBegin`, `ReconcileRecord` and witness regions), the `.turns.cfg`, and the code the design cites on main. I did not re-run TLC; section 6.1's numbers are the author's and are Inferred as evidence. The branch is based on `124395fb` (W0 rev 2) and trails main; the design's code citations still match main (`engine.py:280-283`, `:714`, `archive.py:27,50`, `views.py:58,350,686`).

## Findings

| # | location | finding | severity | evidence | fix | confidence |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | s6 "Registered change" and Appendix A vs the grant | The grant covers "data rows only ... no change to the checker's logic" (W0 s13 row; resolution of `req-01M41F2PAKH97KH6BDGXCTA1KK`). Appendix A changes logic: a new `turns` run in `runs`, base-config routing by `TURN_VARIANTS`, and a merged witness loop that picks the config by name. Also the branch carries none of it: `tools/check_models.py` is not in `git diff 124395fb HEAD -- tools tests`. The `.tla` merging alone gives the 3 failures the design reports. | blocking (merge) | Grant text in `.agents/requests.jsonl` and W0 s13; Appendix A hunks at `@@ -145`, `@@ -161`, `@@ -175`; empty diff for `tools/` and `tests/` on the branch. | Ask the Coordinator to widen the grant to these three logic hunks (or keep the data-only part and let X-J1 own the rest), and put `tools/check_models.py` in the same commit as the `.tla`. State the merge as one unit. | Verified |
| 2 | s6 `CrashedTurnPredicate` | The invariant is `outcome = ClassOf(c)` and the only recording action writes `ClassOf(c)`. It is true by construction except under the one variant. ADR-0015 s7 states the predicate independently (`promptSent /\ ~turnEnded /\ ~terminal`). A wrong `ClassOf` (for example between-turns tested first) passes TLC. Only one direction is seeded (`kill_between_turns`); a crashed turn classed `crashbetween` is not. | major | `run_lifecycle.tla:110`, `:579`, `:731`; ADR-0015 s7 text. | State the invariant with the ADR's literal formula (a crashed turn implies `crashfail`; a between-turns cell with no crashed turn implies `crashbetween`) and add a reverse variant (`crashed_turn_as_between`). | Verified |
| 3 | s6.1 US-44 row | The 1.84e9-state run is `NumTurns = 1`, so it carries none of the turn invariants. Turn rules ran only at 2 cells, parallelism 1, 1 crash. Untested: parallelism 2 beside a copying cell, and a second crash during the redo copy of a between-turns cell (the exact path the liveness fix added). The collision estimate 2.8e-3 is on the weak side for one run, and the design says so. | major | Table rows 4 and 5; `turns.cfg` (`MaxCrashes = 1`, `Parallelism = 1`). | Condition: run `turns.cfg` with `MaxCrashes = 2` once (post-merge ring is fine) or record the gap as a named residual in the Gate record; re-run the US-44 row with a different fingerprint seed (`-fp`) so two independent runs bound the miss. | Verified (cfg); Inferred (feasibility of 2 crashes) |
| 4 | T-ENG-2, T-ENG-4 (the two engine bugs) | Both are red today because turn 2 is never sent, not because of the bug. T-ENG-2 fails as "turns ignored" and T-ENG-4's `u1 + u2` fails for the same reason. The bug itself (`prompt_mono` reset on every `prompt_sent`; usage read from the last response) is caught only by the mutants M-CLOCK and M-LAST, which are named but not run. Both bugs are real on today's code: `engine.py:280-283` resets on every `prompt_sent`; `:663` reads one response. | major | `engine.py:280-283`, `:663`; test rows T-ENG-2, T-ENG-4. | Say which commit lands first: a skeleton commit with the loop, the old `_after_append` and the last-response usage, so both tests fail on the bug (a cell that completes, a sum of 7), then the two fixes. Record the red output of each before the fix. | Verified |
| 5 | T-ENG-4 / s4.5 | The text promises `views._token_cross_check` (`views.py:350`) is fed the summed ACP usage or HB-VAL-005 warns on every two-turn cell, but no test asserts it. | major | s4.5 last sentence; T-ENG-4 row. | Add an assertion to T-ENG-4: `views.verify` on the two-turn run has no `HB-VAL-005`. Mutant: the cross-check reads the last turn. | Verified |
| 6 | README 2a item 1, T-ENG-5..9, T-SNAP-2..7, T-VER-2, T-PLAN-2, T-SWEEP-1 | About fifteen rows say "created with the loop / function" and name no assertion that fails today. T-ENG-6 admits it passes today trivially. Item 1 allows this only with a named skeleton commit order; none is named. Several reach fake-agent options that do not exist (`per_turn`, `prompts_log`; `daemon` and `prompt_error` do exist, `tests/fake_acp_agent.py:17-19,171-176`), so they would fail on a missing option, which is the wrong red. | major | Test table; `fake_acp_agent.py` grep. | Add a "commit order" paragraph: (1) fake-agent options plus `open_session`/`send_turn` skeleton, (2) tests, red on behaviour, (3) the implementation. For T-ENG-6, state the red as the M-STOP run, taken before the fix. | Verified |
| 7 | s2 decision D-J2, T-VER-3 | The final-row omission has only a reader-side pin. T-VER-3 runs legacy golden ledgers, which cannot detect a writer that starts adding `"snapshot": "final"`. `ROW_FIELDS` (`archive.py:27`) does not include `snapshot`, so `archive_hash` itself is safe; what would change is the ledger bytes and head hashes of new final rows, and the "legacy and new rows identical" claim. | major | `archive.py:27,50-52`; `tests/test_verify.py:251-258` (golden covers legacy data only). | Add one test: the rows `engine._archive` appends for a one-turn and a two-turn cell have no `snapshot` key, and `archive_hash` of a fixed row list equals a committed literal. Mutant: writer adds `snapshot: "final"`. | Verified |
| 8 | T-SWEEP-1, s7 sweep | The reader list cites a grep but no output count, and the test is described as "red only if the list drifts" with no named allowlist set or red fixture beyond "synthetic source". README 2a item 5 asks for the scan, its count and the same set in the test. My re-scan on main finds the same 8 readers plus the annotation at `grade/__init__.py:56`. | minor | grep on main (`"archive"`, `archive_dir`, `attempt-`). | State the count (8 readers, 1 annotation) and have the test assert the set. | Verified |
| 9 | s4.6 `NoSnapshotInFlight` in `replay` | The ledger form ("snapshot committed between turn end and next prompt") is not the model property (a copy starting while a turn runs is invisible in the ledger). Sharing the name overstates conformance. | minor | s4.6 table row 4; `tla:729`. | Name the ledger rule differently, for example `SnapshotAfterTurnEnd`, and say what it does not see. | Verified |
| 10 | s7 row 10 | The `ledger.py` kind-list claim is marked Inferred. I checked: `ledger.py` has no kind allowlist, so no change is needed. | minor | `grep` of `cell.prompt_sent\|KINDS` in `ledger.py`: no match. | Change to Verified and drop the row. | Verified |

## Points the brief asked for

- **Variants against ADR-0015 s7.** Four of five invariants each have a variant that removes exactly the guard the invariant names, run alone through `only_invariant` (`.tla:204`, `:378`, `:359`, `:572`). The fifth (`CrashedTurnPredicate`) has the circularity in finding 2. `PromptOncePerTurn` and `ArchiveExistsMeansComplete` additionally keep their older variants. The 4 witnesses make the passes non-vacuous.
- **TLC evidence.** Five clean runs and 28/28 plus 4/4 are consistent with the variant table (22 old, 6 new). Adequacy: see finding 3.
- **`end_turn`-only continuation.** Correctly distinguished from `COMPLETED_STOP_REASONS`; T-ENG-6 and mutant M-STOP separate them. Red-first is the open point (finding 6).
- **Merge blocker.** Finding 1. The design's own fallback (hold the branch) is the right one until the check_models change is in the branch.

## Seam note

No disagreement with another design. The disagreement is with the grant: Appendix A exceeds "data rows only" (finding 1). The `tasks.<id>.turns` shape (SR-J3) and `job_active_baseline` (SR-J1) are provisional and not tested in this plan beyond T-PLAN-1; they go to the Coordinator.

`GATE W1-J · Test Architect · PASS WITH CONDITIONS · 10 findings (rv-ta-w1j-e1e4, 2026-10-03)`

Conditions: 1 (grant and one-unit merge), 2 (independent predicate plus reverse variant), 3 (two-crash run or named residual), 4 to 7 (commit order, cross-check assertion, writer-side pin).
