---
id: review-eval-ds-w1b
title: "W1-B crash-atomic publish: Distributed Systems lens review"
type: doc
status: draft
owner: "@timianmalloo"
links:
  - { to: design-eval-seam-contracts, rel: relates-to }
review-by: "2026-10-17"
summary: >-
  Adversary-mode review of docs/design/eval-atomic-publish.md (branch design/eval-atomic-publish, 67e7dc83) by the
  Distributed Systems lens: the four W0 dispositions taken on trust (DS-5, DS-6, DS-7, DS-9), the bounded rename
  retry, and five minor findings.
---

# W1-B crash-atomic publish: Distributed Systems review (rv-ds-e1e4, 2026-10-03)

Read: sections 2, 3.2-3.5, 4, 5, 6, 8 (rows F3, F11, F18, F22), 9, and the named tests in 10.2. Code opened: `src/harness_bench/engine.py:802-815`.

## W0 dispositions checked

| item | what I checked | result |
| --- | --- | --- |
| DS-5 | `publish_dir` step 2: `os.mkdir` of `<name>.tmp-<pid>-<uuid4 hex>`; a collision raises and `fill` always gets an empty, fresh folder. The test pre-creates `final.tmp-<this pid>-<other nonce>` with `old.txt` and patches `getpid` and `uuid4` to collide: raises, nothing written. The pre-rename `verify` enumerates the folder (file-set equality), so an extra file fails before the rename. | holds (Verified in text) |
| DS-6 | `create_once` uses `O_EXCL`, a 32-hex nonce, `TEMP_RE` full-match (a user file named `x.tmp-notes` is never swept), `sweep_temps` unlinks reparse points without recursing, and a deletion that fails raises. `verify` skips names that `is_temp_name` accepts. | holds; see F3 for one gap |
| DS-9 | State table S0-S6 is complete for the order folder, rows, event: S3 (some rows) is covered by "append only absent keys" with the row key from ADR-0015 §5; S6 is the only unrecoverable state and is reachable only by removal after recording. `recover_archive` changes nothing on a mismatch. The test parametrizes "killed after the rename" (a real child) and "some rows recorded". The crash between two row appends is built from synthetic partial rows, not a real kill; acceptable, because the key-set logic is pure. | holds |
| DS-7 | The three `.gitignore` patterns (`bench/campaigns/**/*.tmp-*`, `bench/discrimination/**/*.tmp-*`, `bench/campaigns/*/campaign.lock`) are syntactically valid, and spike E1-S2 measured `git status --porcelain -uall` in a scratch repo: temps and the lock absent, `real.json` and `campaign.lock.bak` listed. The lines are edited by X-C, not here; the test is X-C's. | holds, provisional on seam S-B2 |
| Rename retry (winerror 5) | `RENAME_BACKOFF` = 0.05, 0.1, 0.2, 0.4, 0.8 s then raise (1.55 s total); only `PermissionError` retries, `FileExistsError` and others propagate at once; tests for success after the handle closes and for a bounded failure with the temp left. A persistent refusal reaches the existing `cell.archive_failed` path (`engine.py` try/except, workspace kept), so no new crash path in E1. | holds; see F5 |

## Findings

| # | location | finding | severity | evidence | fix | confidence |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 3.3 `create_once` step 4-5 | After a successful `os.link` the `os.unlink(tmp)` can fail (Windows sharing violation from a scanner). The step 5 `try/finally` text does not say the failure is swallowed, so a call that created the file could raise; the caller (X-C) then sees a failure for a file that exists, though a re-run returns `False`. | minor | step 4 "Success: `os.unlink(tmp)`; return `True`" | After the link has succeeded, an `unlink` failure is logged `atomic.temp_leaked` and ignored; the sweep removes it. Test with `os.unlink` patched to raise. | Inferred |
| 2 | 3.3 step 4 | "Any other `OSError`" becomes HB-LED-009 "volume cannot hard-link". That mislabels `FileNotFoundError` (a sweep removed the temp under a live writer) and a transient `PermissionError`. | minor | step 4 third bullet | Map only the unsupported-link errors (Windows `ERROR_INVALID_FUNCTION`, POSIX `EPERM`/`EXDEV`/`ENOTSUP`) to HB-LED-009; let others propagate unchanged. | Inferred |
| 3 | 4, F11 | Discrimination temps (`bench/discrimination/<task>/`) have no stated sweeper or lock; the table names only the campaign sweep under `campaign.lock`. They are git-ignored, so they accumulate silently. Readers of that folder (X-E `bench validate`) are not in the "temps are invisible" table. | minor | section 4 reader table; F11 | Name X-E as the sweep owner (before a discriminate run, under the task's own lock or none, since `create_once` is safe without a lock) and add `is_temp_name` to X-E's reader test. | Inferred |
| 4 | 3.3 `sweep_temps` | The precondition (caller holds the lock that excludes a live writer) is documented, not enforced. A sweep under the wrong lock deletes a live writer's temp. | minor | "Precondition: the caller holds the lock" | Accept; each caller's test (X-C, X-K1) asserts it holds its lock before sweeping. | Inferred |
| 5 | 3.3 step 7 | The 1.55 s total backoff was measured with a test handle, not a real scanner on a freshly copied tree. A longer hold turns a good copy into `cell.archive_failed` and loses the cell's archive. | minor | `RENAME_BACKOFF`; F18 | Emit the attempt count and wait time in the publish span (it is a telemetry field of `archive.published`); revisit the values from the first pilot's numbers, not by reasoning. | Inferred |

## Seam disagreements

None between this design and W0 rev 2 §4 or §11. HB-LED-009 and `sweep_temps` are open seam requests S-B1 and S-B2; designed to W0 as written meanwhile.

## Residual risk

Power loss between the file fsyncs and the rename stays Flagged (spike E1-S1). The Windows folder-rename durability is recalled, not measured. Hard-link support on non-NTFS volumes fails loudly (HB-LED-009).

GATE W1-B · Distributed Systems · PASS WITH CONDITIONS · 5 findings (rv-ds-e1e4, 2026-10-03)

Conditions: F1 and F2 applied in the design text; F3 to X-E's design (W1-E); F4 and F5 as test and telemetry lines. No blocking finding; the hard veto does not fire.
