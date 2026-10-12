"""R-SETTINGS: bench-matrix/3 combo settings, the plan-time refusals, pooling, and the alias table (ADR-0024, ADR-0025 s7,
ADR-0028 s7). Mutants: tests/mutations/rerun-settings.json.

Each test is red first on an assertion. Grok and agy profiles are test-local fixtures: their yaml files are R-TRANSPORT's.
"""

from __future__ import annotations

import copy
import dataclasses
import hashlib
from pathlib import Path

import pytest

from harness_bench import board, config, plan, profiles, tools, views
from harness_bench.errors import BenchError
from harness_bench.ledger import canonical

ROOT = Path(__file__).resolve().parents[1]
BOM = config.load_yaml(ROOT / "bench" / "bom.yaml")
RINGS = ROOT / "bench" / "rings"


def _build(tmp_path: Path, harness: str) -> tools.Build:
    return tools.Build(harness, "1", tmp_path / "x.exe", "0" * 64, tmp_path / "adapter.js", "1", "0" * 64)


def _matrix(*combos: dict, schema: str = "bench-matrix/3", caps: dict | None = None, subset=("S1",)) -> dict:
    m = {"schema": schema, "ring": {"tag": "lean"}, "bom": {"file": "bench/bom.yaml", "subset": list(subset)}, "repetitions": 1,
         "arms": [{"id": "off"}, {"id": "on"}], "comparisons": [["off", "on"]], "combos": [dict(c) for c in combos]}
    if caps is not None:
        m["harness_parallelism"] = caps
    return m


def _problems(m: dict) -> list[str]:
    p = config.Problems()
    config.validate_matrix(m, BOM, p, "m.yaml")
    return p.items


CC = {"id": "cc-opus-1m", "harness": "claude-code", "model": "claude-opus-5-5[1m]", "effort": "high", "context": 1000000}
CODEX = {"id": "codex-sol", "harness": "codex", "model": "gpt-6.1-sol", "effort": "high", "context": 872000}


# --- 1. a combo's effort reaches the launch of Claude Code and Codex ----------------------------------------------

def _cells(m: dict) -> list[dict]:
    return [{"cell_id": c.id, **dataclasses.asdict(c)} for c in plan.expand(m, BOM)]


def test_claude_code_effort_high_reaches_the_cell_env(tmp_path):
    cell = _cells(_matrix(CC))[0]
    launcher = profiles.ProfileLauncher(profiles.load(ROOT, "claude-code", credential_source=tmp_path / "absent"),
                                        tmp_path, {})
    launcher.build = _build(tmp_path, "claude-code")
    _, env = launcher.argv_env(cell, tmp_path / "home", "")
    assert env.get("CLAUDE_CODE_EFFORT_LEVEL") == "high"
    assert env["ANTHROPIC_MODEL"] == "claude-opus-5-5[1m]"


def test_codex_effort_high_and_context_reach_the_seeded_config_toml(tmp_path):
    cell = _cells(_matrix(CODEX))[0]
    launcher = profiles.ProfileLauncher(profiles.load(ROOT, "codex", credential_source=tmp_path / "absent"), tmp_path, {})
    launcher.seed(tmp_path / "home", cell)
    text = (tmp_path / "home" / "config.toml").read_text(encoding="utf-8")
    assert 'model_reasoning_effort = "high"' in text.splitlines()
    assert "model_context_window = 872000" in text.splitlines()
    # top-level keys: before the first table, or TOML reads them as [features] keys
    assert text.index("model_reasoning_effort") < text.index("[features]")


def test_claude_code_session_meta_asks_for_the_summarized_thinking_display():
    """ADR-0026 s1: the `_meta` shape the 2026-10-11 spike sent on session/new (spike-settings/claude/acp3.jsonl)."""
    assert profiles.load(ROOT, "claude-code").session_meta == {
        "claudeCode": {"options": {"thinking": {"type": "adaptive", "display": "summarized"}}}}


