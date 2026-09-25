"""Negative controls for F1's hidden tests: each mutant of the reference must fail at least one hidden test."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from harness_bench.config import load_yaml
from harness_bench.grade.correctness import grade

DERIV = "src/CfdBench.Core/Derivations/WingDerivations.cs"
WING = "src/CfdBench.Core/Domain/Wing.cs"
MUTANTS = {  # name: (file, original text, mutated text)
    "span-half-only": (DERIV, "2.0 * wing.Stations[^1].SpanPosition.Metres", "wing.Stations[^1].SpanPosition.Metres"),
    "mac-is-mgc": (DERIV, "(c0 * c0 + c0 * c1 + c1 * c1) / 3.0", "(c0 + c1) / 2.0"),
    "washout-sign": (DERIV, "wing.Stations[0].Twist.Radians - wing.Stations[^1].Twist.Radians",
                     "wing.Stations[^1].Twist.Radians - wing.Stations[0].Twist.Radians"),
    "root-and-tip-only": (DERIV, "for (var i = 1; i < wing.Stations.Count; i++)",
                          "for (var i = wing.Stations.Count - 1; i < wing.Stations.Count; i++)"),
    "no-defensive-copy": (WING, "private Wing(Station[] stations) => Stations = Array.AsReadOnly(stations);",
                          "private Wing(IReadOnlyList<Station> stations) => Stations = stations;"),
    "equal-positions-allowed": (WING, "copy[i].SpanPosition.Metres > copy[i - 1].SpanPosition.Metres",
                                "copy[i].SpanPosition.Metres >= copy[i - 1].SpanPosition.Metres"),
}


def main() -> None:
    task_dir = Path(__file__).resolve().parents[1]
    oracle = load_yaml(task_dir / "task.yaml")["oracle"]
    with tempfile.TemporaryDirectory(prefix="f1-mut-") as scratch:
        run_dir = Path(scratch)
        for name, (rel, old, new) in MUTANTS.items():
            ws = run_dir / f"{name}-ws"
            shutil.copytree(task_dir / "workspace", ws)
            shutil.copytree(task_dir / "oracle" / "reference", ws, dirs_exist_ok=True)
            target = ws / rel
            text = target.read_text(encoding="utf-8")
            if old not in text:
                raise SystemExit(f"{name}: anchor not found in {rel}")
            if name == "no-defensive-copy":
                text = text.replace("var copy = stations.ToArray();", "var copy = stations.ToArray();\n        var kept = stations;")
                text = text.replace("return new Wing(copy);", "return new Wing(kept);")
            target.write_text(text.replace(old, new), encoding="utf-8")
            out_dir = run_dir / name
            out_dir.mkdir()
            result = grade(ws, task_dir, oracle, out_dir, run_dir, timeout=300)
            log = (out_dir / "oracle.log").read_text(encoding="utf-8")
            failed = [line.split()[2] for line in log.splitlines() if line.strip().endswith("[FAIL]")]
            print(f"{name}: passed={result.passed} partial={result.partial_credit} reason={result.reason!r} failed={failed}")


if __name__ == "__main__":
    main()
