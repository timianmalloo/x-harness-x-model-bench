---
id: plan-benchmark-instrumentation-2026-10-14
title: "Benchmark instrumentation for drift, tool use and the Codex/Copilot contradiction"
type: plan
status: done
owner: "@timianmalloo"
summary: "Every new and owed improvement from the 2026-10-13 lean-run analysis, as seven parallel work tracks, built before the next comparison run. Goal: the next run answers 'does GPT drift more in Copilot than in Codex' from measured facts at both layers, with the confounds removed or measured."
tags: [lean-benchmark, instrumentation, drift, tool-use, codex, copilot, plan]
links:
  - { to: plan-lean-runs-2026-10-13-findings-and-repair, rel: relates-to }
  - { to: runbook-add-a-harness, rel: relates-to }
review-by: "2026-10-28"
---

# Benchmark instrumentation for drift, tool use and the Codex/Copilot contradiction

**Goal.** Before the next comparison run, the bench measures, for every harness, the facts that decide whether a model
drifts or over-works more in one harness than another, at both layers (the headless cells and your interactive
sessions). The known confounds are removed or measured.

**Done when.** Every row below is merged to `main` with its tests red-then-green. The full suite, the stamped tier and
the gate ring pass. The behaviour page, run on the existing six runs, shows the new columns, or "not recorded" with the
reason where an old run cannot supply them.

