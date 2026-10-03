---
id: "design-eval-atomic-publish"
title: "W1-B design: crash-atomic publish (atomic.py create_once and publish_dir, archive.py rework)"
type: design
status: proposed
owner: "@timianmalloo"
phase: "Enterprise evaluation: Wave 1 design slice W1-B; builds in E1 (X-B1 atomic.py, X-B2 archive.py)"
tags: [benchmark, crash-atomic, archive, create-once, evaluation-campaign, w1-b]
links:
  - { to: spec-enterprise-evaluation, rel: implements }
  - { to: arch-evaluation-campaign, rel: implements }
  - { to: design-eval-seam-contracts, rel: depends-on }
  - { to: adr-0015-multi-turn-attempt-and-turn-snapshots, rel: depends-on }
  - { to: adr-0016-campaign-record, rel: depends-on }
  - { to: adr-0021-plan-level-resume-and-liveness, rel: depends-on }
  - { to: note-20261003-spike-e1-ntfs-atomic-publish, rel: depends-on }
  - { to: review-eval-ds, rel: relates-to }
  - { to: review-eval-sec, rel: relates-to }
  - { to: review-eval-pat, rel: relates-to }
  - { to: review-eval-ta, rel: relates-to }
  - { to: defect-classes, rel: relates-to }
review-by: "2026-10-17"
summary: >-
  Designs the two write helpers every campaign record and every archive goes through: create_once (a file appears
  only complete, never overwritten) and publish_dir (a folder appears only after its copy verified), plus the one
  recovery rule for the crash window between the rename and the ledger rows (specified here, built by X-K1 in E3).
  Revision 2 applies the five W1-B lens reviews (34 findings, each dispositioned in section 18) and W0 rev 3. Settles the data model (the published
  name is the only completeness fact), the temp-name and sweep contract, the Windows no-directory-fsync branch, the
  strict verify, the reader surfaces a leaked temp would break, and names every red-first test and seeded mutant so
  X-B1 and X-B2 can start from this file alone. Adds three measured Windows facts (text-mode os.write corrupts
  bytes, a junction is unlinkable, a held handle blocks a folder rename).
---

# Design: crash-atomic publish (W1-B)

- **Status:** Revision 2, in review (Gate record: first-round lines recorded; rev 2 pending RV-TA).
- **Spec / architecture:** `docs/specs/enterprise-evaluation.md` (US-19 archive; the campaign records) · `docs/architecture-evaluation-campaign.md` · W0 `docs/design/eval-seam-contracts.md` §4, §11, §12, §13.
- **Delivery phase / vertical slice:** E1. X-B1 builds `src/harness_bench/atomic.py`; X-B2 builds the `archive.py` rework. X-C (campaign records), X-E (discrimination records) and X-D (identity files) consume `create_once` in E1; X-J1 (turn snapshots) consumes `publish_dir` in E2; X-K1 (resume) consumes `sweep_temps` in E3 and builds `recover_archive` to the rule in 5. Nothing here is mocked: the helpers are pure stdlib over a real folder, so every consumer can use them the day X-B1 merges.
- **Author / date:** rev 1 `w1b-publish-e1e4`; rev 2 `w1b-publish-r2-e1e4` (Claude Sonnet 5.5, `claude-sonnet-5-5`) · 2026-10-03.
- **Scope note:** design only. No code. Resume logic is W1-K; snapshot folder paths are W1-J; where this file touches them it states the helper contract only.

## 1. Responsibility

One responsibility: **a name in a published location means its content is complete.** A reader of `attempt-1/`, of `identity/<hash>.json` or of a discrimination record never sees a half-written one, in the face of a process crash, a concurrent writer, a predictable-name attack, or a PID that is reused.

In scope: the `atomic.py` API (W0 §4, with three additions, see 3.5), the rework of `archive.archive_cell` onto it, the recovery rule for the crash window between rename and rows, the strict `verify`, the sweep of leaked temps, the reader surfaces a leaked temp would break, and the defect class. Out of scope: which folder a snapshot lives in (W1-J), when a resume runs the sweep (W1-K), the campaign commands (W1-C), the registry edit of `errors.py` (X-D owns it in E1).

**Done-when map (the plan row, verbatim, and where each item is met).**

| Done-when item | Met in |
| --- | --- |
| Gate PASS incl. Security and Distributed Systems | Gate record (first-round lines; rev 2 pending RV-TA); review disposition in 18; RV-DS dispositions in 9; RV-SEC F10 in 3.4 and 8 |
| The D1 and D3 red tests named | 10.2 table: **D1** = `test_a_kill_mid_copy_leaves_no_final_folder_and_the_redo_succeeds` (archive, red today); **D3** = `test_a_kill_between_write_and_link_leaves_no_final_file` (create_once). These are the council findings D1 (ADR-0015 §5a) and D3 (ADR-0016 §2a). The Testing Strategy directives D1 (unit + mutation) and D3 (architecture) are also met: 10.3, 10.4 |
| The Windows no-directory-fsync branch stated (spike E1-NTFS) | 3.3 "fsync" and test `test_the_real_publish_dir_fsyncs_the_folder_only_on_posix` (nothing patched) and `test_posix_flag_default_follows_the_platform` |
| The defect class text for "exists means complete" | 12 (class `PUB-A`, text ready to paste) |

## 2. Data model (settled first)

**Bounded context.** Durable publication of evaluation artifacts on one local volume. Ubiquitous language: **final name** (the name consumers read), **temp** (`<name>.tmp-<pid>-<nonce>`, a sibling that is never a record), **publish** (the one act that makes a final name appear), **sweep** (delete temps of a target), **rows** (`archive_files` facts), **recover** (reconcile a published folder with its rows).

**Aggregates (each bounded by one invariant, referenced by identity).**

| Aggregate | Root (identity) | The one invariant it protects | Entities / value objects |
| --- | --- | --- | --- |
| Published file | its final path (content-addressed for campaign records) | the final name exists only with its complete bytes, and is never overwritten | value object: the bytes; the temp file is not part of the aggregate |
| Archive entry | `(run_id, cell_id, archive_attempt, snapshot)` (ADR-0015 §5) = one final folder | the final folder exists only if a copy of the source, verified file by file, was renamed into place | value objects: `ArchiveRow` (path, kind, size, sha256, link_target); a temp folder is not part of the aggregate |
| Archive record in the ledger | the same identity | the `cell.archived` event exists only after every row of the entry is recorded; its `archive_hash` commits to those rows | `archive_files` rows (facts), the event (fact) |

The first two protect "exists means complete" on disk. The third protects the order **folder, then rows, then event** in the ledger. They are separate aggregates because they have separate transactions: the folder commits at the rename, the rows commit one ledger line each, and the event commits last. No one transaction spans them; the recovery rule (5) is what makes the three converge after a crash, so the design does not pretend otherwise.

**Durable representation.** No new schema, no new ledger kind, no migration: `archive_files` rows, `cell.archived` and the `archive_hash` are exactly as ADR-0006 and ADR-0015 §5 define them (DM16: expand-migrate-contract is not triggered). The folder is the byte store; the rows are the append-only facts about it.

**Grain statements.**
- A final archive folder is exactly **one complete, verified copy of one cell's working copy and harness home, at one archive attempt (or one turn snapshot)**. It is immutable once published (Type-1 overwrite is forbidden: a second publish at the same name raises).
- An `archive_files` row is exactly one file or link in one snapshot of one archive attempt of one cell (ADR-0015 §5, unchanged). `size` is additive within one snapshot; `sha256` is non-additive and is only compared. No measure is summed across snapshots.
- A temp is **not a record**. It has no grain, no row, and no meaning beyond "an unfinished attempt to publish `<name>`".

**History rule per attribute.** Type-2 everywhere that matters, by construction: there is no update. A row is appended once; a folder is renamed in once; a campaign file is linked in once. A redo after a crash never rewrites a published thing, because the crashed attempt published nothing (the temp is discarded, then a new temp is built).

**Derive, don't store.** Three things are derived and never stored:
1. **"Complete"** is the presence of the final name. No `.complete` marker file, no status row (a second definition of completeness is a defect signature, DM7).
2. **A folder's rows** are derivable from the folder plus the source. This is what recovery uses: the recovery rule in 5 (X-K1) recomputes the rows and compares them with the recorded ones. The rows in the ledger are the committed facts; the recomputed rows are the check.
3. **`archive_hash`** is derived from the rows (`archive.archive_hash`, unchanged), recomputed by `bench verify`.

**Append-only enforcement, tested.** The forbidden update is attempted in `test_publish_dir_refuses_when_final_exists_and_touches_nothing`, `test_create_once_refuses_different_bytes_and_keeps_the_original` and `test_archive_cell_refuses_when_a_complete_archive_exists`. X-K1 backs the "rows are derivable" claim with a rebuild test in E3 (5): it asserts that the rows recomputed after a crash give the same `archive_hash` as a fresh archive of the same source.

**Writers and compute readers of every persisted thing.**

| Persisted thing | Writer | Compute reader |
| --- | --- | --- |
| `<run>/archive/<cid>/attempt-N/` (final folder) | `archive.archive_cell` via `atomic.publish_dir` (X-B2); snapshots via the same call (X-J1) | `archive.verify` (`views.py:686` `bench verify`); `grade/runner.py:306`; `report/summaries.py:235`; `report/judges.py:216`; `report/pack_improvement.py:783`; `report/credentials.py:91` |
| `archive_files` rows, `cell.archived` | `engine._archive` (`engine.py:808-811`), and X-K1's resume | `views.py:679-689` (`archive_hash` recompute, `verify`); `grade/runner.py:237` |
| campaign and discrimination files, identity, prereg and power files | `atomic.create_once` (X-C, X-D, X-E) | `bench campaign verify` (X-C), `bench validate` (X-E) |
| temps (`*.tmp-*`) | the two helpers | `atomic.stale_temps` / `sweep_temps` only; every other reader must not see them (4) |

**Why the model is enough.** The one invariant per aggregate is enforced by the order of operations inside one helper, not by a convention at each call site. That is the point of having exactly two helpers (W0 §4, DM7).

## 3. Contracts

### 3.1 What W0 §4 fixed (revision 3, quoted) and what this design relies on

> `create_once`: "tmp = path.with_name(f"{path.name}.tmp-{os.getpid()}-{uuid4().hex}"), opened O_CREAT|O_EXCL; write, fsync through the write handle, close, os.link(tmp, path), unlink tmp. True = created; False = path existed with equal bytes (no-op). Different bytes: raise BenchError("HB-LED-007", ...) naming the path. Never overwrites."

> `publish_dir(final, fill, verify)`: "If final exists: raise FileExistsError (checked explicitly, on every platform). tmp = final.with_name(...), created by os.mkdir (exclusive: a collision raises); fill(tmp) copies into the empty folder; fsync every file through its write handle; verify(tmp) raises unless the copy matches (it enumerates the folder and compares the file set as well as each file's rows); fsync the folder only when os.name == "posix"; os.rename(tmp, final). On any exception the tmp sibling is left for the sweep."

> `stale_temps(target)`: "The `<target.name>.tmp-*` siblings, files or folders, that a sweep deletes (ADR-0021 §4). Each entry is lstat-ed first: a reparse point (a junction or symlink) is unlinked, never recursed into. Each deletion is logged." Rev 3 narrows it: "a sibling is listed only if is_temp_name(name) holds (TEMP_RE), not by the glob."

> Rev 3, S-B1 (granted in part): "the `OSError` from `os.link` propagates unchanged, with the path in its message; there is no HB-LED-009." `TEMP_RE`, `is_temp_name`, `sweep_temps` and `make_writable` are in W0 §4.

This design adopts all of it. It adds three small things W0 does not yet say, as seam request S-B4 (3.5).

### 3.2 `src/harness_bench/atomic.py` (X-B1): the final API

```python
TEMP_RE = re.compile(r"^(?P<base>.+)\.tmp-(?P<pid>[0-9]+)-(?P<nonce>[0-9a-f]{32})$")   # the one definition of a temp name
RENAME_BACKOFF = (0.05, 0.1, 0.2, 0.4, 0.8, None)   # WIN-A; the ONE copy: workspace._land calls rename_with_retry (RV-PAT 1)
_POSIX = os.name == "posix"                          # module constant so a test can flip the fsync-branch BODY; a second test pins the default
O_BINARY = getattr(os, "O_BINARY", 0)                # 0 off Windows; every os.open in this module passes it (site scan, 10.4)

def is_temp_name(name: str) -> bool: ...                                     # TEMP_RE.fullmatch
def create_once(path: Path, data: bytes) -> bool: ...                        # W0 §4
def publish_dir(final: Path, fill: Callable[[Path], T], verify: Callable[[Path], None]) -> T: ...   # W0 §4
def rename_with_retry(src: Path, dst: Path, *, replace: bool = False, settled: Callable[[], bool] | None = None) -> int: ...
                                                                              # PUBLIC (S-B4): returns the number of retries; the one WIN-A loop
def stale_temps(target: Path) -> list[Path]: ...                             # pure listing, sorted
def sweep_temps(target: Path, lock: RunLock) -> list[Path]: ...              # W0 §4 + the lock argument (S-B4)
def make_writable(func, path, _exc) -> None: ...                             # moved from archive.py; archive re-exports it (S-B1, W0 §4)
```

Imports: stdlib, `harness_bench.errors` and `harness_bench.oslock` (which imports only stdlib and `errors`). `atomic.py` knows nothing of ledgers, campaigns, archives or runs. A cycle with `archive` or `workspace` would fail at import, so no separate import-direction test exists (RV-SIM 4).

### 3.3 Behaviour, step by step

**`create_once(path, data) -> bool`.** Precondition: `path.parent` exists (the helper never creates folders; a missing parent raises `FileNotFoundError`).

