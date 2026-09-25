"""Run one calibration pass over a task's calibration set (design phase3-gateway-judges section 11; R-72).

Each qualified judge in `bench/gateway.yaml` scores every item of `bench/calibration/<task>/manifest.yaml` through the
gateway (blinded, scanned, egress-checked, keyed; a stored verdict is read, never re-called). The labels file is
optional (R-72 item 4): when `bench/calibration/<task>/labels.yaml` exists it must match the manifest all or none, or
the pass is refused with HB-CAL-001 before any spawn. The pass writes `runs/calibration-<task>-<rubric sha[:8]>/` and
prints the header's calibration line.

A live call: the Leader's turn, in day hours, with no run live (the gateway refuses with HB-GRD-005 otherwise).
Needs BENCH_OPERATOR_EMAIL, as `bench grade --allow-model-calls` does (egress scans every request for it).

Usage: python tools/calibrate.py [--task C1] [--root .] [--runs <root>/runs] [--cells-root ...] [--tools-dir ...]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from harness_bench import cli
from harness_bench.errors import BenchError
from harness_bench.gateway import calibration

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--task", default="C1")
    p.add_argument("--root", default=str(ROOT))
    p.add_argument("--runs", default=None, help="runs folder (default: <root>/runs)")
    p.add_argument("--cells-root", default=str(ROOT.parent / "bench-cells"))
    p.add_argument("--tools-dir", default=str(ROOT / ".tools" / "harness"))
    args = p.parse_args(argv)
    root = Path(args.root)
    runs = Path(args.runs) if args.runs else root / "runs"
    try:
        cal_id = calibration.run(root, runs, cli._judge_calls(args, root), args.task)
        print(f"calibration {cal_id}")
        print(calibration.header_line(root, runs, args.task))
    except BenchError as exc:
        print(f"{exc.code}: {exc.message}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
