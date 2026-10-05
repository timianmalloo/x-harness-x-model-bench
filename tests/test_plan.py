import ast
import hashlib
import importlib.util
import json
import os
import shutil
from copy import deepcopy
from dataclasses import asdict
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

import pytest
from hypothesis import given
from hypothesis import strategies as st

from harness_bench import cli, config, gitsafe, plan, profiles, tools, workspace
from harness_bench.errors import BenchError
from harness_bench.ledger import canonical

ROOT = Path(__file__).resolve().parents[1]


def _arm_cells(blocks=3, arms=("off", "candidate")):
    return [plan.Cell("X1", "v1", 5, "cc-opus", "claude-code", "claude-opus-5-5", arm, rep, 300)
            for rep in range(1, blocks + 1) for arm in arms]


def _matrix2():
    return {"schema": "bench-matrix/2", "repetitions": 3, "ring": {"tag": "pilot"},
            "bom": {"subset": ["X1"]}, "arms": [{"id": "off"}, {"id": "candidate"}],
            "combos": [{"id": "cc-opus", "harness": "claude-code", "model": "claude-opus-5-5"}]}


def _plan2(tmp_path, **overrides):
    ring = tmp_path / "pilot.yaml"
    ring.write_bytes(b'schema: bench-matrix/2\r\nring: {tag: pilot}\r\n')
    args = {"root": ROOT, "matrix": _matrix2(), "bom": config.load_yaml(ROOT / "bench" / "bom.yaml"),
            "run_id": "pilot", "builds": {"claude-code": {"version": "test"}}, "matrix_path": ring,
            "arm_packs": {"off": None, "candidate": {"source": str(tmp_path), "commit": "c" * 40, "revision": 95}}}
    args.update(overrides)
    return plan.build_plan(**args)


def test_cell_arm_preserves_legacy_ids_with_the_frozen_pack_ingredient():
    cell = _arm_cells()[1]
    expected = hashlib.sha256(canonical({"task_version": "v1", "combo": "cc-opus", "pack": "candidate", "rep": 1})).hexdigest()[:16]
    assert cell.id == expected
    assert cell.label == "X1.cc-opus.arm-candidate.r1"
    assert getattr(cell, "arm", None) == "candidate"
    assert "pack" not in asdict(cell)


def test_cell_arm_reads_both_schemas_without_overriding_an_explicit_arm():
    assert plan.cell_arm({"arm": "candidate", "pack": "on"}) == "candidate"
    assert plan.cell_arm({"pack": "on"}) == "on"
    assert plan.cell_arm({"pack": "off"}) == "off"
    with pytest.raises(BenchError, match="HB-USR-002"):
        plan.cell_arm({})


def test_arms_of_upcasts_without_mutating_the_matrix():
    matrix = {"schema": "bench-matrix/1", "packs": ["on", "off"]}
    before = deepcopy(matrix)
    assert plan.arms_of(matrix) == [{"id": "on", "pack": None}, {"id": "off", "pack": None}]
    assert matrix == before
    assert plan.arms_of(_matrix2()) == [{"id": "off", "pack": None}, {"id": "candidate", "pack": None}]


@pytest.mark.parametrize("ids,expected", [([], []), (["off"], []), (["on"], []),
    (["on", "off"], [["off", "on"]]), (["off", "candidate"], [["off", "candidate"]]),
    (["incumbent", "candidate"], [["incumbent", "candidate"]])])
def test_default_comparisons_is_the_single_legacy_and_two_arm_rule(ids, expected):
    assert plan.default_comparisons(ids) == expected


def test_default_comparisons_refuses_three_arms_without_an_explicit_list():
    with pytest.raises(BenchError, match="HB-PLN-002"):
        plan.default_comparisons(["off", "incumbent", "candidate"])


def test_plan_packs_and_arm_pack_read_zero_one_two_and_legacy_packs():
    pack = {"source": "repo", "commit": "c" * 40, "revision": 95}
    second = {**pack, "commit": "d" * 40}
    legacy = {"schema": "bench-plan/1", "pack": pack, "cells": [{"pack": "off"}, {"pack": "on"}]}
    assert plan.plan_packs(legacy) == {"on": pack}
    assert plan.plan_pack(legacy) == pack
    assert plan.arm_pack(legacy, "on") == pack
    assert plan.arm_pack(legacy, "off") is None
    assert plan.plan_comparisons(legacy) == [("off", "on")]
    assert plan.plan_comparisons({**legacy, "cells": [{"pack": "off"}]}) == []
    for packs in ({"off": None}, {"off": None, "candidate": pack},
                  {"off": None, "candidate": pack, "incumbent": second}):
        body = {"schema": "bench-plan/2", "arms": {a: {"pack": p} for a, p in packs.items()},
                "comparisons": [["off", "candidate"]]}
        assert plan.plan_packs(body) == {a: p for a, p in packs.items() if p is not None}
        assert plan.arm_pack(body, "off") is None
        assert plan.plan_comparisons(body) == [("off", "candidate")]
        if len(packs) < 3:
            assert plan.plan_pack(body) == packs.get("candidate")
        else:
            with pytest.raises(BenchError) as error:
                plan.plan_pack(body)
            assert error.value.code == "HB-PLN-005"
            assert "candidate" in error.value.message and "incumbent" in error.value.message
        with pytest.raises(BenchError, match="HB-USR-002"):
            plan.arm_pack(body, "missing")
    with pytest.raises(BenchError, match="HB-USR-002"):
        plan.arm_pack(legacy, "missing")


def test_kind_of_defaults_absent_kind_and_refuses_unknown_values():
    assert plan.kind_of({}) == "measurement"
    assert plan.kind_of({"kind": "discrimination"}) == "discrimination"
    for value in (None, "other", True, [], {}):
        with pytest.raises(BenchError, match="HB-PLN-004"):
            plan.kind_of({"kind": value})


