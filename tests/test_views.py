"""Views: pure projections over the verified facts (ADR-0006; design: Data model, Rules; spec US-11, US-23, US-24, US-27).

Runs are built with the shared archived-run builder and graded for real, then projected.
"""

import hashlib
import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from archived_runs import (
    CODEX_MODEL,
    GOOD,
    STUB,
    complete_run,
    make_root,
    make_run,
    pass_rows,
    set_prices,
)

from harness_bench import archive, ledger, profiles, views
from harness_bench import plan as plan_mod
from harness_bench.errors import BenchError
from harness_bench.grade import cost, runner
from harness_bench.telemetry import normalize

SONNET = "claude-sonnet-5"
OPUS = "claude-opus-5-5"
COPILOT_FIX = Path(__file__).parent / "fixtures/native/copilot"

# real cc-opus turn_usage rows, run e2e-wave1-1790299304 cell 17efb75ce2d5fc6d (pin claude-opus-5-5) (R-32)
CC_OPUS_TURN_USAGE = [
    {"kind": "turn_usage", "run_id": "r1", "cell_id": "a", "attempt": 1, "model": "claude-haiku-4-5-20251001",
     "uncached_input": 929, "cache_read": 0, "cache_write": 0, "output": 14, "reasoning": 0},
    {"kind": "turn_usage", "run_id": "r1", "cell_id": "a", "attempt": 1, "model": "claude-opus-5-5[1m]",
     "uncached_input": 10, "cache_read": 179401, "cache_write": 27730, "output": 1385, "reasoning": 0},
]


@pytest.fixture
def root(tmp_path):
    return make_root(tmp_path)


def _usage(cell_id: str, model: str, output: int = 50) -> dict:
    return {"kind": "turn_usage", "run_id": "r1", "cell_id": cell_id, "attempt": 1, "model": model,
            "uncached_input": 100, "cache_read": 1000, "cache_write": 10, "output": output, "reasoning": 0}


def _cell(view: views.RunView, cell_id: str) -> views.CellView:
    return next(c for c in view.cells if c.cell_id == cell_id)


def _edit_events(run_dir: Path, change) -> None:
    """Rewrite the engine's events segment through the real ledger, `change` mapping each row (chain fields dropped)."""
    path = run_dir / "events" / "engine-1.jsonl"
    rows = [change({k: v for k, v in r.items() if k not in ledger.CHAIN_FIELDS}) for r in ledger.read_segment(path)]
    path.unlink()
    with ledger.SegmentWriter.create(run_dir / "events", "engine-1") as ev:
        for row in rows:
            ev.append(row)


def _copilot_run(root: Path, tmp_path: Path, change=None, arm: str = "off", **kw) -> Path:
    """Grade a real archived run using a committed Copilot native record (`arm`: off, on (rev 95), on-rev92)."""
    assert "copilot" in profiles.READERS, "Copilot must be registered before grading its native record"
    run_dir = make_run(root, tmp_path, {"a": GOOD}, harness="copilot", archived=set(), **kw)
    folder = run_dir / "archive/a/attempt-1"
    workspace = folder / "ws"
    workspace.mkdir(parents=True)
    (workspace / "slug.py").write_text(GOOD, encoding="utf-8")
    record = folder / "home/session-state/sess-a/events.jsonl"
    record.parent.mkdir(parents=True)
    source = next((COPILOT_FIX / arm).rglob("events.jsonl"))
    events = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]
    if change is not None:
        events = change(events)
    record.write_text("\n".join(json.dumps(event) for event in events) + "\n", encoding="utf-8")
    rows = [{"path": file.relative_to(folder).as_posix(), "kind": "file", "size": file.stat().st_size,
             "sha256": hashlib.sha256(file.read_bytes()).hexdigest(), "link_target": "", "archive_attempt": 1}
            for file in sorted(folder.rglob("*")) if file.is_file()]
    with ledger.SegmentWriter.create(run_dir / "archive_files", "engine-2") as files:
        for row in rows:
            files.append({"kind": "archive_file", "run_id": "r1", "cell_id": "a", **row})
    with ledger.SegmentWriter.create(run_dir / "events", "engine-2") as events_writer:
        events_writer.append({"kind": "cell.archived", "cell_id": "a", "archive_attempt": 1,
                              "archive_hash": archive.archive_hash(rows)})
    runner.run_pass(run_dir, root)
    return run_dir


# First in the file on purpose (T12): a `-` -> `**` mutant of `_wall` never returns on the builder's mono_ns
# (31e9 ** 1e9), so the mutation run needs a test with small readings to fail before any run is loaded.
def test_wall_time_is_whole_milliseconds_of_the_monotonic_readings():
    events = {"cell.launch_intent": {}, "attempt.process_started": {"mono_ns": 0},
              "attempt.process_ended": {"mono_ns": 999_999_999}}
    assert views._wall(events) == views.Measure(999)


def _runtime(text: str) -> str:
    """An equal string that is not the literal's object: values read from a ledger are compared by value."""
    return "".join(list(text))


# --- current pass, verified reads, duplicate refusal (ADR-0006) ------------------------------------


