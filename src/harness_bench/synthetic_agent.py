"""The synthetic ACP agent and the one overlay path rule (W1-E sections 5 and 6; grade class, stdlib only).

Run as `<python> synthetic_agent.py` it speaks the minimum ACP the driver needs (initialize, session/new, session/prompt),
applies the role's overlay (`HB_SYNTH_OVERLAY`) to its cwd, which the engine sets to the cell's working copy, and ends the
turn. Importable as `harness_bench.synthetic_agent`: `safe_relpath` and `overlay_files` are the one definition of the
overlay path rule, called by readiness (HB-RDY-005), by variant edits and by the agent itself. The agent cannot import
`harness_bench` helpers when run as a script, so the rule lives here and nowhere else.

The overlay is copied inside the cell, never beforehand: the tree the grader sees is the one the engine built plus the
overlay. No file is deleted or renamed (assume: no E1 task needs a deletion; confirm: S1's and S2's overlays hold only
replacements; breaks if false: a stale file the check sees).
"""

import json
import os
import shutil
import stat
import sys
import unicodedata
import uuid
from pathlib import Path, PurePosixPath

SYNTHETIC_VERSION = "synthetic-agent/1"
MAX_FILES = 2000  # simplify: constants; upgrade trigger: a legitimate solution above them
MAX_BYTES = 8 * 1024 * 1024
_REPARSE = 0x400  # FILE_ATTRIBUTE_REPARSE_POINT
_DEVICES = frozenset({"con", "prn", "aux", "nul", "conin$", "conout$", *(f"com{i}" for i in range(10)),
                      *(f"lpt{i}" for i in range(10)), "com¹", "com²", "com³", "lpt¹", "lpt²", "lpt³"})
_BAD_CHARS = frozenset('<>"|?*')


class OverlayError(ValueError):
    """A path or tree the overlay rule refuses; the message names the rule."""


def _component(rel: str, part: str) -> None:
    if part in ("", ".", ".."):
        raise OverlayError(f"{rel!r}: an empty, '.' or '..' segment")
    if ":" in part or part.endswith((".", " ")):
        raise OverlayError(f"{rel!r}: {part!r} contains ':' or ends in '.' or a space")
    if _BAD_CHARS & set(part) or any(ord(c) < 32 for c in part):
        raise OverlayError(f"{rel!r}: {part!r} holds a character Windows refuses in a name")
    if part.split(".")[0].rstrip(" ").casefold() in _DEVICES:
        raise OverlayError(f"{rel!r}: {part!r} has a Windows device name as its stem")


def safe_relpath(rel: str) -> PurePosixPath:
    """One overlay-relative path as a safe `PurePosixPath`, or OverlayError naming the rule broken: absolute, drive or
    UNC prefix, `..` or empty segment, a first segment `.git`, ':' (an NTFS stream), a trailing dot or space, a device
    name as a stem (with or without an extension)."""
    if not isinstance(rel, str) or not rel:
        raise OverlayError(f"{rel!r}: empty path")
    if rel.startswith(("/", "\\")) or "\\" in rel or (len(rel) > 1 and rel[1] == ":"):
        raise OverlayError(f"{rel!r}: absolute, rooted or backslash path")
    parts = rel.split("/")
    for part in parts:
        _component(rel, part)
    if parts[0].casefold() == ".git":
        raise OverlayError(f"{rel!r}: a path under .git")
    return PurePosixPath(rel)


def _is_link(st: os.stat_result) -> bool:
    return stat.S_ISLNK(st.st_mode) or bool(getattr(st, "st_file_attributes", 0) & _REPARSE)


def overlay_files(root: Path) -> list[Path]:
    """The overlay's regular files as sorted paths relative to `root`, or OverlayError. Scans with `os.scandir` and never
    follows a link; refuses a symlink, junction or other reparse point, a non-regular file, two paths equal after NFC
    case-fold, more than MAX_FILES files or MAX_BYTES bytes, and every name `safe_relpath` refuses."""
    found: list[str] = []
    seen: dict[str, str] = {}
    total = 0
    stack = [(root, "")]
    while stack:
        folder, prefix = stack.pop()
        with os.scandir(folder) as entries:
            for entry in entries:
                rel = f"{prefix}{entry.name}"
                st = entry.stat(follow_symlinks=False)
                if _is_link(st):
                    raise OverlayError(f"{rel!r}: a link or reparse point")
                if stat.S_ISDIR(st.st_mode):
                    stack.append((Path(entry.path), rel + "/"))
                    continue
                if not stat.S_ISREG(st.st_mode):
                    raise OverlayError(f"{rel!r}: not a regular file")
                safe_relpath(rel)
                folded = unicodedata.normalize("NFC", rel).casefold()
                if folded in seen:
                    raise OverlayError(f"{rel!r} and {seen[folded]!r} are equal after NFC case-fold")
                seen[folded] = rel
                total += st.st_size
                found.append(rel)
                if len(found) > MAX_FILES:
                    raise OverlayError(f"more than {MAX_FILES} files")
                if total > MAX_BYTES:
                    raise OverlayError(f"more than {MAX_BYTES} bytes")
    return sorted(Path(rel) for rel in found)


def _check_destination(cwd: Path, rel: Path) -> None:
    """Refuse a link, reparse point or non-regular file already in the working copy on the way to `rel` (SEC 3)."""
    here = cwd
    for part in rel.parts[:-1]:
        here = here / part
        try:
            st = os.lstat(here)
        except FileNotFoundError:
            return
        if _is_link(st) or not stat.S_ISDIR(st.st_mode):
            raise OverlayError(f"{rel.as_posix()!r}: {part!r} is a link or not a folder in the working copy")
    dest = cwd / rel
    try:
        st = os.lstat(dest)
    except FileNotFoundError:
        return
    if _is_link(st) or not stat.S_ISREG(st.st_mode):
        raise OverlayError(f"{rel.as_posix()!r}: the destination is a link or not a regular file in the working copy")


def apply_overlay(overlay: Path, cwd: Path) -> list[str]:
    """Copy every overlay file to the same relative path under `cwd`; return the relative POSIX paths written. Every path
    and destination is checked before the first copy, so a refusal writes nothing."""
    files = overlay_files(overlay)
    for rel in files:
        _check_destination(cwd, rel)
    for rel in files:
        dest = cwd / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(overlay / rel, dest)
    return [rel.as_posix() for rel in files]


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
            try:
                apply_overlay(Path(os.environ["HB_SYNTH_OVERLAY"]), Path.cwd())
            except (OverlayError, OSError, KeyError) as exc:
                sys.stderr.write(f"synthetic agent refused the overlay: {exc!r}\n")
                return 2
            _send({"jsonrpc": "2.0", "id": mid, "result": {"stopReason": "end_turn"}})
        elif mid is not None:
            _send({"jsonrpc": "2.0", "id": mid, "result": {}})
    return 0


if __name__ == "__main__":
    sys.exit(main())
