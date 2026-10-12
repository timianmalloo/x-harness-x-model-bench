"""The grade-side seams of the lean re-run, pinned before any reader or derivation is built (R-CONTRACT-FACTS).

Designs: ADR-0024 section 4 (ServedSettings, HB-VAL-010/011), ADR-0026 sections 1-2 (the four stream tables, whose
columns are pinned here exactly), ADR-0027 (CostCompare), ADR-0029 sections 1-4 (PackCost), ADR-0025 section 3 (the
HB-CELL blocked code) and ADR-0028 section 7 (the scripted-user refusal). A pass over an old-shape reader writes no
row in the new streams, and a reasoning row edited after sealing fails `bench verify`.
"""

import dataclasses
import inspect
import json
from pathlib import Path

import pytest
import yaml
from archived_runs import GOOD, ROOT, make_root, make_run, pass_rows

from harness_bench import cli, config, profiles, telemetry, views
from harness_bench.errors import RUN_CODES, Cause
from harness_bench.grade import runner
from harness_bench.report import (
    context_growth,
    cost_compare,
    pack_cost,
    publish,
    tool_phases,
)
from harness_bench.telemetry import normalize

PREFIX = ["kind", "run_id", "extraction_id", "cell_id", "native_session_id"]
STREAMS = ("served", "reasoning", "prompt_parts", "harness_events")


def names(cls) -> list[str]:
    return [f.name for f in dataclasses.fields(cls)]


# --- errors.py: the new codes (ADR-0024 s3-s4, ADR-0025 s3 and s5, ADR-0028 s7) ---------------------------------

def test_the_served_validity_codes_are_named():
    assert RUN_CODES["HB-VAL-010"].startswith("validity: served setting differs from the expected value")
    assert RUN_CODES["HB-VAL-011"].startswith("warning: served setting not recorded")


def test_the_plan_refusal_codes_are_named():
    assert RUN_CODES["HB-PRE-010"].startswith("combo setting not supported by its profile")
    assert RUN_CODES["HB-PRE-011"].startswith("per-harness parallelism cap missing or above 1")
    assert RUN_CODES["HB-PRE-012"].startswith("scripted-user task refused")


def test_the_denied_action_cause_is_a_blocked_cell_never_a_success():
    c = Cause.blocked_denied
    assert (c.code, c.attribution, c.label) == ("HB-CELL-203", "agent", "blocked (denied action)")
    assert not c.invalidates


# --- telemetry/__init__.py: ServedSettings, ToolInput.bytes_returned, the four reader hooks ------------------------

def test_served_settings_fields_and_order():
    assert names(telemetry.ServedSettings) == ["model_requested", "model_served", "model_api", "effort", "context_tokens",
                                               "context_tier", "reasoning_summary", "sources"]
    s = telemetry.ServedSettings()
    assert s.effort == (None, telemetry.READER_NOT_BUILT) and s.sources == {}


def test_not_recorded_is_a_none_with_its_reason():
    assert telemetry.not_recorded("per-turn totals only") == (None, "not recorded: per-turn totals only")
    assert telemetry.is_not_recorded((None, "x")) and not telemetry.is_not_recorded("high")


def test_tool_input_gains_bytes_returned_last_with_a_none_default():
    assert names(telemetry.ToolInput) == ["native_ordinal", "name", "paths", "command", "is_write", "bytes_returned"]
    assert telemetry.ToolInput(1, "read", ("a",), None, False).bytes_returned is None


def test_the_stream_item_dataclasses_carry_the_adr_0026_columns():
    assert names(telemetry.ReasoningItem) == ["native_ordinal", "item_ordinal", "source_kind", "text", "chars",
                                              "reasoning_tokens", "opaque_sha256"]
    assert names(telemetry.PromptPart) == ["native_ordinal", "part", "path", "chars", "delivery", "source"]
    # Ruling on DR1 (ADR-0026 erratum): `native_ordinal`, the event's position in its record, so two identical events
    # never collide on the key (HB-LED-003).
    assert names(telemetry.HarnessEvent) == ["native_ordinal", "event", "name", "start", "end", "ok", "detail"]
    assert telemetry.REASONING_KINDS == ("text", "summary", "encrypted-only", "omitted")
    assert telemetry.PART_KINDS == ("system", "tools", "skills", "instruction_file", "agents_md")
    assert telemetry.DELIVERIES == ("inlined", "on-demand", "listed")
    assert telemetry.EVENT_KINDS == ("hook", "skill_load", "compaction")
    assert telemetry.SERVED_FIELDS == ("model_served", "model_api", "effort", "context_tokens", "context_tier",
                                       "reasoning_summary")


