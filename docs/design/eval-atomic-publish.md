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
  recovery rule for the crash window between the rename and the ledger rows. Settles the data model (the published
  name is the only completeness fact), the temp-name and sweep contract, the Windows no-directory-fsync branch, the
  strict verify, the reader surfaces a leaked temp would break, and names every red-first test and seeded mutant so
  X-B1 and X-B2 can start from this file alone. Adds three measured Windows facts (text-mode os.write corrupts
  bytes, a junction is unlinkable, a held handle blocks a folder rename).
---

# Design: crash-atomic publish (W1-B)

- **Status:** In review (Gate record pending).
- **Spec / architecture:** `docs/specs/enterprise-evaluation.md` (US-19 archive; the campaign records) · `docs/architecture-evaluation-campaign.md` · W0 `docs/design/eval-seam-contracts.md` §4, §11, §12, §13.
- **Delivery phase / vertical slice:** E1. X-B1 builds `src/harness_bench/atomic.py`; X-B2 builds the `archive.py` rework. X-C (campaign records), X-E (discrimination records) and X-D (identity files) consume `create_once` in E1; X-J1 (turn snapshots) consumes `publish_dir` in E2; X-K1 (resume) consumes `sweep_temps` and `recover_archive` in E3. Nothing here is mocked: the helpers are pure stdlib over a real folder, so every consumer can use them the day X-B1 merges.
- **Author / date:** `w1b-publish-e1e4` (Claude Sonnet 5.5, `claude-sonnet-5-5`) · 2026-10-03.
- **Scope note:** design only. No code. Resume logic is W1-K; snapshot folder paths are W1-J; where this file touches them it states the helper contract only.

## 1. Responsibility

One responsibility: **a name in a published location means its content is complete.** A reader of `attempt-1/`, of `identity/<hash>.json` or of a discrimination record never sees a half-written one, in the face of a process crash, a concurrent writer, a predictable-name attack, or a PID that is reused.

In scope: the `atomic.py` API (W0 §4, with three additions, see 3.5), the rework of `archive.archive_cell` onto it, the recovery rule for the crash window between rename and rows, the strict `verify`, the sweep of leaked temps, the reader surfaces a leaked temp would break, and the defect class. Out of scope: which folder a snapshot lives in (W1-J), when a resume runs the sweep (W1-K), the campaign commands (W1-C), the registry edit of `errors.py` (X-D owns it in E1).

**Done-when map (the plan row, verbatim, and where each item is met).**

| Done-when item | Met in |
| --- | --- |
| Gate PASS incl. Security and Distributed Systems | Gate record (pending reviewers); RV-DS dispositions in 9; RV-SEC F10 in 3.4 and 8 |
| The D1 and D3 red tests named | 10.2 table: **D1** = `test_a_kill_mid_copy_leaves_no_final_folder_and_the_redo_succeeds` (archive, red today); **D3** = `test_a_kill_between_write_and_link_leaves_no_final_file` (create_once). These are the council findings D1 (ADR-0015 §5a) and D3 (ADR-0016 §2a). The Testing Strategy directives D1 (unit + mutation) and D3 (architecture) are also met: 10.3, 10.4 |
| The Windows no-directory-fsync branch stated (spike E1-NTFS) | 3.3 "fsync" and test `test_the_folder_fsync_runs_only_on_posix` |
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
2. **A folder's rows** are derivable from the folder plus the source. This is what recovery uses: `recover_archive` recomputes the rows and compares them with the recorded ones. The rows in the ledger are the committed facts; the recomputed rows are the check.
3. **`archive_hash`** is derived from the rows (`archive.archive_hash`, unchanged), recomputed by `bench verify`.

**Append-only enforcement, tested.** The forbidden update is attempted in `test_publish_dir_refuses_when_final_exists_and_touches_nothing`, `test_create_once_refuses_different_bytes_and_keeps_the_original` and `test_archive_cell_refuses_when_a_complete_archive_exists`. A rebuild test backs the "rows are derivable" claim: `test_recover_archive_handles_every_crash_state` asserts that the rows recomputed after a crash give the same `archive_hash` as a fresh archive of the same source.

**Writers and compute readers of every persisted thing.**

| Persisted thing | Writer | Compute reader |
| --- | --- | --- |
| `<run>/archive/<cid>/attempt-N/` (final folder) | `archive.archive_cell` via `atomic.publish_dir` (X-B2); snapshots via the same call (X-J1) | `archive.verify` (`views.py:686` `bench verify`); `grade/runner.py:306`; `report/summaries.py:235`; `report/judges.py:216`; `report/pack_improvement.py:783`; `report/credentials.py:91` |
| `archive_files` rows, `cell.archived` | `engine._archive` (`engine.py:808-811`), and X-K1's resume | `views.py:679-689` (`archive_hash` recompute, `verify`); `grade/runner.py:237` |
| campaign and discrimination files, identity, prereg and power files | `atomic.create_once` (X-C, X-D, X-E) | `bench campaign verify` (X-C), `bench validate` (X-E) |
| temps (`*.tmp-*`) | the two helpers | `atomic.stale_temps` / `sweep_temps` only; every other reader must not see them (4) |

**Why the model is enough.** The one invariant per aggregate is enforced by the order of operations inside one helper, not by a convention at each call site. That is the point of having exactly two helpers (W0 §4, DM7).

## 3. Contracts

### 3.1 What W0 §4 fixed (revision 2, quoted) and what this design relies on

> `create_once`: "tmp = path.with_name(f"{path.name}.tmp-{os.getpid()}-{uuid4().hex}"), opened O_CREAT|O_EXCL; write, fsync through the write handle, close, os.link(tmp, path), unlink tmp. True = created; False = path existed with equal bytes (no-op). Different bytes: raise BenchError("HB-LED-007", ...) naming the path. Never overwrites."

> `publish_dir(final, fill, verify)`: "If final exists: raise FileExistsError (checked explicitly, on every platform). tmp = final.with_name(...), created by os.mkdir (exclusive: a collision raises); fill(tmp) copies into the empty folder; fsync every file through its write handle; verify(tmp) raises unless the copy matches (it enumerates the folder and compares the file set as well as each file's rows); fsync the folder only when os.name == "posix"; os.rename(tmp, final). On any exception the tmp sibling is left for the sweep."

> `stale_temps(target)`: "The `<target.name>.tmp-*` siblings, files or folders, that a sweep deletes (ADR-0021 §4). Each entry is lstat-ed first: a reparse point (a junction or symlink) is unlinked, never recursed into. Each deletion is logged."

This design adopts all three without change to behaviour, and adds the pieces W0 leaves implicit (3.5).

### 3.2 `src/harness_bench/atomic.py` (X-B1): the final API

```python
TEMP_RE = re.compile(r"^(?P<base>.+)\.tmp-(?P<pid>[0-9]+)-(?P<nonce>[0-9a-f]{32})$")   # the one definition of a temp name
RENAME_BACKOFF = (0.05, 0.1, 0.2, 0.4, 0.8, None)   # WIN-A; same values as workspace.RENAME_BACKOFF
_POSIX = os.name == "posix"                          # module constant so a test can flip the fsync branch

def is_temp_name(name: str) -> bool: ...                                     # TEMP_RE.fullmatch; used by stale_temps, verify, tests
def create_once(path: Path, data: bytes) -> bool: ...                        # W0 §4
def publish_dir(final: Path, fill: Callable[[Path], T], verify: Callable[[Path], None]) -> T: ...   # W0 §4
def stale_temps(target: Path) -> list[Path]: ...                             # pure listing, sorted
def sweep_temps(target: Path) -> list[Path]: ...                             # NEW (seam S-B1): delete what stale_temps lists; return removed
def make_writable(func, path, _exc) -> None: ...                             # moved from archive.py (archive re-imports it: workspace uses archive.make_writable)
```

Imports: stdlib and `harness_bench.errors` only (a fitness test enforces it, 10.4). `atomic.py` knows nothing of ledgers, campaigns, archives or runs.

### 3.3 Behaviour, step by step

**`create_once(path, data) -> bool`.** Precondition: `path.parent` exists (the helper never creates folders; a missing parent raises `FileNotFoundError`).

