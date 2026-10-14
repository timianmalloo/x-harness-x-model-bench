---
id: runbook-lean-comparison-run
title: "Runbook: the lean comparison run - pinned windows, launch folder, sessions, Copilot transport control"
type: doc
status: draft
owner: "@timianmalloo"
tags: [runbook, lean, context-window, copilot, acp, session-layer]
links:
  - { to: adr-0024-combo-settings-and-served-read-back, rel: depends-on }
  - { to: adr-0028-copilot-prompt-mode-transport, rel: depends-on }
review-by: "2027-04-14"
summary: >-
  What the operator needs to run Prompt 1 for a like-for-like comparison: the context window each CLI is pinned at
  (measured), the folder to start the CLI in so no pack file loads, how many interactive sessions to run per CLI and how
  the hand-off identifies them, and why Copilot over ACP cannot run at the pinned window (and how to run it at the
  default window as a manual transport control).
---

# Runbook: the lean comparison run

Prompt 1 is `docs/benchmarkpromps/lean-benchmark-run-prompt.html`. This page holds the facts behind its pins.

## 1. Pinned context windows (plan rows A2, B13)

Codex and Copilot both run `gpt-6.1-sol`. A comparison pins each at the highest window it serves.

| CLI | Pin (matrix `context:`) | Served, from the CLI's own record | How it was measured |
|---|---|---|---|
| Codex 0.160.0 | `872000` | `task_started.model_context_window` 828,400 = 872,000 x 95% | one `codex exec`, effort low, isolated `CODEX_HOME` seeded by `Profile.seed_home`, 2026-10-14 |
| Codex, pin 1,000,000 or 1,050,000 | refused by the profile (`values: ["872000"]`) | 828,400 for both: clamped to the catalog `max_context_window` 872000 | same spike, 10.2k tokens each |
| Codex, no pin | `default` | 500,000 nominal (475,000 effective) | the lean run of 2026-10-13 |
| Copilot 1.0.89-1 | `922000` (argv `--context long_context`) | `session.start.contextTier` `long_context`; catalog `max_prompt_tokens` 922,000, `max_context_window_tokens` 1,050,000 | lean cells `...copilot-gpt-6.1-sol-high-922k`; tier re-seen in a `-p` spike 2026-10-14 |

- The codex pin is the ceiling: nothing higher is served. Copilot offers tiers only (`--context default|long_context`),
  so it cannot be pinned at 872k. The 50k nominal gap (922k against 872k, 5%) stays and is recorded.
- The model's own 1.05M is Copilot's window including 128,000 output tokens; Codex's 872k is its catalog ceiling.
  They are not the same quantity, and no run measures a "1.05M" prompt.
- HB-VAL-010 judges the pins. Codex: expected `872000`, served is the rollout window divided by the catalog percent
  (the reader returned 872000 for all three spike rollouts). Copilot: expected tier `long_context`
  (`views._expected`, a pin whose frozen args name `--context`). `tests/test_validity_served.py` covers both.
- A `bench plan` of a matrix with `context: 872000` (codex) and `context: 922000` (copilot) was accepted on 2026-10-14.
- The interactive session is not the cells. For the session layer, set the same windows before you start: Codex
  `model_context_window = 872000` in `~\.codex\config.toml`; Copilot `/model` then `long_context`. The hand-off records
  `session_context`, and an unequal session is listed in `issues`.

## 2. Launch folder and the files a CLI still loads (A4)

Start the CLI in `C:\Projects\bench-launch`: an empty folder, no git repo, no `AGENTS.md`, `CLAUDE.md` or `.github`
instructions above it. Every repo command in Prompt 1 is absolute: `git -C`, `uv --directory <worktree> run bench ...`,
`python <absolute script>`. The one command that reads its working directory is `coord-core.py worktree new`, run with
`Push-Location <repo>` and `Pop-Location`.

