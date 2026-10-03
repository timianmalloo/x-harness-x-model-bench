---
id: coordination-eval-campaign
title: "Coordination plan - Evaluation Campaign build (phases E1-E4)"
type: plan
status: proposed
owner: "@timianmalloo"
phase: "Enterprise evaluation: E1 walking skeleton, then E2 / E3 / E4 in parallel"
tags: [coordination, worktrees, parallelism, federation, evaluation-campaign]
links:
  - { to: arch-evaluation-campaign, rel: implements }
  - { to: spec-enterprise-evaluation, rel: relates-to }
  - { to: coordination-phase1-finish, rel: relates-to }
review-by: "2026-10-17"
summary: >-
  Builds phases E1-E4 of the Evaluation Campaign across Claude Code (Sonnet), Codex, Agy and Grok workers under a
  Claude Code Leader, a Fable Owner and an Opus 5.5 Coordinator. Serial spine first: harness qualification (Codex is
  blocked on the operator), then one seam-contracts doc that also fixes one owner per hub file per phase. Then twelve
  design slices reviewed by six lens reviewers, then federated red-first implementation along the real dependency
  graph: E1 to its demo, then E2, E3 and E4 in parallel, with engine.py edits serialised J before K, converging on the
  ADR-0021 section 4 table, TLC and ten discrimination records produced at the final engine identity.
---

# Coordination plan: the Evaluation Campaign build (E1-E4)

**Goal.** Build phases E1 to E4 of `docs/architecture-evaluation-campaign.md`, gated by ADR-0014 to ADR-0021 and specified by `docs/specs/enterprise-evaluation.md` (EV-1 to EV-20). Decompose into slices, design them in parallel, and federate the implementation across Claude Code (Sonnet), Codex, Agy and Grok.

**Done when** (from the compiled kickoff, audit entry `al-01M4188CTPZ72AV32F3D0WM63S`, `dispatchable: true`):
1. E1's walking skeleton is merged. Its demo (UF-E1 on the security task, through to one verdict in report section 3) and its E2E tests pass.
2. E2, E3 and E4 are merged. The convergence check passes: the ADR-0021 section 4 table, plus TLC with every ADR-0015 section 7 invariant.
3. All ten property tasks have discrimination records.
4. `main` is pushed and CI is green.
5. Every design and ruling is committed and indexed.

**Not in scope:** E5 (the first real campaign); the alarm-channel drill acceptance; macOS; pushes to ai-forward; any benchmark grid other than E1's own pilot and mini grid. **Tier:** T2. **Fan-out cap:** 6 concurrent workers, at most 2 per external harness.

This plan refines the kickoff's decomposition. It never widens it. Each refinement is marked **[refined]** with its reason.

## Seats

| seat | session | model (pinned) | duty | rules into |
| --- | --- | --- | --- | --- |
| Leader | `leader-e1e4` (Claude Code) | `claude-opus-5-5` | holds the leader lease (epoch 13; TTL cap 900 s, renewed by a loop); every merge to `main`; every push; every `coord-runner` dispatch (DR-1); the operator | — |
| Owner | `owner-fable` | `claude-fable-5-1` | answers every `coord decide request --to owner-fable` and every seam dispute | `docs/notes/rulings.md` (class `register`); the next ruling is **R-87** |
| Coordinator | `coord-opus-e1e4`, then one fresh session per phase | `claude-opus-5-5` | decomposes; writes the seam contracts and the slice briefs; compiles each brief (CO-S0); arbitrates seams; reviews joins; keeps the work graph | this plan; the contracts doc; `docs/lessons/defect-classes.md` |
| Workers | one session id per dispatch | pinned per track (Tracks table) | their track's owned paths only | — |

**Context ceilings.** Coordinator: 400k tokens per session. It hands off to a fresh session at each phase boundary: (1) qualification, contracts and Wave 1; (2) E1; (3) E2 to E4 and convergence. Workers: 150-200k tokens per slice. A slice that would exceed this is cut into dispatches, each ending at a commit.

**Who rules.** Every track can raise `coord decide request --to owner-fable`. The Owner rules into `docs/notes/rulings.md`. A request left unanswered for 30 minutes goes to the Coordinator. The Coordinator applies the plan's recommended option and marks it *provisional* (the phase-1 rule). Every track row carries **leader epoch 13** (CO-L). If the epoch changes, the runner refuses further dispatch (`coord-runner.py:891`) and the Coordinator re-reads the lease.

## Layer state

Measured 2026-10-03 16:15Z by `coord-opus-e1e4` (`coord doctor`, `pack-doctor.py --json`, `git worktree list`, `coord session list`). Re-measured after `coord regen`.

| check | result | meaning |
| --- | --- | --- |
| registry | ok - 11 patterns (`.agents/artifacts.yml`) | classification is real; no change needed for this plan (see Artifact classes) |
| merge driver | effective: `coord-regen` and `coord-register` declared and registered | a merge in any tree regenerates derived files and union-merges registers |
| regeneration | **1 artifact OWED** (`docs/docs-index.js`) → `coord regen` run in this plan's worktree: `ok docs/docs-index.js derived 100 entries`, exit 0. The output was byte-identical to the committed file (`git status` clean). The owed marker cleared; the doctor's line is gone on re-run | the index was current; only the marker was stale. Nothing to commit for it |
| leader | `leader-e1e4`, epoch 13, expiring in 863 s at the read | the Leader's renewal loop must keep running (TTL cap 900 s; class COORD-C names a keeper loop that outlives its duty) |
| heartbeat | 31 sessions beating; newest beat 340,369 s old; 1-2 stalled, 0 live | no live traffic. Not evidence of a working layer (CTX-H) |
| requests | 6 total, 0 open, 6 terminal | no open request blocks the plan |
| lease overlap | none (0 live leases) | — |
| worktrees | primary only (`main` at `6cda045c`), plus this plan's tree `x-harness-x-model-bench-coord-eval-campaign-plan` | no other writer in a tree |
| sessions | 1 active: `coord-opus-cq` in `x-harness-x-model-bench-w5-fm1`, 0 claims | a stale registration (its tree is gone); no claim conflicts |
| pack | revision 97 (2026.09.27.1); `python3` does not work, use `python` (3.12.10) | every command in this plan says `python` |
| doorbells | `not recorded` (pack-doctor) | no harness doorbell has been probed. Mail is read by polling `coord mail` (COORD-B: the Leader reads worker mail at every join) |
| commit floor | "the commit floor enforces regardless of the hook" (doctor) | every worker session sets `AGENT_SESSION=<track session>`, which makes the floor enforcing |

**Install once, in the primary checkout. Each worktree inherits it.** `coord install` was run once, in `C:\Projects\x-harness-x-model-bench`. A linked worktree shares `.git/config` and `.git/hooks`, so every tree in this plan inherits the drivers and the floor. `coord worktree new` printed "install NOT needed here" for this plan's tree. Each worker tree runs `coord doctor` to read the inherited state back. No worker tree runs `coord install`.

### Harness capability, as verified here

What a track needs from a delegation mechanism: its own tree and branch; the brief delivered verbatim; the pinned model actually served; commits confined to owned paths; a bounded attempt with a stated fallback.

