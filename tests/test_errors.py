"""The closed failure taxonomy (design: Failure taxonomy; ADR-0007 section 6): one definition of cause -> code -> attribution."""

import re

import pytest

from harness_bench import errors


def test_every_cause_has_a_unique_stable_code():
    codes = [c.code for c in errors.Cause]
    assert len(codes) == len(set(codes))
    assert all(re.fullmatch(r"HB-CELL-\d{3}", c) for c in codes)


def test_attribution_is_from_the_closed_set():
    assert {c.attribution for c in errors.Cause} <= {"agent", "harness", "infrastructure", "benchmark", "none"}


@pytest.mark.parametrize("cause, code, attribution", [
    ("timed_out", "HB-CELL-301", "agent"),
    ("adapter_crash", "HB-CELL-105", "harness"),
    ("provider", "HB-CELL-108", "infrastructure"),
    ("model_unavailable", "HB-CELL-116", "benchmark"),
    ("memory", "HB-CELL-103", "infrastructure"),
    ("unclassified", "HB-CELL-199", "none"),
])
def test_design_table_rows(cause, code, attribution):
    c = errors.Cause[cause]
    assert (c.code, c.attribution) == (code, attribution)


def test_infrastructure_and_benchmark_causes_invalidate_the_cell():
    assert errors.Cause.provider.invalidates
    assert errors.Cause.model_unavailable.invalidates
    assert not errors.Cause.timed_out.invalidates
    assert not errors.Cause.adapter_crash.invalidates


def test_run_level_codes_are_unique_and_named():
    assert len(errors.RUN_CODES) == len(set(errors.RUN_CODES))
    for code in ("HB-PRE-002", "HB-RUN-001", "HB-LED-002", "HB-LED-005", "HB-SEC-001", "HB-USR-001"):
        assert errors.RUN_CODES[code]


def test_bench_error_carries_its_code():
    exc = errors.BenchError("HB-LED-002", "chain break at seq 4")
    assert exc.code == "HB-LED-002"
    assert "HB-LED-002" in str(exc)
    with pytest.raises(ValueError):
        errors.BenchError("HB-NOPE-000", "unknown code")
