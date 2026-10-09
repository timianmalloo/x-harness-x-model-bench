---
id: prompt-lean-benchmark
title: "Execution prompt - the lean pack benchmark (define-architecture, prepare and execute with coordination)"
type: doc
status: proposed
owner: "@timianmalloo"
summary: "The operator's prompt for a fresh session: from the committed lean spec, run /define-architecture, /prepare-for-coordination and /execute-with-coordination, then run the 120-cell benchmark and report. Owner Fable; Leader and Coordinators Opus; Opus and Haiku sub-agents; Grok and Agy for distributed coding."
tags: [prompt, coordination, lean-benchmark]
links:
  - { to: spec-lean-pack-benchmark, rel: implements }
  - { to: plan-strategy-lean-benchmark, rel: depends-on }
review-by: "2026-10-23"
---

# Execution prompt: the lean pack benchmark

Paste everything below the line into a fresh Claude Code session started in `C:\Projects\x-harness-x-model-bench`.

---

Take the lean pack benchmark from its committed spec to a reported result. The four steps run in this session, in
order; each starts only when the one before it has committed and its gate has passed:
1. `/define-architecture`;
2. `/prepare-for-coordination`;
3. `/execute-with-coordination`, as Leader;
4. the benchmark run itself (two batches) and its report.

The operator wants this done fast and small. The project spent weeks on a design that grew to four nights; the lean
design exists to stop that. Prefer reuse over new code, fewer tracks over more, and stop as soon as the result is
proven. The objective is lexicographic: completeness and rigor first, token cost second, speed third.

**Sources of record** (read them first; the repo wins over this prompt):
- the spec, `docs/specs/lean-pack-benchmark.md` (the contract);
- the strategy, `docs/plans/strategy-lean-benchmark.md` (where the repo stood on 2026-10-09, the gaps, and the
  lessons in its section 5);
- the operator-accepted proposal, `docs/proposals/lean-pack-benchmark.html` (revision 2, "perfect", 2026-10-09);
- `docs/notes/rulings.md` (Rulings 115 and 116 bind);
- `docs/lessons/defect-classes.md`;
- the run report and the coordination plan of the finish run (`docs/coordination/coordination-finish.md`).

