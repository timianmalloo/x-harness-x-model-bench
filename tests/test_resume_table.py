"""X-CV: the ADR-0021 section 4 table is covered node by node (docs/design/eval-resume.md section 4).

The kill-then-resume tests themselves live in tests/test_resume.py (X-K1), tests/test_alarm.py and
tests/test_status.py (X-K2b); this file does not re-implement them. It parses the design table and asserts
that every window row names a node id, that pytest collects every named node, and that none carries a
skip or xfail marker, so a row that loses its test, or whose test is switched off, turns this red.

Set HB_RESUME_TABLE_DOC to a copy of the design doc to check that copy instead (the red-first run).
"""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DOC = Path(
    os.environ.get("HB_RESUME_TABLE_DOC") or ROOT / "docs" / "design" / "eval-resume.md"
)
FILES = ("tests/test_resume.py", "tests/test_alarm.py", "tests/test_status.py")
SECTION = re.compile(
    r"^## 4\. ADR-0021 section 4:.*?(?=^## 5)", re.DOTALL | re.MULTILINE
)
ROW = re.compile(r"^\| (W\d+\w*) \|", re.MULTILINE)


def table_nodes(text: str) -> dict[str, list[str]]:
    """Window row -> full node ids (repo-relative), the design's `...` and bare `[param]` forms expanded."""
    section = SECTION.search(text)
    assert section, "section 4 of the design doc is missing"
    rows: dict[str, list[str]] = {}
    base = ""
    for line in section.group(0).splitlines():
        match = ROW.match(line)
        if not match:
            continue
        cells = line.split("|")
        nodes = []
        for span in re.findall(r"`([^`]+)`", cells[4]):
            if span.startswith("..."):
                span = span[3:]
                span = (
                    (base.split("::")[0] + span)
                    if span.startswith("::")
                    else (base + span)
                )
            elif span.startswith("["):
                span = base + span
            base = span.split("[")[0]
            nodes.append("tests/" + span if "/" not in span.split("::")[0] else span)
        rows[match.group(1)] = nodes
    return rows


def _collect(*extra: str) -> set[str]:
    out = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
            *extra,
            *FILES,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    return {line.strip() for line in out.splitlines() if "::" in line}


@pytest.fixture(scope="module")
def collected() -> tuple[set[str], set[str]]:
    return _collect(), _collect("-m", "skip or xfail")


def problems(
    rows: dict[str, list[str]], everything: set[str], switched_off: set[str]
) -> list[str]:
    found = []
    for row, nodes in rows.items():
        if not nodes:
            found.append(f"{row}: names no node id")
        for node in nodes:
            if node not in everything:
                found.append(f"{row}: {node} is not collected")
            elif node in switched_off:
                found.append(f"{row}: {node} carries a skip or xfail marker")
    return found


def test_every_section_4_row_names_a_live_collected_node(collected):
    rows = table_nodes(DOC.read_text(encoding="utf-8"))
    assert len(rows) >= 19, f"only {len(rows)} window rows parsed"
    everything, switched_off = collected
    assert problems(rows, everything, switched_off) == []


def test_the_check_reports_a_missing_node_and_a_switched_off_one():
    rows = {"W2": ["tests/test_resume.py::test_window[W2]"], "W9": []}
    assert problems(rows, {"tests/test_resume.py::test_window[W2]"}, set()) == [
        "W9: names no node id"
    ]
    assert problems(rows, set(), set()) == [
        "W2: tests/test_resume.py::test_window[W2] is not collected",
        "W9: names no node id",
    ]
    assert problems(
        rows,
        {"tests/test_resume.py::test_window[W2]"},
        {"tests/test_resume.py::test_window[W2]"},
    ) == [
        "W2: tests/test_resume.py::test_window[W2] carries a skip or xfail marker",
        "W9: names no node id",
    ]
