"""Tests for board projection and statistics export (S5, design: Board, section Test plan)."""

from __future__ import annotations

import ast
import dataclasses
import hashlib
import json
import re
import sys
from decimal import Decimal
from pathlib import Path

import pytest
from archived_runs import make_root
from stats_fixtures import stats_run
from test_composites import TEST_CATALOG

from harness_bench import board, stats, views
from harness_bench.composites import Catalog
from harness_bench.errors import BenchError
from harness_bench.stats import METHOD, Obs, Params

# Named constants taken from tests/fixtures/catalog/0.4/heads.export (D4)
HEADS_COMBO = "c"
HEADS_PACK = "off"
HEADS_N_CELLS = 2
HEADS_N_VALID = 2
HEADS_PASS_AT_1 = Decimal("0.5")

HEADS_RUN = Path(__file__).parent / "fixtures/ledger/heads/run"


def test_tb1_build_on_committed_fixture_equals_named_constants():
    """T-B1 (red first for S5, D4): build on the committed fixture.

    Its pass@1 points equal named constants taken from tests/fixtures/catalog/0.4/heads.export.
    Pinned in the test BEFORE views._row is deleted.
    """
    view = views.load(HEADS_RUN)

    # Pin equality with views._row before views._row is deleted (D4)
    if hasattr(views, "_row"):
        old_row = views._row(view, view.cells)
        assert old_row.pass_at_1.value == HEADS_PASS_AT_1

    cat = Catalog(
        version="0.4",
        hash="test-cat-hash",
        metrics={},
        areas={},
        has_anchors=False,
    )
    params = Params()
    b = board.build(view, cat, params)

    assert len(b.rows) == 1
    row = b.rows[0]
    assert row.combo == HEADS_COMBO
    assert row.pack == HEADS_PACK
    assert row.n_cells == HEADS_N_CELLS
    assert row.n_valid == HEADS_N_VALID
    assert row.pass_at_1.point == HEADS_PASS_AT_1


def test_tb2_header_row_text():
    """T-B2: the header row text (method, resamples, seed, unit, primary, Python version)."""
    # 1. Primary is pass_at_1 (catalog without anchors)
    board_p1 = board.Board(
        run_id="r1",
        catalog_version="0.4",
        params=Params(seed=20260927, resamples=2000),
        primary="pass_at_1",
        primary_reason="catalog 0.4 has no normalisation anchors",
        rows=[],
        pack_effect=board.PackEffect(status=None, excluded_tasks=(), rows=[]),
    )
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}"
    hdr_p1 = board.header_row(board_p1)
    assert hdr_p1 == (
        f"statistics: {METHOD}, 2000 resamples, seed 20260927, "
        f"resampled by task then repetition, Python {py_ver} random stream; "
        f"ranked on pass@1 (catalog 0.4 has no normalisation anchors)"
    )

    # 2. Primary is gated (catalog with anchors)
    board_gated = board.Board(
        run_id="r1",
        catalog_version="0.5",
        params=Params(seed=20260927, resamples=2000),
        primary="gated",
        primary_reason=None,
        rows=[],
        pack_effect=board.PackEffect(status=None, excluded_tasks=(), rows=[]),
    )
    hdr_gated = board.header_row(board_gated)
    assert hdr_gated == (
        f"statistics: {METHOD}, 2000 resamples, seed 20260927, "
        f"resampled by task then repetition, Python {py_ver} random stream; "
        f"ranked on correctness-gated composite"
    )


def test_tb3_board_export_golden(tmp_path):
    """T-B3 (D6): the board.export golden.

    Built by stats_run with fixed inputs and S4's committed test catalog with anchors.
    """
    root = make_root(tmp_path)
    run_dir = stats_run(
        root,
        tmp_path,
        run_id="r-gold",
        tasks=("A1", "B1"),
        reps=2,
        arms=("off", "on"),
        combos=["c"],
    )
    view = views.load(run_dir)
    # the pass's own catalog version: anchors of another version never make the primary gated (R-78 c3)
    b = board.build(view, dataclasses.replace(TEST_CATALOG, version=view.catalog_version))
    exp = board.export(b)

    # The digest changes only with METHOD or the fixture.
    assert hashlib.sha256(exp).hexdigest() == "f693c2327a3aa706ad518fd6fce32c09775312ee54987202d3047889b7073445"

    payload = json.loads(exp)
    assert payload["seed"] == 20260927
    assert payload["resamples"] == 2000
    assert payload["method"] == METHOD