def test_the_four_reader_hooks_default_to_reader_not_built():
    assert telemetry.READER_NOT_BUILT == "not recorded: reader not built"
    ex = telemetry.Extraction()
    assert [getattr(ex, s) for s in STREAMS] == [telemetry.READER_NOT_BUILT] * 4


# --- normalize.py: the four row builders, ADR-0026 s1's columns exactly ------------------------------------------

def _ex() -> telemetry.Extraction:
    ex = telemetry.Extraction()
    ex.served = telemetry.ServedSettings(model_served="gpt-6-sol", effort="high", context_tokens=telemetry.not_recorded("absent"),
                                         sources={"model_served": "rollout:turn_context.model", "effort": "rollout:turn_context.effort"})
    ex.reasoning = [telemetry.ReasoningItem(3, 0, "summary", "plan", 4, 12, None)]
    ex.prompt_parts = [telemetry.PromptPart(2, "instruction_file", "AGENTS.md", 900, "inlined", "rollout:developer")]
    ex.harness_events = [telemetry.HarnessEvent(7, "hook", "pre", "2026-10-12T00:00:00Z", None, True, None)]
    return ex


def test_two_served_settings_with_different_sources_write_both_rows():  # ruling on DR2: a tuple, one per source
    ex = telemetry.Extraction()
    ex.served = (telemetry.ServedSettings(effort="high", sources={"effort": "rollout:turn_context.effort"}),
                 telemetry.ServedSettings(effort="medium", sources={"effort": "config.toml:model_reasoning_effort"}))
    rows = [r for r in normalize.served_rows("r1", "a", "s", ex, "x") if r["field"] == "effort"]
    assert [(r["value"], r["source"]) for r in rows] == [("high", "rollout:turn_context.effort"),
                                                          ("medium", "config.toml:model_reasoning_effort")]
    # a field neither source read (no source, the same reason) is one row, never a duplicate key
    assert [r["field"] for r in normalize.served_rows("r1", "a", "s", ex, "x")] == [*telemetry.SERVED_FIELDS, "effort"]


def test_served_rows_one_per_setting_with_the_reason_when_not_recorded():
    rows = normalize.served_rows("r1", "a", "s", _ex(), "x")
    assert [list(r) for r in rows] == [[*PREFIX, "field", "value", "not_recorded", "source"]] * 6
    by = {r["field"]: r for r in rows}
    assert list(by) == list(telemetry.SERVED_FIELDS)
    assert (by["effort"]["value"], by["effort"]["not_recorded"], by["effort"]["source"]) == ("high", None, "rollout:turn_context.effort")
    assert (by["context_tokens"]["value"], by["context_tokens"]["not_recorded"]) == (None, "not recorded: absent")
    assert by["effort"]["kind"] == "served_setting"


def test_the_list_stream_row_builders_have_exactly_the_adr_columns():
    ex = _ex()
    (r,) = normalize.reasoning_rows("r1", "a", "s", ex, "x")
    assert list(r) == [*PREFIX, "native_ordinal", "item_ordinal", "source_kind", "text", "chars", "reasoning_tokens",
                       "opaque_sha256"] and r["kind"] == "reasoning_item"
    (p,) = normalize.prompt_part_rows("r1", "a", "s", ex, "x")
    assert list(p) == [*PREFIX, "native_ordinal", "part", "path", "chars", "delivery", "source"]
    assert (p["kind"], p["native_ordinal"]) == ("prompt_part", 2)
    (h,) = normalize.harness_event_rows("r1", "a", "s", ex, "x")
    assert list(h) == [*PREFIX, "native_ordinal", "event", "name", "start", "end", "ok", "detail"]
    assert (h["kind"], h["native_ordinal"]) == ("harness_event", 7)
    assert h["ok"] == 1  # flags are 0/1 ints in the ledger


