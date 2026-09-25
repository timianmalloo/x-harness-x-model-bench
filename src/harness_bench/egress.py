"""The egress gate (US-47, ADR-0005): every payload the bench sends to a judge passes `check` first.

In-process and offline: it reads a string and returns a `Verdict`. It opens no connection and starts
no process. The gateway (row 17, `harness_bench.gateway`) calls it and hands the payload on only
through `Verdict.release`, which never calls the backend for a withheld payload.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TypeVar

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
        return backend(self.payload)


def check(payload: str, *, destination: str, secrets: Sequence[str] = ()) -> Verdict:
    """Scan `payload` bound for `destination`."""
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return Verdict(destination, digest, (), payload)