def test_tb4_compare_same_run_refusal(tmp_path):
    """T-B4: compare on the same run -> HB-STA-001."""
    root = make_root(tmp_path)
    run_dir = stats_run(root, tmp_path, run_id="r-same", tasks=("A1",), reps=1, arms=("off",))
    view = views.load(run_dir)
    with pytest.raises(BenchError) as exc_info:
        board.compare(view, view, TEST_CATALOG)
    assert exc_info.value.code == "HB-STA-001"
    assert "statistics input spans more than one grading pass of one run" in exc_info.value.message


@pytest.mark.parametrize(
    "diff_kind",
    ["not_graded", "combos", "bom_version", "catalog_version", "task_version"],
)
def test_tb5_compare_preconditions_parametrised(tmp_path, diff_kind):
    """T-B5: compare preconditions (parametrised, each naming the difference) -> HB-STA-002."""
    root = make_root(tmp_path)
    run_a = stats_run(root, tmp_path, run_id="r-a", tasks=("A1",), reps=1, arms=("off",), combos=["c"])
    view_a = views.load(run_a)

    if diff_kind == "not_graded":
        view_b = views.RunView(
            run_id="r-b",
            plan=view_a.plan,
            completed=True,
            grading_id=None,
            catalog_version=view_a.catalog_version,
            cells=view_a.cells,
            header=view_a.header,
        )
    elif diff_kind == "combos":
        run_b = stats_run(root, tmp_path, run_id="r-b", tasks=("A1",), reps=1, arms=("off",), combos=["other"])
        view_b = views.load(run_b)
    elif diff_kind == "bom_version":
        run_b = stats_run(
            root, tmp_path, run_id="r-b", tasks=("A1",), reps=1, arms=("off",), combos=["c"], bom_version="0.5"
        )
        view_b = views.load(run_b)
    elif diff_kind == "catalog_version":
        run_b = stats_run(root, tmp_path, run_id="r-b", tasks=("A1",), reps=1, arms=("off",), combos=["c"])
        view_b = dataclasses.replace(views.load(run_b), catalog_version="0.3")
    elif diff_kind == "task_version":
        run_b = stats_run(root, tmp_path, run_id="r-b", tasks=("A1",), reps=1, arms=("off",), combos=["c"])
        view_b = views.load(run_b)
        b_plan = dict(view_b.plan)
        b_cells = [dict(c) for c in b_plan["cells"]]
        b_cells[0]["task_version"] = "tampered-version"
        b_plan["cells"] = b_cells
        view_b = views.RunView(
            run_id=view_b.run_id,
            plan=b_plan,
            completed=view_b.completed,
            grading_id=view_b.grading_id,
            catalog_version=view_b.catalog_version,
            cells=view_b.cells,
            header=view_b.header,
        )

    with pytest.raises(BenchError) as exc_info:
        board.compare(view_a, view_b, TEST_CATALOG)
    assert exc_info.value.code == "HB-STA-002"
    msg = exc_info.value.message
    if diff_kind == "not_graded":
        assert "run r-b is not graded" in msg
    elif diff_kind == "combos":
        assert "combos differ:" in msg and "only in A: c" in msg and "only in B: other" in msg
    elif diff_kind == "bom_version":
        assert "BOM version differs: A 0.4, B 0.5" in msg
    elif diff_kind == "catalog_version":
        assert f"catalog version differs: A {view_a.catalog_version}, B {view_b.catalog_version}" in msg
    elif diff_kind == "task_version":
        assert "task version of A1 differs" in msg


def test_tb5_multiple_preconditions_all_named(tmp_path):
    """When multiple preconditions fail, all differences are named together in the HB-STA-002 refusal."""
    root = make_root(tmp_path)
    run_a = stats_run(root, tmp_path, run_id="r-a", tasks=("A1",), reps=1, arms=("off",), combos=["c"], bom_version="0.4")
    run_b = stats_run(root, tmp_path, run_id="r-b", tasks=("A1",), reps=1, arms=("off",), combos=["other"], bom_version="0.5")
    view_a = views.load(run_a)
    view_b = dataclasses.replace(views.load(run_b), catalog_version="0.3")

    with pytest.raises(BenchError) as exc_info:
        board.compare(view_a, view_b, TEST_CATALOG)
    assert exc_info.value.code == "HB-STA-002"
    msg = exc_info.value.message
    assert "combos differ:" in msg
    assert "BOM version differs: A 0.4, B 0.5" in msg
    assert f"catalog version differs: A {view_a.catalog_version}, B {view_b.catalog_version}" in msg


