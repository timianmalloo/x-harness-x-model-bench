"""Tests for board projection and statistics export (S5, design: Board, section Test plan)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from harness_bench import board, views
from harness_bench.composites import Catalog
from harness_bench.stats import Params

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
