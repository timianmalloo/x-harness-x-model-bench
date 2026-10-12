---
id: "adr-0028-copilot-prompt-mode-transport"
title: "ADR-0028: Copilot cells run copilot -p behind a pinned local ACP adapter, so long_context applies and the engine stays on ACP"
type: adr
status: draft
owner: "@timianmalloo"
phase: "Lean re-run at equal reasoning (operator 2026-10-12)"
tags: [benchmark, transport, copilot, context-window, settings, adapter]
links:
  - { to: arch-lean-rerun, rel: refines }
  - { to: adr-0024-combo-settings-and-served-read-back, rel: depends-on }
  - { to: adr-0025-transport-seam-grok-and-agy-cells, rel: refines }
  - { to: rulings-register, rel: depends-on }
review-by: "2027-04-12"
summary: >-
  Ruling 120 supersedes Ruling 118: both Copilot combos run copilot -p, the only mode in which the pinned 1.0.89-1
  applies --context long_context (922,000 prompt tokens). A small local adapter, bench/adapters/copilot_p_acp.py,
  serves minimal ACP on stdio and runs copilot -p once per prompt (--session-id, then --resume), the way codex-acp
  wraps Codex. The engine, the ACP driver, the lifecycle model and the views stay unchanged: one process per attempt.
  The adapter is pinned by sha256 in tools.LAYOUT. A spike comes first.
---

# ADR-0028: Copilot cells run `copilot -p` behind a pinned local ACP adapter

- **Status:** Proposed (revised at the plan gate, 2026-10-12: veto A, one process per turn broke the lifecycle
  model; replaced by an adapter)
- **Date:** 2026-10-12
- **Deciders:** @timianmalloo (Ruling 120); authored by the Leader seat (Claude Code, Opus).
- **Context:** Ruling 118 (superseded); `docs/architecture-lean-rerun.md`; the 2026-10-11 settings spike
  (`C:\tf\spike-settings\copilot\home-p`) and the ACP context probe (`copilot_tier_probe.py`).

## Context

