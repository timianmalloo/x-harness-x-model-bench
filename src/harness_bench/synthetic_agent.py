"""The synthetic ACP agent and the one overlay path rule (W1-E sections 5 and 6; grade class, stdlib only).

Run as `<python> synthetic_agent.py` it speaks the minimum ACP the driver needs (initialize, session/new, session/prompt),
applies the role's overlay (`HB_SYNTH_OVERLAY`) to its cwd, which the engine sets to the cell's working copy, and ends the
turn. Importable as `harness_bench.synthetic_agent`: `safe_relpath` and `overlay_files` are the one definition of the
overlay path rule, called by readiness (HB-RDY-005), by variant edits and by the agent itself.

Skeleton (E0): the rule accepts everything and the agent copies nothing; the E1 commit builds both.
"""

import json
import sys
import uuid
from pathlib import Path, PurePosixPath

SYNTHETIC_VERSION = "synthetic-agent/1"
MAX_FILES = 2000  # simplify: constants; upgrade trigger: a legitimate solution above them
MAX_BYTES = 8 * 1024 * 1024


class OverlayError(ValueError):
    """A path or tree the overlay rule refuses; the message names the rule."""


def safe_relpath(rel: str) -> PurePosixPath:
    """One overlay-relative path as a safe `PurePosixPath`, or OverlayError naming the rule broken."""
    return PurePosixPath(rel)


def overlay_files(root: Path) -> list[Path]:
    """The overlay's regular files as sorted paths relative to `root`, or OverlayError. Never follows a link."""
    return sorted(p.relative_to(root) for p in root.rglob("*") if p.is_file())


def apply_overlay(overlay: Path, cwd: Path) -> list[str]:
    """Copy every overlay file to the same relative path under `cwd`; return the relative POSIX paths written."""
    return []


def _send(obj: dict) -> None:
    sys.stdout.buffer.write(json.dumps(obj).encode() + b"\n")
    sys.stdout.buffer.flush()


def main() -> int:
    session_id = str(uuid.uuid4())
    for raw in sys.stdin.buffer:
        msg = json.loads(raw)
        method, mid = msg.get("method"), msg.get("id")
        if method == "initialize":
            _send({"jsonrpc": "2.0", "id": mid, "result": {"protocolVersion": 1, "agentCapabilities": {},
                                                           "agentInfo": {"name": "synthetic", "version": SYNTHETIC_VERSION}}})
        elif method == "session/new":
            _send({"jsonrpc": "2.0", "id": mid, "result": {"sessionId": session_id}})
        elif method == "session/prompt":
            _send({"jsonrpc": "2.0", "id": mid, "result": {"stopReason": "end_turn"}})
        elif mid is not None:
            _send({"jsonrpc": "2.0", "id": mid, "result": {}})
    return 0


if __name__ == "__main__":
    sys.exit(main())
