"""The verdict store: a request-keyed memo store, write-once, with one hit check (design sections 4.3, 9)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

FORMAT = "verdict-set/1"
KEY_FIELDS = ("request_sha256", "schema_sha256", "model", "invocation_sha256")


@dataclass(frozen=True)
class Found:
    state: str
    code: str | None = None
    entry: dict | None = None
    entry_sha256: str | None = None


def key(key_inputs: dict) -> str:
    return ""


def write_once(root: Path, cache_key: str, entry: dict) -> Found:
    return Found("failed", "HB-GW-001")


def lookup(root: Path, cache_key: str, known_roots: tuple[Path, ...], allowed_models: tuple[str, ...],
           own_run: Path | None) -> Found:
    return Found("miss")


def verify_entries(root: Path, references: list[dict]) -> list[str]:
    return []
