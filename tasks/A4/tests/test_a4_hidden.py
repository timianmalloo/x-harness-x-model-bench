"""Hidden structural and content checks for A4. Stdlib only. Run with python -m unittest.

The spec under test is the cell's docs/specs/reusable-wing-definition.md.
This file is never placed in the workspace. The hidden tests check that the
required specification was authored, includes the mandatory /specify sections,
and resolves the 5 key clarification dimensions.
"""

from __future__ import annotations

import unittest
from pathlib import Path

SPEC = Path("docs/specs/reusable-wing-definition.md")

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


class TestA4HiddenSpec(unittest.TestCase):
    def test_spec_file_present(self):
        """The specification file must exist at docs/specs/reusable-wing-definition.md."""
        self.assertTrue(SPEC.is_file(), f"{SPEC.as_posix()} is missing")

    def test_spec_required_sections(self):
        """All mandatory sections from the /specify contract must be present and non-empty."""
        self.assertTrue(SPEC.is_file(), f"{SPEC.as_posix()} is missing")
        bodies = _section_bodies(SPEC.read_text(encoding="utf-8"))
        missing = [heading for heading in REQUIRED_SECTIONS if not bodies.get(heading)]
        self.assertEqual(missing, [], f"missing or empty sections: {missing}")

    def test_clarification_persistence_vs_sharing(self):
        """Clarification 1: The spec must address local file persistence rather than cloud/network sharing."""
        self.assertTrue(SPEC.is_file(), f"{SPEC.as_posix()} is missing")
        text = SPEC.read_text(encoding="utf-8")
        bodies = _section_bodies(text)
        scope_body = bodies.get("### In scope / Out of scope (explicit non-goals)", "").lower()
        prob_body = bodies.get("### Problem", "").lower()
        core_body = bodies.get("### Core scenario", "").lower()
        combined = f"{prob_body} {scope_body} {core_body}"

        has_local_file = any(term in combined for term in ("local file", "file persistence", "project file", "to disk", "on disk", "filesystem", "file-based"))
        self.assertTrue(has_local_file, "Spec must specify local file persistence in problem, scope, or core scenario")

        in_scope = scope_body.split("out of scope")[0] if "out of scope" in scope_body else scope_body
        self.assertFalse(any(term in in_scope for term in ("cloud rest", "remote database", "network sync", "cloud service", "remote service")),
                         "Cloud or networked sharing must not be in-scope")

    def test_clarification_format(self):
        """Clarification 2: The spec must specify structured JSON as the serialization format."""
        self.assertTrue(SPEC.is_file(), f"{SPEC.as_posix()} is missing")
        text = SPEC.read_text(encoding="utf-8").lower()
        self.assertIn("json", text, "Spec must specify JSON serialization format")

    def test_clarification_versioning(self):
        """Clarification 3: The spec must mandate schema/format versioning."""
        self.assertTrue(SPEC.is_file(), f"{SPEC.as_posix()} is missing")
        text = SPEC.read_text(encoding="utf-8").lower()
        has_versioning = any(term in text for term in ("version", "schema version", "cfd-wing/1", "format identifier"))
        self.assertTrue(has_versioning, "Spec must specify schema/format versioning")

    def test_clarification_validation(self):
        """Clarification 4: The spec must require fail-closed validation of wing invariants upon load."""
        self.assertTrue(SPEC.is_file(), f"{SPEC.as_posix()} is missing")
        text = SPEC.read_text(encoding="utf-8").lower()
        has_validation = any(term in text for term in ("invariant", "validation", "fail-closed", "fail closed", "reject"))
        self.assertTrue(has_validation, "Spec must specify fail-closed invariant validation")

    def test_clarification_scope(self):
        """Clarification 5: The spec must confine persistence to defining geometry and exclude derived quantities."""
        self.assertTrue(SPEC.is_file(), f"{SPEC.as_posix()} is missing")
        text = SPEC.read_text(encoding="utf-8").lower()
        has_scope = any(term in text for term in ("station", "derived", "planform"))
        self.assertTrue(has_scope, "Spec must address geometric scope and derived quantities")

    def test_gherkin_acceptance_criteria(self):
        """User stories must specify falsifiable Gherkin acceptance criteria (Given/When/Then)."""
        self.assertTrue(SPEC.is_file(), f"{SPEC.as_posix()} is missing")
        text = SPEC.read_text(encoding="utf-8")
        bodies = _section_bodies(text)
        ac_section = bodies.get("### User stories & acceptance criteria (testable)", "")
        self.assertIn("Given", ac_section, "Acceptance criteria must contain Given clauses")
        self.assertIn("When", ac_section, "Acceptance criteria must contain When clauses")
        self.assertIn("Then", ac_section, "Acceptance criteria must contain Then clauses")


if __name__ == "__main__":
    unittest.main()
