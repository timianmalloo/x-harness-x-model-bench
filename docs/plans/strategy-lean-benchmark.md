---
id: plan-strategy-lean-benchmark
title: "Strategy - from E5's campaign to the lean pack benchmark"
type: plan
status: proposed
owner: "@timianmalloo"
summary: "Where the repo stands on 2026-10-09 and the path to the operator-accepted lean design: 10 tasks x 2 arms x 3 harnesses x 2 repetitions = 120 cells, about 2 h of run and 2 h of grading, reusing plan/run/grade/report and adding only a paired property_check_pass summary."
tags: [strategy, evaluation, lean-benchmark, e5, pack-effect]
links:
  - { to: spec-enterprise-evaluation, rel: relates-to }
  - { to: coordination-finish, rel: relates-to }
  - { to: arch-evaluation-campaign, rel: relates-to }
  - { to: rulings-register, rel: depends-on }
review-by: "2026-10-23"
---

# Strategy: from E5's campaign to the lean pack benchmark

**Result first.** Almost everything the lean benchmark needs is already built and joined: the ten property tasks, the
two-arm matrix with a bound pack-on arm, `bench plan` / `run` / `grade` / `report`, pack-off workspaces without
instruction files (Ruling 116), and tokens as the only cost axis (Ruling 115). Four things are missing:
1. a 2-repetition matrix;
2. a paired summary on the primary metric, `property_check_pass`;
3. the docs that retire E5's campaign design;
4. one short pre-registration.

The work is about one day of agent time and about 4.5 h of machine time for the run. Every claim below was read from
the repo on 2026-10-09; anything not read is marked **Inferred**.

## 1. The decision being implemented

The operator accepted the proposal *Lean Pack Benchmark*, revision 2, on 2026-10-09 ("perfect"). The proposal is
`docs/proposals/lean-pack-benchmark.html`, published as https://claude.ai/artifact/2RCLBk2oQAkiaErgW6Em6x. The same
day the operator decided:

- **The alarm requirement is dropped** ("yes drop the requirement"). The drill's push never reached the phone. The
  lean run is under 4 h, so registration's HB-CMP-011 never applies, and the lean run does not register a campaign
  anyway.
