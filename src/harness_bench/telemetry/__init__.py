"""Telemetry from each harness's native session record and the adapter's turn usage (ADR-0008 as amended).

Pattern: Anti-Corruption Layer into a Canonical Data Model. Each reader turns one harness's native
record into the same shapes: model calls in disjoint token buckets (uncached input, cache read,
cache write, output; reasoning is a component of output), tool calls, and provider-error rows.

Readers are bounded (ADR-0008, design): a line over 8 MiB, a line nested deep enough to raise
RecursionError, or a line that does not parse is counted as malformed and skipped; a record over
256 MiB is read only to that size. A field of the wrong type is treated as absent. A usage field that is
absent is listed in `Extraction.missing` as HB-TEL-001: NOT_RECORDED, never a silent 0.

MAX_LINE was 1 MiB (HB-CELL-107 fix, 2026-10-02, the same sibling bound as driver.py's own
MAX_LINE and raised for the same measured reason): grid-3's archive has a Claude Code image
tool_result line at 1.0-1.3 MiB and a Codex CommandExecution verbose-stdout line at 2.3 MiB, both
legitimate single tool-result rows that the old bound silently dropped as malformed (NOT_RECORDED
instead of read). 8 MiB keeps a >3x margin over the largest measured line.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

MAX_LINE = 8 << 20
MAX_FILE = 256 << 20


@dataclass(frozen=True)
class ModelCall:
    """One row is exactly one model's token usage in one native usage report, by one principal, as read
    by one extraction (ADR-0006 Amendment 1). For Claude Code and Codex a report is one request, so
    `requests` is always 1. For Copilot a report is the per-model entry in the **last**
    `session.shutdown.modelMetrics`, and it can summarise several requests: `requests` there is
    `requests.count`. `requests` is additive (calls per cell = Σ `requests`); **a row count is not a
    call count**. Its default of 1 is the single home of that default (design D&P C-b) -- a reader that
    does not report it (a pre-amendment ledger, or Claude Code/Codex) reads as one call per row.

    `total_nano_aiu` (ADR-0006 Amendment 2, ruling R-15 Q6) is Copilot's own
    `modelMetrics.<model>.totalNanoAiu`, stored verbatim as an additive measure at this row's grain --
    no arithmetic, no conversion, and no second definition of tokens is derived from it (R-15 c2). Null,
    never 0, when the native record does not carry it (a missing key, or a value that is not an int).
    Claude Code and Codex report no AI-unit measure at all, so their rows leave it null by the dataclass
    default, the same pattern `reasoning` uses for a bucket a harness's format has no concept of."""
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
    total_nano_aiu: int | None = None  # Copilot's native AI-unit billing measure, verbatim; null, never 0, when absent


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


# Codex prints `unexpected status 401 Unauthorized: ...` with no status field (smoke-1). The digits are the status.
_UNEXPECTED_STATUS = re.compile(r"unexpected status (\d{3})\b")


def unexpected_status(message: str) -> int | None:
    """The HTTP status in `unexpected status NNN`, or None when that phrase is absent."""
    found = _UNEXPECTED_STATUS.search(message)
    return int(found.group(1)) if found else None


def as_str(value) -> str | None:
    return value if isinstance(value, str) else None


def as_dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def as_list(value) -> list:
    return value if isinstance(value, list) else []


# The pack-improvement report section's ceremony/drift indicators (design pack-improvement-section.md
# section 4.3, slice S2): one `ToolInput` per tool call, read tolerantly from the same native record
# `read()` already parses, but never stored and never leaving `report.pack_improvement` past a
# derived boolean or count (section 8: privacy and egress).
#
# The header line ends at either of two real shapes, both confirmed against the grid-1/grid-1-cc
# archive (not guessed): Copilot's own `apply_patch` body is a plain, JSON-escaped string, so a
# Windows absolute path's backslashes survive as literal backslash characters and the header ends
# at a real newline (`runs/grid-1/archive/4a6250261f80ded4/.../events.jsonl:126`, a Copilot D1
# cell: `*** Add File: C:\Projects\bench-cells\...\EvidenceCensusProjectionTests.cs`). Codex's own
# call wraps the patch as JS source text the model wrote (`custom_tool_call`'s `arguments`), so the
# patch's internal newlines are themselves the literal two-character escape `\n` -- there is no
# real newline anywhere in that text (`tests/fixtures/native/codex/pack-on.jsonl` line 45). The old
# pattern excluded backslash outright to catch Codex's case, which also truncated a Windows path
# at "C:" -- a verified bug, not a hypothetical one. `.+?` cannot cross a real newline on its own
# (`.` never matches one), so the non-greedy match naturally stops there for Copilot; the `\\n`
# branch stops it at Codex's literal escape. Residual risk, accepted: a path segment that itself
# starts with a literal `n` right after a backslash (e.g. `...\new\...`) would look like the
# Codex escape and truncate early -- not observed in the archive, and strictly better than the
# previous behaviour, which truncated at the FIRST backslash unconditionally.
_PATCH_HEADER = re.compile(r"\*\*\* (?:Add|Update) File: (.+?)(?:\\n|\n|$)")


@dataclass(frozen=True)
class ToolInput:
    """One tool call's inputs (design section 4.3). `paths` and `command` are read as the native
    record states them -- not yet normalised to the cell's `ws` (`report.pack_improvement`'s job,
    which knows the cell's `ws`; a bare reader over one record file does not)."""
    native_ordinal: int
    name: str
    paths: tuple[str, ...]
    command: str | None
    is_write: bool


@dataclass(frozen=True)
class ProcessTrace:
    """One native record's own `tool_inputs()` result, in native order. `first_assistant_text` is
    this record's own first assistant text block (never a sub-agent's; composing the main session
    with its sub-agent records in native order, design section 4.3's comment, is `report.pack_improvement`'s
    job -- this module reads one record at a time)."""
    first_assistant_text: str | None
    calls: tuple[ToolInput, ...] = ()


def patch_header_paths(text: str) -> tuple[str, ...]:
    """Paths named by an `apply_patch` body's own `*** Add File: ` / `*** Update File: ` headers
    (design section 4.3). Shared by Codex (whose call wraps the patch as JS source text) and
    Copilot (whose call carries the patch body as a plain string) -- both formats use the same
    header line, so one regex serves both readers."""
    return tuple(_PATCH_HEADER.findall(text))