# --- 2. a bench-matrix/2 file loads as "default", and a default cell launches as before ------------------------

def test_a_v2_matrix_loads_with_default_settings_and_unchanged_cell_ids():
    m = config.load_yaml(RINGS / "lean.yaml")
    assert _problems(m) == []
    cells = plan.expand(m, BOM)
    assert {(c.effort, c.context) for c in cells} == {(profiles.DEFAULT, profiles.DEFAULT)}
    for c in cells:
        old = {"task_version": c.task_version, "combo": c.combo, "pack": c.arm, "rep": c.rep}
        assert c.id == hashlib.sha256(canonical(old)).hexdigest()[:16]


@pytest.mark.parametrize("harness", ["claude-code", "codex"])
def test_a_default_cell_launches_without_any_setting(tmp_path, harness):
    """A settings block must not break a /2 cell: "default" drops the env key or file line that carries the setting."""
    p = profiles.load(ROOT, harness, credential_source=tmp_path / "absent")
    env = p.cell_env({"PATH": "p"}, tmp_path, _build(tmp_path, harness), "m", "")
    assert "CLAUDE_CODE_EFFORT_LEVEL" not in env
    p.seed_home(tmp_path / "h", "m")
    for f in (tmp_path / "h").iterdir():
        text = f.read_text(encoding="utf-8")
        assert "{" + "effort}" not in text and "{context_tokens}" not in text
        assert "model_reasoning_effort" not in text and "model_context_window" not in text


# --- 3-7. plan-time refusals -------------------------------------------------------------------------------------

def _refuse(root: Path, m: dict) -> BenchError:
    with pytest.raises(BenchError) as err:
        plan.require_combo_settings(root, m, plan.select_tasks(BOM, m["bom"]["subset"]))
    return err.value


def test_an_unsupported_value_is_refused_naming_the_combo_the_setting_and_the_supported_values():
    err = _refuse(ROOT, _matrix({**CODEX, "effort": "turbo"}))
    assert err.code == "HB-PRE-010"
    assert "codex-sol" in err.message and "effort" in err.message and "'turbo'" in err.message
    assert "high" in err.message and "xhigh" in err.message


def test_an_unsupported_context_is_refused():
    err = _refuse(ROOT, _matrix({**CODEX, "context": 128000}))
    assert err.code == "HB-PRE-010" and "context" in err.message and "872000" in err.message


def test_build_plan_refuses_an_unsupported_value_before_any_cell_exists(monkeypatch):
    monkeypatch.setattr(plan, "_probe_instructions", lambda *a: ({}, []))
    monkeypatch.setattr(plan, "draw_launch_order", lambda cells: (0, cells, 1))  # one block cannot meet the bound
    with pytest.raises(BenchError) as err:
        plan.build_plan(ROOT, _matrix({**CODEX, "effort": "turbo"}), BOM, "r-settings", {"codex": {}},
                        {"off": None, "on": {"source": "/x", "commit": "0" * 40, "revision": 1}})
    assert err.value.code == "HB-PRE-010"


def test_a_supported_combo_passes():
    plan.require_combo_settings(ROOT, _matrix(CC, CODEX), plan.select_tasks(BOM, ["S1"]))


def test_a_v3_combo_with_an_unknown_key_is_refused_and_a_v2_combo_is_not():
    assert any("bogus_key" in x for x in _problems(_matrix({**CODEX, "bogus_key": 1})))
    v2 = {**CODEX, "bogus_key": 1}
    del v2["effort"], v2["context"]
    assert _problems(_matrix(v2, schema="bench-matrix/2")) == []


@pytest.mark.parametrize(("change", "needle"), [
    ({"effort": None}, "effort"), ({"context": None}, "context"), ({"effort": ""}, "effort"),
    ({"context": "1m"}, "context"), ({"context": True}, "context"), ({"context": 0}, "context"),
])
def test_a_v3_combo_needs_effort_and_context_of_the_right_type(change, needle):
    combo = {**CODEX, **change}
    for key in [k for k, v in change.items() if v is None]:
        del combo[key]
    assert any(needle in x and "codex-sol" in x for x in _problems(_matrix(combo)))


