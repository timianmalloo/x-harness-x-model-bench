"""A task's annotated clarifications (`oracle/clarifications.yaml`, schema bench-clarifications/1) and the responder.

The schema is defined in tasks/A1/oracle/README.md: `default_reply`; `clarifications[]` with `id`, `type`,
`deleted_information`, `question`, `reply`. The set's identity is the sha256 of the file's bytes (design section 3).
Loading fails closed (design section 6): a malformed file, a default reply other than R-37's exact text, a repeated
id, a question empty after `normalise`, or two questions that normalise to the same text are refused with a code.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import yaml

from harness_bench.errors import BenchError
from harness_bench.scripted_user.matcher import MatchResult, normalise

SCHEMA = "bench-clarifications/1"
DEFAULT_REPLY = "Decide and state your assumption."
FIELDS = ("id", "type", "deleted_information", "question", "reply")


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
        """The responder (design section 6): the matched clarification's reply verbatim, else the default verbatim."""
        if result.clarification is None:
            return self.default_reply
        return next(c.reply for c in self.clarifications if c.id == result.clarification)


def parse(data: bytes, where: str) -> ClarificationSet:
    def refuse(reason: str) -> BenchError:
        return BenchError("HB-USR-002", f"{where}: {reason}")

    try:
        doc = yaml.safe_load(data.decode("utf-8"))
    except (UnicodeDecodeError, yaml.YAMLError):
        raise refuse("not UTF-8 YAML") from None
    if not isinstance(doc, dict):
        raise refuse("expected a mapping at the top level")
    if doc.get("schema") != SCHEMA:
        raise refuse(f"schema must be {SCHEMA!r}")
    if doc.get("default_reply") != DEFAULT_REPLY:
        raise refuse(f"default_reply must be exactly {DEFAULT_REPLY!r} (R-37)")
    task = doc.get("task")
    if task is not None and not isinstance(task, str):
        raise refuse("task must be a string")
    items = doc.get("clarifications")
    if not isinstance(items, list) or not items:
        raise refuse("clarifications must be a non-empty list")
    out: list[Clarification] = []
    seen: dict[str, int] = {}
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            raise refuse(f"clarifications[{i}] must be a mapping")
        for field in FIELDS:
            if not isinstance(item.get(field), str) or item[field] == "":
                raise refuse(f"clarifications[{i}].{field} must be a non-empty string")
        c = Clarification(*(item[field] for field in FIELDS))
        if any(c.id == earlier.id for earlier in out):
            raise refuse(f"clarifications[{i}].id {c.id!r} repeats an earlier id")
        key = normalise(c.question)
        if key == "":
            raise refuse(f"clarifications[{i}].question is empty after normalise")
        if key in seen:
            raise refuse(f"clarifications[{i}].question normalises to the same text as clarifications[{seen[key]}]: ambiguous")
        seen[key] = i
        out.append(c)
    return ClarificationSet(hashlib.sha256(data).hexdigest(), task, DEFAULT_REPLY, tuple(out))


def load(path: Path) -> ClarificationSet:
    """Read, hash and validate one clarification set. Raises BenchError HB-USR-002 on any defect."""
    return parse(Path(path).read_bytes(), str(path))
