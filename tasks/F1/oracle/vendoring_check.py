"""R-42 c2-c4 for F1: the workspace equals `git archive <commit> -- <vendored_paths>` byte for byte and holds no pack
marker, generated folder, secret-shaped file, user-profile path or e-mail address. Usage: vendoring_check.py <cfd-bench clone>"""

from __future__ import annotations

import io
import re
import subprocess
import sys
import zipfile
from pathlib import Path

from harness_bench.config import PROFILE_PATH, load_yaml

TASK = Path(__file__).resolve().parents[1]
ROOT = TASK.parents[1]
WORKSPACE = TASK / "workspace"
FORBIDDEN_PARTS = {".agents", ".claude", ".github", ".grok", "bin", "obj", ".nuget", ".git", ".cache", "__pycache__"}
FORBIDDEN_SUFFIXES = {".pem", ".pfx", ".key", ".env"}
EMAIL = re.compile(rb"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def main(source: Path) -> int:
    src = load_yaml(TASK / "task.yaml")["source"]
    paths = [p.rstrip("/") for p in src["vendored_paths"]]
    archive = subprocess.run(["git", "-C", str(source), "archive", "--format=zip", src["commit"], "--", *paths],
                             check=True, capture_output=True).stdout
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        expected = {n: z.read(n) for n in z.namelist() if not n.endswith("/")}
    actual = {p.relative_to(WORKSPACE).as_posix(): p.read_bytes() for p in WORKSPACE.rglob("*") if p.is_file()}
    problems = [f"only in archive: {n}" for n in sorted(expected.keys() - actual.keys())]
    problems += [f"only in workspace: {n}" for n in sorted(actual.keys() - expected.keys())]
    problems += [f"bytes differ: {n}" for n in sorted(expected.keys() & actual.keys()) if expected[n] != actual[n]]
    markers = [m.strip().encode() for m in (ROOT / "bench/pack-markers.txt").read_text(encoding="utf-8").splitlines() if m.strip()]
    for name, data in sorted(actual.items()):
        parts = set(Path(name).parts)
        if parts & FORBIDDEN_PARTS or Path(name).suffix.lower() in FORBIDDEN_SUFFIXES:
            problems.append(f"forbidden path: {name}")
        if any(m in data for m in markers):
            problems.append(f"pack marker: {name}")
        if PROFILE_PATH.search(data.decode("utf-8", errors="replace")):
            problems.append(f"user-profile path: {name}")
        if EMAIL.search(data):
            problems.append(f"e-mail address: {name}")
    print(f"{len(actual)} files, {sum(len(d) for d in actual.values())} bytes; archive {len(expected)} files")
    print("\n".join(problems) if problems else "ok")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))
