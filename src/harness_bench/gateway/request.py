"""The judge request, `judge-request/1` (design sections 7.1 and 7.2)."""

from __future__ import annotations

from dataclasses import dataclass

TEMPLATE_VERSION = "judge-request/1"
BOUND = 65_536


@dataclass(frozen=True)
class Rendered:
    text: str
    nonce: str
    artifact_sha256: str
    escaped: tuple[str, ...]


def bound_problem(artifacts: tuple[tuple[str, bytes], ...]) -> str | None:
    return None


def render(preamble: str, rubric: str, items: int, artifacts: tuple[tuple[str, bytes], ...],
           entries: tuple[str, ...]) -> Rendered:
    return Rendered("", "", "", ())