def test_a_hook_left_at_its_default_builds_no_rows():
    ex = telemetry.Extraction()
    builders = (normalize.served_rows, normalize.reasoning_rows, normalize.prompt_part_rows, normalize.harness_event_rows)
    assert [b("r1", "a", "s", ex, "x") for b in builders] == [[], [], [], []]


# --- runner.py PASS_FACTS, views.py FACTS / KEYS ------------------------------------------------------------------

def test_the_four_streams_are_pass_facts_and_view_facts_with_keys():
    assert runner.PASS_FACTS[-4:] == STREAMS
    assert views.FACTS[-4:] == STREAMS
    assert views.KEYS["served"] == ("run_id", "extraction_id", "cell_id", "native_session_id", "field", "source")
    assert views.KEYS["reasoning"] == ("run_id", "extraction_id", "cell_id", "native_session_id", "native_ordinal", "item_ordinal")
    assert views.KEYS["prompt_parts"] == ("run_id", "extraction_id", "cell_id", "native_session_id", "native_ordinal",
                                         "part", "path", "source")
    assert views.KEYS["harness_events"] == ("run_id", "extraction_id", "cell_id", "native_session_id", "native_ordinal")


def _cost_only(root: Path) -> None:
    path = root / "tasks" / "X1" / "task.yaml"
    task = yaml.safe_load(path.read_text(encoding="utf-8"))
    task["graders"] = ["cost"]  # no hidden-test run: these tests are about the fact streams
    path.write_text(yaml.safe_dump(task, sort_keys=False), encoding="utf-8")


@pytest.fixture
def root(tmp_path):
    r = make_root(tmp_path)
    _cost_only(r)
    return r


def _old_shape_reader(monkeypatch) -> None:
    """A reader from before the four hooks: the codex reader with each hook reset to its default (R-READ-CODEX built
    them, so an old shape is patched in)."""
    real = profiles.READERS["codex"]

    def reader(path):
        ex = real(path)
        for stream in STREAMS:
            setattr(ex, stream, telemetry.READER_NOT_BUILT)
        return ex

    monkeypatch.setitem(profiles.READERS, "codex", reader)


def test_an_old_shape_reader_writes_no_row_in_the_new_streams(root, tmp_path, monkeypatch):
    _old_shape_reader(monkeypatch)
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    gid = runner.run_pass(run_dir, root).grading_id
    assert [pass_rows(run_dir, s, gid) for s in STREAMS] == [[], [], [], []]
    completed = pass_rows(run_dir, "events", gid)[-1]
    assert set(completed["heads"]) >= set(STREAMS) and "streams_not_recorded" not in completed
    assert views.verify(run_dir) == []


def _with_hooks(monkeypatch, reason: str | None = None, events: list | None = None, served=None) -> None:
    real = profiles.READERS["codex"]

    def reader(path):
        ex = real(path)
        built = _ex()
        ex.served, ex.reasoning, ex.prompt_parts = served or built.served, built.reasoning, built.prompt_parts
        ex.harness_events = reason if reason is not None else (events or built.harness_events)
        return ex

    monkeypatch.setitem(profiles.READERS, "codex", reader)


def test_an_identical_event_pair_and_two_served_sources_write_every_row_and_the_view_loads(root, tmp_path, monkeypatch):
    load = telemetry.HarnessEvent
    pair = [load(4, "skill_load", "implement", None, None, None, None), load(9, "skill_load", "implement", None, None, None, None)]
    two = (telemetry.ServedSettings(effort="high", sources={"effort": "a"}), telemetry.ServedSettings(effort="high", sources={"effort": "b"}))
    _with_hooks(monkeypatch, events=pair, served=two)
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    gid = runner.run_pass(run_dir, root).grading_id
    assert [r["native_ordinal"] for r in pass_rows(run_dir, "harness_events", gid)] == [4, 9]
    assert [r["source"] for r in pass_rows(run_dir, "served", gid) if r["field"] == "effort"] == ["a", "b"]
    assert views.verify(run_dir) == []
    assert views.load(run_dir).cells[0].validity == "valid"  # no HB-LED-003: the keys differ


