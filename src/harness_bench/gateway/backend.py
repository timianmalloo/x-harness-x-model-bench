"""The `Backend` protocol and slice 1's only backend, a replay fake (design section 16, directive D7).

A backend takes the released request text and returns the judge CLI's stdout as the CLI printed it. It never returns
parsed facts: the gateway's reader (`read_reply`) decides what the stdout says. A backend that cannot answer raises
`BackendDown`, which the pipeline records as NOT_RECORDED `HB-GW-001`, never as a score.

`ReplayBackend` replays recorded stdout keyed by the request's sha256. It opens no process, socket or listener.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Protocol


class BackendDown(Exception):
    """The backend could not answer: CLI error, timeout, provider error, or no recorded reply."""


@dataclass(frozen=True)
class Reply:
    stdout: str  # the judge CLI's stdout, verbatim


class Backend(Protocol):
    def judge(self, request: str) -> Reply: ...


class ReplayBackend:
    """Replays recorded stdout for each request it was given a record of; counts every call it receives."""

    def __init__(self, replies: dict[str, str], down: bool = False) -> None:
        self.replies = dict(replies)  # request sha256 -> recorded stdout
        self.down = down
        self.received: list[str] = []

    def judge(self, request: str) -> Reply:
        self.received.append(request)
        digest = hashlib.sha256(request.encode("utf-8")).hexdigest()
        if self.down or digest not in self.replies:
            raise BackendDown("no recorded reply for this request")
        return Reply(self.replies[digest])


def read_reply(stdout: str) -> tuple[str, tuple[str, ...], str] | None:
    """(final text, served model ids, native session id) from a Claude `--output-format json` stdout, or None.

    simplify: the slice-1 reader reads stdout only; slice 2 reads the native record (served model, tool events) and
    replaces this. Upgrade trigger: s2's record readers land.
    """
    try:
        out = json.loads(stdout)
    except ValueError:
        return None
    if not isinstance(out, dict):
        return None
    text, models, session = out.get("result"), out.get("modelUsage"), out.get("session_id")
    if not isinstance(text, str) or not isinstance(models, dict) or not models or not isinstance(session, str):
        return None
    return text, tuple(sorted(models)), session
