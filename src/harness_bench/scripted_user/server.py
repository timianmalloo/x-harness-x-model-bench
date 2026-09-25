"""The scripted user's stdio MCP server (design section 6, R-37, R-51).

Red stub: the behaviour lands in the next commit.
"""

from __future__ import annotations

import sys
from pathlib import Path


class Server:
    def __init__(self, cset, log) -> None:
        self.cset, self.log = cset, log

    def handle(self, msg: dict) -> dict | None:
        return None


def serve(server: Server, stdin, stdout) -> None:
    return None


def entry(clarifications: Path, log: Path, python: str = sys.executable) -> dict:
    return {}


def main(argv: list[str] | None = None, stdin=None, stdout=None) -> int:
    return 0


if __name__ == "__main__":
    sys.exit(main())
