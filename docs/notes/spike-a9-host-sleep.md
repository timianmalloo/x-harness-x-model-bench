---
id: note-20260924-spike-a9-host-sleep
title: "Spike A9 - the engine and Windows clocks across a real host suspend"
type: decision-note
status: accepted
owner: "@timianmalloo"
tags: [spike, host, clock, sleep, risk-A9]
links:
  - { to: coordination-finish-harness-bench, rel: relates-to }
review-by: "2026-12-24"
summary: >-
  Measured on the operator's Windows 11 host (Modern Standby, about 236 s): the engine's SleepDetector detects a real suspend and
  ends the live cell as host_suspended (HB-CELL-106); time.monotonic counts sleep time, QueryUnbiasedInterruptTime does
  not; a standby shorter than suspend_gap is not detected and inflates turn_ms.
---

# Spike A9: the engine across a real host suspend

**Risk A9** (`docs/architecture.md`, flagged risks): the monotonic clock across Windows sleep. Plan row 30 handed it to the human. On 2026-09-24 the operator approved a scripted probe instead, and the Leader ran it.

## Method (Verified; scripts are in the Leader's session scratchpad)

1. **Host.** Windows 11 Pro 10.0.26200, on AC power (battery 100%). Measured with `powercfg /a`: S0 Low Power Idle ("Modern Standby", network connected) and Hibernate; S1–S3 are not available. Wake timers: `Enable` on AC, `Disable` on DC.
2. **Wake.** A one-shot scheduled task with `WakeToRun`, registered 300 s ahead, that writes a timestamp.
3. **Engine.** The real `Engine` ran one cell with the fake ACP agent: a 420 s turn, a 900 s budget, `suspend_gap` 60 s, and the test suite's `FakeLauncher` and `_plan` helpers.
4. **Suspend.** 45 s after `cell.prompt_sent`, the probe called `SetSuspendState(False, False, False)`.
5. **Sampling.** A sampler recorded `time.time`, `time.monotonic`, `time.perf_counter`, `QueryUnbiasedInterruptTime` (`host.unbiased_seconds`) and `GetTickCount64` every 2 s.

## Results (Verified)

- The host entered standby at 16:51:28 local time. The engine run had already completed by 16:55:33, **before** the wake timer's scheduled time of 16:55:41. The task's own stamp reads 16:55:48, so the task ran on schedule while the host was already awake. **The wake source is not recorded.** It was not this probe's timer. It may have been Modern Standby's own network-connected activity (Inferred). `SetSuspendState` never recorded a return inside the probe (its thread was a daemon, and the run finished first). This gap is named, not guessed. A repeat would read the wake source from the System event log (Power-Troubleshooter event 1) or from `powercfg /lastwake` (which needs admin rights).
- Clock steps across the one gap between samples (about 236 s asleep):

| clock | step |
| --- | --- |
| `time.time` (wall) | 236.1 s |
| `time.monotonic` | 238.6 s |
| `time.perf_counter` | 238.6 s |
| `GetTickCount64` | 236.1 s |
| `QueryUnbiasedInterruptTime` | 5.8 s |

- **The engine behaved as designed.** `SleepDetector` (wall minus unbiased > 60 s) fired on the first loop after the wake. The cell ended `failed` with cause `host_suspended` (HB-CELL-106). The ledger reads, in order: `run.started`, `cell.launch_intent`, `cell.workspace_built`, `attempt.process_started`, `attempt.session_opened`, `cell.prompt_sent`, `attempt.process_ended`, `cell.outcome`, `cell.archived`, `cell.workspace_deleted`, `run.completed`.
- **`turn_ms` includes the sleep:** the recorded value is 292,839 ms, for about 56 s of awake turn plus about 237 s asleep. The engine measures the turn with `time.monotonic`, which counts suspended time on this host.
- This Claude Code session and its background jobs survived the standby.

## What it means

- **Closed:** a suspend longer than `suspend_gap` is detected and never scored. The cell is invalidated as `host_suspended`, and the run completes with a coherent ledger.
- **Residual (Verified mechanism; exposure Inferred):** a standby shorter than `suspend_gap` (60 s) is not detected. Because `time.monotonic` counts it, it adds up to 60 s to that cell's `turn_ms` and consumes its budget. A cell near its budget could then be killed as `timeout`. The power request (`host.keep_awake`, `engine.py:216/258`) prevents idle sleep during a run, so only an explicit suspend or a lid close can cause it. Upgrade trigger: a smoke or grid run whose ledger shows a turn-time outlier. The fix would measure turn time with the unbiased clock (a W2-STOP design question, not a wave-1 defect).
- Measured only on this host and one standby type (Modern Standby). Hibernate was not exercised.
