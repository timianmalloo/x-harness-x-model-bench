---
id: "note-spike-isolation-permissions"
title: "Spikes R1, R2, R11, N1, N2: config isolation, static permissions, host isolation, native cells"
type: doc
status: draft
owner: "@timianmalloo"
tags: [benchmark, spike, isolation, permissions, containers, security]
links:
  - { to: spec-harness-bench, rel: refines }
  - { to: note-spike-runner-path, rel: refines }
review-by: "2026-10-23"
summary: >-
  Per-cell config homes keep sign-in and drop user-level skills for all three harnesses, but a
  workspace under the user profile still loads ~/.claude/CLAUDE.md, and Claude's account context
  (email, account-synced skills) survives any isolation. A static profile runs shell and edits with
  zero prompts on every harness. Linux containers give every harness the same containment, but
  Copilot needs a token passed in there. N1/N2 (after ADR-0012): natively, with Codex in
  agent-full-access, all three run symmetric and unsandboxed with zero prompts, log every command, and
  Copilot needs no token; a Windows Job Object kills and confirms a cell's whole process tree.
---

# Spikes R1, R2, R11: config isolation, static permissions, host isolation

Date: 2026-09-23. Machine: the Windows 11 workstation, Docker Desktop 4.91.0 (engine 29.8.0, WSL2). Adapters: `claude-agent-acp` 0.79.0, `codex-acp` 1.12.0 (pinned lockfile). Resolves the evidence for spec risks R1, R2 and R11 (`docs/specs/harness-bench.md`); the decisions are in `docs/architecture.md`.

Every probe used the same prompt: run `python -c "print(6*7)"`, write the output to `answer.txt`, list every loaded skill. Permission callbacks were refused, as the pack's runner does under `deny`. Credentials were copied into scratch homes, never printed, and deleted after each probe (0 copies left, checked). Throwaway code: `spikes/runner-path/iso_probe.py`, `container_acp.py`, `run_container_probes.py`, `container/Dockerfile` (gitignored).

Labels: **Verified** = run here; **Inferred** = reasoned; **Flagged** = open.

## R1 — per-cell config homes

| Harness | Isolation | Sign-in | User-level canary (`graphify` skill) | Native record |
| --- | --- | --- | --- | --- |
| Claude | `CLAUDE_CONFIG_DIR` = fresh dir holding only `.credentials.json` + `settings.json` | works | 0 (control: 20) | in the cell's home |
| Codex | `CODEX_HOME` = fresh dir holding only `auth.json` + `config.toml` | works | 0 (control: 0, so the check is void for Codex skills) | in the cell's home |
| Copilot | `COPILOT_HOME` = empty dir | works | 0 (control: 9) | in the cell's home |

- **R1.1 [Verified]** Sign-in survives per-cell homes on all three. Claude and Codex need their credential file copied in. Copilot needs nothing: its token is not in `~/.copilot/config.json`; [Inferred] it is in the Windows credential store.
- **R1.2 [Verified]** Per-cell homes also give per-cell native records and per-cell Codex state (memories, goals, history sqlite), so no cell reads or writes another's (spec US-13 c2).
- **R1.3 [Verified] Ancestor-directory leak.** With the workspace under `C:\Users\<user>\...`, Claude loaded `~/.claude/CLAUDE.md` as *project* memory despite the fresh config dir. Claude reads `CLAUDE.md` and `.claude/CLAUDE.md` in every parent directory. With the workspace under `C:\Projects\...` the canary disappeared. **Cell workspaces must live outside the user profile.**
- **R1.4 [Verified] Account-level context survives every isolation**, including a container: the operator's email (2 hits) and the Claude account's synced skills (`anthropic-skills:*`, written into `<home>/skills/synced/` on first run). This is the login, not a file. It applies equally to pack on and off (not a pack confound) but it is a Claude-only treatment in harness comparisons. [Flagged] Whether account skill sync can be turned off; otherwise a dedicated benchmark account per vendor.

## R2 — a static, symmetric permission profile

| Harness | Static profile that completed with 0 permission requests |
| --- | --- |
| Claude | isolated `settings.json`: `permissions.allow = [Bash, Edit, Write, Read, Glob, Grep]`, `defaultMode = dontAsk` (the adapter parses `dontAsk` but does not advertise it as an ACP mode, so it must come from settings) |
| Codex | ACP mode `read-only` plus `[windows] sandbox = "unelevated"` in `config.toml` (native); `agent-full-access` inside a container |
| Copilot | `--acp --model gpt-6-sol --allow-tool shell --allow-tool write` (the runner forbids `--allow-all*`, not `--allow-tool`) |

- **R2.1 [Verified]** All three ran shell and wrote the file with zero permission requests and no model-based approval.
- **R2.2 [Verified by reading codex-acp]** Codex's default ACP mode `agent` routes approvals to an automatic model reviewer (`approvalsReviewer: auto_review`); `agent-full-access` removes the sandbox. On native Windows, `read-only` is the only static profile, and it needs the Windows sandbox setting, or every command asks (first isolated run: 1 request, blocked).
- **R2.3 [Verified] Approval is symmetric; containment is not, natively.** Codex runs commands in its Windows sandbox (workspace-write, no network). Claude's `Bash` and Copilot's `shell` run unsandboxed as the operator on native Windows.

## R11 — host isolation