def test_an_ungraded_run_has_no_scores_and_says_so(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    view = views.load(run_dir)
    assert view.grading_id is None
    a = _cell(view, "a")
    assert a.scores == {} and a.validity == "not graded" and a.tokens is None  # never {} or 0
    assert a.tokens_reason == "not graded"
    assert a.calls_per_cell == views.Measure(None, "not recorded")
    runner.run_pass(run_dir, root)
    a = _cell(views.load(run_dir), "a")
    assert a.tokens and a.tokens_reason is None


def test_a_pass_is_current_only_for_its_catalog_version(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    done = runner.run_pass(run_dir, root)
    assert (views.load(run_dir).grading_id, views.load(run_dir).catalog_version) == (done.grading_id, "0.3")
    assert views.load(run_dir, "0.3").grading_id == done.grading_id
    assert (views.load(run_dir, "9.9").grading_id, views.load(run_dir, "9.9").catalog_version) == (None, "9.9")


@pytest.mark.parametrize("second", ["0" * 64, "f" * 64])  # a new normaliser's id sorting below, or above, the first
def test_a_cell_reads_only_the_current_extraction(root, tmp_path, monkeypatch, second):
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    runner.run_pass(run_dir, root)
    before = _cell(views.load(run_dir), "a")
    monkeypatch.setattr(normalize, "extraction_id", lambda: second)
    runner.run_pass(run_dir, root)
    after = _cell(views.load(run_dir), "a")
    assert after.extraction_id == second and (after.tokens, after.tool_ms) == (before.tokens, before.tool_ms)


@pytest.mark.parametrize("second", ["0" * 64, "f" * 64])
def test_a_new_extraction_with_other_tool_times_replaces_the_old(root, tmp_path, monkeypatch, second):
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    runner.run_pass(run_dir, root)
    record = next((run_dir / "archive" / "a" / "attempt-1" / "home").rglob("*.jsonl"))  # a normaliser that reads other times
    record.write_text(record.read_text(encoding="utf-8").replace('"timestamp": "2026-', '"timestamp": "2027-'), encoding="utf-8")
    monkeypatch.setattr(normalize, "extraction_id", lambda: second)
    runner.run_pass(run_dir, root)
    assert _cell(views.load(run_dir), "a").tool_ms == views.Measure(592)  # never the union of both extractions


def test_a_cell_reads_only_its_own_tool_calls(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD, "b": GOOD})
    record = next((run_dir / "archive" / "b" / "attempt-1" / "home").rglob("*.jsonl"))
    record.write_text(record.read_text(encoding="utf-8").replace('"timestamp": "2026-', '"timestamp": "2027-'), encoding="utf-8")
    runner.run_pass(run_dir, root)
    assert _cell(views.load(run_dir), "a").tool_ms == views.Measure(592)  # b's calls, a year later, are not a's


def test_the_header_reads_only_process_starts(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    with ledger.SegmentWriter.create(run_dir / "events", "engine-2") as ev:
        ev.append({"kind": "attempt.process_started", "cell_id": "a", "credential_kind": "subscription", "network_mode": "open",
                   "harness": "codex", "build_version": "0.156.0"})
        for kind in ("attempt.process_ended", "cell.prompt_sent", "agent.x"):  # kinds sorting before and after it
            ev.append({"kind": kind, "cell_id": "z", "credential_kind": "leak", "network_mode": "leak", "harness": "x", "build_version": "1"})
    assert views.load(run_dir).header == {"credential_kind": "subscription", "network_mode": "open", "executed_builds": "codex 0.156.0"}


def test_a_measure_is_a_frozen_hashable_value():
    from dataclasses import FrozenInstanceError

    assert {views.Measure(1), views.Measure(1)} == {views.Measure(1)}
    with pytest.raises(FrozenInstanceError):
        views.Measure(1).value = 2  # type: ignore[misc]


def test_the_current_pass_is_the_latest_completed_one_and_an_unfinished_pass_is_ignored(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    runner.run_pass(run_dir, root)
    second = runner.run_pass(run_dir, root)
    with ledger.SegmentWriter.create(run_dir / "events", "grade-zzzz") as dead:  # newest id, never completed
        dead.append(ledger.stamp({"kind": "grading.started", "grading_id": "grade-zzzz", "catalog_version": "0.3"}))
    view = views.load(run_dir)
    assert view.grading_id == second.grading_id
    assert _cell(view, "a").scores["pass_at_1"] == views.Measure(1)


def test_a_second_outcome_for_a_cell_is_refused(root, tmp_path):  # HB-LED-003, never "latest wins"
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    with ledger.SegmentWriter.create(run_dir / "events", "engine-2") as ev:
        ev.append({"kind": "cell.outcome", "cell_id": "a", "outcome": "failed", "cause": "spawn", "code": "HB-CELL-114"})
    with pytest.raises(BenchError) as err:
        views.load(run_dir)
    assert err.value.code == "HB-LED-003"


def test_a_duplicate_fact_key_is_refused(root, tmp_path):  # HB-LED-003
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    first = runner.run_pass(run_dir, root)
    copy = [{k: v for k, v in r.items() if k not in ledger.CHAIN_FIELDS} for r in pass_rows(run_dir, "model_calls", first.grading_id)]
    with ledger.SegmentWriter.create(run_dir / "model_calls", "grade-copy") as mc:
        for row in copy:
            mc.append(row)
        mc.seal()
    with ledger.SegmentWriter.create(run_dir / "events", "grade-copy") as ev:
        ev.append(ledger.stamp({"kind": "grading.started", "grading_id": "grade-copy", "catalog_version": "0.3"}))
        ev.append(ledger.stamp({"kind": "grading.completed", "grading_id": "grade-copy", "cells_graded": 0}))
        ev.seal()
    with pytest.raises(BenchError) as err:
        views.load(run_dir)
    assert err.value.code == "HB-LED-003"


# --- validity (US-11; errors.Cause) -----------------------------------------------------------------


def test_an_infrastructure_or_benchmark_cause_invalidates_the_cell(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD, "b": GOOD, "c": GOOD}, outcomes={
        "a": {"outcome": "failed", "cause": "provider", "code": "HB-CELL-108"},
        "b": {"outcome": "failed", "cause": "model_unavailable", "code": "HB-CELL-116"},
        "c": {"outcome": "timed_out", "cause": "timed_out", "code": "HB-CELL-301"}})
    runner.run_pass(run_dir, root)
    view = views.load(run_dir)
    assert [(c.cell_id, c.validity, c.validity_code) for c in view.cells] == [
        ("a", "invalid (infrastructure)", "HB-CELL-108"), ("b", "invalid (benchmark)", "HB-CELL-116"), ("c", "valid", None)]
    assert _cell(view, "c").outcome == "timed_out" and _cell(view, "c").cause == "timed_out"


def test_a_cell_with_no_model_call_is_invalid(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD}, harness="claude-code", model=SONNET, turn_usage=[])
    view = views.load(run_dir)
    assert (_cell(view, "a").validity, _cell(view, "a").validity_code) == ("invalid (no model call)", "HB-VAL-001")


def test_a_served_model_other_than_the_pin_is_a_mismatch(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD}, model="gpt-other")  # the record serves gpt-6-sol
    runner.run_pass(run_dir, root)
    view = views.load(run_dir)
    assert (_cell(view, "a").validity, _cell(view, "a").validity_code) == ("invalid (model mismatch)", "HB-VAL-002")


# R-32: a context-window tag on the served model id is not a mismatch (R-32, HB-VAL-002 false positive) -----


def test_a_context_window_tag_is_not_a_model_mismatch(root, tmp_path):  # red before base_model_id, green after
    run_dir = make_run(root, tmp_path, {"a": GOOD}, harness="claude-code", model=OPUS, turn_usage=CC_OPUS_TURN_USAGE,
                        context_window_tag={"a": "1m"})
    cell = _cell(views.load(run_dir), "a")
    assert (cell.validity, cell.validity_code) == ("valid", None)  # views.py untouched: no CellView.context_window_tag (R-32 cond. 3)


