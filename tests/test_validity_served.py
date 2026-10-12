"""Served-settings validity (ADR-0024 s4-s5, ADR-0028 s4-s5; R-VALIDITY).

Hand-built `served` rows (the ADR-0026 s1 columns) are judged by `views._served_settings` and `views._validity`; one
test drives them through `_cell_view` over a real graded run, and one shows an old run (no `served` rows) unchanged.
"""

import pytest
from archived_runs import GOOD, make_root, make_run
from test_views import _acp_run, _cell, _edit_plan, _warnings

from harness_bench import profiles, telemetry, views

VALID = ("valid", None)
MISMATCH = ("invalid (setting mismatch)", "HB-VAL-010")
MODEL_MISMATCH = ("invalid (model mismatch)", "HB-VAL-002")


def _row(field, value, source="rec field", not_recorded=None):
    return {"kind": "served_setting", "run_id": "r1", "extraction_id": "x1", "cell_id": "a", "native_session_id": "s",
            "field": field, "value": value, "not_recorded": not_recorded, "source": source}


def _prof(default_context=None, default_effort=None, aliases=None, aux=()):
    settings = {"effort": {"default_serves": default_effort}, "context": {"default_serves": default_context}}
    return {"auxiliary_models": list(aux), "settings": settings, **({"model_aliases": aliases} if aliases else {})}


def _cell_rec(harness, model="m", effort="default", context="default"):
    return {"cell_id": "a", "harness": harness, "model": model, "effort": effort, "context": context}


def _judge(cell, prof, rows, served=frozenset({"m"})):
    """(validity, code) and the HB-VAL-011 warnings, as `_cell_view` composes them."""
    mismatch, unrecorded = views._served_settings(cell, prof, rows)
    model_served = views._model_served(rows)
    got = views._validity(cell, prof, {"outcome": "completed", "cause": None}, "completed", set(served),
                          settings=mismatch, model_served=model_served)
    return got, [(w.code, w.level) for w in unrecorded]


def test_a_copilot_cell_serving_128000_under_default_is_hb_val_010():
    got, _ = _judge(_cell_rec("copilot"), _prof(default_context=272000), [_row("context_tokens", 128000, "acp size")])
    assert got == MISMATCH


def test_the_hb_val_010_message_names_setting_expected_served_and_source():
    mismatch, _ = views._served_settings(_cell_rec("copilot"), _prof(default_context=272000),
                                         [_row("context_tokens", 128000, "acp usage_update.size")])
    assert (mismatch.code, mismatch.level, mismatch.message) == (
        "HB-VAL-010", "error", "context served 128000, expected 272000 (default_serves) from acp usage_update.size")


# Leader ruling (2026-10-12): the Codex reader writes the NOMINAL window (828,400 / 95% = 872,000), the effective value
# and the percent kept in `source`; the view judges it against the pin like every harness and parses no source.
CODEX_SOURCE = "rollout task_started.model_context_window 828400 / models_cache.json effective_context_window_percent 95"


def test_a_codex_cell_at_828400_under_pin_872000_with_catalog_percent_95_is_valid():
    rows = [_row("context_tokens", 872000, CODEX_SOURCE)]
    assert _judge(_cell_rec("codex", context="872000"), _prof(default_context=272000), rows)[0] == VALID


def test_an_effective_codex_window_is_judged_as_written_never_scaled_by_the_source():
    rows = [_row("context_tokens", 828400, "models_cache.json effective_context_window_percent=95")]
    assert _judge(_cell_rec("codex", context="872000"), _prof(), rows)[0] == MISMATCH


def test_a_pinned_effort_with_no_source_is_hb_val_011_a_warning():
    rows = [_row("effort", None, None, "not recorded: no turn_context")]
    got, warnings = _judge(_cell_rec("codex", effort="high"), _prof(), rows)
    assert (got, warnings) == (VALID, [("HB-VAL-011", "warning")])


def test_a_pinned_effort_with_no_row_at_all_is_hb_val_011():
    assert _judge(_cell_rec("codex", effort="high"), _prof(), [])[1] == [("HB-VAL-011", "warning")]


def test_a_served_alias_is_valid_through_the_profile_table():  # Copilot gpt-5.6-sol-fast <-> API gpt-5.6-sol (s5)
    prof = _prof(aliases={"gpt-5.6-sol-fast": ["gpt-5.6-sol"]})
    rows = [_row("model_served", "gpt-5.6-sol-fast")]
    assert _judge(_cell_rec("copilot", model="gpt-5.6-sol-fast"), prof, rows, served={"gpt-5.6-sol"})[0] == VALID


def test_a_served_model_outside_the_exact_alias_table_is_hb_val_002():  # a prefix rule would admit -build-fast
    prof = _prof(aliases={"grok-4.7": ["grok-4.7-build"]})
    rows = [_row("model_served", "grok-4.7-build-fast")]
    assert _judge(_cell_rec("grok", model="grok-4.7"), prof, rows, served={"grok-4.7-build"})[0] == MODEL_MISMATCH


def test_the_alias_also_admits_the_model_calls_model():
    prof = _prof(aliases={"grok-4.7": ["grok-4.7-build"]})
    assert _judge(_cell_rec("grok", model="grok-4.7"), prof, [], served={"grok-4.7-build"})[0] == VALID


def test_agy_context_null_is_not_judged():  # default_serves null: recorded as not recorded, nothing judged
    rows = [_row("context_tokens", None, None, "not recorded: agy records no window")]
    assert _judge(_cell_rec("agy"), _prof(default_context=None), rows) == (VALID, [])


