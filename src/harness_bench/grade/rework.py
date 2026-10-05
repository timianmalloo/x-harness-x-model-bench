"""Rework strategy helper (W1-L rev 2 section 6.1; W0 rev 6.6 section 13).

Measures rework_ratio on the turn-1 snapshot and final tree, turn1_tests_pass,
and derives turn 2 not reached from cell.turn_ended events against the plan.
"""

from __future__ import annotations

import dataclasses
import re
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from contextlib import ExitStack
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path
from typing import TYPE_CHECKING

from harness_bench import archive
from harness_bench.grade import CellInput, Score, _changes, correctness
from harness_bench.grade import property as prop

if TYPE_CHECKING:
    from harness_bench.grade.property import GradeContext

__all__ = ["grade", "measure", "ratio"]


def _extract_product_lines(tree: Path | str | dict[str, str]) -> dict[str, list[str]]:
    """Extract product lines for all .py files in tree, calling _changes.product_lines."""
    if isinstance(tree, (str, Path)) and Path(tree).is_dir():
        root = Path(tree)
        out = {}
        for p in sorted(root.rglob("*.py")):
            if ".git" in p.parts:
                continue
            rel = p.relative_to(root).as_posix()
            out[rel] = _changes.product_lines(p)
        return out
    elif isinstance(tree, dict):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            out = {}
            for rel, text in tree.items():
                if not rel.endswith(".py"):
                    continue
                norm = rel.replace("\\", "/")
                target = tmp / norm
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text, encoding="utf-8")
                out[norm] = _changes.product_lines(target)
            return out
    return {}


def measure(
    base: Path | str | dict[str, str],
    snapshot: Path | str | dict[str, str],
    final: Path | str | dict[str, str],
    radius: Sequence[str],
) -> tuple[int, int]:
    """(|T1|, |C|) summed over the non-test .py files in radius (W1-L 6.1 step 3)."""
    base_lines = _extract_product_lines(base)
    snap_lines = _extract_product_lines(snapshot)
    final_lines = _extract_product_lines(final)

    base_paths = frozenset(base_lines.keys())
    all_paths = sorted(set(base_lines.keys()) | set(snap_lines.keys()) | set(final_lines.keys()))

    t1_total = 0
    changed_total = 0

    radius_list = list(radius)
    for path in all_paths:
        if not path.endswith(".py") or _changes.is_test_path(path, base_paths):
            continue
        if not _changes.in_radius(path, radius_list):
            continue
        before = base_lines.get(path, [])
        after = snap_lines.get(path, [])
        last = final_lines.get(path, [])

        added, _ = _changes.line_delta(before, after)
        t1 = set(added)
        _, removed = _changes.line_delta(after, last)
        c_set = set(removed)

        t1_total += len(t1)
        changed_total += len(t1 & c_set)

    return t1_total, changed_total


def ratio(t1_total: int, changed_total: int) -> Decimal | None:
    """rework_ratio at scale 4; None (NA) when turn 1 added no product lines."""
    if t1_total == 0:
        return None
    return (Decimal(changed_total) / Decimal(t1_total)).quantize(
        Decimal("0.0001"), rounding=ROUND_HALF_EVEN
    )


def _run_turn1_hidden_tests(inp: CellInput, snap_ws: Path) -> Score:
    """Run hidden tests for turn 1 on the snapshot tree."""
    t1_tests = inp.task_dir / "tests" / "turn1"
    if t1_tests.is_dir():
        work_base = (inp.work_root or inp.out_dir) / "rework-t1-task"
        work_base.mkdir(parents=True, exist_ok=True)
        staged_tests = work_base / "tests"
        if staged_tests.exists():
            _changes.remove_tree(staged_tests)
        staged_tests.mkdir(parents=True, exist_ok=True)
        _changes.copy_tree(t1_tests, staged_tests / "turn1", ignore=())
        task_yaml = inp.task_dir / "task.yaml"
        if task_yaml.is_file():
            shutil.copyfile(task_yaml, work_base / "task.yaml")
        t1_inp = dataclasses.replace(inp, task_dir=work_base)
        return prop.hidden_tests(t1_inp, snap_ws, "turn1")
    return prop.hidden_tests(inp, snap_ws, "turn1")


