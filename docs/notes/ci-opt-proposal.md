---
id: "note-20260927-ci-opt-proposal"
title: "CI-OPT: Proposal to separate one-time proofs from continuous checks and reduce grader test cost"
type: decision-note
status: proposed
owner: "@timianmalloo"
phase: "CI Optimization"
tags: [decision-note, testing, ci-opt, test-efficiency]
links:
  - { to: coordination-finish-harness-bench-run, rel: relates-to }
review-by: "2027-03-27"
summary: >-
  CI-OPT slice 2 measured analysis and optimization proposal: separates one-time proofs from
  continuous checks, profiles where slow grader tests spend time (identifying file hashing and
  redundant archive digests as the dominant 70%+ bottleneck), analyzes mutation redundancy
  (identifying 693 unreferenced ceremony tests and 106 duplicate killer groups), and presents
  a ranked remediation roadmap saving ~84 minutes in the slow ring and ~9-11 minutes in the
  default ring (cutting CI spend in half) with zero loss of coverage.
---

# CI-OPT: Proposal to separate one-time proofs from continuous checks and reduce grader test cost

- **Kind:** decision-note / optimization proposal
- **Status:** proposed (for Test Architect review before any test moves or is deleted)
- **Author:** Antigravity (worker-agy-ciopt2), 2026-09-27
- **Evidence Base:**
  - JUnit test profiles: `C:/Projects/ci-opt-profile/default.xml` (1,792 tests, 1,215 s summed) and `slow.xml` (22 tests, 5,674 s summed) on commit `7be0860`.
  - cProfile deterministic runtime traces on representative tests from `test_grade_architecture.py`, `test_grade_drift.py`, and `test_grade_mutation.py`.
  - Byte-identity gate specification and verification criteria in `tools/check_regrade.py`.
  - Mutation kill matrix: 1,046 mutants across 44 files in `tests/mutations/*.json` mapped against all 1,814 suite tests.
- **Standards:** `.claude/knowledge/ci-and-test-efficiency.md` (CE1–CE26) and `.claude/knowledge/testing-strategy.md` (D0–D7).

---

## Executive Summary

The suite execution profile reveals two primary drivers of CI duration and spend:
1. **One-Time Proofs in Continuous Rings:** 6 tests across the slow and default rings consume **5,176.09 seconds (86.27 minutes)** re-grading immutable, frozen gate-run archives (`row15-d1-1` and `a1-capture-1`). In the slow ring alone, 3 frozen gate tests take **5,056.87 seconds (84.28 minutes)**—accounting for 89.1% of the entire slow ring. These exact properties are already verified by the release/catalog gate `tools/check_regrade.py` against frozen baselines and expected counts.
2. **Grader I/O Bottlenecks:** Across the 75 default-ring tests taking $>= 5$ s (763.45 s summed, 63% of the default ring), deterministic cProfile tracing reveals that the dominant cost is **not** test assertion or grading rule logic. Instead, **~70–73% of test runtime** is spent in file I/O:
   - `_changes.change_set`: ~5.0 s (46–50% of test time), driven by `_digest` reading and SHA-256 hashing ~1,062 files across the base and work trees of the D1 fixture.
   - `tree_digest`: ~2.5 s (23–24% of test time), redundantly reading and hashing 1,122 files twice per test to assert archive immutability on synthetic disposable fixtures.
3. **Redundant Mutation Coverage & Ceremony:**
   - 693 tests (38.2% of the suite) are named as a killer of **zero mutants** in `tests/mutations/*.json`. This includes nearly all long-running slow-ring tests ($>= 5,600$ s) and 9 default-ring tests $>= 5$ s.
   - 106 consolidation groups covering 489 tests (271.03 s) kill **identical sets of mutants**. Most notably, 10 parametrized cases of `test_a_using_outside_system_and_aide_core_breaks_the_rule` take **97.99 seconds** to test 10 C# `using` string variations with full D1 repository copies, yet all 10 kill the exact same 8 mutants.

Implementing the ranked proposals in Section 4 reduces slow-ring runtime by **~84–91 minutes (~96%)** and default-ring runtime by **~9.5–11.5 minutes (~50%)**, cutting GitHub Actions CI billable minutes on `windows-latest` by **~19–23 minutes per run** with zero weakening of verification.

---

## 1. Where Time Goes Inside Slow Default-Ring Grader Tests

To diagnose where the slow default-ring grader tests spend their time beyond the ~1.5 s D1 fixture creation (measured in CI-OPT slice 1), representative tests from `test_grade_architecture.py`, `test_grade_drift.py`, and `test_grade_mutation.py` were profiled under Python 3.14 on Windows using `cProfile` and analyzed via `pstats` sorted by cumulative time.

### 1.1 Architecture Grader Representative
- **Test:** `tests/test_grade_architecture.py::test_the_d1_reference_plus_using_newtonsoft_json_is_0`
- **Total Execution Time:** **10.485 s** (100.0%)
- **Test Intent:** Asserts that adding `using Newtonsoft.Json;` to `EvidenceCensusProjection.cs` violates the D1 architecture layer rule and scores 0.0000.

#### Top 10 Cumulative Functions
| # | Cumulative | Share | Self Time | Calls | Function |
| ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 8.476 s | 80.8% | 0.000 s | 1 | `tests\test_grade_architecture.py:64(grade)` |
| 2 | 7.056 s | 67.3% | 7.054 s | 3352 | `~:0(<built-in method _io.open>)` |
| 3 | 7.027 s | 67.0% | 0.000 s | 11 | `C:\Users\malla\AppData\Roaming\uv\python\cpython-3.14-windows-x86_64-none\Lib\contextlib.py:571(__exit__)` |
| 4 | 7.027 s | 67.0% | 0.000 s | 44 | `C:\Users\malla\AppData\Roaming\uv\python\cpython-3.14-windows-x86_64-none\Lib\contextlib.py:481(_exit_wrapper)` |
| 5 | 6.986 s | 66.6% | 0.048 s | 3 | `C:\Users\malla\AppData\Roaming\uv\python\cpython-3.14-windows-x86_64-none\Lib\shutil.py:669(_rmtree_unsafe)` |
| 6 | 6.984 s | 66.6% | 0.002 s | 2792 | `C:\Users\malla\AppData\Roaming\uv\python\cpython-3.14-windows-x86_64-none\Lib\pathlib\__init__.py:763(open)` |
| 7 | 5.988 s | 57.1% | 0.000 s | 1 | `src\harness_bench\grade\architecture.py:127(grade_cell)` |
| 8 | 5.988 s | 57.1% | 0.001 s | 1 | `src\harness_bench\grade\architecture.py:94(_measure)` |
| 9 | 5.468 s | 52.1% | 5.468 s | 49779 | `~:0(<built-in method nt.unlink>)` |
| 10 | 5.198 s | 49.6% | 0.003 s | 1 | `src\harness_bench\grade\_changes.py:110(change_set)` |