def test_launch_order_matches_hash_keys_and_keeps_blocks_contiguous():
    cells = _arm_cells(3, ("off", "incumbent", "candidate"))
    seed = 17
    blocks = sorted(range(1, 4), key=lambda rep: hashlib.sha256(f"17|block|X1|cc-opus|{rep}".encode()).digest())
    expected = [c.id for rep in blocks for c in sorted([c for c in cells if c.rep == rep],
                key=lambda c: hashlib.sha256(f"17|arm|X1|cc-opus|{rep}|{plan.cell_arm(asdict(c))}".encode()).digest())]
    assert [c.id for c in plan.launch_order(cells, seed)] == expected
    assert [c.id for c in plan.launch_order(list(reversed(cells)), seed)] == expected


@given(st.integers(min_value=0, max_value=2**63 - 1), st.integers(min_value=1, max_value=12))
def test_launch_order_is_a_replayable_permutation(seed, blocks):
    cells = _arm_cells(blocks)
    ordered = plan.launch_order(cells, seed)
    assert sorted(c.id for c in ordered) == sorted(c.id for c in cells)
    assert plan.launch_order(list(reversed(cells)), seed) == ordered
    assert all({c.rep for c in ordered[i:i + 2]} == {ordered[i].rep} for i in range(0, len(cells), 2))


def test_launch_balance_uses_exact_arm_position_means():
    cells = _arm_cells(5)
    assert plan.launch_balance(cells) == Fraction(1, 20)  # ten positions; each arm mean is 1/2 from 9/2
    assert plan.launch_balance(_arm_cells(1)) == Fraction(1, 4)
    assert plan.launch_balance([]) == 0
    assert plan.launch_balance(_arm_cells(3, ("off",))) == 0


def test_the_bound_is_strict(monkeypatch):
    monkeypatch.setattr(plan, "launch_order", lambda cells, seed: list(cells))
    with pytest.raises(BenchError) as error:
        plan.draw_launch_order(_arm_cells(5), draw=lambda: 4)
    assert error.value.code == "HB-PLN-001"


@pytest.mark.parametrize("blocks,arms", [(3, ("off", "candidate")),
    (2, ("off", "a", "b", "c")), (3, ("off", "a", "b", "c"))])
def test_draw_redraws_a_failed_seed_then_stores_the_first_accepted_seed(blocks, arms):
    cells = _arm_cells(blocks, arms)
    failed = next((seed for seed in range(1000) if plan.launch_balance(plan.launch_order(cells, seed)) >= plan.BALANCE_BOUND), None)
    assert failed is not None
    accepted = next(seed for seed in range(1000) if plan.launch_balance(plan.launch_order(cells, seed)) < plan.BALANCE_BOUND)
    draws = iter([failed, accepted])
    seed, ordered, count = plan.draw_launch_order(cells, draw=lambda: next(draws))
    assert seed == accepted and count == 2
    assert ordered == plan.launch_order(cells, accepted)
    assert plan.launch_balance(ordered) < Fraction(1, 20)


def test_draw_cap_names_shape_without_claiming_a_two_block_minimum():
    calls = []
    with pytest.raises(BenchError) as error:
        plan.draw_launch_order(_arm_cells(1, ("off", "a", "b", "c")), draw=lambda: calls.append(0) or 0)
    assert error.value.code == "HB-PLN-001"
    assert len(calls) == plan.MAX_DRAWS == 100
    assert "1 blocks of 4 arms" in error.value.message
    assert "at least 2" not in error.value.message


def test_plan2_freezes_fields_hash_order_and_campaign_verbatim(tmp_path):
    campaign = {"campaign_id": "c", "prereg_hash": None, "identity": {"hash": "a", "components": {}}}
    body = _plan2(tmp_path, campaign=campaign)
    assert body.get("schema") == "bench-plan/2"
    assert body["campaign"] == campaign
    assert "pack" not in body
    assert body["kind"] == "measurement"
    assert body["ring"] == {"tag": "pilot", "hash": plan.tree_hash(tmp_path, [tmp_path / "pilot.yaml"])}
    assert body["matrix"] == _matrix2()
    assert len(body["cells"]) == 6
    assert all("arm" in cell and "pack" not in cell for cell in body["cells"])
    cells = plan.expand(body["matrix"], config.load_yaml(ROOT / "bench" / "bom.yaml"),
                        {"X1": body["tasks"]["X1"]["version_hash"]})
    assert [c.id for c in plan.launch_order(cells, body["launch_seed"])] == [c["cell_id"] for c in body["cells"]]
    assert plan.launch_balance([next(c for c in cells if c.id == row["cell_id"]) for row in body["cells"]]) < Fraction(1, 20)
    assert body["plan_hash"] == plan.plan_hash(body)
    assert plan.load_confirmed(plan.confirm(tmp_path / "run", body).parent) == body


def test_plan2_optional_fields_are_absent_and_explicit_bad_seed_is_refused(tmp_path):
    matrix = _matrix2()
    matrix.pop("ring")
    body = _plan2(tmp_path, matrix=matrix)
    assert "ring" not in body and "campaign" not in body
    assert body.get("kind") == "measurement"
    cells = _arm_cells()
    bad = next((seed for seed in range(1000) if plan.launch_balance(plan.launch_order(cells, seed)) >= Fraction(1, 20)), None)
    assert bad is not None
    with pytest.raises(BenchError, match="HB-PLN-001"):
        _plan2(tmp_path, matrix=matrix, launch_seed=bad)


def test_build_plan_refuses_unknown_kind_through_the_shared_helper(tmp_path):
    with pytest.raises(BenchError, match="HB-PLN-004"):
        _plan2(tmp_path, kind="other")


def test_build_plan_emits_measured_duration_volume_path_and_draw_count(tmp_path, caplog):
    with caplog.at_level("INFO", logger="harness_bench.plan"):
        body = _plan2(tmp_path)
    record = next(row for row in caplog.records if row.message == "Plan built")
    assert record.run_id == body["run_id"] and record.trace_id == body["trace_id"]
    assert record.cell_count == len(body["cells"]) == 6
    assert record.launch_seed == body["launch_seed"] and 1 <= record.launch_draws <= plan.MAX_DRAWS
    assert record.plan_kind == "measurement" and Fraction(record.launch_balance) < Fraction(1, 20)
    assert record.duration_ns >= 0


