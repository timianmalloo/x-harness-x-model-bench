---
id: prompt-lean-rerun-equal-reasoning
title: "Execution prompt - the lean benchmark re-run at equal reasoning, with cost-anatomy capture"
type: doc
status: proposed
owner: "@timianmalloo"
summary: "The operator's prompt for a fresh session: re-run the lean benchmark with six combos pinned at high reasoning and the largest context each serves (Claude Code Opus 5.5 1M; Codex and Copilot GPT-6.1 Sol; Copilot GPT-5.6 Sol Fast; Grok 4.7; Antigravity Gemini 3.8 Flash), add Grok and Antigravity as bench harnesses, extend each cell's record with reasoning text and the per-request, per-tool and prompt-composition facts that explain token cost and drift, and end with a regenerated harness-cost-comparison.html opened in Chrome."
tags: [prompt, coordination, lean-benchmark, cost-anatomy, reasoning]
links:
  - { to: prompt-lean-benchmark, rel: depends-on }
  - { to: run-report-lean, rel: depends-on }
review-by: "2026-10-25"
---

# Execution prompt: the lean benchmark re-run at equal reasoning

Paste everything below the line into a fresh Claude Code session started in `C:\Projects\x-harness-x-model-bench`.

---

Re-run the lean benchmark with every harness/model combination at the **same reasoning setting (high)** and the
**largest context window each one serves**, and extend each cell's record so the next cost report can explain *why*
token cost, time and drift differ, not only *that* they differ. The steps run in this session, in order; each starts
only when the one before it has committed and its gate has passed:
1. `/define-architecture` (T1): the combo-settings contract, the new per-cell facts, the report generator;
2. `/prepare-for-coordination`;
3. `/execute-with-coordination`, as Leader;
4. the readiness probe, the run (two batches), grading, the run report and the cost report.

**Why this run exists.** The 2026-10-10 lean run compared harnesses at their *default* settings: Codex ran
`gpt-6.1-sol` at reasoning effort **low**, Copilot ran the same model at **medium**, and Claude Code at its own default.
The cost comparison (`docs/coordination/harness-cost-comparison.html`) therefore mixed harness behaviour with
reasoning setting. It also found that reasoning text is barely recorded (Claude Code: 202 thinking blocks, 1,793
characters in total; Codex: encrypted reasoning, summaries off by default; Copilot: readable text on 77 of 214
messages), and that none of it reaches the bench's records.

**Sources of record** (read them first; the repo wins over this prompt):
- `docs/specs/lean-pack-benchmark.md`, `docs/architecture-lean-benchmark.md` (ADR-0022, ADR-0023);
- `docs/coordination/run-report-lean.md` and `docs/coordination/coordination-lean.md` (its errata and planned vs
  actual);
- `docs/coordination/harness-cost-comparison.html`: the report this run must deepen, and its method (footer);
- `docs/lessons/defect-classes.md` (CEIL-A, FLAKE-A, GOLD-A, TOOL-UNPINNED-A, SERVE-A and the 2026-10-10 entries);
- `docs/notes/rulings.md`;
- `bench/profiles/*.yaml`, `bench/rings/lean.yaml`, `bench/rings/lean-codex.yaml`, `bench/tools/package.json`.

**Start-state check, before anything else (stop and report if it fails):**
- `origin/main` contains this prompt and `docs/coordination/harness-cost-comparison.html`.
- ai-forward branch `feat/run-report-open` (`ed9625a`) is pushed, or the operator has said it stays local. Its change
  is already installed here (`59f55424`).