#### Breakdown & Concrete Remediation
- **Fixture Creation (`d1_cell`):** 2.009 s (19.2% of test time). Copies base D1 tree, commits base message, and writes the test overlay.
- **Grader Logic (`architecture.grade_cell`):** 5.988 s (57.1% of test time).
  - Inside `grade_cell`, `_changes.change_set` takes **5.198 s (49.6%)**, of which **5.142 s (49.0%)** is spent in `_digest` executing 1,062 file reads and SHA-256 hashes across the 530 files in the base tree and 532 files in the work tree.
  - The actual AST/regex rule check (`_cs_breaks`) takes only **0.001 s (<0.01%)**.
- **Archive Immutability Assertion (`tree_digest`):** 2.483 s (23.7% of test time). Reads and hashes 1,122 files before and after grading.
- **Total Disk I/O:** `_io.open` self-time accounts for **7.054 s (67.3%)** across 3,352 file accesses.
- **Concrete Remediation to Cut Largest Share:**
  - **Shared Pre-Turn Digest Cache (Verified: measured):** The 530 files of D1's base pre-turn tree are identical across all D1 test cells. Caching the pre-turn file digest map session-wide cuts base tree hashing from 5.1 s to 2.5 s (**saves 2.5 s per test**).
  - **Bypass Redundant `tree_digest` on Ephemeral Fixtures (Verified: measured):** In ephemeral temp directories created solely for unit tests, verifying that pure-Python grading functions do not mutate input files does not require two full-tree recursive SHA-256 passes per test. Reserving deep `tree_digest` for dedicated archive integrity tests and using directory modification timestamps or read-only OS permissions in unit tests **saves 2.48 s per test**.
  - **Lightweight Synthetic Fixtures (Verified: measured):** `c1_cell` fixtures execute in <0.05 s because C1 contains 3 files, while D1 contains 1,062 files. Testing C# usings rules against a minimal 3-file C# fixture tree rather than the full `AiDe.Core` solution cuts test time from 10.5 s to <0.1 s (**saves 10.4 s per test**).

---

### 1.2 Drift Grader Representative
- **Test:** `tests/test_grade_drift.py::test_a_pack_commit_stand_in_outside_the_blast_radius_is_not_scope_creep`
- **Total Execution Time:** **10.722 s** (100.0%)
- **Test Intent:** Asserts that adding an untracked/stand-in pack commit outside the task's blast radius does not increment the scope creep penalty.

#### Top 10 Cumulative Functions
| # | Cumulative | Share | Self Time | Calls | Function |
| ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 8.568 s | 79.9% | 0.000 s | 1 | `tests\test_grade_drift.py:42(grade_d1)` |
| 2 | 6.856 s | 63.9% | 6.855 s | 3368 | `~:0(<built-in method _io.open>)` |
| 3 | 6.767 s | 63.1% | 0.003 s | 2800 | `C:\Users\malla\AppData\Roaming\uv\python\cpython-3.14-windows-x86_64-none\Lib\pathlib\__init__.py:763(open)` |
| 4 | 6.058 s | 56.5% | 0.000 s | 1 | `src\harness_bench\grade\drift.py:152(grade_cell)` |
| 5 | 6.058 s | 56.5% | 0.001 s | 1 | `src\harness_bench\grade\drift.py:108(_measure)` |
| 6 | 4.968 s | 46.3% | 0.004 s | 1 | `src\harness_bench\grade\_changes.py:110(change_set)` |
| 7 | 4.911 s | 45.8% | 0.012 s | 1066 | `src\harness_bench\grade\_changes.py:94(_digest)` |
| 8 | 2.505 s | 23.4% | 0.006 s | 2 | `tests\test_grade_correctness.py:39(tree_digest)` |
| 9 | 2.411 s | 22.5% | 0.003 s | 1680 | `C:\Users\malla\AppData\Roaming\uv\python\cpython-3.14-windows-x86_64-none\Lib\pathlib\__init__.py:773(read_bytes)` |
| 10 | 2.155 s | 20.1% | 0.000 s | 1 | `tests\test_grade_correctness.py:170(d1_cell)` |

#### Breakdown & Concrete Remediation
- **Fixture Creation (`d1_cell`):** 2.155 s (20.1% of test time).
- **Grader Logic (`drift.grade_cell`):** 6.058 s (56.5% of test time).
  - Inside `grade_cell`, `_changes.change_set` takes **4.968 s (46.3%)**, of which **4.911 s (45.8%)** is spent in `_digest` executing 1,066 file reads and SHA-256 hashes.
- **Archive Immutability (`tree_digest`):** 2.505 s (23.4% of test time), executing 1,680 `read_bytes` calls taking 2.411 s.
- **Concrete Remediation:**
  - **Cached Change Set / Pre-Turn Digest (Verified: measured):** Pre-turn digest caching eliminates 50% of `_digest` calls (**saves ~2.5 s**).
  - **Git Diff Seam for Clean Trees (Inferred):** For git repositories, `git status --porcelain` or `git diff --name-only` identifies changed paths in ~0.02 s, avoiding the full recursive filesystem walk of 1,066 files entirely.

---

### 1.3 Mutation Grader Representative
- **Test:** `tests/test_grade_mutation.py::test_no_tests_written_when_only_source_changed_is_na`
- **Total Execution Time:** **10.470 s** (100.0%)
- **Test Intent:** Asserts that a cell where only source files changed (and no test files were written) receives NA for mutation score without launching Stryker.NET.

#### Top 10 Cumulative Functions
| # | Cumulative | Share | Self Time | Calls | Function |
| ---: | ---: | ---: | ---: | ---: | --- |
| 1 | 8.301 s | 79.3% | 0.000 s | 1 | `tests\test_grade_mutation.py:69(grade_d1)` |
| 2 | 6.855 s | 65.5% | 6.854 s | 3341 | `~:0(<built-in method _io.open>)` |
| 3 | 6.776 s | 64.7% | 0.002 s | 2781 | `C:\Users\malla\AppData\Roaming\uv\python\cpython-3.14-windows-x86_64-none\Lib\pathlib\__init__.py:763(open)` |
| 4 | 5.787 s | 55.3% | 0.001 s | 1 | `src\harness_bench\grade\mutation.py:111(grade_cell)` |
| 5 | 4.976 s | 47.5% | 0.003 s | 1 | `src\harness_bench\grade\_changes.py:110(change_set)` |
| 6 | 4.918 s | 47.0% | 0.013 s | 1062 | `src\harness_bench\grade\_changes.py:94(_digest)` |
| 7 | 2.508 s | 24.0% | 0.006 s | 2 | `tests\test_grade_correctness.py:39(tree_digest)` |
| 8 | 2.415 s | 23.1% | 0.003 s | 1663 | `C:\Users\malla\AppData\Roaming\uv\python\cpython-3.14-windows-x86_64-none\Lib\pathlib\__init__.py:773(read_bytes)` |
| 9 | 2.169 s | 20.7% | 0.000 s | 1 | `tests\test_grade_correctness.py:170(d1_cell)` |
| 10 | 1.955 s | 18.7% | 0.000 s | 1 | `tests\test_grade_correctness.py:133(_build_d1_cache)` |

