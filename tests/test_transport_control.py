"""Plan row A3: the Copilot transport control. A bench-matrix/3 combo may name `transport: acp`, a launch the harness's
profile declares under `transports`, so one plan runs Copilot over native ACP beside `copilot -p` without editing a file.
Every place that launches, judges or labels the cell follows the combo's transport, not the harness name alone.
"""
from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from archived_runs import make_root
from test_settings import BOM, _matrix, _problems, _refuse
from test_validity_served import _prompt_mode
from test_views import _acp_run, _copilot_run, _edit_plan, _warnings

from harness_bench import plan, profiles, tools, views
from harness_bench.report import tool_phases

ROOT = Path(__file__).resolve().parents[1]
P = {"id": "copilot-p", "harness": "copilot", "model": "gpt-6.1-sol", "effort": "high", "context": "default"}
ACP = {**P, "id": "copilot-acp", "transport": "acp"}


def _argv(tmp_path: Path, cell: dict) -> list[str]:
    launcher = profiles.ProfileLauncher(profiles.load(ROOT, "copilot"), tmp_path, {})
    launcher.build = tools.Build("copilot", "1", tmp_path / "copilot.exe", "0" * 64, tmp_path / "adapter.py", "1", "0" * 64)
    return launcher.argv_env(cell, tmp_path / "home", "")[0]


def test_an_acp_combo_plans_beside_a_p_combo_and_launches_native_acp(tmp_path):
    m = _matrix(P, ACP)
    assert _problems(m) == []
    plan.require_combo_settings(ROOT, m, plan.select_tasks(BOM, ["S1"]))
    cells = {c.combo: {"cell_id": c.id, **dataclasses.asdict(c)} for c in plan.expand(m, BOM) if c.arm == "off"}
    assert (cells["copilot-acp"]["transport"], cells["copilot-p"]["transport"]) == ("acp", None)
    same_combo = plan.expand(_matrix({k: v for k, v in ACP.items() if k != "transport"}), BOM)
    assert cells["copilot-acp"]["cell_id"] not in {c.id for c in same_combo}  # the transport joins the cell's recipe
    acp, p = _argv(tmp_path, cells["copilot-acp"]), _argv(tmp_path, cells["copilot-p"])
    assert acp[:2] == [str(tmp_path / "copilot.exe"), "--acp"] and str(tmp_path / "adapter.py") not in acp
    assert p[1] == str(tmp_path / "adapter.py") and "--acp" not in p


@pytest.mark.parametrize(("combo", "needle"), [
    ({**ACP, "harness": "codex", "id": "codex-acp", "context": 872000}, "transport 'acp'"),
    ({**ACP, "context": 922000}, "context '922000'"),
])
def test_a_transport_the_profile_lacks_or_a_window_it_cannot_serve_is_refused_at_plan(combo, needle):
    err = _refuse(ROOT, _matrix(combo))
    assert err.code == "HB-PRE-010" and needle in err.message and combo["id"] in err.message


def test_a_transport_must_be_a_nonempty_string():
    assert any("transport must be" in x for x in _problems(_matrix({**ACP, "transport": ""})))


@pytest.fixture
def root(tmp_path):
    return make_root(tmp_path)


def _acp_combo(p: dict) -> dict:
    cell = p["cells"][0]
    return {**_prompt_mode(p), "matrix": {"combos": [{"id": cell["combo"], "transport": "acp"}]},
            "cells": [{**cell, "transport": "acp"}, *p["cells"][1:]]}


def test_an_acp_cell_is_judged_and_labelled_as_acp_even_when_the_build_names_the_adapter(root, tmp_path, monkeypatch):
    """HB-VAL-005: an ACP cell with no ACP usage is the R-24 warning, never the `-p` path's `not recorded`."""
    import test_views

    def acp_run(*args, **kw):
        run_dir = _copilot_run(*args, **kw)
        _edit_plan(run_dir, _acp_combo)
        return run_dir
    monkeypatch.setattr(test_views, "_copilot_run", acp_run)
    cell = _acp_run(root, tmp_path, None)
    assert _warnings(cell, "HB-VAL-005") == [("HB-VAL-005", "warning", "token cross-check not run: no ACP usage recorded")]
    p = _acp_combo({"cells": [{"combo": "c"}]})
    acp, _, prompt = tool_phases.TRANSPORTS
    assert (tool_phases.transport(p, "copilot", "c"), tool_phases.transport(p, "copilot", "other")) == (acp, prompt)
    assert (views._prompt_mode(p, "copilot", "c"), views._prompt_mode(p, "copilot", "other")) == (False, True)


def test_the_pack_cost_page_labels_an_acp_copilot_run_acp():
    """The page pairs cells per harness, so a run holds one Copilot combo; an ACP one is labelled ACP, not `-p`."""
    import test_pack_cost

    from harness_bench.report import pack_cost

    view = test_pack_cost._views()[0]
    cells = [dataclasses.replace(c, combo="copilot-acp") if c.harness == "copilot" else c for c in view.cells]
    p = {**view.plan, "matrix": {"combos": [{"id": "copilot-acp", "transport": "acp"}]}}
    pc = pack_cost.build([dataclasses.replace(view, plan=p, cells=cells)])
    assert pc.transports["copilot"] == tool_phases.TRANSPORTS[0]