def test_a_genuinely_different_served_model_is_still_a_mismatch(root, tmp_path):  # R-32 negative control
    turn_usage = [{**CC_OPUS_TURN_USAGE[1], "model": "claude-sonnet-5[1m]"}]  # a different model, also tagged
    run_dir = make_run(root, tmp_path, {"a": GOOD}, harness="claude-code", model=OPUS, turn_usage=turn_usage,
                        context_window_tag={"a": "1m"})
    cell = _cell(views.load(run_dir), "a")
    assert (cell.validity, cell.validity_code) == ("invalid (model mismatch)", "HB-VAL-002")


def test_copilot_modelmetrics_key_alone_determines_the_served_model(root, tmp_path):
    def rename(events):
        shutdown = next(e for e in events if e["type"] == "session.shutdown")
        metrics = shutdown["data"]["modelMetrics"]
        metrics["other-model"] = metrics.pop("gpt-6-sol")
        return events  # currentModel, selectedModel, and assistant.message.model remain untouched

    cell = _cell(views.load(_copilot_run(root, tmp_path, rename)), "a")
    assert (cell.validity, cell.validity_code) == ("invalid (model mismatch)", "HB-VAL-002")


def test_copilot_empty_modelmetrics_has_no_model_call(root, tmp_path):
    def empty(events):
        next(e for e in events if e["type"] == "session.shutdown")["data"]["modelMetrics"] = {}
        return events

    cell = _cell(views.load(_copilot_run(root, tmp_path, empty)), "a")
    assert (cell.validity, cell.validity_code) == ("invalid (no model call)", "HB-VAL-001")
    assert cell.calls_per_cell == views.Measure(None, "not recorded")


def test_copilot_unmutated_sample_is_valid(root, tmp_path):
    cell = _cell(views.load(_copilot_run(root, tmp_path)), "a")
    assert (cell.validity, cell.validity_code) == ("valid", None)


# --- R-27: a native hook denial makes the cell `invalid (tools denied by hook)` (HB-VAL-004) ------------------------


def test_the_revision_92_pack_on_copilot_cell_is_invalid_tools_denied_by_hook(root, tmp_path):  # R-27 c3 negative control
    run_dir = _copilot_run(root, tmp_path, arm="on-rev92")
    assert sum(r["outcome_code"] == "denied" for r in views.rows(run_dir, "tool_calls")) == 8  # the fixture's count
    cell = _cell(views.load(run_dir), "a")
    assert (cell.validity, cell.validity_code) == ("invalid (tools denied by hook)", "HB-VAL-004")


def test_the_revision_95_pack_on_copilot_cell_is_valid(root, tmp_path):  # R-27 c3: the rev-95 capture
    cell = _cell(views.load(_copilot_run(root, tmp_path, arm="on")), "a")
    assert (cell.validity, cell.validity_code) == ("valid", None)


def test_one_denied_tool_call_is_enough_to_invalidate(root, tmp_path):  # R-27 c2: native hook denials == 0 in a valid cell
    def deny_one(events):
        done = next(e for e in events if e["type"] == "tool.execution_complete")
        done["data"]["success"] = False
        done["data"]["error"] = {"code": "denied", "message": "Denied by preToolUse hook"}
        return events

    cell = _cell(views.load(_copilot_run(root, tmp_path, deny_one)), "a")
    assert (cell.validity, cell.validity_code) == ("invalid (tools denied by hook)", "HB-VAL-004")


def test_a_hook_denial_outranks_an_unreadable_record(root, tmp_path):  # a killed rev-92 cell: the denial is measured
    run_dir = _copilot_run(root, tmp_path, lambda events: [e for e in events if e["type"] != "session.shutdown"], arm="on-rev92")
    cell = _cell(views.load(run_dir), "a")
    assert (cell.validity, cell.validity_code) == ("invalid (tools denied by hook)", "HB-VAL-004")
    assert cell.tokens_reason == "not recorded (native record fields missing: session.shutdown)"


def test_an_ordinary_tool_failure_is_not_a_hook_denial(root, tmp_path):  # the rev-95 capture holds one (code not "denied")
    run_dir = _copilot_run(root, tmp_path, arm="on")
    assert any(r["ok"] == 0 for r in views.rows(run_dir, "tool_calls"))
    assert _cell(views.load(run_dir), "a").validity == "valid"


# --- R-24, R-26 c5: Σ model_calls buckets == the ACP turn total, else an HB-VAL-005 warning (not a validity change) ---

COPILOT_OFF_ACP_USAGE = json.loads((COPILOT_FIX / "provenance.json").read_text(encoding="utf-8"))["facts"]["off"]["acp_prompt_usage"]


def _with_acp_usage(usage):
    def change(e):
        return {**e, "acp_usage": usage} if e["kind"] == "attempt.process_ended" else e
    return change


def _acp_run(root, tmp_path, usage, **kw):
    run_dir = _copilot_run(root, tmp_path, **kw)
    _edit_events(run_dir, _with_acp_usage(usage))
    return _cell(views.load(run_dir), "a")


def _warnings(cell, code):
    return [(w.code, w.level, w.message) for w in cell.warnings if w.code == code]


def test_the_copilot_sample_agrees_with_its_acp_turn_total(root, tmp_path):  # the captured pair, off/ and its provenance
    cell = _acp_run(root, tmp_path, {"usage": COPILOT_OFF_ACP_USAGE, "meta": None})
    assert (cell.validity, _warnings(cell, "HB-VAL-005")) == ("valid", [])


@pytest.mark.parametrize(("key", "sums"), [("inputTokens", "58986"), ("outputTokens", "515"), ("cachedReadTokens", "46801"),
                                           ("cachedWriteTokens", "12170")])
def test_a_bucket_that_disagrees_with_the_acp_turn_total_is_a_warning_not_a_validity_change(root, tmp_path, key, sums):
    usage = {**COPILOT_OFF_ACP_USAGE, key: COPILOT_OFF_ACP_USAGE[key] + 1}
    cell = _acp_run(root, tmp_path, {"usage": usage, "meta": None})
    assert (cell.validity, cell.validity_code) == ("valid", None)
    message = f"model_calls tokens differ from the ACP turn total: {key} ACP {usage[key]}, model_calls {sums}"
    assert _warnings(cell, "HB-VAL-005") == [("HB-VAL-005", "warning", message)]


def test_a_copilot_cell_with_no_acp_usage_says_the_cross_check_did_not_run(root, tmp_path):  # never a silent pass
    cell = _acp_run(root, tmp_path, None)
    assert _warnings(cell, "HB-VAL-005") == [("HB-VAL-005", "warning", "token cross-check not run: no ACP usage recorded")]


def test_the_cross_check_skips_a_harness_whose_acp_usage_is_not_the_turn_total(root, tmp_path):  # Codex: the last call only
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    _edit_events(run_dir, _with_acp_usage({"usage": {"inputTokens": 1, "outputTokens": 1}, "meta": None}))
    runner.run_pass(run_dir, root)
    assert _warnings(_cell(views.load(run_dir), "a"), "HB-VAL-005") == []