#### Breakdown & Concrete Remediation
- **Fixture Creation (`d1_cell`):** 2.169 s (20.7% of test time).
- **Grader Logic (`mutation.grade_cell`):** 5.787 s (55.3% of test time).
  - Inside `grade_cell`, `_changes.change_set` takes **4.976 s (47.5%)**, of which **4.918 s (47.0%)** is spent in `_digest` across 1,062 files.
- **Archive Immutability (`tree_digest`):** 2.508 s (24.0% of test time).
- **Concrete Remediation:**
  - **Synthetic Test File Tree (Verified: measured):** This test solely verifies that if changed files do not include tests, the grader returns NA. It does not require building or hashing the 1,062 files of AiDe.Core. Running on a 2-file synthetic workspace cuts execution to <0.05 s (**saves 10.4 s**).

---

## 2. Separation of One-Time Proofs from Continuous Checks

### 2.1 Criteria for Classification
- **Continuous Check:** A test that exercises code paths, business logic, boundary conditions, CLI parameters, or error dispositions that can regress when a developer or agent modifies the codebase. Must run in normal CI rings.
- **One-Time Proof:** A test whose inputs are frozen benchmark artifacts (e.g. historical gate runs such as `row15-d1-1` or `a1-capture-1`, characterization of a committed frozen archive, or determinism proofs re-grading frozen inputs twice). Because the inputs and expected outputs are immutable, re-evaluating these on every commit does not guard against regression; their integrity is governed by catalog freeze gates.

### 2.2 Gate Equivalence via `tools/check_regrade.py`
`tools/check_regrade.py` is the designated repository gate for byte-identity and regrade fidelity, enforcing 7 criteria across gate runs at catalog freeze:
- **Criterion 1 (Distinct Passes):** Pass A and Pass B are distinct, completed passes.
- **Criterion 2 (Byte Identity):** $E_A == E_B$ (SHA-256 export hash identity across passes).
- **Criterion 3 (Baseline Equivalence):** E03_before == E03_after == the committed baseline (`bench/regrade-baseline-0.3.yaml`).
- **Criterion 4 (Catalog Hash):** Both passes carry the frozen `catalog_hash` (`bench/catalog-freeze.yaml`).
- **Criterion 5 (Non-Vacuity):** Pass A's `pass_at_1` and `partial_credit` match 0.3 values, metric non-NA counts match `tests/fixtures/gate/expected-counts.yaml`, and no reason contains `HB-GRD-` or infrastructure failures.
- **Criterion 6 (Judge Verification):** Gateway per-call records verified.
- **Criterion 7 (Archive Integrity):** `bench verify R` is clean, confirming archive bytes did not move.

### 2.3 Summary of Analyzed Tests
- **Total Tests Analyzed:** 97 (22 slow-ring tests + 75 default-ring tests $>= 5$ s).
- **One-Time Tests:** **6 tests**, totaling **5,176.09 s (86.27 min)**.
  - Slow ring: 3 tests, **5,056.87 s (84.28 min)** (89.1% of the slow ring).
  - Default ring: 3 tests, **119.22 s (1.99 min)**.
- **Continuous Tests:** **91 tests**, totaling **1,260.23 s (21.00 min)**.

