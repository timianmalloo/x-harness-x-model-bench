---
id: "arch-lean-rerun"
title: "Architecture amendment: the lean re-run at equal reasoning (combo settings, served read-back, Grok and Antigravity cells, per-cell anatomy, the cost-compare report)"
type: architecture
status: draft
owner: "@timianmalloo"
phase: "Lean re-run at equal reasoning (operator 2026-10-11)"
tags: [benchmark, architecture, lean-benchmark, settings, reasoning, transport, grok, antigravity, report, drift]
links:
  - { to: arch-lean-benchmark, rel: refines }
  - { to: arch-harness-bench, rel: refines }
  - { to: adr-0024-combo-settings-and-served-read-back, rel: depends-on }
  - { to: adr-0025-transport-seam-grok-and-agy-cells, rel: depends-on }
  - { to: adr-0026-per-cell-anatomy-facts-catalog-0-8, rel: depends-on }
  - { to: adr-0027-cost-compare-report, rel: depends-on }
  - { to: adr-0022-lean-benchmark-two-batch-runs, rel: depends-on }
  - { to: rulings-register, rel: depends-on }
review-by: "2027-04-11"
summary: >-
  The smallest architecture that lets the lean ring re-run six harness/model combos at one reasoning setting and
  explain the cost differences. Combos gain effort and context (bench-matrix/3), frozen per cell and read back
  from each harness's own record as a validity gate (HB-VAL-010), including what "default" serves. The engine picks
  its protocol module by profile: ACP stays in driver.py; a new stream_driver.py with the same signatures speaks
  Antigravity's native stream-json. Grok runs over the existing ACP driver, never on a copy of a worker's
  credential. New hash-chained grading facts record served settings, reasoning items, prompt composition and
  harness events; the existing report derivations are extended, not duplicated; catalog 0.8 adds drift split three
  ways and attention drift. A generated cost-compare report replaces the hand-built page.
---

# Architecture amendment: the lean re-run at equal reasoning

*Status: draft, for the gate below. Authored 2026-10-11 by the Leader seat (Claude Code, `claude-opus-5-5[1m]`) at
`0c569647`. Labels: **Verified** = read or run here; **Inferred** = modelled, model named; **Flagged** = unknown.*

## Context and constraints

The problem statement is the committed prompt `docs/coordination/lean-rerun-equal-reasoning-prompt.md` (12ac42f4),
with Rulings 117 and 118 (`docs/notes/rulings.md`). It asks for:

- the lean ring re-run with six combos, each pinned at reasoning **high** and the largest context it serves;
- per-cell facts that explain *why* token cost, time and drift differ, not only that they differ;
- a cost-comparison page generated from the run records alone.

The binding constraints are these:

- **Lean design unchanged.** Two batches, arms off and on, pairs as before (ADR-0022, ADR-0023). 10 tasks × 2 arms
  × 6 combos = 120 cells per batch.
- **Tokens are the only cost axis** (Ruling 115).
- **Pack-off cells load no instruction files** (Ruling 116, HB-PRE-009). This now has to hold for two new harnesses
  whose user homes leak instructions (Verified, spike G1).
- **Settings are measured, not assumed.** A setting no record carries is `not recorded`, never inferred (IO1).
- **Never fork the ACP path.** Reuse what exists: the pack's coordination transport and the bench's own driver.
- **A non-lean report's rendering stays byte-identical** (LBU-5). The new report is a new command output, not a
  change to `report.html`. The catalog-version line moves once, at the 0.8 freeze (ADR-0026 §5).

The six combos (operator 2026-10-11, as amended by Rulings 117 and 118, Verified at the start-state check):

