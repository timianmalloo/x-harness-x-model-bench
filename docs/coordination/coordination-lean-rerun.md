---
id: coordination-lean-rerun
title: "Coordination plan - the lean re-run at equal reasoning (build, join, probe, run, report)"
type: plan
status: proposed
owner: "@timianmalloo"
tags: [coordination, worktrees, parallelism, lean-benchmark, lean-rerun]
links:
  - { to: arch-lean-rerun, rel: implements }
  - { to: adr-0024-combo-settings-and-served-read-back, rel: implements }
  - { to: adr-0025-transport-seam-grok-and-agy-cells, rel: implements }
  - { to: adr-0026-per-cell-anatomy-facts-catalog-0-8, rel: implements }
  - { to: adr-0027-cost-compare-report, rel: implements }
  - { to: adr-0028-copilot-prompt-mode-transport, rel: implements }
  - { to: adr-0029-ai-forward-pack-cost-analysis, rel: implements }
  - { to: coordination-lean, rel: relates-to }
review-by: "2026-10-26"
summary: >-
  Eighteen tracks: three before wave 1, run in parallel (the GOLD-A fixture move and two contract tracks that fix
  every shared file's structure in code), thirteen in wave 1 split into two dispatch halves at the cap of six, and two
  in wave 2 (the derivations and the AI-Forward pack cost analysis). A Leader-held serial spine carries batched joins, a development probe, the catalog 0.8 freeze and gate
  ring, the batch gate, the formal readiness probe, the pre-registration and the two batches. Derived and register
  artifacts need no coordination; every authored file has one owner at a time, and shared mutation files take
  hand-back retargets only. Grok and Agy get small briefs and a floor canary first. Seven tracks were struck or
  merged. Revised after the adversary gate (three vetoes, cleared by change).
---

# Coordination plan: the lean re-run at equal reasoning

*Written 2026-10-12 by the Leader seat (Claude Code, `claude-opus-5-5[1m]`, session `lean-rerun-leader`) at
`af3da009`, and revised the same day after the adversary gate (see the gate record). Sources:
`docs/coordination/lean-rerun-equal-reasoning-prompt.md` (seats, rules, the plan-output fields);
`docs/architecture-lean-rerun.md` with ADR-0024 to ADR-0027; Rulings 117-119; the 2026-10-10 plan's *Planned vs
actual* (`docs/coordination/coordination-lean.md:363-400`); the defect register. Durations and budgets are
**Inferred** from that run's measured analogues unless marked.*

**Operator rulings folded in (2026-10-12):** Ruling 120 (Copilot in `-p` mode at long_context, ADR-0028; track
R-COPILOT-P) and Ruling 121 (two reports for two audiences: the harness cost comparison for the Copilot team, and the
AI-Forward pack cost analysis for the pack owner, ADR-0029; track R-PACKCOST and an analyst seat at S9).

## Layer state

| check | result | meaning |
| --- | --- | --- |
| `coord doctor` registry | ok - 11 pattern(s) (read 2026-10-11 and 2026-10-12) | `.agents/artifacts.yml` is installed and classifies the derived and register files below |
| `coord doctor` merge driver | effective - coord-regen, coord-register declared and registered | installed **once, in the primary**. Every worktree inherits it through the shared `.git/config`. Never run `coord install` in a tree; run `coord doctor` in each tree to read it back |
| `coord doctor` leader | released (epoch 20) | this run pins **epoch 21** first |
| `coord doctor` requests | 125, 0 open | no decision request is pending |
| `coord doctor` lease overlap | none (0 live leases) | no claims |
| `coord worktree list` | 1 worktree: the primary, on `main` | nothing to clean before S0 |
| harness edit boundary (spikes, not measured here) | claude: enforcing (S5); copilot: historical | Grok and Agy have no edit-boundary spike: **observed-only**. The commit floor enforces for every harness |
| `pack-doctor` | 0 FAIL, 3 WARN (`python3` alias; Copilot global settings; stale doc nodes) | use `python`, never `python3` |
| `pack-doctor` doorbells | not recorded | hand-back is by the runner's exit and the session ledger |
| SUITE-LOCK (LOAD-A) | `tests/suite_lock.py`: one machine-wide lock for every heavy run (full suite, `-n`, directory run, `mutate_check`) | six workers run light, named-file tests concurrently; heavy runs queue on the lock, so the cap of 6 does not breach LOAD-A's measured limit (`defect-classes.md:878-893`). Queue time is measured per track |
| Grok login, real home | stranded 2026-10-11 18:06 (CRED-COPY-A); **re-logged by the operator 2026-10-12**: `grok models` reads "You are logged in with grok.com" (`auth.json` 07:02) | Grok workers can be dispatched |
| agy login | authenticates (`agy models`, 2026-10-11) | Agy workers can be dispatched |
| ai-forward `feat/run-report-open` | pushed, `ed9625a7` (Ruling 117 item 1, resolved) | the pack-on arm's revision is chosen at S0 and recorded |
| Ruling 117 items 2-4 | resolved: agy pinned 1.3.3; reasoning text in `runs/<run>/reasoning/`; `gpt-5.6-sol-fast` kept | no open decision |

## Artifact classes

| path / pattern | class | mechanism | coordination needed |
| --- | --- | --- | --- |
| `docs/docs-index.js` | derived | `docs-graph.py derive` (registry) | **no**: regenerated at each join |
| `docs/audit/audit-data.js`, `docs/audit/index.html` | derived | `audit-log.py ... render` (registry) | **no** |
| `docs/audit/audit-log.jsonl`, `docs/audit/change-log.jsonl` | register | union merge (registry) | **no**: append only |
| `.agents/log/*.jsonl` | register | union merge (registry) | **no**. Never edited (LOGTEAR-A) |
| `docs/specs/harness-bench.html`; skill copies under `.claude/skills/**`, `.agents/skills/**` | derived | `render-doc-html.py`, `sync-skills.py` (registry) | **no**; no track edits their sources |
| `docs/notes/rulings.md` | authored, one writer | the Owner (`owner-fable`) rules into it; the operator's rulings are written by the Leader | Owner / Leader only |
| `docs/lessons/defect-classes.md` | authored, one writer | tracks **hand back** class text; only a Coordinator edits the file | Coordinator only |
| `tests/mutations/*.json` (existing files) | authored, **shared** (not in `.agents/artifacts.yml`) | many tracks' edits move their finds (the gate measured `validity.json`, `stop.json`, `scenario6.json`, `classify.json`, `t3.json`, `r34.json`, `profile_classes.json`, `copilot_reader.json`, `engine.json`, `grade.json`, `plan.json`, `copilot.json`, `scripted_user_wiring.json`, `pack_improvement.json`, `views.json`) | **one writer, the Leader.** A track never edits an existing mutation file: new mutants go in a new per-track file (`tests/mutations/rerun-<track>.json`), and retargets of existing finds are **handed back as text**; the Leader applies them on the candidate before the recount, and MUT-E (`test_mutate_check.py:413`) checks them |
| `tests/fixtures/bench-root/**` | authored, frozen test data | written by R-GOLD; frozen after J0 (no wave-1 edit) | R-GOLD, then the Leader |
| `tests/goldens/**` | authored, test data | captured by the owning track; re-captured only with a stated reason | the owner named in *Seams* |
| `runs/**`, `C:\tf\<track>\**` | not in git (`.gitignore:15`) / scratch | — | **no** |
| every other path a track names below | authored | one owner per file at a time (Tracks) | the only real contention |

## Tracks

**Why pay the multiplier.** An orchestrator-worker shape costs roughly **15×** the tokens of one session (GO6). Each
track's justification is named in the detail table: **independence**, **isolation**, **context hygiene**, or
**machine time**. The token figure in each budget is a **context ceiling per dispatch** (the CEIL-A split threshold:
the floor measured at the first edit plus the planned work), not total spend; spend is measured at each hand-back and
summed in the run report. Last run's floors: Opus Coordinator 137k, Opus worker about 109k, Haiku about 99k, Grok
about 117k, Agy about 166k, all for ~75 kB briefs.

**Routing.** Opus carries every T2 track and every track whose failure mode is judgement, including the validity
gate. Grok and Agy take bounded, test-heavy work with a brief under ~30 kB. **Floor canary:** the first Grok track
(R-READ-CODEX) and the first Agy track (R-READ-COPILOT) are dispatched alone first; their floors at the first edit
are recorded, and every later Grok or Agy row is routed by that number (a floor that leaves under 60k of room routes
the row to Opus). Haiku takes mechanical work. Codex, Sonnet and Copilot are not workers.

**Pins:**
- Grok `grok-4.7`, `--reasoning-effort high`, `XAI_API_KEY` unset (R-103). The served id is read with
  `tools/grok_served_model.py --tree`; a non-`grok-4.7*` first response kills the turn, one retry, then Opus.
- Agy `gemini-3.8-flash-high`; served id from the runner's record.
- Claude sub-agents through the Agent tool, always with an explicit `model`: Opus `claude-opus-5-5`; Haiku
  `claude-haiku-5-5` (re-checked at S0).

**Common to every row:** leader **epoch 21**; **fan-out cap 0** (FALLBACK-A); decision requests go to
**`owner-fable`** (Claude Code, Fable), ruled into `docs/notes/rulings.md`; scratch under `C:\tf\<track>`; seats
never write the primary; a new session id per continuation (IDN-A) and a new branch per new runner turn; the health
check at every dispatch **and every join**.

**Common exit evidence (R-104 and the measured lessons):**
- the worker's own tests are red first, on an assertion, and then green;
- the guard list runs on the first and the final commit;
- `uv run python tools/mutate_check.py tests/mutations/rerun-<track>.json` (the track's own new file); retargets of
  existing finds handed back as text;
- `uv run ruff check src tests tools bench/adapters` (ruff pinned by R-GOLD: TOOL-UNPINNED-A);
- `docs-graph.py validate` passes; `test_identity.py`, `test_architecture.py`, `test_arms_guard.py` pass;
- the console flag on every launch the track adds (`tests/test_console_windows.py`);
- every committed fixture scrubbed (`tools/acp_record.py scrub --forbid …`), with no email, account id,
  `Authorization`, `Bearer ` or `eyJ…` (JWT) shape;
- the served id recorded; the windows check at hand-back;
- the closing audit entry **committed** in the track's tree (AUDIT-STRAND-A);
- a new defect class handed back as text, never written to the register;
- no `--no-verify`, `-n` or hooks override, and no rewritten commit; never edit a log.

**The whole suite is the Leader's** (rule 2): one full suite on the candidate, then the join recount; a red that
passes alone gets one retry; a second red goes to a loop-back fix track on Opus; FLAKE-A instances recorded. Joins
are **batched** (below, S2).

| track | owns (authored) | depends on | tier | fan-out cap | budget | exit evidence | harness |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **R-GOLD** self-contained golden fixtures, ruff pin | `tests/archived_runs.py` (`make_root`, `make_run`): a **frozen** mode, the default, whose root carries its own copies of `bench/metrics.yaml`, `bench/profiles/*`, the tools pin and `tasks/X1` under `tests/fixtures/bench-root/`; a **live** mode kept for the named consumers that test the real catalog's identity (`tests/test_catalog_version.py`, `tests/test_grade_formal.py`; the full list is the track's first output, read from `make_root(release=False)` callers, `archived_runs.py:86-88`); `tests/test_fixture_root_isolation.py` (new); any re-captured golden (reason: "fixture root self-contained; html.py unchanged"); `pyproject.toml` dev group (ruff pinned to the version `uv run ruff --version` prints today) and `uv.lock` | epoch 21 | T1 | 0 | 60 calls · 109k + 80k · 1 · 1.0 h | red: the isolation test fails today (the root copies live `bench/`, `archived_runs.py:93-96`). Green: it passes; editing a live `bench/profiles/*.yaml` byte in a scratch copy leaves `tests/goldens/report-nonlean-arms.html` and `tests/test_pack_improvement_golden.py` green; the live-mode consumers are listed and still read the live catalog (a test per consumer); the full suite green on the branch (Leader). GOLD-A's status handed back ("controlled") | Claude Code Agent tool, Opus (judgement: 85 test files use `make_root`) |
| **R-CONTRACT-RUN** run-side seams in code | `src/harness_bench/profiles.py` (the `Profile` fields `settings` incl. `default_serves`, `transport`, `session_meta`, `user_home_vars`, `seed_files`, `credential_home_env`, `model_aliases`, parsed with defaults that keep the three existing profiles' `profile_record` byte-equal; `HARNESSES` gains `grok`, `agy`; placeholder expansion `{effort}`, `{context_tokens}` at `:95`, `:112`, `:133-135`, a no-op for `"default"`); `src/harness_bench/plan.py` (`Cell.effort`, `Cell.context` defaulting to `"default"`; `cell_id` includes them only when not `"default"`; `harness_parallelism` frozen, default `{}`); placeholders `{python}` (the bench interpreter), `{home}` (the cell home) and `{context_arg}` (from the profile's settings value map: `default` → nothing, e.g. `922000` → `--context long_context`; ADR-0028 §3); the `scripted_user: unsupported` profile flag; `src/harness_bench/engine.py` (`_attempt` picks `driver` or `stream_driver` by `profile.transport`; nothing else); stubs `src/harness_bench/stream_driver.py` (the signatures of `driver.open_session`/`send_turn`, raising `NotImplementedError`), `telemetry/grok.py`, `telemetry/agy.py`; `src/harness_bench/cli.py` (argparse for `report --cost-compare RUN... --out --open`, `report --pack-cost RUN... --out --analysis --open` and `tools install --vendored`; each handler is one call to its module's `cli_main(args)`, so no wave track edits `cli.py`); `src/harness_bench/identity.py` (`CLASSES` for every new file: `stream_driver.py`, `telemetry/grok.py`, `telemetry/agy.py` `run`; `report/cost_compare.py`, `report/pack_cost.py`, `report/tool_phases.py`, `report/publish.py` `grade`); `tests/test_architecture.py` (an agy-stream rule scoped to the stream's **input and outcome grammar** — the `user` input event and the `result`/`denied_actions` outcome — held only by `stream_driver.py`, with `telemetry/agy.py` allowed to read event bodies; `stream_driver.py` in the run-path rule; the one call site to `render-markdown.open_in_chrome`, in `report/publish.py`, named); `tests/test_contract_run.py` (new) | epoch 21 | T1 | 0 | 80 calls · 109k + 120k · 1 · 1.3 h | `tests/test_contract_run.py` pins the new fields' names and defaults, the placeholder expansion (a cell with effort `high` puts `high` in argv, env and a seeded file for a fixture profile; `default` changes nothing; `{python}` expands to `sys.executable`; `{home}` to the cell home; `{context_arg}` with `default` **drops its argv element** and with `922000` gives `--context`, `long_context`), the console-window guard's `ROOTS` extended to `bench/adapters` (`tests/test_console_windows.py:14`, edited by this track only), `cell_id` unchanged for every existing plan fixture (RECID-A), and the three profiles' `profile_record` hashes unchanged (red first: the names are absent). The full suite green on the branch, no behaviour change for any existing run. **Joined (J0) and pushed before wave 1** | Claude Code Agent tool, Opus |
| **R-CONTRACT-FACTS** grade-side seams in code | `src/harness_bench/errors.py` (HB-VAL-010, HB-VAL-011, the HB-PRE setting-refusal, cap-refusal and scripted-user-unsupported codes, the HB-CELL blocked code; numbers checked free); `src/harness_bench/telemetry/__init__.py` (`ServedSettings`, `ToolInput.bytes_returned`, the four reader hooks `served/reasoning/prompt_parts/harness_events` defaulting to "not recorded: reader not built"); `src/harness_bench/telemetry/normalize.py` (the four row builders, ADR-0026 §1's columns exactly); `src/harness_bench/grade/runner.py` (`PASS_FACTS` and the four streams written from the hooks); `src/harness_bench/views.py` (`FACTS`, `KEYS` for the four streams); `src/harness_bench/config.py` (`validate_metrics` accepts `all_tasks`); stubs `src/harness_bench/report/cost_compare.py` (the `CostCompare` dataclasses of ADR-0027), `report/pack_cost.py` (the `PackCost` dataclasses of ADR-0029: the decomposition terms, the component map, the candidates), each with `build`/`render`/`cli_main` raising `NotImplementedError` and each combo row carrying its `transport` (a plan fact); `report/tool_phases.py` (the shared classifier's and the carry-until-compaction function's signatures); a `request_series(view, cell_id)` signature stub in `report/context_growth.py` (ownership passes to R-DERIV at J1b) and `report/publish.py` (`publish(html, out, open)`'s signature); `tests/test_contract_facts.py` (new) | epoch 21 | T1 | 0 | 80 calls · 109k + 120k · 1 · 1.3 h | `tests/test_contract_facts.py` pins every new dataclass's field names and order, every row builder's columns (ADR-0026 §1, quoted), the new codes, and that a metric with `all_tasks: true` validates (red first). **A tamper test:** a `reasoning` row edited after sealing makes `bench verify` exit non-zero (the prompt's R-REASON: "checked by bench verify"). The full suite green, no behaviour change for an old run's view. **Joined (J0) and pushed before wave 1** | Claude Code Agent tool, Opus |
| **R-SETTINGS** `bench-matrix/3`, plan refusals, isolation, write-back | `src/harness_bench/config.py` (`validate_matrix` /3; unknown combo keys refused in /3); `src/harness_bench/plan.py` (plan-time refusal of an unsupported value; `model_id` consistency; refusal of a grok or agy combo unless capped at 1; refusal of a scripted-user task for a profile flagged `scripted_user: unsupported`; ownership passes from R-CONTRACT-RUN at J0); `src/harness_bench/profiles.py` (`DROP_PREFIXES` gains `GROK_`, `AGY_`, `GEMINI_`, `GOOGLE_`; `seed_home` creates parents; `model_allowed` with the exact alias table; the Grok credential seed and atomic write-back in `ProfileLauncher.clean` before deletion, under an `oslock` on the credential home; `GIT_CONFIG_GLOBAL` in `CELL_ENV`); `src/harness_bench/preflight.py` (the Copilot debug log in the HB-PRE-003 disk projection, `:49`); `src/harness_bench/board.py` (`pool_check`'s cell tuple gains effort and context); `bench/profiles/{claude-code,codex}.yaml` (settings blocks; Claude `session_meta` thinking display); `bench/rings/lean-rerun.yaml`, `bench/rings/lean-rerun-probe.yaml`; `tests/test_settings.py`, `tests/test_cred_writeback.py`, `tests/test_isolation_env.py` (new); `tests/mutations/rerun-settings.json` | J0 | T2 | 0 | 150 calls · 109k + 150k · 2 · 2.5 h | red first, for the Claude Code and Codex profiles: a combo with effort `high` reaches each one's launch (env or `config.toml`). Also red: a /2 matrix loads with `default`; an unsupported value is refused with the new HB-PRE code; a grok combo without cap 1 is refused; `pool_check` refuses two batches differing only in effort; a cell env carries no `GROK_`/`GEMINI_`/`GOOGLE_` variable from the parent; the write-back test (a fake credential whose refresh rotates, two sequential cells, the bench home holds the newest token; a second engine waits on the lock); the disk projection counts a debug log. The five-harness red and the 120-cell plan proof are **Leader evidence at J1a**, after R-TRANSPORT's two profiles and R-COPILOT-P's profile join (gate finding 1) | Claude Code Agent tool, Opus |
| **R-CAP** the per-harness cap, auth stops, resume write-back, instruction lists | `src/harness_bench/engine.py` (the scheduler at `:478-481`: the `harness_parallelism` cap; an authentication failure is an infrastructure outcome, and two consecutive ones for one harness stop the batch); `src/harness_bench/resume.py` (ADR-0021: a leftover cell home's newer `auth.json` written back before Grok cells resume); `models/run_lifecycle.tla` and its `.cfg` files; `tests/test_check_models.py`, `tests/test_engine.py` (cases; `test_parallelism_is_never_exceeded`, `:1217`, stays green); `src/harness_bench/workspace.py` (`INSTRUCTION_FILES`/`INSTRUCTION_DIRS` gain `GEMINI.md`, `.agents/rules`, `.agents/skills`, `.grok/`); `tests/test_workspace.py` (cases); `tests/mutations/rerun-cap.json` | J0 | T2 | 0 | 100 calls · 109k + 120k · 1 · 1.7 h | red: with a cap of 1 for one harness and parallelism 3, a scheduler test shows two of its cells running at once (today); the TLA model with the cap fails its new invariant before the spec change and passes after (the model check's output quoted); two consecutive auth failures stop the batch with a named stop, one does not; resume writes back a newer leftover `auth.json`; HB-PRE-009 removes and then refuses an upstream `.agents/rules/x.md` (red today). Existing scheduler, resume and liveness tests green | Claude Code Agent tool, Opus (judgement: a TLA-modelled scheduler) |
| **R-TRANSPORT** the ACP additions, the agy driver, the two new profiles | `src/harness_bench/driver.py` (`session_meta` on `session/new`; the fail-closed `set_model` `_meta.model` check; `acp-timeline.jsonl`, collapsed by kind, buffered, best-effort); `src/harness_bench/stream_driver.py` (ADR-0025 §3); `bench/profiles/grok.yaml`, `bench/profiles/agy.yaml`; `tests/test_stream_driver.py`, `tests/test_agy_oracle.py` (the oracle through public `coord_transport.run_session` with a replay process), `tests/test_profiles_new.py` (new); `tests/fixtures/agy/stream/*.ndjson` (recorded 1.3.3 streams, scrubbed) and `tests/fixtures/agy/stream/replay.py`; additions in `tests/test_driver.py`; `tests/mutations/rerun-transport.json` | J0 | T2 | 0 | 170 calls · 109k + 160k · 2 · 2.7 h | red first: each outcome-table row on a recorded stream; the oracle agrees with `coord_transport` on all five streams; a denial is never a success; a `set_model` answer with another `_meta.model` fails before the prompt (HB-CELL-116); `session/new` carries the profile's `_meta`; the stream driver spawns through `procs` (a test asserts the `CellProcess`); a sidecar count mismatch gives `not recorded`; a 9 MiB line is a protocol failure; a 10,000-chunk turn's timeline is under 100 lines; a timeline write failure leaves the outcome unchanged. **Profile launch tests** (red: the profiles are absent): Grok's env sets `HOME`, `USERPROFILE`, `GROK_HOME` and lacks `XAI_API_KEY`; its argv has `--model` and `--reasoning-effort` before `stdio`; `set_model` is true; `trusted_folders.toml` names the worktree in **both** arms; `config.toml` has `auto_update = false`; agy's env has `AGY_CLI_DISABLE_AUTO_UPDATE=true`, its argv ends `-p=`, and its seeded `settings.json` holds the allow and deny rules. Existing driver tests green | Claude Code Agent tool, Opus (judgement: two coupled protocol modules in one session) |
| **R-BUILDS** Grok and Antigravity builds | `src/harness_bench/tools.py` (`LAYOUT` gains grok and agy; the vendored-exe install from `bench/tools/vendored.json`, hash-checked; installed executables read-only; `check_build` for both); `bench/tools/package.json` (`@xai-official/grok` `1.0.41`) and its lockfile; `bench/tools/vendored.json` (agy `1.3.3`, sha256 `fbbfb3f1…a25b`); a **repo-local adapter mode** for the Copilot entry: today `LAYOUT` resolves adapters only as npm packages (`tools.py:138-145`); the new mode reads the adapter's path, version and sha256 from `bench/adapters/copilot_p_acp.pin.json` (a data file R-COPILOT-P owns), so a later adapter fix never edits `tools.py`; the build record also carries the bench interpreter's `sys.version` and path (`{python}`'s identity); `tests/test_tools.py` cases; `tests/mutations/rerun-builds.json` | J0 | T1 | 0 | 60 calls · 109k + 70k · 1 · 1.0 h | red: `tools.resolve` has no grok or agy entry today; a vendored source with another hash is refused; an installed exe is read-only; `check_build` raises `BuildChanged` after a byte change, including a change to the local adapter against its pin file; a local adapter whose bytes differ from its pin is refused at resolve; the build record carries `sys.version` and the interpreter path (asserted). Green on the Leader's `bench tools install` (TEST-E: the brief's author runs it once and quotes the output). The Leader re-checks the adapter pin against R-COPILOT-P's final commit at J1a | Claude Code Agent tool, Opus (the local-adapter resolution mode is new code, not the existing pattern: gate round 3) |
| **R-DRIFT** the drift split, attention drift, one radius definition | `src/harness_bench/grade/_changes.py` (the machine-written list, separate from `BUILD_OUTPUT`); `src/harness_bench/grade/drift.py` (`drift_machine_lines`, `drift_task_implied_lines`, `scope_creep` redefined, `attention_drift`); `src/harness_bench/grade/runner.py` (`applicable` honours `all_tasks`; ownership passes from R-CONTRACT-FACTS at J0); `bench/metrics.yaml` (`0.8.dev`, the four metrics with `all_tasks: true`, notes, `scope_creep`'s anchor Flagged); `src/harness_bench/report/pack_improvement.py` (`_matches_blast_radius` → `_changes.in_radius` only); `tests/test_drift_split.py`, `tests/test_radius_consumers.py` (new); any moved golden, re-captured with the reason "radius match is case-sensitive (one definition)"; `tests/mutations/rerun-drift.json` | J0 | T2 | 0 | 140 calls · 109k + 140k · 2 · 2.3 h | red first: on a fixture working copy holding `.pytest_cache/x`, a hook log, `tests/test_limiter.py` and a README edit, machine-written 2 rows, task-implied 1, discretionary 1 (today all four are scope creep); **a lean-task fixture (graders `[correctness, property]`) yields all four drift scores** (the point of `all_tasks`); attention drift on a fixture tool sequence equals a hand count; the radius-consumer test fails today on `_matches_blast_radius`. The pack-improvement golden and the non-lean golden run before and after; any re-capture states its reason. The ten tasks' `task_version_hash` unchanged | Claude Code Agent tool, Opus (judgement: a catalog change) |
| **R-READ-CODEX** Codex reader facts (Grok floor canary) | `src/harness_bench/telemetry/codex.py` (served settings, reasoning items, prompt parts, harness events where present, per-request rows, `bytes_returned`); `tests/test_reader_codex.py` (new); `tests/fixtures/codex/rerun-*.jsonl` (scrubbed); `tests/mutations/rerun-read-codex.json` | J0 | T1 | 0 | 60 calls · canary + 50k · 1 · 1.0 h | red first on the scrubbed rollout: served `model`, `effort` `high`, window 828,400 with the catalog percent's source; two reasoning rows (`summary` with text; `encrypted-only` with a sha256); the AGENTS.md block as an `instruction_file` part on a pack-on fixture and none on pack-off. Existing Codex reader tests green | Grok (bounded; brief under 30 kB; dispatched first, alone, as the Grok floor canary) |
| **R-READ-COPILOT** Copilot reader facts (Agy floor canary) | `src/harness_bench/telemetry/copilot.py` (served settings incl. `model_api` from the debug log; reasoning from `reasoningText`; prompt parts from the debug-log request body; hooks and skill loads; per-request rows from the debug log, else session totals marked); `tests/test_reader_copilot.py` (new); `tests/fixtures/copilot/rerun-*` (scrubbed, incl. `Authorization`/bearer shapes); `tests/mutations/rerun-read-copilot.json` | J0 | T1 | 0 | 60 calls · canary + 50k · 1 · 1.0 h | red first on the scrubbed fixtures: `selectedModel`, `reasoningEffort` `high`, `contextTier` `long_context` from a **`-p`-mode** session record (the settings spike's `home-p`, scrubbed; the ACP-era `usage_update.size` does not exist on this path); `gpt-5.6-sol-fast` with `model_api` `gpt-5.6-sol`; per-request rows summing to the session total; without the debug log, `per-session totals only`; `reasoning` rows of kind `summary` with text; `harness_events` hook rows from `hook.start`/`hook.end`; `instruction_file` parts ≥ 1 on a pack-on fixture and 0 on pack-off. Existing Copilot tests green | Agy (bounded; brief under 30 kB; dispatched first, alone, as the Agy floor canary) |
| **R-READ-CC** Claude Code reader facts, Flagged sources spiked | `src/harness_bench/telemetry/claude_code.py` (served settings; thinking `summary` rows; per-request rows by `requestId`; instruction files, system prompt, hooks, skill loads, compaction, each read or `not recorded: <reason>`); `tests/test_reader_claude_code.py` cases; `tests/fixtures/claude/rerun-*` (scrubbed); `tests/mutations/rerun-read-cc.json` | J0 | T2 | 0 | 100 calls · 109k + 100k · 1 · 1.5 h | the spike per Flagged source first (one pack-on X1 turn in an isolated home, `C:\tf\r-read-cc`), with a verdict per source; red first: `effort` `high`, `attachment.identity.modelId` `claude-opus-5-5[1m]`, ACP size 1,000,000, a `summary` row with text, per-request rows deduplicated by `requestId` summing to the ACP output total; each Flagged source either read on the fixture or `not recorded: <reason>`. Existing tests green | Claude Code Agent tool, Opus (judgement: five spikes, five verdicts) |
| **R-READ-GROK** Grok reader | `src/harness_bench/telemetry/grok.py` (served settings; reasoning summary and encrypted rows; prompt parts from `system_prompt.txt`, `tool_definitions.json`, `prompt_context.json`; per-turn usage; tool calls with `TOOL_CLASS` for HB-VAL-008); `tests/test_reader_grok.py` (new); `tests/fixtures/grok/rerun-*` (scrubbed); `tests/mutations/rerun-read-grok.json` | the Grok canary's floor recorded | T1 | 0 | 60 calls · canary + 50k · 1 · 1.0 h | red first on the scrubbed session: `grok-4.7-build` allowed for pin `grok-4.7` by the alias table; `reasoning_effort` `high`; `contextWindowTokens` 256,000; per-request `not recorded: per-turn totals only`; `reasoning` rows (`summary` with text, and `encrypted-only`); `instruction_file` parts from `agents_md_files` ≥ 1 on a trusted pack-on fixture, 0 on pack-off; a `web_fetch` call classed out-of-profile. Handed back: the Grok tool-restriction mechanism (config key, or none), with the evidence | Grok (bounded; brief under 30 kB), or Opus if the canary's floor leaves under 60k |
| **R-READ-AGY** Antigravity reader | `src/harness_bench/telemetry/agy.py` (`init.model`, per-step usage with `thinking_tokens`, tool events; thinking text from `conversations/<id>.db` `steps.step_payload` by a stdlib protobuf wire decoder, failing to `omitted`; prompt parts from `gen_metadata`); `tests/test_reader_agy.py` (new); `tests/fixtures/agy/reader/*` (scrubbed); `tests/mutations/rerun-read-agy.json` | the Agy canary's floor recorded | T1 | 0 | 70 calls · canary + 60k · 1 · 1.2 h | red first on the fixtures: served `gemini-3.8-flash-high`, context `not recorded`; per-step rows; a `text` reasoning row matching the spike's known thinking text; a truncated payload gives `omitted` with the step's `thinking_tokens`, never wrong text; `instruction_file` parts (AGENTS.md as a `RULE`) ≥ 1 on a pack-on fixture and 0 on pack-off | Agy (bounded; brief under 30 kB), or Opus by the canary |
| **R-VALIDITY** served-settings validity, the probe check, the refresh gate, the credential scan | `src/harness_bench/views.py` (`_validity` only: HB-VAL-002 gains `model_served`; HB-VAL-010; HB-VAL-011; the disagreement rule; `default_serves`); `src/harness_bench/report/credentials.py` (also scans the bench credential home's `auth.json`, `:57`); `src/harness_bench/report/publish.py` (`publish`: the egress scan (also exposed as `scan_text`, run on the analyst Markdown before it is committed), fail-closed without `BENCH_OPERATOR_EMAIL`, the email/UUID excerpt filter, the write, and the one `open_in_chrome` call; ADR-0027 §4, §6); `tools/served_check.py` (new: a thin wrapper over the views, plus the real-store and `%APPDATA%`/`%LOCALAPPDATA%` listings, the debug-log bearer scan, and the **Grok refresh gate**: read the bench token's JWT `exp` (never its value), require it expired at the start, then require the bench `auth.json` bytes changed and written back and `grok models` to authenticate in both homes); `tests/test_validity_served.py`, `tests/test_served_check.py` (new); `tests/mutations/rerun-validity.json` | J0 | T2 | 0 | 110 calls · 109k + 110k · 1 · 1.7 h | red first on hand-built `served` rows: a Copilot cell serving 128,000 under `default` is HB-VAL-010; a Codex cell at 828,400 under pin 872,000 with catalog percent 95 is valid; a pinned effort with no source is HB-VAL-011; a `model_calls` model of `gpt-5.6-sol` with `model_served` `gpt-5.6-sol-fast` is valid by the alias, and `grok-4.7-build-fast` for pin `grok-4.7` is HB-VAL-002; agy context `null` is not judged; a Copilot `-p` cell pinned `922000` with served `contextTier` `long_context` is valid and with `null` is HB-VAL-010 (judged by tier, ADR-0028 §5); a Copilot `-p` cell with no usage in its final object gives HB-VAL-005 `not recorded`, never a warning (ADR-0028 §4); two disagreeing sources give HB-VAL-010; an old run with no `served` rows keeps its validity byte-equal. `served_check` exits 1 on each failing clause of ADR-0024 §6 and 0 on a clean fixture; the refresh gate fails on an unexpired token and on unchanged bytes; the credential scan finds a planted bench token in a page; `publish` refuses without `BENCH_OPERATOR_EMAIL`, drops a planted email-shaped excerpt, and under `AF_NO_OPEN=1` prints `not opened: AF_NO_OPEN set` | Claude Code Agent tool, Opus (it gates every cell: gate finding 14) |
| **R-REPORT-R** the cost-compare renderer | `src/harness_bench/report/cost_compare.py` (`render` only, from hand-built `CostCompare` fixtures); `tests/test_cost_compare_render.py` (new); `tests/goldens/cost-compare-render.html` (the renderer's golden); `tests/mutations/rerun-report-r.json` | the Agy canary's floor recorded | T1 | 0 | 80 calls · canary + 70k · 1 · 1.5 h | every ADR-0027 section present from a fixture; kiviat: 12 checkboxes, normalised over all series (the max per axis computed over all 12, asserted; toggling never rescales); axe-core 0 violations light and dark, **run**; 0 matches for `$`, `USD`, `cost_usd`; an excerpt with an email or UUID shape dropped and counted; reasoning excerpts absent unless `--excerpts` (an external page, ADR-0027 §0); every combo row shows its transport, and the Copilot rows say `-p` behind the local adapter (Ruling 120); `not recorded` in every new section for a fixture with absent streams; golden byte-equal on re-render | Agy (bounded render surface with a golden; brief under 30 kB), or Opus by the canary |
| **R-DERIV** the derivations, `build`, and the end-to-end golden | `src/harness_bench/report/tool_phases.py` (the shared classifier, moved from `pack_improvement`, outputs unchanged for its existing categories; phases, bytes, re-reads); `src/harness_bench/report/pack_improvement.py` (calls it; ownership passes from R-DRIFT at J1a); `src/harness_bench/report/context_growth.py`; `src/harness_bench/views.py` (new time-anatomy measures beside `_model_time`, which keeps its meaning; ownership passes from R-VALIDITY at J1b); `src/harness_bench/report/cost_compare.py` (`build`; ownership passes from R-REPORT-R at J1b); `cost_compare.cli_main` (it calls R-VALIDITY's `report/publish.py`); `tests/test_tool_phases.py`, `tests/test_cost_compare_e2e.py` (new); `tests/goldens/cost-compare.html` (the **end-to-end** golden on R-GOLD's frozen root, ADR-0027 §5) and the test that its root reads nothing from the repository's `bench/`; `tests/mutations/rerun-deriv.json` | R-READ-* (five), R-VALIDITY, R-DRIFT, R-REPORT-R joined | T2 | 0 | 150 calls · 109k + 150k · 2 · 2.5 h | red first: phase counts on a fixture tool sequence equal a hand classification under the stated rule; `pack_improvement`'s golden byte-equal after the move; `report.html`'s Model time and Idle columns byte-equal for an existing fixture run; `bench report --cost-compare <fixture b1> <fixture b2> --out x.html` writes a page whose every number traces to a view field (a test walks them); it goes through `publish` (a test asserts the call); `build` fills each combo's `transport` from the plan (asserted: the Copilot rows read `-p` behind the local adapter); the e2e golden byte-equal on re-render | Claude Code Agent tool, Opus |
| **R-COPILOT-P** Copilot `-p` behind a local ACP adapter (ADR-0028) | `bench/adapters/copilot_p_acp.py` (new, stdlib: the ACP subset; one `copilot -p` child per prompt, `--session-id` then `--resume`; `session/cancel` kills the child; stdout JSONL teed to `copilot-p-turn<k>.jsonl`; the stop-reason rule; usage from the final object, if any; children launched with `CREATE_NO_WINDOW`); `bench/profiles/copilot.yaml` (the adapter argv of ADR-0028 §3; the settings block: effort; context `default`→272,000 and `922000`→`--context long_context`, judged by tier; `scripted_user: unsupported`; `--log-level debug --log-dir`); `bench/adapters/copilot_p_acp.pin.json` (its version and sha256, updated with every adapter commit); `tests/test_copilot_p_adapter.py`, `tests/test_profile_copilot_p.py` (new; the adapter driven by the bench's own `driver.py` against a fake `copilot` exe, and one engine-level two-turn cell through the existing fake launcher whose events pass `lifecycle.replay`; the adapter's stdout is UTF-8 with `\n` line ends, asserted, since no text-io gate scans `bench/adapters`); `tests/fixtures/copilot-p/*` (scrubbed); `tests/mutations/rerun-copilot-p.json` | J0 | T2 | 0 | 130 calls · 109k + 130k · 2 · 2.3 h | **the spike first** (ADR-0028 §6, `C:\tf\r-copilot-p`, one X1 turn per question), with a verdict each: tool restriction without `--allow-all-tools`; `--resume` for a second turn; `gpt-5.6-sol-fast` at `long_context`; the longest task prompt against the 32,767-character limit; usage in the final object; the engine job's peak memory includes the child. A "neither holds" verdict on tool restriction is a DR to the operator before the profile freezes. Red first (the adapter is absent): `driver.open_session` + two `send_turn`s against the adapter with a fake `copilot` give two children, `--session-id <uuid>` then `--resume <uuid>` with the same uuid, and **one** engine process, so `lifecycle.replay` conformance holds for a two-turn cell (gate veto A); `session/cancel` kills the child and returns `cancelled`; a non-zero child exit is not `end_turn`; the profile with context `922000` puts `--context long_context` in the child argv | Claude Code Agent tool, Opus (judgement: an adapter under test) |
| **R-PACKCOST** the AI-Forward pack cost analysis (ADR-0029) | `src/harness_bench/report/pack_cost.py` (`build`, `render`, `cli_main`: the pairs, the decomposition terms with their labels, the pack component map from the pack-on minus pack-off base trees and frontmatter, the rule-based tuning candidates with their thresholds as module constants, the outcome header, the `--analysis` embed under its heading); `tests/test_pack_cost.py` (new); `tests/goldens/pack-cost.html` (on R-GOLD's frozen root); `tests/mutations/rerun-packcost.json` | J1b | T2 | 0 | 140 calls · 109k + 140k · 2 · 2.5 h | red first: on a fixture pair with known parts, the terms sum to the fixture's Δ with a planted residual shown, never spread; a pack-on file with `applyTo: "**"` is classed always-applied and a scoped one scoped; the per-file tokens carry the "Inferred (tokens per character)" label; Grok's on-demand term reads `not recorded: per-turn totals only`; a candidate fires exactly at its threshold and not below; the outcome header repeats the lean summary's per-harness effect, interval and MDE; `--analysis` embeds the file under "Analysis (written by an analyst, not generated)", and an analysis citing a number absent from the generated tables is refused with the number listed (ADR-0029 §7); the component map reads the pack source through `gitsafe`, and an unreadable source gives `unclassified` with its reason; every harness row shows its transport (Copilot `-p` disclosure, Ruling 120); the derivations come from `tool_phases`/`context_growth` through the J0 signatures (fakes in its tests; the real-path test at J2); it goes through `publish`; the golden byte-equal on re-render; 0 `$`/`USD` | Claude Code Agent tool, Opus (judgement: an attribution model with labelled steps) |

### Track assignment detail

| track | sessions · branches | why this harness and model | why it earns the multiplier | expected seam requests | deadline · termination · fallback | join batch · gate ring |
| --- | --- | --- | --- | --- | --- | --- |
| R-GOLD | Agent tool, `isolation: worktree` · `build/rerun-gold` | 85 consumers of one fixture builder | **independence**; it lands GOLD-A first | a golden that moves → the Coordinator | 1 h · ends at a green commit · fallback: mask only the plan hash (GOLD-A's original proposal) | J0 · none |
| R-CONTRACT-RUN | Agent tool · `build/rerun-contract-run` | structural run-side edits | **independence**: without it, wave-1 tracks co-author `profiles.py`, `plan.py`, `engine.py`, `cli.py`, `identity.py`, `test_architecture.py` (GO5 b) | none | 1.3 h · ends at a green commit · a second Opus turn | J0 · none |
| R-CONTRACT-FACTS | Agent tool · `build/rerun-contract-facts` | structural grade-side edits | **independence** (as above for `errors.py`, `telemetry/*`, `runner.py`, `views.py`, `config.py`) | none | 1.3 h · ends at a green commit · a second Opus turn | J0 · gate ring at S4b (`grade/runner.py`) |
| R-SETTINGS | Agent tool · `build/rerun-settings` | identity, cell ids, isolation: RECID-A and CRED-COPY-A are the failure modes | **independence** | a profile field → the Coordinator (additive only) | 2 × 1.3 h · each ends at a green commit · a second Opus turn | J1a · none |
| R-CAP | Agent tool · `build/rerun-cap` | a model-checked scheduler | **independence** | none | 1.7 h · ends at the model check green · fallback: the Leader runs the Grok and agy combos in their own batch-internal runs (documented, not preferred) | J1a · none |
| R-TRANSPORT | Agent tool · `build/rerun-transport` | two coupled protocol modules (coupling test) | **independence** at the contract; **context hygiene** | the agy permission map → the Coordinator | 2 × 1.4 h · each ends at a commit · a second Opus turn | J1a · none |
| R-BUILDS | Agent tool · `build/rerun-builds` | the `LAYOUT` pattern exists three times | **context hygiene** | none | 0.8 h · ends at green · the Leader | J1a · none |
| R-DRIFT | Agent tool · `build/rerun-drift` | a catalog change graded on every cell | **independence** | the anchor value → `owner-fable` | 2 × 1.2 h · each ends at a commit · a second Opus turn | J1a · **gate ring at S4b** |
| R-READ-CODEX | runner `rcodex-rerun` · `build/rerun-read-codex` | one reader, one fixture: Grok's measured profile on bounded work | **independence**; it is the Grok floor canary | none | 2,400 s, R-103 kill and one retry · ends at a green commit · Opus sub-agent | J1b · none |
| R-READ-COPILOT | runner `rcopilot-rerun` · `build/rerun-read-copilot` | one reader: a small Agy brief | **independence**; the Agy floor canary | none | 2,400 s · ends at a green commit · Opus sub-agent | J1b · none |
| R-READ-CC | Agent tool · `build/rerun-read-cc` | five spikes and verdicts | **independence**; **isolation** (a live cell in `C:\tf`) | an absent source → `not recorded`, no seam | 1.5 h · ends at a green commit · a second Opus turn | J1b · none |
| R-READ-GROK | runner `rgrok-rerun` · `build/rerun-read-grok` | a Grok worker on Grok's own record | **independence** | the tool-restriction mechanism → handed back; "none" → a DR to the operator, due before S3 | 2,400 s, R-103 kill, one retry · ends at a green commit · Opus sub-agent | J1b · none |
| R-READ-AGY | runner `ragy-rerun` · `build/rerun-read-agy` | bounded reader with a small decoder | **independence** | none | 2,400 s · ends at a green commit · Opus sub-agent | J1b · none |
| R-VALIDITY | Agent tool · `build/rerun-validity` | the cell validity gate and the readiness tool | **independence** at the contract | none | 1.7 h · ends at a green commit · a second Opus turn | J1b · none |
| R-REPORT-R | runner `rrep-rerun` · `build/rerun-report-r` | a bounded render surface: Agy's measured profile (B0) | **independence** at the `CostCompare` contract | a field `CostCompare` lacks → the Coordinator (additive) | 2 × 2,400 s · ends at a green commit with the golden · Opus sub-agent | J1b · none |
| R-DERIV | Agent tool · `build/rerun-deriv` | three report modules and `build`, after their inputs | **context hygiene** on joined code | none expected | 2 × 1.3 h · ends at a green commit with both goldens · a second Opus turn | J2 · none |
| R-COPILOT-P | Agent tool · `build/rerun-copilot-p` | a third transport and a per-turn process model: judgement | **independence** (its module and the Copilot profile are its alone) | tool restriction "neither holds" → a DR to the operator | 2 × 1.3 h · ends at a green commit with the spike verdicts · a second Opus turn | J1a · none |
| R-PACKCOST | Agent tool · `build/rerun-packcost` | an attribution model whose modelled steps must be labelled | **independence** from R-DERIV at the J0 signatures (it calls `tool_phases` and `context_growth` through the signatures R-CONTRACT-FACTS fixes, with injected fakes in its own tests; its real-path test runs at J2) | a fact a term needs that no stream carries → `not recorded`, no seam | 2 × 1.3 h · ends at a green commit with the golden · a second Opus turn | J2 · none |

**Gate ring.** The stamp inputs are `src/harness_bench/grade/**`, `tasks/D1`, `bench/metrics.yaml` and
`bench/regrade-baseline-0.3.yaml` (`tools/gate_stamp.py:4-9`). R-CONTRACT-FACTS (`grade/runner.py`) and R-DRIFT
(`grade/drift.py`, `grade/_changes.py`, `grade/runner.py`, `bench/metrics.yaml`) touch them, and no later track does,
so **the gate ring runs once, at S4b, right after J1a** (77-81 min, `tools/gate_stamp.py:30-32`); S4 re-checks the
digest. **The stamped tier** runs at S4b too, because `errors.py` is a stamped-tier input (`:34`).

**Harness capability, as verified here:**
- **Claude Agent tool:** edit boundary `enforced` (spike S5, `coord doctor`).
- **Grok and Agy through `coord-runner`:** `observed-only` (no edit-boundary spike; the re-read hooks are installed).
  The commit floor enforces.
- **Doorbells:** not recorded for any harness.
- **Codex, Sonnet and Copilot:** not workers (the prompt).

## Serial spine

| item | why it cannot be parallel | who owns it |
| --- | --- | --- |
| S0. Pin epoch 21 (`coord leader pin`, renewed in a loop). Create `integrate/rerun-21`. Re-check "latest" for every cell pin and for Haiku; ask the operator before changing one. Choose and record the pack-on revision (the ai-forward head carrying `ed9625a7`). Time one full suite on `main` (the J-cost below is re-planned from it) | every row carries the epoch; the pack revision is a plan fact; the suite time is the join cost's only unknown | Leader |
| S1. J0: R-GOLD, R-CONTRACT-RUN and R-CONTRACT-FACTS joined as one candidate (one suite, one recount; a red bisects by track), pushed | until every shared file's structure lands, wave-1 results change each other's shape (GO5 b) | Leader |
| S2. **Batched joins.** J1a (R-SETTINGS, R-CAP, R-TRANSPORT, R-COPILOT-P, R-BUILDS, R-DRIFT) and J1b (the five readers, R-VALIDITY, R-REPORT-R): each batch's worker-gated branches are merged into **one candidate** in `integrate/rerun-21`; one full suite on it; the Leader applies the handed-back mutation retargets; then the join recount. A red bisects by track, **one round**; a track that stays red goes to a loop-back fix track on Opus and the rest join. After J1a, the Leader runs the five-harness launch red and the 120-cell plan proof (R-SETTINGS's deferred evidence) | each join's recount is the base of the next (GO5 c); the suite is the shared exclusive resource (SUITE-LOCK). One suite per batch is rule 2's "one full suite on the candidate" (last run's deviation 6, `coordination-lean.md:309-313`, made the plan) | Leader |
| S3. **Development probe**, in parallel with R-DERIV: three cells on X1, pack-on — Codex with `show_raw_agent_reasoning = true`, Copilot with the debug log (the bearer scan), Claude Code (R-READ-CC's sources). It measures the bounds (largest debug-log body, agy line, reasoning row; ADR-0026 §7). Then the profile decisions (ADR-0024 §6) and the Grok tool-restriction answer, as one Leader commit, **before the last join** | a profile change after the formal probe would change `profile_hash` (RECID-A, council N4) | Leader; operator (Grok tool DR, if raised) |
| S4b. Right after J1a: catalog **0.8 freeze** (`bench/catalog-freeze.yaml` entry, X1 export and board goldens), the **gate ring**, the **stamped tier** | no later track touches the stamp inputs, so these leave the critical path; S4 re-checks the digest | Leader; Coordinator (freeze) |
| S4. J2 (R-DERIV and R-PACKCOST, one candidate), then the batch gate: the full suite; `run-verify-gates.py`; `mutate_check --touched <J0 base>`; the gate-ring and stamped digests re-checked (re-run only if changed); ruff; `docs-graph validate`; push | one gated sha is the engine identity of both batches and of the formal probe (ADR-0022 §5) | Leader |
| S5. The **formal R-PROBE** on the gated head: the probe ring (six combos × both arms on one property task, plus RW1 for agy; about 13 cells), the Grok refresh gate (`served_check`, three sequential Grok cells starting on an expired bench token), and `tools/served_check.py` exit 0. No agy worker runs | readiness is judged against the engine that runs; a served setting that differs from its pin is a stop rule | Leader |
| S5b. The **pre-registration** (Haiku draft, Coordinator review): what is compared, the six pins with the **served** settings S5 read back, the arms, the metrics; committed and pushed before batch 1 | the prompt's order: probe, then pre-registration, then approval | Coordinator; Leader push |
| S6. Operator: approve the token budget, asked once. Batch 1: `bench plan --confirm` with `spend_cap_tokens` from the approval, then `bench run`, which grades at its end. No agy worker runs during a batch | batch 2's go depends on batch 1's measured numbers | Leader; operator |
| S7. The checkpoint: minutes per cell for run and grading, tokens per cell per combo and arm, reasoning rows per cell, served settings per combo, each beside its estimate. Batch 2 waits for the operator only if a threshold trips, or if Grok's or Agy's measured tokens per cell exceed 0.8M | the prompt's checkpoint rule | Leader; operator on a trip |
| S8. Batch 2 from the same matrix at the same sha; its commit and `identity_hash` compared with batch 1's; unequal is a stop | one tree, unedited between batches | Leader |
| S9. `bench verify` on both batches (including the four new streams); one audit entry per batch naming the `reasoning` stream, its row count and sealed head (Ruling 117 item 3); the run report (md + html, ending with `render-markdown.py ... --open`), with an Opus analysis seat; then **the two reports for two audiences (Ruling 121)**: `bench report --cost-compare <b1> <b2> --out docs/coordination/harness-cost-comparison.html --open` (for the Copilot team); an Opus analysis seat writes `docs/coordination/ai-forward-pack-tuning.md` from the generated pack-cost tables (every cited number names its table), then `bench report --pack-cost <b1> <b2> --analysis docs/coordination/ai-forward-pack-tuning.md --out docs/coordination/ai-forward-pack-cost.html --open` (for the pack owner). Both need `BENCH_OPERATOR_EMAIL`. Commit and push the run report and both pages | it reads both batches | Leader; Opus sub-agents (run-report analysis; pack-tuning analysis) |

**Critical path (Inferred; durations from the 2026-10-10 analogues, re-planned after S0's suite timing):**

| step | duration (Inferred) | notes |
| --- | --- | --- |
| operator: two `grok login`s | operator | the real home before Grok workers (J1b); the bench home now, so its token can expire before S5 |
| S0 | 0.5 h | includes one timed full suite |
| R-GOLD ∥ R-CONTRACT-RUN ∥ R-CONTRACT-FACTS | 1.3 h | parallel; independent files |
| J0 | 0.6 h | one candidate, one suite (about 25 min, Inferred), recount |
| wave 1a (with the two canaries) | 2.7 h | R-TRANSPORT and R-SETTINGS are the long poles |
| J1a | 0.8 h | one candidate; one bisect round in reserve |
| S4b ∥ wave 1b's tail | (2.0 h, off the path) | gate ring 77-81 min, stamped tier, freeze |
| J1b | 0.8 h | one candidate |
| R-DERIV ∥ R-PACKCOST ∥ S3 | 2.5 h | the development probe and its profile commit fit inside wave 2 |
| J2 + S4 | 1.3 h | the suite, `--touched` mutation, gates; the ring only if its digest moved |
| S5 + S5b | 1.0 h | about 13 cells, Grok and agy one at a time; the pre-registration |
| S6 operator approval, then batch 1 | operator, then 2.5 h | Grok and agy each serial: 20 cells × about 3-4 min (Inferred, never timed in a cell) bound the batch |
| S7 checkpoint | 0.3 h | |
| S8 batch 2 | 2.5 h | |
| S9 verify, the run report, the two pages | 1.8 h | two Opus analysis seats in parallel |
| **total** | **about 18-19 h** | the run itself (S5-S8) about 6 h of machine time; within the prompt's 5-6 h target only if Grok and agy cells average under about 3 min |

## Seams

| from -> to | the request | resolved by |
| --- | --- | --- |
| any wave-1 track -> Coordinator | a contract field or a profile field is missing | the Coordinator rules; the owning track adds it **additively**; no mid-wave edit by another track |
| any track -> Leader | an existing mutation file's finds moved | handed back as text; the Leader applies it on the candidate before the recount (MUT-E checks) |
| R-READ-GROK -> operator (via `owner-fable`) | Grok cannot prevent forbidden tools (detection only) | DR answered **before S3's profile commit** (ADR-0025 §5; RECID-A) |
| R-READ-CC -> Coordinator | a Flagged source is absent | recorded `not recorded: <reason>`; ADR-0024 §6's fallback applies |
| R-DRIFT -> `owner-fable` | `scope_creep`'s anchor under the new definition | the Owner rules a value, or it stays Flagged for the freeze |
| R-TRANSPORT -> Coordinator | the agy permission map does not cover a class | the Coordinator rules; ADR-0004 is not changed |
| R-REPORT-R -> R-DERIV | a section needs a field `CostCompare` lacks | the Coordinator rules; R-REPORT-R adds it additively; R-DERIV fills it |
| R-DERIV <- R-DRIFT, R-VALIDITY, R-REPORT-R | ownership of `pack_improvement.py`, `views.py`, `cost_compare.py` | passes at J1a / J1b, sequentially |
| R-SETTINGS, R-DRIFT <- R-CONTRACT-RUN, R-CONTRACT-FACTS | ownership of `plan.py`, `profiles.py`, `runner.py` | passes at J0, sequentially |
| any track -> Coordinator | a new defect class | handed back as text; the Coordinator writes the register |
| any track -> `owner-fable` | a product or scope question | `coord decide request --to owner-fable`; ruled into `docs/notes/rulings.md`. A relayed decision is answered before its default fires, or its timeout is extended past the operator's expected latency (last run's D1) |

**Shared guards, shown jointly satisfiable (GO14a):**
- **`tests/test_architecture.py`** — root `src/harness_bench/**/*.py`, recursive (`:20`).
  - ACP method strings only in `driver.py` (`ACP_METHODS`, `:23`; `ACP_SERVERS`, `:140`).
  - The agy-stream rule (R-CONTRACT-RUN): the input event and the outcome grammar only in `stream_driver.py`;
    `telemetry/agy.py` may read event bodies (`init`, `step_update`, tool events) for its facts. So the driver and
    the reader are jointly satisfiable (gate finding 10).
  - `subprocess` calls only in `SUBPROCESS_CALLERS` (`procs.py`, `grade/bench_check.py`, `:24`), plus the one named
    `report/publish.py` call to `open_in_chrome`; the run path never imports grade or report (`:44`).
  - Owner of every rule change: R-CONTRACT-RUN at J0. No wave track edits the file.
- **`test_identity.py`** (every `src/harness_bench` file classed, `:103-108`): R-CONTRACT-RUN adds every new file's
  class at J0. No wave track adds a `src/` file.
- **The console-window guard** (`tests/test_console_windows.py`): root `tools/` and `tests/` (`:14`), recursive;
  tokens `subprocess.run|Popen|call|check_call|check_output` without `creationflags` (`:16`), plus `os.system`;
  allowlist `ALLOWLIST` (`:37`) with `OWNER_FILES`/`OWNER_TRACKS` (`:19-36`). R-TRANSPORT's `replay.py` launch,
  R-VALIDITY's `served_check.py` and R-READ-CC's spike script pass
  `creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)` and need no allowlist entry.
- **The portable-text-io gate** (`verify-portable-text-io.py`): root `tools` (`:52`); `tools/served_check.py`
  carries the stdio guard and `newline="\n"`.
- **`test_arms_guard.py`:** no track adds an `"on"`/`"off"`/`"pack"` literal.
- **MUT-E** (`test_mutate_check.py:413`): existing mutation files have one writer, the Leader; each track's new
  mutants are in its own `tests/mutations/rerun-<track>.json`.
- **Goldens:** R-GOLD makes the default fixture root frozen and self-contained first, with a live mode only for its
  named consumers. R-DRIFT may re-capture the pack-improvement golden (stated reason). R-REPORT-R owns
  `cost-compare-render.html`; R-DERIV owns `cost-compare.html` on the frozen root. Because the non-lean golden's
  root is frozen at catalog 0.7, the 0.8 freeze does **not** move it (gate finding 5); the freeze's own goldens are
  its X1 export and board goldens.
- **Spike fixtures:** each reader track scrubs its own fixtures; the Leader's join greps every added fixture for
  email, UUID-account, `Authorization`, `Bearer ` and `eyJ…` shapes and refuses a hit. Agy fixtures are split:
  `tests/fixtures/agy/stream/` (R-TRANSPORT) and `tests/fixtures/agy/reader/` (R-READ-AGY).

## Stop rules

From the prompt, plus the plan's own:
- the health check trips twice → stop and report;
- the host becomes unstable (LOAD-A, JOB-A shapes) → record the evidence first, then stop;
- `main` cannot be made green within one bisect round → stop;
- a probe (S3 or S5) shows a served setting that differs from its pin → stop;
- an operator-only blocker gates every remaining track → stop and report;
- a torn row or a classifier denial → that action stops and goes to the operator (never edit a log);
- two consecutive authentication failures for one harness in a batch → the batch stops (ADR-0025 §7).

## Struck tracks

| track | why it was not worth its multiplier |
| --- | --- |
| a separate `R-SERVED` reader track | merged into the five reader tracks: served settings come from the same record parse |
| a separate `R-DRIVER` (ACP additions) track | merged into R-TRANSPORT: two protocol modules sharing signatures and tests |
| a separate `R-GROK` profile track | the two new profiles go to R-TRANSPORT (with their launch tests), the credential write-back to R-SETTINGS |
| `R-ISOLATION` (`DROP_PREFIXES`, `seed_home` parents) | folded into R-SETTINGS, which owns `profiles.py` in wave 1 |
| `R-PREP` (rings and pre-registration) | rings go to R-SETTINGS; the pre-registration is S5b |
| `anatomy.py` | struck at the architecture gate (finding 11) |
| a Copilot SDK-backed ACP adapter (option B) | Ruling 120 chose `-p` mode: less build work, no pin bump |

## Order of operations

| # | action | cost | why now |
| --- | --- | --- | --- |
| 1 | **Operator:** `grok login` in the real home, and `grok login` into the bench credential home (`HB_GROK_CRED_HOME`); set `BENCH_OPERATOR_EMAIL` in the Leader's environment | operator | the real home before Grok workers; the bench token must expire before S5's refresh gate; S9 fails closed without the email |
| 2 | S0 (with one timed suite) | 0.5 h | every row carries the epoch |
| 3 | R-GOLD ∥ R-CONTRACT-RUN ∥ R-CONTRACT-FACTS (Opus ×3); in parallel, Coordinator #1 (Opus) writes the register entries DRIFT-MACHINE-A, RADIUS-TEST-A, LEAK-HOME-A and compiles the wave-1a briefs (compiled mode, replayed through the runner's check; TEST-E: each proof command run once by its author) | 1.3 h | wave 1 needs one owner per file |
| 4 | J0 (one candidate); push | 0.6 h | the wave-1 base |
| 5 | Wave 1a at the cap of 6: R-SETTINGS, R-CAP, R-TRANSPORT, R-COPILOT-P, R-DRIFT (Opus ×5), R-BUILDS (Haiku). The two canaries take the first free slots: R-READ-CODEX (Grok; the real-home login landed 2026-10-12 07:02) and R-READ-COPILOT (Agy). The health check at every dispatch | 2.7 h | the long poles first; the canaries measure the floors |
| 6 | Wave 1b as slots free (cap 6; Grok ≤ 2, Agy ≤ 2): R-READ-CC, R-VALIDITY (Opus), R-READ-GROK (Grok or Opus), R-READ-AGY and R-REPORT-R (Agy or Opus), each routed by the canaries' floors | overlaps 5 | |
| 7 | J1a (one candidate; the five-harness red and the 120-cell plan proof); push; then S4b (freeze, gate ring, stamped tier) | 0.8 h + 2.0 h off the path | |
| 8 | J1b (one candidate); push | 0.8 h | |
| 9 | R-DERIV ∥ R-PACKCOST ∥ S3 (development probe; the profile commit, including the Grok tool answer) | 2.5 h | before the last join |
| 10 | J2; S4, the batch gate; push | 1.3 h | one gated sha |
| 11 | S5: formal probe, refresh gate, `served_check`; S5b: the pre-registration, pushed | 1.0 h | a served-setting mismatch stops here |
| 12 | **Operator:** approve the token budget, asked once | operator | before any batch cell |
| 13 | S6 batch 1 → S7 checkpoint → S8 batch 2 | about 5.5 h | the run |
| 14 | S9: verify, audit entries, the run report, the harness cost comparison (Copilot team), the AI-Forward pack cost analysis (pack owner); push | 1.8 h | the answer, for both audiences |
| 15 | Close: `coord worktree cleanup` (report, then `--remove` on the operator's go); the closing audit entries; the scratch roots listed for deletion (`C:\tf\spike-settings`, `C:\tf\spike-grok`, `C:\tf\spike-agy`, `C:\tf\grok-1.0.41`, `C:\tf\agy-1.3.2`, `C:\tf\agy-1.3.3` once `.tools` holds the pinned copy, and each `C:\tf\<track>`) | 0.3 h | WT cleanup |

**Operator actions and their timing:**
- **Copilot at 1M:** ruled (Ruling 120, `-p` mode).
- **`grok login`, real home:** done (2026-10-12 07:02; `grok models` reads "You are logged in with grok.com").
- **`grok login` into the bench credential home and `BENCH_OPERATOR_EMAIL`:** step 1, now, so the bench token can
  expire before S5's refresh gate. The path is fixed here: `HB_GROK_CRED_HOME=C:\Users\malla\.harness-bench\grok-cred`
  (a `GROK_HOME`, seeded with `config.toml` `[cli] auto_update = false` before the login).
- **Copilot tool restriction in `-p` mode:** only if R-COPILOT-P's spike says neither form holds; before the profile
  freezes.
- **Grok tool prevention:** only if R-READ-GROK hands back "detection only"; answered before step 9's profile commit.
- **Token budget:** step 12. **Inferred:** about 160M–270M tokens for 240 cells (last run's per-cell means × 40
  cells per combo; Copilot Sol Fast assumed equal to Copilot Sol; × 1.0–1.5 for high effort; Grok and agy bracketed
  at 0.2M–0.8M per cell), plus the probes (about 16 cells, about 10M, Inferred). Copilot at long_context never
  compacts below 922k, so its pack-on cells may cost more than last run's 2.25M (Inferred upward risk; the checkpoint
  measures it). `spend_cap_tokens` per batch is
  set from the approval.
- **A newer Opus, Sol, Grok, Gemini or Haiku id** at step 2, if one is served.
- **Worktree removal** at step 15.

## Status

| | |
| --- | --- |
| **Completed** | the plan: 18 tracks (3 before wave 1, 13 in wave 1 in two halves, 2 in wave 2), the serial spine S0-S9 with batched joins, the seams and their guards, the stop rules, 7 struck or merged tracks; the adversary gate and its revision; Rulings 120 and 121 folded in |
| **Remaining** | `/execute-with-coordination` steps 1-15 |
| **Best next action** | S0, then R-GOLD ∥ R-CONTRACT-RUN ∥ R-CONTRACT-FACTS |

## Gate record

*Adversary gate, 2026-10-12: one Opus sub-agent with the Simplifier, Test Architect and Tech Lead lenses, reading the
code at `af3da009`. The author did not clear any veto alone.*

| # | lens | finding | resolution |
| --- | --- | --- | --- |
| 1 | Test Architect | **VETO.** R-SETTINGS's evidence needed R-TRANSPORT's profiles, and R-TRANSPORT's argv needed R-SETTINGS's placeholders (a cycle). | Placeholder expansion and the plan-cell keys moved to R-CONTRACT-RUN (J0); the five-harness red and the plan proof are Leader evidence at J1a |
| 2 | Test Architect | **VETO.** ADR clauses with no owner: auth-failure stop and resume write-back; the credential scan; the refresh gate; the disk projection; `bench verify` over the new streams. | R-CAP (engine stop, resume); R-VALIDITY (`credentials.py`, refresh gate in `served_check`); R-SETTINGS (`preflight.py`); R-CONTRACT-FACTS (the tamper test); bounds measured at S3 |
| 3 | Test Architect | **VETO.** `grok.yaml`/`agy.yaml` and several driver clauses had no exit evidence. | R-TRANSPORT's profile launch tests and driver cases (row above) |
| 4 | Test Architect | Reader evidence missed instruction files, reasoning and hook rows; R-VALIDITY missed HB-VAL-011 and the alias case. | Added per row |
| 5 | Test Architect | R-GOLD could empty live-catalog controls; S4's golden re-capture contradicted a frozen root. | A live mode for named consumers; the root frozen after J0; S4 corrected |
| 6 | Test Architect | No test that `all_tasks` reaches the lean tasks. | R-DRIFT's lean-task fixture |
| 7 | Test Architect | Bearer shapes in a committed debug-log fixture. | Scrub before commit; the join refuses the shapes |
| 8 | Test Architect | No golden for `build`. | R-DERIV owns the end-to-end golden on the frozen root |
| 9 | Simplifier | Concurrent tracks co-authored many mutation files. | Existing mutation files have one writer (the Leader); per-track new files; retargets handed back |
| 10 | GO14a | The agy rule clashed with the agy reader. | The rule scoped to the input and outcome grammar; the reader may read bodies |
| 11 | one owner | One fixture glob for two tracks. | `agy/stream/` and `agy/reader/` |
| 12 | dependencies | Hidden edges to R-SETTINGS. | Covered by 1 |
| 13 | Simplifier | The contract was too big for one dispatch; R-GOLD→contract was incidental. | Split into R-CONTRACT-RUN and R-CONTRACT-FACTS; behaviour moved to R-SETTINGS; all three run in parallel |
| 14 | Simplifier / Tech Lead | Six external tracks at unmeasured floors; R-VALIDITY gates every cell. | A floor canary per external harness first; routing by its number; R-VALIDITY on Opus |
| 15 | Tech Lead | J1's cost (24 suites under SUITE-LOCK) was not credible. | Batched candidates (two suites for wave 1), one bisect round; S0 times the suite |
| 16 | Tech Lead | The bench login at step 12 put a token lifetime on the path. | Both logins at step 1 |
| 17 | Tech Lead | The Grok tool answer after the gated sha would change a profile hash. | Due before S3's profile commit |
| 18 | Tech Lead | Incidental ordering. | S3 ∥ R-DERIV; the freeze and gate ring right after J1a; R-DERIV's edges narrowed |
| 19 | Rules | Stop rules, health check at joins, rule 4, LOAD-A. | The *Stop rules* section; the health check at joins; SUITE-LOCK in *Layer state* |
| 20 | Rules | Order of probe and pre-registration; the email; the primary; the html; citations; terminations; a test file. | S5b after S5; step 1; no primary fast-forward; the html view; `:19-36`; terminations in the detail table; `tests/test_engine.py` named |

**Round 2 (re-check of the revision, with Rulings 120 and 121 folded in):** vetoes 2 and 3 cleared; veto 1 cleared
for four harnesses and reopened for Copilot; two new Test Architect vetoes.

| # | lens | finding | resolution |
| --- | --- | --- | --- |
| A | Test Architect | **VETO.** One process per turn (ADR-0028's first draft) breaks `lifecycle.py:69-74`'s conformance, `views.py:559`'s event keying and the TLA model, and no track owned them. | ADR-0028 revised: `copilot -p` runs behind a pinned local ACP adapter (`bench/adapters/copilot_p_acp.py`); the engine keeps one process per attempt; R-COPILOT-P's red asserts `lifecycle.replay` conformance for a two-turn cell |
| B | Test Architect | **VETO.** The `-p` disclosure in both reports had no owner. | R-REPORT-R and R-PACKCOST each assert a transport column beside every combo; `transport` is a field of both contracts (R-CONTRACT-FACTS) |
| 1′ | Test Architect | Copilot's `{context_arg}` value map, `{python}`, and the scripted-user refusal had no contract owner. | `{python}`, `{context_arg}` and the `scripted_user` flag in R-CONTRACT-RUN; the refusal code in R-CONTRACT-FACTS; the plan refusal in R-SETTINGS |
| 4′ | Test Architect | Copilot's context evidence used ACP-era fixtures; no tier case; no HB-VAL-005 `not recorded` case. | R-READ-COPILOT reads a `-p` record; R-VALIDITY's tier and HB-VAL-005 cases |
| 10′ | GO14a | The subprocess bullet named `cli.py`. | Named `report/publish.py` |
| 16′ | Tech Lead | The bench credential path was deferred. | Fixed: `C:\Users\malla\.harness-bench\grok-cred` |
| 20′ | Rules | No html view; frontmatter missing ADR-0028/0029. | Rendered at commit; links added |
| — | D&P | R-PACKCOST would redefine R-DERIV's derivations. | R-PACKCOST calls `tool_phases`/`context_growth` through J0 signatures, with fakes; real path at J2 |
| — | Security | The analyst Markdown is committed outside `publish`; the external page carried reasoning excerpts. | `publish.scan_text` on the Markdown before commit; the Copilot-team page's excerpts off by default (`--excerpts`) |
| — | Coverage | The analyst's numbers checked by a read; the pack file list's source. | A mechanical number check (refuse on an unmatched number); the pack source read through `gitsafe`, `unclassified` if unreadable |

**Rounds 3 and 4:** vetoes A and B cleared (round 3); 1′ and three adapter-design findings (the pin cycle: the pin
moves to a data file R-COPILOT-P owns, read by R-BUILDS on Opus; no guard over `bench/adapters`: the console-window
roots and ruff extended, a stdout encoding test; the interpreter's identity in the build record) resolved and
**passed** (round 4). Two minor budget and test fixes applied after round 4.

**Verdicts:** Simplifier pass-with-changes (applied). Test Architect: every veto cleared by the reviewer. Tech Lead:
18 tracks, batched joins, about 18-19 h (Inferred).

## Errata (Coordinator #2, 2026-10-12)

*Written by Coordinator #2 (session `c2-rerun`, Opus) at `8cda3fc3`. The rows above are not rewritten: each erratum
names the row or line it corrects, and where they disagree, the erratum wins. Sources: the Leader's addenda to the
wave-1 briefs (`C:/tf/rerun-leader/briefs/leader-addenda.md`, epoch 21; binding boundary rulings), the J0 commits,
and the Leader's J0 facts. Anchors marked Verified were read by me at `8cda3fc3`; the others are the Leader's.*

| # | corrects | erratum | source |
| --- | --- | --- | --- |
| E1 | R-SETTINGS row (Tracks, `preflight.py` and its exit evidence "the disk projection counts a debug log") | **Struck.** There is no HB-PRE-003 disk projection: `preflight.py:45-47` is a fixed 20 GB floor and `:4-5` names a projection as a later phase (Verified). No track builds a projection. The Leader measures the Copilot debug-log size at the S3 development probe against that floor | addenda, R-SETTINGS |
| E2 | R-CONTRACT-RUN row ("`HARNESSES` gains `grok`, `agy`") | **Not at J0** (Leader ruling at J0): `HARNESSES` stayed three (`0b4bdf5b`). That commit's message says the entries "join with R-SETTINGS"; the later addendum (E3) gives them to R-TRANSPORT, and E3 is the ruling in force | J0 ruling; `0b4bdf5b`; addenda |
| E3 | R-SETTINGS row (`profiles.py`) and R-TRANSPORT row (owns) | In `src/harness_bench/profiles.py`, the `HARNESSES` tuple entries, the `READERS` entries and any `DELEGATE_IDS` entries for `grok` and `agy` move to **R-TRANSPORT** (pointing at the J0 stubs `telemetry/grok.py`, `telemetry/agy.py`), because the engine identity loads a profile for every `HARNESSES` entry (`identity.py:219-220`) and R-TRANSPORT creates the two YAMLs. Every other `profiles.py` line stays R-SETTINGS's. Tests that need a grok or agy profile before J1a use test-local fixture YAMLs | addenda, R-SETTINGS and R-TRANSPORT |
| E4 | R-CAP row ("two consecutive ones for one harness stop the batch" and its exit evidence); *Stop rules*, last bullet | **Replaced** by the existing mechanism: `blocked_auth` (HB-CELL-202) already opens a per-harness decision and pauses that harness's launches while it is open (`engine.py:65`, Verified; `:332-341`, `:482`; PE-4). No new stop path. R-CAP's exit evidence becomes: a Grok cell's authentication failure yields HB-CELL-202 and pauses Grok launches only, while other harnesses keep launching. The `resume.py` write-back stays in scope. The stop-rule bullet reads: an authentication failure pauses that harness's launches (HB-CELL-202) until the decision is answered. ADR-0025 §7 carries the same erratum | addenda, R-CAP |
| E5 | R-CAP row (`INSTRUCTION_FILES`/`INSTRUCTION_DIRS` gain `GEMINI.md`, `.agents/rules`, `.agents/skills`, `.grok/`) | `GEMINI.md` is already in `INSTRUCTION_FILES` (`workspace.py:27`, Verified). The directory rule matches only `*.instructions.md` (`_instruction_paths`, `workspace.py:146-151`, Verified), so adding `.agents/rules` to the list would not catch `.agents/rules/x.md`. Corrected: **every file** under `.agents/rules/`, `.agents/skills/` and `.grok/` in an upstream tree is removed, then refused if present (HB-PRE-009). Red: an upstream `.agents/rules/x.md` | addenda, R-CAP |
| E6 | R-BUILDS row (owns, exit evidence) | `tools.resolve` resolves **only the harnesses a plan uses** (today it needs every `LAYOUT` entry, `tools.py:141-143`, and `preflight.py:52` calls it for every run). Red: a plan with only claude-code resolves with no grok or agy build present. The interpreter identity changes every build record, so `check_build` (exact equality, `tools.py:154-155`) refuses a resume of a plan made before the change (HB-CELL-115). Accepted: no such plan is pending; R-BUILDS states it in its report | addenda, R-BUILDS |
| E7 | *Order of operations* step 5 ("R-DRIFT (Opus ×5), R-BUILDS (Haiku)") | R-BUILDS runs on **Opus, not Haiku**, as its own row's harness column says (gate round 3). Step 5 reads "Opus ×6" | addenda; R-BUILDS row |
| E8 | R-COPILOT-P row (exit evidence) | After its spike, R-COPILOT-P also produces **raw records for R-READ-COPILOT**: one X1 pack-off and one X1 pack-on turn through its adapter with `--log-level debug`, in `C:\tf\r-copilot-p\records\` (never committed by R-COPILOT-P; R-READ-COPILOT scrubs and commits fixtures). It reports whether the debug log holds the full request bodies (system prompt and instruction text). ADR-0026 §1's "Verified: full request bodies" for Copilot prompt parts is **Flagged** until that report shows it | addenda, R-COPILOT-P |
| E9 | *Tracks* routing paragraph ("the first Agy track (R-READ-COPILOT)"); R-READ-COPILOT row ("Agy floor canary", "dispatched first, alone"); its detail row ("the Agy floor canary"); R-READ-AGY row (depends on "the Agy canary's floor recorded"); *Order of operations* steps 5 and 6 | **Canary swap.** The Agy floor canary is **R-READ-AGY** (its fixtures exist in `C:\tf\spike-agy`): it depends on J0 and is dispatched first, alone, in wave 1a. **R-READ-COPILOT moves to wave 1b**, after R-COPILOT-P's raw records (E8) exist, and is routed by the Agy canary's floor like the other later Agy rows | addenda, Canaries |
| E10 | R-DRIFT row (owns) | R-DRIFT also owns the one-line fix in `tests/test_grade_runner.py`: the test compares the default fixture root's catalog (now frozen at 0.7, R-GOLD) with the **live** catalog, so the `0.8.dev` bump would redden it. Compare against `archived_runs.FROZEN_ROOT / "bench" / "metrics.yaml"` instead. Anchor: the addendum cites `:273`, the assertion; the live read it feeds is `:272` (`ROOT / "bench" / "metrics.yaml"`), Verified | addenda, R-DRIFT (R-GOLD's finding) |
| E11 | *Common exit evidence* (the suite results of every Agent-tool track) | **Environment note (HB-GRD-006).** In an Agent-tool worktree under `C:\Projects\x-harness-x-model-bench\.claude\worktrees\`, nine tests fail with HB-GRD-006 ("pyproject.toml is above the grading root …\.claude\worktrees\bench-cells\grading"): the CLI's default `--cells-root` is `root.parent / "bench-cells"` (`cli.py:740` at `2f633d54`, `:762` at `8cda3fc3`, Verified), which lands inside the primary checkout. Five in `test_cli.py`, two in `test_grade_judge.py`, two in `test_injection_and_publication.py`; they fail on the base too. Environmental: workers name them if they ran them and do not "fix" them. The Leader's suite runs in a sibling tree, where they pass. Registered as a class (`docs/lessons/defect-classes.md`, Coordinator #2 entries) | addenda, Everyone |
| E12 | R-CONTRACT-FACTS row (owns, exit evidence) | **J0 rulings on its DR1 and DR2** (landed in `f1a65146`): DR1, `harness_events` rows gain **`native_ordinal`** (the event's position in its record), and `views.KEYS` for the stream is `(run_id, extraction_id, cell_id, native_session_id, native_ordinal)`, so identical events never collide. DR2, the `served` hook accepts **a tuple of `ServedSettings`**, one per source; `served_rows` writes them all (a single `ServedSettings` is still accepted), and an identical row (a field no source read) is written once. ADR-0026 §1 carries the same erratum | J0 rulings; `f1a65146` |
| E13 | *Critical path* J0 row ("one suite (about 25 min, Inferred)"); S0 | **Measured at S0:** one full suite on `main` took **16 min**, 4,378 tests green (Leader-reported). The J-cost rows are re-planned from 16 min | Leader, S0 |
| E14 | S1 (J0: "one suite, one recount") | **J0 recount:** one deterministic red. The frozen-root listing test (`tests/test_fixture_root_isolation.py:49-50`, which lists every file under the frozen root with `rglob("*")`) counted a pytest `__pycache__` that the test run itself writes (collecting `tests/fixtures/bench-root/conftest.py` writes `__pycache__/conftest.cpython-*.pyc` into the frozen root). Fixed by an R-GOLD loop-back, `2d11d554` (red first, quoted in its message), joined in `b06d391e` ("join J0 (retry after the R-GOLD loop-back)") on `integrate/rerun-21`, Verified. The Leader applied the J0 mutation retargets in `8cda3fc3` (copilot, engine and scenario6 finds moved by R-CONTRACT-RUN; two `judge.json` finds moved by R-CONTRACT-FACTS, which its hand-back had not reported; caught by MUT-E). Both registered (Coordinator #2 entries) | Leader, J0; `8cda3fc3` |
| E15 | *Order of operations* step 5; S2 ("each join's recount is the base of the next") | **Wave 1a was dispatched from the candidate head `8cda3fc3`**, not from the joined head on `integrate/rerun-21` (the Leader's choice, recorded). The first join commit `1333370f` has the same tree as `8cda3fc3`; the joined head `b06d391e` adds only the R-GOLD loop-back (`tests/test_fixture_root_isolation.py`) and audit rows (`git diff --stat 8cda3fc3 b06d391e`, Verified). So a wave-1a tree lacks the loop-back: `test_the_frozen_root_holds_exactly_the_contracted_inputs` can be red there after any pytest run collects the fixture root's `conftest.py`. That red is the E14 byproduct, not the track's; each wave-1a join candidate carries the fix from `integrate/rerun-21` | Leader; Coordinator #2 |

## Errata (Coordinator #3, 2026-10-12)

*Written by Coordinator #3 (session `c3-rerun`, Opus) on `coord/rerun-c3`, based on the combined candidate
`d7de17d1`. The rows above are not rewritten: each erratum names the row or line it corrects, and where they
disagree, the erratum wins. Sources: the Leader's owed-docs list (`C:/tf/rerun-leader/owed-docs.md`, items 1-8),
the runner records in `C:/tf/rerun-leader/`, and the commits named. Anchors marked Verified were read by me; the
others are the Leader's. The owed list's clock times are labelled `Z` but are local (PDT, UTC-7): the Grok canary's
record is stamped 15:51 UTC (`"at": 1791820292`), which the list gives as "08:57Z" (Verified by converting the epoch).*

| # | corrects | erratum | source |
| --- | --- | --- | --- |
| E16 | ADR-0027 §4 ("`--open` calls `open_in_chrome` … **from `cli.py` only**") | The one call site is **`report/publish.py`** (`publish`, `:81`), which `--cost-compare` and `--pack-cost` reach through their `cli_main`. `cli.py` does not call it (grep, Verified at `d7de17d1`). The rows above already say `publish.py` (R-CONTRACT-RUN, R-VALIDITY, *Seams* `:241`); only the ADR was wrong. Control: `tests/test_architecture.py::test_open_in_chrome_is_called_only_from_report_publish_once` (`OPEN_IN_CHROME_SITE`, `:189`). ADR-0027 §4 carries the same erratum | owed-docs 3 |
| E17 | *Tracks* harness column of R-READ-CODEX, R-READ-GROK (Grok) and R-READ-AGY, R-READ-COPILOT, R-REPORT-R (Agy); *Order of operations* steps 5 and 6 | **Every runner row ran on the Opus fallback** (Claude Code Agent tool; branches `build/rerun-read-codex-opus`, `-read-grok-opus`, `-read-agy-opus`, `-read-copilot-opus`, `-report-r-opus`), because `coord-runner` refused both canaries before the first prompt. **Grok** (R-READ-CODEX, run `r-rcodex-rerun`): `protocol_error` at phase `session/set_model`, 3.719 s, `prompts_started` 0; the refused message the record names is the skills-reload acknowledgement `{"id": "skills-reload", … {"reloaded": 1}}` (`rcodex-run.log`, Verified). The Leader's probe (`grok_setmodel_probe.py`) shows Grok 1.0.41 answers `set_model` correctly and also emits `session/update` and `_x.ai/*` notifications in that phase. **Agy** (R-READ-AGY, run `r-ragy-rerun`): `callback_failed`, one attempt, 2.11 s, `prompts_started` 0, `protocol_error_message` null, 0 stdout and 0 stderr bytes (`ragy-run.log`, Verified). The owed list's "x6" is the code's six occurrences across the record's six lines, not six attempts. Both are pack-managed (`coord_transport.py`); the fix is upstream, through `/updatepack`. Registered: XPORT-A and RUNMSG-A (Coordinator #3 entries) | owed-docs 1, 4 |
| E18 | *Order of operations* steps 7, 8 and 10; *Serial spine* (J1a, J1b and J2 as separate joins) | **J1a and J2 joined as one combined candidate**, `d7de17d1` (`cand/j1a: merge …`, with R-DERIV and R-PACKCOST merged into it), the Leader's choice: one suite saved. The S4b freeze below is on that candidate | Leader; `git log 1fcb2476..d7de17d1`, Verified |
| E19 | S0; the pack-on arm | The pack-on arm is **`C:/Projects/ai-forward@ed9625a78690aeba04d0b6693ad296ba5e6a0cd9`** (pack revision 99), fixed at S0. It contains last run's `e1f8ad5e` (`git -C C:/Projects/ai-forward merge-base --is-ancestor e1f8ad5e ed9625a7…`, exit 0, Verified) | Leader, S0 |
| E20 | *Order of operations* step 7 ("the 120-cell plan proof") | **Ran clean at `d7de17d1`:** `bench plan --matrix bench/rings/lean-rerun.yaml` (plan `run-20261012T184125`, not confirmed) gives six combos x 20 cells = 120 (cc-opus-1m, codex-sol, copilot-sol, copilot-sol-fast, grok-4.7, agy-gemini), arm off no pack, arm on pack revision 99 (`ed9625a78690`), parallelism 3 (the Leader's output, `C:/tf/rerun-leader/plan-dry.txt`, read by me) | Leader |
| E21 | R-READ-AGY and R-TRANSPORT rows; R-DRIFT row; *Seams* (R-TRANSPORT seams 4, 6, 7, 8) | **Leader rulings at J1a.** The Agy tool restriction is **detection-only**: HB-VAL-008 through `telemetry/agy.py` `TOOL_CLASS`, because agy 1.3.3's grant kinds cannot deny web, image, browser or subagent tools; the operator is told. R-TRANSPORT seam 7 accepted (agy argv without `--add-dir` and `--print-timeout`, measured). Seams 4 (the Grok credential name is `.grok/auth.json`; the archive basename exclusion verified), 6 (the streak becomes a new agent-attributed HB-CELL code) and 8 (`model_map` vendors validated per plan, not per repo) go to the J1a fix track. R-DRIFT DRs: `scope_creep`'s anchor `[1504, 0]` stays **Flagged**; Codex attention drift comes from shell-read extraction (R-READ-CODEX); the new drift metrics have weight 0 | owed-docs 6 |
| E22 | The wave-1 decision requests (R-CAP, R-READ-GROK, R-READ-AGY, R-READ-CODEX, R-READ-COPILOT, R-DRIFT, R-REPORT-R) | **Leader rulings.** R-CAP DR-1 (a): the global decision pause is kept (HB-CELL-202 pauses all launches; E4's "that harness only" is superseded by this ruling). R-READ-GROK: Grok's todo, plan, ask and feedback tools are `meta` (J1A-FIX item 24); the agent-profile allowlist is probed at S3. R-READ-AGY (a): `finish` and `wait` stay `other`; an agy cell joins the S3 development probe. R-READ-CODEX: the nominal window (neither option). R-READ-COPILOT DR-1 (a): the per-session grain is inferred from the rows. R-DRIFT: as E21. R-REPORT-R seams go to R-DERIV (`KiviatSeries.reasons`; `--analysis` on cost-compare through `report/analysis.py`) | owed-docs 7 |
| E23 | R-PACKCOST and R-DERIV rows; R-CONTRACT-FACTS DR1 (E12) | R-PACKCOST's one-line `identity.py` addition (`report/analysis.py`: `grade`) is accepted. R-DERIV DR (a): means are taken over the cells that record the measure. `prompt_parts` had no ordinal key (HB-LED-003 on Codex runs, 61 test failures); J1A-FIX item 28 (`09414521`) puts `PromptPart.native_ordinal` first in the key and in `views.KEYS`, filled by every reader: the same fix as E12's `harness_events`. Registered as one class, KEYORD-A | owed-docs 8 |
| E24 | ADR-0026 §5 *Freeze steps*; the R-GOLD row ("the frozen fixture root … no edit to `bench/` moves a golden") | **S4b freeze landed:** catalog **0.8** released in `6231c8f9` and frozen in `1f506520` with `tools/freeze_catalog.py` (the 0.7 two-commit pattern, `d4be6d3c`/`2c4e2204`): the `bench/catalog-freeze.yaml` entry (append-only; `catalog_hash a020fbf6…`; `board_export_version '3'`, GATE-D's pair from the version side), the X1 export and board goldens in `tests/fixtures/catalog/0.8/`. **The non-lean report golden moved** (`tests/goldens/report-nonlean-arms.html`, `loaded: 0.8.dev` → `loaded: 0.8`, catalog version only), although the brief expected it to stay on the frozen 0.7 root. Cause, Verified: `html.write` called with no `root` loads the catalog from `config.repo_root()` (`report/html.py:2224`), the live tree, not the frozen fixture root. R-DRIFT had already moved it once (`58c489ac`, `loaded: 0.7` → `loaded: 0.8.dev`). Registered as a GOLD-A instance | Coordinator #3 |