### 2.4 Complete Classification Table
| Ring | Duration | Test Identifier | Class | Reason | `check_regrade` Equivalence |
| --- | ---: | --- | --- | --- | --- |
| `slow` | 2.08 s | `tests/test_correctness_dotnet.py::test_dotnet_oracle_runs_in_grading_copy_and_records_version` | `continuous` | Unit / contract tests for the dotnet correctness oracle execution, timeout, TRX parsing, and partial credit. | None (oracle unit tests) |
| `slow` | 0.27 s | `tests/test_correctness_dotnet.py::test_dotnet_oracle_failed_tests_get_partial_credit` | `continuous` | Unit / contract tests for the dotnet correctness oracle execution, timeout, TRX parsing, and partial credit. | None (oracle unit tests) |
| `slow` | 0.38 s | `tests/test_correctness_dotnet.py::test_dotnet_oracle_nonzero_exit_is_not_a_pass_with_all_tests_passing` | `continuous` | Unit / contract tests for the dotnet correctness oracle execution, timeout, TRX parsing, and partial credit. | None (oracle unit tests) |
| `slow` | 0.26 s | `tests/test_correctness_dotnet.py::test_dotnet_oracle_reads_named_trx_beside_nested_project` | `continuous` | Unit / contract tests for the dotnet correctness oracle execution, timeout, TRX parsing, and partial credit. | None (oracle unit tests) |
| `slow` | 0.27 s | `tests/test_correctness_dotnet.py::test_dotnet_oracle_does_not_read_stale_trx_from_archive` | `continuous` | Unit / contract tests for the dotnet correctness oracle execution, timeout, TRX parsing, and partial credit. | None (oracle unit tests) |
| `slow` | 0.31 s | `tests/test_correctness_dotnet.py::test_dotnet_oracle_multiple_named_trx_files_are_na` | `continuous` | Unit / contract tests for the dotnet correctness oracle execution, timeout, TRX parsing, and partial credit. | None (oracle unit tests) |
| `slow` | 0.28 s | `tests/test_correctness_dotnet.py::test_dotnet_oracle_missing_or_invalid_named_summary_is_na[missing-named TRX result file missing]` | `continuous` | Unit / contract tests for the dotnet correctness oracle execution, timeout, TRX parsing, and partial credit. | None (oracle unit tests) |
| `slow` | 0.28 s | `tests/test_correctness_dotnet.py::test_dotnet_oracle_missing_or_invalid_named_summary_is_na[malformed-named TRX result is unparsable]` | `continuous` | Unit / contract tests for the dotnet correctness oracle execution, timeout, TRX parsing, and partial credit. | None (oracle unit tests) |
| `slow` | 0.30 s | `tests/test_correctness_dotnet.py::test_dotnet_oracle_missing_or_invalid_named_summary_is_na[zero-no hidden test ran]` | `continuous` | Unit / contract tests for the dotnet correctness oracle execution, timeout, TRX parsing, and partial credit. | None (oracle unit tests) |
| `slow` | 0.20 s | `tests/test_correctness_dotnet.py::test_dotnet_oracle_missing_or_invalid_named_summary_is_na[wrong-file-named TRX result file missing]` | `continuous` | Unit / contract tests for the dotnet correctness oracle execution, timeout, TRX parsing, and partial credit. | None (oracle unit tests) |
| `slow` | 2.03 s | `tests/test_correctness_dotnet.py::test_dotnet_oracle_timeout_is_na_and_leaves_no_process` | `continuous` | Unit / contract tests for the dotnet correctness oracle execution, timeout, TRX parsing, and partial credit. | None (oracle unit tests) |
| `slow` | 1788.99 s | `tests/test_grade_correctness.py::test_the_moved_grader_gives_the_gate_runs_0_3_correctness_and_leaves_the_archive_unchanged[row15-d1-1]` | `one-time` | Re-grades frozen gate run (row15-d1-1) against 0.3 correctness baseline. | Criterion 3 (E03_before == E03_after baseline) and Criterion 5 (pass_at_1/partial_credit equal 0.3) |
| `slow` | 15.23 s | `tests/test_grade_correctness.py::test_d1_base_plus_a_file_with_a_syntax_error_scores_0_not_na` | `continuous` | Synthetic syntax error test verifying correctness grader handles compilation errors without crashing. | None (synthetic mutant verification) |
| `slow` | 19.77 s | `tests/test_grade_correctness.py::test_d1_reference_with_a_member_deleted_that_unchanged_files_use_scores_0` | `continuous` | Synthetic mutant over D1 reference proving correctness grader fails when referenced member is deleted. | None (synthetic mutant verification) |
| `slow` | 421.02 s | `tests/test_grade_correctness.py::test_d1_base_with_one_public_assertion_inverted_has_exactly_1_regression` | `continuous` | Synthetic mutant over D1 base proving behavioral equivalence / differential regression counter catches inverted assertion. | None (synthetic differential regression mutant, not a gate run) |
| `slow` | 7.73 s | `tests/test_grade_correctness.py::test_an_empty_nuget_cache_is_na_restore_never_0` | `continuous` | Verifies offline restore behavior when NuGet cache is missing (infrastructure contract). | None (offline restore guard) |
| `slow` | 53.26 s | `tests/test_grade_mutation.py::test_d1_reference_plus_new_test_project_seed_or_no_compute_scores_zero` | `continuous` | Synthetic seeded fixture test verifying mutation grader handles new test projects / no compute. | None (synthetic mutant verification) |
| `slow` | 50.87 s | `tests/test_grade_mutation.py::test_d1_reference_plus_seed_or_no_compute_one_always_failing_scores_zero` | `continuous` | Synthetic seeded fixture test verifying mutation grader scores zero on always-failing test. | None (synthetic mutant verification) |
| `slow` | 3065.44 s | `tests/test_grade_mutation.py::test_row15_d1_cells_graded_twice_give_characterization_values_and_leave_archives_unchanged` | `one-time` | Grades frozen row15-d1-1 cells twice to prove characterization values and determinism (frozen archive inputs). | Criterion 2 (EA == EB byte-identity across passes) and Criterion 5 (non-vacuity vs expected counts/0.3) |
| `slow` | 36.08 s | `tests/test_grade_rigor.py::test_d1_base_plus_unused_local_gives_static_analysis_delta_plus_1` | `continuous` | Synthetic mutant over D1 base proving rigor static analysis delta detects added diagnostic. | None (synthetic mutant verification) |
| `slow` | 5.37 s | `tests/test_grade_rigor.py::test_d1_syntax_error_is_na_workspace_does_not_build` | `continuous` | Verifies rigor grader reports NA when workspace does not compile. | None (workspace build failure guard) |
| `slow` | 202.44 s | `tests/test_grade_rigor.py::test_the_d1_gate_cells_static_analysis_delta_and_archive_unchanged` | `one-time` | Grades static analysis delta on frozen gate run row15-d1-1 cells. | Criterion 5 (metric non-NA cell counts and values) and Criterion 7 (archive integrity) |
| `default` | 5.24 s | `tests/test_catalog_version.py::test_an_edited_or_removed_freeze_entry_is_red_through_e` | `continuous` | Unit/contract test verifying plan parsing, catalog hash freeze, or telemetry event serialization. | None (core benchmark framework unit test) |
| `default` | 9.53 s | `tests/test_check_regrade.py::test_a_junk_git_index_leaves_the_pre_turn_commit_and_file_hash_map_unchanged` | `continuous` | Tests check_regrade CLI and validation error reporting logic itself. | None (gate harness test) |
| `default` | 10.81 s | `tests/test_engine.py::test_stop_ends_stubborn_trees_within_30s` | `continuous` | Concurrency, subprocess termination, Job Object lifecycle, and timeout enforcement under Windows. | None (engine lifecycle / subprocess control) |
| `default` | 6.54 s | `tests/test_engine.py::test_a_budget_expiring_after_the_turn_ended_is_not_a_timeout` | `continuous` | Concurrency, subprocess termination, Job Object lifecycle, and timeout enforcement under Windows. | None (engine lifecycle / subprocess control) |
| `default` | 6.54 s | `tests/test_engine.py::test_an_unconfirmed_kill_is_logged_once_and_retried_with_capped_backoff` | `continuous` | Concurrency, subprocess termination, Job Object lifecycle, and timeout enforcement under Windows. | None (engine lifecycle / subprocess control) |
| `default` | 9.67 s | `tests/test_engine.py::test_no_decision_after_a_launch_stop` | `continuous` | Concurrency, subprocess termination, Job Object lifecycle, and timeout enforcement under Windows. | None (engine lifecycle / subprocess control) |
| `default` | 10.35 s | `tests/test_grade_architecture.py::test_the_d1_reference_plus_using_newtonsoft_json_is_0` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 9.66 s | `tests/test_grade_architecture.py::test_the_d1_reference_is_1` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 9.83 s | `tests/test_grade_architecture.py::test_every_platform_and_own_layer_form_conforms_and_using_statements_are_not_directives` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 9.70 s | `tests/test_grade_architecture.py::test_a_using_outside_system_and_aide_core_breaks_the_rule[using AiDe.CoreX;\n]` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 9.75 s | `tests/test_grade_architecture.py::test_a_using_outside_system_and_aide_core_breaks_the_rule[using Systemic;\n]` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 10.08 s | `tests/test_grade_architecture.py::test_a_using_outside_system_and_aide_core_breaks_the_rule[using static Newtonsoft.Json.JsonConvert;\n]` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 10.01 s | `tests/test_grade_architecture.py::test_a_using_outside_system_and_aide_core_breaks_the_rule[using J = Newtonsoft.Json;\n]` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 9.81 s | `tests/test_grade_architecture.py::test_a_using_outside_system_and_aide_core_breaks_the_rule[using N = Newtonsoft.Json.Linq.JEnumerable<int>;\n]` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 9.67 s | `tests/test_grade_architecture.py::test_a_using_outside_system_and_aide_core_breaks_the_rule[global using Newtonsoft.Json;\n]` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 9.80 s | `tests/test_grade_architecture.py::test_a_using_outside_system_and_aide_core_breaks_the_rule[using global::Newtonsoft.Json;\n]` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 9.70 s | `tests/test_grade_architecture.py::test_a_using_outside_system_and_aide_core_breaks_the_rule[using System; using Newtonsoft.Json;\n]` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 9.88 s | `tests/test_grade_architecture.py::test_a_using_outside_system_and_aide_core_breaks_the_rule[namespace A {using Newtonsoft.Json;}\n]` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 9.58 s | `tests/test_grade_architecture.py::test_a_using_outside_system_and_aide_core_breaks_the_rule[\ufeffusing Newtonsoft.Json;\n]` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 9.73 s | `tests/test_grade_architecture.py::test_a_projections_file_that_is_not_utf8_is_read_not_raised` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 9.76 s | `tests/test_grade_architecture.py::test_a_changed_projections_file_is_read_whole` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 9.76 s | `tests/test_grade_architecture.py::test_no_file_in_the_rule_scope_is_na_no_source_file_changed[overlay0]` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 9.88 s | `tests/test_grade_architecture.py::test_no_file_in_the_rule_scope_is_na_no_source_file_changed[overlay1]` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 9.79 s | `tests/test_grade_architecture.py::test_no_file_in_the_rule_scope_is_na_no_source_file_changed[overlay2]` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 9.70 s | `tests/test_grade_architecture.py::test_no_file_in_the_rule_scope_is_na_no_source_file_changed[overlay3]` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 9.69 s | `tests/test_grade_architecture.py::test_a_deleted_projections_file_is_not_read` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 10.11 s | `tests/test_grade_architecture.py::test_the_pack_commit_is_not_a_change` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 9.55 s | `tests/test_grade_architecture.py::test_the_value_is_rules_passed_over_rules_with_files_in_scope` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 7.32 s | `tests/test_grade_architecture.py::test_architecture_is_registered_and_writes_its_log_as_evidence` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 57.44 s | `tests/test_grade_architecture.py::test_the_d1_gate_cells_conform_and_the_archive_is_unchanged` | `one-time` | Grades architecture conformance across all frozen row15-d1-1 gate run cells. | Criterion 5 (expected metric values and non-NA cell counts) and Criterion 7 (archive integrity) |
| `default` | 6.70 s | `tests/test_grade_correctness.py::test_the_moved_grader_gives_the_gate_runs_0_3_correctness_and_leaves_the_archive_unchanged[a1-capture-1]` | `one-time` | Re-grades frozen gate run (a1-capture-1) against 0.3 correctness baseline. | Criterion 3 (E03_before == E03_after baseline) and Criterion 5 (pass_at_1/partial_credit equal 0.3) |
| `default` | 10.15 s | `tests/test_grade_correctness.py::test_the_pack_on_base_is_the_pack_commit_so_the_pack_is_not_a_change[None]` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 10.19 s | `tests/test_grade_correctness.py::test_the_pack_on_base_is_the_pack_commit_so_the_pack_is_not_a_change[Add evidence census projection]` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 9.98 s | `tests/test_grade_correctness.py::test_a_pack_off_cell_takes_the_root_even_when_its_second_commit_looks_like_a_pack` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 10.03 s | `tests/test_grade_correctness.py::test_a_later_look_alike_pack_commit_is_ignored` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 9.84 s | `tests/test_grade_correctness.py::test_a_crlf_only_difference_and_a_deletion_are_read_by_content` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 9.99 s | `tests/test_grade_drift.py::test_a_3_line_edit_outside_the_blast_radius_is_scope_creep_3_in_1_file` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 11.51 s | `tests/test_grade_drift.py::test_a_pack_commit_stand_in_outside_the_blast_radius_is_not_scope_creep` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 10.52 s | `tests/test_grade_drift.py::test_a_block_scoped_namespace_in_a_10_line_file_is_convention_drift_10` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 10.20 s | `tests/test_grade_drift.py::test_the_unmeasured_drift_metrics_are_na_with_the_design_reasons` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 9.88 s | `tests/test_grade_drift.py::test_a_cell_that_changed_nothing_is_0_and_convention_drift_no_lines_changed` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 10.15 s | `tests/test_grade_drift.py::test_only_lines_of_the_rules_file_type_are_the_convention_denominator` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 9.99 s | `tests/test_grade_drift.py::test_a_changed_line_counts_twice_a_deleted_file_counts_every_line_and_crlf_counts_nothing` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 10.02 s | `tests/test_grade_drift.py::test_a_block_namespace_on_a_first_line_after_a_utf8_bom_is_a_violation` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 9.94 s | `tests/test_grade_drift.py::test_an_added_line_that_opens_a_block_namespace_is_a_violation_and_a_file_scoped_one_is_not` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 7.63 s | `tests/test_grade_drift.py::test_a_git_timeout_is_na_hb_grd_002[check-ignore]` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 7.50 s | `tests/test_grade_drift.py::test_drift_is_registered_and_returns_only_the_applicable_metrics_with_its_log_as_evidence` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 10.40 s | `tests/test_grade_drift.py::test_an_untracked_file_the_pre_turn_ignore_rules_name_is_not_scope_creep` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 10.81 s | `tests/test_grade_drift.py::test_more_ignored_files_than_one_check_ignore_call_takes_are_all_asked` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 10.31 s | `tests/test_grade_drift.py::test_the_cells_own_ignore_rule_hides_nothing_and_a_tracked_file_under_a_pre_turn_rule_still_counts` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 55.08 s | `tests/test_grade_drift.py::test_the_d1_gate_cells_have_no_scope_creep_and_the_archive_is_unchanged` | `one-time` | Grades drift/scope creep across all frozen row15-d1-1 gate run cells. | Criterion 5 (expected metric values and non-NA cell counts) and Criterion 7 (archive integrity) |
| `default` | 7.72 s | `tests/test_grade_mutation.py::test_mutation_score_computed_from_stryker_report_fixture` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 7.57 s | `tests/test_grade_mutation.py::test_mutation_score_with_timeout_and_no_coverage` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 11.65 s | `tests/test_grade_mutation.py::test_no_tests_written_when_only_source_changed_is_na` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 10.79 s | `tests/test_grade_mutation.py::test_no_tests_written_when_nothing_changed_is_na` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 10.70 s | `tests/test_grade_mutation.py::test_no_non_test_source_changed_is_na` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 11.40 s | `tests/test_grade_mutation.py::test_no_mutants_generated_is_na` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 10.69 s | `tests/test_grade_mutation.py::test_mutation_tool_not_available_is_na` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 10.39 s | `tests/test_grade_mutation.py::test_mutation_run_failed_is_na` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 10.44 s | `tests/test_grade_mutation.py::test_mutation_timeout_is_na` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 7.90 s | `tests/test_grade_mutation.py::test_stryker_config_json_pinned_timeout_and_command_args` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 8.07 s | `tests/test_grade_mutation.py::test_initial_failing_tests_parsed_from_stryker_warning` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 8.06 s | `tests/test_grade_mutation.py::test_initial_failing_tests_not_recorded_when_the_line_is_absent` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 7.99 s | `tests/test_grade_mutation.py::test_mutation_filters_metrics_when_requested` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 5.20 s | `tests/test_grade_rigor.py::test_pre_turn_tree_does_not_build_is_na` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 5.51 s | `tests/test_grade_rigor.py::test_rigor_na_by_design_metrics_give_the_designs_reasons_verbatim[verification_before_done-test runs not identifiable in the tool record (no command text extracted)]` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 5.45 s | `tests/test_grade_rigor.py::test_rigor_na_by_design_metrics_give_the_designs_reasons_verbatim[test_quality-mechanical rung is mutation_score (not counted twice); no rubric for this task]` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 5.25 s | `tests/test_grade_rigor.py::test_rigor_na_by_design_metrics_give_the_designs_reasons_verbatim[maintainability-no maintainability tool pinned in this catalog version]` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 5.37 s | `tests/test_grade_rigor.py::test_rigor_na_by_design_metrics_give_the_designs_reasons_verbatim[style_conformance-no task-defined style rules (a root .editorconfig exists only in pack-on trees: a treatment); no rubric for this task]` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 5.51 s | `tests/test_grade_rigor.py::test_static_analysis_delta_positive` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 5.36 s | `tests/test_grade_rigor.py::test_static_analysis_delta_can_be_negative` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 5.30 s | `tests/test_grade_rigor.py::test_warnings_accumulated_across_all_projects` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 5.04 s | `tests/test_grade_rigor.py::test_no_csproj_in_working_copy_is_na_workspace_does_not_build` | `continuous` | Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays. | None (unit test of grader logic against synthetic changes) |
| `default` | 7.39 s | `tests/test_plan.py::test_pinned_copilot_instruction_list_repeats_for_both_real_working_copies` | `continuous` | Unit/contract test verifying plan parsing, catalog hash freeze, or telemetry event serialization. | None (core benchmark framework unit test) |
| `default` | 5.00 s | `tests/test_telemetry.py::test_fuzzed_records_never_crash_either_reader_and_stay_typed` | `continuous` | Unit/contract test verifying plan parsing, catalog hash freeze, or telemetry event serialization. | None (core benchmark framework unit test) |

