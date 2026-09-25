"""Copy spike GW-H's Claude records into `records/` with every identifier replaced by a fixed placeholder (design
phase3-gateway-judges section 16, slice 2; the contract tests replay these files).

The Leader's probe turns left their raw files under `<cells root>/gw-probe/<label>/` (never committed). This script
reads, per turn, the one native record (`home/projects/**/<session>.jsonl`) and `stdout.txt`, and writes
`records/<name>.record.jsonl` and `records/<name>.stdout.json`. Every string in every row is rewritten:
- e-mail addresses -> `operator@example.invalid`;
- UUIDs -> `00000000-0000-4000-8000-<n>` in order of first appearance (one map per turn, so the record's and
  stdout's session ids stay equal);
- vendor message, request and tool-use ids (`msg_`, `req_`, `toolu_`, `srvtoolu_`) -> `<prefix>placeholder<n>`;
- the probe's nonce -> `0badc0de`; absolute Windows paths and the CLI's project-folder slug -> fixed placeholders.

It then fails (exit 1, the class named, never the value) if any real value remains: the operator's user name, home
path, host name and git e-mail and name (read here at run time, never written), any other e-mail, UUID or vendor id,
the nonce, the turn's label, or the probe folder. Nothing is written unless every file passes.

Usage (from the repository root): python tests/fixtures/gateway/copy_records.py --source <cells root>/gw-probe
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "records"
TURNS = {"claude-fable-text": "claude-code-claude-fable-5-1-text-", "claude-fable-native": "claude-code-claude-fable-5-1-native-",
         "claude-opus-text": "claude-code-claude-opus-5-5-text-"}
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
VENDOR_ID = re.compile(r"\b(msg|req|toolu|srvtoolu)_[A-Za-z0-9]{6,}")
WIN_PATH = re.compile(r"[A-Za-z]:[\\/][^\s\"'<>|]*")
PLACEHOLDER_EMAIL = "operator@example.invalid"
PLACEHOLDER_NONCE = "0badc0de"
PLACEHOLDER_PATH = "C:\\cells\\gateway\\g0\\c0\\work"
PLACEHOLDER_SLUG = "C--cells-gateway-g0-c0-work"


class Scrubber:
    def __init__(self, nonce: str, slug: str) -> None:
        self.nonce, self.slug = nonce, slug
        self.uuids: dict[str, str] = {}
        self.vendor: dict[str, str] = {}

    def _uuid(self, m: re.Match) -> str:
        return self.uuids.setdefault(m.group(0).lower(), f"00000000-0000-4000-8000-{len(self.uuids) + 1:012d}")

    def _vendor(self, m: re.Match) -> str:
        return self.vendor.setdefault(m.group(0), f"{m.group(1)}_placeholder{len(self.vendor) + 1}")

    def text(self, s: str) -> str:
        s = s.replace(self.slug, PLACEHOLDER_SLUG).replace(self.nonce, PLACEHOLDER_NONCE)
        s = WIN_PATH.sub(lambda m: PLACEHOLDER_PATH, s)
        s = EMAIL.sub(PLACEHOLDER_EMAIL, s)
        s = UUID.sub(self._uuid, s)
        return VENDOR_ID.sub(self._vendor, s)

    def value(self, v):
        if isinstance(v, str):
            return self.text(v)
        if isinstance(v, list):
            return [self.value(x) for x in v]
        if isinstance(v, dict):
            return {self.text(k): self.value(x) for k, x in v.items()}
        return v


def real_values() -> dict[str, str]:
    """class -> value, read at run time; matched, never written or printed."""
    home = Path(os.environ.get("USERPROFILE") or Path.home())
    found = {"user name": os.environ.get("USERNAME", ""), "home path": str(home), "home path (forward)": home.as_posix(),
             "host name": socket.gethostname()}
    git = shutil.which("git")
    for key, name in (("user.email", "git e-mail"), ("user.name", "git name")):
        if git:
            done = subprocess.run([git, "config", "--get", key], capture_output=True, text=True, check=False)
            found[name] = done.stdout.strip()
    return {k: v for k, v in found.items() if len(v) >= 3}


def strings(v) -> list[str]:
    """Every decoded string (keys too) of a parsed JSON value: the check reads values, not their JSON escapes."""
    if isinstance(v, str):
        return [v]
    if isinstance(v, list):
        return [s for x in v for s in strings(x)]
    if isinstance(v, dict):
        return [s for k, x in v.items() for s in (k, *strings(x))]
    return []


def leftovers(text: str, turn_values: dict[str, str]) -> list[str]:
    """The classes of real value still in `text`, the decoded strings of one file (names only)."""
    folded = text.casefold()
    out = [name for name, v in turn_values.items() if v.casefold() in folded]
    if any(e != PLACEHOLDER_EMAIL for e in EMAIL.findall(text)):
        out.append("an e-mail address")
    if any(not u.startswith("00000000-0000-4000-8000-") for u in UUID.findall(text)):
        out.append("a UUID")
    if any("placeholder" not in m.group(0) for m in VENDOR_ID.finditer(text)):
        out.append("a vendor id")
    if any(p != PLACEHOLDER_PATH for p in WIN_PATH.findall(text)):
        out.append("a path")
    return out


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--source", required=True, help="the probe's out root, <cells root>/gw-probe")
    source = Path(p.parse_args(argv).source)
    values = real_values()
    written: dict[Path, str] = {}
    failures = []
    for name, prefix in TURNS.items():
        folder = next(d for d in sorted(source.iterdir()) if d.name.startswith(prefix))
        summary = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
        records = sorted((folder / "home" / "projects").rglob("*.jsonl"))
        if len(records) != 1:
            failures.append(f"{name}: {len(records)} native records, expected 1")
            continue
        slug = re.sub(r"[^A-Za-z0-9]", "-", str(folder / "work"))
        s = Scrubber(summary["nonce"], slug)
        rows = [json.dumps(s.value(json.loads(line)), ensure_ascii=False)
                for line in records[0].read_text(encoding="utf-8").splitlines() if line.strip()]
        stdout = json.dumps(s.value(json.loads((folder / "stdout.txt").read_text(encoding="utf-8"))), ensure_ascii=False)
        turn_values = values | {"nonce": summary["nonce"], "label": folder.name, "probe folder": str(folder),
                                "probe folder (forward)": folder.as_posix(), "cells root": "bench-cells"}
        for suffix, text in ((".record.jsonl", "\n".join(rows) + "\n"), (".stdout.json", stdout + "\n")):
            bad = leftovers("\n".join(s for line in text.splitlines() for s in strings(json.loads(line))), turn_values)
            if bad:
                failures.append(f"{name}{suffix}: a real value remains: {sorted(set(bad))}")
            written[OUT / f"{name}{suffix}"] = text
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    OUT.mkdir(exist_ok=True)
    for path, text in written.items():
        path.write_text(text, encoding="utf-8", newline="\n")
    print(f"{len(written)} file(s) -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
