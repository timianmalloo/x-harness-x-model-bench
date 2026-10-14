---
id: plan-lean-runs-2026-10-13-findings-and-repair
title: "Lean runs of 2026-10-13: what they show, what broke, what changed"
type: plan
status: proposed
owner: "@timianmalloo"
summary: "Six CLIs ran the any-CLI lean prompt. This plan answers four questions: does GPT drift more in Copilot than in Codex (cells say yes, the interactive sessions say the opposite, and two confounds remain); what broke (18 issues, 12 fixed in this change, 6 need a decision); whether bench and grading belong together (capture and deterministic checks yes, judging and analysis no); and how the analysis prompt changed."
tags: [lean-benchmark, analysis, drift, ceremony, over-thinking, repair-plan, copilot, codex, grok, prompts]
links:
  - { to: plan-strategy-lean-benchmark, rel: relates-to }
  - { to: runbook-add-a-harness, rel: relates-to }
  - { to: adr-0023-lean-summary-over-verdicts, rel: relates-to }
  - { to: adr-0025-transport-seam-grok-and-agy-cells, rel: relates-to }
review-by: "2026-10-28"
---

# Lean runs of 2026-10-13: what they show, what broke, what changed

## In one minute

- **Copilot vs Codex, same model (gpt-6.1-sol).** In the 60 headless cells, Copilot does more: 3.6x the tool calls,
  3.4x the reasoning tokens, and it changes lines outside the task (median 16.5 discretionary lines; Codex 0). That
  is behaviour, not only output style. In the interactive sessions you watched, the opposite: Codex polled 10x too
  often, wrote 10x the text and skipped the last three steps; Copilot followed the prompt. Two confounds keep this
  from being a clean harness verdict (section 2), and the instrumentation to remove them is listed.
- **What broke.** 18 issues. 12 are fixed in this change, tested, merged and pushed. 6 need your decision (section 3).
  The biggest: `bench report` failed on every run; the early validity check could never fire; every Codex cell was
  invalid because the bench's Codex profile was out of date; a resumed Grok run could write a live token into the
  repo root.
- **Bench and grading.** Keep capture and the deterministic checks with the run, and make them per cell; keep model
  judging and analysis separate (section 5).
- **Prompt 2** is now "analyse the lean runs": it finds finished runs itself, never copies them, judges only on request,
  and writes four pages, including a behaviour page for exactly your question (section 6).
- **Grok** takes about 18 hours because it runs one cell at a time and spends 67% of each cell reasoning; the pack's
  hooks add about 5 minutes per pack-on cell. A login pool now lets it run in parallel (section 4).

## 1. The runs

| Run | Cells | Valid | Invalid (code) | Session followed the prompt? |
|---|---|---|---|---|
| Claude Code, Opus 5.5, high, 1M | 60/60 | 59 | 1 (HB-VAL-008: the model called `TaskStop`) | Yes; polled every ~1 min instead of 10 |
| Copilot, GPT-5.5, high, 922k | 60/60 | 59 | 1 (HB-VAL-004: Copilot path check) | Yes; `bench report` failed, wrote its own summary |
| Copilot, gpt-6.1-sol, high, 922k | 60/60 | 52 | 8 (HB-VAL-004: Copilot path check) | Yes; polling as asked |
| Codex, gpt-6.1-sol, high, default | 60/60 | 0 | 43 HB-VAL-010 + 17 HB-VAL-008 (stale bench profile) | No: polled every ~1 min, skipped steps 7-9, printed HANDOFF without handoff.json |
| agy, Gemini 4 Argon (high) | 60/60 | 59 | 1 (HB-VAL-008: the model called `schedule`, NG1 pack-on r1; B16) | Finished and graded; about 11 min a cell, one at a time |
| Grok 4.7, high | 15/60 at 20:30 on 2026-10-13 | 15 of 15 (early check, provisional) | - | Still running; about 18 min a cell, one at a time |

The Grok counts come from the new `bench status <run> --check-ended`, run on the live run. It uses the grading pass's
rules but writes nothing; the final grading at the end of the run is the record. On agy it flagged the same one cell
the final grading did.

The Codex run's HANDOFF line should not be graded: its cells are invalid for bench reasons (fixed now) and it has no
handoff.json. Re-run Codex with the fixed profile.

## 2. Does GPT drift more in Copilot than in Codex?

