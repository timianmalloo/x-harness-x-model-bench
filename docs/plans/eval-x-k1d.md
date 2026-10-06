---
id: plan-eval-x-k1d
title: "X-K1d: exit-evidence table and plan record"
type: doc
owner: "@timianmalloo"
status: proposed
summary: "X-K1 (resume engine) exit evidence across K1a to K1d: acceptance items, mutants, simplifications, R1-R3, dispatches."
tags: [evaluation, coordination, execution-graph, resume]
links:
  - {to: brief-eval-x-j1, rel: relates-to}
review-by: "2026-10-20"
---

# X-K1d: exit-evidence table and plan record (T2)

Branch `build/eval-x-k1d`. Integration base `8534dd12`. Part 2 tip `f5c63273`. This turn's commits: R1 `c6118acf`, R2 `dfa5f614`, R3 `75b1c264`. No `src/` line changed in this turn. Sources: `docs/coordination/eval-wave2-e234/x-k1.md` (acceptance items), W1-K `docs/design/eval-resume.md` (sections 4 (d), 7, 8), Coordinator #47 rulings CR47-11 to CR47-14.

Evidence labels: **Observed** = a command run in this turn and read. **From commit log** = taken from the commit subject; the node was not re-run singly, but the 11-file gate below ran every node (693 passed, 0 failed, 0 XPASS). **Inferred** = the commit that turned the item green is read from commit subjects, not from a per-commit run.

## 1. Acceptance items 1 to 6 (x-k1.md)