| combo | harness (pinned build) | model | effort | context pinned | how it is applied | read back from |
| --- | --- | --- | --- | --- | --- | --- |
| `cc-opus-1m` | Claude Code 2.1.282 (claude-agent-acp 0.81.2) | `claude-opus-5-5[1m]` | high | 1,000,000 | env `ANTHROPIC_MODEL`, `CLAUDE_CODE_EFFORT_LEVEL` | transcript `effort`; `attachment.identity.modelId`; ACP `usage_update.size` |
| `codex-sol` | Codex 0.160.0 (codex-acp 1.12.0) | `gpt-6.1-sol` | high | 872,000 | `config.toml` `model_reasoning_effort`, `model_context_window` | rollout `turn_context.effort`; `task_started.model_context_window` (828,400 = 95%) |
| `copilot-sol` | Copilot 1.0.89-1 | `gpt-6.1-sol` | high | 272,000 (default tier; Ruling 118) | argv `--reasoning-effort` | `session.start.reasoningEffort`, `selectedModel`; ACP `usage_update.size` |
| `copilot-sol-fast` | Copilot 1.0.89-1 | `gpt-5.6-sol-fast` | high | 272,000 (default tier; Ruling 118) | argv `--reasoning-effort` | as above; the API's response `model` is `gpt-5.6-sol` (recorded beside it) |
| `grok-4.7` | Grok CLI 1.0.41 | `grok-4.7` | high | 256,000 (no knob; operator 2026-10-11, in the prompt) | argv `grok agent --model … --reasoning-effort … stdio` | `chat_history.jsonl` `model_id`, `reasoning_effort`; `signals.json` `contextWindowTokens` |
| `agy-gemini` | Antigravity 1.3.3 (Ruling 117) | `gemini-3.8-flash-high` | high (in the model id) | not settable; `not recorded` | model id | stream `init.model`; context: not recorded |

## The system as a system

- **Stocks:** two frozen plans and two run ledgers per batch (ADR-0006), now with four more grading-pass fact
  streams (ADR-0026); the per-run `reasoning/` text; six pinned builds in `.tools/`.
- **Flows:** plan (settings frozen) → cell launch (settings applied by the profile) → native record → grading pass
  (served settings, reasoning, anatomy read back) → validity → lean summary and cost-compare report.
- **Feedback loops:**
  - the readiness probe gates batch 1 (a served setting that differs from its pin stops the run);
  - the batch-1 checkpoint gates batch 2 (ADR-0022, LB-3);
  - per cell, HB-VAL-010 removes a cell that ran on the wrong setting from every pair.
- **Delays:** served settings are only known after the native record is read at grading. So a mismatch is caught
  per cell after the fact. The probe moves the first catch before batch 1.
- **The boundary:** the cells and their records. Coordination workers (Grok, Agy) are outside: a worker's home,
  credentials and session store are never a cell's (prompt, *Seats*).
- **The leverage point:** *where a setting is checked.* The visible decision is "add `--reasoning-effort high` to
  each profile". The structural one is that a pin checked where it is written passes even when the harness ignores
  it. That is SERVE-A's root, and it was observed twice more in this session's spikes: Copilot accepts
  `--context long_context` under ACP and serves 272k; codex-acp overrides `model_reasoning_summary = "detailed"`
  with `"auto"`. ADR-0024 puts the check where the setting is honoured.

Candidate shapes considered:

- **Settings:** (a) per-profile constants, one profile file per combo; (b) combo fields frozen per cell and applied
  through profile placeholders (**chosen**, ADR-0024); (c) a free-form `env`/`argv` override per combo (rejected:
  it bypasses the profile, so nothing can check that the setting is one the harness supports).
- **Antigravity transport:** (a) import `coord_transport.run_session("agy")` into the engine; (b) a bench-owned
  native-stream driver beside `driver.py`, with the pack adapter as its conformance oracle (**chosen**, ADR-0025;
  a deviation from the prompt's words that goes to the operator); (c) drive agy through an ACP shim (rejected: none
  exists).
- **Anatomy:** (a) compute everything at report time from the archived native records; (b) read the facts
  `bench verify` must cover (served settings, reasoning, prompt parts, harness events) once at grading into
  hash-chained streams, and extend the report-time derivations that already exist for the rest (**chosen**,
  ADR-0026).

## Archetype and tier allocation

- **LOA archetype:** N/A for this amendment. It adds no AI capability: the bench measures model-backed harnesses,
  it does not call a model to decide anything. It inherits `arch-harness-bench`'s allocation for the cells.
- **Tiers:** every new component is **T0**, deterministic: matrix fields, profile templates, a transport, record
  readers, derived views, a renderer.
- **Rejected:** a model-backed reasoning-quality score or an LLM judge of reasoning text (out of scope by the
  prompt); paraphrase or reconstruction of encrypted reasoning.

## Domain model and durable representation