- **Target: about 2 h of run and 2 h of grading** ("further reduce: i want a target of about 2hr for run time and 2hr
  for grading").

| | E5 as planned (`coordination-finish.md` *E5 sizing*) | Lean benchmark |
| --- | --- | --- |
| cells | 1,644 (27 repetitions + 24 calibration) | **120** (2 repetitions, no calibration) |
| run at 3 slots | 30.7 h, about 4 nights | **about 2.2 h** (Inferred: grid-4's 1.12 min per cell at 3 slots) |
| grading | 31.8 h | **about 2.3 h** (Inferred: grid-4's 1.16 min per cell) |
| tokens | 1.74B | **about 127M** (Inferred: the spec's 1.06M per cell) |
| answer | 15 verdicts (5 properties x 3 harnesses) at MDE 0.20 | per harness: pack-on vs pack-off on the primary metric, 20 pairs, MDE about 0.31; pooled 60 pairs, MDE about 0.19; per property exploratory; token ratio per harness |

The MDE figures use the spec's paired-binary formula. Recomputing the spec's own case (ψ 0.28, δ 0.20, α 0.05,
power 0.8) gives 52.5, which matches the spec's n = 53. The script is `C:\tf\leader\mde2.py`. Repeats of one task are
correlated, so the real per-harness MDE lies between the 20-pair value (0.31) and the 10-task value (0.42).

## 2. Where the repo stands (read 2026-10-09)

**Branches.** `integrate/finish-19` at `a1cf7e95` holds every P2 and P3 join of the finish run:
- X-PROP, X-HYG, X-GSM, X-WIN, X-CACHEB;
- X-REDS, X-NOPRICE, X-S2, X-DRILL (with its loop-back), X-PACKOFF (with its loop-back), X-SJ4, X-E5M;
- Rulings 114-116.

`main` is at `f544deb2`. The finish batch gate (gate ring and stamp renewal, stamped tier, rings, `mutate --touched
f544deb2`, light checks, `run-verify-gates`) was running at this writing. The push to `main` follows its green.

**Usable as is:**

| capability | where | read |
| --- | --- | --- |
| the ten property tasks (S, RS, RW, NG, SM, two each) | `tasks/`, `bench/bom.yaml` | `bench/rings/e5-pilot.yaml` subset |
| two-arm matrix, pack-on as a role arm bound at plan time | `bench/rings/e5-pilot.yaml` (1 repetition, 60 cells), `bench/matrix.e5-grid.yaml` | `bench plan ... --arm on=C:/Projects/ai-forward@4a22f12c...` exits 0 on both, on the joined head (Leader, 2026-10-09) |
| plan, run (runs to completion, then grades), grade, report | `bench --help` | `src/harness_bench/cli.py` |
| pack-off workspaces free of agent-instruction files, for every harness | `workspace.task_source`, HB-PRE-009 | Ruling 116; X-PACKOFF |
| the report's pack-effect section: pass@1 and composite differences per combo, with intervals | `src/harness_bench/board.py` `PackEffectRow`, `report/html.py` | `board.py:80`, `:240` |
| tokens as the only rendered cost axis | `report/**`, `cli_table.py` | Ruling 115; X-NOPRICE |
| pinned E5 models | `cc-opus` `claude-opus-5-5`, `codex-sol` `gpt-6.1-sol`, `copilot-sol` `gpt-6.1-sol` | `bench/rings/e5-pilot.yaml` |

**Not on the lean path:**
- **The campaign machinery.** This covers `bench campaign`, the prior and final power analyses, pre-registration
  registration, the alarm drill, HB-CMP-011, nightly resume under the alarm, and the convergence re-run. It stays in
  the code, unused by this run. Nothing is deleted.
- **The readiness records.** `plan.py` and `run` do not import `readiness`; only `campaign.py`, `cli.py`,
  `discriminate.py` and `identity.py` do (read by grep). So a lean run does not need the ten records. They are stale
  against the final head anyway (RECID-A), and X-PACKOFF changed NG1's and S2's base trees.

**Gaps:**
1. **No 2-repetition matrix.** `e5-pilot.yaml` has 1 repetition; `matrix.e5-grid.yaml` has 27 plus a comparison ring
   tag.
2. **No paired summary on `property_check_pass`.** The board's pack effect covers pass@1 and the composite.
   `property_check_pass` is catalog 0.7 with `weight: 0` (`bench/metrics.yaml:57`), so it is outside the composite.
   The lean question ("does the pack make each harness better at enterprise properties") is answered by that metric,
   so the spec must name the primary metric and the report must show its paired difference per harness with an
   interval.
3. **The docs still describe E5 as a campaign.** These need to say the lean design supersedes it:
   - `docs/specs/enterprise-evaluation.md`;
   - `docs/coordination/coordination-finish.md` spine 8, *E5 sizing* and the operator stops;
   - `docs/architecture-evaluation-campaign.md`.
4. **No pre-registration.** One paragraph naming the primary metric, the comparison, the pairing unit and the
   exclusions, committed before batch 1.

**In flight from the finish run, to land or close before the lean run:**

| item | state | action |
| --- | --- | --- |
| finish batch gate | running | push P2+P3 to `main` when green |
| X-ALARMCWD (`build/fin-x-alarmcwd`, `edceff56`) | verified: red with the old script (`assert 1 == 6`), green 20/20 | join (small, real bug, keeps the alarm correct for future multi-night work) |
| X-FLAKE turn 3 (`build/fin-x-flake3`, Sonnet) | running | verify and join when it returns, or close it as not delivered |
| F-PACK phase 1 (ai-forward `fix/xh-finish-upstream`, `e1f8ad5`) | `verify-bundle` 18/18 by the worker; 37 line-ending-only files uncommitted | Leader verifies, then pushes to ai-forward; phase 2 (`/updatepack` here) after the lean result |
| scheduled task `HarnessBenchAlarmDrill` | exists (on demand, no trigger) | delete with the operator's go |
| X-CACHEB's Windows event-log read | open since 2026-10-08 | stays open (not on the lean path) |
| worktrees (`coord worktree list`) | many finish-run trees | `coord worktree cleanup` report, then `--remove` on the operator's go |

## 3. Strategy

Smallest correct path (the Solution-Selection Ladder): reuse first, and build only what the answer cannot exist without.

1. **Phase A: land the finish run (the current session).** Batch gate green, then push `integrate/finish-19` to
   `main`. Join X-ALARMCWD, and X-FLAKE if it is green, then push. Push F-PACK phase 1 to ai-forward after a Leader
   re-run of `verify-bundle.ps1`. Commit this strategy, the spec and the execution prompt with that push, so a fresh
   session starts from `main`.
2. **Phase B: specify (`/specify`).** A spec for the lean benchmark that supersedes E5's campaign design for this
   question:
   - functional layer: the question, the design (120 cells, two batches), the primary metric, the comparisons, the
     outputs, the checkpoint between batches, the pre-registration;
   - UX and UI layers: the report's lean summary.

   Written on 2026-10-09: `docs/specs/lean-pack-benchmark.md`.
3. **Phase C: define the architecture (`/define-architecture`).** Expected decisions:
   - (a) **One run or two.** One matrix with `repetitions: 2` and a checkpoint read from `bench status`, or two runs of
     the 1-repetition pilot ring with a pooled summary. Choose by reading whether the plan orders cells
     repetition-major and whether the report can pool runs. Recommendation, Inferred: two runs, because the
     checkpoint is then a real stop, plus a summary that reads both runs' ledgers.
   - (b) **Where the paired summary lives.** Extend the board's pack effect to `property_check_pass` paired by
     (task, repetition, harness), reusing `board.interval`. Do not build a second interval engine (derive, don't
     store).
   - (c) **Per-property rows, exploratory**, with counts and no verdict words. EVU-6's sweep pattern keeps "better",
     "worse" and "dominates" out of the exploratory text.
   - (d) **Token ratio per harness with its interval.** Check what the board already gives here.
   - (e) **Records:** refresh the ten readiness records on the final head (about 1 h of Leader machine time,
     Inferred), or settle for `bench validate` plus the discrimination evidence already joined. Recommendation:
     `bench validate` plus one discrimination trial each for NG1 and S2, whose base trees changed.
4. **Phase D: prepare for coordination (`/prepare-for-coordination`).** Few tracks; the Simplifier strikes the rest:
   - **L-MATRIX**: the lean matrix file(s), and `bench plan` proof of 120 cells (60 per batch), 0 instruction files for
     every pack-off cell, and the model pins.
   - **L-SUMMARY**: the paired `property_check_pass` summary in `board` and the report, red first, with mutants.
   - **L-DOCS**: errata that retire E5's campaign design in the spec, the plan and the architecture; the
     pre-registration paragraph.
   - **L-RECORDS** (if the architecture keeps it): Leader machine time.
5. **Phase E: execute (`/execute-with-coordination`).**
   1. Join the tracks.
   2. Run one batch gate, and the gate ring only if a stamp input moved.
   3. Push.
   4. Commit the pre-registration.
   5. **Operator stop:** token approval, about 127M Inferred.
   6. Batch 1: 60 cells. Then the checkpoint: real minutes, grading minutes and tokens per cell against the estimate.
   7. Batch 2: 60 cells. Grade batch 1 while batch 2 runs, if the architecture allows it.
   8. Grade, then report, then write the run report.
6. **Phase F: close.** Delete the drill task, run worktree cleanup, delete the scratch roots, and write the closing
   audit entries.

## 4. Seats and harnesses for the execution (operator, 2026-10-09)

- **Owner:** Fable (`owner-fable`). It rules decision requests.
- **Leader and Coordinators:** Claude Code, Opus (`claude-opus-5-5`).
- **Claude sub-agents:** Opus for code that needs judgement (L-SUMMARY review, any loop-back); Haiku
  (`claude-haiku-4-5-20251001`) for mechanical work (docs errata, cleanup reports, read-only sweeps).
- **Distributed coding:** Grok (`grok-4.7`, effort high) and Agy (`gemini-3.8-flash-high`) through `coord-runner`.
  Codex and Copilot are not workers in this run; Copilot is a benchmark subject only.

## 5. Lessons from the finish run that the execution must carry (each is a class in `docs/lessons/defect-classes.md`)

| class | what happened | carry-over rule |
| --- | --- | --- |
| CEIL-A | Grok's and Agy's floors were taken as the first context reading, so every turn split at item 1 | floors are the grounding cost at the first edit: Grok 88k (`updates.jsonl` `params._meta.totalTokens`), Agy about 105k (Inferred, one case); thresholds absolute |
| verification gap (X-DRILL, X-PACKOFF) | a worker's own test files were green, but neighbours failed at the join recount | before each `src/` join, the Leader runs the full suite on the worker branch (`pytest -n 4 --dist loadscope`) |
| LOGTEAR-A | concurrent runner appends tore a row in the Leader's log, and every commit repo-wide was refused | never edit a log; stop and ask the operator; the control is owed (per-run logs or an append lock) |
| FLAKE-A | the end-to-end walk fails under load and passes alone | one recount retry per join (`conductor-join --continue` needs `--title`), then treat a second red as real |
| PACKOFF-A | upstream instruction files leaked into pack-off workspaces | HB-PRE-009 guards every harness; `bench plan` with the `--arm on=` binding is the probe |
| TEST-E | a compiled premise check omitted `--arm on=SOURCE@COMMIT` and proved nothing | a brief's proof command is run once by its author before dispatch |
| STORE-A | Grok's served-model reader used the wrong store key | fixed by X-GSM; read the served id with `tools/grok_served_model.py --tree` |
| alarm working directory | the scheduled alarm task ran from `System32`, where `bench` cannot find the repo | fixed by X-ALARMCWD (the wrapper runs from the repo) |

## 6. Risks and how they surface

| risk | signal | response |
| --- | --- | --- |
| property tasks run slower or costlier than grid-4 (no real-model cell has run them) | batch 1's measured minutes and tokens per cell | the checkpoint: the operator keeps or cuts batch 2 |
| a harness's pack effect is smaller than the per-harness MDE | the interval crosses 0 | report "inconclusive at MDE 0.31"; a 1-repetition top-up for that harness (20 cells, about 45 min) is the operator's call |
| a rate limit at 3 slots | cell failures with a rate-limit cause in `bench status` | drop to 2 slots (grid-4 measured 2) |
| the pooled result hides opposite per-harness effects | per-harness intervals on opposite sides of 0 | the per-harness rows are the decision; the pooled row is a summary |