1. `tmp = path.with_name(f"{path.name}.tmp-{os.getpid()}-{uuid.uuid4().hex}")`.
2. `fd = os.open(tmp, os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o644)`. **`O_BINARY` is mandatory** (measured, spike E1-S2 below: without it `os.write` on Windows turned 7 bytes `a\nb\r\nc\n` into 10 bytes on disk). `O_RDWR` because a read-only descriptor cannot be fsynced (spike E1-S1, Verified).
3. Write all bytes (loop until written), `os.fsync(fd)`, `os.close(fd)`.
4. `os.link(tmp, path)`.
   - Success: `os.unlink(tmp)`; return `True`.
   - `FileExistsError` (winerror 183, spike E1-S1): `lstat(path)`; if it is not a regular file or is a reparse point, unlink `tmp` and raise `BenchError("HB-LED-007", f"{path} exists and is not a regular file")`. Else read it; equal bytes: unlink `tmp`, return `False`; different: unlink `tmp`, raise `BenchError("HB-LED-007", f"{path} exists with different bytes")`. The original is never touched.
   - Any other `OSError` (the volume cannot hard-link; FAT, exFAT, many network shares): unlink `tmp`, raise `BenchError("HB-LED-009", ...)` naming the path, the OS error and "no fallback copy is made". **Never a silent fallback** (W0 §4, RV-DS residual).
5. Every exit except a process crash removes `tmp` (`try/finally`). A crash leaves `tmp` for the sweep; `path` does not exist, because it is only ever created by the link in step 4.

**`publish_dir(final, fill, verify) -> T`.** Preconditions: `final.parent` exists; `fill` never leaves a read-only file (the helper never changes a mode); one writer per `final` at a time (a run lock, `grade.lock` or `campaign.lock` held by the caller).

1. `if os.path.lexists(final): raise FileExistsError(errno.EEXIST, "...", str(final))`. Explicit on every platform: on POSIX `os.rename` onto an existing **empty** folder would succeed silently (RV-TA 12, RV-PAT 6). `lexists`, not `exists`, so a dangling link also counts. `fill` is **not** called in this case and no temp is created.
2. `tmp = final.with_name(f"{final.name}.tmp-{os.getpid()}-{uuid.uuid4().hex}")`; `os.mkdir(tmp)`. A collision (a stale folder, a squatted junction, a file) raises `FileExistsError` and nothing is written into the existing thing (RV-DS 5, RV-SEC 10). `fill` always receives an **empty, freshly created** folder.
3. `result = fill(tmp)`.
4. fsync pass: walk `tmp` with `os.scandir` + `lstat`; for each regular file (reparse points and folders skipped) `fd = os.open(p, os.O_RDWR | O_BINARY)`; `os.fsync(fd)`; `os.close(fd)`. The descriptor is opened for write; a read-only descriptor fails (spike E1-S1). Measured: opening a read-only-attribute file `O_RDWR` raises `PermissionError`, which is why `fill` must not leave one (`shutil.copyfile`, used today, does not copy the attribute).
5. `verify(tmp)` raises unless the copy matches. The caller's verify **enumerates the folder** and compares the file set as well as each file's row (RV-DS 5). `publish_dir` does not look inside.
6. Folder fsync: **only when `_POSIX`**: `_fsync_dir(tmp)`. **On Windows this step is skipped by platform, not attempted.** Quote of the spike (E1-S1): "a directory cannot be opened for fsync at all (PermissionError), so ADR-0015 section 5a's 'fsync the folder' is POSIX-only"; NTFS journals the rename metadata, which is **recalled, not measured** (Inferred). Power loss between the file fsyncs and the rename is not testable by killing a process and stays Flagged (14).
7. `rename_with_retry(tmp, final)` (private): `os.rename`; `PermissionError` is retried through `RENAME_BACKOFF` (WIN-A: a held handle inside the folder refuses a folder rename, **measured here**: winerror 5 with a handle open in the same or another process, success after the handle closes); `FileExistsError` and every other `OSError` propagate at once (a rename onto an existing target is a race with a second writer, not transient). After a successful rename on POSIX, `_fsync_dir(final.parent)` so the rename itself is durable (Inferred: POSIX semantics, not run on this host).
8. Return `result`.

Any exception in steps 3 to 7 leaves `tmp` where it is. **The sweep is the only cleanup path** (one path to test; the partial copy is also the evidence of why a copy failed). The cost is at most one cell's tree of disk per failure until the next sweep; HB-RUN-004 (disk low at launch) bounds the rest.

