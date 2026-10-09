"""L-MATRIX M4: the pooling check of ADR-0022 section 3, one test per rule.

`board.pool_check(pool, view)` runs compare's preconditions (`board.check_comparable`) plus three lean rules. Each red
fails on an assert (the function's presence is asserted before it is called). Mutants: tests/mutations/lean_ring.json.
"""

from __future__ import annotations

import copy
import dataclasses

import pytest

from harness_bench import board, config, views
from harness_bench.errors import BenchError

ARM_ON = "cand"
COMBO = {"id": "cc-opus", "harness": "claude-code", "model": "claude-opus-5-5"}


def _plan(run_id: str) -> dict:
    cells = [{"cell_id": f"{task}-{arm}", "label": f"{task}/{arm}", "task": task, "task_version": "v1", "scenario": 1,
              "combo": COMBO["id"], "harness": COMBO["harness"], "model": COMBO["model"], "arm": arm, "rep": 1,
              "budget_seconds": 600} for task in ("S1", "S2") for arm in (config.ARM_OFF, ARM_ON)]
    return {"run_id": run_id, "created_at": f"{run_id}-at", "trace_id": f"{run_id}-trace", "launch_seed": len(run_id),
            "plan_hash": f"{run_id}-hash", "platform": "win32", "bom_version": "0.4",
            "ring": {"tag": "lean", "hash": "ring-hash"}, "matrix": {"combos": [dict(COMBO)]},
            "arms": {config.ARM_OFF: {"pack": None}, ARM_ON: {"pack": {"revision": 99, "commit": "e1f8ad5e"}}},
            "builds": {"claude-code": {"version": "2.1"}}, "profiles": {"claude-code": {"profile_hash": "p1"}},
            "instruction_lists": {f"S1/{ARM_ON}": ["AGENTS.md"]}, "parameters": {"parallelism": 2},
            "envelope_seconds": 1200, "cells": cells}


def _run(run_id: str, plan: dict | None = None) -> views.RunView:
    return views.RunView(run_id=run_id, plan=plan or _plan(run_id), completed=True, grading_id=f"g-{run_id}",
                         catalog_version="0.7", cells=[])


def _pair():
    return _run("r-b1"), _run("r-b2")


def _refusal(pool, view) -> BenchError:
    assert hasattr(board, "pool_check"), "board.pool_check (ADR-0022 section 3) is missing"
    with pytest.raises(BenchError) as exc_info:
        board.pool_check(pool, view)
    return exc_info.value


def test_two_batches_of_one_lean_ring_pool_ignoring_identity_fields_and_launch_order():
    pool, view = _pair()
    view.plan["cells"].reverse()  # launch order depends on launch_seed, which differs per plan
    assert hasattr(board, "pool_check"), "board.pool_check (ADR-0022 section 3) is missing"
    assert board.pool_check(pool, view) == ()


@pytest.mark.parametrize("side", ["pool", "view"])
def test_rule_both_plans_carry_ring_tag_lean(side):
    pool, view = _pair()
    run = pool if side == "pool" else view
    run.plan["ring"]["tag"] = "pilot"
    exc = _refusal(pool, view)
    assert exc.code == "HB-STA-002"
    assert f"run {run.run_id} has ring tag pilot, not lean" in exc.message


@pytest.mark.parametrize("change,needle", [
    ("drop", "cells differ: only in A: S2-cand"),
    ("model", "cells differ: changed: S1-off"),
    ("task", "cells differ: changed: S1-off"),
    ("combo", "cells differ: changed: S1-off"),
    ("arm", "cells differ: changed: S1-off"),
])
def test_rule_equal_cells_as_a_set_keyed_by_cell_id_on_task_combo_arm_and_model(change, needle):
    pool, view = _pair()
    cells = view.plan["cells"]
    if change == "drop":
        cells.pop()
    else:
        cell = next(c for c in cells if c["cell_id"] == "S1-off")
        cell[change] = {"model": "other-model", "task": "S9", "combo": "codex-sol", "arm": "alt"}[change]
    exc = _refusal(pool, view)
    assert exc.code == "HB-STA-002"
    assert needle in exc.message


@pytest.mark.parametrize("key,sub", [
    ("arms", ARM_ON),
    ("builds", "claude-code"),
    ("profiles", "claude-code"),
    ("instruction_lists", f"S1/{ARM_ON}"),
])
def test_rule_equal_arms_builds_profiles_and_instruction_lists(key, sub):
    pool, view = _pair()
    view.plan[key][sub] = {"changed": True}
    exc = _refusal(pool, view)
    assert exc.code == "HB-STA-002"
    assert f"{key} differ: {sub}" in exc.message


def test_parameters_and_envelope_seconds_are_shown_as_differences_never_refused():
    pool, view = _pair()
    view.plan["parameters"] = {"parallelism": 1}
    view.plan["envelope_seconds"] = 2400
    assert hasattr(board, "pool_check"), "board.pool_check (ADR-0022 section 3) is missing"
    assert board.pool_check(pool, view) == (
        "parameters differ: A {'parallelism': 2}, B {'parallelism': 1}",
        "envelope_seconds differs: A 1200, B 2400",
    )


def test_a_ring_hash_difference_fails_fast_with_hb_pln_003():
    pool, view = _pair()
    view.plan["ring"] = {"tag": "pilot", "hash": "other-hash"}
    exc = _refusal(pool, view)
    assert exc.code == "HB-PLN-003"
    assert "ring hashes differ:" in exc.message


def test_every_other_compare_precondition_and_the_lean_rules_collect_into_one_hb_sta_002():
    pool, view = _pair()
    view = dataclasses.replace(view, grading_id=None, plan=copy.deepcopy(view.plan))
    view.plan["bom_version"] = "0.5"
    view.plan["builds"]["claude-code"] = {"version": "2.2"}
    exc = _refusal(pool, view)
    assert exc.code == "HB-STA-002"
    for needle in ("run r-b2 is not graded", "BOM version differs: A 0.4, B 0.5", "builds differ: claude-code"):
        assert needle in exc.message


def test_the_same_run_is_hb_sta_001():
    pool = _run("r-b1")
    assert _refusal(pool, pool).code == "HB-STA-001"