1. `tmp = path.with_name(f"{path.name}.tmp-{os.getpid()}-{uuid.uuid4().hex}")`.
2. `fd = os.open(tmp, os.O_RDWR | os.O_CREAT | os.O_EXCL | O_BINARY, 0o644)`. **`O_BINARY` is mandatory** (measured, spike E1-S2: without it `os.write` on Windows turned 7 bytes `a\nb\r\nc\n` into 10 bytes on disk). `O_RDWR` because a read-only descriptor cannot be fsynced (spike E1-S1). **The descriptor stays open until step 5.**
3. Write all bytes (loop until written), `os.fsync(fd)`.
4. `os.link(tmp, path)`; on POSIX, where `os.link in os.supports_follow_symlinks`, with `follow_symlinks=False`.
   - **Success, then identity check (RV-SEC 2).** `os.fstat(fd)` and `os.lstat(path)` must agree on `st_dev` and `st_ino`. A mismatch means the temp name was swapped between the write and the link and `path` now names another file: unlink `path` (the one name this call created), then raise `BenchError("HB-LED-007", f"{path} was replaced between write and link")`. On a match, return `True` (the temp is removed in step 5).
   - `FileExistsError` (winerror 183, spike E1-S1): `lst = os.lstat(path)`; if it is not a regular file or is a reparse point, raise `BenchError("HB-LED-007", f"{path} exists and is not a regular file")`. Else open it `O_RDONLY | O_BINARY | getattr(os, "O_NOFOLLOW", 0)` (an `OSError` with `errno.ELOOP`, a link where `O_NOFOLLOW` forbade one, is `HB-LED-007` "not a regular file"; every other open error propagates unchanged), `os.fstat` the descriptor, require a regular file whose `(st_dev, st_ino)` equals `lst`'s (the check and the read are on one file: RV-SEC 4), and read from that descriptor. Equal bytes: return `False`. Different: raise `HB-LED-007` "exists with different bytes". The original is never touched.
   - **Any other `OSError` propagates unchanged** (RV-DS 2, RV-SIM 5, W0 S-B1 refused HB-LED-009). There is no fallback copy, and `FileNotFoundError` or a transient `PermissionError` keep their own meaning.
5. `finally`: close `fd`; then `_discard_temp(tmp)`: `os.unlink(tmp)`; `FileNotFoundError` is ignored; **any other `OSError` is logged `atomic.temp_leaked` (WARNING, `path`, `exc_type`) and swallowed** (RV-DS 1). On the success path this means a call that created the file never raises because a scanner held the temp; in a failure path it never masks the original exception. The sweep removes a leaked temp. This is the one swallowed cleanup in the module, and it is logged, so it is not CLN-A's silent kind. A crash leaves `tmp` for the sweep; `path` does not exist, because it is only ever created by the link in step 4.

**`publish_dir(final, fill, verify) -> T`.** Preconditions: `final.parent` exists; `fill` never leaves a read-only file (the helper never changes a mode); one writer per `final` at a time (a run lock, `grade.lock` or `campaign.lock` held by the caller).

1. `if os.path.lexists(final): raise FileExistsError(errno.EEXIST, "...", str(final))`. Explicit on every platform: on POSIX `os.rename` onto an existing **empty** folder would succeed silently. `lexists`, not `exists`, so a dangling link also counts. `fill` is **not** called in this case and no temp is created.
2. `tmp = final.with_name(f"{final.name}.tmp-{os.getpid()}-{uuid.uuid4().hex}")`; `os.mkdir(tmp)`. A collision (a stale folder, a squatted junction, a file) raises `FileExistsError` and nothing is written into the existing thing. A missing parent raises `FileNotFoundError` here and creates nothing. `fill` always receives an **empty, freshly created** folder.
3. `result = fill(tmp)`.
4. fsync pass: walk `tmp` with `os.scandir` + `lstat`; for each regular file (reparse points and folders skipped) `fd = os.open(p, os.O_RDWR | O_BINARY)`; `os.fsync(fd)`; `os.close(fd)`. The descriptor is opened for write; a read-only descriptor fails (spike E1-S1). Opening a read-only-attribute file `O_RDWR` raises `PermissionError` (measured), which is why `fill` must not leave one.
5. `verify(tmp)` raises unless the copy matches. The caller's verify **enumerates the folder** and compares the file set as well as each file's row. `publish_dir` does not look inside.
6. Folder fsync: **only when `_POSIX`**: `_fsync_dir(tmp)`. **On Windows this step is skipped by platform, not attempted.** Spike E1-S1: "a directory cannot be opened for fsync at all (PermissionError), so ADR-0015 section 5a's 'fsync the folder' is POSIX-only"; NTFS journals the rename metadata, which is **recalled, not measured** (Inferred). Power loss between the file fsyncs and the rename is not testable by killing a process and stays Flagged (14).
7. `retries = rename_with_retry(tmp, final)`. After a successful rename on POSIX, `_fsync_dir(final.parent)` (Inferred: POSIX semantics, not run on this host).
8. Return `result`.

