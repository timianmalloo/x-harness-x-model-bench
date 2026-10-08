---
id: coordination-finish
title: "Coordination plan - finish: the post-E4 backlog, the pack upstream, E5's preconditions and E5"
type: plan
status: proposed
owner: "@timianmalloo"
phase: "Enterprise evaluation: backlog close-out, pack revision 100, E5 preconditions, E5 (the first real campaign); Leader epoch 19"
tags: [coordination, worktrees, parallelism, evaluation-campaign, e5]
links:
  - { to: arch-evaluation-campaign, rel: implements }
  - { to: spec-enterprise-evaluation, rel: implements }
  - { to: adr-0021-plan-level-resume-and-liveness, rel: depends-on }
  - { to: run-report-e2e4, rel: depends-on }
  - { to: coordination-e2e4, rel: relates-to }
  - { to: proof-eval-campaign-convergence, rel: relates-to }
  - { to: runbook-resume-and-alarm, rel: relates-to }
  - { to: design-eval-multi-turn, rel: relates-to }
  - { to: rulings-register, rel: depends-on }
  - { to: defect-classes, rel: relates-to }
  - { to: coordinator-log-c54, rel: relates-to }
review-by: "2026-10-22"
summary: >-
  Coordinator #54's plan at main f544deb2. 11 tracks (9 dispatchable, 2 gated) across Codex, Agy, Grok and Claude Code
  Sonnet; four push batches with one gate ring (X-PROP, grade/property.py); a serial spine that ends every src/ join,
  then re-runs the ten records and the convergence check on the final head, then runs E5 as a Leader lane with two
  operator stops (pilot spend, then grid spend and nights). E5 sized from grid-4's measured cell and grading rates:
  846-5,256 cells, 24-147 h of run, 1.1-6.7 billion tokens (Inferred from measured rates). Twelve candidates struck or
  merged. Pre-grid critical path Inferred at 12 h, 21-29 h at E2-E4's measured overrun.
---

# Coordination plan: finish (backlog, pack upstream, E5 preconditions, E5)

**Goal** (the operator-approved scope prompt, "run the propmpt now", 2026-10-08). E5 complete end to end (baseline at frozen 0.7, records reproduced, full pilot ring, admission, final power, pre-registration, the multi-night 3-arm grid with resume, verdicts with dominance and eligibility, a defect fix with re-grade), every backlog item below closed, pushed to `origin/main`, and a closing run report. **Done when:** every track below has joined `main` through a pushed batch with its gates green or at a baseline measured before the batch; ai-forward carries the pack items and this repo carries them through `/updatepack`; the ten records and the convergence check are re-run on the final head; the drill acknowledgement is recorded; E5's campaign is concluded with its verdicts; the run report (md + html) is committed and pushed. **Not in scope:** macOS (deferred by the operator); B-3, the E1 demo walk (punted by the operator); GitHub Actions; force pushes or history rewrites; GitHub Copilot as a worker. **Tier:** T2. **Fan-out cap:** 6 concurrent workers, at most 2 per external harness; the Leader, Coordinator and Owner seats do not count. **Objective, lexicographic:** completeness and rigor, then token cost, then speed.

The scope prompt's nine rules are cited here as "scope rule n". Where an older README or brief differs, the scope rules win. The E2-E4 plan's rules still hold where this plan does not change them (`docs/coordination/coordination-e2e4.md`).

### Seats (served id read back and recorded for every dispatch)

| seat | session | model | duty | rules into |
| --- | --- | --- | --- | --- |
| Leader | `leader-fin` (Claude Code) | `claude-opus-5-5` | the lease, **epoch 19** (CO-L); every dispatch through `.tools/coord/runner-leader.sh` with `COORD_TREE=C:\Projects\x-harness-x-model-bench-integrate-finish-19`; every merge, batch, push and E5 command; fast-forwards the primary only after a push (scope rule 2) | - |
| Coordinator | `coord-opus-fin`, hand-back sessions #54 onward | `claude-opus-5-5` (this session: `claude-opus-5-5[1m]`) | compiles every brief at dispatch (CO-S0, compiled mode); arbitrates seams; owns W0, the briefs, errata, this plan, the register and the run report; one file per session under `docs/coordination/coordinator-log/` | W0; the briefs; `docs/lessons/defect-classes.md` |
| Owner | `owner-fable` (Claude Code) | `claude-fable-5-1` | rules every `coord decide request --to owner-fable`; one ruling session at a time, in its own worktree | `docs/notes/rulings.md` (authored); the last ruling is 113; the Owner allocates the next number (ID-A) |
| Workers | one new session id per dispatch, checked free (IDN-A) | per track (Tracks) | their owned paths only | - |

**Who rules.** Every track rules by `owner-fable` into `docs/notes/rulings.md`. A request unanswered for 30 minutes goes to the Coordinator, which applies the brief's recommended default and marks it *provisional*. A compile whose `dispatchable` is false, or that carries an unanswered `DR-n` line, is refused at dispatch with `decision request unanswered: DR-n` (CO-S0). Open before the first dispatch: **DR-REDS** (Ruling 109's optional per-variant `reds` key; X-REDS waits on it) and the operator questions in *Operator actions*.

## Layer state

Measured by Coordinator #54 in this plan's tree, `C:\Projects\x-harness-x-model-bench-coord-fin-c54-plan`, at about 2026-10-08 14:40Z: `coord doctor` exit 0; `pack-doctor.py --json` exit 0 (20 PASS, 3 WARN, 0 FAIL). The Leader's earlier read matches.

| check | result | meaning |
| --- | --- | --- |
| registry | ok - 11 patterns (`.agents/artifacts.yml`) | classification is real; no Stage 1 change needed (below) |
| merge driver | effective: `coord-regen`, `coord-register` declared and registered | merges regenerate derived files and union-merge JSONL registers |
| leader | `leader-fin` epoch 19, 276 s left at the read | every track row carries epoch 19; the renewal loop must run |
| heartbeat | 43 sessions; newest beat 135,436 s old; 3 stalled, 0 live | no live traffic, which is not evidence of a working layer (CTX-H) |
| sessions | `coord session list`: `coord-opus-fin`, `leader-fin`, and **`leader-e1e4` still listed active** (tree `integrate-e2e4-18`, removed) | a stale session; the Leader ends it before the first dispatch (order 1) |
| requests | ok - 116 total, 0 open, 116 terminal | nothing blocks dispatch |
| lease overlap | none (0 live leases) | - |
| worktrees | the primary, `integrate-finish-19` and this tree, all at `f544deb2` | the primary has three modified files and two untracked ledgers (git status at session start); the Leader commits them |
| pack | revision 99 (2026.10.05.2) installed; ai-forward `origin/main` = `7ea5dea` (rev 99) | `/updatepack` will take rev 100 from F-PACK |
| doorbells | `not recorded` (pack-doctor) | the Leader polls `coord mail` at every dispatch and join |
| runner wrapper | `.tools/coord/runner-leader.sh` **exports `AGENT_SESSION=leader-e1e4`** (line 18) and **pins Codex** with `CODEX_CONFIG='{"model":"gpt-6.1-sol",...}'` (line 21), read here | both are stale for this run: the lease is `leader-fin`, and Codex runs with no pin (scope prompt, operator 2026-10-07). The Leader edits the ignored file before the first dispatch (order 1) |
| host | 581 processes (read here; stop line 1,500) | health check passes |

