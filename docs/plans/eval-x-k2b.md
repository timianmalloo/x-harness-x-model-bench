---
id: plan-eval-x-k2b
title: "X-K2b: alarm and liveness plan record"
type: doc
owner: "@timianmalloo"
status: proposed
summary: "X-K2b (alarm check, last_progress_at, resume history, bench-status/2) across K1 to K4: commits, mutants, findings."
tags: [evaluation, coordination, execution-graph, resume]
links:
  - {to: brief-eval-x-j1, rel: relates-to}
review-by: "2026-10-20"
---

# X-K2b: alarm and liveness plan record (T1)

Branch `build/eval-x-k2b`. Three sessions built it: part 1 (K1 skeleton `8b2eef4b`), part 2 (K2 red tests `319a525c`), part 3 (this record: K3, K4, gates; session `x-k2b4-e1e4`, Claude Code Sonnet; planned Agy gemini-3.8-flash-high, reason RUN-IDENTITY after the Agy part 1 split). Sources: W1-K `docs/design/eval-resume.md` sections 2, 6.1, 6.2, 8, 13; W0 rev 6.14 R6.14a, R6.14b.

## 1. Commits

| Item | Commit | What |
|---|---|---|
| K3 views | `8886654f` | `views.resume_history` and `ResumeRecord`, derived per engine segment that holds `run.resumed` |
| K3 status | `2a19dd5f` | `status.last_progress_at`, `bench-status/2` (`parse` reads `/1` and `/2`), `resumes`, `never_launched`, docstring fixed to D-K5; seam fallback: the start-benchmark skill names the three new fields (3 copies) |
| K3 alarm | `f5c74c16`, `03e3afce` | `alarm.check` (HB-ALM-001, HB-ALM-002; `resume.has_work` imported); the plan is read through `views.load` (reader table) |
| K3 cli | `d6f6a0ee`, `7a2df873` | `--alarm-after` exits 6 with `HB-ALM-00x: <cause>` on stderr, `--json` adds `alarm`, `bench plan` prints the one `--alarm-after` number |
| K4 | `1d71a235` | `tests/mutations/alarm.json` (8 mutants), `test_gap_equal_to_the_threshold_is_silent`, the native real-command to alarm-task test |

Order note: status landed before alarm because `alarm.check` calls `status.last_progress_at`.

## 2. Mutants (alarm.json)

| Mutant | Killed by |
|---|---|
| M-HEARTBEATONLY | `test_free_lock_with_work_exits_6_alm_001` |
| M-GE | `test_gap_equal_to_the_threshold_is_silent` |
| M-UNITS | `test_stale_progress_exits_6_with_alm_002` |
| M-ZEROISOK | `test_unreadable_progress_fails_closed` |
| M-PENDINGONLY | `test_pending_zero_does_not_raise_alm_002` |
| M-ALARMPENDING | `test_alarm_has_no_pending_logic_of_its_own` |
| M-NAMESORT (status.py) | `test_last_progress_ignores_segment_name_order` |
| M-STOPEXEMPT | `test_mid_stop_crash_alarms` |

## 3. Findings

- **Seam, X-K2a (`tools/alarm-task.ps1`).** The script runs `bench status ... --json 2>$null` under `$ErrorActionPreference = 'Stop'`. In powershell.exe 5.1 a native command's stderr line becomes a `NativeCommandError`, so the real command's `HB-ALM-00x:` line makes the script exit 1 ("check-error") instead of 6. The K2a stub never writes stderr, so its tests could not see it. The K4 native test redirects stderr inside its `bench.cmd` wrapper as the fallback. Fix for the owner: set `$ErrorActionPreference = 'Continue'` around the call (or redirect inside a `cmd /c`).
- **Seam, start-benchmark skill.** `test_the_skill_names_every_status_field` forces the new status fields into the skill; the three copies are edited as a fallback (precedent `33e827a9`); drop at join if the skill owner lands it.
- **Not built:** the last row kind in the ALM-002 message (W1-K 6.2 lists it); the message carries the gap, the threshold and the last progress time.
