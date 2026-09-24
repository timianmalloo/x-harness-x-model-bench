"""Produce one golden ledger fixture (D6) with the code of the checkout it runs in.

The fixture is a completed run of two cells (one passes, one fails its hidden tests) with every row type
(events, turn_usage, archive_files, model_calls, tool_calls, scores): an in-run grading pass whose summary
`run.completed` records, then a later `bench grade` pass. It writes, under `<out>`:

- `run/`: the run folder (`plan.json`, the segments, `archive/`), without `grading/` and the locks;
- `expected.json`: every segment's head hash, row count, seal state and file sha256, and the producing commit;
- `tampered/`: an overlay on `run/` holding only the changed file: the later pass's scores segment cut by its
  seal and last row. When the pass records `heads` (ruling R-2), the cut segment is also re-sealed, so only
  the recorded head can expose it. The run with the overlay applied must exit 5.

Usage (from the checkout whose code must produce it): python tests/fixtures/ledger/make_fixture.py <out>
"""

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TESTS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(TESTS))

from archived_runs import GOOD, STUB, complete_run, make_root, make_run

from harness_bench import ledger, views
from harness_bench.grade import runner

USAGE = {"kind": "turn_usage", "run_id": "r1", "attempt": 1, "model": "gpt-6-sol", "uncached_input": 100, "cache_read": 1000,
         "cache_write": 10, "output": 50, "reasoning": 0}


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=TESTS.parent, capture_output=True, text=True, check=True).stdout.strip()


def expected(run_dir: Path) -> dict:
    out = {}
    for fact in views.FACTS:
        for path in views.segment_paths(run_dir, fact):
            report = ledger.verify_segment(path)
            assert report.error is None, (path, report.detail)
            out[f"{fact}/{path.name}"] = {"head_hash": report.head_hash, "rows": report.lines, "sealed": report.sealed,
                                          "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    return out


def main(out: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        root = make_root(tmp_path)
        run_dir = make_run(root, tmp_path, {"a": GOOD, "b": STUB},
                           turn_usage=[{**USAGE, "cell_id": "a"}, {**USAGE, "cell_id": "b"}])
        in_run = runner.run_pass(run_dir, root)
        complete_run(run_dir, grading=in_run.summary())
        later = runner.run_pass(run_dir, root)
        if out.exists():
            shutil.rmtree(out / "run", ignore_errors=True)
            shutil.rmtree(out / "tampered", ignore_errors=True)
        shutil.copytree(run_dir, out / "run", ignore=shutil.ignore_patterns("grading", "*.lock", ".lock"))
    cut = f"scores/{later.grading_id}.jsonl"
    (out / "tampered" / "scores").mkdir(parents=True)
    (out / "tampered" / cut).write_bytes(b"".join((out / "run" / cut).read_bytes().splitlines(keepends=True)[:-2]))
    completed = ledger.read_segment(out / "run" / "events" / f"{later.grading_id}.jsonl")[-1]
    resealed = "heads" in completed
    if resealed:
        with ledger.SegmentWriter.reopen(out / "tampered" / cut) as w:
            w.seal()
    doc = {"produced_at": _git("rev-parse", "HEAD"), "src_dirty": bool(_git("status", "--porcelain", "--", "src")),
           "in_run_pass": in_run.grading_id, "later_pass": later.grading_id,
           "tampered": f"{cut}: seal and last row cut" + (", then re-sealed" if resealed else ""),
           "segments": expected(out / "run")}
    (out / "expected.json").write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
