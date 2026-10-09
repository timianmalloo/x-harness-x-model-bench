"""L-MATRIX: the lean ring (ADR-0022 sections 1 and 3a).

Red first on an assertion; each guard has a mutant in tests/mutations/lean_ring.json.
"""

from pathlib import Path

from harness_bench import config

ROOT = Path(__file__).resolve().parents[1]


def test_lean_ring_validates_and_is_e5_pilot_with_tag_lean():
    matrix = config.load_yaml(ROOT / "bench/rings/lean.yaml")
    problems = config.Problems()
    config.validate_matrix(matrix, config.load_yaml(ROOT / "bench/bom.yaml"), problems, "lean")
    assert problems.items == []
    pilot = config.load_yaml(ROOT / "bench/rings/e5-pilot.yaml")
    assert matrix["ring"] == {"tag": "lean"}
    assert {k: v for k, v in matrix.items() if k != "ring"} == {k: v for k, v in pilot.items() if k != "ring"}
