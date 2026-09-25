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
    ("blocked_auth", "HB-CELL-202", "harness"),
])
def test_design_table_rows(cause, code, attribution):
    c = errors.Cause[cause]
    assert (c.code, c.attribution) == (code, attribution)


def test_infrastructure_and_benchmark_causes_invalidate_the_cell():
    assert errors.Cause.provider.invalidates
    assert errors.Cause.model_unavailable.invalidates
    assert not errors.Cause.timed_out.invalidates
    assert not errors.Cause.adapter_crash.invalidates


def test_copilot_set_model_refusal_uses_the_existing_model_unavailable_cause():
    # R-18/R-23: driver classifies the -32602 setter reply by step, not message text.
    cause = errors.Cause.model_unavailable
    assert (cause.code, cause.label, cause.attribution, cause.invalidates) == (
        "HB-CELL-116", "failed (model unavailable)", "benchmark", True
    )


def test_the_wave_two_validity_codes_are_named():  # seam S1 (R-15, R-27)
    assert errors.RUN_CODES["HB-VAL-003"] == "validity: not recorded (the usage record is missing or unreadable)"
    assert errors.RUN_CODES["HB-VAL-004"] == "validity: tools denied by hook"


def test_run_level_codes_are_unique_and_named():
    assert len(errors.RUN_CODES) == len(set(errors.RUN_CODES))
    for code in ("HB-PRE-002", "HB-RUN-001", "HB-LED-002", "HB-LED-005", "HB-SEC-001", "HB-USR-001"):
        assert errors.RUN_CODES[code]
    for name in ("GEMINI.md", ".github/copilot-instructions.md", ".github/instructions/**/*.instructions.md"):
        assert name in errors.RUN_CODES["HB-PRE-002"]


def test_a_held_run_lock_and_a_refused_teardown_have_their_own_codes():  # T1-13
    assert "lock held" in errors.RUN_CODES["HB-RUN-005"]
    assert errors.RUN_CODES["HB-RUN-003"].startswith("teardown refused")


def test_every_cause_and_run_code_is_a_valid_bench_error_code():  # kills the _ALL_CODES survivors (cosmic-ray)
    for code in [c.code for c in errors.Cause] + list(errors.RUN_CODES):
        assert errors.BenchError(code, "x").code == code


def test_bench_error_carries_its_code():
    exc = errors.BenchError("HB-LED-002", "chain break at seq 4")
    assert exc.code == "HB-LED-002"
    assert "HB-LED-002" in str(exc)
    with pytest.raises(ValueError):
        errors.BenchError("HB-NOPE-000", "unknown code")
