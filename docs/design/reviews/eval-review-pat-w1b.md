---
id: review-eval-pat-w1b
title: "Patterns Expert review of W1-B, crash-atomic publish (Adversary Mode)"
type: doc
status: draft
owner: "@timianmalloo"
tags: [review, patterns-expert, evaluation-campaign, wave-1, w1-b]
links:
  - { to: design-eval-seam-contracts, rel: relates-to }
review-by: "2026-10-17"
summary: >-
  RV-PAT review of design/eval-atomic-publish (67e7dc83) against W0 rev 2 and R-87..R-93. W0 finding 5 (a verify step
  before the rename) landed in full. One duplicated constant and retry loop against workspace.py, and minor idiom
  points.
---

# RV-PAT review: W1-B `docs/design/eval-atomic-publish.md` against W0 rev 2

Read on `design/eval-atomic-publish` (67e7dc83): sections 3, 5, 6, 7, 10.3-10.4 in full, the rest by search; W0 rev 2 and rulings from `main`. Code opened: `archive.py:55-93`, `workspace.py:78-100`, `engine.py:803-815`, `plan.py:321`.

**W0 finding 5 landed.** Verified in four places: the signature `publish_dir(final, fill, verify)` (3.2); step 5 runs before the rename and after the fsync pass, with the W0 text quoted (3.1, 3.3); `_Copy.fill` and `_Copy.verify` are the hook pair, and `verify` is the same `archive.verify` that `bench verify` calls, so one definition (6, DM7); `test_publish_dir_never_renames_when_verify_fails` with mutant M10 (10.2). The design also closes a trap: today's rows are hashed from the copy (`archive.py:77`, `_sha(dest)`), so a verify before the rename would compare a copy with itself; the rework hashes the source bytes in the same pass as the copy (6). W0 finding 6 landed too (explicit `lexists`, step 1). Patterns fit: Atomic Publish, Idempotent Receiver, Fail-Fast guard, Janitor by strict regex, Reconciliation by derivation. The state table in section 5 (S0-S6) is complete and idempotent by row key.

| # | location | finding | severity | evidence | fix | confidence |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 3.2 `RENAME_BACKOFF`, 3.3 step 7, 10.4 allowlist | **The rename-retry policy is written twice.** `atomic.RENAME_BACKOFF` is declared "same values as workspace.RENAME_BACKOFF" and `rename_with_retry` is private. `workspace._land` keeps its own loop (allowlisted as a separate site). Two copies of one WIN-A policy is the two-definitions signature; a tuned delay reaches one copy. | major | `workspace.py:89` (`RENAME_BACKOFF = (0.05, ..., None)`), `:100` (the loop); design 3.2, 10.4 | Make `rename_with_retry(src, dst)` public in `atomic.py` (no new import needed); `workspace._land` calls it and drops its constant, so the allowlist entry reduces to the content-addressed `valid(dest)` check. If `_land` must stay, say why and add a test that the two tuples are equal. | Verified |
| 2 | 7 "Template Method with hooks"; 10.4 | **The name overclaims, and so does "the caller cannot forget it".** Two callables are Strategy by function (callbacks), not Template Method (no subclass hook). Omission is prevented (`verify` is required); a no-op `lambda p: None` is not, and `test_every_publish_call_site_is_classified` classifies call sites without looking at the argument. | minor | design 7 row 3; 10.4 first bullet | Rename the row "callbacks (Strategy by function)". Extend the AST test: the `verify` argument at each `publish_dir` call is a named function or method reference, not a lambda or `None`. | Verified (text) |
| 3 | 3.5, 6 `make_writable` | **Two import paths for one function.** `make_writable` moves to `atomic`, and `archive` re-imports it so `workspace.py:84` and `plan.py:321` (`archive.make_writable`) keep working. A re-export alias outlives its reason. | minor | `workspace.py:84`; `plan.py:321`; design 3.2, 6 | Repoint the two callers to `atomic.make_writable` in the same commit and delete the alias (CT18a). | Verified |
| 4 | 5 `recover_archive` | Five positional parameters and a `tuple[ArchiveResult, list[dict]]` return whose second element means "rows not yet recorded". X-K1 will unpack by position. | minor | design 5 and 6 signature | Return a frozen dataclass `Recovery(result, missing_rows)`. | Verified (text) |
| 5 | 8 F20 | **F20 overclaims what `verify` detects.** The re-read after the fsync pass is served from the OS cache, so it catches copy-logic and source-read errors, not a bad write to disk. F20 lists "disk error" as prevented; 14 accepts power loss, not this. | minor | design 8 row F20; 3.3 steps 4-5 | Reword F20 to "copy logic and source read errors" and list silent disk corruption under 14 as accepted. | Inferred (NTFS cache behaviour not measured here) |
| 6 | 3.2 vs W0 rev 2 section 4 | Signatures of `create_once`, `publish_dir(final, fill, verify)` and `stale_temps` match W0 rev 2. The additions `sweep_temps`, `is_temp_name`, `HB-LED-009` are labelled provisional on seams S-B1 and S-B2 with a stated fallback. | nit | design 3.1, 3.5 | none | Verified |

**Seam disagreements (E2E-D).** W1-B 3.2 vs `workspace.py:89-100` (finding 1): the design and the code it classes as a separate site disagree on who owns the retry policy. W1-B vs W0 rev 2: none on behaviour; S-B1 and S-B2 are additions, not conflicts.

**Residual risk.** Finding 1 is where WIN-A drifts first.

GATE W1-B · Patterns Expert · PASS WITH CONDITIONS · 6 findings (rv-pat-gb-e1e4, 2026-10-03)

Condition: finding 1 before X-B1 merges; 2 to 5 may be recorded. Advisory lens.