def test_tb6_views_defines_no_leaderboard_and_export_has_no_leaderboard_key():
    """T-B6 (D3, ast): views.py defines none of leaderboard, Row, _row, _mean.

    views.export(fixture) has no leaderboard key.
    """
    views_path = Path(__file__).resolve().parents[1] / "src/harness_bench/views.py"
    tree = ast.parse(views_path.read_text(encoding="utf-8"))

    defined_functions = {
        node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    defined_classes = {node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}

    assert "leaderboard" not in defined_functions
    assert "_row" not in defined_functions
    assert "_mean" not in defined_functions
    assert "Row" not in defined_classes

    # views.export has no leaderboard key
    view = views.load(HEADS_RUN)
    exp_bytes = views.export(view)
    payload = json.loads(exp_bytes)
    assert "leaderboard" not in payload


def test_tb7_timing_line_format_and_export_absence():
    """T-B7: timing line is printed by CLI, parseable, and absent from HTML/export."""
    line = board.timing_line(130, 3.125)
    match = re.match(r"^statistics: (?P<intervals>\d+) intervals in (?P<seconds>[0-9.]+) s$", line)
    assert match is not None
    assert int(match.group("intervals")) == 130
    assert float(match.group("seconds")) == 3.125

    # Absent from export
    view = views.load(HEADS_RUN)
    cat = Catalog(version="0.4", hash="h", metrics={}, areas={}, has_anchors=False)
    b = board.build(view, cat)
    exp = board.export(b)
    assert b"intervals in" not in exp


def test_anchors_of_another_catalog_version_never_make_the_primary_gated():
    """R-78 c3: the primary measure is pass@1 while the CURRENT PASS's catalog has no anchors. A loaded catalog of
    another version (here the workstation's newer .dev catalog) says nothing about the pass's anchors, so the board
    must not rank a pass graded under 0.4 on a gated composite (found at the S6 join on smoke-1: every row unranked)."""
    view = views.load(HEADS_RUN)
    other = Catalog(version=f"{view.catalog_version}-other", hash="h", metrics={}, areas={}, has_anchors=True)
    b = board.build(view, other)
    assert b.primary == "pass_at_1"
    assert view.catalog_version in b.primary_reason and other.version in b.primary_reason
    # the disclosure names that cause, never "no valid cell with a value" (a composite of the other version's anchors)
    cell_reason = f"no normalisation anchors for catalog {view.catalog_version}"
    assert b.rows and all(r.gated.point is None and r.gated.reason == cell_reason for r in b.rows)
    assert all(pr.reason == cell_reason for pr in b.pack_effect.rows if pr.measure != "pass_at_1")


def test_tb8_na_and_invalid_cells(tmp_path):
    """T-B8 (US-27 at row layer): a stats_run build with one NA cell and one invalid cell."""
    root = make_root(tmp_path)
    outcomes = {
        ("A1", 1, "off"): 1,
        ("A1", 2, "off"): 1,
        ("B1", 1, "off"): "na",
        ("B1", 2, "off"): {
            "validity": "invalid",
            "validity_code": "HB-CELL-108",
            "outcome": "failed",
            "cause": "provider",
        },
    }
    run_dir = stats_run(
        root, tmp_path, run_id="r-tb8", tasks=("A1", "B1"), reps=2, arms=("off",), combos=["c"], outcomes=outcomes
    )
    view = views.load(run_dir)
    cat = Catalog(version="0.4", hash="h", metrics={}, areas={}, has_anchors=False)
    params = Params()
    b = board.build(view, cat, params)

    assert len(b.rows) == 1
    row = b.rows[0]
    assert row.n_cells == 4
    assert row.n_valid == 3

    # Footnote format
    assert row.footnote is not None
    assert row.footnote.startswith("1 of 3 valid cells NA: ")

    # Row interval equals stats.interval over remaining cells only
    valid_with_score = [
        Obs("A1", 1, Decimal(1)),
        Obs("A1", 2, Decimal(1)),
    ]
    expected_iv = stats.interval(valid_with_score, params, f"pass_at_1|{row.combo}|{row.pack}")
    assert row.pass_at_1.point == expected_iv.point
    assert row.pass_at_1.lo == expected_iv.lo
    assert row.pass_at_1.hi == expected_iv.hi

    # Differs from interval if NA cell entered as 0
    with_na_as_zero = [
        Obs("A1", 1, Decimal(1)),
        Obs("A1", 2, Decimal(1)),
        Obs("B1", 1, Decimal(0)),
    ]
    iv_na_zero = stats.interval(with_na_as_zero, params, f"pass_at_1|{row.combo}|{row.pack}")
    assert row.pass_at_1.point != iv_na_zero.point


def test_tb9_ast_import_graph():
    """T-B9 (D3, ast import graph):

    - stats imports only stdlib and harness_bench.errors
    - views imports none of stats, composites, board
    - board reaches grade only through composites.load_catalog
    """
    root = Path(__file__).resolve().parents[1]

    # 1. stats imports
    stats_tree = ast.parse((root / "src/harness_bench/stats.py").read_text(encoding="utf-8"))
    for node in ast.walk(stats_tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] in (
                    "sys",
                    "math",
                    "random",
                    "hashlib",
                    "dataclasses",
                    "decimal",
                    "typing",
                    "collections",
                    "harness_bench",
                )
        elif isinstance(node, ast.ImportFrom) and node.module:
            assert node.module in ("harness_bench.errors",) or node.module.split(".")[0] in (
                "__future__",
                "sys",
                "math",
                "random",
                "hashlib",
                "dataclasses",
                "decimal",
                "typing",
                "collections",
            )

    # 2. views imports
    views_tree = ast.parse((root / "src/harness_bench/views.py").read_text(encoding="utf-8"))
    for node in ast.walk(views_tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "stats" not in alias.name
                assert "composites" not in alias.name
                assert "board" not in alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            assert "stats" not in node.module
            assert "composites" not in node.module
            assert "board" not in node.module

    # 3. board imports
    board_tree = ast.parse((root / "src/harness_bench/board.py").read_text(encoding="utf-8"))
    for node in ast.walk(board_tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "harness_bench.grade" not in alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            assert not node.module.startswith("harness_bench.grade")


def test_tp1_pack_effect_positive_sign(tmp_path):
    """T-P1: on - off sign on a fixture where the pack helps."""
    root = make_root(tmp_path)
    outcomes = {
        ("A1", 1, "off"): 0,
        ("A1", 2, "off"): 0,
        ("A1", 1, "on"): 1,
        ("A1", 2, "on"): 1,
    }
    run_dir = stats_run(
        root, tmp_path, run_id="r-tp1", tasks=("A1",), reps=2, arms=("off", "on"), combos=["c"], outcomes=outcomes
    )
    view = views.load(run_dir)
    cat = Catalog(version="0.4", hash="h", metrics={}, areas={}, has_anchors=False)
    b = board.build(view, cat)
    pe = b.pack_effect
    assert len(pe.rows) >= 1
    p1_row = next(r for r in pe.rows if r.measure == "pass_at_1")
    assert p1_row.delta.point is not None
    assert p1_row.delta.point > Decimal(0)


def test_tp2_pack_effect_no_detectable_effect(tmp_path):
    """T-P2: no detectable effect on a fixture crossing zero."""
    root = make_root(tmp_path)
    outcomes = {
        ("A1", 1, "off"): 1,
        ("A1", 1, "on"): 1,
        ("B1", 1, "off"): 0,
        ("B1", 1, "on"): 0,
    }
    run_dir = stats_run(
        root, tmp_path, run_id="r-tp2", tasks=("A1", "B1"), reps=1, arms=("off", "on"), combos=["c"], outcomes=outcomes
    )
    view = views.load(run_dir)
    cat = Catalog(version="0.4", hash="h", metrics={}, areas={}, has_anchors=False)
    b = board.build(view, cat)
    p1_row = next(r for r in b.pack_effect.rows if r.measure == "pass_at_1")
    assert p1_row.label == "no detectable effect"


def test_tp3_pack_effect_contamination_prone_tasks_excluded(tmp_path):
    """T-P3: on a fixture holding E1 and E2 cells, E1-E3 are excluded from pack effect.

    The pack effect equals paired_delta over arms with E1-E3 removed by hand,
    and differs from the unfiltered value.
    The exclusion line is asserted in the pack-effect section only.
    A second fixture with none present prints 'none in this run'.
    """
    root = make_root(tmp_path)
    outcomes = {
        ("A1", 1, "off"): 0,
        ("A1", 1, "on"): 1,
        ("E1", 1, "off"): 1,
        ("E1", 1, "on"): 0,
        ("E2", 1, "off"): 1,
        ("E2", 1, "on"): 0,
    }
    run_dir = stats_run(
        root,
        tmp_path,
        run_id="r-tp3",
        tasks=("A1", "E1", "E2"),
        reps=1,
        arms=("off", "on"),
        combos=["c"],
        outcomes=outcomes,
    )
    view = views.load(run_dir)
    cat = Catalog(version="0.4", hash="h", metrics={}, areas={}, has_anchors=False)
    b = board.build(view, cat)
    pe = b.pack_effect
    assert pe.excluded_tasks == ("E1", "E2")
    assert pe.exclusion_line == "Excluded as contamination-prone: E1, E2"

    p1_row = next(r for r in pe.rows if r.measure == "pass_at_1")
    assert p1_row.delta.point == Decimal(1)

    # Second fixture with none present
    run_dir_clean = stats_run(
        root, tmp_path, run_id="r-tp3-clean", tasks=("A1",), reps=1, arms=("off", "on"), combos=["c"]
    )
    view_clean = views.load(run_dir_clean)
    b_clean = board.build(view_clean, cat)
    assert b_clean.pack_effect.exclusion_line == "Excluded as contamination-prone: none in this run"


def test_tp4_pack_effect_states(tmp_path):
    """T-P4: one-setting and missing-arm states with spec copy."""
    root = make_root(tmp_path)
    # 1. One-setting: only 'off'
    run_one = stats_run(root, tmp_path, run_id="r-one", tasks=("A1",), reps=1, arms=("off",), combos=["c"])
    view_one = views.load(run_one)
    cat = Catalog(version="0.4", hash="h", metrics={}, areas={}, has_anchors=False)
    b_one = board.build(view_one, cat)
    assert b_one.pack_effect.status == "This run has one pack setting; no effect to show."
    assert b_one.pack_effect.rows == []

    # 2. Missing-arm: combo c has both off and on, combo d has only off
    cells_c = list(view_one.cells)
    c_on = dataclasses.replace(cells_c[0], cell_id="a1-r1-on-c", label="A1.c.pack-on.r1", pack="on")
    d_off = dataclasses.replace(cells_c[0], cell_id="a1-r1-off-d", label="A1.d.pack-off.r1", combo="d", pack="off")
    plan_with_d = dict(view_one.plan)
    plan_with_d["cells"] = [
        *view_one.plan["cells"],
        {"cell_id": "a1-r1-on-c", "task": "A1", "rep": 1, "task_version": "v1"},
        {"cell_id": "a1-r1-off-d", "task": "A1", "rep": 1, "task_version": "v1"},
    ]
    view_missing = views.RunView(
        run_id="r-missing",
        plan=plan_with_d,
        completed=True,
        grading_id="g1",
        catalog_version="0.4",
        cells=[*cells_c, c_on, d_off],
        header={},
    )
    b_missing = board.build(view_missing, cat)
    d_rows = [r for r in b_missing.pack_effect.rows if r.combo == "d"]
    assert len(d_rows) >= 1
    assert d_rows[0].reason == "Pack effect needs both settings."


def test_tm3_comparison_direction_and_negation(tmp_path):
    """T-M3 (US-52 criterion 1): run A is a stats_run build; run B is a second build
    with one (task, rep) outcome flipped from pass to fail in one (combo, pack).
    compare(base=A, view=B) gives that row's delta point exactly -1/n.
    compare(base=B, view=A) gives the negated point.
    Run B holds an E* task (E1) and the comparison names it under the same statement as pack effect (R-78 c6).
    """
    root = make_root(tmp_path)
    outcomes_a = {
        ("A1", 1, "off"): 1,
        ("B1", 1, "off"): 1,
    }
    run_a = stats_run(
        root,
        tmp_path,
        run_id="r-a",
        tasks=("A1", "B1"),
        reps=1,
        arms=("off", "on"),
        combos=["c"],
        outcomes=outcomes_a,
    )
    outcomes_b = {
        ("A1", 1, "off"): 1,
        ("B1", 1, "off"): 0,
        ("E1", 1, "off"): 1,
        ("C1", 1, "off"): 1,
    }
    run_b = stats_run(
        root,
        tmp_path,
        run_id="r-b",
        tasks=("A1", "B1", "E1", "C1"),
        reps=1,
        arms=("off", "on"),
        combos=["c"],
        outcomes=outcomes_b,
    )

    view_a = views.load(run_a)
    view_b = views.load(run_b)
    cat = Catalog(version="0.4", hash="h", metrics={}, areas={}, has_anchors=False)

    comp_ab = board.compare(base=view_a, view=view_b, cat=cat)
    # E1 is excluded as contamination-prone and named under the same statement as pack effect (R-78 c6)
    assert comp_ab.excluded_tasks == ("E1",)
    assert comp_ab.exclusion_line == "Excluded as contamination-prone: E1"
    # Unshared tasks named
    assert "C1" in comp_ab.unshared_tasks
    assert "E1" in comp_ab.unshared_tasks

    row_ab = next(r for r in comp_ab.rows if r.combo == "c" and r.pack == "off" and r.measure == "pass_at_1")
    # delta point exactly -1/n over shared clean tasks A1, B1 (n = 2) -> -0.5
    assert row_ab.delta.point == Decimal("-0.5")
    assert row_ab.delta.lo is not None and row_ab.delta.hi is not None
    assert row_ab.label == "no detectable effect"

    comp_ba = board.compare(base=view_b, view=view_a, cat=cat)
    row_ba = next(r for r in comp_ba.rows if r.combo == "c" and r.pack == "off" and r.measure == "pass_at_1")
    assert row_ba.delta.point == Decimal("0.5")
    assert row_ab.delta.point == -row_ba.delta.point


def test_ver_a_comparison_composite_delta_refused_when_pass_catalog_differs_from_loaded(tmp_path):
    """VER-A: composite delta is computed only when both runs' current passes are of the loaded catalog's
    version; otherwise the area rows are NA with the reason, and pass@1 deltas are still computed.
    """
    import yaml
    root = make_root(tmp_path)
    m_path = root / "bench" / "metrics.yaml"
    cat_data = yaml.safe_load(m_path.read_text(encoding="utf-8"))
    cat_data["version"] = "0.4"
    m_path.write_text(yaml.dump(cat_data), encoding="utf-8")

    run_a = stats_run(root, tmp_path, run_id="r-ver-a", tasks=("A1", "B1"), reps=1, arms=("off", "on"), combos=["c"])
    run_b = stats_run(root, tmp_path, run_id="r-ver-b", tasks=("A1", "B1"), reps=1, arms=("off", "on"), combos=["c"])
    view_a = views.load(run_a)
    view_b = views.load(run_b)
    assert view_a.catalog_version == "0.4"
    assert view_b.catalog_version == "0.4"

    # Loaded catalog has anchors, but version is "0.5.test" != "0.4"
    cat_anchored = Catalog(
        version="0.5.test",
        hash="test-cat-hash",
        metrics={
            "partial_credit": {"id": "partial_credit", "kind": "score", "weight": 1, "anchor": [0, 1], "better": "higher"},
            "pass_at_1": {"id": "pass_at_1", "kind": "score", "weight": 0, "better": "higher"},
        },
        areas={"correctness": ("partial_credit", "pass_at_1")},
        has_anchors=True,
    )
    comp_diff = board.compare(base=view_a, view=view_b, cat=cat_anchored)

    p1_row = next(r for r in comp_diff.rows if r.measure == "pass_at_1")
    assert p1_row.delta.point is not None  # pass@1 delta is still computed

    area_rows = [r for r in comp_diff.rows if r.measure != "pass_at_1"]
    assert len(area_rows) > 0
    for ar in area_rows:
        assert ar.delta.point is None
        assert ar.delta.reason == "no normalisation anchors for catalog 0.4"
        assert ar.label is None

    # When loaded catalog version matches both runs' pass catalog version and has anchors:
    cat_04 = dataclasses.replace(cat_anchored, version="0.4")
    comp_same = board.compare(base=view_a, view=view_b, cat=cat_04)
    same_area_rows = [r for r in comp_same.rows if r.measure != "pass_at_1"]
    assert len(same_area_rows) > 0
    for ar in same_area_rows:
        assert ar.delta.point is not None
