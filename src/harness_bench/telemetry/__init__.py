"""Telemetry from each harness's native session record and the adapter's turn usage (ADR-0008 as amended).

Pattern: Anti-Corruption Layer into a Canonical Data Model. Each reader turns one harness's native
record into the same shapes: model calls in disjoint token buckets (uncached input, cache read,
cache write, output; reasoning is a component of output), tool calls, and provider-error rows.

Readers are bounded (ADR-0008, design): a line over 1 MiB, a line nested deep enough to raise
RecursionError, or a line that does not parse is counted as malformed and skipped; a record over
256 MiB is read only to that size. A field of the wrong type is treated as absent. A usage field that is
absent is listed in `Extraction.missing` as HB-TEL-001: NOT_RECORDED, never a silent 0.
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
    """One row is exactly one model's token usage in one native usage report, by one principal, as read
    by one extraction (ADR-0006 Amendment 1). For Claude Code and Codex a report is one request, so
    `requests` is always 1. For Copilot a report is the per-model entry in the **last**
    `session.shutdown.modelMetrics`, and it can summarise several requests: `requests` there is
    `requests.count`. `requests` is additive (calls per cell = Σ `requests`); **a row count is not a
    call count**. Its default of 1 is the single home of that default (design D&P C-b) -- a reader that
    does not report it (a pre-amendment ledger, or Claude Code/Codex) reads as one call per row."""
    native_ordinal: int
    model: str
    uncached_input: int
    cache_read: int
    cache_write: int
    output: int
    reasoning: int | None  # a component of output; None when the harness does not report it
    start: str | None = None
    end: str | None = None
    requests: int = 1


@dataclass(frozen=True)
class ToolCall:
    native_ordinal: int
    name: str
    tool_class: str  # shell | edit | read | other
    start: str | None
    end: str | None
    ok: bool | None
    outcome_code: str | None = None  # the native error code of a failed call (e.g. "denied"); null on success


@dataclass(frozen=True)
class ProviderError:
    native_ordinal: int
    status: int | None
    error_type: str
    message: str


@dataclass(frozen=True)
class MissingField:
    """A field the record should carry for a model call but does not (HB-TEL-001). The call's bucket holds 0,
    so a consumer treats a measure built from this call as NOT_RECORDED, never as 0."""
    native_ordinal: int
    field: str
    code: str = "HB-TEL-001"


@dataclass
class Extraction:
    session_id: str | None = None
    model_calls: list[ModelCall] = field(default_factory=list)
    tool_calls: list[ToolCall] = field(default_factory=list)
    errors: list[ProviderError] = field(default_factory=list)
    first_user_text: str | None = None
    malformed_lines: int = 0
    truncated: bool = False
    missing: list[MissingField] = field(default_factory=list)
    # US-9 live signal (Copilot only): hook invocations and hook failures seen in the record.
    # None = the harness records no hooks at all (Claude Code, Codex); an int, possibly 0, means the
    # harness's format supports hook telemetry and this many were counted (design section 4.5).
    hook_starts: int | None = None
    hook_failures: int | None = None
    # R-36, R-43: distinct mcp__claude_ai_* tools advertised; None means not read (unreadable record, or not Claude Code), never 0.
    account_connector_tools: int | None = None
    # R-45: Copilot's checkpoint advertises tool ids to the model. None means the checkpoint was
    # not readable or absent; an empty list must never imply a measured absence of tools.
    tools_advertised: list[str] | None = None

    def count(self, n: int, usage: dict, key: str) -> int:
        """The usage field `key` of the call at line `n`; absent or not a count is HB-TEL-001 (and 0 in the bucket)."""
        value = usage.get(key)
        if is_count(value):
            return value
        self.missing.append(MissingField(n, key))
        return 0


def rows(path: Path, ex: Extraction) -> Iterator[tuple[int, dict]]:
    """(1-based line number, object) for every well-formed JSON object line, bounded."""
    read = n = 0
    with path.open("rb") as f:
        while raw := f.readline(MAX_LINE + 1):  # never more than one bounded piece in memory
            n += 1
            read += len(raw)
            too_long = len(raw) > MAX_LINE
            while too_long and not raw.endswith(b"\n") and read <= MAX_FILE and (raw := f.readline(MAX_LINE + 1)):
                read += len(raw)  # skip the rest of the over-long line, piece by piece
            if read > MAX_FILE:
                ex.truncated = True
                return
            if too_long:
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
