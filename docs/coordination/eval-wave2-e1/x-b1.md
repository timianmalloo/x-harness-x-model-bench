---
id: brief-eval-x-b1
title: "Brief X-B1: create_once, publish_dir, the temp sweep and the lock helper (E1 build)"
type: plan
status: proposed
owner: "@timianmalloo"
links:
  - { to: coordination-eval-wave2-e1-briefs, rel: implements }
  - { to: design-eval-atomic-publish, rel: depends-on }
  - { to: design-eval-seam-contracts, rel: depends-on }
review-by: "2026-10-17"
summary: "X-B1 builds atomic.py (W1-B rev 2), the workspace._land hunk and oslock.acquire_then_probe on Grok grok-4.7 high, in three dispatches, each red and green in one turn and joined before the next."
---

# X-B1: crash-atomic writes and the lock helper

**Harness** Grok via `coord-runner` (Leader, R-87), `grok-4.7`, `--reasoning-effort high`, grok 1.0.41, launched with `XAI_API_KEY` removed · **contract** `x-b1.contract.json` (B1a; B1b and B1c reuse it with the suffixes `b`, `c`) · **deadline** 1,200 s per dispatch · **budget** 40 calls · 100k per dispatch · 3 dispatches · 1.5 h total · **fallback** a red-only end, a timeout, or a served-model read that is not all `grok-4.7*`: the green follow-on runs as Claude Sonnet (`model: sonnet`, served `claude-sonnet-5-5`) in the same tree (R-87 Option 1; R-92 is the Owner review).

**Design:** `docs/design/eval-atomic-publish.md` (W1-B rev 2, on `main`, gate passed), sections 3, 4, 10, 11, 12.2, 17. **W0 rev 4:** sections 4 (as granted to S-B4), 6 (`acquire_then_probe`), 11, 13.

## Owned paths
`src/harness_bench/atomic.py` (new), `tests/test_atomic.py` (new), `tests/test_atomic_sites.py` (new), `tests/mutations/atomic.json` (new), `src/harness_bench/oslock.py` (E1: `acquire_then_probe` only), `tests/test_oslock.py` (the helper's tests), `src/harness_bench/workspace.py` (the `_land` hunk and the `make_writable` import only), `tests/mutations/workspace.json`. **Not yours:** `tests/test_workspace.py` (X-A1's; W1-B: it stays green unedited), `archive.py` (X-B2), `docs/lessons/defect-classes.md` (send W1-B §12.2's RIG-D instance to the Coordinator as text).

## Dispatches (each based on `main`; each lands red then green in one turn)
- **B1a** (`x-b1a-e1e4`, `build/eval-x-b1a`): `atomic.py` per W1-B §17 order: the naive skeleton (every public name, neutral wrong values) as the red commit's base, then `create_once`, `TEMP_RE`, `is_temp_name`, `stale_temps`, `sweep_temps(target, lock)` (raises `ValueError` unless `oslock.is_held(lock.path)`), `make_writable` (lstat first, never through a link, adds `S_IWUSR`), `rename_with_retry` with `RENAME_BACKOFF`. Depends on X-D1 (HB-LED-007 in the registry).
- **B1b** (`x-b1b-e1e4`): `publish_dir`; `workspace._land` calls `rename_with_retry(tmp, dest, replace=True, settled=lambda: valid(dest))` and drops its own loop; the WIN-A mutant moves; `tests/test_atomic_sites.py` (the scan, 12 sites in 11 keys, three red-fixture tests; the three grader `copytree` entries stay until X-F deletes them).
- **B1c** (`x-b1c-e1e4`): `oslock.acquire_then_probe(own, own_code, others, *, between=None) -> RunLock` (W0 rev 4 §6): `between` runs after the first operation and before the second; tests with `Barrier(2).wait(timeout=10)`: never both proceed; both-refused leaves every file unchanged; the swap mutant (probe before acquire) is killed by the barrier test.

## Acceptance items (design tests and live gate conditions)
1. The W1-B §10.2 nodes and the §10.3 mutation set M1..M27 plus M14b, each naming its killing test (MUT-B keeps the ids honest).
2. **RV-TA W1-B R2-3:** a mutation run on a Windows host **and** a POSIX host, both in the proof pack (M14 dies only on Windows, M14b only on POSIX): `test_posix_flag_default_follows_the_platform`, `test_the_real_publish_dir_fsyncs_the_folder_only_on_posix`. The POSIX half runs in CI's macOS job; say which run killed which.
3. **RV-SEC W1-B 5(c):** one recorded run of the three unmeasured symlink behaviours (`os.unlink` on a Windows directory symlink, `O_EXCL` onto a dangling symlink on Windows, the sweep of a symlink temp) on a host with symlink rights (macOS CI or Windows Developer Mode); `test_the_posix_job_does_not_skip_the_symlink_variants` and the CI rule that a skipped symlink variant fails the macOS job. Unmeasured on this host (winerror 1314).
4. **RV-SEC 2:** `create_once` keeps the fd open and compares `st_dev`/`st_ino` after the link (M22); reads through one descriptor with `O_NOFOLLOW` where available (M27).
5. **RV-DS 1:** `_discard_temp` swallows an unlink failure after a successful link and logs `atomic.temp_leaked` (M23). **RV-DS 4:** M25 (the lock check). **RV-DS 5:** `rename_retries`, `rename_ms`, `publish_failed(phase=rename)` asserted.
6. The kill tests `test_a_kill_between_write_and_link_leaves_no_final_file` and (B1b) `test_a_kill_mid_copy_leaves_no_final_folder_and_the_redo_succeeds`.

## Exit
README §3 join gate per dispatch; `python tools/grok_served_model.py <session dir>` exits 0 (R-92). Report per README §4.
