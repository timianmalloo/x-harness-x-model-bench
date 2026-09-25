"""The scripted user's matcher (design phase2-scripted-user section 7, ruling R-39): exact, then normalised, then none.

There is no partial, token-overlap or edit-distance rung: nothing fuzzy (R-39 c4). `normalise` reads its parameters
from RULES, the same table MATCHER_VERSION hashes, so the code cannot drift from the version it reports. `match` is
pure and synchronous, so no decision request opens mid-turn (R-37).

The held-out measurement (T-39-1) is owned outside this module's author (R-39 c2); it calls
`match(question, load(path).clarifications)` and reads `.clarification` and `.rung`.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

TIERS = ("exact", "normalised", "none")
RULES = (
    {"id": "N1", "op": "unicode", "form": "NFKC"},
    {"id": "N2", "op": "quotes", "map": {"\u201c": '"', "\u201d": '"', "\u201e": '"', "\u201f": '"',
                                          "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'"}},
    {"id": "N3", "op": "casefold"},
    {"id": "N4", "op": "whitespace", "join": " "},  # strip both ends, collapse every str.split() run
    {"id": "N5", "op": "strip_trailing", "chars": "?.! "},
)
# The hash of {TIERS, RULES, unicodedata.unidata_version} (section 7.3). T-39-3a recomputes it: a changed table, or a
# Python with other Unicode data, is red until this constant is bumped. The server refuses to start on a mismatch.
MATCHER_VERSION = "t0-c8b7e628d0c7"


class Annotated(Protocol):
    id: str
    question: str


@dataclass(frozen=True)
class MatchResult:
    """One match decision. `clarification is None` with rung `none` means the default reply."""
    clarification: str | None
    rung: str
    invalid: str | None = None

    def decision(self) -> dict:
        return {"clarification": self.clarification, "rung": self.rung}


def normalise(text: str) -> str:
    """Apply RULES in order (section 7.2)."""
    for rule in RULES:
        op = rule["op"]
        if op == "unicode":
            text = unicodedata.normalize(rule["form"], text)
        elif op == "quotes":
            text = text.translate(str.maketrans(rule["map"]))
        elif op == "casefold":
            text = text.casefold()
        elif op == "whitespace":
            text = rule["join"].join(text.split())
        elif op == "strip_trailing":
            text = text.rstrip(rule["chars"])
        else:
            raise ValueError(f"unknown normalisation op {op!r}")
    return text


def canonical() -> str:
    """The canonical JSON that MATCHER_VERSION hashes (section 7.3)."""
    return json.dumps({"tiers": list(TIERS), "rules": list(RULES), "unidata_version": unicodedata.unidata_version},
                      sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def compute_matcher_version() -> str:
    return "t0-" + hashlib.sha256(canonical().encode("ascii")).hexdigest()[:12]


def question_sha256(question: object) -> str:
    """sha256 of the question's UTF-8 with surrogatepass, so a lone surrogate cannot crash the hash. A non-string
    (always invalid, always the default reply) is hashed as its JSON text."""
    text = question if isinstance(question, str) else json.dumps(question, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(text.encode("utf-8", "surrogatepass")).hexdigest()


def cache_key(question: object, clarifications_sha256: str, matcher_version: str = MATCHER_VERSION) -> tuple[str, str, str]:
    """The clarification-match key (R-53): the decision is a pure function of exactly these three inputs."""
    return (question_sha256(question), clarifications_sha256, matcher_version)


def invalid_reason(question: object) -> str | None:
    """Why a question cannot be matched (section 6), or None. An invalid question gets the default reply."""
    if not isinstance(question, str):
        return "not a string"
    if question == "":
        return "empty"
    if any("\ud800" <= ch <= "\udfff" for ch in question):
        return "lone surrogate"
    if normalise(question) == "":
        return "empty after normalise"
    return None


def match(question: object, clarifications: Sequence[Annotated]) -> MatchResult:
    """Exact equality with exactly one annotated question, else normalised equality with exactly one, else none."""
    reason = invalid_reason(question)
    if reason is not None:
        return MatchResult(None, "none", reason)
    exact = [c for c in clarifications if c.question == question]
    if len(exact) == 1:
        return MatchResult(exact[0].id, "exact")
    key = normalise(question)
    same = [c for c in clarifications if normalise(c.question) == key]
    if len(same) == 1:
        return MatchResult(same[0].id, "normalised")
    return MatchResult(None, "none")
