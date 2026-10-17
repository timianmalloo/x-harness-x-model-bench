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
  The interactive mode (`bench interactive prepare | collect | gather | report`): one prepare builds a pack-off and a
  pack-on folder per CLI (every lean task, the latest pack), the operator pastes the same text into every window, and
  each session works the lean tasks one at a time through `.bench/next.py`. When a session closes its last task, next.py
  starts that arm's grading: the bench's own graders on a replay (the discriminate path), tokens and tool calls from the
  session's own record, and the arm's report opened in Chrome. `gather` re-reads the records after exit for the
  cross-CLI comparison. Smoke evidence from four CLIs on 2026-10-14 and the mode's limits.
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

The operator's changes (2026-10-15): prepare takes every lean task (the lean ring's list) and the latest pack (HEAD of
`../ai-forward`) by default, and several CLIs in one call (`--harness claude, codex, copilot`). Each session grades
itself and ends with its report open in Chrome. The analysis prompt only gathers the graded runs and compares them.

## 2. How it works

| Step | What happens | Code |
|---|---|---|
| prepare | One run per CLI named in `--harness` (commas, spaces or both; `claude` = `claude-code`), all with one time stamp. Tasks default to the lean ring's list (`bench/rings/lean.yaml`), the pack to HEAD of `../ai-forward`. `<out>/<run>/off/` and `.../on/`: each is one git repository with `tasks/<ID>/` (the base tree from `workspace.task_source`, never the hidden tests) and `.bench/` (`next.py`, `queue.json`, `grade.json`). `on` gets the pack through `workspace.install_pack`. `off` is checked to hold no instruction file. Both arms get the bench's line-ending rule (`* text=auto eol=lf`) in `.git/info/attributes`, which outranks the pack's `.gitattributes`. Prepare then refuses (HB-PRE-013) arms whose `tasks/` files differ in line endings (ARM-FAIR-A). Task trees hold only the files the source commit tracks. Each arm gets `.venv` (git-excluded), made from the `python` the operator's shell resolves to (`session_python`; HB-PRE-014 when there is none). HEAD after prepare is the arm's base. | `interactive.prepare`, `harnesses`, `default_tasks`, `latest_pack` |
| session | The operator launches the CLI in each folder and pastes `interactive.PASTE` (the page shows it verbatim; a test keeps the two equal). `next.py` hands out one task at a time and stamps start and end times. Closing an item first copies its task folder to `.bench/snapshots/<ID>/turn-<n>/`: the task as handed off, which collect grades. Closing an item also commits that task's folder, and only that folder, with hooks off. A later task's `git stash` or reset therefore cannot take the work. The sha, or why there is none, goes to `state.json`, and a failed commit becomes a report warning (TASK-ISO-A). It prints UTF-8 and records the interpreter that ran it; collect warns when that was not the arm's `.venv`. A record belongs to the arm it states it was launched in, and a task boundary is a `next.py` call whose time window holds a hand-out in `state.json` (REC-ATTR-A). | `interactive_next.py` |
| session: grading | The `next.py` call that closes the last item starts `grade.json`'s command, `bench interactive collect <run> --arm <arm> --open`, detached (a new hidden console and process group, out of the CLI's job where allowed), with its output in `<run>/grade-<arm>.log`. It prints nothing, so the session is not told it is graded; `state.json` records the start or why it did not start. A later call does not start it again. | `interactive_next._grade` |
| collect: grade | Each task is graded as handed off (TASK-ISO-A). Its overlay is `next.py`'s copy from the hand-off, every file of it. Base files the copy lacks are reported as deletions the replay cannot make. Files the final tree changed after the hand-off, a later task's edits, are not graded and are reported as a warning. With no copy, the overlay is the task's changes against the base in the final tree (committed or not, plus new files). That is the item still open at the end, or an arm prepared before 2026-10-16. When such an item was closed, collect warns. A two-turn task gets `turn-1/` and `turn-2/`, each from its own copy. A replay run applies the overlays through the real engine, the synthetic agent and the in-run grading pass, which is the path `bench discriminate` uses. Scores come from `readiness.run_scores`: correctness, the property check and the change-set drift scores (`scope_creep`, `drift_task_implied_lines`, `drift_machine_lines`). Files changed outside `tasks/` and `.bench/` are listed. | `interactive.build_overlays`, `replay`, `outside_task_folders` |
| collect: session | The session's records are found under the CLI's home by the arm path (`find_records`) or given with `--record`. Each is read by the harness's reader; agy's conversation db is read by `agy.read_db`. Model and tool calls are split per task at the `next.py` calls (`split`). | `interactive.read_session`, `session_metrics` |
| collect `--open` | The arm's own report, `<run>/collect/<arm>/report.md`, rendered to HTML and opened in Chrome. A failed grading opens `<run>/grade-<arm>-failed.md` instead. | `cli.cmd_interactive`, `interactive.report(only=arm)` |
| gather | After every CLI has exited: re-read the session records each graded arm's grading found (the search runs again only for an arm whose grading found none, because a new search also matches any later session that named the arm folder, as this session's own transcript did in the 2026-10-15 smoke) and write each run's two-arm `interactive-report.md`. An arm not graded is listed, not graded. | `interactive.gather`, `refresh_session` |
| report | The collected arms side by side: scores, drift, minutes, session tokens, per-task tokens, served settings, tool failures and the non-zero exits among them, pack hook events, hook seconds, pack hook seconds, model and tool seconds, warnings. | `interactive.report` |

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

