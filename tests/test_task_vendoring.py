"""R-42: D1's public base is exactly its pinned archive selection."""

from __future__ import annotations

import io
import subprocess
import zipfile
from pathlib import Path

import pytest

from harness_bench.config import load_yaml

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "tasks" / "D1"
WORKSPACE = TASK / "workspace"
SOURCE = Path("C:/projects/ai-de")


def _files() -> dict[str, bytes]:
    return {
        path.relative_to(WORKSPACE).as_posix(): path.read_bytes()
        for path in WORKSPACE.rglob("*")
        if path.is_file()
    }


def test_d1_workspace_matches_pinned_git_archive_byte_for_byte() -> None:
    if not (SOURCE / ".git").exists():
        pytest.skip("C:/projects/ai-de is absent; pinned git archive cannot be rebuilt locally")

    source = load_yaml(TASK / "task.yaml")["source"]
    assert source["repo"] == "https://github.com/timianmalloo/ai-de"
    paths = [path.rstrip("/") for path in source["vendored_paths"]]
    exclusions = [f":(exclude){path}" for path in source["excluded_paths"]]
    archive = subprocess.run(
        ["git", "-C", str(SOURCE), "archive", "--format=zip", source["commit"], "--", *paths, *exclusions],
        check=True,
        capture_output=True,
    ).stdout
    with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
        expected = {name: zipped.read(name) for name in zipped.namelist() if not name.endswith("/")}

    actual = _files()
    assert actual.keys() == expected.keys()
    for name, original in expected.items():
        assert actual[name] == original, name


def test_d1_workspace_has_no_pack_markers_or_generated_content() -> None:
    files = _files()
    forbidden_parts = {
        ".agents", ".claude", ".github", ".grok", "bin", "obj", ".nuget", ".git",
        ".cache", "__pycache__", ".pytest_cache",
    }
    forbidden_names = {"AGENTS.md", "CLAUDE.md", "THIRD-PARTY-NOTICES.md", ".env"}
    forbidden_suffixes = {".pem", ".pfx", ".key"}
    markers = [line.encode() for line in (ROOT / "bench/pack-markers.txt").read_text().splitlines() if line]
    assert files
    for name, content in files.items():
        parts = Path(name).parts
        assert not forbidden_parts.intersection(parts), name
        assert not any(part in forbidden_names for part in parts), name
        assert Path(name).suffix.lower() not in forbidden_suffixes, name
        assert not name.startswith("docs/ai-forward-pack/"), name
        assert not any(marker in content for marker in markers), name
