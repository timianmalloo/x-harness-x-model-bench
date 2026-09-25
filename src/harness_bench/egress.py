"""The egress gate (US-47, ADR-0005): every payload the bench sends to a judge passes `check` first.

In-process and offline: it reads a string and returns a `Verdict`. It opens no connection and starts
no process. The gateway (row 17, `harness_bench.gateway`) calls it and hands the payload on only
through `Verdict.release`, which never calls the backend for a withheld payload.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TypeVar

from harness_bench.report import html as report_html
from harness_bench.report.credentials import encodings

WITHHELD = "withheld: sensitive content"

T = TypeVar("T")


@dataclass(frozen=True)
class Verdict:
    """The result of one scan. A hit names only its classes, never the matched value."""

    destination: str
    payload_sha256: str
    classes: tuple[str, ...]
    payload: str | None

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


def check(payload: str, *, destination: str, secrets: Sequence[str] = (), email: str | None = None,
          username: str | None = None, home: str | None = None, canaries: Sequence[str] = ()) -> Verdict:
    """Scan `payload` bound for `destination`.

    Every value is supplied by the caller at run time and is never stored or returned: `secrets` are the
    credential values the host holds; `email`, `username` and `home` identify the operator (never committed:
    the origin repo is public, R-42); `canaries` are the planted US-13/US-48 markers.
    A hit returns a withheld verdict: no payload, only its sha256, the destination and the class names.
    """
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    classes = tuple(name for name, hit in (
        ("credential", _exact(payload, secrets)),
        ("token_shape", report_html.scan(payload) > 0),  # the report's shape scan (HB-SEC-001), shapes only
        ("email", _anycase(payload, email)),
        ("username", _word(payload, username)),
    ) if hit)
    return Verdict(destination, digest, classes, None if classes else payload)
