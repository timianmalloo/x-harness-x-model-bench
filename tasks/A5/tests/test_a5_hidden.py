"""Hidden structural and content checks for A5. Stdlib only. Run with python -m unittest.

The spec under test is the cell's docs/specs/what-changed-view.md. This file is never placed in
the workspace. The hidden tests check that the required specification was authored, includes the
mandatory /specify sections, and resolves the 4 key clarification dimensions.

Each clarification check pairs a positive assertion (the decided content is present) with a
negative assertion scoped to the "In scope" half of the In scope / Out of scope section (the
plausible wrong answer's content must not appear there as something the spec put in scope). A
single on-topic keyword that any plausible answer would contain proves nothing (tasks/README.md,
new-bench-task Done-when); every check here is built to fail for a specific, plausible wrong
document — see oracle/reference/controls/ and oracle/README.md's discrimination proof.
"""

from __future__ import annotations

import unittest
from pathlib import Path

SPEC = Path("docs/specs/what-changed-view.md")

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


def _in_scope_only(scope_body: str) -> str:
    """The "In scope" half of the In scope / Out of scope section body, lowercased. A plausible
    wrong answer's content is checked against this half only, so a decision correctly named as an
    explicit non-goal never trips the negative assertion — only a decision the spec put IN scope
    does."""
    lowered = scope_body.lower()
    return lowered.split("out of scope", 1)[0]


class TestA5HiddenSpec(unittest.TestCase):
    def test_spec_file_present(self):
        """The specification file must exist at docs/specs/what-changed-view.md."""
        self.assertTrue(SPEC.is_file(), f"{SPEC.as_posix()} is missing")

    def test_spec_required_sections(self):
        """All mandatory sections from the /specify contract must be present and non-empty."""
        self.assertTrue(SPEC.is_file(), f"{SPEC.as_posix()} is missing")
        bodies = _section_bodies(SPEC.read_text(encoding="utf-8"))
        missing = [heading for heading in REQUIRED_SECTIONS if not bodies.get(heading)]
        self.assertEqual(missing, [], f"missing or empty sections: {missing}")

    def test_clarification_scope(self):
        """Clarification 1: the view covers only the current lane's own worktree, never every
        lane or the wider repository."""
        self.assertTrue(SPEC.is_file(), f"{SPEC.as_posix()} is missing")
        text = SPEC.read_text(encoding="utf-8")
        bodies = _section_bodies(text)
        problem_body = bodies.get("### Problem", "").lower()
        core_body = bodies.get("### Core scenario", "").lower()
        scope_body = bodies.get("### In scope / Out of scope (explicit non-goals)", "")
        combined = f"{problem_body} {core_body} {scope_body.lower()}"

        self.assertTrue(
            any(term in combined for term in ("own worktree", "own lane")),
            "Spec must scope the view to the current lane's own worktree/lane",
        )

        in_scope = _in_scope_only(scope_body)
        wrong_scope_terms = (
            "all lanes", "every lane", "across lanes", "every agent", "all agents",
            "across agents", "entire repository", "whole repository", "across the repository",
        )
        self.assertFalse(
            any(term in in_scope for term in wrong_scope_terms),
            "Spec must not put changes across every lane/agent or the wider repository in scope",
        )

    def test_clarification_granularity(self):
        """Clarification 2: a file-level list with a change kind, never full diff content."""
        self.assertTrue(SPEC.is_file(), f"{SPEC.as_posix()} is missing")
        text = SPEC.read_text(encoding="utf-8").lower()
        bodies = _section_bodies(SPEC.read_text(encoding="utf-8"))
        scope_body = bodies.get("### In scope / Out of scope (explicit non-goals)", "")

        self.assertTrue(
            "added, modified, or deleted" in text or "added/modified/deleted" in text,
            "Spec must classify each changed file as added, modified, or deleted",
        )

        in_scope = _in_scope_only(scope_body)
        wrong_granularity_terms = (
            "line-by-line diff", "full diff", "unified diff", "diff content", "patch content",
        )
        self.assertFalse(
            any(term in in_scope for term in wrong_granularity_terms),
            "Spec must not put full line-by-line diff content in scope",
        )

    def test_clarification_source_of_truth(self):
        """Clarification 3: the list is computed from git, never reconstructed from the
        tool-call or audit log."""
        self.assertTrue(SPEC.is_file(), f"{SPEC.as_posix()} is missing")
        text = SPEC.read_text(encoding="utf-8").lower()
        bodies = _section_bodies(SPEC.read_text(encoding="utf-8"))
        scope_body = bodies.get("### In scope / Out of scope (explicit non-goals)", "")

        self.assertIn("from git", text, "Spec must compute the list from git")

        in_scope = _in_scope_only(scope_body)
        wrong_source_terms = ("audit log", "tool-call log", "tool-call history")
        self.assertFalse(
            any(term in in_scope for term in wrong_source_terms),
            "Spec must not put the tool-call or audit log in scope as the source of the list",
        )

    def test_clarification_refresh(self):
        """Clarification 4: the view is computed on demand, never a live-updating stream."""
        self.assertTrue(SPEC.is_file(), f"{SPEC.as_posix()} is missing")
        text = SPEC.read_text(encoding="utf-8").lower()
        bodies = _section_bodies(SPEC.read_text(encoding="utf-8"))
        scope_body = bodies.get("### In scope / Out of scope (explicit non-goals)", "")

        self.assertIn("on demand", text, "Spec must compute the list on demand")

        in_scope = _in_scope_only(scope_body)
        wrong_refresh_terms = (
            "live-updating", "live updating", "real-time", "continuously refresh",
            "continuously updat", "background poll", "streaming",
        )
        self.assertFalse(
            any(term in in_scope for term in wrong_refresh_terms),
            "Spec must not put a live-updating or continuously streaming view in scope",
        )

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
