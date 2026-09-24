---
id: "design-phase2-copilot-profile"
title: "Design: the Copilot harness profile (phase 2, to-do rows 1-5)"
type: design
status: draft
owner: "@timianmalloo"
phase: "Phase 2 · smoke on all harnesses (wave 1: the Copilot-vs-Codex capability)"
tags: [benchmark, harness, copilot, profile, acp, telemetry, isolation]
links:
  - { to: design-phase1-walking-skeleton, rel: refines }
  - { to: arch-harness-bench, rel: implements }
  - { to: spec-harness-bench, rel: implements }
  - { to: adr-0003-harness-profile, rel: implements }
  - { to: adr-0006-results-data-model, rel: refines }
  - { to: adr-0008-telemetry, rel: implements }
  - { to: adr-0002-cell-driver, rel: depends-on }
  - { to: note-spike-isolation-permissions, rel: depends-on }
  - { to: note-spike-runner-path, rel: depends-on }
  - { to: note-20260923-token-source, rel: relates-to }
  - { to: rulings-register, rel: depends-on }
  - { to: coordination-finish-harness-bench, rel: relates-to }
review-by: "2027-03-24"
summary: >-
  How a Copilot cell runs: a data-only profile (bench/profiles/copilot.yaml) whose templated command launches the
  pinned native binary @github/copilot-win32-x64 1.0.89-1 by path with no ACP adapter; an ACP session/set_model
  before the prompt (driver.py changes); a reader over the per-cell events.jsonl that writes per-report model_calls
  rows under the ADR-0006 grain amendment (R-26) and records each tool call's outcome_code, so the pack-on hook
  denial measured on revision 92 (R-27) is visible. Also HB-PRE-002 for Copilot's instruction files, the US-9 scan,
  the US-9..US-14 promise-to-test table, and the Leader's capture and scrub procedure. Revision 3, after the design gate
  and rulings R-12..R-28.
review-suggested: []
---

# Design: the Copilot harness profile (phase 2, rows 1-5)

**Track:** W1-COP-D. **Implemented by:** W1-COP-I (rows 1-3, 5; it wires row 4), W1-COP-R (row 4), W1-ACP (the driver change and three `engine.py` hunks). **History:**
- revision 1: `f3e5c3f`;
- revision 2: `7f2a7c1`, after capture window 1;
- revision 3: this one, after the design gate on `7f2a7c1` and rulings **R-12..R-28** (`docs/notes/rulings.md`, main `38e024a`, merged here).
- revision 3.1: the three lenses cleared their vetoes on `b260dd1`/`f952f87` with Minor conditions, applied here; R-29 and R-30 merged from main. The fixture re-scrub is `f952f87`.

The rulings are authoritative where this text and a ruling differ. The gate dispositions are in section 18.

Labels:
- **Verified**: observed in this session or in a cited spike.
- **C**: measured in capture window 1, from the raw capture (since deleted) or the committed fixture `9c6c615`.
- **Inferred**: reasoned, with the model stated.
- **Flagged**: open.
- `assume:` marks a belief, with what would confirm it and what breaks if it is false.

## 1. Responsibility

Run one Copilot cell exactly as the Claude Code and Codex cells run:
- a fresh per-cell home;
- the pinned build, invoked by path and re-hashed at every cell start;
- the pinned model, set before the prompt;
- the same static permission profile;
- a native record read into the same Canonical Data Model.

The profile table (Ports & Adapters, a data-driven Strategy) carries every harness difference as data.

**Grounding read (cited):**
- `docs/architecture.md`;
- ADR-0003, ADR-0006, ADR-0008, ADR-0013;
- `spike-isolation-permissions.md` (R1, R2, R11, N1.2) and `spike-runner-path.md`;
- `decision-token-source-per-harness.md`;
- `.claude/skills/execute-with-coordination/reference/copilot.md`;
- rulings R-12..R-28;
- the code: `src/harness_bench/{profiles,tools,driver,workspace,errors,engine,archive,views}.py`, `grade/runner.py`, `telemetry/*`, `report/credentials.py`, `bench/profiles/*.yaml`, `tests/e2e/*`.

**Observations:**

| # | Observation | Label |
| --- | --- | --- |
| O1 | The build is 1.0.89-1: the installed CLI, the pinned npm exe (`exe_version`), and ACP `initialize.agentInfo.version` all agree. `session.start.data.copilotVersion` is `"0.0.0"` and is not evidence (R-22). | Verified; C |
| O2 | These flags and subcommands exist: `--acp`, `--model`, `--allow-tool`, `--no-auto-update`, `--assisted-approval`, `--allow-all*`, `--yolo`, and `instruction list --json`. | Verified |
| O3 | `COPILOT_HOME` moves config and state. `COPILOT_GITHUB_TOKEN`, `GH_TOKEN` and `GITHUB_TOKEN` override the stored login. `COPILOT_AUTO_UPDATE=false` pins the running binary. | Verified |
| O4 | The package cache and the shared caches live in `%LOCALAPPDATA%\copilot`, outside `COPILOT_HOME`. | Verified |
| O5 | The npm package is `@github/copilot` 1.0.89-1 (prerelease channel). The binary is `@github/copilot-win32-x64/copilot.exe`. | Verified; R-12 |
| O6 | A per-cell ACP home holds `config.json` (`//` comment lines, no login), `logs/` and `session-state/<id>/{events.jsonl, workspace.yaml, checkpoints/}`. There is **no `session-store.db`** and no token-shaped string. | C |
| O7 | `events.jsonl` has 33 events pack-off and 56 pack-on. The largest raw line was 684,653 bytes (the pack-on `system.message`). | C |
| O8 | `session.start.data`: `sessionId` (equal to the ACP `sessionId`), `version: 1`, `producer: "copilot-agent"`, `selectedModel`. | C |
| O9 | The last `session.shutdown` (`routine`) carries `modelMetrics.<model>.{requests.count, usage.{inputTokens, outputTokens, cacheReadTokens, cacheWriteTokens, reasoningTokens}, tokenDetails.{input, cache_read, cache_write, output}.tokenCount, totalNanoAiu}`. **No event carries per-request token counts.** | C |
| O10 | `tokenDetails.input + cache_read + cache_write == inputTokens`. off: 15 + 46,801 + 12,170 = 58,986. on: 18 + 439,386 + 88,237 = 527,641. `requests.count` (off 5, on 6) equals the number of `assistant.message` events. | C |
| O11 | The ACP `session/prompt` result `usage` equals `modelMetrics` exactly. uncached + cache read + cache write + output = `totalTokens` (off 59,501; on 528,166), and `thoughtTokens` = `reasoningTokens`. It names no model and has no `_meta`. | C |
| O12 | The served model is `{gpt-6-sol}` in `modelMetrics`, in `assistant.message.model` and in `usage_checkpoint`. `session.model_change` shows `gpt-6-sol` → `gpt-6-sol`, source `sdk`. | C |
| O13 | `session/set_model` with `gpt-6-sol` returned `{}`. An unknown id returned `-32602 "Invalid modelId …: not one of this session's models."`. The modes are `agent` (current), `plan` and `autopilot`. | C |
| O14 | The first `user.message` (no top-level `agentId`) `content` sha256 = `802dfde4…` = the plan's `prompt_sha256`, in both arms. Each arm has exactly one `user.message`. | C |
| O15 | **Tool calls requested.** off: `glob` ×2, `powershell` ×2, `view`, `apply_patch`, **6 of 6 `success: true`**. on: `skill` ×2 (`implement`, `optimize-graph`), `glob` ×3, `powershell`, `view`, `rg`, **all 8 `success: false`, `error.code: "denied"`**, message `Denied by preToolUse hook from "repo settings" (hook errored)`. | C (fixture `9c6c615`, re-counted here) |
| O16 | `instruction list --json`: off `[]`; on 21 entries `{id, label, location: "repository", type, sourcePath, applyTo?, description?, defaultDisabled}`. | C |
| O17 | Pack hooks under Copilot ACP: 8 `hook.start` / 8 `hook.end` (`userPromptSubmitted`, `sessionStart`, `preToolUse` ×5, `agentStop`), **all `success: false`**. Each is a PowerShell `ParserError` on the revision-92 POSIX-shell hook command. | C |
| O18 | **No event type names skills or instruction files.** The fixture has no `skill.*` event; instruction-file names appear only inside the `system.message` text. "Skills" are visible only as `tool.execution_start` with `toolName: "skill"`. | C (fixture event-type census) |
| O19 | 0 ACP permission requests in both arms. The pack-on turn made no code change; pack-off added 4 lines. The pack-on turn cost 528,166 tokens, against 59,501 pack-off (R-14 condition 2). | C |
| O20 | Copilot reads these instruction files: `.github/copilot-instructions.md`, `.github/instructions/**/*.instructions.md`, `AGENTS.md`, `CLAUDE.md`, `.claude/CLAUDE.md` and `GEMINI.md`, at the repository root, the cwd and the folders between; at user level in `$COPILOT_HOME/…`; and in `COPILOT_CUSTOM_INSTRUCTIONS_DIRS`. | Verified (docs.github.com, 2026-09-24) |

