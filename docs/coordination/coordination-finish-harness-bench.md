---
id: coordination-finish-harness-bench
title: "Coordination plan - finish harness-bench (phases 2-5, the 31 outstanding to-dos)"
type: plan
status: accepted
owner: "@timianmalloo"
phase: "Phase 2 · smoke on all harnesses"
tags: [coordination, worktrees, parallelism, phase-2]
links:
  - { to: design-phase1-walking-skeleton, rel: relates-to }
  - { to: rulings-register, rel: relates-to }
  - { to: coordination-phase1-finish-run, rel: relates-to }
review-by: "2026-10-08"
summary: >-
  A rolling-wave plan for the 31 outstanding to-dos. Waves 0-1 are planned to the track (the Copilot-vs-Codex
  capability, the real ACP transcript, hardening and the upstream pack fixes); waves 2-5 are planned to the row,
  with the gate's exit conditions carried. Each later wave is re-derived at the previous join. Owner Fable, Leader
  Opus 5.5, workers on Codex gpt-6-sol, Grok, Agy and Claude subagents.
---

# Coordination plan: finish harness-bench

**Compiled from:** `al-01M3AKF6FZSG1RCB5FB5MR3C76` (raw `al-01M3AKF5D9FSZ2BE0ARDZCXNKQ`), dispatchable, 0 decision requests.

**Goal:** take harness-bench from the finished phase-1 walking skeleton to the full design (phases 2–5), closing all 31 outstanding to-dos.

**Done when:**
1. Every row is either (a) merged to `main` with its exit evidence observed at a join, (b) closed by an Owner ruling in `docs/notes/rulings.md`, or (c) handed to the human with a named reason (rows marked HUMAN).
2. The coordination plan and run record are committed, and `bench verify` passes on the final smoke run.

**Not in scope:** new metrics, UI or harnesses beyond the spec; changing the X1 fixture; any API key (subscriptions only, ADR-0003); rewriting phase-1 code except where a row names it.