- `coord worktree list` shows only the primary; otherwise `coord worktree cleanup` (report, then `--remove` on the
  operator's go).
- Run `coord doctor` and `pack-doctor.py`, and read their states back.
- Re-check "latest" for every pin below (`grok models` with `XAI_API_KEY` unset; `agy models`; Copilot's and Codex's
  served lists). If a newer Opus, Sol, Grok or Gemini id is served, ask the operator before changing a pin.

**The six combos (operator, 2026-10-11).** Every cell pins model, reasoning effort and context:

| combo | harness | model | reasoning | context | how the pinned build takes it (verified 2026-10-11 from the build or its catalog) |
| --- | --- | --- | --- | --- | --- |
| `cc-opus-1m` | Claude Code 2.1.282 | `claude-opus-5-5[1m]` | effort `high` | 1M | `ANTHROPIC_MODEL`; effort through `CLAUDE_CODE_EFFORT_LEVEL` or the `effort` setting (both in the 2.1.282 SDK types) |
| `codex-sol` | Codex 0.160.0 | `gpt-6.1-sol` | `model_reasoning_effort = "high"` | 872k (the catalog's `max_context_window`; default 272k) | `config.toml`; also `model_reasoning_summary = "detailed"` |
| `copilot-sol` | Copilot 1.0.89-1 | `gpt-6.1-sol` | `--reasoning-effort high` | `--context long_context` | CLI flags (both in `copilot --help`) |
| `copilot-sol-fast` | Copilot 1.0.89-1 | GPT-5.6 Sol Fast: **id not yet verified** | `--reasoning-effort high` | `--context long_context` (operator expects about 922k) | CLI flags |
| `grok-4.7` | Grok CLI 1.0.41 (`@xai-official/grok`) | `grok-4.7` | `--reasoning-effort high` (levels low, medium, high, xhigh; catalog default high) | **256k**: the catalog's `context_window` for every subscription model; no larger tier, no context setting | `grok agent stdio` (ACP over stdio, as `coord_transport` drives it); `XAI_API_KEY` unset |
| `agy-gemini` | Antigravity CLI 1.3.2 (`agy.exe`) | `gemini-3.8-flash-high` | `high` is part of the model id (`-low`/`-medium`/`-high`); `--effort high` also exists | **not settable and not reported** by the CLI; Inferred about 1M for Gemini Flash, unverified | `agy -p --input-format stream-json --output-format stream-json` (native stream, not ACP) |

- The operator's "1M everywhere" is the target; the largest *served* window is what gets pinned. Codex's catalog
  (`models_cache.json` in the archived homes) says 872,000 for `gpt-6.1-sol`, at 95% effective. Copilot's long-context
  size is not in any record yet: the probe reads it.
- "GPT-5.6 Sol Fast": Codex's catalog lists `gpt-5.6-sol` and no "fast" variant. The Copilot id must come from
  Copilot's own served-model list through the pinned build (ACP `session/new`, or `/model`). If no such model is
  served, raise a decision request to the Owner; never substitute.
- "High" is each vendor's own scale (Anthropic effort, OpenAI reasoning effort, xAI reasoning effort, Google's
  `-high` model variant). Equal *setting* is the control; the
  report states that equal setting is not proven equal *depth*, and shows reasoning tokens per cell beside it.
- **Grok, verified 2026-10-11:** on the subscription login (`grok models` with `XAI_API_KEY` unset) the served models
  are `grok-4.7` (default, "latest frontier"), `grok-4.7-build-fast`, `grok-4.6`, `grok-4.5`; `~/.grok/models_cache.json`
  gives each a 256,000 context window with auto-compaction at 80%. **Operator, 2026-10-11: keep Grok at 256k** (its
  closest to 1M); the report states the smaller window beside Grok's numbers. With `XAI_API_KEY` set, the list differs (API models
  such as `grok-4.20-0309-reasoning`); the bench uses the subscription login, as the coordination runner does (R-103).
- **Antigravity, verified 2026-10-11:** `agy models` serves `gemini-3.8-flash-{low,medium,high}` (the newest Gemini;
  `gemini-3.1-pro-*` is older), plus Claude and GPT-OSS models, which this run does not use. A one-turn stream-json
  spike (`agy -p ... --output-format stream-json`) reported the served model, 60 tools, per-step usage with
  `thinking_tokens` and `cache_read_tokens`, and step durations, but no context window. The probe must find the served
  limit or record it as `not recorded`.
- **Antigravity updates itself:** it moved from 1.3.1 (last run) to 1.3.2 and left `agy.exe.<stamp>.old` beside the
  binary. The bench must pin a copy (version + sha256 in `.tools`, checked at every cell start, as for the npm builds)
  and turn auto-update off for cells, or a batch can change builds mid-run.
- Grok and Antigravity remain coordination workers in this run; as benchmark subjects they run only in isolated cell
  homes, never in a worker's home or session store.
- Pack arms stay as in the lean design (off, on), so cells pair as before: 10 tasks × 2 arms × 6 combos = 120 cells
  per batch, two batches, **240 cells**.

**Work to divide** (verify each against the repo; the Simplifier strikes what the goal does not need):

- **R-HARNESS-GROK: Grok as a bench harness.** A `bench/profiles/grok.yaml` (vendor `xai`) over ACP:
  `grok agent stdio --model {model} --reasoning-effort {effort}`, `XAI_API_KEY` removed from the cell env. Pin
  `@xai-official/grok` 1.0.41 in `bench/tools/package.json` and add it to `tools.LAYOUT` (version, exe, sha256). Spikes,
  each run once against the pinned build: home isolation (does an env var relocate `~/.grok`, or must the cell set
  `HOME`/`USERPROFILE`; the credential is `~/.grok/auth.json`); the record (`sessions/<cwd>/<id>/`: `chat_history.jsonl`
  with `reasoning` items, `events.jsonl`, `prompt_context.json`, which lists `agents_md_files`); the token source
  (per-call usage in the record, or ACP turn usage); the tool allowlist mapped to the ADR-0004 classes; the instruction
  files Grok loads in each arm (pack-off lists 0). Reuse `coord_transport`'s Grok handling (the skills-reload watcher
  replies, release floor 1.0.34) rather than writing it again.
