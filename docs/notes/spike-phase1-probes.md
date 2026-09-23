---
id: "note-spike-phase1-probes"
title: "Phase-1 probes W1, W3, N4: pack install, provider-error rows, job containment"
type: doc
status: draft
owner: "@timianmalloo"
tags: [benchmark, spike, phase-1, pack, telemetry, job-object]
links:
  - { to: design-phase1-walking-skeleton, rel: refines }
  - { to: adr-0013-native-cells, rel: refines }
review-by: "2026-10-23"
summary: >-
  W1: pack-apply.py apply --install installs pack revision 92 non-interactively in under a second and
  lists every path it wrote as JSON (437 files). W3: a failed Claude call is an assistant row with
  isApiErrorMessage, apiErrorStatus and error, model "<synthetic>" and zero usage; Codex reports a bad
  model as ACP complete with task_complete.error. N4: no harness process leaves its cell's Job Object,
  the job handle is not inheritable, and nothing survives TerminateJobObject.
---

# Phase-1 probes W1, W3, N4

Date: 2026-09-23. The Windows 11 workstation. Adapters from the pinned lockfile (`claude-agent-acp` 0.79.0, `codex-acp` 1.12.0); Codex CLI 0.156.0; Copilot CLI on PATH. Code (gitignored): `spikes/runner-path/w3_probe.py`, `n4_probe.py`. Probe folders were under `C:\Projects\bench-probe-*`. Afterwards 0 credential copies remained, and the folders were deleted. Labels: **Verified** means run here.

## W1: install the pack into a task directory [Verified]

- **Command:** `python C:\Projects\ai-forward\pack\scripts\pack-apply.py apply --source C:\Projects\ai-forward --target <fresh git repo> --install --no-baselines --json --project probe`, with stdin closed.
- **Source:** ai-forward `ca032f007b33e4424e50c04c5b2a2bd43f766c78` (one untracked log file, not part of the pack).
- **Result:** exit 0, under 1 s, `source_revision: 92`. 437 files added:
  - `docs/ai-forward-pack/` (91);
  - `.claude/`, `.agents/` and `.grok/` skills (52 each);
  - `.claude/knowledge` (40);
  - `.github/{prompts, agents, knowledge, instructions}`;
  - `.claude/agents`, `.grok/agents`;
  - `docs/index.html`, `CLAUDE.md`, `AGENTS.md`, `.grok/rules`.
- **For the design:**
  - The `--json` rows (`area`, `path`, `action`, `status`) are the pack delta US-9 compares against: `pack=on` is the base plus exactly these paths.
  - The installer that ships with the clone is `pack/scripts/pack-apply.py`, not `scripts/`.

## W3: provider and model errors in native records [Verified]

**Claude Code**, with `ANTHROPIC_MODEL=claude-nonexistent-9`:
- The ACP transport returns `failed` / `remote_error`.
- The native record holds one assistant row:
  - `"type": "assistant"`, `"isApiErrorMessage": true`, `"apiErrorStatus": 404`, `"error": "model_not_found"`;
  - `message.model = "<synthetic>"`, all usage fields 0;
  - `message.content[0].text` is a human-readable explanation.

**Codex**, with `model = "gpt-nonexistent-9"` in `config.toml`:
- The ACP transport returns **`complete`** (stop reason absent).
- The rollout holds `event_msg` / `task_complete` with `error.message`, which embeds `{"type":"error","status":400,"error":{"type":"invalid_request_error","message":"The 'gpt-nonexistent-9' model is not supported when using Codex with a ChatGPT account."}}`.
- This is the same pattern as spike R11.5.

**Consequences for phase 1:**
- The Claude reader skips `isApiErrorMessage` rows and `model == "<synthetic>"` when counting model calls. Otherwise a failed cell passes the served-model and at-least-one-call checks (US-11).
- The pre-outcome provider-error scan reads the Claude error row (`apiErrorStatus`, `error`) and Codex's `task_complete.error.status`.
- Classification:
  - 408, 429, 5xx or overload → `failed (provider)` (HB-CELL-108, infrastructure);
  - any other 4xx model error (for example 404 `model_not_found`, 400 `invalid_request_error`) → `failed (model unavailable)` (HB-CELL-116, benchmark: the plan pinned a model the account cannot serve).
- Golden fixtures come from these two records, with paths replaced by placeholders.

## N4: every harness process stays in the cell's Job Object [Verified]

For each harness, natively:
- The probe created a job with kill-on-close and no breakaway.
- It spawned the adapter suspended, assigned it and resumed it.
- It ran one turn whose shell command slept for 12 s.
- Once a second, it compared every descendant of the adapter (a `Win32_Process` snapshot) with the job's process-id list. For any descendant missing from the list, it checked directly with `IsProcessInJob`.

| Harness | Processes seen | Outside the job | Alive after `TerminateJobObject` | Handle inheritable |
| --- | --- | --- | --- | --- |
| Claude (3 runs) | `claude.exe`, `bash.exe`, `conhost.exe`, `python.exe` (up to 7) | none; the first run's one suspect and the second run's five were processes that had exited between snapshots | none | no |
| Codex | `codex.exe`, `codex-code-mode-host.exe`, `node.exe`, `pwsh.exe`, `cmd.exe`, `python.exe` (up to 6) | none | none | no |
| Copilot | `pwsh.exe`, `conhost.exe`, `python.exe` (up to 3) | none | none | no |

- **Not tested:** processes started through a broker (WMI, COM, Task Scheduler); these would escape any job (residual, ADR-0013).
- **A9 (monotonic clock across host sleep): not run.** It needs the host to sleep during a cell, which would suspend this session too. It is left for the operator.
