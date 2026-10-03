---
id: note-20261003-spike-e1-ntfs-atomic-publish
title: "Spike E1-S1 - os.link fail-if-exists, directory rename and fsync on NTFS (create_once, crash-atomic archive)"
type: decision-note
status: accepted
owner: "@timianmalloo"
tags: [spike, ntfs, crash-atomic, create-once, archive, adr-0015, adr-0016]
links:
  - { to: adr-0016-campaign-record, rel: relates-to }
  - { to: adr-0015-multi-turn-attempt-and-turn-snapshots, rel: relates-to }
  - { to: arch-evaluation-campaign, rel: relates-to }
review-by: "2027-04-03"
summary: >-
  On this host (Windows 11 Pro 10.0.26200, NTFS C:, CPython 3.14.6): os.link onto an existing name raises
  FileExistsError (winerror 183) and keeps the original bytes; os.rename of a directory onto any existing directory
  raises FileExistsError 183; a process killed mid-copy leaves only the temporary sibling and no final folder.
  os.fsync needs a writable file descriptor, and a directory cannot be opened for fsync at all (PermissionError), so
  ADR-0015 section 5a's "fsync the folder" is POSIX-only. Power-loss durability was not tested.
---

# Spike E1-S1: the crash-atomic publish primitives on NTFS

**Question.** ADR-0015 §5a and ADR-0016 §2a rest on three recalled claims (architecture *Contracts at the seams*,
rows `os.link` and `os.rename`, both Inferred): `os.link(tmp, final)` fails atomically if `final` exists; a
same-volume directory rename is one operation that fails if the target exists; files and the folder can be fsynced.

**Method (read + run, 2026-10-03).** A stdlib script in the session scratchpad, run with the repo's interpreter
(`.venv\Scripts\python.exe`, CPython 3.14.6) on volume `C:` (`Get-Volume` → `NTFS`). It (1) linked a temporary file
to a missing name, then a second temporary file to the same name; (2) renamed a temporary folder to a missing name,
then onto an empty and a non-empty existing folder; (3) called `os.fsync` on a read-only and a read-write file
descriptor and on a descriptor of a folder; (4) started a child that copies 400 × 64 KiB files into
`attempt-1.tmp-<pid>` and then renames it to `attempt-1`, killed it after 1 s, and listed the folder; an unkilled
child was the control. The script was deleted after the run (spike scaffolding is not kept).

**Evidence.**

| Probe | Observed | Status |
| --- | --- | --- |
| `os.link` onto a missing name | link created, bytes equal, temporary unlinked | Verified |
| `os.link` onto an existing name | `FileExistsError`, `winerror=183`; the original bytes unchanged | Verified |
| directory `os.rename` onto a missing name | renamed with its contents | Verified |
| directory `os.rename` onto an existing empty / non-empty folder | `FileExistsError`, `winerror=183` in both cases (no replace) | Verified |
| `os.fsync` on an `O_RDONLY` file descriptor | `OSError` (EBADF) | Verified |
| `os.fsync` on an `O_RDWR` file descriptor | succeeds | Verified |
| `os.open(<folder>)` for fsync | `PermissionError`: a folder cannot be fsynced through `os.open` on Windows | Verified |
| kill mid-copy | no `attempt-1`; only `attempt-1.tmp-<pid>` with 98 of 400 files | Verified |
| control (no kill) | `attempt-2` complete with 400 files | Verified |

**What this settles.**
- `create_once` (ADR-0016 §2a): write the temporary file through a read-write handle, `os.fsync` that handle, close,
  `os.link`, unlink. `FileExistsError` is the "exists" branch (compare bytes, then no-op or refuse).
- Crash-atomic archive (ADR-0015 §5a): copy into `<name>.tmp-<pid>`, fsync each file **through its write handle**,
  verify, `os.rename`. "Final folder exists" means "the copy finished" for a **process** crash.
- Directory fsync is POSIX-only: on Windows the step is skipped by platform, not attempted. NTFS journals the rename
  metadata, but that is recalled, not measured here.

**Still Flagged.** Power loss or a host crash between the file fsyncs and the rename (not testable by killing a
process); macOS (APFS) not run; a cross-volume archive root (`os.rename` would raise `OSError` 17, a hard error the
design surfaces, never a fallback copy).
