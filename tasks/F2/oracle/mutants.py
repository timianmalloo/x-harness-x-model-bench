"""Negative controls for F2's hidden tests: each mutant of the reference must fail at least one
hidden test."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from harness_bench.config import load_yaml
from harness_bench.grade.correctness import grade

PROJECTION = "src/AiDe.Core/Projections/EvidenceCensusProjection.cs"

MUTANTS = {  # name: (file, original text, mutated text)
    "ascending-count-sort": (
        PROJECTION,
        "            .OrderByDescending(row => row.Count)",
        "            .OrderBy(row => row.Count)",
    ),
    "cap-unclamped": (
        PROJECTION,
        "        var cap = Math.Clamp(query.MaxRows, 1, 100);",
        "        var cap = query.MaxRows;",
    ),
    "status-ignored-in-grouping": (
        PROJECTION,
        "            .GroupBy(a => (a.Predicate, a.Origin, a.Status))",
        "            .GroupBy(a => (a.Predicate, a.Origin, Status: VerificationStatus.Verified))",
    ),
    "null-query-check-removed": (
        PROJECTION,
        "        ArgumentNullException.ThrowIfNull(query);\n",
        "",
    ),
    "revision-not-preserved": (
        PROJECTION,
        "            buckets.Take(cap).ToList(), assertions.Count, omitted, disclosures, sourceRevision);",
        "            buckets.Take(cap).ToList(), assertions.Count, omitted, disclosures, \"unknown\");",
    ),
    "no-disclosure-ever": (
        PROJECTION,
        '        IReadOnlyList<string> disclosures = omitted > 0 ? [$"Omitted ({omitted})"] : [];',
        "        IReadOnlyList<string> disclosures = [];",
    ),
}

REFERENCE_FILES = (
    "src/AiDe.Core/Projections/EvidenceCensusContract.cs",
    "src/AiDe.Core/Projections/EvidenceCensusProjection.cs",
)


def main() -> None:
    task_dir = Path(__file__).resolve().parents[1]
    oracle = load_yaml(task_dir / "task.yaml")["oracle"]
    with tempfile.TemporaryDirectory(prefix="f2-mut-") as scratch:
        run_dir = Path(scratch)
        for name, (rel, old, new) in MUTANTS.items():
            ws = run_dir / f"{name}-ws"
            shutil.copytree(task_dir / "workspace", ws)
            for ref_rel in REFERENCE_FILES:
                dest = ws / ref_rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(task_dir / "oracle/reference" / ref_rel, dest)
            target = ws / rel
            text = target.read_text(encoding="utf-8")
            if old not in text:
                raise SystemExit(f"{name}: anchor not found in {rel}")
            target.write_text(text.replace(old, new), encoding="utf-8")
            out_dir = run_dir / name
            out_dir.mkdir()
            result = grade(ws, task_dir, oracle, out_dir, run_dir, timeout=300)
            log = (out_dir / "oracle.log").read_text(encoding="utf-8")
            failed = [line.split()[2] for line in log.splitlines() if line.strip().endswith("[FAIL]")]
            print(f"{name}: passed={result.passed} partial={result.partial_credit} reason={result.reason!r} failed={failed}")


if __name__ == "__main__":
    main()
