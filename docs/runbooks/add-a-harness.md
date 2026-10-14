---
id: runbook-add-a-harness
title: "Runbook: add a harness the bench has never run"
type: doc
status: draft
owner: "@timianmalloo"
tags: [runbook, harness, onboarding, profile, telemetry, adapter, lean-benchmark]
links:
  - { to: adr-0025-transport-seam-grok-and-agy-cells, rel: depends-on }
  - { to: adr-0028-copilot-prompt-mode-transport, rel: depends-on }
  - { to: adr-0024-combo-settings-and-served-read-back, rel: depends-on }
review-by: "2027-04-13"
summary: >-
  A harness is its own files: a profile, a build entry, a pin, a reader module and, for a CLI that does not speak
  ACP, a small adapter. No list in the bench code names harnesses. This runbook is the contract the lean prompt's
  onboarding stage follows, and the qualification gate a new harness passes before its numbers count.
---

# Add a harness the bench has never run

A harness is registered by its files. Nothing in `src/` lists harness names:

| File | What it is | Found by |
|---|---|---|
| `bench/profiles/<name>.yaml` | How to seed a cell's home, launch the CLI, pin model/effort/context, and where its session record lands | `config.harness_names`: one harness per profile file |
| `bench/tools/builds.yaml`, entry `<name>` | Where its pinned build lives under `.tools/` | `tools._layout` |
| `bench/tools/vendored.json`, entry `<name>` | `{version, sha256}` of the exe (vendored route) | `tools.install_vendored`, `tools.resolve` |
| `src/harness_bench/telemetry/<name with - as _>.py` | `read(path) -> Extraction`: tokens, served model, tool calls, errors from the native record | `profiles.reader_for` (by module name) |
| `bench/adapters/<name>_acp.py` + `<name>_acp.pin.json` | Only for a CLI that does not speak ACP: a stdlib ACP shim over its headless mode | `adapter_pin` in its builds.yaml entry |
| `tests/test_reader_<name>.py` | The reader's tests, on a real recorded session | pytest |

`tests/test_harness_registry.py` and `tests/test_profiles.py` fail until every profile has its reader, its build
entry and, for a vendored exe, its pin.

## 1. Spike the CLI (measure; do not guess)

Answer each question by running the CLI, and keep the evidence (command, output excerpt) for the note in step 4:

1. **Headless mode.** How does it run one prompt without a TTY? How does a second prompt continue the same
   session (the bench sends several turns per cell)? Does it speak ACP (JSON-RPC 2.0 over stdio:
   `initialize`, `session/new`, `session/prompt`)?
2. **Session record.** Where does it write the session transcript, relative to which home variable? The profile's
   `home_env` points that variable at the cell's own home; `record_glob` finds the file there.
3. **Usage.** Which record field carries, per model call: model id, uncached input, cache read, cache write, output,
   reasoning tokens? Is there an **independent** usage report (an export, trace or stats command, or a final usage
   event) to cross-check the reader against?
4. **Settings.** The flags or config keys for model, effort and context window, and the values it accepts. Where
   does the record show what was *served*?
5. **Permissions.** How to make it never ask (the bench answers every permission request `cancelled`): static
   allow rules for shell, file read, file edit; deny web and MCP.
6. **Login.** Where its credential lives. Does a cell copy it, or read a shared store? Does it rotate on use (then
   cells run one at a time: `harness_parallelism: {<name>: 1}` in the matrix)?
7. **Leaks.** Which environment variables it reads (its home, keys, config), and which files it loads instructions
   from (like `AGENTS.md`, `.grok/`).

## 2. Write the files

