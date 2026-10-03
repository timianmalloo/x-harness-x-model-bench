---
id: review-eval-sec-w1b
title: "Security & Identity review of W1-B: crash-atomic publish (Adversary Mode)"
type: doc
status: draft
owner: "@timianmalloo"
tags: [review, security, evaluation-campaign, wave-1, w1-b]
links:
  - { to: design-eval-seam-contracts, rel: relates-to }
  - { to: review-eval-sec, rel: refines }
review-by: "2026-10-17"
summary: >-
  Security & Identity gate on W1-B (design/eval-atomic-publish, 67e7dc83) against W0 rev 2. W0 F10 landed (nonce
  temp name, exclusive create, lstat-first non-recursing sweep, tests named). Open: ignore patterns hide planted
  content from the tamper check, the temp-to-final link has no identity check, and the symlink branch is unmeasured
  with a test that can skip everywhere. PASS WITH CONDITIONS, 8 findings.
---

# Security & Identity review of W1-B (rv-sec-w1b-e1e4)

PERSONA: security-identity-architect · MODE: Adversary · TIER: T2. Severity: blocking / major / minor. Confidence: Verified (observed in a file) / Inferred (reasoned; the confirming check is named). RV-DS already passed W1-B with conditions (`eval-review-ds-w1b.md`); I do not repeat its five findings.

## W1-B: `docs/design/eval-atomic-publish.md` (branch `design/eval-atomic-publish`, 67e7dc83)

Trust boundaries: B1 to B4 (design 15). I agree with the set. Dependencies added: none (stdlib). No PII.

### W0 F10 and the named checks

| item | result | evidence |
| --- | --- | --- |
| F10 predictable name | Landed. `<name>.tmp-<pid>-<uuid4 hex>`, 122 bits; `TEMP_RE` is a `fullmatch` on `[0-9a-f]{32}`, so a trailing newline or a short nonce cannot match | design 3.2, 3.4 |
| F10 exclusive create | Landed. `O_CREAT\|O_EXCL` for files, `os.mkdir` for folders; `fill` gets an empty new folder | 3.3 step 2; `publish_dir` step 2 |
| F10 reparse guard | Landed. `lstat` first, unlink a reparse point, never recurse; tests `test_sweep_temps_unlinks_reparse_points_without_recursing` and `test_publish_dir_refuses_a_squatted_reparse_point` are named. Junction behaviour is Verified by spike E1-S2; the symlink branch is not (finding 5) | 3.3 `sweep_temps`; 13 |
| O_BINARY (E1-S2, 7 to 10 bytes) | Landed in `create_once` and the fsync pass. Gaps in finding 7 | 3.3 step 2 |
| campaign.lock and temps cannot plant content into an archive | Holds for archives: an archive is built from the cell working copy, a pre-made final name is refused by `lexists`, and `recover_archive` compares folder to source and changes nothing on a mismatch. Does **not** hold for the record trees: findings 1, 2, 3, 8 | 5, 6; `archive.py:98-100` re-verifies before the workspace is deleted |

### Findings