| # | Item | Node ids | Turned green by | Label |
|---|---|---|---|---|
| 1 | Kill in each state, then resume, for every ADR-0021 section 4 row (per-turn rows, turn-1 snapshot-crashed row) | `tests/test_resume.py::test_window[...]` (W1-W16 parameters), `test_every_ledger_prefix_matches_the_adr_table`, `test_every_two_cell_ledger_prefix_matches_the_adr_table`, `test_resume_of_a_resume[W13]` | Reds `61561f15`, `644a8107`; classifier `2a5abc09` (K4); recovery `99c06fc5` (K5a); engine path `3d435574` (K6); markers dropped `4edeed52` `903fc67b` `da8f7c37` `dc787d48` `ab5f0407` `8360b23f` | Inferred (green) / Observed (final gate) |
| 2 | Resume after a stop exits 3 with HB-RUN-008; refusals HB-RUN-005, HB-IDN-001, HB-RUN-009 (naming the segment); `segment.abandoned`; per-launch disk check (HB-RUN-004) | `test_resume_finishes_the_stop[...]`, `test_refusal_order`, `test_abandoned_marker_pins_head`, `tests/test_engine.py::test_disk_low_stops_launching_before_the_intent`, `test_other_stop_rows_are_unchanged` | Refusals `f8b3e067` (K5b); abandoned `63b4ce42` (F9); disk check `fbc2fc86` (K6b), reds `46e62ea9` `6149b8e2`; T-32 fixture `c6118acf` (R1) | Inferred / Observed |
| 3 | `recover_archive` holds no second comparison; returns W1-B's `Recovery` from `append_missing_rows` (DM7) | `tests/test_archive.py`, K5 recovery states in `tests/test_resume.py` | `99c06fc5` (K5a), red `6bfe1dff` | Inferred / Observed |
| 4 | Real-CLI kill tests green (W2, W3, W3b, W6, W11, `test_cli_run_resumes[T2]`) through the `cmd_run` delegation | `tests/test_resume.py::test_cli_run_resumes[T2]` and the real-child kills `571042ee`; `tests/test_cli.py::test_run_refuses_a_run_that_already_started` | Delegation in K1a (`aa8c3883`); real config injected `f8b3e067`; engine continuation `3d435574`; telemetry on the CLI path red `f9e9abe0`, green `08525be5` | Inferred / Observed |
| 5 | One definition of work left: `resume.has_work` (stop row inside it, D-K4); alarm and `bench status` import it | `test_finished_stop_is_silent`, `test_alarm_fires_after_crash_in_grading`, `test_alarm_fires_after_crash_before_last_archive`, `test_launch_stop_alarms` (named in x-k1.md; the alarm half is X-K2's) | `2a5abc09` (K4), `ab9cef31` (one `lifecycle.completed`), red `526f5944` | Inferred. The alarm-side nodes belong to X-K2; this branch's gate does not include `test_alarm.py` |
| 6 | W1-J provisional model branches settled by W1-K's TLC | none here (settled in the model, not in this branch) | not in scope of this branch | From x-k1.md |

## 2. resume.json mutants (W1-K section 4 (d))

Observed: `uv run python tools/mutate_check.py tests/mutations/resume.json` at tip `75b1c264`: exit 0, 24 killed, "every mutation killed", wall 43 s.

| Mutant | Killed by (node ids in resume.json) | W1-K row |
|---|---|---|
| M-SKIPARCH | `test_window[W9_archive_tmp]`, `test_window[W10a_rows_none]` | section 4 (d), archive recovery |
| M-NODISCARD | `test_window[W2_launched_not_prompted]` | section 4 (d), unprompted launch |
| M-NOREDO | `test_window[W4b_snapshot_event_absent_under_stop]`, `test_window[W4c_redo_fails]` | section 4 (d), snapshot redo |
| M-APPENDALL | `test_window[W5b_rows_partial]`, `test_window[W10b_rows_partial]` | section 4 (d), partial rows |
| M-WRITEOLD | `test_abandoned_marker_pins_head`, `test_resume_of_a_resume[W13]`, `test_the_resume_opens_new_segments_and_never_the_dead_one` (since `4d859200`) | section 4 (d), no write to the dead segment |
| M-ORDER | `test_refusal_order` | section 4 (d), refusal order |
| M-ORDINALCOUNT | `test_resume_of_a_resume[W13b_stray_segment]` | section 4 (d), ordinal from the highest stem |
| M-STOPONLYRUNSTOPPED | `test_resume_finishes_the_stop[control_applied]`, `[decision_resolved]` | stop predicate |
| M-LAUNCHSTOPPEDISSTOP | `test_launch_stopped_is_not_a_stop` | stop predicate |
| M-STOPCRASHREC | `test_resume_finishes_the_stop[run_stopped]` | finish the stop |
| M-STOPLAUNCHES | `test_resume_finishes_the_stop[run_stopped]` | finish the stop |
| M-STOPC7 | `test_resume_finishes_the_stop[run_stopped]` (since `4d859200`) | finish the stop, C7 cells |
| M-STOPNOGRADE | `test_resume_finishes_the_stop[run_stopped]` | finish the stop |
| M-DOUBLECOMPLETED | `test_finish_the_stop_is_idempotent` | idempotence |
| M-NOPENDINGSTOP | `test_finished_stop_with_unlaunched_cell_is_a_noop` | finished stop |
| M-ANYCOMPLETED | `test_resume_after_launch_stop[W16]` | launch stop |
| M-PIDREUSE | `test_recycled_pid_is_gone` | pid check |
| M-PIDKILL | `test_recycled_pid_is_gone`, `test_pid_alive_defers_and_writes_no_completed` | pid check |
| M-NOBEAT | `test_resume_heartbeats_the_lock` | heartbeat |
| C2/C3, C3/C5, C5/completed, C6/C2, C2/continued turn | `test_every_ledger_prefix_matches_the_adr_table`, `test_every_two_cell_ledger_prefix_matches_the_adr_table` | five sweep-only classifiers |

The W1-K section number per row is the section 4 (d) manifest as a whole; the per-row cell reference was not re-derived in this turn.

## 3. Named simplifications (part 2, `776731b0`)

Each is an inline `simplify:` comment with its ceiling and upgrade trigger; behaviour unchanged; untested by design.

| Where | Choice |
|---|---|
| `src/harness_bench/resume.py` (snapshot-redo adoption) | An already-published turn folder is adopted by file scan only (`_folder_rows`), not re-verified against the stored rows. |
| `src/harness_bench/resume.py` (outcome write) | A resume-written outcome goes through `Engine.append_row`, which skips `Engine._after_append`. |
| `src/harness_bench/engine.py` (restore) | Restored spend is the sum of `turn_usage` rows only; a turn that died before its usage row is not counted. |
| `src/harness_bench/resume.py` (scripted-user log) | `scripted-user.jsonl` is not closed for a reconciled cell, unlike the Engine's own path. |

(The `_folder_rows` docstring at `resume.py:207` also carries "files only; ceiling a snapshot with links".)

## 4. R1 to R3 (this turn)

| Item | Commit | Evidence |
|---|---|---|
| R1 (CR47-11) T-32 fixture: fake identity check returns `identity.CheckResult([], False)`, assertion `calls == [1]` | `c6118acf` | Observed red on arrival at `3181d0ac`: `assert len(stops) == 1 and calls == []` failed with `[1] == []`. Green after: 1 passed. Disk-stop row (kind, code, reason) unchanged. |
| R2 (CR47-12) cli.json "a started run re-run": find `    resuming = (run_dir / "events").exists()\n`, replace `    resuming = False\n` | `dfa5f614` | Observed: baseline `test_every_mutation_find_text_occurs_exactly_once_in_its_target_file` failed on arrival (cli.json 0 occurrences); after: `test_mutate_check.py` 48 passed. `mutate_check cli.json`: exit 0, 15 killed, every mutant killed (15 s). The killing test is not printed by `mutate_check`. |
| R3 (CR47-13) engine.json "launch after a stop": find the `if self.stopped: return` guard in `_launch` plus the next line; tests add `test_disk_low_stops_launching_before_the_intent` | `75b1c264` | Observed: `mutate_check engine.json`: exit 0, 109 killed, every mutant killed (311 s), including "launch after a stop". Assumption #1 held. |

Why the loop condition `while pending and not self.stopped and not self.broken and held` has no mutant of its own: it is a pre-filter. The `_launch` guard enforces NoLaunchAfterStop for every launch (including the disk stop `_launch` records itself), so removing the loop condition changes no observable behaviour and no test can kill it; the guard is the rule.

MUT-E controls after each commit: `tests/test_mutate_check.py` 48 passed and `tests/test_archive_readers.py` 2 passed, after `dfa5f614` and after `75b1c264`.

## 5. Other mutation files (observed at tip `75b1c264`)

| File | Result | Wall |
|---|---|---|
| `tests/mutations/stop.json` | exit 0, 74 killed, every mutation killed | 240 s |
| `tests/mutations/resume.json` | exit 0, 24 killed | 43 s |
| `tests/mutations/engine.json` | exit 0, 109 killed | 311 s |
| `tests/mutations/cli.json` | exit 0, 15 killed | 15 s |

## 6. Final gates (observed)

| Gate | Result |
|---|---|
| 8-file R-104 list (architecture, identity, atomic_sites, arms_guard, discriminate, mutate_check, skills_in_sync, timing_hygiene) at the base | exit 1, 202 passed, 1 failed: `test_every_mutation_find_text_occurs_exactly_once_in_its_target_file` (cli.json), on arrival; fixed by R2 |
| the same 8 files at the final code commit | exit 0, 203 passed |
| 11-file list (resume, archive_readers, archive, lifecycle, lifecycle_conformance, views, verify, status, engine, multiturn, cli) | exit 0, 693 passed, 0 failed, 0 XPASS (308 s) |
| `uv run ruff check src tests tools` | exit 0 |

## 7. X-K1d dispatches

| Part | Session | Closing audit entry | Outcome |
|---|---|---|---|
| 1 | `x-k1d-e1e4` | `al-01M498VHY7JRTYHZW3WGZEC2E7` | split, tip `08525be5` |
| 2 | `x-k1d-e1e4` | `al-01M49KRWAYB2V6BQ4EN3594R9P` | split, tip `f5c63273` (planned Codex gpt-6.1-sol; ran Claude Code Sonnet) |
| 3 | `x-k1d3-e1e4` | recorded at this turn's close (the id is in the Leader's join) | see the closing entry |

## 8. History repair and the re-observed reds

Part 1 recorded a `history_repair` (autosquash); its closing entry `al-01M498VHY7JRTYHZW3WGZEC2E7` holds the detail (not re-read in this turn). The red commits in scope are `6149b8e2` (K6b fixture and observed assertion reds) and `f9e9abe0` (telemetry red on the real CLI path). The Leader re-observes both reds at the join (CR47-6) and records them there. Not re-observed in this turn: this turn made no history change and does not run those reds.

## 9. Not done / open

- The Leader's join checks (reds at `6149b8e2` and `f9e9abe0`, T-SWEEP-1, whole suite, `--touched`) are not part of this turn.
- Acceptance item 5's alarm-side nodes live with X-K2.
- The "turned green by" column is read from commit subjects (Inferred), not from a per-commit run.
