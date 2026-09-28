"""tools/freeze_catalog.py: write the views and board goldens and the freeze entry for one released catalog version.

Every case runs on a tmp root. The real bench/catalog-freeze.yaml, bench/metrics.yaml and tests/fixtures/catalog/
are never the tool's target.
"""

import hashlib
import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from archived_runs import ROOT, make_root, set_catalog_version

from harness_bench import board as board_mod
from harness_bench import composites, config, views
from harness_bench.grade import runner

_spec = importlib.util.spec_from_file_location("freeze_catalog", ROOT / "tools" / "freeze_catalog.py")
freeze_catalog = importlib.util.module_from_spec(_spec)
sys.modules["freeze_catalog"] = freeze_catalog
_spec.loader.exec_module(freeze_catalog)

FIXTURES = ("c44dd2b-no-heads", "heads")


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, encoding="utf-8", check=False)


def _repo(tmp_path: Path, version: str = "9.1") -> Path:
    """A tmp bench root that is its own git repo, with bench/metrics.yaml committed at `version`."""
    root = make_root(tmp_path)
    set_catalog_version(root, version)
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "-c", "user.email=freeze@test", "-c", "user.name=freeze", "commit", "-q", "-m", "catalog")
    assert _git(root, "status", "--porcelain", "--", "bench/metrics.yaml").stdout == ""
    return root


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_freeze_writes_both_goldens_and_the_entry(tmp_path):
    """A released version gets views and board goldens (each graded twice) and catalog_hash, golden, board_golden."""
    root = _repo(tmp_path)
    golden = tmp_path / "golden"
    freeze_path = tmp_path / "catalog-freeze.yaml"
    assert freeze_catalog.freeze(root, golden, freeze_path) == 0
    version = str(config.load_yaml(root / "bench" / "metrics.yaml")["version"])
    entry = yaml.safe_load(freeze_path.read_text(encoding="utf-8"))["versions"][version]
    assert entry["catalog_hash"] == runner.catalog_hash(root)
    for name in FIXTURES:
        view_bytes = (golden / version / f"{name}.export").read_bytes()
        board_bytes = (golden / version / f"{name}.board.export").read_bytes()
        run = tmp_path / "check" / name / "run"
        shutil.copytree(ROOT / "tests" / "fixtures" / "ledger" / name / "run", run)
        runner.run_pass(run, root)
        view = views.load(run, version)
        assert views.export(view) == view_bytes
        assert board_mod.export(board_mod.build(view, composites.load_catalog(root))) == board_bytes
        assert entry["golden"][name] == _sha(view_bytes)
        assert entry["board_golden"][name] == _sha(board_bytes)


def test_freeze_refuses_a_dev_version(tmp_path):
    root = _repo(tmp_path, "9.2.dev")
    with pytest.raises(SystemExit) as exc:
        freeze_catalog.freeze(root, tmp_path / "golden", tmp_path / "catalog-freeze.yaml")
    assert exc.value.code != 0
    assert not (tmp_path / "catalog-freeze.yaml").exists()


def test_freeze_refuses_an_already_frozen_version(tmp_path):
    root = _repo(tmp_path)
    golden, freeze_path = tmp_path / "golden", tmp_path / "catalog-freeze.yaml"
    assert freeze_catalog.freeze(root, golden, freeze_path) == 0
    before = freeze_path.read_bytes()
    with pytest.raises(SystemExit) as exc:
        freeze_catalog.freeze(root, golden, freeze_path)
    assert exc.value.code != 0
    assert freeze_path.read_bytes() == before  # append-only: the existing entry is untouched


def test_freeze_refuses_uncommitted_metrics(tmp_path):
    root = _repo(tmp_path)
    path = root / "bench" / "metrics.yaml"
    path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        freeze_catalog.freeze(root, tmp_path / "golden", tmp_path / "catalog-freeze.yaml")
    assert exc.value.code != 0
    assert not (tmp_path / "catalog-freeze.yaml").exists()


def test_freeze_refuses_when_the_two_grades_differ(tmp_path, monkeypatch):
    """A golden graded twice that comes back different is refused, and nothing is written."""
    root = _repo(tmp_path)
    calls = {"n": 0}
    real = freeze_catalog.graded

    def flip(root, name, tmp):
        calls["n"] += 1
        view_bytes, board_bytes = real(root, name, tmp)
        if calls["n"] % 2 == 0:  # the second grade of a fixture disagrees
            board_bytes += b" "
        return view_bytes, board_bytes

    monkeypatch.setattr(freeze_catalog, "graded", flip)
    with pytest.raises(SystemExit) as exc:
        freeze_catalog.freeze(root, tmp_path / "golden", tmp_path / "catalog-freeze.yaml")
    assert exc.value.code != 0
    assert not (tmp_path / "catalog-freeze.yaml").exists()
    assert list((tmp_path / "golden").rglob("*")) == []
