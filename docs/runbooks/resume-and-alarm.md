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
**That command lands with X-K2b, not with this script.** Until it lands the script runs but `bench` rejects the
flag, and every check reads as `check-error` (exit code other than 0 or 6).

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

## 5. Limits

- A sleeping or powered-off host sends nothing; `WakeToRun` helps only if the machine may wake.
- A host sleep can make the engine kill cells as `host_suspended`, and `HB-ALM-002` can fire on wake before the
  engine writes its next row. One interval later the next row has landed. Accepted.
- The script is tested with a stub `bench` and a stub `Invoke-RestMethod` under `-DryRun` (Windows only,
  `tests/test_alarm_task.py`). X-K2b adds the test that feeds the real `bench status --alarm-after --json` output
  to this script.