Two layers were measured with the same tool (`tools/behaviour_measures.py`, added in this change).

**Headless cells** (10 tasks x 3 repetitions per arm, medians, computed from each run's facts):

| gpt-6.1-sol | Codex off | Copilot off | Codex on | Copilot on |
|---|---|---|---|---|
| Model requests | 10.5 | 13.5 | 25 | 23 |
| Reasoning tokens | 1,232 | 4,184 | 3,173 | 6,450 |
| Output tokens | 6,183 | 11,611 | 12,836 | 18,480 |
| Tool calls | 9.5 | 34.5 | 22 | 46 |
| Discretionary lines changed outside the task (scope_creep) | 0 | 16.5 | 38 | 28 |
| Reads outside the task's neighbourhood (attention_drift) | not recorded | 0.51 | not recorded | 0.69 |
| Wall minutes per cell | 3.0 | 4.5 | 5.6 | 8.0 |

For reference, Claude Opus 5.5 off: 13 requests, 4.5k reasoning, 16 tool calls, 0 scope creep, attention drift 0.23.

**Interactive sessions** (the same Prompt 1 in each CLI; one session each; read from the session transcripts):

| gpt-6.1-sol | Codex | Copilot |
|---|---|---|
| Status checks | 113, every 0.95 min (asked: 10 min) | 8, every 10.2 min |
| Assistant text | 16.7k chars, 121 messages (111 poll lines) | 1.7k chars, 5 messages |
| Model calls / input tokens | 155 / 19.8M | 46 / 6.7M |
| Steps skipped | 7-9 (verify, summary, handoff.json) | none |
| Unrequested work | read the pack's docs (268k input tokens before starting), audit-log entry, 24 source reads during the run | 2 skill loads, goal-state block, 28 source reads during the run |

**Reading.** The two layers point in opposite directions. In cells, Copilot's extra is real behaviour: more tool
calls, more reasoning, and edits outside the task. In the sessions, Codex's extra is mostly polling volume (style that
follows from one design choice) plus skipping steps (behaviour). Your anecdote matches the cells.

**What keeps this from being a clean harness verdict (Inferred, each with how to remove it):**

1. **Transport.** Copilot cells run through `copilot -p` (one process per turn, resumed), the only mode that applies
   `long_context` (ADR-0028). Codex runs interactively over ACP. Some of Copilot's extra tool calls may come from the
   `-p` mode re-orienting each turn. To remove: one Copilot run at default context over the older ACP mode, compared
   with `-p` at the same context.
2. **Settings and validity.** Codex served 500k context, Copilot 922k; and every Codex cell was invalid for bench
   reasons. To remove: re-run Codex with the fixed profile and pin the same context explicitly in both
   (`model_context_window = 922000` in `~/.codex/config.toml` if Codex accepts it, else both at default).
3. **The sessions were all pack-on.** Every CLI ran Prompt 1 inside this repo, whose AGENTS.md is the pack's; the goal-
   state blocks, skill loads and Codex's grounding reads came from there. Prompt 1 now overrides that ceremony.

**Instrumentation to add, so the next run answers the question directly:**

| # | Measure | Why | Status |
|---|---|---|---|
| I1 | Classify Codex shell commands as read / edit / test / other | Codex's reads and edits are invisible today, so its attention drift and exploration are "not recorded" | Owed |
| I2 | Assistant text per cell (chars, messages) and planning/to-do tool calls | Ceremony is only inferred today | Owed |
| I3 | Per-tool hook time for every harness | Grok records it; Claude records only Stop hooks; pack-on wall time hides it | Owed |
| I4 | The session transcript path in handoff.json, read by the bench's own readers | The interactive layer is your real experience | Done (Prompt 1, behaviour_measures) |
| I5 | Copilot interactive usage | Interactive Copilot writes token usage only at shutdown | Harness limit; use cell layer |
| I6 | First-request input split (system prompt, tool catalogue, instructions) per harness | Separates "the harness sends more" from "the model does more" | Partly there (prompt_parts); owed for Copilot's tool catalogue |
| I7 | Same pinned context and effort across harnesses for a comparison | Settings are a confound today | Prompt/operator |
| I8 | A `tool_inputs` reader for agy and Grok (the paths each call names) | Without it `grade/drift.py` returns "no tool-input reader", so attention drift is not recorded for either harness, though both record read and edit tools | Owed |

