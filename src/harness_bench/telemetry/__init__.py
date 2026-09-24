"""Telemetry from each harness's native session record and the adapter's turn usage (ADR-0008 as amended).

Pattern: Anti-Corruption Layer into a Canonical Data Model. Each reader turns one harness's native
record into the same shapes: model calls in disjoint token buckets (uncached input, cache read,
cache write, output; reasoning is a component of output), tool calls, and provider-error rows.

Readers are bounded (ADR-0008, design): a line over 1 MiB, a line nested deep enough to raise
RecursionError, or a line that does not parse is counted as malformed and skipped; a record over
256 MiB is read only to that size. A field that is absent is NOT_RECORDED, never 0.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

MAX_LINE = 1 << 20
MAX_FILE = 256 << 20


@dataclass(frozen=True)
class ModelCall:
    native_ordinal: int
    model: str
    uncached_input: int
    cache_read: int
    cache_write: int
    output: int
    reasoning: int | None  # a component of output; None when the harness does not report it
    start: str | None = None
    end: str | None = None


@dataclass(frozen=True)
class ToolCall:
    native_ordinal: int
    name: str
    tool_class: str  # shell | edit | read | other
    start: str | None
    end: str | None
    ok: bool | None


@dataclass(frozen=True)
class ProviderError:
    native_ordinal: int
    status: int | None
    error_type: str
    message: str


@dataclass
class Extraction:
    session_id: str | None = None
    model_calls: list[ModelCall] = field(default_factory=list)
    tool_calls: list[ToolCall] = field(default_factory=list)
    errors: list[ProviderError] = field(default_factory=list)
    first_user_text: str | None = None
    malformed_lines: int = 0
    truncated: bool = False


def rows(path: Path, ex: Extraction) -> Iterator[tuple[int, dict]]:
    """(1-based line number, object) for every well-formed JSON object line, bounded."""
    read = 0
    with path.open("rb") as f:
        for n, raw in enumerate(f, 1):
            read += len(raw)
            if read > MAX_FILE:
                ex.truncated = True
                return
            if len(raw) > MAX_LINE:
                ex.malformed_lines += 1
                continue
            try:
                obj = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, ValueError, RecursionError):
                if raw.strip():
                    ex.malformed_lines += 1
                continue
            if isinstance(obj, dict):
                yield n, obj
            else:
                ex.malformed_lines += 1


# The record is untrusted input: a field of the wrong type is treated as absent, so no foreign type reaches a row.
def is_count(value) -> bool:
    """A token count: an int (never a bool) that fits a signed 64-bit column and is not negative."""
    return type(value) is int and 0 <= value < 1 << 63


def as_int(value) -> int:
    return value if is_count(value) else 0


def as_status(value) -> int | None:
    return value if type(value) is int else None


def as_str(value) -> str | None:
    return value if isinstance(value, str) else None


def as_dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def as_list(value) -> list:
    return value if isinstance(value, list) else []