- **Bounded context:** Evaluation (unchanged). New ubiquitous terms, defined in ADR-0024 and ADR-0026:
  *requested setting*, *served setting*, *reasoning item*, *source kind*, *prompt part*, *harness event*,
  *machine-written drift*, *task-implied drift*, *discretionary drift*, *attention drift*, *neighbourhood*.
- **Aggregate:** *Cell* (unchanged). Its new invariant: **a valid cell ran on the settings its plan froze**, as far
  as the harness's own record shows. Enforced by HB-VAL-010 at the view (ADR-0024 §4).
- **Aggregate:** *Lean benchmark* (ADR-0022). Its invariant gains the settings: both batches and both arms of a pair
  share model, effort and context. Enforced at `--pool` by the ring hash of the matrix file (`plan.py:580`,
  HB-PLN-003) and by `board.pool_check`'s cell tuple, which gains effort and context (`board.py:824`; ADR-0024 §2).
- **Durable representation:** unchanged in kind.
  - Frozen plans are dimensions: the settings join `Cell` (ADR-0024 §2).
  - Grading-pass facts are append-only and hash-chained: four new streams (ADR-0026 §1).
  - Everything else is derived on every `bench report`: context curves, tool phases, re-reads, time anatomy, the
    drift split, attention drift, and the kiviat. Each has one definition, in one module.
- **Reasoning text location (Ruling 117 item 3):** the run's own ledger (`runs/<run>/reasoning/`, a fact stream);
  `docs/audit/audit-log.jsonl` gets one entry per batch naming the stream, its row count and its sealed head.
- **Data & Persistence:** new streams, no migration. bench-matrix/2 and bench-plan/2 files still load (ADR-0024 §1);
  old runs have no new streams, and every new view reads their absence as `not recorded (stream absent: run
  predates catalog 0.8)`.

## Component map

| component | kind | change | ADR |
| --- | --- | --- | --- |
| `config.validate_matrix` | validation | accept `bench-matrix/3`; `effort` and `context` per combo; refuse unknown combo keys in /3 | 0024 |
| `plan.Cell`, `plan.expand`, `plan.cell_id` | frozen dimension | `effort`, `context` on every cell; `cell_id` includes them only when not `default` | 0024 |
| `profiles.Profile` | profile contract | `settings:` block (supported values per setting, how each is applied); `{effort}`, `{context_tokens}` placeholders in `command`, `files`, `env`; `session_meta`; `transport`; `user_home_vars`; `seed_files` for trust/update/permission files | 0024, 0025 |
| `bench/profiles/{claude-code,codex,copilot}.yaml` | profiles | effort and context applied; Claude thinking display; Copilot debug log for per-request usage | 0024, 0026 |
| `bench/profiles/grok.yaml`, `bench/profiles/agy.yaml` | profiles | new | 0025 |
| `tools.LAYOUT`, `bench/tools/package.json`, `bench/tools/vendored.json` | builds | Grok 1.0.41 (npm), Antigravity 1.3.3 (vendored exe, sha256 pinned) | 0025 |
| `engine._attempt` | engine | picks `driver` or `stream_driver` by `profile.transport`; same call signatures | 0025 |
| `driver.py` | ACP | unchanged behaviour; `session_meta` passthrough on `session/new`; fail-closed `set_model` `_meta.model` check; `acp-timeline.jsonl` (arrival times, no content) | 0025, 0026 |
| `stream_driver.py` | native stream | new: agy stream-json, multi-turn, raw stream and a line-time sidecar teed to the cell home | 0025 |
| `profiles.py` `DROP_PREFIXES`, `seed_home`, `model_allowed` | isolation, aliases | `GROK_`, `AGY_`, `GEMINI_`, `GOOGLE_` dropped; parent dirs created; exact alias table | 0024, 0025 |
| `workspace.INSTRUCTION_FILES`/`DIRS` | pack-off rule | add `GEMINI.md`, `.agents/rules`, `.agents/skills`, `.grok/` | 0025 |
| plan `harness_parallelism`, `models/run_lifecycle.tla` | plan parameter, scheduler model | mandatory per-harness cap (Grok 1, Agy 1), refused at plan otherwise; added to the TLA model and its check | 0025 |
| Grok bench credential home (`HB_GROK_CRED_HOME`) | credential | operator login once; cells seed from it and write back under a lock | 0025 |
| `telemetry/grok.py`, `telemetry/agy.py` | readers | new (with `TOOL_CLASS` for HB-VAL-008) | 0025, 0026 |
| `telemetry/{claude_code,codex,copilot}.py` | readers | served settings, reasoning items, prompt parts, harness events, per-request rows; `ToolInput.bytes_returned` | 0026 |
| `grade/runner.py` `PASS_FACTS`, `views.FACTS`/`KEYS` | fact streams | `served`, `reasoning`, `prompt_parts`, `harness_events` | 0026 |
| `views._validity`, `errors.py` | validity | HB-VAL-002 gains `model_served`; HB-VAL-010 (invalidating), HB-VAL-011 (warning) | 0024 |
| `board.pool_check` | pooling | effort and context in the cell tuple | 0024 |
| `report/pack_improvement.py` classifier, `report/context_growth.py`, `views` busy/idle | existing derivations | extended: tool phases, bytes, re-reads, per-request curve, hook and timeline time; `_matches_blast_radius` → `_changes.in_radius` | 0026 |
| `grade/_changes.py`, `grade/drift.py`, `grade/runner.applicable`, `bench/metrics.yaml` | grader, catalog | machine-written list, drift split, attention drift, `all_tasks`; catalog 0.7 → 0.8 | 0026 |
| `tests/archived_runs.py` fixture root, `tests/goldens/*` | test fixtures | self-contained `bench/` (GOLD-A); moved **first** | 0027 |
| `report/cost_compare.py`, `cli.py report --cost-compare` | renderer, CLI | new | 0027 |
| `bench/rings/lean-rerun.yaml`, `bench/rings/lean-rerun-probe.yaml` (names Inferred) | matrices | new (`bench-matrix/3`) | 0024 |
| `tools/served_check.py` (name Inferred) | readiness tool | thin wrapper over the views; plus the credential, real-store and debug-log scans | 0024, 0025, 0027 |