## 2. Delivery phasing and seams

Wave 1 of phase 2: X1 × {copilot-sol, codex-sol, cc-opus} × pack {on, off} × 1.
- **Pack on for Copilot is measured on revision 95** through `--pack-source` (R-27). On revision 92 it is not a treatment (O15, O17).
- **Mock-substitutable seams:**
  - the fake ACP agent (driver);
  - the committed samples plus synthetic samples (reader). The revision-92 pack-on sample is **only** the negative control for the denial assertion; the revision-95 capture replaces it for every other test (R-27 condition 3);
  - a fake tools folder (`tools.py`).

## 3. Data model: the `model_calls` grain amendment (ADR-0006, R-26)

The authoritative text is **ADR-0006 "Amendment 1"**, written in this revision:
- **Grain.** One `model_calls` row is exactly one model's token usage in one native usage report, by one principal, as read by one extraction.
  - For Claude Code and Codex, a report is one request.
  - For Copilot, a report is the per-model entry in the **last** `session.shutdown.modelMetrics`.
- **`requests`** is additive: Claude Code and Codex 1; Copilot `requests.count`; absent (a pre-amendment ledger) reads as 1.
- **`start` and `end`** are set only for single-request reports. Copilot model time is therefore NOT_RECORDED.
- **Calls per cell** = Σ `requests`. **A row count is not a call count.**
- **Key rule:** `model` joins the key, `(run_id, extraction_id, principal, native_session_id, native_ordinal, model)`, where `native_ordinal` is the report's line number.
  - Two models in one shutdown line share that line number. `modelMetrics` is keyed by model, so a report has at most one entry per model.
  - The revision-2 packed key (`n*1000 + i`) is **dropped**. A sub-ordinal column was rejected, because `model` already identifies the entry.
- **`tool_calls` gains `outcome_code`**: the native error code of a failed call, for example `denied`; null on success or when not recorded (R-27).
- **Migration:** none. Absent fields read as 1 and as null, and phase-1 ledgers have one model per line.

**Owners in the implementation:**
- **W1-COP-R** (the telemetry package): `ModelCall.requests: int = 1` and the `ModelCall` docstring stating the grain and the `requests` rule; `ToolCall.outcome_code: str | None = None`; `normalize.model_call_rows` / `tool_call_rows` emitting both columns; and the Copilot reader.
- **W1-COP-I** (it wires row 4): the `views.py:33` key tuple (adding `model`), the one `calls_per_cell` compute reader (Σ `requests`), and the guard test ("a two-request single-row fixture yields 2; no view counts rows", R-26 C2).
- **One row reader (D&P C-b):** every `model_calls` row is read through one mapper (ledger row → `ModelCall`). The default for an absent `requests` is the `ModelCall.requests = 1` field default, in one place; no second `.get("requests", 1)` anywhere (W1-COP-I).
- **Release order (D&P C-c):** the `views.py:33` key widening (W1-COP-I) lands before, or in the same merge as, the first graded Copilot cell with two models. Until then `_refuse_duplicates` would reject that cell's rows.

`views.py` and `normalize.py` are outside both tracks' owned lists, so this is a **Leader ownership item** (section 15).

`decision-token-source-per-harness.md:40` is corrected from "per-call rows" to "per-report rows" (R-26 C1, this revision).

AI units (`totalNanoAiu`) stay in provenance until the wave-3 row (R-15). `requests.count` does **not**: it is stored as `model_calls.requests` (R-26 narrows R-20 condition 4; the Leader asks the Owner to record the narrowing).

## 4. Contracts

### 4.1 `bench/profiles/copilot.yaml` (row 1)

```yaml
# Copilot cell profile (ADR-0003, ADR-0013; docs/design/phase2-copilot-profile.md). Native ACP: no adapter.
harness: copilot
home_env: COPILOT_HOME
credential: null                                  # nothing is copied; the login is the Windows credential store (R1.1, N1.2)
credential_kind: "subscription login (credential store)"   # reported by the launcher, not assumed by the engine (R-13 c2)
files: {}
command: ["{exe}", "--acp", "--model", "{model}", "--allow-tool", "shell", "--allow-tool", "write"]   # spike R2; C: 0 ACP requests
env:
  COPILOT_AUTO_UPDATE: "false"                   # R-12
mode: null                                        # agent (default); plan and autopilot are never set
set_model: true                                   # ACP session/set_model with the pin, before the prompt (ADR-0003)
record_glob: "session-state/{session_id}/events.jsonl"
usage_source: native_record                       # R-26: per-report model_calls from the last session.shutdown
auxiliary_models: []                              # C: only gpt-6-sol
```

Profile-data choices (the Patterns Expert's findings, with the Simplifier's N1 and N2; section 18):
- **`credential: null`** stays the nullable singular (Simplifier N1). `report/credentials.py:65` already skips a profile with no credential, and `seed_home`, `clean_home` and `credential_names` guard `None` (so there is no unlink of `home / ""`). No correctness reason favours a list, so Claude Code and Codex keep `credential: {source, name}`, and `report/credentials.py` is unchanged.
- **`command:`** templates the whole launch as data. Claude Code and Codex become `["{node}", "{adapter}"]`. `{node}` is resolved with `shutil.which` only when the template names it; a template naming `{adapter}` for a build without one raises `HB-PRE-007`. The adapter/no-adapter choice moves into the template filler (the placeholders it resolves). It is **not removed**, and `argv` itself has no branch (Simplifier N2).
- **`credential_kind`** is profile data (R-13 condition 2). Claude Code and Codex set `subscription login (copied)`.

