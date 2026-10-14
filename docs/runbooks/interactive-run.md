---
id: runbook-interactive-run
title: "Runbook: the interactive run - one operator CLI session per arm, graded by the bench"
type: doc
status: draft
owner: "@timianmalloo"
tags: [runbook, lean, interactive, session-layer, agy, copilot]
links:
  - { to: runbook-lean-comparison-run, rel: relates-to }
  - { to: adr-0026-per-cell-anatomy-facts-catalog-0-8, rel: depends-on }
review-by: "2027-04-14"
summary: >-
  The interactive mode (`bench interactive prepare | collect | report`): the operator launches a CLI in a pack-off and
  a pack-on folder, pastes the same text into both, and each session works the lean tasks one at a time through
  `.bench/next.py`. The bench grades each task folder with its own graders on a replay (the discriminate path) and reads
  tokens and tool calls from the session's own record, split per task at the next.py calls. Smoke evidence from four
  CLIs on 2026-10-14 and the mode's limits.
---

# Runbook: the interactive run

The prompt page is `docs/benchmarkpromps/interactive-benchmark-prompt.html`. The headless run
(`lean-benchmark-run-prompt.html`, `runbook-lean-comparison-run`) stays as the automated alternative.

## 1. Why this mode

The operator's concern (2026-10-14): a headless cell (`claude -p`, `codex exec`, `copilot -p` behind the adapter) is
one fresh process per task. A developer instead works in one interactive session that runs for hours. Sub-agents in
one session were rejected, because the pack is loaded once, at CLI startup, from the folder. A sub-agent inherits its
parent's setup, so one session cannot hold both arms. The operator chose (2026-10-14): one paste per arm, one
repetition, and the headless prompt kept as the alternative.

## 2. How it works

| Step | What happens | Code |
|---|---|---|
| prepare | `<out>/<run>/off/` and `.../on/`: each is one git repository with `tasks/<ID>/` (the base tree from `workspace.task_source`, never the hidden tests) and `.bench/` (`next.py`, `queue.json`). `on` gets the pinned pack through `workspace.install_pack`. `off` is checked to hold no instruction file. HEAD after prepare is the arm's base. | `interactive.prepare` |
| session | The operator launches the CLI in each folder and pastes `interactive.PASTE` (the page shows it verbatim; a test keeps the two equal). `next.py` hands out one task at a time and stamps start and end times. When it hands out turn 2 of a two-turn task, it first snapshots the task folder as turn 1. | `interactive_next.py` |
| collect: grade | Each task's changes against the base (committed or not, plus new files) become an overlay. A two-turn task gets `turn-1/` (the snapshot) and `turn-2/` (the final tree). A replay run applies the overlays through the real engine, the synthetic agent and the in-run grading pass, which is the path `bench discriminate` uses. Scores come from `readiness.run_scores`. | `interactive.build_overlays`, `replay` |
| collect: session | The session's records are found under the CLI's home by the arm path (`find_records`) or given with `--record`. Each is read by the harness's reader; agy's conversation db is read by `agy.read_db`. Model and tool calls are split per task at the `next.py` calls (`split`). | `interactive.session_metrics` |
| report | Both arms side by side: scores, minutes, session tokens, per-task tokens, served settings, pack hook events, warnings. | `interactive.report` |

The end-to-end test (`tests/test_interactive.py`) plays the fixture two-turn task's reference solution in one arm and
its naive solution in the other, through the real path. It requires the scores the fixture declares
(`property_check_pass` 1 and 0; `rework_ratio` 0.2500 and 1.0000), the same values `bench discriminate` reproduces.

## 3. Evidence: smoke runs, 2026-10-14

Task X1 (slugify), with each CLI's non-interactive mode in an arm folder. Non-interactive mode writes the same record
format as interactive mode (Inferred, by format; the readers read both).

| CLI (installed build) | Arm | Record found by path | X1 hidden tests | Per-task split | Check |
|---|---|---|---|---|---|
| Claude Code 2.1.300 | off, on | yes, the project transcript | 1, 1 | yes | pack hook events 0 (off), 1 (on): the pack's Stop hook ran in the on arm only |
| Codex 0.162.1 | off | yes, the rollout | 1 | yes | served context 872000 read from the record |
| Copilot 1.0.97 | off | yes, `events.jsonl` | 1 | session totals only | totals equal Copilot's own printed summary: input 24 + 179,581 + 29,844 = 209,449 ("209.4k"), output 1,069, reasoning 110 |
| agy 1.3.4 | off | yes, the conversation db | 1 | yes | usage from `steps.metadata` field 9 |

The agy field map was Verified against the lean run of 2026-10-13. Its 60 cells hold both the stream and the db, and
1,542 stream model calls equal 1,542 db rows field by field (9.2 uncached input, 9.3 output, 9.5 cache read,
9.9 thinking; absent = 0; no cache-write bucket).

What the smoke changed: both Claude Code arms ran the operator's own user-level Stop hook (`wtcli.exe`). Copilot's
pack-off record held four lifecycle hook rows (`sessionStart`, `agentStop`, ...) that name no command. So the report
counts **pack** hook events, those whose command runs a script under `docs/ai-forward-pack/`. The count is `not
recorded` for Copilot (event names only) and for Codex and agy (their readers record no hook events).

## 4. Limits

- One session per arm and CLI, one repetition: a paired observation per task, never a significance claim.
- Context carries from task to task in a fixed queue order, the same in both arms. This mode is not comparable with
  the headless runs.
- The pack's per-message rules fire once for the whole paste (one user message), not once per task.
- An overlay cannot replay a deleted file. Collect lists deletions as a warning, and the deleted file stays in the
  graded tree.
- The catalog's process metrics (catalog 0.9) need a record per cell and are not graded in this mode. Collect reports
  tool calls and failed tool calls per task from the session record instead.
- Copilot writes usage as a session summary at exit, so its per-task tokens are `not recorded`. The operator must
  exit each CLI before collecting.
- The installed CLI builds are newer than the bench's pinned builds. The context windows measured for the pins
  (Codex 872000, Copilot `long_context`) are read back from each record where it carries them: Codex's context
  tokens, Copilot's tier. Claude Code and agy record no window.
- The paste approves every tool call (each CLI's own flag, the same in both arms), because one paste runs
  unattended.