def test_a_v3_matrix_validates_and_v1_v2_still_do():
    assert _problems(_matrix(CC, CODEX)) == []
    assert _problems(_matrix({**CODEX, "context": "default", "effort": "default"})) == []


@pytest.mark.parametrize(("model", "context", "ok"), [
    ("claude-opus-5-5[1m]", 1000000, True), ("claude-opus-5-5", "default", True),
    ("claude-opus-5-5[1m]", "default", False), ("claude-opus-5-5", 1000000, False),
])
def test_claude_model_id_and_context_agree(model, context, ok):
    m = _matrix({**CC, "model": model, "context": context})
    tasks = plan.select_tasks(BOM, ["S1"])
    if ok:
        plan.require_combo_settings(ROOT, m, tasks)
    else:
        err = _refuse(ROOT, m)
        assert err.code == "HB-PRE-010" and "cc-opus-1m" in err.message and model in err.message


AGY = """\
harness: {harness}
vendor: google
home_env: AGY_HOME
credential: null
record_glob: "x/{{session_id}}"
shutdown_grace_seconds: 5
transport: agy-stream
scripted_user: {scripted_user}
settings:
  effort: {{values: [low, high], apply: model_id}}
command: ["{{exe}}", "--model", "{{model}}"]
"""


def _fixture_root(tmp_path: Path, monkeypatch, harness: str, scripted_user: str = "supported",
                  task_scripted: bool = False) -> Path:
    (tmp_path / "bench" / "profiles").mkdir(parents=True)
    (tmp_path / "bench" / "profiles" / f"{harness}.yaml").write_text(
        AGY.format(harness=harness, scripted_user=scripted_user), encoding="utf-8")
    (tmp_path / "tasks" / "S1").mkdir(parents=True)
    (tmp_path / "tasks" / "S1" / "task.yaml").write_text(f"id: S1\nscripted_user: {str(task_scripted).lower()}\n",
                                                        encoding="utf-8")
    monkeypatch.setattr(profiles, "HARNESSES", (*profiles.HARNESSES, harness))
    return tmp_path


@pytest.mark.parametrize(("model", "effort", "ok"), [
    ("gemini-3.8-flash-high", "high", True), ("gemini-3.8-flash", "default", True),
    ("gemini-3.8-flash-high", "default", False), ("gemini-3.8-flash", "high", False),
    ("gemini-3.8-flash-low", "high", False),
])
def test_agy_model_id_and_effort_agree(tmp_path, monkeypatch, model, effort, ok):
    root = _fixture_root(tmp_path, monkeypatch, "agy")
    m = _matrix({"id": "agy-gemini", "harness": "agy", "model": model, "effort": effort, "context": "default"},
                caps={"agy": 1})
    if ok:
        plan.require_combo_settings(root, m, plan.select_tasks(BOM, ["S1"]))
    else:
        err = _refuse(root, m)
        assert err.code == "HB-PRE-010" and model in err.message


@pytest.mark.parametrize("harness", ["grok", "agy"])
@pytest.mark.parametrize("caps", [None, {}, {"codex": 1}])
def test_a_grok_or_agy_combo_without_a_cap_is_refused(tmp_path, monkeypatch, harness, caps):
    root = _fixture_root(tmp_path, monkeypatch, harness)
    combo = {"id": f"{harness}-c", "harness": harness, "model": "x", "effort": "default", "context": "default"}
    err = _refuse(root, _matrix(combo, caps=caps))
    assert err.code == "HB-PRE-011" and harness in err.message and f"{harness}-c" in err.message