---

## 3. Redundancy Analysis Across the Mutation Kill Matrix

Analysis of all 44 mutation specification files in `tests/mutations/*.json` (1,046 total mutants) against the complete test suite (1,814 tests across default and slow rings).

### 3.1 Overall Statistics
- **Total Suite Tests:** 1,814 tests
- **Total Mutants in Register:** 1,046 mutants across 44 files
- **Tests Referenced by $>= 1$ Mutant:** **1,121 tests (61.8%)**
- **Tests Referenced by NO Mutant (Ceremony Candidates):** **693 tests (38.2%)**
- **Consolidation Groups (Identical Mutant Kill Signatures):** **106 groups covering 489 tests**

---

### 3.2 Tests Named by No Mutant (Ceremony Candidates)

#### Breakdown of Unreferenced Tests by Module
| Test File | Unreferenced Tests | Total Tests in File | Unref Runtime | Category / Reason |
| --- | ---: | ---: | ---: | --- |
| `tests/test_views.py` | 56 | 145 | 16.54 s | Secondary projection formatting, CLI flag combinations |
| `tests/test_engine.py` | 51 | 179 | 40.90 s | Concurrency race condition variations, Job Object shutdown retries |
| `tests/test_driver.py` | 43 | 64 | 12.40 s | Telemetry event edge cases and surrogate handling |
| `tests/test_mutate_check.py` | 34 | 36 | 1.85 s | Meta-tests for the mutation checker itself (no self-mutation file) |
| `tests/test_telemetry_copilot.py`| 33 | 68 | 0.19 s | Sub-agent event variations and timestamp ordering |
| `tests/test_scripted_user.py` | 30 | 91 | 0.11 s | Question string encoding variations, lone surrogate tests |
| `tests/test_grade.py` | 29 | 60 | 8.82 s | Legacy unittest output parsing variants |
| `tests/test_report.py` | 28 | 59 | 5.94 s | Markdown table formatting and column wrapping |
| `tests/test_telemetry.py` | 27 | 56 | 5.06 s | Fuzzed record schema validation |
| `tests/test_heredoc_guard.py` | 24 | 24 | 1.37 s | CI architecture control guard (meta-test, no mutation file) |
| `tests/test_plan.py` | 24 | 43 | 7.70 s | Plan validation edge cases |
| `tests/test_profiles.py` | 23 | 41 | 0.99 s | Harness profile environment mapping |
| `tests/test_errors.py` | 22 | 23 | 0.00 s | Error code string registration checks |
| `tests/test_workspace.py` | 14 | 26 | 9.58 s | Directory collision and temp folder cleanup |
| `tests/test_acp_record.py` | 13 | 13 | 1.97 s | Driver process record serialization (no mutation file) |

