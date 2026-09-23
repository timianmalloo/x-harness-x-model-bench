---
id: "note-spike-runner-path"
title: "Spike: harness launch over ACP, telemetry, and worker isolation"
type: doc
status: draft
owner: "@timianmalloo"
tags: [benchmark, spike, runner, telemetry, isolation]
links:
  - { to: note-proposal-grounding-findings, rel: refines }
  - { to: proposal-cross-harness-benchmarking, rel: refines }
review-by: "2026-10-23"
summary: >-
  Spikes 1 and 2 run on the workstation on 2026-09-23. All three harnesses complete a turn over
  ACP through the pack's transport, and every token count lives in each harness's own session
  store (Copilot also records a native cost basis). A generated per-cell repo as the invoking
  checkout isolates workers with no runner change. Four runner gaps block unattended benchmark
  cells: prompt delivery, per-worker model pins, permission symmetry, and user-level config leakage.
---

# Spike: harness launch over ACP, telemetry, and worker isolation

Date: 2026-09-23. Machine: the Windows 11 workstation. Pack: revision 92 as installed in this repo.
Resolves the evidence for F1 and F3 in `proposal-grounding-findings.md`; the decisions stay with S-02.

Labels: **Verified** = read and run here. **Flagged** = not resolved by this spike.

## Setup

- ACP adapters installed from the pack's own pinned lockfile (`ai-forward/docs/knowledge/acp-compatibility/package-lock.json`) into the gitignored `spikes/acp-adapters/`: `@agentclientprotocol/claude-agent-acp` 0.79.0, `@agentclientprotocol/codex-acp` 1.12.0. Copilot is native: `copilot --acp`, CLI 1.0.89-0.
- Spike 1 called `coord_transport.run_session` directly (the call `coord-runner.py` makes) with one trivial prompt per harness, in a disposable git repo.
- Spike 2 ran the full `coord-runner.py` path (`prepare` → `fingerprint` → `run`) with three workers (Claude, Codex, Copilot), invoked from a generated per-cell repo with no pack installed. The task: create `PONG.txt` containing `PONG`.
- Throwaway code: `spikes/runner-path/` (`acp_probe.py`, `fill_compile.py`, `qualify.py`). Not committed (`spikes/` is gitignored).

## Spike 1: launch and telemetry over ACP

**1.1 Launch works on all three.** [Verified] Each harness completed one turn over ACP: Claude via the adapter, Codex via the adapter, Copilot natively. Trivial-turn duration 2–8 s.

**1.2 The runner records no usage. Every number comes from the native store.** [Verified] `run_session` returns metadata only; runner events carry `"usage": "not recorded"`. The session id in the ACP result names the store record exactly:

| Harness | Store | What it holds | USD cost |
| --- | --- | --- | --- |
| Claude | `~/.claude/projects/<cwd-slug>/<session>.jsonl` | per assistant message: model, input, output, cache creation (5 m / 1 h split), cache read, thinking tokens; tool calls and results | none |
| Codex | `~/.codex/sessions/YYYY/MM/DD/rollout-*-<session>.jsonl` | model, context window, per-turn and thread totals: input, cached input, cache write, output, reasoning | none |
| Copilot | `~/.copilot/session-store.db`, table `assistant_usage_events`; `session-state/<session>/events.jsonl` | per call: model, input, output, cache read/write, reasoning tokens, duration, time to first token, `total_nano_aiu`, `request_multiplier`, and a per-token-type price in `token_details_json`; `totalPremiumRequests` | **native basis in AI units** |

- Key readers by session id, never by file time. The probe's time-window scan also caught the coordinator's own session file.
- **Contradicts the proposal:** Copilot has a native cost basis. The spike's call: 3 input + 12,945 cache-write + 6 output tokens = 3,242,850,000 nano-AIU, which matches the per-type prices in the row exactly. [Flagged] The AIU→USD conversion is not established.

**1.3 The adapters bring their own CLI builds.** [Verified] `claude-agent-acp` runs the Claude Code binary bundled with its SDK (2.1.274; installed CLI is 2.1.280). `codex-acp` runs its bundled `@openai/codex` (0.154.0; installed is 0.156.0). Overrides: `CLAUDE_CODE_EXECUTABLE`, `CODEX_PATH`. The runner's executable fingerprint hashes `node.exe`, not the adapter or the CLI, so the harness build under test must be bound separately (binding files) and recorded.

**1.4 Model pinning is only enforced for Copilot.** [Verified]
- Copilot: `--model` plus ACP `session/set_model`, then checked against native assistant and usage events (`coord-runner.py:917-918, 947-949`).
- Claude: the adapter takes `ANTHROPIC_MODEL`, else the **user's** `settings.json` model. With defaults, the bundled binary resolved the user's `opus[1m]` to **Claude Opus 5, not Opus 5.5**, and the transcript holds no assistant message while the transport reported `complete`. With `ANTHROPIC_MODEL=claude-sonnet-5` the transcript shows `claude-sonnet-5` served.
- Codex: the model came from the user's `~/.codex/config.toml` (`gpt-6-sol`); nothing in the contract pinned it. [Flagged] `CODEX_CONFIG` or `session/set_model` for Codex not tested.
- `coord-run/1` has no per-worker environment, so an environment pin applies to every worker in a contract: `cc-opus` and `cc-sonnet` cannot share one contract.