**Install once, in the primary checkout. Each worktree inherits it.** `coord install` ran once in `C:\Projects\x-harness-x-model-bench`. A linked worktree shares `.git/config` and `.git/hooks`, so every tree in this plan inherits the drivers and the commit floor. Each tree runs `coord doctor` to read the state back; **no tree runs `coord install`**.

### Harness capability, as verified here

What a track needs: its own tree and branch; the compiled brief delivered verbatim; the model served and read back; commits confined to owned paths; a bounded attempt with a Leader-held fallback.

| harness · mechanism | version (read here) | capability | model and read-back | limits |
| --- | --- | --- | --- | --- |
| Codex via `coord-runner` and the Leader wrapper | codex-cli 0.160.0 | **observed-only** (E2-E4: 9 turns; run report) | **no pin** (scope prompt; operator 2026-10-07). `~/.codex/config.toml` says `model = "gpt-6-sol"`; the newest rollout (2026-10-06 11:28) served `gpt-6.1-sol` under the wrapper's pin. Served id from the rollout record per dispatch | deadline 3,300 s; context floor **90k** (c46: X-K1b first reading 89,613) |
| Agy via `coord-runner` | **1.3.0** (qualified at 1.2.13) | **unsupported at 1.3.0** until its first dispatch reads back the served id; observed-only at 1.2.13 (7 turns) | `gemini-3.8-flash-high`; served id from `cli.log` | deadline 3,300 s; floor **40k** (K2b part 1: 39,611) |
| Grok via `coord-runner` | 1.0.41 | **observed-only** at the pin (3 turns; G3 r2 served `grok-4.7-build`) | `grok-4.7`, `--reasoning-effort high`; **R-103: kill at the first response if not `grok-4.7*`, one retry** | deadline 2,400 s; **short turns only**; floor **not recorded** (the first Grok compile records its first reading) |
| Claude Code Agent tool, Sonnet | host | **qualified fallback for every track**: edit boundary enforcing (spike S5, from `coord doctor`, not re-measured), commit floor enforcing; runs in `coord worktree new` trees by absolute path, never `EnterWorktree` | `claude-sonnet-5-5`, read back per spawn | floor **73k** (c46: first readings 53,951-72,513) |
| GitHub Copilot | - | - | - | **never a worker**. Copilot stays a *measured* cell harness in E5 (spec EN3) |

**RUN-IDENTITY (measured in E2-E4, run report "Tracks").** The runner refuses a session id used before (`coord-runner.py:427-428`, read in ai-forward rev 99: "Each new worker attempt needs a new session identity, including after a prior run stopped.") and a reserved one (`:506-508`). Until F-PACK's IDN-A fix lands, **every continuation gets a new session id, checked free** (`git grep`, `runs/`, the ledger: c47's method), and is recompiled with it. **The wrapper refuses a tree outside this repository** (`runner-leader.sh:14-15`), so no external harness can work in ai-forward: F-PACK is a Sonnet track.

## Artifact classes

Stage 1 ran first (scope rule 1). Every `derived` command in `.agents/artifacts.yml` was run in this tree before this plan relied on it, each exit read: `docs-graph.py derive` (282 entries, exit 0); `audit-log.py ... render` (974 audit + 54 change entries, exit 0); `tools/render-doc-html.py` (exit 0); `tools/sync-skills.py` (exit 0); `coord-core.py regen` ("nothing owed", exit 0). **No new derived or register artifact enters this run**, so the registry is not extended.

| path / pattern | class | mechanism | coordination needed |
| --- | --- | --- | --- |
| `docs/docs-index.js` | derived | `python docs/ai-forward-pack/scripts/docs-graph.py derive` (run here) | **none** |
| `docs/audit/audit-data.js`, `docs/audit/index.html` | derived | `python docs/ai-forward-pack/scripts/audit-log.py --root docs --project x-harness-x-model-bench render` (run here) | **none** |
| `docs/specs/harness-bench.html` | derived | `python tools/render-doc-html.py` (run here) | **none** |
| `.claude/skills/{start-benchmark,new-bench-task}/**`, `.agents/skills/{...}/**` | derived | `python tools/sync-skills.py` (run here) | **none**: edit the source, then sync |
| `docs/audit/audit-log.jsonl`, `docs/audit/change-log.jsonl` | register | union merge (`coord-register`) | **none**; joins are real merges, never squash |
| `.agents/log/*.jsonl` | register | union merge | **none** |
| `docs/notes/rulings.md` | **authored** (REG-C: `register` is JSONL-only) | one writer: `owner-fable`, one ruling session at a time | Owner only |
| `docs/coordination/eval-wave2-e1/README.md` section 8, `docs/coordination/coordinator-log.md` | authored, closed to appends | - | **none** (nobody appends) |
| `docs/coordination/coordinator-log/c<NN>.md` | authored, create-only, one file per session | new files never conflict | **none** |
| `docs/lessons/defect-classes.md` | authored, Coordinator-owned (entries are edited in place) | - | Coordinator only; tracks report class text |
| W0 (`docs/design/eval-seam-contracts.md`), `docs/design/eval-multi-turn.md` section 12, `docs/proof/eval-campaign-convergence.md` (re-run section), the briefs, this plan, the run report | authored, Coordinator | - | Coordinator only |
| `bench/discrimination/**` | authored, create-only, content-addressed | `create_once` compare-and-refuse (ADR-0016 §2a) | the Leader only (the final records) |
| `bench/campaigns/**` (absent today; E5 creates it), `bench/catalog-freeze.yaml` | authored, single writer | - | the Leader only |
| `runs/`, `.tools/` | ignored | not tracked | **none** |
| `src/**`, `tests/**`, `tasks/**`, `tools/**`, `bench/**` (other), `.gitattributes`, `docs/**` (other) | authored | **one owner per file per phase** (hub table) | **yes: the only real contention** |
| `docs/ai-forward-pack/**`, `.claude/**`, `.agents/**` (not `log/`), `.github/**`, `.grok/**`, the managed blocks of `AGENTS.md` and `CLAUDE.md` | authored, pack-managed | `pack-apply.py` | F-PACK phase 2 only |
| ai-forward `pack/**` and its tests | authored, another repository | F-PACK phase 1 only, in its own worktree | yes: F-PACK only |

### Hub files: one owner per file per phase (scope rule 3)

