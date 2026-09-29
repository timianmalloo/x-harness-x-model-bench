"""R-83 condition 2 / R-42 c3 for E3: the two files this folder vendors from Terminal-Bench 2.0's
`extract-moves-from-video` rebuild from `git archive <commit> -- <path>` against a local clone of
the upstream repo -- `oracle/reference/solve.sh` byte-for-byte, `tests/test_outputs.py` after
re-applying the one recorded native-path edit (README.md's diff: `/app/solution.txt` ->
`solution.txt`, both occurrences).

Usage: vendoring_check.py <terminal-bench-2 clone>
"""

from __future__ import annotations

import io
import subprocess
import sys
import zipfile
from pathlib import Path

from harness_bench.config import load_yaml

TASK = Path(__file__).resolve().parents[1]
EDIT = (b'Path("/app/solution.txt")', b'Path("solution.txt")')


def _archived(source: Path, commit: str, vendored_path: str) -> bytes:
    archive = subprocess.run(
        ["git", "-C", str(source), "archive", "--format=zip", commit, "--", vendored_path],
        check=True,
        capture_output=True,
    ).stdout
    with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
        [name] = [n for n in zipped.namelist() if not n.endswith("/")]
        return zipped.read(name)


def main(source: Path) -> int:
    src = load_yaml(TASK / "task.yaml")["source"]
    commit = src["commit"]
    problems: list[str] = []

    solve_expected = _archived(source, commit, "extract-moves-from-video/solution/solve.sh")
    solve_actual = (TASK / "oracle" / "reference" / "solve.sh").read_bytes()
    if solve_actual != solve_expected:
        problems.append("oracle/reference/solve.sh does not match git archive byte-for-byte")

    tests_expected = _archived(source, commit, "extract-moves-from-video/tests/test_outputs.py")
    tests_actual = (TASK / "tests" / "test_outputs.py").read_bytes()
    if tests_expected.count(EDIT[0]) != 2:
        problems.append("upstream tests/test_outputs.py no longer has exactly two /app/solution.txt Path() calls")
    reconstructed = tests_expected.replace(*EDIT)
    if reconstructed != tests_actual:
        problems.append("tests/test_outputs.py does not equal git archive with the recorded README diff applied")

    print("\n".join(problems) if problems else "ok")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))
