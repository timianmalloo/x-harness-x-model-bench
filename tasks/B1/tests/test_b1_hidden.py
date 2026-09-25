"""Hidden structural checks for B1. Stdlib only. Run with python -m unittest.

The spec under test is the cell's docs/specs/p0-conventions-and-spine.md.
This file is never placed in the workspace. Scenario 2 is judged; these checks
only require the spec file and the sections named in the prompt.
"""

import unittest
from pathlib import Path

SPEC = Path("docs/specs/p0-conventions-and-spine.md")

REQUIRED_SECTIONS = (
    "## Part A — Functional specification",
    "## Part B — UX specification",
    "## Part C — UI specification",
    "### Core scenario",
    "### In scope / Out of scope (explicit non-goals)",
    "### User stories & acceptance criteria (testable)",
    "### Non-functional requirements (ISO/IEC 25010 checklist)",
)


def _heading(line: str) -> str | None:
    stripped = line.strip()
    marks = len(stripped) - len(stripped.lstrip("#"))
    if marks in (2, 3) and stripped[marks:marks + 1] == " ":
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


class HiddenSpec(unittest.TestCase):
    def test_spec_file_present(self):
        self.assertTrue(SPEC.is_file(), f"{SPEC.as_posix()} is missing")

    def test_spec_required_sections(self):
        self.assertTrue(SPEC.is_file(), f"{SPEC.as_posix()} is missing")
        bodies = _section_bodies(SPEC.read_text(encoding="utf-8"))
        missing = [heading for heading in REQUIRED_SECTIONS if not bodies.get(heading)]
        self.assertEqual(missing, [], f"missing or empty sections: {missing}")


if __name__ == "__main__":
    unittest.main()
