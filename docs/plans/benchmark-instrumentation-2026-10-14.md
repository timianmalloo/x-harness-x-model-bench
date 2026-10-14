---
id: plan-benchmark-instrumentation-2026-10-14
title: "Benchmark instrumentation for drift, tool use and the Codex/Copilot contradiction"
type: plan
status: in-progress
owner: "@timianmalloo"
summary: "Every new and owed improvement from the 2026-10-13 lean-run analysis, as seven parallel work tracks, built before the next comparison run. Goal: the next run answers 'does GPT drift more in Copilot than in Codex' from measured facts at both layers, with the confounds removed or measured."
tags: [lean-benchmark, instrumentation, drift, tool-use, codex, copilot, plan]
links:
  - { to: plan-lean-runs-2026-10-13-findings-and-repair, rel: derives-from }
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

**Not in scope.** The re-run itself (you run it after this lands). The four decisions (B10 Copilot path checks, B12
Codex personal skills, B15 the pack track in the ai-forward repo, B16 agy `schedule`). Pack changes in the ai-forward
repo.

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
| W3 | B2, and C3/C5 for agy and Grok | `telemetry/agy.py`, `telemetry/grok.py`, `report/tool_phases.py` `TRACE_READERS` | W0 |
| W4 | C3, C5 for Claude, Codex, Copilot | `tool_inputs` in `telemetry/claude_code.py`, `codex.py`, `copilot.py` | W0 |
| W5 | C4, A7 | hook-time and first-request facts (spike first) | - |
| W6 | A2, A3, A4, A5 | Prompt 1, profiles/builds for a pinned context and an ACP Copilot control, a runbook | - |
| W7 | A6 | a new task under the task catalog, by the add-a-task rules | - |

Rules for every track: red-first tests; run only the touched test files (the integration runs the full suite once);
no gate or stamp renewal in a track; commit on the track's branch only; report what was measured, not inferred.

## Integration

1. Merge W0 then W1-W7 into `integrate/instrumentation` in dependency order; resolve conflicts there.
2. Full suite, stamped tier, gate ring.
3. Run the behaviour page on the six 2026-10-13 runs; check every new column has a value or a reason.
4. Merge to `main`, push, and update this plan with the results.

## Progress

Updated by the session as tracks land.

| Track | State |
|---|---|
| W0-W7 | starting |
