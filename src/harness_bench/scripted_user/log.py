"""The scripted-user log (design section 8), schema bench-scripted-user-log/1.

Red stub: the behaviour lands in the next commit.
"""

from __future__ import annotations

import time
from pathlib import Path

SCHEMA = "bench-scripted-user-log/1"
LOG_ENV = "SCRIPTED_USER_LOG"


class LogWriter:
    def __init__(self, path: Path, clock=time.monotonic) -> None:
        self.path = Path(path)

    def header(self, cset, log_source: str) -> dict:
        return {}

    def refused(self, code: str, message: str) -> dict:
        return {}

    def initialize(self, client, protocol_version: str, requested) -> dict:
        return {}

    def tools_listed(self) -> dict:
        return {}

    def call(self, question, result, reply: str, cset) -> dict:
        return {}


def read_rows(text: str) -> tuple[list[dict], bool]:
    return [], False


def end_row(rows: list[dict], torn_tail: bool) -> dict:
    return {}


def close_log(path: Path, header: dict) -> dict:
    return {}


def stored_decisions(rows: list[dict]) -> dict:
    return {}


def decide(question, cset, store: dict) -> dict:
    return {}