**agy (Gemini 4 Argon, high), final, 60 cells.** It does the most reasoning of any run: a median 23.5k reasoning tokens
off and 20.7k on, against 4.5k for Claude and 1.2k for Codex. It takes about 11 minutes a cell. It changes nothing
outside the task (scope_creep 0 on both arms), and the pack barely moves it: requests 25.5 vs 23, tool calls 33.5 vs
31.5, wall time 11.4 vs 11.0 minutes. Its pack-on cells leave only 9.5 machine lines in the task tree, against 519 for
Claude and 587 for Codex (why is not checked yet). Attention drift is not recorded (I8).

## 3. Issues and the repair plan

**Fixed in this change** (tests seen red then green; full suite, stamped tier and gate ring run before the merge):

| # | Issue | Evidence | Cause | Fix |
|---|---|---|---|---|
| B1 | `bench report` failed on every lean run (HB-USR-002 "both RW2 rep 1 arm off") | Claude, both Copilot sessions | `lean._relabelled` set rep = batch index; 3 repetitions in one batch collided | rep = (batch-1) x width + plan rep; ADR-0023 amended |
| B2 | 43 Codex cells HB-VAL-010 | served 500k vs profile 272k | the default window depends on the model | Codex default context recorded, not judged |
| B3 | 17 Codex cells HB-VAL-008 (spawn_agent, send_message...) | 16 pack-on, 1 pack-off | Codex 0.160 takes delegation tools from the server's model catalog; no config flag removes them | Each cell gets a frozen, hash-pinned copy of the served catalog, delegation removed outside scenario 6 |
| B4 | The early validity check could never fire | every session saw "not graded" | validity is computed only by the end-of-run grading pass | `bench status <run> --check-ended`: reads ended cells' records now, same rules, writes nothing; agreed with the final grading on the Codex run. Each flagged line names the cause (for example "out-of-profile tool called: schedule", or "context served 500000, expected 272000"). Exit 7 on a mismatch |
| B5 | Codex cell homes downloaded ~66 MB of plugins each (~4.5 GB per run archived) | archive listing | remote plugin catalog | `plugins = false`, `remote_plugin = false`; measured 0 bytes after |
| B8 | Grok runs one cell at a time | 60 x ~18 min | one rotating login | A pool of logins: `HB_GROK_CRED_HOME` may list several homes; cap <= number of homes. Needs your logins (runbook `grok-credential-pool.md`) |
| B9 | 4 RS2 cells scored ~837k lines of scope creep each | drift.log: `.venv/Lib/...` | an agent-made virtual environment counted as discretionary | `.venv` is machine-written, like the linters' caches |
| B11 | A resumed Grok run could write a live token to `<cwd>/auth.json` | resume.py, verified in code | resume wrote back to the profile's relative source | A cell records the home it seeded from; resume writes there or declines |
| Q1-Q8 | Prompt 1: impossible early check; no rule after a late stop; HANDOFF without handoff.json; polling ignored; sandbox; unrequested work; repo ceremony; no transcript path | the six session transcripts | prompt gaps | Prompt 1 hardened (see its page) |
| - | Prompt 2 assumed judging and copied GBs of runs | its text | design | Rewritten (section 6) |
| - | A new CLI could not be added without editing four lists in code | earlier today | design | Harnesses are registered by their files; Prompt 1 onboards an unknown CLI |
| - | A test failed under full-suite load ("reference: case p-1 timed out") | the merge gate, 1 of 4906 | a 1 s case bound sized for an idle machine (class TIME-B) | Bound raised to 2 s (the slow role still sleeps 3 s); instance recorded in the defect register |

**Needs your decision:**

