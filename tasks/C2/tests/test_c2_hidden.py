"""Hidden structural + content checks for C2. Stdlib only. Run with python -m unittest.

The architecture note under test is the cell's docs/architecture.md. This file is never placed
in the workspace. The structural checks require the sections named in the prompt (C1's six
sections, plus a component list and one ADR-style decision with alternatives). The two content
checks are narrow and fact-specific (not a keyword any on-topic text would contain, per A4's
finding, and matching B2's pattern for the same underlying spec): each targets one decided fact
carried forward from the given spec (tasks/B2's reference spec, consumed here as the given), and
each is shown in oracle/evidence.md failing on exactly one of the two committed negative controls
under oracle/reference/controls/, in the pattern A5 uses.
"""

import re
import unittest
from pathlib import Path

ARCH = Path("docs/architecture.md")

REQUIRED_SECTIONS = (
    "## Context",
    "## Components",
    "## Component list",
    "## Data structure",
    "## Operations",
    "## Exception safety",
    "## Complexity",
    "## Decision",
)

# Fact 1 (the given spec's core reason the capability exists at all, carried from the primer via
# B2): the architecture must state that the component reading a scope's revision reads the
# repository directly, in explicit contrast to the daemon's own last-known/cached state.
_REPOSITORY_NOT_DAEMON = re.compile(
    r"reposit\w*[^.\n]{0,220}?(?:not|never|independent(?:ly)? of)[^.\n]{0,160}?daemon"
    r"|daemon[^.\n]{0,160}?(?:not|never)[^.\n]{0,220}?reposit\w*",
    re.IGNORECASE,
)

# Fact 2 (the given spec's non-goal, carried from B2): the design must state that the prober
# itself never repairs/fixes/re-extracts to close a drift -- that stays another component's job.
_DOES_NOT_REPAIR = re.compile(
    r"(?:does not|never|is not responsible for)[^.\n]{0,60}?(?:repair|fix|correct|resolve)[^.\n]{0,80}?drift",
    re.IGNORECASE,
)

# The Decision section must be ADR-shaped: a decision plus alternatives that were considered and
# rejected, not a bare decision statement.
_ALTERNATIVES = re.compile(r"alternative", re.IGNORECASE)


def _heading(line: str) -> str | None:
    stripped = line.strip()
    marks = len(stripped) - len(stripped.lstrip("#"))
    if marks == 2 and stripped[marks:marks + 1] == " ":
        return stripped
    return None


def _section_bodies(text: str) -> dict[str, str]:
    bodies: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        heading = _heading(line)
        if heading is not None:
            current = heading
            bodies.setdefault(current, [])
            continue
        if current is not None:
            bodies[current].append(line)
    return {heading: "\n".join(lines).strip() for heading, lines in bodies.items()}


class HiddenArchitecture(unittest.TestCase):
    def test_architecture_document_present(self):
        self.assertTrue(ARCH.is_file(), f"{ARCH.as_posix()} is missing")

    def test_architecture_required_sections(self):
        self.assertTrue(ARCH.is_file(), f"{ARCH.as_posix()} is missing")
        bodies = _section_bodies(ARCH.read_text(encoding="utf-8"))
        missing = [heading for heading in REQUIRED_SECTIONS if not bodies.get(heading)]
        self.assertEqual(missing, [], f"missing or empty sections: {missing}")

    def test_decision_names_alternatives(self):
        """The Decision section is ADR-style: it must name at least one alternative considered,
        not just state the chosen design."""
        self.assertTrue(ARCH.is_file(), f"{ARCH.as_posix()} is missing")
        bodies = _section_bodies(ARCH.read_text(encoding="utf-8"))
        decision_body = bodies.get("## Decision", "")
        self.assertRegex(
            decision_body, _ALTERNATIVES,
            "## Decision must name at least one alternative considered (ADR shape)",
        )

    def test_comparison_source_is_the_repository_not_the_daemon(self):
        self.assertTrue(ARCH.is_file(), f"{ARCH.as_posix()} is missing")
        text = ARCH.read_text(encoding="utf-8")
        self.assertRegex(
            text, _REPOSITORY_NOT_DAEMON,
            "architecture does not state that the revision read is from the repository, in "
            "contrast to the daemon's own last-known state",
        )

    def test_prober_does_not_repair_the_drift_itself(self):
        self.assertTrue(ARCH.is_file(), f"{ARCH.as_posix()} is missing")
        text = ARCH.read_text(encoding="utf-8")
        self.assertRegex(
            text, _DOES_NOT_REPAIR,
            "architecture does not state that the prober itself never repairs/fixes/re-extracts "
            "to close the drift",
        )


if __name__ == "__main__":
    unittest.main()