@pytest.mark.parametrize("harness", ["grok", "agy"])
def test_a_grok_or_agy_cap_above_one_is_refused_and_one_passes(tmp_path, monkeypatch, harness):
    root = _fixture_root(tmp_path, monkeypatch, harness)
    combo = {"id": f"{harness}-c", "harness": harness, "model": "x", "effort": "default", "context": "default"}
    err = _refuse(root, _matrix(combo, caps={harness: 2}))
    assert err.code == "HB-PRE-011" and "2" in err.message
    plan.require_combo_settings(root, _matrix(combo, caps={harness: 1}), plan.select_tasks(BOM, ["S1"]))


def test_build_plan_refuses_an_uncapped_grok_combo(monkeypatch):
    monkeypatch.setattr(plan, "_probe_instructions", lambda *a: ({}, []))
    monkeypatch.setattr(plan, "draw_launch_order", lambda cells: (0, cells, 1))  # one block cannot meet the bound
    combo = {"id": "grok-4.7", "harness": "grok", "model": "grok-4.7", "effort": "high", "context": "default"}
    with pytest.raises(BenchError) as err:
        plan.build_plan(ROOT, _matrix(combo), BOM, "r-settings", {"grok": {}},
                        {"off": None, "on": {"source": "/x", "commit": "0" * 40, "revision": 1}})
    assert err.value.code == "HB-PRE-011"


def test_a_scripted_user_task_for_an_unsupported_profile_is_refused(tmp_path, monkeypatch):
    root = _fixture_root(tmp_path, monkeypatch, "agy", scripted_user="unsupported", task_scripted=True)
    combo = {"id": "agy-gemini", "harness": "agy", "model": "x", "effort": "default", "context": "default"}
    err = _refuse(root, _matrix(combo, caps={"agy": 1}))
    assert err.code == "HB-PRE-012" and "S1" in err.message and "agy" in err.message


def test_a_scripted_user_task_passes_where_supported_and_a_plain_task_passes_where_not(tmp_path, monkeypatch):
    combo = {"id": "agy-gemini", "harness": "agy", "model": "x", "effort": "default", "context": "default"}
    m = _matrix(combo, caps={"agy": 1})
    root = _fixture_root(tmp_path / "a", monkeypatch, "agy", scripted_user="supported", task_scripted=True)
    plan.require_combo_settings(root, m, plan.select_tasks(BOM, ["S1"]))
    root = _fixture_root(tmp_path / "b", monkeypatch, "agy", scripted_user="unsupported", task_scripted=False)
    plan.require_combo_settings(root, m, plan.select_tasks(BOM, ["S1"]))


# --- 8. pooling: a batch differing only in effort or context is not the same batch ---------------------------

def _pool_plan(run_id: str, **settings) -> dict:
    cells = [{"cell_id": f"S1-{arm}", "label": f"S1.c.arm-{arm}.r1", "task": "S1", "task_version": "v1", "scenario": 5,
              "combo": "c", "harness": "codex", "model": "m", "arm": arm, "rep": 1, "budget_seconds": 60, **settings}
             for arm in ("off", "on")]
    return {"run_id": run_id, "created_at": "t", "trace_id": "tr", "launch_seed": 1, "plan_hash": run_id,
            "platform": "win32", "bom_version": "0.4", "ring": {"tag": "lean", "hash": "h"},
            "matrix": {"combos": [{"id": "c", "harness": "codex", "model": "m"}]},
            "arms": {"off": {"pack": None}, "on": {"pack": {"revision": 1, "commit": "c"}}},
            "builds": {"codex": {"version": "1"}}, "profiles": {"codex": {"profile_hash": "p"}},
            "parameters": {"parallelism": 2}, "envelope_seconds": 60, "cells": cells}


def _view(run_id: str, p: dict) -> views.RunView:
    return views.RunView(run_id=run_id, plan=p, completed=True, grading_id=f"g-{run_id}", catalog_version="0.7",
                         cells=[])