- Under ACP, Copilot 1.0.89-1 and 1.0.92-4 serve 272,000 whatever the knob (Verified; Ruling 118).
- In `-p` mode, `--context long_context` sets `session.start.contextTier = "long_context"` (Verified, settings
  spike). Copilot's model API lists the tier at `max_prompt_tokens` 922,000 and `max_context_window_tokens`
  1,050,000 (Verified, the spike's process log).
- `copilot --help` (1.0.89-1, Verified 2026-10-12): `-p, --prompt <text>`; `--output-format json` (JSONL);
  `--session-id <id>`; `-r, --resume [<id>]`; `--available-tools`, `--allow-tool`, `--deny-tool`;
  `--allow-all-tools` ("required for non-interactive mode"); `--no-ask-user`; `--disable-builtin-mcps`;
  `--log-level`, `--log-dir`.
- The engine's lifecycle allows one process per attempt: `cell.prompt_sent` must come before
  `attempt.process_ended` (`lifecycle.py:69-74`), `views.py:559` keys a cell's events by kind, and
  `models/run_lifecycle.tla` models one start per attempt (Verified at the plan gate). One process per turn would
  break all three.
- The bench already runs harnesses behind ACP adapters it pins: `claude-agent-acp`, `codex-acp`
  (`bench/tools/package.json`; `tools.LAYOUT` adapter version and sha256).

## Decision

1. **A local ACP adapter, `bench/adapters/copilot_p_acp.py`** (stdlib Python, outside `src/`). It serves the ACP
   subset the driver uses: `initialize`, `session/new` (it chooses a UUID and returns it as the session id),
   optional `session/set_model` (it records the model; the model is also in argv), `session/prompt`,
   `session/cancel`. For each `session/prompt` it runs one `copilot -p` process: the first with
   `--session-id <uuid>`, later ones with `--resume <uuid>`. It waits for exit, then answers the prompt with
   `stopReason` `end_turn` (exit 0 and a final result object), `cancelled` (after `session/cancel`, which kills the
   child) or `refusal`-free incomplete (any other exit), and the final object's usage, if any, as `usage`. It sends
   no permission requests.
   - The engine's process is the adapter; its job contains the Copilot children, so containment, peak memory and CPU
     are measured as today (Inferred from `procs` job semantics; the spike checks the job's peak covers the child).
   - **Nothing in the engine, the driver, `lifecycle.py`, the TLA model or the views changes.**
2. **Pinning.** `tools.LAYOUT`'s Copilot entry gains the adapter: the file's path, its version constant, and its
   sha256, checked at every cell start (`check_build`, HB-CELL-115), as for `codex-acp`. The adapter spawns the
   pinned Copilot exe, with `COPILOT_AUTO_UPDATE=false`.
3. **Argv.** The profile: `["{python}", "{adapter}", "--exe", "{exe}", "--", "--output-format", "json", "--model",
   "{model}", "--reasoning-effort", "{effort}", "{context_arg}", "--available-tools", …, "--allow-tool", "shell",
   "--allow-tool", "write", "--no-ask-user", "--disable-builtin-mcps", "--log-level", "debug", "--log-dir",
   "{home}/logs"]`. `{python}` is the bench's interpreter. `{context_arg}` comes from the profile's settings map:
   `default` → nothing, `922000` → `--context long_context`. The adapter adds `-p <text>` and `--session-id` or
   `--resume` per prompt.
4. **Record.** The native record stays Copilot's session record and debug log (`record_glob` unchanged; the bench
   reads the session id the adapter returned). The adapter tees each prompt's stdout JSONL, unchanged, to
   `<cell home>/copilot-p-turn<k>.jsonl`. ACP `usage_update` messages do not exist on this path, so Copilot's served
   context is judged by `session.start.contextTier` (§5). If the final JSONL object carries no usage, HB-VAL-005's
   cross-check reads `not recorded` for these cells, never a false warning.
5. **Settings.** Copilot's `settings.context` supports `default` (serves 272,000) and `922000` (`--context
   long_context`), judged by `served.context_tier == "long_context"`; the token count is recorded where a record
   carries it. Both Copilot combos pin `context: 922000`.
6. **Spike first** (R-COPILOT-P's first output, `C:\tf\r-copilot-p`, one X1 turn per question):
   - does `--available-tools` plus `--allow-tool` run non-interactively **without** `--allow-all-tools`, and does an
     unlisted tool stay unavailable? If `--allow-all-tools` is required, is the toolset still limited to
     `--available-tools`? If neither holds, a decision request to the operator before the profile freezes;
   - does `--resume <id> -p <text>` continue the same session for a second turn (RW1, RW2)?
   - does `gpt-5.6-sol-fast` get `contextTier = "long_context"`?
   - is any task prompt longer than the Windows command-line limit (32,767 characters)?
   - does the final JSONL object carry usage? Does the engine's job peak memory include the child?
7. **Scripted-user tasks.** The ACP path appends scripted-user MCP args for Copilot (`profiles.py:136-145`). The lean
   tasks use none. A profile flag `scripted_user: unsupported` makes the plan refuse such a task with a named code,
   until a spike shows the MCP wiring works in `-p` mode.

## Consequences

- Copilot runs at a 922k-token prompt window, close to Claude Code's 1M and Codex's 872k.
- Copilot is driven in `-p` mode, unlike the 2026-10-10 run and the other four harnesses. Both reports show each
  combo's transport beside its numbers (a plan fact, ADR-0027 and ADR-0029).
- The bench owns one more adapter, pinned and tested like the npm adapters.

## Alternatives considered

- **One process per turn in the engine** (this ADR's first draft). Rejected at the plan gate (veto A): it breaks
  `lifecycle.py`'s conformance, the views' event keying and the TLA model.
- **Keep ACP at 272k** (Ruling 118): superseded by the operator.
- **An ACP adapter on the Copilot SDK** (`copilot-sdk/types.d.ts:1933`, in 1.0.92-4): rejected: a pin bump and a
  larger adapter.