def test_plan_py_imports_no_campaign_or_identity_module():
    from import_graph import imports

    def forbidden(text):
        return {target for target in imports("src/harness_bench/plan.py", ast.parse(text))
                if target.startswith(("harness_bench.campaign", "harness_bench.identity"))}

    assert forbidden("from . import campaign") == {"harness_bench.campaign"}
    assert forbidden("from harness_bench import identity") == {"harness_bench.identity"}
    assert forbidden((ROOT / "src/harness_bench/plan.py").read_text(encoding="utf-8")) == set()


def test_kind_readers_call_kind_of_instead_of_reading_kind_directly():
    def violations(text):
        tree = ast.parse(text)
        permitted = {id(node) for function in ast.walk(tree) if isinstance(function, ast.FunctionDef)
                     and function.name == "kind_of" for node in ast.walk(function)}

        def plan_value(node):
            return (isinstance(node, ast.Name) and node.id in {"plan", "p", "frozen", "confirmed", "body"}
                    or isinstance(node, ast.Attribute) and node.attr == "plan")

        return [node.lineno for node in ast.walk(tree) if id(node) not in permitted and (
            isinstance(node, ast.Subscript) and plan_value(node.value)
            and isinstance(node.slice, ast.Constant) and node.slice.value == "kind"
            or isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "get"
            and plan_value(node.func.value) and node.args and isinstance(node.args[0], ast.Constant)
            and node.args[0].value == "kind")]

    assert violations('def reader(p):\n    return p["kind"] == "measurement"') == [2]
    assert violations('def reader(p):\n    return p.get("kind") == "measurement"') == [2]
    assert violations('def reader(view):\n    return view.plan["kind"] == "measurement"') == [2]
    assert violations('def archive_row(r):\n    return r["kind"] == "file"') == []
    # Root src/harness_bench; recursive Python files; direct subscript/get on named plan carriers;
    # kind_of alone is exempt. Ledger/archive record kinds are a different domain.
    for path in (ROOT / "src/harness_bench").rglob("*.py"):
        assert violations(path.read_text(encoding="utf-8")) == [], path


def test_grid4_replan_gives_the_same_task_combo_arm_rep_set_and_cell_ids(monkeypatch):
    fixture = json.loads((ROOT / "tests/fixtures/plans/grid4-cells.json").read_text(encoding="utf-8"))
    assert fixture["provenance"]["source"] == "runs/grid-4/plan.json"
    assert len(fixture["provenance"]["sha256"]) == 64
    assert len(fixture["cells"]) == 276
    # EV-17 proves the writer/cell recipe, not a harness probe. Existing probe tests cover this seam.
    monkeypatch.setattr(plan, "_probe_instructions", lambda root, cells, *args: (
        {(c.task, c.arm): 0 for c in cells if c.harness == "copilot"}, []))
    body = plan.build_plan(ROOT, fixture["matrix"], config.load_yaml(ROOT / "bench/bom.yaml"), "grid4-replan",
                           fixture["builds"], fixture["pack"], task_versions=fixture["task_versions"])
    fields = ("cell_id", "task", "task_version", "combo", "arm", "rep")
    expected = {tuple(row[field] for field in fields) for row in fixture["cells"]}
    actual = {tuple(row[field] for field in fields) for row in body.get("cells", [])}
    assert actual == expected


def test_synthetic_profile_record_is_constant_without_loading_a_file(tmp_path):
    record = plan.profile_record(tmp_path, "synthetic")
    assert record == plan.SYNTHETIC_PROFILE_RECORD
    assert record.get("usage_source") == "acp_turn"
    assert record["record_glob"] is None and record["subagent_glob"] is None
    assert record["shutdown_grace_seconds"] == "1"
    canonical(record)


def test_measurement_plan_names_every_nonready_task_and_synthetic_combo(tmp_path):
    root = tmp_path / "root"
    bom = {"version": "test", "tasks": []}
    for n in range(15):
        task = root / "tasks" / f"T{n}"
        task.mkdir(parents=True)
        (task / "task.yaml").write_text('status: draft\n', encoding="utf-8")
        bom["tasks"].append({"id": f"T{n}", "scenario": 5, "budget_minutes": 1})
    matrix = _matrix2()
    matrix["bom"]["subset"] = "full"
    matrix["combos"] = [{"id": "synthetic-reference", "harness": "synthetic", "model": "reference"},
                        {"id": "synthetic-naive", "harness": "synthetic", "model": "naive"}]
    with pytest.raises(BenchError) as error:
        _plan2(tmp_path, root=root, bom=bom, matrix=matrix)
    assert error.value.code == "HB-PLN-004"
    assert all(f"T{n} (draft)" in error.value.message for n in range(15))
    assert all(combo["id"] in error.value.message for combo in matrix["combos"])


def test_a_discrimination_plan_accepts_draft_and_refuses_stub(tmp_path):
    root = tmp_path / "root"
    shutil.copytree(ROOT / "tasks/X1", root / "tasks/X1")
    path = root / "tasks/X1/task.yaml"
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace("status: ready", "status: draft"), encoding="utf-8")
    matrix = _matrix2()
    matrix.pop("ring")
    matrix["arms"] = [{"id": "off"}]
    matrix["combos"] = [{"id": "synthetic-reference", "harness": "synthetic", "model": "reference"},
                        {"id": "synthetic-naive", "harness": "synthetic", "model": "naive"}]
    body = _plan2(tmp_path, root=root, matrix=matrix, kind="discrimination", arm_packs={"off": None},
                  builds={"synthetic": {"version": "test"}})
    assert body.get("kind") == "discrimination"
    assert body["profiles"]["synthetic"] == plan.SYNTHETIC_PROFILE_RECORD
    assert len(body["cells"]) == 6
    path.write_text(text.replace("status: ready", "status: stub"), encoding="utf-8")
    with pytest.raises(BenchError, match="HB-PLN-004"):
        _plan2(tmp_path, root=root, matrix=matrix, kind="discrimination", arm_packs={"off": None})


