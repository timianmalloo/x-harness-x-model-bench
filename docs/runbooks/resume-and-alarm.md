---
id: runbook-resume-and-alarm
title: "Runbook: resume a crashed run and wire the alarm channel"
type: doc
status: draft
owner: "@timianmalloo"
tags: [runbook, alarm, ntfy, resume, task-scheduler, evaluation-campaign]
links:
  - { to: adr-0021-plan-level-resume-and-liveness, rel: implements }
  - { to: design-eval-resume, rel: implements }
  - { to: design-eval-seam-contracts, rel: depends-on }
review-by: "2026-12-31"
summary: >-
  How an operator wires the unattended alarm for a multi-night run: the ntfy topic and user variable, the
  Task Scheduler task that runs tools/alarm-task.ps1 every 15 minutes, the delivery log and edge state file,
  and the honest limits (a toast wakes no one; a sleeping host cannot push).
---

# Runbook: resume a crashed run and wire the alarm channel

Source: `docs/design/eval-resume.md` section 6.3 and ADR-0021 section 7. This runbook covers the alarm script
`tools/alarm-task.ps1` (X-K2a). The check it calls is `bench status <run_id> --alarm-after <seconds>`, which
ADR-0021 section 7 words as: "`bench status <run_id> --alarm-after <seconds>` exits non-zero, naming the cause,
when the heartbeat is stale **or** `now - last_progress_at` exceeds the threshold while cells are pending."
The wrapper forwards its `-RunsRoot` to the status command's `--runs`; the ledger check and delivery log
therefore use the same run folder.

## 1. What the wrapper does

Each run of the task does three things: it runs `bench status <run_id> --alarm-after <s> --json`; it POSTs
to ntfy on the edge; it appends one line to the delivery log.

| `bench status` exit | meaning | payload code |
| --- | --- | --- |
| 0 | no alarm | none (a recovery push if an alarm was open) |
| 6 | an alarm; `bench-status/1` on stdout | `alarm.code` (`HB-ALM-001` or `HB-ALM-002`) with `alarm.cause` and `alarm.age_s` |
| any other non-zero | the check itself failed | `check-error`, cause `bench status exited <n>` |

A check that errors never reads as "no alarm". The push carries only the run id, the code, the cause and the
age: no task content, path, cell id, credential or hostname.

## 2. Set up the push (required for an unattended run)

1. Install the ntfy app on your phone.
2. Choose a random topic (a long random string). The topic is a bearer secret: anyone who knows it can read
   and send to it.
3. Set it as a **user** environment variable, once: `setx HB_ALARM_NTFY_TOPIC <topic>`. Then subscribe to the
   topic in the app. The script reads it only from this variable and never prints, logs or sends it.
4. Optional self-host: set `HB_ALARM_NTFY_URL` to your server's base URL. The default base is `https://ntfy.sh`.
5. With the variable unset the script exits 2 with the fixed line `alarm channel not configured: set
   HB_ALARM_NTFY_TOPIC (runbook)`. An unattended run needs this to be true.