def test_two_identical_prompt_parts_write_two_rows_and_the_view_loads(root, tmp_path, monkeypatch):  # item 28 (DR1 shape)
    real = profiles.READERS["codex"]

    def reader(path):
        ex = real(path)
        ex.prompt_parts = [telemetry.PromptPart(n, "system", None, 10, "inlined", "rollout:response_item.message[developer]")
                           for n in (3, 4)]
        return ex

    monkeypatch.setitem(profiles.READERS, "codex", reader)
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    gid = runner.run_pass(run_dir, root).grading_id
    assert len(pass_rows(run_dir, "prompt_parts", gid)) == 2
    assert views.verify(run_dir) == []
    assert views.load(run_dir).cells[0].validity == "valid"  # no HB-LED-003: the ordinals differ


def test_a_pass_writes_the_four_streams_from_the_hooks(root, tmp_path, monkeypatch):
    _with_hooks(monkeypatch, reason="not recorded: hooks not in the record")
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    gid = runner.run_pass(run_dir, root).grading_id
    served = pass_rows(run_dir, "served", gid)
    assert [r["field"] for r in served] == list(telemetry.SERVED_FIELDS)
    assert all(r["cell_id"] == "a" and r["extraction_id"] == normalize.extraction_id() for r in served)
    assert [r["text"] for r in pass_rows(run_dir, "reasoning", gid)] == ["plan"]
    assert [r["path"] for r in pass_rows(run_dir, "prompt_parts", gid)] == ["AGENTS.md"]
    assert pass_rows(run_dir, "harness_events", gid) == []
    completed = pass_rows(run_dir, "events", gid)[-1]
    assert completed["streams_not_recorded"] == {"a": {"harness_events": "not recorded: hooks not in the record"}}
    assert views.verify(run_dir) == []
    assert views.load(run_dir).cells[0].validity == "valid"


def test_tamper_a_reasoning_row_edited_after_sealing_fails_bench_verify(root, tmp_path, monkeypatch, capsys):
    _with_hooks(monkeypatch)
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    gid = runner.run_pass(run_dir, root).grading_id
    assert cli.main(["--root", str(root), "--runs", str(run_dir.parent), "verify", run_dir.name]) == 0
    seg = run_dir / "reasoning" / f"{gid}.jsonl"
    lines = seg.read_text(encoding="utf-8").splitlines(keepends=True)
    i = next(n for n, line in enumerate(lines) if json.loads(line).get("kind") == "reasoning_item")
    row = json.loads(lines[i])
    row["text"] = "a different plan"
    lines[i] = json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
    seg.write_text("".join(lines), encoding="utf-8")
    assert any(f.code == "HB-LED-002" and f.level == "error" and "reasoning" in f.message for f in views.verify(run_dir))
    assert cli.main(["--root", str(root), "--runs", str(run_dir.parent), "verify", run_dir.name]) == cli.INTEGRITY
    assert "reasoning" in capsys.readouterr().err


# --- config.validate_metrics accepts all_tasks (ADR-0026 s5) -------------------------------------------------------

def _catalog_problems(value) -> list[str]:
    metrics = yaml.safe_load((ROOT / "bench" / "metrics.yaml").read_text(encoding="utf-8"))
    first = next(iter(metrics["areas"].values()))["metrics"][0]
    first["all_tasks"] = value
    p = config.Problems()
    config.validate_metrics(metrics, p, config.grader_modules(ROOT), root=ROOT)
    return p.items


def test_a_metric_with_all_tasks_true_validates():
    assert _catalog_problems(True) == []


@pytest.mark.parametrize("value", ["yes", 1])
def test_a_metric_with_a_non_boolean_all_tasks_is_refused(value):  # red first: accepted before the check existed
    assert any("all_tasks must be true or false" in x for x in _catalog_problems(value))


# --- the report stubs: dataclass shapes, signatures, NotImplementedError -------------------------------------------