def grade(inp: CellInput, ctx: GradeContext) -> Mapping[str, Score]:
    """Grade rework property task (W1-L section 6.1)."""
    task_id = inp.cell.get("task", "")
    plan_tasks = inp.plan.get("tasks") or {}
    task_plan = plan_tasks.get(task_id, {})
    plan_turns = task_plan.get("turns")
    if plan_turns is None:
        plan_turns = inp.task.get("turns") or []
    planned_turns = len(plan_turns) + 1

    events = inp.events or ()
    turn_ended_events = [e for e in events if e.get("kind") == "cell.turn_ended"]
    turns_reached = len(turn_ended_events)

    ceilings = (inp.task.get("property") or {}).get("ceilings") or {}
    ceiling_str = ceilings.get("rework_ratio", "0.3000")
    ceiling = Decimal(str(ceiling_str))

    cid = inp.cell.get("cell_id", "")
    snap_events = [e for e in events if e.get("kind") == "cell.turn_snapshot_archived" and e.get("turn") == 1]
    snap_folder = archive.snapshot_folder(inp.run_dir, cid, 1)
    snap_ws = snap_folder / "ws"

    if turns_reached < planned_turns:
        # Turn 2 not reached
        rework_ratio = Score(None, "turn 2 not reached")
        property_check_pass = Score(0, None)
        if snap_events and snap_ws.is_dir():
            turn1_tests_pass = _run_turn1_hidden_tests(inp, snap_ws)
        else:
            turn1_tests_pass = Score(None, "turn 1 snapshot not archived")

        prop.write_section(inp, "rework", {"clause": "turn2_not_reached", "reason": "turn 2 not reached"})
        scores = {
            "rework_ratio": rework_ratio,
            "property_check_pass": property_check_pass,
            "turn1_tests_pass": turn1_tests_pass,
        }
        return {k: scores.get(k, Score(None, "not applicable")) for k in inp.metrics}

    # Turn 2 reached
    if snap_events and snap_ws.is_dir():
        turn1_tests_pass = _run_turn1_hidden_tests(inp, snap_ws)
    else:
        turn1_tests_pass = Score(None, "turn 1 snapshot not archived")

    final_ws = inp.archive / "ws"
    if not final_ws.is_dir():
        final_tests = Score(None, "no working copy in the archive")
        turn2_passed = False
        turn1_final_passed = False
    else:
        final_tests = prop.hidden_tests(inp, final_ws, "final")
        if final_tests.value == 1:
            turn2_passed = True
            turn1_final_passed = True
        else:
            oracle_log = inp.out_dir / "final" / "oracle.log"
            if oracle_log.is_file():
                log_text = oracle_log.read_text(encoding="utf-8", errors="replace")
                fail_t2 = bool(re.search(r"^(?:FAIL|ERROR): (?:test_)?t2_", log_text, re.MULTILINE))
                fail_t1 = bool(re.search(r"^(?:FAIL|ERROR): (?:test_)?t1_", log_text, re.MULTILINE))
                if fail_t2:
                    turn2_passed = False
                    turn1_final_passed = not fail_t1
                elif fail_t1:
                    turn2_passed = True
                    turn1_final_passed = False
                else:
                    turn2_passed = False
                    turn1_final_passed = False
            else:
                turn2_passed = False
                turn1_final_passed = False

    timeout = inp.plan["parameters"]["grading_step_timeout"]
    with ExitStack() as stack:
        pre = correctness.PreTurn(inp, timeout, stack)
        if pre.commit is not None:
            base_tree = pre.tree
        elif (inp.task_dir / "workspace").is_dir():
            base_tree = inp.task_dir / "workspace"
        else:
            base_tree = {}

        radius = inp.task.get("blast_radius") or []
        t1, changed = measure(base_tree, snap_ws if snap_ws.is_dir() else {}, final_ws, radius)
        r_val = ratio(t1, changed)

    if t1 == 0:
        rework_ratio = Score(None, "turn 1 added no product lines")
    else:
        rework_ratio = Score(r_val, None)

    if final_tests.value is None or turn1_tests_pass.value is None:
        property_check_pass = Score(None, final_tests.reason or turn1_tests_pass.reason)
        clause = None
    elif not turn2_passed:
        property_check_pass = Score(0, None)
        clause = "tests"
    elif not turn1_final_passed:
        property_check_pass = Score(0, None)
        clause = "turn1"
    elif r_val is None or r_val > ceiling:
        property_check_pass = Score(0, None)
        clause = "ratio"
    else:
        property_check_pass = Score(1, None)
        clause = None

    section_data = {
        "clause": clause,
        "rework_ratio": str(r_val) if r_val is not None else None,
        "t1_lines": t1,
        "changed": changed,
    }
    prop.write_section(inp, "rework", section_data)

    scores = {
        "rework_ratio": rework_ratio,
        "property_check_pass": property_check_pass,
        "turn1_tests_pass": turn1_tests_pass,
    }
    return {k: scores.get(k, Score(None, "not applicable")) for k in inp.metrics}
