from pathlib import Path

from harness_bench import config, plan

ROOT = Path(__file__).resolve().parents[1]


def _inputs(subset):
    bom = config.load_yaml(ROOT / "bench" / "bom.yaml")
    m = config.load_yaml(ROOT / "bench" / "matrix.example.yaml")
    m["bom"]["subset"] = subset
    return m, bom


def test_full_grid_matches_proposal_run_count():
    # Proposal: 22 tasks x 4 combos x pack on/off x 3 reps = 528 runs.
    m, bom = _inputs("full")
    assert len(plan.expand(m, bom)) == 528


def test_smoke_grid_is_one_task_per_scenario():
    m, bom = _inputs("smoke")
    cells = plan.expand(m, bom)
    assert sorted({c.scenario for c in cells}) == [1, 2, 3, 4, 5, 6]
    assert len(cells) == 6 * 4 * 2 * 3


def test_cell_ids_are_unique():
    m, bom = _inputs("full")
    ids = [c.id for c in plan.expand(m, bom)]
    assert len(ids) == len(set(ids))


def test_combos_are_interleaved_innermost():
    m, bom = _inputs("smoke")
    cells = plan.expand(m, bom)
    n = len(m["combos"])
    assert [c.combo for c in cells[:n]] == [c["id"] for c in m["combos"]]
    assert len({(c.task, c.pack, c.rep) for c in cells[:n]}) == 1


def test_batches_respect_coord_run_worker_cap():
    m, bom = _inputs("full")
    groups = plan.batches(plan.expand(m, bom))
    assert all(1 <= len(g) <= plan.MAX_WORKERS_PER_CONTRACT for g in groups)
    assert sum(len(g) for g in groups) == 528