# --- US-11: a model the task's model_map routes to is allowed, like the pin (F1; seam S3 freezes it in the plan) -------


def _mapped_run(root, tmp_path, model_map):
    run_dir = make_run(root, tmp_path, {"a": GOOD}, model="gpt-other")  # the record serves gpt-6-sol
    _edit_plan(run_dir, lambda p: {**p, "tasks": {"X1": {"model_map": model_map}}})
    runner.run_pass(run_dir, root)
    return _cell(views.load(run_dir), "a")


def test_a_model_the_task_model_map_names_is_valid(root, tmp_path):  # US-11: "or a model allowed by the task's model_map"
    cell = _mapped_run(root, tmp_path, {"implement": CODEX_MODEL, "review": SONNET})
    assert (cell.validity, cell.validity_code) == ("valid", None)


def test_a_model_the_model_map_does_not_name_is_still_a_mismatch(root, tmp_path):  # the negative control
    cell = _mapped_run(root, tmp_path, {"review": SONNET})
    assert (cell.validity, cell.validity_code) == ("invalid (model mismatch)", "HB-VAL-002")


# --- R-47 (R-28 c2 re-pointed): agent_version against the pinned build's recorded self-report -> HB-VAL-007 ----------


def _edit_plan(run_dir: Path, change) -> None:
    """Rewrite plan.json and its plan_hash (a plan as `bench plan` would have frozen it)."""
    path = run_dir / "plan.json"
    p = change(json.loads(path.read_text(encoding="utf-8")))
    p["plan_hash"] = plan_mod.plan_hash(p)
    path.write_text(json.dumps(p), encoding="utf-8")


def _fake_agent_run(base: Path, build: dict) -> views.CellView:
    """A real engine run of the fake ACP agent (its initialize.agentInfo.version is "0") under a plan pinning `build`."""
    from test_engine import FakeLauncher, _plan, _run
    p = _plan(n_cells=1)
    p["builds"] = {"fake": {"version": "0", "sha256": "f" * 64, "adapter_version": "0", "adapter_sha256": "e" * 64, **build}}
    p["profiles"] = {"fake": {"usage_source": "acp_turn", "auxiliary_models": [], "record_glob": "none/{session_id}"}}
    _, _, config = _run(base, p, FakeLauncher({}))
    p["plan_hash"] = plan_mod.plan_hash(p)
    (config.run_dir / "plan.json").write_text(json.dumps(p), encoding="utf-8")
    return views.load(config.run_dir).cells[0]


def test_a_fake_agent_reporting_another_version_than_the_recorded_self_report_is_invalid(base):  # R-47 c2 (R-22 c2)
    cell = _fake_agent_run(base, {"agent_version": "9.9.9"})  # package.json labels ("0") agree: never the comparand
    assert (cell.validity, cell.validity_code) == ("invalid (build mismatch)", "HB-VAL-007")
    assert cell.warnings == []


def test_a_fake_agent_reporting_the_recorded_self_report_is_not_a_mismatch(base):  # the negative control
    cell = _fake_agent_run(base, {"agent_version": "0"})
    assert cell.validity != "invalid (build mismatch)" and cell.warnings == []


def test_without_a_recorded_self_report_the_check_skips_and_the_cell_stays_valid(base):  # R-47 c3: never package.json
    cell = _fake_agent_run(base, {})
    assert cell.validity != "invalid (build mismatch)"
    assert [(w.code, w.level, w.message) for w in cell.warnings] == [
        ("HB-VAL-006", "warning", "executed-build check skipped: no recorded agent_version for fake")]


def _session_run(root, tmp_path, agent_version, builds, harness="codex", **kw):
    run_dir = make_run(root, tmp_path, {"a": GOOD}, harness=harness, **kw)
    _edit_events(run_dir, lambda e: {**e, "agent_version": agent_version} if e["kind"] == "attempt.session_opened" else e)
    _edit_plan(run_dir, lambda p: {**p, "builds": builds})
    return _cell(views.load(run_dir), "a")


COPILOT_PIN = {"copilot": {"version": "1.0.89-1", "sha256": "f" * 64, "adapter_version": None, "adapter_sha256": None,
                           "agent_version": "1.0.89-3"}}  # R-45 c2: the session self-reports 1.0.89-3 against a 1.0.89-1 manifest


def test_copilot_is_checked_against_its_recorded_self_report_not_its_manifest(root, tmp_path):  # F3; R-47 c4
    assert (_session_run(root, tmp_path / "1", "1.0.89-3", COPILOT_PIN, harness="copilot").validity_code,) == (None,)
    newer = _session_run(root, tmp_path / "2", "1.0.90", COPILOT_PIN, harness="copilot")
    assert (newer.validity, newer.validity_code) == ("invalid (build mismatch)", "HB-VAL-007")


def test_a_build_mismatch_outranks_not_graded_and_yields_to_an_invalidating_cause(root, tmp_path):  # R-47 c2 slot
    ungraded = _session_run(root, tmp_path / "1", "1.0.90", COPILOT_PIN, harness="copilot")  # the builder never grades
    assert (ungraded.validity, ungraded.validity_code) == ("invalid (build mismatch)", "HB-VAL-007")
    caused = _session_run(root, tmp_path / "2", "1.0.90", COPILOT_PIN, harness="copilot",
                          outcomes={"a": {"outcome": "failed", "cause": "provider", "code": "HB-CELL-108"}})
    assert (caused.validity, caused.validity_code) == ("invalid (infrastructure)", "HB-CELL-108")


def test_a_null_agent_version_skips_the_check_with_a_warning_never_a_pass(root, tmp_path):  # R-22 c1, R-28 c1
    cell = _session_run(root, tmp_path, None, COPILOT_PIN, harness="copilot")
    assert _warnings(cell, "HB-VAL-006") == [("HB-VAL-006", "warning", "executed-build check skipped: no agent_version recorded")]
    assert cell.validity != "invalid (build mismatch)"


def test_one_code_one_level_one_emitter():  # R-47 c1: a Cause code is never a view finding; a code has one level
    import re as _re

    from harness_bench.errors import Cause
    src = Path(views.__file__).parent
    texts = [(src / "views.py").read_text(encoding="utf-8")] + [p.read_text(encoding="utf-8") for p in (src / "grade").glob("*.py")]
    emitted = {(code, level) for text in texts for code, level in _re.findall(r'Finding\(\s*"(HB-[A-Z]+-\d{3})",\s*"(\w+)"', text)}
    assert {"HB-VAL-005", "HB-VAL-006"} <= {c for c, _ in emitted}  # the scan sees the view's findings (not vacuous)
    assert {c for c, _ in emitted}.isdisjoint({c.code for c in Cause})
    two_levels = {c for c, level in emitted if any(c == o and level != lv for o, lv in emitted)}
    # HB-LED-002's pre-R-2 "records no heads" warning predates R-47; its own code needs an errors.py row outside this
    # track's seam grant (named in the W2-VIEWS hand-back). The exact set makes the exclusion fail once it is fixed.
    assert two_levels == {"HB-LED-002"}


