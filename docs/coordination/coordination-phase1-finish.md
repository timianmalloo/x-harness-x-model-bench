---
id: coordination-phase1-finish
title: "Coordination plan - finish harness-bench phase 1 (pre-merge findings, N5, mutation bar, E2E)"
type: plan
status: proposed
owner: "@timianmalloo"
phase: "Phase 1 · walking skeleton"
tags: [coordination, worktrees, parallelism, phase-1]
links:
  - { to: design-phase1-walking-skeleton, rel: implements }
  - { to: design-run-lifecycle-model, rel: relates-to }
review-by: "2026-10-08"
summary: >-
  Finish phase 1 with the pre-merge gate cleared. Five parallel fix tracks own disjoint files: engine, ledger and
  verify, process edges, surfaces, and the Codex N5 spike. Each runs its own red-first commits and mutation testing.
  The sub-agents run on Grok (subscription) and Agy, under an Opus 5.5 Coordinator and a Fable Owner (ruling R-1).
  Joins happen in completion order, then comes a serial close: the real E2E ("usable"), then the Proof Pack and
  re-review ("merge-ready").
---

# Coordination plan: finish phase 1

**Goal:** the benchmark is usable: `bench plan → run → status → report → verify → teardown` on real harnesses, with the pre-merge hard veto cleared.

There are two milestones, so the Owner gets a working benchmark even if the merge-ready work slips:

| milestone | what it takes |
| --- | --- |
| **M1 "usable"** | all tracks joined, and the real 4-cell E2E green on the joined branch |
| **M2 "merge-ready"** | the Test Architect's veto cleared and `main` fast-forwarded and pushed |

**Done when (M2):**
1. The Test Architect's three conditions hold:
   - the tamper tests have a recorded red commit and are green;
   - mutation is measured on ledger, engine, errors, views and the graders, with every survivor dispositioned in the mutation record;
   - the E2E ran for real and the Proof Pack is committed, holding the findings→tests map.
2. Every Major from the Python-developer, SRE and Simplifier reviews is fixed with a red-first test, or ruled out in writing by the Owner.
3. The US-13 canary is green for both harnesses, or the Owner rules on N5 (see T5).
4. `main` is fast-forwarded to `impl/phase1` and pushed.

**Not in scope:** phase 2 (Copilot, stop, decisions), the judged and statistics metrics, and any new metric or UI beyond the review findings.

**Starting point:** `impl/phase1` at `c44dd2b`, in worktree `C:\Projects\x-harness-x-model-bench-spike-runner-path`. 297 tests pass (non-credential), ruff is clean, and slices 9–14 are committed.

The pre-merge review returned:

| reviewer | verdict |
| --- | --- |
| Test Architect | BLOCK (hard veto) |
| Simplifier | soft BLOCK |
| Python developer | pass with conditions |
| SRE | pass with conditions |

The US-13 canary ran for real on 2026-09-24:
- Claude Code is clean.
- Codex: the operator's `~/.agents/skills` reached the cell (N5). A per-cell `USERPROFILE`/`HOME` did not stop it, so that change was reverted, and the Codex case is `xfail(strict)`.

## Seats

| seat | who | model | rules into |
| --- | --- | --- | --- |
| Owner | Fable | `claude-fable-5-1` | `docs/notes/rulings.md` (register) |
| Coordinator (leader) | Opus 5.5 | `claude-opus-5-5` | this plan; step 3; the joins; T7 |
| Sub-agents | Grok and Agy instances, one per track | per track (Tracks table), from `agy models` and `grok models` (subscription login), 2026-09-24 | their track's owned paths only |

**Ruling R-1 (Owner, 2026-09-24, verbatim):** "use grok, and agy for sub agent tasks · use the Owner (fable), Coordinator (opus 5.5), Sub.Agent (right model for the right job and delegate to instances of grok and agy)". This is why the sub-agents run on grok and agy even though Claude Code is the only harness whose edit boundary is qualified here.

The Tech Lead and the Simplifier recorded a dissent: put the critical-path track T1 on Claude Code. The plan keeps R-1 and adds a fallback. If a harness fails qualification at step 2, or a track on it stalls through the kick ladder, that track moves to a Claude Code sub-agent (Opus 5.5), and the Coordinator records the move.

**Decision requests:** every track raises them with `coord decide request --to owner-fable`. A request left unanswered for 30 minutes goes to the Coordinator, who applies the plan's recommended option and records it as provisional.

## Layer state