**Other `profiles.py` changes (W1-COP-I):**
- `HARNESSES` gains `copilot`.
- `DROP_EXACT` gains `GH_TOKEN`, `GITHUB_TOKEN` and `GH_HOST`. `COPILOT_*` is already dropped by prefix, and the profile `env` is applied after the drop.
- `READERS["copilot"]` (the COP-R → COP-I seam).
- **One registry-consistency test:** `HARNESSES` == `READERS` keys == `tools.LAYOUT` keys == `bench/profiles/*.yaml` stems.

### 4.2 Pinned build (row 2; R-12)

- `@github/copilot` is pinned exactly at `1.0.89-1`.
- `LAYOUT["copilot"] = {"version_file": "@github/copilot-win32-x64/package.json", "version_key": "version", "exe": "@github/copilot-win32-x64/copilot.exe", "adapter": None}`. The adapter is an **optional component, None-guarded, in `tools.resolve` only**: it skips the adapter checks, and `Build.adapter`, `adapter_version` and `adapter_sha256` are `None`. `record()` keeps all four keys.
- A missing exe raises HB-PRE-007.
- `COPILOT_AUTO_UPDATE=false` is asserted as profile data (R-12 condition 3).
- The report header names the build and marks it `prerelease` (R-12 condition 1).
- **Executed-build evidence:** W1-ACP records `agent_version`, verbatim from `initialize.agentInfo`, on `attempt.session_opened` (R-28). The comparison with the pin is a wave-2 view check.

### 4.3 Launch shape (row 3) and the driver

`Profile.argv(build, model)` fills the `command` template: `{exe}`, `{node}`, `{adapter}`, `{model}`. For Copilot the result is `copilot.exe --acp --model gpt-6-sol --allow-tool shell --allow-tool write`.

**`driver.py` changed.** It gains an optional `session/set_model` (W1-ACP, after its step (f)):
- `run_turn(..., model=None)`. When a model is given, the driver sends `session/set_model {sessionId, modelId}` right after `session/new`, inside the handshake deadline.
- **Errors are mapped by step through R-23's one classifier.** At the `set_model` step:
  - a JSON-RPC error with auth evidence → `blocked_auth`;
  - any other refusal, including C's `-32602 "Invalid modelId"` → `model_unavailable` (HB-CELL-116; R-18);
  - a timeout → `handshake_timeout`; EOF → `adapter_crash`.

  The prompt is never sent after a refusal.
- W1-ACP inverts `test_run_turn_has_no_model_switch`.
- The `engine.py` hunks are W1-ACP's, three in all (R-13, R-24): `model=` to `run_turn`, the `credential_kind` the launcher reports, and `acp_usage` on the terminal event.

**`set_model` and `credential_kind` on the `Launcher` Protocol (R-30).** Both are typed fields of `engine.Launcher`, like `mode`. The call site is `model=cell["model"] if launcher.set_model else None`, and there is no `getattr` on the launcher surface (a grep-level test asserts it). Every launcher and fake declares both fields. The negative control: `set_model = False` never sends the setter (W1-ACP; built at `61acbd6`).

### 4.4 Telemetry reader: `telemetry/copilot.py` (row 4)

**Source:** `usage_source: native_record`, from `events.jsonl`. The ACP `usage` is the **independent oracle**:
- at runtime, recorded as `acp_usage` (R-24); the equality check is a **wave-2 view check**;
- on the committed samples, the **golden-sample cross-check** (section 13).

Rationale (revision 2, upheld by R-26):
- the native record names each served model, and the ACP usage names none;
- the native record needs no engine or normalize change to be the source.

