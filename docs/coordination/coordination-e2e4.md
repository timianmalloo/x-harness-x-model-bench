---
id: coordination-e2e4
title: "Coordination plan - Evaluation Campaign E2-E4, convergence, overnight follow-ons and the pack upstream"
type: plan
status: proposed
owner: "@timianmalloo"
phase: "Enterprise evaluation: E2 (multi-turn), E3 (arms, freeze, resume, alarm), E4 (property graders and tasks), convergence; Leader epoch 18"
tags: [coordination, worktrees, parallelism, evaluation-campaign, e2, e3, e4]
links:
  - { to: coordination-eval-campaign, rel: implements }
  - { to: coordination-eval-wave2-e234-briefs, rel: depends-on }
  - { to: coordination-eval-wave2-e1-overnight-2026-10-05, rel: depends-on }
  - { to: design-eval-seam-contracts, rel: depends-on }
  - { to: rulings-register, rel: depends-on }
  - { to: defect-classes, rel: relates-to }
  - { to: coordinator-log, rel: relates-to }
review-by: "2026-10-19"
summary: >-
  Coordinator #29's plan for the rest of the Evaluation Campaign build at 839d0f4a: 14 dispatchable tracks plus 2
  operator-gated ones (X-LB1, X-RS) across Codex, Agy, Grok and Claude Code, one owner per authored file per phase with
  the joint-satisfiability check for every shared surface, a serial spine of the engine lane (X-J1 then X-K1 then
  X-K2b then X-CV), five push batches with at most two gate rings, nine struck or merged tracks, and Lane F (the
  ai-forward upstream) in its own worktree of C:\projects\ai-forward. Critical path Inferred at 15-20 h wall.
---

# Coordination plan: E2-E4, convergence, follow-ons and the pack upstream

**Goal** (the operator-approved scope prompt, compiled scope). E2, E3 and E4 built and joined on `main`, with as much parallelism as the DAG allows, minimal contention and the best cost per joined track; the pack fixes pushed to ai-forward; this plan (md + html) and a closing run report. **Done when:** every track below has joined `main` through a pushed batch with a green all-rings run (R-104); X-CV's convergence proof is committed with the ten discrimination records at the final engine identity; ai-forward carries Lane F's fixes and this repo carries them through `/updatepack`; the run report is committed and pushed. **Not in scope:** E5 and any real grid; macOS (deferred by the operator); triggering GitHub Actions; force pushes or history rewrites. **Tier:** T2. **Fan-out cap:** 6 concurrent workers, at most 2 per external harness; the Coordinator and Owner seats do not count. **Objective, lexicographic:** completeness and rigor, then token cost, then speed.

Every rule of `docs/coordination/eval-wave2-e1/README.md` sections 1-4 and of `docs/coordination/eval-wave2-e234/README.md` applies to every worker unless this plan changes it. Where they differ, the scope prompt's nine rules win; this plan encodes each one (rule n is cited as "scope rule n").

### Seats (every model pinned; never a default)

| seat | session | model (pinned) | duty | rules into |
| --- | --- | --- | --- | --- |
| Leader | `leader-e1e4` (Claude Code) | `claude-opus-5-5` | the lease, **epoch 18** (CO-L); every dispatch through `.tools/coord/runner-leader.sh` with `COORD_TREE=<integration tree>`; every merge, batch and push; the only seat that writes the primary checkout, and only to fast-forward after a push (scope rule 2) | - |
| Coordinator | `coord-opus-e1e4`, hand-back sessions #30 onward | `claude-opus-5-5` (this session read back `claude-opus-5-5`) | compiles every brief at dispatch (CO-S0); arbitrates seams; owns W0, the briefs, this plan and the defect register; one hand-back file per session under `docs/coordination/coordinator-log/` | W0; the briefs; `docs/lessons/defect-classes.md` |
| Owner | `owner-fable` (Claude Code) | `claude-fable-5-1` | rules every `coord decide request --to owner-fable` | `docs/notes/rulings.md`, now class **authored**: one ruling session at a time, written in its own worktree and merged by the Leader; the next ruling number is the one after R-106 |
| Workers | one session id per dispatch (`<track>-e1e4`) | pinned per track (Tracks) | their owned paths only | - |

**Who rules.** Every track row below rules by `owner-fable` into `docs/notes/rulings.md`. A request left unanswered for 30 minutes goes to the Coordinator, which applies the brief's recommended fallback and marks it *provisional* (the phase-1 rule; README section 2 rev 6.4: a request never parks a worker). A compiled prompt whose `dispatchable` is false, or that still carries an unanswered `DR-n` line, is refused at dispatch with `decision request unanswered: DR-n` (CO-S0). **No Owner decision is open before the first dispatch** (Coordinator #29 checked every routing change below against the briefs and W0; each one is the Coordinator's or the operator's, see Struck tracks).

## Layer state

Measured by the Leader at `839d0f4a` (Stage 1) and re-read by Coordinator #29 in this plan's tree, `C:\Projects\x-harness-x-model-bench-coord-eval-c29-plan`, at about 2026-10-05 14:35Z (`coord doctor`, exit 0; `pack-doctor.py --json`, exit 0).