| check | result | meaning |
| --- | --- | --- |
| registry | ok - 10 patterns (read from the primary checkout, 2026-09-24) | classification is real. `coord` keeps its record per repository in the primary checkout, so the registry is also present there, untracked and identical to the committed copy |
| merge drivers | `coord-regen` and `coord-register` registered in the shared git config. `git check-attr` from the worktree returns `coord-regen` for derived files and `unspecified` for source | a merge in any worktree regenerates derived files. `doctor` run from the primary reads `main`'s `.gitattributes` and reports "none" until `main` fast-forwards |
| pre-commit floor | installed. Advisory until `AGENT_SESSION` is set ("advisory: AGENT_SESSION is unset", seen on commit `c44dd2b`) | every track sets `AGENT_SESSION=<track>`, which makes the commit boundary enforcing |
| leader | none designated | step 1 pins the Coordinator |
| heartbeat, requests, doorbells | not recorded | no traffic yet. This is not evidence of a working layer (CTX-H) |
| edit boundary: claude | enforcing (spike S5) | the fallback harness for any track |
| edit boundary: grok 1.0.30, agy 1.2.3 | **unsupported**: never exercised here, and `doctor` has no rows for them. The launch reference names a Grok 1.0.34 compatibility path, but 1.0.30 is installed | step 2 qualifies each transport with one smoke turn. Until then, only the commit floor enforces ownership |
| python | `python3` is the Store alias here; `python` is 3.12.10 | every command in this plan says `python` |
| grok auth | `XAI_API_KEY` is set in this environment, and grok picks it ("You are using XAI_API_KEY"). With it removed: "You are logged in with grok.com", the Owner's subscription, default `grok-4.7`. Both checked 2026-09-24 | **every grok worker launches with `XAI_API_KEY` removed from its environment.** Subscription models: `grok-4.7`, `grok-4.7-build-fast`, `grok-4.6`, `grok-4.5` |
| mutmut on Windows (probe R13) | not run (design line 413) | step 2 runs it: native first, then WSL. Mutants of Windows-only code (Job Objects, procs, the engine's kill path) cannot run under WSL, so the record counts them as survivors (below) |

**Install once, in the primary checkout. Each worktree inherits it.** `coord install` was run once, in `C:\Projects\x-harness-x-model-bench`. A track worktree runs `coord doctor` to read the inherited state back, and never runs `coord install`.

## Artifact classes

| path / pattern | class | mechanism | coordination needed |
| --- | --- | --- | --- |
| `docs/docs-index.js` | derived | `python docs/ai-forward-pack/scripts/docs-graph.py derive` (ran, exit 0) | **none** |
| `docs/audit/audit-data.js`, `docs/audit/index.html` | derived | `python docs/ai-forward-pack/scripts/audit-log.py --root docs --project x-harness-x-model-bench render` (ran, exit 0) | **none** |
| `docs/specs/harness-bench.html` | derived | `python tools/render-doc-html.py` (ran, exit 0) | **none** |
| `.claude/skills/{start-benchmark,new-bench-task}/*`, `.agents/skills/{…}/*` | derived | `python tools/sync-skills.py` (ran, exit 0) | **none** |
| `docs/audit/audit-log.jsonl`, `docs/audit/change-log.jsonl`, `docs/notes/rulings.md` | register | union merge | **none** |
| `runs/`, `.tools/` | ignored (`.gitignore`) | not tracked | **none** |
| `src/harness_bench/**`, `tests/**`, `bench/**`, `tools/**`, `docs/**` (other) | authored | one owner per file (Tracks table) | yes: one owner per file |

## Rules every track follows

1. **Red first, recorded.** Each finding's test lands in a test-only commit before its fix. The track's findings→tests map records, per finding:
   - the test node id;
   - the red commit's SHA;
   - the failing line from that run.

   A reviewer re-runs the test at that SHA. A finding with no test node and no red SHA is not closed.
2. **Mutation, on the hardened checker.** New guards get `tests/mutations/*.json` entries. At step 3, `tools/mutate_check.py` is hardened to require pytest exit 1 with the named node among the failures, so a collection error or timeout no longer counts as a kill. Tracks validate their entries against the hardened checker only.
3. **The mutmut record** (T1 and T2, for their modules) states the commit SHA it ran on, and classifies every mutant as one of three:
   - **killed**;
   - **survived**, which then needs a new test or a disposition;
   - **not-exercised-on-platform**, which counts as a survivor unless it is run natively.

   An *equivalent mutant* disposition carries the mutant diff and a one-line argument. No timeout or suspicious mutant may stay open. The Test Architect approves the list at re-review.
4. **Exit gate.** The whole non-credential suite and ruff are green on the track branch, merged with the current `impl/phase1`.
5. **Environment.** Each session sets `AGENT_SESSION=<track>`. Grok sessions run with `XAI_API_KEY` removed.

## Tracks

| track | owns (authored) | depends on | tier | fan-out cap | budget | exit evidence | harness |
| --- | --- | --- | --- | --- | --- | --- | --- |
| T1 engine-hardening | `src/harness_bench/engine.py`, `src/harness_bench/errors.py`, `src/harness_bench/lifecycle.py`, `tests/test_engine.py`, `tests/fake_acp_agent.py`, `tests/test_lifecycle_conformance.py`, `tests/test_errors.py`, `tests/mutations/engine.json`, `docs/notes/mutation-record-t1.md` (new) | step 3 | T2 | 0 | 450 tool calls · 6M tokens · 8–12 h (Inferred) | the T1 checklist, each item with a red SHA; `tests/mutations/engine.json` killed under the hardened checker; mutmut record for `engine`, `errors` and `lifecycle`; suite green | agy · `claude-opus-4-6-thinking` (fallback: Claude Code, Opus 5.5) |
| T2 ledger-verify | `src/harness_bench/ledger.py`, `src/harness_bench/views.py`, `src/harness_bench/grade/**`, `tests/test_ledger.py`, `tests/test_views.py`, `tests/test_grade.py`, `tests/test_verify.py` (new), `tests/archived_runs.py`, `tests/fixtures/ledger/**` (new), `tests/mutations/{views,grade}.json`, `tests/mutations/ledger.json` (new), `docs/notes/mutation-record-t2.md` (new) | step 3 | T2 | 0 | 350 tool calls · 4M tokens · 5–7 h (Inferred) | see the T2 exit list below; suite green | grok (subscription) · `grok-4.7` |
| T3 process-edges | `src/harness_bench/driver.py`, `src/harness_bench/procs.py`, `src/harness_bench/telemetry/**`, `src/harness_bench/host.py`, `tests/test_driver.py`, `tests/test_procs.py`, `tests/test_telemetry.py`, `tests/fixtures/acp/**` | step 3 | T2 | 0 | 250 tool calls · 3M tokens · 4–6 h (Inferred) | see the T3 exit list below; suite green | agy · `gemini-3.1-pro-high` |
| T4 surfaces | `src/harness_bench/status.py`, `src/harness_bench/plan.py`, `src/harness_bench/cli.py`, `src/harness_bench/config.py`, `src/harness_bench/report/**`, `tests/test_status.py`, `tests/test_plan.py`, `tests/test_report.py`, `tests/test_config.py`, `tests/test_cli.py`, `tests/mutations/{status,report,cli}.json` | step 3 | T1 | 0 | 200 tool calls · 2.5M tokens · 3–5 h (Inferred) | see the T4 exit list below; suite green | grok (subscription) · `grok-4.6` |
| T5 n5-spike | `bench/profiles/codex.yaml`, `src/harness_bench/profiles.py`, `tests/test_profiles.py`, `tests/e2e/test_us13_canary.py`, `docs/notes/spike-n5-codex-skill-roots.md` (new) | none | T1 | 0 | 120 tool calls · 1.5M tokens · research timebox 1.5 h, whole track 3 h | a spike note with a mechanism **observed** in Codex 0.156 (source or run) that removes user skill roots from a cell; the Codex canary green with its `xfail` removed; the Claude canary still green. **On timeout:** a decision request to the Owner with three options (below) | grok (subscription) · `grok-4.7-build-fast` (research, then one credentials run on this host) |
| T7 e2e-proof-close | `tests/e2e/test_walking_skeleton.py`, `tests/e2e/conftest.py`, `tools/mutate_check.py` (step 3), `docs/proof/**` (new), `docs/design/**`, `docs/lessons/defect-classes.md`, `docs/notes/a6-start-benchmark-golden-cases.md` and its replies, `docs/notes/mutation-record-phase1.md` (new, compiled from T1 and T2), `README.md` | the joins | T2 | 1 (the re-review) | 80 tool calls · 1.5M tokens · 2–3 h | see the T7 exit list below | Coordinator (Claude Code, Opus 5.5) |

**T1 checklist** (each item needs a red SHA):
1. A budget kill after the turn has ended no longer records `timed_out`. `a.ended` is set before `_end_process`, under a per-cell lock that also guards terminate against close.
2. A failure after seed or spawn always ends the process, closes the job and cleans the credential copy. `argv_env` runs before `seed`. Test the T-CELL-credclean spawn-failure variant (`missing_exe=True`).
3. A failure after the outcome writes an archive-failed fact, and the run does not report complete.
4. After the ledger breaks, the queued futures fail and draining continues. No worker blocks forever.
5. `record()` validates the canonical form on the worker side. Only a write or fsync `OSError` breaks the run.
6. `turn_usage` entries are summed per model before they are recorded.
7. One stop path runs on the engine thread. It appends `run.launch_stopped` once, and workers request it.
8. HB-RUN-002 is logged once, after `kill_escalation`, with capped backoff (T-FI-unkillable, through the procs fault seam).
9. `engine.log` keeps whitelisted extras (detail, pids, fact, win32_error).
10. A heartbeat runs during the grading hook.
11. The outcome records `updates` and `last_update_ms`.
12. ENOSPC maps to `Cause.disk`. The disk floor also checks `run_dir`'s volume, and the outcome is recorded before the best-effort files.
13. A new code, HB-RUN-005, means "run lock held". HB-RUN-003 stays "teardown refused".
14. T-LOG-nosecret: the fake agent echoes the credential; it is absent from `engine.log` and status, and present in the archive.
15. Fault tests: T-ENG-suspend (an injected clock), T-JOB-daemon, T-ARC-full.
16. Conformance transitions come from one source of truth: by default, a transition table in `lifecycle.py` that the engine consults. An AST scan is allowed only with a one-line reason why the table cannot work. Every seeded case asserts its rule name.
17. Simplifier minors inside engine.py: delete `process_alive` and `read_events`; remove the dead `archive_file` literal.

**T2 exit list:**
- The tamper probes exit 5 through `bench verify`, with a red SHA: cut the seal and last row of a completed pass; delete a fact's segments. The tests go in `tests/test_verify.py`.
- `grading.completed` gains `heads`, and verify checks every completed pass's and every completed run's heads and seals.
- D2 hypothesis properties: append then verify round-trips; any byte change, cut or insert is detected; a torn tail is handled at any offset.
- D6 golden ledger fixtures:
  - one ledger produced at `c44dd2b`, before `heads`, that must still verify;
  - one produced after the change;
  - every row type (events, model_calls, tool_calls, archive_files, scores);
  - expected hashes and row counts committed separately;
  - a tampered copy of each fixture that must exit 5.
- The ledger survivors (second-writer guard, seal count, bytes after the seal) are killed.
- Mutmut record for `ledger`, `views` and `grade/**`.
- Simplifier minors: merge `busy_ms` and `_has_duration` into one span rule; one `TurnUsage.from_row`.

**T3 exit list:**
- D5: the recorded ACP transcripts are replayed through the driver. Each fixture records its adapter version, capture date and scrub.
- D7: the emitted set is built from real fake-agent runs. The fidelity test is seeded with one unpaired type and must fail on it.
- D2: ACP line-reader bounds, and the T-TEL fuzz (100,000-deep nesting included).
- A failed `QueryInformationJobObject` raises (through the fault seam).
- `procs.run` leaks nothing on an unconfirmed kill.
- `_meta` is kept when `usage` is absent.
- The native reader is bounded on a newline-free file.
- T-TEL-missing gives HB-TEL-001.
- Simplifier minors: delete `run_turn(model=)`, `procs.run(stdin_data=)` and `terminate_and_confirm(retry_every=)`.

**T4 exit list:**
- The exact-value credential scan, with a red SHA: a rotated token found only in an archived home, plus its base64 and URL-encoded forms, is refused with HB-SEC-001.
- `plan --json` ids equal the frozen plan's.
- Status budgets are measured from `prompt_sent`.
- `bench-status/1` gains `stop_code` and a `starting` running phase, and the D2 round-trip property is kept.
- Plan ids are validated against the status id regex.
- UI state tests for "No cells in this run." and the incomplete banner with its never-started count.
- `--json` passes under TTY and `NO_COLOR`.
- The stop rule and the duplicate `plan.json` check each exist once (Simplifier).

**T7 exit list:**
- M1 (usable): the real 4-cell E2E green on the joined branch.
- `bench verify` exits 0 on the E2E run's ledger, and its output goes in the Proof Pack.
- The canary green for both harnesses, or an Owner ruling on N5. Under option (a), the Proof Pack lists the exposed Codex cells, and the strict `xfail` stays as a disclosed residual risk.
- Each mutmut record is still current: `git diff <record-sha> HEAD -- <its modules>` is empty, or mutmut re-runs on those modules.
- All `tests/mutations/*.json` re-run under the hardened checker, and all killed.
- `docs/notes/mutation-record-phase1.md` compiles T1's and T2's records.
- The Proof Pack `docs/proof/phase1.md` holds:
  - the findings→tests map, with red SHAs;
  - the measured timings (`docs/proof/phase1-e2e-last.json`);
  - the A6 replies.
- Design deviations recorded: mutmut's platform limits, the `bench-status/1` fields, the N5 mechanism.
- The defect register updated.
- M2 (merge-ready): the Test Architect's re-review clears the veto; `main` fast-forwarded and pushed.

**T5 fallback.** If the research timebox (1.5 h) or the track budget (3 h) runs out, T5 sends the Owner a decision request with three options:
- (a) keep `xfail(strict)`, record the contamination in the Proof Pack, and flag Codex cells `user-config exposed (N5)` in the report header;
- (b) run tomorrow with Claude Code combos only;
- (c) accept the exposure: ADR-0013 accepts the agent reaching outside its working copy.

The recommended option is (a). Timeboxing the research makes the ruling reach T1 while T1 is still open, if an engine-side change is needed.

**Why each track earns the multiplier** (GO6: expect about 15× the tokens of one session):
- **T1–T4 are genuinely independent.** Their authored paths are disjoint, and the step-3 interfaces remove the data and decision edges between them. They also buy context hygiene: more than 45 findings across four modules would not fit one session's context at full rigor.
- **T5 is isolated and needs machine time:** research, then real model turns.
- **T7 is the serial close.**
- **Speed is last in the objective.** It is admitted only because the Owner set a deadline, and no rigor floor is traded for it.
- **Named risk.** If step 2 fails for both harnesses, five Claude Code sub-agents on one subscription may hit rate limits. The Coordinator then runs T1 and T2 first and T3 to T5 after them.

## Serial spine

| item | why it cannot be parallel | who owns it |
| --- | --- | --- |
| 1. Pin the leader; create `docs/notes/rulings.md` with R-1; set `AGENT_SESSION` per session | every track row carries the leader epoch (CO-L); without `AGENT_SESSION`, the commit floor is advisory | Coordinator |
| 2. Qualify the grok and agy transports (one smoke turn each through `coord-runner`, with the capability recorded); probe mutmut on Windows (R13) | an unexercised mechanism is `unsupported`, and dispatching onto it is guessing. The R13 result decides how T1 and T2 run mutmut | Coordinator |
| 3. Harden `tools/mutate_check.py`; quote the interfaces into each track prompt; the Owner rules on two of them | every track's "all killed" claim depends on the checker; unfixed interfaces fail GO5(b) | Coordinator; the Owner rules on two items |
| 4. Joins, in completion order: merge, not rebase; the full suite after each; derived files regenerate through the drivers | disjoint files make the order free, so a fixed order would only make early finishers wait. Only the last merge is on the critical path | Coordinator |
| 5. T7 E2E (M1), then the Proof Pack and re-review (M2) | needs the joined code and the one credentials host | Coordinator |
| **Loop-back** | any `src` change after its track joins (an E2E-driven fix, or a bug a mutant reveals) reopens the owning track under the Coordinator. mutmut re-runs on the touched modules, and their mutation record is regenerated. Before the fast-forward, remove the primary's untracked `.agents/artifacts.yml` (identical to the tracked copy), or git refuses to overwrite it | Coordinator |

**Interfaces at step 3.**

These three are quoted to the tracks as constraints; they change nothing:
- **Driver → engine.** `TurnResult.usage` keeps the shape `{"usage": <dict or None>, "meta": <dict or None>}`. T3 may only stop dropping `meta` when `usage` is absent.
- **Ledger → engine.** `SegmentWriter.append` keeps raising on failure. After one failed write, later appends also raise (T2), and T1 sets `broken` on the first.
- **Error codes.** Only T1 edits `errors.py`, and it adds HB-RUN-005. Other tracks use existing codes, or raise a seam request.

The Owner rules on two, into `docs/notes/rulings.md`:
- **R-2.** `grading.completed` gains `heads: {fact: head_hash}` for its other sealed facts. `run.completed` keeps `segment_heads`. `bench verify` checks both. Recommended: yes.
- **R-3.** `bench-status/1` gains `stop_code: str | null` and a `starting` running phase. The schema stays version 1, since these are additive fields and the strict parser moves with them in the same change. Recommended: yes.

## Seams

| from -> to | the request | resolved by |
| --- | --- | --- |
| T2 -> T1 | the engine must not rename `run.completed.segment_heads` | fixed at step 3 (constraint) |
| T3 -> T1 | `TurnResult.usage` shape unchanged; `meta` kept when `usage` is absent | fixed at step 3 (constraint) |
| T4 -> T2 | `tests/archived_runs.py` may need a `launch_stopped` helper for status tests | T2 adds it on request (`coord request --to T2`); T4 builds the event inline meanwhile |
| T4 -> T1 | status shows a "grading" phase | none needed: derived from `grading.started` without `grading.completed`; T1's heartbeat keeps the run `alive` |
| T1 -> T3 | T-FI-unkillable and T-JOB-daemon use `procs`'s fault seam | T3 keeps the seam's signature; a change goes back as a seam request |
| T5 -> T1 | if the N5 fix needs an engine-side environment change | T5 proposes it within its 1.5 h research timebox; the Owner rules; T1 applies it while still open |

## Struck tracks

| track | why it was not worth its multiplier |
| --- | --- |
| T6 mutation-bar (serial) | struck at the gate (Simplifier, Tech Lead). Each module's code is final when its owning track exits, so mutmut runs inside T1 and T2 without a serial 4 h tail. T7 compiles the records and re-runs every `mutations/*.json` under the hardened checker |
| one track per reviewer | each reviewer's findings span engine.py; that would put four authors on one file |
| a separate fault-test track | the fault tests depend on T1's engine fixes, and `test_engine.py` has one owner |
| a separate D6 golden-fixture track | coupled to T2's `grading.completed` schema change |
| a "Simplifier minors" sweep | the minors are spread over files T1–T4 own, so each owner takes its own. Dropped: merging `grader_build` with `extraction_id` (crosses T2 and T3), and rewriting the `archive.py` walk (the Simplifier marked it MUST STAY) |
| merging T3 with T4 | kept apart (Tech Lead's vote): no shared file and no data edge. Merged, they would put about 7 h in series |

## Order of operations

| # | action | cost | why now |
| --- | --- | --- | --- |
| 1 | `coord leader pin coord-opus`; `docs/notes/rulings.md` with R-1 (already in the registry); `coord doctor` | 5 min | CO-L epoch and the ruling register before any request |
| 2 | qualify the transports: one `coord-runner` smoke turn each — `grok agent --no-leader stdio` (1.0.30, `XAI_API_KEY` removed; confirm "logged in with grok.com") and `agy --mode accept-edits --input-format stream-json --output-format stream-json`; record enforced / observed-only / unsupported; wire `coord hook --config --host grok` and `--host agy`; run the R13 mutmut probe | 45–90 min (Inferred; grok 1.0.30 is below the known compatibility path) | never dispatch onto an unexercised mode. On failure, route that harness's tracks to Claude Code sub-agents |
| 3 | harden `mutate_check`; quote the constraints; the Owner rules on R-2 and R-3 | 20 min | every "all killed" claim and every interface depends on this |
| 4 | `coord worktree new` × 5 (T1–T5) from `impl/phase1`; `coord doctor` in each (inherited, never installed); dispatch in parallel | 5 min | the fan-out |
| 5 | watch the board and mail; answer seam and decision requests; kick a stalled track per the kick ladder | 8–12 h (T1 is the critical path) | the Coordinator's job during the fan-out |
| 6 | merge each track as it finishes, with the full suite after each | about 15 min per join | serial spine 4 |
| 7 | T7: the E2E → **M1 usable**; compile the mutation record, re-run the checker, write the Proof Pack, re-review → **M2 merge-ready**; fast-forward `main`, push; `worktree cleanup` (reports only; removal is opt-in) | 2–3 h | serial spine 5 |

**Critical path:** step 1 → 2 → 3 → T1 → last join → T7. That is about **12–17 h wall to M2**, and M1 lands roughly 1 h after T1 joins. This is Inferred from this session's measured slice times, scaled to the T1 checklist (the Tech Lead estimated 16–20 h, and the lower bound here assumes the tracks do not stall). Record the planned and actual times for each track (GO19).

**Termination.** Every track stops at its exit evidence, or at its budget with a written report of what remains. A track at its budget does not continue on its own; the Coordinator re-plans. A finding without a test node and a red SHA is not closed.