def test_every_validity_views_can_return_is_a_bench_status_state_or_a_named_exclusion():  # D&P minor
    import ast
    import inspect

    from harness_bench import status
    from harness_bench.errors import Cause
    passthrough = {"not started", "no outcome"}  # outcome states: bench status counts them under outcomes, not validity
    returned: set[str] = set()
    for node in ast.walk(ast.parse(inspect.getsource(views._validity))):
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Tuple):
            first = node.value.elts[0]
            if isinstance(first, ast.Constant):
                returned.add(first.value)
            elif isinstance(first, ast.JoinedStr):  # f"invalid ({cause.attribution})"
                returned |= {f"invalid ({c.attribution})" for c in Cause if c.invalidates}
            elif isinstance(first, ast.Name):  # `state`
                returned |= passthrough
            else:
                pytest.fail(f"_validity returns a form this guard cannot read: {ast.dump(first)}")
    assert {"valid", "not recorded", "invalid (no model call)"} <= returned  # the scan sees the literals (not vacuous)
    assert returned - passthrough <= set(status.VALIDITY)


def test_a_cell_that_never_opened_a_session_has_no_build_check(root, tmp_path):
    z = _cell(views.load(make_run(root, tmp_path, {"a": GOOD}, unstarted=("z",))), "z")
    assert z.warnings == []


# --- R-15 (Q5), R-21 c2: an unreadable native record is "not recorded" (HB-VAL-003), never HB-VAL-001 -------------


def test_a_killed_copilot_cell_with_no_shutdown_is_not_recorded(root, tmp_path):  # R-21 c2: tokens not recorded
    killed = {"a": {"outcome": "timed_out", "cause": "timed_out", "code": "HB-CELL-301"}}
    run_dir = _copilot_run(root, tmp_path, lambda events: [e for e in events if e["type"] != "session.shutdown"], outcomes=killed)
    cell = _cell(views.load(run_dir), "a")
    assert (cell.outcome, cell.validity, cell.validity_code) == ("timed_out", "not recorded", "HB-VAL-003")
    assert (cell.tokens, cell.tokens_reason) == (None, "not recorded (native record fields missing: session.shutdown)")


def test_a_copilot_record_of_an_unsupported_format_version_is_not_recorded(root, tmp_path):  # the F6 version gate
    def version_two(events):
        next(e for e in events if e["type"] == "session.start")["data"]["version"] = 2
        return events

    cell = _cell(views.load(_copilot_run(root, tmp_path, version_two)), "a")
    assert (cell.validity, cell.validity_code) == ("not recorded", "HB-VAL-003")
    assert cell.tokens_reason == "not recorded (native record fields missing: events.version)"


def test_a_cell_with_no_native_record_is_not_recorded(root, tmp_path):  # R-15: every native_record harness (Codex here)
    run_dir = make_run(root, tmp_path, {"a": GOOD, "b": GOOD})
    next((run_dir / "archive/b/attempt-1/home").rglob("*.jsonl")).unlink()
    runner.run_pass(run_dir, root)
    view = views.load(run_dir)
    assert [(c.cell_id, c.validity, c.validity_code) for c in view.cells] == [("a", "valid", None), ("b", "not recorded", "HB-VAL-003")]
    assert _cell(view, "b").tokens_reason == "not recorded (no native record for the session)"


def test_a_record_unreadable_as_a_whole_gives_no_partial_token_sum(root, tmp_path, monkeypatch):  # R-21 c2: never a partial sum
    monkeypatch.setattr(normalize, "record_unreadable", lambda ex: "native record truncated at the size bound")
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    runner.run_pass(run_dir, root)
    assert views.rows(run_dir, "model_calls")  # the calls read before the cut were written
    cell = _cell(views.load(run_dir), "a")
    assert (cell.validity, cell.tokens, cell.tokens_reason) == ("not recorded", None,
                                                                "not recorded (native record truncated at the size bound)")


TRUNCATED = "native record truncated at the size bound"


def _truncated_facts(unreadable: dict) -> tuple[dict, dict, dict]:
    """One Codex cell whose pre-cut rows are complete: a 2 s model call, a 1 s tool call, 10 s of wall time."""
    plan = {"profiles": {"codex": {"usage_source": "native_record", "auxiliary_models": []}}}
    cell = {"cell_id": "a", "harness": "codex", "combo": "c", "pack": "off", "model": CODEX_MODEL}
    call = {"cell_id": "a", "extraction_id": "x1", "native_ordinal": 3, "model": CODEX_MODEL, "uncached_input": 10,
            "cache_read": 0, "cache_write": 0, "output": 5, "reasoning": 0, "requests": 1,
            "start": "2026-09-23T10:00:01.000Z", "end": "2026-09-23T10:00:03.000Z"}
    tool = {"cell_id": "a", "extraction_id": "x1", "start": "2026-09-23T10:00:04.000Z", "end": "2026-09-23T10:00:05.000Z"}
    events = [{"kind": "cell.launch_intent", "cell_id": "a"}, {"kind": "attempt.process_started", "cell_id": "a", "mono_ns": 0},
              {"kind": "attempt.process_ended", "cell_id": "a", "mono_ns": 10_000_000_000},
              {"kind": "cell.outcome", "cell_id": "a", "outcome": "completed", "cause": None},
              {"kind": "grading.completed", "grading_id": "g1", "unreadable_records": unreadable}]
    score = {"grading_id": "g1", "cell_id": "a", "metric_id": "pass_at_1", "value": 1, "reason": None, "extraction_id": "x1"}
    facts = {"events": events, "model_calls": [call], "tool_calls": [tool], "scores": [score], "turn_usage": []}
    return plan, cell, facts


def test_a_truncated_record_gives_no_partial_time_or_call_count():  # Codex review F1
    whole = views._cell_view(*_truncated_facts({}), "g1")  # the control: the pre-cut spans and calls are complete
    assert (whole.model_ms, whole.tool_ms, whole.idle_ms, whole.calls_per_cell) == (
        views.Measure(2000), views.Measure(1000), views.Measure(7000), views.Measure(1))
    cut = views._cell_view(*_truncated_facts({"a": TRUNCATED}), "g1")
    assert (cut.model_ms, cut.tool_ms, cut.idle_ms, cut.calls_per_cell) == (views.Measure(None, TRUNCATED),) * 4
    assert cut.wall_ms == whole.wall_ms == views.Measure(10_000)  # lifecycle-derived: not gated