- **R11.1 [Verified] A Linux container isolates by construction.** Image `node:22-bookworm-slim` + the pinned adapter lockfile + `@github/copilot@1.0.88` + `@openai/codex@0.156.0`, run as non-root user `cell` with only `/work` (the workspace) and the harness's home mounted. Inside: `/mnt` is empty (no host drives), the home holds only what was mounted, and no token, key or secret variable is set.
- **R11.2 [Verified]** Claude and Codex completed the task inside the container (`42`, 0 permission requests, 12 s and 19 s), with native records in the mounted per-cell home. Claude's Linux build reads the same `.credentials.json`; Codex reads the same `auth.json`.
- **R11.3 [Verified] Copilot needs a token passed in.** With no host credential store in the container, `session/new` returned `-32000 Authentication required`. [Flagged] Requires a fine-grained GitHub token with only Copilot access, passed as an environment variable; not tested (it needs the owner to create the token). The `gh` CLI token is not acceptable: it carries repository scopes (spec US-49).
- **R11.4 [Verified] The pack's transport cannot drive a containerised agent as is.** `coord_transport.py:663` sends the host `cwd` in `session/new`; inside the container the workspace is `/work`. The spike used a minimal ACP client instead.
- **R11.5 [Verified] A second "complete but no model answer" case.** The adapter-bundled Codex 0.154.0 rejected `gpt-6-sol` for a ChatGPT-account login (`invalid_request_error`), and the ACP turn still ended `end_turn`. Pinning Codex 0.156.0 fixed it. With spike 1.4 (Claude default profile: no assistant message, transport `complete`), that is two instances of one class: **a completed turn with no successful model call**. The spec's served-model check passes vacuously on zero calls; it must require at least one successful call.
- **Not tested:** a separate low-privilege Windows account (needs administrator rights to create); network egress restriction to the model APIs (proxy or firewall allowlist) [Flagged]; the .NET 10 SDK and Stryker in the image [Inferred: AiDe.Core is cross-platform per the proposal]; running Harbor tasks alongside.

## N1, N2 — native cells without containers (2026-09-23, after ADR-0012)

Question (owner): with security proportionate (ADR-0012), what do containers still buy? Code: `spikes/runner-path/native_probe.py`, `job_probe.py` (gitignored). Workspaces and homes under `C:\Projects\bench-cells-spike` (outside the profile); 0 credential copies left, then the folder was deleted.

**N1: one ACP turn per harness, natively, with a per-cell home.** The prompt asked for three things: run `python -c "print(6*7)"` into `answer.txt`; fetch `https://pypi.org/simple/` and write the HTTP status to `net.txt`; write `outside-<harness>.txt` in the workspace's **parent** directory.

| Harness | Profile | Permission requests | answer / net / outside | Commands in the native record | Time |
| --- | --- | --- | --- | --- | --- |
| Codex | ACP mode `agent-full-access`, per-cell `CODEX_HOME` with `config.toml` `model = "gpt-6-sol"` | 0 | 42 / 200 / written | all 3 | 29.4 s |
| Claude | per-cell `CLAUDE_CONFIG_DIR`, `settings.json` allow list + `dontAsk`, `ANTHROPIC_MODEL=claude-sonnet-5` | 0 | 42 / 200 / written | all 3 | 19.0 s |
| Copilot | empty per-cell `COPILOT_HOME`, `--allow-tool shell --allow-tool write` | 0 | 42 / 200 / written | all 3 | 16.9 s |

- **N1.1 [Verified] Natively, containment is symmetric: none of the three is sandboxed.** Codex's `agent-full-access` mode sets approval `never` and sandbox `dangerFullAccess` (read in `codex-acp` 1.12.0, `dist/index.js`, `AgentFullAccess`). It reached the network and wrote outside the workspace with 0 requests, exactly as Claude and Copilot did. The R2.3 asymmetry was a choice of Codex mode, not a property of native execution.
- **N1.2 [Verified] Copilot works natively with an empty per-cell home.** Its login comes from the Windows credential store (R1.1). It wrote 2 `assistant_usage_events` rows in the per-cell store. The R11.3 token problem exists only inside containers.
- **N1.3 [Verified] Every harness logs the exact commands it ran in its native record.** All three command strings were present in each record. So an agent's reads of the bench repository or a task oracle can be detected from its tool calls.

**N2: a Windows Job Object as the cell boundary (stdlib `ctypes`).**
- **N2.1 [Verified] Kill, then confirm.** A child process and its grandchild were started suspended, assigned to a job, then resumed. `TerminateJobObject` killed both. The job's active-process count went from 2 to 0, and `tasklist` confirmed that neither process remained.
- **N2.2 [Verified] An engine crash cannot leave orphans.** With `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`, a hard kill of the owning process (`taskkill /F`, no cleanup) killed the whole cell tree.
- **N2.3 [Verified] Peak memory per cell** comes from job accounting (`PeakJobMemoryUsed`), with no polling.
- **Not tested:** a job memory limit enforced (the cell killed at the cap); `node`-based adapters spawning their CLI inside the job, which should inherit it unless breakaway is allowed [Inferred, since we never set breakaway].

## What this means for the architecture (options, decided in `docs/architecture.md`)

1. ~~Containment symmetric across harnesses is only available by running every cell in a container.~~ *Corrected by N1.1: natively, Codex in `agent-full-access` is unsandboxed like the other two, so native cells are symmetric. See ADR-0013.*
2. A container-based cell needs a transport that maps the host workspace to `/work`: an upstream change to the pack's transport, or the bench's own minimal ACP driver.
3. Workspaces outside the user profile, per-cell homes seeded with only the credential, and pinned CLI builds are required in either mode.
4. Claude account context is a residual harness-level treatment unless a dedicated account is used.