Hook time and failure kinds (2026-10-17):
- **Hook seconds.** The report gives the time inside every hook the record times. That covers pack and user-level
  hooks together, so the pack's share is on minus off. Only Copilot times every hook, with `hook.start` and
  `hook.end` pairs. In run `int-copilot-20261015T1529` that was 182.2 s over 250 hooks (on) and 1.1 s over 4 hooks
  (off). Claude Code keeps no start for a hook, and Codex records none, so both read `not recorded`, never 0.
- **Pack hook seconds.** From pack revision 109, the pack's dispatcher times itself. `prepare` creates
  `.git/ai-forward/hook-times.jsonl` in both arms, and each dispatch appends one line: host, event, hooks, start, ms
  and exit. The report sums them for every harness, Claude Code included. The time runs from the dispatcher's
  `main()` to its exit, so the host's `git -> sh -> python` launch is outside it, and Copilot's own hook seconds are
  the larger figure. A pack-off arm reads 0 dispatches. An arm prepared with an older pack reads `not recorded`.
- **Model and tool seconds.** These use the per-cell views' rule: the union of the call spans across all of a
  session's records. A model call with no start makes model time `not recorded`, never a partial sum.
- **`tool_failures_exit`.** These are the `tool_failures` that were a command that ran and exited non-zero: a
  `grep` with no match, or a test run expected to fail. In the 2026-10-15 runs they were 26 of 27 failures (Codex
  on) and 18 of 22 (Copilot on). So `tool_failures` alone is not agent error.

## 4. Limits

- One session per arm and CLI, one repetition: a paired observation per task, never a significance claim.
- Context carries from task to task in a fixed queue order, the same in both arms. This mode is not comparable with
  the headless runs.
- The pack's per-message rules fire once for the whole paste (one user message), not once per task.
- An overlay cannot replay a deleted file. Collect lists deletions as a warning, and the deleted file stays in the
  graded tree.
- The catalog's process metrics (catalog 0.9) and `attention_drift` need a record per cell and are not graded in this
  mode. Collect reports tool calls and failed tool calls per task from the session record instead.
- The session's own grading reads its record while the session is still open, so the last turns are missing. Copilot
  writes usage as a session summary at exit, so its local report has no tokens and its per-task tokens are `not
  recorded`. `gather` re-reads every record after the CLIs exit; the comparison uses those numbers.
- The detached grading survives the tool call. Whether it survives the CLI's exit depends on the CLI's job object
  (not measured per CLI), so the operator exits only after the report has opened. If none opens, the log names the
  failure and `collect --open` reruns it.
- The installed CLI builds are newer than the bench's pinned builds. The context windows measured for the pins
  (Codex 872000, Copilot `long_context`) are read back from each record where it carries them: Codex's context
  tokens, Copilot's tier. Claude Code and agy record no window.
- Copilot starts on its default model (`gpt-5.5`), so the operator picks `gpt-6.1-sol` in
  each window's model picker before pasting (the operator, 2026-10-16; both 2026-10-15 records show the `startup`
  model `gpt-5.5`, then a `model_picker` switch). The report warns when the arms were served different models
  (`served_model_warnings`).
- The paste approves every tool call (each CLI's own flag, the same in both arms), because one paste runs
  unattended.