@pytest.mark.parametrize("setting", [{"effort": "low"}, {"context": 272000}])
def test_pool_check_names_cells_that_differ_only_in_a_setting_as_changed(setting):
    pool = _view("r-b1", _pool_plan("r-b1", effort="high", context=872000))
    view = _view("r-b2", _pool_plan("r-b2", **{"effort": "high", "context": 872000, **setting}))
    with pytest.raises(BenchError) as err:
        board.pool_check(pool, view)
    assert err.value.code == "HB-STA-002"
    assert "cells differ: changed: S1-off, S1-on" in err.value.message


def test_pool_check_reads_a_cell_without_settings_as_default():
    pool = _view("r-b1", _pool_plan("r-b1"))
    view = _view("r-b2", _pool_plan("r-b2", effort="default", context="default"))
    assert board.pool_check(pool, copy.deepcopy(view)) == ()


# --- 11. model_allowed: the exact alias table ---------------------------------------------------------------------

def test_model_allowed_reads_the_exact_alias_table():
    grok = profiles.Profile("grok", "GROK_HOME", None, None, ("{exe}",), model_aliases={"grok-4.7": ("grok-4.7-build",)})
    assert grok.model_allowed("grok-4.7-build", "grok-4.7")
    assert grok.model_allowed("grok-4.7", "grok-4.7")
    assert not grok.model_allowed("grok-4.7-build-fast", "grok-4.7")
    assert not grok.model_allowed("grok-4.7-build", "grok-4.8")
    copilot = profiles.Profile("copilot", "COPILOT_HOME", None, None, ("{exe}",),
                               model_aliases={"gpt-5.6-sol-fast": ("gpt-5.6-sol",)})
    assert copilot.model_allowed("gpt-5.6-sol", "gpt-5.6-sol-fast")
    assert not copilot.model_allowed("gpt-5.6-sol-fast", "gpt-5.6-sol")
    assert profiles.model_allowed("grok-4.7-build", "grok-4.7", (), {"grok-4.7": ["grok-4.7-build"]})
    assert not profiles.model_allowed("grok-4.7-build-fast", "grok-4.7", (), {"grok-4.7": ["grok-4.7-build"]})


def test_the_plan_profile_record_freezes_a_profile_alias_table(tmp_path, monkeypatch):
    root = _fixture_root(tmp_path, monkeypatch, "agy")
    path = root / "bench" / "profiles" / "agy.yaml"
    assert "model_aliases" not in plan.profile_record(root, "agy")
    path.write_text(path.read_text(encoding="utf-8") + "model_aliases: {a: [b]}\n", encoding="utf-8")
    assert plan.profile_record(root, "agy")["model_aliases"] == {"a": ["b"]}


# --- 13. the two lean re-run rings validate ------------------------------------------------------------------------

@pytest.mark.parametrize(("name", "cells"), [("lean-rerun.yaml", 120), ("lean-rerun-probe.yaml", 12)])
def test_the_lean_rerun_rings_validate_as_v3(name, cells):
    m = config.load_yaml(RINGS / name)
    assert m["schema"] == "bench-matrix/3"
    assert _problems(m) == []
    assert len(plan.expand(m, BOM)) == cells
    assert plan.frozen_harness_parallelism(m) == {"agy": 1, "grok": 1}
    assert {c["id"] for c in m["combos"]} == {"cc-opus-1m", "codex-sol", "copilot-sol", "copilot-sol-fast", "grok-4.7",
                                             "agy-gemini"}
    assert all(c["effort"] == "high" for c in m["combos"])


def test_the_lean_rerun_rings_pass_the_claude_and_codex_plan_checks():
    """The five-harness plan proof is the Leader's at J1a; here only the two profiles this track owns are checked."""
    for name in ("lean-rerun.yaml", "lean-rerun-probe.yaml"):
        m = config.load_yaml(RINGS / name)
        m["combos"] = [c for c in m["combos"] if c["harness"] in ("claude-code", "codex")]
        plan.require_combo_settings(ROOT, m, plan.select_tasks(BOM, m["bom"]["subset"]))