- **R-HARNESS-AGY: Antigravity as a bench harness.** Antigravity speaks its own stream-json, not ACP, so the engine
  needs a second transport. Reuse the pack's Agy native-stream adapter in `coord_transport` (the coordination runner
  already drives `agy` this way) behind the engine's transport interface; do not fork the ACP path. A
  `bench/profiles/agy.yaml` (vendor `google`): `agy -p --input-format stream-json --output-format stream-json --model
  {model} --add-dir {worktree}` with a stated permission mode. Pin a copy of `agy.exe` 1.3.2 (version and sha256) and
  turn auto-update off for cells. Spikes, each run once: home isolation (`~/.gemini/antigravity-cli`, its credential and
  its conversations store); the record (the stream's per-step `usage` with `thinking_tokens`, and the trajectory database
  `conversations/<id>.db`, table `steps`, which may hold thinking text); the tool allowlist; the instruction files it
  loads in each arm (`AGENTS.md`, `.agents/rules`, `.agents/skills`). If a cell cannot be isolated or recorded to the
  bench's standard, raise a decision request instead of running it half-measured.

- **R-SETTINGS: combo settings are plan facts.** Matrix combos gain `effort` and `context` (schema `bench-matrix/3`;
  `bench-matrix/2` files still load, with both fields absent meaning "harness default", recorded as such). Profiles take
  them through placeholders: Codex `config.toml` (`model_reasoning_effort`, `model_reasoning_summary`,
  `model_context_window`), Copilot argv (`--reasoning-effort`, `--context`), Claude Code env or settings. The plan
  freezes them; the engine identity includes them. Red first: a plan whose combo sets `effort: high` produces a cell
  launch with that setting for every harness.