def test_measurement_plan_refuses_synthetic_even_when_every_task_is_ready(tmp_path):
    matrix = _matrix2()
    matrix["combos"] = [{"id": "synthetic-reference", "harness": "synthetic", "model": "synthetic-1"},
                        {"id": "synthetic-naive", "harness": "synthetic", "model": "synthetic-1"}]
    with pytest.raises(BenchError) as error:
        _plan2(tmp_path, matrix=matrix, builds={"synthetic": {"version": "test"}})
    assert error.value.code == "HB-PLN-004"
    assert "synthetic-reference" in error.value.message and "synthetic-naive" in error.value.message


def test_load_confirmed_reads_legacy_and_refuses_a_future_schema(tmp_path):
    for schema in (None, "bench-plan/1", "bench-plan/9"):
        body = {"schema": schema, "cells": [], "pack": {"revision": 1}}
        if schema is None:
            body.pop("schema")
        body["plan_hash"] = plan.plan_hash(body)
        folder = plan.confirm(tmp_path / str(schema).replace("/", "-"), body).parent
        if schema in (None, "bench-plan/1"):
            assert plan.load_confirmed(folder) == body
        else:
            with pytest.raises(BenchError, match="HB-USR-002"):
                plan.load_confirmed(folder)


def test_parse_binding_partitions_windows_paths_and_at_signs(tmp_path):
    source = str(tmp_path / "repo@part")
    assert plan.parse_binding(f"candidate={source}@{'c' * 40}") == ("candidate", source, "c" * 40)


@pytest.mark.parametrize("text", ["", "candidate", "candidate=repo@" + "c" * 40,
    "off=C:/repo@" + "c" * 40, "candidate=C:/repo@HEAD", "BAD=C:/repo@" + "c" * 40])
def test_parse_binding_refuses_invalid_or_packless_bindings(text):
    with pytest.raises(BenchError, match="HB-PLN-002"):
        plan.parse_binding(text)


def test_resolve_arms_accepts_legacy_roles_and_pinned_matrix_arms(tmp_path):
    binding = (str(tmp_path), "c" * 40)
    expected = {"off": None, "candidate": {"source": binding[0], "commit": binding[1]}}
    assert plan.resolve_arms(_matrix2(), {"candidate": binding}) == expected
    matrix = _matrix2()
    matrix["arms"][1]["pack"] = expected["candidate"]
    assert plan.resolve_arms(matrix, {}) == expected
    assert plan.resolve_arms({"schema": "bench-matrix/1", "packs": ["on", "off"]}, {"on": binding}) == {
        "on": expected["candidate"], "off": None}


@pytest.mark.parametrize("case", ["unbound", "unknown", "off", "pinned", "relative", "commit", "duplicate", "second-off"])
def test_resolve_arms_refuses_each_binding_error(tmp_path, case):
    matrix = _matrix2()
    bindings = {"candidate": (str(tmp_path), "c" * 40)}
    if case == "unbound":
        bindings = {}
    elif case == "unknown":
        bindings["missing"] = bindings["candidate"]
    elif case == "off":
        bindings["off"] = bindings["candidate"]
    elif case == "pinned":
        matrix["arms"][1]["pack"] = {"source": str(tmp_path), "commit": "d" * 40}
    elif case == "relative":
        bindings["candidate"] = ("relative", "c" * 40)
    elif case == "commit":
        bindings["candidate"] = (str(tmp_path), "HEAD")
    elif case == "duplicate":
        matrix["arms"].append({"id": "candidate"})
    else:
        matrix["arms"].append({"id": "off"})
    with pytest.raises(BenchError, match="HB-PLN-002"):
        plan.resolve_arms(matrix, bindings)