| harness · mechanism | version measured now | worktree isolation | instructions | hooks (ownership) | permissions | model pin | status for this plan |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Claude Code sub-agent (Agent tool) | host session | **Agent-tool isolation `unsupported`**: refused twice on a `C:\projects` vs `C:/Projects` case compare (`coordination-phase1-finish-run.md`). Workers run in `coord worktree new` trees by absolute path instead | observed-only | edit boundary `enforcing` (spike S5; the doctor states no version was pinned) | observed-only | `model: sonnet` or `opus` alias. The served id (`claude-sonnet-5`, `claude-opus-5-5`) is **not verified**: read it back from the first dispatch's transcript (Q0) | usable; it is the fallback for every track |
| Codex via `coord-runner` + operator wrapper | `codex` on PATH: **codex-cli 0.160.0** (npm global). The wrapper pins `.tools/.../codex.exe`: **codex-cli 0.156.0**, model `gpt-6-sol` | observed-only at 0.156.0 (`qualify-codex-2`, 2026-09-24) | observed-only at 0.156.0 | `unsupported`: the pack's Codex hook is now the quote-free `git -c alias.aif-hook=...` form, but it was never exercised under Codex. Ownership holds at the commit floor and the runner's evidence check | observed-only (`agent-full-access`, approval `never`) at 0.156.0 | `CODEX_CONFIG` in the wrapper pins `gpt-6-sol` | **`unsupported` at 0.160.0 / `gpt-6.1-sol`. Blocker B-1** |
| Agy via `coord-runner` | **agy 1.2.13** | observed-only at 1.2.3 (`qualify-5`, 2026-09-24); contract argv used through run `w5-b2` (2026-09-29) | observed-only (1.2.3) | observed-only (1.2.3: rows with `host: agy`) | `accept-edits` | `--model gemini-3.8-flash-high` in argv | **`unsupported` at 1.2.13 until Q0** (version moved) |
| Grok via `coord-runner` | **grok 1.0.41** | observed-only at 1.0.41 (`qualify-5`); argv `grok agent --no-leader -m grok-4.7 --reasoning-effort high stdio` used through run `w4-lr` (2026-09-28) | observed-only | observed-only | default | `-m grok-4.7 --reasoning-effort high` | observed-only (same version). Q0 re-confirms; launch with `XAI_API_KEY` removed (phase-1 rule) |
| GitHub Copilot | — | — | — | — | — | — | **never used as a worker** |

**Runner limits, read from `coord-runner.py` (not exercised in this step):** 1-8 workers and parallelism 1-4 per run (`:333-336`); `deadline_seconds` at most 3600 per worker (`:390`); `max_turns` 1-8; a new session id and a new branch per dispatch (`:357-372`); the base is the **invoking tree's HEAD** (`:426`); `prepare` creates each worker's tree itself with `coord worktree new` (`:445`); the contract's `owner` must equal `AGENT_SESSION` and be the **live designated leader** (`:330-332`, `:708-710`: "the runner never pins or steals leadership"); each prompt is a completed compile-audit id (CO-S0, `:410-412`).

Consequences:
- Only `leader-e1e4` can dispatch through the runner while it holds the lease (DR-1).
- An external dispatch is at most about 55 minutes (Grok about 20). A larger slice is cut into dispatches that each end at a commit.
- A follow-on dispatch (green after red) is prepared from a tree whose HEAD is the previous dispatch's branch tip. The runner reads the base from the invoking tree (`:252`, `:426`).
  - *assume:* invoking from a linked tree works. **Confirm** at Q0 by preparing one qualification run from a linked tree. **If false,** the follow-on runs as a Claude Sonnet sub-agent in the same tree.
  - The current Codex wrapper always `cd`s to the primary checkout. This is part of B-1.

## Artifact classes

The registry already covers this work's derived and append-only files. **No new entry is needed.** Every regenerate command below was run by this plan or its precedent before it was written; `docs-graph.py derive` ran in this step.

| path / pattern | class | mechanism | coordination needed |
| --- | --- | --- | --- |
| `docs/docs-index.js` | derived | `python docs/ai-forward-pack/scripts/docs-graph.py derive` (run 2026-10-03 through `coord regen`, exit 0) | **none** |
| `docs/audit/audit-data.js`, `docs/audit/index.html` | derived | `python docs/ai-forward-pack/scripts/audit-log.py --root docs --project x-harness-x-model-bench render` | **none** |
| `docs/specs/harness-bench.html` | derived | `python tools/render-doc-html.py` | **none** |
| `.claude/skills/{start-benchmark,new-bench-task}/**`, `.agents/skills/{…}/**` | derived | `python tools/sync-skills.py` | **none** |
| `docs/audit/audit-log.jsonl`, `docs/audit/change-log.jsonl`, `docs/notes/rulings.md` | register | union merge | **none.** Joins are real merges, never squash (REG-A: a squash merge drops register lines) |
| `runs/`, `.tools/` | ignored | not tracked | **none** |
| `bench/campaigns/<id>/ledger.jsonl` (new) | **authored, single writer**, never `register` | a union merge would interleave rows and break `seq` / `prev_hash` (ADR-0016 §1: "follows ADR-0006's physical rules exactly") | yes: only the session that runs `bench campaign` writes it (the Leader at the E1 demo; tests write under `tmp_path`) |
| `bench/campaigns/<id>/{identity,prereg,power}/<hash>.json`, `bench/discrimination/<task>/<tv16>-<id16>-<platform>.json` (new) | authored, create-only, content-addressed | `create_once` compare-and-refuse (ADR-0016 §2a). Distinct names never conflict. The same name with different bytes is a determinism defect, never a merge | per task folder: the track that owns `tasks/<ID>/` produces its task's record |
| `bench/catalog-freeze.yaml` | authored, **Leader-owned** | R-86: "`bench/catalog-freeze.yaml` stays Leader-owned" | yes: the Leader runs `python tools/freeze_catalog.py` at the 0.7 freeze join |
| `docs/lessons/defect-classes.md` | authored, **Coordinator-owned** | entries are edited, not only appended, so `register` would corrupt them | tracks report class text; the Coordinator commits it at the join |
| `docs/design/eval-*.md` (new; one per slice) | authored | one author track per file | none beyond one owner |
| `src/harness_bench/**`, `tests/**`, `tasks/**`, `bench/**` (other), `models/**`, `tools/**`, `docs/**` (other) | authored | **one owner per file per phase** (Tracks table and the hub-file table below) | **yes: this is the only real contention** |

### Hub files: one owner per phase

Several tracks would each add a few lines to these files. Two authors on one file is a wrong boundary, so each hub file has exactly one owner per phase. New logic goes into new modules. Another track that needs a line in a hub file sends a seam request (`coord request --to <owner>`), and the owner writes it. Every hand-over between phases is a join on `main`, never a concurrent edit.

| hub file | E1 owner | E2 owner | E3 owner | E4 owner | why it is a hub |
| --- | --- | --- | --- | --- | --- |
| `src/harness_bench/engine.py` | X-D (launch recheck, ADR-0017 §7) | X-J1 | X-K1 (**starts only after X-J1 joins**) | — | the kickoff: "engine.py is touched by A, D, J and K". X-A1 needs no engine edit: ADR-0014 §4 says "A new plan's `cells` list *is* the launch order (no engine change)" |
| `src/harness_bench/cli.py` | X-C | — | X-K2 | — | new commands from A, C, E (E1) and K (E3) |
| `src/harness_bench/config.py` | X-A1 | — | X-A3 | — | matrix/2 validation (A); EV-1 and EV-7 checks live in `readiness.py` (X-E), called through a hook line |
| `src/harness_bench/errors.py` | X-D | X-J1 | X-K1 | X-LG | new HB codes from every track. W0 reserves the ids per track |
| `src/harness_bench/identity.py` (classification table) | X-D | X-J1 | X-K1 | X-LG | ADR-0017 §1: "a test that every `src/` file has a class". W0 lists every planned new module and its class, so X-D seeds them all |
| `src/harness_bench/archive.py` | X-B2 | X-J1 | — | — | crash-atomic final archive (E1), then snapshots (E2) |
| `src/harness_bench/views.py`, `ledger.py` | X-A1 (`views.py:525` accessor); X-C (`ledger.py`, generalised for a campaign path) | X-J1 (snapshot key part) | — | — | record-model changes |
| `src/harness_bench/grade/runner.py` | X-F | X-J2 | — | X-LG | the grader registry |
| `src/harness_bench/grade/property.py`, `grade/bench_check.py` | X-F | — | — | X-LB (loopback fake) | one generic runner; E4 adds loopback behind the same `PropertyCheck` contract |
| `src/harness_bench/procs.py`, `egress.py` | X-F (`spawn(..., console=False)`; the `task canary` class) | — | — | — | — |
| `src/harness_bench/profiles.py` | X-E (`synthetic` profile) | X-J2 (per-turn solution trees) | — | — | — |
| `src/harness_bench/report/html.py` | X-H2 (section 3 hook) | — | X-A3 (header per arm) | — | — |
| `src/harness_bench/report/pack_improvement.py`, `board.py`, `report/summaries.py` | — | — | X-A3 (comparison pairs **and** the ADR-0019 item 4 `_passed` fix) | — | ADR-0014 §5 and ADR-0019 item 4 both edit `pack_improvement.py`. **[refined]** One E3 owner takes both |
| `src/harness_bench/plan.py` | X-A1 | — | X-A3 | — | arms, rings, comparisons |
| `src/harness_bench/status.py` | X-C | — | X-K2 | — | campaign view (E1), then `last_progress_at` and alarm (E3) |
| `src/harness_bench/lifecycle.py`, `models/run_lifecycle.tla` + `.cfg` | — | W1-J (model and TLC, **before the build**), then X-J1 (`lifecycle.py`) | W1-K (`NoResumeAfterStop`), then X-K1 | — | ADR-0015 §7: "each with a seeded-bug variant TLC must reject **before the build starts**" |
| `bench/metrics.yaml` | X-G1 (all ten 0.7.dev metrics) | — | X-G3 (freeze prep) | — | one catalog (ADR-0019) |
| `bench/bom.yaml` | **W0 (Coordinator)** adds all ten property-task ids as `stub` entries | each task track edits only its own entry | ← | ← | stubs make each later edit a disjoint hunk |
| `tests/test_engine.py`, `test_cli.py`, `test_config.py`, `test_plan.py`, … | follow their source file's owner in each phase | | | | |
| `tests/mutations/<module>.json` | the module's owner in that phase | | | | |
| `tasks/README.md` (property-task contract section) | W0 (Coordinator) | seam request | ← | ← | the contract is a Wave 0 item |

