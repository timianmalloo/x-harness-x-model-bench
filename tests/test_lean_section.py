"""Tests for the lean summary report section (ADR-0023, spec Part B & Part C)."""

from pathlib import Path

from archived_runs import make_root
from test_report import _arms_view

from harness_bench.report import html


def test_nonlean_report_golden(tmp_path):
    """LBU-5: a non-lean run renders byte-equal to its golden captured before html.py was touched."""
    root = make_root(tmp_path)
    view = _arms_view(root, tmp_path, {"off": None, "on": {"revision": 95, "commit": "a" * 40}})
    run_dir = tmp_path / "runs" / "r1"
    path = html.write(run_dir, view)
    golden = (Path(__file__).parent / "goldens" / "report-nonlean-arms.html").read_bytes()
    assert path.read_bytes() == golden