def test_a_harness_whose_record_is_missing_has_no_measured_zero_tool_time(root, tmp_path):  # F1 on acp_turn (no record found)
    run_dir = make_run(root, tmp_path, {"a": GOOD}, harness="claude-code", model=SONNET, turn_usage=[_usage("a", SONNET)])
    runner.run_pass(run_dir, root)  # the builder's record is Codex-shaped, so the Claude Code glob finds none
    cell = _cell(views.load(run_dir), "a")
    assert (cell.validity, cell.tool_ms) == ("valid", views.Measure(None, "no native record for the session"))


def test_an_acp_turn_cell_whose_adapter_reported_no_usage_is_not_recorded(root, tmp_path):  # R-15 for acp_turn (R-24 c2)
    run_dir = make_run(root, tmp_path, {"a": GOOD}, harness="claude-code", model=SONNET, turn_usage=[])
    _edit_events(run_dir, lambda e: {**e, "acp_usage": None} if e["kind"] == "attempt.process_ended" else e)
    cell = _cell(views.load(run_dir), "a")
    assert (cell.validity, cell.validity_code, cell.tokens_reason) == ("not recorded", "HB-VAL-003", "not recorded (the adapter reported no usage)")


def test_an_acp_turn_cell_whose_adapter_reported_usage_with_no_model_is_still_no_model_call(root, tmp_path):  # R-15 c1
    run_dir = make_run(root, tmp_path, {"a": GOOD}, harness="claude-code", model=SONNET, turn_usage=[])
    _edit_events(run_dir, lambda e: {**e, "acp_usage": {"usage": {}, "meta": None}} if e["kind"] == "attempt.process_ended" else e)
    cell = _cell(views.load(run_dir), "a")
    assert (cell.validity, cell.validity_code) == ("invalid (no model call)", "HB-VAL-001")


def test_copilot_single_row_with_two_requests_counts_two_calls(root, tmp_path):
    def two_requests(events):
        metrics = next(e for e in events if e["type"] == "session.shutdown")["data"]["modelMetrics"]
        metrics["gpt-6-sol"]["requests"]["count"] = 2
        return events

    run_dir = _copilot_run(root, tmp_path, two_requests)
    assert [row["requests"] for row in views.rows(run_dir, "model_calls")] == [2]
    cell = _cell(views.load(run_dir), "a")
    assert cell.calls_per_cell == views.Measure(2)


def test_copilot_two_models_on_one_shutdown_line_have_distinct_keys(root, tmp_path):
    def two_models(events):
        metrics = next(e for e in events if e["type"] == "session.shutdown")["data"]["modelMetrics"]
        metrics["other-model"] = json.loads(json.dumps(metrics["gpt-6-sol"]))
        metrics["other-model"]["requests"]["count"] = 2
        return events

    cell = _cell(views.load(_copilot_run(root, tmp_path, two_models)), "a")
    assert cell.calls_per_cell == views.Measure(7)


def test_copilot_missing_requests_is_not_zero(root, tmp_path):
    def no_requests(events):
        metrics = next(e for e in events if e["type"] == "session.shutdown")["data"]["modelMetrics"]
        del metrics["gpt-6-sol"]["requests"]
        return events

    cell = _cell(views.load(_copilot_run(root, tmp_path, no_requests)), "a")
    assert cell.scores["cost_usd"].reason == "HB-TEL-001 native-record fields missing: count"
    assert cell.calls_per_cell == views.Measure(None, "not recorded")


def test_pre_amendment_model_call_row_defaults_to_one_request():
    row = {"native_ordinal": 1, "model": "gpt-6-sol", "uncached_input": 2, "cache_read": 3,
           "cache_write": 4, "output": 5, "reasoning": None, "start": None, "end": None}
    assert views.model_call(row).requests == 1


def test_model_call_row_missing_start_still_raises():
    row = {"native_ordinal": 1, "model": "gpt-6-sol", "uncached_input": 2, "cache_read": 3,
           "cache_write": 4, "output": 5, "reasoning": None, "end": None}
    with pytest.raises(KeyError, match="start"):
        views.model_call(row)


def test_a_declared_auxiliary_model_is_not_a_mismatch(root, tmp_path):
    usage = [_usage("a", SONNET), _usage("a", "claude-haiku-4-5-20251001")]
    run_dir = make_run(root, tmp_path, {"a": GOOD}, harness="claude-code", model=SONNET, turn_usage=usage)
    assert _cell(views.load(run_dir), "a").validity == "valid"


def test_a_cell_that_never_started_is_listed_as_not_started(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD}, unstarted=("z",))
    z = _cell(views.load(run_dir), "z")
    assert (z.outcome, z.validity, z.wall_ms) == ("not started", "not started", views.Measure(None, "cell never started"))


def test_a_launched_cell_with_no_outcome_is_not_called_not_started(root, tmp_path):  # an engine crash (run incomplete)
    run_dir = make_run(root, tmp_path, {"a": GOOD}, unstarted=("z",))
    with ledger.SegmentWriter.create(run_dir / "events", "engine-2") as ev:
        ev.append({"kind": "cell.launch_intent", "cell_id": "z"})
    z = _cell(views.load(run_dir), "z")
    assert (z.outcome, z.validity) == ("no outcome", "no outcome")


# --- tokens, time split and cost (US-22, US-23, US-24, US-27) ---------------------------------------


