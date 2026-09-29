"""R-42 c3 / R-83 c2 for E2: every path in `task.yaml`'s `source.vendored_paths` is rebuilt from
`git archive <commit> -- <path>` against a clone of the upstream repo and compared to what this
folder carries. Three destinations (`prompt.md`, `tests/test_outputs.py`,
`oracle/reference/solve.sh`) apply the one documented native-path substitution (`tasks/E2/README.md`)
before the comparison; undoing it must reproduce the archived bytes exactly. The rest
(`oracle/upstream/*`) must match byte for byte.

Usage: vendoring_check.py <terminal-bench-2 clone>
"""

from __future__ import annotations

import io
import subprocess
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))
from harness_bench.config import load_yaml  # noqa: E402

TASK = Path(__file__).resolve().parents[1]
ROOT = TASK.parents[1]
UPSTREAM_PREFIX = "count-dataset-tokens/"
EDIT = ("/app/answer.txt", "answer.txt")  # (upstream, native) -- the one substitution (tasks/E2/README.md)

# upstream path (relative to the repo root) -> (this folder's path, edited?)
DESTINATIONS = {
    UPSTREAM_PREFIX + "environment/Dockerfile": (TASK / "oracle/upstream/Dockerfile", False),
    UPSTREAM_PREFIX + "task.toml": (TASK / "oracle/upstream/task.toml", False),
    UPSTREAM_PREFIX + "README.md": (TASK / "oracle/upstream/README.md", False),
    UPSTREAM_PREFIX + "instruction.md": (TASK / "oracle/upstream/instruction.md", False),
    UPSTREAM_PREFIX + "tests/test_outputs.py": (TASK / "tests/test_outputs.py", True),
    UPSTREAM_PREFIX + "solution/solve.sh": (TASK / "oracle/reference/solve.sh", True),
}
# instruction.md also lands, edited, as the run prompt
EXTRA_EDITED = {UPSTREAM_PREFIX + "instruction.md": TASK / "prompt.md"}


def _archive(source: Path, commit: str, paths: list[str]) -> dict[str, bytes]:
    # -c core.autocrlf=false: `git archive` applies the worktree CRLF filter from the *invoking*
    # host's config, not from anything pinned to the commit (measured: this host's system-wide
    # core.autocrlf=true turns 13 LF bytes to CRLF in this one file, changing the archive's length
    # from 467 to 480 bytes with no change to the committed blob, `git cat-file -p` for either path
    # gives the same 467-byte LF content on this host). Forcing it off makes the rebuild match the
    # blob's own bytes regardless of the host's global git config.
    out = subprocess.run(
        ["git", "-c", "core.autocrlf=false", "-C", str(source), "archive", "--format=zip", commit, "--", *paths],
        check=True, capture_output=True,
    ).stdout
    with zipfile.ZipFile(io.BytesIO(out)) as z:
        return {n: z.read(n) for n in z.namelist() if not n.endswith("/")}


def main(source: Path) -> int:
    task = load_yaml(TASK / "task.yaml")
    src = task["source"]
    paths = [p for p in src["vendored_paths"]]
    assert set(paths) == set(DESTINATIONS), f"task.yaml vendored_paths disagrees with the check's own map: {set(paths) ^ set(DESTINATIONS)}"
    archived = _archive(source, src["commit"], paths)
    problems: list[str] = []
    for upstream_path, (dest, edited) in DESTINATIONS.items():
        original = archived.get(upstream_path)
        if original is None:
            problems.append(f"missing from archive: {upstream_path}")
            continue
        actual = dest.read_bytes()
        if edited:
            expected = original.replace(EDIT[0].encode(), EDIT[1].encode())
            if expected == original:
                problems.append(f"archived original has no occurrence of {EDIT[0]!r} to substitute: {upstream_path}")
            if actual != expected:
                problems.append(f"edited file is not exactly the archived original with {EDIT[0]!r} replaced by "
                                 f"{EDIT[1]!r}: {dest.relative_to(TASK).as_posix()}")
        elif actual != original:
            problems.append(f"bytes differ from the archive: {dest.relative_to(TASK).as_posix()}")
    for upstream_path, dest in EXTRA_EDITED.items():
        original = archived[upstream_path]
        actual = dest.read_bytes()
        expected = original.replace(EDIT[0].encode(), EDIT[1].encode())
        if actual != expected:
            problems.append(f"edited file is not exactly the archived original with {EDIT[0]!r} replaced by "
                             f"{EDIT[1]!r}: {dest.relative_to(TASK).as_posix()}")
    markers_file = ROOT / "bench/pack-markers.txt"
    markers = [m.strip().encode() for m in markers_file.read_text(encoding="utf-8").splitlines() if m.strip()]
    for dest, _ in DESTINATIONS.values():
        data = dest.read_bytes()
        if any(m in data for m in markers):
            problems.append(f"pack marker: {dest.relative_to(TASK).as_posix()}")
    print(f"{len(DESTINATIONS) + len(EXTRA_EDITED)} destination files checked against {len(archived)} archived paths")
    print("\n".join(problems) if problems else "ok")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))
