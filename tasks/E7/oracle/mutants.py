"""Negative controls for E7's hidden tests: each mutant of the reference must fail at least one
hidden test."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from harness_bench.config import load_yaml
from harness_bench.grade.correctness import grade

RULE = "src/CfdBench.Core/Estimation/WingEstimator.cs"

MUTANTS = {  # name: (file, original text, mutated text)
    "helmbold-wrong-constant": (
        RULE,
        "var clAlpha = 2.0 * Math.PI * ar / (2.0 + Math.Sqrt(ar * ar + 4.0));",
        "var clAlpha = 2.0 * Math.PI * ar / (2.0 + Math.Sqrt(ar * ar + 40.0));",
    ),
    "ittc-natural-log-not-log10": (
        RULE,
        "var logTerm = Math.Log10(reynolds) - 2.0;",
        "var logTerm = Math.Log(reynolds) - 2.0;",
    ),
    "hoerner-missing-quartic-term": (
        RULE,
        "var formFactor = 1.0 + 2.0 * tc + 60.0 * Math.Pow(tc, 4);",
        "var formFactor = 1.0 + 2.0 * tc;",
    ),
    "induced-drag-missing-pi": (
        RULE,
        "var cdi = (cl * cl) / (Math.PI * inputs.SpanEfficiency * ar);",
        "var cdi = (cl * cl) / (inputs.SpanEfficiency * ar);",
    ),
    "cavitation-margin-sign-flipped": (
        RULE,
        "var cavitationMargin = sigma - sigmaI;",
        "var cavitationMargin = sigmaI - sigma;",
    ),
    "negative-weight-not-rejected": (
        RULE,
        "        if (inputs.WeightNewtons < 0)\n"
        "        {\n"
        "            throw new ArgumentOutOfRangeException(nameof(inputs), \"WeightNewtons must not be negative.\");\n"
        "        }\n",
        "",
    ),
}


def main() -> None:
    task_dir = Path(__file__).resolve().parents[1]
    oracle = load_yaml(task_dir / "task.yaml")["oracle"]
    with tempfile.TemporaryDirectory(prefix="e7-mut-") as scratch:
        run_dir = Path(scratch)
        for name, (rel, old, new) in MUTANTS.items():
            ws = run_dir / f"{name}-ws"
            shutil.copytree(task_dir / "workspace", ws)
            shutil.copytree(task_dir / "oracle" / "reference", ws, dirs_exist_ok=True)
            target = ws / rel
            text = target.read_text(encoding="utf-8")
            if old not in text:
                raise SystemExit(f"{name}: anchor not found in {rel}")
            target.write_text(text.replace(old, new), encoding="utf-8")
            out_dir = run_dir / name
            out_dir.mkdir()
            result = grade(ws, task_dir, oracle, out_dir, run_dir, timeout=180)
            log = (out_dir / "oracle.log").read_text(encoding="utf-8")
            failed = [line.split()[2] for line in log.splitlines() if line.strip().endswith("[FAIL]")]
            print(f"{name}: passed={result.passed} partial={result.partial_credit} reason={result.reason!r} failed={failed}")


if __name__ == "__main__":
    main()