- **R-SERVED: served settings are read back, per cell, and gate validity.** From each native record, read what was
  actually served: model id, reasoning effort, context window or tier. Known sources: Copilot `session.start.contextTier`
  and `session.usage_checkpoint...reasoning_effort`; Codex `session_meta.context_window` and turn context; Grok the
  session record and the catalog entry it ran under (`context_window`, `reasoning_effort`); Antigravity the stream's
  `init.model` (effort is in the id; the context limit is not reported); Claude Code to be found (spike: the
  transcript's model id and any effort field). A mismatch with the plan makes the cell invalid
  under a new `HB-VAL-*` code. A setting that no record carries is `not recorded`, never assumed.
- **R-PROBE: the readiness probe, per combo, through the pinned build** (last run's SERVE-A lesson: the pinned Codex
  build was refused its model at cell one). One real one-turn cell per combo, X1 fixture, pack off. Exit evidence:
  served model, effort and context read back and equal to the pins; reasoning text visible in the record. Runs before
  batch 1 and before the token approval.
- **R-REASON: reasoning goes to the record.** A new hash-chained fact stream `reasoning` per run (the same ledger
  discipline as `model_calls` and `tool_calls`, checked by `bench verify`). One row per reasoning item: cell, request
  ordinal, harness source kind (`text` · `summary` · `encrypted-only` · `omitted`), the visible text, its character
  count, reasoning tokens where the vendor reports them, and a sha256 of any opaque payload. Turn on the most verbose
  visible reasoning each build allows: Codex `model_reasoning_summary = "detailed"` (and raw reasoning if 0.160.0 has a
  setting for it: verify); Claude Code's thinking display (find the 2.1.282 setting: today's records keep signatures
  only); Copilot's `reasoningText`; Grok's `reasoning.summary` text (present in today's records, beside
  `encrypted_content`); Antigravity's thinking text if the trajectory store holds it, otherwise its `thinking_tokens`
  with source kind `omitted`. Where a vendor returns only encrypted reasoning, the row says so; nothing is
  reconstructed or paraphrased.
  - **Where "the audit log" lands** (operator's term; proposal): the per-cell reasoning text belongs in the run's own
    record (`runs/<run>/reasoning/`), because it runs to megabytes per batch. `docs/audit/audit-log.jsonl` gets one
    entry per batch that names the stream, its row count and its hash head. Ask the operator once if they want the
    text itself in `docs/audit`.
- **R-ANATOMY: the per-cell facts behind cost and drift.** Each is read from the native record, emitted on the normal
  path (no flag), and degrades to `not recorded` with a reason:
  1. *Per request:* fresh input, cache read, cache write, output, reasoning tokens; start and end time. Copilot's
     record holds per-session totals only: find a per-request source (ACP updates, the process log), or record `not
     recorded (per-session totals only)`.
  2. *Prompt composition:* the fixed prefix each harness sends: system or base instructions, tool and skill
     catalogue, instruction files loaded (path, characters, inlined or read on demand), `AGENTS.md`/`CLAUDE.md`. Last
     run measured these by hand: Copilot inlined 13 `applyTo: "**"` files (235k characters) on every request.
  3. *Context curve:* input tokens per request in order, the peak against the served window, and compaction events.
  4. *Tool calls with arguments:* target paths (read, edit, search) and commands; inside or outside the task's
     radius; bytes returned into context; a phase tag by a stated rule (explore · edit · verify · other); re-reads of
     the same file.
  5. *Hooks and skills:* every hook invocation by type with its duration; every skill load.
  6. *Time anatomy:* model, tool, hook and idle time per cell, for every harness (last run had model time for Copilot
     only).
  7. *Drift, split three ways:* machine-written (tool caches, hook and audit logs), task-implied, and discretionary
     edits; plus *attention drift*: the share of reads and searches that target files outside the task's neighbourhood
     (its radius, the radius's imports, its tests).
  These are new metrics: catalog 0.7 → 0.8, each with its definition, grader and `not recorded` reason.
- **R-DRIFT-FIX: two defects found by the cost comparison** (register entries first, class → sweep → control):
  - the drift grader counts tool caches (`.pytest_cache`, `.mypy_cache`) as scope creep; most raw scope-creep lines
    last run were caches;
  - five tasks' `blast_radius` omits the test file the task needs (RW2 `test_schedule.py`, NG1
    `tests/test_limiter.py`, NG2 `tests/test_interp.py`, SM1 `tests/test_tables.py`, SM2 `tests/test_search_many.py`);
    every harness wrote it. Fix the task versions (a task-version bump, recorded) or the grader's rule; state which.
- **R-REPORT: the deeper cost report, generated.** `bench report --cost-compare <run> [<run> ...] --out
  docs/coordination/harness-cost-comparison.html --open` writes the page from the run records alone, no hand-filled
  numbers, and opens it in Chrome through the same lookup as `render-markdown.py --open` (skipped under `AF_NO_OPEN` or
  `CI`; otherwise `not opened: <why>`). It keeps the current page's five sections (what was benchmarked; harnesses and
  models, now with served effort and context; cost per combo; observations; why same-model harnesses differ) and adds:
  - reasoning: tokens per cell and per request, visible-text volume, source kind per harness, and a few short excerpts;
  - the per-request context curve per combo;
  - prompt composition per combo (measured, not hand-classified);
  - tool phases (explore / edit / verify) and bytes returned;
  - time anatomy for every combo;
  - drift three ways plus attention drift, with the out-of-scope paths listed;
  - the kiviat with a checkbox per series (6 combos × 2 arms = 12), normalized over all series so toggling never
    rescales; axes: token economy, speed, request economy, tool-call economy, clean cells, edit orientation, read
    orientation, hidden checks passed.
  A golden test pins the renderer on a fixture whose `bench/` inputs are its own (GOLD-A), so a pin bump never reddens it.

**Rules the plan must encode** (measured lessons):
1. **Floors (CEIL-A), measured 2026-10-10 for ~75 kB briefs:** Grok about 117k, Agy about 166k, Opus Coordinator 137k,
   Opus worker about 109k, Haiku about 99k, at the first edit. Keep Grok and Agy briefs under ~30 kB, or route the track
   to an Opus sub-agent. Thresholds are absolute: the floor plus the planned work.
2. **Before every `src/` or `tests/` join,** one full suite on the candidate, then the join recount. A red that passes
   alone gets one retry; a second red goes to a loop-back fix track (Opus). Record FLAKE-A instances.
3. **The worker gate (R-104):** red first on an assertion; the guard list on the first and final commit;
   `mutate_check` on the worker's own mutation files; ruff and `docs-graph validate`; the console flag on every launch
   it adds; the windows check at hand-back. Never `--no-verify`, never rewrite a commit.