| # | Issue | Options |
|---|---|---|
| B10 | 9 Copilot cells HB-VAL-004 "tools denied by hook". It is Copilot's own path verification: commands naming your real home (`$env:USERPROFILE`), uv's Python store, or a 261-char path (over MAX_PATH, because the cell path repeats the run id). No flag fixes it inside ADR-0004 except `--allow-all-paths`, which it excludes. | (A) record it as a harness path limit with its own validity text, not a model fault; (B) point HOME/USERPROFILE at the cell home for Copilot (as for Grok and agy), which changes its environment versus Claude and Codex; (C) shorten cell paths. Recommended: C now, plus A. |
| B12 | Codex cells load your personal skills from `~/.agents/skills` | Moving HOME for Codex cells (`user_home_vars`) needs its own spike; or accept and record it |
| B13 | Re-run Codex | With the fixed profile; decide the context to pin (I7) |
| B14 | Grok spends 67% of its time reasoning at effort high (its default) | Keep high, or add a `medium` Grok combo to see whether the reasoning buys correctness |
| B15 | Pack track (ai-forward repo, not changed here): (P1) three hook processes before every tool call, each `git -> sh -> python`; in Grok that is 11 s per read and 18 s per edit; two of them serve a coordination layer cells do not use. (B7) pack hooks write ~500 lines of `.agents/log` files into the task tree. | One fast dispatcher per event; skip coordination hooks when coordination is off; write logs outside the task tree |
| B16 | agy NG1 pack-on r1 is HB-VAL-008 for one `schedule` call. The call was `schedule(DurationSeconds=30, Prompt="Check task-36 completion")`: a timer to wait for its own background command. agy cancelled it at once ("agent already has undelivered messages"). It touched nothing in the workspace. | (A) keep `schedule` out of profile, as the agy-meta ruling has it; the cell stays invalid; (B) class a `schedule` call as `meta` (turn control, like `wait` and `wait_5_seconds`). Recommended: B, by an amendment to that ruling, since the call is a wait. |

**Open, not yet investigated:** Claude SM2 cell called `TaskStop` (1 cell, HB-VAL-008); every Claude cell warns HB-VAL-006
(no recorded agent_version); `copilot.exe --version` reports 1.0.97 without an isolated COPILOT_HOME (check the
engine's own version calls use the isolated home); Codex's unknown-model check runs at seed time, not plan time.

## 4. Why Grok takes about 18 hours

Measured on its first 5 cells, from Grok's own events:

- **One cell at a time.** 60 cells x 14-22 minutes. The cap exists because a Grok login rotates its refresh token, so
  cells cannot each copy it. Fixed by the login pool (B8): with N homes, N cells run at once.
- **Reasoning dominates.** 61.3 of 91 measured minutes (67%) are spent streaming reasoning, over ~28 model requests
  per cell. Time to first token is ~4 s, so this is reasoning volume, not latency (B14).
- **The pack's hooks.** Pack-on cells spend 4.6-6.0 minutes in tools against 0.2-0.9 pack-off: file reads take a
  median 11 s and edits 18 s because three hook processes run before each call (B15/P1). That biases pack-on vs off
  time comparisons against the pack.

## 5. Should bench and grading be coupled?

**Recommendation: split by what the step is, not by name.** Three layers:

1. **Capture and deterministic checks belong with the run, per cell.** Today `bench run` already ends with a
   deterministic grading pass (`cli.py:428`, no judge calls), but it runs once, at the end. That is why the early
   check could not work and Codex ran 60 invalid cells. Move fact extraction and validity to each cell's end (the
   engine already reads each cell's record), and let `status` show them live. `--check-ended` is the first step.
2. **Model judging stays separate and optional.** It costs tokens, is non-deterministic, and must be re-runnable
   on frozen archives (the verdict store). Prompt 2 now judges only when asked.
3. **Analysis and reporting stay separate.** They are pure functions over the facts, cross-run, and change more often
   than the runs (this whole drift analysis needed no re-run). The `bench report` failure is the cautionary example:
   a report that assumed a run shape broke every run.

## 6. How the analysis prompt (Prompt 2) changed

- Finds every finished run itself (READY / LIVE / BROKEN); live runs are listed as pending, not waited for.
- Never copies runs: it reaches them through directory junctions (verified to work with `bench verify` and `status`).
- Model judges only with `JUDGE = yes`.
- Four pages: run health and issues (including each CLI session's own problems, from its transcript); behaviour
  (drift, ceremony, over-thinking, the same model in two harnesses, both layers); cost; pack on vs off.

## 7. What happens next

1. **You:** choose for B10 (recommended C + A), B12, B14, B16 (recommended B); log in the extra Grok homes if you want Grok in parallel.
2. Re-run Codex with the fixed profile (B13), with context pinned per I7.
3. When agy and Grok finish: paste Prompt 2 for the full analysis pages.
4. Pack track (B15) in the ai-forward repo.
5. Instrumentation I1-I3, I6 before the next comparison run.
