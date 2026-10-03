---
id: note-20261003-spike-e1-handle-list
title: "Spike E1-S2 - the deliverable's explicit handle list on Windows (close_fds + redirected stdio) and the DuplicateHandle forgery"
type: decision-note
status: accepted
owner: "@timianmalloo"
tags: [spike, windows, handle-list, adr-0018, security, b7]
links:
  - { to: adr-0018-hidden-check-harness, rel: relates-to }
  - { to: adr-0013-native-cells, rel: relates-to }
  - { to: design-e1-evaluation-walking-skeleton, rel: relates-to }
review-by: "2027-04-03"
summary: >-
  CPython 3.14.6's subprocess already passes PROC_THREAD_ATTRIBUTE_HANDLE_LIST holding only the three stdio handles
  when close_fds=True and any stdio is redirected (subprocess.py:1498-1521), which is how procs.spawn creates the
  adapter today. Run on this host: a child created that way could not reach the parent's inheritable pipe by the
  passed handle value or by scanning handle values; the positive control (close_fds=False) could. A child that opened
  the parent with PROCESS_DUP_HANDLE and duplicated the pipe handle wrote a forged line into it, confirming the
  ADR-0018 section 10a threat.
---

# Spike E1-S2: explicit handle list for the deliverable

**Question.** ADR-0018 §10 needs the deliverable created with an explicit handle list so it cannot inherit the
check's result pipe; the architecture rated `subprocess.Popen` handle-list behaviour *Inferred (recalled)*. How does
`procs.py` do it for the adapter, and can a child so created write to a handle not in its list?

**Read.** `procs._spawn_win32` (`src/harness_bench/procs.py`, the `subprocess.Popen(... close_fds=True)` call) passes
no `lpAttributeList`. CPython's `subprocess.py` (3.14.6, `C:\Users\malla\AppData\Roaming\uv\python\cpython-3.14-windows-x86_64-none\Lib\subprocess.py:1498-1521`)
builds `attribute_list["handle_list"]` from the three standard handles whenever `close_fds` is true and standard
handles are used, filters it, and creates the process with `bInheritHandles` true but limited to that list. So the
adapter spawn already uses the handle-list attribute implicitly [Verified, read].

**Run (2026-10-03, CPython 3.14.6, `.venv` interpreter).** The parent made an `os.pipe()`, marked the write end
inheritable, drained the read end on a thread, and started a child with `stdin=DEVNULL` and stdout/stderr redirected
to files, passing the write handle's numeric value and its own pid. Three trials:

| Trial | Child behaviour | Pipe received | Status |
| --- | --- | --- | --- |
| `close_fds=True` (the handle list) | `WriteFile` on the passed value, then on every handle value 4..4092 except its own stdio | nothing | Verified: not reachable |
| `close_fds=False` (positive control) | same | `FORGED` | Verified: the probe can see an inherited handle |
| `close_fds=True` + `OpenProcess(PROCESS_DUP_HANDLE)` + `DuplicateHandle` | duplicates the parent's write handle by value | `FORGED` | Verified: the §10a forgery works |

**Findings that change the design or a test.**
1. `bench_check.spawn_deliverable` needs no new ctypes code: `subprocess.Popen(close_fds=True)` with the three
   stdio handles given explicitly is the handle list. The helper passes no `lpAttributeList` of its own, refuses
   `close_fds=False`, and always redirects all three stdio handles; the red test proves the behaviour, not the call.
2. In the `close_fds=True` trial the scan found **one** handle value (256 in the child) that accepted a write, yet the
   pipe got nothing: a process always owns some writable handles of its own. ADR-0018 §10's wording "the fixture must
   record that no write succeeded" is therefore not a sound assertion. The test asserts on the **result pipe**
   (nothing foreign arrived; the parsed result equals the honest one), and the fixture records the handle values it
   tried, as evidence only.
3. The duplicated-handle forgery is real on this host, so §10a (write once, last and alone; single-document
   acceptance) is load-bearing, not theoretical.
4. The venv `python.exe` is a launcher that starts the base interpreter and relays inheritable handles to it (the
   positive control's hit came through it). The check and the deliverable are therefore started with the **base
   interpreter** (`sys._base_executable`), see spike E1-S3.

**Still Flagged.** macOS (`close_fds` on POSIX closes every descriptor above 2 by default; not run); a deliverable
that injects code into the check (accepted, undetected residual of ADR-0018 §10a).
