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
    assert errors.RUN_CODES["HB-VAL-005"] == "warning: model_calls tokens differ from the ACP turn total, or the check did not run"
    assert errors.RUN_CODES["HB-VAL-006"] == "warning: executed-build check skipped (no agent_version, or no recorded self-report)"
    assert errors.RUN_CODES["HB-VAL-007"] == ("validity: build mismatch (the session's agent_version differs from the pinned "
                                              "build's recorded self-report)")  # R-47


def test_the_out_of_profile_codes_are_named():  # R-45 item 2, R-54 (b): one code for each level
    assert errors.RUN_CODES["HB-VAL-008"] == "validity: out-of-profile tool called (a class-other tool call executed)"
    assert errors.RUN_CODES["HB-VAL-009"] == ("warning: out-of-profile attempt refused (the driver counted a permission "
                                              "request, or a native hook denied it)")


def test_the_pre_r2_no_heads_warning_has_its_own_code():  # R-47 c1: one code, one level
    assert errors.RUN_CODES["HB-LED-006"] == ("warning: grading.completed records no heads (written before ruling R-2); "
                                              "only its seals are checked")


def test_the_grader_failure_code_is_named():  # design phase3-graders, F3 (seam S-4)
    assert errors.RUN_CODES.get("HB-GRD-003") == ("grader failed or returned malformed output: its metrics are NA with the "
                                                  "exception type, and the pass continues")


def test_the_incomplete_pass_code_is_named():  # design phase3-graders, GradedOncePerPass (seam S-4)
    assert errors.RUN_CODES.get("HB-GRD-004") == ("grading pass incomplete: a (cell, metric) row is missing, duplicated or "
                                                  "outside the applicable set; the pass is not completed")


def test_run_level_codes_are_unique_and_named():
    assert len(errors.RUN_CODES) == len(set(errors.RUN_CODES))
    for code in ("HB-PRE-002", "HB-RUN-001", "HB-LED-002", "HB-LED-005", "HB-SEC-001", "HB-USR-001"):
        assert errors.RUN_CODES[code]
    for name in ("GEMINI.md", ".github/copilot-instructions.md", ".github/instructions/**/*.instructions.md"):
        assert name in errors.RUN_CODES["HB-PRE-002"]


def test_the_gateway_codes_are_run_codes():  # design phase3-gateway-judges section 17; review w3-gwi-1 A2
    assert {c: t for c, t in errors.RUN_CODES.items() if c.startswith("HB-GW-")} == {
        "HB-GW-001": "judge unavailable: CLI error, timeout, provider error, breaker open, or a store write error "
                     "other than a lost race",
        "HB-GW-002": "invalid output",
        "HB-GW-003": "served model not the pin",
        "HB-GW-004": "blinding scan hit",
        "HB-GW-005": "store entry invalid, or not matched by its storing row",
        "HB-GW-006": "tool event in a judge call",
        "HB-GW-007": "judge not qualified",
        "HB-GW-008": "artifact over the bound or not UTF-8",
        "HB-GW-009": "withheld: sensitive content",
        "HB-GW-010": "leftover credential copy (a verify error)",
        "HB-GW-011": "judge build changed"}


def test_a_held_run_lock_and_a_refused_teardown_have_their_own_codes():  # T1-13
    assert "lock held" in errors.RUN_CODES["HB-RUN-005"]
    assert errors.RUN_CODES["HB-RUN-003"].startswith("teardown refused")


def test_stop_and_spend_cap_have_the_designs_run_codes():  # ERR-1, phase 2 section 4.9
    assert errors.RUN_CODES["HB-RUN-006"] == ("run stopped by the operator (bench stop, or a decision answered stop): "
                                              "running cells stopped, no new launch")
    assert errors.RUN_CODES["HB-RUN-007"] == "spend cap reached: the run stopped (the spend_cap default or answer)"


def test_every_cause_and_run_code_is_a_valid_bench_error_code():  # kills the _ALL_CODES survivors (cosmic-ray)
    for code in [c.code for c in errors.Cause] + list(errors.RUN_CODES):
        assert errors.BenchError(code, "x").code == code


def test_bench_error_carries_its_code():
    exc = errors.BenchError("HB-LED-002", "chain break at seq 4")
    assert exc.code == "HB-LED-002"
    assert "HB-LED-002" in str(exc)
    with pytest.raises(ValueError):
        errors.BenchError("HB-NOPE-000", "unknown code")
