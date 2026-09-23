#!/usr/bin/env python3
"""verify-no-machine-paths.py - a tracked, machine-readable file never carries one machine's paths.

WHY THIS EXISTS (PLAT-B, docs/lessons/defect-classes.md). `coord classify init` wrote
`sys.executable` - `C:\\Users\\<user>\\...\\python.exe` - into the TRACKED registry
`.agents/artifacts.yml`. The file was correct on the machine that wrote it and the tool
reported success; `coord regen` then failed on macOS days later with "command not found",
while `pack-doctor` passed because it checked that the registry parsed, never that its
commands resolve here. A home directory, a drive letter or an interpreter path inside a file
git carries is state about ONE machine masquerading as configuration for all of them.

WHAT IT SCANS. Tracked files (`git ls-files`) under the machine-readable surfaces: pack/,
tools/, tests/, web/, .claude/, .github/, .grok/, .agents/ and the repo-root dotfiles and
manifests. Prose under docs/ is out of scope on purpose - investigations and defect classes
cite offending paths as evidence, and a lint that forbids naming the defect is a lint that
forbids fixing it.

WHAT IT REFUSES. Any line matching a machine-path shape (each line below carries the
opt-out marker because it names the shapes; the marker is `machine-path-ok`):
  <drive>:\\Users\\   <drive>:/Users/   /Users/<name>   /home/<name>   /opt/homebrew/   machine-path-ok
  \\.pyenv/           AppData\\Local     AppData/Local                                machine-path-ok
A line may opt out with the marker `machine-path-ok` when the path is a fixture and the
test says why (the exemption is visible in the diff; the pattern is not silently widened).

USAGE
  python3 verify-no-machine-paths.py               scan the tracked surfaces of this repo
  python3 verify-no-machine-paths.py --root <repo>  scan that repository
  python3 verify-no-machine-paths.py --self-test    prove the gate can fail (DC-104)

EXIT  0 clean  ·  1 a machine path was found  ·  2 usage / git unavailable
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile

# Windows consoles default to cp1252, which cannot encode the box/arrow glyphs this tool
# prints - `prompt-log.py --help` crashed outright with UnicodeEncodeError (FR-047). The guard
# is applied uniformly (class PLAT-A): a script that survives only because its glyphs happen
# to exist in cp1252 is luck, not an invariant.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass

SURFACES = ("pack/", "tools/", "tests/", "web/", ".claude/", ".github/", ".grok/", ".agents/")
ROOT_FILES = (".gitattributes", ".gitignore", ".editorconfig", "package.json", "AGENTS.md",
              "CLAUDE.md", "global.json")
PATTERNS = [
    re.compile(r"[A-Za-z]:[\\/]Users[\\/]"),
    re.compile(r"(^|[^A-Za-z0-9_])/Users/[A-Za-z]"),
    re.compile(r"(^|[^A-Za-z0-9_])/home/[a-z]"),
    re.compile(r"/opt/homebrew/"),   # machine-path-ok: the pattern itself
    re.compile(r"\.pyenv[\\/]"),
    re.compile(r"AppData[\\/]Local"),
]
OPT_OUT = "machine-path-ok"
TEXT_SUFFIXES = {".py", ".ps1", ".sh", ".json", ".jsonl", ".yml", ".yaml", ".md", ".js", ".html",
                 ".css", ".txt", ".toml", ".cfg", ".ini", ""}


def tracked_files(root: str) -> list[str] | None:
    try:
        proc = subprocess.run(["git", "-C", root, "ls-files", "-z"], capture_output=True,
                              timeout=60, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return [p for p in proc.stdout.decode("utf-8", "replace").split("\0") if p]


def in_scope(rel: str) -> bool:
    if rel in ROOT_FILES:
        return True
    if any(rel.startswith(prefix) for prefix in SURFACES):
        ext = os.path.splitext(rel)[1].lower()
        return ext in TEXT_SUFFIXES
    return False


def scan(root: str) -> tuple[list[str], int]:
    files = tracked_files(root)
    if files is None:
        return ["NOT CHECKED: git ls-files failed under {0}".format(root)], -1
    hits, scanned = [], 0
    for rel in files:
        if not in_scope(rel):
            continue
        path = os.path.join(root, rel)
        try:
            with open(path, "rb") as handle:
                raw = handle.read()
        except OSError:
            continue
        if b"\0" in raw[:4096]:
            continue
        scanned += 1
        for lineno, line in enumerate(raw.decode("utf-8", "replace").splitlines(), 1):
            if OPT_OUT in line:
                continue
            if any(rx.search(line) for rx in PATTERNS):
                hits.append("{0}:{1}: {2}".format(rel, lineno, line.strip()[:120]))
    return hits, scanned


def self_test() -> int:
    """The gate must be able to fail: a fixture with a Windows home path is refused, a clean
    fixture is accepted, and an opted-out line is skipped. Exit 0 only if all three hold."""
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["git", "init", "-q", tmp], check=True)
        os.makedirs(os.path.join(tmp, ".agents"))
        bad = os.path.join(tmp, ".agents", "artifacts.yml")
        with open(bad, "w", encoding="utf-8", newline="\n") as handle:
            handle.write('a: derived "C:\\Users\\x\\AppData\\Local\\Programs\\Python\\python.exe" a.py\n')
            handle.write("b: derived python3 b.py\n")
            handle.write("c: derived /Users/x/bin/tool c.py  # fixture, machine-path-ok\n")
        subprocess.run(["git", "-C", tmp, "add", "-A"], check=True)
        hits, _ = scan(tmp)
        if len(hits) != 1 or "artifacts.yml:1" not in hits[0]:
            print("self-test FAILED: expected exactly line 1 refused, got {0!r}".format(hits))
            return 1
        with open(bad, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("b: derived python3 b.py\n")
        hits, _ = scan(tmp)
        if hits:
            print("self-test FAILED: clean fixture refused: {0!r}".format(hits))
            return 1
    print("self-test OK: a machine path is refused, a portable token passes, an opt-out is honoured")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=os.getcwd())
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)
    if args.self_test:
        return self_test()
    hits, scanned = scan(os.path.abspath(args.root))
    if scanned < 0:
        print(hits[0])
        return 2
    if hits:
        print("machine-specific paths in tracked, machine-readable files ({0}):".format(len(hits)))
        for hit in hits:
            print("  " + hit)
        print("fix: carry the portable token (`python3`, `~`, a repo-relative path) and resolve it at")
        print("     run time; for the registry run `coord classify init --force`. A test fixture may")
        print("     opt out with `machine-path-ok` on the line, with the reason beside it.")
        return 1
    print("clean - {0} tracked machine-readable files carry no machine-specific path".format(scanned))
    return 0


if __name__ == "__main__":
    sys.exit(main())