## Contracts at the seams

**Combo settings (ADR-0024).** A `/3` combo is `{id, harness, model, effort, context}`. `effort` is a string on the
vendor's own scale; `context` is an integer token count or `"default"`. A profile's `settings:` block says which
values it accepts. A plan whose combo asks for a value its profile does not accept is refused at plan time
(new HB-PRE code), so an unsupported setting never reaches a cell.

**Served settings (ADR-0024).** Each reader returns one `ServedSettings` per cell:

```
ServedSettings
  model_requested: str | NR; model_served: str | NR; model_api: str | NR      # NR = (None, reason)
  effort: str | NR; context_tokens: int | NR; context_tier: str | NR; reasoning_summary: str | NR
  sources: Mapping[field, str]                        # the record path + field it was read from
```

**Protocol modules (ADR-0025).** `stream_driver.open_session` and `stream_driver.send_turn` take exactly the
arguments `driver.open_session` and `driver.send_turn` take today and return the same `driver.TurnResult`.
`_attempt` chooses the module by `profile.transport`; there is no protocol class. Each module is the only one that
holds its protocol's names (an extended `tests/test_architecture.py` rule).

**Fact rows (ADR-0026).** `served`, `reasoning`, `prompt_parts` and `harness_events`, defined in ADR-0026 §1.
`model_calls` and `tool_calls` keep their columns. Tool arguments are not stored: they are read at report time
through the readers' existing `tool_inputs()`.

**Report (ADR-0027).** `cost_compare.build(views) -> CostCompare` is pure; `render(CostCompare) -> str`; the CLI
writes and opens it.

## Cross-cutting concerns