Any exception in steps 3 to 7 leaves `tmp` where it is and logs one `atomic.publish_failed` (`phase` = the step's name). **The sweep is the only cleanup path** (one path to test; the partial copy is also the evidence of why a copy failed). The cost is at most one cell's tree of disk per failure until the next sweep; HB-RUN-004 (disk low at launch) bounds the rest.

**`rename_with_retry(src, dst, *, replace=False, settled=None) -> int`.** The one WIN-A loop (RV-PAT 1). `op` is `os.replace` if `replace` else `os.rename`, looked up on `os` at call time (a test's patch lands). For each `delay` in `RENAME_BACKOFF`: call `op`; return the number of retries so far. A `PermissionError` is retried: if `settled` is given and `settled()` is true, return (the other writer won); if `delay is None` raise it; else `time.sleep(delay)`. **Every other `OSError`, `FileExistsError` included, propagates at once** (a rename onto an existing target is a race with a second writer, not a transient refusal). WIN-A was measured here: winerror 5 with a handle open in the same or another process, success after the handle closes. `workspace._land` becomes:

```python
try:
    rename_with_retry(tmp, dest, replace=True, settled=lambda: valid(dest))
except OSError:
    if not valid(dest):
        raise
return dest
```

which keeps every behaviour of today's loop (`workspace.py:100-113`): a refusal that clears is retried, a refusal that persists raises unless `dest` is by then a valid build, another `OSError` raises unless `dest` is valid. `tests/test_workspace.py:400-421` stay green unchanged (they patch `workspace.os.replace`, which is `os.replace`).

**`stale_temps(target) -> list[Path]`.** `os.scandir(target.parent)` (an absent parent gives `[]`); keep entries whose `TEMP_RE` match has `base == target.name`; sorted by name; **non-recursive**; lists files, folders and reparse points alike. A name such as `final.tmp-notes`, `other.tmp-1-<hex>` or a nonce of 31 hex digits does not match, so a user file is never swept (the ADR's looser glob `*.tmp-*` would delete them).

**`sweep_temps(target, lock) -> list[Path]`.** **The precondition is enforced (RV-DS 4):** the caller passes the `RunLock` that excludes a live writer to `target`, and the function first requires `oslock.is_held(lock.path)`; if it is not held it raises `ValueError(f"sweep_temps needs the writer lock for {target}")` **before deleting anything**. This proves a lock is held, not whose; passing the `RunLock` object (only `RunLock.acquire` makes one) is what ties it to the caller. A sweep cannot tell a crashed writer's temp from a live one, and PID liveness is unreliable under PID reuse. For each path in `stale_temps(target)`, `os.lstat` first:
- a reparse point (`st_file_attributes & FILE_ATTRIBUTE_REPARSE_POINT`, or `S_ISLNK`): `os.unlink(path)`; **never** recurse (a junction to `C:\Users\...` must keep its target; measured: `os.unlink` removes a junction and the target survives, and `shutil.rmtree` over a tree holding a junction removes the junction only);
- a folder: `shutil.rmtree(path, onexc=make_writable)` (a read-only file inside makes plain `rmtree` fail with winerror 5, measured; the T9-1 lesson in `workspace._discard`);
- a file: `os.unlink`.
Each deletion logs `atomic.temp_swept` (WARNING) with `path` and `kind` in `file|dir|link`. **A deletion that fails raises** (CLN-A: cleanup that fails silently is a defect class); the caller reports it and does not proceed to redo the copy.

**`make_writable(func, path, _exc)`** (moved from `archive.py:93-95`, reviewed on the way: RV-SEC 6). `st = os.lstat(path)`; if the entry is not a link or reparse point, `os.chmod(path, stat.S_IMODE(st.st_mode) | stat.S_IWUSR)` (add the bit, do not replace the mode); then `func(path)`. A link is never chmod-ed, so a symlink inside a temp tree cannot re-mode its target outside the temp.

### 3.4 Threat controls inside the helpers (RV-SEC F10)

| Control | Where | Test |
| --- | --- | --- |
| temp name `<name>.tmp-<pid>-<uuid4 hex>`: 122 bits of nonce, not predictable | both helpers | `test_create_once_temp_names_are_unique_and_exclusive`, `test_publish_dir_hands_fill_an_empty_exclusively_created_folder` |
| exclusive create: `O_EXCL` for the file, `os.mkdir` for the folder | both helpers | same tests, with a pre-created name |
| reparse-point guard: a squatted junction at the tmp name makes `os.mkdir` raise (measured: `FileExistsError` 183); `O_EXCL` onto a junction raises (measured: `PermissionError`); the sweep unlinks, never recurses | helpers and sweep | `test_publish_dir_refuses_a_squatted_reparse_point`, `test_sweep_temps_unlinks_reparse_points_without_recursing` |
| the file the link made is the file that was written (fd kept open; `st_dev`/`st_ino` compared) | `create_once` step 4 | `test_create_once_refuses_a_file_swapped_in_before_the_link` |
| the existing final is `lstat`-checked, then read through one descriptor that must be the same file | `create_once` step 4 | `test_create_once_refuses_a_non_regular_existing_path` |
| `make_writable` never chmods through a link | sweep | `test_make_writable_does_not_chmod_through_a_link` |

### 3.5 Seam requests

W0 rev 3 answered S-B1 (granted in part: `sweep_temps`, `is_temp_name`, `make_writable`, `TEMP_RE`; **HB-LED-009 refused**), S-B2 (granted: the three `.gitignore` lines go to X-C) and S-B3 (granted: `archive.attempt_dirs`). Nothing in this file rests on them any more. One request is new:

| Request | Content | Fallback while pending |
| --- | --- | --- |
| **S-B4** `req-01M41FDXHDYP8YG3HPDNDGQHAN` (to `coord-opus-e1e4`) | (1) public `rename_with_retry`; `workspace._land` calls it (one hunk in `workspace.py`, which has no W0 owner; X-B1 makes it and moves the WIN-A mutant of `tests/mutations/workspace.json` to `atomic.json`). (2) `sweep_temps(target, lock)` checks the lock. (3) W0 §4 line 218: the sweeper of `bench/discrimination/<task>/` is X-E. (4) X-C `verify` lstats `campaign.lock` and names leaked temps; `acquire` refuses a non-regular lock. (5) `make_writable` lstat-first | design to this file; `rename_with_retry` and the lock check are inside X-B1's own module, so nothing in another slice changes before the answer. Sections that rest on S-B4 are marked `provisional (seam S-B4)` |

## 4. Temps are invisible to every reader, and never silently (RV-DS 6, RV-TA 6, RV-SEC W1-B 1)

A temp must never be read as a record, and the hiding must not hide a tamper. There are three kinds of reader.

| Reader | Hazard from a leaked temp | Control | Test |
| --- | --- | --- | --- |
| `git status --porcelain` over `bench/campaigns` and `bench/discrimination` (ADR-0018 §11(b), run by `bench campaign verify`) | an untracked temp reads as a tampered committed folder, so `verify` refuses with `HB-CMP-003` and no sweep exists | the three `.gitignore` lines (W0 §13, X-C adds them in E1). **Measured** (spike E1-S2, a scratch repo, `-uall`): with those patterns, `campaign.lock`, `x.json.tmp-12-<32 hex>`, `y.json.tmp-9-<32 hex>` and a temp **folder** with a file inside are all absent from the porcelain output, while `real.json` and `campaign.lock.bak` are listed | X-C's gitignore test |
| `bench campaign verify` "every content-addressed file's name equals its hash" (ADR-0018 §11(b)) | a temp's name is not a hash. **And the reverse (RV-SEC 1):** the ignore patterns and the `is_temp_name` skip also hide a *folder* named like a temp, holding arbitrary files, and a `campaign.lock` that is a folder or a link | `verify` skips names for which `atomic.is_temp_name` is true and never deletes (the sweep owns deletion, under `campaign.lock`). **It does not skip silently:** it prints one warning line with the count and the names of every temp-named entry, and it `lstat`s `campaign.lock` and fails (`HB-CMP-003`) unless it is a regular file. `acquire` of the lock refuses a non-regular `campaign.lock` the same way (RV-SEC 8: `oslock.acquire` opens with no `O_NOFOLLOW`, and `heartbeat` calls `os.utime` by path) | X-C's tests: `test_campaign_verify_ignores_a_leaked_temp_and_the_sweep_removes_it`, `test_campaign_verify_reports_leaked_temps_by_name`, `test_campaign_verify_rejects_a_lock_that_is_a_folder_or_link`, `test_campaign_acquire_refuses_a_non_regular_lock` (assertions defined here; **provisional (seam S-B4)**) |
| code that globs the archive folder | `report/judges.py:216` does `glob("attempt-*")` and `int(p.name.split("-")[1])`: a leaked `attempt-1.tmp-123-<hex>` raises `ValueError`; `report/pack_improvement.py:783` filters with `rsplit("-", 1)[-1].isdigit()`, which a temp passes when its nonce is all digits (probability about 3e-7, not zero) | one reader, `archive.attempt_dirs(run_dir, cell_id) -> list[Path]`, with `re.fullmatch(r"attempt-(\d+)")`, sorted by number. It is `pack_improvement._attempt_dirs` made strict and moved to `archive.py` (RV-SIM 7: no third helper). `judges.py` uses it in E1 (X-B2 edits it: not a hub file in W0 §13); `pack_improvement.py` switches in E3 and deletes its private copy (X-A3; W0 §4 and §13 carry the request, S-B3 granted) | `test_attempt_dirs_ignores_a_leaked_temp_sibling`; `test_the_judge_artifact_text_survives_a_leaked_archive_temp` |
| `bench validate` over `bench/discrimination/<task>/` (X-E) | same as the campaign readers | X-E skips `is_temp_name` names, names them in a warning line, and **sweeps** them before a discriminate run (RV-DS 3). `sweep_temps` needs a lock: X-E holds the discrimination run's own lock for the task. **Provisional (seam S-B4)**, W1-E carries it | X-E's reader test gains the temp case |

`report/credentials.py:91` globs `*/attempt-*/home` and would also scan a temp's home copy for credential values. That is harmless and arguably correct (a leaked copy is a copy), so it is left unchanged and noted.

## 5. The crash window between rename and rows (RV-DS 9): the one recovery rule (a specification; **X-K1 builds it in E3**)

**Rev 2 scope change (Coordinator ruling on RV-SIM W1-B 1; W0 §4).** `recover_archive` has no caller until resume (X-K1, E3), and the crash fixtures exist there. It is **not built in E1**: X-B2 ships `archive_cell`, the strict `verify` and `attempt_dirs`. This section is the contract X-K1 builds to; it carries no E1 code, no E1 test, no mutant and no event.

**Order of operations for one archive entry.** (1) the folder is renamed into place; (2) each `archive_files` row is appended; (3) `cell.archived` is appended; (4) the workspace is deleted (only after the verified event, US-19). Each step is durable before the next begins. Rows live in a different ledger segment than events, so no single append spans (2) and (3).

**The rule (W0 §4, quoted):** "if `final` exists and its rows are absent, recompute the rows from the folder, compare them with the source (still in the archive root or the working copy), then append them. If `final` exists and its rows are present, verify only." Stated once, covering the case W0 does not list (rows partly present):

> **If `final` exists:** recompute the rows (source rows hash the **source** bytes; the folder's file set and bytes are compared with them), require every already-recorded row to equal its recomputed row, append **only the rows whose key is absent** (`(run_id, cell_id, archive_attempt, snapshot, path)`, ADR-0015 §5), then append `cell.archived` if it is absent. Appending only absent keys makes a re-run idempotent, so zero, some and all rows recorded are the same path. **If `final` does not exist:** `sweep_temps(final)` (under the lock), then `archive_cell`. **One stop condition:** rows or the event are recorded but `final` is absent (the entry was removed after being recorded): not recoverable; `bench verify` reports `HB-LED-005`; stop and tell the operator.

On any difference between the recomputed rows and the source or the recorded rows the recovery raises `HB-LED-005` naming the first differing path and **changes nothing**: it does not delete the folder, append a row or touch the workspace. Never guess: a mismatch is a defect to look at, not a case to repair (a lingering process could have changed the working copy; the engine kills the job at cell end, ADR-0013, so this is rare and the response is a loud stop that leaves both copies for the operator).

**Advice for X-K1 (RV-PAT 4).** Return a frozen dataclass `Recovery(result: ArchiveResult, missing_rows: list[dict])` rather than a positional tuple. The function takes the same arguments as `archive_cell` plus `recorded_rows`. X-K1's tests: the rule under a real child killed after the rename (zero rows), with some rows recorded, with all rows recorded; the rebuild assertion (`archive_hash` of the recomputed rows equals a fresh archive of the same source); a changed workspace file and a differing recorded row both raise `HB-LED-005` and change nothing; the one stop condition. A mutant that appends all rows (duplicates) and one that skips the source comparison belong to X-K1's mutation set. `archive.recovered` (WARNING: `state`, `rows_recomputed`, `rows_appended`) is X-K1's event, with its own test.

**Snapshots (W1-J, ADR-0015 §5).** The same rule applies with the snapshot's folder and rows. The source of a turn-1 snapshot is the working copy, still turn 1's tree because turn 2 was never sent (ADR-0021 §4 row 5). X-J1 passes the snapshot path; this design does not name it.

## 6. `archive.py` rework (X-B2)

**Public surface after the rework.**

```python
@dataclass
class ArchiveResult:
    folder: Path; rows: list[dict]; archive_hash: str; total_bytes: int
    duration_ms: int | None = None           # NEW: measured publish time; None = not recorded

def archive_cell(cell_dir, dest_root, attempt, exclude_names) -> ArchiveResult   # signature unchanged: engine.py:807 needs no edit
def verify(folder, rows) -> None            # signature unchanged: views.py:688 needs no edit; now strict (below)
def attempt_dirs(run_dir, cell_id) -> list[Path]    # NEW (4)
def archive_hash(rows) -> str               # unchanged
def delete_after_verify(...), teardown(...)  # unchanged
make_writable                               # re-exported from atomic (S-B1: 5 src sites and 9 test lines still read archive.make_writable, see 7)
# recover_archive: NOT built here (5); X-K1, E3
```

**X-B2's commit order (so every red test fails on an assertion, RV-TA 1).** *Commit 0, behaviour-preserving:* extract `_copy_hashed(src, dst) -> (size, sha256)` out of today's loop body (`shutil.copyfile`, then `dst.stat().st_size` and `_sha(dst)`: it still hashes the **copy**), and add `attempt_dirs` as the naive unfiltered glob. The existing four tests of `tests/test_archive.py` stay green. *Commit 1, red:* the new tests below, each failing on its stated assertion. *Commit 2, green:* the rework. Without commit 0 the D1 and corrupted-copy tests would patch a symbol that does not exist and be red by `AttributeError`.

**`archive_cell` after the rework.**
1. If `os.path.lexists(folder)`: `BenchError("HB-USR-002", ...)` exactly as today. The message now says a complete archive exists (the folder can only be complete).
2. A private `_Copy` object holds the rows: `_Copy.fill(tmp)` and `_Copy.verify(tmp)` are the two callbacks passed to `publish_dir`. One object, not a closure over a mutable list.
3. `fill(tmp)`: for each entry from `_entries(cell_dir, exclude_names)` (the one definition of "what is archived": sorted, links recorded not followed, credential names skipped, folders created), copy files with `_copy_hashed(src, dst)`: read the **source** in 1 MiB chunks, write each chunk to `dst` **opened `"wb"`** (RV-SEC 7), hash **the bytes read**; return `(size, sha256)`. The row's `size` and `sha256` are the source's, taken in the same pass as the copy.
4. `verify(tmp)` is `archive.verify(tmp, rows)`: **the same function `bench verify` calls**, so there is one definition of "this folder matches these rows" (DM7). It re-reads every copied file and compares size and sha256 with the row (a bad copy fails here, before the rename), and **enumerates the folder** and requires the set of regular files to equal the set of `kind: file` rows (an extra or a missing file fails). Empty folders are copied but are not rows and are not compared (accepted: they carry no content; the archive hash never covered them). A path of a `kind: link` row must have no file in the folder.
5. After `publish_dir` returns, set `archive_attempt` on each row, compute `archive_hash`, and return an `ArchiveResult`.

**What changes for existing behaviour (E7, consistency across surfaces).**
- Today `rows` are hashed from the **copy** (`archive.py:77`, `_sha(dest)`), so `verify` compares a copy with a hash of itself: a corrupted copy passes. After the rework the row comes from the source and the copy is checked against it. This closes a gap that is not on the ADR's list; it is why `verify` before the rename is not vacuous.
- `bench verify` becomes stricter: an extra file in an old archive folder now yields `HB-LED-005`. `archive_cell` never copied an extra file, so archives written by this code have none (Inferred from reading `archive.py:55-80`). **First task of X-B2, before changing `verify`:** run `bench verify` over every archived run present on the host and the fixtures of `tests/archived_runs.py`, and record the result in its proof pack (a characterization step, not a permanent test).
- `engine._archive` (`engine.py:803-815`) is unchanged in E1. Its `cell.archived` event gains no field in this slice (D6/T7 not triggered). Next step, not scope: X-J1 adds `archive_ms` to `cell.archived` with the snapshot events, from `ArchiveResult.duration_ms`.
- ADR-0021 §4 row 6 ("outcome, no `cell.archived`: a `*.tmp-*` folder is redone; a complete final folder is re-verified and its event recorded") is implemented by the rule in 5 and is X-K1's call sequence.
- A tamper between `verify(tmp)` and the rename (a cell process writes into the visible temp) is **detected, not prevented** (RV-SEC 3): rows come from the source, so `delete_after_verify` (`archive.py:98-100`) re-verifies the published folder strictly before the workspace is deleted and keeps the workspace on `HB-LED-005`. Residual accepted per ADR-0012.

## 7. Patterns, named and justified

Climbed the Solution-Selection Ladder: YAGNI, then reuse in the codebase, then stdlib, then native, then installed dependency, then one line.

| Pattern | Where | Why it is the smallest correct idiom |
| --- | --- | --- |
| **Atomic Publish** (write to a sibling temp, then `os.rename`; the standard crash-safe idiom) | `publish_dir` | native rename is the only operation both atomic for a process crash and measured on NTFS (spike E1-S1) |
| **Idempotent Receiver** | `create_once` | equal bytes is a no-op success, different bytes is refused: the same compare-and-refuse rule as the ledger commands (ADR-0016 §2a) |
| **Callbacks (Strategy by function)** (`fill`, `verify`) | `publish_dir` | RV-PAT 2: two callables, not a subclass hook, so the name is not Template Method. `verify` is a required argument, so it cannot be *omitted*; a no-op `verify` is caught by the site scan (10.4), which requires a named function or method reference at each call |
| **Fail-Fast guard** (the explicit `lexists`) | `publish_dir` step 1 | makes "final exists" one behaviour on every platform instead of an OS accident |
| **Janitor / Sweeper** by strict name pattern | `stale_temps`, `sweep_temps` | one cleanup path; the strict regex cannot match a user's file; the lock argument makes the precondition a check |
| **Bounded Retry with Backoff** | `rename_with_retry` | WIN-A, measured here; **one copy** of the policy, used by `publish_dir` and `workspace._land` (RV-PAT 1) |
| **Reconciliation by derivation** (a rebuildable projection compared with its stored facts) | the recovery rule in 5 (X-K1) | rows are derivable from folder plus source, so no recovery journal is needed |

**Rejected, with reasons.**
- *A write-ahead journal or a `.complete` marker file*: a second store and a second definition of "complete" (DM7); the name already is the marker.
- *`os.replace` for the folder*: on POSIX it replaces an existing empty folder silently; the explicit `lexists` plus `os.rename` is exact. (`_land` uses `replace=True` for its own, different reason: a content-addressed destination that may already be a valid build.)
- *`tempfile.mkdtemp` / `mkstemp`* (ladder rung 3, stdlib): equally exclusive, and its random suffix could match a stricter regex, so it is a tie. W0 already fixed `<name>.tmp-<pid>-<uuid4 hex>` and the reviewers verified it; changing it costs a seam request for no behaviour gain, and one strict `TEMP_RE` is shared by the sweep, `verify` and the gitignore lines. Kept.
- *Best-effort cleanup of the temp when `fill` raises*: loses the partial copy as evidence and adds a second cleanup path to test. W0 says leave it for the sweep. Kept.
- *A `Published` result class, a retry policy object, a config knob*: YAGNI.
- *A new error code for "the volume cannot hard-link"* (HB-LED-009): refused by W0 rev 3 (S-B1). The `OSError` propagates unchanged; a code is added when a volume that cannot link appears.
- *Folding `gateway/store.write_once` onto `create_once`*: it has its own race-loser contract (a winner with different bytes is accepted when it recomputes, `store.py:74-92`). Different semantics, not a duplicate; recorded in the sweep (12) and the allowlist (10.4).
- *Retrying `os.link` on `PermissionError`*: no instance observed; WIN-A was observed for a folder rename only. See the `assume:` below.
- *Deleting the `archive.make_writable` re-export now* (RV-PAT 3): 5 `src/` sites in four files (`plan.py:321`, `grade/_changes.py:108,122`, `grade/correctness.py:237`, `grade/drift.py:105`) and 9 test lines read it, in files that other tracks own (`plan.py` is X-A1's hub). W0 §4 says "archive re-exports it". Only `workspace.py` is repointed, in the same hunk as `_land`.

**`simplify:` markers (ceiling and upgrade trigger).**
- `simplify:` `archive.make_writable` stays a re-export of `atomic.make_writable`. Ceiling: the 5 `src/` sites above. Upgrade trigger: any edit to one of those lines by its owner repoints it; delete the alias when the last one goes.
- `simplify:` `sweep_temps` is made safe by the caller's lock, now checked (`oslock.is_held`), not by PID liveness. Ceiling: single-writer per target, true for all consumers today (run lock, `grade.lock`, `campaign.lock`). Upgrade trigger: a consumer with concurrent writers to one target.

**`assume:` markers.**
- `assume:` a transient `PermissionError` does not occur on `os.link` of a just-closed temp (an antivirus scan). **Confirm:** a one-time soak of 500 `create_once` calls on the dev host, in X-B1's proof pack (not a ring test). **If false:** `create_once` raises an `OSError` loudly, never a wrong result; add the same bounded retry.
- `assume:` `os.fsync` on a re-opened `O_RDWR` handle flushes data written through the already-closed handle (Windows `FlushFileBuffers` and POSIX `fsync` act on the file, not the handle). **Confirm:** platform documentation; not testable by killing a process. **If false:** durability on power loss is weaker (already Flagged); process-crash atomicity is unaffected.
- `assume:` a `kill` at a random instant never exposes a final name with partial content on NTFS. **Confirm:** spike E1-S1 (one kill of one child at 1 s, 98 of 400 files in the temp, no final) plus the deterministic crash-point tests in 10.2. **If false:** `verify` of the rows still catches it (HB-LED-005).
- `assume:` `os.fstat(fd)` and `os.lstat(path)` report the same `st_ino` for one NTFS file on this host (CPython 3.14 fills `st_ino` from the file index). **Confirm:** the happy-path `create_once` test on the Windows dev host; it is green only if the two agree. **If false:** that test fails loudly on every call, and the identity check compares `(st_size, st_mtime_ns, st_nlink == 2)` instead.
- `assume:` `oslock.is_held(path)`, called from the process that holds the lock through another descriptor, reports `True` on both Windows (`msvcrt.locking`) and POSIX (`flock`). **Confirm:** `test_sweep_temps_removes_temps_only_while_the_lock_is_held` uses a real `RunLock` on both jobs. **If false:** the test fails on the job that disagrees, before any consumer relies on it.
- `assume:` a refusal longer than the 1.55 s backoff does not occur on a freshly copied tree under a real scanner (RV-DS 5: the backoff was measured against a test handle only). **Confirm:** the first pilot's `atomic.publish.rename_retries` and `rename_ms` (11); revisit the tuple from those numbers, not by reasoning. **Trigger:** any `atomic.publish_failed` with `phase=rename`, or `rename_retries >= 4` on any publish. **If false:** the cell's archive is lost to `cell.archive_failed` with the workspace kept, never a wrong result.

## 8. Failure-mode analysis

| # | Mode | Category | Disposition | Mechanism and evidence | Test |
| --- | --- | --- | --- | --- | --- |
| F1 | process killed during `fill` | state / partial write | **prevent** (no final name) + **recover** (sweep, redo) | temp only; Verified spike E1-S1 | `test_a_kill_during_fill_or_before_the_rename_leaves_no_final_name` (param `fill`), `test_a_kill_mid_copy_leaves_no_final_folder_and_the_redo_succeeds` |
| F2 | killed after verify, before rename | state | same as F1 | temp only | same test (param `rename`) |
| F3 | killed between the rename and the first row | state / inconsistency across stores | **recover** (rule in 5) | the rule; built and tested by X-K1 (E3) | X-K1's `test_resume_recovers_every_crash_state` (not in E1) |
| F4 | killed between two row appends | state | **recover** (append absent keys only) | same rule | X-K1 (same test, param) |
| F5 | killed between the last row and the event | state | **recover** | same rule | X-K1 (same test, param) |
| F6 | killed between write and link in `create_once` | state | **prevent** + recover | no final; temp swept | `test_a_kill_between_write_and_link_leaves_no_final_file` (D3) |
| F7 | stale `<name>.tmp-<pid>` after PID reuse (DS-5) | state | **prevent** | nonce in the name; exclusive create; `fill` gets an empty folder | `test_publish_dir_hands_fill_an_empty_exclusively_created_folder` |
| F8 | squatted junction or symlink at the temp name (SEC F10) | hostile input | **prevent** | `os.mkdir` / `O_EXCL` raise; nothing written through the link | `test_publish_dir_refuses_a_squatted_reparse_point` |
| F9 | sweep follows a junction and deletes outside (SEC F10) | state / hostile | **prevent** | `lstat` first; unlink, never recurse | `test_sweep_temps_unlinks_reparse_points_without_recursing` |
| F10 | sweep deletes a user's file | input | **prevent** | strict `TEMP_RE`, base must equal the target name | `test_stale_temps_lists_only_this_targets_strict_temp_names` |
| F11 | a leaked temp trips `bench campaign verify` (DS-6), or the ignore hides a tamper (SEC 1) | state / hostile | **prevent** the trip; **detect** the hiding | gitignore lines (X-C) + `is_temp_name` skip that names what it skips + `lstat` of the lock; sweep under `campaign.lock` (campaign) or X-E's lock (discrimination) | X-C's four tests, X-E's reader test (4) |
| F12 | a leaked temp breaks a reader (`judges.py:216`) | state | **prevent** | `archive.attempt_dirs` | `test_attempt_dirs_ignores_a_leaked_temp_sibling`, `test_the_judge_artifact_text_survives_a_leaked_archive_temp` |
| F13 | `create_once` with different bytes | input | **detect** + refuse | HB-LED-007, original untouched | `test_create_once_refuses_different_bytes_and_keeps_the_original` |
| F14 | `create_once` with equal bytes (a retry) | input / duplicate | **mitigate** (no-op) | returns `False` | `test_create_once_creates_then_noops_on_equal_bytes` |
| F15 | the final path is a folder or a link | input | **detect** + refuse | HB-LED-007 "not a regular file" | `test_create_once_refuses_a_non_regular_existing_path` |
| F16 | `os.write` text-mode translation corrupts bytes (measured) | platform | **prevent** | `O_BINARY` (and `"wb"` in `_copy_hashed`) | `test_create_once_round_trips_the_bytes_that_text_mode_corrupts`; M2 is killed by the Windows run only |
| F17 | write, fsync or link fails in `create_once`, including a volume that cannot hard-link | dependency / resources | **detect**, no fallback, no leftover | the `OSError` propagates unchanged (W0 S-B1: no HB-LED-009); `finally` closes the descriptor and removes the temp | `test_create_once_leaves_no_temp_and_propagates_when_a_step_fails` (params `fsync`, `link EPERM`, `link FileNotFoundError`) |
| F18 | folder rename refused while a handle is open (WIN-A, measured) | dependency / time | **recover** (bounded retry), then raise | `rename_with_retry` over `RENAME_BACKOFF` | `test_a_rename_refused_n_times` (params `twice then succeeds`, `always`, `FileExistsError`), `test_a_rename_refused_by_an_open_handle_succeeds_once_it_closes` (Windows) |
| F19 | `final` appears between the check and the rename (second writer) | concurrency | **detect** + accept | `FileExistsError` from `os.rename` on Windows; one writer by lock; on POSIX an empty-folder race is accepted | covered by the lock precondition; `test_publish_dir_refuses_when_final_exists_and_touches_nothing` for the sequential case |
| F20 | corrupted copy: a copy-logic or source-read error | state | **prevent** | rows from source bytes, copy re-read by `verify` before the rename. **Not covered (RV-PAT 5):** the re-read is served from the OS cache, so silent disk corruption of the written bytes is not caught here; it is accepted in 14 | `test_a_corrupted_copy_fails_verification_before_the_rename` (red today) |
| F21 | source file changes during the copy (a lingering process) | concurrency | **accept** | the row hashes the bytes actually read, so row and copy agree; ADR-0015 §4 accepts a non-quiescent snapshot; `job_active_processes` shows it. Residual: the archive may contain a torn mix of two versions of one file | none |
| F22 | disk full during `fill` | resources | **detect** | `OSError` ENOSPC propagates; temp left; the engine records `cell.archive_failed` (`engine.py:590-592`) and keeps the workspace | none new: the existing engine path |
| F23 | a sweep fails to delete (locked file) | resources | **detect** | raises; caller stops | `test_sweep_temps_raises_when_a_temp_cannot_be_removed` |
| F24 | recomputed rows differ from the source or a recorded row | state | **detect**, change nothing | HB-LED-005 (rule in 5) | X-K1 |
| F25 | power loss or host crash between file fsyncs and rename | resources / time | **accept**, residual | untestable by killing a process; Flagged in spike E1-S1 | none |
| F26 | cross-volume rename | dependency | **not reachable** | the temp is a sibling of `final`, so the same folder and volume. The spike's "cross-volume archive root" worry applies only to a `fill` that wrote elsewhere; a `fill` writes only into the given folder | none |
| F27 | `publish_dir` called with a missing parent | input | **detect** | `os.mkdir` raises `FileNotFoundError`, nothing created | `test_publish_dir_with_a_missing_parent_raises_and_creates_nothing` |
| F28 | the temp name is swapped between write and link (SEC 2) | hostile | **detect** | fd kept open; `st_dev`/`st_ino` of the fd and of `path` compared; mismatch unlinks the name this call made and raises HB-LED-007 | `test_create_once_refuses_a_file_swapped_in_before_the_link` |
| F29 | `os.unlink(tmp)` fails after a successful link (DS 1) | dependency | **mitigate** | logged `atomic.temp_leaked`, swallowed, returns `True`; the sweep removes it | `test_create_once_returns_true_when_the_temp_unlink_fails` |
| F30 | `sweep_temps` called without the lock (DS 4) | concurrency | **prevent** | `oslock.is_held(lock.path)` checked before any deletion | `test_sweep_temps_removes_temps_only_while_the_lock_is_held` |
| F31 | a write into the visible temp between `verify` and the rename (SEC 3) | hostile | **detect** | `delete_after_verify` re-verifies strictly; workspace kept | `test_a_file_added_after_verify_is_caught_by_delete_after_verify` |
| F32 | `make_writable` re-modes a link's target (SEC 6) | hostile | **prevent** | lstat first, no chmod through a link, add `S_IWUSR` to the current mode | `test_make_writable_does_not_chmod_through_a_link` (POSIX job; symlink) |

## 9. RV-DS dispositions taken on trust in W0, restated as tests

| W0 disposition (RV-DS) | Tests in this design |
| --- | --- |
| **DS-5**: `publish_dir` stale `.tmp-<pid>` reuse on PID reuse | `test_publish_dir_hands_fill_an_empty_exclusively_created_folder` (a pre-created `final.tmp-<this pid>-<other nonce>` folder with `old.txt` is untouched and absent from the result; with `os.getpid` and `uuid.uuid4` patched to the stale folder's values, `publish_dir` raises `FileExistsError` and writes nothing into it); the strict file-set verify: `test_verify_rejects_an_extra_file_and_a_missing_file` |
| **DS-6**: `create_once` temp names and sweep; a leaked temp trips `verify` | `test_create_once_temp_names_are_unique_and_exclusive`, `test_a_kill_between_write_and_link_leaves_no_final_file` (the leaked temp is listed by `stale_temps` and removed by `sweep_temps`), plus X-C's `test_campaign_verify_ignores_a_leaked_temp_and_the_sweep_removes_it` |
| **DS-9**: crash window between rename and row append, and its recovery rule | the rule in 5; **built and tested by X-K1 in E3** (Coordinator ruling on RV-SIM W1-B 1) |
| **DS-7**: `campaign.lock` ignore coverage | W0 §13 (X-C adds the lines) and X-C's `test_gitignore_covers_every_temp_name_and_the_campaign_lock`; the porcelain behaviour is Verified in spike E1-S2 (13) |

## 10. Test plan

### 10.1 Directive map (Testing Strategy triggers)

| Trigger | Directive | How it is met |
| --- | --- | --- |
| D0 hygiene | always | `ruff` clean; no commented-out code; each handled failure mode above has a test or an explicit "none" with the reason |
| T1 pure logic (`TEMP_RE`, `is_temp_name`, row and set comparison) | D1 + D2 | unit tests; the mutation sets in 10.3. No `hypothesis` test: a fixed input kills each mutant it was proposed for (RV-SIM 3) |
| T3 new module and dependency direction | D3 | 10.4 (a cycle would fail at import, so no separate import test) |
| T4 filesystem persistence | D4 | every test uses the real filesystem in `tmp_path`; the crash tests use a real child process and `os._exit`; nothing mocks the filesystem. Fakes only for the OS refusal that cannot be provoked on demand (`PermissionError` bound, `os.link` failure) and the POSIX switch |
| T7 event or payload schema | D6 | **not triggered**: no ledger field is added in this slice (6) |
| T8 a fake at a boundary | D7 | the fakes are one-line monkeypatches of `os.link`, `os.rename`, `atomic._POSIX`; each has a real-filesystem sibling, and the **real-wiring tests** (below) drive the real composition |
| T5, T6, T9 to T14 | D5, A1 to A6 | not applicable: no network, no tool, no model |

**Red-first protocol (README §2a: "red" is a failed assertion, never an `ImportError` or `AttributeError`).** Every table below has a **Red because** column naming the assertion that fails and why.
- **X-B1.** Commit 1 adds `atomic.py` with the *naive skeleton* (every public name defined, so no test fails by import): `create_once` writes `path` in place and returns `True` without comparing; `publish_dir` calls `fill(final)` and returns; `stale_temps` globs `<name>.tmp-*`; `sweep_temps` runs `shutil.rmtree` with no lstat and no lock check; `rename_with_retry` is one bare `os.rename`; `_fsync_dir` is a no-op; `make_writable` is today's body; `_POSIX` and `O_BINARY` are defined. The tests are observed failing on their assertions. Commit 2 makes them green.
- **X-B2.** Commit 0 (behaviour-preserving extraction of `_copy_hashed`, naive `attempt_dirs`) lands first, see 6. Commit 1 holds the red tests; commit 2 the rework.
- A **pin** test with no red phase says so in its Red-because cell and names the mutant it exists to kill.

### 10.2 Tests by node id (each names the failure it alone catches)

`tests/test_atomic.py` (X-B1; real filesystem):

| Node | Asserts | Red because (on the naive skeleton) | Catches |
| --- | --- | --- | --- |
| `test_create_once_round_trips_the_bytes_that_text_mode_corrupts` | the file on disk equals `b"a\nb\r\nc\n"` byte for byte | the skeleton opens without `O_BINARY`: on Windows 10 bytes on disk. **On POSIX the skeleton is green: this is a Windows-run test** | M2 no `O_BINARY` (measured: 7 bytes became 10) |
| `test_create_once_creates_then_noops_on_equal_bytes` | first call `True`, second `False`, file unchanged, no temp left | the skeleton returns `True` on the second call | M3 |
| `test_create_once_refuses_different_bytes_and_keeps_the_original` | `BenchError.code == "HB-LED-007"`, message names the path, original bytes intact, no temp left, exactly one `atomic.create_once` record (`outcome == "conflict"`, `error_code == "HB-LED-007"`); the equal-bytes call of the test above logs none | the skeleton overwrites and raises nothing | M4 |
| `test_a_kill_between_write_and_link_leaves_no_final_file` **(D3)** | a child patches `os.link` to `os._exit(3)`; the child's exit code is 3; afterward `path` is absent, `stale_temps(path)` lists exactly one **file**, `create_once` then succeeds, and `sweep_temps(path, lock)` removes the old temp and returns it | the skeleton never calls `os.link`: exit code is 0, and `path` exists | M1 |
| `test_create_once_temp_names_are_unique_and_exclusive` | two calls use different temp names (spy on `os.open`); with `os.getpid` and `uuid.uuid4` patched, a pre-created temp of that name makes the call raise `FileExistsError` and leaves it unchanged | the skeleton opens no temp: the spy sees zero names | M5, M6 |
| `test_create_once_refuses_a_non_regular_existing_path` (params: a folder; a symlink [POSIX job]; a file swapped for a symlink after `lstat` [POSIX job]) | `HB-LED-007`, no temp left, the target of the link untouched | the skeleton raises `IsADirectoryError`, not `BenchError` | M7, M27 (no `O_NOFOLLOW`/identity check on the read) |
| `test_create_once_refuses_a_file_swapped_in_before_the_link` (RV-SEC 2) | `os.link` is patched to link a *different* pre-made file at `path`: `HB-LED-007`, `path` absent afterwards (the name this call made is removed), no temp, the pre-made file's bytes intact | the skeleton never links, so no raise | M22 no identity check |
| `test_create_once_leaves_no_temp_and_propagates_when_a_step_fails` (params: `os.fsync` raises `OSError(28)`; `os.link` raises `OSError(1)`; `os.link` raises `FileNotFoundError`) | the **same exception object** reaches the caller (not wrapped, no code, no fallback); `path` absent; no temp left | the skeleton writes `path` before failing: `path` exists | M8 falls back to `os.replace`; M24 no `finally` |
| `test_create_once_returns_true_when_the_temp_unlink_fails` (RV-DS 1) | `os.unlink` raises `PermissionError` for the temp only: the call returns `True`, `path` has the bytes, exactly one `atomic.temp_leaked` record (caplog) naming the temp; `sweep_temps` then removes it | the skeleton logs nothing | M23 the failure raises |
| `test_publish_dir_publishes_only_a_verified_complete_folder` | returns `fill`'s result; `final` has exactly the files; no temp remains; **exactly one `atomic.publish` record** with integer `fill_ms`, `fsync_ms`, `verify_ms`, `rename_ms`, `rename_retries == 0` and `files`, `bytes` equal to the real counts | the skeleton logs no record | baseline; the telemetry field values (RV-TA 4) |
| `test_publish_dir_refuses_when_final_exists_and_touches_nothing` | param: final a populated folder, an **empty** folder, a file, a dangling link: `FileExistsError`; `fill` never called; no temp created; contents unchanged | the skeleton calls `fill` | M9 no `lexists` (the empty-folder case separates it from `os.rename`: on POSIX the rename would succeed silently) |
| `test_publish_dir_with_a_missing_parent_raises_and_creates_nothing` | `FileNotFoundError`; `fill` never called; nothing created (RV-TA 6) | the skeleton calls `fill(final)`, which raises something else after creating nothing; **assert `fill` was not called** | F27 |
| `test_publish_dir_never_renames_when_fill_or_verify_fails` (params `fill raises`, `verify raises`) | the exception propagates, `final` absent, the temp is left, one `atomic.publish_failed` record with `phase` `fill` or `verify` and, for a `BenchError`, its `error_code` (caplog) | the skeleton has no temp: `final` exists and no record | M10 |
| `test_publish_dir_hands_fill_an_empty_exclusively_created_folder` (DS-5, SEC F10) | a stale `final.tmp-<other pid>-<nonce>` with `old.txt` is untouched; `fill` sees an empty folder; with `os.getpid` and `uuid.uuid4` **patched** to the stale folder's values, the call raises `FileExistsError` and writes nothing into it | the skeleton passes `final` itself (non-empty or absent) | M11 `exist_ok=True` / reuse |
| `test_publish_dir_refuses_a_squatted_reparse_point` | `os.getpid` and `uuid.uuid4` are **patched** so the temp name is known (RV-SEC 5a). Windows: a junction (`mklink /J`) at that name makes `publish_dir` raise `FileExistsError`; the junction target's contents are unchanged. POSIX: the symlink variant. Skipped only on Windows when symlink creation raises winerror 1314; **on POSIX a failure to make a symlink fails the test** | the skeleton does not create the temp name, so no raise | M11 |
| `test_the_posix_job_does_not_skip_the_symlink_variants` (RV-SEC 5b) | on `os.name == "posix"`, the shared `can_symlink(tmp_path)` helper returns `True` (a failure here fails the job); on Windows it is skipped with the stated reason. The macOS job is the one that runs the symlink variants of this file and of `test_atomic_sites.py`, and CI fails if its junit report lists any of them as skipped | none: a pin whose mutant is "the symlink tests skip on every runner" | RV-SEC 5 |
| `test_a_kill_during_fill_or_before_the_rename_leaves_no_final_name` (param `fill`, `rename`) | a child exits hard inside `fill` (after three files) or inside a patched `os.rename`; `final` absent; exactly one temp folder; the next `publish_dir` succeeds; the old temp stays until `sweep_temps` removes it | the skeleton fills `final` itself, so it exists after the kill | M12 |
| `test_every_file_is_fsynced_through_a_write_handle_before_the_rename` | recorder over `os.open` and `os.fsync`: every fsynced descriptor was opened with write access; the count equals the file count; all fsyncs precede `os.rename` and follow `fill` | the skeleton never fsyncs: count 0 | M13 |
| `test_the_folder_fsync_body_runs_for_the_temp_then_the_parent` | `_POSIX` patched to `True` with a recorder on `_fsync_dir` (the real body replaced): called for the temp before the rename, for the parent after. With `_POSIX` patched to `False`: never called | the skeleton's `_fsync_dir` is never called: 0 calls, expected 2 | the branch body |
| `test_the_real_publish_dir_fsyncs_the_folder_only_on_posix` (RV-TA 2) | **nothing patched**: a recorder wraps the real `atomic._fsync_dir` (calls through); on Windows the recorder sees 0 calls and the publish succeeds (the real branch: a directory cannot be fsynced); on POSIX it sees 2 | on the POSIX job the skeleton makes 0 calls. On Windows it is green by design: it kills M14 | M14 `_POSIX = True` (killed by the Windows run: the real `_fsync_dir` would raise `PermissionError`); M14b `_POSIX = False` (killed by the POSIX run) |
| `test_posix_flag_default_follows_the_platform` | `atomic._POSIX == (os.name == "posix")`, unpatched | none: a pin, green on the skeleton; it exists to kill M14/M14b on whichever host mutates | M14, M14b |
| `test_a_rename_refused_n_times` (RV-TA 5; portable) | `os.rename` patched, `time.sleep` patched. Param `twice then succeeds`: the publish succeeds, `final` exists, `rename_retries == 2` in the `atomic.publish` record, the sleeps equal the first two `RENAME_BACKOFF` values. Param `always`: `PermissionError` after `len(RENAME_BACKOFF)` calls, `final` absent, the temp left, one `atomic.publish_failed` with `phase=rename`. Param `FileExistsError`: exactly **one** call, the error raised, no sleep | the skeleton calls `os.rename` once: `twice` raises | M15 no retry; M16 the last refusal swallowed; M21 retries `FileExistsError` |
| `test_a_rename_refused_by_an_open_handle_succeeds_once_it_closes` (Windows only, skipped elsewhere with reason) | `fill` leaves a handle open and a timer closes it after 0.3 s: the publish succeeds with `rename_retries >= 1` (the real WIN-A behaviour, D7 sibling of the portable test) | the skeleton's single rename raises winerror 5 | M15 |
| `test_stale_temps_lists_only_this_targets_strict_temp_names` | lists the file and folder temps of `final`; excludes `final.tmp-notes`, `other.tmp-1-<hex>`, a 31-digit nonce, a nonce with a trailing newline, `final` itself; `is_temp_name` agrees on every one of those names | the skeleton's glob lists `final.tmp-notes` | M17 |
| `test_sweep_temps_unlinks_reparse_points_without_recursing` (SEC F10) | a temp junction to a folder with a sentinel file: the junction is gone, the sentinel remains, its record has `kind == "link"`; a temp folder holding a read-only file is removed; a **symlink inside a temp folder** pointing at a sentinel is unlinked and the sentinel is untouched (POSIX job); one `atomic.temp_swept` record per deletion (caplog) | the skeleton logs no record; with a symlink inside the folder it raises | M18 (the `kind == "link"` assertion also kills it where `rmtree` happens not to follow a junction); M19 no `make_writable` |
| `test_sweep_temps_raises_when_a_temp_cannot_be_removed` | `shutil.rmtree` patched to raise: the error propagates (CLN-A) | the skeleton swallows nothing, so it is green for the `OSError`; **assert the sibling temp that would be swept next is still present** (the sweep stopped) | M20 swallowed error |
| `test_sweep_temps_removes_temps_only_while_the_lock_is_held` (RV-DS 4) | a real `RunLock` on a lock file: with it held the temp is removed; after `release()`, `sweep_temps` raises `ValueError` and **the temp still exists**. A `RunLock` whose file is held by a *different* process also passes the check (documented: it proves a lock is held, not whose) | the skeleton sweeps without a lock check: the temp is gone | M25 |
| `test_make_writable_does_not_chmod_through_a_link` (RV-SEC 6; POSIX job) | a symlink to a sentinel file of mode `0o444`: after `make_writable(os.unlink, link, None)` the sentinel is still `0o444` and the link is gone; a plain read-only file of mode `0o444` becomes `0o644`-or-wider **keeping its other bits** (`0o444` → `0o644`, not `0o200`) | today's body replaces the mode with `S_IWRITE` and follows the link | M26 |

`tests/test_archive.py` (X-B2; the existing four tests stay unchanged):

| Node | Asserts | Red because (today, after commit 0) | Catches |
| --- | --- | --- | --- |
| `test_a_kill_mid_copy_leaves_no_final_folder_and_the_redo_succeeds` **(D1)** | a child runs `archive_cell` with `archive._copy_hashed` (extracted in commit 0, so it exists) patched to `os._exit(3)` on its third call; the exit code is 3; afterward `attempt-1` is absent and one `attempt-1.tmp-*` exists with a partial tree; `sweep_temps(attempt-1, lock)` then `archive_cell` produce a complete archive whose `verify` passes | `attempt-1` **exists** with two files, and the redo raises `HB-USR-002` | direct-to-final copy (archive.py:57-77) |
| `test_a_corrupted_copy_fails_verification_before_the_rename` | `_copy_hashed` wrapped to call the real one and then flip one byte of the written copy: `BenchError` `HB-LED-005`, no final, the temp left | `archive_cell` hashes the corrupted copy, so it **returns** and `pytest.raises` fails | A1 rows hashed from the copy |
| `test_verify_rejects_an_extra_file_and_a_missing_file` | an extra file, a missing file and a file at a link row's path each raise `HB-LED-005`; an extra empty folder does not | today's `verify` is row-only: the extra file and the file at a link row's path do not raise (the missing file already raises, so that param is green today by design) | A2 |
| `test_archive_cell_refuses_when_a_complete_archive_exists` | `HB-USR-002`; the existing bytes unchanged | none: green today; it guards the forbidden update (append-only) and must stay green | the forbidden update |
| `test_attempt_dirs_ignores_a_leaked_temp_sibling` | `attempt-1`, `attempt-2` and a leaked `attempt-1.tmp-<pid>-<digits-only nonce>`: returns the first two in numeric order | commit 0's naive glob returns the temp too | A3 |
| `test_a_file_added_after_verify_is_caught_by_delete_after_verify` (RV-SEC 3) | `os.rename` wrapped to add a file to the temp first (the cell writes between `verify(tmp)` and the rename); `delete_after_verify` raises `HB-LED-005` and the workspace folder still exists | a strict `delete_after_verify` does not exist: it passes (row-only `verify`) and deletes the workspace | A4 `delete_after_verify` skips the verify |

`tests/test_report_judges.py` (X-B2 edits `judges.py`): `test_the_judge_artifact_text_survives_a_leaked_archive_temp` (a leaked temp beside `attempt-1` does not raise `ValueError`; the text comes from `attempt-1`). **Red today** with the `ValueError` of `int("1.tmp")` at `judges.py:216`.

`tests/test_engine.py` (**real-wiring test**, README §2a item 3): `test_the_engine_archive_goes_through_publish_dir` runs the existing happy-run fixture (`test_happy_run_completes_archives_and_deletes_every_cell`'s `base`) with a recorder wrapped around the real `atomic.publish_dir`; asserts one call per cell and that every `cell.archived` folder exists; red today (zero calls) and red if `archive_cell` stops calling it. `tests/test_views.py::test_bench_verify_passes_a_run_archived_by_the_atomic_path` is the surface-consistency pin (writer then compute reader): green today by design, red when writer and reader drift. The WIN-A wiring of `workspace._land` is the existing `tests/test_workspace.py::test_a_transient_windows_rename_refusal_is_retried` (it drives the real `_land`); its retargeted mutant (below) is red if the `rename_with_retry` call is removed.

X-C's file (assertions defined here; **provisional (seam S-B4)**): `test_gitignore_covers_every_temp_name_and_the_campaign_lock` runs `git check-ignore` on a temp **file**, a temp **folder** and its inner file under `bench/campaigns/<id>/` and `bench/discrimination/<task>/`, and on `bench/campaigns/<id>/campaign.lock`, and asserts all are ignored while `x.json` and `campaign.lock.bak` are not. `test_campaign_verify_ignores_a_leaked_temp_and_the_sweep_removes_it`: leak a temp, `verify` passes, the campaign sweep under `campaign.lock` removes it. `test_campaign_verify_reports_leaked_temps_by_name`: the warning line holds the count and each name (RV-SEC 1). `test_campaign_verify_rejects_a_lock_that_is_a_folder_or_link` and `test_campaign_acquire_refuses_a_non_regular_lock` (RV-SEC 1, 8). X-E's reader test gains a leaked-temp case (4).

One-time proofs outside the rings (proof pack only): the 500-call `create_once` soak (the `assume:` in 7); the `bench verify` characterization run over existing archives (6); **one run of the symlink variants on a host with symlink rights** (macOS in the existing `macos-latest` CI job, or Windows Developer Mode) recording the three behaviours unmeasured on this host: `os.unlink` on a Windows *directory* symlink, `O_EXCL` onto a dangling symlink on Windows, and the sweep of a symlink temp (RV-SEC 5c); the first pilot's `atomic.publish` numbers against the 1.55 s backoff (RV-DS 5).

### 10.3 Directive D1: mutation sets

`tests/mutations/atomic.json` (new, X-B1) holds M1 to M27 and M14b, exactly as named in the *Catches* column above (28 mutants; revision 1 had 26 and spent M16 "unbounded retry", M21 "no log", M24 and M25 on things this revision removed or merged: RV-SIM 3, 6 and the move of `recover_archive`). `tests/mutations/archive.json` (existing) gains A1 to A4. `tests/mutations/workspace.json` loses its WIN-A entry on `RENAME_BACKOFF = ...` (the constant moved) and gains one on the `_land` line (`rename_with_retry(tmp, dest, replace=True, settled=lambda: valid(dest))` replaced by `os.replace(tmp, dest)`), killed by `test_a_transient_windows_rename_refusal_is_retried`. Every mutant names the test that must kill it, and `tests/test_mutate_check.py::test_every_named_test_in_the_mutation_sets_exists` (MUT-B, `:704`) keeps the ids honest. M2 dies only in a Windows mutation run, M14b only in a POSIX one; the proof pack names which run killed which. A survivor is a design defect, not a test to add on the side.

**The mutant that separates each adjacent pair of rules (README §2a item 4).**

| Pair | Input on which they differ | Mutant that swaps them |
| --- | --- | --- |
| the explicit `lexists` guard and `os.rename` onto an existing target | an **empty** existing `final` folder (POSIX rename succeeds silently; the guard refuses) | M9 |
| retry on `PermissionError` and propagate on `FileExistsError` | `os.rename` raising `FileExistsError` once | M21 |
| `FileExistsError` branch (compare bytes) and the identity check after a successful link | a link that succeeds but names a different inode | M22 |
| `kind == "link"` unlink and the folder `rmtree` in the sweep | a temp junction or symlink | M18 |
| swallow the unlink failure (success path) and raise it | `os.unlink` raising after a good link | M23 |

### 10.4 Directive D3: architecture tests (`tests/test_atomic_sites.py`, X-B1)

**Scan (RV-TA 3, RV-SEC 7, RV-PAT 2).** `scan(root: Path) -> list[Hit(module, function, verb, lineno)]`: an AST walk of every `*.py` under `root`, recursive, resolving import aliases per module (`import shutil as sh`, `from os import replace`, `from os import replace as r`). A hit is a call whose resolved callee is one of `os.link`, `os.rename`, `os.replace`, `shutil.move`, `shutil.copytree`, `os.open`; or a method call `.rename(...)` or `.hardlink_to(...)` on any receiver; or a method call `.replace(x)` with **exactly one positional argument and no keyword** (a `str` or `bytes` `.replace` takes two; `dataclasses.replace(obj, field=...)` has keywords and resolves to its module). A hit inside module `atomic` is allowed by construction, except that each `os.open` there must pass `O_BINARY` in its flags. A second scan finds every `publish_dir(...)` call and requires its `verify` argument (third positional or `verify=`) to be a `Name` or `Attribute`, never a `Lambda`, `None` or a missing argument. The `os.mkdir`/`Path.mkdir` clause of revision 1 is gone: an AST cannot decide which name is "later published" (RV-SIM 4).

**The allowlist is checked against the tree (README §2a item 5).** The scan was run on the design's base commit `32548ed9` (`src/harness_bench`): **12 call sites in 11 `(module, function, verb)` keys**. After X-B1 and the `_land` change the count is **10 keys** (`workspace._land` calls the helper and drops out; the scan adds nothing outside `atomic`). `ALLOWED` is a mapping key → reason:

| Key | Reason it is not a publish site |
| --- | --- |
| `cli._write_control` · `os.replace` | stage-then-`os.replace` of a control file; a reader sees a complete file or nothing; a leaked `.json.tmp` is read by no one |
| `engine._read_controls` · `Path.replace` (`engine.py:496`) | renames a rejected control file to `.rejected`; a quarantine, not a published name |
| `gateway/store.write_once` · `os.link` | stage-then-link with its own race-loser contract (`store.py:74-92`, see 12) |
| `gateway/store.move_orphan` · `os.rename` (`store.py:161`) | moves an orphaned entry to `orphaned/`; a quarantine of a record, not a publish |
| `grade/_changes.grading_copy` · `shutil.copytree` (`:118`); `grade/correctness.grade` · `shutil.copytree` (`:207`, `:208`); `grade/formal._grading_copy` · `shutil.copytree` (`:280`) | grader scratch copies, deleted after the grade; not a published name. W0 §3 (RF-9) has X-F replace these three with a reparse-safe copy in E1: **X-F deletes the three entries in the same commit**, and the stale-entry test below is what forces it |
| `workspace.task_source` · `shutil.copytree` (`:183`) | copies into the `tmp` build that `_land` then publishes; the publish is `_land` |
| `oslock.acquire`, `oslock.is_held` · `os.open` | the lock file; no content is written, so no `O_BINARY` is needed |

`workspace._land` · `os.replace` is on the list at base (11th key) and **must be removed** by X-B1 in the same change that makes `_land` call `rename_with_retry`; the stale-entry test turns red if it is not.

| Node | Asserts | Red because | Catches |
| --- | --- | --- | --- |
| `test_every_publish_call_site_is_classified` | `{(m, f, v) for hit in scan(SRC)}` minus module `atomic` equals `set(ALLOWED)`; every `os.open` in `atomic` passes `O_BINARY`; every `publish_dir` call passes a named `verify` | on the skeleton: `_land` still calls `os.replace` and is not in the post-change list, and `atomic` has an `os.open` without `O_BINARY` | a new publish site; a stale entry; a no-op `verify` |
| `test_the_scan_flags_every_verb_and_alias_form` | **red fixture**: a temp tree with one file per form: each of the six verbs, `from os import replace`, `from os import replace as r`, `import shutil as sh; sh.move`, `p.rename(q)`, `p.replace(q)`, `p.hardlink_to(q)`; the scan returns one hit per file. Negatives in the same tree return none: `"a".replace("b", "c")`, `b"".replace(b"a", b"b")`, `dataclasses.replace(x, f=1)`. Deleting a verb from the scan turns this red | a scan without alias resolution misses four files | the scanner itself |
| `test_a_stale_or_unlisted_entry_fails` | **red fixture**: with the temp tree and an `ALLOWED` that lacks one hit, the comparison fails naming it; with an `ALLOWED` that holds an entry the tree lacks, it fails naming the entry; with a `publish_dir(final, lambda p: None, ...)` fixture and a `verify=None` fixture, the verify scan fails | the naive comparison ignores stale entries | RV-TA 3 (d), (e) |

## 11. Telemetry (Observability Standard; instrumentation over inference)

Questions an operator asks, each with a named emitting source: *how long does an archive take and where* (`atomic.publish.fill_ms|fsync_ms|verify_ms|rename_ms`), *how big* (`files`, `bytes`), *how often does the OS refuse a rename, and did the backoff run out* (`rename_retries` on `atomic.publish`; `atomic.publish_failed` with `phase=rename`), *did a sweep delete something* (`atomic.temp_swept`, one per deletion), *did a cleanup fail and leave a temp* (`atomic.temp_leaked`), *did a create-only write conflict* (`atomic.create_once`, conflict only). All use the standard `logging` module, loggers `harness_bench.atomic` and `harness_bench.archive`, a structured `extra` dict, as `engine.py:66` does. No PII; paths are run-local. Every timing degrades to "not recorded" (`duration_ms` is `None`) rather than a plausible wrong number.

| Event | Level | Fields | Asserted by |
| --- | --- | --- | --- |
| `atomic.publish` | INFO | `final`, `files`, `bytes`, `fill_ms`, `fsync_ms`, `verify_ms`, `rename_ms`, `rename_retries` | `test_publish_dir_publishes_only_a_verified_complete_folder` (values), `test_a_rename_refused_n_times` (`rename_retries == 2`) |
| `atomic.publish_failed` | ERROR | `final`, `phase` in `fill|fsync|verify|rename`, `error_code` when a `BenchError`, `exc_type` | `test_publish_dir_never_renames_when_fill_or_verify_fails`, `test_a_rename_refused_n_times[always]` |
| `atomic.create_once` | WARNING | `path`, `outcome == "conflict"`, `error_code`. **Logged for a conflict only**: success is the file existing (RV-SIM 6) | `test_create_once_refuses_different_bytes_and_keeps_the_original` |
| `atomic.temp_swept` | WARNING | `path`, `kind` in `file|dir|link` | `test_sweep_temps_unlinks_reparse_points_without_recursing` |
| `atomic.temp_leaked` | WARNING | `path`, `exc_type` | `test_create_once_returns_true_when_the_temp_unlink_fails` |

Dropped in rev 2: `atomic.rename_retry` (per attempt; `rename_retries` on `atomic.publish` carries the count, RV-SIM 6) and `archive.recovered` (moves to X-K1 with `recover_archive`, 5).

**Stable error codes.** Existing: `HB-USR-002` (a complete archive exists), `HB-LED-005` (a copy does not match its rows). Reserved by W0: `HB-LED-007`. **No `HB-LED-009`** (refused by W0 rev 3, S-B1). The registry row for `HB-LED-007` is added by the phase's `errors.py` owner (X-D in E1). No HTTP surface, so no RFC 9457. No spans: there is no trace context in this library layer; the callers' spans (`engine`, X-C) wrap the calls. Every event above has a test in the right-hand column.

## 12. Class, sweep, derive, prevent

### 12.1 Proposed defect class (ready to paste into `docs/lessons/defect-classes.md`; X-B2 appends it with the first red test, as ADR-0015 §5a says "recorded at implementation")

> ### PUB-A: a name published before its content is complete, and an "exists means complete" check that trusts it
> - **Signature:** a producer writes into the final name (a folder or a file), and a consumer or a retry treats `exists()` as "complete". A crash mid-write leaves a partial under the final name; the retry refuses (`HB-USR-002 already exists`) and the cell deadlocks, or a reader consumes the partial.
> - **Why it survives:** the happy path never shows a partial; the crash window is milliseconds, so a test that finishes normally never sees it; `if dest.exists(): raise` reads like a guard. Nearest existing class: CONC-A (check-then-act on a shared destination), but PUB-A needs no concurrency: a single process that dies is enough.
> - **Instances:** `2026-10-03` (council D1 of ADR-0015 §5a, confirmed in the W1-B design) `archive.archive_cell` (`archive.py:56-77`) copies file by file into `attempt-<n>` with no temp; a crash leaves a partial `attempt-<n>` with no `cell.archived`, and a resume fails `HB-USR-002`. `2026-10-03` (the same design, measured) `create_once` written with `os.open` and no `O_BINARY` on Windows turns `\n` into `\r\n` (7 bytes became 10), a sibling shape: bytes under the final name that are not the bytes asked for. Open instance, not fixed here: `workspace.cell_working_copy` clones straight into `dest` and refuses when it exists (`workspace.py:194-196`), so a relaunch of a cell that crashed after `launch_intent` and before its first prompt (ADR-0021 §4 row 2) can meet a partial `ws/`; passed to W1-K.
> - **Sweep (2026-10-03, base `32548ed9`, `src/harness_bench`, the AST scan of 10.4):** 12 call sites in 11 keys of `os.link|os.rename|os.replace|shutil.move|shutil.copytree|os.open|Path.rename|Path.replace`. Instances: `archive.py:57` (the `.exists()` guard before a direct copy, fixed by this design) and `workspace.py:194` (open, W1-K). Not instances, each with its reason in the allowlist: `workspace._land` (already stage-then-rename with a validity check; now calls `rename_with_retry`), `gateway/store.write_once` (stage-then-link, its own race-loser contract), `gateway/store.move_orphan` (quarantine), `cli._write_control` (stage-then-`os.replace`), `engine._read_controls` (quarantine rename), `workspace.task_source` and the three grader `copytree` calls (scratch copies), `oslock` (lock file, no content). Revision 1 missed `move_orphan`, the three `copytree` sites and named `engine.py:496` as an `os` call; the scan fixed all three (RV-TA 3). `.exists()` start guards at `engine.py:371` and `cli.py:157` (`(run_dir / "events").exists()`): the ledger segment is created by `SegmentWriter.create`, not a published folder; not an instance.
> - **Control:** `atomic.create_once` and `atomic.publish_dir` are the only publish path. Tests: the two kill tests (`test_a_kill_mid_copy_leaves_no_final_folder_and_the_redo_succeeds`, `test_a_kill_between_write_and_link_leaves_no_final_file`), observed failing; `tests/test_atomic_sites.py::test_every_publish_call_site_is_classified` fails when a new publish site appears, with its red fixtures. Mutation sets `tests/mutations/atomic.json`, `archive.json`.
> - **Status:** `partially-controlled` until X-B1 and X-B2 merge; `controlled` after, except the open `cell_working_copy` instance.

### 12.2 One more register instance (RIG-D, "a tool's semantics assumed, not checked"; X-B1 appends)
`2026-10-03`, spike E1-S2: an `os.open` descriptor on Windows is in text mode; `os.write` translated `a\nb\r\nc\n` (7 bytes) into 10 bytes on disk. Control: `test_create_once_round_trips_the_bytes_that_text_mode_corrupts` (observed failing without `O_BINARY`, on Windows), and the site scan's rule that every `os.open` in `atomic` passes `O_BINARY`.

## 13. Evidence: spikes run in this slice

**E1-S1** (existing, `docs/notes/spike-e1-ntfs-atomic-publish.md`, quoted where relied on): `os.link` onto an existing name raises `FileExistsError` (winerror 183) and keeps the original bytes; a directory `os.rename` onto an existing folder raises 183; `os.fsync` needs a writable descriptor; a folder cannot be opened for fsync; a killed child leaves only the temp (98 of 400 files).

**E1-S2** (this slice; 2026-10-03; CPython 3.14.6, NTFS `C:`; scripts in the session scratchpad, not kept). Every row Verified by running it:

| Probe | Observed |
| --- | --- |
| a junction (`mklink /J`): `lstat().st_file_attributes & 0x400`; `Path.is_junction()`; `Path.is_symlink()`; `S_ISLNK(st_mode)` | `True`; `True`; `False`; `False`. The guard must test the reparse attribute, not `S_ISLNK` alone |
| `os.unlink` on a junction | succeeds; the target and its files remain |
| `shutil.rmtree` over a folder that contains a junction | removes the junction; the target remains |
| a symlink | not creatable on this host (winerror 1314); the symlink branch is unmeasured here |
| `os.mkdir` onto a pre-created junction | `FileExistsError` 183 |
| `os.open(..., O_CREAT | O_EXCL)` onto a pre-created junction | `PermissionError` (`winerror` None) |
| directory `os.rename` while a file inside is open (same process, then another process) | `PermissionError` 5 both times; succeeds after the handle closes (WIN-A) |
| directory `os.rename` onto an existing **file** | `FileExistsError` 183 |
| `os.link(tmp, final)` with a `.tmp-<pid>-<32 hex>` name; `st_nlink` after unlinking the temp | link created; `st_nlink` 1 |
| `shutil.rmtree` of a folder holding a read-only file | `PermissionError` 5 (`make_writable` is required) |
| `os.open` without `O_BINARY`, `os.write` of `a\nb\r\nc\n`, read back | 10 bytes on disk; with `O_BINARY` 7 bytes, equal |
| `os.fsync` on an `O_WRONLY` descriptor; on a re-opened `O_RDWR` descriptor | both succeed |
| opening a read-only-attribute file `O_RDWR` | `PermissionError` |
| a scratch git repo, `.gitignore` = the three `.gitignore` patterns of W0 §13, `git status --porcelain -uall bench/campaigns bench/discrimination` | lists `real.json` and `campaign.lock.bak` only; the lock, the temp files and a temp folder with a file are absent |

**Still Flagged.** Power loss between the file fsyncs and the rename; macOS and Linux behaviour of the POSIX branch (`_fsync_dir`, rename over an empty folder); symlinks on Windows; PID reuse itself was not provoked (the test patches `os.getpid` and `uuid.uuid4` to reproduce the collision).

## 14. Flagged risks and residual unknowns

| Risk | Disposition |
| --- | --- |
| Power loss or host crash between file fsyncs and rename | accepted, residual; `verify` of the rows would still catch partial content (F25) |
| silent disk corruption of written bytes: `verify`'s re-read is served from the OS cache (RV-PAT 5) | accepted, residual; not claimed as prevented (F20) |
| `cell_working_copy` has the same class (open instance) | passed to W1-K; not this slice |
| a hostile same-user cell process can create `attempt-1` itself and make the archive fail (denial), or write into the visible temp before the rename | accepted: ADR-0012 and ADR-0013 give the cell the operator's rights; the failure is loud (`cell.archive_failed`, workspace kept) and a tamper is detected by `delete_after_verify` (F31) |
| `bench verify` stricter on old archives | characterization run first (6) |
| the torn-file residual (F21) | accepted, ADR-0015 §4 |
| the 1.55 s rename backoff was measured against a test handle only (RV-DS 5) | open until the first pilot's `rename_retries`; trigger in the `assume:` in 7 |
| symlink behaviour on Windows (directory-symlink unlink; `O_EXCL` onto a dangling symlink; sweep of a symlink temp) | open until the one-time run on a host with symlink rights (10.2) |
| `recover_archive` unbuilt until E3 | by ruling; the rule and its tests are specified in 5 for X-K1 |

## 15. Adversarial analysis (STRIDE-lite)

**Trust boundaries.** (B1) the agent-written cell tree (untrusted content, operator rights) into the archive copy; (B2) a same-user process, including a cell, that can create names in the run, campaign and discrimination folders; (B3) the sweep, which deletes by a name pattern with the operator's rights; (B4) committed records (`bench/campaigns`, `bench/discrimination`) that a later hidden check could tamper with (ADR-0016 §8, accepted residual).

| Boundary | Threat | Disposition | Control (named) | Negative test |
| --- | --- | --- | --- | --- |
| B1 | S: none (no identity claim) | n/a | | |
| B1 | T: a link in the cell tree makes the copy read outside | **mitigate** | links are recorded, never followed (`archive._is_link`; existing) | existing `test_links_are_recorded_never_followed` |
| B2 | T: pre-create the predictable temp name as a junction so the copy lands elsewhere (SEC F10) | **mitigate** | 122-bit nonce; exclusive `mkdir`/`O_EXCL`; fill gets an empty folder | `test_publish_dir_refuses_a_squatted_reparse_point`, `test_publish_dir_hands_fill_an_empty_exclusively_created_folder` |
| B2 | T: pre-create a final name to block or poison a publish | **mitigate** (detect, refuse) | explicit `lexists`; `create_once` compares bytes through one descriptor and refuses a non-regular file | `test_publish_dir_refuses_when_final_exists_and_touches_nothing`, `test_create_once_refuses_a_non_regular_existing_path` |
| B2 | T: swap the visible temp name between the write and the link, so `create_once` publishes planted content (RV-SEC 2) | **mitigate** (detect) | fd kept open; `st_dev`/`st_ino` of the fd and of `path` compared; mismatch removes the name this call made and raises. Content-addressed callers' hash check stays the second line (ADR-0016 §8: detected, not prevented) | `test_create_once_refuses_a_file_swapped_in_before_the_link` |
| B2 | T: write into the archive temp after `verify(tmp)` and before the rename (RV-SEC 3) | **detect**, residual accepted (ADR-0012) | rows come from the source; `delete_after_verify` re-verifies strictly and keeps the workspace on `HB-LED-005` | `test_a_file_added_after_verify_is_caught_by_delete_after_verify` |
| B2 | D: fill the disk with temps | **accept** | same rights as the cell (ADR-0012); the sweep and HB-RUN-004 bound the effect | none |
| B3 | E: a temp named like the pattern but a junction to a sensitive folder makes the sweep delete outside | **mitigate** | `lstat` first, unlink never recurse; `make_writable` never chmods through a link (RV-SEC 6) | `test_sweep_temps_unlinks_reparse_points_without_recursing`, `test_make_writable_does_not_chmod_through_a_link` |
| B3 | T: pattern too loose deletes a user's file | **mitigate** | strict `TEMP_RE` with an exact base | `test_stale_temps_lists_only_this_targets_strict_temp_names` |
| B3 | T: a sweep under no lock deletes a live writer's temp (RV-DS 4) | **mitigate** | `sweep_temps` checks `oslock.is_held` before deleting | `test_sweep_temps_removes_temps_only_while_the_lock_is_held` |
| B3 | R: a deletion with no trace | **mitigate** | one `atomic.temp_swept` per deletion; a cleanup that fails is `atomic.temp_leaked` | the two telemetry tests in 11 |
| B4 | T: a committed record changed after the fact | **transfer (named)** | `create_once` never overwrites; the campaign hash chain and `bench campaign verify` detect (ADR-0016 §8, ADR-0018 §11); detected, not prevented | X-C's verify tests |
| B4 | T: the ignore patterns and the temp skip hide a planted temp-named folder or a `campaign.lock` that is a folder or link (RV-SEC 1, 8) | **detect** | `verify` names every temp-named entry in a warning line and `lstat`s the lock; `acquire` refuses a non-regular lock. **Provisional (seam S-B4)**, X-C | X-C's `..._reports_leaked_temps_by_name`, `..._rejects_a_lock_that_is_a_folder_or_link`, `..._acquire_refuses_a_non_regular_lock` |
| all | I: temps expose data | **accept** | a temp holds the bytes the final will hold, in the same folder, under the same permissions | none |

**Privacy (LINDDUN-lite).** No personal data is introduced. The archive copies a cell's working copy and harness home, which ADR-0006 and ADR-0012 already govern; credential files are never copied (existing). This design adds no field, no log of file contents and no egress. Logs carry paths and counts only.

**UI.** No user-facing interface; the surfaces are logs, a ledger event and CLI errors (`bench verify` messages). Not applicable (U19 not triggered).

## 16. E7 surface list (store, model, service, wire, client, UI, compute reader)

| Surface | Change | Owner |
| --- | --- | --- |
| store: `.../archive/<cid>/` | final appears only after verify; `attempt-N.tmp-*` transient residents | X-B2 |
| store: campaign and discrimination folders | `*.tmp-*` transient residents; ignored by git; named, not hidden, by `verify` | X-B1, X-C (gitignore lines, W0 §13), X-E (discrimination sweep) |
| model: `ArchiveResult` | `+ duration_ms` (optional) | X-B2 |
| model: `archive_files`, `cell.archived`, `archive_hash` | **no change** | n/a |
| service: `archive.archive_cell`, `attempt_dirs`, `verify` (strict), `delete_after_verify` (strict via `verify`) | as 6. **`recover_archive` is not built in E1** | X-B2 |
| service: `atomic.rename_with_retry` (public) | `workspace._land` calls it; `workspace.py` loses `RENAME_BACKOFF`; `tests/mutations/workspace.json` entry retargeted. Provisional (seam S-B4) | X-B1 |
| service: `engine._archive` | **no edit in E1** (signature kept); resume (E3) calls `sweep_temps` and builds `recover_archive`; `archive_ms` event field (E2) | X-K1, X-J1 |
| projection/wire: `bench verify` (`views.py:679-689`) | unchanged code, stricter result | X-B2 verifies; X-A1 owns the file |
| compute readers: `report/judges.py:216` | `attempt_dirs` | X-B2 |
| compute readers: `report/pack_improvement.py:783` | `attempt_dirs`; private copy deleted | X-A3 (E3, W0 §4) |
| compute readers: `report/credentials.py:91`, `report/summaries.py:235`, `grade/runner.py:306` | unchanged (direct paths or harmless) | none |
| compute readers: `bench campaign verify`, `bench validate` | skip `is_temp_name` **and name what they skip**; never delete; lock `lstat` | X-C, X-E |
| `errors.py` | `HB-LED-007` row (no `HB-LED-009`) | X-D (E1) |
| `.gitignore` | three lines | X-C (W0 §13) |
| `tests/test_atomic_sites.py` allowlist | X-F deletes the three `copytree` entries when it replaces those sites (E1); any later owner who adds or removes a site edits it | X-B1, then each owner |
| `docs/lessons/defect-classes.md` | `PUB-A` (12.1) and a RIG-D instance (12.2) | X-B2 / X-B1 |
| client types, UI | none | n/a |

## 17. Order of work (so both tracks start red-first from this file)

1. **X-B1**: add the naive-skeleton `atomic.py` (10.1), then `tests/test_atomic.py` and `tests/test_atomic_sites.py` with their red fixtures; observe the tests failing on their stated assertions; then the real implementation; the one hunk in `workspace.py` (`_land` calls `rename_with_retry`); then `tests/mutations/atomic.json`, the retargeted `workspace.json` entry and the kill run (Windows run for M2, M14; POSIX run for M14b); then the soak and the symlink run (proof pack). Append the RIG-D instance.
2. **X-B2** lands commit 0 (extraction of `_copy_hashed`, naive `attempt_dirs`) and its red **tests** at once (they need only the existing code and X-B1's skeleton), and the rework after X-B1's `publish_dir` is green on `main`. First, the `bench verify` characterization run (6). Then the `archive.py` rework, `judges.py`, `tests/mutations/archive.json`, and the `PUB-A` class entry. **No `recover_archive`.**
3. Consumers (E1: X-C, X-D, X-E for `create_once`, `sweep_temps`, `is_temp_name`) start when X-B1 merges. X-K1 (E3) builds the recovery rule in 5.

## 18. Review disposition (rev 2)

Every finding of the five first-round reviews (`docs/design/reviews/eval-review-{ta,ds,sec,pat,sim}-w1b.md`), by reviewer and number. **Applied** = changed in this file; **Moved** = to the named owner; **Declined** = not done, with the reason. The Coordinator's answers (W0 rev 3 change table) are applied first: S-B1 granted except HB-LED-009 (refused); `recover_archive` moves to X-K1 (E3); S-B2 goes to X-C; S-B3 granted.

| Finding | Severity | Disposition | Where |
| --- | --- | --- | --- |
| **RV-TA 1** D1 test patches `archive._copy_hashed`, which does not exist: red by `AttributeError` | major | **Applied.** X-B2 commit 0 extracts `_copy_hashed` and a naive `attempt_dirs` (behaviour-preserving); every red test has a *Red because* assertion; the `recover_archive` test is gone | 6, 10.1, 10.2 |
| **RV-TA 2** the no-fsync test patches `_POSIX`, so a mutant on `_POSIX` survives | blocking | **Applied.** `test_the_real_publish_dir_fsyncs_the_folder_only_on_posix` patches nothing and wraps the real `_fsync_dir`; `test_posix_flag_default_follows_the_platform` pins the default; mutants M14 and M14b name the Windows and the POSIX run | 10.2, 10.3 |
| **RV-TA 3** `test_every_publish_call_site_is_classified` cannot go green (omits `store.py:161`, three `copytree`, names a `Path.replace` outside the scan) and has no red fixture | blocking | **Applied.** The scan is re-derived (verbs, `Path.rename/replace/hardlink_to`, alias resolution); run on `32548ed9`: 12 sites, 11 keys, each classified; three red-fixture tests (all verbs and aliases with negatives; stale and unlisted entry; no-op `verify`); sweep list in 12.1 corrected | 10.4, 12.1 |
| **RV-TA 4** `rename_retries` and `archive.recovered` fields untested; `publish_failed` untested | major | **Applied** for `atomic.publish` (values), `rename_retries == 2`, `publish_failed` (`phase` fill, verify, rename), `create_once` conflict, `temp_leaked`. `archive.recovered` moved with `recover_archive` to X-K1 | 10.2, 11 |
| **RV-TA 5** the retry-success path is Windows-only; nothing kills a retry on `FileExistsError` | major | **Applied.** `test_a_rename_refused_n_times` is portable (`twice then succeeds`, `always`, `FileExistsError`); the real-handle test stays as the D7 sibling | 10.2; M15, M16, M21 |
| **RV-TA 6** S6, F28 and a `create_once` mid-failure have no test | minor | **Applied.** S6 is now the one stop condition in X-K1's rule; F28 is `test_publish_dir_with_a_missing_parent_raises_and_creates_nothing` (F27); the `os.fsync`-raises case is a param of `test_create_once_leaves_no_temp_and_propagates_when_a_step_fails` with mutant M24 | 5, 8, 10.2 |
| **RV-TA 7** import-direction test has no red fixture; `is_temp_name` property has no oracle | minor | **Declined, by RV-SIM 3 and 4.** Both are deleted instead (a cycle fails at import; the fixed names of `test_stale_temps_...` are the oracle) | 10.1, 10.4 |
| **RV-DS 1** an `unlink` failure after a successful link must not raise | minor | **Applied.** `_discard_temp` logs `atomic.temp_leaked` and swallows; returns `True` | 3.3 step 5, F29, M23 |
| **RV-DS 2** "any other `OSError`" is mislabelled HB-LED-009 | minor | **Applied by the Coordinator's ruling** (HB-LED-009 refused): the `OSError` propagates unchanged | 3.3 step 4, F17, 7 |
| **RV-DS 3** the discrimination temps have no sweeper | minor | **Moved to X-E** (W1-E): X-E sweeps `bench/discrimination/<task>/` under its own lock and skips `is_temp_name` in its reader test. Seam: W0 §4 line 218 names X-C for it; S-B4 item 3 asks the Coordinator to correct the line | 4, 3.5 |
| **RV-DS 4** the sweep lock precondition is documented, not enforced | minor | **Applied.** `sweep_temps(target, lock)` checks `oslock.is_held(lock.path)` and raises `ValueError` before deleting | 3.3, F30, M25. Provisional (seam S-B4 item 2) |
| **RV-DS 5** the 1.55 s backoff was measured only against a test handle | minor | **Applied as telemetry plus a trigger**, not as new values: `rename_retries`, `rename_ms` and `publish_failed(phase=rename)` are asserted; the `assume:` names the trigger (`rename_retries >= 4` or any rename failure in the first pilot) | 7, 11, 14 |
| **RV-SEC 1** the ignore patterns and temp skip hide a planted folder or a lock that is a folder or link | major | **Applied as requirements on X-C** (the tests are X-C's; assertions defined here): `verify` `lstat`s `campaign.lock` and names every temp-named entry | 4, 10.2, 15. Provisional (seam S-B4 item 4) |
| **RV-SEC 2** `create_once` links the temp by name after closing the fd: a swap is published | major | **Applied.** fd kept open; `st_dev`/`st_ino` compared after the link; mismatch removes the name and raises; `follow_symlinks=False` where supported | 3.3, 3.4, F28, M22 |
| **RV-SEC 3** a write into the visible archive temp after `verify(tmp)` | minor | **Applied.** Row added to 15 (detect; residual accepted per ADR-0012); test via `delete_after_verify` | 6, 15, F31, A4 |
| **RV-SEC 4** `lstat` then read by name is check-then-use | minor | **Applied.** The read is one descriptor, `O_NOFOLLOW` where it exists, identity compared with the `lstat` | 3.3 step 4, M27 |
| **RV-SEC 5** the symlink branch is unmeasured; the skip can fire on every runner; the nonce is not patched | major | **Applied.** (a) squat tests patch `os.getpid` and `uuid.uuid4`; (b) `test_the_posix_job_does_not_skip_the_symlink_variants` and a CI rule on skips; (c) one recorded run of the three unmeasured behaviours on a host with symlink rights in X-B1's proof pack. (c) is an obligation on X-B1, **not run here** (no symlink right on this host) | 10.2, 14 |
| **RV-SEC 6** `make_writable` follows a link and replaces the mode | minor | **Applied.** lstat first; no chmod through a link; add `S_IWUSR` to the current mode | 3.3, F32, M26. Provisional (seam S-B4 item 5) |
| **RV-SEC 7** `O_BINARY` gaps: killer test is Windows-only; `_copy_hashed` mode unstated; scan skips `os.open` | minor | **Applied.** `"wb"` stated; `os.open` is in the scan (each site passes `O_BINARY` or is allowlisted with a reason); M2 names the Windows run | 6, 10.2, 10.4 |
| **RV-SEC 8** `oslock.acquire` follows a replaced `campaign.lock` | minor | **Applied as a requirement on X-C** with RV-SEC 1: `acquire` refuses a non-regular lock | 4, 15. Provisional (seam S-B4 item 4) |
| **RV-PAT 1** the rename-retry policy exists twice (`atomic.py` and `workspace.py:89-100`) | major | **Applied.** `rename_with_retry` is public and returns the retry count; `workspace._land` calls it and drops `RENAME_BACKOFF`; the WIN-A mutant is retargeted; the old `simplify:` marker is deleted | 3.2, 3.3, 7, 10.3. Provisional (seam S-B4 item 1) |
| **RV-PAT 2** "Template Method" overclaims; `verify` can be a no-op | minor | **Applied.** Renamed "Callbacks (Strategy by function)"; the site scan requires a named `verify` reference at each `publish_dir` call | 7, 10.4 |
| **RV-PAT 3** two import paths for `make_writable` | minor | **Declined in part.** `workspace.py` is repointed. The re-export stays because 5 `src/` sites in four other-owned files (`plan.py` is X-A1's hub) and 9 test lines read `archive.make_writable`, and W0 §4 says "archive re-exports it". `simplify:` marker with its trigger | 7 |
| **RV-PAT 4** `recover_archive` positional tuple return | minor | **Moved to X-K1** as advice (`Recovery` dataclass) | 5 |
| **RV-PAT 5** F20 overclaims what `verify` detects | minor | **Applied.** Reworded to copy-logic and source-read errors; silent disk corruption listed as accepted | 8 F20, 14 |
| **RV-PAT 6** signatures match W0; additions are provisional | nit | **Closed** by W0 rev 3 (S-B1 granted in part). One new request, S-B4 | 3.5 |
| **RV-SIM 1** `recover_archive` has no caller until E3 | major | **Applied by ruling.** The build, event, tests and mutants leave E1; 5 is the specification X-K1 builds to | 5, 6, 8, 16 |
| **RV-SIM 2** S0-S6 are one rule | minor | **Applied.** One rule plus one stop condition | 5 |
| **RV-SIM 3** tests that catch nothing the others do not (two hypothesis tests, M10 pair, M16, M21) | minor | **Applied.** Both hypothesis tests deleted (a fixed input kills M2 and M17); the M10 tests merged into one param test; M16 "unbounded" and M21 "no log" dropped and the log assertion folded into the baseline test. Net: the reviewer asked about 4 fewer nodes; this revision removes 6 nodes and 4 mutants but **adds** the nodes and mutants that RV-TA, RV-SEC and RV-DS required (28 mutants, from 26) | 10.2, 10.3 |
| **RV-SIM 4** the AST scan's `mkdir` clause is undecidable; the import test is redundant | minor | **Applied.** The `mkdir` clause and the import test are deleted. The scan gains the verbs RV-TA and RV-SEC required | 10.4 |
| **RV-SIM 5** HB-LED-009 for a volume the campaign never uses | minor | **Applied by ruling** (refused) | 3.3, 7, 11 |
| **RV-SIM 6** `atomic.rename_retry` and the success INFO are noise | minor | **Applied.** Both dropped; `create_once` logs conflicts only. `atomic.temp_leaked` is added because RV-DS 1 swallows a failure that must stay visible | 11 |
| **RV-SIM 7** `attempt_dirs` is a third helper; S-B3 is a separate request | minor | **Applied.** It is `pack_improvement._attempt_dirs` made strict and moved; S-B3 is a note (granted by W0) | 4 |
| **RV-SIM 8** W0 should record the narrowed `stale_temps` pattern | minor | **Closed** by W0 rev 3 (Leader ruling: the strict regex is the W0 text) | 3.1 |

Counts: TA 7, DS 5, SEC 8, PAT 6, SIM 8 = 34 rows. Declined: RV-TA 7 (superseded by RV-SIM), RV-PAT 3 (in part). Moved: RV-DS 3, RV-PAT 4, and the `recover_archive` half of RV-TA 4.

## Status & next action

| | |
| --- | --- |
| **Completed** | W1-B design rev 1 (data model, `atomic.py` contract, `archive.py` rework, failure-mode, STRIDE, telemetry, test plan, defect class, spike E1-S2) and **rev 2**: all 34 findings of the five lens reviews dispositioned (18); W0 rev 3 merged; `recover_archive` moved to X-K1; the site scan re-derived from the tree (12 sites, 11 keys) with red fixtures; identity check, enforced sweep lock, public `rename_with_retry`, lock and temp reporting for X-C |
| **Remaining** | RV-TA re-review of rev 2 (the hard veto it holds); Coordinator answer to S-B4; X-F to delete the three `copytree` allowlist entries (16) |
| **Best next action** | RV-TA reviews this revision; then X-B1 starts red-first (17) |

## Gate record
<!-- Adversaries: Patterns Expert + Simplifier (mutual check), Test Architect, Security, Distributed Systems (hard vetoes). Author did not self-clear. -->
First-round lines, verbatim:

`GATE W1-B · Test Architect · BLOCK · 7 findings (rv-ta-bd-e1e4, 2026-10-03)`
`GATE W1-B · Distributed Systems · PASS WITH CONDITIONS · 5 findings (rv-ds-e1e4, 2026-10-03)`
`GATE W1-B · Security & Identity · PASS WITH CONDITIONS · 8 findings (rv-sec-w1b-e1e4, 2026-10-03)`
`GATE W1-B · Patterns Expert · PASS WITH CONDITIONS · 6 findings (rv-pat-gb-e1e4, 2026-10-03)`
`GATE W1-B · Simplifier · PASS WITH CONDITIONS · 8 findings (rv-sim-gb-e1e4, 2026-10-03)`

rev 2 pending RV-TA

`GATE design · rev 2 pending RV-TA · RV-SEC, RV-DS (hard vetoes) and RV-PAT, RV-SIM conditions applied per the review disposition (18) · verdict: pending · vetoes→resolution: RV-TA BLOCK (findings 2, 3) addressed in 10.2, 10.4; awaiting RV-TA`

**Author self-check against `design-slice/reference/definition-of-done.md` (rev 2).** Single responsibility (1): met. Data model first with aggregates, invariants, grain, history, derive-don't-store, append-only tests, writers and readers (2): met; the durable-representation ADR (DM13) is not needed because nothing new is persisted. Change-surface list (16): met. Phasing (header, 17): met. Local conventions: `errors.py` codes, `logging` with `extra`, `BenchError`, WIN-A retry now one copy: met. Consumed contracts established and spiked (13): met; POSIX branch and three Windows symlink behaviours Inferred (named in 14). Patterns named, justified, rejected (7): met. Ladder climbed, `simplify:` and `assume:` markers (7): met. Failure modes (8), STRIDE (15), privacy line (15): met. UI: n/a. Directives: D0, D1, D2, D3, D4, D7 enumerated, D5/D6/A* with reasons (10.1): met. **Testability floor (README §2a):** item 1 (red reason per test) in the *Red because* columns; item 2 (red fixture per guard or scan) in 10.4; item 3 (real-wiring tests) in 10.2; item 4 (adjacent-pair mutants) in 10.3; item 5 (allowlist checked against the tree, count 12/11 then 10) in 10.4: met. Telemetry (11): met, every event asserted. Rollups: `docs/security/threat-model.md` and `privacy-review.md` refresh is left to the Coordinator's `docs-graph.py rollup` (not owned here): **unmet, flagged**. Hard vetoes: not self-cleared.

---
**Handoff:** → RV-TA (re-review), then `/implement` (X-B1, X-B2).