#### Unreferenced Tests Among Slow Tests ($>= 5$ s)
| Ring | Duration | Test Identifier | Architectural Purpose / Why Unreferenced |
| --- | ---: | --- | --- |
| `slow` | 3065.44 s | `tests/test_grade_mutation.py::test_row15_d1_cells_graded_twice...` | One-time characterization proof over frozen archive |
| `slow` | 1788.99 s | `tests/test_grade_correctness.py::test_the_moved_grader...[row15-d1-1]` | One-time 0.3 correctness baseline replay |
| `slow` | 421.02 s | `tests/test_grade_correctness.py::test_d1_base_with_one_public_assertion_inverted...` | Differential regression test running 2,681 C# tests |
| `slow` | 202.44 s | `tests/test_grade_rigor.py::test_the_d1_gate_cells_static_analysis_delta...` | One-time static analysis delta replay |
| `slow` | 53.26 s | `tests/test_grade_mutation.py::test_d1_reference_plus_new_test_project_seed...` | Synthetic mutant fixture; not targeted by python mutants |
| `slow` | 50.87 s | `tests/test_grade_mutation.py::test_d1_reference_plus_seed_or_no_compute...` | Synthetic mutant fixture; not targeted by python mutants |
| `slow` | 36.08 s | `tests/test_grade_rigor.py::test_d1_base_plus_unused_local...` | Synthetic compiler warning test |
| `slow` | 19.77 s | `tests/test_grade_correctness.py::test_d1_reference_with_a_member_deleted...` | Synthetic broken reference test |
| `slow` | 5.37 s | `tests/test_grade_rigor.py::test_d1_syntax_error_is_na_workspace_does_not_build` | Syntax error NA disposition test |
| `default`| 57.44 s | `tests/test_grade_architecture.py::test_the_d1_gate_cells_conform...` | One-time frozen gate run architecture check |
| `default`| 55.08 s | `tests/test_grade_drift.py::test_the_d1_gate_cells_have_no_scope_creep...` | One-time frozen gate run drift check |
| `default`| 10.79 s | `tests/test_grade_mutation.py::test_no_tests_written_when_nothing_changed_is_na` | NA disposition edge case |
| `default`| 9.53 s | `tests/test_check_regrade.py::test_a_junk_git_index_leaves_pre_turn_unchanged` | Gate robustness check against git index corruption |
| `default`| 8.07 s | `tests/test_grade_mutation.py::test_initial_failing_tests_parsed_from_stryker_warning` | Warning parser edge case |
| `default`| 7.72 s | `tests/test_grade_mutation.py::test_mutation_score_computed_from_stryker_report_fixture`| Pre-computed JSON report parser test |
| `default`| 7.39 s | `tests/test_plan.py::test_pinned_copilot_instruction_list_repeats...` | Plan instruction validator |
| `default`| 6.70 s | `tests/test_grade_correctness.py::test_the_moved_grader...[a1-capture-1]` | One-time gate run check over a1-capture-1 |
| `default`| 5.00 s | `tests/test_telemetry.py::test_fuzzed_records_never_crash_either_reader...` | Fuzz/robustness test for telemetry parsers |