def test_tokens_come_from_the_harness_token_source(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    runner.run_pass(run_dir, root)
    assert _cell(views.load(run_dir), "a").tokens == {CODEX_MODEL: {"uncached_input": 4032, "cache_read": 41856,
                                                                      "cache_write": 0, "output": 566}}
    acp = make_run(root, tmp_path / "acp", {"a": GOOD}, harness="claude-code", model=SONNET, turn_usage=[_usage("a", SONNET)])
    assert _cell(views.load(acp), "a").tokens == {SONNET: {"uncached_input": 100, "cache_read": 1000, "cache_write": 10, "output": 50}}


def test_the_time_split_records_what_the_harness_exposes_and_never_invents_idle(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    runner.run_pass(run_dir, root)
    a = _cell(views.load(run_dir), "a")
    assert a.wall_ms == views.Measure(30_000)
    assert a.tool_ms == views.Measure(592)  # 338 + 254 ms, the two tool calls in the Codex record
    assert a.model_ms == views.Measure(None, "the native record gives no model-call start time")
    assert a.idle_ms == views.Measure(None, "needs model time")


@pytest.mark.parametrize(("calls", "expected"), [
    ([{"start": "2026-09-23T10:00:00.000Z", "end": "2026-09-23T10:00:00.500Z"}], views.Measure(500)),
    ([{"start": None, "end": "2026-09-23T10:00:00.500Z"}], views.Measure(None, "the native record gives no model-call start time")),
    ([{"start": "2026-09-23T10:00:00.500Z", "end": "2026-09-23T10:00:00.500Z"}],
     views.Measure(None, "the native record gives no model-call start time")),
    ([], views.Measure(None, "the native record gives no model-call start time")),
    (None, views.Measure(None, "not graded")),
])
def test_model_time_needs_a_real_duration_for_every_call(calls, expected):
    assert views._model_time("native_record", calls) == expected
    assert views._model_time("acp_turn", calls).value is None


@pytest.mark.parametrize(("wall", "model", "tool", "expected"), [
    (1000, 300, 200, views.Measure(500)),
    (1000, 700, 400, views.Measure(None, "model and tool time exceed wall time")),
    (1000, 1000, 0, views.Measure(0)),
    (1000, 700, 301, views.Measure(None, "model and tool time exceed wall time")),  # -1 ms is never idle
])
def test_idle_is_wall_minus_model_minus_tool(wall, model, tool, expected):
    assert views._idle(views.Measure(wall), views.Measure(model), views.Measure(tool)) == expected


@pytest.mark.parametrize("call", [
    {"start": "not a time", "end": "2026-09-23T10:00:01.000Z"},
    {"start": "2026-09-23T10:00:00.000Z", "end": None},
    {"start": "2026-09-23T10:00:02.000Z", "end": "2026-09-23T10:00:01.000Z"},  # ends before it starts
])
def test_a_span_without_both_valid_ends_in_order_is_not_recorded(call):
    assert views.busy_ms([call]) == views.Measure(None, "an interval has no start or end")


@pytest.mark.parametrize("events", [
    {"cell.launch_intent": {}, "attempt.process_started": {"mono_ns": 1}},
    {"cell.launch_intent": {}, "attempt.process_ended": {"mono_ns": 1}},
])
def test_wall_time_needs_both_process_start_and_end(events):
    assert views._wall(events) == views.Measure(None, "no process start or end recorded")


def test_cells_with_long_ids_keep_their_own_events_and_calls(root, tmp_path):  # ids compared by value, never identity
    run_dir = make_run(root, tmp_path, {"cell-alpha-0001": GOOD, "cell-bravo-0002": STUB})
    runner.run_pass(run_dir, root)
    view = views.load(run_dir)
    for cid in ("cell-alpha-0001", "cell-bravo-0002"):
        c = _cell(view, cid)
        assert (c.outcome, c.validity, c.wall_ms) == ("completed", "valid", views.Measure(30_000))
        assert c.tokens == {CODEX_MODEL: {"uncached_input": 4032, "cache_read": 41856, "cache_write": 0, "output": 566}}  # one record each
        assert c.tool_ms == views.Measure(592)


def test_the_acp_token_source_is_matched_by_value():
    assert views._model_time(_runtime("acp_turn"), None) == views.Measure(None, "the native record misses calls (token source acp_turn)")


def test_touching_spans_measure_as_the_one_span_they_form():  # merged before rounding: 3330.5 ms rounds once (T12)
    touching = [{"start": "2026-09-23T10:00:03.981663Z", "end": "2026-09-23T10:00:06.398014Z"},
                {"start": "2026-09-23T10:00:06.398014Z", "end": "2026-09-23T10:00:07.312163Z"}]
    whole = [{"start": "2026-09-23T10:00:03.981663Z", "end": "2026-09-23T10:00:07.312163Z"}]
    assert views.busy_ms(touching) == views.busy_ms(whole) == views.Measure(3330)


def test_the_current_pass_is_chosen_within_its_catalog_version_only():
    events = [{"kind": "grading.started", "grading_id": "grade-1", "catalog_version": "0.3"},
              {"kind": "grading.completed", "grading_id": "grade-1", "recorded_at": "2026-09-23T10:00:00.000Z"},
              {"kind": "grading.started", "grading_id": "grade-2", "catalog_version": "0.4"},  # later, and sorts above 0.3
              {"kind": "grading.completed", "grading_id": "grade-2", "recorded_at": "2026-09-23T11:00:00.000Z"}]
    assert views._current_pass(events, "0.3") == ("grade-1", "0.3")


def test_a_cell_view_reads_only_its_own_rows_of_the_current_pass():  # by value: ids read from a ledger are new objects (T12)
    cid, gid = _runtime("cell-b"), _runtime("grade-new")
    plan = {"profiles": {"claude-code": {"usage_source": "acp_turn", "auxiliary_models": []}}}
    cell = {"cell_id": cid, "harness": "claude-code", "combo": "c", "pack": "off", "model": SONNET}

    def score(grading_id, cell_id, value):
        return {"grading_id": grading_id, "cell_id": cell_id, "metric_id": "pass_at_1", "value": value, "reason": None,
                "extraction_id": "x1"}

    def tool(cell_id, start, end):
        return {"cell_id": cell_id, "extraction_id": "x1", "start": f"2026-09-23T10:00:{start}.000Z",
                "end": f"2026-09-23T10:00:{end}.000Z"}

    facts = {"events": [], "model_calls": [],
             "scores": [score("grade-new", "cell-b", 1), score("grade-new", "cell-a", 0), score("grade-old", "cell-b", 0)],
             "tool_calls": [tool("cell-b", "01", "02"), tool("cell-a", "10", "13")],
             "turn_usage": [_usage("cell-a", SONNET, 70), _usage("cell-b", SONNET, 50), _usage("cell-c", SONNET, 90)]}
    view = views._cell_view(plan, cell, facts, gid)
    assert view.scores == {"pass_at_1": views.Measure(1)}
    assert view.tool_ms == views.Measure(1000)
    assert view.tokens == {SONNET: {"uncached_input": 100, "cache_read": 1000, "cache_write": 10, "output": 50}}


def test_an_executed_build_needs_both_a_harness_and_a_version():
    started = [{"kind": "attempt.process_started", "harness": "codex"}, {"kind": "attempt.process_started", "build_version": "1"}]
    assert views._header(started)["executed_builds"] is None


def _fake_cell(combo: str, **fields) -> SimpleNamespace:
    base = {"combo": combo, "pack": "off", "harness": "codex", "model": CODEX_MODEL, "validity": "valid", "scores": {},
            "tokens": None, "wall_ms": views.Measure(None, "x")}
    return SimpleNamespace(**{**base, **fields})


def test_a_row_averages_wall_time_names_the_first_missing_cost_and_needs_two_cells_for_no_interval():
    cells = [_fake_cell("c", wall_ms=views.Measure(ms), scores={"cost_usd": views.Measure(None, f"reason {i}")})
             for i, ms in enumerate((100, 200, 600))]
    row = views._row(SimpleNamespace(grading_id="grade-1"), cells)
    assert row.wall_ms == views.Measure(Decimal(300))
    assert row.cost_usd == views.Measure(None, "3 of 3 valid cells have no cost: reason 0")
    assert row.interval == "interval not computed (statistics are phase 4)"


def test_a_zero_pass_rate_sorts_after_every_positive_one():
    cells = [_fake_cell("a-zero", scores={"pass_at_1": views.Measure(0)}),
             _fake_cell("b-half", scores={"pass_at_1": views.Measure(Decimal("0.5"))})]
    rows = views.leaderboard(SimpleNamespace(grading_id="grade-1", cells=cells))
    assert [(r.combo, r.rank) for r in rows] == [("b-half", "1"), ("a-zero", "2")]


def test_a_finding_is_a_frozen_value():
    from dataclasses import FrozenInstanceError

    with pytest.raises(FrozenInstanceError):
        views.Finding("HB-LED-002", "error", "m").level = "warning"  # type: ignore[misc]


def test_a_zero_length_tool_call_is_a_measured_zero():  # only model calls need a positive span
    call = {"start": "2026-09-23T10:00:00.500Z", "end": "2026-09-23T10:00:00.500Z"}
    assert views.busy_ms([call]) == views.Measure(0)


def test_a_view_says_whether_the_run_completed(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    assert views.load(run_dir).completed is False
    complete_run(run_dir)
    assert views.load(run_dir).completed is True


def test_an_abandoned_segment_sorted_first_hides_no_completed_pass(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    runner.run_pass(run_dir, root)
    with ledger.SegmentWriter.create(run_dir / "scores", "grade-0000") as dead:  # sorts before every real pass
        dead.append({"kind": "score"})
    assert _cell(views.load(run_dir), "a").scores["pass_at_1"] == views.Measure(1)


def test_overlapping_tool_calls_are_counted_once():
    calls = [{"start": "2026-09-23T10:00:00.000Z", "end": "2026-09-23T10:00:02.000Z"},
             {"start": "2026-09-23T10:00:01.000Z", "end": "2026-09-23T10:00:03.000Z"},
             {"start": "2026-09-23T10:00:05.000Z", "end": "2026-09-23T10:00:06.000Z"}]
    assert views.busy_ms(calls) == views.Measure(4000)
    assert views.busy_ms([{"start": None, "end": "2026-09-23T10:00:01.000Z"}]).value is None


def test_the_cost_score_equals_a_fresh_derivation(root, tmp_path):  # a stored cost is a rebuildable cache (spec)
    set_prices(root, [{"model": CODEX_MODEL, "effective": "2026-09-01", "source": "s", "input": "1.25", "output": 10,
                       "cache_read": "0.125", "cache_write": 0}])
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    runner.run_pass(run_dir, root)
    a = _cell(views.load(run_dir), "a")
    fresh, _, _ = cost.cost_usd(a.tokens, {"entries": [{"model": CODEX_MODEL, "effective": "2026-09-01", "input": "1.25",
                                                          "output": 10, "cache_read": "0.125", "cache_write": 0}]}, "2026-09-23")
    assert a.scores["cost_usd"] == views.Measure(f"{fresh:.6f}")


# --- leaderboard (US-39 skeleton; correctness-gated, ties) -----------------------------------------


def test_the_leaderboard_ranks_by_pass_rate_and_shows_ties(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD, "b": STUB, "c": GOOD},
                       combos={"a": "good", "b": "stub", "c": "also-good"})
    runner.run_pass(run_dir, root)
    rows = views.leaderboard(views.load(run_dir))
    assert [(r.combo, r.rank, r.pass_at_1) for r in rows] == [
        ("also-good", "1=", views.Measure(Decimal(1))), ("good", "1=", views.Measure(Decimal(1))),
        ("stub", "3", views.Measure(Decimal(0)))]
    assert rows[0].interval == "interval not computed (n < 2)"


def test_an_invalid_cell_never_counts_toward_its_combo(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD}, outcomes={"a": {"outcome": "failed", "cause": "provider", "code": "HB-CELL-108"}})
    runner.run_pass(run_dir, root)
    (row,) = views.leaderboard(views.load(run_dir))
    assert (row.n_cells, row.n_valid, row.rank) == (1, 0, "")
    assert row.pass_at_1 == views.Measure(None, "no valid graded cell")


def test_an_unranked_combo_sorts_last_and_two_valid_cells_still_get_no_interval(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a1": GOOD, "a2": GOOD, "b1": GOOD}, combos={"a1": "a-two", "a2": "a-two", "b1": "b-bad"},
                       outcomes={"b1": {"outcome": "failed", "cause": "provider", "code": "HB-CELL-108"}})
    runner.run_pass(run_dir, root)
    rows = views.leaderboard(views.load(run_dir))
    assert [(r.combo, r.rank) for r in rows] == [("a-two", "1"), ("b-bad", "")]
    assert rows[0].interval == "interval not computed (statistics are phase 4)"


def test_cost_is_na_for_a_combo_when_any_valid_cell_has_no_cost(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD})
    runner.run_pass(run_dir, root)
    (row,) = views.leaderboard(views.load(run_dir))
    assert row.cost_usd == views.Measure(None, f"1 of 1 valid cells have no cost: no price list entry for {CODEX_MODEL}")


# --- canonical export (the byte-identical re-grade, US-26) -----------------------------------------


def test_a_higher_pass_rate_sorts_first_whatever_the_combo_name(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a1": GOOD, "a2": STUB, "b1": GOOD},
                       combos={"a1": "a-half", "a2": "a-half", "b1": "b-full"})
    runner.run_pass(run_dir, root)
    rows = views.leaderboard(views.load(run_dir))
    assert [(r.combo, r.rank, r.pass_at_1) for r in rows] == [("b-full", "1", views.Measure(Decimal(1))),
                                                              ("a-half", "2", views.Measure(Decimal("0.5")))]


def test_a_regrade_gives_a_byte_identical_canonical_export(root, tmp_path):
    run_dir = make_run(root, tmp_path, {"a": GOOD, "b": STUB})
    runner.run_pass(run_dir, root)
    first = views.export(views.load(run_dir))
    runner.run_pass(run_dir, root)
    second = views.export(views.load(run_dir))
    assert first == second
    assert b"grade-" not in first  # the pass's identity is not part of the result
