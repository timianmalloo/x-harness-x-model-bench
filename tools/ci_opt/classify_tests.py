"""Classify slow-ring tests and default-ring tests >= 5s as continuous or one-time."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TestRecord:
    ring: str
    classname: str
    name: str
    time: float
    full_id: str
    classification: str = ""
    reason: str = ""
    check_regrade_equiv: str = ""


def load_profile(path: Path | str, ring: str) -> list[TestRecord]:
    tree = ET.parse(path)
    root = tree.getroot()
    records = []
    for tc in root.findall(".//testcase"):
        cls = tc.attrib["classname"]
        name = tc.attrib["name"]
        t = float(tc.attrib.get("time", 0.0))
        file_path = cls.replace(".", "/") + ".py"
        full_id = f"{file_path}::{name}"
        records.append(TestRecord(ring=ring, classname=cls, name=name, time=t, full_id=full_id))
    return records


def classify_record(rec: TestRecord) -> tuple[str, str, str]:
    """Return (classification, reason, check_regrade_criterion)."""
    name = rec.name
    cls = rec.classname

    if "test_the_moved_grader_gives_the_gate_runs_0_3_correctness" in name:
        return (
            "one-time",
            f"Re-grades frozen gate run ({name.partition('[')[2].rstrip(']') or 'gate run'}) against 0.3 correctness baseline.",
            "Criterion 3 (E03_before == E03_after baseline) and Criterion 5 (pass_at_1/partial_credit equal 0.3)",
        )

    # Slow ring tests
    if rec.ring == "slow":
        if "test_row15_d1_cells_graded_twice_give_characterization_values" in name:
            return (
                "one-time",
                "Grades frozen row15-d1-1 cells twice to prove characterization values and determinism (frozen archive inputs).",
                "Criterion 2 (EA == EB byte-identity across passes) and Criterion 5 (non-vacuity vs expected counts/0.3)",
            )
        if "test_the_d1_gate_cells_static_analysis_delta_and_archive_unchanged" in name:
            return (
                "one-time",
                "Grades static analysis delta on frozen gate run row15-d1-1 cells.",
                "Criterion 5 (metric non-NA cell counts and values) and Criterion 7 (archive integrity)",
            )
        if "test_d1_base_with_one_public_assertion_inverted_has_exactly_1_regression" in name:
            return (
                "continuous",
                "Synthetic mutant over D1 base proving behavioral equivalence / differential regression counter catches inverted assertion.",
                "None (synthetic differential regression mutant, not a gate run)",
            )
        if "test_d1_reference_plus_new_test_project_seed" in name:
            return (
                "continuous",
                "Synthetic seeded fixture test verifying mutation grader handles new test projects / no compute.",
                "None (synthetic mutant verification)",
            )
        if "test_d1_reference_plus_seed_or_no_compute_one_always_failing" in name:
            return (
                "continuous",
                "Synthetic seeded fixture test verifying mutation grader scores zero on always-failing test.",
                "None (synthetic mutant verification)",
            )
        if "test_d1_base_plus_unused_local_gives_static_analysis_delta_plus_1" in name:
            return (
                "continuous",
                "Synthetic mutant over D1 base proving rigor static analysis delta detects added diagnostic.",
                "None (synthetic mutant verification)",
            )
        if "test_d1_reference_with_a_member_deleted" in name:
            return (
                "continuous",
                "Synthetic mutant over D1 reference proving correctness grader fails when referenced member is deleted.",
                "None (synthetic mutant verification)",
            )
        if "test_d1_base_plus_a_file_with_a_syntax_error" in name:
            return (
                "continuous",
                "Synthetic syntax error test verifying correctness grader handles compilation errors without crashing.",
                "None (synthetic mutant verification)",
            )
        if "test_an_empty_nuget_cache_is_na" in name:
            return (
                "continuous",
                "Verifies offline restore behavior when NuGet cache is missing (infrastructure contract).",
                "None (offline restore guard)",
            )
        if "test_d1_syntax_error_is_na_workspace_does_not_build" in name:
            return (
                "continuous",
                "Verifies rigor grader reports NA when workspace does not compile.",
                "None (workspace build failure guard)",
            )
        if cls == "tests.test_correctness_dotnet":
            return (
                "continuous",
                "Unit / contract tests for the dotnet correctness oracle execution, timeout, TRX parsing, and partial credit.",
                "None (oracle unit tests)",
            )

    # Default ring tests >= 5s
    # Gate-run checks in default ring (at 7be0860 before CI-OPT slice 1 move)
    if "test_the_d1_gate_cells_conform_and_the_archive_is_unchanged" in name:
        return (
            "one-time",
            "Grades architecture conformance across all frozen row15-d1-1 gate run cells.",
            "Criterion 5 (expected metric values and non-NA cell counts) and Criterion 7 (archive integrity)",
        )
    if "test_the_d1_gate_cells_have_no_scope_creep_and_the_archive_is_unchanged" in name:
        return (
            "one-time",
            "Grades drift/scope creep across all frozen row15-d1-1 gate run cells.",
            "Criterion 5 (expected metric values and non-NA cell counts) and Criterion 7 (archive integrity)",
        )

    # Grader unit tests using D1 fixture
    if cls in (
        "tests.test_grade_architecture",
        "tests.test_grade_drift",
        "tests.test_grade_mutation",
        "tests.test_grade_rigor",
        "tests.test_grade_correctness",
    ):
        return (
            "continuous",
            "Grader unit/contract test verifying rule evaluation, edge cases, NA reasons, or parsing over synthetic overlays.",
            "None (unit test of grader logic against synthetic changes)",
        )

    # Engine / process lifecycle tests
    if cls == "tests.test_engine":
        return (
            "continuous",
            "Concurrency, subprocess termination, Job Object lifecycle, and timeout enforcement under Windows.",
            "None (engine lifecycle / subprocess control)",
        )

    if cls == "tests.test_check_regrade":
        return (
            "continuous",
            "Tests check_regrade CLI and validation error reporting logic itself.",
            "None (gate harness test)",
        )

    if cls in ("tests.test_plan", "tests.test_catalog_version", "tests.test_telemetry"):
        return (
            "continuous",
            "Unit/contract test verifying plan parsing, catalog hash freeze, or telemetry event serialization.",
            "None (core benchmark framework unit test)",
        )

    return ("continuous", "General suite continuous test", "None")


def generate_markdown_table(targets: list[TestRecord]) -> str:
    lines = [
        "| Ring | Duration | Test Identifier | Class | Reason | `check_regrade` Equivalence |",
        "| --- | ---: | --- | --- | --- | --- |",
    ]
    for t in targets:
        lines.append(
            f"| `{t.ring}` | {t.time:.2f} s | `{t.full_id}` | `{t.classification}` | {t.reason} | {t.check_regrade_equiv} |"
        )
    return "\n".join(lines)


def main() -> None:
    slow = load_profile("C:/Projects/ci-opt-profile/slow.xml", "slow")
    default_all = load_profile("C:/Projects/ci-opt-profile/default.xml", "default")
    default_5s = [t for t in default_all if t.time >= 5.0]

    all_targets = slow + default_5s
    for t in all_targets:
        t.classification, t.reason, t.check_regrade_equiv = classify_record(t)

    one_time = [t for t in all_targets if t.classification == "one-time"]
    continuous = [t for t in all_targets if t.classification == "continuous"]

    print(f"Total analyzed: {len(all_targets)} (slow={len(slow)}, default>=5s={len(default_5s)})")
    print(f"One-time: {len(one_time)}, sum={sum(t.time for t in one_time):.2f}s")
    print(f"Continuous: {len(continuous)}, sum={sum(t.time for t in continuous):.2f}s")

    print("\nOne-time tests:")
    for t in one_time:
        print(f"[{t.ring.upper()}] {t.time:7.2f}s | {t.full_id}")
        print(f"  Reason: {t.reason}")
        print(f"  check_regrade equivalence: {t.check_regrade_equiv}")


if __name__ == "__main__":
    import sys
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            try:
                _stream.reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass
    main()