- **Security and identity.**
  - *Home isolation.* Every new cell sets `HOME` and `USERPROFILE` to the cell home as well as the harness's own
    home variable. Grok with only `GROK_HOME` read the real `~/.claude/CLAUDE.md` and skills (Verified, spike G1).
  - *Credentials (measured).* Copying `~/.grok/auth.json` into cells stranded the real login: after the spike's
    two cells, the real home reported "You are not authenticated" (2026-10-11 18:06). So Grok cells never copy a
    worker's credential. They use a dedicated bench credential home the operator logs into once, run one at a
    time, and write the refreshed file back under a lock. Antigravity authenticates through the Windows keyring in
    place (the Copilot pattern), and still authenticated after its spike (Verified). Readiness gates judge by
    authentication, not by file hash (ADR-0025 §7).
  - *Tools.* Grok cells are restricted to the ADR-0004 classes, and HB-VAL-008 detects any out-of-profile call;
    the prevention mechanism is Flagged (ADR-0025 §5). Env prefixes `GROK_`, `AGY_`, `GEMINI_`, `GOOGLE_` are
    dropped from every cell.
  - *Permissions.* Antigravity in headless mode silently denies commands and still reports `SUCCESS` (Verified).
    The profile seeds `settings.json` `permissions.allow` rules from the ADR-0004 class map (Verified that a seeded
    `command(git status)` rule lets the command run). `--dangerously-skip-permissions` is not used. A non-empty
    `denied_actions` is a cell failure, never a success.
  - *Self-update.* Grok in a fresh home updated itself from 1.0.41 to 1.0.50 within a minute (Verified). Cells run
    the pinned exe directly, seed `[cli] auto_update = false`, and agy runs with
    `AGY_CLI_DISABLE_AUTO_UPDATE=true` (the value `1` does not work, Verified). `check_build` re-hashes the exe at
    every cell start (existing, HB-CELL-115).
  - *Egress.* Copilot's debug log, agy's trajectory database and Grok's session files hold prompt text and account
    identifiers (Verified: the spikes found the account email). They stay under the git-ignored `runs/` and are
    never published. The archive has no content scan, only basename exclusions (`archive.py:234`), so the
    published surface is guarded instead: `--cost-compare` refuses to write without `BENCH_OPERATOR_EMAIL`, and
    excerpts pass an email- and UUID-shape filter (ADR-0027 §6).
- **Observability.** Every new fact is emitted on the normal grading path, with no flag. Every missing value
  degrades to `not recorded: <reason>`, never 0. The probe and the batch checkpoint print the served settings.
- **Idempotency.** Grading passes are already idempotent per pass (ADR-0006). The report is pure. Re-running the
  probe makes a new run id, never an overwrite.