| hub file | owner | concurrent writers and why it holds |
| --- | --- | --- |
| `src/harness_bench/grade/property.py` | X-PROP | none |
| `src/harness_bench/campaign.py`, `cli.py`, `errors.py` (a new HB code, ID-A checked), `tools/alarm-task.ps1`, `docs/runbooks/resume-and-alarm.md`, `tests/test_alarm_task.py`, `tests/test_alarm.py`, `tests/test_campaign.py` | X-DRILL | none. X-WIN leaves the two alarm test files to X-DRILL (convention below) |
| `src/harness_bench/discriminate.py`, `tests/test_discriminate.py` | X-REDS (if the DR-REDS ruling rules it in) | none |
| `src/harness_bench/report/**`, report tests and goldens | X-EVU | none. A gap that needs `campaign.py` is a seam to X-DRILL after its join |
| `src/harness_bench/identity.py` (`CLASSES`) | the track that adds a `src/` module adds its own entry | adjacent lines conflict by construction: **the Leader resolves `CLASSES` as a union** at the join |
| `tools/mutate_check.py`, `tests/test_mutate_check.py`, `tests/mutations/atomic.json`, `.gitattributes` | X-HYG | none. X-WIN leaves both files to X-HYG |
| `tests/test_property_grader.py` | X-PROP | X-WIN leaves it to X-PROP |
| `tests/test_security_s2.py`, `tasks/S2/**` | X-S2 | X-WIN leaves the test file to X-S2; the S2 record is the Leader's |
| every other `tools/`, `tools/spikes/` and `tests/` file that launches a child (46 files lack console suppression, below), a new guard test, a new windows-check tool | X-WIN | none |
| `tools/<flake-repro>.py` and its test (new; names checked free at compile, ID-A) | X-FLAKE | none |
| `bench/rings/e5-*.yaml`, `bench/matrix.e5-*.yaml` (new; names checked free) | X-E5M | none |
| `tests/mutations/<module>.json` | the module's owner | MUT-E: `test_mutate_check` is in every guard list |

### Guards over shared surfaces (GO14a)

Every worker runs **the standard guard list** on its first and final commits (scope rule 5): `tests/test_architecture.py`, `tests/test_identity.py`, `tests/test_atomic_sites.py`, `tests/test_arms_guard.py`, `tests/test_discriminate.py`, `tests/test_mutate_check.py`, `tests/test_skills_in_sync.py`, `tests/test_timing_hygiene.py` (all present, listed here).

| shared surface | guard (quoted, with citation) | scan: root · recursion · tokens · allowlist | jointly satisfiable because |
| --- | --- | --- | --- |
| console windows of child launches (new, X-WIN) | the scope prompt: "every child process launched by tools, spikes and test helpers suppresses console windows (CREATE_NO_WINDOW)" | root `tools/` and `tests/` · recursive over `*.py` (fixture helpers such as `tests/fixtures/ledger/make_fixture.py` included), skipping `__pycache__` · calls to `subprocess.run/Popen/call/check_call/check_output` and `os.system` without a `creationflags` keyword · allowlist: none at first; an entry needs a reason (a POSIX-only test) | **the convention is pre-declared by C-W0**: a launch passes `creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)` (stdlib, one line, ladder rung "one line"). Each owner applies it in its own files (X-HYG, X-PROP, X-S2, X-DRILL, X-FLAKE); X-WIN sweeps the rest and lands the guard. The guard runs on the merged P2 and P3 heads. `src/` is out of its root: `tests/test_architecture.py` D3 already holds it (`SUBPROCESS_CALLERS = {"procs.py", "grade/bench_check.py"}`, `:24`) and both set flags (`procs.py:313`, `bench_check.py:224` `DETACHED_PROCESS`) |
| every `src/` file has a class | ADR-0017 §1: "The classification table lives in code, once, with a test that every `src/` file has a class." (`tests/test_identity.py`) | root `src/harness_bench` · recursive · `CLASSES` · `EXEMPT = {"cli.py"}` | a new module's track adds its own key; the Leader unions |
| subprocess speakers in `src/` | W0 §10 D3 (`tests/test_architecture.py`) | `SUBPROCESS_CALLERS` (exact set) | no track adds a `src/` launcher. A drill toast is in `tools/alarm-task.ps1`, outside `src/` |
| mutation finds | MUT-E (`test_every_mutation_find_text_occurs_exactly_once`) | `tests/mutations/*.json` | each track retargets every find its own edit moves and names them; the Leader runs `mutate_check --touched` once per batch with `HB_REQUIRE_DOTNET=1` |
| generated skill copies | `tests/test_skills_in_sync.py` | `.claude/skills`, `.agents/skills` · byte equality with the source | only F-PACK phase 2 edits them, through `sync-skills.py` and `pack-apply.py` |
| the alarm and registration | ADR-0021 §7: "Before E5's comparison grid starts, the scheduled task must turn a non-zero exit into a notification the operator sees away from the terminal ... a seeded stale run must produce a notification the operator acknowledges. `bench campaign register` refuses for a multi-night grid until that drill is recorded." Amendment 1 (R-102 item 2): "a push to the operator's phone the operator acknowledges at the drill, at minimum; a desktop toast is an optional local echo" | not a scan | X-DRILL alone writes `register`'s refusal (today `campaign.register`, `campaign.py:1647-1678`, has none, read here) and the drill record. The scope prompt also asks for the toast, so the drill delivers both |

## Tracks

**Pins:** Codex = no model pin (served id recorded). Agy = `gemini-3.8-flash-high`. Grok = `grok-4.7` effort high, R-103. Sonnet = Agent tool `model: sonnet`, served `claude-sonnet-5-5`. Every row carries **leader epoch 19**, **fan-out cap 0** (a worker spawns nothing: FALLBACK-A) and rules by **`owner-fable`**. **Budgets are Inferred** (calls · context ceiling per dispatch · dispatches · wall) from E2-E4's analogues; the split rule is the harness floor plus the item's work (CEIL-A, scope rule 4). The fallback is Leader-held and never rendered into a brief (FALLBACK-A).

**Common exit evidence (scope rule 5, R-104):** own tests red first on an **assertion**; the worker's own test files green; the guard list on the first and final commits; `mutate_check` on its own mutation file only; `uv run ruff check src tests tools`; `docs-graph.py validate`; the served id; the windows check at hand-back (from X-WIN's join on; before it, the worker lists the windows it opened). **The whole suite is the Leader's**, once per join (`pytest -n 4 --dist loadscope`).

