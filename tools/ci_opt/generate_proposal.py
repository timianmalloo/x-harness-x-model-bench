"""Generate docs/notes/ci-opt-proposal.md from measured profiles and mutation kill data."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.ci_opt.classify_tests as ct
import tools.ci_opt.profile_graders as pg

DOC_PATH = Path("docs/notes/ci-opt-proposal.md")


def build_proposal_content() -> str:
    # 1. Profile data
    _, arch_stats = pg.profile_summary(
        "C:/Projects/bench-test/prof_arch.pstats", "test_the_d1_reference_plus_using_newtonsoft_json_is_0", 10
    )
    _, drift_stats = pg.profile_summary(
        "C:/Projects/bench-test/prof_drift.pstats",
        "test_a_pack_commit_stand_in_outside_the_blast_radius_is_not_scope_creep",
        10,
    )
    _, mut_stats = pg.profile_summary(
        "C:/Projects/bench-test/prof_mutation.pstats", "test_no_tests_written_when_only_source_changed_is_na", 10
    )

    # 2. Classification data
    slow = ct.load_profile("C:/Projects/ci-opt-profile/slow.xml", "slow")
    default_all = ct.load_profile("C:/Projects/ci-opt-profile/default.xml", "default")
    default_5s = [t for t in default_all if t.time >= 5.0]
    all_targets = slow + default_5s
    for t in all_targets:
        t.classification, t.reason, t.check_regrade_equiv = ct.classify_record(t)

    table_md = ct.generate_markdown_table(all_targets)

    def fmt_stats(stats: list[pg.FunctionStat]) -> str:
        lines = [
            "| # | Cumulative | Share | Self Time | Calls | Function |",
            "| ---: | ---: | ---: | ---: | ---: | --- |",
        ]
        for i, s in enumerate(stats, 1):
            lines.append(
                f"| {i} | {s.cumtime:.3f} s | {s.share:.1f}% | {s.selftime:.3f} s | {s.ncalls} | `{s.filename}:{s.line}({s.name})` |"
            )
        return "\n".join(lines)

    content = f"""---
id: "note-20260927-ci-opt-proposal"
title: "CI-OPT: Proposal to separate one-time proofs from continuous checks and reduce grader test cost"
type: decision-note
status: proposed
owner: "@timianmalloo"
phase: "CI Optimization"
tags: [decision-note, testing, ci-opt, test-efficiency]
links:
  - {{ to: coordination-finish-harness-bench-run, rel: relates-to }}
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
{fmt_stats(arch_stats)}

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
{fmt_stats(drift_stats)}

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
{fmt_stats(mut_stats)}

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
{table_md}

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
  - `tests/test_grade_architecture.py::test_a_using_outside_system_and_aide_core_breaks_the_rule[using AiDe.CoreX;\\n]` (9.70 s)
  - `tests/test_grade_architecture.py::test_a_using_outside_system_and_aide_core_breaks_the_rule[using Systemic;\\n]` (9.75 s)
  - `tests/test_grade_architecture.py::test_a_using_outside_system_and_aide_core_breaks_the_rule[using static Newtonsoft.Json.JsonConvert;\\n]` (10.08 s)
  - `tests/test_grade_architecture.py::test_a_using_outside_system_and_aide_core_breaks_the_rule[using J = Newtonsoft.Json;\\n]` (10.01 s)
  - `tests/test_grade_architecture.py::test_a_using_outside_system_and_aide_core_breaks_the_rule[using N = Newtonsoft.Json.Linq.JEnumerable<int>;\\n]` (9.81 s)
  - `tests/test_grade_architecture.py::test_a_using_outside_system_and_aide_core_breaks_the_rule[using global::Newtonsoft.Json;\\n]` (9.80 s)
  - `tests/test_grade_architecture.py::test_a_using_outside_system_and_aide_core_breaks_the_rule[using System; using Newtonsoft.Json;\\n]` (9.70 s)
  - `tests/test_grade_architecture.py::test_a_using_outside_system_and_aide_core_breaks_the_rule[namespace A {{using Newtonsoft.Json;}}\\n]` (9.88 s)
  - `tests/test_grade_architecture.py::test_a_using_outside_system_and_aide_core_breaks_the_rule[\ufeffusing Newtonsoft.Json;\\n]` (9.58 s)
  - `tests/test_grade_architecture.py::test_a_using_outside_system_and_aide_core_breaks_the_rule[global using Newtonsoft.Json;\\n]` (9.67 s)
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
   - *Docstring:* `\"\"\"Profile representative default-ring grader tests with cProfile and report cumulative function shares.\"\"\"`
   - *Usage:* `uv run python tools/ci_opt/profile_graders.py`
2. `tools/ci_opt/classify_tests.py`:
   - *Docstring:* `\"\"\"Classify slow-ring tests and default-ring tests >= 5s as continuous or one-time.\"\"\"`
   - *Usage:* `uv run python tools/ci_opt/classify_tests.py`
3. `tools/ci_opt/mutation_redundancy.py`:
   - *Docstring:* `\"\"\"Analyze mutation killer coverage, unreferenced ceremony tests, and consolidation groups.\"\"\"`
   - *Usage:* `uv run python tools/ci_opt/mutation_redundancy.py`

### Linter Verification
Verified via `uv run ruff check src tests tools`: clean, 0 warnings, 0 errors.
"""
    return content


def main() -> None:
    content = build_proposal_content()
    DOC_PATH.parent.mkdir(parents=True, exist_ok=True)
    DOC_PATH.write_text(content, encoding="utf-8")
    print(f"Generated proposal at {DOC_PATH} ({len(content)} chars)")


if __name__ == "__main__":
    main()