#### Decision Standard: What Decides Whether an Unreferenced Test Earns Its Place
Under Testing Strategy Prime Directive 1 and the CI-OPT mandate (*"a test earns its place by a failure only it catches"*):
1. **Structural Controls vs Unit Tests:** Tests like `test_heredoc_guard.py` (pipefail/heredoc prevention), `test_catalog_version.py` (hash freeze), and `test_check_regrade.py` earn their place as **architectural invariants**, even though they target no product mutation file. They should remain in Ring 0.
2. **Authoring Targeted Mutants:** For unreferenced tests in core domain modules (`views.py`, `engine.py`, `driver.py`), authoring 1-2 targeted mutants in the relevant JSON file will determine whether the test catches an otherwise unkilled bug.
3. **Pruning Genuine Ceremony:** If an unreferenced test verifies defensive formatting, duplicate string representations, or trivial parameter passing that is already exercised by another test, it is a candidate for consolidation or deletion.

---

### 3.3 Groups of Tests Named for Exactly the Same Mutants (Consolidation Candidates)

106 consolidation groups covering 489 tests kill identical sets of mutants. Selected high-impact groups:

#### Group 1: Architecture Rule Usings Directive Variations
- **Tests (10 parametrized cases, 97.99 s total in default ring):**
  - `tests/test_grade_architecture.py::test_a_using_outside_system_and_aide_core_breaks_the_rule[using AiDe.CoreX;\n]` (9.70 s)
  - `tests/test_grade_architecture.py::test_a_using_outside_system_and_aide_core_breaks_the_rule[using Systemic;\n]` (9.75 s)
  - `tests/test_grade_architecture.py::test_a_using_outside_system_and_aide_core_breaks_the_rule[using static Newtonsoft.Json.JsonConvert;\n]` (10.08 s)
  - `tests/test_grade_architecture.py::test_a_using_outside_system_and_aide_core_breaks_the_rule[using J = Newtonsoft.Json;\n]` (10.01 s)
  - `tests/test_grade_architecture.py::test_a_using_outside_system_and_aide_core_breaks_the_rule[using N = Newtonsoft.Json.Linq.JEnumerable<int>;\n]` (9.81 s)
  - `tests/test_grade_architecture.py::test_a_using_outside_system_and_aide_core_breaks_the_rule[using global::Newtonsoft.Json;\n]` (9.80 s)
  - `tests/test_grade_architecture.py::test_a_using_outside_system_and_aide_core_breaks_the_rule[using System; using Newtonsoft.Json;\n]` (9.70 s)
  - `tests/test_grade_architecture.py::test_a_using_outside_system_and_aide_core_breaks_the_rule[namespace A {using Newtonsoft.Json;}\n]` (9.88 s)
  - `tests/test_grade_architecture.py::test_a_using_outside_system_and_aide_core_breaks_the_rule[﻿using Newtonsoft.Json;\n]` (9.58 s)
  - `tests/test_grade_architecture.py::test_a_using_outside_system_and_aide_core_breaks_the_rule[global using Newtonsoft.Json;\n]` (9.67 s)
- **Mutants Killed (8 mutants in `tests/mutations/architecture_grader.json`):**
  - All 10 cases kill the exact same 8 mutants (covering `_cs_breaks` regex matching and token splitting).
- **Consolidation Opportunity:** Each of the 10 cases creates a full D1 repository, hashes 1,062 files, and runs tree_digest twice. Consolidating the regex string parsing into direct unit tests over `_cs_breaks` (taking <0.001 s) and retaining 1 integration test over `d1_cell` preserves 100% of mutation kills while saving **~88 seconds in the default ring**.

#### Group 2: Architecture Unchanged Scope Cases
- **Tests (4 parametrized cases, 39.13 s total in default ring):**
  - `tests/test_grade_architecture.py::test_no_file_in_the_rule_scope_is_na_no_source_file_changed[overlay0..3]` (~9.8 s each).
- **Mutants Killed (2 mutants):** Both mutants are killed equally by all 4 cases.
- **Consolidation Opportunity:** Retaining 1 representative case saves **~29 seconds**.

#### Group 3: Rigor NA Metric Reason Formatting
- **Tests (4 parametrized cases, 21.58 s total in default ring):**
  - `tests/test_grade_rigor.py::test_rigor_na_by_design_metrics_give_the_designs_reasons_verbatim[...]` (4 cases, ~5.4 s each).
- **Mutants Killed (1 mutant):** String mapping for NA reasons.
- **Consolidation Opportunity:** Testing the static reason dictionary directly saves **~16 seconds**.

#### Group 4: Egress Transformation Variants
- **Tests (31 parametrized cases, 0.03 s total):**
  - `tests/test_egress.py::test_a_transformed_sensitive_value_is_withheld_and_never_reaches_the_backend[...]`
- **Mutants Killed (21 mutants).** These tests are sub-millisecond in-memory tests. No runtime optimization needed; they serve as boundary property tests.

---

## 4. Ranked List of Proposed Changes

