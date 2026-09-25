"""The egress gate (US-47, ADR-0005): every payload the bench sends to a judge passes `check` first.

In-process and offline: it reads a string and returns a `Verdict`. It opens no connection and starts
no process. The gateway (row 17, `harness_bench.gateway`) calls it and hands the payload on only
through `Verdict.release`, which never calls the backend for a withheld payload.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import TypeVar

from harness_bench.report import html as report_html
from harness_bench.report.credentials import encodings

WITHHELD = "withheld: sensitive content"
DESTINATION = re.compile(r"[a-z][a-z0-9._-]{0,31}(?::[a-z0-9._-]{1,31})?")
CLASSES = ("credential", "token_shape", "email", "username", "home_path", "canary")

T = TypeVar("T")


@dataclass(frozen=True)
class Verdict:
    """The result of one scan. A hit names only its classes, never the matched value."""

    destination: str
    payload_sha256: str
    classes: tuple[str, ...]
    payload: str | None = field(repr=False)
    scanned: tuple[str, ...] = ()

    def record(self) -> dict:
        """The ledger shape: the destination id, the digest and the class names; never the payload."""
        return {"destination": self.destination, "payload_sha256": self.payload_sha256, "classes": self.classes,
                "scanned": self.scanned}

    @property
    def withheld(self) -> bool:
        return bool(self.classes)

    @property
    def reason(self) -> str | None:
        return WITHHELD if self.withheld else None

    def release(self, backend: Callable[[str], T]) -> T | None:
        """Hand the payload to `backend` when it is clean; a withheld payload never reaches it."""
        if self.withheld or self.payload is None:
            return None
        return backend(self.payload)


def _exact(payload: str, values: Sequence[str]) -> bool:
    """Any non-empty value, or its base64 or URL-encoded form (report.credentials.encodings), in the payload."""
    return any(v in payload for v in encodings({v for v in values if v.strip()}))


def _anycase(payload: str, value: str | None) -> bool:
    """A non-empty value anywhere in the payload, ignoring case (an email's domain is case-insensitive)."""
    return bool(value and value.strip()) and value.casefold() in payload.casefold()


def _word(payload: str, value: str | None) -> bool:
    """A non-empty value as a whole word (no letter or digit on either side), ignoring case."""
    if not (value and value.strip()):
        return False
    return re.search(rf"(?<![^\W_]){re.escape(value)}(?![^\W_])", payload, re.IGNORECASE) is not None


def _path_form(text: str) -> str:
    """Casefolded, with every run of slashes or backslashes as one "/" (so JSON-escaped paths match too)."""
    return re.sub(r"[\\/]+", "/", text.casefold())


def _path(payload: str, value: str | None) -> bool:
    """A non-empty path anywhere in the payload, in any separator form or case."""
    return bool(value and value.strip()) and _path_form(value) in _path_form(payload)


@dataclass(frozen=True)
class Operator:
    """The operator's identifiers, supplied at run time and never committed (the origin repo is public, R-42)."""

    email: str = field(repr=False)
    username: str = field(repr=False)
    home: str = field(repr=False)

    def __post_init__(self) -> None:
        # An empty identifier would be "not scanned" while the verdict reads "clean" (D&P, R-60 c4).
        if not all(v.strip() for v in (self.email, self.username, self.home)):
            raise ValueError("Operator: email, username and home are all required and non-empty")


def check(payload: str, *, destination: str, operator: Operator, secrets: Sequence[str] = (),
          canaries: Sequence[str] = (), token_prefixes: Sequence[str] = ()) -> Verdict:
    """Scan `payload` bound for `destination`.

    Every value is supplied by the caller at run time and is never stored or returned: `secrets` are the
    credential values the host holds; `operator` identifies the operator; `canaries` are the planted
    US-13/US-48 markers. A hit returns a withheld verdict: no payload, only its sha256, the destination and
    the class names.
    """
    def hits(text: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
        scans = {
            "credential": (lambda: _exact(text, secrets)) if secrets else None,
            "token_shape": lambda: report_html.scan(text) > 0,  # the report's shape scan (HB-SEC-001), shapes only
            "email": lambda: _anycase(text, operator.email),
            "username": lambda: _word(text, operator.username),
            "home_path": lambda: _path(text, operator.home),
            "canary": (lambda: _exact(text, canaries)) if canaries else None,
        }
        scanned = tuple(name for name in CLASSES if scans.get(name))
        return tuple(name for name in scanned if scans[name]()), scanned

    # The destination is a fixed backend id (Codex F3): it must not be able to carry content into a record.
    if not DESTINATION.fullmatch(destination) or hits(destination)[0]:
        raise ValueError("destination is not a safe backend id (lower-case name[:qualifier], at most 64 characters)")
    classes, scanned = hits(payload)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return Verdict(destination=destination, payload_sha256=digest, classes=classes,
                   payload=None if classes else payload, scanned=scanned)
