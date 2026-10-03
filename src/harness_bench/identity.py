"""Engine classification and catalog identity (W1-D, dispatch D1).

One class per source file, keyed relative to src/harness_bench/. The manifest
and launch recheck are dispatch D2.
"""

from collections.abc import Mapping
from pathlib import Path
from typing import Literal

CLASSES: Mapping[str, Literal["run", "grade"]] = {}
PLANNED: frozenset[str] = frozenset()
RUN_IMPORTS_GRADE_ALLOWED: Mapping[tuple[str, str], str] = {}


def catalog_hash(root: Path) -> str:
    """The single catalog recipe, moved from grade.runner in the green step."""
    return ""


def unclassed(root: Path, classes: Mapping[str, str], planned: frozenset[str]) -> list[str]:
    """Return disk files without a class; root is the repository root."""
    return []


def stale(root: Path, classes: Mapping[str, str], planned: frozenset[str]) -> list[str]:
    """Return ghost class entries and planned entries that have landed."""
    return []