- **Failure modes.**
  - A setting mismatch invalidates the cell (HB-VAL-010) and drops its pair, with the cause listed.
  - A harness that records no setting gives HB-VAL-011 (a warning), and the report shows `not recorded`.
  - A torn native record degrades its rows to `not recorded`, as the existing readers do.
  - An agy stream with an unknown event type is a protocol failure (the pack adapter's rule), so a silent format
    change fails loudly.

## LOA conformance

C1–C11 are written for AI capabilities. This amendment adds none, so the AI-specific criteria are N/A. The general
ones hold: determinism at the floor (T0 only); verification over plausibility (every setting is read back from the
harness's own record, not trusted from argv); idempotency at side effects (cells are append-only runs).

## Delivery phasing (vertical slices)

0. **Before any profile or catalog edit:** the GOLD-A fixture move (ADR-0027 §5), so later slices cannot redden
   a golden through a live input; the register entries DRIFT-MACHINE-A, RADIUS-TEST-A, LEAK-HOME-A; ruff pinned
   (TOOL-UNPINNED-A).
1. **Walking skeleton: one setting, end to end.** `bench-matrix/3` with `effort` and `context` on one combo, frozen
   per cell, applied by the Codex profile, read back by the Codex reader into a `served` row, judged by HB-VAL-010,
   and rendered in the existing validity section.
   - *Real:* matrix, plan, profile templating, the Codex reader, validity.
   - *Fake:* the cell (a recorded Codex rollout fixture; the synthetic agent for the launch).
   - *Human check:* `bench plan` on a /3 fixture shows `effort high` on every cell; `bench report` on the fixture
     run shows HB-VAL-010 on the cell whose rollout says `low`.
   - *Tests:* red first: a plan whose combo sets `effort: high` produces a launch with that setting for every
     harness (the prompt's R-SETTINGS red); a /2 matrix loads with `default`.
2. **Every harness's settings, plus the probe.** Claude Code, Copilot (two combos), Grok and Antigravity profiles,
   their readers' served settings, the two probe tools, and the transport seam with `stream_driver.py`.
   - *Human check:* a development probe's cells, each with served model, effort and context equal to the expected
     values (agy context `not recorded`), and a reasoning row. The formal R-PROBE runs only after the last `src/`
     and profile join (ADR-0024 §6, RECID-A).
3. **Anatomy facts.** The four new streams, tool arguments, `bench verify` over them, catalog 0.8 drift metrics,
   the two drift-grader fixes.
   - *Tests:* each reader on a recorded fixture per harness; the drift split on a fixture working copy that holds a
     cache, a hook log, a test file and a README edit.
4. **The cost-compare report.** `bench report --cost-compare`, its golden on a self-contained fixture.
5. **The run** (no code): probe, pre-registration, batch 1, checkpoint, batch 2, grading, verify, run report, cost
   report.

Slices 2 to 4 split into parallel tracks at the contracts above; that division is `/prepare-for-coordination`'s.

## Evidence ledger (spikes and reads, 2026-10-11 at `0c569647`)

Spike scratch: `C:\tf\spike-settings\`, `C:\tf\spike-grok\`, `C:\tf\spike-agy\` (credentials removed).

| claim | label | evidence |
| --- | --- | --- |
| combo keys other than `id`, `harness`, `model` pass validation silently | Verified | `config.py:129-136` |
| `config.HARNESSES` has grok and agy; `profiles.HARNESSES` does not | Verified | `config.py:35`; `profiles.py:26` |
| ACP is hard-wired in `_attempt`; no transport seam | Verified | `engine.py:806-902` |
| only `driver.py` may hold ACP method strings | Verified | `tests/test_architecture.py:23`, `:143-145` |
| `coord_transport`'s agy path discards event bodies (no usage, no tools, no model) | Verified | `coord_transport.py:4-5`, `:863-927` |
| `coord_transport` spawns its own process wrapper (Windows gate, Job Object) | Verified | `coord_transport.py:311`, `platform_process.py:117-146` |
| Claude Code honours `CLAUDE_CODE_EFFORT_LEVEL`; served effort on each assistant record | Verified | spike C1, transcript `.effort` |
| Claude thinking text only via `session/new` `_meta.claudeCode.options.thinking.display = "summarized"`; the setting is ignored in SDK mode | Verified | spike C3, `home3` |
| Claude transcript has per-request usage incl. `thinking_tokens`; dedupe by `requestId` | Verified | spike C4 |
| Codex honours `model_reasoning_effort`, `model_context_window`; served window 95% of 872,000 | Verified | spike X2, rollout `task_started` |
| codex-acp 1.12.0 overrides the summary to `auto` | Verified | spike X2, `codex-acp/dist/index.js:28858` |
| Copilot honours `--reasoning-effort` under ACP | Verified | spike P1, `session.start.reasoningEffort` |
| Copilot ignores long_context under ACP on 1.0.89-1 and 1.0.92-4 (4 knobs) | Verified | `C:\tf\spike-settings\tools\copilot_tier_probe.py` output |
| Copilot per-request usage only in the `--log-level debug` process log | Verified | spike P2 |
| `gpt-5.6-sol-fast` is answered by API model `gpt-5.6-sol` | Verified | spike P4, process log lines 424, 599 |
| Grok `--model`/`--reasoning-effort` belong to `grok agent`, before `stdio` | Verified | spike G2 |
| Grok needs `HOME`/`USERPROFILE` as well as `GROK_HOME`; auto-updates in a fresh home; loads project instructions only in trusted folders | Verified | spike G1, G5 |
| Grok token usage is per turn, not per model call | Verified | spike G3 |
| Grok's catalog lists `context_windows [256000, 500000]`; no ACP context option; `config.toml` `context_window` only sets the auto-compact trigger | Verified (catalog, ACP); Inferred (not selectable) | spike G2, G4; `~/.grok/README.md:1844-1849` |
| agy stream: per-step usage with `thinking_tokens`; no context window anywhere | Verified | spike A3 |
| agy thinking text is in `conversations/<id>.db` `steps.step_payload` (protobuf) | Verified | spike A4 |
| agy headless denies commands silently; a seeded `permissions.allow` rule works | Verified | spike A3; `C:\tf\spike-agy\perm_probe.py` |
| property graders already skip test paths (`is_test_path`) | Verified | `diffstats.py:123`, `rework.py:75`, `noguess.py:197` |
| none of the ten lean tasks runs the drift grader (`graders: [correctness, property]`) | Verified (gate) | `tasks/*/task.yaml` |
| copying `~/.grok/auth.json` into cells stranded the real login | Verified (effect); Inferred (cause: refresh-token rotation) | `grok models` "You are not authenticated", file rewritten 18:06 after the spike's two cells; the access token is a JWT that expired 2.4 h earlier |
| Copilot 1.0.92-4 also ignores long_context under ACP | Verified | `copilot_tier_probe.py` with `CP_AUTO_UPDATE=true` (agent version 1.0.92-4) |
| `tool_inputs()` already gives every reader's tool paths and commands | Verified (gate) | `telemetry/__init__.py:206-215` |
| HB-VAL-002 judges every `model_calls` model today | Verified (gate) | `views.py:542` |
| `pool_check` ignores `plan_hash`; its cell tuple is `(task, combo, arm, model)` | Verified (gate) | `board.py:816`, `:824` |
| `runs/` is git-ignored | Verified | `.gitignore:15`; `git ls-files runs` = 0 |
| `.pytest_cache` is not excluded by the drift grader | Verified | `_changes.py:34`; `drift.py:75-124` |

## Residual architectural risk

- **Equal setting is not equal depth.** "High" is each vendor's own scale. The report shows reasoning tokens per
  cell beside it, and says so.
- **Unequal windows.** Copilot runs at 272k and Grok at 256k against 1M for Claude Code and 872k for Codex. A cell
  that would have fitted a larger window may compact. Compaction events are recorded where the record carries them.
- **Grok's per-turn usage** means no per-request curve for Grok (`not recorded: per-turn totals only`).
- **Credentials.** Grok's separate bench login is Inferred to be a separate token family; agy's keyring under
  concurrent refresh is Inferred safe. Both are gated at readiness by authentication.
- **Grok tool restriction** may be detection-only (Flagged); then it goes to the operator.
- **Claude Code's prompt parts, hooks and skill loads** have Flagged sources; absent, they are `not recorded`.
- **Model time for Claude Code and Grok** is the ACP-arrival estimate, labelled as such, not a native measure.
- **Grok cells run one at a time**, which lengthens the batch; the checkpoint measures it.
- **agy's protobuf payload** has no published schema. The reader decodes the wire format with a field map taken
  from the spike; a change reads as `not recorded`, never as wrong text.
- **Two harnesses never timed in a cell.** The batch-1 checkpoint measures them.

## Gate record

*Adversary-mode council, 2026-10-11: one Opus sub-agent with the Simplifier, Test Architect, Data & Persistence,
SRE, Security & Identity, Distributed Systems, Enterprise and coverage lenses, reading the code at `0c569647`. Three
rounds: the review, a re-judgement of the revision, and a re-check of the last open veto. The author re-ran the veto
evidence (`profiles.py:28-33`, `views.py:542`, `board.py:812-826`, `telemetry/__init__.py:206-215`, `.gitignore`)
and measured the Grok credential effect before revising. No veto was cleared by the author.*

| # | lens | finding | resolution |
| --- | --- | --- | --- |
| 1 | Test Architect | **VETO.** `"default"` was recorded, never judged, so Copilot's 272k and Grok's 256k had no verification path (SERVE-A's root). | `default_serves` per profile, judged (ADR-0024 §3-4). **Cleared by the council, round 2.** |
| 2 | Distributed | **VETO.** Copying Grok's `auth.json` strands rotating refresh tokens; the hash probe could not detect it. Measured by the author: the real Grok login was stranded by the spike. | Dedicated bench credential home, one Grok cell at a time, atomic write-back before clean under an `oslock`, a gate that forces a refresh, a two-failure stop, a mandatory cap in the plan and the TLA model, agy capped at 1, no agy worker during a batch, write-back on resume (ADR-0025 §7). **Cleared, round 3.** |
| 3 | Security | **VETO.** The published page could carry account ids; the egress scan degrades without the operator email; the claimed archive scan does not exist. | Fail-closed `BENCH_OPERATOR_EMAIL`, an email/UUID excerpt filter, raw records never published, the sentence corrected (ADR-0027 §6). **Cleared, round 2.** |
| 4 | Security | **VETO.** Grok had no tool policy; `GROK_`/`GEMINI_`/`GOOGLE_` env leaked into cells. | ADR-0004 restriction, `TOOL_CLASS` and HB-VAL-008, a decision request if detection-only (due before the formal probe), `DROP_PREFIXES` extended (ADR-0025 §5, §8). **Cleared, round 2.** |
| 5 | Coverage | agy could not run the two-turn RW tasks. | Multi-turn `stream_driver` (ADR-0025 §3). |
| 6 | Enterprise | Grok reuse dropped the SERVE-A `set_model` control. | `set_model: true` and a fail-closed `_meta.model` check (ADR-0025 §2, §5). |
| 7 | Enterprise / Simplifier | The `Transport` contract dropped `_attempt`'s arguments. | Struck; same signatures, module chosen by profile. |
| 8 | Test Architect | The probe (pack-off, X1) could not see what breaks batch 1. | Both arms on a real property task plus RW1 for agy; instruction-file clauses (ADR-0024 §6). |
| 9 | D&P | HB-VAL-002 would change input and flip old runs. | Keeps `model_calls`; `model_served` added; exact alias table. |
| 10 | D&P | Pooling mechanism mis-cited. | Corrected; `pool_check` tuple gains the settings. |
| 11 | D&P / Simplifier | `anatomy.py` and stored tool args duplicated existing derivations. | Struck; `tool_inputs`, `context_growth`, the classifier and `views` extended (ADR-0026 §4). |
| 12 | D&P | Second radius definition; machine list would hide audit edits and move property graders. | Separate machine list, exact hook outputs shown on their own row; `_matches_blast_radius` swept. |
| 13 | D&P | Drift scope, bool column, duplicated requested values, no disagreement rule. | Restated; ints; requested from the plan; disagreement → HB-VAL-010. |
| 14 | D&P / Test | Catalog 0.8 moves the non-lean golden; freeze steps unstated. | Freeze steps written; GOLD-A fixture move sequenced first (slice 0). |
| 15 | SRE | Bounds unstated (BND-A). | Measured at the probe; one line cap; debug log in the disk projection. |
| 16 | SRE | Sidecar clock and join. | Monotonic, anchored, joined by index; mismatch → `not recorded`. |
| 17 | SRE | Self-update could rewrite the shared exe. | Read-only installed executables. |
| 18 | RECID-A | Probe before the last join. | Formal probe after the last join; profile decisions by a development probe before it. |
| 19 | Test Architect | Oracle test on private internals; 1.2.7 grammar. | Public `run_session` with a replay process, 1.3.3 streams, an outcome table. |
| 20 | Test Architect | Codex 95% rule from two points. | The cell's own catalog percent, source recorded. |
| 21 | Coverage | Per-harness sources, model time for every harness, Claude instruction files, `show_raw`, owners, `INSTRUCTION_FILES`. | Source tables; ACP timeline estimate; `not recorded` fallback named; development-probe decision; owners named; list extended. |
| 22 | Enterprise | The agy reuse deviates from the prompt's words. | **To the operator** (decision request below). |
| 23 | Enterprise | `render-markdown`'s launcher calls `subprocess`. | `cli.py`-only call site named in the rule, with a test. |
| 24 | Simplifier | `model_id` settings unchecked; `served_check` repeats the views. | Plan-time consistency check; thin wrapper. |
| 25 | Security | APPDATA/LOCALAPPDATA, global git config, nested seed dirs. | Probe listing; `GIT_CONFIG_GLOBAL`; `seed_home` parents. |
| N1–N5 | round 2 | Radius-swap output change; unbounded timeline; two model-time definitions; profile flip after the probe; no fallback on a bearer hit. | Each resolved (ADR-0026 §3-4, ADR-0024 §6, ADR-0027 §6); confirmed round 3. |

**Verdicts after revision:** Simplifier pass. Test Architect, Data & Persistence, SRE, Security & Identity,
Distributed Systems, Enterprise and coverage: pass-with-changes, every change applied above. No hard veto open.

**Open for the operator (decision requests):**

- **DR-AGY-REUSE (finding 22).** The prompt says to reuse the pack's agy adapter behind the engine. The design uses
  it as the conformance oracle instead (ADR-0025 §3-4), because it discards the bodies the bench must record and
  spawns its own process. Recommendation: accept the oracle design.
- **Grok tool prevention** (ADR-0025 §5): only if design-slice finds Grok cannot block forbidden tools; due before
  the formal probe.

**Operator actions:** `grok login` in the real home (stranded 2026-10-11; the Grok workers need it), and a
`grok login` into the bench credential home before the readiness gate.