| check | result | meaning |
| --- | --- | --- |
| registry | ok - 11 patterns (`.agents/artifacts.yml`) | classification is real; Stage 1 added one entry (below) |
| merge driver | effective: `coord-regen` and `coord-register` declared and registered | a merge in any tree regenerates derived files and union-merges JSONL registers |
| Stage 1 change | `.agents/log/*.jsonl: register` added | the coord ledgers the tools write in every tree union-merge; they caused merge stops overnight |
| register class | **JSONL-only** (measured by the Leader 2026-10-05 in a throwaway tree: two concurrent appends to a markdown register merged with exit 0 into a file headed "unreadable as JSONL; not merging", markers auto-committed by `git merge`) | `docs/notes/rulings.md` is back to `authored`; Coordinator entries are one file per session (`docs/coordination/coordinator-log/c<NN>.md`); README section 8 is closed to new entries. Class **REG-C** (registered by this session) |
| `coord install` | additive only; the stale `.gitattributes` lines were removed by hand | class **ATTR-A** (registered by this session); the control is a Lane F item |
| leader | `leader-e1e4`, epoch 18, 786 s left at Coordinator #29's read | every track row carries epoch 18; the renewal loop must keep running (COORD-C) |
| heartbeat | 34 sessions; newest beat 40,538 s old; 1 stalled, 0 live, 8 done | no live traffic, which is not evidence of a working layer (CTX-H) |
| requests | ok - 82 total, 0 open, 82 terminal | no open request blocks dispatch |
| lease overlap | none (0 live leases) | - |
| runner wrapper | `.tools/coord/runner-leader.sh` takes `COORD_TREE=<linked worktree>`: tested by the Leader (refuses a non-repo tree; unset behaves as before; `status` works from a linked tree) | **the first `prepare` from a linked tree is untested**. *assume:* `prepare` from the integration tree bases the worker on that tree's HEAD (`coord-runner.py:426`, cited in BASE-A). **Confirm:** at the first dispatch (order of operations 6), read the worker tree's base SHA against the integration tree's HEAD. **If false:** dispatches base on the primary's HEAD, so every batch is pushed before its dependants dispatch (one ring per dependency level), and BASE-A's upgrade trigger fires |
| worktrees | primary at `839d0f4a` = `origin/main` (Leader's read); this plan's tree; no other tree | the primary now shows two modified coord ledgers (`.agents/log/coord-opus-e1e4.jsonl`, written by `coord worktree new` from the primary as the Leader instructed, and `leader-e1e4.jsonl`). Both are class `register`; the Leader commits them |
| sessions | no coord session live (Leader) | no claim conflicts |
| doorbells | `not recorded` (pack-doctor, run here) | mail is read by polling `coord mail` at every join (COORD-B) |
| bottle clone | allowed for X-I-S2 by `.claude/settings.local.json` (Leader) | X-I-S2 is dispatchable |

**Install once, in the primary checkout. Each worktree inherits it.** `coord install` was run once in `C:\Projects\x-harness-x-model-bench`. A linked worktree shares `.git/config` and `.git/hooks`, so every tree in this plan inherits the drivers and the commit floor; `coord worktree new` printed "install NOT needed here" for this plan's tree, and `coord doctor` read the same state back here. Each worker tree runs `coord doctor` to read the inherited state; **no tree ever runs `coord install`**.

### Harness capability, as verified here

What a track needs from a delegation mechanism: its own tree and branch; the compiled brief delivered verbatim; the pinned model actually served and read back; commits confined to owned paths; a bounded attempt with a stated fallback.

| harness · mechanism | version | capability (enforced / observed-only / unsupported) | model pin and read-back | limits |
| --- | --- | --- | --- | --- |
| Codex via `coord-runner` and the Leader wrapper | codex-cli 0.160.0, codex-acp 1.12.0 | **observed-only** (Q0 `q0-e1e4`; X-A1b ran 2,669 s of 3,300 s, overnight section 3) | `gpt-6.1-sol`, effort high; served id from the native rollout record | deadline **3,300 s** (scope rule 6; the J1 contract's 3,600 is reset at compile); runner max 3,600 |
| Agy via `coord-runner` | 1.2.13 | **observed-only** (Q0; X-J2a green in 3,188 s; X-B2 red-only at 3,300 s) | `gemini-3.8-flash-high`; served id from `cli.log` | deadline 3,300 s |
| Grok via `coord-runner` | 1.0.41 | **observed-only** at the pin (Q0b, R-92); `unsupported` at Q0 (served `grok-4.6`) | `grok-4.7`, `--reasoning-effort high`; `XAI_API_KEY` removed; served id per response by `tools/grok_served_model.py`; **R-103: kill at the first response if not `grok-4.7*`, one retry** (operator, 2026-10-05) | deadline 2,400 s; **short turns only** (RUN-B: feature-sized Grok turns run out of time); the XPORT-A transport fix is a repo-local deviation until Lane F upstreams it |
| Claude Code Agent tool, Sonnet | host | **qualified fallback for every track**: edit boundary enforcing (spike S5, from `coord doctor`, not re-measured here), commit floor enforcing; Agent-tool worktree isolation `unsupported`, so workers run in `coord worktree new` trees by absolute path; never `EnterWorktree` | `model: sonnet`, served `claude-sonnet-5-5` (R-91), read back per spawn | budget per row |
| Claude Code Agent tool, Opus | host | as Sonnet | `model: opus`, served `claude-opus-5-5`: read back by this Coordinator session itself (2026-10-05) | X-PACK only |
| GitHub Copilot | - | - | - | **never a worker** |

## Artifact classes

Classification removes most of the contention, and needs no coordination at all. Every regenerate command below was run before it was written (the registry's rule); `docs-graph.py derive` ran in this tree for this plan.

| path / pattern | class | mechanism | coordination needed |
| --- | --- | --- | --- |
| `docs/docs-index.js` | derived | `python docs/ai-forward-pack/scripts/docs-graph.py derive` (run in this tree, 2026-10-05) | **none** |
| `docs/audit/audit-data.js`, `docs/audit/index.html` | derived | `python docs/ai-forward-pack/scripts/audit-log.py --root docs --project x-harness-x-model-bench render` | **none** |
| `docs/specs/harness-bench.html` | derived | `python tools/render-doc-html.py` | **none** |
| `.claude/skills/{start-benchmark,new-bench-task}/**`, `.agents/skills/{…}/**` | derived | `python tools/sync-skills.py` | **none**: edit the source and sync (X-C3b's batch-7 red edited the copies) |
| `docs/audit/audit-log.jsonl`, `docs/audit/change-log.jsonl` | register | union merge (`coord-register`) | **none**. Joins are real merges, never squash (REG-A) |
| `.agents/log/*.jsonl` | register (Stage 1) | union merge | **none** |
| `docs/notes/rulings.md` | **authored** (was `register`; REG-C) | one writer: `owner-fable`, one ruling session at a time, merged by the Leader | yes: Owner only; a concurrent ruling stops the merge visibly |
| `docs/coordination/coordinator-log/c<NN>.md` | authored, create-only, one file per session | new files never conflict | **none** |
| `docs/coordination/coordinator-log.md` (index), `docs/coordination/eval-wave2-e1/README.md` section 8 | authored, closed to appends | - | **none** (nobody appends) |
| `docs/lessons/defect-classes.md` | authored, Coordinator-owned | entries are edited in place, so `register` would corrupt them | Coordinator only; tracks report class text |
| `docs/design/eval-seam-contracts.md` (W0), `docs/design/eval-identity.md` (W1-D amendment), `docs/design/eval-multi-turn.md` section 12 (S-J4, S-J5 results) | authored, Coordinator | - | Coordinator only |
| `docs/coordination/eval-wave2-e234/*.md`, `*.contract.json`, new briefs, this plan | authored, Coordinator | - | Coordinator only |
| `bench/catalog-freeze.yaml` | authored, Leader-owned | R-86: "`bench/catalog-freeze.yaml` stays Leader-owned" | Leader only, at X-G3's join |
| `bench/discrimination/**` | authored, create-only, content-addressed | `create_once` compare-and-refuse (ADR-0016 §2a) | none beyond the per-task writer: X-I5 + the Leader (S1), X-RDY, X-RS, X-CV (the final ten) |
| `bench/campaigns/**` | authored, single writer | - | the Leader only (the E1 demo) |
| `runs/`, `.tools/` | ignored | not tracked | **none** |
| `src/**`, `tests/**`, `tasks/**`, `tools/**`, `bench/**` (other), `models/**`, `docs/**` (other) | authored | **one owner per file per phase** (hub table below) | **yes: the only real contention** |
| `C:\projects\ai-forward` `pack/**` and its tests | authored, another repository | X-PACK only, in its own worktree (the clone's primary carries other sessions' untracked files) | yes: X-PACK only |

### Hub files: one owner per file per phase (scope rule 3)

E2, E3 and E4 overlap in time here, so each row gives the owner **sequence** (each hand-over is a join into the integration tree) and any concurrent writers with the reason their hunks are disjoint. W0 section 13 stays authoritative; the rows marked **W0 rev 6.11** are the amendments Coordinator track C-W0 writes into it.

| hub file | owner sequence | concurrent writers and why it holds |
| --- | --- | --- |
| `engine.py` | X-J1 (a..e) → X-K1 (a..d) | none: lane A only (serial spine 3) |
| `status.py` | X-J1a (`build()`: the cell clock reads the first `prompt_sent`, R6.5b) → X-INTF (`text()`: the EV-18 cell id) → X-K2b (E3: `last_progress_at`, alarm, `has_work`) | none: each dispatch starts after its predecessor joined (W0 rev 6.11 row) |
| `views.py` | X-J1d (snapshot keys, final-rows filter, **`CellView.task` and `.rep`** filled in `_cell_view`; Coordinator #20) → X-K1 (`segment_rows`, `load`'s `completed`, `verify` abandoned head) and X-A3c (`CellView.pack` rename only) | K1 and A3c edit disjoint functions; both take the file from X-J1d's join; the later one rebases (W0 §13 rev 6.8) |
| `verdicts.py` | X-J1d (`_task_rep` reads the new `CellView` fields; the label regex is deleted: one definition of the label format) | none (no other E2-E4 writer) |
| `readiness.py` | X-J2b (E2: admission of a `turns` task, one function, only if needed) ∥ X-LG (E4: the HB-RDY-009 frozen-value check in `contract_failures`, in LGb or LGc; erratum, Coordinator #32: no `task_problems` exists) → X-LB1 (loopback shapes at `:277`, the property-evidence pointer switch) | J2b and LG edit different functions. *assume:* J2b's hunk, if any, is outside `contract_failures` (`readiness.py:282`). **Confirm** at J2b's compile by reading the file. **If false:** LG's hunk waits for J2b's join and rebases (W0 rev 6.11 row) |
| `grade/property.py` | the `STRATEGIES` literal (`:496`, one line today): X-J2b adds `rework`, X-LG adds its two keys; then X-LB1 (E4 owner of the rest, W0 §13) | the literal is one line, so J2b and LG conflict textually by construction: **the Leader resolves it as a union at the P2 merge** (every key kept), pre-declared like `identity.PLANNED` |
| `grade/_changes.py` | X-LG (E4) | none (J2a's E2 commit has joined) |
| `grade/runner.py` | X-J2b (`graded_snapshots` read through `archive.snapshot_folder`; W1-J §7 row 11) ∥ X-LG (E4: only a hunk W1-L names) | disjoint hunks; the later one rebases |
| `grade/formal.py`, `tasks/G2/task.yaml` (pass rule) | X-G3 | none |
| `errors.py` | X-J1a (HB-LED-008 row, `Cause.archive`) ∥ X-LGa (HB-RDY-009 text at `:68`) → X-K1a (HB-CELL-118/119, HB-RUN-008/009, **and HB-ALM-001..003 for X-K2**, W0 §11: "the phase's `errors.py` owner adds the confirmed rows in its first commit") | J1a's rows sit near `:16-30` and `:93-98`, LG's at `:68`: disjoint (read on `839d0f4a`) |
| `identity.py` | `CLASSES` already holds every planned module (`:32`, `:100`, `:112-115`, read on `839d0f4a`); `PLANNED` (`:119-122`): each landing track deletes **its own key** in its landing commit (R6.10a): X-K1 `resume.py` (`:120`), X-J2b `grade/rework.py` and X-K2b `alarm.py` (both on `:121`), X-LG `grade/noguess.py`, `grade/diffstats.py` (`:122`) | same or adjacent lines, so conflicts are certain: **the Leader resolves `PLANNED` as a union of deletions** (scope rule 3). An unplanned `src/` file is a seam request to the phase owner (X-J1 E2, X-K1 E3, X-LG E4) |
| `cli.py` | E2 window: X-INTF (campaign commands honour `--runs`; *assume:* the fix is in `cli.py`'s campaign dispatch, confirmed at compile by reading it, else it is in `campaign.py` and this row empties), X-TE9 (`cmd_validate` calls `readiness.problems`), X-K1 (the `cmd_run` resume branch, R6.9a) → X-K2b (every other E3 line) | the three are disjoint functions; K2b rebases on all three before its first `cli.py` edit (W0 rev 6.9) |
| `campaign.py` | X-INTF (`run_side_check` on a plan with no campaign block) | none |
| `report/html.py` | X-A3 (E3) → X-K2b (the resume header hunk, after X-A3c and X-K1 have joined; W0 §13 rev 6.8) | none |
| `plan.py` | X-A3a/b (E3 arms) and X-J1d (`turns` only, SR-J3) | disjoint fields; the later one rebases (A3b is planned to join before J1d) |
| `config.py`, `board.py`, `report/{pack_improvement,summaries,cli_table,context_growth}.py`, `bench/rings/pack-regression.yaml` | X-A3 | none |
| `archive.py` | X-J1 → X-K1 (`recover_archive` only) | none |
| `lifecycle.py`, `tools/check_models.py`, `models/README.md`, `docs/design/run-lifecycle-model.md` | X-J1 → X-K1 (the W1-K §8 rows) | none |
| `discriminate.py`, `synthetic_agent.py`, `profiles.py`, the variant reader | X-J2 (b, then c) | none |
| `alarm.py`, `tests/test_alarm.py`, `tests/test_report_resume.py` | X-K2b | none |
| `tools/alarm-task.ps1`, `tests/test_alarm_task.py`, `docs/runbooks/resume-and-alarm.md` | X-K2a (**W0 rev 6.11**: the script-only split; W0 rev 6.8/6.9 named them "second dispatch") | none |
| `tests/test_e1_e2e.py` (X-INT's, joined) | each landing track deletes **only its own** strict-xfail marker: X-I5 `:327`, X-INTF `:471` and `:591`, X-A3c `:525`, X-TE9 `:384`, `:391`, `:397` | distinct lines; a marker that turns XPASS is removed in the commit that makes it pass |
| `tests/test_catalog_version.py` (the property-tag strict xfail) | X-LB1, in the commit that makes `config.PROPERTY_NAMES` equal `STRATEGIES`' keys (Coordinator #15) | none |
| `tests/mutations/<module>.json` | the module's owner in that phase; for `cli.json`, each `cli.py` hunk owner retargets only its own finds | MUT-E: every worker's guard list includes `test_mutate_check`, whose `test_every_mutation_find_text_occurs_exactly_once` catches a find another track's edit moved |
| `tests/test_arms_guard.py` pins | X-A3 (lowers every count to `plan.py` only) | no other track adds a `pack`, `on` or `off` literal; one that must is a seam to X-A3 |
| `tasks/S1/**` · `tasks/S2/**` · `tasks/{NG1,NG2,SM1,SM2,RW1,RW2}/**` · `tasks/{RS1,RS2}/**` | X-I5 · X-I-S2 then X-RDY · X-RDY · X-RS | one folder per writer; `bench/bom.yaml`: each edits only its own entry |
| `bench/metrics.yaml` | X-G3, then the Leader's freeze | none |

### Guards over shared surfaces (GO14a)

Every worker runs **the standard guard list** on its skeleton commit **and** its final commit (scope rule 4; GUARD-A's upgrade, written into the brief template by C-W0): `tests/test_architecture.py`, `tests/test_identity.py`, `tests/test_atomic_sites.py`, `tests/test_arms_guard.py`, `tests/test_discriminate.py`, `tests/test_mutate_check.py`, `tests/test_skills_in_sync.py`, `tests/test_timing_hygiene.py`. Widening a guard reddens other tracks at the join; narrowing it stays green.

| shared surface | guard (quoted, with citation) | scan: root · recursion · tokens · allowlist | jointly satisfiable because |
| --- | --- | --- | --- |
| every `src/` reader of the arm | ADR-0014 §2: "No reader reads `pack` directly after this change; a guard test greps for it." (`tests/test_arms_guard.py`, G1) | root `src/harness_bench` · recursive · AST: string `Constant` `"pack"` outside docstrings, `Attribute` `pack`, `keyword(arg="pack")`; plus the arm-literal ratchet · `PACK_READERS_ALLOWED` and `ARM_LITERALS_ALLOWED` (file → pinned count, **equality**), `JS_ARM_LITERALS_ALLOWED = {"report.js": 2}` | only X-A3 moves the pins (down to `plan.py`). J1, K1, K2, J2, LG and INTF read arms only through `plan.cell_arm` / `arm_pack` and add no `pack`, `on` or `off` literal (X-H1c's `gates.py` literal is why the guard is in every list). X-A3c re-runs the pins on the merged P3 head |
| every `src/` file has a class | ADR-0017 §1: "The classification table lives in code, once, with a test that every `src/` file has a class." (`tests/test_identity.py`, G2) | root `src/harness_bench` · recursive · every file except `__pycache__/` · `CLASSES` is the table; `PLANNED`; `EXEMPT = {"cli.py"}` for the direction test; `RUN_IMPORTS_GRADE_ALLOWED` (three `config.py` pairs) | every planned module is in `CLASSES`; each landing commit deletes its `PLANNED` key (R6.10a); `resume.py` (run) imports no grade module; `alarm.py` (grade) imports `resume.has_work`, a grade → run import the rule allows (W0 §9); no fourth allowlist entry |
| the gateway import lint | "ADR-0011 C5/C9 import lint · extended to the campaign, identity, power, verdict, gate and property-grader modules" (`tests/test_architecture.py`, G3) | the files marked "yes" in W0 §9 · non-recursive · imports resolving to `harness_bench.gateway` · none | no new module needs the gateway (ADR-0020 §5, ADR-0018) |
| subprocess and ACP speakers | W0 §10 D3 (`tests/test_architecture.py`) | root `src/harness_bench` · recursive · `SUBPROCESS_CALLS`, `OS_SPAWNS`, `ACP_METHODS` · `SUBPROCESS_CALLERS = {"procs.py", "grade/bench_check.py"}`, `ACP_SERVERS = {"synthetic_agent.py"}`, driver-only ACP | X-J1's driver stays the only ACP client; `tests/fake_acp_agent.py` is under `tests/`; X-LG's resolver child runs through `procs.run` (SR-L5, landed by X-LB0); X-K2a's script is outside `src/` |
| atomic write sites | W0 §13 rev 4 (`tests/test_atomic_sites.py`) | root `src/harness_bench` · recursive `*.py` · rename/replace/link/copytree verbs · `ALLOWED` keyed `(file, function, verb)` | J1's snapshots go through `atomic.publish_dir`, K1's recovery through `archive.append_missing_rows`: no new site. A new site is a seam request to the Coordinator (X-B1 has closed) |
| real-time dependence in tests | TIME-B (`tests/test_timing_hygiene.py`) | root `tests/` · recursive, skipping `fixtures`, `vendor`, `mutations`, `__pycache__` · `CLOCKS = {monotonic, time, perf_counter}`, `FAKE_PARAMS = {sleep, delay}` · `TIMING_ALLOWED` | each track may add **one** `TIMING_ALLOWED` entry for its own test with a checkable reason (granted to every track, part-3 README header); K1's and K2's kill-then-resume and alarm tests use test clocks |
| generated skill copies | `tests/test_skills_in_sync.py` | `.claude/skills`, `.agents/skills` · recursive · byte equality with the source | the only expected editors are X-K2b (status fields in `start-benchmark`) and X-PACK's `/updatepack`; both edit the source and run `tools/sync-skills.py` |
| mutation finds | MUT-E (`tests/test_mutate_check.py::test_every_mutation_find_text_occurs_exactly_once`) | `tests/mutations/*.json` · every `find` occurs exactly once in its file | a track retargets every find its own edit moves, in any mutation file, and names them in its report; the Leader runs `mutate_check --touched` once per batch with `HB_REQUIRE_DOTNET=1` |
| stored-plan readers | T-E19 (`tests/test_discriminate.py`, the exact reader set) | not a scan; an exact set | a track that adds a reader of stored plans (J2b's multi-turn path, K1's resume) adds itself to the set in its own commit as a pre-granted hunk (precedent `d67efccc`) |
| "exists means complete" | ADR-0015 §5a: "copy into a temporary sibling folder (`<name>.tmp-<pid>`), fsync the files and the folder, verify the rows against the copy, then `os.rename` it to the final name" | not a scan | J1 publishes snapshots through `publish_dir`; K1's `recover_archive` returns `append_missing_rows`' result and holds no second comparison (DM7) |
| the launch recheck | ADR-0017 §7: "The engine recomputes the run-side part of the manifest when a campaign run starts and again before each `cell.launch_intent`" | not a scan | J1 and K1 keep the `identity_check` call before each `cell.launch_intent`; its key set is the stamp's (R-106, W0 rev 6.11) |
| the alarm | ADR-0021 §7: "`bench status <run_id> --alarm-after <seconds>` exits non-zero, naming the cause, when the heartbeat is stale **or** `now − last_progress_at` exceeds the threshold while cells are pending" | not a scan | K2b; "pending" is only `resume.has_work` (X-K1, R-102) |

## Tracks

**Pins (every row; never a default):** Codex = `gpt-6.1-sol` effort high on codex-cli 0.160.0. Agy = `gemini-3.8-flash-high` on 1.2.13. Grok = `grok-4.7` `--reasoning-effort high` on 1.0.41, `XAI_API_KEY` removed. Sonnet = Agent tool `model: sonnet`, served `claude-sonnet-5-5`. Opus = `model: opus`, served `claude-opus-5-5`. **Every track's fallback is Claude Code Sonnet in the same tree** (R-87 Option 1). Every row carries **leader epoch 18** and rules by **`owner-fable`** into `docs/notes/rulings.md`.

**Budgets are Inferred** (calls · context per dispatch · dispatches · wall). Overnight measurements (section 3 of the report): Sonnet tracks ran at 0.2-1.0 times plan; externals ended at their deadlines twice in four turns (RUN-B). Planned and actual are recorded per track (GO19).

**Common exit evidence (the worker gate, scope rule 4; R-104):** red-first commits failing on an **assertion** (a skeleton's neutral values must fail by assertion, not `KeyError`: RED-C, registered as a TEST-B shape; a test that already passes is recorded "green on arrival", never faked red); the worker's **own named test files** green; the standard guard list on the skeleton and final commits; `uv run python tools/mutate_check.py` on **its own mutation file only, never `--touched`**; `uv run ruff check src tests tools`; `python docs/ai-forward-pack/scripts/docs-graph.py validate`; the served model read back and recorded. **The whole suite is the Leader's**, once per batch. The Leader re-runs at least one red SHA per track at the join; a green report is not evidence its contents passed.

| track | owns (authored) | depends on | tier | fan-out cap | budget | exit evidence | harness |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **X-J1** multi-turn engine (a..e) | `driver.py`, `engine.py` (E2), `archive.py` (E2), `lifecycle.py`, `ledger.py` (E2), `views.py` (E2, incl. `CellView.task`/`.rep`), `verdicts.py` (`_task_rep` only), `errors.py` (E2), `identity.py` (E2), `plan.py` (`turns` only), `status.py` (`build()` hunk), their tests, `tests/fake_acp_agent.py`, `tests/test_archive_readers.py`, `tests/mutations/{engine,driver}.json` | every E1 join (on `main`: X-D, X-C, X-B2, X-B1b, X-A1a); W1-J ✓ `f23d35ed`; each turn joined before the next | T2 | 0 | 320 · 200k · 5 · 5 h | `x-j1.md` acceptance 1-10 by named test (T-ENG-*, T-DRV-*, T-SNAP-*, T-VER-*, T-LIF-*, T-PLAN-*, T-STATUS-1, T-SWEEP-1, T-WIRE-1); every §11 mutant killed; S-J5 (J1c) and S-J4 (J1e) measured or reported "not run" with the reason; `verdicts` regex deleted with a test that a label built by `plan.Cell.label` and the fields agree | Codex |
| **X-K1** resume engine (a..d) | `resume.py` (new, run), `engine.py` (E3), `errors.py` (E3 incl. HB-ALM-001..003), `identity.py` (E3), `lifecycle.py` (E3), `archive.py` (`recover_archive`), `views.py` (K1 functions), `cli.py` (the `cmd_run` hunk only), `docs/design/run-lifecycle-model.md` and `models/README.md` rows, `tests/test_resume.py`, `tests/test_engine.py` (E3), `tests/mutations/{engine,resume}.json` | **X-J1 joined** (all five); W1-K ✓ `7e96eee3`; X-D2 ✓ | T2 | 0 | 280 · 200k · 4 · 4.5 h | `x-k1.md` acceptance 1-6: kill-then-resume for every ADR-0021 §4 row; HB-RUN-008 exit 3 after a stop; W2, W3, W3b, W6, W11 and `test_resume.py::test_cli_run_resumes[T2]` green through the real CLI; `resume.has_work` red-first tests (`test_finished_stop_is_silent`, `test_alarm_fires_after_crash_in_grading`, `test_alarm_fires_after_crash_before_last_archive`, `test_launch_stop_alarms`) | Codex |
| **X-K2** liveness and alarm: K2a (script-only split), K2b | K2a: `tools/alarm-task.ps1`, `tests/test_alarm_task.py`, `docs/runbooks/resume-and-alarm.md`. K2b: `status.py` (E3), `cli.py` (E3 except K1's hunk), `alarm.py` (new), `report/html.py` resume header hunk, `tests/test_status.py` (E3), `tests/test_alarm.py`, `tests/test_report_resume.py`, own mutation entries | K2a: **W0 rev 6.11 merged** (the split). K2b: X-K1, X-A3c, X-INTF, X-TE9 joined | T1 | 0 | K2a 40 · 100k · 1 · 0.7 h; K2b 110 · 150k · 1 · 1.5 h | K2a: the four W0 rev 6.8 conditions and R6.9b: `test_push_failure_does_not_print_topic` red on a script without the catch; two runs in a row send once; the unset-topic line; runbook with V2 frontmatter. K2b: `x-k2.md` acceptance 1, 2, 4 (ADR-0021 §7 fixture exits non-zero; HB-ALM-003 warning; mutant M-ALARMPENDING killed; "stopped, n cells never launched"); report goldens byte-identical for a run with no `run.resumed` | K2a Grok; K2b Agy |
| **X-A3** three arms, rings, readers (a, b, c) | `board.py`, `report/pack_improvement.py`, `report/html.py` (E3), `report/summaries.py`, `report/cli_table.py`, `report/context_growth.py`, `views.py` (`CellView.pack` rename only), `plan.py` (E3), `config.py` (E3), `bench/rings/pack-regression.yaml`, `tests/test_arms_guard.py` pins, the `:525` marker in `tests/test_e1_e2e.py`, their tests and goldens | X-A1b ✓, X-H2 ✓; A3b after A3a joined; **A3c after A3b and X-J1d joined** (`views.py` hand-over) | T2 | 0 | 240 · 200k · 3 · 3.5 h | `x-a3.md`: A3a red on a cell with no `pass_at_1` read as failure, no 0.6 golden moves (W1-G F7; a moved hash is a stop); A3b EV-17 under 5 % and HB-PLN-003 naming the differences; A3c board per comparison pair, legacy goldens unchanged, G1 allowlist at `plan.py` only with equality pins, the `:525` pack-effect leg passes | Agy |
| **X-G3** scenario-7 `pass_at_1`, 0.7 freeze prep | `grade/formal.py`, `tasks/G2/task.yaml` (pass rule only), `tests/fixtures/catalog/0.7/**`, `tests/test_grade_formal.py` | **X-A3a joined** (serial spine 4) | T2 | 0 | 80 · 120k · up to 3 · 1.2 h | red on a fixture G2 cell with no `pass_at_1`; the US-4 control grades grid-3 and grid-4 fixtures under 0.7 with every 0.6 value unchanged (before/after golden hashes in the report; a move is a stop); `tools/grok_served_model.py` exit 0 per response. The Leader runs `python tools/freeze_catalog.py` at the join (R-86) | Grok |
| **X-J2** rework grader and multi-turn discrimination: J2b, then J2c | J2b: `grade/rework.py` (new), `grade/runner.py` (E2 hunk), the `STRATEGIES["rework"]` key, `profiles.py` (E2), `discriminate.py`, `synthetic_agent.py` (E2), the variant reader function, `readiness.py` (E2 admission hunk, if needed), the `PLANNED` key, `tests/test_rework.py`, the two-turn profile case. J2c: the multi-turn discrimination test through X-J1's engine and the turn-1 snapshot test | J2b: X-J2a ✓, X-E ✓, X-LB0 ✓ (built against X-J1's record contract with fixtures). **J2c: X-J1d joined** (engine loop, snapshots, `plan.turns`) and J2b joined | T2 | 0 | J2b 110 · 180k · 1 · 1 h; J2c 60 · 150k · 1 · 1 h | `x-j2.md` J2b items: `rework_ratio` on the turn-1 snapshot and the final tree; per-turn overlays; the create edit form and `turn-<n>/` prefix, one test and one refused case each; R2-4: a two-turn fixture task gets a discrimination record matching its `expected` (in J2c) | J2b Agy, **planned red-only on the engine leg** with J2c as the Sonnet green follow-on from the start (scope rule 6) |
| **X-LG** no-guessing and simplicity graders (a, b, c) | `grade/noguess.py` and its resolver child, `grade/diffstats.py`, `grade/_changes.py` (E4), `grade/runner.py` (E4), `errors.py` (E4), `identity.py` (E4 keys), `readiness.py` (HB-RDY-009 check), the two `STRATEGIES` keys, their tests | E1 ✓, X-J2a ✓, X-LB0 ✓; each turn joined before the next | T2 | 0 | 180 · 180k · 3 · 3 h | `x-lg.md`: `hallucinated_symbol_errors` by the static resolver, a resolver failure is NA with its reason (never 0); `verified_before_use` NA `not built` (R6-9); `size_vs_reference`, `new_abstractions`, `new_dependencies`, `outside_radius_lines`; EV-6 no line counted twice with `scope_creep`; mutants "drop clause (a)/(b)" killed; HB-RDY-009 red on a hand-edited frozen value | Agy |
| **X-I5** S1 fix (F4 drop and NA declarations) | `tasks/S1/**` (the check's payload set: keep A0, B2, B3, C0, drop the other nine; `expected.reference` declares NA for `behavioural_equivalence` and `regression_count`; a new task version), the `:327` marker in `tests/test_e1_e2e.py` | none (operator decisions (2), 2026-10-05) | T2 | 0 | 60 · 150k · 1 · 1 h | S1's own tests green at the new task version; `bench validate` EV-1 clean for S1; the `:327` pilot-gate leg passes with its marker removed; leave-one-out evidence updated. **Then the Leader** runs `uv run bench discriminate S1` (credentials removed) and commits S1 `ready` with its record in one commit | Sonnet |
| **X-I-S2** second security task (authoring) | `tasks/S2/**`, its BOM entry, `tools/spikes/s2_apps.py`, `tools/spikes/s2_probes.py` (`x-i-s2.md` authoring section) | none; the bottle clone at `cbd569c4` is allowed; `build/eval-x-i-s2c` carries no commits of its own, so the tree is made fresh from the integration head | T2 | 0 | 150 · 200k · 1 · 3 h | stops at `draft`: EV-1 fields valid; reference passes its hidden tests; naive passes the functional tests and fails a probe through the real probe host; R-99's rules (login route only, no `bottle`/`pickle` import, inert bytes, tamper refusal) | Sonnet |
| **X-RDY** the `ready` flips | `tasks/{NG1,NG2,SM1,SM2,RW1,RW2,S2}/task.yaml` (status and measured `expected` corrections, with the author's evidence) and their records under `bench/discrimination/**` | X-LG (LGc), X-J2 (J2c), X-J1 (J1e) joined; the 0.7 freeze committed (S2, W1-I §4) | T2 | 0 | 200 · 200k · 1 (a second session past the cut line) · 3 h | per task, a real-host discrimination record that reproduces `expected` (W1-L §5.3, W1-I §4), committed with the flip; a task that does not reproduce stays `draft` with the measured numbers in the report (never an edited `expected` without its evidence) | Sonnet |
| **X-INTF** X-INT's follow-ons | `campaign.py` (`run_side_check`), `status.py` (`text()` hunk), the campaign `--runs` fix (`cli.py` or `campaign.py`), the `:471` and `:591` markers in `tests/test_e1_e2e.py`, their tests and own mutation entries | **X-J1a joined** (`status.py` order) | T1 | 0 | 80 · 150k · 1 · 1.5 h | the three strict-xfail legs pass with their markers removed; a campaign command given `--runs <dir>` reads that dir (test through `cli.main`); `run_side_check` refuses or labels a plan with no campaign block | Sonnet |
| **X-TE9** strict `bench validate` | `cli.py` (`cmd_validate` line), the `:384`, `:391`, `:397` markers, `tests/test_cli.py` hunk | X-RDY joined (the six draft tasks left draft) **and the operator's T-E9 release** | T1 | 0 | 40 · 100k · 1 · 0.7 h | `bench validate` reports readiness problems (HB-RDY-*) through `readiness.problems`; the three legs pass. *assume:* a `ready` task whose record predates a later `src/` join is not an error without `--baseline`. **Confirm** at compile by reading `readiness.problems`. **If false:** X-TE9 joins after X-CV's final records, on the critical path (+0.7 h). **Checked (Coordinator #44): false.** `readiness.record_key` hashes every `src/harness_bench` file, `bench/bom.yaml` and `uv.lock` (`identity._readers`), so any later `src/` or BOM join is HB-RDY-002 without a campaign baseline; measured at `e5355996`, `readiness.problems` on the repository prints four x lines (HB-RDY-002 S1, S2, SM2; HB-RDY-001 SM1). **Amended (Coordinator #44):** the markers are now `:380`, `:387`, `:393`; the row gains `readiness.pass_rule_problems` and its call in `problems()` with a `tests/test_readiness.py` test (#34's finding) and `validate --campaign`; budget 60 · 100k · 1 · 0.7 h. The build may dispatch now; the join point is the Leader's (the If-false above, or earlier with `ci.yml:29` and `check_regrade` P3 red on stale records until X-CV) | Sonnet |
| **X-CV** convergence | `tests/test_resume_table.py`, `docs/proof/eval-campaign-convergence.md`, `bench/discrimination/**` (the final ten, run by the Leader) | every track above joined, X-LB1 and X-RS included; the freeze committed | T2 | 0 | 120 · 180k · 1 · 2 h + machine time | `x-cv.md` 1-4: the whole ADR-0021 §4 table; TLC with every ADR-0015 §7 invariant and `NoLaunchAfterStop`; ten records at the final `identity_hash`; `bench validate` reports all ten `ready`; planned against actual per track. **Amended:** CI is read if it runs, never triggered; macOS deferred by the operator | Sonnet |
| **X-PACK** Lane F: the ai-forward upstream, then `/updatepack` here | ai-forward `pack/**` sources and tests for the ten items in *Lane F* below (item 10 added by Coordinator #42), in `C:\Projects\ai-forward-fix-xh-e2e4-upstream`; then this repo's pack-managed paths in `C:\Projects\x-harness-x-model-bench-coord-pack-update-e2e4` | phase 1: none; phase 2: the Leader's ai-forward push | T2 | 0 | 250 · 350k · 1 session (two trees) · 4 h | phase 1: each item red first in ai-forward's tests, `/extendaibundle`'s consistency steps, `tools/verify-bundle.ps1` exit 0. Phase 2: `pack-apply.py`'s action table; `coord doctor` reads back; `tests/test_skills_in_sync.py` and the transport tests green; `docs/notes/deviation-coord-transport-grok-session-new.md` marked retired | Opus |
| *gated* **X-LB1** loopback fake | `grade/property.py` (E4), `grade/bench_check.py` (E4), `readiness.py` (loopback shapes, pointer switch), the `property.json` pointers `check.hosts`, `check.clauses`, `check.deliverable`, `check.cases` (Coordinator #19), the property-tag marker, `tests/test_property_loopback.py` | **SP-LB passed (operator, B-2)**; X-LG joined | T2 | 0 | 160 · 180k · 2 · 2.5 h | EV-3 parallel-port isolation; listeners bind literal `127.0.0.1` and assert `getsockname` (HB-CHK-005); hang is measured | Sonnet |
| *gated* **X-RS** resilience tasks | `tasks/RS1/**`, `tasks/RS2/**`, their BOM entries | authoring: SP-LB's result merged; `ready`: X-LB1 joined | T2 | 0 | 200 · 200k · 2 · 4 h | EV-1, EV-3; R2-5 and R2-6 in the first commit; the reference 1 and the naive 0 through the engine; records committed with the flips | Sonnet |

### Track assignment detail

| track | sessions · branches | why this harness and model | expected seam requests | deadline · termination · fallback | compile status (CO-S0, at dispatch) | join batch · gate ring |
| --- | --- | --- | --- | --- | --- | --- |
| X-J1 | `x-j1{a..e}-e1e4` · `build/eval-x-j1{a..e}` | long, deep, serial engine work: the scope's Codex profile; qualified at 0.160.0 | S-J4 read point (a W0 amendment, to the Coordinator, only if measured); T-E19 reader-set entry (pre-granted) | 3,300 s per turn · each turn ends at a commit, red then green · red-only or a failed read-back: Sonnet green follow-on | **J1a RECOMPILE**: `al-01M41TVHN76EXTN73R66S2Q1HM` (Coordinator #9, base `66ec885f`, W0 rev 6.7) predates every E1 join, R-104's worker gate and `CellView.task`/`.rep`; J1b..e each compiled when its predecessor joins | J1a P1; J1b, J1c P2; J1d, J1e P3 · no `grade/` file: pays no gate ring |
| X-K1 | `x-k1{a..d}-e1e4` · `build/eval-x-k1{a..d}` | engine owner in E3, same profile | `views.py` hunks against X-A3c (disjoint by W0) | 3,300 s · as X-J1 · as X-J1 | **COMPILE-OWED**; the Coordinator writes the turn split from W1-K's test map at J1e's join, then compiles K1a | P4 · none |
| X-K2 | `x-k2a-e1e4` · `build/eval-x-k2a` (new Grok contract); `x-k2b-e1e4` · `build/eval-x-k2b` | K2a is a short bounded script turn: Grok's profile, and the scope's candidate; K2b is a bounded multi-file slice: Agy | K2b: HB-ALM rows from X-K1 (W0 §11), the resume header after X-A3c | K2a 2,400 s with R-103's first-response kill and one retry; K2b 3,300 s · as X-J1 · Sonnet | **both COMPILE-OWED**; K2a after W0 rev 6.11 merges (needs a Grok contract copied from `x-g3.contract.json`'s harness block) | K2a P1 or P2; K2b P4 · none |
| X-A3 | `x-a3{a,b,c}-e1e4` · `build/eval-x-a3{a,b,c}` | bounded multi-file report slices; the cheapest external | "absence read as failure" class text (A3a, to the Coordinator) | 3,300 s · as X-J1 · Sonnet | **COMPILE-OWED** (A3a now; A3b, A3c at each predecessor's join) | A3a P1 (joined at once: X-G3 waits); A3b P2; A3c P3 · none (no `grade/` file; checked against `tools/gate_stamp.py` inputs) |
| X-G3 | `x-g3-e1e4` · `build/eval-x-g3` | catalog-sized short turn; G1b and B1a committed green inside 2,400 s | none | 2,400 s · R-103 kill and one retry · Sonnet after R-92's review | **COMPILE-OWED** at A3a's join | P2 · **pays the P2 gate ring** (with the freeze) |
| X-J2 | `x-j2b-e1e4` · `build/eval-x-j2b` (Agy); J2c in the same tree (Sonnet) | J2b: bounded multi-file slice; J2c: R-87 Option 1 for the leg that needs X-J1's engine | `STRATEGIES` union and `PLANNED` union (pre-declared); T-E19 entry | J2b 3,300 s; J2c budget · J2b ends red-only on the engine leg by plan · Sonnet | **J2b COMPILE-OWED** (`x-j2.contract.json` holds J2a's `al-01M44PHDX8QPNF0K3HP1VB8X6G`); J2c compiled at J1d's join | J2b P2; J2c P3 · J2b pays P2's ring; J2c is planned test-and-`discriminate.py`-only, so a `grade/` fix it needs moves to the next ring |
| X-LG | `x-lg{a,b,c}-e1e4` · `build/eval-x-lg{a,b,c}` | bounded grader modules; Agy | `STRATEGIES`, `PLANNED` unions; `readiness.py` order against J2b | 3,300 s · as X-J1 · Sonnet | **COMPILE-OWED** (LGa now) | P2 (all three turns) · **pays the P2 gate ring** |
| X-I5 | `x-i5-e1e4` · `build/eval-x-i5` | task authoring: the Sonnet seat | none | budget · stops at its exit evidence or budget with a report · a fresh Sonnet session | **brief to write** (`x-i5.md`, Coordinator #30, from `x-i.md` and operator decision (2)), then compile | P1 · none (S1 is not a gate-stamp input; `tools/gate_stamp.py` reads `grade/**`, `tasks/D1`, `bench/metrics.yaml`, `bench/regrade-baseline-0.3.yaml`) |
| X-I-S2 | `x-is2c-e1e4` · `build/eval-x-i-s2c` | task authoring; security-adjacent (R-91) | RV-SEC, RV-TA reviews already done on the spike (`18bdce7e`, `e2af2692`) | budget · as X-I5 · as X-I5 | brief exists (`x-i-s2.md`); **compile at dispatch** | P1 or P3, whichever it is ready for · none |
| X-RDY | `x-rdy-e1e4` · `build/eval-x-rdy` | short follow-ons of the task authors' work | a task that does not reproduce `expected` (to its author's brief owner, the Coordinator) | budget · cut line: past budget, the remaining tasks go to a fresh session | **compile at dispatch** from the `ready` sections of `x-ng.md`, `x-sm.md`, `x-rw.md`, `x-i-s2.md` | P4 · none |
| X-INTF | `x-intf-e1e4` · `build/eval-x-intf` | follow-on work: the Sonnet seat | none (X-C has closed; X-INT's legs name the fixes) | budget · as X-I5 · as X-I5 | **brief to write** (`x-intf.md`, Coordinator #30, from X-INT's three xfail reasons) | P2 · none |
| X-TE9 | `x-te9-e1e4` · `build/eval-x-te9` | one-line wiring and test markers | none | budget · as X-I5 · as X-I5 | **brief to write** at X-RDY's join | P4 · none |
| X-CV | `x-cv-e1e4` · `build/eval-x-cv` | integration; the records run under the Leader | none | budget · as X-I5 · as X-I5 | brief exists (`x-cv.md`); compile at dispatch with the amended CI line | P5 · a gate ring only if the digest moved since P4's stamp |
| X-PACK | `lanef-e1e4` · ai-forward `fix/xh-e2e4-upstream`; here `coord/pack-update-e2e4` | edits the coordination engine (merge driver, runner, transport) that every consuming repo inherits; the class measured in Stage 1 (REG-C) shows a defect there commits conflict markers silently: rigor first, so Opus | none in this repo; ai-forward findings go in its own register | budget · stops at its exit evidence or budget · a fresh Sonnet session from the brief | **brief to write** (`x-pack.md`, Coordinator #30), then compile | phase 2 joins P5 · none |
| X-LB1, X-RS | `x-lb1-e1e4`, `x-rs-e1e4` · `build/eval-x-lb1`, `build/eval-x-rs` | security-adjacent; task authoring | X-LB1 → X-LG `readiness.py` order | budget · as X-I5 | `x-lb.md`, `x-rs.md` exist; compile when B-2 clears | P4 if B-2 clears in time, else a P4b batch · X-LB1 **pays a gate ring** (`grade/property.py`) |

Doorbell status for every row: `not recorded` (pack-doctor); the Leader reads worker mail at every join.

### Why each track earns the multiplier (GO6: about 15 times the tokens of one session)

- **One session cannot hold this.** X-J1 alone is five dispatches at 200k each; the whole plan is about 40 dispatches. **Context hygiene** pays for every split, and phase-scoped Coordinator hand-backs keep the seat under its ceiling.
- **Machine-time parallelism** is the main return: external turns run 45-55 minutes each on their own harnesses, and the engine lane is serial for 10 turns, so everything off it (A3, G3, J2, LG, INTF, I5, I-S2, PACK) runs inside the engine lane's wall time at no cost to the critical path.
- **Genuine independence:** X-A3 ∥ X-J1 (disjoint files until A3c's `views.py` hand-over); X-LG ∥ X-J2b (disjoint except the two pre-declared unions); X-I5, X-I-S2 (one task folder each); X-PACK (another repository).
- **Isolation:** Codex runs `agent-full-access`; every external worker has its own tree; X-PACK works in its own ai-forward worktree because that clone's primary carries other sessions' untracked files.
- **Federation is a requirement** of the scope, not a saving; each external dispatch has a Sonnet fallback, so a harness failure costs one re-dispatch, not the plan.

### Harness-slot schedule (cap 6 workers; at most 2 per external harness; times Inferred from T0)

T0 is the first dispatch after this plan merges and the T0 compiles land (Inferred ≈ 2026-10-05 09:00 local, 16:00Z). One external turn plus its join is taken as about 65 minutes (X-A1b 2,669 s, X-J2a 3,188 s, joins about 15 minutes).

| window (h from T0) | Codex 1 | Codex 2 | Agy 1 | Agy 2 | Grok 1 | Grok 2 | Sonnet / Opus | workers |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 - 1.3 | J1a | idle | A3a | LGa | - | - | X-I5, X-I-S2, X-PACK | 6 |
| 1.3 - 2.6 | J1b | idle | J2b | LGb | G3 | - | X-I-S2, X-PACK | 6 |
| 2.6 - 3.9 | J1c | idle | A3b | LGc | K2a | - | X-INTF, X-PACK | 6 |
| 3.9 - 5.2 | J1d | idle | - | - | - | - | X-I-S2 if still open | 1-2 |
| 5.2 - 6.5 | J1e | idle | A3c | - | - | - | J2c | 3 |
| 6.5 - 11.4 | K1a..K1d | idle | - | - | - | - | X-RDY, then X-TE9; X-LB1 and X-RS when B-2 clears | 2-4 |
| 11.4 - 12.5 | - | idle | K2b | - | - | - | - | 1 |
| 12.5 - 15 | - | - | - | - | - | - | X-CV | 1 |

Codex 2 stays idle: no Codex-shaped track is off the engine lane, and moving an Agy track there does not shorten the plan (Struck tracks). The cap binds only in the first four hours; afterwards the DAG does, as it did overnight (section 6 of the report).

### Batch plan (joins into the integration tree; pushes per batch; gate rings)

A **join** is a `--no-ff` merge into the integration tree `integrate/e2e4-18` (its own `coord worktree new` tree, the Leader's only writing tree besides the primary's fast-forward), followed by `coord regen`, the red-SHA re-run, the guard list and `docs-graph.py validate`. A **push** is a batch of at most 6 tracks, after one all-rings run on the batch head (`HB_REQUIRE_DOTNET=1`, `-rs` read), `mutate_check --touched` once with `HB_REQUIRE_DOTNET=1`, and a gate-stamp check or renewal. The gate ring (77-81 min, measured) runs only when the stamp's inputs moved: `src/harness_bench/grade/**/*.py`, `tasks/D1`'s version hash, `bench/metrics.yaml`, `bench/regrade-baseline-0.3.yaml` (read from `tools/gate_stamp.py:3-9`). A renewal computes its digest under SUITE-LOCK, and no mutating job runs in a tree whose renewal is pending (scope rule 5; MUT-A's stamp shape).

| batch | tracks (≤ 6) | ready at (Inferred) | gate ring | why grouped |
| --- | --- | --- | --- | --- |
| P1 | X-J1 (J1a), X-A3 (A3a), X-I5 + the Leader's S1 `ready` commit, X-K2 (K2a, if ready), X-I-S2 (if ready), C-W0 docs | T0 + 2 h | **no** (no input moved) | lands S1 `ready` and the `_passed` fix early; nothing waits on the push itself, because dispatches base on the integration tree |
| P2 | X-G3 + the Leader's freeze, X-J2 (J2b), X-LG (a, b, c), X-A3 (A3b), X-J1 (J1b, J1c), X-INTF | T0 + 5.5 h | **yes, once** (`grade/` and `bench/metrics.yaml`) | every `grade/` join of the run except X-LB1 in one ring; the freeze rides it. The real-data E1 demo becomes possible after this push |
| P3 | X-J1 (J1d, J1e), X-A3 (A3c), X-J2 (J2c), X-I-S2 (if not in P1) | T0 + 7 h | no, unless J2c needed a `grade/` fix | the E2 engine closes; X-K1 bases on it |
| P4 | X-K1 (a..d), X-K2 (K2b), X-RDY, X-TE9, X-LB1 and X-RS if B-2 has cleared | T0 + 12.5 h | only if X-LB1 is in it | E3 closes. If B-2 clears late, X-LB1 and X-RS form P4b with their own ring |
| P5 | X-CV and its final records, X-PACK phase 2 (`/updatepack`) | T0 + 15 h | only if the digest moved since P4 | the final engine identity; the pack update rides the last all-rings run, when no external dispatch is live |

Expected gate rings: **two** (P2, and P4 or P4b for X-LB1). The overnight run paid three rings for seven batches.

## Serial spine

| item | why it cannot be parallel (GO5) | who owns it |
| --- | --- | --- |
| 0. The lease (epoch 18) stays alive; the Leader reads mail and runs the health check (stop above 1,500 processes or on an AppModel-Runtime 208/212 event) at every dispatch and join | every runner dispatch checks the live designation; an expired lease stops all dispatch (GO5(c): one exclusive resource) | Leader |
| 1. This plan merges, then the integration tree is created and the first `prepare` from it confirms the Q0 *assume:* | until the dispatch base is proven, every dependent dispatch's base is a guess (GO5(c), BASE-A) | Leader; Coordinator records the result |
| 2. C-W0: W0 rev 6.11 (R-106 c4 §6 key set, the c7 reader key-set sweep, the K2a split, the §13 rows this plan adds), the W1-D Amendment note, GUARD-A's guard list in the brief template | a vocabulary change: every compile after it reads it (GO5(b)); one author | Coordinator (hand-back session) |
| 3. `engine.py` and its lane: X-J1a → J1b → J1c → J1d → J1e → X-K1a..d → X-K2b | one author on `engine.py` at a time (W0 §13); each J turn builds on the last; K's per-turn rows read J's merged events (GO5(a) data edge); K2b imports K1's `has_work` and rebases on K1's `cmd_run` hunk | Codex workers; Coordinator compiles each at its predecessor's join |
| 4. The freeze: X-A3a's `_passed` fix → X-G3 → the Leader's `freeze_catalog.py` | ADR-0019 item 4 must precede the formal `pass_at_1` rows; R-86 keeps the freeze file Leader-owned and orders it after X-G3 (operator kept the plan order) | Leader |
| 5. `status.py`: J1a's `build()` hunk → X-INTF's `text()` hunk → X-K2b | scope rule 3's order; one writer at a time on a hub file | Coordinator (dispatch order) |
| 6. The S1 record: X-I5 → the Leader's `bench discriminate S1` → one commit with S1 `ready` | the record is keyed by task version and engine identity; the flip without its record is the defect W1-I §5.5 forbids | Leader |
| 7. X-RDY → X-TE9 | the operator held T-E9 "until the six draft tasks leave draft" | Leader (with the operator's release) |
| 8. X-CV last: the ten records at the final engine identity, then P5 | a record is keyed by engine identity (ADR-0016 §4); any `src/` change after it supersedes it | Coordinator (check); Leader (records, push) |
| 9. `/updatepack` here after the Leader's ai-forward push, inside P5 | it replaces pack scripts, hooks and skills that live dispatches and the runner use; only P5 has no live external run | Leader (merge); X-PACK (author) |
| Loop-back | any `src/` change after its track joined (an E2E, demo or record finding) reopens a small fix track under that phase's hub owner, with a red SHA; **three loop-back slots** are budgeted (about 100 calls each; overnight needed one fix per batch in four of seven batches) | Coordinator |

### Critical path (Inferred)

J1a recompile (0.3 h) → J1a..J1e (5 × 65 min ≈ 5.4 h) → K1a compile (0.3 h) → K1a..K1d (4 × 65 min ≈ 4.3 h) → K2b (1.1 h) → X-CV (2 h + about 0.5 h of records + the final all-rings run, 14 min, plus a gate ring only if the digest moved) ≈ **13.5-15 h**. With RUN-B's measured rate (two red-only external ends in four turns overnight, each adding a 20-30 minute Sonnet follow-on) and SUITE-LOCK waits behind the gate ring: **15-20 h wall**. This is a model: the inputs are the overnight durations, not a measurement of these tracks; phase-1 estimates ran 2-14 times off. **The RS chain can extend it:** SP-LB → X-LB1 ∥ X-RS authoring → X-RS `ready` takes about 3.5-5 h, so SP-LB must clear by about T0 + 9 h to stay off the critical path.

## Seams

| from -> to | the request | resolved by |
| --- | --- | --- |
| X-J2b -> X-J1 | the turn record, `archive.snapshot_folder`, `archive.snapshot_of`, `plan.tasks.<id>.turns` | fixed in W1-J rev 2; J2b builds against fixtures; J2c runs the real path after J1d joins |
| X-K1 -> X-J1 | the per-turn rows read `turn_ended{k}`, `turn_snapshot_archived{k}`, `prompt_sent{k}`; `append_missing_rows` | serial spine 3 |
| X-K2b -> X-K1 | `resume.has_work`; the `cmd_run` hunk; the HB-ALM rows in `errors.py` | K1 writes all three (W0 rev 6.9 §12, §13; W0 §11); K2b dispatches after K1 joins |
| X-K2b -> X-A3c | the resume header hunk in `report/html.py` | W0 §13 rev 6.8: after X-A3c and X-K1 have joined |
| X-A3c -> X-J1d | the `views.py` hand-over for the `CellView.pack` rename | A3c dispatches after J1d joins |
| X-LG ∥ X-J2b | the `STRATEGIES` literal; `identity.PLANNED` lines 121-122; `readiness.py`; `grade/runner.py` | pre-declared unions resolved by the Leader at the P2 merge (Read, then Edit, then a marker scan before any add; scope rule 9); disjoint functions for the rest |
| X-INTF -> X-J1a | `status.py` order | X-INTF dispatches after J1a joins |
| X-INTF, X-TE9, X-K1 -> X-K2b | `cli.py` hunks before K2b's | K2b rebases on all three (W0 rev 6.9) |
| X-LB1 -> X-LG | `readiness.py` (E4 second owner), the resilience `STRATEGIES` key, the property-tag marker | X-LB1 starts after X-LG joins |
| every landing track -> `identity.PLANNED` | delete its own key | R6.10a; no request needed |
| X-I5, X-INTF, X-A3c, X-TE9 -> `tests/test_e1_e2e.py` | remove its own strict-xfail marker | pre-granted in this plan; distinct lines |
| a reader of stored plans -> T-E19 set | add itself | pre-granted (precedent `d67efccc`) |
| X-J1c, X-J1e -> Coordinator | S-J5 and S-J4 results | the Coordinator updates W1-J §12's result column from the report; a moved read point is a W0 amendment |
| X-K2a -> W0 | the script-only split | C-W0 writes it in rev 6.11 before K2a dispatches |
| X-G3 -> Leader | the freeze | the Leader runs `python tools/freeze_catalog.py` at the join (R-86) |
| X-PACK -> Leader | the ai-forward push; the `/updatepack` branch | the Leader pushes ai-forward from X-PACK's tree; the update joins P5 |
| any track -> Coordinator | a defect class ("absence read as failure" from A3a, others) | reported as text; the Coordinator commits `docs/lessons/defect-classes.md` |
| any track -> Owner | a decision outside its brief | `coord decide request --to owner-fable`; the brief's fallback stands until ruled |

## Struck tracks

| track | why it was not worth its multiplier |
| --- | --- |
| Three separate `ready`-flip follow-ons (NG, SM, RW), plus a fourth for S2 | merged into **X-RDY**, one Sonnet session after J1e, J2c and LGc join. The interim records are superseded by X-CV's final ten anyway; the flips catch task defects before X-CV, which is all they buy. One grounding instead of four; no critical-path effect (X-RDY ends hours before X-CV can start) |
| Three separate X-INT follow-ons | merged into **X-INTF**: one Sonnet session, three small hunks in X-C's closed files |
| Re-routing an Agy track (X-LG) to the idle second Codex slot (scope Lane C's proposal) | **not proposed to the Owner: it does not shorten the plan.** The critical path is the engine lane (about 13.5-15 h); all Agy work (seven turns) fits two Agy slots in about 6 h beside it, and X-LG's chain ends hours before X-RDY needs it. A Codex turn costs more tokens than an Agy turn (Inferred: per-track spend is not recorded), so the re-route would buy speed off the critical path at a token cost, which the objective forbids. **Revisit trigger:** two Agy turns end red-only, or Agy fails a served-model read; then a DR to `owner-fable` for the next LG or A3 turn |
| A separate W1-D amendment session, a separate GUARD-A template edit, and a separate K2a W0 edit | merged into **C-W0**, one Coordinator hand-back session: all three are Coordinator-owned docs that every later compile reads |
| A worker track for the S1 discrimination record | the Leader runs it (59 s measured overnight) in the same commit as the S1 flip; no worker earns that |
| One Lane F track per upstream item (nine items; ten from Coordinator #42) | **one track** (the scope says so, and the items share one bundle-consistency proof, `verify-bundle.ps1`) |
| A separate `/updatepack` track | phase 2 of X-PACK in a second tree; the author of the upstream change applies it, which keeps the deviation retirement checked by the person who wrote the fix |
| A separate X-A3d for the `CellView.pack` rename if J1d is late | A3c simply dispatches after J1d joins; A3b → A3c has slack (A3c is not on the critical path) |
| T-E9 now | operator-held until the draft tasks leave draft; X-TE9 is planned behind X-RDY, not now |

**Honest count:** 14 dispatchable tracks (X-J1, X-K1, X-K2, X-A3, X-G3, X-J2, X-LG, X-I5, X-I-S2, X-RDY, X-INTF, X-TE9, X-CV, X-PACK) and 2 operator-gated (X-LB1, X-RS). The Simplifier merged or struck the nine candidates in the table above. Fewer is not right here: every remaining track either sits on the engine lane, holds a file no other track may write in its phase, waits on a different join, or runs on another harness or repository.

## Order of operations

| # | action | cost | why now |
| --- | --- | --- | --- |
| 1 | Leader confirms epoch 18 with `coord leader who`; the renewal loop runs. **No `coord leader pin`**: the Leader already holds the lease | 1 min | CO-L: every row carries epoch 18 |
| 2 | Leader reviews and merges this plan (`coord/eval-c29-plan`) through an integration tree, pushes it after its rings, fast-forwards the primary, and commits the two primary ledgers | 20 min | the plan is the contract `/execute-with-coordination` parses |
| 3 | Leader creates `integrate/e2e4-18` with `coord worktree new` (never `coord install`; `coord doctor` there) and deletes the stray `integrate/b3-stage` (conflict markers, never merged; operator default (6), 2026-10-05) | 5 min | scope rule 2: seats never write the primary |
| 4 | **Coordinator #30 (hand-back): T0 compiles.** Recompile J1a (Codex template, deadline 3,300 s, R-104 worker gate, `CellView.task`/`.rep`, `verdicts._task_rep`); compile A3a and LGa (claude-code template, as E1); write and compile `x-i5.md`, `x-intf.md`, `x-pack.md`; compile X-I-S2. Each compilation names W0 rev 6.10 and the integration head it read | 45 min | CO-S0: never dispatch an uncompiled or stale brief |
| 5 | **Coordinator #31 (in parallel): C-W0** (serial spine 2) | 60-90 min | K2a and every later compile read it |
| 6 | **T0 dispatch** (cap 6; health check first): J1a (Codex; **the first `prepare` with `COORD_TREE=integrate/e2e4-18`: read the worker's base SHA and record the Q0 result**), A3a, LGa (Agy), X-I5, X-I-S2 (Sonnet), X-PACK (Opus; served id read back) | 15 min of Leader time | the longest chain first; then the demo path (A3a → G3 → freeze, S1); then the longest Agy chain |
| 7 | Joins as each lands. A3a is joined at once (X-G3 waits on it). X-I5 joined → the Leader's S1 record run and the S1 `ready` commit | 15 min per join | serial spines 4 and 6 |
| 8 | Wave 2 as slots free (priority: J1 > G3 > LG > J2b > K2a > X-INTF > A3b): J1b (compiled at J1a's join), G3 (Grok, at A3a's join), LGb, J2b, K2a (after C-W0 merges), X-INTF (after J1a joins), A3b | as table | starts each track the moment its dependencies join |
| 9 | **P1 push** (T0 + about 2 h) | 14 min non-gate rings + mutations | lands S1 `ready` and the `_passed` fix |
| 10 | The Leader pushes X-PACK's ai-forward branch from its tree once `verify-bundle.ps1` is green (never from `C:\projects\ai-forward`'s primary) | 10 min | Lane F phase 1 done; phase 2 waits for P5 |
| 11 | **P2 push** (T0 + about 5.5 h): one gate ring with stamp renewal under SUITE-LOCK; the freeze rides it | 80 min ring + 14 min | every `grade/` join but X-LB1 in one ring |
| 12 | J1d, J1e; A3c and J2c after J1d; **P3 push** (T0 + about 7 h); Coordinator compiles K1a from W1-K's test map at J1e's join | as table | E2 closes; K1 bases on it |
| 13 | X-RDY; K1a..d; X-TE9 after X-RDY and the operator's release; X-LB1 ∥ X-RS when B-2 clears | as table | E3 and E4 close |
| 14 | K2b; **P4 push** (T0 + about 12.5 h) | 14 min (+ 80 if X-LB1) | E3 closes |
| 15 | X-CV; the Leader runs the ten final records; X-PACK phase 2 merges; **P5 push**; the run report (md + html) committed and pushed; `coord worktree cleanup` (report only; removal opt-in) | 3-4 h | Done when |
| 16 | The E1 demo walk with the operator (B-3), any time after P2: the Leader re-runs `bench discriminate S1` at the demo head first (the S1 record is identity-keyed, so it is stale after J1b/J1c) | 59 s + the walk | the real-data demo the operator asked for |

### Operator actions (with the date each is needed by; local time, UTC-7)

| action | needed by | gates | recommended default |
| --- | --- | --- | --- |
| **B-2: run SP-LB** with the operator present (`tools/spikes/s_lb_loopback.py`; watch for the firewall dialog) | **2026-10-05 18:00** to keep X-RS off the critical path (T0 + 9 h, Inferred). Each hour later moves X-CV an hour; 2026-10-06 09:00 puts X-CV at about 2026-10-06 13:00 | X-LB1, X-RS, and so X-CV | run it this afternoon |
| **B-3: the E1 demo walk on real data** | any time after P2 (Inferred ≈ 2026-10-05 15:00) | nothing downstream | 2026-10-05 evening or 2026-10-06 morning |
| **T-E9 release** | when X-RDY joins (Inferred ≈ 2026-10-05 18:30) | X-TE9, and so X-CV's "`bench validate` reports all ten ready" | release: the condition you set (the draft tasks leave draft) is then met |
| **ntfy topic** (R-102, user variable `HB_ALARM_NTFY_TOPIC`) | before the first unattended E5 run (not in this plan); optional live smoke at K2b's join (≈ 2026-10-05 21:30) | X-K2's drill (out of scope) | set it before E5 |
| Grok routing on grok.com (SERVE-A) | optional, before G3 (≈ 2026-10-05 10:30) | nothing: R-103's kill and one retry covers it | check when convenient |
| ai-forward push | none: approved 2026-10-05 | - | - |

### Operator decisions, 2026-10-06 about 07:45 (made by the operator in person; restated by Coordinator #44)

The operator's words, answering the Leader's five numbered questions: "1: I can do that now" (then, after the run, "Accept for this host"), "2: release", "3: waive it for now", "4: yes", "5: yes". The bold lines below are Coordinator #44's restatements, not quotes (QUOTE-A).

1. **"B-2 / SP-LB closed: accepted for this host."** The spike ran with the operator at the screen, 07:44-07:59: three loopback runs and two positive-control runs, no dialog on any run. Loopback `exchange_ok` true, 0 new rules; positive control `exchange_ok` true, 0 new rules; `--mode report`: "INCONCLUSIVE control did not fire". Cause, measured: `Get-NetFirewallProfile` shows the firewall Enabled on Domain, Private and Public with `NotifyOnListen` False on all three. Results: `docs/notes/spike-s-lb-loopback.md`; ADR-0018 Amendment 2. **X-LB1 and X-RS are unblocked** (the B-2 row above is closed).
2. **"X-TE9 is released"** (all draft tasks are now ready: S1, S2, SM1, SM2, NG1, NG2, RW1, RW2). The T-E9 row above is closed.
3. **"S-J4 is waived for now (adapter builds, credentials and spend)."** Recorded in W1-J section 12 and the register (OPER-A). W1-J section 4.4's `assume:` stays open; the waiver does not confirm it.
4. **"The `-n 4` per-join recount is approved for measurement."** The Leader edits `docs/coordination/join.json`; the Coordinator records it. At `2a24e989` the `recount` command carries no `-n`.
5. **"S2 ships with its open items:** the A6 different-author clause and the two untested controls (cookieless-401, bob-get)." This is the operator's decision on the question Coordinator #39 raised for the Owner. S2's own evidence (`tasks/S2/oracle/evidence.md:118-128`) is not edited here: the folder is inside S2's task version hash (`plan.task_version_hash`), so an edit there makes S2's record stale (HB-RDY-001). The decision is recorded here and in `c44.md`; the evidence line rides S2's next re-record (X-CV's final records).

**Consequences for the tracks (Coordinator #44):** X-TE9, X-LB1 and X-RS are compiled (`c44.md`). X-TE9's `assume:` is **false** (its row). X-RS's authoring needs only decision 1; its `ready` flips still need X-LB1 joined.

### Lane F: the ai-forward upstream (X-PACK)

- **Tree.** From `C:\projects\ai-forward`: `python docs/ai-forward-pack/scripts/coord-core.py worktree new --branch fix/xh-e2e4-upstream --session lanef-e1e4 --base main` (`origin/main` = `4a22f12` at Coordinator #29's read). The clone's primary carries ten untracked or modified paths of other sessions (`git status --short`, read here) and five other worktrees, so **nothing is edited, staged or checked out in `C:\projects\ai-forward` itself**. *assume:* the ai-forward copy of `coord-core.py` (`docs/ai-forward-pack/scripts/coord-core.py`, present) supports `worktree new` as this repo's does. **Confirm:** its output prints the tree path. **If false:** `git -C C:\projects\ai-forward worktree add ..\ai-forward-fix-xh-e2e4-upstream -b fix/xh-e2e4-upstream origin/main`.
- **Method.** `/extendaibundle` for each item, sources under `pack/**`; red first in ai-forward's own tests; `tools/verify-bundle.ps1` exit 0 on the final commit.
- **Items.**
  1. The Grok `session/new` race fix in `coord_transport.py` (`docs/notes/deviation-coord-transport-grok-session-new.md`, XPORT-A).
  2. The verify-gate findings (HYG-VERIFY): a file-level exemption for byte-exact captured records; the relative-glob false positive in `verify-no-machine-paths`; the fix text that names `python3` on Windows.
  3. Runner support for a dispatch base other than the invoking checkout (BASE-A's pack half).
  4. MUT-A's session-start `--check-clean` control, as a generic hook that runs a repo-declared check command.
  5. A gate-stamp rule: a renewal computes its digest under the suite lock, where it generalises (MUT-A's stamp shape, this session).
  6. **REG-C's control:** `coord doctor` refuses a `register` entry on a non-`.jsonl` path, and `merge-register` exits non-zero instead of writing a marker file.
  7. **ATTR-A's control:** `coord install` reconciles `.gitattributes` (removes merge attributes the registry no longer declares).
  8. PRIM-A's control where it generalises: an edit guard that refuses writes under the primary checkout's path from non-Leader sessions (KILL-GUARD's shape).
  9. The staged-markers control (GATE-B instance, this session): a pre-commit and pre-merge-commit scan that refuses staged conflict markers.
  10. **FALLBACK-A's control (added by Coordinator #42, 2026-10-06):** `prompt-compile.py`'s render leaves out the contract slot's `fallback` field (`CONTRACT_KEYS` at `:49-50`, rendered at `:507-508`), and the runner's worker brief does the same (`coord-runner.py:457` writes `fallback` into `<session>.brief.json`). A Leader-only fallback must never reach the worker's prompt. X-K1a's Codex worker carried it out and launched Claude Code sessions itself.
- **Phase 2.** After the Leader's push: `coord worktree new --branch coord/pack-update-e2e4 --session lanef-e1e4 --base <integration head>` in this repo; `/updatepack` from the pushed ai-forward revision; retire the transport deviation; join in P5.

## Status

| | |
| --- | --- |
| **Completed** | layer read back in this tree (`coord doctor`, `pack-doctor`); every dependency checked against `main` at `839d0f4a` (contracts' compile ids, task statuses, `identity.PLANNED`, `STRATEGIES`, `errors.py` rows, the gate-stamp inputs, the E1 E2E strict-xfail legs, the ai-forward clone's state); this plan; twelve register entries in `docs/lessons/defect-classes.md` (six new candidates, six instances of existing classes); `docs/coordination/coordinator-log/c29.md` |
| **Remaining** | the Leader's review and merge; C-W0; the T0 compiles; every track; B-2, B-3 and the T-E9 release (operator) |
| **Best next action** | The Leader merges this plan, creates `integrate/e2e4-18`, and spawns Coordinator #30 for the T0 compiles and #31 for C-W0 in parallel; then `/execute-with-coordination` dispatches row 6 |