- **Profile.** Copy the closest existing profile and change it. Required keys: `harness`, `vendor`, `home_env`,
  `credential` (or `null`), `command`, `record_glob`, `shutdown_grace_seconds` (0 to 10). Set `transport: acp`.
  Set `usage_source: native_record` (the reader supplies usage). Set `scripted_user: unsupported` unless it accepts
  MCP servers on `session/new`. Declare `settings.effort` and `settings.context` with the values it accepts. Add
  the two isolation keys:
  ```yaml
  drop_env: ["MUSE_*", "META_API_KEY"]          # names, or prefixes ending in *; dropped from EVERY harness's cells
  instruction_paths:
    files: ["MUSE.md"]                           # exact paths an agent loads instructions from
    trees: [".muse"]                             # folders whose every file is an instruction file
  ```
  If the CLI loads operator-level files from the user home, set `user_home_vars: [HOME, USERPROFILE]` (Grok, agy), and
  then check a real record: Codex finds `~/.agents/skills` through the Windows known folder, so the variables did not
  hide it; its profile lists `host_skill_roots` instead (each skill file there is disabled in the cell config).
  Since 2026-10-14 (instr/w16, owner decision) Copilot sets `user_home_vars` too, so its environment now differs from
  Claude's and Codex's: a harness that denies paths outside its allowed directories also needs the cell home allowed
  (`--add-dir {home}`), or `$env:USERPROFILE` is still refused. Leave `APPDATA`/`LOCALAPPDATA` alone (uv's Python store).
- **Build.** Vendored route (an installed exe): add `<name>: {exe: "<file name>{suffix}"}` to
  `bench/tools/builds.yaml`, add `{version, sha256}` of the exe to `bench/tools/vendored.json`, then
  `uv run bench tools install --vendored <path to the exe>`. Pin the real binary, not a `.cmd` or `.ps1` launcher.
- **Adapter** (only when the CLI does not speak ACP). Follow `bench/adapters/copilot_p_acp.py` (ADR-0028): a
  stdlib ACP server that runs the CLI's headless mode once per `session/prompt`, resumes the session for later
  turns, and tees each turn's output into the cell home. Pin it in `<name>_acp.pin.json` and name the pin in its
  builds.yaml entry as `adapter_pin`. The profile command is then `["{python}", "{adapter}", "--exe", "{exe}", ...]`.
- **Reader.** `src/harness_bench/telemetry/<name>.py` with `read(path) -> Extraction` (`telemetry/__init__.py`):
  one `ModelCall` per model request (`model`, `uncached_input`, `cache_read`, `cache_write`, `output`,
  `reasoning` or `None`), one `ToolCall` per tool call with its class from a static `TOOL_CLASS` map (`shell`,
  `edit`, `read`, `meta`, `delegate`; anything unmapped is `other`, and makes the cell invalid, HB-VAL-008), every
  provider error, and `served` (`ServedSettings`, with `sources` naming the record field each value came from).
  A field the record lacks is `MissingField` or `not_recorded(<reason>)`, never 0 and never a guess. Bound every
  read: the existing readers show the line and depth limits.
- **Tests.** Red first. Use a short real session record (secrets and personal data removed) as the fixture, and
  assert the exact token counts the independent usage report showed.

## 3. Qualify (the gate before any number counts)

All of these must hold. Any one failing is a stop, not a warning:

1. `uv run pytest -q` is green, including `tests/test_harness_registry.py`.
2. **A probe run.** One task (`S1`), one repetition, both arms: `bench plan`, `--confirm`, `run`, `verify`. Every
   cell is valid. No HB-VAL-001 (no model call), 002 (model mismatch), 008 (tool outside the profile) or 010
   (served setting differs from the pin).
3. **Token cross-check.** For one probe cell, the reader's totals equal the CLI's own independent usage report for
   that session, exactly, per bucket. Record both sets of numbers. If the CLI has no independent report, the
   numbers are labelled **Inferred** in every report, and the note says why.
4. **Served read-back.** The served model, effort and context come from the record (their `sources` name the field),
   not from the plan.

## 4. Record

Write `docs/notes/harness-<name>.md`: the build version and sha256, the spike's answers with their evidence, the
cross-check numbers, and anything not recorded and why. Commit everything on the run's branch with the message
`feat(harness): onboard <name> <version>`.

## Never

- Edit another harness's files, or the engine, driver, views or grading code, to make a new harness pass. A new
  harness that needs such a change is a finding for the operator, not something to patch on the way.
- Copy a credential into the repository, or print a token.
- Weaken a test, a validity code, or the cross-check to get a green result.
