---
id: review-eval-sim-w1b
title: "Simplifier lens review of W1-B, crash-atomic publish"
type: doc
status: draft
owner: "@timianmalloo"
links:
  - { to: design-eval-seam-contracts, rel: relates-to }
review-by: "2026-10-17"
summary: >-
  RV-SIM (Simplifier, soft veto) findings on docs/design/eval-atomic-publish.md (design/eval-atomic-publish, 67e7dc83)
  against W0 rev 2 section 4 and R-87..R-93 on main. The two helpers, the strict verify and the temp reader fix earn
  their place; recover_archive is built two phases early and the test and telemetry surface has removable pieces.
---

# Simplifier review: W1-B crash-atomic publish (rv-sim-gb-e1e4)

Target: `docs/design/eval-atomic-publish.md` on `design/eval-atomic-publish` (`67e7dc83`), against W0 rev 2 section 4. Verified = read in the documents or in code; Inferred = reasoned. Question asked: is every piece earning its place?

## W1-B: atomic.py, archive.py rework

| # | location | finding | severity | evidence | fix | confidence |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 6 `recover_archive`, section 17 order, `archive.recovered`, M24, M25, two tests | `recover_archive` is built in E1 (X-B2) and has no caller until X-K1 in E3. Header: "X-K1 (resume) consumes `sweep_temps` and `recover_archive` in E3". Code with no reader for two phases is speculative, and it is the largest single piece (a 5-argument function, an event, two mutants, two test nodes, a rebuild test). | major | design header, section 5, section 17 | Keep the rule and the state table in the doc (W0 section 4 already quotes it). Move the build of `recover_archive`, its event and its tests to X-K1, where its first caller and real crash fixtures exist. X-B2 in E1 ships `archive_cell`, strict `verify`, `attempt_dirs`. | Verified |
| 2 | 5 table S0-S6 | Seven states, one rule. S2, S3 and S4 differ only by how many rows are already recorded; the code path is "recompute, compare, append the absent row keys, append the event if absent". S0 and S1 are not recoveries, S5 is "nothing to do", S6 is a stop. | minor | section 5 "Appending only absent keys is what makes S2 to S4 one rule" | State the rule once and keep S6 as the one stop condition; one test param each for zero, some and all rows recorded (the rebuild assertion already covers it). | Verified |
| 3 | 10.2 `test_atomic.py`, 10.3 | Several tests catch a failure no other catches only in name. (a) `..._round_trips_any_bytes` uses hypothesis, but the fixed `b"a\nb\r\nc\n"` alone kills M2 (measured, 7 to 10 bytes). (b) the `is_temp_name` hypothesis property duplicates `test_stale_temps_lists_only_...` (M17). (c) `..._never_renames_when_fill_raises` and `..._when_verify_fails` both kill M10; one param. (d) `test_a_persistent_rename_refusal_raises_after_the_backoff` (M16, "unbounded retry") tests a loop over a fixed tuple. (e) `test_publish_logs_one_record_with_phase_timings` (M21, "no log") tests that logging happens. | minor | section 10.2 rows; section 10.3 | Drop the two hypothesis tests, merge (c), keep (d) only if the retry is a `while` and not a tuple walk, and fold (e) into one assertion on a record a consumer needs. About four fewer nodes and mutants (M16, M21 among them). | Inferred (mutant kill sets not run) |
| 4 | 10.4 `tests/test_atomic_sites.py` | Two continuous-ring tests. The AST scan includes "every `os.mkdir`/`Path.mkdir` that creates a name later published", which an AST cannot decide: it will be noisy or hollow. `test_atomic_imports_only_stdlib_and_errors` repeats what the import cycle named in the `simplify:` marker would show at import. | minor | section 10.4 | Narrow the scan to `os.link/rename/replace` and `shutil.move/copytree` with a (module, function) allowlist; drop the `mkdir` clause and the import test. | Inferred |
| 5 | 3.5 S-B1 `HB-LED-009`, F17, M8 | A new registry code, a wrapper and a test for "the volume cannot hard-link". The campaign runs on the dev volume (spike E1-S1: `os.link` works on NTFS). An unwrapped `OSError` from `os.link` is already loud and the design forbids a fallback anyway. | minor | 3.3 step 4, F17 | Let the `OSError` propagate with the path in the message; no new code, no registry row, no test. Add the code when a volume that cannot link appears. | Inferred |
| 6 | 11 telemetry | Six events. `atomic.rename_retry` (per attempt) repeats `rename_retries` on `atomic.publish`. `atomic.create_once` INFO on every success is noise (success is the file existing). | minor | section 11 table | Drop `atomic.rename_retry`; log `atomic.create_once` for `conflict` only. Keep the `atomic.publish` phase timings, `atomic.temp_swept` and `atomic.publish_failed`. | Verified |
| 7 | section 4 row 3, S-B3, `archive.attempt_dirs` | The reader bug is real: `judges.py:216` does `int(p.name.split("-")[1])`, so `attempt-1.tmp-123-ab` gives `"1.tmp"` and a `ValueError` (Verified in code). But `pack_improvement.py` already has `_attempt_dirs` (line 783 area). The design adds a third helper and a seam request (S-B3) for a 3e-7 risk. | minor | `judges.py:216`; `pack_improvement.py:783-786` | Fix `pack_improvement._attempt_dirs` in place with `re.fullmatch(r"attempt-(\d+)")`, move it to `archive.py`, have `judges.py` import it. Drop S-B3 as a separate request (note it in the X-A3 brief). | Verified |
| 8 | 3.2 vs W0 rev 2 section 4 and ADR-0021 section 4 | Seam note, not a conflict. W0 section 4 defines `stale_temps` as `<target.name>.tmp-*`; W1-B narrows it to a strict regex, and adds `sweep_temps`, `is_temp_name`, `make_writable` to W0's API list. The narrowing is the safer reading; the additions are provisional on S-B1. | minor | W0 section 4 lines 185-193 | Coordinator records the narrowed pattern as the W0 text, so X-C and X-K1 read one definition. | Verified |

**Kept as earning their place:** `create_once` and `publish_dir` as the only two helpers; the explicit `lexists`; the no-journal, no-marker data model (the name is the completeness fact); the strict `verify` with rows hashed from the source (red today, closes a real gap); `sweep_temps` as the single reparse-point guard; the Windows folder-fsync skip with its one test; the PUB-A class with a classified-call-site gate; the `.gitignore` lines (measured in spike E1-S2). The 28-row failure table is long but each disposition is one line and untested rows say why.

**Seam disagreements:** none against W0 beyond finding 8.

Blocking: none. Soft veto not exercised. Finding 1 should be decided by the Coordinator before X-B2 is dispatched, because it changes X-B2's scope.

GATE W1-B · Simplifier · PASS WITH CONDITIONS · 8 findings (rv-sim-gb-e1e4, 2026-10-03)
