"""The join contract's recount selects tests only through pyproject's addopts (R-104 condition 9, class MARK-A).

A marker expression copied into docs/coordination/join.json stopped tracking addopts when the slow,
gate and browser markers were added (2026-09-23 to 2026-10-04), so every join ran the heavy rings.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_the_join_recount_carries_no_marker_expression_so_addopts_is_the_one_definition():
    recount = json.loads((ROOT / "docs" / "coordination" / "join.json").read_text(encoding="utf-8"))["recount"]
    assert [arg for command in recount for arg in command if arg.startswith("-m")] == []
