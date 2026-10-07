---
id: brief-eval-x-k2
title: "Brief X-K2: liveness and the alarm (E3 build) - BLOCKED on W1-K"
type: plan
status: proposed
owner: "@timianmalloo"
links:
  - { to: coordination-eval-wave2-e234-briefs, rel: implements }
  - { to: design-eval-seam-contracts, rel: depends-on }
review-by: "2026-10-17"
summary: "X-K2 builds bench status --alarm-after, last_progress_at and the ntfy alarm channel (R-102), importing resume.has_work, on Agy gemini-3.8-flash-high in two turns. Blocked until W1-K passes its gate."
---

# X-K2: liveness and alarm

> **BLOCKED** on W1-K passing its gate (W1-K chooses the alarm channel, ADR-0021 §7, and fixes the runbook path). Also waits on X-C (E1 `status.py`, `cli.py`) and X-J1 (its one `status.py` hunk, W0 rev 6.5 R6.5b) joined. **Rev 6.9 (R6.9a, R6.9b):** X-K2a runs beside X-K1 (`tools/alarm-task.ps1`, `tests/test_alarm_task.py`, the runbook, `last_progress_at`; no `cli.py` edit, no pending logic). **X-K2b waits on X-K1 joined**: its `cli.py` edits rebase on X-K1's `cmd_run` hunk, and `alarm.check` and `bench status` import X-K1's `resume.has_work` (R-102).

**Harness** Agy, `gemini-3.8-flash-high` · **contract** `x-k2.contract.json` · **deadline** 3,300 s per dispatch · **budget** 140 calls · 150k · 2 dispatches · 2 h · **fallback** a Sonnet follow-on in the same tree (R-87 Option 1).

**Design:** W1-K (once gated); ADR-0021 §7; W0 rev 6.6 §9 (`alarm.py`: grade), §10 (the alarm guard row), §11 (HB-ALM-001..003), §13.

## Owned paths (E3 hub owner)
`status.py` (E3), `cli.py` (E3, **except** the `cmd_run` resume branch, X-K1's since W0 rev 6.9 R6.9a; rebase on X-K1's join first), `alarm.py` (new), `tools/alarm-task.ps1`, `tests/test_alarm_task.py` and `docs/runbooks/resume-and-alarm.md` (new; W0 rev 6.8 §13 with its four conditions), the `report/html.py` resume header hunk (second dispatch, after X-A3c and X-K1 join; W0 rev 6.8 §13), `tests/test_report_resume.py` (new), `tests/test_status.py` (E3), `tests/test_alarm.py` (new).

## Acceptance items
1. ADR-0021 §7, quoted: "`bench status <run_id> --alarm-after <seconds>` exits non-zero, naming the cause, when the heartbeat is stale **or** `now − last_progress_at` exceeds the threshold while cells are pending": the stale-progress fixture exits non-zero (HB-ALM-001, HB-ALM-002); the `last_alarm_check_at` warning (HB-ALM-003).
2. `last_progress_at` and elapsed read through X-J1's one "cell start" definition (R6.5b); no second clock.
3. The alarm channel as R-102 rules it (W0 rev 6.9 §13 R6.9b): ntfy push primary and required for an unattended run; the edge state file, the delivery log, and the `try/catch` that never prints the topic; `test_push_failure_does_not_print_topic` and "two runs in a row send once", both dry-run through a stub `Invoke-RestMethod`. The toast is not in E3; the drill is out of scope.
4. **No pending logic of its own** (R-102 item 1; W0 rev 6.9 §12): `alarm.check` and `bench status` call X-K1's `resume.has_work`; mutant M-ALARMPENDING (a local copy) is killed. `bench status` prints "stopped, n cells never launched".

## K2b scope as compiled (Coordinator #39, 2026-10-06)

Where this brief or the plan's row disagrees with W1-K rev 1.2 (the gated design), W1-K governs:
- **HB-ALM-003 and the `last_alarm_check_at` warning** (acceptance item 1's last clause) are E5: W1-K section 6.2 ("Deferred to E5 with the drill") and section 9.
- **The `report/html.py` resume header and `tests/test_report_resume.py`** are E5: W1-K sections 6.2 and 8. R6.8c stays granted for when it is built. The plan's "report goldens byte-identical" holds by construction, because K2b edits no report file.

**K2b's scope:**
- `alarm.py` (`check`, importing `resume.has_work`);
- `status.py`: `last_progress_at`, `bench-status/2`, "resumed n times", and "stopped, n cells never launched";
- `cli.py`: `status --alarm-after`, `ALARM = 6`, and `cmd_plan`'s one `--alarm-after` line;
- `tests/test_alarm.py`, `tests/test_status.py` and `tests/mutations/alarm.json`;
- the cross-owner test (W0 section 13, the alarm-task row);
- deleting `alarm.py` from `identity.PLANNED`.

**The ntfy topic (R-102)** gates only the live drill (E5). Every K2b test runs the script under `-DryRun`.

**The X-TE9 edge is relaxed by W0 rev 6.13 (R6.13d).** K2b no longer waits on X-TE9's join. The two `cli.py` hunks are disjoint functions, so the later one rebases.

## Recompiled (Coordinator #50, 2026-10-06)

- **Compile `al-01M49X64P0ZCJFQCJVP1NA5SAE`** (raw `al-01M49X63TK7YKC6FBXYM91ZRNS`). Agy `gemini-3.8-flash-high` (`claude-code` template, as #39 and #43). Session `x-k2b2-e1e4`, run `w2-k2b2-e1e4`, branch `build/eval-x-k2b`. Both ids are new and checked free. `x-k2.contract.json` points at them. c43's compile `al-01M48P1TDE2VZ8VZHQMMJ21RYZ` is superseded.
- **`resume.history` is placed by W0 rev 6.14 R6.14a.** K2b builds `views.resume_history` and `ResumeRecord` in `views.py`, with W1-K section 2's definition unchanged. `resume.py` is class `run`, so it may not import `views.py`. K2b gains `tests/test_views.py` (its test) and `tests/mutations/views.json` in its gate.
- **The `status.py:4-5` docstring** is corrected to D-K5 in K2b's `status.py` commit.
- **X-TE9 joins after K2b** (R6.14b). K2b edits no `cmd_validate` line.
- **The split rule is floor-based** (CEIL-A). Agy's floor is unmeasured, so the worker records its first reading.

## Exit
E1 README §3 join gate per dispatch; served model from Agy's `cli.log`. Report per E1 README §4.
