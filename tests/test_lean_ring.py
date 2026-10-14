"""L-MATRIX: the lean ring (ADR-0022 sections 1 and 3a).

Red first on an assertion; each guard has a mutant in tests/mutations/lean_ring.json.
"""

from pathlib import Path

import pytest

from harness_bench import campaign, config, plan
from harness_bench.errors import BenchError

ROOT = Path(__file__).resolve().parents[1]


def test_lean_codex_ring_is_lean_with_only_the_codex_combo_and_plans_22_cells():
    """L-CODEX-PIN (operator ruling 2026-10-10): Codex's 40 lean cells run as their own 2-batch pair."""
    path = ROOT / "bench/rings/lean-codex.yaml"
    assert path.is_file(), path
    matrix = config.load_yaml(path)
    bom = config.load_yaml(ROOT / "bench/bom.yaml")
    problems = config.Problems()
    config.validate_matrix(matrix, bom, problems, "lean-codex")
    assert problems.items == []
    lean = config.load_yaml(ROOT / "bench/rings/lean.yaml")
    assert matrix["ring"] == {"tag": "lean"}
    assert matrix["combos"] == [{"id": "codex-sol", "harness": "codex", "model": "gpt-6.1-sol"}]
    assert {k: v for k, v in matrix.items() if k != "combos"} == {k: v for k, v in lean.items() if k != "combos"}
    cells = plan.expand(matrix, bom)
    assert len(cells) == 22  # 11 tasks (the ten property tasks and SV1) x 2 arms
    assert {(c.combo, c.harness, c.model) for c in cells} == {("codex-sol", "codex", "gpt-6.1-sol")}


def test_lean_ring_is_e5_pilot_with_tag_lean_plus_sv1_and_plans_66_cells():
    """ADR-0022 Amendment 1 (accepted 2026-10-14): the ten property tasks and SV1, so 11 x 2 arms x 3 combos."""
    matrix = config.load_yaml(ROOT / "bench/rings/lean.yaml")
    bom = config.load_yaml(ROOT / "bench/bom.yaml")
    problems = config.Problems()
    config.validate_matrix(matrix, bom, problems, "lean")
    assert problems.items == []
    pilot = config.load_yaml(ROOT / "bench/rings/e5-pilot.yaml")
    assert matrix["ring"] == {"tag": "lean"}
    assert matrix["bom"] == pilot["bom"] | {"subset": [*pilot["bom"]["subset"], "SV1"]}
    same = lambda m: {k: v for k, v in m.items() if k not in ("ring", "bom")}
    assert same(matrix) == same(pilot)
    assert len(plan.expand(matrix, bom)) == 66


def test_campaign_plan_block_refuses_the_lean_ring_hb_cmp_010(tmp_path):
    """ADR-0022 section 3a: a lean run never enters campaign state."""
    with pytest.raises(BenchError) as exc_info:
        campaign.plan_block(tmp_path, "x", {"ring": {"tag": "lean"}})
    assert exc_info.value.code == "HB-CMP-010", exc_info.value
    assert "ring lean is not a campaign ring" in exc_info.value.message