**Not in scope.** The re-run itself (you run it after this lands). Grok: skipped in the re-run; a different Grok model
later (so B14, Grok's effort, is moot).

**Decisions (made 2026-10-14, now in scope):**

| # | Decision | Track |
|---|---|---|
| B10 | Copilot path blocks: shorten cell paths (no repeated run id), and label what remains "harness path limit" with its own validity text, never a model fault | W9 |
| B12 | Codex personal skills: isolate the Codex home per cell (spike first: login and the pinned model still work) | W10 |
| B13/A2 | Context: pin both Codex and Copilot at the highest window both actually serve, measured from their own session records. Codex's catalog allows up to 872k (served 500k by default); Copilot served 922k; the model's own maximum is 1.05M (OpenAI docs as quoted by Codex; not verified here) | W6 |
| B15 | Pack costs: fix in the ai-forward repo (one hook dispatcher per event, skip coordination hooks when coordination is off, logs outside the task folder), then update the pack here | W8 |
| B16 | agy `schedule` counts as turn control (`meta`), like `wait`; amend the agy-meta ruling; regrade the agy run | W3 |

**How it runs.** Seven tracks in parallel, each in its own worktree and branch, then one integration branch, the gates,
and a merge to `main`.

## The work

Status: *Owed* = already listed in the 2026-10-13 plan; *New* = added from the follow-up review. "Exists" means the code
already computes it and only the behaviour page lacks it.

| # | Improvement | What it settles | Was | Track |
|---|---|---|---|---|
| A2 | Pin the same context and effort in a comparison (I7) | Codex served 500k context, Copilot 922k: settings are a confound | Owed | W6 |
| A3 | Transport control: Copilot over ACP vs `copilot -p` at the same context | Whether Copilot's extra tool calls come from `-p` re-orienting each turn | Owed | W6 |
| A4 | Run the interactive sessions from a folder without the pack | The sessions were all effectively pack-on (the repo's AGENTS.md) | New | W6 |
| A5 | More than one interactive session per CLI | The session layer is n=1 | New | W6 |
| A6 | A "supervise a long job" task in the cell catalog | Moves polling and skipped steps from the sessions into scored cells | New | W7 |
| A7 | First-request input split; Copilot's tool catalogue size (I6) | "The harness sends more" vs "the model does more" | Owed | W5 |
| A8 | Spread (IQR, min-max) next to medians | Whether the gaps exceed the noise between repetitions | New | W1 |
| B1 | Classify Codex shell commands as read / edit / test / other (I1) | Codex's attention drift is "not recorded" today | Owed | W2 |
| B2 | `tool_inputs` readers for agy and Grok (I8) | Attention drift is "not recorded" for both | Owed | W3 |
| B4 | Name the files behind discretionary lines | Codex 0 -> 38 lines pack-on; Copilot 16.5 even pack-off | New | W1 |
| B5 | Outside reads before vs after the first edit | Exploration vs wandering | New | W1 |
| B6 | Session compliance, measured: polling interval vs asked, steps done vs required, HANDOFF without handoff.json | Instruction drift is read by hand today | New | W1 |
| C1 | Show `tool_error_rate` and `stuck_loops` | Flailing vs thoroughness (graded in `grade/process.py`, not shown) | New (exists) | W1 |
| C2 | Re-reads per cell | Over-thinking signal (`tool_phases.rereads`, not shown) | New (exists) | W1 |
| C3 | Assistant text per cell (chars, messages) and planning/to-do calls (I2) | Ceremony is inferred today | Owed | W4 (Claude, Codex, Copilot), W3 (agy, Grok) |
| C4 | Per-tool hook time for every harness (I3) | Grok's pack hooks add 11-18 s a call; Claude records only Stop hooks | Owed | W5 |
| C5 | Tool-result bytes for every reader | Context eaten per call (`tool_phases.bytes_returned`, often not recorded) | New | W4, W3 |
| C6 | Reasoning tokens per tool call | Thinks-a-lot vs acts-a-lot | New | W1 |

## Tracks

| Track | Rows | Files it owns | Depends on |
|---|---|---|---|
| W0 (me) | the shared contract | `telemetry/__init__.py` `ProcessTrace`: `assistant_chars`, `assistant_messages` (default None = not recorded) | - |
| W1 | A8, B4, B5, B6, C1, C2, C6 | `tools/behaviour_measures.py`, its tests, Prompt 2's behaviour page | W0; reads W2-W4 output when merged |
| W2 | B1 | `telemetry/codex.py` (shell classification), `grade/drift.py` (per-call read class) | - |
| W3 | B2, B16, and C3/C5 for agy and Grok | `telemetry/agy.py`, `telemetry/grok.py`, `report/tool_phases.py` `TRACE_READERS` | W0 |
| W4 | C3, C5 for Claude, Codex, Copilot | `tool_inputs` in `telemetry/claude_code.py`, `codex.py`, `copilot.py` | W0 |
| W5 | C4, A7 | hook-time and first-request facts (spike first) | - |
| W6 | A2, A3, A4, A5 | Prompt 1, profiles/builds for a pinned context and an ACP Copilot control, a runbook | - |
| W7 | A6 | a new task under the task catalog, by the add-a-task rules | - |
| W8 | B15 (and B7) | the ai-forward repo's hooks; then the pack update in this repo | - |
| W9 | B10 | the cell path layout; HB-VAL-004 path-limit labelling | - |
| W10 | B12 | Codex cell home isolation (`profiles/codex.yaml`, seeding) | - |

Rules for every track: red-first tests; run only the touched test files (the integration runs the full suite once);
no gate or stamp renewal in a track; commit on the track's branch only; report what was measured, not inferred.

## Integration

1. Merge W0 then W1-W7 into `integrate/instrumentation` in dependency order; resolve conflicts there.
2. Full suite, stamped tier, gate ring.
3. Run the behaviour page on the six 2026-10-13 runs; check every new column has a value or a reason.
4. Merge to `main`, push, and update this plan with the results.

## Progress

All tracks are merged into `integrate/instrumentation` (2026-10-14). Measured results are from the 2026-10-13 runs, read
with the new code. Tracks W11-W18 were added during the work to close gaps the first tracks found.

| Track | What landed | Measured |
|---|---|---|
| W0 | `ProcessTrace.assistant_chars` / `assistant_messages` | - |
| W1 | Behaviour page: error rate, stuck loops, re-reads, bytes, reasoning per call, spread (IQR, min-max), files behind discretionary lines, reads before/after the first edit, session compliance proved on disk | Codex session: status checks every 1.1 min against 10 asked, 6 of 11 steps on disk, HANDOFF without handoff.json; Copilot 6.1: 10 of 11 |
| W2 | Codex shell commands classed read/edit/test/other per call; batched and escaped commands parsed | Codex attention drift on 60 of 60 cells (was 0): mean 0.41 off, 0.74 on |
| W3 | `tool_inputs` for agy and Grok; agy `schedule` is turn control (B16) | Grok attention drift 0.23-0.64; agy needs the session fallback (in W2) |
| W4 | Assistant text and tool-result bytes for Claude, Codex, Copilot; a Codex double read fixed | Median assistant chars off/on: Codex 975/3,136, Copilot 6.1 743/1,476, Claude 2,903/3,372 |
| W5 | Grok hook time per run; Claude printed hooks; Grok skills part | Grok pack hooks: median 4.9 s per tool call |
| W6 | Prompt 1: Codex 872k / Copilot 922k pins, launch from `C:\Projects\bench-launch`, 2 sessions per CLI | Codex serves at most 828,400 (872k); Copilot offers only 272k or 922k |
| W7 / W11 | SV1, the supervise-a-long-job task; in the lean runs (66 cells) with its own rows | Primary verdict unchanged on all five runs |
| W8 | Pack revision 102 (ai-forward `0900e78`, pushed): one hook process per event, coordination hooks idle, fallback audit writes jsonl only | Hook chain per call 0.9-1.4 s -> 0.16 s; audit lines per pack-on cell 510 -> 1 |
| W9 | Shorter cell paths; Copilot path denials labelled HB-VAL-012 (harness path limit) | Worst-case path 303 -> 238 chars; all 9 cells relabelled |
| W10 | Codex cells cannot see `~/.agents/skills` (disabled per file in the cell config) | Real `codex exec`: no operator skills listed |
| W12 | Copilot transport is a combo option (`transport: acp`) | Real 2-cell run: both valid |
| W13 | Per-call outcome for Codex and agy | Error rate Codex 21%, agy 12% |
| W14 | Copilot tool catalogue size (2,187 tokens); Copilot non-zero exit = failure; Codex write paths; stale docs | Copilot 6.1 failed shell calls 16 -> 276 |
| W15 | Catalog 0.9: the six process metrics graded on every task and in the composite | 0.8 runs stay 0.8; comparing across versions is refused |
| W16 | Copilot HOME/USERPROFILE at the cell home, `--add-dir {home}` | `$env:USERPROFILE` commands no longer denied |
| W17 | Copilot cells trust their worktree; the host uv store is an allowed directory | Real pack-on cells: 39-40 hook events each (0 before); pack-off 0 |
| W18 | Status counts a resume-closed cell as ended; a Grok policy-denied call is a refused attempt | Grok run: 60/60 ended; the `web_fetch` cell valid with a warning |

**Found on the way and fixed at integration:** catalog 0.9 re-frozen on the merged tree; `bench campaign baseline` named
catalog 0.7 (refused every real tree since 0.8, PIN-D); the PreToolUse guard now refuses a .NET file call on a relative
path (PATH-A, two instances); mutation entries and contract pins moved by tracks (PIN-C).

**What this changes about the 2026-10-13 results:** Copilot's pack-on cells ran without the pack's hooks (untrusted
folder); every Codex cell was invalid for bench reasons; Copilot's `ok` meant "the tool ran". Do not compare those runs
with today's naively: today's runs are graded under catalog 0.9 and run pack revision 102.

**Residuals (measured limits, not gaps):** Codex 872k vs Copilot 922k (a 5% nominal gap the CLIs set); Claude records a
tool hook's time only when the hook prints; Copilot and agy record no hook time; agy records no tool-result size.