**1.5 User-level configuration leaks into every cell.** [Verified] The Claude worker loaded `~/.claude/CLAUDE.md`, the user's email context and the user's skill list. Codex used the user's `config.toml`. Copilot fired four hooks whose source was not inspected. A `pack=off` cell is therefore not a bare harness. [Flagged] Isolated config homes per cell (`CLAUDE_CONFIG_DIR`, `CODEX_HOME`, `COPILOT_HOME`) are untested, including whether authentication survives them.

## Spike 2: worker isolation (F1)

**2.1 An external per-cell repo works as the invoking checkout.** [Verified] With the bench repo's pack scripts called by path and cwd in a generated cell repo, `prepare`, `fingerprint` and `run` all succeeded. Worktrees are created as siblings of the cell repo at its base commit.

**2.2 Worker trees stay clean.** [Verified] After the run, each worker tree held only the committed base and the agent's `PONG.txt`. Coordination state stayed in the invoking repo: `.git/coord-runs/` (private), `.agents/log/` and `docs/audit/` (both untracked; `docs/audit/` was written by the compile step). F1 option (b) isolates the worker with no runner change, provided the bench generates the cell repo itself.

**2.3 Option (c) leaks the oracle.** [Verified by the runner's construction] A worker worktree is the invoking checkout at HEAD, so a task placed under a bench-repo worktree would expose `tasks/<ID>/tests/` and `oracle/`. Reject (c).

**2.4 The runner does not send the task text.** [Verified] It sends `render_sections(compiled doc)`: goal state, trace table, references, assumptions, decision requests, contract slot and provenance, prefixed with `python docs/ai-forward-pack/scripts/audit-log.py start --session <id> --skill coordination-worker` and suffixed with coordination instructions (`coord-runner.py:275-279`, `prompt-compile.py:478-519`). The text is identical across harnesses, but:
- the task reaches the model only as a compiler's goal-state fill, never verbatim;
- in `pack=off`, the Claude worker ran the preamble and tried to execute a pack script that does not exist in its tree.
The delivery path itself is a pack treatment applied to the control arm.

**2.5 Permissions are asymmetric under unattended `deny`.** [Verified]
- Codex (default `agent` mode, which auto-reviews approvals): ran shell, wrote the file, `ready_for_review` in 24.7 s.
- Claude (`acceptEdits`): the preamble shell call asked permission, was denied, and the worker is `blocked`, although it then wrote `PONG.txt` with its file tool.
- Copilot: `git status` asked permission, was denied, `blocked`, no file.
The runner forbids Copilot's `--allow-all*` flags, and `ask` needs the Owner to answer each request. As installed, a real task that builds or tests cannot run unattended on Claude or Copilot, while Codex can. [Flagged] Candidates, untested: Claude mode `bypassPermissions`; Copilot scoped `--allow-tool` flags (not on the runner's forbidden list).

**2.6 Runner state is not task outcome.** [Verified] The Claude cell is `blocked` with the correct file present. Grade the tree. Treat runner state as a process metric.

**2.7 Leader lease.** [Verified] `leader pin` TTL is capped at 900 s (default 300 s). The runner renews during `run`; a gap between `prepare` and `run` longer than the TTL needs a re-pin.

## What this means for S-02 (options, not decisions)

1. **Isolation:** option (b). Bootstrap generates one git repo per (task, pack) with the task base committed, applies pack on/off there, and invokes the runner from it. Hidden tests and oracles stay in the bench repo.
2. **Use of coord-runner.** Either (a) change the pack upstream (ai-forward), then `/updatepack`: a verbatim-prompt mode without the audit preamble, per-worker environment or model pin for Claude and Codex, and a symmetric unattended permission profile; or (b) drive cells with `coord_transport.run_session` directly and keep coord-runner for the pack's own coordination scenarios (F-tasks). (b) drops the proposal's rule that every cell is a `coord-run/1` worker; that rule needs an ADR either way.
3. **Telemetry:** native-store readers keyed by ACP session id; `session-profile.py` already reads Claude and Copilot; Codex needs the new reader (as the proposal says).
4. **Configuration isolation:** per-cell config homes, spiked before the first measured run.

## Proposal corrections this forces

- Adapter table: headless flags → ACP adapters, with the pinned CLI build as a recorded factor.
- Cost NA rule: Copilot has a native AIU basis; NA applies only until the AIU→USD rate is sourced.
- "Harness version" means the CLI the adapter actually runs, not the one on PATH.
- "Prompt text identical per task": true across combos, but not verbatim and not pack-free under the current runner.