### Guards over shared surfaces (GO14a)

For every shared surface, each other track's guard is listed. It is shown to be jointly satisfiable with what the owner may write. Every scan-shaped guard states its root, recursion, token set and allowlist. **W0 freezes these four fields.** A later change that widens a guard reddens other tracks at the join. A change that narrows it stays green.

| shared surface | guard (quoted, with citation) | scan: root · recursion · tokens · allowlist | jointly satisfiable because |
| --- | --- | --- | --- |
| every `src/` reader of the arm | ADR-0014 §2: "No reader reads `pack` directly after this change; a guard test greps for it." (owner X-A1) | root `src/harness_bench/` · recursive · `["pack"]`, `.get("pack"`, `.pack` on a cell or view row · allowlist **E1**: `plan.py` (the accessors and the `Cell.id` ingredient at `plan.py:75`) plus the E3-migrated readers `board.py`, `report/pack_improvement.py`, `report/html.py`, `report/summaries.py`. **E3**: X-A3 narrows the allowlist to `plan.py` | X-C, X-E, X-H2, X-J1 and X-K1 read arms only through `cell_arm` / `arm_pack`. The A → C, E, H edges land the accessors first. The E3 readers stay listed until X-A3 migrates them. *assume:* the legacy readers render a non-`on` arm id (the E1 pilot's `off` and `candidate`) without raising. **Confirm:** X-INT's E2E renders the full report of a two-arm (`off`, `candidate`) run. **If false,** X-A3's reader migration moves into E1 |
| every new `src/` file | ADR-0017 §1: "The classification table lives in code, once, with a test that every `src/` file has a class." (owner X-D) | root `src/harness_bench/` · recursive · every `*.py` path · no allowlist | W0 lists every planned new module and its class (`run` / `grade`), and X-D seeds the whole list. An unplanned module is a seam request to that phase's `identity.py` owner |
| campaign, identity, power, verdict, gate and property-grader modules | architecture amendment table: "ADR-0011 C5/C9 import lint · extended to the campaign, identity, power, verdict, gate and property-grader modules" (owner X-D, in `tests/test_architecture.py`) | root: those modules' files (named in W0) · non-recursive · gateway imports (`harness_bench.gateway`, `from .gateway`) · no allowlist | none of these modules needs the gateway (ADR-0020 §5: pure functions; ADR-0018: no model call) |
| the grading environment | ADR-0018 §9: "The allowlist is one constant moved to a shared grading module so the three graders cannot drift (DM7)." (owner X-F) | root `src/harness_bench/grade/` · recursive · `HOST_ENV =` · allowlist `grade/_env.py` | in E1, only X-F edits `correctness.py` and `mutation.py`. X-A1 edits only `grade/_changes.py:84` |
| campaign records during grading | ADR-0018 §11(b): "after every grading pass of a campaign run, and before every `bench campaign` command, `bench campaign verify` checks the campaign ledger's hash chain, that every content-addressed file's name equals its hash, and `git status --porcelain bench/campaigns bench/discrimination`" | not a scan | X-C implements `verify`. The after-grading hook line lives in `grade/runner.py` (X-F), by seam request X-C → X-F |
| "exists means complete" | ADR-0015 §5a: "copy into a temporary sibling folder (`<name>.tmp-<pid>`), fsync the files and the folder, verify the rows against the copy, then `os.rename` it to the final name" | not a scan | X-J1's snapshot write reuses X-B2's primitive. Spike E1-NTFS: "a directory cannot be opened for fsync at all (PermissionError), so ADR-0015 section 5a's 'fsync the folder' is POSIX-only" — X-B2's design states the Windows branch |
| the suite | existing `tests/test_default_suite_is_offline.py` (SUITE-A) and `tests/test_no_leftovers.py` | existing | X-INT's E2E and any real-cell test carry the credentials marker. The demo grid runs only under the Leader |

## Tracks

**Model pins (every row; never a default):** Sonnet = `claude-sonnet-5` (Agent tool `model: sonnet`; served id read back at Q0). Opus = `claude-opus-5-5`. Codex = `gpt-6.1-sol` on codex-cli 0.160.0 (after B-1). Agy = `gemini-3.8-flash-high`. Grok = `grok-4.7`, `--reasoning-effort high`. **Every track's fallback is Claude Sonnet after an Owner review.**

**Budgets are Inferred.** Phase-1 tracks spent 88-415 tool calls and 0.25-5.4 h, and the planned wall estimates were 2-14 times too high (`coordination-phase1-finish-run.md`). Budgets here are calls · context per dispatch · dispatches · wall. Planned and actual times are recorded per track (GO19).

**Common exit evidence for every implementation track (the join gate):**
- red-first commits, each failing test node recorded with its red SHA and the failing line;
- `uv run ruff check src tests tools`;
- the full non-credential suite;
- `python tools/mutate_check.py --touched main` (killed, or a recorded reason);
- `python docs/ai-forward-pack/scripts/docs-graph.py validate`;
- for a join that touches `grade/`: the gate ring and stamp renewal, once per batch;
- CI green on Windows and macOS after each push.

The Coordinator re-runs at least one red SHA per track at the join. A green worker report is not evidence that its contents passed.

### Wave 1: design slices and the spike

Each design slice produces `docs/design/eval-<slice>.md` by `/design-slice` (patterns named, contracts cited, Simplifier versus Patterns Expert). Each passes its own gate line. Authors never clear their own veto.

| track | owns (authored) | depends on | tier | fan-out cap | budget | exit evidence | harness |
| --- | --- | --- | --- | --- | --- | --- | --- |
| W1-A arms v2 | `docs/design/eval-arms.md` | W0 | T2 | 0 | 120 calls · 180k · 1 · 1.5 h | gate line with Patterns, Simplifier and Test Architect PASS; the grid-4 re-plan equivalence test (EV-17) specified by node id; the E1 / E3 split stated | Claude Code · Sonnet |
| W1-B crash-atomic publish | `docs/design/eval-atomic-publish.md` | W0 | T2 | 0 | 100 · 150k · 1 · 1 h | gate PASS incl. Security and Distributed Systems (hard vetoes); the D1 and D3 red tests named; the Windows no-directory-fsync branch stated (spike E1-NTFS); the defect class text for "exists means complete" | Claude Code · Sonnet |
| W1-C campaign record + `bench campaign` | `docs/design/eval-campaign-record.md` | W0 | T2 | 0 | 140 · 180k · 1 · 2 h | gate PASS incl. Security and Distributed Systems; lock-then-read for every command (ADR-0016 §1, council D6); tamper tests named | Claude Code · Sonnet |
| W1-D engine identity + freeze | `docs/design/eval-identity.md` | W0 | T2 | 0 | 110 · 150k · 1 · 1.5 h | gate PASS incl. SRE; the run / grade classification table reviewed (ADR-0017 follow-up "load-bearing"); the launch recheck and `identity_check_ms` | Claude Code · Sonnet |
| W1-E discriminate + synthetic + readiness | `docs/design/eval-discriminate.md` | W0 | T2 | 0 | 130 · 180k · 1 · 1.5 h | gate PASS incl. Security; the SCAN-A red fixture named; the synthetic agent mechanism (a stdlib ACP fake behind `Launcher`, so no `engine.py` edit, Inferred; an engine edit is a seam request to X-D) | Claude Code · Sonnet |
| W1-F hidden-check runner + property grader | `docs/design/eval-property-grader.md` | W0 | T2 | 0 | 160 · 200k · 1 · 2.5 h | gate PASS with **Security & Identity as hard-veto reviewer**; the four ADR-0018 red tests and the race test named; the job-alone constraints adopted ("starts the check with `sys._base_executable` ... and `DETACHED_PROCESS`", plus the one-byte ack, spike E1-S3) | Claude Code · **Opus** (`claude-opus-5-5`) |
| W1-G catalog 0.7 | `docs/design/eval-catalog-0-7.md` | W0 | T2 | 0 | 90 · 150k · 1 · 1 h | gate PASS; the ten metric entries with anchors (R-79 forms); the scenario-7 pass rule for G2; the US-4 control; the append-only `corrected_from` record | Claude Code · Sonnet |
| W1-H power, verdicts, gates, section 3 | `docs/design/eval-power-verdicts.md` | W0 | T2 | 0 | 120 · 180k · 1 · 1.5 h | gate PASS; reference cases 93 / 53 / 115 with the independent formula and the seeded-wrong variant; the verdict and dominance tables with boundary rows; section 3's E1 shape | Claude Code · Sonnet |
| W1-I security tasks S1, S2 | `docs/design/eval-security-tasks.md` | W0 | T2 | 0 | 140 · 180k · 1 · 2 h | gate PASS incl. Security; two real codebases on different bases (DR-T1); the latent requirement; in-process probes (injection, authz bypass, secret leak with a `BENCHCANARY-` value); reference and naive solutions; expected values with provenance (GLD-A) | Claude Code · Sonnet |
| W1-J multi-turn | `docs/design/eval-multi-turn.md`, `models/run_lifecycle.tla`, `models/run_lifecycle.*.cfg` | W0 | T2 | 0 | 180 · 200k · 2 · 3 h | gate PASS incl. Distributed Systems and SRE; **TLC run** with `PromptOncePerTurn`, `SnapshotBeforeNextTurn`, `NoSnapshotInFlight`, `CrashedTurnPredicate`, `ArchiveExistsMeansComplete`, each seeded variant **rejected** (output in the doc). **[refined]** The TLA+ work is part of this design, not a separate track, because ADR-0015 §7 requires it "before the build starts" | Claude Code · Sonnet |
| W1-K resume, liveness, alarm | `docs/design/eval-resume.md` | W0, W1-J (the TLA+ files) | T2 | 0 | 140 · 180k · 1 · 2 h | gate PASS incl. Distributed Systems and SRE; every ADR-0021 §4 row mapped to a kill-then-resume test; `NoResumeAfterStop` added to the model **after W1-J**, with TLC output; the alarm channel chosen (ADR-0021 §7: "The channel is chosen at `/design-slice`"); the drill is out of scope | Claude Code · Sonnet |
| W1-L remaining property tasks | `docs/design/eval-property-tasks.md` | W0 | T2 | 0 | 160 · 200k · 2 · 3 h | gate PASS; for resilience ×2, no-guessing ×2, simplicity ×2 and rework ×2: base codebase, latent requirement, hidden check, reference and naive, expected values; which graders are new (`verified_before_use`, `hallucinated_symbol_errors`, diff statistics) | Claude Code · Sonnet |
| SP-LB loopback firewall spike | `tools/spikes/s_lb_loopback.py`, `docs/notes/spike-s-lb-loopback.md` | W0 | T1 | 0 | 40 · 100k · 1 · 0.5 h + operator session | the procedure in the architecture doc run on Windows, **operator present**: no prompt and no new rule for the loopback bind, **and** the `0.0.0.0` positive control fires | Claude Code · Sonnet (script); the operator runs it |

**Lens reviewers (Adversary Mode).** One reviewer session per lens, continued by `SendMessage` across batches, and replaced by a fresh session past 150k context. Each issues one gate line per slice, so every slice still has its own gate. **[refined]** This replaces about 45 per-slice reviewer sessions. A lens reviewer that reads all of its slices also sees where two designs disagree at a seam (E2E-D).

| reviewer | lens | slices | harness |
| --- | --- | --- | --- |
| RV-PAT | Patterns Expert | all twelve | Claude Code · Sonnet |
| RV-SIM | Simplifier (soft veto) | all twelve | Claude Code · Sonnet |
| RV-TA | Test Architect (hard veto) | all twelve | Claude Code · Sonnet |
| RV-SEC | Security & Identity (hard veto) | B, C, E, F, I | Claude Code · Sonnet |
| RV-DS | Distributed Systems (hard veto) | B, C, J, K | Claude Code · Sonnet |
| RV-SRE | SRE | D, J, K | Claude Code · Sonnet |

### Wave 2: implementation (red first, federated)

A track starts when its design gate has passed **and** its dependencies have joined `main`.

| track | owns (authored) | depends on | tier | fan-out cap | budget | exit evidence | harness |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **E1** | | | | | | | |
| X-G1 catalog 0.7.dev | `bench/metrics.yaml`, `tests/test_catalog_version.py` | W1-G | T2 | 0 | 40 calls · 100k · 2 (red, green) · 0.7 h | the ten metrics validate under `0.7.dev`; every 0.6 metric unchanged | Grok · `grok-4.7` high |
| X-B1 create_once | `src/harness_bench/atomic.py` (new), `tests/test_atomic.py` | W1-B | T2 | 0 | 40 · 100k · 2 · 0.7 h | D3 tests: exists → equal no-op, different → refused; crash before link → no final file; `os.link` `FileExistsError` path (spike E1-NTFS) | Grok · `grok-4.7` high |
| X-A1 arms (two arms) + ring plumbing | `plan.py`, `config.py`, `workspace.py`, `views.py`, `grade/_changes.py`, `bench/rings/pilot.yaml` (new), `tests/test_plan.py`, `test_config.py`, `test_workspace.py`, `test_views.py`, `tests/test_arms_guard.py` (new), `tests/mutations/plan.json` | W1-A | T2 | 0 | 220 · 200k · 3 · 3 h | the grid-4 re-plan equivalence (EV-17: same set and same `cell_id`s); `bench plan` refuses a launch-balance violation (ADR-0014 §4: "`bench plan` asserts the bound and refuses otherwise"); per-arm US-9; `--arm role=source@commit` binding with an unbound role refused; the pack-reader guard green with its E1 allowlist | Codex · `gpt-6.1-sol` (after B-1; until then the fallback) |
| X-D identity + launch recheck | `identity.py` (new), `engine.py` (E1), `errors.py` (E1), `tests/test_identity.py` (new), `tests/test_engine.py` (E1), `tests/test_architecture.py` (the import-lint module list), `tests/mutations/engine.json` (E1) | W1-D, W0 (the module list) | T2 | 0 | 200 · 200k · 3 · 3 h | every `src/` file classified; the differ names `grade/formal.py changed`; ADR-0017 §7, quoted: "The engine recomputes the run-side part of the manifest when a campaign run starts and again before each `cell.launch_intent`" — red test of a drifted file stopping launch with `engine identity drift`; `identity_check_ms` on the launch span | Codex · `gpt-6.1-sol`. **[refined]** Routed to Codex, not Agy: it is the E1 owner of `engine.py` (kickoff: "engine-core changes ... to Codex") |
| X-B2 crash-atomic archive | `archive.py` (E1), `tests/test_archive.py`, `tests/mutations/archive.json` | W1-B | T2 | 0 | 120 · 150k · 2 · 1.5 h | **red first against today's `archive_cell`:** kill during an archive copy, then resume completes without `HB-USR-002` (D1); a `*.tmp-*` sibling is redone | Agy · `gemini-3.8-flash-high` |
| X-H1 power, verdicts, dominance, gates | `power.py`, `verdicts.py`, `gates.py` (new), `tests/test_power.py`, `test_verdicts.py`, `test_gates.py` (new), `tests/mutations/power.json`, `verdicts.json` | W1-H, X-G1 | T2 | 0 | 160 · 120k · 6 (each about 20 min: power red / green; verdict red / green; dominance + pilot gate) · 2.5 h | 93 / 53 / 115 within ±1; MDE within 0.005; independent formula with literal z; seeded-wrong variant fails; verdict and dominance tables with boundary rows; coverage simulations in the slow ring | Grok · `grok-4.7` high |
| X-F property grader | `grade/property.py`, `grade/bench_check.py`, `grade/_env.py` (new), `grade/correctness.py`, `grade/mutation.py`, `grade/runner.py` (E1), `procs.py`, `egress.py`, `tests/test_property_grader.py` (new), `tests/test_procs.py`, `tests/test_egress.py`, `tests/fixtures/property/**` (new), `tests/mutations/property.json` | W1-F, X-G1 | T2 | 0 | 260 · 200k · 3 · 4 h | **red first:** `test_property_check_env_excludes_credentials`, `test_deliverable_cannot_write_result_pipe`, `test_forged_result_via_duplicated_handle_is_tampered`, `test_check_killed_before_write_is_tampered`, `test_forged_write_racing_deliverable_exit_yields_two_documents`; check-bound, check-tamper and seeded-suspend tests; a re-grade of one archive is identical (EV-2) | Claude Code · Sonnet (security-sensitive) |
| X-I security task S1 | `tasks/S1/**` (id fixed in W0), its `bench/bom.yaml` entry | W1-I, W0 (stub) | T2 | 0 | 200 · 200k · 2 · 3 h | `bench validate` passes the EV-1 contract; the reference passes its hidden tests; the naive passes the functional tests and fails a probe (run through X-F's runner once it joins); no listed term appears in `prompt.md` | Claude Code · Sonnet |
| X-C campaign record + CLI | `campaign.py` (new), `ledger.py` (E1), `cli.py` (E1), `status.py` (E1), `tests/test_campaign.py` (new), `tests/test_cli.py`, `tests/test_status.py`, `tests/mutations/campaign.json` | W1-C, X-B1, X-D, X-H1, X-A1 | T2 | 0 | 260 · 200k · 4 · 4 h | states and idempotency (same content → no-op; different → refused, naming the item); lock-then-read; ledger tamper tests; `bench campaign verify`; `status --json` schema-bound; cli wiring for A, C and E (seams) | Agy · `gemini-3.8-flash-high` |
| X-E discriminate + synthetic + readiness | `discriminate.py`, `readiness.py` (new), `profiles.py` (E1), `bench/profiles/synthetic.yaml` (new), the synthetic agent script (path fixed in W1-E), `tests/test_discriminate.py`, `tests/test_readiness.py` (new), `tests/fixtures/discrimination/**` incl. the SCAN-A red fixture | W1-E, X-A1, X-B1, X-D, X-F, X-G1, X-I | T2 | 0 | 240 · 200k · 3 · 3.5 h | the discrimination record for S1 through the engine path (EV-7); the SCAN-A fixture is red under readiness, naming the metric, the expected and the observed value; read-time reconciliation fails on a stale copy (ADR-0016 §4); `synthetic` excluded from leaderboards | Claude Code · Sonnet (integration) |
| X-H2 report section 3 | `report/campaign_section.py` (new), `report/html.py` (E1), `tests/test_report_campaign.py` (new) | W1-H, X-H1, X-C | T2 | 0 | 120 · 150k · 2 · 1.5 h | one verdict renders, with the EV-20 header; a non-campaign run's report golden is unchanged (EVU-4); "exploratory" labelling under 0.7.dev | Agy · `gemini-3.8-flash-high` |
| X-INT E1 E2E | `tests/e2e/test_e1_walking_skeleton.py` (new), `tests/e2e/conftest.py` (E1) | all E1 tracks | T2 | 0 | 100 · 150k · 1 · 1.5 h | the E1 phasing row's E2E list green on the joined `main` (the real cells are credential-marked); the arm-reader *assume:* confirmed or refuted | Claude Code · Sonnet |
| **E2** | | | | | | | |
| X-J1 multi-turn engine | `driver.py`, `engine.py` (E2), `archive.py` (E2), `lifecycle.py`, `ledger.py` (E2), `views.py` (E2), `errors.py` (E2), `identity.py` (E2), their tests, `tests/fake_acp_agent.py`, `tests/mutations/{engine,driver}.json` | W1-J (TLC passed), E1 done | T2 | 0 | 320 · 200k · 5 · 5 h | driver open / send turn / close; stdin closed only after the last turn; per-turn `prompt_sent` through the ack barrier; a create-once snapshot before turn 2; kill in each turn state; EV-4 turn-2-not-reached; a seeded suspend in turn 2 gives `host_suspended`; a legacy single-turn archive verifies unchanged; lifecycle conformance against the new invariants | Codex · `gpt-6.1-sol` |
| X-J2 rework grader + per-turn synthetic | `grade/rework.py` (new), `grade/runner.py` (E2), `profiles.py` (E2), the synthetic agent (E2), `tests/test_rework.py` (new), the two-turn case in the profile qualification suite | W1-J, W1-L, X-J1 (contract only until it joins) | T2 | 0 | 160 · 180k · 2 · 2.5 h | `rework_ratio` on the turn-1 snapshot and the final tree; synthetic cells apply per-turn solution trees | Agy · `gemini-3.8-flash-high` |
| X-RW rework tasks | `tasks/<RW1>/**` (E2), `tasks/<RW2>/**` (E4), their BOM entries | W1-L, W0; the records need X-J1 and X-J2 | T2 | 0 | 200 · 200k · 2 per task · 3 h per task | each task valid under EV-1; the reference scores 1 and the naive 0, through the engine; the ceiling separates them (EV-4) | Claude Code · Sonnet |
| **E3** | | | | | | | |
| X-A3 three arms, rings, readers | `board.py`, `report/pack_improvement.py`, `report/html.py` (E3), `report/summaries.py`, `plan.py` (E3), `config.py` (E3), `bench/rings/pack-regression.yaml` (new), their tests and goldens | W1-A, W1-G, E1 done | T2 | 0 | 240 · 200k · 3 · 3.5 h | three-arm plans; EV-17 launch balance under 5 %; EV-15: a comparison of two ring hashes is refused, naming the differences; the board and pack section per comparison pair, with legacy goldens unchanged; ADR-0019 item 4 (missing `pass_at_1` is NOT_RECORDED) with its defect class "absence read as failure"; the pack-reader allowlist narrowed to `plan.py` | Agy · `gemini-3.8-flash-high` |
| X-G3 scenario-7 pass@1 + 0.7 freeze prep | `grade/formal.py`, `tasks/G2/task.yaml` (the pass rule), `tests/fixtures/catalog/0.7/**`, `tests/test_grade_formal.py` | W1-G, X-A3 (the `_passed` fix) | T2 | 0 | 80 · 120k · 3 · 1.2 h | `pass_at_1` recorded under the declared rule; the US-4 control grades the frozen grid-3 and grid-4 fixtures under 0.7 with every 0.6 value unchanged (EV-10). **The Leader** runs `python tools/freeze_catalog.py` at the join (R-86) | Grok · `grok-4.7` high |
| X-K1 resume (engine) | `resume.py` (new), `engine.py` (E3), `errors.py` (E3), `identity.py` (E3), `lifecycle.py` (E3), `tests/test_resume.py` (new), `tests/test_engine.py` (E3) | W1-K, **X-J1 joined**, X-D | T2 | 0 | 280 · 200k · 4 · 4.5 h | kill in each state, then resume, for **every row of ADR-0021 §4**, including the per-turn rows and the turn-1 snapshot-crashed row; refusals after a stop, a live lock, a drifted identity and a failed verify; `segment.abandoned`; the per-launch disk check (ADR-0021 §8) | Codex · `gpt-6.1-sol` |
| X-K2 liveness + alarm | `status.py` (E3), `cli.py` (E3), `alarm.py` (new), the runbook entry (path fixed in W1-K), `tests/test_status.py` (E3), `tests/test_alarm.py` (new) | W1-K, E1 done | T1 | 0 | 140 · 150k · 2 · 2 h | ADR-0021 §7, quoted: "`bench status <run_id> --alarm-after <seconds>` exits non-zero, naming the cause, when the heartbeat is stale **or** `now − last_progress_at` exceeds the threshold while cells are pending" — the stale-progress fixture exits non-zero; `last_alarm_check_at` warning; the alarm channel built (the drill acceptance is out of scope) | Agy · `gemini-3.8-flash-high` |
| **E4** | | | | | | | |
| X-LB loopback fake harness | `grade/property.py` (E4), `grade/bench_check.py` (E4), `tests/test_property_loopback.py` (new) | **SP-LB passed**, W1-L, E1 done | T2 | 0 | 160 · 180k · 2 · 2.5 h | EV-3 parallel-port isolation; hang-is-measured; listeners bind the literal `127.0.0.1` and assert `getsockname` | Claude Code · Sonnet (security-adjacent) |
| X-LG property graders | `grade/process.py` or new grader modules (named in W1-L), `grade/_changes.py` (E4), `grade/runner.py` (E4), `errors.py` (E4), `identity.py` (E4), their tests | W1-L, E1 done | T2 | 0 | 180 · 180k · 3 · 3 h | `verified_before_use` from tool-call order; `hallucinated_symbol_errors`; `size_vs_reference`, `new_abstractions`, `new_dependencies`; EV-6: no line counted twice with `scope_creep` | Agy · `gemini-3.8-flash-high` |
| X-RS resilience tasks ×2 | `tasks/<RS1>/**`, `tasks/<RS2>/**`, their BOM entries | W1-L, X-LB | T2 | 0 | 200 · 200k · 2 per task · 3 h per task | EV-1, EV-3; the reference 1 and the naive 0 through the engine | Claude Code · Sonnet |
| X-NG no-guessing tasks ×2 | `tasks/<NG1>/**`, `tasks/<NG2>/**` | W1-L, X-LG | T2 | 0 | as X-RS | EV-1, EV-5 (renamed member, changed default, true contract readable) | Claude Code · Sonnet |
| X-SM simplicity tasks ×2 | `tasks/<SM1>/**`, `tasks/<SM2>/**` | W1-L, X-LG | T2 | 0 | as X-RS | EV-1, EV-6 | Claude Code · Sonnet |
| X-I (S2) second security task | `tasks/S2/**` | W1-I, E1 done | T2 | 0 | as X-I | EV-1, EV-2 on a second codebase. **[refined]** Moved from E1 to E4: the E1 phasing row lists "Second property task" under *Mocked / stubbed* | Claude Code · Sonnet |
| **Convergence** | | | | | | | |
| X-CV convergence | `tests/test_resume_table.py` (new, the whole §4 table), `docs/proof/eval-campaign-convergence.md` (new), `bench/discrimination/**` (the final ten) | E2, E3, E4 joined | T2 | 0 | 120 · 180k · 1 · 2 h + machine time | the whole ADR-0021 §4 table green; TLC with every ADR-0015 §7 invariant and `NoResumeAfterStop`; **all ten discrimination records produced at the final engine identity** (synthetic cells, no model spend); `bench validate` ready for all ten | Claude Code · Sonnet; the records run under the Leader |

### Track assignment detail

| track group | doorbell | deadline per dispatch | termination | fallback |
| --- | --- | --- | --- | --- |
| Grok (X-G1, X-B1, X-H1, X-G3) | not recorded | 1,200 s (runner `deadline_seconds`) | each dispatch ends at one commit (red-only or green-only); the track ends at its exit evidence or its budget, with a written report | Claude Code · Sonnet, after an Owner review |
| Codex (X-A1, X-D, X-J1, X-K1) | not recorded | 3,300 s | as above; at most 2 concurrent | as above; also the interim route while B-1 is open (DR-2) |
| Agy (X-B2, X-C, X-H2, X-J2, X-A3, X-K2, X-LG) | not recorded | 3,300 s | as above; at most 2 concurrent | as above |
| Claude Code sub-agents (all W1, RV-*, X-F, X-I, X-E, X-INT, X-RW, X-LB, X-RS, X-NG, X-SM, X-CV) | n/a (in-session) | the harness's own, plus the budget in the row | the budget in the row; past it, the Coordinator re-plans | a fresh Sonnet session from the retained brief |

Every row: rules by `owner-fable` into `docs/notes/rulings.md`; leader epoch 13; `AGENT_SESSION=<the dispatch's session id>`; Grok launched with `XAI_API_KEY` removed.

### Why each track earns the multiplier (GO6, about 15 times the tokens of one session)

- **One session cannot hold this.** The work spans nine components, eight ADRs and ten authored tasks. The phase-1 track T1 alone reported about 600k tokens. That exceeds the 400k ceiling before E1 is half built. **Context hygiene** pays for every split.
- **Genuine independence** (disjoint owned paths, no data or decision edge once W0 is fixed):
  - W1-A to W1-L: one design doc each;
  - in E1, X-G1, X-B1, X-A1, X-D, X-F and X-I start together;
  - the E4 task tracks: one task folder each.
- **Machine time:** SP-LB (an operator session), the E1 demo's pilot and mini grid, and X-CV's ten synthetic discrimination runs.
- **Isolation:** the Codex workers run unsandboxed (`agent-full-access`), so each runs in its own tree.
- **Federation is a requirement, not a saving.** The kickoff routes coding across four harnesses. Each external dispatch carries a Sonnet fallback, so a harness failure costs a re-dispatch, not the plan.
- **Speed is last.** No rigor floor is traded for it. The lens-batched reviewers and the folded TLA+ work make the plan *cheaper* and *more rigorous* together (GO: a conjunction).

## Serial spine

| item | why it cannot be parallel | who owns it |
| --- | --- | --- |
| 0. The Leader keeps the lease alive (renewal loop; TTL cap 900 s) and reads worker mail at every join | every runner dispatch and every merge checks the live designation (`coord-runner.py:708-710`). An expired lease stops all dispatch (COORD-C, COORD-B) | Leader |
| 1. **Q0: qualify the harnesses**: resolve B-1 (Codex); then one `coord-runner` smoke turn each for Codex 0.160.0 / `gpt-6.1-sol`, Agy 1.2.13 and Grok 1.0.41, as one run with parallelism 3; read back the served model on each; prepare one run from a linked tree (confirms the follow-on *assume:*); read back the served Sonnet id on the first Agent-tool dispatch | an unexercised mode is `unsupported`, and dispatching onto it is guessing. The result decides each external track's route. It fails GO5(c): one Leader lease and the dispatch path are an exclusive resource | Leader (dispatch); Coordinator (contracts and record) |
| 2. **W0: the seam-contracts doc** `docs/design/eval-seam-contracts.md`, plus the BOM and `task.yaml` stubs for the ten property-task ids, plus the property-task section of `tasks/README.md`. It fixes: the `PropertyCheck` input and result schema; the `create_once` and archive-rename API; `bench-plan/2` and `bench-matrix/2` (arms, comparisons, seed, `ring`); the campaign ledger event schema (ADR-0016 §1's closed enum); the identity-manifest schema and the run / grade class of **every planned new module**; the catalog 0.7 metric ids and the `expected:` format in `task.yaml`; the verdict input and output shape; the HB code ids reserved per track; the four GO14a guard fields above; and the task ids | until the interfaces are fixed, every track's result changes every other track's shape. That fails GO5(b) outright. It is one author's vocabulary, so it is serial by default | Coordinator (fresh session); the Owner rules on any dispute |
| 3. Owner rulings on DR-1 to DR-3 and any W0 dispute (R-87 onward) | a track that starts on an unanswered decision has no termination variant | Owner |
| 4. W1-J's TLC run, before X-J1 starts | ADR-0015 §7: "each with a seeded-bug variant TLC must reject **before the build starts**" | W1-J author; RV-DS clears |
| 5. E1 joins, in DAG order, then X-INT, then the **E1 demo** (UF-E1 on S1: readiness fails and is fixed → baseline → two-arm pilot ring → gate → prior and final power → pre-registration → mini grid → one verdict in section 3) | every later phase builds on E1 (the architecture's "E1 is the only serial prefix"). The demo needs the credentials host and the operator | Leader (joins, demo, operator); Coordinator (join review) |
| 6. `engine.py` in E2 and E3: X-J1 joins **before** X-K1 starts | two authors on `engine.py` is a wrong boundary. K's per-turn reconciliation rows read J's `turn_ended` and snapshot facts (the architecture's "the seam between E2 and E3 is ADR-0021 §4's per-turn rows"). X-K2, X-A3 and X-G3 run in parallel with X-J1 | Coordinator |
| 7. The 0.7 freeze: X-A3's `_passed` fix, then X-G3, then the Leader's `freeze_catalog.py` commit | ADR-0019 item 4 moves the 0.6 `board_golden`, recorded append-only. The freeze file is Leader-owned (R-86) | Leader |
| 8. X-CV: the convergence check, then the ten discrimination records at the **final** engine identity, then push and CI | a record is keyed by engine identity (ADR-0016 §4). Any `src/` change after a record supersedes it, so the final set is produced once, after the last code join | Coordinator (check); Leader (records, push, CI) |
| **Loop-back** | any `src/` change after its track has joined (an E2E or demo finding) reopens a small fix track under the owning phase's hub-file owner, with a red SHA. Phase 1 needed three loop-backs, so **six loop-back slots are budgeted** (about 100 calls each) | Coordinator |

## Seams

| from -> to | the request | resolved by |
| --- | --- | --- |
| X-C, X-E, X-H2 -> X-A1 | read the arm through `cell_arm(cell)` / `arm_pack(plan, arm)` | fixed in W0; the A → C, E, H edges land them first |
| X-A1, X-E -> X-C | `cli.py` wiring: `plan --arm role=source@commit`, `--matrix <ring>`; `discriminate`; `validate` calling `readiness.check`; the `_workspace_builder` pack per arm (`cli.py:145-148`) | X-C writes the lines on request (`coord request --to X-C`); signatures fixed in W0 |
| X-C -> X-F | the hook after a campaign run's grading pass that runs `bench campaign verify` (ADR-0018 §11(b)); `bench campaign` refuses while `grade.lock` is held | X-F adds the hook line; X-C owns `verify` |
| X-E -> X-A1 | `config.validate_repo` calls `readiness.check` for property tasks | X-A1 adds the line |
| every new-module track -> phase `identity.py` owner | a class row for the module | pre-seeded from W0's list; unplanned → seam |
| X-F, X-C, X-E, X-B2 -> X-D | new HB codes in `errors.py` | the ids are reserved in W0; X-D adds them in its first commit |
| X-E -> X-D | if the synthetic launcher needs an `engine.py` change | Inferred not needed (`Launcher` protocol, `engine.py:69-85`); if needed, X-D writes it before X-E's join |
| X-H2 -> X-C | the campaign header (EV-20): question, arms, prereg hash, baseline, fixes, MDE, power id | read through the ledger reader fixed in W0; built against fixtures until X-C joins |
| X-J1 -> X-B2 | the snapshot write uses the same temp-sibling-then-rename primitive | X-B2's API is fixed in W0; X-J1 calls it |
| X-K1 -> X-J1 | the per-turn reconciliation rows read `turn_ended{k}`, `cell.turn_snapshot_archived{k}` and `prompt_sent{k}` | serial spine 6: X-K1 starts on X-J1's merged code |
| X-K1 -> X-K2 | `bench run <run_id>` resume entry in `cli.py` (E3) | X-K2 writes the line |
| X-A3 -> X-G3 | the `_passed` fix lands before the formal `pass_at_1` rows exist | serial spine 7 |
| X-RW, X-RS, X-NG, X-SM, X-I(S2) -> W0 BOM stubs | edit only their own BOM entry and their own `tasks/<ID>/` | stubs make each a disjoint hunk |
| X-LB -> X-F (closed) | loopback behind the same `PropertyCheck` contract | W0's contract; X-F has closed by E4, so X-LB owns the files in E4 |
| any track -> Coordinator | a defect class (the archive "exists means complete" class, "absence read as failure") | reported as text; the Coordinator commits `docs/lessons/defect-classes.md` |

## Struck tracks

| track | why it was not worth its multiplier |
| --- | --- |
| Probe N4 (a deliverable started by the check stays in the grading Job Object) | **already Verified.** `docs/notes/spike-phase1-probes.md` "N4: every harness process stays in the cell's Job Object [Verified]" (2026-09-23), and spike E1-S3 measured `{check, deliverable}` in the grading job while the deliverable ran (3 of 3). The architecture doc still lists it as open (finding F-1 of the E1 design); W0 cites the spikes |
| A separate TLA+ track for J | folded into W1-J. TLC must pass before the build, so it is a design-gate artifact, not a parallel build track |
| One reviewer session per (slice, lens), about 45 sessions | replaced by six lens reviewers, continued across batches. It is cheaper, and a lens that reads every slice sees cross-slice seam disagreements (E2E-D) |
| S2 in E1 | E1's phasing row puts the second property task under *Mocked / stubbed*. Moved to E4 |
| A W0 "seam stubs" coding track | the stubs are the contract doc plus the BOM and `task.yaml` stubs, written by the Coordinator in W0. Code stubs would be a second definition of each interface (DM7) |
| Splitting B into two designs | one design (W1-B) covers both `create_once` and the archive rename. Only the implementation splits, because the kickoff routes "B's helper" to Grok |
| A separate pack-regression-ring track | folded into X-A3: rings are `bench-matrix/2` files (ADR-0016 §6); there is no separate schema |
| G's `_passed` fix as its own track | folded into X-A3, which owns `pack_improvement.py` in E3. Two authors on that file would be a wrong boundary |
| Discrimination records per task track, as final evidence | a record made mid-phase is superseded by any later `src/` change (identity-keyed). Task tracks show discrimination through the engine as exit evidence; X-CV produces the committed final ten once |
| One task-authoring track per task (ten tracks) | grouped per property (two tasks, two sequential sessions per track), on the Simplifier's argument. The two tasks share a property's hidden-check shape |
| Merging X-K1 into X-J1 (one `engine.py` owner for E2 and E3) | kept apart (Tech Lead's casting vote): X-J1 alone is about 5 dispatches. A merged track would exceed the per-slice context ceiling, and serial spine 6 already removes the contention |

## Decision requests (for the Owner; the next ruling is R-87)

- **DR-1. Who invokes `coord-runner` for external dispatch?** The runner admits only "the live designated Owner; the runner never pins or steals leadership" (`coord-runner.py:708-710`), and the lease is the Leader's.
  - (a) The Leader invokes `prepare`, the qualification attestation, `run` and `status` for each dispatch. The Coordinator hands it a ready contract file and the compiled prompt ids. That is about 3-4 short calls per dispatch.
  - (b) The Leader hands the lease to the Coordinator for each dispatch window and re-pins it for merges. This churns epochs, blocks merges during windows, and every in-flight run refuses on the epoch change (`coord-runner.py:891`).
  - (c) Route all external work to Claude Sonnet sub-agents. This defeats the federation goal.
  - **Recommended: (a).**
- **DR-2. The Codex route while B-1 is open.**
  - (a) Hold the Codex tracks (X-A1, X-D) until the operator fixes the wrapper and Q0 qualifies 0.160.0 / `gpt-6.1-sol`.
  - (b) Run them on the qualified 0.156.0 / `gpt-6-sol` profile. This deviates from the kickoff's pin.
  - (c) Start X-A1 and X-D as Claude Sonnet fallbacks now, and route J1 and K1 to Codex once qualified.
  - **Recommended: (c)** if B-1 is not cleared when W1-A and W1-D pass their gates. X-A1 and X-D are on the E1 critical path. (b) is not recommended: it serves a model the kickoff did not pin.
- **DR-3. The E1 demo's pilot and mini-grid combo and k.** E1 runs one combo, 2 arms (`off`, `candidate`), a mini grid of 1 task × 1 combo × k reps, with the expected verdict `inconclusive (underpowered)`.
  - (a) The combo with the lowest measured mean wall per cell in grid-4, read from `runs/grid-4` at demo time, with k = 3.
  - (b) An operator-named combo and k.
  - **Recommended: (a)**, the cheapest real spend that still exercises the path. The operator confirms at the demo.

## Blockers on the operator

- **B-1. Codex is not qualified at the kickoff's pin.** The operator-approved wrapper exists at `C:/Users/malla/AppData/Local/Temp/claude/C--projects-x-harness-x-model-bench/c44c669c-d0a8-41c1-b4b5-8376f17cf0be/scratchpad/coord-runner.sh` (allow rule in `~/.claude/settings.json`). It pins:
  - `CODEX_PATH` to `.tools/harness/node_modules/@openai/codex-win32-x64/.../codex.exe`, measured **codex-cli 0.156.0**;
  - `CODEX_CONFIG` `{"model":"gpt-6-sol"}`;
  - `AGENT_SESSION=coord-opus-cq`, a retired seat that is not the lease holder, so the runner would refuse with `RUN-LEADER`;
  - a hard-coded `cd` to the primary checkout.

  It also lives in another session's scratchpad, which is the PIN-A shape (a pin resolved through a path another session owns). codex-cli 0.160.0 is installed globally (`codex --version`: `codex-cli 0.160.0`; its exe is under the npm global `@openai/codex/node_modules/@openai/codex-win32-x64/`). No runner run here has ever used 0.160.0 or `gpt-6.1-sol` (`.git/coord-runs`, 106 runs).

  **Operator action:**
  - approve a wrapper at a Leader-owned stable path that pins the 0.160.0 exe, `{"model":"gpt-6.1-sol","model_reasoning_effort":"high"}`, `AGENT_SESSION=leader-e1e4`, and the invoking tree rather than a fixed `cd`;
  - add its allow rule.

  Q0 then qualifies it with one smoke turn. Do not change `.tools/harness` (the cells' pinned build, part of the engine identity). *Untested:* whether codex-acp adapter 1.12.0 drives codex-cli 0.160.0. Q0 is the test.
- **B-2. Spike S-LB needs the operator present** to watch for a firewall dialog. It blocks only E4's loopback half (X-LB, then X-RS).
- **B-3. The E1 demo needs the operator** to walk UF-E1 (human validation) and to confirm DR-3's spend.
- **Not a blocker:** Agy moved from 1.2.3 to **1.2.13**. Q0 re-qualifies it without operator action unless it fails, in which case its tracks take the Sonnet fallback.

## Order of operations

| # | action | cost | why now |
| --- | --- | --- | --- |
| 1 | The Leader keeps its lease alive (renewal loop) and confirms epoch 13 with `coord leader who`. **No `coord leader pin`**: the Leader already holds the lease | 1 min | CO-L: every row carries this epoch |
| 2 | Leader convenes the Owner: DR-1, DR-2, DR-3 → R-87.. | 15 min | the dispatch path and the Codex route depend on them |
| 3 | Operator: B-1 (wrapper and allow rule) | operator time | Q0 cannot qualify Codex without it |
| 4 | **Q0**: the Coordinator writes one qualification contract (3 workers: codex, agy, grok; parallelism 3; deadline 600 s; a one-line commit to `docs/notes/qualify-worker.md`); the brief is compiled (`/compile`); the Leader runs `prepare` (from a linked tree), attests, then `run`. The Coordinator records enforced / observed-only / unsupported per harness and the served model ids | 30-60 min (Inferred) | never dispatch onto an unexercised mode; a failure routes that harness's tracks to the fallback |
| 5 | **W0** (fresh Coordinator session): the contracts doc, the BOM and `task.yaml` stubs, the `tasks/README.md` section; RV-PAT, RV-SIM, RV-TA, RV-SEC and RV-DS review it; the Owner rules on disputes | 3-4 h | serial spine 2 |
| 6 | **W1 batch a** (cap 6): W1-F (Opus), W1-G, W1-A, W1-B, W1-D, W1-I, each in a `coord worktree new` tree (`coord doctor` in each; never `coord install`); the reviewers gate each as it lands | 2-3 h | the E1 critical path: G → F → E |
| 7 | **W1 batch b**: W1-H, W1-C, W1-E, then W1-J, W1-K, W1-L and SP-LB as slots free up; **W1-J's TLC** before any X-J1 | 3-4 h; overlaps step 8 | designs touch no code, so batch b overlaps E1 implementation within the cap |
| 8 | **E1 implementation, by the DAG** (cap 6; at most 2 Codex, 2 Agy, 2 Grok): first X-G1, X-B1 (Grok), X-A1, X-D (Codex, or the DR-2 fallback), X-F, X-I (Sonnet); then X-H1 (Grok, after X-G1), X-B2 (Agy); then X-C (Agy, after X-B1, X-D, X-H1, X-A1); then X-E (Sonnet, after A, B1, D, F, G1, I); then X-H2 (Agy, after X-C). Each brief is compiled; the Leader dispatches external ones (DR-1) | 10-16 h wall (Inferred; critical path W1-G → X-G1 → X-F → X-E → X-INT) | starts each slice the moment its design passes and its dependencies join |
| 9 | Joins in completion order, each a real merge with the join gate; the Leader merges; the Coordinator re-runs one red SHA per track; derived files regenerate through the drivers | about 15 min per join | serial spine 5 |
| 10 | X-INT, then the **E1 demo** with the operator (DR-3), then report "E1 demo ready" | 2-3 h + grid time | Done-when 1; the first operator report |
| 11 | Coordinator hand-off: a fresh session for E2-E4 | 10 min | the 400k ceiling, per phase |
| 12 | **E2 ∥ E3 ∥ E4** (cap 6; at most 2 per external harness), priority to the longest chain: X-J1 (Codex) → X-K1 (Codex); in parallel X-A3 (Agy) → X-G3 (Grok) → the Leader's freeze; X-K2 (Agy); X-J2 (Agy, when an Agy slot frees); X-RW, X-LB (after SP-LB), X-LG, X-RS, X-NG, X-SM, X-I(S2) (Sonnet) | 12-20 h wall (Inferred; critical path X-J1 → X-K1 → X-CV) | serial spines 6 and 7 hold inside the phase |
| 13 | **X-CV**: the convergence check, the ten final discrimination records, the proof note; the Leader pushes; CI green on Windows and macOS; `docs-graph derive`; then `coord worktree cleanup` (reports only; removal is opt-in) | 2-3 h | Done-when 2-5 |

**Critical path (Inferred):** Q0 → W0 → W1-G / W1-F → X-G1 → X-F → X-E → X-INT → demo → X-J1 → X-K1 → X-CV. That is about **30-45 h wall** over several sessions. Phase-1 estimates were 2-14 times too high, so the Coordinator records planned against actual per track (GO19) and re-plans at each phase boundary.

**Termination.** Every track stops at its exit evidence, or at its budget with a written report of what remains. A track at its budget never continues on its own; the Coordinator re-plans. A finding with no test node and no red SHA is not closed. The fan-out cap is a circuit breaker: if it fires, that is a defect signal, not a reason to wait longer.

## Status

| | |
| --- | --- |
| **Completed** | layer measured (`coord doctor`, `pack-doctor`); the owed `docs/docs-index.js` regenerated (byte-identical; marker cleared); harness versions and the runner contract measured; this plan |
| **Remaining** | DR-1 to DR-3 (Owner); B-1 (operator); Q0; W0; Wave 1; E1 to its demo; E2-E4; convergence |
| **Best next action** | The Leader convenes the Owner on DR-1 to DR-3 and asks the operator for B-1. Then `/execute-with-coordination` starts at Q0 and W0 in a fresh Coordinator session |
