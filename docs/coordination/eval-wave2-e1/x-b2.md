---
id: brief-eval-x-b2
title: "Brief X-B2: crash-atomic final archive (E1 build)"
type: plan
status: proposed
owner: "@timianmalloo"
links:
  - { to: coordination-eval-wave2-e1-briefs, rel: implements }
  - { to: design-eval-atomic-publish, rel: depends-on }
  - { to: design-eval-seam-contracts, rel: depends-on }
review-by: "2026-10-17"
summary: "X-B2 reworks archive.archive_cell onto atomic.publish_dir with a strict verify and archive.attempt_dirs as the one attempt-folder reader (W1-B rev 2 section 6) on Agy gemini-3.8-flash-high, one turn red and green."
---

# X-B2: crash-atomic archive

**Harness** Agy via `coord-runner` (Leader, R-87), `gemini-3.8-flash-high`, agy 1.2.13, `--mode accept-edits` · **contract** `x-b2.contract.json` · **deadline** 3,300 s · **dispatch** one turn, red then green · **budget** 120 calls · 150k · 1 · 1.5 h · **fallback** the green follow-on as Claude Sonnet (`model: sonnet`, served `claude-sonnet-5-5`) in the same tree, after an Owner review.

**Design:** `docs/design/eval-atomic-publish.md` §6 (archive rework), §10 (the archive nodes and A1..A4), §12.1 (the defect class). **W0 rev 4:** section 4 (`publish_dir`, "Readers of the archive folder", `recover_archive` is X-K1's in E3), 13.

## Owned paths
`src/harness_bench/archive.py` (E1), `report/judges.py` (the `attempt_dirs` line at `:216` only), `tests/test_archive.py`, `tests/mutations/archive.json`, and in `tests/test_engine.py` only `test_the_engine_archive_goes_through_publish_dir` and in `tests/test_views.py` only `test_bench_verify_passes_a_run_archived_by_the_atomic_path` — both files belong to other E1 owners (X-D, X-A1), so send each as a seam request to them **or** place both tests in `tests/test_archive.py` if they need no private fixture of those files; say which in your report.

## Depends on
**X-B1b joined** (`atomic.publish_dir`); X-D1 (codes).

## Acceptance items
1. **Red first against today's `archive_cell`:** a kill during an archive copy, then a resume completes without `HB-USR-002` (D1); a `*.tmp-*` sibling is redone; red by assertion.
2. `archive_cell` goes through `atomic.publish_dir` with a `verify` that compares the file set and each file's rows; the real-wiring test fails if the call is removed.
3. `archive.attempt_dirs(run_dir, cell_id)` (`re.fullmatch(r"attempt-(\d+)")`, sorted by number) is the one reader; `report/judges.py:216` uses it; a leaked `attempt-1.tmp-…` no longer raises `ValueError` there.
4. `archive.make_writable` stays a re-export of `atomic.make_writable` (W0 §4).
5. The mutants A1..A4 in `tests/mutations/archive.json`, each naming its killing test.
6. The "exists means complete" defect-class text (W1-B §12.1) goes to the Coordinator in your report; you do not edit `docs/lessons/defect-classes.md`.

## Exit
README §3 join gate; served model read from Agy's `cli.log`. Report per README §4.