**Start-state check, before anything else (stop and report if it fails):**
- `origin/main` contains the spec, the strategy and this prompt, and the finish run's P2 and P3 joins (`git log
  origin/main --oneline | grep -E "join-x-packoff|join-x-e5m"`).
- Run `coord doctor` and `pack-doctor.py`, and read their states back.
- The finish run's carry-over items are each landed or explicitly closed: X-ALARMCWD (the alarm wrapper runs from the
  repo), X-FLAKE turn 3, F-PACK phase 1 pushed to ai-forward, and the scheduled task `HarnessBenchAlarmDrill` deleted
  (operator's go). Any item that is not done becomes a track or an operator action in the plan. It is never silently
  dropped.

**Goal:** a lean benchmark run and reported, exactly as the spec defines it:
- 10 property tasks × 2 arms (pack-off, pack-on) × 3 harnesses × 2 repetitions = 120 cells, in two batches of 60, with
  the checkpoint (spec LB-3) between them;
- the primary metric `property_check_pass`, paired by task × repetition × harness through the existing
  `stats.paired_delta`;
- the report's lean summary: per-harness rows (MDE 0.31), a pooled row (MDE 0.19), per-property exploratory rows, and
  token ratios;
- a one-paragraph pre-registration committed before batch 1;
- a closing run report (md + html) under `docs/coordination/`, committed and pushed.

Targets: about 2 h of run and about 2 h of grading (Inferred; the checkpoint measures them). The token budget is
about 127M (Inferred).

**Benchmark cells pin their models.** These are the operator's standing principle ("Codex and GHCP should always be
latest Sol, Claude Code should always be latest Opus"):
- `cc-opus`: Claude Code `claude-opus-5-5`;
- `codex-sol`: Codex `gpt-6.1-sol`;
- `copilot-sol`: GitHub Copilot `gpt-6.1-sol`.

Re-check "latest" at the start. If a newer Opus or Sol id is served, ask the operator before changing a pin.

**Seats** (operator, 2026-10-09):
- **Owner:** Claude Code, Fable (`claude-fable-5-1`), session `owner-fable`. Rules every decision request into
  `docs/notes/rulings.md`.
- **Leader:** Claude Code, Opus (`claude-opus-5-5`), the next lease epoch (`coord leader pin`; renew it in a loop).
  - Merges only in a dedicated integration tree, and batches joins.
  - Pushes with exactly `git -C C:/Projects/x-harness-x-model-bench push origin <gated sha>:main`, never forced, and
    reads origin back after.
  - Fast-forwards the primary after each push.
- **Coordinators:** Claude Code, Opus (`claude-opus-5-5`), hand-back sessions. They compile every brief (compiled
  mode, replayed through the runner's check before dispatch) and own the errata and the register.
- **Claude sub-agents** (the Agent tool, always with an explicit `model`):
  - Opus for work that needs judgement: the lean summary's code review, any loop-back fix, the run report's analysis.
  - Haiku (`claude-haiku-4-5-20251001`) for mechanical work: docs errata, cleanup reports, read-only sweeps, the
    pre-registration's formatting check.
- **Distributed coding, through `coord-runner`, served id read back for every dispatch:**
  - **Grok** `grok-4.7`, effort high. R-103: read the first response's served model with `tools/grok_served_model.py
    --tree`; not `grok-4.7*` means kill and retry once. Run with XAI_API_KEY unset.
  - **Agy** `gemini-3.8-flash-high`.
  - Spread the coding tracks across both in parallel.
- **Not workers in this run:** Codex, Sonnet, and GitHub Copilot (a benchmark subject only, never a worker).

**Work to divide** (the strategy's gaps; verify each against the repo; the Simplifier strikes anything the spec does
not need):
- **L-MATRIX.** The lean matrix file or files, from `bench/rings/e5-pilot.yaml`'s subset, arms and pinned combos, with
  2 repetitions. Proof:
  - `bench plan ... --arm on=<pack source>@<40-hex commit>` exits 0 with exactly 120 cells (60 per batch);
  - every pack-off cell lists 0 instruction files;
  - every cell carries its model pin.

  Bind the pack-on arm to the pack revision the operator names. The finish run planned against
  `C:/Projects/ai-forward@4a22f12c4cbc9cd403627995109ccfdc1c6fa9c6`; ask if the revision should move to the F-PACK
  head.
- **L-SUMMARY.** The lean summary per spec LB-4 to LB-7 and Part B/C. The expected smallest change: add
  `property_check_pass` to the pack effect's measures (`board.py:588`, `:825` build `["pass_at_1", *cat.areas]`),
  plus the report section. Red first, with mutants. A non-lean run's report golden stays byte-identical. No second
  interval engine, and no new metric (catalog 0.7 stays frozen).
- **L-DOCS.** Dated errata beside the text that retire E5's campaign design for this question, in
  `docs/specs/enterprise-evaluation.md`, `docs/coordination/coordination-finish.md` (spine 8, *E5 sizing*, the
  operator stops) and `docs/architecture-evaluation-campaign.md`, following the spec's supersession table. Plus the
  pre-registration paragraph (spec LB-2), committed before batch 1. Haiku can draft; a Coordinator commits.
- **Architecture decisions** for `/define-architecture` to settle, each with a recommendation in the strategy's §3:
  - one run with 2 repetitions, or two 1-repetition runs pooled;
  - where the summary lives;
  - whether to refresh the readiness records. The recommendation is `bench validate` plus one discrimination trial
    each for NG1 and S2, whose base trees changed under Ruling 116.

**Rules the plan must encode** (measured lessons, strategy §5):
1. **Floors (CEIL-A)** are the grounding cost at the first edit of an owned file, never the turn's first reading:
   - Grok 88k, read from the latest `params._meta.totalTokens` in the worker's own `updates.jsonl`;
   - Agy about 105k (Inferred, one case);
   - Opus and Haiku: measure the first compile's reading and record it.

   Thresholds are absolute: the floor plus the planned work.
2. **Before every `src/` or `tests/` join,** the Leader runs the full suite on the worker's branch (`uv run pytest -q
   -p no:cacheprovider -n 4 --dist loadscope`) to catch neighbours that a worker's own files miss. Then the join
   recount runs. A red that passes alone gets one `conductor-join --continue` retry (it needs `--title`); a second red
   is real, and goes to a loop-back fix track (Opus).
3. **The worker gate (R-104):**
   - the worker's own tests are red first, on an assertion;
   - the guard list runs on the first and the final commit;
   - `mutate_check` runs on the worker's own mutation files;
   - ruff and `docs-graph validate` pass;
   - the console flag (`creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)`) is on every launch it adds;
   - the windows check runs at hand-back.

   Never use --no-verify, -n or a hooks override, and never rewrite a commit.
4. **Never edit a log.** A torn row (LOGTEAR-A) or a classifier denial stops that action and goes to the operator.
   Never route around a denial.
5. **Every brief's proof command is run once by its author before dispatch (TEST-E).** For the matrix, that means
   `bench plan` with the `--arm on=` binding and without `--json`, so the instruction probe is reached.
6. **Seats never write the primary.** Every continuation run gets a new session id, checked free (IDN-A). A new
   runner turn uses a new branch based on the old one (RUN-BRANCH).
7. **Caps:** 6 concurrent workers, at most 2 per external harness. Run the health check at every dispatch and join.
   Kill only PIDs the session started; close only windows the session created. Scratch lives under `C:\tf\<track>`.
8. **Tokens are the only cost axis.** Never write USD (Ruling 115).

**The run** (Leader, after the tracks join and the batch gate is green; the gate ring runs only if a stamp input
moved):
1. Push.
2. Commit the pre-registration.
3. Ask the operator once to approve about 127M tokens (Inferred).
4. Batch 1: 60 cells. Then the checkpoint (spec LB-3): measured minutes per cell for run and grading, and tokens per
   cell per harness and arm, each against the estimate. Batch 2 waits for the operator only if the checkpoint's
   thresholds trip.
5. Batch 2: 60 cells. Grade batch 1 while batch 2 runs, if the architecture allows it.
6. Grade, then report.
7. Write the run report: the result, both MDEs and the clustering caveat (the true per-harness MDE lies between 0.31
   and 0.42), the checkpoint numbers, tokens per harness and arm, the engine identity, the pack revision, and the
   pre-registration status.

**Plan output, per track:** owner; harness and model, with the reason; authored paths; depends-on; tier; budget
(calls, tokens, wall); exit evidence; fallback; termination condition; join batch. Also the serial spine, the
critical path (Inferred durations, labelled), the struck tracks, and the operator actions with their timing (the
pack-on revision, the token approval, the drill-task deletion if still open, and worktree cleanup).

**Execution reporting:** one status table per update (task, what it does, status, harness and model). Report only
when done or blocked on the operator.

**Stop rules:**
- the health check trips twice;
- the host becomes unstable (record evidence first);
- `main` cannot be made green within one bisect round;
- an operator-only blocker gates every remaining track.

Close with `coord worktree cleanup` (report first, then `--remove` on the operator's go), the closing audit entries,
and the scratch roots listed for deletion.

**Not in scope:**
- campaigns, power analyses, multi-night grids, the alarm and its drill, calibration cells, and the convergence
  re-run (spec non-goals);
- arm Y;
- new metrics or a catalog change;
- USD;
- macOS;
- GitHub Actions;
- force pushes or history rewrites;
- Codex, Sonnet or GitHub Copilot as workers.