**`stale_temps(target) -> list[Path]`.** `os.scandir(target.parent)` (an absent parent gives `[]`); keep entries whose `TEMP_RE` match has `base == target.name`; sorted by name; **non-recursive**; lists files, folders and reparse points alike. A name such as `final.tmp-notes`, `other.tmp-1-<hex>` or a nonce of 31 hex digits does not match, so a user file is never swept (the ADR's looser glob `*.tmp-*` would delete them).

**`sweep_temps(target) -> list[Path]`.** Precondition: the caller holds the lock that excludes a live writer to `target` (it cannot tell a crashed writer's temp from a live one, and PID liveness is unreliable under PID reuse). For each path in `stale_temps(target)`, `os.lstat` first:
- a reparse point (`st_file_attributes & FILE_ATTRIBUTE_REPARSE_POINT`, or `S_ISLNK`): `os.unlink(path)`; **never** recurse (a junction to `C:\Users\...` must keep its target; measured: `os.unlink` removes a junction and the target survives, and `shutil.rmtree` over a tree holding a junction removes the junction only);
- a folder: `shutil.rmtree(path, onexc=make_writable)` (a read-only file inside makes plain `rmtree` fail with winerror 5, measured; this is the T9-1 lesson in `workspace._discard`);
- a file: `os.unlink`.
Each deletion logs `atomic.temp_swept` (WARNING) with `path` and `kind` in `file|dir|link`. **A deletion that fails raises** (CLN-A: cleanup that fails silently is a defect class); the caller reports it and does not proceed to redo the copy.

### 3.4 Threat controls inside the helpers (RV-SEC F10)

| Control | Where | Test |
| --- | --- | --- |
| temp name `<name>.tmp-<pid>-<uuid4 hex>`: 122 bits of nonce, not predictable | both helpers | `test_create_once_temp_names_are_unique_and_exclusive`, `test_publish_dir_hands_fill_an_empty_exclusively_created_folder` |
| exclusive create: `O_EXCL` for the file, `os.mkdir` for the folder | both helpers | same tests, with a pre-created name |
| reparse-point guard: a squatted junction at the tmp name makes `os.mkdir` raise (measured: `FileExistsError` 183); `O_EXCL` onto a junction raises (measured: `PermissionError`); the sweep unlinks, never recurses | helpers and sweep | `test_publish_dir_refuses_a_squatted_reparse_point`, `test_sweep_temps_unlinks_reparse_points_without_recursing` |
| the existing final is `lstat`-checked before its bytes are read | `create_once` | `test_create_once_refuses_a_non_regular_existing_path` |

### 3.5 What this design adds to W0 §4 (seam requests)

W0 §4 describes `stale_temps` as the list "that a sweep deletes", and says "each deletion is logged", but names no function that deletes. Without one, X-C (campaign sweep) and X-K1 (resume sweep) each write their own loop, and the reparse-point guard stops being in one place. This design therefore adds, **provisional until the Coordinator answers**:

| Request | Content | Fallback while pending |
| --- | --- | --- |
| **S-B1** `req-01M41DMZX6GYN6NP8PRFXBFZDZ` (to `coord-opus-e1e4`) | W0 §4 gains `sweep_temps(target)`, `is_temp_name(name)` and `make_writable` (moved from `archive.py`); W0 §11 gains `HB-LED-009` (`atomic`: the volume cannot hard-link; no fallback; X-B1 · E1) | X-B1 keeps them private to `atomic.py`; consumers import them anyway; no behaviour in this file changes |
| **S-B2** `req-01M41DMZZXE2KY9XDJJ5QZCX51` (to `coord-opus-e1e4`; S-B3 rides on it) | W0 §13 `.gitignore` row (X-C, E1): add `bench/campaigns/**/*.tmp-*`, `bench/discrimination/**/*.tmp-*` and `bench/campaigns/*/campaign.lock` (RV-DS 7); X-C carries `test_gitignore_covers_every_temp_name_and_the_campaign_lock` (assertions in 10.2) | none needed: X-C's first commit adds the lines |

Sections that rest on S-B1 or S-B2 are marked `provisional (seam S-B1)` or `(seam S-B2)`. Design to W0 as written otherwise.

## 4. Temps are invisible to every reader (RV-DS 6, RV-TA 6)

A temp must never be read as a record. There are three kinds of reader.

| Reader | Hazard from a leaked temp | Control | Test |
| --- | --- | --- | --- |
| `git status --porcelain` over `bench/campaigns` and `bench/discrimination` (ADR-0018 §11(b), run by `bench campaign verify`) | an untracked temp reads as a tampered committed folder, so `verify` refuses with `HB-CMP-003` and no sweep exists | the `.gitignore` lines of S-B2. **Measured** (spike E1-S2, a scratch repo, `-uall`): with those three patterns, `campaign.lock`, `x.json.tmp-12-<32 hex>`, `y.json.tmp-9-<32 hex>` and a temp **folder** with a file inside are all absent from the porcelain output, while `real.json` and `campaign.lock.bak` are listed. Ignored files are not committable by an accidental `git add` either | X-C's gitignore test |
| `bench campaign verify` "every content-addressed file's name equals its hash" (ADR-0018 §11(b)) | a temp's name is not a hash | `verify` skips names for which `atomic.is_temp_name` is true; it never deletes (the sweep owns deletion, under `campaign.lock`) | X-C's verify test: leak a temp, `verify` passes |
| code that globs the archive folder | `report/judges.py:216` does `glob("attempt-*")` and `int(p.name.split("-")[1])`: a leaked `attempt-1.tmp-123-<hex>` raises `ValueError`; `report/pack_improvement.py:783` filters with `rsplit("-", 1)[-1].isdigit()`, which a temp passes when its nonce is all digits (probability about 3e-7, not zero) | one helper, `archive.attempt_dirs(run_dir, cell_id) -> list[Path]`, with `re.fullmatch(r"attempt-(\d+)")`, sorted by number; `judges.py` uses it (X-B2 edits it: it is not a hub file in W0 §13); `pack_improvement.py` is X-A3's hub in E3, so a request goes there (S-B3 below) | `test_attempt_dirs_ignores_a_leaked_temp_sibling`; `test_the_judge_artifact_text_survives_a_leaked_archive_temp` |

`report/credentials.py:91` globs `*/attempt-*/home` and would also scan a temp's home copy for credential values. That is harmless and arguably correct (a leaked copy is a copy), so it is left unchanged and noted. **S-B3** (to X-A3 via the Coordinator, E3): `pack_improvement._attempt_dirs` uses `archive.attempt_dirs`. Until then the nonce risk is 3e-7 per leaked temp and the sweep removes temps first on every resume.

## 5. The crash window between rename and rows (RV-DS 9): the one recovery rule

**Order of operations for one archive entry.** (1) the folder is renamed into place; (2) each `archive_files` row is appended; (3) `cell.archived` is appended; (4) the workspace is deleted (only after the verified event, US-19). Each step is durable before the next begins. A crash leaves exactly one of the states below. Rows live in a different ledger segment than events, so no single append spans (2) and (3).

**The rule (W0 §4, quoted):** "if `final` exists and its rows are absent, recompute the rows from the folder, compare them with the source (still in the archive root or the working copy), then append them. If `final` exists and its rows are present, verify only." This design makes it exact, including the case W0 does not list: **rows partly present** (a crash between two row appends).

| State | On disk | Ledger | Action (the caller; X-K1 in E3) | Helper |
| --- | --- | --- | --- | --- |
| S0 | nothing | nothing | archive | `archive_cell` |
| S1 | `<final>.tmp-*` only | nothing | `sweep_temps`, then archive | `sweep_temps`, `archive_cell` |
| S2 | final | no rows, no event | recompute, compare with source, append all rows, then the event | `recover_archive` |
| S3 | final | some rows, no event | recompute, compare, append **only the rows whose key is absent**, then the event | `recover_archive` |
| S4 | final | all rows, no event | verify the folder against the rows, record the event | `recover_archive` (nothing to append), `verify` |
| S5 | final | all rows and the event | nothing (`bench verify` covers it) | none |
| S6 | no final | rows or event present | not recoverable: the entry was removed after being recorded; `bench verify` reports `HB-LED-005`; stop and tell the operator | `verify` |

The row key is `(run_id, cell_id, archive_attempt, snapshot, path)` (ADR-0015 §5). Appending only absent keys is what makes S2 to S4 one rule and keeps a re-run idempotent.

**`recover_archive(cell_dir, dest_root, attempt, exclude_names, recorded_rows) -> tuple[ArchiveResult, list[dict]]`** (X-B2). Precondition: the final folder exists. It computes:
- `source_rows` from the working copy, hashing the **source** bytes (links from the source, since a link is a row and not a copy);
- `folder_rows` for the file rows, hashing the **folder** bytes, and the folder's exact file set;
and requires `folder_rows == source file rows` and the file sets equal. Then, for each recorded row, requires equality with the recomputed row of the same key. It returns the full `ArchiveResult` (rows, `archive_hash`, bytes) and the list of rows **not yet recorded**. On any difference it raises `BenchError("HB-LED-005", ...)` naming the first differing path, and **changes nothing**: it does not delete the folder, append a row or touch the workspace. Never guess: a mismatch is a defect to look at, not a case to repair (a lingering process could have changed the working copy; the engine kills the job at cell end, ADR-0013, so this is rare and the response is a loud stop, which leaves both copies for the operator).

**Snapshots (W1-J, ADR-0015 §5).** The same function applies with the snapshot's folder and rows. The source of a turn-1 snapshot is the working copy, still turn 1's tree because turn 2 was never sent (ADR-0021 §4 row 5). X-J1 passes the snapshot path; this design does not name it.

**Telemetry of recovery.** `archive.recovered` (WARNING): `state` in `S2|S3|S4`, `rows_recomputed`, `rows_appended`.

## 6. `archive.py` rework (X-B2)

**Public surface after the rework.**

```python
@dataclass
class ArchiveResult:
    folder: Path; rows: list[dict]; archive_hash: str; total_bytes: int
    duration_ms: int | None = None           # NEW: measured publish time; None = not recorded

def archive_cell(cell_dir, dest_root, attempt, exclude_names) -> ArchiveResult   # signature unchanged: engine.py:807 needs no edit
def recover_archive(cell_dir, dest_root, attempt, exclude_names, recorded_rows) -> tuple[ArchiveResult, list[dict]]   # NEW (5)
def verify(folder, rows) -> None            # signature unchanged: views.py:688 needs no edit; now strict (below)
def attempt_dirs(run_dir, cell_id) -> list[Path]    # NEW (4)
def archive_hash(rows) -> str               # unchanged
def delete_after_verify(...), teardown(...)  # unchanged
make_writable                               # re-imported from atomic (workspace.py keeps archive.make_writable)
```

**`archive_cell` after the rework.**
1. If `os.path.lexists(folder)`: `BenchError("HB-USR-002", ...)` exactly as today. The message now says a complete archive exists and names `recover_archive`. The meaning of the existing code is kept: it can now only be reached by a complete folder.
2. A private `_Copy` object holds the rows: `_Copy.fill(tmp)` and `_Copy.verify(tmp)` are the two hooks passed to `publish_dir` (Template Method with hooks, RV-PAT 5). One object, not a closure over a mutable list.
3. `fill(tmp)`: for each entry from `_entries(cell_dir, exclude_names)` (the one definition of "what is archived": sorted, links recorded not followed, credential names skipped, folders created), copy files with `_copy_hashed(src, dst)`: read the **source** in 1 MiB chunks, write each chunk to `dst`, hash **the bytes read**; return `(size, sha256)`. The row's `size` and `sha256` are therefore the source's, taken in the same pass as the copy.
4. `verify(tmp)` is `archive.verify(tmp, rows)`: **the same function `bench verify` calls**, so there is one definition of "this folder matches these rows" (DM7). It now re-reads every copied file and compares size and sha256 with the row (a bad copy fails here, before the rename), and **enumerates the folder** and requires the set of regular files to equal the set of `kind: file` rows (an extra or a missing file fails). Empty folders are copied but are not rows and are not compared (accepted: they carry no content; the archive hash never covered them). A path of a `kind: link` row must have no file in the folder (it would be an extra file).
5. After `publish_dir` returns, set `archive_attempt` on each row, compute `archive_hash`, and return an `ArchiveResult`.

**What changes for existing behaviour (E7, consistency across surfaces).**
- Today `rows` are hashed from the **copy** (`archive.py:77`, `_sha(dest)`), so `verify` compares a copy with a hash of itself: a corrupted copy passes. After the rework the row comes from the source and the copy is checked against it. This closes a gap that is not on the ADR's list; it is why `verify` before the rename is not vacuous. Test `test_a_corrupted_copy_fails_verification_before_the_rename` is red today.
- `bench verify` becomes stricter: an extra file in an old archive folder now yields `HB-LED-005`. `archive_cell` never copied an extra file, so archives written by this code have none (Inferred from reading `archive.py:55-80`). **First task of X-B2, before changing `verify`:** run `bench verify` over every archived run present on the host and the fixtures of `tests/archived_runs.py`, and record the result in its proof pack (a characterization step, not a permanent test).
- `engine._archive` (`engine.py:803-815`) is unchanged in E1. Its `cell.archived` event gains no field in this slice (D6/T7 not triggered). Next step, not scope: X-J1 adds `archive_ms` to `cell.archived` with the snapshot events, from `ArchiveResult.duration_ms`.
- ADR-0021 §4 row 6 ("outcome, no `cell.archived`: a `*.tmp-*` folder is redone; a complete final folder is re-verified and its event recorded") is implemented by the table in 5 and is X-K1's call sequence: `sweep_temps(folder)` first, then `recover_archive` if the folder exists, else `archive_cell`.

## 7. Patterns, named and justified

Climbed the Solution-Selection Ladder: YAGNI, then reuse in the codebase, then stdlib, then native, then installed dependency, then one line.

| Pattern | Where | Why it is the smallest correct idiom |
| --- | --- | --- |
| **Atomic Publish** (write to a sibling temp, then `os.rename`; the standard crash-safe idiom) | `publish_dir` | native rename is the only operation both atomic for a process crash and measured on NTFS (spike E1-S1) |
| **Idempotent Receiver** | `create_once` | equal bytes is a no-op success, different bytes is refused: the same compare-and-refuse rule as the ledger commands (ADR-0016 §2a) |
| **Template Method with hooks** (`fill`, `verify` as callables) | `publish_dir` | RV-PAT 5: the verify step is part of the algorithm, so the caller cannot forget it; a callable pair is lighter than a subclass |
| **Fail-Fast guard** (the explicit `lexists`) | `publish_dir` step 1 | makes "final exists" one behaviour on every platform instead of an OS accident |
| **Janitor / Sweeper** by strict name pattern | `stale_temps`, `sweep_temps` | one cleanup path; the strict regex cannot match a user's file |
| **Reconciliation by derivation** (a rebuildable projection compared with its stored facts) | `recover_archive` | rows are derivable from folder plus source, so no recovery journal is needed |
| **Bounded Retry with Backoff** | `rename_with_retry` | WIN-A, measured here; same values as `workspace.RENAME_BACKOFF` |

**Rejected, with reasons.**
- *A write-ahead journal or a `.complete` marker file*: a second store and a second definition of "complete" (DM7); the name already is the marker.
- *`os.replace` for the folder*: on POSIX it replaces an existing empty folder silently; the explicit `lexists` plus `os.rename` is exact.
- *`tempfile.mkdtemp` / `mkstemp`* (ladder rung 3, stdlib): equally exclusive, and its random suffix could match a stricter regex, so it is a tie. W0 revision 2 already fixed `<name>.tmp-<pid>-<uuid4 hex>` and RV-TA, RV-SEC, RV-DS verified it; changing it costs a seam request for no behaviour gain, and one strict `TEMP_RE` is shared by the sweep, `verify` and the gitignore lines. Kept.
- *Best-effort cleanup of the temp when `fill` raises*: loses the partial copy as evidence and adds a second cleanup path to test. W0 says leave it for the sweep. Kept.
- *A `Published` result class, a retry policy object, a config knob*: YAGNI.
- *Folding `gateway/store.write_once` onto `create_once`*: it has its own race-loser contract (a winner with different bytes is accepted when it recomputes, `store.py:74-92`). Different semantics, not a duplicate; recorded in the sweep (12).
- *Retrying `os.link` on `PermissionError`*: no instance observed; WIN-A was observed for a folder rename only. See the `assume:` below.

**`simplify:` markers (ceiling and upgrade trigger).**
- `simplify:` `atomic.RENAME_BACKOFF` duplicates `workspace.RENAME_BACKOFF` because `workspace` imports `archive` which imports `atomic` (a cycle if `atomic` imported `workspace`). Ceiling: two sites. Upgrade trigger: a third retrying rename, or any edit to either list; then `workspace._land` imports the one in `atomic`.
- `simplify:` `sweep_temps` is made safe by the caller's lock, not by PID liveness. Ceiling: single-writer per target, true for all consumers today (run lock, `grade.lock`, `campaign.lock`). Upgrade trigger: a consumer with concurrent writers to one target.

**`assume:` markers.**
- `assume:` a transient `PermissionError` does not occur on `os.link` of a just-closed temp (an antivirus scan). **Confirm:** a one-time soak of 500 `create_once` calls on the dev host, in X-B1's proof pack (not a ring test). **If false:** `create_once` raises an `OSError` loudly, never a wrong result; add the same bounded retry.
- `assume:` `os.fsync` on a re-opened `O_RDWR` handle flushes data written through the already-closed handle (Windows `FlushFileBuffers` and POSIX `fsync` act on the file, not the handle). **Confirm:** platform documentation; not testable by killing a process. **If false:** durability on power loss is weaker (already Flagged); process-crash atomicity is unaffected.
- `assume:` a `kill` at a random instant never exposes a final name with partial content on NTFS. **Confirm:** spike E1-S1 (one kill of one child at 1 s, 98 of 400 files in the temp, no final) plus the deterministic crash-point tests in 10.2. **If false:** `verify` of the rows still catches it (HB-LED-005).

## 8. Failure-mode analysis

| # | Mode | Category | Disposition | Mechanism and evidence | Test |
| --- | --- | --- | --- | --- | --- |
| F1 | process killed during `fill` | state / partial write | **prevent** (no final name) + **recover** (sweep, redo) | temp only; Verified spike E1-S1 | `test_a_kill_during_fill_or_before_the_rename_leaves_no_final_name` (param `fill`), `test_a_kill_mid_copy_leaves_no_final_folder_and_the_redo_succeeds` |
| F2 | killed after verify, before rename | state | same as F1 | temp only | same test (param `rename`) |
| F3 | killed between the rename and the first row | state / inconsistency across stores | **recover** | S2 in 5 | `test_recover_archive_handles_every_crash_state` (param `killed after the rename`) |
| F4 | killed between two row appends | state | **recover** (append absent keys only) | S3 in 5 | same test (param `some rows recorded`) |
| F5 | killed between the last row and the event | state | **recover** | S4 | same test |
| F6 | killed between write and link in `create_once` | state | **prevent** + recover | no final; temp swept | `test_a_kill_between_write_and_link_leaves_no_final_file` (D3) |
| F7 | stale `<name>.tmp-<pid>` after PID reuse (DS-5) | state | **prevent** | nonce in the name; exclusive create; `fill` gets an empty folder | `test_publish_dir_hands_fill_an_empty_exclusively_created_folder` |
| F8 | squatted junction or symlink at the temp name (SEC F10) | hostile input | **prevent** | `os.mkdir` / `O_EXCL` raise; nothing written through the link | `test_publish_dir_refuses_a_squatted_reparse_point` |
| F9 | sweep follows a junction and deletes outside (SEC F10) | state / hostile | **prevent** | `lstat` first; unlink, never recurse | `test_sweep_temps_unlinks_reparse_points_without_recursing` |
| F10 | sweep deletes a user's file | input | **prevent** | strict `TEMP_RE`, base must equal the target name | `test_stale_temps_lists_only_this_targets_strict_temp_names` |
| F11 | a leaked temp trips `bench campaign verify` (DS-6) | state | **prevent** | gitignore lines (S-B2) + `is_temp_name` skip; sweep under `campaign.lock` | X-C's two tests (10.2) |
| F12 | a leaked temp breaks a reader (`judges.py:216`) | state | **prevent** | `archive.attempt_dirs` | `test_attempt_dirs_ignores_a_leaked_temp_sibling`, `test_the_judge_artifact_text_survives_a_leaked_archive_temp` |
| F13 | `create_once` with different bytes | input | **detect** + refuse | HB-LED-007, original untouched | `test_create_once_refuses_different_bytes_and_keeps_the_original` |
| F14 | `create_once` with equal bytes (a retry) | input / duplicate | **mitigate** (no-op) | returns `False` | `test_create_once_creates_then_noops_on_equal_bytes` |
| F15 | the final path is a folder or a link | input | **detect** + refuse | HB-LED-007 "not a regular file" | `test_create_once_refuses_a_non_regular_existing_path` |
| F16 | `os.write` text-mode translation corrupts bytes (measured) | platform | **prevent** | `O_BINARY` | `test_create_once_round_trips_any_bytes` |
| F17 | volume cannot hard-link | dependency | **detect**, no fallback | HB-LED-009 | `test_create_once_raises_hb_led_009_when_the_volume_cannot_link` |
| F18 | folder rename refused while a handle is open (WIN-A, measured) | dependency / time | **recover** (bounded retry), then raise | `RENAME_BACKOFF` | `test_a_rename_refused_by_an_open_handle_succeeds_once_it_closes`, `test_a_persistent_rename_refusal_raises_after_the_backoff` |
| F19 | `final` appears between the check and the rename (second writer) | concurrency | **detect** + accept | `FileExistsError` from `os.rename` on Windows; one writer by lock; on POSIX an empty-folder race is accepted | covered by the lock precondition; `test_publish_dir_refuses_when_final_exists_and_touches_nothing` for the sequential case |
| F20 | corrupted copy (source read error, disk error) | state | **prevent** | rows from source bytes, copy re-read by `verify` before the rename | `test_a_corrupted_copy_fails_verification_before_the_rename` (red today) |
| F21 | source file changes during the copy (a lingering process) | concurrency | **accept** | the row hashes the bytes actually read, so row and copy agree; ADR-0015 §4 accepts a non-quiescent snapshot; `job_active_processes` shows it. Residual: the archive may contain a torn mix of two versions of one file | none |
| F22 | disk full during `fill` | resources | **detect** | `OSError` ENOSPC propagates; temp left; the engine records `cell.archive_failed` (`engine.py:590-592`) and keeps the workspace | none new: the existing engine path |
| F23 | a sweep fails to delete (locked file) | resources | **detect** | raises; caller stops | `test_sweep_temps_raises_when_a_temp_cannot_be_removed` |
| F24 | rows recomputed differ from the source (S2/S3 with a changed workspace) | state | **detect**, change nothing | HB-LED-005 | `test_recover_archive_refuses_a_folder_that_differs_from_its_source` |
| F25 | a row recorded differs from its recomputed row | state | **detect** | HB-LED-005 | same test (param) |
| F26 | power loss or host crash between file fsyncs and rename | resources / time | **accept**, residual | untestable by killing a process; Flagged in spike E1-S1 | none |
| F27 | cross-volume rename | dependency | **not reachable** | the temp is a sibling of `final`, so the same folder and volume. The spike's "cross-volume archive root" worry applies only to a `fill` that wrote elsewhere; a `fill` writes only into the given folder | none |
| F28 | `publish_dir` called with `final` whose parent is missing | input | **detect** | `os.mkdir` raises `FileNotFoundError`, nothing created | covered by `test_publish_dir_refuses_when_final_exists_and_touches_nothing` setup (no separate test) |

## 9. RV-DS dispositions taken on trust in W0, restated as tests

| W0 disposition (RV-DS) | Tests in this design |
| --- | --- |
| **DS-5**: `publish_dir` stale `.tmp-<pid>` reuse on PID reuse | `test_publish_dir_hands_fill_an_empty_exclusively_created_folder` (a pre-created `final.tmp-<this pid>-<other nonce>` folder with `old.txt` is untouched and absent from the result; with `os.getpid` and `uuid.uuid4` patched to the stale folder's values, `publish_dir` raises `FileExistsError` and writes nothing into it); the strict file-set verify: `test_verify_rejects_an_extra_file_and_a_missing_file` |
| **DS-6**: `create_once` temp names and sweep; a leaked temp trips `verify` | `test_create_once_temp_names_are_unique_and_exclusive`, `test_a_kill_between_write_and_link_leaves_no_final_file` (the leaked temp is listed by `stale_temps` and removed by `sweep_temps`), plus X-C's `test_campaign_verify_ignores_a_leaked_temp_and_the_sweep_removes_it` |
| **DS-9**: crash window between rename and row append, and its recovery rule | section 5 and `test_recover_archive_handles_every_crash_state` (S2, S3, S4 built from a real process killed after the rename, and from partial recorded rows) |
| **DS-7**: `campaign.lock` ignore coverage | S-B2 and X-C's `test_gitignore_covers_every_temp_name_and_the_campaign_lock`; the porcelain behaviour is Verified in spike E1-S2 (below) |

## 10. Test plan

### 10.1 Directive map (Testing Strategy triggers)

| Trigger | Directive | How it is met |
| --- | --- | --- |
| D0 hygiene | always | `ruff` clean; no commented-out code; each handled failure mode above has a test or an explicit "none" with the reason |
| T1 pure logic (`TEMP_RE`, `is_temp_name`, row and set comparison) | D1 + D2 | unit tests; a `hypothesis` property on the temp-name regex; the mutation sets in 10.5 (`hypothesis>=6.100` is installed, `pyproject.toml:18`) |
| T3 new module and dependency direction | D3 | 10.4 |
| T4 filesystem persistence | D4 | every test uses the real filesystem in `tmp_path`; the crash tests use a real child process and `os._exit`; nothing mocks the filesystem. Fakes only for the OS refusal that cannot be provoked on demand (`PermissionError` bound, `os.link` failure) and the POSIX switch |
| T7 event or payload schema | D6 | **not triggered**: no ledger field is added in this slice (6) |
| T8 a fake at a boundary | D7 | the fakes above are one-line monkeypatches of `os.link`, `os.rename`, `atomic._POSIX`; each has a real-handle or real-filesystem sibling test |
| T5, T6, T9 to T14 | D5, A1 to A6 | not applicable: no network, no tool, no model |

**Red-first protocol (so "red" means a failed assertion, not an ImportError).** X-B1's first commit adds `atomic.py` with the naive implementations (`create_once` writes the final path in place; `publish_dir` calls `fill(final)`), the tests below are observed failing on their assertions, and the second commit makes them green. X-B2's first commit adds the tests that are red against today's `archive.py`: `test_a_kill_mid_copy...` (final folder exists after the kill and the redo raises `HB-USR-002`), `test_a_corrupted_copy_fails_verification_before_the_rename`, `test_verify_rejects_an_extra_file_and_a_missing_file`, `test_attempt_dirs_ignores_a_leaked_temp_sibling` and `test_the_judge_artifact_text_survives_a_leaked_archive_temp`. Observed-failing is the control (CI6).

### 10.2 Tests by node id (each names the failure it alone catches)

`tests/test_atomic.py` (X-B1; real filesystem):

| Node | Asserts | Catches (mutant) |
| --- | --- | --- |
| `test_create_once_round_trips_any_bytes` (hypothesis, `binary()` plus fixed `b"a\nb\r\nc\n"`) | the file on disk equals the input byte for byte | M2 no `O_BINARY` (measured: 7 bytes became 10) |
| `test_create_once_creates_then_noops_on_equal_bytes` | first call `True`, second `False`, file unchanged, no temp left | M3 returns `True` on exists |
| `test_create_once_refuses_different_bytes_and_keeps_the_original` | `BenchError.code == "HB-LED-007"`, message names the path, original bytes intact, no temp left | M4 overwrite via `os.replace` |
| `test_a_kill_between_write_and_link_leaves_no_final_file` **(D3)** | a child patches `os.link` to `os._exit(3)`; afterward `path` is absent, `stale_temps(path)` lists exactly one **file**, `create_once` then succeeds, `sweep_temps(path)` removes the old temp and returns it | M1 writes the final path in place |
| `test_create_once_temp_names_are_unique_and_exclusive` | two calls use different temp names (spy on `os.open`); with `os.getpid` and `uuid.uuid4` patched, a pre-created temp of that name makes the call raise `FileExistsError` and leaves it unchanged | M5 fixed temp name; M6 no `O_EXCL` |
| `test_create_once_refuses_a_non_regular_existing_path` | a folder at `path` gives `HB-LED-007`, no temp left | M7 reads through the link or folder |
| `test_create_once_raises_hb_led_009_when_the_volume_cannot_link` | `os.link` patched to raise `OSError(1, ...)`: `HB-LED-009`, no final, no temp, no copy fallback | M8 falls back to `os.replace` |
| `test_publish_dir_publishes_only_a_verified_complete_folder` | returns `fill`'s result; `final` has exactly the files; no temp remains | baseline |
| `test_publish_dir_refuses_when_final_exists_and_touches_nothing` | param: final a populated folder, an **empty** folder, a file: `FileExistsError`; `fill` never called; no temp created; contents unchanged | M9 no `lexists` check (the empty-folder case exposes it on POSIX; on Windows `fill` not called does) |
| `test_publish_dir_never_renames_when_verify_fails` (RV-PAT 5) | `verify` raises: exception propagates, `final` absent, the temp is left | M10 verify skipped |
| `test_publish_dir_never_renames_when_fill_raises` | same, with `fill` raising | M10 |
| `test_publish_dir_hands_fill_an_empty_exclusively_created_folder` (DS-5, SEC F10) | stale temp with `old.txt` untouched; `fill` sees an empty folder; collision path raises and writes nothing | M11 `exist_ok=True` / reuse |
| `test_publish_dir_refuses_a_squatted_reparse_point` | Windows: a junction (`mklink /J`) at the predicted temp name makes `publish_dir` raise `FileExistsError`; the junction target's contents are unchanged. POSIX: a symlink variant. Skipped with a stated reason where the link cannot be made (this host: symlinks need a privilege, winerror 1314) | M11 |
| `test_a_kill_during_fill_or_before_the_rename_leaves_no_final_name` (param `fill`, `rename`) | a child exits hard inside `fill` (after three files) or inside a patched `os.rename`; `final` absent; exactly one temp folder; the next `publish_dir` succeeds; the old temp stays until `sweep_temps` removes it | M12 `fill(final)` directly |
| `test_every_file_is_fsynced_through_a_write_handle_before_the_rename` | recorder over `os.open` and `os.fsync`: every fsynced descriptor was opened with write access; the count equals the file count; all fsyncs precede `os.rename` and follow `fill` | M13 no fsync / read-only fsync |
| `test_the_folder_fsync_runs_only_on_posix` | `_POSIX=False`: `_fsync_dir` never called (the Windows branch, spike E1-NTFS). `_POSIX=True` with a recorder: called for the temp before the rename and for the parent after | M14 fsync always |
| `test_a_rename_refused_by_an_open_handle_succeeds_once_it_closes` | `fill` leaves a handle open and a timer closes it after 0.3 s: the publish succeeds (real WIN-A behaviour; Windows only, skipped elsewhere with reason) | M15 no retry |
| `test_a_persistent_rename_refusal_raises_after_the_backoff` | `os.rename` patched to always raise `PermissionError`, `time.sleep` patched: raises after `len(RENAME_BACKOFF)` attempts; the temp is left | M16 unbounded retry |
| `test_stale_temps_lists_only_this_targets_strict_temp_names` | lists the file and folder temps of `final`; excludes `final.tmp-notes`, `other.tmp-1-<hex>`, a 31-digit nonce, `final` itself; `is_temp_name` property over random names | M17 loose glob |
| `test_sweep_temps_unlinks_reparse_points_without_recursing` (SEC F10) | a temp junction to a folder with a sentinel file: the junction is gone, the sentinel remains; a temp folder holding a read-only file is removed; one `atomic.temp_swept` record per deletion (caplog) | M18 `rmtree` through the link; M19 no `make_writable` |
| `test_sweep_temps_raises_when_a_temp_cannot_be_removed` | `shutil.rmtree` patched to raise: the error propagates (CLN-A) | M20 swallowed error |
| `test_publish_logs_one_record_with_phase_timings` | caplog: exactly one `atomic.publish` record with integer `fill_ms`, `fsync_ms`, `verify_ms`, `rename_ms`, `files`, `bytes`, `rename_retries` | M21 no log |

`tests/test_archive.py` (X-B2; the existing four tests stay unchanged):

| Node | Asserts | Catches |
| --- | --- | --- |
| `test_a_kill_mid_copy_leaves_no_final_folder_and_the_redo_succeeds` **(D1)** | a child runs `archive_cell` with `archive._copy_hashed` patched to `os._exit` after two files; afterward `attempt-1` is absent and one `attempt-1.tmp-*` exists with a partial tree; `sweep_temps` then `archive_cell` produce a complete archive whose `verify` passes. **Red today**: the partial `attempt-1` exists and the redo raises `HB-USR-002` | direct-to-final copy (archive.py:57-77) |
| `test_a_corrupted_copy_fails_verification_before_the_rename` | `_copy_hashed` patched to flip one byte in the written copy: `HB-LED-005`, no final, the temp left. **Red today** (rows are hashed from the copy) | M22 rows hashed from the copy |
| `test_verify_rejects_an_extra_file_and_a_missing_file` | an extra file, a missing file and a file at a link row's path each raise `HB-LED-005`; an extra empty folder does not | M23 row-only verify |
| `test_archive_cell_refuses_when_a_complete_archive_exists` | `HB-USR-002`; the existing bytes unchanged | forbidden update |
| `test_recover_archive_handles_every_crash_state` (param: `killed after the rename` built from a real child that exits after `archive_cell` and before any row; `some rows recorded`; `all rows recorded`) | returned rows to append equal exactly the unrecorded ones; the full result's `archive_hash` equals a fresh archive of the same source (the rebuild test) | M24 appends all rows (duplicates); M25 skips the source comparison |
| `test_recover_archive_refuses_a_folder_that_differs_from_its_source` (param: workspace file changed; a recorded row differs) | `HB-LED-005` naming the path; folder, workspace and recorded rows untouched | M25 |
| `test_attempt_dirs_ignores_a_leaked_temp_sibling` | `attempt-1`, `attempt-2` and a leaked `attempt-1.tmp-<pid>-<digits-only nonce>`: returns the first two in numeric order | M26 digit-suffix filter |
| `test_bench_verify_passes_a_run_archived_by_the_atomic_path` (in `tests/test_views.py`) | an archive from the new `archive_cell`, its rows and event: `views` finds no finding (surface consistency: writer, then the compute reader) | writer and reader drift |

`tests/test_report_judges.py` (X-B2 edits `judges.py`): `test_the_judge_artifact_text_survives_a_leaked_archive_temp` (a leaked temp beside `attempt-1` does not raise `ValueError`; the text comes from `attempt-1`). **Red today.**

X-C's file (assertions defined here; seam S-B2): `test_gitignore_covers_every_temp_name_and_the_campaign_lock` runs `git check-ignore` on a temp **file**, a temp **folder** and its inner file under `bench/campaigns/<id>/` and `bench/discrimination/<task>/`, and on `bench/campaigns/<id>/campaign.lock`, and asserts all are ignored while `x.json` and `campaign.lock.bak` are not. `test_campaign_verify_ignores_a_leaked_temp_and_the_sweep_removes_it`: leak a temp, `verify` passes, the campaign sweep under `campaign.lock` removes it.

One-time proofs outside the rings (proof pack only): the 500-call `create_once` soak (the `assume:` in 7); the `bench verify` characterization run over existing archives (6); the symlink variants on macOS in the existing `macos-latest` CI job (the Windows host cannot make a symlink).

### 10.3 Directive D1: mutation sets

`tests/mutations/atomic.json` (new, X-B1) holds M1 to M21 above; `tests/mutations/archive.json` (existing) gains M22 to M26. Every mutant names the test that must kill it, and `tests/test_mutate_check.py::test_every_named_test_in_the_mutation_sets_exists` (MUT-B) keeps the ids honest. A survivor is a design defect, not a test to add on the side.

### 10.4 Directive D3: architecture tests (`tests/test_atomic_sites.py`, X-B1)

- `test_every_publish_call_site_is_classified`: an AST scan of `src/harness_bench` finds every call to `os.link`, `os.rename`, `os.replace`, `shutil.move`, `shutil.copytree` and every `os.mkdir`/`Path.mkdir` that creates a name later published, and compares the set with an allowlist keyed by `(module, function)` and a reason: `atomic.create_once`, `atomic.publish_dir` (the two helpers); `workspace._land` (content-addressed build, WIN-A retry, `valid(dest)`); `gateway/store.write_once` (race-loser contract, see 12); `cli._write_control` (a reader sees a complete `os.replace`d file or nothing; a leaked `.json.tmp` is read by no one); `engine` rejected-file rename. A new site fails the test until someone classifies it against class `PUB-A`. This is the sweep turned into a gate.
- `test_atomic_imports_only_stdlib_and_errors`: dependency direction (no cycle with `archive`, `workspace`, `ledger`).

## 11. Telemetry (Observability Standard; instrumentation over inference)

Questions an operator asks, each with a named emitting source: *how long does an archive take and where* (`atomic.publish.fill_ms|fsync_ms|verify_ms|rename_ms`), *how big* (`files`, `bytes`), *how often does the OS refuse a rename* (`rename_retries`, and `atomic.rename_retry` per attempt), *did a sweep delete something* (`atomic.temp_swept`, one per deletion), *did a recovery run and from which state* (`archive.recovered`), *did a create-only write conflict* (`atomic.create_once` outcome `conflict` with `HB-LED-007`). All use the standard `logging` module, loggers `harness_bench.atomic` and `harness_bench.archive`, a structured `extra` dict, as `engine.py:66` does. No PII; paths are run-local. Every timing degrades to "not recorded" (`duration_ms` is `None`) rather than a plausible wrong number.

| Event | Level | Fields |
| --- | --- | --- |
| `atomic.publish` | INFO | `final`, `files`, `bytes`, `fill_ms`, `fsync_ms`, `verify_ms`, `rename_ms`, `rename_retries` |
| `atomic.publish_failed` | ERROR | `final`, `phase` in `fill|fsync|verify|rename`, `error_code` when a `BenchError`, `exc_type` |
| `atomic.rename_retry` | WARNING | `final`, `attempt`, `winerror` |
| `atomic.create_once` | INFO | `path`, `outcome` in `created|noop|conflict`, `duration_ms` |
| `atomic.temp_swept` | WARNING | `path`, `kind` in `file|dir|link` |
| `archive.recovered` | WARNING | `state` in `S2|S3|S4`, `rows_recomputed`, `rows_appended` |

**Stable error codes.** Existing: `HB-USR-002` (a complete archive exists), `HB-LED-005` (a copy or a recovery does not match its rows). Reserved by W0: `HB-LED-007`. Proposed: `HB-LED-009` (the volume cannot hard-link; seam S-B1). Rows in the registry are added by the phase's `errors.py` owner (X-D in E1). No HTTP surface, so no RFC 9457. No spans: there is no trace context in this library layer; the callers' spans (`engine`, X-C) wrap the calls. Load-bearing telemetry has a test: `test_publish_logs_one_record_with_phase_timings`, and the sweep's records are asserted in `test_sweep_temps_unlinks_reparse_points_without_recursing`.

## 12. Class, sweep, derive, prevent

### 12.1 Proposed defect class (ready to paste into `docs/lessons/defect-classes.md`; X-B2 appends it with the first red test, as ADR-0015 §5a says "recorded at implementation")

> ### PUB-A: a name published before its content is complete, and an "exists means complete" check that trusts it
> - **Signature:** a producer writes into the final name (a folder or a file), and a consumer or a retry treats `exists()` as "complete". A crash mid-write leaves a partial under the final name; the retry refuses (`HB-USR-002 already exists`) and the cell deadlocks, or a reader consumes the partial.
> - **Why it survives:** the happy path never shows a partial; the crash window is milliseconds, so a test that finishes normally never sees it; `if dest.exists(): raise` reads like a guard. Nearest existing class: CONC-A (check-then-act on a shared destination), but PUB-A needs no concurrency: a single process that dies is enough.
> - **Instances:** `2026-10-03` (council D1 of ADR-0015 §5a, confirmed in the W1-B design) `archive.archive_cell` (`archive.py:56-77`) copies file by file into `attempt-<n>` with no temp; a crash leaves a partial `attempt-<n>` with no `cell.archived`, and a resume fails `HB-USR-002`. `2026-10-03` (the same design, measured) `create_once` written with `os.open` and no `O_BINARY` on Windows turns `\n` into `\r\n` (7 bytes became 10), a sibling shape: bytes under the final name that are not the bytes asked for. Open instance, not fixed here: `workspace.cell_working_copy` clones straight into `dest` and refuses when it exists (`workspace.py:194-196`), so a relaunch of a cell that crashed after `launch_intent` and before its first prompt (ADR-0021 §4 row 2) can meet a partial `ws/`; passed to W1-K.
> - **Sweep (2026-10-03, `src/`):** `os.link|os.rename|os.replace|shutil.move|.exists()` sites: `archive.py:57` (instance, fixed by this design), `workspace.py:194` (instance, open, W1-K), `workspace._land` (already stage-then-rename, with a validity check; fine), `gateway/store.py:74-92` (stage-then-link, its own race-loser contract; fine), `cli.py:204` `_write_control` (stage-then-`os.replace`; a reader sees a complete file or nothing; fine), `engine.py:371` and `cli.py:157` (`(run_dir / "events").exists()` start guards: the ledger segment is created by `SegmentWriter.create`, not a published folder; not an instance).
> - **Control:** `atomic.create_once` and `atomic.publish_dir` are the only publish path. Tests: the two kill tests (`test_a_kill_mid_copy_leaves_no_final_folder_and_the_redo_succeeds`, `test_a_kill_between_write_and_link_leaves_no_final_file`), observed failing on the naive implementation; `tests/test_atomic_sites.py::test_every_publish_call_site_is_classified` fails when a new publish site appears. Mutation sets `tests/mutations/atomic.json`, `archive.json`.
> - **Status:** `partially-controlled` until X-B1 and X-B2 merge; `controlled` after, except the open `cell_working_copy` instance.

### 12.2 One more register instance (RIG-D, "a tool's semantics assumed, not checked"; X-B1 appends)
`2026-10-03`, spike E1-S2: an `os.open` descriptor on Windows is in text mode; `os.write` translated `a\nb\r\nc\n` (7 bytes) into 10 bytes on disk. Control: `test_create_once_round_trips_any_bytes` (observed failing without `O_BINARY`).

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
| a scratch git repo, `.gitignore` = the three S-B2 patterns, `git status --porcelain -uall bench/campaigns bench/discrimination` | lists `real.json` and `campaign.lock.bak` only; the lock, the temp files and a temp folder with a file are absent |

**Still Flagged.** Power loss between the file fsyncs and the rename; macOS and Linux behaviour of the POSIX branch (`_fsync_dir`, rename over an empty folder); symlinks on Windows; PID reuse itself was not provoked (the test patches `os.getpid` and `uuid.uuid4` to reproduce the collision).

## 14. Flagged risks and residual unknowns

| Risk | Disposition |
| --- | --- |
| Power loss or host crash between file fsyncs and rename | accepted, residual; `verify` of the rows would still catch partial content (F26) |
| `cell_working_copy` has the same class (open instance) | passed to W1-K; not this slice |
| a hostile same-user cell process can create `attempt-1` itself and make the archive fail (denial) | accepted: ADR-0012 and ADR-0013 give the cell the operator's rights; the failure is loud (`cell.archive_failed`, workspace kept) |
| `bench verify` stricter on old archives | characterization run first (6) |
| the torn-file residual (F21) | accepted, ADR-0015 §4 |
| two retrying-rename constants (`simplify:` in 7) | tracked marker |

## 15. Adversarial analysis (STRIDE-lite)

**Trust boundaries.** (B1) the agent-written cell tree (untrusted content, operator rights) into the archive copy; (B2) a same-user process, including a cell, that can create names in the run, campaign and discrimination folders; (B3) the sweep, which deletes by a name pattern with the operator's rights; (B4) committed records (`bench/campaigns`, `bench/discrimination`) that a later hidden check could tamper with (ADR-0016 §8, accepted residual).

| Boundary | Threat | Disposition | Control (named) | Negative test |
| --- | --- | --- | --- | --- |
| B1 | S: none (no identity claim) | n/a | | |
| B1 | T: a link in the cell tree makes the copy read outside | **mitigate** | links are recorded, never followed (`archive._is_link`; existing) | existing `test_links_are_recorded_never_followed` |
| B2 | T: pre-create the predictable temp name as a junction so the copy lands elsewhere (SEC F10) | **mitigate** | 122-bit nonce; exclusive `mkdir`/`O_EXCL`; fill gets an empty folder | `test_publish_dir_refuses_a_squatted_reparse_point`, `test_publish_dir_hands_fill_an_empty_exclusively_created_folder` |
| B2 | T: pre-create a final name to block or poison a publish | **mitigate** (detect, refuse) | explicit `lexists`; `create_once` compares bytes and refuses a non-regular file | `test_publish_dir_refuses_when_final_exists_and_touches_nothing`, `test_create_once_refuses_a_non_regular_existing_path` |
| B2 | D: fill the disk with temps | **accept** | same rights as the cell (ADR-0012); the sweep and HB-RUN-004 bound the effect | none |
| B3 | E: a temp named like the pattern but a junction to a sensitive folder makes the sweep delete outside | **mitigate** | `lstat` first, unlink never recurse | `test_sweep_temps_unlinks_reparse_points_without_recursing` |
| B3 | T: pattern too loose deletes a user's file | **mitigate** | strict `TEMP_RE` with an exact base | `test_stale_temps_lists_only_this_targets_strict_temp_names` |
| B3 | R: a deletion with no trace | **mitigate** | one `atomic.temp_swept` per deletion | same sweep test (caplog) |
| B4 | T: a committed record changed after the fact | **transfer (named)** | `create_once` never overwrites; the campaign hash chain and `bench campaign verify` detect (ADR-0016 §8, ADR-0018 §11); detected, not prevented | X-C's verify tests |
| all | I: temps expose data | **accept** | a temp holds the bytes the final will hold, in the same folder, under the same permissions | none |

**Privacy (LINDDUN-lite).** No personal data is introduced. The archive copies a cell's working copy and harness home, which ADR-0006 and ADR-0012 already govern; credential files are never copied (existing). This design adds no field, no log of file contents and no egress. Logs carry paths and counts only.

**UI.** No user-facing interface; the surfaces are logs, a ledger event and CLI errors (`bench verify` messages). Not applicable (U19 not triggered).

## 16. E7 surface list (store, model, service, wire, client, UI, compute reader)

| Surface | Change | Owner |
| --- | --- | --- |
| store: `.../archive/<cid>/` | final appears only after verify; `attempt-N.tmp-*` transient residents | X-B2 |
| store: campaign and discrimination folders | `*.tmp-*` transient residents; ignored by git | X-B1, X-C (S-B2) |
| model: `ArchiveResult` | `+ duration_ms` (optional) | X-B2 |
| model: `archive_files`, `cell.archived`, `archive_hash` | **no change** | n/a |
| service: `archive.archive_cell`, `recover_archive`, `attempt_dirs`, `verify` (strict) | as 6 | X-B2 |
| service: `engine._archive` | **no edit in E1** (signature kept); resume calls `sweep_temps` + `recover_archive` (E3); `archive_ms` event field (E2) | X-K1, X-J1 |
| projection/wire: `bench verify` (`views.py:679-689`) | unchanged code, stricter result | X-B2 verifies; X-A1 owns the file |
| compute readers: `report/judges.py:216` | `attempt_dirs` | X-B2 |
| compute readers: `report/pack_improvement.py:783` | `attempt_dirs` | S-B3 to X-A3 (E3) |
| compute readers: `report/credentials.py:91`, `report/summaries.py:235`, `grade/runner.py:306` | unchanged (direct paths or harmless) | none |
| compute readers: `bench campaign verify`, `bench validate` | skip `is_temp_name`; never delete | X-C, X-E |
| `errors.py` | `HB-LED-007`, `HB-LED-009` rows | X-D (E1) |
| `.gitignore` | three lines | X-C (S-B2) |
| `docs/lessons/defect-classes.md` | `PUB-A` (12.1) and a RIG-D instance (12.2) | X-B2 / X-B1 |
| client types, UI | none | n/a |

## 17. Order of work (so both tracks start red-first from this file)

1. **X-B1**: add the naive `atomic.py`, then `tests/test_atomic.py` and `tests/test_atomic_sites.py`; observe the tests failing; then the real implementation; then `tests/mutations/atomic.json` and its kill run; then the soak (proof pack). Append the RIG-D instance.
2. **X-B2** starts its **tests** at once (they are red against today's `archive.py` and need only the existing code), and its implementation after X-B1's `publish_dir` is green on `main`. First, the `bench verify` characterization run (6). Then the `archive.py` rework, `judges.py`, `tests/mutations/archive.json`, and the `PUB-A` class entry.
3. Consumers (E1: X-C, X-D, X-E for `create_once`, `sweep_temps`, `is_temp_name`) start when X-B1 merges.

## Status & next action

| | |
| --- | --- |
| **Completed** | W1-B design: data model, `atomic.py` contract and sweep, `archive.py` rework, the recovery rule and state table, reader surfaces, failure-mode, STRIDE and telemetry, test plan by node id with seeded mutants, defect class text, spike E1-S2 |
| **Remaining** | the five lens reviews (gate); the author's follow-up applying findings; Coordinator answers to S-B1 and S-B2; S-B3 to X-A3 (E3) |
| **Best next action** | RV-TA, RV-SEC, RV-DS, RV-PAT, RV-SIM review this file; then X-B1 starts red-first (17) |

## Gate record
<!-- Adversaries: Patterns Expert + Simplifier (mutual check), Test Architect, Security, Distributed Systems (hard vetoes). Author did not self-clear. -->
`GATE design · pending · RV-PAT, RV-SIM (soft veto), RV-TA (hard veto), RV-SEC (hard veto), RV-DS (hard veto) · criteria met: author self-check against definition-of-done.md (below) · verdict: pending · vetoes→resolution: none recorded yet`

**Author self-check against `design-slice/reference/definition-of-done.md`.** Single responsibility (1): met. Data model first with aggregates, invariants, grain, history, derive-don't-store, append-only tests, writers and readers (2): met; the durable-representation ADR (DM13) is not needed because nothing new is persisted (stated in 2). Change-surface list (16): met. Phasing (header, 17): met. Local conventions: `errors.py` codes, `logging` with `extra`, `BenchError`, WIN-A retry reused: met. Consumed contracts established and spiked (13): met; POSIX branch Inferred. Patterns named, justified, rejected (7): met. Ladder climbed, `simplify:` and `assume:` markers (7): met. Failure modes (8), STRIDE (15), privacy line (15): met. UI: n/a. Directives: D0, D1, D2, D3, D4, D7 enumerated, D5/D6/A* with reasons (10.1): met. Telemetry (11): met. Rollups: `docs/security/threat-model.md` and `privacy-review.md` refresh is left to the Coordinator's `docs-graph.py rollup` (not owned here): **unmet, flagged**. Hard vetoes: not self-cleared.

---
**Handoff:** → RV-TA, RV-SEC, RV-DS, RV-PAT, RV-SIM, then `/implement` (X-B1, X-B2).
