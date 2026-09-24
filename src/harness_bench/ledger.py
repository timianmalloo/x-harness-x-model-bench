"""Hash-chained, append-only JSON Lines segments: the run's durable record (ADR-0006).

Pattern: append-only log as a linear hash chain (Schneier & Kelsey 1999) with sealed segment heads
(the RFC 9162 checkpoint idea).

- One segment per writer and fact: `<fact dir>/<segment_id>.jsonl`.
- Every line is the canonical form of a record plus `seq`, `prev_hash` and `hash`, where `hash` is the
  sha256 of the canonical form of everything but `hash`. The first line's `prev_hash` is bound to the
  segment id, so a segment cannot be replayed under another name.
- Canonical form: sorted keys, compact separators, UTF-8, and only str / int / None / list / dict
  (no floats, no bools); a subset of JCS (RFC 8785).
- One write + flush + fsync per line. A failed write raises its `OSError` and poisons the writer: every later
  append or seal raises HB-LED-002.
- `seal()` appends `segment.sealed{count, head_hash}`; nothing may follow it.
- Only the segment's own writer repairs a torn tail (on reopen), and records `ledger.tail_repaired`.
  Readers ignore the torn tail of an unsealed segment. Anything else broken is HB-LED-002.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Self

from harness_bench.errors import BenchError

SEAL = "segment.sealed"
TAIL_REPAIRED = "ledger.tail_repaired"
CHAIN_FIELDS = ("seq", "prev_hash", "hash")

_open_writers: set[str] = set()
_open_lock = threading.Lock()


def _check(value, path: str = "$") -> None:
    if value is None or isinstance(value, str):
        return
    if isinstance(value, bool) or not isinstance(value, (int, list, dict)):
        raise TypeError(f"{path}: {type(value).__name__} is not allowed in the canonical form (str, int, None, list, dict)")
    if isinstance(value, list):
        for i, v in enumerate(value):
            _check(v, f"{path}[{i}]")
    elif isinstance(value, dict):
        for k, v in value.items():
            if not isinstance(k, str):
                raise TypeError(f"{path}: keys must be strings")
            _check(v, f"{path}.{k}")


def canonical(obj: dict) -> bytes:
    """The canonical UTF-8 bytes of a record (ADR-0006)."""
    _check(obj)
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def genesis(segment_id: str) -> str:
    return _digest(f"genesis:{segment_id}".encode())


def stamp(record: dict) -> dict:
    """A record with `recorded_at` (UTC, for people) and `mono_ns` (monotonic, for durations) (ADR-0006)."""
    now = time.time()
    return {**record, "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(now)) + f".{int(now * 1000) % 1000:03d}Z",
            "mono_ns": time.monotonic_ns()}


def _chain(record: dict, seq: int, prev_hash: str) -> dict:
    for f in CHAIN_FIELDS:
        if f in record:
            raise ValueError(f"record may not set {f!r}")
    row = {**record, "seq": seq, "prev_hash": prev_hash}
    row["hash"] = _digest(canonical(row))
    return row


@dataclass
class SegmentReport:
    segment_id: str
    lines: int  # data rows, excluding the seal
    head_hash: str
    sealed: bool
    torn_tail: bool
    error: str | None  # "HB-LED-002" or None
    detail: str = ""


def _scan(path: Path) -> tuple[SegmentReport, list[dict], int]:
    """Verify a segment. Returns the report, the verified rows (seal excluded) and the byte length of
    the verified prefix (used by the owner to truncate a torn tail)."""
    sid = path.stem
    raw = path.read_bytes()
    parts = raw.split(b"\n")
    complete, tail = parts[:-1], parts[-1]  # tail is b"" when the file ends with a newline
    rows: list[dict] = []
    prev = genesis(sid)
    offset = 0
    report = SegmentReport(sid, 0, prev, False, False, None)

    def broken(detail: str) -> tuple[SegmentReport, list[dict], int]:
        report.error, report.detail = "HB-LED-002", detail
        return report, rows, offset

    for index, line in enumerate(complete):
        if report.sealed:  # anything after the seal, parsed or not, is a break: a sealed segment has no torn tail
            return broken(f"bytes after the seal (line {index + 1})")
        last = index == len(complete) - 1 and tail == b""
        try:
            row = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            row = None
        if not isinstance(row, dict):
            if last:  # a final line that fails to parse is a torn tail
                report.torn_tail = True
                break
            return broken(f"line {index + 1} does not parse")
        stored = row.get("hash")
        body = {k: v for k, v in row.items() if k != "hash"}
        try:
            if canonical(row) != line:
                return broken(f"line {index + 1} is not in canonical form")
        except TypeError as exc:
            return broken(f"line {index + 1}: {exc}")
        if body.get("prev_hash") != prev or _digest(canonical(body)) != stored or body.get("seq") != len(rows) + 1:
            return broken(f"chain break at line {index + 1}")
        if row.get("kind") == SEAL:
            if row.get("count") != len(rows) or row.get("head_hash") != prev:
                return broken("seal does not match the segment")
            report.sealed = True
        else:
            rows.append(row)
        prev = stored
        offset += len(line) + 1
    if tail:
        if report.sealed:
            return broken("bytes after the seal")
        report.torn_tail = True
    report.lines = len(rows)
    report.head_hash = rows[-1]["hash"] if rows else genesis(sid)
    return report, rows, offset


def verify_segment(path: Path) -> SegmentReport:
    return _scan(path)[0]


def read_segment(path: Path) -> list[dict]:
    """Verified data rows of one segment (seal excluded, a torn tail ignored). Raises HB-LED-002."""
    report, rows, _ = _scan(path)
    if report.error:
        raise BenchError("HB-LED-002", f"{path.name}: {report.detail}")
    return rows


class SegmentWriter:
    """The single writer of one segment."""

    def __init__(self, path: Path, rows: int, head: str, sealed: bool, repaired: bool) -> None:
        self.path = path
        self.segment_id = path.stem
        self.count = rows
        self.head_hash = head
        self.sealed = sealed
        self.repaired = repaired
        self.failed: OSError | None = None  # the first failed write; set once, never cleared
        key = str(path.resolve())
        with _open_lock:
            if key in _open_writers:
                raise BenchError("HB-LED-002", f"{path.name} already has a writer")
            _open_writers.add(key)
        self._key = key
        self._file = path.open("ab")
        if repaired:
            self.append({"kind": TAIL_REPAIRED, "segment_id": self.segment_id})

    @classmethod
    def create(cls, fact_dir: Path, segment_id: str) -> SegmentWriter:
        fact_dir.mkdir(parents=True, exist_ok=True)
        path = fact_dir / f"{segment_id}.jsonl"
        with path.open("xb"):  # exclusive: a segment is created once
            pass
        return cls(path, 0, genesis(segment_id), False, False)

    @classmethod
    def reopen(cls, path: Path) -> SegmentWriter:
        """The owner reopens its segment; a torn tail is cut back to the last whole line and recorded."""
        report, _, good = _scan(path)
        if report.error:
            raise BenchError("HB-LED-002", f"{path.name}: {report.detail}")
        if report.sealed:
            raise BenchError("HB-LED-002", f"{path.name} is sealed")
        if report.torn_tail:
            with path.open("r+b") as f:
                f.truncate(good)
                f.flush()
                os.fsync(f.fileno())
        seq_rows = report.lines
        return cls(path, seq_rows, report.head_hash, False, report.torn_tail)

    def _write(self, row: dict) -> None:
        """One line, flushed and fsynced. The first failed write poisons the writer: part of the line may be on
        disk, so every later append or seal is refused (HB-LED-002) rather than written after a torn line."""
        if self.failed is not None:
            raise BenchError("HB-LED-002", f"{self.path.name}: an earlier write failed ({self.failed}); append refused") from self.failed
        line = canonical(row) + b"\n"
        try:
            self._file.write(line)
            self._file.flush()
            os.fsync(self._file.fileno())
        except OSError as exc:
            self.failed = exc
            raise

    def append(self, record: dict) -> dict:
        if self.sealed:
            raise BenchError("HB-LED-002", f"{self.path.name} is sealed; append refused")
        if record.get("kind") == SEAL:
            raise ValueError(f"record may not be of kind {SEAL!r}; only seal() writes it")
        row = _chain(record, self.count + 1, self.head_hash)
        self._write(row)
        self.count += 1
        self.head_hash = row["hash"]
        return row

    def seal(self) -> str:
        if self.sealed:
            return self.head_hash
        row = _chain({"kind": SEAL, "count": self.count, "head_hash": self.head_hash}, self.count + 1, self.head_hash)
        self._write(row)
        self.sealed = True
        return self.head_hash

    def close(self) -> None:
        if not self._file.closed:
            self._file.close()
        with _open_lock:
            _open_writers.discard(self._key)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc) -> None:
        self.close()