User-level files still loaded cannot be avoided without changing the operator's setup. Observed on this host by listing
the home folders (Claude Code's `CLAUDE.md` was also seen loaded; the others are Inferred from the folders present):

- Claude Code: `~\.claude\CLAUDE.md`, `~\.claude\skills`, `~\.claude\plugins`, `~\.claude\settings.json`. Auto-memory is
  keyed by the launch folder, so a new folder starts with none.
- Codex: no `~\.codex\AGENTS.md`; `~\.codex\skills`, `~\.agents\skills`, `~\.codex\memories_1.sqlite`, `~\.codex\rules`.
- Copilot: no `~\.copilot\copilot-instructions.md`; `~\.copilot\skills`, `~\.copilot\installed-plugins`,
  `~\.copilot\mcp-config.json`.
- agy: no `~\.gemini\GEMINI.md`; `~\.agents\skills`, `~\.gemini\antigravity-cli\knowledge` and `...\brain`.

Prompt 1 asks the session to list the instruction files its own context shows as loaded (`instruction_files_seen` in
`handoff.json`), so a leak shows in the data rather than being assumed away.

## 3. Sessions per CLI (A5)

Run Prompt 1 in 2 separate sessions per CLI (`SESSIONS_PER_CLI = 2` in the prompt). Each paste is its own run: its own
`RUN_ID`, branch, worktree, cell folder and 60 cells. The session index is `1 +` the branches
`bench/lean-*-<COMBO_ID>` whose timestamp is at or after `SESSIONS_SINCE`; edit `SESSIONS_SINCE` in the prompt to start a
new campaign. A session that stopped after STEP 1 still counts, because its branch exists. `handoff.json` carries
`session_index`, `sessions_per_cli`, `session_id`, `transcript` (absolute path or `"not found"`), `launch_dir`,
`session_context` and `instruction_files_seen`. The reply ends with `SESSION: <RUN_ID> | session i of n | transcript
<path>` and then the unchanged `HANDOFF: <RUN_ID>@<WT>` line that Prompt 2 reads.

## 4. Copilot over ACP as a transport control (A3)

Question: does Copilot's higher tool-call count come from `copilot -p` re-orienting each turn? The control is the same
model and effort over native ACP. What the bench can do today:

- **Not at the pinned window.** On the pinned 1.0.89-1, in an isolated `COPILOT_HOME` with `copilot --acp`, both
  `--context long_context` and `settings.json` `{"contextTier": "long_context"}` serve `usage_update` size 272,000, and
  `session.start.contextTier` is null (probe 2026-10-14, one trivial prompt each; ADR-0024 and ADR-0028 record the same
  for 1.0.89-1 and 1.0.92-4). ACP cannot reach 922k.
- **Not as a combo option.** `harness: copilot` always loads `bench/profiles/copilot.yaml` (the `-p` adapter command),
  and `views._prompt_mode(plan, harness)` reads one `adapter_version` per harness for the whole plan. A per-combo
  `transport` would change `config.py` (combo schema), `plan.py` (cell and build records), `profiles.py` (a second
  command) and `views.py` (a per-cell `_prompt_mode`). Those files are outside this track.
- **A manual control at the default window works at plan level.** Both transports at context `default` (272,000) compare
  like for like. On a control branch: copy `bench/profiles/controls/copilot-acp.yaml` over `bench/profiles/copilot.yaml`;
  delete the `adapter_pin` line of the `copilot` entry in `bench/tools/builds.yaml`; run a matrix with a Copilot combo
  `context: default`. `bench plan` accepted this on 2026-10-14 (12 cells, build 1.0.89-1). Run the `-p` side from `main`
  with the same combo at `context: default`, and compare the two runs.
- **Not verified:** a whole cell or run through the ACP profile, the Copilot reader on an ACP record (the reader's debug-log
  source is written for `-p` turn logs), and `--log-level debug --log-dir` under `--acp`. Run one task first and read
  `bench status --check-ended` before spending a full run.

Spike cost, 2026-10-14: Codex three runs of about 10.2k tokens each (30.7k); Copilot three runs of about 3.3k to 4.2k
tokens each (the `-p` run used the account default model by mistake: 4.2k).
