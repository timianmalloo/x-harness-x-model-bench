"""The shared change reader: a cell's pre-turn commit and its change set (design phase3-graders, GR-CODE c1).

Red-first stub: the signatures only.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path

NOT_FOUND = "pre-turn commit not found in the working copy"


def pre_turn_commit(ws: Path, cell: Mapping, timeout: float) -> str | None:
    return None


@contextmanager
def pre_turn_tree(ws: Path, commit: str, dest: Path, timeout: float) -> Iterator[Path]:
    yield dest


@contextmanager
def grading_copy(ws: Path, dest: Path) -> Iterator[Path]:
    yield dest


def change_set(before: Path, after: Path) -> dict[str, str]:
    return {}
