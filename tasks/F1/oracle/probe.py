"""Run F1's real correctness grader on the vendored base and on the private reference overlay."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from harness_bench.config import load_yaml
from harness_bench.grade.correctness import grade


def main() -> None:
    task_dir = Path(__file__).resolve().parents[1]
    oracle = load_yaml(task_dir / "task.yaml")["oracle"]
    with tempfile.TemporaryDirectory(prefix="f1-grade-") as scratch:
        run_dir = Path(scratch)
        reference = run_dir / "reference-ws"
        shutil.copytree(task_dir / "workspace", reference)
        shutil.copytree(task_dir / "oracle" / "reference", reference, dirs_exist_ok=True)

        for label, ws in (("base", task_dir / "workspace"), ("reference", reference)):
            out_dir = run_dir / label
            out_dir.mkdir()
            result = grade(ws, task_dir, oracle, out_dir, run_dir, timeout=300)
            print(f"{label}: passed={result.passed} partial={result.partial_credit} reason={result.reason!r}")
            print((out_dir / "oracle.log").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
