"""A task's annotated clarifications (`oracle/clarifications.yaml`, schema bench-clarifications/1) and the responder.

Red stub: the behaviour lands in the next commit.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from harness_bench.scripted_user.matcher import MatchResult

SCHEMA = "bench-clarifications/1"
DEFAULT_REPLY = "Decide and state your assumption."


@dataclass(frozen=True)
class Clarification:
    id: str
    type: str
    deleted_information: str
    question: str
    reply: str


@dataclass(frozen=True)
class ClarificationSet:
    sha256: str
    task: str | None
    default_reply: str
    clarifications: tuple[Clarification, ...]

    def reply_for(self, result: MatchResult) -> str:
        return ""


def parse(data: bytes, where: str) -> ClarificationSet:
    return ClarificationSet("", None, "", ())


def load(path: Path) -> ClarificationSet:
    return parse(Path(path).read_bytes(), str(path))
