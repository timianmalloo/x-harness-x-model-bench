---
id: coordination-eval-wave2-e234-briefs
title: "Wave 2 E2-E4 dispatch pack: briefs, routing, DAG and launch order (Evaluation Campaign, pack part 3)"
type: plan
status: proposed
owner: "@timianmalloo"
phase: "Enterprise evaluation: Wave 2, phases E2 (multi-turn), E3 (arms, catalog freeze, resume), E4 (remaining property tasks), convergence"
tags: [coordination, briefs, wave-2, e2, e3, e4, evaluation-campaign]
links:
  - { to: coordination-eval-campaign, rel: implements }
  - { to: coordination-eval-wave2-e1-briefs, rel: depends-on }
  - { to: design-eval-seam-contracts, rel: depends-on }
  - { to: design-eval-property-tasks, rel: depends-on }
  - { to: rulings-register, rel: depends-on }
review-by: "2026-10-17"
summary: >-
  Pack part 3 (Coordinator session #7): the routing of the sixteen E2-E4 items and X-CV to harness and pinned model,
  the real DAG, the launch order by critical path, the gate state of each design, and one brief per item, plus the
  W1-K design brief. Four Sonnet items can start now (X-NG, X-SM, X-RW authoring; the X-I-S2 spike). Every external brief is written but waits on a
  design gate or an E1 join, so nothing external is compiled yet (CO-S0 runs at dispatch). W0 rev 6.6 carries the
  rulings these briefs build on: RV-TA W1-L rev 2 R2-1..R2-4, and the laundering-variant names. Coordinator #9: W1-J rev 2
  passed its gate and merged (f23d35ed), so X-J1 and X-J2 are unblocked by design; x-j1.md is re-cut on W1-J rev 2's
  final names and commit order; X-J1a and X-J2a are compiled (CO-S0); X-J1a starts only after X-D has joined, because
  X-D owns engine.py in E1. The X-I-S2 brief carries R-99's session rules.
---

# Wave 2 E2-E4 dispatch pack (part 3)

**Every rule of `docs/coordination/eval-wave2-e1/README.md` §1-§4 applies here unchanged**: start, owned paths, red first and observed, named-path commits, the shell shape, no guessing, measured fixture claims, budget, the join gate (`uv run` for `mutate_check`), the served-model read-back, and the report. That includes §2's rev 6.4 rule (**a request never parks you**: build the recommended fallback to green in its own commit) and §3's rule that the Leader checks for open requests at every join. Read that README, then this one, then your brief, then the design it names. Your brief wins over this file, and **W0** (`docs/design/eval-seam-contracts.md`, **rev 6.6 or later**) wins over a design.

**Two §2 rules added by Coordinator #13, restated here because they protect other tracks:** (1) **never kill by name, pattern or command line; only PIDs you started** (class PROC-A: X-F F2's machine-wide `pytest` kill left three other trees' mutants applied); if a run of yours is stuck and you lost its PID, stop and report, never sweep. (2) TIME-B's scan is on `main`: a new real sleep, fake delay or clock assert in `tests/` is event-driven or test-clocked, or gets **one** `TIMING_ALLOWED` entry for your own test with a checkable reason (granted to every track).

**One change to §1 step 4.** Check for W0 rev 6.6: `git log --oneline -1 --grep "W0 seam contracts rev 6.6"` must print a commit. If it does not, stop and report "W0 rev 6.6 not on main".

**Seats.** Leader `leader-e1e4` (epoch 13; merges, pushes, runs every external dispatch through `.tools/coord/runner-leader.sh`, R-87). Owner `owner-fable`. Coordinator `coord-opus-e1e4`, which runs as hand-back sessions: requests to it are answered when the Leader spawns one (E1 README §3).

## 1. Gate state (2026-10-03, Coordinator #7)

| design | gate | consequence |
| --- | --- | --- |
| W1-A arms (rev 2), W1-G catalog 0.7, W1-I security tasks | passed (E1) | X-A3, X-G3 and X-I-S2 have a design; X-A3 and X-G3 still wait on E1 joins |
| W1-L property tasks (rev 2) | **passed**, merged `c8f57b8d` (TA PWC rev 2, PAT, SIM PWC). RV-TA's R2-1..R2-5 had to be fixed before the task authors start: **done** in W0 rev 6.6 and W1-L *Erratum 1* (this branch). R2-6..R2-8 are acceptance items in the task briefs | X-RW, X-NG, X-SM, X-LG are unblocked by design; X-RS also waits on SP-LB |
| W1-J multi-turn (rev 2) | **passed**, merged `f23d35ed` (TA, PAT, SIM, SRE, DS PWC; rev 2 applies every finding; `check_models --quick` 29/29, 4/4 witnesses; Coordinator #9) | X-J1, X-J2 **unblocked by design**; each still waits on its E1 joins (§3). RW1 `ready` waits on X-J1 and X-J2b joining |
| W1-K resume, liveness, alarm | **not written**; its design brief is `w1-k.md`, dispatchable now that W1-J has merged | X-K1, X-K2 **blocked** |
| SP-LB loopback spike | script written, **not run** (`docs/notes/spike-s-lb-loopback.md`: "operator required") | X-LB **blocked** on the operator run; X-RS starts when SP-LB's result merges |

## 2. Routing (harness and pinned model, never a default)

| item | brief | session · branch | harness · model (pinned) | dispatches | brief status |
| --- | --- | --- | --- | --- | --- |
| W1-K resume design | `w1-k.md` | `w1k-resume-e1e4` · `design/eval-resume` | Claude Code · Sonnet (`model: sonnet`, served `claude-sonnet-5-5`, R-91) | one session | **written; dispatchable (W1-J merged `f23d35ed`)** |
| X-J1 multi-turn engine | `x-j1.md` | `x-j1{a..e}-e1e4` · `build/eval-x-j1{a..e}` | Codex · `gpt-6.1-sol` high (codex-cli 0.160.0), 3,600 s per turn | five turns (re-cut on W1-J §11), each red and green, each joined before the next | **written, re-cut; J1a compiled** (§6); **waits on X-D (D1 and D2), X-C, X-B2, X-B1b, X-A1a joined**; contract `x-j1.contract.json` |
| X-J2 rework grader, per-turn synthetic, multi-turn discrimination | `x-j2.md` | `x-j2{a,b}-e1e4` · `build/eval-x-j2{a,b}` | Agy · `gemini-3.8-flash-high` | two turns | **written; J2a compiled** (§6); J2a waits on X-F, X-A1a joined; J2b on X-J2a, X-E, X-LB0 (and X-J1 for its turn-1 snapshot test); contract |
| X-RW rework tasks RW1 (E2), RW2 (E4) | `x-rw.md` | `x-rw-e1e4` · `build/eval-x-rw` | Claude Code · Sonnet (R-91) | Sonnet session, then a follow-on for `ready` after X-J2 joins | **written; authoring dispatchable now** |
| X-A3 three arms, rings, readers, `_passed` fix | `x-a3.md` | `x-a3{a,b,c}-e1e4` · `build/eval-x-a3{a,b,c}` | Agy · `gemini-3.8-flash-high` | three turns | written; **waits on E1 joins** (X-A1b, X-H2); contract |
| X-G3 scenario-7 `pass_at_1`, 0.7 freeze prep | `x-g3.md` | `x-g3-e1e4` · `build/eval-x-g3` | Grok · `grok-4.7`, `--reasoning-effort high` | one turn (2,400 s), red and green | written; **waits on X-A3a** (the `_passed` fix); contract |
| X-K1 resume (engine) | `x-k1.md` | `x-k1{a..d}-e1e4` · `build/eval-x-k1{a..d}` | Codex · `gpt-6.1-sol` high | four turns | **blocked: W1-K; X-J1 joined**; contract |
| X-K2 liveness and alarm | `x-k2.md` | `x-k2{a,b}-e1e4` · `build/eval-x-k2{a,b}` | Agy · `gemini-3.8-flash-high` | two turns | **blocked: W1-K**; contract |
| X-LB0 SR-L5 property additions; X-LB1 loopback fake | `x-lb.md` | `x-lb0-e1e4`, `x-lb1-e1e4` · `build/eval-x-lb0`, `build/eval-x-lb1` | Claude Code · Sonnet (R-91; security-adjacent) | two Sonnet sessions | LB0 written, **waits on X-F**; LB1 **blocked: SP-LB operator run** |
| X-LG property graders | `x-lg.md` | `x-lg{a,b,c}-e1e4` · `build/eval-x-lg{a,b,c}` | Agy · `gemini-3.8-flash-high` | three turns | written; **waits on E1 joins** (X-F, X-D2, X-A1a) and X-J2a (`_changes`); contract |
| X-RS resilience tasks RS1, RS2 | `x-rs.md` | `x-rs-e1e4` · `build/eval-x-rs` | Claude Code · Sonnet (R-91) | Sonnet session; `ready` after X-LB | written; **waits on SP-LB's result** |
| X-NG no-guessing tasks NG1, NG2 | `x-ng.md` | `x-ng-e1e4` · `build/eval-x-ng` | Claude Code · Sonnet (R-91) | Sonnet session; `ready` follow-on after X-LG | **written; authoring dispatchable now** |
| X-SM simplicity tasks SM1, SM2 | `x-sm.md` | `x-sm-e1e4` · `build/eval-x-sm` | Claude Code · Sonnet (R-91) | Sonnet session; `ready` follow-on after X-LG and X-J2 | **written; authoring dispatchable now** |
| X-I-S2 second security task | `x-i-s2.md` | `x-is2-e1e4` · `build/eval-x-i-s2` | Claude Code · Sonnet (R-91) | spike, then RV-SEC and RV-TA review it, then authoring; `ready` follow-on after X-F and the 0.7 freeze | **written; the S2 spike is dispatchable now** |
| X-CV convergence | `x-cv.md` | `x-cv-e1e4` · `build/eval-x-cv` | Claude Code · Sonnet (R-91); the records run under the Leader | Sonnet session | written; **waits on every E2-E4 join** |

**Why authoring starts before `ready`.** A task track's exit evidence is a discrimination record through the real engine and grader (`ready`, W0 §2's flip order). Authoring the folder (base pin, prompt, hidden tests, solutions, variants, wrong-apps) needs only W0 and W1-L, so it starts now and stops at `draft`. The `ready` flip is a short Sonnet follow-on in the same tree once the grader it needs has joined (X-I's pattern in E1).

**Contracts.** As E1 (README §5): `coord-run/1`, copied from the E1 contracts of the same harness. `prompts` holds **`COMPILE-OWED:<brief path>`**; the runner refuses it (`RUN-COMPILE`). **No external brief is compiled in part 3**, because none is dispatchable now: each waits on a gate or an E1 join, and a compilation names W0's revision and the base it was read on. The Coordinator compiles each one (CO-S0) when its row in §4 turns startable, and the Leader asks for it in the same hand-back as the join that unblocks it.

## 3. The E2-E4 DAG (real dependencies only)

A track starts when its design gate has passed, its design is on `main`, and every item it depends on has **joined `main`**. "E1 done" in the campaign plan is replaced by the E1 items each track really needs.

| item | depends on (and why) |
| --- | --- |
| W1-K (design) | W1-J merged (the `.tla` files W1-K extends with `NoLaunchAfterStop` (R-100); the per-turn rows X-K1 reconciles) |
| X-J1a..e | W1-J gate ✓ (`f23d35ed`); **X-D joined, X-D1 and X-D2** (X-D owns `engine.py` in E1, its D2 dispatch being the engine recheck; edits to `engine.py` are serialised, so X-J1a starts only after X-D has joined); X-C (`status.py`, `ledger.py`, E1); X-B2 (`archive.py` E1, the snapshot primitive); X-B1b (`publish_dir`); X-A1a (`plan.py`, for `turns`) |
| X-J2a (`_changes` four functions, `drift.py` hunk) | W1-L ✓ (SR-L4, SR-L6); X-F joined (`_changes.grading_copy` hunk; `grade/runner.py` E1) and X-A1a (line 84) — the hub file's E1 writers |
| X-J2b (`rework.py`, per-turn synthetic, multi-turn discrimination, variant edit forms) | W1-J gate ✓; X-J2a; X-E joined (`discriminate.py`, `synthetic_agent.py`, `profiles.py` E1); X-J1 contract (built against fixtures until X-J1 joins; the turn-1 snapshot test needs X-J1 joined); X-LB0 (`property.hidden_tests` for `rework.grade`) |
| X-RW authoring | W1-L ✓; W0 rev 6.6 ✓ (this branch) |
| X-RW `ready` (RW1) | X-J1, X-J2b joined |
| X-A3a (`_passed` fix, ADR-0019 item 4) | W1-A ✓, W1-G ✓; X-H2 joined (`report/html.py` E1); X-A1b joined (`plan.py`, `config.py` E1 owner) |
| X-A3b, X-A3c (three arms, rings, readers) | X-A3a |
| X-G3 | W1-G ✓; X-A3a (serial spine 7: the `_passed` fix before the formal `pass_at_1` rows exist) |
| Leader `freeze_catalog.py` (R-86) | X-G3 joined |
| X-K1a..d | W1-K gate ✗; **X-J1 joined** (serial spine 6); X-D2 |
| X-K2a, b | W1-K gate ✗; X-C joined (`status.py`, `cli.py` E1); X-J1 joined (R6.5b gives X-J1 one `status.py` hunk in E2, so X-K2 rebases on it); **X-K2b only: X-K1 joined** (W0 rev 6.9: the `cmd_run` resume hunk is X-K1's, R6.9a, and `alarm.py` imports X-K1's `resume.has_work`, R-102) |
| X-LB1 | SP-LB operator run passed and merged ✗; X-LB0 |
| X-LB0 (SR-L5) | X-F joined (`grade/property.py` E1); not SP-LB |
| X-LG | W1-L ✓; X-F, X-D2, X-A1a joined (E1 hub files); X-J2a (`_changes`); X-LB0 (`property.hidden_tests`, `write_section`, `procs.run`) |
| X-RS authoring | SP-LB result merged (sections 9 are provisional on it); `ready` after X-LB |
| X-NG authoring | W1-L ✓; `ready` after X-LG (the `noguess` strategy) |
| X-SM authoring | W1-L ✓; `ready` after X-LG (`diffstats`) and X-J2b (the create edit form; `launderlines`, `laundertest` need it) |
| X-I-S2 | W1-I ✓ for the spike; RV-SEC and RV-TA on the spike note before authoring; `ready` after X-F joins and the 0.7 freeze (W1-I §4) |
| X-CV | every E2-E4 item joined; the Leader's freeze committed |

**Critical path (Inferred durations from the plan, which ran 2-14× long in phase 1):** X-D joined (W1-J's gate has passed) → X-J1 (5 turns, about 5 h) → X-K1 (4 turns, 4.5 h) → X-K2b (1 turn, about 1 h; W0 rev 6.9 puts it after X-K1, X-K2a runs beside X-K1) → X-CV (2 h + machine time). W1-K starts at W1-J's merge and runs beside X-J1, so it is off the path unless its gate takes longer than X-J1. Nearly as long: E1's X-H2 and X-A1b → X-A3 (3 turns) → X-G3 → freeze. The E4 task tracks are off the critical path if their authoring runs now.

## 4. Launch order (cap 6 running across E1 and part 3; at most 2 per external harness; critical path first)

E1 items keep priority over part 3 (E1 README §7) until X-INT. Part 3 fills free slots:

1. **Now, Sonnet (no compile):** X-NG, X-SM, X-RW (RW1 then RW2) authoring, and the X-I-S2 spike, in that order when slots free. Each stops at `draft` (X-I-S2 at its spike note) with its report.
1a. **When X-F has joined:** X-LB0 (Sonnet, short; X-J2b and X-LG need it).
2. **Now (W1-J merged `f23d35ed`):** W1-K (Sonnet design). X-J1a and X-J2a are compiled (§6, Coordinator #9).
3. **After X-D1 joins** (and X-D2, the D2 engine recheck: X-D owns `engine.py` in E1, and edits to `engine.py` are serialised, so X-J1 never runs beside an open X-D tree), **and when X-C, X-B2, X-B1b, X-A1a have joined:** X-J1a (Codex, compiled), then X-J1b..e, each joined before the next and each compiled when its predecessor joins.
4. **When X-F and X-A1a have joined:** X-J2a (Agy, compiled; it gates X-LG and X-SM's `ready`). X-J2b is compiled when X-J2a, X-E and X-LB0 have joined.
5. **When X-H2 and X-A1b have joined:** X-A3a (Agy) → X-G3 (Grok) → the Leader's freeze; X-A3b, X-A3c beside X-G3.
6. **When X-J2a has joined:** X-LG (Agy, three turns).
7. **When the operator has run SP-LB and it passed:** X-LB1 (Sonnet) and X-RS authoring (Sonnet).
8. **When W1-K passes its gate:** X-K1 (Codex) once X-J1 has joined; X-K2a (Agy) beside X-K1 (the alarm task script, its test, the runbook, `last_progress_at`; no `cli.py`, no pending logic); X-K2b once X-K1 has joined (W0 rev 6.9: the `cmd_run` hunk and `resume.has_work` are X-K1's).
9. **`ready` follow-ons (Sonnet, same trees):** X-NG after X-LG; X-SM after X-LG and X-J2b; X-RW (RW1) after X-J1 and X-J2b; X-RS after X-LB; X-I-S2 after X-F.
10. **X-CV** last.

## 5. RV-TA W1-L rev 2 conditions, by brief (the Leader's routing)

| finding | where it is fixed | acceptance item in |
| --- | --- | --- |
| R2-1 variant names and carrier; the `v-laundered` naming conflict | W0 rev 6.6 §2 (f, g), §7; W1-L Erratum 1 | X-RW, X-RS, X-NG, X-SM (names, carrier, a test through W1-E's reader); X-J2 (the create form and `turn-<n>/`) |
| R2-2 `tests.py` counted as product | W0 rev 6.6 §13 (`is_test_path(path, base_paths)`) | X-J2a (function, mutant); X-RW (RW1 fixture: `humanfriendly/tests.py` is a test path); every task track (its base's layout) |
| R2-3 laundering through a test directory | same rule; `laundertest` | X-SM (variant); X-J2a (mutant) |
| R2-4 multi-turn discrimination unowned; a cited test missing | W0 rev 6.6 §13 (X-J2 owns it); W1-L Erratum 1 (T-E11/T-E12) | X-J2b; X-RW (RW `ready` after X-J2b); X-NG (the single-turn seeded-disagreement fixture); X-LB (an RS-shaped discrimination through loopback) |
| R2-5 `cacheerror` probably not hidden-test green | W1-L Erratum 1 | X-RS (first commit) |
| R2-6 `g-ordering` schedule | W1-L Erratum 1 | X-RS (first commit) |
| R2-7 stub sentinel per task | W1-L Erratum 1 | X-RW, X-RS, X-NG, X-SM |
| R2-8 the NG primary rule | W1-L Erratum 1 | X-NG |

## 6. Findings for the Leader
- **W0 rev 6.5** (`f3f08735`) answered W1-J rev 2's three seams; **rev 6.6** (this branch) rules RV-TA W1-L R2-1..R2-4 and the laundering names. Merge rev 6.6 before any part-3 dispatch: the step-4 check above greps for it.
- **The four E1 conditions on X-J1** (E1 README §8) are now acceptance items in `x-j1.md`. R6.5a fixes "no `turn_ended` for a stopping turn"; R6.5b fixes the status clock. The budget clock and last-turn spend stay X-J1's own fixes.
- **SP-LB needs the operator** (blocker B-2). It holds X-LB and X-RS, which are off the critical path; ask for the session when convenient.
- **No compile ids in part 3.** CO-S0 runs per track when it is startable (§2, Contracts).

**Coordinator #9 (2026-10-03, base `66ec885f`, W0 rev 6.7):**
- **W1-J's gate has passed** (`f23d35ed`). `x-j1.md` is re-cut on W1-J rev 2 §11's commit order (K1..K4) and carries its final names and conditions as acceptance items: the budget clock at `turn == 1` through `lifecycle.is_cell_start`; spend summed across turns; `turn_ended` with `next` for stopping turns (R6.5a); `status.py` reads the first `prompt_sent` (R6.5b); `job_active_baseline` at turn 1's first update (R6.5c); `append_missing_rows` owned by X-J1; E2 snapshot recovery; spikes S-J4 and S-J5 run by X-J1. The deadline is 3,600 s per turn. `x-j2.md` J2b is unblocked by design and reads `snapshot_folder`/`snapshot_of`.
- **Compiled (CO-S0):** X-J1a (Codex template) and X-J2a (claude-code template; no Agy template exists, as in E1). The compile ids are in `x-j1.contract.json` and `x-j2.contract.json` (`prompts`), not here, so this README's hash in each compilation's references stays the hash of the file the worker reads. J1b..e and J2b each need their own compilation before dispatch.
- **Launch order:** X-J1a starts after X-D1 joins (and X-D2): X-D owns `engine.py` in E1, and edits to `engine.py` are serialised (§3, §4 step 3).
- **R-99 (DR-S2):** `x-i-s2.md` step 1 item 2 now carries the login-route-only, no-`bottle`/`pickle`-import, inert-bytes-only and tamper-refusal rules. W1-I §12 *Erratum 2* stays X-I's to write.
- **For the Leader:** when X-J1c and X-J1e report S-J5 and S-J4, the Coordinator updates W1-J §12's result column from the report.

**Coordinator #13 (2026-10-04, base `4561daea`):** W1-K has passed its gate (`7e96eee3`), so §1's W1-K row is out of date: X-K1 and X-K2 are unblocked by design. Nothing in this pack is dispatchable externally yet: **X-K2a** waits on X-C and X-J1 joined (`last_progress_at`, R6.5b; the script-only split is in E1 README §8, Coordinator #13); **X-LB0** waits on all of X-F (F2 and F3 still write `grade/property.py`); X-J1a, X-J2a, X-LG, X-A3, X-G3 and X-K1 wait on the E1 joins in §3. The **X-I-S2 spike redo** (Sonnet, R-99) is dispatchable now. The PROC-A and TIME-B rules above apply to every track here.
