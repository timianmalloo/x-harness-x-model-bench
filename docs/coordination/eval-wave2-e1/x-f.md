---
id: brief-eval-x-f
title: "Brief X-F: property grader and hidden-check runner (E1 build)"
type: plan
status: proposed
owner: "@timianmalloo"
links:
  - { to: coordination-eval-wave2-e1-briefs, rel: implements }
  - { to: design-eval-property-grader, rel: depends-on }
  - { to: design-eval-seam-contracts, rel: depends-on }
review-by: "2026-10-17"
summary: "X-F builds grade/property.py, bench_check.py, _env.py and the runner, correctness, mutation, procs and egress edits of W1-F rev 3, red first, on Sonnet; F0 (the skeleton) joins first so X-G1 can start."
---

# X-F: property grader and hidden-check runner

**Session** `x-f-e1e4` · **branch** `build/eval-x-f` · **harness** Claude Code Agent tool, `model: sonnet` (served `claude-sonnet-5-5`, R-91), spawned with cwd = the tree path; security-sensitive, so not external · **budget** 260 calls · 200k context per session · up to 3 sessions (a fresh one per group past 150k) · 4 h · **fallback** a fresh Sonnet session from this brief (the tree and its commits carry the state).

**Design:** `docs/design/eval-property-grader.md` (W1-F rev 3, on `main`). **W0 rev 4:** sections 3 (all, including "Section 3 additions (rev 4)"), 6 (the grading side of `acquire_then_probe`; W1-F §5.11's `campaign.lock_held` pre-check is **superseded**), 7, 9, 10 (G4, G5, D3), 13.

## Owned paths (W0 §13)
`src/harness_bench/grade/property.py`, `grade/bench_check.py`, `grade/_env.py` (new); `grade/correctness.py`, `grade/mutation.py`, `grade/formal.py` (the `DOTNET_HOST_ENV` move, the copy-helper switch, the non-owner guard), `grade/_changes.py` (`grading_copy` and the reparse-safe copy helper only; line 84 is X-A1's), `grade/runner.py` (E1, except lines 108-112, X-D's, and the after-grading `verify` hook hunk, X-C's after you join), `procs.py`, `egress.py`; `tests/test_property_grader.py` (new), `tests/test_grade_runner.py`, `tests/test_procs.py`, `tests/test_egress.py`, `tests/fixtures/property/**` (new), `tests/mutations/property.json`; in `tests/test_atomic_sites.py` (X-B1's) **only** the deletion of the three grader `copytree` allowlist entries, in your RF-9 commit.
Not yours: `errors.py` and `tests/test_architecture.py` (X-D adds your HB codes and the `SUBPROCESS_CALLERS` / R-60 entries), `oslock.py` (X-B1 builds `acquire_then_probe`), `campaign.py` (X-C), `metrics.yaml` (X-G1).

## Depends on (joined on `main`)
- F0 depends on nothing. F1.. need **X-D1** (codes, `tests/import_graph.py`, the `catalog_hash` import in `runner.py`: rebase on it, never re-edit 108-112). F2 needs **X-G1** (property tags for `applicable`). The RF-9 commit needs **X-B1b** (`tests/test_atomic_sites.py`). The grading-side probe needs **X-B1c**.

## Commit groups (each red then green; record every red SHA and failing assertion)
- **F0 (first, ask the Leader to merge it at once):** `grade/property.py` with a docstring only. Nothing else. X-G1 cannot go green until it is on `main` (W0 §7 join order).
- **F1:** `_env.py` (`HOST_ENV`, `TOOLCHAIN_ENV`, `DOTNET_HOST_ENV` moved verbatim, `grading_env()`), the `correctness`/`mutation` imports (US-4 byte-equal), G4 with its red fixture; RF-9: one reparse-safe copy helper in `grade/_changes.py` used by `grading_copy`, `correctness.py:207`, `formal.py:280`, with `test_grading_copy_with_junction_leaves_target_untouched` through each grader, and the three `test_atomic_sites.py` entries deleted in the same commit; `egress.py` `task_canary`.
- **F2:** `runner.applicable(catalog, graders, prop)` with R-95's two clauses and T-R3..T-R6 (W1-G assigns them to you; the `formal` non-owner guard through a real `run_pass`); the property grader's two phases, one `SleepDetector` per phase; the outcome table rows 1-7 with one red test per row and per adjacent pair; `grading.started.grade_identity_hash` plus `python` and `platform` as plain fields (RV-SRE W1-D 6) and a negative case for non-campaign passes (RV-TA W1-D 8).
- **F3:** the probe host (`callable` and `wsgi`, frames, environ, `{state_dir}`, `paths`, app output, start bound); the grading side of the campaign lock: `oslock.acquire_then_probe(grade.lock, "HB-GRD-001", [(bench/campaigns/<plan.campaign.campaign_id>/campaign.lock, "HB-GRD-007")])` only for a plan with a `campaign` block (path built inline, marked `simplify:`; X-C replaces it with `campaign.lock_path`). Do **not** add the after-grading `campaign.verify` call: that hunk is X-C's.

## Acceptance items (the design's tests, plus every live gate condition)
1. The ADR-0018 red tests named in W0 §10 and the design: `test_property_check_env_excludes_credentials`, `test_deliverable_cannot_write_result_pipe`, `test_forged_result_via_duplicated_handle_is_tampered`, `test_check_killed_before_write_is_tampered`, `test_forged_write_racing_deliverable_exit_yields_two_documents`, `test_import_time_forgery_cannot_reach_result`; check-bound, check-tamper (`[clean_exit]`, `[hash+clean_valid]`, `[hash+malformed]`) and seeded-suspend tests for **each phase**; a re-grade of one archive is identical (EV-2).
2. **RV-SEC W1-F rev 3, 1:** commit `forge_factory.py` under `tests/fixtures/property/` with its positive control (the same module called in-check: the forged `blocked` is accepted, row 7), three trials, like `forge_module.py`. The SP-F3 9/9 figure is Inferred until then.
3. **RV-SEC rev 3, 2:** `check-run/state/<case id>/` is created fresh with `exist_ok=False` after an `lstat`; a pre-existing entry is removed, a reparse point unlinked without entering it. Red fixtures: case 1's app seeds `state/<case 2>/seed.db`; a junction variant.
4. **RV-SEC rev 3, 3 (W0 rev 4 §3):** case ids match `^[a-z0-9][a-z0-9_-]{0,31}$` in the `cases.json` writer; red fixtures `..`, `a:b`, `nul`.
5. **RV-TA rev 3, 1:** `test_app_output_grandchild_default_stdio_is_not_captured` through the real host (RF-11 pinned: the child's token is not in the app-output file, nothing but EOF follows on the protocol, `GetStdHandle(-11)` equals fd 1's handle).
6. **RV-TA rev 3, 2:** `test_probe_host_start_bound_is_the_interface_bound[within,past,case_hang]`; `case_hang` asserts `deliverable == "ran"`, outcome `timeout`, `hosts.jsonl` `end == "ready"`, `start_ms < 200`; `within` asserts `end: ready` and `start_ms >= 500`; `past` asserts `cases == []`; one mutant per misclassification.
7. **RV-TA rev 3, 3-6:** assert `path.exists()` first in the app-output nodes; G23 is 7 lines in 3 files, with a scan test and a one-extra-reader red fixture; **the frame and environ golden** (W0 rev 4 §3: exact request and response key sets of both kinds, `set(environ) == W0_ENVIRON_KEYS | {"HTTP_AUTHORIZATION"}`); a `case2` parameter of the `did_not_start` node; an `app_output` parameter of the egress node.
8. **RV-SEC rev 3, 4-6 (text):** N12 says the cap bounds evidence, not disk; run the `getstdhandle` parameter on both interpreters (3.14.6 and 3.12.10) and make the `ctypes` write a real test.
9. **RV-TA W1-F rev 2 residuals:** a `tests/mutations/property.json` row-1 mutant that drops the tests-span term; a host that never writes its ready line gives row 6, not row 2.
10. **RV-SEC W1-F rev 2:** re-run the forgery fixtures through the real grader.
11. G4 and G5 with red fixtures; the `paths` writer-side test `test_cases_paths_outside_root_are_refused` (X-E owns the readiness-side test).
12. `property_check_pass` truth table: reference 1, naive 0, tamper NA, did-not-build 0.

## Exit
The README §3 join gate, plus the gate ring and stamp renewal (the Leader, once per batch). Report per README §4.
