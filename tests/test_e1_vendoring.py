"""R-42 c3 / R-83 condition 2: E1's vendored workspace/code.png is exactly the upstream
code-from-image/environment/code.png at the pinned commit, rebuilt with `git archive`.

Unlike D1's test (tests/test_task_vendoring.py), E1's local file name differs from the upstream
path -- the vendoring is a deliberate flatten (tasks/E1/README.md "Source pin"), not a 1:1 mirror of
the upstream tree -- so this test maps the one vendored_paths entry explicitly by name instead of
comparing an archive's relative names against the workspace's own relative names.
"""

from __future__ import annotations

import io
import subprocess
import zipfile
from pathlib import Path

import pytest

from harness_bench.config import load_yaml

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "tasks" / "E1"
WORKSPACE = TASK / "workspace"
SOURCE = Path("C:/projects/terminal-bench-2")


def test_e1_workspace_matches_pinned_git_archive_byte_for_byte() -> None:
    if not (SOURCE / ".git").exists():
        pytest.skip("C:/projects/terminal-bench-2 is absent; pinned git archive cannot be rebuilt locally")

    source = load_yaml(TASK / "task.yaml")["source"]
    assert source["repo"] == "https://github.com/harbor-framework/terminal-bench-2"
    paths = [path.rstrip("/") for path in source["vendored_paths"]]
    assert paths == ["code-from-image/environment/code.png"]
    archive = subprocess.run(
        ["git", "-C", str(SOURCE), "archive", "--format=zip", source["commit"], "--", *paths],
        check=True,
        capture_output=True,
    ).stdout
    with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
        [name] = [n for n in zipped.namelist() if not n.endswith("/")]
        expected = zipped.read(name)

    actual = (WORKSPACE / "code.png").read_bytes()
    assert actual == expected


def test_e1_workspace_has_no_pack_markers_or_generated_content() -> None:
    markers = [line.encode() for line in (ROOT / "bench/pack-markers.txt").read_text().splitlines() if line]
    files = {p.relative_to(WORKSPACE).as_posix(): p.read_bytes() for p in WORKSPACE.rglob("*") if p.is_file()}
    assert files
    for name, content in files.items():
        assert not any(marker in content for marker in markers), name