def test_wave1_matrix_parses_and_walking_skeleton_selects_it():
    matrix_path = ROOT / "bench" / "matrix.wave1.yaml"
    matrix = config.load_yaml(matrix_path)
    bom = config.load_yaml(ROOT / "bench" / "bom.yaml")
    problems = config.Problems()
    config.validate_matrix(matrix, bom, problems, str(matrix_path))
    assert problems.items == []
    assert matrix["schema"] == "bench-matrix/1"
    assert matrix["bom"]["subset"] == ["X1"]
    assert matrix["repetitions"] == 1 and matrix["packs"] == ["on", "off"]
    assert [(c["id"], c["harness"], c["model"]) for c in matrix["combos"]] == [
        ("copilot-sol", "copilot", "gpt-6-sol"),
        ("codex-sol", "codex", "gpt-6-sol"),
        ("cc-opus", "claude-code", "claude-opus-5-5"),
    ]
    assert len(plan.expand(matrix, bom)) == 6

    spec = importlib.util.spec_from_file_location("walking_skeleton_selection", ROOT / "tests" / "e2e" / "test_walking_skeleton.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    marker = next(mark for mark in module.test_the_walking_skeleton_runs_end_to_end.pytestmark if mark.name == "parametrize")
    assert marker.kwargs["ids"] == ["phase1", "wave1"]
    assert marker.args[1] == [("phase1", "bench/matrix.phase1.yaml"), ("wave1", "bench/matrix.wave1.yaml")]
    assert {mark.name for mark in module.pytestmark} == {"native", "credentials"}


def _inputs(subset):
    bom = config.load_yaml(ROOT / "bench" / "bom.yaml")
    m = config.load_yaml(ROOT / "bench" / "matrix.example.yaml")
    m["bom"]["subset"] = subset
    return m, bom


def test_full_grid_matches_proposal_run_count():
    # Proposal: 24 tasks x 4 combos x pack on/off x 3 reps = 576 runs, plus the ten property-task stubs of BOM 0.6
    # (W0, docs/design/eval-seam-contracts.md section 1): 34 x 4 x 2 x 3 = 816. Fixture tasks are never in it.
    # expand enumerates; build_plan separately refuses nonready tasks (W1-A §3.5).
    m, bom = _inputs("full")
    assert len(plan.expand(m, bom)) == 816


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
    assert len({(c.task, c.arm, c.rep) for c in cells[:n]}) == 1


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
    args = {"root": ROOT, "matrix": m, "bom": bom, "run_id": "r1", "builds": builds, "pack": pack, "parallelism": 2}
    args.update(over)
    return plan.build_plan(**args)


def test_phase1_plan_has_four_cells_and_every_recorded_field():
    p = _phase1_plan()
    assert len(p["cells"]) == 4
    assert {(c["combo"], c["arm"]) for c in p["cells"]} == {("cc-sonnet", "on"), ("cc-sonnet", "off"), ("codex-sol", "on"), ("codex-sol", "off")}
    for key in ("schema", "run_id", "plan_hash", "trace_id", "matrix_hash", "tasks", "builds", "arms", "parameters",
                "price_list_hash", "envelope_seconds"):
        assert key in p, key
    assert len(p["trace_id"]) == 32 and int(p["trace_id"], 16)
    assert p["parameters"]["parallelism"] == 2


def test_plan_records_the_host_platform():  # ADR-0013 Amendment 1 section 5
    import sys

    assert _phase1_plan()["platform"] == sys.platform


def test_plan_records_each_profiles_shutdown_grace():  # PR-3
    p = _phase1_plan()
    assert {h: record["shutdown_grace_seconds"] for h, record in p["profiles"].items()} == {
        "claude-code": "10", "codex": "10"}


def test_stop_parameters_are_frozen_with_the_ruling_units():  # P-1
    p = _phase1_plan()
    assert p["parameters"]["decision_timeout"] == 1800
    assert p["parameters"]["spend_cap_tokens"] is None
    assert _phase1_plan(parameters={"decision_timeout": 120, "spend_cap_tokens": 1000})["parameters"]["spend_cap_tokens"] == 1000


def test_stop_parameters_refuse_non_positive_values():
    for parameters in ({"decision_timeout": 0}, {"decision_timeout": -1}, {"spend_cap_tokens": 0},
                       {"spend_cap_tokens": -1}, {"spend_cap_tokens": True}):
        with pytest.raises(BenchError) as error:
            _phase1_plan(parameters=parameters)
        assert error.value.code == "HB-USR-002"


def test_plan_freezes_the_builds_unrecorded_self_report_reason():  # R-47 condition 3, null path
    builds = {"claude-code": {"agent_version": None, "agent_version_reason": "ACP initialize requires a live handshake"},
              "codex": {"agent_version": None, "agent_version_reason": "ACP initialize requires a live handshake"}}
    p = _phase1_plan(builds=builds)
    assert p["builds"] == builds


def test_an_old_confirmed_plan_missing_a_parameter_is_refused(tmp_path):  # P-2
    p = _phase1_plan()
    p["parameters"].pop("git_timeout")
    p["plan_hash"] = plan.plan_hash(p)
    plan.confirm(tmp_path / "runs" / "old", p)
    with pytest.raises(BenchError) as error:
        plan.require_run_parameters(plan.load_confirmed(tmp_path / "runs" / "old"))
    assert error.value.code == "HB-USR-002"
    assert "git_timeout" in error.value.message


def test_row15_supports_parallelism_four_and_refuses_five():  # R-38 condition 2
    assert plan.PHASE1_MAX_PARALLELISM == 4
    assert _phase1_plan(parallelism=4)["parameters"]["parallelism"] == 4
    with pytest.raises(BenchError):
        _phase1_plan(parallelism=5)


def test_the_plan_freezes_each_task_prompt_verbatim_with_its_hash():  # US-10: the prompt the agent receives
    p = _phase1_plan()
    raw = (ROOT / "tasks" / "X1" / "prompt.md").read_bytes().decode("utf-8")
    assert p["tasks"]["X1"]["prompt"] == raw
    assert p["tasks"]["X1"]["prompt_sha256"] == hashlib.sha256(raw.encode("utf-8")).hexdigest()


def test_the_plan_freezes_each_task_model_map(tmp_path):  # seam S3: views read the run, not today's task.yaml (US-11)
    assert _phase1_plan()["tasks"]["X1"]["model_map"] is None  # X1 declares none
    root = tmp_path / "root"
    shutil.copytree(ROOT / "tasks" / "X1", root / "tasks" / "X1")
    shutil.copytree(ROOT / "bench", root / "bench")
    task_yaml = root / "tasks" / "X1" / "task.yaml"
    task_yaml.write_text(task_yaml.read_text(encoding="utf-8").replace("model_map: null", "model_map:\n  implement: gpt-6-sol"),
                         encoding="utf-8")
    assert _phase1_plan(root=root)["tasks"]["X1"]["model_map"] == {"implement": "gpt-6-sol"}


def test_the_plan_freezes_each_task_graders_list(tmp_path):  # seam S-1: the pass reads the run's list, not today's task.yaml
    assert _phase1_plan()["tasks"]["X1"]["graders"] == ["correctness", "cost"]  # X1's task.yaml, verbatim
    root = tmp_path / "root"
    shutil.copytree(ROOT / "tasks" / "X1", root / "tasks" / "X1")
    shutil.copytree(ROOT / "bench", root / "bench")
    task_yaml = root / "tasks" / "X1" / "task.yaml"
    task_yaml.write_text(task_yaml.read_text(encoding="utf-8").replace("  - cost\n", "  - cost\n  - process\n"), encoding="utf-8")
    assert _phase1_plan(root=root)["tasks"]["X1"]["graders"] == ["correctness", "cost", "process"]


def test_tree_hash_is_the_one_recipe_path_nul_lf_bytes_nul_in_sorted_path_order(tmp_path):  # seam S-2 (R-59 c1)
    (tmp_path / "b").mkdir()
    (tmp_path / "b" / "y.md").write_bytes(b"one\r\ntwo\n")
    (tmp_path / "a.yaml").write_bytes(b"k: v\n")
    expected = hashlib.sha256(b"a.yaml\0k: v\n\0" b"b/y.md\0one\ntwo\n\0").hexdigest()
    assert plan.tree_hash(tmp_path, [tmp_path / "b" / "y.md", tmp_path / "a.yaml"]) == expected  # any order in, sorted out
    assert plan.tree_hash(tmp_path, []) == hashlib.sha256(b"").hexdigest()


def test_task_version_hash_is_tree_hash_over_every_task_file(monkeypatch):  # seam S-2: one recipe, one definition
    task = ROOT / "tasks" / "X1"
    files = sorted(p for p in task.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    assert plan.task_version_hash(task) == plan.tree_hash(task, files)
    seen = []
    monkeypatch.setattr(plan, "tree_hash", lambda base, fs: seen.append((base, sorted(fs))) or "spy")
    assert (plan.task_version_hash(task), seen) == ("spy", [(task, files)])


def test_cmd_plan_refuses_a_changed_frozen_task_before_building_a_plan(monkeypatch, tmp_path, capsys):  # seam S-3 (R-59 c5)
    root = tmp_path / "root"
    shutil.copytree(ROOT / "bench", root / "bench")
    shutil.copytree(ROOT / "tasks" / "X1", root / "tasks" / "X1")
    (root / "bench" / "task-freeze.yaml").write_text(f"schema: bench-task-freeze/1\ntasks: {{X1: '{'0' * 64}'}}\n", encoding="utf-8")
    actual = plan.task_version_hash(root / "tasks" / "X1")
    monkeypatch.setattr(cli.tools, "resolve", lambda path: {})
    monkeypatch.setattr(cli.plan, "build_plan", lambda *a, **k: pytest.fail("a plan was built over a changed frozen task"))
    args = SimpleNamespace(root=str(root), matrix=str(root / "bench" / "matrix.phase1.yaml"), tools_dir=str(tmp_path / "t"),
                           cells_root=str(tmp_path / "c"), pack_source=str(tmp_path / "p"), run_id="p", parallelism=2,
                           json=False, confirm=False, decision_timeout_minutes=30, spend_cap_tokens=None, arm=[], campaign=None)
    assert cli.cmd_plan(args) == cli.INVALID
    assert capsys.readouterr().err == f"x tasks/X1 changed while frozen (R-59 c5): {actual} != {'0' * 64}\n"


def test_the_plan_records_each_harness_profile_it_uses():  # grading and views read the run, not today's files (US-26)
    p = _phase1_plan()
    assert p["profiles"] == {
        "claude-code": {"profile_hash": plan.file_hash(ROOT / "bench" / "profiles" / "claude-code.yaml"),
                        "vendor": "anthropic", "usage_source": "acp_turn", "auxiliary_models": ["claude-haiku-4-5"],
                            "record_glob": "projects/**/{session_id}.jsonl", "shutdown_grace_seconds": "10",
                        "subagent_glob": "projects/**/{session_id}/subagents/agent-*.jsonl"},
        "codex": {"profile_hash": plan.file_hash(ROOT / "bench" / "profiles" / "codex.yaml"),
                  "vendor": "openai", "usage_source": "native_record", "auxiliary_models": [],
                      "record_glob": "sessions/**/rollout-*-{session_id}.jsonl", "shutdown_grace_seconds": "10",
                  "subagent_glob": "sessions/**/rollout-*.jsonl"},
    }


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
        _phase1_plan(parallelism=5)


def test_a_combo_id_that_breaks_the_status_label_regex_is_refused_at_plan_time():  # T4-5
    m = config.load_yaml(ROOT / "bench" / "matrix.phase1.yaml")
    m["combos"][0]["id"] = "cc sonnet"  # a space is not in the status label pattern
    with pytest.raises(BenchError) as e:
        _phase1_plan(matrix=m)
    assert e.value.code == "HB-USR-002"


def test_instruction_list_uses_the_given_fake_exe_workspace_and_environment(monkeypatch, tmp_path):
    calls = []
    fake_exe = tmp_path / "fake-copilot.exe"
    ws = tmp_path / "workspace"
    env = {"COPILOT_HOME": str(tmp_path / "home")}

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))
        return SimpleNamespace(returncode=0, timed_out=False, stdout='[{"label":"AGENTS.md"}]', stderr="")

    monkeypatch.setattr(plan, "procs", SimpleNamespace(run=fake_run), raising=False)
    assert plan.instruction_list(fake_exe, ws, env) == [{"label": "AGENTS.md"}]
    assert calls == [([str(fake_exe), "instruction", "list", "--json"],
                      {"cwd": str(ws), "env": env, "timeout": 120})]