| Rank | Proposed Change | Default Ring Savings | Slow Ring Savings | CI Run Savings (Windows 2x) | Coverage Kept / Lost | Where Property is Still Proven |
| :---: | --- | :---: | :---: | :---: | --- | --- |
| **1** | **Decouple One-Time Frozen Gate Runs from `pytest` Rings**<br>Move the 6 frozen gate tests (`row15-d1-1` and `a1-capture-1`) out of `pytest` into `tools/check_regrade.py`. | **1.99 min**<br>(119 s) | **84.28 min**<br>(5,057 s) | **3.98 min**<br>(billable) | **Keeps 100%**.<br>Loses 0%. | Fully proven by `tools/check_regrade.py` (Criteria 1–5, 7) at each catalog freeze. |
| **2** | **Pre-Turn Digest Caching & Lightweight Fixture Immutability**<br>Cache base tree file digests in `_changes.change_set` and bypass double `tree_digest` re-reads in unit tests. | **5.72 min**<br>(343 s) | **0.75 min**<br>(45 s) | **11.44 min**<br>(billable) | **Keeps 100%**.<br>Loses 0%. | Pure refactoring of test infrastructure; identical inputs, rules, and scores evaluated. |
| **3** | **Target Public Suite in Inverted-Assertion Regression Test**<br>Filter `dotnet test` to the 1 regressing method (`Utf8Content_SurvivesIntact`) instead of running all 2,681 tests twice. | **0.00 min** | **6.97 min**<br>(418 s) | **0.00 min**<br>(not in CI default) | **Keeps 100%**.<br>Loses 0%. | Real dotnet invocation, Job Object containment, TRX logging, and regression count still verified. |
| **4** | **Fast-Path String Unit Tests for Grader Syntax / Usings Rules**<br>Test `_cs_breaks` regexes directly on string inputs; keep 1 full `d1_cell` integration test. | **2.22 min**<br>(133 s) | **0.00 min** | **4.44 min**<br>(billable) | **Keeps 100%**.<br>Loses 0%. | All 8 mutants in `architecture_grader.json` remain killed; pure-function logic tested directly. |
| **5** | **Consolidate Redundant Multi-Test Mutation Killer Groups**<br>Prune duplicate tests in identical-killer groups (e.g. `test_rigor_na_by_design_metrics`). | **0.75 min**<br>(45 s) | **0.00 min** | **1.50 min**<br>(billable) | **Keeps 100%**.<br>Loses 0%. | Mutation kill matrix proves that identical failure signals are preserved. |
| **Total** | **Combined Remediation Impact** | **~10.68 min**<br>(~53% cut) | **~92.00 min**<br>(~97% cut) | **~21.36 min**<br>(per CI push) | **Zero Loss** | **Gate criteria, unit tests, and mutation kills fully intact.** |

---

## 5. Analysis Scripts and Commands Used

All analysis scripts are committed under `tools/ci_opt/` and conform to repository standards:

1. `tools/ci_opt/profile_graders.py`:
   - *Docstring:* `"""Profile representative default-ring grader tests with cProfile and report cumulative function shares."""`
   - *Usage:* `uv run python tools/ci_opt/profile_graders.py`
2. `tools/ci_opt/classify_tests.py`:
   - *Docstring:* `"""Classify slow-ring tests and default-ring tests >= 5s as continuous or one-time."""`
   - *Usage:* `uv run python tools/ci_opt/classify_tests.py`
3. `tools/ci_opt/mutation_redundancy.py`:
   - *Docstring:* `"""Analyze mutation killer coverage, unreferenced ceremony tests, and consolidation groups."""`
   - *Usage:* `uv run python tools/ci_opt/mutation_redundancy.py`

### Linter Verification
Verified via `uv run ruff check src tests tools`: clean, 0 warnings, 0 errors.

---

## Test Architect review (2026-09-27, Adversary Mode, claude-fable-5-1)

**Verdict:** PASS WITH CONDITIONS as a plan. Ranks 3 and 5 are blocked as written. The veto clears per item only when that item's named red observation is in its merge.

- **Rank 1: approve with conditions.** "Zero loss" is false (Verified).
  - `check_regrade` criterion 5 pins counts, and criterion 2 pins identity within one run.
  - The exact gate values live only in `GATE_D1_MUTATION`, the `D1_GATE` tables (rigor, architecture, drift) and `GATE_C2`.
  - The home for these tests is a `gate` pytest marker, excluded from `slow`, with the tests kept unchanged, plus a digest stamp:
    - `tests/fixtures/gate/gate-stamp.yaml` holds a sha256 over `src/harness_bench/grade/**/*.py`, the D1 task version hash, `bench/metrics.yaml`, the pinned tool versions and `bench/regrade-baseline-0.3.yaml`.
    - A fast default-ring test asserts that the current digest equals the stamp.
    - `tools/gate_stamp.py --renew` writes the stamp only after `pytest -m gate` exits 0.
  - Red first: one changed byte in `architecture.py` fails the stamp test. A renew without the ring is impossible by construction.
  - The gate tests skip on CI (`runs/` is git-ignored), so the saving is the Leader's slow ring (84 min), not CI minutes.
- **Rank 2: approve with conditions.**
  - **2b, test-only:** unit tests replace the two `tree_digest` calls with a stat snapshot `{relpath: (size, mtime_ns)}` including the path set.
    - The content `tree_digest` stays in the six gate tests and in one "archive unchanged" test per grader.
    - A structural test asserts that no grader module uses `os.utime`.
    - Red first: a grader that writes a `.pyc` under the archive fails the snapshot.
  - **2a, product:** the pre-turn digest cache is keyed by `git rev-parse <commit>^{tree}` plus the digest algorithm tag, and is process-scoped and bounded.
    - A differential test shows cached equals uncached on CRLF, BOM, symlink and binary fixtures.
    - An isolation test shows two cells with different tree shas never share an entry, and kills the mutant "drop the tree sha from the key".
- **Rank 3: blocked.** Filtering `dotnet test` to one method makes "exactly 1 regression" true by construction and needs a product seam. The full-suite differential is the only proof of "exactly 1, and no collateral". It is not CI-billable.
- **Rank 4: approve with conditions.**
  - The 10 `using` heads stay as parametrizations of a unit test over one `.cs` file (the BOM case via `write_bytes`) that calls `architecture._cs_breaks`.
  - `test_the_d1_reference_plus_using_newtonsoft_json_is_0` stays as the integration path.
  - The 8 mutants in `architecture_grader.json` are re-pointed, and all must be killed. Nothing is deleted.
- **Rank 5: blocked as written.** Section 3 comes from the killer names in the register, not from a kill matrix. It can prioritise where to author mutants; it cannot justify deleting anything.
  - A group is approved only when each parametrization has a mutant that only it kills, a `mutate_check` run without the candidate leaves the survivor set unchanged, and the group's boundary set is listed.
  - Approved now: the rigor N/A group becomes one grade plus a dict equality over all four `NA_BY_DESIGN` keys.
- **Missed by the proposal:**
  - Defender real-time scanning on `windows-latest`, with I/O at about 2 ms per open. A temp-dir exclusion as a CI step is to be measured once and kept only if it moves the number.
  - A measured `pytest-xdist` trial: `-n 4` on an I/O-bound ring. An order-dependent test under xdist is a defect to fix.
  - After the cuts, lower `timeout-minutes` from 60 to 30.
- **Order:**
  1. Rank 4 plus the rigor-N/A consolidation.
  2. 2b.
  3. The Defender and xdist trials, measured.
  4. 2a.
  5. Rank 1 (can run in parallel with steps 1–4).
  6. Rank 5 per group, mutants first.
  Rank 3 is never done.
- **Residual risk:** the stamp catches grader-source drift but not a silent change in the archived runs themselves; that is covered by `check_regrade` criterion 7 at freeze only.