| # | location | finding | severity | evidence | fix | confidence |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 4 table row 1, 3.5 S-B2, F11 | The three ignore patterns make any file **or folder** with a temp-shaped name, or named `campaign.lock`, invisible to `git status`, and `verify` also skips temp names. A folder `x.tmp-1-<32 hex>/` can hold arbitrary files and `campaign.lock` can be a folder with content; the ADR-0018 11(b) tamper check sees neither. The design records the hiding as a benefit (spike last row) and never asks what it hides | major | design 4 and 13 last row: "the lock, the temp files and a temp folder with a file are absent"; the pattern `bench/campaigns/*/campaign.lock` matches a directory too | X-C `verify`: `lstat` `campaign.lock` (must be a regular file) and report the count and names of temp-named entries as a warning line, never silent. Tests: `test_campaign_verify_rejects_a_lock_that_is_a_folder_or_link`, `test_campaign_verify_reports_leaked_temps_by_name` | Verified (design text); git behaviour is the design's own measurement |
| 2 | 3.3 `create_once` steps 3-4 | `os.link(tmp, path)` takes the temp **by name** after the fd is closed. The nonce stops pre-squatting, not replacement: the temp is listed in the directory, so a same-user process reads the nonce and can swap the temp (another file, or on POSIX a symlink; `os.link` follows symlinks by default) between `close` and `link`. The planted content is published under the final name and `create_once` returns `True`. 15 row B2 covers pre-creation only | major | 3.3 step 3 `os.close(fd)` then step 4 `os.link(tmp, path)`; 15 B2 rows | Keep the fd open through the link. After it, require `os.fstat(fd)` and `os.lstat(path)` to agree on `st_dev` and `st_ino`; on a mismatch unlink only the name this call created and raise `HB-LED-007`. On POSIX pass `follow_symlinks=False`. Test: patch `os.link` to swap the temp first; expect the raise. Content-addressed callers' hash check stays the second line (ADR-0016 8: detected, not prevented) | Inferred (call order and `os.link` semantics; the swap test on POSIX CI confirms) |
| 3 | 3.3 `publish_dir` steps 5-7; 15 B2 | The archive temp is visible and writable by the operator's processes (the cell) from `fill` to `rename`. A write after `verify(tmp)` and before `rename` is published in the final folder. Rows come from the source, so `bench verify` and `delete_after_verify` (`archive.py:98-100`) catch it before the workspace is deleted, but the design never says so and 15 has no row for it | minor | 3.3 steps 5, 7; `archive.py:98-100` | Add a 15 row: tamper after verify, disposition **detect** (strict `verify` later, workspace kept on failure), residual accepted per ADR-0012. Add `test_a_file_added_after_verify_is_caught_by_delete_after_verify` | Verified (code read) |
| 4 | 3.3 `create_once` step 4, `FileExistsError` branch | `lstat(path)` then a read by name is a check-then-use gap: the path can become a link between the two. The harm is an equal-bytes oracle, not a write | minor | 3.3 step 4 | Open with `O_RDONLY\|O_BINARY` (plus `O_NOFOLLOW` where it exists), `fstat` the fd, require a regular file, read from the fd | Inferred |
| 5 | 3.4, 10.2 squat-test row, 13 "Still Flagged" | The symlink branch is unmeasured on this host (winerror 1314). The squat test is "skipped with a stated reason", so a skip that fires on every runner is a control that never runs, and no test asserts that the macOS job ran the symlink variants. Also unmeasured: `os.unlink` on a Windows **directory** symlink, and `O_EXCL` onto a dangling symlink on Windows. The junction test says "the predicted temp name" without saying how the name is predicted | major | design 13 row "a symlink: not creatable on this host"; 10.2 squat row | (a) Patch `os.getpid` and `uuid.uuid4` in the squat tests and say so. (b) Add a test that fails when the POSIX job reports the symlink variants as skipped. (c) Record in X-B1's proof pack one run of the symlink tests on a host with symlink rights (Windows Developer Mode, or the macOS job) covering the three unmeasured behaviours | Verified (gap in the text); the behaviours are Inferred |
| 6 | 3.2 `make_writable` (moved from `archive.py:93-95`) | `os.chmod(path, stat.S_IWRITE)` follows a symlink and on POSIX sets the mode to exactly `0200`. `rmtree(onexc=make_writable)` calls it on a failed delete, so a symlink inside a temp tree whose unlink failed gets its **target** re-moded, outside the temp. The design moves this function into the sweep without review | minor | `archive.py:93-95`; 3.3 `sweep_temps` folder case | In `atomic.make_writable`, `lstat` first and return without chmod for a link; OR `S_IWUSR` onto the current mode instead of replacing it. Test: a symlink inside a temp folder pointing at a sentinel | Verified (code read) |
| 7 | 3.3 step 2, 10.3, 10.4, 12.2 | O_BINARY is fixed for `create_once`, but its killer test cannot fail off Windows (`getattr(os, "O_BINARY", 0)` is 0 there). Gaps: the write mode of `dst` in `_copy_hashed` is not stated; M2 dies only in a Windows mutation run; the AST scan (10.4) does not cover `os.open`. The only other `os.open` sites today are `oslock.py:55` and `:82` (no content written; harmless) | minor | grep of `src/harness_bench` for `os.open(`; 10.4 lists link, rename, replace, move, copytree, mkdir | State `wb` for `_copy_hashed`. Add `os.open` to the 10.4 scan: each site passes `O_BINARY` or is allowlisted with a reason. Name the Windows run as the one that must kill M2 | Verified |
| 8 | 4, 6 compute readers; `campaign.lock` consumers | `oslock.acquire` opens with `O_RDWR\|O_CREAT` and no `O_NOFOLLOW`, then `heartbeat` calls `os.utime` by path. A `campaign.lock` replaced by a link makes X-C lock and touch another file (mtime only; no bytes written, so no content planting through the lock itself). The design treats the lock only as an ignore pattern | minor | `oslock.py:55`, `:62-63`; W0 `eval-seam-contracts.md` lines 239, 269 | Fold into the finding 1 fix: X-C `lstat`s `campaign.lock` before `acquire` and refuses a non-regular file; one test | Verified (code read) |

### Seam disagreements
Finding 8: W1-B S-B2 and W0 section 13 (`.gitignore` row for `campaign.lock`) treat the lock as a plain ignored file, and W0 section 11 plus `oslock.py` give it no type check. No contradiction in text; a missing rule at the W1-B to X-C seam. S-B1 and S-B2 are pending with the Coordinator. I do not object to either, and finding 1 adds a requirement to S-B2.

### Conditions for PASS
(1) Finding 1: `verify` names temp-named entries and checks `campaign.lock` is a regular file, with tests. (2) Finding 2: identity check of the linked inode with the fd kept open, and a swap test. (3) Finding 5: the squat tests patch the nonce, a test proves the symlink variants ran on the POSIX job, and the three unmeasured behaviours are recorded once on a host that can run them. Findings 3, 4, 6, 7, 8 are advice for the same revision.

RESIDUAL RISK: power loss between fsync and rename (design F26, accepted); a hostile same-user cell can deny a publish or tamper before `verify`, detected not prevented (ADR-0012, accepted); symlink semantics on Windows until finding 5(c) runs. CLEARS-THE-VETO: yes on conditions 1 to 3, none of which needs a redesign.

GATE W1-B · Security & Identity · PASS WITH CONDITIONS · 8 findings (rv-sec-w1b-e1e4, 2026-10-03)
