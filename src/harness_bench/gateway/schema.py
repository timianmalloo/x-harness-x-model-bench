"""The one shape of an answer, read from `schemas/verdict-set.v1.json` (design section 8.3 step 4)."""

from __future__ import annotations

from pathlib import Path

SCHEMA_PATH = Path(__file__).resolve().parent / "schemas" / "verdict-set.v1.json"


def schema_sha256() -> str:
    return ""


def validate(answer: object, items: int) -> list[str]:
    return []