@pytest.mark.parametrize(("tier", "expected"), [("long_context", VALID), (None, MISMATCH)])
def test_a_copilot_p_cell_pinned_922000_is_judged_by_its_served_tier(tier, expected):  # ADR-0028 s5
    rows = [_row("context_tier", tier, "session.start.contextTier"), _row("context_tokens", 272000, "debug log")]
    assert _judge(_cell_rec("copilot", context="922000"), _prof(default_context=272000), rows)[0] == expected


def test_a_copilot_tier_that_no_source_records_is_hb_val_011():
    rows = [_row("context_tier", None, None, "not recorded: no session.start")]
    got, warnings = _judge(_cell_rec("copilot", context="922000"), _prof(default_context=272000), rows)
    assert (got, warnings) == (VALID, [("HB-VAL-011", "warning")])


def test_two_sources_that_disagree_are_hb_val_010():
    rows = [_row("effort", "high", "transcript .effort"), _row("effort", "low", "acp config")]
    mismatch, _ = views._served_settings(_cell_rec("claude-code", effort="high"), _prof(), rows)
    assert _judge(_cell_rec("claude-code", effort="high"), _prof(), rows)[0] == MISMATCH
    assert mismatch.message == "effort served low, expected high (pinned) from acp config"


def test_a_partial_record_with_a_served_mismatch_is_still_invalid():  # measured, so it outranks HB-VAL-003
    mismatch, _ = views._served_settings(_cell_rec("codex", effort="high"), _prof(), [_row("effort", "low")])
    got = views._validity(_cell_rec("codex", effort="high"), _prof(), {"outcome": "completed", "cause": None},
                          "completed", {"m"}, unrecorded="torn", settings=mismatch)
    assert got == MISMATCH


def test_a_plan_without_settings_or_effort_keys_judges_nothing():  # every plan from before bench-matrix/3
    cell = {"cell_id": "a", "harness": "codex", "model": "m"}
    assert views._served_settings(cell, {"auxiliary_models": []}, [_row("effort", "low")]) == (None, [])


# --- through the projection --------------------------------------------------------------------------------------


@pytest.fixture
def root(tmp_path):
    return make_root(tmp_path)


def test_an_old_run_with_no_served_rows_keeps_its_validity_and_export(root, tmp_path, monkeypatch):
    real = profiles.READERS["codex"]  # an old-shape reader: R-READ-CODEX built the served hook, so it is reset here

    def old_shape(path):
        ex = real(path)
        ex.served = telemetry.READER_NOT_BUILT
        return ex

    monkeypatch.setitem(profiles.READERS, "codex", old_shape)
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    from harness_bench.grade import runner
    runner.run_pass(run_dir, root)
    view = views.load(run_dir)
    assert views.rows(run_dir, "served") == []
    cell = _cell(view, "a")
    assert ((cell.validity, cell.validity_code), [w.code for w in cell.warnings if w.code in ("HB-VAL-010", "HB-VAL-011")]) \
        == (VALID, [])


def test_served_rows_of_the_current_extraction_reach_validity(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    from harness_bench.grade import runner
    runner.run_pass(run_dir, root)
    _edit_plan(run_dir, lambda p: {**p, "cells": [{**c, "effort": "high"} for c in p["cells"]]})
    view = views.load(run_dir)
    facts = {fact: views.rows(run_dir, fact) for fact in views.FACTS}
    extraction = _cell(view, "a").extraction_id
    facts["served"] = [{**_row("effort", "low"), "extraction_id": extraction},
                       {**_row("effort", "medium"), "extraction_id": "an-older-pass"}]
    cell = views._cell_view(view.plan, view.plan["cells"][0], facts, view.grading_id)
    assert (cell.validity, cell.validity_code) == MISMATCH
    facts["served"] = []
    cell = views._cell_view(view.plan, view.plan["cells"][0], facts, view.grading_id)
    assert ((cell.validity, cell.validity_code), _warnings(cell, "HB-VAL-011")[0][:2]) == (VALID, ("HB-VAL-011", "warning"))


# --- ADR-0028 s4: a Copilot -p cell with no usage in its final object ---------------------------------------------


def _prompt_mode(p):
    return {**p, "builds": {"copilot": {"version": "1.0.89-1", "sha256": "a" * 64, "adapter_version": "0.1.0",
                                        "adapter_sha256": "b" * 64, "agent_version": None}}}


def test_a_copilot_p_cell_with_no_usage_reads_hb_val_005_not_recorded_never_a_warning(root, tmp_path, monkeypatch):
    import test_views
    original = test_views._copilot_run

    def p_mode_run(*args, **kw):
        run_dir = original(*args, **kw)
        _edit_plan(run_dir, _prompt_mode)
        return run_dir
    monkeypatch.setattr(test_views, "_copilot_run", p_mode_run)
    cell = _acp_run(root, tmp_path, None)
    assert _warnings(cell, "HB-VAL-005") == [
        ("HB-VAL-005", "not recorded", "token cross-check not recorded: the copilot -p final object carries no usage")]


def test_an_acp_copilot_cell_with_no_usage_still_warns(root, tmp_path):  # the R-24 rule for ACP-era cells, unchanged
    cell = _acp_run(root, tmp_path, None)
    assert _warnings(cell, "HB-VAL-005") == [("HB-VAL-005", "warning", "token cross-check not run: no ACP usage recorded")]
