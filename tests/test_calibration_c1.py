"""C1's calibration items (design phase3-gateway-judges sections 4.4 and 11; rulings R-58 c5, R-62 a3, R-72).

Offline and pure. `intended_score` is provenance, never a label (R-72 condition 3): its one reader is the range check
below, and a second test asserts that no code under `src/` reads it.
"""

import getpass
import hashlib
import re
import socket
from pathlib import Path

import yaml

from harness_bench.gateway import scrub

ROOT = Path(__file__).resolve().parents[1]
CAL = ROOT / "bench" / "calibration" / "C1"
RUBRIC = ROOT / "tasks" / "C1" / "oracle" / "rubric.md"
SCORES = {0, 1, 2}
MIN_PER_ITEM = 4


def _rows() -> list[dict]:
    return yaml.safe_load((CAL / "manifest.yaml").read_text(encoding="utf-8"))["items"]


def _rubric_items() -> set[int]:
    return {int(m) for m in re.findall(r"^(\d+)\. \*\*", RUBRIC.read_text(encoding="utf-8"), re.MULTILINE)}


def test_the_range_check_every_rubric_item_has_four_items_and_every_score():
    rows = _rows()
    assert len({r["id"] for r in rows}) == len(rows)
    assert _rubric_items() == set(range(1, 8))
    assert {r["rubric_item"] for r in rows} == _rubric_items()
    assert all(r["intended_score"] in SCORES for r in rows)
    for item in sorted(_rubric_items()):
        mine = [r for r in rows if r["rubric_item"] == item]
        assert len(mine) >= MIN_PER_ITEM, f"rubric item {item}: {len(mine)} items"
        assert {r["intended_score"] for r in mine} == SCORES, f"rubric item {item}: scores {sorted({r['intended_score'] for r in mine})}"
    assert len(rows) == 30


def test_every_item_and_code_file_matches_its_manifest_sha256():
    for r in _rows():
        assert hashlib.sha256((CAL / r["path"]).read_bytes()).hexdigest() == r["sha256"], r["id"]
        assert hashlib.sha256((CAL / r["code"]).read_bytes()).hexdigest() == r["code_sha256"], r["id"]


def _readers(root: Path) -> list[str]:
    return sorted(str(p.relative_to(root)) for p in root.rglob("*.py") if "intended_score" in p.read_text(encoding="utf-8"))


def test_no_code_under_src_reads_intended_score(tmp_path):
    assert all("intended_score" in r for r in _rows())  # the field exists, so the guard is not vacuous
    (tmp_path / "planted.py").write_text("score = row['intended_score']\n", encoding="utf-8")
    assert _readers(tmp_path) == ["planted.py"]  # the guard can fail
    assert _readers(ROOT / "src") == []


def _denylist() -> tuple[str, ...]:
    combos = []
    for m in sorted((ROOT / "bench").glob("matrix*.yaml")):
        combos += (yaml.safe_load(m.read_text(encoding="utf-8")) or {}).get("combos") or []
    return scrub.denylist(ROOT, {"matrix": {"combos": combos}})


IDENTITY = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+|[A-Za-z]:[\\/]Users[\\/]|/home/|/Users/")


def test_no_item_carries_a_denylist_entry_or_an_identity():
    entries = (*_denylist(), getpass.getuser(), socket.gethostname())
    files = sorted({CAL / r["path"] for r in _rows()} | {CAL / r["code"] for r in _rows()})
    for f in files:
        text = f.read_text(encoding="utf-8")
        assert scrub.scan(text, entries) == (), f.name
        assert not IDENTITY.search(text), f.name
