"""Property grader tests (design: docs/design/eval-property-grader.md, W1-F rev 3). F0: the skeleton exists."""

import importlib.util
import inspect
import re
import subprocess
import sys
from pathlib import Path

import pytest

from harness_bench.grade import _changes, correctness, formal


def test_property_module_exists_as_docstring_only_skeleton():
    spec = importlib.util.find_spec("harness_bench.grade.property")
    assert spec is not None, (
        "grade/property.py is missing (W0 section 7: X-G1 needs the module)"
    )
    module = importlib.import_module("harness_bench.grade.property")
    assert inspect.getdoc(module), "the skeleton carries a docstring"
    public = [n for n in vars(module) if not n.startswith("_")]
    assert public == [], f"F0 is a docstring only; found {public}"


# --- F1: G4, the one allowlist (W0 section 10 G4; ADR-0018 section 9) ---

SRC = Path(__file__).resolve().parents[1] / "src" / "harness_bench"
HOST_ENV_DEFINERS = {"grade/_env.py"}
ENVIRON_READERS = {"grade/_env.py"}
HOST_ENV_TOKEN = re.compile(r"\bHOST_ENV\s*=")


def scan(root: Path, rels, token) -> set[str]:
    return {r for r in rels if token.search((root / r).read_text(encoding="utf-8"))}


def test_host_env_defined_once():
    grade = SRC / "grade"
    rels = [p.relative_to(SRC).as_posix() for p in grade.rglob("*.py")]
    assert scan(SRC, rels, HOST_ENV_TOKEN) == HOST_ENV_DEFINERS
    readers = scan(
        SRC, ["grade/property.py", "grade/_env.py"], re.compile(r"os\.environ")
    )
    assert readers <= ENVIRON_READERS


def test_host_env_scan_catches_a_second_definition_and_ignores_dotnet_tuple(tmp_path):
    (tmp_path / "a.py").write_text('HOST_ENV = ("PATH",)\n')
    (tmp_path / "b.py").write_text('DOTNET_HOST_ENV = ("PATH",)\n')
    assert scan(tmp_path, ["a.py", "b.py"], HOST_ENV_TOKEN) == {"a.py"}


# --- F1: RF-9, one reparse-safe copy helper for every grader copy ---


def make_tree_with_junction(tmp_path):
    """A workspace holding a directory junction to a sentinel folder outside it; returns (ws, sentinel, snapshot)."""
    sentinel = tmp_path / "sentinel"
    sentinel.mkdir()
    (sentinel / "secret.txt").write_text("do not copy", encoding="utf-8")
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "keep.txt").write_text("kept", encoding="utf-8")
    link = ws / "escape"
    if sys.platform == "win32":
        made = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(sentinel)],
            capture_output=True,
            check=False,
        )
        if made.returncode != 0:
            pytest.skip("cannot create a junction here")
    else:
        pytest.skip(
            "a junction is a Windows reparse point; POSIX symlinks are kept as links"
        )
    snapshot = {p.name: (p.read_bytes(), p.stat().st_mode) for p in sentinel.iterdir()}
    return ws, sentinel, snapshot


def sentinel_unchanged(sentinel, snapshot):
    now = {p.name: (p.read_bytes(), p.stat().st_mode) for p in sentinel.iterdir()}
    return now == snapshot


def test_grading_copy_with_junction_leaves_target_untouched_changes(tmp_path):
    ws, sentinel, snapshot = make_tree_with_junction(tmp_path)
    with _changes.grading_copy(ws, tmp_path / "copy") as copy:
        assert (copy / "keep.txt").read_text() == "kept"
        assert not (copy / "escape").exists(), "the junction target was copied"
    assert not (tmp_path / "copy").exists()
    assert sentinel_unchanged(sentinel, snapshot)


def test_grading_copy_with_junction_leaves_target_untouched_correctness(tmp_path):
    ws, sentinel, snapshot = make_tree_with_junction(tmp_path)
    task = tmp_path / "task"
    (task / "tests").mkdir(parents=True)
    (task / "tests" / "test_ok.py").write_text(
        "import unittest\nclass T(unittest.TestCase):\n    def test_a(self): pass\n"
    )
    probe = "import os, sys; sys.exit(0 if os.path.exists('keep.txt') and not os.path.exists('escape') else 3)"
    oracle = {"runner": "unittest", "command": ["{python}", "-c", probe]}
    run_dir = tmp_path / "run"
    out = run_dir / "out"
    out.mkdir(parents=True)
    correctness.grade(ws, task, oracle, out, run_dir, 60, tmp_path / "wd")
    log = (out / "oracle.log").read_text()
    assert "\nexit 0\n" in log, "the junction target was copied into the oracle's copy"
    assert sentinel_unchanged(sentinel, snapshot)


def test_grading_copy_with_junction_leaves_target_untouched_formal(tmp_path):
    ws, sentinel, snapshot = make_tree_with_junction(tmp_path)
    with formal._grading_copy(ws, tmp_path / "copy") as copy:
        assert (copy / "keep.txt").read_text() == "kept"
        assert not (copy / "escape").exists(), "the junction target was copied"
    assert sentinel_unchanged(sentinel, snapshot)

