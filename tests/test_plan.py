import json
import shutil
from pathlib import Path

import pytest

from harness_bench import config, plan
from harness_bench.errors import BenchError

ROOT = Path(__file__).resolve().parents[1]


def _inputs(subset):
    bom = config.load_yaml(ROOT / "bench" / "bom.yaml")
    m = config.load_yaml(ROOT / "bench" / "matrix.example.yaml")
    m["bom"]["subset"] = subset
    return m, bom


def test_full_grid_matches_proposal_run_count():
    # Proposal: 24 tasks x 4 combos x pack on/off x 3 reps = 576 runs. Fixture tasks are never in it.
    m, bom = _inputs("full")
    assert len(plan.expand(m, bom)) == 576


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


def test_fixture_task_is_selectable_by_id_only():
    m, bom = _inputs(["X1"])
    cells = plan.expand(m, bom)
    assert {c.task for c in cells} == {"X1"}
    assert all(c.task != "X1" for c in plan.expand(*_inputs("full")))


# cell identity (ADR-0006) -------------------------------------------------------------------

def test_cell_id_is_a_deterministic_hash_of_its_ingredients():
    a = plan.Cell("X1", "v1", 5, "cc-sonnet", "claude-code", "claude-sonnet-5", "on", 1, 300)
    b = plan.Cell("X1", "v1", 5, "cc-sonnet", "claude-code", "claude-sonnet-5", "on", 1, 300)
    assert a.id == b.id and len(a.id) == 16
    for changed in (plan.Cell("X1", "v2", 5, "cc-sonnet", "claude-code", "claude-sonnet-5", "on", 1, 300),
                    plan.Cell("X1", "v1", 5, "cc-sonnet", "claude-code", "claude-sonnet-5", "off", 1, 300),
                    plan.Cell("X1", "v1", 5, "cc-sonnet", "claude-code", "claude-sonnet-5", "on", 2, 300)):
        assert changed.id != a.id


def test_task_version_hash_changes_with_any_task_file(tmp_path):
    task = tmp_path / "X9"
    shutil.copytree(ROOT / "tasks" / "X1", task)
    before = plan.task_version_hash(task)
    assert plan.task_version_hash(task) == before
    (task / "tests" / "extra.txt").write_text("x", encoding="utf-8")
    assert plan.task_version_hash(task) != before


# envelope, plan hash, confirmation (US-6) -----------------------------------------------------

def test_envelope_is_budget_sum_over_parallelism_plus_the_largest_budget():
    cells = [plan.Cell("T", "v", 5, f"c{i}", "codex", "m", "on", 1, s) for i, s in enumerate((300, 300, 600))]
    assert plan.envelope_seconds(cells, parallelism=2) == 600 + 600  # ceil(1200 / 2) + max(600)
    assert plan.envelope_seconds([], parallelism=2) == 0


def _phase1_plan(**over):
    m = config.load_yaml(ROOT / "bench" / "matrix.phase1.yaml")
    bom = config.load_yaml(ROOT / "bench" / "bom.yaml")
    builds = {"claude-code": {"version": "2.1.274", "sha256": "a" * 64}, "codex": {"version": "0.156.0", "sha256": "b" * 64}}
    pack = {"source": "../ai-forward", "commit": "c" * 40, "revision": 92}
    args = dict(root=ROOT, matrix=m, bom=bom, run_id="r1", builds=builds, pack=pack, parallelism=2)
    args.update(over)
    return plan.build_plan(**args)


def test_phase1_plan_has_four_cells_and_every_recorded_field():
    p = _phase1_plan()
    assert len(p["cells"]) == 4
    assert {(c["combo"], c["pack"]) for c in p["cells"]} == {("cc-sonnet", "on"), ("cc-sonnet", "off"), ("codex-sol", "on"), ("codex-sol", "off")}
    for key in ("schema", "run_id", "plan_hash", "trace_id", "matrix_hash", "tasks", "builds", "pack", "parameters",
                "price_list_hash", "envelope_seconds"):
        assert key in p, key
    assert len(p["trace_id"]) == 32 and int(p["trace_id"], 16)
    assert p["parameters"]["parallelism"] == 2


def test_plan_hash_covers_every_field():
    p = _phase1_plan()
    assert plan.plan_hash(p) == p["plan_hash"]
    tampered = json.loads(json.dumps(p))
    tampered["cells"][0]["model"] = "other"
    assert plan.plan_hash(tampered) != p["plan_hash"]


def test_confirm_freezes_the_plan_and_refuses_a_second_write(tmp_path):
    p = _phase1_plan()
    path = plan.confirm(tmp_path / "runs" / "r1", p)
    assert json.loads(path.read_text(encoding="utf-8"))["plan_hash"] == p["plan_hash"]
    with pytest.raises(BenchError) as e:
        plan.confirm(tmp_path / "runs" / "r1", p)
    assert e.value.code == "HB-USR-002"
    assert plan.load_confirmed(tmp_path / "runs" / "r1")["plan_hash"] == p["plan_hash"]


def test_load_confirmed_detects_an_edited_plan(tmp_path):
    p = _phase1_plan()
    path = plan.confirm(tmp_path / "runs" / "r1", p)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["parameters"]["parallelism"] = 9
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(BenchError) as e:
        plan.load_confirmed(tmp_path / "runs" / "r1")
    assert e.value.code == "HB-LED-002"


def test_load_confirmed_without_a_plan_is_unknown_run(tmp_path):
    with pytest.raises(BenchError) as e:
        plan.load_confirmed(tmp_path / "runs" / "missing")
    assert e.value.code == "HB-USR-001"


def test_parallelism_above_the_phase1_cap_is_refused():
    with pytest.raises(BenchError):
        _phase1_plan(parallelism=3)