def test_instruction_list_refuses_a_non_list_result_from_the_fake_exe(monkeypatch, tmp_path):
    monkeypatch.setattr(plan, "procs", SimpleNamespace(run=lambda *a, **k: SimpleNamespace(
        returncode=0, timed_out=False, stdout='{"instructions":[]}', stderr="")), raising=False)
    with pytest.raises(BenchError) as e:
        plan.instruction_list(tmp_path / "fake-copilot.exe", tmp_path, {})
    assert e.value.code == "HB-PRE-008"


def test_instruction_list_reports_nonzero_exit(monkeypatch, tmp_path):
    monkeypatch.setattr(plan, "procs", SimpleNamespace(run=lambda *a, **k: SimpleNamespace(
        returncode=7, timed_out=False, stdout="", stderr="instruction error")), raising=False)
    with pytest.raises(BenchError) as error:
        plan.instruction_list(tmp_path / "copilot.exe", tmp_path, {})
    assert error.value.code == "HB-PRE-008"
    assert "instruction error" in str(error.value)


def test_instruction_list_reports_invalid_json(monkeypatch, tmp_path):
    monkeypatch.setattr(plan, "procs", SimpleNamespace(run=lambda *a, **k: SimpleNamespace(
        returncode=0, timed_out=False, stdout="not json", stderr="")), raising=False)
    with pytest.raises(BenchError) as error:
        plan.instruction_list(tmp_path / "copilot.exe", tmp_path, {})
    assert error.value.code == "HB-PRE-008"
    assert "did not return JSON" in str(error.value)