def test_series_key_carries_the_transport_plan_fact():
    assert names(cost_compare.SeriesKey) == ["combo", "harness", "model", "arm", "transport"]
    assert cost_compare.TRANSPORTS == ("acp", "native stream", "copilot -p (local adapter)")


def test_cost_compare_dataclasses_fields_and_order():
    assert names(cost_compare.ComboRow) == ["series", "cells", "effort_requested", "effort_served", "context_requested",
                                            "context_served", "tokens_per_cell", "tokens_by_bucket", "wall_ms",
                                            "requests_per_cell", "tool_calls_per_cell"]
    assert names(cost_compare.ReasoningRow) == ["series", "tokens_per_cell", "tokens_per_request", "visible_chars",
                                                "source_kinds", "excerpts", "excerpts_dropped"]
    assert names(cost_compare.ContextCurve) == ["series", "served_window", "median", "low", "high", "reason"]
    assert names(cost_compare.PromptComposition) == ["series", "chars_by_part", "instruction_files"]
    assert names(cost_compare.ToolPhaseRow) == ["series", "explore", "edit", "verify", "other", "bytes_returned"]
    assert names(cost_compare.TimeAnatomyRow) == ["series", "model_ms", "model_ms_acp_estimate", "tool_ms", "hook_ms", "idle_ms"]
    assert names(cost_compare.DriftRow) == ["series", "machine_lines", "task_implied_lines", "discretionary_lines",
                                            "attention_drift", "out_of_scope_paths"]
    assert names(cost_compare.KiviatSeries) == ["series", "axes", "reasons"]
    assert cost_compare.KIVIAT_AXES == ("token economy", "speed", "request economy", "tool-call economy", "clean cells",
                                        "edit orientation", "read orientation", "hidden checks passed")
    assert names(cost_compare.CostCompare) == ["runs", "catalog_version", "excerpts", "combos", "reasoning", "context",
                                               "prompt_composition", "tool_phases", "time_anatomy", "drift", "kiviat"]


def test_pack_cost_dataclasses_fields_and_order():
    assert pack_cost.TERMS == ("fixed_prefix", "extra_requests", "pack_reads", "skill_loads", "hooks", "reasoning_output",
                               "residual")
    assert pack_cost.COMPONENTS == ("always_applied_instruction", "scoped_instruction", "agents_md", "skill", "persona",
                                    "hook", "knowledge_doc", "other", "unclassified")
    assert names(pack_cost.Term) == ["name", "median", "low", "high", "label"]
    assert names(pack_cost.HarnessDecomposition) == ["harness", "transport", "pairs", "delta_total", "terms"]
    assert names(pack_cost.PackFile) == ["path", "component"]
    assert names(pack_cost.ComponentCost) == ["component", "harness", "tokens_per_cell"]
    assert names(pack_cost.TopFile) == ["path", "component", "harness", "tokens_per_cell", "requests_carried", "delivery"]
    assert names(pack_cost.Candidate) == ["rule", "harness", "figure", "threshold", "lever"]
    assert names(pack_cost.PackCost) == ["runs", "pack_source", "pack_source_reason", "harnesses", "components",
                                         "component_costs", "top_files", "candidates", "thresholds", "pairs", "outcomes",
                                         "outcome_reason", "transports"]


def test_the_stub_signatures():  # every J0 stub is built (R-DERIV, R-PACKCOST): their signatures stay pinned
    sig = {f: list(inspect.signature(f).parameters) for f in (
        cost_compare.build, cost_compare.render, cost_compare.cli_main, pack_cost.build, pack_cost.render,
        pack_cost.cli_main, tool_phases.phases, tool_phases.carry_until_compaction, publish.publish, publish.scan_text,
        context_growth.request_series)}
    assert list(sig.values()) == [["views"], ["cc", "scan"], ["argv"], ["views"], ["pc", "analysis_html"], ["argv"],
                                  ["calls"], ["entered", "compacted_before"], ["html", "out", "open"], ["text"],
                                  ["view", "cell_id"]]
    assert tool_phases.PHASES == ("explore", "edit", "verify", "other")
    assert tool_phases.VERIFY_COMMANDS == ("pytest", "tox", "ruff", "mypy", "pyright", "unittest")