4. **Never edit a log.** A torn row or a classifier denial stops that action and goes to the operator.
5. **Every brief's proof command is run once by its author before dispatch (TEST-E).**
6. **Seats never write the primary.** New session ids per continuation (IDN-A); a new runner turn uses a new branch.
7. **Caps:** 6 concurrent workers, at most 2 per external harness; the health check at every dispatch and join.
   Scratch under `C:\tf\<track>`.
8. **Tokens are the only cost axis.** Never write USD (Ruling 115).
9. **A relayed decision is answered before its default fires,** or its timeout is extended past the operator's
   expected latency (last run's D1 defaulted while the operator was answering).
10. **Pin ruff** in the dev dependency group (TOOL-UNPINNED-A) before the first join.

**Seats** (as in the last run):
- **Owner:** Claude Code, Fable (`claude-fable-5-1`), session `owner-fable`; rules into `docs/notes/rulings.md`.
- **Leader:** Claude Code, Opus (`claude-opus-5-5`), the next lease epoch; merges only in a dedicated integration tree;
  pushes with exactly `git -C C:/Projects/x-harness-x-model-bench push origin <gated sha>:main` and reads origin back.
- **Coordinators:** Claude Code, Opus; compiled briefs; own the errata and the register.
- **Claude sub-agents** (explicit `model` every time): Opus for judgement (the reasoning-capture design, the report
  analysis, loop-back fixes); Haiku latest (`claude-haiku-5-5`; re-check) for mechanical work.
- **Distributed coding** through `coord-runner`, served id read back for every dispatch: Grok `grok-4.7` (effort high;
  R-103) and Agy `gemini-3.8-flash-high`, in parallel, within rule 1.
- **Not workers:** Codex, Sonnet, GitHub Copilot (benchmark subjects only). Grok and Antigravity are both workers and
  subjects: a worker's home, credentials and session store are never a cell's, and a cell never reads them.

**The run** (Leader, after the tracks join and the batch gate is green):
1. Push. Run R-PROBE for all six combos; stop on any mismatch.
2. Commit a pre-registration paragraph (what is compared, the six pins, the arms, the metrics) before batch 1.
3. Ask the operator once to approve the token budget: **about 160M–270M** (Inferred: last run's per-cell means × 40
   cells per combo, with Copilot GPT-5.6 Sol Fast assumed equal to Copilot GPT-6.1 Sol, × 1.0–1.5 for high effort;
   Grok and Antigravity have no bench cells yet, so each is bracketed at 0.2M–0.8M per cell). Set `spend_cap_tokens`
   per batch from the approval.
4. Batch 1: 120 cells. Checkpoint: minutes per cell for run and grading, tokens per cell per combo and arm, reasoning
   rows per cell, and served settings, each against the estimate. Batch 2 waits for the operator only if a threshold
   trips, or if Grok's or Antigravity's measured tokens per cell exceed the bracket.
5. Batch 2: 120 cells. Grade, verify (`bench verify` on both, including the `reasoning` stream), report.
6. The run report (md + html) under `docs/coordination/`, ending with `render-markdown.py ... --open` (Stage 7). It
   carries the lean summary as before, and the served settings per combo.
7. **Then the cost report:** `bench report --cost-compare` over both batches, written to
   `docs/coordination/harness-cost-comparison.html` and opened in Chrome. Commit and push both reports.

Targets: about 5–6 h of machine time for 240 cells including grading (Inferred: last run's 158 min for 120 cells,
scaled to 240, with Copilot's heavier cells and two harnesses never timed in a cell). The checkpoint measures it.

**Plan output, per track:** owner; harness and model, with the reason; authored paths; depends-on; tier; budget
(calls, tokens, wall); exit evidence; fallback; termination condition; join batch. Also the serial spine, the critical
path (Inferred durations, labelled), the struck tracks, and the operator actions with their timing (the
GPT-5.6 Sol Fast id if unresolved, the token approval, the audit-log placement question, any Grok or Antigravity
isolation that needs an operator setting, worktree cleanup).

**Execution reporting:** one status table per update (task, what it does, status, harness and model). Report only
when done or blocked on the operator.

**Stop rules:** the health check trips twice; the host becomes unstable (record evidence first); `main` cannot be
made green within one bisect round; a probe shows a served setting that differs from its pin; an operator-only
blocker gates every remaining track.

Close with `coord worktree cleanup` (report first, then `--remove` on the operator's go), the closing audit entries,
and the scratch roots listed for deletion.

**Not in scope:**
- reasoning *quality* scoring or an LLM judge of reasoning text;
- new tasks (the five radius fixes are task-version bumps of existing tasks, not new tasks);
- arm Y, campaigns, calibration cells, macOS, GitHub Actions;
- USD;
- force pushes or history rewrites;
- Codex, Sonnet or GitHub Copilot as workers.