def test_instruction_list_reports_timeout(monkeypatch, tmp_path):
    result = SimpleNamespace(returncode=1, timed_out=True, stdout="", stderr="")
    monkeypatch.setattr(plan, "procs", SimpleNamespace(run=lambda *a, **k: result), raising=False)
    with pytest.raises(BenchError) as error:
        plan.instruction_list(tmp_path / "copilot.exe", tmp_path, {})
    assert error.value.code == "HB-PRE-008"
    assert "timed out after 120 s" in str(error.value)


def test_instruction_list_reports_truncated_stdout(monkeypatch, tmp_path):
    result = SimpleNamespace(returncode=0, timed_out=False, stdout='[{"label":', stderr="")
    monkeypatch.setattr(plan, "procs", SimpleNamespace(run=lambda *a, **k: result), raising=False)
    with pytest.raises(BenchError) as error:
        plan.instruction_list(tmp_path / "copilot.exe", tmp_path, {})
    assert error.value.code == "HB-PRE-008"
    assert "truncated" in str(error.value)


def _fake_copilot_plan(monkeypatch, tmp_path, listing):
    from harness_bench import workspace

    m = config.load_yaml(ROOT / "bench" / "matrix.phase1.yaml")
    m["combos"] = [{"id": "copilot-sol", "harness": "copilot", "model": "gpt-6-sol"}]
    m["repetitions"] = 2
    bom = config.load_yaml(ROOT / "bench" / "bom.yaml")
    build = SimpleNamespace(exe=tmp_path / "fake-copilot.exe")
    resolved_dirs = []

    def resolve(tools_dir):
        resolved_dirs.append(tools_dir)
        return {"copilot": build}

    monkeypatch.setattr(plan, "tools", SimpleNamespace(resolve=resolve, check_build=lambda *_: None), raising=False)
    monkeypatch.setattr(plan, "profile_record", lambda *_: {"profile_hash": "fake"})
    monkeypatch.setattr(plan.profiles, "load", lambda *_: SimpleNamespace(cell_env=lambda base, home, build, model, traceparent: {
        "COPILOT_HOME": str(home)}))
    monkeypatch.setattr(workspace, "check_cells_root", lambda *_: None)
    monkeypatch.setattr(workspace, "task_source", lambda *_: tmp_path / "source")

    def copy(_source, dest):
        dest.mkdir(parents=True)
        return dest

    monkeypatch.setattr(workspace, "cell_working_copy", copy)
    monkeypatch.setattr(workspace, "pack_checkout", lambda *_: tmp_path / "pack")
    def install_pack(_pack_dir, ws, **_kwargs):
        (ws / "AGENTS.md").write_text("installed", encoding="utf-8")
        return []

    monkeypatch.setattr(workspace, "install_pack", install_pack)
    calls = []

    def fake_list(exe, ws, env):
        calls.append((exe, ws, env))
        return listing(ws)

    monkeypatch.setattr(plan, "instruction_list", fake_list, raising=False)
    args = {"root": ROOT, "matrix": m, "bom": bom, "run_id": "copilot-plan", "builds": {"copilot": {
        "version": "1.0.89-1", "sha256": "a" * 64}}, "pack": {"source": str(tmp_path / "pack-source"),
        "commit": "c" * 40, "revision": 95}}
    args["tools_dir"] = tmp_path / "custom-tools"
    args["cells_root"] = tmp_path / "cells-root"
    return args, calls, resolved_dirs


def test_copilot_plan_lists_once_per_task_pack_build_and_freezes_counts(monkeypatch, tmp_path):
    args, calls, resolved_dirs = _fake_copilot_plan(monkeypatch, tmp_path, lambda ws: [
        {"label": "AGENTS.md"}, {"label": "CLAUDE.md"}] if (ws / "AGENTS.md").is_file() else [])
    p = plan.build_plan(**args)
    assert len(calls) == 2
    assert resolved_dirs == [args["tools_dir"]]
    assert all(ws.is_relative_to(args["cells_root"]) for _, ws, _ in calls)
    assert not list(args["cells_root"].glob("bench-plan-*"))
    assert {(c["arm"], c["instruction_count"]) for c in p["cells"]} == {("off", 0), ("on", 2)}
    assert len(p["instruction_lists"]) == 2
    assert all(c["build_sha256"] == "a" * 64 for c in p["instruction_lists"])
    assert {(c["arm"], c["count"]) for c in p["instruction_lists"]} == {("off", 0), ("on", 2)}
    assert next(c for c in p["instruction_lists"] if c["arm"] == "off")["instructions"] == []


def test_copilot_plan_projects_instructions_to_string_identity_fields_and_keeps_canonical(monkeypatch, tmp_path):
    """A boolean field in the exe's instruction rows (defaultDisabled) must not break the ledger's
    canonical encoder (no bools) once the plan is frozen (defect: slice-5 worker)."""
    raw = [{"id": 3, "label": "AGENTS.md", "location": "repository", "type": True,
            "sourcePath": "AGENTS.md", "defaultDisabled": False}]
    args, _, _ = _fake_copilot_plan(monkeypatch, tmp_path, lambda ws: raw if (ws / "AGENTS.md").is_file() else [])
    p = plan.build_plan(**args)
    on_list = next(c for c in p["instruction_lists"] if c["arm"] == "on")
    assert on_list["count"] == 1
    assert on_list["instructions"] == [{"label": "AGENTS.md", "location": "repository", "sourcePath": "AGENTS.md"}]
    canonical(p)  # ledger canonical forbids bool; build_plan already calls plan_hash internally


