"""The scripted user's matcher (design phase2-scripted-user section 7, ruling R-39): exact, then normalised, then none.

Red stub: the behaviour lands in the next commit.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

TIERS = ("exact", "normalised", "none")
RULES = (
    {"id": "N1", "op": "unicode", "form": "NFKC"},
    {"id": "N2", "op": "quotes", "map": {"“": '"', "”": '"', "„": '"', "‟": '"',
                                          "‘": "'", "’": "'", "‚": "'", "‛": "'"}},
    {"id": "N3", "op": "casefold"},
    {"id": "N4", "op": "whitespace", "join": " "},
    {"id": "N5", "op": "strip_trailing", "chars": "?.! "},
)
MATCHER_VERSION = "t0-unset"


class Annotated(Protocol):
    id: str
    question: str


@dataclass(frozen=True)
class MatchResult:
    clarification: str | None
    rung: str
    invalid: str | None = None

    def decision(self) -> dict:
        return {"clarification": self.clarification, "rung": self.rung}


def normalise(text: str) -> str:
    return text


def canonical() -> str:
    return ""


def compute_matcher_version() -> str:
    return MATCHER_VERSION


def question_sha256(question: object) -> str:
    return hashlib.sha256(str(question).encode("utf-8")).hexdigest()


def cache_key(question: object, clarifications_sha256: str, matcher_version: str = MATCHER_VERSION) -> tuple[str, str, str]:
    return ("", clarifications_sha256, matcher_version)


def invalid_reason(question: object) -> str | None:
    return None


def match(question: object, clarifications: Sequence[Annotated]) -> MatchResult:
    return MatchResult(None, "none")
