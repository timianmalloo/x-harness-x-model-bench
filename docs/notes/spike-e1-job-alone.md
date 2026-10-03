---
id: note-20261003-spike-e1-job-alone
title: "Spike E1-S3 - reading the Job Object's process list to prove the hidden check is alone"
type: decision-note
status: accepted
owner: "@timianmalloo"
tags: [spike, windows, job-object, adr-0018, security, b7]
links:
  - { to: adr-0018-hidden-check-harness, rel: relates-to }
  - { to: note-spike-isolation-permissions, rel: refines }
  - { to: note-spike-phase1-probes, rel: relates-to }
  - { to: design-e1-evaluation-walking-skeleton, rel: relates-to }
review-by: "2027-04-03"
summary: >-
  procs.Job.pids() (JobObjectBasicProcessIdList) and the same query with a NULL handle from inside the check both
  work, but "the check is alone" is only a sound test when the check and the deliverable are started with the base
  interpreter and DETACHED_PROCESS. Under the venv launcher the job holds the launcher, the interpreter and a third
  process, and the launcher puts the interpreter in a nested job, so the check's own view misses the deliverable. With
  DETACHED_PROCESS and the base interpreter, both views were exactly {check} before and after the deliverable and
  {check, deliverable} while it ran (3 of 3). An honest check's exit came only 4-8 ms after the grader saw its
  document, so the grader cannot rely on reader timing: the check waits for a one-byte acknowledgement before exiting.
---

# Spike E1-S3: is the check alone in its job?

**Question.** ADR-0018 §10a(a)-(b) decides acceptance on "the Job Object's process list holds the check alone",
read by the check before its one write and by the grader when the document's first byte arrives. Spike N2
(`docs/notes/spike-isolation-permissions.md`) measured the active-process count, not the list; probe N4
(`docs/notes/spike-phase1-probes.md`) proved grandchildren stay in the job. Is the list usable as an "alone" test?

**Read.** `procs.Job.pids()` already reads `JobObjectBasicProcessIdList` (`procs.py`, `_PidList`, `pids()`), and
`tests/test_procs.py:30` asserts a grandchild is in it. The same test notes `active() >= 2` because "a venv
python.exe is a launcher plus the interpreter". Probe N4 is **done** (Verified 2026-09-23), although
`docs/architecture-evaluation-campaign.md` still lists it as open (finding F-1 of the E1 design).

**Run (2026-10-03, CPython 3.14.6).** A fake check started a deliverable (`time.sleep`), waited for it, wrote one
line and exited with code 7. Its own view came from `QueryInformationJobObject(NULL, JobObjectBasicProcessIdList)`;
the grader's from `Job.pids()` right after the first byte of stdout arrived, and the check's exit time from
`GetProcessTimes` on the grader's own handle. Three configurations:

| Configuration | Grader's view at arrival | Check's own view | Status |
| --- | --- | --- | --- |
| `procs.spawn` + venv `python.exe` (5 trials) | 3 pids: launcher, interpreter, one more | only itself, even while the deliverable ran (the launcher's nested job) | Verified: unusable as "alone" |
| `procs.spawn` + base interpreter, `CREATE_NO_WINDOW` (3 trials) | 2 pids: the check and one process present from the start (a console host, inferred: the name lookup ran after it exited) | sees the deliverable | Verified: not "alone" without image-name rules |
| suspended + `DETACHED_PROCESS`, base interpreter, deliverable also `DETACHED_PROCESS` (3 trials) | `{check}`; `{check, deliverable}` while it ran | identical to the grader's | **Verified: usable** |

Exit time minus the grader's arrival timestamp for an honest check that exits right after its write: +4.1 to +8.3 ms
(8 trials). Positive here, but a reader thread delayed by load (two grading slots) could see arrival after exit and
call an honest check tampered.

**What this settles for the design.**
- The property grader starts the check with `sys._base_executable` (checks are stdlib-only, ADR-0018 §8) and
  `DETACHED_PROCESS` through a new `procs.spawn(..., console=False)` flag; `spawn_deliverable` does the same.
  "Alone" is then the exact set test `job.pids() == {check_pid}`, with no image-name rules.
- Arrival ordering is made deterministic by a handshake: the check writes its document and then blocks reading one
  byte from its stdin; the grader, on the first byte, queries the job, finishes reading the document, writes the
  acknowledgement, and only then expects the exit. A forger cannot shortcut it: a document before the ack is
  "while not alone" or a second document; an exit before the ack is "exit before acceptance".
- A query failure raises (the existing `_query` fault seam), never reads as "alone".

**Still Flagged.** The identity of the extra process under `CREATE_NO_WINDOW` (avoided, not explained); macOS (no
Job Object; the runner is Windows-only, ADR-0018 §8); a task whose deliverable needs a third-party interpreter
environment (S1 is stdlib-only; a later task with dependencies needs a fresh look at the launcher layer).
