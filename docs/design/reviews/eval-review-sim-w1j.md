---
id: review-eval-sim-w1j
title: "Simplifier lens review of W1-J, multi-turn attempt and the TLA+ model"
type: doc
status: draft
owner: "@timianmalloo"
links:
  - { to: design-eval-seam-contracts, rel: relates-to }
review-by: "2026-10-17"
summary: >-
  RV-SIM (Simplifier, soft veto) findings on docs/design/eval-multi-turn.md (design/eval-multi-turn, 08fabe34, 6b838ff2)
  against W0 rev 6 and the rulings on main. The mechanism earns its place for E2. The check_models.py change can shrink
  to data rows by reusing the existing WIDER substitution, the US-44 run should be one-time evidence, one of the two
  in-place variants is the same guard, and the resume-owned parts wait for W1-K.
---

# Simplifier review: W1-J multi-turn (rv-sim-w1j-e1e4)

Target: `docs/design/eval-multi-turn.md`, `models/run_lifecycle.tla` and four `.cfg` files on `design/eval-multi-turn`, against W0 rev 6 and `tools/check_models.py` on main. Verified = read in the design, the model or main. Inferred = reasoned, not run. I did not re-run TLC. RV-TA's ten findings (`eval-review-ta-w1j.md`) are not repeated; where I agree I say so in a clause.

## Findings

| # | location | finding | severity | evidence | fix | confidence |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | App. A; `TURN_VARIANTS`, `TURN_WITNESSES`, the extra `runs` entry | The turn routing is new logic where an existing mechanism does the job. `check_models.py` already runs a variant at different bounds through `WIDER = {variant: {"Parallelism = 1": "Parallelism = 2"}}` and `substitute()` (main `check_models.py:68,179`). `TURN_VARIANTS` is a second routing set for the same purpose. What remains is data rows: a `NumTurns = 1` to `NumTurns = 2` substitution fed to the `WIDER` lookup for five variants, plus witness rows. This also answers RV-TA 1: the grant says "data rows only", and this form nearly fits it. | major | Appendix A hunks `@@ -161`, `@@ -175`; main `check_models.py:68,178-179`. | Replace `TURN_VARIANTS` with `WIDER` entries, and run the two turn witnesses through the same substitution. Keep the logic hunks at zero or one. | Verified (mechanism exists); Inferred (the witness path needs one line) |
| 2 | `run_lifecycle.turns.cfg` | The file differs from `safety.cfg` in four values (cells, parallelism, `NumTurns`, an invariant subset) and the header comments. A second config kept in step by hand with `safety.cfg` is the drift the "derive from one file" idiom in `check_models.py` exists to avoid. | minor | `diff safety.cfg turns.cfg`: 3 value lines plus the invariant list. | Derive the two-turn run by `substitute(small, {"NumTurns = 1": "NumTurns = 2"})` like `safety-small`. If the bench-grade space then does not finish, keep the file and say why in its header (Inferred: `small` adds `bench grade`, and the author found that costly at 3 cells). | Verified (diff); Inferred (size) |
| 3 | s6.1 US-44 row, 41 min 54 s, 1.84e9 states | The run proves the phased three-step final-archive write at 3 cells, parallelism 2. It carries no turn invariant (`NumTurns = 1`). Its collision estimate (2.8e-3) is the weakest in the set, and the author says so. The 2-cell runs reach every action of the archive protocol; the extra cell and slot add interleavings of the same per-cell actions, not new actions. It is worth running once, because the archive write changed. It is not worth a place in any continuous ring. | major | s6.1 row 5 and note (1); `--quick` already skips it. | State it as one-time evidence for this model revision. Do not add it to the post-merge ring; run it on a model change that touches the archive protocol, with `--deep`. | Verified (what runs); Inferred (that no new action is reached) |
| 4 | Variants `archive_in_place` and `snapshot_in_place` | Both flip one predicate, `InPlace(a)`, in one action, `CopyBegin(c, a)` (`.tla:359`, `:364`). The invariant is `\A c, a`. One variant at `a = 0` and one at `a > 0` test the same guard in the same action. `snapshot_in_place` also needs the turns bounds, so it costs an extra TLC run in the quick gate. | minor | `.tla:359`: `InPlace(a) == (a = 0 /\ BUG = "archive_in_place") \/ (a > 0 /\ BUG = "snapshot_in_place")`. | Drop `snapshot_in_place` unless a counterexample shows a snapshot-only path in `CopyBegin`; 28 becomes 27. Or keep it and say which guard it separates. | Verified (predicate); Inferred (no snapshot-only branch) |
| 5 | Variant count, 22 old plus 6 new | The six new variants map to the five ADR-0015 section 7 invariants, with the doubled in-place case (finding 4). `resend_turn_on_resume` and the retargeted `relaunch_prompted` both reject through `PromptOncePerTurn`, but `ResendTurn(c)` is its own predicate for a crashed turn k>1 (`.tla:572`, `:577`), so the new one separates a different reopen path. Keep. The four witnesses are the cheapest non-vacuity proof. Keep. | minor (no cut beyond 4) | `.tla:572,577`. | None beyond finding 4. | Verified |
| 6 | Crash classification: `ClassOf`, `BetweenSnapped`, `NotCrashBetween`, `kill_between_turns`, liveness fairness | ADR-0015 section 7 names `CrashedTurnPredicate`, so the model needs it for E2's evidence. The code that acts on it (`failed (coordinator crash between turns)`, HB-CELL-119, the redo of a between-turns snapshot) is X-K1's and ships in E3 (W0 section 11; design F3, "X-K1 owns the code"). The design's own text says "W1-K may refine" the final branch of `ClassOf`. So two rules in W1-J's `.tla` will be rewritten by W1-K: the redo-snapshot branch of resume and the final else-branch. This agrees with RV-TA 2 (the predicate is circular as stated). | major | s6 "Resume classification"; F3; W0 s11 HB-CELL-119 owner. | Keep the invariant and its one variant, now with the ADR's own formula (RV-TA 2). Mark `BetweenSnapped` and the final else-branch of `ClassOf` provisional in the `.tla` header, owned by W1-K at its join. Add nothing for resume to the E2 build list. | Verified |
| 7 | `snapshot` field on `archive_files` (D-J2) | Earns its place. Without it the snapshot rows collide with the final rows on `(cell, attempt, path)`, and `views.load` raises `HB-LED-003` today (T-VER-1 is red for that reason). The alternative, a second table, is rejected in ADR-0015. Omitting the field on final rows keeps every `archive_hash` byte unchanged. Not simplifiable. | none | s2 durable table; T-VER-1; RV-TA 7 on the writer-side pin. | None. | Verified |
| 8 | Snapshot per turn | Earns its place. ADR-0015 section 1 and ruling DR-E4 require it (a rework task grades turn 1). The mechanism is `publish_dir` reuse plus a `Session` split of `run_turn`, with `run_turn` kept as a two-line wrapper. No new primitive. The author cut the right things (no per-turn budget, no `home/`, no third turn). | none | s5 patterns table; ADR-0015 s1, s5a. | None. | Verified |
| 9 | s4.4 step 3 retry; `job_active_baseline` (SR-J1) | Both are small and measured. The baseline is needed for the quiescence filter to mean anything (the adapter counts in `job.active`, Verified in `_end_process`). The three-try 1, 2, 4 s retry on `PermissionError` is S-J3 applied, but W0 section 4 already names one WIN-A retry loop for `PermissionError`; a second loop would be a duplicate. | minor | W0 s4 ("the one WIN-A loop"); design s4.4 step 3. | State that step 3 calls W0's helper. If it is a separate loop, drop it. | Verified (W0 names the loop); Inferred (the design's loop is separate) |
| 10 | Tests T-MOD-1, T-VER-3, T-ENG-3 | Three tests repeat a check another test owns. T-MOD-1 pins a subset relation that `check_models.py` enforces at run time and that the seven existing `test_check_models.py` tests cover (s6.1 says 7 of 7 pass). T-VER-3 is a golden that is green today and stays green: a regression, not a new check. T-ENG-3 (stdin open between turns) is the same observation as T-ENG-1's single `session/new` plus ordered ledger. | minor | s11 rows. | Drop T-MOD-1; name the existing golden test instead of adding T-VER-3; fold T-ENG-3 into T-ENG-1 if M-CLOSE also fails T-ENG-1. | Verified (T-MOD-1, T-VER-3); Inferred (T-ENG-3 fold) |

