"""R-73 c6 and R-74 c6: what the report header discloses for scenario-6 (F1) cells. Per combo, the resolved role -> model
map for its vendor, with `non-discriminating` beside a role whose model is the pin; per cell, the served-model set; the
banner `coordination: not built in 0.4` (header and every scenario-6 row), so an empty coordination area is never read as a
zero; and the scenario-6 allowance per harness. A run with no scenario-6 cell shows none of it."""

import json
import re
from pathlib import Path

import pytest
from archived_runs import CODEX_MODEL, GOOD, make_root, make_run

from harness_bench import plan as plan_mod
from harness_bench import views
from harness_bench.grade import runner
from harness_bench.report import html

MAP = {"domain-model@anthropic": "claude-opus-5-5", "derived-quantities@anthropic": "claude-sonnet-5",
       "tests@anthropic": "claude-sonnet-5", "domain-model@openai": CODEX_MODEL,
       "derived-quantities@openai": "gpt-6-astra", "tests@openai": "gpt-6-astra"}
LABEL = "X1.c.pack-off.r1"
BANNER = "coordination: not built in 0.4"


@pytest.fixture
def root(tmp_path):
    return make_root(tmp_path)


def _run(root: Path, tmp_path: Path, scenario: int, graded: bool = True) -> Path:
    run_dir = make_run(root, tmp_path, {"a": GOOD})  # a Codex cell pinned to gpt-6-sol; its record serves gpt-6-sol
    path = run_dir / "plan.json"
    p = json.loads(path.read_text(encoding="utf-8"))
    p["tasks"] = {"X1": {"scenario": scenario, "model_map": MAP if scenario == 6 else None}}
    p["plan_hash"] = plan_mod.plan_hash(p)
    path.write_text(json.dumps(p), encoding="utf-8")
    if graded:
        runner.run_pass(run_dir, root)
    return run_dir


def _page(run_dir: Path) -> tuple[str, str]:
    doc = html.render(views.load(run_dir), archive_present=True, run_dir=run_dir)
    return re.search(r'<section id="header".*?</section>', doc, re.DOTALL).group(0), doc


def test_the_header_carries_the_resolved_map_of_each_combo_with_non_discriminating_roles(root, tmp_path):
    header, _ = _page(_run(root, tmp_path, 6))
    assert ("<dt>Model map (c)</dt><dd>domain-model → gpt-6-sol (non-discriminating), derived-quantities → gpt-6-astra, "
            "tests → gpt-6-astra</dd>") in header


def test_the_header_carries_each_cells_served_models(root, tmp_path):
    header, _ = _page(_run(root, tmp_path, 6))
    assert f"<dt>Served models ({LABEL})</dt><dd>gpt-6-sol</dd>" in header


def test_an_ungraded_cells_served_models_read_not_recorded(root, tmp_path):  # never an empty set or a zero
    header, _ = _page(_run(root, tmp_path, 6, graded=False))
    assert f"<dt>Served models ({LABEL})</dt><dd>not recorded</dd>" in header


def test_the_coordination_banner_is_in_the_header_and_on_every_scenario6_row(root, tmp_path):
    header, doc = _page(_run(root, tmp_path, 6))
    assert f"<dt>Coordination (scenario 6)</dt><dd>{BANNER}</dd>" in header
    runs = re.search(r'<section id="runs".*?</section>', doc, re.DOTALL).group(0)
    assert f"{LABEL} · {BANNER}" in runs


def test_the_header_names_the_scenario6_allowance_per_harness(root, tmp_path):  # R-74 c6
    header, _ = _page(_run(root, tmp_path, 6))
    assert ("<dt>Scenario-6 allowance</dt><dd>claude-code Agent · copilot task, write_agent, read_agent, list_agents · "
            "codex not qualified</dd>") in header


def test_a_run_with_no_scenario6_cell_shows_none_of_it(root, tmp_path):  # the negative control
    header, doc = _page(_run(root, tmp_path, 5))
    assert "Model map" not in header and "Served models" not in header and "Scenario-6 allowance" not in header
    assert BANNER not in doc
