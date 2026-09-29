"""Hidden structural + content checks for B3. Stdlib only. Run with python -m unittest.

The spec under test is the cell's docs/specs/p1-estimator-validated.md. This file is never
placed in the workspace. Scenario 2 is judged; the two structural checks require the spec
file and the sections named in the prompt. The two content checks are narrow and fact-specific
(not a keyword any on-topic text would contain, per A4's finding): each targets one decided
fact from the primer, restated in prompt.md, and pairs a positive assertion (the decided
content is present) with a negative assertion scoped to the "In scope" half of the In scope /
Out of scope section (the plausible wrong answer's content must not appear there as something
the spec put in scope) — A5's discrimination pattern. See oracle/README.md and
oracle/reference/controls/ for the proof each check fails exactly one plausible wrong answer.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

SPEC = Path("docs/specs/p1-estimator-validated.md")

REQUIRED_SECTIONS = (
    "## Part A — Functional specification",
    "## Part B — UX specification",
    "## Part C — UI specification",
    "### Core scenario",
    "### In scope / Out of scope (explicit non-goals)",
    "### User stories & acceptance criteria (testable)",
    "### Non-functional requirements (ISO/IEC 25010 checklist)",
)

# Fact 1 (primer, phase P1 "Contents"): validation is against DTIC ADA032272's real
# towing-tank lift and drag data for the NACA 16-309 and 64A309 sections. A spec that
# validates against a synthetic, CFD-computed, or self-consistency reference instead has
# dropped the one point the primer makes about *why* validation here is worth a gate: the
# closed-form chain is checked against experiment, not against itself.
_VALIDATION_SOURCE = re.compile(
    r"ADA032272[^.\n]{0,200}?16-309[^.\n]{0,160}?64A309"
    r"|ADA032272[^.\n]{0,200}?64A309[^.\n]{0,160}?16-309"
    r"|16-309[^.\n]{0,160}?64A309[^.\n]{0,200}?ADA032272"
    r"|64A309[^.\n]{0,160}?16-309[^.\n]{0,200}?ADA032272",
    re.IGNORECASE,
)

_WRONG_VALIDATION_SOURCE_TERMS = (
    "cfd-computed", "cfd computed", "self-consistency", "self consistency",
    "synthetic data", "synthetic reference", "internally generated", "internal consistency",
    "simulated data", "computed reference values", "no external validation",
)

# Fact 2 (primer, phase P1 "Contents"): the section catalog supports both the Selig and the
# Lednicer aerofoil coordinate formats, detected automatically. A spec that supports only one
# format, or pushes format identification onto the caller, has dropped the defect-taught
# requirement the primer names.
_DUAL_FORMAT_DETECTION = re.compile(
    r"selig[^.\n]{0,160}?lednicer[^.\n]{0,160}?detect"
    r"|lednicer[^.\n]{0,160}?selig[^.\n]{0,160}?detect"
    r"|detect[^.\n]{0,160}?selig[^.\n]{0,160}?lednicer"
    r"|detect[^.\n]{0,160}?lednicer[^.\n]{0,160}?selig",
    re.IGNORECASE,
)

_WRONG_FORMAT_TERMS = (
    "selig format only", "lednicer format only", "selig only", "lednicer only",
    "single format", "one format only", "caller must specify the format",
    "caller specifies the format", "manually specify the format", "manually convert",
    "must pre-convert", "requires the user to convert",
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
    """The "In scope" half of the In scope / Out of scope section body, lowercased. A
    plausible wrong answer's content is checked against this half only, so a decision
    correctly named as an explicit non-goal never trips the negative assertion — only a
    decision the spec put IN scope does."""
    lowered = scope_body.lower()
    return lowered.split("out of scope", 1)[0]


class HiddenSpec(unittest.TestCase):
    def test_spec_file_present(self):
        self.assertTrue(SPEC.is_file(), f"{SPEC.as_posix()} is missing")

    def test_spec_required_sections(self):
        self.assertTrue(SPEC.is_file(), f"{SPEC.as_posix()} is missing")
        bodies = _section_bodies(SPEC.read_text(encoding="utf-8"))
        missing = [heading for heading in REQUIRED_SECTIONS if not bodies.get(heading)]
        self.assertEqual(missing, [], f"missing or empty sections: {missing}")

    def test_validation_is_against_real_experimental_data(self):
        self.assertTrue(SPEC.is_file(), f"{SPEC.as_posix()} is missing")
        text = SPEC.read_text(encoding="utf-8")
        self.assertRegex(
            text, _VALIDATION_SOURCE,
            "spec does not state validation against DTIC ADA032272's NACA 16-309 and "
            "64A309 towing-tank data",
        )
        bodies = _section_bodies(text)
        scope_body = bodies.get("### In scope / Out of scope (explicit non-goals)", "")
        in_scope = _in_scope_only(scope_body)
        self.assertFalse(
            any(term in in_scope for term in _WRONG_VALIDATION_SOURCE_TERMS),
            "Spec must not put a synthetic/self-computed validation reference in scope",
        )

    def test_section_catalog_detects_selig_and_lednicer(self):
        self.assertTrue(SPEC.is_file(), f"{SPEC.as_posix()} is missing")
        text = SPEC.read_text(encoding="utf-8")
        self.assertRegex(
            text, _DUAL_FORMAT_DETECTION,
            "spec does not state automatic detection of both the Selig and Lednicer "
            "aerofoil coordinate formats",
        )
        bodies = _section_bodies(text)
        scope_body = bodies.get("### In scope / Out of scope (explicit non-goals)", "")
        in_scope = _in_scope_only(scope_body)
        self.assertFalse(
            any(term in in_scope for term in _WRONG_FORMAT_TERMS),
            "Spec must not put single-format support or caller-specified format in scope",
        )

if __name__ == "__main__":
    unittest.main()