def test_copilot_plan_refuses_a_nonempty_pack_off_instruction_list(monkeypatch, tmp_path):
    args, _, _ = _fake_copilot_plan(monkeypatch, tmp_path, lambda ws: [{"label": "leaked"}])
    with pytest.raises(BenchError) as e:
        plan.build_plan(**args)
    assert e.value.code == "HB-PRE-008"


def test_copilot_plan_installs_pack_before_listing_instructions(monkeypatch, tmp_path):
    args, _, _ = _fake_copilot_plan(monkeypatch, tmp_path, lambda ws: [
        {"label": "AGENTS.md"}] if (ws / "AGENTS.md").is_file() else [])
    p = plan.build_plan(**args)
    assert next(item for item in p["instruction_lists"] if item["arm"] == "on")["count"] == 1


def test_copilot_plan_removes_probe_after_instruction_error(monkeypatch, tmp_path):
    args, _, _ = _fake_copilot_plan(monkeypatch, tmp_path, lambda ws: [{"label": "leaked"}])
    with pytest.raises(BenchError, match="HB-PRE-008"):
        plan.build_plan(**args)
    assert not list(args["cells_root"].glob("bench-plan-*"))


def test_copilot_plan_logs_failed_cleanup_without_masking_instruction_error(monkeypatch, tmp_path, caplog):
    args, _, _ = _fake_copilot_plan(monkeypatch, tmp_path, lambda ws: [{"label": "leaked"}])
    original_rmtree = plan.shutil.rmtree

    def fail_probe_cleanup(path, **kwargs):
        if path.name.startswith("bench-plan-"):
            raise OSError("locked probe")
        return original_rmtree(path, **kwargs)

    monkeypatch.setattr(plan.shutil, "rmtree", fail_probe_cleanup)
    with pytest.raises(BenchError, match="HB-PRE-008"):
        plan.build_plan(**args)
    leftover = next(args["cells_root"].glob("bench-plan-*"))
    assert str(leftover) in caplog.text
    monkeypatch.setattr(plan.shutil, "rmtree", original_rmtree)
    original_rmtree(leftover)


def test_cmd_plan_passes_configured_tools_and_cells_roots_to_probe(monkeypatch, tmp_path):
    matrix = config.load_yaml(ROOT / "bench" / "matrix.phase1.yaml")
    bom = config.load_yaml(ROOT / "bench" / "bom.yaml")
    real = config.load_yaml  # bench/task-freeze.yaml is read for real (seam S-3)
    monkeypatch.setattr(cli.config, "load_yaml", lambda path: {"bom.yaml": bom, "matrix.phase1.yaml": matrix}.get(Path(path).name)
                        or real(path))
    monkeypatch.setattr(cli.config, "validate_matrix", lambda *args: None)
    monkeypatch.setattr(cli.tools, "resolve", lambda path: {})
    monkeypatch.setattr(cli, "_pack_record", lambda *args: {"source": "pack", "commit": "c" * 40, "revision": 1})
    monkeypatch.setattr(cli.gitsafe, "git", lambda *a, **k: SimpleNamespace(stdout="c" * 40 + "\n"))
    received = {}

    def fake_build_plan(*args, **kwargs):
        received.update(kwargs)
        return {"cells": [], "builds": {}, "arms": {"on": {"pack": {"revision": 1, "commit": "c" * 40}}}, "launch_seed": 1,
                "parameters": {"parallelism": 2, **kwargs["parameters"]}, "envelope_seconds": 0, "price_list_hash": ""}

    monkeypatch.setattr(cli.plan, "build_plan", fake_build_plan)
    args = SimpleNamespace(root=str(ROOT), matrix=str(ROOT / "bench" / "matrix.phase1.yaml"),
                           tools_dir=str(tmp_path / "custom-tools"), cells_root=str(tmp_path / "cells-root"),
                           pack_source=str(tmp_path / "pack"), run_id="p", parallelism=2, json=False, confirm=False,
                           decision_timeout_minutes=30, spend_cap_tokens=None, arm=[], campaign=None)
    assert cli.cmd_plan(args) == 0
    assert received["tools_dir"] == Path(args.tools_dir)
    assert received["cells_root"] == Path(args.cells_root)


@pytest.mark.native
@pytest.mark.workstation
def test_pinned_copilot_instruction_list_repeats_for_both_real_working_copies(base):
    # The primary checkout holds the installed build and its sibling holds the pack, from any worktree path (also a temp one).
    common = gitsafe.git(["rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=ROOT, timeout=60).stdout.strip()
    primary = Path(common).parent
    tools_dir = ROOT / ".tools" / "harness"
    if not tools_dir.exists():
        tools_dir = primary / ".tools" / "harness"
    exe = tools.resolve(tools_dir)["copilot"].exe
    pack_source = primary.parent / "ai-forward"
    commit = gitsafe.git(["rev-parse", "HEAD"], cwd=pack_source, timeout=60).stdout.strip()
    source = workspace.task_source(ROOT / "tasks" / "X1", plan.task_version_hash(ROOT / "tasks" / "X1"), base / "sources")
    results = {}
    for arm in ("off", "on"):
        ws = workspace.cell_working_copy(source, base / "cells" / arm / "ws")
        if arm == "on":
            pack_dir = workspace.pack_checkout(pack_source, commit, base / "pack")
            workspace.install_pack(pack_dir, ws, project="X1", timeout=300)
        home = base / "homes" / arm
        home.mkdir(parents=True)
        env = profiles.load(ROOT, "copilot").cell_env(dict(os.environ), home, tools.resolve(tools_dir)["copilot"],
                                                       "gpt-6-sol", "")
        results[arm] = [plan.instruction_list(exe, ws, env) for _ in range(2)]
    assert results["off"] == [[], []]
    assert results["on"][0] == results["on"][1]
    assert any(row.get("sourcePath") == "AGENTS.md" for row in results["on"][0])
