"""The verdict store: a request-keyed memo store, write-once, with one hit check (design sections 4.3, 9).

- **Key** (section 9.1): sha256 of the canonical form (ADR-0006:49) of exactly four inputs: the request's sha256,
  the schema's sha256, the model and the invocation's sha256. The entry keeps them as `key_inputs`, so its file name
  can be recomputed from its content.
- **Write-once** (section 9.2): the entry goes to `.<key>.<rand>.tmp`, is flushed and fsynced, then `os.link`ed to
  `<key>.json`. `link` refuses an existing target on every OS, so the first writer wins. Only `FileExistsError` is a
  lost race; any other error is `HB-GW-001`. The entry is then read-only.
- **Hit acceptance** (section 9.3): the one check. An entry is accepted only when it parses, its `key_inputs`
  recompute its name, its served models are allowed, and its storing ledger vouches for it: `stored_by` names a
  ledger inside a known `runs/` root, whose sealed, chain-verified segments hold a `stored` row with this key and
  this entry's sha256 and a `gateway` `model_calls` row with its native session id, beside its archived record.
  A ledger that no longer exists orphans the entry: it is accepted only from this run's own earlier row.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import stat
from dataclasses import dataclass
from pathlib import Path

from harness_bench import ledger

FORMAT = "verdict-set/1"
KEY_FIELDS = ("request_sha256", "schema_sha256", "model", "invocation_sha256")
STALE_TMP_SECONDS = 24 * 3600
USES_FACT = {"run": "verdict_uses", "calibration": "calibration_uses"}
_SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")  # one path component, never "." or ".."


@dataclass(frozen=True)
class Found:
    state: str  # miss | hit | orphaned | stored | race_lost | failed
    code: str | None = None
    entry: dict | None = None
    entry_sha256: str | None = None


def key(key_inputs: dict) -> str:
    if set(key_inputs) != set(KEY_FIELDS):
        raise ValueError(f"key inputs must be exactly {', '.join(KEY_FIELDS)}")
    return hashlib.sha256(ledger.canonical({f: key_inputs[f] for f in KEY_FIELDS})).hexdigest()


def _read(path: Path) -> tuple[dict | None, str | None]:
    """(the parsed entry or None, the sha256 of its bytes or None when the file is absent)."""
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return None, None
    try:
        entry = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        entry = None
    return (entry if isinstance(entry, dict) else None), hashlib.sha256(data).hexdigest()


def _recomputes(entry: dict, cache_key: str, allowed_models: tuple[str, ...]) -> bool:
    """A verdict set whose key inputs recompute its name and whose served models are all allowed."""
    inputs, served = entry.get("key_inputs"), entry.get("served_models")
    try:
        named = isinstance(inputs, dict) and key(inputs) == cache_key
    except (TypeError, ValueError):
        return False
    return (entry.get("format") == FORMAT and named and isinstance(entry.get("verdicts"), list)
            and isinstance(served, list) and bool(served) and all(m in allowed_models for m in served))


def write_once(root: Path, cache_key: str, entry: dict, allowed_models: tuple[str, ...] = ()) -> Found:
    """stored, race_lost (with the winner's entry, accepted on key inputs and served models only), or failed."""
    data = ledger.canonical(entry)
    target, tmp = root / f"{cache_key}.json", root / f".{cache_key}.{secrets.token_hex(4)}.tmp"
    try:
        root.mkdir(parents=True, exist_ok=True)
        with tmp.open("xb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.link(tmp, target)
    except FileExistsError:
        winner, sha = _read(target)
        if winner is None or not _recomputes(winner, cache_key, allowed_models):
            return Found("failed", "HB-GW-005")
        return Found("race_lost", None, winner, sha)
    except OSError:
        return Found("failed", "HB-GW-001")
    finally:
        tmp.unlink(missing_ok=True)
    os.chmod(target, stat.S_IREAD)
    return Found("stored", None, entry, hashlib.sha256(data).hexdigest())


def _sealed_rows(path: Path) -> list[dict] | None:
    """The rows of a sealed segment whose chain verifies from its genesis row; None otherwise."""
    if not path.is_file():
        return None
    report = ledger.verify_segment(path)
    return ledger.read_segment(path) if report.error is None and report.sealed else None


def _vouches(folder: Path, fact: str, pass_id: str, cache_key: str, sha: str, session: str) -> bool:
    """The storing pass's sealed segments and archived record vouch for this exact entry.

    A calibration ledger keeps the run layout (`<fact>/<id>.jsonl`, `grading/<id>/gateway/<call>/record.jsonl`):
    `gateway.calibration.run` writes it so (slice 5), and a second calibration pass reads its entries as hits
    (tests/test_calibrate.py).
    """
    uses = _sealed_rows(folder / fact / f"{pass_id}.jsonl")
    calls = _sealed_rows(folder / "model_calls" / f"{pass_id}.jsonl")
    record = folder / "grading" / pass_id / "gateway" / cache_key[:16] / "record.jsonl"
    return (uses is not None and calls is not None and record.is_file()
            and any(r.get("outcome") == "stored" and r.get("cache_key") == cache_key and r.get("entry_sha256") == sha
                    for r in uses)
            and any(r.get("principal") == "gateway" and r.get("native_session_id") == session for r in calls))


def _own_row(own_run: Path, cache_key: str, sha: str) -> bool:
    """This run's own sealed ledger holds an earlier row with this key and this entry's sha256."""
    for fact in USES_FACT.values():
        for seg in sorted((own_run / fact).glob("*.jsonl")):
            rows = _sealed_rows(seg)
            if rows and any(r.get("cache_key") == cache_key and r.get("entry_sha256") == sha for r in rows):
                return True
    return False


def lookup(root: Path, cache_key: str, known_roots: tuple[Path, ...], allowed_models: tuple[str, ...],
           own_run: Path | None) -> Found:
    """miss, hit, orphaned (the storing ledger is gone), or failed HB-GW-005. Reads sealed segments only."""
    entry, sha = _read(root / f"{cache_key}.json")
    if sha is None:
        return Found("miss")
    if entry is None or not _recomputes(entry, cache_key, allowed_models):
        return Found("failed", "HB-GW-005")
    by = entry.get("stored_by") if isinstance(entry.get("stored_by"), dict) else {}
    fact, ledger_id, pass_id = USES_FACT.get(by.get("ledger")), by.get("ledger_id"), by.get("grading_or_calibration_id")
    session = entry.get("native_session_id")
    if fact is None or not isinstance(session, str) or not all(
            isinstance(v, str) and _SAFE_ID.fullmatch(v) and v not in (".", "..") for v in (ledger_id, pass_id)):
        return Found("failed", "HB-GW-005")  # names no storing ledger, or a path outside the known roots
    folders = [r / ledger_id for r in known_roots
               if (r / ledger_id).is_dir() and (r / ledger_id).resolve().parent == r.resolve()]
    if folders:
        vouched = any(_vouches(f, fact, pass_id, cache_key, sha, session) for f in folders)
        return Found("hit", None, entry, sha) if vouched else Found("failed", "HB-GW-005")
    if own_run is not None and _own_row(own_run, cache_key, sha):
        return Found("hit", None, entry, sha)
    return Found("orphaned")


def move_orphan(root: Path, cache_key: str, utc: str) -> Path:
    """Move an orphaned entry to `orphaned/<key>.<utc>.json`, so a fresh call can store under its key (T-GW-13d)."""
    source, dest = root / f"{cache_key}.json", root / "orphaned" / f"{cache_key}.{utc}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(source, stat.S_IREAD | stat.S_IWRITE)
    os.rename(source, dest)
    os.chmod(dest, stat.S_IREAD)
    return dest


def verify_entries(root: Path, references: list[dict]) -> list[str]:
    """`bench verify`'s store warnings: each referenced entry that is missing, or whose bytes changed since stored."""
    out = []
    for ref in references:
        _, sha = _read(root / f"{ref['cache_key']}.json")
        if sha is None:
            out.append(f"{ref['cache_key']}: missing")
        elif sha != ref["entry_sha256"]:
            out.append(f"{ref['cache_key']}: changed since stored")
    return out


def sweep_tmp(root: Path, now: float) -> list[str]:
    """Remove each `.tmp` older than 24 h (a crash mid-write); return the names removed."""
    removed = []
    for tmp in sorted(root.glob(".*.tmp")) if root.is_dir() else []:
        if now - tmp.stat().st_mtime > STALE_TMP_SECONDS:
            tmp.unlink(missing_ok=True)
            removed.append(tmp.name)
    return removed
