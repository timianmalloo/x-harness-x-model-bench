"""Run D1's real correctness grader on the pinned base and the private reference."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from harness_bench.config import load_yaml
from harness_bench.grade.correctness import grade


def main() -> None:
    task_dir = Path(__file__).resolve().parents[1]
    oracle = load_yaml(task_dir / "task.yaml")["oracle"]
    with tempfile.TemporaryDirectory(prefix="d1-grade-") as scratch:
        run_dir = Path(scratch)
        reference = run_dir / "reference-ws"
        shutil.copytree(task_dir / "workspace", reference)
        ref_file = task_dir / "oracle/reference/src/AiDe.Core/Projections/EvidenceCensusProjection.cs"
        dest = reference / "src/AiDe.Core/Projections/EvidenceCensusProjection.cs"
        shutil.copy2(ref_file, dest)

        for label, ws in (("base", task_dir / "workspace"), ("reference", reference)):
            out_dir = run_dir / label
            out_dir.mkdir()
            result = grade(ws, task_dir, oracle, out_dir, run_dir, timeout=180)
            print(f"{label}: passed={result.passed} partial={result.partial_credit} "
                  f"reason={result.reason!r}")
            print((out_dir / "oracle.log").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
