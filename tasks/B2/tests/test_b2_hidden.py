"""Hidden structural + content checks for B2. Stdlib only. Run with python -m unittest.

The spec under test is the cell's docs/specs/freshness-prober.md. This file is never
placed in the workspace. Scenario 2 is judged; the two structural checks require the
spec file and the sections named in the prompt. The two content checks are narrow and
fact-specific (not a keyword any on-topic text would contain, per A4's finding): each
targets one decided fact from the primer and is shown in oracle/README.md failing on a
plausible wrong answer that gets that one fact wrong while staying on-topic throughout.
"""

import re
import unittest
from pathlib import Path

SPEC = Path("docs/specs/freshness-prober.md")

REQUIRED_SECTIONS = (
    "## Part A — Functional specification",
    "## Part B — UX specification",
    "## Part C — UI specification",
    "### Core scenario",
    "### In scope / Out of scope (explicit non-goals)",
    "### User stories & acceptance criteria (testable)",
    "### Non-functional requirements (ISO/IEC 25010 checklist)",
)

# Fact 1 (primer, "Failure and resilience"): the comparison source is the repository,
# stated in explicit contrast to the daemon's own last-event/last-known view. A spec
# that only says "detects stale data" without that contrast has dropped the one point
# the primer makes about *why* an independent prober exists at all.
_REPOSITORY_NOT_DAEMON = re.compile(
    r"reposit\w*[^.\n]{0,220}?(?:not|never|independent(?:ly)? of)[^.\n]{0,160}?daemon"
    r"|daemon[^.\n]{0,160}?(?:not|never)[^.\n]{0,220}?reposit\w*",
    re.IGNORECASE,
)

# Fact 2 (prompt.md): a divergence raises exactly one incident per scope and the prober
# does not itself repair the drift. A spec that lets the prober "fix", "correct", or
# "re-sync" the drift itself has taken on the extractor's job, which the primer never
# grants it.
_DOES_NOT_REPAIR = re.compile(
    r"(?:does not|never|is not responsible for)[^.\n]{0,60}?(?:repair|fix|correct|resolve)[^.\n]{0,80}?drift",
    re.IGNORECASE,
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

    def test_comparison_source_is_the_repository_not_the_daemon(self):
        self.assertTrue(SPEC.is_file(), f"{SPEC.as_posix()} is missing")
        text = SPEC.read_text(encoding="utf-8")
        self.assertRegex(
            text, _REPOSITORY_NOT_DAEMON,
            "spec does not state the repository (not the daemon's own last-event view) "
            "is the comparison source",
        )

    def test_prober_does_not_repair_the_drift_itself(self):
        self.assertTrue(SPEC.is_file(), f"{SPEC.as_posix()} is missing")
        text = SPEC.read_text(encoding="utf-8")
        self.assertRegex(
            text, _DOES_NOT_REPAIR,
            "spec does not state that the prober itself never repairs/fixes the drift",
        )


if __name__ == "__main__":
    unittest.main()