**Pattern: a Format Indicator with a fail-closed version gate, and a Tolerant Reader for fields.**
- `session.start.data.version` must be in `SUPPORTED_EVENT_VERSIONS = {1}`. When it is not, or when there is no `session.start`: `MissingField(0, "events.version")` and no model rows.
- **Why only Copilot is gated:** it is the only one of the three records that carries a format version distinct from the build. Claude Code and Codex rows carry the CLI build version (Inferred from the phase-1 fixtures' shape). A gate on the build would duplicate US-12's build check, so their readers stay Tolerant Readers without a gate.

**Bounds:** the existing `rows()`: a 1 MiB line cap, a 256 MiB file cap, malformed lines counted. No SQLite file is opened, because a per-cell ACP home has none (O6).

| Canonical field | Source and rule |
| --- | --- |
| `session_id` | `session.start.data.sessionId`, else `path.parent.name` |
| `first_user_text` (US-10) | the first `user.message` with **no top-level `agentId`**: its `data.content`, never `transformedContent`. `assume:` a sub-agent's `user.message` always carries a top-level `agentId`. Evidence: `session-profile.py:708-716` and the operator-log census (O7 in revision 2). Confirm: a synthetic sub-agent-first sample (section 13). Breaks: the prompt hash compares a sub-agent's prompt. The hash is taken after the spec's US-10 normaliser (UTF-8, LF, no BOM, one trailing newline) |
| `model_calls` | the **last** `session.shutdown`: one `ModelCall` per `modelMetrics` key (sorted), `native_ordinal` = that line, `model` = the key, `requests = requests.count`, and `start = end = None` unless `requests == 1`. The buckets: `uncached_input = tokenDetails.input.tokenCount` (never `inputTokens`, R-20 condition 2), `cache_read = usage.cacheReadTokens`, `cache_write = usage.cacheWriteTokens`, `output = usage.outputTokens`, `reasoning = usage.reasoningTokens` (a component of output, **not added**). **The arithmetic check:** `tokenDetails.input + cacheRead + cacheWrite == usage.inputTokens`, else `MissingField(n, "input_tokens")`. Every value goes through `ex.count` |
| no `session.shutdown` | `MissingField(0, "session.shutdown")` and no model rows. **Wave 1** reads `invalid (no model call)`, pinned by a test that cites R-15 (the "not recorded" state is wave 2). The fix is R-21 (a graceful end, W2-STOP) |
| `tool_calls` | `tool.execution_start` → `tool.execution_complete`, correlated by **`toolCallId` (the Correlation Identifier)**. `ok` = `data.success`; **`outcome_code` = `data.error.code`** (null when absent); unmatched → `end=None`, `ok=None`. The tool class is a dict: `TOOL_CLASS = {"powershell": "shell", "bash": "shell", "shell": "shell", "apply_patch": "edit", "write": "edit", "edit": "edit", "create": "edit", "view": "read", "glob": "read", "rg": "read", "grep": "read"}`, default `other` (C: `skill` is `other`). `bash`, `shell`, `write`, `edit`, `create` and `grep` are Inferred |
| `errors` | `session.error` → `ProviderError(n, None, errorType, message[:300])`. None observed (R3) |

**Grain assertions in the reader tests (R-26 C3):**
- the Copilot sample yields exactly one row per model in the last shutdown, with `requests == requests.count` and null `start`/`end`;
- the Claude Code and Codex readers yield `requests == 1` on every row.

### 4.5 HB-PRE-002, the US-9 scan and the pack-on signals (row 5)

**HB-PRE-002 (`workspace.py:25`):**
- `INSTRUCTION_FILES = ("CLAUDE.md", ".claude/CLAUDE.md", "AGENTS.md", "GEMINI.md", ".github/copilot-instructions.md")`;
- `INSTRUCTION_DIRS = (".github/instructions",)`: refuse when the folder holds any `*.instructions.md`;
- both are checked in the cells root and every ancestor; the `RUN_CODES` text lists them;
- this is defensive against O20, which is documentation, not a spike.

**The probe, collapsed to two layers** (Simplifier F1, applied):
1. **Static, the US-9 proof** (W1-COP-I, `tests/test_workspace.py`). Build the pack-off X1 copy **through the real workspace builder**: `workspace.task_source` → `cell_working_copy`, the same path `cli._workspace_builder` runs. Then scan every Copilot instruction path in it, plus `prompt.md`, against `bench/pack-markers.txt`: no marker may appear. The pack-on copy (plus `install_pack`) must match at least one marker (the positive control, R-16 condition 1). The live `[]` check is the `bench plan` step below.
2. **Live, per cell** (W1-COP-R's reader). Hook-denied tool calls and skill calls are **derived from `tool_calls`** (`outcome_code == "denied"`, `name == "skill"`), not counted separately (Simplifier N4). The only new reader output is the hook pair, `hook_starts` and `hook_failures` (failed `hook.end`). Its Canonical home is two `Extraction` fields in `telemetry/__init__.py` (`int | None`; `None` = the harness records no hooks) (W1-COP-R).

**Cut:** the `system.message` marker scan. It remains only as a fixture provenance fact. Any future runtime scan of `system.message` needs a synthetic fixture, and degrades to "not measured" when the field is absent.

**"Instruction files loaded" and the live US-9 check: one function (Simplifier N3).** No event carries instruction files (O18). One function, `instruction_list(exe, ws, env) -> list[dict]` (W1-COP-I), runs the pinned `copilot.exe instruction list --json`. `bench plan` calls it once per Copilot (task version, pack arm, build), on a throwaway working copy built by the real builder, and freezes the result in the plan:
- the **pack-off result must be `[]`**: this is the US-9 live check, and a non-empty list refuses the plan;
- the **pack-on count** is the R-14 condition 1 datum, reported on each cell.

One `native` test covers the function.
- `assume:` the list is a pure function of the working-copy tree, the build and an empty home, so it is identical for every cell of one (task version, pack revision, build).
- Confirm: the two per-arm runs in capture window 1 reproduce on re-run (a W1-COP-I `native` test runs it twice).
- Breaks: a per-cell difference would go unseen.

Recording it in the plan makes `plan.py` a W1-COP-I surface (an ownership item, section 15).

"`skill.invoked`" in R-14 condition 1 does not exist as an event type (O18). The count reported is **skill tool calls requested**, with their outcomes.

**Treatment facts on revision 92** (replacing revision 2's text; R-25, R-27):
- The pack hooks fire and **all fail** (O17), and the failing `preToolUse` hook **denies every tool call** (O15). A pack-on Copilot cell under the revision-92 hook command **runs no tool**.
- Skills are **requested, not loaded**: both `skill` calls were denied.
- The instructions are in the system prompt: `instruction list` returns 21 entries, and the markers are present.
- Every revision-92 pack-on Copilot cell carries `pack hooks failed (Copilot PowerShell)` and is reported "pack on: all tools denied", excluded from comparisons (R-27).

## 5. Patterns

| Where | Pattern |
| --- | --- |
| profile data, `command`, `credential`, `credential_kind`, `set_model` | Table-driven Strategy; typed `Launcher` fields (R-30) |
| `LAYOUT["copilot"]["adapter"]` | an optional component, None-guarded, in `tools.resolve` only |
| `telemetry/copilot.py` | Anti-Corruption Layer into the Canonical Data Model; a Format Indicator with a fail-closed version gate; a Tolerant Reader for fields |
| tool calls | `toolCallId` as the Correlation Identifier; the tool class as a lookup dict |
| the token oracle | the native record as source; ACP `usage` as the independent oracle (`acp_usage` at runtime; the golden-sample cross-check on fixtures) |
| driver errors | one classifier for every step (R-23), mapped by step |

The Solution-Selection Ladder is unchanged: reuse `rows()`, `ex.count`, `find_records` and `check_build`; add no new dependency; `sqlite3` is gone from the design and from `capture_sample.py` (Simplifier F4).

## 6. Change-surface list (E7), with owners

| Surface | Change | Owner |
| --- | --- | --- |
| store | `bench/profiles/{copilot,claude-code,codex}.yaml` (`command`, `credential_kind`; Copilot `credential: null`); `bench/tools/package*.json`; `bench/matrix.wave1.yaml`; `bench/pack-markers.txt` (R-16) | W1-COP-I |
| model | `Profile` (`command`, optional `credential`, `credential_kind`, `set_model`); `Build` (adapter optional) | W1-COP-I |
| model (Canonical) | `ModelCall.requests` and its docstring; `ToolCall.outcome_code`; `Extraction.hook_starts`, `Extraction.hook_failures` | W1-COP-R |
| service | `profiles`, `tools`, `workspace` HB-PRE-002, `errors` RUN_CODES text and the setter form of HB-CELL-116 (R-18) | W1-COP-I |
| service | `plan.py`: freeze `instruction_list` per Copilot (task, pack, build); the pack-off `[]` refusal | W1-COP-I (**ownership item**) |
| driver | `run_turn(model=)`, `session/set_model`, the step mapping through R-23's classifier, `agent_version` (R-28) | W1-ACP |
| engine | exactly three hunks: `model=`, `credential_kind`, `acp_usage` | W1-ACP (R-13, R-24) |
| reader and projection | `telemetry/copilot.py`; `normalize.model_call_rows` / `tool_call_rows` (`requests`, `outcome_code`) | W1-COP-R (**normalize: ownership item**) |
| compute readers | `views.py:33` key (+`model`, landing before the first two-model Copilot cell), the one row mapper (`requests` default), `calls_per_cell`, the row-count guard | W1-COP-I (**ownership item**) |
| client/UI | the report header shows the build plus `prerelease` (R-12 c1) and the pack revision (R-27 c1); `pack hooks failed (Copilot PowerShell)` flag (R-25); `invalid (tools denied by hook)` is a wave-2 row | report owner per plan; wave 2 |
| tests | section 13; `tests/e2e/test_us13_canary.py`, Copilot branch | W1-COP-I (R-16) |
| mutation | `tests/mutations/copilot.json` (W1-COP-I); `tests/mutations/copilot_reader.json` (W1-COP-R) | as listed |
| docs | ADR-0006 Amendment 1; token-source note line 40 | W1-COP-D (this revision) |
| fixtures | `--rescrub` of `9c6c615` to scrub-rule/3 (section 12); the revision-95 capture | Leader |

## 7. Error and concurrency model

- One Job Object per cell, and one `COPILOT_HOME` per cell.
- `assume:` concurrent cells tolerate the shared `%LOCALAPPDATA%\copilot`. Confirm: the X1 run at parallelism 2.
- The reader is pure over the archived file, so a re-grade is byte-identical.
- Codes: HB-CELL-116, HB-CELL-104/105, HB-TEL-001 (`events.version`, `session.shutdown`, bucket fields), HB-PRE-002, HB-PRE-007, HB-CELL-115.

## 8. Failure-mode analysis

| # | Mode | Disposition | Test |
| --- | --- | --- | --- |
| F1 | Advertised model ≠ served model | **Prevent:** `set_model`. **Detect:** served models from `modelMetrics` → HB-VAL-002 | section 13, US-11 |
| F2 | The setter is refused | **Prevent** the prompt: HB-CELL-116 (R-18, R-23) | driver, a `-32602` fake |
| F3 | A newer cached binary answers | **Prevent:** R-12. **Detect:** `agent_version` (R-28, the wave-2 check) | profiles; W1-ACP |
| F4 | A token env var overrides the login | **Prevent:** drop it | profiles |
| F5 | No `session.shutdown` | **Degrade:** HB-TEL-001; wave 1 reads `invalid (no model call)` (pinned test, R-15); the fix is R-21 | reader |
| F6 | An unknown format version, or no `session.start` | **Fail closed:** not recorded | reader |
| F7 | The arithmetic check fails | **Degrade:** HB-TEL-001 `input_tokens` | reader |
| F8 | A bad bucket type | **Degrade:** `ex.count` | reader |
| F9 | Two models in one shutdown | the key includes `model` (R-26) | a synthetic two-model sample |
| F10 | A line over 1 MiB | **Accept:** counted malformed; the reader's fields are small | a synthetic 1.2 MiB `system.message` leaves the rows unchanged |
| F11 | Pack instructions not loaded | **Detect:** the section 4.5 US-9 scan and `instruction list` | W1-COP-I |
| F12 | An instruction file above the cells root | **Prevent:** HB-PRE-002 | workspace |
| F13 | An ACP permission request | **Detect:** the driver counts it (US-14) | E2E |
| F14 | No exe | **Prevent:** HB-PRE-007 | tools |
| F15 | An unknown `session.error` type | **Accept (R3)** | reader |
| F16 | **Pack hooks deny every tool call** (revision 92, O15) | **Detect and fail loud:** `outcome_code` per tool call; the exit E2E asserts 0 hook denials per Copilot cell; the report flag (R-25/R-27); the `invalid (tools denied by hook)` validity state is wave 2 | section 13, US-14 |

## Adversarial analysis (STRIDE-lite)

| Boundary | Threat | Disposition | Control | Test |
| --- | --- | --- | --- | --- |
| matrix → argv | T-1 Tampering: a model id beginning with `-` becomes a flag | accept (ADR-0012) | The matrix is operator-authored and the operator is the trust root; argv is a list, never a shell string | — |
| operator env → cell | S-1 Spoofing: a `gh` token with repository scopes becomes the cell's identity (O3) | mitigate | Drop `GH_TOKEN`, `GITHUB_TOKEN`, `GH_HOST` and `COPILOT_*` | each seeded name is absent from `cell_env` |
| cell → package cache | T-2 / E-1: a newer, unpinned binary answers (O4) | mitigate | `COPILOT_AUTO_UPDATE=false`; the exe re-hashed at every start; `agent_version` recorded (R-28) | one changed exe byte → `BuildChanged` |
| cell home → archive → reader | T-3 / D-1: a hostile or oversized `events.jsonl`, or format drift | mitigate | bounded `rows()`; the fail-closed version gate; wrong types treated as absent; no SQLite opened | reader tests F5-F10 |
| repository hooks → tool calls | E-3: a repository hook (the pack's, or a task's) silently denies or alters tool calls below ACP | mitigate (detect) | `outcome_code` per tool call; 0 hook denials asserted per Copilot cell; US-14 counts both signals | red on the revision-92 fixture |
| cell home → archive | I-1 Information disclosure: `events.jsonl` holds the prompt, replies, tool output and paths | accept (local only) | the archive stays local; HB-SEC-001 unchanged; committed samples scrubbed (section 12) | the scrub's fail-closed leak check |
| record → report | R-1 Repudiation: a served-model claim without evidence | mitigate | served ids from the native `modelMetrics` | a renamed `modelMetrics` key → HB-VAL-002 |
| agent → shell | E-2: Copilot's `shell` runs unsandboxed | accept (ADR-0013, N1.1) | the same as the other harnesses natively | — |

## Privacy analysis (LINDDUN-lite)

Personal data touched: the operator's Windows user name inside paths, and possibly account context in `events.jsonl`. The per-cell `config.json` holds no login (O6).

| Data | Finding | Disposition | Control | Retention |
| --- | --- | --- | --- | --- |
| User name in paths, account context in the cell home and its local archive | Identifiability | accept (local only) | The archive stays local; nothing new leaves the host; HB-SEC-001 unchanged | Until the owner deletes `runs/<id>` |
| The same, in the capture that becomes committed samples | Disclosure, linkability | mitigate | scrub-rule/3 (paths rewritten, identifiers replaced, opaque keys blanked, every `system.message` field except its identity digested); fail-closed leak check | Git history (scrubbed only) |
| Vendor system prompt and request bodies | Disclosure | mitigate | Digest plus marker list, as a class (section 12), with a scrub-time control. Rule 2 missed `system.message.contentBlocks`; it was re-scrubbed in `f952f87`, and the branch is squash-merged so the blob never reaches main (R-30 condition 3) | Not committed |
| What a committed sample holds | Unawareness | mitigate | `provenance.json` states the rule, the counts and the hashes | With the sample |

## 11. Capture procedure (the Leader)

Capture window 1 ran; the fixtures are `9c6c615`. The measured cost of the treatment is 528,166 tokens pack-on against 59,501 pack-off (R-14 condition 2, O19). On revision 92 it is a cost with no work done (O15).

**Now, re-scrub the committed fixtures to rule 3.** It is idempotent and in place; on any failure it restores the files and exits non-zero:

```powershell
Set-Location C:\Projects\x-harness-x-model-bench-phase2-copilot-design
uv run python tests\fixtures\native\copilot\scrub_sample.py --rescrub tests\fixtures\native\copilot
git diff --stat tests/fixtures/native/copilot      # expect the two events.jsonl files and provenance.json
$env:AGENT_SESSION = "coord-opus-cq"
git add tests/fixtures/native/copilot
git commit -m "test(fixtures): re-scrub Copilot samples to scrub-rule/3 (system.message contentBlocks digested)"
```

The re-scrub was verified in this session on a scratch copy of `9c6c615`:
- the `contentBlocks` fields were digested (off 29 KB and on 347 KB, down to 107 and 167 bytes); the pack-on file went from 415 KB to 73 KB;
- a second run changed nothing;
- `provenance.facts.*.readings.tool_outcomes` recorded `{success=False:code=denied: 8}` pack-on and `{success=True:code=None: 6}` pack-off;
- the leak check passed.

**The revision-95 capture (R-27 condition 3)** is a new capture window under R-9 rule 1. It is the same procedure as revision 1, steps 0–4, with `--pack-source` at the ai-forward commit carrying revision 95. Its pack-on sample replaces `on/` for every test except the denial negative control, which moves to `on-rev92/`. The commands:

```powershell
New-Item -ItemType Directory -Force C:\Projects\bench-capture\tools | Out-Null
npm install --prefix C:\Projects\bench-capture\tools --no-save --no-audit --no-fund "@github/copilot@1.0.89-1"
$exe = "C:\Projects\bench-capture\tools\node_modules\@github\copilot-win32-x64\copilot.exe"
uv run python tests\fixtures\native\copilot\capture_sample.py --exe $exe --model gpt-6-sol --pack-source <ai-forward clone at revision 95> --out C:\Projects\bench-capture\run --dry-run
Remove-Item -Recurse -Force C:\Projects\bench-capture\run
uv run python tests\fixtures\native\copilot\capture_sample.py --exe $exe --model gpt-6-sol --pack-source <ai-forward clone at revision 95> --out C:\Projects\bench-capture\run
uv run python tests\fixtures\native\copilot\scrub_sample.py --capture C:\Projects\bench-capture\run --dest <scratch folder>
# then move <scratch>/on to tests/fixtures/native/copilot/on after `git mv on on-rev92`, commit, and remove C:\Projects\bench-capture
```

## 12. Scrub rule (scrub-rule/3)

Rule 2, plus:
- **Every `system.message.data` field except `role` and `interactionId` is digested** (`<scrubbed sha256=… chars=… markers=[…]>`; a non-string value is digested as canonical JSON). Rule 2 digested only `content` and missed `contentBlocks`.
- `user.message.transformedContent` is digested; `user.message.content` stays (US-10).
- A value already digested is left as is, so the rule is **idempotent**.
- The provenance readings add `tool_outcomes` (`success` × `error.code`).
- **`--rescrub <fixture folder>`** re-applies the rule in place and refreshes the output and script hashes. It records `rescrubbed_from` (the original rule) and restores every file on failure.
- The forbidden set, path rewriting, dropped event types, blanked keys and the fail-closed leak check are unchanged from rule 2.

**The vendor-system-prompt class (R-30 condition 3).** Any field carrying harness-injected prompt text (a vendor system prompt, injected context, instruction bodies) is digested **as a class**, not field by field. The control is in the script: after writing, every `system.message.data` field except `role` and `interactionId` must be a digest string, or the scrub fails closed. A field the harness adds later cannot slip through as `contentBlocks` did.

**Why `--rescrub` (Simplifier N6).** The raw capture is deleted once it has been scrubbed, because it holds unscrubbed records. A scrub-rule fix therefore has to be applicable to the committed samples without a new capture window.

## 13. Test plan: promise → test

| Promise | Test (owner, file) | Red first against |
| --- | --- | --- |
| **US-9** (the proof) | Build the pack-off X1 copy through the real workspace builder (`task_source` → `cell_working_copy`). Scan every Copilot instruction path (section 4.5 plus nested `AGENTS.md`/`CLAUDE.md`/`GEMINI.md` and `.github/instructions/**`) and `prompt.md` against `bench/pack-markers.txt`: no marker. The pack-on copy (`+ install_pack`) matches at least one marker (the positive control) (W1-COP-I, `tests/test_workspace.py`). The live check: `instruction_list` returns `[]` on the pack-off copy, and `bench plan` refuses a non-empty pack-off list (one `native` test, W1-COP-I) | a pack-off copy seeded with a marker in `.github/copilot-instructions.md` |
| Fixture provenance check (**not a US-9 proof**) | Provenance: pack-off `system.message` digest `markers=[]`; pack-on all three (W1-COP-R) | — |
| **US-14 for Copilot** (R-27 c2) | A valid cell has **ACP permission requests == 0 AND native hook denials == 0**. The reader records `outcome_code` on each `tool_calls` row (W1-COP-R): the rev-92 pack-on sample (the negative control) yields 8 rows with `outcome_code == "denied"` and `ok == 0`; pack-off yields 6 with `ok == 1` and `outcome_code` null. **The wave-1 exit E2E asserts zero hook denials per Copilot cell, reading `tool_calls.outcome_code` from the ledger rows (`views.rows`), not from an in-memory `Extraction` (D&P C-d)**; it is red on the rev-92 fixture. **Positive control (R-27 c1):** the exit E2E also asserts that every revision-95 pack-on Copilot cell has at least one `tool_calls` row with `ok == 1`. A cell with zero tool calls fails this assertion, and does not pass the zero-denial assertion by default. No pack-effect figure is reported for a combo whose cells fail it. **Both checks are one named assertion function** used by the exit E2E. A unit test applies it to the rev-92 `on-rev92/` sample and observes it fail, and to `off/` and observes it pass (W1-COP-R). The argv equals the section 4.3 list and contains none of `--allow-all*`, `--yolo`, `--assisted-approval`, `--autopilot`, `--resume`, `--continue`, `--connect`; `mode` is never `autopilot` (W1-COP-I). The `invalid (tools denied by hook)` validity state is a wave-2 row (R-15, R-27) | the rev-92 fixture; a profile with `--allow-all-tools` |
| **US-10** | `first_user_text` passes the spec's US-10 normaliser, then its sha256 == `802dfde4…` for both arms. A synthetic sample where `content` ≠ `transformedContent` returns `content`. A **synthetic sub-agent-first sample** (a `user.message` with a top-level `agentId` before the main one) returns the main one's `content`. A **synthetic sample with a later second main `user.message`** returns the first (W1-COP-R) | each synthetic sample |
| **US-11** clauses 1-3 | Driver: `set_model {sessionId, modelId}` precedes `session/prompt`, only when `model=`; `-32602` → HB-CELL-116 with no prompt (W1-ACP). Reader and views: a sample where **only the key under `session.shutdown.data.modelMetrics`** is renamed (`currentModel`, `selectedModel` and every `assistant.message.model` untouched) → views validity `invalid (model mismatch)`. A second mutation empties `modelMetrics` → `invalid (no model call)` (W1-COP-R, through `views.load`) | the unmutated sample must stay `valid` |
| **US-11** clause 4 | Two Copilot combos with different models in one plan: each cell's argv carries its own `--model` and its `set_model` its own `modelId` (profiles argv test plus a driver test over a fake agent that records the ids) (W1-COP-I, W1-ACP) | one shared model id |
| **US-12** | `tools.resolve` on a fake tools folder: Copilot `Build` with `adapter None`, the version from the win32 `package.json`, the exe sha256; one changed byte → `BuildChanged`; missing → HB-PRE-007. `COPILOT_AUTO_UPDATE=false` asserted as profile data (R-12 c3) (W1-COP-I). E2E: `build_sha256 ==` planned. `agent_version` recorded on `attempt.session_opened`, null when absent (W1-ACP, R-28) | `LAYOUT` without Copilot |
| R-12 c1 | The report header names `copilot 1.0.89-1 (prerelease)` (report test on a fixture ledger) | a header without the mark |
| R-12 c3 | The wave-1 X1 run: the Copilot `build_sha256` on the first and the last Copilot cell's `attempt.process_started` are identical (the exit E2E) | — (a run observation) |
| R-13 c2 | `ProfileLauncher.credential_kind` is `subscription login (credential store)` for Copilot and `subscription login (copied)` for Claude Code and Codex; the engine writes the launcher's value (W1-COP-I profile test; W1-ACP engine test) | the engine's constant string |
| **US-13** clause 1 | The Copilot canary (R-16; W1-COP-I, `tests/e2e/test_us13_canary.py`): **four classes** in the control home: `copilot-instructions.md` (instruction), `skills/<name>/SKILL.md` (skill), a user-level hook that writes a marker file (hook), and `settings.json` `model` (settings). The control must show each canary; the probe shows none; a class the control does not show is **void for Copilot** and reported | the control with each class removed in turn |
| **US-13** clause 3 | A fake agent answering `session/new` with `-32000 Authentication required` (the R11.3 shape), or refusing `set_model` for auth → `blocked (auth)`, with no `session/prompt` written (W1-ACP) | red against the pre-R-23 driver (`094b27d`, `driver.py` on main), where an auth error at `session/new` or `set_model` maps to `handshake_timeout` or `adapter_crash`, not `blocked_auth`. W1-ACP has since landed R-23 on its branch; the red is re-run on `094b27d` |
| US-13 env | `cell_env` sets `COPILOT_HOME` and drops `GH_TOKEN`, `GITHUB_TOKEN`, `GH_HOST`, `COPILOT_CUSTOM_INSTRUCTIONS_DIRS`, `COPILOT_MODEL`, `COPILOT_ALLOW_ALL` (W1-COP-I) | each name seeded |
| R-14 c1 | Per Copilot cell the report carries: `hook_starts` and `hook_failures` (the only new reader output, `Extraction`); hook-denied tool calls and skill calls requested, **derived from `tool_calls`** (`outcome_code == "denied"`, `name == "skill"`; there is no `skill.invoked` event type, O18); and instruction files loaded (the `bench plan` datum, section 4.5). Reader test: off hook pair 0/0; rev-92 on 8/8; derived off 0 denied / 0 skill, rev-92 on 8 / 2 | a missing count |
| Tokens (ADR-0008) and grain (R-26 C3) | Per arm (rev-92 `on/` until the rev-95 capture; then `on/` = rev-95 and rev-92 moves to `on-rev92/`, per R-27 c3): one row for `gpt-6-sol`, `requests` == 5 (off) / 6 (on), `start`/`end` null; off buckets 15 / 46,801 / 12,170 / 515, reasoning 166. **The golden-sample cross-check:** Σ(uncached, cache_read, cache_write, output) == ACP `usage.totalTokens` (off 59,501); reasoning is a component of output and is not added. The Claude Code and Codex readers yield `requests == 1` on every row. Views: `calls_per_cell` == Σ `requests`; a two-request single-row fixture yields 2 (W1-COP-R; the guard is W1-COP-I) | `uncached = inputTokens` |
| F5 / R-15 pin | A sample with the shutdown line removed: HB-TEL-001 `session.shutdown`, no rows, and views validity **`invalid (no model call)` in wave 1**. The test cites R-15 and R-21 so the wave-2 change flips a known assertion | — |
| Reader bounds | F6 (`version: 2`; no `session.start`); F7 (arithmetic mismatch); F8; F9 (a synthetic **two-model** shutdown → two rows, distinct keys by `model`, one `native_ordinal`); F10 (a synthetic 1.2 MiB `system.message` line: rows unchanged, `malformed_lines == 1`); D2 (a fuzzed `events.jsonl` never crashes and never yields a partial row) | each branch |
| Mutation | **`tests/mutations/copilot_reader.json`** (W1-COP-R). Each mutant must be killed by a named test: uncached = `inputTokens`; first instead of last `session.shutdown`; the model taken from the pin or `currentModel`; the version gate removed; reasoning dropped; cache read and write swapped; `content` → `transformedContent`. It needs synthetic samples for **first vs last shutdown** (two shutdowns with different totals) and **first vs later `user.message`**. `tests/mutations/copilot.json` (W1-COP-I): one entry per new branch in `profiles`, `tools`, `errors` and `workspace` | — |
| Registry | `HARNESSES` == `READERS` keys == `LAYOUT` keys == profile stems (W1-COP-I) | a missing reader |
| HB-PRE-002 | One test per new name, and for the folder rule, in the cells root and in an ancestor; an empty `.github/instructions` is allowed (W1-COP-I) | each |

Testing Strategy directives:
- **D0:** ruff and no dead code (HYG-A: `store_readings` is deleted).
- **D1:** unit tests plus the two mutation files.
- **D2:** property tests.
- **D4:** real files, the real workspace builder, and the live `instruction list`.
- **D6:** the golden samples (rev-92 as the negative control; rev-95 once captured).
- **D7:** `session/set_model` paired with the capture-window-2 recording (W1-ACP).

## 14. Telemetry

- No new event types. `acp_usage` (R-24) and `agent_version` (R-28) are new attributes on existing events (W1-ACP).
- `tool_calls.outcome_code` and `model_calls.requests` are new columns (ADR-0006 Amendment 1).
- Degradation is visible as HB-TEL-001 `MissingField` names.

## 15. Open items

**Ruled (closed):**
- Q1 and Q2: ruled R-12.
- Q3 and Q9: ruled R-13.
- Q4: ruled R-14, R-25, R-27.
- Q5 and Q6: ruled R-15.
- Q7 and Q8: ruled R-16.
- Q10: ruled R-26 (R-20 withdrawn).
- Q11: ruled R-21.
- Q12: ruled R-22 / R-28.
- Q13: ruled R-18 / R-23.
- Q14: ruled R-24.

**Open:**

| # | Item | To | Recommendation |
| --- | --- | --- | --- |
| O-1 | closed: ruled R-30 (typed `Launcher` fields; section 4.3) | — | — |
| O-2 | closed: re-scrubbed in `f952f87`; the Leader squash-merges this branch so `9c6c615`'s blob never reaches main (R-30 condition 3; the join record cites the squash commit) | — | — |
| O-3 | Ownership outside the listed paths: `normalize.py` (`requests`, `outcome_code`; W1-COP-R), `views.py` (key, row mapper, `calls_per_cell`, guard; W1-COP-I), `plan.py` (the `instruction_list` datum; W1-COP-I), `telemetry/__init__.py` (`ModelCall.requests`, `Extraction.hook_*`; W1-COP-R) | Leader | add them to the tracks' owned lists |
| O-4 | closed: decided in section 4.5 (`bench plan`, one function; Simplifier N3). Ownership is in O-3 | — | — |
| O-5 | The revision-95 capture window (R-27 condition 3) | Leader | after W1-PACK-2 lands upstream |

## 16. Flagged risks and residuals

- **R1:** an unreadable record reads `invalid (no model call)` until the wave-2 state (R-15).
- **R2:** the shared `%LOCALAPPDATA%\copilot` caches are not measured.
- **R3:** `session.error` shapes are not observed.
- **R5:** URL permission prompts may be Copilot-only.
- **R7:** there are no tokens without a routine shutdown; the fix is R-21, W2-STOP.
- **R8:** `assume:` the top-level `modelMetrics` sums every agent. Only `agentMetrics.main` was seen.
- **R9:** the revision-92 pack-on Copilot arm is not a treatment (R-27). No pack-effect figure is reported until a revision-95 cell shows at least one successful tool call.
- **R10 (new):** a task's own repository hooks, not only the pack's, could deny tools below ACP. `outcome_code` makes that visible in any cell, and the zero-denial assertion then fails loud.

## 17. Conformance notes

- ADR-0003 (the pin), ADR-0006 (Amendment 1, written here), ADR-0008 (native records), the token-source note (corrected here), ADR-0013.
- There is no remaining deviation. The revision-2 grain deviation is replaced by the amendment (R-26).

## 18. Gate record: dispositions for revision 3

The gate on `7f2a7c1`:
- Test Architect: **BLOCK** (hard veto);
- Simplifier: soft BLOCK;
- Patterns Expert: PASS WITH CONDITIONS;
- Data & Persistence Architect: PASS WITH CONDITIONS.

| Finding | Disposition |
| --- | --- |
| TA Blocker (a) §4.5 treatment facts | **Applied** (section 4.5: the hooks deny every tool, no tool runs, skills are requested and not loaded) |
| TA (b) O15, F16 | **Applied** (O15 "tool calls requested…; on: all denied"; F16 "Detect and fail loud") |
| TA (c) R-27 row: `outcome_code`, zero-denial E2E red on rev-92, US-14 = both counts, wave-2 validity | **Applied** (section 13, US-14 row; ADR-0006 names `outcome_code`) |
| TA Major: US-9 native row relabelled; the US-9 proof through the real builder plus `instruction list` `[]`; the runtime scan synthetic or "not measured" | **Applied** |
| TA Major: US-11 renamed only under `modelMetrics`, through views; an emptied `modelMetrics` → no model call | **Applied** |
| TA Major: US-13 four classes including a hook marker file; a class not shown is void | **Applied** |
| TA rows: US-11 c4, US-13 c3, R-12 c1, R-12 c3, R-13 c2, R-14 c1 | **Applied** (R-14 c1 names its sources; there is no `skill.invoked`) |
| TA mutation file and synthetic samples | **Applied** (`copilot_reader.json`, W1-COP-R) |
| TA minors: the Σ = `totalTokens` wording; ACP usage as the oracle; the `agentId` `assume:` plus the sub-agent test plus the normaliser; a synthetic > 1 MiB line; the wave-1 no-shutdown pin citing R-15 | **Applied** |
| D&P C1–C3, the key rule, ADR-0006 and note ownership | **Applied**: ADR-0006 Amendment 1 and note line 40 written in this revision; key = `model` added; the docstring and `requests` go to W1-COP-R, and the views key/compute reader/guard to W1-COP-I |
| Simplifier F1: collapse the probe | **Applied**: 1 static (the US-9 scan) + 1 live per-cell signal (the reader's hook and denial counts); `system.message` markers cut. "Instruction files loaded" is not in `events.jsonl`, so `instruction list --json` is its source, once per (task, pack, build), with an `assume:` |
| Simplifier F2 | **Superseded** by R-26's key rule (no packed ordinal) |
| Simplifier F3 | **Overruled** by R-28; `agent_version` kept, narrowed |
| Simplifier F4 | **Applied**: `store_readings`, `USAGE_COLUMNS` and the `sqlite3`/`tempfile`/`shutil` imports deleted from `capture_sample.py` |
| Simplifier F5 | **Applied**: answered questions read "ruled: R-nn"; owners set in section 6 |
| PE: `set_model` as a typed Protocol field, no `getattr` | **Applied per R-30** (the author's R-13 defence is withdrawn) |
| PE: `acp_usage` at runtime; the wave-2 view check; the golden-sample cross-check | **Applied** |
| PE: name the version gate, and why only Copilot | **Applied** (section 4.4) |
| PE: `credentials: []` Null Object; `credential_kind` in YAML | `credential_kind` **applied**; the Null Object is **reverted** in 3.1 (Simplifier N1: `credential: null`, with no correctness reason for a list) |
| PE: `command:` template, or an optional None-guarded component | **Both, by place:** a `command:` template in profile data, where the adapter branch moves into the template filler, is not removed, and leaves `argv` itself branch-free (Simplifier N2); and the adapter as an optional None-guarded component in `tools.resolve` only |
| PE: the registry-consistency test | **Applied** |
| PE: the tool-class dict with the Correlation Identifier | **Applied** |
| PE: `set_model` errors mapped by step through R-23's classifier | **Applied** (section 4.3) |
| New in revision 3: scrub-rule/2 left `system.message.contentBlocks` (the vendor system prompt) in `9c6c615` | **Fixed:** scrub-rule/3 plus `--rescrub`, re-scrubbed in `f952f87`; the class and its script control are in section 12 (R-30 c3); squash-merge at the join |

The author does not self-clear. The Test Architect's veto and the Simplifier's soft veto are re-reviewed at the join.

**Revision 3.1 (the conditions on `b260dd1`/`f952f87`; all three lenses cleared their vetoes):**

| Condition | Disposition |
| --- | --- |
| TA Major: US-14 positive control (R-27 c1) | Applied (section 13, US-14 row) |
| TA Minor: one named assertion function, unit-tested on `on-rev92/` (fails) and `off/` (passes) | Applied (US-14 row) |
| TA Minor: US-13 c3 red against the pre-R-23 driver | Applied (`094b27d`) |
| TA Nit: the tokens/grain row sample note | Applied |
| D&P C-a: `requests.count` struck from "stays in provenance" | Applied (section 3; the R-20 c4 narrowing goes to the Owner) |
| D&P C-b: the `requests` default in one mapper | Applied (section 3, W1-COP-I) |
| D&P C-c: key widening before the first two-model cell | Applied (sections 3 and 6) |
| D&P C-d: the zero-denial assertion reads ledger rows | Applied (US-14 row) |
| Simplifier N1: revert to `credential: null` | Applied; the misattributed "Simplifier's acceptance" line is removed |
| Simplifier N2: the "fewest branches" wording | Applied (the branch moved into the template filler) |
| Simplifier N3: one `instruction_list` function run by `bench plan` | Applied (section 4.5; `plan.py` ownership in O-3) |
| Simplifier N4: derive denial and skill counts from `tool_calls`; name the hook pair's home | Applied (`Extraction.hook_starts` / `hook_failures`) |
| Simplifier N6: `--rescrub` rationale | Applied (section 12) |
| R-30 c3: the vendor-system-prompt class in section 12 | Applied, with a fail-closed script control |

## 19. Status

| | |
| --- | --- |
| **Completed** | Revision 3: every gate finding applied or defended (section 18); ADR-0006 Amendment 1; the token-source note corrected; scrub-rule/3 with `--rescrub`; the dead SQLite code deleted |
| **Remaining** | the join (squash-merge, citing the commit, R-30 c3); O-3 and O-5; the revision-95 capture; W1-COP-I, W1-COP-R, W1-ACP |
| **Best next action** | Re-review of revision 3 at the join (Test Architect, Simplifier), then dispatch W1-COP-I and W1-COP-R |