| track | owns (authored) | depends on | tier | fan-out cap | budget | exit evidence | harness |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **F-PACK** ai-forward upstream (phase 1), then `/updatepack` and the DEV-A sweep here (phase 2) | phase 1: ai-forward `pack/scripts/{coord-runner,prompt-compile,verify-compiled-prompt}.py` and their tests, in a new worktree; phase 2: this repo's pack-managed paths, `docs/notes/deviation-*.md` | phase 1: none. Phase 2: the Leader's ai-forward push, and no external dispatch live | T2 | 0 | 180 · 200k · 1 · 3 h, then 80 · 150k · 1 · 1.5 h | phase 1: four items, each red first in ai-forward's tests (below); `/extendaibundle`'s consistency steps; `tools/verify-bundle.ps1` exit 0. Phase 2: `pack-apply.py`'s action table; every CONFLICT and MERGE path has a deviation note or is retired (DEV-A); `coord doctor` and `pack-doctor` read back; `test_skills_in_sync.py` green | Sonnet |
| **X-PROP** `grade/property.py:330` | `src/harness_bench/grade/property.py`, `tests/test_property_grader.py`, `tests/mutations/property*.json` | none | T1 | 0 | 40 · floor + 40k · 1 · 0.7 h | red: a fake whose `terminate_and_confirm` returns False shows cleanup running against a live tree; green: the result is read and an unconfirmed kill is recorded, not cleaned up; the sweep of the class (`procs.py:529` also discards it; read here) in the report | Grok |
| **X-HYG** machine paths and host-limited mutants | `.gitattributes`, `tools/mutate_check.py`, `tests/test_mutate_check.py`, `tests/mutations/atomic.json` | none | T1 | 0 | 50 · floor + 40k · 1 · 0.7 h | `verify-no-machine-paths.py` exit 0 (today exit 1: 4 hits, all `tests/fixtures/ledger/*/run/archive/*/attempt-1/home/sessions/2026/09/rollout-*.jsonl:3`, byte-exact captured records, so the fix is the per-file `.gitattributes` `machine-path-ok` the gate's own text names); `run-verify-gates.py` 9 of 9; `mutate_check` reports M14b and (if the right is not granted) M27 as **host-limited**, not survived, red first | Grok |
| **X-WIN** console windows | every `tools/`, `tools/spikes/`, `tests/` launch not in another row; the new guard test; a windows-check tool (name checked free) | C-W0 (the convention) | T1 | 0 | 120 · 40k + 80k · 2 · 2.2 h | red: the guard fails on today's tree (46 files lack `creationflags`, list in c54); green after the sweep; the windows check lists visible top-level windows created after a given instant by the session's own PIDs, red first on a fixture | Agy |
| **X-S2** S2's open items | `tasks/S2/**` (variants, two fixtures, evidence), `tests/test_security_s2.py` | none | T2 | 0 | 150 · 40k + 100k · 2 · 2.2 h | A6: one variant shape per class by a non-Sonnet author (5 classes), each flipped to its own probe; a fixture app that answers a cookieless `GET /tasks` with 200 and passes the seed controls kills `tamper-1 no-cookie control removed`; a fixture that reaches `bob-get` kills `authz bob-get control removed` (`tasks/S2/oracle/evidence.md:118-128`). The record is the Leader's (final records) | Agy |
| **X-EVU** E5's test validations | `src/harness_bench/report/**` hunks a gap needs, report tests and goldens | none | T2 | 0 | 150 · 40k + 100k · 2 · 2.2 h | a coverage map of the E5 row's validations to named tests: EV-16, EV-18, EV-19, EVU-1..8 (only EVU-1 and EVU-5 are named by id in `tests/`, read here; EVU-5 is `importorskip("playwright")`); each missing one red first, then green; axe (EVU-5) **run**, not skipped, in light and dark | Agy |
| **X-DRILL** the drill and the registration refusal | the X-DRILL hub row | C-W0 (the drill record's design) | T2 | 0 | 120 · 90k + 100k · 1-2 · 1.5 h | red: `register` on a multi-night grid with no drill record succeeds today; green: it refuses with a new HB code (ID-A); a drill command seeds a stale run, the task delivers the ntfy push and a toast, and the operator's acknowledgement writes the drill record (create-once); `tests/test_alarm_task.py` and the runbook updated | Codex |
| **X-FLAKE** the FLAKE-A load-repro tool | the new tool and its test | none | T1 | 0 | 40 · floor + 40k · 1 · 0.7 h | the tool runs one node N times under `-n 4 --dist loadscope` (a counted loop: `pytest-repeat` is not a dependency) and records the failure rate and stage; red first on a seeded flaky fixture | Grok |
| **X-CACHEB** find what empties the ring cache | read-only host investigation; a fix only through a seam to that file's owner | none | T1 | 0 | 60 · 73k + 60k · 1 · 1 h | the sweep the register owes: every process that can delete under `%TEMP%` (Storage Sense, worker cleanups, `CLN-*` scripts) checked against the 2026-10-05 15:33:22 instant; the register entry updated with the measured result, or "not found" with what was read | Sonnet |
| **X-E5M** E5's ring and grid files | `bench/rings/e5-pilot.yaml`, `bench/matrix.e5-grid.yaml` (names checked free) | the operator's arm-Y answer and the cell pins (Operator actions) | T1 | 0 | 60 · 73k + 60k · 1 · 1 h | `bench plan` builds both; the pilot is 10 tasks × 3 arms × 3 combos × 1 (EV-14: "every admitted-candidate task × every arm × every harness × 1 repetition"); EV-17 launch balance under 5 %; every combo pins its model | Sonnet |
| *gated* **X-REDS** Ruling 109's `reds` key | `src/harness_bench/discriminate.py` (`_variant_record`), `tests/test_discriminate.py` | **the DR-REDS ruling rules it in** | T1 | 0 | 50 · floor + 40k · 1 · 0.7 h | as the ruling states; a variant with `reds` refuses a record whose failing hidden tests differ | Grok |
| *gated* **X-SJ4** spike S-J4 | `docs/notes/spike-s-j4.md` (name checked free); the spike script under `tools/spikes/` | the operator's go: adapter builds on PATH, credentials, spend | T1 | 0 | 60 · 73k + 60k · 1 · 1 h + operator time | the three counts (after `session/new`, at the first update, at the end of a no-tool turn 1) on Claude Code, Codex and Copilot (W1-J §12 row S-J4); the Coordinator writes the result into W1-J §12 | Sonnet |

**F-PACK's four items (all read in `C:\Projects\ai-forward-fix-xh-e2e4-upstream`, rev 99 `7ea5dea`, which equals ai-forward `origin/main`):**

1. **IDN-A.** The runner refuses a reused worker identity (`coord-runner.py:427-428`, `:506-508`), so a continuation needs a recompile with a new id. Fix: the runner accepts a new session identity on a continuation run, or the compiler mints one per run. The brief names one, with its red test.
2. **CEIL-A.** `verify-compiled-prompt.py` checks that `context_ceiling` exists (`:52`) but compares no split threshold with a floor. Fix: refuse a split threshold below the harness's measured first reading (floors: Sonnet 73k, Codex 90k, Agy 40k, from a table the repo supplies).
3. **CONSUME-A.** `prompt-compile.py:430` sets `"dispatchable": None if mode == "compiled" else True`, so a `not-compiled` compile is dispatchable, while the runner refuses it (`coord-runner.py:357`: `doc.get("mode") != "not-compiled"`). Fix: `verify-compiled-prompt.py` refuses a `not-compiled` compile marked dispatchable; the producer agrees with the consumer.
4. **FALLBACK-A (upstream half).** `prompt-compile.py:507-508` renders every `CONTRACT_KEYS` entry (`:49-50`, which includes `fallback`) into the contract slot, and `coord-runner.py:523` writes `fallback` into `<session>.brief.json`. Fix: neither render reaches the worker.

**FLAKE-A's tool stays repo-local** (struck from the pack: the register names `tools/`, and `pytest -n --dist` is this repo's runner).

**F-PACK's tree.** Not the ai-forward primary (`C:\Projects\ai-forward` is at `4a22f12`, behind `origin/main`, with six other worktrees). From the ai-forward clone: `python docs/ai-forward-pack/scripts/coord-core.py worktree new --branch fix/xh-finish-upstream --session fpack-fin --base origin/main` (= `7ea5dea`). The old tree `C:\Projects\ai-forward-fix-xh-e2e4-upstream` (branch `fix/xh-e2e4-upstream-b`, clean, equal to `origin/main`) is reported for cleanup, never reused for writing.

### Track assignment detail

| track | sessions · branches | why this harness and model | expected seam requests | deadline · termination · fallback | compile status | join batch · gate ring |
| --- | --- | --- | --- | --- | --- | --- |
| F-PACK | `fpack-fin` · ai-forward `fix/xh-finish-upstream`; here `coord/pack-update-fin` | the wrapper refuses non-repo trees (`runner-leader.sh:14-15`), so no external can work in ai-forward; the coordination engine is rigor-first, so the Coordinator reviews it in Adversary mode before the push | none here; ai-forward findings go to its own register | budget · stops at exit evidence or budget · a fresh Sonnet session from the brief | to write and compile (Coordinator #55) | phase 2 in P3 · none |
| X-PROP | `xprop-fin` · `build/fin-x-prop` | one function and one red test: a short turn | none | 2,400 s, R-103 kill and one retry · ends at a green commit · Sonnet | to write (#55) | P2 · **pays the P2 ring** (`grade/**` is a stamp input, `tools/gate_stamp.py:3-9`) |
| X-HYG | `xhyg-fin` · `build/fin-x-hyg` | a config line and one labelled outcome: short | none | as X-PROP | to write (#55) | P2 · none |
| X-WIN | `xwin-fin` · `build/fin-x-win` | a bounded multi-file sweep: Agy's profile and the cheapest external; **its first turn is Agy 1.3.0's qualification** | a launch in another row's file (to the Coordinator) | 3,300 s per turn · two turns, each ends at a commit · Sonnet | to write (#55) | P2 · none |
| X-S2 | `xs2-fin` · `build/fin-x-s2` | A6 needs an author other than Sonnet (`x-is2d-e1e4` wrote all 21 variants); Agy is a different model family and the cheapest | none | 3,300 s per turn · two turns · **Codex, never Sonnet** (a Sonnet fallback fails A6 by construction) | to write (#55) | P3 · none |
| X-EVU | `xevu-fin` · `build/fin-x-evu` | bounded report slices: X-A3's precedent on Agy | a `campaign.py` need (to X-DRILL's owner) | as X-WIN | to write (#55) | P3 · none, unless a `grade/` file moves |
| X-DRILL | `xdrill-fin` · `build/fin-x-drill` | campaign and ledger semantics: Codex's long, deep profile | none (C-W0 fixes the record's shape) | 3,300 s · up to two turns · Sonnet | after C-W0 merges | P3 · none |
| X-FLAKE | `xflake-fin` · `build/fin-x-flake` | one tool and one test: short | none | as X-PROP | to write (#55) | P2 · none |
| X-CACHEB | `xcacheb-fin` · `build/fin-x-cacheb` | an investigation on this host's settings: no external harness has shown it reads Windows host state | the fix, if found, to that file's owner | budget · stops at a finding or budget · a fresh Sonnet session | to write (#55) | P2 · none |
| X-E5M | `xe5m-fin` · `build/fin-x-e5m` | bench content authoring: the Sonnet seat | none | budget · as X-CACHEB | after the operator's arm-Y and pin answers | P3 · none |
| X-REDS | `xreds-fin` · `build/fin-x-reds` | one function: short | W0 §2 rev 7 (Coordinator) | as X-PROP | after the DR-REDS ruling | P3 · none |
| X-SJ4 | `xsj4-fin` · `build/fin-x-sj4` | needs the operator's adapters and credentials on this host | none | budget · ends at the three counts per adapter or "not run" with the cause · none: the Owner rules the waiver | after the operator's go | P4 · none |

### Why each track earns the multiplier (GO6: about 15 times one session's tokens)

- **Measured cost of the last plan:** 35.8 h wall against 15-20 h Inferred; 19 external turns, of which **3 ended complete with no follow-on**; per-join recount 9.4-16.2 min at `-n 4`; gate ring 77-84 min; tokens per track **not recorded** except J1a (80 of 320 calls) and J1c (48 of 320) (run report). So an external turn is a likely follow-on, not a likely finish, and the multiplier is paid in Leader joins as much as in tokens.
- **Genuine independence:** the repo fixes touch disjoint files (hub table); F-PACK is another repository; X-S2 is one task folder.
- **Machine-time parallelism:** E5's pilot and grid are hours of model time on the Leader's host; the build tracks finish before the final head, so the pre-grid path is the joins plus the records.
- **Context hygiene:** each track grounds in under its harness's floor plus its work; one session holding all eleven would pass every measured ceiling.
- **Isolation:** Codex runs with full access in its own tree; F-PACK runs in its own ai-forward worktree.

### Harness-slot schedule (cap 6; at most 2 per external harness; hours from T0, Inferred)

T0 is the first dispatch after this plan merges and Coordinator #55's compiles land (Inferred: 2026-10-08 about 10:00 local, UTC-7). One external turn plus its join is taken as about 65 minutes (E2-E4).

| window (h) | Codex 1 | Codex 2 | Agy 1 | Agy 2 | Grok 1 | Grok 2 | Sonnet | workers |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 - 1.1 | - | idle | X-WIN t1 (qualifies 1.3.0) | X-S2 t1 (after X-WIN's served-id read) | X-PROP | X-HYG | F-PACK, X-CACHEB | 6 |
| 1.1 - 2.2 | X-DRILL (after C-W0) | idle | X-WIN t2 | X-EVU t1 | X-FLAKE | X-REDS (if ruled in) | F-PACK | 6 |
| 2.2 - 3.3 | X-DRILL t2 if needed | idle | X-EVU t2 | X-S2 t2 | - | - | F-PACK, X-E5M | 5 |
| 3.3 - 4.8 | - | - | - | - | - | - | F-PACK phase 2 (no external live) | 1 |
| 4.8 on | the final head, the records, E5 (the Leader's machine time) | | | | | | X-SJ4 when the operator is present | 0-1 |

Codex 2 stays idle: moving an Agy track there would shorten the pre-grid path by about 1 h at a higher token cost (Inferred), which the objective's order forbids (Struck tracks).

### Batch plan (joins into `integrate/finish-19`; pushes per batch; gate rings)

A **join** is a `--no-ff` merge into the integration tree, then `coord regen`, the red-SHA re-run, the guard list, `docs-graph.py validate` and the recount `pytest -n 4 --dist loadscope` (`docs/coordination/join.json`). A red that passes alone is diagnosed (load, shared state or environment) with X-FLAKE's tool once it has joined, never re-run until green (scope rule 6). A **push** follows one all-rings run on the batch head and `mutate_check --touched` once with `HB_REQUIRE_DOTNET=1`. The gate ring (77-84 min, measured) runs only when the stamp's inputs move: `src/harness_bench/grade/**/*.py`, `tasks/D1`'s version hash, `bench/metrics.yaml`, `bench/regrade-baseline-0.3.yaml`, and the pinned tool versions (`tools/gate_stamp.py:3-9`, read here).

| batch | tracks | ready at (Inferred) | gate ring | why grouped |
| --- | --- | --- | --- | --- |
| P1 | this plan, C-W0 (W0 amendments) | T0 - 0.5 h | no | docs only; every compile reads them |
| P2 | X-PROP, X-HYG, X-WIN, X-FLAKE, X-CACHEB (findings) | T0 + 2.5 h | **yes, once** (X-PROP) | the only `grade/` change of the run, in one ring; X-WIN's guard lands on the head every P3 track rebases on; `run-verify-gates` reaches 9 of 9 here |
| P3 | X-DRILL, X-S2, X-EVU, X-REDS (if ruled in), X-E5M, F-PACK phase 2 | T0 + 4.8 h | no (no stamp input moves; checked again at the batch) | every remaining `src/` and `tasks/` change, so the final head follows it (RECID-A) |
| P4 | the final records (the ten, S2 re-recorded), the convergence re-run, the S-J4 result, the drill record | T0 + 6.5 h | only if the digest moved since P2 | the final engine identity E5 baselines on |
| P5 | E5's campaign ledger and records, its report, the closing run report | after E5 | only if E5's defect fix touches `grade/**` (Inferred: likely one ring) | E5 closes |

**Expected gate rings: one before E5, plus one if E5's defect fix is a grader fix.**

## Serial spine

| item | why it cannot be parallel (GO5) | who owns it |
| --- | --- | --- |
| 0. The lease (epoch 19) stays alive; the health check (stop above 1,500 processes or on an AppModel-Runtime 208/212 event) and `coord mail` at every dispatch and join | one exclusive resource: an expired lease stops all dispatch | Leader |
| 1. The wrapper fix (`AGENT_SESSION=leader-fin`; no Codex model pin) and the stale `leader-e1e4` session ended, before the first dispatch | every dispatch reads both (GO5(c)) | Leader |
| 2. C-W0: the console convention, the drill record's shape and location, DR-REDS to the Owner, the floors table, the short scratch root in every compile | a vocabulary change every compile reads (GO5(b)); one author | Coordinator (#56, parallel to #55) |
| 3. Every `src/` and `tasks/` change joins (P2, P3) **before** the final records | `readiness.record_key` hashes every `src/harness_bench` file, `bench/bom.yaml` and `uv.lock` (`identity._readers`; Coordinator #44's read), so a later `src/` join makes all ten records stale (RECID-A) | Leader |
| 4. The final records: the Leader re-runs the ten (S2 with its new evidence) on the final head; `bench validate` reports all ten `ready`; Ruling 113's watcher reads `hosts.jsonl` (0 start-bound reference ends required) | records are keyed by engine identity (ADR-0016 §4) | Leader |
| 5. The convergence check on the final head: the whole ADR-0021 §4 table (`tests/test_resume_table.py`) and TLC with every §7 invariant (`tools/check_models.py`); the Coordinator writes the re-run section of `docs/proof/eval-campaign-convergence.md` | the architecture names it before E5 (*Delivery phasing*: "the convergence check before E5 runs the whole §4 table and TLC with every §7 invariant") | Leader runs; Coordinator records |
| 6. The drill with the operator: after X-DRILL joins and before registration | `bench campaign register` refuses a multi-night grid without it (ADR-0021 §7) | Leader and operator |
| 7. S-J4 settled before the E5 baseline: run (X-SJ4), or a ruling that E5 runs without it and what that costs | the baseline read point depends on it (W1-J §4.4 `assume:`) | Owner rules; Leader |
| 8. E5, in order: create and baseline at frozen 0.7 → records reproduced → prior power → **operator stop A (pilot spend)** → pilot ring (90 cells) and grading → pilot pass → admission → final power → **operator stop B (grid spend, nights, dates)** → pre-registration (`register --confirm`) → grid, resumed each night under the alarm task → grading → verdicts (dominance, eligibility) → a defect fix with re-grade (`bench campaign fix`) → conclude | each step reads the state the last one wrote in the campaign ledger (GO5(a)) | Leader; the Coordinator drafts the pre-registration statement; the Owner rules its DRs |
| 9. The run report, then `coord worktree cleanup` (report, then `--remove` with the operator's go) | last | Coordinator; Leader |
| Loop-back | a red at a join that needs a `src/` fix reopens a small fix track under that file's owner, with a red SHA; **two loop-back slots** budgeted (about 100 calls each) | Coordinator |

### Critical path (Inferred)

C-W0 and the T0 compiles (1 h) → X-DRILL (1.1-2.2 h) or X-S2/X-EVU's second turns (to T0 + 3.3 h) → P3 joins (about 5 × 15 min) → final records and convergence (about 1 h) → P4 (whole suite 13 min) ≈ **T0 + 6.5 h** to the final head. Then S-J4 and the E5 steps to the grid start: baseline and prior power (0.4 h) → pilot ring (90 cells × 1.68 min wall = 2.5 h) → pilot grading (90 × 1.16 min = 1.7 h) → admission and final power (0.5 h) → registration (0.3 h) ≈ **T0 + 12 h**, plus the operator's two stops. E2-E4 ran 1.8-2.4 times its Inferred path, so **21-29 h** is the honest figure; the grid's first night is Inferred at **2026-10-09 evening**. This is a model built from E2-E4 and grid-4 durations, not a measurement of these tracks.

## E5 sizing (sources named; Inferred where marked)

**Measured inputs (grid-4, `runs/grid-4`, read here by `measure_grid.py` in the session scratchpad):** 276 cells, 3 combos (`cc-opus` `claude-opus-5-5`, `codex-sol` `gpt-6-sol`, `copilot-sol` `gpt-6-sol`), `budget_seconds` 900. Cell phase `2026-10-02T20:30:57Z` to the last `cell.outcome` `2026-10-03T04:14:19Z` = **7.72 h**; 15.62 cell-hours, so effective concurrency 2.0 and **1.68 min of wall per cell**. Grading `04:14:22Z` to `09:35:32Z` = **5.35 h**, **1.16 min per cell**. Median cell 1.5-2.4 min, p90 4.8-6.4 min, max 30.2 min. *Erratum to the spec's figure:* the spec says "a grid takes about 5 h to run" (`docs/specs/enterprise-evaluation.md:31`); the measured cell phase is 7.72 h, and `run.completed` follows grading (13.08 h from `run.started`). Grid-3: 276 cells, 15.59 cell-hours; its 23.26 h grading span holds two passes.

**Tokens per cell (spec, Verified for its population; `enterprise-evaluation.md:444-458`):** pack-off / pack-on: Claude Code 398k / 858k; Codex 470k / 1,471k; Copilot 265k / 2,873k. The population is flagged against the Leader's figures (R-E5), and cache reads are included. **USD is not computable**: `bench/prices.yaml` has no entries (spec EN8), so tokens are the cost axis.

**Gap that forces modelling:** no real-model cell has run any of the ten property tasks (no `bench/campaigns/`, no E5-shaped run under `runs/`). Grid-4's task mix stands in; the spec calls these figures lower bounds for property tasks. **The pilot ring measures the real rates**, and stop B uses them.

| design (from the spec's illustration, `enterprise-evaluation.md:460-472`) | cells incl. 36 calibration | run at 2 slots | grading | tokens (Inferred: 1.28M per cell, the mean over 3 harnesses × off, X, Y with Y taken as X) |
| --- | --- | --- | --- | --- |
| pilot ring (EV-14) | 90 | 2.5 h | 1.7 h | 115M |
| paired, harnesses pooled | 846 | 23.7 h | 16.4 h | 1.08B |
| **paired per harness, ψ 0.28, δ 0.20 (DR-E5's design)** | **2,466** | **69 h** | **48 h** | **3.16B** |
| paired per harness, Bonferroni over 45 tests | 5,256 | 147 h | 102 h | 6.74B |

The final power analysis (EV-12) sets the real count; DR-E5 (operator, 2026-10-03) chose "Multi-night, per-harness ... run the comparison grid over as many nights as the final power analysis requires". At a 10-hour night (Inferred; the operator sets the window) DR-E5's design is about 7 nights of run, then about 2 days of grading.

## Seams

| from -> to | the request | resolved by |
| --- | --- | --- |
| X-HYG, X-PROP, X-S2, X-DRILL, X-FLAKE -> X-WIN | the console convention in their own files | pre-declared by C-W0; X-WIN's guard runs on the merged P2 and P3 heads |
| X-DRILL -> W0 | the drill record's shape, location and the "multi-night" test register applies | C-W0 writes it before X-DRILL compiles |
| X-REDS -> W0 §2 rev 7, W1-E §7 | the `reds` key | the DR-REDS ruling first; the Coordinator amends W0 if ruled in |
| X-EVU -> X-DRILL | a verdict-section gap that needs `campaign.py` | after X-DRILL joins; a loop-back slot |
| X-CACHEB -> the cleaner's owner | the fix, if the sweeper is found | a seam request to the Coordinator; that file's owner fixes it red first |
| X-S2 -> Leader | the S2 record | the final records (spine 4) |
| X-SJ4 -> Coordinator | the three counts | W1-J §12's result column |
| F-PACK -> Leader | the ai-forward push; the `/updatepack` branch | the Leader pushes from F-PACK's ai-forward tree, never the primary; phase 2 joins P3 |
| E5 -> Owner | the power population (R-E5), the multiplicity choice, DRs in the pre-registration | `coord decide request --to owner-fable` |
| any track -> Coordinator | a defect class | reported as text; the Coordinator commits the register |
| any track -> Owner | a decision outside its brief | the brief's default stands until ruled |

## Struck tracks

| track | why it was not worth its multiplier |
| --- | --- |
| A separate machine-paths track | one `.gitattributes` line set; merged into **X-HYG** |
| A separate DEV-A sweep track | `pack-apply.py`'s action table *is* the measured sweep (the register's own method); merged into **F-PACK phase 2**, which must run after `/updatepack` anyway |
| One pack track per item (four) | one bundle-consistency proof (`verify-bundle.ps1`) covers all four; **one track** |
| A separate `/updatepack` track | phase 2 of F-PACK: the author of the fix applies it and retires any deviation it closes |
| FLAKE-A's tool in the pack | repo-local: the register names `tools/`; `pytest -n --dist` is this repo's runner |
| A worker for the `--dist loadscope` read | the data is the join entries' recounts and reds in this run; the Coordinator reads it at P3 and in the run report |
| A worker for the Codex model setting | an operator setting plus the Leader's wrapper edit; the served id is read from the first rollout |
| A separate toast track | part of **X-DRILL** (one script, one drill) |
| A worker for the S2 re-record and the ten records | the Leader runs them in the final-records step (E2-E4: the S1 record took 59 s) |
| A worker for the convergence re-run | two commands on the final head plus a Coordinator section; spine 5 |
| X-EVU on the idle Codex slot | about 1 h off the pre-grid path for more tokens (Inferred); speed is last in the objective. **Revisit trigger:** two Agy turns end red-only, or Agy 1.3.0 fails its served-id read; then a DR to `owner-fable` |
| A worker for the E5 lane | E5 is the Leader's machine time with operator stops; only its files (X-E5M) and its statement (the Coordinator) are authored |

**Honest count:** 9 dispatchable tracks (F-PACK, X-PROP, X-HYG, X-WIN, X-S2, X-EVU, X-DRILL, X-FLAKE, X-CACHEB) plus X-E5M once the operator answers, and 2 gated (X-REDS on the DR-REDS ruling, X-SJ4 on the operator). Fewer is not right: every remaining track holds files no other track writes, or runs on another harness or repository; merging the five P2 tracks into one Sonnet session would run them serially (about 4 h) at no token saving.

## Order of operations

| # | action | cost | why now |
| --- | --- | --- | --- |
| 1 | Leader: `coord leader who` (epoch 19), the renewal loop; edit `.tools/coord/runner-leader.sh` (`AGENT_SESSION=leader-fin`; drop the `CODEX_CONFIG` model pin); end the stale `leader-e1e4` session; commit the primary's ledgers | 10 min | spine 1 |
| 2 | Leader reviews and merges this plan through `integrate/finish-19`; pushes (P1, docs only); fast-forwards the primary | 20 min | the contract `/execute-with-coordination` parses |
| 3 | Leader asks the operator the *Operator actions* questions in one message | 5 min | X-E5M, X-SJ4 and the Codex pin wait on them |
| 4 | **Coordinator #55** (hand-back): write and compile the T0 briefs (X-WIN, X-S2, X-PROP, X-HYG, F-PACK, X-CACHEB), compiled mode, each replayed through the runner's check, split rule = floor + work, no fallback text in the render, new session ids checked free, the short scratch root | 60 min | CO-S0; scope rule 4 |
| 5 | **Coordinator #56** (in parallel): C-W0 (spine 2) and DR-REDS to `owner-fable` | 60 min | X-DRILL and X-REDS read it |
| 6 | **T0 dispatch** (health check first): X-WIN (Agy; read the served id before the second Agy dispatch), X-S2 (Agy), X-PROP, X-HYG (Grok), F-PACK, X-CACHEB (Sonnet) | 15 min of Leader time | the cap's first wave |
| 7 | As slots free: X-DRILL (after C-W0), X-FLAKE, X-EVU, X-REDS (after the DR-REDS ruling), X-E5M (after the operator) | as the schedule | each starts when its dependencies join |
| 8 | **P2**: joins, the gate ring once, push; `run-verify-gates` 9 of 9 | 82 min ring + joins | the only `grade/` change |
| 9 | The Leader pushes F-PACK's ai-forward branch once `verify-bundle.ps1` is green; F-PACK phase 2 starts when no external dispatch is live | 10 min | phase 2 replaces scripts the runner uses |
| 10 | **P3**: joins; push | joins | RECID-A: the last `src/` changes |
| 11 | The drill with the operator (spine 6); X-SJ4 with the operator (spine 7) | operator time | before registration and baseline |
| 12 | **P4**: final records, convergence re-run, push | about 1.5 h | the final head |
| 13 | **E5** (spine 8), with operator stops A and B | see E5 sizing | the goal |
| 14 | P5; the run report (md + html); `coord worktree cleanup` (report, then `--remove` on the operator's go); the scratch root listed for deletion | 2 h | Done when |

**Execution stop rules (scope prompt):** the health check trips twice; host instability (record evidence first); `main` cannot be made green within one bisect round; or an operator-only blocker gates every remaining track. One status table per update (task, what it does, status, harness and model); report only when done or blocked on the operator.

### Operator actions (with the date each is needed by; local time, UTC-7)

| action | needed by | gates | recommended default |
| --- | --- | --- | --- |
| **Codex model**: set `~/.codex/config.toml` to the latest SOL model, or remove the `model` line so Codex chooses (today it says `gpt-6-sol`) | 2026-10-08 11:00 (X-DRILL, the first Codex dispatch, about T0 + 1.1 h) | X-DRILL | remove the line; the served id is read from the first rollout |
| **Symlink right** (Windows Developer Mode; read here: not enabled, and `SeCreateSymbolicLinkPrivilege` is absent from this token) if M27 should run | 2026-10-08 10:00 (X-HYG at T0) | M27 runs instead of "host-limited" | leave it off; M27 is reported host-limited |
| **Arm Y**: which pack revision is the "slimmed pack" (DR-T4; R-E10: "A slimmed pack revision (Y) may not exist by registration time"), or a 2-arm grid | 2026-10-08 12:00 (X-E5M) | X-E5M, the pilot | name the revision if it exists; else decide 2 arms before the pilot |
| **Cell model pins** for E5's three combos (grid-4 pinned `claude-opus-5-5`, `gpt-6-sol`, `gpt-6-sol`) | 2026-10-08 12:00 | X-E5M | confirm or name the current ids; cells always pin |
| **S-J4**: adapter builds on PATH, credentials, about 3 cells of spend (Inferred under 0.5M tokens, from the qualification cells' 34k-204k), and presence | 2026-10-08 18:00 (before the baseline) | spine 7 | run it; the waiver of 2026-10-06 covered E2-E4 only |
| **The alarm drill acknowledgement**: phone and desktop present; `HB_ALARM_NTFY_TOPIC` is set at user scope (read here: set, 33 characters; the value is not printed) | after X-DRILL joins (Inferred 2026-10-08 15:00) and **by 2026-10-09 12:00** | registration | acknowledge on the phone when the push arrives |
| **Stop A: the pilot ring's spend** (90 cells; about 115M tokens and 4.2 h, Inferred) | 2026-10-09 morning | the pilot | approve |
| **Stop B: the grid's spend, nights and dates** (binding figures from the pilot and the final power; envelope above: 846-5,256 cells, 24-147 h of run, 1.1-6.7B tokens) | 2026-10-09 afternoon, before night 1 | the grid | decided then, on measured numbers |
| `coord worktree cleanup --remove`, and deleting the session scratch root | at close | nothing | - |
| ai-forward push | none: in scope (scope prompt) | - | - |

### Open questions for the Leader or the Owner

1. **Scratch root (PATH-B, scope rule 9).** The prescribed root `...\scratchpad\fin\c54` is 132 characters. The register's measured margin is a 139-character archive depth below a `--runs` root, so "a root longer than about 120 characters ... passes MAX_PATH" (`defect-classes.md`, PATH-B). Worker trials, records and test runs need one short session root (for example `C:\tf\<track>`; not `C:\t`, which awaits the operator's delete). The Leader decides before #55 compiles.
2. **Agy 1.3.0** is not the qualified 1.2.13. The plan makes X-WIN's first turn the qualification; the Owner may prefer a Sonnet first turn.
3. **"A defect fix with re-grade"** is in E5's row. If the pilot and grid find no defect, does the Owner accept a recorded "no defect found", or must one be exercised?
4. **E5 slots**: grid-4 ran 2 slots. A third slot (one per harness) cuts the run by about a third; it changes rate-limit exposure. The operator's call at stop B.
5. **The power population** (R-E5, unresolved in the spec): the Owner rules it at prior power.
6. **PRIM-A's upgrade trigger fired in this session** (`defect-classes.md`, PRIM-A, instance 2026-10-08): a relative path in a shell's .NET call wrote an empty file into the primary; it was removed at once. The edit guard is owed. It is not added to this plan's tracks (a finding, not a goal); the Leader decides whether F-PACK carries it.

## Status

| | |
| --- | --- |
| **Completed** | the layer read back (`coord doctor`, `pack-doctor`); Stage 1's regenerate commands run; every backlog item checked in the repo (the 4 machine-path hits, `property.py:330`, 46 launch files, M14b/M27, the four ai-forward items at rev 99, S2's open items, the missing drill refusal, E5's test validations); E5 sized from grid-4's measured rates; this plan; `docs/coordination/coordinator-log/c54.md` |
| **Remaining** | the Leader's review and merge; C-W0; the T0 compiles; every track; the operator's answers; E5 |
| **Best next action** | The Leader runs order 1-3, then spawns Coordinator #55 (T0 compiles) and #56 (C-W0) in parallel; then `/execute-with-coordination` dispatches row 6 |