## What can wait

| item | until | reason |
| --- | --- | --- |
| `BetweenSnapped` redo, ClassOf else-branch, HB-CELL-119 | W1-K / E3 | the resume predicate is X-K1's (finding 6) |
| US-44 run in any ring | a protocol change only | finding 3 |
| `append_missing_rows` shared with W1-B (SR-J4) | the first of X-B2 or X-J1 that needs it | already "not blocking"; do not build it ahead |
| `turns.cfg` as a separate file | decided by the size of `substitute(small, ...)` | finding 2 |
| `job_active_baseline` (SR-J1) | stays provisional | the report filter is X-A3's, not X-J1's gate |

## Smallest set that proves ADR-0015 section 7

Four runs prove it: liveness (1 cell, 2 turns), safety-turns (2 cells, 2 turns), grading (2 passes, 1 turn) and safety-small (final-archive protocol), plus the variants. The 42-minute US-44 run is an extra, not part of the proof (finding 3). Variants: 27 are enough (finding 4); the four witnesses stay.

## Seam note

No disagreement with another design. The one tension is with the W0 section 13 grant ("data rows only"): findings 1 and 2 are the route that stays inside it. W0 section 5 lists `tasks.<id>.turns` as `[{n, sha256}]`; the design asks for `{n, prompt, sha256}` (SR-J3, provisional). The plan already freezes turn 1's text the same way (`plan.py:153`), so I find it earns its place and leave the ruling to the Coordinator.

`GATE W1-J · Simplifier · PASS WITH CONDITIONS · 10 findings (rv-sim-w1j-e1e4, 2026-10-03)`

Conditions: 1 (reuse `WIDER`), 3 (US-44 as one-time evidence), 6 (mark resume-owned model branches provisional for W1-K). Findings 2, 4, 9 and 10 are advice.