**Why rolling waves.** A plan is a record of a measurement, and measurements go stale. Waves 3–5 depend on designs that do not exist yet (stop and decisions, the scripted user, the judges' gateway). Planning their tracks now would mean guessing their files. So waves 0–1 are planned to the track, and waves 2–5 to the row. Each later wave is re-derived at the previous wave's join, from the code as merged.

## Seats

| seat | who | model | rules into |
| --- | --- | --- | --- |
| Owner | Claude Code subagent | Fable 5.1 (`claude-fable-5-1`) | `docs/notes/rulings.md` (register) |
| Leader / Coordinator | Claude Code session `coord-opus-cq` | Opus 5.5 (`claude-opus-5-5`) | this plan, every join, every `bench run` |
| Complex tracks | Codex, `coord-runner` (qualified `qualify-codex-2`) | `gpt-6-sol`, `agent-full-access` | their owned paths |
| Well-defined tracks | Grok and Agy, `coord-runner` | harness default (operator: grok 4.7 high; Gemini 3.8 Flash High), served id recorded at re-check | their owned paths |
| Claude subagents | Claude Code, `coord worktree new` trees | Opus 5.5 (design, ambiguous work) · Sonnet 5 (mechanical) | their owned paths; the persona gates at joins |

**Rulings in force:** R-1 (seats), R-4 (fallback to Claude Code), R-7 (task sources), R-8 (grading-pass anchor), R-9 (machine time). Operator decisions, 2026-09-24: Codex runs in `agent-full-access`; Grok and Agy run their default models; Agy stays on Gemini for now.

**Cross-vendor review.** Every track's join reviewer comes from a different vendor than its author. A Codex author gets a Claude reviewer; a Grok or Agy author gets a Codex or Claude reviewer; a Claude author gets a Codex reviewer. The Test Architect's hard veto is always a Claude persona subagent that is not the author.

## Layer state

Measured with `coord doctor` in the primary checkout, 2026-09-24, after the stale request was expired:

| check | result | meaning |
| --- | --- | --- |
| registry | ok - 11 patterns | classification is real (`.agents/artifacts.yml`, committed) |
| merge driver | effective: `coord-regen` and `coord-register` declared and registered | a merge in any worktree regenerates derived files and union-merges registers |
| leader | `coord-opus-cq`, epoch 5, TTL 900 s | the Leader renews while any worker runs; reclaims after a lapse |
| heartbeat | 2 sessions beating; 8 stalled, 0 live, 7 done (phase-1 sessions) | the stalled rows are finished phase-1 sessions, not live work |
| requests | ok - 2 requests, 0 open, 2 terminal | `req-01M38KX8…` was expired with its recorded fallback (row 14 stays open) |
| lease overlap | none (0 live leases) | no track holds anything yet |
| pre-commit floor | installed in the shared `.git/hooks`; enforcing when `AGENT_SESSION` is set | every track sets `AGENT_SESSION=<track>` |

**Install once, in the primary checkout.** `coord install` has run for this clone. Every tree this plan creates inherits the registration through the shared `.git/config` and `.git/hooks`; each track runs `coord doctor` inside its tree to read it back. No track installs anything.

## Artifact classes

| path / pattern | class | mechanism | coordination needed |
| --- | --- | --- | --- |
| `docs/docs-index.js`, `docs/audit/audit-data.js`, `docs/audit/index.html`, `docs/specs/harness-bench.html`, synced skill copies | derived | `coord-regen` re-runs the registered command at merge | **none** |
| `docs/audit/audit-log.jsonl`, `docs/audit/change-log.jsonl`, `docs/notes/rulings.md` | register | `coord-register` union-merges; never claimed | **none** |
| `.agents/log/<session>.jsonl` | per-session file (one writer each) | each session writes only its own file | **none** |
| `src/harness_bench/**`, `tests/**`, `bench/**`, `tasks/**`, `tools/**`, `docs/design/**`, `docs/adr/**`, `docs/proof/**` | authored | one owner per file per wave (Tracks table) | **yes**: the only real contention |
| `src/harness_bench/errors.py` (cause codes) | authored, shared surface | wave 1 owner: `W1-COP-I`; others raise a seam | yes |
| `src/harness_bench/profiles.py` (`READERS`, `HARNESSES`) | authored, shared surface | wave 1 owner: `W1-COP-I`; `W1-COP-R` raises a seam for its one `READERS` line | yes |
| `tests/conftest.py` (fixtures `base`, `clean_parent`, loaded by every suite) | authored, shared surface | unclaimed in wave 1; any change is announced at the join and the full suite re-run on the merged head | yes |
| `src/harness_bench/driver.py` | authored | wave 1 owner: `W1-ACP`, from its step (f) only | yes |
| `bench/bom.yaml` | authored, shared surface | the Leader edits it at joins from task tracks' seam requests (R-7 source changes) | yes |
| `docs/proof/phase2.md` and later Proof Packs | authored | the Leader, at joins | yes |

**Shared-surface guards.** `tests/test_architecture.py` (import lint), `tests/test_skills_in_sync.py`, `tests/test_docs_html_in_sync.py` and the heredoc guard are scan-shaped guards every track must keep green. They scan `src/harness_bench/**` (import lint, recursive, module-import tokens, allowlist in the test), `.claude/skills` against `.agents/skills` (recursive), and `docs/specs/*.md` against their HTML (listed files only). Every owned path below lies inside a guard's root, so each track runs the full suite before its hand-back. A track's guard failure is that track's defect, not a join defect.

## Tracks

Waves 0–1: planned to the track. This is version 2, after the Stage 8 gate (see Gate record).

**Budgets.** Claude subagent budgets are tool calls · wall clock, measured from the harness's completion notice. **Runner tracks (Codex, Grok, Agy) are budgeted in slices** because `coord-runner` bounds one attempt to 1–3600 s (`coord-runner.py:365`), at most 8 turns (`:325`) and 16 MiB. Each slice is ≤ 55 min and ends at a commit and a hand-back. The Leader joins the slice to `main` (full suite green, cited reds re-run) and prepares the next slice from `main` with a new session and branch (`simplify:` slices chain through `main`; ceiling: owned paths stay disjoint; upgrade trigger: two tracks' slices need each other's unmerged work). **Runner budgets are Inferred**: no multi-slice runner track has been measured here. After each slice, the Leader records the tool count from the native record where a reader exists (Codex rollout) and writes "not recorded" for Grok and Agy. **R-4 fallback trigger, per runner track:** a slice that ends with no commit, or two `RUN-BOUNDS` refusals, moves the track to Claude Code by Owner ruling. The context ceiling is 400k tokens per track.

**Dispatch gate.** A track is dispatched only while fewer than 5 tracks are live (the fan-out cap). When a slot opens, the critical path goes first.

**Join rule (every join).** A non-author re-runs every cited red SHA in a throwaway worktree, sees it fail for the stated reason, and confirms with `git show --stat` that the red commit touches no `src/`. The cross-vendor reviewer adds 3 mutants of their own to the track's mutation file, and each is killed by a named test.

| track | owns (authored) | depends on | tier | fan-out cap | budget | exit evidence | harness |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **W0-QUAL** Grok and Agy re-check (serial, Leader) | none (throwaway branches) | — | T0 | 0 | 20 calls · 20 min | **Done** (`qualify-6`): both `ready_for_review`; Grok reported `grok-4.7` (ACP `selected_model`); Agy's conversation store shows executor `gemini-3.8-flash-high`, 17 generations on `gemini-3.8-flash` | Leader runs `coord-runner` on Grok and Agy |
| **W1-COP-D** Copilot profile design (rows 1–5) | `docs/design/phase2-copilot-profile.md`, `tests/fixtures/native/copilot/**` (the scrubbed sample and its provenance) | — | T2 | 1 | 150 calls · 2 h | `/design-slice` output, gated by Patterns Expert, Simplifier and Test Architect at the join. It states: the profile, pinned build and launch shape (native ACP, no adapter); **"`driver.py` unchanged \| changed (what)"** and the argv shape; the reader contract, including the SQLite bound (read-only open, a file-size cap and a row cap; an unknown schema version degrades to "not recorded"); a promise→test table for US-9 (the pack-off marker scan over Copilot's instruction files), US-10, US-11, US-12, US-13 and US-14 for Copilot; and a committed, scrubbed `session-store.db` sample (pack-on and pack-off, captured by the Leader seam) whose provenance states the scrub rule | Claude subagent · Opus 5.5 |
| **W1-COP-I** Copilot implementation (rows 1–3, 5; wires row 4) | `bench/profiles/copilot.yaml`, `src/harness_bench/profiles.py`, `src/harness_bench/tools.py`, `src/harness_bench/errors.py`, `src/harness_bench/workspace.py` (HB-PRE-002 only), `bench/tools/package.json`, `bench/tools/package-lock.json`, `bench/matrix.wave1.yaml`, `tests/test_profiles.py`, `tests/test_tools.py`, `tests/test_workspace.py`, `tests/test_errors.py`, `tests/e2e/test_walking_skeleton.py` (the parametrisation only), `tests/mutations/copilot.json`, `tests/mutations/workspace.json`. Never `driver.py`: a driver change goes through the COP-D → W1-ACP seam | W1-COP-D | T2 | 1 | ≤ 5 slices × 55 min (Inferred) | red-first tests for the pack-on probe and for each new HB-PRE-002 branch; `tests/mutations/copilot.json` has at least one entry per new branch in profiles, tools, errors and workspace, all killed; `bench plan` accepts a `copilot` combo; `bench tools install` pins and hashes the Copilot build; **`tests/e2e/test_walking_skeleton.py` is parametrised on `bench/matrix.wave1.yaml`** (the wave-1 exit below) | Codex · `gpt-6-sol` |
| **W1-COP-R** Copilot telemetry reader (row 4) | `src/harness_bench/telemetry/copilot.py`, `tests/test_telemetry_copilot.py` | W1-COP-D (the sample, the SQLite bound and the reader contract) | T1 | 0 | ≤ 2 slices × 55 min (Inferred) | red-first; tests assert the first user message's hash equals `prompt.md` (pack-on included), the served model ids, and token counts equal to values read independently with `sqlite3` and recorded in the sample's provenance; an unknown schema version degrades to "not recorded", never to a number | Grok · default (`grok-4.7`) |
| **W1-ACP** Real ACP transcript and the `last_update` seam (rows 6, 14) | `tools/acp_record.py` (a **standalone stdio recorder**: it spawns the adapter itself and tees both pipes; no argv wrapper, so no `profiles.py` edit), `tests/fixtures/acp/**`, `tests/test_driver.py`, and from its last step `src/harness_bench/driver.py` | — (the capture turns are a Leader seam) | T2 | 0 | 260 calls · 4 h | (a) The recorder is transparent: a test runs the fake agent's `ok` and `permission` modes with and without the recorder, and gets an identical `TurnResult` and identical bytes on both pipes; `git diff <base>..<head> -- src/harness_bench/driver.py` is empty until step (f). (b) `replay_agent.py` replays every agent line of the recorded transcript verbatim, with no synthesised handshake; a red test that fails on the current synthesising replayer comes first. (c) Every D7 `PAIRING` entry except `session/request_permission` cites a message type present in a recorded transcript, and a test asserts that presence by parsing the recordings. (d) Negative control: one byte mutated in a recorded `session/new` result makes D5 fail. (e) `provenance.json` no longer says "No full ACP transcript", and each recording names adapter version, harness build, capture date and scrub rule. (f) Last, red-first: `TurnResult.last_update_seconds` is non-null after at least one `session/update`, and null (never 0) with none; it appears in the wave-1 X1 run's ledger and in `bench status` (that ledger and status half is verified at the wave-1 exit, not at W1-ACP's own join). Seam `req-01M38KX8…` closes | Claude subagent · Opus 5.5 |
| **W1-HOST** Process, host and report hardening (row 28) | `src/harness_bench/procs.py`, `src/harness_bench/host.py`, `src/harness_bench/cli.py`, `src/harness_bench/report/cli_table.py`, `tests/test_procs.py`, `tests/test_host.py`, `tests/test_cli.py`, `tests/test_report.py`, `tests/test_no_leftovers.py`, `tests/mutations/cli.json` | W0-QUAL | T1 | 0 | ≤ 3 slices × 55 min (Inferred) | red SHAs for: spawn `TimeoutExpired` before `job.close()`; unchecked `GlobalMemoryStatusEx` and `QueryUnbiasedInterruptTime`; labels printed before the credential scan (`cli.py:191-194`, `cmd_report` prints the table before `html.write` scans). The "0 folders left" test lives in the new `tests/test_no_leftovers.py`; its red is shown by reverting the CLN-A fixture fix in a throwaway tree (the test fails and states the count). `tests/conftest.py` is not claimed | Grok · default (`grok-4.7`) |
| **W1-TOOLB** TOOL-B control (row 26) | `tools/mutate_check.py`, `tests/test_mutate_check.py` | W0-QUAL | T1 | 0 | ≤ 2 slices × 55 min (Inferred) | red-first seeded cases: a mutant that causes a collection error, a timeout, and an exit-2 run are each reported NOT a named kill. The control re-derives each kill from `cosmic-ray dump` and names the failing test. It is run over the phase-1 modules, and the re-derived kill count is written in `docs/proof/phase2.md` next to 2267 (the Leader writes it at the join). The session database is stored with its sha256 in the run record | Agy · default (`gemini-3.8-flash`) |
| **W1-PACK** Upstream pack fixes (row 29; the Codex hook command) | in `C:\projects\ai-forward`, its own worktree: `pack/scripts/verify-ruling-citations.py`, the Codex branch of `coord-core.py hook --config`, and their tests | — | T1 | 0 | 150 calls · 2 h | red-first upstream, committed and pushed as a new pack revision. (a) The gate recognises `## R-n` definitions and `R-n` citations. Applied here, the local gate counts 9 definitions (R-1..R-9) and at least 1 citation, and a seeded dangling short-form citation (an undefined number) makes it exit non-zero. (b) The Codex hook entry runs under `pwsh`/`cmd.exe` as well as `sh` (the revision-93 Agy pattern). It is observed firing in a real Codex session under `pwsh` (log line cited) at the re-qualification `qualify-codex-3` | Claude subagent · Opus 5.5 |

**Wave-1 exit (the Copilot-vs-Codex capability).** `tests/e2e/test_walking_skeleton.py` is parametrised on `bench/matrix.wave1.yaml` (X1 × {copilot-sol, codex-sol, cc-opus} × pack {on, off} × 1). It passes with every phase-1 Claim-1 assertion applied to all 6 cells:
- `Validity: valid 6`;
- the US-10 prompt hash equals the one in each harness's own native record, Copilot included;
- the US-12 executed build hash equals the planned one;
- US-14 permission requests are `[0]*6`;
- `verify: ok` before and after a re-grade, and the re-grade is byte-identical;
- no process is left in any job, and the run folder is removable.

Also: one Copilot turn is recorded through the W1-ACP recorder and added to D5/D7. The US-13 canary runs for Copilot (the control shows every canary; the isolated probe shows none), or the wave-1 report states "Copilot user-config isolation: not measured" on every Copilot cell.

**Version 3 amendments (2026-09-24, after capture window 1 and rulings R-12..R-28).** These supersede the wording of the rows above where they differ.
- **Copilot record (W1-COP-D, W1-COP-R).** In a per-cell ACP home, Copilot 1.0.89-1 writes `session-state/<sid>/events.jsonl` and **no `session-store.db`**, so every "SQLite bound", "`session-store.db` sample" and "`sqlite3`" requirement above is void.
  - The reader reads `events.jsonl`: per-model usage from the last `session.shutdown.modelMetrics`.
  - The independent oracle is the ACP `usage` (Σ uncached, cache read, cache write and output = `totalTokens`).
  - The samples are committed (`9c6c615`, scrub-rule/2).
  - `model_calls` keeps Copilot under a re-declared grain with an additive `requests` column (R-26). The ADR-0006 amendment is W1-COP-D's.
  - W1-COP-R adds `tests/mutations/copilot_reader.json` and records each tool call's `error.code` on its `tool_calls` row (R-27).
- **W1-COP-I** also owns the Claude Code pin bump to 2.1.282, or 2.1.281 as fallback (R-17). The phase-1 X1 run is declared not comparable.
  - It also owns: the Copilot `set_model` refusal form (R-18); the Copilot branch of the US-13 canary and `bench/pack-markers.txt` (R-16); `COPILOT_AUTO_UPDATE=false` and the `@github/copilot` 1.0.89-1 pin, marked prerelease (R-12).
- **W1-ACP** also owns:
  - `session/set_model` as a typed `Launcher` field;
  - one error classifier (R-18, R-23);
  - `agent_version` on `attempt.session_opened` (R-28);
  - `acp_usage` on the terminal events row (R-24);
  - the engine call-site and `credential_kind` lines (R-13).
- **Ownership additions (after COP-D revision 3).**
  - W1-COP-R: `src/harness_bench/telemetry/normalize.py` and `src/harness_bench/telemetry/__init__.py` (`ModelCall.requests`, its docstring, `ToolCall.outcome_code`, `Extraction.hook_starts`/`hook_failures`), plus `src/harness_bench/telemetry/copilot.py`, its tests and `tests/mutations/copilot_reader.json`. Runs on Claude Sonnet 5 (R-29: Grok held).
  - W1-COP-I: `src/harness_bench/views.py` (the `model_calls` key with `model`, the single row mapper, `calls_per_cell`, the row-count guard) and `src/harness_bench/plan.py` (the `instruction_list` datum per task, pack and build). `report/credentials.py` is dropped (the design reverted to `credential: null`).
  - **Seam granted by the Leader to W1-ACP** (COP-I had not started): `ProfileLauncher` gains `set_model` and `credential_kind` in `profiles.py`, so a real `bench run` does not raise once the typed `Launcher` fields land. W1-COP-I builds on it.
  - Seams to W2-STOP: `last_update` in `bench status`; the stale `assume:` comment at `engine.py:367`.
- **Wave-1 exit.** Pack-on Copilot on revision 92 is not a treatment: its failing hook denies every tool call (R-27).
  - The exit run installs the treatment from `--pack-source` at the revision-95 commit, with the header "pack revision 95". `/updatepack` stays after the wave-1 merge.
  - The exit E2E asserts zero hook denials per Copilot cell, with the revision-92 fixture kept as the negative control.
  - US-14 for Copilot means ACP permission requests AND native hook denials, both 0.
  - If revision 95 is not upstream by then, Copilot pack-on cells are reported "pack on: all tools denied", excluded from every comparison, and re-run as wave 2's first act.

**Wave 2: planned to the row.** Its tracks are drawn at the wave-1 join from the merged code. Only the facts the spine needs are fixed now: W2-STOP owns `engine.py`, `cli.py` and `errors.py`. The exit conditions below are fixed now and carried into the re-derivation (Test Architect, Stage 8).

| row(s) | intended track · harness | exit conditions carried from the gate |
| --- | --- | --- |
| 10 stop, decision timeout, circuit breaker | W2-STOP · Codex `gpt-6-sol`; `/design-slice` and implementation as separate sessions (context hygiene) | **Stop:** a real process tree with a child that ignores termination is stopped within 30 s by the engine's clock, with outcome `stopped`; any open decision becomes `superseded (stop)`; `bench status` shows `stopped` within 30 s (UXA-10). **Race:** both orderings are forced deterministically (injected clock or barrier, no sleep), and each gives exactly one terminal decision state and one ledger event. **US-15:** one test per default (blocked; qualification gap → `skipped (decision)`; spend cap → stop). **Circuit breaker:** its acceptance criterion is written in the design, with a red-first test. The existing power request (`host.keep_awake`, `engine.py:216/258`) stays held through stop and exception (test). The TLC seeded variants still fail |
| 8 T0 scripted-user matcher | W2-USER · Claude Opus 5.5, paired with the AI Systems Engineer | a held-out set of questions not written by the matcher's author; near-miss questions answered exactly `Decide and state your assumption.`; the log records question, decision and reply (US-10) |
| 9 Harbor E1 base image | W2-HARBOR · Claude Opus 5.5 | spike A6 recorded; no bind mount of the operator profile and no Docker socket in the E1 container (inspected); the US-48 canary secrets never appear in any transcript or archive; if not passed by the wave-2 join, E1 is deferred and E6 takes the slot (R-7) |
| 7 smoke tasks A1, B1, C1, D1, F1, E1/E6 | W2-TASKS-a/b/c · Codex `gpt-6-sol` and Claude Opus 5.5 | **For each task:** the hidden tests run on the base workspace and are observed to FAIL, then on a reference solution and are observed to PASS; both runs are recorded in the task's audit entry (commands, exit codes, failing test names). For A1–A3, the LiveCodeBench tests run natively on this host (R-7 condition 6). `bench/bom.yaml` changes are raised to the Leader |
| 15 resource check and the parallelism cap | the last step of W2-TASKS-b (it authors D1) plus a Leader run | the headroom rule (memory and CPU per cell × parallelism, against the host figures) is written before the run; every cell's samples are non-null or the measurement is void; `test_plan.py` asserts the new cap |
| 12, 13 canaries and the N5 probe | W2-CANARY · Grok | a red test with a colliding string ("graphify" in both `CLAUDE.md` and a skill name) reports both classes; the N5 probe's pack-on and pack-off leaked sets are both written to `docs/proof/phase2.md`, and the Owner rules R-5 on their equality |
| the smoke run | Leader, R-9 night window | at 07:00, `bench status` explains every non-completed cell; the phase-2 Proof Pack carries a Claim table per join (evidence, red observed, mutation result, residuals) |

**Waves 3–5: planned to the row.** Tracks are drawn at the previous join.

| wave | rows | intended harness | gate |
| --- | --- | --- | --- |
| 3 · grading and judges | 16 full graders · 17 gateway + judges (ADR-0009) · 18 egress gate + injection fixture | Codex `gpt-6-sol` (16, 17) · Claude Opus 5.5 (18, security) | the smoke archive re-grades byte-identically; κ in the header |
| 4 · statistics and full report | 19 statistics · 20 full report + summaries | Codex `gpt-6-sol` (19) · Claude Opus 5.5 (20, UI) | UIA-1..15, axe, offline load; two P3 readers name the leader and the pack effect |
| 5 · full grid | 21 remaining 17 tasks · 22 G1/G2 (after S-12) · 23 resume · 24 comparison + stability · 27 grading-pass anchor (R-8, ADR-0006 amendment) · 25 full grid run | task authoring split over Codex, Grok, Agy and Claude by task difficulty; 23/24/27 Codex or Claude Opus | crash-then-resume in each state; a pack change validated by a re-run comparison; the full grid in an exclusive block (R-9) |
| HUMAN | 30 host risks A3 / A9 (the host must be put to sleep) | the operator | handed over with the probe steps |
| ruled | 31 Copilot USD cost: `NA` by decision (`docs/proof/phase1.md`, Remaining) | — | closed by citation |
| already built | 11 power request: `host.keep_awake` (`src/harness_bench/host.py:89`), held by `Engine.run` (`engine.py:216`) and released in its `finally` (`engine.py:258`). The to-do list's "not built" was wrong (Simplifier, Stage 8; verified by the Leader) | — | closed by citation; whether it really keeps the host awake overnight is the human's A9 probe (row 30) |

## Serial spine

| item | why it cannot be parallel | who owns it |
| --- | --- | --- |
| W0-QUAL before any Grok or Agy track | their harnesses changed since `qualify-5` (default models, no pin); an unqualified mechanism is `unsupported` | Leader (done) |
| W1-COP-D before W1-COP-I and W1-COP-R | until the Copilot contracts, the sample and the SQLite bound are fixed, every result changes the other's shape (GO5b) | Claude Opus (COP-D) |
| **Capture window 1** at the COP-D join, before COP-I is dispatched: the Leader records the claude-code and codex turns through the W1-ACP recorder, and captures the pack-on and pack-off `session-store.db` samples for COP-D | the capture is cell-shaped and runs on the Anthropic, OpenAI and GitHub logins. No runner slice on those logins may be live (R-9 rule 1), and a runner slice cannot be paused, only ended. Claude subagents on the Anthropic login (ACP, PACK) must be at a hand-back | Leader |
| W1-ACP's recorder before its own `driver.py` step, and before any `driver.py` change by another track | Test Architect condition, `docs/proof/phase1.md` residual 9: "Deadline: before phase 2 changes the driver." | Claude Opus (ACP) |
| Every `bench run`, and **capture window 2** (the Copilot turn plus the wave-1 X1 run) at the wave-1 join | owner ruling 3 (ADR-0002): no benchmark cell runs inside the coordination layer; R-9 vendor exclusivity during a run | Leader via `/start-benchmark` |
| `/updatepack` (the W1-PACK revision) only after every wave-1 track has merged, then `qualify-codex-3` before any wave-2 Codex dispatch | it rewrites managed pack files that `tests/test_skills_in_sync.py` scans in every open worktree, and the Codex qualification is bound to the hook and runner bytes | Leader |
| Each wave join | the next wave's tracks are drawn from the merged code (rolling waves) | Leader |
| The smoke run after every smoke task is `ready` and W2-STOP is joined | an overnight run needs stop and the timeout; R-9 night window | Leader |

## Seams

| from -> to | the request | resolved by |
| --- | --- | --- |
| W1-COP-R -> W1-COP-I | add `"copilot": copilot.read` to `READERS` in `profiles.py` | W1-COP-I, one line, at its next slice |
| W1-ACP -> Leader | record the claude-code and codex turns through the recorder (capture window 1), and the Copilot turn (capture window 2) | Leader |
| W1-COP-D -> Leader | capture the pack-on and pack-off `session-store.db` samples from one Copilot turn each (capture window 1; the installed Copilot CLI with an empty per-cell `COPILOT_HOME`, as in spike N1.2) | Leader |
| W1-COP-D -> W1-ACP | if the design says `driver.py` changes, the change is requested from W1-ACP, `driver.py`'s single wave-1 owner, never co-authored | W1-ACP, after its step (f) |
| any wave-1 track -> W1-COP-I | a new cause code in `errors.py` | W1-COP-I |
| `tests/conftest.py` (shared fixture file) -> Leader | any change to the shared fixtures is announced at the join, and the full suite is re-run on the merged head | Leader at the join |
| W2-TASKS-* -> Leader | `bench/bom.yaml` edits (R-7: B3 and C2 `source: authored`; the E1/E6 swap) | Leader at the join |
| W2-CANARY -> Leader | run the credentialed canary and the pack-seeded N5 probe | Leader, day hours |
| any track -> Owner | a decision the plan did not make | `coord decide request --to <owner-session>`; the Owner rules into `docs/notes/rulings.md` |

## Struck tracks

| track | why it was not worth its multiplier |
| --- | --- |
| A separate track per Copilot row (1, 2, 3, 5) | rows 1–3 and 5 share one aggregate (the Copilot profile) and three files; splitting them fails the coupling test and would generate seams forever |
| Row 11 work (a power-request context manager and its engine wiring) | already built and wired (`host.py:89`; `engine.py:216/258`); closed by citation |
| W2-DRIVER (row 14) as its own track | one field in `driver.py` (the engine already reads it with a null fallback, `engine.py:367-374`); it shares `tests/test_driver.py` with W1-ACP and depends only on it. Merged into W1-ACP as step (f) |
| W2-RES (row 15) as its own track | one Leader run and one constant (`plan.py:30`); folded into W2-TASKS-b, which authors D1 |
| A separate X1 transcript run (the prompt's wave-0 step) | the driver keeps no ACP stream (`tests/fixtures/acp/provenance.json`: "No full ACP transcript … was kept"), so a plain `bench run` captures nothing; replaced by W1-ACP's recorder and the Leader's capture windows |
| Planning waves 2–5 to the track now | their files depend on designs and merges that do not exist yet; the gate's exit conditions are carried instead |

**Kept against a gate finding (written rationale):**
- **W1-TOOLB on Agy, not merged into W1-HOST** (Simplifier finding 6). The compiled prompt assigns "distinct well-defined work" to Agy and Grok, and R-1 names both. The Tech Lead's casting vote keeps 7 wave-1 tracks under the live-count gate. So the peak-6 problem is solved by the gate, not by a merge.
- **The Codex hook fix in W1-PACK** (Simplifier C4). The operator's instruction in this session (2026-09-24) is: "if there are fixes that need to make up-stream, fix them up-stream and commit them (and make the local fix)". The hook defect was found in `qualify-codex-1` and recorded in the run record. The Simplifier's timing concern is taken: `/updatepack` runs only after the wave-1 merge.

## Cost

Parallelism is a cost multiplier, not a saving (about 15× tokens for an orchestrator-worker shape, GO6). Wave 1 holds at most 5 live tracks. Each earns its multiplier:
- **W1-COP-D then W1-COP-I:** a serial session boundary earned by context hygiene (150 + 300 calls would break one 400k context), not parallelism. It is the critical path to the Copilot-vs-Codex comparison.
- **W1-COP-R:** genuine independence (disjoint files; one seam line). It carries the float: 2 slices against COP-I's 5.
- **W1-ACP:** a hard predecessor of every driver change, off the critical path (4 h against about 7 h for COP-D plus COP-I).
- **W1-HOST, W1-TOOLB:** genuine independence (disjoint files, no decision edge), on Grok and Agy, which do not draw on the vendor logins the benchmark cells use.
- **W1-PACK:** isolation (a different repository) and genuine independence.

**Leader budget:** 400 calls · 10 h wall clock for wave 1, including capture windows 1 and 2 and every join. **Loop-back reserve:** 2 × 120 calls, sized for red-first across 3 or more test files. It opens only on a failing join or a failing wave-1 X1 run. In phase 1, 6 of 11 track runs were unplanned loop-backs, and T8 and T9 overran their budgets (98/80, 81/60).

**Live-count schedule:** COP-D, ACP, PACK, HOST and TOOLB are live first (5). COP-D's join opens capture window 1, then COP-I takes the freed slot (critical path first). COP-R takes the next slot that opens.

## Order of operations

| # | action | cost | why now |
| --- | --- | --- | --- |
| 1 | Leader: `coord leader` renewed while workers run (epoch 5, a 90 s loop) | a loop | the runner rechecks the Owner epoch before readiness |
| 2 | Stage 8 gate: Simplifier, Test Architect, Tech Lead | done | version 2 applies every finding or records its rationale |
| 3 | W0-QUAL: Grok and Agy re-check | done | gates W1-HOST and W1-TOOLB |
| 4 | Dispatch W1-COP-D, W1-ACP and W1-PACK (Claude Opus subagents), W1-HOST (Grok slice 1) and W1-TOOLB (Agy slice 1) | 5 live | the fan-out cap |
| 5 | W1-COP-D join (design gate), then capture window 1, then dispatch W1-COP-I (Codex slice 1) | 1 track | serial spine |
| 6 | W1-COP-R (Grok) on the next free slot | 1 track | float |
| 7 | Slice joins as they arrive; the next slice from `main` | per slice | runner deadline 3600 s |
| 8 | Wave-1 join, capture window 2, the wave-1 exit E2E and X1 run; report plus `bench verify` | 6 cells | the Copilot-vs-Codex capability |
| 9 | `/updatepack` with the W1-PACK revision, then `qualify-codex-3` | 1 update + 1 turn | only after the wave-1 merge |
| 10 | Re-derive wave 2 from the merged code; dispatch | ≤ 5 live | rolling waves |

## Status

| | |
| --- | --- |
| **Completed** | Codex qualified (`qualify-codex-2`); rulings R-7..R-9 committed (`0a64b0c`); prompt compiled (`al-01M3AKF6FZSG1RCB5FB5MR3C76`); layer state measured clean; W0-QUAL done (`qualify-6`); Stage 8 gate round 1 applied (version 2) |
| **Remaining** | waves 1–5 |
| **Best next action** | dispatch step 4 (5 live tracks) |

## Gate record

**Round 1 (2026-09-24), on version 1.**

| lens | verdict | disposition in version 2 |
| --- | --- | --- |
| Test Architect (hard veto) | BLOCK: 3 Blockers, 7 Majors, 2 Minors | Blockers applied verbatim: the wave-1 exit E2E on `bench/matrix.wave1.yaml` plus the join red re-run rule; W1-ACP exit (a)–(e); the smoke-task fail-on-base / pass-on-reference rule. Majors and Minors applied to their tracks, or carried into the wave-2 row table |
| Tech Lead (casting vote) | PASS WITH CONDITIONS (F1 Blocker-class) | F1 runner slices ≤ 55 min with an R-4 trigger; F2 Leader budget and loop-back reserve; F3 non-Claude budgets Inferred, tool counts from native records or "not recorded"; F4 live-count gate; F5 COP-D moved to Claude Opus; F6 sample, scrub rule and SQLite bound in COP-D; F7 driver change decided in COP-D, recorder fixed as standalone; F8 capture windows on the spine; F9 `/updatepack` after the wave-1 merge plus `qualify-codex-3`; F10 spine rows corrected. **Casting vote: 7 wave-1 tracks, at most 5 live** |
| Simplifier (soft veto) | BLOCK: C1–C4 | C1 row-11 work struck, closed by citation (verified); C2 `cli.py`, `tests/test_cli.py`, `tests/mutations/cli.json` added to W1-HOST; C3 W2-DRIVER merged into W1-ACP; C4 kept with a written rationale (the operator's instruction), with `/updatepack` pinned after the wave-1 merge. Minors: conftest.py unclaimed (new test file, shared-surface seam); COP-I owns `workspace.json` and `test_errors.py`; W2-RES folded into W2-TASKS-b; wave 2 cut to rows; the COP split justified by context hygiene. Finding 6 (merge TOOLB) kept against, with rationale; finding 7 (drop COP-R's COP-D edge) not taken, because the Tech Lead's F6 puts the sample and the SQLite bound in COP-D |

**Round 2 (2026-09-24), read-back of version 2.**
- **Test Architect: CLEARS THE VETO** for the plan text. All three Blockers are applied verbatim. Nit applied: the ledger and status half of W1-ACP (f) is verified at the wave-1 exit. Per-track Proof Packs are still due at each join.
- **Simplifier: CLEARS THE VETO.** C1–C4 are cleared (C4 by written rationale); findings 6 and 7 are accepted with rationale. Minor applied: `driver.py` is removed from W1-COP-I (one owner, W1-ACP). Nit applied: the wave-2 wording.
- **Tech Lead:** PASS WITH CONDITIONS in round 1, with F1–F9 applied. No read-back was requested, because version 2 takes each fix as written.