6. Send a test push and confirm the phone shows it **before** an unattended run starts (the drill record is E5's).

A toast wakes no one. A desktop toast is an optional local echo that joins at the E5 drill; ntfy is the channel
that reaches a sleeping operator.

## 3. Register the Task Scheduler task

Run the script under `powershell.exe` 5.1 (Windows PowerShell; not `pwsh`), every 15 minutes inside the nightly
window:

```
schtasks /Create /TN "bench-alarm-<run_id>" /SC DAILY /ST <window-start> /RI 15 /DU <window-length HH:MM> /TR "powershell.exe -NoProfile -ExecutionPolicy Bypass -File <repo>\tools\alarm-task.ps1 -RunId <run_id> -AlarmAfter <s>"
```

Then set these task flags (task XML or the Settings tab), from design section 6.3 (SRE 4): start when
available (`StartWhenAvailable`); do not stop on battery and do not require AC (`DisallowStartIfOnBatteries`
and `StopIfGoingOnBatteries` off); `WakeToRun` on; run only when the user is logged on; `ExecutionTimeLimit` 5
minutes; `MultipleInstances IgnoreNew`. Whether the machine may wake is the operator's decision.

Choose `--alarm-after` as `max(budget_seconds, worst-case grading step) + 1800`; `bench plan` prints the number.

## 4. Edge alerting and the two files

Per run, both files live in `runs/<run_id>/` (git-ignored with `runs/`):

- `.alarm_edge` (JSON `{code, first_sent_at, last_sent_at}`): the last alert sent. The script sends on a new
  code, re-sends at most hourly while the code persists, sends once on recovery, and clears the file. A failed
  push leaves the file as it was, so the next run retries.
- `alarm-delivery.log`: one line per wrapper run, `<UTC time> exit=<n> push ok | push failed: <exception type>
  | no push`. It holds no topic and no URI. It answers "how often did the alarm fire, and did the push leave".

A failed POST writes the fixed text `push failed: <exception type>` and nothing from the exception: in 5.1 a
failed `Invoke-RestMethod` carries the full URI, so the message is never printed.

## 5. Prove the scheduled channel before registration (Leader and operator)

This is the Leader's and operator's step after X-DRILL joins, before registration. Workers run only fake
transport tests. A final power analysis above `MULTI_NIGHT_HOURS = 4` hours needs an acknowledged drill;
at or below four hours registration needs no drill. The maximum `PowerResult.hours` across the latest
final analysis's properties decides this. The preview reports the recorded drill, or warns of HB-CMP-011.

1. The Leader and operator configure an existing Task Scheduler task named `HarnessBenchAlarmDrill`
   (or another name passed to `start --task`). Use the settings from section 3. Its action is:

   ```
   powershell.exe -NoProfile -ExecutionPolicy Bypass -File <repo>\tools\alarm-task.ps1 -Drill -TaskName HarnessBenchAlarmDrill -RunsRoot <runs> -Bench <bench executable> -AlarmAfter 60 -Toast
   ```

   Use absolute paths and quote paths containing spaces. The task and both CLI commands must use the
   same runs root. `-Toast` is an optional local echo; remove it if unavailable. The phone push is required.
   Do not put the ntfy topic in the action, command arguments, logs or committed files.

2. The Leader runs `bench --root <repo> --runs <runs> drill start`. This freezes a pending dead-engine
   fixture, records its seed metadata under the runs root, and triggers the already configured task.
   No model or workspace is launched. The command prints acknowledgement instructions and hides the
   random `drill-<8 hex>` run id. The wrapper selects the newest seed matching its configured task name.

3. The operator reads the phone push away from the terminal. It contains the run id, HB-ALM code, cause
   and age. The Leader must not supply the hidden id from disk as a substitute for phone receipt.

4. The operator attests receipt by typing the phone's id:

   ```
   bench --root <repo> --runs <runs> drill ack --run-id <phone run id> --toast seen
   ```

   Use `not-seen` if the toast was requested but unseen, or `not-run` (the default) if omitted. None is
   a pass condition. Missing seeded run, successful push after seeding, HB-ALM code, or matching scheduled
   task evidence refuses with HB-USR-002 naming the missing item. The first `push ok` log line after the
   seed supplies `pushed_at` and its code/task. Optional toast failure does not block acknowledgement.

5. The Leader reviews and commits `bench/drills/<run_id>.json` in plan batch P4. One immutable
   `bench-drill/1` record proves the host's channel for all campaigns. Its fields are `schema`, `run_id`,
   `code`, `task`, `seeded_at`, `pushed_at`, `acknowledged_at`, `toast`, and `bench_commit`; every value is
   a string. Times are UTC to the second and must satisfy `seeded_at < pushed_at <= acknowledged_at`.
   No topic, URL, machine path, hostname or username belongs in it. The writer uses canonical bytes and
   create-once publication: a later acknowledgement with different bytes refuses with HB-LED-007.
   Registration reads the record without creating anything; no ledger kind or transition is added.

For drill checks, `alarm-delivery.log` appends `code=<HB-ALM code> task=<task name>` to the normal delivery
line. A task name in this log is evidence of the configured scheduled path; acknowledgement remains the
operator's attestation. A successful fake transport test is not a real drill and creates no committed record.
The wrapper waits at most one second on the real clock if triggered in the seed's second. If the clock
has moved back or an injected clock is not later, it refuses before pushing; retry the scheduled task
after the clock passes the seed. It never invents a later delivery timestamp.

## 6. Limits

- A sleeping or powered-off host sends nothing; `WakeToRun` helps only if the machine may wake.
- A host sleep can make the engine kill cells as `host_suspended`, and `HB-ALM-002` can fire on wake before the
  engine writes its next row. One interval later the next row has landed. Accepted.
- The script is tested with a stub `bench` and a stub `Invoke-RestMethod` under `-DryRun` (Windows only,
  `tests/test_alarm_task.py`). X-K2b adds the test that feeds the real `bench status --alarm-after --json` output
  to this script.
- HB-ALM-003, `.alarm_check` and `ALARM_INTERVAL_S` remain reserved and unbuilt. There is no alarm for
  the alarm in this revision; E5's run report must name that residual.
