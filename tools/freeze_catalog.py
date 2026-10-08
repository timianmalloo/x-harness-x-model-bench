"""Freeze one released catalog version: views and board goldens, and the bench/catalog-freeze.yaml entry."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

import yaml

from harness_bench import board, composites, config, views
from harness_bench.grade import runner

FIXTURES = ("c44dd2b-no-heads", "heads")
FREEZE_NAME = "bench/catalog-freeze.yaml"
METRICS = "bench/metrics.yaml"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _fixture_run(name: str) -> Path:
    return _repo_root() / "tests" / "fixtures" / "ledger" / name / "run"


def _control_root(root: Path, tmp: Path) -> Path:
    """The environment the US-4 control grades in (tests/archived_runs.make_root, release=False, plus bench/rubrics):
    root's X1 task, catalog, profiles and rubrics, and an empty price list. Goldens graded under the real root would
    read its live price list, which the control (and CI) never sees, so they would never match (found at the 0.5
    freeze: the board's cost reason differed)."""
    r = tmp / "control-root"
    shutil.copytree(root / "tasks" / "X1", r / "tasks" / "X1")
    (r / "bench").mkdir(parents=True)
    shutil.copy(root / METRICS, r / METRICS)
    shutil.copytree(root / "bench" / "profiles", r / "bench" / "profiles")
    if (root / "bench" / "rubrics").is_dir():
        shutil.copytree(root / "bench" / "rubrics", r / "bench" / "rubrics")
    (r / "bench" / "prices.yaml").write_text(json.dumps({"schema": "bench-prices/1", "currency": "USD",
                                                         "unit": "per_million_tokens", "entries": []}),
                                             encoding="utf-8", newline="\n")  # the bytes tests/archived_runs.set_prices writes
    if runner.catalog_hash(r) != runner.catalog_hash(root):
        raise SystemExit("the control root's catalog_hash differs from the root's; nothing frozen")
    return r


def graded(root: Path, name: str, tmp: Path) -> tuple[bytes, bytes]:
    """One offline pass of fixture `name`: its views export and its board export at the default seed and resamples."""
    run_dir = tmp / f"freeze-{name}-{uuid.uuid4().hex}" / "run"
    shutil.copytree(_fixture_run(name), run_dir)
    runner.run_pass(run_dir, root)
    version = str(config.load_yaml(root / "bench" / "metrics.yaml")["version"])
    view = views.load(run_dir, version)
    return views.export(view), board.export(board.build(view, composites.load_catalog(root)))


def _twice(root: Path, name: str, tmp: Path) -> tuple[bytes, bytes]:
    """Grade the fixture twice and refuse when the two results differ."""
    first = graded(root, name, tmp)
    second = graded(root, name, tmp)
    if first != second:
        raise SystemExit(f"{name}: two grades differ; nothing frozen")
    return first


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _metrics_dirty(root: Path) -> bool:
    """True when bench/metrics.yaml is uncommitted in `root` (no repo counts as dirty: the bytes are unpinned)."""
    done = subprocess.run(["git", "status", "--porcelain", "--", METRICS], cwd=root, capture_output=True, text=True,
                          encoding="utf-8", check=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return done.returncode != 0 or done.stdout.strip() != ""


def freeze(root: Path, golden: Path, freeze_path: Path) -> int:
    """Write the views and board goldens and append the freeze entry for `root`'s current released version.

    Refuses a `.dev` version, a version already present (append-only), and a root whose bench/metrics.yaml is
    uncommitted. Each fixture is graded twice; a disagreement writes nothing.
    """
    version = str(config.load_yaml(root / "bench" / "metrics.yaml")["version"])
    if version.endswith(".dev"):
        raise SystemExit(f"{version} is a probe; a freeze needs a released version")
    if _metrics_dirty(root):
        raise SystemExit(f"{METRICS} is uncommitted; freeze the committed catalog")
    record = yaml.safe_load(freeze_path.read_text(encoding="utf-8")) if freeze_path.is_file() else {}
    record = record or {"schema": "bench-catalog-freeze/1", "versions": {}}
    versions = record.setdefault("versions", {})
    if version in versions:
        raise SystemExit(f"{version} is already frozen ({FREEZE_NAME} is append-only per version)")
    with tempfile.TemporaryDirectory(prefix="freeze-") as raw:
        tmp = Path(raw)
        view_pins, board_pins = {}, {}
        clean = _control_root(root, tmp)
        out = golden / version
        out.mkdir(parents=True, exist_ok=True)
        try:
            for name in FIXTURES:
                view_bytes, board_bytes = _twice(clean, name, tmp)
                (out / f"{name}.export").write_bytes(view_bytes)
                (out / f"{name}.board.export").write_bytes(board_bytes)
                view_pins[name] = _sha(view_bytes)
                board_pins[name] = _sha(board_bytes)
        except SystemExit:
            shutil.rmtree(out, ignore_errors=True)
            raise
    # R-86: the entry names its (catalog, board export) pair, whose golden is the board_golden written above
    versions[version] = {"catalog_hash": runner.catalog_hash(root), "golden": view_pins, "board_golden": board_pins,
                         "board_export_version": str(board.EXPORT_VERSION)}
    freeze_path.write_text(yaml.safe_dump(record, sort_keys=False), encoding="utf-8", newline="\n")  # LF (eol=lf)
    print(f"froze {version}: catalog_hash {versions[version]['catalog_hash']}")
    return 0


def freeze_board_export(root: Path, board_golden: Path, freeze_path: Path) -> int:
    """Write tests/fixtures/board/<N>/ in the control's environment without touching the catalog entries,
    and print the exact YAML the Leader must append to bench/catalog-freeze.yaml."""
    version = str(config.load_yaml(root / "bench" / "metrics.yaml")["version"])
    N = str(board.EXPORT_VERSION)
    with tempfile.TemporaryDirectory(prefix="freeze-board-") as raw:
        tmp = Path(raw)
        board_pins = {}
        clean = _control_root(root, tmp)
        out = board_golden / N
        out.mkdir(parents=True, exist_ok=True)
        try:
            for name in FIXTURES:
                _, board_bytes = _twice(clean, name, tmp)
                (out / f"{name}.board.export").write_bytes(board_bytes)
                board_pins[name] = _sha(board_bytes)
        except SystemExit:
            shutil.rmtree(out, ignore_errors=True)
            raise

    # Print the exact YAML the Leader must append
    record = yaml.safe_load(freeze_path.read_text(encoding="utf-8")) if freeze_path.is_file() else {}
    v05_pins = record.get("versions", {}).get("0.5", {}).get("board_golden", {})
    lines = [
        "board_exports:",
        "  '1':",
        "    catalog: '0.5'",
        "    golden:",
    ]
    for name in FIXTURES:
        lines.append(f"      {name}: {v05_pins.get(name, '')}")
    lines.extend([
        f"  '{N}':",
        f"    catalog: '{version}'",
        "    golden:",
    ])
    for name in FIXTURES:
        lines.append(f"      {name}: {board_pins[name]}")
    yaml_text = "\n".join(lines) + "\n"
    print(f"froze board export version {N} into {out}")
    print("\nExact YAML to append to " + str(freeze_path) + ":\n")
    print(yaml_text)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=_repo_root(), help="bench root whose catalog is frozen")
    ap.add_argument("--golden", type=Path, default=_repo_root() / "tests" / "fixtures" / "catalog",
                    help="directory that receives <version>/<fixture>.export and <fixture>.board.export")
    ap.add_argument("--board-golden", type=Path, default=_repo_root() / "tests" / "fixtures" / "board",
                    help="directory that receives <N>/<fixture>.board.export")
    ap.add_argument("--freeze", type=Path, default=_repo_root() / FREEZE_NAME, help="the freeze record to append to")
    ap.add_argument("--board-export", action="store_true",
                    help="write tests/fixtures/board/<N>/ goldens without touching catalog entries")
    args = ap.parse_args(argv)
    if args.board_export:
        return freeze_board_export(args.root, args.board_golden, args.freeze)
    return freeze(args.root, args.golden, args.freeze)


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            try:
                _stream.reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass
    sys.exit(main())
