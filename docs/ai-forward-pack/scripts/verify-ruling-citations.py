#!/usr/bin/env python3
"""verify-ruling-citations.py - every ruling cited as authority resolves to exactly one heading that says what it decided.

THE CLASS (absorbed from ai-de's tools/verify-ruling-citations.py, measured 2026-09-11; class ID-A).
Programme decisions were cited by number across that repository and enforced as binding. Eight of
them defined nothing: numbers cited with no note anywhere recording what they said, one of them
cited six times as governing a dependency decision. Two ends of that met on the same day: a number
was cited by a mockup, a review and a mid-task correction BEFORE any ruling of that number had been
made, and the Owner, unable to see it because nothing recorded it, allocated the same number again
for a different decision. THE ABSENCE OF THE REGISTER IS WHAT CAUSED THE COLLISION IN THE REGISTER.
A decision that cannot be read is not a decision; it is a number with a reputation.

WHAT COUNTS. A DEFINITION is a heading `### Ruling NN — …` (or `## Ruling NN — …`) in
docs/notes/rulings.md - the only definition site; `coord decide rule` writes it. A CITATION is
`Ruling NN` (or `Rulings NN`) in PROSE - `.md`, `.html`, `.txt` - anywhere under docs/, pack/,
.agents/log/, .github/, .claude/. A mention inside prose is a citation, never a definition: that
distinction is the whole point, and collapsing it would make the gate agree with any file that talks
about a ruling often enough. Records (`.json`, `.jsonl`) are not scanned: the audit log and the
dreams quote other repositories' prose verbatim, and a quote is not a citation (decision note
note-20260919-owner-review-register-and-scan-scope). docs/ai-forward-pack/ is skipped as the
generated copy of pack/.

THE TWO DEFECTS. (1) A number cited with no heading. (2) A number defined by two headings. There is
no frozen list: nothing predates this control, so the list that "may only shrink" starts empty and
therefore does not exist.

USAGE
  python3 verify-ruling-citations.py                 scan the repository at the cwd
  python3 verify-ruling-citations.py --root <repo>   scan that repository
  python3 verify-ruling-citations.py --self-test     prove both defects fire and a clean tree is quiet (DC-104)

EXIT  0 ok  ·  1 refused (defects listed, one per line)  ·  2 usage (--root is not a directory)
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Set, Tuple

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass

REGISTER = Path("docs") / "notes" / "rulings.md"
ROOTS = ("docs", "pack", os.path.join(".agents", "log"), ".github", ".claude")
SKIP_PARTS = {"ai-forward-pack", "node_modules", ".git", "_site"}
PROSE_SUFFIXES = {".md", ".html", ".txt"}
CITATION = re.compile(r"\bRulings?\s+(\d{1,3})\b")
DEFINITION = re.compile(r"^#{2,3}[ \t]+Ruling[ \t]+(\d{1,3})\b", re.M)


def definitions(root: Path) -> Dict[int, List[int]]:
    """number -> the register line numbers that define it (two lines = the collision)."""
    path = root / REGISTER
    found: Dict[int, List[int]] = {}
    if not path.is_file():
        return found
    text = path.read_text(encoding="utf-8", errors="replace")
    for match in DEFINITION.finditer(text):
        line = text.count("\n", 0, match.start()) + 1
        found.setdefault(int(match.group(1)), []).append(line)
    return found


def citations(root: Path) -> Dict[int, Set[str]]:
    """number -> the prose files (repo-relative, posix) that cite it. The register is scanned
    too: prose in it that names a number is a citation (a heading is the only definition)."""
    found: Dict[int, Set[str]] = {}
    for top in ROOTS:
        base = root / top
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in PROSE_SUFFIXES:
                continue
            if SKIP_PARTS.intersection(path.relative_to(root).parts):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for match in CITATION.finditer(text):
                found.setdefault(int(match.group(1)), set()).add(path.relative_to(root).as_posix())
    return found


def check(root: Path) -> Tuple[List[str], Dict[int, List[int]], Dict[int, Set[str]]]:
    defined = definitions(root)
    cited = citations(root)
    defects: List[str] = []
    for number in sorted(defined):
        lines = defined[number]
        if len(lines) > 1:
            defects.append("Ruling {} is defined twice in {} (lines {}). One number, one decision (class ID-A):"
                           " the register is the allocator, so the second heading is a collision."
                           .format(number, REGISTER.as_posix(), ", ".join(str(n) for n in lines)))
    for number in sorted(cited):
        if number in defined:
            continue
        where = sorted(cited[number])
        defects.append("Ruling {} is cited as authority in {} file(s) and no heading in {} defines it. Cited by: {}."
                       " Anyone can assert what it said and nobody can check."
                       .format(number, len(where), REGISTER.as_posix(), ", ".join(where)))
    return defects, defined, cited


def self_test() -> int:
    """Break a synthetic tree in each direction and require the gate to notice (DC-104): a
    control's first green is evidence about the control, and the control is the part nobody
    re-examines because it is what they just reasoned about."""
    nl = "\n"
    head = "---" + nl + "id: rulings" + nl + "type: doc" + nl + "---" + nl + "# Rulings" + nl
    cases = [
        ("a ruling cited with no heading defining it",
         {"docs/plans/p.md": "We applied Ruling 91 here." + nl}, "no heading"),
        ("the same ruling, defined by a heading in the register",
         {"docs/plans/p.md": "We applied Ruling 91 here." + nl,
          REGISTER.as_posix(): head + "### Ruling 91 — the thing" + nl + "It decided the thing." + nl}, None),
        ("a number defined by two headings",
         {REGISTER.as_posix(): head + "### Ruling 91 — one" + nl + "## Ruling 91 — again" + nl}, "defined twice"),
        ("a definition that is only prose, not a heading",
         {REGISTER.as_posix(): head + "Ruling 91 decided the thing, at length, repeatedly." + nl}, "no heading"),
        ("a heading outside the register does not define",
         {"docs/notes/other.md": "### Ruling 91 — elsewhere" + nl}, "no heading"),
        ("a record is a quote, not a citation",
         {"docs/audit/audit-log.jsonl": '{"prompt": "ai-de cited Ruling 91"}' + nl}, None),
    ]
    failures = []
    for name, files, expected in cases:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel, body in files.items():
                target = root / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                with open(target, "w", encoding="utf-8", newline="\n") as fh:
                    fh.write(body)
            found, _, _ = check(root)
            if expected is None:
                if found:
                    failures.append("{}: expected clean, got {}".format(name, found))
            elif not any(expected in d for d in found):
                failures.append("{}: expected a defect containing {!r}, got {}".format(name, expected, found))
    if failures:
        print("self-test FAILED: {} case(s).".format(len(failures)))
        for failure in failures:
            print("  - " + failure)
        return 1
    print("self-test: {} cases, the gate fires on each break and stays quiet when clean.".format(len(cases)))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=os.getcwd(), help="the repository to scan (default: cwd)")
    parser.add_argument("--self-test", action="store_true", help="prove this gate can fail, against a synthetic tree")
    args = parser.parse_args(argv)
    if args.self_test:
        return self_test()
    root = Path(args.root)
    if not root.is_dir():
        print("verify-ruling-citations: usage — --root is not a directory: {}".format(root), file=sys.stderr)
        return 2
    defects, defined, cited = check(root)
    if defects:
        print("verify-ruling-citations: FAILED — {} defect(s) under {}.".format(len(defects), root))
        for defect in defects:
            print("  - " + defect)
        return 1
    print("verify-ruling-citations: OK — {} ruling(s) cited, {} defined by a heading in {} (root {}).".format(
        len(cited), len(defined), REGISTER.as_posix(), root))
    return 0


if __name__ == "__main__":
    sys.exit(main())
