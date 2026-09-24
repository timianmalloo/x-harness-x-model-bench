"""Projections over the verified facts (ADR-0006; design: Data model, Rules).

Pattern: On-demand Projection. Every view reads rows through `rows()`, which verifies each segment's hash
chain (HB-LED-002 on a break) and admits only:
- the engine process's segments (`engine-*`), and
- the segments of **completed** grading passes: a `grade-*` pass whose events segment is sealed and holds
  `grading.completed`. Any other grading segment belongs to an abandoned pass and is skipped (HB-LED-004).
"""

from __future__ import annotations

from pathlib import Path

from harness_bench import ledger
from harness_bench.errors import BenchError

ENGINE_PREFIX = "engine-"
GRADE_PREFIX = "grade-"


def segment_paths(run_dir: Path, fact: str) -> list[Path]:
    folder = run_dir / fact
    return sorted(folder.glob("*.jsonl")) if folder.is_dir() else []


def completed_passes(run_dir: Path) -> set[str]:
    done = set()
    for path in segment_paths(run_dir, "events"):
        if not path.stem.startswith(GRADE_PREFIX):
            continue
        report = ledger.verify_segment(path)
        if report.sealed and not report.error and any(r["kind"] == "grading.completed" for r in ledger.read_segment(path)):
            done.add(path.stem)
    return done


def rows(run_dir: Path, fact: str) -> list[dict]:
    """Verified rows of the engine's segments and of completed grading passes, in segment order."""
    done = completed_passes(run_dir)
    out: list[dict] = []
    for path in segment_paths(run_dir, fact):
        sid = path.stem
        if sid.startswith(GRADE_PREFIX) and sid not in done:
            continue
        if not sid.startswith((ENGINE_PREFIX, GRADE_PREFIX)):
            raise BenchError("HB-LED-002", f"{fact}/{path.name}: no known writer for this segment")
        out.extend(ledger.read_segment(path))
    return out
